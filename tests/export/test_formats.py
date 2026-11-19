"""pipeline/export/formats.py reproduces the golden display-format cases (PLAN s.3.3)."""

from __future__ import annotations

import json

import pytest
from _export_helpers import REPO

from pipeline.export.formats import fmt, group_en_in

pytestmark = pytest.mark.export


def test_golden_format_cases() -> None:
    g = json.loads((REPO / "pipeline/export/golden/format_cases.json").read_text(encoding="utf-8"))
    assert len(g["cases"]) >= 40
    kinds = {c["kind"] for c in g["cases"]}
    assert kinds == {"inr", "pct_gdp", "per100", "pct"}
    for c in g["cases"]:
        assert fmt(c["kind"], c["value"]) == c["out"], c


def test_grouping() -> None:
    assert group_en_in("1") == "1"
    assert group_en_in("1000") == "1,000"
    assert group_en_in("12345678") == "1,23,45,678"
    assert group_en_in("100000") == "1,00,000"
