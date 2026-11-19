"""Independent verification of the SAM `government` block (Phase 2 verifier, 2026-09-30; SPEC s.3 rule 3).

This file does NOT import pipeline.sam (no block, helper, framework or spec code) and does not use polars.
Every expected number is recomputed here with DuckDB SQL plus plain Python / numpy from:
- data/clean/union_fiscal: Finance Accounts 2023-24 St 8 (receipts), St 9 (expenditure by head), IGAS-2
  grantee statement, Annual Financial Statement (revenue deficit, Public Account), Expenditure Profile St 6 / 7 / 18;
- data/clean/state_fiscal: RBI State Finances App I / II / IV (all States + UTs, accounts 2023-24), FC16
  subsidies (21 reporting States) and State Finance Accounts (MH 2235, MH 0853);
- data/clean/mospi_nas_2026: St 1.1, 1.9, 1.14, 4.2 (COFOG), 6.1, 7.1A/B/C; data/clean/io_tables: SUT use
  (GFCE by product); data/clean/external_sector: BoP invisibles (official transfers);
  data/clean/finsector_markets: PFRDA State-sector NPS employer contributions; data/clean/rbi_financial_accounts
  (FSF Centre -> State loans);
- the DEPENDS outputs the block legitimately reads: production's P9 entry on C_RPET, factors' F4b and F2 entries
  and `factor_income_keys` / `gg_centre_state_key` satellites, households' `hh_keys` (pop_persons);
- data/sam/2023-24/blocks/*_entries.parquet of all built blocks (double counting, prior imbalances) and
  capital_financial's `s4_fwtw_sam` satellite (K8e netting).

Coverage: a census of all 148 entries (158 before D2-20), all 12 constraint targets, the recomputable rows of the six satellites and
every provenance record (inputs resolve, statuses, source coverage). Findings: docs/phase2/verify/government.md
(V-GOV-n). A confirmed defect is a strict xfail with its id.

Expectations updated by the government builder on 2026-10-01, only where a finding was fixed (dispositions in
docs/phase2/issues/government.md, "Verification dispositions"): V-GOV-1 (R7x interest_states excludes the 14-day
ITB interest, Union MH 2049.01.116; its xfail is now an ordinary test), V-GOV-2 (the PADM seeds exclude public
works; its xfail is now an ordinary test) and V-GOV-7 (statutory bodies are GG: the Centre's K6 to K_NFPU is the
IGAS-2 PSU capital grants only, component `igas2_psu`). V-GOV-3 is not fixed (Checkpoint B) and stays a strict xfail.

Updated by the government builder on 2026-10-01 (second pass), only where a decision changed the pinned behaviour:
DECISIONS D2-20 (R9b = 0, variant 'none'; the Centre-only and Centre + States values are a memo in
gov_r9b_sensitivity: no R9b entry is expected, test_d25 ranks the variants around what is written) and the K3a
bridge repair the orchestrator asked for (issues government-2, -25, -27): no CFC step (V-GOV-3 is fixed, its strict
xfail is now an ordinary test), the Railways / Posts revenue accounts leave the Centre (public NFC departmental
enterprises in NAS), the urban local bodies' revenue surplus (FC16 cityfinance dump) is added to the States, and
the remainder is allocated by the NAS 4.1 NVA of the GG units outside the treasury accounts (local bodies +
autonomous institutions, the Centre's part = Union revenue grants to autonomous bodies capped at their NVA, as in
F4b). The recomputation below does all of that from clean data.

Re-verified on 2026-10-01 (wave C close-out) by a different agent (not the builder, the fixers or the original
verifier): every expectation the fixing agents changed (V-GOV-1, -2, -7; D2-20 R9b none; the K3a bridge repair; the
Wave C PM-KISAN entries and the 26 new constraint targets) was recomputed independently with separate DuckDB / numpy
code and confirmed; none was reverted. Added: the PM-KISAN D39 total check, the D2-5 evidence recomputation from the
entries, and two strict xfails for confirmed defects (V-GOV-11 MH 3006 left in the Centre's K3a bridge; V-GOV-12 the
PM-KISAN reclassification reverses DECISIONS D0-5 without a DECISIONS entry). Report: docs/phase2/verify/government.md,
section "Re-verification (wave C close-out, 2026-10-01)".

Updated by the close-out fixer (2026-10-01), only where a finding was fixed (dispositions in
docs/phase2/issues/government.md, "Close-out re-verification"): V-GOV-11 (MH 3006 is a departmental-enterprise head:
the K3a recomputation's regex and departmental net include it; its strict xfail is an ordinary test) and V-GOV-12
(DECISIONS D2-24 records PM-KISAN as R10; its strict xfail is an ordinary test).
"""

# ruff: noqa: E501  (long SQL / series ids are kept on one line)
from __future__ import annotations

from functools import cache
from pathlib import Path

import duckdb
import numpy as np
import pytest

pytestmark = [pytest.mark.quality, pytest.mark.sam]

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean"
SAMDIR = ROOT / "data" / "sam" / "2023-24"
BLOCKS = SAMDIR / "blocks"
GSAT = BLOCKS / "government_satellites"
TOL = 0.01  # Rs crore (entries are written to 6 decimals; the block's RAS converges to ~2e-4 crore)
YEAR = "2023-24"
HH = ["H_R1", "H_R2", "H_R3", "H_R4", "H_R5", "H_U1", "H_U2", "H_U3", "H_U4", "H_U5"]
GOV = ("G_CEN", "G_STA")
UNITS = ["mospi_nas_2026", "io_tables", "union_fiscal", "state_fiscal", "finsector_markets", "external_sector",
         "rbi_financial_accounts", "rbi_banking_corporate"]  # fmt: skip


def _p(path: Path) -> str:
    return path.as_posix()


@cache
def con() -> duckdb.DuckDBPyConnection:
    for f in ("government_entries", "government_constraints", "government_provenance", "government_checks"):
        if not (BLOCKS / f"{f}.parquet").exists():
            pytest.fail(f"{f}.parquet missing: run `uv run python -m pipeline sam government`")
    return duckdb.connect()


def _rows(sql: str, params: list | None = None) -> list[tuple]:
    return con().execute(sql, params or []).fetchall()


def _file(ds: str) -> str:
    unit = max((u for u in UNITS if ds.startswith(u + "_")), key=len)
    return _p(CLEAN / unit / f"{ds}.parquet")


def _vkey(v: str | None) -> str:
    v = str(v or "")
    return v + "-12-31" if len(v) == 4 else v


def val(ds: str, sid: str, period: str = YEAR) -> float:
    """One clean value in Rs crore: exactly one row of the latest vintage."""
    rows = _rows(f"select vintage, value from '{_file(ds)}' where series_id=? and period=? and unit='INR_crore'", [sid, period])
    assert rows, f"{ds}: {sid} {period} missing"
    top = max(_vkey(r[0]) for r in rows)
    sel = [r[1] for r in rows if _vkey(r[0]) == top]
    assert len(sel) == 1, f"{ds}: {sid} {period}: {len(sel)} rows in the latest vintage"
    return float(sel[0])


def pid(ds: str, sid: str, period: str = YEAR) -> str:
    rows = _rows(f"select vintage, prov_id from '{_file(ds)}' where series_id=? and period=?", [sid, period])
    top = max(_vkey(r[0]) for r in rows)
    return next(r[1] for r in rows if _vkey(r[0]) == top)


def fa8(s: str) -> float:
    return val("union_fiscal_fa_receipts", s)


def fa9(s: str) -> float:
    return val("union_fiscal_fa_expenditure", s)


def gia(s: str) -> float:
    return val("union_fiscal_fa_gia", f"gia.cash.{s}")


def sf1(item: str) -> float:
    return val("state_fiscal_rbi_sf_appendices", f"app1.total_revenue.{item}.in.all_states_uts.actuals")


def sf2(item: str) -> float:
    return val("state_fiscal_rbi_sf_appendices", f"app2.total_expenditure.{item}.in.all_states_uts.actuals")


def nas(stmt: str, s: str) -> float:
    return val(f"mospi_nas_2026_{stmt}", s)


def blk(name: str) -> str:
    return _p(BLOCKS / name)


# ------------------------------------------------------------------------------------------ block outputs
@cache
def entries() -> dict[tuple[str, str, str, str], tuple]:
    """(row, col, ref, component) -> (value, status, role, tol_rel, confidence, prov_id)."""
    return {(r[0], r[1], r[2], r[3]): r[4:] for r in _rows(
        f"select row, col, ref, component, value, status, role, tol_rel, confidence, prov_id from '{blk('government_entries.parquet')}'")}  # fmt: skip


@cache
def constraints() -> dict[str, tuple]:
    """constraint_id -> (ref, rows, cols, refs, components, target, tol_abs, tol_rel, kind, prov_id)."""
    return {r[0]: r[1:] for r in _rows(
        f"select constraint_id, ref, rows, cols, refs, components, target, tol_abs, tol_rel, kind, prov_id from '{blk('government_constraints.parquet')}'")}  # fmt: skip


@cache
def records() -> dict[str, tuple]:
    """prov_id -> (status, inputs list, method)."""
    return {r[0]: (r[1], [x for x in (r[2] or "").split(",") if x], r[3]) for r in _rows(
        f"select prov_id, status, inputs, method from '{blk('government_provenance.parquet')}'")}  # fmt: skip


def satv(name: str, series_id: str) -> float:
    rows = _rows(f"select value from '{_p(GSAT / (name + '.parquet'))}' where series_id=?", [series_id])
    assert len(rows) == 1, f"{name}: {series_id}: {len(rows)} rows"
    return float(rows[0][0])


def all_entries() -> str:
    return f"(select * from '{blk('*_entries.parquet')}')"


# ------------------------------------------------------------------------------------------ dependency keys
def _norm(d: dict[str, float]) -> dict[str, float]:
    tot = sum(d[h] for h in HH)
    return {h: d[h] / tot for h in HH}


@cache
def wage_key() -> dict[str, float]:
    f = blk("factors_satellites/factor_income_keys.parquet")
    return _norm(dict(_rows(f"select household_group, value from '{f}' where key='public_sector_wage_key' and measure='level'")))


@cache
def pop_key() -> dict[str, float]:
    f = blk("households_satellites/hh_keys.parquet")
    return _norm(dict(_rows(f"select household_group, value from '{f}' where key='pop_persons' and measure='level'")))


@cache
def nonfarm_key() -> dict[str, float]:
    f = blk("factors_entries.parquet")
    return _norm(dict(_rows(f"select row, value from '{f}' where ref='F2' and col='F_MIXD' and component='nonfarm'")))


@cache
def farm_key() -> dict[str, float]:
    """Wave C audit fix (government-30, 2026-10-01; added by the fixing agent, re-verified 2026-10-01): PM-KISAN key."""
    f = blk("factors_entries.parquet")
    return _norm(dict(_rows(f"select row, value from '{f}' where ref='F2' and col='F_MIXD' and component='farm'")))


@cache
def f4b() -> dict[str, float]:
    return dict(_rows(f"select row, value from '{blk('factors_entries.parquet')}' where ref='F4b' and col='F_GOSC'"))


# ------------------------------------------------------------------------------------------ recomputation
@cache
def parts() -> dict[str, float]:
    """Intermediate totals of the recomputation (each from clean data or a DEPENDS output)."""
    fe = _file("union_fiscal_fa_expenditure")
    p: dict[str, float] = {}
    p["t2b_i"] = fa9("fa9.3601.08.112") + fa9("fa9.3602.08.106")
    p["t2b_ii"] = (val("union_fiscal_afs", "afs.pa_disbursements.xi_goods_and_service_tax_compensation_fund")
                   + fa9("fa9.3601.08.904") + fa9("fa9.3602.08.904"))  # fmt: skip
    p["r2k"] = gia("state_governments.capital_assets") + gia("ut_governments.capital_assets")
    p["grants"] = sf1("ii.d-grants_from_the_centre")
    p["fc"] = sf1("ii.d.5-finance_commission_grants")
    met0306 = _rows(f"select sum(value) from '{fe}' where period='{YEAR}' and starts_with(series_id, 'fa9.3601.06.9') and item_label ilike '%met from%'")[0][0]
    p["mh3601_06_net"] = fa9("fa9.3601.06.total") - fa9("fa9.3601.06.797") - met0306
    p["css_outside"] = val("union_fiscal_exp_profile", "stat18.transfers_to_states_other_than_i_ii.under_centrally_sponsored_schemes_revenue") - p["mh3601_06_net"]
    p["others_cap_share"] = gia("others.capital_assets") / gia("others.total")
    p["nps_c"] = fa9("fa9.2071.01.117") + fa9("fa9.2071.01.902")
    p["cghs"] = fa9("fa9.2071.01.118")
    p["r9_c"] = fa9("fa9.2071.total") - p["nps_c"] - p["cghs"]
    p["r9_s"] = sf2("ii.e-pensions") - val("finsector_markets_pfrda_sg", "m7d.annual_contribution_employer.state_govt.current")
    p["r9b"] = (fa9("fa9.2071.01.total") - p["nps_c"] - p["cghs"]) * (1 - 18 / 39) + fa9("fa9.2071.02.total")
    p["rail"] = val("union_fiscal_afs", "afs.pa_disbursements.i_railway_funds")
    p["posts"] = fa9("fa9.3201.07.total") - fa9("fa9.3201.07.110")
    # R10 States: FC16 cash transfers + social security of the reporting States, grossed up twice
    fs = _file("state_fiscal_fc16_subsidies")
    sub = _rows(f"select series_id, value from '{fs}' where period='{YEAR}' and (regexp_matches(series_id, '^sub\\.cash_transfers\\.in-[a-z]+\\.gg_state$') or regexp_matches(series_id, '^sub\\.social_security\\.in-[a-z]+\\.gg_state$'))")
    rep = {s.split(".")[2][3:] for s, _ in sub}
    p["n_reporting"] = float(len(rep))
    p["r10_base"] = sum(x for _, x in sub)
    fsa = _file("state_fiscal_fc16_state_accounts")
    mh = dict(_rows(f"select series_id, value from '{fsa}' where period='{YEAR}' and starts_with(series_id, 'fa.revenue_expenditure.mh2235.in-')"))
    mh_all = sum(mh.values())
    p["g1"] = mh_all / sum(x for s, x in mh.items() if s.split("in-")[1] in rep)
    p["g2"] = sf2("i.a.9-social_security_and_welfare") / mh_all
    p["r10_s"] = p["r10_base"] * p["g1"] * p["g2"]
    p["ss_c"] = val("state_fiscal_fc16_subsidies", "sub.social_security.in.gg_centre")
    p9 = _rows(f"select value from '{blk('production_entries.parquet')}' where ref='P9' and row='T_PSUB' and col='C_RPET'")
    assert len(p9) == 1
    p["lpg"] = val("union_fiscal_exp_profile", "stat7.petroleum.lpg_subsidy") + p9[0][0]  # P9 is negative
    # R7x payer keys: NAS 7.1A/B/C OS(+MI) + CFC
    p["pub_min"] = nas("s7_1a", "s7_1a.mining.os.current") + nas("s7_1a", "s7_1a.mining.cfc.current")
    p["prv_min"] = nas("s7_1b", "s7_1b.mining.os.current") + nas("s7_1b", "s7_1b.mining.cfc.current")
    p["hh_min"] = nas("s7_1c", "s7_1c.mining.os_mi.current") + nas("s7_1c", "s7_1c.mining.cfc.current")
    p["pub_com"] = nas("s7_1a", "s7_1a.communication.os.current") + nas("s7_1a", "s7_1a.communication.cfc.current")
    p["prv_com"] = nas("s7_1b", "s7_1b.communication.os.current") + nas("s7_1b", "s7_1b.communication.cfc.current")
    p["mining"] = _rows(f"select sum(value) from '{fsa}' where period='{YEAR}' and starts_with(series_id, 'fa.revenue_receipts.mh0853.in-')")[0][0]
    p["pet_c"] = sum(fa8(f"fa8.0802.00.{m}") for m in ("102", "103", "106", "107", "109"))
    p["pet_s"] = sf1("ii.c.6.xi-petroleum")
    p["tel"] = fa8("fa8.1275.00.104") + fa8("fa8.1275.00.105")
    p["int_psu"] = fa8("fa8.0049.03.190") + fa8("fa8.0049.03.103")
    p["int_oth"] = fa8("fa8.0049.03.109") + fa8("fa8.0049.03.195")
    p["int_serv"] = fa8("fa8.0049.03.118")
    p["int_sta"] = sf1("ii.c.1-interest_receipts") - fa9("fa9.2049.01.116")  # V-GOV-1 fixed: 14-day ITB interest is intra-GG
    # K3a bridge (plan s.2.8 as repaired on 2026-10-01): gross saving, so no CFC step; departmental enterprises
    # (Railways MH 1001-1003 / 3001-3003, Posts MH 1201 / 3201) leave the Centre with their own fund lines; the urban
    # local bodies' revenue surplus is the States'; remainder by the NVA of the GG units outside the treasuries
    # close-out fixer (2026-10-01, V-GOV-11 fixed): MH 3006 'Appropriations from Railway Surplus' is the Railways' too
    de = "regexp_matches(series_id, '^fa9\\.(300[1-36]|3201)\\.')"
    p["t797"] = _rows(f"select sum(value) from '{fe}' where period='{YEAR}' and regexp_matches(series_id, '^fa9\\.[23][0-9]{{3}}\\.[0-9]{{2}}\\.797$') and not {de}")[0][0]
    p["tmet"] = _rows(f"select sum(value) from '{fe}' where period='{YEAR}' and regexp_matches(series_id, '^fa9\\.[23][0-9]{{3}}\\.') and item_label ilike '%met from%' and not {de}")[0][0]
    p["de_net"] = (sum(fa8(f"fa8.{m}.total") for m in ("1001", "1002", "1003", "1201"))
                   - sum(fa9(f"fa9.{m}.total") for m in ("3001", "3002", "3003", "3006", "3201")))  # fmt: skip
    p["cen_sub"] = (-val("union_fiscal_afs", "afs.cfi_rev_receipts.excess_of_disbursements_over_receipts_revenue_deficit")
                    + p["t797"] + p["tmet"] + val("union_fiscal_gcca", "stat6.grand_total") - p["t2b_ii"] - p["de_net"])  # fmt: skip
    p["sta_treasury"] = (val("state_fiscal_rbi_sf_appendices", "app4.a-surplus_deficit_on_revenue_account.in.all_states_uts.actuals")
                         - p["r2k"] + p["t2b_ii"] + sf2("ii.c.1-appropriation_for_reduction_or_avoidance_of_debt"))  # fmt: skip
    ulb = "state_fiscal_ulb_cityfinance"
    p["ulb"] = (val(ulb, "ulb.total_revenues.in.all_ulbs_in_dump") - val(ulb, "ulb.total_revenue_expenditure.in.all_ulbs_in_dump")
                - gia("urban_local_bodies.capital_assets"))  # fmt: skip
    p["ulb_centre_initiatives"] = val(ulb, "ulb.grants_for_centre_s_initiatives.in.all_ulbs_in_dump")
    p["sta_sub"] = p["sta_treasury"] + p["ulb"]
    p["nas_saving"] = nas("s1_9", "s1_9.general_government.current")
    p["rem"] = p["nas_saving"] - p["cen_sub"] - p["sta_sub"]
    aut, loc = nas("s4_1", "s4_1.autonomous_institutions.current"), nas("s4_1", "s4_1.local_bodies.current")
    aut_c = min(gia("autonomous_bodies.total") - gia("autonomous_bodies.capital_assets"), aut)
    p["sh_c"] = aut_c / (aut + loc)
    p["prior_c"] = p["cen_sub"] + p["rem"] * p["sh_c"]
    p["prior_s"] = p["sta_sub"] + p["rem"] * (1 - p["sh_c"])
    p["m_c"] = abs(p["rem"] * p["sh_c"])
    p["m_s"] = abs(p["rem"] * (1 - p["sh_c"])) + p["ulb_centre_initiatives"]
    # K6
    p["bop_pay"] = val("external_sector_invisibles_annual", "invis.inr.official_transfers.payments.current")
    p["gg_row_net"] = nas("s6_1", "s6_1.capital_transfers_to_general_government_from_the_rest_of_the.current")

    def ct(f: str) -> float:
        return nas("s4_2", f"s4_2.capital_transfer.{f}.current")

    p["k_hh"] = ct("06") + ct("10") + ct("09") + ct("07") + ct("08") + ct("04.agri")
    p["k_nfpu"] = (ct("04.energy") + ct("04.transport_comm") + ct("04.mining_mfg_constr") + ct("04.water_supply")
                   + ct("04.other") + ct("04.admin") + ct("03") + ct("01") - p["bop_pay"])  # fmt: skip
    p["cofog_k"] = ct("total")
    return p


@cache
def c2a() -> dict[str, tuple[float, float]]:
    """5 x 2 RAS: seeds = cash functional revenue expenditure, rows = SUT GFCE, Centre column = F4b share x own output."""
    sut = {k: val("io_tables_sut_use", f"use.gfce.sut_{k}.current") for k in ("p127", "p130", "p131", "p151", "p152", "p153")}
    tgt = {"C_PADM": sut["p151"], "C_EDUC": sut["p152"], "C_HLTH": sut["p153"], "C_CNST": sut["p127"],
           "C_UTIL": sut["p130"] + sut["p131"]}  # fmt: skip
    # V-GOV-2 fixed: public works (Centre MH 2059, States ii.d.iv) are seeded once, in CNST, not also inside PADM
    seed_c = {"C_PADM": sum(fa9(f"fa9.section.{s}") for s in ("organs_of_state", "fiscal_services", "administrative_services", "defence_services")) - fa9("fa9.2059.total"),
              "C_EDUC": sum(fa9(f"fa9.{m}.total") for m in ("2202", "2203", "2204", "2205")),
              "C_HLTH": fa9("fa9.2210.total") + fa9("fa9.2211.total"),
              "C_CNST": fa9("fa9.3054.total") + fa9("fa9.2059.total"),
              "C_UTIL": 0.0}  # fmt: skip
    seed_s = {"C_PADM": sf2("ii.a-organs_of_state") + sf2("ii.b-fiscal_services") + sf2("ii.d-administrative_services")
              + sf2("ii.f-miscellaneous_general_services") - sf2("ii.f.payment_on_account_of_state_lo-payment_on_account_of_state_lotteries")
              - sf2("ii.d.iv-public_works"),
              "C_EDUC": sf2("i.a.1-education_sports_art_and_culture"),
              "C_HLTH": sf2("i.a.2-medical_and_public_health") + sf2("i.a.3-family_welfare"),
              "C_CNST": sf2("i.b.7.i-roads_and_bridges") + sf2("ii.d.iv-public_works"),
              "C_UTIL": sf2("i.a.4-water_supply_and_sanitation")}  # fmt: skip
    own = sum(tgt.values())
    share = f4b()["G_CEN"] / (f4b()["G_CEN"] + f4b()["G_STA"])
    rows = list(tgt)
    x = np.array([[seed_c[r], seed_s[r]] for r in rows], dtype=float)
    rt = np.array([tgt[r] for r in rows])
    ctot = np.array([share * own, own - share * own])
    for _ in range(20000):
        x *= (rt / x.sum(1))[:, None]
        x *= (ctot / x.sum(0))[None, :]
        if np.abs(x.sum(1) - rt).max() < 1e-9:
            break
    out = {r: (float(x[i, 0]), float(x[i, 1])) for i, r in enumerate(rows)}
    out["_seed"] = (seed_c, seed_s)  # type: ignore[assignment]
    out["_target"] = (tgt, share * own)  # type: ignore[assignment]
    return out


@cache
def expected() -> dict[tuple[str, str, str, str], float]:
    p = parts()
    E: dict[tuple[str, str, str, str], float] = {}
    for comp, s in {"cgst": "0005.00", "corporation_tax": "0020.00", "income_tax": "0021.00", "customs": "0037.00",
                    "union_excise": "0038.01", "service_tax": "0044.00", "other_commodity_taxes": "0045.00"}.items():  # fmt: skip
        E["G_STA", "G_CEN", "R1", comp] = -fa8(f"fa8.{s}.901")
    E["G_STA", "G_CEN", "T2b", "compensation_grants"] = p["t2b_i"]
    E["G_STA", "G_CEN", "T2b", "cess_loan_recovery"] = p["t2b_ii"]
    E["K_GSTA", "K_GCEN", "R2k", "igas2_capital"] = p["r2k"]
    E["G_STA", "G_CEN", "R2", "fc_grants"] = p["fc"]
    E["G_STA", "G_CEN", "R2", "css_and_other"] = p["grants"] - p["fc"] - p["t2b_i"] - p["r2k"]
    E["G_STA", "G_CEN", "R2", "css_outside_treasury"] = p["css_outside"] * (1 - p["others_cap_share"])
    E["K_GSTA", "K_GCEN", "R2k", "css_outside_treasury"] = p["css_outside"] * p["others_cap_share"]
    E["G_CEN", "E_RBI", "R6", "cash_basis"] = fa8("fa8.0050.00.106")
    E["G_CEN", "E_NFPU", "R7", "public_undertakings"] = fa8("fa8.0050.00.101") + fa8("fa8.0050.00.200")
    E["G_CEN", "E_BANK", "R7", "banks"] = fa8("fa8.0050.00.108") + fa8("fa8.0050.00.109")
    E["G_CEN", "E_INSP", "R7", "lic"] = fa8("fa8.0050.00.107")
    E["G_STA", "E_NFPU", "R7", "state_enterprises"] = sf1("ii.c.2-dividends_and_profits")
    wk, pk, nk = wage_key(), pop_key(), nonfarm_key()
    for h in HH:
        E[h, "G_CEN", "R9a", "pensions"] = p["r9_c"] * wk[h]
        E[h, "G_STA", "R9a", "pensions"] = p["r9_s"] * wk[h]
        E[h, "E_NFPU", "R9d", "railways"] = p["rail"] * wk[h]
        E[h, "E_NFPU", "R9d", "posts"] = p["posts"] * wk[h]
        E[h, "G_STA", "R10", "cash_schemes"] = p["r10_s"] * pk[h]
        E[h, "G_CEN", "R10", "social_security"] = p["ss_c"] * pk[h]
        E[h, "G_CEN", "R10", "lpg_dbt"] = p["lpg"] * pk[h]
        E[h, "G_CEN", "R10", "pm_kisan"] = fa9("fa9.2401.00.130") * farm_key()[h]  # Wave C (government-30)
        E["G_CEN", h, "R7x", "interest_govt_servants"] = p["int_serv"] * wk[h]
        E["G_STA", h, "R7x", "mining_royalties"] = p["mining"] * p["hh_min"] / (p["pub_min"] + p["prv_min"] + p["hh_min"]) * nk[h]
    E["E_NFPU", "G_CEN", "R18", "psu_revenue_grants"] = gia("public_sector_undertakings.total") - gia("public_sector_undertakings.capital_assets")
    E["E_NFPR", "G_CEN", "R18", "coop_revenue_grants"] = gia("cooperatives.total") - gia("cooperatives.capital_assets")
    E["E_INSP", "G_CEN", "R18", "lic_pension_subsidy"] = val("union_fiscal_exp_profile", "stat7.interest_subsidies.interest_subsidy_to_lic_for_pension_plan_for_senior_citizens")
    tmin = p["pub_min"] + p["prv_min"] + p["hh_min"]
    corp = p["pub_min"] + p["prv_min"]
    E["G_STA", "E_NFPU", "R7x", "mining_royalties"] = p["mining"] * p["pub_min"] / tmin
    E["G_STA", "E_NFPR", "R7x", "mining_royalties"] = p["mining"] * p["prv_min"] / tmin
    E["G_CEN", "E_NFPU", "R7x", "petroleum_rent"] = p["pet_c"] * p["pub_min"] / corp
    E["G_CEN", "E_NFPR", "R7x", "petroleum_rent"] = p["pet_c"] * p["prv_min"] / corp
    E["G_STA", "E_NFPU", "R7x", "petroleum_royalties"] = p["pet_s"] * p["pub_min"] / corp
    E["G_STA", "E_NFPR", "R7x", "petroleum_royalties"] = p["pet_s"] * p["prv_min"] / corp
    com = p["pub_com"] + p["prv_com"]
    E["G_CEN", "E_NFPU", "R7x", "telecom_licence"] = p["tel"] * p["pub_com"] / com
    E["G_CEN", "E_NFPR", "R7x", "telecom_licence"] = p["tel"] * p["prv_com"] / com
    E["G_CEN", "E_NFPU", "R7x", "interest_psu"] = p["int_psu"]
    E["G_CEN", "E_NFPR", "R7x", "interest_other_parties"] = p["int_oth"]
    E["G_STA", "E_NFPU", "R7x", "interest_states"] = p["int_sta"]
    E["C_CROP", "G_CEN", "C2a", "food_subsidy"] = val("io_tables_sut_use", "use.gfce.sut_p001.current") + val("io_tables_sut_use", "use.gfce.sut_p002.current")
    for r, (xc, xs) in c2a().items():
        if r.startswith("_"):
            continue
        if xc != 0:
            E[r, "G_CEN", "C2a", "total"] = xc
        E[r, "G_STA", "C2a", "total"] = xs
    for kacct, g, prior, m in (("K_GCEN", "G_CEN", p["prior_c"], p["m_c"]), ("K_GSTA", "G_STA", p["prior_s"], p["m_s"])):
        E[kacct, g, "K3a", "saving_pos"] = m if prior < 0 else prior + m
        E[kacct, g, "K3a", "saving_neg"] = prior - m if prior < 0 else -m
    E["K_ROW", "K_GCEN", "K6", "gg_payments"] = p["bop_pay"]
    E["K_GCEN", "K_ROW", "K6", "gg_receipts"] = p["bop_pay"] + p["gg_row_net"]
    E["K_HH", "K_ROW", "K6", "nongg_net"] = nas("s6_1", "s6_1.capital_transfers_to_corporations_households_and_npishs_net.current")
    E["K_ROW", "K_NFPR", "K6", "npnfa"] = nas("s6_1", "s6_1.acquisitions_less_disposal_of_non_produced_non_financial_ass.current")
    psu_stat = gia("public_sector_undertakings.capital_assets")  # V-GOV-7 fixed: statutory bodies are GG (A-K6-4)
    E["K_NFPU", "K_GCEN", "K6", "igas2_psu"] = psu_stat
    E["K_HH", "K_GCEN", "K6", "igas2_ngos"] = gia("ngos.capital_assets")
    E["K_NFPR", "K_GCEN", "K6", "igas2_cooperatives"] = gia("cooperatives.capital_assets")
    E["K_HH", "K_GSTA", "K6", "cofog_residual"] = p["k_hh"] - gia("ngos.capital_assets")
    E["K_NFPU", "K_GSTA", "K6", "cofog_residual"] = p["k_nfpu"] - psu_stat - gia("cooperatives.capital_assets")
    E["K_GSTA", "I_LOAN", "K8e", "gst_b2b_repayment"] = -p["t2b_ii"]
    E["I_LOAN", "K_GCEN", "K8e", "gst_b2b_repayment"] = -p["t2b_ii"]
    return E


# ================================================================================================ entries
def test_entry_census_keys_match():
    built, exp = set(entries()), set(expected())
    assert not (exp - built), f"expected entries missing from the block: {sorted(exp - built)}"
    assert not (built - exp), f"block entries the recomputation does not produce: {sorted(built - exp)}"
    assert len(built) == 158  # 158 before D2-20 removed the 10 R9b entries; +10 R10 pm_kisan (Wave C, government-30)


def test_entry_census_values_match():
    bad = [(k, entries()[k][0], x) for k, x in expected().items() if abs(entries()[k][0] - x) > TOL]
    assert not bad, f"{len(bad)} entries differ by more than Rs {TOL} crore: {bad[:10]}"


def test_ref_totals_match_sources():
    p = parts()
    e = entries()

    def tot(ref, col=None, comp=None, row=None):
        return sum(v[0] for k, v in e.items() if k[2] == ref and (col is None or k[1] == col)
                   and (comp is None or k[3] == comp) and (row is None or k[0] == row))  # fmt: skip

    assert tot("R1") == pytest.approx(val("union_fiscal_afs", "afs.cfi_rev_receipts.state_s_share_excluded_from_the_consolidated_fund"), abs=0.01)
    assert tot("R2", comp="fc_grants") + tot("R2", comp="css_and_other") + tot("T2b", comp="compensation_grants") + tot("R2k", comp="igas2_capital") == pytest.approx(p["grants"], abs=0.01)
    assert tot("R6") + tot("R7", row="G_CEN") == pytest.approx(fa8("fa8.0050.total"), abs=0.01)
    assert tot("R9a", col="G_CEN") == pytest.approx(p["r9_c"], abs=0.01)
    assert tot("R9a", col="G_STA") == pytest.approx(p["r9_s"], abs=0.01)
    assert tot("C2a") == pytest.approx(val("io_tables_sut_use", "use.gfce.total.current"), abs=0.01)
    assert tot("C2a") == pytest.approx(nas("s1_14", "s1_14.gg.final_consumption_expenditure.current"), abs=1.0)
    assert tot("K3a") == pytest.approx(p["nas_saving"], abs=0.01)
    assert tot("K6", row="K_GCEN") - tot("K6", col="K_GCEN", row="K_ROW") == pytest.approx(p["gg_row_net"], abs=0.01)
    k6_paid = sum(v[0] for k, v in e.items() if k[2] == "K6" and k[1] in ("K_GCEN", "K_GSTA"))
    assert k6_paid - p["cofog_k"] == pytest.approx(-nas("s4_2", "s4_2.capital_transfer.05.current"), abs=0.01)  # only the dropped 05 (-436.19)


def test_statuses_roles_confidence():
    e = entries()
    fixed = {("R1", None), ("R2", "fc_grants"), ("T2b", None), ("R6", None), ("R7", None), ("K8e", None),
             ("C2a", "food_subsidy"), ("K6", "gg_payments"), ("K6", "gg_receipts"), ("K6", "nongg_net"), ("K6", "npnfa")}  # fmt: skip
    for (row, col, ref, comp), (_v, status, role, tol, conf, _) in e.items():
        is_fixed = (ref, None) in fixed or (ref, comp) in fixed
        if is_fixed:
            assert role == "fixed" and tol is None and conf is None, (row, col, ref, comp, role)
        elif (ref, comp) == ("R2", "css_and_other"):
            assert role == "anchored" and tol == pytest.approx(0.10) and status == "derived"
        else:
            assert role == "free" and conf in ("low", "medium", "high"), (row, col, ref, comp, role, conf)
        if ref in ("R9a", "R9b", "R9d", "R10", "R7x", "K3a") or (ref, comp) in (("R2", "css_outside_treasury"), ("R2k", "css_outside_treasury"), ("K6", "cofog_residual")):
            assert status == "estimated" and (role != "free" or conf == "low"), (row, col, ref, comp, status, conf)
        if ref == "C2a" and comp == "total":
            assert status == "estimated"
            assert conf == ("medium" if row in ("C_PADM", "C_EDUC", "C_HLTH") else "low"), (row, col, conf)
        if ref in ("R1",) or (ref, comp) in (("R2", "fc_grants"), ("T2b", "compensation_grants"), ("R6", "cash_basis"), ("K6", "gg_payments")):
            assert status == "official", (row, col, ref, comp, status)


def test_signs():
    for (row, col, ref, comp), (v, *_rest) in entries().items():
        if ref == "K8e" or (ref == "K3a" and comp == "saving_neg"):
            assert v < 0, (row, col, ref, comp, v)
        else:
            assert v > 0, (row, col, ref, comp, v)


def test_no_r15_r16_and_no_excluded_transfers():
    refs = {k[2] for k in entries()}
    assert "R15" not in refs and "R16" not in refs
    comps = {k[3] for k in entries() if k[2] in ("R10", "R18")}
    # PM-KISAN is R10 pm_kisan since the Wave C audit fix (government-30): NAS 4.2 books it as a current transfer
    assert not any(w in c for c in comps - {"pm_kisan"} for w in ("kisan", "miss", "food", "fertil"))


# ================================================================================================ constraints
def test_constraint_targets_recomputed():
    p, c = parts(), constraints()
    want = {
        "gov.c2.total": (nas("s1_14", "s1_14.gg.final_consumption_expenditure.current"), "band", 1.0, 0.0, "C2a"),
        "gov.c2a.centre_own_output": (c2a()["_target"][1], "band", 0.0, 0.10, "C2a"),
        "gov.cofog.capital_transfers": (p["cofog_k"], "band", 0.0, 0.05, "K6"),
        "gov.grants.state_receipts": (p["grants"], "band", 0.0, 0.005, "R2,R2k,T2b"),
        "gov.k3.gg_saving": (p["nas_saving"], "equal", 0.5, 0.0, "K3a"),
        "gov.r1.devolution": (-sum(fa8(f"fa8.{s}.901") for s in ("0005.00", "0020.00", "0021.00", "0032.00", "0037.00", "0038.01", "0044.00", "0045.00")), "equal", 0.5, 0.0, "R1"),
        "gov.r7.union": (fa8("fa8.0050.total") - fa8("fa8.0050.00.106"), "equal", 0.5, 0.0, "R7"),
        "gov.r7x.g_cen": (p["int_psu"] + p["int_oth"] + p["int_serv"] + p["pet_c"] + p["tel"], "band", 0.0, 0.05, "R7x"),
        "gov.r7x.g_sta": (p["int_sta"] + p["mining"] + p["pet_s"], "band", 0.0, 0.05, "R7x"),
        "gov.r9.centre": (p["r9_c"], "band", 0.0, 0.02, "R9a"),
        "gov.r9.states": (p["r9_s"], "band", 0.0, 0.03, "R9a"),
        "gov.t2b.cess_uses": (p["t2b_i"] + p["t2b_ii"], "equal", 0.5, 0.0, "T2b"),
    }
    # Wave C audit fix (2026-10-01; added by the fixing agent; re-verified by a different agent on 2026-10-01 with
    # independent code, all 26 targets equal): published totals the balancing had moved freely are declared, each
    # target recomputed here from clean data
    e = expected()
    want |= {
        "gov.cofog.current_transfers": (nas("s4_2", "s4_2.current_transfer.total.current"), "band", 0.0, 0.05,
                                        "R10,R18,R9a"),
        "gov.r9d.railways": (p["rail"], "band", 0.0, 0.10, "R9d"),
        "gov.r9d.posts": (p["posts"], "band", 0.0, 0.10, "R9d"),
        "gov.r2.css_outside_treasury": (p["css_outside"], "band", 0.0, 0.10, "R2,R2k"),
        "gov.r18.psu_revenue_grants": (e["E_NFPU", "G_CEN", "R18", "psu_revenue_grants"], "band", 0.0, 0.10, "R18"),
        "gov.r18.coop_revenue_grants": (e["E_NFPR", "G_CEN", "R18", "coop_revenue_grants"], "band", 0.0, 0.10, "R18"),
        "gov.r10.pm_kisan": (fa9("fa9.2401.00.130"), "band", 0.0, 0.05, "R10"),
        "gov.r10.lpg_dbt": (p["lpg"], "band", 0.0, 0.05, "R10"),
        "gov.r10.social_security": (p["ss_c"], "band", 0.0, 0.10, "R10"),
    }  # fmt: skip
    # R7x: one band per published line (+-5%) and one per payer sector of a multi-payer line (+-25%)
    for (gov, payer, ref, comp), v in e.items():
        if ref != "R7x":
            continue
        line = f"gov.r7x.{gov.lower()}.{comp}"
        want.setdefault(line, [0.0, "band", 0.0, 0.05, "R7x"])[0] += v
        sec = "hh" if payer.startswith("H_") else payer.lower()
        want.setdefault(f"{line}.{sec}", [0.0, "band", 0.0, 0.25, "R7x"])[0] += v
    for cid in [k for k in want if k.startswith("gov.r7x.") and k.count(".") == 4]:
        line = cid.rsplit(".", 1)[0]
        if sum(1 for k in want if k.startswith(line + ".") and k.count(".") == 4) == 1:
            del want[cid]  # a single-payer line has no payer band
    want = {k: tuple(v) for k, v in want.items()}
    assert set(c) == set(want)
    for cid, (target, kind, tol_abs, tol_rel, refs) in want.items():
        ref, rows, cols, crefs, comps, t, ta, tr, k, _ = c[cid]
        assert t == pytest.approx(target, abs=0.01), (cid, t, target)
        assert (k, ta, tr, crefs) == (kind, pytest.approx(tol_abs), pytest.approx(tol_rel), refs), (cid, k, ta, tr, crefs)
    # XR-20: the treasury receipts constraint excludes cess_loan_recovery and css_outside_treasury
    assert set(c["gov.grants.state_receipts"][4].split(",")) == {"compensation_grants", "css_and_other", "fc_grants", "igas2_capital"}


def test_constraints_hold_on_assembled_prior():
    """Every government constraint holds on the prior of all built blocks (none of them binds before balancing)."""
    for cid, (_ref, rows, cols, refs, comps, target, tol_abs, tol_rel, _kind, _) in constraints().items():
        rl = ",".join(f"'{x}'" for x in rows.split(","))
        cl = ",".join(f"'{x}'" for x in cols.split(","))
        sql = f"select coalesce(sum(value), 0) from {all_entries()} where row in ({rl}) and col in ({cl})"
        if refs:
            sql += " and ref in (" + ",".join(f"'{x}'" for x in refs.split(",")) + ")"
        if comps:
            sql += " and component in (" + ",".join(f"'{x}'" for x in comps.split(",")) + ")"
        s = _rows(sql)[0][0]
        tol = max(tol_abs, tol_rel * abs(target))
        assert abs(s - target) <= tol + 1e-6, (cid, s, target, tol)


def test_production_gfce_targets_hold_on_c2a():
    f = blk("production_constraints.parquet")
    for cid, target, tol in _rows(f"select constraint_id, target, tol_abs from '{f}' where starts_with(constraint_id, 'gfce.') and target <> 0"):
        c = cid.split(".", 1)[1].upper()
        s = sum(v[0] for k, v in entries().items() if k[0] == c and k[2] == "C2a")
        assert abs(s - target) <= tol, (cid, s, target)


# ================================================================================================ satellites
def test_fiscal_bridge_satellite():
    p = parts()
    assert satv("gov_fiscal_bridge", "centre.fund_transfers_797") == pytest.approx(p["t797"], abs=0.01)
    assert satv("gov_fiscal_bridge", "centre.met_from_funds") == pytest.approx(p["tmet"], abs=0.01)
    assert satv("gov_fiscal_bridge", "centre.subtotal") == pytest.approx(p["cen_sub"], abs=0.01)
    assert satv("gov_fiscal_bridge", "states.subtotal") == pytest.approx(p["sta_sub"], abs=0.01)
    assert satv("gov_fiscal_bridge", "unexplained_remainder") == pytest.approx(p["rem"], abs=0.01)
    assert satv("gov_fiscal_bridge", "prior.g_cen") == pytest.approx(p["prior_c"], abs=0.01)
    assert satv("gov_fiscal_bridge", "prior.g_sta") == pytest.approx(p["prior_s"], abs=0.01)
    assert satv("gov_fiscal_bridge", "centre.less_departmental_enterprises_net") == pytest.approx(-p["de_net"], abs=0.01)
    assert satv("gov_fiscal_bridge", "states.treasury_subtotal") == pytest.approx(p["sta_treasury"], abs=0.01)
    assert satv("gov_fiscal_bridge", "states.ulb_revenue_surplus") == pytest.approx(p["ulb"], abs=0.01)
    assert satv("gov_fiscal_bridge", "remainder_share_centre") == pytest.approx(p["sh_c"], abs=1e-9)
    e = entries()
    assert e["K_GCEN", "G_CEN", "K3a", "saving_pos"][0] + e["K_GCEN", "G_CEN", "K3a", "saving_neg"][0] == pytest.approx(p["prior_c"], abs=0.01)
    assert e["K_GSTA", "G_STA", "K3a", "saving_pos"][0] + e["K_GSTA", "G_STA", "K3a", "saving_neg"][0] == pytest.approx(p["prior_s"], abs=0.01)


def test_grants_bridge_satellite():
    p = parts()
    fe = _file("union_fiscal_fa_expenditure")

    def net(mh: str) -> float:
        t797 = _rows(f"select sum(value) from '{fe}' where period='{YEAR}' and regexp_matches(series_id, '^fa9\\.{mh}\\.[0-9]{{2}}\\.797$')")[0][0]
        met = _rows(f"select sum(value) from '{fe}' where period='{YEAR}' and starts_with(series_id, 'fa9.{mh}.') and item_label ilike '%met from%'")[0][0]
        return fa9(f"fa9.{mh}.total") - t797 - met

    assert satv("gov_grants_bridge", "mh3601.net_releases") == pytest.approx(net("3601"), abs=0.01)
    assert satv("gov_grants_bridge", "mh3602.net_releases") == pytest.approx(net("3602"), abs=0.01)
    assert satv("gov_grants_bridge", "gap_union_minus_states") == pytest.approx(net("3601") + net("3602") - p["grants"], abs=0.01)
    assert abs(net("3601") + net("3602") - p["grants"]) <= 0.001 * p["grants"]  # H9 closes within 0.1%
    igas_state = gia("state_governments.total") + val("union_fiscal_fa_gia", "gia.in_kind.state_governments.total")
    fc_local = fa9("fa9.3601.07.102") + fa9("fa9.3601.07.103") + fa9("fa9.3601.07.106")
    assert satv("gov_grants_bridge", "gap_igas2_plus_fc_minus_mh3601") == pytest.approx(igas_state + fc_local - net("3601"), abs=0.01)
    assert satv("gov_grants_bridge", "css_outside_treasury") == pytest.approx(p["css_outside"], abs=0.01)
    assert satv("gov_grants_bridge", "t2b_cess_loan_recovery") == pytest.approx(p["t2b_ii"], abs=0.01)


def test_c2a_keys_and_r9b_satellites():
    seed_c, seed_s = c2a()["_seed"]  # type: ignore[misc]
    for c in seed_c:
        assert satv("gov_c2a_keys", f"seed.{c.lower()}.g_cen") == pytest.approx(seed_c[c], abs=0.01)
        assert satv("gov_c2a_keys", f"seed.{c.lower()}.g_sta") == pytest.approx(seed_s[c], abs=0.01)
    assert satv("gov_c2a_keys", "centre_column_target") == pytest.approx(c2a()["_target"][1], abs=0.01)
    p = parts()
    assert satv("gov_r9b_sensitivity", "chosen") == pytest.approx(0.0, abs=1e-9)  # D2-20: variant 'none' written
    assert satv("gov_r9b_sensitivity", "variant.centre_only.r9b") == pytest.approx(p["r9b"], abs=0.01)
    assert satv("gov_r9b_sensitivity", "memo.centre_only.g_cen") == pytest.approx(p["r9b"], abs=0.01)
    states = p["r9_s"] * (1 - 18 / 39)
    assert satv("gov_r9b_sensitivity", "formula.states_uniform_k") == pytest.approx(states, abs=0.01)


def test_r7x_items_satellite_partitions_the_heads():
    """Included + excluded Union items = MH 0049.03 + MH 0802 + MH 1275 totals + interest from States/UTs."""
    f = _p(GSAT / "gov_r7x_items.parquet")
    cen = _rows(f"select sum(value) from '{f}' where government='G_CEN'")[0][0]
    heads = fa8("fa8.0049.03.total") + fa8("fa8.0802.total") + fa8("fa8.1275.total") + fa8("fa8.0049.01.total") + fa8("fa8.0049.02.total")
    assert cen == pytest.approx(heads, abs=0.01)
    sta = _rows(f"select sum(value) from '{f}' where government='G_STA' and status_note='included'")[0][0]
    assert sta == pytest.approx(constraints()["gov.r7x.g_sta"][5], abs=0.01)


# ================================================================================================ provenance
@cache
def clean_prov_ids() -> set[str]:
    out: set[str] = set()
    for f in CLEAN.glob("*/_provenance.parquet"):
        out |= {r[0] for r in _rows(f"select prov_id from '{_p(f)}'")}
    return out


def test_provenance_resolves_and_statuses_match():
    sam = dict(_rows(f"select prov_id, status from '{_p(SAMDIR / '_provenance.parquet')}'"))
    recs = records()
    # 53 + 4 of the Wave C audit fix: R10 pm_kisan, the NAS 4.2 COFOG constraint target, the R9d totals and the
    # outside-treasury CSS total (the R7x line bands and R18 / R10 line bands reuse their entries' records)
    assert len(recs) == 57
    for p_id, (status, inputs, method) in recs.items():
        assert p_id in sam, p_id
        assert method and len(method) > 40, p_id
        assert inputs, p_id
        for x in inputs:
            assert x in clean_prov_ids() or x in sam, (p_id, x)
            if status == "official" and x.startswith("sam_"):
                assert sam[x] == "official", (p_id, x, sam[x])
    for k, (_v, status, *_r, pv) in entries().items():
        assert pv in recs and recs[pv][0] == status, (k, pv)
    used = {v[-1] for v in entries().values()} | {c[-1] for c in constraints().values()}
    used |= {r[0] for r in _rows(f"select prov_id from '{_p(GSAT)}/*.parquet'")}
    assert used == set(recs)


def test_records_cite_the_series_they_use():
    """For each entry group, the clean records of the series recomputed above are among its record's inputs."""
    e = entries()
    fe, fr = "union_fiscal_fa_expenditure", "union_fiscal_fa_receipts"
    sf = "state_fiscal_rbi_sf_appendices"
    need = {
        ("G_STA", "G_CEN", "R1", "cgst"): [pid(fr, "fa8.0005.00.901"), pid(fr, "fa8.0021.00.901"), pid(fr, "fa8.0037.00.901"), pid(fr, "fa8.0044.00.901"), pid(fr, "fa8.0045.00.901")],
        ("G_STA", "G_CEN", "T2b", "cess_loan_recovery"): [pid("union_fiscal_afs", "afs.pa_disbursements.xi_goods_and_service_tax_compensation_fund"), pid(fe, "fa9.3601.08.904"), pid(fe, "fa9.3602.08.904")],
        ("G_STA", "G_CEN", "R2", "css_outside_treasury"): [pid(fe, "fa9.3601.06.797"), pid(fe, "fa9.3601.06.total"), pid("union_fiscal_exp_profile", "stat18.transfers_to_states_other_than_i_ii.under_centrally_sponsored_schemes_revenue"), pid("union_fiscal_fa_gia", "gia.cash.others.total")],
        ("H_R1", "G_CEN", "R9a", "pensions"): [pid(fe, "fa9.2071.total"), pid(fe, "fa9.2071.01.117"), pid(sf, "app2.total_expenditure.ii.e-pensions.in.all_states_uts.actuals"), pid("finsector_markets_pfrda_sg", "m7d.annual_contribution_employer.state_govt.current")],
        ("H_R1", "E_NFPU", "R9d", "railways"): [pid("union_fiscal_afs", "afs.pa_disbursements.i_railway_funds"), pid(fe, "fa9.3201.07.total")],
        ("H_R1", "G_STA", "R10", "cash_schemes"): [pid("state_fiscal_fc16_subsidies", "sub.cash_transfers.in-ap.gg_state"), pid("state_fiscal_fc16_state_accounts", "fa.revenue_expenditure.mh2235.in-ap"), pid(sf, "app2.total_expenditure.i.a.9-social_security_and_welfare.in.all_states_uts.actuals")],
        ("G_STA", "E_NFPU", "R7x", "mining_royalties"): [pid("state_fiscal_fc16_state_accounts", "fa.revenue_receipts.mh0853.in-od"), pid("mospi_nas_2026_s7_1a", "s7_1a.mining.os.current"), pid("mospi_nas_2026_s7_1b", "s7_1b.mining.os.current"), pid("mospi_nas_2026_s7_1c", "s7_1c.mining.os_mi.current")],
        ("G_CEN", "E_NFPU", "R7x", "telecom_licence"): [pid(fr, "fa8.1275.00.104"), pid("mospi_nas_2026_s7_1a", "s7_1a.communication.os.current")],
        ("G_CEN", "E_NFPU", "R7x", "petroleum_rent"): [pid(fr, "fa8.0802.00.103")],
        ("C_PADM", "G_CEN", "C2a", "total"): [pid(fe, "fa9.section.defence_services"), pid(fe, "fa9.section.administrative_services"), pid(fe, "fa9.2202.total"), pid(fe, "fa9.2210.total"), pid(fe, "fa9.3054.total"), pid(sf, "app2.total_expenditure.i.a.1-education_sports_art_and_culture.in.all_states_uts.actuals")],
        ("K_GCEN", "G_CEN", "K3a", "saving_pos"): [pid("union_fiscal_afs", "afs.cfi_rev_receipts.excess_of_disbursements_over_receipts_revenue_deficit"), pid("union_fiscal_gcca", "stat6.grand_total"), pid(sf, "app4.a-surplus_deficit_on_revenue_account.in.all_states_uts.actuals"), pid("mospi_nas_2026_s1_9", "s1_9.general_government.current"), pid(fr, "fa8.1002.total"), pid("state_fiscal_ulb_cityfinance", "ulb.total_revenues.in.all_ulbs_in_dump")],
        ("K_NFPU", "K_GSTA", "K6", "cofog_residual"): [pid("mospi_nas_2026_s4_2", "s4_2.capital_transfer.total.current"), pid("external_sector_invisibles_annual", "invis.inr.official_transfers.payments.current")],
    }
    for k, pids in need.items():
        inputs = set(records()[e[k][-1]][1])
        missing = [x for x in pids if x not in inputs]
        assert not missing, (k, missing)
    # D2-20: no R9b entry; the formula's series are cited by the R9b record of the sensitivity satellite
    r9b_pid = _rows(f"select distinct prov_id from '{_p(GSAT / 'gov_r9b_sensitivity.parquet')}'")
    assert len(r9b_pid) == 1
    assert {pid(fe, "fa9.2071.01.total"), pid(fe, "fa9.2071.02.total")} <= set(records()[r9b_pid[0][0]][1])
    # every 797 / 'met from' line of the K3a bridge is cited
    fep = _file(fe)
    bridge = {r[0] for r in _rows(f"select distinct prov_id from '{fep}' where period='{YEAR}' and (regexp_matches(series_id, '^fa9\\.[23][0-9]{{3}}\\.[0-9]{{2}}\\.797$') or (regexp_matches(series_id, '^fa9\\.[23][0-9]{{3}}\\.') and item_label ilike '%met from%'))")}
    assert bridge <= set(records()[e["K_GCEN", "G_CEN", "K3a", "saving_pos"][-1]][1])


# ================================================================================================ cross-block
def test_no_duplicate_keys_and_no_foreign_writer_of_government_refs():
    assert not _rows(f"select row, col, ref, component from {all_entries()} group by all having count(*) > 1")
    own = ("C2a", "R1", "R2", "R2k", "T2b", "R6", "R7", "R7x", "R9", "R9a", "R9b", "R9d", "R10", "R15", "R16", "R18", "K3", "K3a", "K6", "K8e")
    refl = ",".join(f"'{r}'" for r in own)
    assert not _rows(f"select block, ref from {all_entries()} where ref in ({refl}) and block <> 'government'")


def test_classified_elsewhere_not_booked_here():
    """PM-KISAN (P10a), MISS and fertiliser (P9a), State food subsidies (P9a) and vehicle tax stay in taxes, once."""
    f = blk("taxes_satellites/tax_classification.parquet")
    cls = dict(_rows(f"select series_id, ref from '{f}'"))
    # Wave C audit fix (government-30): PM-KISAN left taxes' P10a for government's R10 (booked once, there)
    assert cls["class.pm_kisan"] == "none" and cls["class.state_food_subsidies_fc16"] == "P9a"
    kisan = sum(v[0] for k, v in entries().items() if k[2] == "R10" and k[3] == "pm_kisan")
    assert kisan == pytest.approx(fa9("fa9.2401.00.130"), abs=0.01)
    assert cls["class.lic_pension_subsidy"] == "none" and cls["class.lpg_dbt_not_product_subsidy"] == "none"
    lpg_p9 = dict(_rows(f"select series_id, value from '{f}'"))["class.lpg_subsidy_in_p9"]
    r10_lpg = sum(v[0] for k, v in entries().items() if k[2] == "R10" and k[3] == "lpg_dbt")
    assert lpg_p9 + r10_lpg == pytest.approx(val("union_fiscal_exp_profile", "stat7.petroleum.lpg_subsidy"), abs=0.01)
    # R6 is the only RBI flow to government (no dividend from E_RBI in R7)
    assert not [k for k in entries() if k[2] == "R7" and k[1] == "E_RBI"]


def test_k8e_netted_out_of_fsf_centre_state_loans():
    f = blk("capital_financial_satellites/s4_fwtw_sam.parquet")
    sam_loans = _rows(f"select value from '{f}' where series_id='fwtw.i_loan.k_gcen.k_gsta'")[0][0]
    fsf = val("rbi_financial_accounts_fsf_balance_sheets", "fsf.gg_cen.assets.transaction.f4.gg_sta.current")
    k8e = entries()["I_LOAN", "K_GCEN", "K8e", "gst_b2b_repayment"][0]
    assert sam_loans + k8e == pytest.approx(fsf, abs=1.0)


def test_d25_evidence_ranking_on_assembled_prior():
    """GG disposable income of the assembled prior vs NAS 1.14: 'no R9b' fits best, then Centre only, then both."""
    g = "('G_CEN','G_STA')"
    rin = _rows(f"select sum(value) from {all_entries()} where row in {g} and col not in {g}")[0][0]
    out = _rows(f"select sum(value) from {all_entries()} where col in {g} and row not in {g} and ref not in ('C2a','K3a')")[0][0]
    gdi_sam = rin - out
    gap_written = gdi_sam - nas("s1_14", "s1_14.gg.gross_disposable_income.current")
    written = sum(v[0] for k, v in entries().items() if k[2] == "R9b")
    centre, states = parts()["r9b"], parts()["r9_s"] * (1 - 18 / 39)
    base = gap_written - written
    gaps = {"none": base, "centre_only": base + centre, "centre_and_states": base + centre + states}
    assert abs(gaps["none"]) < abs(gaps["centre_only"]) < abs(gaps["centre_and_states"])
    assert written == pytest.approx(0.0, abs=1e-9)  # D2-20: the best-fitting variant 'none' is what is written
    gap_centre = gap_written
    # the GG prior imbalance is exactly this gap (GFCE and saving are pinned to NAS): government-27
    imb = sum(_rows(f"select coalesce(sum(value),0) from {all_entries()} where row='{a}'")[0][0]
              - _rows(f"select coalesce(sum(value),0) from {all_entries()} where col='{a}'")[0][0] for a in GOV)  # fmt: skip
    gfce_gap = sum(v[0] for k, v in entries().items() if k[2] == "C2a") - nas("s1_14", "s1_14.gg.final_consumption_expenditure.current")
    assert imb == pytest.approx(gap_centre - gfce_gap, abs=0.05)


# ================================================================================================ findings
def test_v_gov_1_itb_interest_not_booked_twice():  # V-GOV-1 fixed (was a strict xfail)
    """RBI SF App I ii.c.1 (States' interest receipts) contains interest realised on the States' cash-balance
    investment in the Centre's 14-day intermediate treasury bills. fincorp books that interest (Union MH 2049.01.116)
    as G_STA <- G_CEN (R3 itb_14d); government books all of ii.c.1 as G_STA <- E_NFPU (R7x interest_states)."""
    f = blk("fincorp_entries.parquet")
    itb = _rows(f"select coalesce(sum(value),0) from '{f}' where ref='R3' and row='G_STA' and col='G_CEN' and component='itb_14d'")[0][0]
    assert itb == pytest.approx(fa9("fa9.2049.01.116"), abs=0.01)
    r7x_sta_interest = entries()["G_STA", "E_NFPU", "R7x", "interest_states"][0]
    assert r7x_sta_interest + itb <= sf1("ii.c.1-interest_receipts") + 0.01


def test_v_gov_2_c2a_seed_has_no_overlap():  # V-GOV-2 fixed (was a strict xfail)
    seed_c, seed_s = c2a()["_seed"]  # type: ignore[misc]
    assert seed_s["C_PADM"] + seed_s["C_CNST"] <= (sf2("ii.a-organs_of_state") + sf2("ii.b-fiscal_services") + sf2("ii.d-administrative_services")
                                                   + sf2("ii.f-miscellaneous_general_services") - sf2("ii.f.payment_on_account_of_state_lo-payment_on_account_of_state_lotteries")
                                                   + sf2("i.b.7.i-roads_and_bridges")) + 0.01  # fmt: skip
    assert seed_c["C_PADM"] + seed_c["C_CNST"] <= sum(fa9(f"fa9.section.{s}") for s in ("organs_of_state", "fiscal_services", "administrative_services", "defence_services")) + fa9("fa9.3054.total") + 0.01


def test_v_gov_3_k3a_bridge_does_not_add_cfc():  # V-GOV-3 fixed on 2026-10-01 (was a strict xfail)
    """In SNA gross saving CFC cancels (GOS = CFC is income, CFC is inside GFCE): the block's remainder is NAS saving
    less the two bridge subtotals, with no CFC term."""
    p = parts()
    block_rem = satv("gov_fiscal_bridge", "nas_gg_saving") - satv("gov_fiscal_bridge", "centre.subtotal") - satv("gov_fiscal_bridge", "states.subtotal")
    assert satv("gov_fiscal_bridge", "unexplained_remainder") == pytest.approx(block_rem, abs=0.01)
    assert satv("gov_fiscal_bridge", "unexplained_remainder") == pytest.approx(p["nas_saving"] - p["cen_sub"] - p["sta_sub"], abs=1.0)


# ================================================================================================ re-verification (wave C close-out)
def test_pm_kisan_moves_d39_between_payers_not_its_total():
    """Wave C (government-30, taxes-28): PM-KISAN left taxes' P10a, so the Centre's gross D39 fell by FA 2401.00.130 and
    the States' residual rose by the same amount: total gross D39 still equals NAS 4.2 subsidies - NAS 1.1 product
    subsidies, and no taxes entry carries PM-KISAN (booked once, in R10)."""
    f = blk("taxes_entries.parquet")
    d39 = _rows(f"select coalesce(sum(value),0) from '{f}' where ref='P10a' and component='gross_subsidies'")[0][0]
    nas_d39 = nas("s4_2", "s4_2.subsidy.total.current") - nas("s1_1", "s1_1.subsidies_on_products.current")
    assert -d39 == pytest.approx(nas_d39, abs=0.01)
    assert not _rows(f"select 1 from '{f}' where component ilike '%kisan%'")
    r10_kisan = {k[0] for k in entries() if k[2] == "R10" and k[3] == "pm_kisan"}
    assert r10_kisan == set(HH)


def test_d25_evidence_satellite_recomputes_from_the_entries():
    """The D2-5 / D2-20 evidence after the Wave C PM-KISAN move: delivered net distributive flows without R9b =
    R6 + R7 + R7x + income taxes (taxes' G <- T_PIT/T_CIT) - interest proxy - R9a - R10 - R18; 'none' fits best."""
    e = entries()

    def tot(*refs):
        return sum(v[0] for k, v in e.items() if k[2] in refs)

    f = blk("taxes_entries.parquet")
    inc = _rows(f"select sum(value) from '{f}' where row in ('G_CEN','G_STA') and col in ('T_PIT','T_CIT')")[0][0]
    delivered = tot("R6", "R7", "R7x") + inc - satv("gov_r9b_sensitivity", "prior.interest_paid_proxy") - tot("R9a", "R10") - tot("R18")
    assert satv("gov_r9b_sensitivity", "variant.none.delivered") == pytest.approx(delivered, abs=0.01)
    req = satv("gov_r9b_sensitivity", "nas.required_net_distributive")
    gaps = [abs(satv("gov_r9b_sensitivity", f"variant.{x}.gap")) for x in ("none", "centre_only", "centre_and_states")]
    assert gaps[0] == pytest.approx(abs(delivered - req), abs=0.01)
    assert gaps[0] < gaps[1] < gaps[2]


def test_v_gov_11_k3a_departmental_enterprises_include_mh_3006():  # V-GOV-11 fixed at close-out (was a strict xfail)
    p = parts()
    fe = _file("union_fiscal_fa_expenditure")
    t797_3006 = _rows(f"select coalesce(sum(value),0) from '{fe}' where period='{YEAR}' and regexp_matches(series_id, '^fa9[.]3006[.][0-9]{{2}}[.]797$')")[0][0]
    # the Railways' surplus is exactly what MH 3006 appropriates: with MH 3006 inside the enterprise, its net is ~0
    rail_net = sum(fa8(f"fa8.{m}.total") for m in ("1001", "1002", "1003")) - sum(fa9(f"fa9.{m}.total") for m in ("3001", "3002", "3003", "3006"))
    assert abs(rail_net) < 0.05
    # the verifier's expectation: the subtotal as built before the fix (MH 3006 left in), corrected for MH 3006
    centre_without_3006 = p["cen_sub"] + t797_3006 - fa9("fa9.3006.total")
    centre_full = centre_without_3006 - t797_3006 + fa9("fa9.3006.total")
    assert satv("gov_fiscal_bridge", "centre.subtotal") == pytest.approx(centre_full, abs=1.0)
    assert satv("gov_fiscal_bridge", "centre.subtotal") - centre_without_3006 == pytest.approx(1500.0, abs=0.01)


def test_v_gov_12_pm_kisan_reclassification_is_recorded_in_decisions():  # V-GOV-12 fixed (D2-24; was a strict xfail)
    assert any(e[3] == "pm_kisan" for e in entries())
    rows = [ln for ln in (ROOT / "DECISIONS.md").read_text(encoding="utf-8").splitlines() if ln.startswith("| D2-")]
    assert any("PM-KISAN" in ln or "farm income support" in ln.lower() for ln in rows)
