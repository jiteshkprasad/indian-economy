"""Value tests for the trade_satellites unit (IMF IMTS, UN Comtrade preview, OECD-WTO BaTIS).

Anchor values are read off the pinned raw files (the publisher's own API responses: the IMF
SDMX-CSV rows, the Comtrade JSON records, the BaTIS SDMX-CSV rows) and are quoted with the
row they come from. Cross-source checks compare the unit's numbers with totals printed on
TradeStat as quoted in docs/phase0/recon/external.md s16 and docs/phase0/verify/external.md.
"""

import polars as pl
import pytest

from pipeline.core import checks

pytestmark = pytest.mark.quality

UNIT = "trade_satellites"


def _load(name):
    return checks.load_dataset(UNIT, f"{UNIT}_{name}")


@pytest.fixture(scope="module")
def imf_m():
    return _load("imf_imts_monthly")


@pytest.fixture(scope="module")
def imf_fy():
    return _load("imf_imts_fy")


@pytest.fixture(scope="module")
def imf_a():
    return _load("imf_imts_annual")


@pytest.fixture(scope="module")
def ct_m():
    return _load("comtrade_monthly_2324")


@pytest.fixture(scope="module")
def ct_fy():
    return _load("comtrade_fy_2324")


@pytest.fixture(scope="module")
def batis():
    return _load("batis_2023_2024")


@pytest.fixture(scope="module")
def batis_h():
    return _load("batis_history")


def _v(df, sid, period):
    return checks.value(df, sid, period)


# ---------------------------------------------------------------------------------------------
# common: units, periods, signs
# ---------------------------------------------------------------------------------------------

DATASETS = {
    "imf_imts_monthly": "month",
    "imf_imts_fy": "fy",
    "imf_imts_annual": "cy",
    "comtrade_monthly_2324": "month",
    "comtrade_fy_2324": "fy",
    "batis_2023_2024": "cy",
    "batis_history": "cy",
}


@pytest.mark.parametrize("name, ptype", sorted(DATASETS.items()))
def test_units_periods_signs(name, ptype):
    df = _load(name)
    assert set(df["unit"]) == {"USD_million"}  # dollars kept as published; no hard-coded exchange rate
    assert set(df["period_type"]) == {ptype}  # calendar vs fiscal basis is explicit
    assert set(df["price_basis"]) == {"current"}
    assert set(df["stock_flow"]) == {"flow"}
    # gross trade flows: never negative (exports and imports are both recorded positive)
    checks.assert_no_rows(checks.check_range(df, lo=0), f"{name}: negative flows")
    # partners: ISO3 in geography, groups/unspecified areas in dim_other, never both or neither
    both = df.filter(pl.col("geography").is_not_null() & pl.col("dim_other").fill_null("").str.contains("partner_group="))
    none = df.filter(pl.col("geography").is_null() & ~pl.col("dim_other").fill_null("").str.contains("partner_group="))
    assert both.height == 0 and none.height == 0
    # withdrawn ISO codes (USSR, Yugoslavia, the two pre-1990 Yemens, ...) are not countries today
    withdrawn = {"SUN", "YUG", "CSK", "DDR", "ANT", "SCG", "YAR", "YMD"}
    assert not set(df["geography"].drop_nulls()) & withdrawn


def test_withdrawn_yemen_codes_in_dim_other(imf_a):
    """Verifier V2: IMF annual has YAR / YMD (pre-1990 Yemens); they go to dim_other, not geography."""
    for code in ("YAR", "YMD"):
        d = imf_a.filter(pl.col("dim_other") == f"partner_group={code}")
        assert d.height > 0 and d["geography"].null_count() == d.height


def test_india_as_partner_is_comtrade_reimports_only(ct_m, ct_fy, imf_m, imf_fy, imf_a):
    """Verifier V3 (issues trade_satellites-15): partner IND appears only in the Comtrade imports
    TOTAL pulls (re-imports, partnerCode 699), 7,314.9 US$ mn in FY 2023-24; never in IMF data."""
    for df in (imf_m, imf_fy, imf_a):
        assert df.filter(pl.col("geography") == "IND").height == 0
    ind = ct_m.filter(pl.col("geography") == "IND")
    assert set(ind["item_code"]) == {"imports"} and set(ind["product"]) == {"TOTAL"} and ind.height == 12
    fy = ct_fy.filter(pl.col("geography") == "IND")
    assert fy.height == 1 and fy["value"][0] == pytest.approx(7314.873016, abs=1e-5)


# ---------------------------------------------------------------------------------------------
# IMF IMTS
# ---------------------------------------------------------------------------------------------


# Rows of imts_ind_m_2011on.csv (US$ units): 'XG_FOB_USD,G001,M,2024-M03,41678200000',
# 'MG_CIF_USD,G001,M,2023-M04,50156993311', 'XG_FOB_USD,USA,M,2023-M04,5910696379',
# 'MG_CIF_USD,CHN,M,2024-M03,7740030000', 'MG_CIF_USD,RUS,M,2023-M04,4979026347'.
@pytest.mark.parametrize(
    "sid, period, usd_mn",
    [
        ("imts.exports_fob.g001.current", "2024-03", 41678.2),
        ("imts.imports_cif.g001.current", "2023-04", 50156.993311),
        ("imts.exports_fob.usa.current", "2023-04", 5910.696379),
        ("imts.imports_cif.chn.current", "2024-03", 7740.03),
        ("imts.imports_cif.rus.current", "2023-04", 4979.026347),
    ],
)
def test_imf_monthly_anchors(imf_m, sid, period, usd_mn):
    assert _v(imf_m, sid, period) == pytest.approx(usd_mn, abs=1e-6)


# Rows of imts_ind_a.csv: 'XG_FOB_USD,G001,A,2023,431997480767', 'MG_CIF_USD,CHN,A,2024,109358700000',
# 'MG_CIF_USD,G001,A,1948,1987600000', 'XG_FOB_USD,USA,A,2024,80914500000'.
@pytest.mark.parametrize(
    "sid, period, usd_mn",
    [
        ("imts.exports_fob.g001.current", "2023", 431997.480767),
        ("imts.imports_cif.chn.current", "2024", 109358.7),
        ("imts.imports_cif.g001.current", "1948", 1987.6),
        ("imts.exports_fob.usa.current", "2024", 80914.5),
    ],
)
def test_imf_annual_anchors(imf_a, sid, period, usd_mn):
    assert _v(imf_a, sid, period) == pytest.approx(usd_mn, abs=1e-6)


def test_imf_fy_is_sum_of_months(imf_m, imf_fy):
    """Every FY row = the sum of its 12 monthly rows (April..March)."""
    m = imf_m.with_columns(
        pl.col("period").str.slice(0, 4).cast(pl.Int32).alias("y"), pl.col("period").str.slice(5, 2).cast(pl.Int32).alias("mo")
    ).with_columns(pl.when(pl.col("mo") >= 4).then(pl.col("y")).otherwise(pl.col("y") - 1).alias("s"))
    m = m.with_columns((pl.col("s").cast(pl.String) + "-" + ((pl.col("s") + 1) % 100).cast(pl.String).str.zfill(2)).alias("fy"))
    agg = m.group_by("series_id", "fy").agg(pl.col("value").sum().alias("sum"), pl.len().alias("n"))
    j = imf_fy.join(agg, left_on=["series_id", "period"], right_on=["series_id", "fy"], how="left")
    assert j.filter(pl.col("n") != 12).height == 0
    checks.assert_no_rows(j.filter((pl.col("value") - pl.col("sum")).abs() > 1e-4), "FY != sum of months")
    # and no complete partner-year was left out
    complete = agg.filter(pl.col("n") == 12).join(imf_fy, left_on=["series_id", "fy"], right_on=["series_id", "period"], how="anti")
    assert complete.height == 0


def test_imf_fy_2023_24_world_and_partner_shares(imf_fy):
    x = _v(imf_fy, "imts.exports_fob.g001.current", "2023-24")
    m = _v(imf_fy, "imts.imports_cif.g001.current", "2023-24")
    assert x == pytest.approx(437722.4, rel=1e-5)  # sum of the 12 G001 XG_FOB_USD months Apr 2023..Mar 2024
    assert m == pytest.approx(672860.7, rel=1e-5)
    fy = imf_fy.filter(pl.col("period") == "2023-24")
    for item, world in (("exports_fob", x), ("imports_cif", m)):
        iso = fy.filter((pl.col("item_code") == item) & pl.col("geography").is_not_null())["value"].sum()
        # country partners (complete years only) never exceed the world total and cover >= 99% of it;
        # the rest is 'Countries & Areas not specified' (TX898) and partner-years with missing months
        assert 0.99 * world <= iso <= world
    # the largest partners in FY 2023-24: USA first for exports, China first for imports
    top_x = fy.filter((pl.col("item_code") == "exports_fob") & pl.col("geography").is_not_null()).sort("value", descending=True)
    top_m = fy.filter((pl.col("item_code") == "imports_cif") & pl.col("geography").is_not_null()).sort("value", descending=True)
    assert top_x["geography"][0] == "USA" and top_m["geography"][0] == "CHN"


def test_imf_fy_world_matches_tradestat(imf_fy):
    """Cross-source: IMF world exports (India-reported, via NSDP) vs the TradeStat EIDB totals quoted in
    docs/phase0/recon/external.md s16: 'India's Total Export 437704.58 [2024-25] 441452.14 [2025-26]' (US$ mn)."""
    assert _v(imf_fy, "imts.exports_fob.g001.current", "2024-25") == pytest.approx(437704.58, rel=0.005)
    assert _v(imf_fy, "imts.exports_fob.g001.current", "2025-26") == pytest.approx(441452.14, rel=0.005)


def test_imf_annual_equals_sum_of_months(imf_m, imf_a):
    """Calendar-year IMTS = sum of the 12 months, for the world total (2011-2025)."""
    for sid in ("imts.exports_fob.g001.current", "imts.imports_cif.g001.current"):
        m = imf_m.filter(pl.col("series_id") == sid).with_columns(pl.col("period").str.slice(0, 4).alias("y"))
        agg = m.group_by("y").agg(pl.col("value").sum(), pl.len().alias("n")).filter(pl.col("n") == 12)
        assert agg.height >= 15
        for y, s, _ in agg.iter_rows():
            assert _v(imf_a, sid, y) == pytest.approx(s, rel=0.002), (sid, y)


def test_imf_continuity(imf_fy, imf_a):
    world = [f"imts.{f}.g001.current" for f in ("exports_fob", "imports_cif")]
    # FY 2011-12 .. 2025-26: the largest swings are FY 2021-22 after the pandemic year (imports +57%, from
    # 389,129 to 610,049 US$ mn; exports +45%), a known rebound plus the commodity-price spike
    checks.assert_no_rows(checks.check_continuity(imf_fy, series_ids=world, max_rel_change=0.6), "FY world jump > 60%")
    recent = imf_a.filter(pl.col("period").cast(pl.Int32) >= 1991)
    breaks = checks.check_continuity(recent, series_ids=world, max_rel_change=0.6)
    # One known break, logged as trade_satellites-12: world imports CY 2005 -> 2006 +67% (98,895 -> 165,021
    # US$ mn), with imports below exports in 2000-2004. The IMF annual series looks understated before 2006;
    # do not use IMTS annual world imports before 2006 without checking them against RBI/DGCI&S.
    assert breaks.select("series_id", "from_period", "to_period").rows() == [
        ("imts.imports_cif.g001.current", "2005", "2006")
    ], breaks


def test_imf_vintage(imf_m, imf_fy, imf_a):
    for df in (imf_m, imf_fy, imf_a):
        assert set(df["vintage"]) == {"2026-08-31"}  # PUBLICATION_DATE in the attribute file
    assert set(imf_fy["status"]) == {"derived"} and set(imf_m["status"]) == {"official"}


# ---------------------------------------------------------------------------------------------
# UN Comtrade
# ---------------------------------------------------------------------------------------------


def _c(flow, cmd, partner):
    return f"ct.{flow}.{cmd}.{partner}.current"


def _parts(df):
    return df.with_columns(pl.col("series_id").str.split(".").list.get(3).alias("partner"))


# Records of the pinned preview JSON (primaryValue, US$): ct_m_total_allpartners_202304.json
# 'M TOTAL 0 W00 49056049877.696', 'X TOTAL 0 W00 34618433634.302', 'X TOTAL 842 USA 5908769968.877';
# ct_m_ag2_world_202304.json 'M 27 0 W00 17306475879.856'; ct_m_ag2_p156_842_202402.json
# 'M 85 156 CHN 3668727023.588', 'X 85 842 USA 1281884515.725'; ct_m_ag2_p784_643_202310.json 'M 27 643 RUS 5413739469.469'.
@pytest.mark.parametrize(
    "sid, period, usd_mn",
    [
        (_c("imports", "total", "w00"), "2023-04", 49056.049877696),
        (_c("exports", "total", "w00"), "2023-04", 34618.433634302),
        (_c("exports", "total", "usa"), "2023-04", 5908.769968877),
        (_c("imports", "27", "w00"), "2023-04", 17306.475879856),
        (_c("imports", "85", "chn"), "2024-02", 3668.727023588),
        (_c("exports", "85", "usa"), "2024-02", 1281.884515725),
        (_c("imports", "27", "rus"), "2023-10", 5413.739469469),
    ],
)
def test_comtrade_anchors(ct_m, sid, period, usd_mn):
    assert _v(ct_m, sid, period) == pytest.approx(usd_mn, abs=1e-5)


def test_comtrade_chapters_sum_to_total(ct_m):
    """HS chapters add up to the all-commodity total, for World and for every top-30 partner, each month."""
    d = _parts(ct_m)
    tot = d.filter(pl.col("product") == "TOTAL").select("item_code", "partner", "period", pl.col("value").alias("tot"))
    ch = d.filter(pl.col("product") != "TOTAL").group_by("item_code", "partner", "period").agg(pl.col("value").sum().alias("ch"))
    j = ch.join(tot, on=["item_code", "partner", "period"], how="left")
    assert j.filter(pl.col("tot").is_null()).height == 0
    assert j["partner"].n_unique() >= 30  # World + top-30 partners
    checks.assert_no_rows(j.filter((pl.col("ch") - pl.col("tot")).abs() > 1e-6 * pl.col("tot") + 1e-3), "chapters != total")


def test_comtrade_partners_sum_to_world(ct_m):
    """Totals by every partner add up to the World total (Comtrade's own aggregate), each month."""
    d = _parts(ct_m).filter(pl.col("product") == "TOTAL")
    w = d.filter(pl.col("partner") == "w00").select("item_code", "period", pl.col("value").alias("w"))
    p = d.filter(pl.col("partner") != "w00").group_by("item_code", "period").agg(pl.col("value").sum().alias("p"))
    j = w.join(p, on=["item_code", "period"])
    assert j.height == 24
    checks.assert_no_rows(j.filter((pl.col("w") - pl.col("p")).abs() > 1e-4 * pl.col("w")), "partners != World")


def test_comtrade_fy_is_sum_of_months(ct_m, ct_fy):
    agg = ct_m.group_by("series_id").agg(pl.col("value").sum().alias("s"), pl.len().alias("n"))
    j = ct_fy.join(agg, on="series_id", how="left")
    assert (j["n"] == 12).all() and set(ct_fy["period"]) == {"2023-24"}
    checks.assert_no_rows(j.filter((pl.col("value") - pl.col("s")).abs() > 1e-4), "FY != sum of months")
    assert agg.filter(pl.col("n") == 12).height == ct_fy.height  # no complete series left out


def test_comtrade_fy_vs_imf(ct_fy, imf_fy):
    """Two releases of the same India-reported data: FY 2023-24 World totals agree within 3%."""
    for ct_flow, imf_flow in (("exports", "exports_fob"), ("imports", "imports_cif")):
        a = _v(ct_fy, _c(ct_flow, "total", "w00"), "2023-24")
        b = _v(imf_fy, f"imts.{imf_flow}.g001.current", "2023-24")
        assert a == pytest.approx(b, rel=0.03), (ct_flow, a, b)


def test_comtrade_top_partner_coverage(ct_fy):
    """The HS-chapter x partner block covers the top 30 partners: >= 75% of FY 2023-24 X+M (World)."""
    d = _parts(ct_fy)
    tot = d.filter(pl.col("product") == "TOTAL")
    with_ch = set(d.filter((pl.col("product") != "TOTAL") & (pl.col("partner") != "w00"))["partner"])
    assert len(with_ch) == 30
    world = tot.filter(pl.col("partner") == "w00")["value"].sum()
    covered = tot.filter(pl.col("partner").is_in(sorted(with_ch)))["value"].sum()
    assert 0.75 <= covered / world <= 0.95


def test_comtrade_vintages(ct_m, ct_fy):
    assert ct_m["vintage"].min() >= "2024-05-01" and ct_m["vintage"].max() <= "2024-06-30"
    assert set(ct_fy["vintage"]) == {ct_m["vintage"].max()}
    assert set(ct_fy["status"]) == {"derived"} and set(ct_m["status"]) == {"official"}



# ---------------------------------------------------------------------------------------------
# OECD-WTO BaTIS
# ---------------------------------------------------------------------------------------------


def _b(flow, svc, partner, measure):
    return f"batis.{flow}.{svc}.{partner}.{measure}.current"


# Rows of batis_ind_2023_2024.csv (US$ mn): 'W,X,S,S,...,N,2023,337539.6894', 'W,X,S,S,...,B,2023,223337.091266',
# 'W,M,S,S,...,B,2024,202958.819269', 'USA,X,S,S,...,B,2023,45044.021883', 'GBR,X,S,S,...,B,2023,18809.534874',
# 'USA,X,S,SI2,...,B,2024,18731.707472', 'W,M,S,SD,...,N,2023,33465.798888'.
@pytest.mark.parametrize(
    "sid, period, usd_mn",
    [
        (_b("exports", "s", "w", "reported"), "2023", 337539.6894),
        (_b("exports", "s", "w", "balanced"), "2023", 223337.091266),
        (_b("imports", "s", "w", "balanced"), "2024", 202958.819269),
        (_b("exports", "s", "usa", "balanced"), "2023", 45044.021883),
        (_b("exports", "s", "gbr", "balanced"), "2023", 18809.534874),
        (_b("exports", "si2", "usa", "balanced"), "2024", 18731.707472),
        (_b("imports", "sd", "w", "reported"), "2023", 33465.798888),
    ],
)
def test_batis_anchors(batis, sid, period, usd_mn):
    assert _v(batis, sid, period) == pytest.approx(usd_mn, abs=1e-6)


# Rows of batis_ind_2005_2022.csv: 'W,X,S,S,...,N,2022,309371.096', 'USA,X,S,S,...,B,2015,25652.747736',
# 'W,X,S,S,...,B,2005,35591.77119'.
def test_batis_history_anchors(batis_h):
    assert _v(batis_h, _b("exports", "s", "w", "reported"), "2022") == pytest.approx(309371.096, abs=1e-6)
    assert _v(batis_h, _b("exports", "s", "usa", "balanced"), "2015") == pytest.approx(25652.747736, abs=1e-6)
    assert _v(batis_h, _b("exports", "s", "w", "balanced"), "2005") == pytest.approx(35591.77119, abs=1e-6)
    assert sorted(set(batis_h["period"])) == [str(y) for y in range(2005, 2023)]


def test_batis_reported_matches_comtrade_services():
    """Cross-source: India's reported total services exports 2022 in BaTIS vs UN Comtrade services (EBOPS
    code 200, partner World) 'exports $309.4 bn' quoted in docs/phase0/recon/international.md s5."""
    h = _load("batis_history")
    assert _v(h, _b("exports", "s", "w", "reported"), "2022") / 1000 == pytest.approx(309.4, abs=0.05)


def test_batis_partners_sum_to_world(batis):
    """Balanced measure: the partner flows add up to the World flow (every flow x item x year)."""
    b = batis.filter(pl.col("dim_other").str.starts_with("batis_measure=balanced"))
    b = b.with_columns(
        pl.col("series_id").str.split(".").list.get(3).alias("partner"),
        (pl.col("item_code") + "." + pl.col("product")).alias("k"),
    )
    world = b.filter(pl.col("partner") == "w").select("k", "period", pl.col("value").alias("world"))
    parts = b.filter(pl.col("partner") != "w").group_by("k", "period").agg(pl.col("value").sum().alias("parts"))
    j = world.join(parts, on=["k", "period"], how="full", coalesce=True)
    assert j.filter(pl.col("world").is_null() | pl.col("parts").is_null()).height == 0
    checks.assert_no_rows(
        j.filter((pl.col("world") - pl.col("parts")).abs() > 1e-3 * pl.col("world").abs() + 0.01), "partners != World"
    )


EBOPS = {
    "s": ["sa", "sb", "sc", "sd", "se", "sf", "sg", "sh", "si", "sj", "sk", "sl"],
    "sc": ["sc1", "sc2", "sc3", "sc4"],
    "sd": ["sda", "sdb"],
    "si": ["si1", "si2", "si3"],
    "sj": ["sj1", "sj2", "sj3"],
    "sk": ["sk1", "sk2"],
}


@pytest.mark.parametrize("measure", ["balanced", "adjusted_imputed"])
@pytest.mark.parametrize("flow", ["exports", "imports"])
def test_batis_ebops_identities_world(batis, measure, flow):
    """EBOPS 2010 hierarchy at partner World: total = sum of the 12 main items; sub-items add up.
    (The 'reported' measure is not tested: it carries only the items India reports, e.g. exports have no
    SI/SJ subtotal and imports no total, so its hierarchy is incomplete by construction.)"""
    for total, parts in EBOPS.items():
        v = checks.check_identity(
            batis, _b(flow, total, "w", measure), [_b(flow, p, "w", measure) for p in parts], by=("period",), rel_tol=2e-3
        )
        checks.assert_no_rows(v, f"{flow} {measure} {total}")


def test_batis_balanced_is_far_below_reported(batis):
    """The finding logged in the issues file: BaTIS balanced World totals are 60-80% of India's reported
    totals, so the balanced matrix gives partner shares, not levels."""
    for year in ("2023", "2024"):
        ratio = _v(batis, _b("exports", "s", "w", "balanced"), year) / _v(batis, _b("exports", "s", "w", "reported"), year)
        assert 0.6 < ratio < 0.7, (year, ratio)


def test_batis_status_and_vintage(batis, batis_h):
    for df in (batis, batis_h):
        st = dict(df.select(pl.col("dim_other").str.extract(r"batis_measure=([a-z_]+)"), "status").unique().iter_rows())
        assert st == {"balanced": "estimated", "adjusted_imputed": "estimated", "reported": "official"}
        assert set(df["vintage"]) == {"2025-12"}  # 'OECD-WTO_BATIS_BPM6_December2025_bulk.zip' in the dataflow


def test_batis_history_continuity(batis_h):
    ids = [_b(f, "s", "w", m) for f in ("exports", "imports") for m in ("balanced", "adjusted_imputed")]
    # largest swing: adjusted/imputed imports 2009 -> 2010, +43% (80,553 -> 114,928 US$ mn), the post-crisis rebound
    checks.assert_no_rows(checks.check_continuity(batis_h, series_ids=ids, max_rel_change=0.45), "world services jump > 45%")
