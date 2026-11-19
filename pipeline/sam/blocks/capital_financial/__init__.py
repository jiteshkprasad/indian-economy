"""capital_financial: the SAM's capital and financial accounts (plan docs/phase2/plans/capital_financial.md).

Refs: I1a I2 I2a I3a K1 K4 K7 K7a K7b K8 K8a K8d K9 K9b D3; satellites S4 S5 (and memo tables).

Reads (clean data, one vintage each unless named):
- NAS 2026 (31 Aug 2026): St 1.9 saving (K1, K4, gold), 1.11 GFCF by sector x asset, 1.14 GCF by sector,
  5.3 household financial saving (K7a, K8a), 7.2A/B CIS checks, derived S-I errors and omissions (D3).
- SUT 2023-24 (io_tables_sut_use): GFCF by product (I1a rows, via the committed concordance
  io_tables_sut_product_to_sam34), valuables and CII totals.
- RBI FSF 2023-24 (rbi_financial_accounts_fsf_balance_sheets, vintage 2026-01-21): leaf-sector transactions
  (K7, K8, K8d), the counterparty keys of K7b, the K9 decomposition; St 6.13 (S4) and St 7 (checks);
  RBI T52(a)/(b) household stocks (S5, checks).
- Union Finance Accounts 2023-24 (capital outlay by major head, IGAS-2 capital grants) and RBI State
  Finances (capital outlay): the Centre/State GFCF key; Union AFS (Centre-State loans check); NSSF (PPF).
- RBI Annual Report 2023-24 (vintage 2024-05-30): RBI GFCF and the surplus payable (K9b); RTP 2023-24
  (vintage 2024-12-26): the HDFC merger memo.
- DEPENDS: government (K8e, K3a, K6, R2k), fincorp (K2a; F4a GOS as the FC GFCF key), rest_of_world
  (K8b counterparts `row_financial_counterparts`, R14a, K8c), households (`hh_keys` AIDIS keys for S5),
  production (none numerically; its I1/I3/valuables targets are what I1a/I3a/I2a must add up to).

Writes (roles in brackets): I1a C_x <- K_s GFCF by commodity x investor (free, RAS on SUT rows and NAS
sector columns); I2 / I2a valuables on C_GJOM <- K_HH (fixed); I3a K_DSTK <- K_s (anchored; FC split free);
K1 NFC saving (fixed); K7a / K8a households' NAS 5.3 lines (fixed); K7b counterparts of households (`hh_cp`)
and of the RoW (`row_cp_<line>`) (free, high); K7 / K8 / K8d reconciled FSF domestic pairs (`dom_pos` /
`dom_neg`: control side anchored 10% where it is a pure sum of published reports, else free medium) and
each sector's own FSF trade credit / other payables (`fsf_f81` / `fsf_f89`, free low); K9b RBI surplus
payable / receivable (anchored 2%); K9 residual per domestic sector (`residual_pos` / `residual_neg`, free
low); D3 K_s <- X_DISC (fixed; K_HH = I2a exactly, the rest pro rata to corporate GCF). Constraint-only: K4.

Estimated: the I1a matrix, Centre/State and FC sub-sector GFCF, the FC CIS split, the D3 allocation, every
keyed FSF pair, all K7b postings, K9. Skipped (logged in docs/phase2/issues/capital_financial.md): FSF
'other'/NEC items, monetary gold and SDRs, RBI F6 and MF monetary gold, SFC/SIDC MF-unit holdings, the
non-household insurance/pension cells and non-MF F52 liabilities no step reads (fsf.unread_cells), every
FSF household- and RoW-counterparty cell (rebuilt from NAS 5.3 and the BoP), I_RESV (rest_of_world K8c).

Report only (satellite k9_sensitivity, plan T24): K9 by account with one rule changed at a time (equity issuer
control; no insurers' revaluation strip; the D3 remainder all to K_NFPU). No entry depends on it. The plan's
2022-23 FSF validation run is not built (it needs every DEPENDS block for 2022-23).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl

from pipeline.sam.blocks.capital_financial import fsf as F
from pipeline.sam.blocks.capital_financial import households as H
from pipeline.sam.blocks.capital_financial import params as P
from pipeline.sam.blocks.capital_financial import physical as X
from pipeline.sam.blocks.capital_financial import residuals as R
from pipeline.sam.blocks.capital_financial import row as W
from pipeline.sam.blocks.capital_financial import satellites as S
from pipeline.sam.framework import BlockContext, BlockResult, SamError, Satellite, constraint, entry

BLOCK = "capital_financial"
REFS = ["I1a", "I2", "I2a", "I3a", "K1", "K4", "K7", "K7a", "K7b", "K8", "K8a", "K8d", "K9", "K9b", "D3", "S4", "S5"]
DEPENDS = ["production", "households", "rest_of_world", "government", "fincorp"]

CHECK_TOL = 1.0


@dataclass
class Deps:
    """What this block reads from its DEPENDS (read_deps); tests pass synthetic ones to compute()."""

    k8e: float  # government's K8e on I_LOAN <- K_GCEN (0 if government writes none)
    k8e_pids: list[str]
    fc_gos: dict[tuple[str, str], float]  # (K_BANK|K_NBFC|K_INSP, public|private) -> FC GOS (fincorp F4a)
    fc_pids: list[str]
    row_sat: pl.DataFrame  # rest_of_world row_financial_counterparts
    r14a: pl.DataFrame  # rest_of_world R14a entries (row, col, value, prov_id)
    row_pids: list[str]
    entries: pl.DataFrame  # DEPENDS entries touching a K_* or I_* account (row, col, ref, component, value, block)
    hh_keys: pl.DataFrame | None  # households hh_keys
    hh_pids: list[str] = field(default_factory=list)


def build(ctx: BlockContext) -> BlockResult:
    return compute(ctx, read_deps(ctx))


# =====================================================================================================
# dependencies
# =====================================================================================================

ENTRY_COLS = ["row", "col", "ref", "component", "value", "block", "prov_id"]


def read_deps(ctx: BlockContext) -> Deps:
    gov = ctx.block_entries("government")
    k8e = gov.filter((pl.col("ref") == "K8e") & (pl.col("row") == "I_LOAN") & (pl.col("col") == "K_GCEN"))
    if k8e.height == 0:
        ctx.warn("government wrote no K8e: the Centre -> States loan pair is the full FSF figure (plan s.6.4 Q7)")
    fin = ctx.block_entries("fincorp").filter(
        (pl.col("ref") == "F4a") & (pl.col("col") == "F_GOSC") & pl.col("row").is_in(["E_BANK", "E_NBFC", "E_INSP"])
    )
    fc_gos: dict[tuple[str, str], float] = {}
    for r in fin.iter_rows(named=True):
        parts = [r["component"]] if r["component"] in ("public", "private") else ["public", "private"]
        if r["component"] not in ("public", "private"):
            ctx.warn(
                f"fincorp F4a {r['row']} has component {r['component']!r}, not public/private: used for both parts"
            )
        for part in parts:
            k = (P.E_TO_K[r["row"]], part)
            fc_gos[k] = fc_gos.get(k, 0.0) + float(r["value"])
    row_e = ctx.block_entries("rest_of_world")
    sat = ctx.satellite("rest_of_world", W.SATELLITE)
    r14a = row_e.filter(pl.col("ref") == "R14a").select("row", "col", "value", "prov_id")
    capfin = ctx.accounts.in_group("CAP") + ctx.accounts.in_group("INST")  # capital and instrument accounts
    frames = []
    for b in DEPENDS:
        e = ctx.block_entries(b)
        frames.append(
            e.filter(pl.col("row").is_in(capfin) | pl.col("col").is_in(capfin))
            .with_columns(pl.col("component").fill_null("total"))
            .select(ENTRY_COLS)
        )
    hh_keys = ctx.satellite("households", "hh_keys")
    return Deps(
        k8e=float(k8e["value"].sum()),
        k8e_pids=sorted(set(k8e["prov_id"].to_list())),
        fc_gos=dict(sorted(fc_gos.items())),
        fc_pids=sorted(set(fin["prov_id"].to_list())),
        row_sat=sat,
        r14a=r14a,
        row_pids=sorted(set(sat["prov_id"].to_list()) | set(r14a["prov_id"].to_list())),
        entries=pl.concat(frames, how="vertical"),
        hh_keys=hh_keys,
        hh_pids=sorted(set(hh_keys["prov_id"].to_list())),
    )


# =====================================================================================================
# the block
# =====================================================================================================


class _Out:
    """Collects entries, constraints and satellites."""

    def __init__(self) -> None:
        self.entries: list[dict] = []
        self.cons: list[dict] = []
        self.sats: dict[str, Satellite] = {}

    def add(
        self,
        row: str,
        col: str,
        ref: str,
        v: float,
        pid: str,
        status: str,
        role: str,
        comp: str = "total",
        tol: float | None = None,
        conf: str | None = None,
        note: str | None = None,
    ) -> None:
        if v == 0.0:
            return
        self.entries.append(
            entry(
                row,
                col,
                ref,
                v,
                prov_id=pid,
                status=status,
                role=role,
                component=comp,
                tol_rel=tol,
                confidence=conf,
                note=note,
            )
        )


def compute(ctx: BlockContext, deps: Deps) -> BlockResult:
    out = _Out()

    def val(ds: str, sid: str, **kw) -> tuple[float, str]:
        return ctx.value(ds, sid, vintage=kw.pop("vintage", P.LATEST), **kw)

    # ---------------------------------------------------------------------------------------------
    # FSF extraction (plan s.2.0)
    # ---------------------------------------------------------------------------------------------
    fsf = ctx.rows(P.FSF, vintage=P.LATEST)
    rep = F.reports(fsf)
    totals = F.statement_totals(fsf)
    fsf_pids = sorted(set(rep["prov_id"].to_list()) | set(totals["prov_id"].to_list()))
    ctx.log(f"FSF 2023-24: {rep.height} leaf report cells from {rep['sub'].n_unique()} statements")

    # ---------------------------------------------------------------------------------------------
    # K1, I2, I2a (plan s.2.3, s.2.5)
    # ---------------------------------------------------------------------------------------------
    k1 = {
        k: val(P.NAS19, f"s1_9.{s}.current")
        for k, s in (("K_NFPU", "public_non_financial_corporations"), ("K_NFPR", "private_non_financial_corporations"))
    }
    pid = ctx.prov(
        ref="K1",
        status="official",
        inputs=[p for _, p in k1.values()],
        method="Gap map K1: NFC gross saving as published in NAS 2026 Statement 1.9 (public and private "
        "non-financial corporations), K_NFPU <- E_NFPU and K_NFPR <- E_NFPR. Private NFC saving is "
        "already net of foreign reinvested earnings (rest_of_world R14a).",
    )
    for k, (v, _) in k1.items():
        out.add(k, "E" + k[1:], "K1", v, pid, "official", "fixed")
    gold, gold_pid = val(P.NAS19, "s1_9.saving_in_the_form_of_gold_and_silver_ornaments.current")
    valu, valu_pid = val(P.SUT_USE, "use.valuables.total.current")
    pid_i2 = ctx.prov(
        ref="I2",
        status="official",
        inputs=[gold_pid],
        method="Gap map I2: household saving in gold and silver ornaments, NAS 2026 St 1.9 (= St 5.3), "
        "on C_GJOM <- K_HH. Jewellery is valuables, never PFCE.",
    )
    out.add("C_GJOM", "K_HH", "I2", gold, pid_i2, "official", "fixed", "gold_silver_ornaments")
    i2a = valu - gold
    pid_i2a = ctx.prov(
        ref="I2a",
        status="derived",
        inputs=[valu_pid, gold_pid],
        source_id=P.SRC_SUT,
        method="Gap map I2a: SUT 2023-24 net acquisition of valuables (use.valuables.total, all on "
        "product 125, C_GJOM) less NAS household gold (I2): valuables no NAS sector finances. "
        "The SUT (not NAS 1.1, 0.28 lower) so C_GJOM equals production's valuables target; "
        "financed by D3 -> K_HH of the same amount (closure plan C5).",
    )
    out.add("C_GJOM", "K_HH", "I2a", i2a, pid_i2a, "derived", "fixed", "unsectored_valuables")

    # ---------------------------------------------------------------------------------------------
    # I1a GFCF by commodity x investor (plan s.2.2)
    # ---------------------------------------------------------------------------------------------
    gf = _gfcf(ctx, val, deps)
    cpid = ctx.prov(
        ref="I1a",
        status="estimated",
        inputs=gf["pids"],
        source_id=P.SRC_SUT,
        method="Gap map I1a: GFCF by commodity x investing account. Rows: SUT 2023-24 GFCF by product "
        "(use.gfcf.sut_pNNN) summed to commodities with the committed concordance "
        f"{P.PRODUCT_MAP}. Columns: NAS 2026 St 1.11 GFCF by sector x (SUT total / NAS total). "
        "GG split Centre/States by a capital-spending key (Union capital outlay less departmental "
        "commercial and investment heads 5002, 5003, 5201, 5225, 5275, 4416, 5465-5467, plus "
        "IGAS-2 capital grants to central autonomous bodies and to statutory bodies and development "
        "authorities, which government's K6 treats as inside G_CEN (its A-K6-4); vs RBI State "
        "Finances total capital outlay plus IGAS-2 capital grants to urban local bodies): the "
        "institutional view (DECISIONS D2-8) as far as clean data allow. FC: K_RBI = RBI Annual Report change in net "
        "fixed assets + depreciation (public); the rest of public FC and all private FC over "
        "K_BANK/K_NBFC/K_INSP by fincorp's F4a GOS by ownership part (CFC is not published; "
        "XR-6 boundary). Prior p(c,k) = column total x NAS 1.11 asset share of the column's sector "
        "x SUT(c)/SUT(asset group of c) (asset groups in params.ASSET_OF); RAS to rows and columns "
        f"to {P.RAS_TOL:g} relative ({gf['iterations']} iterations). The NAS asset classes are not "
        "constraints: NAS structures differ from SUT construction by Rs 82,666 crore.",
    )
    for (c, colid), v in gf["cells"].items():
        acct, part = colid.split("|")
        out.add(c, acct, "I1a", v, cpid, "estimated", "free", part, conf="medium")
    by_col = gf["by_col"]  # "K|part" -> column total written

    # ---------------------------------------------------------------------------------------------
    # I3a change in inventories by financing sector (plan s.2.4)
    # ---------------------------------------------------------------------------------------------
    cis_src = gf["cis"]  # NAS sector -> (value, pids)
    cii, cii_pid = val(P.SUT_USE, "use.cii.total.current")
    nonzero = {s: v for s, (v, _) in cis_src.items() if v != 0.0}
    scaled = X.scale_parts(nonzero, cii)
    cis_pids = sorted({p for _, ps in cis_src.values() for p in ps} | {cii_pid})
    pid_cis = ctx.prov(
        ref="I3a",
        status="derived",
        inputs=cis_pids,
        source_id=P.SRC_NAS,
        method="Gap map I3a: change in inventories by NAS sector = NAS 2026 St 1.14 GCF - St 1.11 GFCF "
        "(public FC is exactly 0 and not written), scaled by SUT CII total / sector sum "
        "(382,329.00 / 382,329.05: rounding) so K_DSTK's row equals production's I3. GG goes 100% "
        "to K_GCEN (NAS 7.2A puts public CIS in public administration; FCI and defence stores are "
        "central): a deviation from the gap map's pro rata rule (plan C17).",
    )
    sector_acct = {"nfc_pub": "K_NFPU", "nfc_pvt": "K_NFPR", "gg": "K_GCEN", "hh": "K_HH"}
    for s, a in sector_acct.items():
        out.add("K_DSTK", a, "I3a", scaled.get(s, 0.0), pid_cis, "derived", "anchored", tol=P.CIS_TOL)
    fc_cis = scaled.get("fc_pvt", 0.0) + scaled.get("fc_pub", 0.0)
    priv = {a: by_col.get(f"{a}|private", 0.0) for a in P.K_FC_GFCF}
    fc_cis_split = X.largest_remainder_split(fc_cis, priv) if fc_cis else {}
    pid_cis_fc = ctx.prov(
        ref="I3a",
        status="estimated",
        inputs=[pid_cis, cpid],
        source_id=P.SRC_NAS,
        method="Gap map I3a: private FC change in inventories (NAS 1.14 - 1.11, scaled as above) "
        "split over K_BANK/K_NBFC/K_INSP pro rata to their private-part GFCF in I1a (no "
        "sub-sector inventory data).",
    )
    for a, v in fc_cis_split.items():
        out.add("K_DSTK", a, "I3a", v, pid_cis_fc, "estimated", "free", "private", conf="medium")

    # ---------------------------------------------------------------------------------------------
    # D3 saving-investment errors and omissions (plan s.2.3)
    # ---------------------------------------------------------------------------------------------
    d3, d3_pid = val(P.NAS_RESID, "derived.si_errors_omissions.current")
    pid_d3h = ctx.prov(
        ref="D3",
        status="derived",
        inputs=[d3_pid, valu_pid, gold_pid],
        source_id=P.SRC_NAS,
        method="Gap map D3 (household part): X_DISC finances the valuables no NAS sector saves for, "
        "K_HH <- X_DISC = I2a = SUT valuables - NAS household gold, to the paisa, so K_HH closes "
        "(closure plan T7). The D3 total is NAS 2026 derived S-I errors and omissions; closure "
        "writes D1 = D2 + D3 + D4 as written (DECISIONS D2-3).",
    )
    out.add("K_HH", "X_DISC", "D3", i2a, pid_d3h, "derived", "fixed", "unsectored_valuables")
    gcf_w = gf["corp_gcf"]  # NFC NAS GCF and FC GCF split by I1a + I3a
    fc_gcf_sub = {
        a: by_col.get(f"{a}|public", 0.0) + by_col.get(f"{a}|private", 0.0) + fc_cis_split.get(a, 0.0)
        for a in ("K_RBI", *P.K_FC_GFCF)
    }
    s_fc = sum(fc_gcf_sub.values())
    weights = {
        "K_NFPU": gcf_w["nfc_pub"],
        "K_NFPR": gcf_w["nfc_pvt"],
        **{a: gcf_w["fc"] * v / s_fc for a, v in fc_gcf_sub.items()},
    }
    d3_split = X.largest_remainder_split(d3 - i2a, weights)
    pid_d3 = ctx.prov(
        ref="D3",
        status="estimated",
        inputs=[d3_pid, pid_d3h, cpid, *gf["gcf_pids"]],
        source_id=P.SRC_NAS,
        method="Gap map D3 (remainder): NAS S-I errors and omissions less the K_HH part, allocated to "
        "the corporate capital accounts pro rata to NAS 2026 St 1.14 GCF (public NFC, private NFC, "
        "FC; FC split by each sub-sector's I1a + I3a). Deviation from the gap map (sector with the "
        "largest NAS-FSF disagreement): after the FSF reconciliation that disagreement is mostly "
        "FSF-internal; household and GG saving are measured directly, corporate saving least "
        "(plan s.2.3, C16; alternative: all to K_NFPU).",
    )
    for a, v in d3_split.items():
        out.add(a, "X_DISC", "D3", v, pid_d3, "estimated", "fixed", "si_errors")

    # ---------------------------------------------------------------------------------------------
    # K7a, K8a households (NAS 5.3) and their counterparts (K7b hh_cp) (plan s.2.8)
    # ---------------------------------------------------------------------------------------------
    assets, liabs, coop = H.read_lines(ctx, val)
    pid_k7a = ctx.prov(
        ref="K7a",
        status="official",
        source_id=P.SRC_NAS,
        inputs=sorted({p for ln in assets if not ln.derived for p in ln.prov_ids}),
        method="Gap map K7a: households' financial assets, NAS 2026 St 5.3 lines as published, one "
        "SAM instrument each (currency; deposits with banks, co-operatives, non-banks; trade "
        "debt -> I_OTHR; shares and debentures = corporate + co-operative + secondary-market "
        "lines -> I_EQTY; MF units; G-secs; small savings; life, postal and State insurance) and "
        "PPF from NSSF (nssf.ppf.additions) on I_SSAV: PPF sits only in I_SSAV, never I_INPE.",
    )
    pid_k7a_d = ctx.prov(
        ref="K7a",
        status="derived",
        source_id=P.SRC_NAS,
        inputs=sorted({p for ln in assets if ln.derived for p in ln.prov_ids}),
        method="Gap map K7a: provident and pension funds other than PPF = NAS 5.3 provident and "
        "pension funds - NSSF PPF additions (PPF is proven to be inside the NAS PF line: NSSF "
        "net collection = NAS small savings + PPF; RBI T52(b) PPF stock change = the NSSF "
        "figure).",
    )
    for ln in assets:
        out.add(
            ln.instrument,
            "K_HH",
            "K7a",
            ln.value,
            pid_k7a_d if ln.derived else pid_k7a,
            "derived" if ln.derived else "official",
            "fixed",
            ln.component,
        )
    pid_k8a = ctx.prov(
        ref="K8a",
        status="official",
        inputs=sorted({p for ln in liabs for p in ln.prov_ids}),
        method="Gap map K8a: households' financial liabilities, NAS 2026 St 5.3 lines as published "
        "(bank advances, co-operatives, NBFCs, insurers, government), all I_LOAN. The lender "
        "split used for counterparts is in K7b (hh_cp).",
    )
    for ln in liabs:
        out.add("K_HH", "I_LOAN", "K8a", ln.value, pid_k8a, "official", "fixed", ln.component)
    gpf = {s: H.fsf_value(rep, s, "liabilities", "f6_pf", P.UNALLOCATED) for s in P.GG_CODES}
    hh_posts = H.postings(assets, liabs, rep, gpf, coop)
    pid_hh = ctx.prov(
        ref="K7b",
        status="estimated",
        inputs=sorted({pid_k7a, pid_k7a_d, pid_k8a, *fsf_pids}),
        source_id=P.SRC_NAS,
        method="Gap map K7b (households): each NAS 5.3 line posted on its counterparty in the same "
        "instrument (component hh_cp): currency -> K_RBI; the three deposit lines by the "
        "deposit-takers' FSF liabilities to households (absolute-share rule); trade debt -> "
        "K_NFPR; co-operative shares -> K_BANK and other shares by issuers' FSF F51 liabilities "
        "to households; MF -> K_MUTF; G-secs: States' FSF F3 to households, rest K_GCEN; small "
        "savings + PPF -> K_GCEN; life -> K_INSP; postal -> K_GCEN; State insurance -> K_GSTA "
        "(default, plan Q2); PF & pension: Centre and States by their FSF f6_pf, rest K_INSP. "
        "Loans: government by FSF hh F4 counterparties, insurers -> K_INSP, the rest by FC "
        "lenders' FSF F4 assets on households (SAM boundary: HDFC Ltd inside K_BANK). The FSF "
        "household statement never sets counterparty values.",
    )
    hh_cells: dict[tuple[str, str], float] = {}
    for p in hh_posts:
        cell = (p.account, p.instrument) if p.side == "liability" else (p.instrument, p.account)
        hh_cells[cell] = hh_cells.get(cell, 0.0) + p.value
    for (r_, c_), v in sorted(hh_cells.items()):
        out.add(r_, c_, "K7b", v, pid_hh, "estimated", "free", "hh_cp", conf="high")

    # ---------------------------------------------------------------------------------------------
    # K7, K8, K8d: reconciled FSF domestic pairs (plan s.2.7)
    # ---------------------------------------------------------------------------------------------
    life = next(ln.value for ln in assets if ln.component == "life_insurance")
    mfu = next(ln.value for ln in assets if ln.component == "mutual_funds")
    ins_eq = float(
        rep.filter(
            (pl.col("sub") == "fc_ofc_icpf_ins") & (pl.col("side") == "assets") & (pl.col("fsf_instr") == "f51")
        )["value"].sum()
    )
    ins_f62 = H.fsf_value(rep, "fc_ofc_icpf_ins", "liabilities", "f62", P.UNALLOCATED)
    ins_total = ins_eq - (ins_f62 - life)
    mf_mix = {
        r["cp"]: r["value"]
        for r in rep.filter(
            (pl.col("sub") == "fc_ofc_mf") & (pl.col("side") == "assets") & (pl.col("fsf_instr") == "f51")
        ).iter_rows(named=True)
    }
    mf_issued = H.fsf_value(rep, "fc_ofc_mf", "liabilities", "f52", P.UNALLOCATED)
    recon = F.reconcile(
        rep, insurer_equity=(ins_total, mf_mix), centre_state_k8e=deps.k8e, mf_nonhh_total=mf_issued - mfu
    )
    for n in recon.notes:
        ctx.log(n)
    for c in F.unread_cells(rep):
        what = "replaced by a NAS 5.3 household line" if c["fate"] == "replaced_by_nas_5_3" else "not written"
        ctx.log(
            f"FSF cell not read by the reconciliation ({what}; its FSF - SAM difference is in K9_{c['account']}): "
            f"{c['sub']} {c['side']} {c['fsf_instr']} {c['cp']} {c['value']:,.2f}"
        )
    ctx.log(
        f"insurers' equity (Step C1): FSF {ins_eq:,.2f} - (insurers' F62 {ins_f62:,.2f} - NAS life {life:,.2f}) "
        f"= {ins_total:,.2f}, spread by the MF sector's domestic F51 issuer mix"
    )
    _pair_entries(ctx, out, recon, fsf_pids, deps)

    # own reports: trade credit and other payables (I_OTHR), with K9b replacing the RBI <-> Centre pair
    k9b, k9b_pid = val(P.RBI_K9B, "k9b.change_in_surplus_payable.current")
    own = F.own_reports(rep)
    pair_rbi = H.fsf_value(rep, "fc_rbi", "liabilities", "f89", "gg_cen")
    pair_cen = H.fsf_value(rep, "gg_cen", "assets", "f89", "fc_rbi")
    if pair_rbi == 0.0 or abs(pair_rbi - pair_cen) > 0.01:
        raise SamError(f"FSF RBI -> Centre other payables not found as a matched pair ({pair_rbi}, {pair_cen})")
    own[("K_RBI", "liabilities", "f89")] -= k9b
    own[("K_GCEN", "assets", "f89")] -= k9b
    ctx.log(
        f"K9b {k9b:,.2f} replaces the FSF F89 RBI -> Centre pair {pair_rbi:,.2f}; remainder "
        f"{pair_rbi - k9b:,.2f} stays in fsf_f89 on both sides"
    )
    for ref, side in (("K7", "assets"), ("K8", "liabilities")):
        pid_own = ctx.prov(
            ref=ref,
            status="estimated",
            inputs=[*fsf_pids, k9b_pid],
            source_id=P.SRC_FSF,
            method=f"Gap map {ref} (I_OTHR): each sector's own FSF 2023-24 {side} in trade credit (F81) "
            "and other accounts payable (F89), leaf statements, net of household- and RoW-"
            "counterparty cells (rebuilt from NAS 5.3 and the BoP). Not paired (plan s.2.7 Step "
            "A); FSF 'other'/NEC items are not written and fall into K9. The RBI <-> Centre F89 "
            "pair is replaced by K9b; its remainder (FSF - RBI AR) stays here.",
        )
        for (acct, sd, fi), v in own.items():
            if sd != side:
                continue
            r_, c_ = ("I_OTHR", acct) if side == "assets" else (acct, "I_OTHR")
            out.add(r_, c_, ref, v, pid_own, "estimated", "free", f"fsf_{fi}", conf="low")
    pid_k9b = ctx.prov(
        ref="K9b",
        status="derived",
        inputs=[k9b_pid, *fsf_pids],
        source_id=P.SRC_RBI_AR,
        method="Gap map K9b: RBI surplus timing, RBI Annual Report change in surplus payable to the "
        "Government (k9b.change_in_surplus_payable, vintage 2024-05-30), on both sides: K_RBI <- "
        "I_OTHR (payable) and I_OTHR <- K_GCEN (receivable, as FSF records it), replacing the "
        "FSF F89 RBI -> Centre pair. R6 stays on the Union's cash basis (DECISIONS D0-7, D2-16), "
        "so with cash-basis income the two legs are offset by equal and opposite parts of K9_GCEN "
        "and K9_RBI: a financial reclassification with no income counterpart (XR-27).",
    )
    out.add("K_RBI", "I_OTHR", "K9b", k9b, pid_k9b, "derived", "anchored", "rbi_surplus_payable", tol=P.K9B_TOL)
    out.add("I_OTHR", "K_GCEN", "K9b", k9b, pid_k9b, "derived", "anchored", "rbi_surplus_receivable", tol=P.K9B_TOL)

    # ---------------------------------------------------------------------------------------------
    # K7b RoW counterparts (plan s.2.9)
    # ---------------------------------------------------------------------------------------------
    needs_fc_key = (
        "FC" in set(deps.row_sat["counterpart"].to_list()) if "counterpart" in deps.row_sat.columns else False
    )
    fc_key, fc_key_pids = _fc_row_key(ctx) if needs_fc_key else ({}, [])
    row_posts, row_log = W.postings(deps.row_sat, deps.r14a, fc_key)
    for m in row_log:
        (ctx.warn if m.startswith("WARNING") else ctx.log)(m.removeprefix("WARNING: "))
    pid_row = ctx.prov(
        ref="K7b",
        status="estimated",
        inputs=sorted({*deps.row_pids, *fc_key_pids}),
        source_id=_source_of(ctx, deps.row_pids),
        method="Gap map K7b (RoW): every rest_of_world K8b line with a named domestic counterpart is "
        "posted on that account in the same instrument and value (component row_cp_<line>; the "
        "BoP function is in the component name because bop tags live on K_ROW cells): India's "
        "liabilities as K_s <- I_x, India's assets as I_x <- K_s. FDI reinvested earnings use "
        "rest_of_world's R14a payer split, so income and financing match; a counterpart named "
        "only 'FC' is split by FSF RoW-held FC equity stocks at 2023-03-31; lines without a "
        "counterpart (E&O, NAS reconciliation) are absorbed by K9. All FSF RoW-counterparty cells "
        "are dropped.",
    )
    row_cells: dict[tuple[str, str, str], float] = {}
    for p in row_posts:
        cell = (p.account, p.instrument, p.line) if p.side == "liability" else (p.instrument, p.account, p.line)
        row_cells[cell] = row_cells.get(cell, 0.0) + p.value
    for (r_, c_, line), v in sorted(row_cells.items()):
        out.add(r_, c_, "K7b", v, pid_row, "estimated", "free", f"row_cp_{line}", conf="high")

    # ---------------------------------------------------------------------------------------------
    # K9 residuals (plan s.2.10)
    # ---------------------------------------------------------------------------------------------
    hh_s, hh_s_pid = val(P.NAS19, "s1_9.household_sector.current")
    own_df = pl.DataFrame(
        [{k: e[k] for k in ENTRY_COLS if k != "block"} | {"block": BLOCK} for e in out.entries],
        schema={
            "row": pl.String(),
            "col": pl.String(),
            "ref": pl.String(),
            "component": pl.String(),
            "value": pl.Float64(),
            "prov_id": pl.String(),
            "block": pl.String(),
        },
        orient="row",
    )
    allk = pl.concat([own_df.select(ENTRY_COLS), deps.entries.select(ENTRY_COLS)], how="vertical")
    nets = F.category_nets(rep, totals)
    k9 = R.k9(allk, {a: ctx.accounts.group(a) for a in ctx.accounts.codes}, hh_s, nets)
    dep_pids = sorted(set(deps.entries["prov_id"].to_list()))
    pid_k9 = ctx.prov(
        ref="K9",
        status="estimated",
        inputs=sorted({hh_s_pid, *fsf_pids, *dep_pids}),
        source_id=P.SRC_FSF,
        method="Gap map K9: for each domestic capital account, K9 = row total - column total over every "
        "block's prior entries (saving: K1 here, fincorp K2a, government K3a, NAS 2026 St 1.9 "
        "household saving for K_HH because closure writes K4a later; capital transfers K6/R2k; "
        "D3; GFCF, CIS, valuables; every financial entry). Written on I_OTHR <- K_s as a pair so "
        "balancing can move the net across zero (XR-17): residual_pos = the sum of the positive and "
        "residual_neg = the sum of the negative pair terms (satellite k9_decomposition, items pair:*), "
        "which group the exact decomposition (items term:*: NAS vs FSF published net lending; FSF "
        "reconciliation by instrument; household and RoW replacements; FSF items never read) as "
        "nas_vs_fsf, row_counterparty (all RoW instruments in one term), fsf_unwritten, and per "
        "instrument the household and domestic layers combined (hh_dom:<instrument>; an FSF cell "
        "published without a counterparty, such as insurers' F6, is mostly households' and would "
        "otherwise appear as two opposite terms). The grouping sets the gross size of the pair and so "
        "how cheaply balancing (free, low; cost scales with the prior) can move K9: a weight choice. "
        "A finding, not a target. K9_HH carries the capital transfers to households NAS household "
        "saving cannot see (DECISIONS D2-6).",
    )
    for s, d in k9.items():
        if abs(d["check"]) > 1e-3 or abs(d["check_pair"]) > 1e-3:
            raise SamError(f"K9 decomposition of {s} does not add up (off by {d['check']:.6f})")
        pair = R.residual_pair(d)
        if not pair:
            ctx.log(f"K9 {s}: |{d['k9']:,.4f}| < Rs {P.K9_MIN:g} crore, not written")
        elif len(pair) == 1:
            ctx.warn(f"K9 {s} = {d['k9']:,.2f}: every decomposition term has one sign, single entry (sign fixed)")
        for comp, v in pair.items():
            out.add("I_OTHR", s, "K9", v, pid_k9, "estimated", "free", comp, conf="low")
        ctx.log(
            f"K9 {s}: {d['k9']:,.2f} (pos {d['pos']:,.2f}, neg {d['neg']:,.2f}; real {d['real']:,.2f}, "
            f"FSF net {d['fsf_total']:,.2f})"
        )

    # ---------------------------------------------------------------------------------------------
    # T24 sensitivity of K9 (report only: no entry depends on it)
    # ---------------------------------------------------------------------------------------------
    sens = _k9_sensitivity(
        rep,
        recon,
        k9,
        d3_split,
        insurer=(ins_eq, mf_mix),
        k8e=deps.k8e,
        mf_nonhh_total=mf_issued - mfu,
    )
    pid_sens = ctx.prov(
        ref="K9",
        status="estimated",
        inputs=[pid_k9, pid_d3],
        source_id=P.SRC_FSF,
        method="Plan T24 (report only; no SAM entry depends on it): K9 by domestic capital account under "
        "one-at-a-time changes of this block's stated rules, all else as built. equity_issuer_control: "
        "I_EQTY pairs from the issuers' FSF F51 liability reports (a counterparty named only fc_ofc split by "
        "the OFC sub-sectors' own F51 asset reports), with no insurers' revaluation strip (the strip "
        "corrects the holder side only). insurer_strip_off: insurers' equity = their full FSF F51 assets, "
        "spread by the same MF issuer mix. d3_all_k_nfpu: the D3 remainder (D3 - I2a) all to K_NFPU, the "
        "gap map's alternative. K9_s(variant) = K9_s(base) + change in the net of domestic pairs on s "
        "(issuer + value, holder - value) + change in D3 on s; household and RoW layers, saving, "
        "GCF and capital transfers are unchanged, so the sum over sectors is the same in every variant.",
    )
    out.sats["k9_sensitivity"] = S.k9_sensitivity(sens, pid_sens)

    # ---------------------------------------------------------------------------------------------
    # constraints, checks, satellites
    # ---------------------------------------------------------------------------------------------
    _constraints(ctx, out, val, gf, rep, hh_cells, row_cells, deps, [pid_hh])
    _checks(ctx, out, val, rep, totals, gf, i2a, d3)
    _satellites(ctx, out, val, rep, recon, hh_posts, row_posts, k9, pid_k9, gf, fsf_pids, deps, cpid)
    walras = _instrument_balance(out.entries, deps.entries)
    for inst, gap in walras.items():
        msg = f"prior market {inst}: row - column = {gap:,.2f}"
        if inst == "I_OTHR" or abs(gap) <= 0.01:
            ctx.log(msg)
        else:
            ctx.warn(msg + " (an instrument other than I_OTHR should clear)")
    return BlockResult(entries=out.entries, constraints=out.cons, satellites=out.sats)


# =====================================================================================================
# helpers
# =====================================================================================================


def _source_of(ctx: BlockContext, pids: list[str]) -> str | None:
    """The source of the first input (for records over a DEPENDS block's records: the numbers rest on them)."""
    for p in pids:
        rec = ctx.lookup_prov(p)
        if rec and rec.get("source_id"):
            return str(rec["source_id"])
    return None


def _gfcf(ctx: BlockContext, val, deps: Deps) -> dict:
    """Row and column targets, prior and RAS for I1a; also CIS and corporate GCF by NAS sector."""
    use = ctx.rows(P.SUT_USE, vintage=P.LATEST, item_code="gfcf")
    conc = ctx.concordance(P.PRODUCT_MAP).select(
        ("sut_p" + pl.col("sut_product").str.zfill(3)).alias("product"), "commodity"
    )
    tagged = use.filter(pl.col("product").str.starts_with("sut_p")).join(conc, on="product", how="left")
    if tagged["commodity"].null_count():
        raise SamError("SUT GFCF products missing from the concordance")
    rows: dict[str, float] = {}
    for r in tagged.iter_rows(named=True):
        rows[r["commodity"]] = rows.get(r["commodity"], 0.0) + float(r["value"])
    rows = {c: v for c, v in sorted(rows.items()) if v != 0.0}
    sut_total, sut_pid = val(P.SUT_USE, "use.gfcf.total.current")
    pids = sorted(set(tagged["prov_id"].to_list()) | {sut_pid})
    nas: dict[str, float] = {}
    mix: dict[str, dict[str, float]] = {}
    cis: dict[str, tuple[float, list[str]]] = {}
    gcf: dict[str, float] = {}
    gcf_pids: list[str] = []
    for s, (stem111, stem114) in P.NAS_SECTORS.items():
        v, p = val(P.NAS111, f"s1_11.{stem111}.current")
        nas[s] = v
        pids.append(p)
        mix[s] = {}
        for a in sorted(set(P.ASSET_OF.values())):
            av, ap = val(P.NAS111, f"s1_11.{stem111}.{a}.current")
            mix[s][a] = av
            pids.append(ap)
        g, gp = val(P.NAS114, f"s1_14.{stem114}.gross_capital_formation.current")
        cis[s] = (g - v, [p, gp])
        gcf[s] = g
        gcf_pids.append(gp)
    nas_total, nas_total_pid = val(P.NAS111, "s1_11.gross_fixed_capital_formation.current")
    pids.append(nas_total_pid)
    scale = sut_total / nas_total
    # GG key
    outlay, op = val(P.FA_EXP, "fa9.section.expenditure_heads_capital_account")
    heads = [val(P.FA_EXP, f"fa9.{h}.total") for h in P.UNION_NON_GG_HEADS]
    ab, abp = val(P.FA_GIA, "gia.cash.autonomous_bodies.capital_assets")
    sb, sbp = val(P.FA_GIA, "gia.cash.statutory_bodies_and_development_authorities.capital_assets")
    st_out, sop = val(P.SF_APP, "app4.total_capital_disbursements.i-total_capital_outlay.in.all_states_uts.actuals")
    ulb, ulbp = val(P.FA_GIA, "gia.cash.urban_local_bodies.capital_assets")
    centre = outlay - sum(v for v, _ in heads) + ab + sb
    states = st_out + ulb
    w_cen = centre / (centre + states)
    key_pids = [op, abp, sbp, sop, ulbp, *[p for _, p in heads]]
    pids += key_pids
    # RBI GFCF
    fa1, fp1 = val(
        P.RBI_AC,
        "sch12.x.fixed_assets_net_of_accumulated_depreciation.current",
        period="2024-03-31",
        vintage=P.RBI_AC_VINTAGE,
    )
    fa0, _ = val(
        P.RBI_AC,
        "sch12.x.fixed_assets_net_of_accumulated_depreciation.current",
        period="2023-03-31",
        vintage=P.RBI_AC_VINTAGE,
    )
    dep, dp = val(P.RBI_AC, "is.exp_depreciation.current", vintage=P.RBI_AC_VINTAGE)
    rbi = fa1 - fa0 + dep
    pids += [fp1, dp]
    # FC split by fincorp F4a GOS
    fc_pub = nas["fc_pub"] * scale - rbi
    if fc_pub < 0:
        raise SamError(f"RBI GFCF {rbi:,.2f} exceeds public FC GFCF")
    cols: dict[str, float] = {
        "K_HH|total": nas["hh"] * scale,
        "K_NFPU|total": nas["nfc_pub"] * scale,
        "K_NFPR|total": nas["nfc_pvt"] * scale,
        "K_GCEN|total": nas["gg"] * scale * w_cen,
        "K_GSTA|total": nas["gg"] * scale * (1 - w_cen),
        "K_RBI|public": rbi,
    }
    for part, total in (("public", fc_pub), ("private", nas["fc_pvt"] * scale)):
        key = {a: deps.fc_gos.get((a, part), 0.0) for a in P.K_FC_GFCF}
        if sum(key.values()) <= 0:
            raise SamError(f"fincorp F4a gives no {part} FC GOS to split FC GFCF")
        for a, v in X.largest_remainder_split(total, key).items():
            cols[f"{a}|{part}"] = v
    pids += deps.fc_pids
    sector_of = {"K_HH": "hh", "K_NFPU": "nfc_pub", "K_NFPR": "nfc_pvt", "K_GCEN": "gg", "K_GSTA": "gg"}
    mix_by_col = {
        c: mix[sector_of.get(c.split("|")[0]) or ("fc_pub" if c.endswith("public") else "fc_pvt")] for c in cols
    }
    cols = {c: v for c, v in cols.items() if v != 0.0}
    prior = X.gfcf_prior(rows, {c: mix_by_col[c] for c in cols}, cols)
    cells, it = X.ras(prior, rows, cols)
    by_col: dict[str, float] = {}
    for (_, c), v in cells.items():
        by_col[c] = by_col.get(c, 0.0) + v
    ctx.log(
        f"I1a: {len(rows)} commodities x {len(cols)} columns, RAS {it} iterations; SUT/NAS scale {scale:.12f}; "
        f"Centre share of GG GFCF {w_cen:.6f} (Centre key {centre:,.2f}, States {states:,.2f}); RBI GFCF {rbi:,.2f}"
    )
    return {
        "cells": cells,
        "by_col": by_col,
        "iterations": it,
        "rows": rows,
        "cols": cols,
        "scale": scale,
        "nas": nas,
        "cis": cis,
        "pids": sorted(set(pids)),
        "gcf_pids": sorted(set(gcf_pids)),
        "corp_gcf": {"nfc_pub": gcf["nfc_pub"], "nfc_pvt": gcf["nfc_pvt"], "fc": gcf["fc_pub"] + gcf["fc_pvt"]},
        "key": {
            "centre_outlay": outlay,
            "centre_non_gg_heads": sum(v for v, _ in heads),
            "centre_autonomous": ab,
            "centre_statutory": sb,
            "centre_key": centre,
            "states_outlay": st_out,
            "states_ulb": ulb,
            "states_key": states,
            "centre_share": w_cen,
            "rbi_gfcf": rbi,
        },
        "key_pids": sorted(set(key_pids + [fp1, dp])),
        "sut_total": sut_total,
        "sut_pid": sut_pid,
    }


def _pair_entries(ctx: BlockContext, out: _Out, recon: F.Reconciliation, fsf_pids: list[str], deps: Deps) -> None:
    """Entries from the reconciled pairs, holder side (I_x <- K_h) and issuer side (K_c <- I_x). Positive and
    negative pairs are separate entries (`_pos` / `_neg`) so a net can cross zero. On the control side of an
    instrument, pairs that are published reports (`dom_pos` / `dom_neg`) are anchored; pairs resting on a key
    (`dom_keyed_pos` / `dom_keyed_neg`) are free. The non-control side is free (`dom_pos` / `dom_neg`)."""
    cells: dict[tuple[str, str, str, str], dict] = {}
    for p in recon.pairs:
        sign = "pos" if p.value > 0 else "neg"
        for side, (r_, c_) in (("holder", (p.instrument, p.holder)), ("issuer", (p.issuer, p.instrument))):
            ref = ("K8d" if p.instrument == "I_GSEC" else "K7") if side == "holder" else "K8"
            control = side == P.CONTROL[p.instrument]
            comp = f"dom_keyed_{sign}" if control and p.keyed else f"dom_{sign}"
            d = cells.setdefault((r_, c_, ref, comp), {"value": 0.0, "control": control})
            d["value"] += p.value
    recs: dict[tuple[str, str], str] = {}
    for ref in ("K7", "K8", "K8d"):
        what = {
            "K7": "assets (I_x <- K_s, x not I_GSEC)",
            "K8": "liabilities (K_s <- I_x)",
            "K8d": "G-sec holdings (I_GSEC <- K_s)",
        }[ref]
        recs[(ref, "derived")] = ctx.prov(
            ref=ref,
            status="derived",
            inputs=sorted({*fsf_pids, *deps.k8e_pids}),
            source_id=P.SRC_FSF,
            method=f"Gap map {ref}: reconciled FSF 2023-24 domestic {what}, control side, where every pair in the "
            "cell is a published report: for each instrument the control side's report (issuer for currency, "
            "deposits, small savings, G-secs, MF units; holder for corporate bonds, loans, equity) sets the "
            "pair value X(holder, issuer) on both sides (plan s.2.7). Positive and negative pairs are "
            "separate entries (dom_pos / dom_neg) so a net can cross zero. Centre -> States loans are FSF - "
            "government K8e (FSF includes the GST back-to-back recovery).",
        )
        recs[(ref, "estimated")] = ctx.prov(
            ref=ref,
            status="estimated",
            inputs=sorted({*fsf_pids, *deps.k8e_pids}),
            source_id=P.SRC_FSF,
            method=f"Gap map {ref}: reconciled FSF 2023-24 domestic {what} on the non-control side, or where a pair "
            "rests on a key: a counterparty named only 'fc_ofc' split over NBFC/MF/insurance-PF by the OFC "
            "sub-sectors' own opposite-side reports (absolute-share rule); unnamed or unallocated currency and "
            "deposit holders -> K_NFPR; insurers' equity = FSF F51 - (insurers' F62 - NAS life insurance) "
            "spread by the MF sector's domestic F51 issuer mix (revaluation strip); MF units: FSF MF net sales "
            "less NAS households over the other holders' F52 reports (SFC/SIDC excluded). Household and RoW "
            "counterparty cells are dropped (rebuilt in K7a/K8a/K7b).",
        )
    for (r_, c_, ref, comp), d in sorted(cells.items()):
        if d["value"] == 0.0:
            continue
        if d["control"] and not comp.startswith("dom_keyed"):
            out.add(r_, c_, ref, d["value"], recs[(ref, "derived")], "derived", "anchored", comp, tol=P.CONTROL_TOL)
        else:
            out.add(r_, c_, ref, d["value"], recs[(ref, "estimated")], "estimated", "free", comp, conf="medium")
    dropped: dict[str, float] = {}
    for d in recon.dropped:
        dropped[f"{d['why']}:{d['instrument']}"] = dropped.get(f"{d['why']}:{d['instrument']}", 0.0) + d["value"]
    for k, v in sorted(dropped.items()):
        if abs(v) < 0.005:
            continue
        ctx.log(f"FSF control-side amount not written as a domestic pair: {k} {v:,.2f}")


def _pair_nets(pairs: list[F.Pair]) -> dict[str, float]:
    """Net effect of domestic pairs on each account's K9 (row - column): issuer + value, holder - value."""
    net: dict[str, float] = {}
    for p in pairs:
        net[p.issuer] = net.get(p.issuer, 0.0) + p.value
        net[p.holder] = net.get(p.holder, 0.0) - p.value
    return net


def _k9_sensitivity(
    rep: pl.DataFrame,
    recon: F.Reconciliation,
    k9: dict[str, dict[str, float]],
    d3_split: dict[str, float],
    *,
    insurer: tuple[float, dict[str, float]],
    k8e: float,
    mf_nonhh_total: float,
) -> dict[str, dict[str, float]]:
    """Plan T24: K9 by account under (a) equity issuer control, (b) no insurers' revaluation strip, (c) the D3
    remainder all to K_NFPU; each variant changes one rule, all else as built."""
    base = {s: d["k9"] for s, d in k9.items()}
    base_net = _pair_nets(recon.pairs)
    out: dict[str, dict[str, float]] = {"base": dict(base)}
    variants = {
        "equity_issuer_control": F.reconcile(
            rep,
            insurer_equity=None,
            centre_state_k8e=k8e,
            mf_nonhh_total=mf_nonhh_total,
            control={**P.CONTROL, "I_EQTY": "issuer"},
        ),
        "insurer_strip_off": F.reconcile(
            rep, insurer_equity=insurer, centre_state_k8e=k8e, mf_nonhh_total=mf_nonhh_total
        ),
    }
    for name, rc in variants.items():
        net = _pair_nets(rc.pairs)
        out[name] = {s: base[s] + net.get(s, 0.0) - base_net.get(s, 0.0) for s in base}
    rem = sum(d3_split.values())
    out["d3_all_k_nfpu"] = {s: base[s] - d3_split.get(s, 0.0) + (rem if s == "K_NFPU" else 0.0) for s in base}
    return out


def _fc_row_key(ctx: BlockContext) -> tuple[dict[str, float], list[str]]:
    """Shares of K_BANK/K_NBFC/K_INSP in FSF RoW-held equity of FC issuers, end-March 2023 (plan s.2.9)."""
    df = ctx.rows(
        P.FSF,
        period=P.FC_ROW_KEY_PERIOD,
        vintage=P.LATEST,
        dim_other="measure=outstanding",
        side="liabilities",
        instrument="f51",
        counterparty="row",
        institution=list(P.FC_ROW_KEY_SUBS),
    )
    key: dict[str, float] = {}
    for r in df.iter_rows(named=True):
        a = P.FC_ROW_KEY_SUBS[r["institution"]]
        key[a] = key.get(a, 0.0) + float(r["value"])
    return dict(sorted(key.items())), sorted(set(df["prov_id"].to_list()))


def _instrument_balance(own: list[dict], dep: pl.DataFrame) -> dict[str, float]:
    """Row - column of every instrument account over this block's and its DEPENDS' prior entries."""
    rows = [(e["row"], e["col"], e["value"]) for e in own] + list(dep.select("row", "col", "value").iter_rows())
    out: dict[str, float] = {}
    for r_, c_, v in rows:
        if r_.startswith("I_"):
            out[r_] = out.get(r_, 0.0) + v
        if c_.startswith("I_"):
            out[c_] = out.get(c_, 0.0) - v
    return dict(sorted(out.items()))


def _constraints(
    ctx, out: _Out, val, gf: dict, rep: pl.DataFrame, hh_cells: dict, row_cells: dict, deps: Deps, hh_pids: list
) -> None:
    com = ctx.accounts.in_group("COM")
    fc_accts = ["K_RBI", *P.K_FC_GFCF]
    nas_pids = {}
    for s, (stem111, _) in P.NAS_SECTORS.items():
        nas_pids[s] = val(P.NAS111, f"s1_11.{stem111}.current")
    pid = ctx.prov(
        ref="I1a",
        status="official",
        inputs=sorted({p for _, p in nas_pids.values()}),
        method="Constraint targets for I1a: NAS 2026 St 1.11 GFCF by institutional sector as published "
        "(tolerance Rs 1 crore). The commodity totals are production's I1 constraints (not "
        "re-declared, XR-15).",
    )
    sectors = (
        ("nfc_pub", ["K_NFPU"], ["nfc_pub"], None),
        ("nfc_pvt", ["K_NFPR"], ["nfc_pvt"], None),
        ("gg", ["K_GCEN", "K_GSTA"], ["gg"], None),
        ("hh", ["K_HH"], ["hh"], None),
        ("fc", fc_accts, ["fc_pub", "fc_pvt"], None),
        ("fc_public", fc_accts, ["fc_pub"], ["public"]),
        ("fc_private", fc_accts, ["fc_pvt"], ["private"]),
    )
    for cid, cols, secs, comps in sectors:
        t = sum(nas_pids[s][0] for s in secs)
        out.cons.append(
            constraint(
                f"cf.i1a.gfcf.{cid}",
                "I1a",
                com,
                cols,
                t,
                prov_id=pid,
                tol_abs=1.0,
                refs=["I1a"],
                components=comps,
                description=f"NAS 2026 St 1.11 GFCF of {'+'.join(secs)}",
            )
        )
    # I3a: NAS sector CIS bands and the SUT total
    cis = gf["cis"]
    cis_pid = ctx.prov(
        ref="I3a",
        status="derived",
        inputs=sorted({p for _, ps in cis.values() for p in ps}),
        method="Constraint targets for I3a: NAS 2026 St 1.14 GCF - St 1.11 GFCF by sector (a rounding "
        "band of Rs 0.1 crore around the unscaled NAS value).",
    )
    for cid, cols, secs in (
        ("nfc_pub", ["K_NFPU"], ["nfc_pub"]),
        ("nfc_pvt", ["K_NFPR"], ["nfc_pvt"]),
        ("fc", fc_accts, ["fc_pub", "fc_pvt"]),
        ("gg", ["K_GCEN", "K_GSTA"], ["gg"]),
        ("hh", ["K_HH"], ["hh"]),
    ):
        t = sum(cis[s][0] for s in secs)
        out.cons.append(
            constraint(
                f"cf.i3a.cis.{cid}",
                "I3a",
                ["K_DSTK"],
                cols,
                t,
                prov_id=cis_pid,
                tol_abs=0.1,
                kind="band",
                refs=["I3a"],
                description=f"NAS CIS of {'+'.join(secs)}",
            )
        )
    cii, cii_pid = val(P.SUT_USE, "use.cii.total.current")
    tpid = ctx.prov(
        ref="I3a",
        status="official",
        inputs=[cii_pid],
        method="Constraint target for I3a: SUT 2023-24 CII total (use.cii.total), which production's I3 "
        "entries (K_DSTK's column) add up to.",
    )
    out.cons.append(
        constraint(
            "cf.i3a.cis.total",
            "I3a",
            ["K_DSTK"],
            list(P.K_DOMESTIC),
            cii,
            prov_id=tpid,
            tol_abs=0.01,
            refs=["I3a"],
            description="K_DSTK row = SUT CII total",
        )
    )
    # K4 (identical to closure's closure.k4.hh_saving_total: same selection, series and value)
    k4, k4_pid = val(P.NAS19, "s1_9.household_sector.current")
    kpid = ctx.prov(
        ref="K4",
        status="official",
        inputs=[k4_pid],
        method="Gap map K4: NAS 2026 St 1.9 household gross saving (= St 1.14 = St 5.3), as the target of "
        "K_HH <- H_* (closure writes the K4a entries). Same series and value as closure's constraint.",
    )
    out.cons.append(
        constraint(
            "cf.k4.hh_saving",
            "K4",
            ["K_HH"],
            ctx.accounts.in_group("HH"),
            k4,
            prov_id=kpid,
            tol_abs=0.5,
            refs=["K4a"],
            description="NAS household saving (K4) = sum of K4a",
        )
    )
    # K8 instrument totals of the issuers the plan names (plan s.3)
    ns, ns_pid = val(P.NSSF, "nssf.net_collection")
    nfc_ss = H.fsf_value(rep, "gg_cen", "liabilities", "f22_f29", "nfc_pub")
    fsf_pid = rep.filter(pl.col("sub") == "gg_cen")["prov_id"][0]
    p = ctx.prov(
        ref="K8",
        status="derived",
        inputs=[ns_pid, fsf_pid],
        source_id=P.SRC_BUDGET,
        method="Constraint target: Union small savings and public-account deposits = NSSF net collection "
        "(small savings + PPF, households) + FSF Centre F22/F29 liability to public NFCs.",
    )
    out.cons.append(
        constraint(
            "cf.k8.ssav_centre",
            "K8",
            ["K_GCEN"],
            ["I_SSAV"],
            ns + nfc_ss,
            prov_id=p,
            tol_abs=1.0,
            refs=["K8", "K7b"],
            description="Centre's I_SSAV liabilities",
        )
    )
    cur_all = float(
        rep.filter((pl.col("sub") == "fc_rbi") & (pl.col("side") == "liabilities") & (pl.col("fsf_instr") == "f21"))[
            "value"
        ].sum()
    )
    cur_hh = H.fsf_value(rep, "fc_rbi", "liabilities", "f21", "hh")
    nas_cur = hh_cells[("K_RBI", "I_CURR")]
    cur_nas_pid = val(P.NAS53, "s5_3.currency.current")[1]
    p = ctx.prov(
        ref="K8",
        status="derived",
        inputs=[fsf_pid, cur_nas_pid],
        source_id=P.SRC_FSF,
        method="Constraint target: currency issued = FSF RBI F21 liabilities - FSF household part + NAS 5.3 "
        "household currency (households follow NAS).",
    )
    out.cons.append(
        constraint(
            "cf.k8.curr",
            "K8",
            ["K_RBI"],
            ["I_CURR"],
            cur_all - cur_hh + nas_cur,
            prov_id=p,
            tol_abs=1.0,
            refs=["K8", "K7b"],
            description="RBI currency issued",
        )
    )
    mf = H.fsf_value(rep, "fc_ofc_mf", "liabilities", "f52", P.UNALLOCATED)
    p = ctx.prov(
        ref="K8",
        status="official",
        inputs=[fsf_pid],
        method="Constraint target: MF net sales of units, FSF 2023-24 St 1.3.6 F52 liabilities (band 5%).",
    )
    out.cons.append(
        constraint(
            "cf.k8.mfun",
            "K8",
            ["K_MUTF"],
            ["I_MFUN"],
            mf,
            prov_id=p,
            tol_rel=0.05,
            kind="band",
            refs=["K8", "K7b"],
            description="MF net sales of units",
        )
    )
    gsec_nas_pid = val(P.NAS53, "s5_3.investment_in_government_securities.current")[1]
    f3_liab = rep.filter((pl.col("side") == "liabilities") & (pl.col("fsf_instr") == "f3"))
    f3_pids = {g: set(f3_liab.filter(pl.col("sub") == g)["prov_id"].to_list()) for g in P.GG_CODES}
    row_gsec_pids: dict[str, set[str]] = {}
    if {"instrument", "counterpart", "prov_id"} <= set(deps.row_sat.columns):
        for r in deps.row_sat.filter(pl.col("instrument") == "I_GSEC").iter_rows(named=True):
            row_gsec_pids.setdefault(r["counterpart"], set()).add(r["prov_id"])
    for gov, sub, cp_acct in (("centre", "gg_cen", "K_GCEN"), ("states", "gg_sta", "K_GSTA")):
        allv = float(
            rep.filter((pl.col("sub") == sub) & (pl.col("side") == "liabilities") & (pl.col("fsf_instr") == "f3"))[
                "value"
            ].sum()
        )
        drop = sum(H.fsf_value(rep, sub, "liabilities", "f3", c) for c in ("hh", "row"))
        post = hh_cells.get((cp_acct, "I_GSEC"), 0.0) + sum(
            v for (r_, c_, _), v in row_cells.items() if r_ == cp_acct and c_ == "I_GSEC"
        )
        row_pids = sorted(row_gsec_pids.get(cp_acct, set()))
        p = ctx.prov(
            ref="K8",
            status="estimated",
            # the Centre's target also uses the States' F3 liability to households (the NAS split rule)
            inputs=sorted({*f3_pids[sub], *f3_pids["gg_sta"], gsec_nas_pid, *hh_pids, *row_pids}),
            source_id=P.SRC_FSF,
            method=f"Constraint target: net G-sec issuance by the {gov}: FSF 2023-24 F3 liabilities (Centre St "
            "3.1, States St 3.2), with the household and RoW holder parts replaced by this block's postings: "
            "NAS 2026 St 5.3 household G-secs split by its own rule (the States' FSF F3 liability to "
            "households to K_GSTA, the rest to K_GCEN; K7b hh_cp) and rest_of_world's FPI debt G-sec line "
            "split by issuer (K7b row_cp_fpi_debt_gsec). Estimated because both replacements rest on "
            "estimated splits; the target partly uses this block's own postings, so it is not independent "
            "evidence (capital_financial-24; verification V-CF-3). Band 5%.",
        )
        out.cons.append(
            constraint(
                f"cf.k8.gsec_{gov}",
                "K8",
                [cp_acct],
                ["I_GSEC"],
                allv - drop + post,
                prov_id=p,
                tol_rel=0.05,
                kind="band",
                refs=["K8", "K7b"],
                description=f"net G-sec issuance, {gov}",
            )
        )


def _checks(ctx, out: _Out, val, rep: pl.DataFrame, totals: pl.DataFrame, gf: dict, i2a: float, d3: float) -> None:
    ents = out.entries

    def s(ref: str, **kw) -> float:
        return sum(e["value"] for e in ents if e["ref"] == ref and all(e[k] == v for k, v in kw.items()))

    for sec, (stem111, _) in P.NAS_SECTORS.items():
        t, tp = val(P.NAS111, f"s1_11.{stem111}.current")
        cols = {"nfc_pub": ["K_NFPU"], "nfc_pvt": ["K_NFPR"], "gg": ["K_GCEN", "K_GSTA"], "hh": ["K_HH"]}.get(sec)
        v = (
            sum(e["value"] for e in ents if e["ref"] == "I1a" and e["col"] in cols)
            if cols
            else sum(
                e["value"]
                for e in ents
                if e["ref"] == "I1a" and e["component"] == ("public" if sec == "fc_pub" else "private")
            )
        )
        ctx.check(
            f"i1a.{sec}",
            f"I1a column sum vs NAS 1.11 GFCF, {sec} (SUT/NAS scale)",
            v,
            t,
            target_prov_id=tp,
            tol_abs=CHECK_TOL,
        )
    ctx.check(
        "i1a.total",
        "I1a total vs SUT GFCF total",
        s("I1a"),
        gf["sut_total"],
        target_prov_id=gf["sut_pid"],
        tol_abs=0.01,
    )
    v, p = val(P.SUT_USE, "use.valuables.total.current")
    ctx.check("valuables", "I2 + I2a vs SUT valuables", s("I2") + s("I2a"), v, target_prov_id=p, tol_abs=1e-6)
    v, p = val(P.NAS53, "s5_3.saving_in_form_of_gold_and_silver_ornaments.current")
    ctx.check("i2.nas53", "I2 vs NAS 5.3 gold and silver ornaments", s("I2"), v, target_prov_id=p, tol_abs=1e-6)
    v, p = val(P.SUT_USE, "use.cii.total.current")
    ctx.check("i3a.total", "I3a total vs SUT CII", s("I3a"), v, target_prov_id=p, tol_abs=0.01)
    v, p = val(P.NAS72A, "s7_2a.total.cis.current")
    pub = sum(e["value"] for e in ents if e["ref"] == "I3a" and e["col"] in ("K_NFPU", "K_GCEN"))
    ctx.check("i3a.public", "I3a public (K_NFPU + K_GCEN) vs NAS 7.2A total CIS", pub, v, target_prov_id=p, tol_abs=0.1)
    v, p = val(P.NAS72B, "s7_2b.total.cis.current")
    prv = sum(e["value"] for e in ents if e["ref"] == "I3a" and e["col"] in ("K_NFPR", "K_BANK", "K_NBFC", "K_INSP"))
    ctx.check("i3a.private", "I3a private corporate vs NAS 7.2B total CIS", prv, v, target_prov_id=p, tol_abs=0.1)
    for a, stem in (("K_NFPU", "public"), ("K_NFPR", "private")):
        v, p = val(P.NAS19, f"s1_9.{stem}_non_financial_corporations.current")
        ctx.check(f"k1.{a.lower()}", f"K1 {a} vs NAS 1.9", s("K1", row=a), v, target_prov_id=p, tol_abs=1e-6)
    v, p = val(P.NAS53, "s5_3.gross_financial_saving.current")
    ctx.check("k7a.total", "K7a vs NAS 5.3 gross financial saving", s("K7a"), v, target_prov_id=p, tol_abs=0.01)
    v, p = val(P.NAS53, "s5_3.financial_liabilities.current")
    ctx.check("k8a.total", "K8a vs NAS 5.3 financial liabilities", s("K8a"), v, target_prov_id=p, tol_abs=0.01)
    v, p = val(P.NAS53, "s5_3.net_financial_saving_of_household_sector_1_4.current")
    ctx.check(
        "k7a_k8a.net",
        "K7a - K8a vs NAS 5.3 net financial saving",
        s("K7a") - s("K8a"),
        v,
        target_prov_id=p,
        tol_abs=0.01,
    )
    v, p = val(P.NSSF, "nssf.net_collection")
    ctx.check(
        "k7a.i_ssav", "I_SSAV <- K_HH vs NSSF net collection", s("K7a", row="I_SSAV"), v, target_prov_id=p, tol_abs=0.01
    )
    v, p = val(P.NAS_RESID, "derived.si_errors_omissions.current")
    ctx.check("d3.total", "D3 vs NAS S-I errors and omissions", s("D3"), v, target_prov_id=p, tol_abs=1e-6)
    ctx.check(
        "d3.k_hh",
        "D3 -> K_HH vs I2a (SUT valuables - NAS gold)",
        s("D3", row="K_HH"),
        i2a,
        target_prov_id=val(P.SUT_USE, "use.valuables.total.current")[1],
        tol_abs=1e-6,
    )
    v, p = val(P.RBI_K9B, "k9b.change_in_surplus_payable.current")
    ctx.check(
        "k9b",
        "K9b payable vs RBI AR change in surplus payable",
        s("K9b", row="K_RBI"),
        v,
        target_prov_id=p,
        tol_abs=0.01,
    )
    # Centre -> States loans: FSF = Union AFS net lending (the pair written is FSF - government K8e)
    a1, ap = val(P.AFS, "afs.cfi_cap_disbursements.7601")
    a2, _ = val(P.AFS, "afs.cfi_cap_receipts.state_governments")
    a3, _ = val(P.AFS, "afs.cfi_cap_receipts.union_territories_with_legislature")
    f = H.fsf_value(rep, "gg_cen", "assets", "f4", "gg_sta")
    ctx.check(
        "centre_state_loans.afs",
        "FSF Centre -> States loans vs Union AFS loans to States/UTs net of recoveries",
        f,
        a1 - a2 - a3,
        target_prov_id=ap,
        tol_abs=0.1,
    )
    # FSF extraction reproduces Statement 7: top-level instruments of the leaf statements and the RoW statement
    # (the MF statement's printed total leaves out its F8 of 1,100: rbi_financial_accounts-4, so totals are not used)
    for side in ("assets", "liabilities"):
        tv, tp = val(P.FSF7, f"fsf7.all.{side}.transaction.total.current")
        df = ctx.rows(
            P.FSF,
            vintage=P.LATEST,
            dim_other="measure=transaction",
            counterparty="all",
            side=side,
            institution=[*P.SUB_ACCOUNT, "row"],
            instrument=list(P.FSF_TOP_INSTRUMENTS),
        )
        ctx.check(
            f"fsf.st7.{side}",
            f"FSF leaf statements + RoW, sum of top-level instruments, vs Statement 7 total {side}",
            float(df["value"].sum()),
            tv,
            target_prov_id=tp,
            tol_abs=CHECK_TOL,
        )


def _satellites(ctx, out: _Out, val, rep, recon, hh_posts, row_posts, k9, pid_k9, gf, fsf_pids, deps, cpid) -> None:
    out.sats.update(
        S.all_satellites(ctx, val, rep, recon, hh_posts, row_posts, k9, pid_k9, gf, fsf_pids, deps, cpid, out.entries)
    )
