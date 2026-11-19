"""Independent verification of the finsector_markets unit (Phase 1, verifier first pass, 2026-09-29).

This file does NOT import the unit's code (pipeline.ingest.finsector_markets). It re-reads the pinned
raw files directly with its own locators and label maps and compares them with
data/clean/finsector_markets/:

- XLSX (IRDAI Handbook 2024-25 zip, PFRDA A2/A5/M2/M4/M6, SEBI Handbook 2025-26 tables): openpyxl,
  cells located by the verifier's own header/label search (row labels, block headers, year rows).
- PDF (EPFO Annual Reports 2023-24 and 2024-25): pdfplumber text (the unit uses pypdf), pages found
  by the verifier's own anchor search in a page window, values matched by the verifier's own regexes.
  The rotated Appendix-5(i) page of AR 2024-25 comes out mirrored in pdfplumber; it is read by
  reversing the tokens. HAND_ANCHORS are literal numbers typed by hand from the PDF page text.

Method: a full census. Every clean row (11,258) is resolved to its raw cell or PDF number and compared
(tolerance 1e-6 relative, clean values are rounded to 6 decimals). A completeness count per table
checks the other direction (every published number in the ingested block has a clean row). Derived
rows (PFRDA M4 annual differences) are recomputed from the raw file. Semantic checks cover scale
(Rs lakh, Rs billion, lakh counts), period mapping (FY vs end-March date vs month-end) and a few
cross-table identities that would expose a mis-scaled or shifted table. A seeded random sample
(SEED) is printed for the verification notes.

Second pass (same day, after the builder's fixes): PFRDA Table M7 (new dataset pfrda_sg) is in the census
with its own locator (month label in row 2, measure caption in row 3, the row whose column A is 'Total');
the FY sums are recomputed from the raw monthly cells. The T69 opening SIP count is now a stock dated the
31 March before its FY, and the resolver maps it to the FY that starts the next day. Checks were added for
the EPFO past-accumulation fix (V1), the central lines of AR 2024-25 Appendix-5(i) (V11) and the other
provenance fixes (V4-V7, V9, V10).

Close-out pass (after the builder's EPFO/EPS provenance follow-up; no values changed): a third, independent
route to Appendix-5(i) (`app5i_positional`: pdfplumber word coordinates, columns anchored on the Total row)
places every central line by print position (incl. the 0.19 head-office line the second pass missed),
re-derives every number the new notes state, checks the quoted passages verbatim on the cited pages, and
re-resolves all 61 rows whose provenance was rewritten (seeded sample of 30 printed). NSDL/AMFI refusal is
checked against the registry file and the pins/sidecars. New findings V13 (EPS outgo split into pensions and
withdrawal benefits, Table 5) and V14 (App. 5(i) EPS/total contribution exclude the Government's share) are
pinned: raw facts as passing tests, the provenance fixes as strict xfails.

Final pass (after the builder's V13/V14 fixes): both provenance fixes were re-checked against the pinned PDFs and the
two strict xfails are now ordinary passing checks (strengthened: every number the new notes state is re-derived from
the raw pages). The new dataset epfo_eps_outgo (EPS outgo split into Pension Disbursed / Withdrawal Benefits / Total,
AR 2023-24 'EPS Payments' and AR 2024-25 'Table 5', 30 rows) is in the census through a fourth, independent route:
`eps_outgo_positional` (pdfplumber word coordinates; pages found by searching for the header line, columns anchored
on the header words' right edges, because the amounts are right-aligned). The unit reads pypdf text, and the
close-out `eps_table5` reads pdfplumber text lines; all three agree.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import io
import random
import re
import zipfile
from collections import Counter, defaultdict
from functools import cache
from pathlib import Path

import openpyxl
import pdfplumber
import polars as pl
import pytest
import yaml
from openpyxl.utils import column_index_from_string as ci
from openpyxl.utils import get_column_letter as gl

pytestmark = pytest.mark.quality

ROOT = Path(__file__).resolve().parents[2]
UNIT = "finsector_markets"
CLEAN = ROOT / "data" / "clean" / UNIT
PINS = ROOT / "data" / "raw_pins" / f"{UNIT}.yaml"
SEED = 20260929
DATASETS = ("irdai_summary", "irdai_life", "irdai_nonlife", "epfo_ar", "pfrda_nps", "sebi_primary",
            "sebi_bonds_equity", "sebi_foreign", "sebi_mf", "pfrda_sg", "epfo_eps_outgo")

# ------------------------------------------------------------------------------------------------
# generic helpers (verifier's own)
# ------------------------------------------------------------------------------------------------


def norm(s) -> str:
    """Whitespace-collapsed text, curly quotes straightened; case kept."""
    s = str(s).replace("’", "'").replace("‘", "'").replace("–", "-")
    return re.sub(r"\s+", " ", s).strip()


def num(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    if s in ("", "-", "NA", "N.A.", "na", "--"):
        return None
    if re.fullmatch(r"\(?-?\d+(\.\d+)?\)?", s):
        neg = s.startswith("(")
        x = float(s.strip("()"))
        return -x if neg else x
    return None


def fy_of(label) -> str | None:
    """'2023-24', '2020-21.', '2025-26$', '2019-20 ' -> '2023-24'; anything else -> None."""
    m = re.fullmatch(r"\s*(\d{4})\s*-\s*(\d{2})\s*[.$*]*\s*", str(label))  # '2020-21**' (T44 footnote)
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    assert (a + 1) % 100 == b, label
    return f"{a}-{b:02d}"


def fy_from_date(d: str) -> str:
    """'2024-03-31' -> '2023-24' (the FY that ends on that date)."""
    y = int(d[:4])
    assert d[5:] == "03-31", d
    return f"{y - 1}-{y % 100:02d}"


def month_end(y: int, m: int) -> str:
    nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
    return (nxt - dt.timedelta(days=1)).isoformat()


def close(a: float, b: float) -> bool:
    return abs(a - b) <= max(2e-6, 1e-9 * abs(b))


@cache
def pins() -> dict:
    return yaml.safe_load(PINS.read_text(encoding="utf-8"))["pins"]


@cache
def raw_path(source: str, name: str) -> Path:
    pin = pins()[f"{source}/{name}"]
    p = ROOT / pin["path"]
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    assert h == pin["sha256"], f"{p} hash differs from the pin"
    return p


@cache
def clean(ds: str) -> pl.DataFrame:
    return pl.read_parquet(CLEAN / f"{UNIT}_{ds}.parquet")


@cache
def irdai_wb(member: str):
    z = zipfile.ZipFile(raw_path("irdai_handbook_insurance", "irdai_handbook_2024_25.zip"))
    names = [n for n in z.namelist() if n.endswith("/" + member)]
    assert len(names) == 1, names
    return openpyxl.load_workbook(io.BytesIO(z.read(names[0])), data_only=True)


@cache
def xlsx(source: str, name: str):
    return openpyxl.load_workbook(raw_path(source, name), data_only=True)


def txt(ws, r, c) -> str:
    v = ws.cell(r, c).value
    return "" if v is None else norm(v)


# ------------------------------------------------------------------------------------------------
# IRDAI resolvers
# ------------------------------------------------------------------------------------------------

SUMMARY_SECTION = {  # item-code prefix -> the Summary section header it must sit under (verifier's map)
    "gdp_segment.": "SEGMENT WISE GROSS DIRECT PREMIUM",
    "net_retention.": "NET RETENTIONS",
    "incurred_claims_ratio.": "INCURRED CLAIMS RATIO",
    "nb_premium_channel.": "CHANNEL-WISE NEW BUSINESS - AMOUNT OF PREMIUM",
    "nb_lives_channel.": "CHANNEL WISE-NEW BUSINESS - NO. OF LIVES",
    "offices_region.": "REGION WISE DISTRIBUTION OF OFFICES",
    "aum.": "ASSETS UNDER MANAGEMENT",
}
SUMMARY_FACTOR = {"₹Crore": 1.0, "Nos.": 1.0, "Lakhs": 1e5, "Per cent": 1.0}


@cache
def summary_index(sheet: str):
    """{(section header, label): row} and {fy: col} for Summary sheet A/B/C."""
    ws = irdai_wb("Summary.xlsx")[sheet]
    years = {}
    for c in range(4, ws.max_column + 1):
        f = fy_of(ws.cell(2, c).value) if ws.cell(2, c).value is not None else None
        if f:
            years[f] = c
    idx, section = {}, ""
    for r in range(3, ws.max_row + 1):
        a = txt(ws, r, 1)
        if not a:
            continue
        if ws.cell(r, 3).value is None and all(ws.cell(r, c).value is None for c in years.values()):
            section = a
            continue
        idx.setdefault((section, a), r)
    return ws, idx, years


def res_summary(row: dict) -> float:
    sheet = row["table_id"][-1]
    ws, idx, years = summary_index(sheet)
    lab = norm(row["item_label"])
    code = row["item_code"]
    sec_need = next((v for k, v in SUMMARY_SECTION.items() if code.startswith(k)), None)
    cands = [(s, r) for (s, lbl), r in idx.items() if lbl == lab and (sec_need is None or s.upper().startswith(sec_need))]
    if sec_need is None:  # unique label outside the sub-sections
        cands = [(s, r) for s, r in cands if not any(s.upper().startswith(v) for v in SUMMARY_SECTION.values())] or cands
    assert len(cands) == 1, (sheet, lab, code, cands)
    r = cands[0][1]
    period = row["period"]
    fy = fy_from_date(period) if row["period_type"] == "date" else period
    v = num(ws.cell(r, years[fy]).value)
    return v * SUMMARY_FACTOR[txt(ws, r, 3)]


def block_cols(ws, hdr_row: int, year_row: int, name: str, n: int) -> dict[str, int]:
    hits = [c for c in range(2, ws.max_column + 1) if txt(ws, hdr_row, c).upper() == name.upper()]
    assert len(hits) == 1, (ws.title, name, hits)
    c0 = hits[0]
    return {fy_of(ws.cell(year_row, c0 + i).value): c0 + i for i in range(n)}


@cache
def label_rows(member: str, sheet: str, first: int = 5, col: int = 1) -> dict[str, list[int]]:
    ws = irdai_wb(member)[sheet]
    out = defaultdict(list)
    for r in range(first, ws.max_row + 1):
        a = txt(ws, r, col)
        if a:
            out[a].append(r)
    return out


LIFE_BLOCK = {"lic": "LIC", "insurers_life": "TOTAL"}
T51_BLOCK = {"general_public": "Public Sector Insurers Total", "general_private": "Private Sector Insurers Total",
             "general_specialized": "Specialized Insurers Total", "health_standalone": "Stand-alone Health Insurers Total"}
DUP_OCCURRENCE = {  # (sheet, item_code) -> which occurrence of a repeated label (0-based)
    ("51", "provision_others"): 0, ("51", "other_expenses_others"): 1,
}


def res_accounts(row: dict, member: str, sheet: str, blocks: dict, scale: float) -> float:
    ws = irdai_wb(member)[sheet]
    cols = block_cols(ws, 3, 4, blocks[row["institution"]], 10)
    rows = label_rows(member, sheet)[norm(row["item_label"])]
    k = DUP_OCCURRENCE.get((sheet, row["item_code"]), 0) if len(rows) > 1 else 0
    assert len(rows) == 1 or (sheet, row["item_code"]) in DUP_OCCURRENCE, (sheet, row["item_label"], rows)
    return num(ws.cell(rows[k], cols[row["period"]]).value) * scale


T2_LABEL = {"lic": "Life Insurance Corporation of India", "life_private": "Private Sector Total",
            "insurers_life": "Grand Total"}
GROUP_LABEL = {**T51_BLOCK, "insurers_general_direct": "Grand Total"}


def group_row(member: str, sheet: str, label: str, first: int) -> int:
    rows = label_rows(member, sheet, first, 2)[label]
    assert len(rows) == 1, (sheet, label, rows)
    return rows[0]


def res_t2(row):
    ws = irdai_wb("Part I.xlsx")["2"]
    r = group_row("Part I.xlsx", "2", T2_LABEL[row["institution"]], 4)
    years = {fy_of(ws.cell(3, c).value): c for c in range(3, 13)}
    return num(ws.cell(r, years[row["period"]]).value)


T20_FUND = {"life_fund": "Life Fund", "pension_annuity_group_fund": "Pension & General Annuity Fund",
            "ulip_fund": "ULIP Funds"}


@cache
def t20_index():
    ws = irdai_wb("Part I.xlsx")["20"]
    idx, fund = {}, None
    for r in range(5, 33):
        a, b = txt(ws, r, 1), txt(ws, r, 2)
        if a.upper().startswith("GRAND TOTAL"):
            idx[("all_funds", "GRAND TOTAL")] = r
            continue
        if a:
            fund = a
        if b:
            idx[(fund, b)] = r
    return ws, idx


def res_t20(row):
    ws, idx = t20_index()
    fund = row["product"]
    cat_label = norm(row["item_label"].split(": ", 1)[1])
    key = ("all_funds", "GRAND TOTAL") if fund == "all_funds" else (T20_FUND[fund], cat_label)
    r = idx[key]
    year = int(row["period"][:4])
    cols = {int(ws.cell(4, c).value): c for c in range(3, 13)}
    return num(ws.cell(r, cols[year]).value)


def res_t40(row):
    ws = irdai_wb("Part II.xlsx")["40"]
    r = group_row("Part II.xlsx", "40", GROUP_LABEL[row["institution"]], 4)
    years = {fy_of(ws.cell(3, c).value): c for c in range(3, 13)}
    return num(ws.cell(r, years[row["period"]]).value)


T41_SEG = {"fire": "Fire", "marine": "Marine", "motor": "Motor", "health_pa_travel": "Health + PA+ TRAVEL",
           "others": "Others", "total": "Total"}
T44_SEG = {"fire": "FIRE INSURANCE", "marine": "MARINE INSURANCE", "motor": "MOTOR INSURANCE",
           "health": "HEALTH INSURANCE", "others": "OTHER SEGMENTS", "total": "ALL SEGMENTS"}


def res_t41(row):
    ws = irdai_wb("Part II.xlsx")["41"]
    cols = block_cols(ws, 3, 4, T41_SEG[row["product"]], 10)
    r = group_row("Part II.xlsx", "41", GROUP_LABEL[row["institution"]], 5)
    return num(ws.cell(r, cols[row["period"]]).value)


def res_t44(row):
    ws = irdai_wb("Part II.xlsx")["44"]
    seg = [c for c in range(3, ws.max_column + 1) if txt(ws, 2, c).upper() == T44_SEG[row["product"]]]
    assert len(seg) == 1
    c0 = seg[0]
    needle = "NET PREMIUM EARNED" if row["item_code"] == "net_premium_earned" else "CLAIMS INCURRED (NET)"
    # the measure header sits in row 3 somewhere inside this segment block (before the next segment)
    mc = [c for c in range(c0, c0 + 33) if needle in txt(ws, 3, c).upper()]
    assert len(mc) == 1 and "CRORE" in txt(ws, 3, mc[0]).upper(), (row["product"], needle, mc)
    years = {fy_of(ws.cell(4, c).value): c for c in range(mc[0], mc[0] + 11)}
    r = group_row("Part II.xlsx", "44", GROUP_LABEL[row["institution"]], 5)
    return num(ws.cell(r, years[row["period"]]).value)


def res_t46(row):
    ws = irdai_wb("Part II.xlsx")["46"]
    cat = norm(row["item_label"].split(": ", 1)[1])
    rows = [r for r in range(4, ws.max_row + 1) if txt(ws, r, 1) == cat]
    assert len(rows) == 1 and txt(ws, rows[0], 2) == "Amount (₹Crore)", (cat, rows)
    cols = {int(ws.cell(3, c).value): c for c in range(3, 13)}
    return num(ws.cell(rows[0], cols[int(row["period"][:4])]).value)


def res_irdai(row: dict) -> float:
    t = row["table_id"]
    if t.startswith("Summary"):
        return res_summary(row)
    return {
        "Table 2": res_t2,
        "Table 20": res_t20,
        "Table 24": lambda r: res_accounts(r, "Part I.xlsx", "24", LIFE_BLOCK, 0.01),
        "Table 25": lambda r: res_accounts(r, "Part I.xlsx", "25", LIFE_BLOCK, 0.01),
        "Table 40": res_t40,
        "Table 41": res_t41,
        "Table 44": res_t44,
        "Table 46": res_t46,
        "Table 51": lambda r: res_accounts(r, "Part II.xlsx", "51", T51_BLOCK, 1.0),
    }[t](row)


# ------------------------------------------------------------------------------------------------
# EPFO (pdfplumber)
# ------------------------------------------------------------------------------------------------

EPFO_REPORTS = {  # vintage in the clean data -> (pinned file, report FY, page windows to search)
    "2024-12": ("epfo_annual_report_2023_24.pdf", "2023-24", list(range(80, 101)) + list(range(230, 245))),
    "2026-02": ("epfo_annual_report_2024_25.pdf", "2024-25", list(range(74, 95)) + list(range(232, 246))),
}
AMT = r"(\d{1,3}(?:,\d{2})*,\d{3}\.\d{2}|\d{1,3}\.\d{2})"


def amt(s: str) -> float:
    return float(s.replace(",", "").replace("*", ""))


@cache
def epfo_pages(vintage: str) -> dict[int, str]:
    name, _, window = EPFO_REPORTS[vintage]
    out = {}
    with pdfplumber.open(raw_path("epfo_annual_report_accounts", name)) as pdf:
        for p in window:
            out[p] = pdf.pages[p - 1].extract_text() or ""
    return out


def epfo_page(vintage: str, anchor: str) -> tuple[int, str]:
    hits = [(p, t) for p, t in epfo_pages(vintage).items() if anchor in t]
    assert len(hits) >= 1, (vintage, anchor)
    return hits[0]


def one(pattern: str, text: str) -> re.Match:
    ms = list(re.finditer(pattern, text, flags=re.M))
    assert len(ms) == 1, (pattern, len(ms))
    return ms[0]


@cache
def epfo_values(vintage: str) -> dict[tuple[str, str], float]:
    """{(series_id, period): value} parsed by the verifier from the PDF text."""
    _, rfy, _ = EPFO_REPORTS[vintage]
    end_y = int(rfy[:4]) + 1
    out: dict[tuple[str, str], float] = {}
    # para 5.4
    _, t = epfo_page(vintage, "Contributions Received from Un-exempted Establishments")
    for code, pat in (("epf_contribution", r"Employees. Provident Funds Scheme " + AMT),
                      ("eps_contribution_employer", r"a\) Employers. Share " + AMT),
                      ("eps_contribution_government", r"b\) Government.s Share " + AMT),
                      ("eps_contribution_total", r"Total: " + AMT),
                      ("edli_contribution", r"Insurance Scheme:\s*\nEmployers. Share " + AMT)):
        out[(f"para54.{code}.current", rfy)] = amt(one(pat, t).group(1))
    # five-year tables
    if vintage == "2024-12":
        _, t = epfo_page(vintage, "PROVIDENT FUND CONTRIBUTIONS RECEIVED")
        pf = t[t.index("PROVIDENT FUND CONTRIBUTIONS RECEIVED"): t.index("Pension Fund")]
        for y, v in re.findall(r"^(\d{4}-\d{2})\*? " + AMT + r" -?\d+\.\d{2}$", pf, flags=re.M):
            out[("fiveyear.epf_contribution.current", y)] = amt(v)
        eps = t[t.index("5.8"):]
        for y, e, g in re.findall(r"^(\d{4}-\d{2})\*? " + AMT + " " + AMT + r" -?\d+\.\d{2}$", eps, flags=re.M):
            out[("fiveyear.eps_contribution_employer.current", y)] = amt(e)
            out[("fiveyear.eps_contribution_government.current", y)] = amt(g)
    else:
        _, t = epfo_page(vintage, "CONTRIBUTION AND PAYMENT OF ALL THREE SCHEMES (UNEXEMPTED)")
        codes = ("epf_contribution", "epf_payment", "eps_contribution_employer", "eps_payment", "edli_contribution",
                 "edli_payment", "total_contribution", "total_payment")
        got = re.findall(r"^(\d{4}-\d{2})\*? " + " ".join([AMT] * 8) + r" -?\d+\.\d{2}% -?\d+\.\d{2}%$", t, flags=re.M)
        assert len(got) == 5
        for g in got:
            for code, v in zip(codes, g[1:], strict=True):
                out[(f"fiveyear.{code}.current", g[0])] = amt(v)
    # Appendix-5(i) total row
    app_codes = ("epf_contribution", "epf_payment", "eps_contribution", "eps_payment", "edli_contribution",
                 "edli_payment", "total_contribution", "total_payment")
    if vintage == "2024-12":
        _, t = epfo_page(vintage, "APPENDIX-5(i)")
        m = one(r"^Total " + " ".join([AMT] * 8) + r"$", t)
        vals = [amt(x) for x in m.groups()]
    else:  # rotated page: pdfplumber returns each token mirrored, bottom-up
        _, t = epfo_page(vintage, ")i(5-XIDNEPPA")
        lines = [ln.strip() for ln in t.splitlines()]
        k = [i for i, ln in enumerate(lines) if ln == "latoT" and i >= 8
             and all(re.fullmatch(AMT, lines[j][::-1]) for j in range(i - 8, i))]
        assert len(k) == 1, k
        rev = [amt(lines[j][::-1]) for j in range(k[0] - 8, k[0])]
        # mirrored order: total pay, total contr, EDLI pay, EDLI contr, EPS pay, EPS contr, EPF pay, EPF contr
        vals = rev[::-1]
    for code, v in zip(app_codes, vals, strict=True):
        out[(f"app5i.{code}.current", rfy)] = v
    # investments by scheme
    p0, _ = epfo_page(vintage, "Corpus and Category wise breakup of Investments")
    pages = epfo_pages(vintage)
    t = "\n".join(pages[p] for p in sorted(pages) if p0 <= p <= p0 + 8)
    t = t[t.index("Corpus and Category wise breakup of Investments"):]
    heads = [("epf", r"a\) Employees. Provident Fund"), ("eps", r"b\) Employees. Pension Fund"),
             ("edli", r"c\) Employees. Deposit Linked Insurance Fund"), ("staff_pf", r"d\) Staff Provident Fund"),
             ("staff_pension_gratuity", r"e\) Staff Pension and Gratuity")]
    pos = [(one(p, t).start(), s) for s, p in heads]
    cats = (("central_govt_securities", r"Central Govt\. Securities \(CTG\)"),
            ("state_development_loans", r"State Development Loan \(SDL\)"),
            ("state_guaranteed_securities", r"State Guaranteed Securities \(STG\)"),
            ("special_deposit_scheme", r"Special Deposit Scheme \(SDS\)"),
            ("public_account_central_govt", r"Public Account with Central Govt\."),
            ("corporate_bonds_psu", r"Corporate Bonds - PSU/PSFIs"),
            ("corporate_bonds_private", r"Corporate Bonds -Private Sector \(PVT\)"),
            ("etf_at_cost", r"ETF\(at cost Price\)"), ("treps_lmf", r"TREPS/LMF in hand"), ("invits", r"Invits"))
    for i, (start, s) in enumerate(pos):
        block = t[start: pos[i + 1][0] if i + 1 < len(pos) else len(t)]
        block = block[: re.search(r"^TOTAL " + AMT + r" 100\.00%$", block, flags=re.M).end()]
        for d, m_, y, v in re.findall(r"Total Investments as on (\d{2})\.(\d{2})\.(\d{4}) " + AMT, block):
            out[(f"invest.{s}.total.current", f"{y}-{m_}-{d}")] = amt(v)
        m = one(r"Net addition in Investments at Face value during the year (\d{4}-\d{2}) " + AMT, block)
        out[(f"invest.{s}.net_addition.current", m.group(1))] = amt(m.group(2))
        for code, lab in cats:
            ms = re.findall(r"^\d+\.? ?" + lab + r" (" + AMT[1:-1] + r"|-) \d+\.\d{2}%$", block, flags=re.M)
            if not ms:
                continue
            assert len(ms) == 1
            out[(f"invest.{s}.{code}.current", f"{end_y}-03-31")] = 0.0 if ms[0] == "-" else amt(ms[0])
        m = one(r"^TOTAL " + AMT + r" 100\.00%$", block)
        out[(f"invest.{s}.category_total.current", f"{end_y}-03-31")] = amt(m.group(1))
    # exempted establishments (AR 2023-24 only; the table runs over two pages)
    if vintage == "2024-12":
        p, _ = epfo_page(vintage, "INVESTMENTS MADE BY EXEMPTED ESTABLISHMENTS DURING 2023-24")
        t = pages[p] + "\n" + pages[p + 1]
        for code, lab in (("special_deposit_account", "Special Deposit Account"),
                          ("govt_guaranteed_securities", r"Govt\. Guaranteed Securities"), ("others", "Others"),
                          ("total_gross", "TOTAL GROSS INVESTMENT"), ("redemption", "LESS: Redemption"),
                          ("total_net", "TOTAL NET INVESTMENT")):
            out[(f"exempted.{code}.current", rfy)] = amt(one(r"^" + lab + " " + AMT + "$", t).group(1))
    # Appendix-5(vii) interest rates (skip compound entries: '+0.5% bonus', '12%(April..')
    _, t = epfo_page(vintage, "Rate of Interest on EPF balances")
    for m in re.finditer(r"(\d{4})-(\d{2}) (\d+(?:\.\d+)?)%", t):
        nxt = t[m.end(): m.end() + 1]
        if nxt in ("+", "("):
            continue
        out[("app5vii.epf_interest_rate", f"{m.group(1)}-{m.group(2)}")] = float(m.group(3))
    return out


def res_epfo(row: dict) -> float:
    return epfo_values(row["vintage"])[(row["series_id"], row["period"])]


# literal numbers typed by hand from the PDF page text (verifier read pages 84-99, 235, 241 of AR 2023-24
# and 78, 85-91, 236, 242 of AR 2024-25)
HAND_ANCHORS = [
    ("2024-12", "para54.epf_contribution.current", "2023-24", 226198.57),
    ("2024-12", "para54.eps_contribution_employer.current", "2023-24", 62423.93),
    ("2024-12", "para54.eps_contribution_government.current", "2023-24", 9356.48),
    ("2024-12", "para54.eps_contribution_total.current", "2023-24", 71780.41),
    ("2024-12", "para54.edli_contribution.current", "2023-24", 3358.10),
    ("2024-12", "fiveyear.epf_contribution.current", "2022-23", 212317.01),
    ("2024-12", "fiveyear.epf_contribution.current", "2019-20", 124365.85),
    ("2024-12", "fiveyear.eps_contribution_employer.current", "2020-21", 44009.53),
    ("2024-12", "fiveyear.eps_contribution_government.current", "2021-22", 7806.20),
    ("2024-12", "app5i.epf_payment.current", "2023-24", 118690.66),
    ("2024-12", "app5i.eps_payment.current", "2023-24", 23410.17),
    ("2024-12", "app5i.total_contribution.current", "2023-24", 291980.60),
    ("2024-12", "app5i.total_payment.current", "2023-24", 144152.67),
    ("2024-12", "invest.epf.total.current", "2023-03-31", 1304264.41),
    ("2024-12", "invest.epf.total.current", "2024-03-31", 1529368.04),
    ("2024-12", "invest.epf.net_addition.current", "2023-24", 225103.63),
    ("2024-12", "invest.epf.state_development_loans.current", "2024-03-31", 703691.38),
    ("2024-12", "invest.eps.public_account_central_govt.current", "2024-03-31", 226530.85),
    ("2024-12", "invest.edli.etf_at_cost.current", "2024-03-31", 3699.45),
    ("2024-12", "invest.staff_pf.corporate_bonds_psu.current", "2024-03-31", 546.81),
    ("2024-12", "invest.staff_pension_gratuity.treps_lmf.current", "2024-03-31", 69.82),
    ("2024-12", "exempted.total_gross.current", "2023-24", 456848.78),
    ("2024-12", "exempted.redemption.current", "2023-24", 24935.40),
    ("2024-12", "exempted.total_net.current", "2023-24", 431913.38),
    ("2024-12", "app5vii.epf_interest_rate", "1984-85", 9.90),
    ("2024-12", "app5vii.epf_interest_rate", "2023-24", 8.25),
    ("2026-02", "para54.epf_contribution.current", "2024-25", 258132.93),
    ("2026-02", "para54.eps_contribution_government.current", "2024-25", 10049.70),
    ("2026-02", "fiveyear.epf_contribution.current", "2023-24", 233489.80),
    ("2026-02", "fiveyear.edli_payment.current", "2020-21", 854.91),
    ("2026-02", "invest.epf.total.current", "2025-03-31", 1764126.30),
    ("2026-02", "invest.eps.invits.current", "2025-03-31", 2054.63),
    ("2026-02", "invest.edli.treps_lmf.current", "2025-03-31", 107.23),
    ("2026-02", "app5i.total_payment.current", "2024-25", 175909.82),
    ("2026-02", "app5i.epf_contribution.current", "2024-25", 258132.93),
    ("2026-02", "app5vii.epf_interest_rate", "2024-25", 8.25),
]

# ------------------------------------------------------------------------------------------------
# PFRDA
# ------------------------------------------------------------------------------------------------

PF_FILES = {"Table A2": "A2_sector-wise_asset_under_management.xlsx", "Table A5": "A5_sector-wise_contribution_in_tier.xlsx",
            "Table M2": "M2_sector_wise_asset_under_management.xlsx", "Table M4": "M4_sector_wise_nps_contribution.xlsx",
            "Table M6": "M6_asset_class_wise_classification.xlsx"}
PF_SECTOR = {"nps_apy": {"APY"}, "nps_all_citizen": {"ALL CITIZEN"}, "nps_central_govt": {"CG"},
             "nps_corporate": {"CORPORATE"}, "nps_nps_lite": {"NPS LITE"}, "nps_nps_vatsalya": {"NPS VATSALYA", "NPS VATSLYA"},
             "nps_state_govt": {"SG"}, "nps_msf": {"MSF"}, "nps_msf_tier1": {"MSF TIER-I"}, "nps_msf_tier2": {"MSF TIER-II"},
             "nps_tier2_tax_saver": {"TTS"}, "nps_tier2": {"TIER-II"}}
PF_CLASS = {"total": "AUM", "corporate_bonds": "CORPORATE BOND", "equity": "EQUITY", "gsec": "G-SEC",
            "cash_net_current_assets": "NCA", "reit_invit": "REIT & INVIT", "short_term": "SHORT TERM INVESTMENTS"}
MON = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


@cache
def pf_index(table: str):
    ws = xlsx("pfrda_nps_statistics", PF_FILES[table]).worksheets[0]
    cols = {txt(ws, 2, c).upper(): c for c in range(2, ws.max_column + 1) if txt(ws, 2, c)}
    rows = {}
    for r in range(3, ws.max_row + 1):
        a = txt(ws, r, 1)
        m = re.fullmatch(r"([A-Za-z]{3})-(\d{4})", a)
        if m:
            rows[month_end(int(m.group(2)), MON[m.group(1).upper()])] = r
        elif fy_of(a):
            rows[fy_of(a)] = r
    return ws, cols, rows


def pf_cell(table: str, period: str, header: set[str] | str) -> float | None:
    ws, cols, rows = pf_index(table)
    hs = {header} if isinstance(header, str) else header
    c = [cols[h] for h in hs if h in cols]
    assert len(c) == 1, (table, hs)
    return num(ws.cell(rows[period], c[0]).value)


def res_pfrda(row: dict) -> float:
    t = row["table_id"]
    if t == "Table M4 (derived)":
        y = int(row["period"][:4])
        h = PF_SECTOR[row["institution"]]
        return pf_cell("Table M4", f"{y + 1}-03-31", h) - pf_cell("Table M4", f"{y}-03-31", h)
    if t == "Table M6":
        return pf_cell(t, row["period"], PF_CLASS[row["instrument"]])
    return pf_cell(t, row["period"], PF_SECTOR[row["institution"]])


# ------------------------------------------------------------------------------------------------
# SEBI
# ------------------------------------------------------------------------------------------------

SEBI_FILE = {"1": "hbs2526_t1_a.xlsx", "7": "hbs2526_t7_a.xlsx", "8": "hbs2526_t8_a.xlsx", "11": "hbs2526_t11_a.xlsx",
             "13": "hbs2526_t13_a.xlsx", "14": "hbs2526_t14_a.xlsx", "23": "hbs2526_t23_a.xlsx",
             "58": "hbs2526_t58_a.xlsx", "59": "hbs2526_t59_a.xlsx", "60": "hbs2526_t60_a.xlsx",
             "62": "hbs2526_t62_a.xlsx", "63": "hbs2526_t63_a.xlsx", "64": "hbs2526_t64_a.xlsx",
             "69": "hbs2526_t69_a.xlsx", "70": "hbs2526_t70_a.xlsx", "72": "hbs2526_t72_m.xlsx"}


def pairs(cols: str, names: list[str]) -> dict[str, str]:
    """B..: consecutive (issues, amount) column pairs."""
    out, c = {}, ci(cols)
    for n in names:
        out[f"{n}_issues"] = gl(c)
        out[f"{n}_amount"] = gl(c + 1)
        c += 2
    return out


SEBI_COL = {  # verifier's map: table -> item_code (+dims) -> column letter
    "1": pairs("B", ["total", "ipo_mainboard", "ipo_sme", "ipo_total", "fpo", "rights"]),
    "7": {"issues": "B", "amount": "C"},
    "8": pairs("B", ["bse_only", "nse_only", "both", "total"]),
    "13": pairs("B", ["reit_listed", "invit_public", "invit_private", "total"]),
    "14": pairs("B", ["equity_public", "equity_qip_pref", "debt_public", "debt_private_placement", "reit_invit", "total"]),
    "11": {"issues": "B", ("fc", "listing=listed"): "C", ("fc", "listing=unlisted"): "D", ("fc", "listing=all"): "E",
           ("nfc", "listing=listed"): "F", ("nfc", "listing=unlisted"): "G", ("nfc", "listing=all"): "H",
           ("all_corporations", "listing=all"): "I"},
    "23": {"exchange=bse": "C", "exchange=nse": "G", "exchange=msei": "K"},
    "58": {"fdi_gross_inflows": "B", "fdi_repatriation": "D", "fdi_direct_investment_to_india": "F", "fdi_by_india": "H",
           "fdi_net": "J", "portfolio_net": "L", "total_foreign_investment_net": "N"},
    "59": {("gross_purchases", "INR_crore"): "B", ("gross_sales", "INR_crore"): "C",
           ("net_investment", "INR_crore"): "D", ("net_investment", "USD_million"): "E"},
    "60": {"equity": "B", "debt_general": "C", "debt_vrr": "D", "debt_far": "E", "hybrid": "F", "aif_mf": "G", "total": "H"},
    "63": {"category_i": "B", "category_ii": "G", "category_iii": "L"},
    "64": {("gross_mobilisation", "mf_private"): "B", ("gross_mobilisation", "mf_public"): "C",
           ("gross_mobilisation", "mf_all"): "D", ("redemption", "mf_private"): "E", ("redemption", "mf_public"): "F",
           ("redemption", "mf_all"): "G", ("net_inflow", "mf_private"): "H", ("net_inflow", "mf_public"): "I",
           ("net_inflow", "mf_all"): "J", ("assets_end_of_period", "mf_all"): "K"},
    "70": {"equity": "B", "debt": "E", "total": "H"},
    "72": {"all_holders": "B", "corporates": "C", "hnis": "D", "retail": "E", "banks": "F"},
}
T62_LABEL = {"fpi_fii_sa": "FPI / FII/SA", "insurance_companies": "Insurance Company", "mutual_funds": "Mutual Funds",
             "fdi_investments": "FDI Investments", "foreign_depositories": "Foreign Depository", "banks": "Banks",
             "financial_institutions": "Financial Institutions", "local_pension_funds": "Local Pension Funds",
             "fvci": "Foreign Venture Capital Investment", "corporates": "Corporates",
             "pms": "Portfolio Management Services", "nris": "NRIs", "gdrs": "Global Depository Receipts",
             "ocbs": "OCBs", "others": "Others", "total": "Total"}
T63_INSTR = ["equity", "debt", "debt_vrr", "hybrid", "total"]
T63_HDR = ["Equity", "Debt", "Debt-VRR", "Hybrid", "Total"]


@cache
def sebi_ws(tnum: str):
    return xlsx("sebi_handbook_statistics", SEBI_FILE[tnum]).worksheets[0]


@cache
def sebi_rows(tnum: str) -> dict[str, int]:
    ws = sebi_ws(tnum)
    out = {}
    for r in range(3, ws.max_row + 1):
        f = fy_of(ws.cell(r, 1).value) if ws.cell(r, 1).value is not None else None
        if f:
            assert f not in out, (tnum, f)
            out[f] = r
    return out


def sebi_col(tnum: str, row: dict) -> str:
    m = SEBI_COL.get(tnum, {})
    code = row["item_code"]
    if tnum in ("1", "7", "8", "13", "14"):
        return m[code]
    if tnum == "11":
        return m["issues"] if code == "issuers" else m[(row["institution"], row["dim_other"])]
    if tnum == "23":
        return m[row["dim_other"]]
    if tnum == "58":
        c = m[code]
        return c if row["unit"] == "INR_crore" else gl(ci(c) + 1)
    if tnum == "59":
        return m[(code, row["unit"])]
    if tnum == "60":
        return m[row["instrument"]]
    if tnum == "62":
        ws = sebi_ws("62")
        hits = [c for c in range(2, ws.max_column + 1) if txt(ws, 3, c) == T62_LABEL[row["counterparty"]]]
        assert len(hits) == 1, row["counterparty"]
        assert txt(ws, 4, hits[0]) == "No." and txt(ws, 4, hits[0] + 1) == "Amt"
        return gl(hits[0] if code == "clients" else hits[0] + 1)
    if tnum == "63":
        cat = row["dim_other"].split("=")[1]
        c = ci(m[cat]) + T63_INSTR.index(row["instrument"])
        assert txt(sebi_ws("63"), 3, c) == T63_HDR[T63_INSTR.index(row["instrument"])]
        return gl(c)
    if tnum == "64":
        return m[(code, row["institution"])]
    if tnum == "70":
        return gl(ci(m[row["instrument"]]) + ["gross_purchase", "gross_sales", "net_purchase"].index(code))
    raise KeyError(tnum)


def res_sebi(row: dict) -> float:
    tnum = row["table_id"].split()[-1]
    if tnum == "69":
        return res_t69(row)
    if tnum == "72":
        return res_t72(row)
    ws = sebi_ws(tnum)
    fy = fy_from_date(row["period"]) if row["period_type"] == "date" else row["period"]
    v = num(ws[f"{sebi_col(tnum, row)}{sebi_rows(tnum)[fy]}"].value)
    if tnum == "58" and row["unit"] == "INR_crore":
        v *= 100.0  # Rs billion -> Rs crore
    return v


T69_HDR = {"sips_existing_beginning": "Existing at the beginning", "sips_registered": "Registered during",
           "sips_matured": "Matured during", "sips_terminated": "Terminated prematurely",
           "sips_closing": "Closing no. of SIPs", "sip_aum_end": "AUM at the end"}


def res_t69(row: dict) -> float:
    ws = sebi_ws("69")
    fy = fy_from_date(row["period"]) if row["period_type"] == "date" else row["period"]
    if row["item_code"] == "sips_existing_beginning":
        # opening stock dated D = 31 March: it is printed in the block of the FY that starts the day after D
        assert row["period_type"] == "date" and row["stock_flow"] == "stock", row
        y = int(row["period"][:4])
        fy = f"{y}-{(y + 1) % 100:02d}"
    starts = [c for c in range(1, ws.max_column + 1) if ws.cell(2, c).value is not None and fy_of(ws.cell(2, c).value) == fy]
    assert len(starts) == 1
    c0 = starts[0]
    hits = [c for c in range(c0, c0 + 8) if T69_HDR[row["item_code"]].lower() in txt(ws, 3, c).lower()]
    assert len(hits) == 1, (fy, row["item_code"])
    total = [r for r in range(4, ws.max_row + 1) if txt(ws, r, c0) == "Total"]
    assert len(total) == 1
    v = num(ws.cell(total[0], hits[0]).value)
    return v * (1e5 if row["unit"] == "count" else 1.0)


@cache
def t72_rows() -> dict[str, int]:
    ws = sebi_ws("72")
    out = {}
    for r in range(4, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if isinstance(v, dt.datetime):  # first of month, except Sep/Oct 2016 typed as the 16th
            assert v.day in (1, 16), v
            out[month_end(v.year, v.month)] = r
    return out


def res_t72(row: dict) -> float:
    ws = sebi_ws("72")
    return num(ws[f"{SEBI_COL['72'][row['counterparty']]}{t72_rows()[row['period']]}"].value)


# ------------------------------------------------------------------------------------------------
# PFRDA Table M7 (SG sector, state-wise; the national 'Total' row) - second pass
# ------------------------------------------------------------------------------------------------

M7_MEASURE = {"subscribers": "No. of Subscribers", "contribution_total": "Total Contribution Cr",
              "contribution_employer": "Employer Contribution Cr", "contribution_employee": "Employee Contribution Cr"}


@cache
def m7_index():
    """(ws, total row, {(yyyy-mm, measure caption): col}) found by the verifier's own header search."""
    ws = xlsx("pfrda_nps_statistics", "M7_state_wise_subscribers.xlsx").worksheets[0]
    assert "Table M7" in txt(ws, 1, 1) and "SG Sector" in txt(ws, 1, 1)
    tot = [r for r in range(4, ws.max_row + 1) if txt(ws, r, 1) == "Total"]
    assert len(tot) == 1, tot
    cols, month = {}, None
    for c in range(3, ws.max_column + 1):
        lab = txt(ws, 2, c)
        if lab:
            m = re.fullmatch(r"([A-Za-z]{3})-(\d{2})", lab)
            assert m, lab
            month = f"20{m.group(2)}-{MON[m.group(1).upper()]:02d}"
        cols[(month, txt(ws, 3, c))] = c
    return ws, tot[0], cols


def m7_cell(month: str, measure: str) -> float | None:
    ws, r, cols = m7_index()
    return num(ws.cell(r, cols[(month, M7_MEASURE[measure])]).value)


def m7_fy_months(y: int) -> list[str]:
    return [f"{y}-{m:02d}" for m in range(4, 13)] + [f"{y + 1}-{m:02d}" for m in range(1, 4)]


def res_m7(row: dict) -> float:
    code = row["item_code"]
    if row["table_id"] == "Table M7 (derived)":
        meas = code.removeprefix("annual_")  # annual_contribution_total -> contribution_total, etc.
        assert meas in M7_MEASURE, code
        return sum(m7_cell(m, meas) for m in m7_fy_months(int(row["period"][:4])))
    if code == "subscribers":
        assert row["period_type"] == "date" and row["stock_flow"] == "stock"
        assert row["period"] == month_end(int(row["period"][:4]), int(row["period"][5:7]))
        return m7_cell(row["period"][:7], code)
    assert row["period_type"] == "month" and row["stock_flow"] == "flow"
    return m7_cell(row["period"], code)


# ------------------------------------------------------------------------------------------------
# EPFO EPS outgo table (AR 2023-24 para 2.15 'EPS Payments'; AR 2024-25 para 2.16 'Table 5') - final pass
# pdfplumber word coordinates: a fourth route, independent of the unit (pypdf text) and of `eps_table5` (text lines)
# ------------------------------------------------------------------------------------------------

EPS_OUTGO_HEADER = ("Pension", "Disbursed", "Withdrawal", "Benefits", "Total")
EPS_OUTGO_COLS = ("eps_pension_disbursed", "eps_withdrawal_benefits", "eps_total_outgo")
EPS_OUTGO_SEARCH = range(25, 61)  # PDF pages searched for the header line (the table sits in chapter 2)


@cache
def eps_outgo_positional(vintage: str) -> tuple[tuple[int, ...], dict[str, tuple[float, float, float]]]:
    """(pages where the table was found, {fy: (pension disbursed, withdrawal benefits, total)}).

    A header line is a line whose words include Pension, Disbursed, Withdrawal, Benefits and Total. Column anchors are
    the right edges of 'Disbursed', 'Benefits' and 'Total' on that line (the amounts are right-aligned). Table rows are
    the lines below it whose first word is a FY ('2019-20' or '2020-2021') followed by exactly three amounts, each
    within 30 pt of its anchor; the '(Rs. crores)' caption line is skipped and the first other line ends the table."""
    name = EPFO_REPORTS[vintage][0]
    found, out = [], {}
    with pdfplumber.open(raw_path("epfo_annual_report_accounts", name)) as pdf:
        for p in EPS_OUTGO_SEARCH:
            lines: dict[float, list] = defaultdict(list)
            for w in pdf.pages[p - 1].extract_words():
                key = next((k for k in lines if abs(k - w["top"]) <= 2), w["top"])
                lines[key].append(w)
            tops = sorted(lines)
            heads = [k for k in tops if set(EPS_OUTGO_HEADER) <= {w["text"] for w in lines[k]}]
            if not heads:
                continue
            assert len(heads) == 1, (name, p, heads)
            found.append(p)
            hw = {w["text"]: w for w in lines[heads[0]]}
            anchors = [hw["Disbursed"]["x1"], hw["Benefits"]["x1"], hw["Total"]["x1"]]
            for k in tops[tops.index(heads[0]) + 1:]:
                ws = sorted(lines[k], key=lambda w: w["x0"])
                if ws[0]["text"].startswith("(Rs"):
                    continue
                m = re.fullmatch(r"(\d{4})-(\d{2}|\d{4})", ws[0]["text"])
                amts = [w for w in ws[1:] if re.fullmatch(r"[\d,]+\.\d{2}", w["text"])]
                if not m or len(amts) != 3 or len(ws) != 4:
                    break
                y1 = int(m.group(1))
                assert int(m.group(2)) % 100 == (y1 + 1) % 100, ws[0]["text"]
                cells = [None, None, None]
                for w in amts:
                    j = min(range(3), key=lambda j: abs(anchors[j] - w["x1"]))
                    assert abs(anchors[j] - w["x1"]) < 30 and cells[j] is None, (name, p, w)
                    cells[j] = amt(w["text"])
                fy = f"{y1}-{(y1 + 1) % 100:02d}"
                assert fy not in out, (name, fy)
                out[fy] = tuple(cells)
    return tuple(found), out


def res_eps_outgo(row: dict) -> float:
    assert row["series_id"] == f"eps_outgo.{row['item_code'].removeprefix('eps_')}.current", row["series_id"]
    assert row["period_type"] == "fy" and row["stock_flow"] == "flow" and row["unit"] == "INR_crore"
    return eps_outgo_positional(row["vintage"])[1][row["period"]][EPS_OUTGO_COLS.index(row["item_code"])]


# ------------------------------------------------------------------------------------------------
# census
# ------------------------------------------------------------------------------------------------

RESOLVER = {"irdai_summary": res_irdai, "irdai_life": res_irdai, "irdai_nonlife": res_irdai, "epfo_ar": res_epfo,
            "pfrda_nps": res_pfrda, "sebi_primary": res_sebi, "sebi_bonds_equity": res_sebi,
            "sebi_foreign": res_sebi, "sebi_mf": res_sebi, "pfrda_sg": res_m7, "epfo_eps_outgo": res_eps_outgo}


@cache
def census() -> dict[str, tuple[int, list]]:
    out = {}
    for ds in DATASETS:
        df = clean(ds)
        bad = []
        for row in df.iter_rows(named=True):
            try:
                got = RESOLVER[ds](row)
            except Exception as e:  # noqa: BLE001  (report, then fail below)
                bad.append((row["series_id"], row["period"], row["vintage"], row["value"], f"unresolved: {e!r}"[:160]))
                continue
            if got is None or not close(row["value"], got):
                bad.append((row["series_id"], row["period"], row["vintage"], row["value"], got))
        out[ds] = (df.height, bad)
    return out


@pytest.mark.parametrize("ds", DATASETS)
def test_census_matches_raw(ds):
    n, bad = census()[ds]
    print(f"{ds}: {n} rows compared, {len(bad)} mismatches")
    assert n > 0
    assert not bad, f"{ds}: {len(bad)} of {n} values differ from the raw file, e.g. {bad[:8]}"


def test_seeded_sample_report():
    """Prints a seeded, table-stratified sample (for docs/phase1/verify/finsector_markets.md)."""
    rng = random.Random(SEED)
    total = 0
    for ds in DATASETS:
        df = clean(ds)
        by_t = defaultdict(list)
        for row in df.iter_rows(named=True):
            by_t[row["table_id"]].append(row)
        for t in sorted(by_t):
            for row in rng.sample(by_t[t], min(2, len(by_t[t]))):
                got = RESOLVER[ds](row)
                total += 1
                print(f"{ds} | {t} | {row['series_id']} | {row['period']} | clean {row['value']} | raw {got}")
                assert close(row["value"], got)
    assert total >= 50


def test_hand_anchors_epfo_pdf():
    df = clean("epfo_ar")
    assert len(HAND_ANCHORS) >= 20
    for vint, sid, period, v in HAND_ANCHORS:
        got = df.filter((pl.col("vintage") == vint) & (pl.col("series_id") == sid) & (pl.col("period") == period))
        assert got.height == 1, (vint, sid, period)
        assert close(got["value"][0], v), (vint, sid, period, got["value"][0], v)
        assert close(epfo_values(vint)[(sid, period)], v)  # the verifier's own parse agrees too


# ------------------------------------------------------------------------------------------------
# completeness (the other direction): published numbers in the ingested blocks all have a clean row
# ------------------------------------------------------------------------------------------------


HEADING_ROWS = {"PREMIUMS EARNED - NET", "INCOME FROM INVESTMENTS", "PROVISIONS (OTHER THAN TAXATION)",
                "CHANGE IN VALUATION OF LIABILITY IN RESPECT OF LIFE POLICIES", "APPROPRIATIONS", "OTHER EXPENSES"}


def count_numeric(ws, rows, cols) -> int:
    return sum(1 for r in rows for c in cols if num(ws.cell(r, c).value) is not None)


def n_clean(ds: str, table: str) -> int:
    return clean(ds).filter(pl.col("table_id") == table).height


def test_completeness_sebi():
    for tnum, ds in (("1", "sebi_primary"), ("7", "sebi_primary"), ("8", "sebi_primary"), ("13", "sebi_primary"),
                     ("14", "sebi_primary"), ("11", "sebi_bonds_equity"), ("23", "sebi_bonds_equity"),
                     ("58", "sebi_foreign"), ("59", "sebi_foreign"), ("60", "sebi_foreign"), ("62", "sebi_foreign"),
                     ("63", "sebi_foreign"), ("64", "sebi_mf"), ("70", "sebi_mf")):
        ws = sebi_ws(tnum)
        m = SEBI_COL.get(tnum)
        if tnum == "58":
            cols = [ci(c) + k for c in m.values() for k in (0, 1)]
        elif tnum == "62":
            cols = list(range(2, 34))
        elif tnum == "63":
            cols = list(range(2, 17))
        elif tnum == "70":
            cols = list(range(2, 11))
        else:
            cols = sorted({ci(c) for c in m.values()})
        n = count_numeric(ws, sebi_rows(tnum).values(), cols)
        assert n == n_clean(ds, f"Table {tnum}"), (tnum, n, n_clean(ds, f"Table {tnum}"))
    ws = sebi_ws("72")
    assert count_numeric(ws, t72_rows().values(), range(2, 7)) == n_clean("sebi_mf", "Table 72")
    assert n_clean("sebi_mf", "Table 69") == 7 * 6  # 7 year blocks x 6 fields read from the 'Total' row


def test_completeness_pfrda():
    for t in PF_FILES:
        ws, cols, rows = pf_index(t)
        n = count_numeric(ws, rows.values(), cols.values())
        assert n == n_clean("pfrda_nps", t), (t, n, n_clean("pfrda_nps", t))


def test_completeness_irdai():
    # Table 2, 40: three / five group rows x 10 years
    ws = irdai_wb("Part I.xlsx")["2"]
    rows = [group_row("Part I.xlsx", "2", lab, 4) for lab in T2_LABEL.values()]
    assert count_numeric(ws, rows, range(3, 13)) == n_clean("irdai_life", "Table 2")
    ws = irdai_wb("Part II.xlsx")["40"]
    rows = [group_row("Part II.xlsx", "40", lab, 4) for lab in GROUP_LABEL.values()]
    assert count_numeric(ws, rows, range(3, 13)) == n_clean("irdai_nonlife", "Table 40")
    ws = irdai_wb("Part II.xlsx")["41"]
    rows = [group_row("Part II.xlsx", "41", lab, 5) for lab in GROUP_LABEL.values()]
    cols = [c for seg in T41_SEG.values() for c in block_cols(ws, 3, 4, seg, 10).values()]
    assert count_numeric(ws, rows, cols) == n_clean("irdai_nonlife", "Table 41")
    ws, idx = t20_index()
    assert count_numeric(ws, idx.values(), range(3, 13)) == n_clean("irdai_life", "Table 20")
    # Table 24/25 (LIC, TOTAL blocks) and 51 (four group blocks): every numeric cell of the labelled rows
    for member, sheet, ds, blocks in (("Part I.xlsx", "24", "irdai_life", LIFE_BLOCK),
                                      ("Part I.xlsx", "25", "irdai_life", LIFE_BLOCK),
                                      ("Part II.xlsx", "51", "irdai_nonlife", T51_BLOCK)):
        ws = irdai_wb(member)[sheet]
        cols = [c for b in blocks.values() for c in block_cols(ws, 3, 4, b, 10).values()]
        rows = []
        for lab, rs in label_rows(member, sheet).items():
            for r in rs:
                if lab.startswith(("Note", "Figures", "*", "1.", "2.", "3.")):
                    continue
                if lab.upper().rstrip(":") in HEADING_ROWS:  # section headings: may carry only zeros
                    stray = [(ws.cell(4, c).value, num(ws.cell(r, c).value)) for c in cols
                             if num(ws.cell(r, c).value) not in (None, 0.0)]
                    # known exception: T25 TOTAL block 2018-19 prints 41.75 lakh (0.42 cr) on the heading row
                    assert stray == ([("2018-19", 41.75)] if (sheet, r) == ("25", 16) else []), (sheet, lab, stray)
                    continue
                rows.append(r)
        assert count_numeric(ws, rows, cols) == n_clean(ds, f"Table {sheet}"), sheet


def test_completeness_summary_skips_only_declared_rows():
    """Every numeric Summary row is ingested except Swiss Re (#) figures and grievance/complaint rows."""
    df = clean("irdai_summary")
    for sheet in "ABC":
        ws, idx, years = summary_index(sheet)
        n = 0
        for (sec, lab), r in idx.items():
            skip = lab.endswith("#") or sec.upper().startswith("REDRESSEL") or lab.startswith("No of companies made")
            if not skip:
                n += count_numeric(ws, [r], years.values())
        assert n == df.filter(pl.col("table_id") == f"Summary Table {sheet}").height, sheet


# ------------------------------------------------------------------------------------------------
# semantic / systematic-error hunts
# ------------------------------------------------------------------------------------------------


def val(ds, sid, period, vintage=None) -> float:
    q = clean(ds).filter((pl.col("series_id") == sid) & (pl.col("period") == period))
    if vintage:
        q = q.filter(pl.col("vintage") == vintage)
    assert q.height == 1, (ds, sid, period, q.height)
    return q["value"][0]


def test_scale_rs_lakh_tables_agree_with_crore_tables():
    # T24 (Rs lakh, /100) premium for LIC and the industry == T2 (Rs crore)
    for inst in ("lic", "insurers_life"):
        for fy in ("2019-20", "2023-24", "2024-25"):
            a = val("irdai_life", f"t24.premium.{inst}.current", fy)
            b = val("irdai_life", f"t2.total_premium.{inst}.current", fy)
            assert abs(a / b - 1) < 0.002, (inst, fy, a, b)
    # T51 (no caption) PAT of the four groups ~ Summary C PAT (Rs crore; Summary C adds reinsurers)
    for fy in ("2017-18", "2023-24", "2024-25"):
        s = sum(val("irdai_nonlife", f"t51.profit_after_tax.{g}.current", fy) for g in T51_BLOCK)
        c = val("irdai_summary", "sum_c.profit_after_tax.current", fy)
        assert abs(s - c) < 0.02 * abs(c) + 100, (fy, s, c)


def test_scale_t58_rupee_billion_to_crore():
    # implied INR/USD rate from the converted rupee column must be a plausible rupee rate
    for fy in ("2013-14", "2019-20", "2023-24", "2025-26"):
        inr = val("sebi_foreign", "t58.fdi_gross_inflows.current", fy)
        usd = val("sebi_foreign", "t58.fdi_gross_inflows.usd", fy)
        rate = inr * 1e7 / (usd * 1e6)
        assert 55 < rate < 95, (fy, rate)


def test_counts_are_whole_units():
    # lakh counts converted to units: new policies 2023-24 (Summary A) ~ 36.5 crore policies
    assert close(val("irdai_summary", "sum_a.new_policies", "2023-24"), 3651.65 * 1e5)
    assert close(val("sebi_mf", "t69.sips_closing", "2024-03-31"), num(sebi_ws("69").cell(7, 6 + 8 * 4).value) * 1e5)


def test_t72_month_label_is_month_end_position():
    # first-of-month label read as month-end: March rows equal T64 end-of-FY AUM (2021-22 onwards)
    for y in (2022, 2023, 2024, 2025, 2026):
        a = val("sebi_mf", "t72.aum.total.current", f"{y}-03-31")
        b = val("sebi_mf", "t64.assets_end_of_period.mf_all.current", f"{y}-03-31")
        assert abs(a / b - 1) < 0.002, (y, a, b)


def test_t23_exchange_blocks_are_row_aligned():
    ws = sebi_ws("23")
    for fy, r in sebi_rows("23").items():
        assert fy_of(ws[f"E{r}"].value) == fy and fy_of(ws[f"I{r}"].value) == fy, (fy, r)


def test_status_and_derived_rows():
    for ds in DATASETS:
        df = clean(ds)
        st = Counter(df["status"].to_list())
        if ds in ("pfrda_nps", "pfrda_sg"):
            assert set(st) == {"official", "derived"}
            d = df.filter(pl.col("status") == "derived")
            want = "Table M4 (derived)" if ds == "pfrda_nps" else "Table M7 (derived)"
            assert set(d["table_id"].to_list()) == {want}
        else:
            assert set(st) == {"official"}, (ds, st)


def test_reference_year_2023_24_present_everywhere():
    need = {
        "irdai_summary": ["sum_a.total_premium.current", "sum_c.gross_direct_premium.current"],
        "irdai_life": ["t24.premium.insurers_life.current", "t24.benefits_paid_net.insurers_life.current"],
        "irdai_nonlife": ["t44.claims_incurred_net.total.insurers_general_direct.current"],
        "epfo_ar": ["app5i.epf_contribution.current", "app5i.total_payment.current"],
        "pfrda_nps": ["m4d.annual_contribution.central_govt.current", "a5.tier2_contribution.all_citizen.current"],
        "sebi_primary": ["t14.total_amount.current"],
        "sebi_foreign": ["t60.net_investment.debt_general.current", "t58.portfolio_net.usd"],
        "sebi_mf": ["t64.net_inflow.mf_all.current"],
    }
    for ds, sids in need.items():
        for sid in sids:
            q = clean(ds).filter((pl.col("series_id") == sid) & (pl.col("period") == "2023-24"))
            assert q.height >= 1, (ds, sid)
    assert clean("sebi_bonds_equity").filter(pl.col("period") == "2024-03-31").height > 0


def test_epfo_rates_complete_and_revision_is_the_only_one():
    for vint, (_, rfy, _) in EPFO_REPORTS.items():
        mine = {p for (s, p) in epfo_values(vint) if s == "app5vii.epf_interest_rate"}
        theirs = set(clean("epfo_ar").filter((pl.col("vintage") == vint) & (pl.col("series_id") == "app5vii.epf_interest_rate"))["period"].to_list())
        assert mine == theirs, (vint, mine ^ theirs)
        assert "1978-79" not in theirs and "2000-01" not in theirs
    # EPF contribution 2023-24: AR 2023-24 vs AR 2024-25 (five-year table) - the one known revision
    a = val("epfo_ar", "fiveyear.epf_contribution.current", "2023-24", "2024-12")
    b = val("epfo_ar", "fiveyear.epf_contribution.current", "2023-24", "2026-02")
    assert close(b - a, 7291.23)


# ------------------------------------------------------------------------------------------------
# second pass (verifier, 2026-09-29): the builder's fixes and regressions
# ------------------------------------------------------------------------------------------------


@cache
def prov() -> pl.DataFrame:
    return pl.read_parquet(CLEAN / "_provenance.parquet")


def prov_notes(ds: str, **filt) -> list[str]:
    q = clean(ds)
    for k, v in filt.items():
        q = q.filter(pl.col(k).str.starts_with(v) if k == "series_id" else pl.col(k) == v)
    ids = q["prov_id"].unique().to_list()
    assert ids, (ds, filt)
    return [n or "" for n in prov().filter(pl.col("prov_id").is_in(ids))["notes"].to_list()]


@cache
def epfo_pypdf_page(name: str, page: int) -> str:
    """pypdf text of one page (the rotated App. 5(i) page, where pdfplumber mirrors the tokens)."""
    import pypdf

    return pypdf.PdfReader(raw_path("epfo_annual_report_accounts", name)).pages[page - 1].extract_text()


def app5i_rows(name: str, page: int) -> tuple[list[list[float]], list[float], str]:
    t = epfo_pypdf_page(name, page)
    assert "APPENDIX-5(i)" in t
    zones, total = [], None
    for ln in t.splitlines():
        v = [amt(x) for x in re.findall(r"\d[\d,]*\.\d{2}", ln)]
        if len(v) != 8:
            continue
        if ln.strip().startswith("Total"):
            total = v
        else:
            zones.append(v)
    assert total is not None and len(zones) == 22, (name, len(zones))
    return zones, total, t


def test_v1_epfo_past_accumulation_in_raw_and_provenance():
    # raw: the para 5.4 footnote (pdfplumber) and the App. 5(i) central line and note (pypdf)
    _, t = epfo_page("2026-02", "Contributions Received from Un-exempted Establishments")
    assert "2,58,132.93**" in t
    assert re.search(r"includes the amount of Past Accumulation of Rs\. 7,320\.22 Crore", t)
    zones, total, t5 = app5i_rows("epfo_annual_report_2024_25.pdf", 236)
    assert re.search(r"^Past Accumulation 7,320\.22\*\* 7,320\.22$", t5, flags=re.M)
    assert "include the Contributions, Securities received on cancellation of exemption and Past accumulations" in t5
    zsum = [sum(z[i] for z in zones) for i in range(8)]
    assert abs(total[0] - zsum[0] - 7320.22) < 0.05  # EPF contribution = 22 zones + central past accumulation
    assert close(total[0], val("epfo_ar", "app5i.epf_contribution.current", "2024-25", "2026-02"))
    # AR 2023-24: zones add to the total, no central line, no note
    zones3, total3, t3 = app5i_rows("epfo_annual_report_2023_24.pdf", 235)
    assert all(abs(total3[i] - sum(z[i] for z in zones3)) < 0.05 for i in range(8))
    assert "Past Accumulation" not in t3 and "cancellation of exemption" not in t3
    # the revision of 2023-24 (+7,291.23) sits entirely in EPF contributions
    a = val("epfo_ar", "fiveyear.total_contribution.current", "2023-24", "2026-02")
    assert close(a - total3[6], 7291.23)
    # provenance: the footnote is on every AR 2024-25 contribution record, and not on the AR 2023-24 ones
    for pfx in ("para54.", "fiveyear.", "app5i."):
        notes = prov_notes("epfo_ar", vintage="2026-02", series_id=pfx)
        assert len(notes) == 1 and "7,320.22" in notes[0] and "Past Accumulation" in notes[0], pfx
        assert "subtract 7,320.22" in notes[0], pfx
        if pfx == "fiveyear.":
            assert "7,291.23" in notes[0]
        old = prov_notes("epfo_ar", vintage="2024-12", series_id=pfx)
        assert all("7,320.22" not in n for n in old), pfx


def test_epfo_ar2425_app5i_central_lines_in_eps_payment():
    """AR 2024-25 App. 5(i): EPS payment Total (27,963.41) = zones 20,768.29 + CPPS 6,813.22 + 'Adjustment of
    Pension Disbursement Savings A/c Balance' 381.88 (+ rounding). Pins the raw fact behind finding V11."""
    zones, total, t = app5i_rows("epfo_annual_report_2024_25.pdf", 236)
    assert re.search(r"^CPPS 6813\.22 6813\.22$", t, flags=re.M)
    assert re.search(r"^381\.88 381\.88$", t, flags=re.M) and "Adjustment of Pension Disbursement Savings" in t
    eps_pay = sum(z[3] for z in zones)
    assert abs(total[3] - eps_pay - (6813.22 + 381.88)) < 0.05
    assert close(total[3], val("epfo_ar", "app5i.eps_payment.current", "2024-25", "2026-02"))
    assert close(total[7], val("epfo_ar", "app5i.total_payment.current", "2024-25", "2026-02"))


def test_m7_total_row_integrity_and_completeness():
    ws, r, cols = m7_index()
    months = sorted({m for m, _ in cols})
    assert len(months) == 139 and months[0] == "2014-12" and months[-1] == "2026-06"
    # the Total row equals the sum of the state rows (so the row found is the national total)
    for (m, cap), c in cols.items():
        s = sum(num(ws.cell(k, c).value) or 0.0 for k in range(5, r))
        assert abs(s - num(ws.cell(r, c).value)) < 0.5, (m, cap)
    # every published Total cell has a clean row; FY sums only for complete FYs 2015-16..2025-26
    df = clean("pfrda_sg")
    assert df.filter(pl.col("table_id") == "Table M7").height == count_numeric(ws, [r], cols.values()) == 556
    fys = sorted(df.filter(pl.col("table_id") == "Table M7 (derived)")["period"].unique().to_list())
    assert fys == [f"{y}-{(y + 1) % 100:02d}" for y in range(2015, 2026)]


def test_m7_confirms_m4_cumulative_reading_for_sg():
    for y in range(2015, 2025):
        fy = f"{y}-{(y + 1) % 100:02d}"
        m7 = sum(m7_cell(m, "contribution_total") for m in m7_fy_months(y))
        m4 = pf_cell("Table M4", f"{y + 1}-03-31", "SG") - pf_cell("Table M4", f"{y}-03-31", "SG")
        assert abs(m7 - m4) < (12.0 if fy in ("2022-23", "2024-25") else 0.3), (fy, m7, m4)
    assert abs(val("pfrda_sg", "m7d.annual_contribution_total.state_govt.current", "2023-24")
               - val("pfrda_nps", "m4d.annual_contribution.state_govt.current", "2023-24")) < 0.05


def test_second_pass_metadata_fixes():
    # V4: T69 opening count is a stock at the previous 31 March and equals the prior closing count from 2023-24
    df = clean("sebi_mf").filter(pl.col("item_code") == "sips_existing_beginning")
    assert set(df["stock_flow"].to_list()) == {"stock"} and set(df["period_type"].to_list()) == {"date"}
    assert sorted(df["period"].to_list()) == [f"{y}-03-31" for y in range(2019, 2026)]
    for y in (2023, 2024, 2025):
        assert close(val("sebi_mf", "t69.sips_existing_beginning", f"{y}-03-31"),
                     val("sebi_mf", "t69.sips_closing", f"{y}-03-31"))
    # V5: T58 sign convention; V6: T64 caption; V7: no '(cumulative)' in the M4 label; V9: LIC abroad; V10: '-' as nil
    assert any("outflow" in n for n in prov_notes("sebi_foreign", table_id="Table 58"))
    assert norm(sebi_ws("64")["A1"].value).endswith("(₹ crore)")
    assert any("crore" in n and "caption" in n.lower() for n in prov_notes("sebi_mf", table_id="Table 64"))
    labels = clean("pfrda_nps").filter(pl.col("table_id") == "Table M4")["item_label"].to_list()
    assert labels and not any("cumulative" in x.lower() for x in labels)
    for t in ("Table 24", "Table 2"):
        assert any("398.15" in n and "476.25" in n for n in prov_notes("irdai_life", table_id=t)), t
    assert all("nil" in n for n in prov_notes("epfo_ar", series_id="invest."))


# ------------------------------------------------------------------------------------------------
# Close-out pass (2026-09-29, late): the builder's EPFO/EPS provenance follow-up (V11, V12), the new
# build check `_check_app5i_lines` and the NSDL/AMFI terms block. No values changed; the checks below
# re-derive every number the new notes state from the raw PDFs by a third, independent route:
# pdfplumber *word positions* (the unit reads pypdf text; the census above reads pdfplumber text lines).
# ------------------------------------------------------------------------------------------------

APP5I_COLS = ("epf_contribution", "epf_payment", "eps_contribution", "eps_payment", "edli_contribution",
              "edli_payment", "total_contribution", "total_payment")
APP5I_PAGE = {"2024-12": ("epfo_annual_report_2023_24.pdf", 235), "2026-02": ("epfo_annual_report_2024_25.pdf", 236)}
NUM_TOKEN = re.compile(r"[\d,]+\.\d{2}\**")


@cache
def app5i_positional(vintage: str) -> tuple[list[tuple[str, list[float]]], list[tuple[str, dict]], list[float]]:
    """Appendix-5(i) read from word coordinates: (zone rows, central lines {column: value}, Total row).

    Rows are clusters of numeric tokens along the row axis (a gap > 9 pt starts a new row; a value wrapped a few
    points off its row stays in it). Columns are anchored on the Total row's own eight positions, so a central
    line with one or two values is placed by where it is printed, not by its order. The AR 2024-25 page is
    rotated: pdfplumber returns each token mirrored, the row axis is x0 and the column axis is -top (EPF
    contribution has the largest top). Label words are attached to the nearest numeric row.
    """
    name, page = APP5I_PAGE[vintage]
    with pdfplumber.open(raw_path("epfo_annual_report_accounts", name)) as pdf:
        words = pdf.pages[page - 1].extract_words()
    rotated = sum(not w["upright"] for w in words) > len(words) / 2
    toks = []
    for w in words:
        if rotated and w["upright"]:
            continue  # running header/footer
        text = w["text"][::-1] if rotated else w["text"]
        toks.append(((w["x0"] if rotated else w["top"]), (-w["top"] if rotated else w["x0"]), text))
    nums = sorted(t for t in toks if NUM_TOKEN.fullmatch(t[2]))
    # the 'Total' label with eight amounts on its row; footnotes below it (which quote 7,320.22) are not table rows
    (trow,) = [t[0] for t in toks if t[2] == "Total" and sum(abs(x[0] - t[0]) <= 3 for x in nums) == 8]
    nums = [t for t in nums if t[0] <= trow + 3]
    rows: list[list] = []
    for t in nums:
        if rows and t[0] - rows[-1][-1][0] <= 9:
            rows[-1].append(t)
        else:
            rows.append([t])
    lo, hi = rows[0][0][0] - 6, rows[-1][-1][0] + 6
    labels: dict[int, list] = defaultdict(list)
    for t in toks:
        if NUM_TOKEN.fullmatch(t[2]) or not lo <= t[0] <= hi:
            continue
        k = min(range(len(rows)), key=lambda i: max(rows[i][0][0] - t[0], t[0] - rows[i][-1][0], 0))
        labels[k].append(t)
    lab = {k: " ".join(x[2] for x in sorted(v, key=lambda x: (round(x[0]), x[1]))) for k, v in labels.items()}
    (ti,) = [i for i in range(len(rows)) if lab.get(i, "").startswith("Total") and len(rows[i]) == 8]
    assert ti == len(rows) - 1, "Total is not the last numeric row"
    anchors = sorted(t[1] for t in rows[ti])  # column order: EPF c, EPF p, EPS c, EPS p, EDLI c, EDLI p, total c, total p
    zones, central = [], []
    for i, r in enumerate(rows[:ti]):
        cells = {}
        for t in r:
            j = min(range(8), key=lambda j: abs(anchors[j] - t[1]))
            assert abs(anchors[j] - t[1]) < 5 and APP5I_COLS[j] not in cells, (vintage, lab.get(i), t)
            cells[APP5I_COLS[j]] = amt(t[2])
        if len(cells) == 8:
            zones.append((lab.get(i, ""), [cells[c] for c in APP5I_COLS]))
        else:
            central.append((lab.get(i, ""), cells))
    total = [amt(t[2]) for t in sorted(rows[ti], key=lambda t: t[1])]
    return zones, central, total


def zsum(zones, col: str) -> float:
    return round(sum(v[APP5I_COLS.index(col)] for _, v in zones), 2)


def test_closeout_app5i_positional_matches_pypdf_zone_by_zone():
    """176 zone cells per report, read by word position, equal the pypdf text read (app5i_rows) cell by cell."""
    for vint, (name, page) in APP5I_PAGE.items():
        zones, _, total = app5i_positional(vint)
        zones_py, total_py, _ = app5i_rows(name, page)
        assert len(zones) == 22 and [v for _, v in zones] == zones_py, vint
        assert total == total_py, vint
        for col, v in zip(APP5I_COLS, total, strict=True):  # the emitted Total rows
            assert close(val("epfo_ar", f"app5i.{col}.current", EPFO_REPORTS[vint][1], vint), v), (vint, col)


def test_closeout_app5i_central_lines_by_print_position():
    """AR 2024-25: exactly four central lines, each in the columns the notes and the build check say, and
    Total = zones + central lines in all 8 columns. AR 2023-24: none, and zones = Total."""
    zones, central, total = app5i_positional("2026-02")
    got = {re.sub(r"\s+", " ", lab): cells for lab, cells in central}
    assert len(got) == 4, got
    want = {r"^Past Accumulation$": {"epf_contribution": 7320.22, "total_contribution": 7320.22},
            r"^CPPS$": {"eps_payment": 6813.22, "total_payment": 6813.22},
            r"^Adjustment of Pension Disbursement Savings A/c Balance$": {"eps_payment": 381.88, "total_payment": 381.88},
            r"^Adjustments of remittances at Head O\w+ level$": {"eps_contribution": 0.19}}  # 'Oiffce': ffi ligature
    for pat, cells in want.items():
        (lab,) = [k for k in got if re.match(pat, k)]
        assert got[lab] == cells, (lab, got[lab])
    # a total column gets the central values of its three scheme columns (the 0.19 is printed only under EPS
    # contribution; the Total contribution is 0.23 off without it, 0.04 with it)
    parts = {"total_contribution": APP5I_COLS[0:6:2], "total_payment": APP5I_COLS[1:6:2]}
    for j, col in enumerate(APP5I_COLS):
        extra = sum(c.get(k, 0.0) for c in got.values() for k in parts.get(col, (col,)))
        assert abs(total[j] - zsum(zones, col) - extra) <= 0.05, (col, total[j], zsum(zones, col), extra)
    assert abs(total[6] - zsum(zones, "total_contribution") - 7320.22) > 0.2
    zones3, central3, total3 = app5i_positional("2024-12")
    assert central3 == [] and len(zones3) == 22
    assert all(abs(total3[j] - zsum(zones3, c)) <= 0.05 for j, c in enumerate(APP5I_COLS))


def test_closeout_note_numbers_rederived_from_raw():
    """Every number the new AR 2024-25 App. 5(i) / para 5.5 notes state, recomputed from the positional read."""
    zones, _, total = app5i_positional("2026-02")
    zones3, _, total3 = app5i_positional("2024-12")
    eps_pay = total[APP5I_COLS.index("eps_payment")]
    derived = {
        "20,768.29": zsum(zones, "eps_payment"),
        "1,68,714.70": zsum(zones, "total_payment"),
        "73,788.18": zsum(zones, "eps_contribution"),
        "3,28,308.36": zsum(zones, "total_contribution"),
        "2,50,812.70": zsum(zones, "epf_contribution"),
        "27,581.53": round(eps_pay - 381.88, 2),
        "23,410.17": total3[APP5I_COLS.index("eps_payment")],  # AR 2023-24 Total (= its zones)
        "27,963.41": eps_pay, "1,75,909.82": total[7], "73,788.40": total[2], "3,35,628.81": total[6],
    }
    for s, v in derived.items():
        assert close(amt(s), v), (s, v)
    # the notes say the total 'rises 19.5%': it is 19.4498%, i.e. 19.4% (rounding slip, logged in the close-out notes)
    assert round(100 * (eps_pay / derived["23,410.17"] - 1), 4) == 19.4498
    # the stated residuals (+0.02, +0.03, +0.04) are what the page gives
    assert round(eps_pay - derived["20,768.29"] - 6813.22 - 381.88, 2) == 0.02
    assert round(total[2] - derived["73,788.18"] - 0.19, 2) == 0.03
    assert round(total[6] - derived["3,28,308.36"] - 7320.22 - 0.19, 2) == 0.04
    for pfx in ("app5i.", "fiveyear."):
        (n,) = prov_notes("epfo_ar", vintage="2026-02", series_id=pfx)
        for s in derived:
            assert s in n, (pfx, s)
    # para 5.5 'prints the same 2024-25 totals'
    for j, col in enumerate(("epf_contribution", "epf_payment", "eps_contribution_employer", "eps_payment",
                             "edli_contribution", "edli_payment", "total_contribution", "total_payment")):
        assert close(val("epfo_ar", f"fiveyear.{col}.current", "2024-25", "2026-02"), total[j]), col


CLOSEOUT_QUOTES = [  # (report, PDF page, verbatim text the new notes / issues -5 and -37 quote or paraphrase)
    ("epfo_annual_report_2024_25.pdf", 45, "EPFO rolled out Centralised Pension Payment System (CPPS) pan India Since Jan 2025"),
    ("epfo_annual_report_2024_25.pdf", 136, "was fully implemented in December 2024, ensuring centralised pension disbursal to over 69 lakh pensioners"),
    ("epfo_annual_report_2024_25.pdf", 137, "on 30 November 2024 pensions were disbursed for 24 Regional Offices to 9,30,448 pensioners amounting to"),
    ("epfo_annual_report_2024_25.pdf", 137, "213.55 crore"),
    ("epfo_annual_report_2024_25.pdf", 137, "Online System for Surrender of Exemption and Transfer of Past Accumulations"),
    ("epfo_annual_report_2024_25.pdf", 137, "transfer of funds including government securities to credit member balances in the statutory fund"),
    ("epfo_annual_report_2024_25.pdf", 68, "the employer has the responsibility to transfer the entire corpus to the accounts of the Central Board of Trustees, EPF"),
    ("epfo_annual_report_2024_25.pdf", 70, "EPFO launched an online Module for surrender of exemption on 13.08.2024"),
    ("epfo_annual_report_2023_24.pdf", 72, "the employer has the responsibility to transfer the entire corpus to the accounts of the Central Board of Trustees, EPF"),
]


@cache
def pdf_page_text(name: str, page: int) -> str:
    with pdfplumber.open(raw_path("epfo_annual_report_accounts", name)) as pdf:
        return re.sub(r"\s+", " ", pdf.pages[page - 1].extract_text() or "")


def test_closeout_quoted_passages_are_verbatim_on_the_cited_pages():
    for name, page, s in CLOSEOUT_QUOTES:
        assert s in pdf_page_text(name, page), (name, page, s)
    (n,) = prov_notes("epfo_ar", vintage="2026-02", series_id="app5i.")
    for s in ("Since Jan 2025", "fully implemented in December 2024", "213.55", "9,30,448", "PDF p.68", "PDF p.70",
              "PDF p.137", "upper bound", "not published"):
        assert s in n, s
    (n3,) = prov_notes("epfo_ar", vintage="2024-12", series_id="app5i.")
    assert "no central line" in n3 and "7,320.22" not in n3 and "CPPS" not in n3


def test_closeout_changed_rows_seeded_census():
    """The rows whose provenance the follow-up rewrote (AR 2024-25 para 5.4, para 5.5, App. 5(i); AR 2023-24
    App. 5(i)): all 61 re-resolved, App. 5(i) through the positional parser and the rest through epfo_values."""
    df = clean("epfo_ar")
    changed = df.filter(((pl.col("vintage") == "2026-02") & pl.col("series_id").str.contains(r"^(para54|fiveyear|app5i)\."))
                        | ((pl.col("vintage") == "2024-12") & pl.col("series_id").str.starts_with("app5i.")))
    assert changed.height == 5 + 40 + 8 + 8 == 61
    pos = {v: app5i_positional(v)[2] for v in APP5I_PAGE}
    rows = list(changed.iter_rows(named=True))
    for r in rows:
        if r["series_id"].startswith("app5i."):
            got = pos[r["vintage"]][APP5I_COLS.index(r["series_id"].split(".")[1])]
        else:
            got = epfo_values(r["vintage"])[(r["series_id"], r["period"])]
        assert close(r["value"], got), (r["vintage"], r["series_id"], r["period"], r["value"], got)
    for r in random.Random(SEED).sample(rows, 30):  # printed for the notes
        print(f"{r['vintage']} | {r['series_id']} | {r['period']} | {r['value']}")


def test_closeout_terms_block_on_hosts_and_pins():
    """NSDL/AMFI: the code policy refuses every registry URL of both sources (verifier reads the registry file
    itself), and no finsector_markets pin or sidecar URL is on either host."""
    from urllib.parse import urlsplit

    from pipeline.core import policy

    reg = yaml.safe_load((ROOT / "data" / "registry.yaml").read_text(encoding="utf-8"))
    entries = {e["id"]: e for e in (reg["sources"] if isinstance(reg, dict) else reg)}
    for sid in ("nsdl_fpi_monitor", "amfi_monthly_quarterly"):
        e = entries[sid]
        assert policy.source_refusal(sid, e), sid
        for u in [e["urls"]["landing"], *e["urls"]["data"]]:
            assert policy.url_refusal(sid, e, u) and policy.denied_host(u), u
    for key, pin in pins().items():
        host = urlsplit(pin["url"]).hostname or ""
        assert not re.search(r"(^|\.)(nsdl\.co\.in|amfiindia\.com)$", host), key
        side = ROOT / (pin["path"] + ".meta.json")
        if side.exists():
            for u in re.findall(r"https?://[^\"\s]+", side.read_text(encoding="utf-8")):
                assert not re.search(r"nsdl\.co\.in|amfiindia\.com", urlsplit(u).hostname or ""), (key, u)


# --- close-out findings ---------------------------------------------------------------------------

EPS_TABLE5 = {  # 'EPS Payments' / 'Table 5' (Pension Disbursed, Withdrawal Benefits, Total), as printed
    "2024-12": ("epfo_annual_report_2023_24.pdf", (39,), {
        "2019-20": (11320.89, 6796.62, 18117.51), "2020-21": (12172.56, 8206.41, 20378.97),
        "2021-22": (12933.12, 7989.01, 20922.14), "2022-23": (14444.60, 7352.25, 21796.85),
        "2023-24": (15130.68, 7908.25, 23038.94)}),
    "2026-02": ("epfo_annual_report_2024_25.pdf", (40, 41), {
        "2020-21": (12172.56, 8206.41, 20378.97), "2021-22": (12933.12, 7989.01, 20922.14),
        "2022-23": (14444.60, 7352.25, 21796.85), "2023-24": (15130.68, 7908.25, 23038.94),
        "2024-25": (18957.86, 9005.90, 27963.76)}),
}


def eps_table5(vint: str) -> dict[str, tuple[float, float, float]]:
    name, pages, _ = EPS_TABLE5[vint]
    t = " ".join(pdf_page_text(name, p) for p in pages)
    t = t[t.index("Pension Disbursed Withdrawal Benefits Total"):]
    out = {}
    for y1, y2, a, b, c in re.findall(r"(\d{4})-(?:\d{2})?(\d{2}) ([\d,]+\.\d{2}) ([\d,]+\.\d{2}) ([\d,]+\.\d{2})", t):
        out.setdefault(f"{y1}-{y2}", (amt(a), amt(b), amt(c)))
    return out


def test_v13_raw_eps_outgo_table_splits_pensions_from_withdrawal_benefits():
    """V13 (raw fact): the report's own EPS outgo table splits the EPS payment into Pension Disbursed and
    Withdrawal Benefits. 2024-25: 18,957.86 + 9,005.90 = 27,963.76, which the note under it reconciles to the
    Balance-Sheet 27,963.41 (Life Assurance Benefit 0.35). Earlier years: App. 5(i)/para 5.5 EPS payment exceeds
    the outgo total by 38.03 (2020-21), 382.46, 315.97 and 371.23 (2023-24)."""
    for vint, (_, _, want) in EPS_TABLE5.items():
        got = eps_table5(vint)
        for y, w in want.items():
            assert got[y] == w and abs(w[0] + w[1] - w[2]) < 0.015, (vint, y, got.get(y))
    assert "due to adjustment of Life Assurance Benefit (Rs. 0.35 Cr)" in pdf_page_text("epfo_annual_report_2024_25.pdf", 41)
    gaps = {y: round(val("epfo_ar", "fiveyear.eps_payment.current", y, "2026-02") - EPS_TABLE5["2026-02"][2][y][2], 2)
            for y in ("2020-21", "2021-22", "2022-23", "2023-24", "2024-25")}
    assert gaps == {"2020-21": 38.03, "2021-22": 382.46, "2022-23": 315.97, "2023-24": 371.23, "2024-25": -0.35}


def test_v13_notes_cite_eps_outgo_split():
    """V13 fixed (final pass; was a strict xfail): the AR 2024-25 App. 5(i) and para 5.5 notes call the EPS payment
    pensions AND withdrawal benefits, cite Table 5 and its 0.35 reconciliation, give 27,581.53 as the alternative for
    total EPS payments (not pensions), log the earlier-year excess and say 19.4%. The AR 2023-24 App. 5(i) note gives
    its own 371.23 gap. Every number is re-derived here from the raw pages (positional reads), not copied."""
    _, t5 = eps_outgo_positional("2026-02")
    _, t5_old = eps_outgo_positional("2024-12")
    _, _, pos = app5i_positional("2026-02")
    _, _, pos3 = app5i_positional("2024-12")
    eps_pay, eps_pay3 = pos[APP5I_COLS.index("eps_payment")], pos3[APP5I_COLS.index("eps_payment")]
    pen, wd, tot = t5["2024-25"]
    assert (pen, wd, tot) == (18957.86, 9005.90, 27963.76) and round(tot - eps_pay, 2) == 0.35
    p41 = pdf_page_text("epfo_annual_report_2024_25.pdf", 41)
    assert "due to adjustment of Life Assurance Benefit (Rs. 0.35 Cr)" in p41
    gap23 = round(eps_pay3 - t5_old["2023-24"][2], 2)
    assert gap23 == 371.23
    for pfx in ("app5i.", "fiveyear."):
        (n,) = prov_notes("epfo_ar", vintage="2026-02", series_id=pfx)
        assert "18,957.86" in n and "9,005.90" in n and "27,963.76" in n and "0.35 Life Assurance Benefit" in n, pfx
        assert "pensions AND withdrawal benefits" in n and "Table 5" in n and "PDF pp.40-41" in n, pfx
        assert "EPS pensions paid in 2024-25 lie between" not in n and "EPS pensions" not in n, pfx
        assert "total EPS payments 2024-25 are 27,581.53" in n and close(round(eps_pay - 381.88, 2), 27581.53), pfx
        assert "38-382 cr (371.23 in 2023-24)" in n, pfx
        assert "rises 19.4%" in n and "19.5%" not in n, pfx
    (n3,) = prov_notes("epfo_ar", vintage="2024-12", series_id="app5i.")
    for s in ("15,130.68", "7,908.25", "23,038.94", "23,410.17", "by 371.23", "PDF p.39",
              "pensions and withdrawal benefits"):
        assert s in n3, s
    assert close(eps_pay3, 23410.17) and t5_old["2023-24"] == (15130.68, 7908.25, 23038.94)


def test_v14_raw_app5i_eps_contribution_is_employers_share_only():
    """V14 (raw fact): App. 5(i) 'Total EPS contribution' equals para 5.4's EMPLOYERS' share, and 'Total
    contribution' = EPF + EPS employers' share + EDLI; the Central Government's EPS share (9,356.48 in 2023-24,
    10,049.70 in 2024-25) is in neither."""
    for vint, fy in (("2024-12", "2023-24"), ("2026-02", "2024-25")):
        a = {c: val("epfo_ar", f"app5i.{c}.current", fy, vint) for c in APP5I_COLS}
        emp = val("epfo_ar", "para54.eps_contribution_employer.current", fy, vint)
        gov = val("epfo_ar", "para54.eps_contribution_government.current", fy, vint)
        assert close(a["eps_contribution"], emp) and gov > 9000
        assert abs(a["total_contribution"] - a["epf_contribution"] - emp - a["edli_contribution"]) < 0.015


def test_v14_notes_say_government_share_excluded():
    """V14 fixed (final pass; was a strict xfail): both App. 5(i) notes and the AR 2024-25 para 5.5 note say that
    'Total EPS contribution' is the employers' share only and 'Total contribution' = EPF + that + EDLI, excluding the
    Central Government's EPS share. The shares are re-read from the raw para 5.4 page and App. 5(i) positional read."""
    for vint, fy, pfxs in (("2024-12", "2023-24", ("app5i.",)), ("2026-02", "2024-25", ("app5i.", "fiveyear."))):
        raw = epfo_values(vint)  # pdfplumber para 5.4
        emp = raw[("para54.eps_contribution_employer.current", fy)]
        gov = raw[("para54.eps_contribution_government.current", fy)]
        assert close(emp + gov, raw[("para54.eps_contribution_total.current", fy)])  # 'Total:' in para 5.4 is both
        _, _, pos = app5i_positional(vint)
        assert close(pos[APP5I_COLS.index("eps_contribution")], emp)  # App. 5(i) 'Total EPS contribution' = employers'
        epf, edli = pos[APP5I_COLS.index("epf_contribution")], pos[APP5I_COLS.index("edli_contribution")]
        assert abs(pos[APP5I_COLS.index("total_contribution")] - epf - emp - edli) < 0.015
        for pfx in pfxs:
            (n,) = prov_notes("epfo_ar", vintage=vint, series_id=pfx)
            assert re.search(r"Gov\w*\.?'?s? share", n) and re.search(r"exclud|not includ|without", n), (vint, pfx)
            assert _indian(emp) in n, (vint, pfx, emp)
            assert _indian(gov) in n and "para54.eps_contribution_government" in n, (vint, pfx, gov)
            assert "exclude the Central Government's share of EPS" in n and "despite the word 'Total'" in n, (vint, pfx)


def _indian(x: float) -> str:
    """1234567.8 -> '12,34,567.80' (Indian digit grouping, as printed in the reports)."""
    s = f"{x:.2f}"
    whole, frac = s.split(".")
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join([*groups, tail]) + "." + frac


# ------------------------------------------------------------------------------------------------
# Final pass (2026-09-29): the new dataset epfo_eps_outgo (EPS outgo split, 30 rows), independently re-derived
# ------------------------------------------------------------------------------------------------

EPS_OUTGO_PAGES = {"2024-12": (39,), "2026-02": (40, 41)}
EPS_OUTGO_FYS = {"2024-12": [f"{y}-{(y + 1) % 100:02d}" for y in range(2019, 2024)],
                 "2026-02": [f"{y}-{(y + 1) % 100:02d}" for y in range(2020, 2025)]}


def test_final_eps_outgo_pages_completeness_and_identities():
    """The header line is found only on the pages the provenance locator names; every published cell has exactly one
    clean row and every clean row one published cell; Pension Disbursed + Withdrawal Benefits = Total; the two vintages
    print the same values in 2020-21..2023-24; the positional read equals the close-out text read (`eps_table5`)."""
    df = clean("epfo_eps_outgo")
    assert df.height == 30
    for vint, want_pages in EPS_OUTGO_PAGES.items():
        pages, t = eps_outgo_positional(vint)
        assert pages == want_pages, (vint, pages)
        (loc,) = prov().filter(pl.col("prov_id").is_in(df.filter(pl.col("vintage") == vint)["prov_id"].unique()
                                                        .to_list()))["locator"].to_list()
        assert loc.startswith("PDF page(s) " + ", ".join(map(str, want_pages)) + " "), (vint, loc)
        assert list(t) == EPS_OUTGO_FYS[vint], (vint, list(t))
        mine = {(c, fy) for fy in t for c in EPS_OUTGO_COLS}
        d = df.filter(pl.col("vintage") == vint)
        theirs = list(zip(d["item_code"].to_list(), d["period"].to_list(), strict=True))
        assert len(theirs) == len(set(theirs)) and set(theirs) == mine, (vint, mine ^ set(theirs))
        for fy, (pen, wd, tot) in t.items():
            assert abs(pen + wd - tot) < 0.015, (vint, fy)
        assert t == eps_table5(vint) == EPS_TABLE5[vint][2], vint
    _, old = eps_outgo_positional("2024-12")
    _, new = eps_outgo_positional("2026-02")
    assert all(old[fy] == new[fy] for fy in ("2020-21", "2021-22", "2022-23", "2023-24"))
    # all official, Rs crore; only the report year of each vintage is flagged 'Unaudited' (report-wide convention:
    # para 5.4 '*Unaudited' / '*The provided figures are un-audited'; the outgo table itself prints no audit mark)
    assert set(df["status"].to_list()) == {"official"} and set(df["unit"].to_list()) == {"INR_crore"}
    for r in df.iter_rows(named=True):
        rfy = EPFO_REPORTS[r["vintage"]][1]
        assert r["estimate_stage"] == ("Unaudited" if r["period"] == rfy else "n.a."), (r["vintage"], r["period"])


def test_final_eps_outgo_note_numbers_and_quotes_rederived():
    """Every number and quote in the epfo_eps_outgo notes, recomputed from the raw pages."""
    _, new = eps_outgo_positional("2026-02")
    df = clean("epfo_eps_outgo")
    notes = {v: prov_notes("epfo_eps_outgo", vintage=v) for v in EPS_OUTGO_PAGES}
    assert all(len(n) == 1 for n in notes.values())
    n_old, n_new = notes["2024-12"][0], notes["2026-02"][0]
    # EPS payment (para 5.5 of AR 2024-25; census-verified clean rows) minus the outgo total, per FY
    gaps = {fy: round(val("epfo_ar", "fiveyear.eps_payment.current", fy, "2026-02") - new[fy][2], 2) for fy in new}
    assert gaps == {"2020-21": 38.03, "2021-22": 382.46, "2022-23": 315.97, "2023-24": 371.23, "2024-25": -0.35}
    for n in (n_old, n_new):
        for fy, g in gaps.items():
            want = f"{abs(g):.2f}" + ("" if fy in ("2023-24", "2024-25") else f" ({fy})")
            assert want in n, (fy, g)
        assert "identical values for the overlapping years 2020-21..2023-24" in n
        assert ("on exit from service or on superannuation, provided the member has not rendered service eligible for "
                "pension") in n
    # 'Pension Disbursed rises 25.3% from 2023-24 (15,130.68 to 18,957.86)'
    assert round(100 * (new["2024-25"][0] / new["2023-24"][0] - 1), 1) == 25.3 and "rises 25.3%" in n_new
    ar25 = "epfo_annual_report_2024_25.pdf"
    quotes = [(ar25, 41, "The total outgo Rs. 27,963.76 Cr shown above is slightly different from figure given in "
               "Balance Sheet (Rs. 27,963.41) due to adjustment of Life Assurance Benefit (Rs. 0.35 Cr) entry in "
               "Balance Sheet."),
              (ar25, 36, "Withdrawal benefit on exit from service or on superannuation, "
               "provided the member has not rendered service eligible for pension."),
              (ar25, 46, "Table D i.e, Return of contribution on exit from employment has been amended vide GSR 326 "
               "(E) dated 14.06.2024. Now withdrawal benefits are available even for 1 month contribution"),
              (ar25, 40, "Table 5:Employee’sPension Fund outgo distribution financial year wise."),
              ("epfo_annual_report_2023_24.pdf", 39, "2.15 EPS Fund - Receipts, Payments and Corpus"),
              ("epfo_annual_report_2023_24.pdf", 39, "EPS Payments ( Rs. in crores )")]
    for name, page, s in quotes:
        assert s in pdf_page_text(name, page), (name, page, s[:60])
    for s in ("The total outgo Rs. 27,963.76 Cr", "(Rs. 27,963.41)", "PDF p.46", "GSR 326 (E) dated 14.06.2024"):
        assert s in n_new, s
    # AR 2023-24 prints the definition without the comma and 'the' (the notes quote AR 2024-25's wording for both)
    assert ("Withdrawal benefit on exit from service or on superannuation provided member has not rendered service "
            "eligible for pension") in pdf_page_text("epfo_annual_report_2023_24.pdf", 37)
    assert df.filter(pl.col("vintage") == "2026-02")["table_id"].unique().to_list() == [
        "Table 5 (para 2.16, Employee's Pension Fund outgo distribution financial year wise)"]
