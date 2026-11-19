"""Parsers for Union Budget documents (Receipt Budget tables and annexes, Annual Financial
Statement, Expenditure Profile statements).

Only the ACTUALS column is read. Every parser first checks that the column it reads is headed
'Actual(s) <year>' for the year the caller expects, because the Budget site keeps stale files
under current names (e.g. budget2025-26/doc/rec/tr.xls is the Interim 2024-25 vintage and
/doc/AFS/allafs.xlsx is the July 2024 vintage). All amounts are published in Rs crore.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import openpyxl
import pdfplumber

from pipeline.core.units import clean_label, parse_number, slug

_BUDGET_NIL = {"...", "…", ".."}


def _num(cell: Any) -> float | None:
    """A budget cell. '...', '..' and '…' mean nil in Budget documents (the xlsx files print 0 in
    the same places) -> 0.0; blanks -> None; strings like '878730.73 ' -> float."""
    if cell is None:
        return None
    if isinstance(cell, str):
        s = cell.strip()
        if not s:
            return None
        if s in _BUDGET_NIL:
            return 0.0
        return parse_number(s)
    return parse_number(cell)


def _year_of(text: str) -> str | None:
    m = re.search(r"(20\d{2})\s*-\s*(20\d{2})", text)
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    if b != a + 1:
        raise ValueError(f"odd year label {text!r}")
    return f"{a}-{str(b)[2:]}"


# ---------------------------------------------------------------------------------------------
# Receipt Budget: Tax Revenue (tr) and Non Tax Revenue (ntr) tables
# ---------------------------------------------------------------------------------------------


@dataclass
class RBRow:
    code: str  # '1.01', '2.13.03'; '' for Total-/Net- lines
    label: str
    major_head: str  # '0020'; '' when not printed
    value: float | None  # Actuals column (None = '...' nil)
    kind: str  # 'item' | 'total'
    where: str  # page/line or sheet/row, for the provenance locator


_RB_ITEM = re.compile(
    r"^(?P<code>\d+(?:\.\d+)*)\.?\s+(?P<label>.*?)(?:\s+(?P<mh>\d{4}))?"
    r"(?:\s+(?P<vals>(?:-?\d[\d,]*\.?\d*|\.\.\.)(?:\s+(?:-?\d[\d,]*\.?\d*|\.\.\.)){3}))?$"
)
_RB_TOTAL = re.compile(
    r"^(?P<label>(?:Total|Net|Grand Total)\b.*?)"
    r"\s+(?P<vals>(?:-?\d[\d,]*\.?\d*|\.\.\.)(?:\s+(?:-?\d[\d,]*\.?\d*|\.\.\.)){3})$"
)


def rb_rows_pdf(path: Path, *, table: str, actual_year: str) -> list[RBRow]:
    """Receipt Budget tr.pdf / ntr.pdf (Budget 2025-26 layout). Pages without the column header
    'Actual Budget Revised Budget' (the explanatory notes) are skipped."""
    rows: list[RBRow] = []
    seen_header = False
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            words = page.extract_words()
            lines: dict[int, list[dict[str, Any]]] = {}
            for w in words:
                key = next((k for k in lines if abs(k - w["top"]) <= 2.5), None)
                lines.setdefault(key if key is not None else round(w["top"]), []).append(w)
            ordered = [sorted(lines[k], key=lambda w: w["x0"]) for k in sorted(lines)]
            texts = [clean_label(" ".join(w["text"] for w in ln)) for ln in ordered]
            if not any(t.startswith("Actual Budget Revised Budget") for t in texts):
                continue
            hdr = next(t for t in texts if re.search(r"Major Head\s+20\d\d-20\d\d", t))
            years = re.findall(r"20\d{2}-20\d{2}", hdr)
            if not years or _year_of(years[0]) != actual_year:
                raise ValueError(f"{path.name} p{pno}: first column is {years[:1]}, expected Actual {actual_year}")
            if "(In crores)" not in texts and "(In ₹ crores)" not in texts and not any("crores" in t for t in texts):
                raise ValueError(f"{path.name} p{pno}: unit caption '(In crores)' not found")
            seen_header = True
            body = False
            for ln, t in zip(ordered, texts, strict=True):
                if re.search(r"Major Head\s+20\d\d-20\d\d", t):
                    body = True
                    continue
                if not body or t in (table, "Tax Revenue", "Non Tax Revenue") or t.startswith("Receipt Budget"):
                    continue
                x0 = ln[0]["x0"]
                where = f"page {pno}"
                mt = _RB_TOTAL.match(t)
                if mt:
                    lab = mt.group("label")
                    if lab.strip() in ("Net",):
                        continue  # bare 'Net' lines: arithmetic of the item above, not a new number
                    rows.append(RBRow("", lab, "", _num(mt.group("vals").split()[0]), "total", where))
                    continue
                mi = _RB_ITEM.match(t)
                if mi and x0 < 90:
                    vals = mi.group("vals")
                    val = _num(vals.split()[0]) if vals else None
                    rows.append(
                        RBRow(mi.group("code"), mi.group("label"), mi.group("mh") or "", val,
                              "item" if vals else "header", where)
                    )
                    continue
                if x0 > 40 and rows:  # headings sit at the left margin (x0 ~30)
                    rows[-1].label = clean_label(rows[-1].label + " " + t)  # wrapped label
                    continue
                # a heading at the left margin: ignored
    if not seen_header:
        raise ValueError(f"{path.name}: no table page found")
    return rows


def rb_rows_xlsx(path: Path, *, table: str, actual_year: str) -> list[RBRow]:
    """Receipt Budget tr.xlsx / ntr.xlsx (sheet 'ReceiptReport123', Budget 2024-25 and 2026-27)."""
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb["ReceiptReport123"]
    grid = [list(r) for r in ws.iter_rows(values_only=True)]
    width = max(len(r) for r in grid)
    grid = [r + [None] * (width - len(r)) for r in grid]
    hdr_i = next(i for i, r in enumerate(grid) if any(isinstance(v, str) and v.strip() == "Major Head" for v in r))
    hdr = grid[hdr_i]
    mh_col = next(j for j, v in enumerate(hdr) if isinstance(v, str) and v.strip() == "Major Head")
    act_col = mh_col + 1
    if not (isinstance(hdr[act_col], str) and "Actual" in hdr[act_col] and _year_of(hdr[act_col]) == actual_year):
        raise ValueError(f"{path.name}: column after 'Major Head' is {hdr[act_col]!r}, expected Actuals {actual_year}")
    if not any(isinstance(v, str) and "Crore" in v for r in grid[: hdr_i + 1] for v in r):
        raise ValueError(f"{path.name}: unit caption '(In Rs Crores)' not found")
    rows: list[RBRow] = []
    for i, r in enumerate(grid[hdr_i + 1 :], start=hdr_i + 2):
        cells = [clean_label(v) if isinstance(v, str) else v for v in r[:mh_col]]
        texts = [c for c in cells if isinstance(c, str) and c]
        if not texts:
            continue
        val = _num(r[act_col])
        mh = str(r[mh_col]).strip() if r[mh_col] not in (None, "") else ""
        where = f"sheet 'ReceiptReport123' row {i}"
        first = texts[0]
        if re.match(r"^(Total|Net|Grand Total)\b", first):
            if first == "Net":
                continue
            rows.append(RBRow("", first, "", val, "total", where))
            continue
        if re.match(r"^\d+(?:\.\d+)*\.?$", first) and len(texts) >= 2:
            code = first.rstrip(".")
            rows.append(RBRow(code, texts[1], mh, val, "item", where))
            continue
        # section heading rows ('Tax Revenue', 'Fiscal Services'): no number of their own
    return rows


def rb_leaves(rows: list[RBRow]) -> tuple[list[RBRow], list[RBRow]]:
    """Split the items into the ones that add up to the grand total, and aggregate rows.

    Bottom-up over the item codes: a parent whose printed value equals the net of its children
    (the xlsx prints parent rows with that sum) is an aggregate; a parent whose value differs is
    a gross amount of its own with its children as adjustments (e.g. '1.03 Other Interest
    Receipts' with child '1.03.01 Less-Receipts netted against expenditure'). A parent printed
    without a value (the PDF layout) is a heading. Returns (addends, aggregates)."""
    items = [r for r in rows if r.kind in ("item", "header")]
    kids: dict[int, list[RBRow]] = {
        id(r): [k for k in items if k.code.startswith(r.code + ".") and k.code.count(".") == r.code.count(".") + 1]
        for r in items
    }
    role: dict[int, str] = {}
    net: dict[int, float] = {}
    for r in sorted(items, key=lambda r: -r.code.count(".")):
        ks = kids[id(r)]
        child_net = sum(net[id(k)] for k in ks)
        if not ks:
            role[id(r)] = "addend" if r.kind == "item" else "heading"
            net[id(r)] = r.value or 0.0
        elif r.kind == "header" or r.value is None:
            role[id(r)] = "heading"
            net[id(r)] = child_net
        elif abs((r.value or 0.0) - child_net) <= 0.05:
            role[id(r)] = "aggregate"
            net[id(r)] = r.value or 0.0
        else:
            role[id(r)] = "addend"
            net[id(r)] = (r.value or 0.0) + child_net
    addends = [r for r in items if role[id(r)] == "addend"]
    aggregates = [r for r in items if role[id(r)] == "aggregate"]
    return addends, aggregates


# ---------------------------------------------------------------------------------------------
# Annual Financial Statement (allafs.xlsx)
# ---------------------------------------------------------------------------------------------

AFS_SHEETS = {
    "Sheet1": ("cfi_rev_receipts", "STATEMENT I - CONSOLIDATED FUND OF INDIA - REVENUE ACCOUNT - RECEIPTS"),
    "Sheet2": ("cfi_rev_disbursements", "STATEMENT I - CONSOLIDATED FUND OF INDIA - REVENUE ACCOUNT - DISBURSEMENTS"),
    "Sheet3": ("cfi_cap_receipts", "STATEMENT I - CONSOLIDATED FUND OF INDIA - CAPITAL ACCOUNT - RECEIPTS"),
    "Sheet4": ("cfi_cap_disbursements", "STATEMENT I - CONSOLIDATED FUND OF INDIA - CAPITAL ACCOUNT - DISBURSEMENTS"),
    "Sheet7": ("pa_receipts", "STATEMENT III - PUBLIC ACCOUNT OF INDIA - RECEIPTS"),
    "Sheet8": ("pa_disbursements", "STATEMENT III - PUBLIC ACCOUNT OF INDIA - DISBURSEMENTS"),
}


@dataclass
class AFSRow:
    sheet: str
    key: str
    label: str
    major_head: str
    value: float
    row: int
    col: str
    section: str


def afs_rows(path: Path, *, actual_year: str) -> list[AFSRow]:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    out: list[AFSRow] = []
    for sheet, (key, title) in AFS_SHEETS.items():
        ws = wb[sheet]
        grid = [list(r) for r in ws.iter_rows(values_only=True)]
        width = max(len(r) for r in grid)
        grid = [r + [None] * (width - len(r)) for r in grid]
        head = re.sub(r"\s+", " ", " ".join(str(v) for r in grid[:12] for v in r if isinstance(v, str)))
        if title not in head.upper() or "crore" not in head.lower():
            raise ValueError(f"{path.name} {sheet}: expected {title!r} in Rs crore, header reads {head[:200]!r}")
        hdr_i, act_col = next(
            (i, j)
            for i, r in enumerate(grid[:10])
            for j, v in enumerate(r)
            if isinstance(v, str) and "Actuals" in v
        )
        if _year_of(str(grid[hdr_i][act_col])) != actual_year:
            raise ValueError(f"{path.name} {sheet}: Actuals column is {grid[hdr_i][act_col]!r}, expected {actual_year}")
        mh_col = next((j for j, v in enumerate(grid[hdr_i]) if isinstance(v, str) and "Major" in v), None)
        section = ""
        for i, r in enumerate(grid[hdr_i + 1 :], start=hdr_i + 2):
            # English label: the right-most text cell left of the value columns that is ASCII
            texts = [
                (j, clean_label(v))
                for j, v in enumerate(r[: mh_col if mh_col is not None else act_col])
                if isinstance(v, str) and v.strip() and re.search(r"[A-Za-z]", v) and not re.search(r"[ऀ-ॿ]", v)
            ]
            if not texts:
                continue
            label = texts[-1][1]
            prefix = [t for _, t in texts[:-1] if re.fullmatch(r"[A-Z]\.|\([a-z]+\)|[A-Z]\.?", t)]
            if prefix:
                label = f"{prefix[0]} {label}"
            mh = ""
            if mh_col is not None and r[mh_col] not in (None, ""):
                mh = str(r[mh_col]).strip()
            v = _num(r[act_col])
            if v is None:
                if not mh:
                    section = label
                continue
            out.append(
                AFSRow(key, "", label, mh, v, i, openpyxl.utils.get_column_letter(act_col + 1), section)
            )
    # stable keys: the major head when printed, else a slug of the label (+ section on clashes)
    for key in {r.sheet for r in out}:
        rs = [r for r in out if r.sheet == key]
        base = [r.major_head if re.fullmatch(r"\d{4}", r.major_head) else slug(r.label) for r in rs]
        counts: dict[str, int] = {}
        for b in base:
            counts[b] = counts.get(b, 0) + 1
        for r, b in zip(rs, base, strict=True):
            r.key = b if counts[b] == 1 else f"{b}.{slug(r.section) or 'top'}"
        keys = [r.key for r in rs]
        dup = {k for k in keys if keys.count(k) > 1}
        if dup:
            raise ValueError(f"{path.name} {key}: ambiguous rows {sorted(dup)}")
    return out


# ---------------------------------------------------------------------------------------------
# Expenditure Profile statements (stat1, stat7, stat18, stat20, stat21)
# ---------------------------------------------------------------------------------------------


@dataclass
class EPRow:
    group: str  # the heading row the item sits under ('' for the heading rows themselves)
    number: str  # the printed item number ('1.', 'a', '')
    label: str
    component: str  # '' | 'revenue' | 'capital' | 'grant' | 'loan' | 'total'
    value: float
    row: int
    col: str
    is_group: bool
    sub_item: bool = False  # '4.01 ...' under item '4.' (Statement 21): part of the item above, not an addend


def ep_rows(path: Path, *, actual_year: str, title: str) -> list[EPRow]:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb.worksheets[0]
    grid = [list(r) for r in ws.iter_rows(values_only=True)]
    width = max(len(r) for r in grid)
    grid = [r + [None] * (width - len(r)) for r in grid]
    head = " ".join(str(v) for r in grid[:8] for v in r if isinstance(v, str))
    if title.upper() not in re.sub(r"\s+", " ", head.upper()):
        raise ValueError(f"{path.name}: expected title {title!r}, header reads {head[:200]!r}")
    if "crore" not in head.lower():
        raise ValueError(f"{path.name}: unit caption '(In Rs Crores)' not found")
    hdr_i, act_col = next(
        (i, j) for i, r in enumerate(grid[:12]) for j, v in enumerate(r) if isinstance(v, str) and "Actual" in v
    )
    if _year_of(str(grid[hdr_i][act_col])) != actual_year:
        raise ValueError(f"{path.name}: Actuals column is {grid[hdr_i][act_col]!r}, expected {actual_year}")
    # a sub-header row (Revenue/Capital/Total or Grant/Loan/Total) under 'Actuals'?
    sub = grid[hdr_i + 1] if hdr_i + 1 < len(grid) else []
    comps: dict[int, str] = {}
    if isinstance(sub[act_col] if act_col < len(sub) else None, str) and sub[act_col].strip() in ("Revenue", "Grant"):
        for j in range(act_col, act_col + 3):
            comps[j] = sub[j].strip().lower()
        first_data = hdr_i + 2
    else:
        comps[act_col] = ""
        first_data = hdr_i + 1
    # pass 1: table rows (label, number, values), wrapped labels merged into the row above
    table: list[dict[str, Any]] = []
    for i, r in enumerate(grid[first_data:], start=first_data + 1):
        lead = [v for v in r[:act_col] if v not in (None, "") and str(v).strip()]
        if not lead:
            continue
        raw0 = str(lead[0])
        strs = [clean_label(str(v)) for v in lead]
        number = ""
        sub_item = False
        m_emb = _EMBEDDED_NUMBER.match(raw0)
        if len(strs) >= 2 and re.fullmatch(r"(\d+|[a-z]|[ivx]+)\.?", strs[0]):
            number, label = strs[0], " ".join(strs[1:])
        elif len(strs) >= 2 and re.fullmatch(r"\d+\.\d+", strs[0]):  # sub-item '4.01' of item '4.'
            number, label, sub_item = strs[0], " ".join(strs[1:]), True
        elif m_emb:  # '1.          Food Subsidy' / 'a       Assistance ...' in one cell (Budget 2025-26)
            number, label = m_emb.group(1), clean_label(" ".join([m_emb.group(2), *strs[1:]]))
        else:
            label = " ".join(strs)
        rest = [r[j] for j in range(act_col, len(r)) if r[j] not in (None, "")]
        if label.lower().startswith(("this statement", "note")):
            break  # notes below the table
        if not rest:
            if table and not number and table[-1]["label"] != "Grand Total":
                table[-1]["label"] = clean_label(table[-1]["label"] + " " + label)  # wrapped label
            continue
        table.append({"row": i, "number": number, "label": label, "vals": {j: r[j] for j in comps}, "sub": sub_item})
        if label == "Grand Total":
            break
    # pass 2: rows with values; headings (no item number) set the group of the items below
    out: list[EPRow] = []
    group = ""
    for t in table:
        is_group = not t["number"]
        if is_group:
            group = t["label"]
        for j, comp in comps.items():
            v = _num(t["vals"][j])
            if v is None:
                continue
            out.append(
                EPRow("" if is_group else group, t["number"], t["label"], comp, v, t["row"],
                      openpyxl.utils.get_column_letter(j + 1), is_group, t["sub"])
            )
    return out


_EMBEDDED_NUMBER = re.compile(r"^\s*(\d+\.|[a-z])\s{3,}(\S.*)$")


# ---------------------------------------------------------------------------------------------
# Expenditure Profile Statement 6: allocation under the object head 'Grants for creation of
# capital assets' (GCCA), by Ministry > Demand (department) > item
# ---------------------------------------------------------------------------------------------

S6_TITLE = "ALLOCATION UNDER THE OBJECT HEAD GRANTS FOR CREATION OF CAPITAL ASSETS"
_S6_GT = re.compile(r"^Grand Total$")
_S6_DEMAND = re.compile(r"^Demand\s*No\.?\s*(\d+)$")
# '12.  Label' (at least one space: '2.0 (CITIIS 2.0)' and '41.15 metres ...' are wrapped label tails)
_S6_ITEM = re.compile(r"^(\d+)\.\s+(\S.*)$")
_S6_SUBITEM = re.compile(r"^\d+\.\d{2}\s+[A-Z]")  # '4.01 Contribution ...' (not '2.0 (CITIIS' or '41.15 metres')


@dataclass
class S6Row:
    level: str  # 'ministry' | 'demand' | 'item' | 'total'
    ministry: str
    demand: str  # printed demand number ('42'); '' for ministry and total rows
    department: str  # the heading printed under the demand line ('' if none is printed)
    number: str  # item number ('3'); '' otherwise
    label: str
    values: list[float]  # every value column, left to right (Actuals first); blank -> 0.0
    row: int  # 1-based sheet row where the values are printed
    col: str  # column letter of the Actuals column


def stat6_rows(path: Path, *, actual_year: str) -> list[S6Row]:
    """Expenditure Profile Statement 6 (xlsx). Three layouts are handled:

    - Budgets 2024-25 and 2026-27: item number and label in their own cells, one row per line;
    - Budget 2025-26: a PDF conversion with the item number embedded in the label cell
      ('1.            Coconut Development Board'), labels wrapped onto the next row(s), and a few
      rows where two printed lines share one cell ('10. Nehru Yuva ...\\n11. Rajiv Gandhi ...',
      the second item's values sitting on the next row with its label tail).

    Rules: a row with values is the Grand Total, a 'Demand No. N' line, an item (numbered), the
    value row of an item whose number was printed on the row above (pending), or else a ministry
    line. A row without values is the department heading when it follows a demand line, and the
    tail of the previous line's label otherwise. The caller's closure checks (items = demand,
    demands = ministry, ministries = Grand Total, in every value column) prove the assignment."""
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb.worksheets[0]
    grid = [list(r) for r in ws.iter_rows(values_only=True)]
    width = max(len(r) for r in grid)
    grid = [r + [None] * (width - len(r)) for r in grid]
    head = re.sub(r"\s+", " ", " ".join(str(v) for r in grid[:8] for v in r if isinstance(v, str))).upper()
    if S6_TITLE not in head or "CRORES" not in head:
        raise ValueError(f"{path.name}: expected {S6_TITLE!r} in Rs crore, header reads {head[:200]!r}")
    hdr_i = next(
        i for i, r in enumerate(grid[:12]) if any(isinstance(v, str) and "MINISTRY/DEPARTMENT" in v for v in r)
    )
    vcols = [
        j
        for j, v in enumerate(grid[hdr_i])
        if isinstance(v, str) and re.search(r"Actuals|Budget Estimates|Revised Estimates", v)
    ]
    if len(vcols) != 4 or "Actuals" not in str(grid[hdr_i][vcols[0]]):
        raise ValueError(f"{path.name}: value header {[grid[hdr_i][j] for j in vcols]!r}")
    if _year_of(str(grid[hdr_i][vcols[0]])) != actual_year:
        raise ValueError(f"{path.name}: Actuals column is {grid[hdr_i][vcols[0]]!r}, expected {actual_year}")
    lcols = list(range(vcols[0]))
    col = openpyxl.utils.get_column_letter(vcols[0] + 1)

    out: list[S6Row] = []
    pending: list[S6Row] = []
    ministry = demand = ""
    dept: list[str] | None = None  # the current department heading (mutable: wrapped tails)
    last: Any = None  # the record (or department list) a label tail belongs to
    last_was_demand = False
    dept_of: dict[int, list[str]] = {}

    def item(number: str, label: str, values: list[float] | None, row: int) -> S6Row:
        r = S6Row("item", ministry, demand, "", number, label, values or [], row, col)
        dept_of[id(r)] = dept if dept is not None else []
        out.append(r)
        return r

    for i, r in enumerate(grid[hdr_i + 1 :], start=hdr_i + 2):
        text = " ".join(str(r[j]).strip() for j in lcols if r[j] is not None and str(r[j]).strip())
        lines = [clean_label(x) for x in text.split("\n") if x.strip()]
        raw_vals = [r[j] for j in vcols]
        has_vals = any(v is not None and str(v).strip() for v in raw_vals)
        if not lines:
            if has_vals:
                raise ValueError(f"{path.name} row {i}: values without a label")
            continue
        if any(_S6_SUBITEM.match(x) for x in lines):
            raise ValueError(f"{path.name} row {i}: sub-item numbering not handled: {lines!r}")
        if not has_vals:
            if last_was_demand:
                dept = [" ".join(lines)]
                last = dept
            elif isinstance(last, list):
                last[0] = clean_label(last[0] + " " + " ".join(lines))
            elif last is not None:
                last.label = clean_label(last.label + " " + " ".join(lines))
                if last.level == "ministry":  # 'Ministry of Electronics and Information' + 'Technology'
                    ministry = last.ministry = last.label
            else:
                raise ValueError(f"{path.name} row {i}: text {lines!r} before the first table line")
            last_was_demand = False
            continue
        vals = [(_num(v) or 0.0) for v in raw_vals]
        last_was_demand = False
        if _S6_GT.match(lines[0]):
            out.append(S6Row("total", "", "", "", "", "Grand Total", vals, i, col))
            break
        m = _S6_DEMAND.match(lines[0])
        if m:
            if len(lines) != 1 or pending:
                raise ValueError(f"{path.name} row {i}: demand line {lines!r} (pending items {pending})")
            demand = m.group(1)
            dept = None
            rec = S6Row("demand", ministry, demand, "", "", f"Demand No. {demand}", vals, i, col)
            out.append(rec)
            last, last_was_demand = rec, True
            continue
        idx = [k for k, x in enumerate(lines) if _S6_ITEM.match(x)]
        if idx:
            if pending:
                raise ValueError(f"{path.name} row {i}: item {lines!r} while {pending} still have no values")
            prefix = lines[: idx[0]]
            cur: S6Row | None = None
            for k in range(idx[0], len(lines)):
                mi = _S6_ITEM.match(lines[k])
                if mi:
                    lab = " ".join([*prefix, mi.group(2)]) if cur is None else mi.group(2)
                    # the row's values belong to its first numbered line; a second one waits
                    cur = item(mi.group(1), clean_label(lab), vals if cur is None else None, i)
                    if not cur.values:
                        pending.append(cur)
                    prefix = []
                else:
                    assert cur is not None
                    cur.label = clean_label(cur.label + " " + lines[k])
            last = cur
            continue
        if pending:
            it = pending.pop(0)
            it.values, it.row = vals, i
            it.label = clean_label(it.label + " " + " ".join(lines))
            last = it
            continue
        ministry = " ".join(lines)
        demand, dept = "", None
        rec = S6Row("ministry", ministry, "", "", "", ministry, vals, i, col)
        out.append(rec)
        last = rec
    if pending:
        raise ValueError(f"{path.name}: items without values {pending}")
    if not out or out[-1].level != "total":
        raise ValueError(f"{path.name}: no Grand Total line")
    for r in out:
        if r.level == "item":
            d = dept_of[id(r)]
            r.department = d[0] if d else ""
    # the department of a demand is the heading printed under it (read from its items)
    for r in out:
        if r.level == "demand":
            r.department = next((x.department for x in out if x.level == "item" and x.demand == r.demand
                                 and x.ministry == r.ministry and x.department), "")
    return out


# ---------------------------------------------------------------------------------------------
# Receipt Budget Annex 8: Sources and application of the National Small Savings Fund
# ---------------------------------------------------------------------------------------------


@dataclass
class A8Row:
    section: str
    label: str
    value: float
    stock_date: str | None  # 'YYYY-04-01' for 'as on 1st April' rows, else None (flow)
    where: str


def annex8_rows(path: Path, *, actual_year: str) -> list[A8Row]:
    with pdfplumber.open(path) as pdf:
        text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    lines = [clean_label(x) for x in text.splitlines() if x.strip()]
    if not any("SOURCES AND APPLICATION OF NATIONAL SMALL SAVINGS FUND" in x for x in lines):
        raise ValueError(f"{path.name}: not the NSSF annex")
    hdr = next(x for x in lines if x.startswith("Particulars"))
    m = re.search(r"Actual\s+(20\d{2}-20\d{2})", hdr)
    if not m or _year_of(m.group(1)) != actual_year:
        raise ValueError(f"{path.name}: first column {hdr!r}, expected Actual {actual_year}")
    start_year = int(actual_year[:4])
    out: list[A8Row] = []
    section = ""
    vals_re = re.compile(r"^(?P<label>.*?)\s+(?P<a>-?[\d,]+\.\d+|-|\.\.\.)\s+(?P<b>\S+)\s+(?P<c>\S+)$")
    part = ""
    for x in lines:
        if x.startswith("A SOURCES OF FUND"):
            part = "sources"
            continue
        if x.startswith("B APPLICATION OF FUND"):
            part = "application"
            continue
        if not part:
            continue
        if x.startswith(("Receipt Budget", "Particulars", "(In ")):
            continue  # running header of a continuation page
        mv = vals_re.match(x)
        if not mv:
            section = x
            continue
        label = mv.group("label")
        v = _num(mv.group("a")) if mv.group("a") not in ("-",) else None
        if v is None:
            continue
        stock = f"{start_year}-04-01" if re.search(r"as on 1st April|Opening Balance", label, re.I) else None
        out.append(A8Row(f"{part}: {section}" if section else part, label, v, stock, "page 1"))
    return out
