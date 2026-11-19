"""RBI Flow of Funds (FSF 2023-24) extraction and pairwise reconciliation (plan s.2.6-2.7). Pure functions.

FSF instrument markets do not clear: holders and issuers report different amounts for the same flow
(equity is off by Rs 15.8 lakh crore). So for each instrument one side is the control (params.CONTROL):
every domestic pair (holder H, issuer C) gets the control side's report X(H, C), and both H's asset and
C's liability take that one value. Pairs with households or the rest of the world are dropped here and
rebuilt from NAS 5.3 and the BoP (households.py, row.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl

from pipeline.sam.blocks.capital_financial import params as P
from pipeline.sam.framework import SamError


def sam_instrument(fsf_instr: str, issuer_code: str) -> str:
    """FSF instrument (+ issuer) -> SAM instrument account (plan s.2.7 Step A)."""
    if fsf_instr == "f21":
        return "I_CURR"
    if fsf_instr == "f22_f29":
        return "I_SSAV" if issuer_code in P.GG_CODES else "I_DEPO"
    if fsf_instr == "f3":
        return "I_GSEC" if issuer_code in P.GG_CODES else "I_CBND"
    if fsf_instr == "f4":
        return "I_LOAN"
    if fsf_instr == "f51":
        return "I_EQTY"
    if fsf_instr == "f52":
        return "I_MFUN"
    if fsf_instr in P.OWN_INSTRUMENTS:
        return "I_OTHR"
    if fsf_instr in P.INPE_INSTRUMENTS:
        return "I_INPE"
    raise SamError(f"FSF instrument {fsf_instr!r} has no SAM instrument")


def abs_share(total: float, reported: dict[str, float]) -> dict[str, float] | None:
    """Allocate a control total over units with reported values of any sign (plan s.2.0):
    x_i = r_i + (T - sum r) * |r_i| / sum |r|. None when every report is zero (caller applies a default)."""
    s = sum(reported.values())
    a = sum(abs(v) for v in reported.values())
    if a == 0:
        return None
    return {k: v + (total - s) * abs(v) / a for k, v in sorted(reported.items())}


# ---------------------------------------------------------------------------------------------------
# the report table
# ---------------------------------------------------------------------------------------------------


def reports(fsf: pl.DataFrame) -> pl.DataFrame:
    """FSF 2023-24 transactions of the leaf statements (params.SUB_ACCOUNT) as one row per
    (statement, side, FSF instrument, leaf counterparty), plus an `unallocated` row = 'all' minus the
    leaf counterparties (for f52 and the f6 components, published without counterparties, that is all).
    Columns: sub, account, code, side, fsf_instr, cp, value, instrument, holder_code, issuer_code, prov_id."""
    df = fsf.filter(
        (pl.col("dim_other") == "measure=transaction")
        & pl.col("institution").is_in(list(P.SUB_ACCOUNT))
        & pl.col("instrument").is_in(list(P.READ_INSTRUMENTS))
    )
    rows: list[dict] = []
    keys = (
        df.select("institution", "side", "instrument")
        .unique(maintain_order=True)
        .sort("institution", "side", "instrument")
    )
    for sub, side, fi in keys.iter_rows():
        g = df.filter((pl.col("institution") == sub) & (pl.col("side") == side) & (pl.col("instrument") == fi))
        by_cp = {r["counterparty"]: (float(r["value"]), r["prov_id"]) for r in g.iter_rows(named=True)}
        if "all" not in by_cp:
            raise SamError(f"FSF {sub} {side} {fi}: no 'all' row")
        total, pid = by_cp["all"]
        leaf = 0.0
        for cp in P.LEAF_CPS:
            if cp in by_cp and by_cp[cp][0] != 0.0:
                rows.append(_rep(sub, side, fi, cp, by_cp[cp][0], by_cp[cp][1]))
                leaf += by_cp[cp][0]
        rest = total - leaf
        if abs(rest) > 1e-6:
            rows.append(_rep(sub, side, fi, P.UNALLOCATED, rest, pid))
    return pl.DataFrame(rows, schema=_REP_SCHEMA, orient="row").sort("sub", "side", "fsf_instr", "cp")


_REP_SCHEMA = {
    "sub": pl.String(),
    "account": pl.String(),
    "code": pl.String(),
    "side": pl.String(),
    "fsf_instr": pl.String(),
    "cp": pl.String(),
    "value": pl.Float64(),
    "instrument": pl.String(),
    "holder_code": pl.String(),
    "issuer_code": pl.String(),
    "prov_id": pl.String(),
}


def _rep(sub: str, side: str, fi: str, cp: str, value: float, pid: str) -> dict:
    code = P.SUB_CODE[sub]
    holder, issuer = (code, cp) if side == "assets" else (cp, code)
    return {
        "sub": sub,
        "account": P.SUB_ACCOUNT[sub],
        "code": code,
        "side": side,
        "fsf_instr": fi,
        "cp": cp,
        "value": value,
        "instrument": sam_instrument(fi, issuer),
        "holder_code": holder,
        "issuer_code": issuer,
        "prov_id": pid,
    }


def statement_totals(fsf: pl.DataFrame) -> pl.DataFrame:
    """Published 'Gross financial assets / liabilities' (instrument 'total') of each leaf statement."""
    df = fsf.filter(
        (pl.col("dim_other") == "measure=transaction")
        & pl.col("institution").is_in(list(P.SUB_ACCOUNT))
        & (pl.col("instrument") == "total")
        & (pl.col("counterparty") == "all")
    )
    return df.select(pl.col("institution").alias("sub"), "side", "value", "prov_id").sort("sub", "side")


# ---------------------------------------------------------------------------------------------------
# reconciliation
# ---------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Pair:
    """One reconciled domestic flow: `holder` acquires `instrument` issued by `issuer` (Rs crore)."""

    instrument: str
    holder: str
    issuer: str
    value: float
    control: str  # 'holder' or 'issuer': whose report the value is
    rule: str  # published | ofc_key | unnamed_default | insurer_equity | mf_holder_key | centre_state_net_k8e
    reporter: str  # the leaf statement whose report it came from ('' for keyed totals)
    cp: str  # the counterparty code in that report

    @property
    def keyed(self) -> bool:
        return self.rule not in ("published", "centre_state_net_k8e")


@dataclass
class Reconciliation:
    pairs: list[Pair] = field(default_factory=list)
    dropped: list[dict] = field(default_factory=list)  # control-side amounts not written (why, value)
    notes: list[str] = field(default_factory=list)


def ofc_key(rep: pl.DataFrame, fsf_instr: str, side: str, cp: str, exclude: tuple[str, ...] = ()) -> dict[str, float]:
    """Reports of the OFC sub-sectors on `side` for `fsf_instr` with counterparty `cp`, summed by SAM account:
    the key that splits a counterparty named only `fc_ofc` (plan s.2.7 Step B)."""
    g = rep.filter(
        pl.col("sub").is_in([s for s in P.OFC_SUBS if s not in exclude])
        & (pl.col("side") == side)
        & (pl.col("fsf_instr") == fsf_instr)
        & (pl.col("cp") == cp)
    )
    out: dict[str, float] = {}
    for r in g.iter_rows(named=True):
        out[r["account"]] = out.get(r["account"], 0.0) + r["value"]
    return dict(sorted(out.items()))


def reconcile(
    rep: pl.DataFrame,
    *,
    insurer_equity: tuple[float, dict[str, float]] | None,
    centre_state_k8e: float,
    mf_nonhh_total: float,
    control: dict[str, str] | None = None,
) -> Reconciliation:
    """Every domestic non-household pair X(H, C) from the control side's reports (plan s.2.7 Steps B, C, F).

    insurer_equity: (total, issuer mix by counterparty code) that replaces insurers' F51 report (Step C1);
    centre_state_k8e: government's K8e value, netted out of the Centre->States loan (Step C4);
    mf_nonhh_total: the MF sector's net sales to non-household holders (issuer total less NAS households);
    control: the control side by instrument (default params.CONTROL; another one only for the plan T24
    sensitivity table, never for entries)."""
    control = P.CONTROL if control is None else control
    out = Reconciliation()
    for r in rep.sort("sub", "side", "fsf_instr", "cp").iter_rows(named=True):
        inst = r["instrument"]
        if r["sub"] == "hh":
            continue  # households' own statement is replaced by NAS 5.3 (households.py)
        if inst in ("I_OTHR", "I_INPE", "I_MFUN"):
            continue  # I_OTHR: own reports; I_INPE: households only (NAS); I_MFUN: mf_pairs below
        role = "holder" if r["side"] == "assets" else "issuer"
        if control[inst] != role:
            continue
        if r["sub"] == "fc_ofc_icpf_ins" and r["fsf_instr"] == "f51" and r["side"] == "assets" and insurer_equity:
            continue  # replaced below (Step C1)
        out.pairs += _map_counterparty(rep, r, r["value"], "published", out)
    if insurer_equity is not None:
        total, mix = insurer_equity
        w = {cp: v for cp, v in mix.items() if cp not in ("hh", "row", P.UNALLOCATED, "other_resident")}
        s = sum(w.values())
        if s == 0:
            raise SamError("insurers' equity rule: the MF issuer mix has no domestic counterparty")
        base = rep.filter((pl.col("sub") == "fc_ofc_icpf_ins") & (pl.col("fsf_instr") == "f51")).row(0, named=True)
        for cp, v in sorted(w.items()):
            r = {**base, "side": "assets", "cp": cp, "holder_code": "fc_ofc", "issuer_code": cp}
            out.pairs += _map_counterparty(rep, r, total * v / s, "insurer_equity", out)
    out.pairs = _net_centre_state(out.pairs, centre_state_k8e)
    out.pairs += mf_pairs(rep, mf_nonhh_total, out)
    return out


def _map_counterparty(rep: pl.DataFrame, r: dict, value: float, rule: str, out: Reconciliation) -> list[Pair]:
    inst, cp, own = r["instrument"], r["cp"], r["account"]
    role = "holder" if r["side"] == "assets" else "issuer"
    opposite = "liabilities" if r["side"] == "assets" else "assets"

    def pair(other: str, v: float, rl: str) -> Pair:
        h, c = (own, other) if role == "holder" else (other, own)
        return Pair(inst, h, c, v, role, rl, r["sub"], cp)

    if cp in ("hh", "row"):
        out.dropped.append({"why": f"counterparty_{cp}", "instrument": inst, "account": own, "value": value})
        return []
    if cp in P.CP_ACCOUNT:
        return [pair(P.CP_ACCOUNT[cp], value, rule)]
    if cp == "fc_ofc":
        key = ofc_key(rep, r["fsf_instr"], opposite, r["code"])
        split = abs_share(value, key)
        if split is None:
            out.notes.append(
                f"{r['sub']} {r['side']} {r['fsf_instr']} -> fc_ofc {value:,.2f}: OFC key all zero, "
                f"default {P.OFC_DEFAULT}"
            )
            return [pair(P.OFC_DEFAULT, value, "ofc_key")]
        return [pair(k, v, "ofc_key" if rule == "published" else rule) for k, v in split.items() if v != 0.0]
    # other_resident / unallocated
    default = P.UNNAMED_DEFAULT.get(inst)
    if default is None:
        out.dropped.append({"why": f"unnamed_{cp}", "instrument": inst, "account": own, "value": value})
        return []
    return [pair(default, value, "unnamed_default")]


def _net_centre_state(pairs: list[Pair], k8e: float) -> list[Pair]:
    """Step C4: FSF Centre -> States loans include the GST back-to-back recovery that government writes as
    K8e; the `dom` pair is FSF - K8e so that the sum over refs equals FSF."""
    out, hit = [], 0
    for p in pairs:
        if p.instrument == "I_LOAN" and p.holder == "K_GCEN" and p.issuer == "K_GSTA" and p.rule == "published":
            p = Pair(
                p.instrument, p.holder, p.issuer, p.value - k8e, p.control, "centre_state_net_k8e", p.reporter, p.cp
            )
            hit += 1
        out.append(p)
    if hit != 1:
        raise SamError(f"Centre -> States loan pair found {hit} times in the FSF Centre statement (expected 1)")
    return out


def mf_pairs(rep: pl.DataFrame, nonhh_total: float, out: Reconciliation) -> list[Pair]:
    """I_MFUN (Step A, issuer control): the MF sector's net sales, less the NAS household part, split over the
    other domestic holders by their own F52 reports (absolute-share rule). SFC/SIDC holdings are excluded
    (Step C3); holders abroad do not report F52."""
    g = rep.filter(
        (pl.col("fsf_instr") == "f52")
        & (pl.col("side") == "assets")
        & ~pl.col("sub").is_in(["hh", *P.MF_HOLDER_EXCLUDED])
    )
    held: dict[str, float] = {}
    for r in g.iter_rows(named=True):
        held[r["account"]] = held.get(r["account"], 0.0) + r["value"]
    split = abs_share(nonhh_total, held)
    if split is None:
        raise SamError("MF units: no domestic non-household holder reports F52")
    ex = rep.filter((pl.col("fsf_instr") == "f52") & pl.col("sub").is_in(list(P.MF_HOLDER_EXCLUDED)))
    for r in ex.iter_rows(named=True):
        out.dropped.append(
            {"why": "mf_holder_excluded", "instrument": "I_MFUN", "account": r["account"], "value": r["value"]}
        )
    return [
        Pair("I_MFUN", k, "K_MUTF", v, "issuer", "mf_holder_key", "fc_ofc_mf", P.UNALLOCATED)
        for k, v in split.items()
        if v != 0.0
    ]


# ---------------------------------------------------------------------------------------------------
# own reports (I_OTHR) and the per-sector nets used by the K9 decomposition
# ---------------------------------------------------------------------------------------------------


def own_reports(rep: pl.DataFrame) -> dict[tuple[str, str, str], float]:
    """(account, side, 'f81'|'f89') -> each sector's own report net of its household- and RoW-counterparty
    cells (those flows are rebuilt from NAS 5.3 and the BoP). Households' own statement is not used."""
    g = rep.filter(pl.col("fsf_instr").is_in(list(P.OWN_INSTRUMENTS)) & ~pl.col("cp").is_in(["hh", "row"]))
    g = g.filter(pl.col("sub") != "hh")
    out: dict[tuple[str, str, str], float] = {}
    for r in g.iter_rows(named=True):
        k = (r["account"], r["side"], r["fsf_instr"])
        out[k] = out.get(k, 0.0) + r["value"]
    return dict(sorted(out.items()))


def unread_cells(rep: pl.DataFrame) -> list[dict]:
    """FSF report cells that no reconciliation step reads (verification V-CF-4): every I_INPE cell of a
    non-household statement (holder control, households only, plan s.2.7 Step A) and every F52 liability
    outside the MF sector (I_MFUN is keyed on the MF sector's own net sales). `fate` says whether a NAS 5.3
    household line replaces the cell (params.INPE_NAS_REPLACED) or it is not written and falls into K9 of
    `account`. SFC/SIDC F52 holdings are logged with the reconciliation (mf_holder_excluded)."""
    g = rep.filter(
        (pl.col("sub") != "hh")
        & (
            (pl.col("instrument") == "I_INPE")
            | ((pl.col("instrument") == "I_MFUN") & (pl.col("side") == "liabilities") & (pl.col("sub") != "fc_ofc_mf"))
        )
    )
    out = []
    for r in g.sort("sub", "side", "fsf_instr", "cp").iter_rows(named=True):
        replaced = r["side"] == "liabilities" and (r["sub"], r["fsf_instr"]) in P.INPE_NAS_REPLACED
        out.append(
            {
                "sub": r["sub"],
                "account": r["account"],
                "side": r["side"],
                "fsf_instr": r["fsf_instr"],
                "cp": r["cp"],
                "value": r["value"],
                "fate": "replaced_by_nas_5_3" if replaced else "k9",
            }
        )
    return out


def category_nets(rep: pl.DataFrame, totals: pl.DataFrame) -> dict[str, dict[str, float]]:
    """Per SAM account, the FSF net financial transactions (assets - liabilities) split into `total`
    (published statement totals) and `<layer>|<SAM instrument>` for every cell read, where layer is `hh`
    (household-counterparty cells; for the household statement, every cell), `row` (RoW-counterparty cells)
    or `dom` (all other cells); `unwritten` = total - the rest (FSF items this block never reads: 'other',
    NEC, monetary gold and SDRs, printed-total-only lines)."""
    out: dict[str, dict[str, float]] = {}

    def add(acct: str, key: str, v: float) -> None:
        d = out.setdefault(acct, {})
        d[key] = d.get(key, 0.0) + v

    for r in totals.iter_rows(named=True):
        add(P.SUB_ACCOUNT[r["sub"]], "total", r["value"] if r["side"] == "assets" else -r["value"])
    for r in rep.iter_rows(named=True):
        v = r["value"] if r["side"] == "assets" else -r["value"]
        layer = "row" if r["cp"] == "row" else "hh" if (r["cp"] == "hh" or r["sub"] == "hh") else "dom"
        add(r["account"], f"{layer}|{r['instrument']}", v)
    for d in out.values():
        d["unwritten"] = d.get("total", 0.0) - sum(v for k, v in d.items() if k != "total")
    return dict(sorted(out.items()))


def dual_reports(rep: pl.DataFrame) -> pl.DataFrame:
    """Every (SAM instrument, holder code, issuer code) with the holder's and the issuer's report, at FSF
    sector-code level (the s.2.6 evidence). Columns: instrument, holder, issuer, holder_report, issuer_report."""
    rows: dict[tuple[str, str, str], list[float]] = {}
    for r in rep.iter_rows(named=True):  # the household statement reports as a holder and a borrower too
        k = (r["instrument"], r["holder_code"], r["issuer_code"])
        slot = rows.setdefault(k, [0.0, 0.0])
        slot[0 if r["side"] == "assets" else 1] += r["value"]
    data = [
        {"instrument": k[0], "holder": k[1], "issuer": k[2], "holder_report": v[0], "issuer_report": v[1]}
        for k, v in sorted(rows.items())
    ]
    return pl.DataFrame(
        data,
        schema={
            "instrument": pl.String(),
            "holder": pl.String(),
            "issuer": pl.String(),
            "holder_report": pl.Float64(),
            "issuer_report": pl.Float64(),
        },
        orient="row",
    )
