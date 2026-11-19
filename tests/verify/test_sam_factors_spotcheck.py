"""Independent verification of the SAM `factors` block (Phase 2 verifier, 2026-09-30; SPEC s.3 rule 3).

This file does NOT import pipeline.sam (no block, helper, framework or spec code) and does not use polars.
Every expected number is recomputed here with DuckDB SQL plus plain Python from:
- data/clean/io_tables: SUT 2023-24 value added (`va.ce/os_mi/cfc.sut_iNN.current`, published-table record
  io_tables:d1e9110c5674), aggregated with data/concordance/io_tables_sut_industry_to_sam34.csv; IFPRI 2022/23
  T10 (factor shares by national quintile) and T11 (total spending per capita);
- data/clean/labour_enterprise_surveys: PLFS 2023-24 Tables 20, 26, 35, 51, WPR (ps+ss), API indicators 6/7/8
  (Q1-Q4 2023-24); ASUSE 2023-24 Tables 4, 6, 33, 37 (period 2023-10/2024-09);
- data/clean/mospi_nas_2026: Statements 4.1, 6.1, 7.1A, 7.1B, 7.1C, 8.15.1 and the derived CE-receivable row;
- data/clean/union_fiscal: Finance Accounts 2023-24 grants-in-aid to autonomous bodies;
- the DEPENDS outputs the block legitimately reads: production's constraints, households' C4a entries,
  `hh_keys` (pop_persons, aidis_fixed_assets) and `hh_national_quintile_xwalk`;
- data/sam/2023-24/blocks/*_entries.parquet of all built blocks (double counting, account closure).
It is compared with the block's written outputs (data/sam/2023-24/blocks/factors_*): a census of all 227
entries, all 62 constraint targets and the recomputable satellite rows.

Findings are recorded in docs/phase2/verify/factors.md (V-F-n). A confirmed defect is a strict xfail with its id.
Maintenance 2026-09-30 (docs/phase2/issues/factors.md, Verification dispositions): V-F-2, V-F-3, V-F-4, V-F-5 and
V-F-6 were fixed in the block; their strict xfails are ordinary tests and the census expects the fixed method
(trade on ASUSE T1-T5, utilities' rural/urban key PLFS 35-39, wage bills in Rs crore).
2026-10-01 (block maintainer, DECISIONS D2-19): the block maps IFPRI's national-quintile gradients with k = q, so
the expectations that pinned the crosswalk mapping now use MAPPING = "k_eq_q"; the crosswalk is checked as the
`sensitivity_xwalk_*` rows, and V-F-1 (fixed by the switch) is an ordinary test.
Re-verification (wave C close-out, 2026-10-01; a different agent from the fixers): every expectation the fixers changed
was recomputed independently (scratch code, not this file) and confirmed; added checks of all D2-19 sensitivity rows
(crosswalk and HCES variants, every key, levels, area shares and group totals), the casual wage bills, and the
`f4b.centre` band's kind, selection and tolerance rule (docs/phase2/verify/factors.md, "Re-verification").
"""

# ruff: noqa: E501  (long SQL / series ids are kept on one line)
from __future__ import annotations

import csv
import hashlib
import json
from functools import cache
from pathlib import Path

import duckdb
import pytest

pytestmark = [pytest.mark.quality, pytest.mark.sam]

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean"
BLOCKS = ROOT / "data" / "sam" / "2023-24" / "blocks"
HSAT = BLOCKS / "households_satellites"
FSAT = BLOCKS / "factors_satellites"
TOL = 0.01  # Rs crore, census tolerance (outputs are written to 6 decimals)
YEAR = "2023-24"
PLFS = "2023-07/2024-06"
ASUSE = "2023-10/2024-09"
Q23 = ["Q1 2023-24", "Q2 2023-24", "Q3 2023-24", "Q4 2023-24"]
AREAS = ["rural", "urban"]
HH = ["H_R1", "H_R2", "H_R3", "H_R4", "H_R5", "H_U1", "H_U2", "H_U3", "H_U4", "H_U5"]
AREA_OF = {g: ("rural" if g.startswith("H_R") else "urban") for g in HH}
QS = ["q1", "q2", "q3", "q4", "q5"]

# PLFS Table 20 industry groups -> NIC sections (Table 26 / Table 51); plan s.2.1 step 2
PLFS_GROUPS = {"01-03": ["a"], "05-09": ["b"], "10-33": ["c"], "35-39": ["d", "e"], "41-43": ["f"], "45-47": ["g"],
               "49-53": ["h"], "55-56": ["i"], "58-99": list("jklmnopqrst")}  # fmt: skip
MANUF = [
    "A_FOOD",
    "A_BVTB",
    "A_TXAP",
    "A_WOOD",
    "A_GJOM",
    "A_RPET",
    "A_CHEM",
    "A_PHRM",
    "A_NMMN",
    "A_MTLS",
    "A_MACH",
    "A_ELEQ",
    "A_TREQ",
]
ACT_GROUP = {"A_CROP": "01-03", "A_LVST": "01-03", "A_FOFI": "01-03", "A_COAL": "05-09", "A_OILG": "05-09", "A_OMIN": "05-09",
             "A_UTIL": "35-39", "A_CNST": "41-43", "A_TRAD": "45-47", "A_TRNS": "49-53", "A_HOTL": "55-56",
             **{a: "10-33" for a in MANUF},
             **{a: "58-99" for a in ["A_COMM", "A_FINS", "A_INSR", "A_DWEL", "A_BSRE", "A_ITSV", "A_EDUC", "A_HLTH", "A_OSRV", "A_PADM"]}}  # fmt: skip
# NAS 7.1C rows -> SAM activities (plan s.2.2 table)
NASGRP = {"crops": (["crops"], ["A_CROP"]), "livestock": (["livestock"], ["A_LVST"]),
          "forestry_fishing": (["forestry", "fishing"], ["A_FOFI"]), "mining": (["mining"], ["A_COAL", "A_OILG", "A_OMIN"]),
          "manufacturing": (["manufacturing"], MANUF), "utilities": (["utilities"], ["A_UTIL"]),
          "construction": (["construction"], ["A_CNST"]), "trade_repair": (["trade_repair"], ["A_TRAD"]),
          "hotels": (["hotels"], ["A_HOTL"]),
          "transport": (["railways", "road_transport", "water_transport", "transport_services", "storage"], ["A_TRNS"]),
          "communication": (["communication"], ["A_COMM"]), "financial": (["financial"], ["A_FINS", "A_INSR"]),
          "real_estate_prof": (["real_estate_prof"], ["A_DWEL", "A_BSRE", "A_ITSV"]),
          "other_services": (["other_services"], ["A_EDUC", "A_HLTH", "A_OSRV"])}  # fmt: skip
# ASUSE categories by activity (plan s.2.2 step 4). Trade uses the sub-categories T1-T5 like every other activity
# (V-F-2, fixed in the 2026-09-30 maintenance rebuild; the 22:30/23:07 builds used the aggregate T)
ASU_MAP = {"A_FOOD": ["m2"], "A_BVTB": ["m3", "m4"], "A_TXAP": ["m1", "m5", "m6", "m7"], "A_WOOD": ["m8", "m9", "m10", "m23"],
           "A_GJOM": ["m24"], "A_RPET": ["m11"], "A_CHEM": ["m12", "m14"], "A_PHRM": ["m13"], "A_NMMN": ["m15"], "A_MTLS": ["m16"],
           "A_MACH": ["m17", "m20", "m25"], "A_ELEQ": ["m18", "m19"], "A_TREQ": ["m21", "m22"],
           "A_EDUC": ["s13"], "A_HLTH": ["s14"], "A_OSRV": ["s15"], "A_TRAD": ["t1", "t2", "t3", "t4", "t5"], "A_HOTL": ["s1", "s2"],
           "A_TRNS": ["s3", "s4", "s5", "s6"], "A_COMM": ["s7"], "A_ITSV": ["s7"], "A_BSRE": ["s10", "s11", "s12"]}  # fmt: skip
NONPROP = ["partnership_diff_hh", "society_trust", "cooperative", "others"]
FARM = ["A_CROP", "A_LVST", "A_FOFI"]
FACTOR_ACCOUNTS = ["F_LREG", "F_LCAS", "F_MIXD", "F_GOSC"]


def _p(path: Path) -> str:
    return path.as_posix()


@cache
def con() -> duckdb.DuckDBPyConnection:
    for f in ("factors_entries", "factors_constraints", "factors_provenance", "factors_checks"):
        if not (BLOCKS / f"{f}.parquet").exists():
            pytest.fail(f"{f}.parquet missing: run `uv run python -m pipeline sam factors`")
    return duckdb.connect()


@cache
def _series(unit: str, dataset: str) -> dict[tuple[str, str], float]:
    """(series_id, period) -> value of the latest vintage; fails on a duplicate within that vintage."""
    rows = (
        con()
        .execute(
            f"select series_id, period, vintage, value, prov_id from '{_p(CLEAN / unit / (dataset + '.parquet'))}'"
        )
        .fetchall()
    )
    best: dict[tuple[str, str], tuple[str, list[tuple[float, str]]]] = {}
    for sid, per, vint, val, pid in rows:
        k = (sid, per)
        if k not in best or vint > best[k][0]:
            best[k] = (vint, [(val, pid)])
        elif vint == best[k][0]:
            best[k][1].append((val, pid))
    out = {}
    for k, (_, vals) in best.items():
        if len(vals) == 1:
            out[k] = vals[0][0]
    return out


def v(unit: str, dataset: str, sid: str, period: str = YEAR) -> float:
    d = _series(unit, dataset)
    assert (sid, period) in d, f"{dataset}: {sid} {period} missing or ambiguous"
    return d[sid, period]


def les(ds: str, sid: str, period: str) -> float:
    return v("labour_enterprise_surveys", "labour_enterprise_surveys_" + ds, sid, period)


def nas(tab: str, sid: str) -> float:
    return v("mospi_nas_2026", "mospi_nas_2026_" + tab, sid)


def asu(sid: str) -> float:
    return les("asuse_2324_activity", sid, ASUSE)


def ifp(sid: str) -> float:
    return v("io_tables", "io_tables_ifpri_2223_datapaper", sid, "2022-23")


# ------------------------------------------------------------------------------------------ recomputation
@cache
def sut() -> dict:
    """CE and GOS (OS/MI + CFC) by activity from the published SUT value-added record and the concordance."""
    f = _p(CLEAN / "io_tables" / "io_tables_sut_va.parquet")
    rows = (
        con()
        .execute(f"select series_id, value from '{f}' where period='{YEAR}' and prov_id='io_tables:d1e9110c5674'")
        .fetchall()
    )
    va = dict(rows)
    assert len(va) == len(rows), "duplicate SUT VA series in the published record"
    ce: dict[str, float] = {}
    gos: dict[str, float] = {}
    cfc: dict[str, float] = {}
    acts: list[str] = []
    with open(ROOT / "data" / "concordance" / "io_tables_sut_industry_to_sam34.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            a, i = r["activity"], int(r["sut_industry"])
            if a not in acts:
                acts.append(a)
            ce[a] = ce.get(a, 0.0) + va[f"va.ce.sut_i{i:02d}.current"]
            gos[a] = gos.get(a, 0.0) + va[f"va.os_mi.sut_i{i:02d}.current"] + va[f"va.cfc.sut_i{i:02d}.current"]
            cfc[a] = cfc.get(a, 0.0) + va[f"va.cfc.sut_i{i:02d}.current"]
    return {"acts": acts, "ce": ce, "gos": gos, "cfc": cfc}


@cache
def hkeys() -> dict:
    f = _p(HSAT / "hh_keys.parquet")
    out: dict[str, dict[str, float]] = {}
    for key, g, val in (
        con()
        .execute(
            f"select key, household_group, value from '{f}' where measure='level' and key in ('pop_persons','aidis_fixed_assets','hces_total')"
        )
        .fetchall()
    ):
        out.setdefault(key, {})[g] = val
    xw: dict[str, dict[str, float]] = {}
    fx = _p(HSAT / "hh_national_quintile_xwalk.parquet")
    for g, q, val in (
        con().execute(f"select household_group, national_quintile, value from '{fx}' where measure='share'").fetchall()
    ):
        xw.setdefault(g, {})[q] = val
    he = _p(BLOCKS / "households_entries.parquet")
    c4a = dict(con().execute(f"select component, sum(value) from '{he}' where ref='C4a' group by component").fetchall())
    c4a_imp = dict(
        con().execute(f"select col, value from '{he}' where ref='C4a' and component='imputed_rent'").fetchall()
    )
    return {"pop": out["pop_persons"], "aidis": out["aidis_fixed_assets"], "hces": out["hces_total"], "xw": xw, "c4a": c4a,
            "c4a_imp": c4a_imp}  # fmt: skip


def _api_mean(sid: str) -> float:
    return sum(les("plfs_earnings_api", sid, q) for q in Q23) / 4


@cache
def labour() -> dict:
    """V1a (plan s.2.1): PLFS wage bills by group and area, share_reg, D; entries by activity."""
    s = sut()
    pop = hkeys()["pop"]
    pop_area = {a: sum(pop[g] for g in HH if AREA_OF[g] == a) for a in AREAS}
    wpr = {a: les("plfs_lfs_indicators", f"lfs.wpr.ps_ss.all.{a}.person", PLFS) for a in AREAS}
    ereg = {a: 12 * _api_mean(f"api_i6.regular_wage_earnings_month.{a}.person.current") for a in AREAS}
    se = {a: 12 * _api_mean(f"api_i8.self_employment_gross_earnings_30d.{a}.person.current") for a in AREAS}
    d_days = asu("t33.emol_per_hired_worker.informal.asuse_all.total.current") / _api_mean(
        "api_i7.casual_wage_earnings_day.total.person.current"
    )
    t51 = _series("labour_enterprise_surveys", "labour_enterprise_surveys_plfs_earnings")
    reg, cas, sel, fallbacks = {}, {}, {}, []
    for g, secs in PLFS_GROUPS.items():
        for a in AREAS:
            sh = sum(les("plfs_industry_dist", f"t26.worker_share.{x}.{a}.person", PLFS) for x in secs)
            workers = wpr[a] / 100 * pop_area[a] * sh / 100
            wsum = 0.0
            for x in secs:
                k = (f"t51.casual_wage_day.{x}.{a}.person.current", PLFS)
                if k not in t51:
                    fallbacks.append((x, a))
                    k = (f"t51.casual_wage_day.{x}.total.person.current", PLFS)
                wsum += les("plfs_industry_dist", f"t26.worker_share.{x}.{a}.person", PLFS) * t51[k]
            t20 = {
                st: les("plfs_industry_status", f"t20.worker_share.{st}.{g}.{a}.person", PLFS)
                for st in ("regular_wage", "casual_labour", "self_employed")
            }
            reg[g, a] = workers * t20["regular_wage"] / 100 * ereg[a]
            cas[g, a] = workers * t20["casual_labour"] / 100 * (wsum / sh) * d_days
            sel[g, a] = workers * t20["self_employed"] / 100 * se[a]
    share_reg = {g: sum(reg[g, a] for a in AREAS) / sum(reg[g, a] + cas[g, a] for a in AREAS) for g in PLFS_GROUPS}
    v1a = {}
    for act in s["acts"]:
        if s["ce"][act] == 0:
            continue
        if act == "A_PADM":  # plan s.2.1 step 7: all regular
            v1a["F_LREG", act] = s["ce"][act]
            continue
        r = share_reg[ACT_GROUP[act]] * s["ce"][act]
        v1a["F_LREG", act] = r
        v1a["F_LCAS", act] = s["ce"][act] - r
    return {
        "reg": reg,
        "cas": cas,
        "sel": sel,
        "share_reg": share_reg,
        "d_days": d_days,
        "v1a": v1a,
        "fallbacks": fallbacks,
    }


def cat_gva(cat: str, area: str = "total") -> float:
    return sum(
        asu(f"t4.establishments.asuse_{cat}.{area}.{t}") * asu(f"t37.gva_per_estt.asuse_{cat}.{area}.{t}.current")
        for t in ("oae", "hwe")
    )


def cat_surplus(cat: str, area: str = "total") -> float:
    return cat_gva(cat, area) - asu(f"t33.hired_workers.all.asuse_{cat}.{area}") * asu(
        f"t33.emol_per_hired_worker.all.asuse_{cat}.{area}.current"
    )


def cat_nonprop_gva(cat: str, area: str = "total") -> float:
    tot = 0.0
    for t in ("oae", "hwe"):
        sh = sum(asu(f"t6.estt_share.{o}.asuse_{cat}.{area}.{t}") for o in NONPROP) / 100
        tot += (
            sh
            * asu(f"t4.establishments.asuse_{cat}.{area}.{t}")
            * asu(f"t37.gva_per_estt.asuse_{cat}.{area}.{t}.current")
        )
    return tot


def _ras(
    rows: dict[str, float], cols: dict[str, float], prior: dict[str, dict[str, float]]
) -> dict[str, dict[str, float]]:
    x = {a: dict(p) for a, p in prior.items()}
    for _ in range(10000):
        for a in x:
            f = rows[a] / sum(x[a].values())
            for c in x[a]:
                x[a][c] *= f
        err = 0.0
        for c in cols:
            f = cols[c] / sum(x[a][c] for a in x)
            for a in x:
                x[a][c] *= f
            err = max(err, abs(f - 1))
        if err < 1e-13:
            break
    return x


def c71c(row: str) -> float:
    return nas("s7_1c", f"s7_1c.{row}.os_mi.current") + nas("s7_1c", f"s7_1c.{row}.cfc.current")


@cache
def surplus() -> dict:
    """V2a (plan s.2.2): household part by activity, hh_quasi, dwellings, corp_gov."""
    s = sut()
    gos = s["gos"]
    hhg = {k: sum(c71c(r) for r in rows) for k, (rows, _) in NASGRP.items()}
    hha: dict[str, float] = {}
    for k in (
        "crops",
        "livestock",
        "forestry_fishing",
        "utilities",
        "construction",
        "trade_repair",
        "hotels",
        "transport",
        "communication",
    ):
        hha[NASGRP[k][1][0]] = hhg[k]
    hha["A_OMIN"] = hhg["mining"]  # plan step 3: household mining is quarrying
    for k in ("manufacturing", "other_services"):
        acts = NASGRP[k][1]
        prior = {a: {"hh": sum(cat_surplus(c) for c in ASU_MAP[a]), "rest": gos[a]} for a in acts}
        x = _ras({a: gos[a] for a in acts}, {"hh": hhg[k], "rest": sum(gos[a] for a in acts) - hhg[k]}, prior)
        for a in acts:
            hha[a] = x[a]["hh"]
    g9 = ["s7", "s10", "s11", "s12"]
    emol9 = sum(cat_gva(c) - cat_surplus(c) for c in g9)
    ratio9 = sum(cat_surplus(c) for c in g9) / emol9
    nondwell = nas("s7_1c", "s7_1c.real_estate_prof.ce.current") * ratio9
    s_it, s_bs = cat_surplus("s7"), sum(cat_surplus(c) for c in ("s10", "s11", "s12"))
    hha["A_ITSV"] = min(nondwell * s_it / (s_it + s_bs), gos["A_ITSV"])
    hha["A_BSRE"] = min(nondwell * s_bs / (s_it + s_bs), gos["A_BSRE"])
    hha["A_DWEL"] = min(hhg["real_estate_prof"] - hha["A_ITSV"] - hha["A_BSRE"], gos["A_DWEL"])
    q = {a: sum(cat_nonprop_gva(c) for c in cats) / sum(cat_gva(c) for c in cats) for a, cats in ASU_MAP.items()}
    c4a = hkeys()["c4a"]
    s_imp = c4a["imputed_rent"] / (c4a["imputed_rent"] + c4a["actual_rent"] + c4a["govt_housing"])
    dw_imp = min(s_imp * gos["A_DWEL"], hha["A_DWEL"])
    dw_act = hha["A_DWEL"] - dw_imp
    v2a: dict[tuple[str, str, str], float] = {}
    quasi: dict[str, float] = {}
    for a in s["acts"]:
        hh = hha.get(a, 0.0)
        if a == "A_DWEL":
            v2a["F_GOSC", a, "hh_dwelling_imputed"] = dw_imp
            v2a["F_GOSC", a, "hh_dwelling_actual"] = dw_act
        elif hh > 0:
            qa = q.get(a, 0.0)
            if qa > 0:
                v2a["F_GOSC", a, "hh_quasi"] = quasi[a] = qa * hh
            v2a["F_MIXD", a, "mixed_income"] = hh - qa * hh
        if gos[a] - hh != 0:
            v2a["F_GOSC", a, "corp_gov"] = gos[a] - hh
    return {"hhg": hhg, "hha": hha, "q": q, "s_imp": s_imp, "dw_imp": dw_imp, "dw_act": dw_act, "v2a": v2a, "quasi": quasi,
            "ratio9": ratio9, "nondwell": nondwell}  # fmt: skip


def _iq(factors: list[str]) -> dict[str, float]:
    return {
        q: sum(ifp(f"ifpri.t10.{f}.{q}") for f in factors) / 100 * ifp(f"ifpri.t11.total_spending_per_capita.{q}")
        for q in QS
    }


MAPPING = "k_eq_q"  # DECISIONS D2-19 (2026-10-01): group k of each area takes national quintile k's IFPRI index


def within_area(iq: dict[str, float], mapping: str = MAPPING) -> dict[str, float]:
    pop, xw = hkeys()["pop"], hkeys()["xw"]
    out = {}
    for a in AREAS:
        gs = [g for g in HH if AREA_OF[g] == a]
        ig = {g: (sum(xw[g][q] * iq[q] for q in QS) if mapping == "xwalk" else iq[QS[int(g[-1]) - 1]]) for g in gs}
        tot = sum(pop[g] * ig[g] for g in gs)
        for g in gs:
            out[g] = pop[g] * ig[g] / tot
    return out


V3_SID = "s6_1.compensation_of_employees_from_rest_of_the_world.current"
V4_SID = "s6_1.compensation_of_employees_to_the_rest_of_the_world.current"


@cache
def household_income() -> dict:
    """F1a, F2, F3a, F3b, F3c (plan s.2.5-2.7)."""
    lab, sur, hk = labour(), surplus(), hkeys()
    split = {}
    for kind, bills, row in (("reg", lab["reg"], "F_LREG"), ("cas", lab["cas"], "F_LCAS")):
        out = {a: 0.0 for a in AREAS}
        for (r, act), val in lab["v1a"].items():
            if r != row:
                continue
            g = ACT_GROUP[act]
            tot = sum(bills[g, a] for a in AREAS)
            for a in AREAS:
                out[a] += val * bills[g, a] / tot
        split[kind] = out
    net = nas("s6_1", V3_SID) - nas("s6_1", V4_SID)
    reg_t = sum(split["reg"].values())
    reg_area = {a: split["reg"][a] * (1 + net / reg_t) for a in AREAS}
    sh_reg = within_area(_iq(["labour_medium_educated", "labour_high_educated"]))
    sh_cas = within_area(_iq(["labour_low_educated"]))
    f1a = {}
    for g in HH:
        f1a[g, "F_LREG"] = reg_area[AREA_OF[g]] * sh_reg[g]
        f1a[g, "F_LCAS"] = split["cas"][AREA_OF[g]] * sh_cas[g]
    mix = {a: val for (r, a, _), val in sur["v2a"].items() if r == "F_MIXD"}
    farm_tot = sum(mix[a] for a in FARM)
    farm_area = {a: farm_tot * lab["sel"]["01-03", a] / sum(lab["sel"]["01-03", x] for x in AREAS) for a in AREAS}
    nf = {a: 0.0 for a in AREAS}
    for act, val in mix.items():
        if act in FARM:
            continue
        if act in ("A_OMIN", "A_COAL", "A_OILG"):
            k = {a: lab["sel"]["05-09", a] for a in AREAS}
        elif act == "A_CNST":
            k = {a: lab["sel"]["41-43", a] for a in AREAS}
        elif act == "A_UTIL":  # PLFS 35-39 self-employment (V-F-3 fixed; the 22:30/23:07 builds used ASUSE E)
            k = {a: lab["sel"]["35-39", a] for a in AREAS}
        else:
            k = {a: sum(cat_surplus(c, a) for c in ASU_MAP[act]) for a in AREAS}
        for a in AREAS:
            nf[a] += val * k[a] / sum(k.values())
    sh_farm = within_area(_iq(["crop_land", "capital_agriculture"]))
    sh_nonf = within_area(_iq(["capital_non_agriculture"]))
    f2 = {}
    for g in HH:
        f2[g, "farm"] = farm_area[AREA_OF[g]] * sh_farm[g]
        f2[g, "nonfarm"] = nf[AREA_OF[g]] * sh_nonf[g]
    imp_tot = sum(hk["c4a_imp"].values())
    f3a = {g: sur["dw_imp"] * hk["c4a_imp"][g] / imp_tot for g in HH}
    f3b = {g: sur["dw_act"] * hk["aidis"][g] / sum(hk["aidis"].values()) for g in HH}
    q_area = {a: 0.0 for a in AREAS}
    for act, val in sur["quasi"].items():
        k = {a: sum(cat_nonprop_gva(c, a) for c in ASU_MAP[act]) for a in AREAS}
        for a in AREAS:
            q_area[a] += val * k[a] / sum(k.values())
    f3c = {g: q_area[AREA_OF[g]] * sh_nonf[g] for g in HH}
    return {"f1a": f1a, "f2": f2, "f3a": f3a, "f3b": f3b, "f3c": f3c, "reg_area": reg_area, "cas_area": split["cas"],
            "sh_reg": sh_reg, "sh_reg_xw": within_area(_iq(["labour_medium_educated", "labour_high_educated"]), "xwalk"),
            "areas": {"lreg": reg_area, "lcas": split["cas"], "mixd_farm": farm_area, "mixd_nonfarm": nf,
                      "quasi_corporate": q_area}}  # fmt: skip


SENS_FACTORS = {"lreg": ["labour_medium_educated", "labour_high_educated"], "lcas": ["labour_low_educated"],
                "mixd_farm": ["crop_land", "capital_agriculture"], "mixd_nonfarm": ["capital_non_agriculture"],
                "quasi_corporate": ["capital_non_agriculture"]}  # fmt: skip


def sensitivity_shares(factors: list[str], variant: str) -> dict[str, float]:
    """D2-19 sensitivity mappings: 'xwalk' (households' national-quintile crosswalk) or 'hces' (k = q with IFPRI T11
    spending per capita replaced by the group's HCES MPCE: weight = T10 share in quintile k x hces_total_g)."""
    if variant == "xwalk":
        return within_area(_iq(factors), "xwalk")
    hces = hkeys()["hces"]
    out = {}
    for a in AREAS:
        gs = [g for g in HH if AREA_OF[g] == a]
        w = {g: sum(ifp(f"ifpri.t10.{f}.{QS[int(g[-1]) - 1]}") for f in factors) / 100 * hces[g] for g in gs}
        for g in gs:
            out[g] = w[g] / sum(w.values())
    return out


def gos_arith(tab: str, row: str) -> float:
    return (
        nas(tab, f"{tab}.{row}.gva.current")
        - nas(tab, f"{tab}.{row}.ce.current")
        - nas(tab, f"{tab}.{row}.net_production_taxes.current")
    )


@cache
def sectors() -> dict:
    """F4 / F4b (plan s.2.8-2.9)."""
    gg = nas("s8_15_1", "s8_15_1.total.cfc.current")
    s41 = lambda x: nas("s4_1", f"s4_1.{x}.current")  # noqa: E731
    gia = v("union_fiscal", "union_fiscal_fa_gia", "gia.cash.autonomous_bodies.total") - v(
        "union_fiscal", "union_fiscal_fa_gia", "gia.cash.autonomous_bodies.capital_assets"
    )
    cen = (s41("central_government") + min(gia, s41("autonomous_institutions"))) / s41("net_value_added")
    return {
        "E_NFPU": gos_arith("s7_1a", "total") - gos_arith("s8_15_1", "total") - gos_arith("s7_1a", "financial"),
        "E_NFPR": gos_arith("s7_1b", "total") - gos_arith("s7_1b", "financial"),
        "fc": (nas("s7_1a", "s7_1a.financial.os.current") + nas("s7_1a", "s7_1a.financial.cfc.current")
               + nas("s7_1b", "s7_1b.financial.os.current") + nas("s7_1b", "s7_1b.financial.cfc.current")),
        "gg": gg, "centre_share": cen, "G_CEN": cen * gg, "G_STA": (1 - cen) * gg, "gia_rev": gia,
    }  # fmt: skip


@cache
def expected_entries() -> dict[tuple[str, str, str, str], float]:
    exp: dict[tuple[str, str, str, str], float] = {}
    for (r, a), val in labour()["v1a"].items():
        exp[r, a, "V1a", "total"] = val
    for (r, a, comp), val in surplus()["v2a"].items():
        exp[r, a, "V2a", comp] = val
    exp["F_LREG", "R_ROW", "V3", "total"] = nas("s6_1", V3_SID)
    exp["R_ROW", "F_LREG", "V4", "total"] = nas("s6_1", V4_SID)
    hi = household_income()
    for (g, f), val in hi["f1a"].items():
        exp[g, f, "F1a", "total"] = val
    for (g, comp), val in hi["f2"].items():
        exp[g, "F_MIXD", "F2", comp] = val
    for key, ref in (("f3a", "F3a"), ("f3b", "F3b"), ("f3c", "F3c")):
        for g, val in hi[key].items():
            exp[g, "F_GOSC", ref, "total"] = val
    sec = sectors()
    exp["E_NFPU", "F_GOSC", "F4", "total"] = sec["E_NFPU"]
    exp["E_NFPR", "F_GOSC", "F4", "total"] = sec["E_NFPR"]
    exp["G_CEN", "F_GOSC", "F4b", "total"] = sec["G_CEN"]
    exp["G_STA", "F_GOSC", "F4b", "total"] = sec["G_STA"]
    return exp


@cache
def expected_constraints() -> dict[str, float]:
    s, sur, hi, sec = sut(), surplus(), household_income(), sectors()
    out = {"f1.total": nas("derived_residuals", "derived.ce_receivable_by_residents.current"),
           "f2f3.hh_gross_os_mi": nas("s7_1c", "s7_1c.total.os_mi.current") + nas("s7_1c", "s7_1c.total.cfc.current"),
           "f4.fc_gos": sec["fc"], "f4.gg_gos": sec["gg"], "f4.nfc_private": sec["E_NFPR"], "f4.nfc_public": sec["E_NFPU"],
           # added by the Wave C audit fix (BS-12, 2026-10-01; re-verified 2026-10-01): the Centre's F4b CFC held
           # near its NVA-key value, the same recomputed entry as the census
           "f4b.centre": sec["G_CEN"]}  # fmt: skip
    for g in HH:
        out[f"f3a_band.{g.lower()}"] = hi["f3a"][g]
    floors = {"communication": ["communication"], "financial": ["financial"], "hotels": ["hotels"], "manufacturing": ["manufacturing"],
              "mining": ["mining"], "public_admin": ["public_admin"], "trade_repair": ["trade_repair"], "utilities": ["utilities"],
              "real_estate_prof_other_services": ["real_estate_prof", "other_services"],
              "transport": ["railways", "road_transport", "air_transport", "water_transport", "transport_services", "storage"]}  # fmt: skip
    for k, rows in floors.items():
        out[f"v1a_floor.{k}"] = sum(nas("s7_1a", f"s7_1a.{r}.ce.current") for r in rows)
    for k, (_, acts) in NASGRP.items():
        out[f"v2a_hh.{k}"] = sur["hhg"][k]
        if k in ("mining", "manufacturing", "real_estate_prof", "other_services"):
            for a in acts:
                out[f"v2a_cap.{a.lower()}"] = s["gos"][a]
    return out


# ------------------------------------------------------------------------------------------ helpers
def _rows(sql: str) -> list[tuple]:
    return con().execute(sql).fetchall()


def _entries() -> dict[tuple[str, str, str, str], tuple]:
    f = _p(BLOCKS / "factors_entries.parquet")
    return {
        (r[0], r[1], r[2], r[3]): r[4:]
        for r in _rows(f"select row, col, ref, component, value, status, role, tol_rel, confidence, prov_id from '{f}'")
    }


def _sat(name: str) -> str:
    return _p(FSAT / f"{name}.parquet")


# ------------------------------------------------------------------------------------------ tests
def _stale_deps() -> list[str]:
    cat = json.loads((BLOCKS / "factors_block.json").read_text(encoding="utf-8"))
    return [f"{dep}_{kind}" for dep, files in cat["dependency_hashes"].items() for kind, h in files.items()
            if hashlib.sha256((BLOCKS / f"{dep}_{kind}.parquet").read_bytes()).hexdigest() != h]  # fmt: skip


def test_outputs_are_current_against_their_dependencies():
    cat = json.loads((BLOCKS / "factors_block.json").read_text(encoding="utf-8"))
    assert cat["refs_not_implemented"] == []
    assert cat["entries"] == 227 and cat["constraints"] == 63  # + f4b.centre (Wave C, BS-12)
    stale = _stale_deps()
    if stale:
        # V-F-7: households was rebuilt at 2026-09-30 23:01, after factors (22:30). The census below still
        # matches (the values factors reads did not change), but factors must be rebuilt. Other agents share
        # this working tree, so the state can flip either way: record it, do not fail on it.
        pytest.xfail(f"V-F-7: factors is stale against {stale}; rebuild factors, then its dependents")


def test_sut_activity_totals_equal_production_targets():
    """XR-15: factors splits production's ce.* / os_mi_cfc.* targets; both must come from the same SUT numbers."""
    s = sut()
    f = _p(BLOCKS / "production_constraints.parquet")
    n = 0
    for cid, cols, target in _rows(
        f"select constraint_id, cols, target from '{f}' where constraint_id like 'ce.%' or constraint_id like 'os_mi_cfc.%'"
    ):
        exp = s["ce"][cols] if cid.startswith("ce.") else s["gos"][cols]
        assert abs(exp - target) < 1e-6, cid
        n += 1
    assert n == 68
    assert abs(sum(s["ce"].values()) - nas("s7_1", "s7_1.total.ce.current")) < 1.0
    assert (
        abs(sum(s["gos"].values()) - nas("s7_1", "s7_1.total.os_mi.current") - nas("s7_1", "s7_1.total.cfc.current"))
        < 1.0
    )


def test_v1a_parameters_recomputed():
    lab = labour()
    assert abs(lab["d_days"] - 306.798245614) < 1e-6  # 125,910 / 410.40
    assert lab["fallbacks"] == [("l", "urban")]  # issues factors-7
    got = dict(_rows(f"select series_id, value from '{_sat('v1a_parameters')}'"))
    assert abs(got["d_days"] - lab["d_days"]) < 1e-6
    for g, sh in lab["share_reg"].items():
        assert abs(got[f"share_reg.{g}"] - sh) < 1e-8, g
    national = sum(val for (r, _), val in lab["v1a"].items() if r == "F_LREG") / sum(sut()["ce"].values())
    assert abs(got["national_regular_share"] - national) < 1e-8
    assert 0.70 <= national <= 0.85  # plan s.7 test 15


@pytest.mark.parametrize(
    "refs", [("V1a",), ("V2a",), ("V3", "V4"), ("F1a",), ("F2",), ("F3a", "F3b", "F3c"), ("F4", "F4b")]
)
def test_entry_census(refs):
    """Every written entry equals the independent recomputation, and nothing is missing or extra."""
    exp = {k: val for k, val in expected_entries().items() if k[2] in refs}
    got = {k: r[0] for k, r in _entries().items() if k[2] in refs}
    assert set(got) == set(exp), (sorted(set(got) - set(exp)), sorted(set(exp) - set(got)))
    bad = {k: (got[k], exp[k]) for k in exp if abs(got[k] - exp[k]) > TOL}
    assert not bad, bad


def test_entry_census_covers_all_227():
    assert len(expected_entries()) == 227 == len(_entries())


def test_constraint_target_census():
    exp = expected_constraints()
    f = _p(BLOCKS / "factors_constraints.parquet")
    got = dict(_rows(f"select constraint_id, target from '{f}'"))
    assert set(got) == set(exp)
    bad = {k: (got[k], exp[k]) for k in exp if abs(got[k] - exp[k]) > TOL}
    assert not bad, bad


def test_constraint_kinds_and_selections():
    f = _p(BLOCKS / "factors_constraints.parquet")
    rows = {
        r[0]: r[1:]
        for r in _rows(f"select constraint_id, kind, rows, cols, refs, components, tol_abs, tol_rel from '{f}'")
    }
    kinds: dict[str, int] = {}
    for kind, *_rest in rows.values():
        kinds[kind] = kinds.get(kind, 0) + 1
    assert kinds == {"equal": 20, "band": 11, "min": 10, "max": 22}  # band + f4b.centre (Wave C, BS-12)
    assert rows["f4.fc_gos"][1:4] == ("E_RBI,E_BANK,E_NBFC,E_INSP", "F_GOSC", "F4a")
    assert rows["f1.total"][3] == "F1a" and rows["f2f3.hh_gross_os_mi"][3] == "F2,F3a,F3b,F3c"
    # no re-declaration of production's V1/V2 selections (XR-15)
    assert not [c for c in rows if c.startswith(("v1.", "v2.", "factors.v1", "factors.v2"))]
    # fincorp declares the same FC selection with the same target (they merge)
    fc = _rows(
        f"select target, tol_abs from '{_p(BLOCKS / 'fincorp_constraints.parquet')}' where constraint_id='f4a.fc_gos_total'"
    )
    assert fc and abs(fc[0][0] - sectors()["fc"]) < 1e-6


def test_official_totals():
    e = _entries()
    tot = lambda ref: sum(r[0] for k, r in e.items() if k[2] == ref)  # noqa: E731
    assert abs(tot("V1a") - nas("s7_1", "s7_1.total.ce.current")) < 1.0
    assert abs(tot("F1a") - nas("derived_residuals", "derived.ce_receivable_by_residents.current")) < 1.0
    hh_gross = nas("s7_1c", "s7_1c.total.os_mi.current") + nas("s7_1c", "s7_1c.total.cfc.current")
    assert abs(tot("F2") + tot("F3a") + tot("F3b") + tot("F3c") - hh_gross) < 1.0
    assert abs(tot("V2a") - sum(sut()["gos"].values())) < 1e-4
    sec = sectors()
    assert abs(sec["E_NFPU"] + sec["E_NFPR"] + sec["fc"] + sec["gg"] + hh_gross - sum(sut()["gos"].values())) < 1.0
    assert abs(tot("F4b") - nas("s1_14", "s1_14.gg.consumption_of_fixed_capital.current")) < 0.01
    # the 7.1C household anchor by NAS group (sum of household components of the group's activities)
    for k, (_, acts) in NASGRP.items():
        hh = sum(r[0] for kk, r in e.items() if kk[2] == "V2a" and kk[1] in acts and kk[3] != "corp_gov")
        assert abs(hh - surplus()["hhg"][k]) < 0.01, k


def test_factor_accounts_close_on_the_assembled_prior():
    fs = sorted(BLOCKS.glob("*_entries.parquet"))
    union = " union all ".join(f"select row, col, value from '{_p(f)}'" for f in fs)
    for acc in FACTOR_ACCOUNTS:
        rec = _rows(f"select coalesce(sum(value),0) from ({union}) where row='{acc}'")[0][0]
        pay = _rows(f"select coalesce(sum(value),0) from ({union}) where col='{acc}'")[0][0]
        assert abs(rec - pay) < (1.0 if acc == "F_GOSC" else 1e-4), (acc, rec - pay)


def test_no_double_counting_with_other_blocks():
    fs = sorted(BLOCKS.glob("*_entries.parquet"))
    union = " union all ".join(f"select row, col, ref, component, block from '{_p(f)}'" for f in fs)
    fac = "('F_LREG','F_LCAS','F_MIXD','F_GOSC')"
    others = _rows(
        f"select block, ref, count(*) from ({union}) where (row in {fac} or col in {fac}) and block <> 'factors' group by all order by all"
    )
    assert others == [("fincorp", "F4a", 7)], others  # plan s.6 risk 4: fincorp writes only F4a
    assert (
        _rows(
            f"select count(*) from (select row, col, ref, component from ({union}) group by all having count(*) > 1)"
        )[0][0]
        == 0
    )
    # plan s.6 risks 1-6, 10
    e = _entries()
    assert not [
        k for k in e if k[0] == "F_MIXD" and k[1] in ("A_DWEL", "A_FINS", "A_INSR", "A_PADM", "A_COAL", "A_OILG")
    ]
    assert not [k for k in e if k[0] == "F_LCAS" and k[1] == "A_PADM"]
    assert not [k for k in e if k[0] in ("E_RBI", "E_BANK", "E_NBFC", "E_INSP")]
    assert not [k for k in e if k[2] in ("F1", "F3")]


def test_statuses_roles_signs():
    e = _entries()
    assert all(r[0] > 0 for r in e.values())
    for (row, col, ref, comp), (_val, status, role, tol, conf, _pid) in e.items():
        if ref in ("V3", "V4"):
            assert (status, role) == ("official", "fixed")
        elif ref == "F4":
            assert (status, role) == ("derived", "fixed")
        elif ref == "V2a" and role == "anchored":
            # single-activity NAS groups: household part (q = 0) or the SUT - NAS residual
            assert status == "derived" and tol == 0.02
            assert col in (
                "A_CROP",
                "A_LVST",
                "A_FOFI",
                "A_UTIL",
                "A_CNST",
                "A_TRAD",
                "A_HOTL",
                "A_TRNS",
                "A_COMM",
                "A_FINS",
                "A_INSR",
                "A_PADM",
            )
        else:
            assert status == "estimated" and role == "free" and conf in ("high", "medium", "low"), (row, col, ref, comp)
    assert e["F_LREG", "A_PADM", "V1a", "total"][4] == "high"
    assert all(r[4] == "low" for k, r in e.items() if k[2] in ("F1a", "F2", "F3b", "F3c"))


def test_provenance_inputs_resolve_and_statuses_match():
    ids: dict[str, str] = {}
    for f in list(CLEAN.glob("*/_provenance.parquet")) + list(BLOCKS.glob("*_provenance.parquet")):
        ids.update(dict(_rows(f"select prov_id, status from '{_p(f)}'")))
    prov = {
        r[0]: (r[1], r[2])
        for r in _rows(f"select prov_id, status, inputs from '{_p(BLOCKS / 'factors_provenance.parquet')}'")
    }
    dangling = []
    for pid, (status, inputs) in prov.items():
        for i in (inputs or "").split(","):
            if i and i not in ids:
                dangling.append((pid, i))
        if status == "official":
            assert all(ids.get(i) == "official" for i in inputs.split(",")), pid
    # a dangling input is tolerated only as the V-F-7 staleness (a DEPENDS block rebuilt after factors)
    assert all(i.startswith("sam_households:") for _, i in dangling), dangling
    assert not dangling or _stale_deps(), dangling
    for k, r in _entries().items():
        assert prov[r[5]][0] == r[1], k
    for (pid,) in _rows(f"select distinct target_prov_id from '{_p(BLOCKS / 'factors_checks.parquet')}'"):
        assert pid in ids
    assert all(ok for (ok,) in _rows(f"select ok from '{_p(BLOCKS / 'factors_checks.parquet')}'"))


def test_satellites_recomputed():
    sec, hi, sur = sectors(), household_income(), surplus()
    gos = dict(_rows(f"select sector, value from '{_sat('sector_gos')}' where item='gos'"))
    assert abs(gos["nfc_public"] - sec["E_NFPU"]) < TOL and abs(gos["nfc_private"] - sec["E_NFPR"]) < TOL
    assert abs(gos["fc_public"] + gos["fc_private"] - sec["fc"]) < TOL and abs(gos["gg"] - sec["gg"]) < TOL
    key = dict(_rows(f"select series_id, value from '{_sat('gg_centre_state_key')}'"))
    assert (
        abs(key["centre_share"] - sec["centre_share"]) < 1e-9
        and abs(key["gia.autonomous_bodies_revenue"] - sec["gia_rev"]) < 1e-6
    )
    assert 0.25 <= sec["centre_share"] <= 0.35
    va = dict(_rows(f"select series_id, value from '{_sat('va_split_by_activity')}'"))
    assert abs(va["dwelling.s_imp"] - sur["s_imp"]) < 1e-8
    assert (
        abs(va["group9.ratio_asuse"] - sur["ratio9"]) < 1e-8
        and abs(va["group9.hh_nondwelling"] - sur["nondwell"]) < TOL
    )
    for a, q in sur["q"].items():
        assert abs(va[f"q_nonprop.{a.lower()}"] - q) < 1e-8, a
    assert "q_nonprop.a_util" not in va  # V-F-3 fixed: utilities have no ASUSE category (q = 0, not keyed by E)
    gos_dwel = sut()["gos"]["A_DWEL"]
    cfc_share = nas("s7_1c", "s7_1c.real_estate_prof.cfc.current") / sut()["cfc"]["A_DWEL"]
    assert abs(va["sensitivity.hh_dwelling_share_cfc"] - cfc_share) < 1e-8
    assert abs(va["sensitivity.moved"] - (surplus()["hha"]["A_DWEL"] / gos_dwel - cfc_share) * gos_dwel) < TOL
    fik = {
        (r[0], r[1], r[2]): r[3]
        for r in _rows(f"select household_group, key, measure, value from '{_sat('factor_income_keys')}'")
    }
    for g in HH:
        assert abs(fik[g, "lreg", "level"] - hi["f1a"][g, "F_LREG"]) < TOL
        assert abs(fik[g, "quasi_corporate", "level"] - hi["f3c"][g]) < TOL
        t35 = les("plfs_enterprise_type", f"t35.worker_share.govt_public_sector.{AREA_OF[g]}.person", PLFS)
        assert abs(fik[g, "public_sector_wage_key", "level"] - hi["f1a"][g, "F_LREG"] * t35 / 100) < TOL
        assert abs(fik[g, "sensitivity_xwalk_lreg", "area_share"] - hi["sh_reg_xw"][g]) < 1e-8  # D2-19 sensitivity
    bills = {
        r[0]: r[1]
        for r in _rows(f"select series_id, value from '{_sat('v1a_labour_split')}' where item like 'wage_bill%'")
    }
    lab = labour()
    for (g, a), val in lab["reg"].items():  # V-F-5 fixed: wage bills are published in Rs crore (val is in rupees)
        assert abs(bills[f"bill_reg.{g}.{a}"] * 1e7 / val - 1) < 1e-9


def test_floors_and_caps_hold_in_the_prior():
    e, exp = _entries(), expected_constraints()
    f = _p(BLOCKS / "factors_constraints.parquet")
    for cid, kind, cols, target, tol in _rows(
        f"select constraint_id, kind, cols, target, tol_abs from '{f}' where kind in ('min','max')"
    ):
        acts = cols.split(",")
        if kind == "min":
            s = sum(r[0] for k, r in e.items() if k[0] == "F_LREG" and k[1] in acts)
            assert s >= target - tol, cid
        else:
            s = sum(r[0] for k, r in e.items() if k[2] == "V2a" and k[1] in acts and k[3] != "corp_gov")
            assert s <= target + tol, cid
    assert exp["v1a_floor.public_admin"] <= sut()["ce"]["A_PADM"]


# ------------------------------------------------------------------------------------------ findings
# V-F-2, V-F-4, V-F-5, V-F-6 were fixed on 2026-09-30; V-F-1 on 2026-10-01 by the k = q mapping (DECISIONS D2-19):
# ordinary tests since.
def test_top_urban_group_earns_more_regular_labour_income_per_person_than_u4():
    pop = hkeys()["pop"]
    f1a = household_income()["f1a"]
    assert f1a["H_U5", "F_LREG"] / pop["H_U5"] > 1.05 * f1a["H_U4", "F_LREG"] / pop["H_U4"]


def test_trade_quasi_share_uses_the_ASUSE_subcategories():
    cats = ["t1", "t2", "t3", "t4", "t5"]
    q = sum(cat_nonprop_gva(c) for c in cats) / sum(cat_gva(c) for c in cats)
    got = _entries()["F_GOSC", "A_TRAD", "V2a", "hh_quasi"][0]
    assert abs(got - q * surplus()["hhg"]["trade_repair"]) < 1.0


def test_computed_gia_difference_is_not_labelled_official():
    st = _rows(f"select status from '{_sat('gg_centre_state_key')}' where series_id='gia.autonomous_bodies_revenue'")[
        0
    ][0]
    assert st != "official"


def test_wage_bill_index_unit_matches_its_values():
    rows = _rows(
        f"select unit, max(value) from '{_sat('v1a_labour_split')}' where item like 'wage_bill%' group by unit"
    )
    assert not [u for u, mx in rows if u == "ratio" and mx > 1.0]


def test_v1a_method_text_names_the_right_r9d_payer():
    methods = [
        m
        for (m,) in _rows(f"select method from '{_p(BLOCKS / 'factors_provenance.parquet')}' where method like '%R9d%'")
    ]
    assert methods and not [m for m in methods if "by government under R9d" in m]


# ------------------------------------------------------------------------------------------ re-verification (wave C)
@pytest.mark.parametrize("variant", ["xwalk", "hces"])
def test_d2_19_sensitivity_rows_recomputed(variant):
    """D2-19: the crosswalk and HCES-rescaled variants keep every area total and the entries' F3a/F3b."""
    hi = household_income()
    fik = {
        (r[0], r[1], r[2]): r[3]
        for r in _rows(f"select household_group, key, measure, value from '{_sat('factor_income_keys')}'")
    }
    total = {g: hi["f3a"][g] + hi["f3b"][g] for g in HH}
    for key, factors in SENS_FACTORS.items():
        sh = sensitivity_shares(factors, variant)
        for g in HH:
            level = hi["areas"][key][AREA_OF[g]] * sh[g]
            total[g] += level
            assert abs(fik[g, f"sensitivity_{variant}_{key}", "area_share"] - sh[g]) < 1e-8, (key, g)
            assert abs(fik[g, f"sensitivity_{variant}_{key}", "level"] - level) < TOL, (key, g)
    for g in HH:
        assert abs(fik[g, f"sensitivity_{variant}_factor_income", "level"] - total[g]) < TOL, g
    if variant == "xwalk":  # the crosswalk reproduces V-F-1: equal regular-labour income per person in H_U4 and H_U5
        pop = hkeys()["pop"]
        u4, u5 = (fik[g, "sensitivity_xwalk_lreg", "level"] / pop[g] for g in ("H_U4", "H_U5"))
        assert abs(u5 / u4 - 1) < 1e-9


def test_casual_wage_bills_recomputed():
    bills = dict(_rows(f"select series_id, value from '{_sat('v1a_labour_split')}' where item='wage_bill_casual'"))
    for (g, a), val in labour()["cas"].items():
        assert abs(bills[f"bill_cas.{g}.{a}"] * 1e7 / val - 1) < 1e-9


def test_f4b_centre_band_follows_its_stated_rule():
    """Wave C (BS-12, factors-23): a band on the Centre's F4b entry alone, tolerance max(5%, gap to sensitivity A)."""
    f = _p(BLOCKS / "factors_constraints.parquet")
    kind, rows, cols, refs, target, tol_abs, tol_rel = _rows(
        f"select kind, rows, cols, refs, target, tol_abs, tol_rel from '{f}' where constraint_id='f4b.centre'"
    )[0]
    sec = sectors()
    s41 = lambda x: nas("s4_1", f"s4_1.{x}.current")  # noqa: E731
    share_a = s41("central_government") / (s41("net_value_added") - s41("autonomous_institutions"))
    assert (kind, rows, cols, refs, tol_abs) == ("band", "G_CEN", "F_GOSC", "F4b", 0.0)
    assert abs(target - sec["G_CEN"]) < TOL
    assert abs(tol_rel - max(0.05, abs(sec["centre_share"] - share_a) / sec["centre_share"])) < 1e-12
    key = dict(_rows(f"select series_id, value from '{_sat('gg_centre_state_key')}'"))
    assert abs(key["centre_share_sensitivity_a"] - share_a) < 1e-9
