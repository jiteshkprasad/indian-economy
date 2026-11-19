"""Independent verification of the hces_consumption unit (Phase 1, verifier first pass, 2026-09-29).

This file does NOT import the unit's code. It re-reads the pinned raw files directly (openpyxl for the
Excel tables, pypdf for the PDF reports, while the unit uses pdfplumber) with its own State map,
fractile map, column map and label handling, and compares against data/clean/hces_consumption/.

Method:
- Excel tables (A2, A6, A10F, A10S, A10SW, CPI Annexure 5.3a-d): a full census. Every clean row is
  matched to its raw cell by label, not position. Completeness is also checked the other way: every
  published value / household cell has a clean row. A random sample (seed 20260929) is printed for the
  notes.
- PDF tables (Report 592 T3.17-3.19, Report 596 T2.21/2.24, Report 595 St. 2.3): a full census against
  a pypdf re-parse, plus literal anchors typed by hand from the page text (HAND_ANCHORS).
- Semantics: a quantity unit must agree with the item label in both HCES rounds.
- Second pass (2026-09-29): regression tests for the verify-1 fix: one quantity unit per code across rounds,
  unit / qty_published_unit / provenance agreement, cross-round implied unit values, the 384 fixed rows
  against raw, and the V3/V5 dim_other tags.
- Close-out pass (2026-09-29): HCES rows now carry the survey window (period_type 'sy'). The verifier derives
  each window itself: the HCES Aug-Jul windows are parsed from the Report 592 page text (p.3 cover and p.20),
  the NSS round of each Table 3.18 column is read from the printed column heading, and the July-June months of
  those rounds (not printed in the report) come from the IHSN catalogue, checked by the verifier. Selections
  use those windows; nothing was loosened. New tests: a period census of every row, provenance notes against
  row windows, the 716 derived CPI rows, and a seeded 10% re-parse of every changed Excel row with a second
  xlsx reader (python-calamine; the unit and the census use openpyxl).
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from collections import defaultdict
from functools import cache
from pathlib import Path

import openpyxl
import polars as pl
import pypdf
import pytest
import yaml
from python_calamine import CalamineWorkbook

pytestmark = pytest.mark.quality

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean" / "hces_consumption"
PINS = ROOT / "data" / "raw_pins" / "hces_consumption.yaml"
SEED = 20260929

# ------------------------------------------------------------------------------------------------
# independent helpers
# ------------------------------------------------------------------------------------------------

MY_STATES = {  # verifier's own map, keyed by a normalised publisher name
    "all-india": "IN",
    "all india": "IN",
    "andaman and nicobar islands": "IN-AN",
    "andaman and n island": "IN-AN",
    "a and n island": "IN-AN",
    "andhra pradesh": "IN-AP",
    "arunachal pradesh": "IN-AR",
    "assam": "IN-AS",
    "bihar": "IN-BR",
    "chandigarh": "IN-CH",
    "chhattisgarh": "IN-CG",
    "dadra and nagar haveli and daman and diu": "IN-DH",
    "delhi": "IN-DL",
    "nct of delhi": "IN-DL",
    "goa": "IN-GA",
    "gujarat": "IN-GJ",
    "haryana": "IN-HR",
    "himachal pradesh": "IN-HP",
    "jammu and kashmir": "IN-JK",
    "jharkhand": "IN-JH",
    "karnataka": "IN-KA",
    "kerala": "IN-KL",
    "ladakh": "IN-LA",
    "lakshadweep": "IN-LD",
    "madhya pradesh": "IN-MP",
    "maharashtra": "IN-MH",
    "manipur": "IN-MN",
    "meghalaya": "IN-ML",
    "mizoram": "IN-MZ",
    "nagaland": "IN-NL",
    "odisha": "IN-OD",
    "puducherry": "IN-PY",
    "punjab": "IN-PB",
    "rajasthan": "IN-RJ",
    "sikkim": "IN-SK",
    "tamil nadu": "IN-TN",
    "telangana": "IN-TS",
    "tripura": "IN-TR",
    "uttar pradesh": "IN-UP",
    "uttarakhand": "IN-UK",
    "uttrakhand": "IN-UK",
    "west bengal": "IN-WB",
}
MY_FRACTILES = [
    "0-5%",
    "5-10%",
    "10-20%",
    "20-30%",
    "30-40%",
    "40-50%",
    "50-60%",
    "60-70%",
    "70-80%",
    "80-90%",
    "90-95%",
    "95-100%",
]


def geo(name) -> str:
    s = str(name).strip().lower().replace("&", " and ").replace(".", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = s.removeprefix("the ")
    return MY_STATES[s]


def frac(label) -> str:
    s = re.sub(r"\s+", "", str(label)).lower()
    if s == "allclasses":
        return "all"
    i = MY_FRACTILES.index(s)
    a, b = MY_FRACTILES[i].rstrip("%").split("-")
    return f"p{int(a):02d}_{int(b):02d}"


def norm(s) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def num(x):
    """Raw cell -> float, or None for '##', '-', blank."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace(",", "")
    if s in ("", "##", "#", "-"):
        return None
    return float(s)


@cache
def pins() -> dict:
    return yaml.safe_load(PINS.read_text(encoding="utf-8"))["pins"]


@cache
def raw(key: str) -> Path:
    p = pins()[key]
    path = ROOT / p["path"]
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    assert h == p["sha256"], f"{key}: sha256 mismatch"
    return path


@cache
def sheet(key: str, name: str | None = None, engine: str = "openpyxl") -> list[tuple]:
    """Raw sheet rows. engine 'calamine' is a second, independent xlsx reader (empty cells -> None)."""
    if engine == "calamine":
        wb = CalamineWorkbook.from_path(str(raw(key)))
        rows = wb.get_sheet_by_name(name or wb.sheet_names[0]).to_python(skip_empty_area=False)
        return [tuple(None if c == "" else c for c in r) for r in rows]
    wb = openpyxl.load_workbook(raw(key), read_only=True, data_only=True)
    ws = wb[name] if name else wb.worksheets[0]
    rows = [tuple(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    return rows


@cache
def clean(ds: str) -> pl.DataFrame:
    return pl.read_parquet(CLEAN / f"hces_consumption_{ds}.parquet")


def close(a: float, b: float, tol: float = 5e-7) -> bool:
    return abs(a - b) <= tol + 1e-9 * abs(b)


def _report(name: str, mismatches: list, n: int) -> None:
    print(f"[spotcheck] {name}: compared {n}, mismatched {len(mismatches)}")
    assert not mismatches, f"{name}: {len(mismatches)} of {n} values differ, e.g. {mismatches[:8]}"


ROUNDS = {"2023-24": "mospi_hces_2023_24/hces2324_", "2022-23": "mospi_hces_2022_23/hces2223_"}

# ------------------------------------------------------------------------------------------------
# survey windows (close-out pass): the verifier's own derivation, not the unit's
# ------------------------------------------------------------------------------------------------

MONTHS = {
    m: i
    for i, m in enumerate(
        (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ),
        1,
    )
}
WINDOW_RX = r"([A-Z][a-z]+)\s*,?\s*(\d{4})\s*(?:–|-|to)\s*([A-Z][a-z]+)\s*,?\s*(\d{4})"


def _window(m1: str, y1: str, m2: str, y2: str) -> str:
    a, b = (int(y1), MONTHS[m1.lower()]), (int(y2), MONTHS[m2.lower()])
    assert (b[0] * 12 + b[1]) - (a[0] * 12 + a[1]) == 11, f"not a 12-month window: {m1} {y1} - {m2} {y2}"
    return f"{a[0]:04d}-{a[1]:02d}/{b[0]:04d}-{b[1]:02d}"


@cache
def hces_windows() -> dict:
    """HCES round key -> survey window, parsed from Report 592's own text.

    p.3 (cover): 'Survey on Household Consumption Expenditure: 2023-24 ... August, 2023 – July, 2024'.
    p.20: 'last survey has been conducted in during August, 2022 to July, 2023 (2022-23)'."""
    cover = page(R592, 3)
    assert "Expenditure: 2023-24" in cover
    found = {_window(*m) for m in re.findall(WINDOW_RX, cover)}
    assert len(found) == 1, found
    out = {"2023-24": found.pop()}
    m = re.search(WINDOW_RX + r"\s*\((\d{4}-\d{2})\)", page(R592, 20))
    assert m and m.group(5) == "2022-23", m
    out["2022-23"] = _window(*m.groups()[:4])
    return out


def sy(round_key: str) -> str:
    """Clean `period` of an HCES round ('2023-24' -> the survey window printed in Report 592)."""
    return hces_windows()[round_key]


# Table 3.18 columns: printed heading -> (NSS round printed under the heading, survey window).
# The report prints only the round numbers. The July-June months of the four NSS rounds were checked by the
# verifier on 2026-09-29 in the IHSN survey catalogue ('dates of data collection'): 55th round
# catalog.ihsn.org/catalog/2606 (1 Jul 1999 - 30 Jun 2000), 61st /1910 (2004-07 to 2005-06), 66th /1903
# (2009-07 to 2010-06), 68th /3281 (2011-07 to 2012-06). The two HCES columns use hces_windows().
T318_NSS = {
    "1999-00": ("55th", "1999-07/2000-06"),
    "2004-05": ("61st", "2004-07/2005-06"),
    "2009-10": ("66th", "2009-07/2010-06"),
    "2011-12": ("68th", "2011-07/2012-06"),
}


def t318_window(heading: str) -> str:
    return T318_NSS[heading][1] if heading in T318_NSS else sy(heading)


# ------------------------------------------------------------------------------------------------
# Table A2
# ------------------------------------------------------------------------------------------------

A2_MAP = {  # clean item_code -> (raw 0-based column, multiplier)
    "households": (3, 100),
    "adults_male": (4, 100),
    "adults_female": (5, 100),
    "adults_persons": (6, 100),
    "children_male": (7, 100),
    "children_female": (8, 100),
    "children_persons": (9, 100),
    "avg_mpce": (10, 1),
    "sample_households": (11, 1),
    "sample_persons": (12, 1),
}


def raw_a2(period: str, engine: str = "openpyxl") -> dict:
    rows = sheet(ROUNDS[period] + "table_a2.xlsx", engine=engine)
    assert "Estimated no. (00)" in str(rows[1][3]) and "Average MPCE" in str(rows[1][10])
    out, sector, g = {}, None, None
    for r in rows[5:]:
        if r[0] is not None and str(r[0]).strip().lower().startswith("note"):
            break
        if r[0] is not None:
            sector = str(r[0]).strip().lower()
        if r[1] is not None:
            g = geo(r[1])
        if r[2] is None or str(r[2]).lower().startswith("sample"):
            continue
        hg = f"{sector}_{frac(r[2])}"
        for code, (c, m) in A2_MAP.items():
            out[(g, hg, code)] = num(r[c]) * m
        out[(g, hg, "persons")] = (num(r[6]) + num(r[9])) * 100
    return out


def test_a2_census():
    df = clean("a2_fractile_persons")
    bad, n = [], 0
    for period in ROUNDS:
        exp = raw_a2(period)
        sub = df.filter(pl.col("period") == sy(period))
        seen = set()
        for g, hg, code, v in sub.select("geography", "household_group", "item_code", "value").iter_rows():
            n += 1
            k = (g, hg, code)
            seen.add(k)
            if k not in exp or not close(v, exp[k], 1e-6):
                bad.append((period, k, v, exp.get(k)))
        missing = set(exp) - seen
        bad += [(period, k, "missing in clean") for k in sorted(missing)[:5]]
        assert not missing, f"A2 {period}: {len(missing)} raw cells not in clean"
    _report("A2", bad, n)


# ------------------------------------------------------------------------------------------------
# Table A6
# ------------------------------------------------------------------------------------------------


def raw_a6(period: str, engine: str = "openpyxl") -> dict:
    rows = sheet(ROUNDS[period] + "table_a6.xlsx", engine=engine)
    hdr = [frac(x) for x in rows[2][3:16]]
    assert hdr[-1] == "all" and hdr[0] == "p00_05"
    out, sector, g = {}, None, None
    for r in rows[4:]:
        if r[0] is not None and str(r[0]).strip().lower().startswith("note"):
            break
        if r[0] is not None:
            sector = str(r[0]).strip().lower()
        if r[1] is not None:
            g = geo(r[1])
        if r[2] is None:
            continue
        lab = norm(r[2])
        if "no. of h" in lab:
            continue
        for fr, cell in zip(hdr, r[3:16], strict=True):
            v = num(cell)
            if v is not None:
                out[(g, f"{sector}_{fr}", lab)] = v
    return out


def test_a6_census():
    df = clean("a6_group_fractile")
    bad, n = [], 0
    for period in ROUNDS:
        exp = raw_a6(period)
        sub = df.filter(pl.col("period") == sy(period))
        seen = set()
        for g, hg, lab, v in sub.select("geography", "household_group", "item_label", "value").iter_rows():
            n += 1
            k = (g, hg, norm(lab))
            seen.add(k)
            if k not in exp or not close(v, exp[k]):
                bad.append((period, k, v, exp.get(k)))
        missing = set(exp) - seen
        assert not missing, f"A6 {period}: {len(missing)} raw cells not in clean, e.g. {sorted(missing)[:5]}"
    _report("A6", bad, n)


# ------------------------------------------------------------------------------------------------
# Item tables A10F / A10S / A10SW
# ------------------------------------------------------------------------------------------------


def raw_items(key: str, by: str, engine: str = "openpyxl") -> dict:
    rows = sheet(key, engine=engine)
    assert "Value per person per 30 days" in str(rows[1][5]) and "Estimated (00)" in str(rows[2][6])
    out = {}
    for r in rows[4:]:
        code = str(r[2]).strip() if r[2] is not None else ""
        if not re.fullmatch(r"\d{3}", code):
            continue
        sector = str(r[0]).strip().lower()
        hg, g = (f"{sector}_{frac(r[1])}", "IN") if by == "fractile" else (f"{sector}_all", geo(r[1]))
        out[(g, hg, code)] = {"label": norm(r[3]), "qty": num(r[4]), "value": num(r[5]), "hh": num(r[6])}
    return out


ITEM_TABLES = [
    ("a10f_item_fractile", "2023-24", "table_a10f.xlsx", "fractile"),
    ("a10f_item_fractile", "2022-23", "table_a10f.xlsx", "fractile"),
    ("a10s_state_item", "2023-24", "table_a10s.xlsx", "state"),
    ("a10s_state_item", "2022-23", "table_a10s.xlsx", "state"),
    ("a10sw_state_item_imputed", "2023-24", "table_a10sw.xlsx", "state"),
]


@pytest.mark.parametrize(("ds", "period", "fname", "by"), ITEM_TABLES, ids=[f"{t[0]}-{t[1]}" for t in ITEM_TABLES])
def test_item_table_census(ds, period, fname, by):
    exp = raw_items(ROUNDS[period] + fname, by)
    sub = clean(ds).filter(pl.col("period") == sy(period))
    assert sub.height, f"{ds}: no rows in {sy(period)}"
    bad, n, seen = [], 0, defaultdict(set)
    for g, hg, prod, ic, unit, v, lab in sub.select(
        "geography", "household_group", "product", "item_code", "unit", "value", "item_label"
    ).iter_rows():
        n += 1
        code = prod.split(":")[1]
        k = (g, hg, code)
        seen[ic].add(k)
        e = exp.get(k)
        if e is None:
            bad.append((k, ic, "not in raw"))
            continue
        if norm(lab) != e["label"]:
            bad.append((k, ic, "label", lab, e["label"]))
        if ic == "value_per_person_30d":
            ok = e["value"] is not None and unit == "INR" and close(v, e["value"])
            want = e["value"]
        elif ic == "households_reporting":
            ok = e["hh"] is not None and unit == "count" and close(v, e["hh"] * 100, 1e-4)
            want = e["hh"]
        elif ic == "qty_per_person_30d":
            if unit == "tonnes":
                ok = e["qty"] is not None and close(v * 1000, e["qty"], 5e-4)
            else:
                ok = e["qty"] is not None and unit == "count" and close(v, e["qty"])
            want = e["qty"]
        else:
            ok, want = False, "unknown item_code"
        if not ok:
            bad.append((k, ic, unit, v, want))
    # completeness: every published value (and, in A10F, household count) has a row
    miss_v = [k for k, e in exp.items() if e["value"] is not None and k not in seen["value_per_person_30d"]]
    assert not miss_v, f"{ds} {period}: {len(miss_v)} published values not ingested, e.g. {miss_v[:5]}"
    if by == "fractile":
        miss_h = [k for k, e in exp.items() if e["hh"] is not None and k not in seen["households_reporting"]]
        assert not miss_h, f"{ds} {period}: {len(miss_h)} household counts not ingested, e.g. {miss_h[:5]}"
    _report(f"{ds} {period}", bad, n)


QTY_OTHER_UNIT = re.compile(r"\((no\.?|nos\.?|litre|gm|metre|std\.? ?unit|box)\)", re.I)


def test_kg_quantities_agree_with_labels_in_both_rounds():
    """A quantity stored as kg -> tonnes must not be labelled '(no.)' (or another unit) in either round.

    KNOWN DEFECT (verifier first pass): HCES 2022-23 prints 223 'pineapple', 224 'coconut', 225
    'green coconut' and 228 'orange, mausami' without '(no.)', and the 2023-24 tables print '(no.)'
    for the same codes. Implied 2022-23 'kg' prices (orange Rs 8/kg, coconut Rs 20/kg) equal the
    2023-24 per-number prices, so the 2022-23 quantities are numbers but are stored as tonnes.
    """
    labels = defaultdict(dict)
    for period in ROUNDS:
        for (_, _, code), e in raw_items(ROUNDS[period] + "table_a10f.xlsx", "fractile").items():
            labels[code][period] = e["label"]
    bad = set()
    for ds in ("a10f_item_fractile", "a10s_state_item", "a10sw_state_item_imputed"):
        kg = clean(ds).filter(pl.col("unit") == "tonnes").select("period", "product").unique()
        for period, prod in kg.iter_rows():
            code = prod.split(":")[1]
            for p2, lab in labels[code].items():
                if QTY_OTHER_UNIT.search(lab):
                    bad.add((ds, period, code, f"{p2} label {lab!r}"))
    assert not bad, f"{len(bad)} kg-stored quantity series whose item is counted in other units: {sorted(bad)}"


# ------------------------------------------------------------------------------------------------
# CPI 2024 weights (Annexure 5.3)
# ------------------------------------------------------------------------------------------------

CPI_KEY = "mospi_cpi_2024base/cpi2024_annex_5_3_weights.xlsx"


def test_cpi_census():
    df = clean("cpi2024_weights")
    bad, n = [], 0
    # 5.3d State x sector x item
    exp, agg = {}, defaultdict(float)
    for r in sheet(CPI_KEY, "5.3d")[4:]:
        if r[0] is None:
            continue
        sec = {"1": "rural", "2": "urban"}[str(r[2]).strip()]
        code = str(r[4]).strip()
        exp[(geo(r[1]), sec, code, "weight_share_all_india")] = float(r[13])
        exp[(geo(r[1]), sec, code, "weight_share_within_state")] = float(r[14])
        agg[("IN", sec, code, "weight_share_all_india")] += float(r[13])
    d = df.filter(pl.col("table_id") == "Annexure 5.3d")
    seen = set()
    for g, hg, prod, ic, st, v in d.select(
        "geography", "household_group", "product", "item_code", "status", "value"
    ).iter_rows():
        n += 1
        k = (g, hg.split("_")[0], prod.split(":")[1], ic)
        seen.add(k)
        want = agg.get(k) if g == "IN" else exp.get(k)
        if want is None or not close(v, want) or (st == "derived") != (g == "IN"):
            bad.append((k, st, v, want))
    assert set(exp) | set(agg) == seen, "5.3d rows missing or extra"
    # 5.3a divisions, 5.3b groups, 5.3c States
    cols = {"rural": 1, "urban": 2, "all": 3}
    a = {str(r[0]).strip(): r for r in sheet(CPI_KEY, "5.3a")[6:] if r[0] is not None}
    for lab, hg, v in (
        df.filter(pl.col("table_id") == "Annexure 5.3a").select("item_label", "household_group", "value").iter_rows()
    ):
        n += 1
        want = float(a[lab][cols[hg.split("_")[0]]])
        if not close(v, want):
            bad.append(("5.3a", lab, hg, v, want))
    b = {str(r[1]).strip(): r for r in sheet(CPI_KEY, "5.3b")[5:] if r[1] is not None}
    for lab, hg, v in (
        df.filter(pl.col("table_id") == "Annexure 5.3b").select("item_label", "household_group", "value").iter_rows()
    ):
        n += 1
        want = float(b[lab][cols[hg.split("_")[0]] + 1])
        if not close(v, want):
            bad.append(("5.3b", lab, hg, v, want))
    c = {geo(r[1]): r for r in sheet(CPI_KEY, "5.3c")[5:] if r[1] is not None}
    for g, hg, v in (
        df.filter(pl.col("table_id") == "Annexure 5.3c").select("geography", "household_group", "value").iter_rows()
    ):
        n += 1
        want = float(c[g][cols[hg.split("_")[0]] + 1])
        if not close(v, want):
            bad.append(("5.3c", g, hg, v, want))
    assert df.filter(pl.col("table_id") == "Annexure 5.3a").height == 39
    assert df.filter(pl.col("table_id") == "Annexure 5.3b").height == 3 * len(b)
    _report("CPI 5.3a-d", bad, n)


# ------------------------------------------------------------------------------------------------
# PDF tables: independent pypdf parse + hand-typed anchors
# ------------------------------------------------------------------------------------------------

R592 = "mospi_hces_2023_24/hces2324_report592.pdf"
H596 = "nss_health_2025_report/nss596_health_report.pdf"
E595 = "nss_cms_education_2025_report/cms_education_2025_report.pdf"
NUMS = r"((?:-?[\d,]+(?:\.\d+)?\s+)*-?[\d,]+(?:\.\d+)?)"


@cache
def page(key: str, p: int) -> str:
    return pypdf.PdfReader(raw(key)).pages[p - 1].extract_text()


def row_nums(text: str, label: str, n: int) -> list[float]:
    hits = [m for m in re.finditer(rf"(?m)^\s*{label}\s+{NUMS}\s*$", text) if len(m.group(1).split()) == n]
    assert len(hits) == 1, f"{label!r}: {len(hits)} lines with {n} numbers"
    return [float(t.replace(",", "")) for t in hits[0].group(1).split()]


def pdf_expected() -> dict:
    """series_id -> (period, value) from an independent pypdf parse."""
    exp = {}
    t = page(R592, 69)
    assert "Table 3.17: Average MPCE and urban-rural differences in MPCE in 2023-24" in t
    for st in [
        "Andhra Pradesh",
        "Assam",
        "Bihar",
        "Chhattisgarh",
        "Gujarat",
        "Haryana",
        "Jharkhand",
        "Karnataka",
        "Kerala",
        "Madhya Pradesh",
        "Maharashtra",
        "Odisha",
        "Punjab",
        "Rajasthan",
        "Tamil Nadu",
        "Telangana",
        "Uttar Pradesh",
        "West Bengal",
        "All-India",
    ]:
        v = row_nums(t, re.escape(st), 6)
        g = geo(st).lower()
        exp[f"t3_17.mpce.{g}.rural.current"] = (sy("2023-24"), v[0])
        exp[f"t3_17.mpce.{g}.urban.current"] = (sy("2023-24"), v[1])
        exp[f"t3_17.mpce_with_imputation.{g}.rural.current"] = (sy("2023-24"), v[3])
        exp[f"t3_17.mpce_with_imputation.{g}.urban.current"] = (sy("2023-24"), v[4])
    t = page(R592, 70)
    nominal, real = t.split("At real price (2011-12 price)")
    nominal = nominal.split("At nominal price")[1]
    periods = ["1999-00", "2004-05", "2009-10", "2011-12", "2022-23", "2022-23i", "2023-24", "2023-24i"]
    for basis, block in (("current", nominal), ("constant_2011_12", real)):
        for sec in ("Rural", "Urban"):
            for p, v in zip(periods, row_nums(block, sec, 8), strict=True):
                code = "mpce_with_imputation" if p.endswith("i") else "mpce"
                # key by the printed column heading; the expected period is that column's survey window
                exp[f"t3_18.{code}.{sec.lower()}.{basis}@{p.rstrip('i')}"] = (t318_window(p.rstrip("i")), v)
    t = page(R592, 71)
    t = t.replace("beverages, refreshments,  \nprocessed food#", "beverages_processed")
    t = t.replace("consumer services excl. \nconveyance&", "consumer_services")
    groups = [
        ("cereals", r"cereals & cereal substitutes"),
        ("pulses", r"pulses & pulse products\*"),
        ("sugar_salt", r"sugar & salt"),
        ("milk", r"milk & milk products"),
        ("vegetables", r"vegetables"),
        ("fruits", r"fruits"),
        ("egg_fish_meat", r"egg, fish & meat"),
        ("edible_oil", r"edible oil"),
        ("spices", r"spices"),
        ("beverages_processed", "beverages_processed"),
        ("food_total", r"food total"),
        ("pan_tobacco", r"pan, tobacco & intoxicants"),
        ("fuel_light", r"fuel and light"),
        ("education", r"education"),
        ("medical", r"medical"),
        ("conveyance", r"conveyance"),
        ("consumer_services", "consumer_services"),
        ("misc_goods_entertainment", r"misc\. goods, entertainment"),
        ("rent", r"rent"),
        ("taxes_cesses", r"taxes and cesses"),
        ("clothing_bedding_footwear", r"clothing, bedding & footwear\$"),
        ("durables", r"durable goods"),
        ("nonfood_total", r"non-food total"),
        ("all_items", r"all items"),
    ]
    metrics = [
        "mpce.rural.current",
        "mpce.urban.current",
        "mpce_with_imputation.rural.current",
        "mpce_with_imputation.urban.current",
        "share.rural",
        "share.urban",
        "share_with_imputation.rural",
        "share_with_imputation.urban",
    ]
    for code, rx in groups:
        for m, v in zip(metrics, row_nums(t, rx, 8), strict=True):
            exp[f"t3_19.{code}.{m}"] = (sy("2023-24"), v)
    t = page(H596, 55)
    assert "Table 2.21" in t
    for lab, q in (
        ("1st quintile", "hh_q1"),
        ("2nd quintile", "hh_q2"),
        ("3rd quintile", "hh_q3"),
        ("4th quintile", "hh_q4"),
        ("5th quintile", "hh_q5"),
        ("All", "all"),
    ):
        v = row_nums(t, lab, 4)
        for (m, sec), x in zip(
            (("avg", "rural"), ("avg", "urban"), ("median", "rural"), ("median", "urban")), v, strict=True
        ):
            exp[f"t2_21.oop_per_hosp_case_{m}.{sec}_{q}"] = ("2025", x)
    t = page(H596, 58)
    t = t.split("Table 2.25")[0]
    for lab, hg in (("Rural", "rural_all"), ("Urban", "urban_all"), (r"Rural\+ Urban", "all")):
        a, med = row_nums(t, lab, 2)
        exp[f"t2_24.oop_per_opd_spell_avg.{hg}"] = ("2025", a)
        exp[f"t2_24.oop_per_opd_spell_median.{hg}"] = ("2025", med)
    text = page(E595, 26) + "\n" + page(E595, 27).split("In Statement 2.4")[0]
    text = "\n".join(text.split("Statement 2.3: Average expenditure")[1:])
    blocks = re.split(r"(?m)^(rural \+ urban|rural|urban)\s*$", text)
    cur, by = None, defaultdict(str)
    for piece in blocks:
        if piece in ("rural", "urban", "rural + urban"):
            cur = piece
        elif cur:
            by[cur] += piece
    for sec, hg in (("rural", "rural_all"), ("urban", "urban_all"), ("rural + urban", "all")):
        for lab, lvl in (
            ("Pre-primary", "pre_primary"),
            ("Primary", "primary"),
            ("Middle", "middle"),
            ("Secondary", "secondary"),
            ("Higher secondary", "higher_secondary"),
            ("All", "all"),
        ):
            for sex, x in zip(("male", "female", "person"), row_nums(by[sec], lab, 3), strict=True):
                exp[f"s2_3.exp_per_student.{lvl}.{sex}.{hg}"] = ("2025-Q2", x)
    return exp


def t318_heading() -> dict:
    """survey window -> Table 3.18 printed column heading (inverse of t318_window)."""
    heads = [*T318_NSS, "2022-23", "2023-24"]
    out = {t318_window(h): h for h in heads}
    assert len(out) == len(heads)
    return out


def _clean_pdf_rows():
    out = {}
    for ds in ("report592_mpce", "health596", "cms_education_2025"):
        for sid, period, v in clean(ds).select("series_id", "period", "value").iter_rows():
            # T3.18: map the row's window back to the printed heading (an unknown window stays as is, so the
            # key comparison in test_pdf_tables_census reports it)
            key = f"{sid}@{t318_heading().get(period, period)}" if sid.startswith("t3_18") else sid
            assert key not in out
            out[key] = (period, v)
    return out


def test_pdf_tables_census():
    exp = pdf_expected()
    got = _clean_pdf_rows()
    assert set(exp) == set(got), (sorted(set(exp) - set(got))[:5], sorted(set(got) - set(exp))[:5])
    bad = [(k, got[k], exp[k]) for k in exp if got[k][0] != exp[k][0] or not close(got[k][1], exp[k][1])]
    _report("PDF tables", bad, len(exp))


# Literal values typed by the verifier from the PDF page text (pdfplumber and pypdf text layers
# read side by side). (series_id[@period], value, where printed)
HAND_ANCHORS = [
    ("t3_17.mpce.in-ap.rural.current", 5327, "R592 p.51 T3.17 Andhra Pradesh col 2"),
    ("t3_17.mpce_with_imputation.in-ts.urban.current", 9131, "R592 p.51 T3.17 Telangana col 6"),
    ("t3_17.mpce.in-kl.urban.current", 7783, "R592 p.51 T3.17 Kerala col 3"),
    ("t3_17.mpce_with_imputation.in-wb.rural.current", 3815, "R592 p.51 T3.17 West Bengal col 5"),
    ("t3_17.mpce.in.urban.current", 6996, "R592 p.51 T3.17 All-India col 3"),
    ("t3_17.mpce_with_imputation.in-cg.rural.current", 2927, "R592 p.51 T3.17 Chhattisgarh col 5"),
    ("t3_18.mpce.rural.current@1999-00", 486, "R592 p.52 T3.18 nominal Rural col 2"),
    ("t3_18.mpce.urban.current@2011-12", 2630, "R592 p.52 T3.18 nominal Urban col 5"),
    ("t3_18.mpce_with_imputation.rural.current@2022-23", 3860, "R592 p.52 T3.18 nominal Rural col 7"),
    ("t3_18.mpce.rural.constant_2011_12@2004-05", 1054, "R592 p.52 T3.18 real Rural col 3"),
    ("t3_18.mpce.urban.constant_2011_12@2023-24", 3632, "R592 p.52 T3.18 real Urban col 8"),
    ("t3_18.mpce_with_imputation.urban.constant_2011_12@2023-24", 3674, "R592 p.52 T3.18 real Urban col 9"),
    ("t3_19.cereals.mpce_with_imputation.rural.current", 323, "R592 p.53 T3.19 cereals col 4"),
    ("t3_19.food_total.share.urban", 39.68, "R592 p.53 T3.19 food total col 7"),
    ("t3_19.rent.mpce.urban.current", 460, "R592 p.53 T3.19 rent col 3"),
    ("t3_19.beverages_processed.share_with_imputation.urban", 10.96, "R592 p.53 T3.19 beverages col 9"),
    ("t3_19.consumer_services.mpce.rural.current", 217, "R592 p.53 T3.19 consumer services col 2"),
    ("t3_19.nonfood_total.mpce_with_imputation.urban.current", 4225, "R592 p.53 T3.19 non-food total col 5"),
    ("t3_19.durables.share.rural", 6.48, "R592 p.53 T3.19 durable goods col 6"),
    ("t2_21.oop_per_hosp_case_avg.rural_hh_q1", 25704, "R596 p.29 T2.21 1st quintile col 2"),
    ("t2_21.oop_per_hosp_case_avg.urban_hh_q5", 53531, "R596 p.29 T2.21 5th quintile col 3"),
    ("t2_21.oop_per_hosp_case_median.urban_hh_q4", 15000, "R596 p.29 T2.21 4th quintile col 5"),
    ("t2_21.oop_per_hosp_case_median.rural_all", 10500, "R596 p.29 T2.21 All col 4"),
    ("t2_24.oop_per_opd_spell_avg.all", 861, "R596 p.32 T2.24 Rural+Urban average"),
    ("t2_24.oop_per_opd_spell_median.rural_all", 395, "R596 p.32 T2.24 Rural median"),
    ("s2_3.exp_per_student.pre_primary.male.rural_all", 6311, "R595 p.13 St2.3 rural pre-primary male"),
    ("s2_3.exp_per_student.higher_secondary.person.urban_all", 29286, "R595 p.13 St2.3 urban HS person"),
    ("s2_3.exp_per_student.middle.female.all", 11682, "R595 p.13 St2.3 rural+urban middle female"),
    ("s2_3.exp_per_student.secondary.male.all", 15567, "R595 p.14 St2.3 rural+urban secondary male"),
    ("s2_3.exp_per_student.all.person.all", 12616, "R595 p.14 St2.3 rural+urban all person"),
]


def test_pdf_hand_anchors():
    got = _clean_pdf_rows()
    bad = [(k, got.get(k), v, w) for k, v, w in HAND_ANCHORS if k not in got or not close(got[k][1], v)]
    _report("PDF hand anchors", bad, len(HAND_ANCHORS))


def test_pdf_price_basis_and_periods():
    r = clean("report592_mpce")
    t18 = r.filter(pl.col("table_id") == "Table 3.18")
    real = t18.filter(pl.col("price_basis") == "constant_2011_12")
    assert real.height == 16 and set(real["base_year"].unique()) == {"2011-12"}
    assert set(t18.filter(pl.col("price_basis") == "current")["base_year"].unique().to_list()) == {None}
    assert set(r["period_type"]) == {"sy"}
    assert set(r.filter(pl.col("table_id") != "Table 3.18")["period"]) == {sy("2023-24")}
    assert set(t18["period"]) == set(t318_heading())
    h = clean("health596")
    assert set(h["period"]) == {"2025"} and set(h["period_type"]) == {"cy"}
    e = clean("cms_education_2025")
    assert set(e["period"]) == {"2025-Q2"} and set(e["period_type"]) == {"cq"}


# ------------------------------------------------------------------------------------------------
# sample printed for the verification notes
# ------------------------------------------------------------------------------------------------


def test_print_random_sample():
    rng = random.Random(SEED)
    df = clean("a10f_item_fractile").filter(pl.col("period") == sy("2023-24"))
    exp = raw_items(ROUNDS["2023-24"] + "table_a10f.xlsx", "fractile")
    rows = df.select("household_group", "product", "item_code", "unit", "value").rows()
    for hg, prod, ic, unit, v in rng.sample(rows, 10):
        e = exp[("IN", hg, prod.split(":")[1])]
        print(f"[sample] A10F 2023-24 {hg} {prod} {ic} clean={v} {unit} raw={e}")


# ------------------------------------------------------------------------------------------------
# second pass (2026-09-29): regression tests for the verify-1 fix and the V3/V5 wording fixes
# ------------------------------------------------------------------------------------------------

COUNTED_FRUIT_2223 = ("223", "224", "225", "228")  # printed without '(no.)' in 2022-23 only


def _qty_units(ds: str) -> dict:
    """(code) -> {period: unit} for every quantity series in a clean item dataset."""
    out = defaultdict(dict)
    q = clean(ds).filter(pl.col("item_code") == "qty_per_person_30d").select("period", "product", "unit").unique()
    for period, prod, unit in q.iter_rows():
        code = prod.split(":")[1]
        out[code].setdefault(period, set()).add(unit)
    return out


@pytest.mark.parametrize("ds", ["a10f_item_fractile", "a10s_state_item"])
def test_quantity_unit_is_the_same_in_both_rounds(ds):
    """A code whose quantity is ingested in both rounds must carry one unit in both (join-ability)."""
    bad = []
    for code, by in _qty_units(ds).items():
        units = set().union(*by.values())
        if len(units) != 1:
            bad.append((code, {p: sorted(u) for p, u in by.items()}))
    assert not bad, f"{ds}: quantity unit differs across rounds / within a round: {bad}"


@pytest.mark.parametrize("ds", ["a10f_item_fractile", "a10s_state_item", "a10sw_state_item_imputed"])
def test_qty_published_unit_tag_agrees_with_unit_and_provenance(ds):
    df = clean(ds).filter(pl.col("item_code") == "qty_per_person_30d")
    prov = pl.read_parquet(CLEAN / "_provenance.parquet").select("prov_id", "unit_as_published", "conversion")
    j = df.join(prov, on="prov_id", how="left")
    bad = []
    for unit, dim, uap, conv in j.select("unit", "dim_other", "unit_as_published", "conversion").unique().iter_rows():
        tag = re.search(r"qty_published_unit=(\w+)", dim or "")
        tag = tag.group(1) if tag else None
        ok = (unit, tag) in (("tonnes", "kg"), ("count", "number"))
        ok &= (unit == "tonnes") == (str(uap).startswith("kg")) and (unit == "count") == str(uap).startswith("number")
        ok &= (unit == "tonnes") == ("0.001" in str(conv))
        if not ok:
            bad.append((unit, tag, uap, conv))
    assert not bad, f"{ds}: unit / qty_published_unit / provenance disagree: {bad}"


def _implied_prices(ds: str, period: str) -> dict:
    """(code, household_group) -> Rs per published unit, All-India, from the CLEAN rows only."""
    df = clean(ds).filter((pl.col("period") == sy(period)) & (pl.col("geography") == "IN"))
    val, qty = {}, {}
    for prod, hg, ic, unit, v in df.select("product", "household_group", "item_code", "unit", "value").iter_rows():
        k = (prod.split(":")[1], hg)
        if ic == "value_per_person_30d":
            val[k] = v
        elif ic == "qty_per_person_30d":
            qty[k] = v * 1000 if unit == "tonnes" else v
    return {k: val[k] / q for k, q in qty.items() if q and k in val and val[k]}


def test_implied_unit_values_join_across_rounds():
    """Guards against numeric scale slips: 2023-24 vs 2022-23 implied Rs per published unit (A10S
    All-India, rural_all/urban_all) must stay within x0.2..x5 for every item whose All-India quantity is
    at least 0.05 units per person (tiny PDS lines are rounding noise). A forgotten or doubled kg -> tonnes
    conversion shows up as roughly x1000 (mutation-tested). The verify-1 defect itself (the right number
    under the wrong unit tag) is NOT visible here; test_quantity_unit_is_the_same_in_both_rounds catches it
    (also mutation-tested)."""
    a, b = _implied_prices("a10s_state_item", "2023-24"), _implied_prices("a10s_state_item", "2022-23")
    qty = {}
    for prod, hg, unit, v in (
        clean("a10s_state_item")
        .filter((pl.col("geography") == "IN") & (pl.col("item_code") == "qty_per_person_30d"))
        .select("product", "household_group", "unit", "value")
        .iter_rows()
    ):
        k = (prod.split(":")[1], hg)
        qty[k] = min(qty.get(k, 1e9), v * 1000 if unit == "tonnes" else v)
    bad, n = [], 0
    for k in sorted(set(a) & set(b)):
        if qty[k] < 0.05:
            continue
        n += 1
        r = a[k] / b[k]
        if not 0.2 <= r <= 5:
            bad.append((k, round(b[k], 2), round(a[k], 2), round(r, 2)))
    assert n >= 100, n  # 150 series on 2026-09-29
    assert not bad, f"implied unit values do not join across rounds: {bad}"
    # the four fixed codes, explicitly: per-piece prices of the same order in both rounds
    for code in COUNTED_FRUIT_2223:
        for hg in ("rural_all", "urban_all"):
            r = a[(code, hg)] / b[(code, hg)]
            assert 0.7 <= r <= 1.5, (code, hg, b[(code, hg)], a[(code, hg)])


def test_counted_fruit_2223_values_as_printed():
    """The 384 fixed rows carry the printed number unchanged (not /1000), matched to raw by label."""
    n = 0
    for ds, fname, by, want in (
        ("a10f_item_fractile", "table_a10f.xlsx", "fractile", 96),
        ("a10s_state_item", "table_a10s.xlsx", "state", 288),
    ):
        exp = raw_items(ROUNDS["2022-23"] + fname, by)
        sub = clean(ds).filter(
            (pl.col("period") == sy("2022-23"))
            & (pl.col("item_code") == "qty_per_person_30d")
            & pl.col("product").is_in([f"hces:{c}" for c in COUNTED_FRUIT_2223])
        )
        assert sub.height == want, (ds, sub.height)
        assert set(sub["unit"]) == {"count"}
        for g, hg, prod, v in sub.select("geography", "household_group", "product", "value").iter_rows():
            e = exp[(g, hg, prod.split(":")[1])]
            assert "(no" not in e["label"]  # the 2022-23 label really lacks the unit
            assert close(v, e["qty"]), (g, hg, prod, v, e)
            n += 1
    # hand anchor from the raw sheet: HCES 2022-23 A10F rural 0-5% coconut (224) quantity
    a10f = raw_items(ROUNDS["2022-23"] + "table_a10f.xlsx", "fractile")
    assert a10f[("IN", "rural_p00_05", "224")]["qty"] == pytest.approx(0.068)
    print(f"[spotcheck] counted-fruit 2022-23 rows: compared {n}, mismatched 0")


def test_wording_fixes_v3_v5():
    e = clean("cms_education_2025")
    assert all(d.startswith("ref_period=current_academic_year;") for d in e["dim_other"])
    w = clean("cpi2024_weights").filter((pl.col("table_id") == "Annexure 5.3d") & (pl.col("status") == "official"))
    tags = dict(w.select("item_code", "dim_other").unique().iter_rows())
    assert tags == {
        "weight_share_within_state": "share_of=state_combined_rural_urban_basket",
        "weight_share_all_india": "share_of=all_india_combined_basket",
    }
    # the semantics the tag claims: within-State shares add to 100 over BOTH sectors together
    s = w.filter(pl.col("item_code") == "weight_share_within_state").group_by("geography").agg(pl.col("value").sum())
    assert s["value"].min() > 99.999 and s["value"].max() < 100.001


# ------------------------------------------------------------------------------------------------
# close-out pass (2026-09-29): survey-window periods, shared State codes, verify-6 tag
# ------------------------------------------------------------------------------------------------

DATASETS = (
    "a2_fractile_persons",
    "a6_group_fractile",
    "a10f_item_fractile",
    "a10s_state_item",
    "a10sw_state_item_imputed",
    "report592_mpce",
    "cpi2024_weights",
    "health596",
    "cms_education_2025",
)
HCES_EXCEL = DATASETS[:5]
TAG_ROUND = {"hces2324": "2023-24", "hces2223": "2022-23"}
SOURCE_ROUND = {"mospi_hces_2023_24": "2023-24", "mospi_hces_2022_23": "2022-23"}
CALENDAR_PERIODS = {
    "cpi2024_weights": ("2024", "cy"),
    "health596": ("2025", "cy"),
    "cms_education_2025": ("2025-Q2", "cq"),
}


def test_survey_windows_are_printed_in_the_documents():
    """The windows the verifier uses, re-derived from the raw text (nothing taken from the unit's output)."""
    assert hces_windows() == {"2023-24": "2023-08/2024-07", "2022-23": "2022-08/2023-07"}
    # Report 592 p.9 repeats both windows
    assert {_window(*m) for m in re.findall(WINDOW_RX, page(R592, 9))} == set(hces_windows().values())
    # each Table 3.18 NSS column heading is printed with the round that the IHSN windows belong to
    t = re.sub(r"\s+", " ", page(R592, 70).split("At nominal price")[0])
    for heading, (rnd, _) in T318_NSS.items():
        y0, y1 = heading.split("-")
        assert re.search(rf"{y0}-\W?{y1} NSS ?\( ?{rnd} round\)", t), (heading, rnd)
    # the kept calendar periods: Report 596 is a Jan-Dec 2025 survey, Report 595 an Apr-Jun 2025 survey
    assert "January – December, 2025" in page(H596, 3)
    assert "April - June, 2025" in page(E595, 2)


def test_period_census_every_row():
    """Every one of the 328,697 rows carries the period its source and table imply (a census, not a sample)."""
    n, bad = 0, []
    for ds in DATASETS:
        cols = clean(ds).select("series_id", "source_id", "table_id", "period", "period_type")
        for sid, src, tab, per, pt in cols.iter_rows():
            n += 1
            ok = True
            if ds in HCES_EXCEL:
                tag = sid.split(".")[1]
                want = (sy(TAG_ROUND[tag]), "sy")
                ok = SOURCE_ROUND[src] == TAG_ROUND[tag]
            elif ds == "report592_mpce":
                t318 = tab == "Table 3.18" and per in t318_heading()
                want = (per if t318 else sy("2023-24"), "sy")
                ok = src == "mospi_hces_2023_24"
            else:
                want = CALENDAR_PERIODS[ds]
            if not ok or (per, pt) != want:
                bad.append((ds, sid, src, per, pt, want))
    total = sum(v["rows"] for v in json.loads((CLEAN / "_datasets.json").read_text(encoding="utf-8")).values())
    assert n == total == 328_697, (n, total)
    _report("period census", bad, n)
    # T3.18: plain MPCE spans all six columns; 'with imputation' only the two HCES rounds
    t18 = clean("report592_mpce").filter(pl.col("table_id") == "Table 3.18")
    for sid, pers in t18.group_by("series_id").agg(pl.col("period")).iter_rows():
        imputed = sid.split(".")[1] == "mpce_with_imputation"
        want = set(hces_windows().values()) if imputed else set(t318_heading())
        assert set(pers) == want and len(pers) == len(want), (sid, sorted(pers))


def _prov() -> pl.DataFrame:
    return pl.read_parquet(CLEAN / "_provenance.parquet")


NOTE_WINDOW_RX = r"Survey reference period ([A-Z][a-z]+) (\d{4}) - ([A-Z][a-z]+) (\d{4})"


def test_provenance_notes_name_the_row_window():
    """Each HCES record's note must state the window its rows carry; derived records must take their inputs
    from records of the same round and period (every HCES prov_id was re-issued in the close-out)."""
    prov = {r["prov_id"]: r for r in _prov().iter_rows(named=True)}
    used = defaultdict(set)
    for ds in DATASETS:
        for pid, per in clean(ds).select("prov_id", "period").unique().iter_rows():
            used[pid].add(per)
    assert set(used) == set(prov), "provenance records unused or missing"
    bad, n_inputs = [], 0
    for pid, pers in used.items():
        note = prov[pid]["notes"] or ""
        if prov[pid]["table_id"] == "Table 3.18":
            heads = {t318_heading()[p] for p in pers}
            if not all(h in note for h in heads) or "IHSN" not in note:
                bad.append((pid, sorted(pers), note[:120]))
        elif prov[pid]["source_id"] in SOURCE_ROUND:
            want = sy(SOURCE_ROUND[prov[pid]["source_id"]])
            m = re.search(NOTE_WINDOW_RX, note)
            if pers != {want} or not m or _window(*m.groups()) != want or f"rows carry period '{want}'" not in note:
                bad.append((pid, sorted(pers), note[:120]))
        for inp in filter(None, (prov[pid]["inputs"] or "").split(",")):  # stored comma-separated
            if inp not in prov or used.get(inp) != pers or prov[inp]["source_id"] != prov[pid]["source_id"]:
                bad.append((pid, "input", inp, sorted(used.get(inp, ())), sorted(pers)))
                continue
            n_inputs += 1
    assert n_inputs == 3, n_inputs  # A2 persons (2 rounds) and the CPI All-India sums
    _report("provenance windows", bad, len(used))


def test_cpi_derived_all_india_rows_closeout():
    """verify-6: all 716 derived rows carry the tag of the official col N rows they sum. Values are re-summed
    with a second xlsx reader (calamine) for a seeded sample of 80 rows (11%); test_cpi_census covers all."""
    w = clean("cpi2024_weights").filter(pl.col("table_id") == "Annexure 5.3d")
    d = w.filter(pl.col("status") == "derived")
    assert d.height == 716 and d["product"].n_unique() == 358
    assert set(d["dim_other"]) == {"share_of=all_india_combined_basket"}
    assert set(d["geography"]) == {"IN"} and set(d["item_code"]) == {"weight_share_all_india"}
    assert set(d["period"]) == {"2024"} and set(d["period_type"]) == {"cy"}
    assert w["dim_other"].null_count() == 0
    pr = _prov().filter(pl.col("prov_id").is_in(d["prov_id"].unique().to_list()))
    assert pr.height == 1 and pr["status"][0] == "derived" and "summed over States" in pr["locator"][0]
    sums = defaultdict(float)
    for r in sheet(CPI_KEY, "5.3d", engine="calamine")[4:]:
        if r[0] is None:
            continue
        sec = {1: "rural", 2: "urban"}[int(float(r[2]))]
        sums[(sec, str(r[4]).strip())] += float(r[13])
    sample = random.Random(SEED).sample(d.select("household_group", "product", "value").rows(), 80)
    bad = []
    for hg, prod, v in sample:
        want = sums.get((hg.split("_")[0], prod.split(":")[1]))
        if want is None or not close(v, want, 1e-6):
            bad.append((hg, prod, v, want))
    _report("CPI derived All-India rows (calamine, seeded sample)", bad, len(sample))


def _calamine_expected(ds: str, rnd: str) -> dict:
    """Raw cells from a calamine re-parse, keyed as in the census helpers."""
    if ds == "a2_fractile_persons":
        return raw_a2(rnd, engine="calamine")
    if ds == "a6_group_fractile":
        return raw_a6(rnd, engine="calamine")
    fname = {
        "a10f_item_fractile": "table_a10f.xlsx",
        "a10s_state_item": "table_a10s.xlsx",
        "a10sw_state_item_imputed": "table_a10sw.xlsx",
    }[ds]
    by = "fractile" if ds == "a10f_item_fractile" else "state"
    return raw_items(ROUNDS[rnd] + fname, by, engine="calamine")


@pytest.mark.parametrize("ds", HCES_EXCEL)
def test_calamine_seeded_sample_of_changed_rows(ds):
    """Every HCES Excel row changed period and prov_id in the close-out. A seeded 10% sample of each dataset
    is re-read with calamine (a different xlsx reader from the unit's and the census's openpyxl) and must
    match on value, geography, household group and survey window."""
    rows = (
        clean(ds)
        .select(
            "series_id", "period", "geography", "household_group", "item_code", "item_label", "product", "unit", "value"
        )
        .rows()
    )
    sample = random.Random(f"{SEED}-{ds}").sample(rows, max(30, -(-len(rows) // 10)))
    exp = {rnd: _calamine_expected(ds, rnd) for rnd in {TAG_ROUND[r[0].split(".")[1]] for r in sample}}
    bad = []
    for sid, per, g, hg, ic, lab, prod, unit, v in sample:
        rnd = TAG_ROUND[sid.split(".")[1]]
        if per != sy(rnd):
            bad.append((sid, per, "window"))
            continue
        if ds == "a2_fractile_persons":
            want = exp[rnd].get((g, hg, ic))
        elif ds == "a6_group_fractile":
            want = exp[rnd].get((g, hg, norm(lab)))
        else:
            cell = exp[rnd].get((g, hg, prod.split(":")[1]), {})
            if ic == "value_per_person_30d":
                want = cell.get("value")
            elif ic == "households_reporting":
                want = None if cell.get("hh") is None else cell["hh"] * 100
            else:
                q = cell.get("qty")
                want = None if q is None else (q / 1000 if unit == "tonnes" else q)
        tol = 1e-4 if ic in ("households_reporting", "households") or ds == "a2_fractile_persons" else 5e-7
        if want is None or not close(v, want, tol):
            bad.append((sid, per, g, hg, v, want))
    print(f"[spotcheck] {ds}: calamine sample {len(sample)} of {len(rows)} rows (seed {SEED}-{ds})")
    _report(f"{ds} calamine sample", bad, len(sample))
