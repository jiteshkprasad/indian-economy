"""Everything the exporter reads, gathered into one `ExportInputs` (docs/phase3/PLAN.md s.3.1).

`load_real(layout)` reads the committed pipeline outputs (read-only). `pipeline/export/fixture.py` builds a
synthetic `ExportInputs` on the real accounts and hierarchy, and both go through the same writer
(`pipeline/export/build.py`), so the fixture has exactly the shape of the real export.
"""

from __future__ import annotations

import glob
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from pipeline.core import io
from pipeline.core.paths import Layout
from pipeline.export.hierarchy import Hierarchy, load_hierarchy

EXPORT_DIR = Path(__file__).resolve().parent
YEAR = "2023-24"
GDP_BASE = "2022-23"


class ExportError(RuntimeError):
    """The export cannot go on; the message names the item (PLAN s.3.1: no silent fallbacks)."""


@dataclass
class ExportInputs:
    hierarchy: Hierarchy
    sam: pl.DataFrame  # row, col, value (balanced SAM, unrounded)
    entries: pl.DataFrame  # balanced entries + log columns (explanation_required, binding, pct_change, ...)
    items: dict[tuple[str, str, str, str], dict[str, Any]]  # current explanation items: key -> {verdict, why}
    constraints: pl.DataFrame  # constraints.parquet joined with balancing_constraints (lo, hi, balanced_sum, binding)
    members: dict[str, np.ndarray]  # constraint id -> entry row indices (pipeline's own selector)
    prov: dict[str, dict[str, Any]]  # every provenance record (SAM, time series, clean), by prov id
    registry: dict[str, dict[str, Any]]  # source id -> registry entry
    gap_map: dict[str, dict[str, str]]  # ref -> gap map row
    run: dict[str, Any]  # balancing_run.json
    ts: pl.DataFrame  # top_flows.parquet
    ts_defs: pl.DataFrame  # top_flows_definitions.parquet
    ts_check: pl.DataFrame  # top_flows_sam_check.parquet
    ts_flows: dict[str, Any]  # flow id -> pipeline.timeseries.build.Flow (sam_terms for the entry selector)
    config: dict[str, Any]  # the curated YAML files of pipeline/export/
    stories: dict[str, dict[str, Any]]  # slug -> story spec (pipeline/export/stories/<slug>.yaml)
    satellites: dict[str, pl.DataFrame] = field(default_factory=dict)  # "<block>/<name>" -> frame (lazy for real)
    input_hashes: dict[str, str] = field(default_factory=dict)  # repo path -> sha256
    fixture: bool = False
    layout: Layout | None = None
    gdp_sam_check: float | None = None  # GDP from the SAM's production side (real data only)
    # published (clean) figures the exporter checks SAM sums against: name -> (value, prov id); real data only
    published: dict[str, tuple[float, str]] = field(default_factory=dict)

    def satellite(self, table: str) -> pl.DataFrame:
        if table not in self.satellites:
            if self.layout is None:
                raise ExportError(f"satellite table {table!r} is not available")
            block, _, name = table.partition("/")
            path = self.layout.sam / YEAR / "blocks" / f"{block}_satellites" / f"{name}.parquet"
            if not path.exists():
                raise ExportError(f"story satellite table {table!r} not found at {path}")
            self.satellites[table] = pl.read_parquet(path)
            self.input_hashes[_rel(self.layout, path)] = io.sha256_file(path)
        return self.satellites[table]


def _rel(layout: Layout, p: Path) -> str:
    return Path(p).resolve().relative_to(layout.root.resolve()).as_posix()


def load_config() -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    for name in ("judgement_bands", "old_base_scope", "disc_text", "link_policy", "ts_view"):
        path = EXPORT_DIR / f"{name}.yaml"
        if not path.exists():
            raise ExportError(f"curated list pipeline/export/{name}.yaml is missing")
        cfg[name] = io.read_yaml(path) or {}
    return cfg


def load_stories() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for p in sorted((EXPORT_DIR / "stories").glob("*.yaml")):
        doc = io.read_yaml(p) or {}
        slug = doc.get("slug")
        if slug != p.stem:
            raise ExportError(f"pipeline/export/stories/{p.name}: slug {slug!r} must equal the file name {p.stem!r}")
        out[slug] = doc
    return out


def constraint_members(entries: pl.DataFrame, constraints: pl.DataFrame, accounts: list[str]) -> dict[str, np.ndarray]:
    """Member entries of every constraint, with the pipeline's own selector (balance.problem_from_frames)."""
    from pipeline.sam.balance import problem_from_frames

    ent = entries.select(
        "row", "col", "ref", "component", pl.col("prior").alias("value"), "role", "tol_rel", "confidence"
    )
    p = problem_from_frames(ent, constraints, accounts)
    return {c.constraint_id: c.members for c in p.constraints}


def explanation_items(log: pl.DataFrame) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    from pipeline.sam.report import current_items, load_explanations, verdict

    out: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for key, it in current_items(log, load_explanations()):
        why = " ".join(str(it.get("why", "")).split())
        v = verdict(why)
        if v not in ("explained", "level unexplained", "unexplained"):
            raise ExportError(f"explanation item {key} has no verdict word ({v!r})")
        out[tuple(key)] = {"verdict": v, "why": why}
    return out


def load_real(layout: Layout) -> ExportInputs:
    from pipeline.core.registry import load_registry
    from pipeline.sam.accounts import gap_map as read_gap_map
    from pipeline.timeseries.build import load_definitions

    hashes: dict[str, str] = {}

    def track(p: Path) -> Path:
        if not p.exists():
            raise ExportError(f"input {p} does not exist (run the pipeline first)")
        hashes[_rel(layout, p)] = io.sha256_file(p)
        return p

    sam_dir = layout.sam / YEAR
    sam = pl.read_parquet(track(sam_dir / "sam_balanced.parquet"))
    ent = pl.read_parquet(track(sam_dir / "sam_entries_balanced.parquet"))
    log = pl.read_parquet(track(sam_dir / "balancing_log.parquet"))
    key = ["row", "col", "ref", "component"]
    if ent.height != log.height or not ent.select(key).equals(log.select(key)):
        raise ExportError("sam_entries_balanced.parquet and balancing_log.parquet are not in the same row order")
    entries = ent.with_columns(
        log["explanation_required"], log["binding"], log["pct_change"], log["cell_explanation_required"]
    )
    cons = pl.read_parquet(track(sam_dir / "constraints.parquet"))
    bcons = pl.read_parquet(track(sam_dir / "balancing_constraints.parquet"))
    if sorted(cons["constraint_id"].to_list()) != sorted(bcons["constraint_id"].to_list()):
        raise ExportError("constraints.parquet and balancing_constraints.parquet list different constraint ids")
    constraints = cons.join(
        bcons.select("constraint_id", "lo", "hi", "balanced_sum", "binding", "n_members"),
        on="constraint_id",
        how="left",
        maintain_order="left",
    )
    run = io.read_yaml(track(sam_dir / "balancing_run.json"))  # JSON is YAML
    track(sam_dir / "_provenance.parquet")

    prov: dict[str, dict[str, Any]] = {}
    files = [sam_dir / "_provenance.parquet", layout.clean.parent / "timeseries" / "_provenance.parquet"]
    files += sorted(Path(p) for p in glob.glob(str(layout.clean / "*" / "_provenance.parquet")))
    for f in files:
        for r in pl.read_parquet(track(f)).iter_rows(named=True):
            if r["prov_id"] in prov:
                raise ExportError(f"provenance id {r['prov_id']} appears in more than one provenance file")
            prov[r["prov_id"]] = r

    ts_dir = layout.clean.parent / "timeseries"
    ts = pl.read_parquet(track(ts_dir / "top_flows.parquet"))
    ts_defs = pl.read_parquet(track(ts_dir / "top_flows_definitions.parquet"))
    ts_check = pl.read_parquet(track(ts_dir / "top_flows_sam_check.parquet"))
    defs = load_definitions(layout=layout)
    ts_flows = {f.flow_id: f for f in defs.flows}

    track(layout.registry)
    track(layout.gap_map)
    for p in sorted((layout.root / "pipeline" / "sam" / "explanations").glob("*.yaml")):
        track(p)
    track(layout.root / "pipeline" / "sam" / "accounts.yaml")
    hier = load_hierarchy()
    members = constraint_members(entries, constraints, hier.codes)
    gm = read_gap_map(str(layout.gap_map))
    gdp_sam = _gdp_production_side(sam)
    published = {
        # NAS derived saving-investment errors and omissions (X_DISC D3, both components; requests/U6.md V2-02)
        "nas_si_errors": _clean_value(
            track(layout.clean / "mospi_nas_2026" / "mospi_nas_2026_derived_residuals.parquet"),
            "derived.si_errors_omissions.current",
        ),
    }
    inp = ExportInputs(
        hierarchy=hier,
        sam=sam,
        entries=entries,
        items=explanation_items(log),
        constraints=constraints,
        members=members,
        prov=prov,
        registry=load_registry(layout),
        gap_map={k: dict(v) for k, v in gm.items()},
        run=run,
        ts=ts,
        ts_defs=ts_defs,
        ts_check=ts_check,
        ts_flows=ts_flows,
        config=load_config(),
        stories=load_stories(),
        input_hashes=hashes,
        layout=layout,
        gdp_sam_check=gdp_sam,
        published=published,
    )
    return inp


def _clean_value(path: Path, series_id: str) -> tuple[float, str]:
    """The one new-base 2023-24 value of a clean series, with its prov id (fails unless exactly one row)."""
    d = pl.read_parquet(path).filter(
        (pl.col("series_id") == series_id) & (pl.col("period") == YEAR) & (pl.col("base_year") == GDP_BASE)
    )
    if d.height != 1:
        raise ExportError(f"{path.name}: expected one {YEAR} row of {series_id} (base {GDP_BASE}), found {d.height}")
    return float(d["value"][0]), str(d["prov_id"][0])


def _gdp_production_side(sam: pl.DataFrame) -> float:
    """GDP at market prices from the SAM's production side: value added (factor payments by activities and
    production taxes less subsidies on activities) plus taxes less subsidies on products (tax accounts paid by
    commodities). Checked against M01 within Rs 1 crore (PLAN s.3.3)."""
    act = sam.filter(pl.col("col").str.starts_with("A_"))
    va = act.filter(pl.col("row").str.starts_with("F_") | (pl.col("row") == "T_PROD"))["value"].sum()
    ptax = sam.filter(pl.col("col").str.starts_with("C_") & pl.col("row").str.starts_with("T_"))["value"].sum()
    return float(va + ptax)
