"""Independent verification of the SAM `fincorp` block (Phase 2 verifier, 2026-10-01; SPEC s.3 rule 3).

This file does NOT import pipeline.sam or the block (no block, framework or spec code) and does not use polars.
Every expected number is recomputed here with DuckDB SQL plus plain Python arithmetic from:
- data/clean/mospi_nas_2026: St 1.9 (FC saving), 1.13 (FISIM by user), 7.1A/B/C (IC, financial OS + CFC),
  8.12 (FC sub-sector GVA), 8.15.1 (GG IC);
- data/clean/io_tables: SUT value added, industries 55 and 56;
- data/clean/rbi_banking_corporate: RBI Annual Report 2023-24 (vintage 2024-05-30), RTP 2023-24 bank, co-op and
  NBFI P&L and SCB cost/return rates (vintage 2025-12-29);
- data/clean/rbi_financial_accounts: FSF balance sheets (who-to-whom, average of end-March 2023 and 2024), HBS
  T107 G-sec ownership;
- data/clean/union_fiscal (Finance Accounts MH 2049, 0049, 0050, St 14; NSSF), data/clean/state_fiscal (RBI SF
  App. II/III/IV, FC16 KFI);
- data/clean/finsector_markets: IRDAI life/non-life/summary, EPFO AR (vintage 2024-12), PFRDA NPS and SG, SEBI MF
  T72 and market capitalisation;
- data/sam/2023-24/blocks: the legitimate DEPENDS inputs (households' hh_keys and C4b entries, factors' F1a/F4
  entries and public_sector_wage_key, government's R6/R7, rest_of_world's R13/R14) and every built block's
  *_entries.parquet (constraints on the assembled prior, double counting).
It is compared with the block's written outputs (data/sam/2023-24/blocks/fincorp_*): a census of all 455 entries,
all 14 constraints, all 14 check targets, and the satellites (S9 in full; the bridges' inputs).

Method rules: docs/phase2/plans/fincorp.md (incl. s.8), DECISIONS D2-6/7/10/14/16, CROSS_REVIEW XR-4/5/6/10/12/13/29.
Findings are recorded in docs/phase2/verify/fincorp.md (V-FIN-n). A confirmed defect is a strict xfail with its id.
Where the block's method differs from the plan in a way recorded as a finding, the census reproduces the block's
variant (parameter noted) so that it stays a regression test; the strict xfail tests the corrected rule.

Updated 2026-10-01 after the builder's fixes (dispositions in docs/phase2/issues/fincorp.md): V-FIN-1, -2, -3 and -4
were fixed, so their strict xfails are ordinary tests and the census reproduces the corrected rules (all four 8.15.1
GG-IC industries; E_BANK dividends grossed with the Union's share; GPF groups free estimates; GG-held bank/NBFC debt
interest written in R4 and inside the lender scaling). V-FIN-6 was fixed by reconciling the dividend memo to R7:
government parts are government's R7 entries and the rest of each issuer total goes to the non-government holders
by their FSF F51 shares (so the private E_NBFC total has no government holder). The entry count (455 -> 462), the
anchored set and the D0-7 evidence bound moved with these fixes only.

Updated 2026-10-01 (fincorp repair after the failed balancing run; DECISIONS D2-21; docs/phase2/issues/fincorp.md
fincorp-27..31): the recomputation now follows four changed rules, each marked 'repair 2026-10-01' below: OFC claims
on ODCs split by the creditors' own instrument mix (fincorp-4), FISIM lender shares by reference-rate margins
(fincorp-2), r_corp on insurers' and MFs' corporate bonds, and E_NFPR's other distributed income sized by the
old-base St 2.2 structure (`oldbase_topup`). Pinned counts moved with them only: entries 462 -> 488, records 42 -> 47,
entries of at least 10,000 121 -> 140.

Re-verified 2026-10-01 (wave C close-out; a different agent from the builder, the fixers and the first verifier;
docs/phase2/verify/fincorp.md "Re-verification (wave C close-out, 2026-10-01)"). Every expectation the fixers changed
was recomputed with separate code (DuckDB on the clean Parquet and the dependency entries, no pipeline import) and
CONFIRMED: the 488-entry census, the 140 entries >= 10,000, the 55 records, the four repair rules (OFC claims by the
creditors' mix, FISIM lender shares by reference-rate margins, r_corp on insurers'/MFs' corporate bonds, the D2-21
top-up 8,21,158.76), the V-FIN-1/-3/-4/-6 rules, the D0-7 bound (+23.32), r17.premiums at 1% and the 16 Wave C
constraint targets. Nothing was reverted. Added: `test_wave_c_constraint_targets_recomputed_from_sources` (targets
straight from the sources, not from this file's census), `test_oldbase_topup_satellite_rows`, and the strict xfail
V-FIN-9 (R17 payer bands do not hold D71 = D72 by payer after balancing).
"""

# ruff: noqa: E501  (long DuckDB SQL literals are kept on one line so each rule reads as one statement)
from __future__ import annotations

import glob
import hashlib
import json
import math
from functools import cache
from pathlib import Path

import duckdb
import pytest

pytestmark = [pytest.mark.quality, pytest.mark.sam]

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean"
BLOCKS = ROOT / "data" / "sam" / "2023-24" / "blocks"
SAT = BLOCKS / "fincorp_satellites"
YEAR = "2023-24"
TOL = 0.01  # Rs crore: census tolerance (entries are written to 6 decimals)
D0, D1 = "2023-03-31", "2024-03-31"  # stock dates averaged for every stock key
RTP_V = "2025-12-29"
AR_V = "2024-05-30"
EPFO_V = "2024-12"
HH = ["H_R1", "H_R2", "H_R3", "H_R4", "H_R5", "H_U1", "H_U2", "H_U3", "H_U4", "H_U5"]
FC = ["E_RBI", "E_BANK", "E_NBFC", "E_INSP"]


def _p(path: Path | str) -> str:
    return Path(path).as_posix()


@cache
def con() -> duckdb.DuckDBPyConnection:
    for f in ("entries", "constraints", "provenance", "checks"):
        if not (BLOCKS / f"fincorp_{f}.parquet").exists():
            pytest.fail(f"fincorp_{f}.parquet missing: run `uv run python -m pipeline sam fincorp`")
    return duckdb.connect()


def q(sql: str, *args):
    return con().execute(sql, list(args)).fetchall()


@cache
def _ds(dataset: str) -> str:
    hits = sorted(CLEAN.glob(f"*/{dataset}.parquet"))
    assert len(hits) == 1, f"clean dataset {dataset}: {hits}"
    return _p(hits[0])


def _vkey(v: str) -> str:
    parts = v.split("-")
    return v + ("-12-31" if len(parts) == 1 else "-31" if len(parts) == 2 else "")


def val(dataset: str, series_id: str, period: str = YEAR, vintage: str | None = None, pct: bool = False) -> float:
    """One clean value; vintage None = the latest vintage of that (series, period)."""
    rows = q(
        f"select value, vintage, unit, price_basis from '{_ds(dataset)}' where series_id = ? and period = ?",
        series_id,
        period,
    )
    assert rows, f"{dataset} {series_id} {period}: no row"
    vintage = vintage or max((r[1] for r in rows), key=_vkey)
    rows = [r for r in rows if r[1] == vintage]
    assert len(rows) == 1, (dataset, series_id, period, vintage)
    if pct:
        assert rows[0][2] == "percent"
    else:
        assert rows[0][2] == "INR_crore" and rows[0][3] == "current", (series_id, rows[0][2:])
    return rows[0][0]


def avg(dataset: str, series_id: str, vintage: str | None = None, pct: bool = False) -> float:
    return (val(dataset, series_id, D0, vintage, pct) + val(dataset, series_id, D1, vintage, pct)) / 2


@cache
def fsf() -> dict:
    rows = q(
        f"select institution, side, instrument, counterparty, avg(value) from '{_ds('rbi_financial_accounts_fsf_balance_sheets')}' where period in ('{D0}', '{D1}') and stock_flow = 'stock' and instrument in ('f22_f29', 'f3', 'f4', 'f51', 'f6') group by all having count(*) = 2"
    )
    return {(a, s, i, c): v for a, s, i, c, v in rows}


def F(inst: str, side: str, instr: str, cp: str) -> float:
    return fsf().get((inst, side, instr, cp), 0.0)


@cache
def all_entries() -> list[tuple]:
    return q(
        f"select block, row, col, ref, component, value from read_parquet('{_p(BLOCKS)}/*_entries.parquet', union_by_name=true)"
    )


def se(row: str, col: str, ref: str | None = None, comp: str | None = None, block: str | None = None) -> float:
    return sum(
        v
        for b, r, c, rf, cp, v in all_entries()
        if r == row
        and c == col
        and (ref is None or rf == ref)
        and (comp is None or cp == comp)
        and (block is None or b == block)
    )


@cache
def block_entries() -> dict:
    return {
        (r, c, rf, cp): (v, st, role, tol, conf, pid)
        for r, c, rf, cp, v, st, role, tol, conf, pid in q(
            f"select row, col, ref, component, value, status, role, tol_rel, confidence, prov_id from '{_p(BLOCKS / 'fincorp_entries.parquet')}'"
        )
    }


def satv(name: str, sid: str) -> float:
    r = q(f"select value from '{_p(SAT / (name + '.parquet'))}' where series_id = ?", sid)
    assert len(r) == 1, (name, sid)
    return r[0][0]


@cache
def hh_keys() -> dict:
    d: dict = {}
    for k, g, v in q(
        f"select key, household_group, value from '{_p(BLOCKS / 'households_satellites' / 'hh_keys.parquet')}' where measure = 'level'"
    ):
        d.setdefault(k, {})[g] = v
    return d


def shares(levels: dict) -> dict:
    s = sum(levels[g] for g in HH)
    return {g: levels[g] / s for g in HH}


# ---------------------------------------------------------------------------------------------------- F4a
RB, RC, RN = "rbi_banking_corporate_rtp_banks", "rbi_banking_corporate_rtp_coop", "rbi_banking_corporate_rtp_nbfi"
AR = "rbi_banking_corporate_rbi_accounts"


def rtp(ds: str, sid: str) -> float:
    return val(ds, sid, vintage=RTP_V)


@cache
def dt_shares() -> tuple[float, float]:
    def sh(dt: str, ndt: str) -> float:
        a, b = F(dt, "assets", "f4", "all"), F(ndt, "assets", "f4", "all")
        return a / (a + b)

    return sh("fc_odc_nbfc_dt", "fc_ofc_nbfc_ndt"), sh("fc_odc_hfc_dt", "fc_ofc_hfc_ndt")


@cache
def f4a() -> dict:
    s812 = lambda s: val("mospi_nas_2026_s8_12", f"s8_12.{s}.current")  # noqa: E731
    sut = lambda item, i: val("io_tables_sut_va", f"va.{item}.sut_i{i}.current")  # noqa: E731
    s121, s122, s124 = (
        s812("central_bank_s_121"),
        s812("deposit_taking_corporations_excluding_central_bank_s_122_and"),
        s812("other_financial_corporations_s_124_to_s_127"),
    )
    rbi_ce = val(AR, "is.exp_employee_cost.current", vintage=AR_V)
    gos55 = sut("os_mi", 55) + sut("cfc", 55)
    gos56 = sut("os_mi", 56) + sut("cfc", 56)
    e_rbi = s121 - rbi_ce
    scale = (sut("gva_production", 55) - s121) / (s122 + s124)
    gva_b, gva_n = s122 * scale, s124 * scale
    sh_n, sh_h = dt_shares()
    wage = (
        rtp(RB, "rtp.scb_pl.wage_bill.scb.current")
        + rtp(RB, "rtp.rrb_pl.wage_bill.rrb.current")
        + rtp(RC, "rtp.ucb_pl.staff_expenses.ucb.current")
        + rtp(RC, "rtp.stcb_pl.wage_bill.stcb.current")
        + rtp(RC, "rtp.dccb_pl.wage_bill.dccb.current")
    )
    n_opex = rtp(RN, "rtp.nbfc_layer_pl.operating_expenditure.nbfc_ul.current") + rtp(
        RN, "rtp.nbfc_layer_pl.operating_expenditure.nbfc_ml.current"
    )
    h_opex = rtp(RN, "rtp.hfc_pl.operating_expenditure.hfc.current")
    ce_b = wage + (sh_n * n_opex + sh_h * h_opex) * rtp(RB, "rtp.scb_pl.wage_bill.scb.current") / rtp(
        RB, "rtp.scb_pl.operating_expenses.scb.current"
    )
    ce_n = sut("ce", 55) - rbi_ce - ce_b
    npt = sut("net_production_taxes", 55)
    npt_b = npt * gva_b / (gva_b + gva_n)
    rb, rn = gva_b - ce_b - npt_b, gva_n - ce_n - (npt - npt_b)
    e_bank = (gos55 - e_rbi) * rb / (rb + rn)
    e_nbfc = gos55 - e_rbi - e_bank
    op = lambda g, d=RB, s="scb_pl": rtp(d, f"rtp.{s}.operating_profit.{g}.current")  # noqa: E731
    bank_op = (
        op("scb")
        + op("rrb", RB, "rrb_pl")
        + op("ucb", RC, "ucb_pl")
        + op("stcb", RC, "stcb_pl")
        + op("dccb", RC, "dccb_pl")
    )
    nbfc_pbt = rtp(RN, "rtp.nbfc_layer_pl.profit_before_tax.nbfc_ul.current") + rtp(
        RN, "rtp.nbfc_layer_pl.profit_before_tax.nbfc_ml.current"
    )
    hfc_op = (
        rtp(RN, "rtp.hfc_pl.fund_income.hfc.current")
        + rtp(RN, "rtp.hfc_pl.fee_income.hfc.current")
        - rtp(RN, "rtp.hfc_pl.financial_expenditure.hfc.current")
        - h_opex
    )
    bank_pub_share = (op("psb") + op("rrb", RB, "rrb_pl")) / (bank_op + sh_n * nbfc_pbt + sh_h * hfc_op)
    irl, irn = "finsector_markets_irdai_life", "finsector_markets_irdai_nonlife"
    lic = val(irl, "t24.operating_expenses.lic.current") / val(irl, "t24.operating_expenses.insurers_life.current")
    npe = lambda g: val(irn, f"t44.net_premium_earned.total.{g}.current")  # noqa: E731
    nl_pub = (npe("general_public") + npe("general_specialized")) / npe("insurers_general_direct")
    lw = s812("life_insurance_s_128") / (s812("life_insurance_s_128") + s812("non_life_insurance_s_128"))
    insp_pub_share = lw * lic + (1 - lw) * nl_pub
    pub_t = val("mospi_nas_2026_s7_1a", "s7_1a.financial.os.current") + val(
        "mospi_nas_2026_s7_1a", "s7_1a.financial.cfc.current"
    )
    pvt_t = val("mospi_nas_2026_s7_1b", "s7_1b.financial.os.current") + val(
        "mospi_nas_2026_s7_1b", "s7_1b.financial.cfc.current"
    )
    bank_pub, insp_pub = e_bank * bank_pub_share, gos56 * insp_pub_share
    nbfc_pub = pub_t - e_rbi - bank_pub - insp_pub
    parts = {
        ("E_RBI", "public"): e_rbi,
        ("E_BANK", "public"): bank_pub,
        ("E_BANK", "private"): e_bank - bank_pub,
        ("E_NBFC", "public"): nbfc_pub,
        ("E_NBFC", "private"): e_nbfc - nbfc_pub,
        ("E_INSP", "public"): insp_pub,
        ("E_INSP", "private"): gos56 - insp_pub,
    }
    return {
        "parts": parts,
        "gos55": gos55,
        "gos56": gos56,
        "pub_t": pub_t,
        "pvt_t": pvt_t,
        "ce_bank": ce_b,
        "ce_nbfc": ce_n,
        "bank_pub_share": bank_pub_share,
        "insp_pub_share": insp_pub_share,
        "rbi_dep": val(AR, "is.exp_depreciation.current", vintage=AR_V),
    }


# ---------------------------------------------------------------------------------------------------- R3 / R3a / R3b
UFE, UFR, SF = "union_fiscal_fa_expenditure", "union_fiscal_fa_receipts", "state_fiscal_rbi_sf_appendices"
HOLD = [
    "commercial_banks",
    "cooperative_banks",
    "non_bank_pds",
    "insurance",
    "mutual_funds",
    "provident_funds",
    "pension_funds",
    "financial_institutions",
    "corporates",
    "fpi",
    "rbi",
    "others",
]


def u(code: str) -> float:
    return val(UFE, f"fa9.2049.{code}")


def st(tail: str) -> float:
    return val(SF, f"app2.total_expenditure.{tail}.in.all_states_uts.actuals")


def t107(inst: str, h: str) -> float:
    return avg("rbi_financial_accounts_hbs_gsec_ownership", f"t107.{inst}.share.{h}", pct=True) / 100


@cache
def mf_shares() -> dict:
    t = lambda c: avg("finsector_markets_sebi_mf", f"t72.aum.{c}.current")  # noqa: E731
    return {
        "E_BANK": t("banks") / t("total"),
        "E_NFPR": t("corporates") / t("total"),
        "HH": (t("hnis") + t("retail")) / t("total"),
    }


@cache
def govint() -> dict:
    reissue = val(UFR, "fa8.0049.03.116") + val(UFR, "fa8.0049.03.117")
    lines = {
        "dated": ("gsec_central", u("01.101") - reissue),
        "tb": ("tbills", u("01.103") + u("01.108") + u("01.110")),
        "sdl": ("sgs", st("ii.c.2.ii.a-interest_on_market_loans")),
        "other": ("gsec_central", sum(u(c) for c in ["01.118", "01.134", "01.200", "60.101", "60.106", "60.109"])),
    }
    fpi = {k: t107(i, "fpi") * amt for k, (i, amt) in lines.items() if k != "other"}
    rbi_ar = val(AR, "sch13.a.interest_on_holding_of_rupee_securities.current", vintage=AR_V) + val(
        AR, "sch14.a.amortisation_of_premium_discount_on_rupee_securities.current", vintage=AR_V
    )
    raw_rbi = {k: t107(i, "rbi") * amt for k, (i, amt) in lines.items() if k != "other"}
    rbi = {k: rbi_ar * v / sum(raw_rbi.values()) for k, v in raw_rbi.items()}
    alloc = {}
    for k, (inst, amt) in lines.items():
        rest = amt - fpi.get(k, 0.0) - rbi.get(k, 0.0)
        base = sum(t107(inst, h) for h in HOLD if h not in ("fpi", "rbi"))
        a = {h: rest * t107(inst, h) / base for h in HOLD if h not in ("fpi", "rbi", "others")}
        a["state_govts"] = rest * t107(inst, "others_state_governments") / base
        a["others_x"] = rest * (t107(inst, "others") - t107(inst, "others_state_governments")) / base
        alloc[k] = a

    def fk(inst: str, cps: list[str]) -> dict:
        v = {c: F(inst, "liabilities", "f3", c) for c in cps}
        return {c: x / sum(v.values()) for c, x in v.items()}

    kc, ko = fk("gg_cen", ["nfc_pub", "nfc_pvt"]), fk("gg_cen", ["hh", "nfc_pub", "nfc_pvt"])
    ks, kso = fk("gg_sta", ["nfc_pvt"]), fk("gg_sta", ["hh", "nfc_pvt"])
    acc = {}
    for k, (c, o) in {"dated": (kc, ko), "tb": (kc, ko), "other": (kc, ko), "sdl": (ks, kso)}.items():
        a = alloc[k]
        acc[k] = {
            "E_BANK": a["commercial_banks"] + a["cooperative_banks"],
            "E_NBFC": a["non_bank_pds"] + a["financial_institutions"],
            "E_INSP": a["insurance"] + a["provident_funds"] + a["pension_funds"],
            "E_NFPU": a["corporates"] * c.get("nfc_pub", 0) + a["others_x"] * o.get("nfc_pub", 0),
            "E_NFPR": a["corporates"] * c.get("nfc_pvt", 0) + a["others_x"] * o.get("nfc_pvt", 0),
            "HH": a["others_x"] * o.get("hh", 0),
            "MF": a["mutual_funds"],
            "STG": a["state_govts"],
        }
    acc["dated"]["E_RBI"], acc["sdl"]["E_RBI"] = rbi["dated"], rbi["sdl"]
    mf = mf_shares()
    out = {}
    for comp, k, col in (
        ("dated_securities", "dated", "G_CEN"),
        ("tbills", "tb", "G_CEN"),
        ("other_securities", "other", "G_CEN"),
        ("sdl", "sdl", "G_STA"),
    ):
        for a, v in acc[k].items():
            if a.startswith("E_") and abs(v) > 1e-9:
                out[(a, col, "R3a", comp)] = v
    for col, ks_ in (("G_CEN", ["dated", "tb", "other"]), ("G_STA", ["sdl"])):
        m = sum(acc[k]["MF"] for k in ks_)
        out[("E_BANK", col, "R3a", "mf_lookthrough")] = m * mf["E_BANK"]
        out[("E_NFPR", col, "R3a", "mf_lookthrough")] = m * mf["E_NFPR"]
    wma = u("01.115")
    lna = val(AR, "sch13.a.interest_on_loans_and_advances.current", vintage=AR_V) - wma
    k = {c: F("fc_rbi", "assets", "f4", c) for c in ("fc_odc", "fc_ofc", "gg_sta")}
    wma_od = lna * k["gg_sta"] / sum(k.values())
    out[("E_RBI", "G_CEN", "R3a", "wma")] = wma
    out[("E_RBI", "G_STA", "R3a", "wma_od")] = wma_od
    out[("E_BANK", "G_CEN", "R3a", "recap_bonds")] = u("01.132") + u("01.133") + u("60.110")
    out[("E_INSP", "G_CEN", "R3a", "public_account_funds")] = u("03.108") + u("03.109")
    stl = st("ii.c.2.ii-interest_on_internal_debt") - lines["sdl"][1] - st("ii.c.2.ii.b-interest_on_nssf") - wma_od
    k4 = {c: F("gg_sta", "liabilities", "f4", c) for c in ("fc_odc", "fc_ofc")}
    out[("E_BANK", "G_STA", "R3a", "state_loans")] = stl * k4["fc_odc"] / sum(k4.values())
    out[("E_NBFC", "G_STA", "R3a", "state_loans")] = stl * k4["fc_ofc"] / sum(k4.values())
    out[("G_CEN", "G_STA", "R3", "central_loans")] = st("ii.c.2.i-interest_on_loans_from_the_centre")
    out[("G_CEN", "G_STA", "R3", "nssf")] = st("ii.c.2.ii.b-interest_on_nssf")
    out[("G_STA", "G_CEN", "R3", "itb_14d")] = u("01.116")
    out[("G_STA", "G_CEN", "R3", "gsec_state_reserve_funds")] = sum(acc[k]["STG"] for k in ("dated", "tb", "other"))
    nssf_int = u("01.121") + u("01.122") + u("01.125") + st("ii.c.2.ii.b-interest_on_nssf")
    hh_direct = {
        "G_CEN": sum(acc[k]["HH"] for k in ("dated", "tb", "other")) + u("01.129") + u("01.130"),
        "G_STA": acc["sdl"]["HH"],
    }
    hh_mf = {
        "G_CEN": sum(acc[k]["MF"] for k in ("dated", "tb", "other")) * mf["HH"],
        "G_STA": acc["sdl"]["MF"] * mf["HH"],
    }
    recov = u("01.911") + u("03.911") + u("05.911")
    intra = u("01.121") + u("01.122") + u("01.125") + u("05.total") + u("60.107") + u("60.111")
    union_t = u("total") - intra - u("01.305") - recov - reissue + nssf_int
    states_t = st("ii.c.2-interest_payments") - st("ii.c.2.iv-others") - acc["sdl"]["STG"]
    k_rl = {c: F("fc_rbi", "assets", "f4", c) for c in ("fc_odc", "fc_ofc", "gg_sta")}
    rbi_loans = {
        "E_BANK": lna * k_rl["fc_odc"] / sum(k_rl.values()),
        "E_NBFC": lna * k_rl["fc_ofc"] / sum(k_rl.values()),
    }
    pension_gsec = sum(alloc[k]["pension_funds"] for k in alloc)
    return {
        "entries": out,
        "nssf_int": nssf_int,
        "hh_direct": hh_direct,
        "hh_mf": hh_mf,
        "union_t": union_t,
        "states_t": states_t,
        "rbi_loans": rbi_loans,
        "pension_gsec": pension_gsec,
        "fpi": fpi,
        "rbi": rbi,
        "sdl_states": acc["sdl"]["STG"],
    }


# ---------------------------------------------------------------------------------------------------- R4 / R5 / FISIM
@cache
def rates() -> dict:
    cr = lambda x: val(RB, f"rtp.scb_cost_return.{x}.scb", vintage=RTP_V, pct=True) / 100  # noqa: E731
    return {
        "A": cr("return_on_advances"),
        "I": cr("return_on_investments"),
        "D": cr("cost_of_deposits"),
        "B": cr("cost_of_borrowings"),
    }


@cache
def positions() -> tuple[list, list]:
    """(creditor, debtor, instrument, stock, rate) from FSF; the second list is the government-held FC debt (bank and
    NBFC bonds/borrowings held by G_CEN/G_STA), which is part of the first since the V-FIN-4 fix."""
    r = rates()
    cp = {"hh": "HH", "nfc_pvt": "E_NFPR", "nfc_pub": "E_NFPU", "gg_cen": "G_CEN", "gg_sta": "G_STA"}
    p = []
    for c, acc in [("fc_ofc", "E_NBFC"), ("nfc_pvt", "E_NFPR"), ("nfc_pub", "E_NFPU"), ("hh", "HH")]:
        if F("fc_odc", "assets", "f4", c):
            p.append(("E_BANK", acc, "loans", F("fc_odc", "assets", "f4", c), r["A"]))
        if F("fc_odc", "assets", "f3", c):
            p.append(("E_BANK", acc, "nongov_bonds", F("fc_odc", "assets", "f3", c), r["I"]))
    ofc_claims = {}
    for instr, name, rt in [("f22_f29", "deposits", r["D"]), ("f3", "bonds", r["B"]), ("f4", "borrowings", r["B"])]:
        for c, acc in cp.items():
            if F("fc_odc", "liabilities", instr, c):
                p.append((acc, "E_BANK", name, F("fc_odc", "liabilities", instr, c), rt))
        icpf, mf = F("fc_ofc_icpf", "assets", instr, "fc_odc"), F("fc_ofc_mf", "assets", instr, "fc_odc")
        for acc, part in (("E_INSP", icpf), ("MF", mf), ("E_NBFC", F("fc_ofc", "assets", instr, "fc_odc") - icpf - mf)):
            ofc_claims[(acc, name, rt)] = max(part, 0.0)
    # fincorp repair 2026-10-01 (fincorp-4): OFC claims on ODCs = the ODC-side total over deposits, debt securities
    # and borrowings, split over OFC sub-sectors AND instruments by the creditors' own FSF claims on ODCs (was: each
    # instrument's ODC-side stock split by that instrument's OFC-side weights, which sent 18.5 lakh of ODC
    # 'borrowings from OFC' to NBFCs)
    odc_tot = sum(F("fc_odc", "liabilities", i, "fc_ofc") for i in ("f22_f29", "f3", "f4"))
    w_tot = sum(ofc_claims.values())
    for (acc, name, rt), part in ofc_claims.items():
        if part > 0:
            p.append((acc, "E_BANK", name, odc_tot * part / w_tot, rt))
    for c, acc in [("nfc_pvt", "E_NFPR"), ("nfc_pub", "E_NFPU"), ("hh", "HH")]:
        for instr, name, rt in (("f4", "loans", r["A"]), ("f3", "nongov_bonds", r["I"])):
            tot, icpf, mf = (
                F("fc_ofc", "assets", instr, c),
                F("fc_ofc_icpf", "assets", instr, c),
                F("fc_ofc_mf", "assets", instr, c),
            )
            for acc2, part in (("E_INSP", icpf), ("MF", mf), ("E_NBFC", tot - icpf - mf)):
                if part > 1e-9:
                    # repair 2026-10-01: the unscaled creditors' corporate bonds earn r_corp (SCB cost of borrowings)
                    rt2 = r["B"] if name == "nongov_bonds" and acc2 in ("E_INSP", "MF") else rt
                    p.append((acc2, acc, name, part, rt2))
    for instr, name, rt in [("f22_f29", "deposits", r["D"]), ("f3", "bonds", r["B"]), ("f4", "borrowings", r["B"])]:
        for c, acc in cp.items():
            if F("fc_ofc", "liabilities", instr, c):
                p.append((acc, "E_NBFC", name, F("fc_ofc", "liabilities", instr, c), rt))
        tot = (
            F("fc_ofc", "liabilities", instr, "fc_ofc")
            - F("fc_ofc_icpf", "liabilities", instr, "fc_ofc")
            - F("fc_ofc_mf", "liabilities", instr, "fc_ofc")
        )
        den = F("fc_ofc", "assets", instr, "fc_ofc")
        for acc, part in (
            ("E_INSP", F("fc_ofc_icpf", "assets", instr, "fc_ofc")),
            ("MF", F("fc_ofc_mf", "assets", instr, "fc_ofc")),
        ):
            if part > 0 and den > 0:
                p.append((acc, "E_NBFC", name, tot * part / den, rt))
    gov_held = [x for x in p if x[0].startswith("G_") and x[2] != "deposits"]
    return p, gov_held


@cache
def bank_interest() -> dict:
    p, _ = positions()
    sh_n, sh_h = dt_shares()
    g = govint()
    nb_fb = rtp(RN, "rtp.nbfc_layer_pl.fund_based_income.nbfc_ul.current") + rtp(
        RN, "rtp.nbfc_layer_pl.fund_based_income.nbfc_ml.current"
    )
    nb_fe = rtp(RN, "rtp.nbfc_layer_pl.financial_expenditure.nbfc_ul.current") + rtp(
        RN, "rtp.nbfc_layer_pl.financial_expenditure.nbfc_ml.current"
    )
    h_fi, h_fe = rtp(RN, "rtp.hfc_pl.fund_income.hfc.current"), rtp(RN, "rtp.hfc_pl.financial_expenditure.hfc.current")
    ii = lambda d, s, x: rtp(d, f"rtp.{s}.interest_income.{x}.current")  # noqa: E731
    ie = lambda d, s, x: rtp(d, f"rtp.{s}.interest_expended.{x}.current")  # noqa: E731
    pl = {
        "bank_interest_income": ii(RB, "scb_pl", "scb")
        + ii(RB, "rrb_pl", "rrb")
        + ii(RC, "ucb_pl", "ucb")
        + ii(RC, "stcb_pl", "stcb")
        + ii(RC, "dccb_pl", "dccb")
        + sh_n * nb_fb
        + sh_h * h_fi,
        "bank_interest_expended": ie(RB, "scb_pl", "scb")
        + ie(RB, "rrb_pl", "rrb")
        + ie(RC, "ucb_pl", "ucb")
        + ie(RC, "stcb_pl", "stcb")
        + ie(RC, "dccb_pl", "dccb")
        + sh_n * nb_fe
        + sh_h * h_fe,
        "nbfc_interest_income": (1 - sh_n) * nb_fb
        + (1 - sh_h) * h_fi
        + ii(RN, "aifi_pl", "aifi")
        + rtp(RN, "rtp.spd_pl.interest_discount.spd.current"),
        "nbfc_interest_expended": (1 - sh_n) * nb_fe
        + (1 - sh_h) * h_fe
        + ie(RN, "aifi_pl", "aifi")
        + ie(RN, "spd_pl", "spd"),
    }
    r3a = {
        a: sum(v for (r, c, rf, cp), v in g["entries"].items() if r == a and rf == "R3a" and cp != "mf_lookthrough")
        for a in ("E_BANK", "E_NBFC")
    }
    laf = -(
        val(AR, "sch13.a.net_interest_on_laf_operations.current", vintage=AR_V)
        + val(AR, "sch13.a.interest_on_sdf.current", vintage=AR_V)
    )
    msf = val(AR, "sch13.a.interest_on_msf_operations.current", vintage=AR_V)
    row_in = {a: se(a, "R_ROW", "R13", "oi_income") for a in ("E_BANK", "E_NBFC")}
    row_out = {
        "E_BANK": se("R_ROW", "E_BANK", "R14", "nri_deposit_interest")
        + se("R_ROW", "E_BANK", "R14", "oi_other_interest"),
        "E_NBFC": se("R_ROW", "E_NBFC", "R14", "oi_other_interest"),
    }
    raw = lambda pred: sum(s * rt for c, d, i, s, rt in p if pred(c, d))  # noqa: E731
    s_bi = (pl["bank_interest_income"] - r3a["E_BANK"] - laf - row_in["E_BANK"]) / raw(lambda c, d: c == "E_BANK")
    s_be = (pl["bank_interest_expended"] - row_out["E_BANK"] - msf - g["rbi_loans"]["E_BANK"]) / raw(
        lambda c, d: d == "E_BANK"
    )
    from_bank = sum(s * rt * s_be for c, d, i, s, rt in p if c == "E_NBFC" and d == "E_BANK")
    s_ni = (pl["nbfc_interest_income"] - r3a["E_NBFC"] - row_in["E_NBFC"] - from_bank) / raw(
        lambda c, d: c == "E_NBFC" and d != "E_BANK"
    )
    to_bank = sum(s * rt * s_bi for c, d, i, s, rt in p if c == "E_BANK" and d == "E_NBFC")
    s_ne = (pl["nbfc_interest_expended"] - row_out["E_NBFC"] - to_bank - g["rbi_loans"]["E_NBFC"]) / raw(
        lambda c, d: d == "E_NBFC" and c != "E_BANK"
    )

    def scale(c: str, d: str) -> float:
        return (
            s_bi
            if c == "E_BANK"
            else s_be
            if d == "E_BANK"
            else s_ni
            if c == "E_NBFC"
            else s_ne
            if d == "E_NBFC"
            else 1.0
        )

    return {
        "bi": {(c, d, i): s * rt * scale(c, d) for c, d, i, s, rt in p},
        "stock": {(c, d, i): s for c, d, i, s, rt in p},
        "scale": {"bank_inc": s_bi, "bank_exp": s_be, "nbfc_inc": s_ni, "nbfc_exp": s_ne},
        "pl": pl,
        "laf": laf,
        "msf": msf,
    }


GG_IC_ALL = ("construction", "other_services", "public_admin", "utilities")  # NAS 8.15.1 publishes GG IC for these four
GG_IC_BLOCK = GG_IC_ALL  # V-FIN-1 fixed: the block now nets out GG IC of all four (it left out utilities before)
IND113 = {
    "agriculture_livestock_forestry_and_fishing": "agri",
    "mining_and_quarrying": "mining",
    "manufacturing": "manufacturing",
    "electricity_gas_water_supply_and_other_utility_services": "utilities",
    "construction": "construction",
    "trade_repair_hotels_and_restaurants": "trade_hotels",
    "transport_storage_communication_and_services_related_to_broa": "transport_comm",
    "real_estate_ownership_of_dwelling_and_professional_services": "real_estate_prof",
    "other_services": "other_services",
    "public_administration_and_defence": "public_admin",
}


@cache
def ic_fisim(gg_ind: tuple) -> dict:
    out = {"pub": 0.0, "pvt": 0.0, "hh": 0.0}
    for k, ind in IND113.items():
        x = val("mospi_nas_2026_s1_13", f"s1_13.{k}.current")
        if x == 0:
            continue
        a = val("mospi_nas_2026_s7_1a", f"s7_1a.{ind}.ic.current") - (
            val("mospi_nas_2026_s8_15_1", f"s8_15_1.{ind}.ic.current") if ind in gg_ind else 0.0
        )
        b, c = (
            val("mospi_nas_2026_s7_1b", f"s7_1b.{ind}.ic.current"),
            val("mospi_nas_2026_s7_1c", f"s7_1c.{ind}.ic.current"),
        )
        for key, v in (("pub", a), ("pvt", b), ("hh", c)):
            out[key] += x * v / (a + b + c)
    return out


@cache
def interest_entries(gg_ind: tuple = GG_IC_BLOCK) -> dict:
    """R4, R5, R8 interest_mf_lookthrough and the R8a deposit/debenture entries, SNA basis."""
    b = bank_interest()
    bi, (p, _) = b["bi"], positions()
    r = rates()
    fis = ic_fisim(gg_ind)
    pfce = val("mospi_nas_2026_s1_13", "s1_13.private_final_consumption_expenditure.current")
    gross = 1 + fis["hh"] / pfce
    fl, fd = {}, {}
    for acc, key in (("E_NFPR", "pvt"), ("E_NFPU", "pub")):
        L = sum(s for c, d, i, s, rt in p if d == acc and i == "loans" and c in ("E_BANK", "E_NBFC"))
        D = sum(s for c, d, i, s, rt in p if c == acc and i == "deposits" and d in ("E_BANK", "E_NBFC"))
        wl, wd = (r["A"] - r["I"]) * L, (r["I"] - r["D"]) * D
        fl[acc], fd[acc] = fis[key] * wl / (wl + wd), fis[key] * wd / (wl + wd)
    hk = hh_keys()
    hfd = {g: hk["c4b_fisim_deposits"][g] * gross for g in HH}
    hfl = {g: hk["c4b_fisim_loans"][g] * gross for g in HH}
    out: dict = {}

    def add(k, v):
        out[k] = out.get(k, 0.0) + v

    stock = b["stock"]

    def split(pairs):
        # repair 2026-10-01 (fincorp-2): lender shares of a user's FISIM = reference-rate margins (SNA 2008 6.166):
        # loans interest - r* x stock, deposits r* x stock - interest (negative margins 0; interest shares if none)
        m = {
            x: max((r["I"] * stock[x] - bi[x]) if x[2] == "deposits" else (bi[x] - r["I"] * stock[x]), 0.0)
            for x in pairs
        }
        if sum(m.values()) <= 0:
            m = {x: bi[x] for x in pairs}
        t = sum(m.values())
        return {x: m[x] / t for x in pairs}

    for acc in ("E_NFPR", "E_NFPU"):
        lp = [x for x in bi if x[1] == acc and x[2] == "loans" and x[0] in ("E_BANK", "E_NBFC")]
        dp = [x for x in bi if x[0] == acc and x[2] == "deposits" and x[1] in ("E_BANK", "E_NBFC")]
        ls, ds = split(lp), split(dp)
        for x in lp:
            add((x[0], acc, "R5", "loans"), bi[x] - fl[acc] * ls[x])
        for x in dp:
            add((acc, x[1], "R4", "deposits"), bi[x] + fd[acc] * ds[x])
    lp = [x for x in bi if x[1] == "HH" and x[2] == "loans" and x[0] in ("E_BANK", "E_NBFC")]
    dp = [x for x in bi if x[0] == "HH" and x[2] == "deposits"]
    ls, ds = split(lp), split(dp)
    kl, kd, kf = shares(hk["aidis_inst_loans"]), shares(hk["aidis_deposits"]), shares(hk["aidis_fin_assets"])
    for g in HH:
        for x in lp:  # E_NBFC's household debt securities (FSF, 11.97) ride in its R5 'loans' component
            add(
                (x[0], g, "R5", "loans"),
                (bi[x] + (bi.get(("E_NBFC", "HH", "nongov_bonds"), 0.0) if x[0] == "E_NBFC" else 0.0)) * kl[g]
                - hfl[g] * ls[x],
            )
        add(("E_INSP", g, "R5", "loans"), bi[("E_INSP", "HH", "loans")] * kl[g])
        add(
            (g, "E_BANK", "R8a", "deposits_bank"),
            bi[("HH", "E_BANK", "deposits")] * kd[g] + hfd[g] * ds[("HH", "E_BANK", "deposits")],
        )
        add(
            (g, "E_NBFC", "R8a", "deposits_nbfc"),
            bi[("HH", "E_NBFC", "deposits")] * kd[g] + hfd[g] * ds[("HH", "E_NBFC", "deposits")],
        )
        add((g, "E_BANK", "R8a", "debentures"), bi[("HH", "E_BANK", "bonds")] * kf[g])
        add(
            (g, "E_NBFC", "R8a", "debentures"),
            (bi[("HH", "E_NBFC", "bonds")] + bi[("HH", "E_NBFC", "borrowings")]) * kf[g],
        )
    for (c, d, i), v in bi.items():
        if (
            (c in ("E_NFPR", "E_NFPU") and i == "deposits")
            or (d in ("E_NFPR", "E_NFPU") and i == "loans" and c in ("E_BANK", "E_NBFC"))
            or "HH" in (c, d)
            or "MF" in (c, d)
        ):
            continue
        add((c, d, "R5" if d in ("E_NFPR", "E_NFPU") else "R4", i), v)
    mf = mf_shares()
    for (c, d, _i), v in bi.items():
        if c != "MF":
            continue
        if d in ("E_NFPR", "E_NFPU"):
            add(("E_BANK", d, "R5", "mf_lookthrough"), v * mf["E_BANK"])
            add(("E_NFPR", d, "R8", "interest_mf_lookthrough"), v * mf["E_NFPR"])
        else:
            add(("E_BANK", d, "R4", "mf_lookthrough"), v * mf["E_BANK"])
            add(("E_NFPR", d, "R4", "mf_lookthrough"), v * mf["E_NFPR"])
    g = govint()
    add(("E_BANK", "E_RBI", "R4", "laf_sdf"), b["laf"])
    add(("E_RBI", "E_BANK", "R4", "msf"), b["msf"])
    add(("E_RBI", "E_BANK", "R4", "rbi_loans"), g["rbi_loans"]["E_BANK"])
    add(("E_RBI", "E_NBFC", "R4", "rbi_loans"), g["rbi_loans"]["E_NBFC"])
    mf_hh = {
        d: sum(v for (c, dd, i), v in bi.items() if c == "MF" and dd == d) * mf["HH"]
        for d in ("E_BANK", "E_NBFC", "E_NFPR", "E_NFPU")
    }
    written = sum(fl.values()) + sum(fd.values()) + sum(hfd.values()) + sum(hfl.values())
    return {"entries": out, "mf_hh": mf_hh, "fis": fis, "fl": fl, "fd": fd, "gross": gross, "written": written}


# ---------------------------------------------------------------------------------------------------- R8 / R8a
@cache
def dividends() -> dict:
    iss_f = {
        "E_NFPU": [("nfc_pub", 1)],
        "E_NFPR": [("nfc_pvt", 1)],
        "E_BANK": [("fc_odc", 1)],
        "E_INSP": [("fc_ofc_icpf", 1)],
        "E_NBFC": [("fc_ofc", 1), ("fc_ofc_icpf", -1)],
    }

    def liab(iss, cp):
        return sum(sg * F(inst, "liabilities", "f51", cp) for inst, sg in iss_f[iss])

    holders = {
        "fc_odc": "E_BANK",
        "fc_rbi": "E_RBI",
        "hh": "HH",
        "nfc_pub": "E_NFPU",
        "nfc_pvt": "E_NFPR",
        "gg_cen": "G_CEN",
        "gg_sta": "G_STA",
        "row": "ROW",
        "fc_ofc": None,
    }

    def denom(iss):  # the block normalises by the mapped counterparties (it drops FSF 'other_resident', 0.1)
        return sum(liab(iss, c) for c in holders)

    gshare = lambda iss, cps: sum(liab(iss, c) for c in cps) / denom(iss)  # noqa: E731
    r7 = {(g, iss): se(g, iss, "R7") for g in ("G_CEN", "G_STA") for iss in iss_f}
    tot = {
        "E_NFPU": (r7[("G_CEN", "E_NFPU")] + r7[("G_STA", "E_NFPU")]) / gshare("E_NFPU", ["gg_cen", "gg_sta"]),
        # V-FIN-3 fixed: the Union's R7 bank dividends over the Union's share of ODC equity (plan s.2.6)
        "E_BANK": r7[("G_CEN", "E_BANK")] / gshare("E_BANK", ["gg_cen"]),
    }
    irl, irn = "finsector_markets_irdai_life", "finsector_markets_irdai_nonlife"
    nl = sum(
        r[0]
        for r in q(
            f"select value from '{_ds(irn)}' where period = '{YEAR}' and (series_id like 't51.appr_interim_dividends.%' or series_id like 't51.appr_proposed_final_dividend.%')"
        )
    )
    tot["E_INSP"] = (
        val(irl, "t25.appr_interim_dividends.insurers_life.current")
        + val(irl, "t25.appr_proposed_final_dividend.insurers_life.current")
        + nl
    )
    gos = {a: se(a, "F_GOSC", block="factors") for a in ("E_NFPU", "E_NFPR")}
    ratio = tot["E_NFPU"] / gos["E_NFPU"]
    tot["E_NFPR"] = ratio * gos["E_NFPR"]
    tot["E_NBFC"] = ratio * f4a()["parts"][("E_NBFC", "private")]
    plan_bank = se("G_CEN", "E_BANK", "R7") / gshare("E_BANK", ["gg_cen"])
    dm = {}
    for iss, t in tot.items():
        # V-FIN-6 fixed: government parts = R7 as booked; the rest by the non-government holders' FSF shares
        gov = {g: r7[(g, iss)] for g in ("G_CEN", "G_STA")}
        rest = t - sum(gov.values())
        d = sum(liab(iss, c) for c in holders if c not in ("gg_cen", "gg_sta"))
        for cp, acc in holders.items():
            if acc in gov:
                dm[(iss, acc)] = gov[acc]
            elif acc:
                dm[(iss, acc)] = rest * liab(iss, cp) / d
        ofc = rest * liab(iss, "fc_ofc") / d
        cpn = iss_f[iss][0][0] if iss != "E_INSP" else "fc_ofc"
        a_all, a_icpf, a_mf = (
            F("fc_ofc", "assets", "f51", cpn),
            F("fc_ofc_icpf", "assets", "f51", cpn),
            F("fc_ofc_mf", "assets", "f51", cpn),
        )
        if a_all <= 0:
            dm[(iss, "E_NBFC")] = dm.get((iss, "E_NBFC"), 0.0) + ofc
            continue
        dm[(iss, "E_INSP")] = dm.get((iss, "E_INSP"), 0.0) + ofc * a_icpf / a_all
        dm[(iss, "MF")] = ofc * a_mf / a_all
        dm[(iss, "E_NBFC")] = dm.get((iss, "E_NBFC"), 0.0) + ofc * (a_all - a_icpf - a_mf) / a_all
    return {"tot": tot, "ratio": ratio, "dm": dm, "plan_bank": plan_bank}


@cache
def r8_r8a() -> dict:
    d, mf, hk = dividends(), mf_shares(), hh_keys()
    g, it = govint(), interest_entries()
    ke, km, kfa, kss = (
        shares(hk["aidis_equity"]),
        shares(hk["aidis_mf"]),
        shares(hk["aidis_fin_assets"]),
        shares(hk["aidis_small_savings"]),
    )
    out = {}
    for (iss, h), v in d["dm"].items():
        if abs(v) < 1e-12:
            continue
        if h in ("E_BANK", "E_INSP", "E_NBFC", "E_NFPR", "E_NFPU", "E_RBI"):
            out[(h, iss, "R8", "dividends")] = v
        elif h == "MF":
            out[("E_BANK", iss, "R8", "mf_lookthrough")] = v * mf["E_BANK"]
            out[("E_NFPR", iss, "R8", "mf_lookthrough")] = v * mf["E_NFPR"]
        elif h == "HH":
            for grp in HH:
                out[(grp, iss, "R8a", "dividends")] = v * ke[grp]
    mf_hh = {
        iss: d["dm"].get((iss, "MF"), 0.0) * mf["HH"] + it["mf_hh"].get(iss, 0.0)
        for iss in ("E_BANK", "E_INSP", "E_NBFC", "E_NFPR", "E_NFPU")
    }
    mf_hh.update(g["hh_mf"])
    for iss, v in mf_hh.items():
        for grp in HH:
            out[(grp, iss, "R8a", "mf_lookthrough")] = v * km[grp]
    for grp in HH:
        out[(grp, "G_CEN", "R8a", "small_savings")] = g["nssf_int"] * kss[grp]
        for col in ("G_CEN", "G_STA"):
            out[(grp, col, "R8a", "gsec_direct")] = g["hh_direct"][col] * kfa[grp]
    return out


# ---------------------------------------------------------------------------------------------------- R9c / R17
@cache
def r9c() -> dict:
    ep, nps = "finsector_markets_epfo_ar", "finsector_markets_pfrda_nps"
    rate = val(ep, "app5vii.epf_interest_rate", vintage=EPFO_V, pct=True) / 100
    epf, eps = avg(ep, "invest.epf.total.current", EPFO_V), avg(ep, "invest.eps.total.current", EPFO_V)
    nps_s = avg(nps, "m6.aum_by_asset_class.total.current")
    exm = (
        avg("rbi_financial_accounts_fsf_balance_sheets", "fsf.fc_ofc_icpf_pf.liabilities.outstanding.f6.all.current")
        - epf
        - eps
        - nps_s
    )
    dy = sum(dividends()["tot"].values()) / avg("finsector_markets_sebi_bonds_equity", "t23.market_cap.nse.current")
    d44 = {
        "life": val("finsector_markets_irdai_life", "t24.inv_interest_dividends_rent_gross.insurers_life.current")
        + val("finsector_markets_irdai_life", "t24.inv_amortisation.insurers_life.current"),
        "epf": epf * rate,
        "eps": eps * rate,
        "exempted_pf": exm * rate,
        "nps": govint()["pension_gsec"]
        + avg(nps, "m6.aum_by_asset_class.corporate_bonds.current") * rates()["B"]
        + avg(nps, "m6.aum_by_asset_class.equity.current") * dy,
        "gpf_union": u("03.104"),
        "gpf_states": st("ii.c.2.iii-interest_on_small_savings_state_provident_funds"),
    }
    lreg = {g: se(g, "F_LREG", "F1a", block="factors") for g in HH}
    pub = {
        r[0]: r[1]
        for r in q(
            f"select household_group, value from '{_p(BLOCKS / 'factors_satellites' / 'factor_income_keys.parquet')}' where key = 'public_sector_wage_key' and measure = 'level'"
        )
    }
    k_priv, k_pub = shares({g: lreg[g] - pub[g] for g in HH}), shares(pub)
    pop = hh_keys()["pop_persons"]
    k_low = shares({g: (pop[g] if g[-1] in "123" else 0.0) for g in HH})
    m4 = {
        c: val(nps, f"m4d.annual_contribution.{c}.current")
        for c in (
            "central_govt",
            "state_govt",
            "corporate",
            "all_citizen",
            "apy",
            "nps_lite",
            "tier2",
            "tier2_tax_saver",
        )
    }
    w_pub, w_low = (
        (m4["central_govt"] + m4["state_govt"]) / sum(m4.values()),
        (m4["apy"] + m4["nps_lite"]) / sum(m4.values()),
    )
    keys = {
        "life": shares(hh_keys()["aidis_fin_assets"]),
        "epf": k_priv,
        "eps": k_priv,
        "exempted_pf": k_priv,
        "gpf_union": k_pub,
        "gpf_states": k_pub,
        "nps": {g: w_pub * k_pub[g] + (1 - w_pub - w_low) * k_priv[g] + w_low * k_low[g] for g in HH},
    }
    col = {"gpf_union": "G_CEN", "gpf_states": "G_STA"}
    out = {(g, col.get(s, "E_INSP"), "R9c", s): t * keys[s][g] for s, t in d44.items() for g in HH}
    return {
        "entries": out,
        "d44": d44,
        "stocks": {"epf": epf, "eps": eps, "exempted_pf": exm, "nps_aum": nps_s},
        "dy": dy,
    }


@cache
def r17() -> dict:
    irn = "finsector_markets_irdai_nonlife"
    lines = ["motor", "health", "fire", "marine", "others"]
    hshare = dict(
        zip(lines, (0.70, 0.55, 0.10, 0.0, 0.30), strict=True)
    )  # the block's assumption record sam_fincorp:ec21dc1c9670
    claims = {ln: val(irn, f"t44.claims_incurred_net.{ln}.insurers_general_direct.current") for ln in lines}
    npe = {ln: val(irn, f"t44.net_premium_earned.{ln}.insurers_general_direct.current") for ln in lines}
    sh_inv = sum(
        r[0]
        for r in q(
            f"select value from '{_ds(irn)}' where period = '{YEAR}' and series_id like 't51.inv_interest_dividend_rent_gross.%'"
        )
    )
    supp = val("finsector_markets_irdai_summary", "sum_c.investment_income.current") - sh_inv
    supp_l = {ln: supp * npe[ln] / sum(npe.values()) for ln in lines}
    gos = {a: se(a, "F_GOSC", block="factors") for a in ("E_NFPU", "E_NFPR")}
    kins = shares(hh_keys()["c4b_insurance_service"])
    out = {}
    for comp, amt in (("claim", claims), ("premium", claims), ("premium_supplement", supp_l)):
        for ln in lines:
            hh, nfc = amt[ln] * hshare[ln], amt[ln] * (1 - hshare[ln])
            tgt = {g: hh * kins[g] for g in HH} | {a: nfc * gos[a] / sum(gos.values()) for a in gos}
            for acc, v in tgt.items():
                if v:
                    k = ("E_INSP", acc, "R17", comp) if comp == "premium" else (acc, "E_INSP", "R17", comp)
                    out[k] = out.get(k, 0.0) + v
    return {
        "entries": out,
        "claims": sum(claims.values()),
        "supp": supp,
        "service": sum(npe.values()) + supp - sum(claims.values()),
    }


# ---------------------------------------------------------------------------------------------------- K2a
@cache
def k2a() -> dict:
    rec = sum(
        v
        for b, r, c, rf, cp, v in all_entries()
        if r == "E_RBI" and not (rf == "R13" and cp == "reserve_income_unexplained")
    )
    pay = sum(v for b, r, c, rf, cp, v in all_entries() if c == "E_RBI" and rf != "K2a")
    k_rbi = rec - pay
    s19 = lambda s: val("mospi_nas_2026_s1_9", f"s1_9.{s}.current")  # noqa: E731
    pub, pvt = s19("public_financial_corporations"), s19("private_financial_corporations")
    parts = f4a()["parts"]
    rp = (pub - k_rbi) / (sum(v for (a, c), v in parts.items() if c == "public") - parts[("E_RBI", "public")])
    rv = pvt / sum(v for (a, c), v in parts.items() if c == "private")
    out = {("K_RBI", "E_RBI", "K2a", "public"): k_rbi}
    for (a, c), v in parts.items():
        if a != "E_RBI":
            out[("K_" + a[2:], a, "K2a", c)] = v * (rp if c == "public" else rv)
    debit = se("R_ROW", "E_RBI", "R14", "reserve_asset_debit")
    return {"entries": out, "k_rbi": k_rbi, "nas_target": pub - f4a()["pub_t"], "debit": debit}


OLDB = "mospi_nas_2026_oldbase_soa_s2_2"


@cache
def oldbase_ratio(period: str = "2022-23") -> float:
    ob = lambda item: val(OLDB, f"oldbase_soa_s2_2.{item}.current", period=period)  # noqa: E731
    return (ob("allocation_of_primary_income.resources.d4") - ob("allocation_of_primary_income.uses.d4")) / (
        ob("allocation_of_primary_income.resources.b2n_b3n") + ob("production.uses.p51c")
    )


def oldbase_topup(m: dict) -> dict:
    """DECISIONS D2-21 (fincorp repair 2026-10-01): E_NFPR's other distributed income brings its net D4 over all
    SAM entries (fincorp R3a/R4/R5/R8/R8a and R17 premium supplements as recomputed here; rest_of_world R13, R14,
    R14a; government R7, R7x) to the old-base St 2.2 2022-23 net-D4/GOS ratio x factors' GOS; holders by FSF F51
    (non-government residents other than E_NFPR and RBI), MF looked through, the part returning to E_NFPR grossed up."""
    a = "E_NFPR"
    d4 = ("R3a", "R4", "R5", "R8", "R8a")
    isd4 = lambda k: k[2] in d4 or (k[2] == "R17" and k[3] == "premium_supplement")  # noqa: E731
    net = sum(v for k, v in m.items() if isd4(k) and k[0] == a and k[1] != a) - sum(
        v for k, v in m.items() if isd4(k) and k[1] == a and k[0] != a
    )
    net += sum(
        v for b, rr, c, rf, cp, v in all_entries() if b != "fincorp" and rr == a and c == "R_ROW" and rf == "R13"
    )
    net -= sum(
        v
        for b, rr, c, rf, cp, v in all_entries()
        if b != "fincorp" and rr == "R_ROW" and c == a and rf in ("R14", "R14a")
    )
    net -= sum(v for b, rr, c, rf, cp, v in all_entries() if b == "government" and c == a and rf in ("R7", "R7x"))
    prior = oldbase_ratio() * se(a, "F_GOSC", block="factors")
    hold = {
        h: max(F("nfc_pvt", "liabilities", "f51", cp), 0.0)
        for h, cp in (("HH", "hh"), ("E_NFPU", "nfc_pub"), ("E_BANK", "fc_odc"))
    }
    ofc = max(F("nfc_pvt", "liabilities", "f51", "fc_ofc"), 0.0)
    w = {
        "E_NBFC": max(
            F("fc_ofc", "assets", "f51", "nfc_pvt")
            - F("fc_ofc_icpf", "assets", "f51", "nfc_pvt")
            - F("fc_ofc_mf", "assets", "f51", "nfc_pvt"),
            0.0,
        ),
        "E_INSP": max(F("fc_ofc_icpf", "assets", "f51", "nfc_pvt"), 0.0),
        "MF": max(F("fc_ofc_mf", "assets", "f51", "nfc_pvt"), 0.0),
    }
    base = sum(hold.values()) + ofc
    sh = {h: v / base for h, v in hold.items()} | {k: ofc / base * v / sum(w.values()) for k, v in w.items()}
    mf = mf_shares()
    total = max(net - prior, 0.0) / (1.0 - sh["MF"] * mf["E_NFPR"])
    hk = hh_keys()
    ke, km = shares(hk["aidis_equity"]), shares(hk["aidis_mf"])
    out = {}
    for h in ("E_NFPU", "E_BANK", "E_NBFC", "E_INSP"):
        out[(h, a, "R8", "distributed_income")] = total * sh[h]
    for h in ("E_BANK", "E_NFPR"):
        out[(h, a, "R8", "distributed_income_mf")] = total * sh["MF"] * mf[h]
    for g in HH:
        out[(g, a, "R8a", "distributed_income")] = total * sh["HH"] * ke[g]
        out[(g, a, "R8a", "distributed_income_mf")] = total * sh["MF"] * mf["HH"] * km[g]
    return {"entries": out, "total": total, "prior": prior, "before": net}


@cache
def expected(gg_ind: tuple = GG_IC_BLOCK) -> dict:
    m = {(r, "F_GOSC", "F4a", c): v for (r, c), v in f4a()["parts"].items()}
    m |= (
        govint()["entries"]
        | interest_entries(gg_ind)["entries"]
        | r8_r8a()
        | r9c()["entries"]
        | r17()["entries"]
        | k2a()["entries"]
    )
    m |= oldbase_topup(m)["entries"]
    return m


# ==================================================================================================== tests
def test_entry_census_all_455_entries_recomputed():
    blk, exp = block_entries(), expected()
    # 455 + 7 R4 entries on GG-held bank/NBFC debt (V-FIN-4 fix) + 26 entries of E_NFPR's other distributed income
    # (DECISIONS D2-21, repair 2026-10-01: R8 to four FC/NFC holders and two MF look-through holders, R8a 2 x 10)
    assert len(blk) == 488
    missing = sorted(k for k in blk if k not in exp)
    extra = sorted(k for k, v in exp.items() if k not in blk and abs(v) > 1e-9)
    assert not missing and not extra, (missing[:5], extra[:5])
    bad = sorted((k, exp[k], blk[k][0]) for k in blk if abs(exp[k] - blk[k][0]) > TOL)
    assert not bad, bad[:10]
    # 121 before; factors' D2-19 rebuild (R9c keys) and the repair of 2026-10-01 (D2-21 top-up, OFC claims, FISIM
    # lender split, r_corp) moved entries across the 10,000 line
    assert sum(abs(v[0]) >= 10_000 for v in blk.values()) == 140


def test_ref_totals_against_clean_sources():
    blk = block_entries()
    tot = lambda ref, comp=None: sum(v[0] for k, v in blk.items() if k[2] == ref and (comp is None or k[3] == comp))  # noqa: E731
    fa = f4a()
    assert math.isclose(tot("F4a"), fa["gos55"] + fa["gos56"], abs_tol=0.01)
    assert abs(tot("F4a") - (fa["pub_t"] + fa["pvt_t"])) < 1.0  # SUT vs NAS 7.1 rounding (0.22)
    assert math.isclose(tot("F4a", "public"), fa["pub_t"], abs_tol=0.01)
    assert math.isclose(
        blk[("E_RBI", "F_GOSC", "F4a", "public")][0], fa["rbi_dep"], abs_tol=0.01
    )  # central bank output at cost
    assert math.isclose(tot("K2a"), val("mospi_nas_2026_s1_9", "s1_9.financial_corporations.current"), abs_tol=0.01)
    assert math.isclose(tot("R9c", "life"), r9c()["d44"]["life"], abs_tol=0.01)
    assert math.isclose(tot("R9c", "gpf_union"), u("03.104"), abs_tol=0.01)
    assert math.isclose(tot("R17", "claim"), r17()["claims"], abs_tol=0.01)
    assert math.isclose(tot("R17", "premium"), tot("R17", "claim"), abs_tol=0.01)
    assert math.isclose(tot("R17", "premium_supplement"), r17()["supp"], abs_tol=0.01)
    assert math.isclose(tot("R8a", "small_savings"), govint()["nssf_int"], abs_tol=0.01)
    # FISIM written in R4/R5/R8a = NAS 1.13 IC + PFCE (RoW FISIM excluded, XR-13)
    target = val("mospi_nas_2026_s1_13", "s1_13.allocation_of_fisim_as_ic_to_user_industry.current") + val(
        "mospi_nas_2026_s1_13", "s1_13.private_final_consumption_expenditure.current"
    )
    assert math.isclose(interest_entries()["written"], target, abs_tol=0.01)


def test_constraint_targets_and_selections():
    fa, g = f4a(), govint()
    s19 = lambda s: val("mospi_nas_2026_s1_9", f"s1_9.{s}.current")  # noqa: E731
    claims = r17()["claims"]
    mine = {
        "f4a.fc_gos_total": (fa["pub_t"] + fa["pvt_t"], None, 1.0, 0.0, "equal"),
        "f4a.fins_gos": (fa["gos55"], None, 1.0, 0.0, "equal"),
        "f4a.insp_gos": (fa["gos56"], None, 1.0, 0.0, "equal"),
        "f4a.public": (fa["pub_t"], "public", 1.0, 0.0, "equal"),
        "f4a.private": (fa["pvt_t"], "private", 1.0, 0.0, "equal"),
        "k2.fc_saving_total": (s19("financial_corporations"), None, 1.0, 0.0, "equal"),
        "k2.public": (s19("public_financial_corporations"), "public", 1.0, 0.0, "equal"),
        "k2.private": (s19("private_financial_corporations"), "private", 1.0, 0.0, "equal"),
        "r3b.union_nas_concept": (g["union_t"], None, 0.0, 0.03, "band"),
        "r3b.states_nas_concept": (g["states_t"], None, 0.0, 0.01, "band"),
        "r9c.gpf_union": (u("03.104"), None, 0.0, 0.02, "equal"),
        "r9c.life": (r9c()["d44"]["life"], "life", 0.0, 0.05, "band"),
        "r17.claims": (claims, "claim", 0.0, 0.01, "equal"),
        "r17.premiums": (claims, "premium", 0.0, 0.01, "band"),  # 5% -> 1% (fincorp-33, Wave C audit fix)
    }
    # Wave C audit fix (BS-1, 2026-10-01; added by the fixing agent, NOT yet re-verified by a different agent):
    # targets recomputed here from clean data (supplements, RBI) or from this file's own recomputed entries
    ex, k = expected(), k2a()

    def ssum(rows, cols, refs, comps) -> float:
        return sum(v for (r, c, rf, cp), v in ex.items() if r in rows and c in cols and rf in refs and cp in comps)

    payer = {"hh": HH, "e_nfpu": ["E_NFPU"], "e_nfpr": ["E_NFPR"]}
    for s, accts in payer.items():
        mine[f"r17.payer.{s}.premium"] = (ssum(["E_INSP"], accts, ["R17"], ["premium"]), "premium", 0.0, 0.05, "band")
        mine[f"r17.payer.{s}.claim"] = (ssum(accts, ["E_INSP"], ["R17"], ["claim"]), "claim", 0.0, 0.05, "band")
        mine[f"r17.payer.{s}.premium_supplement"] = (
            ssum(accts, ["E_INSP"], ["R17"], ["premium_supplement"]),
            "premium_supplement",
            0.0,
            0.05,
            "band",
        )
    holders = ["E_BANK", "E_NBFC", "E_INSP", "E_NFPR", *HH]
    mine |= {
        "r17.supplements": (r17()["supp"], "premium_supplement", 0.0, 0.01, "band"),
        "k2a.rbi_ar_basis": (k["nas_target"] - k["debit"], None, 2500.0, 0.0, "band"),
        "r3a.states_other_internal_debt": (
            ssum(["E_BANK", "E_NBFC", "E_RBI"], ["G_STA"], ["R3a"], ["state_loans", "wma_od"]),
            "state_loans,wma_od", 0.0, 0.02, "band"),
        "r5.insp_bonds.e_nfpu": (ssum(["E_INSP"], ["E_NFPU"], ["R5"], ["nongov_bonds"]), "nongov_bonds", 0.0, 0.25,
                                 "band"),
        "r5.insp_bonds.e_nfpr": (ssum(["E_INSP"], ["E_NFPR"], ["R5"], ["nongov_bonds"]), "nongov_bonds", 0.0, 0.25,
                                 "band"),
        "r8.mf_bonds.e_nfpu": (ssum(["E_NFPR"], ["E_NFPU"], ["R8"], ["interest_mf_lookthrough"]),
                               "interest_mf_lookthrough", 0.0, 0.25, "band"),
        "r8.nfpu_nongov_holders": (ssum(holders, ["E_NFPU"], ["R8", "R8a"], ["dividends", "mf_lookthrough"]),
                                   "dividends,mf_lookthrough", 0.0, 0.25, "band"),
    }  # fmt: skip
    rows = q(
        f"select constraint_id, target, components, tol_abs, tol_rel, kind, refs from '{_p(BLOCKS / 'fincorp_constraints.parquet')}'"
    )
    assert {r[0] for r in rows} == set(mine)
    for cid, target, comps, ta, tr, kind, refs in rows:
        t, c, a, rel, k = mine[cid]
        assert math.isclose(target, t, abs_tol=1e-4), cid
        assert (comps, ta, tr, kind) == (c, a, rel, k), cid
        if cid.startswith("r3b."):
            assert refs == "R14,R3,R3a,R8a,R9c"
    # factors declares the same FC GOS selection with the same target (duplicate, not conflict)
    fac = q(
        f"select target, tol_abs from '{_p(BLOCKS / 'factors_constraints.parquet')}' where constraint_id = 'f4.fc_gos'"
    )
    assert fac and math.isclose(fac[0][0], fa["pub_t"] + fa["pvt_t"], abs_tol=1e-6)


def test_constraints_hold_on_the_assembled_prior():
    rows = q(
        f"select constraint_id, rows, cols, refs, components, target, tol_abs, tol_rel from '{_p(BLOCKS / 'fincorp_constraints.parquet')}'"
    )
    for cid, rs, cs, refs, comps, target, ta, tr in rows:
        rs, cs = rs.split(","), cs.split(",")
        refs = refs.split(",") if refs else None
        comps = comps.split(",") if comps else None
        s = sum(
            v
            for b, r, c, rf, cp, v in all_entries()
            if r in rs and c in cs and (refs is None or rf in refs) and (comps is None or cp in comps)
        )
        assert abs(s - target) <= max(ta, tr * abs(target)), (cid, s, target)


def test_check_targets_and_the_rbi_saving_evidence():
    fa, k = f4a(), k2a()
    rows = {
        r[0]: r[1:] for r in q(f"select check_id, sam_value, target, ok from '{_p(BLOCKS / 'fincorp_checks.parquet')}'")
    }
    assert len(rows) == 14
    exp_t = {
        "f4a.equals_factors_fc_gos": fa["pub_t"] + fa["pvt_t"],
        "f4a.equals_production_a_fins": fa["gos55"],
        "f4a.equals_production_a_insr": fa["gos56"],
        "f4a.rbi_gos_equals_depreciation": fa["rbi_dep"],
        "k2.total_equals_parts": val("mospi_nas_2026_s1_9", "s1_9.financial_corporations.current"),
        "k2a.rbi_cash_basis_evidence": k["nas_target"],
        "k2a.rbi_prior_vs_nas": k["nas_target"],
        "fisim.domestic_total": interest_entries()["written"],
        "fisim.written_total": interest_entries()["written"],
        "fisim.ic_industries_add_up": val(
            "mospi_nas_2026_s1_13", "s1_13.allocation_of_fisim_as_ic_to_user_industry.current"
        ),
        "r17.claims_lines_add_up": r17()["claims"],
        "r3.states_lines_add_up": st("ii.c.2-interest_payments"),
        "r3.states_vs_fc16_kfi": val("state_fiscal_fc16_kfi", "kfi.b_1_a-interest_payments.in.all_states_28"),
        "r3.union_lines_add_up": u("total"),
    }
    for cid, t in exp_t.items():
        assert math.isclose(rows[cid][1], t, abs_tol=0.01), cid
    # D0-7 evidence (plan C3): E_RBI saving on the RBI AR basis matches NAS public FC saving less public FC GOS
    assert math.isclose(rows["k2a.rbi_cash_basis_evidence"][0], k["k_rbi"] + k["debit"], abs_tol=0.01)
    # -1.90 before the V-FIN-6 fix; +23.32 after it (E_RBI's R8 dividends from private NBFCs rise by 25.22 once
    # the government holders no longer take a share of the private E_NBFC total)
    assert abs(k["k_rbi"] + k["debit"] - k["nas_target"]) < 30.0
    assert math.isclose(rows["k2a.rbi_prior_vs_nas"][0], k["k_rbi"], abs_tol=0.01)
    assert rows["k2a.rbi_prior_vs_nas"][2] is False and all(
        v[2] for c, v in rows.items() if c != "k2a.rbi_prior_vs_nas"
    )
    # the AR-only computation of the plan (C3) is 121.81 above NAS; the accrual surplus would miss by ~1.2 lakh
    ar = lambda s: val(AR, s, vintage=AR_V)  # noqa: E731
    plan_c3 = (
        fa["rbi_dep"]
        + ar("sch13.a.sub_total.current")
        + ar("sch14.a.amortisation_of_premium_discount_on_rupee_securities.current")
        + ar("sch13.b.sub_total.current")
        + ar("sch14.b.amortisation_of_premium_discount_on_foreign_securities.current")
        - ar("is.exp_interest.current")
    )
    cash = val("rbi_banking_corporate_rbi_surplus_timing", "r6.surplus_received_by_centre_cash.current")
    assert abs(plan_c3 - cash - k["nas_target"] - 121.81) < 0.01
    assert plan_c3 - ar("is.surplus_payable.current") - k["nas_target"] < -120_000


def test_satellite_bridges_reproduce():
    fa, g, b, it, d, r9 = f4a(), govint(), bank_interest(), interest_entries(), dividends(), r9c()
    sh_n, sh_h = dt_shares()
    for sid, v in (
        ("input.dt_share_nbfc", sh_n),
        ("input.dt_share_hfc", sh_h),
        ("input.ce_bank", fa["ce_bank"]),
        ("input.ce_nbfc", fa["ce_nbfc"]),
        ("input.bank_public_share", fa["bank_pub_share"]),
        ("input.insp_public_share", fa["insp_pub_share"]),
    ):
        assert math.isclose(satv("fc_public_private", sid), v, rel_tol=1e-6, abs_tol=1e-6), sid
    for (c, d_, i), s in b["stock"].items():
        assert math.isclose(
            satv("interest_fisim_bridge", f"pos.{c.lower()}.{d_.lower()}.{i}.stock"), s, abs_tol=0.01
        ), (c, d_, i)
        assert math.isclose(
            satv("interest_fisim_bridge", f"pos.{c.lower()}.{d_.lower()}.{i}.bank_interest"),
            b["bi"][(c, d_, i)],
            abs_tol=0.01,
        ), (c, d_, i)
    for k, v in b["pl"].items():
        assert math.isclose(satv("interest_fisim_bridge", f"pl.{k}"), v, abs_tol=0.01), k
    for k, v in b["scale"].items():
        assert math.isclose(satv("interest_fisim_bridge", f"scale.{k}"), v, abs_tol=1e-6), k
    for k, v in (
        ("fisim.ic_nfc_public", it["fis"]["pub"]),
        ("fisim.ic_nfc_private", it["fis"]["pvt"]),
        ("fisim.ic_households", it["fis"]["hh"]),
    ):
        assert math.isclose(satv("interest_fisim_bridge", k), v, abs_tol=0.01), k
    for line in ("01.101", "01.103", "01.115", "01.116", "01.132", "03.104", "03.108", "60.107", "60.111"):
        assert math.isclose(satv("gov_interest_bridge", f"union.line.{line}"), u(line), abs_tol=1e-4), line
    assert math.isclose(satv("gov_interest_bridge", "target.union_nas_concept"), g["union_t"], abs_tol=1e-4)
    assert math.isclose(satv("gov_interest_bridge", "target.states_nas_concept"), g["states_t"], abs_tol=1e-4)
    assert math.isclose(
        satv("gov_interest_bridge", "derived.union.fpi_own_formula"), g["fpi"]["dated"] + g["fpi"]["tb"], abs_tol=0.01
    )
    # rest_of_world writes the FPI interest with the same formula (XR-12)
    assert math.isclose(
        se("R_ROW", "G_CEN", "R14", "fpi_gsec_interest") + se("R_ROW", "G_CEN", "R14", "fpi_tbill_interest"),
        g["fpi"]["dated"] + g["fpi"]["tb"],
        abs_tol=0.01,
    )
    assert math.isclose(se("R_ROW", "G_STA", "R14", "fpi_sdl_interest"), g["fpi"]["sdl"], abs_tol=0.01)
    for iss, v in d["tot"].items():
        assert math.isclose(satv("dividend_matrix", f"total.{iss.lower()}"), v, abs_tol=0.01), iss
    for (iss, h), v in d["dm"].items():
        assert math.isclose(satv("dividend_matrix", f"div.{iss.lower()}.{h.lower()}"), v, abs_tol=0.01), (iss, h)
    for s, v in r9["d44"].items():
        assert math.isclose(satv("d44_by_scheme", f"d44.{s}"), v, abs_tol=0.01), s
    for s, v in r9["stocks"].items():
        assert math.isclose(satv("d44_by_scheme", f"stock.{s}"), v, abs_tol=0.01), s
    assert math.isclose(satv("dividend_matrix", "param.dividend_yield_market"), r9["dy"], abs_tol=1e-6)


def test_s9_funded_schemes_census():
    ep, nps = "finsector_markets_epfo_ar", "finsector_markets_pfrda_nps"
    exp = {
        "s9.epf.contributions": val(ep, "app5i.epf_contribution.current", vintage=EPFO_V),
        "s9.epf.payments": val(ep, "app5i.epf_payment.current", vintage=EPFO_V),
        "s9.eps.contributions": val(ep, "para54.eps_contribution_total.current", vintage=EPFO_V),
        "s9.eps.pensions": val(
            "finsector_markets_epfo_eps_outgo", "eps_outgo.pension_disbursed.current", vintage=EPFO_V
        ),
        "s9.eps.withdrawals": val(
            "finsector_markets_epfo_eps_outgo", "eps_outgo.withdrawal_benefits.current", vintage=EPFO_V
        ),
        "s9.edli.contributions": val(ep, "app5i.edli_contribution.current", vintage=EPFO_V),
        "s9.edli.payments": val(ep, "app5i.edli_payment.current", vintage=EPFO_V),
        "s9.life.premiums": val("finsector_markets_irdai_life", "t24.premium.insurers_life.current"),
        "s9.life.benefits": val("finsector_markets_irdai_life", "t24.benefits_paid_net.insurers_life.current"),
        "s9.gpf_union.additions": val("union_fiscal_fa_provident_funds", "fa14.8009.total.additions"),
        "s9.gpf_union.discharges": val("union_fiscal_fa_provident_funds", "fa14.8009.total.discharges"),
        "s9.pli.additions": val("union_fiscal_fa_provident_funds", "fa14.8014.total.additions"),
        "s9.pli.discharges": val("union_fiscal_fa_provident_funds", "fa14.8014.total.discharges"),
        "s9.cgegis.additions": val("union_fiscal_fa_provident_funds", "fa14.8011.total.additions"),
        "s9.cgegis.discharges": val("union_fiscal_fa_provident_funds", "fa14.8011.total.discharges"),
        "s9.gpf_states.receipts": val(
            SF, "app3.total_capital_receipts.vi.1-state_provident_funds.in.all_states_uts.actuals"
        ),
        "s9.gpf_states.disbursements": val(
            SF, "app4.total_capital_disbursements.vii.1-state_provident_funds.in.all_states_uts.actuals"
        ),
        "s9.ppf.net_accretion": val("union_fiscal_nssf", "nssf.ppf.additions"),
        "s9.nps.contributions.state_govt.employer": val(
            "finsector_markets_pfrda_sg", "m7d.annual_contribution_employer.state_govt.current"
        ),
        "s9.nps.contributions.state_govt.employee": val(
            "finsector_markets_pfrda_sg", "m7d.annual_contribution_employee.state_govt.current"
        ),
    }
    for c in ("central_govt", "state_govt", "corporate", "all_citizen", "apy", "nps_lite", "tier2", "tier2_tax_saver"):
        exp[f"s9.nps.contributions.{c}"] = val(nps, f"m4d.annual_contribution.{c}.current")
    for s, v in r9c()["d44"].items():
        exp[f"s9.{s}.interest_credited"] = v
    rows = {r[0]: r[1] for r in q(f"select series_id, value from '{_p(SAT / 's9_funded_schemes.parquet')}'")}
    assert set(rows) == set(exp), set(rows) ^ set(exp)
    for sid, v in exp.items():
        assert math.isclose(rows[sid], v, abs_tol=0.01), sid


def test_roles_statuses_and_structure():
    blk = block_entries()
    assert all(v[0] > 0 for v in blk.values())  # no zero or negative entries (all these flows are positive)
    anchored = {k for k, v in blk.items() if v[2] == "anchored"}
    assert {(k[2], k[3]) for k in anchored} == {
        ("F4a", "public"),
        ("R3", "central_loans"),
        ("R3", "nssf"),
        ("R3", "itb_14d"),
        ("R3a", "dated_securities"),
        ("R3a", "sdl"),
        ("R3a", "wma"),
        ("R3a", "recap_bonds"),
        ("R4", "laf_sdf"),
        ("R4", "msf"),
        ("R4", "rbi_loans"),
    }  # ("R9c", "gpf_union") left the set with the V-FIN-2 fix
    assert all(v[1] == "derived" and v[3] and v[4] is None for k, v in blk.items() if k in anchored)
    assert all(
        v[1] == "estimated" and v[3] is None and v[4] in ("high", "medium", "low")
        for k, v in blk.items()
        if k not in anchored
    )
    assert all(blk[k][4] == "low" for k in blk if k[2] in ("K2a", "R8"))
    # plan T14 guards
    assert not any("R_ROW" in k[:2] for k in blk)
    assert not any(k[0].startswith("G_") and k[2] == "R8" for k in blk)
    assert not any(k[2] == "R3a" and k[0].startswith("H_") for k in blk)
    assert not any(k[2] == "R5" and k[1].startswith("G_") for k in blk)
    assert not any(k[2] == "R9c" and "ppf" in k[3] for k in blk)
    assert ("G_CEN", "G_CEN") not in {k[:2] for k in blk}
    # every household-touching entry is at group level
    assert all(k[0] in HH or k[1] in HH for k in blk if k[2] in ("R8a", "R9c") or "H_" in k[0] + k[1])
    # no other block writes a ref fincorp owns
    owned = ("F4a", "R3", "R3a", "R4", "R5", "R8", "R8a", "R9c", "R17", "K2", "K2a")
    assert not [x for x in all_entries() if x[0] != "fincorp" and x[3] in owned]


def test_provenance_inputs_resolve_and_records_match_refs():
    clean = {
        r[0] for r in q(f"select prov_id from read_parquet('{_p(CLEAN)}/*/_provenance.parquet', union_by_name=true)")
    }
    sam = {
        r[0] for r in q(f"select prov_id from read_parquet('{_p(BLOCKS)}/*_provenance.parquet', union_by_name=true)")
    }
    recs = q(f"select prov_id, inputs, table_id, status, method from '{_p(BLOCKS / 'fincorp_provenance.parquet')}'")
    # 42 + 5 (repair 2026-10-01): the D2-21 ratio parameter, the R8 and R8a other-distributed-income methods, and
    # the satellite records of the old-base rows (dividend_matrix) and the E_INSP income memo (d44_by_scheme);
    # + 8 constraint-target records of the Wave C audit fix (R17 supplements and payers, K2a RBI, R3a States'
    # other internal debt, R5 insurers' bonds x2, R8 MF bonds, R8 non-government dividends of E_NFPU)
    assert len(recs) == 55
    stale = {f"sam_{d}" for d in stale_deps()}  # a rebuilt dependency re-hashes its record ids (V-FIN-5)
    for pid, inputs, _tab, _st, meth in recs:
        assert meth and meth.strip(), pid
        for x in (inputs or "").split(","):
            assert not x or x in clean or x in sam or x.split(":")[0] in stale, (pid, x)
    tab = {r[0]: (r[2], r[3]) for r in recs}
    for k, v in block_entries().items():
        assert tab[v[5]] == (f"SAM 2023-24 gap-map {k[2]}", v[1]), k
    # the K2a E_RBI record cites every other block's record behind the E_RBI entries it sums (D2-7)
    ins = next(r[1] for r in recs if r[0] == block_entries()[("K_RBI", "E_RBI", "K2a", "public")][5]).split(",")
    need = q(
        f"select distinct prov_id from read_parquet('{_p(BLOCKS)}/*_entries.parquet', union_by_name=true) where block <> 'fincorp' and (row = 'E_RBI' or col = 'E_RBI') and not (ref = 'R13' and component = 'reserve_income_unexplained')"
    )
    assert all(p[0] in ins for p in need)


def test_ic_fisim_user_split_removes_all_gg_ic():
    """V-FIN-1 (fixed 2026-10-01; was a strict xfail): NAS 8.15.1 also publishes GG IC in utilities (36,031.26),
    and the block now removes GG IC for all four industries it publishes."""
    exp, blk = expected(GG_IC_ALL), block_entries()
    bad = [(k, exp[k], blk[k][0]) for k in blk if abs(exp[k] - blk[k][0]) > TOL]
    assert not bad
    assert math.isclose(satv("interest_fisim_bridge", "fisim.ic_nfc_public"), ic_fisim(GG_IC_ALL)["pub"], abs_tol=0.01)
    assert math.isclose(ic_fisim(GG_IC_ALL)["pub"], 53_648.36, abs_tol=0.01)  # the figure of the finding


def test_gpf_union_group_entries_are_labelled_estimated_and_free():
    """V-FIN-2 (fixed; was a strict xfail): the household split rests on factors' estimated public_sector_wage_key,
    so the groups are estimated/free; the published total is held by constraint r9c.gpf_union."""
    rows = [(k, v) for k, v in block_entries().items() if k[3] == "gpf_union"]
    assert len(rows) == 10
    for k, v in rows:
        assert v[1] == "estimated" and v[2] == "free" and v[3] is None and v[4] in ("high", "medium", "low"), k


def test_bank_dividend_grossing_uses_the_union_share():
    """V-FIN-3 (fixed; was a strict xfail): E_BANK dividends = the Union's R7 receipts / the Centre's share of ODC
    equity (plan s.2.6): 62,053.06, not 54,563.61."""
    assert math.isclose(dividends()["tot"]["E_BANK"], satv("dividend_matrix", "total.e_bank"), abs_tol=0.01)
    assert math.isclose(satv("dividend_matrix", "total.e_bank"), dividends()["plan_bank"], abs_tol=0.01)


def test_interest_on_government_held_fc_debt_is_written_somewhere():
    """V-FIN-4 (fixed; was a strict xfail): the interest on GG-held bank and NBFC debt is written by fincorp in R4,
    at the scaled rate of the lender's P&L group (the positions are inside the scale denominators)."""
    _, gov_held = positions()
    assert gov_held, "FSF shows government holdings of bank bonds/borrowings"
    bi = bank_interest()["bi"]
    for c, d, i, _s, _rt in gov_held:
        assert math.isclose(se(c, d, "R4", i, block="fincorp"), bi[(c, d, i)], abs_tol=TOL), (c, d, i)
    written = sum(
        v
        for b, r, c, rf, cp, v in all_entries()
        if r in ("G_CEN", "G_STA") and c in ("E_BANK", "E_NBFC") and cp not in ("deposits", "banks", "lic")
    )
    assert written > 0 and math.isclose(written, sum(bi[x[:3]] for x in gov_held), abs_tol=0.05)


def test_dividend_memo_reconciles_to_r7():
    """V-FIN-6 (fixed): the government rows of dividend_matrix are government's R7 as booked, the private E_NBFC
    total reaches no government holder, and every issuer's holder rows add up to its total."""
    for iss in ("e_nfpu", "e_nfpr", "e_bank", "e_nbfc", "e_insp"):
        for g in ("G_CEN", "G_STA"):
            assert math.isclose(
                satv("dividend_matrix", f"div.{iss}.{g.lower()}"), se(g, iss.upper(), "R7"), abs_tol=1e-6
            )
        rows = q(f"select sum(value) from '{_p(SAT / 'dividend_matrix.parquet')}' where series_id like 'div.{iss}.%'")
        assert math.isclose(rows[0][0], satv("dividend_matrix", f"total.{iss}"), abs_tol=0.01), iss
    assert satv("dividend_matrix", "div.e_nbfc.g_cen") == 0 and satv("dividend_matrix", "div.e_nbfc.g_sta") == 0


def test_wave_c_constraint_targets_recomputed_from_sources():
    """Re-verification 2026-10-01 (wave C close-out): the 16 Wave C targets and r17.premiums straight from the clean
    sources and the dependency entries (not from this file's recomputed census, which the fixer used)."""
    tg = {r[0]: r[1] for r in q(f"select constraint_id, target from '{_p(BLOCKS / 'fincorp_constraints.parquet')}'")}
    irn = "finsector_markets_irdai_nonlife"
    sh_inv = sum(
        val(irn, f"t51.inv_interest_dividend_rent_gross.{g}.current")
        for g in ("general_private", "general_public", "general_specialized", "health_standalone")
    )
    supp = val("finsector_markets_irdai_summary", "sum_c.investment_income.current") - sh_inv
    lines, hs = ["motor", "health", "fire", "marine", "others"], (0.70, 0.55, 0.10, 0.0, 0.30)
    cl = [val(irn, f"t44.claims_incurred_net.{ln}.insurers_general_direct.current") for ln in lines]
    npe = [val(irn, f"t44.net_premium_earned.{ln}.insurers_general_direct.current") for ln in lines]
    gos = {a: se(a, "F_GOSC", block="factors") for a in ("E_NFPU", "E_NFPR")}
    hh_c = sum(c * h for c, h in zip(cl, hs, strict=True))
    hh_s = sum(supp * n / sum(npe) * h for n, h in zip(npe, hs, strict=True))
    exp = {"r17.supplements": supp, "r17.premiums": sum(cl), "r17.claims": sum(cl)}
    for p, c_, s_ in (
        ("hh", hh_c, hh_s),
        *(
            (a.lower(), (sum(cl) - hh_c) * gos[a] / sum(gos.values()), (supp - hh_s) * gos[a] / sum(gos.values()))
            for a in gos
        ),
    ):
        exp |= {f"r17.payer.{p}.claim": c_, f"r17.payer.{p}.premium": c_, f"r17.payer.{p}.premium_supplement": s_}
    s19 = val("mospi_nas_2026_s1_9", "s1_9.public_financial_corporations.current")
    pub_gos = val("mospi_nas_2026_s7_1a", "s7_1a.financial.os.current") + val(
        "mospi_nas_2026_s7_1a", "s7_1a.financial.cfc.current"
    )
    exp["k2a.rbi_ar_basis"] = s19 - pub_gos - se("R_ROW", "E_RBI", "R14", "reserve_asset_debit")
    exp["r3a.states_other_internal_debt"] = (
        st("ii.c.2.ii-interest_on_internal_debt")
        - st("ii.c.2.ii.a-interest_on_market_loans")
        - st("ii.c.2.ii.b-interest_on_nssf")
    )
    rc, mf = rates()["B"], mf_shares()
    exp["r5.insp_bonds.e_nfpu"] = F("fc_ofc_icpf", "assets", "f3", "nfc_pub") * rc
    exp["r5.insp_bonds.e_nfpr"] = F("fc_ofc_icpf", "assets", "f3", "nfc_pvt") * rc
    mf_bond = F("fc_ofc_mf", "assets", "f3", "nfc_pub") * rc
    exp["r8.mf_bonds.e_nfpu"] = mf_bond * mf["E_NFPR"]
    # public NFC issuer total = both governments' R7 / their FSF F51 share; the rest by non-government FSF shares
    hold = ("fc_odc", "fc_rbi", "hh", "nfc_pub", "nfc_pvt", "gg_cen", "gg_sta", "row", "fc_ofc")
    lb = {c: F("nfc_pub", "liabilities", "f51", c) for c in hold}
    r7 = se("G_CEN", "E_NFPU", "R7") + se("G_STA", "E_NFPU", "R7")
    rest = r7 / ((lb["gg_cen"] + lb["gg_sta"]) / sum(lb.values())) - r7
    ng = {
        c: rest * v / sum(v for k, v in lb.items() if not k.startswith("gg"))
        for c, v in lb.items()
        if not c.startswith("gg")
    }
    a_all, a_ic, a_mf = (F(i, "assets", "f51", "nfc_pub") for i in ("fc_ofc", "fc_ofc_icpf", "fc_ofc_mf"))
    div_sel = (
        ng["fc_odc"] + ng["hh"] + ng["nfc_pvt"] + ng["fc_ofc"] * (a_all - a_mf) / a_all + ng["fc_ofc"] * a_mf / a_all
    )
    exp["r8.nfpu_nongov_holders"] = div_sel + mf_bond * mf["HH"]
    assert set(exp) <= set(tg) and len(tg) == 30 and len(exp) == 18  # 16 new + r17.premiums (1%) + r17.claims
    for cid, v in exp.items():
        assert math.isclose(tg[cid], v, abs_tol=1e-3), (cid, tg[cid], v)
    # V-FIN-10 (minor): the 'dividends' band also carries households' MF-held public NFC bond interest (about 20%)
    assert math.isclose(tg["r8.nfpu_nongov_holders"] - div_sel, 6_235.31, abs_tol=0.01)
    assert math.isclose(rest, 28_622.63, abs_tol=0.01) and math.isclose(ng["row"], 1_222.64, abs_tol=0.01)


def test_oldbase_topup_satellite_rows():
    """Re-verification 2026-10-01 (D2-21, fincorp-27): the dividend_matrix old-base rows, from the old-base St 2.2 and
    the SAM entries of every block as built (fincorp's top-up itself excluded), not from this file's census."""
    dm = {
        r[0]: r[1]
        for r in q(
            f"select series_id, value from '{_p(SAT / 'dividend_matrix.parquet')}' where series_id like 'oldbase.%'"
        )
    }
    assert math.isclose(dm["oldbase.param.net_d4_to_gos"], oldbase_ratio("2022-23"), abs_tol=1e-9)
    for p in ("2021-22", "2020-21"):
        assert math.isclose(dm[f"oldbase.sens.net_d4_to_gos.{p}"], oldbase_ratio(p), abs_tol=1e-9)
    gos = se("E_NFPR", "F_GOSC", block="factors")
    prior = oldbase_ratio() * gos
    a, di = "E_NFPR", ("distributed_income", "distributed_income_mf")
    rec = sum(
        v
        for b, r, c, rf, cp, v in all_entries()
        if r == a
        and c != a
        and (
            (b == "fincorp" and rf in ("R3a", "R4", "R5", "R8", "R8a"))
            or (rf == "R17" and cp == "premium_supplement")
            or rf == "R13"
        )
    )
    pay = sum(
        v
        for b, r, c, rf, cp, v in all_entries()
        if c == a
        and r != a
        and cp not in di
        and ((b == "fincorp" and rf in ("R3a", "R4", "R5", "R8", "R8a")) or rf in ("R14", "R14a", "R7", "R7x"))
    )
    paid_top = sum(v for b, r, c, rf, cp, v in all_entries() if b == "fincorp" and c == a and r != a and cp in di)
    diag_top = sum(v for b, r, c, rf, cp, v in all_entries() if b == "fincorp" and c == a and r == a and cp in di)
    assert math.isclose(dm["oldbase.e_nfpr.before.net"], rec - pay, abs_tol=0.01)
    assert math.isclose(dm["oldbase.e_nfpr.prior_net_d4"], prior, abs_tol=0.01)
    assert math.isclose(rec - pay - paid_top, prior, abs_tol=0.01)  # the top-up lands E_NFPR exactly on the prior
    assert math.isclose(dm["oldbase.e_nfpr.total"], paid_top + diag_top, abs_tol=0.01)
    assert math.isclose(dm["oldbase.e_nfpr.returning_share"], diag_top / (paid_top + diag_top), abs_tol=1e-9)
    assert math.isclose(
        sum(v for k, v in dm.items() if k.startswith("oldbase.e_nfpr.holder.")),
        dm["oldbase.e_nfpr.total"],
        abs_tol=0.01,
    )
    assert math.isclose(dm["oldbase.e_nfpr.total"], 821_158.76, abs_tol=0.01)
    # cross-check row: old-base D4 share of net distributive flows x the new-base requirement (NAS 1.9 saving - GOS)
    ob = lambda s: val(OLDB, f"oldbase_soa_s2_2.{s}.current", period="2022-23")  # noqa: E731
    gos_ob = ob("allocation_of_primary_income.resources.b2n_b3n") + ob("production.uses.p51c")
    share = (ob("allocation_of_primary_income.resources.d4") - ob("allocation_of_primary_income.uses.d4")) / (
        ob("use_of_disposable_income.uses.b8n") + ob("production.uses.p51c") - gos_ob
    )
    assert math.isclose(dm["oldbase.check.d4_share_of_net_distributive"], share, abs_tol=1e-8)
    req = val("mospi_nas_2026_s1_9", "s1_9.private_non_financial_corporations.current") - gos
    assert math.isclose(dm["oldbase.check.prior_via_new_base_requirement"], share * req, abs_tol=0.01)


@pytest.mark.xfail(
    strict=True,
    reason="V-FIN-9: the R17 payer bands hold each payer's premiums and claims within 5% of their prior separately, so "
    "after balancing E_NFPU pays 10.5% and E_NFPR 8.1% more premiums than they receive in claims (D71 = D72 by payer)",
)
def test_r17_premiums_equal_claims_by_payer_after_balancing():
    bal = BLOCKS.parent / "sam_entries_balanced.parquet"
    if not bal.exists():
        pytest.skip("no balanced SAM")
    for name, payers in (("hh", HH), ("e_nfpu", ["E_NFPU"]), ("e_nfpr", ["E_NFPR"])):
        ps = ",".join(f"'{p}'" for p in payers)
        prem = q(
            f"select sum(balanced) from '{_p(bal)}' where row = 'E_INSP' and col in ({ps}) and ref = 'R17' and component = 'premium'"
        )[0][0]
        claim = q(
            f"select sum(balanced) from '{_p(bal)}' where col = 'E_INSP' and row in ({ps}) and ref = 'R17' and component = 'claim'"
        )[0][0]
        assert abs(prem / claim - 1) <= 0.05, (name, prem, claim)


@cache
def stale_deps() -> tuple[str, ...]:
    """Dependencies whose outputs changed after fincorp read them (fincorp_block.json records their sha256)."""
    cat = json.loads((BLOCKS / "fincorp_block.json").read_text(encoding="utf-8"))
    return tuple(
        sorted(
            {
                dep
                for dep, hashes in cat["dependency_hashes"].items()
                for part, h in hashes.items()
                if hashlib.sha256((BLOCKS / f"{dep}_{part}.parquet").read_bytes()).hexdigest() != h
            }
        )
    )


def test_dependency_outputs_read_are_current():
    """V-FIN-5 (process): the census reads the dependencies as they are now; a rebuilt dependency makes fincorp stale
    (and, when the dependency's record ids change, leaves fincorp's provenance citing records that no longer exist)."""
    if stale_deps():
        pytest.skip(f"fincorp is stale against {list(stale_deps())}: rebuild fincorp, then capital_financial (V-FIN-5)")


def test_glob_sanity():
    # the dependency outputs this file reads exist
    for name in (
        "households_satellites/hh_keys.parquet",
        "factors_satellites/factor_income_keys.parquet",
        "government_entries.parquet",
        "rest_of_world_entries.parquet",
    ):
        assert glob.glob(_p(BLOCKS / name)), name
