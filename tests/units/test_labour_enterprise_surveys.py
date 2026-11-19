"""Value tests for the labour_enterprise_surveys unit (PLFS 2023-24, ASUSE 2023-24, ASI 2023-24,
AIDIS 2019 press note, SAS 2019).

Every anchor value below was read off the source PDF; the comment gives the table and page
(PDF page number, printed page in brackets). Survey years are not fiscal years: see the unit
docstring.
"""

import polars as pl
import pytest

from pipeline.core import checks
from pipeline.core.units import agricultural_year, survey_period
from pipeline.ingest import labour_enterprise_surveys as U

pytestmark = pytest.mark.quality
PREFIX = f"{U.UNIT}_"


def load(name):
    return checks.load_dataset(U.UNIT, PREFIX + name)


@pytest.fixture(scope="module")
def lfs():
    return load("plfs_lfs_indicators")


@pytest.fixture(scope="module")
def st6():
    return load("plfs_status_dist")


@pytest.fixture(scope="module")
def ind():
    return load("plfs_industry_dist")


@pytest.fixture(scope="module")
def earn():
    return load("plfs_earnings")


@pytest.fixture(scope="module")
def fs():
    return load("asuse_key_indicators")


@pytest.fixture(scope="module")
def act():
    return load("asuse_2324_activity")


@pytest.fixture(scope="module")
def asi_hist():
    return load("asi_principal_characteristics")


@pytest.fixture(scope="module")
def asi_ind():
    return load("asi_2324_industry")


@pytest.fixture(scope="module")
def aidis():
    return load("aidis_2019_press_note")


@pytest.fixture(scope="module")
def sas():
    return load("sas_2019_income_by_landclass")


def v(df, sid, period):
    return checks.value(df, sid, period)


def ay(label):
    """PLFS/SAS survey-year label '2023-24' -> its `sy` period '2023-07/2024-06' (July-June)."""
    return agricultural_year(int(label[:4]))


def osy(label):
    """ASUSE survey-year label '2023-24' -> its `sy` period '2023-10/2024-09' (October-September)."""
    return survey_period(int(label[:4]), 10)


# ---------------------------------------------------------------------------------------------
# PLFS Annual Report 2023-24
# ---------------------------------------------------------------------------------------------


def test_plfs_lfs_anchor_values(lfs):
    # Highlights Table 2 (usual status), PDF p.23 (printed vii): WPR 15+ rural+urban person 58.2 (2023-24), 46.8 (2017-18)
    assert v(lfs, "lfs.wpr.ps_ss.15plus.total.person", ay("2023-24")) == 58.2
    assert v(lfs, "lfs.wpr.ps_ss.15plus.total.person", ay("2017-18")) == 46.8
    # Highlights Table 1, p.22: LFPR 15+ rural+urban person 60.1; female rural 47.6
    assert v(lfs, "lfs.lfpr.ps_ss.15plus.total.person", ay("2023-24")) == 60.1
    assert v(lfs, "lfs.lfpr.ps_ss.15plus.rural.female", ay("2023-24")) == 47.6
    # Highlights Table 3, p.24: UR 15+ person 3.2 (2023-24) and 6.0 (2017-18); urban female 7.1
    assert v(lfs, "lfs.ur.ps_ss.15plus.total.person", ay("2023-24")) == 3.2
    assert v(lfs, "lfs.ur.ps_ss.15plus.total.person", ay("2017-18")) == 6.0
    assert v(lfs, "lfs.ur.ps_ss.15plus.urban.female", ay("2023-24")) == 7.1
    # CWS Table 1, p.25 (printed ix): LFPR 15+ person 56.4
    assert v(lfs, "lfs.lfpr.cws.15plus.total.person", ay("2023-24")) == 56.4
    assert lfs.height == 6 * 7 * 2 * 9


def test_plfs_lfs_ranges_and_flags(lfs):
    checks.assert_no_rows(checks.check_range(lfs, lo=0, hi=100), "percent out of range")
    # WPR <= LFPR for the same cell, and UR is consistent with them: UR ~ 100 * (1 - WPR/LFPR)
    w = lfs.filter(pl.col("item_code") == "wpr").with_columns(pl.col("series_id").str.replace("wpr", "x"))
    lf = lfs.filter(pl.col("item_code") == "lfpr").with_columns(pl.col("series_id").str.replace("lfpr", "x"))
    ur = lfs.filter(pl.col("item_code") == "ur").with_columns(pl.col("series_id").str.replace("ur", "x"))
    j = w.join(lf, on=["series_id", "period"], suffix="_l").join(ur, on=["series_id", "period"], suffix="_u")
    assert j.height == 2 * 7 * 2 * 9  # (ps_ss, cws) x 7 years x 2 age groups x 9 cells
    assert (j["value"] <= j["value_l"]).all()
    implied = 100 * (1 - j["value"] / j["value_l"])
    assert ((implied - j["value_u"]).abs() < 0.5).all(), "UR inconsistent with WPR/LFPR beyond rounding"
    assert set(lfs["period_type"]) == {"sy"} and not lfs["dim_other"].str.contains("survey_year").any()
    # LFPR rose every year 2017-18 -> 2023-24 in usual status (15+, person): no break above 10%
    # Known, published movements (not parsing errors): rural female participation jumped in 2019-20
    # (LFPR 15+ ps+ss 26.4 -> 33.0, Highlights Table 1) and CWS unemployment fell in 2022-23
    # (rural male 15+ 6.5 -> 4.6, CWS Table 3). Any other >25% move is a break to investigate.
    brk = checks.check_continuity(lfs, max_rel_change=0.25, min_abs_level=5.0)
    expected = {
        (sid, p)
        for sid, p in zip(brk["series_id"], brk["to_period"])
        if (p == ay("2019-20") and sid.endswith("rural.female") and sid.split(".")[1] in ("lfpr", "wpr"))
        or (p == ay("2022-23") and sid.startswith("lfs.ur.cws."))
    }
    assert set(zip(brk["series_id"], brk["to_period"])) == expected, brk


def test_plfs_status_distribution(st6):
    # Statement 6, p.42 (printed 13), 2023-24 rural+urban person: SE 58.4, regular 21.7, casual 19.8
    assert v(st6, "st6.worker_share.self_employed.total.person", ay("2023-24")) == 58.4
    assert v(st6, "st6.worker_share.regular_wage.total.person", ay("2023-24")) == 21.7
    assert v(st6, "st6.worker_share.casual_labour.total.person", ay("2023-24")) == 19.8
    assert v(st6, "st6.worker_share.helper.rural.female", ay("2022-23")) == 43.1
    assert v(st6, "st6.worker_share.regular_wage.urban.male", ay("2021-22")) == 46.2
    for sec in ("rural", "urban", "total"):
        for sex in ("male", "female", "person"):
            s = f".{sec}.{sex}"
            checks.assert_no_rows(
                checks.check_identity(
                    st6,
                    f"st6.worker_share.self_employed{s}",
                    [f"st6.worker_share.own_account_employer{s}", f"st6.worker_share.helper{s}"],
                    abs_tol=0.11,
                ),
                f"SE = own account + helper {s}",
            )
            checks.assert_no_rows(
                checks.check_identity(
                    st6,
                    f"st6.worker_share.all{s}",
                    [
                        f"st6.worker_share.self_employed{s}",
                        f"st6.worker_share.regular_wage{s}",
                        f"st6.worker_share.casual_labour{s}",
                    ],
                    abs_tol=0.11,
                ),
                f"all = SE + regular + casual {s}",
            )
    assert set(st6.filter(pl.col("item_code") == "worker_share_all")["value"]) == {100.0}


def test_plfs_industry_distribution(ind):
    # Statement 7, p.44 (printed 15): agriculture share 2023-24 rural+urban person 46.1; urban female other services 40.1
    assert v(ind, "st7.worker_share.a.total.person", ay("2023-24")) == 46.1
    assert v(ind, "st7.worker_share.k-u.urban.female", ay("2023-24")) == 40.1
    assert v(ind, "st7.worker_share.h_j.total.person", ay("2022-23")) == 5.4
    # Table 26, p.213 (printed A-150): section A 46.07; division 01 45.24; class 0111 13.24 (rural+urban person)
    assert v(ind, "t26.worker_share.a.total.person", ay("2023-24")) == 46.07
    assert v(ind, "t26.worker_share.01.total.person", ay("2023-24")) == 45.24
    assert v(ind, "t26.worker_share.0111.total.person", ay("2023-24")) == 13.24
    # p.228 (printed A-165): sample workers rural+urban person 1,83,070; section T urban female 10.90
    assert v(ind, "t26.sample_workers.total.person", ay("2023-24")) == 183070
    assert v(ind, "t26.worker_share.t.urban.female", ay("2023-24")) == 10.90
    t26 = ind.filter(pl.col("table_id") == "Table (26)")
    sec = t26.filter(pl.col("item_code") == "worker_share_nic_section")
    for sid_sfx in ("total.person", "rural.male", "urban.female"):
        s = sec.filter(pl.col("series_id").str.ends_with(sid_sfx))["value"].sum()
        assert abs(s - 100) < 0.2, (sid_sfx, s)
    # divisions add up to their section (section letter from NIC-2008 division ranges)
    ranges = {
        "A": (1, 3),
        "B": (5, 9),
        "C": (10, 33),
        "D": (35, 35),
        "E": (36, 39),
        "F": (41, 43),
        "G": (45, 47),
        "H": (49, 53),
        "I": (55, 56),
        "J": (58, 63),
        "K": (64, 66),
        "L": (68, 68),
        "M": (69, 75),
        "N": (77, 82),
        "O": (84, 84),
        "P": (85, 85),
        "Q": (86, 88),
        "R": (90, 93),
        "S": (94, 96),
        "T": (97, 98),
    }
    div = t26.filter(pl.col("item_code") == "worker_share_nic_division").filter(
        pl.col("series_id").str.ends_with("total.person")
    )
    divs = {r["industry"][-2:]: r["value"] for r in div.iter_rows(named=True)}
    for letter, (a, b) in ranges.items():
        parts = [x for d, x in divs.items() if a <= int(d) <= b]
        total = v(ind, f"t26.worker_share.{letter.lower()}.total.person", ay("2023-24"))
        assert abs(sum(parts) - total) <= 0.02 * max(1, len(parts)), (letter, sum(parts), total)
    # Statement 7 broad groups agree with Table 26 sections to the published rounding
    pairs = {"a": ["a"], "c": ["c"], "f": ["f"], "g_i": ["g", "i"], "h_j": ["h", "j"]}
    for broad, secs in pairs.items():
        b = v(ind, f"st7.worker_share.{broad}.total.person", ay("2023-24"))
        s = sum(v(ind, f"t26.worker_share.{x}.total.person", ay("2023-24")) for x in secs)
        assert abs(b - s) <= 0.1, (broad, b, s)
    checks.assert_no_rows(checks.check_range(ind.filter(pl.col("unit") == "percent"), lo=0, hi=100), "share range")


def test_plfs_earnings(earn):
    # Statement 10, p.47 (printed 18): regular wage/salary, rural+urban person: Jul-Sep 2023 20095; Apr-Jun 2024 21103
    assert v(earn, "st10.regular_wage_earnings_month.total.person.current", "Q2 2023-24") == 20095
    assert v(earn, "st10.regular_wage_earnings_month.total.person.current", "Q1 2024-25") == 21103
    assert v(earn, "st10.regular_wage_earnings_month.rural.female.current", "Q3 2023-24") == 12557
    # Statement 11, p.48 (printed 19): casual wage per day, rural+urban person Jan-Mar 2024 419; urban male Apr-Jun 537
    assert v(earn, "st11.casual_wage_earnings_day.total.person.current", "Q4 2023-24") == 419
    assert v(earn, "st11.casual_wage_earnings_day.urban.male.current", "Q1 2024-25") == 537
    # Statement 12, p.48: self-employment gross earnings (30 days), rural+urban person Oct-Dec 2023 13044
    assert v(earn, "st12.self_employment_gross_earnings_30d.total.person.current", "Q3 2023-24") == 13044
    # Table 51, pp.406-408 (printed A-343..A-345): casual wage per day by NIC section
    assert v(earn, "t51.casual_wage_day.all.total.person.current", ay("2023-24")) == 408.48
    assert v(earn, "t51.casual_wage_day.a.total.person.current", ay("2023-24")) == 333
    assert v(earn, "t51.casual_wage_day.a.rural.male.current", ay("2023-24")) == 373
    assert v(earn, "t51.casual_wage_day.f.total.person.current", ay("2023-24")) == 447
    assert v(earn, "t51.sample_days.all.total.person", ay("2023-24")) == 143979
    # Note 2: zero = no sample observation -> not ingested (section U everywhere; J rural female)
    assert not earn.filter(pl.col("series_id").str.starts_with("t51.casual_wage_day.u.")).height
    assert not earn.filter(pl.col("series_id") == "t51.casual_wage_day.j.rural.female.current").height
    # the annual casual wage (all sections) lies within the range of the four quarterly values
    q = earn.filter(pl.col("series_id") == "st11.casual_wage_earnings_day.total.person.current")["value"]
    assert q.min() - 5 <= 408.48 <= q.max() + 5
    # earnings are positive rupees, and ordered: regular monthly > self-employed monthly > casual daily
    checks.assert_no_rows(checks.check_range(earn.filter(pl.col("unit") == "INR"), lo=1, hi=100000), "earnings range")
    quarters = earn.filter(pl.col("period_type") == "fq")
    assert set(quarters["period"]) == {"Q2 2023-24", "Q3 2023-24", "Q4 2023-24", "Q1 2024-25"}
    for p in quarters["period"].unique():
        assert (
            v(earn, "st10.regular_wage_earnings_month.total.person.current", p)
            > v(earn, "st12.self_employment_gross_earnings_30d.total.person.current", p)
            > 30 * v(earn, "st11.casual_wage_earnings_day.total.person.current", p) * 0.5
        )
    # One quarter-on-quarter move above 10%: rural female regular wages Jul-Sep 11,071 -> Oct-Dec 12,557
    # (Statement 10, small sample of 914 rural female regular employees per Table 38). Published as is.
    brk = checks.check_continuity(quarters, max_rel_change=0.1)
    assert set(zip(brk["series_id"], brk["to_period"])) <= {
        ("st10.regular_wage_earnings_month.rural.female.current", "Q3 2023-24")
    }, brk


# ---------------------------------------------------------------------------------------------
# ASUSE
# ---------------------------------------------------------------------------------------------


def test_asuse_factsheet_anchor_values(fs):
    # Factsheet Table 1, p.6 (printed 4): GVA Rs crore 15,42,409 (2022-23) and 17,97,278 (2023-24)
    assert v(fs, "fs.gva.asuse_all.total.current", osy("2022-23")) == 1542409
    assert v(fs, "fs.gva.asuse_all.total.current", osy("2023-24")) == 1797278
    assert v(fs, "fs.gva.asuse_all.urban.current", osy("2023-24")) == 1160949
    # establishments 7,33,995 ('00) and workers 12,05,998 ('00) in 2023-24 -> counts
    assert v(fs, "fs.establishments.asuse_all.total", osy("2023-24")) == 73399500
    assert v(fs, "fs.workers.asuse_all.total", osy("2023-24")) == 120599800
    # Table 2, p.8 (printed 6): GVA manufacturing 3,80,341 (2023-24); workers other services 4,71,026 ('00)
    assert v(fs, "fs.gva.asuse_m.total.current", osy("2023-24")) == 380341
    assert v(fs, "fs.workers.asuse_s.total", osy("2023-24")) == 47102600
    # Table 3, p.10 (printed 8): emoluments per hired worker 1,41,071; GVA per worker 1,49,742; per estt 2,45,687
    assert v(fs, "fs.emol_per_hired_worker.asuse_all.total.current", osy("2023-24")) == 141071
    assert v(fs, "fs.gva_per_worker.asuse_all.total.current", osy("2023-24")) == 149742
    assert v(fs, "fs.gva_per_estt.asuse_all.total.current", osy("2022-23")) == 238168
    # Table 6, p.12: other services % hired worker establishments, urban 2023-24 19.25
    assert v(fs, "fs.pct_hwe.asuse_s.urban", osy("2023-24")) == 19.25


def test_asuse_factsheet_identities(fs):
    for item, tol in (("gva", 1.0), ("establishments", 100.0), ("workers", 100.0)):
        sfx = ".current" if item == "gva" else ""
        checks.assert_no_rows(
            checks.check_identity(
                fs,
                f"fs.{item}.asuse_all.total{sfx}",
                [f"fs.{item}.asuse_all.rural{sfx}", f"fs.{item}.asuse_all.urban{sfx}"],
                abs_tol=tol,
            ),
            f"ASUSE {item}: rural + urban = total",
        )
        # M + T + S = all, except the tiny non-captive electricity category E (not tabulated): < 0.1%
        checks.assert_no_rows(
            checks.check_identity(
                fs,
                f"fs.{item}.asuse_all.total{sfx}",
                [f"fs.{item}.asuse_{b}.total{sfx}" for b in "mts"],
                abs_tol=tol,
                rel_tol=1e-3,
            ),
            f"ASUSE {item}: M + T + S ~ all",
        )
    # GVA per worker x workers ~ GVA (the ratio is market establishments only; within 3%)
    for p in (osy("2022-23"), osy("2023-24")):
        implied = v(fs, "fs.gva_per_worker.asuse_all.total.current", p) * v(fs, "fs.workers.asuse_all.total", p) / 1e7
        assert abs(implied / v(fs, "fs.gva.asuse_all.total.current", p) - 1) < 0.03, (p, implied)
    checks.assert_no_rows(checks.check_range(fs.filter(pl.col("unit") == "percent"), lo=0, hi=100), "percent")
    assert fs["dim_other"].is_null().all() and set(fs["period_type"]) == {"sy"}


def test_asuse_report_anchor_values(act):
    # Table 4, PDF p.89 (printed A8): rural HWE establishments, M2 food products 1,50,875; all 27,91,253
    assert v(act, "t4.establishments.asuse_m2.rural.hwe", osy("2023-24")) == 150875
    assert v(act, "t4.establishments.asuse_all.rural.hwe", osy("2023-24")) == 2791253
    # Table 6, p.134 (printed A53): rural HWE, M2 proprietary all 969 per 1000 -> 96.9%; S8 SHG (p.135) 390 -> 39.0%
    assert v(act, "t6.estt_share.proprietary_all.asuse_m2.rural.hwe", osy("2023-24")) == 96.9
    assert v(act, "t6.estt_share.shg.asuse_s8.rural.hwe", osy("2023-24")) == 39.0
    # Table 29, p.827 (printed A746): rural HWE, M2 full-time male workers 5,72,207
    assert v(act, "t29.workers.full_time.male.asuse_m2.rural.hwe", osy("2023-24")) == 572207
    # Table 33, p.1008 (printed A927): urban, M2 emoluments per hired worker (all) 1,37,909; hired workers 7,56,823
    assert v(act, "t33.emol_per_hired_worker.all.asuse_m2.urban.current", osy("2023-24")) == 137909
    assert v(act, "t33.hired_workers.all.asuse_m2.urban", osy("2023-24")) == 756823
    assert v(act, "t33.hired_workers.all.asuse_all.urban", osy("2023-24")) == 22359024
    # Table 35, p.1022 (printed A941): M1 rural OAE GVA per worker 73,864; M+T+E+S combined all 1,49,742
    assert v(act, "t35.gva_per_worker.asuse_m1.rural.oae.current", osy("2023-24")) == 73864
    assert v(act, "t35.gva_per_worker.asuse_all.total.all.current", osy("2023-24")) == 149742
    assert v(act, "t37.gva_per_estt.asuse_all.total.all.current", osy("2023-24")) == 245687


def test_asuse_report_identities_and_cross_checks(act, fs):
    P = osy("2023-24")
    # report totals equal the factsheet (factsheet is rounded to '00)
    assert abs(v(act, "t31.workers.total.all.asuse_all.total.all", P) - v(fs, "fs.workers.asuse_all.total", P)) <= 100
    assert (
        abs(v(act, "t4.establishments.asuse_all.total.all", P) - v(fs, "fs.establishments.asuse_all.total", P)) <= 100
    )
    for kind, fsid in (
        ("all", "emol_per_hired_worker"),
        ("formal", "emol_per_formal_hired_worker"),
        ("informal", "emol_per_informal_hired_worker"),
    ):
        assert v(act, f"t33.emol_per_hired_worker.{kind}.asuse_all.total.current", P) == v(
            fs, f"fs.{fsid}.asuse_all.total.current", P
        )
    assert v(act, "t35.gva_per_worker.asuse_all.total.all.current", P) == v(
        fs, "fs.gva_per_worker.asuse_all.total.current", P
    )
    # Table 29 and Table 31 give the same worker totals; Table 33 hired workers = Table 31 HWE hired workers
    for sec in ("rural", "urban", "total"):
        for est in ("oae", "hwe", "all"):
            a = v(act, f"t29.workers.all.all.asuse_all.{sec}.{est}", P)
            b = v(act, f"t31.workers.total.all.asuse_all.{sec}.{est}", P)
            assert abs(a - b) <= 0.001 * a + 5, (sec, est, a, b)
        hired31 = sum(v(act, f"t31.workers.{w}.all.asuse_all.{sec}.hwe", P) for w in ("formal_hired", "informal_hired"))
        assert abs(hired31 - v(act, f"t33.hired_workers.all.asuse_all.{sec}", P)) <= 0.001 * hired31, sec
    # Table 31: total = owners + formal hired + informal hired + unpaid family + other (combined, all)
    parts = [
        f"t31.workers.{w}.all.asuse_all.total.all"
        for w in ("working_owner", "formal_hired", "informal_hired", "unpaid_family", "other")
    ]
    checks.assert_no_rows(
        checks.check_identity(act, "t31.workers.total.all.asuse_all.total.all", parts, abs_tol=10), "T31 worker types"
    )
    # establishments: rural + urban = combined; OAE + HWE = all; M1..M25 = M (report rounding)
    for code in ("asuse_all", "asuse_m", "asuse_t5", "asuse_s13"):
        checks.assert_no_rows(
            checks.check_identity(
                act,
                f"t4.establishments.{code}.total.all",
                [f"t4.establishments.{code}.rural.all", f"t4.establishments.{code}.urban.all"],
                abs_tol=10,
            ),
            f"T4 rural+urban {code}",
        )
        checks.assert_no_rows(
            checks.check_identity(
                act,
                f"t4.establishments.{code}.total.all",
                [f"t4.establishments.{code}.total.oae", f"t4.establishments.{code}.total.hwe"],
                abs_tol=10,
            ),
            f"T4 OAE+HWE {code}",
        )
    checks.assert_no_rows(
        checks.check_identity(
            act,
            "t4.establishments.asuse_m.total.all",
            [f"t4.establishments.asuse_m{i}.total.all" for i in range(1, 26)],
            abs_tol=50,
        ),
        "T4 M = M1..M25",
    )
    # Table 6: ownership shares (cols 4-10) add up to 1000 per mille, up to rounding of 7 cells
    t6 = act.filter(pl.col("table_id") == "Table 6")
    keep = [
        "proprietary_all",
        "partnership_same_hh",
        "partnership_diff_hh",
        "shg",
        "society_trust",
        "cooperative",
        "others",
    ]
    g = (
        t6.with_columns(pl.col("dim_other").str.extract(r"ownership=(\w+)").alias("own"))
        .filter(pl.col("own").is_in(keep))
        .group_by("industry", "household_group", pl.col("dim_other").str.extract(r"estt_type=(\w+)").alias("est"))
        .agg(pl.col("value").sum())
    )
    bad = g.filter(((pl.col("value") - 100).abs() > 0.45) & (pl.col("value") > 0))
    assert bad.height == 0, bad
    checks.assert_no_rows(checks.check_range(act.filter(pl.col("unit") == "percent"), lo=0, hi=100), "percent")
    checks.assert_no_rows(checks.check_range(act.filter(pl.col("unit") != "percent"), lo=0), "negative counts/rupees")


# ---------------------------------------------------------------------------------------------
# ASI 2023-24
# ---------------------------------------------------------------------------------------------


def test_asi_statement_3a(asi_hist):
    # Summary Results Statement 3A, PDF p.34 (printed S3-5); Rs lakh -> Rs crore (/100)
    assert v(asi_hist, "s3a.gva.current", "2023-24") == pytest.approx(2458336.05)
    assert v(asi_hist, "s3a.gva.current", "2019-20") == pytest.approx(1485745.12)
    assert v(asi_hist, "s3a.total_emoluments.current", "2023-24") == pytest.approx(716469.03)
    assert v(asi_hist, "s3a.wages_to_workers.current", "2022-23") == pytest.approx(299903.80)
    assert v(asi_hist, "s3a.factories_in_operation", "2023-24") == 212990
    assert v(asi_hist, "s3a.persons_engaged", "2023-24") == 19589131
    for p in ("2019-20", "2020-21", "2021-22", "2022-23", "2023-24"):
        checks.assert_no_rows(
            checks.check_identity(
                asi_hist.filter(pl.col("period") == p),
                "s3a.nva.current",
                {"s3a.gva.current": 1, "s3a.depreciation.current": -1},
                abs_tol=0.02,
            ),
            f"NVA {p}",
        )
        checks.assert_no_rows(
            checks.check_identity(
                asi_hist.filter(pl.col("period") == p),
                "s3a.gva.current",
                {"s3a.total_output.current": 1, "s3a.total_input.current": -1},
                abs_tol=0.02,
            ),
            f"GVA {p}",
        )
    assert (asi_hist["value"] > 0).all()
    # Statement 3B prints the growth rates: input +37.4% and output +35.4% in 2021-22, net profit +54.8%
    # in 2021-22 and +30.8% in 2020-21 (post-COVID recovery and prices). Anything else > 40% is a break.
    brk = checks.check_continuity(asi_hist, max_rel_change=0.40)
    assert set(zip(brk["series_id"], brk["to_period"])) <= {("s3a.net_profit.current", "2021-22")}, brk


def test_asi_industry(asi_ind, asi_hist):
    P = "2023-24"
    # Statement 5A, p.39 (printed S4-4): basic metals (24) GVA 2,84,23,673 lakh; all industries persons engaged 1,95,89,131
    assert v(asi_ind, "s5a.gva.24.current", P) == pytest.approx(284236.73)
    assert v(asi_ind, "s5a.persons_engaged.all", P) == 19589131
    assert v(asi_ind, "s5a.gva_share.24", P) == 11.56
    # Volume I Table 3, PDF p.320 (printed T3-1): All: workers 1,55,19,957; wages to workers 3,35,98,653 lakh
    assert v(asi_ind, "v1t3.workers.all", P) == 15519957
    assert v(asi_ind, "v1t3.wages_salary_workers.all.current", P) == pytest.approx(335986.53)
    assert v(asi_ind, "v1t3.workers_direct_women.1020", P) == 45923  # p.320, class 1020 (fish processing)
    # p.334 (printed T3-15): class 'Other' persons engaged 5,89,847
    assert v(asi_ind, "v1t3.persons_engaged.other", P) == 589847
    # cross-table: Vol I Table 3 'All' = Summary Statement 3A = Statement 5A
    assert v(asi_ind, "v1t3.persons_engaged.all", P) == v(asi_hist, "s3a.persons_engaged", P)
    assert v(asi_ind, "v1t3.wages_salary_incl_bonus.all.current", P) == pytest.approx(
        v(asi_hist, "s3a.total_emoluments.current", P)
    )
    assert v(asi_ind, "v1t3.wages_salary_workers.all.current", P) == pytest.approx(
        v(asi_hist, "s3a.wages_to_workers.current", P)
    )
    assert v(asi_ind, "s5a.gva.all.current", P) == pytest.approx(v(asi_hist, "s3a.gva.current", P))
    # identities for every NIC class
    classes = {s.rsplit(".", 1)[-1] for s in asi_ind.filter(pl.col("item_code") == "workers")["series_id"]}
    assert len(classes) == 150
    for c in classes:
        for tot, parts, tol in (
            ("workers", ["workers_direct", "workers_contract"], 3.0),  # estimates rounded independently
            ("persons_engaged", ["workers", "employees_other_than_workers", "unpaid_family_proprietor"], 3.0),
        ):
            checks.assert_no_rows(
                checks.check_identity(asi_ind, f"v1t3.{tot}.{c}", [f"v1t3.{p}.{c}" for p in parts], abs_tol=tol),
                f"{tot} {c}",
            )
        # men + women fall short of 'directly employed' in a few classes (All: 90,64,912 vs 90,65,536;
        # largest gap 0.74% in class 2392). The table does not say why (other genders?); never above it.
        d = v(asi_ind, f"v1t3.workers_direct.{c}", P)
        mw = v(asi_ind, f"v1t3.workers_direct_men.{c}", P) + v(asi_ind, f"v1t3.workers_direct_women.{c}", P)
        assert mw <= d + 1 and d - mw <= max(1.0, 0.01 * d), (c, d, mw)
        checks.assert_no_rows(
            checks.check_identity(
                asi_ind,
                f"v1t3.wages_salaries_incl_employer_contrib.{c}.current",
                [f"v1t3.wages_salary_incl_bonus.{c}.current", f"v1t3.employers_contribution.{c}.current"],
                abs_tol=0.02,
            ),
            f"C = C1 + C2 {c}",
        )
    # 2-digit divisions (plus 'other') add up to all industries, within publisher rounding
    div = asi_ind.filter(
        (pl.col("item_code") == "gva") & (pl.col("table_id") == "Statement 5A") & (pl.col("industry") != "nic2008_all")
    )
    assert abs(div["value"].sum() / v(asi_ind, "s5a.gva.all.current", P) - 1) < 1e-4
    checks.assert_no_rows(checks.check_range(asi_ind, lo=0), "negative ASI values")


# ---------------------------------------------------------------------------------------------
# AIDIS 2019 press note and SAS 2019
# ---------------------------------------------------------------------------------------------


def test_aidis_press_note(aidis):
    D = "2018-06-30"
    # press note p.3: AVA rural 15,92,379 (cultivator 22,07,257); urban 27,17,081; physical + financial = total
    assert v(aidis, "pn.ava_per_hh.rural.all.current", D) == 1592379
    assert v(aidis, "pn.ava_per_hh.rural.cultivator.current", D) == 2207257
    assert v(aidis, "pn.ava_per_hh.urban.all.current", D) == 2717081
    for sec in ("rural", "urban"):
        checks.assert_no_rows(
            checks.check_identity(
                aidis,
                f"pn.ava_per_hh.{sec}.all.current",
                [f"pn.ava_physical_per_hh.{sec}.all.current", f"pn.ava_financial_per_hh.{sec}.all.current"],
            ),
            f"AVA physical + financial {sec}",
        )
        shares = aidis.filter(
            pl.col("item_code").is_in(
                ["asset_share_land", "asset_share_building", "asset_share_deposits", "asset_share_other"]
            )
            & (pl.col("household_group") == sec)
        )
        assert abs(shares["value"].sum() - 100) <= 1, sec
    # p.4-5: IOI rural cultivator 40.3; AOD rural 59,748, urban 1,20,336; AODL urban 5,36,861
    assert v(aidis, "pn.incidence_of_indebtedness.rural.cultivator", D) == 40.3
    assert v(aidis, "pn.aod_per_hh.rural.all.current", D) == 59748
    assert v(aidis, "pn.aod_per_hh.urban.all.current", D) == 120336
    assert v(aidis, "pn.aod_per_indebted_hh.urban.all.current", D) == 536861
    # p.5-6: fixed capital expenditure 2018-19 (Jul-Jun): rural 8,966, urban 10,863
    assert v(aidis, "pn.fce_per_hh.rural.all.current", "2018-07/2019-06") == 8966
    assert v(aidis, "pn.fce_per_hh.urban.all.current", "2018-07/2019-06") == 10863
    assert v(aidis, "pn.pct_adults_with_bank_deposit_account.urban.female", "2019") == 81.3
    # institutional-only + non-institutional-only + both = incidence of indebtedness (to rounding)
    for sec, who in (("rural", "all"), ("rural", "cultivator"), ("urban", "self_employed"), ("urban", "other")):
        parts = sum(
            v(aidis, f"pn.pct_hh_indebted_{k}.{sec}.{who}", D)
            for k in ("institutional_only", "noninstitutional_only", "both")
        )
        assert abs(parts - v(aidis, f"pn.incidence_of_indebtedness.{sec}.{who}", D)) <= 0.6, (sec, who, parts)
    for sec in ("rural", "urban"):
        assert (
            v(aidis, f"pn.debt_share_institutional.{sec}.all", D)
            + v(aidis, f"pn.debt_share_noninstitutional.{sec}.all", D)
            == 100
        )
    assert aidis.height == 87


def test_sas_income_by_land_class(sas):
    P = "2018-07/2019-06"
    # Statement 5.1A, PDF p.114 (printed 84): all sizes total 10,218; wages 4,063; 10.00+ ha crop 43,599
    assert v(sas, "s5_1a.income_total.agri_all.current", P) == 10218
    assert v(sas, "s5_1a.income_wages.agri_all.current", P) == 4063
    assert v(sas, "s5_1a.income_crop_production_net.agri_land_gt10.00.current", P) == 43599
    # Statement 5.1B, p.116 (printed 86): all sizes total 8,337; 0.01-0.40 ha animals 349
    assert v(sas, "s5_1b.income_total.agri_all.current", P) == 8337
    assert v(sas, "s5_1b.income_farming_animals_net.agri_land_0.01-0.40.current", P) == 349
    # Statement 1.1, p.75 (printed 45): 93.094 million agricultural households
    assert v(sas, "s1_1.households.agri_all", P) == pytest.approx(93.094e6)
    checks.assert_no_rows(
        checks.check_identity(
            sas,
            "s1_1.households.rural_all",
            ["s1_1.households.agri_all", "s1_1.households.rural_nonagri_all"],
            abs_tol=1500,
        ),
        "rural hh",
    )
    # Statement 5.7, p.123 (printed 93): outstanding loan per agricultural household 74,121; 50.2% indebted
    assert v(sas, "s5_7.outstanding_loan_per_hh.agri_all.current", P) == 74121
    assert v(sas, "s5_7.pct_indebted.agri_all", P) == 50.2
    for st in ("s5_1a", "s5_1b"):
        for hh in sas.filter(pl.col("series_id").str.starts_with(f"{st}.income_total"))["household_group"]:
            parts = [
                f"{st}.income_{c}.{hh}.current"
                for c in (
                    "wages",
                    "leasing_out_land",
                    "crop_production_net",
                    "farming_animals_net",
                    "nonfarm_business_net",
                )
            ]
            checks.assert_no_rows(
                checks.check_identity(sas, f"{st}.income_total.{hh}.current", parts, abs_tol=3), f"{st} {hh}"
            )
    # land-class shares of agricultural households (Statement 1.3) add up to 100 (rounding)
    s13 = sas.filter(pl.col("item_code") == "agri_hh_share_by_land_class")
    assert abs(s13.filter(pl.col("household_group") != "agri_all")["value"].sum() - 100) <= 0.5
    # income rises with land size (total, paid-out basis) above 0.01-0.40 ha
    order = [
        "agri_land_0.01-0.40",
        "agri_land_0.41-1.00",
        "agri_land_1.01-2.00",
        "agri_land_2.01-4.00",
        "agri_land_4.01-10.00",
        "agri_land_gt10.00",
    ]
    tot = [v(sas, f"s5_1a.income_total.{h}.current", P) for h in order]
    assert tot == sorted(tot)
    assert set(sas["period_type"]) == {"sy"} and not sas["dim_other"].fill_null("").str.contains("survey_year").any()
    # VER-C1: every statement, 1.3 included, carries the agricultural year printed in its title
    # (St 1.3: "for the agricultural year July 2018 - June 2019"); 1.3's July-December 2018 land
    # basis (visit 1, the table's footnote) is stated in its provenance note, not in the period
    assert set(s13["period"]) == {P}
    assert set(sas["period"]) == {P}


def test_every_dataset_has_reference_or_latest_year():
    """Each dataset carries its latest survey year (2023-24 for PLFS/ASUSE/ASI; 2019 round for AIDIS/SAS;
    Q1 2023-24 for the API earnings; calendar 2025 for ASUSE 2025)."""
    want = {
        "plfs_lfs_indicators": ay("2023-24"),
        "plfs_status_dist": ay("2023-24"),
        "plfs_industry_dist": ay("2023-24"),
        "plfs_industry_status": ay("2023-24"),
        "plfs_enterprise_type": ay("2023-24"),
        "plfs_earnings": ay("2023-24"),
        "asuse_key_indicators": osy("2023-24"),
        "asuse_2324_activity": osy("2023-24"),
        "asi_principal_characteristics": "2023-24",
        "asi_2324_industry": "2023-24",
        "aidis_2019_press_note": "2018-06-30",
        "sas_2019_income_by_landclass": "2018-07/2019-06",
        "aidis_2019_quintile": "2018-06-30",
        "plfs_earnings_api": "Q1 2023-24",
        "asuse_2025_assets_loans": "2025",
    }
    for name, period in want.items():
        d = load(name)
        assert d.filter(pl.col("period") == period).height > 0, name
        assert set(d["status"]) == {"official"}, name


# ---------------------------------------------------------------------------------------------
# Added after verification (verifier findings VER-1, VER-3, VER-4, VER-5, VER-6)
# ---------------------------------------------------------------------------------------------

T20_GROUPS = ["01-03", "05-09", "10-33", "35-39", "41-43", "05-43", "45-47", "49-53", "55-56", "58-99", "45-99", "all"]
BLOCKS = [(s, x) for s in ("rural", "urban", "total") for x in ("male", "female", "person")]


def test_plfs_table20_industry_x_status(st6):
    t20 = load("plfs_industry_status")
    # Table (20), p.147 (printed A-84), rural male: manufacturing regular 51.4; total casual 24.9; sample 69,969
    assert v(t20, "t20.worker_share.regular_wage.10-33.rural.male", ay("2023-24")) == 51.4
    assert v(t20, "t20.worker_share.casual_labour.all.rural.male", ay("2023-24")) == 24.9
    assert v(t20, "t20.sample_workers.all.rural.male", ay("2023-24")) == 69969
    # p.149 (A-86), rural persons, '10-33 (manufacturing) 45.3 8.4 53.7 35.5 10.7 100.0'
    assert [
        v(t20, f"t20.worker_share.{st}.10-33.rural.person", ay("2023-24"))
        for st in ("own_account_employer", "helper", "self_employed", "regular_wage", "casual_labour", "all")
    ] == [45.3, 8.4, 53.7, 35.5, 10.7, 100.0]
    # p.155 (A-92), rural+urban persons: construction casual 80.6; sample workers 1,83,070
    assert v(t20, "t20.worker_share.casual_labour.41-43.total.person", ay("2023-24")) == 80.6
    assert v(t20, "t20.sample_workers.all.total.person", ay("2023-24")) == 183070
    assert t20.height == 9 * (12 * 6 + 6)
    assert set(t20["industry"]) == {f"nic2008_{g}" for g in T20_GROUPS}
    assert set(t20["period"]) == {ay("2023-24")} and set(t20["period_type"]) == {"sy"}
    for sec, sex in BLOCKS:
        for g in T20_GROUPS:
            s = f".{g}.{sec}.{sex}"
            checks.assert_no_rows(
                checks.check_identity(
                    t20, f"t20.worker_share.self_employed{s}",
                    [f"t20.worker_share.own_account_employer{s}", f"t20.worker_share.helper{s}"], abs_tol=0.11,
                ),
                f"T20 SE = own account + helper {s}",
            )
            checks.assert_no_rows(
                checks.check_identity(
                    t20, f"t20.worker_share.all{s}",
                    [f"t20.worker_share.self_employed{s}", f"t20.worker_share.regular_wage{s}", f"t20.worker_share.casual_labour{s}"],
                    abs_tol=0.11,
                ),
                f"T20 100 = SE + regular + casual {s}",
            )
        n = f".{sec}.{sex}"
        checks.assert_no_rows(
            checks.check_identity(
                t20, f"t20.sample_workers.all{n}",
                [f"t20.sample_workers.self_employed{n}", f"t20.sample_workers.regular_wage{n}", f"t20.sample_workers.casual_labour{n}"],
                abs_tol=0,
            ),
            f"T20 sample workers add up {n}",
        )
        # the 'total' row of each block is Statement 6 for 2023-24 (same survey, same concept)
        for st in ("own_account_employer", "helper", "self_employed", "regular_wage", "casual_labour"):
            a = v(t20, f"t20.worker_share.{st}.all{n}", ay("2023-24"))
            b = v(st6, f"st6.worker_share.{st}{n}", ay("2023-24"))
            assert abs(a - b) <= 0.11, (st, sec, sex, a, b)
    assert set(t20.filter(pl.col("item_code") == "worker_share_all")["value"]) == {100.0}
    checks.assert_no_rows(
        checks.check_range(t20.filter(pl.col("unit") == "percent"), lo=0, hi=100), "T20 shares in [0, 100]"
    )


def test_plfs_table35_enterprise_type():
    t35 = load("plfs_enterprise_type")
    # Table (35), p.274 (printed A-211), rural male 'all India 82.7 7.2 0.1 7.6 0.1 0.8 0.6 0.8 100.0 37,075'
    codes = ["proprietary_partnership", "govt_public_sector", "autonomous_bodies", "pvt_public_ltd_company",
             "cooperative_societies", "trust_nonprofit", "employer_households", "others", "all"]
    assert [v(t35, f"t35.worker_share.{c}.rural.male", ay("2023-24")) for c in codes] == [82.7, 7.2, 0.1, 7.6, 0.1, 0.8, 0.6, 0.8, 100.0]
    assert v(t35, "t35.sample_workers.all.rural.male", ay("2023-24")) == 37075
    # p.282 (A-219), rural+urban persons: govt/public sector 10.6; sample proprietary 78,732; total 1,10,937
    assert v(t35, "t35.worker_share.govt_public_sector.total.person", ay("2023-24")) == 10.6
    assert v(t35, "t35.sample_workers.proprietary_partnership.total.person", ay("2023-24")) == 78732
    assert v(t35, "t35.sample_workers.all.total.person", ay("2023-24")) == 110937
    assert t35.height == 9 * 9 * 2
    assert set(t35["industry"]) == {"nic2008_05-99"}
    for sec, sex in BLOCKS:
        n = f".{sec}.{sex}"
        checks.assert_no_rows(
            checks.check_identity(t35, f"t35.worker_share.all{n}", [f"t35.worker_share.{c}{n}" for c in codes[:-1]], abs_tol=0.41),
            f"T35 shares add to 100 {n}",
        )
        checks.assert_no_rows(
            checks.check_identity(t35, f"t35.sample_workers.all{n}", [f"t35.sample_workers.{c}{n}" for c in codes[:-1]], abs_tol=0),
            f"T35 sample workers add up {n}",
        )
    # p.275 (A-212) rural female govt/public sector 24.5; p.278 (A-215) urban female 12.5 (rural
    # non-farm women are more often in government/public work than urban women in 2023-24)
    assert v(t35, "t35.worker_share.govt_public_sector.rural.female", ay("2023-24")) == 24.5
    assert v(t35, "t35.worker_share.govt_public_sector.urban.female", ay("2023-24")) == 12.5


def _notes(df, sid):
    prov = checks.load_provenance(U.UNIT)
    pid = df.filter(pl.col("series_id") == sid)["prov_id"].unique().to_list()
    assert len(pid) == 1, sid
    return prov.filter(pl.col("prov_id") == pid[0])["notes"][0] or ""


def test_provenance_notes_after_verification(aidis, earn, act, fs):
    # VER-6: whole-number prose values sit on their own provenance record, which lists them
    n = _notes(aidis, "pn.incidence_of_indebtedness.rural.all")
    assert "ROUNDED" in n and "pn.incidence_of_indebtedness.rural.all*" in n
    assert "pn.pct_hh_reporting_fce.urban.all*" in n and "pn.asset_share_land.urban.all*" in n
    assert "ROUNDED" not in _notes(aidis, "pn.incidence_of_indebtedness.rural.cultivator")
    assert "ROUNDED" not in _notes(aidis, "pn.ava_per_hh.rural.all.current")
    # VER-3: Statement 10 is for the preceding calendar month
    assert "preceding the interview" in _notes(earn, "st10.regular_wage_earnings_month.total.person.current")
    assert "preceding the interview" not in _notes(earn, "st11.casual_wage_earnings_day.total.person.current")
    # VER-5: ASUSE household_group is the establishment's location
    assert "LOCATION sector of the establishment" in _notes(act, "t4.establishments.asuse_m.total.all")
    assert "LOCATION sector of the establishment" in _notes(fs, "fs.gva.asuse_all.rural.current")



# ---------------------------------------------------------------------------------------------
# eSankhyiki API datasets (added at Phase 1 close-out: DECISIONS D1-6 legacy-TLS opt-in)
# ---------------------------------------------------------------------------------------------

D18 = "2018-06-30"


def test_aidis_quintile_api(aidis):
    q = load("aidis_2019_quintile")
    # anchors from the pinned API pages (nss77_aidis_i5_allindia_p1/p2, i9 p1): rural cultivators in
    # quintile class 1 are 170 per 1000 cultivator households with Rs 11,00,360 assets per household
    # and Rs 28,039 cash loan; urban all households: 224 per 1000 indebted
    assert v(q, "i5.hh_distribution.rural_q1.cultivator", D18) == 17.0
    assert v(q, "i5.ava_per_hh.rural_q1.cultivator.current", D18) == 1100360
    assert v(q, "i5.aod_per_hh.rural_q1.cultivator.current", D18) == 28039
    assert v(q, "i5.incidence_of_indebtedness.urban.all", D18) == 22.4
    assert v(q, "i9.fixed_assets_per_hh.rural.cultivator.ahc_d1.current", D18) == 42056
    assert v(q, "i9.valuables_per_hh.rural.cultivator.ahc_d1.current", D18) == 23063
    # the all-quintile rows equal the press note (a second publication of the same survey)
    for item in ("ava_per_hh", "aod_per_hh"):
        for sec, types in (
            ("rural", ("all", "cultivator", "non_cultivator")),
            ("urban", ("all", "self_employed", "other")),
        ):
            for t in types:
                assert v(q, f"i5.{item}.{sec}.{t}.current", D18) == v(aidis, f"pn.{item}.{sec}.{t}.current", D18)
    for sec, t in (("rural", "cultivator"), ("urban", "self_employed"), ("urban", "all")):
        ioi = f"incidence_of_indebtedness.{sec}.{t}"
        assert v(q, f"i5.{ioi}", D18) == v(aidis, f"pn.{ioi}", D18)
    # every category's households are spread over the five quintile classes (per 1000 -> 100%, rounding)
    dist = q.filter(pl.col("item_code") == "hh_distribution", pl.col("household_group").str.contains("_q"))
    g = dist.group_by(pl.col("household_group").str.slice(0, 5), "dim_other").agg(pl.col("value").sum())
    assert g.height == 6 and ((g["value"] - 100).abs() <= 0.25).all(), g
    # indicator 9: fixed + financial assets = indicator 5 'assets' (valuables are outside it); loans agree
    for hg in ("rural", "rural_q1", "rural_q5", "urban", "urban_q1", "urban_q5"):
        for t in ("all",):
            ff = v(q, f"i9.fixed_assets_per_hh.{hg}.{t}.current", D18)
            ff += v(q, f"i9.financial_assets_per_hh.{hg}.{t}.current", D18)
            assert abs(ff - v(q, f"i5.ava_per_hh.{hg}.{t}.current", D18)) <= 2, hg
            assert v(q, f"i9.cash_loan_per_hh.{hg}.{t}.current", D18) == v(q, f"i5.aod_per_hh.{hg}.{t}.current", D18)
    # wealth rises from the bottom to the top quintile class in both sectors (all households)
    for sec in ("rural", "urban"):
        a = [v(q, f"i5.ava_per_hh.{sec}_q{i}.all.current", D18) for i in range(1, 6)]
        assert a[0] < a[4], (sec, a)
    assert q.height == 144 + 6 * 16 * 4
    assert set(q["period"]) == {D18} and set(q["geography"]) == {"IN"}
    assert "NOT the SAM's HCES 2023-24" in _notes(q, "i5.ava_per_hh.rural_q1.all.current")


def test_plfs_earnings_api(earn):
    a = load("plfs_earnings_api")
    # April-June 2023 (agricultural year 2022-23, quarter Apr-Jun = Q1 2023-24), rural+urban person
    assert v(a, "api_i6.regular_wage_earnings_month.total.person.current", "Q1 2023-24") == 20039.2
    assert v(a, "api_i7.casual_wage_earnings_day.total.person.current", "Q1 2023-24") == 403.2
    assert v(a, "api_i8.self_employment_gross_earnings_30d.total.person.current", "Q1 2023-24") == 13347.4
    assert set(a["period"]) == {
        "Q2 2022-23", "Q3 2022-23", "Q4 2022-23", "Q1 2023-24", "Q2 2023-24", "Q3 2023-24", "Q4 2023-24", "Q1 2024-25"
    }
    assert a.height == 3 * 8 * 9
    # the agricultural year 2023-24 values are the AR 2023-24 Statements 10-12 (API one decimal, AR whole rupees)
    k = ["item_code", "household_group", "dim_other", "period"]
    j = a.join(earn.filter(pl.col("period_type") == "fq"), on=k, suffix="_pdf")
    assert j.height == 3 * 4 * 9
    assert ((j["value"] - j["value_pdf"]).abs() <= 0.5).all()
    assert (j["vintage"] == "2024-09-23").all()
    assert set(a.filter(pl.col("period") == "Q1 2023-24")["vintage"]) == {"2026-09-29"}
    # One move above 20%: rural female regular wages Jan-Mar 2023 11,336.8 -> Apr-Jun 2023 13,825.4 (+22%),
    # back to 11,071.3 in Jul-Sep 2023 (small sample, as in Statement 10). Published as is; logged.
    brk = checks.check_continuity(a, max_rel_change=0.2)
    assert set(zip(brk["series_id"], brk["to_period"])) == {
        ("api_i6.regular_wage_earnings_month.rural.female.current", "Q1 2023-24")
    }, brk


def test_asuse_2025_api():
    s = load("asuse_2025_assets_loans")
    assert s.height == 4500 and set(s["period"]) == {"2025"} and set(s["period_type"]) == {"cy"}
    # all activities, combined sector, all establishments (asuse_i36_allindia pages)
    base = "asuse_all.total.all"
    assert v(s, f"i36.rent_payable_hired_fixed_assets_per_estt.{base}.current", "2025") == 13575
    assert v(s, f"i36.interest_payable_per_estt.{base}.current", "2025") == 4338
    assert v(s, f"i36.outstanding_loan_per_estt.{base}.current", "2025") == 42776
    # owned + hired fixed assets ~ all (per-establishment averages over the same establishments)
    ok = 0
    for r in s.filter(pl.col("dim_other").str.contains("fixed_assets=all")).iter_rows(named=True):
        o = s.filter(pl.col("series_id") == r["series_id"].replace("fa_all", "fa_owned"))["value"]
        h = s.filter(pl.col("series_id") == r["series_id"].replace("fa_all", "fa_hired"))["value"]
        if len(o) and len(h):
            assert abs(o[0] + h[0] - r["value"]) <= max(2, 1e-4 * r["value"]), r["series_id"]
            ok += 1
    assert ok > 100
    checks.assert_no_rows(checks.check_range(s, lo=0), "negative per-establishment values")
    assert set(s["industry"]) >= {"asuse_all", "asuse_M8", "asuse_S10"}
