"""Independent verification of the SAM `taxes` block (Phase 2 verifier, 2026-09-30; SPEC s.3 rule 3).

This file does NOT import pipeline.sam (no block, helper, framework or spec code) and does not use polars.
Every expected number is recomputed here with DuckDB SQL plus plain Python / numpy from:
- data/clean/union_fiscal: Receipt Budget 2025-26 actuals (rb.tr.*), Finance Accounts St 8/9, Expenditure
  Profile St 7, PPAC exchequer 2023-24, PIB GST (Apr-May 2023);
- data/clean/state_fiscal: RBI State Finances App I (all States + UTs, accounts 2023-24), FC16 subsidies and
  State accounts (MH 0028, 2022-23), cityfinance ULB property tax;
- data/clean/io_tables: SUT 2023-24 supply/use by product, the IFPRI 2022-23 data paper (T8, T11);
- data/clean/mospi_nas_2026: Statements 1.1, 4.2, 7.1 and the old-base (2011-12) sequence of accounts 2022-23;
- data/clean/finsector_markets, rbi_banking_corporate, rbi_financial_accounts: IRDAI tax provisions, RBI RTP
  tax provisions (vintage 2025-12-29), FSF balance sheets (end-March 2024);
- data/concordance/io_tables_sut_product_to_sam34.csv;
- the DEPENDS outputs the block legitimately reads: production's P7 constraint targets and P8/P9/P10 entries,
  households' `hh_group_map` and `hh_national_quintile_xwalk`, factors' F1a (F_LREG) entries;
- data/sam/2023-24/blocks/*_entries.parquet of all built blocks (double counting, tax-account closure).

The P7a split (product taxes by type within commodity) is re-implemented from the method text of the block's
P7a provenance record and plan s.2.1: the product-level prior is rebuilt and fitted with an own RAS, so all
136 P7a cells are a census, not a sample. It is compared with the block's written outputs
(data/sam/2023-24/blocks/taxes_*): a census of all 180 entries, all 22 constraint targets and the recomputable
satellite rows.

Findings are recorded in docs/phase2/verify/taxes.md (V-TX-n). A confirmed defect is a strict xfail with its id.

Maintainer update (2026-09-30): V-TX-1, V-TX-2 and V-TX-3 were fixed in the block. Expectations changed only where
those defects were pinned (the E_BANK public/private split in t4a(), the `non_pol_vat` component in p7a_prior() and
the entry count / component set, the three former xfails, now ordinary tests); every other expectation is the
verifier's. Dispositions: docs/phase2/issues/taxes.md, "Verification dispositions".

Wave C (2026-10-01): the fixing agents changed p10a() (PM-KISAN out of the Union's D39 heads, taxes-28), added
t4a.nfpu to expected_constraints() (BS-10, taxes-29), and changed the PM-KISAN lines of
test_double_counting_guards_with_government, test_s7_and_classification_satellites_are_as_published and
test_v_tx_2_.... A different agent re-verified every one of these against its own recomputation on 2026-10-01
(docs/phase2/verify/taxes.md, "Re-verification (wave C close-out, 2026-10-01)") and kept them; it added
test_wave_c_reverification_* below (findings V-TX-6..8).
"""

# ruff: noqa: E501  (long SQL / series ids are kept on one line)
from __future__ import annotations

import csv
import hashlib
import json
from functools import cache
from pathlib import Path

import duckdb
import numpy as np
import pytest

pytestmark = [pytest.mark.quality, pytest.mark.sam]

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean"
BLOCKS = ROOT / "data" / "sam" / "2023-24" / "blocks"
TSAT = BLOCKS / "taxes_satellites"
HSAT = BLOCKS / "households_satellites"
TOL = 0.01  # Rs crore, census tolerance (entries are written to 6 decimals; the RAS converges to ~1e-9 rel)
YEAR = "2023-24"
OLD = "2022-23"
RTP = "2025-12-29"
HH = ["H_R1", "H_R2", "H_R3", "H_R4", "H_R5", "H_U1", "H_U2", "H_U3", "H_U4", "H_U5"]
PT = ["T_CGST", "T_SGST", "T_GCES", "T_UEXC", "T_SVAT", "T_SEXC", "T_OPRT"]  # product-tax accounts
UNITS = ["mospi_nas_2026", "io_tables", "union_fiscal", "state_fiscal", "finsector_markets", "rbi_banking_corporate",
         "rbi_financial_accounts", "hces_consumption"]  # fmt: skip


def _p(path: Path) -> str:
    return path.as_posix()


@cache
def con() -> duckdb.DuckDBPyConnection:
    for f in ("taxes_entries", "taxes_constraints", "taxes_provenance", "taxes_checks"):
        if not (BLOCKS / f"{f}.parquet").exists():
            pytest.fail(f"{f}.parquet missing: run `uv run python -m pipeline sam taxes`")
    return duckdb.connect()


def _rows(sql: str) -> list[tuple]:
    return con().execute(sql).fetchall()


def _file(ds: str) -> str:
    unit = next(u for u in UNITS if ds.startswith(u))
    return _p(CLEAN / unit / f"{ds}.parquet")


def val(ds: str, sid: str, period: str = YEAR, vintage: str | None = None) -> float:
    """One clean value: exactly one row of the named (or, if None, the latest) vintage."""
    rows = _rows(f"select vintage, value from '{_file(ds)}' where series_id='{sid}' and period='{period}'")
    assert rows, f"{ds}: {sid} {period} missing"
    vint = vintage or max(r[0] for r in rows)
    sel = [r[1] for r in rows if r[0] == vint]
    assert len(sel) == 1, f"{ds}: {sid} {period} {vint}: {len(sel)} rows"
    return sel[0]


def rb(sid: str, period: str = YEAR) -> float:
    return val("union_fiscal_rb_receipts", sid, period)


def sf(code: str) -> float:
    return val("state_fiscal_rbi_sf_appendices", f"app1.total_revenue.{code}.in.all_states_uts.actuals")


def _sumlike(ds: str, prefix: str, period: str) -> float:
    rows = _rows(f"select series_id, vintage, value from '{_file(ds)}' where starts_with(series_id, '{prefix}') and period='{period}'")
    latest: dict[str, tuple[str, float]] = {}
    for sid, vint, v in rows:
        if sid not in latest or vint > latest[sid][0]:
            latest[sid] = (vint, v)
    assert latest, f"{ds}: nothing under {prefix} {period}"
    return sum(v for _, v in latest.values())


# ------------------------------------------------------------------------------------------ block outputs
@cache
def entries() -> dict[tuple[str, str, str, str], tuple]:
    """(row, col, ref, component) -> (value, status, role, tol_rel, confidence, prov_id)."""
    f = _p(BLOCKS / "taxes_entries.parquet")
    return {(r[0], r[1], r[2], r[3]): r[4:] for r in
            _rows(f"select row, col, ref, component, value, status, role, tol_rel, confidence, prov_id from '{f}'")}  # fmt: skip


@cache
def constraints() -> dict[str, tuple]:
    f = _p(BLOCKS / "taxes_constraints.parquet")
    return {r[0]: r[1:] for r in _rows(
        f"select constraint_id, ref, rows, cols, refs, components, target, tol_abs, tol_rel, kind, prov_id from '{f}'")}  # fmt: skip


def e(row: str, col: str, ref: str, comp: str = "total") -> float:
    return entries()[row, col, ref, comp][0]


def sat(name: str) -> str:
    return _p(TSAT / f"{name}.parquet")


# ------------------------------------------------------------------------------------------ cash receipts
@cache
def cash() -> dict:
    """Union (Receipt Budget) and State (RBI SF App I) cash heads by SAM tax account and government."""
    c = {
        # Union
        ("T_CGST", "G_CEN", "cgst"): rb("rb.tr.0005.central_goods_and_services_tax_cgst"),
        ("T_CGST", "G_CEN", "igst"): rb("rb.tr.0008.integrated_goods_and_services_tax_igst"),
        ("T_CGST", "G_CEN", "utgst"): rb("rb.tr.0007.union_territories_goods_and_services_tax_utgst"),
        ("T_GCES", "G_CEN", "cess"): rb("rb.tr.0009.gst_compensation_cess"),
        ("T_UEXC", "G_CEN", "excise"): rb("rb.tr.total.total_union_excise_duties"),
        ("T_SVAT", "G_CEN", "ut_sales_tax"): rb("rb.tr.0710.sales_tax"),
        ("T_SEXC", "G_CEN", "ut_state_excise"): rb("rb.tr.0710.state_excise_duties"),
        ("T_OPRT", "G_CEN", "ut_vehicle_tax"): rb("rb.tr.0710.taxes_on_vehicles"),
        ("T_OPRT", "G_CEN", "ut_goods_passengers"): rb("rb.tr.0710.taxes_on_goods_and_passengers"),
        ("T_OPRT", "G_CEN", "ut_electricity_duty"): rb("rb.tr.0710.taxes_and_duties_on_electricity"),
        ("T_OPRT", "G_CEN", "service_tax"): rb("rb.tr.total.total_service_tax"),
        ("T_OPRT", "G_CEN", "mh0045"): rb("rb.tr.total.total_other_taxes_and_duties_on_commodities_and_services"),
        ("T_OPRT", "G_CEN", "export_duty"): rb("rb.tr.0037.export_duty") + rb("rb.tr.0037.cesses_on_exports"),
        ("T_OPRT", "G_CEN", "ctt"): rb("rb.tr.total.total_commodity_transaction_tax"),
        # States + UTs with legislature
        ("T_SGST", "G_STA", "sgst"): sf("i.a.3.vii-state_goods_and_services_tax"),
        ("T_SVAT", "G_STA", "sales_tax"): sf("i.a.3.i-sales_tax"),
        ("T_SEXC", "G_STA", "state_excise"): sf("i.a.3.ii-state_excise"),
        ("T_OPRT", "G_STA", "vehicle_tax"): sf("i.a.3.iii-taxes_on_vehicles"),
        ("T_OPRT", "G_STA", "goods_passengers"): sf("i.a.3.iv-taxes_on_goods_and_passengers"),
        ("T_OPRT", "G_STA", "electricity_duty"): sf("i.a.3.v-taxes_and_duties_on_electricity"),
        ("T_OPRT", "G_STA", "entertainment"): sf("i.a.3.vi-entertainment_tax"),
        ("T_OPRT", "G_STA", "other_taxes"): sf("i.a.3.viii-other_taxes_and_duties"),
    }
    return c


def cash_acct(a: str, gov: str | None = None) -> float:
    return sum(v for (acct, g, _), v in cash().items() if acct == a and (gov is None or g == gov))


def cash_item(item: str) -> float:
    return next(v for (_, _, i), v in cash().items() if i == item)


@cache
def direct_cash() -> dict[str, float]:
    mh21 = _sumlike("union_fiscal_rb_receipts", "rb.tr.0021.", YEAR)
    d = {
        "mh0021": mh21,
        "stt": rb("rb.tr.0034.security_transaction_tax"),
        "firm_heads": rb("rb.tr.0023.hotel_receipts_tax") + rb("rb.tr.0024.interest_tax") + rb("rb.tr.0026.fringe_benefit_tax"),
        "mh0028": _sumlike("union_fiscal_rb_receipts", "rb.tr.0028.", YEAR),
        "wealth": rb("rb.tr.0031.estate_duty") + rb("rb.tr.0032.taxes_on_wealth"),
        "taxes_on_income": rb("rb.tr.total.total_taxes_on_income"),
        "cit": rb("rb.tr.total.total_corporation_tax"),
        "customs": rb("rb.tr.total.total_customs"),
        "professions": sf("i.a.1.ii-taxes_on_professions_trades_callings_and_employm"),
        "agri_income": sf("i.a.1.i-agricultural_income_tax"),
        "state_income": sf("i.a.1-taxes_on_income"),
    }
    return d


# ------------------------------------------------------------------------------------------ SUT by product
@cache
def conc() -> dict[str, str]:
    with open(ROOT / "data" / "concordance" / "io_tables_sut_product_to_sam34.csv", encoding="utf-8") as fh:
        return {f"sut_p{int(r['sut_product']):03d}": r["commodity"] for r in csv.DictReader(fh)}


def _sut_vec(ds: str, item: str) -> dict[str, float]:
    return dict(_rows(f"select product, sum(value) from '{_file(ds)}' where period='{YEAR}' and item_code='{item}' and starts_with(product, 'sut_p') group by product"))


@cache
def sut() -> dict:
    return {
        "tax": {p: v for p, v in _sut_vec("io_tables_sut_supply", "product_taxes").items() if v != 0},
        "sub": _sut_vec("io_tables_sut_supply", "product_subsidies"),
        "imports": _sut_vec("io_tables_sut_supply", "imports"),
        "pfce": _sut_vec("io_tables_sut_use", "pfce"),
        "gfcf": _sut_vec("io_tables_sut_use", "gfcf"),
        "exports": _sut_vec("io_tables_sut_use", "exports"),
        "total_tax": val("io_tables_sut_supply", "supply.product_taxes.total.current"),
        "total_sub": val("io_tables_sut_supply", "supply.product_subsidies.total.current"),
        "total_import_duty": val("io_tables_sut_supply", "supply.import_duty.total.current"),
    }


@cache
def prod() -> dict:
    fe = _p(BLOCKS / "production_entries.parquet")
    fc = _p(BLOCKS / "production_constraints.parquet")
    cols = {cid.split(".", 1)[1].upper(): t for cid, t in
            _rows(f"select constraint_id, target from '{fc}' where starts_with(constraint_id, 'product_taxes.')")}  # fmt: skip
    by_ref = {ref: dict(_rows(f"select col, sum(value) from '{fe}' where ref='{ref}' group by col")) for ref in ("P9", "P10")}
    p8 = _rows(f"select sum(value) from '{fe}' where ref='P8'")[0][0]
    return {"cols": cols, "p9": by_ref["P9"], "p10": sum(by_ref["P10"].values()), "p8": p8}


# ------------------------------------------------------------------------------------------ P7a
PPAC = "union_fiscal_ppac_exchequer"
P_POL, P_GAS, P_CRUDE, P_ALCO, P_ELEC = "sut_p085", "sut_p043", "sut_p044", "sut_p065", "sut_p128"
NON_GST = {P_POL, P_GAS, P_CRUDE, P_ALCO, P_ELEC}
CESS_BASE = ["sut_p064", "sut_p066", "sut_p069", "sut_p120"]
CESS_FACTOR = 0.5  # stated in the P7a record's method text


def _pro(total: float, w: dict[str, float]) -> dict[str, float]:
    w = {k: x for k, x in w.items() if x > 0}
    s = sum(w.values())
    return {k: total * x / s for k, x in w.items()} if total else {}


@cache
def p7a_prior() -> list[tuple[str, str, str, str, float]]:
    """(account, component, item, product, value): the product-level prior of the P7a method text."""
    s, tax = sut(), sut()["tax"]
    pp = {k: val(PPAC, f"ppac.{k}") for k in ("centre.a.excise_duty", "centre.a.cess_on_crude_oil", "centre.a.nccd_on_crude_oil",
                                               "centre.a.cgst", "centre.a.igst", "states.a.sgst_utgst",
                                               "states.a.sales_tax_vat_on_pol_products", "states.a.entry_tax_others",
                                               "states.a.octroi_duties_incl_electricity_duty")}  # fmt: skip
    placed = dict.fromkeys(tax, 0.0)
    loads: list[tuple[str, str, str, str, float]] = []

    def put(a: str, item: str, amt: dict[str, float], comp: str = "total") -> None:
        for p, x in amt.items():
            assert p in tax, (item, p)
            if x > 0:
                loads.append((a, comp, item, p, x))
                placed[p] += x

    def room(p: str) -> float:
        return max(0.0, tax.get(p, 0.0) - placed.get(p, 0.0))

    rc, rs = cash_acct("T_CGST"), cash_acct("T_SGST")
    put("T_UEXC", "ppac_excise", {P_POL: pp["centre.a.excise_duty"]})
    put("T_UEXC", "crude_cess", _pro(pp["centre.a.cess_on_crude_oil"] + pp["centre.a.nccd_on_crude_oil"], {P_CRUDE: tax[P_CRUDE], P_GAS: tax[P_GAS]}))
    put("T_SVAT", "ppac_vat", {P_POL: pp["states.a.sales_tax_vat_on_pol_products"]})
    entry_octroi = pp["states.a.entry_tax_others"] + pp["states.a.octroi_duties_incl_electricity_duty"]
    put("T_OPRT", "ppac_entry_octroi", {P_POL: entry_octroi})
    put("T_CGST", "ppac_gst", {P_POL: pp["centre.a.cgst"] + pp["centre.a.igst"] * rc / (rc + rs)})
    put("T_SGST", "ppac_gst", {P_POL: pp["states.a.sgst_utgst"] + pp["centre.a.igst"] * rs / (rc + rs)})
    put("T_UEXC", "tobacco", {"sut_p069": cash_acct("T_UEXC") - pp["centre.a.excise_duty"] - pp["centre.a.cess_on_crude_oil"] - pp["centre.a.nccd_on_crude_oil"]})
    sexc = cash_acct("T_SEXC")
    on_alco = min(sexc, room(P_ALCO))
    put("T_SEXC", "alcohol", {P_ALCO: on_alco})
    put("T_SEXC", "licence", _pro(sexc - on_alco, {"sut_p134": tax["sut_p134"], "sut_p132": tax["sut_p132"]}), "licence_fee_excess")
    put("T_OPRT", "electricity", {P_ELEC: cash_item("electricity_duty") + cash_item("ut_electricity_duty")})
    veh = ["sut_p120", "sut_p121", "sut_p122"]
    put("T_OPRT", "vehicle", _pro(cash_item("vehicle_tax") + cash_item("ut_vehicle_tax"), {p: s["pfce"].get(p, 0) + s["gfcf"].get(p, 0) for p in veh}))
    put("T_OPRT", "goods_passengers", {"sut_p136": cash_item("goods_passengers") + cash_item("ut_goods_passengers")})
    put("T_OPRT", "entertainment", {"sut_p155": cash_item("entertainment")})
    put("T_OPRT", "equalisation", _pro(cash_item("mh0045"), {p: s["imports"].get(p, 0) for p in ("sut_p149", "sut_p141")}))
    put("T_OPRT", "export_duty", _pro(cash_item("export_duty"), {p: s["exports"].get(p, 0) for p in tax if int(p[5:]) <= 126}))
    put("T_OPRT", "ctt", {"sut_p142": cash_item("ctt")})
    # V-TX-3 fixed (2026-09-30): the non-POL VAT residual is its own component, `non_pol_vat` (low confidence)
    put("T_SVAT", "non_pol_vat", _pro(cash_acct("T_SVAT") - pp["states.a.sales_tax_vat_on_pol_products"], {p: room(p) for p in (P_ALCO, P_GAS, P_POL)}), "non_pol_vat")
    other = cash_item("service_tax") + cash_item("other_taxes") - entry_octroi
    put("T_OPRT", "other", _pro(max(0.0, other), {p: room(p) for p in tax if p not in NON_GST}))
    res = {p: room(p) for p in tax if p not in NON_GST}
    base = {p: CESS_FACTOR * res.get(p, 0.0) for p in CESS_BASE}
    cess = cash_acct("T_GCES")
    if sum(base.values()) >= cess:
        put("T_GCES", "cess_base", _pro(cess, base))
    else:
        put("T_GCES", "cess_base", base)
        put("T_GCES", "cess_spread", _pro(cess - sum(base.values()), {p: x for p, x in res.items() if p not in CESS_BASE and p != "sut_p042"}))
    for p in sorted(res):
        g = room(p)
        if g > 0:
            put("T_CGST", "gst", {p: g * rc / (rc + rs)})
            put("T_SGST", "gst", {p: g * rs / (rc + rs)})
    return loads


@cache
def p7a() -> dict:
    """Own RAS of the aggregated prior to the SUT columns (production's targets) and the scaled cash rows."""
    cm = conc()
    cells: dict[tuple[str, str, str], float] = {}
    for a, comp, _, p, x in p7a_prior():
        k = (a, comp, cm[p])
        cells[k] = cells.get(k, 0.0) + x
    dropped = {k: x for k, x in cells.items() if x < 1e-3}
    cells = {k: x for k, x in cells.items() if x >= 1e-3}
    cols = {c: t for c, t in prod()["cols"].items() if t > 0}
    rows_cash = {a: cash_acct(a) for a in PT}
    scale = sum(cols.values()) / sum(rows_cash.values())
    rows = {a: x * scale for a, x in rows_cash.items()}
    keys = sorted(cells)
    x = np.array([cells[k] for k in keys])
    ri = np.array([PT.index(k[0]) for k in keys])
    cl = sorted(cols)
    ci = np.array([cl.index(k[2]) for k in keys])
    rt = np.array([rows[a] for a in PT])
    ct = np.array([cols[c] for c in cl])
    for _ in range(500_000):  # column first, then row: a different order than the builder's RAS on purpose
        x *= (ct / np.bincount(ci, weights=x, minlength=len(cl)))[ci]
        x *= (rt / np.bincount(ri, weights=x, minlength=len(PT)))[ri]
        err = max(np.max(np.abs(np.bincount(ci, weights=x, minlength=len(cl)) / ct - 1)),
                  np.max(np.abs(np.bincount(ri, weights=x, minlength=len(PT)) / rt - 1)))  # fmt: skip
        if err < 1e-12:
            break
    else:
        raise AssertionError(f"own RAS did not converge ({err:.2e})")
    return {"cells": dict(zip(keys, x.tolist(), strict=True)), "prior": {k: cells[k] for k in keys}, "rows": rows,
            "rows_cash": rows_cash, "cols": cols, "scale": scale, "dropped": dropped}  # fmt: skip


# ------------------------------------------------------------------------------------------ T1a / T2x
@cache
def receipts() -> dict[tuple[str, str, str, str], float]:
    rt = {a: sum(x for (acct, _, _), x in p7a()["cells"].items() if acct == a) for a in PT}
    out: dict[tuple[str, str, str, str], float] = {}
    for a in PT:
        c, s = cash_acct(a, "G_CEN"), cash_acct(a, "G_STA")
        if a == "T_CGST":
            ut = cash_item("utgst")
            out["G_CEN", a, "T1a", "total"] = rt[a] * (c - ut) / (c + s)
            out["G_CEN", a, "T1a", "utgst"] = rt[a] * ut / (c + s)
            continue
        if c:
            out["G_CEN", a, "T1a", "total"] = rt[a] * c / (c + s)
        if s:
            out["G_STA", a, "T2x", "total"] = rt[a] * s / (c + s)
    d = direct_cash()
    out["G_CEN", "T_CUST", "T1a", "total"] = prod()["p8"]
    out["G_CEN", "T_PIT", "T1a", "total"] = d["taxes_on_income"] + d["wealth"]
    out["G_CEN", "T_CIT", "T1a", "total"] = d["cit"]
    out["G_STA", "T_PIT", "T2x", "total"] = d["state_income"]
    return out


# ------------------------------------------------------------------------------------------ T3 / T3a / T4a
@cache
def t3() -> dict:
    d = direct_cash()
    d5_hh = val("mospi_nas_2026_oldbase_soa_s5_0", "oldbase_soa_s5_0.secondary_distribution_of_income.uses.d5.current", OLD)
    mh21_old = _sumlike("union_fiscal_rb_receipts", "rb.tr.0021.", OLD)
    pt_old = _sumlike("state_fiscal_fc16_state_accounts", "fa.revenue_receipts.mh0028.in-", OLD)
    h = (d5_hh - pt_old) / mh21_old
    ucb = val("rbi_banking_corporate_rtp_coop", "rtp.ucb_pl.tax_provisions.ucb.current", vintage=RTP)
    qc = (1 - h) * d["mh0021"] + d["firm_heads"]
    hh_union = h * d["mh0021"] + d["stt"] + d["mh0028"] + d["wealth"]
    ifpri = val("io_tables_ifpri_2223_datapaper", "ifpri.t8.taxes.households.current", OLD) / mh21_old
    return {"h": h, "ifpri": ifpri, "qc": qc, "qc_bank": ucb, "qc_nfpr": qc - ucb, "hh_union": hh_union,
            "hh_total": hh_union + d["state_income"], "pt_old": pt_old, "mh21_old": mh21_old, "d5_hh_old": d5_hh}  # fmt: skip


@cache
def t3a() -> dict:
    f = _p(HSAT / "hh_group_map.parquet")
    tab: dict[str, dict] = {}
    for cls, g, m, x in _rows(f"select hces_class, household_group, measure, value from '{f}' where measure in ('persons','households','avg_mpce')"):
        tab.setdefault(cls, {"group": g})[m] = x
    assert len(tab) == 24
    hces = sum(r["persons"] * r["avg_mpce"] * 12 for r in tab.values()) / 1e7
    k = val("mospi_nas_2026_s1_1", "s1_1.pfce.current") / hces
    rate = {f"q{i}": val("io_tables_ifpri_2223_datapaper", f"ifpri.t11.savings_rate.q{i}", OLD) / 100 for i in range(1, 6)}
    fx = _p(HSAT / "hh_national_quintile_xwalk.parquet")
    w: dict[str, dict[str, float]] = {}
    for g, q, x in _rows(f"select household_group, national_quintile, value from '{fx}' where measure='persons'"):
        w.setdefault(g, {})[q] = x
    s = {g: sum(x * rate[q] for q, x in w[g].items()) / sum(w[g].values()) for g in HH}
    inc = {cls: 12 * r["avg_mpce"] * r["persons"] / r["households"] * k / (1 - s[r["group"]]) for cls, r in tab.items()}
    keys = {}
    for th in (500_000.0, 700_000.0, 1_000_000.0):
        kk = dict.fromkeys(HH, 0.0)
        for cls, r in tab.items():
            kk[r["group"]] += r["households"] * max(0.0, inc[cls] - th)
        tot = sum(kk.values())
        keys[th] = {g: x / tot for g, x in kk.items()}
    ff = _p(BLOCKS / "factors_entries.parquet")
    ce = dict(_rows(f"select row, sum(value) from '{ff}' where ref='F1a' and col='F_LREG' group by row"))
    return {"k": k, "hces": hces, "saving": s, "income": inc, "keys": keys, "ce": ce, "tab": tab}


@cache
def t4a() -> dict:
    d5 = {k: val(f"mospi_nas_2026_oldbase_soa_{s}", f"oldbase_soa_{s}.secondary_distribution_of_income.uses.d5.current", OLD)
          for k, s in (("pub_nfc", "s2_1"), ("pvt_nfc", "s2_2"), ("pub_fc", "s3_1"), ("pvt_fc", "s3_2"))}  # fmt: skip
    sh = {k: x / sum(d5.values()) for k, x in d5.items()}
    t = t3()
    corp = direct_cash()["cit"] + t["qc"]
    sec = {k: corp * x for k, x in sh.items()}
    life = val("finsector_markets_irdai_life", "t24.provision_for_tax.insurers_life.current") + val("finsector_markets_irdai_life", "t25.provision_for_tax.insurers_life.current")
    lic = val("finsector_markets_irdai_life", "t24.provision_for_tax.lic.current") + val("finsector_markets_irdai_life", "t25.provision_for_tax.lic.current")
    nl = {g: val("finsector_markets_irdai_nonlife", f"t51.provision_for_tax.{g}.current") for g in ("general_public", "general_private", "health_standalone", "general_specialized")}
    insp_pub = lic + nl["general_public"] + nl["general_specialized"]
    insp_pvt = life - lic + nl["general_private"] + nl["health_standalone"]
    nb = "rbi_banking_corporate_rtp_nbfi"
    ul = val(nb, "rtp.nbfc_layer_pl.tax_provisions.nbfc_ul.current", vintage=RTP)
    ml = val(nb, "rtp.nbfc_layer_pl.tax_provisions.nbfc_ml.current", vintage=RTP)
    hfc = val(nb, "rtp.hfc_pl.tax_provisions.hfc.current", vintage=RTP)
    aifi = val(nb, "rtp.aifi_pl.tax_provisions.aifi.current", vintage=RTP)
    st = {k: val("rbi_financial_accounts_fsf_balance_sheets", f"fsf.fc_{k}.assets.outstanding.total.all.current", "2024-03-31")
          for k in ("odc_nbfc_dt", "ofc_nbfc_ndt", "odc_hfc_dt", "ofc_hfc_ndt")}  # fmt: skip
    dt_n = st["odc_nbfc_dt"] / (st["odc_nbfc_dt"] + st["ofc_nbfc_ndt"])
    dt_h = st["odc_hfc_dt"] / (st["odc_hfc_dt"] + st["ofc_hfc_ndt"])
    to_bank = (ul + ml) * dt_n + hfc * dt_h
    nbfc = ul + ml + hfc + aifi - to_bank
    pub_ratio = sh["pub_fc"] / (sh["pub_fc"] + sh["pvt_fc"])
    nbfc_pub = aifi + (nbfc - aifi) * pub_ratio
    # V-TX-1 fixed (2026-09-30, plan s.2.7 step 4): E_BANK (the FC residual) is split public/private by RTP 2023-24
    # net profit (PSB + RRB vs PVB + FB + SFB + PB + LAB) on the banks' own part; the XR-6 deposit-taking share is private
    fc = sec["pub_fc"] + sec["pvt_fc"] - t["qc_bank"]
    bank = fc - insp_pub - insp_pvt - nbfc
    rb_ = "rbi_banking_corporate_rtp_banks"
    npf = {g: val(rb_, f"rtp.scb_pl.net_profit.{g}.current", vintage=RTP) for g in ("psb", "pvb", "fb", "sfb", "pb")}
    npf["rrb"] = val(rb_, "rtp.rrb_pl.net_profit.rrb.current", vintage=RTP)
    npf["lab"] = val(rb_, "rtp.lab_pl.net_profit.lab.current", vintage=RTP)
    bank_share = (npf["psb"] + npf["rrb"]) / sum(npf.values())
    cells = {
        ("E_NFPU", "total"): sec["pub_nfc"],
        ("E_NFPR", "total"): sec["pvt_nfc"] - t["qc_nfpr"],
        ("E_INSP", "public"): insp_pub,
        ("E_INSP", "private"): insp_pvt,
        ("E_NBFC", "public"): nbfc_pub,
        ("E_NBFC", "private"): nbfc - nbfc_pub,
        ("E_BANK", "public"): (bank - to_bank) * bank_share,
        ("E_BANK", "private"): (bank - to_bank) * (1 - bank_share) + to_bank,
    }
    return {"cells": cells, "shares": sh, "corp": corp, "nbfc": nbfc, "insp": insp_pub + insp_pvt,
            "fc": fc, "to_bank": to_bank, "dt_n": dt_n, "dt_h": dt_h, "bank_share": bank_share,
            "scb_groups": sum(v for g, v in npf.items() if g not in ("rrb", "lab"))}  # fmt: skip


# ------------------------------------------------------------------------------------------ P9a / P10a
EXP = "union_fiscal_exp_profile"


@cache
def p9a() -> dict:
    p9 = prod()["p9"]
    aasha = val(EXP, "stat7.other_subsidies.pradhan_mantri_annadata_aay_sanrakshan_yojna")
    miss = val(EXP, "stat7.interest_subsidies.modified_interest_subvention_scheme")
    air = sut()["sub"]["sut_p137"]
    food = _sumlike("state_fiscal_fc16_subsidies", "sub.food.in-", YEAR)
    rows: list[tuple[str, str, float]] = []  # commodity, payer, value
    unexpl: dict[str, float] = {}
    for c, x in sorted(p9.items()):
        if c in ("C_CHEM", "C_TREQ", "C_RPET"):
            rows.append((c, "G_CEN", x))
        elif c in ("C_UTIL", "C_LVST", "C_FOFI"):
            rows.append((c, "G_STA", x))
        elif c == "C_CROP":
            rows += [(c, "G_CEN", -aasha), (c, "G_STA", x + aasha)]
        elif c == "C_FINS":
            rows += [(c, "G_CEN", -miss), (c, "G_STA", x + miss)]
        elif c == "C_TRNS":
            rows += [(c, "G_CEN", air), (c, "G_STA", x - air)]
        elif c == "C_TRAD":
            rows.append((c, "G_STA", -food))
            unexpl[c] = x + food
        else:
            unexpl[c] = x
    cen = sum(x for _, g, x in rows if g == "G_CEN")
    sta = sum(x for _, g, x in rows if g == "G_STA")
    ratio = cen / (cen + sta)
    for c, x in unexpl.items():
        rows += [(c, "G_CEN", x * ratio), (c, "G_STA", x * (1 - ratio))]
    return {"rows": rows, "ratio": ratio, "centre_identified": cen, "food": food,
            "G_CEN": sum(x for _, g, x in rows if g == "G_CEN"), "G_STA": sum(x for _, g, x in rows if g == "G_STA")}  # fmt: skip


@cache
def p10a() -> dict:
    d39 = val("mospi_nas_2026_s4_2", "s4_2.subsidy.total.current") - val("mospi_nas_2026_s1_1", "s1_1.subsidies_on_products.current")
    net = prod()["p10"]
    d29 = d39 + net
    heads = {
        ("G_CEN", "stamps_registration"): rb("rb.tr.0030.stamps_duty_judicial_court_fees_released_in_stamps") + rb("rb.tr.0710.stamps_and_registration"),
        ("G_CEN", "land_revenue"): rb("rb.tr.0710.land_revenue"),
        ("G_STA", "stamps_registration"): sf("i.a.2.ii-stamps_and_registration_fees"),
        ("G_STA", "land_revenue"): sf("i.a.2.i-land_revenue"),
        ("G_STA", "property_tax"): sf("i.a.2.iii-urban_immovable_property_tax") + val("state_fiscal_ulb_cityfinance", "ulb.property_tax.in.all_ulbs_in_dump"),
    }
    heads["G_STA", "other_production_taxes"] = d29 - sum(heads.values())
    # PM-KISAN left the Union's D39 heads in the Wave C audit fix (government-30, 2026-10-01; re-verified 2026-10-01):
    # inferred to sit in NAS 4.2 COFOG 04.agri current transfers (V-TX-8); it is government's R10 pm_kisan
    items = {
        "interest_subsidies_other": val(EXP, "stat7.interest_subsidies") - val(EXP, "stat7.interest_subsidies.modified_interest_subvention_scheme")
        - val(EXP, "stat7.interest_subsidies.interest_subsidy_to_lic_for_pension_plan_for_senior_citizens"),
        "other_subsidies_other": val(EXP, "stat7.other_subsidies") - val(EXP, "stat7.other_subsidies.pradhan_mantri_annadata_aay_sanrakshan_yojna"),
        "fc16_union_business": val("state_fiscal_fc16_subsidies", "sub.business.in.gg_centre"),
    }
    heads["G_CEN", "gross_subsidies"] = -sum(items.values())
    heads["G_STA", "gross_subsidies"] = -(d39 - sum(items.values()))
    return {"d39": d39, "d29": d29, "net": net, "heads": heads, "items": items}


# ------------------------------------------------------------------------------------------ expected entries
@cache
def expected() -> dict[tuple[str, str, str, str], float]:
    out: dict[tuple[str, str, str, str], float] = {}
    for (a, comp, c), x in p7a()["cells"].items():
        out[a, c, "P7a", comp] = x
    out.update(receipts())
    t = t3()
    out["T_PIT", "E_NFPR", "T3", "quasi_corporate"] = t["qc_nfpr"]
    out["T_PIT", "E_BANK", "T3", "quasi_corporate"] = t["qc_bank"]
    k, ce = t3a()["keys"][700_000.0], t3a()["ce"]
    for g in HH:
        if k[g] > 0:
            out["T_PIT", g, "T3a", "income_tax"] = t["hh_union"] * k[g]
        if ce.get(g, 0) > 0:
            out["T_PIT", g, "T3a", "professions_tax"] = direct_cash()["state_income"] * ce[g] / sum(ce.values())
    for (a, comp), x in t4a()["cells"].items():
        out["T_CIT", a, "T4a", comp] = x
    p = p9a()
    out["G_CEN", "T_PSUB", "P9a", "total"] = p["G_CEN"]
    out["G_STA", "T_PSUB", "P9a", "total"] = p["G_STA"]
    for (g, comp), x in p10a()["heads"].items():
        out[g, "T_PROD", "P10a", comp] = x
    return out


@cache
def expected_constraints() -> dict[str, float]:
    d, t, p = direct_cash(), t3(), p10a()
    return {
        "p7a.total": sum(p7a()["cols"].values()),
        "p9a.total": sum(prod()["p9"].values()),
        "p9a.centre": p9a()["centre_identified"],
        "p10a.net": p["net"],
        "p10a.gross_taxes": p["d29"],
        "p10a.gross_subsidies": -p["d39"],
        "p10a.centre_net": sum(x for (g, _), x in p["heads"].items() if g == "G_CEN"),
        "t1.cgst": cash_acct("T_CGST", "G_CEN"),
        "t1.gces": cash_acct("T_GCES", "G_CEN"),
        "t1.uexc": cash_acct("T_UEXC", "G_CEN"),
        "t1.cust": d["customs"] - cash_item("export_duty"),
        "t1.pit": d["taxes_on_income"] + d["wealth"],
        "t1.cit": d["cit"],
        "t2.sgst": cash_acct("T_SGST", "G_STA"),
        "t2.svat": cash_acct("T_SVAT", "G_STA"),
        "t2.sexc": cash_acct("T_SEXC", "G_STA"),
        "t3.total": d["taxes_on_income"] + d["wealth"] + d["state_income"],
        "t3.households": t["hh_total"],
        "t4.total": d["cit"],
        "t4a.fc": t4a()["fc"],
        "t4a.insp": t4a()["insp"],
        "t4a.nbfc": t4a()["nbfc"],
        "t4a.nfpu": t4a()["cells"][("E_NFPU", "total")],  # Wave C audit fix (BS-10): old-base public NFC share, 25%
    }


# ======================================================================================== tests
def test_cash_identities_hold():
    d = direct_cash()
    # RB 'total taxes on income' = MH 0021 + STT + firm-only heads + MH 0028 (the T3/T1 mapping relies on it)
    assert abs(d["mh0021"] + d["stt"] + d["firm_heads"] + d["mh0028"] - d["taxes_on_income"]) < 0.02
    assert abs(d["professions"] + d["agri_income"] - d["state_income"]) < 0.01
    # TAX-4 and RB gross = FA net + minor head 901
    assert abs(cash_item("cgst") + cash_item("igst") + cash_item("cess") - rb("rb.tr.total.total_goods_and_services_tax_gst")) < 0.01
    fa = "union_fiscal_fa_receipts"
    for rbv, tot, h901 in ((cash_item("cgst"), "fa8.0005.total", "fa8.0005.00.901"), (d["cit"], "fa8.0020.total", "fa8.0020.00.901"),
                           (d["mh0021"], "fa8.0021.total", "fa8.0021.00.901"), (d["customs"], "fa8.0037.total", "fa8.0037.00.901"),
                           (cash_item("excise"), "fa8.0038.total", "fa8.0038.01.901")):  # fmt: skip
        assert abs(rbv - (val(fa, tot) - val(fa, h901))) < 0.02, tot
    # the SUT C_OILG product tax equals PPAC cess + NCCD on crude (taxes-4)
    oilg = sum(x for p, x in sut()["tax"].items() if conc()[p] == "C_OILG")
    assert abs(oilg - val(PPAC, "ppac.centre.a.cess_on_crude_oil") - val(PPAC, "ppac.centre.a.nccd_on_crude_oil")) < 0.01


def test_p7a_column_targets_are_the_sut():
    cols: dict[str, float] = {}
    for p, x in sut()["tax"].items():
        cols[conc()[p]] = cols.get(conc()[p], 0.0) + x
    pc = prod()["cols"]
    assert {c for c, t in pc.items() if t} == set(cols)
    assert all(abs(pc[c] - cols[c]) < 1e-6 for c in cols)
    assert abs(sum(cols.values()) - sut()["total_tax"]) < 1e-3
    assert pc["C_DWEL"] == 0 and pc["C_PADM"] == 0


def test_p7a_prior_drops_only_the_logged_cell():
    # taxes-6: the only prior cell below Rs 0.001 crore is the export-duty share of crude on C_OILG
    dropped = p7a()["dropped"]
    assert list(dropped) == [("T_OPRT", "total", "C_OILG")] and dropped["T_OPRT", "total", "C_OILG"] < 1e-3


def test_entry_census_matches_recomputation():
    exp, got = expected(), entries()
    assert set(got) == set(exp), (sorted(set(got) - set(exp)), sorted(set(exp) - set(got)))
    diffs = {k: got[k][0] - x for k, x in exp.items() if abs(got[k][0] - x) > TOL}
    assert not diffs, diffs
    assert len(got) == 181  # 180 + the (T_SVAT, C_RPET) non_pol_vat component (V-TX-3 fix)


def test_p7a_margins_and_scale():
    f = p7a()
    # the scaling factor that spreads the TAX-1 gap (taxes-1) and the row totals of the entries
    assert abs(f["scale"] - 1.015965) < 5e-7
    for a in PT:
        got = sum(r[0] for k, r in entries().items() if k[0] == a and k[2] == "P7a")
        assert abs(got - f["rows"][a]) < TOL, a
    for c, t in f["cols"].items():
        got = sum(r[0] for k, r in entries().items() if k[1] == c and k[2] == "P7a")
        assert abs(got - t) < TOL, c
    # the gap itself (taxes-1): SUT product taxes less Union + State product-tax cash receipts
    assert abs(sut()["total_tax"] - sum(f["rows_cash"].values()) - 47_383.10) < 0.05


def test_p7a_structure_and_roles():
    p = {k: r for k, r in entries().items() if k[2] == "P7a"}
    assert all(r[0] > 0 and r[1] == "estimated" and r[2] == "free" for r in p.values())
    cols = {k[1] for k in p}
    assert "C_DWEL" not in cols and "C_PADM" not in cols
    assert not any(k[0] == "T_GCES" and k[1] == "C_COAL" for k in p)
    assert not any(k[0] in ("T_CGST", "T_SGST", "T_GCES") and k[1] == "C_OILG" for k in p)
    assert {k[1] for k in p if k[0] == "T_SVAT"} == {"C_RPET"}  # taxes-3: all State VAT lands on POL
    assert {k[1] for k in p if k[0] == "T_UEXC"} == {"C_RPET", "C_OILG", "C_BVTB"}
    assert {k[3] for k in p} == {"total", "licence_fee_excess", "non_pol_vat"}  # non_pol_vat: V-TX-3 fix
    assert {(k[0], k[1]) for k in p if k[3] == "licence_fee_excess"} == {("T_SEXC", "C_HOTL"), ("T_SEXC", "C_TRAD")}


def test_other_entries_roles_statuses_signs():
    E = entries()
    assert E["G_CEN", "T_CUST", "T1a", "total"][1:3] == ("official", "fixed")
    for k in (("G_CEN", "T_PIT", "T1a", "total"), ("G_CEN", "T_CIT", "T1a", "total")):
        assert E[k][1:4] == ("official", "anchored", 0.005)
    assert E["G_STA", "T_PIT", "T2x", "total"][1:4] == ("official", "anchored", 0.01)
    for k, r in E.items():
        if k[2] in ("P9a",) or k[3] == "gross_subsidies":
            assert r[0] < 0, k
        else:
            assert r[0] > 0, k
        if r[2] == "free":
            assert r[4] in ("high", "medium", "low") and r[3] is None, k
        if r[2] == "anchored":
            assert r[3] and r[3] > 0 and r[4] is None, k
    assert all(r[4] == "low" for k, r in E.items() if k[2] in ("T3", "T3a"))
    assert not any(k[1] == "E_RBI" for k in E)
    for comp in ("stamps_registration", "land_revenue", "property_tax"):
        for g in ("G_CEN", "G_STA"):
            if (g, "T_PROD", "P10a", comp) in E:
                assert E[g, "T_PROD", "P10a", comp][1:4] == ("derived", "anchored", 0.03)


def test_constraint_targets_census():
    exp, got = expected_constraints(), constraints()
    assert set(got) == set(exp)
    for cid, x in exp.items():
        assert abs(got[cid][5] - x) < TOL, (cid, got[cid][5], x)
    # production's per-commodity P7 constraints are the column margin; the entries meet them exactly
    fc = _p(BLOCKS / "production_constraints.parquet")
    for cid, t, tol in _rows(f"select constraint_id, target, tol_abs from '{fc}' where starts_with(constraint_id, 'product_taxes.')"):
        got_c = sum(r[0] for k, r in entries().items() if k[2] == "P7a" and k[1] == cid.split(".")[1].upper())
        assert abs(got_c - t) <= max(tol, 1e-6), cid


def test_constraints_hold_on_the_block_entries():
    E = entries()
    for cid, (_, rows, cols, refs, comps, target, tol_abs, tol_rel, _kind, _) in constraints().items():
        rs, cs = rows.split(","), cols.split(",")
        rf = refs.split(",") if refs else None
        cp = comps.split(",") if comps else None
        s = sum(r[0] for k, r in E.items() if k[0] in rs and k[1] in cs and (rf is None or k[2] in rf) and (cp is None or k[3] in cp))
        assert abs(s - target) <= max(tol_abs, tol_rel * abs(target)) + 1e-6, (cid, s, target)


def test_tax_accounts_close_on_the_assembled_prior():
    rows = _rows(f"select row, col, value from read_parquet('{_p(BLOCKS)}/*_entries.parquet')")
    acc: dict[str, float] = {}
    for r, c, x in rows:
        if r.startswith("T_"):
            acc[r] = acc.get(r, 0.0) + x
        if c.startswith("T_"):
            acc[c] = acc.get(c, 0.0) - x
    assert len(acc) == 12 and all(abs(x) < 1e-3 for x in acc.values()), acc


def test_no_other_block_writes_tax_cells():
    rows = _rows(f"select block, ref from read_parquet('{_p(BLOCKS)}/*_entries.parquet') where block <> 'taxes' and (starts_with(row, 'T_') or starts_with(col, 'T_')) group by all")
    assert set(rows) <= {("production", "P8"), ("production", "P9"), ("production", "P10")}, rows


def test_double_counting_guards_with_government():
    ge = _p(BLOCKS / "government_entries.parquet")
    g = _rows(f"select ref, row, col, component, value from '{ge}'")
    assert not [r for r in g if r[0] == "R16"]  # vehicle tax is a product tax here (D2-4)
    comps = {r[3] for r in g}
    assert not {c for c in comps if "vehicle" in c or "professions" in c or "stt" in c}
    # PM-KISAN: government's R10 (Wave C, government-30), and not in P10a here, so it is booked once
    kisan = sum(r[4] for r in g if r[0] == "R10" and r[3] == "pm_kisan")
    assert abs(kisan - val("union_fiscal_fa_expenditure", "fa9.2401.00.130")) < 0.01
    assert not _rows(f"select item from '{sat('p10a_items')}' where item = 'pm_kisan'")
    # LPG: 2,280 in P9 (SUT C_RPET), the rest of St 7 LPG in government R10 lpg_dbt
    lpg = sum(r[4] for r in g if r[0] == "R10" and r[3] == "lpg_dbt")
    assert abs(lpg + 2280.0 - val(EXP, "stat7.petroleum.lpg_subsidy")) < 0.5
    # State food subsidies booked here (XR-23): no State food component in government's C2a
    assert not [r for r in g if r[0] == "C2a" and r[2] == "G_STA" and "food" in r[3]]
    # R18 LIC pension subsidy excluded from P10a's interest subsidies (booked once, in government)
    assert any(r[0] == "R18" and r[3] == "lic_pension_subsidy" for r in g)


def test_t3_shares_and_bounds():
    t = t3()
    assert abs(t["h"] - 0.785483) < 1e-6 and abs(t["ifpri"] - 0.901733) < 1e-6
    hh_mh21 = sum(r[0] for k, r in entries().items() if k[2] == "T3a" and k[3] == "income_tax") - direct_cash()["stt"] - direct_cash()["mh0028"] - direct_cash()["wealth"]
    assert 0.78 <= hh_mh21 / direct_cash()["mh0021"] <= 0.91  # plan s.7 test 8 bounds


def test_t3a_key_and_sensitivity():
    k = t3a()
    assert abs(k["k"] - 2.2566) < 1e-4
    got = {(r[0], r[1]): r[2] for r in _rows(f"select household_group, threshold_rs, value from '{sat('t3a_sensitivity')}' where starts_with(series_id, 't3a.share.')")}
    for th, kk in k["keys"].items():
        for g, x in kk.items():
            assert abs(got[g, f"{th:.0f}"] - x) < 1e-8, (th, g)
    inc = dict(_rows(f"select series_id, value from '{sat('t3a_sensitivity')}' where starts_with(series_id, 't3a.fractile.')"))
    for cls, y in k["income"].items():
        assert abs(inc[f"t3a.fractile.income_per_household.{cls}"] - y) < 1e-3
    key7 = k["keys"][700_000.0]
    assert abs(key7["H_U5"] + key7["H_R5"] - 0.726) < 0.001  # taxes-8: below the gap map's expected > 90%
    assert [g for g in HH if key7[g] == 0] == ["H_R1", "H_R2", "H_R3", "H_R4", "H_U1"]


def test_t4a_and_direct_tax_split_satellite():
    t = t4a()
    assert abs(sum(t["cells"].values()) - direct_cash()["cit"]) < 1e-6
    ds = dict(_rows(f"select series_id, value from '{sat('direct_tax_split')}'"))
    for (a, c), x in t["cells"].items():
        assert abs(ds[f"t4a.{a.lower()}.{c}"] - x) < TOL
    assert abs(ds["t4a.detail.corporate_d5_prior"] - t["corp"]) < TOL
    assert abs(ds["t4a.detail.moved_to_e_bank"] - t["to_bank"]) < TOL
    assert abs(ds["t3.household_share_mh0021"] - t3()["h"]) < 1e-8
    for k, x in t["shares"].items():
        assert abs(ds[f"t4a.detail.old_base_share_{k}"] - x) < 1e-8
    # RTP vintage 2025-12-29, not 2024-12-26 (NBFC-ML 25,242 vs 23,958)
    assert ds["t4a.detail.nbfc_ml"] == 25242.0 and ds["t4a.detail.nbfc_ul"] == 13102.0


def test_p9a_and_p10a_satellites():
    p = p9a()
    got = {(r[0], r[1]): r[2] for r in _rows(f"select commodity, payer, sum(value) from '{sat('p9a_by_commodity')}' group by all")}
    exp: dict[tuple[str, str], float] = {}
    for c, g, x in p["rows"]:
        exp[c, g] = exp.get((c, g), 0.0) + x
    exp = {k: x for k, x in exp.items() if x != 0}
    assert set(got) == set(exp) and all(abs(got[k] - exp[k]) < TOL for k in exp)
    assert abs(p["ratio"] - 0.4600) < 5e-5 and abs(p["food"] - 54_463.3933) < 1e-3
    q = p10a()
    it = {(r[0], r[1]): r[2] for r in _rows(f"select government, item, value from '{sat('p10a_items')}' where government is not null")}
    for (g, comp), x in q["heads"].items():
        assert abs(it[g, comp] - x) < TOL
    for k, x in q["items"].items():
        assert abs(it["G_CEN", k] + x) < TOL
    der = dict(_rows(f"select item, value from '{sat('p10a_items')}' where government is null"))
    assert abs(der["gross_d39"] - q["d39"]) < TOL and abs(der["gross_d29"] - q["d29"]) < TOL
    # gross D29 is essentially full after the identified heads (taxes-13): no room for vehicle/professions tax
    assert 0 < q["heads"]["G_STA", "other_production_taxes"] < 1000


def test_p7a_precheck_satellite():
    f = p7a()
    got = {(r[0], r[1]): r[2] for r in _rows(f"select account, measure, value from '{sat('p7a_precheck')}' where kind='row'")}
    for a in PT:
        assert abs(got[a, "cash"] - f["rows_cash"][a]) < TOL
        assert abs(got[a, "cash_centre"] - cash_acct(a, "G_CEN")) < TOL and abs(got[a, "cash_states"] - cash_acct(a, "G_STA")) < TOL
        assert abs(got[a, "scaled_target"] - f["rows"][a]) < TOL and abs(got[a, "precheck_target"] - f["rows"][a]) < TOL
        assert abs(got[a, "final_over_cash"] - f["scale"]) < 1e-8
    cols = dict(_rows(f"select account, value from '{sat('p7a_precheck')}' where kind='column'"))
    assert set(cols) == set(f["cols"]) and all(abs(cols[c] - x) < TOL for c, x in f["cols"].items())


def test_p7b_satellite_adds_up_and_obeys_rules():
    rows = _rows(f"select tax_account, component, commodity, use, use_type, value from '{sat('p7b_tax_by_use')}'")
    by_parent: dict[tuple[str, str, str], float] = {}
    for a, comp, c, _, _, x in rows:
        by_parent[a, comp, c] = by_parent.get((a, comp, c), 0.0) + x
    p7 = {(k[0], k[3], k[1]): r[0] for k, r in entries().items() if k[2] == "P7a"}
    assert set(by_parent) == set(p7)
    assert all(abs(by_parent[k] - x) < TOL for k, x in p7.items())
    assert all(x > 0 for *_, x in rows)
    non_itc = {"A_CROP", "A_LVST", "A_FOFI", "A_UTIL", "A_RPET", "A_DWEL", "A_EDUC", "A_HLTH", "A_PADM", "A_OSRV", "A_FINS", "A_INSR", "A_BVTB"}
    for a, _, c, use, ut, _ in rows:
        if a in ("T_CGST", "T_SGST", "T_GCES", "T_UEXC", "T_SVAT", "T_SEXC"):
            assert ut != "exports", (a, c)
        if a in ("T_CGST", "T_SGST", "T_GCES"):
            assert ut != "cii" and (ut != "ic" or use in non_itc), (a, c, use)
            assert ut != "gfcf" or c in ("C_CNST", "C_TREQ"), (a, c)


def test_s7_and_classification_satellites_are_as_published():
    for sid, per, src, x in _rows(f"select series_id, period, source_series, value from '{sat('s7_igst_settlement')}'"):
        ds = "union_fiscal_pib_gst" if src.startswith("pib.") else "union_fiscal_fa_receipts"
        assert abs(val(ds, src, per) - x) < 1e-3, sid
    fa = "union_fiscal_fa_receipts"
    assert abs(val(fa, "fa8.0008.01.total") + val(fa, "fa8.0008.02.total") - val(fa, "fa8.0008.total")) < 0.01
    assert abs(val(fa, "fa8.0005.00.105") + val(fa, "fa8.0008.02.105")) < 0.01
    cl = dict(_rows(f"select item, value from '{sat('tax_classification')}'"))
    d = direct_cash()
    exp = {"vehicle_tax_states": cash_item("vehicle_tax"), "vehicle_tax_uts": cash_item("ut_vehicle_tax"), "stt": d["stt"],
           "professions_tax": d["professions"], "agricultural_income_tax": d["agri_income"], "ctt": cash_item("ctt"),
           "equalisation_levy_mh0045": cash_item("mh0045"), "export_duty": cash_item("export_duty"), "utgst": cash_item("utgst"),
           "union_excise_gross_incl_nccd": cash_item("excise"), "fertiliser_subsidy": val(EXP, "stat7.fertiliser"),
           "union_food_subsidy": val(EXP, "stat7.food"), "lpg_subsidy_in_p9": -prod()["p9"]["C_RPET"],
           "lpg_dbt_not_product_subsidy": val(EXP, "stat7.petroleum.lpg_subsidy") + prod()["p9"]["C_RPET"],
           "state_food_subsidies_fc16": p9a()["food"], "state_power_subsidies": -prod()["p9"]["C_UTIL"],
           "miss_interest_subvention": val(EXP, "stat7.interest_subsidies.modified_interest_subvention_scheme"),
           "pm_aasha": val(EXP, "stat7.other_subsidies.pradhan_mantri_annadata_aay_sanrakshan_yojna"), **p10a()["items"],
           "lic_pension_subsidy": val(EXP, "stat7.interest_subsidies.interest_subsidy_to_lic_for_pension_plan_for_senior_citizens"),
           "pm_kisan": val("union_fiscal_fa_expenditure", "fa9.2401.00.130")}  # fmt: skip  (pm_kisan: Wave C, booked in R10)
    assert set(cl) == set(exp)
    assert all(abs(cl[k] - x) < 1e-3 for k, x in exp.items())


def test_checks_pass_and_targets_are_clean_records():
    ck = {r[0]: r[1:] for r in _rows(f"select check_id, sam_value, target, ok, target_prov_id from '{_p(BLOCKS / 'taxes_checks.parquet')}'")}
    assert len(ck) == 16 and all(r[2] for r in ck.values())
    assert abs(ck["product_taxes_nas"][1] - val("mospi_nas_2026_s1_1", "s1_1.taxes_on_products.current")) < 1e-6
    assert abs(ck["p10a_net_nas71"][1] - val("mospi_nas_2026_s7_1", "s7_1.total.net_production_taxes.current")) < 1e-6
    assert abs(ck["t_cust_sut"][1] - sut()["total_import_duty"]) < 1e-6


def test_provenance_inputs_resolve_and_statuses_match():
    ids: dict[str, str] = {}
    for f in list(CLEAN.glob("*/_provenance.parquet")) + list(BLOCKS.glob("*_provenance.parquet")):
        ids.update(dict(_rows(f"select prov_id, status from '{_p(f)}'")))
    prov = {r[0]: (r[1], r[2], r[3]) for r in _rows(f"select prov_id, status, inputs, method from '{_p(BLOCKS / 'taxes_provenance.parquet')}'")}
    dangling = [(pid, i) for pid, (_, inputs, _) in prov.items() for i in (inputs or "").split(",") if i and i not in ids]
    assert not dangling, dangling
    for pid, (status, inputs, method) in prov.items():
        assert method
        if status == "official":
            assert inputs and all(ids[i] == "official" for i in inputs.split(",")), pid
        if status == "derived":
            assert inputs, pid
    for k, r in entries().items():
        assert prov[r[5]][0] == r[1], k
    for cid, c in constraints().items():
        assert c[9] in prov, cid
    for f in TSAT.glob("*.parquet"):
        for pid, st in _rows(f"select distinct prov_id, status from '{_p(f)}'"):
            assert prov[pid][0] == st, f.name
    for (pid,) in _rows(f"select distinct target_prov_id from '{_p(BLOCKS / 'taxes_checks.parquet')}'"):
        assert pid in ids
    # the T4a record cites the RTP 2025-12-29 records, not the 2024-12-26 ones
    rtp = {r[0]: r[1] for r in _rows(f"select prov_id, vintage from '{_file('rbi_banking_corporate_rtp_nbfi')}' where series_id like '%tax_provisions%' and period='{YEAR}'")}
    t4a_inputs = prov[entries()["T_CIT", "E_NFPR", "T4a", "total"][5]][1].split(",")
    assert {rtp[i] for i in t4a_inputs if i in rtp} == {RTP}


# ======================================================================================== confirmed findings
# V-TX-1, V-TX-2 and V-TX-3 were fixed by the taxes maintainer on 2026-09-30 (dispositions in
# docs/phase2/issues/taxes.md); their strict xfails are now ordinary tests of the fixed behaviour.
def test_v_tx_1_e_bank_public_share_near_psb_profit_share():
    rtp = "rbi_banking_corporate_rtp_banks"
    psb = val(rtp, "rtp.scb_pl.net_profit.psb.current", vintage=RTP) / val(rtp, "rtp.scb_pl.net_profit.scb.current", vintage=RTP)
    pub, pvt = e("T_CIT", "E_BANK", "T4a", "public"), e("T_CIT", "E_BANK", "T4a", "private")
    assert abs(psb - 0.4039) < 1e-3  # PSBs earn 40.4% of SCB net profit (the block gave public banks ~13% before the fix)
    assert 0.5 * psb <= pub / (pub + pvt) <= 1.5 * psb, (pub / (pub + pvt), psb)
    # the fix follows plan s.2.7 step 4: the RTP groups add up to SCB, and the key is PSB + RRB net profit
    t = t4a()
    assert abs(t["scb_groups"] - val(rtp, "rtp.scb_pl.net_profit.scb.current", vintage=RTP)) < 5
    assert abs(t["bank_share"] - 0.416487) < 1e-6
    ds = dict(_rows(f"select series_id, value from '{sat('direct_tax_split')}'"))
    assert abs(ds["t4a.detail.bank_public_share_net_profit"] - t["bank_share"]) < 1e-8


def test_v_tx_2_p10a_items_published_heads_not_labelled_estimated():
    st = dict(_rows(f"select item, status from '{sat('p10a_items')}' where government='G_CEN'"))
    assert st["fc16_union_business"] != "estimated", st
    assert st["fc16_union_business"] == "official"
    assert "pm_kisan" not in st  # Wave C (government-30): PM-KISAN is government's R10, not a P10a head
    assert st["interest_subsidies_other"] == st["other_subsidies_other"] == "derived"
    assert st["gross_subsidies"] == "estimated"  # the entry rows keep the P10a estimate record


def test_v_tx_3_fallback_heavy_cell_not_high_confidence():
    fallback = sum(x for a, _, item, p, x in p7a_prior() if a == "T_SVAT" and item == "non_pol_vat" and conc()[p] == "C_RPET")
    pr = p7a()["prior"]
    share = fallback / (pr["T_SVAT", "total", "C_RPET"] + pr["T_SVAT", "non_pol_vat", "C_RPET"])
    assert 0.27 < share < 0.29
    # the fallback sits in its own low-confidence component; the 'high' component is PPAC's VAT on POL only
    assert abs(pr["T_SVAT", "non_pol_vat", "C_RPET"] - fallback) < 1e-6
    assert abs(pr["T_SVAT", "total", "C_RPET"] - val(PPAC, "ppac.states.a.sales_tax_vat_on_pol_products")) < 1e-6
    assert entries()["T_SVAT", "C_RPET", "P7a", "non_pol_vat"][4] == "low"
    assert entries()["T_SVAT", "C_RPET", "P7a", "total"][4] == "high"


# ======================================================================================== wave C re-verification
# Added by the wave C re-verifier (2026-10-01); findings V-TX-6..8 in docs/phase2/verify/taxes.md.
def _clean_prov(ds: str, sid: str, period: str = YEAR) -> str:
    rows = _rows(f"select prov_id from '{_file(ds)}' where series_id='{sid}' and period='{period}'")
    assert len(rows) == 1, (ds, sid, rows)
    return rows[0][0]


def test_wave_c_reverification_p10a_without_pm_kisan():
    q, kisan = p10a(), val("union_fiscal_fa_expenditure", "fa9.2401.00.130")
    union = sum(q["items"].values())
    assert abs(union - 58_290.87) < 0.005 and abs(union + kisan - 1_09_907.78) < 0.005
    # the States' D39 residual rose by exactly PM-KISAN; gross D39 is unchanged
    assert abs(e("G_STA", "T_PROD", "P10a", "gross_subsidies") + (q["d39"] - union)) < TOL
    assert abs(e("G_STA", "T_PROD", "P10a", "gross_subsidies") + 2_32_228.97 + kisan) < 0.01  # was -2,32,228.97
    assert abs(e("G_CEN", "T_PROD", "P10a", "gross_subsidies") + e("G_STA", "T_PROD", "P10a", "gross_subsidies") + q["d39"]) < TOL
    # PM-KISAN is booked exactly once in the whole SAM: government R10 G_CEN -> households, = FA 2401.00.130
    k = _rows(f"select block, ref, col, sum(value) from read_parquet('{_p(BLOCKS)}/*_entries.parquet') where lower(component) like '%kisan%' group by all")
    assert len(k) == 1 and k[0][:3] == ("government", "R10", "G_CEN") and abs(k[0][3] - kisan) < 0.01, k
    # provenance: the P10a subsidy record no longer cites FA St 9; the classification record does
    fa9 = _clean_prov("union_fiscal_fa_expenditure", "fa9.2401.00.130")
    prov = dict(_rows(f"select prov_id, inputs from '{_p(BLOCKS / 'taxes_provenance.parquet')}'"))
    assert fa9 not in prov[entries()["G_CEN", "T_PROD", "P10a", "gross_subsidies"][5]].split(",")
    cl = {r[0]: r[1:] for r in _rows(f"select item, ref, sam_cell, government, prov_id from '{sat('tax_classification')}'")}
    assert cl["pm_kisan"][0] == "none" and cl["pm_kisan"][1].startswith("government R10") and cl["pm_kisan"][2] == "G_CEN"
    assert fa9 in prov[cl["pm_kisan"][3]].split(",")
    # the evidence the reclassification rests on (an inference, V-TX-8): NAS 4.2 GG current expenditure =
    # consumption + subsidies + current transfers, and 04.agri current transfers can hold PM-KISAN (88.5%)
    s42 = "mospi_nas_2026_s4_2"
    parts = sum(val(s42, f"s4_2.{s}.total.current") for s in ("consumption_expenditure", "subsidy", "current_transfer"))
    assert abs(val(s42, "s4_2.current_expenditure.total.current") - parts) < 0.01
    agri_ct = val(s42, "s4_2.current_transfer.04.agri.current")
    assert abs(agri_ct - 58_325.32) < 0.01 and 0.88 < kisan / agri_ct < 0.89
    c = constraints()["p10a.centre_net"]
    assert c[8] == "band" and c[7] == 0.30 and c[0] == "P10a" and c[1] == "G_CEN" and c[2] == "T_PROD"


def test_wave_c_reverification_t4a_nfpu_band():
    c, fc = constraints()["t4a.nfpu"], constraints()["t4a.fc"]
    assert (c[0], c[1], c[2], c[3], c[4]) == ("T4a", "T_CIT", "E_NFPU", "T4a", None)
    assert c[8] == "band" and c[7] == fc[7] == 0.25 and c[6] == 0.0
    assert abs(c[5] - t4a()["cells"]["E_NFPU", "total"]) < TOL
    assert c[9] == entries()["T_CIT", "E_NFPU", "T4a", "total"][5]  # the T4a (estimated) record
    # V-TX-6 (finding, not a defect of the arithmetic): the band is centred on the 2022-23 old-base public-NFC share of
    # corporate D5, the lowest of the 12-year old-base series in clean data; 2019-20..2021-22 were 8.0-10.4%
    sh = {}
    for per in ("2011-12", "2012-13", "2013-14", "2014-15", "2015-16", "2016-17", "2017-18", "2018-19", "2019-20", "2020-21", "2021-22", "2022-23"):
        d5 = {s: val(f"mospi_nas_2026_oldbase_soa_{s}", f"oldbase_soa_{s}.secondary_distribution_of_income.uses.d5.current", per)
              for s in ("s2_1", "s2_2", "s3_1", "s3_2")}  # fmt: skip
        sh[per] = d5["s2_1"] / sum(d5.values())
    assert abs(sh["2022-23"] - t4a()["shares"]["pub_nfc"]) < 1e-12 and min(sh, key=sh.get) == "2022-23"
    assert 0.080 < min(sh["2019-20"], sh["2020-21"], sh["2021-22"]) and max(sh["2019-20"], sh["2020-21"], sh["2021-22"]) < 0.105


def test_wave_c_reverification_balanced_edges_as_reported():
    run = json.loads((ROOT / "data" / "sam" / "2023-24" / "balancing_run.json").read_text(encoding="utf-8"))
    for kind in ("entries", "constraints"):
        h = hashlib.sha256((BLOCKS / f"taxes_{kind}.parquet").read_bytes()).hexdigest()
        if run["block_inputs"]["taxes"][kind] != h:
            pytest.xfail("the balanced run predates the current taxes build; re-check taxes-29/30 after re-balancing")
    bc = {r[0]: r[1:] for r in _rows(f"select declared_by, lo, hi, balanced_sum, binding from '{_p(ROOT / 'data' / 'sam' / '2023-24' / 'balancing_constraints.parquet')}' where starts_with(declared_by, 'taxes:')")}
    for cid in ("t1.cgst", "t1.gces", "t1.uexc", "t4a.nfpu", "p10a.centre_net"):  # taxes-29 / taxes-30 (BS-9, BS-10)
        lo, hi, got, binding = bc[f"taxes:{cid}"]
        assert binding and abs(got - hi) < 0.01, (cid, lo, hi, got)
    assert abs(bc["taxes:t1.cgst"][1] - 1.05 * cash_acct("T_CGST", "G_CEN")) < 0.01
    assert abs(bc["taxes:t4a.nfpu"][1] - 1.25 * t4a()["cells"]["E_NFPU", "total"]) < 0.01
    assert abs(bc["taxes:p10a.centre_net"][1] - 0.70 * expected_constraints()["p10a.centre_net"]) < 0.01


def _stale() -> list[str]:
    doc = json.loads((BLOCKS / "taxes_block.json").read_text(encoding="utf-8"))
    out = []
    for dep, hashes in doc["dependency_hashes"].items():
        for kind, h in hashes.items():
            if hashlib.sha256((BLOCKS / f"{dep}_{kind}.parquet").read_bytes()).hexdigest() != h:
                out.append(f"{dep}_{kind}")
    return out


def test_block_is_not_stale_against_its_dependencies():
    stale = _stale()
    if stale:
        pytest.xfail(f"taxes is stale against {stale}: rebuild taxes (then government)")
