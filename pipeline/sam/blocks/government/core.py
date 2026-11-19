"""government helpers that touch no data: tracked numbers, keys, RAS, the R9b formula and the D2-5 evidence.

Everything here is pure (no BlockContext), so tests exercise it on small fixtures.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from pipeline.sam.framework import SamError

HH = ["H_R1", "H_R2", "H_R3", "H_R4", "H_R5", "H_U1", "H_U2", "H_U3", "H_U4", "H_U5"]
GOV = ["G_CEN", "G_STA"]


@dataclass(frozen=True)
class Q:
    """A number and the prov_ids it rests on (clean, own or DEPENDS-block records)."""

    v: float
    p: frozenset[str] = field(default_factory=frozenset)

    def __add__(self, o: Q | float) -> Q:
        if isinstance(o, Q):
            return Q(self.v + o.v, self.p | o.p)
        return Q(self.v + float(o), self.p)

    __radd__ = __add__

    def __sub__(self, o: Q | float) -> Q:
        return self + (-o if isinstance(o, Q) else -float(o))

    def __neg__(self) -> Q:
        return Q(-self.v, self.p)

    def __mul__(self, k: float) -> Q:
        return Q(self.v * float(k), self.p)

    __rmul__ = __mul__

    @property
    def pids(self) -> list[str]:
        return sorted(self.p)


def qsum(items: Iterable[Q]) -> Q:
    out = Q(0.0)
    for x in items:
        out = out + x
    return out


def pids_of(*items: Q | Mapping[str, Q] | Iterable[Q]) -> list[str]:
    """Sorted union of the prov_ids of any mix of Q, {k: Q} and iterables of Q."""
    out: set[str] = set()
    for it in items:
        if isinstance(it, Q):
            out |= it.p
        elif isinstance(it, Mapping):
            for x in it.values():
                out |= x.p
        else:
            for x in it:
                out |= x.p
    return sorted(out)


def shares(levels: Mapping[str, float], what: str) -> dict[str, float]:
    """Normalise non-negative levels to shares summing to 1 (fails on negatives or an all-zero key)."""
    bad = {k: v for k, v in levels.items() if not math.isfinite(v) or v < 0}
    if bad:
        raise SamError(f"government: key {what} has negative or non-finite levels {bad}")
    tot = sum(levels.values())
    if tot <= 0:
        raise SamError(f"government: key {what} sums to {tot}")
    return {k: v / tot for k, v in levels.items()}


def split(total: float, key: Mapping[str, float]) -> dict[str, float]:
    """total x share, in the key's order; zero shares give no item."""
    return {k: total * s for k, s in key.items() if s != 0.0}


def ras(
    seed: Mapping[tuple[str, str], float],
    row_targets: Mapping[str, float],
    col_targets: Mapping[str, float],
    *,
    tol: float = 1e-9,
    max_iter: int = 10_000,
) -> dict[tuple[str, str], float]:
    """Biproportional scaling of a non-negative seed to row and column totals (relative tolerance `tol`).
    A zero seed cell stays zero. Fails if the totals are inconsistent or it does not converge."""
    rows, cols = sorted(row_targets), sorted(col_targets)
    if abs(sum(row_targets.values()) - sum(col_targets.values())) > 1e-6 * max(1.0, sum(row_targets.values())):
        raise SamError(f"RAS: row totals {sum(row_targets.values())} != column totals {sum(col_targets.values())}")
    x = {(r, c): float(seed.get((r, c), 0.0)) for r in rows for c in cols}
    if any(v < 0 for v in x.values()):
        raise SamError("RAS: negative seed cell")
    for _ in range(max_iter):
        for r in rows:
            s = sum(x[(r, c)] for c in cols)
            if s <= 0:
                raise SamError(f"RAS: row {r} has an all-zero seed but target {row_targets[r]}")
            f = row_targets[r] / s
            for c in cols:
                x[(r, c)] *= f
        worst = 0.0
        for c in cols:
            s = sum(x[(r, c)] for r in rows)
            if s <= 0:
                raise SamError(f"RAS: column {c} has an all-zero seed but target {col_targets[c]}")
            f = col_targets[c] / s
            worst = max(worst, abs(f - 1.0))
            for r in rows:
                x[(r, c)] *= f
        rgap = max(abs(sum(x[(r, c)] for c in cols) / row_targets[r] - 1.0) for r in rows if row_targets[r])
        if worst < tol and rgap < tol:
            return x
    raise SamError(f"RAS did not converge in {max_iter} iterations")


def r9b_formula(
    civil_base: float, defence: float, year: str, *, start: int = 2005, career: int = 39
) -> dict[str, float]:
    """Gap-map R9b (S&M 2026 s.3.1.1): Centre civil OPS pensions x (1 - k/career), k = years since `start`
    (2005-06, NPS for new Central civil recruits from 2004-05), defence unadjusted (armed forces stay on OPS)."""
    k = int(year[:4]) - start
    if not 0 <= k <= career:
        raise SamError(f"R9b: k = {k} years out of range for {year}")
    factor = 1.0 - k / career
    return {"k": float(k), "factor": factor, "civil": civil_base * factor, "defence": defence}


@dataclass(frozen=True)
class Evidence:
    variant: str
    r9b: float
    delivered: float
    required: float

    @property
    def gap(self) -> float:
        return self.delivered - self.required


def gdi_evidence(
    *, property_received: float, property_paid: float, income_taxes: float, benefits_paid: float,
    other_transfers_paid: float, required: float, variants: Mapping[str, float],
) -> list[Evidence]:  # fmt: skip
    """GG net distributive flows implied by the prior (resources - uses outside GG, other than taxes on
    production and imports) for each R9b variant, against the NAS requirement GDI - CFC - net D2-D3."""
    base = property_received - property_paid + income_taxes - benefits_paid - other_transfers_paid
    return [Evidence(name, v, base + v, required) for name, v in variants.items()]


def choose_variant(ev: list[Evidence], allowed: Iterable[str]) -> Evidence:
    """The allowed variant with the smallest |gap| (ties: the first allowed, in the given order)."""
    allowed = list(allowed)
    cands = [e for e in ev if e.variant in allowed]
    if not cands:
        raise SamError(f"R9b: none of the allowed variants {allowed} was evaluated")
    return min(cands, key=lambda e: (abs(e.gap), allowed.index(e.variant)))


def paired_saving(net: float, margin: float) -> tuple[float, float]:
    """A saving prior written as two same-cell entries (+, -) whose sum is `net`, so balancing can move the net
    across zero (SAM_GUIDE s.5, FRAMEWORK_REQUESTS P-9): pos = max(net, 0) + m, neg = min(net, 0) - m."""
    m = abs(margin)
    if m == 0:
        raise SamError("paired saving needs a non-zero margin")
    return max(net, 0.0) + m, min(net, 0.0) - m
