"""The project State/UT code set (pipeline/core/geo.py, DECISIONS D1-9)."""

import polars as pl
import pytest

from pipeline.core import geo
from pipeline.core.schema import CleanDataError, conform_clean, validate_clean

pytestmark = pytest.mark.unit


def test_current_iso_set_is_28_states_and_8_uts():
    kinds = [k for _, k in geo.STATES_UTS.values()]
    assert kinds.count("state") == 28 and kinds.count("ut") == 8
    # the ISO change of 2023-11-23, and the 2019/2020 reorganisations
    for code in ("IN-CG", "IN-OD", "IN-TS", "IN-UK", "IN-LA", "IN-DH", "IN-JK"):
        assert code in geo.STATES_UTS
    assert geo.STATES_UTS["IN-JK"][1] == "ut" and geo.STATES_UTS["IN-CH"][0] == "Chandigarh"
    assert not set(geo.SUPERSEDED) & geo.ALL_CODES
    assert all(c.startswith("IN-X") and len(c) == 6 for c in geo.HISTORICAL)


@pytest.mark.parametrize(
    "name, code",
    [
        ("Chhattisgarh", "IN-CG"),
        ("CHHATTISGARH", "IN-CG"),
        ("Orissa", "IN-OD"),
        ("Odisha", "IN-OD"),
        ("Telangana", "IN-TS"),
        ("Uttaranchal", "IN-UK"),
        ("NCT of Delhi", "IN-DL"),
        ("Jammu & Kashmir", "IN-JK"),
        ("12. Tamil Nadu", "IN-TN"),
        ("Tamilnadu", "IN-TN"),
        ("Pondicherry", "IN-PY"),
        ("Andaman & Nicobar Islands", "IN-AN"),
        ("Dadra & Nagar Haveli and Daman & Diu", "IN-DH"),
        ("Chandīgarh", "IN-CH"),
    ],
)
def test_state_code_from_printed_names(name, code):
    assert geo.state_code(name) == code


def test_unknown_or_historical_names_are_not_guessed():
    for name in ("Daman and Diu", "Dadra and Nagar Haveli", "Andhra Pradesh (undivided)", "Atlantis"):
        with pytest.raises(KeyError):
            geo.state_code(name)
    assert geo.state_name("IN-XAP").startswith("Andhra Pradesh (undivided")


def test_geography_problem():
    assert geo.geography_problem("IN") is None and geo.geography_problem("USA") is None
    assert geo.geography_problem("IN-CG") is None and geo.geography_problem("IN-XAP") is None
    assert "IN-CG" in geo.geography_problem("IN-CT")
    assert "IN-XDD" in geo.geography_problem("IN-DD")
    assert "not a current" in geo.geography_problem("IN-ZZ")


def _rows(geography: str) -> pl.DataFrame:
    return conform_clean(
        pl.DataFrame(
            {
                "series_id": ["x.y"],
                "source_id": ["mospi_nas_2026_publication"],
                "table_id": ["T1"],
                "item_code": ["y"],
                "item_label": ["Y"],
                "geography": [geography],
                "stock_flow": ["flow"],
                "period": ["2023-24"],
                "period_type": ["fy"],
                "value": [1.0],
                "unit": ["INR_crore"],
                "price_basis": ["current"],
                "vintage": ["2026-08-31"],
                "estimate_stage": ["Final"],
                "status": ["official"],
                "prov_id": ["demo_unit:0123456789ab"],
            }
        ),
        "demo_unit_t",
    )


@pytest.mark.parametrize("code", ["IN", "IN-CG", "IN-XAP", "IN-XJK", "USA"])
def test_schema_accepts_project_codes(code):
    validate_clean(_rows(code))


@pytest.mark.parametrize("code", ["IN-CT", "IN-OR", "IN-TG", "IN-UT", "IN-DD", "IN-ZZ", "IN-XZZ", "IN-XA"])
def test_schema_rejects_codes_outside_the_set(code):
    with pytest.raises(CleanDataError):
        validate_clean(_rows(code))
