"""The physical side of the capital account: GFCF by commodity x investor (I1a), inventories by sector
(I3a), and the allocation of the NAS saving-investment errors (D3). Pure functions."""

from __future__ import annotations

import math

from pipeline.sam.blocks.capital_financial import params as P
from pipeline.sam.framework import SamError


def ras(
    prior: dict[tuple[str, str], float], rows: dict[str, float], cols: dict[str, float]
) -> tuple[dict[tuple[str, str], float], int]:
    """Biproportional (RAS) fit of a non-negative prior to row and column totals (plan s.2.2 step 4).
    Zero priors stay zero. Stops when every row and column is within params.RAS_TOL (relative)."""
    if any(v < 0 for v in prior.values()):
        raise SamError("RAS prior has negative cells")
    tr, tc = sum(rows.values()), sum(cols.values())
    if abs(tr - tc) > 1e-9 * max(abs(tr), 1.0):
        raise SamError(f"RAS row total {tr:,.6f} != column total {tc:,.6f}")
    x = {k: v for k, v in prior.items() if v > 0}
    for r, t in rows.items():
        if t != 0 and not any(k[0] == r for k in x):
            raise SamError(f"RAS: row {r} has target {t:,.2f} but no non-zero prior")
    for c, t in cols.items():
        if t != 0 and not any(k[1] == c for k in x):
            raise SamError(f"RAS: column {c} has target {t:,.2f} but no non-zero prior")
    for it in range(1, P.RAS_MAX_ITER + 1):
        rs: dict[str, float] = {}
        for (r, _), v in x.items():
            rs[r] = rs.get(r, 0.0) + v
        x = {k: v * rows[k[0]] / rs[k[0]] for k, v in x.items()}
        cs: dict[str, float] = {}
        for (_, c), v in x.items():
            cs[c] = cs.get(c, 0.0) + v
        x = {k: v * cols[k[1]] / cs[k[1]] for k, v in x.items()}
        rs = {}
        for (r, _), v in x.items():
            rs[r] = rs.get(r, 0.0) + v
        err = max(abs(rs[r] - t) / abs(t) for r, t in rows.items() if t != 0)
        if err <= P.RAS_TOL:
            return dict(sorted(x.items())), it
    raise SamError(f"RAS did not converge in {P.RAS_MAX_ITER} iterations")


def gfcf_prior(
    commodity_gfcf: dict[str, float],
    asset_by_column: dict[str, dict[str, float]],
    column_totals: dict[str, float],
) -> dict[tuple[str, str], float]:
    """p(c, k) = V(k, a(c)) * SUT(c) / SUT(a(c)) (plan s.2.2 step 3), where V(k, a) is the NAS 1.11 asset
    mix of the column's sector scaled to the column's total. asset_by_column: column -> asset -> NAS value."""
    missing = sorted(set(commodity_gfcf) - set(P.ASSET_OF))
    if missing:
        raise SamError(f"commodities with SUT GFCF but no NAS asset group (params.ASSET_OF): {missing}")
    by_asset: dict[str, float] = {}
    for c, v in commodity_gfcf.items():
        by_asset[P.ASSET_OF[c]] = by_asset.get(P.ASSET_OF[c], 0.0) + v
    prior: dict[tuple[str, str], float] = {}
    for k, mix in asset_by_column.items():
        s = sum(mix.values())
        if s <= 0:
            raise SamError(f"GFCF column {k}: NAS asset mix sums to {s}")
        for c, v in commodity_gfcf.items():
            a = P.ASSET_OF[c]
            p = column_totals[k] * mix.get(a, 0.0) / s * v / by_asset[a]
            if p > 0:
                prior[(c, k)] = p
    return dict(sorted(prior.items()))


def largest_remainder_split(total: float, weights: dict[str, float]) -> dict[str, float]:
    """total x weight / sum(weights), with the float remainder put on the largest weight so the parts add
    up to `total` exactly (fixed X_DISC entries must close)."""
    s = sum(weights.values())
    if s <= 0 or any(w < 0 for w in weights.values()):
        raise SamError(f"allocation weights must be non-negative with a positive sum: {weights}")
    parts = {k: total * w / s for k, w in sorted(weights.items()) if w > 0}
    big = max(parts, key=lambda k: (weights[k], k))
    parts[big] = total - sum(v for k, v in parts.items() if k != big)
    return parts


def scale_parts(values: dict[str, float], target: float) -> dict[str, float]:
    """Scale values to sum to `target` (sector CIS to the SUT total); remainder on the largest."""
    s = sum(values.values())
    if s == 0 or not math.isfinite(s):
        raise SamError("cannot scale parts that sum to zero")
    out = {k: v * target / s for k, v in values.items()}
    big = max(out, key=lambda k: (abs(out[k]), k))
    out[big] = target - sum(v for k, v in out.items() if k != big)
    return out
