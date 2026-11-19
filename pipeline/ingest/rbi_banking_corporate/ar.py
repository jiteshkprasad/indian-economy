"""RBI Annual Report, Chapter XII 'The Reserve Bank's Accounts' (HTML chapter on www.rbi.org.in).

Three editions (2023-24, 2024-25, 2025-26) give the RBI's audited accounts for the accounting years
2021-22 to 2025-26 (April-March), each year from up to three editions (vintages):
- Table XII.1: income, expenditure, net income, transfer to funds, surplus transferred (5 years).
- Table XII.10: expenditure by head (5 years).
- Income statement (2 years) and Schedules 1-15 (2 years; balance-sheet schedules are stocks at
  31 March, income schedules 13-15 are flows).
- Balance sheet (2 dates).
- Table XII.8: foreign currency assets and the earnings on them (2 years).

Not ingested: XII.1/XII.10 columns for 2019-20 and 2020-21. Until 2019-20 the RBI's accounting year
ran July-June and 2020-21 was a nine-month transition year (July 2020-March 2021), so those columns
are not fiscal years and cannot carry period_type 'fy'. Tables XII.2-XII.7 and XII.9 (reserve
balances, gold, FX reserves, domestic earnings re-cut) repeat the schedules or are outside the SAM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pipeline.core.unit import BuildContext, RawFile
from pipeline.core.units import clean_label, normalize_fy, parse_number, slug

from . import _html as H

SRC = "rbi_annual_report"
LANDING = "https://www.rbi.org.in/Scripts/AnnualReportPublications.aspx"
URL = "https://www.rbi.org.in/Scripts/AnnualReportPublications.aspx?Id={id}"


@dataclass(frozen=True)
class Edition:
    key: str  # file-name stem
    page_id: int
    year: str  # the accounting year the edition reports
    vintage: str  # release date printed on the page

    @property
    def name(self) -> str:
        return f"{self.key}_ch12_accounts.html"

    @property
    def url(self) -> str:
        return URL.format(id=self.page_id)

    @property
    def release(self) -> str:
        return f"RBI Annual Report {self.year}, Chapter XII 'The Reserve Bank's Accounts for {self.year}' (HTML, {self.vintage})"


EDITIONS = (
    Edition("ar2324", 1412, "2023-24", "2024-05-30"),
    Edition("ar2425", 1442, "2024-25", "2025-05-29"),
    Edition("ar2526", 1472, "2025-26", "2026-05-29"),
)
FIRST_FY = "2021-22"  # first April-March accounting year (see module docstring)
STAGE = "Audited"
_MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}


def page_date(text: str) -> str:
    m = re.fullmatch(r"([A-Za-z]{3})[a-z]* (\d{1,2}), (\d{4})", text.strip())
    if not m:
        raise ValueError(f"unexpected date {text!r}")
    return f"{m.group(3)}-{_MONTHS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"


def fy_end_date(fy: str) -> str:
    return f"{int(fy[:4]) + 1}-03-31"


def _fy_ok(fy: str) -> bool:
    return fy >= FIRST_FY


def _num(text: str, *, footnoted: bool = False) -> float | None:
    s = text.strip()
    if footnoted:  # XII.1 'Total Expenditure' cells carry a footnote number: '1,29,800.68 2'
        m = re.fullmatch(r"(-?[\d,]+\.\d+)\s+\d{1,2}", s)
        if m:
            s = m.group(1)
    return parse_number(s)


class _Rows:
    """Collects clean rows for one edition."""

    def __init__(self, ctx: BuildContext, raw: RawFile, ed: Edition) -> None:
        self.ctx, self.raw, self.ed = ctx, raw, ed
        self.rows: list[dict[str, Any]] = []

    def prov(self, table_id: str, locator: str, unit_pub: str = "Rs crore", how: str = "rows matched by label") -> str:
        return self.ctx.prov(
            raw=self.raw,
            table_id=table_id,
            locator=f"{self.ed.url} (HTML chapter XII of the Annual Report {self.ed.year}); {locator}; {how}",
            unit_as_published=unit_pub,
            conversion="none",
            price_basis="current" if unit_pub == "Rs crore" else "n/a",
            vintage=self.ed.vintage,
            release=self.ed.release,
        )

    def add(self, *, series: str, table_id: str, item: str, label: str, period: str, ptype: str, value: float,
            pid: str, stock_flow: str, unit: str = "INR_crore", side: str | None = None) -> None:
        self.rows.append({
            "series_id": f"{series}.current" if unit == "INR_crore" else series,
            "source_id": SRC,
            "table_id": table_id,
            "item_code": item,
            "item_label": clean_label(label),
            "institution": "rbi",
            "geography": "IN",
            "side": side,
            "stock_flow": stock_flow,
            "period": period,
            "period_type": ptype,
            "value": value,
            "unit": unit,
            "price_basis": "current" if unit == "INR_crore" else "n/a",
            "vintage": self.ed.vintage,
            "estimate_stage": STAGE,
            "status": "official",
            "prov_id": pid,
        })


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


# ---------------------------------------------------------------------------------------------
# Table XII.1 and XII.10 (five-year tables)
# ---------------------------------------------------------------------------------------------

XII_1_ITEMS = {
    "income": "income",
    "total expenditure 1": "total_expenditure",
    "net income": "net_income",
    "transfer to funds 7": "transfer_to_funds",
    "surplus transferred to the central government": "surplus_transferred",
}
XII_10_ITEMS = {
    "interest": "interest",
    "employee cost": "employee_cost",
    "agency charges/commission": "agency_charges",
    "printing of notes": "printing_of_notes",
    "provisions": "provisions",
    "others": "others",
    "total": "total",
}


def _five_year(r: _Rows, doc: Any, title_re: str, table_id: str, key: str, items: dict[str, str]) -> None:
    caption, g = H.find_table(doc, title_re)
    _expect("crore" in g[1][0], f"{table_id}: unit caption not in crore: {g[1][0]!r}")
    headers, data, _ = H.split_table(g, label_cols=1, header_from=2)
    years = [normalize_fy(h.text) for h in headers]
    _expect(years[-1] == r.ed.year and len(years) == 5, f"{table_id}: unexpected year header {years}")
    keep = [(i, y) for i, y in enumerate(years) if _fy_ok(y)]
    pid = r.prov(table_id, f"'{caption}', all item rows, year columns {keep[0][1]} to {keep[-1][1]} "
                           f"(columns {years[0]} to {years[keep[0][0] - 1]} skipped: not April-March years)"
                 if keep[0][0] else f"'{caption}', all item rows, year columns {years[0]} to {years[-1]}")
    seen = set()
    for row in data:
        if H.is_note_row(row):
            break
        nl = H.norm_label(row[0])
        # XII.1 prints footnote numbers as separate tokens after labels ('Total Expenditure 1').
        code = items.get(nl) or items.get(re.sub(r"\s+\d$", "", nl))
        if code is None:
            raise ValueError(f"{table_id} ({r.ed.key}): unmapped row label {row[0]!r}")
        seen.add(code)
        for i, y in keep:
            v = _num(row[1 + i], footnoted=True)
            _expect(v is not None, f"{table_id} ({r.ed.key}): blank cell for {code} {y}")
            r.add(series=f"{key}.{code}", table_id=table_id, item=code, label=row[0], period=y, ptype="fy",
                  value=v, pid=pid, stock_flow="flow")
    _expect(seen == set(items.values()), f"{table_id} ({r.ed.key}): rows missing: {set(items.values()) - seen}")


# ---------------------------------------------------------------------------------------------
# Income statement
# ---------------------------------------------------------------------------------------------

IS_ITEMS = {
    ("income", "interest"): "income_interest",
    ("income", "other income"): "income_other",
    ("income", "total"): "income_total",
    ("expenditure", "printing of notes"): "exp_printing_of_notes",
    ("expenditure", "expenditure on remittance of currency"): "exp_remittance_of_currency",
    ("expenditure", "agency charges"): "exp_agency_charges",
    ("expenditure", "employee cost"): "exp_employee_cost",
    ("expenditure", "interest"): "exp_interest",
    ("expenditure", "postage and telecommunication charges"): "exp_postage_telecom",
    ("expenditure", "printing and stationery"): "exp_printing_stationery",
    ("expenditure", "rent, taxes, insurance, lighting, etc."): "exp_rent_taxes_insurance_lighting",
    ("expenditure", "repairs and maintenance"): "exp_repairs_maintenance",
    ("expenditure", "directors' and local board members' fees and expenses"): "exp_directors_fees",
    ("expenditure", "auditors' fees and expenses"): "exp_auditors_fees",
    ("expenditure", "law charges"): "exp_law_charges",
    ("expenditure", "depreciation"): "exp_depreciation",
    ("expenditure", "miscellaneous expenses"): "exp_miscellaneous",
    ("expenditure", "provisions"): "exp_provisions",
    ("expenditure", "total"): "expenditure_total",
    ("expenditure", "available balance"): "available_balance",
    ("less", "national industrial credit (long term operations) fund"): "to_nic_lto_fund",
    ("less", "national housing credit (long term operations) fund"): "to_nhc_lto_fund",
    ("less", "national rural credit (long term operations) fund 1"): "to_nrc_lto_fund",
    ("less", "national rural credit (long term operations) fund1"): "to_nrc_lto_fund",
    ("less", "national rural credit (stabilisation) fund 1"): "to_nrc_stabilisation_fund",
    ("less", "national rural credit (stabilisation) fund1"): "to_nrc_stabilisation_fund",
    ("less", "others"): "to_others",
    ("less", "surplus payable to the central government"): "surplus_payable",
}
IS_HEADERS = {"expenditure": "expenditure", "less:": "less", "contribution to:": None, "transferable to nabard:": None}


def _income_statement(r: _Rows, doc: Any) -> None:
    fy_end = int(r.ed.year[:4]) + 1
    caption, g = H.find_table(doc, rf"^RESERVE BANK OF INDIA INCOME STATEMENT FOR THE YEAR ENDED MARCH 31, {fy_end}$")
    _expect("crore" in g[1][0], f"income statement: caption {g[1][0]!r}")
    hdr = g[2]
    _expect(hdr[0].upper() == "INCOME" and hdr[1] == "Schedule", f"income statement header {hdr}")
    years = [normalize_fy(hdr[2]), normalize_fy(hdr[3])]
    _expect(years[1] == r.ed.year, f"income statement years {years}")
    pid = r.prov("Income Statement", f"'{caption}', all rows, columns {years[0]} and {years[1]}")
    section, seen = "income", set()
    for row in g[3:]:
        if H.is_note_row(row) or re.match(r"^\d+\. These funds", row[0]):
            break
        nl = H.norm_label(row[0])
        if nl in IS_HEADERS and not any(row[2:4]):
            section = IS_HEADERS[nl] or section
            continue
        code = IS_ITEMS.get((section, nl))
        if code is None and nl == "surplus payable to the central government":
            code = IS_ITEMS[("less", nl)]
        if code is None:
            raise ValueError(f"income statement ({r.ed.key}): unmapped row {section}/{row[0]!r}")
        seen.add(code)
        for j, y in enumerate(years):
            v = parse_number(row[2 + j])
            if v is None:
                if code == "to_others":  # '(c) Others' is printed blank in some editions
                    continue
                raise ValueError(f"income statement ({r.ed.key}): blank {code} {y}")
            if _fy_ok(y):
                r.add(series=f"is.{code}", table_id="Income Statement", item=code, label=row[0], period=y,
                      ptype="fy", value=v, pid=pid, stock_flow="flow")
    need = {c for c in IS_ITEMS.values()}
    _expect(seen == need, f"income statement ({r.ed.key}): rows missing {need - seen}")


# ---------------------------------------------------------------------------------------------
# Balance sheet
# ---------------------------------------------------------------------------------------------

BS_LIAB = {
    "capital": "capital",
    "reserve fund": "reserve_fund",
    "other reserves": "other_reserves",
    "deposits": "deposits",
    "contingency fund": "contingency_fund",
    "asset development fund": "asset_development_fund",
    "revaluation accounts": "revaluation_accounts",
    "other liabilities": "other_liabilities",
    "notes issued": "notes_issued",
    "total liabilities": "total_liabilities",
}
BS_LIAB_HEADERS = {"risk provisions", "liabilities of issue department"}
BS_ASSET = {
    "notes, rupee coin, small coin": "notes_rupee_coin_small_coin",
    "gold-bd": "gold_bd",
    "investments-foreign-bd": "investments_foreign_bd",
    "investments-domestic-bd": "investments_domestic_bd",
    "bills purchased and discounted": "bills_purchased_discounted",
    "loans and advances": "loans_and_advances",
    "investment in subsidiaries": "investment_in_subsidiaries",
    "investment in subsidiaries/associates": "investment_in_subsidiaries",
    "other assets": "other_assets",
    "gold-id": "gold_id",
    "rupee coin": "rupee_coin_id",
    "investments-foreign-id": "investments_foreign_id",
    "investments-domestic-id": "investments_domestic_id",
    "domestic bills of exchange and other commercial papers": "domestic_bills_id",
    "": "issue_department_assets_total",
    "total assets": "total_assets",
}
BS_ASSET_HEADERS = {"assets of banking department (bd)", "assets of issue department (id) (as backing for notes issued)"}


def _balance_sheet(r: _Rows, doc: Any) -> None:
    fy_end = int(r.ed.year[:4]) + 1
    caption, g = H.find_table(doc, rf"^RESERVE BANK OF INDIA BALANCE SHEET AS ON MARCH 31, {fy_end}$")
    hdr = g[2]
    _expect(hdr[0] == "Liabilities" and hdr[4] == "Assets", f"balance sheet header {hdr}")
    years = [normalize_fy(hdr[2]), normalize_fy(hdr[3])]
    _expect(years == [normalize_fy(hdr[6]), normalize_fy(hdr[7])] and years[1] == r.ed.year, f"bs years {hdr}")
    dates = [fy_end_date(y) for y in years]
    pid = r.prov("Balance Sheet", f"'{caption}', liabilities (cols 1-4) and assets (cols 5-8), as on {dates[0]} and {dates[1]}")
    # The Issue Department assets sub-total has no printed label: separate record so the locator says so.
    pid_unlabelled = r.prov(
        "Balance Sheet",
        f"'{caption}', assets (cols 5-8), the UNLABELLED sub-total row printed directly below 'Domestic Bills of "
        f"Exchange and other Commercial Papers' and above 'Total Assets' (sum of the Issue Department assets), as on "
        f"{dates[0]} and {dates[1]}; the row has no label in the source, so item_label is descriptive (in parentheses)",
        how="row located by its position (the only valued asset row without a label)")
    seen: set[str] = set()
    for row in g[3:]:
        for side, off, items, headers in (("liabilities", 0, BS_LIAB, BS_LIAB_HEADERS),
                                          ("assets", 4, BS_ASSET, BS_ASSET_HEADERS)):
            label, vals = row[off], row[off + 2 : off + 4]
            nl = H.norm_label(label)
            if not any(v.strip() for v in vals):
                if nl and nl not in headers:
                    raise ValueError(f"balance sheet ({r.ed.key}): unexpected header row {label!r}")
                continue
            code = items.get(nl)
            if code is None:
                raise ValueError(f"balance sheet ({r.ed.key}): unmapped {side} row {label!r}")
            seen.add(code)
            for d, v in zip(dates, vals, strict=True):
                x = parse_number(v)
                _expect(x is not None, f"balance sheet ({r.ed.key}): blank {code} {d}")
                r.add(series=f"bs.{code}", table_id="Balance Sheet", item=code,
                      label=label or "(unlabelled row: Issue Department assets total)",
                      period=d, ptype="date", value=x, pid=pid if label else pid_unlabelled, stock_flow="stock", side=side)
    need = set(BS_LIAB.values()) | set(BS_ASSET.values())
    _expect(seen == need, f"balance sheet ({r.ed.key}): rows missing {need - seen}")


# ---------------------------------------------------------------------------------------------
# Schedules 1-15
# ---------------------------------------------------------------------------------------------

FLOW_SCHEDULES = {13, 14, 15}  # Interest, Other Income, Agency Charges (income statement schedules)
# Lines relabelled in the 2025-26 edition; the 31 March 2025 values are identical in both editions,
# so they keep the code of the earlier label (the item_label keeps each edition's wording).
SCHEDULE_ALIASES = {
    "sch2.c.repo_foreign": "sch2.c.repo_borrowing_foreign",
    "sch2.c.cash_margin_foreign": "sch2.c.reverse_repo_margin_foreign",
    "sch10.c.reverse_repo_foreign": "sch10.c.reverse_repo_lending_foreign",
    "sch10.c.cash_margin_foreign": "sch10.c.repo_margin_foreign",
}
_TOP = re.compile(r"^\(([ivx]+)\)\s+")
_SUB = re.compile(r"^([a-z])\.\s+")
_SEC = re.compile(r"^\(([a-z])\)\s+")


def _schedules(r: _Rows, doc: Any) -> None:
    caption, g = H.find_table(doc, r"^SCHEDULES FORMING PART OF BALANCE SHEET AND INCOME STATEMENT$")
    _expect("crore" in g[1][0], "schedules caption")
    years = [normalize_fy(g[2][2]), normalize_fy(g[2][3])]
    _expect(years[1] == r.ed.year, f"schedule years {years}")
    pids: dict[int, str] = {}  # one provenance record per schedule (table_id 'Schedule N', as on the rows)

    def pid_of(n: int) -> str:
        if n not in pids:
            what = (f"income-statement items, columns {years[0]} and {years[1]}" if n in FLOW_SCHEDULES
                    else f"balance-sheet items, columns {years[0]} and {years[1]} = as on 31 March")
            pids[n] = r.prov(f"Schedule {n}", f"'{caption}', block 'Schedule {n}:' ({what})")
        return pids[n]

    sched, sec, parent = 0, "x", None
    groups: dict[tuple[Any, ...], list[str]] = {}  # identity groups: key -> item codes
    totals: dict[tuple[Any, ...], str] = {}
    single_sections: dict[tuple[Any, ...], str] = {}
    values: dict[str, list[float]] = {}
    labels: dict[str, str] = {}
    for row in g[3:]:
        head, label, vals = row[0], row[1], row[2:4]
        if H.is_note_row(row):
            break
        m = re.fullmatch(r"Schedule (\d+):", head.strip())
        if m:
            sched, sec, parent = int(m.group(1)), "x", None
            continue
        _expect(sched > 0 and not head.strip(), f"schedules ({r.ed.key}): unexpected row {row}")
        nums = [parse_number(v) for v in vals]
        lab = clean_label(label)
        if all(n is None for n in nums):
            ms = _SEC.match(lab)
            _expect(bool(ms), f"schedules ({r.ed.key}): unexpected blank row {lab!r} in schedule {sched}")
            sec, parent = ms.group(1), None
            continue
        if lab.lower() in ("sub total", "sub-total", "subtotal"):
            code = f"sch{sched}.{sec}.sub_total"
            totals[(sched, sec)] = code
        elif lab.lower() == "total":
            code = f"sch{sched}.total"
            totals[(sched,)] = code
        elif _TOP.match(lab) is not None:
            code = f"sch{sched}.{sec}.{slug(H.norm_label(lab))}"
            code = SCHEDULE_ALIASES.get(code, code)
            groups.setdefault((sched, sec), []).append(code)
            parent = code if re.search(r"\(\s*a\s*\+\s*b\s*\)\s*$", lab) else None
        elif (mb := _SUB.match(lab)) is not None:
            _expect(parent is not None, f"schedules ({r.ed.key}): sub-item {lab!r} without an '(a + b)' parent")
            code = f"{parent}.{mb.group(1)}"
            groups.setdefault((parent,), []).append(code)
            totals[(parent,)] = parent
        elif (ms := _SEC.match(lab)) is not None:
            # a section printed as one line with its own value, e.g. Schedule 7 '(b) Issue Department'
            sec, parent = ms.group(1), None
            code = f"sch{sched}.{sec}.{slug(H.norm_label(lab))}"
            single_sections[(sched, sec)] = code
        else:
            raise ValueError(f"schedules ({r.ed.key}): unrecognised row label {lab!r} in schedule {sched}")
        _expect(code not in values, f"schedules ({r.ed.key}): duplicate item {code}")
        _expect(all(n is not None for n in nums), f"schedules ({r.ed.key}): blank value in {code}")
        values[code] = nums  # type: ignore[assignment]
        labels[code] = lab
    _expect(sched >= 15, f"schedules ({r.ed.key}): only {sched} schedules found")
    # Structural check: every item group adds up to its (sub)total, else the layout changed.
    for key, total_code in totals.items():
        if len(key) == 1 and isinstance(key[0], int):  # schedule total = sub totals, or top items if none
            parts = [c for k, c in {**totals, **single_sections}.items() if len(k) == 2 and k[0] == key[0]]
            parts = parts or groups.get((key[0], "x"), [])
        else:
            parts = groups.get(key, [])
        for j in range(2):
            s = sum(values[c][j] for c in parts)
            _expect(parts != [] and abs(s - values[total_code][j]) < 0.05,
                    f"schedules ({r.ed.key}): {total_code} = {values[total_code][j]} but its items sum to {s:.2f} ({parts})")
    for code, nums in values.items():
        n = int(code.split(".")[0][3:])
        is_flow = n in FLOW_SCHEDULES
        for y, v in zip(years, nums, strict=True):
            if not _fy_ok(y):
                continue
            r.add(series=code, table_id=f"Schedule {n}", item=code, label=labels[code],
                  period=y if is_flow else fy_end_date(y), ptype="fy" if is_flow else "date",
                  value=v, pid=pid_of(n), stock_flow="flow" if is_flow else "stock")


# ---------------------------------------------------------------------------------------------
# Table XII.8 (foreign sources)
# ---------------------------------------------------------------------------------------------

def _xii_8(r: _Rows, doc: Any) -> None:
    caption, g = H.find_table(doc, r"^Table XII\.8: Earnings from Foreign Sources$")
    headers, data, _ = H.split_table(g, label_cols=1, header_from=2)
    years = [normalize_fy(headers[0].text), normalize_fy(headers[1].text)]
    _expect(years[1] == r.ed.year and "Variation" in headers[2].text, f"XII.8 header {headers}")
    pid = r.prov("Table XII.8", f"'{caption}', rows 1-4, columns {years[0]} and {years[1]} (variation columns not ingested)")
    pid_pct = r.prov("Table XII.8", f"'{caption}', row 'Earnings from FCA as per cent of average FCA', columns {years[0]} and {years[1]}",
                     unit_pub="per cent")
    got = set()
    for row in data:
        if H.is_note_row(row):
            break
        nl = H.norm_label(row[0])
        if nl == "foreign currency assets (fca)":
            code, kind = "fca", "stock"
        elif nl == "average fca":
            code, kind = "fca_average", "avg"
        elif nl.startswith("earnings from fca (interest, discount, exchange gain"):
            code, kind = "fca_earnings", "flow"
        elif nl == "earnings from fca as per cent of average fca":
            code, kind = "fca_earnings_pct_avg_fca", "pct"
        else:
            raise ValueError(f"XII.8 ({r.ed.key}): unmapped row {row[0]!r}")
        got.add(code)
        for j, y in enumerate(years):
            v = parse_number(row[1 + j])
            _expect(v is not None, f"XII.8 blank {code} {y}")
            if not _fy_ok(y):
                continue
            if kind == "stock":
                r.add(series=f"xii_8.{code}", table_id="Table XII.8", item=code, label=row[0], period=fy_end_date(y),
                      ptype="date", value=v, pid=pid, stock_flow="stock")
            elif kind == "pct":
                r.add(series=f"xii_8.{code}", table_id="Table XII.8", item=code, label=row[0], period=y, ptype="fy",
                      value=v, pid=pid_pct, stock_flow="n/a", unit="percent")
            else:
                r.add(series=f"xii_8.{code}", table_id="Table XII.8", item=code, label=row[0], period=y, ptype="fy",
                      value=v, pid=pid, stock_flow="flow" if kind == "flow" else "n/a")
    _expect(len(got) == 4, f"XII.8 ({r.ed.key}): rows {got}")


def build_edition(ctx: BuildContext, ed: Edition) -> list[dict[str, Any]]:
    raw = ctx.raw(SRC, ed.name)
    doc = H.soup(raw.path)
    date, heading = H.page_heading(H.soup(raw.path))
    _expect(page_date(date) == ed.vintage, f"{ed.name}: page date {date!r} != {ed.vintage}")
    _expect(heading.replace("’", "'") == f"XII. The Reserve Bank's Accounts for {ed.year}", f"{ed.name}: heading {heading!r}")
    r = _Rows(ctx, raw, ed)
    _five_year(r, doc, r"^Table XII\.1: Trends in Income, Expenditure, Net Income and Surplus", "Table XII.1", "xii_1", XII_1_ITEMS)
    _five_year(r, doc, r"^Table XII\.10: Expenditure$", "Table XII.10", "xii_10", XII_10_ITEMS)
    _income_statement(r, doc)
    _balance_sheet(r, doc)
    _schedules(r, doc)
    _xii_8(r, doc)
    return r.rows
