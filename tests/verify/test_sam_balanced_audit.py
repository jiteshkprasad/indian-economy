"""Independent audit of the balanced SAM 2023-24 (SPEC s.6 Phase 2 acceptance tests; SPEC rule 3).

Report: docs/phase2/verify/balanced_sam.md. Written by an auditor who built nothing in the SAM. Nothing here
imports `pipeline.sam` or `pipeline.core`: the balanced entries, the constraints and the clean targets are read
with DuckDB straight from Parquet, the account order from `pipeline/sam/accounts.yaml`, and every number is
recomputed here. Every target comes from data/clean at test time (never typed in). Tolerances are stated next
to each test; where a total is the sum of constrained parts, its tolerance is the sum of the parts' declared
tolerances (and says so).

Confirmed defects are strict xfails: they turn into failures (XPASS) once fixed, so the xfail must then go.
"""

from __future__ import annotations

import csv
import json
import math
from functools import cache
from pathlib import Path

import duckdb
import numpy as np
import pytest
import yaml

pytestmark = [pytest.mark.quality, pytest.mark.sam]

ROOT = Path(__file__).resolve().parents[2]
SAM = ROOT / "data" / "sam" / "2023-24"
CLEAN = ROOT / "data" / "clean"
YEAR = "2023-24"
BAL_TOL = 0.01  # SPEC / DESIGN_BRIEF s.5.3: |row - column| <= Rs 0.01 crore per account
NUM = 1e-3  # numerical slack on top of a declared band (the solver closes to about 1e-6 crore)


# ---------------------------------------------------------------------------------------------
# data access
# ---------------------------------------------------------------------------------------------


@cache
def _con() -> duckdb.DuckDBPyConnection:
    run = SAM / "balancing_run.json"
    if not run.exists():
        pytest.skip("no balancing run yet (run `uv run python -m pipeline sam`)")
    if not json.loads(run.read_text(encoding="utf-8")).get("ok"):
        pytest.fail("the last balancing run failed: no balanced SAM to audit")
    con = duckdb.connect()
    con.execute(f"create view b as select * from read_parquet('{(SAM / 'sam_entries_balanced.parquet').as_posix()}')")
    con.execute(f"create view p as select * from read_parquet('{(SAM / 'sam_entries_prior.parquet').as_posix()}')")
    con.execute(f"create view k as select * from read_parquet('{(SAM / 'constraints.parquet').as_posix()}')")
    return con


@cache
def _accounts() -> tuple[list[str], dict[str, list[str]]]:
    acc = yaml.safe_load((ROOT / "pipeline" / "sam" / "accounts.yaml").read_text(encoding="utf-8"))["accounts"]
    groups: dict[str, list[str]] = {}
    for a in acc:
        groups.setdefault(a["group"], []).append(a["code"])
    return [a["code"] for a in acc], groups


def G(*names: str) -> list[str]:
    g = _accounts()[1]
    return [c for n in names for c in g[n]]


def _in(col: str, vals) -> str:
    return f"{col} in ({','.join(repr(v) for v in vals)})"


def s(rows=None, cols=None, refs=None, comps=None, col: str = "value") -> float:
    w = ["true"]
    for name, vals in (("row", rows), ("col", cols), ("ref", refs), ("component", comps)):
        if vals is not None:
            w.append(_in(name, vals))
    return float(_con().execute(f"select coalesce(sum({col}), 0) from b where {' and '.join(w)}").fetchone()[0])


def clean(unit: str, dataset: str, sid: str, period: str = YEAR) -> float:
    """The one value of a clean series for a period (latest vintage if several; each is asserted to exist)."""
    path = (CLEAN / unit / f"{dataset}.parquet").as_posix()
    rows = (
        duckdb.connect()
        .execute(
            f"select vintage, value from read_parquet('{path}') where series_id = ? and period = ? order by vintage",
            [sid, period],
        )
        .fetchall()
    )
    assert rows, f"{dataset}/{sid} {period}: no row (series id wrong?)"
    return float(rows[-1][1])


def nas(table: str, sid: str) -> float:
    return clean("mospi_nas_2026", f"mospi_nas_2026_{table}", sid)


def close(got: float, want: float, tol: float, what: str) -> None:
    assert abs(got - want) <= tol, f"{what}: SAM {got:,.4f} vs source {want:,.4f} (diff {got - want:+,.4f}, tol {tol})"


# ---------------------------------------------------------------------------------------------
# integrity of the outputs audited
# ---------------------------------------------------------------------------------------------


def test_balanced_file_is_the_prior_plus_the_change():
    c = _con()
    assert c.execute("select count(*) from b where abs(value - balanced) > 1e-9").fetchone()[0] == 0
    assert c.execute("select max(abs(change - (balanced - prior))) from b").fetchone()[0] < 1e-6
    n, d = c.execute(
        "select count(*), max(abs(p.value - b.prior)) from p join b using (row, col, ref, component)"
    ).fetchone()
    assert n == c.execute("select count(*) from b").fetchone()[0] == c.execute("select count(*) from p").fetchone()[0]
    assert d == 0.0
    blocks = (SAM / "blocks").as_posix()
    n2, d2 = c.execute(
        "select count(*), max(abs(x.value - b.prior))"
        f" from read_parquet('{blocks}/*_entries.parquet', union_by_name=true) x"
        " join b using (row, col, ref, component)"
    ).fetchone()
    assert n2 == n and d2 == 0.0, "the prior is not exactly the nine blocks' entries"


def test_cells_and_matrix_match_the_entries():
    codes = _accounts()[0]
    c = _con()
    cells_file = (SAM / "sam_balanced.parquet").as_posix()
    n, d = c.execute(
        "select count(*), max(abs(coalesce(c.value, 0) - coalesce(e.v, 0)))"
        f" from read_parquet('{cells_file}') c"
        " full join (select row, col, sum(value) v from b group by all) e using (row, col)"
    ).fetchone()
    assert d < 1e-5, d
    m = list(csv.reader((SAM / "sam_balanced_matrix.csv").open(encoding="utf-8")))
    assert m[0][1:] == codes and [r[0] for r in m[1:]] == codes, "matrix order is not accounts.yaml order"
    cells = {(r, cc): v for r, cc, v in c.execute("select row, col, sum(value) from b group by all").fetchall()}
    worst = max(
        abs((float(v) if v else 0.0) - cells.get((codes[i], codes[j]), 0.0))
        for i, r in enumerate(m[1:])
        for j, v in enumerate(r[1:])
    )
    # was 0.005 (the CSV was printed to 2 decimals); audit BS-2 (7) fixed: 6 decimals, measured 2e-6 on the Wave C run
    # (re-verification 2026-10-01), so the tolerance is the 6-decimal rounding plus float noise
    assert worst <= 1e-5, f"matrix CSV differs from the entries by {worst} (it is printed to 6 decimals)"


# ---------------------------------------------------------------------------------------------
# (a) every account: row total = column total
# ---------------------------------------------------------------------------------------------


def test_every_account_row_equals_column():
    codes = _accounts()[0]
    r = dict(_con().execute("select row, sum(value) from b group by 1").fetchall())
    c = dict(_con().execute("select col, sum(value) from b group by 1").fetchall())
    assert set(r) | set(c) <= set(codes)
    bad = {a: r.get(a, 0.0) - c.get(a, 0.0) for a in codes if abs(r.get(a, 0.0) - c.get(a, 0.0)) > BAL_TOL}
    assert not bad, bad
    assert all(a in r or a in c for a in codes), "an account has no entry"


# ---------------------------------------------------------------------------------------------
# (b) GDP three ways vs NAS 1.1; only the official discrepancy (0 in 2023-24)
# ---------------------------------------------------------------------------------------------

GDP_TOL = 10.0  # production anchors each SUT cell within Rs 1 crore; measured miss is about 0.6


def _gdp() -> dict[str, float]:
    npt = s(G("TAX"), G("COM"))
    return {
        "production": s(G("ACT"), G("COM")) - s(G("COM"), G("ACT")) + npt,
        "income": s(G("FAC"), G("ACT")) + s(G("TAX"), G("ACT")) + npt,
        "expenditure": s(G("COM"), G("HH", "GOV", "CAP", "DSTK", "ROW")) - s(G("ROW"), G("COM")),
        "d4": s(G("COM"), G("DISC")),
    }


def test_gdp_three_ways_and_only_the_official_discrepancy():
    g, gdp, disc = _gdp(), nas("s1_1", "s1_1.gdp.current"), nas("s1_1", "s1_1.discrepancies.current")
    close(g["production"], gdp, GDP_TOL, "GDP by production")
    close(g["income"], gdp, GDP_TOL, "GDP by income")
    close(g["expenditure"] + g["d4"], nas("s1_1", "s1_1.gdp_expenditure.current"), GDP_TOL, "GDP by expenditure")
    close(g["d4"], disc, 1e-9, "D4 (X_DISC <- COM) vs the NAS 1.1 discrepancy")
    close(g["expenditure"] - g["production"], disc, 1.0, "expenditure - production GDP beyond the discrepancy")
    close(g["production"], g["income"], BAL_TOL, "production vs income GDP (an identity of the balanced SAM)")


def test_gva_and_net_product_taxes():
    close(s(G("FAC"), G("ACT")) + s(G("TAX"), G("ACT")), nas("s1_1", "s1_1.gva_basic.current"), 5.0, "GVA basic")
    net = nas("s1_1", "s1_1.taxes_on_products.current") - nas("s1_1", "s1_1.subsidies_on_products.current")
    close(s(G("TAX"), G("COM")), net, 5.0, "product taxes less subsidies")


@pytest.mark.parametrize(
    "what,rows,cols,sid,tol",
    [
        # PFCE and GFCE: the declared bands hh.c1.total and gov.c2.total are +-1 (both end on an edge)
        ("PFCE", ("COM",), ("HH",), "s1_1.pfce.current", 1.0 + NUM),
        ("GFCE", ("COM",), ("GOV",), "s1_1.gfce.current", 1.0 + NUM),
        ("change in inventories", ("COM",), ("DSTK",), "s1_1.cis.current", 5.0),
        ("exports", ("COM",), ("ROW",), "s1_1.exports.current", 5.0),
        ("imports incl. the CIF adjustment", ("ROW",), ("COM",), "s1_1.imports.current", 5.0),
    ],
)
def test_expenditure_components(what, rows, cols, sid, tol):
    close(s(G(*rows), G(*cols)), nas("s1_1", sid), tol, f"{what} vs NAS 1.1")


def test_gfcf_plus_valuables():
    want = nas("s1_1", "s1_1.gfcf.current") + nas("s1_1", "s1_1.valuables.current")
    close(s(G("COM"), G("CAP")), want, 5.0, "GFCF + valuables (COM <- CAP) vs NAS 1.1")


# ---------------------------------------------------------------------------------------------
# (c) government: GG saving, GFCE, GDI; Centre and State taxes vs Finance Accounts / Receipt Budget / RBI SF / FC16
# ---------------------------------------------------------------------------------------------


def test_gg_saving_gfce_and_gdi():
    sav = s(["K_GCEN"], ["G_CEN"]) + s(["K_GSTA"], ["G_STA"])
    close(sav, nas("s1_9", "s1_9.general_government.current"), 0.5 + NUM, "GG saving vs NAS 1.9 (gov.k3 band +-0.5)")
    close(s(G("COM"), G("GOV")), nas("s1_14", "s1_14.gg.final_consumption_expenditure.current"), 1.0 + NUM, "GG FCE")
    close(s(G("COM"), G("GOV")) + sav, nas("s1_14", "s1_14.gg.gross_disposable_income.current"), 1.5 + NUM,
          "GG GDI vs NAS 1.14 (GFCE +-1 plus saving +-0.5)")  # fmt: skip


def _rb(sid):
    return clean("union_fiscal", "union_fiscal_rb_receipts", sid)


def _fa(sid):
    return clean("union_fiscal", "union_fiscal_fa_receipts", sid)


def _sf(item):
    return clean(
        "state_fiscal", "state_fiscal_rbi_sf_appendices", f"app1.total_revenue.{item}.in.all_states_uts.actuals"
    )


TAXES = [
    # (gov, tax account, cash source, relative band declared by the taxes block for cash vs accrual)
    ("G_CEN", "T_CIT", lambda: _fa("fa8.0020.total") - _fa("fa8.0020.00.901"), 0.005),
    ("G_CEN", "T_PIT", lambda: _rb("rb.tr.total.total_taxes_on_income"), 0.01),
    ("G_CEN", "T_UEXC", lambda: _rb("rb.tr.total.total_union_excise_duties"), 0.05),
    ("G_CEN", "T_GCES", lambda: _rb("rb.tr.0009.gst_compensation_cess"), 0.05),
    ("G_CEN", "T_CUST", lambda: _rb("rb.tr.total.total_customs"), 0.025),
    ("G_STA", "T_SGST", lambda: _sf("i.a.3.vii-state_goods_and_services_tax"), 0.05),
    ("G_STA", "T_SVAT", lambda: _sf("i.a.3.i-sales_tax"), 0.15),
    ("G_STA", "T_SEXC", lambda: _sf("i.a.3.ii-state_excise"), 0.15),
    ("G_STA", "T_PIT", lambda: _sf("i.a.1-taxes_on_income"), 0.01),
]


@pytest.mark.parametrize("gov,tax,src,rel", TAXES, ids=[f"{g}<-{t}" for g, t, _, _ in TAXES])
def test_tax_receipts_by_government(gov, tax, src, rel):
    want = src()
    close(s([gov], [tax]), want, rel * abs(want) * (1 + 1e-9), f"{gov} <- {tax} vs cash receipts ({rel:.1%})")


def test_union_gross_tax_revenue_five_heads():
    """Receipt Budget gross tax (before devolution) on five heads. The GST series id is
    `total_goods_and_services_tax_gst` (the closure identity test reads a non-existent id). Band 5% (cash vs SUT)."""
    heads = ["total_corporation_tax", "total_taxes_on_income", "total_goods_and_services_tax_gst", "total_customs",
             "total_union_excise_duties"]  # fmt: skip
    want = sum(_rb(f"rb.tr.total.{h}") for h in heads)
    close(
        s(["G_CEN"], ["T_CIT", "T_PIT", "T_CGST", "T_GCES", "T_CUST", "T_UEXC"]), want, 0.05 * want, "Union gross tax"
    )


def test_state_sgst_not_below_fc16_28_states():
    fc16 = clean("state_fiscal", "state_fiscal_fc16_kfi", "kfi.a_1_1_2-state_goods_and_service_tax.in.all_states_28")
    assert s(["G_STA"], ["T_SGST"]) >= 0.95 * fc16


def test_devolution_equals_the_finance_accounts():
    lines = ["fa8.0005.00.901", "fa8.0020.00.901", "fa8.0021.00.901", "fa8.0037.00.901", "fa8.0038.01.901",
             "fa8.0044.00.901", "fa8.0045.00.901"]  # fmt: skip
    close(s(["G_STA"], ["G_CEN"], ["R1"]), -sum(_fa(x) for x in lines), 1.0, "R1 devolution vs FA 901 lines")


def test_tax_accounts_pass_everything_to_government():
    close(s(G("GOV"), G("TAX")), s(None, G("TAX")), BAL_TOL, "tax accounts: receipts paid on to G_CEN / G_STA")


# ---------------------------------------------------------------------------------------------
# (c) BoP: current account, RoW accounts, D2
# ---------------------------------------------------------------------------------------------


def test_row_current_account_and_d2():
    receipts = s(None, ["R_ROW"]) - s(["K_ROW"], ["R_ROW"])
    disb = s(["R_ROW"], None)
    close(receipts, nas("s6_1", "s6_1.current_receipts.current"), 1.0, "RoW current receipts vs NAS 6.1")
    close(disb, nas("s6_1", "s6_1.current_disbursements.current"), 1.0, "RoW current disbursements vs NAS 6.1")
    close(receipts - disb, nas("s6_1", "s6_1.surplus_on_current_transactions.current"), 2.0, "current surplus")
    close(s(["K_ROW"], ["R_ROW"]), nas("s1_9", "s1_9.net_capital_inflow_from_row.current"), 0.5, "K5 vs NAS 1.9")
    cif = clean("io_tables", "io_tables_sut_supply", "supply.cif_adj.cif.current")
    close(s(["R_ROW"], ["X_DISC"]), cif, 1e-6, "D2 vs SUT CIF adjustment")
    close(
        s(["R_ROW"], ["X_DISC"]), nas("s6_1", "s6_1.adjustment_for_cif_in_import_of_services.current"), 1.0, "D2 vs 6.1"
    )
    close(s(G("FAC"), ["R_ROW"]), nas("s6_1", "s6_1.compensation_of_employees_from_rest_of_the_world.current"), 0.5,
          "CE from RoW")  # fmt: skip
    close(s(["R_ROW"], G("FAC")), nas("s6_1", "s6_1.compensation_of_employees_to_the_rest_of_the_world.current"), 0.5,
          "CE to RoW")  # fmt: skip


def test_row_financial_account():
    close(s(G("INST"), ["K_ROW"], ["K8b"]), nas("s6_1", "s6_1.net_incurrence_of_foreign_liabilities.current"), 1.0,
          "net incurrence of foreign liabilities")  # fmt: skip
    close(s(["K_ROW"], G("INST"), ["K8b"]), nas("s6_1", "s6_1.net_acquisition_of_foreign_financial_assets.current"),
          1.0, "net acquisition of foreign financial assets")  # fmt: skip
    for a in ("R_ROW", "K_ROW"):
        close(s([a], None), s(None, [a]), BAL_TOL, f"{a} row vs column")


# ---------------------------------------------------------------------------------------------
# (c) flow of funds: every instrument clears; household financial saving = NAS 5.3
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("inst", ["I_CURR", "I_DEPO", "I_LOAN", "I_GSEC", "I_SSAV", "I_CBND", "I_EQTY", "I_MFUN",
                                  "I_INPE", "I_RESV", "I_OTHR"])  # fmt: skip
def test_instrument_market_clears(inst):
    assert inst in G("INST")
    close(s([inst], None), s(None, [inst]), BAL_TOL, f"{inst}: acquisitions vs incurrence")


def test_household_financial_saving_equals_nas_5_3():
    a, liab = s(G("INST"), ["K_HH"], ["K7a"]), s(["K_HH"], G("INST"), ["K8a"])
    close(a, nas("s5_3", "s5_3.gross_financial_saving.current"), 0.5, "household financial assets")
    close(liab, nas("s5_3", "s5_3.financial_liabilities.current"), 0.5, "household financial liabilities")
    close(
        a - liab, nas("s5_3", "s5_3.net_financial_saving_of_household_sector_1_4.current"), 1.0, "net financial saving"
    )


# ---------------------------------------------------------------------------------------------
# sector saving and income aggregates vs NAS
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "what,rows,cols,sid,tol",
    [
        ("households", ["K_HH"], ("HH",), "s1_9.household_sector.current", 0.5 + NUM),
        ("public NFC", ["K_NFPU"], ["E_NFPU"], "s1_9.public_non_financial_corporations.current", 1.0),
        ("private NFC", ["K_NFPR"], ["E_NFPR"], "s1_9.private_non_financial_corporations.current", 1.0),
        ("financial corporations", ("CAP",), ("FC",), "s1_9.financial_corporations.current", 1.0 + NUM),
        ("gross national saving", ("CAP",), ("HH", "NFC", "FC", "GOV"), "s1_9.gross_savings.current", 2.0),
    ],
)
def test_saving_by_sector_vs_nas_1_9(what, rows, cols, sid, tol):
    rr = G(*rows) if isinstance(rows, tuple) else rows
    cc = G(*cols) if isinstance(cols, tuple) else cols
    close(s(rr, cc), nas("s1_9", sid), tol, f"{what} saving vs NAS 1.9")


def test_fc_public_and_private_saving():
    fc = ["E_RBI", "E_BANK", "E_NBFC", "E_INSP"]
    pub = s(G("CAP"), fc, comps=["public"])
    priv = s(G("CAP"), fc, comps=["private"])
    close(pub + priv, s(G("CAP"), fc), 1e-6, "FC saving is all public or private components")
    close(pub, nas("s1_9", "s1_9.public_financial_corporations.current"), 1.5, "public FC saving")
    close(priv, nas("s1_9", "s1_9.private_financial_corporations.current"), 1.5, "private FC saving")


def test_household_gdi_within_the_sum_of_its_parts_tolerances():
    """GDI = PFCE + saving + D1. Each part is held by its own band: PFCE hh.c1.total +-1, saving K4 +-0.5, and D1 is
    written as D2 + D3 + D4 (DECISIONS D2-3), which differs from the published residual by a fixed amount measured
    here. The balanced SAM misses NAS 1.14 by -1.61 = -1.00 (PFCE) - 0.50 (saving) - 0.11 (D1): every part is inside
    its band, so the closure identity test's Rs 1 tolerance, not the SAM, is what fails (finding BS-3)."""
    hh = G("HH")
    d1_gap = abs(s(["X_DISC"], hh) - nas("derived_residuals", "derived.household_residual.current"))
    tol = 1.0 + 0.5 + d1_gap + NUM
    gdi = s(G("COM"), hh) + s(["K_HH"], hh) + s(["X_DISC"], hh)
    close(gdi, nas("s1_14", "s1_14.households_npish.gross_disposable_income.current"), tol, "household GDI")


def test_gndi():
    sav = s(G("CAP"), G("HH", "NFC", "FC", "GOV"))
    gndi = sav + s(G("COM"), G("HH", "GOV")) + s(["X_DISC"], G("HH"))
    close(gndi, nas("s1_1", "s1_1.gndi.current"), 3.0, "GNDI vs NAS 1.1")


# ---------------------------------------------------------------------------------------------
# X_DISC and fixed entries unchanged; anchored boxes; signs; no entry near zero; every constraint in its band
# ---------------------------------------------------------------------------------------------


def test_fixed_entries_and_x_disc_unchanged():
    c = _con()
    assert c.execute("select count(*) from b where role = 'fixed' and balanced <> prior").fetchone()[0] == 0
    n = c.execute("select count(*) from b where (row = 'X_DISC' or col = 'X_DISC') and role <> 'fixed'").fetchone()[0]
    assert n == 0, "an X_DISC entry is not fixed"
    close(s(["X_DISC"], None), s(None, ["X_DISC"]), BAL_TOL, "X_DISC row vs column")
    close(s(["X_DISC"], None), nas("derived_residuals", "derived.household_residual.current"), 1.0, "D1 vs published")


def test_anchored_entries_inside_their_boxes():
    bad = (
        _con()
        .execute(
            "select row, col, ref, component, prior, balanced, tol_rel from b where role = 'anchored'"
            " and abs(balanced / prior - 1) > tol_rel * (1 + 1e-9) + 1e-12"
        )
        .fetchall()
    )
    assert not bad, bad


def test_no_sign_flip_and_no_entry_driven_towards_zero():
    """z = balanced / prior. Stated plausibility bounds for this audit: 0.1 <= z <= 10 for every entry of Rs 1 crore
    or more (measured range 0.517 to 1.936 on the 03:00 run; 0.155 to 6.46 on the Wave C run of 05:41, re-verification
    2026-10-01: the new bands bind and E_NFPU's surplus lands on its weak flows, fincorp-37)."""
    c = _con()
    assert c.execute("select count(*) from b where sign(prior) <> sign(balanced)").fetchone()[0] == 0
    bad = c.execute("select row, col, ref, component, prior, balanced from b where abs(prior) >= 1"
                    " and (balanced / prior < 0.1 or balanced / prior > 10)").fetchall()  # fmt: skip
    assert not bad, bad


def _constraint_mask(rows, cols, refs, comps) -> str:
    w = [_in("row", rows.split(",")), _in("col", cols.split(","))]
    if refs:
        w.append(_in("ref", refs.split(",")))
    if comps:
        w.append(_in("component", comps.split(",")))
    return " and ".join(w)


def _constraints() -> list[tuple]:
    return (
        _con()
        .execute("select constraint_id, kind, rows, cols, refs, components, target, tol_abs, tol_rel from k order by 1")
        .fetchall()
    )


def _band(kind, target, tol_abs, tol_rel) -> tuple[float, float]:
    tol = max(tol_abs, tol_rel * abs(target))
    lo, hi = target - tol, target + tol
    return (lo if kind != "max" else -math.inf), (hi if kind != "min" else math.inf)


def test_every_declared_constraint_holds_on_the_balanced_sam():
    cons = _constraints()
    assert len(cons) > 300
    bad = []
    for cid, kind, rows, cols, refs, comps, target, ta, tr in cons:
        got = _con().execute(f"select coalesce(sum(value), 0) from b where {_constraint_mask(rows, cols, refs, comps)}")
        v = float(got.fetchone()[0])
        lo, hi = _band(kind, target, ta, tr)
        if not (lo - 1e-4 <= v <= hi + 1e-4):
            bad.append((cid, kind, lo, hi, v))
    assert not bad, bad


def test_cross_entropy_stationarity_independently():
    """For every variable entry of Rs 1,000 crore or more (smaller ones carry 6-decimal rounding noise in ln z) that
    is in no constraint at a bound and strictly inside its box, the optimum of sum w|a|(z ln z - z + 1) requires
    w sign(a) ln z = lam[row] - lam[col] for one set of account multipliers. Fit lam by least squares and require
    the residual to vanish. Weights: anchored 16, free high 4, medium 1, low 0.25 (DESIGN_BRIEF s.5.1)."""
    codes = _accounts()[0]
    ent = (
        _con().execute("select row, col, ref, component, role, confidence, tol_rel, prior, balanced from b").fetchall()
    )
    in_bound = set()
    for _cid, kind, rows, cols, refs, comps, target, ta, tr in _constraints():
        m = _constraint_mask(rows, cols, refs, comps)
        v = float(_con().execute(f"select coalesce(sum(value), 0) from b where {m}").fetchone()[0])
        lo, hi = _band(kind, target, ta, tr)
        if min(abs(v - lo), abs(v - hi)) < 1e-3 * max(1.0, (hi - lo) / 2 if math.isfinite(hi - lo) else 1.0):
            in_bound |= set(_con().execute(f"select row, col, ref, component from b where {m}").fetchall())
    w_of = {"high": 4.0, "medium": 1.0, "low": 0.25}
    idx = {a: i for i, a in enumerate(codes)}
    A, g = [], []
    for row, col, ref, comp, role, conf, tol, a, x in ent:
        if role == "fixed" or abs(a) < 1000 or (row, col, ref, comp) in in_bound:
            continue
        z = x / a
        if role == "anchored" and abs(z - 1) >= tol * (1 - 1e-6):
            continue
        r = np.zeros(len(codes))
        r[idx[row]] += 1.0
        r[idx[col]] -= 1.0
        A.append(r)
        g.append((16.0 if role == "anchored" else w_of[conf]) * math.copysign(1.0, a) * math.log(z))
    A, g = np.array(A), np.array(g)
    assert len(g) > 1000
    lam, *_ = np.linalg.lstsq(A, g, rcond=None)
    res = np.abs(g - A @ lam)
    assert res.max() < 1e-6, f"stationarity residual {res.max():.3e} (max |w ln z| {np.abs(g).max():.3f})"


def test_duality_gap_and_primal_from_dual_independently():
    """Re-verification of the Wave C run (2026-10-01; the interior-point fallback of DECISIONS D2-23 produced it).
    A full KKT certificate from the published file alone: lambda per account and mu per band within 1e-3 crore of a
    bound are fitted by least squares (weighted by |x|, capped at 1e4, because the file's 6-decimal rounding puts
    noise of about 5e-7/|x| into ln z), then (1) every variable entry, interior or on its box, must equal
    a * clip(exp(-s (dlambda + sum mu) / w), box) within 1e-4 crore (stationarity and the sign at the bounds in one
    test), (2) no multiplier may sit on the wrong side (mu > 0 only at a top, mu < 0 only at a bottom), and (3) the
    own dual function q(lambda, mu) = sum_e min_box [c phi(z) + t_e z] + lambda.b - sigma(mu), a lower bound on the
    optimum for any multipliers, must be within 1e-8 relative of the objective (measured: 5.7e-12)."""
    codes = _accounts()[0]
    idx = {a: i for i, a in enumerate(codes)}
    n = len(codes)
    ent = (
        _con().execute("select row, col, ref, component, role, confidence, tol_rel, prior, balanced from b").fetchall()
    )
    row = np.array([idx[e[0]] for e in ent])
    col = np.array([idx[e[1]] for e in ent])
    ref = np.array([e[2] for e in ent], dtype=object)
    comp = np.array([e[3] for e in ent], dtype=object)
    role = np.array([e[4] for e in ent], dtype=object)
    a_all = np.array([e[7] for e in ent], float)
    x_all = np.array([e[8] for e in ent], float)
    var = np.flatnonzero(role != "fixed")
    w_of = {"high": 4.0, "medium": 1.0, "low": 0.25}
    w = np.array([16.0 if ent[i][4] == "anchored" else w_of[ent[i][5]] for i in var])
    a, x = a_all[var], x_all[var]
    z, sg, c = x / a, np.sign(a), w * np.abs(a)
    an = role[var] == "anchored"
    t = np.array([ent[i][6] if ent[i][6] is not None else np.nan for i in var], float)
    zlo, zhi = np.where(an, np.maximum(0.0, 1 - t), 0.0), np.where(an, 1 + t, np.inf)
    pos = -np.ones(len(ent), int)
    pos[var] = np.arange(len(var))
    rows_a, cols_a = np.array([e[0] for e in ent], dtype=object), np.array([e[1] for e in ent], dtype=object)
    lo_b, hi_b, mem = [], [], []
    for _cid, kind, rows, cols, refs, comps, target, ta, tr in _constraints():
        m = np.isin(rows_a, rows.split(",")) & np.isin(cols_a, cols.split(","))
        if refs:
            m &= np.isin(ref, refs.split(","))
        if comps:
            m &= np.isin(comp, comps.split(","))
        lo, hi = _band(kind, target, ta, tr)
        lo_b.append(lo)
        hi_b.append(hi)
        mem.append(np.flatnonzero(m))
    lo_b, hi_b = np.array(lo_b), np.array(hi_b)
    bsum = np.array([x_all[m].sum() for m in mem])
    top = np.isfinite(hi_b) & (bsum >= hi_b - 1e-3)
    bot = np.isfinite(lo_b) & (bsum <= lo_b + 1e-3)
    act = [k for k in range(len(mem)) if len(mem[k]) and (top[k] or bot[k])]
    ri, ci = row[var], col[var]
    A = np.zeros((len(var), n + len(act)))
    off = ri != ci
    A[np.flatnonzero(off), ri[off]] += (sg / w)[off]
    A[np.flatnonzero(off), ci[off]] -= (sg / w)[off]
    for j, k in enumerate(act):
        mv = pos[mem[k]]
        mv = mv[mv >= 0]
        A[mv, n + j] += (sg / w)[mv]
    lnz = np.log(z)
    on_box = (np.isfinite(zhi) & (z >= zhi - 1e-6 / np.abs(a))) | ((zlo > 0) & (z <= zlo + 1e-6 / np.abs(a)))
    fit = ~on_box & (np.abs(x) >= 1.0)
    sw = np.minimum(np.abs(x[fit]), 1e4)[:, None]
    sol = np.linalg.lstsq(A[fit] * sw, -lnz[fit] * sw[:, 0], rcond=None)[0]
    rec = a * np.clip(np.exp(-(A @ sol)), zlo, zhi)
    assert np.abs(rec - x).max() < 1e-4, f"primal-from-dual: an entry is {np.abs(rec - x).max():.2e} crore off"
    mu = np.zeros(len(mem))
    mu[act] = sol[n:]
    wrong = [k for k in act if (mu[k] > 1e-7 and not top[k]) or (mu[k] < -1e-7 and not bot[k])]
    assert not wrong, f"{len(wrong)} band multipliers on the wrong side"
    lam = sol[:n]
    const = np.where(role == "fixed", a_all, 0.0)
    bvec = np.bincount(row, const, n) - np.bincount(col, const, n)
    te = np.zeros(len(var))
    te[off] = a[off] * (lam[ri[off]] - lam[ci[off]])
    sig = 0.0
    for k in np.flatnonzero(mu != 0):
        mv = pos[mem[k]]
        mv = mv[mv >= 0]
        te[mv] += a[mv] * mu[k]
        sig += mu[k] * ((hi_b[k] if mu[k] > 0 else lo_b[k]) - const[mem[k]].sum())
    zs = np.clip(np.exp(np.clip(-te / c, -700, 700)), zlo, zhi)
    q = float(np.sum(c * (zs * np.log(zs) - zs + 1) + te * zs)) + float(lam @ bvec) - sig
    f = float(np.sum(c * (z * np.log(z) - z + 1)))
    assert -1e-6 <= f - q <= 1e-8 * max(1.0, f), f"duality gap {f - q:.3e} on objective {f:,.3f}"


# ---------------------------------------------------------------------------------------------
# (d) no over-threshold move without an explanation
# ---------------------------------------------------------------------------------------------


def _need(prior: float, bal: float) -> bool:
    d = abs(bal - prior)
    return d >= 5000.0 or (d >= 500.0 and d >= 0.1 * abs(prior))  # DESIGN_BRIEF s.5.3


@cache
def _items() -> list[dict]:
    files = sorted((ROOT / "pipeline" / "sam" / "explanations").glob("*.yaml"))
    files.append(ROOT / "pipeline" / "sam" / "explanations.yaml")
    out = []
    for f in files:
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        for it in doc.get("explanations") or []:
            out.append({**it, "file": f.stem})
    return out


@cache
def _needed() -> tuple[set, set]:
    ent = _con().execute("select row, col, ref, component, prior, balanced from b").fetchall()
    cells = _con().execute("select row, col, sum(prior), sum(balanced), count(*) from b group by all").fetchall()
    e_need = {(r, c, f, m) for r, c, f, m, a, x in ent if _need(a, x)}
    c_need = {(r, c) for r, c, a, x, n in cells if n > 1 and _need(a, x)}
    single = {(r, c) for r, c, a, x, n in cells if n == 1 and _need(a, x)}
    assert single <= {(r, c) for r, c, _f, _m in e_need}
    return e_need, c_need


def test_every_over_threshold_entry_and_cell_has_one_current_explanation():
    e_need, c_need = _needed()
    ent = {(r, c, f, m): (a, x, blk) for r, c, f, m, a, x, blk in
           _con().execute("select row, col, ref, component, prior, balanced, block from b").fetchall()}  # fmt: skip
    cells = {(r, c): (a, x) for r, c, a, x in
             _con().execute("select row, col, sum(prior), sum(balanced) from b group by all").fetchall()}  # fmt: skip
    keys, problems = [], []
    for it in _items():
        key = (it["row"], it["col"], str(it["ref"]), str(it["component"]))
        keys.append(key)
        if key[2] == "*":
            got = cells.get(key[:2])
            if key[:2] not in c_need:
                problems.append(("cell item for a cell that does not need one", key))
        else:
            got = ent.get(key)
            if key not in e_need:
                problems.append(("entry item for an entry that does not need one", key))
            elif got[2] != it["file"]:
                problems.append(("entry item outside its block's file", key, it["file"]))
        if got is None:
            problems.append(("item for nothing in the SAM", key))
            continue
        ce, ca = float(it["balanced"]) - float(it["prior"]), got[1] - got[0]
        if abs(ca - ce) > max(500.0, 0.2 * abs(ce)):  # SAM_GUIDE s.12 staleness rule
            problems.append(("stale item", key, ce, ca))
    assert len(keys) == len(set(keys)), "an item is explained twice"
    covered = set(keys)
    problems += [("entry without an item", k) for k in sorted(e_need - covered)]
    problems += [("cell without an item", k) for k in sorted(c_need) if (*k, "*", "*") not in covered]
    assert not problems, problems[:20]


def test_explanations_cite_registry_sources_and_figures():
    reg = set()
    for f in [ROOT / "data" / "registry.yaml", *sorted((ROOT / "data" / "registry_additions").glob("*.yaml"))]:
        for src in (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("sources") or []:
            reg.add(src["id"])
            reg.update(src.get("aliases") or [])
    bad = []
    for it in _items():
        srcs, why = it.get("sources") or [], str(it.get("why") or "")
        if not srcs or any(x not in reg for x in srcs):
            bad.append(("sources", it["row"], it["col"], it["ref"], it["component"], srcs))
        if len(why) < 150 or not any(ch.isdigit() for ch in why):
            bad.append(("why too thin", it["row"], it["col"], it["ref"], it["component"]))
    assert not bad, bad[:20]


@pytest.mark.xfail(
    strict=True,
    reason="BS-1 (owner fincorp): after the Wave C fix of 2026-10-01 (R17, K2a RBI, bond and dividend bands) 12 "
    "fincorp items still begin 'Unexplained': the E_NFPU flows that carry its prior surplus of 3.13 lakh "
    "(fincorp-37, government-33, a NAD question). They are honest findings, and BALANCING.md now counts the "
    "verdicts. Remove this xfail when the E_NFPU prior is repaired or the owner accepts them at Checkpoint B.",
)
def test_no_explanation_item_says_unexplained():
    bad = [(it["file"], it["row"], it["col"], it["ref"], it["component"]) for it in _items()
           if str(it.get("why") or "").lstrip().lower().startswith("unexplained")]  # fmt: skip
    assert not bad, f"{len(bad)} items say 'Unexplained': {bad[:5]}"


# ---------------------------------------------------------------------------------------------
# economic plausibility against the blocks' own sources (confirmed defects are strict xfails)
# ---------------------------------------------------------------------------------------------


# BS-5 (government-31) was a strict xfail here: balancing had taken R9a + R10 + R18 to +10.0% over NAS 4.2 COFOG.
# Fixed 2026-10-01 (Wave C): PM-KISAN moved to R10 and gov.cofog.current_transfers (+-5%) is declared, so the xfail
# was removed by the fixing agent as this file asks; the test itself is unchanged.
def test_gg_current_transfers_within_5pct_of_nas_4_2():
    want = nas("s4_2", "s4_2.current_transfer.total.current")
    # Re-verification 2026-10-01: the declared band gov.cofog.current_transfers is the same +-5% and binds at its top
    # (+5.0000%, margin 1e-6 crore), so NUM is added as for every other test that sits on a declared band edge
    close(s(None, None, ["R9a", "R10", "R18"]), want, 0.05 * want + NUM, "R9a + R10 + R18 vs NAS 4.2 current transfers")


# BS-6 (government-33) was a strict xfail here: R9d railways had gone 59,802 -> 1,11,414 against its AFS source.
# Fixed 2026-10-01 (Wave C): gov.r9d.railways / gov.r9d.posts (+-10%) are declared; xfail removed, test unchanged.
def test_r9d_railway_pensions_within_10pct_of_the_afs():
    want = clean("union_fiscal", "union_fiscal_afs", "afs.pa_disbursements.i_railway_funds")
    # Re-verification 2026-10-01: gov.r9d.railways (+-10%) binds at its top (+10.0000%, margin 1e-6 crore): + NUM
    close(s(G("HH"), ["E_NFPU"], ["R9d"], ["railways"]), want, 0.10 * want + NUM, "R9d railways vs AFS Railway Funds")
