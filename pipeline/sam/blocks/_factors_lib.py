"""Pure functions used by the `factors` block (no I/O, no BlockContext): the labour split (V1a), the
two-column RAS for the household share of surplus (V2a), and the IFPRI gradient keys (F1a, F2, F3c).

Everything here works on plain dicts so the block tests can check each step on small fixtures. The block
module (`factors.py`) reads the clean data, calls these functions and registers provenance.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

AREAS = ("rural", "urban")


class FactorsError(ValueError):
    """A computation in the factors block cannot proceed (bad or inconsistent inputs)."""


# ---------------------------------------------------------------------------------------------
# V1a: regular vs casual wage bills by PLFS industry group and area
# ---------------------------------------------------------------------------------------------


def workers_by_group(
    wpr: Mapping[str, float],
    persons: Mapping[str, float],
    section_share: Mapping[tuple[str, str], float],
    groups: Mapping[str, Sequence[str]],
) -> dict[tuple[str, str], float]:
    """Workers of PLFS group g in area s, up to a common factor: WPR_s (%) x persons_s x the sum of the
    t26 worker shares (%) of the NIC sections in g. `section_share[(section, area)]` in percent."""
    out: dict[tuple[str, str], float] = {}
    for g, secs in groups.items():
        for s in AREAS:
            share = sum(section_share.get((sec, s), 0.0) for sec in secs) / 100.0
            out[(g, s)] = wpr[s] / 100.0 * persons[s] * share
    return out


def casual_wage_by_group(
    section_share: Mapping[tuple[str, str], float],
    section_wage: Mapping[tuple[str, str], float],
    groups: Mapping[str, Sequence[str]],
) -> dict[tuple[str, str], float]:
    """Casual daily wage of group g in area s: the t51 wages of its sections weighted by their t26 worker
    shares. Sections without a wage (not in `section_wage`) are left out of the weighting."""
    out: dict[tuple[str, str], float] = {}
    for g, secs in groups.items():
        for s in AREAS:
            num = den = 0.0
            for sec in secs:
                w = section_wage.get((sec, s))
                if w is None:
                    continue
                sh = section_share.get((sec, s), 0.0)
                num += sh * w
                den += sh
            if den <= 0:
                raise FactorsError(f"no casual wage for PLFS group {g} in {s} areas")
            out[(g, s)] = num / den
    return out


def wage_bills(
    workers: Mapping[tuple[str, str], float],
    reg_share: Mapping[tuple[str, str], float],
    cas_share: Mapping[tuple[str, str], float],
    reg_earnings_year: Mapping[str, float],
    cas_wage_day: Mapping[tuple[str, str], float],
    days: float,
) -> tuple[dict[tuple[str, str], float], dict[tuple[str, str], float]]:
    """Regular bill = workers x regular share (%) x annual regular earnings of the area; casual bill =
    workers x casual share (%) x daily casual wage x days. Same (unknown) scale as `workers`."""
    reg, cas = {}, {}
    for key, w in workers.items():
        g, s = key
        reg[key] = w * reg_share[key] / 100.0 * reg_earnings_year[s]
        cas[key] = w * cas_share[key] / 100.0 * cas_wage_day[key] * days
    return reg, cas


def regular_share(reg: Mapping[tuple[str, str], float], cas: Mapping[tuple[str, str], float]) -> dict[str, float]:
    """share_reg_g = sum_s reg / sum_s (reg + cas)."""
    out = {}
    for g in sorted({k[0] for k in reg}):
        r = sum(reg[(g, s)] for s in AREAS)
        c = sum(cas[(g, s)] for s in AREAS)
        if r + c <= 0:
            raise FactorsError(f"PLFS group {g}: no wage bill")
        out[g] = r / (r + c)
    return out


def rural_share(bill: Mapping[tuple[str, str], float], g: str) -> float:
    tot = bill[(g, "rural")] + bill[(g, "urban")]
    if tot <= 0:
        raise FactorsError(f"PLFS group {g}: zero wage bill, no rural share")
    return bill[(g, "rural")] / tot


def apply_floor(reg: Mapping[str, float], ce: Mapping[str, float], floor: float) -> tuple[dict[str, float], float]:
    """Raise regular CE of the activities in one NAS group so that it sums to at least `floor`, scaling
    every activity's regular CE by one factor and capping each at its CE (the cap's excess is spread over
    the activities that still have room). Returns (new regular CE, amount added)."""
    now = sum(reg.values())
    if now >= floor:
        return dict(reg), 0.0
    if floor > sum(ce.values()) + 1e-9:
        raise FactorsError(f"regular-CE floor {floor:,.2f} exceeds the group's CE {sum(ce.values()):,.2f}")
    out = dict(reg)
    for _ in range(len(out) + 1):
        room = {a: ce[a] - out[a] for a in out if ce[a] - out[a] > 1e-12}
        need = floor - sum(out.values())
        if need <= 1e-9 or not room:
            break
        base = sum(out[a] for a in room)
        if base <= 0:
            for a in room:  # nothing to scale: fill pro rata to the room left
                out[a] += need * room[a] / sum(room.values())
            break
        k = 1.0 + need / base
        for a in room:
            out[a] = min(ce[a], out[a] * k)
    return out, sum(out.values()) - now


# ---------------------------------------------------------------------------------------------
# V2a: household share of surplus within a multi-activity NAS group
# ---------------------------------------------------------------------------------------------


def ras_two_columns(
    row_totals: Mapping[str, float],
    hh_total: float,
    hh_prior: Mapping[str, float],
    *,
    tol: float = 1e-10,
    max_iter: int = 10_000,
) -> dict[str, float]:
    """Split each row total (activity GOS) into a household part and a rest so that the household parts
    sum to `hh_total` and each row sums to its total. Priors: household = `hh_prior[a]`, rest = the row
    total (a two-column RAS). Returns the household part by activity (0 <= hh_a <= row_a).

    A row with a zero household prior gets no household part. Fails if the household total exceeds the
    sum of rows with a positive prior, or does not converge."""
    rows = {a: float(v) for a, v in row_totals.items()}
    if any(v < 0 for v in rows.values()) or hh_total < 0:
        raise FactorsError("RAS needs non-negative row totals and household total")
    rest_total = sum(rows.values()) - hh_total
    if rest_total < -1e-9:
        raise FactorsError(f"household total {hh_total:,.2f} exceeds the group's surplus {sum(rows.values()):,.2f}")
    cap = sum(rows[a] for a in rows if hh_prior.get(a, 0.0) > 0)
    if hh_total > cap + 1e-9:
        raise FactorsError(f"household total {hh_total:,.2f} exceeds the surplus of activities with a prior {cap:,.2f}")
    if hh_total == 0:
        return {a: 0.0 for a in rows}
    h = {a: max(0.0, float(hh_prior.get(a, 0.0))) for a in rows}
    o = {a: rows[a] for a in rows}
    for _ in range(max_iter):
        # row scaling
        for a in rows:
            s = h[a] + o[a]
            if s > 0:
                f = rows[a] / s
                h[a] *= f
                o[a] *= f
        # column scaling
        sh, so = sum(h.values()), sum(o.values())
        fh = hh_total / sh if sh > 0 else 0.0
        fo = rest_total / so if so > 0 else 0.0
        for a in rows:
            h[a] *= fh
            o[a] *= fo
        err = max(abs(h[a] + o[a] - rows[a]) for a in rows)
        if err <= tol * max(1.0, max(rows.values())):
            return {a: min(h[a], rows[a]) for a in rows}
    raise FactorsError("two-column RAS did not converge")


# ---------------------------------------------------------------------------------------------
# F1a, F2, F3c: IFPRI per-capita gradients mapped onto the 10 SAM groups
# ---------------------------------------------------------------------------------------------

QUINTILES = ("q1", "q2", "q3", "q4", "q5")


def ifpri_index(component_pct: Mapping[str, float], spending_per_capita: Mapping[str, float]) -> dict[str, float]:
    """Per-capita income index of a factor by national quintile: the factor's share of each quintile's
    income (IFPRI T10, %) x the quintile's total spending per capita (T11), normalised to sum to 1."""
    raw = {q: component_pct[q] / 100.0 * spending_per_capita[q] for q in QUINTILES}
    tot = sum(raw.values())
    if tot <= 0:
        raise FactorsError("IFPRI index sums to zero")
    return {q: raw[q] / tot for q in QUINTILES}


def group_index(
    index_q: Mapping[str, float],
    groups: Sequence[str],
    xwalk: Mapping[str, Mapping[str, float]] | None,
) -> dict[str, float]:
    """Per-capita index of each SAM group. With a crosswalk (share of the group's persons in national
    quintile q): I_g = sum_q x_{g,q} I_q. Without one, the k-th group of an area takes the k-th national
    quintile's index (the stated assumption k = q; group codes end in their quintile number)."""
    out = {}
    for g in groups:
        if xwalk is not None:
            x = xwalk[g]
            tot = sum(x.values())
            if tot <= 0:
                raise FactorsError(f"crosswalk row for {g} is empty")
            out[g] = sum(x.get(q, 0.0) / tot * index_q[q] for q in QUINTILES)
        else:
            out[g] = index_q[f"q{g[-1]}"]
    return out


def area_shares(persons: Mapping[str, float], index_g: Mapping[str, float], groups: Sequence[str]) -> dict[str, float]:
    """Shares within one area: persons_g x index_g, normalised over the area's groups."""
    raw = {g: persons[g] * index_g[g] for g in groups}
    tot = sum(raw.values())
    if tot <= 0:
        raise FactorsError(f"no weight in groups {list(groups)}")
    return {g: raw[g] / tot for g in groups}


def split_by_area(
    total_rural: float, total_urban: float, shares: Mapping[str, Mapping[str, float]]
) -> dict[str, float]:
    """Group amounts from area totals and within-area shares (`shares['rural'][g]`)."""
    out = {}
    for s, tot in (("rural", total_rural), ("urban", total_urban)):
        for g, sh in shares[s].items():
            out[g] = tot * sh
    return out


def normalise(levels: Mapping[str, float]) -> dict[str, float]:
    tot = sum(levels.values())
    if tot <= 0 or any(v < 0 for v in levels.values()):
        raise FactorsError("a key must be non-negative with a positive total")
    return {k: v / tot for k, v in levels.items()}
