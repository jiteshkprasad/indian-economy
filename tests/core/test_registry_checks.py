import polars as pl
import pytest
import yaml

from pipeline.core import checks
from pipeline.core.paths import Layout
from pipeline.core.policy import source_refusal, url_refusal
from pipeline.core.registry import (
    RegistryError,
    UnknownSourceError,
    get_source,
    registry_problems,
    require_sources,
    source_ids,
)

pytestmark = pytest.mark.unit


def test_registry_lookup():
    ids = source_ids()
    assert len(ids) > 50
    assert get_source("mospi_nas_2026_publication")["family"] == "mospi_nas"
    with pytest.raises(UnknownSourceError, match="not in data/registry.yaml"):
        get_source("no_such_source")
    with pytest.raises(UnknownSourceError, match="nope_a, nope_b"):
        require_sources(["mospi_nas_2026_publication", "nope_b", "nope_a"])


def _addition_layout(tmp_path, name, entry, units=("demo_unit", "other_unit", "third_unit")):
    root = tmp_path / "repo"
    (root / "data" / "registry_additions").mkdir(parents=True, exist_ok=True)
    (root / "pipeline" / "ingest").mkdir(parents=True, exist_ok=True)
    for u in units:
        (root / "pipeline" / "ingest" / f"{u}.py").write_text("", encoding="utf-8")
    (root / "data" / "registry.yaml").write_bytes(Layout.default().registry.read_bytes())
    doc = {"unit": name, "sources": [entry]}
    (root / "data" / "registry_additions" / f"{name}.yaml").write_text(yaml.safe_dump(doc), encoding="utf-8")
    return Layout(root, tmp_path / "raw", tmp_path / "pins", tmp_path / "clean", tmp_path / "m.json", tmp_path / "r")


NEW = {
    "id": "demo_new_source",
    "name": "Demo",
    "publisher": "Demo",
    "family": "demo",
    "urls": {"landing": "https://example.org"},
    "access": {"method": "download", "requires": "none"},
    "license": {"name": "unknown"},
    "verification": {"status": "unverified"},
}


def test_registry_additions(tmp_path):
    lay = _addition_layout(tmp_path, "demo_unit", NEW)
    assert get_source("demo_new_source", lay)["_added_by"] == "demo_unit"
    assert "mospi_nas_2026_publication" in source_ids(lay)


@pytest.mark.parametrize(
    "entry, needle",
    [
        (NEW | {"verification": {"status": "verified"}}, "unverified"),
        (NEW | {"id": "mospi_nas_2026_publication"}, "already exists"),
        ({k: v for k, v in NEW.items() if k != "license"}, "lacks"),
    ],
)
def test_registry_addition_rules(tmp_path, entry, needle):
    """A bad addition file is that unit's problem only: the registry still loads for everyone."""
    lay = _addition_layout(tmp_path, "demo_unit", entry)
    assert "mospi_nas_2026_publication" in source_ids(lay)  # the rest keeps working
    problems = registry_problems(lay)
    assert set(problems) == {"demo_unit"} and needle in " ".join(problems["demo_unit"])
    with pytest.raises(RegistryError, match=needle):
        require_sources(["mospi_nas_2026_publication"], lay, unit="demo_unit")  # the owner fails
    require_sources(["mospi_nas_2026_publication"], lay, unit="other_unit")  # others do not
    if entry["id"] == "demo_new_source":
        with pytest.raises(RegistryError, match=needle):  # a unit using the broken id fails too
            get_source("demo_new_source", lay)


def test_broken_addition_file_affects_only_its_unit(tmp_path):
    lay = _addition_layout(tmp_path, "other_unit", NEW | {"id": "other_source"})
    adds = lay.registry_additions
    (adds / "demo_unit.yaml").write_text("unit: demo_unit\nsources: [ {id: x, name: [unclosed\n", encoding="utf-8")
    (adds / "third_unit.yaml").write_text(yaml.safe_dump({"unit": "wrong", "sources": [NEW]}), encoding="utf-8")
    (adds / "not_a_unit.yaml").write_text(yaml.safe_dump({"unit": "not_a_unit", "sources": []}), encoding="utf-8")
    problems = registry_problems(lay)
    assert set(problems) == {"demo_unit", "third_unit", "not_a_unit"}
    assert "not valid YAML" in problems["demo_unit"][0]
    assert "'unit' must be" in problems["third_unit"][0]
    assert "no ingest unit" in problems["not_a_unit"][0]
    assert get_source("other_source", lay)["_added_by"] == "other_unit"
    require_sources(["other_source", "mospi_nas_2026_publication"], lay, unit="other_unit")


def test_same_id_added_by_two_units_breaks_both_owners_only(tmp_path):
    lay = _addition_layout(tmp_path, "demo_unit", NEW)
    (lay.registry_additions / "other_unit.yaml").write_text(
        yaml.safe_dump({"unit": "other_unit", "sources": [NEW]}), encoding="utf-8"
    )
    problems = registry_problems(lay)
    assert set(problems) == {"demo_unit", "other_unit"}
    assert "several addition files" in problems["demo_unit"][0]
    with pytest.raises(RegistryError, match="several"):
        get_source("demo_new_source", lay)
    require_sources(["mospi_nas_2026_publication"], lay, unit="third_unit")


@pytest.mark.parametrize(
    "source_id, needle",
    [
        ("gstn_gst_statistics", "GSTN is not automated"),  # registry says requires: none
        ("gst_monthly_state_revenue", "denied host"),  # a GSTN PDF on tutorial.gst.gov.in
        ("cbdt_time_series", "CBDT is not automated"),
        ("mospi_hces_unit_data", "microdata"),
        ("cmie_cphs", "requires = 'paid'"),
        ("data_gov_in_ogd", "requires = 'api_key'"),
        ("dpe_public_enterprises_survey", "requires = 'manual_download'"),
    ],
)
def test_access_policy_refuses_sources(source_id, needle):
    why = source_refusal(source_id, get_source(source_id))
    assert why and needle in why, why


def test_access_policy_public_parts_and_hosts():
    asi = get_source("mospi_asi")  # registry: requires registration, but aggregates are public
    assert source_refusal("mospi_asi", asi) is None
    assert url_refusal("mospi_asi", asi, "https://api.mospi.gov.in/api/asi/getASIData") is None
    assert "public prefixes" in url_refusal("mospi_asi", asi, "https://api.mospi.gov.in/api/other")
    assert "microdata" in url_refusal("mospi_asi", asi, "https://microdata.gov.in/NADA/index.php/catalog/256")
    nas = get_source("mospi_nas_2026_publication")
    assert url_refusal("mospi_nas_2026_publication", nas, "https://www.mospi.gov.in/uploads/x.xlsx") is None
    assert "GSTN" in url_refusal("mospi_nas_2026_publication", nas, "https://tutorial.gst.gov.in/x.xlsx")
    assert "CBDT" in url_refusal("mospi_nas_2026_publication", nas, "https://www.incometaxindia.gov.in/x.pdf")
    assert "sign-in" in url_refusal("mospi_nas_2026_publication", nas, "https://www.mospi.gov.in/login.aspx")


def _long(rows):
    return pl.DataFrame(rows, schema=["series_id", "period", "vintage", "value"], orient="row")


DF = _long(
    [
        ("gdp", "2022-23", "v1", 100.0),
        ("c", "2022-23", "v1", 60.0),
        ("i", "2022-23", "v1", 30.0),
        ("m", "2022-23", "v1", 5.0),
        ("x", "2022-23", "v1", 15.0),
        ("gdp", "2023-24", "v1", 120.0),
        ("c", "2023-24", "v1", 70.0),
        ("i", "2023-24", "v1", 30.0),
        ("m", "2023-24", "v1", 5.0),
        ("x", "2023-24", "v1", 15.0),  # 70+30+15-5 = 110 != 120
        ("gdp", "2024-25", "v1", 130.0),  # parts missing for 2024-25
    ]
)


def test_identity():
    v = checks.check_identity(DF, "gdp", {"c": 1, "i": 1, "x": 1, "m": -1})
    assert v["period"].to_list() == ["2023-24", "2024-25"]
    assert v.filter(pl.col("period") == "2023-24")["diff"][0] == pytest.approx(10.0)
    assert v.filter(pl.col("period") == "2024-25")["missing_parts"][0] == "c,i,x,m"
    with pytest.raises(AssertionError, match="2 violation"):
        checks.assert_no_rows(v, "expenditure identity")


def test_range_continuity_vintages():
    assert checks.check_range(DF, lo=0, hi=110, series_ids=["gdp"])["period"].to_list() == ["2023-24", "2024-25"]
    jumps = checks.check_continuity(DF, max_rel_change=0.15, series_ids=["gdp", "c"])
    assert set(jumps["series_id"]) == {"gdp", "c"}
    two = pl.concat([DF, DF.with_columns(pl.lit("v2").alias("vintage"), pl.col("value") * 1.01)])
    rev = checks.compare_vintages(two, "v1", "v2", rel_tol=0.005, series_ids=["gdp"])
    assert rev.height == 3 and set(rev["change"]) == {"revised"}
    assert checks.compare_vintages(two, "v1", "v2", rel_tol=0.02, series_ids=["gdp"]).height == 0
    with pytest.raises(LookupError):
        checks.check_range(DF, lo=0, series_ids=["nope"])
    assert checks.value(DF, "gdp", "2022-23") == 100.0
