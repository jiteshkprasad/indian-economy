"""Value tests for the io_tables unit: MoSPI SUT 2022-23/2023-24 (Aug-2026 files), the SUT note
totals, ADB India IOT and the OECD ICIO India slice.

Expected numbers are read off the source documents; each is commented with where it is printed:
- 'xlsx <sheet> <cell>': the SUT workbooks (sut_2022_23.xlsx / sut_2023_24.xlsx, 31 Aug 2026 files);
- 'note T9.x': SUT methodological note, Tables 9.1 (2022-23) and 9.2 (2023-24), printed pp. 14-16;
- 'gap map <ref>': data/gap_map.csv, whose numbers Phase 0 read off the same SUT file;
- 'ADB <sheet> <row>/<col>': IND IOT 2000, 2007-2024.xlsx;
- ICIO values are re-read from the raw CSV inside the test with the csv module (independent path).
"""

from __future__ import annotations

import csv
import io
import zipfile

import openpyxl
import polars as pl
import pytest

from pipeline.core import checks
from pipeline.core.fetch import pinned_raw
from pipeline.core.paths import Layout
from pipeline.ingest.io_tables import adb as ADB
from pipeline.ingest.io_tables import icio as ICIO
from pipeline.ingest.io_tables import sut as SUT

pytestmark = pytest.mark.quality
UNIT = "io_tables"
PERIODS = ("2022-23", "2023-24")


@pytest.fixture(scope="module")
def supply():
    return checks.load_dataset(UNIT, "io_tables_sut_supply")


@pytest.fixture(scope="module")
def use():
    return checks.load_dataset(UNIT, "io_tables_sut_use")


@pytest.fixture(scope="module")
def va():
    return checks.load_dataset(UNIT, "io_tables_sut_va")


@pytest.fixture(scope="module")
def note():
    return checks.load_dataset(UNIT, "io_tables_sut_note_totals")


@pytest.fixture(scope="module")
def adb():
    return checks.load_dataset(UNIT, "io_tables_adb_ind_iot")


@pytest.fixture(scope="module")
def icio():
    return checks.load_dataset(UNIT, "io_tables_icio_india")


def v(df: pl.DataFrame, sid: str, period: str) -> float:
    return checks.value(df, sid, period)


def _wide(df: pl.DataFrame, period: str, key: str) -> pl.DataFrame:
    """item_code columns by `key` (product or industry); absent (blank) cells are 0."""
    d = df.filter(pl.col("period") == period)
    return (
        d.group_by(key, "item_code", maintain_order=True)
        .agg(pl.col("value").sum())
        .pivot(on="item_code", index=key, values="value")
        .fill_null(0.0)
        .sort(key)
    )


def _viol(df: pl.DataFrame, lhs: pl.Expr, rhs: pl.Expr, tol: float, key: str) -> pl.DataFrame:
    return df.with_columns((lhs - rhs).alias("diff")).filter(pl.col("diff").abs() > tol).select(key, "diff")


# ---------------------------------------------------------------------------------------------
# SUT: anchor values read off the workbooks
# ---------------------------------------------------------------------------------------------

ANCHORS = [
    # (dataset fixture, series_id, period, value, where printed)
    ("supply", "supply.output.sut_p001.sut_i01.current", "2023-24", 473067.2118946095, "xlsx Supply 2023-24 C3"),
    ("supply", "supply.product_subsidies.sut_p001.current", "2023-24", -6691.375896, "xlsx Supply 2023-24 BX3"),
    ("supply", "supply.ttm.sut_p001.current", "2023-24", 71383.8097503977, "xlsx Supply 2023-24 BY3"),
    ("supply", "supply.imports.sut_p042.current", "2022-23", 400441.24109921156, "xlsx Supply 2022-23 BS44"),
    ("supply", "supply.imports.cif.current", "2022-23", -292775.310401841, "xlsx Supply 2022-23 BS158"),
    ("supply", "supply.imports.purchases_residents_abroad.current", "2022-23", 183317.0, "xlsx Supply 2022-23 BS159"),
    ("use", "use.pfce.sut_p001.current", "2023-24", 31526.0, "xlsx Use 2023-24 BS3"),
    ("use", "use.gfce.sut_p001.current", "2023-24", 101441.21333966365, "xlsx Use 2023-24 BT3 (PDS paddy)"),
    ("use", "use.gfce.sut_p002.current", "2023-24", 62530.54036033634, "xlsx Use 2023-24 BT4 (PDS wheat)"),
    ("use", "use.ic.sut_p001.sut_i01.current", "2023-24", 16454.875139392218, "xlsx Use 2023-24 C3"),
    ("use", "use.exports.purchases_nonresidents_domestic.current", "2022-23", 221703.0, "xlsx Use 2022-23 BX160"),
    ("va", "va.net_production_taxes.sut_i01.current", "2023-24", -203683.0, "xlsx Use 2023-24 C165"),
    ("va", "va.cfc.sut_i01.current", "2023-24", 209151.0, "xlsx Use 2023-24 C166"),
    ("va", "va.ce.sut_i01.current", "2023-24", 650969.0, "xlsx Use 2023-24 C167"),
    ("va", "va.os_mi.sut_i01.current", "2023-24", 2531813.0, "xlsx Use 2023-24 C168"),
    ("va", "va.gva_income.sut_i01.current", "2023-24", 3188250.0, "xlsx Use 2023-24 C169"),
    ("va", "va.ce.sut_i01.current", "2022-23", 600550.0496514945, "xlsx Use 2022-23 C167"),
]


@pytest.mark.parametrize("fixture, sid, period, expected, where", ANCHORS, ids=[a[4] for a in ANCHORS])
def test_sut_anchor_cells(request, fixture, sid, period, expected, where):
    assert v(request.getfixturevalue(fixture), sid, period) == pytest.approx(expected, abs=1e-6)


# Rounded values quoted in data/gap_map.csv and ACCOUNT_STRUCTURE s.2 (read off the 2023-24 file in Phase 0).
@pytest.mark.parametrize(
    "fixture, sid, crore, where",
    [
        ("supply", "supply.product_subsidies.sut_p128.current", -192370, "gap map P9: electricity"),
        ("supply", "supply.product_subsidies.sut_p089.current", -145129, "gap map P9: fertilisers"),
        ("supply", "supply.product_subsidies.sut_p090.current", -62440, "gap map P9: pesticides (issue Q6)"),
        ("supply", "supply.product_subsidies.sut_p132.current", -105007, "gap map P9: trade (issue Q7)"),
        ("supply", "supply.product_subsidies.sut_p002.current", -4110, "gap map P9: wheat"),
        ("use", "use.pfce.sut_p144.current", 2148044, "ACCOUNT_STRUCTURE DWEL: dwellings PFCE"),
        ("va", "va.net_production_taxes.sut_i60.current", 66850, "gap map P10 / ACCOUNT_STRUCTURE ITSV"),
        ("use", "use.valuables.sut_p125.current", 376232, "gap map I2a: all valuables on gems & jewellery"),
        ("supply", "supply.cif_adj.cif.current", 212499, "gap map D2/P6: CIF adjustment"),
        ("supply", "supply.imports.purchases_residents_abroad.current", 226203, "gap map P6: residents abroad"),
        ("use", "use.exports.purchases_nonresidents_domestic.current", 280978, "gap map P5: non-residents"),
    ],
)
def test_sut_gap_map_values_2023_24(request, fixture, sid, crore, where):
    assert round(v(request.getfixturevalue(fixture), sid, "2023-24")) == crore, where


# ---------------------------------------------------------------------------------------------
# SUT: totals vs published totals (note Tables 9.1/9.2) and NAS 2026
# ---------------------------------------------------------------------------------------------

# note T9.1 (2022-23) and T9.2 (2023-24), Rs crore as printed
NOTE_TABLES = {
    "2022-23": {
        "output": 53484478, "ic": 29661343, "gva": 23823136, "product_taxes_less_subsidies": 2353866,
        "gdp": 26177001, "pfce": 14938852, "gfce": 2934060, "gfcf": 8452956, "cis": 174121, "valuables": 360668,
        "exports": 6278722, "imports": 6962377, "gdp_expenditure": 26177001, "production_taxes_less_subsidies": -69725,
        "cfc": 3584380, "ce": 8653669, "os_mi": 11654812, "gva_income": 23823136,
    },
    "2023-24": {
        "output": 57564356, "ic": 31158876, "gva": 26405480, "product_taxes_less_subsidies": 2667806,
        "gdp": 29073287, "pfce": 16415547, "gfce": 3121027, "gfcf": 9245762, "cis": 382329, "valuables": 376232,
        "exports": 6479296, "imports": 6946906, "gdp_expenditure": 29073287, "production_taxes_less_subsidies": -57442,
        "cfc": 3836206, "ce": 9442896, "os_mi": 13183820, "gva_income": 26405480,
    },
}


@pytest.mark.parametrize("period", PERIODS)
def test_note_dataset_matches_printed_tables(note, period):
    got = {r["item_code"]: r["value"] for r in note.filter(pl.col("period") == period).iter_rows(named=True)}
    assert got == {k: float(x) for k, x in NOTE_TABLES[period].items()}


# NAS 2026 press release / Statement 1.1: GDP 2,61,77,001 (2022-23) and 2,90,73,287 (2023-24) - the
# SUT is integrated with the Final Estimates (zero discrepancy).
@pytest.mark.parametrize("period, gdp", [("2022-23", 26177001), ("2023-24", 29073287)])
def test_sut_gdp_equals_nas_2026(supply, va, period, gdp):
    gva = va.filter((pl.col("period") == period) & (pl.col("item_code") == "gva_production"))["value"].sum()
    s = supply.filter((pl.col("period") == period) & pl.col("product").str.starts_with("sut_p"))
    ptls = s.filter(pl.col("item_code").is_in(["import_duty", "product_taxes", "product_subsidies"]))["value"].sum()
    assert round(gva + ptls) == gdp


# Tolerance for sums of the 155 x 67 cells against a printed total: MoSPI rounds each printed total to
# whole crore, and the 2023-24 file has three 1-crore inconsistencies of its own between the matrix, its
# 'Total Output' row and the 'Supply at BP' total cell (issue io_tables-2). 5 crore = 0.00001% of output.
TOL = 5.0


@pytest.mark.parametrize("period", PERIODS)
def test_cells_sum_to_note_totals(supply, use, va, note, period):
    n = {r["item_code"]: r["value"] for r in note.filter(pl.col("period") == period).iter_rows(named=True)}
    s = supply.filter(pl.col("period") == period)
    u = use.filter(pl.col("period") == period)
    a = va.filter(pl.col("period") == period)
    prod = pl.col("product").str.starts_with("sut_p")
    tot = pl.col("product") == "total"

    def ssum(df, item, sel):
        return df.filter((pl.col("item_code") == item) & sel)["value"].sum()

    got = {
        "output": ssum(s, "output", prod),
        "ic": ssum(u, "ic", prod),
        "gva": ssum(a, "gva_production", pl.lit(True)),
        "product_taxes_less_subsidies": sum(
            ssum(s, i, prod) for i in ("import_duty", "product_taxes", "product_subsidies")
        ),
        "pfce": ssum(u, "pfce", tot),
        "gfce": ssum(u, "gfce", tot),
        "gfcf": ssum(u, "gfcf", tot),
        "cis": ssum(u, "cii", tot),
        "valuables": ssum(u, "valuables", tot),
        "exports": ssum(u, "exports", tot),
        "imports": ssum(s, "imports_after_cif", tot),
        "production_taxes_less_subsidies": ssum(a, "net_production_taxes", pl.lit(True)),
        "cfc": ssum(a, "cfc", pl.lit(True)),
        "ce": ssum(a, "ce", pl.lit(True)),
        "os_mi": ssum(a, "os_mi", pl.lit(True)),
        "gva_income": ssum(a, "gva_income", pl.lit(True)),
    }
    bad = {k: (x, n[k]) for k, x in got.items() if abs(x - n[k]) > TOL}
    assert not bad, f"{period}: cell sums differ from the note's printed totals: {bad}"


@pytest.mark.parametrize("period", PERIODS)
def test_final_use_total_rows_equal_product_rows(use, period):
    """The 'Total Use' row of each final-use column equals the sum of the 155 product rows; the three
    memo rows (CIF, residents abroad, non-residents) are 'of which' reclassifications, not additive."""
    w = _wide(use.filter(pl.col("industry").is_null()), period, "product")
    items = ["pfce", "gfce", "gfcf", "cii", "valuables", "exports", "ic_total", "total_use_pp"]
    prods = w.filter(pl.col("product").str.starts_with("sut_p"))
    total = w.filter(pl.col("product") == "total")
    bad = {i: (prods[i].sum(), total[i][0]) for i in items if abs(prods[i].sum() - total[i][0]) > TOL}
    assert not bad


@pytest.mark.parametrize("period", PERIODS)
def test_supply_total_row_rule_and_cif_adj_exception(supply, period):
    """io_tables-5 (verifier finding): on the Supply side the 'Total' row equals the 155 product rows in
    every valuation column EXCEPT 'CIF Adj', whose printed Total (0) includes the CIF memo row:
    products -2,12,499.24 + CIF memo +2,12,499.24 = 0 in 2023-24 (-2,92,775.31 + 2,92,775.31 in 2022-23).
    So supply.cif_adj.total = 0 is not the product-level CIF adjustment."""
    w = _wide(supply.filter(pl.col("industry").is_null()), period, "product")
    prods = w.filter(pl.col("product").str.starts_with("sut_p"))
    total = w.filter(pl.col("product") == "total")
    cif = w.filter(pl.col("product") == "cif")
    items = [c for c in w.columns if c not in ("product", "cif_adj")]
    bad = {i: (prods[i].sum(), total[i][0]) for i in items if abs(prods[i].sum() - total[i][0]) > 2.5}
    assert not bad  # 2.5: the 2023-24 'Supply at BP' total is 2 crore below its column sum (io_tables-2)
    assert abs(total["cif_adj"][0]) < TOL and prods["cif_adj"].sum() < -1e5
    assert abs(prods["cif_adj"].sum() + cif["cif_adj"][0]) < TOL


def test_product_43_44_swap_flag(supply, use):
    """Verifier finding on io_tables-1: every row of the p043/p044 series (supply and use, both years)
    carries the series-level flag naming the swapped period and the partner product; no other row
    does. The flag is right: in 2023-24 (only) each row is produced by the partner's industry."""
    both = pl.concat([d.select("product", "period", "dim_other", "item_code", "industry", "value") for d in (supply, use)])
    flagged = both.filter(pl.col("dim_other").is_not_null() & pl.col("dim_other").str.contains("label_swap"))
    want = both.filter(pl.col("product").is_in(["sut_p043", "sut_p044"]))
    assert flagged.height == want.height > 0
    got = dict(flagged.group_by("product").agg(pl.col("dim_other").unique()).iter_rows())
    assert got == {
        "sut_p043": ["label_swap_period=2023-24;swap_partner=sut_p044"],
        "sut_p044": ["label_swap_period=2023-24;swap_partner=sut_p043"],
    }
    out = both.filter(pl.col("item_code") == "output")

    def producer(period, prod):
        return out.filter((pl.col("period") == period) & (pl.col("product") == prod)).sort("value")["industry"][-1]

    # 2022-23 correct (43 gas by industry 7), 2023-24 swapped (43 by industry 6 Crude Petroleum)
    assert (producer("2022-23", "sut_p043"), producer("2023-24", "sut_p044")) == ("sut_i07", "sut_i07")
    assert (producer("2022-23", "sut_p044"), producer("2023-24", "sut_p043")) == ("sut_i06", "sut_i06")


def test_provenance_locators_point_at_the_right_cells():
    """Verifier findings: the ADB locator must name TOTAL's real column (AS), and the SUT note locator the
    printed pages of each table (9.1: 14-15; 9.2: 15-16; printed = PDF page - 6)."""
    prov = checks.load_provenance(UNIT)
    loc = dict(prov.select("table_id", "locator").unique().iter_rows())
    assert "printed pages 14-15" in loc["Table 9.1"] and "printed pages 15-16" in loc["Table 9.2"]
    a = loc["IND IOT 2023"]
    assert "cols D:AS (c1-c35 D:AL, F1-F6 AM:AR, TOTAL AS)" in a
    raw = pinned_raw(Layout.default(), UNIT, ADB.SRC, ADB.FILE)
    wb = openpyxl.load_workbook(raw.path, read_only=True)
    ws = wb["2023"]
    hdr = {c: ws[f"{c}{ADB.HEADER_LABEL_ROW}"].value for c in ("D", "AL", "AM", "AR", "AS")}
    codes = {c: ws[f"{c}{ADB.HEADER_CODE_ROW}"].value for c in ("D", "AL", "AM", "AR")}
    wb.close()
    assert hdr["AS"] == "TOTAL" and codes == {"D": "c1", "AL": "c35", "AM": "F1", "AR": "F6"}


# ---------------------------------------------------------------------------------------------
# SUT: identities (rows and columns)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("period", PERIODS)
def test_supply_row_identities(supply, period):
    d = supply.filter(pl.col("product").str.starts_with("sut_p"))
    out = (
        d.filter((pl.col("item_code") == "output") & (pl.col("period") == period))
        .group_by("product", maintain_order=True)
        .agg(pl.col("value").sum().alias("out_sum"))
    )
    w = _wide(d.filter(pl.col("industry").is_null()), period, "product").join(out, on="product", how="left")
    w = w.fill_null(0.0)
    # 2023-24 product 126: Supply at BP is 1 crore below its row sum (issue io_tables-2)
    checks.assert_no_rows(_viol(w, pl.col("supply_bp"), pl.col("out_sum"), 1.0, "product"), "supply_bp = sum output")
    checks.assert_no_rows(
        _viol(w, pl.col("imports_after_cif"), pl.col("imports") + pl.col("cif_adj"), 0.01, "product"),
        "imports after cif = imports + cif adj",
    )
    rhs = sum(
        pl.col(c)
        for c in ("supply_bp", "imports_after_cif", "import_duty", "product_taxes", "product_subsidies", "ttm")
    )
    checks.assert_no_rows(_viol(w, pl.col("supply_pp"), rhs, 0.01, "product"), "supply at PP = components")


@pytest.mark.parametrize("period", PERIODS)
def test_use_row_identities_and_product_balance(supply, use, period):
    d = use.filter(pl.col("product").str.starts_with("sut_p"))
    ic = (
        d.filter((pl.col("item_code") == "ic") & (pl.col("period") == period))
        .group_by("product", maintain_order=True)
        .agg(pl.col("value").sum().alias("ic_sum"))
    )
    w = _wide(d.filter(pl.col("industry").is_null()), period, "product").join(ic, on="product", how="left")
    w = w.fill_null(0.0)
    # the printed 'Intermediate Consumption' column differs from its row sum by up to 1 crore (issue io_tables-2)
    checks.assert_no_rows(_viol(w, pl.col("ic_total"), pl.col("ic_sum"), 1.0, "product"), "IC total = sum IC")
    rhs = sum(pl.col(c) for c in ("ic_total", "pfce", "gfce", "gfcf", "cii", "valuables", "exports"))
    checks.assert_no_rows(_viol(w, pl.col("total_use_pp"), rhs, 0.01, "product"), "total use = components")
    s = _wide(supply.filter(pl.col("industry").is_null() & pl.col("product").str.starts_with("sut_p")), period, "product")
    j = s.select("product", "supply_pp").join(w.select("product", "total_use_pp"), on="product")
    # product balance: supply = use at purchasers' prices (MoSPI's balanced table; <= 1 crore per product)
    checks.assert_no_rows(_viol(j, pl.col("supply_pp"), pl.col("total_use_pp"), 1.0, "product"), "supply = use")


@pytest.mark.parametrize("period", PERIODS)
def test_industry_column_identities(supply, use, va, period):
    out = supply.filter(
        (pl.col("period") == period) & (pl.col("item_code") == "output") & pl.col("industry").is_not_null()
    )
    msum = (
        out.filter(pl.col("product").str.starts_with("sut_p"))
        .group_by("industry", maintain_order=True)
        .agg(pl.col("value").sum().alias("m"))
    )
    trow = out.filter(pl.col("product") == "total").select("industry", pl.col("value").alias("out"))
    ic = use.filter((pl.col("period") == period) & (pl.col("item_code") == "ic") & pl.col("industry").is_not_null())
    icsum = (
        ic.filter(pl.col("product").str.starts_with("sut_p"))
        .group_by("industry", maintain_order=True)
        .agg(pl.col("value").sum().alias("icm"))
    )
    icrow = ic.filter(pl.col("product") == "total").select("industry", pl.col("value").alias("ic"))
    a = _wide(va, period, "industry")
    j = trow.join(msum, on="industry").join(icrow, on="industry").join(icsum, on="industry").join(a, on="industry")
    assert j.height == 67
    # 'Total Output' / 'Total Use' rows = column sums (2023-24 industry 39: 1 crore off, issue io_tables-2)
    checks.assert_no_rows(_viol(j, pl.col("out"), pl.col("m"), 1.5, "industry"), "Total Output row = sum")
    checks.assert_no_rows(_viol(j, pl.col("ic"), pl.col("icm"), 1.0, "industry"), "Total Use row = sum")
    # GVA (production) = output - IC; GVA (income) = NPT + CFC + CE + OS/MI; both approaches agree
    checks.assert_no_rows(
        _viol(j, pl.col("gva_production"), pl.col("out") - pl.col("ic"), 1.0, "industry"), "GVA = output - IC"
    )
    inc = pl.col("net_production_taxes") + pl.col("cfc") + pl.col("ce") + pl.col("os_mi")
    checks.assert_no_rows(_viol(j, pl.col("gva_income"), inc, 1.0, "industry"), "GVA income = components")
    # 2023-24 trade (53) and hotels (54): the two GVA rows differ by 1.06 and 1.23 crore (issue io_tables-2)
    checks.assert_no_rows(
        _viol(j, pl.col("gva_production"), pl.col("gva_income"), 1.5, "industry"), "GVA production = income"
    )


@pytest.mark.parametrize("period", PERIODS)
def test_margins_and_cif_net_to_zero(supply, period):
    s = supply.filter((pl.col("period") == period) & pl.col("industry").is_null())
    ttm = s.filter((pl.col("item_code") == "ttm") & pl.col("product").str.starts_with("sut_p"))
    assert abs(ttm["value"].sum()) < 1.0  # gap map P3: 'the TTM column sums to ~0'
    cif = s.filter((pl.col("item_code") == "cif_adj") & (pl.col("product") != "total"))
    assert abs(cif["value"].sum()) < 0.01
    # negative margins sit only on the margin-supplying products: trade and transport (gap map P3)
    neg = set(ttm.filter(pl.col("value") < 0)["product"].to_list())
    assert neg <= {SUT.product_code(n) for n in (132, 133, 135, 136, 137, 138, 139, 140)}, neg


def test_margins_supplied_2023_24(supply):
    # gap map P3: 'Negative entries of SUT TTM column ... Sum 39,60,078 cr'
    ttm = supply.filter(
        (pl.col("period") == "2023-24") & (pl.col("item_code") == "ttm") & pl.col("product").str.starts_with("sut_p")
    )
    assert round(-ttm.filter(pl.col("value") < 0)["value"].sum()) == 3960078


# ---------------------------------------------------------------------------------------------
# SUT: ranges, signs, units, continuity
# ---------------------------------------------------------------------------------------------


def test_sut_signs_and_ranges(supply, use, va):
    for df in (supply, use, va):
        assert set(df["unit"].unique().to_list()) == {"INR_crore"}
        assert set(df["price_basis"].unique().to_list()) == {"current"}
        assert set(df["period"].unique().to_list()) == set(PERIODS)
        assert set(df["vintage"].unique().to_list()) == {"2026-08-31"}
    prod = pl.col("product").str.starts_with("sut_p")
    nonneg = ["imports", "import_duty", "product_taxes", "supply_bp", "supply_pp"]
    checks.assert_no_rows(
        supply.filter(prod & pl.col("item_code").is_in(nonneg) & (pl.col("value") < 0)), "negative supply entries"
    )
    # MoSPI's 2022-23 make matrix has 6 tiny negative cells (all > -0.4 crore; balancing residue): io_tables-3
    checks.assert_no_rows(supply.filter((pl.col("item_code") == "output") & (pl.col("value") < -1.0)), "output < -1")
    checks.assert_no_rows(
        supply.filter(prod & (pl.col("item_code") == "product_subsidies") & (pl.col("value") > 0)),
        "subsidies must be recorded negative",
    )
    nonneg_use = ["pfce", "gfce", "gfcf", "valuables", "exports", "total_use_pp"]
    checks.assert_no_rows(
        use.filter(prod & pl.col("item_code").is_in(nonneg_use) & (pl.col("value") < 0)), "negative final uses"
    )
    # MoSPI's balanced IC matrix has tiny negative cells (all > -1 crore; balancing residue): issue io_tables-3
    checks.assert_no_rows(use.filter((pl.col("item_code") == "ic") & (pl.col("value") < -1.0)), "IC below -1 crore")
    for item in ("ce", "cfc", "gva_production"):
        checks.assert_no_rows(va.filter((pl.col("item_code") == item) & (pl.col("value") < 0)), f"negative {item}")


def test_sut_counts(supply, use, va):
    for per in PERIODS:
        a = va.filter(pl.col("period") == per)
        assert a.height == 67 * 6
        assert a["industry"].n_unique() == 67
        s = supply.filter(pl.col("period") == per)
        assert s.filter(pl.col("item_code") == "supply_bp").height == 155 + 1  # 155 products + total
        u = use.filter(pl.col("period") == per)
        assert u.filter(pl.col("item_code") == "total_use_pp").height == 155 + 1


def test_gva_continuity_2022_23_to_2023_24(va):
    """Industry GVA moves less than 50% between the two SUT years, except the listed industries
    whose jumps were checked against the file (MoSPI's numbers, not parsing errors)."""
    g = va.filter(pl.col("item_code") == "gva_production")
    flagged = checks.check_continuity(g, max_rel_change=0.5, min_abs_level=1000)
    # Air transport (industry 49) GVA 20,686 -> 36,774 crore (+78%): MoSPI's figures (xlsx Use sheets, column
    # AY, rows 162 and 169 in both files); logged as io_tables-4 for the Phase 2 reviewers.
    explained = {"va.gva_production.sut_i49.current"}
    checks.assert_no_rows(flagged.filter(~pl.col("series_id").is_in(list(explained))), "GVA break")


def test_product_43_44_swap_is_as_published(supply):
    """Issue Q1 / io_tables-1: in 2023-24 the 'Natural Gas' row (serial 43) is produced by industry 6
    (Crude Petroleum); in 2022-23 by industry 7 (Natural Gas). Kept as published."""
    out = supply.filter(pl.col("item_code") == "output")

    def producer(period, prod):  # the main producing industry of a product row
        r = out.filter((pl.col("period") == period) & (pl.col("product") == prod)).sort("value", descending=True)
        return r["industry"][0]

    assert producer("2022-23", "sut_p043") == "sut_i07" and producer("2022-23", "sut_p044") == "sut_i06"
    assert producer("2023-24", "sut_p043") == "sut_i06" and producer("2023-24", "sut_p044") == "sut_i07"
    lab = supply.filter((pl.col("period") == "2023-24") & (pl.col("series_id") == "supply.imports.sut_p043.current"))
    assert lab["item_label"][0].startswith("Natural Gas")


def test_sut_raw_files_are_the_aug_2026_vintage():
    lay = Layout.default()
    for name, (_, prefix) in SUT.FILES.items():
        raw = pinned_raw(lay, UNIT, SUT.SRC, name)
        assert raw.sha256.startswith(prefix)
        wb = openpyxl.load_workbook(raw.path, read_only=True)
        assert wb.sheetnames[0].startswith("Supply Table")
        wb.close()


# ---------------------------------------------------------------------------------------------
# ADB India IOT (US$ million)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sid, period, expected, where",
    [
        ("adb.dom_c1.c1.current", "2023-24", 48721.8426392509, "ADB 2023 row IND c1 / col c1"),
        ("adb.imp_c1.c1.current", "2023-24", 372.69798366243776, "ADB 2023 row IMP c1 / col c1"),
        ("adb.dom_c1.f1.current", "2023-24", 407655.127726716, "ADB 2023 row IND c1 / col F1"),
        ("adb.r64.total.current", "2023-24", 3318751.5796841593, "ADB 2023 row r64 / TOTAL"),
    ],
)
def test_adb_anchor_cells(adb, sid, period, expected, where):
    assert v(adb, sid, period) == pytest.approx(expected, abs=1e-6), where


# Phase 0 verifier (docs/phase0/verify/international.md): sum of r64 over c1-c35 = 3,135,712 (2022)
# and 3,598,908 (2024); recon: 2,606,507 (2019), 3,318,752 (2023).
@pytest.mark.parametrize(
    "period, musd", [("2019-20", 2606507), ("2022-23", 3135712), ("2023-24", 3318752), ("2024-25", 3598908)]
)
def test_adb_value_added_totals(adb, period, musd):
    r = adb.filter(
        (pl.col("period") == period) & (pl.col("item_code") == "value_added_basic_prices")
        & pl.col("industry").str.contains(r"^adb_c\d+$")
    )
    assert r.height == 35
    assert round(r["value"].sum()) == musd


@pytest.mark.parametrize("period", ["2000-01", "2015-16", "2023-24", "2024-25"])
def test_adb_identities(adb, period):
    d = adb.filter(pl.col("period") == period)
    ind_cols = [f"adb_c{i}" for i in range(1, 36)]
    # column: r60 (intermediate input total) = sum of domestic + imported rows, r69 = r60 + r99 + r61-r64 + trs
    cols = d.group_by("industry", "item_code", maintain_order=True).agg(pl.col("value").sum())
    w = cols.pivot(on="item_code", index="industry", values="value").fill_null(0.0)
    w = w.filter(pl.col("industry").is_in(ind_cols))
    viol = _viol(w, pl.col("intermediate_input_total"), pl.col("domestic_use") + pl.col("imported_use"), 0.5, "industry")
    checks.assert_no_rows(viol, "ADB r60 = domestic + imported")
    rest = ["intermediate_input_total", "taxes_less_subsidies_on_products", "cif_fob_adjustments_on_exports",
            "direct_purchases_abroad_by_residents", "purchases_by_nonresidents_in_domestic_territory",
            "value_added_basic_prices", "international_transport_margins"]
    checks.assert_no_rows(_viol(w, pl.col("total"), sum(pl.col(c) for c in rest), 0.5, "industry"), "ADB r69")
    # row: TOTAL column = sum of c1..c35 + F1..F6 (every row); each industry's domestic row total
    # (its output) = its column total (r69)
    r = d.with_columns(pl.col("series_id").str.extract(r"^adb\.([a-z0-9_]+)\.", 1).alias("row"))
    body = r.filter(pl.col("industry") != "adb_TOTAL").group_by("row", maintain_order=True).agg(pl.col("value").sum())
    tot = r.filter(pl.col("industry") == "adb_TOTAL").select("row", pl.col("value").alias("t"))
    j = body.join(tot, on="row")
    assert j.height == 79
    # ADB prints TOTAL = 0 for the 'Total Imports' row in every sheet and for the IMP rows in the older
    # sheets (e.g. 2000, 2015); only those rows may have a zero TOTAL against a non-zero body (issue io_tables-6).
    zero_total = j.filter((pl.col("t") == 0) & (pl.col("value").abs() > 0.5))
    assert set(zero_total["row"].to_list()) <= {"m"} | {f"imp_c{i}" for i in range(1, 36)}
    j = j.filter(~((pl.col("t") == 0) & pl.col("row").str.contains(r"^(m|imp_c\d+)$")))
    checks.assert_no_rows(_viol(j, pl.col("t"), pl.col("value"), 0.5, "row"), "ADB row totals")
    out = tot.filter(pl.col("row").str.starts_with("dom_c")).select(
        ("adb_" + pl.col("row").str.slice(4)).alias("industry"), "t"
    )
    j = out.join(w.select("industry", "total"), on="industry")
    assert j.height == 35
    checks.assert_no_rows(_viol(j, pl.col("t"), pl.col("total"), 0.5, "industry"), "ADB output row = column")


def test_adb_years_units_and_zero_rows(adb):
    assert set(adb["unit"].unique().to_list()) == {"USD_million"}
    years = sorted(adb["period"].unique().to_list())
    assert years == ["2000-01"] + [f"{y}-{(y + 1) % 100:02d}" for y in range(2007, 2025)]
    # registry quirk: r62 and r63 are zero for India in every year; trs (international transport margins)
    # is zero from 2015-16 on but filled for 2000-01 and 2007-08..2014-15 (the registry note covers recent years)
    z = adb.filter(pl.col("item_code").is_in(["direct_purchases_abroad_by_residents",
                                              "purchases_by_nonresidents_in_domestic_territory"]))
    assert z["value"].abs().max() == 0.0
    trs = adb.filter((pl.col("item_code") == "international_transport_margins") & (pl.col("value") != 0))
    assert max(trs["period"].to_list()) == "2014-15"
    # vintages are the per-sheet stamps
    assert dict(adb.select("period", "vintage").unique().sort("period").iter_rows())["2019-20"] == "2024-09"
    assert dict(adb.select("period", "vintage").unique().sort("period").iter_rows())["2023-24"] == "2025-08"


def test_adb_continuity_of_value_added(adb):
    """Total value added (US$) moves less than 30% a year; the only larger step is 2000-01 -> 2007-08,
    which spans the file's gap (no 2001-2006 sheets). (2009-10 -> 2010-11 is +25.4%: rupee appreciation
    plus nominal growth.)"""
    va_by = (
        adb.filter((pl.col("item_code") == "value_added_basic_prices") & pl.col("industry").str.contains(r"^adb_c\d+$"))
        .group_by("period", maintain_order=True)
        .agg(pl.col("value").sum())
        .sort("period")
    )
    pers, vals = va_by["period"].to_list(), va_by["value"].to_list()
    jumps = [(pers[i], pers[i + 1]) for i in range(len(vals) - 1) if abs(vals[i + 1] / vals[i] - 1) > 0.30]
    assert jumps == [("2000-01", "2007-08")]


# ---------------------------------------------------------------------------------------------
# OECD ICIO 2025, India slice (US$ million)
# ---------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def icio_raw_2022():
    """The 2022 CSV read with the csv module (not polars): an independent path to the source cells."""
    raw = pinned_raw(Layout.default(), UNIT, ICIO.SRC, ICIO.ZIP)
    with zipfile.ZipFile(raw.path) as z:
        text = z.read("2022_SML.csv").decode("utf-8")
    rdr = csv.reader(io.StringIO(text))
    header = next(rdr)
    idx = {h: i for i, h in enumerate(header)}
    rows = {r[0]: r for r in rdr}
    return idx, rows


@pytest.mark.parametrize(
    "row, col, sid",
    [
        ("IND_C19", "IND_C20", "icio.dom.c19.c20.current"),
        ("IND_A01", "IND_HFCE", "icio.dom.a01.hfce.current"),
        ("IND_F", "IND_GFCF", "icio.dom.f.gfcf.current"),
        ("VA", "IND_J62_63", "icio.va.j62_63.current"),
        ("TLS", "IND_HFCE", "icio.tls.hfce.current"),
        ("OUT", "IND_C26", "icio.out_row.c26.current"),
    ],
)
def test_icio_official_cells_equal_raw_csv(icio, icio_raw_2022, row, col, sid):
    idx, rows = icio_raw_2022
    assert v(icio, sid, "2022-23") == pytest.approx(float(rows[row][idx[col]]), abs=1e-6)


def test_icio_import_sum_equals_raw_csv(icio, icio_raw_2022):
    idx, rows = icio_raw_2022
    for ind, col in (("B06", "IND_C19"), ("C26", "IND_C26"), ("C26", "IND_HFCE")):
        expect = sum(float(r[idx[col]]) for k, r in rows.items() if k.endswith(f"_{ind}") and not k.startswith("IND_"))
        got = v(icio, f"icio.imp.{ind.lower()}.{col[4:].lower()}.current", "2022-23")
        assert got == pytest.approx(expect, rel=1e-9)


@pytest.mark.parametrize("period", ["2016-17", "2019-20", "2022-23"])
def test_icio_output_identities(icio, period):
    d = icio.filter(pl.col("period") == period)
    # column: output (OUT row) = domestic + imported intermediate inputs + TLS + VA, for each Indian industry
    ind_cols = [f"icio_{c}" for c in ICIO.INDUSTRIES]
    colsum = (
        d.filter(pl.col("item_code").is_in(["domestic_use", "imported_use", "tls", "va"]))
        .filter(pl.col("industry").is_in(ind_cols))
        .group_by("industry", maintain_order=True)
        .agg(pl.col("value").sum().alias("inputs"))
    )
    out = d.filter(pl.col("item_code") == "out_row").select("industry", pl.col("value").alias("out"))
    j = colsum.join(out, on="industry")
    assert j.height == 50
    checks.assert_no_rows(_viol(j, pl.col("out"), pl.col("inputs"), 1.0, "industry"), "ICIO column output")
    # row: output (OUT column) = domestic intermediate + final use + exports, for each Indian product
    rowsum = (
        d.filter(pl.col("item_code").is_in(["domestic_use", "exports"]))
        .group_by("product", maintain_order=True)
        .agg(pl.col("value").sum().alias("uses"))
    )
    outc = d.filter(pl.col("item_code") == "output").select("product", pl.col("value").alias("out"))
    j = rowsum.join(outc, on="product")
    assert j.height == 50
    # OECD's own real-estate rows do not add up exactly (raw 2022 CSV: IND_L row sum 242,502.83 vs OUT
    # 242,479.07; USA_L off by 238.6), so the tolerance is 0.02% of output, not 1 US$ million.
    j = j.with_columns((pl.col("out") - pl.col("uses")).abs().alias("gap"))
    checks.assert_no_rows(j.filter(pl.col("gap") > pl.max_horizontal(pl.lit(1.0), 2e-4 * pl.col("out"))), "ICIO rows")


def test_icio_statuses_units_years(icio):
    assert set(icio["unit"].unique().to_list()) == {"USD_million"}
    st = dict(icio.group_by("item_code", maintain_order=True).agg(pl.col("status").first()).iter_rows())
    assert st["imported_use"] == "derived" and st["exports"] == "derived" and st["domestic_use"] == "official"
    assert sorted(icio["period"].unique().to_list()) == [f"{y}-{(y + 1) % 100:02d}" for y in range(2016, 2023)]
    # crude oil (B06) is India's largest imported intermediate input into refining (C19)
    imp = icio.filter((pl.col("period") == "2022-23") & (pl.col("item_code") == "imported_use"))
    into_c19 = imp.filter(pl.col("industry") == "icio_C19").sort("value", descending=True)
    assert into_c19["product"][0] == "icio_B06"


# ---------------------------------------------------------------------------------------------
# Energy PSUT (Energy Statistics 2026, Ch. 9; clean dataset io_tables_energy_psut, unit PJ, gap map S6).
# The `psut` fixture re-parses the raw PDF; the `psut_clean` tests read the written dataset.
# ---------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def psut():
    from pipeline.ingest.io_tables import energy as EN

    raw = pinned_raw(Layout.default(), UNIT, EN.SRC, EN.FILE)
    cells = EN.parse_all(str(raw.path))
    return {(c.table.table_id, c.section, c.label, c.column): c.value for c in cells}


@pytest.mark.parametrize(
    "key, pj",
    [
        # Table 9.2 (A), PDF p. 12 (printed p. 126): physical supply 2023-24
        (("Table 9.2 (A)", "energy_products.production", "Coal", "isic_b"), 16906),
        (("Table 9.2 (A)", "energy_products.production", "Coal", "rest_of_world_imports"), 5930),
        (("Table 9.2 (A)", "energy_products.production", "Oil Products", "isic_c"), 11810.85),
        (("Table 9.2 (A)", "energy_products.production", "Electricity", "isic_d"), 7051),
        (("Table 9.2 (A)", "total", "TOTAL SUPPLY", "total"), 109671),
        # Table 9.2 (B), PDF p. 13 (printed p. 127): physical use 2023-24
        (("Table 9.2 (B)", "energy_products.transformation", "Coal", "isic_d"), 15754),
        (("Table 9.2 (B)", "energy_products.end_use", "Oil Products", "transport_storage"), 5064),
        (("Table 9.2 (B)", "energy_products.end_use", "Electricity", "households"), 1329),
        (("Table 9.2 (B)", "energy_products.end_use", "Coal", "isic_a"), 0.089786),
        (("Table 9.2 (B)", "total", "TOTAL USE", "total"), 109800),
        # Table 9.3 (A)/(B), PDF pp. 14-15: 2024-25 (P)
        (("Table 9.3 (A)", "energy_products.production", "Coal", "isic_b"), 17655),
        (("Table 9.3 (B)", "energy_products.end_use", "Electricity", "households"), 1471),
        (("Table 9.3 (B)", "total", "TOTAL USE", "total"), 113509),
    ],
)
def test_psut_anchor_values(psut, key, pj):
    assert psut[key] == pytest.approx(pj, abs=1e-6)


@pytest.mark.parametrize("sup, use", [("Table 9.2 (A)", "Table 9.2 (B)"), ("Table 9.3 (A)", "Table 9.3 (B)")])
def test_psut_product_balance(psut, sup, use):
    """SEEA identity (ii) in the chapter: supply of each energy product = transformation + end use.
    Oil products do not balance in the publication itself (2023-24: 13,829 supplied vs 85 + 13,874 used;
    the same ~130 PJ is the gap between TOTAL SUPPLY 109,671 and TOTAL USE 109,800): issue io_tables-7."""
    bad = {}
    for prod in ("Coal", "Lignite", "Crude Oil", "Natural Gas", "Electricity", "Oil Products"):
        s = psut[(sup, "energy_products.production", prod, "total")]
        u = psut.get((use, "energy_products.transformation", prod, "total"), 0.0) + psut[
            (use, "energy_products.end_use", prod, "total")
        ]
        if abs(s - u) > 2.0:
            bad[prod] = round(u - s)
    assert set(bad) <= {"Oil Products"} and all(100 <= g <= 150 for g in bad.values()), bad


@pytest.fixture(scope="module")
def psut_clean():
    return checks.load_dataset(UNIT, "io_tables_energy_psut")


def test_psut_clean_is_the_parsed_pdf(psut, psut_clean):
    """Every parsed cell is written once, in PJ, as printed (6-decimal rounding by the writer: the one
    longer printed value, 0.16179072 in Table 9.3 (B), is stored as 0.161791; io_tables-17)."""
    from pipeline.ingest.io_tables import energy as EN

    assert psut_clean.height == len(psut) == 324
    assert psut_clean.group_by("table_id").len().sort("table_id")["len"].to_list() == [56, 106, 56, 106]
    assert set(psut_clean["unit"]) == {"PJ"} and set(psut_clean["status"]) == {"official"}
    assert set(psut_clean["price_basis"]) == {"n/a"} and set(psut_clean["vintage"]) == {EN.VINTAGE}
    stage = dict(psut_clean.select("period", "estimate_stage").unique().iter_rows())
    assert stage == {"2023-24": "n.a.", "2024-25": "Provisional"}
    tab = {t.table_id: t for t in EN.TABLES}
    got = {
        (r["table_id"], r["series_id"]): r["value"]
        for r in psut_clean.select("table_id", "series_id", "value").iter_rows(named=True)
    }
    want = {
        (t, f"psut.{tab[t].kind}.{sec}.{EN.slug(lab)}.{col}"): v for (t, sec, lab, col), v in psut.items()
    }
    assert got.keys() == want.keys()
    bad = {k: (got[k], v) for k, v in want.items() if abs(got[k] - v) > 5e-7}
    assert not bad, bad


@pytest.mark.parametrize(
    "period, series_id, pj",
    [
        # Table 9.2 (B), PDF p. 13 (printed p. 127): end use 2023-24 by industry
        ("2023-24", "psut.use.energy_products.end_use.coal.isic_c", 6902),
        ("2023-24", "psut.use.energy_products.end_use.oil_products.transport_storage", 5064),
        ("2023-24", "psut.use.energy_products.end_use.electricity.other_industries", 1982),
        ("2023-24", "psut.use.energy_products.end_use.oil_products.construction", 19),
        ("2023-24", "psut.use.energy_products.transformation.coal.isic_d", 15754),
        ("2023-24", "psut.use.total.total_use.total", 109800),
        # Table 9.2 (A), PDF p. 12 (printed p. 126)
        ("2023-24", "psut.supply.energy_products.production.crude_oil.rest_of_world_imports", 10024),
        ("2023-24", "psut.supply.total.total_supply.total", 109671),
        # Table 9.3 (B), PDF p. 15: 2024-25 (P)
        ("2024-25", "psut.use.energy_products.end_use.electricity.households", 1471),
        ("2024-25", "psut.use.energy_products.end_use.coal.isic_a", 0.161791),
    ],
)
def test_psut_clean_anchor_values(psut_clean, period, series_id, pj):
    r = psut_clean.filter((pl.col("period") == period) & (pl.col("series_id") == series_id))
    assert r.height == 1 and r["value"][0] == pytest.approx(pj, abs=1e-6)


def test_psut_dimensions(psut_clean):
    """Dims follow the printed column (energy.py docstring): industry only on the 7 industry columns,
    households as an institution, RoW / environment as counterparties, psut_column on every row."""
    from pipeline.ingest.io_tables import energy as EN

    col = psut_clean["series_id"].str.split(".").list.last()
    assert (psut_clean["dim_other"] == ("psut_column=" + col)).all()
    ind = psut_clean.filter(pl.col("industry").is_not_null())
    assert (ind["industry"] == ind["series_id"].str.split(".").list.last()).all()
    assert set(ind["industry"]) == set(EN.INDUSTRY_COLS)
    assert set(psut_clean.filter(pl.col("institution").is_not_null())["dim_other"]) == {"psut_column=households"}
    cp_rows = psut_clean.filter(pl.col("counterparty").is_not_null()).select("dim_other", "counterparty").unique()
    cp = dict(cp_rows.iter_rows())
    assert cp == {
        "psut_column=rest_of_world_imports": "rest_of_world",
        "psut_column=exports": "rest_of_world",
        "psut_column=environment": "environment",
        "psut_column=flows_to_environment": "environment",
    }
    prod = psut_clean.filter(pl.col("product").is_not_null())
    assert set(prod["product"]) == set(EN.SIEC_PRODUCTS)
    ic = prod["item_code"]
    assert (ic.str.starts_with("energy_products.") | ic.str.starts_with("natural_inputs.")).all()
    assert psut_clean.filter(pl.col("item_code").str.contains("non_energy_purposes"))["product"].is_null().all()
    # side follows the table
    side = psut_clean.select(pl.col("table_id").str.ends_with("(A)"), pl.col("side"))
    assert side.filter(pl.col("table_id"))["side"].unique().to_list() == ["resources"]
    assert side.filter(~pl.col("table_id"))["side"].unique().to_list() == ["uses"]


# The printed 'Total End Use for Energy purposes' sub-total row of Table 9.2 (B), PDF p. 13, is not ingested
# (its first number is overprinted on the label: 'purpo1s1e8s3' = 1183). It is an independent check of the
# end-use cells by column, 2023-24.
END_USE_SUBTOTAL_2023_24 = {
    "isic_a": 1183, "isic_b": 497, "isic_c": 10682, "isic_d": 384, "transport_storage": 5783, "construction": 19,
    "other_industries": 6472, "households": 2582, "accumulation": 434, "exports": 2820,
    "statistical_difference": -376, "total": 30478,
}


def test_psut_end_use_by_industry_matches_printed_subtotal(psut_clean):
    """Gap map S6: energy end use by industry 2023-24 = the printed sub-total row (within 2 PJ of rounding)."""
    eu = psut_clean.filter(
        (pl.col("period") == "2023-24") & pl.col("item_code").str.starts_with("energy_products.end_use.")
    ).with_columns(pl.col("series_id").str.split(".").list.last().alias("col"))
    got = dict(eu.group_by("col").agg(pl.col("value").sum()).iter_rows())
    bad = {c: (got.get(c), v) for c, v in END_USE_SUBTOTAL_2023_24.items() if abs(got.get(c, 0.0) - v) > 2.0}
    assert not bad, bad


@pytest.mark.parametrize("table_id", ["Table 9.2 (A)", "Table 9.2 (B)", "Table 9.3 (A)", "Table 9.3 (B)"])
def test_psut_clean_rows_add_to_total_column(psut_clean, table_id):
    """Each printed row: its columns add up to its Total column (2 PJ rounding tolerance)."""
    t = psut_clean.filter(pl.col("table_id") == table_id)
    t = t.with_columns(pl.col("series_id").str.replace(r"\.[a-z_]+$", "").alias("row"))
    parts = t.filter(~pl.col("series_id").str.ends_with(".total"))
    for row in parts["row"].unique().sort().to_list():
        coef = {s: 1.0 for s in parts.filter(pl.col("row") == row)["series_id"].to_list()}
        checks.assert_no_rows(
            checks.check_identity(t, f"{row}.total", coef, abs_tol=2.0), f"{table_id} {row}: parts = Total"
        )


# ---------------------------------------------------------------------------------------------
# IFPRI India SAM 2022/23 data paper (printed tables; labelled 'estimated' priors)
# ---------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def ifpri():
    return checks.load_dataset(UNIT, "io_tables_ifpri_2223_datapaper")


# Table 8 (paper p. 24), Rs billion as printed; the registry quotes the same figures (entry
# ifpri_nexus_sam_india_2022_23 key_series 'Table 8').
@pytest.mark.parametrize(
    "cell, bn",
    [
        ("factors.activities", 246992), ("taxes.commodities", 22743), ("commodities.households", 139795),
        ("commodities.government", 28836), ("commodities.investment", 92604), ("commodities.rest_of_world", 61334),
        ("rest_of_world.commodities", 70532), ("savings.enterprises", 49632), ("savings.households", 47714),
        ("savings.government", -9855), ("savings.rest_of_world", 5113), ("taxes.activities", -428),
    ],
)
def test_ifpri_macro_sam_values(ifpri, cell, bn):
    assert v(ifpri, f"ifpri.t8.{cell}.current", "2022-23") == pytest.approx(bn * 100)


def test_ifpri_macro_sam_balances(ifpri):
    t8 = ifpri.filter(pl.col("table_id") == "Table 8").with_columns(
        pl.col("series_id").str.split(".").list.get(2).alias("r"), pl.col("series_id").str.split(".").list.get(3).alias("c")
    )
    rows = t8.filter((pl.col("r") != "total") & (pl.col("c") != "total"))
    rs = dict(rows.group_by("r", maintain_order=True).agg(pl.col("value").sum()).iter_rows())
    cs = dict(rows.group_by("c", maintain_order=True).agg(pl.col("value").sum()).iter_rows())
    for acc in ("activities", "commodities", "factors", "enterprises", "households", "government", "taxes"):
        assert rs[acc] == pytest.approx(cs[acc], abs=500)  # a SAM: row total = column total (<= 5 bn rounding)
    assert rs["savings"] == pytest.approx(cs["investment"], abs=500)


def test_ifpri_household_tables(ifpri):
    t10 = ifpri.filter(pl.col("table_id") == "Table 10")
    # Table 10 (p. 26): 'Quintile 5' labour 44.7, government transfers 11.0; 'Urban' crop land 0.2
    assert v(t10, "ifpri.t10.labour_all.q5", "2022-23") == 44.7
    assert v(t10, "ifpri.t10.transfers_government.q5", "2022-23") == 11.0
    assert v(t10, "ifpri.t10.crop_land.urban", "2022-23") == 0.2
    for g in ("all", "q1", "q2", "q3", "q4", "q5", "rural", "urban"):
        parts = sum(v(t10, f"ifpri.t10.{c}.{g}", "2022-23") for c in
                    ("labour_all", "crop_land", "capital_all", "transfers_government", "transfers_world"))
        assert parts == pytest.approx(100.0, abs=0.3), g
        lab = sum(v(t10, f"ifpri.t10.labour_{e}_educated.{g}", "2022-23") for e in ("low", "medium", "high"))
        assert lab == pytest.approx(v(t10, f"ifpri.t10.labour_all.{g}", "2022-23"), abs=0.3), g
    t11 = ifpri.filter(pl.col("table_id") == "Table 11")
    # Table 11 (p. 26): all households 1,406.6 million people; quintile 5 consumption share 41.6%
    assert v(t11, "ifpri.t11.population.all", "2022-23") == pytest.approx(1406.6e6)
    assert v(t11, "ifpri.t11.consumption_share.q5", "2022-23") == 41.6
    assert v(t11, "ifpri.t11.consumption_per_capita.q1", "2022-23") == 45000.0
    shares = sum(v(t11, f"ifpri.t11.consumption_share.q{i}", "2022-23") for i in range(1, 6))
    assert shares == pytest.approx(100.0, abs=0.3)
    assert set(ifpri["status"].unique().to_list()) == {"estimated"}
