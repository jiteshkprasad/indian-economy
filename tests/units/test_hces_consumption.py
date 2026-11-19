"""Value tests for the hces_consumption unit.

Anchor values are read off the published files themselves:
- HCES 2023-24 Appendix-A Excel tables (MoSPI, 30 Jan 2025): Table A2 (TableA2.xlsx), Table A6,
  Table A10F, Table A10S, Table A10SW; HCES 2022-23 tables (June 2024).
- HCES 2023-24 Report No. 592 PDF, Tables 3.17 (p.51), 3.18 (p.52), 3.19 (p.53).
- CPI 2024=100 Expert Group report Annexure 5.3 (Annex_5.3.xlsx; PDF pp.108-112).
- NSS Report No. 596 (Health) Tables 2.21 (p.29) and 2.24 (p.32); NSS Report No. 595 (CMS
  Education 2025) Statement 2.3 (pp.13-14).
"""

import polars as pl
import pytest

from pipeline.core import checks
from pipeline.ingest import hces_consumption as U
from pipeline.ingest.hces_consumption import hces_tables as T

pytestmark = pytest.mark.quality
UNIT = U.UNIT

# Survey windows (period_type 'sy'): HCES runs August-July (Report 592 p.3 'August, 2023 - July, 2024';
# p.20 'August, 2022 to July, 2023'); NSS rounds 55-68 run July-June.
SY24, SY23 = "2023-08/2024-07", "2022-08/2023-07"


def _ds(name):
    return checks.load_dataset(UNIT, f"{UNIT}_{name}")


@pytest.fixture(scope="module")
def a2():
    return _ds("a2_fractile_persons")


@pytest.fixture(scope="module")
def a6():
    return _ds("a6_group_fractile")


@pytest.fixture(scope="module")
def a10f():
    return _ds("a10f_item_fractile")


@pytest.fixture(scope="module")
def a10s():
    return _ds("a10s_state_item")


@pytest.fixture(scope="module")
def a10sw():
    return _ds("a10sw_state_item_imputed")


@pytest.fixture(scope="module")
def r592():
    return _ds("report592_mpce")


@pytest.fixture(scope="module")
def cpi():
    return _ds("cpi2024_weights")


@pytest.fixture(scope="module")
def h596():
    return _ds("health596")


@pytest.fixture(scope="module")
def edu():
    return _ds("cms_education_2025")


def v(df, sid, period):
    return checks.value(df, sid, period)


# ---------------------------------------------------------------------------------------------
# Table A2
# ---------------------------------------------------------------------------------------------


# TableA2.xlsx (2023-24) rows 1014-1040 (All-India) and 6 (Andhra Pradesh rural 0-5%).
@pytest.mark.parametrize(
    "sid, expected",
    [
        ("a2.hces2324.avg_mpce.in.rural_all.current", 4121.79),
        ("a2.hces2324.avg_mpce.in.urban_all.current", 6996.26),
        ("a2.hces2324.avg_mpce.in.rural_p00_05.current", 1676.70),
        ("a2.hces2324.avg_mpce.in.urban_p95_100.current", 20309.80),
        ("a2.hces2324.avg_mpce.in-ap.rural_p00_05.current", 2178.36),
        ("a2.hces2324.households.in.rural_all", 1937838 * 100),
        ("a2.hces2324.households.in.urban_all", 978872 * 100),
        ("a2.hces2324.adults_persons.in.rural_all", 6369630 * 100),
        ("a2.hces2324.children_persons.in.urban_all", 733741 * 100),
        ("a2.hces2324.sample_households.in.rural_all", 154357),
        ("a2.hces2324.persons.in.rural_all", (6369630 + 2177724) * 100),
    ],
)
def test_a2_anchor_2023_24(a2, sid, expected):
    assert v(a2, sid, SY24) == pytest.approx(expected, abs=1e-6)


# Table A2.xlsx (2022-23), urban All-India 'All classes' row.
def test_a2_anchor_2022_23(a2):
    assert v(a2, "a2.hces2223.avg_mpce.in.urban_all.current", SY23) == pytest.approx(6458.7)
    assert v(a2, "a2.hces2223.households.in.urban_all", SY23) == pytest.approx(895030 * 100)


def test_a2_fractiles_add_up_and_are_person_fractiles(a2):
    """Persons over the 12 classes add to 'all classes' (rounding of hundreds), each class holds its
    nominal share of persons, and the person-weighted MPCE of the classes equals the published mean."""
    shares = {"p00_05": 5, "p05_10": 5, "p90_95": 5, "p95_100": 5}
    for period, rt in ((SY24, "hces2324"), (SY23, "hces2223")):
        for s in ("rural", "urban"):
            d = a2.filter((pl.col("period") == period) & (pl.col("geography") == "IN"))
            p = {r["household_group"]: r["value"] for r in d.filter(pl.col("item_code") == "persons").iter_rows(named=True)}
            m = {r["household_group"]: r["value"] for r in d.filter(pl.col("item_code") == "avg_mpce").iter_rows(named=True)}
            fr = [k for k in p if k.startswith(s + "_p")]
            assert len(fr) == 12
            tot = sum(p[k] for k in fr)
            assert tot == pytest.approx(p[f"{s}_all"], rel=1e-5)
            for k in fr:
                want = shares.get(k.split("_", 1)[1], 10)
                assert 100 * p[k] / tot == pytest.approx(want, abs=0.05), (period, k)
            wm = sum(p[k] * m[k] for k in fr) / tot
            assert wm == pytest.approx(m[f"{s}_all"], abs=0.02), (period, s, rt)


def test_a2_state_persons_add_to_all_india(a2):
    d = a2.filter((pl.col("item_code") == "persons") & pl.col("household_group").str.ends_with("_all"))
    for period in (SY24, SY23):
        for s in ("rural", "urban"):
            x = d.filter((pl.col("period") == period) & (pl.col("household_group") == f"{s}_all"))
            states = x.filter(pl.col("geography") != "IN")["value"].sum()
            ai = x.filter(pl.col("geography") == "IN")["value"][0]
            # All-India rural includes a special stratum (Table A1 note: rural households of
            # 'uninhabited villages'); in 2022-23 the States add to only 98.9% of All-India rural
            # persons (issue hces_consumption-6), in 2023-24 to 99.99%.
            lo = 0.985 if (period, s) == (SY23, "rural") else 0.998
            assert lo * ai <= states <= ai * 1.000001, (period, s, states / ai)


def test_a2_mpce_growth_between_rounds_is_plausible(a2):
    """Nominal MPCE (all classes) should rise 2022-23 -> 2023-24 in every State/sector, by < 25%."""
    m = a2.filter((pl.col("item_code") == "avg_mpce") & pl.col("household_group").str.ends_with("_all"))
    w = m.pivot(on="period", index=["geography", "household_group"], values="value")
    r = w.with_columns((pl.col(SY24) / pl.col(SY23)).alias("r"))
    checks.assert_no_rows(r.filter((pl.col("r") < 1.0) | (pl.col("r") > 1.25)), "MPCE growth outside [0%, 25%]")


def test_a2_units_and_signs(a2):
    checks.assert_no_rows(checks.check_range(a2, lo=0), "negative A2 values")
    assert set(a2.filter(pl.col("item_code") == "avg_mpce")["unit"]) == {"INR"}
    assert set(a2.filter(pl.col("item_code") != "avg_mpce")["unit"]) == {"count"}
    assert set(a2.filter(pl.col("item_code") == "persons")["status"]) == {"derived"}


# ---------------------------------------------------------------------------------------------
# Table A6
# ---------------------------------------------------------------------------------------------


# TableA6.xlsx (2023-24): row 5 (Andhra Pradesh rural cereal), All-India rural block.
@pytest.mark.parametrize(
    "sid, expected",
    [
        ("a6.hces2324.cereal.in-ap.rural_p00_05.current", 110.51),
        ("a6.hces2324.cereal.in-ap.rural_all.current", 250.32),
        ("a6.hces2324.total_expenditure.in-ap.rural_p95_100.current", 11161.24),
        ("a6.hces2324.food_total.in.rural_all.current", 1938.50),
        ("a6.hces2324.nonfood_total.in.rural_all.current", 2183.38),
        ("a6.hces2324.total_expenditure.in.rural_all.current", 4121.78),
        ("a6.hces2324.memo_imputed_rent.in.rural_all.current", 168.59),
        ("a6.hces2324.medical_hosp.in-ap.rural_p95_100.current", 1151.06),
    ],
)
def test_a6_anchor(a6, sid, expected):
    assert v(a6, sid, SY24) == pytest.approx(expected)


def test_a6_identities(a6):
    """Food + non-food = total for every State x class (the one known 0.10 break is All-India rural)."""
    for period, rt in ((SY24, "hces2324"), (SY23, "hces2223")):
        d = a6.filter(pl.col("period") == period)
        keys = d.filter(pl.col("item_code") == "value_per_person_30d").select("geography", "household_group").unique()
        for geo, hg in keys.iter_rows():
            g = geo.lower()
            ids = {f"a6.{rt}.{c}.{g}.{hg}.current": c for c in ("food_total", "nonfood_total", "total_expenditure")}
            x = d.filter(pl.col("series_id").is_in(list(ids)))
            val = {ids[s]: x2 for s, x2 in zip(x["series_id"], x["value"], strict=True)}
            tol = 0.11 if (period, geo, hg) == (SY24, "IN", "rural_all") else 0.03
            assert val["food_total"] + val["nonfood_total"] == pytest.approx(val["total_expenditure"], abs=tol), (
                period, geo, hg)


def test_a6_total_matches_a2_mpce(a6, a2):
    """Table A6 total expenditure per person = Table A2 average MPCE (same survey, same classes)."""
    for period, rt in ((SY24, "hces2324"), (SY23, "hces2223")):
        t = a6.filter((pl.col("period") == period) & pl.col("series_id").str.starts_with(f"a6.{rt}.total_expenditure."))
        m = a2.filter((pl.col("period") == period) & (pl.col("item_code") == "avg_mpce"))
        j = t.join(m, on=["geography", "household_group"], suffix="_a2")
        assert j.height == t.height == m.height
        # Rounding differences between the two tables reach 0.10 Rs; Lakshadweep rural 90-95% differs
        # by 0.13 (2023-24) and 0.36 (2022-23) Rs (issue hces_consumption-5): allow 0.11 Rs or 0.005%.
        diff = (pl.col("value") - pl.col("value_a2")).abs()
        checks.assert_no_rows(j.filter(diff > pl.max_horizontal(pl.lit(0.11), 5e-5 * pl.col("value_a2"))),
                              "A6 total != A2 MPCE")


# ---------------------------------------------------------------------------------------------
# Table A10F
# ---------------------------------------------------------------------------------------------


# TableA10F (2023-24): rows 5 (rice-free), 12-13, 10569-10587 (urban 95-100%).
def test_a10f_anchor_2023_24(a10f):
    p = SY24
    assert v(a10f, "a10f.hces2324.999.value.urban_p95_100.current", p) == pytest.approx(20309.79)
    assert v(a10f, "a10f.hces2324.102.value.urban_p95_100.current", p) == pytest.approx(177.06)
    assert v(a10f, "a10f.hces2324.539.value.urban_p95_100.current", p) == pytest.approx(2580.33)
    assert v(a10f, "a10f.hces2324.101.value.rural_p00_05.current", p) == pytest.approx(5.28)
    # rice-free: quantity 2.405 kg per person per 30 days, value '##' (not collected), 49,710 (00) households
    assert v(a10f, "a10f.hces2324.061.qty.rural_p00_05", p) == pytest.approx(0.002405)
    assert v(a10f, "a10f.hces2324.061.hh_reporting.rural_p00_05", p) == pytest.approx(4971000)
    assert a10f.filter(pl.col("series_id") == "a10f.hces2324.061.value.rural_p00_05.current").height == 0
    # eggs: 7.363 (no.) per person, urban 95-100%
    assert v(a10f, "a10f.hces2324.190.qty.urban_p95_100", p) == pytest.approx(7.363)


# Table A10F (2022-23): row 5 (rice-free rural 0-5%: 1.975 kg, 36,273.65 (00) households).
def test_a10f_anchor_2022_23(a10f):
    assert v(a10f, "a10f.hces2223.061.qty.rural_p00_05", SY23) == pytest.approx(0.001975)
    assert v(a10f, "a10f.hces2223.061.hh_reporting.rural_p00_05", SY23) == pytest.approx(3627365)


def test_a10f_only_leaf_codes_are_additive(a10f):
    """Gap map C1a: the commodity key uses leaf codes only. Sub-totals and totals (099, 619, 649,
    983, 999, ...) must never be tagged leaf, and the leaf values of each class re-add to 999."""
    roles = dict(
        a10f.select(pl.col("product").str.replace("hces:", ""), pl.col("dim_other").str.extract(r"item_role=(\w+)"))
        .unique()
        .iter_rows()
    )
    for code in ("099", "129", "619", "649", "981", "982", "983", "984", "999"):
        assert roles[code] in ("subtotal", "total"), code
    assert roles["539"] == "memo" and roles["092"] == "aggregate" and roles["115"] == "memo_detail"
    assert roles["061"] == "leaf" and roles["102"] == "leaf" and roles["640"] == "leaf"
    val = a10f.filter(pl.col("item_code") == "value_per_person_30d")
    leaf = val.filter(pl.col("dim_other").str.contains("item_role=leaf")).group_by("period", "household_group").agg(
        pl.col("value").sum().alias("leaf_sum"))
    tot = val.filter(pl.col("product") == "hces:999").select("period", "household_group", "value")
    j = tot.join(leaf, on=["period", "household_group"])
    assert j.height == 48
    checks.assert_no_rows(j.filter((pl.col("value") - pl.col("leaf_sum")).abs() > 1.5), "leaf sum != 999 total")


def test_a10f_class_totals_match_a2(a10f, a2):
    """The item table's 999 'Total Expenditure' by class = Table A2 average MPCE of that class."""
    t = a10f.filter((pl.col("product") == "hces:999") & (pl.col("item_code") == "value_per_person_30d"))
    m = a2.filter((pl.col("item_code") == "avg_mpce") & (pl.col("geography") == "IN"))
    j = t.join(m, on=["period", "household_group"], suffix="_a2")
    assert j.height == 48
    checks.assert_no_rows(j.filter((pl.col("value") - pl.col("value_a2")).abs() > 0.02), "A10F 999 != A2 MPCE")


def test_a10f_quantities_units(a10f):
    q = a10f.filter(pl.col("item_code") == "qty_per_person_30d")
    assert set(q["unit"]) == {"tonnes", "count"}
    kg = q.filter(pl.col("unit") == "tonnes")
    # kg published to 3 decimals -> tonnes exact to 6 decimals; per-person monthly food < 50 kg
    checks.assert_no_rows(checks.check_range(kg, lo=0, hi=0.05), "implausible kg quantities")
    assert q.filter(pl.col("product") == "hces:005").height == 0  # 'cheese' quantity is not in kg: skipped
    assert q.filter(pl.col("product") == "hces:160").height == 0  # milk in litres: no unit in vocabulary


def test_a10f_values_non_negative(a10f):
    checks.assert_no_rows(checks.check_range(a10f, lo=0), "negative A10F values")


def test_item_classification_helpers():
    assert T.item_role("999") == "total" and T.item_role("649") == "subtotal" and T.item_role("640") == "leaf"
    assert T.qty_unit("101", "rice- PDS", "129") == "kg"
    assert T.qty_unit("190", "eggs (no.)", "199") == "number"
    assert T.qty_unit("160", "milk: liquid (litre)", "169") is None
    assert T.qty_unit("005", "cheese", "169") is None
    assert T.qty_unit("129", "cereal: sub-total", "129") is None
    # 2022-23 prints these four fruits without '(no.)'; 2023-24 prints '(no.)' (verifier finding, issue 24)
    for code, lab in (("223", "pineapple"), ("224", "coconut"), ("225", "green coconut"), ("228", "orange, mausami")):
        assert T.qty_unit(code, lab, "239", "2022-23") == "number"
        assert T.qty_unit(code, f"{lab} (no.)", "239", "2023-24") == "number"
    assert T.qty_unit("226", "guava", "239", "2022-23") == "kg"


def test_counted_fruit_quantities_are_counts_in_both_rounds(a10f, a10s):
    # HCES 2022-23 TableA10F rural 0-5%: 224 'coconut' qty 0.068, value Rs 1.49 (a count, not kg)
    for df in (a10f, a10s):
        q = df.filter((pl.col("item_code") == "qty_per_person_30d")
                      & pl.col("product").is_in(["hces:223", "hces:224", "hces:225", "hces:228"]))
        assert q.height > 0 and set(q["unit"].unique()) == {"count"}
        assert set(q["period"].unique()) == {SY23, SY24}
    r = a10f.filter((pl.col("period") == SY23) & (pl.col("product") == "hces:224")
                    & (pl.col("item_code") == "qty_per_person_30d") & (pl.col("household_group") == "rural_p00_05"))
    assert r.height == 1 and r["value"][0] == pytest.approx(0.068)
    assert "qty_published_unit=number" in r["dim_other"][0]


# ---------------------------------------------------------------------------------------------
# Tables A10S / A10SW
# ---------------------------------------------------------------------------------------------


def test_a10s_anchor(a10s, a10sw):
    # TableA10S-State.xlsx (2023-24) row 11: Andhra Pradesh rural rice - other sources, 4.116 kg, Rs 202.98
    assert v(a10s, "a10s.hces2324.102.value.in-ap.rural.current", SY24) == pytest.approx(202.98)
    assert v(a10s, "a10s.hces2324.102.qty.in-ap.rural", SY24) == pytest.approx(0.004116)
    # last rows of A10S / A10SW: urban All-India Total Expenditure 6,996.26 / 7,078.15 (with imputation)
    assert v(a10s, "a10s.hces2324.999.value.in.urban.current", SY24) == pytest.approx(6996.26)
    assert v(a10sw, "a10sw.hces2324.999.value.in.urban.current", SY24) == pytest.approx(7078.15)
    assert v(a10sw, "a10sw.hces2324.999.value.in.rural.current", SY24) == pytest.approx(4247.26)
    # A10SW row 5: Andhra Pradesh rural rice-free, imputed Rs 178.22 (A10S: '##')
    assert v(a10sw, "a10sw.hces2324.061.value.in-ap.rural.current", SY24) == pytest.approx(178.22)
    # Table_A10S-State.xlsx (2022-23) last row: urban All-India total 6,458.69
    assert v(a10s, "a10s.hces2223.999.value.in.urban.current", SY23) == pytest.approx(6458.69)


def test_a10s_totals_match_a2(a10s, a2):
    t = a10s.filter(pl.col("product") == "hces:999").with_columns(
        pl.col("household_group").alias("hg"))
    m = a2.filter(pl.col("item_code") == "avg_mpce")
    j = t.join(m, left_on=["period", "geography", "hg"], right_on=["period", "geography", "household_group"],
               suffix="_a2")
    assert j.height == t.height > 140
    checks.assert_no_rows(j.filter((pl.col("value") - pl.col("value_a2")).abs() > 0.11), "A10S 999 != A2 MPCE")


def test_imputation_raises_mpce_and_matches_report(a10s, a10sw, r592):
    """With-imputation MPCE >= without, in every State/sector; All-India matches Report Table 3.17."""
    a = a10s.filter((pl.col("product") == "hces:999") & (pl.col("period") == SY24))
    b = a10sw.filter(pl.col("product") == "hces:999")
    j = a.join(b, on=["geography", "household_group"], suffix="_w")
    assert j.height == a.height
    checks.assert_no_rows(j.filter(pl.col("value_w") < pl.col("value") - 0.01), "imputation lowered MPCE")
    for sec in ("rural", "urban"):
        rep = v(r592, f"t3_17.mpce_with_imputation.in.{sec}.current", SY24)
        tab = v(a10sw, f"a10sw.hces2324.999.value.in.{sec}.current", SY24)
        assert round(tab) == rep


# ---------------------------------------------------------------------------------------------
# Report 592
# ---------------------------------------------------------------------------------------------


# Report 592 Table 3.18 (p.52), Table 3.19 (p.53), Table 3.17 (p.51).
def test_report592_anchor(r592):
    assert v(r592, "t3_18.mpce.rural.current", "1999-07/2000-06") == 486
    assert v(r592, "t3_18.mpce.urban.current", "2011-07/2012-06") == 2630
    assert v(r592, "t3_18.mpce_with_imputation.urban.current", SY24) == 7078
    assert v(r592, "t3_18.mpce.urban.constant_2011_12", SY24) == 3632
    assert v(r592, "t3_19.food_total.mpce.rural.current", SY24) == 1939
    assert v(r592, "t3_19.beverages_processed.mpce.urban.current", SY24) == 776
    assert v(r592, "t3_19.consumer_services.share_with_imputation.urban", SY24) == pytest.approx(5.65)
    assert v(r592, "t3_19.cereals.share_with_imputation.rural", SY24) == pytest.approx(7.60)
    assert v(r592, "t3_17.mpce.in-kl.rural.current", SY24) == 6611
    assert v(r592, "t3_17.mpce_with_imputation.in-ts.urban.current", SY24) == 9131


def test_report592_consistent_with_tables(r592, a2):
    for sec in ("rural", "urban"):
        assert v(r592, f"t3_18.mpce.{sec}.current", SY24) == round(
            v(a2, f"a2.hces2324.avg_mpce.in.{sec}_all.current", SY24))
        assert v(r592, f"t3_18.mpce.{sec}.current", SY23) == round(
            v(a2, f"a2.hces2223.avg_mpce.in.{sec}_all.current", SY23))
        # Table 3.19: food + non-food = all items (to rounding) and shares add to 100
        f = v(r592, f"t3_19.food_total.mpce.{sec}.current", SY24)
        n = v(r592, f"t3_19.nonfood_total.mpce.{sec}.current", SY24)
        assert f + n == pytest.approx(v(r592, f"t3_19.all_items.mpce.{sec}.current", SY24), abs=1)
        assert v(r592, f"t3_19.food_total.share.{sec}", SY24) + v(
            r592, f"t3_19.nonfood_total.share.{sec}", SY24) == pytest.approx(100, abs=0.011)


def test_report592_real_mpce_continuity(r592):
    """Real MPCE rises round on round; the nominal 2011-12 -> 2022-23 jump (+164% rural) is 11 years
    of inflation plus the 2022-23 survey redesign (Table 3.18 note i), so it is expected."""
    for sec in ("rural", "urban"):
        sid = f"t3_18.mpce.{sec}.constant_2011_12"
        d = r592.filter(pl.col("series_id") == sid).sort("period")
        vals = d["value"].to_list()
        assert vals == sorted(vals) and len(vals) == 6
        breaks = checks.check_continuity(r592, series_ids=[f"t3_18.mpce.{sec}.current"], max_rel_change=0.5)
        assert set(zip(breaks["from_period"], breaks["to_period"], strict=True)) <= {
            ("2004-07/2005-06", "2009-07/2010-06"), ("2011-07/2012-06", SY23)}


# ---------------------------------------------------------------------------------------------
# CPI 2024 weights
# ---------------------------------------------------------------------------------------------


def test_cpi_anchor(cpi):
    p = "2024"
    # Annexure 5.3a (PDF p.108): Food and beverages 36.7531063101009 combined; total rural 55.419...
    assert v(cpi, "w5_3a.div_01.all", p) == pytest.approx(36.753106, abs=1e-6)
    assert v(cpi, "w5_3a.div_total.rural", p) == pytest.approx(55.419206, abs=1e-6)
    # 5.3b: 04.1 Actual rental payments for housing, urban 8.42776...
    assert v(cpi, "w5_3b.grp_04.1.urban", p) == pytest.approx(8.427762, abs=1e-6)
    # 5.3c: Uttar Pradesh combined 12.5348577531066
    assert v(cpi, "w5_3c.in-up.all", p) == pytest.approx(12.534858, abs=1e-6)
    # 5.3d row 5: Jammu and Kashmir rural rice, share in All India 0.0212277590386373
    assert v(cpi, "w5_3d.01.1.1.1.1.01.in-jk.rural.share_all_india", p) == pytest.approx(0.021228, abs=1e-6)


def test_cpi_item_weights_add_up(cpi):
    d = cpi.filter(pl.col("series_id").str.starts_with("w5_3d") & (pl.col("geography") == "IN"))
    for sec in ("rural", "urban"):
        s = d.filter(pl.col("household_group") == f"{sec}_all")["value"].sum()
        assert s == pytest.approx(v(cpi, f"w5_3a.div_total.{sec}", "2024"), abs=2e-3)
    divs = cpi.filter(pl.col("series_id").str.starts_with("w5_3a.div_") & pl.col("series_id").str.ends_with(".all"))
    assert divs.filter(~pl.col("series_id").str.contains("total"))["value"].sum() == pytest.approx(100, abs=1e-4)
    assert d.select("product").n_unique() == 358  # 358 weighted items (press release, 12 Feb 2026)
    checks.assert_no_rows(checks.check_range(cpi, lo=0, hi=100), "weights outside [0, 100]")


# ---------------------------------------------------------------------------------------------
# NSS Health 596 and CMS Education 2025
# ---------------------------------------------------------------------------------------------


def test_health596_anchor(h596):
    p = "2025"
    assert v(h596, "t2_21.oop_per_hosp_case_avg.rural_hh_q1", p) == 25704
    assert v(h596, "t2_21.oop_per_hosp_case_avg.urban_all", p) == 38688
    assert v(h596, "t2_21.oop_per_hosp_case_median.urban_hh_q5", p) == 20000
    assert v(h596, "t2_24.oop_per_opd_spell_avg.all", p) == 861
    assert v(h596, "t2_24.oop_per_opd_spell_median.rural_all", p) == 395
    # OOP spending per case rises from the bottom to the top urban quintile
    urb = [v(h596, f"t2_21.oop_per_hosp_case_avg.urban_hh_q{q}", p) for q in range(1, 6)]
    assert urb == sorted(urb)


def test_cms_education_anchor(edu):
    p = "2025-Q2"
    assert v(edu, "s2_3.exp_per_student.all.person.rural_all", p) == 8382
    assert v(edu, "s2_3.exp_per_student.higher_secondary.male.urban_all", p) == 32615
    assert v(edu, "s2_3.exp_per_student.secondary.person.all", p) == 14781
    assert v(edu, "s2_3.exp_per_student.pre_primary.female.all", p) == 9624
    # urban spending per student exceeds rural at every level
    for lvl in ("pre_primary", "primary", "middle", "secondary", "higher_secondary", "all"):
        assert v(edu, f"s2_3.exp_per_student.{lvl}.person.urban_all", p) > v(
            edu, f"s2_3.exp_per_student.{lvl}.person.rural_all", p)


def test_survey_period_recorded_in_provenance():
    prov = checks.load_provenance(UNIT)
    hces = prov.filter(pl.col("source_id").is_in(["mospi_hces_2023_24", "mospi_hces_2022_23"]))
    assert hces.height > 0
    bad = pl.col("notes").is_null() | ~pl.col("notes").str.contains("NOT fiscal year|survey window")
    assert hces.filter(bad).height == 0


# ---------------------------------------------------------------------------------------------
# Close-out: survey-window periods, shared State codes, CPI derived-row tags and precision
# ---------------------------------------------------------------------------------------------

HCES_DATASETS = ("a2_fractile_persons", "a6_group_fractile", "a10f_item_fractile", "a10s_state_item",
                 "a10sw_state_item_imputed", "report592_mpce")


@pytest.mark.parametrize("name", HCES_DATASETS)
def test_hces_rows_carry_survey_windows(name):
    """HCES rounds run August-July: never 'fy'. Report 592 T3.18's NSS rounds run July-June."""
    d = _ds(name)
    assert set(d["period_type"]) == {"sy"}
    allowed = {SY24, SY23}
    if name == "report592_mpce":
        allowed |= {"1999-07/2000-06", "2004-07/2005-06", "2009-07/2010-06", "2011-07/2012-06"}
    assert set(d["period"]) <= allowed and SY24 in set(d["period"])
    # series ids keep the round tag: every hces2324 row is the Aug 2023-Jul 2024 window, and so on
    for tag, sy in (("hces2324", SY24), ("hces2223", SY23)):
        x = d.filter(pl.col("series_id").str.contains(f".{tag}.", literal=True))
        assert set(x["period"]) <= {sy}


def test_t318_rounds_map_to_their_windows(r592):
    t = r592.filter(pl.col("series_id") == "t3_18.mpce.rural.current").sort("period")
    assert t["period"].to_list() == ["1999-07/2000-06", "2004-07/2005-06", "2009-07/2010-06", "2011-07/2012-06",
                                     SY23, SY24]
    assert t["value"].to_list() == [486, 579, 1054, 1430, 3773, 4122]  # Report 592 p.52, Rural, cols 2-6, 8


def test_other_datasets_keep_their_calendar_periods(h596, edu, cpi):
    assert set(h596["period_type"]) == {"cy"} and set(h596["period"]) == {"2025"}
    assert set(edu["period_type"]) == {"cq"} and set(edu["period"]) == {"2025-Q2"}
    assert set(cpi["period_type"]) == {"cy"} and set(cpi["period"]) == {"2024"}


def test_geography_uses_the_shared_code_set():
    from pipeline.core import geo
    from pipeline.ingest.hces_consumption import _common as C

    for name in (*HCES_DATASETS, "cpi2024_weights"):
        g = set(_ds(name)["geography"].drop_nulls())
        assert g <= {"IN"} | set(geo.STATES_UTS), (name, sorted(g - set(geo.STATES_UTS)))
    # printed variants in the HCES / CPI files
    assert C.state_geo("All India") == "IN" and C.state_geo("All-India") == "IN"
    assert C.state_geo("A & N Island") == C.state_geo("Andaman & N Island") == "IN-AN"
    assert C.state_geo("Uttrakhand") == "IN-UK" and C.state_geo("NCT of Delhi") == "IN-DL"
    assert C.state_geo("Chhattisgarh") == "IN-CG" and C.state_geo("Odisha") == "IN-OD"
    with pytest.raises(ValueError):
        C.state_geo("Atlantis")


def test_cpi_derived_all_india_rows_are_tagged(cpi):
    d = cpi.filter((pl.col("table_id") == "Annexure 5.3d") & (pl.col("status") == "derived"))
    assert d.height == 716 and set(d["geography"]) == {"IN"}
    assert set(d["dim_other"]) == {"share_of=all_india_combined_basket"}

