"""Value tests for the rbi_financial_accounts unit.

Anchor values are read off the source documents themselves (sheet/cell or page/line quoted in
each comment): the FSF 2023-24 workbook (RBI, 21 Jan 2026), RBI Bulletin Sept 2026 tables
52(a)/52(b), the Handbook 2025-26 HTML table views, and the DEA Quarterly Reports / Status Paper.

Where a publisher's own table does not add up, the test pins the exact exceptions (and the issue
file docs/phase1/issues/rbi_financial_accounts.md explains them) instead of loosening tolerances.
"""

from __future__ import annotations

import polars as pl
import pytest

from pipeline.core import checks
from pipeline.ingest.rbi_financial_accounts import common as C

pytestmark = pytest.mark.quality
U = C.UNIT


def _ds(name: str) -> pl.DataFrame:
    return checks.load_dataset(U, f"{U}_{name}")


@pytest.fixture(scope="module")
def bs():
    return _ds("fsf_balance_sheets")


@pytest.fixture(scope="module")
def fwtw():
    return _ds("fsf_fwtw")


@pytest.fixture(scope="module")
def s7():
    return _ds("fsf_instrument_sector")


@pytest.fixture(scope="module")
def s8():
    return _ds("fsf_financing")


@pytest.fixture(scope="module")
def hh52():
    return _ds("hh_finsav_52ab")


@pytest.fixture(scope="module")
def saving():
    return _ds("hbs_saving")


@pytest.fixture(scope="module")
def t107():
    return _ds("hbs_gsec_ownership")


@pytest.fixture(scope="module")
def t109():
    return _ds("hbs_small_savings")


@pytest.fixture(scope="module")
def t49():
    return _ds("hbs_scb_balance_sheet")


@pytest.fixture(scope="module")
def own():
    return _ds("dea_gsec_ownership")


@pytest.fixture(scope="module")
def debt():
    return _ds("dea_central_debt")


def v(df: pl.DataFrame, sid: str, period: str) -> float:
    return checks.value(df, sid, period)


# =============================================================================================
# FSF St 1-5 balance sheets
# =============================================================================================


def fsf(inst, side, measure, instr, cp="all"):
    return f"fsf.{inst}.{side}.{measure}.{instr}.{cp}.current"


def test_fsf_anchor_values(bs):
    # sheet 'St 1', row 10 'II.a Currency' (F21), liabilities: D10 (2011-12) and P10 (2023-24)
    assert v(bs, fsf("fc", "liabilities", "outstanding", "f21"), "2012-03-31") == pytest.approx(1055840.082, abs=0.01)
    assert v(bs, fsf("fc", "liabilities", "outstanding", "f21"), "2024-03-31") == pytest.approx(3478039.5, abs=0.01)
    # sheet 'St 1', row 21 'Households (including NPISHs)' under F21, D21 (2011-12)
    assert v(bs, fsf("fc", "liabilities", "outstanding", "f21", "hh"), "2012-03-31") == pytest.approx(
        973318.41, abs=0.01
    )
    # sheet 'St 1', row 12 'Central bank' under F21, AC12... D12 (2011-12) = 11.707
    assert v(bs, fsf("fc", "liabilities", "outstanding", "f21", "fc_rbi"), "2012-03-31") == pytest.approx(
        11.707, abs=1e-3
    )
    # sheet 'St 4' (households), loans (F4) liabilities to ODCs / OFCs, transactions 2022-23 and 2023-24:
    # 12,52,313 -> 18,77,458 and 3,43,354 -> 1,208 (the HDFC-merger reclassification; gap map K8 note)
    assert round(v(bs, fsf("hh", "liabilities", "transaction", "f4", "fc_odc"), "2022-23")) == 1252313
    assert round(v(bs, fsf("hh", "liabilities", "transaction", "f4", "fc_odc"), "2023-24")) == 1877458
    assert round(v(bs, fsf("hh", "liabilities", "transaction", "f4", "fc_ofc"), "2022-23")) == 343354
    assert round(v(bs, fsf("hh", "liabilities", "transaction", "f4", "fc_ofc"), "2023-24")) == 1208


def test_fsf_household_totals_2023_24(bs, fwtw):
    """St 4 gross financial assets / liabilities, 2023-24 transactions, equal the S 6.13.b 'Total'
    row for households (Uses 34,45,382.5 / Sources 18,75,522.2, printed in sheet 'S 6.13' Q31/P31)."""
    fa = v(bs, fsf("hh", "assets", "transaction", "total"), "2023-24")
    fl = v(bs, fsf("hh", "liabilities", "transaction", "total"), "2023-24")
    assert fa == pytest.approx(3445382.5, abs=0.1)
    assert fl == pytest.approx(1875522.2, abs=0.1)
    assert v(fwtw, "fsf6.hh.assets.transaction.all.current", "2023-24") == pytest.approx(fa, abs=0.1)
    assert v(fwtw, "fsf6.hh.liabilities.transaction.all.current", "2023-24") == pytest.approx(fl, abs=0.1)


# Known non-closures of the published counterparty splits (dataset rows: institution, side, measure,
# instrument, identity). Anything else that fails is a parsing error.
_MF = ("fc", "fc_ofc", "fc_ofc_mf", "fc_ofc_mf_mmf", "fc_ofc_mf_other")


def _cp_violations(bs: pl.DataFrame) -> pl.DataFrame:
    idx = ["institution", "side", "dim_other", "instrument", "period"]
    w = bs.filter(pl.col("counterparty") != "all").pivot(on="counterparty", index=idx, values="value")
    tot = bs.filter(pl.col("counterparty") == "all").select(*idx, pl.col("value").alias("all"))
    cps = ["fc_rbi", "fc_odc", "fc_ofc", "gg", "nfc_pub", "nfc_pvt", "other_resident", "hh"]
    w = w.join(tot, on=idx, how="left")
    out = []
    for name, expr in (
        ("residents", sum(pl.col(c) for c in cps) - pl.col("residents")),
        ("gg", pl.col("gg_cen") + pl.col("gg_sta") - pl.col("gg")),
        ("all", pl.col("residents") + pl.col("row") - pl.col("all")),
    ):
        out.append(
            w.select(*idx, expr.alias("diff")).filter(pl.col("diff").abs() > 1).with_columns(identity=pl.lit(name))
        )
    return pl.concat(out)


def test_fsf_counterparty_identities_stocks(bs):
    """Residents = sum of resident counterparties, GG = Centre + States, instrument total = residents +
    RoW: for every outstanding stock, except one published cell (GG/States deposits at end-March 2021)."""
    bad = _cp_violations(bs).filter(pl.col("dim_other") == "measure=outstanding")
    got = sorted(bad.select("institution", "instrument", "period", "identity").iter_rows())
    assert got == [("gg", "f22_f29", "2021-03-31", "all"), ("gg_sta", "f22_f29", "2021-03-31", "all")]


def test_fsf_counterparty_identities_flows_reference_years(bs):
    """For 2022-23 and 2023-24 flows the splits close except on the mutual-fund asset side (MMF
    deposits/equity, other-MF loans, propagated to OFC and FC) and household valuation changes."""
    bad = _cp_violations(bs).filter(pl.col("period").is_in(["2022-23", "2023-24"]))
    unexpected = bad.filter(
        ~(
            (
                pl.col("institution").is_in(_MF)
                & (pl.col("side") == "assets")
                & pl.col("instrument").is_in(["f22_f29", "f4", "f51"])
            )
            | ((pl.col("institution") == "hh") & (pl.col("dim_other") == "measure=valuation"))
        )
    )
    checks.assert_no_rows(unexpected, "unexpected counterparty non-closure in 2022-23/2023-24")
    assert bad.height == 68  # pinned: a change means the parser or the file changed


def test_fsf_instrument_hierarchy(bs):
    t = bs.filter(pl.col("counterparty") == "all").pivot(
        on="instrument", index=["institution", "side", "dim_other", "period"], values="value"
    )
    idents = {
        "f1": ["f11", "f12"],
        "f2": ["f21", "f22_f29"],
        "f5": ["f51", "f52"],
        "f52": ["f521", "f522"],
        "f6": ["f61", "f62", "f63", "f6_pf", "f64", "f66"],
        "f8": ["f81", "f89"],
        "total": ["f1", "f2", "f3", "f4", "f5", "f6", "f8", "other", "nec"],
    }
    bad = []
    for tot, parts in idents.items():
        x = t.with_columns((pl.col(tot) - sum(pl.col(p) for p in parts)).alias("diff")).filter(pl.col("diff").abs() > 1)
        bad.append(x.select("institution", "side", "dim_other", "period", "diff").with_columns(total=pl.lit(tot)))
    bad_df = pl.concat(bad)
    ref = bad_df.filter(pl.col("period").is_in(["2023-03-31", "2024-03-31", "2022-23", "2023-24"]))
    # Published inconsistencies in the reference years (see the issues file):
    # - RBI F6 liabilities exceed their printed components (35,535 / 38,100 stock; 2,159 / 2,566 flow);
    # - money-market MF F8 transactions: the F8 row is 1,000 / 1,100 above F81 + F89, and the gross total
    #   below the sum of instruments by the same amount (propagates to MF, OFC and FC);
    # - household valuation changes: the gross total differs from the sum of instruments.
    known = (
        ((pl.col("total") == "f6") & pl.col("institution").is_in(["fc", "fc_rbi"]) & (pl.col("side") == "liabilities"))
        | (
            pl.col("total").is_in(["f8", "total"])
            & pl.col("institution").is_in(["fc", "fc_ofc", "fc_ofc_mf", "fc_ofc_mf_mmf"])
            & (pl.col("side") == "liabilities")
            & (pl.col("dim_other") == "measure=transaction")
        )
        | (
            (pl.col("total") == "total")
            & (pl.col("institution") == "hh")
            & (pl.col("dim_other") == "measure=valuation")
        )
    )
    checks.assert_no_rows(ref.filter(~known), "unexpected instrument-hierarchy non-closure")
    assert ref.height == 26
    # the stock hierarchy holds at every other date (only RBI F6 is off, from end-March 2020 on at most)
    stocks = bad_df.filter(
        (pl.col("dim_other") == "measure=outstanding")
        & ~((pl.col("total") == "f6") & pl.col("institution").is_in(["fc", "fc_rbi"]))
    )
    checks.assert_no_rows(stocks, "stock instrument hierarchy")


@pytest.mark.parametrize(
    "parent, parts",
    [
        ("fc", ["fc_rbi", "fc_odc", "fc_ofc"]),
        ("fc_odc", ["fc_odc_scb", "fc_odc_coop", "fc_odc_nbfc_dt", "fc_odc_hfc_dt"]),
        (
            "fc_ofc",
            [
                "fc_ofc_aifi",
                "fc_ofc_sfc",
                "fc_ofc_sidc",
                "fc_ofc_nbfc_ndt",
                "fc_ofc_hfc_ndt",
                "fc_ofc_mf",
                "fc_ofc_icpf",
            ],
        ),
        ("fc_ofc_mf", ["fc_ofc_mf_other", "fc_ofc_mf_mmf"]),
        ("fc_ofc_icpf", ["fc_ofc_icpf_ins", "fc_ofc_icpf_pf"]),
        ("nfc", ["nfc_pub", "nfc_pvt"]),
        ("nfc_pub", ["nfc_pub_cpse", "nfc_pub_power", "nfc_pub_ports"]),
        ("gg", ["gg_cen", "gg_sta"]),
    ],
)
def test_fsf_subsectors_add_up(bs, parent, parts):
    k = ["side", "dim_other", "instrument", "counterparty", "period"]
    a = bs.filter(pl.col("institution") == parent).select(*k, pl.col("value").alias("t"))
    b = bs.filter(pl.col("institution").is_in(parts)).group_by(k).agg(pl.col("value").sum().alias("s"))
    j = a.join(b, on=k, how="left")
    assert j["s"].null_count() == 0
    checks.assert_no_rows(j.filter((pl.col("t") - pl.col("s")).abs() > 1), f"{parent} = sum of {parts}")


def test_fsf_statement_7_matches_balance_sheets(bs, s7):
    """S 7.x instrument x sector cells equal the St 1-5 sheets' instrument totals (outstanding and flows,
    2011-12..2023-24), except the OFC liabilities total flow, which S 7 prints Rs 100 crore x (year-2012)
    higher every year (the MMF F8 inconsistency)."""
    st = bs.filter(pl.col("counterparty") == "all").select(
        "institution", "side", "dim_other", "instrument", "period", pl.col("value").alias("st")
    )
    x = s7.filter(pl.col("institution") != "all").join(
        st, on=["institution", "side", "dim_other", "instrument", "period"], how="inner"
    )
    assert x.height >= 8000
    bad = x.filter((pl.col("value") - pl.col("st")).abs() > 1)
    assert sorted(set(bad.select("institution", "side", "dim_other", "instrument").iter_rows())) == [
        ("fc_ofc", "liabilities", "measure=transaction", "total")
    ]
    diffs = dict(bad.select("period", pl.col("value") - pl.col("st")).iter_rows())
    assert diffs["2023-24"] == pytest.approx(1100, abs=0.01) and diffs["2013-14"] == pytest.approx(100, abs=0.01)


def test_fsf_nonrow_totals_nonnegative(bs):
    tot = bs.filter((pl.col("instrument") == "total") & (pl.col("dim_other") == "measure=outstanding"))
    checks.assert_no_rows(checks.check_range(tot, lo=0), "gross financial assets/liabilities stocks >= 0")


def test_fsf_continuity_of_sector_totals(bs):
    """Year-on-year changes in the top-level sectors' gross financial asset/liability stocks stay
    under 50%; the only larger jumps are NFC stocks in 2016-17..2018-19 (published as is)."""
    top = ["fc", "nfc", "gg", "hh", "row", "fc_rbi", "fc_odc", "fc_ofc", "nfc_pub", "nfc_pvt", "gg_cen", "gg_sta"]
    tot = bs.filter(
        (pl.col("instrument") == "total")
        & (pl.col("dim_other") == "measure=outstanding")
        & pl.col("institution").is_in(top)
    )
    br = checks.check_continuity(tot, max_rel_change=0.5)
    assert set(br["series_id"].to_list()) <= {
        fsf("nfc", "assets", "outstanding", "total"),
        fsf("nfc_pvt", "assets", "outstanding", "total"),
        fsf("nfc", "liabilities", "outstanding", "total"),
        fsf("nfc_pvt", "liabilities", "outstanding", "total"),
    }, br


# =============================================================================================
# FSF S 6 (from-whom-to-whom), S 7, S 8
# =============================================================================================


def test_fwtw_anchor_values(fwtw):
    # sheet 'S 6.13', Statement 6.13.b (flows 2023-24): row VIII 'Households', col F (ODC Sources) = 1431737.5,
    # col G (ODC Uses) = 1849460.2; row X 'Total' cols T/U = 13892543.4 / 13843740.9
    assert v(fwtw, "fsf6.fc_odc.liabilities.transaction.hh.current", "2023-24") == pytest.approx(1431737.5, abs=0.1)
    assert v(fwtw, "fsf6.fc_odc.assets.transaction.hh.current", "2023-24") == pytest.approx(1849460.2, abs=0.1)
    assert v(fwtw, "fsf6.all.liabilities.transaction.all.current", "2023-24") == pytest.approx(13892543.4, abs=0.1)
    assert v(fwtw, "fsf6.all.assets.transaction.all.current", "2023-24") == pytest.approx(13843740.9, abs=0.1)
    # Statement 6.13.a (outstanding end-March 2024): row VIII, col F = 14375507.6; row X col T = 139830942.9
    assert v(fwtw, "fsf6.fc_odc.liabilities.outstanding.hh.current", "2024-03-31") == pytest.approx(14375507.6, abs=0.1)
    assert v(fwtw, "fsf6.all.liabilities.outstanding.all.current", "2024-03-31") == pytest.approx(139830942.9, abs=0.1)
    # sheet 'S 6.1' (outstanding 2011-12): row I 'Central bank', col F (ODC Sources) = 98758.2
    assert v(fwtw, "fsf6.fc_odc.liabilities.outstanding.fc_rbi.current", "2012-03-31") == pytest.approx(
        98758.2, abs=0.1
    )


def test_fwtw_rows_and_columns_add_up(fwtw):
    by = ["institution", "side", "dim_other", "period"]
    rows = fwtw.filter(pl.col("counterparty") != "all").group_by(by).agg(pl.col("value").sum().alias("s"))
    tot = fwtw.filter(pl.col("counterparty") == "all").select(*by, "value")
    j = tot.join(rows, on=by)
    checks.assert_no_rows(j.filter((pl.col("value") - pl.col("s")).abs() > 1), "S 6: Total row = sum of sector rows")
    by2 = ["counterparty", "side", "dim_other", "period"]
    cols = fwtw.filter(pl.col("institution") != "all").group_by(by2).agg(pl.col("value").sum().alias("s"))
    tot2 = fwtw.filter(pl.col("institution") == "all").select(*by2, "value")
    j2 = tot2.join(cols, on=by2)
    bad2 = j2.filter((pl.col("value") - pl.col("s")).abs() > 1)
    # one published non-closure: 'Central bank' row, Uses, end-March 2020 (Total column 18,052 below the sum)
    assert sorted(bad2.select("counterparty", "side", "dim_other", "period").iter_rows()) == [
        ("all", "assets", "measure=outstanding", "2020-03-31"),
        ("fc_rbi", "assets", "measure=outstanding", "2020-03-31"),
    ]


def test_fwtw_totals_match_statement_7(fwtw, s7):
    a = fwtw.filter(pl.col("counterparty") == "all").select(
        "institution", "side", "dim_other", "period", pl.col("value").alias("s6")
    )
    b = s7.filter(pl.col("instrument") == "total").select(
        "institution", "side", "dim_other", "period", pl.col("value").alias("s7")
    )
    j = a.join(b, on=["institution", "side", "dim_other", "period"])
    assert j.height == a.height
    bad = j.filter((pl.col("s6") - pl.col("s7")).abs() > 1)
    # the OFC liabilities flow total (and the all-sector total) differ every year (S 7 is +100 x (year-2012));
    # plus two stock cells: all-sector assets end-March 2020 (the S 6 column-sum break) and GG/all liabilities
    # end-March 2021 (the St 3 deposit counterparty break)
    flows = bad.filter(pl.col("dim_other") == "measure=transaction")
    assert set(flows.select("institution", "side").iter_rows()) == {("fc_ofc", "liabilities"), ("all", "liabilities")}
    assert sorted(
        bad.filter(pl.col("dim_other") == "measure=outstanding").select("institution", "side", "period").iter_rows()
    ) == [
        ("all", "assets", "2020-03-31"),
        ("all", "liabilities", "2021-03-31"),
        ("gg", "liabilities", "2021-03-31"),
    ]


def test_statement_7_anchor_values(s7):
    # sheet 'S 7.13', Statement 7.13.b (flows 2023-24): row 'Currency' col D (central bank Sources) = 129794.8;
    # 'Debt Securities' col J (GG Sources) = 1883882.9; 'Loans' col G (ODC Uses) = 2657918.1;
    # 'Life insurance and annuity entitlements' col Q (households Uses) = 589065
    assert v(s7, "fsf7.fc_rbi.liabilities.transaction.f21.current", "2023-24") == pytest.approx(129794.8, abs=0.1)
    assert v(s7, "fsf7.gg.liabilities.transaction.f3.current", "2023-24") == pytest.approx(1883882.9, abs=0.1)
    assert v(s7, "fsf7.fc_odc.assets.transaction.f4.current", "2023-24") == pytest.approx(2657918.1, abs=0.1)
    assert v(s7, "fsf7.hh.assets.transaction.f62.current", "2023-24") == pytest.approx(589065.0, abs=0.1)


def test_financing_anchor_values_and_identity(s8):
    # sheet 'S 8.1', Statement 8.1.a: 'Financial Resources' D5 (2011-12) = 13775812.3, P5 (2023-24) = 32969554.3;
    # 'Financial Deficit' P7 = 12941592.9
    assert v(s8, "fsf8.nfc_pvt.outstanding.financial_resources.current", "2012-03-31") == pytest.approx(
        13775812.3, abs=0.1
    )
    assert v(s8, "fsf8.nfc_pvt.outstanding.financial_resources.current", "2024-03-31") == pytest.approx(
        32969554.3, abs=0.1
    )
    assert v(s8, "fsf8.nfc_pvt.outstanding.financial_deficit.current", "2024-03-31") == pytest.approx(
        12941592.9, abs=0.1
    )
    for inst in ("nfc_pvt", "gg", "hh"):
        for m in ("outstanding", "transaction"):
            viol = checks.check_identity(
                s8,
                f"fsf8.{inst}.{m}.financial_deficit.current",
                {f"fsf8.{inst}.{m}.financial_resources.current": 1, f"fsf8.{inst}.{m}.financial_uses.current": -1},
            )
            checks.assert_no_rows(viol, f"S 8 {inst} {m}: deficit = resources - uses")


# =============================================================================================
# Bulletin 52(a) / 52(b)
# =============================================================================================


def test_52a_anchor_values(hh52):
    # 52(a) page 2 (2023-24), 'Annual' column
    assert v(hh52, "t52a.nfa.current.fy", "2023-24") == pytest.approx(1692414.2)
    assert v(hh52, "t52a.fa.current.fy", "2023-24") == pytest.approx(3601838.9)
    assert v(hh52, "t52a.fa_deposits.current.fy", "2023-24") == pytest.approx(1417816.0)
    assert v(hh52, "t52a.fa_life_insurance.current.fy", "2023-24") == pytest.approx(649086.9)
    assert v(hh52, "t52a.fa_pf_pension_incl_ppf.current.fy", "2023-24") == pytest.approx(723026.6)
    assert v(hh52, "t52a.fa_currency.current.fy", "2023-24") == pytest.approx(118248.0)
    assert v(hh52, "t52a.fl.current.fy", "2023-24") == pytest.approx(1909424.7)
    assert v(hh52, "t52a.fl_fc_banks_scb.current.fy", "2023-24") == pytest.approx(1856136.4)
    assert v(hh52, "t52a.nfa_pct_gdp.n_a.fy", "2023-24") == pytest.approx(5.8)
    # page 1, 2022-23 Q1 NFA = 338118.4; page 4, 2025-26 annual NFA = 2168779.7 (Preliminary)
    assert v(hh52, "t52a.nfa.current.fq", "Q1 2022-23") == pytest.approx(338118.4)
    assert v(hh52, "t52a.nfa.current.fy", "2025-26") == pytest.approx(2168779.7)
    stages = dict(
        hh52.filter(pl.col("table_id") == "Table 52(a)").select("period", "estimate_stage").unique().iter_rows()
    )
    assert stages["2025-26"] == "Preliminary" and stages["2023-24"] == "Revised"


def test_52b_anchor_values(hh52):
    # 52(b) page 2, column Mar-2024: FA 41470111.9, FL 12130649.0, per cent of GDP 142.6
    assert v(hh52, "t52b.fa.current", "2024-03-31") == pytest.approx(41470111.9)
    assert v(hh52, "t52b.fl.current", "2024-03-31") == pytest.approx(12130649.0)
    assert v(hh52, "t52b.fa_pct_gdp.n_a", "2024-03-31") == pytest.approx(142.6)
    assert v(hh52, "t52b.fa.current", "2022-06-30") == pytest.approx(32894206.1)
    assert v(hh52, "t52b.fa.current", "2026-03-31") == pytest.approx(49024188.6)


def test_52a_identities(hh52):
    for p in ("fy", "fq"):
        s = lambda code, p=p: f"t52a.{code}.current.{p}"  # noqa: E731
        idents = {
            "nfa": {"fa": 1, "fl": -1},
            "fa_deposits": {"fa_deposits_bank": 1, "fa_deposits_nonbank": 1},
            "fa_deposits_bank": {"fa_deposits_bank_scb": 1, "fa_deposits_bank_coop": 1},
            "fa_deposits_nonbank_ofi": {"fa_deposits_nonbank_ofi_nbfc": 1, "fa_deposits_nonbank_ofi_hfc": 1},
            "fl": {"fl_fc": 1, "fl_nfc_pvt": 1, "fl_gg": 1},
            "fl_fc": {"fl_fc_banks": 1, "fl_fc_ofi": 1},
            "fl_fc_ofi": {"fl_fc_ofi_nbfc": 1, "fl_fc_ofi_hfc": 1, "fl_fc_ofi_insurance": 1},
        }
        for tot, parts in idents.items():
            viol = checks.check_identity(hh52, s(tot), {s(k): c for k, c in parts.items()}, abs_tol=0.3)
            checks.assert_no_rows(viol, f"52(a) {tot} ({p})")
    # annual = sum of the four quarters (all Rs crore items)
    q = hh52.filter(
        (pl.col("table_id") == "Table 52(a)") & (pl.col("period_type") == "fq") & (pl.col("unit") == "INR_crore")
    )
    q = (
        q.with_columns(pl.col("period").str.slice(3).alias("fy"))
        .group_by("item_code", "fy")
        .agg(pl.col("value").sum().alias("q"))
    )
    a = hh52.filter(
        (pl.col("table_id") == "Table 52(a)") & (pl.col("period_type") == "fy") & (pl.col("unit") == "INR_crore")
    )
    j = a.select("item_code", pl.col("period").alias("fy"), "value").join(q, on=["item_code", "fy"])
    assert j.height == 27 * 4  # 30 items less the 3 per-cent-of-GDP rows, 4 years
    checks.assert_no_rows(j.filter((pl.col("value") - pl.col("q")).abs() > 0.5), "52(a) annual = Q1+Q2+Q3+Q4")


def test_52b_identities_and_continuity(hh52):
    s = lambda code: f"t52b.{code}.current"  # noqa: E731
    idents = {
        "fa": {
            k: 1
            for k in (
                "fa_deposits_bank",
                "fa_deposits_nonbank_ofi",
                "fa_life_insurance",
                "fa_currency",
                "fa_investments",
                "fa_ppf",
                "fa_pension_funds",
                "fa_small_savings_excl_ppf",
            )
        },
        "fa_deposits_bank": {"fa_deposits_bank_scb": 1, "fa_deposits_bank_coop": 1},
        "fa_deposits_nonbank_ofi": {"fa_deposits_nonbank_ofi_nbfc": 1, "fa_deposits_nonbank_ofi_hfc": 1},
        "fl": {"fl_banks": 1, "fl_ofi": 1},
        "fl_ofi": {"fl_ofi_nbfc": 1, "fl_ofi_hfc": 1, "fl_ofi_insurance": 1},
    }
    for tot, parts in idents.items():
        viol = checks.check_identity(hh52, s(tot), {s(k): c for k, c in parts.items()}, abs_tol=0.5)
        checks.assert_no_rows(viol, f"52(b) {tot}")
    stocks = hh52.filter(pl.col("series_id").is_in([s("fa"), s("fl"), s("fa_deposits_bank"), s("fl_banks")]))
    checks.assert_no_rows(checks.check_continuity(stocks, max_rel_change=0.12), "52(b) quarter-on-quarter > 12%")


# =============================================================================================
# Handbook T11, T12, T107, T109, T49
# =============================================================================================


def test_t11_anchor_values_and_identities(saving):
    # HBS T11 HTML, column '2023-24' (Base Year 2022-23)
    assert v(saving, "t11.gross_saving.base2022.current", "2023-24") == 9517450
    assert v(saving, "t11.gross_saving_hh.base2022.current", "2023-24") == 5963550
    assert v(saving, "t11.gross_financial_saving_hh.base2022.current", "2023-24") == 3575657
    assert v(saving, "t11.gross_saving_nfc_pub.base2022.current", "2023-24") == 465394
    assert v(saving, "t11.gross_saving_nfc_pvt.base2022.current", "2023-24") == 2415036
    # column 4 '2022-23' (Base Year 2011-12)
    assert v(saving, "t11.gross_saving.base2011.current", "2022-23") == 8244048
    for b in ("base2011", "base2022"):
        s = lambda c, b=b: f"t11.{c}.{b}.current"  # noqa: E731
        idents = {
            "gross_saving": ["gross_saving_nfc", "gross_saving_fc", "gross_saving_gg", "gross_saving_hh"],
            "gross_saving_nfc": ["gross_saving_nfc_pub", "gross_saving_nfc_pvt"],
            "gross_saving_nfc_pub": ["gross_saving_nfc_pub_dept", "gross_saving_nfc_pub_nondept"],
            "gross_saving_fc": ["gross_saving_fc_pub", "gross_saving_fc_pvt"],
            "gross_saving_fc_pub": ["gross_saving_fc_pub_dept", "gross_saving_fc_pub_nondept"],
        }
        for tot, parts in idents.items():
            checks.assert_no_rows(
                checks.check_identity(saving, s(tot), [s(p) for p in parts], abs_tol=2), f"T11 {tot} {b}"
            )
        viol = checks.check_identity(
            saving,
            s("gross_saving_hh"),
            {
                s("gross_financial_saving_hh"): 1,
                s("financial_liabilities_hh"): -1,
                s("saving_physical_assets_hh"): 1,
                s("saving_gold_silver_hh"): 1,
            },
            abs_tol=2,
        )
        checks.assert_no_rows(viol, f"T11 household saving {b}")


def test_t12_anchor_values_identities_continuity(saving):
    # HBS T12 HTML, row 2023-24: bank deposits 1442142, total assets 3430640; bank advances 1877458,
    # total liabilities 1878999; row 1983-84 currency 2776
    assert v(saving, "t12.assets.bank_deposits.current", "2023-24") == 1442142
    assert v(saving, "t12.assets.financial_assets.current", "2023-24") == 3430640
    assert v(saving, "t12.liabilities.bank_advances.current", "2023-24") == 1877458
    assert v(saving, "t12.liabilities.financial_liabilities.current", "2023-24") == 1878999
    assert v(saving, "t12.assets.currency.current", "1983-84") == 2776
    t12 = saving.filter(pl.col("table_id") == "HBS Table 12")
    # NAS 2025 (base 2011-12) starts in 2011-12; earlier spliced years carry no base_year
    assert t12.filter((pl.col("period") >= "2011-12") & pl.col("base_year").ne_missing("2011-12")).height == 0
    assert t12.filter((pl.col("period") < "2011-12") & pl.col("base_year").is_not_null()).height == 0
    a = [
        c
        for c in (
            "currency",
            "bank_deposits",
            "nonbank_deposits",
            "life_insurance_fund",
            "pf_pension_fund",
            "claims_on_government",
            "shares_debentures",
            "units_of_uti",
            "trade_debt_net",
        )
    ]
    # '-' cells are absent rows; sum what is printed (table note 7: rounding)
    parts = (
        t12.filter(pl.col("series_id").is_in([f"t12.assets.{c}.current" for c in a]))
        .group_by("period")
        .agg(pl.col("value").sum())
    )
    tot = t12.filter(pl.col("series_id") == "t12.assets.financial_assets.current").select(
        "period", pl.col("value").alias("t")
    )
    j = tot.join(parts, on="period")
    assert j.height == 41
    checks.assert_no_rows(j.filter((pl.col("t") - pl.col("value")).abs() > 3), "T12 assets = sum of cols 2-10")
    # the household financial saving flow swings with demonetisation (2016-17 currency) etc.; totals stay within
    # +-60% year on year except the listed years
    tots = t12.filter(pl.col("item_code").is_in(["financial_assets", "financial_liabilities"]))
    br = checks.check_continuity(tots, max_rel_change=0.6)
    assert set(zip(br["series_id"], br["to_period"], strict=True)) <= {
        ("t12.liabilities.financial_liabilities.current", p)
        for p in ("1991-92", "1992-93", "1994-95", "2001-02", "2004-05", "2005-06", "2006-07", "2017-18", "2022-23")
    }, br


def test_t107_ownership(t107):
    # HBS T107 HTML, panel 'Central Government Dated Securities': total (Rs crore) 2024 = 10740389,
    # Commercial Banks 2024 = 37.66, RBI 2023 = 14.26; SGS total 2024 = 5646219, PF 2024 = 22.35;
    # T-bills Commercial Banks 2024 = 58.53
    assert v(t107, "t107.gsec_central.outstanding.current", "2024-03-31") == 10740389
    assert v(t107, "t107.gsec_central.share.commercial_banks", "2024-03-31") == 37.66
    assert v(t107, "t107.gsec_central.share.rbi", "2023-03-31") == 14.26
    assert v(t107, "t107.sgs.outstanding.current", "2024-03-31") == 5646219
    assert v(t107, "t107.sgs.share.provident_funds", "2024-03-31") == 22.35
    assert v(t107, "t107.tbills.share.commercial_banks", "2024-03-31") == 58.53
    shares = t107.filter((pl.col("unit") == "percent") & (pl.col("counterparty") != "others_state_governments"))
    tot = shares.group_by("instrument", "period").agg(pl.col("value").sum())
    checks.assert_no_rows(tot.filter((pl.col("value") - 100).abs() > 0.1), "T107 holder shares sum to 100")
    checks.assert_no_rows(checks.check_range(shares, lo=0, hi=100), "T107 shares in [0, 100]")
    # 'of which: State Governments' never exceeds 'Others'
    o = t107.filter(pl.col("counterparty") == "others").select("instrument", "period", pl.col("value").alias("o"))
    s = t107.filter(pl.col("counterparty") == "others_state_governments").select("instrument", "period", "value")
    assert (s.join(o, on=["instrument", "period"]).select(pl.col("value") <= pl.col("o"))).to_series().all()


def test_t109_small_savings(t109):
    # HBS T109 HTML, row 2023-24: total receipts 232460, total outstanding 1865029, PPF outstanding 148213
    assert v(t109, "t109.total.receipts.current", "2023-24") == 232460
    assert v(t109, "t109.total.outstanding.current", "2024-03-31") == 1865029
    assert v(t109, "t109.ppf.outstanding.current", "2024-03-31") == 148213
    for kind in ("receipts", "outstanding"):
        viol = checks.check_identity(
            t109,
            f"t109.total.{kind}.current",
            [f"t109.{c}.{kind}.current" for c in ("deposits", "certificates", "ppf")],
            abs_tol=2,
        )
        # 1995-96 prints '-' for PPF receipts, so that year has no PPF row
        checks.assert_no_rows(viol.filter(pl.col("missing_parts").is_null()), f"T109 {kind} total")
        assert viol.filter(pl.col("missing_parts").is_not_null()).height <= 1


def test_t49_scb_balance_sheet(t49):
    # HBS T49 HTML, row '2023-24' (end-March 2024): deposits 21741578, loans 17142309, total 28080520
    assert v(t49, "t49.liabilities.deposits.current", "2024-03-31") == 21741578
    assert v(t49, "t49.assets.loans_advances.current", "2024-03-31") == 17142309
    assert v(t49, "t49.total.total.current", "2024-03-31") == 28080520
    liab = ["capital", "reserves_surplus", "deposits", "borrowings", "other_liabilities_provisions"]
    assets = [
        "cash_balances_rbi",
        "balances_banks_call_money",
        "investments",
        "loans_advances",
        "fixed_assets",
        "other_assets",
    ]
    for side, parts in (("liabilities", liab), ("assets", assets)):
        viol = checks.check_identity(
            t49, "t49.total.total.current", [f"t49.{side}.{p}.current" for p in parts], abs_tol=2
        )
        checks.assert_no_rows(viol, f"T49 total = sum of {side}")
    checks.assert_no_rows(
        checks.check_continuity(t49.filter(pl.col("item_code") == "total"), max_rel_change=0.3), "T49 total yoy > 30%"
    )


# =============================================================================================
# DEA
# =============================================================================================


def test_dea_ownership_anchor_values(own):
    # QR Jan-Mar 2024, page 13-14, Table 4.4 col 'Mar.24': Commercial Banks 37.7, RBI 12.3; Table 4.5 col 'Mar .24':
    # Commercial Banks 58.5
    assert v(own, "qr2024_t4_4.gsec_central.share.commercial_banks", "2024-03-31") == 37.7
    assert v(own, "qr2024_t4_4.gsec_central.share.rbi", "2024-03-31") == 12.3
    assert v(own, "qr2024_t4_5.tbills.share.commercial_banks", "2024-03-31") == 58.5
    # QR Jan-Mar 2023, page 14, Table 4.4: Commercial Banks Mar.21 = 37.8, RBI Mar.23 = 14.3
    assert v(own, "qr2023_t4_4.gsec_central.share.commercial_banks", "2021-03-31") == 37.8
    assert v(own, "qr2023_t4_4.gsec_central.share.rbi", "2023-03-31") == 14.3
    # Status Paper 2023-24, page 15, Table 2.10: Insurance Companies 2024 = 26.0; HB-5 page 99 '2014 (End-June)'
    # Commercial Banks 43.43, and the second '2015 (End-March)' row (read as March 2016) Commercial Banks 41.81
    assert v(own, "sp_t2_10.gsec_central.share.insurance", "2024-03-31") == 26.0
    assert v(own, "sp_hb5.gsec_central.share.commercial_banks", "2014-06-30") == 43.43
    assert v(own, "sp_hb5.gsec_central.share.commercial_banks", "2016-03-31") == 41.81
    assert v(own, "sp_hb5.gsec_central.share.commercial_banks", "2015-03-31") == 43.30


def test_dea_ownership_shares_sum_to_100(own):
    s = own.filter(pl.col("counterparty") != "total").group_by("series_id", "period").len()  # uniqueness guard
    assert s["len"].max() == 1
    tot = (
        own.filter(pl.col("counterparty") != "total")
        .with_columns(pl.col("series_id").str.extract(r"^([a-z0-9_]+)\.").alias("tab"))
        .group_by("tab", "instrument", "period")
        .agg(pl.col("value").sum())
    )
    checks.assert_no_rows(tot.filter((pl.col("value") - 100).abs() > 0.31), "DEA ownership shares sum to 100")


def test_hb5_matches_handbook_t107(own, t107):
    """Two publishers, same RBI data: Status Paper HB-5 end-March 2023/2024 = HBS T107 (2 decimals).
    This also pins the HB-5 column order, which the PDF header text does not show cleanly."""
    for d in ("2023-03-31", "2024-03-31"):
        a = own.filter((pl.col("table_id") == "Status Paper Table HB-5") & (pl.col("period") == d))
        b = t107.filter(
            (pl.col("instrument") == "gsec_central") & (pl.col("unit") == "percent") & (pl.col("period") == d)
        )
        j = a.select("counterparty", "value").join(
            b.select("counterparty", pl.col("value").alias("t107")), on="counterparty"
        )
        assert j.height == 12
        checks.assert_no_rows(j.filter((pl.col("value") - pl.col("t107")).abs() > 0.005), f"HB-5 vs T107 {d}")


def test_qr2023_swapped_rows_agree_with_other_dea_tables(own):
    """Issue rbi_financial_accounts-18: QR Jan-Mar 2023 T4.4 (p.18) prints '11. Pension Fund' and '12. Others'
    swapped; the unit reassigns them. After the swap every QR23 cell must agree (to one decimal) with the same
    holder in Status Paper T2.10 (end-March 2021-2023), QR Jan-Mar 2024 T4.4 (Mar.23) and HB-5 (two decimals,
    all nine quarters), and pension funds must have no rows before March 2022."""
    q = own.filter(pl.col("table_id") == "QR Jan-Mar 2023 Table 4.4")
    # printed: 'Pension Fund' Mar.21 7.3 .. Mar.23 5.6 (row holds Others); 'Others' Mar.22 3.5 .. Mar.23 4.0
    assert v(own, "qr2023_t4_4.gsec_central.share.others", "2021-03-31") == 7.3
    assert v(own, "qr2023_t4_4.gsec_central.share.others", "2023-03-31") == 5.6
    assert v(own, "qr2023_t4_4.gsec_central.share.pension_funds", "2022-03-31") == 3.5
    assert v(own, "qr2023_t4_4.gsec_central.share.pension_funds", "2023-03-31") == 4.0
    assert q.filter((pl.col("counterparty") == "pension_funds") & (pl.col("period") < "2022-03-31")).height == 0
    flagged = q.filter(pl.col("dim_other").is_not_null())
    assert sorted(set(zip(flagged["counterparty"], flagged["dim_other"], strict=True))) == [
        ("others", "printed_as=pension_funds"),
        ("pension_funds", "printed_as=others"),
    ]
    assert flagged.height == 14
    for tid, tol, n_min in (
        ("Status Paper Table 2.10", 0.051, 30),
        ("QR Jan-Mar 2024 Table 4.4", 0.051, 12),
        ("Status Paper Table HB-5", 0.051, 90),
    ):
        o = own.filter(pl.col("table_id") == tid).select("counterparty", "period", pl.col("value").alias("o"))
        j = q.select("counterparty", "period", "value").join(o, on=["counterparty", "period"])
        assert j.height >= n_min, (tid, j.height)
        assert {"pension_funds", "others"} <= set(j["counterparty"]), tid
        checks.assert_no_rows(j.filter((pl.col("value") - pl.col("o")).abs() > tol), f"QR23 T4.4 vs {tid}")


def test_dea_central_debt(debt):
    # Status Paper HB-1A page 90, row 2023-24: dated securities 10265571, total internal debt 14698177,
    # total public debt at current rates 15494255; row 2001-02 dated securities 536104
    assert v(debt, "sp_hb1a.dated_securities.current", "2024-03-31") == 10265571
    assert v(debt, "sp_hb1a.internal_debt.current", "2024-03-31") == 14698177
    assert v(debt, "sp_hb1a.public_debt_curr.current", "2024-03-31") == 15494255
    assert v(debt, "sp_hb1a.dated_securities.current", "2002-03-31") == 536104
    # HB-1B page 91, row 2023-24: NSSF 416511, total liabilities 16978100
    assert v(debt, "sp_hb1b.nssf.current", "2024-03-31") == 416511
    assert v(debt, "sp_hb1b.total_liabilities_hist.current", "2024-03-31") == 16978100
    a = lambda c: f"sp_hb1a.{c}.current"  # noqa: E731
    b = lambda c: f"sp_hb1b.{c}.current"  # noqa: E731
    idents = [
        (a("market_loans"), [a("dated_securities"), a("tbills_91d"), a("tbills_182d"), a("tbills_364d")]),
        (
            a("internal_debt"),
            [
                a(c)
                for c in (
                    "market_loans",
                    "tbills_14d",
                    "special_securities_tb_conversion",
                    "compensation_other_bonds",
                    "securities_to_ifis",
                    "securities_against_small_savings",
                    "others",
                )
            ],
        ),
        (a("public_debt_hist"), [a("internal_debt"), a("external_debt_hist")]),
        (a("public_debt_curr"), [a("internal_debt"), a("external_debt_curr")]),
        (
            b("other_accounts"),
            [b("special_securities_in_lieu_of_subsidies"), b("special_deposits_nongovt_pf"), b("other_items")],
        ),
        (b("reserve_funds"), [b("reserve_funds_interest"), b("reserve_funds_no_interest")]),
        (b("deposits"), [b("deposits_interest"), b("deposits_no_interest")]),
        (
            b("other_liabilities"),
            [b(c) for c in ("nssf", "state_provident_funds", "other_accounts", "reserve_funds", "deposits")],
        ),
        (b("total_liabilities_hist"), [b("other_liabilities"), b("public_debt_hist")]),
    ]
    for tot, parts in idents:
        viol = checks.check_identity(debt, tot, parts, abs_tol=2)
        if tot == a("market_loans"):
            # 2019-20 includes Rs 80,000 crore of cash management bills (footnote *); 2013-14 prints a total 194 below
            # its parts. Both as published.
            assert sorted(zip(viol["period"], viol["diff"], strict=True)) == [
                ("2014-03-31", -194.0),
                ("2020-03-31", 80000.0),
            ]
            continue
        if tot == a("internal_debt"):
            # consistent with the dated/T-bill components, i.e. the 2013-14 market-loans total is the misprint
            assert sorted(zip(viol["period"], viol["diff"], strict=True)) == [("2014-03-31", 195.0)]
            continue
        checks.assert_no_rows(viol, f"{tot}")
    # HB-1B column 15 repeats HB-1A column 16
    checks.assert_no_rows(
        checks.check_identity(debt, b("public_debt_hist"), [a("public_debt_hist")], abs_tol=0.5),
        "HB-1B col 15 = HB-1A col 16",
    )
    checks.assert_no_rows(
        checks.check_continuity(debt.filter(pl.col("series_id") == a("public_debt_curr")), max_rel_change=0.25),
        "public debt yoy > 25%",
    )


def test_cross_source_household_2023_24(hh52, bs, saving):
    """Household financial saving 2023-24 from three RBI/NSO vintages: 52(a) (Sept 2026, new base),
    HBS T11 (pre-NAS-2026 new base) and FSF St 4 (Jan 2026, old base). They are different vintages, so
    only their order of magnitude is asserted; the gaps are findings recorded in the issues file."""
    a = v(hh52, "t52a.fa.current.fy", "2023-24")
    b = v(saving, "t11.gross_financial_saving_hh.base2022.current", "2023-24")
    c = v(bs, fsf("hh", "assets", "transaction", "total"), "2023-24")
    for x in (b, c):
        assert abs(x / a - 1) < 0.06
