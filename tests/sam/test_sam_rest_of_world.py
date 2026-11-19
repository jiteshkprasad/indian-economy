"""The rest_of_world block: its built outputs validate, match a fresh rebuild, and reproduce NAS 2026 St 6.1 / 1.9
and the RBI BoP (plan docs/phase2/plans/rest_of_world.md s.7). Every expected value is recomputed here from
data/clean with polars, never typed in. Pure helpers are tested on small fixtures."""

from __future__ import annotations

import glob
import math

import polars as pl
import pytest

from pipeline.core.io import canonical_floats
from pipeline.core.paths import Layout
from pipeline.sam import spec
from pipeline.sam.accounts import Accounts
from pipeline.sam.blocks import rest_of_world
from pipeline.sam.blocks.rest_of_world import _common as c
from pipeline.sam.framework import SamError, SamPaths, _sig, build_block_module

pytestmark = pytest.mark.sam

LAYOUT = Layout.default()
PATHS = SamPaths(LAYOUT)
YEAR = spec.YEAR
BLOCK = "rest_of_world"
TOL = 1e-4  # Rs crore: entries are written rounded to 6 decimals; sums of up to ~100 of them
HH = ["H_R1", "H_R2", "H_R3", "H_R4", "H_R5", "H_U1", "H_U2", "H_U3", "H_U4", "H_U5"]


# --------------------------------------------------------------------------------------------------
# reading clean data in the test itself
# --------------------------------------------------------------------------------------------------


def _dataset(name: str) -> pl.DataFrame:
    (f,) = glob.glob(str(LAYOUT.clean / "*" / f"{name}.parquet"))
    return pl.read_parquet(f)


def cv(dataset: str, sid: str, period: str = YEAR, vintage: str | None = None) -> float:
    """One clean value (the latest vintage of that series and period unless named)."""
    df = _dataset(dataset).filter((pl.col("series_id") == sid) & (pl.col("period") == period))
    df = df.filter(pl.col("vintage") == (vintage or df["vintage"].max()))
    assert df.height == 1, (dataset, sid, period, vintage, df.height)
    return float(df["value"][0])


def nas61(item: str) -> float:
    return cv("mospi_nas_2026_s6_1", f"s6_1.{item}.current")


def bpm6(item: str) -> float:
    return cv("external_sector_bop_bpm6_annual", f"bpm6.inr.{item}.current")


def old(path: str) -> float:
    return cv("external_sector_bop_overall_annual", f"bop_old.inr.{path}.net.current")


# --------------------------------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def built() -> pl.DataFrame:
    if not PATHS.built(BLOCK):
        pytest.fail("rest_of_world block not built: run `uv run python -m pipeline sam rest_of_world`")
    return pl.read_parquet(PATHS.entries(BLOCK))


@pytest.fixture(scope="module")
def cons() -> pl.DataFrame:
    return pl.read_parquet(PATHS.constraints(BLOCK))


@pytest.fixture(scope="module")
def prov() -> pl.DataFrame:
    return pl.read_parquet(PATHS.provenance(BLOCK))


@pytest.fixture(scope="module")
def sat():
    def read(name: str) -> pl.DataFrame:
        return pl.read_parquet(PATHS.satellites(BLOCK) / f"{name}.parquet")

    return read


@pytest.fixture(scope="module")
def fresh():
    r, valid = build_block_module(rest_of_world, LAYOUT, write=False)
    assert r.ok, r.message
    return valid


def _sum(df: pl.DataFrame, **eq) -> float:
    for k, v in eq.items():
        df = df.filter(pl.col(k).is_in(v) if isinstance(v, (list, tuple)) else pl.col(k) == v)
    return float(df["value"].sum())


# --------------------------------------------------------------------------------------------------
# the files are what the code builds; checks pass
# --------------------------------------------------------------------------------------------------


def test_built_outputs_equal_a_fresh_build(built, cons, prov, fresh, sat):
    want = canonical_floats(fresh.entries, {"value": 6, "tol_rel": None}).sort(list(spec.ENTRY_KEY))
    assert built.drop("block").equals(want)
    assert cons.drop("block").equals(canonical_floats(fresh.constraints).sort("constraint_id"))
    assert prov.equals(fresh.provenance.sort("prov_id"))
    for name, (s, df) in fresh.satellites.items():
        # the framework caps satellite values at 12 significant digits on write (framework._sig, Wave C repro)
        df = df.with_columns(pl.Series("value", [_sig(v, s.decimals) for v in df["value"].to_list()],
                                       dtype=pl.Float64))  # fmt: skip
        assert sat(name).equals(canonical_floats(df, {"value": s.decimals}).sort("series_id")), name


def test_every_control_total_check_passes(fresh):
    failed = fresh.checks.filter(~pl.col("ok"))
    assert failed.height == 0, failed
    assert fresh.checks.height >= 25


# --------------------------------------------------------------------------------------------------
# plan s.7: 1-2 current transfers
# --------------------------------------------------------------------------------------------------


def test_remittances_r11a(built, cons):
    r11a = built.filter(pl.col("ref") == "R11a")
    target = nas61("other_current_transfers_to_resident_sectors_other_than_gener")
    assert _sum(r11a) == pytest.approx(target, abs=TOL)
    assert _sum(r11a) == pytest.approx(bpm6("bpm6_1_c_1.credit"), abs=1.0)
    assert _sum(r11a) == pytest.approx(
        cv("external_sector_invisibles_annual", "invis.inr.private_transfers.receipts.current"), abs=1.0
    )
    assert sorted(r11a["row"]) == HH and (r11a["value"] >= 0).all()
    assert set(r11a["role"]) == {"free"} and set(r11a["confidence"]) == {"low"} and set(r11a["status"]) == {"estimated"}
    c11 = cons.filter(pl.col("constraint_id") == "row.r11_total")
    assert c11["target"].item() == pytest.approx(target, abs=TOL) and c11["refs"].item() == "R11a"


def test_remittance_survey_shares_sum_to_100():
    s = _dataset("external_sector_remittance_survey").filter(
        (pl.col("period") == YEAR)
        & pl.col("series_id").str.starts_with("remit.destination_state.")
        & (pl.col("vintage") == c.V_REMIT)
    )
    assert s.height == 36
    assert s["value"].sum() == pytest.approx(100.0, abs=0.05)


def test_r11a_reproduces_survey_x_state_key(built):
    """Independent recomputation of R11a: survey State shares x households' State consumption key."""
    s = (
        _dataset("external_sector_remittance_survey")
        .filter(
            (pl.col("period") == YEAR)
            & pl.col("series_id").str.starts_with("remit.destination_state.")
            & (pl.col("vintage") == c.V_REMIT)
        )
        .with_columns(pl.col("series_id").str.split(".").list.get(2).str.to_uppercase().alias("geography"))
    )
    s = s.with_columns((pl.col("value") / pl.col("value").sum()).alias("s"))
    xw = pl.read_parquet(PATHS.satellites("households") / "hh_state_xwalk.parquet").filter(
        (pl.col("measure") == "consumption") & (pl.col("hces_class") == "all")
    )
    xw = xw.with_columns((pl.col("value") / pl.col("value").sum().over("geography")).alias("w"))
    # each State's weights over groups sum to 1
    assert xw.group_by("geography", maintain_order=True).agg(pl.col("w").sum())["w"].to_list() == pytest.approx(
        [1.0] * xw["geography"].n_unique()
    )
    j = xw.join(s.select("geography", "s"), on="geography", how="inner")
    total = nas61("other_current_transfers_to_resident_sectors_other_than_gener")
    exp = j.group_by("household_group", maintain_order=True).agg((pl.col("s") * pl.col("w")).sum() * total)
    got = dict(built.filter(pl.col("ref") == "R11a").select("row", "value").iter_rows())
    for g, x in exp.iter_rows():
        assert got[g] == pytest.approx(x, abs=TOL), g


def test_r11a_per_capita_rises_with_the_quintile(built):
    """Plan s.2.1 step 5 (qualitative): remittances per person rise with the quintile within each area."""
    keys = pl.read_parquet(PATHS.satellites("households") / "hh_keys.parquet").filter(
        (pl.col("key") == "pop_persons") & (pl.col("measure") == "level")
    )
    pop = dict(keys.select("household_group", "value").iter_rows())
    r = dict(built.filter(pl.col("ref") == "R11a").select("row", "value").iter_rows())
    for area in ("R", "U"):
        pc = [r[f"H_{area}{q}"] / pop[f"H_{area}{q}"] for q in range(1, 6)]
        assert pc == sorted(pc), (area, pc)


def test_r11a_sensitivity_band(built, sat):
    """Plan s.6 (remittance-survey caveats): the band holds three allocations of the same total; the prior is the
    R11a entries; consumption_only is R11 x each group's share of all-India consumption (recomputed here)."""
    s = sat("r11a_sensitivity")
    total = nas61("other_current_transfers_to_resident_sectors_other_than_gener")
    prior = dict(built.filter(pl.col("ref") == "R11a").select("row", "value").iter_rows())
    val = {(r["variant"], r["household_group"]): r["value"] for r in s.iter_rows(named=True)}
    for var in ("prior", "hub_neutral", "consumption_only"):
        assert sum(val[(var, g)] for g in HH) == pytest.approx(total, abs=TOL), var
    for g in HH:
        assert val[("prior", g)] == pytest.approx(prior[g], abs=TOL)
        vals = [val[(var, g)] for var in ("prior", "hub_neutral", "consumption_only")]
        assert val[("band_low", g)] == pytest.approx(min(vals), abs=TOL)
        assert val[("band_high", g)] == pytest.approx(max(vals), abs=TOL)
    xw = pl.read_parquet(PATHS.satellites("households") / "hh_state_xwalk.parquet").filter(
        (pl.col("measure") == "consumption") & (pl.col("hces_class") == "all")
    )
    by_g = xw.group_by("household_group", maintain_order=True).agg(pl.col("value").sum())
    tot_c = float(by_g["value"].sum())
    for g, x in by_g.iter_rows():
        assert val[("consumption_only", g)] == pytest.approx(total * x / tot_c, abs=1e-3), g
    # removing the State information makes R11a less top-heavy
    top = ("H_R5", "H_U5")
    assert sum(val[("consumption_only", g)] for g in top) < sum(val[("prior", g)] for g in top)


def test_r12a_sensitivity(built, sat):
    s = sat("r12a_sensitivity")
    val = {(r["variant"], r["household_group"]): r["value"] for r in s.iter_rows(named=True)}
    target = nas61("other_current_transfers_by_resident_sectors_other_than_gener")
    alt = {g: val[("other_transfers_all_groups", g)] for g in HH}
    assert sum(alt.values()) == pytest.approx(target, abs=TOL)
    # the 1.C.1.2 part on H_R1..H_U3 is spread by pfce_total
    keys = pl.read_parquet(PATHS.satellites("households") / "hh_keys.parquet").filter(
        (pl.col("key") == "pfce_total") & (pl.col("measure") == "level")
    )
    lv = dict(keys.select("household_group", "value").iter_rows())
    oct_db = bpm6("bpm6_1_c_1_2.debit")
    tot = sum(lv[g] for g in HH)
    for g in HH[:8]:
        assert alt[g] == pytest.approx(oct_db * lv[g] / tot, abs=1e-3), g
    got = dict(built.filter(pl.col("ref") == "R12a").select("col", "value").iter_rows())
    for g in ("H_U4", "H_U5"):
        assert val[("prior", g)] == pytest.approx(got[g], abs=TOL)


def test_outward_transfers_r12a(built):
    r12a = built.filter(pl.col("ref") == "R12a")
    target = nas61("other_current_transfers_by_resident_sectors_other_than_gener")
    assert _sum(r12a) == pytest.approx(target, abs=TOL)
    assert _sum(r12a) == pytest.approx(bpm6("bpm6_1_c_1.debit"), abs=1.0)
    assert sorted(r12a["col"]) == ["H_U4", "H_U5"] and set(r12a["row"]) == {"R_ROW"}
    keys = pl.read_parquet(PATHS.satellites("households") / "hh_keys.parquet").filter(
        (pl.col("key") == "pfce_total") & (pl.col("measure") == "level")
    )
    lv = dict(keys.select("household_group", "value").iter_rows())
    got = dict(r12a.select("col", "value").iter_rows())
    assert got["H_U4"] / got["H_U5"] == pytest.approx(lv["H_U4"] / lv["H_U5"], abs=TOL)


# --------------------------------------------------------------------------------------------------
# 3-5 property income
# --------------------------------------------------------------------------------------------------


def test_property_income_received_r13(built):
    r13 = built.filter(pl.col("ref") == "R13")
    assert _sum(r13) == pytest.approx(nas61("property_and_entrepreneurial_income_from_rest_of_the_world"), abs=TOL)
    assert set(r13["col"]) == {"R_ROW"}
    for comp, item in (
        ("di_income", "bpm6_1_b_2_1"),
        ("pi_income", "bpm6_1_b_2_2"),
        ("oi_income", "bpm6_1_b_2_3"),
        ("other_primary_income", "bpm6_1_b_3"),
    ):
        assert _sum(r13, component=comp) == pytest.approx(bpm6(f"{item}.credit"), abs=1.0), comp
    # E_RBI in two components (DECISIONS D2-7): RBI AR reserve income anchored 2% + the unexplained excess
    ar = cv("rbi_banking_corporate_rbi_accounts", "sch13.b.sub_total.current", vintage=c.V_RBI_AR) + cv(
        "rbi_banking_corporate_rbi_accounts",
        "sch14.b.amortisation_of_premium_discount_on_foreign_securities.current",
        vintage=c.V_RBI_AR,
    )
    rai = r13.filter(pl.col("component") == "reserve_asset_income")
    unx = r13.filter(pl.col("component") == "reserve_income_unexplained")
    assert rai["row"].item() == "E_RBI" and rai["value"].item() == pytest.approx(ar, abs=TOL)
    assert rai["role"].item() == "anchored" and rai["tol_rel"].item() == pytest.approx(0.02)
    assert unx["row"].item() == "E_RBI" and unx["role"].item() == "free" and unx["confidence"].item() == "low"
    assert rai["value"].item() + unx["value"].item() == pytest.approx(bpm6("bpm6_1_b_2_4.credit"), abs=TOL)


def test_property_income_paid_r14_r14a(built):
    r14 = built.filter(pl.col("ref").is_in(["R14", "R14a"]))
    total = nas61("property_and_entrepreneurial_income_to_the_rest_of_the_world")
    assert _sum(r14) == pytest.approx(total, abs=TOL)
    assert _sum(r14) == pytest.approx(
        cv("external_sector_invisibles_annual", "invis.inr.income.investment.payments.current"), abs=1.0
    )
    assert set(r14["row"]) == {"R_ROW"}
    # DI debit = distributed (R14) + reinvested (R14a)
    di = _sum(r14, component=["di_distributed", "reinvested_earnings"])
    assert di == pytest.approx(bpm6("bpm6_1_b_2_1.debit"), abs=1.0)
    for comps, item in (
        (["fpi_gsec_interest", "fpi_tbill_interest", "fpi_sdl_interest", "pi_other"], "bpm6_1_b_2_2"),
        (["ext_assistance_interest", "nri_deposit_interest", "oi_other_interest"], "bpm6_1_b_2_3"),
        (["reserve_asset_debit"], "bpm6_1_b_2_4"),
        (["other_primary_income"], "bpm6_1_b_3"),
    ):
        assert _sum(r14, component=comps) == pytest.approx(bpm6(f"{item}.debit"), abs=1.0), item
    ea = r14.filter(pl.col("component") == "ext_assistance_interest")
    assert ea["col"].item() == "G_CEN" and ea["role"].item() == "anchored"
    assert ea["value"].item() == pytest.approx(cv("union_fiscal_fa_expenditure", "fa9.2049.02.total"), abs=TOL)


def test_fpi_interest_on_government_paper_uses_fincorps_formula(built):
    """XR-12: average T107 FPI share x the payer line (market loans net of re-issue receipts)."""

    def share(inst: str) -> float:
        return (
            sum(
                cv("rbi_financial_accounts_hbs_gsec_ownership", f"t107.{inst}.share.fpi", period=d)
                for d in c.STOCK_DATES
            )
            / 200.0
        )

    ml = cv("union_fiscal_fa_expenditure", "fa9.2049.01.101") - sum(
        cv("union_fiscal_fa_receipts", s) for s in ("fa8.0049.03.116", "fa8.0049.03.117")
    )
    tb = sum(cv("union_fiscal_fa_expenditure", s) for s in ("fa9.2049.01.103", "fa9.2049.01.108", "fa9.2049.01.110"))
    sdl = cv(
        "state_fiscal_rbi_sf_appendices",
        "app2.total_expenditure.ii.c.2.ii.a-interest_on_market_loans.in.all_states_uts.actuals",
    )
    got = dict(built.filter(pl.col("ref") == "R14").select("component", "value").iter_rows())
    assert got["fpi_gsec_interest"] == pytest.approx(share("gsec_central") * ml, abs=TOL)
    assert got["fpi_tbill_interest"] == pytest.approx(share("tbills") * tb, abs=TOL)
    assert got["fpi_sdl_interest"] == pytest.approx(share("sgs") * sdl, abs=TOL)


def test_reinvested_earnings(built):
    r14a = built.filter(pl.col("ref") == "R14a")
    re_ = cv("mospi_nas_2026_s1_9", "s1_9.reinvested_earnings_of_foreign_companies_in_private_corporat.current")
    assert _sum(r14a) == pytest.approx(re_, abs=TOL)
    assert _sum(r14a) == pytest.approx(bpm6("bpm6_3_1_a_1_2.credit"), abs=1.0)
    assert set(r14a["bop_function"]) == {"FDI_reinvested_earnings"}
    k8b_re = built.filter((pl.col("ref") == "K8b") & (pl.col("component") == "fdi_reinvested_earnings"))
    assert k8b_re["value"].item() == pytest.approx(_sum(r14a), abs=TOL)
    odi_re = built.filter((pl.col("ref") == "K8b") & (pl.col("component") == "odi_reinvested_earnings"))
    assert odi_re["value"].item() == pytest.approx(bpm6("bpm6_3_1_b_1_2.debit"), abs=TOL)
    # payer split: NFC share from the FLA 2023-24 round t8 market-value equity
    fin = cv("external_sector_fla_census", "fla.t8.g.financial_and_insurance_activities.equity", "2024-03-31", c.V_FLA)
    tot = cv("external_sector_fla_census", "fla.t8.total.equity", "2024-03-31", c.V_FLA)
    nfc = _sum(r14a, col="E_NFPR")
    assert nfc / _sum(r14a) == pytest.approx(1 - fin / tot, abs=TOL)
    assert _sum(r14a, col=["E_NFPU", "E_INSP"]) == 0.0


# --------------------------------------------------------------------------------------------------
# 6-7 K5 and D2
# --------------------------------------------------------------------------------------------------


def test_k5_rest_of_world_saving(built):
    k5 = built.filter(pl.col("ref") == "K5")
    assert k5.select("row", "col", "role").row(0) == ("K_ROW", "R_ROW", "fixed")
    nci = cv("mospi_nas_2026_s1_9", "s1_9.net_capital_inflow_from_row.current")
    assert k5["value"].item() == pytest.approx(nci, abs=TOL)
    assert k5["value"].item() == pytest.approx(-nas61("surplus_on_current_transactions"), abs=0.01)
    # NAS vs BoP: the difference is exactly BoP 1.C.2 government transfers (external_sector-5)
    assert k5["value"].item() + bpm6("bpm6_1.net") == pytest.approx(bpm6("bpm6_1_c_2.net"), abs=1.0)


def test_d2_cif_reconciliation(built):
    d2 = built.filter(pl.col("ref") == "D2")
    assert d2.select("row", "col", "role", "status").row(0) == ("R_ROW", "X_DISC", "fixed", "official")
    cif = cv("io_tables_sut_supply", "supply.cif_adj.cif.current")
    assert d2["value"].item() == pytest.approx(cif, abs=TOL)
    imp = cv("io_tables_sut_supply", "supply.imports.total.current")
    after = cv("io_tables_sut_supply", "supply.imports_after_cif.total.current")
    assert imp - after == pytest.approx(cif, abs=0.01)
    assert abs(cif - nas61("adjustment_for_cif_in_import_of_services")) <= 1.0
    p6 = pl.read_parquet(PATHS.entries("production")).filter(pl.col("ref") == "P6")["value"].sum()
    assert p6 + cif == pytest.approx(nas61("imports"), abs=0.01)


# --------------------------------------------------------------------------------------------------
# 8-9 the two RoW accounts close
# --------------------------------------------------------------------------------------------------


def test_r_row_closes_in_the_prior(built):
    """P5/P6 from production, V3/V4 from NAS 6.1 (factors writes them), this block's entries: row = column."""
    prod = pl.read_parquet(PATHS.entries("production"))
    p5 = prod.filter(pl.col("ref") == "P5")["value"].sum()
    p6 = prod.filter(pl.col("ref") == "P6")["value"].sum()
    v3 = nas61("compensation_of_employees_from_rest_of_the_world")
    v4 = nas61("compensation_of_employees_to_the_rest_of_the_world")
    row = p6 + v4 + _sum(built, row="R_ROW")
    col = p5 + v3 + _sum(built, col="R_ROW")
    assert row - col == pytest.approx(0.0, abs=0.01)
    assert row == pytest.approx(nas61("current_disbursements"), abs=1.0)
    assert col - _sum(built, ref="K5") == pytest.approx(nas61("current_receipts"), abs=1.0)


def test_r_row_closes_with_factors_v3_v4_if_built(built):
    """Integration: with factors' own V3/V4 entries (not the NAS values), R_ROW still closes in the prior."""
    if not PATHS.built("factors"):
        pytest.skip("factors block not built yet (integration check)")
    fac = pl.read_parquet(PATHS.entries("factors")).filter(pl.col("ref").is_in(["V3", "V4"]))
    prod = pl.read_parquet(PATHS.entries("production")).filter(pl.col("ref").is_in(["P5", "P6"]))
    allr = pl.concat([built.select("row", "col", "value"), fac.select("row", "col", "value"),
                      prod.select("row", "col", "value")])  # fmt: skip
    assert _sum(allr, row="R_ROW") - _sum(allr, col="R_ROW") == pytest.approx(0.0, abs=0.01)


def test_no_r15_entries_anywhere():
    """Government's current transfers with RoW are capital in NAS (K6); nobody writes R15 (integration)."""
    for f in sorted(PATHS.blocks.glob("*_entries.parquet")):
        e = pl.read_parquet(f)
        assert e.filter(pl.col("ref") == "R15").height == 0, f.name


def test_k_row_financial_account(built):
    inst = Accounts.load().in_group("INST")
    liab = built.filter((pl.col("ref") == "K8b") & (pl.col("col") == "K_ROW") & pl.col("row").is_in(inst))
    asset = built.filter((pl.col("ref") == "K8b") & (pl.col("row") == "K_ROW") & pl.col("col").is_in(inst))
    assert _sum(liab) == pytest.approx(nas61("net_incurrence_of_foreign_liabilities"), abs=1.0)
    assert _sum(asset) == pytest.approx(nas61("net_acquisition_of_foreign_financial_assets"), abs=1.0)
    nl = nas61("net_lending_to_the_rest_of_the_world_13_14_15_16_or_18_19")
    assert _sum(liab) - _sum(asset) == pytest.approx(-nl, abs=1.0)
    assert _sum(liab) - _sum(asset) == pytest.approx(-(bpm6("bpm6_1.net") + bpm6("bpm6_2.net")), abs=2.0)


def test_k_row_closes_with_nas_capital_transfers(built):
    """K_ROW row = column once the NAS 6.1 capital transfers with RoW (government's K6) are in. NPNFA is published
    +1,666.26 (India acquiring) and enters with a minus sign (CROSS_REVIEW XR-14)."""
    k6 = (
        nas61("capital_transfers_to_general_government_from_the_rest_of_the")
        + nas61("capital_transfers_to_corporations_households_and_npishs_net")
        - nas61("acquisitions_less_disposal_of_non_produced_non_financial_ass")
    )
    row = _sum(built, row="K_ROW")  # K5 + India's foreign assets
    col = _sum(built, col="K_ROW")  # India's foreign liabilities
    # k6 = net capital transfers received by India from RoW (negative: India pays 7,110.25); K_ROW's row lacks -k6
    assert row - col - k6 == pytest.approx(0.0, abs=0.01)


def test_k_row_closes_with_governments_k6_if_built(built):
    if not PATHS.built("government"):
        pytest.skip("government block not built yet (integration check)")
    gov = pl.read_parquet(PATHS.entries("government")).filter(pl.col("ref") == "K6")
    k6_row = _sum(gov, row="K_ROW")
    k6_col = _sum(gov, col="K_ROW")
    assert _sum(built, row="K_ROW") + k6_row - _sum(built, col="K_ROW") - k6_col == pytest.approx(0.0, abs=0.01)


# --------------------------------------------------------------------------------------------------
# 10-12 K8b reproduces the BoP; FPI debt; reserves
# --------------------------------------------------------------------------------------------------


def test_k8b_reproduces_the_bop(built):
    k = built.filter(pl.col("ref") == "K8b")
    assert _sum(k, component=["fdi_equity", "fdi_reinvested_earnings", "fdi_debt"]) == pytest.approx(
        bpm6("bpm6_3_1_a.net"), abs=1.0
    )
    assert _sum(k, component=["fpi_equity", "fpi_debt_gsec", "fpi_debt_corporate"]) == pytest.approx(
        bpm6("bpm6_3_2_a.net"), abs=2.0
    )
    assert _sum(k, component="nri_deposits") == old("ka.banking_capital.commercial_banks.nri_deposits")
    assert _sum(k, component=["odi_equity", "odi_reinvested_earnings", "odi_debt"]) == pytest.approx(
        -bpm6("bpm6_3_1_b.net"), abs=2.0
    )
    eo = _sum(k, component="errors_omissions")
    assert eo == pytest.approx(nas61("other_liabilities_to_non_residents"), abs=TOL)
    assert eo == pytest.approx(bpm6("bpm6_5.net"), abs=1.0)
    for comp in ("nas_reconciliation_liab", "nas_reconciliation_assets"):
        assert abs(_sum(k, component=comp)) <= 150.0
    tags = set(spec.BOP_FUNCTIONS)
    assert k["bop_function"].is_not_null().all() and set(k["bop_function"]) <= tags
    assert ((k["row"] == "K_ROW") | (k["col"] == "K_ROW")).all()
    # trade credit is I_OTHR (plan s.5 item 15), FPI/FDI equity I_EQTY, NRI deposits I_DEPO
    inst = dict(k.select("component", pl.when(pl.col("row") == "K_ROW").then("col").otherwise("row")).iter_rows())
    assert inst["short_term_trade_credit"] == "I_OTHR" and inst["nri_deposits"] == "I_DEPO"
    assert inst["fdi_equity"] == inst["fpi_equity"] == "I_EQTY" and inst["reserve_assets"] == "I_RESV"


def test_fpi_debt_split(built):
    k = built.filter(pl.col("ref") == "K8b")
    g = k.filter(pl.col("component") == "fpi_debt_gsec")
    cb = k.filter(pl.col("component") == "fpi_debt_corporate")
    assert (g["row"].item(), cb["row"].item()) == ("I_GSEC", "I_CBND")
    assert g["value"].item() + cb["value"].item() == pytest.approx(old("ka.portfolio.in_india.fiis.debt"), abs=TOL)
    held = 0.0
    for inst in ("gsec_central", "tbills", "sgs"):
        pos = [
            cv("rbi_financial_accounts_hbs_gsec_ownership", f"t107.{inst}.share.fpi", period=d)
            / 100.0
            * cv("rbi_financial_accounts_hbs_gsec_ownership", f"t107.{inst}.outstanding.current", period=d)
            for d in c.STOCK_DATES
        ]
        held += pos[1] - pos[0]
    assert g["value"].item() == pytest.approx(held, abs=1.0)
    sebi = cv("finsector_markets_sebi_foreign", "t60.net_investment.debt_general.current")
    assert abs(g["value"].item() - sebi) <= 0.03 * abs(sebi)


def test_reserves_k8c(built):
    k8c = built.filter(pl.col("ref") == "K8c")
    assert k8c.select("row", "col", "role").row(0) == ("I_RESV", "K_RBI", "fixed")
    res = bpm6("bpm6_3_5.debit")
    assert k8c["value"].item() == pytest.approx(res, abs=TOL)
    assert res == pytest.approx(
        cv(
            "rbi_financial_accounts_fsf_balance_sheets",
            "fsf.row.liabilities.transaction.f3.fc_rbi.current",
            vintage=c.V_FSF,
        ),
        abs=1.0,
    )
    q = _dataset("external_sector_bop_bpm6_quarterly").filter(
        (pl.col("series_id") == "bpm6q.inr.bpm6_3_5.net.current") & pl.col("period").str.ends_with(YEAR)
    )
    q = q.filter(pl.col("vintage") == q["vintage"].max())
    assert q.height == 4 and -q["value"].sum() == pytest.approx(res, abs=1.0)
    # I_RESV clears inside the block
    assert _sum(built, row="I_RESV") == pytest.approx(_sum(built, col="I_RESV"), abs=1e-9)


# --------------------------------------------------------------------------------------------------
# 13-14 interface satellites and memo satellites
# --------------------------------------------------------------------------------------------------


def test_counterparts_cover_every_k8b_entry(built, sat):
    cp = sat("row_financial_counterparts")
    k = built.filter(pl.col("ref") == "K8b")
    per_line = dict(cp.group_by("line", maintain_order=True).agg(pl.col("value").sum()).iter_rows())
    for comp, x in k.select("component", "value").iter_rows():
        assert per_line[comp] == pytest.approx(x, abs=TOL), comp
    assert cp["value"].sum() == pytest.approx(k["value"].sum(), abs=TOL)
    ok = set(Accounts.load().in_group("CAP")) | {"unallocated_k9"}
    assert set(cp["counterpart"]) <= ok
    unal = set(cp.filter(pl.col("counterpart") == "unallocated_k9")["line"])
    assert unal == {"errors_omissions", "nas_reconciliation_liab", "nas_reconciliation_assets"}
    # reinvested earnings counterparts = the R14a payers
    r14a = {c.INST_TO_K[a]: x for a, x in built.filter(pl.col("ref") == "R14a").select("col", "value").iter_rows()}
    re_cp = dict(cp.filter(pl.col("line") == "fdi_reinvested_earnings").select("counterpart", "value").iter_rows())
    assert re_cp == pytest.approx(r14a)


def test_property_income_satellite_mirrors_the_entries(built, sat):
    p = sat("row_property_income")
    e = built.filter(pl.col("ref").is_in(["R13", "R14", "R14a"]))
    assert p.height == e.height
    assert p["value"].sum() == pytest.approx(e["value"].sum(), abs=1e-4)
    assert set(p["entry_prov_id"]) == set(e["prov_id"])


def test_fla_keys_come_from_the_2023_24_round(prov):
    """Plan s.7 item 14: FLA inputs are the 2023-24 round (vintage 2024-10-11) only."""
    fla = _dataset("external_sector_fla_census").select("prov_id", "vintage").unique(maintain_order=True)
    ins = {i for s in prov["inputs"].drop_nulls() for i in s.split(",")}
    used = fla.filter(pl.col("prov_id").is_in(sorted(ins)))
    assert used.height >= 1
    assert set(used["vintage"]) == {c.V_FLA}


def test_s3_remittance_sources(sat):
    s3 = sat("s3_remittance_sources")
    sh = s3.filter(pl.col("measure") == "share")
    assert sh["value"].sum() == pytest.approx(1.0, abs=TOL)
    inr = s3.filter(pl.col("measure") == "inr_crore")["value"].sum()
    assert inr == pytest.approx(nas61("other_current_transfers_to_resident_sectors_other_than_gener"), abs=0.01)


def test_s2_services_totals_reproduce_the_bop(sat):
    s2 = sat("s2_services_by_partner").filter(pl.col("measure") == "inr_crore")
    for k in range(1, 14):
        for side, flow in (("credit", "exports"), ("debit", "imports")):
            got = s2.filter((pl.col("bop_item") == f"bpm6_1_a_b_{k}") & (pl.col("flow") == flow))["value"].sum()
            assert got == pytest.approx(bpm6(f"bpm6_1_a_b_{k}.{side}"), abs=0.01), (k, flow)
    si = s2.filter((pl.col("bop_item") == "bpm6_1_a_b_9") & (pl.col("flow") == "exports"))
    tot = si["value"].sum()
    for region, iso in (("united_states_of_america", "USA"), ("united_kingdom", "GBR"), ("canada", "CAN")):
        share = si.filter(pl.col("partner") == iso)["value"].item() / tot
        ites = cv("external_sector_ites_survey", f"ites.t5.{region}.share") / 100.0
        assert share == pytest.approx(ites, abs=0.0005), region


def test_s1_goods_reproduce_imts_world(sat, prov):
    s1 = sat("s1_goods_by_partner").filter(pl.col("measure") == "usd_mn")
    for flow, item in (("exports", "exports_fob"), ("imports", "imports_cif")):
        got = s1.filter((pl.col("flow") == flow) & (pl.col("partner_type") != "memo_reimports"))["value"].sum()
        assert got == pytest.approx(cv("trade_satellites_imf_imts_fy", f"imts.{item}.g001.current"), rel=1e-6)
        # partner margins equal IMTS country totals
        usa = s1.filter((pl.col("flow") == flow) & (pl.col("partner") == "USA"))["value"].sum()
        assert usa == pytest.approx(cv("trade_satellites_imf_imts_fy", f"imts.{item}.usa.current"), rel=1e-6)
    # rupee values use the external_sector FX series only, and the record cites it
    fx = _dataset("external_sector_fx_inr_usd").filter(
        (pl.col("series_id") == "t133.usd_fy_average") & (pl.col("period") == YEAR)
    )
    rec = prov.filter(pl.col("method").str.contains("Gap map S1"))
    assert fx["prov_id"].item() in rec["inputs"].item().split(",")
    both = (
        sat("s1_goods_by_partner")
        .filter(pl.col("partner") == "USA")
        .pivot(on="measure", index=["flow", "hs2"], values="value")
    )
    assert (both["inr_crore"] - both["usd_mn"] * fx["value"].item() / 10.0).abs().max() < 1e-4


# --------------------------------------------------------------------------------------------------
# 15 structure and provenance
# --------------------------------------------------------------------------------------------------


def test_structure_roles_and_provenance(built, prov):
    acc = Accounts.load()
    # no FAC cells in R13/R14 (property income is not factor income)
    pi = built.filter(pl.col("ref").is_in(["R13", "R14", "R14a"]))
    assert not any(acc.group(a) == "FAC" for a in pi["row"].to_list() + pi["col"].to_list())
    # fixed: K5, K8c, D2 and the BoP K8b lines; free entries carry a confidence
    for ref in ("K5", "K8c", "D2"):
        assert set(built.filter(pl.col("ref") == ref)["role"]) == {"fixed"}, ref
    free = built.filter(pl.col("role") == "free")
    assert free["confidence"].is_not_null().all() and set(free["status"]) == {"estimated"}
    # every estimated record has a method that names its key or assumption
    est = prov.filter(pl.col("status") == "estimated")
    assert est.height > 0 and (est["method"].str.len_chars() > 80).all()
    assert all(
        ("key" in m.lower())
        or ("assum" in m.lower())
        or ("share" in m.lower())
        or ("split" in m.lower())
        or ("interface" in m.lower())
        for m in est["method"].to_list()
    )
    # bop tags only on RoW entries
    tagged = built.filter(pl.col("bop_function").is_not_null())
    assert ((tagged["row"].is_in(spec.BOP_ACCOUNTS)) | (tagged["col"].is_in(spec.BOP_ACCOUNTS))).all()


def test_each_sensitivity_record_cites_its_own_refs_record(built, prov, sat):
    """V-ROW-1 regression: the r11a_sensitivity record cites the R11a entries' record (not R12a's) and vice versa."""
    ins = dict(prov.select("prov_id", "inputs").iter_rows())
    for ref, name, other in (("R11a", "r11a_sensitivity", "R12a"), ("R12a", "r12a_sensitivity", "R11a")):
        (own,) = set(built.filter(pl.col("ref") == ref)["prov_id"])
        (oth,) = set(built.filter(pl.col("ref") == other)["prov_id"])
        (sens,) = set(sat(name)["prov_id"])
        cited = set((ins[sens] or "").split(","))
        assert own in cited and oth not in cited, (name, own, oth, cited)


def test_method_texts_have_no_unformatted_placeholders(prov):
    """V-ROW-2 regression: no record's method or notes keeps a literal '{...}' (a string segment missing its f)."""
    for col in ("method", "notes"):
        bad = prov.filter(pl.col(col).fill_null("").str.contains(r"[{}]"))
        assert bad.height == 0, (col, bad["prov_id"].to_list())


def test_constraint_targets_come_from_nas(cons):
    t = dict(cons.select("constraint_id", "target").iter_rows())
    assert t["row.r13_total"] == pytest.approx(nas61("property_and_entrepreneurial_income_from_rest_of_the_world"))
    assert t["row.r14_total"] == pytest.approx(nas61("property_and_entrepreneurial_income_to_the_rest_of_the_world"))
    assert t["row.current_receipts"] == pytest.approx(nas61("current_receipts"))
    assert t["row.current_disbursements"] == pytest.approx(nas61("current_disbursements"))
    assert t["row.k8b_liabilities_to_row"] == pytest.approx(nas61("net_incurrence_of_foreign_liabilities"))
    assert t["row.k8b_assets_from_row"] == pytest.approx(nas61("net_acquisition_of_foreign_financial_assets"))
    assert t["row.fpi_debt"] == pytest.approx(old("ka.portfolio.in_india.fiis.debt"))
    assert t["row.r14_type.di"] == pytest.approx(bpm6("bpm6_1_b_2_1.debit"))


def test_prior_satisfies_every_own_constraint(built, cons):
    """The block's own entries (plus production's P5/P6 and NAS V3/V4 for the acceptance totals) meet every
    constraint it declares, before balancing."""
    prod = pl.read_parquet(PATHS.entries("production")).drop("block")
    pseudo = pl.DataFrame(
        [
            {
                "row": "F_LREG",
                "col": "R_ROW",
                "ref": "V3",
                "component": "total",
                "value": nas61("compensation_of_employees_from_rest_of_the_world"),
            },
            {
                "row": "R_ROW",
                "col": "F_LREG",
                "ref": "V4",
                "component": "total",
                "value": nas61("compensation_of_employees_to_the_rest_of_the_world"),
            },
        ]
    )
    cols = ["row", "col", "ref", "component", "value"]
    e = pl.concat([built.select(cols), prod.select(cols), pseudo])
    for r in cons.iter_rows(named=True):
        sel = e.filter(pl.col("row").is_in(r["rows"].split(",")) & pl.col("col").is_in(r["cols"].split(",")))
        if r["refs"]:
            sel = sel.filter(pl.col("ref").is_in(r["refs"].split(",")))
        if r["components"]:
            sel = sel.filter(pl.col("component").is_in(r["components"].split(",")))
        tol = max(r["tol_abs"], r["tol_rel"] * abs(r["target"]))
        assert abs(sel["value"].sum() - r["target"]) <= tol + 1e-6, (r["constraint_id"], sel["value"].sum())


# --------------------------------------------------------------------------------------------------
# pure helpers on small fixtures
# --------------------------------------------------------------------------------------------------


def test_allocate_and_shares():
    got = c.allocate(10.0, {"a": 1.0, "b": 3.0, "z": 0.0}, "t")
    assert got == pytest.approx({"a": 2.5, "b": 7.5}) and sum(got.values()) == 10.0
    with pytest.raises(SamError):
        c.shares({"a": -1.0, "b": 2.0}, "t")
    with pytest.raises(SamError):
        c.shares({"a": 0.0}, "t")


def test_remittance_by_group_small():
    key = {"s1": {"H_R1": 1.0, "H_U5": 3.0}, "s2": {"H_R1": 1.0}}
    got = c.remittance_by_group(100.0, {"s1": 50.0, "s2": 50.0}, key)
    assert got == pytest.approx({"H_R1": 62.5, "H_U5": 37.5})
    assert math.isclose(sum(got.values()), 100.0)
    with pytest.raises(SamError):
        c.remittance_by_group(100.0, {"s1": 50.0, "s3": 50.0}, key)  # a State without a key is an error


def test_ras_small():
    seed = {("a", "x"): 1.0, ("a", "y"): 1.0, ("b", "x"): 1.0, ("b", "y"): 3.0}
    got = c.ras(seed, {"a": 4.0, "b": 6.0}, {"x": 5.0, "y": 5.0})
    rows = {r: sum(v for (rr, _), v in got.items() if rr == r) for r in ("a", "b")}
    cols = {k: sum(v for (_, kk), v in got.items() if kk == k) for k in ("x", "y")}
    assert rows == pytest.approx({"a": 4.0, "b": 6.0}, abs=TOL) and cols == pytest.approx({"x": 5.0, "y": 5.0})
    with pytest.raises(SamError):
        c.ras(seed, {"a": 4.0, "b": 6.0}, {"x": 5.0, "y": 6.0})
