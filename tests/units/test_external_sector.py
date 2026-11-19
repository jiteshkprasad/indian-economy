"""Value tests for the external_sector unit.

Anchor values are read off the source pages themselves (the pinned HTML on www.rbi.org.in):
- HBS 2025-26 (31 Jul 2026): T126/T127 BPM6 BoP, T125 old-format BoP, T131 invisibles, T133/T205
  exchange rates, T139-T142 NRI deposits, T143 foreign investment, T144 reserves, T145/T146 debt,
  T197/T198 quarterly BoP, T200 quarterly IIP.
- HBS 2024-25 (29 Aug 2025): T197 quarterly BoP (2023-24 quarters), T199 quarterly IIP.
- ECB data for April 2023 (ECBUserView Id=235) and Feb/Mar 2024 grand totals; FLA census 2024-25
  (PublicationsView id=23438) and 2023-24 (press release prid=58874);
  remittances survey (Bulletin Id=23260); ITES survey releases prid=61562 and 63625; LRS Bulletin
  tables (Id=22690, 23490, 24281).
The NAS 2026 figures quoted in data/gap_map.csv (V3, V4, R11, R12, R13, R14, R14a) are used as
cross-checks of the 2023-24 BoP values.
"""

from __future__ import annotations

import polars as pl
import pytest

from pipeline.core import checks, geo
from pipeline.ingest import external_sector as U

pytestmark = pytest.mark.quality
UNIT = U.UNIT


def load(name: str) -> pl.DataFrame:
    return checks.load_dataset(UNIT, f"{UNIT}_{name}")


def v(df: pl.DataFrame, sid: str, period: str, vintage: str | None = None) -> float:
    return checks.value(df, sid, period, vintage)


@pytest.fixture(scope="module")
def fx():
    return load("fx_inr_usd")


@pytest.fixture(scope="module")
def bpm6():
    return load("bop_bpm6_annual")


@pytest.fixture(scope="module")
def bpm6q():
    return load("bop_bpm6_quarterly")


@pytest.fixture(scope="module")
def old():
    return load("bop_overall_annual")


@pytest.fixture(scope="module")
def invis():
    return load("invisibles_annual")


def filled_identity(df: pl.DataFrame, total: str, parts: dict[str, float], periods, tol: float = 3.0) -> list:
    """total = sum(parts) where a part printed as '-' (no row) counts as zero; the total must exist."""
    bad = []
    for per in periods:
        sub = df.filter(pl.col("period") == per)
        vals = dict(zip(sub["series_id"].to_list(), sub["value"].to_list(), strict=True))
        s = sum(c * vals.get(p, 0.0) for p, c in parts.items())
        if total not in vals:
            if any(p in vals for p in parts):  # a total printed as '-' must have all parts '-'
                bad.append((per, total, "missing total", s))
            continue
        if abs(vals[total] - s) > tol:
            bad.append((per, total, vals[total], s))
    return bad


# ---------------------------------------------------------------------------------------------
# Exchange rate (the dataset other units DEPEND on)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sid, period, rate",
    [
        ("t133.usd_fy_average", "2023-24", 82.7897),
        ("t133.usd_end_march", "2024-03-31", 83.3739),
        ("t133.usd_fy_average", "2024-25", 84.5756),
        ("t133.usd_end_march", "2025-03-31", 85.5814),
        ("t133.usd_fy_average", "2025-26", 88.3071),
        ("t133.usd_end_march", "2026-03-31", 94.6543),
        ("t133.usd_fy_average", "1986-87", 12.7782),
        ("t205.usd_month_average", "2022-01", 74.4416),
        ("t205.usd_end_month", "2022-01-31", 74.9674),
        ("t205.usd_month_average", "2026-05", 95.5975),
    ],
)
def test_fx_anchor_values(fx, sid, period, rate):
    assert v(fx, sid, period) == pytest.approx(rate, abs=1e-9)


def test_fx_contract_and_ranges(fx):
    assert set(fx["unit"]) == {"INR_per_USD"}
    assert set(fx["series_id"]) == {"t133.usd_fy_average", "t133.usd_end_march", "t205.usd_month_average", "t205.usd_end_month"}
    fy = fx.filter(pl.col("series_id") == "t133.usd_fy_average")
    assert {f"{y}-{(y + 1) % 100:02d}" for y in range(1986, 2026)} == set(fy["period"])
    checks.assert_no_rows(checks.check_range(fx, lo=5, hi=150), "exchange rate out of range")
    checks.assert_no_rows(
        checks.check_continuity(fx.filter(pl.col("period_type") == "month"), max_rel_change=0.05),
        "monthly average moves more than 5% in a month",
    )
    # the only FY jumps above 25% are 1991-92 (official rate, devalued in July 1991) and 1992-93
    # (first year of FEDAI market-based rates; T133 notes 3-4)
    jumps = checks.check_continuity(fy, max_rel_change=0.25)
    assert jumps["to_period"].to_list() == ["1991-92", "1992-93"]


def test_fx_end_march_equals_end_month(fx):
    for y in range(2022, 2027):
        assert v(fx, "t133.usd_end_march", f"{y}-03-31") == v(fx, "t205.usd_end_month", f"{y}-03-31")


def test_fx_phase2_usage_contract(fx):
    """What the Phase 2 guide in docs/phase1/issues/external_sector.md promises about fx_inr_usd."""
    from pipeline.core.units import UnitError, usd_million_to_inr_crore

    # one vintage, one provenance record per source table, one row per (series, period)
    assert set(fx["vintage"]) == {"2026-07-31"}
    assert fx.group_by("series_id").agg(pl.col("prov_id").n_unique())["prov_id"].to_list() == [1, 1, 1, 1]
    assert fx.group_by("series_id", "period").len()["len"].max() == 1
    kinds = dict(fx.select("series_id", "period_type").unique().rows())
    assert kinds == {"t133.usd_fy_average": "fy", "t133.usd_end_march": "date", "t205.usd_month_average": "month", "t205.usd_end_month": "date"}
    # monthly averages: every month Jan 2022..Jun 2026, nothing earlier; no calendar-year series
    months = sorted(fx.filter(pl.col("series_id") == "t205.usd_month_average")["period"])
    assert months == [f"{y}-{m:02d}" for y in range(2022, 2027) for m in range(1, 13)][:54]
    assert "cy" not in set(fx["period_type"])
    # the rates must be filtered to one series: end-March dates sit in both T133 and T205
    usd = pl.DataFrame({"period": ["2024-03-31"], "value": [1000.0], "unit": ["USD_million"]})
    with pytest.raises(UnitError, match="duplicate exchange rates"):
        usd_million_to_inr_crore(usd, fx.filter(pl.col("period_type") == "date"))
    # a US$ 1,000 million FY 2023-24 flow at the FY-average rate 82.7897 = Rs 8,278.97 crore
    rates = fx.filter(pl.col("series_id") == "t133.usd_fy_average")
    out = usd_million_to_inr_crore(pl.DataFrame({"period": ["2023-24"], "value": [1000.0], "unit": ["USD_million"]}), rates)
    assert out["value"][0] == pytest.approx(8278.97)
    assert out["unit"][0] == "INR_crore"
    assert out["fx_prov_id"][0] == rates.filter(pl.col("period") == "2023-24")["prov_id"][0]


def test_fx_fy_average_close_to_mean_of_months(fx):
    m = fx.filter(pl.col("series_id") == "t205.usd_month_average")
    for y in (2022, 2023, 2024, 2025):
        months = [f"{y}-{k:02d}" for k in range(4, 13)] + [f"{y + 1}-{k:02d}" for k in range(1, 4)]
        mean = m.filter(pl.col("period").is_in(months))["value"].mean()
        assert abs(mean - v(fx, "t133.usd_fy_average", f"{y}-{(y + 1) % 100:02d}")) < 0.3


# ---------------------------------------------------------------------------------------------
# BPM6 annual (T126 US$, T127 Rs)
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sid, period, value",
    [
        ("bpm6.inr.bpm6_1.credit.current", "2023-24", 7807138),
        ("bpm6.inr.bpm6_1.debit.current", "2023-24", 8022385),
        ("bpm6.inr.bpm6_1.net.current", "2023-24", -215248),
        ("bpm6.inr.bpm6_1.net.current", "2022-23", -534201),
        ("bpm6.inr.bpm6_1.credit.current", "2025-26", 9530151),
        ("bpm6.inr.bpm6_1_a_b_9.credit.current", "2025-26", 1827090),
        ("bpm6.inr.bpm6_1_c_1_1.credit.current", "2024-25", 1117502),
        ("bpm6.inr.bpm6_3_1_a_1_2.credit.current", "2024-25", 192652),
        ("bpm6.usd.bpm6_1.net.current", "2023-24", -26033),
        ("bpm6.usd.bpm6_1.credit.current", "2025-26", 1077768),
        ("bpm6.usd.bpm6_5.net.current", "2023-24", 402),
    ],
)
def test_bpm6_anchor_values(bpm6, sid, period, value):
    assert v(bpm6, sid, period) == value


def test_bpm6_2023_24_matches_nas_2026(bpm6):
    """Gap-map (NAS 2026 Statement 6.1 / 1.9) values for 2023-24, Rs crore."""
    p = "2023-24"
    assert v(bpm6, "bpm6.inr.bpm6_1_b_1.credit.current", p) == 62344  # V3, NAS 6.1 item 2
    assert v(bpm6, "bpm6.inr.bpm6_1_b_1.debit.current", p) == 30636  # V4, item 7
    assert v(bpm6, "bpm6.inr.bpm6_1_c_1.credit.current", p) == 983128  # R11, item 4
    assert v(bpm6, "bpm6.inr.bpm6_1_c_1.debit.current", p) == 99913  # R12, item 9
    assert v(bpm6, "bpm6.inr.bpm6_1_b_2.credit.current", p) + v(bpm6, "bpm6.inr.bpm6_1_b_3.credit.current", p) == 280907  # R13, item 3
    paid = v(bpm6, "bpm6.inr.bpm6_1_b_2.debit.current", p) + v(bpm6, "bpm6.inr.bpm6_1_b_3.debit.current", p)
    assert abs(paid - 724612) <= 1  # R14, item 8 (7,24,612; BoP components sum to 7,24,611)
    assert v(bpm6, "bpm6.inr.bpm6_3_1_a_1_2.credit.current", p) == 163704  # R14a, NAS 1.9 memo
    # K5: NAS 1.9 net capital inflow 2,08,891; BoP CAD 2,15,248; the gap is government transfers
    gap = -v(bpm6, "bpm6.inr.bpm6_1.net.current", p) - 208891
    assert gap == -v(bpm6, "bpm6.inr.bpm6_1_c_2.net.current", p) == 6357


@pytest.mark.parametrize("cur", ["inr", "usd"])
def test_bpm6_identities(bpm6, cur):
    df = bpm6.filter(pl.col("series_id").str.starts_with(f"bpm6.{cur}."))
    periods = ["2022-23", "2023-24", "2024-25", "2025-26"]

    def s(code: str, side: str) -> str:
        return f"bpm6.{cur}.bpm6_{code}.{side}.current"

    bad = []
    for code in U.hbs.BPM6_ITEMS:
        c = code.lower().replace(".", "_")
        bad += filled_identity(df, s(c, "net"), {s(c, "credit"): 1, s(c, "debit"): -1}, periods)
    tree = {
        "1": ["1_a", "1_b", "1_c"],
        "1_a": ["1_a_a", "1_a_b"],
        "1_a_a": ["1_a_a_1", "1_a_a_2", "1_a_a_3"],
        "1_a_b": [f"1_a_b_{i}" for i in range(1, 14)],
        "1_b": ["1_b_1", "1_b_2", "1_b_3"],
        "1_b_2": ["1_b_2_1", "1_b_2_2", "1_b_2_3", "1_b_2_4"],
        "1_c": ["1_c_1", "1_c_2"],
        "1_c_1": ["1_c_1_1", "1_c_1_2"],
        "2": ["2_1", "2_2"],
        "3": ["3_1", "3_2", "3_3", "3_4", "3_5"],
        "3_1": ["3_1_a", "3_1_b"],
        "3_2": ["3_2_a", "3_2_b"],
        "3_4": ["3_4_1", "3_4_2", "3_4_3", "3_4_4", "3_4_5", "3_4_6", "3_4_7"],
        "3_4_3": ["3_4_3_a", "3_4_3_b"],
        "4": ["3"],
    }
    for side in ("credit", "debit", "net"):
        for tot, parts in tree.items():
            bad += filled_identity(df, s(tot, side), {s(p, side): 1 for p in parts}, periods, tol=4)
    assert not bad, bad[:20]


@pytest.mark.parametrize("cur", ["inr", "usd"])
def test_bpm6_sign_convention_overall_identity(bpm6, cur):
    """RBI sign convention: financial-account net = net inflow (reserve accretion negative), so
    current account + capital account + financial account + errors and omissions = 0."""
    for p in ("2022-23", "2023-24", "2024-25", "2025-26"):
        tot = sum(v(bpm6, f"bpm6.{cur}.bpm6_{c}.net.current", p) for c in ("1", "2", "3", "5"))
        assert abs(tot) <= 3, (cur, p, tot)
    # reserves rose in 2023-24 (a debit in the financial account)
    assert v(bpm6, f"bpm6.{cur}.bpm6_3_5.net.current", "2023-24") < 0


def test_bpm6_rupee_and_dollar_tables_consistent(bpm6, fx):
    """T127 / T126 for every sizeable gross (credit/debit) cell is within 3% of the FY-average rate.
    Net cells are excluded: RBI converts each quarter at its own rate, so a net that changes sign
    within the year can imply any ratio."""
    bpm6 = bpm6.filter(pl.col("side") != "net")
    inr = bpm6.filter(pl.col("unit") == "INR_crore").select(
        pl.col("series_id").str.replace("bpm6.inr.", "", literal=True).alias("k"), "period", pl.col("value").alias("inr")
    )
    usd = bpm6.filter(pl.col("unit") == "USD_million").select(
        pl.col("series_id").str.replace("bpm6.usd.", "", literal=True).alias("k"), "period", pl.col("value").alias("usd")
    )
    rate = fx.filter(pl.col("series_id") == "t133.usd_fy_average").select("period", pl.col("value").alias("rate"))
    j = inr.join(usd, on=["k", "period"]).join(rate, on="period").filter(pl.col("usd").abs() > 2000)
    assert j.height > 250
    bad = j.filter(((pl.col("inr") * 10 / pl.col("usd")) / pl.col("rate") - 1).abs() > 0.03)
    checks.assert_no_rows(bad, "Rs/US$ implied rate off the FY average by more than 3%")


# ---------------------------------------------------------------------------------------------
# BPM6 quarterly (two editions)
# ---------------------------------------------------------------------------------------------


def test_bpm6q_anchor_values(bpm6q):
    assert v(bpm6q, "bpm6q.inr.bpm6_1.credit.current", "Q1 2023-24", "2025-08-29") == 1821825
    assert v(bpm6q, "bpm6q.inr.bpm6_1.net.current", "Q1 2023-24", "2025-08-29") == -73501
    assert v(bpm6q, "bpm6q.inr.bpm6_1.net.current", "Q2 2023-24", "2025-08-29") == -93094
    assert v(bpm6q, "bpm6q.inr.bpm6_1.net.current", "Q1 2024-25", "2026-07-31") == -37159
    assert v(bpm6q, "bpm6q.inr.bpm6_1.net.current", "Q4 2025-26", "2026-07-31") == 64744
    assert v(bpm6q, "bpm6q.inr.bpm6_5.net.current", "Q2 2025-26", "2026-07-31") == 8674


@pytest.mark.parametrize("fy, vintage", [("2023-24", "2025-08-29"), ("2024-25", "2026-07-31"), ("2025-26", "2026-07-31")])
def test_quarters_sum_to_annual(bpm6q, bpm6, fy, vintage):
    q = bpm6q.filter(pl.col("period").str.ends_with(fy), pl.col("vintage") == vintage)
    s = q.group_by("series_id", maintain_order=True).agg(pl.col("value").sum().alias("q"), pl.len().alias("n"))
    a = bpm6.filter(pl.col("period") == fy).select(
        pl.col("series_id").str.replace("bpm6.", "bpm6q.", literal=True), pl.col("value").alias("a")
    )
    j = s.join(a, on="series_id", how="inner").filter(pl.col("n") == 4)
    assert j.height > 300
    checks.assert_no_rows(j.filter((pl.col("q") - pl.col("a")).abs() > 3), f"quarters of {fy} vs annual")


def test_bpm6q_vintages_and_stages(bpm6q):
    by = dict(bpm6q.group_by("vintage", maintain_order=True).agg(pl.col("period").n_unique()).iter_rows())
    assert by == {"2025-08-29": 8, "2026-07-31": 8}
    prelim = bpm6q.filter(pl.col("estimate_stage") == "Preliminary")
    assert set(prelim.select(pl.col("period").str.slice(3)).to_series()) == {"2024-25", "2025-26"}
    # 2024-25 quarters were revised between the editions. Known revision (issues file): Q1 2024-25
    # goods exports up US$ 4,011 mn (1,11,158 -> 1,15,169), so the CAD fell from 8,647 to 4,454.
    rev = checks.compare_vintages(bpm6q, "2025-08-29", "2026-07-31", rel_tol=0.0).filter(pl.col("change") == "revised")
    assert rev.height > 0
    old, new = "2025-08-29", "2026-07-31"
    assert v(bpm6q, "bpm6q.usd.bpm6_1_a_a.credit.current", "Q1 2024-25", old) == 111158
    assert v(bpm6q, "bpm6q.usd.bpm6_1_a_a.credit.current", "Q1 2024-25", new) == 115169
    assert v(bpm6q, "bpm6q.usd.bpm6_1.net.current", "Q1 2024-25", old) == -8647
    assert v(bpm6q, "bpm6q.usd.bpm6_1.net.current", "Q1 2024-25", new) == -4454
    # secondary income was not revised
    assert v(bpm6q, "bpm6q.inr.bpm6_1_c.credit.current", "Q1 2024-25", old) == v(bpm6q, "bpm6q.inr.bpm6_1_c.credit.current", "Q1 2024-25", new)


# ---------------------------------------------------------------------------------------------
# Old-format BoP (T124/T125) and invisibles (T130/T131)
# ---------------------------------------------------------------------------------------------


def test_old_format_anchor_values(old):
    assert v(old, "bop_old.inr.ca.merchandise.credit.current", "2022-23") == 3661287
    assert v(old, "bop_old.inr.ca.merchandise.net.current", "2023-24") == -2028119
    assert v(old, "bop_old.inr.ca.transfers.private.credit.current", "2022-23") == 905234
    assert v(old, "bop_old.inr.ka.fdi.in_india.reinvested_earnings.credit.current", "2020-21") == 125600
    assert v(old, "bop_old.inr.monetary_movements.reserves.net.current", "2023-24") == -526931
    assert v(old, "bop_old.inr.ka.banking_capital.commercial_banks.nri_deposits.debit.current", "2022-23") == 445816


def test_old_format_identities(old):
    periods = sorted(set(old["period"]))
    bad = []
    for cur in ("inr", "usd"):
        for side in ("credit", "debit", "net"):

            def s(code, cur=cur, side=side):
                return f"bop_old.{cur}.{code}.{side}.current"

            bad += filled_identity(old, s("ca.total"), {s("ca.merchandise"): 1, s("ca.invisibles"): 1}, periods)
            bad += filled_identity(old, s("ca.invisibles"), {s("ca.services"): 1, s("ca.transfers"): 1, s("ca.income"): 1}, periods)
            bad += filled_identity(old, s("ka.loans"), {s("ka.loans.external_assistance"): 1, s("ka.loans.ecb"): 1, s("ka.loans.short_term"): 1}, periods)
            bad += filled_identity(old, s("overall_balance"), {s("ca.total"): 1, s("ka.total"): 1, s("errors_omissions"): 1}, periods)
        bad += filled_identity(
            old,
            f"bop_old.{cur}.overall_balance.net.current",
            {f"bop_old.{cur}.monetary_movements.net.current": -1},
            periods,
        )
    assert not bad, bad[:20]


def test_old_format_agrees_with_bpm6(old, bpm6):
    for p in ("2022-23", "2023-24", "2024-25", "2025-26"):
        assert v(old, "bop_old.inr.ca.merchandise.credit.current", p) == v(bpm6, "bpm6.inr.bpm6_1_a_a.credit.current", p)
        assert v(old, "bop_old.inr.ca.services.net.current", p) == v(bpm6, "bpm6.inr.bpm6_1_a_b.net.current", p)
        assert v(old, "bop_old.inr.monetary_movements.reserves.net.current", p) == v(bpm6, "bpm6.inr.bpm6_3_5.net.current", p)


def test_invisibles_anchor_and_identities(invis, old):
    assert v(invis, "invis.inr.nonfactor_services.net.current", "2006-07") == 133064
    assert v(invis, "invis.inr.nonfactor_services.receipts.current", "2006-07") == 333093
    assert v(invis, "invis.inr.nonfactor_services.travel.receipts.current", "2023-24") == 279274
    assert v(invis, "invis.inr.nonfactor_services.travel.net.current", "2023-24") == 388
    assert v(invis, "invis.inr.private_transfers.receipts.current", "2013-14") == 421044
    periods = sorted(set(invis["period"]))
    assert periods[0] == "2006-07" and periods[-1] == "2025-26" and len(periods) == 20
    bad = []
    for cur in ("inr", "usd"):
        for code in [c for c, _ in U.hbs.INVISIBLES]:

            def s(side, code=code, cur=cur):
                return f"invis.{cur}.{code}.{side}.current"

            bad += filled_identity(invis, s("net"), {s("receipts"): 1, s("payments"): -1}, periods)
        for side in ("net", "receipts", "payments"):
            t = {c: f"invis.{cur}.{c}.{side}.current" for c, _ in U.hbs.INVISIBLES}
            bad += filled_identity(invis, t["invisibles"], {t[k]: 1 for k in ("nonfactor_services", "income", "private_transfers", "official_transfers")}, periods)
            bad += filled_identity(invis, t["income"], {t["income.investment"]: 1, t["income.compensation_of_employees"]: 1}, periods)
    assert not bad, bad[:20]
    # the same 2023-24 invisibles total as the old-format BoP table
    assert v(invis, "invis.inr.invisibles.receipts.current", "2023-24") == v(old, "bop_old.inr.ca.invisibles.credit.current", "2023-24")
    # remittance receipts never fall by more than a third or jump by more than half in a year
    pt = invis.filter(pl.col("series_id") == "invis.inr.private_transfers.receipts.current")
    checks.assert_no_rows(checks.check_continuity(pt, max_rel_change=0.5), "private transfers break")


# ---------------------------------------------------------------------------------------------
# NRI deposits, foreign investment, reserves, external debt, IIP
# ---------------------------------------------------------------------------------------------


def test_nri_deposits():
    df = load("nri_deposits")
    assert v(df, "nri.stock.inr.total.current", "2025-03-31") == 1409330
    assert v(df, "nri.stock.usd.total.current", "2026-03-31") == 165654
    assert v(df, "nri.stock.usd.fcnr_b.current", "2008-03-31") == 14168
    assert v(df, "nri.flow.inr.total.current", "2024-25") == 136702
    schemes = [s for s in U.hbs.NRI_SCHEMES.values() if s != "total"]
    bad = []
    for kind, periods in (("stock", sorted(set(df.filter(pl.col("period_type") == "date")["period"]))),
                          ("flow", sorted(set(df.filter(pl.col("period_type") == "fy")["period"])))):  # fmt: skip
        for cur in ("inr", "usd"):
            bad += filled_identity(df, f"nri.{kind}.{cur}.total.current", {f"nri.{kind}.{cur}.{s}.current": 1 for s in schemes}, periods)
    assert not bad, bad
    debt = load("external_debt")
    for y in (2020, 2024, 2026):  # T140 outstanding = T146 'VI. Non-resident Deposits'
        assert v(df, "nri.stock.inr.total.current", f"{y}-03-31") == v(debt, "debt.inr.nri_deposits.current", f"{y}-03-31")


def test_foreign_investment(bpm6):
    df = load("foreign_investment")
    assert v(df, "t143.inr.fdi_gross_inflows.current", "2024-25") == 680929
    assert v(df, "t143.usd.fdi_gross_inflows.current", "2024-25") == 80615
    assert v(df, "t143.inr.fdi_gross_inflows.current", "2004-05") == 27234
    assert v(df, "t143.usd.portfolio_net.current", "2025-26") == -16363
    periods = sorted(set(df["period"]))
    bad = []
    for cur in ("inr", "usd"):

        def s(code, cur=cur):
            return f"t143.{cur}.{code}.current"

        bad += filled_identity(df, s("fdi_to_india_net"), {s("fdi_gross_inflows"): 1, s("fdi_repatriation"): -1}, periods)
        bad += filled_identity(df, s("fdi_net"), {s("fdi_to_india_net"): 1, s("fdi_by_india"): -1}, periods)
        bad += filled_identity(df, s("foreign_investment_net"), {s("fdi_net"): 1, s("portfolio_net"): 1}, periods)
    assert not bad, bad
    for p in ("2022-23", "2023-24", "2024-25", "2025-26"):
        assert v(df, "t143.inr.fdi_gross_inflows.current", p) == v(bpm6, "bpm6.inr.bpm6_3_1_a.credit.current", p)


def test_fx_reserves():
    df = load("fx_reserves")
    assert v(df, "t144.inr.total.current", "2024-03-31") == 5391256
    assert v(df, "t144.usd.total.current", "2024-03-31") == 646419
    assert v(df, "t144.usd.total.current", "1969-03-31") == 769
    assert v(df, "t144.usd.gold.current", "2026-03-31") == 115395
    periods = sorted(set(df["period"]))
    bad = []
    for cur in ("inr", "usd"):
        bad += filled_identity(df, f"t144.{cur}.total.current", {f"t144.{cur}.{c}.current": 1 for c in ("sdr", "gold", "fca", "rtp")}, periods, tol=2)
    assert not bad, bad
    checks.assert_no_rows(checks.check_range(df, lo=0), "negative reserves")


def test_external_debt(fx):
    df = load("external_debt")
    assert v(df, "debt.inr.gross_external_debt.current", "2024-03-31") == 5576778
    assert v(df, "debt.inr.gross_external_debt.current", "2008-03-31") == 897290
    assert v(df, "debt.inr.commercial_borrowing.current", "2024-03-31") == 2089300
    assert v(df, "debt.inr.imf.current", "2022-03-31") == 173415
    dates = sorted(set(df["period"]))
    assert dates[0] == "2008-03-31" and dates[-1] == "2026-03-31" and len(dates) == 19
    bad = []
    for cur in ("inr", "usd"):

        def s(code, cur=cur):
            return f"debt.{cur}.{code}.current"

        bad += filled_identity(df, s("long_term_total"), {s(c): 1 for c in ("multilateral", "bilateral", "imf", "trade_credit", "commercial_borrowing", "nri_deposits", "rupee_debt")}, dates)
        bad += filled_identity(df, s("gross_external_debt"), {s("long_term_total"): 1, s("short_term"): 1}, dates)
        bad += filled_identity(df, s("multilateral"), {s("multilateral.govt"): 1, s("multilateral.nongovt"): 1}, dates)
        bad += filled_identity(df, s("short_term.trade_credit"), {s("short_term.trade_credit.above_180d"): 1, s("short_term.trade_credit.upto_180d"): 1}, dates)
    assert not bad, bad[:20]
    # Rs / US$ gross debt at end-March is close to the end-March exchange rate (T133); RBI values
    # each currency at its own rate; 17 of 19 year-ends agree to 0.2%
    for y in range(2008, 2027):
        d = f"{y}-03-31"
        implied = v(df, "debt.inr.gross_external_debt.current", d) * 10 / v(df, "debt.usd.gross_external_debt.current", d)
        tol = 0.007 if y in (2020, 2021) else 0.002  # end-March 2020/2021 differ by 0.29% / 0.58% (logged)
        assert implied == pytest.approx(v(fx, "t133.usd_end_march", d), rel=tol), y


def test_external_debt_ratio_tables_disagree_once():
    """T145 and T146 print the same ratio rows; they differ in one cell (logged as an issue)."""
    df = load("external_debt").filter(pl.col("unit") == "percent")
    a = df.filter(pl.col("series_id").str.starts_with("debt.145.")).select("item_code", "period", pl.col("value").alias("a"))
    b = df.filter(pl.col("series_id").str.starts_with("debt.146.")).select("item_code", "period", pl.col("value").alias("b"))
    j = a.join(b, on=["item_code", "period"])
    assert j.height == 4 * 19
    diff = j.filter(pl.col("a") != pl.col("b"))
    assert diff.rows() == [("pct.debt_to_gdp", "2023-03-31", 19.1, 19.6)]


def test_iip_quarterly():
    df = load("iip_quarterly")
    assert v(df, "iipq.inr.niip.current", "2026-03-31", "2026-07-31") == -2026767
    assert v(df, "iipq.inr.niip.current", "2023-06-30", "2025-08-29") == -3126515
    assert v(df, "iipq.inr.niip.current", "2024-03-31", "2025-08-29") == -3031785
    assert v(df, "iipq.inr.assets.4.current", "2026-03-31", "2026-07-31") == 6553861
    # Column headers carry "PR" / "P"; the notes read "PR: Partially Revised, P: Provisional".
    # HBS 2024-25 T198/T199: Q1 2023-24..Q3 2024-25 PR, Q4 2024-25 P. HBS 2025-26 T199/T200: Q1
    # 2024-25..Q3 2025-26 PR, Q4 2025-26 P.
    stages = {(r[0], r[1]): r[2] for r in df.select("vintage", "period", "estimate_stage").unique().rows()}
    assert len(stages) == 16  # one stage per (vintage, quarter)
    assert {k for k, s in stages.items() if s == "Provisional"} == {("2025-08-29", "2025-03-31"), ("2026-07-31", "2026-03-31")}
    assert set(stages.values()) == {"Partially Revised", "Provisional"}
    bad = []
    for vint in ("2025-08-29", "2026-07-31"):
        sub = df.filter(pl.col("vintage") == vint)
        dates = sorted(set(sub["period"]))
        for cur in ("inr", "usd"):

            def s(code, cur=cur):
                return f"iipq.{cur}.{code}.current"

            bad += filled_identity(sub, s("niip"), {s("assets"): 1, s("liabilities"): -1}, dates, tol=3)
            bad += filled_identity(sub, s("assets"), {s(f"assets.{i}"): 1 for i in (1, 2, 3, 4)}, dates, tol=3)
            bad += filled_identity(sub, s("liabilities"), {s(f"liabilities.{i}"): 1 for i in (1, 2, 3)}, dates, tol=3)
            bad += filled_identity(sub, s("liabilities.3"), {s(f"liabilities.3.{i}"): 1 for i in (1, 2, 3, 4, 5)}, dates, tol=3)
    assert not bad, bad[:20]
    # end-March reserve assets = HBS T144 reserves (same edition)
    res = load("fx_reserves")
    assert v(df, "iipq.inr.assets.4.current", "2026-03-31", "2026-07-31") == v(res, "t144.inr.total.current", "2026-03-31")


# ---------------------------------------------------------------------------------------------
# ECB, FLA, remittances survey, ITES survey, LRS
# ---------------------------------------------------------------------------------------------


def test_ecb_loans_sum_to_published_totals():
    df = load("ecb_monthly_2324")
    assert sorted(set(df["period"])) == list(U.surveys.ECB_IDS)
    loans = df.filter(pl.col("item_code") == "ecb_registration").with_columns(
        pl.col("dim_other").str.extract(r"route=(\w+)").alias("route"),
        pl.when(pl.col("instrument") == "rdb").then(pl.lit("rdb")).otherwise(pl.lit("ecb_fccb")).alias("kind"),
    )
    tot = df.filter(pl.col("item_code") == "ecb_registrations_total").with_columns(
        pl.col("dim_other").str.extract(r"route=(\w+)").alias("route"), pl.col("instrument").alias("kind")
    )
    sums = loans.group_by("period", "kind", "route", maintain_order=True).agg(pl.col("value").sum().alias("s"))
    per_route = tot.filter(pl.col("route") != "all").join(sums, on=["period", "kind", "route"], how="left")
    per_route = per_route.with_columns(pl.col("s").fill_null(0.0))
    checks.assert_no_rows(per_route.filter((pl.col("value") - pl.col("s")).abs() > 1e-5), "loans vs route total (US$ 10 tolerance)")
    grand = tot.filter(pl.col("route") == "all").join(
        loans.group_by("period", "kind", maintain_order=True).agg(pl.col("value").sum().alias("s")), on=["period", "kind"], how="left"
    )
    checks.assert_no_rows(grand.filter((pl.col("value") - pl.col("s").fill_null(0.0)).abs() > 1e-5), "loans vs grand total")


def test_ecb_anchor_values():
    df = load("ecb_monthly_2324")
    assert v(df, "ecb.total.ecb_fccb.all", "2023-04") == pytest.approx(5359.880471)
    assert v(df, "ecb.total.ecb_fccb.approval", "2023-04") == pytest.approx(3799.353313)
    first = df.filter(pl.col("series_id") == "ecb.2023-04.ecb_fccb.automatic.001")
    assert first["item_label"][0] == "Deepali Deepak Private Limited"
    assert first["value"][0] == pytest.approx(0.16)
    assert first["dim_other"][0].startswith("lender=foreign_collaborator_foreign_equity_holder;")
    rdb = df.filter(pl.col("series_id") == "ecb.total.rdb.automatic", pl.col("period") == "2023-05")
    assert rdb["value"][0] == pytest.approx(159.634071)  # printed 15,96,34,071 US$
    fy_total = df.filter(pl.col("item_code") == "ecb_registration")["value"].sum()
    assert 40000 < fy_total < 60000  # US$ 49.2 bn registered in 2023-24
    # Feb and Mar 2024 label the all-routes total 'Grand total' (verifier finding V2)
    assert v(df, "ecb.total.ecb_fccb.all", "2024-02") == pytest.approx(2216.395722)  # printed 2,21,63,95,722
    assert v(df, "ecb.total.ecb_fccb.all", "2024-03") == pytest.approx(7733.556768)  # printed 7,73,35,56,768
    assert v(df, "ecb.total.rdb.all", "2024-02") == pytest.approx(79.552922)  # printed 7,95,52,922
    months = df.filter(pl.col("series_id") == "ecb.total.ecb_fccb.all")["period"].to_list()
    assert sorted(months) == [f"{y}-{m:02d}" for y, m in [(2023, i) for i in range(4, 13)] + [(2024, i) for i in range(1, 4)]]


FLA_2425, FLA_2324 = "2025-10-29", "2024-10-11"  # release dates (vintages) of the two census rounds


def test_fla_census():
    df = load("fla_census")
    assert set(df["vintage"]) == {FLA_2425, FLA_2324}
    # 2024-25 round (PublicationsView id=23438)
    assert v(df, "fla.t3b.liabilities.total.inr", "2024-03-31", FLA_2425) == 6188243
    assert v(df, "fla.t3b.liabilities.total.usd", "2024-03-31", FLA_2425) == 742228
    assert v(df, "fla.t3b.assets.total.inr", "2025-03-31") == 1166790
    assert v(df, "fla.5.liabilities.usa.total", "2025-03-31") == 1375638
    assert v(df, "fla.t8.total.total", "2025-03-31") == 6875931
    assert v(df, "fla.t2b.fc.fdi_equity", "2025-03-31") == 93082
    assert v(df, "fla.t4.liabilities.loans.inr", "2024-03-31", FLA_2425) == 1163061
    # 2023-24 round (press release prid 58874, 11 Oct 2024): end-March 2024 FC/NFC and activity splits (R14a, R8)
    assert v(df, "fla.t2b.fc.fdi_equity", "2024-03-31") == 98358
    assert v(df, "fla.t2b.nfc.fdi_equity", "2024-03-31") == 806849
    assert v(df, "fla.t2b.total.entities", "2024-03-31") == 32129
    assert v(df, "fla.t8.total.total", "2024-03-31") == 6057599
    assert v(df, "fla.t8.g.information_and_communication.total", "2024-03-31") == 929146  # printed '4.Information and communication'
    assert v(df, "fla.t8.g.financial_and_insurance_activities.equity", "2024-03-31") == 939517
    assert v(df, "fla.t8.g.other_service_activities.total", "2024-03-31") == 339357  # printed 'Other Services activities'
    assert v(df, "fla.t3a.inward.listed.equity", "2023-03-31") == 2338361
    assert v(df, "fla.t4.liabilities.currency_deposits.inr", "2024-03-31", FLA_2324) == 775916  # 'Currency and Deposits'
    assert v(df, "fla.6.assets.bmu.total", "2024-03-31") == 10691
    # end-March 2024 revised by the 2024-25 round (both vintages kept)
    assert v(df, "fla.t3b.liabilities.total.usd", "2024-03-31", FLA_2324) == 726558
    assert set(df["estimate_stage"]) == {"Provisional"}
    t8_ind = {vin: set(df.filter(pl.col("table_id") == "Table 8", pl.col("vintage") == vin)["industry"]) for vin in (FLA_2425, FLA_2324)}
    assert t8_ind[FLA_2425] == t8_ind[FLA_2324]  # same activity codes in both rounds
    bad = []
    for vin, (d0, d1) in {FLA_2425: ("2024-03-31", "2025-03-31"), FLA_2324: ("2023-03-31", "2024-03-31")}.items():
        dv = df.filter(pl.col("vintage") == vin)
        for d in (d0, d1):
            for side in ("liabilities", "assets"):
                for cur in ("inr", "usd"):
                    bad += filled_identity(dv, f"fla.t3b.{side}.total.{cur}", {f"fla.t3b.{side}.equity.{cur}": 1, f"fla.t3b.{side}.debt.{cur}": 1}, [d])
                    bad += filled_identity(dv, f"fla.t4.{side}.total.{cur}", {f"fla.t4.{side}.{c}.{cur}": 1 for c in ("trade_credit", "loans", "currency_deposits", "other_accounts")}, [d])
            for tab, side in (("5", "liabilities"), ("6", "assets")):
                sub = dv.filter(pl.col("series_id").str.starts_with(f"fla.{tab}.{side}."), pl.col("instrument") == "total", pl.col("period") == d)
                total = sub.filter(pl.col("dim_other") == "partner=all_countries")["value"][0]
                parts = sub.filter(pl.col("dim_other").is_null() | (pl.col("dim_other") == "partner=other_countries"))["value"].sum()
                if abs(total - parts) > 3:
                    bad.append((vin, tab, d, total, parts))
            # Table 3A total inward = Table 3B inward (Rs crore)
            assert v(dv, "fla.t3a.inward.total.total", d) == v(dv, "fla.t3b.liabilities.total.inr", d)
        t8 = dv.filter(pl.col("series_id").str.starts_with("fla.t8."), pl.col("series_id").str.ends_with(".total"))
        assert set(t8["period"]) == {d1}
        sections = t8.filter(pl.col("dim_other") == "level=section")["value"].sum()
        if abs(sections - v(dv, "fla.t8.total.total", d1)) > 5:
            bad.append((vin, "t8 sections", sections))
        for sec, head in (("c", "fla.t8.c_manufacturing.total"), ("g", "fla.t8.g_services.total")):
            subs = t8.filter(pl.col("dim_other") == f"level=subsection;section={sec}")["value"].sum()
            if abs(subs - v(dv, head, d1)) > 5:
                bad.append((vin, f"t8 section {sec}", subs))
        bad += filled_identity(dv, "fla.t2b.total.fdi_equity", {"fla.t2b.fc.fdi_equity": 1, "fla.t2b.nfc.fdi_equity": 1}, [d1])
    assert not bad, bad


def test_remittance_survey():
    df = load("remittance_survey")
    p = "2023-24"
    assert v(df, "remit.source_country.usa", p) == 27.7
    assert v(df, "remit.source_country.are", p) == 19.2
    assert v(df, "remit.source_country.gbr", p) == 10.8
    assert v(df, "remit.source_country.are", "2016-17") == 26.9
    assert v(df, "remit.destination_state.in-mh", p) == 20.5
    assert v(df, "remit.destination_state.in-kl", p) == 19.7
    assert v(df, "remit.destination_state.in-tn", p) == 10.4
    gcc = sum(v(df, f"remit.source_country.{c}", p) for c in ("are", "sau", "kwt", "qat", "omn", "bhr"))
    assert gcc == pytest.approx(37.9, abs=0.05)  # the article rounds this to 'GCC ... 38 per cent'
    for kind, n in (("source_country", 27), ("destination_state", 36)):
        sub = df.filter(pl.col("period") == p, pl.col("series_id").str.starts_with(f"remit.{kind}."))
        assert sub.height == n
        assert sub["value"].sum() == pytest.approx(100, abs=0.3)
    checks.assert_no_rows(checks.check_range(df, lo=0, hi=100), "share out of range")


def test_remittance_survey_state_codes():
    """Destination States use the shared code set (DECISIONS D1-9, pipeline/core/geo.py)."""
    df = load("remittance_survey").filter(pl.col("table_id") == "Table 2")
    # the 2016-17 round predates 31 Oct 2019: Jammu and Kashmir is the former State incl. Ladakh
    assert v(df, "remit.destination_state.in-xjk", "2016-17") == 0.2
    jk = df.filter(pl.col("series_id") == "remit.destination_state.in-jk").sort("period")
    assert jk.select("period", "value").rows() == [("2020-21", 0.3), ("2023-24", 0.4)]
    assert set(df.filter(pl.col("geography") == "IN-XJK")["period"]) == {"2016-17"}
    # every other row carries the current code that geo.state_code gives for the printed name
    for label, code in df.filter(pl.col("geography") != "IN-XJK").select("item_label", "geography").unique().rows():
        name = label.split(": share in", 1)[0]
        assert geo.state_code(U.surveys.REM_STATE_SPELLING.get(name, name)) == code, label
    assert all(geo.geography_problem(c) is None for c in df["geography"].drop_nulls())
    assert df["series_id"].to_list() == [f"remit.destination_state.{c.lower()}" for c in df["geography"]]
    # 2023-24 prints all 36 current States/UTs
    assert set(df.filter(pl.col("period") == "2023-24")["geography"]) == set(geo.STATES_UTS)
    # the helper refuses figures with no single territory code
    for name, period in (("Ladakh", "2016-17"), ("Jammu and Kashmir", "2019-20"), ("Dadra & Nagar Haveli and Daman & Diu", "2016-17")):
        with pytest.raises(ValueError, match="no single code"):
            U.surveys.rem_state_code(name, period)
    assert U.surveys.rem_state_code("Andhra Pradesh", "2013-14") == "IN-XAP"
    assert U.surveys.rem_state_code("Andhra Pradesh", "2016-17") == "IN-AP"


def test_ites_survey():
    df = load("ites_survey")
    r24, r26 = "2025-11-04", "2026-09-18"
    assert v(df, "ites.t2.total_export_of_software_services.inr", "2023-24", r24) == 1578650
    assert v(df, "ites.t2.total_export_of_software_services.usd", "2023-24", r24) == pytest.approx(190700)
    assert v(df, "ites.t5.united_states_of_america.share", "2023-24", r24) == 54.1
    assert v(df, "ites.t5.united_kingdom.inr", "2023-24", r24) == 222116
    assert v(df, "ites.t2.total_export_of_software_services.inr", "2025-26", r26) == 1955947
    assert v(df, "ites.t5.united_states_of_america.share", "2025-26", r26) == 54.1
    bad = []
    for vint, periods in ((r24, ["2023-24", "2024-25"]), (r26, ["2024-25", "2025-26"])):
        sub = df.filter(pl.col("vintage") == vint)
        for tag in ("inr", "share"):
            bad += filled_identity(sub, f"ites.t2.total_export_of_software_services.{tag}", {f"ites.t2.computer_services.{tag}": 1, f"ites.t2.it_enabled_services.{tag}": 1}, periods, tol=0.2 if tag == "share" else 2)
            bad += filled_identity(
                sub,
                f"ites.t5.total.{tag}",
                {f"ites.t5.{c}.{tag}": 1 for c in ("united_states_of_america", "canada", "europe", "asia", "australia_new_zealand", "other_countries")},
                periods,
                tol=0.3 if tag == "share" else 3,
            )
        for per in periods:
            t2 = v(sub, "ites.t2.total_export_of_software_services.inr", per)
            for t in ("t4", "t5", "t6", "t7"):
                assert v(sub, f"ites.{t}.total.inr", per) == t2, (vint, t, per)
    assert not bad, bad
    # both releases print 2024-25; the total was not revised
    assert v(df, "ites.t2.total_export_of_software_services.inr", "2024-25", r24) == v(
        df, "ites.t2.total_export_of_software_services.inr", "2024-25", r26
    )


def test_lrs(fx):
    df = load("lrs_outward")
    assert v(df, "lrs.usd.annual.lrs_1.current", "2023-24") == 31735.74
    assert v(df, "lrs.usd.annual.lrs_1_6.current", "2023-24") == 17006.27
    assert v(df, "lrs.usd.annual.lrs_1_7.current", "2023-24") == 4611.53
    assert v(df, "lrs.usd.monthly.lrs_1.current", "2023-04") == 2332.08
    assert v(df, "lrs.usd.annual.lrs_1.current", "2025-26") == 28979.36
    # April 2024 is printed in the June 2024 and June 2025 issues, unchanged
    assert v(df, "lrs.usd.monthly.lrs_1.current", "2024-04", "2024-06-19") == v(df, "lrs.usd.monthly.lrs_1.current", "2024-04", "2025-06-25")
    ann = df.filter(pl.col("unit") == "USD_million", pl.col("period_type") == "fy")
    parts = {f"lrs.usd.annual.lrs_1_{i}.current": 1 for i in range(1, 11)}
    assert not filled_identity(ann, "lrs.usd.annual.lrs_1.current", parts, ["2023-24", "2024-25", "2025-26"], tol=0.1)
    # Travel sub-items 1.6.1-1.6.5 start in March 2026: their '2025-26' cell is one month, so no FY row
    # (and no derived rupee row) is stored; the March and April 2026 cells are kept (verifier finding V1).
    for i in range(1, 6):
        assert df.filter(pl.col("series_id").is_in([f"lrs.usd.annual.lrs_1_6_{i}.current", f"lrs.inr.annual.lrs_1_6_{i}.current"])).is_empty()
    assert v(df, "lrs.usd.monthly.lrs_1_6_1.current", "2026-03") == 16.05
    assert v(df, "lrs.usd.monthly.lrs_1_6_5.current", "2026-04") == 686.65
    # derived rupee totals use the FY-average rate
    for p in ("2023-24", "2024-25", "2025-26"):
        inr = df.filter(pl.col("series_id") == "lrs.inr.annual.lrs_1.current", pl.col("period") == p)
        assert inr["status"][0] == "derived"
        expected = v(df, "lrs.usd.annual.lrs_1.current", p) * v(fx, "t133.usd_fy_average", p) / 10
        assert inr["value"][0] == pytest.approx(expected, abs=1e-3)
    prov = checks.load_provenance(UNIT)
    pid = df.filter(pl.col("series_id") == "lrs.inr.annual.lrs_1.current", pl.col("period") == "2023-24")["prov_id"][0]
    rec = prov.filter(pl.col("prov_id") == pid)
    fx_pid = fx.filter(pl.col("series_id") == "t133.usd_fy_average")["prov_id"][0]
    assert fx_pid in rec["inputs"][0].split(",")


def test_every_dataset_has_reference_year_values():
    ref = {
        "bop_bpm6_annual": "2023-24",
        "bop_bpm6_quarterly": "Q4 2023-24",
        "bop_overall_annual": "2023-24",
        "invisibles_annual": "2023-24",
        "fx_inr_usd": "2023-24",
        "nri_deposits": "2023-24",
        "foreign_investment": "2023-24",
        "fx_reserves": "2024-03-31",
        "external_debt": "2024-03-31",
        "iip_quarterly": "2024-03-31",
        "ecb_monthly_2324": "2024-03",
        "fla_census": "2024-03-31",
        "remittance_survey": "2023-24",
        "ites_survey": "2023-24",
        "lrs_outward": "2023-24",
    }
    for name, period in ref.items():
        assert load(name).filter(pl.col("period") == period).height > 0, name


def test_external_debt_by_sector():
    df = load("external_debt_by_sector")
    d24 = "2024-03-31"
    assert v(df, "edr.t1.gg.usd.current", d24) == pytest.approx(148700)
    assert v(df, "edr.t1.other_sectors.nfc.usd.current", d24) == pytest.approx(252700)
    assert v(df, "edr.t1.total.usd.current", d24) == pytest.approx(668900)
    assert v(df, "edr.t1.total.usd.current", "2026-03-31") == pytest.approx(762800)
    assert v(df, "edr.t3.total.pct_gdp", d24) == 19.2
    assert v(df, "edr.t4.loans.usd.current", d24) == pytest.approx(221400)
    assert v(df, "edr.t5.external_debt.usd.current", "1991-03-31") == pytest.approx(83800)
    assert v(df, "edr.t5.debt_to_gdp", "1991-03-31") == 28.3
    stage = df.filter(pl.col("series_id") == "edr.t1.total.usd.current").select("period", "estimate_stage").sort("period")
    # footnote "R: Revised. PR: Partially Revised. P: Provisional."; headers read 2024 R, 2025 PR, 2026 P
    assert stage.rows() == [("2024-03-31", "Revised"), ("2025-03-31", "Partially Revised"), ("2026-03-31", "Provisional")]
    assert set(df.filter(pl.col("period") <= "2023-03-31")["estimate_stage"]) == {"n.a."}
    bad = []
    for d in ("2024-03-31", "2025-03-31", "2026-03-31"):
        t1 = {c: f"edr.t1.{c}.usd.current" for c in ("gg", "central_bank", "deposit_taking_corporations", "other_sectors", "di_intercompany_lending")}
        bad += filled_identity(df, "edr.t1.total.usd.current", {x: 1 for x in t1.values()}, [d], tol=300)
        bad += filled_identity(df, "edr.t1.other_sectors.usd.current", {f"edr.t1.other_sectors.{c}.usd.current": 1 for c in ("ofc", "nfc", "hh_npish")}, [d], tol=300)
        bad += filled_identity(df, "edr.t1.total.usd.current", {"edr.t1.memo.long_term_original_maturity.usd.current": 1, "edr.t1.memo.short_term_original_maturity.usd.current": 1}, [d], tol=300)
        assert v(df, "edr.t1.gg.usd.current", d) == v(df, "edr.t3.government.usd.current", d)
        assert v(df, "edr.t5.external_debt.usd.current", d) == v(df, "edr.t1.total.usd.current", d)
    for d in ("2023-03-31", "2024-03-31", "2025-03-31", "2026-03-31"):
        bad += filled_identity(df, "edr.t3.total.usd.current", {"edr.t3.government.usd.current": 1, "edr.t3.non_government.usd.current": 1}, [d], tol=300)
        bad += filled_identity(df, "edr.t4.total.usd.current", {f"edr.t4.{c}.usd.current": 1 for c in ("sdr_allocations", "currency_deposits", "debt_securities", "loans", "trade_credit", "other", "di_intercompany_lending")}, [d], tol=300)
    assert not bad, bad
    # the release total agrees with HBS 2025-26 T145 (US$ mn) within rounding to US$ 0.1 bn
    debt = load("external_debt")
    for d in ("2024-03-31", "2025-03-31", "2026-03-31"):
        assert abs(v(df, "edr.t1.total.usd.current", d) - v(debt, "debt.usd.gross_external_debt.current", d)) <= 100
    # the release's GDP ratios for end-March 2023 (19.6, new GDP base) side with T146, not T145
    assert v(df, "edr.t3.total.pct_gdp", "2023-03-31") == v(debt, "debt.146.pct.debt_to_gdp", "2023-03-31") == 19.6
