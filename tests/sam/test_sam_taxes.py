"""The taxes block: pure-function tests on small fixtures (always run), and tests of the built outputs against
the official totals they must reproduce. Every expected value is recomputed here from data/clean (polars),
never typed in; the plan's s.7 tests are numbered in the docstrings."""

from __future__ import annotations

import polars as pl
import pytest

from pipeline.core.io import canonical_floats
from pipeline.core.paths import Layout
from pipeline.sam import spec
from pipeline.sam.blocks import taxes
from pipeline.sam.blocks.taxes import direct, p7a
from pipeline.sam.framework import SamError, SamPaths, build_block_module

pytestmark = pytest.mark.sam

LAYOUT = Layout.default()
PATHS = SamPaths(LAYOUT)
YEAR = spec.YEAR
PRODUCT_TAX = p7a.PRODUCT_TAX_ACCOUNTS
HH = ("H_R1", "H_R2", "H_R3", "H_R4", "H_R5", "H_U1", "H_U2", "H_U3", "H_U4", "H_U5")


# ---------------------------------------------------------------------------------------------------
# helpers: clean data, read independently of the block's code
# ---------------------------------------------------------------------------------------------------


def _clean(dataset: str) -> pl.DataFrame:
    unit = next(u for u in ("union_fiscal", "state_fiscal", "io_tables", "mospi_nas_2026", "finsector_markets",
                            "rbi_banking_corporate", "rbi_financial_accounts") if dataset.startswith(u))  # fmt: skip
    return pl.read_parquet(LAYOUT.clean / unit / f"{dataset}.parquet")


def v(dataset: str, sid: str, period: str = YEAR, vintage: str | None = None) -> float:
    d = _clean(dataset).filter((pl.col("series_id") == sid) & (pl.col("period") == period))
    d = d.filter(pl.col("vintage") == (vintage or d["vintage"].max()))
    assert d.height == 1, (dataset, sid, period, d.height)
    return float(d["value"][0])


def vsum(dataset: str, prefix: str, period: str = YEAR) -> float:
    d = _clean(dataset).filter(pl.col("series_id").str.starts_with(prefix) & (pl.col("period") == period))
    d = d.filter(pl.col("vintage") == d["vintage"].max())
    assert d.height > 0, prefix
    return float(d["value"].sum())


def sf(code: str) -> float:
    return v("state_fiscal_rbi_sf_appendices", f"app1.total_revenue.{code}.in.all_states_uts.actuals")


def sut(dataset: str, item: str) -> pl.DataFrame:
    d = _clean(dataset).filter((pl.col("period") == YEAR) & (pl.col("item_code") == item))
    return d.filter(pl.col("vintage") == d["vintage"].max())


# ---------------------------------------------------------------------------------------------------
# pure functions on fixtures (no built blocks needed)
# ---------------------------------------------------------------------------------------------------


def _toy_sut() -> p7a.SutProducts:
    tax = {"sut_p043": 60.0, "sut_p044": 40.0, "sut_p065": 90.0, "sut_p066": 20.0, "sut_p069": 50.0,
           "sut_p085": 1000.0, "sut_p120": 300.0, "sut_p121": 100.0, "sut_p122": 1.0, "sut_p128": 70.0,
           "sut_p132": 80.0, "sut_p134": 60.0, "sut_p136": 30.0, "sut_p142": 20.0, "sut_p149": 10.0,
           "sut_p141": 10.0, "sut_p155": 5.0, "sut_p042": 5.0, "sut_p060": 40.0, "sut_p064": 30.0}  # fmt: skip
    com = {p: "C_" + p[-3:] for p in tax}
    return p7a.SutProducts(
        tax=tax, commodity=com, pfce={"sut_p120": 10.0, "sut_p121": 10.0, "sut_p122": 1.0},
        gfcf={"sut_p120": 10.0}, exports={"sut_p060": 5.0, "sut_p085": 5.0}, imports={"sut_p149": 3.0, "sut_p141": 1.0},
        output={}, prov_ids=[],
    )  # fmt: skip


def _toy_rows() -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    rows = {"T_CGST": 250.0, "T_SGST": 250.0, "T_GCES": 60.0, "T_UEXC": 420.0, "T_SVAT": 330.0, "T_SEXC": 110.0,
            "T_OPRT": 200.0}  # fmt: skip
    oprt = {"electricity_duty": 60.0, "vehicle_tax": 100.0, "goods_passengers": 10.0, "entertainment_tax": 2.0,
            "equalisation_levy": 4.0, "export_duty": 4.0, "ctt": 1.0, "other_taxes_duties": 15.0,
            "service_tax_arrears": 4.0}  # fmt: skip
    ppac = {"excise": 300.0, "crude_cess": 90.0, "crude_nccd": 10.0, "cgst": 10.0, "igst": 20.0, "sgst": 10.0,
            "vat": 300.0, "entry_tax": 2.0, "octroi": 3.0}  # fmt: skip
    return rows, oprt, ppac


def test_prior_places_each_head_on_its_base_and_adds_up_to_the_cash_rows():
    s = _toy_sut()
    rows, oprt, ppac = _toy_rows()
    loads = p7a.build_prior(s, rows, oprt, ppac)
    by = {}
    for ld in loads:
        by[(ld.account, ld.item)] = by.get((ld.account, ld.item), 0.0) + ld.value
        assert ld.value > 0
    acct = {a: sum(ld.value for ld in loads if ld.account == a) for a in rows}
    # every non-GST account's prior equals its cash row (GST shares are the SUT residual, not the cash)
    for a in ("T_UEXC", "T_SVAT", "T_SEXC", "T_GCES"):
        assert acct[a] == pytest.approx(rows[a]), a
    # State excise fills alcohol first; the excess is licence fees on hotels and trade only
    assert by[("T_SEXC", "state_excise_alcohol")] == pytest.approx(s.tax["sut_p065"])
    lic = [ld for ld in loads if ld.component == "licence_fee_excess"]
    assert {ld.product for ld in lic} == {"sut_p132", "sut_p134"}
    assert sum(ld.value for ld in lic) == pytest.approx(rows["T_SEXC"] - s.tax["sut_p065"])
    # vehicle tax only on vehicles, pro rata to PFCE + GFCF; export duty only on goods
    veh = {ld.product: ld.value for ld in loads if ld.item == "vehicle_tax"}
    assert veh["sut_p120"] == pytest.approx(100 * 20 / 31)
    assert {ld.product for ld in loads if ld.item == "export_duty"} <= {"sut_p060", "sut_p085"}
    # no GST on products outside GST (except PPAC's own GST on POL); no cess on coal
    for ld in loads:
        if ld.account in ("T_CGST", "T_SGST") and ld.item == "gst":
            assert ld.product not in p7a.NON_GST
        if ld.account == "T_GCES":
            assert ld.product != "sut_p042"


def test_precheck_and_ras_hit_both_margins_and_move_infeasible_rows_minimally():
    cells = pl.DataFrame({"account": ["A", "A", "B"], "component": ["total"] * 3, "commodity": ["X", "Y", "Y"],
                          "value": [1.0, 1.0, 1.0]})  # fmt: skip
    cols = {"X": 30.0, "Y": 70.0}
    # feasible: rows kept
    rows = {"A": 50.0, "B": 50.0}
    assert p7a.precheck(cells, rows, cols) == rows
    x, it, err = p7a.ras(cells, rows, cols)
    assert err < 1e-9 and x.sum() == pytest.approx(100)
    assert x[0] == pytest.approx(30) and x[2] == pytest.approx(50)
    # infeasible: B can only use Y (70) but needs 80; A must take X (30) at least
    rows = {"A": 20.0, "B": 80.0}
    out = p7a.precheck(cells, rows, cols)
    assert out["A"] == pytest.approx(30) and out["B"] == pytest.approx(70)


def test_t3a_key_is_threshold_excess_and_xwalk_rates_are_person_weighted():
    table = pl.DataFrame({"class": ["rural_p00_05", "urban_p95_100"], "group": ["H_R1", "H_U5"],
                          "persons": [100.0, 100.0], "households": [25.0, 25.0],
                          "avg_mpce": [1000.0, 50000.0]})  # fmt: skip
    fr = direct.Fractiles(table, 1.0, dict.fromkeys(direct.HH_GROUPS, 0.0), [], "")
    key = direct.t3a_key(fr, 700_000.0)
    assert key["H_U5"] == 1.0 and key["H_R1"] == 0.0  # 12 x 50,000 x 4 = 24 lakh > 7 lakh; 48,000 < 7 lakh
    with pytest.raises(SamError):
        direct.t3a_key(fr, 1e9)
    xw = pl.DataFrame({"household_group": [*["H_R1"] * 2, *[g for g in direct.HH_GROUPS if g != "H_R1"]],
                       "national_quintile": ["q1", "q2", *["q5"] * 9], "measure": ["persons"] * 11,
                       "value": [3.0, 1.0, *[1.0] * 9]})  # fmt: skip
    r = direct.xwalk_rates(xw, {"q1": 0.1, "q2": 0.3, "q3": 0.0, "q4": 0.0, "q5": 0.5})
    assert r["H_R1"] == pytest.approx(0.15) and r["H_U5"] == pytest.approx(0.5)


def test_fractile_table_needs_24_classes_in_one_group_each():
    rows = [{"hces_class": f"rural_p{i:02d}", "household_group": "H_R1", "measure": m, "value": 1.0}
            for i in range(23) for m in direct.MEASURES]  # fmt: skip
    with pytest.raises(SamError, match="24"):
        direct.fractile_table(pl.DataFrame(rows))


def test_p7b_eligibility_rules():
    assert p7a.eligible("T_CGST", "gst", "C_FOOD", "exports", "exports", 0.0) == 0
    assert p7a.eligible("T_CGST", "gst", "C_FOOD", "A_MACH", "ic", 0.0) == 0
    assert p7a.eligible("T_CGST", "gst", "C_FOOD", "A_HLTH", "ic", 0.0) == 1
    assert p7a.eligible("T_CGST", "gst", "C_CNST", "gfcf", "gfcf", 0.0) == 1
    assert p7a.eligible("T_UEXC", "ppac_excise_pol", "C_RPET", "A_MACH", "ic", 0.0) == 1
    assert p7a.eligible("T_UEXC", "ppac_excise_pol", "C_RPET", "exports", "exports", 0.0) == 0
    assert p7a.eligible("T_OPRT", "export_duty", "C_FOOD", "exports", "exports", 0.0) == 1
    assert p7a.eligible("T_OPRT", "export_duty", "C_FOOD", "pfce", "pfce", 0.0) == 0
    assert p7a.eligible("T_OPRT", "vehicle_tax", "C_TREQ", "A_TRNS", "ic", 0.0) == 0


# ---------------------------------------------------------------------------------------------------
# the built block
# ---------------------------------------------------------------------------------------------------


def _need_built() -> None:
    missing = [d for d in taxes.DEPENDS if not PATHS.built(d)]
    if missing:
        pytest.skip(f"taxes depends on {missing}, not built yet")
    if not PATHS.built("taxes"):
        pytest.fail("taxes block not built: run `uv run python -m pipeline sam taxes`")


@pytest.fixture(scope="module")
def built() -> pl.DataFrame:
    _need_built()
    return pl.read_parquet(PATHS.entries("taxes"))


@pytest.fixture(scope="module")
def cons() -> pl.DataFrame:
    _need_built()
    return pl.read_parquet(PATHS.constraints("taxes"))


@pytest.fixture(scope="module")
def prod() -> pl.DataFrame:
    return pl.read_parquet(PATHS.entries("production"))


def sat(name: str) -> pl.DataFrame:
    return pl.read_parquet(PATHS.satellites("taxes") / f"{name}.parquet")


def s(df: pl.DataFrame, **eq) -> float:
    for k, x in eq.items():
        df = df.filter(pl.col(k).is_in(x if isinstance(x, list | tuple) else [x]))
    return float(df["value"].sum())


@pytest.fixture(scope="module")
def fresh():
    _need_built()
    r, valid = build_block_module(taxes, LAYOUT, write=False)
    assert r.ok, r.message
    return valid


def test_built_outputs_equal_a_fresh_build(built, cons, fresh):
    want = canonical_floats(fresh.entries, {"value": 6, "tol_rel": None}).sort(list(spec.ENTRY_KEY))
    assert built.drop("block").equals(want)
    assert cons.drop("block").equals(canonical_floats(fresh.constraints).sort("constraint_id"))
    assert pl.read_parquet(PATHS.provenance("taxes")).equals(fresh.provenance.sort("prov_id"))


def test_every_control_total_check_passes(fresh):
    failed = fresh.checks.filter(~pl.col("ok"))
    assert failed.height == 0, failed
    assert fresh.checks.height >= 15


def test_p7a_by_commodity_equals_the_sut(built):
    """Plan test 1: per commodity, P7a = SUT product taxes summed over the concordance; total = SUT 'total'."""
    conc = pl.read_csv(LAYOUT.concordance / "io_tables_sut_product_to_sam34.csv", infer_schema=False).select(
        ("sut_p" + pl.col("sut_product").str.zfill(3)).alias("product"), "commodity"
    )
    t = sut("io_tables_sut_supply", "product_taxes")
    by = t.join(conc, on="product", how="inner").group_by("commodity", maintain_order=True).agg(pl.col("value").sum())
    p = built.filter(pl.col("ref") == "P7a").group_by("col", maintain_order=True).agg(pl.col("value").sum())
    got = dict(p.iter_rows())
    for com, want in by.iter_rows():
        assert got.get(com, 0.0) == pytest.approx(want, abs=0.5), com
    total = float(t.filter(pl.col("product") == "total")["value"][0])
    assert s(built, ref="P7a") == pytest.approx(total, abs=1.0)


def test_p7a_structure(built):
    """Plan test 2: no P7a on C_DWEL/C_PADM, none negative, no cess on coal, C_OILG only Union excise
    (the SUT C_OILG product tax equals PPAC cess + NCCD on crude)."""
    p = built.filter(pl.col("ref") == "P7a")
    assert set(p["row"]) <= set(PRODUCT_TAX)
    assert not set(p["col"]) & {"C_DWEL", "C_PADM"}
    assert (p["value"] > 0).all()
    assert p.filter((pl.col("row") == "T_GCES") & (pl.col("col") == "C_COAL")).height == 0
    assert set(p.filter(pl.col("col") == "C_OILG")["row"]) == {"T_UEXC"}
    crude = v("union_fiscal_ppac_exchequer", "ppac.centre.a.cess_on_crude_oil") + v(
        "union_fiscal_ppac_exchequer", "ppac.centre.a.nccd_on_crude_oil"
    )
    assert s(p, col="C_OILG") == pytest.approx(crude, abs=0.01)
    assert set(p.filter(pl.col("component") != "total")["component"]) == {"licence_fee_excess", "non_pol_vat"}
    assert set(p.filter(pl.col("component") == "licence_fee_excess")["col"]) <= {"C_HOTL", "C_TRAD"}
    assert set(p["role"]) == {"free"} and set(p["status"]) == {"estimated"}


def test_state_vat_on_pol_keeps_the_non_pol_residual_apart(built):
    """Verification V-TX-3: on C_RPET, T_SVAT 'total' is PPAC's VAT on POL (high confidence) and the non-petroleum
    VAT residual forced onto POL (plan fallback (b), taxes-3) is its own low-confidence component; both carry the
    cell's one RAS factor, so the cell total is unchanged by the split."""
    p = built.filter((pl.col("ref") == "P7a") & (pl.col("row") == "T_SVAT"))
    conf = {(r["col"], r["component"]): r["confidence"] for r in p.iter_rows(named=True)}
    assert conf[("C_RPET", "total")] == "high" and conf[("C_RPET", "non_pol_vat")] == "low"
    assert all(c == "low" for (_, comp), c in conf.items() if comp == "non_pol_vat")
    ppac = v("union_fiscal_ppac_exchequer", "ppac.states.a.sales_tax_vat_on_pol_products")
    cash = sf("i.a.3.i-sales_tax") + v("union_fiscal_rb_receipts", "rb.tr.0710.sales_tax")
    tot, npv = s(p, col="C_RPET", component="total"), s(p, component="non_pol_vat")
    assert tot / ppac == pytest.approx(npv / (cash - ppac), rel=1e-9)  # one factor for both parts
    assert npv / (tot + npv) == pytest.approx((cash - ppac) / cash, rel=1e-9)  # ~28% of the cell


def test_e_bank_public_private_by_bank_net_profit(built):
    """Verification V-TX-1 (plan s.2.7 step 4): within E_BANK, the deposit-taking NBFC/HFC share moved in (XR-6) is
    private and the rest is split by RBI RTP 2023-24 net profit, public = PSBs + RRBs."""
    rtp, vt = "rbi_banking_corporate_rtp_banks", "2025-12-29"
    grp = {g: v(rtp, f"rtp.scb_pl.net_profit.{g}.current", vintage=vt) for g in ("psb", "pvb", "fb", "sfb", "pb")}
    assert sum(grp.values()) == pytest.approx(v(rtp, "rtp.scb_pl.net_profit.scb.current", vintage=vt), abs=5.0)
    rrb = v(rtp, "rtp.rrb_pl.net_profit.rrb.current", vintage=vt)
    lab = v(rtp, "rtp.lab_pl.net_profit.lab.current", vintage=vt)
    share = (grp["psb"] + rrb) / (sum(grp.values()) + rrb + lab)
    d = dict(sat("direct_tax_split").select("series_id", "value").iter_rows())
    moved = d["t4a.detail.moved_to_e_bank"]
    cit = built.filter((pl.col("row") == "T_CIT") & (pl.col("col") == "E_BANK"))
    pub, pvt = s(cit, component="public"), s(cit, component="private")
    assert pub == pytest.approx((pub + pvt - moved) * share, rel=1e-9)
    assert pvt == pytest.approx((pub + pvt - moved) * (1 - share) + moved, rel=1e-9)
    assert d["t4a.detail.bank_public_share_net_profit"] == pytest.approx(share, abs=1e-9)  # 9 decimals
    # the E_BANK total is still the residual of the FC total (unchanged by the split)
    fc = built.filter((pl.col("row") == "T_CIT") & pl.col("col").is_in(["E_BANK", "E_NBFC", "E_INSP"]))
    assert s(fc) == pytest.approx(d["t4a.detail.e_bank_residual"] + s(fc, col=["E_NBFC", "E_INSP"]), abs=1e-5)


def test_p10a_items_carry_the_status_of_what_they_are(built):
    """Verification V-TX-2: the Union's published subsidy heads are official, differences of published heads are
    derived, the gross_subsidies rows (an estimate) keep the P10a entries' estimated record."""
    it = sat("p10a_items")
    st = {(r["government"], r["item"]): r["status"] for r in it.iter_rows(named=True)}
    assert st[("G_CEN", "fc16_union_business")] == "official"
    # PM-KISAN left P10a (government-30, audit BS-5): it is government's R10, recorded as such in the classification
    assert ("G_CEN", "pm_kisan") not in st
    cls = sat("tax_classification").filter(pl.col("item") == "pm_kisan")
    assert cls["ref"].to_list() == ["none"] and "R10" in cls["sam_cell"][0]
    assert cls["value"][0] == pytest.approx(v("union_fiscal_fa_expenditure", "fa9.2401.00.130"), abs=1e-6)
    assert st[("G_CEN", "interest_subsidies_other")] == st[("G_CEN", "other_subsidies_other")] == "derived"
    assert st[("G_CEN", "gross_subsidies")] == st[("G_STA", "gross_subsidies")] == "estimated"
    assert st[(None, "gross_d39")] == st[(None, "gross_d29")] == "derived"
    prov = dict(pl.read_parquet(PATHS.provenance("taxes")).select("prov_id", "status").iter_rows())
    assert all(prov[r["prov_id"]] == r["status"] for r in it.iter_rows(named=True))


def test_customs(built, prod):
    """Plan test 3: G_CEN <- T_CUST = SUT import duty = Sum production P8, and within 1% of cash less export duty."""
    c = s(built, row="G_CEN", col="T_CUST")
    assert c == pytest.approx(float(sut("io_tables_sut_supply", "import_duty").filter(
        pl.col("product") == "total")["value"][0]), abs=1.0)  # fmt: skip
    assert c == pytest.approx(s(prod, ref="P8"), abs=1e-5)
    rb = "union_fiscal_rb_receipts"
    cash = v(rb, "rb.tr.total.total_customs") - v(rb, "rb.tr.0037.export_duty") - v(rb, "rb.tr.0037.cesses_on_exports")
    assert abs(c / cash - 1) < 0.01
    assert built.filter(pl.col("col") == "T_CUST")["role"].to_list() == ["fixed"]


def test_net_product_taxes_and_subsidies_match_nas(built, prod):
    """Plan tests 4 and 5."""
    nas = "mospi_nas_2026_s1_1"
    taxes_p, subs_p = v(nas, "s1_1.taxes_on_products.current"), v(nas, "s1_1.subsidies_on_products.current")
    assert s(built, ref="P7a") + s(prod, ref="P8") + s(prod, ref="P9") == pytest.approx(taxes_p - subs_p, abs=1.0)
    p9a = s(built, ref="P9a")
    assert p9a == pytest.approx(float(sut("io_tables_sut_supply", "product_subsidies").filter(
        pl.col("product") == "total")["value"][0]), abs=1.0)  # fmt: skip
    assert p9a == pytest.approx(-subs_p, abs=1.0)
    assert set(built.filter(pl.col("ref") == "P9a")["row"]) == {"G_CEN", "G_STA"}


def test_production_taxes(built):
    """Plan test 6: P10a net = SUT net production taxes = NAS 7.1 (within 1); gross D39/D29 within 3%."""
    p10 = built.filter(pl.col("ref") == "P10a")
    va = sut("io_tables_sut_va", "net_production_taxes").filter(pl.col("industry").str.starts_with("sut_i"))
    assert s(p10) == pytest.approx(float(va["value"].sum()), abs=1e-4)
    assert s(p10) == pytest.approx(v("mospi_nas_2026_s7_1", "s7_1.total.net_production_taxes.current"), abs=1.0)
    d39 = v("mospi_nas_2026_s4_2", "s4_2.subsidy.total.current") - v(
        "mospi_nas_2026_s1_1", "s1_1.subsidies_on_products.current"
    )
    assert -s(p10, component="gross_subsidies") == pytest.approx(d39, rel=0.03)
    taxes_c = ["stamps_registration", "land_revenue", "property_tax", "other_production_taxes"]
    assert s(p10, component=taxes_c) == pytest.approx(d39 + float(va["value"].sum()), rel=0.03)
    assert set(p10["component"]) == {*taxes_c, "gross_subsidies"}  # XR-19 names, frozen
    assert s(p10, row="G_STA", component="stamps_registration") == pytest.approx(
        sf("i.a.2.ii-stamps_and_registration_fees"), rel=1e-9)  # fmt: skip


def test_union_identities(cons):
    """Plan test 7: T1 CGST target = MH 0005 + 0008 + 0007; RB gross = FA net + 901; TAX-4."""
    rb, fa = "union_fiscal_rb_receipts", "union_fiscal_fa_receipts"
    t = dict(cons.select("constraint_id", "target").iter_rows())
    assert t["t1.cgst"] == pytest.approx(
        v(rb, "rb.tr.0005.central_goods_and_services_tax_cgst")
        + v(rb, "rb.tr.0008.integrated_goods_and_services_tax_igst")
        + v(rb, "rb.tr.0007.union_territories_goods_and_services_tax_utgst")
    )
    for rbs, tot, h901 in (
        ("rb.tr.0005.central_goods_and_services_tax_cgst", "fa8.0005.total", "fa8.0005.00.901"),
        ("rb.tr.total.total_corporation_tax", "fa8.0020.total", "fa8.0020.00.901"),
        ("rb.tr.total.total_customs", "fa8.0037.total", "fa8.0037.00.901"),
        ("rb.tr.total.total_union_excise_duties", "fa8.0038.total", "fa8.0038.01.901"),
    ):
        assert v(rb, rbs) == pytest.approx(v(fa, tot) - v(fa, h901), abs=0.02), rbs
    assert vsum(rb, "rb.tr.0021.") == pytest.approx(v(fa, "fa8.0021.total") - v(fa, "fa8.0021.00.901"), abs=0.02)
    assert v(rb, "rb.tr.0005.central_goods_and_services_tax_cgst") + v(
        rb, "rb.tr.0008.integrated_goods_and_services_tax_igst") + v(rb, "rb.tr.0009.gst_compensation_cess") == \
        pytest.approx(v(rb, "rb.tr.total.total_goods_and_services_tax_gst"), abs=0.01)  # fmt: skip
    assert t["t4.total"] == v(rb, "rb.tr.total.total_corporation_tax")


def test_direct_taxes(built):
    """Plan test 8: T_CIT = MH 0020; no E_RBI; T_PIT = MH 0021 + STT + minor heads + State taxes on income;
    the household share of MH 0021 is within the old-base / IFPRI range."""
    rb = "union_fiscal_rb_receipts"
    cit = built.filter(pl.col("row") == "T_CIT")
    assert s(cit) == pytest.approx(v(rb, "rb.tr.total.total_corporation_tax"), abs=1.0)
    assert "E_RBI" not in set(cit["col"])
    mh21 = vsum(rb, "rb.tr.0021.")
    heads = sum(v(rb, x) for x in ("rb.tr.0034.security_transaction_tax", "rb.tr.0023.hotel_receipts_tax",
                                   "rb.tr.0024.interest_tax", "rb.tr.0026.fringe_benefit_tax",
                                   "rb.tr.total.total_other_taxes_on_income_and_expenditure",
                                   "rb.tr.0031.estate_duty", "rb.tr.0032.taxes_on_wealth"))  # fmt: skip
    state = sf("i.a.1-taxes_on_income")
    pit = built.filter(pl.col("row") == "T_PIT")
    assert s(pit) == pytest.approx(mh21 + heads + state, abs=1.0)
    other_hh = sum(v(rb, x) for x in ("rb.tr.0034.security_transaction_tax",
                                      "rb.tr.total.total_other_taxes_on_income_and_expenditure",
                                      "rb.tr.0031.estate_duty", "rb.tr.0032.taxes_on_wealth"))  # fmt: skip
    share = (s(pit, component="income_tax") - other_hh) / mh21
    assert 0.78 <= share <= 0.91, share
    assert set(pit.filter(pl.col("ref") == "T3")["col"]) == {"E_NFPR", "E_BANK"}
    assert set(pit.filter(pl.col("ref") == "T3")["component"]) == {"quasi_corporate"}
    ucb = v("rbi_banking_corporate_rtp_coop", "rtp.ucb_pl.tax_provisions.ucb.current", vintage="2025-12-29")
    assert s(pit, col="E_BANK") == pytest.approx(ucb)


def test_t3a_groups(built, cons):
    """Plan test 9: groups add up to the household constraint target, none negative; U5 + R5 share > 50%."""
    t3a = built.filter(pl.col("ref") == "T3a")
    assert set(t3a["col"]) <= set(HH) and (t3a["value"] > 0).all()
    t = dict(cons.select("constraint_id", "target").iter_rows())
    assert s(t3a) == pytest.approx(t["t3.households"], abs=1.0)
    it = t3a.filter(pl.col("component") == "income_tax")
    top = s(it, col=["H_U5", "H_R5"]) / s(it)
    print(f"T3a: U5 + R5 share of household income tax = {top:.3f} (gap map expects > 0.9: a finding if not)")
    assert top > 0.5
    pt = t3a.filter(pl.col("component") == "professions_tax")
    assert s(pt) == pytest.approx(sf("i.a.1-taxes_on_income"), abs=0.01)


def test_t4a_financial_corporations(built):
    """Plan test 10 (with XR-6): E_INSP within 15% of IRDAI provisions; E_NBFC + the deposit-taking share moved
    to E_BANK = RTP provisions, and E_NBFC within 15% of RTP less that share."""
    life, nl = "finsector_markets_irdai_life", "finsector_markets_irdai_nonlife"
    irdai = v(life, "t24.provision_for_tax.insurers_life.current") + v(
        life, "t25.provision_for_tax.insurers_life.current"
    )
    for g in ("general_public", "general_private", "health_standalone", "general_specialized"):
        irdai += v(nl, f"t51.provision_for_tax.{g}.current")
    cit = built.filter(pl.col("row") == "T_CIT")
    assert s(cit, col="E_INSP") == pytest.approx(irdai, rel=0.15)
    rtp, vt = "rbi_banking_corporate_rtp_nbfi", "2025-12-29"
    ul = v(rtp, "rtp.nbfc_layer_pl.tax_provisions.nbfc_ul.current", vintage=vt)
    ml = v(rtp, "rtp.nbfc_layer_pl.tax_provisions.nbfc_ml.current", vintage=vt)
    hfc = v(rtp, "rtp.hfc_pl.tax_provisions.hfc.current", vintage=vt)
    aifi = v(rtp, "rtp.aifi_pl.tax_provisions.aifi.current", vintage=vt)
    fsf = "rbi_financial_accounts_fsf_balance_sheets"

    def a(k: str) -> float:
        return v(fsf, f"fsf.fc_{k}.assets.outstanding.total.all.current", period="2024-03-31")

    moved = (ul + ml) * a("odc_nbfc_dt") / (a("odc_nbfc_dt") + a("ofc_nbfc_ndt")) + hfc * a("odc_hfc_dt") / (
        a("odc_hfc_dt") + a("ofc_hfc_ndt"))  # fmt: skip
    assert s(cit, col="E_NBFC") == pytest.approx(ul + ml + hfc + aifi - moved, rel=0.15)
    for acct in ("E_BANK", "E_NBFC", "E_INSP"):
        assert set(cit.filter(pl.col("col") == acct)["component"]) == {"public", "private"}


def test_state_side(cons):
    """Plan test 11: each T2 target is its RBI SF App I series; FC16 (28 States) within 6% of RBI SF."""
    t = dict(cons.select("constraint_id", "target").iter_rows())
    assert t["t2.sgst"] == sf("i.a.3.vii-state_goods_and_services_tax")
    assert t["t2.svat"] == sf("i.a.3.i-sales_tax")
    assert t["t2.sexc"] == sf("i.a.3.ii-state_excise")
    kfi = "state_fiscal_fc16_kfi"
    for code, app in (("a_1_1_2-state_goods_and_service_tax", "i.a.3.vii-state_goods_and_services_tax"),
                      ("a_1_1_1-taxes_on_sales_trade_etc", "i.a.3.i-sales_tax"),
                      ("a_1_1_3-state_excise", "i.a.3.ii-state_excise"),
                      ("a_1_1_4-taxes_on_vehicles", "i.a.3.iii-taxes_on_vehicles")):  # fmt: skip
        assert abs(v(kfi, f"kfi.{code}.in.all_states_28") / sf(app) - 1) <= 0.06, code


def test_s7_satellite(built):
    """Plan test 12: MH 0008 imports + domestic = total; CGST-side ITC = minus IGST-side ITC; the residual is
    the IGST inside T_CGST."""
    s7 = sat("s7_igst_settlement")
    val = dict(s7.select("series_id", "value").iter_rows())
    assert val["s7.annual.igst_imports"] + val["s7.annual.igst_domestic_net"] == pytest.approx(
        val["s7.annual.igst_residual"], abs=0.01)  # fmt: skip
    assert val["s7.annual.cgst_from_igst_itc"] == pytest.approx(-val["s7.annual.itc_to_cgst"], abs=0.01)
    assert val["s7.annual.igst_residual"] == pytest.approx(
        v("union_fiscal_rb_receipts", "rb.tr.0008.integrated_goods_and_services_tax_igst"), abs=0.01
    )
    assert set(s7["status"]) == {"official"}


def test_p7b_satellite(built):
    """Plan test 13: per (type, component, commodity) the uses add up to the P7a entry; no GST/cess or petroleum
    excise/VAT on exports."""
    b = sat("p7b_tax_by_use")
    agg = b.group_by(["tax_account", "component", "commodity"], maintain_order=True).agg(pl.col("value").sum())
    got = {(r[0], r[1], r[2]): r[3] for r in agg.iter_rows()}
    p = built.filter(pl.col("ref") == "P7a")
    assert len(got) == p.height
    for r in p.iter_rows(named=True):
        assert got[(r["row"], r["component"], r["col"])] == pytest.approx(r["value"], rel=1e-7, abs=1e-5)
    ex = b.filter(pl.col("use_type") == "exports")
    assert ex.filter(pl.col("tax_account").is_in(["T_CGST", "T_SGST", "T_GCES"])).height == 0
    assert ex.filter(pl.col("tax_account").is_in(["T_UEXC", "T_SVAT"]) & (pl.col("commodity") == "C_RPET")).height == 0


def test_tax_classification_books_each_contested_head_once(built):
    """Plan test 14: vehicle tax, professions tax and MISS appear once in tax_classification; vehicle tax only in
    T_OPRT (no T_PROD component for it); and, once government is built, it books no R16 vehicle tax."""
    c = sat("tax_classification")
    for item in ("vehicle_tax_states", "professions_tax", "miss_interest_subvention", "stt", "ctt", "utgst"):
        assert c.filter(pl.col("item") == item).height == 1, item
    assert c.filter(pl.col("item") == "vehicle_tax_states")["value"][0] == sf("i.a.3.iii-taxes_on_vehicles")
    assert "vehicle" not in " ".join(built.filter(pl.col("ref") == "P10a")["component"].to_list())
    if PATHS.built("government"):
        g = pl.read_parquet(PATHS.entries("government"))
        assert g.filter((pl.col("ref") == "R16") & pl.col("component").str.contains("vehicle")).height == 0


def test_tax_accounts_close_in_the_prior(built, prod):
    """Every tax account's row (production + taxes) equals its column (taxes)."""
    both = pl.concat([built.select("row", "col", "value"), prod.select("row", "col", "value")])
    for a in [*PRODUCT_TAX, "T_CUST", "T_PSUB", "T_PROD", "T_PIT", "T_CIT"]:
        assert s(both, row=a) == pytest.approx(s(both, col=a), abs=1e-4), a


def test_provenance_and_roles(built, cons):
    """Plan test 15: every output cites a record of this block; estimated records state their assumptions."""
    prov = pl.read_parquet(PATHS.provenance("taxes"))
    ids = set(prov["prov_id"])
    assert set(built["prov_id"]) <= ids and set(cons["prov_id"]) <= ids
    for f in sorted(PATHS.satellites("taxes").glob("*.parquet")):
        assert set(pl.read_parquet(f)["prov_id"]) <= ids, f.name
    est = prov.filter(pl.col("status") == "estimated")
    assert all("Gap map" in m or "gap map" in m for m in est["method"].to_list())
    text = " ".join(est["method"].to_list())
    for must in ("700,000", "old-base NAS", "scaled by one factor", "licence_fee_excess"):
        assert must in text, must
    roles = {(r["row"], r["col"]): r["role"] for r in built.iter_rows(named=True) if r["ref"] == "T1a"}
    assert roles[("G_CEN", "T_CUST")] == "fixed"
    assert roles[("G_CEN", "T_PIT")] == roles[("G_CEN", "T_CIT")] == "anchored"
    assert built.filter(pl.col("role") == "free")["confidence"].null_count() == 0
