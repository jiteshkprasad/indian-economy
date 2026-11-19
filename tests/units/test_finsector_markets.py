"""Value tests for the finsector_markets unit (IRDAI Handbook 2024-25, EPFO AR 2023-24/2024-25,
PFRDA NPS statistics, SEBI Handbook 2025-26).

Anchor values are read off the published documents; the comment above each group says where.
Identity tests use the publishers' own totals. Where a published table does not add up, the test
names the exception and the issues file (docs/phase1/issues/finsector_markets.md) logs it.
"""

import polars as pl
import pytest

from pipeline.core import checks
from pipeline.core.fetch import pinned_raw
from pipeline.core.paths import Layout
from pipeline.ingest import finsector_markets as U

pytestmark = pytest.mark.quality
UNIT = U.UNIT


def _load(name):
    return checks.load_dataset(UNIT, f"{UNIT}_{name}")


@pytest.fixture(scope="module")
def summ():
    return _load("irdai_summary")


@pytest.fixture(scope="module")
def life():
    return _load("irdai_life")


@pytest.fixture(scope="module")
def nonlife():
    return _load("irdai_nonlife")


@pytest.fixture(scope="module")
def epfo():
    return _load("epfo_ar")


@pytest.fixture(scope="module")
def nps():
    return _load("pfrda_nps")


@pytest.fixture(scope="module")
def primary():
    return _load("sebi_primary")


@pytest.fixture(scope="module")
def bonds():
    return _load("sebi_bonds_equity")


@pytest.fixture(scope="module")
def foreign():
    return _load("sebi_foreign")


@pytest.fixture(scope="module")
def mf():
    return _load("sebi_mf")


def _v(df, sid, period, vintage=None):
    return checks.value(df, sid, period, vintage)


def _sum_present(df, total, parts, *, by=("vintage", "period"), abs_tol=1.0):
    """Like check_identity, but parts published as missing ('-', blank) count as zero. Rows where the
    total itself is missing are skipped."""
    d = df.filter(pl.col("series_id").is_in([total, *parts]))
    tot = d.filter(pl.col("series_id") == total).select(*by, pl.col("value").alias("total"))
    s = (
        d.filter(pl.col("series_id").is_in(parts))
        .group_by(list(by), maintain_order=True)
        .agg(pl.col("value").sum().alias("sum_parts"))
    )
    j = tot.join(s, on=list(by), how="left").with_columns(pl.col("sum_parts").fill_null(0.0))
    return j.filter((pl.col("total") - pl.col("sum_parts")).abs() > abs_tol)


# ------------------------------------------------------------------------------------------------
# IRDAI Handbook 2024-25
# ------------------------------------------------------------------------------------------------

# Summary B (life): total premium 2023-24 8,29,929.46; total benefits paid 5,77,021.35; Total Fund
# (AUM) 31 Mar 2024 61,56,849.50; LIC market share 57.32%. Summary C (general): gross direct premium
# 2,93,622.3; segment total within India 2,89,672.97; income from investments 44,129.04; PAT
# 10,118.72. Summary A: total premium 11,19,613; AUM 67,57,960.52; new policies 3,651.65 lakh.
def test_irdai_summary_anchors(summ):
    assert _v(summ, "sum_b.total_premium.current", "2023-24") == pytest.approx(829929.463617, abs=0.01)
    assert _v(summ, "sum_b.total_benefits_paid.current", "2023-24") == pytest.approx(577021.35)
    assert _v(summ, "sum_b.aum.total.current", "2024-03-31") == pytest.approx(6156849.50101736, abs=0.01)
    assert _v(summ, "sum_b.lic_market_share", "2023-24") == pytest.approx(57.32)
    assert _v(summ, "sum_c.gross_direct_premium.current", "2023-24") == pytest.approx(293622.3)
    assert _v(summ, "sum_c.gdp_segment.total.current", "2023-24") == pytest.approx(289672.97)
    assert _v(summ, "sum_c.investment_income.current", "2023-24") == pytest.approx(44129.04)
    assert _v(summ, "sum_c.profit_after_tax.current", "2023-24") == pytest.approx(10118.72)
    assert _v(summ, "sum_a.total_premium.current", "2023-24") == 1119613
    assert _v(summ, "sum_a.aum.current", "2024-03-31") == pytest.approx(6757960.52)
    assert _v(summ, "sum_a.new_policies", "2023-24") == pytest.approx(3651.65e5)  # 3,651.65 lakh
    # the Swiss Re penetration/density rows are not IRDAI figures and are not ingested
    assert not summ.filter(pl.col("item_code").str.contains("swiss_re")).height


def test_irdai_summary_identities(summ):
    # segment-wise gross direct premium within India (Summary C)
    segs = [f"sum_c.gdp_segment.{s}.current" for s in ("fire", "marine", "motor", "health", "others")]
    checks.assert_no_rows(checks.check_identity(summ, "sum_c.gdp_segment.total.current", segs, abs_tol=0.05),
                          "Summary C segments")
    aum = [f"sum_b.aum.{f}.current" for f in ("life_fund", "pension_annuity_group_fund", "ulip_fund")]
    checks.assert_no_rows(checks.check_identity(summ, "sum_b.aum.total.current", aum, abs_tol=2.0), "Summary B AUM")
    # all insurers = life + general, for AUM and PAT (Summary A vs B and C)
    for per in ("2022-03-31", "2023-03-31", "2024-03-31", "2025-03-31"):
        a = _v(summ, "sum_a.aum.current", per)
        assert a == pytest.approx(_v(summ, "sum_b.aum.total.current", per) + _v(summ, "sum_c.aum.current", per), abs=1)
    for fy in ("2022-23", "2023-24", "2024-25"):
        a = _v(summ, "sum_a.profit_after_tax.current", fy)
        assert a == pytest.approx(_v(summ, "sum_b.profit_after_tax.current", fy) + _v(summ, "sum_c.profit_after_tax.current", fy), abs=1)
        # from 2022-23 Summary A total premium = life total premium + general premium within India
        a = _v(summ, "sum_a.total_premium.current", fy)
        b_c = _v(summ, "sum_b.total_premium.current", fy) + _v(summ, "sum_c.gdp_segment.total.current", fy)
        assert a == pytest.approx(b_c, rel=1e-4)


# Table 2: LIC 4,75,751.92; private sector total 3,54,177.54; grand total 8,29,929.46 (2023-24).
# Table 20 (31 Mar 2024): life fund total 39,21,782.92; grand total 61,56,849.50.
# Table 24 (Rs lakh): industry premium 8,29,92,946.28 lakh; interest, dividends & rent 3,73,47,812.28
# lakh; benefits paid (net) 5,77,02,095.15 lakh; LIC premium 4,75,75,192 lakh.
# Table 25: industry PAT 47,40,727.69 lakh; LIC PAT 40,67,579 lakh; provision for taxation 22,341.73 lakh.
def test_irdai_life_anchors(life):
    assert _v(life, "t2.total_premium.lic.current", "2023-24") == pytest.approx(475751.92)
    assert _v(life, "t2.total_premium.life_private.current", "2023-24") == pytest.approx(354177.543617, abs=0.01)
    assert _v(life, "t2.total_premium.insurers_life.current", "2024-25") == pytest.approx(885771.734697, abs=0.01)
    assert _v(life, "t20.aum.life_fund.total.current", "2024-03-31") == pytest.approx(3921782.919487, abs=0.01)
    assert _v(life, "t20.aum.all_funds.total.current", "2025-03-31") == pytest.approx(6778660.560079, abs=0.01)
    assert _v(life, "t24.premium.insurers_life.current", "2023-24") == pytest.approx(829929.4628, abs=0.01)
    assert _v(life, "t24.inv_interest_dividends_rent_gross.insurers_life.current", "2023-24") == pytest.approx(373478.1228, abs=0.01)
    assert _v(life, "t24.benefits_paid_net.insurers_life.current", "2023-24") == pytest.approx(577020.9515, abs=0.01)
    assert _v(life, "t24.premium.lic.current", "2023-24") == pytest.approx(475751.92)
    assert _v(life, "t25.profit_after_tax.insurers_life.current", "2023-24") == pytest.approx(47407.2769, abs=0.01)
    assert _v(life, "t25.profit_after_tax.lic.current", "2023-24") == pytest.approx(40675.79)
    assert _v(life, "t25.provision_for_tax.insurers_life.current", "2023-24") == pytest.approx(223.4173, abs=0.001)
    # units: T24/T25 are published in Rs lakh; the provenance says so and records the conversion
    prov = checks.load_provenance(UNIT)
    t24 = prov.filter(pl.col("table_id") == "Table 24")
    assert set(t24["unit_as_published"]) == {"Rs lakh"} and set(t24["conversion"]) == {"INR_lakh -> INR_crore: x 0.01"}


def test_irdai_life_identities(life, summ):
    ci = checks.check_identity
    checks.assert_no_rows(ci(life, "t2.total_premium.insurers_life.current",
                             ["t2.total_premium.lic.current", "t2.total_premium.life_private.current"]), "T2 LIC + private")
    for fund, cats in (
        ("life_fund", ("central_govt_securities", "state_govt_other_approved_securities", "infrastructure",
                       "approved_investments", "other_than_approved")),
        ("pension_annuity_group_fund", ("central_govt_securities", "state_govt_other_approved_securities",
                                        "approved_investments")),
        ("ulip_fund", ("approved_investments", "other_than_approved")),
    ):
        checks.assert_no_rows(ci(life, f"t20.aum.{fund}.total.current", [f"t20.aum.{fund}.{c}.current" for c in cats],
                                 abs_tol=0.05), f"T20 {fund}")
    checks.assert_no_rows(ci(life, "t20.aum.all_funds.total.current",
                             [f"t20.aum.{f}.total.current" for f in ("life_fund", "pension_annuity_group_fund", "ulip_fund")],
                             abs_tol=0.05), "T20 grand total")
    # T2 and T20 agree with Summary B
    for fy in ("2019-20", "2023-24", "2024-25"):
        assert _v(life, "t2.total_premium.insurers_life.current", fy) == pytest.approx(_v(summ, "sum_b.total_premium.current", fy), abs=0.02)
    assert _v(life, "t20.aum.all_funds.total.current", "2024-03-31") == pytest.approx(_v(summ, "sum_b.aum.total.current", "2024-03-31"), abs=0.01)
    # T24 premium (Rs lakh -> crore) equals T2 total premium
    for inst in ("lic", "insurers_life"):
        for fy in ("2022-23", "2023-24", "2024-25"):
            assert _v(life, f"t24.premium.{inst}.current", fy) == pytest.approx(_v(life, f"t2.total_premium.{inst}.current", fy), abs=0.5)
    # the accounts' own sub-totals (industry and LIC, all years)
    for inst in ("insurers_life", "lic"):
        t = lambda code: f"t24.{code}.{inst}.current"  # noqa: E731
        a = ["premium", "reinsurance_ceded", "reinsurance_accepted", "inv_interest_dividends_rent_gross", "inv_profit_on_sale",
             "inv_loss_on_sale", "inv_fair_value_change", "inv_amortisation", "inv_appropriation_adjustment",
             "unrealised_gains", "other_income", "transfer_from_shareholders"]
        b = ["commission", "operating_expenses", "provision_doubtful_debts", "prior_year_adjustment",
             "bad_debts_written_off", "provision_for_tax", "provision_diminution_investments", "provision_others",
             "service_tax_ulip_charges"]
        c = ["benefits_paid_net", "interim_bonuses_paid", "change_liability_gross", "change_liability_ceded",
             "change_liability_accepted", "transfer_to_linked_fund", "fund_discontinued_policies"]
        present = set(life["series_id"])
        for total, parts in (("total_a_income", a), ("total_b_expenses", b), ("total_c_benefits_reserves", c)):
            v = _sum_present(life.filter(pl.col("period") == "2023-24"), t(total), [t(p) for p in parts if t(p) in present],
                             abs_tol=0.05)
            checks.assert_no_rows(v, f"T24 {total} {inst} 2023-24")
        v = checks.check_identity(life.filter(pl.col("period") == "2023-24"), t("surplus"),
                                  {t("total_a_income"): 1, t("total_b_expenses"): -1, t("total_c_benefits_reserves"): -1},
                                  abs_tol=0.05)
        checks.assert_no_rows(v, f"T24 surplus {inst}")
        s = lambda code: f"t25.{code}.{inst}.current"  # noqa: E731
        v = checks.check_identity(life.filter(pl.col("period") == "2023-24"), s("profit_before_tax"),
                                  {s("total_a_income"): 1, s("total_b_expenses"): -1}, abs_tol=0.05)
        checks.assert_no_rows(v, f"T25 PBT {inst}")
        v = checks.check_identity(life.filter(pl.col("period") == "2023-24"), s("profit_after_tax"),
                                  {s("profit_before_tax"): 1, s("provision_for_tax"): -1}, abs_tol=0.05)
        checks.assert_no_rows(v, f"T25 PAT {inst}")
    # T25 industry PAT = Summary B PAT
    assert _v(life, "t25.profit_after_tax.insurers_life.current", "2023-24") == pytest.approx(_v(summ, "sum_b.profit_after_tax.current", "2023-24"), abs=0.01)


# Table 40 (2023-24): public 94,191.20; private 1,55,090.19; specialised 11,211.34; SAHI 33,119.30;
# grand total 2,93,612.04. Table 44 all segments (grand total): net premium earned 2,08,791.32;
# claims incurred (net) 1,72,290.46. Table 46 total AUM 31 Mar 2024 6,01,111.02.
def test_irdai_nonlife_anchors(nonlife):
    assert _v(nonlife, "t40.gross_direct_premium.general_public.current", "2023-24") == pytest.approx(94191.2026)
    assert _v(nonlife, "t40.gross_direct_premium.general_private.current", "2023-24") == pytest.approx(155090.19219)
    assert _v(nonlife, "t40.gross_direct_premium.insurers_general_direct.current", "2023-24") == pytest.approx(293612.04022)
    assert _v(nonlife, "t41.gross_direct_premium.fire.general_public.current", "2023-24") == pytest.approx(9223.405726, abs=1e-5)
    assert _v(nonlife, "t44.net_premium_earned.total.insurers_general_direct.current", "2023-24") == pytest.approx(208791.315339, abs=0.01)
    assert _v(nonlife, "t44.claims_incurred_net.total.insurers_general_direct.current", "2023-24") == pytest.approx(172290.460808, abs=0.01)
    assert _v(nonlife, "t44.net_premium_earned.fire.general_public.current", "2023-24") == pytest.approx(5752.7331096, abs=1e-4)
    assert _v(nonlife, "t46.aum.total.current", "2024-03-31") == pytest.approx(601111.015739, abs=0.01)
    assert _v(nonlife, "t46.aum.central_govt_securities.current", "2024-03-31") == pytest.approx(179398.743033, abs=0.01)
    assert _v(nonlife, "t51.profit_after_tax.general_private.current", "2023-24") == pytest.approx(6046.793825, abs=1e-5)
    assert _v(nonlife, "t51.provision_for_tax.general_private.current", "2023-24") == pytest.approx(2196.69839, abs=1e-5)


def test_irdai_nonlife_identities(nonlife, summ):
    ci = checks.check_identity
    groups = ("general_public", "general_private", "general_specialized", "health_standalone")
    checks.assert_no_rows(ci(nonlife, "t40.gross_direct_premium.insurers_general_direct.current",
                             [f"t40.gross_direct_premium.{g}.current" for g in groups], abs_tol=0.05), "T40 groups")
    segs41 = ("fire", "marine", "motor", "health_pa_travel", "others")
    for g in (*groups, "insurers_general_direct"):
        v = _sum_present(nonlife, f"t41.gross_direct_premium.total.{g}.current",
                         [f"t41.gross_direct_premium.{s}.{g}.current" for s in segs41], abs_tol=0.05)
        checks.assert_no_rows(v, f"T41 segments {g}")
    for m, bad in (("net_premium_earned", []), ("claims_incurred_net", ["2019-20"])):
        v = _sum_present(nonlife, f"t44.{m}.total.insurers_general_direct.current",
                         [f"t44.{m}.{s}.insurers_general_direct.current" for s in ("fire", "marine", "motor", "health", "others")],
                         abs_tol=0.5)  # 2015-16 net premium: segments exceed the total by Rs 0.40 cr (publisher rounding)
        # 2019-20 claims: the five segments add to 1,09,133.47 against a printed total of 1,08,390.26 (logged)
        assert v["period"].to_list() == bad, (m, v)
    cats = ("central_govt_securities", "state_govt_other_approved_securities", "housing_state_govt_loans", "infrastructure",
            "approved_investments", "other_investments")
    checks.assert_no_rows(ci(nonlife, "t46.aum.total.current", [f"t46.aum.{c}.current" for c in cats], abs_tol=0.05), "T46 total")
    # cross-table: T41 within-India total = Summary C segment total; T46 = Summary C AUM
    for fy in ("2021-22", "2022-23", "2023-24", "2024-25"):
        assert _v(nonlife, "t41.gross_direct_premium.total.insurers_general_direct.current", fy) == pytest.approx(
            _v(summ, "sum_c.gdp_segment.total.current", fy), abs=0.6)
    assert _v(nonlife, "t46.aum.total.current", "2024-03-31") == pytest.approx(_v(summ, "sum_c.aum.current", "2024-03-31"), abs=0.01)
    # Known publisher difference (issues file): T40 grand total 2,93,612.04 vs Summary C 2,93,622.30 in 2023-24
    assert _v(summ, "sum_c.gross_direct_premium.current", "2023-24") - _v(
        nonlife, "t40.gross_direct_premium.insurers_general_direct.current", "2023-24") == pytest.approx(10.26, abs=0.01)
    # T51: PBT = total A - total B, private and SAHI groups (public-sector PAT also carries prior-period items)
    for g in ("general_private", "health_standalone"):
        s = lambda code: f"t51.{code}.{g}.current"  # noqa: E731
        d = nonlife.filter(pl.col("period") == "2023-24")
        checks.assert_no_rows(ci(d, s("profit_before_tax"), {s("total_a_income"): 1, s("total_b_expenses"): -1}, abs_tol=0.05),
                              f"T51 PBT {g}")
        checks.assert_no_rows(ci(d, s("profit_after_tax"), {s("profit_before_tax"): 1, s("provision_for_tax"): -1}, abs_tol=0.05),
                              f"T51 PAT {g}")


def test_irdai_ranges_and_continuity(summ, life, nonlife):
    for df in (summ, life, nonlife):
        checks.assert_no_rows(checks.check_range(df.filter(pl.col("unit") == "percent"), lo=0, hi=150), "percent range")
    stocks = pl.concat([life, nonlife], how="diagonal_relaxed").filter(
        pl.col("series_id").str.ends_with("total.current") & (pl.col("stock_flow") == "stock"))
    checks.assert_no_rows(checks.check_range(stocks, lo=0), "AUM totals non-negative")
    # one expected break: ULIP funds +40% in the year to March 2021 (equity market rebound after March 2020)
    v = checks.check_continuity(stocks, max_rel_change=0.35)
    assert v.select("series_id", "to_period").rows() == [("t20.aum.ulip_fund.total.current", "2021-03-31")], v
    prem = pl.concat([summ.filter(pl.col("series_id").is_in(["sum_b.total_premium.current", "sum_c.gross_direct_premium.current",
                                                              "sum_a.total_premium.current"])),
                      life.filter(pl.col("series_id").str.starts_with("t2."))], how="diagonal_relaxed")
    checks.assert_no_rows(checks.check_range(prem, lo=0), "premium non-negative")
    # the general-insurance premium jump of 2016-17 (+31.9%, crop insurance PMFBY) is the only break > 25%
    v = checks.check_continuity(prem, max_rel_change=0.25)
    assert v.select("series_id", "to_period").rows() == [("sum_c.gross_direct_premium.current", "2016-17")], v


# ------------------------------------------------------------------------------------------------
# EPFO Annual Reports
# ------------------------------------------------------------------------------------------------

# AR 2023-24 para 5.4: EPF 2,26,198.57; EPS employers' 62,423.93, Government 9,356.48, total 71,780.41;
# EDLI 3,358.10. Appendix-5(i) total row: EPF payment 1,18,690.66; total contribution 2,91,980.60;
# total payment 1,44,152.67. Para 5.20: EPF investments 31.03.2024 15,29,368.04 (SDL 7,03,691.38).
# AR 2024-25: 2023-24 EPF contribution revised to 2,33,489.80; 2024-25 total contribution 3,35,628.81.
def test_epfo_anchors(epfo):
    v1, v2 = "2024-12", "2026-02"
    assert _v(epfo, "para54.epf_contribution.current", "2023-24", v1) == pytest.approx(226198.57)
    assert _v(epfo, "para54.eps_contribution_employer.current", "2023-24", v1) == pytest.approx(62423.93)
    assert _v(epfo, "para54.eps_contribution_government.current", "2023-24", v1) == pytest.approx(9356.48)
    assert _v(epfo, "para54.edli_contribution.current", "2023-24", v1) == pytest.approx(3358.10)
    assert _v(epfo, "app5i.epf_payment.current", "2023-24", v1) == pytest.approx(118690.66)
    assert _v(epfo, "app5i.total_contribution.current", "2023-24", v1) == pytest.approx(291980.60)
    assert _v(epfo, "app5i.total_payment.current", "2023-24", v1) == pytest.approx(144152.67)
    assert _v(epfo, "invest.epf.total.current", "2024-03-31", v1) == pytest.approx(1529368.04)
    assert _v(epfo, "invest.epf.state_development_loans.current", "2024-03-31", v1) == pytest.approx(703691.38)
    assert _v(epfo, "invest.eps.public_account_central_govt.current", "2024-03-31", v1) == pytest.approx(226530.85)
    assert _v(epfo, "invest.epf.public_account_central_govt.current", "2024-03-31", v1) == 0.0  # printed '-'
    assert _v(epfo, "exempted.total_net.current", "2023-24", v1) == pytest.approx(431913.38)
    assert _v(epfo, "fiveyear.epf_contribution.current", "2019-20", v1) == pytest.approx(124365.85)
    assert _v(epfo, "fiveyear.epf_contribution.current", "2023-24", v2) == pytest.approx(233489.80)
    assert _v(epfo, "fiveyear.total_contribution.current", "2024-25", v2) == pytest.approx(335628.81)
    assert _v(epfo, "invest.epf.total.current", "2025-03-31", v2) == pytest.approx(1764126.30)
    assert _v(epfo, "invest.epf.invits.current", "2025-03-31", v2) == pytest.approx(41.28)
    assert _v(epfo, "app5vii.epf_interest_rate", "2023-24", v1) == 8.25
    assert _v(epfo, "app5vii.epf_interest_rate", "2021-22", v2) == 8.10
    stage = epfo.filter((pl.col("series_id") == "para54.epf_contribution.current") & (pl.col("period") == "2023-24"))
    assert stage["estimate_stage"].to_list() == ["Unaudited"]


def test_epfo_identities(epfo):
    ci = checks.check_identity
    checks.assert_no_rows(ci(epfo, "para54.eps_contribution_total.current",
                             ["para54.eps_contribution_employer.current", "para54.eps_contribution_government.current"]),
                          "EPS total")
    for side in ("contribution", "payment"):
        checks.assert_no_rows(ci(epfo, f"app5i.total_{side}.current",
                                 [f"app5i.{s}_{side}.current" for s in ("epf", "eps", "edli")], abs_tol=0.02), f"App 5(i) {side}")
        checks.assert_no_rows(ci(epfo.filter(pl.col("vintage") == "2026-02"), f"fiveyear.total_{side}.current",
                                 [f"fiveyear.{s}_{side}.current" if not (s == "eps" and side == "contribution")
                                  else "fiveyear.eps_contribution_employer.current" for s in ("epf", "eps", "edli")],
                                 abs_tol=0.02), f"five-year {side}")
    # para 5.4 = Appendix-5(i) = five-year table, same report year
    for vin, fy in (("2024-12", "2023-24"), ("2026-02", "2024-25")):
        d = epfo.filter(pl.col("vintage") == vin)
        assert _v(d, "para54.epf_contribution.current", fy) == _v(d, "app5i.epf_contribution.current", fy) == _v(
            d, "fiveyear.epf_contribution.current", fy)
        assert _v(d, "para54.eps_contribution_employer.current", fy) == _v(d, "app5i.eps_contribution.current", fy)
    # investments: categories add to the table total; total = end-of-year corpus; end - start = net addition
    for vin, end, start, fy in (("2024-12", "2024-03-31", "2023-03-31", "2023-24"), ("2026-02", "2025-03-31", "2024-03-31", "2024-25")):
        d = epfo.filter(pl.col("vintage") == vin)
        for sch in ("epf", "eps", "edli", "staff_pf", "staff_pension_gratuity"):
            cats = [s for s in d["series_id"].unique().to_list()
                    if s.startswith(f"invest.{sch}.") and s.split(".")[2] not in ("total", "net_addition", "category_total")]
            assert len(cats) == (9 if vin == "2024-12" else 10), (sch, vin, cats)
            checks.assert_no_rows(ci(d.filter(pl.col("period") == end), f"invest.{sch}.category_total.current", cats, abs_tol=0.02),
                                  f"{sch} categories {vin}")
            assert _v(d, f"invest.{sch}.category_total.current", end) == _v(d, f"invest.{sch}.total.current", end)
            assert _v(d, f"invest.{sch}.total.current", end) - _v(d, f"invest.{sch}.total.current", start) == pytest.approx(
                _v(d, f"invest.{sch}.net_addition.current", fy), abs=0.02)
    # the closing corpus of AR 2023-24 is the opening corpus of AR 2024-25
    for sch in ("epf", "eps", "edli", "staff_pf", "staff_pension_gratuity"):
        assert _v(epfo, f"invest.{sch}.total.current", "2024-03-31", "2024-12") == _v(
            epfo, f"invest.{sch}.total.current", "2024-03-31", "2026-02")
    # exempted establishments: gross - redemption = net (the category rows do not add up; issues file)
    assert _v(epfo, "exempted.total_gross.current", "2023-24") - _v(epfo, "exempted.redemption.current", "2023-24") == pytest.approx(
        _v(epfo, "exempted.total_net.current", "2023-24"), abs=0.01)


def test_epfo_revisions(epfo):
    """AR 2024-25 revises exactly one 2020-21..2023-24 figure that AR 2023-24 printed: EPF contributions
    2023-24, +7,291.23 cr (logged). Everything else overlapping is identical, including the interest rates."""
    rev = checks.compare_vintages(epfo, "2024-12", "2026-02").filter(pl.col("change") == "revised")
    assert rev.select("series_id", "period").rows() == [("fiveyear.epf_contribution.current", "2023-24")]
    assert rev["revision"][0] == pytest.approx(7291.23, abs=0.01)


def test_epfo_ranges(epfo):
    money = epfo.filter(pl.col("unit") == "INR_crore")
    checks.assert_no_rows(checks.check_range(money, lo=0), "EPFO money non-negative")
    checks.assert_no_rows(checks.check_range(epfo.filter(pl.col("unit") == "percent"), lo=3, hi=12.5), "EPF rates 3-12%")
    flows = money.filter(pl.col("series_id").str.starts_with("fiveyear.") & (pl.col("vintage") == "2026-02"))
    # EDLI payments 2020-21 (854.91) to 2021-22 (2,025.32): COVID death-claim surge, the one flagged break
    v = checks.check_continuity(flows, max_rel_change=0.35)
    assert v.select("series_id", "to_period").rows() == [("fiveyear.edli_payment.current", "2021-22")], v


# ------------------------------------------------------------------------------------------------
# PFRDA
# ------------------------------------------------------------------------------------------------

# A2 (Mar-2024): CG 3,22,215.21; SG 5,82,672.76; corporate 1,66,729.01; APY 35,647.67.
# M6 (Mar-2024): AUM 11,72,651.74; G-sec 6,35,652.01; equity 2,21,738.83; corporate bonds 2,78,492.31.
# M6 Aug-2026 AUM 18,22,758.49 (registry). A5 2023-24 Tier-II all citizen 868.55.
def test_pfrda_anchors(nps):
    assert _v(nps, "a2.aum_tier1.central_govt.current", "2024-03-31") == pytest.approx(322215.21)
    assert _v(nps, "a2.aum_tier1.state_govt.current", "2024-03-31") == pytest.approx(582672.76)
    assert _v(nps, "a2.aum_tier1.corporate.current", "2024-03-31") == pytest.approx(166729.01)
    assert _v(nps, "a2.aum_tier1.apy.current", "2024-03-31") == pytest.approx(35647.67)
    assert _v(nps, "m6.aum_by_asset_class.total.current", "2024-03-31") == pytest.approx(1172651.74)
    assert _v(nps, "m6.aum_by_asset_class.gsec.current", "2024-03-31") == pytest.approx(635652.01)
    assert _v(nps, "m6.aum_by_asset_class.equity.current", "2024-03-31") == pytest.approx(221738.83)
    assert _v(nps, "m6.aum_by_asset_class.total.current", "2026-08-31") == pytest.approx(1822758.49, abs=0.01)
    assert _v(nps, "a5.tier2_contribution.all_citizen.current", "2023-24") == pytest.approx(868.55)
    # derived annual contribution = difference of the published M4 end-March levels
    for sec in ("central_govt", "state_govt", "corporate"):
        d = _v(nps, f"m4d.annual_contribution.{sec}.current", "2023-24")
        assert d == pytest.approx(_v(nps, f"m4.cumulative_contribution.{sec}.current", "2024-03-31")
                                  - _v(nps, f"m4.cumulative_contribution.{sec}.current", "2023-03-31"))
    der = nps.filter(pl.col("series_id").str.starts_with("m4d."))
    assert set(der["status"]) == {"derived"} and der["period"].max() == "2024-25"


def test_pfrda_identities(nps):
    m6 = nps.filter(pl.col("series_id").str.starts_with("m6."))
    parts = [s for s in m6["series_id"].unique().to_list() if ".total." not in s]
    checks.assert_no_rows(_sum_present(m6, "m6.aum_by_asset_class.total.current", parts, abs_tol=0.05), "M6 asset classes")
    # M2 sector AUM summed across all sector columns equals M6 total AUM within 0.1% (within 0.0025% since 2020)
    m2 = (nps.filter(pl.col("series_id").str.starts_with("m2."))
          .group_by("period", maintain_order=True).agg(pl.col("value").sum().alias("m2")))
    j = m2.join(m6.filter(pl.col("series_id") == "m6.aum_by_asset_class.total.current").select("period", "value"), on="period")
    assert j.height > 100
    # Feb-Jun 2026 excluded: M2 departs from M6 (0.2% in Feb-Mar, 1.3% from April as the CG sector drops;
    # the same Feb-2026 break shows in M4; logged in the issues file)
    j = j.filter(pl.col("period") < "2026-02-01")
    bad = j.filter(((pl.col("m2") / pl.col("value")) - 1).abs() > 0.001)
    assert not bad.height, bad
    bad = j.filter((pl.col("period") >= "2020-03-31") & (((pl.col("m2") / pl.col("value")) - 1).abs() > 2.5e-5))
    assert not bad.height, bad
    # A2 (Tier-I, annual) equals M2 within Rs 1 cr for CG, SG and corporate at end-March (other sectors differ: Tier-I only)
    for sec in ("central_govt", "state_govt", "corporate"):
        for per in ("2022-03-31", "2023-03-31", "2024-03-31", "2025-03-31"):
            assert _v(nps, f"a2.aum_tier1.{sec}.current", per) == pytest.approx(_v(nps, f"m2.aum.{sec}.current", per), abs=1.0)


def test_pfrda_ranges_and_continuity(nps):
    checks.assert_no_rows(checks.check_range(nps.filter(pl.col("status") == "official"), lo=0), "PFRDA levels non-negative")
    checks.assert_no_rows(checks.check_range(nps.filter(pl.col("series_id").str.starts_with("m4d.")), lo=0),
                          "derived annual contributions non-negative")
    tot = nps.filter(pl.col("series_id") == "m6.aum_by_asset_class.total.current")
    checks.assert_no_rows(checks.check_continuity(tot.filter(pl.col("period") >= "2012-01-01"), max_rel_change=0.1),
                          "M6 total AUM month-on-month > 10%")
    # M4 is read as a cumulative stock: it never falls before Feb-2026 in the big sectors (the Feb-2026 break is logged)
    for sec in ("central_govt", "state_govt", "corporate", "all_citizen"):
        s = nps.filter((pl.col("series_id") == f"m4.cumulative_contribution.{sec}.current") & (pl.col("period") < "2026-02-01")).sort("period")
        assert (s["value"].diff().drop_nulls() >= 0).all(), sec


# ------------------------------------------------------------------------------------------------
# SEBI Handbook 2025-26
# ------------------------------------------------------------------------------------------------

# T14 (2025-26): equity public 2,34,872.28; QIP+pref 2,16,072.09; debt public 11,342.75; debt PP
# 8,99,735.57; REIT/InvIT 30,325.66; total 13,92,348.34 (3,828 issues) (verify/markets_finsector.md).
# T14 2023-24 total 10,93,166.66. T1 2023-24 main-board IPOs 76 issues, 61,859.85 cr.
def test_sebi_primary_anchors(primary):
    assert _v(primary, "t14.total_amount.current", "2025-26") == pytest.approx(1392348.34, abs=0.01)
    assert _v(primary, "t14.total_issues", "2025-26") == 3828
    assert _v(primary, "t14.debt_private_placement_amount.current", "2025-26") == pytest.approx(899735.57, abs=0.01)
    assert _v(primary, "t14.total_amount.current", "2023-24") == pytest.approx(1093166.66, abs=0.01)
    assert _v(primary, "t14.debt_private_placement_amount.current", "2023-24") == pytest.approx(837755.55, abs=0.01)
    assert _v(primary, "t1.ipo_mainboard_issues", "2023-24") == 76
    assert _v(primary, "t1.ipo_mainboard_amount.current", "2023-24") == pytest.approx(61859.85, abs=0.01)
    assert _v(primary, "t7.amount.current", "2023-24") == 19168
    assert _v(primary, "t8.total_issues", "2025-26") == 1924


def test_sebi_primary_identities(primary):
    ci = checks.check_identity
    checks.assert_no_rows(ci(primary, "t1.total_amount.current", ["t1.ipo_total_amount.current", "t1.fpo_amount.current",
                                                                  "t1.rights_amount.current"]), "T1 total")
    checks.assert_no_rows(ci(primary, "t1.ipo_total_amount.current", ["t1.ipo_mainboard_amount.current", "t1.ipo_sme_amount.current"]),
                          "T1 IPOs")
    checks.assert_no_rows(ci(primary, "t14.total_amount.current",
                             [f"t14.{c}_amount.current" for c in ("equity_public", "equity_qip_pref", "debt_public",
                                                                  "debt_private_placement", "reit_invit")]), "T14 total")
    checks.assert_no_rows(ci(primary, "t14.total_issues", [f"t14.{c}_issues" for c in ("equity_public", "equity_qip_pref",
                                                                                         "debt_public", "debt_private_placement",
                                                                                         "reit_invit")]), "T14 issues")
    # T8 exchange split: publisher rounding up to Rs 2 cr (2022-23)
    checks.assert_no_rows(ci(primary, "t8.total_amount.current", ["t8.bse_only_amount.current", "t8.nse_only_amount.current",
                                                                  "t8.both_amount.current"], abs_tol=2.5), "T8 total")
    checks.assert_no_rows(_sum_present(primary, "t13.total_amount.current", ["t13.reit_listed_amount.current",
                                                                             "t13.invit_public_amount.current",
                                                                             "t13.invit_private_amount.current"]), "T13 total")
    # T14 columns repeat the detail tables
    checks.assert_no_rows(ci(primary, "t14.equity_public_amount.current", ["t1.total_amount.current"]), "T14 = T1")
    checks.assert_no_rows(ci(primary, "t14.debt_public_amount.current", ["t7.amount.current"]), "T14 = T7")
    checks.assert_no_rows(ci(primary, "t14.debt_private_placement_amount.current", ["t8.total_amount.current"], abs_tol=1.1),
                          "T14 = T8")
    d = primary.filter(pl.col("period") >= "2017-18")  # T13 starts in 2017-18 (earlier: 'NA' / blank, T14 prints 0)
    checks.assert_no_rows(ci(d, "t14.reit_invit_amount.current", ["t13.total_amount.current"]), "T14 = T13")


# T11 (31 Mar 2024): outstanding corporate bonds 47,22,009.87 (FC listed 23,31,582.12; NFC listed
# 14,67,026.85); 31 Mar 2026 59,09,146.74 (verify notes). T23: BSE mcap end 2023-24 3,86,97,099.77.
def test_sebi_bonds_equity(bonds):
    assert _v(bonds, "t11.outstanding.all.all_corporations.current", "2024-03-31") == pytest.approx(4722009.87)
    assert _v(bonds, "t11.outstanding.listed.fc.current", "2024-03-31") == pytest.approx(2331582.12)
    assert _v(bonds, "t11.outstanding.listed.nfc.current", "2024-03-31") == pytest.approx(1467026.85)
    assert _v(bonds, "t11.outstanding.all.all_corporations.current", "2026-03-31") == pytest.approx(5909146.74, abs=0.01)
    assert _v(bonds, "t11.issuers", "2024-03-31") == 4178
    assert _v(bonds, "t23.market_cap.bse.current", "2024-03-31") == pytest.approx(38697099.77)
    ci = checks.check_identity
    for inst in ("fc", "nfc"):
        checks.assert_no_rows(ci(bonds, f"t11.outstanding.all.{inst}.current", [f"t11.outstanding.listed.{inst}.current",
                                                                               f"t11.outstanding.unlisted.{inst}.current"]), f"T11 {inst}")
    checks.assert_no_rows(ci(bonds, "t11.outstanding.all.all_corporations.current", ["t11.outstanding.all.fc.current",
                                                                                   "t11.outstanding.all.nfc.current"]), "T11 total")
    # sector totals: the only break > 25% is the 2024-25 reclassification (FC +36%; listed NFC bonds fall 28%,
    # listed FC rise 37%: registry quirk, logged). The listed/unlisted sub-series are more volatile and not checked.
    tots = bonds.filter(pl.col("series_id").str.starts_with("t11.outstanding.all.") & (pl.col("period") >= "2016-03-31"))
    v = checks.check_continuity(tots, max_rel_change=0.25)
    assert v.select("series_id", "to_period").rows() == [("t11.outstanding.all.fc.current", "2025-03-31")], v
    v = checks.check_continuity(bonds.filter(pl.col("series_id") == "t11.outstanding.listed.nfc.current"), max_rel_change=0.25)
    assert ("t11.outstanding.listed.nfc.current", "2025-03-31") in v.select("series_id", "to_period").rows()


# T58 (2023-24, Source RBI): gross FDI inflows US$71,302 mn (Rs 5,903.96 bn); net FDI US$10,152 mn;
# net portfolio US$44,081 mn (Rs 3,648.04 bn). T59: FPI net 2023-24 Rs 3,39,064.62 cr (US$41,044.09 mn);
# 2025-26 -1,52,691.03 cr. T60 2023-24 equity 2,08,212; debt 1,21,059. T63/T62: FPI AUC 31 Mar 2024
# 69,53,987.69 cr. T72 (Mar-2026) total 73,73,376.98; corporates 27,03,761.64.
def test_sebi_foreign_anchors(foreign):
    assert _v(foreign, "t58.fdi_gross_inflows.usd", "2023-24") == 71302
    assert _v(foreign, "t58.fdi_gross_inflows.current", "2023-24") == pytest.approx(590396.0)  # 5,903.96 bn x 100
    assert _v(foreign, "t58.fdi_net.usd", "2023-24") == 10152
    assert _v(foreign, "t58.portfolio_net.usd", "2023-24") == 44081
    assert _v(foreign, "t59.net_investment.current", "2023-24") == pytest.approx(339064.62)
    assert _v(foreign, "t59.net_investment.usd", "2023-24") == pytest.approx(41044.09)
    assert _v(foreign, "t59.net_investment.current", "2025-26") == pytest.approx(-152691.03)
    assert _v(foreign, "t60.net_investment.equity.current", "2023-24") == 208212
    assert _v(foreign, "t60.net_investment.debt_general.current", "2023-24") == 121059
    assert _v(foreign, "t62.assets_under_custody.fpi_fii_sa.current", "2024-03-31") == pytest.approx(6953987.69)
    assert _v(foreign, "t63.assets_under_custody.category_i.equity.current", "2024-03-31") == 6076800
    prov = checks.load_provenance(UNIT)
    t58 = prov.filter((pl.col("table_id") == "Table 58") & (pl.col("unit_as_published") == "Rs billion"))
    assert t58.height == 1 and t58["conversion"][0] == "INR_billion -> INR_crore: x 100"


def test_sebi_foreign_identities(foreign):
    ci = checks.check_identity
    for sfx in ("current", "usd"):
        checks.assert_no_rows(ci(foreign, f"t58.fdi_direct_investment_to_india.{sfx}",
                                 {f"t58.fdi_gross_inflows.{sfx}": 1, f"t58.fdi_repatriation.{sfx}": -1}), f"T58 FDI to India {sfx}")
        checks.assert_no_rows(ci(foreign, f"t58.fdi_net.{sfx}", {f"t58.fdi_direct_investment_to_india.{sfx}": 1,
                                                                 f"t58.fdi_by_india.{sfx}": -1}), f"T58 net FDI {sfx}")
        checks.assert_no_rows(ci(foreign, f"t58.total_foreign_investment_net.{sfx}", [f"t58.fdi_net.{sfx}", f"t58.portfolio_net.{sfx}"]),
                              f"T58 total {sfx}")
    checks.assert_no_rows(ci(foreign, "t59.net_investment.current", {"t59.gross_purchases.current": 1,
                                                                     "t59.gross_sales.current": -1}, abs_tol=2.5), "T59 net")
    instr = [f"t60.net_investment.{i}.current" for i in ("equity", "debt_general", "debt_vrr", "debt_far", "hybrid", "aif_mf")]
    checks.assert_no_rows(_sum_present(foreign, "t60.net_investment.total.current", instr, abs_tol=3.5), "T60 total")  # rounding up to Rs 3 cr
    checks.assert_no_rows(ci(foreign, "t60.net_investment.total.current", ["t59.net_investment.current"], abs_tol=3),
                          "T60 total = T59 net (NSDL)")
    cats = [s for s in foreign["series_id"].unique().to_list() if s.startswith("t62.assets_under_custody.") and ".total." not in s]
    checks.assert_no_rows(ci(foreign, "t62.assets_under_custody.total.current", cats, abs_tol=2), "T62 total")
    for c in ("category_i", "category_ii", "category_iii"):
        parts = [f"t63.assets_under_custody.{c}.{i}.current" for i in ("equity", "debt", "debt_vrr", "hybrid")]
        checks.assert_no_rows(_sum_present(foreign, f"t63.assets_under_custody.{c}.total.current", parts, abs_tol=5), f"T63 {c}")
    # T63 carries no unit caption; Rs crore is inferred from its agreement with T62 (Rs crore):
    # equal within Rs 2 cr in 2016-2019 and 2024, within 0.1% in 2015 and 2020-2023 (2025 and 2026 diverge: logged)
    for per in ("2016-03-31", "2017-03-31", "2018-03-31", "2019-03-31", "2024-03-31"):
        tot = sum(_v(foreign, f"t63.assets_under_custody.{c}.total.current", per) for c in ("category_i", "category_ii", "category_iii"))
        assert tot == pytest.approx(_v(foreign, "t62.assets_under_custody.fpi_fii_sa.current", per), abs=2.5), per
    for per in ("2015-03-31", "2020-03-31", "2021-03-31", "2022-03-31", "2023-03-31"):
        tot = sum(_v(foreign, f"t63.assets_under_custody.{c}.total.current", per) for c in ("category_i", "category_ii", "category_iii"))
        assert tot == pytest.approx(_v(foreign, "t62.assets_under_custody.fpi_fii_sa.current", per), rel=1e-3), per


# T64 (2023-24): gross mobilisation 1,14,48,214.79; net inflow 3,55,340.47; assets at end 53,40,194.67;
# 2025-26 net inflow 7,36,020.88 and AUM 73,73,376.97 (Bulletin T60 matches). T70 2023-24 equity net
# purchase 2,00,732.11. T69 SIP AUM end 2023-24 10,62,058.79. T72 Mar-2026 corporates 27,03,761.64.
def test_sebi_mf_anchors(mf):
    assert _v(mf, "t64.gross_mobilisation.mf_all.current", "2023-24") == pytest.approx(11448214.79, abs=0.01)
    assert _v(mf, "t64.net_inflow.mf_all.current", "2023-24") == pytest.approx(355340.47, abs=0.01)
    assert _v(mf, "t64.assets_end_of_period.mf_all.current", "2024-03-31") == pytest.approx(5340194.67, abs=0.01)
    assert _v(mf, "t64.net_inflow.mf_all.current", "2025-26") == pytest.approx(736020.88, abs=0.01)
    assert _v(mf, "t64.assets_end_of_period.mf_all.current", "2026-03-31") == pytest.approx(7373376.97, abs=0.01)
    assert _v(mf, "t70.net_purchase.equity.current", "2023-24") == pytest.approx(200732.11)
    assert _v(mf, "t69.sip_aum_end.current", "2024-03-31") == pytest.approx(1062058.79, abs=0.01)
    assert _v(mf, "t69.sips_closing", "2024-03-31") == pytest.approx(831.09761e5, abs=1)
    assert _v(mf, "t72.aum.corporates.current", "2026-03-31") == pytest.approx(2703761.64, abs=0.01)
    assert _v(mf, "t72.aum.total.current", "2026-03-31") == pytest.approx(7373376.98, abs=0.01)


def test_sebi_mf_identities(mf):
    ci = checks.check_identity
    for m in ("gross_mobilisation", "redemption", "net_inflow"):
        checks.assert_no_rows(ci(mf, f"t64.{m}.mf_all.current", [f"t64.{m}.mf_private.current", f"t64.{m}.mf_public.current"]),
                              f"T64 {m}")
    # net = gross - redemption, except 2017-18 (published net 2,71,796.60 vs 2,82,723.68; issues file)
    v = ci(mf, "t64.net_inflow.mf_all.current", {"t64.gross_mobilisation.mf_all.current": 1, "t64.redemption.mf_all.current": -1})
    assert v["period"].to_list() == ["2017-18"], v
    # T70 net = purchase - sales; published exceptions logged in the issues file
    for i, bad in (("equity", ["2013-14"]), ("debt", ["2013-14", "2015-16", "2018-19", "2022-23"]),
                   ("total", ["2013-14", "2015-16", "2018-19", "2022-23"])):
        v = ci(mf, f"t70.net_purchase.{i}.current", {f"t70.gross_purchase.{i}.current": 1, f"t70.gross_sales.{i}.current": -1})
        assert v["period"].to_list() == bad, (i, v)
    # T72 holder split adds up (exact since Dec-2019; a few early months carry publisher differences up to 0.6%)
    v = ci(mf, "t72.aum.total.current", [f"t72.aum.{h}.current" for h in ("corporates", "hnis", "retail", "banks")])
    assert (v["period"] < "2019-12-01").all() and (v["diff"].abs() / v["total"]).max() < 0.006, v
    # T64 end-of-year AUM = T72 March AUM (same AMFI data) from March 2021; earlier years differ by 0.2-0.6%
    # (T64 note: net assets of funds of funds are excluded)
    a = mf.filter(pl.col("series_id") == "t64.assets_end_of_period.mf_all.current").select("period", "value")
    b = mf.filter(pl.col("series_id") == "t72.aum.total.current").select("period", pl.col("value").alias("t72"))
    j = a.join(b, on="period").filter(pl.col("period") >= "2021-03-31")
    assert j.height == 6 and ((j["value"] - j["t72"]).abs() < 1.5).all(), j


def test_sebi_ranges(primary, bonds, foreign, mf):
    for df in (primary, bonds, mf.filter(~pl.col("item_code").is_in(["net_inflow", "net_purchase"]))):
        checks.assert_no_rows(checks.check_range(df, lo=0), "SEBI non-negative levels")
    counts = pl.concat([primary, bonds, mf], how="diagonal_relaxed").filter(pl.col("unit") == "count")
    assert (counts["value"] == counts["value"].round(0)).all() or counts.filter(pl.col("series_id").str.starts_with("t69")).height
    # FPI net flows swing sign; sanity bound: |net| < Rs 5 lakh crore a year
    checks.assert_no_rows(checks.check_range(foreign.filter(pl.col("item_code") == "net_investment") .filter(pl.col("unit") == "INR_crore"),
                                             lo=-500000, hi=500000), "FPI net flows bound")


# ------------------------------------------------------------------------------------------------
# unit-level checks
# ------------------------------------------------------------------------------------------------


def test_sebi_links_come_from_contents_pdf():
    raw = pinned_raw(Layout.default(), UNIT, "sebi_handbook_statistics", "hbs2025_26_contents.pdf")
    links = U.sebi_links(raw.path)
    assert len(links) == 153  # the contents PDF's 153 table links (recon)
    for t, kind in U.SEBI_TABLES.items():
        assert (t, kind) in links


def test_vintages_and_stages(summ, epfo, primary, nps):
    assert set(summ["vintage"]) == {"2026-02-03"}
    assert set(primary["vintage"]) == {"2026-08-17"}
    assert set(epfo["vintage"]) == {"2024-12", "2026-02"}
    assert all(v.startswith("2026-09-") for v in nps["vintage"].unique().to_list())
    for df in (summ, primary, epfo, nps):
        assert set(df["price_basis"]) <= {"current", "n/a"}
        money = df.filter(pl.col("unit").is_in(["INR_crore", "USD_million"]))
        assert set(money["price_basis"]) == {"current"}


def test_sign_conventions(life, foreign, mf, epfo):
    """Signs are kept as published: outflows and deductions are negative where the publisher prints them so."""
    # T24: reinsurance ceded and losses on sale are printed negative (bracketed) and summed into TOTAL (A)
    assert _v(life, "t24.reinsurance_ceded.insurers_life.current", "2023-24") == pytest.approx(-8259.484357, abs=1e-5)
    assert _v(life, "t24.inv_loss_on_sale.insurers_life.current", "2023-24") < 0
    # FPI: net outflow years are negative (T59 2025-26 -1,52,691.03 cr; T58 net portfolio 2025-26 -US$17,792 mn)
    assert _v(foreign, "t59.net_investment.current", "2025-26") < 0
    assert _v(foreign, "t58.portfolio_net.usd", "2025-26") == pytest.approx(-17792.019982, abs=1e-5)
    assert _v(foreign, "t60.net_investment.equity.current", "2024-25") == -127041
    # MF: debt net sales on exchanges are negative (T70 2023-24 debt -1,95,777.35)
    assert _v(mf, "t70.net_purchase.debt.current", "2023-24") == pytest.approx(-195777.35)
    # EPFO: payments are positive amounts (outflows are separate series, not negative contributions)
    assert _v(epfo, "app5i.total_payment.current", "2023-24") > 0


# ------------------------------------------------------------------------------------------------
# Verifier follow-ups (2026-09-29)
# ------------------------------------------------------------------------------------------------

# PFRDA Table M7 (SG sector, 'Total' row): Mar-2024 total 9,718.10 = employer 5,404.46 + employee 4,313.68;
# subscribers 65,96,356 at end-March 2024. FY 2023-24 sum 77,599.18.
def test_pfrda_m7_sg_confirms_m4_reading(nps):
    sg = _load("pfrda_sg")
    assert _v(sg, "m7.contribution_total.state_govt.current", "2024-03") == pytest.approx(9718.10)
    assert _v(sg, "m7.contribution_employer.state_govt.current", "2024-03") == pytest.approx(5404.46)
    assert _v(sg, "m7.contribution_employee.state_govt.current", "2024-03") == pytest.approx(4313.68)
    assert _v(sg, "m7.subscribers.state_govt", "2024-03-31") == 6596356
    assert _v(sg, "m7d.annual_contribution_total.state_govt.current", "2023-24") == pytest.approx(77599.18, abs=0.005)
    # total = employer + employee (rounding: within Rs 0.1 crore)
    checks.assert_no_rows(checks.check_identity(sg.filter(pl.col("status") == "official"),
                                                "m7.contribution_total.state_govt.current",
                                                ["m7.contribution_employer.state_govt.current",
                                                 "m7.contribution_employee.state_govt.current"], abs_tol=0.11), "M7 total")
    # M7 FY sums equal the M4 end-March differences (the reading of M4 as cumulative): 2023-24 within 0.05;
    # 2022-23 and 2024-25 carry an offsetting timing difference of about 11.8 cr; others within Rs 0.3 crore
    for y in range(2015, 2025):
        f = f"{y}-{(y + 1) % 100:02d}"
        a = _v(sg, "m7d.annual_contribution_total.state_govt.current", f)
        b = _v(nps, "m4d.annual_contribution.state_govt.current", f)
        assert abs(a - b) < (12.0 if f in ("2022-23", "2024-25") else 0.3), (f, a, b)
    assert abs(_v(sg, "m7d.annual_contribution_total.state_govt.current", "2023-24")
               - _v(nps, "m4d.annual_contribution.state_govt.current", "2023-24")) < 0.05
    # derived FY sums only for complete FYs (Dec-2014..Jun-2026 published -> 2015-16..2025-26)
    d = sg.filter(pl.col("series_id") == "m7d.annual_contribution_total.state_govt.current")
    assert d["period"].min() == "2015-16" and d["period"].max() == "2025-26" and set(d["status"]) == {"derived"}


def test_sebi_t69_opening_count_is_a_stock(mf):
    o = mf.filter(pl.col("series_id") == "t69.sips_existing_beginning")
    assert set(o["stock_flow"]) == {"stock"} and set(o["period_type"]) == {"date"}
    assert o["period"].min() == "2019-03-31" and o["period"].max() == "2025-03-31"
    # from 2023-24 the opening count equals the previous block's closing count
    for per in ("2023-03-31", "2024-03-31", "2025-03-31"):
        assert _v(mf, "t69.sips_existing_beginning", per) == _v(mf, "t69.sips_closing", per)


def test_provenance_notes_from_verifier():
    prov = checks.load_provenance(UNIT)
    txt = " ".join(n for n in prov["notes"].to_list() if n)
    assert "7,320.22" in txt and "Past Accumulation" in txt  # EPFO AR 2024-25 past accumulations
    assert "(except in case of FDI by India)" in txt  # SEBI T58 sign convention
    assert "398.15" in txt  # LIC out-of-India premium (IRDAI T24 note 3)
    assert "gap is in the publication" in txt  # EPFO para 5.22
    m4 = checks.load_dataset(UNIT, f"{UNIT}_pfrda_nps").filter(pl.col("series_id").str.starts_with("m4."))
    assert not m4["item_label"].str.contains("cumulative").any()


def _epfo_notes(vintage, prefix):
    epfo = _load("epfo_ar")
    ids = epfo.filter((pl.col("vintage") == vintage) & pl.col("series_id").str.starts_with(prefix))["prov_id"].unique()
    prov = checks.load_provenance(UNIT).filter(pl.col("prov_id").is_in(ids.to_list()))
    return [n or "" for n in prov["notes"].to_list()]


def test_epfo_central_lines_and_transfers_documented():
    # AR 2024-25 App. 5(i), PDF p.236: central lines above 'Total' (CPPS, pension-disbursement adjustment,
    # head-office remittance adjustment, past accumulation); the notes state them and the zonal caveat.
    for pfx in ("app5i.", "fiveyear."):
        (n,) = _epfo_notes("2026-02", pfx)
        for s in ("CPPS 6813.22", "381.88", "0.19", "20,768.29", "27,581.53", "Centralised Pension Payment System",
                  "subtract 7,320.22", "upper bound", "2,50,812.70", "not published"):
            assert s in n, (pfx, s)
    (n,) = _epfo_notes("2026-02", "para54.")
    assert "2,50,812.70" in n and "upper bound" in n and "CPPS" not in n  # para 5.4 has contributions only
    (n,) = _epfo_notes("2024-12", "app5i.")
    assert "no central line" in n and "7,320.22" not in n


def test_epfo_app5i_build_check_is_strict():
    # the build asserts Total = 22 zones + central lines; a changed figure or a missing line must fail
    import pypdf

    from pipeline.ingest.finsector_markets import epfo as E

    for rep in (E.AR2324, E.AR2425):
        raw = pinned_raw(Layout.default(), UNIT, E.SRC, rep.raw)
        t = E._text(pypdf.PdfReader(raw.path), rep, "app5i")
        m = E._one(r"^Total " + " +".join([E.AMOUNT] * 8) + r"\s*$", t, "total")
        total = [E._amount(v) for v in m.groups()]
        E._check_app5i_lines(rep, t, total)  # passes as published
        with pytest.raises(ValueError, match="Total != zones"):
            E._check_app5i_lines(rep, t, [total[0]] + total[1:3] + [total[3] + 1.0] + total[4:])
    t2425 = E._text(pypdf.PdfReader(pinned_raw(Layout.default(), UNIT, E.SRC, E.AR2425.raw).path), E.AR2425, "app5i")
    with pytest.raises(ValueError, match="central line 6813.22"):
        E._check_app5i_lines(E.AR2425, t2425.replace("CPPS 6813.22", "CPPS 6813.20"), [0.0] * 8)


# EPS outgo table (verifier V13): AR 2023-24 para 2.15 'EPS Payments' (PDF p.39): 2023-24 Pension Disbursed
# 15,130.68, Withdrawal Benefits 7,908.25, Total 23,038.94; 2019-20 total 18,117.51. AR 2024-25 para 2.16 Table 5
# (PDF pp.40-41): 2024-25 18,957.86 + 9,005.90 = 27,963.76 (note: Balance Sheet 27,963.41, Life Assurance Benefit 0.35).
def test_epfo_eps_outgo_anchors_and_identities(epfo):
    out = _load("epfo_eps_outgo")
    assert out.height == 30
    p, w, t = (f"eps_outgo.{c}.current" for c in ("pension_disbursed", "withdrawal_benefits", "total_outgo"))
    assert _v(out, p, "2023-24", "2024-12") == pytest.approx(15130.68)
    assert _v(out, w, "2023-24", "2024-12") == pytest.approx(7908.25)
    assert _v(out, t, "2019-20", "2024-12") == pytest.approx(18117.51)
    assert _v(out, p, "2024-25", "2026-02") == pytest.approx(18957.86)
    assert _v(out, w, "2024-25", "2026-02") == pytest.approx(9005.90)
    assert _v(out, t, "2024-25", "2026-02") == pytest.approx(27963.76)
    checks.assert_no_rows(checks.check_identity(out, t, [p, w], abs_tol=0.015), "EPS outgo = pensions + withdrawals")
    rev = checks.compare_vintages(out, "2024-12", "2026-02")
    assert rev.filter(pl.col("change") == "revised").height == 0  # identical in the overlap 2020-21..2023-24
    # the documented excess of the EPS payment over the outgo total (notes, issue -37), both reports
    gaps = {y: round(_v(epfo, "fiveyear.eps_payment.current", y, "2026-02") - _v(out, t, y, "2026-02"), 2)
            for y in ("2020-21", "2021-22", "2022-23", "2023-24", "2024-25")}
    assert gaps == {"2020-21": 38.03, "2021-22": 382.46, "2022-23": 315.97, "2023-24": 371.23, "2024-25": -0.35}
    assert round(_v(epfo, "app5i.eps_payment.current", "2023-24", "2024-12") - _v(out, t, "2023-24", "2024-12"), 2) == 371.23
    stage = out.filter(pl.col("period") == "2024-25")["estimate_stage"].unique().to_list()
    assert stage == ["Unaudited"]


def test_epfo_eps_payment_notes_split_pensions_and_withdrawals():
    # V13: the EPS payment is pensions + withdrawal benefits; the notes cite Table 5 and no longer call it 'pensions'
    for pfx in ("app5i.", "fiveyear."):
        (n,) = _epfo_notes("2026-02", pfx)
        for s in ("18,957.86", "9,005.90", "27,963.76", "Life Assurance Benefit", "withdrawal benefits", "19.4%",
                  "38-382 cr", "371.23"):
            assert s in n, (pfx, s)
        assert "EPS pensions paid in 2024-25 lie between" not in n and "19.5%" not in n, pfx
    (n,) = _epfo_notes("2024-12", "app5i.")
    assert "15,130.68" in n and "7,908.25" in n and "371.23" in n
    prov = checks.load_provenance(UNIT)
    ids = _load("epfo_eps_outgo")["prov_id"].unique().to_list()
    notes = prov.filter(pl.col("prov_id").is_in(ids))["notes"].to_list()
    assert len(notes) == 2 and all("382.46" in x and "has not rendered service eligible for pension" in x for x in notes)
    assert sum("Balance Sheet (Rs. 27,963.41)" in x for x in notes) == 1


def test_epfo_app5i_government_share_excluded_documented():
    # V14: App. 5(i) EPS contribution = para 5.4 employers' share; the Government's share is in neither column
    for vin, gov in (("2024-12", "9,356.48"), ("2026-02", "10,049.70")):
        (n,) = _epfo_notes(vin, "app5i.")
        assert "Government's share" in n and "exclude" in n and gov in n, vin
    (n,) = _epfo_notes("2026-02", "fiveyear.")
    assert "10,049.70" in n


def test_epfo_eps_build_checks_are_strict():
    from pipeline.ingest.finsector_markets import epfo as E

    rows = [{"series_id": "fiveyear.eps_payment.current", "period": y, "value": v}
            for y, v in (("2020-21", 20417.0), ("2021-22", 21304.6), ("2022-23", 22112.82), ("2023-24", 23410.17),
                         ("2024-25", 27963.41))]
    outgo = {"2020-21": 20378.97, "2021-22": 20922.14, "2022-23": 21796.85, "2023-24": 23038.94, "2024-25": 27963.76}
    E._check_eps_outgo(E.AR2425, rows, outgo)  # as published
    with pytest.raises(ValueError, match="documented excess"):
        E._check_eps_outgo(E.AR2425, rows, {**outgo, "2023-24": 23410.17})
    base = {"app5i.eps_contribution.current": 62423.93, "para54.eps_contribution_employer.current": 62423.93,
            "para54.eps_contribution_government.current": 9356.48, "app5i.epf_contribution.current": 226198.57,
            "app5i.edli_contribution.current": 3358.10, "app5i.total_contribution.current": 291980.60}
    mk = lambda d: [{"series_id": k, "period": "2023-24", "value": v} for k, v in d.items()]  # noqa: E731
    E._check_govt_share(E.AR2324, mk(base))
    with pytest.raises(ValueError, match="employers' share only"):
        E._check_govt_share(E.AR2324, mk({**base, "app5i.total_contribution.current": 291980.60 + 9356.48}))


def test_terms_restricted_sources_are_refused_in_code():
    # NSDL FPI Monitor and AMFI: terms forbid reproduction / derivative works (finsector_markets-1, -2). The
    # registry still says access.requires: none (orchestrator follow-up), so the refusal must come from policy.py.
    from pipeline.core import policy
    from pipeline.core.registry import get_source

    for sid in ("nsdl_fpi_monitor", "amfi_monthly_quarterly"):
        assert sid not in U.SOURCES
        entry = get_source(sid)
        assert policy.source_refusal(sid, entry), sid
        for url in [entry["urls"]["landing"], *entry["urls"]["data"]]:
            assert policy.url_refusal(sid, entry, url), url
    assert policy.denied_host("https://portal.amfiindia.com/spages/x.xls")
    assert policy.denied_host("https://www.fpi.nsdl.co.in/web/Reports/Latest.aspx")
