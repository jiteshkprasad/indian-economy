"""Value tests for the rbi_banking_corporate unit.

Anchor values are read off the source pages themselves (www.rbi.org.in HTML tables; the table and
edition are named in each comment). Identities test that each table's components add up to its
printed totals; cross-table tests check that the same number printed in two places agrees.
"""

import re

import polars as pl
import pytest

from pipeline.core import checks
from pipeline.core.fetch import pinned_raw
from pipeline.core.paths import Layout
from pipeline.ingest import rbi_banking_corporate as U

pytestmark = pytest.mark.quality

AR23, AR24, AR25 = "2024-05-30", "2025-05-29", "2026-05-29"  # AR 2023-24, 2024-25, 2025-26 editions
RTP23, RTP24 = "2024-12-26", "2025-12-29"  # RTP 2023-24, 2024-25 editions


def _load(name: str) -> pl.DataFrame:
    return checks.load_dataset(U.UNIT, f"{U.UNIT}_{name}")


@pytest.fixture(scope="module")
def acc():
    return _load("rbi_accounts")


@pytest.fixture(scope="module")
def timing():
    return _load("rbi_surplus_timing")


@pytest.fixture(scope="module")
def banks():
    return _load("rtp_banks")


@pytest.fixture(scope="module")
def coop():
    return _load("rtp_coop")


@pytest.fixture(scope="module")
def nbfi():
    return _load("rtp_nbfi")


@pytest.fixture(scope="module")
def bsr():
    return _load("bsr1_mar2024")


@pytest.fixture(scope="module")
def pcbs():
    return _load("pcbs_2324")


def v(df, sid, period, vintage=None):
    return checks.value(df, sid, period, vintage)


# ---------------------------------------------------------------------------------------------
# RBI accounts (Annual Report Chapter XII)
# ---------------------------------------------------------------------------------------------


def test_rbi_accounts_anchor_values(acc):
    # Table XII.1, AR 2025-26: surplus row 30,307.45 / 87,416.22 / 2,10,873.99 / 2,68,590.07 / 2,86,588.46
    for fy, x in (("2021-22", 30307.45), ("2022-23", 87416.22), ("2023-24", 210873.99), ("2024-25", 268590.07),
                  ("2025-26", 286588.46)):
        assert v(acc, "xii_1.surplus_transferred.current", fy, AR25) == x
    # Income statement for the year ended 31 March 2024 (AR 2023-24): income 2,75,572.32 = interest
    # 1,88,605.73 + other income 86,966.59; employee cost 7,890.11; provisions 42,819.91.
    assert v(acc, "is.income_total.current", "2023-24", AR23) == 275572.32
    assert v(acc, "is.income_interest.current", "2023-24", AR23) == 188605.73
    assert v(acc, "is.income_other.current", "2023-24", AR23) == 86966.59
    assert v(acc, "is.exp_employee_cost.current", "2023-24", AR23) == 7890.11
    assert v(acc, "is.exp_provisions.current", "2023-24", AR23) == 42819.91
    # Schedule 13 (b) foreign-source interest 1,03,177.64; Schedule 14 (b)(iii) exchange gain 83,615.86
    assert v(acc, "sch13.b.sub_total.current", "2023-24", AR23) == 103177.64
    assert v(acc, "sch14.b.exchange_gain_loss_from_foreign_exchange_transactions.current", "2023-24", AR23) == 83615.86
    # Schedule 4 (iv) surplus payable to the Central Government, as on 31 March 2024: 2,10,873.99
    assert v(acc, "sch4.x.surplus_payable_to_the_central_government.current", "2024-03-31", AR23) == 210873.99
    # Schedule 2 (b)(i) deposits of SCBs with the RBI, 31 March 2024: 9,56,010.64
    assert v(acc, "sch2.b.scheduled_commercial_banks.current", "2024-03-31", AR23) == 956010.64
    # Balance sheet total, 31 March 2024: 70,47,703.21; Table XII.8 earnings from FCA 2023-24: 1,87,471.20
    assert v(acc, "bs.total_liabilities.current", "2024-03-31", AR23) == 7047703.21
    assert v(acc, "xii_8.fca_earnings.current", "2023-24", AR23) == 187471.20
    # Table XII.10 (AR 2025-26): provisions 2025-26 1,09,379.64 (the CF provision quoted in the registry)
    assert v(acc, "xii_10.provisions.current", "2025-26", AR25) == 109379.64


@pytest.mark.parametrize("vintage", [AR23, AR24, AR25])
def test_rbi_income_statement_identities(acc, vintage):
    d = acc.filter(pl.col("vintage") == vintage)
    tol = {"abs_tol": 0.015}
    checks.assert_no_rows(checks.check_identity(
        d, "is.income_total.current", ["is.income_interest.current", "is.income_other.current"], **tol), "income")
    exp_items = [s for s in d["series_id"].unique().sort().to_list() if s.startswith("is.exp_")]
    assert len(exp_items) == 15
    checks.assert_no_rows(checks.check_identity(d, "is.expenditure_total.current", exp_items, abs_tol=0.05), "expenditure")
    checks.assert_no_rows(checks.check_identity(
        d, "is.available_balance.current", {"is.income_total.current": 1, "is.expenditure_total.current": -1}, **tol),
        "available balance")
    transfers = {f"is.{c}.current": -1 for c in ("to_nic_lto_fund", "to_nhc_lto_fund", "to_nrc_lto_fund", "to_nrc_stabilisation_fund")}
    checks.assert_no_rows(checks.check_identity(
        d.filter(pl.col("series_id") != "is.to_others.current"), "is.surplus_payable.current",
        {"is.available_balance.current": 1, **transfers}, **tol), "surplus")


@pytest.mark.parametrize("vintage", [AR23, AR24, AR25])
def test_rbi_cross_table_agreement(acc, vintage):
    """The same figure printed in XII.1, XII.10, the income statement and the schedules agrees."""
    d = acc.filter(pl.col("vintage") == vintage)
    pairs = [
        ("xii_1.income.current", "is.income_total.current"),
        ("xii_1.total_expenditure.current", "is.expenditure_total.current"),
        ("xii_10.total.current", "is.expenditure_total.current"),
        ("xii_1.net_income.current", "is.available_balance.current"),
        ("xii_1.surplus_transferred.current", "is.surplus_payable.current"),
        ("xii_10.provisions.current", "is.exp_provisions.current"),
        ("xii_10.employee_cost.current", "is.exp_employee_cost.current"),
        ("sch13.total.current", "is.income_interest.current"),
        ("sch14.total.current", "is.income_other.current"),
        ("sch15.total.current", "is.exp_agency_charges.current"),
    ]
    fy_rows = d.filter(pl.col("period_type") == "fy")
    is_years = fy_rows.filter(pl.col("series_id") == "is.income_total.current")["period"].to_list()
    assert len(is_years) == 2
    both = fy_rows.filter(pl.col("period").is_in(is_years))  # the five-year tables reach further back
    for a, b in pairs:
        checks.assert_no_rows(checks.check_identity(both, a, [b], abs_tol=0.015), f"{a} = {b}")
    # the surplus payable at 31 March equals the surplus of the year just ended
    fy = {AR23: "2023-24", AR24: "2024-25", AR25: "2025-26"}[vintage]
    end = f"{int(fy[:4]) + 1}-03-31"
    assert v(d, "sch4.x.surplus_payable_to_the_central_government.current", end) == v(d, "is.surplus_payable.current", fy)
    # balance sheet balances, and schedules match their balance-sheet lines
    for date in d.filter(pl.col("series_id") == "bs.total_assets.current")["period"].to_list():
        assert v(d, "bs.total_assets.current", date) == v(d, "bs.total_liabilities.current", date)
        assert v(d, "bs.deposits.current", date) == v(d, "sch2.total.current", date)
        assert v(d, "bs.other_liabilities.current", date) == v(d, "sch4.total.current", date)
        assert v(d, "bs.notes_issued.current", date) == v(d, "sch5.total.current", date)
        assert v(d, "bs.loans_and_advances.current", date) == v(d, "sch10.total.current", date)


def test_rbi_accounts_same_across_editions(acc):
    """Audited accounts do not change between editions (the only difference is one per-cent ratio
    printed as 5.3 in AR 2024-25 and 5.31 in AR 2025-26)."""
    for old, new in ((AR23, AR24), (AR24, AR25)):
        rev = checks.compare_vintages(acc, old, new).filter(pl.col("change") == "revised")
        rev = rev.filter(pl.col("series_id") != "xii_8.fca_earnings_pct_avg_fca")
        checks.assert_no_rows(rev, f"revisions {old} -> {new}")


def test_rbi_accounts_ranges(acc):
    lv = acc.filter(pl.col("unit") == "INR_crore")
    may_be_negative = re.compile(r"^sch1[34]\.|^sch3\.")  # LAF/SDF interest, amortisation, FX losses
    pos = lv.filter(~pl.col("series_id").str.contains(may_be_negative.pattern))
    checks.assert_no_rows(checks.check_range(pos, lo=0), "negative RBI levels")
    checks.assert_no_rows(checks.check_range(lv, hi=1e8), "RBI level above Rs 10 crore crore")
    # income grows every year 2021-22 -> 2025-26 in the latest edition, by less than 60% a year
    inc = acc.filter((pl.col("series_id") == "xii_1.income.current") & (pl.col("vintage") == AR25))
    checks.assert_no_rows(checks.check_continuity(inc, max_rel_change=0.6), "RBI income jump")
    assert inc.sort("period")["value"].is_sorted()


def test_surplus_timing(timing, acc):
    # R6: cash received by the Centre in FY 2023-24 = RBI surplus for 2022-23 = 87,416.22 (DECISIONS D0-7)
    assert v(timing, "r6.surplus_received_by_centre_cash.current", "2023-24") == 87416.22
    assert v(timing, "r6.surplus_received_by_centre_cash.current", "2024-25") == 210873.99
    # K9b: 2,10,873.99 accrued minus 87,416.22 paid = 1,23,457.77 (gap map: 1,23,458)
    assert v(timing, "k9b.change_in_surplus_payable.current", "2023-24") == pytest.approx(123457.77, abs=0.005)
    assert set(timing["status"]) == {"derived"}
    prov = checks.load_provenance(U.UNIT)
    for pid in timing["prov_id"].unique().to_list():
        rec = prov.filter(pl.col("prov_id") == pid)
        assert rec["method"][0] and rec["inputs"][0], pid
        assert set(rec["inputs"][0].split(",")) <= set(acc["prov_id"].to_list())


# ---------------------------------------------------------------------------------------------
# Trend and Progress: banks
# ---------------------------------------------------------------------------------------------


def test_scb_pl_anchor_values(banks):
    # RTP 2024-25 Table IV.3 (2023-24 column): PSBs income 12,12,665; interest income 10,66,243;
    # SCBs wage bill 2,94,488; SCBs net profit 3,49,603; SCBs provisions and contingencies 2,41,331
    assert v(banks, "rtp.scb_pl.income_total.psb.current", "2023-24", RTP24) == 1212665
    assert v(banks, "rtp.scb_pl.interest_income.psb.current", "2023-24", RTP24) == 1066243
    assert v(banks, "rtp.scb_pl.wage_bill.scb.current", "2023-24", RTP24) == 294488
    assert v(banks, "rtp.scb_pl.net_profit.scb.current", "2023-24", RTP24) == 349603
    assert v(banks, "rtp.scb_pl.provisions_contingencies.scb.current", "2023-24", RTP24) == 241331
    assert v(banks, "rtp.scb_pl.net_profit.pb.current", "2023-24", RTP24) == -1
    assert v(banks, "rtp.scb_pl.nim.scb", "2023-24", RTP24) == 3.3
    # RTP 2023-24 Table IV.4 (2022-23 column): PSBs income 9,71,421; All SCBs interest expended 8,07,144
    assert v(banks, "rtp.scb_pl.income_total.psb.current", "2022-23", RTP23) == 971421
    assert v(banks, "rtp.scb_pl.interest_expended.scb.current", "2022-23", RTP23) == 807144
    # RTP 2024-25 Table IV.1: SCB deposits end-March 2024 2,17,41,578; loans and advances 1,71,42,309
    assert v(banks, "rtp.scb_bs.deposits.scb.current", "2024-03-31", RTP24) == 21741578
    assert v(banks, "rtp.scb_bs.loans_advances.scb.current", "2024-03-31", RTP24) == 17142309
    # RTP 2023-24 Table IV.1, figures in parentheses (excluding the merger): PVB deposits 74,51,388,
    # SCB loans 1,66,17,066
    assert v(banks, "rtp.scb_bs.deposits_excl_merger.pvb.current", "2024-03-31", RTP23) == 7451388
    assert v(banks, "rtp.scb_bs.loans_advances_excl_merger.scb.current", "2024-03-31", RTP23) == 16617066
    # RTP 2024-25 Table IV.4 (cost/return of funds, per cent): SCBs 2023-24 cost of deposits 4.8,
    # return on advances 9.4; SFBs return on advances 17.0
    assert v(banks, "rtp.scb_cost_return.cost_of_deposits.scb", "2023-24", RTP24) == 4.8
    assert v(banks, "rtp.scb_cost_return.return_on_advances.scb", "2023-24", RTP24) == 9.4
    assert v(banks, "rtp.scb_cost_return.return_on_advances.sfb", "2023-24", RTP24) == 17.0
    # RRBs (IV.32, RTP 2024-25): income 70,443, of which income tax 2,430, net profit 7,571
    assert v(banks, "rtp.rrb_pl.income_total.rrb.current", "2023-24", RTP24) == 70443
    assert v(banks, "rtp.rrb_pl.income_tax.rrb.current", "2023-24", RTP24) == 2430
    assert v(banks, "rtp.rrb_pl.net_profit.rrb.current", "2023-24", RTP24) == 7571
    # LABs (IV.35) income 197; payments banks (IV.39) tax provisions 68; RTP 2023-24 IV.40 PB 2021-22 net loss -131
    assert v(banks, "rtp.lab_pl.income_total.lab.current", "2023-24", RTP24) == 197
    assert v(banks, "rtp.pb_pl.tax_provisions.pb.current", "2023-24", RTP24) == 68
    assert v(banks, "rtp.pb_pl.net_profit.pb.current", "2021-22", RTP23) == -131


@pytest.mark.parametrize("vintage", [RTP23, RTP24])
@pytest.mark.parametrize("grp", ["psb", "pvb", "fb", "sfb", "pb", "scb"])
def test_scb_pl_identities(banks, vintage, grp):
    d = banks.filter(pl.col("vintage") == vintage)
    s = lambda c: f"rtp.scb_pl.{c}.{grp}.current"  # noqa: E731
    tol = {"abs_tol": 3.0}  # printed rounded to Rs crore
    idents = {
        "income_total": {"interest_income": 1, "other_income": 1},
        "expenditure_total": {"interest_expended": 1, "operating_expenses": 1, "provisions_contingencies": 1},
        "operating_profit": {"income_total": 1, "interest_expended": -1, "operating_expenses": -1},
        "net_profit": {"operating_profit": 1, "provisions_contingencies": -1},
        "net_interest_income": {"interest_income": 1, "interest_expended": -1},
    }
    for total, parts in idents.items():
        checks.assert_no_rows(checks.check_identity(d, s(total), {s(p): c for p, c in parts.items()}, **tol),
                              f"{total} ({grp}, {vintage})")


@pytest.mark.parametrize("vintage", [RTP23, RTP24])
def test_scb_groups_add_to_total(banks, vintage):
    d = banks.filter(pl.col("vintage") == vintage)
    for tbl, items, tol in (
        ("scb_pl", ("income_total", "interest_income", "expenditure_total", "interest_expended", "wage_bill",
                    "provisions_contingencies", "net_profit"), 5.0),
        ("scb_bs", ("deposits", "borrowings", "investments", "loans_advances", "total_liabilities_assets"), 5.0),
    ):
        for it in items:
            parts = [f"rtp.{tbl}.{it}.{g}.current" for g in ("psb", "pvb", "fb", "sfb", "pb")]
            sub = d.filter(pl.col("series_id").is_in(parts + [f"rtp.{tbl}.{it}.scb.current"]))
            # payments banks print '-' (nil) for loans: a missing part is nil there
            present = [p for p in parts if p in sub["series_id"].to_list()]
            checks.assert_no_rows(checks.check_identity(sub, f"rtp.{tbl}.{it}.scb.current", present, abs_tol=tol),
                                  f"{tbl} {it} groups ({vintage})")


@pytest.mark.parametrize("vintage", [RTP23, RTP24])
@pytest.mark.parametrize("grp", ["psb", "pvb", "fb", "sfb", "scb"])
def test_scb_balance_sheet_identities(banks, vintage, grp):
    d = banks.filter(pl.col("vintage") == vintage)
    s = lambda c: f"rtp.scb_bs.{c}.{grp}.current"  # noqa: E731
    have = set(d["series_id"].to_list())
    idents = {
        "total_liabilities_assets": ["capital", "reserves_surplus", "deposits", "borrowings", "other_liabilities_provisions"],
        "deposits": ["deposits_demand", "deposits_savings", "deposits_term"],
        "loans_advances": ["loans_bills", "loans_cash_credit_overdraft", "loans_term"],
        "investments": ["inv_gsec", "inv_other_approved", "inv_non_approved"],
    }
    for total, parts in idents.items():
        ps = [s(p) for p in parts if s(p) in have]  # '-' (nil) cells are not ingested
        checks.assert_no_rows(checks.check_identity(d, s(total), ps, abs_tol=3.0), f"{total} ({grp}, {vintage})")
    assets = ["cash_balances_rbi", "balances_banks_call_money", "investments", "loans_advances", "fixed_assets", "other_assets"]
    checks.assert_no_rows(checks.check_identity(d, s("total_liabilities_assets"), [s(p) for p in assets if s(p) in have],
                                                abs_tol=3.0), f"assets ({grp}, {vintage})")


def test_sfb_table_matches_scb_table(banks):
    """RTP 2024-25: Table IV.37 (SFBs) repeats the SFB columns of Table IV.3."""
    d = banks.filter(pl.col("vintage") == RTP24)
    for it in ("income_total", "interest_income", "expenditure_total", "interest_expended", "wage_bill", "net_profit"):
        checks.assert_no_rows(checks.check_identity(d, f"rtp.sfb_pl.{it}.sfb.current", [f"rtp.scb_pl.{it}.sfb.current"],
                                                    abs_tol=0.5), it)


def test_bank_ranges(banks):
    lv = banks.filter(pl.col("unit") == "INR_crore")
    may_be_negative = ["net_profit", "operating_profit", "reserves_surplus", "profit_before_tax", "tax_provisions"]
    checks.assert_no_rows(checks.check_range(lv.filter(~pl.col("item_code").is_in(may_be_negative)), lo=0),
                          "negative bank levels")
    checks.assert_no_rows(checks.check_range(banks.filter(pl.col("unit") == "percent"), lo=0, hi=25), "bank rates")
    # SCB income grew 29% in 2023-24 (HDFC merger) and 13% in 2024-25: nothing beyond 50% at the SCB level
    scb = banks.filter(pl.col("series_id").str.starts_with("rtp.scb_pl.") & pl.col("series_id").str.contains(r"\.scb\.current$"))
    checks.assert_no_rows(checks.check_continuity(scb, max_rel_change=0.5), "SCB P&L jump")


def test_bank_editions_agree_on_pl(banks):
    """2023-24 SCB P&L as printed in both editions: revisions are small (< 1.5%) where they exist.
    The largest are SFB other income (5,803 -> 5,753) and provisions (4,567 -> 4,521); logged."""
    rev = checks.compare_vintages(banks, RTP23, RTP24, rel_tol=0.015,
                                  series_ids=[s for s in banks["series_id"].unique().sort().to_list()
                                              if s.startswith("rtp.scb_pl.") and s.endswith(".current")])
    checks.assert_no_rows(rev.filter(pl.col("change") == "revised"), "SCB P&L revisions > 1.5%")


# ---------------------------------------------------------------------------------------------
# Trend and Progress: co-operative banks and NBFIs
# ---------------------------------------------------------------------------------------------


def test_coop_anchor_values_and_identities(coop):
    # RTP 2024-25 Table V.5: all UCBs total income 2023-24 55,198; provision for taxes 1,620; PAT 4,680
    assert v(coop, "rtp.ucb_pl.income_total.ucb.current", "2023-24", RTP24) == 55198
    assert v(coop, "rtp.ucb_pl.tax_provisions.ucb.current", "2023-24", RTP24) == 1620
    assert v(coop, "rtp.ucb_pl.net_profit.ucb.current", "2023-24", RTP24) == 4680
    # Table V.15 StCBs income 32,401 (2023-24), wage bill 2,178 (2024-25 P); Table V.18 DCCBs income 52,408
    assert v(coop, "rtp.stcb_pl.income_total.stcb.current", "2023-24", RTP24) == 32401
    assert v(coop, "rtp.stcb_pl.wage_bill.stcb.current", "2024-25", RTP24) == 2178
    assert v(coop, "rtp.dccb_pl.income_total.dccb.current", "2023-24", RTP24) == 52408
    row = coop.filter((pl.col("series_id") == "rtp.stcb_pl.wage_bill.stcb.current") & (pl.col("period") == "2024-25"))
    assert row["estimate_stage"][0] == "Provisional"  # printed '2024-25 P'
    for vintage in (RTP23, RTP24):
        d = coop.filter(pl.col("vintage") == vintage)
        for it in ("income_total", "interest_income", "expenditure_total", "net_profit", "tax_provisions"):
            checks.assert_no_rows(checks.check_identity(
                d, f"rtp.ucb_pl.{it}.ucb.current", [f"rtp.ucb_pl.{it}.ucb_scheduled.current",
                                                   f"rtp.ucb_pl.{it}.ucb_nonscheduled.current"], abs_tol=2.0), f"UCB {it}")
        for g in ("stcb", "dccb"):
            s = lambda c, g=g: f"rtp.{g}_pl.{c}.{g}.current"  # noqa: E731
            checks.assert_no_rows(checks.check_identity(d, s("income_total"), [s("interest_income"), s("other_income")],
                                                        abs_tol=2.0), f"{g} income")
            checks.assert_no_rows(checks.check_identity(
                d, s("expenditure_total"), [s("interest_expended"), s("provisions_contingencies"), s("operating_expenses")],
                abs_tol=2.0), f"{g} expenditure")
            checks.assert_no_rows(checks.check_identity(
                d, s("net_interest_income"), {s("interest_income"): 1, s("interest_expended"): -1}, abs_tol=2.0), f"{g} NII")
    checks.assert_no_rows(checks.check_range(coop.filter(~pl.col("item_code").is_in(["net_profit", "operating_profit",
                                                                                      "profit_before_tax"])), lo=0), "coop")


def test_nbfi_anchor_values(nbfi):
    # RTP 2024-25 Table VI.9: NBFC income 2023-24 5,93,747; NBFC-UL 1,82,115; total assets end-March 2025 61,09,126
    assert v(nbfi, "rtp.nbfc_pl.income_total.nbfc.current", "2023-24", RTP24) == 593747
    assert v(nbfi, "rtp.nbfc_pl.income_total.nbfc_ul.current", "2023-24", RTP24) == 182115
    assert v(nbfi, "rtp.nbfc_pl.total_assets.nbfc.current", "2025-03-31", RTP24) == 6109126
    # Appendix VI.6 (RTP 2024-25) NBFC-UL: tax provisions 2023-24 13,102; interest payment 42,930; 2022-23 income 1,41,310
    assert v(nbfi, "rtp.nbfc_layer_pl.tax_provisions.nbfc_ul.current", "2023-24", RTP24) == 13102
    assert v(nbfi, "rtp.nbfc_layer_pl.interest_payment.nbfc_ul.current", "2023-24", RTP24) == 42930
    assert v(nbfi, "rtp.nbfc_layer_pl.income_total.nbfc_ul.current", "2022-23", RTP24) == 141310
    # Table VI.12 HFCs 2023-24: total income 1,07,639; tax provision 826
    assert v(nbfi, "rtp.hfc_pl.income_total.hfc.current", "2023-24", RTP24) == 107639
    assert v(nbfi, "rtp.hfc_pl.tax_provisions.hfc.current", "2023-24", RTP24) == 826
    # Table VI.18 AIFIs 2023-24: income 1,05,392; provision for taxation 4,631; PAT 15,913
    assert v(nbfi, "rtp.aifi_pl.income_total.aifi.current", "2023-24", RTP24) == 105392
    assert v(nbfi, "rtp.aifi_pl.tax_provisions.aifi.current", "2023-24", RTP24) == 4631
    assert v(nbfi, "rtp.aifi_pl.net_profit.aifi.current", "2023-24", RTP24) == 15913
    # Table VI.23 SPDs 2023-24 income 10,270; Table VI.3 government NBFCs' assets end-March 2025 22,28,097
    assert v(nbfi, "rtp.spd_pl.income_total.spd.current", "2023-24", RTP24) == 10270
    assert v(nbfi, "rtp.nbfc_ownership.assets_government.nbfc.current", "2025-03-31", RTP24) == 2228097
    assert v(nbfi, "rtp.nbfc_ownership.assets_government.nbfc.current", "2024-03-31", RTP23) == 1901090
    assert v(nbfi, "rtp.nbfc_ownership.companies_total.nbfc", "2025-03-31", RTP24) == 431


@pytest.mark.parametrize("vintage", [RTP23, RTP24])
def test_nbfi_identities(nbfi, vintage):
    d = nbfi.filter(pl.col("vintage") == vintage)
    for it in ("income_total", "expenditure_total", "net_profit", "total_assets"):
        checks.assert_no_rows(checks.check_identity(
            d, f"rtp.nbfc_pl.{it}.nbfc.current", [f"rtp.nbfc_pl.{it}.nbfc_ul.current", f"rtp.nbfc_pl.{it}.nbfc_ml.current"],
            abs_tol=2.0), f"NBFC = UL + ML: {it}")
        # the appendix (VI.6/VI.7) repeats the layer totals of Table VI.9 (for the years VI.9 prints)
        for layer in ("nbfc_ul", "nbfc_ml"):
            total = f"rtp.nbfc_pl.{it}.{layer}.current"
            years = d.filter(pl.col("series_id") == total)["period"].to_list()
            assert len(years) >= 2
            checks.assert_no_rows(checks.check_identity(
                d.filter(pl.col("period").is_in(years)), total, [f"rtp.nbfc_layer_pl.{it}.{layer}.current"], abs_tol=0.5),
                f"VI.9 = appendix: {it} {layer}")
    for layer in ("nbfc_ul", "nbfc_ml"):
        s = lambda c, lay=layer: f"rtp.nbfc_layer_pl.{c}.{lay}.current"  # noqa: E731
        checks.assert_no_rows(checks.check_identity(
            d, s("expenditure_total"), [s("financial_expenditure"), s("operating_expenditure"), s("other_expenditure")],
            abs_tol=2.0), f"{layer} expenditure")
        checks.assert_no_rows(checks.check_identity(
            d, s("net_profit"), {s("profit_before_tax"): 1, s("tax_provisions"): -1}, abs_tol=2.0), f"{layer} PAT")
    a = lambda c: f"rtp.aifi_pl.{c}.aifi.current"  # noqa: E731
    checks.assert_no_rows(checks.check_identity(d, a("income_total"), [a("interest_income"), a("non_interest_income")],
                                                abs_tol=2.0), "AIFI income")
    checks.assert_no_rows(checks.check_identity(d, a("expenditure_total"), [a("interest_expended"), a("operating_expenses")],
                                                abs_tol=2.0), "AIFI expenditure")
    # Table VI.18 closure (to PAT via contingencies; the PBT line is inconsistent) is pinned in
    # test_aifi_table_closure and logged in the issues file.
    for g in ("nbfc", "nbfc_ul", "nbfc_ml"):
        o = lambda c, g=g: f"rtp.nbfc_ownership.{c}.{g}.current"  # noqa: E731
        have = set(d["series_id"].to_list())
        parts = [o(x) for x in ("assets_government", "assets_non_government") if o(x) in have]
        checks.assert_no_rows(checks.check_identity(d, o("assets_total"), parts, abs_tol=2.0), f"ownership {g}")
        checks.assert_no_rows(checks.check_identity(
            d, o("assets_non_government"), [o("assets_non_government_public_ltd"), o("assets_non_government_private_ltd")],
            abs_tol=2.0), f"non-government {g}")


def test_aifi_table_closure(nbfi):
    """RTP 2024-25 Table VI.18 (AIFIs) prints 'Provisions for Contingencies'. With it, income - expenditure
    - contingencies - taxation = PAT within 1 for 2022-23 and 2023-24 (e.g. 2023-24: 1,05,392 - 81,913 -
    2,936 - 4,631 = 15,912 vs PAT 15,913). It does not close for 2024-25 (18,710 vs PAT 19,773), and the
    'Operating Profit (PBT)' line is inconsistent with its components in every year (PBT - tax - PAT =
    1,550 / 514 / -283). RTP 2023-24 prints no contingencies line; its gap income - expenditure - tax - PAT
    equals the contingencies printed in the next edition (2,934 vs 2,935; 2,935 vs 2,936). Kept as printed;
    the findings are logged in the issues file (-8)."""
    a = lambda c, y, d: v(d, f"rtp.aifi_pl.{c}.aifi.current", y)  # noqa: E731
    d24 = nbfi.filter(pl.col("vintage") == RTP24)
    d23 = nbfi.filter(pl.col("vintage") == RTP23)

    def rest(y, d, cont=True):
        c = a("provisions_contingencies", y, d) if cont else 0
        return a("income_total", y, d) - a("expenditure_total", y, d) - c - a("tax_provisions", y, d) - a("net_profit", y, d)

    assert rest("2022-23", d24) == -1 and rest("2023-24", d24) == -1  # closes within rounding
    assert rest("2024-25", d24) == -1063  # 18,710 vs PAT 19,773
    for y, gap in (("2022-23", 1550), ("2023-24", 514), ("2024-25", -283)):  # PBT line vs its components
        assert a("profit_before_tax", y, d24) - a("tax_provisions", y, d24) - a("net_profit", y, d24) == gap
    assert rest("2022-23", d23, cont=False) == 2934 and rest("2023-24", d23, cont=False) == 2935
    assert d23.filter(pl.col("series_id") == "rtp.aifi_pl.provisions_contingencies.aifi.current").height == 0


def test_nbfi_ranges(nbfi):
    lv = nbfi.filter(pl.col("unit") == "INR_crore")
    checks.assert_no_rows(checks.check_range(lv.filter(~pl.col("item_code").is_in(["trading_profits", "net_profit"])), lo=0),
                          "negative NBFI levels")
    checks.assert_no_rows(checks.check_range(nbfi.filter(pl.col("unit") == "percent"), lo=0, hi=100), "shares")


# ---------------------------------------------------------------------------------------------
# press releases
# ---------------------------------------------------------------------------------------------


def _pdf_text(name: str, source: str) -> str:
    import pdfplumber

    raw = pinned_raw(Layout.default(), U.UNIT, source, name)
    with pdfplumber.open(raw.path) as pdf:
        return re.sub(r"\s+", " ", " ".join(p.extract_text() or "" for p in pdf.pages))


def test_bsr1_values(bsr):
    # BSR-1 March 2024 release (4 Jun 2024), Highlights: individuals 47.4%, other households 10.4% of
    # bank credit; growth 15.3% net of merger, 19.1% including it; PSB share 51.8%, PVB 40.6%
    assert v(bsr, "bsr1.share_credit_individuals.scb", "2024-03-31") == 47.4
    assert v(bsr, "bsr1.share_credit_other_households.scb", "2024-03-31") == 10.4
    assert v(bsr, "bsr1.credit_growth_net_of_merger.scb", "2023-24") == 15.3
    assert v(bsr, "bsr1.credit_growth_incl_merger.scb", "2023-24") == 19.1
    assert v(bsr, "bsr1.share_credit_by_group.psb", "2024-03-31") == 51.8
    assert v(bsr, "bsr1.share_credit_by_group.pvb", "2024-03-31") == 40.6
    checks.assert_no_rows(checks.check_range(bsr, lo=0, hi=100), "BSR per cent")


def test_bsr1_values_match_the_signed_pdf(bsr):
    """The PDF version of the release (rbidocs) prints the same figures as the HTML page."""
    try:
        text = _pdf_text(U.BSR_PDF, "rbi_bsr")
    except Exception as e:  # not pinned on a machine where rbidocs was challenged (D1-4)
        pytest.skip(f"BSR PDF not available: {e}")
    for x in bsr["value"].to_list():
        assert f"{x:.1f} per" in text, x


def test_pcbs_values(pcbs):
    # PCBS 2023-24 release (28 Jun 2024): sales growth 4.7% (2023-24) and 19.8% (2022-23); 3,281 companies;
    # operating profit margin manufacturing 14.4%, IT 22.7%
    assert v(pcbs, "pcbs.sales_growth.all", "2023-24") == 4.7
    assert v(pcbs, "pcbs.sales_growth.all", "2022-23") == 19.8
    assert v(pcbs, "pcbs.sample_companies.all", "2023-24") == 3281
    assert v(pcbs, "pcbs.operating_profit_margin.manufacturing", "2023-24") == 14.4
    assert v(pcbs, "pcbs.operating_profit_margin.it_services", "2023-24") == 22.7
    checks.assert_no_rows(checks.check_range(pcbs.filter(pl.col("unit") == "percent"), lo=0, hi=100), "PCBS per cent")


def test_pcbs_values_match_the_signed_pdf(pcbs):
    try:
        text = _pdf_text(U.PCBS_PDF, "rbi_corporate_finances")
    except Exception as e:
        pytest.skip(f"PCBS PDF not available: {e}")
    for x in pcbs.filter(pl.col("unit") == "percent")["value"].to_list():
        assert f"{x:.1f} per" in text or f"({x:.1f} per" in text, x
    assert "3,281" in text


# ---------------------------------------------------------------------------------------------
# whole unit
# ---------------------------------------------------------------------------------------------


def test_every_dataset_has_a_reference_year_value():
    for name in ("rbi_accounts", "rbi_surplus_timing", "rtp_banks", "rtp_coop", "rtp_nbfi", "bsr1_mar2024", "pcbs_2324"):
        df = _load(name)
        assert df.filter(pl.col("period").is_in(["2023-24", "2024-03-31"])).height > 0, name


def test_units_and_status():
    for name in ("rbi_accounts", "rtp_banks", "rtp_coop", "rtp_nbfi", "bsr1_mar2024", "pcbs_2324"):
        df = _load(name)
        assert set(df["status"]) == {"official"}, name
        assert set(df["unit"]) <= {"INR_crore", "percent", "count"}, name
        money = df.filter(pl.col("unit") == "INR_crore")
        assert set(money["price_basis"]) <= {"current"}, name
        assert money.filter(~pl.col("series_id").str.ends_with(".current")).height == 0, name


# ---------------------------------------------------------------------------------------------
# verifier findings (docs/phase1/issues/rbi_banking_corporate.md, 'Verifier findings')
# ---------------------------------------------------------------------------------------------


def test_bsr1_population_is_not_the_rtp_scb(bsr, banks):
    """BSR-1 covers SCBs including RRBs; RTP 'scb' excludes RRBs. The slugs must differ (V3)."""
    assert set(bsr.filter(pl.col("series_id").str.ends_with(".scb"))["institution"].unique()) == {"scb_incl_rrb"}
    grp = bsr.filter(pl.col("item_code") == "share_credit_by_group")
    assert set(grp["dim_other"].unique()) == {"denominator=scb_incl_rrb"}
    assert "scb_incl_rrb" not in set(banks["institution"].unique())


def test_merger_excluded_rows_carry_their_scope(banks):
    """Merger-excluded figures (RTP 2023-24 Table IV.1, printed in parentheses) are marked in dim_other (V7)."""
    ex = banks.filter(pl.col("item_code").str.ends_with("_excl_merger"))
    assert ex.height > 0 and set(ex["dim_other"].unique()) == {"scope=excl_merger"}
    assert set(ex["vintage"].unique()) == {RTP23}
    assert banks.filter(~pl.col("item_code").str.ends_with("_excl_merger"))["dim_other"].null_count() ==         banks.filter(~pl.col("item_code").str.ends_with("_excl_merger")).height


def test_estimate_stage_follows_the_printed_source(banks):
    """Stage comes from each table's printed note / source (V8). SFB P&L: RTP 2024-25 IV.37 cites annual
    accounts *and* off-site returns, RTP 2023-24 IV.38 off-site returns only: neither is wholly audited."""
    sfb = banks.filter(pl.col("series_id").str.starts_with("rtp.sfb_pl."))
    assert set(sfb["estimate_stage"].unique()) == {"n.a."}
    # SCB tables (source: annual accounts of respective banks) and cost/return of funds (computed from them)
    for pre in ("rtp.scb_pl.", "rtp.scb_bs.", "rtp.scb_cost_return."):
        assert set(banks.filter(pl.col("series_id").str.starts_with(pre))["estimate_stage"].unique()) == {"Audited"}, pre
    # a stage may differ between editions only from Provisional to n.a. (a year no longer flagged provisional)
    both = banks.group_by(["series_id", "period"]).agg(pl.col("estimate_stage").unique().sort())
    changed = both.filter(pl.col("estimate_stage").list.len() > 1)
    assert all(x == ["Provisional", "n.a."] for x in changed["estimate_stage"].to_list()), changed


def test_schedule_provenance_is_per_schedule(acc):
    """Each 'Schedule N' row points at a provenance record with table_id 'Schedule N' (V10), and the
    unlabelled Issue Department sub-total says so in its locator (V7)."""
    prov = pl.read_parquet(Layout.default().clean / U.UNIT / "_provenance.parquet")
    j = acc.join(prov.select("prov_id", pl.col("table_id").alias("p_table"), "locator"), on="prov_id")
    assert j.filter(pl.col("table_id") != pl.col("p_table")).height == 0
    unl = j.filter(pl.col("item_code") == "issue_department_assets_total")
    assert unl.height == 6 and all("UNLABELLED" in x and "matched by label" not in x for x in unl["locator"].to_list())


def test_reverse_check_ar_2019_20_and_2020_21_surplus_present_but_not_ingested(acc):
    """AR 2023-24 XII.1 also prints the 2019-20 (Jul-Jun) and 2020-21 (Jul-Mar transition) surplus
    (57,127.53 and 99,122.00); they are not April-March years and are not ingested (issues -7/-14, V6)."""
    assert set(acc.filter(pl.col("series_id") == "xii_1.surplus_transferred.current")["period"].unique()) == {
        "2021-22", "2022-23", "2023-24", "2024-25", "2025-26"}
