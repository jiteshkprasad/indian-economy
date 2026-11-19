import polars as pl
import pytest

from pipeline.core import units as u


@pytest.mark.parametrize(
    "cell, want",
    [
        ("2,61,77,001", 26177001.0),
        ("2,90,73,287.4", 29073287.4),
        ("(1,234)", -1234.0),
        ("-1,07,438", -107438.0),
        ("−1,07,438", -107438.0),  # unicode minus
        ("12.5%", 12.5),
        ("₹ 3,45,36,796", 34536796.0),
        ("Rs. 1,000", 1000.0),
        ("1,234*", 1234.0),
        ("1,234 #", 1234.0),
        ("  42 ", 42.0),
        ("1.5e3", 1500.0),
        ("Nil", 0.0),
        (26177001.4450127, 26177001.4450127),
        (7, 7.0),
        ("-", None),
        ("–", None),
        ("NA", None),
        ("n.a.", None),
        ("..", None),
        ("", None),
        (None, None),
        (float("nan"), None),
    ],
)
def test_parse_number(cell, want):
    assert u.parse_number(cell) == want


def test_parse_number_dash_as_zero():
    assert u.parse_number("-", dash_as_zero=True) == 0.0
    assert u.parse_number("—", dash_as_zero=True) == 0.0


@pytest.mark.parametrize("cell", ["abc", "1,2,3x", "12-13", "GDP", True])
def test_parse_number_rejects_garbage(cell):
    with pytest.raises(u.NumberParseError):
        u.parse_number(cell)


@pytest.mark.parametrize(
    "label, key",
    [
        ("(₹ crore)", "INR_crore"),
        ("Rs. crore", "INR_crore"),
        ("(Rs lakh crore)", "INR_lakh_crore"),
        ("(Rs '000 crore)", "INR_thousand_crore"),
        ("Rs thousand crore", "INR_thousand_crore"),
        ("In ₹ billion", "INR_billion"),
        ("(Rs. lakh)", "INR_lakh"),
        ("Rs million", "INR_million"),
        ("(Rs '000)", "INR_thousand"),
    ],
)
def test_inr_unit_from_label(label, key):
    assert u.inr_unit_from_label(label) == key


def test_inr_unit_from_label_rejects_dollars_and_unknown():
    with pytest.raises(u.UnitError):
        u.inr_unit_from_label("US$ million")
    with pytest.raises(u.UnitError):
        u.inr_unit_from_label("tonnes")


@pytest.mark.parametrize(
    "value, unit, want",
    [
        (1.0, "INR_lakh_crore", 100000.0),
        (1.0, "INR_thousand_crore", 1000.0),
        (250.0, "INR_billion", 25000.0),
        (500.0, "INR_lakh", 5.0),
        (10.0, "INR_million", 1.0),
        (1e7, "INR", 1.0),
        (3.0, "INR_crore", 3.0),
    ],
)
def test_to_inr_crore(value, unit, want):
    assert u.to_inr_crore(value, unit) == pytest.approx(want)


def test_to_inr_crore_works_on_polars_expressions():
    df = pl.DataFrame({"v": [1.0, 2.5]}).with_columns(u.to_inr_crore(pl.col("v"), "INR_lakh_crore"))
    assert df["v"].to_list() == [100000.0, 250000.0]
    assert u.conversion_note("INR_lakh") == "INR_lakh -> INR_crore: x 0.01"
    assert u.conversion_note("INR_crore") == "none"
    with pytest.raises(u.UnitError):
        u.to_inr_crore(1.0, "USD_million")


def test_usd_conversion_needs_an_explicit_rate_series():
    vals = pl.DataFrame({"period": ["2023-24", "2024-25"], "value": [100.0, 200.0], "unit": ["USD_million"] * 2})
    rates = pl.DataFrame({"period": ["2023-24", "2024-25"], "value": [82.8, 84.6], "prov_id": ["x:1", "x:2"]})
    out = u.usd_million_to_inr_crore(vals, rates)
    assert out["value"].to_list() == pytest.approx([828.0, 1692.0])  # US$ 100 mn x 82.8 = Rs 828 crore
    assert out["unit"].unique().to_list() == ["INR_crore"]
    assert out["fx_prov_id"].to_list() == ["x:1", "x:2"]
    with pytest.raises(u.UnitError, match="no exchange rate"):
        u.usd_million_to_inr_crore(vals, rates.head(1))
    with pytest.raises(u.UnitError, match="duplicate"):
        u.usd_million_to_inr_crore(vals, pl.concat([rates, rates]))


def test_periods():
    assert u.fy(2023) == "2023-24"
    assert u.fy(1999) == "1999-00"
    assert u.fq(1, 2026) == "Q1 2026-27"
    assert u.fy_start("2023-24") == 2023
    with pytest.raises(ValueError):
        u.fy_start("2023-25")
    for text in ("2023-24", "2023-2024", "2023–24", "FY 2023-24 (FE)", "2023/24", "2023-24 \n"):
        assert u.normalize_fy(text) == "2023-24"
    for bad in ("2023-25", "2023-24 and 2024-25", "none"):
        with pytest.raises(ValueError):
            u.normalize_fy(bad)
    assert u.period_type_of("Q4 2025-26") == "fq"
    assert u.period_type_of("2024-12") == "month"
    assert u.period_type_of("2023-24") == "fy"
    with pytest.raises(ValueError, match="ambiguous"):
        u.period_type_of("2011-12")  # FY 2011-12 or December 2011
    assert u.period_sort_key("2011-12", "fy") < u.period_sort_key("2011-12", "month")
    assert u.period_ok("2023-24", "fy") and not u.period_ok("2023-25", "fy")
    assert u.period_ok("Q1 2026-27", "fq") and not u.period_ok("2026-27 Q1", "fq")
    ordered = ["2023-24", "Q1 2024-25", "Q4 2024-25", "2025-26"]
    assert sorted(reversed(ordered), key=u.period_sort_key) == ordered


def test_labels():
    assert u.clean_label("  GDP \n (1+2-3) ") == "GDP (1+2-3)"
    assert u.slug("Share in GDP (%) ") == "share_in_gdp"
