"""Report on Trend and Progress of Banking in India (RTP): income-and-expenditure tables by lender group.

The substitute for STRBI (DBIE-only, manual) chosen per the access checker: the chapter HTML pages
(not the appendix, which has no bank-group P&L) of two editions on www.rbi.org.in:
- RTP 2024-25 (29 Dec 2025): 2023-24 and 2024-25 columns (some tables also 2022-23).
- RTP 2023-24 (26 Dec 2024): 2022-23 and 2023-24 columns (some tables from 2021-22).
Each table is found by its title (table numbers differ between editions), rows are matched by
normalised label and every level row must be mapped; the ratio blocks under the levels are not
ingested except where listed. Half-year columns (H1) and variation/growth columns are skipped.

Tables: SCB income and expenditure by bank group, SCB balance sheet by bank group, cost and return
of funds by bank group, RRBs, LABs, SFBs, payments banks, urban co-operative banks, StCBs, DCCBs,
NBFC sector (all/UL/ML), NBFC-UL and NBFC-ML detail (appendix VI.6/VI.7), NBFC ownership, HFCs,
AIFIs, standalone primary dealers.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pipeline.core.unit import BuildContext, RawFile
from pipeline.core.units import clean_label, normalize_fy, parse_number

from . import _html as H

SRC = "rbi_trend_progress"
LANDING = "https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Trend%20and%20Progress%20of%20Banking%20in%20India"
URL = "https://www.rbi.org.in/Scripts/PublicationsView.aspx?id={id}"


@dataclass(frozen=True)
class Page:
    edition: str  # 'rtp2425' | 'rtp2324'
    part: str  # 'ch4', 'ch5', 'ch6', 'app_vi_6', 'app_vi_7'
    page_id: int
    heading: str  # printed heading, checked at build

    @property
    def name(self) -> str:
        return f"{self.edition}_{self.part}.html"

    @property
    def url(self) -> str:
        return URL.format(id=self.page_id)


EDITIONS = {
    "rtp2425": ("2025-12-29", "Report on Trend and Progress of Banking in India 2024-25 (RBI, 29 Dec 2025)"),
    "rtp2324": ("2024-12-26", "Report on Trend and Progress of Banking in India 2023-24 (RBI, 26 Dec 2024)"),
}
PAGES = (
    Page("rtp2425", "ch4", 23639, "Commercial Banks"),
    Page("rtp2425", "ch5", 23640, "Co-operative Banks"),
    Page("rtp2425", "ch6", 23641, "Non-Banking Financial Institutions"),
    Page("rtp2425", "app_vi_6", 23677, "Appendix Table VI.6: Financial Performance of NBFC-UL"),
    Page("rtp2425", "app_vi_7", 23678, "Appendix Table VI.7: Financial Performance of NBFC-ML"),
    Page("rtp2324", "ch4", 23075, "Operations and Performance of Commercial Banks"),
    Page("rtp2324", "ch5", 23076, "Developments in Co-operative Banking"),
    Page("rtp2324", "ch6", 23077, "Non-Banking Financial Institutions"),
    Page("rtp2324", "app_vi_6", 23113, "Appendix Table VI.6: Financial Performance of NBFC-UL"),
    Page("rtp2324", "app_vi_7", 23114, "Appendix Table VI.7: Financial Performance of NBFC-ML"),
)

# Lender-group column headers -> institution code (documented slugs; see the issues file).
GROUPS = {
    "psbs": "psb", "public sector banks": "psb",
    "pvbs": "pvb", "private sector banks": "pvb",
    "fbs": "fb", "foreign banks": "fb",
    "sfbs": "sfb", "small finance banks": "sfb",
    "pbs": "pb", "payments banks": "pb",
    "scbs": "scb", "all scbs": "scb", "scheduled commercial banks": "scb", "all scheduled commercial banks": "scb",
    "scheduled ucbs": "ucb_scheduled", "non-scheduled ucbs": "ucb_nonscheduled", "all ucbs": "ucb",
    "nbfcs": "nbfc", "nbfc-ul": "nbfc_ul", "nbfc-ml": "nbfc_ml", "nbfc-sector": "nbfc", "nbfc sector": "nbfc",
}

# Row kinds: F = flow (Rs crore), S = stock at end of the fiscal year (Rs crore), A = average of
# stocks over the year (Rs crore), P = per cent.
F, S, A, P = "flow", "stock", "avg", "pct"


@dataclass(frozen=True)
class Spec:
    key: str  # stable table key used in series_id (table numbers differ between editions)
    title_re: str  # matched against the caption row (after 'Table X.n: ') or the page heading
    parts: tuple[str, ...]  # which page parts carry it
    items: dict[str, tuple[str, str]]  # normalised label -> (item_code, kind)
    institution: str | None = None  # single-group tables
    stop: tuple[str, ...] = ("financial ratios", "analytical ratios", "cost to income ratio")
    headers: tuple[str, ...] = ()  # normalised labels of rows allowed to be blank (section headers)
    in_page_title: bool = False  # appendix pages: the table has no caption row, the page heading is the title
    min_years: int = 2
    paren_suffix: str | None = None  # meaning of '(1,234)' rows under a level row, if the note gives one
    paren_note: str = ""  # regex the table note must match for paren_suffix to apply


def _items(**kw: tuple[str, str]) -> dict[str, tuple[str, str]]:
    return kw


_PL_BANK = {
    "income": ("income_total", F), "interest income": ("interest_income", F), "other income": ("other_income", F),
    "expenditure": ("expenditure_total", F), "interest expended": ("interest_expended", F),
    "operating expenses": ("operating_expenses", F), "wage bill": ("wage_bill", F),
    "provisions and contingencies": ("provisions_contingencies", F),
    "operating profit": ("operating_profit", F), "net profit": ("net_profit", F),
}

SPECS: tuple[Spec, ...] = (
    Spec("scb_pl", r"Trends in Income and Expenditure of Scheduled Commercial Banks$", ("ch4",), {
        **_PL_BANK,
        "provision and contingencies": ("provisions_contingencies", F),
        "net interest income (nii)": ("net_interest_income", F),
        "net interest margin (nim)": ("nim", P),
    }, stop=()),
    Spec("scb_bs", r"Consolidated Balance Sheet of Scheduled Commercial Banks$", ("ch4",), {
        "capital": ("capital", S), "reserve and surplus": ("reserves_surplus", S), "reserves and surplus": ("reserves_surplus", S),
        "deposits": ("deposits", S), "demand deposits": ("deposits_demand", S),
        "savings bank deposits": ("deposits_savings", S), "term deposits": ("deposits_term", S),
        "borrowings": ("borrowings", S), "other liabilities and provisions": ("other_liabilities_provisions", S),
        "total liabilities/assets": ("total_liabilities_assets", S),
        "cash and balances with rbi": ("cash_balances_rbi", S),
        "balances with banks and money at call and short notice": ("balances_banks_call_money", S),
        "investments": ("investments", S), "in government securities": ("inv_gsec", S),
        "in india": ("inv_gsec_in_india", S), "outside india": ("inv_gsec_outside_india", S),
        "other approved securities": ("inv_other_approved", S), "non-approved securities": ("inv_non_approved", S),
        "loans and advances": ("loans_advances", S), "bills purchased and discounted": ("loans_bills", S),
        "cash credits, overdrafts, etc.": ("loans_cash_credit_overdraft", S), "term loans": ("loans_term", S),
        "fixed assets": ("fixed_assets", S), "other assets": ("other_assets", S),
    }, stop=(), headers=("liabilities", "assets"), paren_suffix="_excl_merger",
       paren_note=r"data in parentheses exclude the impact of the merger of a non-bank with a bank"),
    Spec("rrb_pl", r"Financial Performance of Regional Rural Banks$", ("ch4",), {
        **_PL_BANK, "income tax": ("income_tax", F), "total average assets": ("average_total_assets", A),
    }, institution="rrb", headers=("profit",)),
    Spec("lab_pl", r"Financial Performance of Local Area Banks$", ("ch4",), {
        **_PL_BANK, "net interest income": ("net_interest_income", F),
        "operating profit/loss": ("operating_profit", F), "net profit/loss": ("net_profit", F),
        "total assets": ("total_assets", S),
    }, institution="lab", headers=("profit",)),
    Spec("sfb_pl", r"Financial Performance of Small Finance Banks$", ("ch4",), {
        **_PL_BANK,
        # RTP 2023-24 prints 'Staff Expenses' where RTP 2024-25 prints 'Wage Bill' (same line, same values)
        "staff expenses": ("wage_bill", F), "profit (before tax)": ("profit_before_tax", F),
        "operating profit (ebpt)": ("operating_profit", F), "net profit (pat)": ("net_profit", F),
        "total assets": ("total_assets", S),
    }, institution="sfb", headers=("profit",)),
    Spec("pb_pl", r"Financial Performance of Payments Banks$", ("ch4",), {
        "income": ("income_total", F), "interest income": ("interest_income", F),
        "non-interest income": ("non_interest_income", F),
        "expenditure": ("expenditure_total", F), "interest expended": ("interest_expended", F),
        "interest expenses": ("interest_expended", F), "operating expenses": ("operating_expenses", F),
        "provisions and contingencies": ("provisions_contingencies", F),
        "risk provisions": ("risk_provisions", F), "tax provisions": ("tax_provisions", F),
        "net interest income": ("net_interest_income", F),
        "operating profit": ("operating_profit", F), "operating profit (ebpt)": ("operating_profit", F),
        "net profit": ("net_profit", F), "net profit/loss": ("net_profit", F),
    }, institution="pb", headers=("income", "expenditure", "profit", "of which,", "")),
    Spec("ucb_pl", r"Financial Performance of Scheduled and Non-scheduled Urban Co-operative Banks$", ("ch5",), {
        "total income": ("income_total", F), "interest income": ("interest_income", F),
        "non-interest income": ("non_interest_income", F),
        "total expenditure": ("expenditure_total", F), "interest expenditure": ("interest_expended", F),
        "non-interest expenditure": ("non_interest_expenditure", F), "staff expenses": ("staff_expenses", F),
        "operating profits": ("operating_profit", F), "provision and contingencies": ("provisions_contingencies", F),
        "provisions and contingencies": ("provisions_contingencies", F),
        "provision for taxes": ("tax_provisions", F), "provisions for taxes": ("tax_provisions", F),
        "net profit before taxes": ("profit_before_tax", F), "net profit after taxes": ("net_profit", F),
        "amount of operating profits": ("operating_profit", F),
        "amount of net profit before taxes": ("profit_before_tax", F),
        "amount of net profit after taxes": ("net_profit", F),
    }, headers=("profits",)),
    Spec("stcb_pl", r"Financial Performance of State Co-operative Banks$", ("ch5",), {
        **_PL_BANK, "net interest income": ("net_interest_income", F), "operating profits": ("operating_profit", F),
        "net profits": ("net_profit", F),
    }, institution="stcb", headers=("profits",)),
    Spec("dccb_pl", r"Financial Performance of District Central Co-operative Banks$", ("ch5",), {
        **_PL_BANK, "net interest income": ("net_interest_income", F), "operating profits": ("operating_profit", F),
        "net profits": ("net_profit", F),
    }, institution="dccb", headers=("profits",)),
    Spec("nbfc_pl", r"Financial Parameters of the NBFC Sector$", ("ch6",), {
        "income": ("income_total", F), "expenditure": ("expenditure_total", F), "net profit": ("net_profit", F),
        "total assets": ("total_assets", S),
    }),
    Spec("nbfc_layer_pl", r"^Appendix Table VI\.[67]: Financial Performance of NBFC-(UL|ML)$", ("app_vi_6", "app_vi_7"), {
        "total income": ("income_total", F), "fund based income": ("fund_based_income", F),
        "fee based income": ("fee_based_income", F), "expenditure": ("expenditure_total", F),
        "financial expenditure": ("financial_expenditure", F), "interest payment": ("interest_payment", F),
        "operating expenditure": ("operating_expenditure", F), "others": ("other_expenditure", F),
        "tax provisions": ("tax_provisions", F), "profit before tax": ("profit_before_tax", F),
        "net profit": ("net_profit", F), "total assets": ("total_assets", S),
    }, in_page_title=True),
    Spec("hfc_pl", r"Financial Parameters of HFCs$", ("ch6",), {
        "total income": ("income_total", F), "fund income": ("fund_income", F), "fee income": ("fee_income", F),
        "total expenditure": ("expenditure_total", F), "financial expenditure": ("financial_expenditure", F),
        "operating expenditure": ("operating_expenditure", F), "tax provision": ("tax_provisions", F),
        "net profit (pat)": ("net_profit", F), "total assets": ("total_assets", S),
    }, institution="hfc"),
    Spec("aifi_pl", r"Financial Performance of AIFIs$", ("ch6",), {
        "income": ("income_total", F), "interest income": ("interest_income", F),
        "non-interest income": ("non_interest_income", F), "expenditure": ("expenditure_total", F),
        "interest expenditure": ("interest_expended", F), "operating expenses": ("operating_expenses", F),
        "wage bill": ("wage_bill", F), "for taxation": ("tax_provisions", F),
        "provisions for taxation": ("tax_provisions", F), "for contingencies": ("provisions_contingencies", F),
        "operating profit (pbt)": ("profit_before_tax", F), "net profit (pat)": ("net_profit", F),
    }, institution="aifi", headers=("provisions", "profit")),
    Spec("spd_pl", r"Financial Performance of SPDs$", ("ch6",), {
        "income": ("income_total", F), "interest and discount": ("interest_discount", F),
        "trading profits": ("trading_profits", F), "other income": ("other_income", F),
        "expenses": ("expenses_total", F), "interest": ("interest_expended", F),
        "other": ("other_expenses", F),
        "other expenses including establishment and administrative costs": ("other_expenses", F),
        "profit before tax": ("profit_before_tax", F), "profit after tax": ("net_profit", F),
        "average assets": ("average_assets", A),
    }, institution="spd"),
)


# ---------------------------------------------------------------------------------------------
# column headers
# ---------------------------------------------------------------------------------------------

_SKIP_COL = re.compile(r"variation|growth|y-o-y|change", re.I)
_YEAR = re.compile(r"(?<!\d)(\d{4})\s*[-–]\s*(\d{2})(?!\d)")
_ANY_YEAR = re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)")
_END_MARCH = re.compile(r"^(\d{4})(\s*P)?$")


@dataclass(frozen=True)
class Col:
    idx: int
    institution: str | None
    period: str  # fiscal year (for end-March stock columns: the fiscal year that ends then)
    provisional: bool
    header: str


def _columns(headers: list[H.Header], spec: Spec, label_cols: int) -> list[Col]:
    cols: list[Col] = []
    for i, h in enumerate(headers):
        parts = [p for p in dict.fromkeys(h.parts) if p]
        text = " | ".join(parts)
        if _SKIP_COL.search(text):
            continue  # variation / growth columns: arithmetic on the levels
        if re.search(r"(?<![A-Za-z])H[12](?![0-9])", text):
            continue  # half-year columns: not a fiscal year (see module docstring)
        years = [p for p in parts if _YEAR.search(p)]
        ends = [p for p in parts if _END_MARCH.match(p)]
        if len(years) == 1 and not ends:
            fy = normalize_fy(years[0])
            ypart = years[0]
        elif len(ends) == 1 and not years:  # '(At end-March)' balance-sheet columns: '2024'
            y = int(_END_MARCH.match(ends[0]).group(1))  # type: ignore[union-attr]
            fy, ypart = f"{y - 1}-{y % 100:02d}", ends[0]
        else:
            raise ValueError(f"{spec.key}: column header {text!r} has no single year part")
        prov = bool(re.search(r"\(P\)|(?<![A-Za-z])P(?![A-Za-z])", ypart))
        others = [p for p in parts if p != ypart and not re.search(r"^amount", p, re.I) and p.lower() not in ("item", "items")]
        inst = spec.institution
        if others:
            if len(others) != 1:
                raise ValueError(f"{spec.key}: column header {text!r}: cannot tell the lender group")
            g = others[0].lower()
            if g not in GROUPS:
                raise ValueError(f"{spec.key}: unknown lender group {others[0]!r}")
            inst = GROUPS[g]
        if inst is None:
            raise ValueError(f"{spec.key}: no lender group for column {text!r}")
        cols.append(Col(label_cols + i, inst, fy, prov, text))
    return cols


def _is_value(text: str) -> bool:
    t = text.strip()
    return bool(re.fullmatch(r"-?[\d,]+(\.\d+)?", t)) and not re.fullmatch(r"(19|20)\d{2}", t)


def _note(rows: list[list[str]]) -> str:
    return " ".join(r[0] for r in rows if H.is_note_row(r))


def _audited_source(note: str) -> bool:
    """True when the table's printed 'Source(s):' line names only banks' annual accounts / balance sheets
    (optionally with RBI staff calculations on them). A table that also cites off-site or supervisory
    returns, NABARD, etc. is not wholly audited, so its stage stays 'n.a.' (e.g. SFB P&L: RTP 2024-25
    Table IV.37 cites 'Annual accounts of banks; and off-site returns', RTP 2023-24 Table IV.38 cites
    only off-site returns; both are 'n.a.')."""
    srcs = re.findall(r"Sources?:\s*(.+?)(?=$|Notes?:)", note, re.I)
    if not srcs:
        return False
    src = srcs[-1]
    accounts = re.search(r"annual accounts of (?:respective )?banks|balance sheets of (?:respective )?banks", src, re.I)
    other = re.search(r"off-site|returns|nabard|supervisory|institutions", src, re.I)
    return bool(accounts) and not other


def _stage(note: str, col: Col) -> str:
    if col.provisional:
        return "Provisional"
    m = re.search(r"data (?:are|is) provisional for (\d{4}-\d{2})|data for (\d{4}-\d{2}) are provisional", note, re.I)
    if m:
        return "Provisional" if (m.group(1) or m.group(2)) == col.period else "n.a."
    if re.search(r"data are provisional", note, re.I):
        return "Provisional"
    if _audited_source(note):
        return "Audited"
    return "n.a."


# ---------------------------------------------------------------------------------------------
# generic level table
# ---------------------------------------------------------------------------------------------


def _parse_level_table(ctx: BuildContext, raw: RawFile, page: Page, spec: Spec, doc: Any) -> list[dict[str, Any]]:
    vintage, release = EDITIONS[page.edition]
    if spec.in_page_title:
        _, heading = H.page_heading(H.soup(raw.path))
        m = re.search(spec.title_re, heading)
        if not m:
            raise ValueError(f"{page.name}: heading {heading!r} does not match {spec.title_re}")
        caption = heading
        tables = [H.grid(t) for t in doc.find_all("table")]
        cand = [g for g in tables if g and g[0][0].startswith("(") and "crore" in g[0][0] and len(g[0][0]) < 40]
        if len(cand) != 1:
            raise ValueError(f"{page.name}: expected one data table, found {len(cand)}")
        g = cand[0]
        inst_override = "nbfc_" + m.group(1).lower()
    else:
        caption, g = H.find_table(doc, r"^Table [IVX]+\.\d+:\s*" + spec.title_re.lstrip("^"))
        inst_override = None
    table_id = caption.split(":")[0].strip()
    # unit caption: '(Amount in Rs crore)' / '(Rs crore)' in the rows above the header, or 'Amount (in Rs crore)' in the header
    head_rows = [r for r in g[:6] if len(set(r)) == 1]
    first_hdr = next(i for i, r in enumerate(g) if len(set(r)) > 1)
    captions = " ".join(r[0] for r in head_rows) + " " + " ".join(g[first_hdr])
    if "crore" not in captions:
        raise ValueError(f"{page.name} {table_id}: no crore unit caption found ({captions[:200]!r})")
    # header rows end at the column-number row ('1 | 2 | ...') or, where a table has none, at the
    # first row that carries a non-year number
    ncol = len(g[0])
    num_row = next((i for i in range(first_hdr, len(g)) if g[i][0].strip() == "1"), None)
    if num_row is not None:
        hdr_end, data = num_row, g[num_row + 1 :]
    else:
        hdr_end = next((i for i in range(first_hdr + 1, len(g)) if any(_is_value(x) for x in g[i][1:])), None)
        if hdr_end is None:
            raise ValueError(f"{page.name} {table_id}: cannot find the first data row")
        data = g[hdr_end:]
    # label columns = leading columns whose header carries no year
    label_cols = 0
    for c in range(ncol):
        if any(_ANY_YEAR.search(g[r][c]) for r in range(first_hdr, hdr_end)):
            break
        label_cols += 1
    headers = [H.Header(tuple(g[r][c] for r in range(first_hdr, hdr_end))) for c in range(label_cols, ncol)]
    spec_i = spec if inst_override is None else Spec(**{**spec.__dict__, "institution": inst_override})
    cols = _columns(headers, spec_i, label_cols)
    if len({c.period for c in cols}) < spec.min_years:
        raise ValueError(f"{page.name} {table_id}: only {len(cols)} usable columns: {[c.header for c in cols]}")
    note = _note(g)
    paren_meaning = None
    if spec.paren_suffix and re.search(spec.paren_note, note, re.I):
        paren_meaning = spec.paren_suffix
    prov: dict[str, str] = {}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    last: tuple[str, str, str] | None = None  # (code, kind, label) of the previous level row

    def emit(code: str, kind: str, label: str, c: Col, x: float, variant: str = "") -> None:
        unit_pub = "per cent" if kind == P else "Rs crore"
        pkey = unit_pub + variant
        if pkey not in prov:
            what = ("per cent rows" if kind == P else "amount rows") + (
                f"; figures in parentheses ({variant.strip('_').replace('_', ' ')}, per the table note)" if variant else "")
            prov[pkey] = ctx.prov(
                raw=raw,
                table_id=table_id,
                locator=(f"{page.url} ({page.edition} {page.part} HTML), '{caption}', {what}, matched by label; "
                         f"columns {', '.join(dict.fromkeys(c2.header for c2 in cols))}"),
                unit_as_published=unit_pub,
                conversion="none",
                price_basis="n/a" if kind == P else "current",
                vintage=vintage,
                release=release,
                notes=f"Table note: {note[:400]}" if variant else None,
            )
        if kind == S:
            period, ptype, sf = f"{int(c.period[:4]) + 1}-03-31", "date", "stock"
        else:
            period, ptype, sf = c.period, "fy", ("flow" if kind == F else "n/a")
        out.append({
            "series_id": f"rtp.{spec.key}.{code}{variant}.{c.institution}" + ("" if kind == P else ".current"),
            "source_id": SRC,
            "table_id": table_id,
            "item_code": code + variant,
            # The merger-excluded figure is printed in parentheses under the level row and has no label of
            # its own; the row label is the printed one plus the table note's meaning, and the scope is also
            # carried in dim_other so it can be filtered on without parsing the label.
            "item_label": clean_label(label) + (f" ({variant.strip('_').replace('_', ' ')})" if variant else ""),
            "institution": c.institution,
            "geography": "IN",
            "dim_other": f"scope={variant.strip('_')}" if variant else None,
            "stock_flow": sf,
            "period": period,
            "period_type": ptype,
            "value": x,
            "unit": "percent" if kind == P else "INR_crore",
            "price_basis": "n/a" if kind == P else "current",
            "vintage": vintage,
            "estimate_stage": _stage(note, c),
            "status": "official",
            "prov_id": prov[pkey],
        })

    for row in data:
        if H.is_note_row(row):
            break
        label = next((x for x in reversed(row[:label_cols]) if x.strip()), "")
        vals = [row[c.idx] for c in cols]
        nl = H.norm_label(label)
        if spec.stop and any(nl.startswith(s) for s in spec.stop):
            break
        if not label.strip() or nl == "":
            cells = row[label_cols:]
            if all(not v.strip() or H.is_growth_cell(v) or v.strip() == "-" for v in cells):
                if paren_meaning and last is not None and any(H.is_growth_cell(v) for v in vals):
                    for c, v in zip(cols, vals, strict=True):
                        if H.is_growth_cell(v):
                            emit(last[0], last[1], last[2], c, abs(parse_number(v) or 0.0), paren_meaning)
                continue  # growth / share row printed under a level row
            if nl not in spec.headers:
                raise ValueError(f"{page.name} {table_id}: unlabelled row with values {row}")
        if all(not v.strip() for v in vals):
            if nl in spec.headers or nl in spec.items:
                continue
            raise ValueError(f"{page.name} {table_id}: unexpected blank row {label!r}")
        item = spec.items.get(nl)
        if item is None:
            raise ValueError(f"{page.name} {table_id}: unmapped row label {label!r} (normalised {nl!r})")
        code, kind = item
        if code in seen:
            raise ValueError(f"{page.name} {table_id}: row {code} appears twice")
        seen.add(code)
        last = (code, kind, label)
        for c, v in zip(cols, vals, strict=True):
            if H.is_growth_cell(v):
                raise ValueError(f"{page.name} {table_id}: parenthesised value {v!r} in a level row {label!r}")
            x = parse_number(v)
            if x is None:
                continue  # published blank or '-': no row
            emit(code, kind, label, c, x)
    if not seen:
        raise ValueError(f"{page.name} {table_id}: no rows parsed")
    return out


# ---------------------------------------------------------------------------------------------
# special layouts
# ---------------------------------------------------------------------------------------------

COST_COLS = {
    "cost of deposits": "cost_of_deposits", "cost of borrowings": "cost_of_borrowings", "cost of funds": "cost_of_funds",
    "return on advances": "return_on_advances", "return on investments": "return_on_investments",
    "return on funds": "return_on_funds", "spread (columns 8-5)": "spread",
}


def _cost_of_funds(ctx: BuildContext, raw: RawFile, page: Page, doc: Any) -> list[dict[str, Any]]:
    """'Cost of Funds and Return on Funds - Bank Group-wise': rows = group x year, columns = rates."""
    vintage, release = EDITIONS[page.edition]
    caption, g = H.find_table(doc, r"^Table IV\.\d+: Cost of Funds and Return on Funds")
    table_id = caption.split(":")[0].strip()
    if "Per cent" not in g[1][0]:
        raise ValueError(f"{page.name} {table_id}: caption {g[1][0]!r}")
    hdr = g[2]
    if [hdr[0], hdr[1]] != ["Bank Group", "Year"]:
        raise ValueError(f"{page.name} {table_id}: header {hdr}")
    codes = []
    for h in hdr[2:]:
        k = H.norm_label(h)
        if k.startswith("spread"):  # 'Spread (columns 8-5)' / 'Spread (Column 8 - Column 5)'
            k = "spread (columns 8-5)"
        if k not in COST_COLS:
            raise ValueError(f"{page.name} {table_id}: unknown column {h!r}")
        codes.append((COST_COLS[k], h))
    pid = ctx.prov(raw=raw, table_id=table_id,
                   locator=f"{page.url} ({page.edition} {page.part} HTML), '{caption}', all group x year rows, columns 3-9",
                   unit_as_published="per cent", conversion="none", price_basis="n/a", vintage=vintage, release=release)
    note = _note(g)
    if not re.search(r"Sources?:", note):
        raise ValueError(f"{page.name} {table_id}: no printed source line in the note ({note[-200:]!r})")
    stage = "Audited" if _audited_source(note) else "n.a."
    out, group = [], None
    num_row = next(i for i in range(3, len(g)) if g[i][0] == "1")
    for row in g[num_row + 1 :]:
        if H.is_note_row(row):
            break
        if row[0].strip():
            k = row[0].strip().lower()
            if k not in GROUPS:
                raise ValueError(f"{page.name} {table_id}: unknown group {row[0]!r}")
            group = GROUPS[k]
        if group is None:
            raise ValueError(f"{page.name} {table_id}: row before any group {row}")
        fy = normalize_fy(row[1])
        for (code, label), v in zip(codes, row[2:], strict=True):
            x = parse_number(v)
            if x is None:
                continue
            out.append({
                "series_id": f"rtp.scb_cost_return.{code}.{group}", "source_id": SRC, "table_id": table_id,
                "item_code": code, "item_label": clean_label(label), "institution": group, "geography": "IN",
                "stock_flow": "n/a", "period": fy, "period_type": "fy", "value": x, "unit": "percent",
                "price_basis": "n/a", "vintage": vintage, "estimate_stage": stage, "status": "official",
                "prov_id": pid,
            })
    if len(out) < 40:
        raise ValueError(f"{page.name} {table_id}: only {len(out)} values")
    return out


OWN_ROWS = {
    "government companies": "government",
    "non-government companies": "non_government",
    "public limited companies": "non_government_public_ltd",
    "private limited companies": "non_government_private_ltd",
    "total": "total",
}
OWN_MEASURES = {"number": ("companies", "count"), "asset size": ("assets", "INR_crore"), "asset share": ("asset_share", "percent"),
                "asset share in per cent": ("asset_share", "percent")}


def _nbfc_ownership(ctx: BuildContext, raw: RawFile, page: Page, doc: Any) -> list[dict[str, Any]]:
    """'Ownership Pattern of NBFCs' (at end-March of the edition year): number, assets, share."""
    vintage, release = EDITIONS[page.edition]
    caption, g = H.find_table(doc, r"^Table VI\.\d+: Ownership Pattern of NBFCs")
    table_id = caption.split(":")[0].strip()
    blob = " ".join(r[0] for r in g[:4] if len(set(r)) == 1) + " " + caption
    m = re.search(r"end-\s*March (\d{4})", blob)
    if not m or "crore" not in blob:
        raise ValueError(f"{page.name} {table_id}: date/unit caption not found in {blob!r}")
    date = f"{m.group(1)}-03-31"
    first_hdr = next(i for i, r in enumerate(g) if len(set(r)) > 1)
    headers, data, _ = H.split_table(g, label_cols=1, header_from=first_hdr)
    cols = []
    for i, h in enumerate(headers):
        parts = [p for p in dict.fromkeys(h.parts) if p]
        if len(parts) != 2 or parts[0].lower() not in GROUPS or parts[1].lower() not in OWN_MEASURES:
            raise ValueError(f"{page.name} {table_id}: column header {parts}")
        cols.append((1 + i, GROUPS[parts[0].lower()], *OWN_MEASURES[parts[1].lower()]))
    pids = {}
    for unit, pub in (("count", "number of companies"), ("INR_crore", "Rs crore"), ("percent", "per cent")):
        pids[unit] = ctx.prov(raw=raw, table_id=table_id,
                              locator=f"{page.url} ({page.edition} {page.part} HTML), '{caption}', rows A-C, "
                                      f"{'Number' if unit == 'count' else 'Asset Size' if unit == 'INR_crore' else 'Asset share'} columns",
                              unit_as_published=pub, conversion="none",
                              price_basis="current" if unit == "INR_crore" else "n/a", vintage=vintage, release=release)
    out, seen = [], set()
    for row in data:
        if H.is_note_row(row):
            break
        k = H.norm_label(row[0])
        if k not in OWN_ROWS:
            raise ValueError(f"{page.name} {table_id}: unmapped row {row[0]!r}")
        seen.add(k)
        for idx, inst, measure, unit in cols:
            x = parse_number(row[idx])
            if x is None:
                continue
            code = f"{measure}_{OWN_ROWS[k]}"
            out.append({
                "series_id": f"rtp.nbfc_ownership.{code}.{inst}" + (".current" if unit == "INR_crore" else ""),
                "source_id": SRC, "table_id": table_id, "item_code": code, "item_label": clean_label(row[0]),
                "institution": inst, "geography": "IN", "dim_other": f"ownership={OWN_ROWS[k]}",
                "stock_flow": "stock" if unit != "percent" else "n/a", "period": date, "period_type": "date",
                "value": x, "unit": unit, "price_basis": "current" if unit == "INR_crore" else "n/a",
                "vintage": vintage, "estimate_stage": "Provisional" if "provisional" in _note(g).lower() else "n.a.",
                "status": "official", "prov_id": pids[unit],
            })
    if seen != set(OWN_ROWS):
        raise ValueError(f"{page.name} {table_id}: rows missing {set(OWN_ROWS) - seen}")
    return out


@dataclass
class Result:
    rows: dict[str, list[dict[str, Any]]] = field(default_factory=dict)  # dataset suffix -> rows


DATASET_OF = {
    "scb_pl": "banks", "scb_bs": "banks", "scb_cost_return": "banks", "rrb_pl": "banks", "lab_pl": "banks",
    "sfb_pl": "banks", "pb_pl": "banks",
    "ucb_pl": "coop", "stcb_pl": "coop", "dccb_pl": "coop",
    "nbfc_pl": "nbfi", "nbfc_layer_pl": "nbfi", "nbfc_ownership": "nbfi", "hfc_pl": "nbfi", "aifi_pl": "nbfi",
    "spd_pl": "nbfi",
}


def build(ctx: BuildContext) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"banks": [], "coop": [], "nbfi": []}
    for page in PAGES:
        raw = ctx.raw(SRC, page.name)
        doc = H.soup(raw.path)
        date, heading = H.page_heading(H.soup(raw.path))
        from .ar import page_date

        if page_date(date) != EDITIONS[page.edition][0] or clean_label(heading) != page.heading:
            raise ValueError(f"{page.name}: page is {date!r} {heading!r}, expected {EDITIONS[page.edition][0]} {page.heading!r}")
        for spec in SPECS:
            if page.part in spec.parts:
                out[DATASET_OF[spec.key]] += _parse_level_table(ctx, raw, page, spec, doc)
        if page.part == "ch4":
            out["banks"] += _cost_of_funds(ctx, raw, page, doc)
        if page.part == "ch6":
            out["nbfi"] += _nbfc_ownership(ctx, raw, page, doc)
    return out


Parser = Callable[..., list[dict[str, Any]]]
