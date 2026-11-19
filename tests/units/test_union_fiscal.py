"""Value tests for the union_fiscal unit (Union Finance Accounts 2023-24, Union Budgets 2024-25 to
2026-27, PPAC exchequer table, NSI collections).

Anchor values are read off the source documents (page/sheet noted next to each). Finance
Accounts print Rs thousand, so '8,74,16,21,62' is Rs 87,416.2162 crore.
"""

from __future__ import annotations

import polars as pl
import pytest

from pipeline.core import checks
from pipeline.ingest.union_fiscal import budget as B
from pipeline.ingest.union_fiscal import fa as FA

pytestmark = pytest.mark.quality

UNIT = "union_fiscal"
Y = "2023-24"


def _load(name: str) -> pl.DataFrame:
    return checks.load_dataset(UNIT, f"{UNIT}_{name}")


@pytest.fixture(scope="module")
def fa8():
    return _load("fa_receipts")


@pytest.fixture(scope="module")
def fa9():
    return _load("fa_expenditure")


@pytest.fixture(scope="module")
def rb():
    return _load("rb_receipts")


@pytest.fixture(scope="module")
def afs():
    return _load("afs")


@pytest.fixture(scope="module")
def ep():
    return _load("exp_profile")


@pytest.fixture(scope="module")
def nssf():
    return _load("nssf")


@pytest.fixture(scope="module")
def ppac():
    return _load("ppac_exchequer")


@pytest.fixture(scope="module")
def nsi():
    return _load("nsi_collections")


def v(df: pl.DataFrame, sid: str, period: str = Y) -> float:
    return checks.value(df, sid, period)


# ---------------------------------------------------------------------------------------------
# parser helpers (no data needed)
# ---------------------------------------------------------------------------------------------


def test_fa_amount_parsing():
    assert FA.parse_amount("8,74,16,21,62") == 874162162
    assert FA.parse_amount("—34,27,87,33,00") == -3427873300
    assert FA.parse_amount("–—3,95,81,66,00") == -395816600  # en dash + em dash
    assert FA.parse_amount("#—90,00,00,00") == -90000000
    assert FA.parse_amount("—") == 0.0
    assert FA.split_glued("15,41,63,23,6015,42,56,27,64") == (1541632360, 1542562764)
    assert FA.split_glued("—7,29,94,83,81—7,29,94,83,81") == (-729948381, -729948381)
    with pytest.raises(ValueError):
        FA.parse_amount("1,77,72,78,702,17,77,28")  # two glued amounts are never one number


def test_budget_nil_marks():
    assert B._num("...") == 0.0 and B._num("…") == 0.0 and B._num(None) is None
    assert B._num("878730.73 ") == 878730.73


# ---------------------------------------------------------------------------------------------
# Finance Accounts 2023-24, Statement 8 (receipts)
# ---------------------------------------------------------------------------------------------


def test_fa8_anchor_values(fa8):
    # printed page 97: MH 0005 CGST, 101 Tax 33,70,32,12,92; 901 share assigned to States
    # —34,27,87,33,00; TOTAL 47,78,34,76,26 (Rs thousand)
    assert v(fa8, "fa8.0005.00.101") == pytest.approx(337032.1292)
    assert v(fa8, "fa8.0005.00.901") == pytest.approx(-342787.33)
    assert v(fa8, "fa8.0005.total") == pytest.approx(477834.7626)
    # printed page 117: MH 0050 Dividends and Profits by payer
    assert v(fa8, "fa8.0050.00.101") == pytest.approx(63827.412)  # public undertakings 6,38,27,41,20
    assert v(fa8, "fa8.0050.00.106") == pytest.approx(87416.2162)  # RBI surplus 8,74,16,21,62
    assert v(fa8, "fa8.0050.00.107") == pytest.approx(4272.536)  # LIC 42,72,53,60
    assert v(fa8, "fa8.0050.00.108") == pytest.approx(13806.5683)  # nationalised banks 1,38,06,56,83
    assert v(fa8, "fa8.0050.total") == pytest.approx(170890.5055)  # 17,08,90,50,55
    assert v(fa8, "fa8.section.b_interest_receipts_dividends_and_profits") == pytest.approx(249564.6159)
    # printed page 103: MH 0026 Fringe Benefit Tax, 101 '*— 4,83,81' (minus sign detached from the
    # digits in the PDF) and TOTAL —4,45,88
    assert v(fa8, "fa8.0026.00.101") == pytest.approx(-4.8381)
    assert v(fa8, "fa8.0026.total") == pytest.approx(-4.4588)
    # printed page 101: MH 0008 IGST total —48,50,43,02
    assert v(fa8, "fa8.0008.total") == pytest.approx(-4850.4302)


def test_fa8_closures(fa8):
    """Every minor head adds up to its major-head total, and the section totals nest."""
    minors = fa8.filter((pl.col("series_id").str.count_matches(r"\.") == 3) & ~pl.col("series_id").str.ends_with(".total"))
    minors = minors.with_columns(pl.col("series_id").str.split(".").list.get(1).alias("mh"))
    sums = minors.group_by("mh").agg(pl.col("value").sum().alias("s"))
    tots = fa8.filter(pl.col("series_id").str.ends_with(".total") & (pl.col("series_id").str.count_matches(r"\.") == 2))
    tots = tots.with_columns(pl.col("series_id").str.split(".").list.get(1).alias("mh"))
    j = tots.join(sums, on="mh", how="full", coalesce=True)
    assert j.filter(pl.col("s").is_null() | pl.col("value").is_null()).height == 0
    assert (j["value"] - j["s"]).abs().max() < 0.0002
    sec = "fa8.section."
    ident = {
        "a_tax_revenue": ["a_goods_and_service_tax", "b_taxes_on_income_and_expenditure",
                          "c_taxes_on_property_capital_and_other_transactions",
                          "d_taxes_on_commodities_and_services_other_than_goods_and_services_tax"],
        "revenue_receipts": ["a_tax_revenue", "b_non_tax_revenue", "c_grants_in_aid_and_contributions"],
        "revenue_and_capital_receipts": ["revenue_receipts", "capital_receipts"],
        "b_non_tax_revenue": ["a_fiscal_services", "b_interest_receipts_dividends_and_profits",
                              "c_other_non_tax_revenue"],
    }
    for tot, parts in ident.items():
        checks.assert_no_rows(
            checks.check_identity(fa8, sec + tot, [sec + p for p in parts], abs_tol=0.0002), f"St 8 {tot}"
        )
    # the whole statement: all major-head totals add up to 'REVENUE AND CAPITAL RECEIPTS'
    assert tots["value"].sum() == pytest.approx(v(fa8, sec + "revenue_and_capital_receipts"), abs=0.001)


def test_fa8_gross_gst_and_direct_taxes_match_budget(fa8, afs, rb):
    """Gross (before the States' share, minor head 901) = AFS/Receipt Budget actuals 2023-24."""
    # AFS 0005 CGST 820622.09 (gap map T1); tr.pdf Total-Corporation Tax 911055.01
    for mh, doc_v in (("0005", 820622.09), ("0020", 911055.01), ("0021", None)):
        net = v(fa8, f"fa8.{mh}.total")
        share = v(fa8, f"fa8.{mh}.00.901")
        if doc_v is not None:
            assert net - share == pytest.approx(doc_v, abs=0.01), mh
        assert net - share == pytest.approx(v(afs, f"afs.cfi_rev_receipts.{mh}"), abs=0.01), mh
    # IGST residual and GST compensation cess (MH 0009) as in the Budget (AFS Statement I, 2025-26)
    assert v(afs, "afs.cfi_rev_receipts.0008") == pytest.approx(-4850.43)
    assert v(afs, "afs.cfi_rev_receipts.0009") == pytest.approx(141436.16)
    assert v(fa8, "fa8.0009.total") == pytest.approx(141436.161)
    # Receipt Budget 2025-26 'Dividend/Surplus of RBI, Nationalised Banks & FIs' 105495.32
    # = FA minor heads 106 (RBI) + 107 (LIC) + 108 (nationalised banks)
    rbi_etc = sum(v(fa8, f"fa8.0050.00.{m}") for m in ("106", "107", "108"))
    ntr = rb.filter(pl.col("series_id").str.contains("dividend_surplus_of_reserve_bank") & (pl.col("period") == Y))
    assert ntr.height == 1 and ntr["value"][0] == pytest.approx(105495.32)
    assert rbi_etc == pytest.approx(105495.32, abs=0.01)


def test_fa8_signs(fa8):
    shares = fa8.filter(pl.col("series_id").str.ends_with(".901"))
    assert shares.height >= 6 and (shares["value"] <= 0).all()  # devolution is deducted inside each head
    for mh in ("0005", "0009", "0020", "0021", "0037", "0038", "0050"):
        assert v(fa8, f"fa8.{mh}.total") > 0, mh
    assert v(fa8, "fa8.0008.total") < 0  # IGST: more apportioned out than retained (NAS net basis)


# ---------------------------------------------------------------------------------------------
# Finance Accounts 2023-24, Statement 9 (expenditure)
# ---------------------------------------------------------------------------------------------


def test_fa9_anchor_values(fa9):
    # printed page 141: 2011-01-101 Lok Sabha, Total column 2,44,69,68; MH 2011 TOTAL 10,82,48,05
    assert v(fa9, "fa9.2011.01.101") == pytest.approx(244.6968)
    assert v(fa9, "fa9.2011.total") == pytest.approx(1082.4805)
    # printed page 209: 3002-02 Repairs and maintenance of permanent way and works 1,97,73,87,17
    assert v(fa9, "fa9.3002.02.000") == pytest.approx(19773.8717)
    # printed page 228: MH 3475 TOTAL 54,99,01,04
    assert v(fa9, "fa9.3475.total") == pytest.approx(5499.0104)
    # printed page 234: grand total, revenue account 3,85,40,82,21,38
    assert v(fa9, "fa9.section.expenditure_heads_revenue_account") == pytest.approx(3854082.2138)
    # printed page 235: 4076 Capital outlay on Defence Services 15,42,56,27,64 (glued to the voted column)
    assert v(fa9, "fa9.4076.total") == pytest.approx(154256.2764)
    assert v(fa9, "fa9.section.expenditure_heads_capital_account") == pytest.approx(807180.3412)


def test_fa9_closures(fa9, afs):
    minors = fa9.filter(
        (pl.col("series_id").str.count_matches(r"\.") == 3) & ~pl.col("series_id").str.ends_with(".total")
    ).with_columns(
        pl.col("series_id").str.split(".").list.get(1).alias("mh")
    )
    tots = fa9.filter(pl.col("series_id").str.ends_with(".total") & (pl.col("series_id").str.count_matches(r"\.") == 2))
    tots = tots.with_columns(pl.col("series_id").str.split(".").list.get(1).alias("mh"))
    rev = tots.filter(pl.col("mh").str.slice(0, 1).is_in(["2", "3"]))
    cap = tots.filter(pl.col("mh").str.slice(0, 1).is_in(["4", "5"]))
    sums = minors.group_by("mh").agg(pl.col("value").sum().alias("s"))
    j = rev.join(sums, on="mh", how="left")
    assert j["s"].null_count() == 0 and (j["value"] - j["s"]).abs().max() < 0.0002
    assert rev["value"].sum() == pytest.approx(v(fa9, "fa9.section.expenditure_heads_revenue_account"), abs=0.001)
    assert cap["value"].sum() == pytest.approx(v(fa9, "fa9.section.expenditure_heads_capital_account"), abs=0.001)
    # AFS 2025-26 Statement I agrees with the audited accounts (revenue disbursements; capital
    # expenditure outside the revenue account)
    assert v(afs, "afs.cfi_rev_disbursements.total_revenue_disbursements") == pytest.approx(3854082.21, abs=0.01)
    assert v(afs, "afs.cfi_cap_disbursements.total_capital_expenditure_outside_the_revenue_account") == pytest.approx(
        807180.34, abs=0.01
    )


def test_fa9_key_heads(fa9):
    # MH 2049 Interest Payments and MH 2071 Pensions (Union, cash, 2023-24): orders of magnitude
    assert 1.0e6 < v(fa9, "fa9.2049.total") < 1.2e6
    assert 2.0e5 < v(fa9, "fa9.2071.total") < 2.8e5
    # grants-in-aid to States (MH 3601) are below the revenue total and positive
    assert 0 < v(fa9, "fa9.3601.total") < v(fa9, "fa9.section.grants_in_aid_and_contributions")


# ---------------------------------------------------------------------------------------------
# Receipt Budget tax / non-tax actuals, three vintages
# ---------------------------------------------------------------------------------------------


def test_rb_anchor_values(rb):
    # Receipt Budget 2025-26 tr.pdf p1-3, 'Actual 2023-2024'
    assert v(rb, "rb.tr.total.total_corporation_tax") == pytest.approx(911055.01)
    assert v(rb, "rb.tr.0034.security_transaction_tax") == pytest.approx(33777.78)
    assert v(rb, "rb.tr.total.total_goods_and_services_tax_gst") == pytest.approx(957207.82)
    assert v(rb, "rb.tr.0710.less_states_share") == pytest.approx(-1129493.71)
    assert v(rb, "rb.tr.total.grand_total") == pytest.approx(2327250.55)
    # Receipt Budget 2026-27 tr.xlsx 'Actuals 2024-2025': Corporation Tax 986766.59
    assert v(rb, "rb.tr.total.total_corporation_tax", "2024-25") == pytest.approx(986766.59)
    # Receipt Budget 2024-25 tr.xlsx 'Actuals 2022-2023': Corporation Tax 825833.64
    assert v(rb, "rb.tr.total.total_corporation_tax", "2022-23") == pytest.approx(825833.64)
    # ntr.pdf 2023-24: dividends from PSEs 65381.65, Total-Dividends and Profits 170876.97
    assert v(rb, "rb.ntr.total.total_dividends_and_profits") == pytest.approx(170876.97)
    assert v(rb, "rb.ntr.total.grand_total") == pytest.approx(401785.34)
    assert v(rb, "rb.ntr.total.total_dividends_and_profits", "2024-25") == pytest.approx(308424.29)


@pytest.mark.parametrize("tab", ["tr", "ntr"])
@pytest.mark.parametrize("period", ["2022-23", "2023-24", "2024-25"])
def test_rb_items_add_to_grand_total(rb, tab, period):
    d = rb.filter((pl.col("period") == period) & pl.col("series_id").str.starts_with(f"rb.{tab}."))
    items = d.filter(~pl.col("series_id").str.contains(r"\.total\."))
    assert items["value"].sum() == pytest.approx(v(rb, f"rb.{tab}.total.grand_total", period), abs=0.05)


def test_rb_gst_components_and_continuity(rb):
    for p in ("2022-23", "2023-24", "2024-25"):
        checks.assert_no_rows(
            checks.check_identity(
                rb.filter(pl.col("period") == p),
                "rb.tr.total.total_goods_and_services_tax_gst",
                [
                    "rb.tr.0005.central_goods_and_services_tax_cgst",
                    "rb.tr.0008.integrated_goods_and_services_tax_igst",
                    "rb.tr.0009.gst_compensation_cess",
                ],
                abs_tol=0.02,
            ),
            f"GST = CGST + IGST + cess, {p}",
        )
    big = rb.filter(
        pl.col("series_id").is_in(
            ["rb.tr.total.total_corporation_tax", "rb.tr.total.total_taxes_on_income", "rb.tr.total.total_customs",
             "rb.tr.total.total_union_excise_duties", "rb.tr.total.total_goods_and_services_tax_gst",
             "rb.tr.total.grand_total"]
        )
    )
    assert big.height == 18
    checks.assert_no_rows(checks.check_continuity(big.with_columns(pl.lit("x").alias("vintage")), max_rel_change=0.3),
                          "tax totals jump > 30% year on year")


# ---------------------------------------------------------------------------------------------
# AFS
# ---------------------------------------------------------------------------------------------


def test_afs_anchor_values_and_identities(afs):
    # allafs.xlsx (Budget 2025-26) Sheet1, Actuals 2023-2024
    assert v(afs, "afs.cfi_rev_receipts.0005") == pytest.approx(820622.09)
    assert v(afs, "afs.cfi_rev_receipts.0007") == pytest.approx(5497.16)
    # allafs.xlsx (Budget 2024-25) Sheet1, Actuals 2022-2023
    assert v(afs, "afs.cfi_rev_receipts.0020", "2022-23") == pytest.approx(825833.64)
    assert v(afs, "afs.cfi_rev_receipts.total_revenue_receipts", "2022-23") == pytest.approx(2713267.2)
    assert v(afs, "afs.cfi_rev_receipts.excess_of_disbursements_over_receipts_revenue_deficit", "2022-23") == \
        pytest.approx(1070431.31)
    for p in ("2022-23", "2023-24"):
        d = afs.filter(pl.col("period") == p)
        checks.assert_no_rows(
            checks.check_identity(
                d, "afs.cfi_rev_receipts.total",
                ["afs.cfi_rev_receipts.total_revenue_receipts",
                 "afs.cfi_rev_receipts.excess_of_disbursements_over_receipts_revenue_deficit"], abs_tol=0.02),
            f"revenue account balances, {p}")
        checks.assert_no_rows(
            checks.check_identity(d, "afs.cfi_rev_receipts.total", ["afs.cfi_rev_disbursements.total_revenue_disbursements"],
                                  abs_tol=0.02), f"revenue total = disbursements, {p}")
        checks.assert_no_rows(
            checks.check_identity(
                d, "afs.cfi_rev_receipts.a_goods_and_services_tax",
                ["afs.cfi_rev_receipts.0005", "afs.cfi_rev_receipts.0007", "afs.cfi_rev_receipts.0008",
                 "afs.cfi_rev_receipts.0009"], abs_tol=0.02),
            f"AFS GST block, {p}")


# ---------------------------------------------------------------------------------------------
# Expenditure Profile
# ---------------------------------------------------------------------------------------------


def test_ep_anchor_values(ep):
    # stat7.xlsx (Budget 2025-26), Actuals 2023-2024
    assert v(ep, "stat7.food.food_subsidy") == pytest.approx(211814.39)
    assert v(ep, "stat7.fertiliser") == pytest.approx(188291.62)
    assert v(ep, "stat7.fertiliser.urea_subsidy") == pytest.approx(123092.04)
    assert v(ep, "stat7.petroleum.lpg_subsidy") == pytest.approx(12240.0)
    assert v(ep, "stat7.interest_subsidies") == pytest.approx(19515.82)
    # stat7.xlsx (Budget 2026-27), Actuals 2024-2025 (registry verify note: Grand Total 422606.49)
    assert v(ep, "stat7.grand_total", "2024-25") == pytest.approx(422606.49)
    # stat18.xlsx (Budget 2025-26), Actuals 2023-2024
    assert v(ep, "stat18.some_important_items_of_transfer") == pytest.approx(160257.17)
    assert v(ep, "stat18.some_important_items_of_transfer.externally_aided_projects_loan") == pytest.approx(31308.41)
    # stat18.xlsx (Budget 2026-27), Grand Total 938628.46 (registry note)
    assert v(ep, "stat18.grand_total", "2024-25") == pytest.approx(938628.46)
    # stat1.xlsx (Budget 2025-26): Total Expenditure through Budget (1+5), total 4443447.23
    assert v(ep, "stat1.total_expenditure_through_budget_1_5.total") == pytest.approx(4443447.23)
    # stat20.xlsx (Budget 2025-26): Grand Total 9067.61 (grant 7455.62 + loan 1611.99)
    assert v(ep, "stat20.grand_total.total") == pytest.approx(9067.61)


@pytest.mark.parametrize("period", ["2022-23", "2023-24", "2024-25"])
def test_ep_identities(ep, period):
    d = ep.filter(pl.col("period") == period)
    # every level adds up to the Grand Total on its own (headings; Statement 21 departments; items),
    # so no aggregation mixes two levels (verify-1: Statement 21 ministries vs departments)
    for st in ("stat7", "stat18", "stat21"):
        gt = v(ep, f"{st}.grand_total", period)
        rest = d.filter(pl.col("series_id").str.starts_with(f"{st}.") & (pl.col("series_id") != f"{st}.grand_total"))
        for level in ("heading", "item") + (("department",) if st == "stat21" else ()):
            part = rest.filter(pl.col("dim_other").str.contains(f"level={level}(;|$)"))
            assert part.height > 0 and part["value"].sum() == pytest.approx(gt, abs=0.05), (st, level)
    for comp in ("revenue", "capital", "total"):
        checks.assert_no_rows(
            checks.check_identity(
                d, f"stat1.total_expenditure_through_budget_1_5.{comp}",
                [f"stat1.central_expenditure_2_3_4.{comp}", f"stat1.transfers_6_7_8.{comp}"], abs_tol=0.02),
            f"stat1 (1+5) {comp} {period}")
    checks.assert_no_rows(
        checks.check_identity(d, "stat20.grand_total.total", ["stat20.grand_total.grant", "stat20.grand_total.loan"],
                              abs_tol=0.02), f"stat20 grant + loan {period}")


# ---------------------------------------------------------------------------------------------
# NSSF, NSI, PPAC
# ---------------------------------------------------------------------------------------------


def test_nssf(nssf, nsi):
    # annex8.pdf (Budget 2025-26), Actual 2023-2024
    assert v(nssf, "nssf.net_collection") == pytest.approx(421678.36)
    # opening stocks ("as on 1st April 2023") are dated at the previous 31 March
    assert v(nssf, "nssf.savings_deposits.opening", "2023-03-31") == pytest.approx(1418963.20)
    assert v(nssf, "nssf.ppf.additions") == pytest.approx(111927.46)
    assert v(nssf, "nssf.total_deposits", "2024-03-31") == pytest.approx(3147690.85)
    # annex8.pdf (Budget 2026-27), Actual 2024-2025
    assert v(nssf, "nssf.net_collection", "2024-25") == pytest.approx(338985.20)
    for y0, end in ((2023, "2024-03-31"), (2024, "2025-03-31")):
        fy = f"{y0}-{str(y0 + 1)[2:]}"
        ins = ("savings_deposits", "savings_certificates", "ppf")
        adds = sum(v(nssf, f"nssf.{i}.additions", fy) for i in ins)
        opens = sum(v(nssf, f"nssf.{i}.opening", f"{y0}-03-31") for i in ins)
        assert adds == pytest.approx(v(nssf, "nssf.net_collection", fy), abs=0.02)
        assert opens + adds == pytest.approx(v(nssf, "nssf.total_deposits", end), abs=0.02)
        assert v(nssf, "nssf.total_investments", end) + v(nssf, "nssf.accumulated_income_expenditure_balance", end) + \
            v(nssf, "nssf.cash_balance", end) == pytest.approx(v(nssf, "nssf.total", end), abs=0.02)
    # one stock, one date: the 2024-25 openings (Budget 2026-27) sit at 2024-03-31, the same date as the
    # 2023-24 closing total (Budget 2025-26), and add up to it (verifier finding verify-5)
    opens_2024 = sum(v(nssf, f"nssf.{i}.opening", "2024-03-31") for i in ("savings_deposits", "savings_certificates", "ppf"))
    assert opens_2024 == pytest.approx(v(nssf, "nssf.total_deposits", "2024-03-31"), abs=0.02)
    assert not any(p.endswith("-04-01") for p in nssf["period"].to_list())
    # NSI's own table agrees with Annex 8 to the rupee-crore rounding (421678.35 vs 421678.36)
    assert v(nsi, "nsi.net_collections") == pytest.approx(v(nssf, "nssf.net_collection"), abs=0.02)
    assert v(nsi, "nsi.net_collections", "2024-25") == pytest.approx(v(nssf, "nssf.net_collection", "2024-25"), abs=1.0)


def test_nsi(nsi):
    # InternalPage.aspx?Id_Pk=152: '2022-23 1124908.99 819539.66 305369.33', '2023-24 1010801.36 - 421678.35'
    assert v(nsi, "nsi.gross_deposits", "2022-23") == pytest.approx(1124908.99)
    assert v(nsi, "nsi.withdrawals", "2022-23") == pytest.approx(819539.66)
    assert v(nsi, "nsi.net_collections") == pytest.approx(421678.35)
    assert v(nsi, "nsi.net_collections", "2025-26") == pytest.approx(431205.74)
    both = nsi.pivot(on="item_code", index="period", values="value").drop_nulls()
    assert both.height >= 20
    assert ((both["gross_deposits"] - both["withdrawals"] - both["net_collections"]).abs() < 0.02).all()
    periods = sorted(nsi["period"].unique().to_list())
    assert periods[0] == "2002-03" and periods[-1] == "2025-26" and len(periods) == 24  # no gaps


def test_ppac(ppac):
    # 'Anx 1' (table posted 17.07.2026), 2023-24 column
    assert v(ppac, "ppac.centre.a.excise_duty") == pytest.approx(273683.88)
    assert v(ppac, "ppac.centre.a.customs_duty") == pytest.approx(13133.73)
    assert v(ppac, "ppac.centre.a.cess_on_crude_oil") == pytest.approx(19580.39)
    assert v(ppac, "ppac.states.a.sales_tax_vat_on_pol_products") == pytest.approx(292716.41)
    assert v(ppac, "ppac.centre.a.excise_duty", "2024-25") == pytest.approx(276562.85)
    for p in ppac["period"].unique().to_list():
        d = ppac.filter(pl.col("period") == p)
        for blk in ("centre", "states"):
            for part in ("a", "b"):
                items = d.filter(pl.col("series_id").str.starts_with(f"ppac.{blk}.{part}.")
                                 & (pl.col("series_id") != f"ppac.{blk}.{part}.subtotal"))
                gap = v(ppac, f"ppac.{blk}.{part}.subtotal", p) - items["value"].sum()
                # Published inconsistency (issues file union_fiscal-9): 2025-26 (P) State sub-total
                # (A) 342180.50 exceeds the sum of its rows (341513.26) by 667.24.
                expected = 667.24 if (p, blk, part) == ("2025-26", "states", "a") else 0.0
                assert gap == pytest.approx(expected, abs=0.1), (p, blk, part)
            assert v(ppac, f"ppac.{blk}.a.subtotal", p) + v(ppac, f"ppac.{blk}.b.subtotal", p) == pytest.approx(
                v(ppac, f"ppac.{blk}.total.total", p), abs=0.1)
        assert v(ppac, "ppac.centre.total.total", p) + v(ppac, "ppac.states.total.total", p) == pytest.approx(
            v(ppac, "ppac.all.total.total_contribution", p), abs=0.1)
    stages = dict(ppac.select("period", "estimate_stage").unique().iter_rows())
    assert stages["2025-26"] == "Provisional" and stages["2023-24"] == "n.a."


# ---------------------------------------------------------------------------------------------
# generic properties of every dataset of the unit
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["fa_receipts", "fa_expenditure", "rb_receipts", "afs", "exp_profile", "nssf", "ppac_exchequer",
             "nsi_collections"]
)
def test_units_and_basis(name):
    d = _load(name)
    assert set(d["unit"]) == {"INR_crore"}
    assert set(d["price_basis"]) == {"current"}
    assert set(d["geography"]) == {"IN"}
    # Rs crore magnitudes: nothing above Rs 2 crore crore (the Consolidated Fund totals are ~1.6e7)
    checks.assert_no_rows(checks.check_range(d, lo=-5e6, hi=2e7), f"{name} range")


def test_vintages_and_stages(fa8, fa9, rb, afs, ep):
    assert set(fa8["vintage"]) == set(fa9["vintage"]) == {"2024-12-10"}
    assert set(fa8["estimate_stage"]) == {"Audited"}
    vint = dict(rb.select("period", "vintage").unique().iter_rows())
    assert vint == {"2022-23": "2024-07-23", "2023-24": "2025-02-01", "2024-25": "2026-02-01"}
    assert dict(afs.select("period", "vintage").unique().iter_rows()) == {"2022-23": "2024-07-23", "2023-24": "2025-02-01"}
    assert set(ep["estimate_stage"]) == {"Actuals"}


# ---------------------------------------------------------------------------------------------
# series identity (verifier findings, 2026-09-29)
# ---------------------------------------------------------------------------------------------


def test_stat21_levels(ep):
    """Statement 21: ministry headings, numbered department headings under them, items, and the one
    '4.01' sub-item (part of item 4, 'Archaeological Survey of India')."""
    s21 = ep.filter(pl.col("series_id").str.starts_with("stat21."))
    assert not s21.filter(pl.col("series_id").str.contains(r"\.nx")).height
    # stat21.xlsx (Budget 2025-26) rows 170-171: 'Ministry of Home Affairs' 10.51 (2022-23 in Budget
    # 2024-25), department '28. Ministry of Home Affairs'; Actuals 2023-24 both 7.11
    assert v(ep, "stat21.ministry_of_home_affairs") == pytest.approx(7.11)
    assert v(ep, "stat21.dept.ministry_of_home_affairs") == pytest.approx(7.11)
    assert v(ep, "stat21.dept.ministry_of_home_affairs", "2022-23") == pytest.approx(3.94)
    assert v(ep, "stat21.ministry_of_home_affairs", "2022-23") == pytest.approx(10.51)
    sub = s21.filter(pl.col("dim_other").str.contains("level=subitem"))
    assert set(sub["series_id"]) == {
        "stat21.ministry_of_culture.contribution_for_hoisting_unesco_world_heritage_event_and_india_international_centre"
    }
    assert set(sub["period"]) == {"2022-23", "2023-24", "2024-25"}  # printed '3.01' in 2022-23, '4.01' later
    # Budget 2026-27 stat21.xlsx: 4.01 = 5.62 in Actuals 2024-25 (the gap verify-1 saw: 5,552.86 - 2 x 2,773.62)
    assert v(ep, sub["series_id"][0], "2024-25") == pytest.approx(5.62)


def test_stat18_groups_one_series_across_vintages(ep):
    """Statement 18 heads III and IV read 'Transfer to' (Budgets 2024-25, 2026-27) and 'Transfers to'
    (Budget 2025-26); they are one series each."""
    for sid in ("stat18.transfers_to_states_other_than_i_ii", "stat18.transfers_to_delhi_puducherry_and_jammu_kashmir",
                "stat18.transfers_to_states_other_than_i_ii.capital_transfers",
                "stat18.transfers_to_states_other_than_i_ii.under_centrally_sponsored_schemes_revenue"):
        assert set(ep.filter(pl.col("series_id") == sid)["period"]) == {"2022-23", "2023-24", "2024-25"}, sid
    assert not ep.filter(pl.col("series_id").str.starts_with("stat18.transfer_to")).height
    # stat18.xlsx (Budget 2024-25) Actuals 2022-23, head III
    assert v(ep, "stat18.transfers_to_states_other_than_i_ii", "2022-23") == pytest.approx(566884.39)


def test_rb_series_one_per_line_across_vintages(rb):
    """Non-tax section totals print 'Total-X' (xlsx) or 'Net-X' (Budget 2025-26 PDF) for the same line;
    PDF-glued words ('OtherRural') do not split series."""
    periods = {sid: set(g["period"]) for (sid,), g in rb.group_by("series_id")}
    three = {"2022-23", "2023-24", "2024-25"}
    for sec in ("transport", "energy", "social_services", "agriculture_and_allied_activities", "general_services",
                "economic_services", "dividends_and_profits", "customs", "corporation_tax", "taxes_on_income",
                "goods_and_services_tax_gst", "union_excise_duties"):
        tab = "tr" if sec in ("customs", "corporation_tax", "taxes_on_income", "goods_and_services_tax_gst",
                              "union_excise_duties") else "ntr"
        assert periods.get(f"rb.{tab}.total.total_{sec}") == three, sec
    # ntr.pdf (Budget 2025-26) 'Net-Transport' Actual 2023-2024; ntr.xlsx 'Total-Transport' in the others
    assert v(rb, "rb.ntr.total.total_transport") == pytest.approx(28797.29)
    for sid in ("rb.ntr.0515.other_rural_development_programme", "rb.tr.0038.oil_and_oil_seeds",
                "rb.tr.0038.special_additional_excise_duties"):
        assert periods.get(sid) == three, sid
    assert not rb.filter(pl.col("item_label").str.contains(r"[a-z][A-Z]")).height
    # where one file prints both 'Net-X' and 'Total-X' they stay two published lines
    assert "rb.ntr.total.net_general_services" in periods and "rb.ntr.total.net_economic_services" in periods


def test_fa8_nil_901_mh0032(fa8):
    # printed page 105: MH 0032 Taxes on Wealth, 901 'Share of Net Proceeds Assigned to States' printed '–—' (nil)
    assert v(fa8, "fa8.0032.00.901") == 0.0
    assert FA.parse_amount("–—") == 0.0 and FA.parse_amount("—–") == 0.0


# ---------------------------------------------------------------------------------------------
# follow-up pass (2026-09-29): Statement 6 (GCCA), FA Appendix to St 9 (IGAS-2), FA St 14, PIB GST
# ---------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcca():
    return _load("gcca")


@pytest.fixture(scope="module")
def gia():
    return _load("fa_gia")


@pytest.fixture(scope="module")
def pf():
    return _load("fa_provident_funds")


@pytest.fixture(scope="module")
def gst():
    return _load("pib_gst")


def test_gcca_anchor_values(gcca):
    # Grand Total, Actuals column: b2425_stat6.xlsx row 634 (2022-23), b2526_stat6.xlsx row 730
    # (2023-24), b2627_stat6.xlsx row 611 (2024-25)
    assert v(gcca, "stat6.grand_total", "2022-23") == pytest.approx(306263.98)
    assert v(gcca, "stat6.grand_total") == pytest.approx(303915.55)
    assert v(gcca, "stat6.grand_total", "2024-25") == pytest.approx(272655.92)
    # Budget 2025-26 St 6 rows 299-303: Demand No. 42 'Transfers to States' 6,460.38 = ACA for EAP
    # (grants) 5,478.83 + Special Assistance 981.55
    assert v(gcca, "stat6.demand.ministry_of_finance.transfers_to_states") == pytest.approx(6460.38)
    assert v(gcca, "stat6.item.ministry_of_finance.special_assistance") == pytest.approx(981.55)
    # Jal Jeevan Mission (b2526 rows 467-468, label wrapped over two rows): 64,700.75
    jjm = gcca.filter(pl.col("series_id").str.contains("jal_jeevan_mission") & (pl.col("period") == Y))
    assert jjm["value"].to_list() == [pytest.approx(64700.75)]


@pytest.mark.parametrize("period", ["2022-23", "2023-24", "2024-25"])
def test_gcca_each_level_adds_to_grand_total(gcca, period):
    d = gcca.filter(pl.col("period") == period)
    gt = v(d, "stat6.grand_total", period)
    for level in ("ministry", "demand", "item"):
        s = d.filter(pl.col("dim_other") == f"level={level}")["value"].sum()
        assert s == pytest.approx(gt, abs=0.05), (period, level)


def test_gcca_pdf_conversion_glitches(gcca):
    """Budget 2025-26 stat6.xlsx is a PDF conversion: row 727 holds '10. Nehru Yuva Kendra Sangathan'
    and '11. Rajiv Gandhi National Institute of Youth' in one cell with item 10's values; item 11's
    values are on row 728 ('Development'). Row 714 prints the head of item 8's label above its number.
    Wrapped ministry names are joined ('Ministry of Electronics and Information' + 'Technology')."""
    ids = set(gcca.filter(pl.col("period") == Y)["series_id"])
    assert v(gcca, "stat6.item.ministry_of_youth_affairs_and_sports.nehru_yuva_kendra_sangathan") == 0.93
    assert v(gcca, "stat6.item.ministry_of_youth_affairs_and_sports."
                   "rajiv_gandhi_national_institute_of_youth_development") == 1.5
    assert "stat6.ministry.ministry_of_electronics_and_information_technology" in ids
    saksham = gcca.filter(pl.col("series_id").str.contains("saksham_anganwadi") & (pl.col("period") == Y))
    assert saksham["value"].to_list() == [pytest.approx(586.66)]
    # ministry series are one series across the three vintages, except ministries with no GCCA line in
    # a year (Coal, Cooperation, Corporate Affairs, Planning)
    per = gcca.filter(pl.col("dim_other") == "level=ministry").group_by("series_id").agg(pl.col("period").n_unique())
    assert per.filter(pl.col("period") < 3).height <= 4


def test_gcca_parser_rejects_wrong_year():
    import glob
    from pathlib import Path

    f = sorted(glob.glob("data/raw/mof_union_budget_2026_27/*/union_fiscal/b2526_stat6.xlsx"))[-1]
    with pytest.raises(ValueError, match="expected 2022-23"):
        B.stat6_rows(Path(f), actual_year="2022-23")


def test_fa_gia(gia, gcca):
    # Appendix to Statement No. 9, PDF page 2 (printed 246), Rs lakh: State Government 39842803.58 /
    # 11943532.45; Autonomous Bodies capital 13989667.15; in kind (page 3) State Government 19492.96
    assert v(gia, "gia.cash.state_governments.total") == pytest.approx(398428.0358)
    assert v(gia, "gia.cash.state_governments.capital_assets") == pytest.approx(119435.3245)
    assert v(gia, "gia.cash.autonomous_bodies.capital_assets") == pytest.approx(139896.6715)
    assert v(gia, "gia.in_kind.state_governments.total") == pytest.approx(194.9296)
    cash = gia.filter(pl.col("series_id").str.starts_with("gia.cash."))
    cap = cash.filter(pl.col("series_id").str.ends_with(".capital_assets"))["value"].sum()
    # audited IGAS-2 capital-asset grants (all grantees) = Budget 2025-26 St 6 Actuals 2023-24 GCCA
    assert cap == pytest.approx(v(gcca, "stat6.grand_total"), abs=0.05)
    for cat in {s.split(".")[2] for s in cash["series_id"]}:
        assert v(gia, f"gia.cash.{cat}.capital_assets") <= v(gia, f"gia.cash.{cat}.total")


def test_fa14_provident_funds(pf, afs):
    # St 14 printed page 456: 8009-01-101 General Provident Fund 12,95,10,71,48 / 3,08,02,65,76 /
    # 2,95,72,58,05 / 13,07,40,79,19 (Rs thousand); p457 TOTAL-STATE PROVIDENT FUNDS
    assert v(pf, "fa14.8009.01.101.balance", "2023-03-31") == pytest.approx(129510.7148)
    assert v(pf, "fa14.8009.01.101.additions") == pytest.approx(30802.6576)
    assert v(pf, "fa14.8009.01.101.discharges") == pytest.approx(29572.5805)
    assert v(pf, "fa14.8009.01.101.balance", "2024-03-31") == pytest.approx(130740.7919)
    assert v(pf, "fa14.8009.total.balance", "2024-03-31") == pytest.approx(267407.832)
    # p458 8011-103 CGEGIS additions 4,30,30,86; p462 Total-Postal Life Insurance Schemes closing
    assert v(pf, "fa14.8011.00.103.additions") == pytest.approx(430.3086)
    assert v(pf, "fa14.8014.total.balance", "2024-03-31") == pytest.approx(80736.9866)
    # every line: opening + additions - discharges = closing
    for sid in {s.rsplit(".", 1)[0] for s in pf["series_id"]}:
        o = v(pf, f"{sid}.balance", "2023-03-31")
        c = v(pf, f"{sid}.balance", "2024-03-31")
        assert o + v(pf, f"{sid}.additions") - v(pf, f"{sid}.discharges") == pytest.approx(c, abs=1e-3), sid
    # sub-major totals of 8009 add up to the major-head total
    for m in ("additions", "discharges"):
        parts = pf.filter(pl.col("series_id").str.contains(r"^fa14\.8009\.\d\d\.total\." + m + "$"))["value"].sum()
        assert parts == pytest.approx(v(pf, f"fa14.8009.total.{m}"), abs=1e-3)
    # cross-document: AFS (Budget 2025-26) Statement III '(i) State Provident Fund', Actuals 2023-24
    assert v(pf, "fa14.8009.total.additions") == pytest.approx(
        v(afs, "afs.pa_receipts.i_state_provident_fund"), abs=0.01
    )
    assert v(pf, "fa14.8009.total.discharges") == pytest.approx(
        v(afs, "afs.pa_disbursements.i_state_provident_fund"), abs=0.01
    )


def test_pib_gst(gst):
    # PIB release 1921186 (1 May 2023): April 2023 gross 1,87,035 = CGST 38,440 + SGST 47,412 + IGST
    # 89,158 (imports 34,972) + cess 12,025 (imports 901); settled 45,864 / 37,959; post 84,304 / 85,371
    assert v(gst, "pib.gst.gross_gst", "2023-04") == 187035
    assert v(gst, "pib.gst.igst_on_imports", "2023-04") == 34972
    assert v(gst, "pib.gst.cgst_post_settlement", "2023-04") == 84304
    # PIB release 1929031 (1 Jun 2023): May 2023 gross 1,57,090
    assert v(gst, "pib.gst.gross_gst", "2023-05") == 157090
    for p in ("2023-04", "2023-05"):
        parts = sum(v(gst, f"pib.gst.{k}", p) for k in ("cgst", "sgst", "igst", "cess"))
        assert parts == pytest.approx(v(gst, "pib.gst.gross_gst", p), abs=2)
    st = gst.filter(pl.col("series_id").str.starts_with("pib.gst_domestic_by_state."))
    # Table 1 (release 1921186): Maharashtra Apr-22 27,495, Apr-23 33,196
    assert v(st, "pib.gst_domestic_by_state.in-mh", "2023-04") == 33196
    assert v(st, "pib.gst_domestic_by_state.in-mh", "2022-04") == 27495
    for p in ("2022-04", "2023-04", "2022-05", "2023-05"):
        d = st.filter(pl.col("period") == p)
        tot = v(d, "pib.gst_domestic_by_state.grand_total", p)
        rest = d.filter(pl.col("series_id") != "pib.gst_domestic_by_state.grand_total")["value"].sum()
        assert rest == pytest.approx(tot, abs=25), p
    assert d.filter(pl.col("geography") != "IN").height == 36  # 28 States + 8 UTs
    assert set(gst["vintage"]) == {"2023-05-01", "2023-06-01"}
    assert set(gst["estimate_stage"]) == {"Provisional"}
