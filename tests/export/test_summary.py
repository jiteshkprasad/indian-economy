"""summary.methodology: every key the methodology page binds to (docs/phase3/requests/U6.md), and the rule
constants equal the constants the pipeline applies (no retyped numbers)."""

from __future__ import annotations

import pytest

from pipeline.export.pinned import PIN_ABS, PIN_REL
from pipeline.export.status import SPLIT_SHARE
from pipeline.sam.spec import EXPLAIN_ABS, EXPLAIN_MIN_ABS, EXPLAIN_REL

pytestmark = pytest.mark.export

U6_KEYS = {
    "hces_pfce_coverage", "hh_factor_income", "disc_d1", "disc_d2", "disc_d3_valuables", "disc_d3_si_errors",
    "disc_d4", "judgement_bands", "judgement_band_entries", "judgement_band_abs", "old_base_entries",
    "old_base_abs", "constraints", "constraints_binding", "explain_entries", "explain_entries_explained",
    "explain_entries_level_unexplained", "explain_entries_unexplained", "explain_cells", "explain_cells_explained",
    "explain_cells_level_unexplained", "explain_cells_unexplained", "moved_abs_gdp", "ts_linked_flows",
    "ts_segment_joins", "ts_base_changes", "ts_concept_breaks", "ts_check_pass", "ts_check_explained",
    "ts_check_none", "sources", "sources_withheld", "withheld_urls", "assumption_records",
    "explain_abs", "explain_small_abs", "explain_small_rel", "pin_width_abs", "pin_width_rel", "split_headline_min",
}  # fmt: skip

RULES = {
    "explain_abs": (EXPLAIN_ABS, "inr"),
    "explain_small_abs": (EXPLAIN_MIN_ABS, "inr"),
    "explain_small_rel": (EXPLAIN_REL, "pct"),
    "pin_width_abs": (PIN_ABS, "inr"),
    "pin_width_rel": (PIN_REL, "pct"),
    "split_headline_min": (SPLIT_SHARE, "pct"),
}


def test_methodology_has_every_requested_key(ex) -> None:
    m = ex.get("summary.json")["methodology"]
    missing = U6_KEYS - set(m)
    assert not missing, sorted(missing)
    for k, x in m.items():
        assert x["unit"] in ("inr", "pct_gdp", "pct", "count"), k
        if x["unit"] == "count":
            assert x["value"] == int(x["value"]) and x["value"] >= 0, k


def test_rule_constants_come_from_the_code(ex) -> None:
    m = ex.get("summary.json")["methodology"]
    for k, (v, unit) in RULES.items():
        assert m[k] == {"value": v, "unit": unit, "prov": []}, k


# headline part -> the level-0 node(s) receiving it (summary.HH_PARTS); single-node parts have a link id
_PART_LINK = {
    "consumption": "HH--PRDS",
    "saving": "HH--SI",
    "taxes": "HH--TAX",
    "transfers_abroad": "HH--ROW",
    "unallocated_residual": "HH--DISC",
}


def test_headline_parts_carry_total_labels(ex) -> None:
    """Each 'of every Rs 100' part says whether its total is held to a published figure (V1-03, V5-04), with
    the same answer as the map's link for that part (sam/pinned.json)."""
    pinned = ex.get("sam/pinned.json")
    parts = ex.get("summary.json")["headline"]["hh_outlays"]["parts"]
    for p in parts:
        assert (p["total_label"] is None) == (not p["pins"]), p["key"]
        link = _PART_LINK.get(p["key"])
        if link is None:
            continue
        pin = pinned.get(link + "~pair") or pinned.get(link)
        if pin is None:
            assert p["total_label"] is None, p["key"]
        else:
            assert (p["total_label"], p["pins"]) == (pin["total"], pin["pins"]), p["key"]


def test_headline_official_totals_on_real_data(real) -> None:
    """PLAN s.3.4.2: household consumption (PFCE) and household saving are official totals; the D1 residual
    is a derived (published residual) total."""
    by = {p["key"]: p for p in real.get("summary.json")["headline"]["hh_outlays"]["parts"]}
    assert by["consumption"]["total_label"] == "official"
    assert by["saving"]["total_label"] == "official"
    assert by["unallocated_residual"]["total_label"] == "derived"


# economic values on the methodology page (sums of SAM entries) carry status fields (V5-03); counts do not
_ECON = {
    "hh_factor_income", "disc_d1", "disc_d2", "disc_d3", "disc_d3_valuables", "disc_d3_si_errors", "disc_d4",
    "judgement_band_abs", "old_base_abs",
}  # fmt: skip


def test_methodology_economic_values_carry_labels(ex) -> None:
    m = ex.get("summary.json")["methodology"]
    for k, x in m.items():
        if k not in _ECON:
            assert not {"split_label", "total_label", "pins"} & set(x), k
            continue
        if x["value"] == 0:  # no split label for a zero amount (PLAN s.3.4.2); the page says it is zero
            assert "split_label" not in x, k
            continue
        assert x["split_label"] in ("official", "derived", "estimated", "balancing_set"), k
        assert x["total_label"] in ("official", "derived", None), k
        assert (x["total_label"] is None) == (not x["pins"]), k


def test_methodology_d1_matches_the_first_screen_part(ex) -> None:
    """X_DISC D1 entries are exactly the household -> DISC link, so its label is the first screen's."""
    s = ex.get("summary.json")
    d1 = s["methodology"]["disc_d1"]
    part = next(p for p in s["headline"]["hh_outlays"]["parts"] if p["key"] == "unallocated_residual")
    assert d1["value"] == pytest.approx(part["value"], abs=0.01)
    assert (d1["split_label"], d1["total_label"], d1["pins"]) == (
        part["split_label"],
        part["total_label"],
        part["pins"],
    )


def test_methodology_disc_d3_is_the_nas_si_errors(real) -> None:
    """V2-02: the whole D3 (both components) equals the NAS derived saving-investment errors and omissions for
    2023-24, recomputed here from the parquet files, and its prov names that NAS record."""
    import polars as pl
    from _export_helpers import REPO, SAM

    m = real.get("summary.json")["methodology"]
    ent = pl.read_parquet(SAM / "sam_entries_balanced.parquet").filter(pl.col("ref") == "D3")
    nas = pl.read_parquet(
        REPO / "data" / "clean" / "mospi_nas_2026" / "mospi_nas_2026_derived_residuals.parquet"
    ).filter(
        (pl.col("series_id") == "derived.si_errors_omissions.current")
        & (pl.col("period") == "2023-24")
        & (pl.col("base_year") == "2022-23")
    )
    assert nas.height == 1
    assert m["disc_d3"]["value"] == pytest.approx(float(ent["value"].sum()), abs=0.01)
    assert m["disc_d3"]["value"] == pytest.approx(float(nas["value"][0]), abs=0.01)
    assert m["disc_d3"]["value"] == pytest.approx(
        m["disc_d3_valuables"]["value"] + m["disc_d3_si_errors"]["value"], abs=0.02
    )
    assert nas["prov_id"][0] in m["disc_d3"]["prov"]
