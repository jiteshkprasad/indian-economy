"""Independent verification of the SAM `rest_of_world` block (Phase 2 verifier, 2026-09-30; SPEC s.3 rule 3).

This file does NOT import pipeline.sam or the block (no block, framework or spec code) and does not use polars.
Every expected number is recomputed here with DuckDB SQL plus plain Python arithmetic from:
- data/clean/mospi_nas_2026: St 6.1 (RoW account) and St 1.9 (net capital inflow, reinvested earnings);
- data/clean/external_sector: BoP BPM6 annual and quarterly, old-format BoP, invisibles, remittance survey,
  FLA census (2023-24 round, vintage 2024-10-11), NRI deposits, ECB registrations 2023-24, LRS, FX, ITES survey;
- data/clean/rbi_banking_corporate: RBI Annual Report schedules 13/14 (vintage 2025-05-29), RTP banks
  (vintage 2025-12-29: foreign banks' income/expenditure, SCB cost of deposits);
- data/clean/rbi_financial_accounts: FSF RoW balance sheets (vintage 2026-01-21), HBS T107 G-sec ownership;
- data/clean/union_fiscal (Finance Accounts MH 2049 and 0049), data/clean/state_fiscal (RBI State Finances App. 2);
- data/clean/io_tables: SUT supply (CIF memo row); data/clean/trade_satellites: IMF IMTS FY (World totals);
- data/sam/2023-24/blocks: households' hh_state_xwalk / hh_keys satellites (the legitimate DEPENDS inputs), and
  every built block's *_entries.parquet (closure of R_ROW / K_ROW, double counting, the capital_financial mirror).
It is compared with the block's written outputs (data/sam/2023-24/blocks/rest_of_world_*): a census of all
81 entries, all 14 constraints, all 29 checks' targets, the interface satellites and the sensitivity satellites.

Method rules recomputed: docs/phase2/plans/rest_of_world.md s.2-3 and s.8 (XR-4, XR-12, XR-13, XR-14), DECISIONS
D2-3 and D2-7, the gap map R11a..D2. Findings are recorded in docs/phase2/verify/rest_of_world.md (V-ROW-n).
A confirmed defect is a strict xfail with its finding id.
"""

# ruff: noqa: E501  (long DuckDB SQL literals are kept on one line so each rule reads as one statement)
from __future__ import annotations

import math
from functools import cache
from pathlib import Path

import duckdb
import pytest
import yaml

pytestmark = [pytest.mark.quality, pytest.mark.sam]

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean"
BLOCKS = ROOT / "data" / "sam" / "2023-24" / "blocks"
SAT = BLOCKS / "rest_of_world_satellites"
HHSAT = BLOCKS / "households_satellites"
YEAR = "2023-24"
TOL = 0.01  # Rs crore: census tolerance (entries are written to 6 decimals)
GROUPS = ["H_R1", "H_R2", "H_R3", "H_R4", "H_R5", "H_U1", "H_U2", "H_U3", "H_U4", "H_U5"]
D0, D1 = "2023-03-31", "2024-03-31"  # the two stock dates averaged for every stock key
FLA_V = "2024-10-11"  # the FLA 2023-24 round: the only one with end-March 2024 sector detail
RTP_V = "2025-12-29"
AR_V = "2025-05-29"


def _p(path: Path) -> str:
    return path.as_posix()


@cache
def con() -> duckdb.DuckDBPyConnection:
    for f in ("entries", "constraints", "provenance", "checks"):
        if not (BLOCKS / f"rest_of_world_{f}.parquet").exists():
            pytest.fail(f"rest_of_world_{f}.parquet missing: run `uv run python -m pipeline sam rest_of_world`")
    return duckdb.connect()


@cache
def _ds_path(dataset: str) -> str:
    hits = sorted(CLEAN.glob(f"*/{dataset}.parquet"))
    assert len(hits) == 1, f"clean dataset {dataset}: {hits}"
    return _p(hits[0])


def val(dataset: str, series_id: str, period: str = YEAR, vintage: str | None = None) -> tuple[float, str]:
    """One clean value; vintage None = the latest vintage of that (series, period)."""
    f = _ds_path(dataset)
    rows = (
        con()
        .execute(f"select value, prov_id, vintage from '{f}' where series_id = ? and period = ?", [series_id, period])
        .fetchall()
    )
    assert rows, f"{dataset} {series_id} {period}: no row"
    if vintage is None:
        vintage = max(r[2] for r in rows)
    rows = [r for r in rows if r[2] == vintage]
    assert len(rows) == 1, f"{dataset} {series_id} {period} {vintage}: {len(rows)} rows"
    return float(rows[0][0]), rows[0][1]


def v(dataset: str, series_id: str, period: str = YEAR, vintage: str | None = None) -> float:
    return val(dataset, series_id, period, vintage)[0]


def avg(dataset: str, series_id: str, vintage: str | None = None) -> float:
    return 0.5 * (v(dataset, series_id, D0, vintage) + v(dataset, series_id, D1, vintage))


def nas(s: str) -> float:
    return v("mospi_nas_2026_s6_1", f"s6_1.{s}.current")


def bpm6(s: str) -> float:
    return v("external_sector_bop_bpm6_annual", f"bpm6.inr.{s}.current")


def bop_old(s: str) -> float:
    return v("external_sector_bop_overall_annual", f"bop_old.inr.{s}.net.current")


@cache
def accounts() -> dict[str, list[str]]:
    data = yaml.safe_load((ROOT / "pipeline" / "sam" / "accounts.yaml").read_text(encoding="utf-8"))
    out: dict[str, list[str]] = {}
    for a in data["accounts"]:
        out.setdefault(a["group"], []).append(a["code"])
    return out


@cache
def entries() -> dict[tuple[str, str, str, str], dict]:
    f = _p(BLOCKS / "rest_of_world_entries.parquet")
    cur = con().execute(f"select * from '{f}'")
    cols = [d[0] for d in cur.description]
    out = {}
    for r in cur.fetchall():
        d = dict(zip(cols, r, strict=True))
        out[(d["row"], d["col"], d["ref"], d["component"])] = d
    return out


@cache
def all_entries() -> list[dict]:
    cur = con().execute(f"select block, row, col, ref, component, value from '{_p(BLOCKS)}/*_entries.parquet'")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


@cache
def prov() -> dict[str, dict]:
    f = _p(BLOCKS / "rest_of_world_provenance.parquet")
    cur = con().execute(f"select * from '{f}'")
    cols = [d[0] for d in cur.description]
    return {r[cols.index("prov_id")]: dict(zip(cols, r, strict=True)) for r in cur.fetchall()}


def sat(name: str) -> list[dict]:
    cur = con().execute(f"select * from '{_p(SAT / (name + '.parquet'))}'")
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


# --------------------------------------------------------------------------------------------------------------
# Independent recomputation of every entry value
# --------------------------------------------------------------------------------------------------------------


@cache
def r11a_key() -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """Survey State shares (normalised) and each State's consumption by SAM group (households' hh_state_xwalk)."""
    f = _ds_path("external_sector_remittance_survey")
    surv = dict(
        con()
        .execute(
            f"select replace(series_id, 'remit.destination_state.', ''), value from '{f}' where series_id like 'remit.destination_state.%' and period = '{YEAR}' and vintage = '2025-03-19'"
        )
        .fetchall()
    )
    tot = sum(surv.values())
    s_k = {k: x / tot for k, x in surv.items()}
    xw = (
        con()
        .execute(
            f"select lower(geography), household_group, sum(value) from '{_p(HHSAT / 'hh_state_xwalk.parquet')}' where measure = 'consumption' and hces_class = 'all' group by all"
        )
        .fetchall()
    )
    cons: dict[str, dict[str, float]] = {}
    for k, g, x in xw:
        cons.setdefault(k, {})[g] = cons.get(k, {}).get(g, 0.0) + float(x)
    return s_k, cons


def remit_by_group(total: float, shares: dict[str, float], cons: dict[str, dict[str, float]]) -> dict[str, float]:
    tot = sum(shares.values())
    out = dict.fromkeys(GROUPS, 0.0)
    for k, s in shares.items():
        ck = cons[k]
        ct = sum(ck.values())
        for g, x in ck.items():
            out[g] += total * (s / tot) * x / ct
    return out


@cache
def pfce_levels() -> dict[str, float]:
    return dict(
        con()
        .execute(
            f"select household_group, value from '{_p(HHSAT / 'hh_keys.parquet')}' where key = 'pfce_total' and measure = 'level'"
        )
        .fetchall()
    )


@cache
def expected() -> dict[tuple[str, str, str, str], float]:
    e: dict[tuple[str, str, str, str], float] = {}

    # ---- R11a: survey State shares x within-State consumption by national group, scaled to NAS 6.1 item 4
    r11 = nas("other_current_transfers_to_resident_sectors_other_than_gener")
    s_k, cons = r11a_key()
    for g, x in remit_by_group(r11, s_k, cons).items():
        e[(g, "R_ROW", "R11a", "remittances")] = x

    # ---- R12a: NAS 6.1 item 9 on H_U4/H_U5 by pfce_total levels
    r12 = nas("other_current_transfers_by_resident_sectors_other_than_gener")
    pf = pfce_levels()
    for g in ("H_U4", "H_U5"):
        e[("R_ROW", g, "R12a", "outward_transfers")] = r12 * pf[g] / (pf["H_U4"] + pf["H_U5"])

    # ---- R13: property income received, by recipient
    fsf = "rbi_financial_accounts_fsf_balance_sheets"
    ar = v("rbi_banking_corporate_rbi_accounts", "sch13.b.sub_total.current", vintage=AR_V) + v(
        "rbi_banking_corporate_rbi_accounts",
        "sch14.b.amortisation_of_premium_discount_on_foreign_securities.current",
        vintage=AR_V,
    )
    e[("E_RBI", "R_ROW", "R13", "reserve_asset_income")] = ar
    e[("E_RBI", "R_ROW", "R13", "reserve_income_unexplained")] = bpm6("bpm6_1_b_2_4.credit") - ar
    f51 = {cp: avg(fsf, f"fsf.row.liabilities.outstanding.f51.{cp}.current") for cp in ("nfc_pvt", "fc_ofc", "fc_odc")}
    acc51 = {"nfc_pvt": "E_NFPR", "fc_ofc": "E_NBFC", "fc_odc": "E_BANK"}
    t51 = sum(f51.values())
    nonres: dict[str, float] = {}
    for comp, s in (("di_income", "bpm6_1_b_2_1.credit"), ("pi_income", "bpm6_1_b_2_2.credit")):
        tot = bpm6(s)
        for cp, x in f51.items():
            e[(acc51[cp], "R_ROW", "R13", comp)] = tot * x / t51
            nonres[acc51[cp]] = nonres.get(acc51[cp], 0.0) + tot * x / t51
    oi_map = {"fc_odc": "E_BANK", "nfc_pvt": "E_NFPR", "gg_cen": "G_CEN", "fc_ofc": "E_NBFC"}
    oi_key = {
        cp: avg(fsf, f"fsf.row.liabilities.outstanding.f22_f29.{cp}.current")
        + avg(fsf, f"fsf.row.liabilities.outstanding.f4.{cp}.current")
        for cp in oi_map
    }
    oi_tot = bpm6("bpm6_1_b_2_3.credit")
    for cp, x in oi_key.items():
        e[(oi_map[cp], "R_ROW", "R13", "oi_income")] = oi_tot * x / sum(oi_key.values())
        nonres[oi_map[cp]] = nonres.get(oi_map[cp], 0.0) + oi_tot * x / sum(oi_key.values())
    types_cr = sum(bpm6(f"bpm6_1_b_2_{i}.credit") for i in (1, 2, 3, 4)) + bpm6("bpm6_1_b_3.credit")
    opi_cr = bpm6("bpm6_1_b_3.credit") + nas("property_and_entrepreneurial_income_from_rest_of_the_world") - types_cr
    for a, x in nonres.items():
        e[(a, "R_ROW", "R13", "other_primary_income")] = opi_cr * x / sum(nonres.values())

    # ---- R14a and R14 DI distributed: FLA t8 NFC/FC key, foreign banks' profit for E_BANK
    re_ = v("mospi_nas_2026_s1_9", "s1_9.reinvested_earnings_of_foreign_companies_in_private_corporat.current")
    di_db = bpm6("bpm6_1_b_2_1.debit")
    dist = di_db - re_
    fc = v("external_sector_fla_census", "fla.t8.g.financial_and_insurance_activities.equity", D1, FLA_V) / v(
        "external_sector_fla_census", "fla.t8.total.equity", D1, FLA_V
    )
    fb = v("rbi_banking_corporate_rtp_banks", "rtp.scb_pl.income_total.fb.current", vintage=RTP_V) - v(
        "rbi_banking_corporate_rtp_banks", "rtp.scb_pl.expenditure_total.fb.current", vintage=RTP_V
    )
    ratio = re_ / di_db
    e[("R_ROW", "E_NFPR", "R14a", "reinvested_earnings")] = re_ * (1 - fc)
    e[("R_ROW", "E_BANK", "R14a", "reinvested_earnings")] = fb * ratio
    e[("R_ROW", "E_NBFC", "R14a", "reinvested_earnings")] = re_ * fc - fb * ratio
    e[("R_ROW", "E_NFPR", "R14", "di_distributed")] = dist * (1 - fc)
    e[("R_ROW", "E_BANK", "R14", "di_distributed")] = fb * (1 - ratio)
    e[("R_ROW", "E_NBFC", "R14", "di_distributed")] = dist * fc - fb * (1 - ratio)

    # ---- R14 portfolio income: FPI interest on government paper (XR-12 formula), remainder by FLA t8
    hbs = "rbi_financial_accounts_hbs_gsec_ownership"

    def sh(inst: str) -> float:
        return avg(hbs, f"t107.{inst}.share.fpi") / 100.0

    fa9 = "union_fiscal_fa_expenditure"
    ml_net = (
        v(fa9, "fa9.2049.01.101")
        - v("union_fiscal_fa_receipts", "fa8.0049.03.116")
        - v("union_fiscal_fa_receipts", "fa8.0049.03.117")
    )
    tb = sum(v(fa9, f"fa9.2049.01.{c}") for c in ("103", "108", "110"))
    sdl_int = v(
        "state_fiscal_rbi_sf_appendices",
        "app2.total_expenditure.ii.c.2.ii.a-interest_on_market_loans.in.all_states_uts.actuals",
    )
    g_int = sh("gsec_central") * ml_net
    t_int = sh("tbills") * tb
    s_int = sh("sgs") * sdl_int
    e[("R_ROW", "G_CEN", "R14", "fpi_gsec_interest")] = g_int
    e[("R_ROW", "G_CEN", "R14", "fpi_tbill_interest")] = t_int
    e[("R_ROW", "G_STA", "R14", "fpi_sdl_interest")] = s_int
    pi_other = bpm6("bpm6_1_b_2_2.debit") - g_int - t_int - s_int
    bank_di = fb  # E_BANK's DI payments (distributed + reinvested) = foreign banks' profit
    nbfc_di = re_ * fc - fb * ratio + dist * fc - fb * (1 - ratio)
    e[("R_ROW", "E_NFPR", "R14", "pi_other")] = pi_other * (1 - fc)
    e[("R_ROW", "E_BANK", "R14", "pi_other")] = pi_other * fc * bank_di / (bank_di + nbfc_di)
    e[("R_ROW", "E_NBFC", "R14", "pi_other")] = pi_other * fc * nbfc_di / (bank_di + nbfc_di)

    # ---- R14 other investment income
    ext = v(fa9, "fa9.2049.02.total")
    nri_avg = avg("external_sector_nri_deposits", "nri.stock.inr.total.current")
    nri = (
        nri_avg
        * v("rbi_banking_corporate_rtp_banks", "rtp.scb_cost_return.cost_of_deposits.scb", vintage=RTP_V)
        / 100.0
    )
    e[("R_ROW", "G_CEN", "R14", "ext_assistance_interest")] = ext
    e[("R_ROW", "E_BANK", "R14", "nri_deposit_interest")] = nri
    oi_other = bpm6("bpm6_1_b_2_3.debit") - ext - nri
    k = {
        "E_BANK": avg(fsf, "fsf.row.assets.outstanding.f4.fc_odc.current")
        + avg(fsf, "fsf.row.assets.outstanding.f22_f29.fc_odc.current")
        - nri_avg,
        "E_NBFC": avg(fsf, "fsf.row.assets.outstanding.f4.fc_ofc.current"),
        "E_NFPR": avg(fsf, "fsf.row.assets.outstanding.f4.nfc_pvt.current"),
        "E_RBI": avg(fsf, "fsf.row.assets.outstanding.f22_f29.fc_rbi.current"),
    }
    for a, x in k.items():
        e[("R_ROW", a, "R14", "oi_other_interest")] = oi_other * x / sum(k.values())
    e[("R_ROW", "E_RBI", "R14", "reserve_asset_debit")] = bpm6("bpm6_1_b_2_4.debit")
    types_db = sum(bpm6(f"bpm6_1_b_2_{i}.debit") for i in (1, 2, 3, 4)) + bpm6("bpm6_1_b_3.debit")
    opi_db = bpm6("bpm6_1_b_3.debit") + nas("property_and_entrepreneurial_income_to_the_rest_of_the_world") - types_db
    by_payer: dict[str, float] = {}
    for (r, c, ref, _comp), x in e.items():
        if r == "R_ROW" and ref == "R14":
            by_payer[c] = by_payer.get(c, 0.0) + x
    for a, x in by_payer.items():
        e[("R_ROW", a, "R14", "other_primary_income")] = opi_db * x / sum(by_payer.values())

    # ---- K5, K8c, D2
    e[("K_ROW", "R_ROW", "K5", "total")] = v("mospi_nas_2026_s1_9", "s1_9.net_capital_inflow_from_row.current")
    e[("I_RESV", "K_RBI", "K8c", "reserve_assets")] = bpm6("bpm6_3_5.debit")
    e[("R_ROW", "X_DISC", "D2", "cif_reconciliation")] = v("io_tables_sut_supply", "supply.cif_adj.cif.current")

    # ---- K8b: BoP functional lines (old format), NAS totals, FPI debt split by T107
    liab = {
        ("I_EQTY", "fdi_equity"): bop_old("ka.fdi.in_india.equity"),
        ("I_EQTY", "fdi_reinvested_earnings"): re_,
        ("I_LOAN", "fdi_debt"): bop_old("ka.fdi.in_india.other_capital"),
        ("I_EQTY", "fpi_equity"): bop_old("ka.portfolio.in_india.fiis.equity"),
        ("I_LOAN", "ecb"): bop_old("ka.loans.ecb.to_india"),
        ("I_LOAN", "external_assistance"): bop_old("ka.loans.external_assistance.to_india"),
        ("I_OTHR", "short_term_trade_credit"): bop_old("ka.loans.short_term"),
        ("I_DEPO", "nri_deposits"): bop_old("ka.banking_capital.commercial_banks.nri_deposits"),
        ("I_DEPO", "bank_other_liabilities"): bop_old("ka.banking_capital.commercial_banks.liabilities")
        - bop_old("ka.banking_capital.commercial_banks.nri_deposits"),
        ("I_DEPO", "rbi_deposits"): bop_old("ka.banking_capital.others"),
        ("I_OTHR", "rupee_debt_service"): bop_old("ka.rupee_debt_service"),
        ("I_OTHR", "errors_omissions"): nas("other_liabilities_to_non_residents"),
    }
    gsec = sum(
        v(hbs, f"t107.{i}.share.fpi", D1) / 100 * v(hbs, f"t107.{i}.outstanding.current", D1)
        - v(hbs, f"t107.{i}.share.fpi", D0) / 100 * v(hbs, f"t107.{i}.outstanding.current", D0)
        for i in ("gsec_central", "tbills", "sgs")
    )
    fpi_debt = bop_old("ka.portfolio.in_india.fiis.debt")
    liab[("I_GSEC", "fpi_debt_gsec")] = gsec
    liab[("I_CBND", "fpi_debt_corporate")] = fpi_debt - gsec
    liab[("I_OTHR", "nas_reconciliation_liab")] = nas("net_incurrence_of_foreign_liabilities") - sum(liab.values())
    for (inst, comp), x in liab.items():
        e[(inst, "K_ROW", "K8b", comp)] = x
    asset = {
        ("I_EQTY", "odi_equity"): -bop_old("ka.fdi.abroad.equity"),
        ("I_EQTY", "odi_reinvested_earnings"): -bop_old("ka.fdi.abroad.reinvested_earnings"),
        ("I_LOAN", "odi_debt"): -bop_old("ka.fdi.abroad.other_capital"),
        ("I_EQTY", "portfolio_abroad"): -bop_old("ka.portfolio.abroad"),
        ("I_LOAN", "loans_by_india"): -bop_old("ka.loans.ecb.by_india"),
        ("I_LOAN", "external_assistance_by_india"): -bop_old("ka.loans.external_assistance.by_india"),
        ("I_DEPO", "banks_foreign_assets"): -bop_old("ka.banking_capital.commercial_banks.assets"),
        ("I_OTHR", "other_capital"): -bop_old("ka.other_capital"),
        ("I_RESV", "reserve_assets"): -bop_old("monetary_movements.reserves"),
    }
    asset[("I_OTHR", "nas_reconciliation_assets")] = nas("net_acquisition_of_foreign_financial_assets") - sum(
        asset.values()
    )
    for (inst, comp), x in asset.items():
        e[("K_ROW", inst, "K8b", comp)] = x
    return e


# Expected metadata per (ref, component): status, role, confidence, tol_rel. bop tags checked separately.
META = {
    ("R11a", "remittances"): ("estimated", "free", "low", None),
    ("R12a", "outward_transfers"): ("estimated", "free", "low", None),
    ("R13", "reserve_asset_income"): ("derived", "anchored", None, 0.02),  # plan s.8 item 1 (XR-4), D2-7
    ("R13", "reserve_income_unexplained"): ("estimated", "free", "low", None),
    ("R13", "di_income"): ("estimated", "free", "low", None),
    ("R13", "pi_income"): ("estimated", "free", "low", None),
    ("R13", "oi_income"): ("estimated", "free", "low", None),
    ("R13", "other_primary_income"): ("estimated", "free", "low", None),
    ("R14", "ext_assistance_interest"): ("derived", "anchored", None, 0.10),  # cash vs accrual (plan s.2.4)
    ("R14", "nri_deposit_interest"): ("estimated", "free", "medium", None),
    ("R14", "fpi_gsec_interest"): ("estimated", "free", "medium", None),
    ("R14", "fpi_tbill_interest"): ("estimated", "free", "low", None),
    ("R14", "fpi_sdl_interest"): ("estimated", "free", "low", None),
    ("R14", "pi_other"): ("estimated", "free", "low", None),
    ("R14", "oi_other_interest"): ("estimated", "free", "low", None),
    ("R14", "reserve_asset_debit"): ("estimated", "free", "low", None),
    ("R14", "other_primary_income"): ("estimated", "free", "low", None),
    ("K5", "total"): ("official", "fixed", None, None),
    ("K8c", "reserve_assets"): ("official", "fixed", None, None),
    ("D2", "cif_reconciliation"): ("official", "fixed", None, None),
    ("K8b", "fpi_debt_gsec"): ("estimated", "free", "medium", None),
    ("K8b", "fpi_debt_corporate"): ("estimated", "free", "medium", None),
    ("K8b", "bank_other_liabilities"): ("derived", "fixed", None, None),
    ("K8b", "nas_reconciliation_liab"): ("derived", "fixed", None, None),
    ("K8b", "nas_reconciliation_assets"): ("derived", "fixed", None, None),
}
BOP_TAG = {
    "fdi_equity": "FDI_equity", "fdi_reinvested_earnings": "FDI_reinvested_earnings", "fdi_debt": "FDI_debt",
    "fpi_equity": "FPI_equity", "fpi_debt_gsec": "FPI_debt", "fpi_debt_corporate": "FPI_debt", "ecb": "ECB",
    "external_assistance": "other", "short_term_trade_credit": "short_term_credit", "nri_deposits": "NRI_deposits",
    "bank_other_liabilities": "other", "rbi_deposits": "other", "rupee_debt_service": "other", "errors_omissions": "other",
    "nas_reconciliation_liab": "other", "odi_equity": "ODI", "odi_reinvested_earnings": "ODI", "odi_debt": "ODI",
    "portfolio_abroad": "other", "loans_by_india": "other", "external_assistance_by_india": "other",
    "banks_foreign_assets": "other", "other_capital": "other", "reserve_assets": "reserves", "nas_reconciliation_assets": "other",
}  # fmt: skip


# --------------------------------------------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------------------------------------------


@cache
def stale_deps() -> tuple[str, ...]:
    """DEPENDS blocks whose outputs changed after rest_of_world read them (catalog sha256 vs the files now)."""
    import hashlib
    import json

    cat = json.loads((BLOCKS / "rest_of_world_block.json").read_text(encoding="utf-8"))
    out = []
    for blk, files in sorted(cat["dependency_hashes"].items()):
        for kind, sha in files.items():
            if hashlib.sha256((BLOCKS / f"{blk}_{kind}.parquet").read_bytes()).hexdigest() != sha:
                out.append(blk)
                break
    return tuple(out)


HH_REFS = ("R11a", "R12a")  # the only entries computed from households' outputs


def test_dependencies_not_stale():
    """V-ROW-5: after a households/production rebuild, rest_of_world must be rebuilt before its household keys can be verified."""
    if stale_deps():
        pytest.skip(f"V-ROW-5: rest_of_world is stale on {stale_deps()}: rebuild it (then fincorp, capital_financial)")


def test_entry_census_every_value():
    """All 81 entries recomputed from clean data (and households' published keys); same key set, values to 0.01.
    R11a/R12a are compared only while the block is not stale on households (V-ROW-5)."""
    exp, got = expected(), entries()
    assert set(got) == set(exp), f"missing {sorted(set(exp) - set(got))}; extra {sorted(set(got) - set(exp))}"
    assert len(got) == 81
    skip = HH_REFS if "households" in stale_deps() else ()
    bad = {k: (got[k]["value"], x) for k, x in exp.items() if k[2] not in skip and abs(got[k]["value"] - x) > TOL}
    assert not bad, bad


def test_entry_metadata_roles_status_confidence_tags():
    for k, d in entries().items():
        _row, _col, ref, comp = k
        if (ref, comp) in META:
            st, role, conf, tol = META[(ref, comp)]
        elif ref == "K8b":
            st, role, conf, tol = ("official", "fixed", None, None)
        elif ref == "R14" and comp == "di_distributed":
            st, role, conf, tol = ("estimated", "free", "medium" if k[1] == "E_NFPR" else "low", None)
        elif ref == "R14a":
            st, role, conf, tol = ("estimated", "free", "medium" if k[1] == "E_NFPR" else "low", None)
        else:
            pytest.fail(f"unexpected entry {k}")
        assert (d["status"], d["role"], d["confidence"]) == (st, role, conf), (
            k,
            d["status"],
            d["role"],
            d["confidence"],
        )
        assert (d["tol_rel"] is None and tol is None) or math.isclose(d["tol_rel"], tol), (k, d["tol_rel"])
        assert prov()[d["prov_id"]]["status"] == d["status"], k
        if ref == "K8b":
            assert d["bop_function"] == BOP_TAG[comp], (k, d["bop_function"])
        elif ref == "R14a":
            assert d["bop_function"] == "FDI_reinvested_earnings", k
        else:
            assert d["bop_function"] is None, k
        assert d["value"] != 0.0 and math.isfinite(d["value"]), k


def test_signs():
    """Signs follow the plan: every current-account entry and K5/K8c/D2 is positive; K8b signs are the published net flows."""
    for (row, col, ref, comp), d in entries().items():
        if ref in ("R11a", "R12a", "R13", "R14", "R14a", "K5", "K8c", "D2"):
            assert d["value"] > 0, (row, col, ref, comp)
    neg = {k[3] for k, d in entries().items() if d["value"] < 0}
    assert neg == {
        "short_term_trade_credit",
        "rupee_debt_service",
        "banks_foreign_assets",
        "nas_reconciliation_liab",
        "nas_reconciliation_assets",
    }


def test_official_totals_and_bop_type_totals():
    ent = entries()

    def s(pred) -> float:
        return sum(d["value"] for k, d in ent.items() if pred(k))

    assert abs(s(lambda k: k[2] == "R11a") - nas("other_current_transfers_to_resident_sectors_other_than_gener")) < 1e-5
    assert abs(s(lambda k: k[2] == "R11a") - bpm6("bpm6_1_c_1.credit")) <= 1.0
    assert abs(s(lambda k: k[2] == "R12a") - nas("other_current_transfers_by_resident_sectors_other_than_gener")) < 1e-5
    assert abs(s(lambda k: k[2] == "R12a") - bpm6("bpm6_1_c_1.debit")) <= 1.0
    assert abs(s(lambda k: k[2] == "R13") - nas("property_and_entrepreneurial_income_from_rest_of_the_world")) < 1e-5
    assert (
        abs(s(lambda k: k[2] in ("R14", "R14a")) - nas("property_and_entrepreneurial_income_to_the_rest_of_the_world"))
        < 1e-5
    )
    assert (
        abs(
            s(lambda k: k[2] in ("R14", "R14a"))
            - v("external_sector_invisibles_annual", "invis.inr.income.investment.payments.current")
        )
        <= 1.0
    )
    re_ = v("mospi_nas_2026_s1_9", "s1_9.reinvested_earnings_of_foreign_companies_in_private_corporat.current")
    assert abs(s(lambda k: k[2] == "R14a") - re_) < 1e-5
    assert abs(re_ - bpm6("bpm6_3_1_a_1_2.credit")) <= 1.0
    # BoP credit types (prior; not binding, rest_of_world-7)
    assert abs(s(lambda k: k[2] == "R13" and k[3] == "di_income") - bpm6("bpm6_1_b_2_1.credit")) < 1e-5
    assert abs(s(lambda k: k[2] == "R13" and k[3] == "pi_income") - bpm6("bpm6_1_b_2_2.credit")) < 1e-5
    assert abs(s(lambda k: k[2] == "R13" and k[3] == "oi_income") - bpm6("bpm6_1_b_2_3.credit")) < 1e-5
    assert abs(s(lambda k: k[0] == "E_RBI" and k[2] == "R13") - bpm6("bpm6_1_b_2_4.credit")) < 1e-5
    assert abs(s(lambda k: k[2] == "R13" and k[3] == "other_primary_income") - bpm6("bpm6_1_b_3.credit")) <= 1.0
    # BoP debit types
    assert abs(s(lambda k: k[3] in ("di_distributed", "reinvested_earnings")) - bpm6("bpm6_1_b_2_1.debit")) < 1e-5
    assert (
        abs(
            s(lambda k: k[3] in ("fpi_gsec_interest", "fpi_tbill_interest", "fpi_sdl_interest", "pi_other"))
            - bpm6("bpm6_1_b_2_2.debit")
        )
        < 1e-5
    )
    assert (
        abs(
            s(lambda k: k[3] in ("ext_assistance_interest", "nri_deposit_interest", "oi_other_interest"))
            - bpm6("bpm6_1_b_2_3.debit")
        )
        < 1e-5
    )
    assert abs(s(lambda k: k[3] == "reserve_asset_debit") - bpm6("bpm6_1_b_2_4.debit")) < 1e-5
    assert abs(s(lambda k: k[2] == "R14" and k[3] == "other_primary_income") - bpm6("bpm6_1_b_3.debit")) <= 1.0
    # K5 and the external_sector-5 bridge
    k5 = ent[("K_ROW", "R_ROW", "K5", "total")]["value"]
    assert abs(k5 + nas("surplus_on_current_transactions")) < 0.01
    assert abs(k5 + bpm6("bpm6_1.net") - bpm6("bpm6_1_c_2.net")) <= 1.0
    # K8b sides equal NAS items 17/16; their difference is minus NAS net lending = -(BoP CA + KA)
    liab = s(lambda k: k[1] == "K_ROW" and k[2] == "K8b")
    ast = s(lambda k: k[0] == "K_ROW" and k[2] == "K8b")
    assert abs(liab - nas("net_incurrence_of_foreign_liabilities")) < 1e-5
    assert abs(ast - nas("net_acquisition_of_foreign_financial_assets")) < 1e-5
    assert abs(liab - ast + nas("net_lending_to_the_rest_of_the_world_13_14_15_16_or_18_19")) < 1e-5
    assert abs(liab - ast + bpm6("bpm6_1.net") + bpm6("bpm6_2.net")) <= 1.0
    # K8b reproduces the BPM6 functional totals
    assert (
        abs(s(lambda k: k[3] in ("fdi_equity", "fdi_reinvested_earnings", "fdi_debt")) - bpm6("bpm6_3_1_a.net")) <= 1.0
    )
    assert (
        abs(s(lambda k: k[3] in ("fpi_equity", "fpi_debt_gsec", "fpi_debt_corporate")) - bpm6("bpm6_3_2_a.net")) <= 1.0
    )
    assert (
        abs(s(lambda k: k[3] in ("odi_equity", "odi_reinvested_earnings", "odi_debt")) + bpm6("bpm6_3_1_b.net")) <= 1.0
    )
    assert (
        abs(ent[("K_ROW", "I_EQTY", "K8b", "odi_reinvested_earnings")]["value"] - bpm6("bpm6_3_1_b_1_2.debit")) < 1e-5
    )
    assert abs(ent[("I_OTHR", "K_ROW", "K8b", "errors_omissions")]["value"] - bpm6("bpm6_5.net")) <= 1.0
    assert abs(ent[("I_EQTY", "K_ROW", "K8b", "fdi_reinvested_earnings")]["value"] - re_) < 1e-9
    for comp in ("nas_reconciliation_liab", "nas_reconciliation_assets"):
        x = [d["value"] for k, d in ent.items() if k[3] == comp][0]
        assert abs(x) <= 150, comp
    # K8c = BPM6 3.5 = FSF RBI F3 transaction = minus the four quarters of the quarterly BoP (net: + is a drawdown)
    k8c = ent[("I_RESV", "K_RBI", "K8c", "reserve_assets")]["value"]
    assert (
        abs(k8c - v("rbi_financial_accounts_fsf_balance_sheets", "fsf.row.liabilities.transaction.f3.fc_rbi.current"))
        <= 1.0
    )
    q = sum(
        v("external_sector_bop_bpm6_quarterly", "bpm6q.inr.bpm6_3_5.net.current", f"Q{i} {YEAR}") for i in (1, 2, 3, 4)
    )
    assert abs(k8c + q) <= 1.0
    assert abs(k8c - ent[("K_ROW", "I_RESV", "K8b", "reserve_assets")]["value"]) < 1e-9  # I_RESV clears in the block
    # D2 = SUT imports - imports after CIF; NAS item 18 within 1; production P6 + D2 = NAS imports
    d2 = ent[("R_ROW", "X_DISC", "D2", "cif_reconciliation")]["value"]
    assert (
        abs(
            d2
            - (
                v("io_tables_sut_supply", "supply.imports.total.current")
                - v("io_tables_sut_supply", "supply.imports_after_cif.total.current")
            )
        )
        < 0.01
    )
    assert v("io_tables_sut_supply", "supply.cif_adj.total.current") == 0.0
    assert abs(d2 - nas("adjustment_for_cif_in_import_of_services")) <= 1.0
    p6 = sum(d["value"] for d in all_entries() if d["block"] == "production" and d["ref"] == "P6")
    assert abs(p6 + d2 - nas("imports")) < 0.01


def test_fpi_debt_split_and_sebi_crosscheck():
    ent = entries()
    g = ent[("I_GSEC", "K_ROW", "K8b", "fpi_debt_gsec")]["value"]
    c = ent[("I_CBND", "K_ROW", "K8b", "fpi_debt_corporate")]["value"]
    assert abs(g + c - bop_old("ka.portfolio.in_india.fiis.debt")) < 1e-5
    sebi = v("finsector_markets_sebi_foreign", "t60.net_investment.debt_general.current")
    assert abs(g - sebi) <= 0.03 * sebi


def test_constraints_census():
    acc = accounts()
    hh, e6, g2 = acc["HH"], acc["NFC"] + acc["FC"], acc["GOV"]
    inst = acc["INST"]
    e8 = [a for a in (acc["NFC"] + acc["FC"] + acc["GOV"])]
    rec_rows = acc["COM"] + acc["FAC"] + hh + e6 + g2
    exp = {
        "row.r11_total": (
            "R11",
            hh,
            ["R_ROW"],
            "R11a",
            None,
            nas("other_current_transfers_to_resident_sectors_other_than_gener"),
        ),
        "row.r12_total": (
            "R12",
            ["R_ROW"],
            hh,
            "R12a",
            None,
            nas("other_current_transfers_by_resident_sectors_other_than_gener"),
        ),
        "row.r13_total": (
            "R13",
            e8,
            ["R_ROW"],
            "R13",
            None,
            nas("property_and_entrepreneurial_income_from_rest_of_the_world"),
        ),
        "row.r14_total": (
            "R14",
            ["R_ROW"],
            e8,
            "R14,R14a",
            None,
            nas("property_and_entrepreneurial_income_to_the_rest_of_the_world"),
        ),
        "row.r14a_total": (
            "R14a",
            ["R_ROW"],
            acc["NFC"] + [a for a in acc["FC"] if a != "E_RBI"],
            "R14a",
            None,
            v("mospi_nas_2026_s1_9", "s1_9.reinvested_earnings_of_foreign_companies_in_private_corporat.current"),
        ),
        "row.current_receipts": ("K5", rec_rows, ["R_ROW"], None, None, nas("current_receipts")),
        "row.current_disbursements": ("K5", ["R_ROW"], rec_rows + ["X_DISC"], None, None, nas("current_disbursements")),
        "row.k8b_liabilities_to_row": (
            "K8b",
            inst,
            ["K_ROW"],
            "K8b",
            None,
            nas("net_incurrence_of_foreign_liabilities"),
        ),
        "row.k8b_assets_from_row": (
            "K8b",
            ["K_ROW"],
            inst,
            "K8b",
            None,
            nas("net_acquisition_of_foreign_financial_assets"),
        ),
        "row.fpi_debt": (
            "K8b",
            ["I_GSEC", "I_CBND"],
            ["K_ROW"],
            "K8b",
            None,
            bop_old("ka.portfolio.in_india.fiis.debt"),
        ),
        "row.r14_type.di": (
            "R14",
            ["R_ROW"],
            e8,
            "R14,R14a",
            {"di_distributed", "reinvested_earnings"},
            bpm6("bpm6_1_b_2_1.debit"),
        ),
        "row.r14_type.pi": (
            "R14",
            ["R_ROW"],
            e8,
            "R14",
            {"fpi_gsec_interest", "fpi_sdl_interest", "fpi_tbill_interest", "pi_other"},
            bpm6("bpm6_1_b_2_2.debit"),
        ),
        "row.r14_type.oi": (
            "R14",
            ["R_ROW"],
            e8,
            "R14",
            {"ext_assistance_interest", "nri_deposit_interest", "oi_other_interest"},
            bpm6("bpm6_1_b_2_3.debit"),
        ),
        "row.r14_type.reserves": ("R14", ["R_ROW"], e8, "R14", {"reserve_asset_debit"}, bpm6("bpm6_1_b_2_4.debit")),
    }
    rows = con().execute(f"select * from '{_p(BLOCKS / 'rest_of_world_constraints.parquet')}'").fetchall()
    cols = [
        d[0]
        for d in con()
        .execute(f"select * from '{_p(BLOCKS / 'rest_of_world_constraints.parquet')}' limit 0")
        .description
    ]
    got = {r[cols.index("constraint_id")]: dict(zip(cols, r, strict=True)) for r in rows}
    assert set(got) == set(exp)
    allent = all_entries()
    for cid, (ref, rws, cls, refs, comps, target) in exp.items():
        d = got[cid]
        assert d["ref"] == ref, cid
        assert set(d["rows"].split(",")) == set(rws), cid
        assert set(d["cols"].split(",")) == set(cls), cid
        assert (d["refs"] or None) == refs, (cid, d["refs"])
        assert (set(d["components"].split(",")) if d["components"] else None) == comps, cid
        assert abs(d["target"] - target) < 1e-6, (cid, d["target"], target)
        assert d["kind"] == "equal" and d["tol_abs"] == 1.0 and d["tol_rel"] == 0.0, cid
        # every constraint holds on the assembled prior of all built blocks
        sel = sum(
            x["value"] for x in allent
            if x["row"] in set(rws) and x["col"] in set(cls)
            and (refs is None or x["ref"] in refs.split(","))
            and (comps is None or x["component"] in comps)
        )  # fmt: skip
        assert abs(sel - target) <= 1.0, (cid, sel, target)
        p = prov()[d["prov_id"]]
        assert p["status"] == "official", cid


def test_checks_targets():
    rows = (
        con()
        .execute(f"select check_id, sam_value, target, ok from '{_p(BLOCKS / 'rest_of_world_checks.parquet')}'")
        .fetchall()
    )
    got = {r[0]: r for r in rows}
    assert len(got) == 29 and all(r[3] for r in rows)
    q = -sum(
        v("external_sector_bop_bpm6_quarterly", "bpm6q.inr.bpm6_3_5.net.current", f"Q{i} {YEAR}") for i in (1, 2, 3, 4)
    )
    exp = {
        "d2_vs_nas61": nas("adjustment_for_cif_in_import_of_services"),
        "fpi_gsec_vs_sebi": v("finsector_markets_sebi_foreign", "t60.net_investment.debt_general.current"),
        "k5_bop_bridge": bpm6("bpm6_1_c_2.net"),
        "k5_vs_surplus": -nas("surplus_on_current_transactions"),
        "k8b_errors_omissions": bpm6("bpm6_5.net"),
        "k8b_fdi_in_india": bpm6("bpm6_3_1_a.net"),
        "k8b_fpi_in_india": bpm6("bpm6_3_2_a.net"),
        "k8b_odi": -bpm6("bpm6_3_1_b.net"),
        "k8b_nri_vs_hbs_flow": v("external_sector_nri_deposits", "nri.flow.inr.total.current"),
        "k8c_vs_quarters": q,
        "r11_vs_bop": bpm6("bpm6_1_c_1.credit"),
        "r11_vs_invisibles": v("external_sector_invisibles_annual", "invis.inr.private_transfers.receipts.current"),
        "r12_vs_bop": bpm6("bpm6_1_c_1.debit"),
        "r13_reserves_vs_bop": bpm6("bpm6_1_b_2_4.credit"),
        "r14_vs_invisibles": v("external_sector_invisibles_annual", "invis.inr.income.investment.payments.current"),
        "r14a_vs_bop": bpm6("bpm6_3_1_a_1_2.credit"),
        "r_row_disbursements": nas("current_disbursements"),
        "r_row_receipts": nas("current_receipts"),
        "p6_plus_d2_vs_nas_imports": nas("imports"),
        "k8b_net_lending": -nas("net_lending_to_the_rest_of_the_world_13_14_15_16_or_18_19"),
    }
    for cid, t in exp.items():
        assert abs(got[cid][2] - t) < 1e-6, (cid, got[cid][2], t)


def test_r_row_and_k_row_close_on_the_prior_of_all_built_blocks():
    """R_ROW and K_ROW close with production P5/P6, factors V3/V4, government K6 and this block (no R15 anywhere)."""
    ent = all_entries()
    assert not [d for d in ent if d["ref"] == "R15"]
    for acct in ("R_ROW", "K_ROW"):
        row = sum(d["value"] for d in ent if d["row"] == acct)
        col = sum(d["value"] for d in ent if d["col"] == acct)
        assert abs(row - col) < 0.01, (acct, row, col)
    # which blocks touch the RoW accounts, and with which refs
    touch = sorted(
        {(d["block"], d["ref"]) for d in ent if "R_ROW" in (d["row"], d["col"]) or "K_ROW" in (d["row"], d["col"])}
    )
    allowed = {("factors", "V3"), ("factors", "V4"), ("government", "K6"), ("production", "P5"), ("production", "P6")}
    others = {t for t in touch if t[0] != "rest_of_world"}
    assert others <= allowed, others
    # government's K6 RoW entries net to NAS (XR-14): capital transfers GG + non-GG, less NPNFA
    k6 = sum(d["value"] for d in ent if d["ref"] == "K6" and d["col"] == "K_ROW") - sum(
        d["value"] for d in ent if d["ref"] == "K6" and d["row"] == "K_ROW"
    )
    nas_k6 = (
        nas("capital_transfers_to_general_government_from_the_rest_of_the")
        + nas("capital_transfers_to_corporations_households_and_npishs_net")
        - nas("acquisitions_less_disposal_of_non_produced_non_financial_ass")
    )
    assert abs(k6 - nas_k6) < 0.01


def test_no_double_counting_with_other_blocks():
    ent = all_entries()
    own = {(d["row"], d["col"]) for d in ent if d["block"] == "rest_of_world"}
    # no other block writes any cell this block writes (RoW property income, remittances, K8b/K8c, D2)
    clash = [d for d in ent if d["block"] != "rest_of_world" and (d["row"], d["col"]) in own]
    assert not clash, clash[:5]
    # fincorp writes nothing with R_ROW / K_ROW (plan s.4: RoW property income is owned here, XR-4/XR-12)
    assert not [d for d in ent if d["block"] == "fincorp" and ({d["row"], d["col"]} & {"R_ROW", "K_ROW"})]
    # nobody else writes the X_DISC column (D2 here, D3 capital_financial, D4 production are the only X_DISC payments)
    xcol = sorted({(d["block"], d["ref"]) for d in ent if d["col"] == "X_DISC"})
    assert ("rest_of_world", "D2") in xcol and all(r in ("D2", "D3", "D4") for _, r in xcol), xcol
    # capital_financial mirrors every K8b counterpart exactly once (K7b row_cp_<line>), except K8c's reserves
    # (posted here as I_RESV <- K_RBI) and the unallocated K9 lines
    cp = sat("row_financial_counterparts")
    mirror: dict[tuple[str, str, str], float] = {}
    for d in ent:
        if d["block"] == "capital_financial" and d["ref"] == "K7b" and d["component"].startswith("row_cp_"):
            line = d["component"][len("row_cp_") :]
            k = (line, d["row"], d["col"])
            mirror[k] = mirror.get(k, 0.0) + d["value"]
    expect: dict[tuple[str, str, str], float] = {}
    for r in cp:
        if r["counterpart"] == "unallocated_k9" or r["line"] == "reserve_assets":
            continue
        k = (
            (r["line"], r["counterpart"], r["instrument"])
            if r["direction"] == "row_acquires"
            else (r["line"], r["instrument"], r["counterpart"])
        )
        expect[k] = expect.get(k, 0.0) + r["value"]
    assert set(mirror) == set(expect), (sorted(set(expect) - set(mirror)), sorted(set(mirror) - set(expect)))
    assert all(abs(mirror[k] - x) < TOL for k, x in expect.items())
    # no other block books reserve-asset transactions (K8c is the only I_RESV <- K_RBI)
    assert [d["block"] for d in ent if "I_RESV" in (d["row"], d["col"])] == ["rest_of_world", "rest_of_world"]


def test_row_financial_counterparts_keys():
    """Counterpart shares recomputed: each K8b entry's rows add up to it; FLA t8 equity/debt, ECB registrations, F51."""
    ent = entries()
    cp = sat("row_financial_counterparts")
    by_line: dict[str, dict[str, float]] = {}
    for r in cp:
        by_line.setdefault(r["line"], {})[r["counterpart"]] = r["value"]
    for (_row, _col, ref, comp), d in ent.items():
        if ref == "K8b":
            assert abs(sum(by_line[comp].values()) - d["value"]) < TOL, comp
    fc = v("external_sector_fla_census", "fla.t8.g.financial_and_insurance_activities.equity", D1, FLA_V) / v(
        "external_sector_fla_census", "fla.t8.total.equity", D1, FLA_V
    )
    fcd = v("external_sector_fla_census", "fla.t8.g.financial_and_insurance_activities.debt", D1, FLA_V) / v(
        "external_sector_fla_census", "fla.t8.total.debt", D1, FLA_V
    )
    for line, key in (("fdi_equity", fc), ("fpi_equity", fc), ("fpi_debt_corporate", fc), ("fdi_debt", fcd)):
        tot = sum(by_line[line].values())
        assert abs(by_line[line]["K_NFPR"] - tot * (1 - key)) < TOL, line
    for inst in ("E_BANK", "E_NBFC", "E_NFPR"):
        k = {"E_BANK": "K_BANK", "E_NBFC": "K_NBFC", "E_NFPR": "K_NFPR"}[inst]
        assert (
            abs(by_line["fdi_reinvested_earnings"][k] - ent[("R_ROW", inst, "R14a", "reinvested_earnings")]["value"])
            < TOL
        )
    f = _ds_path("external_sector_ecb_monthly_2324")
    fin, tot = (
        con()
        .execute(
            f"select sum(value) filter (where industry like 'financial_service_activities_except_insurance_and_pension%'), sum(value) from '{f}' where series_id not like 'ecb.total.%'"
        )
        .fetchone()
    )
    assert abs(by_line["ecb"]["K_NBFC"] - bop_old("ka.loans.ecb.to_india") * fin / tot) < TOL
    fsf = "rbi_financial_accounts_fsf_balance_sheets"
    f51 = {
        cp_: avg(fsf, f"fsf.row.liabilities.outstanding.f51.{cp_}.current") for cp_ in ("nfc_pvt", "fc_ofc", "fc_odc")
    }
    for line in ("odi_equity", "odi_reinvested_earnings"):
        tot_ = sum(by_line[line].values())
        assert abs(by_line[line]["K_NFPR"] - tot_ * f51["nfc_pvt"] / sum(f51.values())) < TOL, line
    g = by_line["fpi_debt_gsec"]
    hbs = "rbi_financial_accounts_hbs_gsec_ownership"
    sgs = v(hbs, "t107.sgs.share.fpi", D1) / 100 * v(hbs, "t107.sgs.outstanding.current", D1) - v(
        hbs, "t107.sgs.share.fpi", D0
    ) / 100 * v(hbs, "t107.sgs.outstanding.current", D0)
    assert abs(g["K_GSTA"] - sgs) < TOL


def test_row_property_income_mirrors_the_entries():
    ent = entries()
    rows = sat("row_property_income")
    got = {(r["account"], r["ref"], r["component"]): r for r in rows}
    exp = {}
    for (row, col, ref, comp), d in ent.items():
        if ref in ("R13", "R14", "R14a"):
            acct = row if ref == "R13" else col
            exp[(acct, ref, comp)] = d
    assert set(got) == set(exp)
    for k, d in exp.items():
        assert abs(got[k]["value"] - d["value"]) < 1e-6 and got[k]["entry_prov_id"] == d["prov_id"], k
        assert got[k]["direction"] == ("credit" if k[1] == "R13" else "debit"), k


def test_s3_remittance_sources():
    f = _ds_path("external_sector_remittance_survey")
    src = dict(
        con()
        .execute(
            f"select upper(replace(series_id, 'remit.source_country.', '')), value from '{f}' where series_id like 'remit.source_country.%' and period = '{YEAR}'"
        )
        .fetchall()
    )
    tot = sum(src.values())
    assert abs(tot - 99.8) < 0.05  # external_sector-13
    r11 = nas("other_current_transfers_to_resident_sectors_other_than_gener")
    rows = sat("s3_remittance_sources")
    shares = {r["country"].upper(): r["value"] for r in rows if r["measure"] == "share"}
    inr = {r["country"].upper(): r["value"] for r in rows if r["measure"] == "inr_crore"}
    assert set(shares) == set(inr) and len(shares) == len(src)
    for c, x in src.items():
        assert abs(shares[c] - x / tot) < 1e-6, c
        assert abs(inr[c] - r11 * x / tot) < 0.01, c
    assert abs(sum(inr.values()) - r11) < 0.01


def test_r11a_sensitivity_variants():
    if "households" in stale_deps():
        pytest.skip("V-ROW-5: stale on households; rebuild rest_of_world")
    r11 = nas("other_current_transfers_to_resident_sectors_other_than_gener")
    s_k, cons = r11a_key()
    tot_c = {k: sum(d.values()) for k, d in cons.items()}
    cshare = {k: x / sum(tot_c.values()) for k, x in tot_c.items()}
    hub = dict(s_k)
    for h in ("in-mh", "in-dl"):
        hub[h] = cshare[h]
    variants = {
        "prior": remit_by_group(r11, s_k, cons),
        "hub_neutral": remit_by_group(r11, hub, cons),
        "consumption_only": remit_by_group(r11, {k: x for k, x in cshare.items() if x > 0}, cons),
    }
    variants["band_low"] = {
        g: min(variants[n][g] for n in ("prior", "hub_neutral", "consumption_only")) for g in GROUPS
    }
    variants["band_high"] = {
        g: max(variants[n][g] for n in ("prior", "hub_neutral", "consumption_only")) for g in GROUPS
    }
    rows = sat("r11a_sensitivity")
    assert len(rows) == 50
    for r in rows:
        assert abs(r["value"] - variants[r["variant"]][r["household_group"]]) < TOL, (
            r["variant"],
            r["household_group"],
        )
    for n in ("prior", "hub_neutral", "consumption_only"):
        assert abs(sum(variants[n].values()) - r11) < 1e-5
    # per person, the prior rises with the quintile in each area (plan s.2.1 step 5)
    pop = dict(
        con()
        .execute(
            f"select household_group, value from '{_p(HHSAT / 'hh_keys.parquet')}' where key = 'pop_persons' and measure = 'level'"
        )
        .fetchall()
    )
    for a in ("R", "U"):
        pc = [variants["prior"][f"H_{a}{i}"] / pop[f"H_{a}{i}"] for i in range(1, 6)]
        assert pc == sorted(pc), (a, pc)


def test_r12a_sensitivity_variant():
    if "households" in stale_deps():
        pytest.skip("V-ROW-5: stale on households; rebuild rest_of_world")
    r12 = nas("other_current_transfers_by_resident_sectors_other_than_gener")
    oct_ = bpm6("bpm6_1_c_1_2.debit")
    pf = pfce_levels()
    tot = sum(pf[g] for g in GROUPS)
    alt = {g: oct_ * pf[g] / tot for g in GROUPS}
    for g in ("H_U4", "H_U5"):
        alt[g] += (r12 - oct_) * pf[g] / (pf["H_U4"] + pf["H_U5"])
    prior = {g: 0.0 for g in GROUPS}
    for g in ("H_U4", "H_U5"):
        prior[g] = r12 * pf[g] / (pf["H_U4"] + pf["H_U5"])
    rows = sat("r12a_sensitivity")
    var = {
        "other_transfers_all_groups": alt,
        "prior": prior,
        "band_low": {g: min(alt[g], prior[g]) for g in GROUPS},
        "band_high": {g: max(alt[g], prior[g]) for g in GROUPS},
    }
    assert len(rows) == 40
    for r in rows:
        assert abs(r["value"] - var[r["variant"]][r["household_group"]]) < TOL, (r["variant"], r["household_group"])


def test_s1_s2_totals():
    rows = (
        con()
        .execute(
            f"select flow, partner_type, measure, sum(value) from '{_p(SAT / 's1_goods_by_partner.parquet')}' group by all"
        )
        .fetchall()
    )
    usd = {}
    inr = {}
    for flow, pt, m, x in rows:
        if pt == "memo_reimports":
            continue
        (usd if m == "usd_mn" else inr)[flow] = (usd if m == "usd_mn" else inr).get(flow, 0.0) + x
    fx = v("external_sector_fx_inr_usd", "t133.usd_fy_average")
    for flow, s in (("exports", "imts.exports_fob.g001.current"), ("imports", "imts.imports_cif.g001.current")):
        world = v("trade_satellites_imf_imts_fy", s, YEAR)
        assert abs(usd[flow] - world) < 0.01, flow
        assert abs(inr[flow] - world * fx / 10) < 0.5, flow
    rows = (
        con()
        .execute(
            f"select flow, bop_item, sum(value) from '{_p(SAT / 's2_services_by_partner.parquet')}' where partner is not null group by all"
        )
        .fetchall()
    )
    for flow, item, x in rows:
        side = "credit" if flow == "exports" else "debit"
        assert abs(x - bpm6(f"{item}.{side}")) < 0.01, (flow, item)
    si = dict(
        con()
        .execute(
            f"select partner, value from '{_p(SAT / 's2_services_by_partner.parquet')}' where flow = 'exports' and bop_item = 'bpm6_1_a_b_9'"
        )
        .fetchall()
    )
    tot_si = bpm6("bpm6_1_a_b_9.credit")
    for iso, reg in (("USA", "united_states_of_america"), ("GBR", "united_kingdom"), ("CAN", "canada")):
        share = v("external_sector_ites_survey", f"ites.t5.{reg}.share")
        assert abs(si[iso] / tot_si * 100 - share) < 0.05, iso


def test_provenance_inputs_resolve_and_status_honest():
    clean_ids = set()
    for f in CLEAN.glob("*/_provenance.parquet"):
        clean_ids |= {r[0] for r in con().execute(f"select prov_id from '{_p(f)}'").fetchall()}
    sam_ids = {r[0] for r in con().execute(f"select prov_id from '{_p(BLOCKS)}/*_provenance.parquet'").fetchall()}
    for pid, p in prov().items():
        assert p["method"], pid
        ins = [x for x in (p["inputs"] or "").split(",") if x]
        if p["status"] in ("official", "derived"):
            assert ins, pid
        for i in ins:
            if i.startswith("sam_households:") and "households" in stale_deps():
                continue  # V-ROW-5: a stale block cites the households records it read; checked after a rebuild
            assert i in clean_ids or i in sam_ids, (pid, i)
    # the key records cite the clean records the verifier used
    ent = entries()

    def ins_of(k):
        return set(prov()[ent[k]["prov_id"]]["inputs"].split(","))

    assert val("union_fiscal_fa_expenditure", "fa9.2049.02.total")[1] in ins_of(
        ("R_ROW", "G_CEN", "R14", "ext_assistance_interest")
    )
    assert val("io_tables_sut_supply", "supply.cif_adj.cif.current")[1] in ins_of(
        ("R_ROW", "X_DISC", "D2", "cif_reconciliation")
    )
    assert val("rbi_banking_corporate_rbi_accounts", "sch13.b.sub_total.current", vintage=AR_V)[1] in ins_of(
        ("E_RBI", "R_ROW", "R13", "reserve_asset_income")
    )
    assert val("external_sector_fla_census", "fla.t8.total.equity", D1, FLA_V)[1] in ins_of(
        ("R_ROW", "E_NFPR", "R14a", "reinvested_earnings")
    )
    assert val("mospi_nas_2026_s1_9", "s1_9.net_capital_inflow_from_row.current")[1] in ins_of(
        ("K_ROW", "R_ROW", "K5", "total")
    )
    # official records are over official clean inputs only
    cstat = {}
    for f in CLEAN.glob("*/_provenance.parquet"):
        cstat |= dict(con().execute(f"select prov_id, status from '{_p(f)}'").fetchall())
    for pid, p in prov().items():
        if p["status"] == "official":
            for i in p["inputs"].split(","):
                assert cstat.get(i, "official") == "official", (pid, i, cstat.get(i))


def test_r11a_sensitivity_record_cites_the_r11a_record():
    """V-ROW-1 (fixed by the builder 2026-09-30; was a strict xfail): the r11a_sensitivity record cites R11a's record."""
    r11a_pid = {d["prov_id"] for k, d in entries().items() if k[2] == "R11a"}
    sens_pid = {r["prov_id"] for r in sat("r11a_sensitivity")}
    assert len(r11a_pid) == 1 and len(sens_pid) == 1
    ins = set(prov()[sens_pid.pop()]["inputs"].split(","))
    r12a_pid = {d["prov_id"] for k, d in entries().items() if k[2] == "R12a"}
    assert r11a_pid <= ins and not (r12a_pid & ins)


def test_method_texts_have_no_unformatted_placeholders():
    """V-ROW-2 (fixed by the builder 2026-09-30; was a strict xfail): no method text keeps a '{...}' placeholder."""
    bad = [pid for pid, p in prov().items() if "{" in p["method"] or "}" in p["method"]]
    assert not bad, bad
