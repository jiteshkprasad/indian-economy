"""The JSON Schemas are current and every exported file validates (PLAN s.3.6, s.3.10)."""

from __future__ import annotations

import pytest

from pipeline.export.schemas import SCHEMA_DIR, rendered
from pipeline.export.validate import validate_file

pytestmark = pytest.mark.export


def test_schema_files_current() -> None:
    for name, text in rendered().items():
        assert (SCHEMA_DIR / name).read_text(encoding="utf-8") == text, (
            f"{name} is stale: run python -m pipeline.export.schemas"
        )


def test_every_file_validates(ex) -> None:
    assert not validate_file("index.json", ex.index)
    for rel in ex.files():
        errs = validate_file(rel, ex.get(rel))
        assert not errs, (rel, errs[:3])


def test_index_and_version(ex) -> None:
    import re

    assert re.match(r"^\d{4}-\d{2}\.([0-9a-f]{10}|fixture0000)$", ex.version)
    assert ex.index["fixture"] == ex.version.endswith("fixture0000")
    required = {"summary.json", "hierarchy.json", "sam/cells.json", "sam/pinned.json", "sam/constraints.json",
                "sam/refs.json", "provenance.json", "ts/series.json", "ts/view.json", "ts/cover.json"}  # fmt: skip
    assert required <= set(ex.files())
    assert sum(1 for f in ex.files() if f.startswith("sam/entries/")) == 13
    assert sum(1 for f in ex.files() if f.startswith("stories/")) == 3
