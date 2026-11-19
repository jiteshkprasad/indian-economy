"""Value tests for the NAS API part of mospi_nas_2026 (pipeline/ingest/mospi_nas_2026/api.py), the F1 identity row,
the shared State code map in 4.1 and the SNA code-column guard of the old-base sequences.

Anchor values are quoted from the pinned API pages (data/raw/mospi_nas_api/<date>/mospi_nas_2026/*.json), which
is where a verifier finds them: file name, then the record with the given year.
"""

import json
from types import SimpleNamespace

import polars as pl
import pytest

from pipeline.core import checks, geo
from pipeline.core.fetch import pinned_raw
from pipeline.core.paths import Layout
from pipeline.ingest.mospi_nas_2026 import api, oldbase

pytestmark = pytest.mark.quality

U = "mospi_nas_2026"
API_SETS = ("api_b2011_back", "api_b2011_annual", "api_b2011_quarterly", "api_b2022_annual", "api_b2022_quarterly")


def ds(name: str) -> pl.DataFrame:
    return checks.load_dataset(U, f"{U}_{name}")


def val(df: pl.DataFrame, sid: str, period: str) -> float:
    return checks.value(df, sid, period)


def raw_records(name: str) -> list[dict]:
    return json.loads(pinned_raw(Layout.default(), U, api.SRC_API, name).path.read_text(encoding="utf-8"))["data"]


# ---- anchors (nasapi_b2011_back_a_i05_p01.json: GDP records) --------------------------------------------------
@pytest.mark.parametrize(
    "period, current, constant",
    [("1950-51", 10221, 496848), ("1990-91", 576109, 2514548), ("2002-03", 2492613, 4707983),
     ("2011-12", 8736331, 8736331)],
)
def test_back_series_gdp_anchors(period, current, constant):
    b = ds("api_b2011_back")
    assert val(b, "api.gdp.current", period) == current
    assert val(b, "api.gdp.constant_2011_12", period) == constant


def test_back_series_span_and_labels():
    b = ds("api_b2011_back")
    gdp = b.filter(pl.col("series_id") == "api.gdp.current")
    assert gdp["period"].to_list() == sorted(gdp["period"].to_list())
    assert gdp.height == 62 and gdp["period"].min() == "1950-51" and gdp["period"].max() == "2011-12"
    assert set(b["base_year"]) == {"2011-12"} and set(b["price_basis"]) == {"current", "constant_2011_12"}
    assert set(b["estimate_stage"]) == {"n.a."} and set(b["source_id"]) == {"mospi_nas_api"}
    # valuables: 14 records from 1998-99; the 1998-99 record has no numbers (both prices null in raw)
    assert b.filter(pl.col("series_id") == "api.valuables.current").height == 13
    # GNDI, gross saving and other current transfers are current-price only
    assert not b.filter(pl.col("item_code").is_in(["gndi", "gross_saving", "other_current_transfers_row_net"])
                        & (pl.col("price_basis") != "current")).height


def test_back_series_identities():
    """GDP = GVA + net product taxes; NDP = GDP - CFC; GNI = GDP + net primary income; GVA = 'Total GVA' row."""
    b = ds("api_b2011_back")
    bad = []
    for basis in ("current", "constant_2011_12"):
        for per in sorted(set(b["period"])):
            g = {s: val(b, f"api.{s}.{basis}", per)
                 for s in ("gdp", "gva", "net_taxes_on_products", "cfc", "ndp", "gni", "primary_income_row_net",
                           "gva.ind_total")}
            for name, d in (("gdp", g["gdp"] - g["gva"] - g["net_taxes_on_products"]),
                            ("ndp", g["ndp"] - g["gdp"] + g["cfc"]),
                            ("gni", g["gni"] - g["gdp"] - g["primary_income_row_net"]),
                            ("gva_total", g["gva"] - g["gva.ind_total"])):
                if abs(d) > 2:
                    bad.append((per, basis, name, d))
    assert not bad, bad[:10]


TOP_INDUSTRIES = ("agri", "mining", "manufacturing", "utilities", "construction", "trade_hotels", "transport_comm",
                  "financial", "real_estate_prof", "public_admin", "other_services")


def test_back_series_industries_add_up_from_2004_05_only():
    """The 11 industries sum to total GVA (rounding <= 11 crore) from 2004-05. Before that the back series is
    spliced industry by industry and is not additive (issue mospi_nas_2026-33): the test pins both facts."""
    g = ds("api_b2011_back").filter(pl.col("item_code") == "gva")
    diff = {}
    for (per, basis), grp in g.group_by(["period", "price_basis"]):
        d = {r["industry"]: r["value"] for r in grp.iter_rows(named=True)}
        diff[(per, basis)] = sum(d[t] for t in TOP_INDUSTRIES) - d["total"]
    assert all(abs(v) <= 11 for (per, _), v in diff.items() if per >= "2004-05")
    assert sum(abs(v) > 11 for (per, _), v in diff.items() if per < "2004-05") >= 100  # 108 of 108 in raw


# ---- new base: equal to NAS 2026 ------------------------------------------------------------------------------
def test_new_base_api_equals_nas_2026_statements():
    """Every whole-economy aggregate of the new-base API equals NAS 2026 Statement 1.1 / 8.17.1 within API rounding
    (the API serves whole crore), with the same estimate stage."""
    a = ds("api_b2022_annual").filter(pl.col("industry").is_null() & pl.col("institution").is_null())
    nas = pl.concat([ds("s1_1"), ds("s8_17_1")], how="diagonal_relaxed").select(
        "item_code", "period", "price_basis", pl.col("value").alias("nas"), pl.col("estimate_stage").alias("nas_stage")
    ).unique(subset=["item_code", "period", "price_basis"])
    m = a.join(nas, on=["item_code", "period", "price_basis"], how="left")
    assert m["nas"].null_count() == 0
    assert m.height >= 100
    checks.assert_no_rows(m.filter((pl.col("value") - pl.col("nas")).abs() > 0.5), "API vs NAS 2026 > 0.5 crore")
    checks.assert_no_rows(m.filter(pl.col("estimate_stage") != pl.col("nas_stage")), "API stage vs NAS 2026 stage")


def test_new_base_quarters_add_to_annual_and_reach_q1_2026_27():
    q, a = ds("api_b2022_quarterly"), ds("api_b2022_annual")
    annual = a.filter((pl.col("item_code") == "gdp") & pl.col("industry").is_null())  # one round per year
    for basis in ("current", "constant_2022_23"):
        for per in ("2022-23", "2023-24", "2024-25", "2025-26"):
            qs = q.filter((pl.col("series_id") == f"api.gdp.{basis}") & pl.col("period").str.ends_with(per))
            yr = annual.filter((pl.col("price_basis") == basis) & (pl.col("period") == per))
            assert qs.height == 4 and yr.height == 1
            assert abs(qs["value"].sum() - yr["value"][0]) <= 1, (basis, per)
    # nasapi_b2022_current_q_i05_p01.json: GDP Q1 2026-27 current 88,26,871 (registry latest_release)
    assert val(q, "api.gdp.current", "Q1 2026-27") == 8826871


# ---- indicator 8 'GCF by industry of use' (verifier finding c-1, issue mospi_nas_2026-37) ------------------------
def _gcf_rows(name: str) -> pl.DataFrame:
    return ds(name).filter(pl.col("table_id") == "NAS API getNASData indicator 8")


def test_gcf_by_industry_of_use_is_not_coded_as_1_1_gcf():
    for name in ("api_b2011_back", "api_b2011_annual", "api_b2022_annual"):
        assert "gcf" not in set(_gcf_rows(name)["item_code"]), name
    assert set(_gcf_rows("api_b2011_annual")["item_code"]) == {"gcf_excl_valuables"}
    assert set(_gcf_rows("api_b2022_annual")["item_code"]) == {"gcf_excl_valuables"}
    back = _gcf_rows("api_b2011_back")
    assert set(back["item_code"]) == {"gcf_incl_errors_omissions"} and back["industry"].null_count() == back.height
    meta = json.loads((Layout.default().clean / U / "_datasets.json").read_text(encoding="utf-8"))
    for name in ("api_b2011_back", "api_b2011_annual", "api_b2022_annual"):
        assert "Indicator 8" in meta[f"{U}_{name}"]["description"], name


def test_gcf_by_industry_of_use_equals_statement_7_2():
    """New base: indicator 8 by industry = NAS 2026 Statement 7.2 GCF (GFCF + CIS) in every cell, within 0.5 crore.
    nasapi_b2022_current_a_i08_p01.json: 2023-24 'Total Gross Capital Formation' current 96,28,092; 1.1 GCF is
    1,00,04,323 (the 3,76,231 difference is valuables)."""
    a = _gcf_rows("api_b2022_annual").select("industry", "period", "price_basis", "value")
    s72 = ds("s7_2").filter(pl.col("item_code") == "gcf_excl_valuables").select(
        "industry", "period", "price_basis", pl.col("value").alias("s72"))
    m = a.join(s72, on=["industry", "period", "price_basis"], how="inner")
    assert m.height == a.height == 150
    checks.assert_no_rows(m.filter((pl.col("value") - pl.col("s72")).abs() > 0.5), "API 8 vs 7.2 > 0.5 crore")
    assert val(ds("api_b2022_annual"), "api.gcf_excl_valuables.ind_total.rev_final_estimates.current",
               "2023-24") == 9628092


def test_gcf_back_series_is_the_old_1_1_concept():
    """nasapi_b2011_back_a_i08_p01.json: 2011-12 total 34,03,008 = NAS 2025 old-base 1.1 GCF (34,03,007.9, which
    holds valuables and errors and omissions); the current series' 2011-12 'Additional Revision' total is
    32,05,716 = GFCF + CIS."""
    back = _gcf_rows("api_b2011_back")
    old11 = ds("oldbase_nas2025_s1_1").filter((pl.col("item_code") == "gcf") & (pl.col("period") == "2011-12"))
    for basis in ("current", "constant_2011_12"):
        b = val(back, f"api.gcf_incl_errors_omissions.{basis}", "2011-12")
        assert b == 3403008 and abs(b - old11.filter(pl.col("price_basis") == basis)["value"][0]) < 1
    cur = val(_gcf_rows("api_b2011_annual"), "api.gcf_excl_valuables.ind_total.rev_additional_revision.current",
              "2011-12")
    assert cur == 3205716


def test_gcf_concept_guard_fails_on_a_changed_concept():
    def row(item, value, industry=None, period="2023-24"):
        return {"item_code": item, "value": value, "industry": industry, "institution": None, "period": period,
                "price_basis": "current", "dim_other": None}
    cur_ok = [row("gcf_excl_valuables", 105.0, "total"), row("gfcf", 100.0), row("cis", 5.0), row("valuables", 7.0)]
    api._check_gcf_concept("t", "Current", cur_ok)
    with pytest.raises(ValueError, match="concept changed"):  # current series starts to include valuables
        api._check_gcf_concept("t", "Current", [*cur_ok[1:], row("gcf_excl_valuables", 112.0, "total")])
    back_ok = [row("gcf_incl_errors_omissions", 90.0), row("gfcf", 100.0), row("cis", 5.0), row("valuables", 7.0)]
    api._check_gcf_concept("t", "Back", back_ok)
    with pytest.raises(ValueError, match="concept changed"):  # back series re-issued as GFCF + CIS + valuables
        api._check_gcf_concept("t", "Back", [*back_ok[1:], row("gcf_incl_errors_omissions", 112.0)])
    with pytest.raises(ValueError, match="industry detail"):
        api._check_gcf_concept("t", "Back", [*back_ok, row("gcf_incl_errors_omissions", 1.0, "agri")])
    with pytest.raises(ValueError, match="0 checks"):
        api._check_gcf_concept("t", "Current", cur_ok[1:])


# ---- old base: revision rounds ------------------------------------------------------------------------------
def test_old_base_revision_rounds_are_series():
    a = ds("api_b2011_annual")
    for sid, g in a.group_by("series_id"):
        assert g["estimate_stage"].n_unique() == 1 and g["dim_other"].n_unique() == 1, sid
    gdp = a.filter(pl.col("item_code") == "gdp").filter(pl.col("industry").is_null())
    # nasapi_b2011_current_a_i05_p01.json: 2025-26 FAE 3,57,13,886 current; 2024-25 SAE 3,31,03,214
    assert val(gdp, "api.gdp.rev_first_advance_estimates.current", "2025-26") == 35713886
    assert val(gdp, "api.gdp.rev_second_advance_estimates.current", "2024-25") == 33103214
    assert set(gdp["estimate_stage"]) == {"FAE", "SAE", "PE", "FRE", "SRE", "TRE", "Final", "Revised"}


def test_oldbase_stages_match_api_revision_rounds():
    """Issue mospi_nas_2026-9: every NAS 2025 Statement 1.1 level and the NAS 2024 1.15 CFC equal the API value of
    the revision round the unit labels them with (oldbase.STAGES)."""
    # whole economy: records without a dimension, or the 'Total ...' institutional record (GFCF, CFC, saving)
    a = ds("api_b2011_annual").filter(
        pl.col("industry").is_null() & (pl.col("institution").is_null() | (pl.col("institution") == "total_economy"))
    )
    api_vals: dict[tuple, list[float]] = {}
    for r in a.iter_rows(named=True):
        api_vals.setdefault((r["item_code"], r["period"], r["price_basis"], r["estimate_stage"]), []).append(r["value"])
    o = ds("oldbase_nas2025_s1_1")
    n, bad = 0, []
    for r in o.iter_rows(named=True):
        k = (r["item_code"], r["period"], r["price_basis"], r["estimate_stage"])
        if r["item_code"] in {v[1] for v in api.INDICATORS.values()} and any(
            x[:3] == k[:3] for x in api_vals
        ):
            n += 1
            if not any(abs(v - r["value"]) <= 1 for v in api_vals.get(k, [])):
                bad.append(k)
    assert n >= 13 * 25 and not bad, (n, bad[:10])
    cfc = ds("oldbase_soa_s1_15").filter(pl.col("series_id") == "oldbase_soa_s1_15.production.uses.p51c.current")
    for r in cfc.iter_rows(named=True):
        rounds = api_vals[("cfc", r["period"], "current", r["estimate_stage"])]
        assert any(abs(v - r["value"]) <= 1 for v in rounds), r["period"]


def test_old_base_quarterly():
    q = ds("api_b2011_quarterly")
    # nasapi_b2011_current_q_i05_p01.json: 2025-26 Q1 86,05,364 current, 47,88,623 constant
    assert val(q, "api.gdp.current", "Q1 2025-26") == 8605364
    assert val(q, "api.gdp.constant_2011_12", "Q1 2025-26") == 4788623
    assert set(q["period_type"]) == {"fq"} and set(q["estimate_stage"]) == {"n.a."}


# ---- publisher errors handled (issues mospi_nas_2026-31, -32) --------------------------------------------------
def test_taxes_and_subsidies_skipped_because_of_lakh_label():
    """The API labels indicators 3/4 '₹ Lakh' but taxes - subsidies = net taxes (labelled '₹ Crore') exactly, so
    the label is wrong; the unit skips them rather than relabel the publisher's unit."""
    for name in API_SETS:
        assert not ds(name).filter(pl.col("item_code").is_in(["taxes_on_products", "subsidies_on_products"])).height
    for tag in ("b2011_current_a", "b2022_current_a"):
        t, s, nt = (raw_records(f"nasapi_{tag}_i{i:02d}_p01.json") for i in (3, 4, 2))
        assert {r["unit"] for r in t + s} == {"₹ Lakh"} and {r["unit"] for r in nt} == {"₹ Crore"}
        key = {(r["year"], r["revision"]): r for r in nt}
        ts = {(r["year"], r["revision"]): r for r in t}
        n = 0
        for r in s:
            k = (r["year"], r["revision"])
            if k in key and k in ts:
                for f in ("current_price", "constant_price"):
                    assert abs(float(ts[k][f]) - float(r[f]) - float(key[k][f])) <= 2, (tag, k, f)
                    n += 1
        assert n >= 6


def test_bogus_and_duplicate_records_dropped():
    gndi = raw_records("nasapi_b2011_current_a_i19_p01.json")
    assert [r["year"] for r in gndi if not r["year"][:4].isdigit() or len(r["year"]) == 4] == ["1999"]
    a = ds("api_b2011_annual")
    assert "1999" not in set(a["period"])
    q_raw = [r for p in (1, 2, 3) for r in raw_records(f"nasapi_b2011_current_q_i01_p{p:02d}.json")]
    dup = [r for r in q_raw if r["year"] == "2019-20" and r["quarter"] == "Q1"
           and r["industry"] == "Agriculture, Livestock, Forestry and Fishing"]
    assert len(dup) == 2 and dup[0] == dup[1]
    q = ds("api_b2011_quarterly").filter(pl.col("series_id") == "api.gva.ind_agri.current")
    assert q.filter(pl.col("period") == "Q1 2019-20")["value"].to_list() == [float(dup[0]["current_price"])]


def test_api_rows_carry_snapshot_vintage_and_api_provenance():
    for name in API_SETS:
        d = ds(name)
        assert set(d["source_id"]) == {"mospi_nas_api"} and set(d["status"]) == {"official"}
        assert set(d["unit"]) == {"INR_crore"}
        assert d["vintage"].n_unique() == 1 and d["vintage"][0] >= "2026-09-29"


# ---- F1 identity (gap map F1) ----------------------------------------------------------------------------------
def test_f1_ce_receivable_by_residents():
    d = ds("derived_residuals").filter(pl.col("series_id") == "derived.ce_receivable_by_residents.current")
    s71, s61 = ds("s7_1"), ds("s6_1")
    for per in ("2022-23", "2023-24", "2024-25"):
        want = (val(s71, "s7_1.total.ce.current", per)
                + val(s61, "s6_1.compensation_of_employees_from_rest_of_the_world.current", per)
                - val(s61, "s6_1.compensation_of_employees_to_the_rest_of_the_world.current", per))
        assert abs(val(d, "derived.ce_receivable_by_residents.current", per) - want) < 1e-3
    # COVERAGE.md F1: 94,42,897 + 62,344 - 30,636 = 94,74,605 (2023-24)
    assert round(val(d, "derived.ce_receivable_by_residents.current", "2023-24")) == 9474605
    rec = checks.load_provenance(U).filter(pl.col("prov_id") == d["prov_id"][0]).row(0, named=True)
    assert rec["status"] == "derived" and rec["method"]
    inputs = set(rec["inputs"].split(",")) if isinstance(rec["inputs"], str) else set(rec["inputs"])
    assert set(s71["prov_id"]) & inputs and set(s61["prov_id"]) & inputs


# ---- State code map (DECISIONS D1-9) ---------------------------------------------------------------------------
def test_4_1_state_rows_use_the_shared_code_map():
    d = ds("s4_1").filter(pl.col("geography") != "IN")
    assert d.height and d["geography"].n_unique() == 31
    for label, code in d.select("item_label", "geography").unique().iter_rows():
        assert geo.state_code(label) == code, label


# ---- SNA code-column guard (verifier note s2-1) -----------------------------------------------------------------
class _WS(dict):
    def __getitem__(self, cell):
        return SimpleNamespace(value=self.get(cell))


def _cfg(key):
    return SimpleNamespace(key=key, code_col="P")


def test_code_guard_rejects_a_one_sided_code():
    assert oldbase._row_code(_WS({"A5": "D1", "P5": "D1"}), _cfg("nas2024/2.0"), 5) == "D1"
    assert oldbase._row_code(_WS({}), _cfg("nas2024/2.0"), 5) == ""
    for cells in ({"A5": "D1"}, {"P5": "D1"}, {"A5": "D1", "P5": "D2"}):
        with pytest.raises(ValueError, match="disagree or only one"):
            oldbase._row_code(_WS(cells), _cfg("nas2024/2.0"), 5)


def test_code_guard_whitelist_is_exact():
    ws = _WS({"A11": "P1+34:3411:153", "P11": "P1"})
    assert oldbase._row_code(ws, _cfg("nas2024/1.15"), 11) == "P1"
    with pytest.raises(ValueError):  # same cells on another row or statement are not accepted
        oldbase._row_code(_WS({"A12": "P1+34:3411:153", "P12": "P1"}), _cfg("nas2024/1.15"), 12)
    with pytest.raises(ValueError):
        oldbase._row_code(_WS({"A11": "", "P11": "P1"}), _cfg("nas2024/1.15"), 11)
