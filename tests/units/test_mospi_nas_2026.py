"""Value tests for the mospi_nas_2026 unit (NAS 2026, base 2022-23, vintage 31 Aug 2026).

Expected numbers are quoted from the NAS 2026 press release (31 Aug 2026) and Statement 1.1 as
recorded in docs/phase0/recon/mospi_nas.md and docs/phase0/verify/mospi_nas.md.
"""

import polars as pl
import pytest

from pipeline.core import checks
from pipeline.core.fetch import pinned_raw
from pipeline.core.paths import Layout
from pipeline.ingest import mospi_nas_2026 as U

pytestmark = pytest.mark.quality


@pytest.fixture(scope="module")
def s11():
    return checks.load_dataset(U.UNIT, f"{U.UNIT}_s1_1")


@pytest.fixture(scope="module")
def s817():
    return checks.load_dataset(U.UNIT, f"{U.UNIT}_s8_17_1")


# Press release: GDP 2,61,77,001 | 2,90,73,287 | 3,17,98,524 | 3,45,36,796 (PE) crore.
@pytest.mark.parametrize("period, crore", [("2022-23", 26177001), ("2023-24", 29073287), ("2024-25", 31798524)])
def test_gdp_current_matches_press_release(s11, period, crore):
    assert round(checks.value(s11, "s1_1.gdp.current", period)) == crore


def test_gdp_2025_26_pe(s817):
    assert round(checks.value(s817, "s8_17_1.gdp.current", "2025-26")) == 34536796
    row = s817.filter((pl.col("series_id") == "s8_17_1.gdp.current") & (pl.col("period") == "2025-26"))
    assert row["estimate_stage"][0] == "PE"


def test_discrepancy(s11):
    assert checks.value(s11, "s1_1.discrepancies.current", "2022-23") == 0.0
    assert checks.value(s11, "s1_1.discrepancies.current", "2023-24") == 0.0
    assert round(checks.value(s11, "s1_1.discrepancies.current", "2024-25")) == -107438
    assert round(checks.value(s11, "s1_1.discrepancies.constant_2022_23", "2023-24")) == -70316


def test_other_recon_values(s11):
    assert round(checks.value(s11, "s1_1.pfce.current", "2023-24")) == 16415547
    assert round(checks.value(s11, "s1_1.gross_saving.current", "2023-24")) == 9436799
    assert round(checks.value(s11, "s1_1.primary_income_row_net.current", "2022-23")) == -370307
    assert round(checks.value(s11, "s1_1.imports_services.current", "2022-23")) == 1168704


@pytest.mark.parametrize("basis", ["current", "constant_2022_23"])
def test_identities(s11, basis):
    b = f".{basis}"
    ident = {
        "gdp": {"gva_basic": 1, "taxes_on_products": 1, "subsidies_on_products": -1},
        "ndp": {"gdp": 1, "cfc": -1},
        "gcf": {"gfcf": 1, "cis": 1, "valuables": 1},
        "exports": {"exports_goods": 1, "exports_services": 1},
        "imports": {"imports_goods": 1, "imports_services": 1},
        "gdp_expenditure": {"pfce": 1, "gfce": 1, "gcf": 1, "exports": 1, "imports": -1, "discrepancies": 1},
        "gni": {"gdp": 1, "primary_income_row_net": 1},
        "nni": {"gni": 1, "cfc": -1},
    }
    if basis == "current":
        ident |= {
            "gndi": {"gni": 1, "other_current_transfers_row_net": 1},
            "nndi": {"gndi": 1, "cfc": -1},
            "net_saving": {"gross_saving": 1, "cfc": -1},
        }
    for total, parts in ident.items():
        v = checks.check_identity(s11, f"s1_1.{total}{b}", {f"s1_1.{k}{b}": c for k, c in parts.items()})
        checks.assert_no_rows(v, f"{total} identity ({basis})")


def test_ranges_and_continuity(s11):
    levels = s11.filter(pl.col("unit") == "INR_crore")
    may_be_negative = {"discrepancies", "primary_income_row_net"}
    checks.assert_no_rows(
        checks.check_range(levels.filter(~pl.col("item_code").is_in(list(may_be_negative))), lo=0), "negative levels"
    )
    checks.assert_no_rows(checks.check_range(s11.filter(pl.col("unit") == "percent"), lo=-100, hi=200), "percent")
    big = levels.filter(~pl.col("item_code").is_in(["discrepancies", "cis", "valuables", "net_saving"]))
    checks.assert_no_rows(checks.check_continuity(big, max_rel_change=0.25), "year-on-year break > 25%")


def test_s8_17_1_repeats_s1_1(s11, s817):
    """Overlapping years of the two statements (same vintage) must agree."""
    for code in (
        "gdp",
        "gva_basic",
        "pfce",
        "gfce",
        "gfcf",
        "cis",
        "valuables",
        "exports",
        "imports",
        "discrepancies",
        "gni",
        "nni",
    ):
        for basis in ("current", "constant_2022_23"):
            a = s11.filter(pl.col("series_id") == f"s1_1.{code}.{basis}").select("period", "value")
            b = s817.filter(pl.col("series_id") == f"s8_17_1.{code}.{basis}").select("period", "value")
            j = a.join(b, on="period", suffix="_b")
            assert j.height == 3, (code, basis)
            assert ((j["value"] - j["value_b"]).abs() < 0.01).all(), (code, basis, j)


def test_stages_and_bases(s11, s817):
    for df in (s11, s817):
        stages = dict(df.select("period", "estimate_stage").unique().iter_rows())
        assert stages == {p: U.STAGES[p] for p in stages}
        assert set(df["vintage"]) == {"2026-08-31"} and set(df["base_year"]) == {"2022-23"}
    # saving and disposable income exist only at current prices (statement note iii)
    assert not s11.filter(pl.col("series_id").str.starts_with("s1_1.gross_saving.constant")).height
    pop = s817.filter(pl.col("item_code") == "population")
    assert set(pop["unit"]) == {"count"} and pop["value"].min() > 1.3e9


def test_statement_urls_come_from_listing():
    listing = pinned_raw(Layout.default(), U.UNIT, U.SRC, "chapters_2861.json").read_json()
    urls = U._statement_urls(listing)
    assert urls["1.1"] == U.FILE_BASE + "1.1.xlsx"
    assert len(urls) == 64  # 64 sub-chapters, one file each (verify/mospi_nas.md)
    assert {"8.17.1", "8.18.2", "8.6.1A", "8.6.1B", "1.6B"} <= set(urls)


# ---- verifier findings verify-4 / verify-5: sign convention and dims -----------------------------


def test_less_items_are_positive_and_documented():
    """'Less'-captioned items are stored as published (positive magnitudes to subtract), and every dataset
    holding one says so in its description. The 1.9 household identity holds only with the minus."""
    import json

    meta = json.loads((Layout.default().clean / U.UNIT / "_datasets.json").read_text(encoding="utf-8"))
    with_less = []
    for name in meta:
        if name.startswith("_"):
            continue
        d = checks.load_dataset(U.UNIT, name)
        if d.filter(pl.col("item_label").str.to_lowercase().str.strip_chars_start().str.starts_with("less")).height:
            with_less.append(name)
            assert "'Less'-captioned items" in meta[name]["description"], name
    assert {f"{U.UNIT}_s1_1", f"{U.UNIT}_s1_9", f"{U.UNIT}_oldbase_soa_s1_15"} <= set(with_less)
    s19 = checks.load_dataset(U.UNIT, f"{U.UNIT}_s1_9")

    def v(c):
        return checks.value(s19, f"s1_9.{c}.current", "2023-24")

    assert v("less_financial_liabilities") > 0
    hh = v("gross_financial_saving") - v("less_financial_liabilities") + v("saving_in_physical_assets") \
        + v("saving_in_the_form_of_gold_and_silver_ornaments")
    assert abs(hh - v("household_sector")) < 2


def test_state_rows_of_4_1_carry_iso_geography():
    d = checks.load_dataset(U.UNIT, f"{U.UNIT}_s4_1")
    states = d.filter(pl.col("geography") != "IN")
    assert states["geography"].n_unique() == 31
    assert states["geography"].str.contains(r"^IN-[A-Z]{2}$").all()
    assert set(d.filter(pl.col("geography") == "IN")["item_code"]) == {
        "gross_value_added", "consumption_of_fixed_capital", "net_value_added", "central_government",
        "state_government", "local_bodies", "autonomous_institutions"}
    assert set(states.filter(pl.col("geography") == "IN-MH")["item_code"]) == {"maharashtra"}
    # the 31 States add up to 'State government' (4.1 item 3.2)
    for (per, basis), g in d.group_by(["period", "price_basis"]):
        tot = g.filter(pl.col("item_code") == "state_government")["value"][0]
        assert abs(g.filter(pl.col("geography") != "IN")["value"].sum() - tot) < 5, (per, basis)


def test_sector_rows_of_1_9_and_1_11_carry_institution():
    s19 = checks.load_dataset(U.UNIT, f"{U.UNIT}_s1_9")
    got = dict(s19.select("item_code", "institution").unique().iter_rows())
    assert got["public_non_financial_corporations"] == "nfc_public"
    assert got["household_sector"] == "households_npish"
    assert got["public_non_financial_corporations.departmental_enterprises"] == "nfc_public_de"
    assert got["gross_savings"] is None and got["net_capital_inflow_from_row"] is None
    assert got["public_financial_corporations.departmental_enterprises"] is None
    assert got["gross_financial_saving"] is None
    s111 = checks.load_dataset(U.UNIT, f"{U.UNIT}_s1_11")
    got = dict(s111.select("item_code", "institution").unique().iter_rows())
    assert got["general_government"] == "gg"
    assert got["pct_share.private_financial_corporations"] == "fc_private"
    # asset sub-rows name the sector only via the parent heading: sector stays in the item-code prefix
    assert got["general_government.machinery_and_equipment"] is None
    assert got["gross_fixed_capital_formation"] is None
    # same codes as 1.14's institution column
    s114 = set(checks.load_dataset(U.UNIT, f"{U.UNIT}_s1_14")["institution"].drop_nulls())
    assert set(s111["institution"].drop_nulls()) == s114
