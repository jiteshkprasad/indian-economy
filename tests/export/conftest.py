"""Shared helpers for tests/export (Phase 3 data export, docs/phase3/PLAN.md s.5.1). Owner: U1.

`exported("real")` reads web/public/data, `exported("fixture")` reads web/fixtures/data. Both must have been
written by `uv run python -m pipeline export` / `export --fixture`; test_export_current.py checks they are
current. Tests that need the real export skip with an explicit reason when it does not exist.
"""

from __future__ import annotations

import pytest
from _export_helpers import Export, exported


@pytest.fixture(params=["real", "fixture"])
def ex(request: pytest.FixtureRequest) -> Export:
    return exported(request.param)


@pytest.fixture
def real() -> Export:
    return exported("real")


@pytest.fixture
def fixture_export() -> Export:
    return exported("fixture")
