"""Independent verification of the labour_enterprise_surveys unit (Phase 1, verifier first pass, 2026-09-29).

This file does NOT import the unit's code. It re-reads the 7 pinned MoSPI PDFs directly with its own
parsers and compares them with data/clean/labour_enterprise_surveys/:

- Upright pages are read with pdfplumber ``extract_text``. Pages whose characters are drawn rotated
  (the landscape ASUSE report tables; the unit reads them with pypdf) are read with the verifier's own
  character-level reader (``_rot_lines``), which groups glyphs by x position and orders them bottom-to-top.
- Tables are located by their printed title (never by the unit's page numbers), rows are matched by
  printed label / code, and the verifier keeps its own label -> code maps.
- Method: a full census. Every clean row of every dataset must match a value re-parsed from the PDF
  (tolerance 1e-6 relative, after the verifier's own unit conversion), and every published cell the
  verifier parses must have a clean row, except the documented zero-cell skips.
- HAND_ANCHORS: 40 values typed by hand from the printed page text (read page by page during the
  verification) as a check on both parsers.
- A seeded random sample (SEED) of matched rows is printed for the notes.

Close-out pass (2026-09-29):
- Survey rows are re-keyed from fy + survey_year to `sy` windows. The verifier derives each window from the
  printed text (jul_jun / oct_sep / SAS statement titles, tested in
  test_survey_windows_are_printed_in_the_documents). Values are unchanged.
- One known label defect was tracked by a strict xfail: VER-C1, the SAS Statement 1.3 window. Final pass
  (2026-09-29): the unit now labels it with the printed window, so the xfail mark and the census's period
  remap were removed and test_sas_statement_1_3_period_is_the_printed_window is a normal check.
- The three eSankhyiki API datasets (5,244 rows) get a full census from the verifier's own reader of the 58
  pinned JSON pages, with its own maps: quarter via calendar month, the ASUSE activity names checked against
  Annexure I, and the AIDIS classes.
- Cross-source checks: the AIDIS API against the press note, and the PLFS API against AR Statements 10-12.
- Identity checks on the raw JSON, plus a provenance-per-page check.
"""

from __future__ import annotations

import collections
import hashlib
import json
import random
import re
from functools import cache
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pdfplumber
import polars as pl
import pytest
import yaml

pytestmark = pytest.mark.quality

ROOT = Path(__file__).resolve().parents[2]
UNIT = "labour_enterprise_surveys"
CLEAN = ROOT / "data" / "clean" / UNIT
PINS = ROOT / "data" / "raw_pins" / f"{UNIT}.yaml"
SEED = 20260929
NUM = r"-?\d[\d,]*(?:\.\d+)?"

# ------------------------------------------------------------------------------------------------
# raw access and text readers (verifier's own)
# ------------------------------------------------------------------------------------------------


@cache
def raw_path(name: str) -> Path:
    pins = yaml.safe_load(PINS.read_text(encoding="utf-8"))["pins"]
    hits = [v["path"] for k, v in pins.items() if k.endswith("/" + name)]
    assert len(hits) == 1, name
    p = ROOT / hits[0]
    assert p.exists(), p
    return p


@cache
def pdf(name: str):
    return pdfplumber.open(raw_path(name))


def _rot_lines(page) -> list[str]:
    chars = [c for c in page.chars if c["text"].strip()]
    groups: list[list] = []
    for c in sorted(chars, key=lambda c: c["x0"]):
        if groups and abs(c["x0"] - groups[-1][0]) <= 2.0:
            groups[-1][1].append(c)
        else:
            groups.append([c["x0"], [c]])
    out = []
    for _, cs in groups:
        cs.sort(key=lambda c: -c["bottom"])
        s, prev = "", None
        for c in cs:
            if prev is not None and (prev["top"] - c["bottom"]) > 1.5:
                s += " "
            s += c["text"]
            prev = c
        out.append(s)
    return out


@cache
def lines(name: str, pno: int) -> tuple[str, ...]:
    """Text lines of 1-based page ``pno``, orientation-aware."""
    page = pdf(name).pages[pno - 1]
    mats = collections.Counter(tuple(round(x) for x in ch["matrix"][:4]) for ch in page.chars)
    if mats and mats.most_common(1)[0][0] == (0, 1, -1, 0):
        return tuple(_rot_lines(page))
    return tuple((page.extract_text() or "").split("\n"))


def text(name: str, pno: int) -> str:
    return "\n".join(lines(name, pno))


def nums(s: str) -> list[float]:
    return [float(t.replace(",", "")) for t in re.findall(NUM, s)]


def all_numeric(s: str) -> bool:
    return bool(s.strip()) and all(re.fullmatch(NUM, t) for t in s.split())


def find_pages(name: str, lo: int, hi: int, pattern: str) -> list[int]:
    return [p for p in range(lo, hi + 1) if re.search(pattern, text(name, p))]


# ------------------------------------------------------------------------------------------------
# keys: (table_id, item_code, industry, household_group, dims, period)
# ------------------------------------------------------------------------------------------------

# Close-out pass: 'survey_year' is no longer ignored. A stray survey_year key would now break the census.
IGNORED_DIMS = {"market"}  # checked separately (flags), not identity


def mk(table, item, industry, hh, period, **dims):
    return (table, item, industry, hh, tuple(sorted(dims.items())), period)


# Survey windows (close-out pass). The verifier's own label -> window rules. Each rule is justified by
# the printed text, checked in test_survey_windows_are_printed_in_the_documents:
# - PLFS AR p.22: "2023-24 refers to the period July 2023 - June 2024 and likewise for 2022-23, ... 2017-18".
# - ASUSE factsheet p.3: "ASUSE 2022-23 conducted during October 2022 to September 2023 ... ASUSE 2023-24 ...
#   October 2023 to September 2024".
# - SAS Report 587: each statement's title names its window ("agricultural year July 2018 - June 2019").
#   Statement 5.7 prints none, so it takes the report's "agricultural year 2018-19" (p.14).
# - AIDIS press note p.2: capital expenditure "during the Agricultural Year 2018-19 (July-June)".
def jul_jun(label: str) -> str:
    y0 = int(label[:4])
    assert int(label[5:7]) == (y0 + 1) % 100, label
    return f"{y0}-07/{y0 + 1}-06"


def oct_sep(label: str) -> str:
    y0 = int(label[:4])
    assert int(label[5:7]) == (y0 + 1) % 100, label
    return f"{y0}-10/{y0 + 1}-09"


# VER-C1 (close-out pass) had the unit labelling SAS Statement 1.3 '2018-07/2018-12' (visit 1) while the
# printed title (pp.76-77) reads "for the agricultural year July 2018 - June 2019". The census then remapped
# that one label (KNOWN_PERIOD_DEFECTS) so it could compare values. Final pass (2026-09-29): the unit is fixed,
# so the remap is gone and the census keys every row by the period exactly as the unit labels it. A relapse to
# the 6-month label now fails the census as well as test_sas_statement_1_3_period_is_the_printed_window.


def row_key(r: dict):
    dims = {}
    if r["dim_other"]:
        for kv in r["dim_other"].split(";"):
            k, v = kv.split("=", 1)
            if k not in IGNORED_DIMS:
                dims[k] = v
    dims_t = tuple(sorted(dims.items()))
    return (r["table_id"], r["item_code"], r["industry"], r["household_group"], dims_t, r["period"])


def load(ds: str) -> pl.DataFrame:
    return pl.read_parquet(CLEAN / f"{UNIT}_{ds}.parquet")


SECT = {"rural": "rural", "urban": "urban", "rural+urban": "total", "rural +urban": "total", "rural + urban": "total"}
SEX3 = ["male", "female", "person"]
RU9 = [(s, x) for s in ("rural", "urban", "total") for x in SEX3]

# ------------------------------------------------------------------------------------------------
# PLFS Annual Report 2023-24
# ------------------------------------------------------------------------------------------------
PLFS = "plfs_ar_2023_24.pdf"
PLFS_2324 = jul_jun("2023-24")  # '2023-07/2024-06'


def parse_plfs_lfs() -> dict:
    out = {}
    ind = {"labour force participation rate": "lfpr", "worker population ratio": "wpr", "wpr": "wpr", "unemployment rate": "ur"}
    title = r"(?i)Table\s*\d:\s*(Labour force participation rate|Worker population ratio|WPR|Unemployment rate)"
    pages = find_pages(PLFS, 15, 35, title)
    assert len(pages) == 6, pages
    seen = set()
    for p in pages:
        t = text(PLFS, p)
        m = re.search(title, t)
        item = ind[m.group(1).lower()]
        head = t[: t.find("(1) (2)")]
        status = "cws" if "current weekly status" in head else "ps_ss"
        assert ("usual status (ps+ss)" in head) != (status == "cws")
        seen.add((item, status))
        year, label = None, None
        for ln in lines(PLFS, p):
            ln = ln.strip()
            if m2 := re.fullmatch(r"PLFS\s*\((\d{4}-\d{2})\)", ln):
                year = m2.group(1)
                continue
            lab = next((a for a in ("15 years and above", "all ages") if ln.startswith(a)), None)
            if lab:
                label, ln = lab, ln[len(lab):].strip()
            if label and year and all_numeric(ln) and len(ln.split()) == 9:
                age = "15plus" if label.startswith("15") else "all"
                for (hh, sx), v in zip(RU9, nums(ln), strict=True):
                    out[mk(f"Highlights table ({status})", item, None, hh, jul_jun(year), activity_status=status, age_group=age, sex=sx)] = v
                label = None
    assert len(seen) == 6
    return out


def parse_plfs_st6() -> dict:
    out = {}
    (p,) = find_pages(PLFS, 35, 50, r"Statement 6: Percentage distribution of workers in usual status")
    cols = ["own_account_employer", "helper", "self_employed", "regular_wage", "casual_labour", "all"]
    year = sec = None
    for ln in lines(PLFS, p):
        ln = ln.strip()
        if m := re.fullmatch(r"PLFS\s*\((\d{4}-\d{2})\)", ln):
            year = m.group(1)
        elif ln in SECT:
            sec = SECT[ln]
        elif (m := re.fullmatch(r"(male|female|person)\s+(.*)", ln)) and all_numeric(m.group(2)):
            vals = nums(m.group(2))
            assert len(vals) == 6
            for c, v in zip(cols, vals, strict=True):
                out[mk("Statement 6", f"worker_share_{c}", None, sec, jul_jun(year), activity_status="ps_ss", employment_status=c, sex=m.group(1))] = v
    return out


def parse_plfs_st7() -> dict:
    out = {}
    (p,) = find_pages(PLFS, 35, 50, r"Statement 7: Percentage distribution of workers in usual status")
    lab = [("agriculture", "A"), ("mining", "B"), ("manufacturing", "C"), ("electricity", "D-E"), ("construction", "F"),
           ("trade", "G_I"), ("transport", "H_J"), ("communications", "H_J"), ("other services", "K-U"), ("all", "all")]
    year = None
    for ln in lines(PLFS, p):
        ln = ln.strip()
        if m := re.fullmatch(r"PLFS\s*\((\d{4}-\d{2})\)", ln):
            year = m.group(1)
            continue
        m = re.fullmatch(rf"(.*?)\s*((?:{NUM}\s+){{8}}{NUM})", ln)
        if not (m and year):
            continue
        label = m.group(1).lower()
        code = next(c for k, c in lab if label.startswith(k))
        for (hh, sx), v in zip(RU9, nums(m.group(2)), strict=True):
            out[mk("Statement 7", "worker_share_broad_industry", f"nic2008_{code}", hh, jul_jun(year), activity_status="ps_ss", sex=sx)] = v
    return out


def parse_plfs_earn_statements() -> dict:
    out = {}
    items = {10: "regular_wage_earnings_month", 11: "casual_wage_earnings_day", 12: "self_employment_gross_earnings_30d"}
    periods = ["Q2 2023-24", "Q3 2023-24", "Q4 2023-24", "Q1 2024-25"]
    for st, item in items.items():
        (p,) = find_pages(PLFS, 40, 55, rf"Statement {st}: Average")
        t = text(PLFS, p)
        seg = t[t.find(f"Statement {st}:"):]
        nxt = re.search(r"Statement \d+:", seg[5:])
        seg = seg[: nxt.start() + 5] if nxt else seg
        seg = seg[seg.find("(1) (2)"):]
        # the four quarter rows appear in calendar order
        pos = [seg.find(k) for k in ("July", "October", "January", "April")]
        assert all(x >= 0 for x in pos) and pos == sorted(pos), (st, pos)
        rows = []
        for ln in seg.split("\n")[1:]:
            toks = re.findall(NUM, ln)
            if len(toks) >= 9:
                rows.append([float(x.replace(",", "")) for x in toks[-9:]])
        assert len(rows) >= 4, st
        for per, vals in zip(periods, rows[:4], strict=True):
            for (hh, sx), v in zip(RU9, vals, strict=True):
                out[mk(f"Statement {st}", item, None, hh, per, activity_status="cws", sex=sx)] = v
    return out


def parse_plfs_t26() -> tuple[dict, int]:
    out = {}
    pages = find_pages(PLFS, 200, 240, r"Table \(26\): Percentage distribution of usually working persons")
    nrows = 0
    for p in pages:
        for ln in lines(PLFS, p):
            m = re.fullmatch(rf"(\d{{2,4}}|[A-U]|total|sample worker)\s+((?:{NUM}\s+){{8}}{NUM})", ln.strip())
            if not m:
                continue
            code, vals = m.group(1), nums(m.group(2))
            nrows += 1
            if code == "sample worker":
                item, ind = "sample_workers", None
            elif code == "total":
                item, ind = "worker_share_nic_total", "nic2008_all"
            else:
                lvl = {4: "class", 3: "group", 2: "division", 1: "section"}[len(code)]
                item, ind = f"worker_share_nic_{lvl}", f"nic2008_{code}"
            for (hh, sx), v in zip(RU9, vals, strict=True):
                k = mk("Table (26)", item, ind, hh, PLFS_2324, activity_status="ps_ss", sex=sx)
                assert k not in out, k
                out[k] = v
    return out, len(pages)


def parse_plfs_t51() -> tuple[dict, set]:
    out, zeros = {}, set()
    pages = find_pages(PLFS, 395, 415, r"Table \(51\): Average wage earnings")
    assert len(pages) == 3, pages
    secs = list("ABCDEFGHIJKLMNOPQRSTU") + ["all"]
    for p in pages:
        L = [x.strip() for x in lines(PLFS, p)]
        hh = sx = None
        for i, ln in enumerate(L):
            if m := re.fullmatch(r"(rural|urban|rural\+urban) (male|female|person)", ln):
                hh, sx = SECT[m.group(1)], m.group(2)
            elif ln.startswith("Average wage earnings (Rs.)") and hh and all_numeric(ln[len("Average wage earnings (Rs.)"):]):
                vals = nums(ln[len("Average wage earnings (Rs.)"):])
                assert len(vals) == 22
                for s, v in zip(secs, vals, strict=True):
                    k = mk("Table (51)", "casual_wage_earnings_day", f"nic2008_{s}", hh, PLFS_2324, activity_status="cws", sex=sx)
                    (zeros.add(k) if v == 0 else out.__setitem__(k, v))
            elif ln.startswith("sample no. of days worked as casual") and hh:
                nxt = L[i + 1]
                assert nxt.startswith("labour")
                vals = nums(nxt[len("labour"):])
                assert len(vals) == 22
                for s, v in zip(secs, vals, strict=True):
                    out[mk("Table (51)", "sample_casual_days", f"nic2008_{s}", hh, PLFS_2324, activity_status="cws", sex=sx)] = v
    return out, zeros


# --- second pass (VER-1 / VER-4 fixes): Tables (20) and (35) ---------------------------------------
T20_TITLE = r"Table \(20\):\s*Percentage distribution of workers in usual status \(ps\+ss\) by broad status"
T35_TITLE = r"Table \(35\): Percentage distribution of usually working \(ps\+ss\) persons engaged in non-agriculture"
# column order (2)..(7) of Table (20), confirmed by header-word x positions (see _t20_header_order)
T20_STATUS = ["own_account_employer", "helper", "self_employed", "regular_wage", "casual_labour", "all"]
T20_GROUPS = {"01-03", "05-09", "10-33", "35-39", "41-43", "05-43", "45-47", "49-53", "55-56", "58-99", "45-99"}
# column order (2)..(10) of Table (35), confirmed by header-word x positions (see _t35_header_order)
T35_ENT = ["proprietary_partnership", "govt_public_sector", "autonomous_bodies", "pvt_public_ltd_company",
           "cooperative_societies", "trust_nonprofit", "employer_households", "others", "all"]


def _words_x(pno: int) -> dict[str, list[float]]:
    xs: dict[str, list[float]] = collections.defaultdict(list)
    for w in pdf(PLFS).pages[pno - 1].extract_words():
        xs[w["text"]].append(w["x0"])
    return xs


def _t20_header_order(pno: int) -> None:
    """(5) is 'regular wage/salary' and (6) 'casual labour' (the V1a-critical pair), by word x position."""
    x = _words_x(pno)
    (reg,), (cas,), (c5,), (c6,) = x["regular"], x["casual"], x["(5)"], x["(6)"]
    (own,), (hlp,) = x["own"], x["helper"]
    assert abs(reg - c5) < 25 and abs(cas - c6) < 25, (pno, reg, c5, cas, c6)
    assert own < hlp < reg < cas, pno


def _t35_header_order(pno: int) -> None:
    x = _words_x(pno)
    seq = [x["proprietary"][0], x["govt./"][0], x["autonomous"][0], x["Public/"][0], x["cooperative"][0],
           x["trust/"][0], x["employer’s"][0], x["others"][0], x["total"][0], x["sample"][0]]
    assert seq == sorted(seq), (pno, seq)
    cols = [x[f"({i})"][0] for i in range(2, 12)]
    # each header word starts within 45pt of its column number (the numbers are right-aligned)
    assert all(abs(a - b) < 45 for a, b in zip(seq, cols, strict=True)), (pno, seq, cols)


def _footer_2023_24(pno: int) -> None:
    assert "Annual Report, PLFS, 2023-24" in text(PLFS, pno), f"p.{pno}: footer is not the 2023-24 report"


def parse_plfs_t20() -> tuple[dict, dict]:
    """Table (20) census. Returns (keyed values, raw rows per block for the identity checks)."""
    out, blocks = {}, {}
    pages = find_pages(PLFS, 140, 160, T20_TITLE)
    assert len(pages) == 9, pages
    for p in pages:
        _footer_2023_24(p)
        _t20_header_order(p)
        L = [x.strip() for x in lines(PLFS, p)]
        (h,) = [m for m in (re.fullmatch(r"all-India (rural|urban|rural\+urban) (male|female|persons?)", x) for x in L) if m]
        hh, sx = SECT[h.group(1)], ("person" if h.group(2).startswith("person") else h.group(2))
        assert (hh, sx) not in blocks
        rows = {}
        for ln in L:
            if m := re.fullmatch(rf"(\d\d-\d\d)\s*\(.*?\)+\s*((?:{NUM}\s+){{5}}{NUM})", ln):
                code, vals = m.group(1), nums(m.group(2))
            elif m := re.fullmatch(rf"(total|sample workers)\s+((?:{NUM}\s+){{5}}{NUM})", ln):
                code, vals = m.group(1), nums(m.group(2))
            else:
                continue
            assert code not in rows, (p, code)
            rows[code] = vals
        assert set(rows) == T20_GROUPS | {"total", "sample workers"}, (p, sorted(rows))
        blocks[(hh, sx)] = rows
        for code, vals in rows.items():
            for st, v in zip(T20_STATUS, vals, strict=True):
                if code == "sample workers":
                    k = mk("Table (20)", "sample_workers", "nic2008_all", hh, PLFS_2324, activity_status="ps_ss", employment_status=st, sex=sx)
                else:
                    ind = "all" if code == "total" else code
                    k = mk("Table (20)", f"worker_share_{st}", f"nic2008_{ind}", hh, PLFS_2324, activity_status="ps_ss", employment_status=st, sex=sx)
                out[k] = v
    assert len(blocks) == 9
    return out, blocks


def parse_plfs_t35() -> tuple[dict, dict]:
    """Table (35) all-India rows. Returns (keyed values, {(hh, sex): (shares incl col 11, sample counts)})."""
    out, blocks = {}, {}
    pages = find_pages(PLFS, 268, 290, T35_TITLE)
    assert len(pages) == 9, pages
    for p in pages:
        _footer_2023_24(p)
        _t35_header_order(p)
        L = [x.strip() for x in lines(PLFS, p)]
        (h,) = [m for m in (re.fullmatch(r"(rural|urban|rural\+urban) (male|female|persons?)", x) for x in L) if m]
        hh, sx = SECT[h.group(1)], ("person" if h.group(2).startswith("person") else h.group(2))
        (a,) = [x for x in L if x.startswith("all India ")]
        (s,) = [x for x in L if x.startswith("sample workers ")]
        shares = nums(a[len("all India "):])
        assert len(shares) == 10 and all_numeric(a[len("all India "):]), (p, a)
        assert s.endswith(" x"), (p, s)
        counts = nums(s[len("sample workers "):-2])
        assert len(counts) == 9, (p, s)
        blocks[(hh, sx)] = (shares, counts)
        for e, v, n in zip(T35_ENT, shares[:9], counts, strict=True):
            d = dict(activity_status="ps_ss", enterprise_type=e, sex=sx)
            out[mk("Table (35)", "worker_share_enterprise_type", "nic2008_05-99", hh, PLFS_2324, **d)] = v
            out[mk("Table (35)", "sample_workers", "nic2008_05-99", hh, PLFS_2324, **d)] = n
    assert len(blocks) == 9
    return out, blocks


# ------------------------------------------------------------------------------------------------
# ASUSE 2023-24 factsheet and report
# ------------------------------------------------------------------------------------------------
FS = "asuse_2023_24_factsheet.pdf"
REP = "asuse_2023_24_full_report.pdf"
FS_RATIO_ITEMS = [  # printed order of the parameter column in factsheet Tables 3-6 (checked by keyword)
    ("pct_market_estt", "Market"), ("pct_prop_partnership_estt", "Proprietary"), ("pct_hwe", "Hired Worker"),
    ("emol_per_formal_hired_worker", "per Formal"), ("emol_per_informal_hired_worker", "per Informal"),
    ("emol_per_hired_worker", "per Hired"), ("gvo_per_estt", "(GVO)"), ("gva_per_estt", "GVA (Rs.) per"),
    ("gva_per_worker", "GVA per worker"),
]


def _fs_table(tno: int) -> list[tuple[str, list[float]]]:
    """Rows (label context, 6 values) of factsheet Table ``tno``."""
    for p in range(1, 17):
        t = text(FS, p)
        if f"Table {tno}:" in t:
            seg = t[t.find(f"Table {tno}:"):]
            nxt = re.search(r"\nTable \d:", seg)
            seg = seg[: nxt.start()] if nxt else seg
            seg = seg[seg.find("(1) (2)") + 1:]
            L = seg.split("\n")[1:]
            rows = []
            for i, ln in enumerate(L):
                if "%" in ln:
                    continue
                m = re.fullmatch(rf"(.*?)\s*((?:{NUM}\s+){{5}}{NUM})", ln.strip())
                if m:
                    ctx = " ".join(L[max(0, i - 1): i + 2])
                    rows.append((m.group(1) + " || " + ctx, nums(m.group(2))))
            return rows
    raise AssertionError(tno)


def parse_asuse_factsheet() -> dict:
    out = {}
    per = [oct_sep("2022-23")] * 3 + [oct_sep("2023-24")] * 3
    for tno, cols in ((1, ["rural", "urban", "total"] * 2), (2, ["asuse_M", "asuse_T", "asuse_S"] * 2)):
        rows = _fs_table(tno)
        assert len(rows) == 3, rows
        for (ctx, vals), (item, kw, mult) in zip(rows, [("establishments", "establishments", 100), ("workers", "Workers", 100), ("gva", "Gross Value Added", 1)], strict=True):
            assert kw in ctx, (tno, ctx)
            for c, pr, v in zip(cols, per, vals, strict=True):
                ind, hh = ("asuse_all", c) if tno == 1 else (c, "total")
                out[mk(f"Factsheet Table {tno}", item, ind, hh, pr)] = v * mult
    for tno, ind in ((3, "asuse_all"), (4, "asuse_M"), (5, "asuse_T"), (6, "asuse_S")):
        rows = _fs_table(tno)
        assert len(rows) == 9, (tno, rows)
        for (ctx, vals), (item, kw) in zip(rows, FS_RATIO_ITEMS, strict=True):
            assert kw in ctx, (tno, item, ctx)
            for hh, pr, v in zip(["rural", "urban", "total"] * 2, per, vals, strict=True):
                out[mk(f"Factsheet Table {tno}", item, ind, hh, pr)] = v
    return out


ASUSE_CODE = r"(M\+E\+T\+S|M\d{1,2}|T\d|S\d{1,2}|M|E|T|S)"
SEC = {"Rural": "rural", "Urban": "urban", "Combined": "total"}
EST = {"HWE": "hwe", "OAE": "oae", "All": "all"}


def _ind(code: str) -> str:
    return "asuse_all" if code == "M+E+T+S" else f"asuse_{code}"


@cache
def rep_pages(tno: int) -> tuple[int, ...]:
    windows = {4: (80, 100), 6: (125, 160), 29: (815, 850), 31: (905, 940), 33: (1000, 1015), 35: (1015, 1030), 37: (1025, 1040)}
    lo, hi = windows[tno]
    ps = tuple(p for p in range(lo, hi + 1) if any(re.match(rf"Table {tno}:\s", ln) for ln in lines(REP, p)))
    assert ps and ps == tuple(range(ps[0], ps[-1] + 1)), (tno, ps)
    return ps


def _rep_rows(tno: int, ncols: int):
    """Yield (sec, est, code, values) for report Table ``tno``."""
    sec = est = None
    for p in rep_pages(tno):
        for ln in lines(REP, p):
            ln = ln.strip()
            if m := re.fullmatch(r"Sec:\s*(Rural|Urban|Combined)(?:\s+Est\.:\s*(HWE|OAE|All))?", ln):
                sec, est = SEC[m.group(1)], (EST[m.group(2)] if m.group(2) else None)
                continue
            m = re.fullmatch(rf"{ASUSE_CODE}\s+(.*)", ln)
            if m and all_numeric(m.group(2)):
                vals = nums(m.group(2))
                assert len(vals) == ncols, (tno, p, ln)
                yield sec, est, m.group(1), vals


def parse_asuse_report() -> tuple[dict, set]:
    out, skipped = {}, set()
    per = oct_sep("2023-24")
    # Table 4: col (2) number of establishments (col 3 % mixed is not ingested)
    for sec, est, code, v in _rep_rows(4, 2):
        out[mk("Table 4", "establishments", _ind(code), sec, per, estt_type=est)] = v[0]
    # Table 6: per-1000 shares (cols 2-11) -> percent
    own = ["proprietary_male", "proprietary_female", "proprietary_all", "partnership_same_hh", "partnership_diff_hh",
           "shg", "society_trust", "cooperative", "others", "all"]
    for sec, est, code, v in _rep_rows(6, 12):
        for o, x in zip(own, v[:10], strict=True):
            out[mk("Table 6", "estt_share_by_ownership", _ind(code), sec, per, estt_type=est, ownership=o)] = x / 10
    # Table 29: full time / part time / all x male female all*
    for sec, est, code, v in _rep_rows(29, 11):
        for i, (emp, sx) in enumerate([(e, s) for e in ("full_time", "part_time", "all") for s in ("male", "female", "all")]):
            out[mk("Table 29", "workers", _ind(code), sec, per, employment=emp, estt_type=est, sex=sx)] = v[i]
    # Table 31: worker type x sex
    wt = ["working_owner", "formal_hired", "informal_hired", "unpaid_family", "other", "total"]
    for sec, est, code, v in _rep_rows(31, 18):
        for i, (w, sx) in enumerate([(w, s) for w in wt for s in ("male", "female", "all")]):
            out[mk("Table 31", f"workers_{w}", _ind(code), sec, per, estt_type=est, sex=sx, worker_type=w)] = v[i]
    # Table 33: emoluments per hired worker (2-4), hired workers (5-7); HWE only
    for sec, est, code, v in _rep_rows(33, 8):
        assert est is None
        for i, w in enumerate(["formal_hired", "informal_hired", "all_hired"]):
            out[mk("Table 33", "hired_workers", _ind(code), sec, per, estt_type="hwe", worker_type=w)] = v[3 + i]
            k = mk("Table 33", "emol_per_hired_worker", _ind(code), sec, per, estt_type="hwe", worker_type=w)
            if v[3 + i] == 0:  # no such workers: per-worker value printed as 0 is not a value
                assert v[i] == 0, (code, sec, w, v)
                skipped.add(k)
            else:
                out[k] = v[i]
    # Tables 35/37: Rural/Urban/Combined x OAE/HWE/all, market establishments; printed 0 = none
    for tno, item in ((35, "gva_per_worker"), (37, "gva_per_estt")):
        for _, _, code, v in _rep_rows(tno, 9):
            for i, (sec, est) in enumerate([(s, e) for s in ("rural", "urban", "total") for e in ("oae", "hwe", "all")]):
                k = mk(f"Table {tno}", item, _ind(code), sec, per, estt_type=est)
                (skipped.add(k) if v[i] == 0 else out.__setitem__(k, v[i]))
    return out, skipped


# ------------------------------------------------------------------------------------------------
# ASI 2023-24
# ------------------------------------------------------------------------------------------------
ASI_SR = "asi_2023_24_summary_results.pdf"
ASI_V1 = "asi_2023_24_vol_i.pdf"
LAKH_TO_CRORE = 0.01
S3A = {"Factories in Operation": "factories_in_operation", "Fixed Capital": "fixed_capital", "Invested Capital": "invested_capital",
       "Workers": "workers", "Total Persons Engaged": "persons_engaged", "Wages to Worker": "wages_to_workers",
       "Total Emoluments": "total_emoluments", "Input": "total_input", "Output": "total_output", "GVA": "gva",
       "Depreciation": "depreciation", "NVA": "nva", "Rent Paid for Fixed Assets": "rent_paid", "Interest Paid": "interest_paid",
       "Net Income": "net_income", "Net Profit": "net_profit"}


def parse_asi_3a() -> dict:
    out = {}
    (p,) = find_pages(ASI_SR, 25, 45, r"Statement 3A: Value of Principal Characteristics")
    t = text(ASI_SR, p)
    t = t[t.find("Statement 3A"): t.find("Statement 3B")]
    years = re.findall(r"\d{4}-\d{2}", t.split("\n")[2])
    assert years == ["2019-20", "2020-21", "2021-22", "2022-23", "2023-24"], years
    for ln in t.split("\n"):
        m = re.fullmatch(rf"(.+?) (Number|₹ Lakhs) ((?:{NUM}\s+){{4}}{NUM})", ln.strip())
        if not m:
            continue
        item = S3A[m.group(1)]
        mult = 1 if m.group(2) == "Number" else LAKH_TO_CRORE
        for y, v in zip(years, nums(m.group(3)), strict=True):
            out[mk("Statement 3A", item, "nic2008_all", None, y)] = v * mult
    assert len(out) == 80
    return out


def parse_asi_5a() -> dict:
    out = {}
    (p,) = find_pages(ASI_SR, 30, 50, r"Statement 5A: Estimate of Some Principal Characteristics by 2-digit")
    cols = [("factories_in_operation", 1), ("fixed_capital", LAKH_TO_CRORE), ("working_capital", LAKH_TO_CRORE),
            ("invested_capital", LAKH_TO_CRORE), ("gross_value_plant_machinery", LAKH_TO_CRORE), ("persons_engaged", 1),
            ("total_input", LAKH_TO_CRORE), ("total_output", LAKH_TO_CRORE), ("gva", LAKH_TO_CRORE), ("nva", LAKH_TO_CRORE),
            ("gva_share", 1)]
    for ln in lines(ASI_SR, p):
        m = re.fullmatch(rf"(\d{{2}}|OT|All Industries)\b(.*?)((?:\s+{NUM}){{11}})", ln.strip())
        if not m:
            continue
        code = {"OT": "other", "All Industries": "all"}.get(m.group(1), m.group(1))
        for (item, mult), v in zip(cols, nums(m.group(3)), strict=True):
            out[mk("Statement 5A", item, f"nic2008_{code}", None, "2023-24")] = v * mult
    return out


V1T3_ROWS = [  # (label regex, item, multiplier) -- verifier's own map of the printed row labels
    (r"A\. No\. of Persons Engaged \(no\.\)", "persons_engaged", 1),
    (r"1\. Workers", "workers", 1),
    (r"1\.1 Directly Employed", "workers_direct", 1),
    (r"Men", "workers_direct_men", 1),
    (r"Women", "workers_direct_women", 1),
    (r"1\.2 Employed Through Contractors", "workers_contract", 1),
    (r"2\. Employees Other Than Workers", "employees_other_than_workers", 1),
    (r"2\.1 Supervisory and Managerial", "supervisory_managerial", 1),
    (r"2\.2 Other Employees", "other_employees", 1),
    (r"3\. Unpaid family members/proprietor etc", "unpaid_family_proprietor", 1),
    (r"B\. Total Mandays Employed \(in '000\)", "mandays", 1000),
    (r"Employers' Contribution \( ?lakhs\)", "wages_salaries_incl_employer_contrib", LAKH_TO_CRORE),
    (r"1\. Wages and Salary Including Bonus", "wages_salary_incl_bonus", LAKH_TO_CRORE),
    (r"1\.1 Wages and Salary", "wages_salary", LAKH_TO_CRORE),
    (r"1\.1\.1 Workers", "wages_salary_workers", LAKH_TO_CRORE),
    (r"1\.1\.2 Supervisory & Managerial", "wages_salary_supervisory", LAKH_TO_CRORE),
    (r"1\.1\.3 Other Employees", "wages_salary_other_employees", LAKH_TO_CRORE),
    (r"1\.2 Bonus to All Staff", "bonus", LAKH_TO_CRORE),
    (r"2\. Employers' Contribution", "employers_contribution", LAKH_TO_CRORE),
]


def parse_asi_v1t3() -> tuple[dict, int]:
    out = {}
    pages = find_pages(ASI_V1, 300, 350, r"Table 3: Estimate of \(i\) employment")
    for p in pages:
        L = [x.strip() for x in lines(ASI_V1, p)]
        hdr = [x for x in L if re.fullmatch(r"(?:(?:All|Other|\d{4})\s*)+", x)]
        assert len(hdr) == 1, (p, hdr)
        codes = hdr[0].split()
        found = set()
        for ln in L:
            m = re.fullmatch(rf"(.*?)((?:\s+{NUM}){{{len(codes)}}})", ln)
            if not m or not m.group(1):
                continue
            hit = [(it, mult) for rx, it, mult in V1T3_ROWS if re.fullmatch(rx, m.group(1).strip())]
            if not hit:
                continue
            (item, mult), = hit
            assert item not in found, (p, item)
            found.add(item)
            for c, v in zip(codes, nums(m.group(2)), strict=True):
                ind = f"nic2008_{c.lower()}" if c in ("All", "Other") else f"nic2008_{c}"
                out[mk("Table 3 (Vol I)", item, ind, None, "2023-24")] = v * mult
        assert len(found) == len(V1T3_ROWS), (p, set(i for _, i, _ in V1T3_ROWS) - found)
    return out, len(pages)


# ------------------------------------------------------------------------------------------------
# SAS 2019 (Report 587) and AIDIS 2019 press note
# ------------------------------------------------------------------------------------------------
SAS = "sas_2019_report_587.pdf"
LAND = {"< 0.01": "agri_land_lt0.01", "0.01 - 0.40": "agri_land_0.01-0.40", "0.40 - 1.00": "agri_land_0.41-1.00",
        "1.01 - 2.00": "agri_land_1.01-2.00", "2.01 - 4.00": "agri_land_2.01-4.00", "4.01 - 10.00": "agri_land_4.01-10.00",
        "10.00 +": "agri_land_gt10.00", "all sizes": "agri_all"}
LAND_RX = r"(< 0\.01|0\.01 - 0\.40|0\.40 - 1\.00|1\.01 - 2\.00|2\.01 - 4\.00|4\.01 - 10\.00|10\.00 \+|all sizes)"


def _sas_page(title: str, must: str = "") -> int:
    (p,) = [q for q in range(70, 130) if re.search(title, text(SAS, q)) and must in text(SAS, q)]
    return p


SAS_AY = jul_jun("2018-19")  # p.14: "Information was collected primarily for the agricultural year 2018-19"


def sas_title_window(t: str, st: str) -> str | None:
    """Window printed in the title of Statement ``st`` (title = text from 'Statement st:' to the '(1)' header)."""
    title = t[t.find(f"Statement {st}:"):]
    title = re.sub(r"\s+", " ", title[: title.find("(1)")])
    m = re.search(r"July (\d{4}) ?[-–] ?June (\d{4})", title)
    if not m:
        return None
    assert int(m.group(2)) == int(m.group(1)) + 1, title
    return f"{m.group(1)}-07/{m.group(2)}-06"


def parse_sas() -> dict:
    out = {}
    t = text(SAS, _sas_page(r"Statement 1\.1: Estimates and percentage of agricultural households"))
    per = sas_title_window(t, "1.1")
    assert per == SAS_AY, per
    m = re.search(rf"Estimated number ({NUM}) ({NUM}) ({NUM})\s*\n\(in Millions\)", t)
    for hh, v in zip(["agri_all", "rural_nonagri_all", "rural_all"], m.groups(), strict=True):
        out[mk("Statement 1.1", "households", None, hh, per)] = float(v) * 1_000_000
    t = text(SAS, _sas_page(r"Statement 1\.3: Percentage distribution of agricultural and non-", "Social Group: all"))
    per13 = sas_title_window(t, "1.3")  # printed: "for the agricultural year July 2018 - June 2019" (VER-C1)
    assert per13 == SAS_AY, per13
    blk = t[t.find("Social Group: all"):]
    for lab, a, _b, _c in re.findall(rf"{LAND_RX} ({NUM}) ({NUM}) ({NUM})", blk)[:8]:
        out[mk("Statement 1.3", "agri_hh_share_by_land_class", None, LAND[lab], per13)] = float(a)
    items = ["income_wages", "income_leasing_out_land", "income_crop_production_net", "income_farming_animals_net",
             "income_nonfarm_business_net", "income_total"]
    for st, basis in (("5.1A", "paid_out"), ("5.1B", "paid_out_imputed")):
        t = text(SAS, _sas_page(rf"Statement {re.escape(st)}: Average monthly income"))
        per51 = sas_title_window(t, st)  # printed: "during July 2018 - June 2019"
        assert per51 == SAS_AY, (st, per51)
        t = t[t.find(f"Statement {st}:"):]
        rows = re.findall(rf"{LAND_RX} ((?:{NUM} ){{5}}{NUM})", t)
        assert len(rows) == 8, (st, rows)
        for lab, vals in rows:
            for it, v in zip(items, nums(vals), strict=True):
                out[mk(f"Statement {st}", it, None, LAND[lab], per51, net_receipt_basis=basis)] = v
    t = text(SAS, _sas_page(r"Statement 5\.7: Percentage of indebted agricultural households"))
    assert sas_title_window(t, "5.7") is None  # no window printed: the survey's agricultural year (see VER-C2)
    per = SAS_AY
    t = t[t.find("Statement 5.7:"):]
    rows = re.findall(rf"{LAND_RX} ({NUM}) ({NUM}) ({NUM})", t)
    assert len(rows) == 8
    for lab, a, b, c in rows:
        out[mk("Statement 5.7", "outstanding_loan_per_hh", None, LAND[lab], per)] = float(a.replace(",", ""))
        out[mk("Statement 5.7", "pct_indebted", None, LAND[lab], per)] = float(b)
        out[mk("Statement 5.7", "indebted_hh_share", None, LAND[lab], per)] = float(c)
    return out


AIDIS = "aidis_2019_press_note.pdf"
D = "2018-06-30"


def parse_aidis(tokens: dict | None = None) -> dict:
    """``tokens`` (optional) receives the printed number string of every hh-type row (precision check)."""
    t = " ".join(re.sub(r"\n\d \| Page\s*$", "", text(AIDIS, p)) for p in range(1, 7))
    t = re.sub(r"\s+", " ", t)
    out = {}

    def put(item, hh, typ, v, period=D):
        k = mk("Press note", item, None, hh, period, hh_type=typ)
        out[k] = float(str(v).replace(",", ""))
        if tokens is not None:
            tokens[k] = str(v)

    def trio(rx, item, hh, types, period=D):
        m = re.search(rx, t)
        assert m, rx
        for typ, v in zip(types, m.groups(), strict=True):
            put(item, hh, typ, v, period)

    R3, U3 = ("all", "cultivator", "non_cultivator"), ("all", "self_employed", "other")
    N = r"([\d,]+(?:\.\d+)?)"
    trio(rf"About {N}% of the households in Rural India \({N}% cultivator households and {N}% non-cultivator", "pct_hh_owning_any_asset", "rural", R3)
    trio(rf"About {N}% of the households in Urban India \({N}% self-employed households and {N}% other", "pct_hh_owning_any_asset", "urban", U3)
    m = re.search(rf"In Rural India, {N}% households owned physical assets & {N}% households owned financial", t)
    put("pct_hh_owning_physical_asset", "rural", "all", m.group(1)); put("pct_hh_owning_financial_asset", "rural", "all", m.group(2))
    m = re.search(rf"In Urban India, {N}% households owned physical assets & {N}% households owned financial", t)
    put("pct_hh_owning_physical_asset", "urban", "all", m.group(1)); put("pct_hh_owning_financial_asset", "urban", "all", m.group(2))
    trio(rf"Rs\. {N} in Rural India \(Rs\. {N} for cultivator households, Rs\. {N} for non-cultivator", "ava_per_hh", "rural", R3)
    trio(rf"Rs\. {N} in Urban India \(Rs\. {N} for self-employed households, Rs\. {N} for other", "ava_per_hh", "urban", U3)
    m = re.search(rf"physical asset per household was Rs\. {N} and average value for financial asset was Rs\. {N} in Rural", t)
    put("ava_physical_per_hh", "rural", "all", m.group(1)); put("ava_financial_per_hh", "rural", "all", m.group(2))
    m = re.search(rf"physical asset per household was Rs\. {N} and Average value of financial asset per household was Rs\. {N} in Urban", t)
    put("ava_physical_per_hh", "urban", "all", m.group(1)); put("ava_financial_per_hh", "urban", "all", m.group(2))
    m = re.search(rf"Rural India, jointly holding {N}% share in the total value of asset, with land having {N}% share and buildings {N}% share followed by deposits \({N}%\) and other assets \({N}%\)", t)
    for it, v in zip(["asset_share_land_building", "asset_share_land", "asset_share_building", "asset_share_deposits", "asset_share_other"], m.groups(), strict=True):
        put(it, "rural", "all", v)
    m = re.search(rf"Share of land in total value of assets is around {N}% in Urban India followed by building \({N} ?%\), deposits \({N}%\) and other assets \({N}%\)", t)
    for it, v in zip(["asset_share_land", "asset_share_building", "asset_share_deposits", "asset_share_other"], m.groups(), strict=True):
        put(it, "urban", "all", v)
    m = re.search(rf"Incidence of Indebtedness was about {N}% in Rural India \({N}% cultivator households, {N}% non-cultivator households\) compared to {N}% in Urban India \({N}% self-employed households, {N}% other", t)
    for (hh, typ), v in zip([("rural", x) for x in R3] + [("urban", x) for x in U3], m.groups(), strict=True):
        put("incidence_of_indebtedness", hh, typ, v)
    for rx, item in ((rf"In Rural India, ?{N}% households were indebted to institutional credit agencies only \({N}% cultivator households, {N}% non-cultivator households\) against {N}% households in Urban India \({N}% self-employed households, {N}% other", "pct_hh_indebted_institutional_only"),
                     (rf"About {N}% of the households were indebted to non-institutional credit agencies only in Rural India \({N}% cultivator households, {N}% non-cultivator households\) compared to {N}% households in Urban India \({N}% self-employed households, {N}% other", "pct_hh_indebted_noninstitutional_only"),
                     (rf"About {N}% of the households were indebted to both institutional credit agencies & non-institutional credit agencies in Rural India \({N}% cultivator households, {N}% non-cultivator households\) against {N}% households in Urban India \({N}% self-employed households, {N}% other", "pct_hh_indebted_both")):
        m = re.search(rx, t)
        assert m, item
        for (hh, typ), v in zip([("rural", x) for x in R3] + [("urban", x) for x in U3], m.groups(), strict=True):
            put(item, hh, typ, v)
    trio(rf"Average amount of debt was Rs\. {N} among rural households \(Rs\. {N} for cultivator households, Rs\. {N} for non-cultivator", "aod_per_hh", "rural", R3)
    trio(rf"Average amount of debt was Rs\. {N} among urban households \(Rs\. {N} for self-employed households, Rs\. {N} for other", "aod_per_hh", "urban", U3)
    m = re.search(rf"In Rural India, the share of outstanding cash debt from institutional credit agencies was {N}% against {N}% from non-institutional credit agencies\. In Urban India, the share of outstanding cash debt from institutional credit agencies was {N}% compared to {N}%", t)
    for (it, hh), v in zip([("debt_share_institutional", "rural"), ("debt_share_noninstitutional", "rural"), ("debt_share_institutional", "urban"), ("debt_share_noninstitutional", "urban")], m.groups(), strict=True):
        put(it, hh, "all", v)
    trio(rf"Average amount of debt was Rs\. {N} among indebted households in Rural India \(Rs\. {N} for cultivator households, Rs\. {N} for non-cultivator", "aod_per_indebted_hh", "rural", R3)
    trio(rf"Average amount of debt was Rs\. {N} among indebted households in Urban India \(Rs\. {N} for self-employed households, Rs\. {N} for other", "aod_per_indebted_hh", "urban", U3)
    trio(rf"About {N}% of the rural households reported incurring expenditure towards formation of fixed capital \({N}% cultivator households, {N}% non-cultivator", "pct_hh_reporting_fce", "rural", R3, jul_jun("2018-19"))
    trio(rf"About {N}% of the urban households reported incurring expenditure towards formation of fixed capital \({N}% self-employed households, {N}% other", "pct_hh_reporting_fce", "urban", U3, jul_jun("2018-19"))
    trio(rf"Rs\. {N} in Rural India \(Rs\. {N} for cultivator households, Rs\. {N} for non-cultivator households\) The average fixed", "fce_per_hh", "rural", R3, jul_jun("2018-19"))
    trio(rf"expenditure incurred per household was Rs\. {N} in Urban India \(Rs\. {N} for self-employed households, Rs\. {N} for other", "fce_per_hh", "urban", U3, jul_jun("2018-19"))
    for hh, rx in (("rural", rf"About {N} ?% of the population of age 18 years and above had deposit account in Banks in Rural India \({N}% male and {N}% female\)"),
                   ("urban", rf"About {N} ?% of the population of age 18 years and above had deposit account in Banks in Urban India \({N}% male and {N}% female\)")):
        m = re.search(rx, t)
        for sx, v in zip(["all", "male", "female"], m.groups(), strict=True):
            k = mk("Press note", "pct_adults_with_bank_deposit_account", None, hh, "2019", sex=sx)
            out[k] = float(v)
            if tokens is not None:
                tokens[k] = v
    return out


# ------------------------------------------------------------------------------------------------
# close-out pass: eSankhyiki API JSON pages (api.mospi.gov.in; D1-6). Verifier's own reader and maps.
# ------------------------------------------------------------------------------------------------
API_SRC = "mospi_esankhyiki_api"
API_STEMS = {  # pin-name stem -> query parameters every page URL must carry (all-India queries)
    "nss77_aidis_i5_allindia": ("/api/nss-77/getNss77AidisRecords", {"indicator_code": "5", "survey_code": "1", "state_code": "37"}),
    "nss77_aidis_i9_allindia": ("/api/nss-77/getNss77AidisRecords", {"indicator_code": "9", "survey_code": "1", "state_code": "37"}),
    **{f"plfs_i{i}_ay{y.replace('-', '_')}_allindia": ("/api/plfs/getData", {"indicator_code": str(i), "year": y, "state_code": "99",
                                                                             "year_type_code": "1", "frequency_code": "1"})
       for i in (6, 7, 8) for y in ("2022-23", "2023-24")},
    "asuse_i36_allindia": ("/api/asuse/getAsuseRecords", {"indicator_code": "36", "frequency_code": "1"}),
}


@cache
def api_pages(stem: str) -> tuple[tuple[str, dict], ...]:
    """((pin name, JSON document), ...) for every pinned page of one query, in page order. Checks the sha256
    against the pin, the page URL, the paging metadata, and that the pages hold exactly totalRecords records."""
    pins = yaml.safe_load(PINS.read_text(encoding="utf-8"))["pins"]
    rx = re.compile(rf"{API_SRC}/{stem}_p(\d+)\.json")
    keys = sorted((k for k in pins if rx.fullmatch(k)), key=lambda k: int(rx.fullmatch(k).group(1)))
    path_, params = API_STEMS[stem]
    out = []
    for i, k in enumerate(keys, 1):
        pin = pins[k]
        assert int(rx.fullmatch(k).group(1)) == i, (stem, keys)
        u = urlsplit(pin["url"])
        q = dict(parse_qsl(u.query))
        assert u.netloc == "api.mospi.gov.in" and u.path == path_, pin["url"]
        assert {a: q.get(a) for a in params} == params and q["page"] == str(i) and q["limit"] == "100", pin["url"]
        b = (ROOT / pin["path"]).read_bytes()
        assert hashlib.sha256(b).hexdigest() == pin["sha256"], k
        d = json.loads(b.decode("utf-8"))
        assert d["statusCode"] is True and d["meta_data"]["page"] == i, (k, d["meta_data"])
        out.append((k.split("/", 1)[1], d))
    m = out[0][1]["meta_data"]
    assert m["totalPages"] == len(out), (stem, m, len(out))
    assert all(d["meta_data"]["totalRecords"] == m["totalRecords"] for _, d in out), stem
    assert sum(len(d["data"]) for _, d in out) == m["totalRecords"], stem
    assert all(len(d["data"]) == 100 for _, d in out[:-1]), stem
    return tuple(out)


def api_records(stem: str) -> list[tuple[str, dict]]:
    return [(name, r) for name, d in api_pages(stem) for r in d["data"]]


def _api_num(s: str) -> float:
    assert re.fullmatch(r"\d+(?:\.\d+)?", s), s  # no negatives, blanks or formatted numbers appear in these pages
    return float(s)


# --- AIDIS 2019 (NSS-77) indicators 5 and 9 ----------------------------------------------------
AIDIS_API_TYPE = {("Rural", "Cultivator"): "cultivator", ("Rural", "Non-cultivator"): "non_cultivator", ("Rural", "All"): "all",
                  ("Urban", "Self-employed"): "self_employed", ("Urban", "Others"): "other", ("Urban", "All"): "all"}
AIDIS_I5 = {  # sub_indicator -> (item code, multiplier to the clean unit)
    "Per 1000 number of households": ("hh_distribution", 0.1),
    "Average value of assets per household (Rs.)": ("ava_per_hh", 1.0),
    "Number of households reporting cash loan per 1000 households": ("incidence_of_indebtedness", 0.1),
    "Average amount of cash loan per household (Rs.)": ("aod_per_hh", 1.0),
}
AIDIS_I9 = {"Average value (Rs.) of fixed assets": "fixed_assets_per_hh", "Average value (Rs.) of financial assets": "financial_assets_per_hh",
            "Average value (Rs.) of valuables": "valuables_per_hh", "Average value (Rs.) of cash loan outstanding": "cash_loan_per_hh"}
QB = "aidis_hh_expenditure"


@cache
def parse_aidis_api() -> tuple[dict, dict, dict]:
    """Returns (keyed values, key -> pin name, raw lookup {(ind, sector, occ, class, sub_indicator): value})."""
    out, page, raw = {}, {}, {}
    for name, r in api_records("nss77_aidis_i5_allindia"):
        assert r["state"] == "All-India" and r["indicator"].endswith("by Quintile class of household expenditure"), r
        sec, cls = r["sector"].lower(), r["quintile_class"]
        typ = AIDIS_API_TYPE[(r["sector"], r["occupational_category"])]
        item, mult = AIDIS_I5[r["sub_indicator"]]
        assert re.fullmatch(r"[1-5]|All", cls), cls
        hh = sec if cls == "All" else f"{sec}_q{cls}"
        v = _api_num(r["value"])
        raw[(5, r["sector"], r["occupational_category"], cls, r["sub_indicator"])] = v
        k = mk("NSS-77 AIDIS indicator 5", item, None, hh, D, hh_type=typ, quintile_basis=QB)
        assert k not in out, k
        out[k], page[k] = v * mult, name
    for name, r in api_records("nss77_aidis_i9_allindia"):
        assert r["state"] == "All-India", r
        sec, cls = r["sector"].lower(), r["asset_quintile_class"]
        typ = AIDIS_API_TYPE[(r["sector"], r["occupational_category"])]
        item = AIDIS_I9[r["sub_indicator"]]
        v = _api_num(r["value"])
        raw[(9, r["sector"], r["occupational_category"], cls, r["sub_indicator"])] = v
        if cls == "All (Asset Holding Class)":  # duplicate of the quintile total (checked in test_aidis_api_identities)
            continue
        if m := re.fullmatch(r"Q([1-5])", cls):
            hh, dims = f"{sec}_q{m.group(1)}", {"quintile_basis": QB}
        elif cls == "All (Qunitile Class)":  # sic, API spelling
            hh, dims = sec, {"quintile_basis": QB}
        else:
            assert re.fullmatch(r"[1-9]|10", cls), cls
            hh, dims = sec, {"asset_holding_class": f"d{cls}"}
        k = mk("NSS-77 AIDIS indicator 9", item, None, hh, D, hh_type=typ, **dims)
        assert k not in out, k
        out[k], page[k] = v, name
    return out, page, raw


# --- PLFS indicators 6-8 (quarterly earnings, agricultural years) --------------------------------
PLFS_API = {6: ("regular_wage_earnings_month", "during the preceding calendar month from regular wage/salaried employment"),
            7: ("casual_wage_earnings_day", "per day from casual labour work other than public works"),
            8: ("self_employment_gross_earnings_30d", "during last 30 days from self-employment")}
QTR_FIRST_MONTH = {"Jul-Sep": 7, "Oct-Dec": 10, "Jan-Mar": 1, "Apr-Jun": 4}
API_SECT = {"rural": "rural", "urban": "urban", "rural + urban": "total"}


def fiscal_quarter(ay: str, qlabel: str) -> str:
    """Quarter of an agricultural year (July-June) -> Indian fiscal quarter, via the calendar month."""
    y0, m = int(ay[:4]), QTR_FIRST_MONTH[qlabel]
    cal_year = y0 if m >= 7 else y0 + 1
    fy0 = cal_year if m >= 4 else cal_year - 1
    return f"Q{(m - 4) % 12 // 3 + 1} {fy0}-{(fy0 + 1) % 100:02d}"


@cache
def parse_plfs_api() -> tuple[dict, dict]:
    out, page = {}, {}
    for ind, (item, phrase) in PLFS_API.items():
        for ay in ("2022-23", "2023-24"):
            for name, r in api_records(f"plfs_i{ind}_ay{ay.replace('-', '_')}_allindia"):
                assert phrase in r["indicator"] and r["state"] == "All India" and r["unit"] == "₹", r
                assert r["year"] == ay and r["year_type"] == "Agriculture Year" and r["month"] is None, r
                k = mk(f"PLFS annual indicator {ind}", item, None, API_SECT[r["sector"]], fiscal_quarter(ay, r["quarter"]),
                       activity_status="cws", sex=r["gender"])
                assert k not in out, k
                out[k], page[k] = _api_num(r["value"]), name
    return out, page


# --- ASUSE indicator 36 (ASUSE 2025) -------------------------------------------------------------
# API activity_category -> ASUSE notation, typed from Annexure I of the pinned ASUSE 2023-24 report (pp.30-31);
# test_asuse_api_activity_map_matches_annexure checks every pair against that page text.
ASUSE_API_CODE = {
    "Cotton Ginning, Cleaning and Bailing": "M1", "Manufacture of Food Products": "M2", "Manufacture of Beverages": "M3",
    "Manufacture of Tobacco Products": "M4", "Manufacture of Textiles": "M5", "Manufacture of Wearing Apparel": "M6",
    "Manufacture of Leather and Related Products": "M7",
    "Manufacture of Wood and Products of Wood and Cork, Except Furniture, Manufacture of Articles of Straw and Plaiting Materials": "M8",
    "Manufacture of Paper and Paper Products": "M9", "Printing and Reproduction of Recorded Media": "M10",
    "Manufacture of Coke and Refined Petroleum Products": "M11", "Manufacture of Chemicals and Chemical Products": "M12",
    "Manufacture of Pharmaceuticals, Medicinal Chemical and Botanical Products": "M13",
    "Manufacture of Rubber and Plastics Products": "M14", "Manufacture of Other Non-metallic Mineral Products": "M15",
    "Manufacture of Basic Metals": "M16", "Manufacture of Fabricated Metal Products, Except Machinery and Equipment": "M17",
    "Manufacture of Computer, Electronic and Optical Products": "M18", "Manufacture of Electrical Equipment": "M19",
    "Manufacture of Machinery and Equipment N.e.c.": "M20", "Manufacture of Motor Vehicles, Trailers and Semi- Trailers": "M21",
    "Manufacture of Other Transport Equipment": "M22", "Manufacture of Furniture": "M23", "Other Manufacturing": "M24",
    "Repair and Installation of Machinery and Equipment": "M25", "Manufacturing Activities": "M",
    "Non-captive Electricity Generation and Transmission": "E",
    "Wholesale and Retail Trade of Motor Vehicles and Motor Cycles": "T1",
    "Maintenance and Repair of Motor Vehicles and Motor Cycles": "T2", "Wholesale on a Fee or Contract Basis": "T3",
    "Other Wholesale Trade": "T4", "Other Retail Trade": "T5", "Trading Activities": "T",
    "Accommodation": "S1", "Food and Accommodation Service Activities": "S2", "Land Transport": "S3", "Water Transport": "S4",
    "Warehousing and Storage": "S5", "Support Activities for Transportation, Postal and Courier Activities": "S6",
    "Information and Communication": "S7", "Financial Service Activities Except Insurance and Pension Funding": "S8",
    "Other Financial Activities": "S9", "Real Estate Activities": "S10", "Professional, Scientific and Technical Activities": "S11",
    "Administrative and Support Service Activities": "S12", "Education": "S13", "Human Health and Social Work Activities": "S14",
    "Other Community, Social and Personal Service Activities": "S15", "Other Services": "S", "All": "M+E+T+S",
}
ASUSE_I36 = {  # sub_indicator -> (item code, stock/flow)
    "Market Value (Rs.) of Land Per Estt.": ("land_value_per_estt", "stock"),
    "Market Value (Rs.) of Fixed Assets Per Estt.": ("fixed_assets_value_per_estt", "stock"),
    "Net Addition to Fixed Assets (Rs.) Per Estt. During Last 365 Days/ Last Year": ("net_addition_fixed_assets_per_estt", "flow"),
    "Outstan-ding Loan (Rs.) Per Estt.": ("outstanding_loan_per_estt", "stock"),
    "Annual Interest Payable (Rs.) Payable Per Estt.": ("interest_payable_per_estt", "flow"),
    "Annual Rental (Rs.) Payable on Hired Fixed Assets Per Estt.": ("rent_payable_hired_fixed_assets_per_estt", "flow"),
}
ASUSE_API_SECT = {"Rural": "rural", "Urban": "urban", "Combined": "total"}
ASUSE_API_EST = {"Own Account Establishments(OAE)": "oae", "Hired Worker Establishments(HWE)": "hwe", "All Establishments(All)": "all"}


@cache
def parse_asuse_api() -> tuple[dict, dict, dict]:
    """Returns (keyed values, key -> pin name, raw lookup {(sector, activity, sub_indicator, est, fixed_assets): value})."""
    out, page, raw = {}, {}, {}
    for name, r in api_records("asuse_i36_allindia"):
        assert r["state/UT"] == "All India" and r["year"] == "2025" and r["frequency"] == "Annually", r
        assert r["indicator"].startswith("Estimated Market Value of Land and Fixed Assets and Outstanding Loans"), r
        item, _ = ASUSE_I36[r["sub_indicator"]]
        code = ASUSE_API_CODE[r["activity_category"]]
        ind = "asuse_all" if code == "M+E+T+S" else f"asuse_{code}"
        dims = {"establishment_type": ASUSE_API_EST[r["establishment_type"]]}
        # only the two market-value items are split owned / hired / all
        assert (r["fixed_assets"] is not None) == item.endswith("value_per_estt"), r
        if r["fixed_assets"] is not None:
            dims["fixed_assets"] = {"Owned": "owned", "Hired": "hired", "All": "all"}[r["fixed_assets"]]
        v = _api_num(r["value"])
        raw[(r["sector"], r["activity_category"], r["sub_indicator"], r["establishment_type"], r["fixed_assets"])] = v
        k = mk("ASUSE indicator 36", item, ind, ASUSE_API_SECT[r["sector"]], "2025", **dims)
        assert k not in out, k
        out[k], page[k] = v, name
    return out, page, raw


API_DATASETS = ["aidis_2019_quintile", "plfs_earnings_api", "asuse_2025_assets_loans"]


# ------------------------------------------------------------------------------------------------
# hand anchors: typed from the printed page text during verification (PDF page = 1-based index)
# ------------------------------------------------------------------------------------------------
HAND_ANCHORS = [
    # (dataset, series_id, period, value, where)
    ("plfs_lfs_indicators", "lfs.lfpr.ps_ss.15plus.total.person", "2023-07/2024-06", 60.1, "PLFS p.22 Highlights D T1"),
    ("plfs_lfs_indicators", "lfs.lfpr.ps_ss.15plus.rural.female", "2018-07/2019-06", 26.4, "PLFS p.22"),
    ("plfs_lfs_indicators", "lfs.lfpr.ps_ss.all.urban.male", "2017-07/2018-06", 57.0, "PLFS p.22"),
    ("plfs_status_dist", "st6.worker_share.regular_wage.urban.female", "2023-07/2024-06", 49.4, "PLFS p.42 St 6"),
    ("plfs_status_dist", "st6.worker_share.casual_labour.total.person", "2021-07/2022-06", 22.7, "PLFS p.42"),
    ("plfs_status_dist", "st6.worker_share.helper.rural.female", "2022-07/2023-06", 43.1, "PLFS p.42"),
    ("plfs_industry_dist", "t26.worker_share.0111.rural.male", "2023-07/2024-06", 16.57, "PLFS p.213 T26"),
    ("plfs_industry_dist", "t26.worker_share.97.urban.female", "2023-07/2024-06", 10.9, "PLFS p.228 (division 97 printed to 1 dp)"),
    ("plfs_industry_dist", "t26.sample_workers.total.person", "2023-07/2024-06", 183070, "PLFS p.228 '1,83,070'"),
    ("plfs_earnings", "st10.regular_wage_earnings_month.total.person.current", "Q2 2023-24", 20095, "PLFS p.47 St 10 Jul-Sep 2023"),
    ("plfs_earnings", "st10.regular_wage_earnings_month.rural.female.current", "Q1 2024-25", 12396, "PLFS p.47 Apr-Jun 2024"),
    ("plfs_earnings", "st11.casual_wage_earnings_day.urban.person.current", "Q3 2023-24", 504, "PLFS p.48 St 11 Oct-Dec 2023"),
    ("plfs_earnings", "st12.self_employment_gross_earnings_30d.total.male.current", "Q4 2023-24", 16334, "PLFS p.48 St 12 Jan-Mar 2024"),
    ("plfs_earnings", "t51.casual_wage_day.j.urban.female.current", "2023-07/2024-06", 2000, "PLFS p.407 T51 '2,000'"),
    ("plfs_earnings", "t51.sample_days.a.total.person", "2023-07/2024-06", 43831, "PLFS p.408"),
    ("asuse_key_indicators", "fs.gva.asuse_all.total.current", "2023-10/2024-09", 1797278, "Factsheet p.6 T1 '17,97,278' Rs crore"),
    ("asuse_key_indicators", "fs.establishments.asuse_all.rural", "2022-10/2023-09", 35643300, "Factsheet p.6 '3,56,433' in '00"),
    ("asuse_key_indicators", "fs.workers.asuse_s.total", "2023-10/2024-09", 47102600, "Factsheet p.8 T2 '4,71,026' in '00"),
    ("asuse_key_indicators", "fs.emol_per_hired_worker.asuse_all.rural.current", "2023-10/2024-09", 122095, "Factsheet p.10 T3"),
    ("asuse_key_indicators", "fs.gvo_per_estt.asuse_m.urban.current", "2023-10/2024-09", 1076502, "Factsheet p.11 T4 '10,76,502'"),
    ("asuse_key_indicators", "fs.pct_hwe.asuse_s.urban", "2023-10/2024-09", 19.25, "Factsheet p.12 T6"),
    ("asuse_2324_activity", "t4.establishments.asuse_m2.rural.hwe", "2023-10/2024-09", 150875, "Report p.89 T4"),
    ("asuse_2324_activity", "t4.establishments.asuse_all.rural.hwe", "2023-10/2024-09", 2791253, "Report p.89 T4 M+E+T+S"),
    ("asuse_2324_activity", "t6.estt_share.partnership_same_hh.asuse_m13.rural.hwe", "2023-10/2024-09", 32.2, "Report p.134 T6 '322' per 1000"),
    ("asuse_2324_activity", "t6.estt_share.cooperative.asuse_t4.rural.hwe", "2023-10/2024-09", 16.3, "Report p.134 T6 '163' per 1000"),
    ("asuse_2324_activity", "t33.emol_per_hired_worker.all.asuse_all.rural.current", "2023-10/2024-09", 122095, "Report p.1007 T33"),
    ("asuse_2324_activity", "t33.hired_workers.formal.asuse_s13.rural", "2023-10/2024-09", 512601, "Report p.1007 T33"),
    ("asuse_2324_activity", "t35.gva_per_worker.asuse_m1.rural.hwe.current", "2023-10/2024-09", 426755, "Report p.1022 T35"),
    ("asuse_2324_activity", "t37.gva_per_estt.asuse_e.urban.hwe.current", "2023-10/2024-09", 5640175, "Report p.1032 T37"),
    ("asi_principal_characteristics", "s3a.gva.current", "2023-24", 2458336.05, "ASI SR p.34 St 3A 245833605 lakh"),
    ("asi_principal_characteristics", "s3a.workers", "2019-20", 13058156, "ASI SR p.34"),
    ("asi_principal_characteristics", "s3a.net_profit.current", "2021-22", 950713.68, "ASI SR p.34 95071368 lakh"),
    ("asi_2324_industry", "s5a.gva.24.current", "2023-24", 284236.73, "ASI SR p.39 St 5A 28423673 lakh"),
    ("asi_2324_industry", "s5a.persons_engaged.other", "2023-24", 589847, "ASI SR p.39 'OT'"),
    ("asi_2324_industry", "v1t3.workers_direct_women.1020", "2023-24", 45923, "ASI Vol I p.320 T3"),
    ("asi_2324_industry", "v1t3.mandays.all", "2023-24", 6005509000, "ASI Vol I p.320 6005509 ('000)"),
    # second pass: PLFS Table (20) (pp.147-155) and Table (35) all-India rows (pp.274-282), typed from page text
    ("plfs_industry_status", "t20.worker_share.regular_wage.10-33.rural.male", "2023-07/2024-06", 51.4, "PLFS p.147 T20"),
    ("plfs_industry_status", "t20.worker_share.casual_labour.41-43.rural.male", "2023-07/2024-06", 83.1, "PLFS p.147"),
    ("plfs_industry_status", "t20.worker_share.own_account_employer.49-53.rural.male", "2023-07/2024-06", 53.3, "PLFS p.147 '49-53( transport)'"),
    ("plfs_industry_status", "t20.worker_share.self_employed.55-56.rural.male", "2023-07/2024-06", 59.3, "PLFS p.147 'services))'"),
    ("plfs_industry_status", "t20.sample_workers.casual_labour.rural.male", "2023-07/2024-06", 16323, "PLFS p.147 '16,323'"),
    ("plfs_industry_status", "t20.worker_share.helper.all.rural.female", "2023-07/2024-06", 42.3, "PLFS p.148 total row"),
    ("plfs_industry_status", "t20.worker_share.regular_wage.58-99.urban.female", "2023-07/2024-06", 84.1, "PLFS p.151"),
    ("plfs_industry_status", "t20.worker_share.regular_wage.58-99.total.person", "2023-07/2024-06", 75.8, "PLFS p.155"),
    ("plfs_industry_status", "t20.worker_share.casual_labour.45-99.total.person", "2023-07/2024-06", 4.1, "PLFS p.155"),
    ("plfs_industry_status", "t20.sample_workers.all.total.person", "2023-07/2024-06", 183070, "PLFS p.155 '1,83,070'"),
    ("plfs_enterprise_type", "t35.worker_share.govt_public_sector.rural.male", "2023-07/2024-06", 7.2, "PLFS p.274 all India"),
    ("plfs_enterprise_type", "t35.sample_workers.pvt_public_ltd_company.rural.male", "2023-07/2024-06", 2496, "PLFS p.274 '2,496'"),
    ("plfs_enterprise_type", "t35.worker_share.employer_households.urban.female", "2023-07/2024-06", 12.4, "PLFS p.278"),
    ("plfs_enterprise_type", "t35.worker_share.autonomous_bodies.urban.female", "2023-07/2024-06", 0.6, "PLFS p.278"),
    ("plfs_enterprise_type", "t35.worker_share.govt_public_sector.total.person", "2023-07/2024-06", 10.6, "PLFS p.282"),
    ("plfs_enterprise_type", "t35.sample_workers.all.total.person", "2023-07/2024-06", 110937, "PLFS p.282 '1,10,937'"),
    ("aidis_2019_press_note", "pn.ava_per_hh.urban.self_employed.current", D, 4151226, "Press note p.3 'Rs. 41,51,226'"),
    ("aidis_2019_press_note", "pn.aod_per_indebted_hh.urban.all.current", D, 536861, "Press note p.5"),
    ("sas_2019_income_by_landclass", "s5_1b.income_total.agri_all.current", "2018-07/2019-06", 8337, "SAS p.116 St 5.1B"),
    ("sas_2019_income_by_landclass", "s5_7.outstanding_loan_per_hh.agri_land_gt10.00.current", "2018-07/2019-06", 791132, "SAS p.123 '7,91,132'"),
    # final pass (VER-C1): St 1.3, p.77 'Social Group: all', col (2) agricultural households (word x 248-265)
    ("sas_2019_income_by_landclass", "s1_3.hh_share.agri_land_0.41-1.00", SAS_AY, 35.6, "SAS p.77 '0.40 - 1.00'"),
    ("sas_2019_income_by_landclass", "s1_3.hh_share.agri_land_lt0.01", SAS_AY, 0.6, "SAS p.77 St 1.3 '< 0.01'"),
    # close-out pass: eSankhyiki API records, typed from the raw JSON pages (file, record index 0-based)
    ("aidis_2019_quintile", "i5.hh_distribution.rural_q1.cultivator", D, 17.0, "i5 p1 #0 '170' per 1000"),
    ("aidis_2019_quintile", "i5.ava_per_hh.rural_q1.cultivator.current", D, 1100360, "i5 p1 #1"),
    ("aidis_2019_quintile", "i5.incidence_of_indebtedness.rural_q1.cultivator", D, 32.0, "i5 p1 #2 '320' per 1000"),
    ("aidis_2019_quintile", "i5.aod_per_hh.rural_q1.cultivator.current", D, 28039, "i5 p1 #3"),
    ("aidis_2019_quintile", "i5.incidence_of_indebtedness.rural_q1.all", D, 26.5, "i5 p1 #50 '265'"),
    ("aidis_2019_quintile", "i5.aod_per_hh.urban_q1.other.current", D, 23191, "i5 p1 #99 (Urban, Others)"),
    ("aidis_2019_quintile", "i5.incidence_of_indebtedness.urban_q4.other", D, 18.7, "i5 p2 #10 '187'"),
    ("aidis_2019_quintile", "i5.aod_per_hh.urban.all.current", D, 120336, "i5 p2 #43 (class All)"),
    ("aidis_2019_quintile", "i9.financial_assets_per_hh.rural.non_cultivator.ahc_d10.current", D, 442318, "i9 p2 #5 (asset class '10')"),
    ("aidis_2019_quintile", "i9.fixed_assets_per_hh.urban_q5.all.current", D, 2750466, "i9 p5 #0 ('Q5')"),
    ("aidis_2019_quintile", "i9.cash_loan_per_hh.urban.all.current", D, 120336, "i9 p5 #7 ('All (Qunitile Class)')"),
    ("plfs_earnings_api", "api_i6.regular_wage_earnings_month.rural.male.current", "Q2 2022-23", 16205.8, "i6 ay2022-23 #0 Jul-Sep"),
    ("plfs_earnings_api", "api_i6.regular_wage_earnings_month.total.person.current", "Q1 2023-24", 20039.2, "i6 ay2022-23 #35 Apr-Jun"),
    ("plfs_earnings_api", "api_i7.casual_wage_earnings_day.rural.female.current", "Q2 2022-23", 258.7, "i7 ay2022-23 #12"),
    ("plfs_earnings_api", "api_i8.self_employment_gross_earnings_30d.total.female.current", "Q2 2023-24", 5297.2, "i8 ay2023-24 #20"),
    ("asuse_2025_assets_loans", "i36.land_value_per_estt.asuse_m1.rural.hwe.fa_owned.current", "2025", 2144373, "i36 p1 #0"),
    ("asuse_2025_assets_loans", "i36.net_addition_fixed_assets_per_estt.asuse_m25.urban.all.current", "2025", 4258, "i36 p23 #40"),
    ("asuse_2025_assets_loans", "i36.interest_payable_per_estt.asuse_all.total.all.current", "2025", 4338, "i36 p45 #99 ('All', Combined)"),
]

# ------------------------------------------------------------------------------------------------
# tests
# ------------------------------------------------------------------------------------------------


def _plfs_industry():
    t26, _ = parse_plfs_t26()
    return {**parse_plfs_st7(), **t26}, set()


def _plfs_earnings():
    t51, z51 = parse_plfs_t51()
    return {**parse_plfs_earn_statements(), **t51}, z51


def _asi_industry():
    v1, _ = parse_asi_v1t3()
    return {**parse_asi_5a(), **v1}, set()


PARSERS = {
    "plfs_lfs_indicators": lambda: (parse_plfs_lfs(), set()),
    "plfs_status_dist": lambda: (parse_plfs_st6(), set()),
    "plfs_industry_dist": _plfs_industry,
    "plfs_earnings": _plfs_earnings,
    "asuse_key_indicators": lambda: (parse_asuse_factsheet(), set()),
    "asuse_2324_activity": parse_asuse_report,
    "asi_principal_characteristics": lambda: (parse_asi_3a(), set()),
    "asi_2324_industry": _asi_industry,
    "aidis_2019_press_note": lambda: (parse_aidis(), set()),
    "sas_2019_income_by_landclass": lambda: (parse_sas(), set()),
    "plfs_industry_status": lambda: (parse_plfs_t20()[0], set()),
    "plfs_enterprise_type": lambda: (parse_plfs_t35()[0], set()),
    "aidis_2019_quintile": lambda: (parse_aidis_api()[0], set()),
    "plfs_earnings_api": lambda: (parse_plfs_api()[0], set()),
    "asuse_2025_assets_loans": lambda: (parse_asuse_api()[0], set()),
}


@cache
def parsed(ds: str) -> tuple[dict, set]:
    return PARSERS[ds]()


DATASETS = [
    "plfs_lfs_indicators", "plfs_status_dist", "plfs_industry_dist", "plfs_earnings", "asuse_key_indicators",
    "asuse_2324_activity", "asi_principal_characteristics", "asi_2324_industry", "aidis_2019_press_note",
    "sas_2019_income_by_landclass", "plfs_industry_status", "plfs_enterprise_type",
]


def close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-6 * max(1.0, abs(b))


@pytest.mark.parametrize("ds", DATASETS + API_DATASETS)
def test_census_clean_matches_pdf(ds):
    """Every clean row equals the verifier's re-parse; every parsed cell has a clean row (no dropped rows).
    Close-out pass: the 3 eSankhyiki API datasets are in the census too, re-parsed from the raw JSON pages."""
    exp, skipped = parsed(ds)
    df = load(ds)
    bad, missing_in_parse, seen = [], [], set()
    for r in df.iter_rows(named=True):
        k = row_key(r)
        assert k not in seen, ("duplicate key", k)
        seen.add(k)
        if k not in exp:
            missing_in_parse.append((r["series_id"], r["period"], k))
            continue
        if not close(r["value"], exp[k]):
            bad.append((r["series_id"], r["period"], r["value"], exp[k]))
    dropped = sorted(set(exp) - seen)
    in_skips = [k for k in seen if k in skipped]
    assert not bad, f"{len(bad)} value mismatches, e.g. {bad[:10]}"
    assert not missing_in_parse, f"{len(missing_in_parse)} clean rows the verifier cannot find in the PDF, e.g. {missing_in_parse[:5]}"
    assert not dropped, f"{len(dropped)} published cells without a clean row, e.g. {dropped[:5]}"
    assert not in_skips, f"zero/no-observation cells ingested as values: {in_skips[:5]}"


@pytest.mark.parametrize("ds,sid,period,value,where", HAND_ANCHORS)
def test_hand_anchors(ds, sid, period, value, where):
    df = load(ds).filter((pl.col("series_id") == sid) & (pl.col("period") == period))
    assert len(df) == 1, (sid, period, where)
    assert close(df["value"][0], value), (sid, df["value"][0], value, where)
    # and the verifier's parser agrees with the hand value
    k = row_key(df.row(0, named=True))
    assert close(parsed(ds)[0][k], value), where


SY_RX = r"(\d{4})-(\d{2})/(\d{4})-(\d{2})"


def _months(period: str) -> int:
    y0, m0, y1, m1 = map(int, re.fullmatch(SY_RX, period).groups())
    return (y1 - y0) * 12 + m1 - m0 + 1


def test_survey_periods():
    """Close-out pass (replaces test_survey_period_flags). Survey windows that are not fiscal years are `sy`
    periods, and the old `survey_year` flag is gone everywhere. The expected period type for each table is
    set here independently: PLFS/SAS July-June and ASUSE October-September survey windows, PLFS
    Statements 10-12 and the API as fiscal quarters, ASI as a true fiscal year, AIDIS stocks at 30.06.2018,
    and the AIDIS deposit-account share for calendar 2019."""
    want = {  # (dataset, table_id) -> set of (period_type, period) allowed
        ("plfs_lfs_indicators", None): {("sy", jul_jun(f"{y}-{(y + 1) % 100:02d}")) for y in range(2017, 2024)},
        ("plfs_status_dist", None): {("sy", jul_jun(y)) for y in ("2021-22", "2022-23", "2023-24")},
        ("plfs_industry_dist", "Statement 7"): {("sy", jul_jun(y)) for y in ("2021-22", "2022-23", "2023-24")},
        ("plfs_industry_dist", "Table (26)"): {("sy", PLFS_2324)},
        ("plfs_earnings", "Table (51)"): {("sy", PLFS_2324)},
        ("plfs_industry_status", None): {("sy", PLFS_2324)},
        ("plfs_enterprise_type", None): {("sy", PLFS_2324)},
        ("asuse_key_indicators", None): {("sy", oct_sep("2022-23")), ("sy", oct_sep("2023-24"))},
        ("asuse_2324_activity", None): {("sy", oct_sep("2023-24"))},
        ("sas_2019_income_by_landclass", None): {("sy", SAS_AY)},
        ("asi_principal_characteristics", None): {("fy", f"{y}-{(y + 1) % 100:02d}") for y in range(2019, 2024)},
        ("asi_2324_industry", None): {("fy", "2023-24")},
        ("aidis_2019_quintile", None): {("date", D)},
        ("plfs_earnings_api", None): {("fq", f"Q{q} {y}-{(y + 1) % 100:02d}") for q, y in
                                      ((2, 2022), (3, 2022), (4, 2022), (1, 2023), (2, 2023), (3, 2023), (4, 2023), (1, 2024))},
        ("asuse_2025_assets_loans", None): {("cy", "2025")},
    }
    fq_st = {("fq", p) for p in ("Q2 2023-24", "Q3 2023-24", "Q4 2023-24", "Q1 2024-25")}
    aidis_pn = {  # item -> period (press note: stocks at 30.06.2018; FCE agricultural year; accounts 2019)
        "pct_hh_reporting_fce": ("sy", jul_jun("2018-19")), "fce_per_hh": ("sy", jul_jun("2018-19")),
        "pct_adults_with_bank_deposit_account": ("cy", "2019"),
    }
    for ds in DATASETS + API_DATASETS:
        df = load(ds)
        assert not df["dim_other"].drop_nulls().str.contains("survey_year").any(), ds
        for r in df.iter_rows(named=True):
            got = (r["period_type"], r["period"])
            if ds == "plfs_earnings" and r["table_id"].startswith("Statement"):
                ok = got in fq_st
            elif ds == "aidis_2019_press_note":
                ok = got == aidis_pn.get(r["item_code"], ("date", D))
            else:
                rule = want.get((ds, r["table_id"])) or want[(ds, None)]
                ok = got in rule
            assert ok, (ds, r["table_id"], r["series_id"], got)
            if r["period_type"] == "sy":  # every survey window is 12 months (SAS Statement 1.3 included)
                assert _months(got[1]) == 12, (ds, r["series_id"], r["period"])


def test_sas_statement_1_3_period_is_the_printed_window():
    """VER-C1 (closed in the final pass, 2026-09-29; was a strict xfail). Statement 1.3 carries the window
    printed in its title on BOTH title pages (pp.76-77), not the visit-1 window. The p.77 footnote
    ("Based on the land possessed by the household during July-December 2018") dates the land-possessed
    classifier, and the provenance note must say so, so the nuance is not lost."""
    title = "Statement 1.3: Percentage distribution of agricultural and non-"
    pages = [q for q in range(70, 130) if title in text(SAS, q)]
    assert len(pages) == 2, pages
    printed = {sas_title_window(text(SAS, q), "1.3") for q in pages}
    assert printed == {SAS_AY}, printed
    s13 = load("sas_2019_income_by_landclass").filter(pl.col("table_id") == "Statement 1.3")
    assert s13.height == 8 and set(s13["period"]) == {SAS_AY} and set(s13["period_type"]) == {"sy"}, s13
    t = re.sub(r"\s+", " ", text(SAS, _sas_page(r"Statement 1\.3: Percentage distribution", "Social Group: all")))
    assert "Note: Based on the land possessed by the household during July-December 2018" in t
    (pid,) = set(s13["prov_id"])
    (note,) = pl.read_parquet(CLEAN / "_provenance.parquet").filter(pl.col("prov_id") == pid)["notes"]
    assert "agricultural year July 2018 - June 2019" in note and "July-December 2018" in note, note


def test_survey_windows_are_printed_in_the_documents():
    """The window rules jul_jun / oct_sep / SAS_AY are stated in the pinned documents themselves."""
    t = re.sub(r"\s+", " ", text(PLFS, 22))
    assert "2023-24 refers to the period July 2023 – June 2024 and likewise for 2022-23, 2021-22, 2020-21, 2019-20, 2018-19 and 2017-18" in t
    t = re.sub(r"\s+", " ", text(FS, 3))
    assert "ASUSE 2022-23 conducted during October 2022 to September 2023" in t
    assert "ASUSE 2023-24 was conducted during October 2023 to September 2024" in t
    t = re.sub(r"\s+", " ", text(SAS, 14))
    assert "Information was collected primarily for the agricultural year 2018-19" in t
    assert "visit-1: information was collected for July-December 2018" in t  # visit 1 (VER-C1: St 1.3 land basis)
    t = re.sub(r"\s+", " ", text(AIDIS, 2))
    assert "during the Agricultural Year 2018-19 (July-June)" in t and "as on 30.06.2018" in t


def test_units_and_status():
    for ds in DATASETS + API_DATASETS:
        df = load(ds)
        assert (df["status"] == "official").all(), ds
        # money must never be a per-lakh/thousand count; INR_crore only for aggregates
        money = df.filter(pl.col("unit") == "INR_crore")
        assert money["item_code"].is_in(["gva", "fixed_capital", "working_capital", "invested_capital", "gross_value_plant_machinery",
                                         "total_input", "total_output", "nva", "total_emoluments", "wages_to_workers", "depreciation",
                                         "rent_paid", "interest_paid", "net_income", "net_profit", "bonus", "employers_contribution",
                                         "wages_salary", "wages_salary_incl_bonus", "wages_salaries_incl_employer_contrib",
                                         "wages_salary_workers", "wages_salary_supervisory", "wages_salary_other_employees"]).all(), ds


def test_plfs_table20_industry_x_status_is_in_pinned_pdf():
    """VER-1 (first pass): PLFS AR Table (20) (workers by status in employment for each industry of work,
    9 sector x sex blocks) is printed in the pinned PDF. Second pass: it is now ingested as
    plfs_industry_status (full census in test_census_clean_matches_pdf); Statement 6 stays industry-free."""
    pages = find_pages(PLFS, 140, 160, r"Table \(20\):\s*Percentage distribution of workers in usual status \(ps\+ss\) by broad status")
    blocks = {}
    for p in pages:
        L = [x.strip() for x in lines(PLFS, p)]
        (hdr,) = [x for x in L if re.fullmatch(r"all-India (rural|urban|rural\+urban) (male|female|persons?)", x)]
        rows = [x for x in L if re.fullmatch(rf"\d\d-\d\d\s*\(.*\)\s*(?:{NUM}\s+){{5}}{NUM}", x) or x.startswith("total ")]
        blocks[hdr] = rows
    assert len(blocks) == 9, sorted(blocks)
    assert all(len(r) == 12 for r in blocks.values()), {k: len(v) for k, v in blocks.items()}
    # second pass: the table is ingested in its own dataset, 9 blocks x (12 rows x 6 shares + 6 sample counts)
    t20 = load("plfs_industry_status")
    assert t20.height == 9 * (12 * 6 + 6)
    assert set(t20["table_id"]) == {"Table (20)"}
    assert load("plfs_status_dist").filter(pl.col("industry").is_not_null()).height == 0  # St 6 dataset unchanged


def test_plfs_table20_identities_and_cross_tables():
    """Row identities, sample-count additivity, total row == Statement 6 (2023-24), and the sample-worker
    total == Table (26) sample workers, per block."""
    _, blocks = parse_plfs_t20()
    st6 = parsed("plfs_status_dist")[0]
    t26 = parse_plfs_t26()[0]
    for (hh, sx), rows in blocks.items():
        for code, v in rows.items():
            if code == "sample workers":
                assert v[0] + v[1] == v[2] and v[2] + v[3] + v[4] == v[5], (hh, sx, v)
            else:
                assert abs(v[0] + v[1] - v[2]) <= 0.15, (hh, sx, code, v)
                assert abs(v[2] + v[3] + v[4] - v[5]) <= 0.25 and v[5] == 100.0, (hh, sx, code, v)
        for st, v in zip(T20_STATUS, rows["total"], strict=True):
            k = mk("Statement 6", f"worker_share_{st}", None, hh, PLFS_2324, activity_status="ps_ss", employment_status=st, sex=sx)
            assert st6[k] == v, (hh, sx, st, st6[k], v)
        k26 = mk("Table (26)", "sample_workers", None, hh, PLFS_2324, activity_status="ps_ss", sex=sx)
        assert t26[k26] == rows["sample workers"][5], (hh, sx)


def test_plfs_table35_identities():
    """Table (35) all-India rows: shares add to 100 (rounding), sample counts add exactly, col (11) == count total;
    sectors and sexes add up in the sample counts."""
    _, blocks = parse_plfs_t35()
    for (hh, sx), (shares, counts) in blocks.items():
        assert shares[8] == 100.0 and abs(sum(shares[:8]) - 100) <= 0.5, (hh, sx, shares)
        assert sum(counts[:8]) == counts[8] == shares[9], (hh, sx, counts, shares)
    for hh in ("rural", "urban", "total"):
        a = [x + y for x, y in zip(blocks[(hh, "male")][1], blocks[(hh, "female")][1], strict=True)]
        assert a == blocks[(hh, "person")][1], hh
    for sx in SEX3:
        a = [x + y for x, y in zip(blocks[("rural", sx)][1], blocks[("urban", sx)][1], strict=True)]
        assert a == blocks[("total", sx)][1], sx


def test_new_tables_provenance_pages_and_flags():
    """Provenance locators name the pages the verifier found by title. Rows carry the PLFS 2023-24 survey window
    as an `sy` period. Close-out pass: this replaces the old fy '2023-24' + survey_year=jul_jun convention, a
    label change only; the values are still checked by the census."""
    prov = pl.read_parquet(CLEAN / "_provenance.parquet")
    for ds, title, lo, hi in (("plfs_industry_status", T20_TITLE, 140, 160), ("plfs_enterprise_type", T35_TITLE, 268, 290)):
        pages = find_pages(PLFS, lo, hi, title)
        df = load(ds)
        for pid in df["prov_id"].unique().to_list():
            loc = prov.filter(pl.col("prov_id") == pid)["locator"][0]
            assert loc.startswith(f"pp.{pages[0]}-{pages[-1]}"), (ds, loc, pages)
        assert (df["status"] == "official").all() and (df["period"] == PLFS_2324).all()
        assert (df["period_type"] == "sy").all() and not df["dim_other"].str.contains("survey_year").any(), ds
        assert set(df.filter(pl.col("unit") == "count")["item_code"]) == {"sample_workers"}, ds
        assert set(df.filter(pl.col("item_code") != "sample_workers")["unit"]) == {"percent"}, ds


def test_aidis_whole_number_percents_carry_rounded_provenance():
    """VER-6 fix: every AIDIS percent printed without a decimal point (and only those) points to the
    ROUNDED provenance record, and that record's note names the series."""
    toks: dict = {}
    parse_aidis(toks)
    prov = {r["prov_id"]: r["notes"] or "" for r in pl.read_parquet(CLEAN / "_provenance.parquet").iter_rows(named=True)}
    n_whole = 0
    for r in load("aidis_2019_press_note").filter(pl.col("unit") == "percent").iter_rows(named=True):
        tok = toks[row_key(r)]
        whole = "." not in tok
        n_whole += whole
        note = prov[r["prov_id"]]
        assert ("ROUNDED" in note) == whole, (r["series_id"], tok)
        if whole:
            assert r["series_id"] in note, r["series_id"]
    assert n_whole == 23


def test_print_seeded_sample():
    """Not an assertion: prints a seeded sample of matched rows for the verification notes."""
    rng = random.Random(SEED)
    for ds in DATASETS:
        df = load(ds)
        idx = rng.sample(range(len(df)), k=min(3, len(df)))
        exp = parsed(ds)[0]
        for i in idx:
            r = df.row(i, named=True)
            print(ds, r["series_id"], r["period"], r["value"], exp[row_key(r)])


# ------------------------------------------------------------------------------------------------
# close-out pass: eSankhyiki API datasets (aidis_2019_quintile, plfs_earnings_api, asuse_2025_assets_loans)
# ------------------------------------------------------------------------------------------------
PROV = CLEAN / "_provenance.parquet"


def test_api_pins_and_access():
    """58 API pages are pinned: AIDIS i5 has 2, i9 has 5, PLFS has 6 x 1 and ASUSE i36 has 45. Every page passes
    api_pages' URL, sha256 and paging checks. The sidecars show plain keyless GETs: status 200, no
    redirects, and no cookie or authorization header (D1-1, D1-6)."""
    counts = {s: len(api_pages(s)) for s in API_STEMS}
    assert counts == {"nss77_aidis_i5_allindia": 2, "nss77_aidis_i9_allindia": 5, **{s: 1 for s in API_STEMS if s.startswith("plfs")},
                      "asuse_i36_allindia": 45}, counts
    pins = yaml.safe_load(PINS.read_text(encoding="utf-8"))["pins"]
    api = [v for k, v in pins.items() if k.startswith(API_SRC + "/")]
    assert len(api) == 58 == sum(counts.values()) and len(pins) == 65
    for v in api:
        meta = json.loads((ROOT / (v["path"] + ".meta.json")).read_text(encoding="utf-8"))
        assert meta["status"] == 200 and meta["redirects"] == [] and meta["method"] == "GET", v["path"]
        hdrs = {h.lower() for h in meta["request_headers"]}
        assert not hdrs & {"cookie", "authorization", "x-api-key"}, v["path"]


def test_aidis_api_vs_press_note():
    """The all-class rows of the NSS-77 AIDIS API equal the press note, which the verifier parses on its own from
    the PDF. The rows checked are assets, cash loans and incidence of indebtedness by R/U x household type, plus
    physical (= API 'fixed') and financial assets for all households."""
    raw = parse_aidis_api()[2]
    pn = parse_aidis()
    occ = {"rural": {"all": "All", "cultivator": "Cultivator", "non_cultivator": "Non-cultivator"},
           "urban": {"all": "All", "self_employed": "Self-employed", "other": "Others"}}
    n = 0
    for hh, types in occ.items():
        S = hh.capitalize()
        for typ, o in types.items():
            def p(item, hh=hh, typ=typ):
                return pn[mk("Press note", item, None, hh, D, hh_type=typ)]
            assert raw[(5, S, o, "All", "Average value of assets per household (Rs.)")] == p("ava_per_hh"), (hh, typ)
            assert raw[(5, S, o, "All", "Average amount of cash loan per household (Rs.)")] == p("aod_per_hh"), (hh, typ)
            ioi = raw[(5, S, o, "All", "Number of households reporting cash loan per 1000 households")] / 10
            assert abs(ioi - p("incidence_of_indebtedness")) < 1e-9, (hh, typ, ioi, p("incidence_of_indebtedness"))
            n += 3
        allq = "All (Qunitile Class)"
        phys = pn[mk("Press note", "ava_physical_per_hh", None, hh, D, hh_type="all")]
        fin = pn[mk("Press note", "ava_financial_per_hh", None, hh, D, hh_type="all")]
        assert raw[(9, S, "All", allq, "Average value (Rs.) of fixed assets")] == phys, hh
        assert raw[(9, S, "All", allq, "Average value (Rs.) of financial assets")] == fin, hh
        n += 2
    assert n == 22


def test_aidis_api_identities():
    """Internal consistency of indicators 5 and 9 on the raw JSON:
    - each household type's per-1000 distribution over quintile classes 1-5 adds to 1000 (+-1), and its 'All'
      class is 1000;
    - for all households the five classes hold 200 each, so they are quintiles of households;
    - fixed + financial assets (i9) equal 'assets' (i5) within Rs 2, so valuables are outside 'assets';
    - i9 cash loans equal i5 cash loans;
    - the 'All (Asset Holding Class)' total equals the 'All (Qunitile Class)' total;
    - the asset-holding classes 1-10 rise in fixed assets (ordered classes), for every household type."""
    raw = parse_aidis_api()[2]
    occs = {"Rural": ("Cultivator", "Non-cultivator", "All"), "Urban": ("Self-employed", "Others", "All")}
    d1000 = "Per 1000 number of households"
    for S, os_ in occs.items():
        for o in os_:
            d = [raw[(5, S, o, q, d1000)] for q in "12345"]
            assert abs(sum(d) - 1000) <= 1 and raw[(5, S, o, "All", d1000)] == 1000, (S, o, d)
            if o == "All":
                assert d == [200.0] * 5, (S, d)
            for q5, q9 in [(str(i), f"Q{i}") for i in range(1, 6)] + [("All", "All (Qunitile Class)")]:
                fx = raw[(9, S, o, q9, "Average value (Rs.) of fixed assets")]
                fn = raw[(9, S, o, q9, "Average value (Rs.) of financial assets")]
                assert abs(fx + fn - raw[(5, S, o, q5, "Average value of assets per household (Rs.)")]) <= 2, (S, o, q5)
                loan9 = raw[(9, S, o, q9, "Average value (Rs.) of cash loan outstanding")]
                assert loan9 == raw[(5, S, o, q5, "Average amount of cash loan per household (Rs.)")], (S, o, q5)
            for si in AIDIS_I9:
                assert raw[(9, S, o, "All (Asset Holding Class)", si)] == raw[(9, S, o, "All (Qunitile Class)", si)], (S, o, si)
            fixed = [raw[(9, S, o, str(i), "Average value (Rs.) of fixed assets")] for i in range(1, 11)]
            assert fixed == sorted(fixed), (S, o, fixed)


def test_plfs_api_vs_ar_statements():
    """Agricultural year 2023-24 from the API = PLFS AR 2023-24 Statements 10-12 (the verifier's own PDF parse):
    108 cells within Rs 0.5 (API one decimal, AR whole rupees). The match proves the quarter mapping
    independently: the AR prints month names, the API prints 'Jul-Sep' etc. The API also adds April-June 2023
    (Q1 2023-24) for all 27 series, and the AR PDF has no such row."""
    api = parse_plfs_api()[0]
    ar = parse_plfs_earn_statements()
    st = {"PLFS annual indicator 6": "Statement 10", "PLFS annual indicator 7": "Statement 11", "PLFS annual indicator 8": "Statement 12"}
    n = 0
    for (tab, item, ind, hh, dims, per), v in api.items():
        k = (st[tab], item, ind, hh, dims, per)
        if k in ar:
            n += 1
            assert abs(v - ar[k]) <= 0.5 + 1e-9, (k, v, ar[k])
    assert n == 108 == len(ar)
    q1 = [k for k in api if k[5] == "Q1 2023-24"]
    assert len(q1) == 27 and not any(k[5] == "Q1 2023-24" for k in ar)
    assert load("plfs_earnings").filter(pl.col("period") == "Q1 2023-24").height == 0  # the PDF dataset really lacks it


def test_asuse_api_identities():
    """ASUSE i36 on the raw JSON:
    - owned + hired = all, within Rs 2, for land and fixed assets;
    - 'All Establishments' lies between OAE and HWE, and 'Combined' between Rural and Urban (weighted means,
      +-1 for rounding), which guards the establishment-type and sector labels;
    - no value is negative."""
    raw = parse_asuse_api()[2]
    oae, hwe = "Own Account Establishments(OAE)", "Hired Worker Establishments(HWE)"
    for (s, a, si, e, fa), v in raw.items():
        assert v >= 0
        if fa == "All":
            assert abs(raw[(s, a, si, e, "Owned")] + raw[(s, a, si, e, "Hired")] - v) <= 2, (s, a, si, e)
        if e == "All Establishments(All)":
            x, y = raw[(s, a, si, oae, fa)], raw[(s, a, si, hwe, fa)]
            assert min(x, y) - 1 <= v <= max(x, y) + 1, (s, a, si, fa, x, y, v)
        if s == "Combined":
            x, y = raw[("Rural", a, si, e, fa)], raw[("Urban", a, si, e, fa)]
            assert min(x, y) - 1 <= v <= max(x, y) + 1, (a, si, e, fa, x, y, v)
    assert len(raw) == 4500


def _annexure_text() -> str:
    """Annexure I of the pinned ASUSE 2023-24 report (found by title), with codes, NIC numbers and NIC-column
    words removed, letters only."""
    (p,) = [q for q in range(20, 40) if "Annexure – I" in text(REP, q) and "Different Activities" in text(REP, q)]
    toks = []
    for q in (p, p + 1):
        for ln in lines(REP, q):
            for tok in ln.split():
                if re.fullmatch(r"M\d{1,2}|T\d|S\d{1,2}|[METS]|M\+E\+T\+S", tok) or re.search(r"[\d()]", tok):
                    continue
                if tok.lower().strip(",;") in {"special", "code", "codes", "including", "excluding", "but", "–", "-"}:
                    continue
                toks.append(tok)
    return re.sub(r"[^a-z]", "", " ".join(toks).lower())


def test_asuse_api_activity_map_matches_annexure():
    """ASUSE_API_CODE (typed by the verifier) against Annexure I of the pinned report:
    - the map covers exactly the 50 API names, with 50 distinct codes (25 M, E, 5 T, 15 S, 3 sector totals, all);
    - every name appears in the annexure text (letters only), directly after the preceding code's name, so the
      code order is the annexure's order;
    - the three sector aggregates are the printed 'Manufacturing activities', 'Trading activities' and 'Other
      services'. Two names differ from the annexure only in punctuation: 'semi- trailers', and ', manufacture'
      where the annexure has '; manufacture'.
    The unit's own mapping is checked indirectly through the census (industry is part of the key)."""
    names = {r["activity_category"] for _, r in api_records("asuse_i36_allindia")}
    assert names == set(ASUSE_API_CODE) and len(set(ASUSE_API_CODE.values())) == 50
    ann = _annexure_text()
    pos = []
    for name, code in ASUSE_API_CODE.items():
        if code == "M+E+T+S":
            continue  # printed as 'All' in the last row
        i = ann.find(re.sub(r"[^a-z]", "", name.lower()))
        assert i >= 0, (code, name)
        pos.append((i, code))
    order = [c for _, c in sorted(pos)]
    want = [f"M{i}" for i in range(1, 26)] + ["M", "E"] + [f"T{i}" for i in range(1, 6)] + ["T"] + [f"S{i}" for i in range(1, 16)] + ["S"]
    assert order == want, order


def test_api_rows_semantics_and_provenance():
    """Row flags and provenance of the 5,244 API rows.
    - Units: INR, and percent only for the two per-1000 AIDIS items.
    - stock_flow: stocks are assets and loans; flows are earnings, net addition, rent and interest; shares are n/a.
    - Geography IN, status official, source mospi_esankhyiki_api.
    - Each row's provenance raw_path is the pinned page that actually holds its record, and its sha256 is the
      pin's.
    - Vintages: AIDIS 2021-09-10, printed on press note p.2; PLFS ay2023-24 2024-09-23, printed on AR p.2. PLFS
      ay2022-23 and ASUSE 2025 carry the retrieval date, and their release text must say so.
    - The indicator-6 notes state the preceding-month lag."""
    prov = {r["prov_id"]: r for r in pl.read_parquet(PROV).iter_rows(named=True)}
    pins = yaml.safe_load(PINS.read_text(encoding="utf-8"))["pins"]
    sha = {k.split("/", 1)[1]: v["sha256"] for k, v in pins.items()}
    assert "10 September, 2021" in text(AIDIS, 2)
    assert re.search(r"23(?:rd)?\s+September,?\s+2024", text(PLFS, 2)), "AR 2023-24 release date"
    pages = {"aidis_2019_quintile": parse_aidis_api()[1], "plfs_earnings_api": parse_plfs_api()[1],
             "asuse_2025_assets_loans": parse_asuse_api()[1]}
    stock = {"ava_per_hh", "aod_per_hh", "fixed_assets_per_hh", "financial_assets_per_hh", "valuables_per_hh", "cash_loan_per_hh",
             "land_value_per_estt", "fixed_assets_value_per_estt", "outstanding_loan_per_estt"}
    na = {"hh_distribution", "incidence_of_indebtedness"}
    n = 0
    for ds in API_DATASETS:
        df = load(ds)
        assert (df["source_id"] == API_SRC).all() and (df["geography"] == "IN").all() and (df["status"] == "official").all(), ds
        for r in df.iter_rows(named=True):
            n += 1
            it = r["item_code"]
            assert r["stock_flow"] == ("n/a" if it in na else "stock" if it in stock else "flow"), (ds, r["series_id"])
            assert (r["unit"], r["price_basis"]) == (("percent", "n/a") if it in na else ("INR", "current")), (ds, r["series_id"])
            pr = prov[r["prov_id"]]
            page = pages[ds][row_key(r)]
            assert pr["raw_path"].endswith("/" + page) and pr["raw_sha256"] == sha[page], (ds, r["series_id"], pr["raw_path"], page)
            assert pr["locator"].startswith(page) and pr["table_id"] == r["table_id"] and pr["vintage"] == r["vintage"]
            if ds == "aidis_2019_quintile":
                assert r["vintage"] == "2021-09-10"
                assert "NOT the SAM" in pr["notes"]
                if it in na:
                    assert pr["unit_as_published"].startswith("per 1000") and "x 0.1" in pr["conversion"]
            elif ds == "plfs_earnings_api":
                ay2324 = "ay2023_24" in page
                assert r["vintage"] == ("2024-09-23" if ay2324 else "2026-09-29"), (r["series_id"], r["period"])
                if not ay2324:
                    assert "vintage = date served" in pr["release"]
                if r["table_id"].endswith("indicator 6"):
                    assert "calendar month before the interview" in pr["notes"]
            else:
                assert r["vintage"] == "2026-09-29" and "vintage = date served" in pr["release"]
    assert n == 528 + 216 + 4500


def test_api_coverage_entries():
    """The coverage entries on the API datasets name series that exist for the declared period, all `partial`.
    C4a and F3a say PROXY ONLY. The ASUSE 2025 dataset declares no ref. F3b and R10 stay undeclared."""
    cov = yaml.safe_load((ROOT / "pipeline" / "ingest" / f"{UNIT}_coverage.yaml").read_text(encoding="utf-8"))["entries"]
    refs = {e["ref"] for e in cov}
    assert not refs & {"F3b", "R10", "T3a", "R9b"}, refs
    seen = collections.defaultdict(set)
    for e in cov:
        ds = e["dataset"].removeprefix(f"{UNIT}_")
        if ds not in API_DATASETS:
            continue
        assert ds != "asuse_2025_assets_loans"
        assert e["extent"] == "partial", e
        df = load(ds).filter(pl.col("period") == str(e["period"]))
        assert set(e["series_ids"]) <= set(df["series_id"]), (e["ref"], set(e["series_ids"]) - set(df["series_id"]))
        if e["ref"] in ("C4a", "F3a"):
            assert e["note"].startswith("PROXY ONLY"), e["ref"]
        seen[ds].add(e["ref"])
    assert seen == {"aidis_2019_quintile": {"S5", "R8a", "C4b", "C4a", "F3a"}, "plfs_earnings_api": {"V1a", "F1a", "F2"}}, dict(seen)


def test_seeded_sample_new_rows():
    """A seeded sample of at least 10% (min 30) of the 5,244 API rows, compared with the verifier's JSON
    re-parse. This is in addition to the full census, and a few rows are printed for the notes."""
    rng = random.Random(SEED)
    rows = [(ds, r) for ds in API_DATASETS for r in load(ds).iter_rows(named=True)]
    k = max(30, -(-len(rows) // 10))
    sample = rng.sample(rows, k)
    for ds, r in sample:
        assert close(r["value"], parsed(ds)[0][row_key(r)]), (ds, r["series_id"], r["period"])
    for ds, r in sample[:12]:
        print(ds, r["series_id"], r["period"], r["value"], parsed(ds)[0][row_key(r)])
    assert k == 525
