"""Generic contract tests over every clean dataset on disk (data/clean/<unit>/<dataset>.parquet).

These run for every unit automatically; units add their own value tests in tests/units/.
"""

import json
from functools import cache
from pathlib import Path

import polars as pl
import pytest

from pipeline.core import io
from pipeline.core.fetch import PinStore
from pipeline.core.manifest import build_manifest
from pipeline.core.paths import Layout
from pipeline.core.registry import source_ids
from pipeline.core.runner import PROVENANCE_FILE, clean_files
from pipeline.core.schema import CLEAN_KEY, PROV_KEY, validate_clean, validate_provenance
from pipeline.core.unit import unit_names

pytestmark = pytest.mark.schema
LAYOUT = Layout.default()
FILES = clean_files(LAYOUT)
IDS = [p.relative_to(LAYOUT.clean).as_posix() for p in FILES]
UNIT_DIRS = sorted({p.parent for p in FILES})


@cache
def _read(p: Path) -> pl.DataFrame:
    return pl.read_parquet(p)


def test_there_is_clean_data():
    assert FILES, "no clean datasets on disk: run `uv run python -m pipeline build`"


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_schema_and_naming(path):
    df = _read(path)
    validate_clean(df, path.name)
    unit = path.parent.name
    assert unit in unit_names(LAYOUT), f"{unit}: no unit module pipeline/ingest/{unit}"
    assert df["dataset"].unique().to_list() == [path.stem]
    assert path.stem == unit or path.stem.startswith(unit + "_")


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_sources_registered(path):
    unknown = set(_read(path)["source_id"].unique().to_list()) - source_ids(LAYOUT)
    assert not unknown, f"source ids not in data/registry.yaml: {unknown}"


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_provenance_complete(path):
    df = _read(path)
    prov = _read(path.parent / PROVENANCE_FILE)
    missing = set(df["prov_id"].unique().to_list()) - set(prov["prov_id"].to_list())
    assert not missing, f"prov_ids without a provenance record: {sorted(missing)[:10]}"
    j = df.join(prov.select("prov_id", "status", "source_id", "vintage", "price_basis"), on="prov_id", suffix="_p")
    for c in ("status", "source_id", "vintage", "price_basis"):
        assert (j[c] == j[f"{c}_p"]).all(), f"{c} differs between rows and provenance"
    est = j.filter(pl.col("status") != "official")
    if est.height:
        methods = prov.filter(pl.col("prov_id").is_in(est["prov_id"].unique().to_list()))["method"]
        assert methods.null_count() == 0, "derived/estimated rows need a method in provenance"


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_file_is_canonical(path):
    """Written by pipeline.core.io: re-serialising gives the same bytes (sorted, rounded, no metadata)."""
    df = _read(path)
    assert io.sha256_bytes(io.parquet_bytes(df, sort_by=CLEAN_KEY)) == io.sha256_file(path)
    assert df.select(CLEAN_KEY).is_duplicated().sum() == 0


@pytest.mark.parametrize("unit_dir", UNIT_DIRS, ids=[d.name for d in UNIT_DIRS])
def test_unit_provenance_table(unit_dir):
    prov = _read(unit_dir / PROVENANCE_FILE)
    validate_provenance(prov, f"{unit_dir.name}/_provenance")
    assert io.sha256_bytes(io.parquet_bytes(prov, sort_by=PROV_KEY)) == io.sha256_file(unit_dir / PROVENANCE_FILE)
    assert set(prov["ingest_unit"].to_list()) == {unit_dir.name}
    pins = {p["path"]: p["sha256"] for p in PinStore.load(LAYOUT, unit_dir.name).pins.values()}
    for row in prov.filter(pl.col("raw_path").is_not_null()).iter_rows(named=True):
        assert pins.get(row["raw_path"]) == row["raw_sha256"], (
            f"{row['prov_id']}: raw file {row['raw_path']} is not the pinned one (re-run build after fetch)"
        )


def test_manifest_lists_the_files_on_disk():
    """The manifest's file hashes and raw pins match disk. code_hash is not compared here (any code
    edit changes it); `python -m pipeline manifest --check` and `repro` check it."""
    assert LAYOUT.manifest.exists(), "data/manifest.json missing: run `uv run python -m pipeline build`"
    have = json.loads(LAYOUT.manifest.read_text(encoding="utf-8"))
    want = build_manifest(LAYOUT)
    for part in ("files", "raw_pins", "schema_version"):
        assert have.get(part) == want[part], (
            f"data/manifest.json {part} is stale: run `uv run python -m pipeline build`"
        )


@pytest.mark.parametrize("unit_dir", UNIT_DIRS, ids=[d.name for d in UNIT_DIRS])
def test_unit_catalog(unit_dir):
    catalog = json.loads((unit_dir / "_datasets.json").read_text(encoding="utf-8"))
    on_disk = {p.stem for p in unit_dir.glob("*.parquet") if p.name != PROVENANCE_FILE}
    assert set(catalog) == on_disk
    for name, entry in catalog.items():
        assert entry["description"].strip(), f"{name}: empty description"
        assert entry["rows"] == _read(unit_dir / f"{name}.parquet").height
