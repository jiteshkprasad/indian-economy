"""Total labels: which aggregates are held to published figures (docs/phase3/PLAN.md s.3.4.2).

A pin is a narrow official/derived constraint (kind equal or band, half-width max(tol_abs, tol_rel x |target|)
<= max(Rs 1 crore, 0.1% of |target|), balanced sum inside its band) or a time-series flow whose 2023-24 SAM
check passes. An aggregate (a set of entries) has total label official/derived when its entry set is exactly a
disjoint union of pins; the label is the least certain status among them. Entries that round to zero are left
out on both sides (they carry no value, e.g. the D4 cells).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import polars as pl

from pipeline.export.inputs import ExportError
from pipeline.export.sam_export import SamView, nonzero_cells, r2
from pipeline.export.status import least_certain_total

PIN_ABS = 1.0  # Rs crore
PIN_REL = 0.001
BAND_EPS = 0.01  # Rs crore: balanced sum may sit this far outside its band (solver tolerance)
ZERO = 0.005
MAX_SEARCH = 200_000


@dataclass(frozen=True)
class Pin:
    id: str  # constraint id or "ts:F01"
    status: str  # official | derived
    mask: int  # bitmask over entry indices (non-zero entries only)
    size: int


def constraint_pins(view: SamView) -> list[Pin]:
    inp = view.inp
    out: list[Pin] = []
    for r in inp.constraints.iter_rows(named=True):
        if r["kind"] not in ("equal", "band"):
            continue
        tol = max(float(r["tol_abs"] or 0.0), float(r["tol_rel"] or 0.0) * abs(float(r["target"])))
        if tol > max(PIN_ABS, PIN_REL * abs(float(r["target"]))):
            continue
        rec = inp.prov.get(r["prov_id"])
        if rec is None:
            raise ExportError(f"constraint {r['constraint_id']}: provenance {r['prov_id']!r} does not resolve")
        if rec.get("status") not in ("official", "derived"):
            continue
        lo, hi, bs = float(r["lo"]), float(r["hi"]), float(r["balanced_sum"])
        if not (lo - BAND_EPS <= bs <= hi + BAND_EPS):
            continue
        m = _mask(view, inp.members[r["constraint_id"]])
        if m:
            out.append(Pin(r["constraint_id"], str(rec["status"]), m, m.bit_count()))
    return out


def ts_pins(view: SamView, flow_entries: dict[str, list[int]], status_2023: dict[str, str]) -> list[Pin]:
    inp = view.inp
    out: list[Pin] = []
    for r in inp.ts_check.iter_rows(named=True):
        if r["verdict"] != "pass":
            continue
        fid = r["flow_id"]
        st = status_2023.get(fid)
        if st not in ("official", "derived"):
            continue
        m = _mask(view, flow_entries.get(fid, []))
        if m:
            out.append(Pin(f"ts:{fid}", st, m, m.bit_count()))
    return out


def _mask(view: SamView, ents: Any) -> int:
    m = 0
    for i in ents:
        i = int(i)
        if abs(float(view.v[i])) >= ZERO:
            m |= 1 << i
    return m


class Pinner:
    def __init__(self, pins: list[Pin]) -> None:
        # deterministic preference: official before derived, larger pins first, then id
        self.pins = sorted(pins, key=lambda p: (p.status != "official", -p.size, p.id))

    def cover(self, target: int) -> list[Pin] | None:
        """An exact disjoint cover of `target` by pins, or None."""
        if not target:
            return None
        cands = [p for p in self.pins if p.mask & ~target == 0]
        if not cands:
            return None
        union = 0
        for p in cands:
            union |= p.mask
        if union != target:
            return None
        budget = [MAX_SEARCH]

        def dfs(rem: int, chosen: list[Pin]) -> list[Pin] | None:
            if rem == 0:
                return chosen
            budget[0] -= 1
            if budget[0] < 0:
                raise ExportError("pinned totals: exact-cover search exceeded its budget")
            low = rem & -rem
            for p in cands:
                if p.mask & low and p.mask & ~rem == 0:
                    got = dfs(rem & ~p.mask, [*chosen, p])
                    if got is not None:
                        return got
            return None

        return dfs(target, [])

    def label(self, target: int) -> dict[str, Any] | None:
        got = self.cover(target)
        if got is None:
            return None
        total = least_certain_total([p.status for p in got])
        return {"total": total, "pins": sorted(p.id for p in got)}


def node_universe(view: SamView) -> dict[str, frozenset[str]]:
    """Every node that can be visible: the 168 hierarchy nodes and PRODUCERS (the simple preset's merge).
    The simple preset's SI (= SI + FINM) is keyed as SI: it differs from SI only by flows with FINM, which
    exist only between SI and FINM (checked)."""
    h = view.inp.hierarchy
    out = {nid: frozenset(n.accounts) for nid, n in h.nodes.items()}
    for p in h.presets.values():
        for mid, members in p["merges"].items():
            if mid in out:
                continue
            out[mid] = frozenset(a for m in members for a in h.nodes[m].accounts)
    finm = out.get("FINM", frozenset())
    si = out.get("SI", frozenset())
    for r, c in view.cell_value:
        if (r in finm) != (c in finm) and not ((r in si) or (c in si)):
            raise ExportError(
                f"cell {r} <- {c} links FINM with a node other than SI: the simple preset's SI id is ambiguous"
            )
    return out


def ancestors(view: SamView, code: str, universe: dict[str, frozenset[str]]) -> list[str]:
    return [nid for nid, accts in universe.items() if code in accts]


def pair_entries(view: SamView) -> dict[tuple[str, str], dict[str, list[int]]]:
    """{(payer node, receiver node): {'pos': entries, 'neg': entries, 'pair': entries}} for every pair of
    non-nested nodes with a non-zero cell between them. Pairs inside PRDS (margins) are internal at every
    zoom and are not links."""
    universe = node_universe(view)
    anc: dict[str, list[str]] = {}
    for code in view.codes:
        anc[code] = ancestors(view, code, universe)
    prds = universe.get(view.inp.hierarchy.split_node, frozenset())
    out: dict[tuple[str, str], dict[str, list[int]]] = {}
    for r, c in nonzero_cells(view):
        if r in prds and c in prds:
            continue
        val = r2(view.cell_value[(r, c)])
        part = "pos" if val > 0 else "neg"
        ents = view.cell_entries[(r, c)]
        for a in anc[c]:  # payer side
            for b in anc[r]:  # receiver side
                if universe[a] & universe[b]:
                    continue  # nested or the same node: internal
                d = out.setdefault((a, b), {"pos": [], "neg": [], "pair": []})
                d[part].extend(ents)
                d["pair"].extend(ents)
    return out


def pinned_json(view: SamView, pins: list[Pin]) -> tuple[dict[str, Any], int]:
    pinner = Pinner(pins)
    out: dict[str, Any] = {}
    pairs = pair_entries(view)
    for a, b in sorted(pairs):
        d = pairs[(a, b)]
        base = f"{a}--{b}"
        for suffix, key in (("", "pos"), ("~neg", "neg"), ("~pair", "pair")):
            ents = d[key]
            if not ents:
                continue
            if suffix == "~pair" and (not d["pos"] or not d["neg"]):
                continue  # the pair equals its only part
            lab = pinner.label(_mask(view, ents))
            if lab is not None:
                out[base + suffix] = lab
    return out, len(pairs)


def aggregate_total(view: SamView, pins: list[Pin], ents: list[int]) -> dict[str, Any] | None:
    return Pinner(pins).label(_mask(view, ents))


def flow_entry_indices(view: SamView, flows: dict[str, Any], ent: pl.DataFrame) -> dict[str, list[tuple[int, float]]]:
    """{flow id: [(entry index, coef)]}: the entries each time-series flow measures in the SAM, selected exactly
    as pipeline.timeseries.build.eval_sam selects them (checked against eval_sam's value)."""
    from pipeline.timeseries.build import eval_sam

    out: dict[str, list[tuple[int, float]]] = {}
    for fid, flow in flows.items():
        sel_all: list[tuple[int, float]] = []
        for t in flow.sam_terms:
            block = ent.filter(pl.col("row").is_in(list(t.rows)) & pl.col("col").is_in(list(t.cols)))
            sel = block.filter(pl.col("ref").is_in(list(t.refs)))
            if t.components is not None:
                sel = sel.filter(pl.col("component").is_in(list(t.components)))
            if t.bop_functions is not None:
                sel = sel.filter(pl.col("bop_function").is_in(list(t.bop_functions)))
            if t.exclude_components:
                sel = sel.filter(~pl.col("component").is_in(list(t.exclude_components)).fill_null(False))
            sel_all.extend((int(i), float(t.coef)) for i in sel["i"].to_list())
        if flow.sam_terms:
            mine = sum(c * float(view.v[i]) for i, c in sel_all)
            ref = eval_sam(flow, ent).value
            if abs(mine - ref) > 0.01:
                raise ExportError(f"flow {fid}: entry selection {mine:.2f} differs from eval_sam {ref:.2f}")
        out[fid] = sel_all
    return out


def entry_array(view: SamView) -> np.ndarray:
    return np.asarray(view.v)
