"""Parsers for the small non-Budget sources of the union_fiscal unit: the PPAC table of the
petroleum sector's contribution to the exchequer (XLS) and the NSI table of collections under
National Savings Schemes (HTML)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import xlrd
from bs4 import BeautifulSoup

from pipeline.core.units import clean_label, normalize_fy, parse_number, slug


@dataclass
class PPACRow:
    block: str  # 'centre' | 'states'
    part: str  # 'a' (taxes/duties) | 'b' (dividends, income tax etc.) | 'total'
    label: str
    code: str
    period: str
    provisional: bool
    value: float
    row: int  # 1-based sheet row
    col: str


def ppac_rows(path: Path) -> tuple[list[PPACRow], str]:
    """Sheet 'Anx 1' of 'Contribution of Petroleum Sector to Exchequer'. Returns rows and the
    'Table Posted' date (YYYY-MM-DD)."""
    book = xlrd.open_workbook(str(path))
    sh = book.sheet_by_name("Anx 1")
    cells = [[sh.cell_value(r, c) for c in range(sh.ncols)] for r in range(sh.nrows)]
    flat = [str(v) for row in cells for v in row if str(v).strip()]
    posted = next((re.search(r"(\d{2})\.(\d{2})\.(\d{4})", v) for v in flat if "Table Posted" in v), None)
    if not posted:
        raise ValueError(f"{path.name}: 'Table Posted' date not found")
    vintage = f"{posted.group(3)}-{posted.group(2)}-{posted.group(1)}"
    if not any("Contribution of Petroleum Sector to Exchequer" in v for v in flat):
        raise ValueError(f"{path.name}: title not found")
    if not any(v.strip() == "(Rs. Crore)" for v in flat):
        raise ValueError(f"{path.name}: unit caption '(Rs. Crore)' not found")
    hdr_r = next(r for r, row in enumerate(cells) if str(row[0]).strip() == "Particulars")
    years: dict[int, tuple[str, bool]] = {}
    for c, v in enumerate(cells[hdr_r]):
        s = str(v).strip()
        if re.match(r"^20\d\d-\d\d", s):
            years[c] = (normalize_fy(s.replace("(P)", "").strip()), "(P)" in s)
    if not years:
        raise ValueError(f"{path.name}: no year columns")
    out: list[PPACRow] = []
    block, part = "", ""
    seen: set[tuple[str, str]] = set()
    for r in range(hdr_r + 1, len(cells)):
        a, b = str(cells[r][0]).strip(), str(cells[r][1]).strip()
        if a.startswith("1. Contribution to Central"):
            block = "centre"
            continue
        if a.startswith("2. Contribution to State"):
            block = "states"
            continue
        if a.startswith("(P)") or a.startswith("Notes"):
            break
        if b.startswith("A. "):
            part = "a"
            continue
        if b.startswith("B. "):
            part = "b"
            continue
        label = clean_label(a or b)
        if not label or not block and not label.startswith("Total Contribution of Petroleum"):
            continue
        if label.startswith("Total Contribution of Petroleum"):
            blk, prt, code = "all", "total", "total_contribution"
        elif label.startswith("Total Contribution to"):
            blk, prt, code = block, "total", "total"
        elif label.startswith("Sub Total"):
            blk, prt, code = block, part, "subtotal"
        else:
            blk, prt, code = block, part, slug(label)
        if (blk, f"{prt}.{code}") in seen:
            raise ValueError(f"{path.name}: duplicate row {blk} {prt} {code}")
        seen.add((blk, f"{prt}.{code}"))
        for c, (period, prov) in years.items():
            v = parse_number(cells[r][c]) if not isinstance(cells[r][c], float) else cells[r][c]
            if v is None:
                continue
            out.append(PPACRow(blk, prt, clean_label(re.sub(r"\s+\((A|B|A\+B|1\+2)\)$", "", label)), code, period,
                               prov, round(float(v), 2), r + 1, xlrd.colname(c)))
    return out, vintage


@dataclass
class NSIRow:
    period: str
    item: str  # gross_deposits | withdrawals | net_collections
    label: str
    value: float
    row: int


def nsi_rows(path: Path) -> list[NSIRow]:
    """NSI InternalPage.aspx?Id_Pk=152 'Collection under National Savings Schemes' (Rs crore)."""
    soup = BeautifulSoup(path.read_bytes(), "lxml")
    tables = [t for t in soup.find_all("table") if not t.find("table") and "Gross" in t.get_text()]
    if len(tables) != 1:
        raise ValueError(f"{path.name}: expected one collections table, found {len(tables)}")
    rows = [[clean_label(c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"])] for tr in tables[0].find_all("tr")]
    if not any("Crore" in " ".join(r) for r in rows[:2]):
        raise ValueError(f"{path.name}: unit caption '(Rs. In Crores)' not found")
    hdr = next(i for i, r in enumerate(rows) if r[:1] == ["Year"])
    if rows[hdr] != ["Year", "Gross(Deposit)", "Withdrawal", "Net"]:
        raise ValueError(f"{path.name}: unexpected header {rows[hdr]}")
    items = [("gross_deposits", "Gross (Deposit)"), ("withdrawals", "Withdrawal"), ("net_collections", "Net")]
    out: list[NSIRow] = []
    for i, r in enumerate(rows[hdr + 1 :], start=hdr + 2):
        if not r or not re.match(r"^\d{4}-\d{2}$", r[0]):
            raise ValueError(f"{path.name}: unexpected row {r}")
        period = normalize_fy(r[0])
        for (code, lab), cell in zip(items, r[1:4], strict=True):
            v = parse_number(cell)
            if v is None:
                continue
            out.append(NSIRow(period, code, lab, v, i))
    return out
