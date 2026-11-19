"""Factors block: value added by activity split into factor types, and factor income paid to institutions.

Refs: V1a V2a V3 V4 F1 F1a F2 F3 F3a F3b F3c F4 F4b (F1 and F3 are constraint-only refs; F4a, the
financial-corporation split of GOS, belongs to fincorp: this block only declares the FC GOS total).
Plan: docs/phase2/plans/factors.md (its section 8 and DECISIONS D2-x override the plan body).

Reads (period 2023-24 unless stated; latest vintage of each series, an explicit choice):
- production (DEPENDS): its `ce.<act>` (V1) and `os_mi_cfc.<act>` (V2) constraint targets, the SUT
  2023-24 CE and OS/MI + CFC by activity. They are split here, never re-declared (CROSS_REVIEW XR-15).
- households (DEPENDS): `hh_keys` levels `pop_persons` and `aidis_fixed_assets`; the C4a entries by
  component (`imputed_rent`, `actual_rent`, `govt_housing`); `hh_national_quintile_xwalk` if published.
- NAS 2026 (vintage 2026-08-31): Statements 6.1 (CE from/to RoW), 7.1/7.1A/7.1B/7.1C (CE, OS/MI, CFC,
  GVA, net production taxes by sector and industry group), 8.15.1 (GG), 8.16 (CFC), 1.14 (sector GVA,
  CFC), 4.1 (GG NVA by government), and the derived row `derived.ce_receivable_by_residents`.
- PLFS 2023-24 (Jul 2023 - Jun 2024; vintage 2024-09-23, Q1 2023-24 earnings from the 2026-09-29 API
  pull): Table 20 status by industry group, Table 26 worker shares by NIC section, Table 51 casual wages
  by section, WPR, API indicators 6/7/8 (quarterly regular, casual and self-employment earnings),
  Table 35 enterprise type (public-sector worker share).
- ASUSE 2023-24 (Oct 2023 - Sep 2024): Tables 4, 6, 33, 37 (establishments, ownership, hired workers and
  emoluments, GVA per establishment). ASI 2023-24 (contract workers; a cross-check only).
- IFPRI 2022/23 SAM data paper (old base, national quintiles): T10 income composition and T11 spending
  per capita by national quintile (gradients only).
- Union Finance Accounts 2023-24 (grants-in-aid to autonomous bodies; F4b).

Writes: V1a F_LREG/F_LCAS <- A_* (PLFS status x earnings key); V2a F_MIXD/F_GOSC <- A_* (NAS 7.1C
household share, ASUSE keys); V3 F_LREG <- R_ROW and V4 R_ROW <- F_LREG (NAS 6.1, fixed); F1a H_* <-
F_LREG/F_LCAS; F2 H_* <- F_MIXD (components farm, nonfarm); F3a/F3b/F3c H_* <- F_GOSC; F4 E_NFPU,
E_NFPR <- F_GOSC (fixed, NAS sector arithmetic); F4b G_CEN, G_STA <- F_GOSC.
Constraints: F1 total; F2 + F3 household gross OS/MI (NAS 7.1C); FC and GG GOS totals; NFC GOS; the NAS
7.1C household controls by industry group (components filter); the regular-CE floor (kind min); the
household cap per activity (kind max); per-group F3a bands, +-10% of the prior level set by the C4a imputed-rent
shares (XR-22; fixed-level bands, the share link is checked after balancing).
Satellites: sector_gos (F4), gg_centre_state_key (F4b), factor_income_keys (F1a; incl.
public_sector_wage_key), v1a_labour_split and v1a_parameters (V1a), va_split_by_activity (V2a).

Estimated (all from published tables, no microdata: D1-2): the regular/casual split, the household
share of surplus below the NAS group, partnerships/trusts, dwellings, and every household-group split (IFPRI
gradients mapped k = q, DECISIONS D2-19; the crosswalk and an HCES-MPCE-rescaled variant are sensitivity rows).
Every assumption is stated in a provenance record and logged in docs/phase2/issues/factors.md.
Skipped: the capital-outlay sensitivity for F4b (report-only in the plan; not computed).
"""

from __future__ import annotations

import polars as pl

from pipeline.core import units
from pipeline.sam.blocks import _factors_lib as lib
from pipeline.sam.framework import BlockContext, BlockResult, SamError, Satellite, constraint, entry

BLOCK = "factors"
REFS = ["V1a", "V2a", "V3", "V4", "F1", "F1a", "F2", "F3", "F3a", "F3b", "F3c", "F4", "F4b"]
DEPENDS = ["production", "households"]

VINTAGE = "latest"  # explicit choice: the latest vintage of each (series, period); stated in method texts
PLFS_P = "2023-07/2024-06"
ASUSE_P = "2023-10/2024-09"
IFPRI_P = "2022-23"
QUARTERS = ("Q1 2023-24", "Q2 2023-24", "Q3 2023-24", "Q4 2023-24")
AREAS = lib.AREAS
AREA_GROUPS = {"rural": ["H_R1", "H_R2", "H_R3", "H_R4", "H_R5"], "urban": ["H_U1", "H_U2", "H_U3", "H_U4", "H_U5"]}
HH = AREA_GROUPS["rural"] + AREA_GROUPS["urban"]

S61, S71, S71A, S71B, S71C = (f"mospi_nas_2026_{s}" for s in ("s6_1", "s7_1", "s7_1a", "s7_1b", "s7_1c"))
S8151, S816, S114, S41 = (f"mospi_nas_2026_{s}" for s in ("s8_15_1", "s8_16", "s1_14", "s4_1"))
DERIVED = "mospi_nas_2026_derived_residuals"
T20, T26 = "labour_enterprise_surveys_plfs_industry_status", "labour_enterprise_surveys_plfs_industry_dist"
T51, API = "labour_enterprise_surveys_plfs_earnings", "labour_enterprise_surveys_plfs_earnings_api"
LFS, T35 = "labour_enterprise_surveys_plfs_lfs_indicators", "labour_enterprise_surveys_plfs_enterprise_type"
ASUSE, ASI = "labour_enterprise_surveys_asuse_2324_activity", "labour_enterprise_surveys_asi_2324_industry"
IFPRI = "io_tables_ifpri_2223_datapaper"
GIA, BOP = "union_fiscal_fa_gia", "external_sector_bop_bpm6_annual"

MANUF = ["A_FOOD", "A_BVTB", "A_TXAP", "A_WOOD", "A_GJOM", "A_RPET", "A_CHEM", "A_PHRM", "A_NMMN", "A_MTLS",
         "A_MACH", "A_ELEQ", "A_TREQ"]  # fmt: skip
FARM = ["A_CROP", "A_LVST", "A_FOFI"]

# PLFS Table 20 industry groups (NIC 2008 divisions) and the Table 26/51 sections they contain
PLFS_GROUPS = {
    "01-03": ["a"], "05-09": ["b"], "10-33": ["c"], "35-39": ["d", "e"], "41-43": ["f"], "45-47": ["g"],
    "49-53": ["h"], "55-56": ["i"], "58-99": ["j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u"],
}  # fmt: skip
ACT_PLFS = {
    **{a: "01-03" for a in FARM}, **{a: "05-09" for a in ("A_COAL", "A_OILG", "A_OMIN")},
    **{a: "10-33" for a in MANUF}, "A_UTIL": "35-39", "A_CNST": "41-43", "A_TRAD": "45-47", "A_TRNS": "49-53",
    "A_HOTL": "55-56", **{a: "58-99" for a in ("A_COMM", "A_FINS", "A_INSR", "A_BSRE", "A_ITSV", "A_EDUC",
                                              "A_HLTH", "A_OSRV", "A_PADM", "A_DWEL")},
}  # fmt: skip
V1A_LOW = {"01-03", "05-09", "41-43", "49-53", "55-56"}  # confidence low (plan s.2); others medium; A_PADM high

# regular-CE floor: NAS 7.1A public-sector CE by group (agriculture and construction excluded, plan s.2.1
# step 6); groups 9 and 11 are compared together (the SUT keeps R&D in A_EDUC, NAS in group 9)
FLOOR_GROUPS = {
    "mining": (["A_COAL", "A_OILG", "A_OMIN"], ["mining"]),
    "manufacturing": (MANUF, ["manufacturing"]),
    "utilities": (["A_UTIL"], ["utilities"]),
    "trade_repair": (["A_TRAD"], ["trade_repair"]),
    "hotels": (["A_HOTL"], ["hotels"]),
    "transport": (["A_TRNS"], ["railways", "road_transport", "air_transport", "water_transport",
                               "transport_services", "storage"]),
    "communication": (["A_COMM"], ["communication"]),
    "financial": (["A_FINS", "A_INSR"], ["financial"]),
    "real_estate_prof_other_services": (["A_BSRE", "A_ITSV", "A_EDUC", "A_HLTH", "A_OSRV"],
                                        ["real_estate_prof", "other_services"]),
    "public_admin": (["A_PADM"], ["public_admin"]),
}  # fmt: skip

# NAS 7.1C household-sector industry groups -> SAM activities (7.1C leaf rows; it has no air-transport or
# public-administration row)
HH_GROUPS = {
    "crops": (["A_CROP"], ["crops"]),
    "livestock": (["A_LVST"], ["livestock"]),
    "forestry_fishing": (["A_FOFI"], ["forestry", "fishing"]),
    "mining": (["A_COAL", "A_OILG", "A_OMIN"], ["mining"]),
    "manufacturing": (MANUF, ["manufacturing"]),
    "utilities": (["A_UTIL"], ["utilities"]),
    "construction": (["A_CNST"], ["construction"]),
    "trade_repair": (["A_TRAD"], ["trade_repair"]),
    "hotels": (["A_HOTL"], ["hotels"]),
    "transport": (["A_TRNS"], ["railways", "road_transport", "water_transport", "transport_services", "storage"]),
    "communication": (["A_COMM"], ["communication"]),
    "financial": (["A_FINS", "A_INSR"], ["financial"]),
    "real_estate_prof": (["A_DWEL", "A_BSRE", "A_ITSV"], ["real_estate_prof"]),
    "other_services": (["A_EDUC", "A_HLTH", "A_OSRV"], ["other_services"]),
}  # fmt: skip
SINGLE = ["crops", "livestock", "forestry_fishing", "utilities", "construction", "trade_repair", "hotels",
          "transport", "communication"]  # fmt: skip

# ASUSE 2023-24 activity categories -> SAM activities (plan s.2.2 step 4; services by NIC). Every activity uses
# ASUSE's sub-categories, trade too (T1-T5, not the aggregate T: verification V-F-2). Utilities have no usable
# ASUSE category (E is only non-captive electricity; NIC 36-39 sits inside S15 with personal services), so
# A_UTIL is left out like farming, mining and construction: q = 0 and a PLFS rural/urban key (V-F-3).
ASUSE_MAP = {
    "A_FOOD": ["m2"], "A_BVTB": ["m3", "m4"], "A_TXAP": ["m1", "m5", "m6", "m7"], "A_WOOD": ["m8", "m9", "m10", "m23"],
    "A_GJOM": ["m24"], "A_RPET": ["m11"], "A_CHEM": ["m12", "m14"], "A_PHRM": ["m13"], "A_NMMN": ["m15"],
    "A_MTLS": ["m16"], "A_MACH": ["m17", "m20", "m25"], "A_ELEQ": ["m18", "m19"], "A_TREQ": ["m21", "m22"],
    "A_TRAD": ["t1", "t2", "t3", "t4", "t5"], "A_HOTL": ["s1", "s2"], "A_TRNS": ["s3", "s4", "s5", "s6"],
    "A_COMM": ["s7"], "A_ITSV": ["s7"], "A_BSRE": ["s10", "s11", "s12"], "A_EDUC": ["s13"], "A_HLTH": ["s14"],
    "A_OSRV": ["s15"],
}  # fmt: skip
# non-farm mixed income whose rural/urban key is PLFS self-employment earnings of the activity's group (no ASUSE
# category describes the household part: plan s.2.6; utilities added by V-F-3)
PLFS_RU_KEY = ("A_OMIN", "A_CNST", "A_UTIL")
NONPROP = ["partnership_diff_hh", "society_trust", "cooperative", "others"]  # carved out of mixed income (F3c)
GRP9_NONDWELL = ["s7", "s10", "s11", "s12"]  # ASUSE categories of household group-9 enterprises (not dwellings)
# How IFPRI's national-quintile gradients reach the 10 SAM groups (F1a, F2, F3c): "k_eq_q" = the k-th group of each
# area takes the k-th national quintile (DECISIONS D2-19, which replaces CROSS_REVIEW XR-10's crosswalk here);
# "crosswalk" = households' hh_national_quintile_xwalk (it puts H_U4 and H_U5 both wholly in national q5: issues
# factors-3/-19). The mapping not used and an HCES-MPCE-rescaled k = q variant are published as sensitivity rows in
# `factor_income_keys` (report only).
IFPRI_MAPPING = "k_eq_q"
MIN_ENTRY = 1.0  # Rs crore: smaller pieces are folded into their complement (plan s.6: keep entries >= 1 or omit)
CHECK_TOL = 1.0


# =============================================================================================
# build
# =============================================================================================


def build(ctx: BlockContext) -> BlockResult:
    acts = ctx.accounts.in_group("ACT")
    prod = _production_targets(ctx, acts)
    hh = _households(ctx)
    ctx.log(
        f"production V1/V2 targets read; households keys: persons, fixed assets, C4a {sorted(hh['c4a'])}; "
        f"IFPRI mapping {IFPRI_MAPPING!r}; national-quintile crosswalk "
        f"{'published' if hh['xwalk_all'] else 'NOT published'}; HCES MPCE key "
        f"{'published' if hh['hces'] else 'NOT published'}"
    )

    entries: list[dict] = []
    cons: list[dict] = []
    sats: dict[str, Satellite] = {}

    lab = _v1a(ctx, prod, hh, entries, cons, sats)
    va = _v2a(ctx, prod, hh, entries, cons, sats)
    row = _v3_v4(ctx, entries)
    sec = _f4(ctx, prod, entries, cons, sats)
    _f4b(ctx, sec, entries, cons, sats)
    _household_income(ctx, prod, hh, lab, va, row, entries, cons, sats)
    return BlockResult(entries=entries, constraints=cons, satellites=sats)


# =============================================================================================
# readers
# =============================================================================================


def _get(ctx: BlockContext, ds: str, ids: list[str], *, period: str | None = None, unit: str | None = "INR_crore",
         price_basis: str | None = "current") -> tuple[dict[str, float], list[str]]:  # fmt: skip
    """Several series of one dataset for one period: {series_id: value} and the clean prov_ids read."""
    want = sorted(set(ids))
    df = ctx.rows(ds, series_id=want, period=period or ctx.year, vintage=VINTAGE, unit=unit, price_basis=price_basis)
    got = dict(zip(df["series_id"].to_list(), df["value"].to_list(), strict=True))
    if len(got) != df.height or set(got) != set(want):
        raise SamError(f"{ds}: expected one row each for {len(want)} series, got {df.height} (missing "
                       f"{sorted(set(want) - set(got))[:5]})")  # fmt: skip
    return {k: float(v) for k, v in got.items()}, sorted(set(df["prov_id"].to_list()))


def _has(ctx: BlockContext, ds: str, sid: str, period: str) -> bool:
    f = ctx.frame(ds)
    return f.filter((pl.col("series_id") == sid) & (pl.col("period") == period)).height > 0


def _fy_mean(ctx: BlockContext, sid: str) -> tuple[float, list[str]]:
    """Mean of the four 2023-24 quarters of a PLFS API earnings series (latest vintage per quarter)."""
    df = ctx.rows(API, series_id=sid, period=None, vintage=VINTAGE, unit="INR", price_basis="current")
    df = df.filter(pl.col("period").is_in(list(QUARTERS)))
    if sorted(df["period"].to_list()) != sorted(QUARTERS):
        raise SamError(f"{API}/{sid}: need exactly the quarters {QUARTERS}, got {sorted(df['period'].to_list())}")
    return float(df["value"].mean()), sorted(set(df["prov_id"].to_list()))


def _src(ctx: BlockContext, pid: str) -> str:
    rec = ctx.lookup_prov(pid)
    if rec is None or not rec.get("source_id"):
        raise SamError(f"prov_id {pid} has no source_id")
    return str(rec["source_id"])


def _production_targets(ctx: BlockContext, acts: list[str]) -> dict:
    c = ctx.block_constraints("production")
    out: dict = {"ce": {}, "gos": {}, "ce_tol": {}, "gos_tol": {}}
    for stem, key in (("ce", "ce"), ("os_mi_cfc", "gos")):
        sel = c.filter(pl.col("constraint_id").str.starts_with(stem + "."))
        pids = sorted(set(sel["prov_id"].to_list()))
        if len(pids) != 1:
            raise SamError(f"production {stem}.* constraints: expected one provenance record, got {pids}")
        out[f"{key}_pid"] = pids[0]
        for r in sel.iter_rows(named=True):
            a = r["cols"]
            if a not in acts:
                raise SamError(f"production constraint {r['constraint_id']}: unexpected cols {a!r}")
            out[key][a] = float(r["target"])
            out[f"{key}_tol"][a] = float(r["tol_abs"])
        missing = sorted(set(acts) - set(out[key]))
        if missing:
            raise SamError(f"production has no {stem} target for {missing}")
    return out


def _hh_key(ctx: BlockContext, key: str) -> tuple[dict[str, float], list[str]]:
    """Levels of one households `hh_keys` key by SAM group (consumers normalise levels themselves)."""
    df = ctx.satellite("households", "hh_keys")
    sub = (
        df.filter(pl.col("key") == key)
        if "key" in df.columns
        else df.filter(pl.col("series_id").str.starts_with(key + "."))
    )
    if "measure" in sub.columns:
        sub = sub.filter(pl.col("measure") == "level")
    else:
        sub = sub.filter(pl.col("series_id").str.contains(".level.", literal=True))
    if "household_group" not in sub.columns:
        raise SamError("households hh_keys has no household_group column")
    vals = {str(g).upper(): float(v) for g, v in zip(sub["household_group"].to_list(), sub["value"].to_list(),
                                                     strict=True)}  # fmt: skip
    if sorted(vals) != sorted(HH) or sub.height != len(HH):
        raise SamError(f"households hh_keys {key!r} (level): need one row per group {HH}, got {sorted(vals)}")
    if any(v < 0 for v in vals.values()) or sum(vals.values()) <= 0:
        raise SamError(f"households hh_keys {key!r}: negative or all-zero levels")
    return vals, sorted(set(sub["prov_id"].to_list()))


def _xwalk(ctx: BlockContext) -> tuple[dict[str, dict[str, float]] | None, list[str]]:
    """households' `hh_national_quintile_xwalk`: share of each SAM group's persons by national MPCE
    quintile. None (with a warning) if households does not publish it: then, under IFPRI_MAPPING = "crosswalk",
    the k = q assumption holds; under "k_eq_q" (D2-19) only the crosswalk sensitivity rows are missing."""
    try:
        df = ctx.satellite("households", "hh_national_quintile_xwalk")
    except SamError as e:
        if "has no satellite" not in str(e):
            raise
        if IFPRI_MAPPING == "crosswalk":
            ctx.warn("households publishes no hh_national_quintile_xwalk: IFPRI national-quintile gradients are "
                     "mapped with the k = q assumption (plan s.2.5 step 3; issues factors-5)")  # fmt: skip
        else:
            ctx.warn("households publishes no hh_national_quintile_xwalk: the crosswalk sensitivity rows of "
                     "factor_income_keys are not published (D2-19; issues factors-3)")  # fmt: skip
        return None, []
    if "household_group" not in df.columns:
        raise SamError(f"hh_national_quintile_xwalk: no household_group column in {df.columns}")
    df = df.filter(pl.col("household_group").is_not_null())  # memo rows (the national cut-offs) have no group
    if "measure" in df.columns:  # households publishes persons and shares: use the person shares
        df = df.filter(pl.col("measure") == "share")
    qcol = None
    for c in df.columns:
        if c in ("series_id", "household_group", "unit", "status", "prov_id") or df.schema[c] != pl.String:
            continue
        vals = {str(v).lower() for v in df[c].drop_nulls().to_list()}
        if vals and vals <= set(lib.QUINTILES):
            qcol = c
            break
    if qcol is None:
        raise SamError(f"hh_national_quintile_xwalk: cannot find the national-quintile column in {df.columns}")
    out: dict[str, dict[str, float]] = {g: {} for g in HH}
    for g, q, v in zip(df["household_group"].to_list(), df[qcol].to_list(), df["value"].to_list(), strict=True):
        g = str(g).upper()
        if g not in out:
            raise SamError(f"hh_national_quintile_xwalk: unknown group {g!r}")
        out[g][str(q).lower()] = out[g].get(str(q).lower(), 0.0) + float(v)
    bad = [g for g, x in out.items() if abs(sum(x.values()) - 1.0) > 1e-6]
    if bad:
        raise SamError(f"hh_national_quintile_xwalk: person shares do not sum to 1 for {bad}")
    return out, sorted(set(df["prov_id"].to_list()))


def _households(ctx: BlockContext) -> dict:
    pop, pop_pids = _hh_key(ctx, "pop_persons")
    fa, fa_pids = _hh_key(ctx, "aidis_fixed_assets")
    ent = ctx.block_entries("households").filter(pl.col("ref") == "C4a")
    c4a: dict[str, float] = {}
    imputed: dict[str, float] = {g: 0.0 for g in HH}
    for r in ent.iter_rows(named=True):
        c4a[r["component"]] = c4a.get(r["component"], 0.0) + r["value"]
        if r["component"] == "imputed_rent":
            imputed[r["col"]] += r["value"]
    need = {"imputed_rent", "actual_rent"}
    if not need <= set(c4a):
        raise SamError(f"households C4a entries lack components {sorted(need - set(c4a))} (have {sorted(c4a)})")
    if IFPRI_MAPPING not in ("crosswalk", "k_eq_q"):
        raise SamError(f"IFPRI_MAPPING must be 'crosswalk' or 'k_eq_q', got {IFPRI_MAPPING!r}")
    # the crosswalk is read under either mapping: it keys the entries ("crosswalk") or a sensitivity ("k_eq_q")
    xw_all, xw_all_pids = _xwalk(ctx)
    if IFPRI_MAPPING == "k_eq_q":
        ctx.log(
            "IFPRI_MAPPING = 'k_eq_q' (DECISIONS D2-19): group k of each area takes national quintile k's IFPRI "
            "index; households' national-quintile crosswalk keys only the sensitivity rows (issues factors-3)"
        )
        xw, xw_pids = None, []
    else:
        xw, xw_pids = xw_all, xw_all_pids
    # HCES MPCE by group (households' hces_total levels / pop_persons): the HCES-rescaled sensitivity (D2-19)
    hces, hces_pids = None, []
    hk = ctx.satellite("households", "hh_keys")
    has_hces = (
        (hk["key"] == "hces_total").any()
        if "key" in hk.columns
        else hk["series_id"].str.starts_with("hces_total.").any()
    )
    if has_hces:
        hces, hces_pids = _hh_key(ctx, "hces_total")
    else:
        ctx.warn("households hh_keys has no 'hces_total' key: the HCES-MPCE-rescaled sensitivity rows of "
                 "factor_income_keys are not published (D2-19; issues factors-19)")  # fmt: skip
    return {
        "pop": pop, "pop_pids": pop_pids, "fixed_assets": fa, "fa_pids": fa_pids, "c4a": c4a,
        "c4a_imputed": imputed, "c4a_pids": sorted(set(ent["prov_id"].to_list())), "xwalk": xw, "xw_pids": xw_pids,
        "xwalk_all": xw_all, "xw_all_pids": xw_all_pids, "hces": hces, "hces_pids": hces_pids,
        "persons_area": {s: sum(pop[g] for g in AREA_GROUPS[s]) for s in AREAS},
    }  # fmt: skip


# =============================================================================================
# V1a: regular vs casual CE by activity
# =============================================================================================


def _v1a(ctx: BlockContext, prod: dict, hh: dict, entries: list, cons: list, sats: dict) -> dict:
    groups = {g: [s for s in secs if _has(ctx, T26, f"t26.worker_share.{s}.rural.person", PLFS_P)]
              for g, secs in PLFS_GROUPS.items()}  # fmt: skip
    dropped = sorted(set(sum(PLFS_GROUPS.values(), [])) - set(sum(groups.values(), [])))
    if dropped:
        ctx.log(f"PLFS Table 26 has no worker share for section(s) {dropped}: left out (no workers)")
    secs = sorted(set(sum(groups.values(), [])))
    t26, p26 = _get(ctx, T26, [f"t26.worker_share.{s}.{a}.person" for s in secs for a in AREAS], period=PLFS_P,
                    unit="percent", price_basis=None)  # fmt: skip
    share = {(s, a): t26[f"t26.worker_share.{s}.{a}.person"] for s in secs for a in AREAS}
    st_ids = [f"t20.worker_share.{k}.{g}.{a}.person" for k in ("regular_wage", "casual_labour", "self_employed")
              for g in PLFS_GROUPS for a in AREAS]  # fmt: skip
    t20, p20 = _get(ctx, T20, st_ids, period=PLFS_P, unit="percent", price_basis=None)
    reg_sh = {(g, a): t20[f"t20.worker_share.regular_wage.{g}.{a}.person"] for g in PLFS_GROUPS for a in AREAS}
    cas_sh = {(g, a): t20[f"t20.worker_share.casual_labour.{g}.{a}.person"] for g in PLFS_GROUPS for a in AREAS}
    se_sh = {(g, a): t20[f"t20.worker_share.self_employed.{g}.{a}.person"] for g in PLFS_GROUPS for a in AREAS}
    wpr, pw = _get(ctx, LFS, [f"lfs.wpr.ps_ss.all.{a}.person" for a in AREAS], period=PLFS_P, unit="percent",
                   price_basis=None)  # fmt: skip
    wpr = {a: wpr[f"lfs.wpr.ps_ss.all.{a}.person"] for a in AREAS}

    # casual wage by section (Table 51); a missing area cell falls back to the section's all-area wage
    wage: dict[tuple[str, str], float] = {}
    p51: set[str] = set()
    fallbacks = []
    for s in secs:
        for a in AREAS:
            sid = f"t51.casual_wage_day.{s}.{a}.person.current"
            if not _has(ctx, T51, sid, PLFS_P):
                alt = f"t51.casual_wage_day.{s}.total.person.current"
                if not _has(ctx, T51, alt, PLFS_P):
                    fallbacks.append(f"{s}.{a}: no wage at all (section left out of the casual-wage weights)")
                    continue
                fallbacks.append(f"{s}.{a} -> {s}.total")
                sid = alt
            v, p = _get(ctx, T51, [sid], period=PLFS_P, unit="INR", price_basis="current")
            wage[(s, a)] = v[sid]
            p51.update(p)
    if fallbacks:
        ctx.log(f"PLFS Table 51 casual-wage fallbacks: {fallbacks}")

    reg_month = {}
    p_api: set[str] = set()
    for a in AREAS:
        v, p = _fy_mean(ctx, f"api_i6.regular_wage_earnings_month.{a}.person.current")
        reg_month[a] = v
        p_api.update(p)
    cas_day_all, p7 = _fy_mean(ctx, "api_i7.casual_wage_earnings_day.total.person.current")
    emol, p33 = _get(ctx, ASUSE, ["t33.emol_per_hired_worker.informal.asuse_all.total.current"], period=ASUSE_P,
                     unit="INR", price_basis="current")  # fmt: skip
    emol_v = emol["t33.emol_per_hired_worker.informal.asuse_all.total.current"]
    days = emol_v / cas_day_all
    p_api.update(p7)
    d_pid = ctx.prov(
        ref="V1a", status="estimated", inputs=[*p33, *p7], source_id=_src(ctx, p33[0]),
        method=f"Gap map V1a parameter D (casual days worked per year) = ASUSE 2023-24 Table 33 annual emoluments "
        f"per informal hired worker, all activities ({emol_v:,.0f} Rs) / the mean of PLFS API indicator 7 "
        f"casual daily wage, all areas, over Q1-Q4 2023-24 ({cas_day_all:,.2f} Rs) = {days:.2f} days. "
        "Assumption: the annual pay of informal hired workers expressed in casual-wage days is the casual "
        "labourer's working year (sensitivity: 250 days).",
    )  # fmt: skip

    workers = lib.workers_by_group(wpr, hh["persons_area"], share, groups)
    cas_wage = lib.casual_wage_by_group(share, wage, groups)
    reg_year = {a: 12.0 * reg_month[a] for a in AREAS}
    reg_bill, cas_bill = lib.wage_bills(workers, reg_sh, cas_sh, reg_year, cas_wage, days)
    share_reg = lib.regular_share(reg_bill, cas_bill)
    rb250, cb250 = lib.wage_bills(workers, reg_sh, cas_sh, reg_year, cas_wage, 250.0)
    share_250 = lib.regular_share(rb250, cb250)

    ce = prod["ce"]
    reg: dict[str, float] = {}
    for a, v in ce.items():
        if v == 0:
            continue
        reg[a] = v if a == "A_PADM" else share_reg[ACT_PLFS[a]] * v

    # regular-CE floor: NAS 7.1A public-sector CE by group
    fl_ids = sorted({f"s7_1a.{n}.ce.current" for _, (_, ns) in FLOOR_GROUPS.items() for n in ns})
    fl, p71a = _get(ctx, S71A, fl_ids)
    floor_pid = ctx.prov(
        ref="V1a", status="derived", inputs=p71a,
        method="Gap map V1a floor (plan s.2.1 step 6): regular CE of a NAS industry group >= that group's "
        "public-sector CE, NAS 2026 Statement 7.1A 'Compensation of employees' (sum of the 7.1A rows listed "
        "in the constraint description). Not applied to agriculture and construction, where government "
        "departments may employ muster-roll (casual) labour; NAS groups 9 and 11 are compared together "
        "because the SUT keeps R&D in A_EDUC while NAS files it under group 9.",
    )  # fmt: skip
    floors = {}
    for name, (acts, rows) in FLOOR_GROUPS.items():
        target = sum(fl[f"s7_1a.{n}.ce.current"] for n in rows)
        floors[name] = target
        grp = {a: reg[a] for a in acts if a in reg}
        new, added = lib.apply_floor(grp, {a: ce[a] for a in grp}, target)
        if added > 0:
            ctx.warn(f"V1a floor binds for {name}: regular CE raised by {added:,.2f} to the 7.1A public-sector CE "
                     f"{target:,.2f}")  # fmt: skip
            reg.update(new)
        cons.append(constraint(
            f"v1a_floor.{name}", "V1a", ["F_LREG"], acts, target, prov_id=floor_pid, kind="min", refs=["V1a"],
            description=f"Regular CE of {name} >= NAS 7.1A public-sector CE ({' + '.join(rows)})",
        ))  # fmt: skip

    split_inputs = sorted({prod["ce_pid"], *p20, *p26, *pw, *p51, *p_api, *p33, *hh["pop_pids"], d_pid})
    est_pid = ctx.prov(
        ref="V1a", status="estimated", inputs=split_inputs, source_id=_src(ctx, p20[0]),
        method="Gap map V1a, fallback without PLFS unit data (D1-2). CE by activity = production's V1 targets "
        "(SUT 2023-24). For each PLFS Table 20 industry group g (01-03, 05-09, 10-33, 35-39, 41-43, 45-47, "
        "49-53, 55-56, 58-99) and area s: workers = WPR_s (PLFS ps+ss, all ages) x persons_s (households' "
        "pop_persons, summed by area) x sum of Table 26 worker shares of the NIC sections in g; regular bill = "
        "workers x Table 20 regular-wage share x 12 x mean of API indicator 6 regular monthly earnings of area s "
        "over Q1-Q4 2023-24; casual bill = workers x Table 20 casual share x Table 51 casual daily wage of g "
        "(section wages weighted by Table 26 shares; a missing area cell uses the section's all-area wage) x D "
        f"days ({days:.2f}, record {d_pid}). share_reg_g = sum_s regular / sum_s (regular + casual); F_LREG = "
        "share_reg_g x CE of each activity in g (every activity of a group gets the group share: the SUT's CE "
        "is pro rata within MoSPI groups, so nothing finer exists); F_LCAS = CE - F_LREG. Floor: regular CE by "
        "NAS group >= 7.1A public-sector CE (none binds unless logged). Assumptions: usual-status worker shares "
        "and CWS earnings combine; wage bills are used only as shares, never as levels. CE includes employers' "
        "actual and imputed social contributions (e.g. departmental enterprises' pension liabilities, paid to "
        "households by the public non-financial corporations E_NFPU under R9d, D2-9; government's imputed OPS "
        "contributions, paid back to households by government under R9b).",
    )  # fmt: skip
    padm_pid = ctx.prov(
        ref="V1a", status="estimated", inputs=[prod["ce_pid"]],
        notes="assumption: public administration employs regular staff only",
        method="Gap map V1a for A_PADM: all SUT CE of public administration and defence is regular wages "
        "(F_LREG); assumption: NAS GG CE includes the imputed OPS pension contributions, which accrue to "
        "regular employees only, and muster-roll labour in government is booked in construction/agriculture.",
    )  # fmt: skip
    for a in sorted(reg):
        g = ACT_PLFS[a]
        r, c = reg[a], ce[a] - reg[a]
        if a == "A_PADM":
            entries.append(entry("F_LREG", a, "V1a", r, prov_id=padm_pid, status="estimated", role="free",
                                 confidence="high"))  # fmt: skip
            continue
        conf = "low" if g in V1A_LOW else "medium"
        if r >= MIN_ENTRY:
            entries.append(entry("F_LREG", a, "V1a", r, prov_id=est_pid, status="estimated", role="free",
                                 confidence=conf))  # fmt: skip
        if c >= MIN_ENTRY:
            entries.append(entry("F_LCAS", a, "V1a", c, prov_id=est_pid, status="estimated", role="free",
                                 confidence=conf))  # fmt: skip
        if r < MIN_ENTRY or c < MIN_ENTRY:
            raise SamError(f"V1a {a}: regular {r:,.4f} / casual {c:,.4f} below Rs {MIN_ENTRY} crore")

    # ASI cross-check (report only): contract workers in the factory sector
    asi, pasi = _get(ctx, ASI, ["v1t3.workers.all", "v1t3.workers_contract.all"], unit="count", price_basis=None)
    contract = asi["v1t3.workers_contract.all"] / asi["v1t3.workers.all"]
    ctx.log(f"V1a manufacturing regular share {share_reg['10-33']:.3f}; ASI 2023-24 contract workers are "
            f"{contract:.3f} of factory workers (often 'regular' in PLFS; report only)")  # fmt: skip
    nat = sum(reg.values()) / sum(ce.values())
    if not 0.70 <= nat <= 0.85:
        ctx.warn(f"V1a national regular share of CE {nat:.3f} outside the plan's band [0.70, 0.85]")

    # satellites: parameters and the per-group wage-bill decomposition (F1a reads it)
    par_rows = [("d_days", "parameter", "all", days, "count", d_pid),
                ("d_days_sensitivity", "parameter", "all", 250.0, "count", d_pid),
                ("national_regular_share", "result", "all", nat, "ratio", est_pid)]  # fmt: skip
    for g in PLFS_GROUPS:
        par_rows.append((f"share_reg.{g}", "share_reg", g, share_reg[g], "ratio", est_pid))
        par_rows.append((f"share_reg_d250.{g}", "share_reg_d250", g, share_250[g], "ratio", est_pid))
    for name, t in floors.items():
        par_rows.append((f"floor.{name}", "floor_public_ce", name, t, "INR_crore", floor_pid))
    asi_pid = ctx.prov(ref="V1a", status="derived", inputs=pasi,
                       method="Gap map V1a cross-check (report only): ASI 2023-24 v1t3 contract workers / all "
                       "workers, factory sector, all India.")  # fmt: skip
    par_rows.append(("asi_contract_share", "cross_check", "10-33", contract, "ratio", asi_pid))
    sats["v1a_parameters"] = _sat("V1a", par_rows, ctx, "V1a parameters: D (days), share_reg by PLFS group (and "
                                  "at D = 250), public-sector CE floors, ASI contract-worker share",
                                  dims=("item", "plfs_group"), decimals=9)  # fmt: skip
    split_rows = []
    for a in sorted(reg):
        split_rows.append(
            (f"ce_reg.{a.lower()}", "ce_reg", a, reg[a], "INR_crore", est_pid if a != "A_PADM" else padm_pid)
        )
        split_rows.append((f"ce_cas.{a.lower()}", "ce_cas", a, ce[a] - reg[a], "INR_crore",
                           est_pid if a != "A_PADM" else padm_pid))  # fmt: skip
    # the wage bills are rupee amounts (workers x annual earnings): published in Rs crore (V-F-5)
    for (g, s), v in sorted(reg_bill.items()):
        split_rows.append((f"bill_reg.{g}.{s}", "wage_bill_regular", f"{g}.{s}", units.to_inr_crore(v, "INR"),
                           "INR_crore", est_pid))  # fmt: skip
    for (g, s), v in sorted(cas_bill.items()):
        split_rows.append((f"bill_cas.{g}.{s}", "wage_bill_casual", f"{g}.{s}", units.to_inr_crore(v, "INR"),
                           "INR_crore", est_pid))  # fmt: skip
    sats["v1a_labour_split"] = _sat("V1a", split_rows, ctx, "V1a regular/casual CE by activity and the PLFS wage-"
                                    "bill decomposition by group and area (survey-scale annual wage bills, workers x "
                                    "earnings, Rs crore; used only as shares, never as levels)",
                                    dims=("item", "subject"), decimals=9)  # fmt: skip
    return {"reg": reg, "ce": ce, "reg_bill": reg_bill, "cas_bill": cas_bill, "share_reg": share_reg,
            "workers": workers, "se_sh": se_sh, "wpr": wpr, "share": share, "groups": groups, "days": days,
            "pids": sorted({*p20, *p26, *pw, *p_api}), "est_pid": est_pid}  # fmt: skip


# =============================================================================================
# V2a: mixed income vs operating surplus by activity
# =============================================================================================


def _asuse(ctx: BlockContext) -> tuple[dict, list[str]]:
    """ASUSE per category and area: GVA (Table 4 x Table 37, OAE + HWE), surplus (GVA - Table 33 hired
    workers x emoluments), non-proprietary GVA (Table 6 ownership shares x GVA by establishment type).
    Rupees (only ratios are used)."""
    cats = sorted({c for cs in ASUSE_MAP.values() for c in cs})
    ids = []
    for c in cats:
        for s in (*AREAS, "total"):
            ids += [f"t33.hired_workers.all.asuse_{c}.{s}", f"t33.emol_per_hired_worker.all.asuse_{c}.{s}.current"]
            for t in ("oae", "hwe"):
                ids += [f"t4.establishments.asuse_{c}.{s}.{t}", f"t37.gva_per_estt.asuse_{c}.{s}.{t}.current"]
                ids += [f"t6.estt_share.{o}.asuse_{c}.{s}.{t}" for o in NONPROP]
    df = ctx.rows(ASUSE, series_id=sorted(set(ids)), period=ASUSE_P, vintage=VINTAGE, unit=None, price_basis=None)
    v = dict(zip(df["series_id"].to_list(), df["value"].to_list(), strict=True))
    miss = sorted(set(ids) - set(v))
    if miss:
        raise SamError(f"ASUSE series missing: {miss[:5]}")
    out = {}
    for c in cats:
        for s in (*AREAS, "total"):
            gva = {t: v[f"t4.establishments.asuse_{c}.{s}.{t}"] * v[f"t37.gva_per_estt.asuse_{c}.{s}.{t}.current"]
                   for t in ("oae", "hwe")}  # fmt: skip
            emol = v[f"t33.hired_workers.all.asuse_{c}.{s}"] * v[f"t33.emol_per_hired_worker.all.asuse_{c}.{s}.current"]
            nonprop = sum(sum(v[f"t6.estt_share.{o}.asuse_{c}.{s}.{t}"] for o in NONPROP) / 100.0 * gva[t]
                          for t in ("oae", "hwe"))  # fmt: skip
            out[(c, s)] = {"gva": sum(gva.values()), "emol": emol, "surplus": sum(gva.values()) - emol,
                           "nonprop": nonprop}  # fmt: skip
    return out, sorted(set(df["prov_id"].to_list()))


def _agg(asu: dict, cats: list[str], area: str, item: str) -> float:
    return sum(asu[(c, area)][item] for c in cats)


def _v2a(ctx: BlockContext, prod: dict, hh: dict, entries: list, cons: list, sats: dict) -> dict:
    gos = prod["gos"]
    leaves = sorted({n for _, ns in HH_GROUPS.values() for n in ns})
    ids = [f"s7_1c.{n}.{i}.current" for n in [*leaves, "total"] for i in ("os_mi", "cfc", "ce")]
    c7, p71c = _get(ctx, S71C, ids)
    hh_g = {k: sum(c7[f"s7_1c.{n}.os_mi.current"] + c7[f"s7_1c.{n}.cfc.current"] for n in ns)
            for k, (_, ns) in HH_GROUPS.items()}  # fmt: skip
    hh_total = c7["s7_1c.total.os_mi.current"] + c7["s7_1c.total.cfc.current"]
    ctx.check("v2a.hh_groups_sum", "NAS 7.1C household gross OS/MI: sum of the industry leaves used vs 7.1C total",
              sum(hh_g.values()), hh_total, target_prov_id=p71c[0], tol_abs=0.01)  # fmt: skip
    asu, pas = _asuse(ctx)

    hh_a: dict[str, float] = {a: 0.0 for a in gos}
    notes: list[str] = []
    # single-activity groups: the household share is exact at group level
    for k in SINGLE:
        (a,) = HH_GROUPS[k][0]
        v = hh_g[k]
        if v > gos[a]:
            notes.append(f"{k}: household {v:,.2f} > SUT GOS {gos[a]:,.2f}, capped")
            v = gos[a]
        hh_a[a] = v
    # mining: all household mining is quarrying (A_OMIN); coal and oil/gas have no household part
    v = hh_g["mining"]
    if v > gos["A_OMIN"]:
        raise SamError(f"household mining {v:,.2f} exceeds A_OMIN GOS {gos['A_OMIN']:,.2f}")
    hh_a["A_OMIN"] = v
    # manufacturing and other services: two-column RAS with ASUSE surplus as the household prior
    ras_prior = {}
    for k in ("manufacturing", "other_services"):
        acts = HH_GROUPS[k][0]
        prior = {a: max(0.0, _agg(asu, ASUSE_MAP[a], "total", "surplus")) for a in acts}
        ras_prior.update(prior)
        got = lib.ras_two_columns({a: gos[a] for a in acts}, hh_g[k], prior)
        hh_a.update(got)
    # real estate & professional (group 9): household non-dwelling surplus by the ASUSE ratio method
    gva9 = _agg(asu, GRP9_NONDWELL, "total", "gva")
    emol9 = _agg(asu, GRP9_NONDWELL, "total", "emol")
    ratio9 = (gva9 - emol9) / emol9
    hh_nondwell = c7["s7_1c.real_estate_prof.ce.current"] * ratio9
    hh_dwel = hh_g["real_estate_prof"] - hh_nondwell
    if hh_dwel > gos["A_DWEL"]:
        notes.append(f"group 9: household dwellings {hh_dwel:,.2f} capped at A_DWEL GOS {gos['A_DWEL']:,.2f}")
        hh_nondwell += hh_dwel - gos["A_DWEL"]
        hh_dwel = gos["A_DWEL"]
    s_it = _agg(asu, ["s7"], "total", "surplus")
    s_bs = _agg(asu, ["s10", "s11", "s12"], "total", "surplus")
    it = min(gos["A_ITSV"], hh_nondwell * s_it / (s_it + s_bs))
    bs = hh_nondwell - it
    if bs > gos["A_BSRE"]:
        raise SamError(f"group 9 household non-dwelling surplus does not fit A_BSRE ({bs:,.2f} > {gos['A_BSRE']:,.2f})")
    hh_a.update({"A_DWEL": hh_dwel, "A_BSRE": bs, "A_ITSV": it})
    # financial corporations and public administration have no household sector (7.1C financial = 0)
    if hh_g["financial"] != 0:
        raise SamError(f"NAS 7.1C financial household OS/MI is {hh_g['financial']} (not 0): needs a method")
    for n in notes:
        ctx.warn(f"V2a {n}")

    # dwellings: imputed vs actual (households' C4a split)
    c4a = hh["c4a"]
    s_imp = c4a["imputed_rent"] / (c4a["imputed_rent"] + c4a["actual_rent"] + c4a.get("govt_housing", 0.0))
    dw_imp = min(s_imp * gos["A_DWEL"], hh_dwel)
    dw_act = hh_dwel - dw_imp
    # partnerships, trusts, co-operatives: share of ASUSE GVA in non-proprietary establishments
    q = {a: _agg(asu, cs, "total", "nonprop") / _agg(asu, cs, "total", "gva") for a, cs in ASUSE_MAP.items()}
    quasi = {a: (q[a] * hh_a[a] if a in q and a not in ("A_DWEL",) else 0.0) for a in gos}
    mixd = {a: hh_a[a] - quasi[a] for a in gos}
    mixd["A_DWEL"] = 0.0
    corp = {a: gos[a] - hh_a[a] for a in gos}
    folded = []
    for a in sorted(gos):
        if 0 < quasi[a] < MIN_ENTRY:
            folded.append(f"{a} hh_quasi {quasi[a]:.4f} -> mixed income")
            mixd[a] += quasi[a]
            quasi[a] = 0.0
        if 0 < mixd[a] < MIN_ENTRY:
            folded.append(f"{a} mixed income {mixd[a]:.4f} -> hh_quasi" if quasi[a] > 0 else
                          f"{a} mixed income {mixd[a]:.4f} -> corp_gov (household share below Rs 1 crore)")  # fmt: skip
            if quasi[a] > 0:
                quasi[a] += mixd[a]
            else:
                corp[a] += mixd[a]
                hh_a[a] -= mixd[a]
            mixd[a] = 0.0
        if corp[a] < -1e-6:
            raise SamError(f"V2a {a}: corporate/government surplus negative ({corp[a]:,.4f})")
        if 0 < corp[a] < MIN_ENTRY:
            folded.append(f"{a} corp_gov {corp[a]:.4f} -> household mixed income")
            mixd[a] += corp[a]
            hh_a[a] += corp[a]
            corp[a] = 0.0
    if folded:
        ctx.log(f"V2a pieces below Rs {MIN_ENTRY} crore folded into their complement: {folded}")

    # provenance
    gos_pid = prod["gos_pid"]
    single_pid = ctx.prov(
        ref="V2a", status="derived", inputs=[gos_pid, *p71c], source_id=_src(ctx, p71c[0]),
        method="Gap map V2a, single-activity NAS groups (crops, livestock, forestry+fishing, utilities, "
        "construction, trade & repair, hotels, transport, communication) and the groups with no household "
        "sector (financial: 7.1C = 0; public administration: GG only): household gross OS/MI of the group = "
        "NAS 2026 Statement 7.1C OS/MI + CFC of its rows (transport = railways + road + water + transport "
        "services + storage; 7.1C has no air row); corp_gov = SUT GOS of the activity (production's V2 target) - "
        "household part. Mixed income = the household part where the partnership/trust share q is 0 (no ASUSE "
        "category describes the activity's household part: crops, livestock, forestry+fishing, utilities, "
        "construction; see the V2a(b) record).",
    )  # fmt: skip
    ras_pid = ctx.prov(
        ref="V2a", status="estimated", inputs=[gos_pid, *p71c, *pas], source_id=_src(ctx, p71c[0]),
        method="Gap map V2a, multi-activity NAS groups (manufacturing, other services), where the gap map's "
        "'SUT OS shares within the group' are pro rata to GVA (Q2): the group's 7.1C household gross OS/MI is "
        "spread over its activities by a two-column RAS (rows = SUT GOS by activity; columns = household total "
        "and the rest); household prior = ASUSE 2023-24 surplus of unincorporated enterprises of the mapped "
        "categories (Table 4 establishments x Table 37 GVA per establishment, OAE + HWE, minus Table 33 hired "
        "workers x emoluments per hired worker); rest prior = the activity's GOS. Mapping: M2 food; M3+M4 "
        "beverages & tobacco; M1+M5+M6+M7 textiles; M8+M9+M10+M23 wood/paper/furniture; M24 gems & other; M11 "
        "petroleum; M12+M14 chemicals; M13 pharma; M15 non-metallic; M16 metals; M17+M20+M25 machinery; "
        "M18+M19 electrical; M21+M22 transport equipment; S13 education; S14 health; S15 other services. "
        "Mining: all 7.1C household mining is quarrying (A_OMIN); coal and oil/gas have no household part "
        "(assumption). Group 9: household non-dwelling surplus = 7.1C real-estate/professional CE x ASUSE "
        "(GVA - emoluments)/emoluments of S7+S10+S11+S12 (ownership of dwellings has no CE), split between "
        "A_ITSV (S7) and A_BSRE (S10-S12) by ASUSE surplus; the rest of group 9 is dwellings (see the dwelling "
        "record). ASUSE levels are used only as shares or ratios.",
    )  # fmt: skip
    quasi_pid = ctx.prov(
        ref="V2a", status="estimated", inputs=[*p71c, *pas, gos_pid], source_id=_src(ctx, pas[0]),
        method="Gap map V2a(b): surplus of household-sector partnerships between different households, "
        "societies/trusts, co-operatives and 'others' goes to F_GOSC (component hh_quasi), not mixed income. "
        "Share q_a = sum over OAE and HWE of ASUSE 2023-24 Table 6 establishment shares of those ownership types "
        "x the type's GVA (Table 4 x Table 37), divided by all GVA of the activity's ASUSE categories; hh_quasi = "
        "q_a x the household part of the activity, and mixed income (F_MIXD) = the household part - hh_quasi "
        "(the household part is exact at NAS-group level in single-activity groups: 7.1C). Proprietary units, "
        "same-household partnerships and SHGs stay mixed income. Assumption: non-proprietary units have their "
        "type's average GVA per establishment. Categories: ASUSE sub-categories for every activity, as in the "
        "V2a RAS record for manufacturing and other services, and T1+T2+T3+T4+T5 trade (not the aggregate T), "
        "S1+S2 hotels, S3-S6 transport, S7 communication and IT, S10-S12 business services. q = 0 (logged) for "
        "farming, mining and construction (outside ASUSE) and for utilities (ASUSE category E is only "
        "non-captive electricity, NIC 35103/35105-35107/35109, and NIC 36-39 sits inside S15 with personal "
        "services, so no ASUSE category describes household utilities).",
    )  # fmt: skip
    dwel_pid = ctx.prov(
        ref="V2a", status="estimated", inputs=[*p71c, *pas, gos_pid, *hh["c4a_pids"]], source_id=_src(ctx, p71c[0]),
        method="Gap map V2a(a): household dwelling surplus = 7.1C real-estate/professional gross OS/MI minus the "
        "household non-dwelling part (ASUSE ratio method), capped at A_DWEL GOS; all of it to F_GOSC. Imputed "
        "part = min(s_imp x A_DWEL GOS, household dwelling surplus), with s_imp = households' C4a imputed rent / "
        "(imputed + actual rent + government housing); actual (rented-out) part = the rest. The CFC-based "
        "alternative is rejected (issues factors-1: 7.1C group-9 CFC is below SUT dwelling CFC); the rest of "
        "A_DWEL GOS is corporate/government-owned dwellings (corp_gov).",
    )  # fmt: skip
    group_of = {a: k for k, (acts, _) in HH_GROUPS.items() for a in acts}
    for a in sorted(gos):
        k = group_of.get(a, "public_admin")
        single = k in SINGLE or k in ("financial", "public_admin")
        if a in ("A_COAL", "A_OILG"):
            single = False
        if corp[a] > 0:
            if single:
                entries.append(entry("F_GOSC", a, "V2a", corp[a], component="corp_gov", prov_id=single_pid,
                                     status="derived", role="anchored", tol_rel=0.02))  # fmt: skip
            else:
                pid = dwel_pid if a == "A_DWEL" else ras_pid
                conf = "low" if a == "A_DWEL" else ("high" if a in ("A_COAL", "A_OILG") else "medium")
                entries.append(entry("F_GOSC", a, "V2a", corp[a], component="corp_gov", prov_id=pid,
                                     status="estimated", role="free", confidence=conf))  # fmt: skip
        if mixd[a] > 0:
            if single and quasi[a] == 0:
                entries.append(entry("F_MIXD", a, "V2a", mixd[a], component="mixed_income", prov_id=single_pid,
                                     status="derived", role="anchored", tol_rel=0.02))  # fmt: skip
            else:
                pid = quasi_pid if single else ras_pid
                entries.append(entry("F_MIXD", a, "V2a", mixd[a], component="mixed_income", prov_id=pid,
                                     status="estimated", role="free", confidence="medium"))  # fmt: skip
        if quasi[a] > 0:
            entries.append(entry("F_GOSC", a, "V2a", quasi[a], component="hh_quasi", prov_id=quasi_pid,
                                 status="estimated", role="free", confidence="low"))  # fmt: skip
    for comp, v in (("hh_dwelling_imputed", dw_imp), ("hh_dwelling_actual", dw_act)):
        if v >= MIN_ENTRY:
            entries.append(entry("F_GOSC", "A_DWEL", "V2a", v, component=comp, prov_id=dwel_pid, status="estimated",
                                 role="free", confidence="low"))  # fmt: skip
        elif v > 0:
            raise SamError(f"V2a {comp} {v:.4f} below Rs {MIN_ENTRY} crore")

    # constraints: 7.1C household controls by group (components filter) and the household cap per activity
    hh_comps = ["mixed_income", "hh_quasi", "hh_dwelling_imputed", "hh_dwelling_actual"]
    ctrl_pid = ctx.prov(
        ref="V2a", status="derived", inputs=list(p71c),
        method="Gap map V2a household anchor: NAS 2026 Statement 7.1C household-sector OS/MI + CFC of the NAS "
        "industry group (rows listed in the constraint description) = the household components (mixed income, "
        "hh_quasi, household dwellings) of the group's activities (XR-20).",
    )  # fmt: skip
    for k, (acts, rows) in HH_GROUPS.items():
        cons.append(constraint(
            f"v2a_hh.{k}", "V2a", ["F_MIXD", "F_GOSC"], acts, hh_g[k], prov_id=ctrl_pid, tol_abs=CHECK_TOL,
            refs=["V2a"], components=hh_comps,
            description=f"NAS 7.1C household gross OS/MI of {k} ({' + '.join(rows)}) = household components",
        ))  # fmt: skip
    cap_pid = ctx.prov(
        ref="V2a", status="derived", inputs=[gos_pid],
        method="Gap map V2a household cap (XR-20, kind max): the household components of an activity's surplus "
        "are at most its SUT 2023-24 OS/MI + CFC (production's V2 target, with production's tolerance). Declared "
        "for the activities of multi-activity NAS groups only: in a single-activity group the 7.1C control fixes "
        "the household part exactly, and financial services / public administration have none.",
    )  # fmt: skip
    capped = sorted(a for k in ("mining", "manufacturing", "real_estate_prof", "other_services")
                    for a in HH_GROUPS[k][0])  # fmt: skip
    for a in capped:
        cons.append(constraint(
            f"v2a_cap.{a.lower()}", "V2a", ["F_MIXD", "F_GOSC"], [a], gos[a], prov_id=cap_pid,
            tol_abs=prod["gos_tol"][a], kind="max", refs=["V2a"], components=hh_comps,
            description=f"Household part of {a} surplus <= its SUT OS/MI + CFC (production V2 target)",
        ))  # fmt: skip

    # checks and diagnostics
    ctx.check("v2a.hh_total", "Household components of V2a vs NAS 7.1C total OS/MI + CFC",
              sum(mixd.values()) + sum(quasi.values()) + dw_imp + dw_act, hh_total, target_prov_id=p71c[0],
              tol_abs=CHECK_TOL)  # fmt: skip
    for k, (acts, _) in HH_GROUPS.items():
        got = sum(mixd[a] + quasi[a] for a in acts) + (dw_imp + dw_act if "A_DWEL" in acts else 0.0)
        ctx.check(f"v2a.hh.{k}", f"Household components of {k} vs NAS 7.1C", got, hh_g[k],
                  target_prov_id=p71c[0], tol_abs=0.01)  # fmt: skip
    share_dw = hh_dwel / gos["A_DWEL"]
    cfc_ids = ["s7_1c.real_estate_prof.cfc.current"]
    cfc_hh9 = c7[cfc_ids[0]]
    sut_dw_cfc_sh = None
    try:
        vcfc = ctx.rows("io_tables_sut_va", series_id="va.cfc.sut_i57.current", vintage=VINTAGE)
        sut_dw_cfc = float(vcfc["value"][0])
        sut_dw_cfc_sh = cfc_hh9 / sut_dw_cfc
        p_sut = sorted(set(vcfc["prov_id"].to_list()))
    except SamError:
        p_sut = []
    if not 0.70 <= share_dw <= 1.0:
        ctx.warn(f"V2a household dwelling share of A_DWEL GOS {share_dw:.4f} outside [0.70, 1.00]")
    va_rows = []
    for a in sorted(gos):
        for item, v in (("hh_mixed_income", mixd[a]), ("hh_quasi", quasi[a]), ("corp_gov", corp[a]),
                        ("household_total", hh_a[a] if a != "A_DWEL" else hh_dwel)):  # fmt: skip
            va_rows.append((f"{item}.{a.lower()}", item, a, v, "INR_crore", ras_pid))
        if a in q:
            va_rows.append((f"q_nonprop.{a.lower()}", "q_nonprop", a, q[a], "ratio", quasi_pid))
    va_rows += [
        ("dwelling.imputed", "hh_dwelling_imputed", "A_DWEL", dw_imp, "INR_crore", dwel_pid),
        ("dwelling.actual", "hh_dwelling_actual", "A_DWEL", dw_act, "INR_crore", dwel_pid),
        ("dwelling.s_imp", "s_imp", "A_DWEL", s_imp, "ratio", dwel_pid),
        ("dwelling.hh_share", "hh_dwelling_share", "A_DWEL", share_dw, "ratio", dwel_pid),
        ("group9.ratio_asuse", "asuse_surplus_to_emoluments", "S7+S10+S11+S12", ratio9, "ratio", ras_pid),
        ("group9.hh_nondwelling", "hh_nondwelling", "A_BSRE+A_ITSV", hh_nondwell, "INR_crore", ras_pid),
    ]
    if sut_dw_cfc_sh is not None:
        sens_pid = ctx.prov(
            ref="V2a", status="estimated", inputs=[*p71c, *p_sut, gos_pid], source_id=_src(ctx, p71c[0]),
            method="Gap map V2a sensitivity (plan s.5 C7): CFC-consistent household dwelling share = NAS 7.1C "
            "real-estate/professional household CFC / SUT A_DWEL (industry 57) CFC; the amount it would move is "
            "(built share - that share) x A_DWEL GOS, between F3a/F3b and F2 (totals unchanged). Report only.",
        )  # fmt: skip
        va_rows += [("sensitivity.hh_dwelling_share_cfc", "sensitivity", "A_DWEL", sut_dw_cfc_sh, "ratio", sens_pid),
                    ("sensitivity.moved", "sensitivity", "A_DWEL", (share_dw - sut_dw_cfc_sh) * gos["A_DWEL"],
                     "INR_crore", sens_pid)]  # fmt: skip
    sats["va_split_by_activity"] = _sat(
        "V2a",
        va_rows,
        ctx,
        "V2a split of SUT OS/MI + CFC by activity: household "
        "mixed income, partnerships/trusts, dwellings, corporate/government; keys "
        "and the dwelling sensitivity",
        dims=("item", "activity"),
        decimals=9,
    )
    return {"mixd": mixd, "quasi": quasi, "dw_imp": dw_imp, "dw_act": dw_act, "asu": asu, "asu_pids": pas,
            "hh_total": hh_total, "hh_pid": p71c[0], "p71c": p71c, "corp": corp,
            "pids": {"single": single_pid, "ras": ras_pid, "quasi": quasi_pid, "dwel": dwel_pid}}  # fmt: skip


# =============================================================================================
# V3, V4: CE with the rest of the world
# =============================================================================================


def _v3_v4(ctx: BlockContext, entries: list) -> dict:
    fr, to = "s6_1.compensation_of_employees_from_rest_of_the_world.current", \
        "s6_1.compensation_of_employees_to_the_rest_of_the_world.current"  # fmt: skip
    v, p = _get(ctx, S61, [fr, to])
    v3 = ctx.prov(ref="V3", status="official", inputs=p,
                  method="Gap map V3: NAS 2026 Statement 6.1 item 2, compensation of employees from the rest of "
                  "the world, as published; all of it to regular labour (F_LREG): gap-map assumption "
                  "(seafarers, mission staff are salaried).")  # fmt: skip
    v4 = ctx.prov(ref="V4", status="official", inputs=p,
                  method="Gap map V4: NAS 2026 Statement 6.1 item 7, compensation of employees to the rest of the "
                  "world, as published; paid out of regular labour income (F_LREG), gap-map assumption.")  # fmt: skip
    entries.append(entry("F_LREG", "R_ROW", "V3", v[fr], prov_id=v3, status="official", role="fixed"))
    entries.append(entry("R_ROW", "F_LREG", "V4", v[to], prov_id=v4, status="official", role="fixed"))
    b, pb = _get(ctx, BOP, ["bpm6.inr.bpm6_1_b_1.credit.current", "bpm6.inr.bpm6_1_b_1.debit.current"])
    ctx.check("v3.bop", "V3 (NAS 6.1) vs RBI BoP BPM6 compensation of employees, credit (rounded)", v[fr],
              b["bpm6.inr.bpm6_1_b_1.credit.current"], target_prov_id=pb[0], tol_abs=CHECK_TOL)  # fmt: skip
    ctx.check("v4.bop", "V4 (NAS 6.1) vs RBI BoP BPM6 compensation of employees, debit (rounded)", v[to],
              b["bpm6.inr.bpm6_1_b_1.debit.current"], target_prov_id=pb[0], tol_abs=CHECK_TOL)  # fmt: skip
    return {"v3": v[fr], "v4": v[to], "pids": p}


# =============================================================================================
# F4: sector GOS (NAS arithmetic)
# =============================================================================================

ITEMS = ("gva", "ce", "net_production_taxes", "cfc", "os")


def _f4(ctx: BlockContext, prod: dict, entries: list, cons: list, sats: dict) -> dict:
    a, pa = _get(ctx, S71A, [f"s7_1a.{r}.{i}.current" for r in ("total", "financial") for i in ITEMS])
    b, pb = _get(ctx, S71B, [f"s7_1b.{r}.{i}.current" for r in ("total", "financial") for i in ITEMS])
    g, pg = _get(ctx, S8151, [f"s8_15_1.total.{i}.current" for i in ITEMS])
    h, ph = _get(ctx, S71C, [f"s7_1c.total.{i}.current" for i in ("gva", "ce", "net_production_taxes", "cfc",
                                                                     "os_mi")])  # fmt: skip
    sec = {
        "nfc_public": {i: a[f"s7_1a.total.{i}.current"] - g[f"s8_15_1.total.{i}.current"]
                       - a[f"s7_1a.financial.{i}.current"] for i in ITEMS},
        "nfc_private": {i: b[f"s7_1b.total.{i}.current"] - b[f"s7_1b.financial.{i}.current"] for i in ITEMS},
        "fc_public": {i: a[f"s7_1a.financial.{i}.current"] for i in ITEMS},
        "fc_private": {i: b[f"s7_1b.financial.{i}.current"] for i in ITEMS},
        "gg": {i: g[f"s8_15_1.total.{i}.current"] for i in ITEMS},
        "households_npish": {i: h[f"s7_1c.total.{'os_mi' if i == 'os' else i}.current"] for i in ITEMS},
    }  # fmt: skip
    for s in sec.values():
        s["gos"] = s["gva"] - s["ce"] - s["net_production_taxes"]
    inputs = sorted({*pa, *pb, *pg, *ph})
    pid = ctx.prov(
        ref="F4", status="derived", inputs=inputs,
        method="Gap map F4: sector GOS = GVA - CE - net production taxes, NAS 2026. Public NFC = Statement 7.1A "
        "total - 8.15.1 total (general government) - 7.1A financial row; private NFC = 7.1B total - 7.1B "
        "financial row; public FC = 7.1A financial; private FC = 7.1B financial; GG = 8.15.1 total (GOS = CFC); "
        "households incl. NPISH = 7.1C total (OS/MI). E_NFPU and E_NFPR entries are the NFC GOS; FC and GG are "
        "constraints (fincorp writes F4a, F4b splits GG).",
    )  # fmt: skip
    entries.append(entry("E_NFPU", "F_GOSC", "F4", sec["nfc_public"]["gos"], prov_id=pid, status="derived",
                         role="fixed"))  # fmt: skip
    entries.append(entry("E_NFPR", "F_GOSC", "F4", sec["nfc_private"]["gos"], prov_id=pid, status="derived",
                         role="fixed"))  # fmt: skip
    # FC GOS: the same series and arithmetic as fincorp.f4a.fc_gos_total (byte-identical target)
    fc = (a["s7_1a.financial.os.current"] + a["s7_1a.financial.cfc.current"] + b["s7_1b.financial.os.current"]
          + b["s7_1b.financial.cfc.current"])  # fmt: skip
    fc_pid = ctx.prov(
        ref="F4", status="derived", inputs=sorted({*pa, *pb}),
        method="Gap map F4, financial corporations: FC GOS = NAS 2026 Statement 7.1A financial OS + CFC + 7.1B "
        "financial OS + CFC (added in that order; the same series and arithmetic as fincorp's F4a total). "
        "factors writes no FC entry: fincorp's F4a entries must sum to it.",
    )  # fmt: skip
    cons.append(constraint("f4.fc_gos", "F4", ["E_RBI", "E_BANK", "E_NBFC", "E_INSP"], ["F_GOSC"], fc,
                           prov_id=fc_pid, tol_abs=1.0, refs=["F4a"],
                           description="FC GOS (NAS 7.1A + 7.1B financial OS + CFC) = F4a entries"))  # fmt: skip
    gg_pid = ctx.prov(
        ref="F4", status="derived", inputs=list(pg),
        method="Gap map F4, general government: GG GOS = GG CFC (OS = 0), NAS 2026 Statement 8.15.1 total CFC; "
        "split between Centre and States by F4b.",
    )  # fmt: skip
    cons.append(constraint("f4.gg_gos", "F4", ["G_CEN", "G_STA"], ["F_GOSC"], g["s8_15_1.total.cfc.current"],
                           prov_id=gg_pid, tol_abs=0.5, refs=["F4b"],
                           description="GG GOS (NAS 8.15.1 CFC) = F4b entries"))  # fmt: skip
    for code, s in (("E_NFPU", "nfc_public"), ("E_NFPR", "nfc_private")):
        cons.append(constraint(f"f4.{s}", "F4", [code], ["F_GOSC"], sec[s]["gos"], prov_id=pid, tol_abs=0.01,
                               refs=["F4"], description=f"{s} GOS (NAS arithmetic; the fixed F4 entry)"))  # fmt: skip

    # checks against Statement 1.14 / 8.16 and the V2 total
    names = {"nfc_public": "nfc_public", "nfc_private": "nfc_private", "fc_public": "fc_public",
             "fc_private": "fc_private", "gg": "gg", "households_npish": "households_npish"}  # fmt: skip
    ids = [f"s1_14.{n}.{i}.current" for n in names.values() for i in
           ("gross_value_added_at_basic_prices", "consumption_of_fixed_capital")]  # fmt: skip
    s114, p114 = _get(ctx, S114, ids)
    for s, n in names.items():
        ctx.check(
            f"f4.gva.{s}",
            f"{s} GVA (7.1A/7.1B/8.15.1/7.1C arithmetic) vs NAS 1.14",
            sec[s]["gva"],
            s114[f"s1_14.{n}.gross_value_added_at_basic_prices.current"],
            target_prov_id=p114[0],
            tol_abs=0.01,
        )
        ctx.check(
            f"f4.cfc.{s}",
            f"{s} CFC vs NAS 1.14",
            sec[s]["cfc"],
            s114[f"s1_14.{n}.consumption_of_fixed_capital.current"],
            target_prov_id=p114[0],
            tol_abs=0.01,
        )
        ctx.check(f"f4.gos_identity.{s}", f"{s} GOS: GVA - CE - NPT vs OS + CFC", sec[s]["gos"],
                  sec[s]["os"] + sec[s]["cfc"], target_prov_id=pid, tol_abs=0.01)  # fmt: skip
    c816, p816 = _get(ctx, S816, ["s8_16.departmental_enterprises.cfc.current", "s8_16.non_financial.cfc.current",
                                  "s8_16.administrative_departments.cfc.current"])  # fmt: skip
    ctx.check("f4.cfc.nfc_public_8_16", "Public NFC CFC vs NAS 8.16 departmental enterprises + non-financial",
              sec["nfc_public"]["cfc"], c816["s8_16.departmental_enterprises.cfc.current"]
              + c816["s8_16.non_financial.cfc.current"], target_prov_id=p816[0], tol_abs=0.01)  # fmt: skip
    ctx.check(
        "f4.gg_cfc_8_16",
        "GG GOS vs NAS 8.16 administrative departments CFC",
        sec["gg"]["gos"],
        c816["s8_16.administrative_departments.cfc.current"],
        target_prov_id=p816[0],
        tol_abs=0.01,
    )
    s41, p41 = _get(ctx, S41, ["s4_1.consumption_of_fixed_capital.current"])
    gg41 = s41["s4_1.consumption_of_fixed_capital.current"]
    ctx.check("f4.gg_cfc_4_1", "GG GOS vs NAS 4.1 CFC", sec["gg"]["gos"], gg41,
              target_prov_id=p41[0], tol_abs=0.01)  # fmt: skip
    ctx.check(
        "f4.fc_vs_sut",
        "FC GOS target vs SUT A_FINS + A_INSR OS/MI + CFC (production V2)",
        fc,
        prod["gos"]["A_FINS"] + prod["gos"]["A_INSR"],
        target_prov_id=prod["gos_pid"],
        tol_abs=CHECK_TOL,
    )
    ctx.check("f4.sectors_vs_v2", "Sum of sector GOS (NAS) vs SUT OS/MI + CFC (production V2 targets)",
              sum(s["gos"] for s in sec.values()), sum(prod["gos"].values()), target_prov_id=prod["gos_pid"],
              tol_abs=CHECK_TOL)  # fmt: skip
    rows = [(f"{s}.{i}", s, i, v[i], "INR_crore", pid) for s, v in sec.items() for i in (*ITEMS, "gos")]
    sats["sector_gos"] = _sat("F4", rows, ctx, "NAS 2026 GVA, CE, net production taxes, CFC, OS and GOS by "
                              "institutional sector (F4 arithmetic)", dims=("sector", "item"), decimals=6)  # fmt: skip
    return {"sec": sec, "fc": fc, "gg": g["s8_15_1.total.cfc.current"], "gg_pid": gg_pid, "pid": pid}


# =============================================================================================
# F4b: GG GOS (= CFC), Centre vs States
# =============================================================================================


def _f4b(ctx: BlockContext, sec: dict, entries: list, cons: list, sats: dict) -> None:
    ids = [f"s4_1.{k}.current" for k in ("central_government", "state_government", "local_bodies",
                                         "autonomous_institutions", "net_value_added")]  # fmt: skip
    n, pn = _get(ctx, S41, ids)
    gia, pg = _get(ctx, GIA, ["gia.cash.autonomous_bodies.total", "gia.cash.autonomous_bodies.capital_assets"])
    cen, sta = n["s4_1.central_government.current"], n["s4_1.state_government.current"]
    loc, aut = n["s4_1.local_bodies.current"], n["s4_1.autonomous_institutions.current"]
    nva = n["s4_1.net_value_added.current"]
    gia_rev = gia["gia.cash.autonomous_bodies.total"] - gia["gia.cash.autonomous_bodies.capital_assets"]
    aut_c = min(gia_rev, aut)
    if gia_rev > aut:
        ctx.warn(f"F4b Union revenue grants to autonomous bodies {gia_rev:,.2f} exceed NAS 4.1 autonomous "
                 f"institutions NVA {aut:,.2f}: capped")  # fmt: skip
    share_c = (cen + aut_c) / nva
    share_a = cen / (nva - aut)
    ctx.check("f4b.nva_parts", "NAS 4.1 NVA: Centre + States + local bodies + autonomous vs total", cen + sta + loc
              + aut, nva, target_prov_id=pn[0], tol_abs=CHECK_TOL)  # fmt: skip
    total = sec["gg"]
    pid = ctx.prov(
        ref="F4b", status="estimated", inputs=[*pn, *pg, sec["gg_pid"]], source_id=_src(ctx, pn[0]),
        method="Gap map F4b: GG GOS (= CFC, NAS 8.15.1) split pro rata to NAS 2026 Statement 4.1 NVA, "
        "institutional view (D2-8). Centre = central government NVA + central autonomous bodies, proxied by "
        "Union revenue grants-in-aid to autonomous bodies (Finance Accounts 2023-24 IGAS-2: cash grants total "
        "minus grants for creation of capital assets), capped at the 4.1 autonomous-institutions NVA; States = "
        "State governments + local bodies + the rest of the autonomous institutions (the States' grants to their "
        "autonomous bodies are not in clean data). Assumption: equal CFC/NVA ratios across governments.",
    )  # fmt: skip
    g_cen = share_c * total
    entries.append(entry("G_CEN", "F_GOSC", "F4b", g_cen, prov_id=pid, status="estimated", role="free",
                         confidence="medium"))  # fmt: skip
    entries.append(entry("G_STA", "F_GOSC", "F4b", total - g_cen, prov_id=pid, status="estimated", role="free",
                         confidence="medium"))  # fmt: skip
    if not 0.25 <= share_c <= 0.35:
        ctx.warn(f"F4b Centre share {share_c:.4f} outside [0.25, 0.35]")
    # audit BS-12 (factors-22, 2026-10-01): balancing moved the Centre's CFC share to 0.323 while C2a moved own
    # output to the States, so the two splits built from one key went opposite ways. No source splits GG CFC by
    # government (NAS 4.1 publishes it for GG only; factors-15), so the NAS 4.1 NVA key is held within a band. The
    # 5% is a judgement with no source; it is wider than the gap to sensitivity A (share_a, about 1%), which is only
    # a floor, not where the 5% comes from. C2a keeps its own cash evidence and +-10% band (government-7). The band
    # has its own estimated record saying so (close-out V-F-10)
    tol_c = max(0.05, abs(share_c - share_a) / share_c)
    band_pid = ctx.prov(
        ref="F4b", status="estimated", inputs=[pid], source_id=_src(ctx, pn[0]),
        method="Constraint f4b.centre (audit BS-12, factors-23): the Centre's F4b entry (G_CEN <- F_GOSC) within "
        "a band around its NAS 4.1 NVA-key value. Tolerance = max(5%, |key share - sensitivity A share| / key "
        f"share) = {tol_c:.2%}. The 5% is a judgement band with no source: no clean source splits GG CFC between "
        "the Centre and the States (NAS 4.1 publishes CFC for GG only; factors-15), and the gap to sensitivity A "
        f"({abs(share_c - share_a) / share_c:.2%}) is only a floor, so the band is not derived from sensitivity A. "
        "If the band binds in balancing, its edge, not evidence, sets the balanced G_CEN (it bound at its upper "
        "edge in the wave C run of 2026-10-01). Owner item for Checkpoint B (factors-23).",
    )  # fmt: skip
    cons.append(constraint("f4b.centre", "F4b", ["G_CEN"], ["F_GOSC"], g_cen, prov_id=band_pid, kind="band",
                           tol_rel=tol_c, refs=["F4b"], description="Centre's GG CFC near the NAS 4.1 NVA key "
                           f"(judgement band {tol_c:.0%})"))  # fmt: skip
    in_pid = ctx.prov(ref="F4b", status="official", inputs=list(pn), source_id=_src(ctx, pn[0]),
                      method="Gap map F4b key inputs as published: NAS 2026 Statement 4.1 NVA by government "
                      "(current prices).")  # fmt: skip
    # a difference of two published figures is derived, not official (SAM_GUIDE s.5; verification V-F-4)
    gia_pid = ctx.prov(ref="F4b", status="derived", inputs=list(pg), source_id=_src(ctx, pg[0]),
                       method="Gap map F4b key input: Union revenue grants-in-aid to autonomous bodies = Union Finance "
                       "Accounts 2023-24 (IGAS-2) cash grants-in-aid to autonomous bodies, total minus grants for "
                       "creation of capital assets (a difference of two published figures).")  # fmt: skip
    sens_pid = ctx.prov(ref="F4b", status="estimated", inputs=list(pn), source_id=_src(ctx, pn[0]),
                        method="Gap map F4b sensitivity A (plan s.2.9): autonomous institutions split pro rata to the "
                        "rest of GG NVA, so Centre share = central government NVA / (NVA - autonomous "
                        "institutions). Report only.")  # fmt: skip
    rows = [("centre_share", "centre_share", "G_CEN", share_c, "ratio", pid),
            ("state_share", "state_share", "G_STA", 1.0 - share_c, "ratio", pid),
            ("centre_share_sensitivity_a", "sensitivity", "G_CEN", share_a, "ratio", sens_pid),
            ("nva.central_government", "nva", "G_CEN", cen, "INR_crore", in_pid),
            ("nva.state_government", "nva", "G_STA", sta, "INR_crore", in_pid),
            ("nva.local_bodies", "nva", "G_STA", loc, "INR_crore", in_pid),
            ("nva.autonomous_institutions", "nva", "G_CEN+G_STA", aut, "INR_crore", in_pid),
            ("nva.total", "nva", "GG", nva, "INR_crore", in_pid),
            ("gia.autonomous_bodies_revenue", "gia_revenue", "G_CEN", gia_rev, "INR_crore", gia_pid),
            ("autonomous_to_centre", "autonomous_to_centre", "G_CEN", aut_c, "INR_crore", pid)]  # fmt: skip
    sats["gg_centre_state_key"] = _sat("F4b", rows, ctx, "Centre/State shares of GG NVA (NAS 4.1, institutional "
                                       "view) incl. the autonomous-bodies split; the F4b key that C2a must use",
                                       dims=("item", "government"), decimals=12)  # fmt: skip


# =============================================================================================
# F1a, F2, F3a, F3b, F3c: factor income by household group; F1 and F3 constraints
# =============================================================================================


def _ifpri(ctx: BlockContext) -> tuple[dict[str, dict[str, float]], dict[str, float], list[str]]:
    """IFPRI per-capita indices by factor and national quintile (T10 share x T11 spending per capita, normalised),
    T11 spending per capita by quintile (to strip it out for the HCES-rescaled sensitivity) and the prov_ids."""
    comps = ["labour_low_educated", "labour_medium_educated", "labour_high_educated", "labour_all", "crop_land",
             "capital_agriculture", "capital_non_agriculture"]  # fmt: skip
    t10, p10 = _get(ctx, IFPRI, [f"ifpri.t10.{c}.{q}" for c in comps for q in lib.QUINTILES], period=IFPRI_P,
                    unit="percent", price_basis=None)  # fmt: skip
    t11, p11 = _get(ctx, IFPRI, [f"ifpri.t11.total_spending_per_capita.{q}" for q in lib.QUINTILES], period=IFPRI_P,
                    unit="INR", price_basis=None)  # fmt: skip
    spend = {q: t11[f"ifpri.t11.total_spending_per_capita.{q}"] for q in lib.QUINTILES}

    def comp(*cs: str) -> dict[str, float]:
        return lib.ifpri_index({q: sum(t10[f"ifpri.t10.{c}.{q}"] for c in cs) for q in lib.QUINTILES}, spend)

    idx = {
        "regular": comp("labour_medium_educated", "labour_high_educated"),
        "casual": comp("labour_low_educated"),
        "labour_all": comp("labour_all"),
        "farm": comp("crop_land", "capital_agriculture"),
        "nonfarm": comp("capital_non_agriculture"),
    }
    return idx, spend, sorted({*p10, *p11})


def _shares(hh: dict, index_q: dict[str, float]) -> dict[str, dict[str, float]]:
    ig = lib.group_index(index_q, HH, hh["xwalk"])
    return {s: lib.area_shares(hh["pop"], ig, AREA_GROUPS[s]) for s in AREAS}


def _variant_shares(hh: dict, variant: str, index_q: dict[str, float], spend: dict[str, float]
                    ) -> dict[str, dict[str, float]]:  # fmt: skip
    """Within-area shares of one IFPRI-keyed factor under a sensitivity mapping (report only, D2-19).
    "xwalk": I_g = sum_q x_gq I_q (households' national-quintile crosswalk); "k_eq_q": I_g = I_q with q = k;
    "hces": k = q, with IFPRI's T11 spending per capita of quintile k replaced by the group's HCES 2023-24 MPCE
    (hces_total / pop_persons), i.e. I_g = T10 share of the factor in quintile k's income x MPCE_g, so the
    within-area gradient follows households' HCES consumption gradient."""
    if variant == "xwalk":
        ig = lib.group_index(index_q, HH, hh["xwalk_all"])
    elif variant == "k_eq_q":
        ig = lib.group_index(index_q, HH, None)
    elif variant == "hces":
        ig = {g: index_q[f"q{g[-1]}"] / spend[f"q{g[-1]}"] * hh["hces"][g] / hh["pop"][g] for g in HH}
    else:
        raise SamError(f"unknown sensitivity mapping {variant!r}")
    return {s: lib.area_shares(hh["pop"], ig, AREA_GROUPS[s]) for s in AREAS}


def _household_income(ctx: BlockContext, prod: dict, hh: dict, lab: dict, va: dict, row: dict, entries: list,
                      cons: list, sats: dict) -> None:  # fmt: skip
    idx, spend, pif = _ifpri(ctx)
    if hh["xwalk"]:
        xw_note = "households' hh_national_quintile_xwalk (I_g = sum_q x_gq I_q)"
    elif IFPRI_MAPPING == "k_eq_q":
        xw_note = (
            "k = q: the k-th group of each area takes the k-th national quintile's index (DECISIONS D2-19; "
            "the crosswalk and an HCES-rescaled variant are sensitivity rows in factor_income_keys)"
        )
    else:
        xw_note = "the assumption that the k-th quintile of each area takes the k-th national quintile's index (k = q)"
    key_in = sorted({*pif, *hh["pop_pids"], *hh["xw_pids"]})

    # ---- F1a: labour income ---------------------------------------------------------------------
    reg, ce = lab["reg"], lab["ce"]
    reg_g = {g: sum(reg[a] for a in reg if ACT_PLFS[a] == g) for g in PLFS_GROUPS}
    cas_g = {g: sum(ce[a] - reg[a] for a in reg if ACT_PLFS[a] == g) for g in PLFS_GROUPS}
    net_row = row["v3"] - row["v4"]
    reg_area = {"rural": sum(reg_g[g] * lib.rural_share(lab["reg_bill"], g) for g in PLFS_GROUPS)}
    reg_area["urban"] = sum(reg_g.values()) - reg_area["rural"]
    r_sh = reg_area["rural"] / sum(reg_area.values())
    reg_area = {"rural": reg_area["rural"] + net_row * r_sh, "urban": reg_area["urban"] + net_row * (1 - r_sh)}
    cas_area = {"rural": sum(cas_g[g] * lib.rural_share(lab["cas_bill"], g) for g in PLFS_GROUPS if cas_g[g] > 0)}
    cas_area["urban"] = sum(cas_g.values()) - cas_area["rural"]
    f1a_reg = lib.split_by_area(reg_area["rural"], reg_area["urban"], _shares(hh, idx["regular"]))
    f1a_cas = lib.split_by_area(cas_area["rural"], cas_area["urban"], _shares(hh, idx["casual"]))
    f1a_pid = ctx.prov(
        ref="F1a", status="estimated", inputs=sorted({*key_in, *lab["pids"], lab["est_pid"], *row["pids"]}),
        source_id=_src(ctx, pif[0]),
        method="Gap map F1a, fallback without PLFS unit data (D1-2). Factor totals: F_LREG = V1a regular CE + "
        "V3 - V4; F_LCAS = V1a casual CE. Rural/urban: each PLFS group's regular (casual) CE split by its rural "
        "and urban regular (casual) wage bills from V1a (PLFS Tables 20/26/51, API 6); A_PADM (all regular) is in "
        "PLFS group 58-99 (NIC section O), so its regular CE is split by that group's regular wage bills; V3 - V4 "
        "pro rata to the regular rural/urban split. Within an area, group g gets persons_g (households' "
        "pop_persons) x I_g, "
        "normalised; I_q = IFPRI 2022/23 T10 share of the factor in quintile q's income x T11 total spending per "
        "capita, normalised (regular: medium + high-educated labour; casual: low-educated labour), mapped with "
        f"{xw_note}. IFPRI is old base, 2022-23, national quintiles: used only as gradients (low confidence).",
    )  # fmt: skip
    for g in HH:
        for acct, vals in (("F_LREG", f1a_reg), ("F_LCAS", f1a_cas)):
            entries.append(entry(g, acct, "F1a", vals[g], prov_id=f1a_pid, status="estimated", role="free",
                                 confidence="low"))  # fmt: skip
    ce_rec, pce = _get(ctx, DERIVED, ["derived.ce_receivable_by_residents.current"])
    f1_pid = ctx.prov(
        ref="F1",
        status="derived",
        inputs=pce,
        method="Gap map F1: labour income of households = NAS 2026 CE receivable by residents "
        "(Statement 7.1 CE + 6.1 CE from RoW - 6.1 CE to RoW); the F1a entries must sum to it.",
    )
    f1_target = ce_rec["derived.ce_receivable_by_residents.current"]
    cons.append(constraint("f1.total", "F1", HH, ["F_LREG", "F_LCAS"], f1_target,
                           prov_id=f1_pid, tol_abs=CHECK_TOL, refs=["F1a"],
                           description="F1: labour income to households = NAS CE receivable by residents "
                           "(tolerance covers SUT vs NAS CE rounding, 0.17)"))  # fmt: skip
    ctx.check(
        "f1.total",
        "Sum of F1a vs NAS CE receivable by residents",
        sum(f1a_reg.values()) + sum(f1a_cas.values()),
        ce_rec["derived.ce_receivable_by_residents.current"],
        target_prov_id=pce[0],
        tol_abs=CHECK_TOL,
    )
    ce71, p71 = _get(ctx, S71, ["s7_1.total.ce.current", "s7_1.total.os_mi.current", "s7_1.total.cfc.current"])
    ctx.check("v1a.total", "Sum of V1a vs NAS 7.1 total CE", sum(ce.values()), ce71["s7_1.total.ce.current"],
              target_prov_id=p71[0], tol_abs=CHECK_TOL)  # fmt: skip

    # ---- F2: mixed income -------------------------------------------------------------------------
    mixd = va["mixd"]
    asu = va["asu"]
    api8 = {}
    p8: set[str] = set()
    for s in AREAS:
        v, p = _fy_mean(ctx, f"api_i8.self_employment_gross_earnings_30d.{s}.person.current")
        api8[s] = v
        p8.update(p)

    def plfs_rural(g: str) -> float:
        se = {s: lab["workers"][(g, s)] * lab["se_sh"][(g, s)] / 100.0 * api8[s] for s in AREAS}
        return se["rural"] / (se["rural"] + se["urban"])

    farm = sum(mixd[a] for a in FARM)
    farm_r = farm * plfs_rural("01-03")
    nonfarm = {"rural": 0.0, "urban": 0.0}
    rsh_used = {}
    for a, v in sorted(mixd.items()):
        if v <= 0 or a in FARM:
            continue
        if a in ASUSE_MAP:
            rs = {s: max(0.0, _agg(asu, ASUSE_MAP[a], s, "surplus")) for s in AREAS}
            r = rs["rural"] / (rs["rural"] + rs["urban"])
        elif a in PLFS_RU_KEY:
            r = plfs_rural(ACT_PLFS[a])
        else:
            raise SamError(f"F2: no rural/urban key for mixed income of {a}")
        rsh_used[a] = r
        nonfarm["rural"] += v * r
        nonfarm["urban"] += v * (1 - r)
    f2_farm = lib.split_by_area(farm_r, farm - farm_r, _shares(hh, idx["farm"]))
    f2_non = lib.split_by_area(nonfarm["rural"], nonfarm["urban"], _shares(hh, idx["nonfarm"]))
    f2_pid = ctx.prov(
        ref="F2", status="estimated", inputs=sorted({*key_in, *lab["pids"], *p8, *va["asu_pids"],
                                                    va["pids"]["ras"], va["pids"]["single"], va["pids"]["quasi"]}),
        source_id=_src(ctx, pif[0]),
        method="Gap map F2 (fallback without unit data). Totals: farm = V2a mixed income of A_CROP, A_LVST, "
        "A_FOFI; non-farm = the rest. Rural/urban: farm by PLFS farm self-employment earnings (workers of group "
        "01-03 by area from V1a x Table 20 self-employed share x mean API indicator 8 self-employment earnings, "
        "Q1-Q4 2023-24; the gap map's 100% rural is the sensitivity); non-farm by ASUSE 2023-24 surplus (GVA - "
        "emoluments) of the activity's categories by area (establishment location proxies the household's area; "
        "the categories of the V2a(b) record, e.g. T1-T5 for trade); mining, construction and utilities by PLFS "
        "groups 05-09, 41-43 and 35-39 self-employment earnings (workers x Table 20 self-employed share x API "
        "indicator 8, as for farm; ASUSE has no category for household utilities: E is only non-captive "
        "electricity and NIC 36-39 sits inside S15). Within an area: "
        "persons x IFPRI 2022/23 per-capita index (farm: crop land + agricultural capital; non-farm: "
        f"non-agricultural capital; T10 x T11), mapped with {xw_note}. Low confidence.",
    )  # fmt: skip
    for g in HH:
        for comp, vals in (("farm", f2_farm), ("nonfarm", f2_non)):
            if vals[g] > 0:
                entries.append(entry(g, "F_MIXD", "F2", vals[g], component=comp, prov_id=f2_pid, status="estimated",
                                     role="free", confidence="low"))  # fmt: skip

    # ---- F3a, F3b, F3c: household operating surplus ------------------------------------------------
    imp_key = lib.normalise(hh["c4a_imputed"])
    f3a = {g: va["dw_imp"] * imp_key[g] for g in HH}
    f3a_pid = ctx.prov(
        ref="F3a", status="estimated", inputs=sorted({*hh["c4a_pids"], va["pids"]["dwel"]}),
        source_id=_src(ctx, hh["c4a_pids"][0]),
        method="Gap map F3a: household imputed-rent operating surplus (V2a hh_dwelling_imputed total) keyed "
        "exactly like households' C4a imputed-rent consumption by group (each group's share of the C4a "
        "imputed_rent entries), so each group's imputed-rent income is proportional to its imputed-rent "
        "consumption; the levels differ (output vs surplus).",
    )  # fmt: skip
    fa_key = lib.normalise(hh["fixed_assets"])
    f3b = {g: va["dw_act"] * fa_key[g] for g in HH}
    f3b_pid = ctx.prov(
        ref="F3b", status="estimated", inputs=sorted({*hh["fa_pids"], va["pids"]["dwel"]}),
        source_id=_src(ctx, hh["fa_pids"][0]),
        method="Gap map F3b: actual rent received by household landlords (V2a hh_dwelling_actual total) keyed by "
        "owners of property, not tenants: households' AIDIS 2019 fixed-assets key by group (aidis_fixed_assets; "
        "stocks at 2018-06-30). Proxy: AIDIS tables on rented-out residential property are not located "
        "(labour_enterprise_surveys-2, -19). Low confidence.",
    )  # fmt: skip
    quasi = va["quasi"]
    q_area = {"rural": 0.0, "urban": 0.0}
    for a, v in sorted(quasi.items()):
        if v <= 0:
            continue
        ns = {s: _agg(asu, ASUSE_MAP[a], s, "nonprop") for s in AREAS}
        r = ns["rural"] / (ns["rural"] + ns["urban"])
        q_area["rural"] += v * r
        q_area["urban"] += v * (1 - r)
    f3c = lib.split_by_area(q_area["rural"], q_area["urban"], _shares(hh, idx["nonfarm"]))
    f3c_pid = ctx.prov(
        ref="F3c", status="estimated", inputs=sorted({*key_in, *va["asu_pids"], va["pids"]["quasi"]}),
        source_id=_src(ctx, pif[0]),
        method="Gap map F3c: surplus of household partnerships, trusts and co-operatives (V2a hh_quasi) by "
        "group. Rural/urban by ASUSE 2023-24 non-proprietary GVA of each activity's categories by area (the "
        "categories of the V2a(b) record, e.g. T1-T5 for trade); within an "
        "area by persons x the IFPRI 2022/23 non-agricultural capital index (T10 x T11), mapped with "
        f"{xw_note}. Low confidence.",
    )  # fmt: skip
    for g in HH:
        for ref, vals, pid in (("F3a", f3a, f3a_pid), ("F3b", f3b, f3b_pid), ("F3c", f3c, f3c_pid)):
            if vals[g] >= MIN_ENTRY:
                conf = "medium" if ref == "F3a" else "low"
                entries.append(entry(g, "F_GOSC", ref, vals[g], prov_id=pid, status="estimated", role="free",
                                     confidence=conf))  # fmt: skip
            elif vals[g] > 0:
                ctx.warn(f"{ref} {g}: {vals[g]:.4f} below Rs {MIN_ENTRY} crore, left out")
    # XR-22: per-group F3a bands (+-10%) around the prior F3a level, i.e. the prior F3a total x the prior C4a
    # imputed-rent share. A fixed-level band: it does not follow a change in the C4a shares or the F3a total in
    # balancing, so the share link itself is checked after balancing (plan s.8 item 3; verification V-F-9).
    for g in HH:
        if f3a[g] >= MIN_ENTRY:
            cons.append(constraint(f"f3a_band.{g.lower()}", "F3a", [g], ["F_GOSC"], f3a[g], prov_id=f3a_pid,
                                   tol_rel=0.10, kind="band", refs=["F3a"],
                                   description=f"F3a of {g} within 10% of its prior level (prior F3a total x its prior "
                                   "C4a imputed-rent share; XR-22). A fixed-level band, not a share link: the "
                                   "post-balancing share-drift report checks the shares"))  # fmt: skip
    f3_pid = ctx.prov(
        ref="F3",
        status="derived",
        inputs=list(va["p71c"]),
        method="Gap map F3 (constraint only): household-sector gross OS/MI = NAS 2026 Statement 7.1C "
        "total OS/MI + CFC; F2 (mixed income) + F3a + F3b + F3c must sum to it, so F_GOSC clears.",
    )
    cons.append(constraint("f2f3.hh_gross_os_mi", "F3", HH, ["F_MIXD", "F_GOSC"], va["hh_total"], prov_id=f3_pid,
                           tol_abs=CHECK_TOL, refs=["F2", "F3a", "F3b", "F3c"],
                           description="F2 + F3: household gross OS/MI (NAS 7.1C OS/MI + CFC)"))  # fmt: skip
    got = sum(f2_farm.values()) + sum(f2_non.values()) + sum(f3a.values()) + sum(f3b.values()) + sum(f3c.values())
    ctx.check("f2f3.total", "F2 + F3a + F3b + F3c vs NAS 7.1C household gross OS/MI", got, va["hh_total"],
              target_prov_id=va["hh_pid"], tol_abs=CHECK_TOL)  # fmt: skip
    f3c_share = sum(f3c.values()) / va["hh_total"]
    if not 0 <= f3c_share <= 0.05:
        ctx.warn(f"F3c share of household gross OS/MI {f3c_share:.4f} outside [0, 0.05]")

    # ---- factor_income_keys (incl. public_sector_wage_key) ----------------------------------------
    t35, p35 = _get(ctx, T35, [f"t35.worker_share.govt_public_sector.{s}.person" for s in AREAS], period=PLFS_P,
                    unit="percent", price_basis=None)  # fmt: skip
    pub = {g: f1a_reg[g] * t35[f"t35.worker_share.govt_public_sector.{'rural' if g.startswith('H_R') else 'urban'}"
                                ".person"] / 100.0 for g in HH}  # fmt: skip
    pub_pid = ctx.prov(
        ref="F1a", status="estimated", inputs=sorted({*p35, f1a_pid}), source_id=_src(ctx, p35[0]),
        method="public_sector_wage_key (CROSS_REVIEW s.8 item 5, for government R9a/R9b and fincorp R9c): each "
        "group's F1a regular-labour income x the PLFS 2023-24 Table 35 share of workers in government/public "
        "sector enterprises of its area (ps+ss). A proxy (the public share is not known by MPCE quintile); low "
        "confidence.",
    )  # fmt: skip
    key_pid = ctx.prov(
        ref="F1a", status="estimated", inputs=sorted({f1a_pid, f2_pid, f3a_pid, f3b_pid, f3c_pid}),
        source_id=_src(ctx, pif[0]),
        method="factor_income_keys: this block's household factor-income entries by group and factor type (F1a "
        "regular and casual labour, F2 farm and non-farm mixed income, F3a imputed rent, F3b actual rent, F3c "
        "partnership/trust surplus) as levels (Rs crore) and shares within each key, plus rural/urban totals; the "
        "same numbers as the entries, published for taxes (T3a), government (R9a) and fincorp (R9c keys). "
        "Sensitivity rows (report only): the IFPRI all-labour gradient for both labour factors (within-area "
        "shares), and the D2-19 mapping variants under their own record.",
    )  # fmt: skip
    keys = {"lreg": f1a_reg, "lcas": f1a_cas, "mixd_farm": f2_farm, "mixd_nonfarm": f2_non, "imputed_rent": f3a,
            "actual_rent": f3b, "quasi_corporate": f3c}  # fmt: skip
    krows = []
    for k, vals in keys.items():
        sh = lib.normalise(vals)
        for g in HH:
            krows.append((f"{k}.level.{g.lower()}", k, "level", g, vals[g], "INR_crore", key_pid))
            krows.append((f"{k}.share.{g.lower()}", k, "share", g, sh[g], "ratio", key_pid))
    psh = lib.normalise(pub)
    for g in HH:
        krows.append((f"public_sector_wage_key.level.{g.lower()}", "public_sector_wage_key", "level", g, pub[g],
                      "INR_crore", pub_pid))  # fmt: skip
        krows.append((f"public_sector_wage_key.share.{g.lower()}", "public_sector_wage_key", "share", g, psh[g],
                      "ratio", pub_pid))  # fmt: skip
    area_rows = [("lreg", reg_area), ("lcas", cas_area), ("mixd_nonfarm", nonfarm), ("quasi_corporate", q_area),
                 ("mixd_farm", {"rural": farm_r, "urban": farm - farm_r})]  # fmt: skip
    for k, d in area_rows:
        for s in AREAS:
            krows.append((f"{k}.area_total.{s}", k, "area_total", s, d[s], "INR_crore", key_pid))
    # sensitivities (report only): IFPRI labour_all key for both labour factors; farm MI 100% rural
    sens = lib.split_by_area(1.0, 1.0, _shares(hh, idx["labour_all"]))
    for g in HH:
        krows.append((f"sensitivity.labour_all_share.{g.lower()}", "sensitivity_labour_all", "area_share", g, sens[g],
                      "ratio", key_pid))  # fmt: skip
    # D2-19 sensitivities (report only): the IFPRI-keyed factors (F1a, F2, F3c) under the mapping not used and
    # under the HCES-MPCE-rescaled k = q variant; area totals, F3a and F3b as in the entries
    variants = ["k_eq_q" if IFPRI_MAPPING == "crosswalk" else "xwalk", "hces"]
    avail = {"xwalk": hh["xwalk_all"] is not None, "k_eq_q": True, "hces": hh["hces"] is not None}
    variants = [x for x in variants if avail[x]]
    # k = q is the entries' mapping (D2-19), so it has sensitivity rows only when the crosswalk is switched back on
    # (close-out V-F-12: the record names only the variants it publishes)
    kq_text = ("'k_eq_q': group k takes national quintile k's index; " if "k_eq_q" in variants else
                "k = q (group k takes national quintile k's index) is the entries' mapping (D2-19) and has no "
                "sensitivity rows; ")  # fmt: skip
    if variants:
        sens_pid = ctx.prov(
            ref="F1a", status="estimated",
            inputs=sorted({key_pid, *pif, *hh["pop_pids"], *hh["xw_all_pids"], *hh["hces_pids"]}),
            source_id=_src(ctx, pif[0]),
            method="Sensitivity rows of factor_income_keys (report only; DECISIONS D2-19): the household factor "
            "income keyed by IFPRI 2022/23 (F1a regular and casual labour, F2 farm and non-farm mixed income, F3c "
            "partnership/trust surplus) recomputed with other within-area mappings, holding every area total and "
            "F3a/F3b as in the entries. 'xwalk': I_g = sum_q x_gq I_q with households' hh_national_quintile_xwalk "
            "(the mapping CROSS_REVIEW XR-10 prescribed; it puts H_U4 and H_U5 both wholly in national q5); "
            f"{kq_text}'hces': k = q with IFPRI T11 spending per capita "
            "of quintile k replaced by the group's HCES 2023-24 MPCE (households' hces_total / pop_persons), i.e. "
            "I_g = T10 share of the factor in quintile k's income x MPCE_g, so the within-area gradient follows "
            "HCES. Levels (Rs crore) and within-area shares by key; '<variant>_factor_income' is the group total "
            "(F1a + F2 + F3a + F3b + F3c). Other blocks that use factors' keys (taxes, government, fincorp) are not "
            "recomputed. Low confidence.",
        )  # fmt: skip
        f3ab = {g: f3a[g] + f3b[g] for g in HH}
        sens_keys = (("lreg", "regular", reg_area), ("lcas", "casual", cas_area),
                     ("mixd_farm", "farm", {"rural": farm_r, "urban": farm - farm_r}),
                     ("mixd_nonfarm", "nonfarm", nonfarm), ("quasi_corporate", "nonfarm", q_area))  # fmt: skip
        for var in variants:
            tot = dict(f3ab)
            for k, ix, area_tot in sens_keys:
                sh = _variant_shares(hh, var, idx[ix], spend)
                lev = lib.split_by_area(area_tot["rural"], area_tot["urban"], sh)
                for g in HH:
                    s = "rural" if g.startswith("H_R") else "urban"
                    tot[g] += lev[g]
                    krows.append((f"sensitivity.{var}.{k}.level.{g.lower()}", f"sensitivity_{var}_{k}", "level", g,
                                  lev[g], "INR_crore", sens_pid))  # fmt: skip
                    krows.append((f"sensitivity.{var}.{k}.area_share.{g.lower()}", f"sensitivity_{var}_{k}",
                                  "area_share", g, sh[s][g], "ratio", sens_pid))  # fmt: skip
            for g in HH:
                krows.append((f"sensitivity.{var}.factor_income.level.{g.lower()}", f"sensitivity_{var}_factor_income",
                              "level", g, tot[g], "INR_crore", sens_pid))  # fmt: skip
        ctx.log(f"D2-19 sensitivity mappings published in factor_income_keys: {variants}")
    rows = [(sid, g, (key, meas), v, u, p) for sid, key, meas, g, v, u, p in krows]
    sats["factor_income_keys"] = _sat_keys(rows, ctx)
    ctx.log(
        f"F1a rural share regular {reg_area['rural'] / sum(reg_area.values()):.3f}, casual "
        f"{cas_area['rural'] / sum(cas_area.values()):.3f}; F2 farm rural {farm_r / farm:.3f}; non-farm rural "
        f"{nonfarm['rural'] / sum(nonfarm.values()):.3f}; F3c {f3c_share:.4f} of household gross OS/MI"
    )


# =============================================================================================
# satellites
# =============================================================================================


def _sat(ref: str, rows: list[tuple], ctx: BlockContext, description: str, *, dims: tuple[str, str],
         decimals: int) -> Satellite:  # fmt: skip
    """rows: (series_id, dim1, dim2, value, unit, prov_id); status is taken from the record."""
    recs = []
    for sid, d1, d2, v, u, pid in rows:
        recs.append({"series_id": sid, dims[0]: str(d1), dims[1]: str(d2), "value": float(v), "unit": u,
                     "status": ctx.provenance[pid]["status"], "prov_id": pid})  # fmt: skip
    schema = {"series_id": pl.String(), dims[0]: pl.String(), dims[1]: pl.String(), "value": pl.Float64(),
              "unit": pl.String(), "status": pl.String(), "prov_id": pl.String()}  # fmt: skip
    df = pl.DataFrame(recs, schema=schema, orient="row").sort("series_id")
    return Satellite(ref, df, description, decimals=decimals)


def _sat_keys(rows: list[tuple], ctx: BlockContext) -> Satellite:
    recs = [{"series_id": sid, "household_group": g, "key": km[0], "measure": km[1], "value": float(v), "unit": u,
             "status": ctx.provenance[pid]["status"], "prov_id": pid} for sid, g, km, v, u, pid in rows]  # fmt: skip
    schema = {"series_id": pl.String(), "household_group": pl.String(), "key": pl.String(), "measure": pl.String(),
              "value": pl.Float64(), "unit": pl.String(), "status": pl.String(), "prov_id": pl.String()}  # fmt: skip
    df = pl.DataFrame(recs, schema=schema, orient="row").sort("series_id")
    return Satellite(
        "F1a",
        df,
        "Household factor income by group and factor type (levels, shares within each key, "
        "area totals), incl. public_sector_wage_key; the F1a/F2/F3a/F3b/F3c entries as keys",
        decimals=9,
    )
