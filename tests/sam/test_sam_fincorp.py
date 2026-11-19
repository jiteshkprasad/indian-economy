"""The fincorp block (F4a R3 R3a R3b R4 R5 R8 R8a R9c R17 K2 K2a S9).

Two sources are tested:
- `synthetic`: the block assembled from clean data with *synthetic* dependency outputs (households' keys and
  C4b FISIM, factors' wage keys and NFC GOS, government's R6/R7, rest_of_world's R13/R14), so the block's own
  arithmetic is tested whatever the state of the other blocks;
- `built`: the outputs of `sam fincorp` (skipped while a dependency is not built; they must match a fresh build).

Every expected total is recomputed here from data/clean with polars (plan s.7), never typed in."""

from __future__ import annotations

import polars as pl
import pytest

from pipeline.core.io import canonical_floats
from pipeline.core.paths import Layout
from pipeline.sam import spec
from pipeline.sam.blocks import fincorp
from pipeline.sam.blocks.fincorp.assemble import assemble
from pipeline.sam.blocks.fincorp.core import HH, Out, Q, qsum, shares
from pipeline.sam.blocks.fincorp.deps import KEYS_NEEDED, Deps
from pipeline.sam.framework import BlockContext, SamPaths, build_block_module, validate_result

pytestmark = pytest.mark.sam

LAYOUT = Layout.default()
PATHS = SamPaths(LAYOUT)
YEAR = spec.YEAR
FC = ["E_RBI", "E_BANK", "E_NBFC", "E_INSP"]
NFC = ["E_NFPU", "E_NFPR"]
UNITS = {
    "mospi": "mospi_nas_2026",
    "io_tables": "io_tables",
    "rbi_banking": "rbi_banking_corporate",
    "rbi_financial": "rbi_financial_accounts",
    "union": "union_fiscal",
    "state": "state_fiscal",
    "finsector": "finsector_markets",
}


# ---------------------------------------------------------------------------------------------
# clean data, read independently of the block
# ---------------------------------------------------------------------------------------------


def _unit(dataset: str) -> str:
    for k, u in UNITS.items():
        if dataset.startswith(k):
            return u
    raise KeyError(dataset)


_FRAMES: dict[str, pl.DataFrame] = {}


def clean(dataset: str, series_id: str, period: str = YEAR, vintage: str | None = None) -> float:
    if dataset not in _FRAMES:
        _FRAMES[dataset] = pl.read_parquet(LAYOUT.clean / _unit(dataset) / f"{dataset}.parquet")
    df = _FRAMES[dataset].filter((pl.col("series_id") == series_id) & (pl.col("period") == period))
    if vintage is not None:
        df = df.filter(pl.col("vintage") == vintage)
    df = df.sort("vintage")
    assert df.height >= 1, (dataset, series_id, period, vintage)
    return float(df["value"][-1])


def nas(ds: str, sid: str) -> float:
    return clean(f"mospi_nas_2026_{ds}", sid)


RBI_AR = ("rbi_banking_corporate_rbi_accounts", "2024-05-30")


# ---------------------------------------------------------------------------------------------
# synthetic dependency outputs (TEST FIXTURE, not data)
# ---------------------------------------------------------------------------------------------

RISING = [1, 2, 3, 4, 6, 2, 3, 4, 6, 10]
FIX_NFC_GOS = {"E_NFPU": 1_167_179.33, "E_NFPR": 4_619_027.77}  # fixture levels (factors plan s.3)


def synthetic_deps(ctx: BlockContext) -> Deps:
    def fx(ref: str, what: str) -> frozenset[str]:
        return frozenset(
            {
                ctx.prov(
                    ref=ref,
                    status="estimated",
                    inputs=[],
                    vintage="2026-09-30",
                    method=f"TEST FIXTURE (synthetic dependency output): {what}",
                    notes="synthetic test fixture, not data",
                )
            }
        )

    def lv(ref: str, what: str, w: list[float]) -> dict[str, Q]:
        p = fx(ref, what)
        return {g: Q(float(x), p) for g, x in zip(HH, w)}

    keys = {
        k: lv("R8a", f"hh_keys {k}", RISING if k != "pop_persons" else [12, 11, 10, 9, 8, 5, 5, 5, 5, 5])
        for k in KEYS_NEEDED
    }
    pfce_fisim = nas("s1_13", "s1_13.private_final_consumption_expenditure.current")
    c4b = {
        "fisim_deposits": lv("R8a", "C4b fisim_deposits", [0.46 * pfce_fisim * w / sum(RISING) for w in RISING]),
        "fisim_loans": lv("R8a", "C4b fisim_loans", [0.54 * pfce_fisim * w / sum(RISING) for w in RISING]),
    }
    p = fx("R8", "government R6/R7, factors F4 NFC GOS")
    r7 = {
        ("G_CEN", "E_NFPU"): 64_906.20,
        ("G_CEN", "E_BANK"): 14_295.56,
        ("G_CEN", "E_INSP"): 4_272.54,
        ("G_STA", "E_NFPU"): 6_914.54,
    }
    rp = fx("R4", "rest_of_world R13/R14")
    row = [
        ("E_RBI", "R_ROW", "R13", "reserve_asset_income", 105_413.50),
        ("E_RBI", "R_ROW", "R13", "reserve_income_unexplained", 25_645.50),
        ("E_BANK", "R_ROW", "R13", "oi_income", 16_000.0),
        ("E_NBFC", "R_ROW", "R13", "oi_income", 10.0),
        ("R_ROW", "G_CEN", "R14", "ext_assistance_interest", 29_616.7407),
        ("R_ROW", "G_CEN", "R14", "fpi_gsec_interest", 12_700.0),
        ("R_ROW", "G_CEN", "R14", "fpi_tbill_interest", 120.0),
        ("R_ROW", "G_STA", "R14", "fpi_sdl_interest", 166.0),
        ("R_ROW", "E_BANK", "R14", "nri_deposit_interest", 57_794.0),
        ("R_ROW", "E_NBFC", "R14", "oi_other_interest", 25_000.0),
        ("R_ROW", "E_RBI", "R14", "reserve_asset_debit", 7_118.0),
    ]
    return Deps(
        hh_keys=keys,
        c4b_fisim=c4b,
        wage_regular=lv("R9c", "F1a F_LREG", [5, 8, 10, 14, 20, 6, 10, 15, 22, 35]),
        wage_public=lv("R9c", "public_sector_wage_key", [1, 2, 3, 4, 6, 1, 2, 4, 7, 12]),
        nfc_gos={k: Q(v, p) for k, v in FIX_NFC_GOS.items()},
        r6=Q(87_416.2162, p),
        r7={k: Q(v, p) for k, v in r7.items()},
        row=[dict(row=a, col=b, ref=c, component=d, q=Q(v, rp)) for a, b, c, d, v in row],
        r7x={("G_STA", "E_NFPR"): Q(50_000.0, p), ("G_CEN", "E_NFPU"): Q(100_000.0, p)},
    )


@pytest.fixture(scope="module")
def synthetic():
    ctx = BlockContext(block="fincorp", refs=tuple(fincorp.REFS), depends=(), layout=LAYOUT)
    deps = synthetic_deps(ctx)
    valid = validate_result(ctx, assemble(ctx, deps))
    return valid, deps


def _deps_built() -> bool:
    return all(PATHS.built(d) for d in fincorp.DEPENDS)


@pytest.fixture(scope="module")
def built():
    if not _deps_built():
        pytest.skip(
            "fincorp integration pending: a dependency is not built ("
            + ", ".join(d for d in fincorp.DEPENDS if not PATHS.built(d))
            + ")"
        )
    if not PATHS.built("fincorp"):
        pytest.fail("fincorp not built: run `uv run python -m pipeline sam fincorp`")
    return pl.read_parquet(PATHS.entries("fincorp"))


@pytest.fixture(scope="module", params=["synthetic", "built"])
def entries(request, synthetic):
    if request.param == "synthetic":
        return synthetic[0].entries
    return request.getfixturevalue("built").drop("block")


def _sum(e: pl.DataFrame, **f) -> float:
    for k, v in f.items():
        e = e.filter(pl.col(k).is_in(v if isinstance(v, list) else [v]))
    return float(e["value"].sum())


# ---------------------------------------------------------------------------------------------
# built outputs
# ---------------------------------------------------------------------------------------------


def test_built_outputs_equal_a_fresh_build(built):
    r, valid = build_block_module(fincorp, LAYOUT, write=False)
    assert r.ok, r.message
    want = canonical_floats(valid.entries, {"value": 6, "tol_rel": None}).sort(list(spec.ENTRY_KEY))
    assert built.drop("block").equals(want)
    cons = pl.read_parquet(PATHS.constraints("fincorp"))
    assert cons.drop("block").equals(canonical_floats(valid.constraints).sort("constraint_id"))
    assert pl.read_parquet(PATHS.provenance("fincorp")).equals(valid.provenance.sort("prov_id"))


def test_built_checks_pass_except_logged_findings(built):
    checks = pl.read_parquet(PATHS.checks("fincorp"))
    allowed = {"k2a.rbi_prior_vs_nas"}  # fincorp-1 in docs/phase2/issues/fincorp.md (rest_of_world-26)
    failed = checks.filter(~pl.col("ok") & ~pl.col("check_id").is_in(list(allowed)))
    assert failed.height == 0, failed
    assert checks.height >= 14
    assert checks.filter(pl.col("check_id") == "k2a.rbi_cash_basis_evidence")["ok"].to_list() == [True]


def test_rbi_saving_evidence_and_the_reserve_asset_debit(built):
    """Plan C3 (D0-7 evidence): E_RBI's saving on the RBI AR basis matches NAS public FC saving less public FC
    GOS; the K2a prior differs from it by exactly rest_of_world's R14 reserve-asset debit on E_RBI (fincorp-1)."""
    target = (
        nas("s1_9", "s1_9.public_financial_corporations.current")
        - nas("s7_1a", "s7_1a.financial.os.current")
        - nas("s7_1a", "s7_1a.financial.cfc.current")
    )
    k2a = _sum(built, ref="K2a", row="K_RBI", col="E_RBI")
    row = pl.read_parquet(PATHS.entries("rest_of_world"))
    debit = _sum(row, ref="R14", row="R_ROW", col="E_RBI", component="reserve_asset_debit")
    checks = {r["check_id"]: r for r in pl.read_parquet(PATHS.checks("fincorp")).iter_rows(named=True)}
    ev, pr = checks["k2a.rbi_cash_basis_evidence"], checks["k2a.rbi_prior_vs_nas"]
    assert abs(ev["target"] - target) <= 0.01 and abs(pr["target"] - target) <= 0.01
    assert abs(pr["sam_value"] - k2a) <= 0.01
    assert abs(ev["sam_value"] - (k2a + debit)) <= 0.01
    assert abs(ev["sam_value"] - target) <= 2500.0


def test_rest_of_world_components_are_checked_by_name(built):
    """deps.py reads rest_of_world's R13/R14 components by name: the built ones pass the guard, a renamed one stops
    the build (no silent drop out of a sum)."""
    from pipeline.sam.blocks.fincorp.deps import check_row_components

    re_ = pl.read_parquet(PATHS.entries("rest_of_world")).filter(pl.col("ref").is_in(["R13", "R14", "R14a"]))
    row = [dict(ref=r["ref"], component=r["component"]) for r in re_.iter_rows(named=True)]
    check_row_components(row)
    renamed = [
        dict(r, component="sdr_allocation_charges") if r["component"] == "reserve_asset_debit" else r for r in row
    ]
    with pytest.raises(Exception, match="components changed"):
        check_row_components(renamed)


# ---------------------------------------------------------------------------------------------
# official totals (plan s.7 T1-T5, T11, T12), recomputed from clean data
# ---------------------------------------------------------------------------------------------


def test_f4a_totals(entries):
    """T1, T3, T4: F4a = FC GOS (7.1A + 7.1B); RBI+banks+NBFCs = SUT ind. 55, insurers = ind. 56; public and
    private parts = 7.1A and 7.1B."""
    f = entries.filter(pl.col("ref") == "F4a")
    pub = nas("s7_1a", "s7_1a.financial.os.current") + nas("s7_1a", "s7_1a.financial.cfc.current")
    prv = nas("s7_1b", "s7_1b.financial.os.current") + nas("s7_1b", "s7_1b.financial.cfc.current")
    i55 = clean("io_tables_sut_va", "va.os_mi.sut_i55.current") + clean("io_tables_sut_va", "va.cfc.sut_i55.current")
    i56 = clean("io_tables_sut_va", "va.os_mi.sut_i56.current") + clean("io_tables_sut_va", "va.cfc.sut_i56.current")
    assert abs(_sum(f) - (pub + prv)) <= 1.0
    assert abs(_sum(f, row=["E_RBI", "E_BANK", "E_NBFC"]) - i55) <= 1.0
    assert abs(_sum(f, row="E_INSP") - i56) <= 1.0
    assert abs(_sum(f, component="public") - pub) <= 1.0
    assert abs(_sum(f, component="private") - prv) <= 1.0
    assert set(f["col"]) == {"F_GOSC"} and set(f["row"]) == set(FC)


def test_f4a_rbi_is_gva_less_employee_cost_and_equals_depreciation(entries):
    """T2: central-bank output at cost."""
    rbi = _sum(entries, ref="F4a", row="E_RBI")
    s121 = nas("s8_12", "s8_12.central_bank_s_121.current")
    ce = clean(RBI_AR[0], "is.exp_employee_cost.current", vintage=RBI_AR[1])
    dep = clean(RBI_AR[0], "is.exp_depreciation.current", vintage=RBI_AR[1])
    assert abs(rbi - (s121 - ce)) <= 0.01 and abs(rbi - dep) <= 0.01
    row = entries.filter((pl.col("ref") == "F4a") & (pl.col("row") == "E_RBI"))
    assert row["role"].to_list() == ["anchored"] and row["component"].to_list() == ["public"]


def test_k2a_reproduces_nas_saving(entries):
    """T5: K2a = NAS 1.9 FC saving; public and private components = NAS public and private (co-op banks private)."""
    k = entries.filter(pl.col("ref") == "K2a")
    assert abs(_sum(k) - nas("s1_9", "s1_9.financial_corporations.current")) <= 1.0
    assert abs(_sum(k, component="public") - nas("s1_9", "s1_9.public_financial_corporations.current")) <= 1.0
    assert abs(_sum(k, component="private") - nas("s1_9", "s1_9.private_financial_corporations.current")) <= 1.0
    assert set(zip(k["row"], k["col"])) <= {
        ("K_RBI", "E_RBI"),
        ("K_BANK", "E_BANK"),
        ("K_NBFC", "E_NBFC"),
        ("K_INSP", "E_INSP"),
    }


def test_gpf_and_life_d44(entries):
    """T11: R9c gpf_union = MH 2049.03.104; life = IRDAI T24 interest/dividends/rent + amortisation."""
    gpf = clean("union_fiscal_fa_expenditure", "fa9.2049.03.104")
    assert abs(_sum(entries, ref="R9c", component="gpf_union", col="G_CEN") - gpf) <= 1.0
    life = clean("finsector_markets_irdai_life", "t24.inv_interest_dividends_rent_gross.insurers_life.current") + clean(
        "finsector_markets_irdai_life", "t24.inv_amortisation.insurers_life.current"
    )
    assert abs(_sum(entries, ref="R9c", component="life") - life) <= 1.0
    states_pf = clean(
        "state_fiscal_rbi_sf_appendices",
        "app2.total_expenditure.ii.c.2.iii-interest_on_small_savings_state_provident_funds.in.all_states_uts.actuals",
    )
    assert abs(_sum(entries, ref="R9c", component="gpf_states", col="G_STA") - states_pf) <= 1.0


def test_r17_claims_premiums_supplements(entries):
    """T12: claims = IRDAI net claims; premiums = claims; supplements = non-life investment income less the
    shareholders' part."""
    r = entries.filter(pl.col("ref") == "R17")
    claims = clean("finsector_markets_irdai_nonlife", "t44.claims_incurred_net.total.insurers_general_direct.current")
    supp = clean("finsector_markets_irdai_summary", "sum_c.investment_income.current") - sum(
        clean("finsector_markets_irdai_nonlife", f"t51.inv_interest_dividend_rent_gross.{g}.current")
        for g in ("general_private", "general_public", "general_specialized", "health_standalone")
    )
    assert abs(_sum(r, component="claim") - claims) <= 1.0
    assert abs(_sum(r, component="premium") - claims) <= 1.0
    assert abs(_sum(r, component="premium_supplement") - supp) <= 1.0
    assert set(r.filter(pl.col("component") == "premium")["row"]) == {"E_INSP"}
    assert set(r.filter(pl.col("component") != "premium")["col"]) == {"E_INSP"}


# ---------------------------------------------------------------------------------------------
# government interest (T7-T10)
# ---------------------------------------------------------------------------------------------


def _union_lines() -> dict[str, float]:
    df = pl.read_parquet(LAYOUT.clean / "union_fiscal" / "union_fiscal_fa_expenditure.parquet").filter(
        pl.col("series_id").str.starts_with("fa9.2049.") & (pl.col("period") == YEAR)
    )
    return {r["series_id"].removeprefix("fa9.2049."): r["value"] for r in df.iter_rows(named=True)}


def test_union_bridge_reproduces_the_nas_concept_target(synthetic):
    """T7: the bridge lines add to MH 2049 total, and every Union interest written (fincorp + the RoW memo)
    equals the NAS-concept target recomputed here: cash - intra-G_CEN - management of debt - recoveries -
    re-issue receipts + NSSF interest to savers."""
    valid, deps = synthetic
    ln = _union_lines()
    total = ln.pop("total")
    lines = {k: v for k, v in ln.items() if not k.endswith(".total")}
    assert abs(sum(lines.values()) - total) <= 0.05
    L = lambda *ks: sum(lines.get(k, 0.0) for k in ks)  # noqa: E731
    reissue = clean("union_fiscal_fa_receipts", "fa8.0049.03.117") + clean(
        "union_fiscal_fa_receipts", "fa8.0049.03.116"
    )
    states_nssf = clean(
        "state_fiscal_rbi_sf_appendices",
        "app2.total_expenditure.ii.c.2.ii.b-interest_on_nssf.in.all_states_uts.actuals",
    )
    nssf = L("01.121", "01.122", "01.125")
    target = (
        total
        - nssf
        - L("05.101", "05.103", "05.105", "60.107", "60.111")
        - L("01.305")
        - L("01.911", "03.911", "05.911")
        - reissue
        + nssf
        + states_nssf
    )
    cons = valid.constraints.filter(pl.col("constraint_id") == "r3b.union_nas_concept")
    assert abs(cons["target"][0] - target) <= 0.01
    e = valid.entries.filter((pl.col("col") == "G_CEN") & pl.col("ref").is_in(["R3", "R3a", "R8a", "R9c"]))
    row = sum(x["q"].v for x in deps.row if x["col"] == "G_CEN" and x["ref"] == "R14")
    assert abs(_sum(e) + row - target) <= 1.0
    sat = valid.satellites["gov_interest_bridge"][1]
    assert abs(float(sat.filter(pl.col("series_id") == "union.total")["value"][0]) - total) <= 1e-6


def test_states_bridge_and_lines(synthetic):
    """T8: States' lines add to the App. II total; the payer band holds in the prior; KFI cross-check within 3%."""
    valid, deps = synthetic
    sf = "app2.total_expenditure.ii.c.2{}.in.all_states_uts.actuals"
    S = lambda s: clean("state_fiscal_rbi_sf_appendices", sf.format(s))  # noqa: E731
    total = S("-interest_payments")
    parts = (
        S(".i-interest_on_loans_from_the_centre")
        + S(".ii-interest_on_internal_debt")
        + S(".iii-interest_on_small_savings_state_provident_funds")
        + S(".iv-others")
    )
    assert abs(parts - total) <= 0.05
    kfi = clean("state_fiscal_fc16_kfi", "kfi.b_1_a-interest_payments.in.all_states_28")
    assert abs(total / kfi - 1) <= 0.03
    cons = valid.constraints.filter(pl.col("constraint_id") == "r3b.states_nas_concept").row(0, named=True)
    e = valid.entries.filter((pl.col("col") == "G_STA") & pl.col("ref").is_in(["R3", "R3a", "R8a", "R9c"]))
    row = sum(x["q"].v for x in deps.row if x["col"] == "G_STA" and x["ref"] == "R14")
    assert abs(_sum(e) + row - cons["target"]) <= cons["tol_rel"] * cons["target"]
    assert cons["target"] <= total - S(".iv-others")


def test_instrument_allocation_sums_to_payer_lines(synthetic):
    """T9: dated securities (net of re-issue receipts), T-bills and SDLs are fully allocated: holders + FPI
    (RoW memo) + State reserve funds + households (bridge) = the payer line."""
    valid, deps = synthetic
    sat = valid.satellites["gov_interest_bridge"][1]
    ln = _union_lines()
    reissue = clean("union_fiscal_fa_receipts", "fa8.0049.03.117") + clean(
        "union_fiscal_fa_receipts", "fa8.0049.03.116"
    )
    alloc = sat.filter(pl.col("series_id").str.starts_with("alloc."))
    g = lambda sid: float(sat.filter(pl.col("series_id") == sid)["value"][0])  # noqa: E731
    cen = float(alloc.filter(pl.col("payer") == "G_CEN")["value"].sum())
    other_sec = sum(ln.get(k, 0.0) for k in ("01.118", "01.134", "01.200", "60.101", "60.106", "60.109"))
    want_c = (ln["01.101"] - reissue) + ln["01.103"] + ln["01.108"] + ln["01.110"] + other_sec
    assert abs(cen + g("derived.union.fpi_in_r14") + g("derived.union.rbi_ar") - want_c) <= 1.0
    sdl = clean(
        "state_fiscal_rbi_sf_appendices",
        "app2.total_expenditure.ii.c.2.ii.a-interest_on_market_loans.in.all_states_uts.actuals",
    )
    sta = float(alloc.filter(pl.col("payer") == "G_STA")["value"].sum())
    assert abs(sta + g("derived.states.fpi_in_r14") + g("derived.states.rbi_ar") - sdl) <= 1.0


def test_rbi_interest_from_government_and_banks(entries):
    """T10: E_RBI <- G = RBI AR rupee-securities interest + amortisation + the Centre's WMA (+ States' WMA/OD);
    RBI <-> bank entries + WMA/OD = the four Sch. 13 A money-market and loan lines (no WMA counted twice)."""
    ar = lambda s: clean(RBI_AR[0], f"sch13.a.{s}.current", vintage=RBI_AR[1])  # noqa: E731
    sec = ar("interest_on_holding_of_rupee_securities") + clean(
        RBI_AR[0], "sch14.a.amortisation_of_premium_discount_on_rupee_securities.current", vintage=RBI_AR[1]
    )
    wma = clean("union_fiscal_fa_expenditure", "fa9.2049.01.115")
    rbi_g = entries.filter((pl.col("row") == "E_RBI") & pl.col("col").is_in(["G_CEN", "G_STA"]))
    assert abs(_sum(rbi_g, component=["dated_securities", "sdl"]) - sec) <= 1.0
    assert abs(_sum(rbi_g, component="wma") - wma) <= 0.01
    money = (
        ar("net_interest_on_laf_operations")
        + ar("interest_on_sdf")
        + ar("interest_on_msf_operations")
        + ar("interest_on_loans_and_advances")
    )
    rbi_in = _sum(entries.filter(pl.col("ref") == "R4"), row="E_RBI") + _sum(rbi_g, component=["wma", "wma_od"])
    rbi_out = _sum(entries.filter(pl.col("ref") == "R4"), col="E_RBI")
    assert abs((rbi_in - rbi_out) - money) <= 1.0


# ---------------------------------------------------------------------------------------------
# FISIM (T6) and structure (T14-T16)
# ---------------------------------------------------------------------------------------------


def test_fisim_bridge_equals_domestic_nas_fisim(synthetic):
    """T6: FISIM written (NFC and household deposit/loan adjustments) = NAS 1.13 IC + PFCE FISIM (RoW FISIM
    has no SAM interest counterpart, XR-13); households' part per group = the C4b entries (XR-5) grossed up."""
    valid, deps = synthetic
    want = nas("s1_13", "s1_13.allocation_of_fisim_as_ic_to_user_industry.current") + nas(
        "s1_13", "s1_13.private_final_consumption_expenditure.current"
    )
    chk = valid.checks.filter(pl.col("check_id") == "fisim.written_total").row(0, named=True)
    assert chk["ok"] and abs(chk["target"] - want) <= 1e-6
    sat = valid.satellites["interest_fisim_bridge"][1]
    parts = sat.filter(
        pl.col("series_id").is_in(["fisim.ic_households", "fisim.ic_nfc_public", "fisim.ic_nfc_private"])
    )
    assert (
        abs(float(parts["value"].sum()) - nas("s1_13", "s1_13.allocation_of_fisim_as_ic_to_user_industry.current"))
        <= 1.0
    )
    # household deposit FISIM by group (added to R8a deposits) follows the C4b key exactly
    grossup = 1.0 + float(sat.filter(pl.col("series_id") == "fisim.household_grossup")["value"][0])
    for g in HH:
        c4b = deps.c4b_fisim["fisim_deposits"][g].v * grossup
        key = shares(deps.key("aidis_deposits"))[g].v
        dep = valid.entries.filter((pl.col("row") == g) & pl.col("component").is_in(["deposits_bank", "deposits_nbfc"]))
        bank_int = sum(
            float(sat.filter(pl.col("series_id") == f"pos.hh.{d}.deposits.bank_interest")["value"].sum())
            for d in ("e_bank", "e_nbfc")
        )
        assert abs(float(dep["value"].sum()) - (bank_int * key + c4b)) <= 0.01


def test_no_double_count_guards(entries):
    """T14."""
    e = entries
    assert e.filter(pl.col("row") == "R_ROW").height == 0 and e.filter(pl.col("col") == "R_ROW").height == 0
    assert e.filter((pl.col("ref") == "R8") & pl.col("row").is_in(["G_CEN", "G_STA"])).height == 0
    assert e.filter((pl.col("ref") == "R3a") & pl.col("row").str.starts_with("H_")).height == 0
    assert e.filter((pl.col("ref") == "R5") & pl.col("col").is_in(["G_CEN", "G_STA"])).height == 0
    assert e.filter((pl.col("ref") == "R9c") & (pl.col("component") == "ppf")).height == 0
    assert e.filter((pl.col("row") == "G_CEN") & (pl.col("col") == "G_CEN")).height == 0
    assert e.filter(pl.col("col") == "E_RBI").filter(pl.col("row") == "G_CEN").height == 0  # R6 is government's
    assert e.filter(pl.col("component").str.contains("premium") & (pl.col("ref") != "R17")).height == 0
    assert e.filter(pl.col("row").str.starts_with("I_") | pl.col("col").str.starts_with("I_")).height == 0
    # non-life supplements only in R17; GPF only in R9c
    assert e.filter((pl.col("ref") == "R9c") & (pl.col("component") == "premium_supplement")).height == 0
    assert e.filter((pl.col("component").str.starts_with("gpf")) & (pl.col("ref") != "R9c")).height == 0


def test_roles_statuses_and_cells(entries):
    e = entries
    assert e.filter(pl.col("value") == 0).height == 0
    assert set(e.filter(pl.col("role") == "free")["status"]) == {"estimated"}
    allowed_rows = {
        "F4a": set(FC),
        "R3": {"G_CEN", "G_STA"},
        "R3a": {*FC, *NFC, "G_STA"},
        "R4": {*FC, *NFC, "G_CEN", "G_STA"},
        "R5": {"E_BANK", "E_NBFC", "E_INSP"},
        "R8": {*FC, *NFC},
        "R8a": set(HH),
        "R9c": set(HH),
        "R17": {*HH, *NFC, "E_INSP"},
        "K2a": {"K_RBI", "K_BANK", "K_NBFC", "K_INSP"},
    }
    for ref, rows in allowed_rows.items():
        got = set(e.filter(pl.col("ref") == ref)["row"])
        assert got and got <= rows, (ref, got - rows)
    assert set(e.filter(pl.col("ref") == "R5")["col"]) <= {*HH, *NFC}
    assert set(e.filter(pl.col("ref") == "R9c")["col"]) <= {"E_INSP", "G_CEN", "G_STA"}
    assert set(e.filter(pl.col("ref") == "R3a")["col"]) <= {"G_CEN", "G_STA"}


def test_household_entries_are_by_group_and_follow_their_keys(synthetic):
    """T15: every household-touching entry is at group level; R8a components without a FISIM part are the
    total x the named hh_keys key."""
    valid, deps = synthetic
    e = valid.entries
    hh_e = e.filter(pl.col("row").str.starts_with("H_") | pl.col("col").str.starts_with("H_"))
    assert set(hh_e["row"]).union(hh_e["col"]) & {"HH", "H_TOTAL"} == set()
    key_of = {
        "small_savings": "aidis_small_savings",
        "gsec_direct": "aidis_fin_assets",
        "mf_lookthrough": "aidis_mf",
        "dividends": "aidis_equity",
        "debentures": "aidis_fin_assets",
    }
    r8a = e.filter(pl.col("ref") == "R8a")
    for (comp, col), grp in r8a.group_by(["component", "col"], maintain_order=True):
        if comp not in key_of:
            continue
        key = shares(deps.key(key_of[comp]))
        tot = float(grp["value"].sum())
        assert grp.height == 10
        for r in grp.iter_rows(named=True):
            assert abs(r["value"] / tot - key[r["row"]].v) <= 1e-9, (comp, col, r["row"])


def test_assumption_parameters_are_their_own_records(synthetic):
    """T16: every entry has a record; each assumption parameter exists as its own record."""
    valid, _ = synthetic
    prov = valid.provenance
    assert valid.entries["prov_id"].is_in(prov["prov_id"].to_list()).all()
    methods = prov["method"].to_list()
    for needle in (
        "r* (FISIM reference rate)",
        "r_corp",
        "EPS and exempted-PF funds earn the EPF declared rate",
        "private NFCs and private NBFCs distribute the same share",
        "share of each non-life line",
        "mutual-fund units held by 'corporates'",
    ):
        assert sum(needle in m for m in methods) == 1, needle
    est = prov.filter(pl.col("status") == "estimated")
    assert (est["method"].str.len_chars() > 40).all()


def test_s9_satellite_census(synthetic):
    """T13: S9 official rows equal their source series exactly."""
    valid, _ = synthetic
    s9 = valid.satellites["s9_funded_schemes"][1]
    g = lambda sid: float(s9.filter(pl.col("series_id") == sid)["value"][0])  # noqa: E731
    E = ("finsector_markets_epfo_ar", "2024-12")
    assert g("s9.epf.contributions") == pytest.approx(
        clean(E[0], "app5i.epf_contribution.current", vintage=E[1]), abs=0.01
    )
    assert g("s9.eps.contributions") == pytest.approx(
        clean(E[0], "para54.eps_contribution_total.current", vintage=E[1]), abs=0.01
    )
    assert g("s9.life.premiums") == pytest.approx(
        clean("finsector_markets_irdai_life", "t24.premium.insurers_life.current"), abs=0.01
    )
    assert g("s9.ppf.net_accretion") == pytest.approx(clean("union_fiscal_nssf", "nssf.ppf.additions"), abs=0.01)
    assert g("s9.gpf_union.additions") == pytest.approx(
        clean("union_fiscal_fa_provident_funds", "fa14.8009.total.additions"), abs=0.01
    )
    for c in ("central_govt", "state_govt", "corporate", "apy"):
        assert g(f"s9.nps.contributions.{c}") == pytest.approx(
            clean("finsector_markets_pfrda_nps", f"m4d.annual_contribution.{c}.current"), abs=0.01
        )
    assert s9["series_id"].n_unique() == s9.height


def test_vintages_are_pinned(synthetic):
    """T18: multi-vintage inputs are read at the named vintage (RBI AR 2023-24 = 2024-05-30; EPFO AR 2023-24)."""
    valid, _ = synthetic
    ins = set(",".join(x for x in valid.provenance["inputs"].drop_nulls().to_list()).split(","))
    ar = pl.read_parquet(LAYOUT.clean / "rbi_banking_corporate" / "rbi_banking_corporate_rbi_accounts.parquet")
    used = ar.filter(pl.col("prov_id").is_in(list(ins)) & (pl.col("period") == YEAR))
    assert used.height and set(used["vintage"]) == {"2024-05-30"}
    ep = pl.read_parquet(LAYOUT.clean / "finsector_markets" / "finsector_markets_epfo_ar.parquet")
    used = ep.filter(pl.col("prov_id").is_in(list(ins)))
    assert used.height and set(used["vintage"]) == {"2024-12"}


# ---------------------------------------------------------------------------------------------
# verification fixes (docs/phase2/verify/fincorp.md V-FIN-1..8; dispositions in the issues file)
# ---------------------------------------------------------------------------------------------

ENDS = ("2023-03-31", "2024-03-31")


def fsf_avg(sec: str, side: str, inst: str, cp: str) -> float:
    sid = f"fsf.{sec}.{side}.outstanding.{inst}.{cp}.current"
    return sum(clean("rbi_financial_accounts_fsf_balance_sheets", sid, period=p) for p in ENDS) / 2


def test_ic_fisim_user_key_nets_out_gg_ic_of_every_published_industry(synthetic):
    """V-FIN-1: public NFCs' IC FISIM share = 7.1A IC less NAS 8.15.1 GG IC for *every* industry 8.15.1
    publishes (the list is read from the clean table here, not from the block)."""
    valid, _ = synthetic
    s8151 = pl.read_parquet(LAYOUT.clean / "mospi_nas_2026" / "mospi_nas_2026_s8_15_1.parquet").filter(
        (pl.col("period") == YEAR) & pl.col("series_id").str.ends_with(".ic.current")
    )
    gg = {
        r["series_id"].split(".")[1]: r["value"]
        for r in s8151.sort("vintage").unique("series_id", keep="last", maintain_order=True).iter_rows(named=True)
    }
    gg_total = gg.pop("total")
    assert abs(sum(gg.values()) - gg_total) <= 1.0 and "utilities" in gg
    ind = {
        "agriculture_livestock_forestry_and_fishing": "agri",
        "mining_and_quarrying": "mining",
        "manufacturing": "manufacturing",
        "electricity_gas_water_supply_and_other_utility_services": "utilities",
        "construction": "construction",
        "trade_repair_hotels_and_restaurants": "trade_hotels",
        "transport_storage_communication_and_services_related_to_broa": "transport_comm",
        "real_estate_ownership_of_dwelling_and_professional_services": "real_estate_prof",
        "public_administration_and_defence": "public_admin",
        "other_services": "other_services",
    }
    want = {"pub": 0.0, "pvt": 0.0, "hh": 0.0}
    for k, code in ind.items():
        f = nas("s1_13", f"s1_13.{k}.current")
        if f == 0:
            continue
        a = nas("s7_1a", f"s7_1a.{code}.ic.current") - gg.get(code, 0.0)
        b, c = nas("s7_1b", f"s7_1b.{code}.ic.current"), nas("s7_1c", f"s7_1c.{code}.ic.current")
        for key, v in (("pub", a), ("pvt", b), ("hh", c)):
            want[key] += f * v / (a + b + c)
    sat = valid.satellites["interest_fisim_bridge"][1]
    got = lambda sid: float(sat.filter(pl.col("series_id") == sid)["value"][0])  # noqa: E731
    assert abs(got("fisim.ic_nfc_public") - want["pub"]) <= 0.01
    assert abs(got("fisim.ic_nfc_private") - want["pvt"]) <= 0.01
    assert abs(got("fisim.ic_households") - want["hh"]) <= 0.01


def test_gpf_union_groups_are_free_estimates_and_the_total_is_a_constraint(synthetic, entries):
    """V-FIN-2: the household split of the Union GPF interest rests on factors' estimated public-sector wage key,
    so the group entries are estimated/free/medium; the published total is the constraint r9c.gpf_union."""
    g = entries.filter(pl.col("component") == "gpf_union")
    assert g.height == 10 and set(g["row"]) == set(HH) and set(g["col"]) == {"G_CEN"}
    assert set(g["status"]) == {"estimated"} and set(g["role"]) == {"free"} and set(g["confidence"]) == {"medium"}
    cons = synthetic[0].constraints.filter(pl.col("constraint_id") == "r9c.gpf_union").row(0, named=True)
    assert abs(cons["target"] - clean("union_fiscal_fa_expenditure", "fa9.2049.03.104")) <= 1e-6
    assert abs(_sum(g) - cons["target"]) <= 0.01


def _dividend_checks(dm: pl.DataFrame, r7: dict[tuple[str, str], float], row_di: dict[str, float]) -> None:
    val = lambda sid: float(dm.filter(pl.col("series_id") == sid)["value"][0])  # noqa: E731
    # V-FIN-3: banks' total = the Union's R7 bank dividends / the Centre's share of ODC equity (FSF F51)
    share = fsf_avg("fc_odc", "liabilities", "f51", "gg_cen") / fsf_avg("fc_odc", "liabilities", "f51", "all")
    assert abs(val("total.e_bank") - r7[("G_CEN", "E_BANK")] / share) <= 0.01
    # E_NFPU: Centre + States' R7 over both shares
    pub = sum(fsf_avg("nfc_pub", "liabilities", "f51", c) for c in ("gg_cen", "gg_sta"))
    want = (r7[("G_CEN", "E_NFPU")] + r7[("G_STA", "E_NFPU")]) / (pub / fsf_avg("nfc_pub", "liabilities", "f51", "all"))
    assert abs(val("total.e_nfpu") - want) <= 0.01
    for iss in ("e_nfpu", "e_nfpr", "e_bank", "e_nbfc", "e_insp"):
        parts = dm.filter(pl.col("series_id").str.starts_with(f"div.{iss}."))
        # V-FIN-6: government parts are R7 as booked (0 where government books none, e.g. private NBFCs) ...
        for g in ("G_CEN", "G_STA"):
            assert abs(val(f"div.{iss}.{g.lower()}") - r7.get((g, iss.upper()), 0.0)) <= 1e-6, (iss, g)
        # ... and the holder parts add up to the issuer total
        assert abs(float(parts["value"].sum()) - val(f"total.{iss}")) <= 0.01, iss
        assert abs(val(f"memo.r14_di_distributed.{iss}") - row_di.get(iss.upper(), 0.0)) <= 1e-6
    assert set(dm.filter(pl.col("holder") == "ROW")["treatment"].to_list()) >= {
        "memo: FSF share, not a SAM flow (rest_of_world writes R14)"
    }


def test_dividend_grossing_and_government_parts_synthetic(synthetic):
    valid, deps = synthetic
    r7 = {k: q.v for k, q in deps.r7.items()}
    _dividend_checks(valid.satellites["dividend_matrix"][1], r7, {})


def test_dividend_grossing_and_government_parts_built(built):
    ge = pl.read_parquet(PATHS.entries("government")).filter(pl.col("ref") == "R7")
    r7: dict[tuple[str, str], float] = {}
    for r in ge.iter_rows(named=True):
        r7[(r["row"], r["col"])] = r7.get((r["row"], r["col"]), 0.0) + r["value"]
    re_ = pl.read_parquet(PATHS.entries("rest_of_world")).filter(
        (pl.col("ref") == "R14") & (pl.col("component") == "di_distributed")
    )
    row_di = {c: float(g["value"].sum()) for (c,), g in re_.group_by(["col"], maintain_order=True)}
    dm = pl.read_parquet(PATHS.satellites("fincorp") / "dividend_matrix.parquet")
    _dividend_checks(dm, r7, row_di)
    # no R8 entry from an issuer goes to government (R7 is the government block's)
    assert built.filter((pl.col("ref") == "R8") & pl.col("row").is_in(["G_CEN", "G_STA"])).height == 0


def test_interest_on_government_held_fc_debt_is_written(synthetic, entries):
    """V-FIN-4: GG's FSF holdings of bank bonds/borrowings and of NBFC bonds/loans earn R4 interest (low
    confidence), inside the lender P&L scaling; every such FSF position has its entry."""
    sat = synthetic[0].satellites["interest_fisim_bridge"][1]
    for g, cp in (("G_CEN", "gg_cen"), ("G_STA", "gg_sta")):
        for debt, sec in (("E_BANK", "fc_odc"), ("E_NBFC", "fc_ofc")):
            for inst, f in (("bonds", "f3"), ("borrowings", "f4")):
                stock = fsf_avg(sec, "liabilities", f, cp)
                if sec == "fc_ofc":
                    stock -= fsf_avg("fc_ofc_icpf", "liabilities", f, cp) + fsf_avg("fc_ofc_mf", "liabilities", f, cp)
                e = entries.filter(
                    (pl.col("ref") == "R4")
                    & (pl.col("row") == g)
                    & (pl.col("col") == debt)
                    & (pl.col("component") == inst)
                )
                if stock <= 0:
                    assert e.height == 0
                    continue
                assert e.height == 1 and e["confidence"][0] == "low", (g, debt, inst)
                base = f"pos.{g.lower()}.{debt.lower()}.{inst}"
                s = float(sat.filter(pl.col("series_id") == f"{base}.stock")["value"][0])
                assert abs(s - stock) <= 1e-3
    gg = entries.filter((pl.col("ref") == "R4") & pl.col("row").is_in(["G_CEN", "G_STA"]))
    assert set(gg["confidence"]) == {"low"}  # deposits too (V-FIN-7: possible overlap with government's R7x)


def test_bank_public_share_and_its_proxy_are_published(synthetic):
    """V-FIN-8: the deposit-taking NBFC/HFC profit proxy behind E_BANK's public share, recomputed from RTP."""
    sat = synthetic[0].satellites["fc_public_private"][1]
    val = lambda sid: float(sat.filter(pl.col("series_id") == sid)["value"][0])  # noqa: E731
    N, B, C = "rbi_banking_corporate_rtp_nbfi", "rbi_banking_corporate_rtp_banks", "rbi_banking_corporate_rtp_coop"
    rtp = lambda ds, s: clean(ds, s, vintage="2025-12-29")  # noqa: E731
    pbt = sum(rtp(N, f"rtp.nbfc_layer_pl.profit_before_tax.{g}.current") for g in ("nbfc_ul", "nbfc_ml"))
    hfc = (
        rtp(N, "rtp.hfc_pl.fund_income.hfc.current")
        + rtp(N, "rtp.hfc_pl.fee_income.hfc.current")
        - rtp(N, "rtp.hfc_pl.financial_expenditure.hfc.current")
        - rtp(N, "rtp.hfc_pl.operating_expenditure.hfc.current")
    )
    proxy = val("input.dt_share_nbfc") * pbt + val("input.dt_share_hfc") * hfc
    assert abs(val("input.dt_profit_proxy") - proxy) <= 0.01
    op = lambda ds, s, g: rtp(ds, f"rtp.{s}.operating_profit.{g}.current")  # noqa: E731
    banks = (op(B, "scb_pl", "scb") + op(B, "rrb_pl", "rrb") + op(C, "ucb_pl", "ucb") + op(C, "stcb_pl", "stcb")) + op(
        C, "dccb_pl", "dccb"
    )
    public = op(B, "scb_pl", "psb") + op(B, "rrb_pl", "rrb")
    assert abs(val("input.bank_public_share") - public / (banks + proxy)) <= 1e-6
    assert abs(val("input.bank_public_share_banks_only") - public / banks) <= 1e-6


# ---------------------------------------------------------------------------------------------
# repair of 2026-10-01 (DECISIONS D2-21; fincorp-2, fincorp-4, fincorp-11, fincorp-27..30)
# ---------------------------------------------------------------------------------------------

OLD22 = "mospi_nas_2026_oldbase_soa_s2_2"
D4_REFS = ("R3a", "R4", "R5", "R8", "R8a")


def _old22(item: str, period: str = "2022-23") -> float:
    return clean(OLD22, f"oldbase_soa_s2_2.{item}.current", period=period)


def _e_nfpr_net_d4(e: pl.DataFrame, deps: Deps) -> float:
    """E_NFPR's net property income over fincorp's entries (intra-account flows cancel) and the dependency flows."""
    d4 = e.filter(
        pl.col("ref").is_in(D4_REFS) | ((pl.col("ref") == "R17") & (pl.col("component") == "premium_supplement"))
    )
    recv = _sum(d4.filter((pl.col("row") == "E_NFPR") & (pl.col("col") != "E_NFPR")))
    paid = _sum(d4.filter((pl.col("col") == "E_NFPR") & (pl.col("row") != "E_NFPR")))
    row = (
        deps.row_sum(row="E_NFPR", col="R_ROW", refs=("R13",)).v
        - deps.row_sum(row="R_ROW", col="E_NFPR", refs=("R14", "R14a")).v
    )
    gov = sum(q.v for (_, c), q in {**deps.r7, **deps.r7x}.items() if c == "E_NFPR")
    return recv - paid + row - gov


def test_oldbase_topup_brings_private_nfc_net_d4_to_the_old_base_prior(synthetic):
    """D2-21: E_NFPR's net D4 over every SAM entry = old-base NAS 2024 St 2.2 2022-23 (D4 resources - uses) /
    (NOS + CFC) x the new-base GOS; the top-up is R8/R8a 'distributed_income', estimated / free / low, and reaches
    no government, RBI, RoW or (directly) private-NFC holder."""
    valid, deps = synthetic
    e = valid.entries
    ratio = (_old22("allocation_of_primary_income.resources.d4") - _old22("allocation_of_primary_income.uses.d4")) / (
        _old22("allocation_of_primary_income.resources.b2n_b3n") + _old22("production.uses.p51c")
    )
    prior = ratio * FIX_NFC_GOS["E_NFPR"]
    assert abs(_e_nfpr_net_d4(e, deps) - prior) <= 0.05
    top = e.filter(pl.col("component").str.starts_with("distributed_income"))
    assert top.height > 0 and set(top["col"]) == {"E_NFPR"}
    assert set(top["ref"]) == {"R8", "R8a"}
    assert set(top["status"]) == {"estimated"} and set(top["role"]) == {"free"} and set(top["confidence"]) == {"low"}
    assert not set(top["row"]) & {"G_CEN", "G_STA", "E_RBI", "R_ROW"}
    assert top.filter(pl.col("row") == "E_NFPR")["component"].to_list() == ["distributed_income_mf"]
    assert set(top.filter(pl.col("ref") == "R8a")["row"]) == set(HH)
    # direct holders by FSF F51 shares of private NFC equity (households vs public NFCs, same denominator)
    hh = _sum(top.filter((pl.col("ref") == "R8a") & (pl.col("component") == "distributed_income")))
    pu = _sum(top.filter(pl.col("row") == "E_NFPU"))
    want = fsf_avg("nfc_pvt", "liabilities", "f51", "hh") / fsf_avg("nfc_pvt", "liabilities", "f51", "nfc_pub")
    assert abs(hh / pu - want) <= 1e-6
    dm = valid.satellites["dividend_matrix"][1]
    val = lambda sid: float(dm.filter(pl.col("series_id") == sid)["value"][0])  # noqa: E731
    assert abs(val("oldbase.param.net_d4_to_gos") - ratio) <= 1e-9
    assert abs(val("oldbase.e_nfpr.after.net") - prior) <= 0.05
    assert (
        abs(
            val("oldbase.e_nfpr.total")
            - _sum(top.filter(pl.col("row") != "E_NFPR"))
            - _sum(top.filter(pl.col("row") == "E_NFPR"))
        )
        <= 0.05
    )


def test_oldbase_topup_built_uses_government_r7x_and_the_factors_gos(built):
    """Built: the prior uses factors' E_NFPR GOS and the net D4 counts government's R7x paid by E_NFPR."""
    dm = pl.read_parquet(PATHS.satellites("fincorp") / "dividend_matrix.parquet")
    val = lambda sid: float(dm.filter(pl.col("series_id") == sid)["value"][0])  # noqa: E731
    gos = _sum(pl.read_parquet(PATHS.entries("factors")), row="E_NFPR", col="F_GOSC")
    assert abs(val("oldbase.e_nfpr.prior_net_d4") - val("oldbase.param.net_d4_to_gos") * gos) <= 0.01
    r7x = _sum(pl.read_parquet(PATHS.entries("government")), ref=["R7", "R7x"], col="E_NFPR")
    assert r7x > 0 and abs(val("oldbase.e_nfpr.before.gov_r7_r7x_paid") + r7x) <= 0.01
    assert abs(val("oldbase.e_nfpr.after.net") - val("oldbase.e_nfpr.prior_net_d4")) <= 0.05


def test_ofc_claims_on_banks_follow_the_creditors_mix(synthetic):
    """fincorp-4: OFC claims on E_BANK = the ODC-side total over deposits, debt securities and borrowings, split
    over NBFCs / insurers-PFs / MFs and instruments by the OFC sub-sectors' own FSF claims on ODCs."""
    sat = synthetic[0].satellites["interest_fisim_bridge"][1]
    insts = {"deposits": "f22_f29", "bonds": "f3", "borrowings": "f4"}
    odc = sum(fsf_avg("fc_odc", "liabilities", f, "fc_ofc") for f in insts.values())
    claim = {}
    for inst, f in insts.items():
        icpf, mf = fsf_avg("fc_ofc_icpf", "assets", f, "fc_odc"), fsf_avg("fc_ofc_mf", "assets", f, "fc_odc")
        nb = fsf_avg("fc_ofc", "assets", f, "fc_odc") - icpf - mf
        for acct, v in (("e_nbfc", nb), ("e_insp", icpf), ("mf", mf)):
            claim[(acct, inst)] = max(v, 0.0)
    tot = sum(claim.values())
    got = sat.filter(pl.col("series_id").str.contains(r"^pos\.(e_nbfc|e_insp|mf)\.e_bank\..*\.stock$"))
    assert abs(float(got["value"].sum()) - odc) <= 0.01
    for (acct, inst), v in claim.items():
        row = got.filter(pl.col("series_id") == f"pos.{acct}.e_bank.{inst}.stock")
        assert (row.height == 0 and v == 0) or abs(float(row["value"][0]) - odc * v / tot) <= 0.01, (acct, inst)


def test_fisim_lender_split_follows_reference_rate_margins(synthetic):
    """fincorp-2: each user's FISIM is split between E_BANK and E_NBFC by the reference-rate margin of each
    lender's position (loans: interest - r* x stock; deposits: r* x stock - interest), SNA 2008 6.166."""
    sat = synthetic[0].satellites["interest_fisim_bridge"][1]
    val = lambda sid: float(sat.filter(pl.col("series_id") == sid)["value"][0])  # noqa: E731
    r_star = clean("rbi_banking_corporate_rtp_banks", "rtp.scb_cost_return.return_on_investments.scb") / 100
    for sector, side, inst in (("e_nfpr", "L", "loans"), ("e_nfpu", "L", "loans"), ("hh", "L", "loans")):
        m = {}
        for lend in ("e_bank", "e_nbfc"):
            base = f"pos.{lend}.{sector}.{inst}"
            m[lend] = max(val(f"{base}.bank_interest") - r_star * val(f"{base}.stock"), 0.0)
        for lend in m:
            assert abs(val(f"fisim.lender_share.{sector}.{side}.{lend}") - m[lend] / sum(m.values())) <= 1e-9
    fl = {k: val(f"fisim.by_lender.{k}") for k in ("e_bank", "e_nbfc")}
    assert (
        abs(
            sum(fl.values())
            - val("fisim.pfce")
            - sum(val(f"fisim.ic_{k}") for k in ("households", "nfc_public", "nfc_private"))
        )
        <= 1.0
    )


def test_insp_investment_income_memo(synthetic):
    """fincorp-2 (E_INSP): the memo compares the administrative investment income behind D44 and R17 with the
    SAM's R3a + R4 + R5 + R8 receipts of E_INSP."""
    valid, _ = synthetic
    d = valid.satellites["d44_by_scheme"][1]
    val = lambda sid: float(d.filter(pl.col("series_id") == sid)["value"][0])  # noqa: E731
    irl = "finsector_markets_irdai_life"
    life_sh = clean(irl, "t25.inv_interest_dividends_rent_gross.insurers_life.current") + clean(
        irl, "t25.inv_amortisation.insurers_life.current"
    )
    assert abs(val("memo.insp_income.life_shareholders") - life_sh) <= 0.01
    nonlife = clean("finsector_markets_irdai_summary", "sum_c.investment_income.current")
    assert abs(val("memo.insp_income.nonlife") - nonlife) <= 0.01
    parts = ("life_policyholders", "life_shareholders", "nonlife", "pf_pension_d44")
    assert abs(val("memo.insp_income.admin_total") - sum(val(f"memo.insp_income.{k}") for k in parts)) <= 0.01
    sam = _sum(valid.entries.filter(pl.col("col") != "E_INSP"), row="E_INSP", ref=["R3a", "R4", "R5", "R8"])
    assert abs(val("memo.insp_income.sam_receipts") - sam) <= 0.01
    assert abs(val("memo.insp_income.shortfall") - (val("memo.insp_income.admin_total") - sam)) <= 0.01


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------


def test_tracked_numbers_union_their_inputs():
    a, b = Q(2.0, frozenset({"x"})), Q(3.0, frozenset({"y"}))
    assert (a * b + 1).v == 7.0 and (a * b + 1).p == {"x", "y"}
    assert qsum([a, b]).v == 5.0
    s = shares({"p": a, "q": b})
    assert s["p"].v == pytest.approx(0.4) and s["p"].p == {"x", "y"}


def test_collector_drops_zeros_and_rejects_wrong_signs():
    ctx = BlockContext(block="fincorp", refs=tuple(fincorp.REFS), depends=(), layout=LAYOUT)
    out = Out(ctx)
    out.method("t", "R4", "estimated", "TEST METHOD for the collector unit test (no data)")
    out.add("E_BANK", "E_NBFC", "loans", Q(0.0), key="t", role="free", confidence="low")
    assert out.items == [] and out.dropped
    with pytest.raises(Exception, match="wrong sign"):
        out.add("E_BANK", "E_NBFC", "loans", Q(-1.0), key="t", role="free", confidence="low")
