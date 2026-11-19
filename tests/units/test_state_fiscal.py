"""Value tests for the state_fiscal unit.

Anchor values were read off the source files themselves (sheet and cell given in each comment):
FC16 'State Finances - Key Fiscal Indicators.xlsx' (sheet 'State-wise'), 'Time series of transfer of
resources from Centre to States.xlsx', 'Sector wise Subsidies and Transfers.xlsx', 'State Finance
Accounts - Revenue and Expenditure.xlsx', 'FC16 ULB Data Dump Cityfinance.xlsx'; RBI State Finances
2025-26 Statements 13-17, 36, Appendix Tables 1-3, 9, 11 and Appendices I-IV (All States and UTs);
RBI Report on Municipal Finances (Nov 2024) Statements 1, 4, 8; RBI Finances of PRIs (Jan 2024)
Appendices I-II and Chapter II.
"""

import re

import polars as pl
import pytest

from pipeline.core import checks
from pipeline.core.fetch import pinned_raw
from pipeline.core.paths import Layout
from pipeline.ingest.state_fiscal import rbi as R
from pipeline.ingest.state_fiscal import sources as S
from pipeline.ingest.state_fiscal.common import _FORMULA

pytestmark = pytest.mark.quality
U = "state_fiscal"
ALL28 = "in.all_states_28"
ALLUT = "in.all_states_uts"


def load(name):
    return checks.load_dataset(U, f"{U}_{name}")


@pytest.fixture(scope="module")
def kfi():
    return load("fc16_kfi")


@pytest.fixture(scope="module")
def app():
    return load("rbi_sf_appendices")


@pytest.fixture(scope="module")
def at():
    return load("rbi_sf_app_tables")


@pytest.fixture(scope="module")
def st():
    return load("rbi_sf_statements")


def v(df, sid, period):
    return checks.value(df, sid, period)


def k(code):
    return f"kfi.{code}.{ALL28}"


# ---------------------------------------------------------------------------------------------
# FC16 Key Fiscal Indicators
# ---------------------------------------------------------------------------------------------

# Sheet 'State-wise', block All_States, column headed 2024 (= FY 2023-24), rows 3-113.
KFI_2023_24 = {
    "a_1-revenue_receipts": 3793278.1237,
    "a_1_1_2-state_goods_and_service_tax": 800112.0157,
    "a_1_1_1-taxes_on_sales_trade_etc": 397467.0631,
    "a_1_1_3-state_excise": 249133.4951,
    "a_1_1_4-taxes_on_vehicles": 106020.9925,
    "a_1_1_5-stamps_and_registration_fees": 220289.4881,
    "a_1_3-state_s_share_in_union_taxes_and_duties": 1129396.7189,
    "a_1_4-grants_in_aid_from_goi": 472465.8779,
    "a_1_4_a-compensation_for_loss_of_revenue_for_gst": 43788.4065,
    "b_1_a-interest_payments": 494910.9671,
    "b_1_b-pension_and_other_retirement_benefits": 494938.7245,
    "b_2-capital_expenditure": 727926.4529,
    "d_1-revenue_deficit_surplus_a_1_b_1": -103369.0106,
    "d_2-fiscal_deficit_surplus_a_3_b_5": -864160.3801,
    "c_10-gross_state_domestic_product_gsdp": 30122955.8977,
}


@pytest.mark.parametrize("code, crore", list(KFI_2023_24.items()))
def test_kfi_anchor_values_2023_24(kfi, code, crore):
    assert v(kfi, k(code), "2023-24") == pytest.approx(crore, abs=0.001)


def test_kfi_year_labels_are_fiscal_year_ends(kfi):
    """'2024' = FY 2023-24: SGST is 0 in the column headed 2017 and first positive under 2018
    (GST began July 2017); GST compensation loans appear under 2021 and 2022 (FY 2020-21, 2021-22)."""
    assert v(kfi, k("a_1_1_2-state_goods_and_service_tax"), "2016-17") == 0.0
    assert v(kfi, k("a_1_1_2-state_goods_and_service_tax"), "2017-18") == pytest.approx(269014.05)
    assert v(kfi, k("a_4_2_a-loans_for_gst_compensation"), "2020-21") == pytest.approx(101329)
    assert v(kfi, k("a_4_2_a-loans_for_gst_compensation"), "2021-22") == pytest.approx(147862)
    # stocks are dated end-March of the fiscal year
    assert v(kfi, k("c_1-public_debt"), "2024-03-31") == pytest.approx(6787363.1819, abs=0.01)
    assert v(kfi, k("c_1_2_a-loan_for_gst_compensation_cum"), "2024-03-31") == pytest.approx(249191)
    assert set(kfi["period"].filter(kfi["period_type"] == "fy")) == {f"{y}-{(y + 1) % 100:02d}" for y in range(2011, 2024)}


def test_kfi_not_compiled_rows_dropped(kfi):
    """Debt-flow rows are 0 for 2023-24 in the file (not compiled): they must not appear as zeros."""
    assert kfi.filter(pl.col("series_id") == k("a_4-public_debt_receipts"))["period"].max() == "2022-23"
    for code in ("a_5-total_capital_receipts_a_2_a_4", "a_11-total_receipts_a_8_a_9_a_10", "b_11-total_disbursements_by_the_state_b_8_b_9"):
        assert kfi.filter((pl.col("series_id") == k(code)) & (pl.col("period") == "2023-24")).height == 0
    # undivided AP exists to 2014-15 only; AP and Telangana from 2014-15
    ap_un = kfi.filter(pl.col("series_id") == "kfi.a_1-revenue_receipts.in-xap.undivided")
    assert ap_un["period"].max() == "2014-15"
    assert kfi.filter(pl.col("series_id") == "kfi.a_1-revenue_receipts.in-ts")["period"].min() == "2014-15"


def _prov_notes(kfi, sid, period):
    pv = checks.load_provenance(U).select("prov_id", "notes")
    r = kfi.filter((pl.col("series_id") == sid) & (pl.col("period") == period)).join(pv, on="prov_id")
    assert r.height == 1, (sid, period)
    return r["notes"][0] or ""


def test_kfi_zero_rule_by_family_head(kfi):
    """Verifier findings verify-2/3: a 0 is a nil when its family head is non-zero for the same block-year
    (sheet 'State-wise'); it is 'not compiled' (dropped) when the head is 0."""
    # A.4.2.a GST loans: nil in 2019-20 (A.4 compiled) and in 2023-24 (A.4.2.b SASCI compiled, 1,09,554)
    for p in ("2019-20", "2022-23", "2023-24"):
        assert v(kfi, k("a_4_2_a-loans_for_gst_compensation"), p) == 0.0
    # Kerala and Punjab 2023-24: A.4, A.4.2.a and A.4.2.b all 0 -> not compiled, no row
    for geo in ("in-kl", "in-pb"):
        assert kfi.filter((pl.col("series_id") == f"kfi.a_4_2_a-loans_for_gst_compensation.{geo}") & (pl.col("period") == "2023-24")).height == 0
    # WMA receipts: 0 for a State with no WMA in a compiled year is a nil (Gujarat 2022-23, A.4 > 0)
    assert v(kfi, "kfi.a_4_1_2-transactions_under_wma_and_overdraft_rec.in-gj", "2022-23") == 0.0
    # 2023-24 debt flows are not compiled anywhere: A.4 for the 28 States ends in 2022-23 (tested above)
    assert kfi.filter(pl.col("item_code").str.starts_with("a_4-") & (pl.col("period") == "2023-24")).height == 0
    # C.8.a maximum amount guaranteed: every 0 is dropped (it cannot be 0 while C.8 > 0)
    assert kfi.filter(pl.col("item_code").str.starts_with("c_8_a-") & (pl.col("value") == 0)).height == 0


def test_kfi_west_bengal_2022_23_public_account_kept(kfi):
    """West Bengal is the only State whose public account is compiled for 2022-23 (A.10 2,93,555): its
    values are kept and satisfy A.11 = A.8 + A.9 + A.10; the All_States aggregate (= WB only) is dropped."""
    wb = "in-wb"
    a10 = v(kfi, f"kfi.a_10-public_account_receipts.{wb}", "2022-23")
    assert a10 == pytest.approx(293555)
    a11 = kfi.filter(pl.col("item_code").str.starts_with("a_11-") & (pl.col("geography") == "IN-WB") & (pl.col("period") == "2022-23"))["value"][0]
    a8 = kfi.filter(pl.col("item_code").str.starts_with("a_8-") & (pl.col("geography") == "IN-WB") & (pl.col("period") == "2022-23"))["value"][0]
    a9 = v(kfi, f"kfi.a_9-contingency_fund_receipts.{wb}", "2022-23")
    assert a11 == pytest.approx(a8 + a9 + a10, abs=0.01)
    agg = kfi.filter(pl.col("dim_other").str.starts_with("state_group") & pl.col("item_code").str.contains("^(a_10|b_10|a_11|b_11)-") & (pl.col("period") == "2022-23"))
    assert agg.height == 0
    # other States: public account not compiled in 2022-23 -> A.10 and A.11 absent
    assert kfi.filter(pl.col("item_code").str.contains("^(a_10|a_11)-") & (pl.col("geography") == "IN-MH") & (pl.col("period") == "2022-23")).height == 0


def test_kfi_incomplete_aggregates_are_flagged(kfi):
    """Aggregates over States whose component is 'not compiled' are kept as published but point to a
    provenance record that says INCOMPLETE and names the States (issues file state_fiscal-3)."""
    n = _prov_notes(kfi, k("b_6-repayment_of_public_debt"), "2022-23")  # 18 of 28 States compiled
    assert n.startswith("INCOMPLETE AGGREGATE") and "MH" in n and "UP" in n
    n = _prov_notes(kfi, k("c_8_a-maximum_amount_guaranteed"), "2023-03-31")  # 3 of 28 States
    assert n.startswith("INCOMPLETE AGGREGATE") and "MH" in n
    n = _prov_notes(kfi, "kfi.a_5-total_capital_receipts_a_2_a_4.in-nl", "2022-23")  # A.4 not compiled for Nagaland
    assert n.startswith("INCOMPLETE TOTAL") and "NL" in n
    # complete cells keep the main record
    assert "INCOMPLETE" not in _prov_notes(kfi, k("a_4-public_debt_receipts"), "2019-20")
    assert "INCOMPLETE" not in _prov_notes(kfi, k("a_1-revenue_receipts"), "2023-24")


def test_kfi_undivided_ap_has_no_stocks_after_bifurcation(kfi):
    """Undivided AP ceased on 2 June 2014: no stock rows at end-March 2015 (its '2015' stocks are 0, and
    C.8.a repeats the end-March 2014 figure, 55,536)."""
    un = kfi.filter(pl.col("dim_other") == "boundary=undivided")
    assert un.filter(pl.col("period_type") == "date")["period"].max() == "2014-03-31"
    assert v(kfi, "kfi.c_8_a-maximum_amount_guaranteed.in-xap.undivided", "2014-03-31") == pytest.approx(55536)


@pytest.mark.parametrize("geo", [ALL28, "in-mh", "in-up", "in-sk", "in.neh_states"])
def test_kfi_identities(kfi, geo):
    def s(code):
        return f"kfi.{code}.{geo}"

    ident = {
        "a_1-revenue_receipts": {"state_s_own_revenue": 1, "central_transfers": 1},
        "state_s_own_revenue": {"a_1_1-tax_revenue": 1, "a_1_2-non_tax_revenue": 1},
        "a_1_1-tax_revenue": {f"a_1_1_{i}-{n}": 1 for i, n in enumerate(
            ["taxes_on_sales_trade_etc", "state_goods_and_service_tax", "state_excise", "taxes_on_vehicles",
             "stamps_and_registration_fees", "land_revenue", "other_taxes"], start=1)},  # fmt: skip
        "central_transfers": {"a_1_3-state_s_share_in_union_taxes_and_duties": 1, "a_1_4-grants_in_aid_from_goi": 1},
        "a_3-total_revenue_and_non_debt_capital_recei": {"a_1-revenue_receipts": 1, "a_2-non_debt_capital_receipts": 1},
        "b_1-revenue_expenditure": {"b_1_1-general_services_r": 1, "b_1_2-social_services_r": 1,
                                    "b_1_3-economic_services_r": 1, "b_1_4-assignment_compensation_to_local_bodies": 1},
        "b_5-total_expenditure_b_1_b_2_b_3_b_4": {"b_1-revenue_expenditure": 1, "b_2-capital_expenditure": 1,
                                                  "b_3-disbursement_of_loans_and_advances": 1,
                                                  "b_4-inter_state_settlement_disbursement": 1},
        "d_1-revenue_deficit_surplus_a_1_b_1": {"a_1-revenue_receipts": 1, "b_1-revenue_expenditure": -1},
        # the label prints (A.3-B.5) but the figures also net contingency-fund transfers (A.6, B.7): issue state_fiscal-9
        "d_2-fiscal_deficit_surplus_a_3_b_5": {"a_3-total_revenue_and_non_debt_capital_recei": 1,
                                               "b_5-total_expenditure_b_1_b_2_b_3_b_4": -1,
                                               "a_6-appropriation_from_contingency_fund": 1,
                                               "b_7-appropriation_to_contingency_fund": -1},
        "d_3-primary_deficit_surplus_d_2_b_1_a": {"d_2-fiscal_deficit_surplus_a_3_b_5": 1, "b_1_a-interest_payments": 1},
    }  # fmt: skip
    for total, parts in ident.items():
        viol = checks.check_identity(kfi, s(total), {s(p): c for p, c in parts.items()}, abs_tol=0.01)
        checks.assert_no_rows(viol, f"KFI {total} ({geo})")
    stocks = {"c_1-public_debt": {"c_1_1-internal_debt": 1, "c_1_2-loans_from_goi": 1},
              "c_3-outstanding_liabilities": {"c_1-public_debt": 1, "c_2-public_account_liabilities": 1}}  # fmt: skip
    for total, parts in stocks.items():
        checks.assert_no_rows(
            checks.check_identity(kfi, s(total), {s(p): c for p, c in parts.items()}, abs_tol=0.01), f"KFI {total} ({geo})"
        )


def test_kfi_states_add_up_to_all_states(kfi):
    """The 28 State blocks add up to All_States, and NEH + non-NEH = All_States (2023-24)."""
    y = kfi.filter((pl.col("period") == "2023-24") & (pl.col("unit") == "INR_crore"))
    y = y.filter(~pl.col("item_code").str.starts_with("c_10"))  # All_States 'GSDP' is India GDP (sheet note)
    states = y.filter(pl.col("geography").str.starts_with("IN-") & pl.col("dim_other").is_null())
    assert states["geography"].n_unique() == 28
    sums = states.group_by("item_code", maintain_order=True).agg(pl.col("value").sum().alias("states"))
    tot = y.filter(pl.col("dim_other") == "state_group=all_states_28").select("item_code", pl.col("value").alias("all"))
    j = tot.join(sums, on="item_code", how="left")
    bad = j.filter((pl.col("all") - pl.col("states")).abs() > 0.05)
    checks.assert_no_rows(bad, "sum of 28 States vs All_States")
    groups = y.filter(pl.col("dim_other").is_in(["state_group=neh_states", "state_group=non_neh_states"]))
    g = groups.group_by("item_code", maintain_order=True).agg(pl.col("value").sum().alias("groups"))
    bad = tot.join(g, on="item_code").filter((pl.col("all") - pl.col("groups")).abs() > 0.05)
    checks.assert_no_rows(bad, "NEH + non-NEH vs All_States")


def test_kfi_ranges_signs_continuity(kfi):
    # core aggregates are positive; many detail rows are net figures and can be negative as published
    # (e.g. Bihar State excise after prohibition refunds, WMA transactions, deposits)
    core = re.compile(r"^(a_1-|a_1_1-|a_1_1_2|a_1_3|a_1_4-|b_1-|b_1_a|b_1_b|b_1_c|b_2-|b_5-|c_1-|c_3-outstanding|c_10)")
    pos = kfi.filter((pl.col("unit") == "INR_crore") & pl.col("item_code").str.contains(core.pattern))
    checks.assert_no_rows(checks.check_range(pos, lo=0.0), "negative core KFI levels")
    # States as a whole ran a fiscal deficit (negative sign) in every year
    fd = kfi.filter(pl.col("series_id") == k("d_2-fiscal_deficit_surplus_a_3_b_5"))
    assert (fd["value"] < 0).all() and fd.height == 13
    big = kfi.filter(pl.col("series_id").is_in([k(c) for c in (
        "a_1-revenue_receipts", "b_1-revenue_expenditure", "a_1_3-state_s_share_in_union_taxes_and_duties",
        "b_1_a-interest_payments", "b_1_b-pension_and_other_retirement_benefits", "b_1_c-salaries")]))  # fmt: skip
    checks.assert_no_rows(checks.check_continuity(big, max_rel_change=0.5), "KFI year-on-year break > 50%")
    # E.1 interest/revenue receipts and E.2 committed expenditure/revenue receipts are proper shares;
    # E.3 (revenue deficit / fiscal deficit) explodes when a fiscal deficit is near zero, so it is not bounded
    ratios = kfi.filter((pl.col("unit") == "ratio") & pl.col("item_code").str.contains("^e_[12]-"))
    assert ratios.height > 700
    checks.assert_no_rows(checks.check_range(ratios, lo=0, hi=1.5), "KFI ratios E.1, E.2")


# ---------------------------------------------------------------------------------------------
# FC16 transfers and subsidies
# ---------------------------------------------------------------------------------------------


def test_transfers_anchor_values():
    tr = load("fc16_transfers")
    # sheet 'Time series of transfers - mast', rows 3, 88, 90 (cols C, G, H, J)
    assert v(tr, "tsm.states_share.actuals", "1952-53") == pytest.approx(73.8)
    assert v(tr, "tsm.states_share.actuals", "2023-24") == pytest.approx(1129494)
    assert v(tr, "tsm.total_grants.actuals", "2023-24") == pytest.approx(739260)
    assert v(tr, "tsm.total_transfers.actuals", "2023-24") == pytest.approx(1868754)
    assert v(tr, "tsm.gtr.actuals", "2023-24") == pytest.approx(3465519)
    # GTR is the Union's gross tax revenue (verify-5): tagged to the Centre, not to the States
    gtr = tr.filter(pl.col("item_code") == "gtr")
    assert set(gtr["institution"]) == {"gg_centre"} and gtr["dim_other"].null_count() == gtr.height
    assert set(tr.filter(pl.col("item_code") != "gtr")["institution"]) == {"gg_state"}
    assert v(tr, "tsm.states_share.be", "2025-26") == pytest.approx(1422444)
    assert v(tr, "tsm.states_share.re", "2024-25") == pytest.approx(1286885)
    # sheet 'Grants - details RBI', row 74 (2023-24)
    assert v(tr, "gd.fc_grants", "2023-24") == pytest.approx(148522)
    for total, parts in {
        "tsm.total_fc_transfers": ("tsm.states_share", "tsm.fc_grants"),
        "tsm.total_grants": ("tsm.fc_grants", "tsm.non_fc_grants"),
        "tsm.total_transfers": ("tsm.states_share", "tsm.total_grants"),
    }.items():
        for stage in ("actuals", "re", "be"):
            viol = checks.check_identity(tr, f"{total}.{stage}", [f"{p}.{stage}" for p in parts], abs_tol=0.5)
            checks.assert_no_rows(viol, f"transfers {total} {stage}")
    # the two sheets agree on total grants and States' share for the RBI years
    a = tr.filter(pl.col("series_id") == "tsm.total_grants.actuals").select("period", "value")
    b = tr.filter(pl.col("series_id") == "gd.total_grants").select("period", pl.col("value").alias("gd"))
    j = a.join(b, on="period").filter(pl.col("period") >= "1990-91")
    checks.assert_no_rows(j.filter((pl.col("value") - pl.col("gd")).abs() > 1.0), "master vs grant-details sheet")
    checks.assert_no_rows(checks.check_range(tr.filter(~pl.col("item_code").str.contains("grants_|state_plan")), lo=0), "transfers >= 0")


def test_subsidies_anchor_values():
    sub = load("fc16_subsidies")
    # sheet 'Sector wise Subsidies and Trans', rows 200, 216, 217, 3 (col H = 2023-24, col C = 2018-19)
    assert v(sub, "sub.power.in-up.gg_state", "2023-24") == pytest.approx(33383.5667)
    assert v(sub, "sub.fertilizer.in.gg_centre", "2023-24") == pytest.approx(188292.04)
    assert v(sub, "sub.food.in.gg_centre", "2023-24") == pytest.approx(230755.71)
    assert v(sub, "sub.agriculture.in-ap.gg_state", "2018-19") == pytest.approx(2741.55)
    assert v(sub, "sub.power.in-up.gg_state", "2025-26") == pytest.approx(29912.81)
    assert sub.filter(pl.col("period") == "2025-26")["estimate_stage"].unique().to_list() == ["BE"]
    assert sub.filter(pl.col("institution") == "gg_state")["geography"].n_unique() == 21
    checks.assert_no_rows(checks.check_range(sub, lo=0), "subsidies >= 0")


# ---------------------------------------------------------------------------------------------
# FC16 State Finance Accounts dump (derived major-head totals)
# ---------------------------------------------------------------------------------------------


def test_accounts_major_heads_match_kfi(kfi):
    """Major-head sums over the 28 States reproduce the published KFI totals (both FC16, 2023-24)."""
    fa = load("fc16_state_accounts")
    y = fa.filter((pl.col("period") == "2023-24") & (pl.col("institution") == "gg_state"))
    y = y.filter(~pl.col("geography").is_in(["IN-DL", "IN-PY", "IN-JK"]))

    def mh(code, account):
        return y.filter((pl.col("item_code") == code) & pl.col("dim_other").str.contains(account))["value"].sum()

    assert mh("mh_0006", "revenue_receipts") == pytest.approx(800112.0157, abs=0.01)  # KFI A.1.1.2 SGST
    assert mh("mh_0041", "revenue_receipts") == pytest.approx(106020.9925, abs=0.01)  # KFI A.1.1.4 vehicles
    assert mh("mh_0039", "revenue_receipts") == pytest.approx(249133.4951, abs=0.05)  # KFI A.1.1.3 excise
    assert mh("mh_0029", "revenue_receipts") == pytest.approx(23975.0878, abs=0.01)  # KFI A.1.1.6 land revenue
    # whole accounts: revenue receipts and capital expenditure by State = KFI A.1 and B.2
    for account, code in (("revenue_receipts", "a_1-revenue_receipts"), ("capital_expenditure", "b_2-capital_expenditure")):
        by_state = (
            y.filter(pl.col("dim_other").str.contains(account))
            .group_by("geography", maintain_order=True)
            .agg(pl.col("value").sum().alias("fa"))
        )
        kf = kfi.filter((pl.col("item_code") == code) & (pl.col("period") == "2023-24") & pl.col("geography").str.starts_with("IN-"))
        j = kf.filter(pl.col("dim_other").is_null()).select("geography", "value").join(by_state, on="geography", how="left")
        assert j.height == 28
        checks.assert_no_rows(j.filter((pl.col("value") - pl.col("fa")).abs() > 0.05), f"accounts {account} vs KFI")


def test_accounts_year_convention_and_union():
    fa = load("fc16_state_accounts")
    assert fa["period"].min() == "1995-96" and fa["period"].max() == "2023-24"  # 'Year' 1996..2024
    union = fa.filter(pl.col("institution") == "gg_centre")
    assert union.height > 0 and set(union["geography"]) == {"IN"}
    assert set(fa["status"]) == {"derived"}


def test_local_body_minor_heads():
    """Minor heads 191-198 are the CGA 'assistance to local bodies' heads (checked in the raw dump), and
    the rural total exceeds the Finance Commission grants for rural local bodies that pass through it."""
    raw = pinned_raw(Layout.default(), U, S.FC16, "fc16_state_accounts.xlsx")
    df = pl.read_excel(raw.path, sheet_name="ServiceHeads", engine="calamine", infer_schema_length=0)
    names = (
        df.filter(pl.col("Minor Head").is_in(["191", "192", "193", "196", "197", "198"]))
        .group_by("Minor Head", "Minor Head Desc", maintain_order=True)
        .len()
        .sort("len", descending=True)
        .unique("Minor Head", keep="first", maintain_order=True)
    )
    desc = dict(zip(names["Minor Head"], names["Minor Head Desc"].str.to_lowercase(), strict=True))
    assert "municipal corporation" in desc["191"]
    assert "municipalit" in desc["192"]
    assert "nagar panchayat" in desc["193"] or "notified area" in desc["193"]
    assert "zil" in desc["196"] or "district" in desc["196"]
    assert "block" in desc["197"] or "intermediate" in desc["197"]
    assert "gram panchayat" in desc["198"]
    lb = load("fc16_local_body_assistance").filter(pl.col("period") == "2023-24")
    # verify-8: minor heads 191-198 only; MH 3604 (KFI B.1.4) is excluded and the provenance says so
    pv = checks.load_provenance(U).filter(pl.col("prov_id").is_in(lb["prov_id"].unique().to_list()))
    assert pv.height == 1 and "3604" in pv["notes"][0]
    rural = lb.filter(pl.col("counterparty") == "gg_local_rural")["value"].sum()
    app = load("rbi_sf_appendices")
    rlb_fc = v(app, f"app1.total_revenue.ii.d.5.ii-grants_for_rural_local_bodies.{ALLUT}.actuals", "2023-24")
    assert rural > rlb_fc > 0


# ---------------------------------------------------------------------------------------------
# FC16 ULB dump
# ---------------------------------------------------------------------------------------------


def test_ulb_counts_and_totals():
    ulb = load("ulb_cityfinance")
    alli = "in.all_ulbs_in_dump"
    # registry (verified from the file): 3,725 ULBs in 2015-16 to 4,620 in 2023-24
    assert v(ulb, f"ulb.total_revenues_n_ulbs.{alli}", "2015-16") == 3725
    assert v(ulb, f"ulb.total_revenues_n_ulbs.{alli}", "2023-24") == 4620
    # States add up to the all-ULB row
    y = ulb.filter((pl.col("period") == "2023-24") & (pl.col("item_code") == "total_revenues"))
    assert y.filter(pl.col("geography") != "IN")["value"].sum() == pytest.approx(v(ulb, f"ulb.total_revenues.{alli}", "2023-24"))
    # identities per ULB carry over to sums where every ULB reports every part (checked at all-India level loosely)
    tr = v(ulb, f"ulb.total_revenues.{alli}", "2023-24")
    parts = sum(v(ulb, f"ulb.{c}.{alli}", "2023-24") for c in ("total_own_revenue", "total_grants", "assigned_revenue_and_compensation", "other_revenue"))
    assert abs(tr - parts) / tr < 0.02
    # municipal corporations (RBI) are a subset of ULBs: MC revenue < all-ULB revenue, same State and year
    mu = load("rbi_municipal")
    for geo in ("in-mh", "in-gj", "in-ka"):
        mc = v(mu, f"m1.revenue_receipts.{geo}.actuals", "2021-22")
        assert 0 < mc < v(ulb, f"ulb.total_revenues.{geo}", "2021-22") * 1.2
    money = ulb.filter(pl.col("unit") == "INR_crore")
    checks.assert_no_rows(checks.check_range(money.filter(pl.col("geography") == "IN"), lo=0, hi=1_000_000), "ULB all-India range")


# ---------------------------------------------------------------------------------------------
# RBI State Finances 2025-26
# ---------------------------------------------------------------------------------------------


def test_statements_anchor_values(st):
    # St 13 row 8 (Andhra Pradesh) and row 39 (All States and UTs), cols C, D, G
    assert v(st, "st13.interest_payments_gross.in-ap.actuals", "2023-24") == pytest.approx(29481.2)
    assert v(st, "st13.interest_payments_net.in-ap.actuals", "2023-24") == pytest.approx(29460.4)
    assert v(st, f"st13.interest_payments_gross.{ALLUT}.actuals", "2023-24") == pytest.approx(507175.4)
    assert v(st, f"st13.interest_payments_gross.{ALLUT}.be", "2025-26") == pytest.approx(624737.6)
    # St 17 rows 33 (Uttar Pradesh) and 39
    assert v(st, "st17.transfers_from_centre_gross.in-up.actuals", "2023-24") == pytest.approx(278176.3)
    assert v(st, f"st17.transfers_from_centre_gross.{ALLUT}.actuals", "2023-24") == pytest.approx(1800210.2)
    # St 36 row 37; St 14 row 20 (Maharashtra, own tax revenue share, col F)
    assert v(st, f"st36.subsidies.{ALLUT}.actuals", "2023-24") == pytest.approx(329610.4)
    assert v(st, f"st36.subsidies.{ALLUT}.actuals", "2018-19") == pytest.approx(187432.8)
    # verify-1: the total sums only reporting States; 2023-24 omits Maharashtra (43,158 in 2022-23) etc.
    pv = checks.load_provenance(U)
    pid = st.filter(pl.col("series_id") == f"st36.subsidies.{ALLUT}.actuals")["prov_id"].unique().to_list()
    note = pv.filter(pl.col("prov_id").is_in(pid))["notes"].to_list()
    assert len(note) == 1 and note[0].startswith("PARTIAL TOTAL")
    assert "2023-24: IN-AP, IN-AR, IN-GA, IN-JK, IN-MH, IN-UK;" in note[0] and "2022-23: IN-GA, IN-JK;" in note[0]
    assert v(st, "st36.subsidies.in-mh.actuals", "2022-23") == pytest.approx(43158.4)
    assert st.filter((pl.col("series_id") == "st36.subsidies.in-mh.actuals") & (pl.col("period") == "2023-24")).height == 0
    assert v(st, "st14.own_tax_revenue_share.in-mh.actuals", "2023-24") == pytest.approx(15.5)
    assert v(st, "st15.grants_share.in.all_states_uts.actuals", "2023-24") == pytest.approx(100)


def test_statements_states_add_up(st):
    y = st.filter(pl.col("unit") == "INR_crore")
    for (sid_prefix,), g in y.with_columns(pl.col("series_id").str.replace(r"\.(in-[a-z]{2}|in\.all_states_uts)\.", ".*.").alias("k")).group_by(
        "k", maintain_order=True
    ):
        pass
    for base in ("st13.interest_payments_gross", "st13.interest_payments_net", "st17.transfers_from_centre_gross", "st36.subsidies"):
        for stage, period in (("actuals", "2023-24"), ("re", "2024-25"), ("be", "2025-26")):
            rows = y.filter(pl.col("series_id").str.starts_with(base + ".") & pl.col("series_id").str.ends_with("." + stage) & (pl.col("period") == period))
            states = rows.filter(pl.col("geography") != "IN")["value"].sum()
            total = rows.filter(pl.col("geography") == "IN")["value"].sum()
            assert states == pytest.approx(total, abs=2.0), (base, stage)
    shares = st.filter((pl.col("unit") == "percent") & (pl.col("geography") != "IN"))
    s = shares.group_by("item_code", "period", "estimate_stage", maintain_order=True).agg(pl.col("value").sum())
    checks.assert_no_rows(s.filter((pl.col("value") - 100).abs() > 1.6), "State shares sum to 100")


def test_transfers_cross_table(st, app, at):
    """St 17 gross = States' share (App I B) + grants (App I D) + loans from the Centre (App III II), and
    St 17 net = gross - repayments (App IV III) - interest to the Centre (App II C.2.i): all 2023-24 Accounts."""
    p = "2023-24"
    share = v(app, f"app1.total_revenue.i.b-share_in_central_taxes.{ALLUT}.actuals", p)
    grants = v(app, f"app1.total_revenue.ii.d-grants_from_the_centre.{ALLUT}.actuals", p)
    loans = v(app, f"app3.total_capital_receipts.ii-loans_and_advances_from_the_centre.{ALLUT}.actuals", p)
    repay = v(app, f"app4.total_capital_disbursements.iii-repayment_of_loans_to_the_centre.{ALLUT}.actuals", p)
    intc = v(app, f"app2.total_expenditure.ii.c.2.i-interest_on_loans_from_the_centre.{ALLUT}.actuals", p)
    gross = v(st, f"st17.transfers_from_centre_gross.{ALLUT}.actuals", p)
    net = v(st, f"st17.transfers_from_centre_net.{ALLUT}.actuals", p)
    assert share + grants + loans == pytest.approx(gross, abs=0.1)
    assert gross - repay - intc == pytest.approx(net, abs=0.1)
    assert v(at, "at2.i-states_share_in_central_taxes.actuals", p) == pytest.approx(share, abs=0.1)
    assert v(at, "at2.ii-grants_from_the_centre.actuals", p) == pytest.approx(grants, abs=0.1)
    # App Table 2 rows III-VI for 2023-24 (Accounts) repeat 2022-23 and are not ingested (issue state_fiscal-5)
    stale = at.filter(pl.col("series_id").str.contains(r"^at2\.(iii|iv|v|vi)[-.]") & (pl.col("period") == p) & (pl.col("estimate_stage") == "Actuals"))
    assert stale.height == 0
    assert v(at, "at2.iii-gross_loans_from_the_centre.actuals", "2022-23") == pytest.approx(112672.8)
    # interest: Appendix II C.2 = Statement 13 gross
    assert v(app, f"app2.total_expenditure.ii.c.2-interest_payments.{ALLUT}.actuals", p) == pytest.approx(
        v(st, f"st13.interest_payments_gross.{ALLUT}.actuals", p), abs=0.1
    )


def test_app_tables_anchor_values_and_identities(at):
    # App T1 row 38 (2023-24), App T3 row 38, App T9 row 27, App T11 row 25 (end-March 2024)
    assert v(at, "at1.gross_fiscal_deficit.actuals", "2023-24") == pytest.approx(877194.6)
    assert v(at, "at1.revenue_deficit.actuals", "2023-24") == pytest.approx(93436.9)  # positive = deficit
    assert v(at, "at1.primary_revenue_deficit.actuals", "2023-24") == pytest.approx(-413738.5)  # negative = surplus
    assert v(at, "at1.gross_fiscal_deficit.be", "2025-26") == pytest.approx(1175074.7)
    assert v(at, "at3.total.actuals", "2023-24") == pytest.approx(5308361.1)
    assert v(at, "at9.market_borrowings.actuals", "2023-24") == pytest.approx(741070.8)
    assert v(at, "at11.market_loans.actuals", "2024-03-31") == pytest.approx(5519895)
    assert v(at, "at2.i-states_share_in_central_taxes.actuals", "2007-08") == pytest.approx(151402.5)
    viol = checks.check_identity(at, "at3.total.actuals", ["at3.development.actuals", "at3.non_development.actuals", "at3.others.actuals"], abs_tol=0.2)
    checks.assert_no_rows(viol, "App T3 total")
    # App T2: gross transfer = share + grants + loans, net = gross - repayments, all years but 2023-24
    t2 = at.filter(pl.col("series_id").str.starts_with("at2.") & (pl.col("period") != "2023-24"))
    for stage in ("actuals", "re", "be"):
        viol = checks.check_identity(
            t2.filter(pl.col("series_id").str.ends_with(stage)),
            f"at2.iv-gross_transfer.{stage}",
            [f"at2.i-states_share_in_central_taxes.{stage}", f"at2.ii-grants_from_the_centre.{stage}", f"at2.iii-gross_loans_from_the_centre.{stage}"],
            abs_tol=0.3,
        )
        checks.assert_no_rows(viol, f"App T2 gross transfer {stage}")
    stock = at.filter(pl.col("table_id") == "Appendix Table 11")
    assert set(stock["period_type"]) == {"date"} and set(stock["stock_flow"]) == {"stock"}


NUM_TOKEN = re.compile(r"^([ivx]+|[a-h]|\d+)$")


def _formula_violations(df, *, prefix_re):
    out = []
    df = df.with_columns(pl.col("item_code").str.replace(prefix_re, "").str.split("-").list.first().alias("path"))
    for key, g in df.group_by("period", "estimate_stage", "geography", "dim_other", maintain_order=True):
        vals = dict(zip(g["path"], g["value"], strict=True))
        labels = dict(zip(g["path"], g["item_label"], strict=True))
        for p, lab in labels.items():
            if not _FORMULA.search(lab):
                continue
            kids = [q for q in vals if q.startswith(p + ".") and NUM_TOKEN.match(q[len(p) + 1 :])]
            if not kids:
                continue
            d = vals[p] - sum(vals[q] for q in kids)
            if abs(d) > max(0.2, 0.06 * len(kids)):
                out.append({"key": str(key), "item": lab, "total": vals[p], "diff": d})
    return pl.DataFrame(out, schema={"key": pl.String, "item": pl.String, "total": pl.Float64, "diff": pl.Float64})


def test_appendices_printed_formulas_close(app, at):
    """Every line that prints its own formula ('(1 to 3)', '(i+ii)', '(A+B)') equals the sum of its
    numbered children, in every Appendix I-IV column and in App. Table 2 (blank children count as 0)."""
    checks.assert_no_rows(_formula_violations(app, prefix_re=r"^app[1-4]\."), "Appendices I-IV printed formulas")
    t2 = at.filter(pl.col("table_id") == "Appendix Table 2")
    checks.assert_no_rows(_formula_violations(t2, prefix_re=r"^$"), "App Table 2 printed formulas")
    # the parser found the whole tree (item counts per appendix)
    counts = dict(app.filter(pl.col("period") == "2023-24").group_by("table_id", maintain_order=True).len().iter_rows())
    assert counts["Appendix I"] >= 75 and counts["Appendix II"] >= 65 and counts["Appendix III"] >= 45 and counts["Appendix IV"] >= 100


def test_appendices_anchor_values(app):
    """Appendix I-IV 'All States and UTs' blocks, 2023-24 (Accounts), printed in Rs lakh."""
    lakh = {
        "app1.total_revenue-total_revenue": 393024020.7,  # App I sheet AP_1_T3 C7
        "app1.total_revenue.i.a.3.vii-state_goods_and_services_tax": 84112077.2,  # C29
        "app1.total_revenue.i.a.2.ii-stamps_and_registration_fees": 22815497.5,  # C15
        "app1.total_revenue.i.b-share_in_central_taxes": 112976146.1,  # C31
        "app2.total_expenditure-total_expenditure": 402367709.3,  # 2APDX_3 C7
        "app2.total_expenditure.ii.e-pensions": 49098318.2,  # 2APDX_4
        "app3.total_capital_receipts.i.1-market_loans": 100705831.8,  # AP_3_T5 C10
        "app4.total_capital_disbursements.i-total_capital_outlay": 74730579.1,  # 4APP_1 C9 '7,47,30,579.1'
    }
    for code, val in lakh.items():
        assert v(app, f"{code}.{ALLUT}.actuals", "2023-24") == pytest.approx(val / 100, abs=0.001), code
    assert v(app, f"app1.total_revenue.i.a.3.vii-state_goods_and_services_tax.{ALLUT}.be", "2025-26") == pytest.approx(1131954.794)
    assert set(app["unit"]) == {"INR_crore"}
    # revenue balance: Appendix IV 'A. Surplus (+)/Deficit (-) on Revenue Account' = App I total - App II total
    rb = v(app, f"app4.a-surplus_deficit_on_revenue_account.{ALLUT}.actuals", "2023-24")
    assert rb == pytest.approx(-93436.886, abs=0.01)
    assert rb == pytest.approx(
        v(app, f"app1.total_revenue-total_revenue.{ALLUT}.actuals", "2023-24")
        - v(app, f"app2.total_expenditure-total_expenditure.{ALLUT}.actuals", "2023-24"),
        abs=0.05,
    )


def test_kfi_vs_rbi_all_states(kfi, app):
    """28 States (KFI, Finance Accounts) must not exceed All States and UTs (RBI) for tax items, and
    differ only by the UTs with legislature plus reporting differences (< 8%)."""
    pairs = {
        "a_1_1_2-state_goods_and_service_tax": "app1.total_revenue.i.a.3.vii-state_goods_and_services_tax",
        "a_1_1_3-state_excise": "app1.total_revenue.i.a.3.ii-state_excise",
        "a_1_1_4-taxes_on_vehicles": "app1.total_revenue.i.a.3.iii-taxes_on_vehicles",
        "a_1_3-state_s_share_in_union_taxes_and_duties": "app1.total_revenue.i.b-share_in_central_taxes",
    }
    for kc, ac in pairs.items():
        a = v(kfi, k(kc), "2023-24")
        b = v(app, f"{ac}.{ALLUT}.actuals", "2023-24")
        assert a <= b * 1.001 and (b - a) / b < 0.08, (kc, a, b)


# ---------------------------------------------------------------------------------------------
# Municipal corporations and panchayats
# ---------------------------------------------------------------------------------------------


def test_municipal_anchor_values_and_totals():
    mu = load("rbi_municipal")
    # St 1 rows 8 and 36 (lakh): Andhra Pradesh 2019-20 1,81,524; Total 2019-20 1,11,30,799
    assert v(mu, "m1.revenue_receipts.in-ap.actuals", "2019-20") == pytest.approx(1815.24)
    assert v(mu, f"m1.revenue_receipts.{ALLUT}.actuals", "2019-20") == pytest.approx(111307.99)
    assert v(mu, f"m1.revenue_receipts.{ALLUT}.be", "2023-24") == pytest.approx(170721.94)
    assert v(mu, "m1.revenue_receipts.in-mh.actuals", "2019-20") == pytest.approx(45045.99)
    for code in ("m1.revenue_receipts", "m4.revenue_expenditure", "m8.capital_outlay"):
        for period, stage in (("2019-20", "actuals"), ("2021-22", "actuals"), ("2023-24", "be")):
            rows = mu.filter(pl.col("series_id").str.starts_with(code + ".") & pl.col("series_id").str.ends_with("." + stage) & (pl.col("period") == period))
            states = rows.filter(pl.col("geography") != "IN")["value"].sum()
            total = rows.filter(pl.col("geography") == "IN")["value"].sum()
            assert states == pytest.approx(total, rel=0.001, abs=0.5), (code, period)
    pct = mu.filter(pl.col("unit") == "percent")
    checks.assert_no_rows(checks.check_range(pct, lo=0, hi=15), "municipal % of GSDP")


def test_pri_values():
    pri = load("rbi_pri")
    # Appendix I sheet AP_7(ii), 'ALL STATES/UTs*' block, rows 7, 34 (Rs per panchayat)
    assert v(pri, "pri_app1.revenue_receipts-revenue_receipts", "2020-21") == 2202057
    assert v(pri, "pri_app1.revenue_receipts-revenue_receipts", "2021-22") == 2320265
    assert v(pri, "pri_app1.revenue_receipts.iii.1-grants_from_central_government", "2021-22") == 1846118
    assert set(pri.filter(pl.col("series_id").str.starts_with("pri_app"))["unit"]) == {"INR"}
    # Chapter II, Table II.3 and II.5 (Rs crore, balanced panel) and Tables II.1/II.2 (counts)
    assert v(pri, "pri_ch2.rr", "2020-21") == 41744
    assert v(pri, "pri_ch2.rr", "2022-23") == 35354
    assert v(pri, "pri_ch2.grants_centre", "2021-22") == 27060
    assert v(pri, "pri_ch2.rev_exp", "2020-21") == 24600
    assert v(pri, "pri_ch2.rev_exp_water_sanitation", "2022-23") == 5616
    assert v(pri, "pri_ch2.n_village_panchayats", "2022-12-31") == 255623
    assert v(pri, "pri_ch2.n_vp_panel_receipts", "2022-23") == 208848
    assert v(pri, "pri_ch2.n_vp_panel_expenditure", "2022-23") == 178572
    for p in ("2020-21", "2021-22", "2022-23"):
        parts = sum(v(pri, f"pri_ch2.{c}", p) for c in ("own_tax", "own_non_tax", "grants"))
        assert parts == pytest.approx(v(pri, "pri_ch2.rr", p), abs=3)  # printed rounded to whole crore
        assert v(pri, "pri_ch2.grants_centre", p) + v(pri, "pri_ch2.grants_state", p) <= v(pri, "pri_ch2.grants", p)


# ---------------------------------------------------------------------------------------------
# fetch plumbing
# ---------------------------------------------------------------------------------------------


def test_rbidocs_links_resolve_from_pinned_listings():
    lay = Layout.default()
    for sid, (name, _) in S.LISTINGS.items():
        links = S.listing_xlsx_links(pinned_raw(lay, U, sid, name).read_bytes())
        for f in (f for f in S.RBI_FILES if f.source_id == sid):
            url = S.resolve(f, links)
            assert url.startswith("https://rbidocs.rbi.org.in/rdocs/Publications/")
            assert pinned_raw(lay, U, sid, f.name).url == url
    assert S.resolve(S.RBI_FILES[0], S.listing_xlsx_links(pinned_raw(lay, U, S.RBI_SF, "rbi_sf_listing.html").read_bytes())).endswith(
        "02_APP23012026B2830D87C491433F932392727168FB91.XLSX"
    )
    assert R.SF_VINTAGE == "2026-01-23"


def test_app_tables_carry_delhi_puducherry_break(at):
    """verify-6: App. Tables 1, 2, 3, 9, 11 include Delhi and Puducherry from 2017-18 (sheet notes);
    every provenance record of the dataset says so."""
    pv = checks.load_provenance(U).filter(pl.col("prov_id").is_in(at["prov_id"].unique().to_list()))
    assert set(pv["table_id"]) == {f"Appendix Table {n}" for n in (1, 2, 3, 9, 11)}
    assert all("COVERAGE BREAK" in (n or "") and "2017-18" in n for n in pv["notes"])


# ---------------------------------------------------------------------------------------------
# State/UT codes and territories (DECISIONS D1-9; issues state_fiscal-21, -23)
# ---------------------------------------------------------------------------------------------


def test_codes_come_from_the_shared_map():
    """Names and FC16 abbreviations resolve through pipeline/core/geo.py, never a private table."""
    from pipeline.core import geo
    from pipeline.ingest.state_fiscal import common as C

    assert C.FC16_ABBR["CH"] == "IN-CG" == geo.state_code("Chhattisgarh")  # FC16 'CH' is not Chandigarh
    assert C.FC16_ABBR == {a: geo.state_code(n) for a, n in C._FC16_NAMES.items()}
    assert C.state_geo("NCT Delhi").geography == "IN-DL"
    assert C.state_geo("29. Jammu and Kashmir").geography == "IN-JK"
    assert C.state_geo("All States and UTs").dim_other == "state_group=all_states_uts"
    with pytest.raises(ValueError):
        C.state_geo("Atlantis")
    for name in ("fc16_kfi", "fc16_state_accounts", "fc16_local_body_assistance", "fc16_subsidies",
                 "ulb_cityfinance", "rbi_sf_statements", "rbi_municipal"):  # fmt: skip
        g = set(load(name)["geography"].unique().to_list()) - {"IN"}
        assert g <= geo.ALL_CODES, (name, g - geo.ALL_CODES)


def test_historical_territories_are_coded():
    """Undivided AP is IN-XAP (the boundary dim is kept as a redundant marker); the accounts of the former
    State of J&K (FY 2013-14 to 2018-19) are IN-XJK and the UT's (2020-21) IN-JK."""
    for name in ("fc16_kfi", "fc16_state_accounts", "fc16_local_body_assistance"):
        df = load(name)
        un = df.filter(pl.col("dim_other").fill_null("").str.contains("boundary=undivided"))
        assert un.height > 0 and set(un["geography"]) == {"IN-XAP"}, name
        assert df.filter((pl.col("geography") == "IN-AP") & pl.col("dim_other").fill_null("").str.contains("boundary")).height == 0
    fa = load("fc16_state_accounts")
    jk = fa.group_by("geography").agg(pl.col("period").min().alias("lo"), pl.col("period").max().alias("hi"))
    jk = {r["geography"]: (r["lo"], r["hi"]) for r in jk.filter(pl.col("geography").is_in(["IN-XJK", "IN-JK"])).to_dicts()}
    assert jk == {"IN-XJK": ("2013-14", "2018-19"), "IN-JK": ("2020-21", "2020-21")}
    # the recode changes the label only: J&K revenue receipts 2018-19 (sum of major heads, Rs crore)
    rr = fa.filter((pl.col("geography") == "IN-XJK") & (pl.col("period") == "2018-19") & pl.col("dim_other").str.contains("revenue_receipts"))
    assert rr["value"].sum() == pytest.approx(51231, abs=1)


def test_territory_guard():
    """Rows outside their territory's existence fail the build unless declared (straddles, successor figures)."""
    from pipeline.ingest import state_fiscal as SF
    from pipeline.ingest.state_fiscal.common import territory_class, territory_problems

    assert territory_class("IN-XAP", "2014-03-31", "date") is None
    assert territory_class("IN-XAP", "2014-15", "fy") == "straddle"
    assert territory_class("IN-XAP", "2015-03-31", "date") == "after"
    assert territory_class("IN-TS", "2013-14", "fy") == "before"
    assert territory_class("IN-JK", "2019-20", "fy") == "straddle"
    assert territory_class("IN-XJK", "2018-19", "fy") is None
    df = pl.DataFrame({"geography": ["IN-JK", "IN-MH"], "period": ["2018-19", "2018-19"], "period_type": ["fy", "fy"]})
    assert territory_problems(df, {}) and "IN-JK 2018-19: before" in territory_problems(df, {})[0]
    assert territory_problems(df, {("IN-JK", "2018-19", "before"): "x"}) == []
    assert territory_problems(df.head(0), {("IN-JK", "2018-19", "before"): "x"})  # declared but absent
    for name, declared in SF.TERRITORY_DECLARED.items():
        assert territory_problems(load(name.removeprefix(f"{U}_")), declared) == [], name


def test_territory_guard_requires_reason_in_provenance():
    """verify-13: every row outside its territory's existence must sit on a provenance record that says why.
    Before the fix, the KFI E.1-E.3 ratio record (AP, TS, AP_un FY 2014-15; 9 rows) and the Municipal
    per-cent-of-GSDP records (J&K FY 2019-20; 3 rows) had no such note."""
    from pipeline.ingest import state_fiscal as SF
    from pipeline.ingest.state_fiscal.common import territory_class, territory_problems

    df = pl.DataFrame({"geography": ["IN-JK", "IN-JK"], "period": ["2019-20"] * 2, "period_type": ["fy"] * 2,
                       "prov_id": ["p_ok", "p_silent"]})  # fmt: skip
    declared = {("IN-JK", "2019-20", "straddle"): "x"}
    notes = {"p_ok": "... (DECISIONS D1-9; ...)", "p_silent": "Per cent of GSDP."}
    got = territory_problems(df, declared, notes)
    assert len(got) == 1 and "p_silent" in got[0] and "does not state why" in got[0]
    assert territory_problems(df.filter(pl.col("prov_id") == "p_ok"), declared, notes) == []
    # the built data: every out-of-lifetime row's record states the reason (the build enforces the same)
    pv = {r["prov_id"]: r["notes"] for r in checks.load_provenance(U).select("prov_id", "notes").to_dicts()}
    n_rows = 0
    for name, declared in SF.TERRITORY_DECLARED.items():
        d = load(name.removeprefix(f"{U}_"))
        assert territory_problems(d, declared, pv) == [], name
        keys = d.select("geography", "period", "period_type").iter_rows()
        n_rows += sum(territory_class(*r) is not None for r in keys)
    assert n_rows == 1178  # 924 accounts, 22 local-body, 225 KFI, 6 Municipal, 1 St 36
    kfi = load("fc16_kfi").filter(pl.col("item_code").str.starts_with("e_") & (pl.col("period") == "2014-15"))
    kfi = kfi.filter(pl.col("geography").is_in(["IN-AP", "IN-TS", "IN-XAP"]))
    assert kfi.height == 9 and all("1 April-1 June 2014" in pv[p] for p in kfi["prov_id"])
    muni = load("rbi_municipal").filter((pl.col("geography") == "IN-JK") & (pl.col("period") == "2019-20"))
    assert muni.height == 6 and all("31 Oct 2019" in pv[p] for p in muni["prov_id"])


def test_kfi_ratios_are_within_block_2014_15(kfi):
    """The E.* ratio record says each ratio uses two flows of the same block and year, so the FY 2014-15 AP_un
    ratios cover 1 April-1 June 2014 like its flows. E.1 = B.1.a / A.1 exactly for AP, TS and AP_un
    (e.g. AP_un 2,090.95 / 24,977.05 = 0.083715; KFI 'State-wise', year column 2015)."""
    k = kfi.filter((pl.col("period") == "2014-15") & pl.col("geography").is_in(["IN-AP", "IN-TS", "IN-XAP"]))
    for g in ("IN-AP", "IN-TS", "IN-XAP"):
        s = {r["item_code"].split("-", 1)[0]: r["value"] for r in k.filter(pl.col("geography") == g).to_dicts()}
        assert s["e_1"] == pytest.approx(s["b_1_a"] / s["a_1"], abs=1e-6), g
    assert k.filter(pl.col("geography") == "IN-XAP").filter(pl.col("item_code").str.starts_with("e_1"))["value"][0] == (
        pytest.approx(0.083715, abs=1e-6))  # fmt: skip


def test_kfi_gsdp_territory_records(kfi):
    """AP/TS GSDP before the States existed and undivided-AP GSDP after it ceased carry their own records;
    AP + TS = undivided AP exactly (so the IN-XAP series must never be added to them)."""
    g = kfi.filter(pl.col("item_code").str.starts_with("c_10-"))
    pv = checks.load_provenance(U).select("prov_id", "notes")
    gj = g.join(pv, on="prov_id")
    succ = gj.filter(pl.col("notes").str.starts_with("SUCCESSOR-TERRITORY"))
    assert set(zip(succ["geography"], succ["period"], strict=True)) == {
        (s, p) for s in ("IN-AP", "IN-TS") for p in ("2011-12", "2012-13", "2013-14", "2014-15")
    }
    terr = gj.filter(pl.col("notes").str.starts_with("TERRITORIAL AGGREGATE"))
    assert set(terr["geography"]) == {"IN-XAP"} and sorted(terr["period"]) == [f"{y}-{(y + 1) % 100:02d}" for y in range(2014, 2024)]
    for p in ("2012-13", "2019-20"):
        ap, ts, un = (g.filter((pl.col("geography") == c) & (pl.col("period") == p))["value"][0] for c in ("IN-AP", "IN-TS", "IN-XAP"))
        assert un == pytest.approx(ap + ts, abs=0.01)


def test_kfi_c8a_2015_stale_undivided_ap_is_noted(kfi):
    """verify-10: All_States and non-NEH C.8.a at end-March 2015 include undivided AP's stale 55,536.02
    (= its end-March 2014 figure) on top of AP and Telangana; both rows' notes say so, with the sums."""
    rows = kfi.filter(pl.col("item_code").str.starts_with("c_8_a-") & (pl.col("period") == "2015-03-31") & pl.col("dim_other").str.starts_with("state_group"))
    notes = dict(zip(rows["dim_other"], rows.join(checks.load_provenance(U).select("prov_id", "notes"), on="prov_id")["notes"], strict=True))
    assert {k for k, x in notes.items() if "STALE UNDIVIDED-AP" in x} == {"state_group=all_states_28", "state_group=non_neh_states"}
    n = notes["state_group=all_states_28"]
    assert "INCOMPLETE AGGREGATE" in n and "STALE UNDIVIDED-AP" in n and "594,159.08" in n and "538,623.06" in n and "55,536.02" in n
    assert "STALE UNDIVIDED-AP" in notes["state_group=non_neh_states"]
    pv = checks.load_provenance(U).filter(pl.col("notes").fill_null("").str.contains("STALE UNDIVIDED-AP"))
    assert pv.height == 2  # nowhere else


def test_kfi_ceased_block_not_listed_as_not_compiled(kfi):
    """verify-12: undivided AP is never named as 'not compiled' for a stock dated after it ceased."""
    pv = checks.load_provenance(U).select("prov_id", "notes")
    late = kfi.filter((pl.col("period_type") == "date") & (pl.col("period") >= "2015-03-31")).join(pv, on="prov_id")
    lists = late["notes"].str.extract_all(r"not compiled for [^;)]*").explode().drop_nulls()
    assert lists.len() > 0 and not lists.str.contains("AP_un").any()


def test_state_provident_funds_gross_flows(app):
    """S9 (state_fiscal-25): RBI SF 2025-26 Appendix III item VI and Appendix IV item VII print State Provident
    Funds as gross receipts and gross disbursements (All States and UTs, Rs lakh; sheets AP_3_T5 rows 39-41 and
    4APP_3 rows 21-23, column '2023-24 (Accounts)'). Only Appendix III's 'Total capital receipts (includes
    public accounts on a net basis)' nets them."""
    def a(sid):
        return v(app, f"{sid}.{ALLUT}.actuals", "2023-24")

    r1, r2, r = (a(f"app3.total_capital_receipts.{c}") for c in
                 ("vi.1-state_provident_funds", "vi.2-others", "vi-state_provident_funds_etc"))  # fmt: skip
    d1, d2, d = (a(f"app4.total_capital_disbursements.{c}") for c in
                 ("vii.1-state_provident_funds", "vii.2-others", "vii-state_provident_funds_etc"))  # fmt: skip
    assert (r1, d1) == (pytest.approx(103892.371, abs=1e-3), pytest.approx(91398.493, abs=1e-3))
    assert r1 + r2 == pytest.approx(r, abs=0.01) and d1 + d2 == pytest.approx(d, abs=0.01)  # printed '(1 + 2)'
    assert r1 > d1 > 0  # both sides positive: gross flows, not a net figure
