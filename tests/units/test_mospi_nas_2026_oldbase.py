"""Value tests for the old-base (2011-12) datasets of the mospi_nas_2026 unit: NAS 2024 sequences
of accounts (1.15, 2.x, 3.x, 4.0, 5.0, 6.0) and NAS 2025 Statements 1.1, 1.9, 1.14, 5.3.

They are ratio/history inputs only: these tests also pin that they never mix with the new base.
"""

from __future__ import annotations

import polars as pl
import pytest

from pipeline.core import checks

pytestmark = pytest.mark.quality
U = "mospi_nas_2026"
SOA = ["s1_15", "s2_0", "s2_1", "s2_1a", "s2_1b", "s2_2", "s3_0", "s3_1", "s3_2", "s4_0", "s5_0", "s6_0"]
NAS25 = ["s1_1", "s1_9", "s1_14", "s5_3"]
OLD = [f"oldbase_soa_{s}" for s in SOA] + [f"oldbase_nas2025_{s}" for s in NAS25]
YEARS_2024 = [f"{y}-{str(y + 1)[2:]}" for y in range(2011, 2023)]
_cache: dict[str, pl.DataFrame] = {}


def ds(name: str) -> pl.DataFrame:
    if name not in _cache:
        _cache[name] = checks.load_dataset(U, f"{U}_{name}")
    return _cache[name]


def ident(df: pl.DataFrame, total: str, parts: dict[str, float], what: str, tol: float = 2.0) -> None:
    checks.assert_no_rows(checks.check_identity(df, total, parts, by=("period",), abs_tol=tol), what)


# values quoted in docs/phase0/recon/mospi_nas.md s1.4 and docs/phase0/verify/mospi_nas.md
DOC_VALUES = [
    ("oldbase_nas2025_s1_1", "oldbase_nas2025_s1_1.gdp.current", "2022-23", 26890473),
    ("oldbase_nas2025_s1_1", "oldbase_nas2025_s1_1.gdp.current", "2023-24", 30122956),
    ("oldbase_nas2025_s1_1", "oldbase_nas2025_s1_1.discrepancies.current", "2022-23", -474817),
    ("oldbase_nas2025_s5_3", "oldbase_nas2025_s5_3.household_saving_1_2_3_4.current", "2011-12", 2065566),
]


@pytest.mark.parametrize("name, sid, period, crore", DOC_VALUES, ids=[f"{d[1]}@{d[2]}" for d in DOC_VALUES])
def test_values_quoted_in_phase0_notes(name, sid, period, crore):
    assert round(checks.value(ds(name), sid, period)) == crore


ANCHORS = [
    # (dataset, series, period, value, pinned-file cell)
    ("oldbase_soa_s5_0", "oldbase_soa_s5_0.production.resources.p1.current", "2011-12", 5974183.7, "5.0!C11"),
    ("oldbase_nas2025_s1_9", "oldbase_nas2025_s1_9.gross_savings.current", "2011-12", 3026836.9, "1.9!C8"),
    ("oldbase_nas2025_s1_1", "oldbase_nas2025_s1_1.gva_basic.current", "2011-12", 8106946.0, "1.1!C8"),
    ("oldbase_nas2025_s1_1", "oldbase_nas2025_s1_1.gva_basic.constant_2011_12", "2022-23", 14878028.3, "1.1!AA8"),
    ("oldbase_nas2025_s1_1", "oldbase_nas2025_s1_1.cfc.constant_2011_12", "2022-23", 2087963.7, "1.1!AA12"),
    ("oldbase_nas2025_s1_1", "oldbase_nas2025_s1_1.gni.constant_2011_12", "2022-23", 15939375.8, "1.1!AA30"),
    ("oldbase_nas2025_s1_1", "oldbase_nas2025_s1_1.valuables_pct_gdp.current", "2022-23", 1.3, "1.1!N47"),
    ("oldbase_nas2025_s1_14", "oldbase_nas2025_s1_14.fc_private.gross_savings.current", "2022-23", 305600.0, "1.14!N27"),
    ("oldbase_nas2025_s1_14", "oldbase_nas2025_s1_14.fc_private.consumption_of_fixed_capital.current", "2022-23", 25895.3, "1.14!N29"),
    ("oldbase_nas2025_s1_14", "oldbase_nas2025_s1_14.households_npish.consumption_of_fixed_capital.current", "2022-23", 1182718.2, "1.14!N43"),
    ("oldbase_nas2025_s1_14", "oldbase_nas2025_s1_14.nfc_public.gross_value_added_at_basic_prices.current", "2022-23", 1256277.6, "1.14!N11"),
    ("oldbase_nas2025_s1_9", "oldbase_nas2025_s1_9.gross_savings.current", "2022-23", 8244048.3, "1.9!N8"),
    ("oldbase_nas2025_s1_9", "oldbase_nas2025_s1_9.finances_for_gross_capital_formation_1_2.current", "2022-23", 8771573.2, "1.9!N26"),
    ("oldbase_nas2025_s1_9", "oldbase_nas2025_s1_9.private_non_financial_corporations.current", "2022-23", 2644507.4, "1.9!N13"),
    ("oldbase_nas2025_s1_9", "oldbase_nas2025_s1_9.savings_of_co_operatives_banks_and_societies.current", "2022-23", 33224.7, "1.9!N29"),
    ("oldbase_nas2025_s5_3", "oldbase_nas2025_s5_3.bank_advances.current", "2022-23", 1191387.0, "5.3!N32"),
    ("oldbase_nas2025_s5_3", "oldbase_nas2025_s5_3.loans_by_financial_corporations_and_non_banking_companies.current", "2022-23", 334556.0, "5.3!N34"),
    ("oldbase_nas2025_s5_3", "oldbase_nas2025_s5_3.with_non_banking_companies.current", "2022-23", 67275.0, "5.3!N14"),
    ("oldbase_soa_s1_15", "oldbase_soa_s1_15.allocation_of_primary_income.resources.b2n_b3n.current", "2022-23", 12630865.7, "1.15!N34"),
    ("oldbase_soa_s1_15", "oldbase_soa_s1_15.financial.liabilities.f8.current", "2022-23", 2387686.4, "1.15!N137"),
    ("oldbase_soa_s1_15", "oldbase_soa_s1_15.use_of_disposable_income.uses.p32.current", "2022-23", 2883648.5, "1.15!N88"),
    ("oldbase_soa_s2_0", "oldbase_soa_s2_0.allocation_of_primary_income.resources.b2n_b3n.current", "2022-23", 4306092.6, "S2.0!N31"),
    ("oldbase_soa_s2_0", "oldbase_soa_s2_0.financial.liabilities.f3.current", "2022-23", 41960.3, "S2.0!N94"),
    ("oldbase_soa_s2_0", "oldbase_soa_s2_0.use_of_disposable_income.uses.b8n.current", "2022-23", 1370019.6, "S2.0!N62"),
    ("oldbase_soa_s2_1", "oldbase_soa_s2_1.allocation_of_primary_income.resources.b2n_b3n.current", "2022-23", 442782.3, "S2.1!N32"),
    ("oldbase_soa_s2_1", "oldbase_soa_s2_1.financial.liabilities.f4.current", "2022-23", 232521.0, "S2.1!N96"),
    ("oldbase_soa_s2_1", "oldbase_soa_s2_1.use_of_disposable_income.uses.b8n.current", "2022-23", 2877.6, "S2.1!N56"),
    ("oldbase_soa_s2_1a", "oldbase_soa_s2_1a.allocation_of_primary_income.resources.b2n_b3n.current", "2022-23", 170847.3, "S2.1A!N30"),
    ("oldbase_soa_s2_1a", "oldbase_soa_s2_1a.financial.liabilities.f8.current", "2022-23", 196672.7, "S2.1A!N90"),
    ("oldbase_soa_s2_1a", "oldbase_soa_s2_1a.use_of_disposable_income.uses.b8n.current", "2022-23", 6820.3, "S2.1A!N54"),
    ("oldbase_soa_s2_1b", "oldbase_soa_s2_1b.allocation_of_primary_income.resources.b2n_b3n.current", "2022-23", 271935.0, "S2.1B!N32"),
    ("oldbase_soa_s2_1b", "oldbase_soa_s2_1b.financial.liabilities.f4.current", "2022-23", 232521.0, "S2.1B!N96"),
    ("oldbase_soa_s2_1b", "oldbase_soa_s2_1b.use_of_disposable_income.uses.b8n.current", "2022-23", -3942.7, "S2.1B!N56"),
    ("oldbase_soa_s2_2", "oldbase_soa_s2_2.allocation_of_primary_income.resources.b2n_b3n.current", "2022-23", 3863310.3, "S2.2!N31"),
    ("oldbase_soa_s2_2", "oldbase_soa_s2_2.financial.liabilities.f3.current", "2022-23", 37460.2, "S2.2!N94"),
    ("oldbase_soa_s2_2", "oldbase_soa_s2_2.use_of_disposable_income.uses.b8n.current", "2022-23", 1367142.0, "S2.2!N62"),
    ("oldbase_soa_s3_0", "oldbase_soa_s3_0.allocation_of_primary_income.resources.b2n_b3n.current", "2022-23", 938648.6, "S3.0!N32"),
    # 3.0 liabilities: codes from column A (column P is shifted one row down in this block: verify-1)
    ("oldbase_soa_s3_0", "oldbase_soa_s3_0.financial.liabilities.f2.current", "2022-23", 2005617.5, "S3.0!N94"),
    ("oldbase_soa_s3_0", "oldbase_soa_s3_0.financial.liabilities.f3.current", "2022-23", 276987.9, "S3.0!N95"),
    ("oldbase_soa_s3_0", "oldbase_soa_s3_0.financial.liabilities.f8.current", "2022-23", 650207.1, "S3.0!N100"),
    ("oldbase_soa_s3_0", "oldbase_soa_s3_0.financial.liabilities.b9.current", "2022-23", 909872.4, "S3.0!N101"),
    ("oldbase_soa_s3_0", "oldbase_soa_s3_0.financial.liabilities.net_incurrence_of_liabilities.current", "2022-23",
     4277019.5, "S3.0!N92"),
    ("oldbase_soa_s3_0", "oldbase_soa_s3_0.use_of_disposable_income.uses.b8n.current", "2022-23", 726324.4, "S3.0!N56"),
    ("oldbase_soa_s3_1", "oldbase_soa_s3_1.allocation_of_primary_income.resources.b2n_b3n.current", "2022-23", 390572.7, "S3.1!N32"),
    ("oldbase_soa_s3_1", "oldbase_soa_s3_1.financial.liabilities.f3.current", "2022-23", 180813.0, "S3.1!N95"),
    ("oldbase_soa_s3_1", "oldbase_soa_s3_1.use_of_disposable_income.uses.b8n.current", "2022-23", 453992.3, "S3.1!N56"),
    ("oldbase_soa_s3_2", "oldbase_soa_s3_2.allocation_of_primary_income.resources.b2n_b3n.current", "2022-23", 548075.9, "S3.2!N32"),
    ("oldbase_soa_s3_2", "oldbase_soa_s3_2.financial.liabilities.f3.current", "2022-23", 96174.8, "S3.2!N95"),
    ("oldbase_soa_s3_2", "oldbase_soa_s3_2.use_of_disposable_income.uses.b8n.current", "2022-23", 272332.1, "S3.2!N56"),
    ("oldbase_soa_s4_0", "oldbase_soa_s4_0.allocation_of_primary_income.resources.d2.current", "2022-23", 3326676.5, "S4.0!N35"),
    ("oldbase_soa_s4_0", "oldbase_soa_s4_0.financial.liabilities.f8.current", "2022-23", 82764.2, "S4.0!N127"),
    ("oldbase_soa_s4_0", "oldbase_soa_s4_0.use_of_disposable_income.uses.p32.current", "2022-23", 2020210.0, "S4.0!N79"),
    ("oldbase_soa_s5_0", "oldbase_soa_s5_0.allocation_of_primary_income.resources.b2n_b3n.current", "2022-23", 7386124.4, "5.0!N32"),
    ("oldbase_soa_s5_0", "oldbase_soa_s5_0.generation_of_income.uses.d2.current", "2022-23", 190774.2, "5.0!N26"),
    ("oldbase_soa_s5_0", "oldbase_soa_s5_0.use_of_disposable_income.uses.p31.current", "2022-23", 16422535.4, "5.0!N76"),
    ("oldbase_soa_s6_0", "oldbase_soa_s6_0.capital.assets.b9.current", "2022-23", 535134.8, "6.0!N74"),
    ("oldbase_soa_s6_0", "oldbase_soa_s6_0.external_of_primary_income.resources.d1.current", "2022-23", 27526.5, "6.0!N26"),
    ("oldbase_soa_s6_0", "oldbase_soa_s6_0.financial.liabilities.f8.current", "2022-23", -58028.7, "6.0!N87"),
]


@pytest.mark.parametrize("name, sid, period, value, cell", ANCHORS, ids=[f"{a[1]}@{a[2]}" for a in ANCHORS])
def test_anchor_values(name, sid, period, value, cell):
    got = checks.value(ds(name), sid, period)
    assert abs(got - value) < 0.051, f"{sid} {period}: {got} != {value} (pinned file cell {cell})"


def test_every_dataset_has_anchors():
    assert {a[0] for a in ANCHORS} == set(OLD)
    for name in OLD:
        assert sum(a[0] == name for a in ANCHORS) >= 3, name


def _g(name: str, key: str) -> str:
    return f"{name}.{key}.current"


@pytest.mark.parametrize("s", [s for s in SOA if s != "s6_0"])
def test_production_account(s):
    n = f"oldbase_soa_{s}"
    d = ds(n)
    parts = {_g(n, "production.resources.p1"): 1, _g(n, "production.uses.p2"): -1}
    if s == "s1_15":  # total economy: GDP = output + taxes on products - subsidies - IC
        parts |= {_g(n, "production.resources.d21"): 1, _g(n, "production.resources.d31"): -1}
    ident(d, _g(n, "production.uses.b1g"), parts, f"{s}: B1g")
    ident(d, _g(n, "production.uses.b1n"), {_g(n, "production.uses.b1g"): 1, _g(n, "production.uses.p51c"): -1},
          f"{s}: B1n = B1g - CFC")


@pytest.mark.parametrize("s", [s for s in SOA if s not in ("s1_15", "s6_0")])
def test_capital_account(s):
    """B9 = B101 - net capital formation - valuables - non-produced assets (items published blank
    count as zero). Not for 1.15, whose net capital formation 'includes adjustment factor from flow
    of funds' (its note 2)."""
    n = f"oldbase_soa_{s}"
    d = ds(n)
    parts = {_g(n, "capital.liabilities.b101"): 1, _g(n, "capital.assets.p5n"): -1,
             _g(n, "capital.assets.p53"): -1, _g(n, "capital.assets.np"): -1}
    periods = sorted(set(d.filter(pl.col("series_id") == _g(n, "capital.assets.b9"))["period"]))
    assert periods == YEARS_2024, s
    bad = []
    for per in periods:
        vals = {r["series_id"]: r["value"] for r in d.filter(pl.col("period") == per).iter_rows(named=True)}
        diff = vals[_g(n, "capital.assets.b9")] - sum(c * vals.get(k, 0.0) for k, c in parts.items())
        if abs(diff) > 2.0:
            bad.append((per, round(diff, 1)))
    assert not bad, f"{s}: capital account does not close: {bad}"


# financial-account totals: 6.0 (rest of the world) prints them with code 'F'
FIN_TOTALS = {"s6_0": ("financial.assets.f", "financial.liabilities.f")}


@pytest.mark.parametrize("s", SOA)
def test_financial_account_matches_capital_account(s):
    """Net lending from the financial account (assets - liabilities) = B9 of the capital account, in every
    sequence (all close as published once 3.0's shifted English code column is corrected: verify-1/-2)."""
    n = f"oldbase_soa_{s}"
    d = ds(n)
    assets, liabs = FIN_TOTALS.get(s, ("financial.assets.net_acquisition_of_financial_assets",
                                       "financial.liabilities.net_incurrence_of_liabilities"))
    periods = sorted(set(d.filter(pl.col("series_id") == _g(n, "financial.liabilities.b9"))["period"]))
    assert periods == YEARS_2024, s
    ident(d, _g(n, "financial.liabilities.b9"), {_g(n, assets): 1, _g(n, liabs): -1}, f"{s}: financial B9", tol=3.0)
    ident(d, _g(n, "financial.liabilities.b9"), {_g(n, "capital.assets.b9"): 1}, f"{s}: B9 capital = financial",
          tol=3.0)


# SNA 2008 financial instruments (F1..F8) and B9, by English label
SNA_FIN = {
    "monetary gold and sdrs": "F1", "currency and deposits": "F2", "debt securities": "F3", "loans": "F4",
    "equity and investment fund shares": "F5", "insurance, pension and standardised guarantee scheme": "F6",
    "financial derivatives and employee stock options": "F7", "other accounts payable": "F8",
    "other accounts receivable": "F8", "net lending (+) / net borrowing (-)": "B9",
}


def test_financial_instrument_codes_match_labels():
    """Every financial-account row labelled with an SNA instrument carries that instrument's code (and the
    totals carry none, or 'F' in 6.0). Guards the 3.0 column-P shift (verify-1)."""
    bad = []
    for s in SOA:
        d = ds(f"oldbase_soa_{s}").filter(pl.col("item_code").str.starts_with("financial."))
        for code, label in d.select("item_code", "item_label").unique().iter_rows():
            lab, printed = label.rsplit(" [", 1)
            want = SNA_FIN.get(lab.replace("*", "").strip().lower())
            if want and (printed != f"{want}]" or code.split(".")[-1] != want.lower()):
                bad.append((s, code, label))
            if lab.lower().startswith(("net incurrence", "net acquisition")) and printed not in ("-]", "F]"):
                bad.append((s, code, label))
    assert not bad, bad


def test_code_columns_are_cross_checked():
    """The parser reads both SNA code columns: a disagreement outside the documented 3.0 shift fails."""
    from pipeline.ingest.mospi_nas_2026 import oldbase

    class Cell:
        def __init__(self, v):
            self.value = v

    ws = {"A5": Cell("F2"), "P5": Cell("F3"), "A6": Cell(None)}
    cfg = next(c for c in oldbase.CFGS if c.key == "nas2024/2.0")
    with pytest.raises(ValueError, match="disagree"):
        oldbase._row_code(ws, cfg, 5)
    ws["P5"] = Cell("F2")
    assert oldbase._row_code(ws, cfg, 5) == "F2"
    shifted = next(c for c in oldbase.CFGS if c.key == "nas2024/3.0")
    ws = {"A95": Cell("F3"), "P95": Cell("F4"), "A96": Cell("F4")}
    assert oldbase._row_code(ws, shifted, 95) == "F3"
    ws["A96"] = Cell("F3")  # the shift no longer holds: a re-issued file must fail, not be re-coded silently
    with pytest.raises(ValueError, match="shift"):
        oldbase._row_code(ws, shifted, 95)


@pytest.mark.parametrize("key", ["production.resources.p1", "production.uses.b1g", "production.uses.p51c"])
def test_sectors_add_up(key):
    frames = pl.concat([ds(f"oldbase_soa_{s}") for s in SOA], how="diagonal_relaxed")

    def g(s: str) -> str:
        return f"oldbase_soa_{s}.{key}.current"

    ident(frames, g("s2_0"), {g("s2_1"): 1, g("s2_2"): 1}, f"NFC = public + private ({key})", tol=5.0)
    ident(frames, g("s2_1"), {g("s2_1a"): 1, g("s2_1b"): 1}, f"public NFC = DE + NDE ({key})", tol=5.0)
    ident(frames, g("s3_0"), {g("s3_1"): 1, g("s3_2"): 1}, f"FC = public + private ({key})", tol=5.0)
    parts = {g("s2_0"): 1, g("s3_0"): 1, g("s4_0"): 1, g("s5_0"): 1}
    if key == "production.uses.b1g":  # the total economy's B1g is GDP: sector GVA + taxes less subsidies on products
        parts |= {"oldbase_soa_s1_15.production.resources.d21.current": 1,
                  "oldbase_soa_s1_15.production.resources.d31.current": -1}
    ident(frames, g("s1_15"), parts, f"total economy = NFC + FC + GG + households ({key})", tol=10.0)


def test_rest_of_world_account_matches_total_economy():
    d = pl.concat([ds("oldbase_soa_s6_0"), ds("oldbase_soa_s1_15")], how="diagonal_relaxed")
    ident(d, "oldbase_soa_s6_0.capital.assets.b9.current", {"oldbase_soa_s1_15.capital.assets.b9.current": -1},
          "RoW net lending = -(total-economy net lending)", tol=3.0)


@pytest.mark.parametrize("basis", ["current", "constant_2011_12"])
def test_nas2025_key_aggregates_identities(basis):
    n = "oldbase_nas2025_s1_1"
    d = ds(n)

    def s(c: str) -> str:
        return f"{n}.{c}.{basis}"

    ident(d, s("gdp"), {s("gva_basic"): 1, s("taxes_on_products"): 1, s("subsidies_on_products"): -1}, "GDP")
    # No GCF = GFCF + CIS + valuables check here: in the old series GCF also carried errors and omissions
    # (the new series moved them out, Sources and Methods 2026 s.23.4), so that identity holds only on the
    # new base (tests/units/test_mospi_nas_2026.py).
    ident(d, s("gdp_expenditure"), {s("pfce"): 1, s("gfce"): 1, s("gfcf"): 1, s("cis"): 1, s("valuables"): 1,
          s("exports"): 1, s("imports"): -1, s("discrepancies"): 1}, "GDP expenditure side (GCF components)")
    ident(d, s("gni"), {s("gdp"): 1, s("primary_income_row_net"): 1}, "GNI")


def test_nas2025_saving_statements_agree():
    d = pl.concat([ds("oldbase_nas2025_s1_1"), ds("oldbase_nas2025_s1_9"), ds("oldbase_nas2025_s1_14"),
                   ds("oldbase_nas2025_s5_3")], how="diagonal_relaxed")
    p = "oldbase_nas2025_s1_9.{}.current".format
    ident(d, "oldbase_nas2025_s1_1.gross_saving.current", {p("gross_savings"): 1}, "1.9 = 1.1 gross saving", tol=5.0)
    ident(d, p("gross_savings"), {p(x): 1 for x in ("non_financial_corporations", "financial_corporations",
          "general_government", "household_sector")}, "1.9 by sector", tol=5.0)
    ident(d, p("household_sector"), {"oldbase_nas2025_s5_3.household_saving_1_2_3_4.current": 1}, "1.9 = 5.3",
          tol=5.0)
    ident(d, p("household_sector"), {"oldbase_nas2025_s1_14.households_npish.gross_savings.current": 1},
          "1.9 = 1.14", tol=5.0)


def test_level_break_between_bases_is_about_minus_2_7_percent():
    """2022-23 GDP: new base 2,61,77,001 vs old base (NAS 2025) 2,68,90,473 = -2.65% (recon s0.5).
    The two series are different measurements; a time series across 2022-23 must flag this break."""
    new = checks.value(checks.load_dataset(U, f"{U}_s1_1"), "s1_1.gdp.current", "2022-23")
    old = checks.value(ds("oldbase_nas2025_s1_1"), "oldbase_nas2025_s1_1.gdp.current", "2022-23")
    assert 0.970 < new / old < 0.980


def test_old_base_is_labelled_and_separate():
    new_ids = set(checks.load_dataset(U, f"{U}_s1_1")["series_id"])
    for name in OLD:
        d = ds(name)
        assert set(d["base_year"]) == {"2011-12"}, name
        assert set(d["price_basis"]) <= {"current", "constant_2011_12"}, name
        assert set(d["source_id"]) == {"mospi_nas_old_base_2011_12"}, name
        assert set(d["vintage"]) == ({"2024-06-05"} if "soa" in name else {"2025-06-26"}), name
        assert not (set(d["series_id"]) & new_ids), name
        latest = "2022-23" if "soa" in name else "2023-24"
        stages = dict(d.select("period", "estimate_stage").unique().iter_rows())
        assert stages[latest] == "FRE", name
        # stages as the NAS API labels these values' revision rounds (oldbase.STAGES, issue mospi_nas_2026-9)
        want = {"2011-12": "Revised", "2012-13": "Revised", "2013-14": "Revised", "2021-22": "SRE"}
        want |= {"2022-23": "FRE"} if "soa" in name else {"2022-23": "Final", "2023-24": "FRE"}
        assert stages == {p: want.get(p, "TRE") for p in stages}, name
    assert sorted(set(ds("oldbase_soa_s5_0")["period"])) == YEARS_2024


def test_old_base_series_are_continuous():
    heads = [("oldbase_nas2025_s1_1", r"\.(gdp|gva_basic|pfce|gfce|gfcf)\."),
             ("oldbase_soa_s1_15", r"production\.(resources\.p1|uses\.b1g)")]
    for name, rx in heads:
        d = ds(name).filter(pl.col("series_id").str.contains(rx))
        assert d.height, name
        # 2020-21 (COVID) fell and 2021-22 rebounded: current-price GFCF +28.7% in 2021-22 is the largest move
        checks.assert_no_rows(checks.check_continuity(d, max_rel_change=0.30), f"{name}: break > 30%")
