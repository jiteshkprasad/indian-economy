"""Every pinned raw file is on disk and byte-identical to its pin (catches hand edits and missing
downloads). Missing files FAIL, they are not skipped: run `uv run python -m pipeline fetch`."""

import json

import pytest

from pipeline.core import io
from pipeline.core.fetch import PinStore, meta_path
from pipeline.core.paths import Layout
from pipeline.core.registry import registry_problems
from pipeline.core.unit import unit_names

pytestmark = pytest.mark.raw
LAYOUT = Layout.default()
PINS = [(u, key, pin) for u in unit_names(LAYOUT) for key, pin in sorted(PinStore.load(LAYOUT, u).pins.items())]


@pytest.mark.parametrize("unit, key, pin", PINS, ids=[f"{u}:{k}" for u, k, _ in PINS])
def test_pinned_raw_file(unit, key, pin):
    path = LAYOUT.raw_abs(pin["path"])
    assert path.exists(), f"{pin['path']} missing: run `uv run python -m pipeline fetch {unit}`"
    assert io.sha256_file(path) == pin["sha256"], f"{pin['path']} does not match its pin (edited?)"
    meta = json.loads(meta_path(path).read_text(encoding="utf-8"))
    assert meta["sha256"] == pin["sha256"] and meta["url"] and meta["retrieved_at"] == pin["retrieved_at"]
    source_id, name = key.split("/", 1)
    parts = pin["path"].split("/")  # data/raw/<source_id>/<date>[-rN]/<unit>/<name>
    assert parts[:3] == ["data", "raw", source_id] and parts[4:] == [unit, name], pin["path"]


@pytest.mark.parametrize("unit", sorted(p.stem for p in LAYOUT.registry_additions.glob("*.yaml")))
def test_registry_additions_valid(unit):
    """Each data/registry_additions/<unit>.yaml is checked on its own (`test -k <unit>`)."""
    problems = registry_problems(LAYOUT).get(unit, ())
    assert not problems, "\n".join(problems)


def test_pin_files_belong_to_units():
    orphans = [p.name for p in LAYOUT.pins.glob("*.yaml") if p.stem not in unit_names(LAYOUT)]
    assert not orphans, f"pin files without a unit module: {orphans}"
