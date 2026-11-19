"""SAM side of the export: entry labels and flags, cells, entries, constraints, refs (PLAN s.3.4, s.3.6).

`SamView` is built once from `ExportInputs` and is used by the summary, pinned totals, the time-series
cover and the story evaluator, so every figure is computed from the same labelled entries.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import polars as pl

from pipeline.core.io import canonical_float
from pipeline.export.inputs import ExportError, ExportInputs
from pipeline.export.status import (
    FLAG_BITS,
    LABEL_CODE,
    LABELS,
    VERDICT_FLAG,
    LabelError,
    entry_label,
    flags_mask,
    split_of,
)

CR = 2  # money decimals
SHARE = 6
COMP = 4
ZERO_CELL = 0.005  # a cell that rounds to 0.00 is not exported (D4 cells are exactly zero)
CELL = "*"


def r2(x: float) -> float:
    return canonical_float(float(x), CR)


@dataclass
class SamView:
    inp: ExportInputs
    codes: list[str]
    idx: dict[str, int]
    # per entry (parquet order)
    row: list[str] = field(default_factory=list)
    col: list[str] = field(default_factory=list)
    ref: list[str] = field(default_factory=list)
    comp: list[str] = field(default_factory=list)
    v: np.ndarray = field(default_factory=lambda: np.zeros(0))
    label: list[str] = field(default_factory=list)
    flags: list[list[str]] = field(default_factory=list)
    verdict: list[str | None] = field(default_factory=list)
    why: list[str | None] = field(default_factory=list)
    binding: list[list[str]] = field(default_factory=list)
    prov: list[str] = field(default_factory=list)
    # per cell (row, col) -> entry indices, signed rounded value
    cell_entries: dict[tuple[str, str], list[int]] = field(default_factory=dict)
    cell_value: dict[tuple[str, str], float] = field(default_factory=dict)
    judgement_ids: list[str] = field(default_factory=list)
    old_base_ids: list[str] = field(default_factory=list)
    disc_key: list[str | None] = field(default_factory=list)

    @property
    def n(self) -> int:
        return len(self.row)

    # ---- aggregates ----------------------------------------------------------------------------
    def abs_by_label(self, ents: list[int] | np.ndarray) -> dict[str, float]:
        out = dict.fromkeys(LABELS, 0.0)
        for i in ents:
            out[self.label[i]] += abs(float(self.v[i]))
        return out

    def split(self, ents: list[int] | np.ndarray) -> tuple[dict[str, float], str]:
        a = {k: r2(x) for k, x in self.abs_by_label(ents).items()}
        return split_of(a["official"], a["derived"], a["estimated"], a["balancing_set"])

    def flag_set(self, ents: list[int] | np.ndarray) -> list[str]:
        names: set[str] = set()
        for i in ents:
            names.update(self.flags[i])
        return [n for n in FLAG_BITS if n in names]

    def entries_in(self, rows: set[str], cols: set[str]) -> list[int]:
        out: list[int] = []
        for (r, c), ents in self.cell_entries.items():
            if r in rows and c in cols:
                out.extend(ents)
        return sorted(out)


def build_view(inp: ExportInputs, prov_flags: dict[str, dict[str, bool]]) -> SamView:
    """Label every entry (s.3.4.1) and flag it (s.3.4.4). `prov_flags[prov_id]['depends_on_assumption']`
    comes from the provenance walk (pipeline/export/provenance.py)."""
    h = inp.hierarchy
    e = inp.entries
    view = SamView(inp=inp, codes=list(h.codes), idx=dict(h.idx))
    cfg = inp.config
    jb = [str(x) for x in (cfg["judgement_bands"].get("judgement_bands") or [])]
    cons = {r["constraint_id"]: r for r in inp.constraints.iter_rows(named=True)}
    for cid in jb:
        if cid not in cons:
            raise ExportError(f"judgement_bands.yaml names {cid!r}, which is not a constraint of this run")
        if not cons[cid]["binding"]:
            raise ExportError(f"judgement_bands.yaml: {cid} does not bind in this run (review the list)")
    view.judgement_ids = jb
    jb_members: set[int] = set()
    for cid in jb:
        jb_members.update(int(i) for i in inp.members[cid])
    obs = [str(x["prov_id"]) for x in (cfg["old_base_scope"].get("old_base_scope") or [])]
    for pid in obs:
        if pid not in inp.prov:
            raise ExportError(f"old_base_scope.yaml names {pid!r}, which is not a provenance record")
    view.old_base_ids = obs
    obs_set = set(obs)
    disc = cfg["disc_text"].get("disc_text") or {}

    rows = e["row"].to_list()
    cols = e["col"].to_list()
    refs = e["ref"].to_list()
    comps = e["component"].to_list()
    bal = e["balanced"].to_numpy().astype(np.float64)
    if not np.all(np.isfinite(bal)):
        raise ExportError("a balanced entry value is not finite")
    roles = e["role"].to_list()
    status = e["status"].to_list()
    pstatus = e["prior_status"].to_list()
    expl = e["explanation_required"].to_list()
    bind = e["binding"].to_list()
    provs = e["prov_id"].to_list()
    items = inp.items
    for i in range(e.height):
        key = (rows[i], cols[i], refs[i], comps[i])
        own = items.get(key)
        cell = items.get((rows[i], cols[i], CELL, CELL))
        it = own or cell
        try:
            lab = entry_label(
                {
                    "key": key,
                    "role": roles[i],
                    "status": status[i],
                    "prior_status": pstatus[i],
                    "explanation_required": bool(expl[i]),
                    "has_item": it is not None,
                    "in_judgement_band": i in jb_members,
                }
            )
        except LabelError as err:
            raise ExportError(str(err)) from err
        fl: set[str] = set()
        if i in jb_members:
            fl.add("judgement_band")
        for x in (own, cell):
            if x is not None and x["verdict"] in VERDICT_FLAG:
                fl.add(VERDICT_FLAG[x["verdict"]])
        if provs[i] in obs_set:
            fl.add("old_base_structure")
        dk = None
        if rows[i] == "X_DISC" or cols[i] == "X_DISC":
            fl.add("discrepancy")
            cands = [k for k in (f"{refs[i]}.{comps[i]}", refs[i]) if k in disc]
            if not cands:
                raise ExportError(f"X_DISC entry {key} has no text in disc_text.yaml")
            dk = disc[cands[0]]["key"]
        if bal[i] < 0:
            fl.add("has_negative")
        pf = prov_flags.get(provs[i])
        if pf is None:
            raise ExportError(f"entry {key}: provenance id {provs[i]!r} does not resolve")
        if pf["depends_on_assumption"]:
            fl.add("depends_on_assumption")
        view.row.append(rows[i])
        view.col.append(cols[i])
        view.ref.append(refs[i])
        view.comp.append(comps[i])
        view.label.append(lab)
        view.flags.append([n for n in FLAG_BITS if n in fl])
        view.verdict.append(it["verdict"] if it else None)
        view.why.append(it["why"] if it else None)
        view.binding.append(sorted(b for b in (bind[i] or "").split(",") if b))
        view.prov.append(provs[i])
        view.disc_key.append(dk)
        view.cell_entries.setdefault((rows[i], cols[i]), []).append(i)
    view.v = bal
    for r, c, val in inp.sam.select("row", "col", "value").iter_rows():
        if not math.isfinite(val):
            raise ExportError(f"SAM cell {r} <- {c} is not finite")
        view.cell_value[(r, c)] = float(val)
    missing = set(view.cell_value) ^ set(view.cell_entries)
    if missing:
        raise ExportError(f"cells without entries or entries without a SAM cell: {sorted(missing)[:5]}")
    for k, ents in view.cell_entries.items():
        s = float(bal[ents].sum())
        if abs(s - view.cell_value[k]) > 0.01:
            raise ExportError(f"cell {k}: entries sum to {s:.4f}, the SAM says {view.cell_value[k]:.4f}")
    return view


def nonzero_cells(view: SamView) -> list[tuple[str, str]]:
    """Exported cells (rounded value non-zero), ordered by (row index, col index)."""
    keys = [k for k, v in view.cell_value.items() if abs(r2(v)) > 0]
    return sorted(keys, key=lambda k: (view.idx[k[0]], view.idx[k[1]]))


def cell_refs(view: SamView, ents: list[int]) -> list[str]:
    by: dict[str, float] = {}
    for i in ents:
        by[view.ref[i]] = by.get(view.ref[i], 0.0) + abs(float(view.v[i]))
    return [r for r, _ in sorted(by.items(), key=lambda kv: (-kv[1], kv[0]))]


def cells_json(view: SamView) -> dict[str, Any]:
    keys = nonzero_cells(view)
    out: dict[str, list[Any]] = {
        k: [] for k in ("row", "col", "v", "abs_o", "abs_d", "abs_e", "abs_b", "split", "flags", "n_entries", "refs")
    }
    for r, c in keys:
        ents = view.cell_entries[(r, c)]
        a = view.abs_by_label(ents)
        ar = {k: r2(x) for k, x in a.items()}
        _, lab = split_of(ar["official"], ar["derived"], ar["estimated"], ar["balancing_set"])
        out["row"].append(view.idx[r])
        out["col"].append(view.idx[c])
        out["v"].append(r2(view.cell_value[(r, c)]))
        out["abs_o"].append(ar["official"])
        out["abs_d"].append(ar["derived"])
        out["abs_e"].append(ar["estimated"])
        out["abs_b"].append(ar["balancing_set"])
        out["split"].append(LABEL_CODE[lab])
        out["flags"].append(flags_mask(view.flag_set(ents)))
        out["n_entries"].append(len(ents))
        out["refs"].append(cell_refs(view, ents))
    return {"n": len(keys), **out}


def entries_json(view: SamView) -> dict[str, dict[str, Any]]:
    """{L0 id: Entries} for the entries whose row account is in that level-0 node (13 files)."""
    h = view.inp.hierarchy
    e = view.inp.entries
    prior = e["prior"].to_list()
    change = e["change"].to_list()
    pct = e["pct_change"].to_list()
    status = e["status"].to_list()
    pstatus = e["prior_status"].to_list()
    role = e["role"].to_list()
    conf = e["confidence"].to_list()
    bop = e["bop_function"].to_list()
    out: dict[str, dict[str, Any]] = {n: {"node": n, "entries": []} for n in h.level0}
    for i in range(view.n):
        p = pct[i]
        out[h.l0(view.row[i])]["entries"].append(
            {
                "row": view.row[i],
                "col": view.col[i],
                "ref": view.ref[i],
                "component": view.comp[i],
                "v": r2(view.v[i]),
                "prior": r2(prior[i]),
                "change": r2(change[i]),
                # the balancing log stores 100 x change / |prior| (percent); the contract is a fraction
                "pct_change": None if p is None or not math.isfinite(p) else canonical_float(p / 100.0, SHARE),
                "status": status[i],
                "prior_status": pstatus[i],
                "role": role[i],
                "label": view.label[i],
                "confidence": conf[i],
                "bop_function": bop[i],
                "prov": view.prov[i],
                "flags": list(view.flags[i]),
                "verdict": view.verdict[i],
                "why": view.why[i],
                "binding": list(view.binding[i]),
            }
        )
    return out


def _bound(x: float | None) -> float | None:
    if x is None or not math.isfinite(x):
        return None
    return r2(x)


def constraints_json(view: SamView) -> dict[str, Any]:
    jb = set(view.judgement_ids)
    out: dict[str, Any] = {}
    for r in view.inp.constraints.iter_rows(named=True):
        out[r["constraint_id"]] = {
            "kind": r["kind"],
            "ref": r["ref"],
            "description": " ".join(str(r["description"] or "").split()),
            "target": r2(r["target"]),
            "lo": _bound(r["lo"]),
            "hi": _bound(r["hi"]),
            "balanced_sum": r2(r["balanced_sum"]),
            "binding": bool(r["binding"]),
            "judgement": r["constraint_id"] in jb,
            "prov": r["prov_id"],
        }
    return out


def refs_json(view: SamView) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for ref in sorted(set(view.ref)):
        g = view.inp.gap_map.get(ref)
        if g is None:
            raise ExportError(f"ref {ref!r} used by entries is not in data/gap_map.csv")
        out[ref] = {
            "row_block": g.get("row_block") or "",
            "col_block": g.get("col_block") or "",
            "description": " ".join((g.get("description") or "").split()),
            "gap_status": g.get("status") or "",
            "primary_source": g.get("primary_source_id") or "",
            "method": " ".join((g.get("method") or "").split()),
        }
    return out


def label_counts(view: SamView) -> dict[str, dict[str, float]]:
    out = {lab: {"entries": 0, "abs": 0.0} for lab in LABELS}
    for i in range(view.n):
        out[view.label[i]]["entries"] += 1
        out[view.label[i]]["abs"] += abs(float(view.v[i]))
    return {k: {"entries": int(x["entries"]), "abs": r2(x["abs"])} for k, x in out.items()}


def composition_json(comp: dict[str, float]) -> dict[str, float]:
    return {k: canonical_float(comp[k], COMP) for k in ("o", "d", "e", "b")}


def pl_entries(view: SamView) -> pl.DataFrame:
    """The labelled entries as a frame (for selectors in stories and the time-series cover)."""
    e = view.inp.entries
    return pl.DataFrame(
        {
            "i": np.arange(view.n, dtype=np.int64),
            "row": view.row,
            "col": view.col,
            "ref": view.ref,
            "component": view.comp,
            "value": view.v,
            "bop_function": e["bop_function"].to_list(),
            "role": e["role"].to_list(),
            "tol_rel": e["tol_rel"].to_list(),
            "prior": e["prior"].to_list(),
        },
        schema_overrides={"bop_function": pl.String, "tol_rel": pl.Float64},
    )
