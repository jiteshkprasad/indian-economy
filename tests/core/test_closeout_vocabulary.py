"""Phase 1 close-out additions (docs/phase1/FRAMEWORK_REQUESTS.md): units of measure, survey-year
periods, the 'Partially Revised' stage, significant-digit rounding, check_identity with zero-filled
parts, and the per-unit code hash used by `repro UNIT`."""

import datetime as dt

import polars as pl
import pytest

from pipeline import cli
from pipeline.core import checks, manifest
from pipeline.core import units as u
from pipeline.core.paths import REPO_ROOT
from pipeline.core.schema import ESTIMATE_STAGES, CleanDataError, conform_clean, validate_clean

pytestmark = pytest.mark.unit


def test_new_units_of_measure():
    for k in ("PJ", "KToE", "kg", "gram", "litre", "metre", "kWh", "EUR_million"):
        assert k in u.UNITS
    assert "tonnes" in u.UNITS  # unchanged
    assert "Partially Revised" in ESTIMATE_STAGES
    for caption in ("EUR million", "(in euro)", "€ mn"):
        with pytest.raises(u.UnitError, match="euro"):
            u.inr_unit_from_label(caption)


def test_survey_periods():
    assert u.survey_period(2023, 8) == "2023-08/2024-07"  # HCES 2023-24 (Aug-Jul)
    assert u.agricultural_year(2023) == "2023-07/2024-06"  # PLFS/SAS (Jul-Jun)
    assert u.survey_period(2022, 10) == "2022-10/2023-09"  # ASUSE (Oct-Sep)
    assert u.survey_period(2025, 1) == "2025-01/2025-12" and u.survey_period(2023, 11, 3) == "2023-11/2024-01"
    assert u.period_type_of("2023-08/2024-07") == "sy"
    assert u.period_ok("2023-08/2024-07", "sy") and not u.period_ok("2024-08/2023-07", "sy")
    assert not u.period_ok("2023-13/2024-07", "sy") and not u.period_ok("2023-24", "sy")
    assert u.period_start("2023-08/2024-07", "sy") == dt.date(2023, 8, 1)
    assert u.period_end("2023-08/2024-07", "sy") == dt.date(2024, 7, 31)
    assert u.period_end("2023-24", "fy") == dt.date(2024, 3, 31)
    assert u.period_end("Q4 2025-26", "fq") == dt.date(2026, 3, 31)
    assert u.period_end("H1 2023-24", "fh") == dt.date(2023, 9, 30)
    assert u.period_end("2024-Q1", "cq") == dt.date(2024, 3, 31) and u.period_end("2024", "cy") == dt.date(2024, 12, 31)
    assert u.period_end("2024-02", "month") == dt.date(2024, 2, 29)
    order = ["2023-04/2024-03", "2023-07/2024-06", "2023-08/2024-07"]
    assert sorted(reversed(order), key=lambda p: u.period_sort_key(p, "sy")) == order
    # period_sort_key is the START only; period_order_key breaks ties by the end, then the label
    assert u.period_sort_key("2023-07/2023-12", "sy") == u.period_sort_key("2023-07/2024-06", "sy")
    assert u.period_sort_key("2023-07/2024-06", "sy") == u.period_sort_key("2023-07", "month")
    mixed = [("2023-07", "month"), ("2023-07/2023-12", "sy"), ("2023-07/2024-06", "sy"), ("2023-24", "fy")]
    for perm in (mixed, mixed[::-1], mixed[1:] + mixed[:1]):
        assert sorted(perm, key=lambda t: u.period_order_key(*t)) == [mixed[3], mixed[0], mixed[1], mixed[2]]
    with pytest.raises(ValueError):
        u.survey_period(2023, 13)


def _frame(**over) -> pl.DataFrame:
    row = {
        "series_id": "hces.mpce.rural",
        "source_id": "mospi_nas_2026_publication",
        "table_id": "Table 1",
        "item_code": "mpce",
        "item_label": "MPCE",
        "geography": "IN",
        "stock_flow": "flow",
        "period": "2023-08/2024-07",
        "period_type": "sy",
        "value": 4122.0,
        "unit": "INR",
        "price_basis": "current",
        "vintage": "2025-02-28",
        "estimate_stage": "n.a.",
        "status": "official",
        "prov_id": "demo_unit:0123456789ab",
    } | over
    return conform_clean(pl.DataFrame({k: [v] for k, v in row.items()}), "demo_unit_t")


def test_schema_accepts_sy_and_new_stage_and_units():
    validate_clean(_frame())
    validate_clean(_frame(estimate_stage="Partially Revised", period="2024-03-31", period_type="date"))
    validate_clean(_frame(unit="PJ", price_basis="n/a", period="2023-24", period_type="fy"))
    with pytest.raises(CleanDataError, match="sy='2023-08/2024-07'"):
        validate_clean(_frame(period="2024-08/2023-07"))
    with pytest.raises(CleanDataError, match="after its vintage"):
        validate_clean(_frame(vintage="2023-06"))  # a survey window cannot start after its release


def test_round_sig_expr_keeps_at_least_six_decimals():
    df = pl.DataFrame({"v": [0.000123456789123, 12.5, 1234.56789123, 0.0, 99.99999999999, 5e-20, -0.0012345678912]})
    out = df.select(u.round_sig_expr(pl.col("v"), 9))["v"].to_list()
    assert out[0] == 0.000123456789  # 9 significant digits instead of 0.000123
    assert out[1] == 12.5 and out[2] == 1234.567891  # never coarser than 6 decimals
    assert out[3] == 0.0 and out[4] == 100.0 and out[5] == 0.0  # capped at 15 decimals
    assert out[6] == -0.00123456789
    with pytest.raises(ValueError):
        u.round_sig_expr(pl.col("v"), 0)


def test_check_identity_missing_parts_as_zero():
    df = pl.DataFrame(
        {
            "series_id": ["t", "a", "b", "t", "a"],
            "vintage": ["v"] * 5,
            "period": ["2022-23", "2022-23", "2022-23", "2023-24", "2023-24"],
            "value": [10.0, 4.0, 6.0, 5.0, 5.0],
        }
    )
    strict = checks.check_identity(df, "t", ["a", "b"])
    assert strict["missing_parts"].to_list() == ["b"]  # default: an absent part is reported
    assert checks.check_identity(df, "t", ["a", "b"], missing_parts_as_zero=True).height == 0
    bad = df.with_columns(pl.when(pl.col("series_id") == "t").then(20.0).otherwise(pl.col("value")).alias("value"))
    v = checks.check_identity(bad, "t", ["a", "b"], missing_parts_as_zero=True)
    assert v.height == 2 and v["missing_parts"].to_list() == [None, "b"]
    # a missing TOTAL is never zero-filled: the group is still reported
    no_total = df.filter(~((pl.col("series_id") == "t") & (pl.col("period") == "2023-24")))
    v = checks.check_identity(no_total, "t", ["a", "b"], missing_parts_as_zero=True)
    assert v["period"].to_list() == ["2023-24"] and v["missing_parts"].to_list() == ["t,b"]


def test_unit_code_files_are_framework_plus_own_files():
    rel = [p.relative_to(REPO_ROOT).as_posix() for p in manifest.unit_code_files(REPO_ROOT, "io_tables")]
    assert "pipeline/core/fetch.py" in rel and "pipeline/cli.py" in rel and "uv.lock" in rel
    assert "pipeline/ingest/__init__.py" in rel and "pipeline/ingest/io_tables_coverage.yaml" in rel
    assert any(r.startswith("pipeline/ingest/io_tables/") for r in rel)
    assert not any(r.startswith(("pipeline/ingest/state_fiscal", "pipeline/ingest/mospi_nas_2026")) for r in rel)
    assert manifest.unit_code_hash(REPO_ROOT, "io_tables") != manifest.unit_code_hash(REPO_ROOT, "state_fiscal")


def test_every_build_input_under_pipeline_is_hashed():
    """Review of FRAMEWORK_REQUESTS #17: mospi_nas_2026 reads spec_*.json at build time, so those
    files must be in code_hash and in the unit's scoped hash. No file under pipeline/ or models/
    may have a suffix the hash ignores (except placeholders and bytecode)."""
    unhashed = [
        p.relative_to(REPO_ROOT).as_posix()
        for d in manifest.CODE_DIRS
        for p in (REPO_ROOT / d).rglob("*")
        if p.is_file()
        and "__pycache__" not in p.parts
        and p.name != ".gitkeep"
        and p.suffix not in manifest.CODE_SUFFIXES
    ]
    assert unhashed == []
    rel = [p.relative_to(REPO_ROOT).as_posix() for p in manifest.unit_code_files(REPO_ROOT, "mospi_nas_2026")]
    assert "pipeline/ingest/mospi_nas_2026/spec_nas2026.json" in rel
    assert "pipeline/ingest/mospi_nas_2026/spec_oldbase.json" in rel


def test_repro_code_hash_comparison_is_unit_scoped(capsys):
    m0 = {"code_hash": "a", "unit_code_hashes": {"io_tables": "x"}}
    other_unit_edited = {"code_hash": "b", "unit_code_hashes": {"io_tables": "x"}}
    assert cli._code_hash_changes(m0, other_unit_edited, scoped=True) == []
    assert "ignored" in capsys.readouterr().out
    assert cli._code_hash_changes(m0, other_unit_edited, scoped=False)  # a full repro still fails
    own_edit = {"code_hash": "b", "unit_code_hashes": {"io_tables": "y"}}
    assert "io_tables" in cli._code_hash_changes(m0, own_edit, scoped=True)[0]


def test_terms_blocked_sources_are_refused_in_code():
    """finsector_markets FR1: NSDL FPI Monitor and AMFI are blocked-terms (ACCESS_PLAN s.5), so the code
    policy refuses them by id and host even though the registry says access.requires = none."""
    from pipeline.core.policy import source_refusal, url_refusal
    from pipeline.core.registry import get_source

    for sid in ("nsdl_fpi_monitor", "amfi_monthly_quarterly"):
        assert "blocked-terms" in source_refusal(sid, get_source(sid))
    other = get_source("mospi_nas_2026_publication")
    assert "AMFI" in url_refusal("mospi_nas_2026_publication", other, "https://www.amfiindia.com/a.xls")
    assert "NSDL" in url_refusal("mospi_nas_2026_publication", other, "https://www.fpi.nsdl.co.in/web/x.aspx")
