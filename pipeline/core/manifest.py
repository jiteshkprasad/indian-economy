"""data/manifest.json: sha256 of every clean file + deterministic code hashes (no timestamps, no git).

The manifest is regenerated after every build from what is on disk, so it always describes the
current data/clean tree. Text is hashed with LF line endings so Windows and Linux checkouts agree.

- `code_hash` covers pipeline/ and models/ sources (CODE_SUFFIXES: *.py, *.yaml, and data specs a
  unit reads at build time such as *.json) and uv.lock: the whole code base.
- `unit_code_hashes` has one hash per built unit over only what can change that unit's output: the
  shared framework (pipeline/*.py, pipeline/core/**, pipeline/ingest/__init__.py), the unit's own
  files (pipeline/ingest/<unit>.py or <unit>/**, _<unit>_*.py, <unit>_coverage.yaml) and uv.lock.
  A DEPENDS unit has its own entry (repro rebuilds it too). `repro UNIT` compares these, so an edit
  to an unrelated unit during the three builds no longer fails a unit-scoped repro.
- Phase 2: `files` also holds every SAM output under data/sam/ (*.parquet, *.json, *.csv) and the
  generated BALANCING.md, so `manifest --check` and a full `repro` cover them. pipeline/sam/** is
  in `code_hash` (not in any unit's scoped hash: SAM code cannot change a Phase 1 unit's output).
  The post-SAM time series (data/timeseries/*.parquet, DECISIONS D2-18) is hashed the same way.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import polars as pl
import pyarrow.parquet as pq

from pipeline.core import io
from pipeline.core.locks import file_lock
from pipeline.core.paths import Layout
from pipeline.core.schema import SCHEMA_VERSION

CODE_DIRS = ("pipeline", "models")
# Everything under pipeline/ and models/ that can change a build: code, YAML, and the spec/lookup
# files units read at build time (e.g. pipeline/ingest/mospi_nas_2026/spec_*.json). A test fails if
# a file with any other suffix appears there, so a new kind of spec file cannot go unhashed.
CODE_SUFFIXES = (".py", ".yaml", ".yml", ".json", ".csv", ".tsv", ".txt", ".toml")
# Files under data/sam/ and data/timeseries/ that the manifest hashes (Phase 2 outputs).
SAM_SUFFIXES = (".parquet", ".json", ".csv")


def _code_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for d in CODE_DIRS:
        base = root / d
        if not base.exists():
            continue
        for p in base.rglob("*"):
            if p.is_file() and p.suffix in CODE_SUFFIXES and "__pycache__" not in p.parts:
                files.append(p)
    lock = root / "uv.lock"
    if lock.exists():
        files.append(lock)
    return sorted(files, key=lambda p: p.relative_to(root).as_posix())


def _hash_files(root: Path, files: list[Path]) -> str:
    h = hashlib.sha256()
    for p in files:
        data = p.read_bytes().replace(b"\r\n", b"\n")
        h.update(p.relative_to(root).as_posix().encode() + b"\0")
        h.update(hashlib.sha256(data).digest())
    return h.hexdigest()


def code_hash(root: Path | None = None) -> str:
    """Hash of the whole code base (every file of _code_files)."""
    root = root or Layout.default().root
    return _hash_files(root, _code_files(root))


def unit_code_files(root: Path, unit: str) -> list[Path]:
    """The files that can change `unit`'s build output: shared framework + the unit's own files + uv.lock."""
    ingest = root / "pipeline" / "ingest"
    out: list[Path] = []
    for p in _code_files(root):
        rel = p.relative_to(root)
        parts = rel.parts
        if parts[0] != "pipeline":
            if rel.as_posix() == "uv.lock":
                out.append(p)
            continue  # models/ is not an ingest dependency
        if len(parts) == 2 or parts[1] == "core":  # pipeline/*.py, pipeline/core/**
            out.append(p)
            continue
        if parts[1] != "ingest":
            continue
        own = p.parent == ingest and (
            p.name in (f"{unit}.py", f"{unit}_coverage.yaml", "__init__.py")
            or (p.name.startswith(f"_{unit}_") and p.suffix == ".py")
        )
        if own or (len(parts) > 3 and parts[2] == unit):  # pipeline/ingest/<unit>/**
            out.append(p)
    return out


def unit_code_hash(root: Path, unit: str) -> str:
    return _hash_files(root, unit_code_files(root, unit))


def schema_hash(path: Path) -> str:
    schema = pq.read_schema(path)
    text = ";".join(f"{f.name}:{f.type}" for f in schema)
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def build_manifest(layout: Layout) -> dict[str, Any]:
    files: dict[str, Any] = {}
    if layout.clean.exists():
        found = [*layout.clean.rglob("*.parquet"), *layout.clean.glob("*/_datasets.json")]
        for p in sorted(found, key=lambda q: q.as_posix()):
            if any(part.startswith(".") for part in p.relative_to(layout.clean).parts):
                continue
            rel = "data/clean/" + p.relative_to(layout.clean).as_posix()
            if p.suffix == ".parquet":
                files[rel] = {
                    "sha256": io.sha256_file(p),
                    "rows": pq.read_metadata(p).num_rows,
                    "schema_hash": schema_hash(p),
                }
            else:
                files[rel] = {"sha256": io.sha256_file(p)}
    # Phase 2: SAM outputs (data/sam/<year>/**) and the generated BALANCING.md are hashed too, so
    # `manifest --check` and `repro` cover them (docs/phase2/SAM_GUIDE.md).
    # The post-SAM time series (data/timeseries/, next to data/sam in every layout) is covered the same way.
    for name, tree in (("sam", layout.sam), ("timeseries", layout.clean.parent / "timeseries")):
        if not tree.exists():
            continue
        found = [p for p in tree.rglob("*") if p.is_file() and p.suffix in SAM_SUFFIXES]
        for p in sorted(found, key=lambda q: q.as_posix()):
            if any(part.startswith(".") for part in p.relative_to(tree).parts):
                continue
            rel = f"data/{name}/" + p.relative_to(tree).as_posix()
            if p.suffix == ".parquet":
                files[rel] = {
                    "sha256": io.sha256_file(p),
                    "rows": pq.read_metadata(p).num_rows,
                    "schema_hash": schema_hash(p),
                }
            else:
                files[rel] = {"sha256": io.sha256_file(p)}
    if layout.balancing_report.exists():
        files["BALANCING.md"] = {"sha256": io.sha256_file(layout.balancing_report)}
    pins: dict[str, Any] = {}
    if layout.pins.exists():
        for p in sorted(layout.pins.glob("*.yaml")):
            doc = io.read_yaml(p) or {}
            pins[p.stem] = {k: v["sha256"] for k, v in sorted((doc.get("pins") or {}).items())}
    built = sorted(
        p.name
        for p in (layout.clean.iterdir() if layout.clean.exists() else [])
        if p.is_dir() and not p.name.startswith(".")
    )
    return {
        "manifest_version": 1,
        "schema_version": SCHEMA_VERSION,
        "code_hash": code_hash(layout.root),
        "unit_code_hashes": {u: unit_code_hash(layout.root, u) for u in built},
        "files": files,
        "raw_pins": pins,
    }


def write_manifest(layout: Layout) -> dict[str, Any]:
    m = build_manifest(layout)
    io.write_json(layout.manifest, m)
    return m


def read_manifest(path: Path) -> dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def diff_manifests(a: dict[str, Any], b: dict[str, Any], prefix: str = "") -> list[str]:
    """Human-readable differences in the `files` sections (restricted to paths starting with prefix)."""
    fa = {k: v for k, v in a.get("files", {}).items() if k.startswith(prefix)}
    fb = {k: v for k, v in b.get("files", {}).items() if k.startswith(prefix)}
    out = []
    for k in sorted(set(fa) | set(fb)):
        if k not in fa:
            out.append(f"only in second: {k}")
        elif k not in fb:
            out.append(f"only in first: {k}")
        elif fa[k] != fb[k]:
            out.append(f"differs: {k} ({fa[k]['sha256'][:12]} vs {fb[k]['sha256'][:12]})")
    return out


def frames_equal_within(a: Path, b: Path, rel_tol: float = 1e-9) -> bool:
    """Tolerance comparison used only to explain a byte difference in repro reports."""
    da, db = pl.read_parquet(a), pl.read_parquet(b)
    if da.columns != db.columns or da.height != db.height:
        return False
    for c in da.columns:
        if da[c].dtype == pl.Float64:
            pair = pl.DataFrame({"x": da[c], "y": db[c]})
            ok = pair.select(
                (
                    (pl.col("x") - pl.col("y")).abs()
                    <= rel_tol * pl.max_horizontal(pl.col("x").abs(), pl.col("y").abs(), pl.lit(1.0))
                ).all()
            ).item()
            if not ok:
                return False
        elif not da[c].equals(db[c]):
            return False
    return True


@contextmanager
def repo_lock(layout: Layout, timeout_s: float = 900) -> Iterator[None]:
    """Serialise writes to data/clean and data/manifest.json between concurrent pipeline processes.

    An OS lock (pipeline.core.locks): if the holder is killed, the lock goes with it, so a crashed
    agent never blocks the others. Held only while files are written (seconds)."""
    with file_lock(layout.lock, timeout_s=timeout_s, what="the data/clean write lock"):
        yield
