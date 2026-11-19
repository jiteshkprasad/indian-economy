"""Network canaries: marked `live`, skipped by default. Run: uv run python -m pipeline test -m live

They fetch into a scratch folder (never into data/) and check that the sources the template unit
uses are still reachable, still served without a challenge, and still byte-identical to the pins.
"""

import pytest

from pipeline.core.fetch import PinStore
from pipeline.core.paths import Layout
from pipeline.core.runner import fetch_module
from pipeline.ingest import mospi_nas_2026 as U

pytestmark = pytest.mark.live


def test_mospi_nas_2026_still_served_and_unchanged(tmp_path):
    scratch = Layout.scratch(tmp_path)
    r = fetch_module(U, scratch)
    assert r.ok, r.message
    fresh = PinStore.load(scratch, U.UNIT).pins
    pinned = PinStore.load(Layout.default(), U.UNIT).pins
    changed = [k for k in pinned if k.endswith(".xlsx") and fresh[k]["sha256"] != pinned[k]["sha256"]]
    assert not changed, f"upstream changed since pinning (new vintage?): {changed}"
