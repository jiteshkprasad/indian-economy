"""Independent verification of the external_sector unit (Phase 1, verifier first pass, 2026-09-29).

This file does NOT import the unit's code (pipeline.ingest.external_sector). It re-reads the pinned raw
HTML pages directly with lxml (the unit uses BeautifulSoup) and its own colspan/rowspan expansion,
number parser, period mapping, column finder and row locator, and compares against
data/clean/external_sector/*.parquet read with DuckDB (the unit writes with polars).

Method
- Every raw file's sha256 is checked against data/raw_pins/external_sector.yaml.
- A stratified random sample (seed 20260929) of every dataset: 15% of rows, at least 40 per dataset
  (all rows when fewer), stratified by (unit, period_type, vintage/table) so every edition, unit of
  measure and period type is drawn. Plus every gap-map-critical series named in the unit's coverage
  yaml for its covered period (or 2023-24). Each sampled clean row is located in the raw page by
  LABEL (item number, printed label + parent label, scheme/column header), never by the unit's row
  order, and compared to the raw cell after the documented unit conversion.
- Derived rows (LRS Rs crore) are recomputed from raw US$ and the raw T133 FY-average rate.
- Hand anchors: a few literal numbers typed from the page text (not produced by any parser).
- Completeness: the number of numeric cells printed in each BPM6 / invisibles / NRI / T143 / T144 /
  IIP table equals the number of clean rows drawn from it (catches dropped rows or columns).

Close-out pass (2026-09-29, same verifier role, after the builder's V1-V4 fixes and follow-up):
- Stale expectations updated only where re-derived from the raw pages: 45 pins (FLA 2023-24 round
  added), LRS derived rows counted from the raw April column (33), FLA located in the file of the
  row's round (vintage = the page's printed release date), the FLA 3B hand anchor split by round
  (726,558 first estimate vs 742,228 revised, both typed from the pages), and the ECB 'Grand total'
  rows (V2 fix) located by their printed label.
- New: estimate stages of every IIP and debt-release row re-derived from the raw period flags and
  the raw footnote legend ('PR: Partially Revised'); a seeded sample (>=10%, min 30) of the 804
  rows the follow-up changed, checked for value, stage and geography; remittance-survey State codes
  checked against a hand-typed ISO 3166-2:IN list (D1-9) with the historical IN-XJK rule; FLA
  completeness per round; the INR/USD guide's coverage and conversion claims.
"""

from __future__ import annotations

import hashlib
import math
import random
import re
from collections import defaultdict
from functools import cache
from pathlib import Path

import duckdb
import pytest
import yaml
from lxml import html

pytestmark = pytest.mark.quality

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean" / "external_sector"
PINS = ROOT / "data" / "raw_pins" / "external_sector.yaml"
COVERAGE = ROOT / "pipeline" / "ingest" / "external_sector_coverage.yaml"
SEED = 20260929
FRACTION = 0.15
MIN_PER_DATASET = 40

DATASETS = [
    "fx_inr_usd", "bop_bpm6_annual", "bop_bpm6_quarterly", "bop_overall_annual", "invisibles_annual",
    "nri_deposits", "foreign_investment", "fx_reserves", "external_debt", "external_debt_by_sector",
    "iip_quarterly", "ecb_monthly_2324", "fla_census", "remittance_survey", "ites_survey", "lrs_outward",
]  # fmt: skip


# ------------------------------------------------------------------------------------------------
# independent raw readers
# ------------------------------------------------------------------------------------------------


@cache
def pins() -> dict:
    return yaml.safe_load(PINS.read_text(encoding="utf-8"))["pins"]


def raw(key: str) -> Path:
    """key = '<source_id>/<name>' -> pinned local path."""
    return ROOT / pins()[key]["path"]


def by_name(name: str) -> Path:
    hits = [k for k in pins() if k.endswith("/" + name)]
    assert len(hits) == 1, name
    return raw(hits[0])


@cache
def grids(path: Path) -> tuple[tuple[tuple[str, ...], ...], ...]:
    """Innermost <table>s as grids, colspan and rowspan expanded (verifier's own implementation)."""
    root = html.parse(str(path)).getroot()
    out = []
    for tb in root.iter("table"):
        if tb.find(".//table") is not None:
            continue
        g, carry = [], {}
        for r, tr in enumerate(tb.iter("tr")):
            row, c = [], 0
            for cell in [x for x in tr if x.tag in ("td", "th")]:
                while (r, c) in carry:
                    row.append(carry.pop((r, c)))
                    c += 1
                t = " ".join(cell.text_content().split())
                cs, rs = int(cell.get("colspan") or 1), int(cell.get("rowspan") or 1)
                for k in range(cs):
                    row.append(t)
                    for d in range(1, rs):
                        carry[(r + d, c + k)] = t
                c += cs
            while (r, c) in carry:
                row.append(carry.pop((r, c)))
                c += 1
            g.append(tuple(row))
        out.append(tuple(g))
    return tuple(out)


@cache
def page_text(path: Path) -> str:
    return " ".join(html.parse(str(path)).getroot().text_content().split())


MISSING = {"", "-", "–", "—", "nil", "n.a.", "na", "..."}


def pnum(s: str, paren_positive: bool = False) -> float | None:
    s = s.strip().replace(",", "").replace("−", "-").rstrip("#*").strip()
    if paren_positive and s.startswith("(") and s.endswith(")"):
        s = s[1:-1]
    if s.lower() in MISSING:
        return None
    return float(s)


def nrm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def colnum_row(g) -> int:
    for i, r in enumerate(g):
        v = [x for x in r if x]
        if v and v[0] == "1" and all(re.fullmatch(r"\d+", x) for x in v):
            return i
    raise AssertionError("no column-number row")


def grid_titled(path: Path, prefix: str):
    hits = [g for g in grids(path) if g and g[0] and g[0][0].startswith(prefix)]
    assert len(hits) == 1, (path.name, prefix, len(hits))
    return hits[0]


# ------------------------------------------------------------------------------------------------
# clean data
# ------------------------------------------------------------------------------------------------


@cache
def clean(ds: str) -> list[dict]:
    p = CLEAN / f"external_sector_{ds}.parquet"
    rel = duckdb.sql(f"select * from read_parquet('{p.as_posix()}') order by series_id, vintage, period")
    cols = rel.columns
    return [dict(zip(cols, t, strict=True)) for t in rel.fetchall()]


@cache
def labels_by_code(ds: str, table: str, unit: str) -> dict[str, str]:
    out = {}
    for r in clean(ds):
        if r["table_id"] == table and (r["unit"] == unit or r["unit"] == "percent"):
            out[r["item_code"]] = r["item_label"]
    return out


# ------------------------------------------------------------------------------------------------
# locators: clean row -> list of (raw value, note); value already in the clean unit
# ------------------------------------------------------------------------------------------------

HBS = {
    ("bop_bpm6_annual", "USD_million", "2026-07-31"): "hbs2026_t126.html",
    ("bop_bpm6_annual", "INR_crore", "2026-07-31"): "hbs2026_t127.html",
    ("bop_bpm6_quarterly", "USD_million", "2025-08-29"): "hbs2025_t196.html",
    ("bop_bpm6_quarterly", "INR_crore", "2025-08-29"): "hbs2025_t197.html",
    ("bop_bpm6_quarterly", "USD_million", "2026-07-31"): "hbs2026_t197.html",
    ("bop_bpm6_quarterly", "INR_crore", "2026-07-31"): "hbs2026_t198.html",
    ("bop_overall_annual", "USD_million", "2026-07-31"): "hbs2026_t124.html",
    ("bop_overall_annual", "INR_crore", "2026-07-31"): "hbs2026_t125.html",
    ("invisibles_annual", "USD_million", "2026-07-31"): "hbs2026_t130.html",
    ("invisibles_annual", "INR_crore", "2026-07-31"): "hbs2026_t131.html",
    ("iip_quarterly", "USD_million", "2025-08-29"): "hbs2025_t198.html",
    ("iip_quarterly", "INR_crore", "2025-08-29"): "hbs2025_t199.html",
    ("iip_quarterly", "USD_million", "2026-07-31"): "hbs2026_t199.html",
    ("iip_quarterly", "INR_crore", "2026-07-31"): "hbs2026_t200.html",
}
QMONTHS = {1: ("April-June", 0), 2: ("July-September", 0), 3: ("October-December", 0), 4: ("January-March", 1)}
MONTH_ABBR = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def fy_of_march(date: str) -> str:
    y = int(date[:4])
    return f"{y - 1}-{str(y)[2:]}"


def q_header(period: str) -> str:
    m = re.fullmatch(r"Q([1-4]) (\d{4})-\d{2}", period)
    name, dy = QMONTHS[int(m.group(1))]
    return f"{name} {int(m.group(2)) + dy}"


def find_cdn_column(g, period_text: str, side: str) -> int | None:
    """Column of (period header, Credit/Debit/Net) in an HBS grid; None if the grid lacks the period."""
    for i, r in enumerate(g):
        if r and r[0].lower().startswith("item") and period_text in r:
            sides = g[i + 1]
            for c in range(1, len(r)):
                if r[c] == period_text and sides[c].lower() == side:
                    return c
    return None


def loc_bpm6(row: dict) -> float:
    path = by_name(HBS[(row["dataset"].removeprefix("external_sector_"), row["unit"], row["vintage"])])
    number = row["item_code"].removeprefix("bpm6_").replace("_", ".")
    ptext = row["period"] if row["period_type"] == "fy" else q_header(row["period"])
    for g in grids(path):
        c = find_cdn_column(g, ptext, row["side"])
        if c is None:
            continue
        hits = [r for r in g if r and " " in r[0] and r[0].split(" ")[0].lower() == number]
        assert len(hits) == 1, (path.name, number, len(hits))
        lab = hits[0][0].split(" ", 1)[1]
        assert nrm(lab) == nrm(row["item_label"]), (lab, row["item_label"])
        return pnum(hits[0][c])
    raise AssertionError(f"{path.name}: period {ptext} not found")


def hier_index(body: list, code: str, labels: dict[str, str]) -> int:
    """Row index of `code` in body: by its printed label; if the label repeats, the first occurrence
    after its parent's row (parent located the same way, recursively)."""
    want = nrm(labels[code])
    cand = [i for i, r in enumerate(body) if nrm(r[0]) == want]
    assert cand, (code, labels[code])
    if len(cand) == 1:
        return cand[0]
    parent = code
    while "." in parent:
        parent = parent.rsplit(".", 1)[0]
        if parent in labels:
            p = hier_index(body, parent, labels)
            return min(i for i in cand if i > p)
    return cand[0]


def loc_bop_old(row: dict) -> float:
    path = by_name(HBS[("bop_overall_annual", row["unit"], row["vintage"])])
    labels = labels_by_code("bop_overall_annual", row["table_id"], row["unit"])
    for g in grids(path):
        c = find_cdn_column(g, row["period"], row["side"])
        if c is None:
            continue
        k = colnum_row(g)
        body = list(g[k + 1 :])
        return pnum(body[hier_index(body, row["item_code"], labels)][c])
    raise AssertionError("period not found")


def loc_invisibles(row: dict) -> float:
    path = by_name(HBS[("invisibles_annual", row["unit"], row["vintage"])])
    for g in grids(path):
        hdr = next((r for r in g if r and r[0].lower().startswith("item")), None)
        if hdr is None or row["period"] not in hdr:
            continue
        c = hdr.index(row["period"])
        want = nrm(row["item_label"])
        hits = [i for i, r in enumerate(g) if r and nrm(r[0].replace(", Net", "")) == want]
        assert len(hits) == 1, row["item_label"]
        off = {"net": 0, "receipts": 1, "payments": 2}[row["side"]]
        assert g[hits[0] + off][0] == {"net": g[hits[0]][0], "receipts": "Receipts", "payments": "Payments"}[row["side"]]
        return pnum(g[hits[0] + off][c])
    raise AssertionError("period not found")


FX_MONTHS = {m: i for i, m in enumerate(MONTH_ABBR, 1)}


def loc_fx(row: dict) -> float:
    sid = row["series_id"]
    if sid.startswith("t133."):
        g = grids(by_name("hbs2026_t133.html"))[0]
        kind = "Average" if sid.endswith("fy_average") else "End-year"
        fy = row["period"] if row["period_type"] == "fy" else fy_of_march(row["period"])
    else:
        g = grids(by_name("hbs2026_t205.html"))[0]
        kind = "Average" if sid.endswith("month_average") else "End-month"
    c = next(c for c in range(len(g[1])) if g[1][c] == "US Dollar" and g[2][c] == kind)
    if sid.startswith("t133."):
        (r,) = [r for r in g if r[0] == fy]
        return pnum(r[c])
    y, m = int(row["period"][:4]), int(row["period"][5:7])
    year = None
    for r in g:
        if re.fullmatch(r"\d{4}", r[0]):
            year = int(r[0])
        elif year == y and FX_MONTHS.get(r[0]) == m:
            return pnum(r[c])
    raise AssertionError("month not found")


NRI_FILE = {("stock", "USD_million"): "hbs2026_t139.html", ("stock", "INR_crore"): "hbs2026_t140.html",
            ("flow", "USD_million"): "hbs2026_t141.html", ("flow", "INR_crore"): "hbs2026_t142.html"}  # fmt: skip
NRI_HEAD = {"fcnr_a": "FCNR(A)", "fcnr_b": "FCNR(B)", "nr_e_ra": "NR(E)RA", "nr_nr_rd": "NR(NR)RD", "nro": "NRO",
            "fc_b_o_d": "FC(B&O)D", "fc_o_n": "FC(O)N", "total": "Total"}  # fmt: skip


def loc_nri(row: dict) -> float:
    g = grids(by_name(NRI_FILE[(row["stock_flow"], row["unit"])]))[0]
    c = g[1].index(NRI_HEAD[row["instrument"]])
    key = row["period"][:4] if row["stock_flow"] == "stock" else row["period"]
    (r,) = [r for r in g if r[0] == key]
    return pnum(r[c])


UNIT_HEAD = {"INR_crore": "₹ Crore", "USD_million": "US $ Million"}


def loc_t143(row: dict) -> float:
    g = grids(by_name("hbs2026_t143.html"))[0]
    cols = [c for c in range(1, len(g[0])) if nrm(g[0][c]) == nrm(row["item_label"]) and g[1][c] == UNIT_HEAD[row["unit"]]]
    assert len(cols) == 1, row["item_label"]
    (r,) = [r for r in g if r[0] == row["period"]]
    return pnum(r[cols[0]])


T144_HEAD = {"sdr": "SDRs", "gold": "Gold", "fca": "Foreign Currency Assets", "rtp": "Reserve Tranche Position", "total": "Total"}


def loc_t144(row: dict) -> float:
    g = grids(by_name("hbs2026_t144.html"))[0]
    cols = [c for c in range(1, len(g[0])) if re.sub(r"[#*]", "", g[0][c]).strip() == T144_HEAD[row["instrument"]]
            and g[1][c] == UNIT_HEAD[row["unit"]]]  # fmt: skip
    assert len(cols) == 1
    (r,) = [r for r in g if r[0] == fy_of_march(row["period"])]
    return pnum(r[cols[0]])


def loc_debt(row: dict) -> float:
    if row["unit"] == "percent":
        name = "hbs2026_t145.html" if row["series_id"].startswith("debt.145.") else "hbs2026_t146.html"
        unit = "USD_million" if name.endswith("145.html") else "INR_crore"
    else:
        name = "hbs2026_t145.html" if row["unit"] == "USD_million" else "hbs2026_t146.html"
        unit = row["unit"]
    path = by_name(name)
    assert row["table_id"] == ("Table 145" if name.endswith("145.html") else "Table 146")
    labels = labels_by_code("external_debt", row["table_id"], unit)
    year = row["period"][:4]
    for g in grids(path):
        hdr = next((r for r in g if r and r[0] == "Item"), None)
        if hdr is None or year not in hdr:
            continue
        k = colnum_row(g)
        body = list(g[k + 1 :])
        if not any(nrm(r[0]) == nrm(row["item_label"]) for r in body):
            continue
        return pnum(body[hier_index(body, row["item_code"], labels)][hdr.index(year)])
    raise AssertionError("not found")


def iip_date(h: str) -> str:
    m = re.fullmatch(r"(\d{4})-\d{2}:\s*Q([1-4]).*", h)
    y, q = int(m.group(1)), int(m.group(2))
    return {1: f"{y}-06-30", 2: f"{y}-09-30", 3: f"{y}-12-31", 4: f"{y + 1}-03-31"}[q]


def loc_iip(row: dict) -> float:
    unit = row["unit"]
    if unit == "percent":
        unit = "INR_crore"  # the memo ratio is kept from the rupee page (printed on both)
    g = grids(by_name(HBS[("iip_quarterly", unit, row["vintage"])]))[0]
    hdr = next(r for r in g if r[0] == "Period")
    c = next(c for c in range(1, len(hdr)) if iip_date(hdr[c]) == row["period"])
    code = row["item_code"]
    if code == "niip":
        (r,) = [r for r in g if r[0].startswith("Net International Investment Position")]
    elif code.startswith("memo"):
        (r,) = [r for r in g if r[0].lower().startswith("memo item")]
    else:
        sect, _, num_ = code.partition(".")
        a = next(i for i, r in enumerate(g) if r[0].startswith("A. Assets"))
        b = next(i for i, r in enumerate(g) if r[0].startswith("B. Liabilities"))
        rng = g[a:b] if sect == "assets" else g[b:]
        if not num_:
            r = rng[0]
        elif num_ == "3.5" and not any(x[0].startswith("3.5 ") for x in rng):
            (r,) = [x for x in rng if x[0].lower().startswith("of which: special drawing rights")]
        else:
            (r,) = [x for x in rng if re.match(rf"^{re.escape(num_)}\.?\s", x[0])]
    return pnum(r[c])


def loc_debt_release(row: dict) -> float:
    path = by_name("external_debt_end_march_2026_release.html")
    table = row["table_id"]
    g = grid_titled(path, table + ":")
    k = colnum_row(g)
    pct = row["unit"] == "percent"
    scale = 1.0 if pct else 1000.0
    if table == "Table 5":
        hdr = g[k - 1]
        hname = row["item_label"].split(": ", 1)[1]
        c = hdr.index(hname)
        (r,) = [r for r in g[k + 1 :] if r[0].split(" ")[0] == row["period"][:4]]
        return pnum(r[c], paren_positive=True) * scale
    hdr = g[k - 1]
    c = next(c for c in range(1, len(hdr)) if hdr[c].split(" ")[0] == row["period"][:4])
    body = [r for r in g[k + 1 :]]
    labels = {}
    for r2 in clean("external_debt_by_sector"):
        if r2["table_id"] == table:
            labels[r2["item_code"].removeprefix("external_debt.")] = r2["item_label"]
    idx = hier_index(body, row["item_code"].removeprefix("external_debt."), labels)
    return pnum(body[idx][c], paren_positive=True) * scale


ECB_ROUTE = {"automatic": "AUTOMATIC ROUTE", "approval": "APPROVAL ROUTE"}


def ecb_page(month: str) -> Path:
    return by_name(f"ecb_{month}.html")


def loc_ecb(row: dict) -> float:
    path = ecb_page(row["period"])
    kind = row["series_id"].split(".")[2]
    title = "Data on ECB/FCCB for the month of" if kind == "ecb_fccb" else "Data on RDB for the month of"
    (g,) = [g for g in grids(path) if g and g[0][0].startswith(title)]
    y, m = int(row["period"][:4]), int(row["period"][5:])
    assert g[0][0].endswith(f"{['January','February','March','April','May','June','July','August','September','October','November','December'][m-1]} {y}")
    hdr = next(r for r in g if "Borrower" in r)
    amt = next(i for i, h in enumerate(hdr) if h.startswith("Equivalent Amount in USD"))
    if row["item_code"] == "ecb_registrations_total":
        route = row["series_id"].split(".")[3]
        want = {"automatic": {"totalautomaticroute"}, "approval": {"totalapprovalroute"},
                # Feb/Mar 2024 print 'Grand total' / 'Grand Total' for automatic + approval (V2)
                "all": {"totalautomaticrouteapprovalroute", "grandtotal"}}[route]  # fmt: skip
        hits = [r for r in g if any(re.sub(r"[^a-z]", "", x.lower()) in want for x in r)]
        if not hits and route == "all":  # RDB tables print a bare 'Total' for both routes
            hits = [r for r in g if any(x.strip().lower() == "total" for x in r)]
        assert len(hits) == 1, (path.name, route)
        return pnum(hits[0][amt]) / 1e6
    route = row["series_id"].split(".")[3]
    serial = int(row["series_id"].split(".")[4])
    cur, seq = None, 0
    has_serial = any(re.fullmatch(r"\d+", r[0]) for r in g)
    for r in g:
        if "AUTOMATIC ROUTE" in r[0]:
            cur = "automatic"
            continue
        if "APPROVAL ROUTE" in r[0]:
            cur = "approval"
            continue
        if cur != route or r is hdr or "Borrower" in r:
            continue
        if has_serial and re.fullmatch(r"\d+", r[0]) and int(r[0]) == serial:
            assert nrm(r[hdr.index("Borrower")]) == nrm(row["item_label"]), (r, row["item_label"])
            return pnum(r[amt]) / 1e6
        if not has_serial and r[hdr.index("Borrower")] and not r[hdr.index("Borrower")].lower().startswith("total"):
            seq += 1
            if seq == serial:
                return pnum(r[amt]) / 1e6
    raise AssertionError((path.name, route, serial))


def fla_col(g, k: int, needs: list[str]) -> int:
    heads = g[2:k] if g[1][0].startswith("(") else g[1:k]
    cols = [c for c in range(1, len(g[k])) if all(any(h[c] == n for h in heads) for n in needs)]
    assert len(cols) == 1, (needs, cols)
    return cols[0]


# FLA round -> page. The vintage is the release date printed on each page ('Date : Oct 11, 2024',
# 'Date : Oct 29, 2025'); checked in test_fla_round_vintage_is_the_page_date.
FLA_FILE = {"2024-10-11": "fla_census_2023_24.html", "2025-10-29": "fla_census_2024_25.html"}
FLA_PAGE_DATE = {"2024-10-11": "Oct 11, 2024", "2025-10-29": "Oct 29, 2025"}


def loc_fla(row: dict) -> float:
    path = by_name(FLA_FILE[row["vintage"]])
    t = row["table_id"]
    g = grid_titled(path, t + ":")
    k = colnum_row(g)
    lab = row["item_label"]
    year = row["period"][:4]
    ucell = {"INR_crore": "₹ crore", "USD_million": "US$ million"}.get(row["unit"])
    if t == "Table 3A":
        grp, rname = lab.removeprefix("Inward direct investment, ").split(": ", 1)
        needs = [grp, year]
    elif t in ("Table 3B", "Table 4"):
        grp, rname = lab.split(": ", 1)
        needs = [grp, year, ucell]
    elif t in ("Table 5", "Table 6"):
        rname, grp = lab.rsplit(": ", 1)
        needs = [grp, year]
    else:  # Table 2B, Table 8
        rname, hname = lab.split(": ", 1)
        needs = [hname]
        # single-date tables: the caption prints '(amount in ... , end-March YYYY)'
        m = re.search(r"end-March (\d{4})\)", g[1][0])
        assert m and year == m.group(1), (g[1][0], row["period"])
    c = fla_col(g, k, needs)
    (r,) = [r for r in g[k + 1 :] if r[0] == rname]
    return pnum(r[c])


def loc_remit(row: dict) -> float:
    path = by_name("remittances_survey_r6.html")
    prefix = "Table 1:" if row["table_id"] == "Table 1" else "Table 2:"
    g = grid_titled(path, prefix)
    c = g[1].index(row["period"])
    rname = row["item_label"].split(": share in", 1)[0]
    (r,) = [r for r in g[2:] if r[0] == rname]
    return pnum(r[c])


ITES_FILE = {"2025-11-04": "ites_survey_2024_25.html", "2026-09-18": "ites_survey_2025_26.html"}
ITES_UNIT = {"INR_crore": ("₹ crore", 1.0), "USD_million": ("US$ billion", 1000.0), "percent": ("Share (%)", 1.0)}


def loc_ites(row: dict) -> float:
    g = grid_titled(by_name(ITES_FILE[row["vintage"]]), row["table_id"] + ":")
    uh, scale = ITES_UNIT[row["unit"]]
    cols = [c for c in range(1, len(g[1])) if g[1][c] == row["period"] and g[2][c] == uh]
    assert len(cols) == 1
    hits = [r for r in g[4:] if nrm(r[0]) == nrm(row["item_label"])]
    assert len(hits) == 1, row["item_label"]
    return pnum(hits[0][cols[0]]) * scale


LRS_FILE = {"2023-24": "lrs_bulletin_2024-06.html", "2024-25": "lrs_bulletin_2025-06.html", "2025-26": "lrs_bulletin_2026-06.html"}
LRS_BY_VINTAGE = {"2024-06-19": "lrs_bulletin_2024-06.html", "2025-06-25": "lrs_bulletin_2025-06.html",
                  "2026-06-22": "lrs_bulletin_2026-06.html"}  # fmt: skip


def lrs_usd(name: str, number: str, period: str, ptype: str) -> float:
    (g,) = [g for g in grids(by_name(name)) if g and g[0][0] == "(US $ Million)"]
    if ptype == "fy":
        assert g[1][1] == period
        c = 1
    else:
        y, m = period[:4], MONTH_ABBR[int(period[5:]) - 1]
        c = next(c for c in range(2, len(g[1])) if g[1][c] == y and g[2][c].rstrip(".") == m)
    (r,) = [r for r in g if r[0].split(" ")[0] == number]
    return pnum(r[c])


def t133_avg(fy: str) -> float:
    return loc_fx({"series_id": "t133.usd_fy_average", "period": fy, "period_type": "fy"})


def loc_lrs(row: dict) -> float:
    number = row["item_code"].removeprefix("lrs_").replace("_", ".")
    if row["status"] == "derived":
        usd = lrs_usd(LRS_FILE[row["period"]], number, row["period"], "fy")
        return usd * t133_avg(row["period"]) / 10.0
    return lrs_usd(LRS_BY_VINTAGE[row["vintage"]], number, row["period"], row["period_type"])


LOCATOR = {
    "fx_inr_usd": loc_fx, "bop_bpm6_annual": loc_bpm6, "bop_bpm6_quarterly": loc_bpm6,
    "bop_overall_annual": loc_bop_old, "invisibles_annual": loc_invisibles, "nri_deposits": loc_nri,
    "foreign_investment": loc_t143, "fx_reserves": loc_t144, "external_debt": loc_debt,
    "external_debt_by_sector": loc_debt_release, "iip_quarterly": loc_iip, "ecb_monthly_2324": loc_ecb,
    "fla_census": loc_fla, "remittance_survey": loc_remit, "ites_survey": loc_ites, "lrs_outward": loc_lrs,
}  # fmt: skip


def close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6)


# ------------------------------------------------------------------------------------------------
# sample
# ------------------------------------------------------------------------------------------------


def stratum(r: dict) -> tuple:
    return (r["unit"], r["period_type"], r["vintage"], r["table_id"], r["status"])


@cache
def sample() -> dict[str, list[dict]]:
    rng = random.Random(SEED)
    out = {}
    for ds in DATASETS:
        rows = clean(ds)
        n = min(len(rows), max(MIN_PER_DATASET, math.ceil(FRACTION * len(rows))))
        strata = defaultdict(list)
        for r in rows:
            strata[stratum(r)].append(r)
        picked = []
        for key in sorted(strata, key=str):  # at least one per stratum, then proportional
            members = strata[key]
            k = max(1, round(n * len(members) / len(rows)))
            picked += rng.sample(members, min(k, len(members)))
        if len(picked) < n:  # proportional rounding can fall short of the minimum: top up (seeded)
            ids = {id(r) for r in picked}
            picked += rng.sample([r for r in rows if id(r) not in ids], n - len(picked))
        out[ds] = picked
    return out


@cache
def critical() -> list[dict]:
    cov = yaml.safe_load(COVERAGE.read_text(encoding="utf-8"))["entries"]
    out = []
    for e in cov:
        ds = e["dataset"].removeprefix("external_sector_")
        for r in clean(ds):
            if r["series_id"] in e["series_ids"] and r["period"] == e.get("period", "2023-24"):
                out.append(r)
    return out


@cache
def comparisons() -> list[tuple[str, dict, float | None, str]]:
    res = []
    seen = set()
    for ds, rows in sample().items():
        for r in rows:
            seen.add((ds, r["series_id"], r["vintage"], r["period"]))
            try:
                v = LOCATOR[ds](r)
                res.append((ds, r, v, ""))
            except Exception as ex:  # noqa: BLE001 - recorded as a mismatch
                res.append((ds, r, None, repr(ex)))
    for r in critical():
        ds = r["dataset"].removeprefix("external_sector_")
        if (ds, r["series_id"], r["vintage"], r["period"]) in seen:
            continue
        seen.add((ds, r["series_id"], r["vintage"], r["period"]))
        try:
            res.append((ds, r, LOCATOR[ds](r), "critical"))
        except Exception as ex:  # noqa: BLE001
            res.append((ds, r, None, repr(ex)))
    return res


# ------------------------------------------------------------------------------------------------
# tests
# ------------------------------------------------------------------------------------------------


def test_raw_files_match_pins():
    # 44 first pins + the FLA 2023-24 round page (prid 58874) pinned after verification (V4)
    assert len(pins()) == 45
    assert "rbi_fla_census/fla_census_2023_24.html" in pins()
    for key, p in pins().items():
        data = (ROOT / p["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == p["sha256"], key
        assert b"<table" in data.lower() and len(data) > 50_000, f"{key}: not a data page (challenge?)"
        assert p["url"].startswith("https://www.rbi.org.in/"), key  # never rbidocs (D1-4)


def test_sample_size_meets_the_ten_percent_rule():
    total = sum(len(clean(ds)) for ds in DATASETS)
    checked = len(comparisons())
    # 19,576 at the first pass; -10 LRS (V1), +3 ECB grand totals (V2), +396 FLA 2023-24 round (V4).
    # Each delta is re-derived from raw in test_lrs_derived_rows_recomputed_from_raw,
    # test_ecb_route_totals_complete and test_fla_no_dropped_cells.
    assert total == 19965
    assert checked >= 0.10 * total and checked >= 50
    for ds in DATASETS:
        assert len(sample()[ds]) >= min(MIN_PER_DATASET, len(clean(ds))), ds
    print(f"\nspot-check: {checked} values of {total} ({checked / total:.1%})")


def test_sampled_values_match_raw():
    bad = []
    per = defaultdict(lambda: [0, 0])
    for ds, r, v, note in comparisons():
        per[ds][0] += 1
        if v is None or not close(v, r["value"]):
            per[ds][1] += 1
            bad.append((ds, r["series_id"], r["period"], r["vintage"], r["value"], v, note))
    for ds in DATASETS:
        print(f"{ds}: checked {per[ds][0]}, mismatched {per[ds][1]}")
    assert not bad, "\n".join(map(str, bad[:40]))


def test_gap_map_critical_series_were_checked():
    crit = critical()
    assert len(crit) >= 50
    got = {(r["series_id"], r["period"]) for _, r, v, _ in comparisons() if v is not None}
    missing = [(r["series_id"], r["period"]) for r in crit if (r["series_id"], r["period"]) not in got]
    assert not missing, missing


HAND = [  # typed from the raw page text (dump of the pinned HTML), not from any parser output;
    # last field: the vintage the value belongs to (None = every vintage of the cell must carry it)
    ("bop_bpm6_annual", "bpm6.inr.bpm6_1.net.current", "2023-24", -215248, None),  # T127 row 1, 2023-24 Net
    ("bop_bpm6_annual", "bpm6.inr.bpm6_3_1_a_1_2.credit.current", "2023-24", 163704, None),  # T127 3.1.A.1.2
    ("bop_bpm6_annual", "bpm6.inr.bpm6_1_b_2_4.credit.current", "2023-24", 131059, None),  # T127 1.B.2.4 credit
    ("bop_bpm6_quarterly", "bpm6q.usd.bpm6_1_c_1_1.credit.current", "Q3 2023-24", 30589, None),  # 2024-25 ed. T196
    ("bop_bpm6_quarterly", "bpm6q.usd.bpm6_1_a_a_1.debit.current", "Q1 2023-24", 151939, None),
    ("bop_overall_annual", "bop_old.usd.monetary_movements.reserves.debit.current", "2023-24", 63702, None),  # T124
    ("invisibles_annual", "invis.usd.nonfactor_services.travel.receipts.current", "2023-24", 33704, None),  # T130
    ("fx_inr_usd", "t133.usd_fy_average", "2024-25", 84.5756, None),
    ("fx_inr_usd", "t205.usd_month_average", "2022-01", 74.4416, None),
    ("nri_deposits", "nri.flow.inr.total.current", "2024-25", 136702, None),  # T142
    ("fx_reserves", "t144.inr.total.current", "2025-03-31", 5712141, None),  # T144 row 2024-25
    ("foreign_investment", "t143.usd.fdi_gross_inflows.current", "2024-25", 80615, None),
    ("external_debt", "debt.146.pct.debt_to_gdp", "2023-03-31", 19.6, None),
    ("external_debt", "debt.inr.commercial_borrowing.current", "2024-03-31", 2089300, None),
    ("external_debt_by_sector", "edr.t1.other_sectors.nfc.usd.current", "2024-03-31", 252700.0, None),
    ("iip_quarterly", "iipq.inr.liabilities.3.5.current", "2023-06-30", 180575, None),  # 2024-25 ed. 'of which' SDR
    # FLA 3B total inward DI, US$ mn, end-March 2024: printed 7,26,558 in the 2023-24 round page
    # (Table 3B, column 2024 / US$ million) and revised to 7,42,228 in the 2024-25 round page.
    ("fla_census", "fla.t3b.liabilities.total.usd", "2024-03-31", 726558, "2024-10-11"),
    ("fla_census", "fla.t3b.liabilities.total.usd", "2024-03-31", 742228, "2025-10-29"),
    ("fla_census", "fla.t2b.fc.fdi_equity", "2025-03-31", 93082, None),
    ("remittance_survey", "remit.destination_state.in-kl", "2023-24", 19.7, None),
    ("ites_survey", "ites.t5.united_states_of_america.usd", "2023-24", 103200.0, None),
    ("lrs_outward", "lrs.usd.annual.lrs_1_4.current", "2023-24", 3580.27, None),
    ("ecb_monthly_2324", "ecb.2024-03.ecb_fccb.approval.126", "2024-03", 450.0, None),
]


@pytest.mark.parametrize(("ds", "sid", "period", "want", "vintage"), HAND)
def test_hand_anchors(ds, sid, period, want, vintage):
    rows = [r for r in clean(ds) if r["series_id"] == sid and r["period"] == period
            and (vintage is None or r["vintage"] == vintage)]  # fmt: skip
    assert rows, (sid, period)
    for r in rows:  # every vintage of the cell must carry the printed value
        assert close(r["value"], want), (sid, period, r["vintage"], r["value"], want)


def numeric_cells(path: Path, skip_label=None) -> int:
    n = 0
    for g in grids(path):
        try:
            k = colnum_row(g)
        except AssertionError:
            continue
        for r in g[k + 1 :]:
            if not r or r[0].lower().startswith(("(continued)", "notes", "note", "source")):
                continue
            if skip_label and skip_label(r[0]):
                continue
            for x in r[1:]:
                try:
                    if pnum(x) is not None:
                        n += 1
                except ValueError:
                    pass
    return n


COMPLETE = [  # (dataset, file, filter on clean rows, row-label filter excluded from the raw count)
    ("bop_bpm6_annual", "hbs2026_t126.html", {"unit": "USD_million"}, None),
    ("bop_bpm6_annual", "hbs2026_t127.html", {"unit": "INR_crore"}, None),
    ("bop_bpm6_quarterly", "hbs2025_t196.html", {"unit": "USD_million", "vintage": "2025-08-29"}, None),
    ("bop_bpm6_quarterly", "hbs2026_t198.html", {"unit": "INR_crore", "vintage": "2026-07-31"}, None),
    ("bop_overall_annual", "hbs2026_t125.html", {"unit": "INR_crore"}, None),
    ("invisibles_annual", "hbs2026_t130.html", {"unit": "USD_million"}, None),
    ("nri_deposits", "hbs2026_t142.html", {"unit": "INR_crore", "stock_flow": "flow"}, None),
    ("foreign_investment", "hbs2026_t143.html", {}, None),
    ("fx_reserves", "hbs2026_t144.html", {}, None),
    ("external_debt", "hbs2026_t146.html", {"table_id": "Table 146"}, None),
    ("iip_quarterly", "hbs2025_t199.html", {"unit": "INR_crore", "vintage": "2025-08-29"}, None),
]


@pytest.mark.parametrize(("ds", "name", "flt", "skip"), COMPLETE)
def test_no_dropped_cells(ds, name, flt, skip):
    rows = [r for r in clean(ds) if all(r[k] == v for k, v in flt.items())]
    assert len(rows) == numeric_cells(by_name(name), skip), (ds, name, len(rows))


def test_scale_rupee_vs_dollar_consistent_with_fx():
    """Rs crore / US$ mn must be ~ rate/10: catches lakh/crore/million slips across whole datasets."""
    fy_avg = {r["period"]: r["value"] for r in clean("fx_inr_usd") if r["series_id"] == "t133.usd_fy_average"}
    end = {r["period"]: r["value"] for r in clean("fx_inr_usd") if r["series_id"] == "t133.usd_end_march"}
    for ds, rate_of, lo, hi in (
        ("bop_bpm6_annual", lambda p: fy_avg[p], 0.97, 1.03),
        ("invisibles_annual", lambda p: fy_avg[p], 0.95, 1.05),
        # reserves from end-March 1994 only: 1991-92/1992-93 were dual-rate years (T133 notes)
        ("fx_reserves", lambda p: end.get(p) if p >= "1994" else None, 0.9, 1.1),
    ):
        pairs = defaultdict(dict)
        for r in clean(ds):
            key = (r["series_id"].replace(".inr.", ".x.").replace(".usd.", ".x."), r["period"], r["vintage"])
            pairs[key][r["unit"]] = r["value"]
        n = 0
        for (sid, period, _), v in pairs.items():
            gross = not sid.endswith((".net.current",)) or ds == "fx_reserves"
            if gross and {"INR_crore", "USD_million"} <= set(v) and abs(v["USD_million"]) >= 5000 and rate_of(period):
                ratio = v["INR_crore"] * 10 / v["USD_million"] / rate_of(period)
                assert lo < ratio < hi, (ds, sid, period, ratio)
                n += 1
        assert n > 20, ds


def test_lrs_derived_rows_recomputed_from_raw():
    rows = [r for r in clean("lrs_outward") if r["status"] == "derived"]
    # One derived Rs row per FY cell whose item is also printed for April of that FY (V1 rule),
    # counted from the three raw Bulletin tables (11 + 11 + 11 = 33 on the pinned pages).
    assert len(rows) == lrs_full_year_cells() == 33
    assert {r["item_code"] for r in rows if r["period"] == "2025-26"}.isdisjoint(
        {f"lrs_1_6_{i}" for i in range(1, 6)})
    for r in rows:
        assert r["unit"] == "INR_crore" and r["period_type"] == "fy"
        assert close(r["value"], loc_lrs(r)), r["series_id"]
    assert all(r["status"] == "official" for r in clean("lrs_outward") if r["unit"] == "USD_million")


def test_reference_year_fx_rate_anchor():
    """The INR_per_USD cells other units DEPEND on for 2023-24 (T133 row 2023-24, US Dollar columns)."""
    fx = {(r["series_id"], r["period"]): r["value"] for r in clean("fx_inr_usd")}
    assert fx[("t133.usd_fy_average", "2023-24")] == 82.7897
    assert fx[("t133.usd_end_march", "2024-03-31")] == 83.3739


def test_lrs_fy_rows_cover_the_full_year():
    """A cell stored with period_type 'fy' must not be a single month's value. In the June 2026 Bulletin
    table the new travel sub-items 1.6.1-1.6.5 are printed only for Mar-2026 and Apr-2026; their
    '2025-26' column equals the March value, so they are one month, not the financial year."""
    partial = []
    for r in clean("lrs_outward"):
        if r["period_type"] != "fy" or r["status"] != "official" or r["period"] != "2025-26":
            continue
        number = r["item_code"].removeprefix("lrs_").replace("_", ".")
        mar = lrs_usd("lrs_bulletin_2026-06.html", number, "2026-03", "month")
        feb_cell = lrs_usd_or_none("lrs_bulletin_2026-06.html", number, "2026-02")
        if feb_cell is None and mar is not None and close(mar, r["value"]):
            partial.append(r["series_id"])
    assert not partial, partial


def lrs_full_year_cells() -> int:
    n = 0
    for fy, name in LRS_FILE.items():
        (g,) = [g for g in grids(by_name(name)) if g and g[0][0] == "(US $ Million)"]
        assert g[1][1] == fy
        apr = next(c for c in range(2, len(g[1])) if g[1][c] == fy[:4] and g[2][c].rstrip(".") == "Apr")
        for r in g[3:]:
            if re.match(r"^\d+(\.\d+)*\s", r[0]) and pnum(r[1]) is not None and pnum(r[apr]) is not None:
                n += 1
    return n


def lrs_usd_or_none(name: str, number: str, period: str) -> float | None:
    try:
        return lrs_usd(name, number, period, "month")
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------------------------------------
# close-out pass (2026-09-29): builder follow-up (PR stage, D1-9 State codes, FX guide) and the
# rows added by the V1-V4 fixes
# ------------------------------------------------------------------------------------------------


def test_fla_round_vintage_is_the_page_date():
    for v, name in FLA_FILE.items():
        assert f"Date : {FLA_PAGE_DATE[v]}" in page_text(by_name(name)), name
    assert {r["vintage"] for r in clean("fla_census")} == set(FLA_FILE)


FLA_TABLES = ("Table 2B", "Table 3A", "Table 3B", "Table 4", "Table 5", "Table 6", "Table 8")


@pytest.mark.parametrize("vintage", sorted(FLA_FILE))
def test_fla_no_dropped_cells(vintage):
    """Clean rows per FLA table and round == numeric cells printed. '%' growth/share columns are not
    ingested (derivable), except Table 2B's '% share of FDI in Total Equity', which is."""
    path = by_name(FLA_FILE[vintage])
    for t in FLA_TABLES:
        g = grid_titled(path, t + ":")
        k = colnum_row(g)
        pct = set() if t == "Table 2B" else {c for c in range(len(g[k])) if any("%" in h[c] for h in g[2:k])}
        n = 0
        for r in g[k + 1 :]:
            if r[0].lower().startswith(("note", "source")):
                continue
            for c in range(1, len(r)):
                if c in pct:
                    continue
                try:
                    n += pnum(r[c]) is not None
                except ValueError:
                    pass
        got = sum(1 for r in clean("fla_census") if r["vintage"] == vintage and r["table_id"] == t)
        assert got == n, (vintage, t, got, n)


ECB_ROUTE_LABEL = {"totalautomaticroute": "automatic", "totalapprovalroute": "approval",
                   "totalautomaticrouteapprovalroute": "all", "grandtotal": "all", "total": "all"}  # fmt: skip


def ecb_months() -> list[str]:
    out = []
    for k in pins():
        m = re.search(r"/ecb_(\d{4}-\d{2})\.html$", k)
        if m:
            out.append(m.group(1))
    return sorted(out)


def test_ecb_route_totals_complete():
    """Every route total printed WITH a number on the 12 monthly pages has exactly one clean row, and
    no clean total exists where the page prints '-' or a blank (V2: 'Grand total' in Feb/Mar 2024)."""
    months = ecb_months()
    assert len(months) == 12
    want = {}
    for month in months:
        for g in grids(ecb_page(month)):
            if not (g and g[0] and g[0][0].startswith("Data on")):
                continue
            kind = "ecb_fccb" if "ECB/FCCB" in g[0][0] else "rdb"
            hdr = next(r for r in g if "Borrower" in r)
            amt = next(i for i, h in enumerate(hdr) if h.startswith("Equivalent Amount in USD"))
            for r in g:
                keys = {re.sub(r"[^a-z]", "", c.lower()) for c in r}
                routes = {ECB_ROUTE_LABEL[x] for x in keys if x in ECB_ROUTE_LABEL}
                if len(routes) != 1:
                    continue
                v = pnum(r[amt])
                if v is None:
                    continue
                key = (month, kind, routes.pop())
                assert key not in want, key
                want[key] = v / 1e6
    got = {}
    for r in clean("ecb_monthly_2324"):
        if r["item_code"] == "ecb_registrations_total":
            _, _, kind, route = r["series_id"].split(".")[:4]
            got[(r["period"], kind, route)] = r["value"]
    assert set(got) == set(want), set(got) ^ set(want)
    assert all(close(got[k], want[k]) for k in want)
    assert {k for k in got if k[2] == "all" and k[1] == "ecb_fccb"} == {(m, "ecb_fccb", "all") for m in months}


# --- estimate stages from the raw period flags --------------------------------------------------


def stage_legend(path: Path) -> dict[str, str]:
    """Flag -> stage as printed in the page's own footnote ('PR: Partially Revised, P: Provisional')."""
    out: dict[str, str] = {}
    for m in re.finditer(r"\b(PR|R|P): (Partially Revised|Revised|Provisional)\b", page_text(path)):
        assert out.setdefault(m.group(1), m.group(2)) == m.group(2)
    assert out, path.name
    return out


def expected_stage(ds: str, row: dict) -> str:
    """Stage re-derived from the raw page: the flag printed next to the row's period, read through
    that page's footnote legend; 'n.a.' when no flag is printed."""
    if ds == "iip_quarterly":
        unit = "INR_crore" if row["unit"] == "percent" else row["unit"]
        path = by_name(HBS[("iip_quarterly", unit, row["vintage"])])
        g = grids(path)[0]
        hdr = next(r for r in g if r[0] == "Period")
        (h,) = [h for h in hdr[1:] if iip_date(h) == row["period"]]
        flag = re.fullmatch(r"\d{4}-\d{2}:\s*Q[1-4]\s*(PR|P|R)?", h).group(1)
    else:
        path = by_name("external_debt_end_march_2026_release.html")
        g = grid_titled(path, row["table_id"] + ":")
        k = colnum_row(g)
        year = row["period"][:4]
        if row["table_id"] == "Table 5":
            (cell,) = [r[0] for r in g[k + 1 :] if r[0].split(" ")[0] == year]
        else:
            (cell,) = [h for h in g[k - 1][1:] if h.split(" ")[0] == year]
        flag = re.fullmatch(r"\d{4}(?: (PR|P|R))?", cell).group(1)
    return "n.a." if flag is None else stage_legend(path)[flag]


def test_estimate_stages_follow_raw_flags():
    """Every IIP and debt-release row (872 + 289), not a sample."""
    n: dict[tuple, int] = defaultdict(int)
    for ds in ("iip_quarterly", "external_debt_by_sector"):
        for r in clean(ds):
            want = expected_stage(ds, r)
            got = r["estimate_stage"]
            assert got == want, (ds, r["series_id"], r["period"], r["vintage"], got, want)
            n[(ds, want)] += 1
    assert n[("iip_quarterly", "Partially Revised")] == 763
    assert n[("external_debt_by_sector", "Partially Revised")] == 40
    assert stage_legend(by_name("external_debt_end_march_2026_release.html")) == {
        "R": "Revised", "PR": "Partially Revised", "P": "Provisional"}  # fmt: skip
    for name in ("hbs2025_t198.html", "hbs2025_t199.html", "hbs2026_t199.html", "hbs2026_t200.html"):
        assert stage_legend(by_name(name)) == {"PR": "Partially Revised", "P": "Provisional"}, name


# --- remittance survey State codes (D1-9) --------------------------------------------------------

# Typed by the verifier from ISO 3166-2:IN as amended 2023-11-23 (IN-CG, IN-OD, IN-TS, IN-UK) plus
# the merged UT IN-DH (2020) and Ladakh IN-LA (2019); keyed by the name exactly as printed in Table 2.
REM_PRINTED_ISO = {
    "Maharashtra": "IN-MH", "Kerala": "IN-KL", "Tamil Nadu": "IN-TN", "Telangana": "IN-TS", "Karnataka": "IN-KA",
    "Andhra Pradesh": "IN-AP", "Delhi NCT": "IN-DL", "Punjab": "IN-PB", "Gujarat": "IN-GJ", "Uttar Pradesh": "IN-UP",
    "Haryana": "IN-HR", "West Bengal": "IN-WB", "Rajasthan": "IN-RJ", "Bihar": "IN-BR", "Uttarakhand": "IN-UK",
    "Goa": "IN-GA", "Madhya Pradesh": "IN-MP", "Odisha": "IN-OD", "Jharkhand": "IN-JH", "Jammu and Kashmir": "IN-JK",
    "Chandigarh": "IN-CH", "Puducherry": "IN-PY", "Himachal Pradesh": "IN-HP", "Assam": "IN-AS",
    "Chhattisgarh": "IN-CG", "Dadra & Nagar Haveli and Daman & Diu": "IN-DH", "Tripura": "IN-TR",
    "Manipur": "IN-MN", "Meghalaya": "IN-ML", "Mizoram": "IN-MZ", "Ladakh": "IN-LA", "Sikkim": "IN-SK",
    "Nagaland": "IN-NL", "Lakshwadeep": "IN-LD", "Arunachal Pradesh": "IN-AR", "Andaman & Nicobar": "IN-AN",
}  # fmt: skip
SUPERSEDED = {"IN-TG", "IN-CT", "IN-OR", "IN-UT", "IN-DD", "IN-DN"}


def rem_expected_code(printed: str, fy: str) -> str:
    code = REM_PRINTED_ISO[printed]
    start, end = f"{fy[:4]}-04-01", f"{int(fy[:4]) + 1}-03-31"
    if code == "IN-JK" and end <= "2019-10-30":  # the State incl. Ladakh, to 30 Oct 2019
        return "IN-XJK"
    assert not (code == "IN-JK" and start <= "2019-10-30"), "FY straddles the J&K reorganisation"
    assert not (code == "IN-LA" and start < "2019-10-31"), "Ladakh printed before it existed"
    assert not (code == "IN-DH" and start < "2020-01-26"), "DNH&DD printed before the merger"
    return code


def test_remittance_state_codes_independent():
    """Every numeric cell of raw Table 2 -> exactly one clean row with the verifier's code."""
    g = grid_titled(by_name("remittances_survey_r6.html"), "Table 2:")
    assert g[1] == ("Destination State", "2016-17", "2020-21", "2023-24")
    want = {}
    for r in g[2:]:
        if r[0].startswith("Note"):
            continue
        for c in (1, 2, 3):
            v = pnum(r[c])
            if v is not None:
                code = rem_expected_code(r[0], g[1][c])
                want[(f"remit.destination_state.{code.lower()}", g[1][c])] = (code, v)
    t2 = [r for r in clean("remittance_survey") if r["table_id"] == "Table 2"]
    got = {(r["series_id"], r["period"]): (r["geography"], r["value"]) for r in t2}
    assert len(got) == len(t2)
    assert got == want
    assert got[("remit.destination_state.in-xjk", "2016-17")] == ("IN-XJK", 0.2)
    assert ("remit.destination_state.in-jk", "2016-17") not in got
    sums: dict[str, float] = defaultdict(float)
    for (_, fy), (_, v) in want.items():
        sums[fy] += v
    assert abs(sums["2023-24"] - 100) < 0.2  # all 36 States/UTs listed in 2023-24 (-20)
    for ds in DATASETS:
        assert not {r["geography"] for r in clean(ds)} & SUPERSEDED, ds


# --- seeded sample of the rows the follow-up changed ---------------------------------------------


def test_closeout_changed_rows_sample():
    """The follow-up changed 804 rows (763 IIP + 40 debt-release stages, 1 State code). Draw >=10%
    (min 30; seed SEED+1) plus the recoded row and re-check value, stage and geography from raw."""
    changed = [(ds, r) for ds in ("iip_quarterly", "external_debt_by_sector") for r in clean(ds)
               if r["estimate_stage"] == "Partially Revised"]  # fmt: skip
    recoded = [("remittance_survey", r) for r in clean("remittance_survey")
               if (r["geography"] or "").startswith("IN-X")]  # fmt: skip
    total = len(changed) + len(recoded)
    assert len(recoded) == 1 and total == 804
    n = max(30, math.ceil(0.10 * total))
    picked = random.Random(SEED + 1).sample(changed, n - 1) + recoded
    assert len(picked) >= 0.10 * total and len(picked) >= 30
    per: dict[tuple, int] = defaultdict(int)
    for ds, r in picked:
        v = LOCATOR[ds](r)
        assert v is not None and close(v, r["value"]), (ds, r["series_id"], r["period"], r["vintage"], r["value"], v)
        if ds == "remittance_survey":
            assert r["geography"] == rem_expected_code(r["item_label"].split(": share in", 1)[0], r["period"])
            assert r["series_id"] == f"remit.destination_state.{r['geography'].lower()}"
        else:
            assert r["estimate_stage"] == expected_stage(ds, r)
        per[(ds, r["unit"], r["vintage"])] += 1
    assert len({k[0] for k in per}) == 3
    print(f"\nclose-out sample: {len(picked)} of {total} changed rows: {dict(per)}")


# --- INR/USD exchange-rate guide for Phase 2 (issues file) ----------------------------------------


def test_fx_phase2_guide_claims():
    import datetime as dt

    fx = clean("fx_inr_usd")
    assert len(fx) == 188
    assert {(r["unit"], r["status"], r["estimate_stage"], r["dim_other"], r["vintage"]) for r in fx} == {
        ("INR_per_USD", "official", "n.a.", "currency=usd", "2026-07-31")}  # fmt: skip
    by = defaultdict(list)
    for r in fx:
        by[(r["series_id"], r["period_type"])].append(r["period"])
    assert set(by) == {("t133.usd_fy_average", "fy"), ("t133.usd_end_march", "date"),
                       ("t205.usd_month_average", "month"), ("t205.usd_end_month", "date")}  # fmt: skip
    # extents re-derived from the raw tables
    g133 = grids(by_name("hbs2026_t133.html"))[0]
    fys = [r[0] for r in g133 if re.fullmatch(r"\d{4}-\d{2}", r[0])]
    assert sorted(by[("t133.usd_fy_average", "fy")]) == fys
    assert (fys[0], fys[-1], len(fys)) == ("1986-87", "2025-26", 40)
    assert sorted(by[("t133.usd_end_march", "date")]) == [f"{int(f[:4]) + 1}-03-31" for f in fys]
    g205 = grids(by_name("hbs2026_t205.html"))[0]
    months, year = [], None
    for r in g205:
        if re.fullmatch(r"\d{4}", r[0]):
            year = int(r[0])
        elif r[0] in FX_MONTHS and year:
            months.append(f"{year}-{FX_MONTHS[r[0]]:02d}")
    assert sorted(by[("t205.usd_month_average", "month")]) == months
    assert (months[0], months[-1], len(months)) == ("2022-01", "2026-06", 54)
    ends = sorted(by[("t205.usd_end_month", "date")])
    assert [e[:7] for e in ends] == months
    for e in ends:  # dated to the last calendar day of the month
        y, m, d = map(int, e.split("-"))
        first_next = dt.date(y + (m == 12), m % 12 + 1, 1)
        assert (first_next - dt.timedelta(days=1)).day == d, e
    # end-March appears in both T133 and T205 with equal values (the guide's one-series rule)
    em = {r["period"]: r["value"] for r in fx if r["series_id"] == "t133.usd_end_march"}
    eo = {r["period"]: r["value"] for r in fx if r["series_id"] == "t205.usd_end_month"}
    both = sorted(set(em) & set(eo))
    assert both == ["2022-03-31", "2023-03-31", "2024-03-31", "2025-03-31", "2026-03-31"]
    assert all(em[d] == eo[d] for d in both)
    # the guide's worked example: US$ 1,000 mn in FY 2023-24 = Rs 8,278.97 crore
    avg = {r["period"]: r["value"] for r in fx if r["series_id"] == "t133.usd_fy_average"}
    assert close(1000 * avg["2023-24"] / 10, 8278.97)
    assert len({r["prov_id"] for r in fx}) == 2  # one provenance record per source table
