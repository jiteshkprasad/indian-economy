"""Gap-map coverage: does every OFFICIAL cell of data/gap_map.csv have clean data behind it?

Each unit may ship `pipeline/ingest/<unit>_coverage.yaml`:

    unit: mospi_nas_2026
    entries:
      - ref: C1                          # a ref from data/gap_map.csv
        dataset: mospi_nas_2026_s1_1     # a dataset of this unit
        series_ids: [s1_1.pfce.current]  # all must have a row in `period`
        period: '2023-24'                # optional; default the SAM reference year
        extent: control_total            # full | partial | control_total
        note: PFCE total only; the commodity split comes from the SUT unit.

A ref is `covered` if at least one entry with extent `full` passes, `partial` if only
partial/control_total entries pass, `missing` if nothing is declared, and `BROKEN` if an entry
is declared but its data is not there (a failure).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from pipeline.core import io
from pipeline.core.paths import REFERENCE_YEAR, Layout
from pipeline.core.unit import unit_names

EXTENTS = ("full", "partial", "control_total")


@dataclass
class EntryResult:
    unit: str
    ref: str
    dataset: str
    extent: str
    ok: bool
    detail: str


def load_gap_map(layout: Layout) -> pl.DataFrame:
    return pl.read_csv(layout.gap_map, infer_schema_length=0)


def coverage_files(layout: Layout, units: list[str] | None = None) -> dict[str, Path]:
    out = {}
    for u in unit_names(layout):
        if units is not None and u not in units:
            continue
        p = layout.ingest_dir / f"{u}_coverage.yaml"
        if p.exists():
            out[u] = p
    return out


def check_entries(layout: Layout, units: list[str] | None = None) -> tuple[list[EntryResult], list[str]]:
    gm = load_gap_map(layout)
    refs = set(gm["ref"].to_list())
    results: list[EntryResult] = []
    errors: list[str] = []
    if units is not None:
        errors.extend(f"no unit {u!r} in pipeline/ingest" for u in units if u not in unit_names(layout))
    for unit, path in coverage_files(layout, units).items():
        doc: dict[str, Any] = io.read_yaml(path) or {}
        if doc.get("unit") != unit:
            errors.append(f"{path.name}: unit is {doc.get('unit')!r}, expected {unit!r}")
            continue
        for i, e in enumerate(doc.get("entries") or []):
            where = f"{path.name} entry {i + 1}"
            ref, dataset, extent = e.get("ref"), e.get("dataset"), e.get("extent", "partial")
            sids = e.get("series_ids") or []
            period = str(e.get("period", REFERENCE_YEAR))
            if ref not in refs:
                errors.append(f"{where}: ref {ref!r} is not in data/gap_map.csv")
                continue
            if extent not in EXTENTS:
                errors.append(f"{where}: extent must be one of {EXTENTS}")
                continue
            if not dataset or not sids:
                errors.append(f"{where}: dataset and series_ids are required")
                continue
            f = layout.clean / unit / f"{dataset}.parquet"
            if not f.exists():
                results.append(EntryResult(unit, ref, dataset, extent, False, f"{f.name} not built"))
                continue
            df = pl.read_parquet(f, columns=["series_id", "period"])
            have = set(df.filter(pl.col("period") == period)["series_id"].to_list())
            absent = [s for s in sids if s not in have]
            ok = not absent
            detail = f"{len(sids)} series in {period}" if ok else f"missing in {period}: {absent[:5]}"
            results.append(EntryResult(unit, ref, dataset, extent, ok, detail))
    return results, errors


def report(layout: Layout, json_out: Path | None = None, units: list[str] | None = None) -> int:
    """Print the coverage table. With `units`, only those units' entries count (and only the refs
    they declare are listed), so one agent's unfinished unit does not fail another's check.
    Returns 1 if a counted entry is BROKEN or a counted coverage file has errors."""
    gm = load_gap_map(layout)
    results, errors = check_entries(layout, units)
    if units is not None:
        declared = {r.ref for r in results}
        gm = gm.filter(pl.col("ref").is_in(sorted(declared)))
        print(f"coverage for unit(s) {', '.join(units)}: {len(declared)} gap-map ref(s) declared")
    by_ref: dict[str, list[EntryResult]] = {}
    for r in results:
        by_ref.setdefault(r.ref, []).append(r)
    rows = []
    for g in gm.iter_rows(named=True):
        rs = by_ref.get(g["ref"], [])
        if any(not r.ok for r in rs):
            state = "BROKEN"
        elif any(r.extent == "full" for r in rs):
            state = "covered"
        elif rs:
            state = "partial"
        else:
            state = "missing"
        rows.append(
            {
                "ref": g["ref"],
                "gap_status": g["status"],
                "coverage": state,
                "by": ";".join(sorted({f"{r.unit}/{r.dataset}({r.extent})" for r in rs})),
                "detail": "; ".join(r.detail for r in rs if not r.ok),
            }
        )
    table = pl.DataFrame(
        rows,
        schema={"ref": pl.String, "gap_status": pl.String, "coverage": pl.String, "by": pl.String, "detail": pl.String},
        orient="row",
    )
    order = {"OFFICIAL": 0, "INTERNATIONAL": 1, "ESTIMATED": 2}
    shown = (
        table.with_columns(pl.col("gap_status").replace_strict(order, default=9).alias("_o"))
        .sort("_o", maintain_order=True)
        .drop("_o")
    )
    with pl.Config(tbl_rows=200, fmt_str_lengths=70, tbl_width_chars=220):
        print(shown)
    off = table.filter(pl.col("gap_status") == "OFFICIAL")
    counts = off.group_by("coverage", maintain_order=True).len().sort("coverage")
    print("\nOFFICIAL cells:", ", ".join(f"{c}={n}" for c, n in counts.iter_rows()), f"(of {off.height})")
    for e in errors:
        print(f"ERROR: {e}")
    if json_out:
        io.write_json(json_out, {"refs": table.to_dicts(), "errors": errors})
    broken = table.filter(pl.col("coverage") == "BROKEN").height
    return 1 if (errors or broken) else 0


def as_json(layout: Layout) -> str:  # pragma: no cover - convenience
    results, errors = check_entries(layout)
    return json.dumps({"entries": [r.__dict__ for r in results], "errors": errors}, indent=2)
