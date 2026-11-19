"""The government block's entries, constraints, satellites and checks, ref by ref (see the package docstring).

`assemble(ctx, deps)` does all the work; `deps` comes from deps.read_deps(ctx) in a real build and from a
synthetic fixture in tests. Every clean value is read with vintage='latest' (each dataset used carries one
vintage for 2023-24 today; an explicit choice, stated in every method text).
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

import polars as pl

from pipeline.sam.blocks.government.core import (
    GOV,
    HH,
    Q,
    choose_variant,
    gdi_evidence,
    paired_saving,
    pids_of,
    qsum,
    r9b_formula,
    ras,
    shares,
    split,
)
from pipeline.sam.blocks.government.deps import Deps
from pipeline.sam.framework import BlockContext, BlockResult, SamError, Satellite, constraint, entry

VINTAGE = "latest"
# datasets
FA_R, FA_E, GIA = "union_fiscal_fa_receipts", "union_fiscal_fa_expenditure", "union_fiscal_fa_gia"
AFS, EXP, GCCA, RB = "union_fiscal_afs", "union_fiscal_exp_profile", "union_fiscal_gcca", "union_fiscal_rb_receipts"
SF, FC16_SUB, FC16_ACC, KFI = (
    "state_fiscal_rbi_sf_appendices", "state_fiscal_fc16_subsidies", "state_fiscal_fc16_state_accounts",
    "state_fiscal_fc16_kfi",
)  # fmt: skip
NAS = "mospi_nas_2026_"
INVIS, PFRDA = "external_sector_invisibles_annual", "finsector_markets_pfrda_sg"
RBI_T = "rbi_banking_corporate_rbi_surplus_timing"
ULB = "state_fiscal_ulb_cityfinance"

# R1: Union tax head (901 "States' share" line) -> component
R1_HEADS = {"0005": "cgst", "0020": "corporation_tax", "0021": "income_tax", "0032": "wealth_tax", "0037": "customs",
            "0038": "union_excise", "0044": "service_tax", "0045": "other_commodity_taxes"}  # fmt: skip
OWN_OUTPUT = ("C_PADM", "C_EDUC", "C_HLTH", "C_CNST", "C_UTIL")
C2A_CONF = {"C_PADM": "medium", "C_EDUC": "medium", "C_HLTH": "medium", "C_CNST": "low", "C_UTIL": "low"}
R9B_VARIANTS_ALLOWED = ("none", "centre_only", "centre_and_states")  # DECISIONS D2-5 as amended by D2-20
PAIRED_SIGN_WARN = 50_000.0  # Rs crore: plan s.2.8 sign check on a government's saving prior
CHECK_TOL = 0.5


def sf(code: str) -> str:
    """RBI State Finances appendix series id, all States + UTs with legislature, actuals."""
    return f"{code}.in.all_states_uts.actuals"


class Build:
    """Collects entries, constraints and satellites; wraps the context's readers with tracked values."""

    def __init__(self, ctx: BlockContext, deps: Deps) -> None:
        self.ctx, self.deps = ctx, deps
        self.entries: list[dict[str, Any]] = []
        self.cons: list[dict[str, Any]] = []
        self.sats: dict[str, Satellite] = {}
        self.memo: dict[str, Any] = {}  # values shared between parts

    # --- readers ------------------------------------------------------------------------------
    def v(self, ds: str, sid: str) -> Q:
        val, pid = self.ctx.value(ds, sid, vintage=VINTAGE)
        return Q(val, frozenset({pid}))

    def rows(self, ds: str, **kw: Any) -> pl.DataFrame:
        return self.ctx.rows(ds, vintage=VINTAGE, **kw)

    def vsum(self, ds: str, sids: Iterable[str]) -> Q:
        return qsum(self.v(ds, s) for s in sids)

    def frame_sum(self, df: pl.DataFrame) -> Q:
        # math.fsum: exact, so the result does not depend on how a multi-threaded filter chunked the frame (repro)
        return Q(math.fsum(df["value"].to_list()), frozenset(df["prov_id"].to_list()))

    # --- provenance and output ----------------------------------------------------------------
    def prov(self, ref: str, status: str, inputs: Iterable[str], method: str, *, main: str | None = None,
             notes: str | None = None) -> str:  # fmt: skip
        """A record; source_id = the source of `main` (default: the first input), which is among the inputs."""
        ins = sorted(set(inputs))
        src = None
        if ins:
            rec = self.ctx.lookup_prov(main or ins[0])
            src = rec.get("source_id") if rec else None
        return self.ctx.prov(ref=ref, status=status, inputs=ins, method=method, notes=notes, source_id=src)

    def add(self, row: str, col: str, ref: str, comp: str, value: float, pid: str, status: str, role: str,
            *, tol: float | None = None, conf: str | None = None, bop: str | None = None,
            note: str | None = None) -> None:  # fmt: skip
        if value == 0.0:
            self.ctx.log(f"{ref} {row} <- {col} [{comp}] is exactly 0: no entry (structural zero)")
            return
        self.entries.append(entry(row, col, ref, value, prov_id=pid, status=status, role=role, component=comp,
                                  tol_rel=tol, confidence=conf, bop_function=bop, note=note))  # fmt: skip

    def sat(self, name: str, ref: str, rows: list[dict[str, Any]], pid: str, status: str, desc: str,
            dims: list[str]) -> None:  # fmt: skip
        schema = {"series_id": pl.String(), **{d: pl.String() for d in dims}, "value": pl.Float64(),
                  "unit": pl.String(), "status": pl.String(), "prov_id": pl.String()}  # fmt: skip
        data = [{"series_id": r["series_id"], **{d: r.get(d) for d in dims}, "value": float(r["value"]),
                 "unit": r.get("unit", "INR_crore"), "status": status, "prov_id": pid} for r in rows]  # fmt: skip
        self.sats[name] = Satellite(ref, pl.DataFrame(data, schema=schema, orient="row"), desc, decimals=9)

    def s(self, ref: str, *, row: str | None = None, col: str | None = None, comp: str | None = None) -> float:
        return sum(e["value"] for e in self.entries if e["ref"] == ref and (row is None or e["row"] == row)
                   and (col is None or e["col"] == col) and (comp is None or e["component"] == comp))  # fmt: skip


def assemble(ctx: BlockContext, deps: Deps) -> BlockResult:
    b = Build(ctx, deps)
    for n in deps.notes:
        ctx.warn(n)
    _c2a(b)
    _intergovernmental(b)  # R1, R2, R2k, T2b, K8e + the H9 bridge satellite
    _dividends(b)  # R6, R7
    _r7x(b)
    _pensions(b)  # R9 (constraint), R9a, R9d
    _r10(b)
    _r18(b)
    _k6(b)
    _k3a(b)
    _r9b(b)  # last: the D2-5 evidence uses the flows above
    _checks(b)
    return BlockResult(entries=b.entries, constraints=b.cons, satellites=b.sats)


# =====================================================================================================
# C2a: GFCE by commodity, Centre vs States
# =====================================================================================================


def _c2a(b: Build) -> None:
    ctx, d = b.ctx, b.deps
    fa_sec = {  # Centre seed: Union Finance Accounts revenue expenditure by function (cash)
        "C_PADM": [f"fa9.section.{s}" for s in ("organs_of_state", "fiscal_services", "administrative_services",
                                                 "defence_services")],
        "C_EDUC": ["fa9.2202.total", "fa9.2203.total", "fa9.2204.total", "fa9.2205.total"],
        "C_HLTH": ["fa9.2210.total", "fa9.2211.total"],
        "C_CNST": ["fa9.3054.total", "fa9.2059.total"],
        "C_UTIL": [],
    }  # fmt: skip
    sf_heads = {  # States seed: RBI SF Appendix II (all States + UTs), revenue expenditure by function
        "C_PADM": ["app2.total_expenditure.ii.a-organs_of_state", "app2.total_expenditure.ii.b-fiscal_services",
                   "app2.total_expenditure.ii.d-administrative_services",
                   "app2.total_expenditure.ii.f-miscellaneous_general_services"],
        "C_EDUC": ["app2.total_expenditure.i.a.1-education_sports_art_and_culture"],
        "C_HLTH": ["app2.total_expenditure.i.a.2-medical_and_public_health",
                   "app2.total_expenditure.i.a.3-family_welfare"],
        "C_CNST": ["app2.total_expenditure.i.b.7.i-roads_and_bridges", "app2.total_expenditure.ii.d.iv-public_works"],
        "C_UTIL": ["app2.total_expenditure.i.a.4-water_supply_and_sanitation"],
    }  # fmt: skip
    lotteries = b.v(SF, sf("app2.total_expenditure.ii.f.payment_on_account_of_state_lo-payment_on_account_of_"
                           "state_lotteries"))  # fmt: skip
    seed_c = {c: b.vsum(FA_E, ids) for c, ids in fa_sec.items()}
    seed_s = {c: b.vsum(SF, [sf(i) for i in ids]) for c, ids in sf_heads.items()}
    seed_s["C_PADM"] = seed_s["C_PADM"] - lotteries  # lottery prize payouts are not own output
    # public works sit inside the administrative-services aggregates (Union FA section administrative_services =
    # MH 2051-2070 incl. 2059; RBI SF App. II ii.d = items i to v incl. ii.d.iv) and are seeded in CNST: take them
    # out of the PADM seeds so no cash line is seeded twice (verifier V-GOV-2)
    seed_c["C_PADM"] = seed_c["C_PADM"] - b.v(FA_E, "fa9.2059.total")
    seed_s["C_PADM"] = seed_s["C_PADM"] - b.v(SF, sf("app2.total_expenditure.ii.d.iv-public_works"))

    # --- C_CROP: free PDS grain, 100% Centre (FCI is inside G_CEN), fixed at the SUT target ------------
    crop = d.gfce["C_CROP"]
    pid = b.prov(
        "C2a",
        "derived",
        crop.pids,
        "Gap map C2a (1): SUT 2023-24 GFCE on C_CROP (paddy + wheat: production constraint gfce.c_crop, "
        "pure aggregation of io_tables_sut_use) is free PDS grain, a social transfer in kind of the Centre "
        "(the FCI is inside G_CEN; S&M compiles food-subsidy GFCE from CGA food-subsidy data), so it is "
        "written 100% on G_CEN and nothing on G_STA. Assumption A-C2a-1: all SUT GFCE grain is Central.",
    )
    b.add(
        "C_CROP",
        "G_CEN",
        "C2a",
        "food_subsidy",
        crop.v,
        pid,
        "derived",
        "fixed",
        note="free PDS grain (component name frozen, XR-19)",
    )

    # --- own output: 5 x 2 RAS; rows = SUT GFCE, Centre column = F4b key x own-output total ---------------
    own_total = qsum(d.gfce[c] for c in OWN_OUTPUT)
    cfc = d.f4b["G_CEN"] + d.f4b["G_STA"]
    centre_share = d.f4b["G_CEN"].v / cfc.v
    col_c = own_total * centre_share
    seed = {}
    for c in OWN_OUTPUT:
        seed[(c, "G_CEN")] = max(seed_c[c].v, 0.0)
        seed[(c, "G_STA")] = max(seed_s[c].v, 0.0)
    res = ras(seed, {c: d.gfce[c].v for c in OWN_OUTPUT}, {"G_CEN": col_c.v, "G_STA": own_total.v - col_c.v})
    inputs = pids_of(own_total, d.f4b, seed_c, seed_s, lotteries)
    pid = b.prov(
        "C2a",
        "estimated",
        inputs,
        "Gap map C2a (2),(3): own-output GFCE (C_PADM, C_EDUC, C_HLTH, C_CNST, C_UTIL; SUT 2023-24 targets "
        "from production's gfce.* constraints) split Centre vs States by a 5x2 RAS. Row totals = the SUT "
        "commodity GFCE. Column total for G_CEN = the F4b key (factors: G_CEN / (G_CEN + G_STA) GG CFC, the "
        "institutional NAS 4.1 NVA split with central autonomous bodies proxied by Union revenue GIA; "
        "DECISIONS D2-8) x the own-output total. Seed = cash revenue expenditure by function, latest "
        "vintage: Centre = Union Finance Accounts 2023-24 (fa9.section organs of state + fiscal + "
        "administrative + defence services less MH 2059 public works -> PADM; MH 2202-2205 -> EDUC; "
        "2210+2211 -> HLTH; 3054+2059 -> CNST; UTIL 0, because MH 2215 is Jal Jeevan transfers and capital, "
        "not own output); States = RBI State Finances App. II all States + UTs (ii.a+ii.b+ii.d+ii.f less "
        "State lotteries and less ii.d.iv public works -> PADM; i.a.1 -> EDUC; i.a.2+i.a.3 -> HLTH; i.b.7.i "
        "roads + ii.d.iv public works -> CNST; i.a.4 -> UTIL). Public works are inside the administrative-"
        "services aggregates (FA section = MH 2051-2070; App. II ii.d = items i to v), so they are taken out of "
        "the PADM seeds and seeded once, in CNST (verifier V-GOV-2). "
        "Assumption A-C2a-2: non-CE costs (IC + CFC - sales) are proportional to CE across levels "
        "(probably understates the Centre: defence IC is heavy).",
    )
    rows_sat: list[dict[str, Any]] = []
    for (c, g), val in sorted(res.items()):
        b.add(c, g, "C2a", "total", val, pid, "estimated", "free", conf=C2A_CONF[c])
    b.cons.append(
        constraint(
            "gov.c2a.centre_own_output",
            "C2a",
            list(OWN_OUTPUT),
            ["G_CEN"],
            col_c.v,
            prov_id=pid,
            kind="band",
            tol_rel=0.10,
            refs=["C2a"],
            description="Centre own-output GFCE = F4b institutional key x SUT own-output GFCE, +-10% (the key "
            "assumes non-CE costs proportional to CE; stops balancing from moving lakhs between levels)",
        )
    )
    nas_gfce = b.v(NAS + "s1_14", "s1_14.gg.final_consumption_expenditure.current")
    pid_t = b.prov(
        "C2",
        "official",
        nas_gfce.pids,
        "NAS 2026 Statement 1.14 general government final consumption expenditure 2023-24, current "
        "prices, latest vintage, as published (the total the C2a split must reproduce).",
    )
    b.cons.append(constraint(
        "gov.c2.total", "C2", ctx.accounts.in_group("COM"), GOV, nas_gfce.v, prov_id=pid_t, kind="band", tol_abs=1.0,
        refs=["C2a"], description="GFCE (all C2a entries) = NAS 1.14 GG FCE within Rs 1 crore (the SUT total "
                                  "differs by Rs 0.23 crore)"))  # fmt: skip
    for c in OWN_OUTPUT:
        for g, sd in (("G_CEN", seed_c), ("G_STA", seed_s)):
            rows_sat.append({"series_id": f"seed.{c.lower()}.{g.lower()}", "item": "seed_cash_revenue_expenditure",
                             "commodity": c, "government": g, "value": sd[c].v})  # fmt: skip
            rows_sat.append({"series_id": f"ras.{c.lower()}.{g.lower()}", "item": "ras_result", "commodity": c,
                             "government": g, "value": res[(c, g)]})  # fmt: skip
        rows_sat.append({"series_id": f"target.{c.lower()}", "item": "sut_gfce_target", "commodity": c,
                         "government": None, "value": d.gfce[c].v})  # fmt: skip
    rows_sat += [
        {"series_id": "centre_share_f4b", "item": "f4b_centre_share", "commodity": None, "government": "G_CEN",
         "value": centre_share, "unit": "ratio"},
        {"series_id": "centre_column_target", "item": "centre_own_output_target", "commodity": None,
         "government": "G_CEN", "value": col_c.v},
        {"series_id": "food_subsidy.c_crop", "item": "free_pds_grain", "commodity": "C_CROP", "government": "G_CEN",
         "value": crop.v},
    ]  # fmt: skip
    b.sat(
        "gov_c2a_keys",
        "C2a",
        rows_sat,
        pid,
        "estimated",
        "C2a Centre/State split: cash seeds, SUT targets, F4b Centre share and the RAS result",
        ["item", "commodity", "government"],
    )
    b.memo["c2a_centre_share"] = centre_share


# =====================================================================================================
# R1, R2, R2k, T2b, K8e: Centre -> States
# =====================================================================================================


def _net_releases(b: Build, mh: str, sub: str | None = None) -> tuple[Q, Q, Q, Q]:
    """(total, 797 transfers to reserve funds, 'amount met from' deducts, net releases) of a Union grant head."""
    df = b.rows(FA_E).filter(pl.col("series_id").str.starts_with(f"fa9.{mh}." + (f"{sub}." if sub else "")))
    total = b.v(FA_E, f"fa9.{mh}.{sub}.total" if sub else f"fa9.{mh}.total")
    leaf = df.filter(~pl.col("series_id").str.ends_with(".total"))
    t797 = b.frame_sum(leaf.filter(pl.col("series_id").str.ends_with(".797")))
    met = b.frame_sum(leaf.filter(pl.col("item_label").str.to_lowercase().str.contains("met from")))
    return total, t797, met, total - t797 - met


def _intergovernmental(b: Build) -> None:
    ctx = b.ctx
    # --- R1 devolution ---------------------------------------------------------------------------------
    rec = b.rows(FA_R).filter(pl.col("series_id").str.contains(r"^fa8\.00\d\d\.\d\d\.901$"))
    r1_items = []
    for r in rec.sort("series_id").iter_rows(named=True):
        mh = r["series_id"].split(".")[1]
        if mh not in R1_HEADS:
            raise SamError(f"R1: unexpected 901 (States' share) line {r['series_id']}")
        r1_items.append((R1_HEADS[mh], -float(r["value"]), r["prov_id"], r["series_id"]))
    pid = b.prov(
        "R1",
        "official",
        [p for *_, p, _ in r1_items],
        "Gap map R1: tax devolution = the Union Finance Accounts 2023-24 (latest vintage, audited) minor "
        "head 901 'States' share' line of each Union tax head (MH 0005 CGST, 0020 corporation tax, 0021 "
        "income tax, 0037 customs, 0038 Union excise, 0044 service tax, 0045 other taxes on commodities; "
        "0032 wealth tax is 0), as published with the sign reversed (901 is a deduction from Union "
        "receipts). taxes routes Union taxes gross of devolution to G_CEN, so R1 is the only route.",
    )
    for comp, val, _, _ in r1_items:
        b.add("G_STA", "G_CEN", "R1", comp, val, pid, "official", "fixed")
    r1 = Q(sum(v for _, v, _, _ in r1_items), frozenset(p for *_, p, _ in r1_items))
    b.cons.append(
        constraint(
            "gov.r1.devolution",
            "R1",
            ["G_STA"],
            ["G_CEN"],
            r1.v,
            prov_id=pid,
            tol_abs=CHECK_TOL,
            refs=["R1"],
            description="Tax devolution = Union FA minor heads 901 (fixed entries)",
        )
    )

    # --- H9 bridge: Union grant heads to net releases ---------------------------------------------------
    t3601, f3601, m3601, n3601 = _net_releases(b, "3601")
    t3602, f3602, m3602, n3602 = _net_releases(b, "3602")
    t06, f06, m06, n06 = _net_releases(b, "3601", "06")
    sf_grants = b.v(SF, sf("app1.total_revenue.ii.d-grants_from_the_centre"))
    fc = b.v(SF, sf("app1.total_revenue.ii.d.5-finance_commission_grants"))
    igas_state = b.vsum(GIA, ["gia.cash.state_governments.total", "gia.in_kind.state_governments.total"])
    fc_local = b.vsum(FA_E, ["fa9.3601.07.102", "fa9.3601.07.103", "fa9.3601.07.106"])
    st18_css = b.v(EXP, "stat18.transfers_to_states_other_than_i_ii.under_centrally_sponsored_schemes_revenue")
    others_tot = b.v(GIA, "gia.cash.others.total")
    others_cap = b.v(GIA, "gia.cash.others.capital_assets")

    # --- T2b: uses of the GST compensation cess ---------------------------------------------------------
    t2b1 = b.vsum(FA_E, ["fa9.3601.08.112", "fa9.3602.08.106"])
    fund_out = b.v(AFS, "afs.pa_disbursements.xi_goods_and_service_tax_compensation_fund")
    fund_in = b.v(AFS, "afs.pa_receipts.xi_goods_and_service_tax_compensation_fund")
    met_gst = b.vsum(FA_E, ["fa9.3601.08.904", "fa9.3602.08.904"])  # negative deducts
    t2b2 = fund_out + met_gst
    pid1 = b.prov(
        "T2b",
        "official",
        t2b1.pids,
        "Gap map T2b (i): GST compensation grants released = Union FA 2023-24 fa9.3601.08.112 (States) + "
        "fa9.3602.08.106 (UTs with legislature), latest vintage, as published (= FC16 KFI A.1.4.a for the "
        "28 States; RBI SF's 45,464.24 is 518.72 higher and that difference stays in R2 css_and_other).",
    )
    pid2 = b.prov(
        "T2b",
        "derived",
        pids_of(fund_out, met_gst),
        "Gap map T2b (ii): compensation cess applied to recover the 2020-22 GST back-to-back loans = AFS "
        "2023-24 Public Account disbursements of the GST Compensation Fund (xi) less the grants it financed "
        "(the 'amount met from GST Compensation Fund' deducts fa9.3601.08.904 + fa9.3602.08.904), latest "
        "vintage. Recorded as a current transfer Centre -> States (DECISIONS D2-13, Checkpoint B flag), "
        "financing the States' negative loan incurrence K8e.",
    )
    b.add("G_STA", "G_CEN", "T2b", "compensation_grants", t2b1.v, pid1, "official", "fixed")
    b.add("G_STA", "G_CEN", "T2b", "cess_loan_recovery", t2b2.v, pid2, "derived", "fixed")
    pid_t2b = b.prov(
        "T2b",
        "derived",
        pids_of(t2b1, t2b2),
        "Gap map T2b: total uses of the GST compensation cess in 2023-24 = compensation grants (Union FA "
        "3601.08.112 + 3602.08.106) + cess applied to back-to-back loan recovery (AFS fund outgo less the "
        "grants it financed); the documenting target of the two fixed T2b entries.",
    )
    b.cons.append(constraint("gov.t2b.cess_uses", "T2b", ["G_STA"], ["G_CEN"], (t2b1 + t2b2).v, prov_id=pid_t2b,
                             tol_abs=CHECK_TOL, refs=["T2b"],
                             description="Uses of the GST compensation cess (two fixed T2b entries)"))  # fmt: skip

    # --- K8e: the States' repayment of the back-to-back loans, financed by T2b(ii) ----------------------
    pid = b.prov(
        "K8e",
        "derived",
        t2b2.pids,
        "Gap map K8e: the 2023-24 recovery of the GST back-to-back loans (= T2b(ii), AFS GST Compensation "
        "Fund outgo less the grants it financed) is a negative incurrence of I_LOAN liabilities by K_GSTA and "
        "an equal negative acquisition of I_LOAN assets by K_GCEN. Conditional on capital_financial writing "
        "the FSF Centre->State loan flow net of it (its plan s.2.7: FSF 41,791.65 + 78,104 = 1,19,895.65).",
    )
    b.add("K_GSTA", "I_LOAN", "K8e", "gst_b2b_repayment", -t2b2.v, pid, "derived", "fixed")
    b.add("I_LOAN", "K_GCEN", "K8e", "gst_b2b_repayment", -t2b2.v, pid, "derived", "fixed")

    # --- R2k: capital grants to State and UT governments (IGAS-2) ------------------------------------
    r2k = b.vsum(GIA, ["gia.cash.state_governments.capital_assets", "gia.cash.ut_governments.capital_assets"])
    pid_k = b.prov(
        "R2k",
        "derived",
        r2k.pids,
        "Gap map R2k: Union grants-in-aid 'for creation of capital assets' to State and UT (with "
        "legislature) governments, Finance Accounts 2023-24 IGAS-2 grantee statement (cash), latest "
        "vintage. States book every central grant as revenue, so this part is taken out of their current "
        "receipts (R2). Union capital grants to ULBs (1,479.24) are not added: under D2-8 they are inside "
        "the CSS-outside-treasury bridge (component css_outside_treasury).",
    )
    b.add("K_GSTA", "K_GCEN", "R2k", "igas2_capital", r2k.v, pid_k, "derived", "free", conf="medium")

    # --- R2: current grants, treasury receipts (RBI SF) less T2b(i) and R2k ----------------------------
    pid_fc = b.prov(
        "R2",
        "official",
        fc.pids,
        "Gap map R2: Finance Commission grants received by States + UTs with legislature, RBI State "
        "Finances 2023-24 Appendix I ii.d.5 (accounts), latest vintage, as published.",
    )
    b.add("G_STA", "G_CEN", "R2", "fc_grants", fc.v, pid_fc, "official", "fixed")
    css = sf_grants - fc - t2b1 - r2k
    pid_css = b.prov(
        "R2",
        "derived",
        pids_of(sf_grants, fc, t2b1, r2k),
        "Gap map R2: other current grants received in State treasuries = RBI SF 2023-24 Appendix I ii.d "
        "grants from the Centre (all States + UTs with legislature) - FC grants (ii.d.5) - GST "
        "compensation grants T2b(i) (Union FA) - capital grants R2k (IGAS-2). Anchored +-10%: it absorbs "
        "the R2k estimate and the RBI SF vs Union 518.72 difference on GST compensation.",
    )
    b.add("G_STA", "G_CEN", "R2", "css_and_other", css.v, pid_css, "derived", "anchored", tol=0.10)
    pid_rc = b.prov(
        "R2",
        "official",
        sf_grants.pids,
        "RBI State Finances 2023-24 Appendix I ii.d grants from the Centre, all States + UTs with "
        "legislature (the treasury receipts of central grants; H9 control, plan C1), as published.",
    )
    b.cons.append(
        constraint(
            "gov.grants.state_receipts",
            "R2",
            ["G_STA", "K_GSTA"],
            ["G_CEN", "K_GCEN"],
            sf_grants.v,
            prov_id=pid_rc,
            kind="band",
            tol_rel=0.005,
            refs=["R2", "T2b", "R2k"],
            components=["fc_grants", "css_and_other", "compensation_grants", "igas2_capital"],
            description="Central grants received in State treasuries (R2 treasury parts + T2b(i) + R2k IGAS-2) = "
            "RBI SF grants from the Centre +-0.5% (XR-20: cess_loan_recovery and css_outside_treasury excluded)",
        )
    )

    # --- D2-8 institutional view: CSS released outside State treasuries ------------------------------
    outside = st18_css - n06
    cap_share = others_cap.v / others_tot.v
    out_cap = outside * cap_share
    out_cur = outside - out_cap
    ins = pids_of(st18_css, t06, f06, m06, others_cap, others_tot)
    pid_o = b.prov(
        "R2",
        "estimated",
        ins,
        "DECISIONS D2-8 (institutional Centre/State boundary, CROSS_REVIEW XR-7): CSS money the Union "
        "releases "
        "to State implementing agencies outside State treasuries is a Centre -> State transfer (those "
        "societies and local bodies are inside G_STA in NAS 4.1). Size = Expenditure Profile 2024-25 "
        "Statement 18 III 'under Centrally Sponsored Schemes (Revenue)' 2023-24 actuals (States) - MH "
        "3601.06 net releases through treasuries (FA total less minor head 797 transfers to reserve funds "
        "and 'amount met from' fund deducts). Current part = total x (1 - IGAS-2 'Others' capital-asset "
        "share); assumption A-R2-1: the outside-treasury agencies are the IGAS-2 'Others' grantees (their "
        "total 1,73,699 is the closest match in size), so their capital share applies. Union direct "
        "grants to ULBs are not added separately (they reach ULBs through the same scheme releases; "
        "adding the ULB dump 54,108.73 would double count).",
        main=st18_css.pids[0],
    )
    b.add("G_STA", "G_CEN", "R2", "css_outside_treasury", out_cur.v, pid_o, "estimated", "free", conf="low")
    pid_ok = b.prov(
        "R2k",
        "estimated",
        ins,
        "DECISIONS D2-8 / XR-7: capital part of the CSS released outside State treasuries = (Statement 18 "
        "III CSS revenue - MH 3601.06 net releases) x IGAS-2 'Others' capital-asset share (assumption "
        "A-R2-1, see the R2 css_outside_treasury record).",
        main=st18_css.pids[0],
    )
    b.add("K_GSTA", "K_GCEN", "R2k", "css_outside_treasury", out_cap.v, pid_ok, "estimated", "free", conf="low")
    # audit BS-7 (government-34): the outside-treasury CSS money is a published-derived total (St 18 III - MH
    # 3601.06 net releases; IGAS-2 'Others' grantees 1,73,699 within 3.3%), not a residual: balancing cut the
    # transfer 40% because no block writes the agencies' outlays. The band holds the transfer (current + capital)
    pid_ot = b.prov(
        "R2",
        "derived",
        ins,
        "Outside-treasury CSS transfer total (constraint target; D2-8): Expenditure Profile 2024-25 Statement 18 "
        "III CSS (revenue) 2023-24 actuals - MH 3601.06 net releases through State treasuries (Union FA 2023-24, "
        "latest vintage). Band +-10%: it covers the 3.3% gap to IGAS-2 'Others' grantees (1,73,699.15) and the "
        "release timing; audit BS-7 (2026-10-01).",
        main=st18_css.pids[0],
    )
    b.cons.append(constraint(
        "gov.r2.css_outside_treasury", "R2", ["G_STA", "K_GSTA"], ["G_CEN", "K_GCEN"], outside.v, prov_id=pid_ot,
        kind="band", tol_rel=0.10, refs=["R2", "R2k"], components=["css_outside_treasury"],
        description="CSS released outside State treasuries (R2 + R2k css_outside_treasury) near St 18 III - MH "
        "3601.06 (band 10%)",
    ))  # fmt: skip

    # --- H9 bridge satellite -------------------------------------------------------------------------
    pid_b = b.prov(
        "R2",
        "derived",
        pids_of(
            t3601,
            f3601,
            m3601,
            t3602,
            f3602,
            m3602,
            sf_grants,
            igas_state,
            fc_local,
            st18_css,
            t06,
            f06,
            m06,
            others_tot,
            others_cap,
        ),
        "H9 grants bridge (plan s.2.2): Union MH 3601 / 3602 total = net releases + minor head 797 "
        "transfers "
        "to reserve funds + 'amount met from' fund deducts (Union FA 2023-24, latest vintage); net releases "
        "vs RBI SF grants received; IGAS-2 'State Government' (cash + kind) + FC local-body and health "
        "grants (3601.07.102/.103/.106) vs MH 3601 net releases; Statement 18 CSS vs MH 3601.06 net "
        "releases (the outside-treasury CSS).",
        main=t3601.pids[0],
    )
    bridge = [
        ("mh3601.total", t3601), ("mh3601.transfers_797", f3601), ("mh3601.met_from_funds", m3601),
        ("mh3601.net_releases", n3601), ("mh3602.total", t3602), ("mh3602.transfers_797", f3602),
        ("mh3602.met_from_funds", m3602), ("mh3602.net_releases", n3602),
        ("union_net_releases", n3601 + n3602), ("rbi_sf_grants_received", sf_grants),
        ("gap_union_minus_states", n3601 + n3602 - sf_grants), ("igas2_state_government", igas_state),
        ("fc_local_body_health_grants", fc_local), ("gap_igas2_plus_fc_minus_mh3601", igas_state + fc_local - n3601),
        ("stat18_css_revenue", st18_css), ("mh3601_06.net_releases", n06), ("css_outside_treasury", outside),
        ("igas2_others_total", others_tot), ("igas2_others_capital_share", Q(cap_share)),
        ("gst_fund.receipts", fund_in), ("gst_fund.disbursements", fund_out), ("gst_fund.accumulation",
                                                                              fund_in - fund_out),
        ("t2b_compensation_grants", t2b1), ("t2b_cess_loan_recovery", t2b2),
    ]  # fmt: skip
    b.sat(
        "gov_grants_bridge",
        "R2",
        [
            {"series_id": k, "item": k, "value": q.v, "unit": "ratio" if "share" in k else "INR_crore"}
            for k, q in bridge
        ],
        pid_b,
        "derived",
        "H9: Union grant heads to net releases vs State receipts; outside-treasury CSS; GST fund",
        ["item"],
    )
    b.memo.update(r1=r1, sf_grants=sf_grants, n3601=n3601, n3602=n3602, igas_state=igas_state, fc_local=fc_local,
                  t2b1=t2b1, t2b2=t2b2, fund_in=fund_in, r2k=r2k, outside=outside, others_tot=others_tot,
                  pid_rc=pid_rc)  # fmt: skip
    ctx.log(
        f"H9: Union net releases {(n3601 + n3602).v:,.2f} vs RBI SF {sf_grants.v:,.2f}; outside-treasury CSS "
        f"{outside.v:,.2f} (capital share {cap_share:.4f})"
    )


# =====================================================================================================
# R6, R7: RBI surplus and dividends
# =====================================================================================================


def _dividends(b: Build) -> None:
    r6 = b.v(FA_R, "fa8.0050.00.106")
    pid = b.prov(
        "R6",
        "official",
        r6.pids,
        "Gap map R6: RBI surplus received by the Centre in FY 2023-24, cash basis (DECISIONS D0-7, D2-16) = "
        "Union FA 2023-24 fa8.0050.00.106, latest vintage, as published (RBI's 2022-23 surplus). The SNA "
        "7.131 super-dividend test is reported, not applied (plan C8).",
    )
    b.add("G_CEN", "E_RBI", "R6", "cash_basis", r6.v, pid, "official", "fixed")
    items = {  # (row, col, component): Union FA minor heads of MH 0050; status: official where the minor head
        # names the payer exactly, derived where a mixed head is put on one account by an assumption (V-GOV-6)
        ("G_CEN", "E_NFPU", "public_undertakings"): (["fa8.0050.00.101", "fa8.0050.00.200"], "derived"),
        ("G_CEN", "E_BANK", "banks"): (["fa8.0050.00.108", "fa8.0050.00.109"], "official"),
        ("G_CEN", "E_INSP", "lic"): (["fa8.0050.00.107"], "official"),
    }
    total = b.v(FA_R, "fa8.0050.total")
    got = Q(0.0)
    for (row, col, comp), (ids, status) in items.items():
        q = b.vsum(FA_R, ids)
        got = got + q
        if status == "official":
            how = (f"as published; the minor heads name the payer ({col}): 108 nationalised banks + 109 IDBI -> "
                   "E_BANK, 107 LIC -> E_INSP")  # fmt: skip
        else:
            how = ("the published total, put wholly on E_NFPU by assumption A-R7-1: 101 'public undertakings' "
                   "also holds the dividends of financial PSUs (public NBFCs such as PFC / REC / IRFC, public "
                   "insurers other than LIC), which clean data cannot separate, and 200 'other investments' has no "
                   "payer detail; so the payer split is derived, not official (verifier V-GOV-6). Fixed: the "
                   "Union total is exact and held by gov.r7.union with the other two entries fixed, and no "
                   "alternative payer entry can be seeded from clean data")  # fmt: skip
        pid = b.prov(
            "R7",
            status,
            q.pids,
            f"Gap map R7: dividends and profits received by the Centre from {comp.replace('_', ' ')} = Union "
            f"FA 2023-24 {' + '.join(ids)}, latest vintage; {how}. The RBI surplus (106) is R6, not R7.",
        )
        b.add(row, col, "R7", comp, q.v, pid, status, "fixed")
    other = total - r6 - got
    if abs(other.v) > 0.01:
        raise SamError(f"R7: MH 0050 has lines outside 101/106/107/108/109/200 worth {other.v:,.2f}")
    sta = b.v(SF, sf("app1.total_revenue.ii.c.2-dividends_and_profits"))
    pid = b.prov(
        "R7",
        "derived",
        sta.pids,
        "Gap map R7: dividends and profits received by States + UTs with legislature, RBI SF 2023-24 "
        "Appendix I ii.c.2, latest vintage; the published total, put wholly on E_NFPU (State enterprises) by "
        "assumption A-R7-2: App. I has no payer detail, and State financial corporations or co-operative banks "
        "may pay part of it; so the payer split is derived, not official (verifier V-GOV-6, same rule as the "
        "Union's 101). Fixed at the published total (no alternative payer can be seeded from clean data).",
    )
    b.add("G_STA", "E_NFPU", "R7", "state_enterprises", sta.v, pid, "derived", "fixed")
    union_r7 = total - r6
    pid_u = b.prov(
        "R7",
        "derived",
        union_r7.pids,
        "Union dividends and profits excluding the RBI surplus = Union FA fa8.0050.total - fa8.0050.00.106.",
    )
    b.cons.append(constraint("gov.r7.union", "R7", ["G_CEN"], ["E_NFPU", "E_BANK", "E_INSP"], union_r7.v,
                             prov_id=pid_u, tol_abs=CHECK_TOL, refs=["R7"],
                             description="Union dividends excluding the RBI surplus (fixed entries)"))  # fmt: skip
    b.memo.update(r6=r6, r7_total=total, r7_states=sta)


# =====================================================================================================
# R7x: property income other than dividends (interest from non-GG units, resource rents)
# =====================================================================================================


def _r7x(b: Build) -> None:
    d = b.deps

    # payer keys (NAS 2026 St 7.1A public / 7.1B private corporations / 7.1C households, OS + CFC, latest)
    def gos(stmt: str, ind: str, os_item: str = "os") -> Q:
        return b.vsum(NAS + stmt, [f"{stmt}.{ind}.{os_item}.current", f"{stmt}.{ind}.cfc.current"])

    mine = {"E_NFPU": gos("s7_1a", "mining"), "E_NFPR": gos("s7_1b", "mining"),
            "HH": gos("s7_1c", "mining", "os_mi")}  # fmt: skip
    comm = {"E_NFPU": gos("s7_1a", "communication"), "E_NFPR": gos("s7_1b", "communication")}
    wage_key = shares({g: d.public_wage_key[g].v for g in HH}, "public_sector_wage_key")
    mi_key = shares({g: d.mi_nonfarm[g].v for g in HH}, "F2 nonfarm")

    def payers(total: float, key: dict[str, Q], with_hh: bool) -> dict[str, float]:
        k = shares({p: q.v for p, q in key.items() if with_hh or p != "HH"}, "R7x payer")
        out = {p: total * s for p, s in k.items() if p != "HH"}
        if "HH" in k:
            out.update({g: total * k["HH"] * s for g, s in mi_key.items()})
        return out

    def lines(ids: list[str]) -> Q:
        return b.vsum(FA_R, ids)

    items: list[tuple[str, str, Q, dict[str, float], str, str]] = []  # (gov, comp, total, payer split, how, conf)
    # Union interest receipts from non-GG units (MH 0049.03)
    q = lines(["fa8.0049.03.190", "fa8.0049.03.103"])
    items.append(
        (
            "G_CEN",
            "interest_psu",
            q,
            {"E_NFPU": q.v},
            "MH 0049.03.190 public sector and other undertakings + .103 departmental commercial undertakings -> E_NFPU",
            "low",
        )
    )
    q = lines(["fa8.0049.03.109", "fa8.0049.03.195"])
    items.append(
        (
            "G_CEN",
            "interest_other_parties",
            q,
            {"E_NFPR": q.v},
            "MH 0049.03.109 other parties + .195 co-operative societies -> E_NFPR (assumption A-R7x-2)",
            "low",
        )
    )
    q = lines(["fa8.0049.03.118"])
    items.append(
        (
            "G_CEN",
            "interest_govt_servants",
            q,
            split(q.v, wage_key),
            "MH 0049.03.118 interest on loans to government servants -> households by the public-sector wage "
            "key (factors)",
            "low",
        )
    )
    # Union resource rents
    q = lines(["fa8.0802.00.102", "fa8.0802.00.103", "fa8.0802.00.106", "fa8.0802.00.107", "fa8.0802.00.109"])
    items.append(
        (
            "G_CEN",
            "petroleum_rent",
            q,
            payers(q.v, mine, False),
            "MH 0802 profit petroleum + royalties + licence fee and mining-lease rent + production-level "
            "payment + revenue share (offshore oil and gas) -> public/private corporations by NAS 7.1A/7.1B "
            "mining OS + CFC",
            "low",
        )
    )
    q = lines(["fa8.1275.00.104", "fa8.1275.00.105"])
    items.append(
        (
            "G_CEN",
            "telecom_licence",
            q,
            payers(q.v, comm, False),
            "MH 1275 telecom licence fee + universal access levy (annual charges on adjusted gross revenue, "
            "treated as rent D45; assumption A-R7x-3, NAD question) -> public/private corporations by NAS "
            "7.1A/7.1B communication OS + CFC",
            "low",
        )
    )
    # States: interest receipts less the interest on their cash-balance investment in the Centre's 14-day
    # intermediate treasury bills (intra-GG: fincorp books it as R3 itb_14d G_STA <- G_CEN; verifier V-GOV-1)
    sta_int = b.v(SF, sf("app1.total_revenue.ii.c.1-interest_receipts"))
    itb14 = b.v(FA_E, "fa9.2049.01.116")
    q = sta_int - itb14
    items.append(
        (
            "G_STA",
            "interest_states",
            q,
            {"E_NFPU": q.v},
            "RBI SF App. I ii.c.1 interest receipts (all States + UTs) less the interest the States earn on "
            "their cash-balance investment in the Centre's 14-day intermediate treasury bills (= Union FA "
            "MH 2049.01.116 'interest on 14 days treasury bills', paid only to State governments; intra-GG, "
            "booked by fincorp as R3 itb_14d, so it is taken out here: verifier V-GOV-1) -> E_NFPU (assumption "
            "A-R7x-4: loans to State PSUs dominate)",
            "low",
        )
    )
    roy = b.rows(FC16_ACC).filter(pl.col("series_id").str.starts_with("fa.revenue_receipts.mh0853.in-"))
    q = b.frame_sum(roy)
    items.append(
        (
            "G_STA",
            "mining_royalties",
            q,
            payers(q.v, mine, True),
            "FC16 State Finance Accounts MH 0853 non-ferrous mining and metallurgical industries (mining "
            "royalties, dead rent, concession fees; sum over the States reported) -> public corporations, "
            "private corporations and household enterprises by NAS 7.1A/7.1B/7.1C mining OS(+MI) + CFC; the "
            "household part to groups by factors' F2 non-farm mixed income",
            "low",
        )
    )
    q = b.v(SF, sf("app1.total_revenue.ii.c.6.xi-petroleum"))
    items.append(
        (
            "G_STA",
            "petroleum_royalties",
            q,
            payers(q.v, mine, False),
            "RBI SF App. I ii.c.6.xi petroleum (onshore oil and gas royalties) -> public/private corporations by "
            "NAS 7.1A/7.1B mining OS + CFC",
            "low",
        )
    )

    sat_rows: list[dict[str, Any]] = []
    tot = {"G_CEN": Q(0.0), "G_STA": Q(0.0)}
    for gov, comp, total, pay, how, conf in items:
        keys_used = pids_of(mine) if comp in ("petroleum_rent", "mining_royalties", "petroleum_royalties") else []
        if comp == "telecom_licence":
            keys_used = pids_of(comm)
        if comp in ("interest_govt_servants",):
            keys_used = pids_of(d.public_wage_key)
        if comp == "mining_royalties":
            keys_used += pids_of(d.mi_nonfarm)
        pid = b.prov(
            "R7x",
            "estimated",
            total.pids + keys_used,
            f"Gap map R7x (DECISIONS D2-9, XR-1), component {comp}: cash 2023-24 (latest vintage) {how}. The "
            f"payer split is a key; the line total is held by its own band gov.r7x.{gov.lower()}.{comp} (+-5%, "
            "cash vs accrual; government-32, audit 2026-10-01) inside the gov.r7x.* government band, and each payer "
            "sector's part (E_NFPU, E_NFPR, households) within 25% of its key share.",
            main=total.pids[0],
        )
        for payer, val in sorted(pay.items()):
            b.add(gov, payer, "R7x", comp, val, pid, "estimated", "free", conf=conf)
        payers_line = sorted(k for k, v in pay.items() if v != 0.0)
        b.cons.append(constraint(f"gov.r7x.{gov.lower()}.{comp}", "R7x", [gov], payers_line, total.v, prov_id=pid,
                                 kind="band", tol_rel=0.05, refs=["R7x"], components=[comp],
                                 description=f"R7x {comp}: the published cash line +-5% (cash vs accrual)"))
        # the payer split of a multi-payer line is a key (NAS 7.1A/B/C OS(+MI) + CFC): a trial run of the Wave C
        # fix moved it up to 3x (telecom licence fees from public NFCs 4,511 -> 13,992) to carry E_NFPU's prior
        # surplus; each payer sector's part is held within 25% of its key share (government-32, audit 2026-10-01)
        sectors = {"E_NFPU": ["E_NFPU"], "E_NFPR": ["E_NFPR"], "HH": [h for h in HH if pay.get(h, 0.0) != 0.0]}
        if sum(1 for accts in sectors.values() if any(pay.get(a, 0.0) != 0.0 for a in accts)) > 1:
            for sec, accts in sectors.items():
                part = sum(pay.get(a, 0.0) for a in accts)
                if part == 0.0:
                    continue
                b.cons.append(constraint(
                    f"gov.r7x.{gov.lower()}.{comp}.{sec.lower()}", "R7x", [gov], accts, part, prov_id=pid, kind="band",
                    tol_rel=0.25, refs=["R7x"], components=[comp],
                    description=f"R7x {comp} paid by {sec} near its key share (band 25%)",
                ))  # fmt: skip
        tot[gov] = tot[gov] + total
        sat_rows.append({"series_id": f"included.{comp}", "item": comp, "status_note": "included",
                         "government": gov, "value": total.v})  # fmt: skip
    # excluded lines, logged in the satellite (and in docs/phase2/issues/government.md)
    excluded = {
        "interest_cash_balance_investment": ["fa8.0049.03.110"],
        "interest_sdr_imf": ["fa8.0049.03.115"],
        "premium_and_interest_on_market_loans": ["fa8.0049.03.116", "fa8.0049.03.117"],
        "interest_foreign_govts_and_ifis": ["fa8.0049.03.111", "fa8.0049.03.119"],
        "interest_other_receipts_grantees_refunds": ["fa8.0049.03.800", "fa8.0049.03.801", "fa8.0049.03.900"],
        "interest_from_states_and_uts": ["fa8.0049.01.total", "fa8.0049.02.total"],
        "petroleum_act_receipts_and_other": ["fa8.0802.00.104", "fa8.0802.00.800", "fa8.0802.00.801"],
        "telecom_wpc_spectrum_and_refunds": ["fa8.1275.00.103", "fa8.1275.00.800", "fa8.1275.00.900"],
    }
    ex_q = []
    for k, ids in excluded.items():
        q = lines(ids)
        ex_q.append(q)
        sat_rows.append({"series_id": f"excluded.{k}", "item": k, "status_note": "excluded", "government": "G_CEN",
                         "value": q.v})  # fmt: skip
    ex_q.append(itb14)
    sat_rows.append({"series_id": "excluded.states_interest_on_14day_itbs_intra_gg",
                     "item": "states_interest_on_14day_itbs_intra_gg", "status_note": "excluded",
                     "government": "G_STA", "value": itb14.v})  # fmt: skip
    for gov in GOV:
        pid_t = b.prov(
            "R7x",
            "derived",
            tot[gov].pids,
            f"Gap map R7x: total property income other than dividends written for {gov} (cash 2023-24, "
            "latest vintage; the included components listed in the gov_r7x_items satellite).",
            main=tot[gov].pids[0],
        )
        payers_all = ["E_NFPU", "E_NFPR", *HH]
        b.cons.append(constraint(f"gov.r7x.{gov.lower()}", "R7x", [gov], payers_all, tot[gov].v, prov_id=pid_t,
                                 kind="band", tol_rel=0.05, refs=["R7x"],
                                 description=f"{gov} interest from non-GG units and resource rents = its cash items "
                                             "+-5% (cash vs accrual)"))  # fmt: skip
    pid_s = b.prov(
        "R7x",
        "derived",
        pids_of(tot.values(), ex_q),
        "R7x item list: every Union / State line considered, included (written) or excluded (with the "
        "reason in the item name): cash 2023-24, latest vintage.",
        main=tot["G_CEN"].pids[0],
    )
    b.sat(
        "gov_r7x_items",
        "R7x",
        sat_rows,
        pid_s,
        "derived",
        "R7x: GG interest and rent items included and excluded",
        ["item", "status_note", "government"],
    )
    b.memo.update(r7x=tot)


# =====================================================================================================
# R9 (constraint), R9a (group entries), R9d (departmental enterprises)
# =====================================================================================================


def _pensions(b: Build) -> None:
    d = b.deps
    key = shares({g: d.public_wage_key[g].v for g in HH}, "public_sector_wage_key")
    gross_c = b.v(FA_E, "fa9.2071.total")
    nps_c = b.vsum(FA_E, ["fa9.2071.01.117", "fa9.2071.01.902"])
    cghs = b.v(FA_E, "fa9.2071.01.118")
    cen = gross_c - nps_c - cghs
    gross_s = b.v(SF, sf("app2.total_expenditure.ii.e-pensions"))
    nps_s = b.v(PFRDA, "m7d.annual_contribution_employer.state_govt.current")
    sta = gross_s - nps_s
    pid_c = b.prov(
        "R9",
        "derived",
        pids_of(gross_c, nps_c, cghs),
        "Gap map R9: Centre pensions paid (D62) = Union FA 2023-24 MH 2071 total - the government "
        "contribution to the defined-contribution pension scheme (2071.01.117 + .902: NPS, employer CE that "
        "reaches households via F_LREG and I_INPE) - medical treatment of CGHS pensioners (2071.01.118: in "
        "kind, already in health GFCE); latest vintage. Delhi pensions paid by the Union (01.120) stay "
        "here.",
        main=gross_c.pids[0],
    )
    pid_s = b.prov(
        "R9",
        "derived",
        pids_of(gross_s, nps_s),
        "Gap map R9: States' pensions paid = RBI SF 2023-24 App. II ii.e pensions (all States + UTs; plan "
        "C4: coverage = G_STA; KFI 4,94,938.72 for 28 States is the cross-check) - PFRDA State-sector "
        "employer NPS contribution 2023-24 (m7d; assumption A-R9-1: booked inside the States' pension head, "
        "as most States use MH 2071 for it); latest vintages.",
        main=gross_s.pids[0],
    )
    pid_a = b.prov(
        "R9a",
        "estimated",
        pids_of(gross_c, nps_c, cghs, gross_s, nps_s, d.public_wage_key),
        "Gap map R9a: government pensions (R9 net totals, Centre and States) split over the 10 groups by "
        "the "
        "public-sector wage key (factors' factor_income_keys public_sector_wage_key: F_LREG income by "
        "group x "
        "PLFS 2023-24 public-sector worker share of its area), normalised within each government; a proxy "
        "for past government employment (no microdata, D1-2): low confidence.",
        main=gross_c.pids[0],
    )
    for gov, tot in (("G_CEN", cen), ("G_STA", sta)):
        for g, val in split(tot.v, key).items():
            b.add(g, gov, "R9a", "pensions", val, pid_a, "estimated", "free", conf="low")
    b.cons.append(
        constraint(
            "gov.r9.centre",
            "R9",
            HH,
            ["G_CEN"],
            cen.v,
            prov_id=pid_c,
            kind="band",
            tol_rel=0.02,
            refs=["R9a"],
            description="Centre pensions (MH 2071 net of NPS and CGHS) +-2%",
        )
    )
    b.cons.append(
        constraint(
            "gov.r9.states",
            "R9",
            HH,
            ["G_STA"],
            sta.v,
            prov_id=pid_s,
            kind="band",
            tol_rel=0.03,
            refs=["R9a"],
            description="States' pensions (RBI SF net of PFRDA SG employer) +-3%",
        )
    )
    # R9d: departmental enterprises (Railways, Posts) -> E_NFPU pays
    rail = b.v(AFS, "afs.pa_disbursements.i_railway_funds")
    posts = b.v(FA_E, "fa9.3201.07.total") - b.v(FA_E, "fa9.3201.07.110")
    pid_d = b.prov(
        "R9d",
        "estimated",
        pids_of(rail, posts, d.public_wage_key),
        "Gap map R9d (DECISIONS D2-9, XR-2): pensions paid by departmental enterprises (public NFCs), "
        "latest vintage: Railways = AFS 2023-24 Public Account disbursements of the Railway Funds "
        "(assumption A-R9d-1: dominated by the Railway Pension Fund; the Railways' appropriation to funds, "
        "MH 3002/3003 .12, is 59,800 in the same year); Posts = Union FA MH 3201.07 total pension - "
        ".110 (NPS contribution, CE). Split over groups by the public-sector wage key: low.",
        main=rail.pids[0],
    )
    for comp, tot in (("railways", rail), ("posts", posts)):
        for g, val in split(tot.v, key).items():
            b.add(g, "E_NFPU", "R9d", comp, val, pid_d, "estimated", "free", conf="low")
    # audit BS-6 (government-33): the published totals the R9d split rests on are declared, so balancing can move
    # the group split but not double the level (it did: railways 59,802 -> 1,11,414 while the AFS line is 59,802)
    pid_rt = b.prov(
        "R9d",
        "derived",
        pids_of(rail, posts),
        "Gap map R9d totals (constraint targets; DECISIONS D2-9): Railways = AFS 2023-24 Public Account "
        "disbursements of the Railway Funds (as published); Posts = Union FA MH 3201.07 total pension - .110 (NPS "
        "contribution); latest vintages. Band +-10%: assumption A-R9d-1 (the Railway Funds disbursements are "
        "dominated by the Railway Pension Fund) and cash vs accrual; the audit of 2026-10-01 (BS-6) asked for it.",
        main=rail.pids[0],
    )
    for comp, tot in (("railways", rail), ("posts", posts)):
        b.cons.append(constraint(
            f"gov.r9d.{comp}", "R9d", HH, ["E_NFPU"], tot.v, prov_id=pid_rt, kind="band", tol_rel=0.10,
            refs=["R9d"], components=[comp],
            description=f"R9d {comp} pensions paid by departmental enterprises near their published total (band 10%)",
        ))  # fmt: skip
    b.memo.update(r9_cen=cen, r9_sta=sta, pid_r9c=pid_c, pid_r9s=pid_s, kfi_pen=b.v(KFI, "kfi.b_1_b-pension_and_other_"
                  "retirement_benefits.in.all_states_28"), r9_civil=b.v(FA_E, "fa9.2071.01.total") - nps_c - cghs,
                  r9_defence=b.v(FA_E, "fa9.2071.02.total"), wage_key=key)  # fmt: skip


# =====================================================================================================
# R10: current cash transfers to households
# =====================================================================================================


def _r10(b: Build) -> None:
    d = b.deps
    key = shares({g: d.pop[g].v for g in HH}, "pop_persons")
    sub = b.rows(FC16_SUB)
    st = sub.filter(pl.col("series_id").str.contains(r"^sub\.(cash_transfers|social_security)\.in-[a-z]+\.gg_state$"))
    schemes = b.frame_sum(st)
    states = sorted(set(st["geography"].to_list()))
    acc = b.rows(FC16_ACC).filter(pl.col("series_id").str.starts_with("fa.revenue_expenditure.mh2235.in-"))
    mh_all = b.frame_sum(acc)
    mh_rep = b.frame_sum(acc.filter(pl.col("geography").is_in(states)))
    ssw = b.v(SF, sf("app2.total_expenditure.i.a.9-social_security_and_welfare"))
    g1, g2 = mh_all.v / mh_rep.v, ssw.v / mh_all.v
    sta = Q(schemes.v * g1 * g2, schemes.p | mh_all.p | ssw.p)
    pid = b.prov(
        "R10",
        "estimated",
        pids_of(schemes, mh_all, ssw, d.pop),
        f"Gap map R10, States: FC16 2023-24 subsidy data, cash transfers + social security of the "
        f"{len(states)} reporting States (sub.cash_transfers / sub.social_security gg_state), grossed up "
        f"to 28 "
        "States with FC16 State Finance Accounts MH 2235 (all / reporting States) and to States + UTs with "
        "RBI "
        "SF App. II i.a.9 social security and welfare (/ MH 2235 all States); latest vintages; split over "
        "groups by population (households hh_keys pop_persons): low. Excluded: farm income support "
        "(P10a), free grain (C2a), health/education in kind (GFCE), housing and loan waivers (capital, K6 "
        "via COFOG), State food subsidies (taxes P9a).",
        main=schemes.pids[0],
    )
    for g, val in split(sta.v, key).items():
        b.add(g, "G_STA", "R10", "cash_schemes", val, pid, "estimated", "free", conf="low")
    ss_c = b.v(FC16_SUB, "sub.social_security.in.gg_centre")
    lpg = b.v(EXP, "stat7.petroleum.lpg_subsidy")
    lpg_dbt = lpg + d.p9_rpet  # P9 is negative
    pid_c = b.prov(
        "R10",
        "estimated",
        pids_of(ss_c, d.pop),
        "Gap map R10, Centre: FC16 2023-24 Union social security (sub.social_security gg_centre), latest "
        "vintage, split by population: low. Flag: it may include NSAP money released through MH 3601 "
        "(then counted with the States too); no clean NSAP split exists.",
        main=ss_c.pids[0],
    )
    for g, val in split(ss_c.v, key).items():
        b.add(g, "G_CEN", "R10", "social_security", val, pid_c, "estimated", "free", conf="low")
    pid_l = b.prov(
        "R10",
        "estimated",
        pids_of(lpg, d.p9_rpet, d.pop),
        "Gap map R10, Centre: LPG subsidy paid as DBT to households = Expenditure Profile Statement 7 LPG "
        "subsidy 2023-24 - the part the SUT books as a product subsidy on C_RPET (production P9 entry); SNA "
        "2008 treats transfers to households as consumers as social benefits. Split by population: low.",
        main=lpg.pids[0],
    )
    for g, val in split(lpg_dbt.v, key).items():
        b.add(g, "G_CEN", "R10", "lpg_dbt", val, pid_l, "estimated", "free", conf="low")
    # PM-KISAN (government-30; audit BS-5, 2026-10-01; DECISIONS D2-24): a current transfer to households (R10), not a
    # D39 production subsidy; taxes no longer books it in P10a. NAS 4.2 does not itemise PM-KISAN: that NAS books it
    # in COFOG 04.agri current transfers is inferred (close-out V-TX-8)
    kisan = b.v(FA_E, "fa9.2401.00.130")
    fkey = shares({g: d.mi_farm[g].v for g in HH}, "mixed_income_farm")
    pid_k = b.prov(
        "R10",
        "estimated",
        pids_of(kisan, d.mi_farm),
        "Gap map R10, Centre: PM-KISAN income support to landholding farm families = Union Finance Accounts "
        "2023-24 St 9 MH 2401.00.130, latest vintage (cash as accrual). A current transfer to households "
        "(DECISIONS D2-24, amending D0-5's default): NAS 2026 St 4.2 does not itemise PM-KISAN, so its NAS "
        "treatment is inferred: St 4.2 current expenditure = consumption + subsidies + current transfers, so "
        "subsidies and transfers are disjoint, St 4.2 agriculture (COFOG 04.agri) current transfers, 58,325.32, "
        "are large enough to hold it, and the SNA treats a flat payment per family as a transfer (government-9, "
        "government-30; taxes dropped it from P10a). Split over the 10 groups by factors' farm mixed income (F2 "
        "`farm`; assumption A-R10-2: no beneficiary data by group). The scheme pays a flat amount per "
        "landholding family, so an income-weighted key overweights the groups with large farms (H_R4, H_R5) "
        "against a count of beneficiary families (close-out V-GOV-14; Checkpoint B): low.",
        main=kisan.pids[0],
    )
    for g, val in split(kisan.v, fkey).items():
        b.add(g, "G_CEN", "R10", "pm_kisan", val, pid_k, "estimated", "free", conf="low")
    # the Union's R10 lines are published totals split by a key: each total is held (audit 2026-10-01: in a trial
    # run with only the COFOG band, balancing cut them 38% to carry G_CEN's prior shortfall). PM-KISAN (Finance
    # Accounts) and LPG DBT (St 7 less the SUT P9) +-5% (cash vs accrual); FC16 Union social security +-10% (it may
    # include NSAP money counted with the States, government-11)
    for comp, tot, pid_x, tol in (("pm_kisan", kisan, pid_k, 0.05), ("lpg_dbt", lpg_dbt, pid_l, 0.05),
                                  ("social_security", ss_c, pid_c, 0.10)):  # fmt: skip
        b.cons.append(constraint(
            f"gov.r10.{comp}", "R10", HH, ["G_CEN"], tot.v, prov_id=pid_x, kind="band", tol_rel=tol, refs=["R10"],
            components=[comp], description=f"Union R10 {comp} near its published total (band {tol:.0%})",
        ))  # fmt: skip
    b.memo.update(r10_sta=sta, r10_cen=ss_c + lpg_dbt + kisan, r10_g=(g1, g2), pm_kisan=kisan)


# =====================================================================================================
# R18: current transfers to corporations (not subsidies)
# =====================================================================================================


def _r18(b: Build) -> None:
    psu = b.v(GIA, "gia.cash.public_sector_undertakings.total") - b.v(GIA, "gia.cash.public_sector_undertakings."
                                                                          "capital_assets")  # fmt: skip
    coop = b.v(GIA, "gia.cash.cooperatives.total") - b.v(GIA, "gia.cash.cooperatives.capital_assets")
    lic = b.v(EXP, "stat7.interest_subsidies.interest_subsidy_to_lic_for_pension_plan_for_senior_citizens")
    specs = [
        (
            "E_NFPU",
            "psu_revenue_grants",
            psu,
            "derived",
            "Union IGAS-2 grants-in-aid to public sector undertakings (cash) less the part for creation of capital "
            "assets (that part is K6)",
        ),
        (
            "E_NFPR",
            "coop_revenue_grants",
            coop,
            "derived",
            "Union IGAS-2 grants-in-aid to co-operative societies less the capital-asset part; co-operatives are "
            "private corporations in NAS (assumption A-R18-1; the plan's E_NFPU is corrected)",
        ),
        (
            "E_INSP",
            "lic_pension_subsidy",
            lic,
            "official",
            "Expenditure Profile Statement 7 interest subsidy to LIC for the senior-citizen pension plan, as published",
        ),
    ]
    rows = []
    for col, comp, q, status, how in specs:
        pid = b.prov(
            "R18",
            status,
            q.pids,
            f"Gap map R18: {how}; FY 2023-24, latest vintage. Only current transfers "
            "taxes does not classify as subsidies (P9a/P10a).",
        )
        b.add(col, "G_CEN", "R18", comp, q.v, pid, status, "free", conf="low")
        if comp != "lic_pension_subsidy":
            # audit BS-11: the IGAS-2 grants are published cash totals; balancing cut psu_revenue_grants 44% with
            # nothing but E_NFPU's prior surplus behind it. Band +-10% (cash vs accrual); the possible overlap with
            # taxes' FC16 Union 'business' subsidies (government-28) stays open for Checkpoint B
            b.cons.append(constraint(
                f"gov.r18.{comp}", "R18", [col], ["G_CEN"], q.v, prov_id=pid, kind="band", tol_rel=0.10,
                refs=["R18"], components=[comp],
                description=f"R18 {comp} near the IGAS-2 grants less their capital part (band 10%)",
            ))  # fmt: skip  # its source line is the St 7 row below: one row per source line (V-GOV-8)
            rows.append({"series_id": f"r18.{comp}", "item": comp, "destination": "R18", "account": col,
                         "value": q.v})  # fmt: skip
    # the classification of the other transfer and subsidy lines (so nothing lands twice)
    cls = [
        ("stat7.food.food_subsidy", "C2a", "C_CROP<-G_CEN (grain GFCE; St 7 is a cross-check only)"),
        ("stat7.fertiliser", "P9a", "taxes: product subsidy on C_CHEM"),
        ("stat7.petroleum.lpg_subsidy", "P9a+R10", "taxes P9a C_RPET part; rest R10 lpg_dbt"),
        ("stat7.interest_subsidies.modified_interest_subvention_scheme", "P9a", "taxes: product subsidy on C_FINS"),
        ("stat7.interest_subsidies.interest_equalisation_scheme", "P10a", "taxes: production subsidy"),
        ("stat7.other_subsidies.pradhan_mantri_annadata_aay_sanrakshan_yojna", "P9a", "taxes: C_CROP"),
        ("stat7.interest_subsidies.interest_subsidy_to_lic_for_pension_plan_for_senior_citizens", "R18", "E_INSP"),
    ]
    ins = [lic, psu, coop]
    for sid, dest, acct in cls:
        q = b.v(EXP, sid)
        ins.append(q)
        rows.append({"series_id": f"stat7.{sid.split('.', 1)[1]}", "item": sid, "destination": dest, "account": acct,
                     "value": q.v})  # fmt: skip
    for sid, dest, acct in (("fa9.2401.00.130", "R10", "PM-KISAN: R10 H_* <- G_CEN pm_kisan (inferred NAS 4.2 COFOG "
                                                        "04.agri current transfer; not P10a, government-30, D2-24)"),):
        q = b.v(FA_E, sid)
        ins.append(q)
        rows.append({"series_id": f"fa.{sid}", "item": sid, "destination": dest, "account": acct, "value": q.v})
    # IGAS-2 statutory bodies and development authorities: one class for both parts (assumption A-K6-4, V-GOV-7)
    st_tot = b.v(GIA, "gia.cash.statutory_bodies_and_development_authorities.total")
    st_cap = b.v(GIA, "gia.cash.statutory_bodies_and_development_authorities.capital_assets")
    ins += [st_tot, st_cap]
    for sid, item, q in (("igas2.statutory_bodies.revenue", "gia.cash.statutory_bodies_and_development_authorities."
                          "total - capital_assets", st_tot - st_cap),
                         ("igas2.statutory_bodies.capital", "gia.cash.statutory_bodies_and_development_authorities."
                          "capital_assets", st_cap)):  # fmt: skip
        rows.append({"series_id": sid, "item": item, "destination": "none",
                     "account": "intra-G_CEN: statutory bodies are GG (A-K6-4); not R18 or K6",
                     "value": q.v})  # fmt: skip
    for sid, dest, acct in (
        ("sub.food.in.gg_centre", "C2a", "cross-check of free grain only"),
        ("sub.business.in.gg_centre", "P9a/P10a", "taxes (FC16 Union business)"),
        ("sub.housing.in.gg_centre", "K6", "capital transfer, inside NAS 4.2 COFOG 06"),
    ):
        q = b.v(FC16_SUB, sid)
        ins.append(q)
        rows.append({"series_id": f"fc16.{sid}", "item": sid, "destination": dest, "account": acct, "value": q.v})
    for sid, dest, acct in (
        ("food", "P9a", "taxes: State food subsidies on C_TRAD (XR-23)"),
        ("housing", "K6", "capital (COFOG 06)"),
        ("loan_waiver", "K6", "capital (not written; logged)"),
        ("power", "P9a", "taxes: C_UTIL"),
        ("transport", "P9a", "taxes: C_TRNS"),
        ("agriculture", "P10a", "taxes"),
        ("business", "P9a/P10a", "taxes"),
        ("education", "C2a", "in-kind (GFCE)"),
        ("health", "C2a", "in-kind (GFCE)"),
        ("cash_transfers", "R10", "cash_schemes"),
        ("social_security", "R10", "cash_schemes"),
    ):
        df = b.rows(FC16_SUB).filter(pl.col("series_id").str.contains(rf"^sub\.{sid}\.in-[a-z]+\.gg_state$"))
        q = b.frame_sum(df)
        ins.append(q)
        rows.append({"series_id": f"fc16.states.{sid}", "item": f"sub.{sid}.gg_state (reporting States)",
                     "destination": dest, "account": acct, "value": q.v})  # fmt: skip
    pid = b.prov(
        "R18",
        "derived",
        pids_of(ins),
        "Transfer classification (mirrors taxes' tax_classification): every Statement 7, FC16 subsidy and "
        "IGAS-2 line considered for R10/R18, with the ref that books it, one row per source line (so no line "
        "lands twice). IGAS-2 grants to statutory bodies and development authorities (revenue and capital "
        "parts) are intra-G_CEN: assumption A-K6-4, they are GG autonomous institutions in NAS 4.1.",
        main=lic.pids[0],
    )
    b.sat(
        "gov_transfer_classification",
        "R18",
        rows,
        pid,
        "derived",
        "Where each subsidy / transfer line is booked (C2a, P9a, P10a, R10, R18, K6)",
        ["item", "destination", "account"],
    )
    b.memo.update(r18=psu + coop + lic)


# =====================================================================================================
# K6: capital transfers (RoW on the NAS basis; domestic from NAS 4.2 COFOG)
# =====================================================================================================

COFOG_RECIPIENT = {  # NAS 4.2 COFOG function -> recipient capital account (plan s.2.9)
    "06": "K_HH", "10": "K_HH", "09": "K_HH", "07": "K_HH", "08": "K_HH", "04.agri": "K_HH",
    "04.energy": "K_NFPU", "04.transport_comm": "K_NFPU", "04.mining_mfg_constr": "K_NFPU", "04.water_supply": "K_NFPU",
    "04.other": "K_NFPU", "04.admin": "K_NFPU", "03": "K_NFPU", "01": "K_NFPU",
}  # fmt: skip


def _k6(b: Build) -> None:
    ctx = b.ctx
    pay = b.v(INVIS, "invis.inr.official_transfers.payments.current")
    gg_net = b.v(NAS + "s6_1", "s6_1.capital_transfers_to_general_government_from_the_rest_of_the.current")
    non_gg = b.v(NAS + "s6_1", "s6_1.capital_transfers_to_corporations_households_and_npishs_net.current")
    npnfa = b.v(NAS + "s6_1", "s6_1.acquisitions_less_disposal_of_non_produced_non_financial_ass.current")
    rec = pay + gg_net
    pid = b.prov(
        "K6",
        "official",
        pay.pids,
        "Gap map K6, RoW: general-government capital transfers paid to the RoW = RBI BoP invisibles 2023-24 "
        "(old format) IV official transfers, payments, Rs crore, latest vintage, as published. NAS 6.1 books "
        "GG transfers with the RoW as capital, so there is no R15 (plan C6).",
    )
    b.add("K_ROW", "K_GCEN", "K6", "gg_payments", pay.v, pid, "official", "fixed", bop="other")
    pid = b.prov(
        "K6",
        "derived",
        pids_of(pay, gg_net),
        "Gap map K6, RoW: GG capital transfers received from the RoW = BoP official-transfer payments + NAS "
        "2026 St 6.1 'capital transfers to GG from the RoW, net' (-6,999.68), so the pair nets exactly to "
        "NAS (XR-14; the BoP receipts 1,558 would leave K_ROW 0.68 out).",
        main=gg_net.pids[0],
    )
    b.add("K_GCEN", "K_ROW", "K6", "gg_receipts", rec.v, pid, "derived", "fixed", bop="other")
    pid = b.prov(
        "K6",
        "derived",
        non_gg.pids,
        "Gap map K6, RoW: NAS 2026 St 6.1 capital transfers to corporations, households and NPISHs, net "
        "(received), all to K_HH (assumption A-K6-1: migrants' transfers and grants to NPISHs dominate).",
    )
    b.add("K_HH", "K_ROW", "K6", "nongg_net", non_gg.v, pid, "derived", "fixed", bop="other")
    pid = b.prov(
        "K6",
        "derived",
        npnfa.pids,
        "Gap map K6, RoW: NAS 2026 St 6.1 acquisitions less disposals of non-produced non-financial assets "
        "(+, India acquires, so India pays the RoW), payer K_NFPR (assumption A-K6-2).",
    )
    b.add("K_ROW", "K_NFPR", "K6", "npnfa", npnfa.v, pid, "derived", "fixed", bop="other")

    # --- domestic: NAS 4.2 COFOG capital transfers by recipient; Centre = identifiable IGAS-2 grantees -------
    cof = {fn: b.v(NAS + "s4_2", f"s4_2.capital_transfer.{fn}.current") for fn in COFOG_RECIPIENT}
    neg = b.v(NAS + "s4_2", "s4_2.capital_transfer.05.current")
    total = b.v(NAS + "s4_2", "s4_2.capital_transfer.total.current")
    parts = {**cof, "05": neg, "02": b.v(NAS + "s4_2", "s4_2.capital_transfer.02.current")}
    diff = total - qsum(parts.values())
    if abs(diff.v) > 0.05:
        raise SamError(f"K6: COFOG capital transfers by function do not add to the total ({diff.v:,.2f})")
    rec_tot: dict[str, Q] = {}
    for fn, acct in COFOG_RECIPIENT.items():
        q = cof[fn] - pay if fn == "01" else cof[fn]  # 01 GPS includes the grants to the RoW (assumption A-K6-3)
        rec_tot[acct] = rec_tot.get(acct, Q(0.0)) + q
    psu = b.v(GIA, "gia.cash.public_sector_undertakings.capital_assets")
    ngo = b.v(GIA, "gia.cash.ngos.capital_assets")
    coop = b.v(GIA, "gia.cash.cooperatives.capital_assets")
    pid_c = b.prov(
        "K6",
        "derived",
        pids_of(psu, ngo, coop),
        "Gap map K6, domestic, Centre: Union IGAS-2 2023-24 grants 'for creation of capital assets' to "
        "non-government grantees (cash, latest vintage): PSUs -> K_NFPU, NGOs -> K_HH (NPISHs are in the "
        "household account), co-operatives -> K_NFPR. The 'Others' grantees' capital part is the "
        "outside-treasury CSS (R2k, D2-8). Statutory bodies and development authorities are not "
        "written: assumption A-K6-4, they are GG autonomous institutions (NAS 4.1), so the grant is "
        "intra-G_CEN, the same class as their revenue grants, which are not written either (V-GOV-7).",
        main=psu.pids[0],
    )
    b.add("K_NFPU", "K_GCEN", "K6", "igas2_psu", psu.v, pid_c, "derived", "free", conf="medium")
    b.add("K_HH", "K_GCEN", "K6", "igas2_ngos", ngo.v, pid_c, "derived", "free", conf="medium")
    b.add("K_NFPR", "K_GCEN", "K6", "igas2_cooperatives", coop.v, pid_c, "derived", "free", conf="medium")
    sta_hh = rec_tot["K_HH"] - ngo
    sta_nfpu = rec_tot["K_NFPU"] - psu - coop
    pid_s = b.prov(
        "K6",
        "estimated",
        pids_of(cof.values(), pay, psu, ngo, coop),
        "Gap map K6, domestic, States: NAS 2026 St 4.2 COFOG capital transfers of GG (latest vintage) by "
        "recipient: 06 housing, 10 social protection, 09 education, 07 health, 08 recreation, 04 "
        "agriculture "
        "-> K_HH (DECISIONS D2-6: written in K6; NAS household saving cannot see them, so "
        "capital_financial's "
        "K9_HH shows it); 04 energy, transport, mining/manufacturing/construction, water, other, admin, 03 "
        "and 01 less the BoP grants to the RoW (assumption A-K6-3) -> K_NFPU; less the Centre's identified "
        "IGAS-2 non-government grantees (PSUs and co-operatives from K_NFPU, NGOs from K_HH; statutory bodies "
        "are GG, assumption A-K6-4, so nothing is deducted for them); the rest is the States' (residual): "
        "low. 05 environment (negative) is dropped and logged.",
        main=cof["06"].pids[0],
    )
    b.add("K_HH", "K_GSTA", "K6", "cofog_residual", sta_hh.v, pid_s, "estimated", "free", conf="low")
    b.add("K_NFPU", "K_GSTA", "K6", "cofog_residual", sta_nfpu.v, pid_s, "estimated", "free", conf="low")
    pid_t = b.prov(
        "K6",
        "official",
        total.pids,
        "NAS 2026 Statement 4.2 GG capital transfers (COFOG total), 2023-24, current prices, as published.",
    )
    b.cons.append(constraint(
        "gov.cofog.capital_transfers", "K6", ["K_HH", "K_NFPU", "K_NFPR", "K_ROW"], ["K_GCEN", "K_GSTA"], total.v,
        prov_id=pid_t, kind="band", tol_rel=0.05, refs=["K6"],
        description="GG capital transfers paid (incl. to the RoW) = NAS 4.2 COFOG total +-5%"))  # fmt: skip
    ctx.log(
        f"K6: COFOG 05 environment {neg.v:,.2f} dropped (negative); domestic K_HH {rec_tot['K_HH'].v:,.2f}, "
        f"K_NFPU {rec_tot['K_NFPU'].v:,.2f}"
    )
    b.memo.update(k6_total=total, k6_neg05=neg, k6_row=(pay, rec, non_gg, npnfa), gg_net=gg_net)


# =====================================================================================================
# K3, K3a: saving split
# =====================================================================================================


def _k3a(b: Build) -> None:
    """K3a saving priors from a cash-to-NAS bridge (plan s.2.8, repaired 2026-10-01; issues government-2, -25, -27).

    Gross saving = GDI - GFCE. GG's GOS is its CFC, which is income, and CFC is also a cost inside GFCE, so CFC
    cancels: gross saving is the current (revenue) balance on a NAS-coverage basis, and nothing is added for CFC
    (the plan's CFC step treated the cash balance as net saving; V-GOV-3). The treasury balances miss the saving of
    GG units outside the Union and State treasury accounts; the one measured in clean data, the urban local bodies'
    revenue surplus (FC16 cityfinance dump), is added to the States (institutional boundary, D2-8). The rest of NAS
    1.9 GG saving (the unexplained remainder) is allocated by the NVA (NAS 4.1) of the GG units outside the treasury
    accounts, split as factors' F4b splits them (local bodies and most autonomous institutions are the States').
    """
    ctx, d = b.ctx, b.deps
    k3 = b.v(NAS + "s1_9", "s1_9.general_government.current")
    rd = b.v(AFS, "afs.cfi_rev_receipts.excess_of_disbursements_over_receipts_revenue_deficit")
    fe_all = b.rows(FA_E).filter(~pl.col("series_id").str.ends_with(".total") & pl.col("series_id").str.contains(
        r"^fa9\.[23]\d{3}\."))  # fmt: skip
    # departmental enterprises (Railways MH 3001-3003 and 3006 / 1001-1003, Posts MH 3201 / 1201) are public NFCs in
    # NAS (NAS 1.9 saves them in public NFC departmental enterprises; St 8.16 railways / communication CFC): their
    # revenue-account receipts and expenditure (incl. their own fund lines) leave the Centre's GG balance. MH 3006
    # 'Appropriations from Railway Surplus' (the Railway Development Fund and its 797 line) appropriates the Railways'
    # own surplus to the Railways' funds, so it belongs to the enterprise too (close-out V-GOV-11)
    is_de = pl.col("series_id").str.contains(r"^fa9\.(300[1-36]|3201)\.")
    fe = fe_all.filter(~is_de)
    f797 = b.frame_sum(fe.filter(pl.col("series_id").str.ends_with(".797")))
    met = b.frame_sum(fe.filter(pl.col("item_label").str.to_lowercase().str.contains("met from")))
    de_exp = b.frame_sum(fe_all.filter(is_de))
    de_rec = b.vsum(FA_R, ["fa8.1001.total", "fa8.1002.total", "fa8.1003.total", "fa8.1201.total"])
    capg = b.v(GCCA, "stat6.grand_total")
    t2b2, r2k = b.memo["t2b2"], b.memo["r2k"]
    cen = -rd + f797 + met + capg - t2b2 - (de_rec - de_exp)
    sbal = b.v(SF, sf("app4.a-surplus_deficit_on_revenue_account"))
    sink = b.v(SF, sf("app2.total_expenditure.ii.c.1-appropriation_for_reduction_or_avoidance_of_debt"))
    sta_treasury = sbal - r2k + t2b2 + sink
    # urban local bodies (inside G_STA): revenues less revenue expenditure, less capital grants received directly
    # from the Centre (IGAS-2; a capital transfer into G_STA, not saving). Grants routed through State treasuries are
    # intra-G_STA: their capital part already left the States' side as r2k.
    ulb_rev = b.v(ULB, "ulb.total_revenues.in.all_ulbs_in_dump")
    ulb_exp = b.v(ULB, "ulb.total_revenue_expenditure.in.all_ulbs_in_dump")
    ulb_cap = b.v(GIA, "gia.cash.urban_local_bodies.capital_assets")
    ulb_cen = b.v(ULB, "ulb.grants_for_centre_s_initiatives.in.all_ulbs_in_dump")
    ulb = ulb_rev - ulb_exp - ulb_cap
    sta = sta_treasury + ulb
    cfc_c, cfc_s = d.f4b["G_CEN"], d.f4b["G_STA"]  # memo only (cancels in gross saving)
    rem = k3 - (cen + sta)
    out = d.outside_nva
    w_c = out["G_CEN"].v / (out["G_CEN"].v + out["G_STA"].v)
    prior = {"G_CEN": cen + rem * w_c, "G_STA": sta + rem * (1.0 - w_c)}
    # +/- pair margins: each government's share of the unexplained remainder; the States' also carries the ULB
    # line's own uncertainty (grants for the Centre's initiatives may be capital grants received from outside G_STA)
    margin = {"G_CEN": abs(rem.v * w_c), "G_STA": abs(rem.v * (1.0 - w_c)) + abs(ulb_cen.v)}
    # sensitivities (report only): the plan's bridge (CFC added, remainder by revenue expenditure), and the repaired
    # bridge with other remainder rules or without the ULB grants for the Centre's initiatives
    rx_c = b.v(FA_E, "fa9.section.expenditure_heads_revenue_account")
    rx_s = b.v(SF, sf("app2.total_expenditure-total_expenditure"))
    w_rx = rx_c.v / (rx_c.v + rx_s.v)
    # the plan's Centre subtotal (departmental enterprises inside, their fund lines in the 797 / 'met from' sums)
    cen_plan = (-rd.v + b.frame_sum(fe_all.filter(pl.col("series_id").str.ends_with(".797"))).v
                + b.frame_sum(fe_all.filter(pl.col("item_label").str.to_lowercase().str.contains("met from"))).v
                + capg.v - t2b2.v)  # fmt: skip
    rem_plan = k3.v - (cen_plan + cfc_c.v + sta_treasury.v + cfc_s.v)
    rem_nocfc = k3.v - (cen_plan + sta_treasury.v)
    sens = {
        "plan_cfc_revexp": (cen_plan + cfc_c.v + rem_plan * w_rx, sta_treasury.v + cfc_s.v + rem_plan * (1 - w_rx)),
        "no_cfc_revexp": (cen_plan + rem_nocfc * w_rx, sta_treasury.v + rem_nocfc * (1 - w_rx)),
        "no_cfc_outside_nva": (cen_plan + rem_nocfc * w_c, sta_treasury.v + rem_nocfc * (1 - w_c)),
        "remainder_revexp": (cen.v + rem.v * w_rx, sta.v + rem.v * (1 - w_rx)),
        "remainder_to_states": (cen.v, sta.v + rem.v),
        "ulb_excl_centre_initiatives": (cen.v + (rem.v + ulb_cen.v) * w_c,
                                        sta.v - ulb_cen.v + (rem.v + ulb_cen.v) * (1 - w_c)),
    }  # fmt: skip
    ins = pids_of(k3, rd, f797, met, de_exp, de_rec, capg, t2b2, r2k, sbal, sink, ulb_rev, ulb_exp, ulb_cap, ulb_cen,
                  out)  # fmt: skip
    pid = b.prov(
        "K3a",
        "estimated",
        ins,
        "Gap map K3a: government gross saving priors from a cash-to-NAS bridge (plan s.2.8 as repaired on "
        "2026-10-01; latest vintages). Gross saving = GDI - GFCE, and CFC cancels (GG's GOS = CFC is income and CFC "
        "is inside GFCE), so no CFC is added to the cash balances (issues government-25, V-GOV-3). Centre = -(AFS "
        "2023-24 revenue deficit) + net transfers to Public Account funds booked as revenue expenditure (all "
        "2xxx/3xxx minor heads 797 + 'amount met from' fund deducts, Union FA) + grants for creation of capital "
        "assets (GCCA Statement 6, capital transfers) - T2b(ii) (paid from the GST fund outside the revenue "
        "account) - the net revenue of the departmental enterprises (Railways MH 1001-1003 receipts less MH "
        "3001-3003 expenditure and MH 3006 appropriations from the Railway surplus to the Railways' own funds, Posts "
        "MH 1201 less MH 3201; public NFCs in NAS, so outside GG saving; their fund lines, including MH 3006's 797 "
        "line, are left out of the 797 / 'met from' sums). States = RBI SF App. IV A revenue balance - R2k IGAS-2 "
        "capital grants (booked as States' revenue receipts) + T2b(ii) + sinking-fund appropriation (App. II "
        "ii.c.1, internal to GG) + the revenue surplus of "
        "urban local bodies (inside G_STA, D2-8; FC16 cityfinance dump 2023-24, 4,620 ULBs: total revenues - total "
        "revenue expenditure - IGAS-2 capital grants to ULBs, which are capital transfers received from the Centre). "
        "The unexplained remainder (NAS 2026 St 1.9 GG saving - bridge) is allocated by the NVA (NAS 2026 St 4.1) of "
        "the GG units outside the Union and State treasury accounts, split as factors' F4b splits them (Centre: the "
        "autonomous institutions F4b gives the Centre; States: local bodies + the other autonomous institutions): "
        "their saving is what the treasury balances miss. Each government's saving is written as two entries in "
        "its cell, saving_pos (+) and saving_neg (-), with a margin equal to its share of the remainder (States: plus "
        "the ULB grants for the Centre's initiatives, whose capital part is unknown), so balancing can move the net "
        "across zero (XR-17, FRAMEWORK_REQUESTS P-9): low confidence.",
        main=k3.pids[0],
    )
    for gov, kacct in (("G_CEN", "K_GCEN"), ("G_STA", "K_GSTA")):
        pos, neg = paired_saving(prior[gov].v, margin[gov])
        b.add(kacct, gov, "K3a", "saving_pos", pos, pid, "estimated", "free", conf="low")
        b.add(kacct, gov, "K3a", "saving_neg", neg, pid, "estimated", "free", conf="low")
        if abs(prior[gov].v) < PAIRED_SIGN_WARN:
            ctx.warn(
                f"K3a: {gov} saving prior {prior[gov].v:,.0f} is within Rs {PAIRED_SIGN_WARN:,.0f} crore of zero "
                "(sign fragile; written as a +/- pair)"
            )
    pid_k = b.prov(
        "K3",
        "official",
        k3.pids,
        "NAS 2026 Statement 1.9 gross saving of general government, 2023-24, current prices, as published.",
    )
    b.cons.append(
        constraint(
            "gov.k3.gg_saving",
            "K3",
            ["K_GCEN", "K_GSTA"],
            GOV,
            k3.v,
            prov_id=pid_k,
            tol_abs=CHECK_TOL,
            refs=["K3a"],
            description="GG gross saving = NAS 1.9 (K_GCEN<-G_STA and K_GSTA<-G_CEN do not exist)",
        )
    )
    steps = [
        ("centre.revenue_balance", -rd), ("centre.fund_transfers_797", f797), ("centre.met_from_funds", met),
        ("centre.capital_asset_grants", capg), ("centre.less_t2b_cess_loan_recovery", -t2b2),
        ("centre.departmental_enterprises_receipts", de_rec), ("centre.departmental_enterprises_expenditure", de_exp),
        ("centre.less_departmental_enterprises_net", -(de_rec - de_exp)), ("centre.subtotal", cen),
        ("states.revenue_balance", sbal),
        ("states.less_r2k_igas2_capital", -r2k), ("states.plus_t2b_cess_loan_recovery", t2b2),
        ("states.sinking_fund_appropriation", sink), ("states.treasury_subtotal", sta_treasury),
        ("states.ulb_total_revenues", ulb_rev), ("states.ulb_less_revenue_expenditure", -ulb_exp),
        ("states.ulb_less_igas2_capital_grants", -ulb_cap), ("states.ulb_revenue_surplus", ulb),
        ("states.subtotal", sta), ("nas_gg_saving", k3), ("unexplained_remainder", rem),
        ("remainder_key.outside_nva_g_cen", out["G_CEN"]), ("remainder_key.outside_nva_g_sta", out["G_STA"]),
        ("remainder_share_centre", Q(w_c)), ("prior.g_cen", prior["G_CEN"]), ("prior.g_sta", prior["G_STA"]),
        ("margin.g_cen", Q(margin["G_CEN"])), ("margin.g_sta", Q(margin["G_STA"])),
        ("memo.cfc_f4b_g_cen", cfc_c), ("memo.cfc_f4b_g_sta", cfc_s),
        ("memo.ulb_grants_for_centre_initiatives", ulb_cen), ("memo.revenue_expenditure_share_centre", Q(w_rx)),
    ]  # fmt: skip
    for name, (pc, ps) in sens.items():
        steps += [(f"sensitivity.{name}.g_cen", Q(pc)), (f"sensitivity.{name}.g_sta", Q(ps))]
    b.sat(
        "gov_fiscal_bridge",
        "K3a",
        [{"series_id": k, "item": k, "value": q.v, "unit": "ratio" if "share" in k else "INR_crore"} for k, q in steps],
        pid,
        "estimated",
        "K3a: cash revenue balances (+ ULB revenue surplus) to NAS gross saving, remainder, allocation, sensitivities",
        ["item"],
    )
    ctx.log(
        f"K3a: bridge Centre {cen.v:,.2f}; States treasury {sta_treasury.v:,.2f} + ULB revenue surplus {ulb.v:,.2f}; "
        f"remainder {rem.v:,.2f} (Centre share {w_c:.4f} by outside-treasury NVA); priors G_CEN "
        f"{prior['G_CEN'].v:,.2f}, G_STA {prior['G_STA'].v:,.2f} (plan bridge with CFC: "
        f"{sens['plan_cfc_revexp'][0]:,.2f} / {sens['plan_cfc_revexp'][1]:,.2f})"
    )
    b.memo.update(k3=k3, k3a_prior=prior, k3a_rem=rem)


# =====================================================================================================
# R9b: imputed OPS contributions, with the D2-5 evidence test
# =====================================================================================================


def _r9b(b: Build) -> None:
    ctx, d, m = b.ctx, b.deps, b.memo
    f = r9b_formula(m["r9_civil"].v, m["r9_defence"].v, ctx.year)
    centre = f["civil"] + f["defence"]
    states = m["r9_sta"].v * f["factor"]
    variants = {"none": 0.0, "centre_only": centre, "centre_and_states": centre + states}
    # NAS requirement: GG GDI - CFC - (taxes on products - subsidies on products + net production taxes)
    gdi = b.v(NAS + "s1_14", "s1_14.gg.gross_disposable_income.current")
    cfc = b.v(NAS + "s1_14", "s1_14.gg.consumption_of_fixed_capital.current")
    tp = b.v(NAS + "s1_1", "s1_1.taxes_on_products.current")
    sp = b.v(NAS + "s1_1", "s1_1.subsidies_on_products.current")
    npt = b.v(NAS + "s7_1", "s7_1.total.net_production_taxes.current")
    required = gdi - cfc - (tp - sp + npt)
    # interest paid by GG outside GG (proxy; fincorp writes the SAM entries later): Union MH 2049 less interest on
    # reserve funds, less interest on 14-day treasury bills (paid to the States: intra-GG, taken out of R7x
    # interest_states on the receiving side, V-GOV-1) and less premium/accrued interest received on market loans;
    # States' interest payments less interest on loans from the Centre (intra-GG)
    ui = b.v(FA_E, "fa9.2049.total") - b.v(FA_E, "fa9.2049.05.total") - b.v(FA_E, "fa9.2049.01.116") - b.vsum(
        FA_R, ["fa8.0049.03.116", "fa8.0049.03.117"])  # fmt: skip
    si = b.v(SF, sf("app2.total_expenditure.ii.c.2-interest_payments")) - b.v(
        SF, sf("app2.total_expenditure.ii.c.2.i-interest_on_loans_from_the_centre"))  # fmt: skip
    prop_in = m["r6"] + (m["r7_total"] - m["r6"]) + m["r7_states"] + m["r7x"]["G_CEN"] + m["r7x"]["G_STA"]
    inc_tax = d.income_taxes["G_CEN"] + d.income_taxes["G_STA"]
    benefits = b.s("R9a") + b.s("R10")
    other = b.s("R18")
    ev = gdi_evidence(
        property_received=prop_in.v,
        property_paid=(ui + si).v,
        income_taxes=inc_tax.v,
        benefits_paid=benefits,
        other_transfers_paid=other,
        required=required.v,
        variants=variants,
    )
    chosen = choose_variant(ev, R9B_VARIANTS_ALLOWED)
    best = min(ev, key=lambda e: abs(e.gap))
    for e in ev:
        ctx.log(
            f"R9b D2-5 evidence: variant {e.variant}: R9b {e.r9b:,.2f}, GG net distributive flows "
            f"{e.delivered:,.2f} "
            f"vs NAS {e.required:,.2f} (gap {e.gap:+,.2f})"
        )
    if best.variant not in R9B_VARIANTS_ALLOWED:  # cannot happen while D2-20 allows all three; kept as a guard
        ctx.warn(f"R9b: the best-fitting variant {best.variant} is not allowed; {chosen.variant} is written")
    ctx.log(
        f"R9b: variant {chosen.variant} written (DECISIONS D2-20 amends D2-5: 'none' is allowed and fits best, gap "
        f"{chosen.gap:+,.0f}); the Centre-only ({variants['centre_only']:,.2f}) and Centre + States "
        f"({variants['centre_and_states']:,.2f}) values are kept as memo rows of gov_r9b_sensitivity. NAD question "
        "and Checkpoint B flag."
    )
    ins = pids_of(m["r9_civil"], m["r9_defence"], m["r9_sta"], gdi, cfc, tp, sp, npt, ui, si, prop_in, inc_tax,
                  d.public_wage_key)  # fmt: skip
    pid = b.prov("R9b", "estimated", ins,
                 "Gap map R9b (S&M 2026 s.3.1.1 via DESIGN_REVIEW row 54): imputed OPS pension contributions "
                 "returned by "
                 f"households = Centre civil pensions (Union FA MH 2071.01 net of NPS and CGHS) x (1 - k/39), k = "
                 f"{int(f['k'])} years since 2005-06, + defence pensions (2071.02) unadjusted"
                 + ("; + States' pensions (R9 net) x the same factor (uniform k; the OPS/NPS State list is not in "
                    "clean data)" if chosen.variant == "centre_and_states" else "")
                 + ". Variant chosen by the DECISIONS D2-5 evidence test: GG net distributive flows implied by the "
                   "prior "
                 "(R6 + R7 + R7x + taxes' G<-T_PIT/T_CIT - GG interest paid outside GG (proxy: Union MH 2049 less "
                 "interest on reserve funds, less interest on 14-day treasury bills (MH 2049.01.116, paid to the "
                 "States) and less premium/interest received on market loans; States' interest less "
                 "interest on Central loans) - R9a - R10 - R18 + R9b) against NAS 2026 GG GDI - CFC - net taxes on "
                 f"production and imports; the variant with the smallest gap ({chosen.variant}) is written "
                 "(DECISIONS D2-5 as amended by D2-20, which allows 'none'; with 'none' no R9b entry exists and the "
                 "Centre-only and Centre + States values are a memo in satellite gov_r9b_sensitivity). A non-zero "
                 "variant would be split over groups by the public-sector wage key (the key of the CE it returns): "
                 "low.",
                 main=m["r9_civil"].pids[0],
                 notes="Parameters k (NPS start 2005-06) and career 39 years are from S&M 2026 s.3.1.1 as quoted in "
                       "docs/phase0/DESIGN_REVIEW.md row 54.")  # fmt: skip
    parts: list[tuple[str, float]] = []
    if chosen.variant in ("centre_only", "centre_and_states"):
        parts.append(("G_CEN", centre))
    if chosen.variant == "centre_and_states":
        parts.append(("G_STA", states))
    for gov, tot in parts:
        for g, val in split(tot, m["wage_key"]).items():
            b.add(gov, g, "R9b", "imputed_ops", val, pid, "estimated", "free", conf="low")
    rows = [
        {"series_id": "formula.k_years", "item": "k_years", "variant": None, "value": f["k"], "unit": "count"},
        {"series_id": "formula.factor", "item": "one_minus_k_over_39", "variant": None, "value": f["factor"],
         "unit": "ratio"},
        {"series_id": "formula.centre_civil", "item": "centre_civil_imputed", "variant": None, "value": f["civil"]},
        {"series_id": "formula.centre_defence", "item": "centre_defence_imputed", "variant": None,
         "value": f["defence"]},
        {"series_id": "formula.states_uniform_k", "item": "states_imputed_uniform_k", "variant": None, "value": states},
        {"series_id": "nas.required_net_distributive", "item": "nas_gdi_less_cfc_less_net_d2_d3", "variant": None,
         "value": required.v},
        {"series_id": "prior.property_income_received", "item": "r6_r7_r7x", "variant": None, "value": prop_in.v},
        {"series_id": "prior.interest_paid_proxy", "item": "interest_paid_outside_gg_proxy", "variant": None,
         "value": (ui + si).v},
        {"series_id": "prior.income_taxes", "item": "taxes_g_from_t_pit_t_cit", "variant": None, "value": inc_tax.v},
        {"series_id": "prior.benefits_paid", "item": "r9a_r10", "variant": None, "value": benefits},
        {"series_id": "prior.other_transfers_paid", "item": "r18", "variant": None, "value": other},
        {"series_id": "chosen", "item": f"chosen_{chosen.variant}", "variant": chosen.variant, "value": chosen.r9b},
        # memo (DECISIONS D2-20): the computed non-zero variants by government, not written as entries
        {"series_id": "memo.centre_only.g_cen", "item": "memo_r9b_g_cen", "variant": "centre_only", "value": centre},
        {"series_id": "memo.centre_and_states.g_cen", "item": "memo_r9b_g_cen", "variant": "centre_and_states",
         "value": centre},
        {"series_id": "memo.centre_and_states.g_sta", "item": "memo_r9b_g_sta", "variant": "centre_and_states",
         "value": states},
    ]  # fmt: skip
    for e in ev:
        rows += [
            {"series_id": f"variant.{e.variant}.r9b", "item": "r9b_total", "variant": e.variant, "value": e.r9b},
            {"series_id": f"variant.{e.variant}.delivered", "item": "gg_net_distributive_flows", "variant": e.variant,
             "value": e.delivered},
            {"series_id": f"variant.{e.variant}.gap", "item": "gap_vs_nas", "variant": e.variant, "value": e.gap},
            {"series_id": f"variant.{e.variant}.gdi", "item": "implied_gg_gdi", "variant": e.variant,
             "value": e.delivered + (gdi - required).v},
        ]  # fmt: skip
    b.sat(
        "gov_r9b_sensitivity",
        "R9b",
        rows,
        pid,
        "estimated",
        "R9b: formula, variants, the D2-5 GG disposable-income evidence and the D2-20 memo of the unwritten variants",
        ["item", "variant"],
    )
    m.update(r9b_chosen=chosen, r9b_ev=ev, gdi=gdi)


# =====================================================================================================
# control totals (targets read from clean data)
# =====================================================================================================


def _checks(b: Build) -> None:
    ctx, m = b.ctx, b.memo

    def chk(cid: str, desc: str, val: float, target: Q, tol: float) -> None:
        ctx.check(cid, desc, val, target.v, target_prov_id=target.pids[0], tol_abs=tol)

    afs_share = b.v(AFS, "afs.cfi_rev_receipts.state_s_share_excluded_from_the_consolidated_fund")
    sf_dev = b.v(SF, sf("app1.total_revenue.i.b-share_in_central_taxes"))
    kfi_dev = b.v(KFI, "kfi.a_1_3-state_s_share_in_union_taxes_and_duties.in.all_states_28")
    r1 = b.s("R1")
    chk("r1_vs_afs", "Devolution (R1) vs AFS States' share excluded from the Consolidated Fund", r1, afs_share, 0.05)
    chk(
        "r1_vs_rbi_sf",
        "Devolution (R1) vs RBI SF share in central taxes (States + UTs), 0.05%",
        r1,
        sf_dev,
        5e-4 * sf_dev.v,
    )
    chk("r1_vs_kfi", "Devolution (R1) vs FC16 KFI A.1.3 (28 States), 0.05%", r1, kfi_dev, 5e-4 * kfi_dev.v)
    treas = (b.s("R2", comp="fc_grants") + b.s("R2", comp="css_and_other") + b.s("T2b", comp="compensation_grants")
             + b.s("R2k", comp="igas2_capital"))  # fmt: skip
    chk(
        "grants_state_receipts",
        "Treasury grants (R2 + T2b(i) + R2k IGAS-2) vs RBI SF grants from the Centre",
        treas,
        m["sf_grants"],
        CHECK_TOL,
    )
    chk(
        "h9_union_net_releases",
        "Union MH 3601 + 3602 net releases vs RBI SF grants received (0.1%)",
        (m["n3601"] + m["n3602"]).v,
        m["sf_grants"],
        1e-3 * m["sf_grants"].v,
    )
    chk(
        "h9_igas2_plus_fc_local",
        "IGAS-2 State Government + FC local-body/health grants vs MH 3601 net releases (0.1%)",
        (m["igas_state"] + m["fc_local"]).v,
        m["n3601"],
        1e-3 * m["n3601"].v,
    )
    chk(
        "css_outside_vs_igas2_others",
        "Outside-treasury CSS (St 18 - MH 3601.06) vs IGAS-2 'Others' grantees (5%)",
        m["outside"].v,
        m["others_tot"],
        0.05 * m["others_tot"].v,
    )
    r6_t = b.v(RBI_T, "r6.surplus_received_by_centre_cash.current")
    chk(
        "r6_vs_rbi_timing",
        "RBI surplus (R6, FA) vs RBI surplus received by the Centre (RBI series)",
        b.s("R6"),
        r6_t,
        0.01,
    )
    chk(
        "r6_r7_vs_fa_0050",
        "R6 + Union R7 vs Union FA MH 0050 total",
        b.s("R6") + b.s("R7", row="G_CEN"),
        m["r7_total"],
        0.01,
    )
    rb = b.v(RB, "rb.ntr.total.total_dividends_and_profits")
    chk(
        "r6_r7_vs_receipt_budget",
        "R6 + Union R7 (FA) vs Receipt Budget dividends and profits (Rs 20 crore)",
        b.s("R6") + b.s("R7", row="G_CEN"),
        rb,
        20.0,
    )
    chk(
        "r9_states_vs_kfi",
        "States' gross pensions (RBI SF) vs FC16 KFI B.1.b (28 States), 1%",
        m["r9_sta"].v + b.v(PFRDA, "m7d.annual_contribution_employer.state_govt.current").v,
        m["kfi_pen"],
        0.01 * m["kfi_pen"].v,
    )
    nas_gfce = b.v(NAS + "s1_14", "s1_14.gg.final_consumption_expenditure.current")
    chk("c2a_total_vs_nas", "GFCE (all C2a) vs NAS 1.14 GG FCE", b.s("C2a"), nas_gfce, 1.0)
    pay, rec, _, _ = m["k6_row"]
    chk(
        "k6_row_gg_net",
        "K6 GG capital transfers with the RoW, receipts - payments, vs NAS 6.1",
        rec.v - pay.v,
        m["gg_net"],
        0.01,
    )
    dom = sum(e["value"] for e in b.entries if e["ref"] == "K6" and e["col"] in ("K_GCEN", "K_GSTA"))
    chk(
        "k6_vs_cofog",
        "GG capital transfers paid (K6, incl. RoW) vs NAS 4.2 COFOG total (5%)",
        dom,
        m["k6_total"],
        0.05 * m["k6_total"].v,
    )
    k3a = b.s("K3a")
    chk("k3a_vs_nas_saving", "K3a priors (G_CEN + G_STA) vs NAS 1.9 GG saving", k3a, m["k3"], CHECK_TOL)
    cur = b.v(NAS + "s4_2", "s4_2.current_transfer.total.current")
    # audit BS-5 (government-31): declared as a constraint once PM-KISAN moved from taxes' P10a to R10 (government-
    # 30): the prior is then -1.4% of NAS 4.2, and balancing can no longer push R10 10% past it
    pid_cur = b.prov(
        "R10",
        "official",
        list(cur.pids),
        "NAS 2026 Statement 4.2 (GG expenditure by COFOG function), current transfers, total, 2023-24, latest "
        "vintage, as published: the control total of GG current transfers to households and corporations "
        "(R9a + R10 + R18; government-9 shows GFCE excl. CFC and subsidies match NAS 4.2, so current transfers "
        "carry the rest). Band +-5% (scope: NAS 4.2 may include small transfers the SAM books elsewhere).",
    )
    b.cons.append(constraint(
        "gov.cofog.current_transfers", "R10", [*HH, "E_NFPU", "E_NFPR", "E_INSP"], ["G_CEN", "G_STA"], cur.v,
        prov_id=pid_cur, kind="band", tol_rel=0.05, refs=["R9a", "R10", "R18"],
        description="GG current transfers R9a + R10 + R18 near NAS 4.2 COFOG current transfers (band 5%)",
    ))  # fmt: skip
    chk(
        "cofog_current_transfers",
        "R9a + R10 + R18 vs NAS 4.2 COFOG current transfers (5%; scope differs, logged)",
        b.s("R9a") + b.s("R10") + b.s("R18"),
        cur,
        0.05 * cur.v,
    )
    ch = m["r9b_chosen"]
    chk(
        "gg_gdi_sketch",
        f"GG GDI implied by the prior with R9b {ch.variant} vs NAS 1.14 (5%)",
        ch.delivered + (m["gdi"].v - ch.required),
        m["gdi"],
        0.05 * m["gdi"].v,
    )
