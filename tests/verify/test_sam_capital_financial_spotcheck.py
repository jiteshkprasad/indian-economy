"""Independent verification of the SAM `capital_financial` block (Phase 2 verifier, 2026-10-01; SPEC s.3 rule 3).

This file does NOT import pipeline.sam (no block, helper, framework or spec code) and does not use polars.
Every expected number is recomputed here with DuckDB SQL plus plain Python / numpy from:
- data/clean/io_tables (SUT 2023-24 use: GFCF by product, valuables, CII) and the committed concordance
  data/concordance/io_tables_sut_product_to_sam34.csv;
- data/clean/mospi_nas_2026: St 1.9, 1.11, 1.14, 5.3, 7.2A/7.2B and the derived S-I errors and omissions;
- data/clean/union_fiscal (Finance Accounts St 9 capital heads, IGAS-2 capital grants, NSSF, AFS),
  data/clean/state_fiscal (RBI State Finances App IV capital outlay);
- data/clean/rbi_financial_accounts: FSF 2023-24 balance sheets (leaf statements, transactions), Statement 7,
  T52(a)/(b); data/clean/rbi_banking_corporate: RBI Annual Report 2023-24 (fixed assets, depreciation, surplus
  payable), RTP 2023-24 (HDFC merger lines);
- the DEPENDS outputs the block legitimately reads: fincorp's `fc_public_private` satellite, government's K8e
  entries, rest_of_world's `row_financial_counterparts` satellite, households' `hh_keys`;
- data/sam/2023-24/blocks/*_entries.parquet of all built blocks (K9, market clearing, double counting).

Coverage: a census of all 444 entries (I1a by an own RAS; the FSF reconciliation at cell level: 101 cells), all
19 constraint targets, all 24 check targets, and the recomputable rows of the ten satellites.
Findings: docs/phase2/verify/capital_financial.md (V-CF-n). V-CF-1 (the block was stale against government's
2026-10-01 00:15 rebuild) was recorded with conditional xfails; fixed by the builder's rebuild (2026-10-01), so they are
ordinary assertions now (a stale block fails them). With V-CF-1 the builder also adopted the recommended key change:
IGAS-2 capital grants to statutory bodies and development authorities join the Centre's GG GFCF key (government
A-K6-4 / V-GOV-7), so the key recomputed below includes them and the pinned Centre share is 0.4553743.
"""

# ruff: noqa: E501  (long SQL / series ids are kept on one line)
from __future__ import annotations

import csv
import glob
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
SAT = BLOCKS / "capital_financial_satellites"
YEAR = "2023-24"
TOL = 0.01  # Rs crore (entries are written to 6 decimals; the block's RAS stops at 1e-9 relative)
DOM = ("K_HH", "K_NFPU", "K_NFPR", "K_RBI", "K_BANK", "K_NBFC", "K_INSP", "K_MUTF", "K_GCEN", "K_GSTA")
HH = ["H_R1", "H_R2", "H_R3", "H_R4", "H_R5", "H_U1", "H_U2", "H_U3", "H_U4", "H_U5"]

# FSF leaf statement -> SAM capital account (plan s.2.0; XR-6: ODC incl. HDFC Ltd = K_BANK)
LEAF = {"fc_rbi": "K_RBI", "fc_odc_scb": "K_BANK", "fc_odc_coop": "K_BANK", "fc_odc_nbfc_dt": "K_BANK",
        "fc_odc_hfc_dt": "K_BANK", "fc_ofc_aifi": "K_NBFC", "fc_ofc_sfc": "K_NBFC", "fc_ofc_sidc": "K_NBFC",
        "fc_ofc_nbfc_ndt": "K_NBFC", "fc_ofc_hfc_ndt": "K_NBFC", "fc_ofc_mf": "K_MUTF", "fc_ofc_icpf_ins": "K_INSP",
        "fc_ofc_icpf_pf": "K_INSP", "gg_cen": "K_GCEN", "gg_sta": "K_GSTA", "nfc_pub": "K_NFPU", "nfc_pvt": "K_NFPR"}  # fmt: skip
CODE2ACC = {"fc_rbi": "K_RBI", "fc_odc": "K_BANK", "gg_cen": "K_GCEN", "gg_sta": "K_GSTA", "nfc_pub": "K_NFPU", "nfc_pvt": "K_NFPR"}
ACC2CODE = {v: k for k, v in CODE2ACC.items()} | {"K_NBFC": "fc_ofc", "K_MUTF": "fc_ofc", "K_INSP": "fc_ofc"}
OFC = ("K_NBFC", "K_MUTF", "K_INSP")
CPS = ("fc_rbi", "fc_odc", "fc_ofc", "gg_cen", "gg_sta", "hh", "nfc_pub", "nfc_pvt", "other_resident", "row")
GG = ("K_GCEN", "K_GSTA")
ISSUER_CTRL = {"I_CURR", "I_DEPO", "I_SSAV", "I_GSEC", "I_MFUN"}  # plan s.2.7 Step A
ASSET_OF = {"C_CNST": 0, "C_TREQ": 1, "C_ELEQ": 1, "C_MACH": 1, "C_WOOD": 1, "C_GJOM": 1, "C_PHRM": 1,
            "C_ITSV": 2, "C_EDUC": 2, "C_OSRV": 2, "C_CROP": 3, "C_LVST": 3}  # fmt: skip
ASSETS = ("dwellings_other_buildings_and_structures", "machinery_and_equipment", "intellectual_property_products",
          "cultivated_biological_resources")  # fmt: skip
NAS_SEC = {"nfc_pub": ("public_non_financial_corporations", "nfc_public"), "nfc_pvt": ("private_non_financial_corporations", "nfc_private"),
           "fc_pub": ("public_financial_corporations", "fc_public"), "fc_pvt": ("private_financial_corporations", "fc_private"),
           "gg": ("general_government", "gg"), "hh": ("household_sector", "households_npish")}  # fmt: skip


def _p(path: Path) -> str:
    return path.as_posix()


@cache
def con() -> duckdb.DuckDBPyConnection:
    for f in ("capital_financial_entries", "capital_financial_constraints", "capital_financial_provenance", "capital_financial_checks"):
        if not (BLOCKS / f"{f}.parquet").exists():
            pytest.fail(f"{f}.parquet missing: run `uv run python -m pipeline sam capital_financial`")
    return duckdb.connect()


def _rows(sql: str, params: list | None = None) -> list[tuple]:
    return con().execute(sql, params or []).fetchall()


def _clean(unit: str, ds: str) -> str:
    return _p(CLEAN / unit / f"{ds}.parquet")


def val(unit: str, ds: str, sid: str, period: str = YEAR, vintage: str | None = None) -> float:
    q = f"select value, vintage from '{_clean(unit, ds)}' where series_id=? and period=?"
    r = _rows(q, [sid, period])
    if vintage:
        r = [x for x in r if x[1] == vintage]
    assert r, (ds, sid, period)
    return float(sorted(r, key=lambda x: str(x[1]))[-1][0])  # latest vintage


def nas(tab: str, sid: str) -> float:
    return val("mospi_nas_2026", f"mospi_nas_2026_{tab}", sid)


@cache
def entries() -> dict[tuple, tuple]:
    f = _p(BLOCKS / "capital_financial_entries.parquet")
    return {(r[0], r[1], r[2], r[3]): r[4:] for r in _rows(f"select row, col, ref, component, value, status, role, tol_rel, confidence, prov_id from '{f}'")}


def by_ref(*refs: str) -> dict[tuple, tuple]:
    return {k: v for k, v in entries().items() if k[2] in refs}


@cache
def all_entries() -> list[tuple]:
    fs = sorted(glob.glob(_p(BLOCKS) + "/*_entries.parquet"))
    return _rows("select block, row, col, ref, component, value from read_parquet(?, union_by_name=true)", [fs])


def _sat(name: str) -> str:
    return _p(SAT / f"{name}.parquet")


def _stale_deps() -> list[str]:
    cat = json.loads((BLOCKS / "capital_financial_block.json").read_text(encoding="utf-8"))
    return [f"{dep}_{kind}" for dep, files in cat["dependency_hashes"].items() for kind, h in files.items()
            if hashlib.sha256((BLOCKS / f"{dep}_{kind}.parquet").read_bytes()).hexdigest() != h]  # fmt: skip


# ------------------------------------------------------------------------------------------ physical side
@cache
def physical() -> dict:
    conc = {r["sut_product"]: r["commodity"] for r in csv.DictReader((ROOT / "data" / "concordance" / "io_tables_sut_product_to_sam34.csv").open(encoding="utf-8"))}
    rows: dict[str, float] = {}
    for sid, v in _rows(f"select series_id, value from '{_clean('io_tables', 'io_tables_sut_use')}' where period=? and series_id like 'use.gfcf.sut_p%'", [YEAR]):
        c = conc[str(int(sid.split(".sut_p")[1].split(".")[0]))]
        rows[c] = rows.get(c, 0.0) + v
    rows = {k: v for k, v in rows.items() if v != 0}
    sut_tot = val("io_tables", "io_tables_sut_use", "use.gfcf.total.current")
    nsec = {s: nas("s1_11", f"s1_11.{n}.current") for s, (n, _) in NAS_SEC.items()}
    nasset = {(s, a): nas("s1_11", f"s1_11.{n}.{a}.current") for s, (n, _) in NAS_SEC.items() for a in ASSETS}
    scale = sut_tot / nas("s1_11", "s1_11.gross_fixed_capital_formation.current")
    U = "union_fiscal"
    heads = sum(val(U, "union_fiscal_fa_expenditure", f"fa9.{h}.total") for h in ("5002", "5003", "5201", "5225", "5275", "4416", "5465", "5466", "5467"))
    centre = val(U, "union_fiscal_fa_expenditure", "fa9.section.expenditure_heads_capital_account") - heads + val(U, "union_fiscal_fa_gia", "gia.cash.autonomous_bodies.capital_assets") + val(U, "union_fiscal_fa_gia", "gia.cash.statutory_bodies_and_development_authorities.capital_assets")
    states = val("state_fiscal", "state_fiscal_rbi_sf_appendices", "app4.total_capital_disbursements.i-total_capital_outlay.in.all_states_uts.actuals") + val(U, "union_fiscal_fa_gia", "gia.cash.urban_local_bodies.capital_assets")
    csh = centre / (centre + states)
    R, RA = "rbi_banking_corporate", "rbi_banking_corporate_rbi_accounts"
    fa = "sch12.x.fixed_assets_net_of_accumulated_depreciation.current"
    rbi = val(R, RA, fa, "2024-03-31", "2024-05-30") - val(R, RA, fa, "2023-03-31", "2024-05-30") + val(R, RA, "is.exp_depreciation.current", YEAR, "2024-05-30")
    gos = {(a, p): v for a, p, v in _rows(f"select account, part, value from '{_p(BLOCKS / 'fincorp_satellites' / 'fc_public_private.parquet')}' where item='gos' and account<>'E_RBI'")}
    cols = {("K_NFPU", "total"): ("nfc_pub", nsec["nfc_pub"] * scale), ("K_NFPR", "total"): ("nfc_pvt", nsec["nfc_pvt"] * scale),
            ("K_HH", "total"): ("hh", nsec["hh"] * scale), ("K_GCEN", "total"): ("gg", nsec["gg"] * scale * csh),
            ("K_GSTA", "total"): ("gg", nsec["gg"] * scale * (1 - csh)), ("K_RBI", "public"): ("fc_pub", rbi)}  # fmt: skip
    for part, sec, tot in (("public", "fc_pub", nsec["fc_pub"] * scale - rbi), ("private", "fc_pvt", nsec["fc_pvt"] * scale)):
        den = sum(gos[(e, part)] for e in ("E_BANK", "E_NBFC", "E_INSP"))
        for e, k in (("E_BANK", "K_BANK"), ("E_NBFC", "K_NBFC"), ("E_INSP", "K_INSP")):
            cols[(k, part)] = (sec, tot * gos[(e, part)] / den)
    grp = {a: sum(v for c, v in rows.items() if ASSET_OF[c] == a) for a in range(4)}
    rk, ck = sorted(rows), sorted(cols)
    X = np.array([[cols[c][1] * nasset[(cols[c][0], ASSETS[ASSET_OF[r]])] / nsec[cols[c][0]] * rows[r] / grp[ASSET_OF[r]] for c in ck] for r in rk])
    rt, ct = np.array([rows[r] for r in rk]), np.array([cols[c][1] for c in ck])
    for _ in range(10000):
        X *= (rt / X.sum(1))[:, None]
        X *= (ct / X.sum(0))[None, :]
        if max(abs(X.sum(1) / rt - 1).max(), abs(X.sum(0) / ct - 1).max()) < 1e-13:
            break
    i1a = {(rk[i], ck[j][0], ck[j][1]): float(X[i, j]) for i in range(len(rk)) for j in range(len(ck)) if X[i, j] != 0}
    i2 = nas("s1_9", "s1_9.saving_in_the_form_of_gold_and_silver_ornaments.current")
    i2a = val("io_tables", "io_tables_sut_use", "use.valuables.total.current") - i2
    gcf = {s: nas("s1_14", f"s1_14.{n}.gross_capital_formation.current") for s, (_, n) in NAS_SEC.items()}
    cis = {s: gcf[s] - nsec[s] for s in NAS_SEC}
    cii = val("io_tables", "io_tables_sut_use", "use.cii.total.current")
    cs = cii / sum(cis.values())
    i3a = {"K_NFPU": cis["nfc_pub"] * cs, "K_NFPR": cis["nfc_pvt"] * cs, "K_GCEN": cis["gg"] * cs, "K_HH": cis["hh"] * cs}
    priv = {k: sum(v for (_, a, comp), v in i1a.items() if a == k and comp == "private") for k in ("K_BANK", "K_NBFC", "K_INSP")}
    for k, v in priv.items():
        i3a[k] = cis["fc_pvt"] * cs * v / sum(priv.values())
    d3tot = val("mospi_nas_2026", "mospi_nas_2026_derived_residuals", "derived.si_errors_omissions.current")
    rem = d3tot - i2a
    corp = gcf["nfc_pub"] + gcf["nfc_pvt"] + gcf["fc_pub"] + gcf["fc_pvt"]
    fcg = {k: sum(v for (_, a, _c), v in i1a.items() if a == k) + i3a.get(k, 0.0) for k in ("K_RBI", "K_BANK", "K_NBFC", "K_INSP")}
    d3 = {"K_HH": i2a, "K_NFPU": rem * gcf["nfc_pub"] / corp, "K_NFPR": rem * gcf["nfc_pvt"] / corp}
    d3 |= {k: rem * (gcf["fc_pub"] + gcf["fc_pvt"]) / corp * v / sum(fcg.values()) for k, v in fcg.items()}
    k1 = {"K_NFPU": nas("s1_9", "s1_9.public_non_financial_corporations.current"), "K_NFPR": nas("s1_9", "s1_9.private_non_financial_corporations.current")}
    return {"rows": rows, "cols": cols, "i1a": i1a, "i2": i2, "i2a": i2a, "i3a": i3a, "d3": d3, "d3tot": d3tot, "k1": k1,
            "nsec": nsec, "cis": cis, "cii": cii, "csh": csh, "centre": centre, "states": states, "rbi": rbi, "sut_tot": sut_tot}  # fmt: skip


# ------------------------------------------------------------------------------------------ FSF reconciliation
@cache
def fsf() -> dict:
    f = _clean("rbi_financial_accounts", "rbi_financial_accounts_fsf_balance_sheets")
    raw = _rows(f"select institution, side, instrument, counterparty, value from '{f}' where period=? and dim_other='measure=transaction'", [YEAR])
    leaf = {(i, s, ins, cp): v for i, s, ins, cp, v in raw}
    agg: dict[tuple, float] = {}
    for (i, s, ins, cp), v in leaf.items():
        if i in LEAF:
            k = (LEAF[i], s, ins, cp)
            agg[k] = agg.get(k, 0.0) + v
    return {"leaf": leaf, "agg": agg}


def t(inst: str, side: str, instr: str, cp: str = "all") -> float:
    return float(fsf()["leaf"].get((inst, side, instr, cp), 0.0))


def rep(acct: str, side: str, instr: str, cp: str) -> float:
    return float(fsf()["agg"].get((acct, side, instr, cp), 0.0))


def absshare(total: float, r: dict[str, float]) -> dict[str, float]:
    """Plan s.2.0: x_i = r_i + (T - sum r) |r_i| / sum |r| (mixed-sign keys)."""
    s, sa = sum(r.values()), sum(abs(v) for v in r.values())
    assert sa != 0
    return {k: v + (total - s) * abs(v) / sa for k, v in r.items()}


@cache
def recon() -> dict:
    accts = sorted(set(LEAF.values()))
    X: dict[tuple, float] = {}

    def add(si, h, i, v, kind):
        if v:
            X[(si, h, i, kind)] = X.get((si, h, i, kind), 0.0) + v

    for f, pick in (("f21", lambda i: "I_CURR"), ("f22_f29", lambda i: "I_SSAV" if i in GG else "I_DEPO"), ("f3", lambda i: "I_GSEC" if i in GG else None)):
        for i in accts:
            si = pick(i)
            if si is None:
                continue
            for cp in CPS:
                v = rep(i, "liabilities", f, cp)
                if not v or cp in ("hh", "row"):
                    continue
                if cp in CODE2ACC:
                    add(si, CODE2ACC[cp], i, v, "pub")
                elif cp == "fc_ofc":
                    for h, x in absshare(v, {h: rep(h, "assets", f, ACC2CODE[i]) for h in OFC}).items():
                        add(si, h, i, x, "key")
                elif cp == "other_resident" and si in ("I_CURR", "I_DEPO"):
                    add(si, "K_NFPR", i, v, "key")
            u = rep(i, "liabilities", f, "all") - sum(rep(i, "liabilities", f, c) for c in CPS)
            if abs(u) > 1e-6 and si in ("I_CURR", "I_DEPO"):
                add(si, "K_NFPR", i, u, "key")
    for f, si in (("f3", "I_CBND"), ("f4", "I_LOAN"), ("f51", "I_EQTY")):
        for h in accts:
            for cp in CPS:
                if f == "f3" and cp in ("gg_cen", "gg_sta"):
                    continue
                v = t("fc_ofc_icpf_pf", "assets", "f51", cp) if (f == "f51" and h == "K_INSP") else rep(h, "assets", f, cp)
                if not v or cp in ("hh", "row"):
                    continue
                if cp in CODE2ACC:
                    add(si, h, CODE2ACC[cp], v, "pub")
                elif cp == "fc_ofc":
                    for i, x in absshare(v, {i: rep(i, "liabilities", f, ACC2CODE[h]) for i in OFC}).items():
                        add(si, h, i, x, "key")
    # Step C1: insurers' equity net of revaluation, spread by the MF sector's domestic F51 issuer mix
    strip = t("fc_ofc_icpf_ins", "assets", "f51") - (t("fc_ofc_icpf_ins", "liabilities", "f62") - nas("s5_3", "s5_3.life_insurance_funds.current"))
    mix = {cp: t("fc_ofc_mf", "assets", "f51", cp) for cp in ("fc_rbi", "fc_odc", "fc_ofc", "gg_cen", "gg_sta", "nfc_pub", "nfc_pvt", "other_resident")}
    mix = {k: v for k, v in mix.items() if v}
    for cp, v in mix.items():
        x = strip * v / sum(mix.values())
        if cp in CODE2ACC:
            add("I_EQTY", "K_INSP", CODE2ACC[cp], x, "key")
        else:
            for i, y in absshare(x, {i: rep(i, "liabilities", "f51", "fc_ofc") for i in OFC}).items():
                add("I_EQTY", "K_INSP", i, y, "key")
    # Step C4: Centre -> States loans net of government's K8e (plan s.2.7, XR-? D1)
    k8e = sum(v for b, r, c, ref, _, v in all_entries() if b == "government" and ref == "K8e" and r == "I_LOAN" and c == "K_GCEN")
    add("I_LOAN", "K_GCEN", "K_GSTA", -k8e, "pub")
    # Step C3: MF units = FSF MF net sales less NAS households over the other holders' F52 (SFC/SIDC excluded)
    r: dict[str, float] = {}
    for inst, a in LEAF.items():
        if inst not in ("fc_ofc_sfc", "fc_ofc_sidc") and t(inst, "assets", "f52"):
            r[a] = r.get(a, 0.0) + t(inst, "assets", "f52")
    for h, x in absshare(t("fc_ofc_mf", "liabilities", "f52") - nas("s5_3", "s5_3.mutual_funds.current"), r).items():
        add("I_MFUN", h, "K_MUTF", x, "key")
    k9b = val("rbi_banking_corporate", "rbi_banking_corporate_rbi_surplus_timing", "k9b.change_in_surplus_payable.current", vintage="2024-05-30")
    own: dict[tuple, float] = {}
    for f in ("f81", "f89"):
        for a in accts:
            for side in ("assets", "liabilities"):
                v = rep(a, side, f, "all") - rep(a, side, f, "hh") - rep(a, side, f, "row")
                if f == "f89" and ((a == "K_RBI" and side == "liabilities") or (a == "K_GCEN" and side == "assets")):
                    v -= k9b  # K9b replaces the FSF RBI <-> Centre F89 pair (plan s.2.10)
                if abs(v) > 1e-9:
                    own[(f, a, side)] = v
    cells: dict[tuple, float] = {}
    for (si, h, i, _kind), v in X.items():
        k1, k2 = (si, h, "K8d" if si == "I_GSEC" else "K7"), (i, si, "K8")
        cells[k1] = cells.get(k1, 0.0) + v
        cells[k2] = cells.get(k2, 0.0) + v
    for (_f, a, side), v in own.items():
        k = ("I_OTHR", a, "K7") if side == "assets" else (a, "I_OTHR", "K8")
        cells[k] = cells.get(k, 0.0) + v
    return {"X": X, "cells": cells, "own": own, "k9b": k9b, "k8e": k8e, "strip": strip, "mix": mix}


# ------------------------------------------------------------------------------------------ tests
def test_catalog_and_currency_against_dependencies():
    cat = json.loads((BLOCKS / "capital_financial_block.json").read_text(encoding="utf-8"))
    assert cat["refs_not_implemented"] == []
    assert cat["entries"] == len(entries()) == 444 and cat["constraints"] == 19
    assert cat["depends"] == ["production", "households", "rest_of_world", "government", "fincorp"]  # D2-10
    # V-CF-1 (fixed 2026-10-01 by a rebuild): the block must be built after every DEPENDS block it read
    stale = _stale_deps()
    assert not stale, f"V-CF-1: capital_financial is stale against {stale}; rebuild it"


def test_i1a_census_by_independent_ras():
    ph = physical()
    got = by_ref("I1a")
    assert len(got) == len(ph["i1a"]) == 130
    for (r, c, _ref, comp), (v, st, role, _tol, conf, _) in got.items():
        assert abs(v - ph["i1a"][(r, c, comp)]) < TOL, (r, c, comp)
        assert (st, role, conf) == ("estimated", "free", "medium")
    assert abs(sum(v[0] for v in got.values()) - ph["sut_tot"]) < 1e-3
    assert abs(ph["csh"] - 0.4553743) < 1e-6 and abs(ph["rbi"] - 1431.69) < 1e-6  # issues -11, -12 (V-CF-1 key change)


def test_gg_gfcf_key_satellite():
    ph = physical()
    got = dict(_rows(f"select item, value from '{_sat('gg_gfcf_key')}'"))
    assert abs(got["centre_key"] - ph["centre"]) < 1e-3 and abs(got["states_key"] - ph["states"]) < 1e-3
    assert abs(got["centre_share"] - ph["csh"]) < 1e-6 and abs(got["rbi_gfcf"] - ph["rbi"]) < 1e-6


def test_valuables_inventories_d3_k1_census():
    ph = physical()
    e = entries()
    assert abs(e[("C_GJOM", "K_HH", "I2", "gold_silver_ornaments")][0] - ph["i2"]) < 1e-6
    assert abs(ph["i2"] - nas("s5_3", "s5_3.saving_in_form_of_gold_and_silver_ornaments.current")) < 1e-6
    assert abs(e[("C_GJOM", "K_HH", "I2a", "unsectored_valuables")][0] - ph["i2a"]) < 1e-6
    i3a = by_ref("I3a")
    assert {k[1] for k in i3a} == set(ph["i3a"])  # public FC CIS is exactly 0: not written
    for (r, c, _ref, _comp), (v, st, role, tol, conf, _) in i3a.items():
        assert r == "K_DSTK" and abs(v - ph["i3a"][c]) < TOL, c
        if c in ("K_BANK", "K_NBFC", "K_INSP"):
            assert (st, role, conf) == ("estimated", "free", "medium")
        else:
            assert (st, role, tol) == ("derived", "anchored", 0.001)
    d3 = by_ref("D3")
    assert len(d3) == 7
    for (r, c, _ref, comp), (v, st, role, *_x) in d3.items():
        assert c == "X_DISC" and role == "fixed" and abs(v - ph["d3"][r]) < TOL, r
        assert (comp, st) == (("unsectored_valuables", "derived") if r == "K_HH" else ("si_errors", "estimated"))
    assert abs(sum(v[0] for v in d3.values()) - ph["d3tot"]) < 1e-5
    for (r, c, _ref, _comp), (v, st, role, *_x) in by_ref("K1").items():
        assert (st, role) == ("official", "fixed") and abs(v - ph["k1"][r]) < 1e-6 and c == r.replace("K_", "E_")


def test_household_k7a_k8a_census():
    """XR-19 components; PPF only in I_SSAV (NSSF), never I_INPE; totals = NAS 5.3."""
    n = lambda s: nas("s5_3", f"s5_3.{s}.current")  # noqa: E731
    ppf = val("union_fiscal", "union_fiscal_nssf", "nssf.ppf.additions")
    exp = {("I_DEPO", "banks"): n("with_banks"), ("I_DEPO", "coop_banks"): n("with_co_operative_banks_and_societies"),
           ("I_DEPO", "nonbank_deposits"): n("with_non_banking_companies"), ("I_CURR", "currency"): n("currency"),
           ("I_OTHR", "trade_debt"): n("trade_debt_net"), ("I_GSEC", "gsec"): n("investment_in_government_securities"),
           ("I_SSAV", "small_savings"): n("investment_in_small_savings_etc"), ("I_SSAV", "ppf"): ppf,
           ("I_EQTY", "shares_debentures"): n("shares_and_debentures") - n("mutual_funds"), ("I_MFUN", "mutual_funds"): n("mutual_funds"),
           ("I_INPE", "life_insurance"): n("life_insurance_funds"), ("I_INPE", "postal_insurance"): n("postal_insurance"),
           ("I_INPE", "state_insurance"): n("state_insurance"), ("I_INPE", "pf_pension"): n("provident_and_pension_funds") - ppf}  # fmt: skip
    got = by_ref("K7a")
    assert {(k[0], k[3]) for k in got} == set(exp) and all(k[1] == "K_HH" for k in got)
    for (r, _c, _ref, comp), (v, st, role, *_x) in got.items():
        assert abs(v - exp[(r, comp)]) < 1e-5, comp
        assert role == "fixed" and st == ("derived" if comp == "pf_pension" else "official")
    assert abs(sum(v[0] for v in got.values()) - n("gross_financial_saving")) < 0.01
    assert abs(ppf + n("investment_in_small_savings_etc") - val("union_fiscal", "union_fiscal_nssf", "nssf.net_collection")) < 0.01
    ek = {"banks": n("bank_advances"), "coop_banks": n("loans_and_advances_by_co_operative_banks_and_societies"),
          "nbfc": n("loans_by_financial_corporations_and_non_banking_companies"), "government": n("loans_and_advances_from_government"),
          "insurers": n("loans_from_insurance_corporations")}  # fmt: skip
    got = by_ref("K8a")
    assert {k[3] for k in got} == set(ek) and all(k[:2] == ("K_HH", "I_LOAN") for k in got)
    for k, (v, st, role, *_x) in got.items():
        assert abs(v - ek[k[3]]) < 1e-5 and (st, role) == ("official", "fixed")
    assert abs(sum(v[0] for v in got.values()) - n("financial_liabilities")) < 0.01


def test_household_counterpart_postings_census():
    """K7b hh_cp: NAS 5.3 lines posted on the counterparties' own FSF keys (plan s.2.8-2.9)."""
    n = lambda s: nas("s5_3", f"s5_3.{s}.current")  # noqa: E731
    ppf = val("union_fiscal", "union_fiscal_nssf", "nssf.ppf.additions")
    exp: dict[tuple, float] = {}

    def post(cell, v):
        exp[cell] = exp.get(cell, 0.0) + v

    post(("K_RBI", "I_CURR"), n("currency"))
    dep = n("with_banks") + n("with_co_operative_banks_and_societies") + n("with_non_banking_companies")
    key = {a: sum(t(i, "liabilities", "f22_f29", "hh") for i, x in LEAF.items() if x == a) for a in ("K_BANK", "K_NBFC", "K_NFPR")}
    for a, x in absshare(dep, key).items():
        post((a, "I_DEPO"), x)
    post(("K_NFPR", "I_OTHR"), n("trade_debt_net"))
    coop = n("co_operative_banks_and_societies")
    post(("K_BANK", "I_EQTY"), coop)
    key = {a: sum(t(i, "liabilities", "f51", "hh") for i, x in LEAF.items() if x == a) for a in sorted(set(LEAF.values()))}
    for a, x in absshare(n("shares_and_debentures") - n("mutual_funds") - coop, {k: v for k, v in key.items() if v}).items():
        post((a, "I_EQTY"), x)
    post(("K_MUTF", "I_MFUN"), n("mutual_funds"))
    gs = t("gg_sta", "liabilities", "f3", "hh")
    post(("K_GSTA", "I_GSEC"), gs)
    post(("K_GCEN", "I_GSEC"), n("investment_in_government_securities") - gs)
    post(("K_GCEN", "I_SSAV"), n("investment_in_small_savings_etc") + ppf)
    pfc, pfs = t("gg_cen", "liabilities", "f6_pf"), t("gg_sta", "liabilities", "f6_pf")
    post(("K_INSP", "I_INPE"), n("life_insurance_funds") + n("provident_and_pension_funds") - ppf - pfc - pfs)
    post(("K_GCEN", "I_INPE"), n("postal_insurance") + pfc)
    post(("K_GSTA", "I_INPE"), n("state_insurance") + pfs)
    post(("I_LOAN", "K_GCEN"), t("hh", "liabilities", "f4", "gg_cen"))
    post(("I_LOAN", "K_GSTA"), t("hh", "liabilities", "f4", "gg_sta"))
    post(("I_LOAN", "K_INSP"), n("loans_from_insurance_corporations"))
    rest = n("financial_liabilities") - n("loans_and_advances_from_government") - n("loans_from_insurance_corporations")
    key = {a: sum(t(i, "assets", "f4", "hh") for i, x in LEAF.items() if x == a and i != "fc_ofc_icpf_ins" and i.startswith("fc_")) for a in ("K_RBI", "K_BANK", "K_NBFC", "K_MUTF", "K_INSP")}
    for a, x in absshare(rest, {k: v for k, v in key.items() if v}).items():
        post(("I_LOAN", a), x)
    got = {(k[0], k[1]): v for k, v in by_ref("K7b").items() if k[3] == "hh_cp"}
    assert set(got) == {k for k, v in exp.items() if abs(v) > 1e-9}
    for k, (v, st, role, _tol, conf, _) in got.items():
        assert abs(v - exp[k]) < TOL, k
        assert (st, role, conf) == ("estimated", "free", "high")


def test_row_counterpart_postings_census():
    """K7b row_cp: every rest_of_world K8b line with a named domestic counterpart, same value and instrument."""
    f = _p(BLOCKS / "rest_of_world_satellites" / "row_financial_counterparts.parquet")
    exp = {}
    for line, ins, direction, cp, v in _rows(f"select line, instrument, direction, counterpart, value from '{f}'"):
        if cp == "unallocated_k9" or ins == "I_RESV":
            continue  # E&O / NAS reconciliation -> K9; reserves are rest_of_world's K8c (plan D3)
        cell = (cp, ins) if direction == "row_acquires" else (ins, cp)
        exp[(*cell, f"row_cp_{line}")] = v
    got = {(k[0], k[1], k[3]): v for k, v in by_ref("K7b").items() if k[3].startswith("row_cp_")}
    assert set(got) == set(exp) and len(got) == 37
    for k, (v, st, role, _tol, conf, _) in got.items():
        assert abs(v - exp[k]) < 1e-6, k
        assert (st, role, conf) == ("estimated", "free", "high")
    # FDI reinvested earnings mirror rest_of_world's R14a payer split exactly (D8)
    r14a = {c.replace("E_", "K_"): v for b, r, c, ref, _, v in all_entries() if ref == "R14a"}
    for k, v in r14a.items():
        assert abs(got[(k, "I_EQTY", "row_cp_fdi_reinvested_earnings")][0] - v) < 1e-6


def test_fsf_reconciliation_cell_census():
    """K7 / K8 / K8d: every (row, col, ref) cell equals the independent pairwise control-side reconciliation."""
    rc = recon()
    got: dict[tuple, float] = {}
    for (r, c, ref, _comp), v in by_ref("K7", "K8", "K8d").items():
        got[(r, c, ref)] = got.get((r, c, ref), 0.0) + v[0]
    assert set(got) == set(rc["cells"]) and len(got) == 101
    for k, v in got.items():
        assert abs(v - rc["cells"][k]) < TOL, k
    assert abs(rc["strip"] - 208850.200345) < 1e-4  # plan s.2.7 C1
    assert abs(rc["k8e"] + 78104.0) < 1e-9  # government K8e (T2b(ii))
    # every instrument market except I_OTHR clears on the domestic pairs: the pairs are the same numbers on both sides
    for si in ("I_CURR", "I_DEPO", "I_SSAV", "I_GSEC", "I_CBND", "I_LOAN", "I_EQTY", "I_MFUN"):
        a = sum(v for (r, c, _), v in rc["cells"].items() if r == si)
        b = sum(v for (r, c, _), v in rc["cells"].items() if c == si)
        assert abs(a - b) < 1e-6, si


def test_fsf_entry_labels_follow_the_control_side_rule():
    """Control side: published pairs dom_* derived/anchored 10%, keyed pairs dom_keyed_* estimated/free medium;
    non-control side dom_* estimated/free medium; own F81/F89 reports estimated/free low; signs match names."""
    n = 0
    for (r, c, _ref, comp), (v, st, role, tol, conf, _) in by_ref("K7", "K8", "K8d").items():
        instr = r if r.startswith("I_") else c
        asset_side = r.startswith("I_")
        control = (not asset_side) if instr in ISSUER_CTRL else asset_side
        if comp.startswith("fsf_f8"):
            assert instr == "I_OTHR" and (st, role, conf) == ("estimated", "free", "low")
        elif control and comp in ("dom_pos", "dom_neg"):
            assert (st, role, tol) == ("derived", "anchored", 0.10), (r, c, comp)
        else:
            assert comp in ("dom_pos", "dom_neg", "dom_keyed_pos", "dom_keyed_neg") and (st, role, conf) == ("estimated", "free", "medium"), (r, c, comp)
            assert control or not comp.startswith("dom_keyed")
        if comp.endswith("_pos"):
            assert v > 0
        if comp.endswith("_neg"):
            assert v < 0
        n += 1
    assert n == 195


def test_k9b_and_rbi_centre_f89_remainder():
    rc, e = recon(), entries()
    assert abs(rc["k9b"] - 123457.77) < 1e-6
    for k in (("K_RBI", "I_OTHR", "K9b", "rbi_surplus_payable"), ("I_OTHR", "K_GCEN", "K9b", "rbi_surplus_receivable")):
        v, st, role, tol, *_ = e[k]
        assert abs(v - rc["k9b"]) < 1e-6 and (st, role, tol) == ("derived", "anchored", 0.02)
    # K9b + fsf_f89 remainder on K_RBI = FSF RBI -> Centre F89 (plan T18)
    assert abs(e[("K_RBI", "I_OTHR", "K8", "fsf_f89")][0] + rc["k9b"] - t("fc_rbi", "liabilities", "f89", "gg_cen")) < 0.01


def test_k9_residuals_close_every_domestic_capital_account():
    """K9_s = row - column over every block's prior entries (K_HH: NAS K4, since K4a is closure's)."""
    k4 = nas("s1_9", "s1_9.household_sector.current")
    k9: dict[str, float] = {}
    for s in DOM:
        rs = sum(v for b, r, c, ref, _, v in all_entries() if r == s and c != s and ref not in ("K9", "K4a"))
        cs = sum(v for b, r, c, ref, _, v in all_entries() if c == s and r != s and ref not in ("K9", "K4a"))
        k9[s] = rs - cs + (k4 if s == "K_HH" else 0.0)
    got = {s: 0.0 for s in DOM}
    for (r, c, _ref, comp), (v, st, role, _tol, conf, _) in by_ref("K9").items():
        assert r == "I_OTHR" and (st, role, conf) == ("estimated", "free", "low") and comp in ("residual_pos", "residual_neg")
        assert (v > 0) == (comp == "residual_pos")
        got[c] += v
    assert abs(sum(got.values()) - sum(k9.values())) < 0.01  # the government change moved money between G accounts only
    for s in DOM:
        assert abs(got[s] - k9[s]) < 0.01, s  # V-CF-1 fixed: K_GCEN/K_GSTA close again
    # D2-6 / XR-3: K9_HH = the capital transfers households receive, which NAS household saving cannot see
    k6hh = sum(v for b, r, c, ref, _, v in all_entries() if ref == "K6" and r == "K_HH")
    assert abs(got["K_HH"] - k6hh) < 0.05


def test_k9_decomposition_adds_up_and_matches_the_entry_pair():
    dec: dict[str, dict[str, float]] = {}
    for acc, item, v in _rows(f"select account, item, value from '{_sat('k9_decomposition')}'"):
        dec.setdefault(acc, {})[item] = v
    e = by_ref("K9")
    leaf_nft: dict[str, float] = {}
    for inst, a in {**LEAF, "hh": "K_HH"}.items():
        leaf_nft[a] = leaf_nft.get(a, 0.0) + t(inst, "assets", "total") - t(inst, "liabilities", "total")
    for acc, d in dec.items():
        terms = sum(v for k, v in d.items() if k.startswith("term:"))
        assert abs(terms - d["k9"]) < 1e-3, acc
        assert abs(d["pos"] + d["neg"] - d["k9"]) < 1e-3
        assert abs(e.get(("I_OTHR", acc, "K9", "residual_pos"), (0.0,))[0] - d["pos"]) < 1e-3
        assert abs(e.get(("I_OTHR", acc, "K9", "residual_neg"), (0.0,))[0] - d["neg"]) < 1e-3
        assert abs(d["fsf_total"] - leaf_nft[acc]) < 0.01, acc  # FSF published net financial transactions (leaf basis)
        assert abs(d["term:nas_vs_fsf"] - (d["real"] - d["fsf_total"])) < 1e-3


def test_k9_sensitivity_variants_recomputed():
    """Plan T24 (report only): insurer strip off exactly; equity issuer control within the OFC-internal split
    convention (<= Rs 200 crore on K_NBFC/K_MUTF/K_INSP, exact elsewhere); the sum is the same in every variant."""
    sens: dict[str, dict[str, float]] = {}
    for var, acc, item, v in _rows(f"select variant, account, item, value from '{_sat('k9_sensitivity')}'"):
        if item == "k9":
            sens.setdefault(var, {})[acc] = v
    base = sens["base"]
    for var, d in sens.items():
        assert abs(sum(d.values()) - sum(base.values())) < 1e-3, var
    rc = recon()

    def net(xd):
        n: dict[str, float] = {}
        for (si, h, i, _k), v in xd.items():
            if si == "I_EQTY":
                n[i] = n.get(i, 0.0) + v
                n[h] = n.get(h, 0.0) - v
        return n

    b = net(rc["X"])
    xs = {k: v for k, v in rc["X"].items() if not (k[0] == "I_EQTY" and k[1] == "K_INSP" and k[3] == "key")}
    full = t("fc_ofc_icpf_ins", "assets", "f51")
    for cp, v in rc["mix"].items():
        x = full * v / sum(rc["mix"].values())
        parts = {CODE2ACC[cp]: x} if cp in CODE2ACC else absshare(x, {i: rep(i, "liabilities", "f51", "fc_ofc") for i in OFC})
        for i, y in parts.items():
            xs[("I_EQTY", "K_INSP", i, "key")] = xs.get(("I_EQTY", "K_INSP", i, "key"), 0.0) + y
    off = net(xs)
    xi: dict[tuple, float] = {}
    for i in sorted(set(LEAF.values())):
        for cp in CPS:
            v = rep(i, "liabilities", "f51", cp)
            if not v or cp in ("hh", "row"):
                continue
            parts = {CODE2ACC[cp]: v} if cp in CODE2ACC else absshare(v, {h: rep(h, "assets", "f51", ACC2CODE[i]) for h in OFC}) if cp == "fc_ofc" else {}
            for h, x in parts.items():
                xi[("I_EQTY", h, i, "k")] = xi.get(("I_EQTY", h, i, "k"), 0.0) + x
    iss = net(xi)
    for acc in DOM:
        assert abs(sens["insurer_strip_off"][acc] - (base[acc] + off.get(acc, 0.0) - b.get(acc, 0.0))) < 0.01, acc
        tol = 200.0 if acc in OFC else 0.01
        assert abs(sens["equity_issuer_control"][acc] - (base[acc] + iss.get(acc, 0.0) - b.get(acc, 0.0))) < tol, acc
    ph = physical()
    d3_moved = ph["d3tot"] - ph["i2a"]
    assert abs(sens["d3_all_k_nfpu"]["K_NFPU"] - base["K_NFPU"] - (d3_moved - ph["d3"]["K_NFPU"])) < 0.01


def test_every_instrument_market_clears_and_walras():
    rs: dict[str, float] = {}
    cs: dict[str, float] = {}
    for _b, r, c, _ref, _comp, v in all_entries():
        rs[r] = rs.get(r, 0.0) + v
        cs[c] = cs.get(c, 0.0) + v
    for i in ("I_CURR", "I_DEPO", "I_SSAV", "I_GSEC", "I_CBND", "I_LOAN", "I_EQTY", "I_MFUN", "I_INPE", "I_RESV"):
        assert abs(rs.get(i, 0.0) - cs.get(i, 0.0)) < 0.01, i
    assert abs(rs["I_OTHR"] - cs["I_OTHR"]) < 1.0  # plan T15 (Walras: -0.25)
    assert abs(rs["K_DSTK"] - cs["K_DSTK"]) < 0.01  # I3a row = production's I3 column


def test_structure_and_no_double_counting():
    e = entries()
    assert all(v[0] != 0 for v in e.values())
    assert not [k for k in e if "K_ROW" in k[:2] or "I_RESV" in k[:2] or "R_ROW" in k[:2]]  # T22
    assert not [k for k in e if k[0] == "I_INPE" and k[2] == "K7a" and k[3] == "ppf"]  # PPF only in I_SSAV
    mine = {(k[0], k[1]) for k in e}
    shared = sorted({(b, r, c, ref) for b, r, c, ref, _comp, _v in all_entries() if b != "capital_financial" and (r, c) in mine})
    assert shared == [("government", "I_LOAN", "K_GCEN", "K8e"), ("government", "K_GSTA", "I_LOAN", "K8e")]


def test_constraint_targets_recomputed():
    ph = physical()
    n5 = lambda s: nas("s5_3", f"s5_3.{s}.current")  # noqa: E731
    f = _p(BLOCKS / "rest_of_world_satellites" / "row_financial_counterparts.parquet")
    rv = dict(((a, b), v) for a, b, v in _rows(f"select line, counterpart, value from '{f}'"))
    gs = t("gg_sta", "liabilities", "f3", "hh")
    ns = ph["nsec"]
    exp = {"cf.i1a.gfcf.nfc_pub": ns["nfc_pub"], "cf.i1a.gfcf.nfc_pvt": ns["nfc_pvt"], "cf.i1a.gfcf.gg": ns["gg"], "cf.i1a.gfcf.hh": ns["hh"],
           "cf.i1a.gfcf.fc": ns["fc_pub"] + ns["fc_pvt"], "cf.i1a.gfcf.fc_public": ns["fc_pub"], "cf.i1a.gfcf.fc_private": ns["fc_pvt"],
           "cf.i3a.cis.nfc_pub": ph["cis"]["nfc_pub"], "cf.i3a.cis.nfc_pvt": ph["cis"]["nfc_pvt"], "cf.i3a.cis.fc": ph["cis"]["fc_pvt"],
           "cf.i3a.cis.gg": ph["cis"]["gg"], "cf.i3a.cis.hh": ph["cis"]["hh"], "cf.i3a.cis.total": ph["cii"],
           "cf.k4.hh_saving": nas("s1_9", "s1_9.household_sector.current"),
           "cf.k8.curr": t("fc_rbi", "liabilities", "f21") - t("fc_rbi", "liabilities", "f21", "hh") + n5("currency"),
           "cf.k8.gsec_centre": t("gg_cen", "liabilities", "f3") - t("gg_cen", "liabilities", "f3", "hh") - t("gg_cen", "liabilities", "f3", "row") + n5("investment_in_government_securities") - gs + rv[("fpi_debt_gsec", "K_GCEN")],
           "cf.k8.gsec_states": t("gg_sta", "liabilities", "f3") - t("gg_sta", "liabilities", "f3", "row") + rv[("fpi_debt_gsec", "K_GSTA")],
           "cf.k8.mfun": t("fc_ofc_mf", "liabilities", "f52"),
           "cf.k8.ssav_centre": val("union_fiscal", "union_fiscal_nssf", "nssf.net_collection") + t("gg_cen", "liabilities", "f22_f29", "nfc_pub")}  # fmt: skip
    got = {c: (tg, k, ta, tr) for c, tg, k, ta, tr in _rows(f"select constraint_id, target, kind, tol_abs, tol_rel from '{_p(BLOCKS / 'capital_financial_constraints.parquet')}'")}
    assert set(got) == set(exp)
    for c, (tg, kind, _ta, _tr) in got.items():
        assert abs(tg - exp[c]) < 1e-5, c
        assert kind == ("band" if c.startswith("cf.i3a.cis.") and c != "cf.i3a.cis.total" or c in ("cf.k8.gsec_centre", "cf.k8.gsec_states", "cf.k8.mfun") else "equal"), c
    # the K4 constraint duplicates closure's exactly (same selection, target and tolerance), if closure is built
    cf = BLOCKS / "closure_constraints.parquet"
    if cf.exists():
        cl = _rows(f"select rows, cols, refs, target, tol_abs, kind from '{_p(cf)}' where constraint_id='k4.hh_saving_total'")
        mine = _rows(f"select rows, cols, refs, target, tol_abs, kind from '{_p(BLOCKS / 'capital_financial_constraints.parquet')}' where constraint_id='cf.k4.hh_saving'")
        assert cl == mine


def test_check_targets_recomputed():
    ph = physical()
    n5 = lambda s: nas("s5_3", f"s5_3.{s}.current")  # noqa: E731
    s7 = _clean("rbi_financial_accounts", "rbi_financial_accounts_fsf_instrument_sector")
    st7 = dict(_rows(f"select series_id, value from '{s7}' where period=? and series_id like 'fsf7.all.%.transaction.total.current'", [YEAR]))
    afs = lambda s: val("union_fiscal", "union_fiscal_afs", s)  # noqa: E731
    exp = {"i1a.nfc_pub": ph["nsec"]["nfc_pub"], "i1a.nfc_pvt": ph["nsec"]["nfc_pvt"], "i1a.fc_pub": ph["nsec"]["fc_pub"], "i1a.fc_pvt": ph["nsec"]["fc_pvt"],
           "i1a.gg": ph["nsec"]["gg"], "i1a.hh": ph["nsec"]["hh"], "i1a.total": ph["sut_tot"], "valuables": ph["i2"] + ph["i2a"], "i2.nas53": n5("saving_in_form_of_gold_and_silver_ornaments"),
           "i3a.total": ph["cii"], "i3a.public": nas("s7_2a", "s7_2a.total.cis.current"), "i3a.private": nas("s7_2b", "s7_2b.total.cis.current"),
           "k1.k_nfpu": ph["k1"]["K_NFPU"], "k1.k_nfpr": ph["k1"]["K_NFPR"], "k7a.total": n5("gross_financial_saving"), "k8a.total": n5("financial_liabilities"),
           "k7a_k8a.net": n5("net_financial_saving_of_household_sector_1_4"), "k7a.i_ssav": val("union_fiscal", "union_fiscal_nssf", "nssf.net_collection"),
           "d3.total": ph["d3tot"], "d3.k_hh": ph["i2a"], "k9b": recon()["k9b"],
           "centre_state_loans.afs": afs("afs.cfi_cap_disbursements.7601") - afs("afs.cfi_cap_receipts.state_governments") - afs("afs.cfi_cap_receipts.union_territories_with_legislature"),
           "fsf.st7.assets": st7["fsf7.all.assets.transaction.total.current"], "fsf.st7.liabilities": st7["fsf7.all.liabilities.transaction.total.current"]}  # fmt: skip
    got = {c: (sv, tg, ok) for c, sv, tg, ok in _rows(f"select check_id, sam_value, target, ok from '{_p(BLOCKS / 'capital_financial_checks.parquet')}'")}
    assert set(got) == set(exp)
    for c, (_sv, tg, ok) in got.items():
        assert abs(tg - exp[c]) < 0.01, c
        assert ok, c
    assert abs(got["centre_state_loans.afs"][0] - t("gg_cen", "assets", "f4", "gg_sta")) < 1e-6


def test_fsf_instrument_closure_and_statement7():
    leaves = [*LEAF, "hh", "row"]
    got = _rows(f"select fsf_instrument, side, value from '{_sat('fsf_instrument_closure')}'")
    assert len(got) == 24
    for ins, side, v in got:
        assert abs(v - sum(t(i, side, ins) for i in leaves)) < 0.01, (ins, side)
    a = sum(v for _i, s, v in got if s == "assets")
    s7 = _clean("rbi_financial_accounts", "rbi_financial_accounts_fsf_instrument_sector")
    st7a = _rows(f"select value from '{s7}' where period=? and series_id='fsf7.all.assets.transaction.total.current'", [YEAR])[0][0]
    assert abs(a - st7a) < 1.0  # plan s.2.6: 1,38,43,741 (the liabilities differ by the MMF F8 1,100, rbi_financial_accounts-4)
    eq = {s: v for i, s, v in got if i == "f51"}
    assert eq["assets"] - eq["liabilities"] > 1.5e6  # the equity market does not clear in FSF (plan s.2.6)


def test_fwtw_sam_and_dual_reports():
    rc = recon()
    fw = {(i, h, s): v for i, h, s, v in _rows(f"select instrument, holder, issuer, value from '{_sat('s4_fwtw_sam')}'")}
    mine: dict[tuple, float] = {}
    for (si, h, i, _k), v in rc["X"].items():
        mine[(si, h, i)] = mine.get((si, h, i), 0.0) + v
    for k, v in mine.items():
        assert abs(fw[k] - v) < TOL, k
    dom = {k for k in fw if "K_HH" not in k[1:] and "K_ROW" not in k[1:]}
    assert dom == set(mine)
    # row/column sums of the matrix equal the dom + hh_cp + row_cp entries of each K account
    fin = {k: v[0] for k, v in by_ref("K7", "K8", "K8d", "K7a", "K8a", "K7b").items() if not k[3].startswith("fsf_f8")}
    for k_acc in DOM:
        a = sum(v for (r, c, *_), v in fin.items() if c == k_acc and r.startswith("I_"))
        b = sum(v for (i, h, s), v in fw.items() if h == k_acc)
        assert abs(a - b) < TOL, k_acc
    rows = _rows(f"select instrument, holder, issuer, control, measure, value from '{_sat('s4_fsf_dual_reports')}'")
    d: dict[tuple, dict] = {}
    for i, h, s, c, m, v in rows:
        d.setdefault((i, h, s, c), {})[m] = v
    for (i, h, s, c), m in d.items():
        # + the framework's 12-significant-digit cap on satellite values (framework._sig, Wave C repro)
        assert abs(m["difference"] - (m["holder_report"] - m["issuer_report"])) < 1e-6 + 1e-11 * (abs(m["holder_report"]) + abs(m["issuer_report"]))
        if c == "none":
            assert i == "I_OTHR" and m["chosen"] == 0.0
        else:
            assert c == ("issuer" if i in ISSUER_CTRL else "holder"), i
            assert abs(m["chosen"] - (m["issuer_report" if c == "issuer" else "holder_report"])) < 1e-6, (i, h, s)
    # s4_fwtw_fsf is FSF St 6.13.a/b as published: every row equals its clean record
    f6 = _clean("rbi_financial_accounts", "rbi_financial_accounts_fsf_fwtw")
    n, mx, matched = _rows(f"select count(*), max(abs(s.value - f.value) / greatest(1.0, abs(f.value))), count(f.value) from '{_sat('s4_fwtw_fsf')}' s left join '{f6}' f on s.series_id = f.series_id || '.' || f.period")[0]
    # relative: the framework caps satellite values at 12 significant digits (framework._sig, Wave C repro)
    assert n == matched == 360 and mx < 1e-11
    # one leaf-report spot check: Centre's F51 purchase of public-NFC equity vs what public NFCs report (C18)
    x = d[("I_EQTY", "gg_cen", "nfc_pub", "holder")]
    assert abs(x["holder_report"] - t("gg_cen", "assets", "f51", "nfc_pub")) < 1e-6
    assert abs(x["issuer_report"] - t("nfc_pub", "liabilities", "f51", "gg_cen")) < 1e-6


def test_s5_household_wealth_and_hdfc_memo():
    h52 = _clean("rbi_financial_accounts", "rbi_financial_accounts_hh_finsav_52ab")
    fa = val("rbi_financial_accounts", "rbi_financial_accounts_hh_finsav_52ab", "t52b.fa.current", "2024-03-31")
    fl = val("rbi_financial_accounts", "rbi_financial_accounts_hh_finsav_52ab", "t52b.fl.current", "2024-03-31")
    s5 = {(g, m): v for g, m, v in _rows(f"select household_group, measure, value from '{_sat('s5_hh_wealth')}'")}
    keys = _p(BLOCKS / "households_satellites" / "hh_keys.parquet")
    for measure, key, total in (("financial_assets", "aidis_fin_assets", fa), ("institutional_debt", "aidis_inst_loans", fl)):
        lv = dict(_rows(f"select household_group, value from '{keys}' where key=? and measure='level'", [key]))
        assert abs(sum(s5[(g, measure)] for g in HH) - total) < 1.0
        for g in HH:
            assert abs(s5[(g, measure)] - total * lv[g] / sum(lv.values())) < 0.01, (measure, g)
    for measure, key in (("physical_assets_2018", "aidis_fixed_assets"), ("noninstitutional_debt_2018", "aidis_noninst_loans")):
        lv = dict(_rows(f"select household_group, value from '{keys}' where key=? and measure='level'", [key]))
        for g in HH:
            assert abs(s5[(g, measure)] - lv[g]) < 0.01, (measure, g)
    memo = dict(_rows(f"select series_id, value from '{_sat('s4_hdfc_merger_memo')}'"))
    rtp = lambda s: val("rbi_banking_corporate", "rbi_banking_corporate_rtp_banks", s, "2024-03-31", "2024-12-26")  # noqa: E731
    assert abs(memo["rtp.scb.merger_effect.loans"] - (rtp("rtp.scb_bs.loans_advances.scb.current") - rtp("rtp.scb_bs.loans_advances_excl_merger.scb.current"))) < 1e-6
    assert abs(memo["rtp.scb.merger_effect.deposits"] - (rtp("rtp.scb_bs.deposits.scb.current") - rtp("rtp.scb_bs.deposits_excl_merger.scb.current"))) < 1e-6
    assert memo["rtp.scb.merger_effect.loans"] == 525274.0 and memo["rtp.scb.merger_effect.deposits"] == 110114.0  # plan T21
    t52a = dict(_rows(f"select series_id, value from '{h52}' where period=? and series_id like 't52a.fl_fc_%.current.fy'", [YEAR]))
    for mk, sk in (("t52a.loans.scb", "t52a.fl_fc_banks_scb.current.fy"), ("t52a.loans.nbfc", "t52a.fl_fc_ofi_nbfc.current.fy"), ("t52a.loans.hfc", "t52a.fl_fc_ofi_hfc.current.fy")):
        assert abs(memo[mk] - t52a[sk]) < 1e-6
    for acc in ("K_BANK", "K_NBFC", "K_RBI", "K_INSP", "K_GCEN", "K_GSTA"):
        # + the framework's 12-significant-digit cap on satellite values (framework._sig, Wave C repro)
        assert abs(memo[f"sam.loans.{acc.lower()}"] - entries()[("I_LOAN", acc, "K7b", "hh_cp")][0]) < 1e-6 + 1e-11 * abs(memo[f"sam.loans.{acc.lower()}"])


def test_capital_formation_by_account():
    ph = physical()
    got = {(a, i): v for a, i, v in _rows(f"select account, item, value from '{_sat('capital_formation_by_account')}'")}
    for acc in DOM:
        gf = sum(v for (_c, a, _p2), v in ph["i1a"].items() if a == acc)
        if gf:
            assert abs(got[(acc, "gfcf")] - gf) < TOL, acc
            assert abs(got[(acc, "gcf")] - gf - ph["i3a"].get(acc, 0.0)) < TOL, acc
        if acc in ph["d3"]:
            assert abs(got[(acc, "d3")] - ph["d3"][acc]) < TOL, acc
    assert abs(got[("K_HH", "valuables")] - ph["i2"] - ph["i2a"]) < 1e-6


def test_provenance_inputs_resolve():
    clean = {r[0] for r in _rows(f"select prov_id from read_parquet('{_p(CLEAN)}/*/_provenance.parquet')")}
    sam = {r[0] for r in _rows("select prov_id from read_parquet(?)", [sorted(glob.glob(_p(BLOCKS) + "/*_provenance.parquet"))])}
    recs = _rows(f"select prov_id, table_id, status, inputs from '{_p(BLOCKS / 'capital_financial_provenance.parquet')}'")
    assert len(recs) == 43
    missing = [(p, i) for p, _t, _s, inp in recs for i in (inp or "").split(",") if i and i not in clean and i not in sam]
    st = {p: (tab, s) for p, tab, s, _ in recs}
    for (r, c, ref, comp), v in entries().items():
        tab, s = st[v[5]]
        assert tab.endswith(" " + ref) and s == v[1], (r, c, ref, comp)
    assert not missing, missing  # V-CF-1 fixed: the K9 record cites government's current records
