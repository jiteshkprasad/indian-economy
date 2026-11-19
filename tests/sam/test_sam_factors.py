"""The factors block (V1a V2a V3 V4 F1 F1a F2 F3 F3a F3b F3c F4 F4b).

Three layers:
1. the pure functions in `pipeline/sam/blocks/_factors_lib.py` on small fixtures;
2. a full build of the block in a scratch layout (a copy of data/clean, production's built outputs and a
   SYNTHETIC households stub: made-up keys that exist only in the test) so the contract, the identities and
   every official total can be tested before the real households block exists;
3. the real build (skipped until households and factors are built): fresh build equals the files, checks.

Every official value is recomputed here from data/clean (polars), never typed in. The stub's numbers are
test fixtures, not data: they never reach data/sam.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import polars as pl
import pytest

from pipeline.core import io
from pipeline.core.io import canonical_floats
from pipeline.core.paths import Layout
from pipeline.core.schema import PROV_DTYPES
from pipeline.sam import spec
from pipeline.sam.blocks import _factors_lib as lib
from pipeline.sam.blocks import factors
from pipeline.sam.framework import SamPaths, build_block_module

pytestmark = pytest.mark.sam

LAYOUT = Layout.default()
PATHS = SamPaths(LAYOUT)
YEAR = spec.YEAR
HH = factors.HH
FC = ["E_RBI", "E_BANK", "E_NBFC", "E_INSP"]


# =============================================================================================
# 1. pure functions
# =============================================================================================


def test_ras_two_columns_hits_both_margins_and_respects_rows():
    rows = {"a": 100.0, "b": 50.0, "c": 30.0}
    got = lib.ras_two_columns(rows, 90.0, {"a": 10.0, "b": 40.0, "c": 0.0})
    assert sum(got.values()) == pytest.approx(90.0, abs=1e-8)
    assert got["c"] == 0.0  # no prior, no household part
    for a, v in got.items():
        assert 0.0 <= v <= rows[a] + 1e-9
    assert got["b"] / rows["b"] > got["a"] / rows["a"]  # the prior's ordering survives


def test_ras_two_columns_refuses_an_impossible_total():
    with pytest.raises(lib.FactorsError):
        lib.ras_two_columns({"a": 10.0, "b": 10.0}, 15.0, {"a": 1.0, "b": 0.0})


def test_apply_floor_scales_and_caps():
    reg, ce = {"a": 10.0, "b": 50.0}, {"a": 12.0, "b": 100.0}
    same, added = lib.apply_floor(reg, ce, 55.0)
    assert same == reg and added == 0.0
    new, added = lib.apply_floor(reg, ce, 90.0)
    assert sum(new.values()) == pytest.approx(90.0, abs=1e-6)
    assert new["a"] <= 12.0 + 1e-12 and added == pytest.approx(30.0, abs=1e-6)
    with pytest.raises(lib.FactorsError):
        lib.apply_floor(reg, ce, 200.0)


def test_labour_split_functions_on_a_fixture():
    groups = {"g1": ["x"], "g2": ["y", "z"]}
    share = {("x", "rural"): 50.0, ("x", "urban"): 10.0, ("y", "rural"): 30.0, ("y", "urban"): 60.0,
             ("z", "rural"): 20.0, ("z", "urban"): 30.0}  # fmt: skip
    w = lib.workers_by_group({"rural": 50.0, "urban": 40.0}, {"rural": 100.0, "urban": 50.0}, share, groups)
    assert w[("g1", "rural")] == pytest.approx(0.5 * 100 * 0.5)
    assert w[("g2", "urban")] == pytest.approx(0.4 * 50 * 0.9)
    wage = lib.casual_wage_by_group(share, {("x", "rural"): 300.0, ("x", "urban"): 400.0, ("y", "rural"): 500.0,
                                            ("y", "urban"): 600.0, ("z", "rural"): 700.0}, groups)  # fmt: skip
    assert wage[("g2", "rural")] == pytest.approx((30 * 500 + 20 * 700) / 50)
    assert wage[("g2", "urban")] == pytest.approx(600.0)  # z has no urban wage: left out of the weights
    reg_sh = {k: 50.0 for k in w}
    cas_sh = {k: 25.0 for k in w}
    reg, cas = lib.wage_bills(w, reg_sh, cas_sh, {"rural": 1000.0, "urban": 2000.0}, wage, 300.0)
    sr = lib.regular_share(reg, cas)
    r = w[("g1", "rural")] * 0.5 * 1000 + w[("g1", "urban")] * 0.5 * 2000
    c = w[("g1", "rural")] * 0.25 * 300 * 300 + w[("g1", "urban")] * 0.25 * 400 * 300
    assert sr["g1"] == pytest.approx(r / (r + c))


def test_group_index_with_and_without_a_crosswalk():
    idx = {"q1": 0.1, "q2": 0.15, "q3": 0.2, "q4": 0.25, "q5": 0.3}
    no_x = lib.group_index(idx, HH, None)
    assert no_x["H_R1"] == idx["q1"] and no_x["H_U5"] == idx["q5"]
    ident = {g: {f"q{g[-1]}": 1.0} for g in HH}
    assert lib.group_index(idx, HH, ident) == no_x
    mix = dict(ident, H_R2={"q1": 0.5, "q3": 0.5})
    assert lib.group_index(idx, HH, mix)["H_R2"] == pytest.approx(0.15)
    sh = lib.area_shares({g: 1.0 for g in HH}, no_x, factors.AREA_GROUPS["rural"])
    assert sum(sh.values()) == pytest.approx(1.0) and sh["H_R5"] == pytest.approx(0.3)


def _clean(dataset: str, period: str | None = YEAR) -> pl.DataFrame:
    unit = next(p.parent.name for p in LAYOUT.clean.glob(f"*/{dataset}.parquet"))
    df = pl.read_parquet(LAYOUT.clean / unit / f"{dataset}.parquet")
    if period is not None:
        df = df.filter(pl.col("period") == period)
    latest = df.group_by("series_id", "period", maintain_order=True).agg(pl.col("vintage").max().alias("_v"))
    return df.join(latest, on=["series_id", "period"]).filter(pl.col("vintage") == pl.col("_v")).drop("_v")


def _v(df: pl.DataFrame, sid: str) -> float:
    r = df.filter(pl.col("series_id") == sid)
    assert r.height == 1, sid
    return float(r["value"][0])


def test_ifpri_regular_index_matches_the_plan_from_clean_data():
    """Plan s.2.5: regular labour <- IFPRI medium + high educated x T11 spending: 6.47/10.10/13.70/19.43/50.30%."""
    t = _clean("io_tables_ifpri_2223_datapaper", "2022-23")
    comp = {q: _v(t, f"ifpri.t10.labour_medium_educated.{q}") + _v(t, f"ifpri.t10.labour_high_educated.{q}")
            for q in lib.QUINTILES}  # fmt: skip
    spend = {q: _v(t, f"ifpri.t11.total_spending_per_capita.{q}") for q in lib.QUINTILES}
    got = [round(100 * v, 2) for v in lib.ifpri_index(comp, spend).values()]
    assert got == [6.47, 10.10, 13.70, 19.43, 50.30]


# =============================================================================================
# 2. scratch build with a synthetic households stub
# =============================================================================================

STUB_PID = "sam_households:00000000000{}"
STUB_POP = {"rural": 170_947_080.0, "urban": 72_581_600.0}  # synthetic persons per group (equal within area)
STUB_FA = [1.0, 1.4, 1.9, 2.6, 2.2, 1.2, 1.8, 2.5, 3.4, 3.0]  # synthetic fixed-assets key (relative levels)
STUB_IMP = [1.2, 2.2, 3.4, 5.9, 14.2, 7.4, 10.4, 12.8, 16.4, 26.0]  # synthetic imputed-rent consumption key
STUB_C4A = {"imputed_rent": 1_596_000.0, "actual_rent": 531_988.0, "govt_housing": 20_056.0}  # synthetic levels
STUB_HCES = [4.0, 5.5, 7.0, 9.0, 14.0, 2.5, 3.6, 4.7, 6.2, 10.5]  # synthetic HCES consumption key (relative levels)


def _stub_prov(i: int, source: str) -> dict:
    return {"prov_id": STUB_PID.format(i), "ingest_unit": "sam_households", "source_id": source, "url": None,
            "raw_path": None, "raw_sha256": None, "retrieved_at": None, "table_id": "synthetic test stub",
            "locator": "tests/sam/test_sam_factors.py", "unit_as_published": "Rs crore", "conversion": "none",
            "price_basis": "current", "base_year": "2022-23", "vintage": "2026-08-31",
            "release": "synthetic test stub", "status": "estimated",
            "method": "SYNTHETIC households stub for the factors block tests (not data)", "inputs": None,
            "notes": "synthetic"}  # fmt: skip


def write_households_stub(layout: Layout, *, xwalk: dict | None = None) -> None:
    """A minimal households block (entries, empty constraints, provenance, catalog, satellites) with
    made-up keys in the shape of CROSS_REVIEW s.4.3, so factors can be built before households exists."""
    paths = SamPaths(layout)
    paths.blocks.mkdir(parents=True, exist_ok=True)
    p_pop, p_fa, p_c4a, p_xw = (STUB_PID.format(i) for i in range(1, 5))
    rows = []
    tot = sum(STUB_IMP)
    for g, k in zip(HH, STUB_IMP, strict=True):
        for comp, level in STUB_C4A.items():
            share = k / tot if comp == "imputed_rent" else 0.1
            rows.append(dict(row="C_DWEL", col=g, ref="C4a", component=comp, value=level * share, status="estimated",
                             role="free", tol_rel=None, confidence="low", bop_function=None, prov_id=p_c4a,
                             note=None))  # fmt: skip
    ent = pl.DataFrame(rows, schema=spec.ENTRY_DTYPES, orient="row").with_columns(pl.lit("households").alias("block"))
    io.write_parquet(ent, paths.entries("households"), sort_by=spec.ENTRY_KEY)
    con = pl.DataFrame(schema=spec.CONSTRAINT_DTYPES).with_columns(pl.lit("households").alias("block"))
    io.write_parquet(con, paths.constraints("households"), sort_by=("constraint_id",))
    prov = pl.DataFrame([_stub_prov(1, "mospi_hces_2023_24"), _stub_prov(2, "mospi_aidis_2019"),
                         _stub_prov(3, "mospi_hces_2023_24"), _stub_prov(4, "mospi_hces_2023_24")],
                        schema=PROV_DTYPES, orient="row")  # fmt: skip
    io.write_parquet(prov, paths.provenance("households"), sort_by=("prov_id",))
    keys = []
    for i, g in enumerate(HH):
        area = "rural" if g.startswith("H_R") else "urban"
        for key, level, pid in (("pop_persons", STUB_POP[area], p_pop), ("aidis_fixed_assets", STUB_FA[i], p_fa),
                                ("hces_total", STUB_HCES[i], p_pop)):  # fmt: skip
            keys.append({"series_id": f"{key}.level.{g.lower()}", "household_group": g, "key": key, "measure": "level",
                         "value": level, "unit": "count", "status": "estimated", "prov_id": pid})  # fmt: skip
    sdir = paths.satellites("households")
    sdir.mkdir(parents=True, exist_ok=True)
    io.write_parquet(pl.DataFrame(keys), sdir / "hh_keys.parquet", sort_by=("series_id",))
    if xwalk is not None:
        # the shape households publishes: persons and shares by group x quintile, plus cut-off memo rows
        xr = [{"series_id": f"{g.lower()}.{q}.{m}", "household_group": g, "national_quintile": q, "measure": m,
               "value": v * (1.0 if m == "share" else 1e6), "unit": "ratio" if m == "share" else "count",
               "status": "estimated", "prov_id": p_xw}
              for g, qs in xwalk.items() for q, v in qs.items() for m in ("persons", "share")]  # fmt: skip
        xr.append(
            {
                "series_id": "cut.q1_q2",
                "household_group": None,
                "national_quintile": "q1|q2",
                "measure": "cut_mpce",
                "value": 2500.0,
                "unit": "INR",
                "status": "estimated",
                "prov_id": p_xw,
            }
        )
        io.write_parquet(pl.DataFrame(xr), sdir / "hh_national_quintile_xwalk.parquet", sort_by=("series_id",))
    io.write_json(paths.catalog("households"), {"block": "households", "note": "synthetic test stub"})


def scratch_layout(base: Path, *, xwalk: dict | None = None) -> Layout:
    """data/clean copied under `base`, production's built outputs copied, households stubbed."""
    layout = Layout.scratch(base)
    if not (base / "clean").exists():
        shutil.copytree(LAYOUT.clean, base / "clean", ignore=shutil.ignore_patterns(".*"))
    paths = SamPaths(layout)
    paths.blocks.mkdir(parents=True, exist_ok=True)
    if not PATHS.built("production"):
        pytest.fail("production block not built: run `uv run python -m pipeline sam production`")
    for p in sorted(PATHS.blocks.glob("production_*")):
        dst = paths.blocks / p.name
        if p.is_dir():
            shutil.copytree(p, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(p, dst)
    write_households_stub(layout, xwalk=xwalk)
    return layout


@pytest.fixture(scope="module")
def stub(tmp_path_factory):
    layout = scratch_layout(tmp_path_factory.mktemp("factors_stub"))
    r, valid = build_block_module(factors, layout, write=False)
    assert r.ok, r.message
    return valid


@pytest.fixture(scope="module")
def real():
    if not (PATHS.built("households") and PATHS.built("production")):
        pytest.skip("households block not built yet: the real factors build waits for it")
    r, valid = build_block_module(factors, LAYOUT, write=False)
    assert r.ok, r.message
    return valid


@pytest.fixture(scope="module", params=["stub", "real"])
def v(request):
    return request.getfixturevalue(request.param)


def _e(valid, ref=None, row=None, col=None, comp=None) -> pl.DataFrame:
    df = valid.entries
    for c, x in (("ref", ref), ("row", row), ("col", col), ("component", comp)):
        if x is not None:
            df = df.filter(pl.col(c).is_in([x] if isinstance(x, str) else list(x)))
    return df


def _sut_by_activity(items: list[str]) -> dict[str, float]:
    conc = pl.read_csv(LAYOUT.concordance / "io_tables_sut_industry_to_sam34.csv", infer_schema=False).select(
        ("sut_i" + pl.col("sut_industry").str.zfill(2)).alias("industry"), "activity"
    )
    va = _clean("io_tables_sut_va").filter(pl.col("item_code").is_in(items))
    j = va.join(conc, on="industry", how="inner")
    agg = j.group_by("activity", maintain_order=True).agg(pl.col("value").sum()).sort("activity")
    return dict(agg.iter_rows())


def test_v1_by_activity_equals_the_sut(v):
    ce = _sut_by_activity(["ce"])
    got = dict(_e(v, "V1a").group_by("col", maintain_order=True).agg(pl.col("value").sum()).sort("col").iter_rows())
    for a, t in ce.items():
        assert got.get(a, 0.0) == pytest.approx(t, abs=0.01), a
    assert "A_DWEL" not in got
    assert sum(got.values()) == pytest.approx(_v(_clean("mospi_nas_2026_s7_1"), "s7_1.total.ce.current"), abs=1.0)


def test_v2_by_activity_equals_the_sut(v):
    gos = _sut_by_activity(["os_mi", "cfc"])
    got = dict(_e(v, "V2a").group_by("col", maintain_order=True).agg(pl.col("value").sum()).sort("col").iter_rows())
    for a, t in gos.items():
        assert got[a] == pytest.approx(t, abs=0.01), a
    s71 = _clean("mospi_nas_2026_s7_1")
    nas = _v(s71, "s7_1.total.os_mi.current") + _v(s71, "s7_1.total.cfc.current")
    assert sum(got.values()) == pytest.approx(nas, abs=1.0)


def test_production_targets_are_split_not_redeclared(v):
    """XR-15: factors re-declares no V1/V2 per-activity target; its splits add up to production's."""
    assert not v.constraints.filter(pl.col("ref").is_in(["V1", "V2"])).height
    prod = pl.read_parquet(PATHS.constraints("production"))
    for stem, ref in (("ce.", "V1a"), ("os_mi_cfc.", "V2a")):
        for r in prod.filter(pl.col("constraint_id").str.starts_with(stem)).iter_rows(named=True):
            got = _e(v, ref, col=r["cols"])["value"].sum()
            assert got == pytest.approx(r["target"], abs=1e-6), r["constraint_id"]


def test_household_anchor_by_nas_group(v):
    c7 = _clean("mospi_nas_2026_s7_1c")
    comps = ["mixed_income", "hh_quasi", "hh_dwelling_imputed", "hh_dwelling_actual"]
    total = 0.0
    for k, (acts, rows) in factors.HH_GROUPS.items():
        want = sum(_v(c7, f"s7_1c.{n}.os_mi.current") + _v(c7, f"s7_1c.{n}.cfc.current") for n in rows)
        got = _e(v, "V2a", col=acts, comp=comps)["value"].sum()
        assert got == pytest.approx(want, abs=0.01), k
        total += got
    assert total == pytest.approx(_v(c7, "s7_1c.total.os_mi.current") + _v(c7, "s7_1c.total.cfc.current"), abs=1.0)


def test_household_factor_income_totals(v):
    c7 = _clean("mospi_nas_2026_s7_1c")
    hh = _v(c7, "s7_1c.total.os_mi.current") + _v(c7, "s7_1c.total.cfc.current")
    got = _e(v, ["F2", "F3a", "F3b", "F3c"], row=HH)["value"].sum()
    assert got == pytest.approx(hh, abs=1.0)
    f1 = _v(_clean("mospi_nas_2026_derived_residuals"), "derived.ce_receivable_by_residents.current")
    assert _e(v, "F1a", row=HH)["value"].sum() == pytest.approx(f1, abs=1.0)
    con = v.constraints.filter(pl.col("constraint_id") == "f2f3.hh_gross_os_mi")
    assert con["target"][0] == pytest.approx(hh, abs=1e-9)
    assert v.constraints.filter(pl.col("constraint_id") == "f1.total")["target"][0] == pytest.approx(f1, abs=1e-9)


def _account_gap(valid, acct: str, extra_col: float = 0.0) -> float:
    e = valid.entries
    return e.filter(pl.col("row") == acct)["value"].sum() - e.filter(pl.col("col") == acct)["value"].sum() - extra_col


def test_factor_accounts_close_in_the_prior(v):
    """F_LREG, F_LCAS, F_MIXD close exactly; F_GOSC closes once the FC GOS (fincorp's F4a) is paid out."""
    for acct in ("F_LREG", "F_LCAS", "F_MIXD"):
        assert abs(_account_gap(v, acct)) < 1e-6, acct
    fc = v.constraints.filter(pl.col("constraint_id") == "f4.fc_gos")["target"][0]
    assert abs(_account_gap(v, "F_GOSC", fc)) < 0.1


def test_v3_v4_are_nas_6_1_and_agree_with_the_bop(v):
    s61 = _clean("mospi_nas_2026_s6_1")
    bop = _clean("external_sector_bop_bpm6_annual")
    v3 = _e(v, "V3")
    v4 = _e(v, "V4")
    assert v3.height == 1 and v3["row"][0] == "F_LREG" and v3["col"][0] == "R_ROW" and v3["role"][0] == "fixed"
    assert v4.height == 1 and v4["row"][0] == "R_ROW" and v4["col"][0] == "F_LREG" and v4["role"][0] == "fixed"
    assert v3["value"][0] == _v(s61, "s6_1.compensation_of_employees_from_rest_of_the_world.current")
    assert v4["value"][0] == _v(s61, "s6_1.compensation_of_employees_to_the_rest_of_the_world.current")
    assert v3["value"][0] == pytest.approx(_v(bop, "bpm6.inr.bpm6_1_b_1.credit.current"), abs=1.0)
    assert v4["value"][0] == pytest.approx(_v(bop, "bpm6.inr.bpm6_1_b_1.debit.current"), abs=1.0)


def _sector_table() -> dict[str, dict[str, float]]:
    a, b = _clean("mospi_nas_2026_s7_1a"), _clean("mospi_nas_2026_s7_1b")
    g, h = _clean("mospi_nas_2026_s8_15_1"), _clean("mospi_nas_2026_s7_1c")
    it = ("gva", "ce", "net_production_taxes", "cfc", "os")
    sec = {
        "nfc_public": {i: _v(a, f"s7_1a.total.{i}.current") - _v(g, f"s8_15_1.total.{i}.current")
                       - _v(a, f"s7_1a.financial.{i}.current") for i in it},
        "nfc_private": {i: _v(b, f"s7_1b.total.{i}.current") - _v(b, f"s7_1b.financial.{i}.current") for i in it},
        "fc_public": {i: _v(a, f"s7_1a.financial.{i}.current") for i in it},
        "fc_private": {i: _v(b, f"s7_1b.financial.{i}.current") for i in it},
        "gg": {i: _v(g, f"s8_15_1.total.{i}.current") for i in it},
        "households_npish": {i: _v(h, f"s7_1c.total.{'os_mi' if i == 'os' else i}.current") for i in it},
    }  # fmt: skip
    for s in sec.values():
        s["gos"] = s["gva"] - s["ce"] - s["net_production_taxes"]
    return sec


def test_f4_nfc_entries_and_sector_arithmetic(v):
    sec = _sector_table()
    assert _e(v, "F4", row="E_NFPU")["value"][0] == pytest.approx(sec["nfc_public"]["gos"], abs=1e-6)
    assert _e(v, "F4", row="E_NFPR")["value"][0] == pytest.approx(sec["nfc_private"]["gos"], abs=1e-6)
    assert set(_e(v, "F4")["role"]) == {"fixed"} and set(_e(v, "F4")["row"]) == {"E_NFPU", "E_NFPR"}
    s114 = _clean("mospi_nas_2026_s1_14")
    for s, d in sec.items():
        assert d["gva"] == pytest.approx(_v(s114, f"s1_14.{s}.gross_value_added_at_basic_prices.current"), abs=0.01)
        assert d["cfc"] == pytest.approx(_v(s114, f"s1_14.{s}.consumption_of_fixed_capital.current"), abs=0.01)
        assert d["gos"] == pytest.approx(d["os"] + d["cfc"], abs=0.01)
    s816 = _clean("mospi_nas_2026_s8_16")
    assert sec["nfc_public"]["cfc"] == pytest.approx(
        _v(s816, "s8_16.departmental_enterprises.cfc.current") + _v(s816, "s8_16.non_financial.cfc.current"), abs=0.01
    )


def test_fc_and_gg_constraints(v):
    a, b = _clean("mospi_nas_2026_s7_1a"), _clean("mospi_nas_2026_s7_1b")
    fc_want = (_v(a, "s7_1a.financial.os.current") + _v(a, "s7_1a.financial.cfc.current")
               + _v(b, "s7_1b.financial.os.current") + _v(b, "s7_1b.financial.cfc.current"))  # fmt: skip
    fc = v.constraints.filter(pl.col("constraint_id") == "f4.fc_gos").row(0, named=True)
    assert fc["target"] == fc_want  # byte-identical to fincorp's arithmetic
    assert fc["rows"] == ",".join(FC) and fc["cols"] == "F_GOSC" and fc["refs"] == "F4a" and fc["tol_abs"] == 1.0
    sut = _sut_by_activity(["os_mi", "cfc"])
    assert fc["target"] == pytest.approx(sut["A_FINS"] + sut["A_INSR"], abs=1.0)
    gg = v.constraints.filter(pl.col("constraint_id") == "f4.gg_gos").row(0, named=True)
    for ds, sid in (("mospi_nas_2026_s1_14", "s1_14.gg.consumption_of_fixed_capital.current"),
                    ("mospi_nas_2026_s4_1", "s4_1.consumption_of_fixed_capital.current"),
                    ("mospi_nas_2026_s8_16", "s8_16.administrative_departments.cfc.current")):  # fmt: skip
        assert gg["target"] == pytest.approx(_v(_clean(ds), sid), abs=0.01)
    sec = _sector_table()
    assert sum(s["gos"] for s in sec.values()) == pytest.approx(sum(sut.values()), abs=1.0)
    assert _e(v, "F4b")["value"].sum() == pytest.approx(gg["target"], abs=1e-6)


def test_structure_signs_and_forbidden_cells(v):
    e = v.entries
    assert (e["value"] > 0).all()
    assert not _e(v, row="F_MIXD", col=["A_DWEL", "A_FINS", "A_INSR", "A_PADM", "A_COAL", "A_OILG"]).height
    assert not _e(v, row="F_LCAS", col="A_PADM").height
    assert not e.filter(pl.col("row").is_in(FC)).height  # FC GOS is fincorp's (F4a)
    assert not _e(v, "F4", row=["G_CEN", "G_STA"]).height  # GG GOS only via F4b
    assert not e.filter(pl.col("ref") == "F1").height and not e.filter(pl.col("ref") == "F3").height
    assert set(_e(v, "F1a")["col"]) == {"F_LREG", "F_LCAS"} and set(_e(v, "F2")["component"]) == {"farm", "nonfarm"}
    assert set(e.filter(pl.col("ref").is_in(["F1a", "F2", "F3a", "F3b", "F3c"]))["row"]) == set(HH)
    assert set(_e(v, "V2a")["component"]) <= {"mixed_income", "corp_gov", "hh_quasi", "hh_dwelling_imputed",
                                                "hh_dwelling_actual"}  # fmt: skip


def test_caps_floors_and_public_administration(v):
    gos = _sut_by_activity(["os_mi", "cfc"])
    hh = _e(v, "V2a", comp=["mixed_income", "hh_quasi", "hh_dwelling_imputed", "hh_dwelling_actual"])
    for a, t in dict(
        hh.group_by("col", maintain_order=True).agg(pl.col("value").sum()).sort("col").iter_rows()
    ).items():
        assert t <= gos[a] + 1e-6, a
    a71 = _clean("mospi_nas_2026_s7_1a")
    for name, (acts, rows) in factors.FLOOR_GROUPS.items():
        floor = sum(_v(a71, f"s7_1a.{n}.ce.current") for n in rows)
        assert _e(v, "V1a", row="F_LREG", col=acts)["value"].sum() >= floor - 1e-6, name
        c = v.constraints.filter(pl.col("constraint_id") == f"v1a_floor.{name}")
        assert c["kind"][0] == "min" and c["target"][0] == pytest.approx(floor, abs=1e-9)
    padm = _e(v, "V1a", col="A_PADM")
    assert padm.height == 1 and padm["row"][0] == "F_LREG"


def test_f3a_is_keyed_like_c4a_imputed_rent(v, request):
    f3a = _e(v, "F3a")
    if request.node.callspec.params["v"] == "stub":
        c4a = dict(zip(HH, STUB_IMP, strict=True))
    else:
        he = pl.read_parquet(PATHS.entries("households")).filter((pl.col("ref") == "C4a")
                                                                 & (pl.col("component") == "imputed_rent"))  # fmt: skip
        c4a = dict(he.group_by("col", maintain_order=True).agg(pl.col("value").sum()).sort("col").iter_rows())
    tot_k, tot_f = sum(c4a.values()), f3a["value"].sum()
    for g, val in f3a.select("row", "value").iter_rows():
        assert val / tot_f == pytest.approx(c4a[g] / tot_k, abs=1e-9)
    bands = v.constraints.filter(pl.col("constraint_id").str.starts_with("f3a_band."))
    assert bands.height == f3a.height and set(bands["kind"]) == {"band"} and set(bands["tol_rel"]) == {0.10}


def test_f4b_centre_share(v):
    s41 = _clean("mospi_nas_2026_s4_1")
    gia = _clean("union_fiscal_fa_gia")
    rev = _v(gia, "gia.cash.autonomous_bodies.total") - _v(gia, "gia.cash.autonomous_bodies.capital_assets")
    want = (_v(s41, "s4_1.central_government.current") + min(rev, _v(s41, "s4_1.autonomous_institutions.current"))
            ) / _v(s41, "s4_1.net_value_added.current")  # fmt: skip
    cen = _e(v, "F4b", row="G_CEN")["value"][0]
    assert cen / _e(v, "F4b")["value"].sum() == pytest.approx(want, abs=1e-12)
    assert 0.25 <= want <= 0.35
    sat = v.satellites["gg_centre_state_key"][1]
    assert sat.filter(pl.col("series_id") == "centre_share")["value"][0] == pytest.approx(want, abs=1e-12)


def test_parameter_d_is_recomputed_from_clean_data(v):
    asuse = _clean("labour_enterprise_surveys_asuse_2324_activity", "2023-10/2024-09")
    api = _clean("labour_enterprise_surveys_plfs_earnings_api", None).filter(
        (pl.col("series_id") == "api_i7.casual_wage_earnings_day.total.person.current")
        & pl.col("period").is_in(list(factors.QUARTERS))
    )
    assert api.height == 4
    d = _v(asuse, "t33.emol_per_hired_worker.informal.asuse_all.total.current") / api["value"].mean()
    par = v.satellites["v1a_parameters"][1]
    row = par.filter(pl.col("series_id") == "d_days")
    assert row["value"][0] == pytest.approx(d, abs=1e-6)
    rec = v.provenance.filter(pl.col("prov_id") == row["prov_id"][0])
    assert rec["status"][0] == "estimated" and "parameter D" in rec["method"][0]


def test_f1a_area_totals_and_within_area_ifpri_gradient(v, request):
    """F1a: area totals equal the V1a by-product; within an area the groups follow the IFPRI index."""
    keys = v.satellites["factor_income_keys"][1]
    for k, ref_col in (("lreg", "F_LREG"), ("lcas", "F_LCAS")):
        ent = _e(v, "F1a", col=ref_col)
        for area, groups in factors.AREA_GROUPS.items():
            tot = keys.filter(pl.col("series_id") == f"{k}.area_total.{area}")["value"][0]
            assert ent.filter(pl.col("row").is_in(groups))["value"].sum() == pytest.approx(tot, abs=1e-3)
    if request.node.callspec.params["v"] != "stub":
        return  # the real crosswalk and persons differ by group; checked by the verifier
    t = _clean("io_tables_ifpri_2223_datapaper", "2022-23")
    comp = {q: _v(t, f"ifpri.t10.labour_medium_educated.{q}") + _v(t, f"ifpri.t10.labour_high_educated.{q}")
            for q in lib.QUINTILES}  # fmt: skip
    idx = lib.ifpri_index(comp, {q: _v(t, f"ifpri.t11.total_spending_per_capita.{q}") for q in lib.QUINTILES})
    reg = _e(v, "F1a", col="F_LREG")
    for groups in factors.AREA_GROUPS.values():
        sub = reg.filter(pl.col("row").is_in(groups))
        for g, val in sub.select("row", "value").iter_rows():
            assert val / sub["value"].sum() == pytest.approx(idx[f"q{g[-1]}"], abs=1e-9)  # stub: equal persons


def test_sanity_bands(v):
    ce = _e(v, "V1a")
    nat = ce.filter(pl.col("row") == "F_LREG")["value"].sum() / ce["value"].sum()
    assert 0.70 <= nat <= 0.85
    gos = _sut_by_activity(["os_mi", "cfc"])
    dw = _e(v, "V2a", col="A_DWEL", comp=["hh_dwelling_imputed", "hh_dwelling_actual"])["value"].sum()
    assert 0.70 <= dw / gos["A_DWEL"] <= 1.0
    c7 = _clean("mospi_nas_2026_s7_1c")
    hh = _v(c7, "s7_1c.total.os_mi.current") + _v(c7, "s7_1c.total.cfc.current")
    assert 0 <= _e(v, "F3c")["value"].sum() / hh <= 0.05


def test_asuse_mapping_uses_subcategories_and_utilities_have_no_asuse_key(v):
    """Verification V-F-2 / V-F-3: every activity uses ASUSE sub-categories (trade T1-T5, not the aggregate T);
    utilities have no ASUSE category (E is only non-captive electricity, NIC 36-39 sits in S15), so q = 0 and
    their mixed income is split rural/urban by PLFS 35-39 self-employment, like mining and construction."""
    assert factors.ASUSE_MAP["A_TRAD"] == ["t1", "t2", "t3", "t4", "t5"]
    cats = [c for cs in factors.ASUSE_MAP.values() for c in cs]
    assert not {"t", "m", "s", "e"} & set(cats)  # no aggregate category, and not the electricity-only E
    assert "A_UTIL" not in factors.ASUSE_MAP and set(factors.PLFS_RU_KEY) == {"A_OMIN", "A_CNST", "A_UTIL"}
    assert not _e(v, "V2a", col="A_UTIL", comp="hh_quasi").height
    va = v.satellites["va_split_by_activity"][1]
    assert not va.filter(pl.col("series_id") == "q_nonprop.a_util").height
    # q for trade recomputed from clean ASUSE 2023-24 (Tables 4, 6, 37) over T1-T5
    asu = _clean("labour_enterprise_surveys_asuse_2324_activity", "2023-10/2024-09")
    nonprop = gva = 0.0
    for c in factors.ASUSE_MAP["A_TRAD"]:
        for t in ("oae", "hwe"):
            g = _v(asu, f"t4.establishments.asuse_{c}.total.{t}")
            g *= _v(asu, f"t37.gva_per_estt.asuse_{c}.total.{t}.current")
            nonprop += sum(_v(asu, f"t6.estt_share.{o}.asuse_{c}.total.{t}") for o in factors.NONPROP) / 100.0 * g
            gva += g
    q = nonprop / gva
    assert va.filter(pl.col("series_id") == "q_nonprop.a_trad")["value"][0] == pytest.approx(q, abs=1e-9)
    c7 = _clean("mospi_nas_2026_s7_1c")
    hh_trade = _v(c7, "s7_1c.trade_repair.os_mi.current") + _v(c7, "s7_1c.trade_repair.cfc.current")
    assert _e(v, "V2a", col="A_TRAD", comp="hh_quasi")["value"][0] == pytest.approx(q * hh_trade, abs=1e-6)


def test_satellite_labels_are_honest(v):
    """Verification V-F-4 / V-F-5: a computed difference is not labelled official; wage bills carry a money unit."""
    prov = {r["prov_id"]: r for r in v.provenance.iter_rows(named=True)}
    key = v.satellites["gg_centre_state_key"][1]
    gia = key.filter(pl.col("series_id") == "gia.autonomous_bodies_revenue").row(0, named=True)
    assert gia["status"] == "derived" and prov[gia["prov_id"]]["status"] == "derived"
    assert "minus" in prov[gia["prov_id"]]["method"]
    for r in key.filter(pl.col("status") == "official").iter_rows(named=True):
        assert r["series_id"].startswith("nva."), r["series_id"]  # only NAS 4.1 values as published
    split = v.satellites["v1a_labour_split"][1]
    bills = split.filter(pl.col("item").str.starts_with("wage_bill"))
    assert bills.height == 36 and set(bills["unit"]) == {"INR_crore"}
    assert not split.filter((pl.col("unit") == "ratio") & (pl.col("value") > 1.0)).height


def test_method_texts_name_the_right_payers_and_bases(v):
    """Verification V-F-6 / V-F-8 / V-F-9 (wording)."""
    methods = v.provenance["method"].to_list()
    r9d = [m for m in methods if "R9d" in m]
    assert r9d and all("E_NFPU under R9d" in m for m in r9d)
    assert not [m for m in methods if "by government under R9d" in m]
    f1a = v.provenance.filter(pl.col("method").str.starts_with("Gap map F1a"))["method"].to_list()
    assert len(f1a) == 1 and "A_PADM" in f1a[0] and "58-99" in f1a[0]
    f2 = v.provenance.filter(pl.col("method").str.starts_with("Gap map F2 "))["method"].to_list()
    assert len(f2) == 1 and "35-39" in f2[0]
    bands = v.constraints.filter(pl.col("constraint_id").str.starts_with("f3a_band."))["description"].to_list()
    assert bands and all("fixed-level band" in d and "link shares, not levels" not in d for d in bands)


def test_checks_pass(v):
    failed = v.checks.filter(~pl.col("ok"))
    assert failed.height == 0, failed
    assert v.checks.height >= 40


def test_provenance_is_complete(v):
    prov = v.provenance
    ids = set(prov["prov_id"].to_list())
    assert set(v.entries["prov_id"].to_list()) <= ids and set(v.constraints["prov_id"].to_list()) <= ids
    for _, df in v.satellites.values():
        assert set(df["prov_id"].to_list()) <= ids
    est = prov.filter(pl.col("status") == "estimated")
    assert est.height and est.filter(pl.col("method").is_null() | ~pl.col("method").str.contains(
        r"Gap map|key|sensitivity|parameter")).height == 0  # fmt: skip
    clean_prov = {}
    for f in sorted(LAYOUT.clean.glob("*/_provenance.parquet")):
        for pid in pl.read_parquet(f, columns=["prov_id"])["prov_id"].to_list():
            clean_prov[pid] = True
    for ins in prov["inputs"].drop_nulls().to_list():
        for i in ins.split(","):
            assert i in clean_prov or i.startswith(("sam_factors:", "sam_production:", "sam_households:")), i


def test_mapping_is_k_eq_q_and_the_crosswalk_is_a_sensitivity(tmp_path):
    """DECISIONS D2-19: the entries use k = q whatever crosswalk households publishes; the crosswalk (and the
    HCES-rescaled k = q variant) are published as report-only sensitivity rows of factor_income_keys."""
    assert factors.IFPRI_MAPPING == "k_eq_q"
    top = {g: ({"q5": 1.0} if g in ("H_U4", "H_U5") else {f"q{g[-1]}": 1.0}) for g in HH}  # the real one's flaw
    layout = scratch_layout(tmp_path, xwalk=top)
    r, with_x = build_block_module(factors, layout, write=False)
    assert r.ok, r.message
    base = scratch_layout(tmp_path / "b")
    r2, without = build_block_module(factors, base, write=False)
    assert r2.ok, r2.message
    key = ["row", "col", "ref", "component"]
    for ref in ("F1a", "F2", "F3c"):
        a = with_x.entries.filter(pl.col("ref") == ref).sort(key)
        b = without.entries.filter(pl.col("ref") == ref).sort(key)
        assert a.select(key).equals(b.select(key))
        assert (a["value"] - b["value"]).abs().max() < 1e-6, ref  # the crosswalk does not touch the entries
    assert not any("crosswalk" in w for w in r.warnings)
    assert any("no hh_national_quintile_xwalk" in w and "sensitivity" in w for w in r2.warnings)
    fik = with_x.satellites["factor_income_keys"][1]
    lev = {(g, k): v for g, k, m, v in fik.select("household_group", "key", "measure", "value").iter_rows() if
           m == "level"}  # fmt: skip
    # the crosswalk sensitivity reproduces the flaw it replaced: H_U4 and H_U5 get the same regular labour income
    assert lev["H_U4", "sensitivity_xwalk_lreg"] == pytest.approx(lev["H_U5", "sensitivity_xwalk_lreg"], rel=1e-9)
    assert lev["H_U5", "lreg"] > 1.5 * lev["H_U4", "lreg"]  # k = q separates them
    fi_keys = ["lreg", "lcas", "mixd_farm", "mixd_nonfarm", "quasi_corporate", "imputed_rent", "actual_rent"]
    for var in ("xwalk", "hces"):
        for area, gs in factors.AREA_GROUPS.items():  # the mapping moves income only within an area
            for k in ("lreg", "lcas", "mixd_farm", "mixd_nonfarm", "quasi_corporate"):
                assert sum(lev[g, f"sensitivity_{var}_{k}"] for g in gs) == pytest.approx(
                    sum(lev[g, k] for g in gs), rel=1e-9), (var, k, area)  # fmt: skip
        for g in HH:
            want = sum(lev[g, k] for k in fi_keys) + sum(lev[g, f"sensitivity_{var}_{k}"] - lev[g, k] for k in
                                                         fi_keys[:5])  # fmt: skip
            assert lev[g, f"sensitivity_{var}_factor_income"] == pytest.approx(want, rel=1e-9)
    # HCES variant: within an area, group g's regular labour income is proportional to its HCES consumption x
    # IFPRI's T10 share of regular labour in quintile k's income (the stub has equal persons within an area)
    t = _clean("io_tables_ifpri_2223_datapaper", "2022-23")
    comp = {q: _v(t, f"ifpri.t10.labour_medium_educated.{q}") + _v(t, f"ifpri.t10.labour_high_educated.{q}")
            for q in lib.QUINTILES}  # fmt: skip
    for gs in factors.AREA_GROUPS.values():
        raw = {g: comp[f"q{g[-1]}"] * STUB_HCES[HH.index(g)] for g in gs}
        tot = sum(lev[g, "sensitivity_hces_lreg"] for g in gs)
        for g in gs:
            assert lev[g, "sensitivity_hces_lreg"] / tot == pytest.approx(raw[g] / sum(raw.values()), abs=1e-9)
    prov = {p["prov_id"]: p for p in with_x.provenance.iter_rows(named=True)}
    sens = fik.filter(pl.col("key").str.starts_with("sensitivity_xwalk"))["prov_id"].unique().to_list()
    assert len(sens) == 1 and "D2-19" in prov[sens[0]]["method"] and prov[sens[0]]["status"] == "estimated"
    f1a = with_x.provenance.filter(pl.col("method").str.starts_with("Gap map F1a"))["method"][0]
    assert "k = q" in f1a and "D2-19" in f1a


def test_crosswalk_mapping_still_works_when_switched(tmp_path, monkeypatch):
    """IFPRI_MAPPING = "crosswalk" (the pre-D2-19 mapping) stays available: an identity crosswalk reproduces k = q,
    and the k = q mapping is then the sensitivity."""
    monkeypatch.setattr(factors, "IFPRI_MAPPING", "crosswalk")
    ident = {g: {f"q{g[-1]}": 1.0} for g in HH}
    r, with_x = build_block_module(factors, scratch_layout(tmp_path, xwalk=ident), write=False)
    assert r.ok, r.message
    monkeypatch.setattr(factors, "IFPRI_MAPPING", "k_eq_q")
    r2, kq = build_block_module(factors, scratch_layout(tmp_path / "b", xwalk=ident), write=False)
    assert r2.ok, r2.message
    key = ["row", "col", "ref", "component"]
    a = with_x.entries.filter(pl.col("ref") == "F1a").sort(key)
    b = kq.entries.filter(pl.col("ref") == "F1a").sort(key)
    assert a.select(key).equals(b.select(key)) and (a["value"] - b["value"]).abs().max() < 1e-6
    keys = set(with_x.satellites["factor_income_keys"][1]["key"].to_list())
    assert "sensitivity_k_eq_q_lreg" in keys and "sensitivity_xwalk_lreg" not in keys


# =============================================================================================
# 3. the real build
# =============================================================================================


def test_built_outputs_equal_a_fresh_build(real):
    if not PATHS.built("factors"):
        pytest.skip("factors block not built yet (run `uv run python -m pipeline sam factors`)")
    built = pl.read_parquet(PATHS.entries("factors"))
    want = canonical_floats(real.entries, {"value": 6, "tol_rel": None}).sort(list(spec.ENTRY_KEY))
    assert built.drop("block").equals(want)
    cons = pl.read_parquet(PATHS.constraints("factors"))
    assert cons.drop("block").equals(canonical_floats(real.constraints).sort("constraint_id"))
    assert pl.read_parquet(PATHS.provenance("factors")).equals(real.provenance.sort("prov_id"))
    cat = json.loads(PATHS.catalog("factors").read_text(encoding="utf-8"))
    assert cat["refs_not_implemented"] == []
