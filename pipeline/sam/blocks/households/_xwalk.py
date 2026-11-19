"""Households block: placing HCES fractile classes on MPCE quintiles that are not their own (households plan
s.2.8 `hh_state_xwalk`; CROSS_REVIEW XR-10 `hh_national_quintile_xwalk`). Private helper.

Model (an assumption, stated in the provenance records): HCES A2 publishes class means, not class boundaries.
Within one list of classes (a State x area, or all-India x area), the classes are ordered by mean MPCE and
each class's persons are spread uniformly in log MPCE over an interval whose inner ends are the log-midpoints
between adjacent class means; the outer ends of the first and last class mirror their inner end around the
class mean. Nominal MPCE, no spatial price deflator."""

from __future__ import annotations

import math


def log_intervals(means: list[float]) -> list[tuple[float, float]]:
    """(lo, hi) in ln(MPCE) for classes given in ascending mean order."""
    x = [math.log(m) for m in means]
    if len(x) == 1:
        return [(x[0], x[0])]
    mid = [(x[i] + x[i + 1]) / 2 for i in range(len(x) - 1)]
    lo = [2 * x[0] - mid[0], *mid]
    hi = [*mid, 2 * x[-1] - mid[-1]]
    return list(zip(lo, hi, strict=True))


def fraction(lo: float, hi: float, a: float, b: float) -> float:
    """Share of a class spread uniformly on [lo, hi] that falls in [a, b) (a point class: 1 if inside)."""
    if hi > lo:
        return max(0.0, min(hi, b) - max(lo, a)) / (hi - lo)
    return 1.0 if a <= lo < b else 0.0


def weights(lo: float, hi: float, cuts: list[float]) -> list[float]:
    """Share of a class in each of the len(cuts)+1 bands (-inf, c1), [c1, c2), ..., [ck, inf)."""
    edges = [-math.inf, *cuts, math.inf]
    return [fraction(lo, hi, edges[i], edges[i + 1]) for i in range(len(edges) - 1)]


def quantile_cuts(intervals: list[tuple[float, float]], persons: list[float], qs: list[float]) -> list[float]:
    """ln MPCE at which the cumulative person share reaches each q, for the mixture of uniform classes
    (bisection to machine precision; deterministic)."""
    total = sum(persons)

    def cdf(x: float) -> float:
        s = 0.0
        for (lo, hi), p in zip(intervals, persons, strict=True):
            s += p * (fraction(lo, hi, -math.inf, x) if hi > lo else (1.0 if lo < x else 0.0))
        return s / total

    lo0, hi0 = min(i[0] for i in intervals), max(i[1] for i in intervals)
    out = []
    for q in qs:
        a, b = lo0, hi0
        for _ in range(200):
            m = (a + b) / 2
            if cdf(m) < q:
                a = m
            else:
                b = m
            if b - a < 1e-13:
                break
        out.append((a + b) / 2)
    return out
