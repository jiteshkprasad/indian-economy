"""Shared constants and small pure helpers of the rest_of_world block (no data access here).

Everything in this module is either a stated rule (a code mapping, a dataset name, a vintage the plan
names) or a pure function tested in tests/sam/test_sam_rest_of_world.py on small fixtures.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pipeline.sam.framework import SamError

# --- clean datasets read ----------------------------------------------------------------------------
NAS61 = "mospi_nas_2026_s6_1"  # NAS 2026 Statement 6.1: external transactions (the control totals)
NAS19 = "mospi_nas_2026_s1_9"  # NAS 2026 Statement 1.9 (net capital inflow; reinvested earnings memo)
BPM6 = "external_sector_bop_bpm6_annual"  # RBI HBS BoP, BPM6 presentation (T127), FY, Rs crore
BPM6Q = "external_sector_bop_bpm6_quarterly"
BOP_OLD = "external_sector_bop_overall_annual"  # RBI HBS BoP, old (functional) presentation
INVIS = "external_sector_invisibles_annual"
NRI = "external_sector_nri_deposits"
REMIT = "external_sector_remittance_survey"
FLA = "external_sector_fla_census"
ECB = "external_sector_ecb_monthly_2324"
FX = "external_sector_fx_inr_usd"
FSF = "rbi_financial_accounts_fsf_balance_sheets"
T107 = "rbi_financial_accounts_hbs_gsec_ownership"
RTP = "rbi_banking_corporate_rtp_banks"
RBI_AR = "rbi_banking_corporate_rbi_accounts"
FA_EXP = "union_fiscal_fa_expenditure"
FA_REC = "union_fiscal_fa_receipts"
SF_APP = "state_fiscal_rbi_sf_appendices"
SEBI_FPI = "finsector_markets_sebi_foreign"
SUT_SUPPLY = "io_tables_sut_supply"
LRS = "external_sector_lrs_outward"
IMTS_FY = "trade_satellites_imf_imts_fy"
COMTRADE_FY = "trade_satellites_comtrade_fy_2324"
BATIS = "trade_satellites_batis_2023_2024"
ITES = "external_sector_ites_survey"

# --- vintages named by the plan (explicit choices; stated in every method text that uses them) ----
LATEST = "latest"  # NAS 2026 (31 Aug 2026) and HBS BoP (31 Jul 2026) carry one vintage for 2023-24 today
V_FLA = "2024-10-11"  # FLA census 2023-24 round: the only round with end-March 2024 sector detail
V_FSF = "2026-01-21"  # RBI FSF (old base): keys only, never levels
V_RTP = "2025-12-29"  # RBI Report on Trend and Progress 2024-25 (revised 2023-24 figures)
V_RBI_AR = "2025-05-29"  # RBI Annual Report 2024-25 (2023-24 column; identical to the 2024-05-30 release)
V_REMIT = "2025-03-19"  # RBI remittances survey, 2023-24 round (external_sector-13, -20)
STOCK_DATES = ("2023-03-31", "2024-03-31")  # opening and closing stocks of FY 2023-24

# FSF counterparty code -> SAM institution account (ACCOUNT_STRUCTURE s.7; CROSS_REVIEW XR-6: E_BANK = FSF ODC)
FSF_TO_SAM: dict[str, str] = {
    "nfc_pvt": "E_NFPR",
    "nfc_pub": "E_NFPU",
    "fc_rbi": "E_RBI",
    "fc_odc": "E_BANK",
    "fc_ofc": "E_NBFC",
    "gg_cen": "G_CEN",
    "gg_sta": "G_STA",
}
# SAM institution account -> capital account (the K_* that holds the same unit's financial transactions)
INST_TO_K: dict[str, str] = {
    "E_NFPU": "K_NFPU",
    "E_NFPR": "K_NFPR",
    "E_RBI": "K_RBI",
    "E_BANK": "K_BANK",
    "E_NBFC": "K_NBFC",
    "E_INSP": "K_INSP",
    "G_CEN": "K_GCEN",
    "G_STA": "K_GSTA",
}
# Domestic accounts that can receive or pay property income with RoW (gap map R13/R14: NFC; FC; GOV)
PROPERTY_ACCOUNTS = ("E_NFPU", "E_NFPR", "E_RBI", "E_BANK", "E_NBFC", "E_INSP", "G_CEN", "G_STA")
R14A_PAYERS = ("E_NFPU", "E_NFPR", "E_BANK", "E_NBFC", "E_INSP")  # gap map R14a: NFC(E_NFPR, E_NFPU); FC


@dataclass
class Out:
    """What the sub-builders accumulate (entries, constraints, satellite rows by satellite name)."""

    entries: list[dict[str, Any]] = field(default_factory=list)
    constraints: list[dict[str, Any]] = field(default_factory=list)
    sat_rows: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    # memo of values other sub-builders need (e.g. the R14a payer split, reused by K8b counterparts)
    memo: dict[str, Any] = field(default_factory=dict)

    def rows(self, name: str) -> list[dict[str, Any]]:
        return self.sat_rows.setdefault(name, [])


def shares(weights: Mapping[str, float], what: str) -> dict[str, float]:
    """Normalise non-negative weights to shares that sum to 1 (zero weights dropped). Fails on a
    negative or non-finite weight, or when everything is zero (no silent empty key)."""
    bad = {k: v for k, v in weights.items() if not math.isfinite(v) or v < 0}
    if bad:
        raise SamError(f"{what}: negative or non-finite key weights {bad}")
    tot = sum(v for v in weights.values())
    if tot <= 0:
        raise SamError(f"{what}: every key weight is zero")
    return {k: v / tot for k, v in sorted(weights.items()) if v > 0}


def allocate(total: float, weights: Mapping[str, float], what: str) -> dict[str, float]:
    """Split `total` over the keys of `weights` in proportion (shares()); the last key in sorted order
    takes the float residual so the pieces add up to `total` exactly."""
    sh = shares(weights, what)
    keys = sorted(sh)
    out = {k: total * sh[k] for k in keys[:-1]}
    out[keys[-1]] = total - sum(out.values())
    return out


def add_into(acc: dict[str, float], part: Mapping[str, float]) -> dict[str, float]:
    for k, v in part.items():
        acc[k] = acc.get(k, 0.0) + v
    return acc


def mean(values: Sequence[float]) -> float:
    if not values:
        raise SamError("mean of nothing")
    return sum(values) / len(values)


def state_consumption_key(
    xwalk_rows: Sequence[Mapping[str, Any]], groups: Sequence[str]
) -> dict[str, dict[str, float]]:
    """{state: {group: consumption}} from rows with keys state, household_group, value. Groups outside
    `groups` are an error; a State whose consumption sums to zero is an error (no silent drop)."""
    out: dict[str, dict[str, float]] = {}
    for r in xwalk_rows:
        g = r["household_group"]
        if g not in groups:
            raise SamError(f"hh_state_xwalk: unknown household group {g!r}")
        st = out.setdefault(r["state"], {})
        st[g] = st.get(g, 0.0) + float(r["value"])
    for s, d in out.items():
        if sum(d.values()) <= 0:
            raise SamError(f"hh_state_xwalk: State {s} has no consumption")
    return out


def remittance_by_group(
    total: float, state_shares: Mapping[str, float], key: Mapping[str, Mapping[str, float]]
) -> dict[str, float]:
    """Gap map R11a: R11a_g = total * sum_k s_k * w_{k,g}, with s_k the State share of inward remittances
    (normalised to 1 here) and w_{k,g} the share of State k's consumption falling in group g. Every State
    with a remittance share must have a consumption key (else an error: the caller logs and decides)."""
    missing = sorted(k for k, s in state_shares.items() if s > 0 and k not in key)
    if missing:
        raise SamError(f"R11a: no household consumption key for State(s) {missing}")
    s_norm = shares({k: v for k, v in state_shares.items() if v > 0}, "R11a State shares")
    out: dict[str, float] = {}
    for k, sk in s_norm.items():
        w = shares(key[k], f"R11a consumption key of {k}")
        add_into(out, {g: total * sk * wg for g, wg in w.items()})
    # make the pieces add up to the total exactly (float residual on the largest group)
    big = max(sorted(out), key=lambda g: out[g])
    out[big] += total - sum(out.values())
    return dict(sorted(out.items()))


def ras(
    seed: Mapping[tuple[str, str], float],
    row_targets: Mapping[str, float],
    col_targets: Mapping[str, float],
    *,
    tol: float = 1e-6,
    max_iter: int = 5000,
) -> dict[tuple[str, str], float]:
    """Two-margin RAS (biproportional scaling) of a non-negative seed matrix to row and column targets.
    Row and column targets must have the same total (within 1e-6 relative). Fails if it does not
    converge (no silent partial answer)."""
    rt, ct = sum(row_targets.values()), sum(col_targets.values())
    if abs(rt - ct) > 1e-6 * max(abs(rt), 1.0):
        raise SamError(f"RAS: row targets sum {rt} but column targets {ct}")
    x = {k: v for k, v in seed.items() if v > 0}
    for r, c in x:
        if r not in row_targets or c not in col_targets:
            raise SamError(f"RAS: seed cell {(r, c)} has no target")
    for _ in range(max_iter):
        rs: dict[str, float] = {}
        for (r, _c), v in x.items():
            rs[r] = rs.get(r, 0.0) + v
        for k in list(x):
            t = row_targets[k[0]]
            x[k] = x[k] * t / rs[k[0]] if rs[k[0]] > 0 else 0.0
        cs: dict[str, float] = {}
        for (_r, c), v in x.items():
            cs[c] = cs.get(c, 0.0) + v
        for k in list(x):
            t = col_targets[k[1]]
            x[k] = x[k] * t / cs[k[1]] if cs[k[1]] > 0 else 0.0
        rs = {}
        for (r, _c), v in x.items():
            rs[r] = rs.get(r, 0.0) + v
        err = max(abs(rs.get(r, 0.0) - t) for r, t in row_targets.items())
        if err <= tol:
            return dict(sorted(x.items()))
    raise SamError(f"RAS did not converge in {max_iter} iterations (max row error {err:.3g})")
