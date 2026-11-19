"""Independent verification of the rbi_financial_accounts unit (Phase 1, verifier first pass, 2026-09-29).

This file does NOT import the unit's code. It re-reads the pinned raw files itself and compares them with
data/clean/rbi_financial_accounts/:
- FSF workbook: openpyxl in read-only/values mode (the unit uses openpyxl's random-access mode). The verifier
  has its own maps: sheet title -> sector, SNA code -> instrument, counterparty labels, S 6/S 7/S 8 labels.
  This is a full census in both directions: every clean row has its raw cell, and every non-blank raw cell has
  a clean row.
- Bulletin 52(a)/52(b) and DEA PDFs: pypdf text (the unit uses pdfplumber) with the verifier's own row lists.
  This is also a full census, plus literal anchors that the verifier typed by hand from the page text
  (HAND_ANCHORS).
- HBS HTML tables: pandas.read_html/lxml (the unit uses BeautifulSoup). Full census.
- Semantics: stock dates, FWTW orientation, QR 2023 labels against the Status Paper.

SOURCE MISPRINT (verifier first pass, verify-1; fixed by the builder as rbi_financial_accounts-18):
QR Jan-Mar 2023 Table 4.4 prints the rows '11. Pension Fund' and '12. Others' swapped. The printed
'Pension Fund' row carries values for Mar-Dec 2021, when pension funds were still inside 'Others' (the '-'
cells sit on the printed 'Others' row), and every overlapping date equals the Status Paper's 'Others'
figure. Second pass: the census derives the swap independently. It asserts the printed '-' pattern in the
PDF text and only then maps printed 'Pension Fund' -> others and printed 'Others' -> pension_funds. The
flags (dim_other printed_as=..., item_label as printed, separate provenance block) and the agreement with
T2.10, QR 2024 T4.4 and HB-5 are tested in test_qr2023_pension_others_labels_agree_with_status_paper and
test_qr2023_swap_flags_and_provenance.
"""

from __future__ import annotations

import hashlib
import random
import re
from collections import defaultdict
from functools import cache
from pathlib import Path

import openpyxl
import pandas as pd
import polars as pl
import pypdf
import pytest
import yaml

pytestmark = pytest.mark.quality

ROOT = Path(__file__).resolve().parents[2]
UNIT = "rbi_financial_accounts"
CLEAN = ROOT / "data" / "clean" / UNIT
PINS = ROOT / "data" / "raw_pins" / f"{UNIT}.yaml"
SEED = 20260929
TOL = 1e-6  # clean values are rounded to 6 decimals on write

FSF = "rbi_fsf_fof/FSF2023-24_21012026.xlsx"
T52A = "rbi_hh_fin_savings/bulletin_2026_09_t52a.pdf"
T52B = "rbi_hh_fin_savings/bulletin_2026_09_t52b.pdf"
SP = "dea_public_debt_reports/dea_status_paper_2023_24.pdf"
QR23 = "dea_public_debt_reports/dea_qr_jan_mar_2023.pdf"
QR24 = "dea_public_debt_reports/dea_qr_jan_mar_2024.pdf"


# ------------------------------------------------------------------------------------------------
# independent helpers
# ------------------------------------------------------------------------------------------------


@cache
def pins() -> dict:
    return yaml.safe_load(PINS.read_text(encoding="utf-8"))["pins"]


@cache
def raw(key: str) -> Path:
    p = pins()[key]
    path = ROOT / p["path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == p["sha256"], f"{key}: sha256 mismatch"
    return path


@cache
def clean(ds: str) -> pl.DataFrame:
    return pl.read_parquet(CLEAN / f"{UNIT}_{ds}.parquet")


def norm(s) -> str:
    s = str(s).replace(" ", " ").lower().replace("non-financial", "nonfinancial")
    s = s.replace("non financial", "nonfinancial")
    s = re.sub(r"[()]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def num(x):
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(",", "")
    if s in ("", "-", "--", "nan", "NaN", "NA", "n.a."):
        return None
    return float(s)


def close(a: float, b: float, tol: float = TOL) -> bool:
    return abs(a - b) <= tol + 1e-12 * abs(b)


def end_march(fy: str) -> str:
    m = re.fullmatch(r"(\d{4})-(\d{2})", fy.strip())
    assert m and (int(m.group(1)) + 1) % 100 == int(m.group(2)), fy
    return f"{int(m.group(1)) + 1}-03-31"


def compare(name: str, exp: dict, got: dict, tol: float = TOL) -> int:
    """exp/got: key -> value. Both directions; returns the number of values compared."""
    missing = sorted(set(exp) - set(got), key=str)
    extra = sorted(set(got) - set(exp), key=str)
    bad = [(k, got[k], exp[k]) for k in exp.keys() & got.keys() if not close(got[k], exp[k], tol)]
    n = len(exp.keys() & got.keys())
    print(f"[spotcheck] {name}: compared {n}, mismatched {len(bad)}, raw-not-clean {len(missing)}, "
          f"clean-not-raw {len(extra)}")
    assert not missing, f"{name}: {len(missing)} raw values missing from clean, e.g. {missing[:6]}"
    assert not extra, f"{name}: {len(extra)} clean rows with no raw cell, e.g. {extra[:6]}"
    assert not bad, f"{name}: {len(bad)} of {n} values differ, e.g. {bad[:6]}"
    return n


# ------------------------------------------------------------------------------------------------
# FSF workbook (openpyxl read-only, own maps)
# ------------------------------------------------------------------------------------------------

# the verifier's own map: normalised sheet title (after 'Statement x.y:') -> sector code
MY_TITLES = {
    "financial corporations": "fc",
    "reserve bank of india": "fc_rbi",
    "other depository corporations": "fc_odc",
    "scheduled commercial banks includes regional rural banks": "fc_odc_scb",
    "co-operative banks and credit societies": "fc_odc_coop",
    "non-banking finance companies - deposit taking": "fc_odc_nbfc_dt",
    "housing finance companies - deposit taking": "fc_odc_hfc_dt",
    "other financial corporations": "fc_ofc",
    "all-india financial institutions aifi": "fc_ofc_aifi",
    "state finance corporations": "fc_ofc_sfc",
    "state industrial development corporations": "fc_ofc_sidc",
    "non-banking finance companies-non-deposit taking": "fc_ofc_nbfc_ndt",
    "housing finance companies - non-deposit taking": "fc_ofc_hfc_ndt",
    "mutual funds": "fc_ofc_mf",
    "other mutual funds": "fc_ofc_mf_other",
    "money market mutual funds": "fc_ofc_mf_mmf",
    "insurance and pension and provident funds": "fc_ofc_icpf",
    "insurance": "fc_ofc_icpf_ins",
    "provident & pension funds non- government": "fc_ofc_icpf_pf",
    "nonfinancial corporations": "nfc",
    "public nonfinancial corporations": "nfc_pub",
    "central public sector enterprises": "nfc_pub_cpse",
    "power companies": "nfc_pub_power",
    "port trusts": "nfc_pub_ports",
    "private nonfinancial corporations": "nfc_pvt",
    "general government": "gg",
    "central government": "gg_cen",
    "state governments": "gg_sta",
    "households including non-profit institutions serving households": "hh",
    "rest of the world": "row",
}
MY_CODES = {  # SNA code in column C
    "F1": "f1", "F11": "f11", "F12": "f12", "F2": "f2", "F21": "f21", "F22 & F29": "f22_f29", "F3": "f3",
    "F4": "f4", "F5": "f5", "F51": "f51", "F52": "f52", "F521": "f521", "F522": "f522", "F6": "f6",
    "F61": "f61", "F62": "f62", "F63": "f63", "F64": "f64", "F66": "f66", "F8": "f8", "F81": "f81",
    "F89": "f89",
}
MY_UNCODED = [("provident fund", "f6_pf"), ("viii. other", "other"), ("ix. nec", "nec"),
              ("gross financial", "total")]
MY_CPTY = {
    "residents": "residents", "central bank": "fc_rbi", "other depository corporations": "fc_odc",
    "other financial corporations": "fc_ofc", "general government": "gg", "central government": "gg_cen",
    "state and local government": "gg_sta", "public nonfinancial corporations": "nfc_pub",
    "private nonfinancial corporations": "nfc_pvt", "other resident sectors": "other_resident",
    "households including npishs": "hh", "rest of the world": "row",
}
MY_MEASURES = {"outstanding": "outstanding", "transaction": "transaction", "valuation": "valuation"}


@cache
def fsf_sheets() -> dict[str, list[tuple]]:
    wb = openpyxl.load_workbook(raw(FSF), read_only=True, data_only=True)
    out = {ws.title: [tuple(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}
    wb.close()
    return out


def cell(rows, r, c):  # 0-based
    row = rows[r] if r < len(rows) else ()
    return row[c] if c < len(row) else None


def fsf_st_expected() -> tuple[dict, list]:
    exp, blanks = {}, []
    for sheet, rows in fsf_sheets().items():
        if not sheet.startswith("St "):
            continue
        title = norm(re.sub(r"^\s*statement\s*[\d.]+\s*:?", "", str(cell(rows, 1, 1)), flags=re.I))
        inst = MY_TITLES[title]
        heads = [i for i, r in enumerate(rows) if norm(cell(rows, i, 1)) in
                 ("financial liabilities/sources", "financial assets/uses")]
        assert len(heads) == 2, (sheet, heads)
        for h in heads:
            side = "liabilities" if "liabilities" in norm(cell(rows, h, 1)) else "assets"
            mrow = next(i for i in range(h - 1, h - 5, -1) if norm(cell(rows, i, 3)) == "outstanding")
            starts = sorted((c, MY_MEASURES[norm(v)]) for c, v in enumerate(rows[mrow])
                            if v is not None and norm(v) in MY_MEASURES)
            cols = {}
            for c, y in enumerate(rows[h]):
                if c < 3 or y is None:
                    continue
                meas = [m for c0, m in starts if c0 <= c][-1]
                cols[c] = (meas, str(y).strip())
            instr, cp = None, None
            for i in range(h + 1, len(rows)):
                lab = cell(rows, i, 1)
                if lab is None:
                    continue
                code = cell(rows, i, 2)
                n = norm(lab)
                if code is not None and str(code).strip():
                    instr, cp = MY_CODES[str(code).strip()], "all"
                elif any(n.startswith(p) for p, _ in MY_UNCODED):
                    instr, cp = next(s for p, s in MY_UNCODED if n.startswith(p)), "all"
                else:
                    cp = MY_CPTY[n]
                for c, (meas, fy) in cols.items():
                    v = num(cell(rows, i, c))
                    period = end_march(fy) if meas == "outstanding" else fy
                    key = (inst, side, meas, instr, cp, period)
                    if v is None:
                        blanks.append((sheet, i + 1, c + 1, key))
                        continue
                    assert key not in exp, f"duplicate raw key {key} at {sheet} r{i + 1}"
                    exp[key] = v
                if n.startswith("gross financial"):
                    break
    return exp, blanks


def test_fsf_balance_sheets_census():
    exp, blanks = fsf_st_expected()
    df = clean("fsf_balance_sheets")
    got = {}
    for inst, side, dim, instr, cp, period, v in df.select(
        "institution", "side", "dim_other", "instrument", "counterparty", "period", "value"
    ).iter_rows():
        got[(inst, side, dim.split("=")[1], instr, cp, period)] = v
    assert len(got) == df.height
    compare("FSF St 1-5 balance sheets", exp, got)
    # blanks in the workbook: exactly the 12 cells the unit documents (St 1 assets, loans, 'Residents', R:AC)
    assert len(blanks) == 12 and {b[0] for b in blanks} == {"St 1"} and {b[1] for b in blanks} == {167}, blanks[:3]


MY_SECTORS = {
    "central bank": "fc_rbi", "other depository corporations": "fc_odc", "other financial corporations": "fc_ofc",
    "general government": "gg", "public nonfinancial corporations": "nfc_pub",
    "private nonfinancial corporations": "nfc_pvt", "other resident sectors": "other_resident",
    "households including npishs": "hh", "rest of the world": "row", "total": "all",
}


def _matrix(rows, title_row: int, label_col: int):
    """Return (header row, {col: (sector, side)})."""
    head = next(i for i in range(title_row + 1, title_row + 5) if norm(cell(rows, i, 3)) == "central bank")
    cols, sec = {}, None
    for c in range(3, len(rows[head]) + 1):
        v = cell(rows, head, c)
        if v is not None:
            sec = MY_SECTORS[norm(v)]
        su = norm(cell(rows, head + 1, c))
        if su in ("sources", "uses"):
            cols[c] = (sec, "liabilities" if su == "sources" else "assets")
    assert len(cols) == 18, (title_row, cols)
    return head, cols


def fsf_s6_expected() -> dict:
    exp = {}
    for sheet, rows in fsf_sheets().items():
        if not sheet.startswith("S 6."):
            continue
        for t, r in enumerate(rows):
            lab = str(cell(rows, t, 1) or "")
            m = re.match(r"\s*Statement\s*6\.\d+(?:\.[ab])?\s*:\s*Financial (Outstanding|Flows).*?(\d{4}-\d{2})", lab, re.I)
            if not m:
                continue
            meas = "outstanding" if m.group(1).lower() == "outstanding" else "transaction"
            period = end_march(m.group(2)) if meas == "outstanding" else m.group(2)
            head, cols = _matrix(rows, t, 2)
            for i in range(head + 2, head + 12):
                cp = MY_SECTORS[norm(cell(rows, i, 2))]
                for c, (sec, side) in cols.items():
                    exp[(sec, side, meas, cp, period)] = num(cell(rows, i, c))
    return exp


def test_fsf_fwtw_census():
    exp = fsf_s6_expected()
    df = clean("fsf_fwtw")
    got = {(a, b, d.split("=")[1], cp, p): v for a, b, d, cp, p, v in
           df.select("institution", "side", "dim_other", "counterparty", "period", "value").iter_rows()}
    compare("FSF S 6 FWTW", exp, got)


MY_S7 = {
    "i. monetary gold and sdrs": "f1", "monetary gold and sdrs": "f1", "monetary gold": "f11", "sdrs": "f12",
    "currency and deposits": "f2", "currency": "f21", "deposits": "f22_f29", "debt securities": "f3",
    "loans": "f4", "equity and investment fund shares": "f5", "equity": "f51",
    "investment fund shares/ units": "f52",
    "insurance, pension, provident and standardised guarantee schemes": "f6",
    "non-life insurance technical reserves": "f61", "life insurance and annuity entitlements": "f62",
    "pension entitlements": "f63", "provident funds": "f6_pf", "claims of pension funds on pension managers": "f64",
    "provisions for calls under standardised guarantees": "f66", "other account receivable / payable": "f8",
    "trade credit and advances": "f81",
    "other account receivable / payable, except trade credit and advances": "f89",
    "foreign claims not elsewhere classified": "foreign_nec", "other items not elsewhere classified": "other_nec",
    "total": "total",
}


def fsf_s7_expected() -> dict:
    exp = {}
    for sheet, rows in fsf_sheets().items():
        if not sheet.startswith("S 7."):
            continue
        for t in range(len(rows)):
            lab = str(cell(rows, t, 1) or "")
            m = re.match(r"\s*STATEMENT\s*7\.\d+(?:\.[ab])?\s*:\s*FINANCIAL (OUTSTANDING|FLOWS).*?(\d{4}-\d{2})", lab, re.I)
            if not m:
                continue
            meas = "outstanding" if m.group(1).upper() == "OUTSTANDING" else "transaction"
            period = end_march(m.group(2)) if meas == "outstanding" else m.group(2)
            head, cols = _matrix(rows, t, 2)
            for i in range(head + 2, len(rows)):
                lab2 = cell(rows, i, 2)
                if lab2 is None:
                    continue
                ins = MY_S7[norm(lab2)]
                for c, (sec, side) in cols.items():
                    k = (sec, side, meas, ins, period)
                    assert k not in exp, (sheet, i, k)
                    exp[k] = num(cell(rows, i, c))
                if ins == "total":
                    break
    return exp


def test_fsf_instrument_sector_census():
    exp = fsf_s7_expected()
    df = clean("fsf_instrument_sector")
    got = {(a, b, d.split("=")[1], ins, p): v for a, b, d, ins, p, v in
           df.select("institution", "side", "dim_other", "instrument", "period", "value").iter_rows()}
    compare("FSF S 7 instrument x sector", exp, got)


MY_S8 = {"S 8.1": "nfc_pvt", "S 8.2": "gg", "S 8.3": "hh"}
MY_S8_ITEMS = {"financial resources": "financial_resources", "financial uses": "financial_uses",
               "financial deficit": "financial_deficit"}


def fsf_s8_expected() -> dict:
    exp = {}
    for sheet, inst in MY_S8.items():
        rows = fsf_sheets()[sheet]
        for t in range(len(rows)):
            m = re.match(r"\s*Statement\s*8\.\d\.[ab]\s*:\s*Financing of the (.+?)[\[(](Outstanding|Flow)",
                         str(cell(rows, t, 1) or ""))
            if not m:
                continue
            meas = "outstanding" if m.group(2) == "Outstanding" else "transaction"
            head = next(i for i in range(t + 1, t + 4) if norm(cell(rows, i, 2)) == "item")
            years = {c: str(v).strip() for c, v in enumerate(rows[head]) if c >= 3 and v is not None}
            fin = False
            for i in range(head + 1, head + 14):
                lab = norm(cell(rows, i, 2))
                if lab.startswith("deficit financed by"):
                    fin = True
                    continue
                item, cp = ("financed_by", MY_SECTORS[lab]) if fin else (MY_S8_ITEMS[lab], None)
                for c, fy in years.items():
                    exp[(inst, f"{meas}.{item}", cp, end_march(fy) if meas == "outstanding" else fy)] = num(
                        cell(rows, i, c))
    return exp


def test_fsf_financing_census():
    exp = fsf_s8_expected()
    df = clean("fsf_financing")
    got = {(a, ic, cp, p): v for a, ic, cp, p, v in
           df.select("institution", "item_code", "counterparty", "period", "value").iter_rows()}
    compare("FSF S 8 financing", exp, got)


def test_fsf_semantics():
    """Orientation and dates that a census cannot see."""
    bs = clean("fsf_balance_sheets")

    def v(**kw):
        d = bs
        for k, x in kw.items():
            d = d.filter(pl.col(k) == x)
        assert d.height == 1, kw
        return d["value"][0]

    # stock header '2023-24' = end-March 2024 (the article: 'NFW ... at end-March 2024, up from ... 2022-23')
    assert set(bs.filter(pl.col("stock_flow") == "stock")["period"].str.slice(5)) == {"03-31"}
    assert bs.filter(pl.col("stock_flow") == "stock")["period"].max() == "2024-03-31"
    # FWTW: cell (row = HH, column = Central bank 'Sources') is RBI's currency liability to households; the
    # 2023-24 flow 1,18,026 equals FSF St 4 HH currency acquisition and St 1.1 RBI F21 liability to HH
    fw = clean("fsf_fwtw").filter((pl.col("period") == "2023-24") & (pl.col("institution") == "fc_rbi")
                                  & (pl.col("side") == "liabilities") & (pl.col("counterparty") == "hh"))
    assert close(fw["value"][0], 118026.0, 1e-3)
    assert close(v(institution="hh", side="assets", dim_other="measure=transaction", instrument="f21",
                   counterparty="all", period="2023-24"), 118026.0, 1e-3)
    assert close(v(institution="fc_rbi", side="liabilities", dim_other="measure=transaction", instrument="f21",
                   counterparty="hh", period="2023-24"), 118026.0, 1e-3)
    # K8 claim in the coverage file: HH loans from ODC / OFC 2022-23 -> 2023-24
    for per, odc, ofc in (("2022-23", 1252313, 343354), ("2023-24", 1877458, 1208)):
        assert abs(v(institution="hh", side="liabilities", dim_other="measure=transaction", instrument="f4",
                     counterparty="fc_odc", period=per) - odc) < 1
        assert abs(v(institution="hh", side="liabilities", dim_other="measure=transaction", instrument="f4",
                     counterparty="fc_ofc", period=per) - ofc) < 1
    # K9b note: RBI F89 payable to the Centre, flow 2023-24 1,21,648 and stock end-March 2024 2,22,372
    assert abs(v(institution="fc_rbi", side="liabilities", dim_other="measure=transaction", instrument="f89",
                 counterparty="gg_cen", period="2023-24") - 121648) < 1
    assert abs(v(institution="fc_rbi", side="liabilities", dim_other="measure=outstanding", instrument="f89",
                 counterparty="gg_cen", period="2024-03-31") - 222372) < 1


# ------------------------------------------------------------------------------------------------
# Bulletin 52(a) / 52(b) (pypdf, own row lists)
# ------------------------------------------------------------------------------------------------

NUM = r"-?\d+(?:\.\d+)?"


@cache
def pdf_pages(key: str) -> list[str]:
    return [p.extract_text() for p in pypdf.PdfReader(raw(key)).pages]


def numeric_rows(text: str, n: int) -> list[tuple[str, list[float]]]:
    out = []
    for line in text.splitlines():
        m = re.match(rf"^(.*?[A-Za-z)].*?)\s+((?:{NUM}\s+){{{n - 1}}}{NUM})\s*$", line.strip())
        if m:
            out.append((m.group(1).strip(), [float(x) for x in m.group(2).split()]))
    return out


# 52(a): every numeric row in page order -> (verifier's label check, clean series stem)
MY_52A = [
    ("net financial assets", "t52a.nfa.current"), ("per cent of gdp", "t52a.nfa_pct_gdp.n_a"),
    ("i. financial assets", "t52a.fa.current"), ("per cent of gdp", "t52a.fa_pct_gdp.n_a"),
    ("1. total deposits", "t52a.fa_deposits.current"), ("(a) bank deposits", "t52a.fa_deposits_bank.current"),
    ("i. commercial banks", "t52a.fa_deposits_bank_scb.current"),
    ("ii. co-operative banks", "t52a.fa_deposits_bank_coop.current"),
    ("(b) non-bank deposits", "t52a.fa_deposits_nonbank.current"),
    ("other financial institutions (i+ii)", "t52a.fa_deposits_nonbank_ofi.current"),
    ("i. non-banking financial companies", "t52a.fa_deposits_nonbank_ofi_nbfc.current"),
    ("ii. housing finance companies", "t52a.fa_deposits_nonbank_ofi_hfc.current"),
    ("2. life insurance funds", "t52a.fa_life_insurance.current"),
    ("3. provident and pension funds", "t52a.fa_pf_pension_incl_ppf.current"),
    ("4. currency", "t52a.fa_currency.current"), ("5. investments", "t52a.fa_investments.current"),
    ("(a) mutual funds", "t52a.fa_investments_mf.current"), ("(b) equity", "t52a.fa_investments_equity.current"),
    ("6. small savings", "t52a.fa_small_savings_excl_ppf.current"),
    ("ii. financial liabilities", "t52a.fl.current"), ("per cent of gdp", "t52a.fl_pct_gdp.n_a"),
    ("1. financial corporations", "t52a.fl_fc.current"), ("(a) banking sector", "t52a.fl_fc_banks.current"),
    ("i. commercial banks", "t52a.fl_fc_banks_scb.current"),
    ("(b) other financial institutions", "t52a.fl_fc_ofi.current"),
    ("i. non-banking financial companies", "t52a.fl_fc_ofi_nbfc.current"),
    ("ii. housing finance companies", "t52a.fl_fc_ofi_hfc.current"),
    ("iii. insurance corporations", "t52a.fl_fc_ofi_insurance.current"),
    ("2. non-financial corporations", "t52a.fl_nfc_pvt.current"), ("3. general government", "t52a.fl_gg.current"),
]
MY_52B = [
    ("financial assets", "t52b.fa.current"), ("per cent of gdp", "t52b.fa_pct_gdp.n_a"),
    ("(a) bank deposits", "t52b.fa_deposits_bank.current"), ("i. commercial banks", "t52b.fa_deposits_bank_scb.current"),
    ("ii. co-operative banks", "t52b.fa_deposits_bank_coop.current"),
    ("other financial institutions", "t52b.fa_deposits_nonbank_ofi.current"),
    ("i. non-banking financial companies", "t52b.fa_deposits_nonbank_ofi_nbfc.current"),
    ("ii. housing finance companies", "t52b.fa_deposits_nonbank_ofi_hfc.current"),
    ("(c) life insurance funds", "t52b.fa_life_insurance.current"), ("(d) currency", "t52b.fa_currency.current"),
    ("(e) investments", "t52b.fa_investments.current"), ("(i) mutual funds", "t52b.fa_investments_mf.current"),
    ("(ii) equity", "t52b.fa_investments_equity.current"), ("(f) public provident fund", "t52b.fa_ppf.current"),
    ("(g) pension funds", "t52b.fa_pension_funds.current"),
    ("(h) small savings", "t52b.fa_small_savings_excl_ppf.current"),
    ("financial liabilities", "t52b.fl.current"), ("per cent of gdp", "t52b.fl_pct_gdp.n_a"),
    ("(a) banking sector", "t52b.fl_banks.current"), ("i. commercial banks", "t52b.fl_banks_scb.current"),
    ("ii. co-operative banks", "t52b.fl_banks_coop.current"),
    ("(b) other financial institutions", "t52b.fl_ofi.current"),
    ("i. non-banking financial companies", "t52b.fl_ofi_nbfc.current"),
    ("ii. housing finance companies", "t52b.fl_ofi_hfc.current"),
    ("iii. insurance corporations", "t52b.fl_ofi_insurance.current"),
]
MONTH_END = {"Jun": "06-30", "Sep": "09-30", "Dec": "12-31", "Mar": "03-31"}


def t52_expected() -> dict:
    exp = {}
    for page in pdf_pages(T52A):
        fy = re.search(r"Item\s+(\d{4}-\d{2})", page).group(1)
        rows = numeric_rows(page, 5)
        rows = [r for r in rows if not r[0].startswith("RBI Bulletin")]
        assert len(rows) == len(MY_52A), (fy, len(rows))
        for (lab, vals), (want, stem) in zip(rows, MY_52A, strict=True):
            assert norm(lab).startswith(norm(want)), (fy, lab, want)
            for q, x in zip(("Q1", "Q2", "Q3", "Q4"), vals[:4], strict=True):
                exp[(f"{stem}.fq", f"{q} {fy}")] = x
            exp[(f"{stem}.fy", fy)] = vals[4]
    for page in pdf_pages(T52B):
        dates = re.search(r"Item\s+((?:[A-Z][a-z]{2}-\d{4}\s*){4})", page).group(1).split()
        periods = [f"{d[4:]}-{MONTH_END[d[:3]]}" for d in dates]
        rows = numeric_rows(page, 4)
        assert len(rows) == len(MY_52B), (dates, len(rows))
        for (lab, vals), (want, stem) in zip(rows, MY_52B, strict=True):
            assert norm(lab).startswith(norm(want)), (dates, lab, want)
            for p, x in zip(periods, vals, strict=True):
                exp[(stem, p)] = x
    return exp


def test_52ab_census():
    exp = t52_expected()
    df = clean("hh_finsav_52ab")
    got = {(s, p): v for s, p, v in df.select("series_id", "period", "value").iter_rows()}
    compare("Bulletin 52(a)/(b)", exp, got)
    # period semantics: 52(a) annual = FY, 52(b) quarter-end stocks; stages per table note 2
    a = df.filter(pl.col("table_id") == "Table 52(a)")
    stage = dict(a.select("period", "estimate_stage").unique().iter_rows())
    assert all(stage[p] == ("Preliminary" if "2025-26" in p else "Revised") for p in stage)
    b = df.filter(pl.col("table_id") == "Table 52(b)")
    assert set(b["period_type"]) == {"date"} and set(b["stock_flow"]) <= {"stock", "n/a"}
    pct = df.filter(pl.col("unit") == "percent")
    assert set(pct["base_year"]) == {"2022-23"} and set(pct["price_basis"]) == {"n/a"}


# ------------------------------------------------------------------------------------------------
# HBS HTML tables (pandas.read_html, own maps)
# ------------------------------------------------------------------------------------------------


@cache
def hbs(t: int) -> list[pd.DataFrame]:
    return pd.read_html(raw(f"rbi_hbs/hbs_t{t}.html"))


MY_T11 = {
    "1 gross savings": "gross_saving", "1.1 nonfinancial corporations": "gross_saving_nfc",
    "1.1.1 public nonfinancial corporations": "gross_saving_nfc_pub",
    "1.1.2 private nonfinancial corporations": "gross_saving_nfc_pvt",
    "1.2 financial corporations": "gross_saving_fc", "1.2.1 public financial corporations": "gross_saving_fc_pub",
    "1.2.2 private financial corporations": "gross_saving_fc_pvt", "1.3 general government": "gross_saving_gg",
    "1.4 household sector": "gross_saving_hh", "1.4.1.1 gross financial saving": "gross_financial_saving_hh",
    "1.4.1.2 less financial liabilities": "financial_liabilities_hh",
    "1.4.2 saving in physical assets": "saving_physical_assets_hh",
    "1.4.3 saving in the form of gold and silver ornaments": "saving_gold_silver_hh",
}
MY_T11_DEPT = {"1.1.1.1": "gross_saving_nfc_pub_dept", "1.1.1.2": "gross_saving_nfc_pub_nondept",
               "1.2.1.1": "gross_saving_fc_pub_dept", "1.2.1.2": "gross_saving_fc_pub_nondept"}
MY_T12A = {"currency": "currency", "bank deposits": "bank_deposits", "non-banking deposits": "nonbank_deposits",
           "life insurance fund": "life_insurance_fund", "provident and pension fund": "pf_pension_fund",
           "claims on government": "claims_on_government", "shares & debentures": "shares_debentures",
           "units of uti": "units_of_uti", "trade debt net": "trade_debt_net",
           "changes in financial assets 2 to 10": "financial_assets"}
MY_T12L = {"bank advances": "bank_advances", "loans & advances from other financial institutions": "loans_from_ofi",
           "loans & advances from government": "loans_from_government",
           "loans & advances from co-operative non-credit societies": "loans_from_coop_noncredit",
           "changes in financial liabilities 12 to 15": "financial_liabilities"}


def hbs_expected() -> dict:
    exp = {}
    # T11
    t = hbs(11)[1]
    years = [str(x) for x in t.iloc[1, 1:]]
    bases = ["2011" if "2011-12" in str(x) else "2022" for x in t.iloc[3, 1:]]
    for r in range(4, len(t)):
        lab = str(t.iloc[r, 0])
        if lab.lower().startswith("note"):
            break
        code = MY_T11_DEPT.get(lab.split()[0]) or MY_T11[norm(lab)]
        for y, b, x in zip(years, bases, t.iloc[r, 1:], strict=True):
            exp[("hbs_saving", f"t11.{code}.base{b}.current", y)] = num(x)
    # T12
    a, lia = hbs(12)[1], hbs(12)[2]
    for tab, m, side, hdr in ((a, MY_T12A, "assets", 1), (lia, MY_T12L, "liabilities", 2)):
        codes = [m[norm(h)] for h in tab.iloc[hdr, 1:]]
        for r in range(hdr + 2, len(tab)):
            y = str(tab.iloc[r, 0])
            if not re.fullmatch(r"\d{4}-\d{2}", y):
                continue
            for c, x in zip(codes, tab.iloc[r, 1:], strict=True):
                if num(x) is not None:
                    exp[("hbs_saving", f"t12.{side}.{c}.current", y)] = num(x)
    # T107
    holders = {"1": "commercial_banks", "2": "cooperative_banks", "3": "non_bank_pds", "4": "insurance",
               "5": "mutual_funds", "6": "provident_funds", "7": "pension_funds", "8": "financial_institutions",
               "9": "corporates", "10": "fpi", "11": "rbi", "12": "others", "12.1": "others_state_governments"}
    panels = {"central government dated securities": "gsec_central", "state governments securities": "sgs",
              "treasury bills": "tbills"}
    for tab in hbs(107)[1:]:
        ins = panels[norm(tab.iloc[1, 1] if "Per cent" in str(tab.iloc[0, 0]) else tab.iloc[0, 1])]
        yrow = next(i for i in range(4) if str(tab.iloc[i, 1]).strip() == "2022")
        dates = [f"{int(str(y))}-03-31" for y in tab.iloc[yrow, 1:]]
        for r in range(yrow + 2, len(tab)):
            lab = str(tab.iloc[r, 0])
            if lab.lower().startswith("note"):
                break
            if "Total" in lab:
                sid = f"t107.{ins}.outstanding.current"
            else:
                sid = f"t107.{ins}.share.{holders[lab.split()[0]]}"
            for d, x in zip(dates, tab.iloc[r, 1:], strict=True):
                exp[("hbs_gsec_ownership", sid, d)] = num(x)
    # T109: cols 1..8 = deposits R/O, certificates R/O, PPF R/O, total R/O
    t = hbs(109)[1]
    cols = [("deposits", "receipts"), ("deposits", "outstanding"), ("certificates", "receipts"),
            ("certificates", "outstanding"), ("ppf", "receipts"), ("ppf", "outstanding"), ("total", "receipts"),
            ("total", "outstanding")]
    assert "Deposits" in str(t.iloc[1, 1]) and "Receipts" in str(t.iloc[2, 1]) and "Outstandings" in str(t.iloc[2, 8])
    for r in range(4, len(t)):
        y = str(t.iloc[r, 0])
        if not re.fullmatch(r"\d{4}-\d{2}", y):
            continue
        for (ins, m), x in zip(cols, t.iloc[r, 1:], strict=True):
            if num(x) is not None:
                exp[("hbs_small_savings", f"t109.{ins}.{m}.current", y if m == "receipts" else end_march(y))] = num(x)
    # T49
    liab, ass = hbs(49)[1], hbs(49)[2]
    lmap = {"capital": "liabilities.capital", "reserves & surplus": "liabilities.reserves_surplus",
            "deposits": "liabilities.deposits", "borrowings": "liabilities.borrowings",
            "other liabilities and provisions": "liabilities.other_liabilities_provisions"}
    amap = {"cash and balances with rbi": "assets.cash_balances_rbi",
            "balances with banks and money at call and short notice": "assets.balances_banks_call_money",
            "investments": "assets.investments", "loans and advances": "assets.loans_advances",
            "fixed assets": "assets.fixed_assets", "other assets": "assets.other_assets",
            "total liabilities/ assets": "total.total"}
    for tab, m, hdr in ((liab, lmap, 2), (ass, amap, 1)):
        codes = [m[norm(h)] for h in tab.iloc[hdr, 1:]]
        for r in range(hdr + 1, len(tab)):
            y = str(tab.iloc[r, 0])
            if not re.fullmatch(r"\d{4}-\d{2}", y):
                continue
            for c, x in zip(codes, tab.iloc[r, 1:], strict=True):
                if num(x) is not None:
                    exp[("hbs_scb_balance_sheet", f"t49.{c}.current", end_march(y))] = num(x)
    return exp


def test_hbs_census():
    exp = hbs_expected()
    got = {}
    for ds in ("hbs_saving", "hbs_gsec_ownership", "hbs_small_savings", "hbs_scb_balance_sheet"):
        for s, p, v in clean(ds).select("series_id", "period", "value").iter_rows():
            got[(ds, s, p)] = v
    compare("HBS T11/T12/T49/T107/T109", exp, got)
    t11 = clean("hbs_saving").filter(pl.col("table_id") == "HBS Table 11")
    for sid, by in t11.select("series_id", "base_year").unique().iter_rows():
        assert by == ("2011-12" if ".base2011." in sid else "2022-23"), (sid, by)


# ------------------------------------------------------------------------------------------------
# DEA PDFs (pypdf, own maps)
# ------------------------------------------------------------------------------------------------

HB1A_COLS = ["dated_securities", "tbills_91d", "tbills_182d", "tbills_364d", "market_loans", "tbills_14d",
             "special_securities_tb_conversion", "compensation_other_bonds", "securities_to_ifis",
             "securities_against_small_savings", "others", "internal_debt", "external_debt_hist",
             "external_debt_curr", "public_debt_hist", "public_debt_curr"]
HB1B_COLS = ["nssf", "state_provident_funds", "special_securities_in_lieu_of_subsidies",
             "special_deposits_nongovt_pf", "other_items", "other_accounts", "reserve_funds_interest",
             "reserve_funds_no_interest", "reserve_funds", "deposits_interest", "deposits_no_interest", "deposits",
             "other_liabilities", "public_debt_hist", "total_liabilities_hist", "total_liabilities_curr"]
HB5_COLS = ["commercial_banks", "cooperative_banks", "non_bank_pds", "insurance", "mutual_funds", "provident_funds",
            "pension_funds", "financial_institutions", "corporates", "fpi", "rbi", "others"]
MY_HOLDERS = {"commercial banks": "commercial_banks", "co-operative banks": "cooperative_banks",
              "non-bank pds": "non_bank_pds", "insurance companies": "insurance", "mutual funds": "mutual_funds",
              "provident funds": "provident_funds", "pension funds": "pension_funds", "pension fund": "pension_funds",
              "financial institutions": "financial_institutions", "corporates": "corporates",
              "foreign portfolio investors": "fpi", "fpis": "fpi", "rbi": "rbi", "others": "others",
              "total": "total"}
QMONTH = {"mar": "03-31", "jun": "06-30", "sep": "09-30", "sept": "09-30", "dec": "12-31"}


def sp_page(p: int) -> str:
    return pdf_pages(SP)[p - 1]


def _join_split_decimals(s: str) -> str:
    return re.sub(r"(\d)\.\s+(\d)", r"\1.\2", s)  # pypdf prints '7. 21' for 7.21


def dea_expected() -> dict:
    exp = {}
    for page, cols, pref in ((110, HB1A_COLS, "sp_hb1a"), (111, HB1B_COLS, "sp_hb1b")):
        for line in sp_page(page).splitlines():
            m = re.match(r"^(\d{4}-\d{2})\s+(.*)$", line.strip())
            if not m:
                continue
            vals = [float(x) for x in m.group(2).replace("*", " ").split()]
            assert len(vals) == 16, (page, line)
            for c, x in zip(cols, vals, strict=True):
                exp[("dea_central_debt", f"{pref}.{c}.current", end_march(m.group(1)))] = x
    # HB-5 quarterly
    seq = []
    for page in (119, 120):
        for line in sp_page(page).splitlines():
            m = re.match(r"^(\d{4})\s*\((End[- ]?\w+)\)\s+(.*)$", line.strip())
            if not m:
                continue
            q = m.group(2).lower().replace("end", "").strip("- ")
            toks = _join_split_decimals(m.group(3)).split()
            assert len(toks) == 12, line
            seq.append((int(m.group(1)), q, toks))
    # the second '2015 (End-March)' sits between Dec 2015 and Jun 2016: end-March 2016 (quarterly sequence)
    prev = None
    for y, q, toks in seq:
        mon = {"june": 6, "september": 9, "december": 12, "march": 3}[q]
        yy = y
        if prev is not None:
            want = (prev[0] + (prev[1] // 12), prev[1] % 12 + 3)
            if (yy, mon) != want:
                assert (y, mon) == (2015, 3) and want == (2016, 3), (y, q, prev)
                yy = 2016
        prev = (yy, mon)
        d = f"{yy}-{mon:02d}-{({3: 31, 6: 30, 9: 30, 12: 31})[mon]}"
        for c, t in zip(HB5_COLS, toks, strict=True):
            if t != "-":
                exp[("dea_gsec_ownership", f"sp_hb5.gsec_central.share.{c}", d)] = float(t)
    # T2.10 (page 35)
    t = sp_page(35).split("Table 2.10")[1]
    for line in t.splitlines():
        m = re.match(r"^([A-Za-z][A-Za-z .-]+?)\s+((?:[-\d.]+\s+){4}[-\d.]+)\s*$", line.strip())
        if not m or norm(m.group(1)) not in MY_HOLDERS:
            continue
        for y, tok in zip(range(2020, 2025), m.group(2).split(), strict=True):
            if tok != "-":
                exp[("dea_gsec_ownership", f"sp_t2_10.gsec_central.share.{MY_HOLDERS[norm(m.group(1))]}",
                     f"{y}-03-31")] = float(tok)
    # QR tables. QR23 T4.4 prints '11. Pension Fund' / '12. Others' swapped (verify-1): the swap is applied
    # here only after the printed pattern is confirmed from the page text ('Others' '-' for the four 2021
    # quarters, which is impossible for the residual holder; 'Pension Fund' filled throughout).
    qr23_swap = {"pension fund": "others", "others": "pension_funds"}
    specs = [(QR23, [18], "Table 4. 4", "qr2023_t4_4", "gsec_central", None),
             (QR24, [17, 18], "Table 4. 4", "qr2024_t4_4", "gsec_central", "Table 4.5"),
             (QR24, [18], "Table 4.5", "qr2024_t4_5", "tbills", None)]
    for key, pages, start, pref, ins, stop in specs:
        text = "\n".join(pdf_pages(key)[p - 1] for p in pages)
        text = text.split(start, 1)[1]
        if stop:
            text = text.split(stop, 1)[0]
        hdr = re.search(r"Category\s+(.*?)\n\s*(?:\n|1\.)", text, re.S).group(1)
        hdr = re.sub(r"\s+", " ", hdr).replace(". ", ".").replace(" .", ".")
        dates = []
        for mon, yr in re.findall(r"(Mar|Jun|Sept?|Dec)\.?\s*(\d{2})", hdr):
            dates.append(f"20{yr}-{QMONTH[mon.lower()]}")
        for line in text.splitlines():
            m = re.match(r"^(?:\d+\.\s+)?([A-Za-z][A-Za-z .-]+?)\s+((?:[-\d.]+\s+)*[-\d.]+)\s*$", line.strip())
            if m and not re.match(r"^\d+\.", line.strip()) and norm(m.group(1)) != "total":
                continue
            if not m:
                continue
            toks = m.group(2).split()
            assert len(toks) == len(dates), (pref, line, dates)
            holder = MY_HOLDERS[norm(m.group(1))]
            if pref == "qr2023_t4_4" and norm(m.group(1)) in qr23_swap:
                dashes = [t == "-" for t in toks]
                want = [False] * 9 if norm(m.group(1)) == "pension fund" else [True] * 4 + [False] * 5
                assert dashes == want, ("QR23 T4.4 printed pattern changed; re-examine the swap", line)
                holder = qr23_swap[norm(m.group(1))]
                printed = re.match(r"^(\d+\.\s+[A-Za-z][A-Za-z .-]*?)\s+[-\d]", line.strip()).group(1)
                QR23_PRINTED_AS[holder] = (MY_HOLDERS[norm(m.group(1))], re.sub(r"\s+", " ", printed))
            for d, tok in zip(dates, toks, strict=True):
                if tok != "-":
                    exp[("dea_gsec_ownership", f"{pref}.{ins}.share.{holder}", d)] = float(tok)
    assert set(QR23_PRINTED_AS) == {"others", "pension_funds"}
    return exp


QR23_PRINTED_AS: dict[str, tuple[str, str]] = {}  # true holder -> (printed holder code, printed row text)


def test_dea_census():
    exp = dea_expected()
    got = {}
    for ds in ("dea_central_debt", "dea_gsec_ownership"):
        for s, p, v in clean(ds).select("series_id", "period", "value").iter_rows():
            got[(ds, s, p)] = v
    compare("DEA HB-1A/1B, HB-5, T2.10, QR T4.4/T4.5", exp, got)


def test_hb5_equals_hbs_t107_end_march():
    """Cross-source check of the HB-5 column order (its header text is scrambled): HB-5 end-March 2022-2024
    must equal HBS T107 Central dated securities holder shares."""
    d = clean("dea_gsec_ownership").filter(pl.col("table_id") == "Status Paper Table HB-5")
    t = clean("hbs_gsec_ownership").filter(pl.col("series_id").str.starts_with("t107.gsec_central.share."))
    tv = {(s.split(".")[-1], p): v for s, p, v in t.select("series_id", "period", "value").iter_rows()}
    n = 0
    for s, p, v in d.select("series_id", "period", "value").iter_rows():
        k = (s.split(".")[-1], p)
        if k in tv:
            n += 1
            assert close(v, tv[k], 1e-9), (k, v, tv[k])
    assert n == 36


def test_qr2023_pension_others_labels_agree_with_status_paper():
    """QR Jan-Mar 2023 T4.4 must agree with the Status Paper 2023-24 T2.10 (same publisher, same concept,
    one decimal) at every common end-March date for pension funds and others. Every other holder agrees;
    these two rows are printed swapped in the QR PDF (its 'Pension Fund' row has values for 2021 quarters,
    when pension funds were not reported separately). Failed on the first-pass build; second pass (after the
    builder's swap) also checks QR 2024 T4.4 Mar.23 and HB-5 (two decimals) at all nine QR23 quarters, and that
    no DEA table carries pension-fund rows before March 2022."""
    df = clean("dea_gsec_ownership")

    def tab(tid):
        return {(c, p): v for c, p, v in df.filter(pl.col("table_id") == tid).select(
            "counterparty", "period", "value").iter_rows()}

    q = tab("QR Jan-Mar 2023 Table 4.4")
    for other_tid, n_min, n_po in (("Status Paper Table 2.10", 30, 5), ("QR Jan-Mar 2024 Table 4.4", 12, 2),
                                   ("Status Paper Table HB-5", 100, 14)):
        s = tab(other_tid)
        common = sorted(q.keys() & s.keys())
        po = [k for k in common if k[0] in ("pension_funds", "others")]
        bad = [(k, q[k], s[k]) for k in common if abs(q[k] - s[k]) >= 0.051]
        print(f"[spotcheck] QR23 T4.4 vs {other_tid}: {len(common)} common cells ({len(po)} pension/others), "
              f"{len(bad)} disagree")
        assert len(common) >= n_min and len(po) == n_po, (other_tid, len(common), len(po))
        assert not bad, f"QR 2023 T4.4 disagrees with {other_tid}: {bad}"
    pension_before_2022 = df.filter((pl.col("counterparty") == "pension_funds") & (pl.col("period") < "2022-03-31"))
    assert pension_before_2022.height == 0, pension_before_2022.select("table_id", "period", "value").to_dicts()
    # the printed-page values themselves (QR23 p.18 text, typed by the verifier): Mar.21 'Pension Fund' 7.3 is
    # Others; Mar.23 'Others' 4.0 is pension funds (T2.10 2023: Pension 4.0, Others 5.6)
    assert q[("others", "2021-03-31")] == 7.3 and q[("others", "2023-03-31")] == 5.6
    assert q[("pension_funds", "2022-03-31")] == 3.5 and q[("pension_funds", "2023-03-31")] == 4.0


def test_qr2023_swap_flags_and_provenance():
    """The 14 reassigned rows must be traceable back to the printed page: item_label = the printed row label,
    dim_other = printed_as=<printed holder>, and a provenance block of their own whose notes cite the misprint.
    No other DEA row carries a dim_other flag."""
    dea_expected()  # fills QR23_PRINTED_AS from the verifier's own parse of the page text
    df = clean("dea_gsec_ownership")
    flagged = df.filter(pl.col("dim_other").is_not_null())
    assert set(flagged["table_id"]) == {"QR Jan-Mar 2023 Table 4.4"} and flagged.height == 14
    for holder, (printed_code, printed_label) in QR23_PRINTED_AS.items():
        rows = flagged.filter(pl.col("counterparty") == holder)
        assert rows.height == (9 if holder == "others" else 5), (holder, rows.height)
        assert set(rows["dim_other"]) == {f"printed_as={printed_code}"}, (holder, set(rows["dim_other"]))
        assert set(rows["item_label"]) == {printed_label}, (holder, set(rows["item_label"]), printed_label)
        assert set(rows["series_id"]) == {f"qr2023_t4_4.gsec_central.share.{holder}"}
    unflagged = df.filter((pl.col("table_id") == "QR Jan-Mar 2023 Table 4.4") & pl.col("dim_other").is_null())
    assert not set(unflagged["counterparty"]) & {"others", "pension_funds"}
    prov = pl.read_parquet(CLEAN / "_provenance.parquet")
    pids = set(flagged["prov_id"])
    assert len(pids) == 1 and not pids & set(unflagged["prov_id"])
    p = prov.filter(pl.col("prov_id") == pids.pop()).row(0, named=True)
    assert p["status"] == "official" and "page 18" in p["locator"]
    assert "swapped" in p["notes"] and "Table 2.10" in p["notes"]
    assert "Table 4. 4" in pdf_pages(QR23)[17]


def test_second_pass_minor_fixes():
    """verify-3: HBS T12 base_year null before 2011-12; verify-5: FSF descriptions warn about non-additivity."""
    t12 = clean("hbs_saving").filter(pl.col("series_id").str.starts_with("t12."))
    by = dict(t12.group_by(pl.col("period") >= "2011-12").agg(pl.col("base_year").unique()).iter_rows())
    assert list(by[True]) == ["2011-12"] and list(by[False]) == [None], by
    import json
    desc = json.loads((CLEAN / "_datasets.json").read_text(encoding="utf-8"))
    for ds in ("fsf_balance_sheets", "fsf_fwtw", "fsf_instrument_sector"):
        d = desc[f"{UNIT}_{ds}"]
        text = d if isinstance(d, str) else d["description"]
        assert "additive" in text.lower() or "do not add" in text.lower(), (ds, text)


# ------------------------------------------------------------------------------------------------
# literal anchors typed by the verifier from the PDF page text / the workbook
# ------------------------------------------------------------------------------------------------

# (dataset, series_id, period, value, where printed)
HAND_ANCHORS = [
    ("hh_finsav_52ab", "t52a.nfa.current.fy", "2023-24", 1692414.2, "52(a) p.154 NFA 2023-24 Annual"),
    ("hh_finsav_52ab", "t52a.fa.current.fy", "2023-24", 3601838.9, "52(a) p.154 I. Financial Assets Annual"),
    ("hh_finsav_52ab", "t52a.fl.current.fy", "2023-24", 1909424.7, "52(a) p.154 II. Financial Liabilities Annual"),
    ("hh_finsav_52ab", "t52a.fl_fc_ofi_hfc.current.fq", "Q2 2023-24", -404294.0, "52(a) p.154 HFC loans Q2"),
    ("hh_finsav_52ab", "t52a.fa_deposits_nonbank_ofi_hfc.current.fy", "2023-24", -119045.2, "52(a) p.154 HFC dep"),
    ("hh_finsav_52ab", "t52a.fa_pct_gdp.n_a.fq", "Q4 2023-24", 16.2, "52(a) p.154 FA per cent of GDP Q4"),
    ("hh_finsav_52ab", "t52a.fa_investments_equity.current.fy", "2022-23", 4801.7, "52(a) p.153 equity Annual"),
    ("hh_finsav_52ab", "t52a.fl_gg.current.fq", "Q3 2024-25", 144.0, "52(a) p.155 General Government Q3"),
    ("hh_finsav_52ab", "t52a.fa_currency.current.fy", "2025-26", 413000.2, "52(a) p.156 Currency Annual"),
    ("hh_finsav_52ab", "t52b.fa.current", "2024-03-31", 41470111.9, "52(b) p.158 Financial Assets Mar-2024"),
    ("hh_finsav_52ab", "t52b.fl.current", "2024-03-31", 12130649.0, "52(b) p.158 Financial Liabilities Mar-2024"),
    ("hh_finsav_52ab", "t52b.fa_deposits_nonbank_ofi_hfc.current", "2023-09-30", 23939.1, "52(b) p.158 HFC Sep-23"),
    ("hh_finsav_52ab", "t52b.fl_pct_gdp.n_a", "2026-03-31", 45.9, "52(b) p.160 FL per cent of GDP Mar-2026"),
    ("hh_finsav_52ab", "t52b.fa_pension_funds.current", "2022-06-30", 744459.2, "52(b) p.157 Pension Jun-2022"),
    ("dea_central_debt", "sp_hb1a.dated_securities.current", "2024-03-31", 10265571, "SP p.90 HB-1A 2023-24 c2"),
    ("dea_central_debt", "sp_hb1a.market_loans.current", "2020-03-31", 6560225, "SP p.90 HB-1A 2019-20 c6 (*CMB)"),
    ("dea_central_debt", "sp_hb1a.tbills_14d.current", "2020-03-31", 154911, "SP p.90 HB-1A 2019-20 c7"),
    ("dea_central_debt", "sp_hb1a.securities_against_small_savings.current", "2024-03-31", 2731179, "SP p.90 c11"),
    ("dea_central_debt", "sp_hb1a.public_debt_curr.current", "2002-03-31", 1112958, "SP p.90 HB-1A 2001-02 c17"),
    ("dea_central_debt", "sp_hb1b.nssf.current", "2024-03-31", 416511, "SP p.91 HB-1B 2023-24 c2"),
    ("dea_central_debt", "sp_hb1b.total_liabilities_curr.current", "2024-03-31", 17207908, "SP p.91 c17"),
    ("dea_central_debt", "sp_hb1b.reserve_funds_interest.current", "2020-03-31", -13792, "SP p.91 2019-20 c8"),
    ("dea_gsec_ownership", "sp_hb5.gsec_central.share.provident_funds", "2014-06-30", 7.21, "SP p.99 HB-5 '7. 21'"),
    ("dea_gsec_ownership", "sp_hb5.gsec_central.share.mutual_funds", "2020-03-31", 1.43, "SP p.99 HB-5 '1. 43'"),
    ("dea_gsec_ownership", "sp_hb5.gsec_central.share.others", "2016-03-31", 5.72, "SP p.99 2nd '2015 (End-March)'"),
    ("dea_gsec_ownership", "sp_hb5.gsec_central.share.corporates", "2023-12-31", 1.33, "SP p.100 HB-5 '1. 33'"),
    ("dea_gsec_ownership", "sp_hb5.gsec_central.share.rbi", "2024-03-31", 12.31, "SP p.100 HB-5 Mar 2024"),
    ("dea_gsec_ownership", "sp_t2_10.gsec_central.share.commercial_banks", "2024-03-31", 37.7, "SP p.15 T2.10"),
    ("dea_gsec_ownership", "sp_t2_10.gsec_central.share.others", "2021-03-31", 7.3, "SP p.15 T2.10 Others 2021"),
    ("dea_gsec_ownership", "qr2024_t4_4.gsec_central.share.fpi", "2024-03-31", 2.3, "QR24 p.14 T4.4 FPIs Mar.24"),
    ("dea_gsec_ownership", "qr2024_t4_5.tbills.share.financial_institutions", "2024-03-31", 7.2, "QR24 p.14 T4.5"),
    ("dea_gsec_ownership", "qr2024_t4_5.tbills.share.provident_funds", "2023-06-30", 1.5, "QR24 p.14 T4.5 Jun.23"),
    ("dea_gsec_ownership", "qr2023_t4_4.gsec_central.share.rbi", "2022-12-31", 14.7, "QR23 p.14 T4.4 Dec.22"),
    ("dea_gsec_ownership", "qr2023_t4_4.gsec_central.share.commercial_banks", "2021-06-30", 36.0, "QR23 p.14 T4.4"),
    # second pass: the swapped rows, typed from QR23 p.18 (printed p.14) and cross-read on SP p.35 / QR24 p.17
    ("dea_gsec_ownership", "qr2023_t4_4.gsec_central.share.others", "2021-09-30", 8.8, "QR23 printed 'Pension Fund' Sep.21"),
    ("dea_gsec_ownership", "qr2023_t4_4.gsec_central.share.others", "2022-12-31", 5.5, "QR23 printed 'Pension Fund' Dec.22"),
    ("dea_gsec_ownership", "qr2023_t4_4.gsec_central.share.pension_funds", "2022-09-30", 3.8, "QR23 printed 'Others' Sept.22"),
    ("dea_gsec_ownership", "qr2023_t4_4.gsec_central.share.pension_funds", "2022-12-31", 3.9, "QR23 printed 'Others' Dec.22"),
    ("dea_gsec_ownership", "qr2023_t4_4.gsec_central.share.provident_funds", "2023-03-31", 4.7, "QR23 p.18 Mar.23"),
    ("dea_gsec_ownership", "sp_t2_10.gsec_central.share.pension_funds", "2023-03-31", 4.0, "SP p.35 T2.10 Pension 2023"),
    ("dea_gsec_ownership", "sp_t2_10.gsec_central.share.others", "2022-03-31", 4.5, "SP p.35 T2.10 Others 2022"),
    ("dea_gsec_ownership", "qr2024_t4_4.gsec_central.share.pension_funds", "2023-03-31", 4.0, "QR24 p.17 Mar.23"),
    ("dea_gsec_ownership", "qr2024_t4_4.gsec_central.share.pension_funds", "2023-06-30", 4.2, "QR24 p.17 Jun.23"),
    ("dea_gsec_ownership", "sp_hb5.gsec_central.share.pension_funds", "2023-03-31", 3.98, "SP HB-5 = T107"),
    # workbook / HTML anchors
    ("fsf_balance_sheets", "fsf.hh.assets.transaction.total.all.current", "2023-24", 3445382.5152310324,
     "FSF St 4 row 232 'Gross Financial Assets' col AC"),
    ("fsf_balance_sheets", "fsf.hh.liabilities.transaction.total.all.current", "2023-24", 1875522.2387270033,
     "FSF St 4 row 115 'Gross Financial Liabilities' col AC"),
    ("hbs_saving", "t11.gross_financial_saving_hh.base2022.current", "2023-24", 3575657, "HBS T11 1.4.1.1 col 6"),
    ("hbs_saving", "t12.assets.financial_assets.current", "2023-24", 3430640, "HBS T12 col 11 2023-24"),
    ("hbs_gsec_ownership", "t107.gsec_central.outstanding.current", "2024-03-31", 10740389, "HBS T107 (A) 2024"),
]


def test_hand_anchors():
    bad, n = [], 0
    for ds, sid, per, want, where in HAND_ANCHORS:
        d = clean(ds).filter((pl.col("series_id") == sid) & (pl.col("period") == per))
        n += 1
        if d.height != 1 or not close(d["value"][0], float(want), 1e-6):
            bad.append((sid, per, d["value"].to_list(), want, where))
    print(f"[spotcheck] hand anchors: compared {n}, mismatched {len(bad)}")
    assert not bad, bad


# ------------------------------------------------------------------------------------------------
# provenance and status
# ------------------------------------------------------------------------------------------------


def test_status_units_and_provenance_pages():
    prov = pl.read_parquet(CLEAN / "_provenance.parquet")
    assert set(prov["status"]) == {"official"}
    assert set(prov["conversion"]) == {"none"}
    # every PDF-derived provenance locator names a page that actually contains the table
    checks = {"Table HB-1A": (SP, "Table HB-1A"), "Table HB-1B": (SP, "Table HB-1B"),
              "Table HB-5": (SP, "Per cent of Total"), "Table 2.10": (SP, "Table 2.10"),
              "QR Jan-Mar 2023 Table 4.4": (QR23, "Table 4. 4"), "QR Jan-Mar 2024 Table 4.4": (QR24, "Commercial"),
              "QR Jan-Mar 2024 Table 4.5": (QR24, "Table 4.5"), "Table 52(a)": (T52A, "No. 52 (a)"),
              "Table 52(b)": (T52B, "No. 52 (b)")}
    n = 0
    for tid, loc in prov.select("table_id", "locator").iter_rows():
        for k, (key, needle) in checks.items():
            if tid.endswith(k):
                p = int(re.search(r"page (\d+)", loc).group(1))
                assert needle in pdf_pages(key)[p - 1], (tid, loc)
                n += 1
    assert n >= 20


def test_print_random_sample():
    """Random FSF sample printed for the notes (seeded), each re-read from the raw cell."""
    rng = random.Random(SEED)
    exp, _ = fsf_st_expected()
    keys = rng.sample(sorted(exp, key=str), 12)
    df = clean("fsf_balance_sheets")
    for k in keys:
        inst, side, meas, ins, cp, per = k
        d = df.filter((pl.col("institution") == inst) & (pl.col("side") == side)
                      & (pl.col("dim_other") == f"measure={meas}") & (pl.col("instrument") == ins)
                      & (pl.col("counterparty") == cp) & (pl.col("period") == per))
        print(f"[sample] {k} raw={exp[k]} clean={d['value'].to_list()}")
        assert d.height == 1 and close(d["value"][0], exp[k])
