"""Independent verification of ingest unit rbi_banking_corporate (Phase 1 verifier, first pass, 2026-09-29).

This file does NOT import pipeline.ingest.rbi_banking_corporate. Every pinned raw file is re-read here
with a different parser than the unit uses:
- HTML tables: lxml.html directly, with this file's own colspan/rowspan expansion and header-path
  column matching (the unit uses BeautifulSoup and its own _html.grid / split_table helpers);
- press-release figures: regular expressions over the page text, and a second time over the text of
  the rbidocs PDF print copies read with pypdf (the unit's tests use pdfplumber).
Clean data are read with pyarrow.parquet directly.

How a clean row is located in its raw table (never by row position):
1. file: from the row's vintage (edition) and table_id (chapter / appendix page);
2. table: by its printed caption ('Table IV.3:', 'INCOME STATEMENT', 'Schedule 4:' block ...);
3. row: by its printed label (item_label, normalised), disambiguated where a label repeats by the
   printed section heading above it ('(b) Banks', 'EXPENDITURE');
4. column: by the printed header text above the column (year / end-March date / bank group / measure);
   growth, variation, H1 and part-year columns are excluded.
The comparison is exhaustive (every clean row), and the derived rows (R6, K9b) are recomputed from the
raw tables. A seeded random sample is printed for the verifier notes (docs/phase1/verify/).
"""

from __future__ import annotations

import random
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

import lxml.html
import pyarrow.parquet as pq
import pytest
import yaml
from pypdf import PdfReader

pytestmark = pytest.mark.quality

ROOT = Path(__file__).resolve().parents[2]
UNIT = "rbi_banking_corporate"
CLEAN = ROOT / "data" / "clean" / UNIT
SEED = 20260929
TOL = 1e-6

AR_FILES = {"2024-05-30": "ar2324", "2025-05-29": "ar2425", "2026-05-29": "ar2526"}
RTP_FILES = {"2024-12-26": "rtp2324", "2025-12-29": "rtp2425"}


# --------------------------------------------------------------------------------------------- raw access
@lru_cache(maxsize=None)
def _pins() -> dict:
    return yaml.safe_load((ROOT / "data" / "raw_pins" / f"{UNIT}.yaml").read_text(encoding="utf-8"))["pins"]


def raw_path(key: str) -> Path:
    p = ROOT / _pins()[key]["path"]
    if not p.exists():
        pytest.skip(f"raw file {p} not present (run `pipeline fetch {UNIT} --offline`)")
    return p


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").replace("\xa0", " ")
    s = s.replace("’", "'").replace("‘", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


def _expand(table) -> list[list[str]]:
    """Own colspan/rowspan expansion (lxml elements)."""
    out: list[list[str]] = []
    carry: dict[tuple[int, int], str] = {}
    for r, tr in enumerate(table.xpath("./tr|./thead/tr|./tbody/tr|./tfoot/tr")):
        row: list[str] = []
        c = 0
        for cell in tr.xpath("./td|./th"):
            while (r, c) in carry:
                row.append(carry.pop((r, c)))
                c += 1
            txt = _norm(" ".join(t for t in cell.itertext()))
            cs = int(cell.get("colspan") or 1)
            rs = int(cell.get("rowspan") or 1)
            for k in range(cs):
                row.append(txt)
                for d in range(1, rs):
                    carry[(r + d, c + k)] = txt
            c += cs
        while (r, c) in carry:
            row.append(carry.pop((r, c)))
            c += 1
        out.append(row)
    w = max((len(x) for x in out), default=0)
    return [x + [""] * (w - len(x)) for x in out]


@lru_cache(maxsize=None)
def _doc_tables(key: str) -> tuple[tuple[tuple[str, ...], ...], ...]:
    doc = lxml.html.fromstring(raw_path(key).read_bytes())
    res = []
    for t in doc.iter("table"):
        if t.xpath(".//table"):  # layout container
            continue
        g = _expand(t)
        if g:
            res.append(tuple(tuple(r) for r in g))
    return tuple(res)


@lru_cache(maxsize=None)
def _page_text(key: str) -> str:
    doc = lxml.html.fromstring(raw_path(key).read_bytes())
    for bad in doc.xpath("//script|//style"):
        bad.getparent().remove(bad)
    return _norm(" ".join(doc.itertext()))


def _pdf_text(key: str) -> str:
    return _norm(" ".join((p.extract_text() or "") for p in PdfReader(str(raw_path(key))).pages))


_NUM = re.compile(r"^\(?-?[\d,]*\.?\d+\)?$")


def num(cell: str) -> float | None:
    s = _norm(cell)
    # XII.1 'Total Expenditure' cells carry a trailing footnote number: '1,29,800.68 4'
    m = re.fullmatch(r"(-?[\d,]+\.\d{2}) \d{1,2}", s)
    if m:
        s = m.group(1)
    s = s.replace(" ", "")
    if s in ("", "-", "–", "NA", "n.a.", ".."):
        return None
    if not _NUM.match(s):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace(",", "")
    v = float(s)
    return -v if neg else v


def label_key(s: str) -> str:
    s = _norm(s).lower()
    s = re.sub(r"\s+\d$", "", s)  # footnote marker at the end ('... fund 1')
    return s


# --------------------------------------------------------------------------------------------- table lookup
def _file_key(ds: str, table_id: str, vintage: str) -> str:
    if ds == "rbi_accounts":
        return f"rbi_annual_report/{AR_FILES[vintage]}_ch12_accounts.html"
    ed = RTP_FILES[vintage]
    m = re.match(r"Appendix Table VI\.(\d+)", table_id)
    if m:
        return f"rbi_trend_progress/{ed}_app_vi_{m.group(1)}.html"
    chap = {"IV": 4, "V": 5, "VI": 6}[re.match(r"Table ([IV]+)\.", table_id).group(1)]
    return f"rbi_trend_progress/{ed}_ch{chap}.html"


def find_table(key: str, table_id: str) -> list[tuple[str, ...]]:
    tabs = _doc_tables(key)
    if table_id.startswith("Appendix Table"):
        # the appendix page holds one data table; its caption sits above it on the page
        assert table_id + ":" in _page_text(key), (key, table_id)
        big = [t for t in tabs if len(t) > 10]
        assert len(big) == 1, (key, len(big))
        return list(big[0])
    if table_id.startswith("Schedule"):
        pat = "SCHEDULES FORMING PART"
    elif table_id == "Income Statement":
        pat = "INCOME STATEMENT FOR THE YEAR"
    elif table_id == "Balance Sheet":
        pat = "BALANCE SHEET AS ON"
    else:
        pat = table_id + ":"
    hits = [t for t in tabs if pat in t[0][0] and len(t[0][0]) < 300]
    assert len(hits) == 1, (key, table_id, len(hits))
    g = list(hits[0])
    if table_id.startswith("Schedule"):
        n = int(table_id.split()[1])
        start = next(i for i, r in enumerate(g) if r[0] == f"Schedule {n}:")
        end = next((i for i in range(start + 1, len(g)) if g[i][0].startswith("Schedule ")), len(g))
        # keep the header rows (years) plus the schedule block
        head = [r for r in g[:start] if any(re.fullmatch(r"\d{4}-\d{2}", c) for c in r)]
        return head + g[start:end]
    return g


# --------------------------------------------------------------------------------------------- column logic
INST = {
    "psb": r"public sector banks|\bpsbs\b",
    "pvb": r"private sector banks|\bpvbs\b",
    "fb": r"foreign banks|\bfbs\b",
    "sfb": r"small finance banks|\bsfbs\b",
    "pb": r"payments banks|\bpbs\b",
    "scb": r"all scbs|^scbs$|(?:^|\| )scbs(?: \||$)|all scheduled commercial banks|^scheduled commercial banks|\| scheduled commercial banks",
    "ucb_scheduled": r"(?<!non-)scheduled ucbs",
    "ucb_nonscheduled": r"non-scheduled ucbs",
    "ucb": r"all ucbs",
    "nbfc": r"nbfc[- ]sector|\bnbfcs\b",
    "nbfc_ul": r"nbfc-ul",
    "nbfc_ml": r"nbfc-ml",
}
SINGLE = {"rbi", "rrb", "lab", "aifi", "hfc", "spd", "stcb", "dccb"}
EXCLUDE_COL = re.compile(r"variation|growth|absolute|\bh1\b|h1:|apr|sep|oct|nov|per cent\)|\(%\)", re.I)


def period_tokens(period: str, ptype: str) -> list[str]:
    if ptype == "fy":
        return [re.escape(period)]
    y = int(period[:4])
    assert period.endswith("-03-31"), period
    return [rf"(?<![\d-]){y}(?![\d-])", re.escape(f"{y - 1}-{str(y)[2:]}"), rf"march 31, {y}", rf"mar-{str(y)[2:]}"]


def header_rows(g: list[tuple[str, ...]], first_data: int) -> list[str]:
    """Header text above each column; caption / unit rows that span the whole width are skipped."""
    w = len(g[0])
    rows = [r for r in range(first_data) if len(set(g[r])) > 1
            and not all(re.fullmatch(r"\d*", c) for c in g[r])]  # caption rows, column-number row
    return [" | ".join(dict.fromkeys(g[r][c] for r in rows if g[r][c])).lower() for c in range(w)]


def first_data_row(g) -> int:
    for i, r in enumerate(g):
        if i == 0:
            continue
        nums = [num(c) for c in r[1:]]
        lab = r[0]
        if re.fullmatch(r"\d+", lab.strip() or "x") and all(re.fullmatch(r"\d*", c) for c in r):
            continue  # column-number row
        if any(v is not None and not re.fullmatch(r"(19|20)\d\d", c.strip()) for v, c in zip(nums, r[1:])):
            if not re.fullmatch(r"(19|20)\d\d(-\d\d)?", lab.strip()):
                return i
    raise AssertionError("no data row")


class Unresolved(Exception):
    pass


def locate(rec: dict, ds: str):
    """Return (raw value, where) for one clean row, or raise Unresolved."""
    key = _file_key(ds, rec["table_id"], rec["vintage"])
    g = find_table(key, rec["table_id"])
    fd = first_data_row(g)
    heads = header_rows(g, fd)
    inst = rec["institution"]
    unit = rec["unit"]
    item = rec["item_code"]
    lab = label_key(rec["item_label"])
    if "excl_merger" in item:
        # the unit labels these '<row label> (excl merger)'; RBI prints the figure in parentheses under the row
        assert lab.endswith(" (excl merger)"), lab
        lab = lab[: -len(" (excl merger)")]

    # --- cost / return of funds tables: rows are (bank group, year), columns are measures
    if rec["series_id"].startswith("rtp.scb_cost_return."):
        grp = {"psb": "psbs", "pvb": "pvbs", "fb": "fbs", "sfb": "sfbs", "pb": "pbs", "scb": "all scbs"}[inst]
        cur = None
        for r in g[fd:]:
            if r[0]:
                cur = r[0].lower()
            if cur in (grp, grp.replace("all ", "")) and r[1] == rec["period"]:
                cols = [c for c, h in enumerate(heads) if label_key(h.split(" | ")[-1]) == lab or h.endswith(lab)]
                if len(cols) != 1:
                    raise Unresolved(f"measure column {lab!r} -> {cols}")
                return num(r[cols[0]]), f"{key} {rec['table_id']} row ({cur},{rec['period']}) col {heads[cols[0]]!r}"
        raise Unresolved("cost/return row not found")

    # --- candidate label cells
    cands = []
    for i in range(fd, len(g)):
        for j, cell in enumerate(g[i]):
            if cell and label_key(cell) == lab and (j == 0 or g[i][j - 1] != cell):
                cands.append((i, j))
    if item == "issue_department_assets_total":
        i = next(i for i in range(fd, len(g)) if g[i][0].startswith("Total Liabilities")) - 1
        cands = [(i, 3)]
    # section disambiguation
    sec = None
    m = re.match(r"sch\d+\.([a-d])\.", rec["series_id"])
    if m:
        sec = f"({m.group(1)})"
    if len(cands) > 1 and sec:
        srow = next(i for i in range(len(g)) if any(c.startswith(sec) for c in g[i][:2]))
        after = [x for x in cands if x[0] > srow]
        cands = after[:1]
    if len(cands) > 1:  # level rows vs the same label repeated under 'Financial Ratios (Per cent)'
        rrow = next((i for i in range(fd, len(g)) if re.search(r"ratios", " ".join(g[i][:2]), re.I)), len(g))
        cands = [x for x in cands if (x[0] > rrow) == (unit == "percent")]
    if len(cands) > 1 and rec["table_id"] == "Income Statement":
        erow = next(i for i in range(len(g)) if g[i][0] == "EXPENDITURE")
        want_exp = item.startswith("exp_") or item == "expenditure_total"
        cands = [x for x in cands if (x[0] > erow) == want_exp]
    if len(cands) > 1 and rec["table_id"] == "Balance Sheet":
        side_col = 0 if rec["side"] == "liabilities" else 4
        cands = [x for x in cands if x[1] == side_col]
    if len(cands) != 1:
        raise Unresolved(f"label {lab!r}: {len(cands)} candidate cells")
    i, j = cands[0]
    row = g[i]
    if "excl_merger" in item:
        row = g[i + 1]  # the parenthesised merger-excluded figure printed under the level
        if not any(c.startswith("(") for c in row):
            raise Unresolved("no merger-excluded row")

    # --- column: header must name the period (and the group where the table has groups)
    ptoks = period_tokens(rec["period"], rec["period_type"])
    # the group filter applies only where the table's headers name groups (single-entity tables do not)
    grouped = inst in INST and inst not in SINGLE and any(re.search(INST[inst], h) for h in heads)
    cols = []
    for c in range(j + 1, len(heads)):
        h = heads[c]
        if EXCLUDE_COL.search(h):
            continue
        if rec["table_id"] == "Balance Sheet" and c > 3 and j < 4 and rec["side"] == "liabilities":
            continue
        if not any(re.search(t, h) for t in ptoks):
            continue
        if grouped and "Table VI.3" != rec["table_id"]:
            if not re.search(INST[inst], h):
                continue
        if rec["table_id"] == "Table VI.3":
            if inst not in INST or not re.search(INST[inst], h):
                continue
            want = {"count": "number", "INR_crore": "asset size", "percent": "asset share"}[unit]
            if want not in h:
                continue
        cols.append(c)
    if rec["table_id"] == "Table VI.3":  # single-date table: no year in the column header
        cols = []
        for c in range(j + 1, len(heads)):
            h = heads[c]
            want = {"count": "number", "INR_crore": "asset size", "percent": "asset share"}[unit]
            if re.search(INST[inst], h) and want in h:
                cols.append(c)
    if inst in ("scb",) and len(cols) > 1:  # 'All SCBs' vs group names containing 'SCBs'
        cols = [c for c in cols if re.search(r"all scbs|scheduled commercial banks|(?:^|\| )scbs(?: \||$)", heads[c])]
    if len(cols) != 1:
        raise Unresolved(f"period/group column for {rec['period']} {inst}: {[heads[c] for c in cols]}")
    cell = row[cols[0]]
    if "excl_merger" in item:  # '(74,51,388)': parentheses mark the merger-excluded figure, not a sign
        if not re.fullmatch(r"\([\d,]+\)", cell):
            raise Unresolved(f"merger-excluded cell {cell!r}")
        cell = cell.strip("()")
    return num(cell), f"{key} {rec['table_id']} r{i} '{g[i][j]}' col '{heads[cols[0]]}'"


# --------------------------------------------------------------------------------------------- clean data
TABLE_DATASETS = ["rbi_accounts", "rtp_banks", "rtp_coop", "rtp_nbfi"]


@lru_cache(maxsize=None)
def clean(ds: str) -> list[dict]:
    p = CLEAN / f"{UNIT}_{ds}.parquet"
    if not p.exists():
        pytest.skip(f"{p} missing: run `pipeline build {UNIT}`")
    return pq.read_table(p).to_pylist()


def test_every_table_value_matches_raw():
    bad, unresolved, n = [], [], 0
    for ds in TABLE_DATASETS:
        for rec in clean(ds):
            try:
                v, where = locate(rec, ds)
            except Unresolved as e:
                unresolved.append((ds, rec["series_id"], rec["period"], rec["vintage"], str(e)))
                continue
            n += 1
            if v is None or abs(v - rec["value"]) > TOL:
                bad.append((ds, rec["series_id"], rec["period"], rec["vintage"], rec["value"], v, where))
    print(f"compared {n} table values; unresolved {len(unresolved)}; mismatched {len(bad)}")
    print(Counter((u[0], u[1].split(".")[0] + "." + u[1].split(".")[1], u[3]) for u in unresolved).most_common(60))
    for u in unresolved[:15]:
        print("UNRESOLVED", u)
    for b in bad[:40]:
        print("MISMATCH", b)
    assert not bad
    assert not unresolved


# --------------------------------------------------------------------------------------------- sensitivity
def test_checker_detects_mutations():
    """The comparison above must be able to fail: perturbed values, shifted periods and swapped bank
    groups must not resolve to the same raw cell."""
    rng = random.Random(SEED)
    recs = [(ds, r) for ds in TABLE_DATASETS for r in clean(ds)]
    sample = rng.sample(recs, 300)
    swap = {"psb": "pvb", "pvb": "psb", "fb": "sfb", "sfb": "fb", "pb": "scb", "scb": "psb", "ucb": "ucb_scheduled",
            "ucb_scheduled": "ucb_nonscheduled", "ucb_nonscheduled": "ucb", "nbfc": "nbfc_ul", "nbfc_ul": "nbfc_ml",
            "nbfc_ml": "nbfc"}
    n_val = n_per = n_inst = 0
    for ds, r in sample:
        v, where = locate(r, ds)
        assert abs(v - (r["value"] * 1.01 + 1)) > TOL  # a perturbed value never matches
        n_val += 1
        # shift the period by one year (fy 2023-24 -> 2022-23; date 2024-03-31 -> 2023-03-31)
        y = int(r["period"][:4]) - 1
        per = f"{y}-{str(y + 1)[2:]}" if r["period_type"] == "fy" else f"{y}-03-31"
        if r["table_id"] != "Table VI.3":  # single-date table: its date is checked from the caption below
            try:
                _, w2 = locate({**r, "period": per}, ds)
                assert w2 != where, (r["series_id"], r["period"], where)
            except Unresolved:
                pass
            n_per += 1
        if r["institution"] in swap and not r["series_id"].startswith("rtp.scb_cost_return.") and r["table_id"] != "Table VI.3":
            key = _file_key(ds, r["table_id"], r["vintage"])
            g = find_table(key, r["table_id"])
            heads = header_rows(g, first_data_row(g))
            if any(re.search(INST[r["institution"]], h) for h in heads):  # grouped table
                try:
                    _, w3 = locate({**r, "institution": swap[r["institution"]]}, ds)
                    assert w3 != where, (r["series_id"], where)
                except Unresolved:
                    pass
                n_inst += 1
    print(f"mutations: value {n_val}, period {n_per}, bank-group {n_inst}")
    assert n_val == 300 and n_inst >= 50


# --------------------------------------------------------------------------------------------- derived rows
def test_derived_surplus_timing_recomputed_from_raw():
    rows = clean("rbi_surplus_timing")
    assert len(rows) == 8
    # R6: XII.1 of the 2025-26 edition, 'Surplus transferred' by accounting year t -> cash in fiscal year t+1
    g = find_table("rbi_annual_report/ar2526_ch12_accounts.html", "Table XII.1")
    fd = first_data_row(g)
    heads = header_rows(g, fd)
    srow = next(r for r in g if r[0].startswith("e) Surplus transferred"))
    cash = {}
    for c, h in enumerate(heads):
        m = re.fullmatch(r"(\d{4})-(\d{2})", h.split(" | ")[-1])
        if m and c > 0:
            y = int(m.group(1)) + 1
            cash[f"{y}-{str(y + 1)[2:]}"] = num(srow[c])
    r6 = {r["period"]: r["value"] for r in rows if r["series_id"] == "r6.surplus_received_by_centre_cash.current"}
    assert r6 == cash, (r6, cash)
    assert r6["2023-24"] == 87416.22  # gap map R6 / DECISIONS D0-7
    # K9b: Schedule 4 '(iv) Surplus payable to the Central Government', end-March t minus end-March t-1
    k9b = {r["period"]: r["value"] for r in rows if r["series_id"] == "k9b.change_in_surplus_payable.current"}
    for ed in AR_FILES.values():
        g = find_table(f"rbi_annual_report/{ed}_ch12_accounts.html", "Schedule 4")
        row = next(r for r in g if "Surplus payable to the Central Government" in r[1])
        vals = [num(x) for x in row[2:] if num(x) is not None]
        assert len(vals) == 2
        fy = f"20{ed[2:4]}-{ed[4:6]}"
        assert abs(k9b[fy] - round(vals[1] - vals[0], 2)) < TOL, (fy, k9b[fy], vals)
    assert abs(k9b["2023-24"] - 123457.77) < TOL  # gap map K9b: 2,10,874 - 87,416 = 1,23,458


# --------------------------------------------------------------------------------------------- press releases
# pattern -> the (series_id, period) of each captured figure, in order. Whitespace is removed from both
# the text and the pattern first (pypdf inserts stray spaces: '2023 -24').
PR = {
    "bsr1_mar2024": ("rbi_bsr/bsr1_mar2024_pr.html", "rbi_bsr/bsr1_mar2024_pr_annex.pdf", [
        (r"increased by ([\d.]+) per cent, net of merger\d? \(([\d.]+) per cent including the merger impact\) during"
         r" 2023-24 as compared to ([\d.]+) per cent rise in the previous financial year",
         [("bsr1.credit_growth_net_of_merger.scb", "2023-24"), ("bsr1.credit_growth_incl_merger.scb", "2023-24"),
          ("bsr1.credit_growth_incl_merger.scb", "2022-23")]),
        (r"Individuals in the household sector accounted for ([\d.]+) per cent of total bank credit in March 2024",
         [("bsr1.share_credit_individuals.scb", "2024-03-31")]),
        (r"partnership firms\} had another ([\d.]+) per cent share", [("bsr1.share_credit_other_households.scb", "2024-03-31")]),
        (r"personal loans in total bank credit, which has been consistently rising, stood at ([\d.]+) per cent in March 2024",
         [("bsr1.share_credit_personal_loans.scb", "2024-03-31")]),
        (r"share of industry declined to ([\d.]+) per cent", [("bsr1.share_credit_industry.scb", "2024-03-31")]),
        (r"their share in total credit by SCBs rose to ([\d.]+) per cent in March 2024",
         [("bsr1.share_credit_by_group.pvb", "2024-03-31")]),
        (r"share of public sector banks declined to ([\d.]+) per cent", [("bsr1.share_credit_by_group.psb", "2024-03-31")]),
        (r"small finance banks resulted in their share in total credit by SCBs rising to ([\d.]+) per cent in March 2024",
         [("bsr1.share_credit_by_group.sfb", "2024-03-31")]),
    ]),
    "pcbs_2324": ("rbi_corporate_finances/pcbs_2023_24_pr.html", "rbi_corporate_finances/pcbs_2023_24_pr_annex.pdf", [
        (r"abridged financial results of ([\d,]+) listed non-government non-financial", [("pcbs.sample_companies.all", "2023-24")]),
        (r"moderated to ([\d.]+) per cent during 2023-24 from the high of ([\d.]+) per cent in 2022-23",
         [("pcbs.sales_growth.all", "2023-24"), ("pcbs.sales_growth.all", "2022-23")]),
        (r"non-IT services companies rose by ([\d.]+) per cent, ([\d.]+) per cent and ([\d.]+) per cent, respectively, during"
         r" 2023-24 as compared with ([\d.]+) per cent, ([\d.]+) per cent and ([\d.]+) per cent",
         [("pcbs.sales_growth.manufacturing", "2023-24"), ("pcbs.sales_growth.it_services", "2023-24"),
          ("pcbs.sales_growth.non_it_services", "2023-24"), ("pcbs.sales_growth.manufacturing", "2022-23"),
          ("pcbs.sales_growth.it_services", "2022-23"), ("pcbs.sales_growth.non_it_services", "2022-23")]),
        (r"raw material to sales ratio moderated to ([\d.]+) per cent in 2023-24 from ([\d.]+) per cent a year ago",
         [("pcbs.raw_material_to_sales.manufacturing", "2023-24"), ("pcbs.raw_material_to_sales.manufacturing", "2022-23")]),
        (r"Staff cost rose by ([\d.]+) per cent, ([\d.]+) per cent and ([\d.]+) per cent \(y-o-y\) during 2023-24 for"
         r" manufacturing, IT and non-IT services",
         [("pcbs.staff_cost_growth.manufacturing", "2023-24"), ("pcbs.staff_cost_growth.it_services", "2023-24"),
          ("pcbs.staff_cost_growth.non_it_services", "2023-24")]),
        (r"accelerated for manufacturing companies \(([\d.]+) per cent\) and non-IT services companies \(([\d.]+) per cent\)"
         r" ?, while it moderated for IT companies \(([\d.]+) per cent\)",
         [("pcbs.operating_profit_growth.manufacturing", "2023-24"), ("pcbs.operating_profit_growth.non_it_services", "2023-24"),
          ("pcbs.operating_profit_growth.it_services", "2023-24")]),
        (r"it stood at ([\d.]+) per cent, ([\d.]+) per cent and ([\d.]+) per cent for manufacturing, non-IT services and IT",
         [("pcbs.operating_profit_margin.manufacturing", "2023-24"), ("pcbs.operating_profit_margin.non_it_services", "2023-24"),
          ("pcbs.operating_profit_margin.it_services", "2023-24")]),
    ]),
}


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", _norm(s))


def _pattern(p: str) -> str:
    return re.sub(r"(?<!\\) ", "", p)


@pytest.mark.parametrize("ds", sorted(PR))
def test_press_release_values_in_html_and_pdf(ds):
    html_key, pdf_key, pats = PR[ds]
    got = {(r["series_id"], r["period"]): r["value"] for r in clean(ds)}
    for label, text in (("html", _page_text(html_key)), ("pdf", _pdf_text(pdf_key))):
        t = _squash(text)
        seen = {}
        for pat, targets in pats:
            m = re.search(_pattern(pat), t)
            assert m, (label, pat)
            for (sid, per), val in zip(targets, m.groups()):
                seen[(sid, per)] = float(val.replace(",", ""))
        diff = {k: (seen.get(k), got.get(k)) for k in set(seen) | set(got) if seen.get(k) != got.get(k)}
        assert not diff, (label, diff)
    print(f"{ds}: {len(got)} values matched in the HTML page text and in the PDF text")


# --------------------------------------------------------------------------------------------- provenance, units
def test_provenance_points_at_the_page_the_value_came_from():
    prov = {r["prov_id"]: r for r in pq.read_table(CLEAN / "_provenance.parquet").to_pylist()}
    pins = _pins()
    bad = []
    for ds in TABLE_DATASETS:
        for r in clean(ds):
            p = prov[r["prov_id"]]
            key = _file_key(ds, r["table_id"], r["vintage"])
            if p["url"] != pins[key]["url"] or p["raw_sha256"] != pins[key]["sha256"]:
                bad.append((r["series_id"], r["vintage"], p["url"], pins[key]["url"]))
            tid = r["table_id"]
            if not (p["table_id"] == tid or (tid.startswith("Schedule") and p["table_id"].startswith("Schedules"))):
                bad.append((r["series_id"], "table_id", p["table_id"], tid))
            if p["vintage"] != r["vintage"] or p["status"] != "official" or r["status"] != "official":
                bad.append((r["series_id"], "vintage/status"))
    assert not bad, bad[:10]


def test_table_captions_state_the_units_used():
    """Scale check: INR rows must come from tables captioned in Rs crore (not lakh / thousand crore /
    million); percent rows from 'Per cent' tables, or ratio rows of tables that say so in the row."""
    bad = []
    seen = set()
    for ds in TABLE_DATASETS:
        for r in clean(ds):
            key = _file_key(ds, r["table_id"], r["vintage"])
            if (key, r["table_id"], r["unit"]) in seen:
                continue
            seen.add((key, r["table_id"], r["unit"]))
            if r["table_id"].startswith("Schedule"):
                g = next(t for t in _doc_tables(key) if "SCHEDULES FORMING" in t[0][0])
            else:
                g = find_table(key, r["table_id"])
            head = " ".join(" ".join(x) for x in g[:4]).lower()
            if r["table_id"].startswith("Appendix"):
                head += " " + _page_text(key)[:3000].lower()
            if r["unit"] == "INR_crore":
                if "crore" not in head or re.search(r"lakh crore|'000 crore|thousand crore|million|billion", head):
                    bad.append((key, r["table_id"], r["unit"], head[:120]))
            elif r["unit"] == "percent":
                if not re.search(r"per cent|percent", head):
                    rowtxt = " ".join(" ".join(x) for x in g).lower()
                    if not re.search(r"per ?cent|margin", rowtxt):
                        bad.append((key, r["table_id"], r["unit"], head[:120]))
    assert not bad, bad


def test_period_of_single_date_tables():
    """Table VI.3 has no year column: its date comes from the caption '(At end-March YYYY)'."""
    for r in clean("rtp_nbfi"):
        if r["table_id"] == "Table VI.3":
            key = _file_key("rtp_nbfi", r["table_id"], r["vintage"])
            cap = " ".join(" ".join(x) for x in find_table(key, "Table VI.3")[:3])
            assert f"end-March {r['period'][:4]}" in cap, (r["period"], cap[:120])


# --------------------------------------------------------------------------------------------- sample for the notes
def test_print_seeded_sample():
    """Seeded, stratified 10% sample (every dataset x table x vintage x unit stratum), printed with the
    raw cell each value was matched to, for docs/phase1/verify/rbi_banking_corporate.md. (The exhaustive
    test above already compares every row; this is the reproducible sample quoted in the notes.)"""
    rng = random.Random(SEED)
    strata: dict[tuple, list] = {}
    for ds in TABLE_DATASETS:
        for r in clean(ds):
            strata.setdefault((ds, r["table_id"], r["vintage"], r["unit"]), []).append(r)
    picked = []
    for k in sorted(strata):
        rows = strata[k]
        n = max(1, round(len(rows) * 0.10))
        picked += [(k[0], r) for r in rng.sample(rows, n)]
    ok = 0
    lines = []
    for ds, r in picked:
        v, where = locate(r, ds)
        ok += abs(v - r["value"]) <= TOL
        lines.append(f"  {r['series_id']} | {r['period']} | v{r['vintage']} | clean {r['value']} | raw {v} | {where}")
    print(f"sample: {len(picked)} rows in {len(strata)} strata, {ok} match")
    for x in lines[:: max(1, len(lines) // 30)]:
        print(x)
    assert ok == len(picked)


def test_balance_sheet_side_matches_the_half_of_the_statement():
    """'side' = liabilities for labels printed in the left half of the RBI balance sheet, assets for the right."""
    bad = []
    for r in clean("rbi_accounts"):
        if r["table_id"] != "Balance Sheet" or r["item_code"] == "issue_department_assets_total":
            continue
        g = find_table(_file_key("rbi_accounts", "Balance Sheet", r["vintage"]), "Balance Sheet")
        pos = {j for row in g for j, c in enumerate(row) if label_key(c) == label_key(r["item_label"])}
        side = "liabilities" if min(pos) < 4 else "assets"
        if side != r["side"]:
            bad.append((r["series_id"], r["side"], pos))
    assert not bad, bad
