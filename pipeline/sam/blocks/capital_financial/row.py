"""K7b RoW counterparts (plan s.2.9): every rest_of_world K8b line posted on the domestic account it names,
in the same instrument and with the same value, so each instrument market clears with the BoP.

Interface (rest_of_world plan s.4, CROSS_REVIEW s.4.3): satellite `row_financial_counterparts`, one row per
K8b line x domestic counterpart, with columns `line`, `instrument`, `bop_function`, `direction`
(`row_acquires` = India's liability, `row_incurs` = India's asset), `counterpart` (a K_* account, an E_*/G_*
account, `FC` for financial corporations not split, or `unallocated_k9`) and `value` (Rs crore).
`fdi_reinvested_earnings` is posted with rest_of_world's R14a payer split, so income and financing match.
"""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from pipeline.sam.blocks.capital_financial import params as P
from pipeline.sam.blocks.capital_financial.fsf import abs_share
from pipeline.sam.framework import SamError

SATELLITE = "row_financial_counterparts"
NEEDED = ("line", "instrument", "direction", "counterpart", "value")
REINVESTED = "fdi_reinvested_earnings"
UNALLOCATED = "unallocated_k9"


@dataclass(frozen=True)
class RowPosting:
    account: str  # domestic K account
    instrument: str
    side: str  # 'liability' (K <- I: RoW acquired India's liability) or 'asset' (I <- K)
    value: float
    line: str  # K8b line slug (component row_cp_<line>)
    bop_function: str | None
    how: str


def _account(code: str) -> str | None:
    if code in P.K_DOMESTIC:
        return code
    return P.E_TO_K.get(code)


def postings(sat: pl.DataFrame, r14a: pl.DataFrame, fc_key: dict[str, float]) -> tuple[list[RowPosting], list[str]]:
    """Postings and log lines. `r14a`: rest_of_world's R14a entries (R_ROW <- E_*, value); `fc_key`: shares
    of K_BANK / K_NBFC / K_INSP for a counterpart named only 'FC' (FSF RoW-held equity stocks)."""
    missing = [c for c in NEEDED if c not in sat.columns]
    if missing:
        raise SamError(
            f"rest_of_world satellite {SATELLITE} lacks columns {missing} (has {sat.columns}); the interface is "
            "CROSS_REVIEW s.4.3 / rest_of_world plan s.4"
        )
    if "unit" in sat.columns and set(sat["unit"].to_list()) - {"INR_crore"}:
        raise SamError(f"{SATELLITE}: values must be INR_crore, got {sorted(set(sat['unit']))}")
    log: list[str] = []
    out: list[RowPosting] = []
    bop = "bop_function" in sat.columns
    for r in sat.sort("line", "counterpart").iter_rows(named=True):
        line, inst, v = r["line"], r["instrument"], float(r["value"])
        if r["direction"] not in ("row_acquires", "row_incurs"):
            raise SamError(f"{SATELLITE}: unknown direction {r['direction']!r} on line {line}")
        side = "liability" if r["direction"] == "row_acquires" else "asset"
        fn = r["bop_function"] if bop else None
        if line == REINVESTED:
            continue  # posted from R14a below
        cp = r["counterpart"]
        if inst == "I_RESV":
            log.append(f"RoW line {line} (I_RESV) {v:,.2f}: its domestic side is rest_of_world's K8c, not posted here")
            continue
        if cp == UNALLOCATED or v == 0.0:
            log.append(f"RoW line {line} ({inst}) {v:,.2f}: no domestic counterpart, absorbed by K9")
            continue
        acct = _account(cp)
        if acct is not None:
            out.append(RowPosting(acct, inst, side, v, line, fn, f"rest_of_world counterpart {cp}"))
        elif cp == "FC":
            split = abs_share(v, fc_key)
            if split is None:
                raise SamError("FC split key for RoW counterparts is all zero")
            for k, x in split.items():
                out.append(RowPosting(k, inst, side, x, line, fn, "FC split by FSF RoW-held FC equity stocks"))
            log.append(f"RoW line {line} ({inst}) {v:,.2f}: counterpart 'FC' split {split}")
        else:
            raise SamError(f"{SATELLITE}: counterpart {cp!r} on line {line} is not a domestic account")
    re_lines = sat.filter(pl.col("line") == REINVESTED)
    if re_lines.height:
        re_total = float(re_lines["value"].sum())
        inst = re_lines["instrument"][0]
        fn = re_lines["bop_function"][0] if bop else None
        r14 = {}
        for r in r14a.iter_rows(named=True):
            acct = _account(r["col"])
            if acct is None:
                raise SamError(f"R14a payer {r['col']} has no capital account")
            r14[acct] = r14.get(acct, 0.0) + float(r["value"])
        if abs(sum(r14.values()) - re_total) > 1.0:
            log.append(f"WARNING: R14a total {sum(r14.values()):,.2f} != K8b {REINVESTED} {re_total:,.2f}")
        for k, x in sorted(r14.items()):
            out.append(RowPosting(k, inst, "liability", x, REINVESTED, fn, "rest_of_world R14a payer split"))
    return out, log
