"""SPEC acceptance identities on the balanced SAM (DESIGN_BRIEF s.7; FRAMEWORK_REQUESTS FR2-1; CROSS_REVIEW
XR-33), owned by the closure block, plus closure's post-balancing tests (plan s.7 T2, T6, T7, T9, T10).

They skip until a successful balancing run exists (`uv run python -m pipeline sam`, all nine blocks) and then
fail loudly with the numbers. Every target is read from data/clean at test time (never typed in); the
tolerances are stated next to each test and in docs/phase2/issues/closure.md:
- balance: Rs 0.01 crore per account (spec.BALANCE_TOL);
- GDP three ways: Rs 10 crore against NAS 1.1 (the SUT is not exactly additive: production anchors each SUT
  cell within Rs 1 crore and its own GDP checks use Rs 5 crore; the official discrepancy is 0 in 2023-24);
- NAS saving, GDI and BoP totals: Rs 0.5-3 crore (the blocks' constraint tolerances, summed where totals add);
- cash tax receipts: the relative bands the taxes block declares (plan taxes s.3), because the SAM is on the
  SUT accrual basis and receipts are cash (TAX-1: SUT product taxes exceed Union + State receipts by 5%).
"""

from __future__ import annotations

import json

import polars as pl
import pytest

from pipeline.core.paths import Layout
from pipeline.sam import spec
from pipeline.sam.accounts import Accounts
from pipeline.sam.framework import SamPaths

pytestmark = pytest.mark.sam

LAYOUT = Layout.default()
PATHS = SamPaths(LAYOUT)
YEAR = spec.YEAR
ACC = Accounts.load()
G = {g: ACC.in_group(g) for g in ("ACT", "COM", "FAC", "HH", "NFC", "FC", "GOV", "TAX", "ROW", "CAP", "DSTK", "INST",
                                   "DISC")}  # fmt: skip
GDP_TOL = 10.0


def _clean(unit: str, dataset: str, sid: str, period: str = YEAR) -> float:
    df = pl.read_parquet(LAYOUT.clean / unit / f"{dataset}.parquet")
    df = df.filter((pl.col("series_id") == sid) & (pl.col("period") == period))
    df = df.filter(pl.col("vintage") == df["vintage"].max())
    assert df.height == 1, f"{dataset}/{sid}: {df.height} rows"
    return float(df["value"][0])


def _nas(ds: str, sid: str) -> float:
    return _clean("mospi_nas_2026", f"mospi_nas_2026_{ds}", sid)


@pytest.fixture(scope="module")
def bal() -> pl.DataFrame:
    if not PATHS.run_json.exists():
        pytest.skip("no balancing run yet (run `uv run python -m pipeline sam` once all nine blocks are built)")
    run = json.loads(PATHS.run_json.read_text(encoding="utf-8"))
    if not run.get("ok") or not PATHS.balanced_entries.exists():
        pytest.fail(f"the last balancing run failed, so no balanced SAM exists: {run.get('messages')}")
    return pl.read_parquet(PATHS.balanced_entries)


def _s(df: pl.DataFrame, rows=None, cols=None, refs=None, value: str = "value") -> float:
    e = df
    if rows is not None:
        e = e.filter(pl.col("row").is_in(list(rows)))
    if cols is not None:
        e = e.filter(pl.col("col").is_in(list(cols)))
    if refs is not None:
        e = e.filter(pl.col("ref").is_in(list(refs)))
    return float(e[value].sum())


NUM = 1e-4  # the solver's numerical slack on top of a declared band (it closes to about Rs 1e-6 crore): a total on
# the edge of its constraint's band (e.g. FC saving at +1.000001 against k2.fc_saving_total +-1) is inside the band


def _close(got: float, want: float, tol: float, what: str) -> None:
    assert abs(got - want) <= tol + NUM, (
        f"{what}: SAM {got:,.4f} vs source {want:,.4f} (diff {got - want:+,.4f}, tol {tol})"
    )


# ---------------------------------------------------------------------------------------------
# (a) rows = columns
# ---------------------------------------------------------------------------------------------


def test_every_account_row_equals_column(bal):
    r = bal.group_by("row", maintain_order=True).agg(pl.col("value").sum().alias("r")).rename({"row": "a"})
    c = bal.group_by("col", maintain_order=True).agg(pl.col("value").sum().alias("c")).rename({"col": "a"})
    j = r.join(c, on="a", how="full", coalesce=True).fill_null(0.0).with_columns((pl.col("r") - pl.col("c")).alias("d"))
    bad = j.filter(pl.col("d").abs() > spec.BALANCE_TOL)
    assert bad.height == 0, bad.sort(pl.col("d").abs(), descending=True)


# ---------------------------------------------------------------------------------------------
# (b) GDP three ways vs NAS 1.1, only the official discrepancy
# ---------------------------------------------------------------------------------------------


def _gdp(bal: pl.DataFrame) -> dict[str, float]:
    net_product_taxes = _s(bal, G["TAX"], G["COM"])  # P7a + P8 import duty + P9 subsidies (negative)
    production = _s(bal, G["ACT"], G["COM"]) - _s(bal, G["COM"], G["ACT"]) + net_product_taxes
    expenditure = (
        _s(bal, G["COM"], G["HH"]) + _s(bal, G["COM"], G["GOV"]) + _s(bal, G["COM"], G["CAP"])
        + _s(bal, G["COM"], G["DSTK"]) + _s(bal, G["COM"], G["ROW"]) - _s(bal, G["ROW"], G["COM"])
    )  # fmt: skip
    income = _s(bal, G["FAC"], G["ACT"]) + _s(bal, G["TAX"], G["ACT"]) + net_product_taxes
    return {"production": production, "expenditure": expenditure, "income": income,
            "discrepancy": _s(bal, G["COM"], G["DISC"])}  # fmt: skip


def test_gdp_three_ways(bal):
    gdp = _nas("s1_1", "s1_1.gdp.current")
    g = _gdp(bal)
    _close(g["production"], gdp, GDP_TOL, "GDP, production approach vs NAS 1.1 GDP")
    _close(g["income"], gdp, GDP_TOL, "GDP, income approach vs NAS 1.1 GDP")
    _close(g["expenditure"] + g["discrepancy"], _nas("s1_1", "s1_1.gdp_expenditure.current"), GDP_TOL,
           "GDP, expenditure approach (+ D4) vs NAS 1.1")  # fmt: skip
    # only the official discrepancy separates expenditure from production
    _close(g["expenditure"] - g["production"], _nas("s1_1", "s1_1.discrepancies.current") - g["discrepancy"],
           GDP_TOL, "expenditure - production GDP vs the NAS 1.1 discrepancy")  # fmt: skip
    _close(g["discrepancy"], _nas("s1_1", "s1_1.discrepancies.current"), 1e-6, "D4 vs NAS 1.1 discrepancies")


@pytest.mark.parametrize(
    "what,rows,cols,series,tol",
    [
        ("PFCE", "COM", "HH", "s1_1.pfce.current", 2.0),
        ("GFCE", "COM", "GOV", "s1_1.gfce.current", 2.0),
        ("change in inventories", "COM", "DSTK", "s1_1.cis.current", 5.0),
        ("exports", "COM", "ROW", "s1_1.exports.current", 5.0),
        ("imports (after the CIF adjustment)", "ROW", "COM", "s1_1.imports.current", 5.0),
    ],
)
def test_expenditure_components(bal, what, rows, cols, series, tol):
    _close(_s(bal, G[rows], G[cols]), _nas("s1_1", series), tol, f"{what} vs NAS 1.1")


def test_gfcf_and_valuables(bal):
    want = _nas("s1_1", "s1_1.gfcf.current") + _nas("s1_1", "s1_1.valuables.current")
    _close(_s(bal, G["COM"], G["CAP"]), want, 5.0, "GFCF + valuables (COM <- CAP) vs NAS 1.1")


# ---------------------------------------------------------------------------------------------
# (c) government
# ---------------------------------------------------------------------------------------------


def _gg_saving(bal):
    return _s(bal, ["K_GCEN"], ["G_CEN"]) + _s(bal, ["K_GSTA"], ["G_STA"])


def test_gg_saving_and_gdi(bal):
    """T10 (GG): saving = NAS 1.9; GDI = GFCE + saving = NAS 1.14 GG GDI."""
    _close(_gg_saving(bal), _nas("s1_9", "s1_9.general_government.current"), 1.0, "GG gross saving vs NAS 1.9")
    gdi = _s(bal, G["COM"], G["GOV"]) + _gg_saving(bal)
    _close(gdi, _nas("s1_14", "s1_14.gg.gross_disposable_income.current"), 2.0, "GG GDI vs NAS 1.14")


def _union(sid: str) -> float:
    return _clean("union_fiscal", "union_fiscal_rb_receipts", sid)


def _fa(sid: str) -> float:
    return _clean("union_fiscal", "union_fiscal_fa_receipts", sid)


def _states(item: str) -> float:
    return _clean(
        "state_fiscal", "state_fiscal_rbi_sf_appendices", f"app1.total_revenue.{item}.in.all_states_uts.actuals"
    )


@pytest.mark.parametrize(
    "gov,tax,target,rel",
    [
        # Union: Finance Accounts gross (total less the 901 devolution line) and the Receipt Budget
        ("G_CEN", "T_CIT", lambda: _fa("fa8.0020.total") - _fa("fa8.0020.00.901"), 0.005),
        ("G_CEN", "T_PIT", lambda: _union("rb.tr.total.total_taxes_on_income"), 0.01),
        ("G_CEN", "T_UEXC", lambda: _union("rb.tr.total.total_union_excise_duties"), 0.05),
        ("G_CEN", "T_GCES", lambda: _union("rb.tr.0009.gst_compensation_cess"), 0.05),
        ("G_CEN", "T_CUST", lambda: _union("rb.tr.total.total_customs"), 0.025),
        # States + UTs with legislature (RBI State Finances, Accounts 2023-24)
        ("G_STA", "T_SGST", lambda: _states("i.a.3.vii-state_goods_and_services_tax"), 0.05),
        ("G_STA", "T_SVAT", lambda: _states("i.a.3.i-sales_tax"), 0.15),
        ("G_STA", "T_SEXC", lambda: _states("i.a.3.ii-state_excise"), 0.15),
        ("G_STA", "T_PIT", lambda: _states("i.a.1-taxes_on_income"), 0.01),
    ],
)  # fmt: skip
def test_tax_receipts_by_government(bal, gov, tax, target, rel):
    want = target()
    _close(_s(bal, [gov], [tax]), want, rel * abs(want), f"{gov} <- {tax} vs cash receipts (band {rel:.1%})")


def test_union_gross_tax_revenue(bal):
    """Union gross tax revenue before devolution (Receipt Budget: corporation tax + taxes on income + GST incl. the
    compensation cess + customs + Union excise; `total_tax_revenue` is net of the States' share, so it is not
    used) vs G_CEN <- {T_CIT, T_PIT, T_CGST, T_GCES, T_CUST, T_UEXC}: accrual SUT basis vs cash, 5% band (TAX-1)."""
    parts = ["total_corporation_tax", "total_taxes_on_income", "total_goods_and_services_tax_gst", "total_customs",
             "total_union_excise_duties"]  # fmt: skip  (series id fixed: audit BS-4)
    want = sum(_union(f"rb.tr.total.{p}") for p in parts)
    got = _s(bal, ["G_CEN"], ["T_CIT", "T_PIT", "T_CGST", "T_GCES", "T_CUST", "T_UEXC"])
    _close(got, want, 0.05 * want, "Union gross tax revenue (five heads) vs Receipt Budget")


def test_state_sgst_at_least_fc16(bal):
    """FC16 key fiscal indicators cover 28 States only: the SAM (States + UTs + local bodies) must not be below."""
    fc16 = _clean("state_fiscal", "state_fiscal_fc16_kfi", "kfi.a_1_1_2-state_goods_and_service_tax.in.all_states_28")
    got = _s(bal, ["G_STA"], ["T_SGST"])
    assert got >= 0.95 * fc16, f"G_STA <- T_SGST {got:,.2f} below 95% of FC16 28-State SGST {fc16:,.2f}"


def test_devolution_equals_the_finance_accounts(bal):
    """R1 (G_STA <- G_CEN) = the States' share of Union taxes, Finance Accounts 901 lines (sign flipped)."""
    lines = ["fa8.0005.00.901", "fa8.0020.00.901", "fa8.0021.00.901", "fa8.0037.00.901", "fa8.0038.01.901",
             "fa8.0044.00.901", "fa8.0045.00.901"]  # fmt: skip
    want = -sum(_fa(s) for s in lines)
    _close(_s(bal, ["G_STA"], ["G_CEN"], refs=["R1"]), want, 1.0, "tax devolution R1 vs Finance Accounts")


# ---------------------------------------------------------------------------------------------
# (c) BoP: current account, R_ROW and K_ROW closure with D2
# ---------------------------------------------------------------------------------------------


def test_row_current_account(bal):
    receipts = _s(bal, None, ["R_ROW"]) - _s(bal, ["K_ROW"], ["R_ROW"])  # what RoW pays residents
    disbursements = _s(bal, ["R_ROW"], None)  # what residents pay RoW, incl. D2 (the CIF reconciliation)
    _close(receipts, _nas("s6_1", "s6_1.current_receipts.current"), 1.0, "RoW current receipts vs NAS 6.1")
    _close(disbursements, _nas("s6_1", "s6_1.current_disbursements.current"), 1.0, "RoW current disbursements vs 6.1")
    _close(receipts - disbursements, _nas("s6_1", "s6_1.surplus_on_current_transactions.current"), 2.0,
           "surplus on current transactions vs NAS 6.1")  # fmt: skip
    _close(_s(bal, ["K_ROW"], ["R_ROW"]), _nas("s1_9", "s1_9.net_capital_inflow_from_row.current"), 0.5,
           "RoW saving (K5) vs NAS 1.9 net capital inflow")  # fmt: skip


def test_d2_is_the_sut_cif(bal):
    cif = _clean("io_tables", "io_tables_sut_supply", "supply.cif_adj.cif.current")
    _close(_s(bal, ["R_ROW"], ["X_DISC"]), cif, 1e-6, "D2 vs SUT CIF adjustment")


def test_k_row_financial_account(bal):
    liab = _s(bal, G["INST"], ["K_ROW"], refs=["K8b"])
    assets = _s(bal, ["K_ROW"], G["INST"], refs=["K8b"])
    _close(liab, _nas("s6_1", "s6_1.net_incurrence_of_foreign_liabilities.current"), 1.0,
           "India's net incurrence of foreign liabilities (I_* <- K_ROW, K8b) vs NAS 6.1")  # fmt: skip
    _close(assets, _nas("s6_1", "s6_1.net_acquisition_of_foreign_financial_assets.current"), 1.0,
           "India's net acquisition of foreign financial assets (K_ROW <- I_*, K8b) vs NAS 6.1")  # fmt: skip
    r, c = _s(bal, ["K_ROW"], None), _s(bal, None, ["K_ROW"])
    _close(r, c, spec.BALANCE_TOL, "K_ROW row vs column")


# ---------------------------------------------------------------------------------------------
# (c) flow of funds: every instrument clears; household financial saving = NAS 5.3
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("inst", G["INST"])
def test_every_instrument_market_clears(bal, inst):
    _close(_s(bal, [inst], None), _s(bal, None, [inst]), spec.BALANCE_TOL, f"{inst}: acquisitions vs incurrence")


def test_household_financial_saving_equals_nas_5_3(bal):
    assets = _s(bal, G["INST"], ["K_HH"], refs=["K7a"])
    liab = _s(bal, ["K_HH"], G["INST"], refs=["K8a"])
    _close(assets, _nas("s5_3", "s5_3.gross_financial_saving.current"), 0.5, "household financial assets (K7a)")
    _close(liab, _nas("s5_3", "s5_3.financial_liabilities.current"), 0.5, "household financial liabilities (K8a)")
    _close(assets - liab, _nas("s5_3", "s5_3.net_financial_saving_of_household_sector_1_4.current"), 1.0,
           "household net financial saving vs NAS 5.3")  # fmt: skip


# ---------------------------------------------------------------------------------------------
# X_DISC unchanged; closure's post-balancing tests (plan s.7 T2, T6, T7, T9, T10)
# ---------------------------------------------------------------------------------------------


def test_xdisc_unchanged_and_closed(bal):
    """T6: X_DISC entries are pinned (balanced = prior) and the account closes; D1 = D2 + D3 + D4 within Rs 1 crore
    of the published household residual (DECISIONS D2-3)."""
    x = bal.filter((pl.col("row") == "X_DISC") | (pl.col("col") == "X_DISC"))
    moved = x.filter(pl.col("value") != pl.col("prior"))
    assert moved.height == 0, moved
    d1 = _s(bal, ["X_DISC"], None)
    _close(d1, _s(bal, None, ["X_DISC"]), spec.BALANCE_TOL, "X_DISC row vs column")
    _close(d1, _nas("derived_residuals", "derived.household_residual.current"), 1.0, "D1 vs published residual")


def test_household_saving_equals_nas(bal):
    """T2: sum of balanced K4a = NAS 1.9 = 1.14 = 5.3 household saving."""
    k4 = _s(bal, ["K_HH"], G["HH"], refs=["K4a"])
    for ds, sid in (("s1_9", "s1_9.household_sector.current"),
                    ("s1_14", "s1_14.households_npish.gross_savings.current"),
                    ("s5_3", "s5_3.household_saving_1_2_3_4.current")):  # fmt: skip
        _close(k4, _nas(ds, sid), 0.5, f"household saving vs {sid}")


def test_k_hh_closure(bal):
    """T7 (as amended by CROSS_REVIEW XR-3 / D2-6): K_HH closes including capital_financial's K9 residual, and the
    D3 posting to K_HH equals the unsectored valuables cell I2a to the paisa."""
    _close(_s(bal, ["K_HH"], None), _s(bal, None, ["K_HH"]), spec.BALANCE_TOL, "K_HH row vs column")
    _close(_s(bal, ["K_HH"], ["X_DISC"], refs=["D3"]), _s(bal, ["C_GJOM"], ["K_HH"], refs=["I2a"]), 1e-6,
           "D3 -> K_HH vs I2a")  # fmt: skip


GDI_PARTS = ("households:hh.c1.total", "capital_financial:cf.k4.hh_saving", "closure:d1.published_total")


def test_household_gdi(bal):
    """T9: household GDI = consumption + saving + D1 = NAS 1.14. Each part is held by its own declared constraint
    (PFCE `hh.c1.total` +-1, saving `cf.k4.hh_saving` +-0.5, D1 `d1.published_total` +-1, D2-3), whose targets add
    up to NAS 1.14 GDI, so the tolerance is the sum of those declared tolerances, read from constraints.parquet
    (audit BS-3: a Rs 1 tolerance was tighter than its parts allow; the run left PFCE -1.00, saving -0.50 and the
    pinned D1 -0.11 inside their own bands)."""
    hh = G["HH"]
    gdi = _s(bal, G["COM"], hh) + _s(bal, ["K_HH"], hh) + _s(bal, ["X_DISC"], hh)
    cons = pl.read_parquet(PATHS.constraints_all).filter(pl.col("constraint_id").is_in(list(GDI_PARTS)))
    assert cons.height == len(GDI_PARTS), f"GDI part constraints missing: {cons['constraint_id'].to_list()}"
    tol = sum(max(r["tol_abs"], r["tol_rel"] * abs(r["target"])) for r in cons.iter_rows(named=True))
    want = _nas("s1_14", "s1_14.households_npish.gross_disposable_income.current")
    _close(float(cons["target"].sum()), want, 1e-3, "GDI part targets vs NAS 1.14 GDI")
    _close(gdi, want, tol, "household GDI")


def test_corporate_saving(bal):
    """T10 (NFC, FC): saving cells = NAS 1.9."""
    _close(_s(bal, ["K_NFPU"], ["E_NFPU"]), _nas("s1_9", "s1_9.public_non_financial_corporations.current"), 1.0,
           "public NFC saving")  # fmt: skip
    _close(_s(bal, ["K_NFPR"], ["E_NFPR"]), _nas("s1_9", "s1_9.private_non_financial_corporations.current"), 1.0,
           "private NFC saving")  # fmt: skip
    _close(_s(bal, G["CAP"], G["FC"]), _nas("s1_9", "s1_9.financial_corporations.current"), 1.0, "FC saving")


def test_national_saving_and_gndi(bal):
    saving = _s(bal, G["CAP"], G["HH"] + G["NFC"] + G["FC"] + G["GOV"])
    _close(saving, _nas("s1_1", "s1_1.gross_saving.current"), 2.0, "gross national saving vs NAS 1.1")
    gndi = saving + _s(bal, G["COM"], G["HH"] + G["GOV"]) + _s(bal, ["X_DISC"], G["HH"])
    _close(gndi, _nas("s1_1", "s1_1.gndi.current"), 3.0, "GNDI (saving + final consumption + D1) vs NAS 1.1")
