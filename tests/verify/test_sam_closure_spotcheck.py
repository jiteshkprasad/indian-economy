"""Independent verification of the SAM `closure` block (Phase 2 verifier, 2026-10-01; SPEC s.3 rule 3).

This file does NOT import pipeline.sam (no block, helper, framework or spec code) and does not use polars.
Every expected number is recomputed here with DuckDB SQL plus plain Python from:
- data/clean/mospi_nas_2026: St 1.1, 1.9, 1.14, 5.3, 6.1, 7.1A/B/C, 8.15.1 and the derived residuals
  (published household residual D1, S-I errors D3, CE receivable by residents);
- data/clean/io_tables: SUT supply (CIF adjustment), SUT use (valuables), IFPRI 2022/23 data paper T11;
- the outputs closure legitimately reads: every entry and constraint of the eight other built blocks
  (data/sam/2023-24/blocks/*_entries.parquet, *_constraints.parquet) and households' `hh_keys` satellite
  (pop_persons levels);
- pipeline/sam/accounts.yaml (read as data: the 128 account codes and their groups).

Coverage: a census of all 20 entries, both constraint targets, all 9 checks, every row of the five satellites
(hh_saving 169, xdisc_identity 10, prior_imbalance 896, constraint_gaps 2,290, institution_gaps 281) and every
provenance record (inputs resolve; the K4a records cite exactly the entries they use). Findings are in
docs/phase2/verify/closure.md (V-CLO-n). No confirmed defect in the numbers, so there is no xfail.

The expected values are recomputed from whatever the dependency outputs are at test time: if a dependency is
rebuilt and closure is not, these tests fail (closure is stale; rebuild it with `uv run python -m pipeline sam
closure`), which is the intended regression signal.
"""

# ruff: noqa: E501  (long SQL / series ids are kept on one line)
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from functools import cache
from pathlib import Path

import duckdb
import pytest
import yaml

pytestmark = [pytest.mark.quality, pytest.mark.sam]

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean"
BLOCKS = ROOT / "data" / "sam" / "2023-24" / "blocks"
SAT = BLOCKS / "closure_satellites"
YEAR = "2023-24"
HH = ["H_R1", "H_R2", "H_R3", "H_R4", "H_R5", "H_U1", "H_U2", "H_U3", "H_U4", "H_U5"]
DEPS = ["production", "households", "factors", "taxes", "government", "fincorp", "rest_of_world", "capital_financial"]
EPS = 1e-6  # Rs crore: entries are written to 6 decimals

# Plan s.2.1 step 2 as amended by s.8 item 2 and DECISIONS D2-9 (R7x, R9d)
RESOURCES = {"F1a", "F2", "F3a", "F3b", "F3c", "R8a", "R9a", "R9c", "R9d", "R10", "R11a", "R17"}
USES = {"C1a", "C4a", "C4b", "C4d", "T3a", "R9b", "R16", "R12a", "R17", "R5", "R7x"}
# Plan s.2.3 item 3 flow classes (R7x added by D2-9, R9d by D2-9)
PROP = {"R3", "R3a", "R3b", "R4", "R5", "R6", "R7", "R7x", "R8", "R8a", "R9c", "R13", "R14", "R14a"}
SOC = {"R9", "R9a", "R9b", "R9d"}
OTH = {"R1", "R2", "T2b", "R10", "R11", "R11a", "R12", "R12a", "R15", "R16", "R17", "R18"}


def _p(path: Path) -> str:
    return path.as_posix()


@cache
def con() -> duckdb.DuckDBPyConnection:
    for f in ("closure_entries", "closure_constraints", "closure_provenance", "closure_checks"):
        if not (BLOCKS / f"{f}.parquet").exists():
            pytest.fail(f"{f}.parquet missing: run `uv run python -m pipeline sam closure`")
    return duckdb.connect()


def _rows(sql: str, params: list | None = None) -> list[tuple]:
    return con().execute(sql, params or []).fetchall()


def _val(unit: str, ds: str, sid: str, period: str = YEAR) -> tuple[float, str]:
    """One clean value in Rs crore at current prices (latest vintage) and its prov_id."""
    rows = _rows(f"select vintage, value, prov_id from '{_p(CLEAN / unit / (ds + '.parquet'))}' where series_id=? and period=? and unit='INR_crore'", [sid, period])
    assert rows, f"{ds}: {sid} {period} missing"
    top = max(str(r[0]) for r in rows)
    sel = [r for r in rows if str(r[0]) == top]
    assert len(sel) == 1, f"{ds}: {sid}: {len(sel)} rows in the latest vintage"
    return float(sel[0][1]), sel[0][2]


def nas(stmt: str, sid: str) -> float:
    return _val("mospi_nas_2026", f"mospi_nas_2026_{stmt}", sid)[0]


def nas_pid(stmt: str, sid: str) -> str:
    return _val("mospi_nas_2026", f"mospi_nas_2026_{stmt}", sid)[1]


# ------------------------------------------------------------------------------------------ inputs
@cache
def accounts() -> tuple[list[str], dict[str, str]]:
    acc = yaml.safe_load((ROOT / "pipeline" / "sam" / "accounts.yaml").read_text(encoding="utf-8"))["accounts"]
    return [a["code"] for a in acc], {a["code"]: a["group"] for a in acc}


@cache
def all_entries() -> list[tuple]:
    """(block, row, col, ref, component, value, status, role, confidence, tol_rel, prov_id) of every built block."""
    return _rows(f"select block, row, col, ref, component, value, status, role, confidence, tol_rel, prov_id from '{_p(BLOCKS)}/*_entries.parquet' order by block, row, col, ref, component")


def other() -> list[tuple]:
    return [e for e in all_entries() if e[0] != "closure"]


@cache
def closure_entries() -> dict[tuple, tuple]:
    return {(e[1], e[2], e[3], e[4]): e for e in all_entries() if e[0] == "closure"}


@cache
def recompute() -> dict:
    """Plan s.2.1 / s.2.2 and D2-3, from the other blocks' entries only."""
    inc = {g: math.fsum(e[5] for e in other() if e[1] == g) for g in HH}
    out = {g: math.fsum(e[5] for e in other() if e[2] == g) for g in HH}
    cons = {g: math.fsum(e[5] for e in other() if e[2] == g and e[1].startswith("C_")) for g in HH}
    d2 = math.fsum(e[5] for e in other() if e[2] == "X_DISC" and e[3] == "D2")
    d3 = math.fsum(e[5] for e in other() if e[2] == "X_DISC" and e[3] == "D3")
    d4 = math.fsum(e[5] for e in other() if e[2] == "X_DISC" and e[3] == "D4")
    d1tot = math.fsum(e[5] for e in other() if e[2] == "X_DISC")
    tot = math.fsum(inc.values())
    d1 = {g: round(d1tot * inc[g] / tot, 6) for g in HH}
    big = max(HH, key=lambda g: inc[g])
    d1[big] = round(d1[big] + (d1tot - math.fsum(d1.values())), 6)
    k4a = {g: round(inc[g] - out[g] - d1[g], 6) for g in HH}
    k4 = nas("s1_9", "s1_9.household_sector.current")
    return {"inc": inc, "out": out, "cons": cons, "d1": d1, "k4a": k4a, "d1tot": d1tot, "tot": tot,
            "d2": d2, "d3": d3, "d4": d4, "k4": k4, "z": math.fsum(k4a.values()) - k4, "big": big}


def _sat(name: str, dims: str) -> dict:
    return {tuple(r[:-1]): r[-1] for r in _rows(f"select {dims}, value from '{_p(SAT / (name + '.parquet'))}'")}


# ------------------------------------------------------------------------------------------ tests
def test_closure_read_the_dependency_outputs_on_disk():
    """closure is not stale: the sha256 it recorded for each DEPENDS output equals the file on disk."""
    cat = json.loads((BLOCKS / "closure_block.json").read_text(encoding="utf-8"))
    assert sorted(cat["depends"]) == sorted(DEPS)
    for b in DEPS:
        for kind in ("entries", "constraints", "provenance"):
            h = hashlib.sha256((BLOCKS / f"{b}_{kind}.parquet").read_bytes()).hexdigest()
            assert cat["dependency_hashes"][b][kind] == h, f"closure is stale against {b}_{kind}: rebuild closure"


def test_entry_census_values_roles_and_statuses():
    r = recompute()
    ce = closure_entries()
    expected = {("K_HH", g, "K4a", "total"): r["k4a"][g] for g in HH} | {("X_DISC", g, "D1", "total"): r["d1"][g] for g in HH}
    assert set(ce) == set(expected), "closure must write exactly 10 K4a and 10 D1 entries"
    for k, v in expected.items():
        e = ce[k]
        assert abs(e[5] - v) <= EPS, f"{k}: written {e[5]} vs recomputed {v}"
        assert e[6] == "estimated", k
        if k[2] == "K4a":
            assert (e[7], e[8], e[9]) == ("free", "low", None), k
            assert abs(e[5]) >= 1.0, f"{k}: residual below Rs 1 crore (plan s.6 R6)"
        else:
            assert (e[7], e[8], e[9]) == ("fixed", None, None), k
            assert e[5] > 0, k


def test_d1_total_is_the_xdisc_column_and_inside_the_published_band():
    r = recompute()
    pub = _val("mospi_nas_2026", "mospi_nas_2026_derived_residuals", "derived.household_residual.current")[0]
    sut_cif = _val("io_tables", "io_tables_sut_supply", "supply.cif_adj.cif.current")[0]
    sie = _val("mospi_nas_2026", "mospi_nas_2026_derived_residuals", "derived.si_errors_omissions.current")[0]
    written = math.fsum(e[5] for e in closure_entries().values() if e[3] == "D1")
    assert abs(written - (r["d2"] + r["d3"] + r["d4"])) <= EPS  # D2-3: X_DISC closes exactly
    assert abs(written - pub) <= 1.0  # the published residual as a +-1 band
    assert abs(r["d2"] - sut_cif) <= 0.01  # rest_of_world uses the SUT CIF (plan C3)
    assert abs(r["d3"] - sie) <= 0.01
    assert r["d4"] == 0.0
    # the largest-income group absorbs the rounding remainder; the key is prior gross income
    assert r["big"] == max(HH, key=lambda g: r["inc"][g])
    for g in HH:
        assert abs(r["d1"][g] / r["d1tot"] - r["inc"][g] / r["tot"]) <= 1e-9


def test_household_accounts_close_in_the_prior():
    """Option A (plan C7 / T3): every H_g row total = column total, K4a and D1 included."""
    for g in HH:
        rt = math.fsum(e[5] for e in all_entries() if e[1] == g)
        ct = math.fsum(e[5] for e in all_entries() if e[2] == g)
        assert abs(rt - ct) <= 1e-5, f"{g}: {rt - ct}"


def test_constraint_targets_from_clean():
    c = {r[0]: r[1:] for r in _rows(f"select constraint_id, ref, rows, cols, refs, components, target, tol_abs, tol_rel, kind from '{_p(BLOCKS / 'closure_constraints.parquet')}'")}
    assert set(c) == {"k4.hh_saving_total", "d1.published_total"}
    k4 = nas("s1_9", "s1_9.household_sector.current")
    assert k4 == nas("s1_14", "s1_14.households_npish.gross_savings.current") == nas("s5_3", "s5_3.household_saving_1_2_3_4.current")
    assert c["k4.hh_saving_total"] == ("K4", "K_HH", ",".join(HH), "K4a", None, k4, 0.5, 0.0, "equal")
    pub = _val("mospi_nas_2026", "mospi_nas_2026_derived_residuals", "derived.household_residual.current")[0]
    assert c["d1.published_total"] == ("D1", "X_DISC", ",".join(HH), "D1", None, pub, 1.0, 0.0, "band")
    # the published residual is the NAS 1.14 and the NAS 1.1 identity
    via_114 = nas("s1_14", "s1_14.households_npish.gross_disposable_income.current") - nas("s1_14", "s1_14.households_npish.final_consumption_expenditure.current") - nas("s1_14", "s1_14.households_npish.gross_savings.current")
    via_11 = nas("s1_1", "s1_1.gndi.current") - nas("s1_1", "s1_1.pfce.current") - nas("s1_1", "s1_1.gfce.current") - nas("s1_1", "s1_1.gross_saving.current")
    assert abs(via_114 - pub) <= 0.01 and abs(via_11 - pub) <= 0.01
    # the K4 constraint is a duplicate (same selection, kind and target) of capital_financial's: it merges
    cf = _rows(f"select rows, cols, refs, components, target, kind from '{_p(BLOCKS / 'capital_financial_constraints.parquet')}' where refs='K4a'")
    assert cf == [("K_HH", ",".join(HH), "K4a", None, k4, "equal")]


def test_checks_recompute_from_clean():
    r = recompute()
    ch = {x[0]: x[1:] for x in _rows(f"select check_id, sam_value, target, diff, tol_abs, ok from '{_p(BLOCKS / 'closure_checks.parquet')}'")}
    pub = _val("mospi_nas_2026", "mospi_nas_2026_derived_residuals", "derived.household_residual.current")[0]
    valuables = _val("io_tables", "io_tables_sut_use", "use.valuables.total.current")[0]
    gold = nas("s1_9", "s1_9.saving_in_the_form_of_gold_and_silver_ornaments.current")
    d3_khh = math.fsum(e[5] for e in other() if e[1] == "K_HH" and e[2] == "X_DISC")
    row_net = (nas("s6_1", "s6_1.property_and_entrepreneurial_income_from_rest_of_the_world.current") - nas("s6_1", "s6_1.property_and_entrepreneurial_income_to_the_rest_of_the_world.current")
               + nas("s6_1", "s6_1.other_current_transfers_to_resident_sectors_other_than_gener.current") - nas("s6_1", "s6_1.other_current_transfers_by_resident_sectors_other_than_gener.current"))
    exp = {
        "d1.written_vs_published": (r["d1tot"], pub, True),
        "d2.written_vs_sut_cif": (r["d2"], _val("io_tables", "io_tables_sut_supply", "supply.cif_adj.cif.current")[0], True),
        "d3.written_vs_nas": (r["d3"], _val("mospi_nas_2026", "mospi_nas_2026_derived_residuals", "derived.si_errors_omissions.current")[0], True),
        "d3.k_hh_vs_unsectored_valuables": (d3_khh, valuables - gold, True),
        "x_disc.prior_closure": (math.fsum(r["d1"].values()), r["d2"] + r["d3"] + r["d4"], True),
        "k4.prior_sum_vs_nas": (math.fsum(r["k4a"].values()), r["k4"], False),  # fails by Z on purpose (closure-3)
        "required_flows.identity": (None, row_net, True),
    }
    assert set(ch) == set(exp) | {"d1.published_identity_s1_14", "d1.published_identity_s1_1"}
    for k, (sv, tg, ok) in exp.items():
        if sv is not None:
            assert abs(ch[k][0] - sv) <= EPS, (k, ch[k][0], sv)
        assert abs(ch[k][1] - tg) <= EPS, (k, ch[k][1], tg)
        assert ch[k][4] == ok, k
    for k in ("d1.published_identity_s1_14", "d1.published_identity_s1_1"):
        assert abs(ch[k][1] - pub) <= EPS and ch[k][4]
    # the D3 posting to K_HH equals the I2a valuables cell to the paisa (plan C5)
    i2a = math.fsum(e[5] for e in other() if e[3] == "I2a")
    assert abs(d3_khh - i2a) <= EPS


def test_hh_saving_satellite():
    r = recompute()
    s = _sat("hh_saving", "household_group, measure")
    pers = {x[0]: x[1] for x in _rows(f"select household_group, value from '{_p(BLOCKS / 'households_satellites' / 'hh_keys.parquet')}' where key='pop_persons' and measure='level'")}
    inc, out, cons, k4a, d1, z = r["inc"], r["out"], r["cons"], r["k4a"], r["d1"], r["z"]
    exp = {("ALL", "d1"): r["d1tot"], ("ALL", "gross_income"): r["tot"], ("ALL", "k4_nas"): r["k4"],
           ("ALL", "k4a_sum"): math.fsum(k4a.values()), ("ALL", "z"): z}
    for g in HH:
        paid = out[g] - cons[g]
        exp |= {(g, "gross_income"): inc[g], (g, "outlays_excl_saving"): out[g], (g, "pfce"): cons[g],
                (g, "current_transfers_paid"): paid, (g, "disposable_income"): inc[g] - paid, (g, "d1"): d1[g],
                (g, "d1_key"): inc[g] / r["tot"], (g, "k4a"): k4a[g], (g, "k4a_option_b"): k4a[g] - z * inc[g] / r["tot"],
                (g, "persons"): pers[g], (g, "k4a_per_person"): k4a[g] * 1e7 / pers[g],
                (g, "saving_rate_gross_income"): 100 * k4a[g] / inc[g],
                (g, "saving_rate_disposable_income"): 100 * k4a[g] / (inc[g] - paid),
                (g, "saving_rate_spending"): 100 * k4a[g] / (cons[g] + k4a[g]),
                (g, "d1_by_pfce"): r["d1tot"] * cons[g] / math.fsum(cons.values()),
                (g, "d1_by_population"): r["d1tot"] * pers[g] / math.fsum(pers.values())}
    for area, gs in (("RURAL", HH[:5]), ("URBAN", HH[5:])):
        k = math.fsum(k4a[g] for g in gs)
        exp[(area, "saving_rate_spending")] = 100 * k / (math.fsum(cons[g] for g in gs) + k)
        exp[(area, "ifpri_saving_rate_2022_23")] = _rows(f"select value from '{_p(CLEAN / 'io_tables' / 'io_tables_ifpri_2223_datapaper.parquet')}' where series_id=? and period='2022-23' and unit='percent'", [f"ifpri.t11.savings_rate.{area.lower()}"])[0][0]
    assert set(s) == set(exp)
    for k, v in exp.items():
        assert abs(s[k] - v) <= 1e-6 * max(1.0, abs(v)), (k, s[k], v)
    # option B sums to NAS; the D1 sensitivities keep the total
    assert abs(math.fsum(s[(g, "k4a_option_b")] for g in HH) - r["k4"]) <= 1e-4
    for m in ("d1_by_pfce", "d1_by_population"):
        assert abs(math.fsum(s[(g, m)] for g in HH) - r["d1tot"]) <= 1e-4


def test_xdisc_identity_satellite():
    r = recompute()
    s = _sat("xdisc_identity", "item")
    pub = _val("mospi_nas_2026", "mospi_nas_2026_derived_residuals", "derived.household_residual.current")[0]
    n61 = nas("s6_1", "s6_1.adjustment_for_cif_in_import_of_services.current")
    exp = {"d1_published": pub, "d1_written": r["d2"] + r["d3"] + r["d4"], "d2_written": r["d2"], "d3_written": r["d3"],
           "d4_written": r["d4"], "ref_d2_nas61_cif": n61,
           "ref_d2_sut_cif": _val("io_tables", "io_tables_sut_supply", "supply.cif_adj.cif.current")[0],
           "ref_d3_nas_si_errors": _val("mospi_nas_2026", "mospi_nas_2026_derived_residuals", "derived.si_errors_omissions.current")[0],
           "residual_published_minus_written": pub - (r["d2"] + r["d3"] + r["d4"]),
           "residual_with_nas61_cif": pub - (n61 + r["d3"] + r["d4"])}
    assert set(k[0] for k in s) == set(exp)
    for k, v in exp.items():
        assert abs(s[(k,)] - v) <= EPS, (k, s[(k,)], v)


def test_prior_imbalance_satellite_all_128_accounts():
    codes, grp = accounts()
    rt, ct, nvr, nvc = defaultdict(float), defaultdict(float), defaultdict(int), defaultdict(int)
    for e in all_entries():
        rt[e[1]] += e[5]
        ct[e[2]] += e[5]
        if e[7] != "fixed":
            nvr[e[1]] += 1
            nvc[e[2]] += 1
    imb = {c: rt[c] - ct[c] for c in codes}
    assert abs(math.fsum(imb.values())) <= 1e-6  # the global SAM identity
    s = _sat("prior_imbalance", 'account, "group", measure')
    assert len(s) == 7 * len(codes) == 896
    order = sorted(codes, key=lambda c: (-abs(imb[c]), codes.index(c)))
    for c in codes:
        big = max(abs(rt[c]), abs(ct[c]))
        exp = {"row_total": rt[c], "col_total": ct[c], "imbalance": imb[c], "n_var_row": nvr[c], "n_var_col": nvc[c],
               "imbalance_pct": 100 * imb[c] / big if big > 0 else 0.0}
        for m, v in exp.items():
            assert abs(s[(c, grp[c], m)] - v) <= 1e-5, (c, m, s[(c, grp[c], m)], v)
        if abs(imb[c]) >= 1.0:  # ranks among rounding-size imbalances are not meaningful
            assert s[(c, grp[c], "rank")] == order.index(c) + 1, c
    # K_HH carries exactly Z (option A); the household and X_DISC accounts close
    assert abs(imb["K_HH"] - recompute()["z"]) <= 1e-5
    for c in HH + ["X_DISC"]:
        assert abs(imb[c]) <= 1e-5, c


def test_constraint_gaps_satellite_every_declared_constraint():
    idx = defaultdict(list)
    for e in all_entries():
        idx[(e[1], e[2])].append(e)
    cs = _rows(f"select block, constraint_id, ref, rows, cols, refs, components, target, tol_abs, tol_rel, kind from '{_p(BLOCKS)}/*_constraints.parquet'")
    s = defaultdict(dict)
    for x in _rows(f"select constraint_id, block, ref, kind, outside_band, measure, value from '{_p(SAT / 'constraint_gaps.parquet')}'"):
        s[x[0]]["meta"] = x[1:5]
        s[x[0]][x[5]] = x[6]
    assert len(s) == len(cs)
    outside = []
    for blk, cid, ref, rows, cols, refs, comps, tgt, ta, tr, kind in cs:
        rf = set(refs.split(",")) if refs else None
        cp = set(comps.split(",")) if comps else None
        sel = [e for r_ in rows.split(",") for c_ in cols.split(",") for e in idx.get((r_, c_), [])
               if (rf is None or e[3] in rf) and (cp is None or e[4] in cp)]
        tot = math.fsum(e[5] for e in sel)
        tol = max(ta, tr * abs(tgt))
        lo = tgt - tol if kind in ("equal", "band", "min") else None
        hi = tgt + tol if kind in ("equal", "band", "max") else None
        ob = (lo is not None and tot < lo - 1e-9) or (hi is not None and tot > hi + 1e-9)
        g = s[f"{blk}:{cid}"]
        assert g["meta"] == (blk, ref, kind, "yes" if ob else "no"), (blk, cid)
        for m, v in (("prior_sum", tot), ("target", tgt), ("gap", tot - tgt), ("n_members", len(sel)), ("lo", lo), ("hi", hi)):
            if v is None:
                assert m not in g, (blk, cid, m)
            else:
                # + the framework's 12-significant-digit cap on satellite values (framework._sig, Wave C repro)
                assert abs(g[m] - v) <= 1e-5 + 1e-11 * abs(v), (blk, cid, m, g[m], v)
        if ob:
            outside.append(f"{blk}:{cid}")
    # the prior misses only the two (identical) K4 declarations, by Z
    assert sorted(outside) == ["capital_financial:cf.k4.hh_saving", "closure:k4.hh_saving_total"]


def _required() -> dict[str, tuple[float, float]]:
    """Plan table 2.4-C: (NAS total, NAS primary income) by institution, from clean NAS 2026."""
    fin_a = nas("s7_1a", "s7_1a.financial.os.current") + nas("s7_1a", "s7_1a.financial.cfc.current")
    fin_b = nas("s7_1b", "s7_1b.financial.os.current") + nas("s7_1b", "s7_1b.financial.cfc.current")
    npt = math.fsum(nas(t, f"{t}.total.net_production_taxes.current") for t in ("s7_1a", "s7_1b", "s7_1c"))
    ce = _val("mospi_nas_2026", "mospi_nas_2026_derived_residuals", "derived.ce_receivable_by_residents.current")[0]
    return {
        "HH": (nas("s1_14", "s1_14.households_npish.gross_disposable_income.current"),
               ce + nas("s7_1c", "s7_1c.total.os_mi.current") + nas("s7_1c", "s7_1c.total.cfc.current")),
        "E_NFPU": (nas("s1_9", "s1_9.public_non_financial_corporations.current"),
                   nas("s7_1a", "s7_1a.total.os.current") + nas("s7_1a", "s7_1a.total.cfc.current") - fin_a
                   - nas("s8_15_1", "s8_15_1.total.os.current") - nas("s8_15_1", "s8_15_1.total.cfc.current")),
        "E_NFPR": (nas("s1_9", "s1_9.private_non_financial_corporations.current"),
                   nas("s7_1b", "s7_1b.total.os.current") + nas("s7_1b", "s7_1b.total.cfc.current") - fin_b),
        "FC": (nas("s1_9", "s1_9.financial_corporations.current"), fin_a + fin_b),
        "GG": (nas("s1_14", "s1_14.gg.gross_disposable_income.current"),
               nas("s1_14", "s1_14.gg.consumption_of_fixed_capital.current") + nas("s1_1", "s1_1.taxes_on_products.current")
               - nas("s1_1", "s1_1.subsidies_on_products.current") + npt),
    }


def test_required_flows_add_up_to_the_rest_of_the_world_net():
    req = _required()
    row_net = (nas("s6_1", "s6_1.property_and_entrepreneurial_income_from_rest_of_the_world.current") - nas("s6_1", "s6_1.property_and_entrepreneurial_income_to_the_rest_of_the_world.current")
               + nas("s6_1", "s6_1.other_current_transfers_to_resident_sectors_other_than_gener.current") - nas("s6_1", "s6_1.other_current_transfers_by_resident_sectors_other_than_gener.current"))
    assert abs(math.fsum(t - p for t, p in req.values()) - row_net) <= 0.01


def test_institution_gaps_satellite():
    codes, grp = accounts()

    def cls(e: tuple, inside: set[str]) -> str:
        cp = e[2] if e[1] in inside else e[1]
        g = grp[cp]
        if g in ("FAC", "COM", "CAP", "DISC"):
            return {"FAC": "factor_income", "COM": "final_consumption", "CAP": "saving", "DISC": "discrepancy"}[g]
        if g == "TAX":
            return "current_taxes" if cp in ("T_PIT", "T_CIT") else "taxes_on_production_imports"
        return "property_income" if e[3] in PROP else "social" if e[3] in SOC else "other_transfers" if e[3] in OTH else "unclassified"

    sets = {g: [g] for g in HH} | {"HH": HH, "E_NFPU": ["E_NFPU"], "E_NFPR": ["E_NFPR"], "E_RBI": ["E_RBI"], "E_BANK": ["E_BANK"],
                                   "E_NBFC": ["E_NBFC"], "E_INSP": ["E_INSP"], "FC": [c for c in codes if grp[c] == "FC"],
                                   "G_CEN": ["G_CEN"], "G_STA": ["G_STA"], "GG": [c for c in codes if grp[c] == "GOV"]}
    exp = {}
    for name, mem in sets.items():
        ms = set(mem)
        tot = defaultdict(float)
        for e in all_entries():
            ri, ci = e[1] in ms, e[2] in ms
            if ri != ci:
                tot[cls(e, ms)] += e[5] if ri else -e[5]
        for k in ("factor_income", "final_consumption", "saving", "discrepancy", "taxes_on_production_imports",
                  "current_taxes", "property_income", "social", "other_transfers", "unclassified"):
            exp[(name, k + ".net")] = tot[k]
        exp[(name, "delivered_net")] = tot["current_taxes"] + tot["property_income"] + tot["social"] + tot["other_transfers"] + tot["unclassified"]
        exp[(name, "imbalance")] = math.fsum(tot.values())
    req = _required()
    for k, (t, p) in req.items():
        exp |= {(k, "nas_total"): t, (k, "nas_primary_income"): p, (k, "required_net"): t - p,
                (k, "gap"): exp[(k, "delivered_net")] - (t - p),
                (k, "primary_income_gap"): exp[(k, "factor_income.net")] + exp[(k, "taxes_on_production_imports.net")] - p}
    exp[("DOMESTIC", "required_net")] = math.fsum(t - p for t, p in req.values())
    exp[("DOMESTIC", "delivered_net")] = math.fsum(exp[(k, "delivered_net")] for k in req)
    exp[("DOMESTIC", "gap")] = exp[("DOMESTIC", "delivered_net")] - exp[("DOMESTIC", "required_net")]
    exp[("ROW_NET", "required_net")] = (nas("s6_1", "s6_1.property_and_entrepreneurial_income_from_rest_of_the_world.current") - nas("s6_1", "s6_1.property_and_entrepreneurial_income_to_the_rest_of_the_world.current")
                                        + nas("s6_1", "s6_1.other_current_transfers_to_resident_sectors_other_than_gener.current") - nas("s6_1", "s6_1.other_current_transfers_by_resident_sectors_other_than_gener.current"))
    s = _sat("institution_gaps", "institution, measure")
    assert set(s) == set(exp)
    for k, v in exp.items():
        assert abs(s[k] - v) <= 1e-4, (k, s[k], v)  # GG CFC: 8.15.1 vs 1.14 differ by 2.7e-5
    # every institution's primary income equals its NAS figure up to published rounding (< Rs 0.5 crore)
    for k in req:
        assert abs(exp[(k, "primary_income_gap")]) < 0.5, k
    # the household gap is Z up to the PFCE (SUT vs NAS 0.48) and D1 (0.11) roundings
    assert abs(exp[("HH", "gap")] - recompute()["z"]) < 1.0
    # the domestic gaps sum to zero: the prior's institutional accounts are consistent in total
    assert abs(exp[("DOMESTIC", "gap")]) <= 0.01


def test_household_refs_whitelist_and_no_double_counting():
    keys = [(e[1], e[2], e[3], e[4]) for e in all_entries()]
    assert len(keys) == len(set(keys)), "an entry key is written twice"
    for e in other():
        rh, ch = e[1] in HH, e[2] in HH
        assert not (rh and ch), f"intra-household entry {e[:5]}"
        if rh:
            assert e[3] in RESOURCES, f"resource ref outside the whitelist: {e[:5]}"
        if ch:
            assert e[3] in USES, f"use ref outside the whitelist: {e[:5]}"
        # only closure writes K_HH <- H_* (K4a) and X_DISC <- H_* (D1)
        assert not (e[1] in ("K_HH", "X_DISC") and ch), e[:5]
        assert e[3] not in ("K4a", "D1"), e[:5]
    # the X_DISC column holds only D2, D3, D4; D3 valuables are a capital receipt of K_HH, never household income
    assert {e[3] for e in other() if e[2] == "X_DISC"} == {"D2", "D3", "D4"}
    assert not [e for e in other() if e[1] in HH and e[3] in ("D3", "I2", "I2a")]


def test_provenance_records():
    pr = {x[0]: (x[1], {i for i in (x[2] or "").split(",") if i}) for x in _rows(f"select prov_id, status, inputs from '{_p(BLOCKS / 'closure_provenance.parquet')}'")}
    known = set()
    for f in list(CLEAN.glob("*/_provenance.parquet")) + list(BLOCKS.glob("*_provenance.parquet")):
        known |= {x[0] for x in _rows(f"select prov_id from '{_p(f)}'")}
    for pid, (_, inputs) in pr.items():
        assert inputs and inputs <= known, f"{pid}: inputs do not resolve: {sorted(inputs - known)[:5]}"
    ce = closure_entries()
    for e in ce.values():
        assert pr[e[10]][0] == e[6], e[:5]
    k4_pid = nas_pid("s1_9", "s1_9.household_sector.current")
    for g in HH:
        used = {e[10] for e in other() if e[1] == g or e[2] == g} | {ce[("X_DISC", g, "D1", "total")][10], k4_pid}
        assert pr[ce[("K_HH", g, "K4a", "total")][10]][1] == used, g
    # D1 split record: the income key's entries and the D1 total record, which is derived over D2, D3, D4 and the published residual
    d1_split = pr[ce[("X_DISC", "H_R1", "D1", "total")][10]][1]
    assert {e[10] for e in other() if e[1] in HH} <= d1_split
    xdisc = {e[10] for e in other() if e[2] == "X_DISC"}
    pub_pid = _val("mospi_nas_2026", "mospi_nas_2026_derived_residuals", "derived.household_residual.current")[1]
    totals = [pid for pid, (st, inp) in pr.items() if st == "derived" and inp == xdisc | {pub_pid}]
    assert len(totals) == 1 and totals[0] in d1_split
    # constraint records: K4 official over NAS 1.9; D1 derived over the published residual
    c = dict(_rows(f"select constraint_id, prov_id from '{_p(BLOCKS / 'closure_constraints.parquet')}'"))
    assert pr[c["k4.hh_saving_total"]] == ("official", {k4_pid})
    assert pr[c["d1.published_total"]] == ("derived", {pub_pid})
