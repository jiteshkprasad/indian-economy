"""The government block: the official totals it must reproduce (recomputed here from data/clean with polars,
never typed in), the plan's section 7 tests, and the contract (roles, statuses, structure, provenance).

Two layers:
- `result` assembles the block in memory. With every dependency built it uses the real dependency outputs;
  otherwise (a dependency not built yet) it uses a synthetic `Deps` fixture (production's real GFCE targets and P9
  entry; synthetic keys), so everything that does not depend on another block's numbers is tested now.
- the built-output tests (fresh build equals the files, checks pass) need `sam government`; they skip, saying
  so, while a dependency is missing.
"""

from __future__ import annotations

import polars as pl
import pytest

from pipeline.core.io import canonical_floats
from pipeline.core.paths import Layout
from pipeline.sam import spec
from pipeline.sam.accounts import Accounts
from pipeline.sam.blocks import government
from pipeline.sam.blocks.government.core import (
    HH,
    Evidence,
    Q,
    choose_variant,
    gdi_evidence,
    paired_saving,
    r9b_formula,
    ras,
    shares,
)
from pipeline.sam.blocks.government.deps import Deps, read_deps
from pipeline.sam.blocks.government.parts import R9B_VARIANTS_ALLOWED, assemble
from pipeline.sam.framework import BlockContext, SamError, SamPaths, build_block_module, validate_result

pytestmark = pytest.mark.sam

LAYOUT = Layout.default()
PATHS = SamPaths(LAYOUT)
YEAR = spec.YEAR
DEPS_BUILT = all(PATHS.built(d) for d in government.DEPENDS)
UNIT = {"union_fiscal": "union_fiscal", "state_fiscal": "state_fiscal", "mospi": "mospi_nas_2026",
        "external": "external_sector", "finsector": "finsector_markets", "rbi": "rbi_banking_corporate",
        "io": "io_tables"}  # fmt: skip


# ---------------------------------------------------------------------------------------------
# clean-data helpers (independent of the block's code)
# ---------------------------------------------------------------------------------------------


def _clean(dataset: str) -> pl.DataFrame:
    unit = next(u for p, u in UNIT.items() if dataset.startswith(p))
    df = pl.read_parquet(LAYOUT.clean / unit / f"{dataset}.parquet").filter(pl.col("period") == YEAR)
    return df.filter(pl.col("vintage") == df["vintage"].max())


def _v(dataset: str, sid: str) -> float:
    df = _clean(dataset).filter(pl.col("series_id") == sid)
    assert df.height == 1, (dataset, sid, df.height)
    return float(df["value"][0])


def _sf(code: str) -> float:
    return _v("state_fiscal_rbi_sf_appendices", f"{code}.in.all_states_uts.actuals")


FA_R, FA_E = "union_fiscal_fa_receipts", "union_fiscal_fa_expenditure"
GIA, AFS = "union_fiscal_fa_gia", "union_fiscal_afs"


def _sum(e: pl.DataFrame, **flt: str | list[str]) -> float:
    for k, v in flt.items():
        e = e.filter(pl.col(k).is_in(v if isinstance(v, list) else [v]))
    return float(e["value"].sum())


# ---------------------------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------------------------


def _synthetic_deps() -> Deps:
    pc = pl.read_parquet(PATHS.constraints("production"))
    pe = pl.read_parquet(PATHS.entries("production"))
    g = pc.filter(pl.col("constraint_id").str.starts_with("gfce.") & (pl.col("target") != 0))
    gfce = {r["constraint_id"].split(".")[1].upper(): Q(r["target"], frozenset({r["prov_id"]}))
            for r in g.iter_rows(named=True)}  # fmt: skip
    p9 = pe.filter((pl.col("ref") == "P9") & (pl.col("col") == "C_RPET"))
    lv = [3.0, 4.0, 5.0, 6.0, 8.0, 4.0, 5.0, 6.0, 8.0, 12.0]
    return Deps(
        gfce=gfce, p9_rpet=Q(p9["value"][0], frozenset({p9["prov_id"][0]})),
        f4b={"G_CEN": Q(111_000.0), "G_STA": Q(264_679.16)},
        public_wage_key={h: Q(v) for h, v in zip(HH, lv, strict=True)},
        mi_nonfarm={h: Q(v) for h, v in zip(HH, reversed(lv), strict=True)},
        mi_farm={h: Q(v if h.startswith("H_R") else 0.5) for h, v in zip(HH, lv, strict=True)},
        pop={h: Q(10.0 if h.startswith("H_R") else 8.0) for h in HH},
        income_taxes={"G_CEN": Q(1_950_000.0), "G_STA": Q(7_900.0)},
        outside_nva={"G_CEN": Q(51_000.0), "G_STA": Q(320_000.0)},
    )  # fmt: skip


@pytest.fixture(scope="module")
def built_production() -> None:
    if not PATHS.built("production"):
        pytest.fail("production block not built: run `uv run python -m pipeline sam production`")


@pytest.fixture(scope="module")
def run(built_production):
    """(ctx, deps, validated result) of an in-memory assembly."""
    if DEPS_BUILT:
        ctx = BlockContext(block="government", refs=tuple(government.REFS), depends=tuple(government.DEPENDS),
                           layout=LAYOUT)  # fmt: skip
        deps = read_deps(ctx)
    else:
        ctx = BlockContext(block="government", refs=tuple(government.REFS), depends=("production",), layout=LAYOUT)
        deps = _synthetic_deps()
    valid = validate_result(ctx, assemble(ctx, deps))
    return ctx, deps, valid


@pytest.fixture(scope="module")
def ent(run) -> pl.DataFrame:
    return run[2].entries


@pytest.fixture(scope="module")
def cons(run) -> pl.DataFrame:
    return run[2].constraints


# ---------------------------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------------------------


def test_ras_hits_both_margins_and_keeps_zeros():
    seed = {("a", "x"): 1.0, ("a", "y"): 2.0, ("b", "x"): 3.0, ("b", "y"): 0.0}
    out = ras(seed, {"a": 10.0, "b": 5.0}, {"x": 8.0, "y": 7.0})
    assert abs(out[("a", "x")] + out[("a", "y")] - 10.0) < 1e-7
    assert abs(out[("a", "x")] + out[("b", "x")] - 8.0) < 1e-7
    assert out[("b", "y")] == 0.0
    with pytest.raises(SamError):
        ras(seed, {"a": 10.0, "b": 5.0}, {"x": 8.0, "y": 8.0})


def test_r9b_formula_uses_k_years_since_2005_06():
    f = r9b_formula(390.0, 100.0, "2023-24")
    assert f["k"] == 18 and abs(f["factor"] - 21 / 39) < 1e-12
    assert abs(f["civil"] - 210.0) < 1e-9 and f["defence"] == 100.0


def test_paired_saving_nets_to_the_prior_and_keeps_signs():
    for net, m in ((-355_000.0, 100_000.0), (36_000.0, 106_000.0), (0.0, 5.0)):
        pos, neg = paired_saving(net, m)
        assert pos > 0 > neg and abs(pos + neg - net) < 1e-9


def test_choose_variant_takes_the_allowed_variant_with_the_smaller_gap():
    ev = gdi_evidence(property_received=10.0, property_paid=5.0, income_taxes=20.0, benefits_paid=10.0,
                      other_transfers_paid=1.0, required=12.0, variants={"none": 0.0, "a": 3.0, "b": 9.0})  # fmt: skip
    assert [e.gap for e in ev] == [2.0, 5.0, 11.0]
    assert choose_variant(ev, ["a", "b"]).variant == "a"
    assert choose_variant(ev, ["none", "a", "b"]).variant == "none"  # D2-20: 'none' is allowed and can win
    assert choose_variant([Evidence("a", 1, 11, 10), Evidence("b", 1, 9, 10)], ["b", "a"]).variant == "b"


def test_shares_reject_negative_keys():
    assert shares({"a": 1.0, "b": 3.0}, "k") == {"a": 0.25, "b": 0.75}
    with pytest.raises(SamError):
        shares({"a": -1.0, "b": 3.0}, "k")


# ---------------------------------------------------------------------------------------------
# contract, roles and structure
# ---------------------------------------------------------------------------------------------


def test_entries_respect_structure_refs_and_roles(ent):
    acc = Accounts.load()
    assert all(acc.allowed_cell(r, c) for r, c in ent.select("row", "col").iter_rows())
    assert set(ent["ref"]) <= set(government.REFS)
    assert not ent.filter(pl.col("ref").is_in(["R9", "K3"])).height  # constraint-only refs (XR-11)
    fixed = ent.filter(pl.col("role") == "fixed")
    assert set(fixed["ref"]) == {"C2a", "R1", "R2", "T2b", "R6", "R7", "K6", "K8e"}
    assert fixed.filter(pl.col("ref") == "C2a")["col"].to_list() == ["G_CEN"]  # only the grain cell
    assert ent.filter((pl.col("role") == "free") & pl.col("confidence").is_null()).height == 0
    assert ent.filter(pl.col("value") == 0).height == 0


def test_no_r15_r16_and_no_double_counted_transfer(ent):
    """Plan s.7 test 16: no R15/R16; no R10/R18 component named after MISS or food; R6 not in R7. PM-KISAN is R10
    `pm_kisan` (G_CEN -> households, = Finance Accounts 2401.00.130) since government-30 / audit BS-5 (2026-10-01),
    and taxes no longer books it in P10a (its classification says so), so it is counted once."""
    assert ent.filter(pl.col("ref").is_in(["R15", "R16"])).height == 0
    comps = ent.filter(pl.col("ref").is_in(["R10", "R18"]))["component"].to_list()
    assert not [c for c in comps if any(w in c for w in ("miss", "food", "interest_subvention"))]
    kisan = ent.filter(pl.col("component").str.contains("kisan"))
    assert set(kisan["ref"]) == {"R10"} and set(kisan["col"]) == {"G_CEN"} and set(kisan["component"]) == {"pm_kisan"}
    assert abs(float(kisan["value"].sum()) - _v(FA_E, "fa9.2401.00.130")) <= 0.01
    if PATHS.built("taxes"):
        cls = pl.read_parquet(PATHS.satellites("taxes") / "tax_classification.parquet")
        assert cls.filter(pl.col("item") == "pm_kisan")["ref"].to_list() == ["none"]
        p10 = pl.read_parquet(PATHS.satellites("taxes") / "p10a_items.parquet")
        assert p10.filter(pl.col("item") == "pm_kisan").height == 0
    assert ent.filter((pl.col("ref") == "R7") & (pl.col("col") == "E_RBI")).height == 0


# ---------------------------------------------------------------------------------------------
# C2a (plan s.7 tests 1-2)
# ---------------------------------------------------------------------------------------------


def test_c2a_reproduces_sut_gfce_by_commodity_and_nas(ent, run):
    use = _clean("io_tables_sut_use").filter(pl.col("item_code") == "gfce")
    conc = pl.read_csv(LAYOUT.concordance / "io_tables_sut_product_to_sam34.csv", infer_schema=False).select(
        ("sut_p" + pl.col("sut_product").str.zfill(3)).alias("product"), "commodity")  # fmt: skip
    sut = use.join(conc, on="product", how="inner").group_by("commodity").agg(pl.col("value").sum())
    c2a = ent.filter(pl.col("ref") == "C2a").group_by("row").agg(pl.col("value").sum())
    got = dict(c2a.iter_rows())
    for c, v in sut.filter(pl.col("value") != 0).iter_rows():
        assert abs(got.get(c, 0.0) - v) <= 0.5, c
    assert set(got) == set(sut.filter(pl.col("value") != 0)["commodity"])
    grain = _sum(use, product=["sut_p001", "sut_p002"])
    assert abs(_sum(ent, ref="C2a", row="C_CROP", col="G_CEN") - grain) < 1e-6
    assert ent.filter((pl.col("row") == "C_CROP") & (pl.col("col") == "G_STA")).height == 0
    nas = _v("mospi_nas_2026_s1_14", "s1_14.gg.final_consumption_expenditure.current")
    assert abs(_sum(ent, ref="C2a") - nas) <= 1.0
    # s.7 test 2: the Centre's own-output GFCE follows the F4b key (institutional, D2-8)
    deps = run[1]
    own = ["C_PADM", "C_EDUC", "C_HLTH", "C_CNST", "C_UTIL"]
    share = deps.f4b["G_CEN"].v / (deps.f4b["G_CEN"].v + deps.f4b["G_STA"].v)
    want = share * sum(deps.gfce[c].v for c in own)
    assert abs(_sum(ent, ref="C2a", row=own, col="G_CEN") - want) <= 1.0


def test_c2a_seeds_count_each_cash_line_once(run):
    """V-GOV-2: public works are inside the administrative-services aggregates (Union FA section = MH 2051-2070,
    RBI SF App. II ii.d = items i-v) and are seeded in CNST, so the PADM seeds exclude them."""
    app2 = "app2.total_expenditure."
    fe = _clean(FA_E)
    mh = fe.filter(pl.col("series_id").str.contains(r"^fa9\.20(5\d|6\d|70)\.total$"))["value"].sum()
    assert abs(mh - _v(FA_E, "fa9.section.administrative_services")) <= 0.05  # 2059 is inside the section
    items = ("i-secretariat_general_services", "ii-district_administration", "iii-police", "iv-public_works",
             "v-others")  # fmt: skip
    parts = [_sf(f"{app2}ii.d.{i}") for i in items]
    assert abs(sum(parts) - _sf(f"{app2}ii.d-administrative_services")) <= 0.05  # ii.d.iv is inside ii.d
    sat = dict(run[2].satellites["gov_c2a_keys"][1].select("series_id", "value").iter_rows())
    secs = ("organs_of_state", "fiscal_services", "administrative_services", "defence_services")
    sections = sum(_v(FA_E, f"fa9.section.{s}") for s in secs)
    works_c, works_s = _v(FA_E, "fa9.2059.total"), _sf(f"{app2}ii.d.iv-public_works")
    assert abs(sat["seed.c_padm.g_cen"] - (sections - works_c)) <= 0.01
    assert abs(sat["seed.c_cnst.g_cen"] - (_v(FA_E, "fa9.3054.total") + works_c)) <= 0.01
    padm = ("ii.a-organs_of_state", "ii.b-fiscal_services", "ii.d-administrative_services",
            "ii.f-miscellaneous_general_services")  # fmt: skip
    lotteries = _sf(f"{app2}ii.f.payment_on_account_of_state_lo-payment_on_account_of_state_lotteries")
    padm_s = sum(_sf(app2 + c) for c in padm) - lotteries - works_s
    assert abs(sat["seed.c_padm.g_sta"] - padm_s) <= 0.01
    assert abs(sat["seed.c_cnst.g_sta"] - (_sf(f"{app2}i.b.7.i-roads_and_bridges") + works_s)) <= 0.01


# ---------------------------------------------------------------------------------------------
# Centre -> States (plan s.7 tests 3-6, 13)
# ---------------------------------------------------------------------------------------------


def test_r1_devolution_equals_the_union_901_lines(ent):
    fa = _clean(FA_R).filter(pl.col("series_id").str.contains(r"^fa8\.00\d\d\.\d\d\.901$"))
    want = -float(fa["value"].sum())
    assert abs(_sum(ent, ref="R1") - want) <= 0.01
    assert abs(want - _v(AFS, "afs.cfi_rev_receipts.state_s_share_excluded_from_the_consolidated_fund")) <= 0.01
    for other in (
        _sf("app1.total_revenue.i.b-share_in_central_taxes"),
        _v("state_fiscal_fc16_kfi", "kfi.a_1_3-state_s_share_in_union_taxes_and_duties.in.all_states_28"),
    ):
        assert abs(want / other - 1) <= 5e-4  # fmt: skip


def _net_releases(mh: str) -> float:
    fa = _clean(FA_E).filter(pl.col("series_id").str.starts_with(f"fa9.{mh}."))
    leaf = fa.filter(~pl.col("series_id").str.ends_with(".total"))
    t797 = leaf.filter(pl.col("series_id").str.ends_with(".797"))["value"].sum()
    met = leaf.filter(pl.col("item_label").str.to_lowercase().str.contains("met from"))["value"].sum()
    total = fa.filter(pl.col("series_id") == f"fa9.{mh}.total")["value"][0]
    assert abs(leaf["value"].sum() - total) <= 0.05  # the leaf lines add up to the head total
    return total - t797 - met


def test_h9_grants_bridge():
    """Plan s.7 test 4: net releases (3601 + 3602) vs RBI SF within 0.1%; IGAS-2 State + FC local-body/health grants
    vs MH 3601 net releases within 0.1%."""
    sfg = _sf("app1.total_revenue.ii.d-grants_from_the_centre")
    n3601, n3602 = _net_releases("3601"), _net_releases("3602")
    assert abs((n3601 + n3602) / sfg - 1) <= 1e-3
    igas = _v(GIA, "gia.cash.state_governments.total") + _v(GIA, "gia.in_kind.state_governments.total")
    fcl = sum(_v(FA_E, f"fa9.3601.07.{m}") for m in ("102", "103", "106"))
    assert abs((igas + fcl) / n3601 - 1) <= 1e-3


def test_r2_t2b_r2k_equal_state_treasury_receipts(ent):
    sfg = _sf("app1.total_revenue.ii.d-grants_from_the_centre")
    treas = (_sum(ent, ref="R2", component=["fc_grants", "css_and_other"]) + _sum(ent, ref="T2b",
             component="compensation_grants") + _sum(ent, ref="R2k", component="igas2_capital"))  # fmt: skip
    assert abs(treas / sfg - 1) <= 5e-3
    r2k = _v(GIA, "gia.cash.state_governments.capital_assets") + _v(GIA, "gia.cash.ut_governments.capital_assets")
    assert abs(_sum(ent, ref="R2k", component="igas2_capital") - r2k) < 1e-6
    assert abs(_sum(ent, ref="R2", component="fc_grants")
               - _sf("app1.total_revenue.ii.d.5-finance_commission_grants")) < 1e-6  # fmt: skip
    # D2-8: the outside-treasury CSS = St 18 CSS revenue - MH 3601.06 net releases, current + capital
    st18 = _v(
        "union_fiscal_exp_profile",
        "stat18.transfers_to_states_other_than_i_ii.under_centrally_sponsored_schemes_revenue",
    )
    out = _sum(ent, component="css_outside_treasury")
    assert abs(out - (st18 - _net_releases("3601.06"))) <= 0.01
    # the reserve-fund transfers (minor head 797) never reach the R2 entries
    assert _sum(ent, ref="R2") < _v(FA_E, "fa9.3601.total") + _v(FA_E, "fa9.3602.total") - 1.0


def test_t2b_uses_of_the_cess_and_k8e(ent):
    fund_out = _v(AFS, "afs.pa_disbursements.xi_goods_and_service_tax_compensation_fund")
    b2b = fund_out + _v(FA_E, "fa9.3601.08.904") + _v(FA_E, "fa9.3602.08.904")
    assert abs(_sum(ent, ref="T2b", component="cess_loan_recovery") - b2b) <= 0.01
    comp = _v(FA_E, "fa9.3601.08.112") + _v(FA_E, "fa9.3602.08.106")
    assert abs(_sum(ent, ref="T2b", component="compensation_grants") - comp) <= 0.01
    assert _sum(ent, ref="T2b") <= _v(AFS, "afs.pa_receipts.xi_goods_and_service_tax_compensation_fund")
    k8e = ent.filter(pl.col("ref") == "K8e")
    assert k8e.height == 2 and all(abs(v + b2b) <= 0.01 for v in k8e["value"])
    assert set(k8e.select("row", "col").iter_rows()) == {("K_GSTA", "I_LOAN"), ("I_LOAN", "K_GCEN")}


# ---------------------------------------------------------------------------------------------
# property income (plan s.7 tests 7-8; R7x)
# ---------------------------------------------------------------------------------------------


def test_r6_r7_as_published(ent):
    r6 = _v(FA_R, "fa8.0050.00.106")
    assert abs(_sum(ent, ref="R6") - r6) <= 0.01
    timing = _v("rbi_banking_corporate_rbi_surplus_timing", "r6.surplus_received_by_centre_cash.current")
    assert abs(r6 - timing) <= 0.01
    assert abs(_sum(ent, ref="R7", row="G_CEN") - (_v(FA_R, "fa8.0050.total") - r6)) <= 0.01
    assert abs(_sum(ent, ref="R7", row="G_STA") - _sf("app1.total_revenue.ii.c.2-dividends_and_profits")) <= 0.01


def test_r7x_totals_equal_their_cash_lines(ent, cons):
    union = sum(_v(FA_R, f"fa8.{s}") for s in (
        "0049.03.190", "0049.03.103", "0049.03.109", "0049.03.195", "0049.03.118", "0802.00.102", "0802.00.103",
        "0802.00.106", "0802.00.107", "0802.00.109", "1275.00.104", "1275.00.105"))  # fmt: skip
    roy = _clean("state_fiscal_fc16_state_accounts").filter(
        pl.col("series_id").str.starts_with("fa.revenue_receipts.mh0853.in-"))["value"].sum()  # fmt: skip
    itb14 = _v(FA_E, "fa9.2049.01.116")  # States' interest on the Centre's 14-day treasury bills: intra-GG (V-GOV-1)
    states = (_sf("app1.total_revenue.ii.c.1-interest_receipts") - itb14 + roy
              + _sf("app1.total_revenue.ii.c.6.xi-petroleum"))  # fmt: skip
    assert abs(_sum(ent, ref="R7x", row="G_CEN") - union) <= 0.01
    assert abs(_sum(ent, ref="R7x", row="G_STA") - states) <= 0.01
    sta_target = cons.filter(pl.col("constraint_id") == "gov.r7x.g_sta")["target"][0]
    assert abs(sta_target - states) <= 0.01
    # spectrum (WPC) receipts are excluded pending NAD; no R7x entry is paid by government or the RoW
    assert ent.filter((pl.col("ref") == "R7x") & pl.col("col").is_in(["G_CEN", "G_STA", "R_ROW"])).height == 0
    c = cons.filter(pl.col("constraint_id").str.starts_with("gov.r7x."))
    assert set(c["kind"]) == {"band"}
    # the two government totals, one band per published line (+-5%) and one per payer sector of a multi-payer line
    # (+-25%): government-32, audit 2026-10-01
    assert {"gov.r7x.g_cen", "gov.r7x.g_sta"} <= set(c["constraint_id"])
    lines = c.filter(pl.col("constraint_id").str.count_matches(r"\.") == 3)
    assert lines.height == ent.filter(pl.col("ref") == "R7x").select("row", "component").unique().height
    for r in lines.iter_rows(named=True):
        gov, comp = r["rows"], r["components"]
        assert abs(r["target"] - _sum(ent, ref="R7x", row=gov, component=comp)) <= 0.01 and r["tol_rel"] == 0.05
    for r in c.filter(pl.col("constraint_id").str.count_matches(r"\.") == 4).iter_rows(named=True):
        assert r["tol_rel"] == 0.25


def test_itb_interest_is_intra_gg_not_r7x(ent):
    """V-GOV-1: the States' interest on the Centre's 14-day treasury bills (Union MH 2049.01.116, paid only to
    State governments) is intra-GG (fincorp R3 itb_14d), so R7x interest_states is App. I ii.c.1 without it."""
    ii_c_1 = _sf("app1.total_revenue.ii.c.1-interest_receipts")
    itb14 = _v(FA_E, "fa9.2049.01.116")
    assert itb14 > 0
    got = _sum(ent, ref="R7x", row="G_STA", col="E_NFPU", component="interest_states")
    assert abs(got - (ii_c_1 - itb14)) <= 0.01
    if PATHS.built("fincorp"):  # the intra-GG part is booked once, by fincorp
        fe = pl.read_parquet(PATHS.entries("fincorp"))
        itb = _sum(fe, ref="R3", row="G_STA", col="G_CEN", component="itb_14d")
        assert got + itb <= ii_c_1 + 0.01


def test_r7_payer_split_on_mixed_heads_is_derived(ent):
    """V-GOV-6: R7 on a mixed minor head (Union 101 public undertakings + 200, States' dividends) puts a published
    total on one payer by assumption, so it is `derived`; heads that name the payer (banks, LIC) are `official`."""
    r7 = {(r["row"], r["col"], r["component"]): (r["status"], r["role"])
          for r in ent.filter(pl.col("ref") == "R7").iter_rows(named=True)}  # fmt: skip
    assert r7[("G_CEN", "E_NFPU", "public_undertakings")] == ("derived", "fixed")
    assert r7[("G_STA", "E_NFPU", "state_enterprises")] == ("derived", "fixed")
    assert r7[("G_CEN", "E_BANK", "banks")] == ("official", "fixed")
    assert r7[("G_CEN", "E_INSP", "lic")] == ("official", "fixed")


# ---------------------------------------------------------------------------------------------
# pensions (plan s.7 tests 9-10; R9d)
# ---------------------------------------------------------------------------------------------


def test_r9a_pension_totals(ent, cons):
    cen = (_v(FA_E, "fa9.2071.total") - _v(FA_E, "fa9.2071.01.117") - _v(FA_E, "fa9.2071.01.902")
           - _v(FA_E, "fa9.2071.01.118"))  # fmt: skip
    sta = _sf("app2.total_expenditure.ii.e-pensions") - _v(
        "finsector_markets_pfrda_sg", "m7d.annual_contribution_employer.state_govt.current"
    )
    assert abs(_sum(ent, ref="R9a", col="G_CEN") - cen) <= 0.01
    assert abs(_sum(ent, ref="R9a", col="G_STA") - sta) <= 0.01
    for cid, want, tol in (("gov.r9.centre", cen, 0.02), ("gov.r9.states", sta, 0.03)):
        c = cons.filter(pl.col("constraint_id") == cid)
        assert c.height == 1 and abs(c["target"][0] - want) <= 0.01 and c["tol_rel"][0] == tol
        assert c["refs"][0] == "R9a"


def test_r9b_formula_and_variant(ent, run):
    civil = (_v(FA_E, "fa9.2071.01.total") - _v(FA_E, "fa9.2071.01.117") - _v(FA_E, "fa9.2071.01.902")
             - _v(FA_E, "fa9.2071.01.118"))  # fmt: skip
    centre = civil * 21 / 39 + _v(FA_E, "fa9.2071.02.total")
    sat = run[2].satellites["gov_r9b_sensitivity"][1]
    sv = dict(sat.select("series_id", "value").iter_rows())
    assert abs(sv["variant.centre_only.r9b"] - centre) <= 1.0
    chosen = sat.filter(pl.col("series_id") == "chosen")["variant"][0]
    assert set(R9B_VARIANTS_ALLOWED) == {"none", "centre_only", "centre_and_states"}  # D2-5 as amended by D2-20
    gaps = {r["variant"]: abs(r["value"]) for r in sat.filter(pl.col("item") == "gap_vs_nas").iter_rows(named=True)}
    assert gaps[chosen] == min(gaps[v] for v in R9B_VARIANTS_ALLOWED)
    written = {"none": 0.0, "centre_only": centre, "centre_and_states": sv["variant.centre_and_states.r9b"]}[chosen]
    assert abs(_sum(ent, ref="R9b") - written) <= 1.0
    if chosen != "centre_and_states":
        assert ent.filter((pl.col("ref") == "R9b") & (pl.col("row") == "G_STA")).height == 0
    # D2-20 memo: the unwritten non-zero variants stay in the satellite
    assert abs(sv["memo.centre_only.g_cen"] - centre) <= 1.0
    assert abs(sv["memo.centre_and_states.g_cen"] + sv["memo.centre_and_states.g_sta"]
               - sv["variant.centre_and_states.r9b"]) <= 1e-6  # fmt: skip
    for gov in ("G_CEN", "G_STA"):  # R9b <= R9 for each government
        assert _sum(ent, ref="R9b", row=gov) <= _sum(ent, ref="R9a", col=gov) + 1e-6
    req = sat.filter(pl.col("series_id") == "nas.required_net_distributive")["value"][0]
    want = (_v("mospi_nas_2026_s1_14", "s1_14.gg.gross_disposable_income.current")
            - _v("mospi_nas_2026_s1_14", "s1_14.gg.consumption_of_fixed_capital.current")
            - _v("mospi_nas_2026_s1_1", "s1_1.taxes_on_products.current")
            + _v("mospi_nas_2026_s1_1", "s1_1.subsidies_on_products.current")
            - _v("mospi_nas_2026_s7_1", "s7_1.total.net_production_taxes.current"))  # fmt: skip
    assert abs(req - want) <= 1e-3


def test_r9b_is_none_on_the_real_evidence(ent, run):
    """D2-20: on the real prior the evidence favours no R9b, so no R9b entry is written."""
    if not DEPS_BUILT:
        pytest.skip("synthetic dependencies: the evidence ranking needs taxes' real income-tax entries")
    sat = run[2].satellites["gov_r9b_sensitivity"][1]
    assert sat.filter(pl.col("series_id") == "chosen")["variant"][0] == "none"
    assert ent.filter(pl.col("ref") == "R9b").height == 0


def test_r9d_departmental_pensions(ent):
    assert abs(_sum(ent, ref="R9d", component="railways") - _v(AFS, "afs.pa_disbursements.i_railway_funds")) <= 0.01
    posts = _v(FA_E, "fa9.3201.07.total") - _v(FA_E, "fa9.3201.07.110")
    assert abs(_sum(ent, ref="R9d", component="posts") - posts) <= 0.01
    assert set(ent.filter(pl.col("ref") == "R9d")["col"]) == {"E_NFPU"}


# ---------------------------------------------------------------------------------------------
# saving and capital (plan s.7 tests 11-12)
# ---------------------------------------------------------------------------------------------


def test_k3a_priors_add_to_nas_saving_and_are_paired(ent, run):
    k3 = _v("mospi_nas_2026_s1_9", "s1_9.general_government.current")
    assert abs(_sum(ent, ref="K3a") - k3) <= 0.5
    for kacct, gov in (("K_GCEN", "G_CEN"), ("K_GSTA", "G_STA")):
        k = ent.filter((pl.col("ref") == "K3a") & (pl.col("row") == kacct) & (pl.col("col") == gov))
        comps = dict(k.select("component", "value").iter_rows())
        assert set(comps) == {"saving_pos", "saving_neg"} and comps["saving_pos"] > 0 > comps["saving_neg"]
    br = dict(run[2].satellites["gov_fiscal_bridge"][1].select("series_id", "value").iter_rows())
    for gov, kacct in (("G_CEN", "K_GCEN"), ("G_STA", "K_GSTA")):
        assert abs(br[f"prior.{gov.lower()}"] - _sum(ent, ref="K3a", row=kacct)) <= 1e-3
    assert (
        abs(
            br["centre.revenue_balance"]
            + _v(AFS, "afs.cfi_rev_receipts.excess_of_disbursements_over_receipts_revenue_deficit")
        )
        < 1e-6
    )
    assert abs(br["states.revenue_balance"] - _sf("app4.a-surplus_deficit_on_revenue_account")) < 1e-6


def test_k3a_bridge_has_no_cfc_step_and_adds_the_ulb_surplus(run):
    """Repaired bridge (2026-10-01; government-2, -25, V-GOV-3): gross saving needs no CFC step; departmental
    enterprises leave the Centre; the urban local bodies' revenue surplus is the States'; the remainder is split by
    the NVA of the GG units outside the treasury accounts."""
    ctx, deps, valid = run
    br = dict(valid.satellites["gov_fiscal_bridge"][1].select("series_id", "value").iter_rows())
    ulb = "state_fiscal_ulb_cityfinance"
    de_rec = sum(_v("union_fiscal_fa_receipts", f"fa8.{m}.total") for m in ("1001", "1002", "1003", "1201"))
    de_exp = sum(_v(FA_E, f"fa9.{m}.total") for m in ("3001", "3002", "3003", "3006", "3201"))  # MH 3006: V-GOV-11
    assert abs(br["centre.less_departmental_enterprises_net"] + de_rec - de_exp) <= 0.01
    surplus = (_v(ulb, "ulb.total_revenues.in.all_ulbs_in_dump")
               - _v(ulb, "ulb.total_revenue_expenditure.in.all_ulbs_in_dump")
               - _v(GIA, "gia.cash.urban_local_bodies.capital_assets"))  # fmt: skip
    assert abs(br["states.ulb_revenue_surplus"] - surplus) <= 0.01
    k3 = _v("mospi_nas_2026_s1_9", "s1_9.general_government.current")
    # no CFC in the bridge: the remainder is NAS saving less the two subtotals
    assert abs(br["unexplained_remainder"] - (k3 - br["centre.subtotal"] - br["states.subtotal"])) <= 1e-6
    assert abs(br["states.subtotal"] - br["states.treasury_subtotal"] - surplus) <= 0.01
    w = deps.outside_nva["G_CEN"].v / (deps.outside_nva["G_CEN"].v + deps.outside_nva["G_STA"].v)
    assert abs(br["remainder_share_centre"] - w) <= 1e-12
    assert abs(br["prior.g_cen"] - br["centre.subtotal"] - w * br["unexplained_remainder"]) <= 1e-6
    # the plan's bridge (CFC added, remainder by revenue expenditure) is kept as a sensitivity
    cfc = deps.f4b["G_CEN"].v + deps.f4b["G_STA"].v
    plan = br["sensitivity.plan_cfc_revexp.g_cen"] + br["sensitivity.plan_cfc_revexp.g_sta"]
    assert abs(plan - k3) <= 1e-6 and abs(br["memo.cfc_f4b_g_cen"] + br["memo.cfc_f4b_g_sta"] - cfc) <= 1e-6


def test_k6_row_on_the_nas_basis_and_cofog_total(ent):
    s61 = "mospi_nas_2026_s6_1"
    gg = _v(s61, "s6_1.capital_transfers_to_general_government_from_the_rest_of_the.current")
    row = ent.filter((pl.col("ref") == "K6") & ((pl.col("row") == "K_ROW") | (pl.col("col") == "K_ROW")))
    rec = _sum(row, row="K_GCEN")
    pay = _sum(row, row="K_ROW", col="K_GCEN")
    assert abs(rec - pay - gg) <= 0.01
    assert abs(pay - _v("external_sector_invisibles_annual", "invis.inr.official_transfers.payments.current")) < 1e-6
    net = _sum(row.filter(pl.col("col") == "K_ROW")) - _sum(row.filter(pl.col("row") == "K_ROW"))
    want = (gg + _v(s61, "s6_1.capital_transfers_to_corporations_households_and_npishs_net.current")
            - _v(s61, "s6_1.acquisitions_less_disposal_of_non_produced_non_financial_ass.current"))  # fmt: skip
    assert abs(net - want) <= 1.0
    assert set(row["role"]) == {"fixed"} and set(row["bop_function"]) == {"other"}
    paid = _sum(ent.filter((pl.col("ref") == "K6") & pl.col("col").is_in(["K_GCEN", "K_GSTA"])))
    cofog = _v("mospi_nas_2026_s4_2", "s4_2.capital_transfer.total.current")
    assert abs(paid / cofog - 1) <= 0.05
    assert _sum(ent, ref="K6", row="K_HH", col=["K_GCEN", "K_GSTA"]) > 0  # D2-6: capital transfers to households
    # V-GOV-7 / A-K6-4: statutory bodies are GG (their revenue grants are not R18 either), so the Centre's K6 to
    # K_NFPU is the IGAS-2 PSU capital grants only
    psu = _v(GIA, "gia.cash.public_sector_undertakings.capital_assets")
    assert abs(_sum(ent, ref="K6", row="K_NFPU", col="K_GCEN") - psu) <= 0.01
    assert ent.filter((pl.col("ref") == "K6") & pl.col("component").str.contains("statutory")).height == 0
    assert not [c for c in ent.filter(pl.col("ref") == "R18")["component"].to_list() if "statutory" in c]


def test_constraints_declared(cons):
    ids = set(cons["constraint_id"])
    assert {"gov.c2.total", "gov.c2a.centre_own_output", "gov.k3.gg_saving", "gov.grants.state_receipts",
            "gov.r1.devolution", "gov.t2b.cess_uses", "gov.r7.union", "gov.r9.centre", "gov.r9.states",
            "gov.cofog.capital_transfers", "gov.r7x.g_cen", "gov.r7x.g_sta"} <= ids  # fmt: skip
    g = cons.filter(pl.col("constraint_id") == "gov.grants.state_receipts")
    assert "cess_loan_recovery" not in g["components"][0] and "css_outside_treasury" not in g["components"][0]
    assert not any(i.startswith("gfce.") for i in ids)  # production's per-commodity targets are not re-declared


def test_satellites_present(run):
    assert set(run[2].satellites) == {
        "gov_c2a_keys",
        "gov_grants_bridge",
        "gov_r7x_items",
        "gov_transfer_classification",
        "gov_fiscal_bridge",
        "gov_r9b_sensitivity",
    }
    cls = run[2].satellites["gov_transfer_classification"][1]
    assert cls["series_id"].n_unique() == cls.height
    # V-GOV-8: one row per source line; the LIC pension subsidy (a St 7 line) appears once, with destination R18
    lic = cls.filter(pl.col("item").str.contains("_lic_"))
    assert lic.height == 1 and lic["destination"][0] == "R18" and lic["account"][0] == "E_INSP"
    assert cls["item"].n_unique() == cls.height
    # V-GOV-7: statutory bodies' revenue and capital grants share one class (intra-GG)
    st = cls.filter(pl.col("series_id").str.starts_with("igas2.statutory_bodies."))
    assert st.height == 2 and set(st["destination"]) == {"none"}


# ---------------------------------------------------------------------------------------------
# built outputs (need every dependency built)
# ---------------------------------------------------------------------------------------------

needs_build = pytest.mark.skipif(
    not DEPS_BUILT,
    reason="a dependency of government is not built yet: integration pending (see docs/phase2/issues/government.md)",
)


@needs_build
def test_built_outputs_equal_a_fresh_build():
    if not PATHS.built("government"):
        pytest.fail("government block not built: run `uv run python -m pipeline sam government`")
    r, valid = build_block_module(government, LAYOUT, write=False)
    assert r.ok, r.message
    built = pl.read_parquet(PATHS.entries("government"))
    want = canonical_floats(valid.entries, {"value": 6, "tol_rel": None}).sort(list(spec.ENTRY_KEY))
    assert built.drop("block").equals(want)
    c = pl.read_parquet(PATHS.constraints("government"))
    assert c.drop("block").equals(canonical_floats(valid.constraints).sort("constraint_id"))


@needs_build
def test_checks_that_must_pass():
    if not PATHS.built("government"):
        pytest.fail("government block not built: run `uv run python -m pipeline sam government`")
    ch = pl.read_parquet(PATHS.checks("government"))
    known = {"cofog_current_transfers"}  # logged finding (issues government-9); gg_gdi_sketch passes with R9b none
    failed = ch.filter(~pl.col("ok") & ~pl.col("check_id").is_in(list(known)))
    assert failed.height == 0, failed
