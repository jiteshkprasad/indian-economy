import polars as pl
import pytest

from pipeline.core.schema import (
    CLEAN_COLUMNS,
    PROV_DTYPES,
    CleanDataError,
    conform_clean,
    validate_clean,
    validate_provenance,
)

pytestmark = pytest.mark.unit

PID = "demo_unit:0123456789ab"


def good_rows(n: int = 2) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "series_id": ["t1.gdp.current"] * n,
            "source_id": ["mospi_nas_2026_publication"] * n,
            "table_id": ["Statement 1.1"] * n,
            "item_code": ["gdp"] * n,
            "item_label": ["GDP (1+2-3)"] * n,
            "geography": ["IN"] * n,
            "stock_flow": ["flow"] * n,
            "period": ["2022-23", "2023-24"][:n],
            "period_type": ["fy"] * n,
            "value": [26177001.4, 29073286.7][:n],
            "unit": ["INR_crore"] * n,
            "price_basis": ["current"] * n,
            "base_year": ["2022-23"] * n,
            "vintage": ["2026-08-31"] * n,
            "estimate_stage": ["Final"] * n,
            "status": ["official"] * n,
            "prov_id": [PID] * n,
        }
    )


def conformed(df: pl.DataFrame) -> pl.DataFrame:
    return conform_clean(df, "demo_unit_t1")


def test_good_frame_passes_and_is_conformed():
    df = conformed(good_rows())
    validate_clean(df)
    assert df.columns == list(CLEAN_COLUMNS)
    assert df["dataset"].unique().to_list() == ["demo_unit_t1"]
    assert df["institution"].null_count() == 2  # optional dims added as nulls


@pytest.mark.parametrize(
    "column, bad",
    [
        ("unit", "crore"),  # not in the vocabulary
        ("unit", "INR_lakh"),  # must be converted to INR_crore first
        ("price_basis", "constant"),  # needs the base year
        ("estimate_stage", "final"),
        ("status", "balanced"),
        ("stock_flow", "flows"),
        ("period_type", "year"),
        ("series_id", "T1.GDP"),  # lower case only
        ("source_id", "Mospi"),
        ("prov_id", "no-colon"),
        ("vintage", "31 Aug 2026"),
        ("geography", "all india"),  # dims are codes without spaces
    ],
)
def test_bad_values_are_rejected(column, bad):
    df = conformed(good_rows().with_columns(pl.lit(bad).alias(column)))
    with pytest.raises(CleanDataError):
        validate_clean(df)


def test_period_must_match_its_type():
    for period, ptype in (("2023-25", "fy"), ("2023-24", "fq"), ("2026-27 Q1", "fq"), ("2024-13", "month")):
        df = conformed(good_rows(1).with_columns(pl.lit(period).alias("period"), pl.lit(ptype).alias("period_type")))
        with pytest.raises(CleanDataError, match="period"):
            validate_clean(df)


def test_null_and_nan_values_rejected():
    for v in (None, float("nan")):
        df = conformed(good_rows(1).with_columns(pl.lit(v, dtype=pl.Float64).alias("value")))
        with pytest.raises(CleanDataError):
            validate_clean(df)
    df = conformed(good_rows(1).with_columns(pl.lit(float("inf")).alias("value")))
    with pytest.raises(CleanDataError, match="infinite"):
        validate_clean(df)


def test_duplicate_key_rejected():
    df = conformed(pl.concat([good_rows(1), good_rows(1)]))
    with pytest.raises(CleanDataError, match="uniqueness"):
        validate_clean(df)


def test_series_invariants():
    df = good_rows().with_columns(pl.Series("unit", ["INR_crore", "percent"]))
    with pytest.raises(CleanDataError, match="unit"):
        validate_clean(conformed(df))


def test_constant_prices_need_matching_base_year():
    df = good_rows().with_columns(
        pl.lit("t1.gdp.constant").alias("series_id"),
        pl.lit("constant_2011_12").alias("price_basis"),
    )
    with pytest.raises(CleanDataError, match="base_year"):
        validate_clean(conformed(df))
    validate_clean(conformed(df.with_columns(pl.lit("2011-12").alias("base_year"))))


def test_labels_must_be_canonical():
    df = good_rows().with_columns(pl.lit("GDP  (1+2-3) ").alias("item_label"))
    with pytest.raises(CleanDataError, match="item_label"):
        validate_clean(conformed(df))


def test_unknown_and_missing_columns():
    with pytest.raises(CleanDataError, match="not in the clean schema"):
        conformed(good_rows().with_columns(pl.lit(1).alias("extra")))
    with pytest.raises(CleanDataError, match="required columns missing"):
        conformed(good_rows().drop("vintage"))
    with pytest.raises(CleanDataError, match="different dataset"):
        conformed(good_rows().with_columns(pl.lit("other").alias("dataset")))


def prov_row(**kw):
    base = {
        "prov_id": PID,
        "ingest_unit": "demo_unit",
        "source_id": "mospi_nas_2026_publication",
        "url": "https://www.mospi.gov.in/x.xlsx",
        "raw_path": "data/raw/mospi_nas_2026_publication/2026-09-29/x.xlsx",
        "raw_sha256": "0" * 64,
        "retrieved_at": "2026-09-29T09:15:35Z",
        "table_id": "Statement 1.1",
        "locator": "sheet '1.1', rows 9-37",
        "unit_as_published": "Rs crore",
        "conversion": "none",
        "price_basis": "current",
        "base_year": "2022-23",
        "vintage": "2026-08-31",
        "release": "NAS 2026",
        "status": "official",
        "method": None,
        "inputs": None,
        "notes": None,
    }
    return pl.DataFrame([base | kw], schema=PROV_DTYPES, orient="row")


def test_provenance_rules():
    validate_provenance(prov_row())
    with pytest.raises(CleanDataError, match="official records need"):
        validate_provenance(prov_row(url=None))
    with pytest.raises(CleanDataError, match="need a method"):
        validate_provenance(prov_row(status="estimated"))
    validate_provenance(prov_row(status="estimated", method="Scaled HCES shares to NAS PFCE", url=None))
    with pytest.raises(CleanDataError):
        validate_provenance(prov_row(inputs="not an id"))
    # traceability: derived needs inputs or a raw file; estimated needs inputs, raw or notes
    untraced = dict(url=None, raw_path=None, raw_sha256=None, retrieved_at=None, method="m")
    with pytest.raises(CleanDataError, match="traceable"):
        validate_provenance(prov_row(status="derived", **untraced))
    validate_provenance(prov_row(status="derived", inputs="other_unit:0123456789ab", **untraced))
    with pytest.raises(CleanDataError, match="traceable"):
        validate_provenance(prov_row(status="estimated", **untraced))
    validate_provenance(prov_row(status="estimated", notes="HCES 2023-24 report, Table 3", **untraced))
    with pytest.raises(CleanDataError, match="vintage"):
        validate_provenance(prov_row(vintage="2026-13-45"))


@pytest.mark.parametrize(
    "changes, needle",
    [
        ({"vintage": "2026-13-45"}, "vintage"),
        ({"vintage": "0000-00-00"}, "vintage"),
        ({"vintage": "2099-01-01"}, "vintage"),
        ({"vintage": "1900"}, "vintage"),
        ({"geography": "India"}, "geography"),
        ({"geography": "IN-Maharashtra"}, "geography"),
        ({"dim_other": "z=1;a=2"}, "dim_other"),
        ({"dim_other": "a=1;a=2"}, "dim_other"),
        ({"period": "2099-00"}, "starts after its vintage"),
    ],
)
def test_format_checks(changes, needle):
    df = good_rows(1).with_columns(*(pl.lit(v).alias(k) for k, v in changes.items()))
    with pytest.raises(CleanDataError, match=needle):
        validate_clean(conformed(df))


def test_format_checks_accept_valid_values():
    for changes in (
        {"geography": "IN-MH"},
        {"geography": "USA"},
        {"dim_other": "a=1;b=x y"},
        {"vintage": "2026"},
        {"vintage": "2026-08"},
        {"period": "2027-28", "estimate_stage": "BE"},  # budget estimates may run ahead of the vintage
        {"period": "2027-28", "status": "estimated"},
    ):
        df = good_rows(1).with_columns(*(pl.lit(v).alias(k) for k, v in changes.items()))
        validate_clean(conformed(df))
    date_rows = good_rows(1).with_columns(
        pl.lit("2024-02-31").alias("period"), pl.lit("date").alias("period_type"), pl.lit("stock").alias("stock_flow")
    )
    with pytest.raises(CleanDataError, match="period"):
        validate_clean(conformed(date_rows))
