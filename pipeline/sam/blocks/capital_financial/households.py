"""Households' financial transactions (K7a, K8a) from NAS 5.3, and their counterparties (K7b `hh_cp`).

NAS 2026 Statement 5.3 is the control for households (plan s.2.8). Each line maps to one SAM instrument
(component names frozen by XR-19). The counterparty of each line is found from the counterparties' own FSF
statements (issuer side for deposits, equity and G-secs; lender side for loans); the FSF household
statement is never used for counterparty values (gap map K7b).
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from pipeline.sam.blocks.capital_financial import params as P
from pipeline.sam.blocks.capital_financial.fsf import abs_share
from pipeline.sam.framework import SamError

# NAS 5.3 asset lines: (K7a component, SAM instrument, series stems summed; PPF is special)
ASSET_LINES = (
    ("currency", "I_CURR", ("currency",)),
    ("banks", "I_DEPO", ("with_banks",)),
    ("coop_banks", "I_DEPO", ("with_co_operative_banks_and_societies",)),
    ("nonbank_deposits", "I_DEPO", ("with_non_banking_companies",)),
    ("trade_debt", "I_OTHR", ("trade_debt_net",)),
    # shares and debentures other than MF units = the three NAS sub-lines (= shares_and_debentures - MF)
    (
        "shares_debentures",
        "I_EQTY",
        (
            "corporate_companies_shares_debentures_hybrid_instruments_in",
            "co_operative_banks_and_societies",
            "secondary_markets_net_investments",
        ),
    ),
    ("mutual_funds", "I_MFUN", ("mutual_funds",)),
    ("gsec", "I_GSEC", ("investment_in_government_securities",)),
    ("small_savings", "I_SSAV", ("investment_in_small_savings_etc",)),
    ("ppf", "I_SSAV", ()),  # union_fiscal_nssf nssf.ppf.additions (moved out of PF & pension)
    ("life_insurance", "I_INPE", ("life_insurance_funds",)),
    ("postal_insurance", "I_INPE", ("postal_insurance",)),
    ("state_insurance", "I_INPE", ("state_insurance",)),
    ("pf_pension", "I_INPE", ("provident_and_pension_funds",)),  # less PPF
)
# NAS 5.3 liability lines (K8a components, XR-19)
LIABILITY_LINES = (
    ("banks", "bank_advances"),
    ("coop_banks", "loans_and_advances_by_co_operative_banks_and_societies"),
    ("nbfc", "loans_by_financial_corporations_and_non_banking_companies"),
    ("insurers", "loans_from_insurance_corporations"),
    ("government", "loans_and_advances_from_government"),
)
COOP_SHARES = "co_operative_banks_and_societies"  # the co-operative share sub-line goes to K_BANK directly


@dataclass(frozen=True)
class Line:
    component: str
    instrument: str
    value: float
    prov_ids: tuple[str, ...]
    derived: bool  # arithmetic beyond pure aggregation (PF & pension less PPF)


@dataclass(frozen=True)
class Posting:
    """A household-facing counterpart: `account` incurs a liability (side 'liability': K <- I) or acquires
    an asset (side 'asset': I <- K) in `instrument`, mirroring a NAS 5.3 line."""

    account: str
    instrument: str
    side: str
    value: float
    source: str  # the K7a/K8a component(s) it mirrors
    key: str  # how the counterparty was found


def counterparty_key(
    rep: pl.DataFrame,
    fsf_instr: str,
    side: str,
    *,
    subs: list[str] | None = None,
    issuer_codes: tuple[str, ...] | None = None,
) -> dict[str, float]:
    """Counterparties' own reports with counterparty = households, by SAM account."""
    g = rep.filter((pl.col("fsf_instr") == fsf_instr) & (pl.col("side") == side) & (pl.col("cp") == "hh"))
    g = g.filter(pl.col("sub") != "hh")
    if subs is not None:
        g = g.filter(pl.col("sub").is_in(subs))
    if issuer_codes is not None:
        g = g.filter(pl.col("code").is_in(list(issuer_codes)))
    out: dict[str, float] = {}
    for r in g.iter_rows(named=True):
        out[r["account"]] = out.get(r["account"], 0.0) + r["value"]
    return dict(sorted(out.items()))


def fsf_value(rep: pl.DataFrame, sub: str, side: str, fsf_instr: str, cp: str) -> float:
    g = rep.filter(
        (pl.col("sub") == sub) & (pl.col("side") == side) & (pl.col("fsf_instr") == fsf_instr) & (pl.col("cp") == cp)
    )
    return float(g["value"].sum())


def postings(
    assets: list[Line], liabilities: list[Line], rep: pl.DataFrame, gpf: dict[str, float], coop_shares: float
) -> list[Posting]:
    """hh_cp postings for every K7a / K8a line (plan s.2.8 table). `gpf`: the Centre's and States' provident-
    fund liabilities from their FSF statements (f6_pf 'all'), which households hold. `coop_shares`: the NAS
    co-operative shares sub-line of shares_debentures (issued by co-operative banks and societies: K_BANK)."""
    a = {ln.component: ln.value for ln in assets}
    li = {ln.component: ln.value for ln in liabilities}
    out: list[Posting] = []

    def post(acct: str, inst: str, side: str, v: float, src: str, key: str) -> None:
        if v != 0.0:
            out.append(Posting(acct, inst, side, v, src, key))

    L = "liability"
    post("K_RBI", "I_CURR", L, a["currency"], "currency", "RBI issues currency")
    # deposits: the three NAS lines together, split by the deposit-takers' own reports (non-GG issuers)
    dep = a["banks"] + a["coop_banks"] + a["nonbank_deposits"]
    key = counterparty_key(
        rep, "f22_f29", "liabilities", issuer_codes=("fc_rbi", "fc_odc", "fc_ofc", "nfc_pub", "nfc_pvt")
    )
    for k, v in _split(dep, key, "deposits").items():
        post(k, "I_DEPO", L, v, "banks+coop_banks+nonbank_deposits", "FSF issuers' F22/F29 liabilities to hh")
    post("K_NFPR", "I_OTHR", L, a["trade_debt"], "trade_debt", "FSF hh F81 asset: counterparty nfc_pvt only")
    # equity: co-operative shares to K_BANK; the rest by issuers' F51 liabilities to households
    post("K_BANK", "I_EQTY", L, coop_shares, "shares_debentures (co-operative shares)", "NAS co-operative sub-line")
    eq_key = counterparty_key(rep, "f51", "liabilities")
    for k, v in _split(a["shares_debentures"] - coop_shares, eq_key, "equity").items():
        post(k, "I_EQTY", L, v, "shares_debentures", "FSF issuers' F51 liabilities to hh")
    post("K_MUTF", "I_MFUN", L, a["mutual_funds"], "mutual_funds", "MF units")
    sta = fsf_value(rep, "gg_sta", "liabilities", "f3", "hh")
    post("K_GSTA", "I_GSEC", L, sta, "gsec", "FSF States' F3 liability to hh")
    post("K_GCEN", "I_GSEC", L, a["gsec"] - sta, "gsec", "remainder (retail G-secs, SGBs are Central)")
    post("K_GCEN", "I_SSAV", L, a["small_savings"] + a["ppf"], "small_savings+ppf", "NSSF (Union public account)")
    post("K_INSP", "I_INPE", L, a["life_insurance"], "life_insurance", "life insurers")
    post("K_GCEN", "I_INPE", L, a["postal_insurance"], "postal_insurance", "Postal Life Insurance (Union)")
    post(
        "K_GSTA",
        "I_INPE",
        L,
        a["state_insurance"],
        "state_insurance",
        "default: State Government insurance funds (plan s.6.4 Q2)",
    )
    post("K_GCEN", "I_INPE", L, gpf["gg_cen"], "pf_pension", "FSF Centre f6_pf liability (GPF)")
    post("K_GSTA", "I_INPE", L, gpf["gg_sta"], "pf_pension", "FSF States f6_pf liability (State PFs)")
    post(
        "K_INSP",
        "I_INPE",
        L,
        a["pf_pension"] - gpf["gg_cen"] - gpf["gg_sta"],
        "pf_pension",
        "remainder: EPFO, NPS, pension funds",
    )
    # loans (K8a): government by FSF hh F4 counterparties, insurers to K_INSP, the rest by lenders' reports
    g_cen = fsf_value(rep, "hh", "liabilities", "f4", "gg_cen")
    g_sta = fsf_value(rep, "hh", "liabilities", "f4", "gg_sta")
    for k, v in _split(li["government"], {"K_GCEN": g_cen, "K_GSTA": g_sta}, "government loans").items():
        post(k, "I_LOAN", "asset", v, "government", "FSF hh F4 liabilities to gg_cen / gg_sta")
    post("K_INSP", "I_LOAN", "asset", li["insurers"], "insurers", "insurers")
    lenders = [s for s in P.SUB_ACCOUNT if s.startswith("fc_") and s != "fc_ofc_icpf_ins"]
    rest = li["banks"] + li["coop_banks"] + li["nbfc"]
    for k, v in _split(rest, counterparty_key(rep, "f4", "assets", subs=lenders), "loans").items():
        post(k, "I_LOAN", "asset", v, "banks+coop_banks+nbfc", "FSF FC lenders' F4 assets on hh (SAM boundary)")
    return out


def _split(total: float, key: dict[str, float], what: str) -> dict[str, float]:
    split = abs_share(total, key)
    if split is None:
        raise SamError(f"household counterparties for {what}: the FSF key is all zero")
    return split


def read_lines(ctx, value) -> tuple[list[Line], list[Line], float]:
    """NAS 5.3 lines as K7a/K8a lines. `value(dataset, series)` -> (value, prov_id). Returns
    (asset lines, liability lines, the co-operative shares sub-line)."""
    assets: list[Line] = []
    coop_v = 0.0
    ppf, ppf_pid = value(P.NSSF, "nssf.ppf.additions")
    for comp, inst, stems in ASSET_LINES:
        if comp == "ppf":
            assets.append(Line(comp, inst, ppf, (ppf_pid,), False))
            continue
        vals = [value(P.NAS53, f"s5_3.{s}.current") for s in stems]
        v = sum(x for x, _ in vals)
        pids = tuple(sorted({p for _, p in vals}))
        if comp == "pf_pension":
            assets.append(Line(comp, inst, v - ppf, tuple(sorted({*pids, ppf_pid})), True))
            continue
        if comp == "shares_debentures":
            coop_v = dict(zip(stems, [x for x, _ in vals], strict=True))[COOP_SHARES]
        assets.append(Line(comp, inst, v, pids, False))
    liabilities = []
    for comp, stem in LIABILITY_LINES:
        v, pid = value(P.NAS53, f"s5_3.{stem}.current")
        liabilities.append(Line(comp, "I_LOAN", v, (pid,), False))
    return assets, liabilities, coop_v
