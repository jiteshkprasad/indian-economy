"""V1-07 / V5-08: a cited source that is only in data/registry_additions/ (unverified until the orchestrator
merges it into data/registry.yaml) is exported with registry_status 'unverified', so the site says so; a
source in registry.yaml is never labelled unverified by the exporter. The test prints the additions-only ids."""

from __future__ import annotations

import pytest
import yaml
from _export_helpers import REPO

pytestmark = pytest.mark.export


def test_sources_outside_registry_yaml_are_marked_unverified(real) -> None:
    reg = yaml.safe_load((REPO / "data" / "registry.yaml").read_text(encoding="utf-8"))
    merged = {s["id"] for s in reg["sources"]}
    sources = real.get("provenance.json")["sources"]
    outside = sorted(sid for sid in sources if sid not in merged)
    print("cited sources only in registry additions (unverified):", outside)
    for sid in outside:
        assert sources[sid]["registry_status"] == "unverified", sid
