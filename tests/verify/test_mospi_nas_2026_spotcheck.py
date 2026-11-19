"""Independent verification of ingest unit mospi_nas_2026 (Phase 1 verifier, first pass 2026-09-29;
second pass 2026-09-29: tests after test_checker_rejects_mutations check the verify-1..5 fixes;
close-out pass 2026-09-29: the NAS API datasets (mospi_nas_2026_api_*) are checked against the pinned JSON
pages with my own reader, the old-base stage relabel is re-derived from raw, and F1 is recomputed. The
workbook checks below apply to the statement datasets; API rows go through the close-out section).

This file does NOT import pipeline.ingest.mospi_nas_2026 (or its specs). The unit parses the MoSPI
workbooks with openpyxl and frozen row specs; this file re-reads every raw workbook with
python-calamine and locates each clean value by *search*, not by position:

1. every candidate cell in the pinned workbook whose number equals the clean value (after the unit's
   declared conversion) is found;
2. a candidate is accepted only if its own context agrees with the clean row:
   - label: every part of ``item_label`` appears in the cell's row, its column header chain or the
     nearest block-heading rows above it;
   - period: the nearest financial-year / quarter / year token in the column header chain (or the
     sheet name for 4.2) equals the clean ``period``;
   - price basis: the nearest 'current' / 'constant (YYYY-YY)' marker (column chain, then block rows,
     then the title) equals the clean ``price_basis``;
   - dims: industry / institution / COFOG / NIC / SNA account / side are checked against my own
     keyword maps (written from the raw labels, not from the unit's codes.py).
3. derived rows are recomputed from raw cells located the same way.

A seeded, stratified random sample (every dataset, >= 12% of each dataset, >= 10 rows each) plus
every 2023-24 row of the gap-map-critical statements (1.1, 1.9, 1.11, 1.14, 5.3, 6.1) is checked.
A reverse sweep checks that every level number of every new-base workbook appears in the clean data
(dropped-row detection), except the growth-rate blocks the unit documents as skipped.

Clean data are read with pyarrow.parquet directly.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from functools import cache
from pathlib import Path

import pyarrow.parquet as pq
import pytest
import yaml
from python_calamine import CalamineWorkbook
from rapidfuzz import fuzz

pytestmark = pytest.mark.quality

ROOT = Path(__file__).resolve().parents[2]
UNIT = "mospi_nas_2026"
CLEAN = ROOT / "data" / "clean" / UNIT
SEED = 20260929
FRACTION = 0.12
MIN_PER_DATASET = 10

DEV = re.compile("[\u0900-\u097f\u200b-\u200d\ufeff]+")
FY_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})\s*[-\u2013]\s*((?:19|20)?\d{2})(?!\d)")
Q_RE = re.compile(r"\bQ([1-4])\b")
YEAR_HDR = re.compile(
    r"(?:(?:19|20)\d{2}\s*[-\u2013]\s*(?:19|20)?\d{2}|Q[1-4]|(?:19|20)\d{2})(?:\s*\((?:FRE|SRE|TRE|PE|RE|AE)\))?"
)


# ---------------------------------------------------------------------------------------- basics
def is_num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def eng(s: object) -> str:
    """English part of a cell (Devanagari stripped), whitespace collapsed."""
    return " ".join(DEV.sub(" ", str(s)).split())


def norm(s: object) -> str:
    s = eng(s).lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def strip_serial(s: str) -> str:
    """Drop leading serial tokens ('1.1', '2.', 'i', '(a)') from a normalised label."""
    return re.sub(r"^(?:\d+(?: \d+)*|[ivx]+|[a-h])\s+", "", s)


@cache
def pins() -> dict:
    return yaml.safe_load((ROOT / "data" / "raw_pins" / f"{UNIT}.yaml").read_text(encoding="utf-8"))["pins"]


@cache
def raw_path(key: str) -> Path:
    pin = pins()[key]
    p = ROOT / pin["path"]
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    assert h == pin["sha256"], f"{key}: file hash {h} != pin {pin['sha256']}"
    return p


def file_key(table_id: str) -> str:
    """Map a clean table_id to its pin key (my own mapping, from the file names in the pins)."""
    m = re.fullmatch(r"Statement (\S+) \(NAS(2024|2025)\)", table_id)
    if m:
        return f"mospi_nas_old_base_2011_12/nas{m.group(2)}_{m.group(1)}.xlsx"
    m = re.fullmatch(r"Statement (\S+)", table_id)
    assert m, table_id
    return f"mospi_nas_2026_publication/{m.group(1)}.xlsx"


@cache
def workbook(key: str) -> dict[str, list[list]]:
    wb = CalamineWorkbook.from_path(str(raw_path(key)))
    # skip_empty_area=False keeps Excel coordinates (row 1 = index 0), so R/C references are real cells
    return {name: wb.get_sheet_by_name(name).to_python(skip_empty_area=False) for name in wb.sheet_names}


def cell(rows: list[list], r: int, c: int):
    if r < len(rows) and c < len(rows[r]):
        return rows[r][c]
    return ""


def header_like(row: list) -> bool:
    """A row without real data: every number is a small integer (serials, column numbers, years)."""
    return all(float(v).is_integer() and abs(v) <= 3000 for v in row if is_num(v))


def row_texts(row: list) -> list[str]:
    return [eng(v) for v in row if isinstance(v, str) and eng(v)]


@cache
def value_index(key: str) -> dict[str, list[tuple[int, int, float]]]:
    out: dict[str, list[tuple[int, int, float]]] = {}
    for name, rows in workbook(key).items():
        out[name] = [(r, c, float(v)) for r, row in enumerate(rows) for c, v in enumerate(row) if is_num(v)]
    return out


# ---------------------------------------------------------------------------------------- context
def column_chain(rows: list[list], r: int, c: int, cross_labels: bool = True) -> list[str]:
    """Header texts for column c above row r, nearest first (spanning headers propagate rightwards).

    With cross_labels=False the leftward propagation stops at a label column of the data row (a
    column where row r holds text), so a panel's year header never leaks into the next panel."""
    out = []
    for k in range(r - 1, -1, -1):
        row = rows[k]
        if not header_like(row):
            continue
        v = cell(rows, k, c)
        if v == "" or v is None:
            for j in range(c - 1, -1, -1):
                lab = cell(rows, r, j)
                if not cross_labels and isinstance(lab, str) and re.search(r"[A-Za-z]", eng(lab)):
                    break  # a label column of the data row separates panels: never cross it
                w = cell(rows, k, j)
                if w not in ("", None):
                    v = w if isinstance(w, str) or (is_num(w) and float(w).is_integer()) else ""
                    break
        if is_num(v):
            v = str(int(v))
        if isinstance(v, str) and eng(v):
            out.append(eng(v))
    return out


def block_rows(rows: list[list], r: int, limit: int = 60) -> list[str]:
    """Text of header-like rows above r (nearest first), each row joined."""
    out = []
    for k in range(r - 1, max(-1, r - 1 - limit), -1):
        if header_like(rows[k]):
            t = " || ".join(row_texts(rows[k]))
            if t:
                out.append(t)
    return out


def title_text(rows: list[list]) -> str:
    return " || ".join(" ".join(row_texts(rows[k])) for k in range(min(4, len(rows))))


def text_has(label_part: str, texts: list[str]) -> bool:
    a = strip_serial(norm(label_part))
    if not a:
        return True
    for t in texts:
        for piece in t.split(" || "):
            b = strip_serial(norm(piece))
            if not b:
                continue
            if a == b or (fuzz.ratio(a, b) >= 97 and a.split()[0] == b.split()[0]):
                return True
    return False


def slug_of(text: str) -> str:
    return strip_serial(norm(text)).replace(" ", "_")


def slug_eq(code_part: str, text: str) -> bool:
    """The unit's code segment names this label (codes are label slugs, truncated at ~60 chars)."""
    s = slug_of(text)
    if not s:
        return False
    if code_part == s:
        return True
    return len(code_part) >= 12 and (s.startswith(code_part) or code_part.startswith(s))


def row_label(row: list) -> str:
    """The English label of a row: the longest text cell with a letter in it."""
    texts = [t for t in row_texts(row) if re.search(r"[A-Za-z]{2}", t)]
    return max(texts, key=len) if texts else ""


def parent_ok(rec: dict, rows: list[list], r: int, parents: frozenset[str]) -> tuple[bool, str]:
    """For dotted item codes (repeated labels), the nearest parent heading above r must be the code's parent."""
    segs = rec["item_code"].split(".")
    if len(segs) < 2:
        return True, ""
    want = segs[-2]
    labels_in_sheet = [row_label(row) for row in rows]
    if not any(slug_eq(want, lab) for lab in labels_in_sheet):
        return True, ""  # synthetic prefix (e.g. 'pct_share'): nothing to check against
    # matrix layouts (5.2, 7.x, 8.16) code 'row.column': the row itself is the parent
    start = r - 1 if slug_eq(segs[-1], labels_in_sheet[r]) else r
    for k in range(start, -1, -1):
        lab = labels_in_sheet[k]
        hit = [p for p in parents if slug_eq(p, lab)]
        if hit:
            return (want in hit), f"nearest parent heading above is {lab!r}, code wants {want!r}"
    return False, f"no parent heading for {want!r}"


def fy_tokens(text: str) -> list[str]:
    out = []
    for a, b in FY_RE.findall(text):
        b2 = b[-2:]
        if int(b2) == (int(a) + 1) % 100:
            out.append(f"{a}-{b2}")
    return out


def period_of(rows, r, c, sheet: str, period_type: str) -> str | None:
    # only pure year headers count ('2023-24', '2024-25 (FRE)', '2022-2023', 'Q1', '2023'); captions such
    # as '(2022-23)' left over from 'At constant (2022-23) prices' do not
    chain = [t for t in column_chain(rows, r, c, cross_labels=False) if YEAR_HDR.fullmatch(t.strip())]
    if period_type == "fy":
        for t in chain:
            f = fy_tokens(t)
            if f:
                return f[0]
        f = fy_tokens(sheet)
        return f[0] if f else None
    if period_type == "fq":
        q = fy = None
        for t in chain:
            if q is None and Q_RE.search(t):
                q = Q_RE.search(t).group(1)
            if fy is None and fy_tokens(t):
                fy = fy_tokens(t)[0]
        return f"Q{q} {fy}" if q and fy else None
    if period_type == "date":
        for t in chain:
            m = re.fullmatch(r"((?:19|20)\d{2})", t.strip())
            if m:
                return f"{m.group(1)}-03-31"
        return None
    raise AssertionError(period_type)


def pb_marker(text: str) -> str | None:
    t = text.lower()
    cur, con = "current" in t, "constant" in t
    if cur and not con:
        return "current"
    if con and not cur:
        f = fy_tokens(t)
        if len(set(f)) == 1:  # 'constant (2022-23) prices' or 'constant prices, 2022-23 series'
            return "constant_" + f[0].replace("-", "_")
        return "constant_?"
    return None


def price_basis_of(rows, r, c) -> str | None:
    """Nearest price marker; a bare 'constant' keeps looking for one that names the base year."""
    vague = None
    sources = list(column_chain(rows, r, c)) + block_rows(rows, r, limit=200)
    sources += [" ".join(row_texts(rows[k])) for k in range(min(4, len(rows)))]
    for t in sources:
        m = pb_marker(t)
        if m == "constant_?":
            vague = vague or m
            continue
        if m:
            if vague and m == "current":
                return vague  # the nearer marker said 'constant'
            return m
    if vague:  # a bare 'constant' panel: take the base year that the title names for constant prices
        title = " ".join(" ".join(row_texts(rows[k])) for k in range(min(4, len(rows)))).lower()
        m = re.search(r"constant\s*\(\s*((?:19|20)\d{2})\s*[-\u2013]\s*(\d{2})\s*\)", title)
        if m:
            return f"constant_{m.group(1)}_{m.group(2)}"
    return vague


# ---------------------------------------------------------------------------------------- dims
IND = {
    "agri": r"agriculture livestock forestry (and )?fish\w*",
    "crops": r"crops",
    "livestock": r"livestock",
    "forestry": r"forestry (and )?logging",
    "fishing": r"fishing and aquaculture",
    "mining": r"mining (and )?quarrying",
    "manufacturing": r"manufacturing",
    "mfg_food": r"food products beverages and tobacco",
    "mfg_textiles": r"textiles apparel and leather products",
    "mfg_metal": r"metal products",
    "mfg_machinery": r"machinery and equipment",
    "mfg_other": r"other manufactured goods",
    "utilities": r"electricity gas water supply (and )?other utility services",
    "construction": r"construction",
    "trade_hotels": r"trade repair hotels and restaurants",
    "trade_repair": r"trade and repair services",
    "hotels": r"hotels and restaurants",
    "transport_comm": r"transport storage communication and services related to broadcasting",
    "railways": r"railways",
    "road_transport": r"road transport",
    "water_transport": r"water transport",
    "air_transport": r"air transport",
    "transport_services": r"services incidental to transport",
    "storage": r"storage",
    "communication": r"communication and services related to broadcasting",
    "financial": r"financial services",
    "real_estate_prof": r"real estate ownership of dwelling (and )?professional services",
    "public_admin": r"public administration and defence",
    "other_services": r"other services",
    "total": (
        r"total( gva at basic prices)?|gva at basic prices|total gva|total \w+ at basic prices"
        r"|total \w+ by industry of use"
    ),
    "primary": r"primary sector",
    "secondary": r"secondary sector",
    "tertiary": r"tertiary sector",
    "trade_transport_comm": r"trade hotels transport communication.*",
    "financial_real_estate_prof": r"financial real estate.*",
    "public_admin_other": r"public administration defence and other services",
}

INST = {
    "nfc_public": r"public non financial corporations?",
    "nfc_private": r"private non financial corporations?",
    "fc_public": r"public financial corporations?",
    "fc_private": r"private financial corporations?",
    "gg": r"general government",
    "households_npish": r"households? including npish|household sector|households",
    "public_sector": r"public sector",
    "private_corporate": r"private corporat\w*",
    "public_departmental_enterprises": r"departmental enterprises",
    "public_non_departmental_enterprises": r"non departmental enterprises",
    "nfc": r"non financial corporations?",
    "fc": r"financial corporations?",
    "rest_of_world": r"rest of the world",
    "total_economy": r"total economy",
    "nfc_public_de": r"departmental",
    "nfc_public_nde": r"non departmental",
}

COFOG = {
    "01": "general public services",
    "02": "defence",
    "03": "public order and safety",
    "04": "economic affairs",
    "04.admin": "general administration regulation and research",
    "04.agri": "agriculture forestry and fishing",
    "04.mining_mfg_constr": "mining manufacturing and construction",
    "04.energy": "electricity gas steam and other sources of energy",
    "04.water_supply": "water supply",
    "04.transport_comm": "transport and communication",
    "04.other": "other economic services",
    "05": "environment protection",
    "06": "housing and community amenities",
    "07": "health",
    "07.admin": "administration regulation and research",
    "07.health_services": "health services",
    "08": "recreation culture and religion",
    "09": "education",
    "09.admin": "administration regulation and research",
    "09.educational_services": "educational services",
    "10": "social protection",
    "total": "total",
}
COFOG_PARENT = {"07.admin": "health", "09.admin": "education"}

ACCOUNT = {
    "production": r"production account",
    "generation_of_income": r"generation of income account",
    "allocation_of_primary_income": r"allocation of primary income account",
    "secondary_distribution_of_income": r"secondary distribution of income account",
    "redistribution_of_income_in_kind": r"redistribution of income in kind account",
    "use_of_disposable_income": r"use of disposable income account",
    "use_of_adjusted_disposable_income": r"use of adjusted disposable income account",
    "capital": r"capital account",
    "financial": r"financial account",
    "external_of_goods_and_services": r"external account of goods and services",
    "external_of_primary_income": r"external account of primary income",
    "external_of_secondary_income": r"external account of secondary income",
    "external_of_disposable_income": r"external account of disposable income",
}
SIDE = {
    "resources": r"resources",
    "uses": r"uses",
    "liabilities": r"changes in liabilities and net worth|liabilities",
    "assets": r"changes in assets|assets",
}


def label_matches(pattern: str, texts: list[str]) -> bool:
    rx = re.compile(rf"(?:{pattern})")
    for t in texts:
        for piece in t.split(" || "):
            if rx.fullmatch(strip_serial(norm(piece))):
                return True
    return False


def nearest_block_matching(rows, r, table: dict[str, str]) -> str | None:
    """The code whose pattern fully matches the nearest header-like row above r (any cell)."""
    for t in block_rows(rows, r, limit=400):
        for piece in t.split(" || "):
            n = strip_serial(norm(piece))
            for code, pat in table.items():
                if re.fullmatch(pat, n):
                    return code
    return None


# ---------------------------------------------------------------------------------------- checks
def dims_ok(rec: dict, rows, r, c, sheet: str) -> tuple[bool, str]:
    rowt = row_texts(rows[r])
    chain = column_chain(rows, r, c)
    title = title_text(rows)
    ind = rec.get("industry")
    if ind:
        pat = IND[ind]
        if not label_matches(pat, rowt):
            is_item_row = text_has(rec["item_label"].split(" | ")[-1], rowt)
            other = [] if is_item_row else [k for k, p in IND.items() if label_matches(p, rowt)]
            if other:
                return False, f"industry {ind} but the row is labelled as {other}"
            blk = nearest_block_matching(rows, r, IND)
            if blk != ind:
                return False, f"industry {ind} not in row {rowt[:3]}; nearest industry block is {blk}"
    inst = rec.get("institution")
    if inst and rec["dataset"].endswith(("s1_14", "s5_3")):
        blk = nearest_block_matching(
            rows,
            r,
            {k: INST[k] for k in ("nfc_public", "nfc_private", "fc_public", "fc_private", "gg", "households_npish")},
        )
        if rec["dataset"].endswith("s1_14") and blk != inst:
            return False, f"institution {inst} but nearest block is {blk}"
    elif inst and inst not in ("total_economy",):
        hay = [title] + block_rows(rows, r, limit=400)[:3] + rowt
        segs = rec["item_code"].split(".")
        if len(segs) >= 2:  # second pass: a sub-row may take its sector from its parent heading
            # (parent_ok() separately proves that heading is the nearest parent above this cell)
            hay += [row_label(rows[k]) for k in range(r - 1, -1, -1) if slug_eq(segs[-2], row_label(rows[k]))][:1]
        if not any(re.search(INST[inst], norm(h)) for h in hay):
            return False, f"institution {inst} not in title/blocks"
    other = rec.get("dim_other") or ""
    for kv in filter(None, other.split(";")):
        k, v = kv.split("=", 1)
        if k == "cofog":
            want = COFOG[v]
            if not chain or norm(chain[0]) != want:
                return False, f"cofog {v}: header {chain[:1]}"
            if v in COFOG_PARENT:
                hr = next(k2 for k2 in range(r - 1, -1, -1) if any(norm(x) == "defence" for x in rows[k2]))
                parents = [norm(cell(rows, hr, j)) for j in range(c - 1, -1, -1)]
                top = next(
                    p
                    for p in parents
                    if p
                    in (
                        "health",
                        "education",
                        "economic affairs",
                        "housing and community amenities",
                        "recreation culture and religion",
                    )
                )
                if top != COFOG_PARENT[v]:
                    return False, f"cofog {v}: parent {top}"
        elif k == "nic":
            codes = {re.sub(r"\s+", "", str(x)) for x in rows[r] if x not in ("", None)}
            codes |= {str(int(x)) for x in rows[r] if is_num(x) and float(x).is_integer()}
            if v not in codes:
                return False, f"nic {v} not in row {sorted(codes)[:6]}"
        elif k == "account":
            got = nearest_block_matching(rows, r, ACCOUNT)
            if got != v:
                return False, f"account {v} but block {got}"
        else:
            return False, f"unknown dim_other key {k}"
    side = rec.get("side")
    if side:
        got = nearest_block_matching(rows, r, SIDE)
        if got != side:
            return False, f"side {side} but block {got}"
    return True, ""


def scale_for(rec: dict, prov: dict) -> float:
    conv = prov[rec["prov_id"]]["conversion"]
    if conv == "none":
        return 1.0
    if conv.startswith("x 1,000,000"):
        return 1e6
    raise AssertionError(f"unexpected conversion {conv!r}")


def locate(rec: dict, prov: dict) -> tuple[str, list[str]]:
    """Return ('ok', [where]) / ('sign', ...) / ('fail', reasons)."""
    key = file_key(rec["table_id"])
    pv = prov[rec["prov_id"]]
    assert pv["raw_path"].replace("\\", "/") == pins()[key]["path"], (rec["table_id"], pv["raw_path"])
    scale = scale_for(rec, prov)
    target = rec["value"] / scale
    tol = 1e-6 / scale + 1e-12 * abs(target)
    reasons = []
    sign_hit = False
    for sheet, cells in value_index(key).items():
        rows = workbook(key)[sheet]
        for r, c, v in cells:
            if abs(v - target) > tol:
                if abs(-v - target) <= tol and target != 0:
                    sign_hit = True
                continue
            why = []
            label = rec["item_label"]
            m = re.fullmatch(r"(.*) \[([^\]]+)\]", label)  # old base: 'Compensation of employees [D1]'
            if m:
                label, sna = m.group(1), m.group(2)
                if sna != "-" and sna not in {str(x).strip() for x in rows[r] if isinstance(x, str)}:
                    why.append(f"SNA code {sna} not in row")
            parts = label.split(" | ")
            texts = row_texts(rows[r]) + column_chain(rows, r, c, cross_labels=False)
            for p in parts:
                if not text_has(p, texts):
                    why.append(f"label part {p!r} not in context")
            ok, msg = parent_ok(rec, rows, r, parents_of(rec["dataset"]))
            if not ok:
                why.append(msg)
            per = period_of(rows, r, c, sheet, rec["period_type"])
            if per != rec["period"]:
                why.append(f"period {per} != {rec['period']}")
            if rec["price_basis"] != "n/a":
                pb = price_basis_of(rows, r, c)
                if pb is None and "_oldbase_soa_" in rec["dataset"]:
                    pb = "current"  # sequences of accounts carry no price marker; they exist only at current prices
                if pb != rec["price_basis"]:
                    why.append(f"price basis {pb} != {rec['price_basis']}")
            ok, msg = dims_ok(rec, rows, r, c, sheet)
            if not ok:
                why.append(msg)
            where = f"{sheet}!R{r + 1}C{c + 1}"
            if not why:
                return "ok", [where]
            reasons.append(f"{where}: " + "; ".join(why))
    if not reasons:
        reasons.append("value not found in workbook" + (" (found with opposite sign)" if sign_hit else ""))
    return "fail", reasons


# ---------------------------------------------------------------------------------------- data
@cache
def parents_of(dataset: str) -> frozenset[str]:
    return frozenset(c.split(".")[-2] for c in {r["item_code"] for r in datasets()[dataset]} if "." in c)


@cache
def datasets() -> dict[str, list[dict]]:
    out = {}
    for p in sorted(CLEAN.glob("*.parquet")):
        if p.name.startswith("_"):
            continue
        out[p.stem] = pq.read_table(p).to_pylist()
    return out


def is_api(name: str) -> bool:
    """NAS API datasets (close-out pass): values live in JSON pages, not workbooks."""
    return name.startswith(f"{UNIT}_api_")


def stmt_datasets() -> dict[str, list[dict]]:
    return {k: v for k, v in datasets().items() if not is_api(k)}


@cache
def provenance() -> dict[str, dict]:
    return {r["prov_id"]: r for r in pq.read_table(CLEAN / "_provenance.parquet").to_pylist()}


CRITICAL = {
    "mospi_nas_2026_s1_1",
    "mospi_nas_2026_s1_9",
    "mospi_nas_2026_s1_11",
    "mospi_nas_2026_s1_14",
    "mospi_nas_2026_s5_3",
    "mospi_nas_2026_s6_1",
}


def sample() -> list[dict]:
    rng = random.Random(SEED)
    out = []
    for name, rows in sorted(stmt_datasets().items()):
        if name.endswith("derived_residuals"):
            continue
        n = min(len(rows), max(MIN_PER_DATASET, math.ceil(FRACTION * len(rows))))
        idx = set(rng.sample(range(len(rows)), n))
        if name in CRITICAL:
            idx |= {i for i, r in enumerate(rows) if r["period"] == "2023-24"}
        out += [rows[i] for i in sorted(idx)]
    return out


def run_spotcheck() -> tuple[list[dict], list[tuple[dict, list[str]]]]:
    prov = provenance()
    checked, failures = [], []
    for rec in sample():
        status, info = locate(rec, prov)
        checked.append(rec)
        if status != "ok":
            failures.append((rec, info))
    return checked, failures


# ---------------------------------------------------------------------------------------- tests
def test_sample_is_large_enough():
    """Workbook sample (statement datasets). The API datasets have their own sample and census below."""
    total = sum(len(v) for v in stmt_datasets().values())
    s = sample()
    assert len(s) >= 0.10 * total, (len(s), total)
    assert {r["dataset"] for r in s} >= {k for k in stmt_datasets() if not k.endswith("derived_residuals")}
    periods = Counter((r["dataset"], r["period"]) for r in s)
    assert len(periods) > 150


def test_spotcheck_values_against_raw():
    checked, failures = run_spotcheck()
    msg = "\n".join(
        f"{r['dataset']} {r['series_id']} {r['period']} {r['value']}: {' | '.join(info[:3])}"
        for r, info in failures[:40]
    )
    assert not failures, f"{len(failures)} of {len(checked)} sampled values failed:\n{msg}"


def test_every_row_against_raw():
    """Full population (not a sample): every official clean row is located in its raw workbook with the same
    checks as the sample test (label, period, price basis, dims, parent heading). ~40 s."""
    prov = provenance()
    failures, n = [], 0
    for name, rows in stmt_datasets().items():
        if name.endswith("derived_residuals"):
            continue
        for rec in rows:
            n += 1
            status, info = locate(rec, prov)
            if status != "ok":
                failures.append((name, rec["series_id"], rec["period"], rec["value"], info[:2]))
    assert n == sum(len(v) for k, v in stmt_datasets().items() if not k.endswith("derived_residuals"))
    assert not failures, (len(failures), failures[:20])


def _find(key: str, label: str, period: str, block: str | None = None) -> float:
    """Locate one value by English label (and optional block heading) and period, independently."""
    hits = []
    for sheet, rows in workbook(key).items():
        for r, row in enumerate(rows):
            if not any(norm(t) == norm(label) for t in row_texts(row)):
                continue
            if block and not any(norm(block) in norm(t) for t in block_rows(rows, r, limit=400)[:1]):
                continue
            for c, v in enumerate(row):
                if (
                    is_num(v)
                    and period_of(rows, r, c, sheet, "fy") == period
                    and price_basis_of(rows, r, c)
                    in (
                        "current",
                        None,
                    )
                ):
                    hits.append(float(v))
                    break
    assert len(hits) == 1, (key, label, period, block, hits)
    return hits[0]


def test_derived_residuals_recomputed_from_raw():
    """Both official gaps recomputed from raw cells found by label (1.14 households; 1.1 GCF vs 1.9 item 3)."""
    rows = datasets()["mospi_nas_2026_derived_residuals"]
    k114 = "mospi_nas_2026_publication/1.14.xlsx"
    k11 = "mospi_nas_2026_publication/1.1.xlsx"
    k19 = "mospi_nas_2026_publication/1.9.xlsx"
    hh = "Households including NPISH"
    for per in ("2022-23", "2023-24", "2024-25"):
        gdi = _find(k114, "Gross Disposable Income", per, hh)
        fce = _find(k114, "Final Consumption Expenditure", per, hh)
        sav = _find(k114, "Gross Savings", per, hh)
        got = [r for r in rows if r["period"] == per and r["series_id"] == "derived.household_residual.current"]
        assert len(got) == 1 and abs(got[0]["value"] - (gdi - fce - sav)) < 1e-3, (per, got, gdi - fce - sav)
        gcf = _find(k11, "GCF", per)
        fin = _find(k19, "finances for gross capital formation (1+2)", per)
        got = [r for r in rows if r["period"] == per and r["series_id"] == "derived.si_errors_omissions.current"]
        assert len(got) == 1 and abs(got[0]["value"] - (gcf - fin)) < 1e-3, (per, got, gcf - fin)
        # close-out pass: gap map F1 = 7.1 'Total' x 'Compensation of employees' (domestic) + 6.1 CE from RoW
        # - 6.1 CE to RoW, all three located in raw by label
        ce = _find_col("mospi_nas_2026_publication/7.1.xlsx", "Total", "compensation of employee", per)
        k61 = "mospi_nas_2026_publication/6.1.xlsx"
        frm = _find(k61, "compensation of employees from rest of the world", per)
        to = _find(k61, "compensation of employees to the rest of the world", per)
        got = [r for r in rows if r["period"] == per and r["series_id"] == "derived.ce_receivable_by_residents.current"]
        assert len(got) == 1 and abs(got[0]["value"] - (ce + frm - to)) < 1e-3, (per, got, ce + frm - to)
        assert got[0]["estimate_stage"] == NEW_STAGE[per] and got[0]["vintage"] == "2026-08-31"
    assert len(rows) == 9 and len({r["series_id"] for r in rows}) == 3
    # derived rows must be labelled derived, with a method and inputs
    prov = provenance()
    for r in rows:
        assert r["status"] == "derived"
        pv = prov[r["prov_id"]]
        assert pv["status"] == "derived" and pv["method"] and pv["inputs"]
    # F1's inputs are exactly the provenance records of the 7.1 total-CE row and the two 6.1 CE rows
    want_inputs = set()
    for ds, pred in (
        ("mospi_nas_2026_s7_1",
         lambda r: r["industry"] == "total" and "compensation of employee" in norm(r["item_label"])),
        ("mospi_nas_2026_s6_1", lambda r: norm(r["item_label"]).startswith("compensation of employees")),
    ):
        want_inputs |= {r["prov_id"] for r in datasets()[ds] if r["price_basis"] == "current" and pred(r)}
    f1 = next(r for r in rows if r["series_id"] == "derived.ce_receivable_by_residents.current")
    assert set(prov[f1["prov_id"]]["inputs"].split(",")) == want_inputs, (prov[f1["prov_id"]]["inputs"], want_inputs)
    # 2023-24 figures quoted in the unit's issues file and the gap map
    by = {(r["series_id"], r["period"]): r["value"] for r in rows}
    assert round(by[("derived.household_residual.current", "2023-24")]) == 571133
    assert round(by[("derived.si_errors_omissions.current", "2023-24")]) == 358634
    assert round(by[("derived.ce_receivable_by_residents.current", "2023-24")]) == 9474605  # 94,42,897+62,344-30,636


def _find_col(key: str, row_label: str, col_label: str, period: str) -> float:
    """Locate one matrix value (7.1: industry row x item column) by English row label, column header and period."""
    hits = []
    for sheet, rows in workbook(key).items():
        for r, row in enumerate(rows):
            if not any(norm(t) == norm(row_label) for t in row_texts(row)):
                continue
            for c, v in enumerate(row):
                chain = column_chain(rows, r, c)
                if is_num(v) and period_of(rows, r, c, sheet, "fy") == period and chain and norm(chain[0]).startswith(
                    norm(col_label)
                ):
                    hits.append(float(v))
    assert len(hits) == 1, (key, row_label, col_label, period, hits)
    return hits[0]


def test_provenance_points_at_the_statement_file():
    """Every row (not a sample): its provenance record is the pinned file of its own statement."""
    prov = provenance()
    bad = []
    for name, rows in datasets().items():
        for r in rows:
            pv = prov[r["prov_id"]]
            if r["status"] == "derived":
                continue
            if is_api(name):  # close-out: a pinned JSON page of this row's own query and indicator
                tag, _ = API_TAG[name.removeprefix(f"{UNIT}_")]
                ind = int(API_TABLE.fullmatch(r["table_id"]).group(1))
                keys = [k for k, p in pins().items() if p["path"] == pv["raw_path"].replace("\\", "/")]
                m = PAGE_RE.fullmatch(keys[0]) if len(keys) == 1 else None
                if not m or (m.group(1), int(m.group(2))) != (tag, ind) or pv["table_id"] != r["table_id"]:
                    bad.append((name, r["series_id"], r["period"], pv["raw_path"], pv["table_id"]))
                if (pv["source_id"], pv["conversion"], pv["status"]) != ("mospi_nas_api", "none", "official"):
                    bad.append((name, r["series_id"], "prov", pv["source_id"], pv["conversion"]))
            else:
                want = pins()[file_key(r["table_id"])]["path"]
                if pv["raw_path"].replace("\\", "/") != want or pv["table_id"] != r["table_id"]:
                    bad.append((name, r["series_id"], r["period"], pv["raw_path"], pv["table_id"]))
            for f in ("source_id", "price_basis", "vintage", "status"):
                if pv[f] != r[f]:
                    bad.append((name, r["series_id"], f, pv[f], r[f]))
    assert not bad, bad[:10]


NEW_STAGE = {"2022-23": "Final", "2023-24": "Final", "2024-25": "FRE", "2025-26": "PE"}


def textbook_stage(vintage: str, period: str) -> str:
    """First/second-pass rule for old-base stages (latest FRE, then SRE, then TRE). Superseded in the close-out
    pass by oldbase_stage_table(), which is derived from raw; kept to count the rows the relabel touched."""
    last = "2022-23" if vintage == "2024-06-05" else "2023-24"
    prev = f"{int(last[:4]) - 1}-{last[2:4]}"
    return "FRE" if period == last else "SRE" if period == prev else "TRE"


def test_base_vintage_and_stage_labels():
    """New and old base strictly separated; new-base stages follow the NAS 2026 press release (Final/Final/FRE/PE).
    Old-base stages (close-out pass): the table derived from raw in oldbase_stage_table(), not the textbook cycle
    (the NAS API's revision rounds show the cycle was wrong for 2011-12..2013-14 and NAS 2025's 2021-22/2022-23).
    API rows: base from the query, source mospi_nas_api, vintage = the page's retrieval date, stage from the
    record's revision field (checked per row in test_api_census_every_row_against_raw_json)."""
    bad = []
    stages = oldbase_stage_table()
    for name, rows in datasets().items():
        old = "_oldbase_" in name
        for r in rows:
            if is_api(name):
                base = API_TAG[name.removeprefix(f"{UNIT}_")][1]
                ok = (
                    r["base_year"] == base
                    and r["price_basis"] in ("current", f"constant_{base.replace('-', '_')}")
                    and r["source_id"] == "mospi_nas_api"
                    and r["vintage"] == "2026-09-29"
                    and r["status"] == "official"
                )
                if name.endswith("b2022_annual"):  # the API's new-base rounds = the NAS 2026 press-release stages
                    ok = ok and r["estimate_stage"] == NEW_STAGE[r["period"]]
            elif old:
                ok = (
                    r["base_year"] == "2011-12"
                    and r["price_basis"] in ("current", "constant_2011_12", "n/a")
                    and r["vintage"] in ("2024-06-05", "2025-06-26")
                    and r["source_id"] == "mospi_nas_old_base_2011_12"
                )
                edition = "nas2024" if r["vintage"] == "2024-06-05" else "nas2025"
                last = "2022-23" if edition == "nas2024" else "2023-24"
                ok = ok and r["estimate_stage"] == stages[(edition, r["period"])] and r["period"] <= last
            else:
                fy = r["period"].split(" ")[-1]
                if r["period_type"] == "date":  # stock at 31 March of year Y belongs to FY (Y-1)-Y
                    y = int(r["period"][:4])
                    fy = f"{y - 1}-{str(y)[2:]}"
                ok = (
                    r["base_year"] == "2022-23"
                    and r["price_basis"] in ("current", "constant_2022_23", "n/a")
                    and r["vintage"] == "2026-08-31"
                    and r["source_id"] == "mospi_nas_2026_publication"
                    and r["estimate_stage"] == NEW_STAGE[fy]
                )
            if not ok:
                bad.append(
                    (
                        name,
                        r["series_id"],
                        r["period"],
                        r["base_year"],
                        r["price_basis"],
                        r["vintage"],
                        r["estimate_stage"],
                    )
                )
    assert not bad, (len(bad), bad[:10])


def unmatched_raw_numbers() -> dict[str, list[str]]:
    """Reverse sweep: raw data numbers of every ingested workbook that appear nowhere in that table's clean rows."""
    import bisect

    by_table: dict[str, list[float]] = defaultdict(list)
    prov = provenance()
    for rows in stmt_datasets().values():  # API pages have their own reverse sweep (close-out section)
        for r in rows:
            scale = 1e6 if prov[r["prov_id"]]["conversion"] != "none" else 1.0
            by_table[r["table_id"]].append(r["value"] / scale)
    missing = {}
    for table_id, vals in by_table.items():
        if "derived" in table_id:
            continue
        vals = sorted(vals)

        def present(x: float, vals: list[float] = vals) -> bool:
            k = bisect.bisect_left(vals, x - 2e-6)
            return k < len(vals) and abs(vals[k] - x) <= 2e-6 + 1e-12 * abs(x)

        miss = []
        for sheet, rows in workbook(file_key(table_id)).items():
            for r, row in enumerate(rows):
                if header_like(row):
                    continue
                if not re.search(r"[A-Za-z]{2}", " ".join(row_texts(row))) and all(
                    abs(v) < 100 for v in row if is_num(v)
                ):
                    continue  # a row of column serial numbers (4.2 row 7)
                for c, v in enumerate(row):
                    if not is_num(v) or present(float(v)):
                        continue
                    if c == 0 or c == len(row) - 1 or (c >= len(row) - 2 and abs(v) < 100):
                        continue  # S.No. columns (first and last)
                    if (
                        float(v).is_integer()
                        and abs(v) < 1000
                        and any(
                            j != c and str(int(v)) == re.sub(r"\.0$", "", str(w)).strip() for j, w in enumerate(row)
                        )
                    ):
                        continue  # a code repeated in the row (8.6.x: NIC code on both Hindi and English sides)
                    hdr = " ".join(column_chain(rows, r, c, cross_labels=False)).lower()
                    if re.search(r"s\.\s?no|sl\.\s?no|nic 2008 code|\bcode\b", hdr):
                        continue  # serial / NIC-code columns
                    miss.append(f"{sheet}!R{r + 1}C{c + 1}={v}")
        if miss:
            missing[table_id] = miss
    return missing


# Blocks the unit documents as not ingested (issues file, mospi_nas_2026-3): growth-rate columns/rows
# of 8.17.1, 8.17.2, 8.18.1, 8.18.2. Anything else unmatched is a dropped value.
SKIPPED_BY_DESIGN = {"Statement 8.17.1", "Statement 8.17.2", "Statement 8.18.1", "Statement 8.18.2"}


def test_every_raw_number_is_ingested():
    missing = unmatched_raw_numbers()
    unexpected = {k: v for k, v in missing.items() if k not in SKIPPED_BY_DESIGN}
    assert not unexpected, {k: (len(v), v[:6]) for k, v in unexpected.items()}


def test_skipped_blocks_are_only_growth_rates():
    """In the growth-rate statements every unmatched number must sit under a 'percentage change' / growth header."""
    missing = unmatched_raw_numbers()
    bad = []
    for table_id in SKIPPED_BY_DESIGN & set(missing):
        rows_by_sheet = workbook(file_key(table_id))
        for ref in missing[table_id]:
            sheet, rc = ref.split("!")
            r, c = (int(x) - 1 for x in re.match(r"R(\d+)C(\d+)", rc).groups())
            rows = rows_by_sheet[sheet]
            ctx = " ".join(column_chain(rows, r, c) + block_rows(rows, r, 400)).lower()
            if "percentage change" not in ctx and "growth" not in ctx:
                bad.append(ref)
    assert not bad, bad[:20]


# Canonical SNA 2008 codes of the financial-account rows (label -> code). Written from the SNA, not from the unit.
SNA_FIN = {
    "monetary gold and sdrs": "F1",
    "currency and deposits": "F2",
    "debt securities": "F3",
    "loans": "F4",
    "equity and investment fund shares": "F5",
    "insurance pension and standardised guarantee scheme": "F6",
    "financial derivatives and employee stock options": "F7",
    "other accounts payable": "F8",
    "other accounts receivable": "F8",
    "net lending net borrowing": "B9",
}


def test_oldbase_sna_codes_match_labels():
    """Every old-base row whose label is an SNA financial instrument (or B9) must carry that instrument's code.

    Raw nas2024_3.0 prints the English-side code column (P) shifted down one row on the financial-account
    liabilities block (P92 'F1' beside 'Net incurrence of liabilities' ... P100 'B9' beside 'Other accounts
    payable'); the Hindi-side code column A is correct. A unit that reads column P mis-codes those rows."""
    bad = []
    for name, rows in datasets().items():
        if "_oldbase_soa_" not in name:
            continue
        for r in rows:
            m = re.fullmatch(r"(.*) \[([^\]]+)\]", r["item_label"])
            if not m:
                continue
            lab = norm(m.group(1)).replace(" *", "").strip()
            want = SNA_FIN.get(lab)
            if want and (m.group(2) != want or r["item_code"].split(".")[-1] != want.lower()):
                bad.append((name, r["series_id"], r["item_label"], r["period"]))
            totals = ("net incurrence of liabilities", "net acquisition of financial assets")
            if lab in totals and m.group(2) not in ("-", "F"):
                bad.append((name, r["series_id"], r["item_label"], r["period"]))
    seen = sorted({b[:3] for b in bad})
    assert not bad, f"{len(bad)} rows ({len(seen)} series) carry the wrong SNA code: {seen}"


def test_oldbase_financial_accounts_close_in_raw():
    """Raw check (no clean data): in every NAS 2024 sequence, net acquisition of financial assets - net incurrence
    of liabilities = B9 of the financial account = B9 of the capital account, every year. So a clean dataset that
    does not close (unit issue mospi_nas_2026-13 for 3.0) points at the ingest, not at MoSPI."""
    bad = []
    for key in [k for k in pins() if re.search(r"/nas2024_\d\.\d[AB]?\.xlsx$|/nas2024_1\.15\.xlsx$", k)]:
        for rows in workbook(key).values():

            def find(label: str, after: int, rows: list[list] = rows) -> int:
                return next(i for i in range(after, len(rows)) if any(norm(x) == norm(label) for x in rows[i]))

            fa = find("Financial account", 0)
            ca = find("Capital account", 0)
            ni, na = find("Net incurrence of liabilities", fa), find("Net acquisition of financial assets", fa)
            b9f, b9c = find("NET LENDING (+) / NET BORROWING (-)", fa), find("NET LENDING (+) / NET BORROWING (-)", ca)
            for c in range(2, 14):
                vals = [rows[k][c] for k in (na, ni, b9f, b9c)]
                if not all(is_num(v) for v in vals):
                    continue
                a, li, f9, c9 = vals
                if abs(a - li - f9) > 3 or abs(f9 - c9) > 3:
                    bad.append((key, c, round(a - li - f9, 1), round(f9 - c9, 1)))
    assert not bad, bad[:10]


def test_checker_rejects_mutations():
    """Self-test: the checker must reject wrong values, row shifts, wrong periods and wrong price bases
    (otherwise a 'pass' above would mean nothing). Seeded; ~300 records x 4 mutations."""
    prov = provenance()
    rng = random.Random(SEED + 1)
    recs = sample()
    rng.shuffle(recs)
    leaks, tried = [], 0
    for rec in recs[:300]:
        rows = datasets()[rec["dataset"]]
        muts = [dict(rec, value=rec["value"] * 1.001 + 0.01)]
        others = [
            r
            for r in rows
            if r["period"] == rec["period"]
            and r["price_basis"] == rec["price_basis"]
            and r["series_id"] != rec["series_id"]
            and abs(r["value"] - rec["value"]) > 1e-3
        ]
        if others:
            muts.append(dict(rec, value=rng.choice(others)["value"]))
        pers = sorted(
            {r["period"] for r in rows if r["series_id"] == rec["series_id"] and abs(r["value"] - rec["value"]) > 1e-3}
        )
        if pers:
            muts.append(dict(rec, period=rng.choice(pers)))
        alt = [
            r
            for r in rows
            if r["item_code"] == rec["item_code"]
            and r["period"] == rec["period"]
            and r["price_basis"] != rec["price_basis"]
            and abs(r["value"] - rec["value"]) > 1e-3
            and r.get("industry") == rec.get("industry")
            and r.get("institution") == rec.get("institution")
        ]
        if alt:
            muts.append(dict(rec, price_basis=alt[0]["price_basis"]))
        for m in muts:
            tried += 1
            if locate(m, prov)[0] == "ok":
                leaks.append((rec["series_id"], rec["period"], m["value"], m["period"], m["price_basis"]))
    assert tried > 900
    assert len(leaks) <= 2, leaks  # allow rare genuine coincidences (equal published numbers)


# ======================================================================================== second pass
# Checks of the builder's fixes for verify-1 (3.0 code shift), verify-2 (closure), verify-4 ('Less' notes)
# and verify-5 (4.1 geography, 1.9 / 1.11 institution). Still no import of the unit's code.
CODE_RE = re.compile(r"[A-Z][A-Za-z0-9+/]{0,7}")


def ascii_code(v: object) -> str:
    s = v.strip() if isinstance(v, str) else ""
    return s if CODE_RE.fullmatch(s) and s.upper() not in ("CODE", "USES") else ""


def raw_code_columns(rows: list[list], r: int) -> tuple[str, str]:
    """(Hindi-side column A code, English-side last-column code) of raw row r (0-based)."""
    row = rows[r]
    return ascii_code(row[0] if row else ""), ascii_code(row[-1] if row else "")


def test_oldbase_sna_code_is_the_hindi_side_code():
    """Full population: every old-base sequence row's printed '[code]' must be the SNA code of the raw row it was
    found in, taken from column A (the Hindi side, correct in every file) or, when A has none, the English code
    column. The census label check only asks that the code appears *somewhere* in the row, which cannot tell
    3.0's shifted pair (A='F2', P='F3') apart. The raw file itself must still show the documented shift."""
    prov = provenance()
    bad, n = [], 0
    for name, rows in datasets().items():
        if "_oldbase_soa_" not in name:
            continue
        for rec in rows:
            m = re.fullmatch(r"(.*) \[([^\]]+)\]", rec["item_label"])
            assert m, rec["item_label"]
            status, info = locate(rec, prov)
            assert status == "ok", (rec["series_id"], rec["period"], info[:2])
            sheet, rc = info[0].split("!")
            r = int(re.match(r"R(\d+)", rc).group(1)) - 1
            a, p = raw_code_columns(workbook(file_key(rec["table_id"]))[sheet], r)
            if sheet == "S3.0" and 91 <= r <= 100:
                p = ""  # inside the shifted block the English column belongs to the row above: A only
            want = a or p or "-"
            n += 1
            slug = re.sub(r"[^a-z0-9]+", "_", want.lower().replace("+", "_plus_")).strip("_")
            if m.group(2) != want:
                bad.append((name, rec["series_id"], rec["period"], rec["item_label"], f"raw A={a!r} P={p!r}"))
            elif want != "-" and rec["item_code"].split(".")[-1] != slug:
                bad.append((name, rec["series_id"], rec["period"], rec["item_code"], f"raw code {want}"))
    assert n == sum(len(v) for k, v in datasets().items() if "_oldbase_soa_" in k)
    assert not bad, (len(bad), bad[:10])
    # the publisher's shift is still in the pinned file (so the unit's exception is not stale)
    rows = workbook("mospi_nas_old_base_2011_12/nas2024_3.0.xlsx")["S3.0"]
    shifted = [k + 1 for k in range(len(rows) - 1) if raw_code_columns(rows, k)[1] and raw_code_columns(rows, k)[1]
               != raw_code_columns(rows, k)[0]]
    assert shifted == list(range(92, 101)), shifted
    assert all(raw_code_columns(rows, k)[1] == raw_code_columns(rows, k + 1)[0] for k in range(91, 100))


def test_oldbase_3_0_liability_anchors():
    """2022-23 anchors read off raw S3.0 rows 92-101 (column N), with the correct (column A) identities."""
    got = {
        r["item_code"]: (r["value"], r["item_label"])
        for r in datasets()["mospi_nas_2026_oldbase_soa_s3_0"]
        if r["period"] == "2022-23" and r["dim_other"] == "account=financial" and r["side"] == "liabilities"
    }
    rows = workbook("mospi_nas_old_base_2011_12/nas2024_3.0.xlsx")["S3.0"]
    want = {  # item code -> (raw row, label start)
        "net_incurrence_of_liabilities": (92, "Net incurrence of liabilities [-]"),
        "f2": (94, "Currency and deposits [F2]"),
        "f3": (95, "Debt Securities [F3]"),
        "f4": (96, "Loans [F4]"),
        "f5": (97, "Equity and investment fund shares [F5]"),
        "f6": (98, "Insurance, pension"),
        "f8": (100, "Other accounts payable [F8]"),
        "b9": (101, "NET LENDING (+) / NET BORROWING (-) [B9]"),
    }
    assert set(got) == set(want), sorted(got)  # F1 and F7 liabilities are blank in raw
    for code, (raw_row, lab) in want.items():
        v = rows[raw_row - 1][13]
        assert abs(got[code][0] - v) < 1e-5 and got[code][1].startswith(lab), (code, got[code], v)
    assert round(got["f2"][0], 1) == 2005617.5 and round(got["b9"][0], 1) == 909872.4


def _soa_by(name: str) -> dict[tuple[str, str, str], dict[str, float]]:
    """(account, side, kind) -> {period: value}, rows identified by their English label (not item code)."""
    out: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    for r in datasets()[name]:
        lab = norm(r["item_label"].rsplit(" [", 1)[0])
        kind = (
            "na" if lab.startswith("net acquisition of financial assets")
            else "ni" if lab.startswith("net incurrence of liabilities")
            else "b9" if lab.startswith("net lending")
            else None
        )
        if kind:
            acct = (r["dim_other"] or "").removeprefix("account=")
            key = (acct, r["side"], kind)
            assert r["period"] not in out[key], (name, key, r["period"])  # no duplicated totals
            out[key][r["period"]] = r["value"]
    return out


def test_oldbase_financial_accounts_close_in_clean():
    """Clean data (all 12 sequences, every year): net acquisition - net incurrence = financial B9 = capital B9.
    Before the verify-1 fix 3.0 failed by -45,36,685 crore (2022-23). Also RoW B9 (6.0) = -total economy B9
    (1.15) every year."""
    bad = []
    names = sorted(k for k in datasets() if "_oldbase_soa_" in k)
    assert len(names) == 12
    for name in names:
        g = _soa_by(name)
        na, ni = g[("financial", "assets", "na")], g[("financial", "liabilities", "ni")]
        b9f, b9c = g[("financial", "liabilities", "b9")], g[("capital", "assets", "b9")]
        assert len(b9f) == 12 and set(na) == set(ni) == set(b9f) == set(b9c), name
        for per in sorted(b9f):
            if abs(na[per] - ni[per] - b9f[per]) > 3 or abs(b9f[per] - b9c[per]) > 3:
                bad.append((name, per, round(na[per] - ni[per] - b9f[per], 1), round(b9f[per] - b9c[per], 1)))
    row = _soa_by("mospi_nas_2026_oldbase_soa_s6_0")[("financial", "liabilities", "b9")]
    tot = _soa_by("mospi_nas_2026_oldbase_soa_s1_15")[("financial", "liabilities", "b9")]
    bad += [("RoW vs total", p, row[p] + tot[p]) for p in tot if abs(row[p] + tot[p]) > 3]
    assert not bad, bad


# ISO 3166-2:IN (my own list). Where the code set is disputed across units (issue mospi_nas_2026-26: IN-CT/IN-CG,
# IN-TS/IN-TG, IN-UK/IN-UT) both spellings are accepted; the choice is an orchestrator decision.
ISO_IN = {
    "andhra pradesh": {"IN-AP"}, "arunachal pradesh": {"IN-AR"}, "assam": {"IN-AS"}, "bihar": {"IN-BR"},
    "chhattisgarh": {"IN-CT", "IN-CG"}, "delhi": {"IN-DL"}, "goa": {"IN-GA"}, "gujarat": {"IN-GJ"},
    "haryana": {"IN-HR"}, "himachal pradesh": {"IN-HP"}, "jammu and kashmir": {"IN-JK"}, "jharkhand": {"IN-JH"},
    "karnataka": {"IN-KA"}, "kerala": {"IN-KL"}, "madhya pradesh": {"IN-MP"}, "maharashtra": {"IN-MH"},
    "manipur": {"IN-MN"}, "meghalaya": {"IN-ML"}, "mizoram": {"IN-MZ"}, "nagaland": {"IN-NL"},
    "odisha": {"IN-OD"}, "puducherry": {"IN-PY"}, "punjab": {"IN-PB"}, "rajasthan": {"IN-RJ"},
    "sikkim": {"IN-SK"}, "tamilnadu": {"IN-TN"}, "tamil nadu": {"IN-TN"}, "telangana": {"IN-TS", "IN-TG"},
    "tripura": {"IN-TR"}, "uttar pradesh": {"IN-UP"}, "uttarakhand": {"IN-UK", "IN-UT"}, "west bengal": {"IN-WB"},
}


def test_4_1_state_rows_carry_their_own_iso_code():
    """Every 4.1 row named after a State/UT carries that State's ISO code; every other row is IN; codes are
    unique per State; the 31 States in raw 4.1 are all present."""
    rows = datasets()["mospi_nas_2026_s4_1"]
    bad, seen = [], defaultdict(set)
    for r in rows:
        lab = norm(r["item_label"])
        want = ISO_IN.get(lab, {"IN"})
        if r["geography"] not in want:
            bad.append((r["series_id"], r["period"], r["geography"], sorted(want)))
        if lab in ISO_IN:
            seen[r["geography"]].add(lab)
    assert not bad, bad[:10]
    assert all(len(v) == 1 for v in seen.values()), seen
    raw = workbook(file_key(rows[0]["table_id"]))
    raw_states = {
        norm(t) for rws in raw.values() for row in rws for t in row_texts(row) if norm(t) in ISO_IN
    }
    assert len(raw_states) == 31 and raw_states == set().union(*seen.values()), raw_states ^ set().union(*seen.values())


INST_BY_LABEL = {  # my own map, from the raw 1.9 / 1.11 labels
    "non financial corporations": "nfc", "financial corporations": "fc",
    "public non financial corporations": "nfc_public", "private non financial corporations": "nfc_private",
    "public financial corporations": "fc_public", "private financial corporations": "fc_private",
    "general government": "gg", "household sector": "households_npish",
}
LEAF = {"nfc_public", "nfc_private", "fc_public", "fc_private", "gg", "households_npish"}


def test_1_9_and_1_11_institutions():
    """Sector rows carry the sector named by their own label; sub-rows carry none or their parent's sector;
    the six leaf sectors add up to the total in every period / price basis (no double tagging), and the 1.11
    percentage shares add up to 100."""
    bad = []
    for ds, total in (
        ("mospi_nas_2026_s1_9", "gross savings"),
        ("mospi_nas_2026_s1_11", "gross fixed capital formation"),
    ):
        lev, pct, tot = defaultdict(float), defaultdict(float), {}
        for r in datasets()[ds]:
            segs = r["item_code"].split(".")
            lab = strip_serial(norm(r["item_label"]))
            if segs[0] == "pct_share" or len(segs) == 1:
                want = INST_BY_LABEL.get(lab)
            else:  # a sub-row: none, or the sector of its parent heading (1.9 items 1.1.1.1-2)
                parent = segs[-2].replace("_", " ")
                want = r["institution"] if r["institution"] in (None, f"{INST_BY_LABEL.get(parent)}_de",
                                                                f"{INST_BY_LABEL.get(parent)}_nde") else "?"
                if r["institution"] and not r["institution"].endswith(
                    "_de" if lab.startswith("departmental") else "_nde"
                ):
                    want = "?"
            if r["institution"] != want:
                bad.append((ds, r["series_id"], r["institution"], want))
            k = (r["period"], r["price_basis"])
            if r["institution"] in LEAF:
                (pct if r["unit"] == "percent" else lev)[k] += r["value"]
            if lab == total and len(segs) == 1:
                tot[k] = r["value"]
        assert tot and set(tot) == set(lev), ds
        bad += [(ds, k, lev[k], tot[k]) for k in tot if abs(lev[k] - tot[k]) > 0.5]
        bad += [(ds, k, "pct", v) for k, v in pct.items() if abs(v - 100) > 0.05]
    assert not bad, bad[:10]


def test_less_items_are_documented():
    """Every dataset whose raw workbook has a 'Less'-captioned data row says in its description that such items
    are stored as positive magnitudes (verify-4); and every such clean value has the raw sign (census covers)."""
    import json

    desc = json.loads((CLEAN / "_datasets.json").read_text(encoding="utf-8"))
    by_key = defaultdict(set)
    for name, rows in stmt_datasets().items():  # API imports: test_api_imports_positive_and_documented
        for r in rows:
            if r["status"] != "derived":
                by_key[file_key(r["table_id"])].add(name)
    missing, n = [], 0
    for key, names in by_key.items():
        has_less = any(
            re.match(r"(?i)^less\b", strip_serial(eng(x)).strip())
            and any(is_num(v) and abs(v) > 3000 for v in row)
            for rows in workbook(key).values()
            for row in rows
            for x in row
            if isinstance(x, str)
        )
        if has_less:
            for name in names:
                n += 1
                d = desc[name]
                text = d.get("description", "") if isinstance(d, dict) else str(d)
                if "positive magnitude" not in text:
                    missing.append(name)
    assert n >= 16 and not missing, (n, missing)


# ======================================================================================== close-out pass
# NAS API datasets (mospi_nas_api) and the old-base stage relabel. My own reader: every pinned JSON page is read
# with the json module after its sha256 is checked against the pin (raw_path); nothing is imported from
# pipeline.ingest.mospi_nas_2026.api. Records are matched to clean rows by indicator, year, quarter, revision
# round and the printed industry / sub-industry / sector labels; dims are checked against my own maps.
API_TABLE = re.compile(r"NAS API getNASData indicator (\d+)")
PAGE_RE = re.compile(r"mospi_nas_api/nasapi_(b\d{4}_(?:back|current)_[aq])_i(\d\d)_p(\d\d)\.json")
API_TAG = {  # dataset (unit prefix removed) -> (page-name tag, base year); from the pinned file names
    "api_b2011_back": ("b2011_back_a", "2011-12"),
    "api_b2011_annual": ("b2011_current_a", "2011-12"),
    "api_b2011_quarterly": ("b2011_current_q", "2011-12"),
    "api_b2022_annual": ("b2022_current_a", "2022-23"),
    "api_b2022_quarterly": ("b2022_current_q", "2022-23"),
}
TAG_QUERY = {  # page-name tag -> (base_year, series, frequency) every record on those pages must carry
    "b2011_back_a": ("2011-12", "Back", "Annual"),
    "b2011_current_a": ("2011-12", "Current", "Annual"),
    "b2011_current_q": ("2011-12", "Current", "Quarterly"),
    "b2022_current_a": ("2022-23", "Current", "Annual"),
    "b2022_current_q": ("2022-23", "Current", "Quarterly"),
    "b2022_back_a": ("2022-23", "Back", "Annual"),
}
REV = {  # API revision round -> schema estimate_stage (PIPELINE_GUIDE s.5 vocabulary)
    "First Advance Estimates": "FAE",
    "Second Advance Estimates": "SAE",
    "Provisional Estimates": "PE",
    "First Revised Estimates": "FRE",
    "Second Revised Estimates": "SRE",
    "Third Revised Estimates": "TRE",
    "Final Estimates": "Final",
    "Additional Revision": "Revised",  # the only generic 'revised' stage in the vocabulary
}
API_BLANK = (None, "", "nan", "NaN")
API_COUNTS = {  # builder's reported row counts (issues file header); re-counted from raw in the reverse sweep
    "api_b2011_back": 5344, "api_b2011_annual": 7160, "api_b2011_quarterly": 2084,
    "api_b2022_annual": 575, "api_b2022_quarterly": 612,
}
API_IND_EXTRA = {  # API industry labels my workbook map (IND) does not cover
    "total gross value added": "total",
    "total gross capital formation": "total",
    "transport by other means": "transport_other_means",  # back series 1950-51..2003-04 only
}
SEC_LEAF = ("nfc_public", "nfc_private", "fc_public", "fc_private", "gg", "households_npish")


@cache
def api_pages() -> dict[tuple[str, int], list[tuple[str, dict]]]:
    """(tag, indicator) -> [(pin key, page JSON)] in page order."""
    out: dict[tuple[str, int], dict[int, tuple[str, dict]]] = defaultdict(dict)
    for key in pins():
        m = PAGE_RE.fullmatch(key)
        if m:
            doc = json.loads(raw_path(key).read_text(encoding="utf-8"))
            out[(m.group(1), int(m.group(2)))][int(m.group(3))] = (key, doc)
    return {k: [v[p] for p in sorted(v)] for k, v in out.items()}


def api_period(rec: dict) -> str | None:
    """'2011-12' -> '2011-12', '1999-2000' -> '1999-00'; quarter prefixed; None for a non-fiscal-year label."""
    y = str(rec.get("year") or "")
    f = fy_tokens(y) if re.fullmatch(r"(?:19|20)\d\d-(?:\d\d|(?:19|20)\d\d)", y) else []
    if len(f) != 1:
        return None
    return f"{rec['quarter']} {f[0]}" if rec.get("quarter") else f[0]


def rec_labels(rec: dict) -> list[str]:
    return [rec["indicator"]] + [rec[k] for k in ("industry", "subindustry", "institutional_sector", "revision")
                                 if rec.get(k)]


def api_value(rec: dict, basis: str, base: str) -> float | None:
    field = {"current": "current_price", f"constant_{base.replace('-', '_')}": "constant_price"}.get(basis)
    v = rec.get(field) if field else None
    return None if v in API_BLANK else float(v)


@cache
def api_index() -> dict[tuple[str, int, str], list[tuple[str, dict]]]:
    idx = defaultdict(list)
    for (tag, ind), pages in api_pages().items():
        for key, doc in pages:
            for rec in doc.get("data") or []:
                per = api_period(rec)
                if per:
                    idx[(tag, ind, per)].append((key, rec))
    return idx


def api_industry_code(label: str) -> str:
    n = strip_serial(norm(label))
    if n in API_IND_EXTRA:
        return API_IND_EXTRA[n]
    hits = [k for k, p in IND.items() if re.fullmatch(p, n)]
    return hits[0] if len(hits) == 1 else f"?{n}:{hits}"


def api_sector_code(label: str) -> str:
    n = strip_serial(norm(label))
    if n.startswith("total "):
        return "total_economy"  # 'Total Gross Value Added' / 'Total Consumption of Fixed Capital' / ...
    hits = [k for k in SEC_LEAF if re.fullmatch(INST[k], n)]
    return hits[0] if len(hits) == 1 else f"?{n}:{hits}"


def rev_slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def api_context_problems(row: dict, rec: dict, key: str, tag: str, base: str, prov: dict) -> list[str]:
    why = []
    if (rec["base_year"], rec["series"], rec["frequency"]) != TAG_QUERY[tag]:
        why.append(f"record from another query {rec['base_year'], rec['series'], rec['frequency']}")
    if rec.get("unit") != "₹ Crore" or row["unit"] != "INR_crore":
        why.append(f"unit {rec.get('unit')!r} / {row['unit']}")
    ind_lab = rec.get("subindustry") or rec.get("industry")
    want = {
        "industry": api_industry_code(ind_lab) if ind_lab else None,
        "institution": api_sector_code(rec["institutional_sector"]) if rec.get("institutional_sector") else None,
        "dim_other": f"revision={rev_slug(rec['revision'])}" if rec.get("revision") else None,
        "estimate_stage": REV.get(rec.get("revision"), "?") if rec.get("revision") else "n.a.",
        "period_type": "fq" if rec.get("quarter") else "fy",
        "geography": "IN", "product": None, "instrument": None, "counterparty": None, "household_group": None,
        "side": None, "stock_flow": "flow", "base_year": base, "source_id": "mospi_nas_api", "status": "official",
        "vintage": pins()[key]["retrieved_at"][:10],
    }
    for f, w in want.items():
        if row.get(f) != w:
            why.append(f"{f} {row.get(f)!r} != {w!r}")
    sid = row["series_id"]
    if not sid.endswith("." + row["price_basis"]) or (rec.get("revision") and f".rev_{rev_slug(rec['revision'])}."
                                                       not in sid):
        why.append(f"series_id {sid} does not carry the round / price basis")
    if prov[row["prov_id"]]["raw_path"].replace("\\", "/") != pins()[key]["path"]:
        why.append(f"prov page {prov[row['prov_id']]['raw_path']} is not the page holding the record")
    return why


def api_locate(row: dict, prov: dict) -> tuple[str, list[str]]:
    """Keyed route: the raw records of the row's query / indicator / period whose printed labels equal the row's
    label parts; accept if one has the same number in the row's price field and agrees on every context field."""
    tag, base = API_TAG[row["dataset"].removeprefix(f"{UNIT}_")]
    ind = int(API_TABLE.fullmatch(row["table_id"]).group(1))
    want = [norm(p) for p in row["item_label"].split(" | ")]
    reasons, hits = [], []
    for key, rec in api_index().get((tag, ind, row["period"]), []):
        if [norm(x) for x in rec_labels(rec)] != want:
            continue
        v = api_value(rec, row["price_basis"], base)
        if v is None:
            reasons.append(f"{key}: blank / no field for {row['price_basis']}")
            continue
        if abs(v - row["value"]) > 1e-6:
            reasons.append(f"{key}: raw value {v}")
            continue
        why = api_context_problems(row, rec, key, tag, base, prov)
        if why:
            reasons.append(f"{key}: " + "; ".join(why))
            continue
        hits.append(key)
    return ("ok", hits) if hits else ("fail", reasons or ["no raw record with these labels and period"])


def api_search(row: dict, prov: dict) -> bool:
    """Search route (independent of api_index): scan every record on every page of the row's query and indicator
    for the row's number in the row's price field; accept if one such record has the row's period and labels
    and agrees on every context field."""
    tag, base = API_TAG[row["dataset"].removeprefix(f"{UNIT}_")]
    ind = int(API_TABLE.fullmatch(row["table_id"]).group(1))
    for key, doc in api_pages()[(tag, ind)]:
        for rec in doc["data"]:
            v = api_value(rec, row["price_basis"], base)
            if v is None or abs(v - row["value"]) > 1e-6:
                continue
            if api_period(rec) != row["period"] or " ".join(" | ".join(rec_labels(rec)).split()) != " ".join(
                row["item_label"].split()
            ):
                continue
            if not api_context_problems(row, rec, key, tag, base, prov):
                return True
    return False


def api_rows() -> list[dict]:
    return [r for name, rows in sorted(datasets().items()) if is_api(name) for r in rows]


def api_sample() -> list[dict]:
    rng = random.Random(SEED + 35)
    out = []
    for name, rows in sorted(datasets().items()):
        if is_api(name):
            n = min(len(rows), max(30, math.ceil(0.10 * len(rows))))
            out += [rows[i] for i in sorted(rng.sample(range(len(rows)), n))]
    return out


def test_api_pages_complete_and_pinned():
    """Every API page is pinned (sha256 checked on read), pagination is complete (page i of n, 200 records per
    page, totalRecords = records served), every record belongs to its page's query, and the new-base back-series
    probe still answers 'No Data Found' (issue mospi_nas_2026-7)."""
    pages = api_pages()
    assert sum(len(v) for v in pages.values()) == 105  # + the indicator list = the builder's 106 pages
    assert "mospi_nas_api/nasapi_indicator_list.json" in pins()
    want_q = {("b2011_back_a", i) for i in range(1, 21)} | {("b2011_current_a", i) for i in range(1, 21)}
    want_q |= {("b2022_current_a", i) for i in range(1, 21)} | {("b2022_back_a", 5)}
    want_q |= {(t, i) for t in ("b2011_current_q", "b2022_current_q") for i in (1, 2, 5, 9, 10, 11, 12, 13, 14, 15)}
    assert set(pages) == want_q, set(pages) ^ want_q
    for (tag, ind), pl in pages.items():
        base, series, freq = TAG_QUERY[tag]
        if tag == "b2022_back_a" or (tag, ind) in (("b2011_back_a", 3), ("b2011_back_a", 4)):
            # the new-base back-series probe (issue 7) and the old-base back series of taxes / subsidies on products
            assert len(pl) == 1 and pl[0][1]["data"] == [] and pl[0][1]["msg"] == "No Data Found", pl
            continue
        total = sum(len(d["data"]) for _, d in pl)
        for i, (key, d) in enumerate(pl, 1):
            meta = d["meta_data"]
            assert (meta["page"], meta["totalPages"], meta["totalRecords"], meta["recordPerPage"]) == (
                i, len(pl), total, 200), (key, meta)
            assert len(d["data"]) == (200 if i < len(pl) else total - 200 * (len(pl) - 1)), key
            url = pins()[key]["url"]
            for part in (f"base_year={base}", f"series={series}", f"indicator_code={ind}&", "limit=200",
                         f"page={i}", f"frequency_code={'Annually' if freq == 'Annual' else 'Quarterly'}"):
                assert part in url, (key, part)
            assert all((r["base_year"], r["series"], r["frequency"]) == (base, series, freq) for r in d["data"]), key
            assert all(r.get("quarter") in ((None,) if freq == "Annual" else ("Q1", "Q2", "Q3", "Q4"))
                       for r in d["data"]), key
            assert not any(r.get("state") for r in d["data"]), key
    ilist = json.loads(raw_path("mospi_nas_api/nasapi_indicator_list.json").read_text(encoding="utf-8"))["data"]
    names = {int(i["indicator_code"]): i["description"] for i in ilist["indicator"]}
    assert set(names) == set(range(1, 23)) and all("Growth Rate" in names[i] for i in (21, 22)), names


def test_api_census_every_row_against_raw_json():
    """Full population: every one of the 15,775 API rows is found in its raw page with the same number, labels,
    period, round, price basis, dims, stage, vintage and provenance page."""
    prov = provenance()
    counts = Counter(r["dataset"].removeprefix(f"{UNIT}_") for r in api_rows())
    assert counts == API_COUNTS, counts
    bad = []
    for r in api_rows():
        st, info = api_locate(r, prov)
        if st != "ok":
            bad.append((r["dataset"], r["series_id"], r["period"], r["value"], info[:2]))
    assert not bad, (len(bad), bad[:10])


def test_api_spotcheck_sample_by_value_search():
    """Seeded sample (>= 10% and >= 30 rows of each API dataset), located by searching the raw pages for the
    number rather than by key (a second route to the census above)."""
    prov = provenance()
    s = api_sample()
    assert len(s) >= 0.10 * len(api_rows()) and {r["dataset"] for r in s} == {f"{UNIT}_{k}" for k in API_TAG}
    assert all(sum(r["dataset"] == f"{UNIT}_{k}" for r in s) >= 30 for k in API_TAG)
    bad = [(r["dataset"], r["series_id"], r["period"], r["value"]) for r in s if not api_search(r, prov)]
    assert not bad, (len(bad), bad[:10])


def test_api_checker_rejects_mutations():
    """Self-test of the API checker: another value, another series' value, another period, the other price basis,
    another stage, another industry and another vintage must all be rejected."""
    prov = provenance()
    rng = random.Random(SEED + 36)
    recs = api_sample()
    rng.shuffle(recs)
    by_ds = defaultdict(list)
    for r in api_rows():
        by_ds[r["dataset"]].append(r)
    leaks, tried = [], 0
    for rec in recs[:300]:
        rows = by_ds[rec["dataset"]]
        muts = [dict(rec, value=rec["value"] + 1), dict(rec, vintage="2026-08-31"),
                dict(rec, estimate_stage="TRE" if rec["estimate_stage"] != "TRE" else "SRE")]
        others = [r for r in rows if r["period"] == rec["period"] and r["price_basis"] == rec["price_basis"]
                  and r["series_id"] != rec["series_id"] and abs(r["value"] - rec["value"]) > 1e-3]
        if others:
            muts.append(dict(rec, value=rng.choice(others)["value"]))
        pers = sorted({r["period"] for r in rows if r["series_id"] == rec["series_id"]
                       and abs(r["value"] - rec["value"]) > 1e-3})
        if pers:
            muts.append(dict(rec, period=rng.choice(pers)))
        alt = [r for r in rows if r["item_label"] == rec["item_label"] and r["period"] == rec["period"]
               and r["price_basis"] != rec["price_basis"] and abs(r["value"] - rec["value"]) > 1e-3]
        if alt:
            muts.append(dict(rec, price_basis=alt[0]["price_basis"]))
        if rec["industry"]:
            muts.append(dict(rec, industry="manufacturing" if rec["industry"] != "manufacturing" else "mining"))
        for m in muts:
            tried += 1
            if api_locate(m, prov)[0] == "ok" or api_search(m, prov):
                leaks.append((rec["series_id"], rec["period"], m["value"], m["period"], m["price_basis"]))
    assert tried > 1200 and not leaks, (tried, leaks[:10])


def test_api_every_raw_record_is_ingested_or_a_documented_skip():
    """Reverse sweep over all raw records. The only values not in clean data must be exactly the documented skips:
    indicators 3/4 (served as '₹ Lakh', issue 31), one GNDI record dated '1999' that repeats the 2025-26 FAE
    (issue 32a), two exact duplicate quarterly records (32b), and blank prices (null / 'nan', 32c)."""
    clean: dict[tuple, list[float]] = defaultdict(list)
    for r in api_rows():
        tag, _ = API_TAG[r["dataset"].removeprefix(f"{UNIT}_")]
        ind = int(API_TABLE.fullmatch(r["table_id"]).group(1))
        role = "ind" if r["industry"] else "sec" if r["institution"] else "-"  # GVA totals: same label, two roles
        clean[(tag, ind, r["period"], " ".join(r["item_label"].split()), role, r["price_basis"])].append(r["value"])
    assert all(len(v) == 1 for v in clean.values())
    missing, lakh, nonfy, dups, blanks, ingested = [], [], [], [], Counter(), 0
    seen: dict[tuple, dict] = {}
    for (tag, ind), pages in sorted(api_pages().items()):
        base = TAG_QUERY[tag][0]
        for key, doc in pages:
            for rec in doc["data"]:
                if ind in (3, 4):
                    lakh.append(rec)
                    continue
                per = api_period(rec)
                if per is None:
                    nonfy.append((tag, ind, rec))
                    continue
                role = "ind" if rec.get("industry") else "sec" if rec.get("institutional_sector") else "-"
                ident = (tag, ind, per, " ".join(" | ".join(rec_labels(rec)).split()), role)
                if ident in seen:
                    dups.append((ident, seen[ident] == rec))
                    continue
                seen[ident] = rec
                con = f"constant_{base.replace('-', '_')}"
                for basis, f in (("current", "current_price"), (con, "constant_price")):
                    if rec[f] in API_BLANK:
                        blanks[repr(rec[f])] += 1
                        continue
                    ingested += 1
                    got = clean.get((*ident, basis), [])
                    if not any(abs(v - float(rec[f])) < 1e-6 for v in got):
                        missing.append((key, ident, basis, rec[f], got))
    assert not missing, (len(missing), missing[:10])
    assert ingested == sum(API_COUNTS.values()) == 15775
    # 32a: the only non-fiscal-year record
    assert len(nonfy) == 1, nonfy
    tag, ind, bogus = nonfy[0]
    assert (tag, ind, bogus["year"], bogus["revision"], bogus["constant_price"]) == (
        "b2011_current_a", 19, "1999", "First Advance Estimates", None)
    fae = [r for _, r in api_index()[("b2011_current_a", 19, "2025-26")] if r["revision"] == "First Advance Estimates"]
    assert len(fae) == 1 and fae[0]["current_price"] == bogus["current_price"] == "36204793"
    # 32b: exactly two exact duplicates, 2019-20 agriculture Q1 and Q3 (old-base quarterly GVA)
    assert [d[0] for d in dups] == [
        ("b2011_current_q", 1, "Q1 2019-20", "Gross Value Added | Agriculture, Livestock, Forestry and Fishing", "ind"),
        ("b2011_current_q", 1, "Q3 2019-20", "Gross Value Added | Agriculture, Livestock, Forestry and Fishing", "ind"),
    ] and all(same for _, same in dups), dups
    # 31: all 74 lakh-labelled records are skipped whole (none in clean)
    assert len(lakh) == 74 and {r["unit"] for r in lakh} == {"₹ Lakh"}
    assert not [r for r in api_rows() if r["table_id"] in ("NAS API getNASData indicator 3",
                                                           "NAS API getNASData indicator 4")]
    assert set(blanks) <= {"None", "'nan'"}, blanks


def test_api_lakh_label_is_a_label_error():
    """Issue 31 re-derived: in every record of indicators 3/4 ('₹ Lakh'), taxes - subsidies = net taxes on
    products (indicator 2, '₹ Crore') within API truncation, so the values are crore; and the new-base API
    taxes / subsidies equal NAS 2026 Statement 1.1 (crore) within 1."""
    def keyed(tag, ind):
        return {(per, r.get("revision")): r for (t, i, per), lst in api_index().items() if (t, i) == (tag, ind)
                for _, r in lst}
    cases = 0
    for tag in ("b2011_current_a", "b2022_current_a"):
        tx, sb, nt = keyed(tag, 3), keyed(tag, 4), keyed(tag, 2)
        assert set(tx) == set(sb) and set(tx) <= set(nt)
        for k in tx:
            for f in ("current_price", "constant_price"):
                if tx[k][f] in API_BLANK:
                    continue
                cases += 1
                assert abs(float(tx[k][f]) - float(sb[k][f]) - float(nt[k][f])) <= 2, (tag, k, f)
    assert cases >= 74, cases
    s11 = {(r["item_code"], r["period"], r["price_basis"]): r["value"] for r in datasets()["mospi_nas_2026_s1_1"]}
    for ind, code in ((3, "taxes_on_products"), (4, "subsidies_on_products")):
        for (per, _), r in keyed("b2022_current_a", ind).items():
            assert abs(float(r["current_price"]) - s11[(code, per, "current")]) < 1, (ind, per)


NEW_BASE_MAP = {  # API indicator -> NAS 2026 1.1 / 8.17.1 item code (my map, from the two statements' labels)
    1: "gva_basic", 2: "net_taxes_on_products", 5: "gdp", 6: "cfc", 7: "ndp", 9: "gfcf", 10: "pfce", 11: "gfce",
    12: "cis", 13: "valuables", 14: "exports", 15: "imports", 16: "primary_income_row_net", 17: "gni",
    18: "other_current_transfers_row_net", 19: "gndi", 20: "gross_saving",
}


def national_total(rec: dict) -> bool:
    ind, sec = rec.get("industry") or "", rec.get("institutional_sector") or ""
    return not rec.get("subindustry") and (not ind or ind.startswith("Total")) and (not sec or sec.startswith("Total"))


def test_api_new_base_equals_nas_2026_statements():
    """The builder's cross-check, redone from raw and extended to the totals its own test filters out (industry /
    sector 'Total' rows: GVA, CFC, GFCF, saving): every whole-economy new-base API figure equals NAS 2026 1.1 or
    8.17.1 within 0.5 crore, with the same stage. Indicator 8 ('GCF by industry of use') is GFCF + CIS, i.e. NOT
    the 1.1 GCF (which adds valuables): checked separately."""
    nas = {}
    for ds in ("mospi_nas_2026_s1_1", "mospi_nas_2026_s8_17_1"):
        for r in datasets()[ds]:
            nas.setdefault((r["item_code"], r["period"], r["price_basis"]), (r["value"], r["estimate_stage"]))
    s11 = {k: v[0] for k, v in nas.items()}
    for (code, per, pb) in [k for k in s11 if k[0] == "taxes_on_products"]:
        nas.setdefault(("net_taxes_on_products", per, pb),
                       (s11[(code, per, pb)] - s11[("subsidies_on_products", per, pb)], nas[(code, per, pb)][1]))
    n, bad = 0, []
    for (tag, ind, per), lst in api_index().items():
        if tag != "b2022_current_a" or ind not in NEW_BASE_MAP | {8: None}:
            continue
        for _, rec in lst:
            if not national_total(rec):
                continue
            for pb in ("current", "constant_2022_23"):
                v = api_value(rec, pb, "2022-23")
                if v is None:
                    continue
                n += 1
                if ind == 8:
                    want = s11[("gfcf", per, pb)] + s11[("cis", per, pb)]
                    if abs(v - want) > 1 or abs(v - s11[("gcf", per, pb)]) < 1e4:
                        bad.append(("gcf_by_industry_of_use", per, pb, v, want))
                    continue
                w = nas.get((NEW_BASE_MAP[ind], per, pb))
                if w is None or abs(v - w[0]) > 0.5 or REV[rec["revision"]] != w[1]:
                    bad.append((ind, per, pb, rec.get("industry") or rec.get("institutional_sector"), v, w))
    assert n >= 130 and not bad, (n, bad[:10])


def test_api_quarters_add_up_to_annual():
    """New base: for every quarterly indicator, both price bases and all four complete years, Q1..Q4 add up to
    the annual whole-economy figure within 2 crore (four API-rounded quarters; the builder's 'within 1' holds for
    GDP; current-price imports differ by 2). Q1 2026-27 GDP is present."""
    worst, blank = {}, Counter()
    for (tag, ind, per), lst in api_index().items():
        if tag != "b2022_current_a":
            continue
        ann = [r for _, r in lst if national_total(r)]
        if ind not in (1, 2, 5, 9, 10, 11, 12, 13, 14, 15) or not ann:
            continue
        for f in ("current_price", "constant_price"):
            qs = [r[f] for q in ("Q1", "Q2", "Q3", "Q4")
                  for _, r in api_index().get(("b2022_current_q", ind, f"{q} {per}"), []) if national_total(r)]
            if any(x in API_BLANK for x in qs):
                blank[(ind, f)] += 1
                continue
            av = {float(r[f]) for r in ann if r[f] not in API_BLANK}  # GVA: served as industry and sector total
            assert len(qs) == 4 and len(av) == 1, (ind, per, f, qs, av)
            worst[(ind, per, f)] = abs(sum(float(x) for x in qs) - av.pop())
    top = sorted(worst.items(), key=lambda kv: -kv[1])[:5]
    assert not blank and len(worst) == 10 * 4 * 2 and max(worst.values()) <= 2, top
    assert max(v for (i, _, _), v in worst.items() if i == 5) <= 1
    q1 = [r for _, r in api_index()[("b2022_current_q", 5, "Q1 2026-27")]]
    assert len(q1) == 1 and q1[0]["current_price"] == "8826871"


def test_api_back_series_identities_and_additivity():
    """Issue 33 re-derived from raw: GDP = GVA + net taxes, NDP = GDP - CFC, GNI = GDP + net primary income from
    RoW in every year 1950-51..2011-12 at both price bases (within 2, API rounding); the 11 industries add up to
    total GVA within 11 crore from 2004-05 only, and not before (gap up to about 1 lakh crore)."""
    def series(ind, f, industry_filter=None):
        """National total per year (one value: GVA is served both as industry 'Total ...' and with no industry in
        some years, always equal), or with industry_filter the sum of the matching records."""
        out: dict[str, set | float] = defaultdict(set) if industry_filter is None else defaultdict(float)
        for (tag, i, per), lst in api_index().items():
            if (tag, i) == ("b2011_back_a", ind):
                for _, r in lst:
                    if (industry_filter or national_total)(r) and r[f] not in API_BLANK:
                        if industry_filter is None:
                            out[per].add(float(r[f]))
                        else:
                            out[per] += float(r[f])
        if industry_filter is None:
            # 3 years (1988-89, 1997-98, 1998-99, current prices) serve the two GVA totals 1 crore apart
            spread = {p: v for p, v in out.items() if len(v) > 1}
            assert all(max(v) - min(v) <= 1 for v in out.values()), (ind, f, spread)
            return {p: min(v) for p, v in out.items()}
        return dict(out)
    bad = []
    for f in ("current_price", "constant_price"):
        gva, nt, gdp, cfc, ndp = (series(i, f) for i in (1, 2, 5, 6, 7))
        npi, gni = series(16, f), series(17, f)
        assert len(gdp) == 62 and min(gdp) == "1950-51" and max(gdp) == "2011-12"
        for p in gdp:
            for name, d in (("gdp", gdp[p] - gva[p] - nt[p]), ("ndp", ndp[p] - gdp[p] + cfc[p])):
                if abs(d) > 2:
                    bad.append((f, p, name, d))
            if p in gni and abs(gni[p] - gdp[p] - npi[p]) > 2:
                bad.append((f, p, "gni", gni[p] - gdp[p] - npi[p]))
        inds = series(1, f, lambda r: bool(r.get("industry")) and not r.get("subindustry")
                      and not r["industry"].startswith("Total"))
        gap = {p: inds[p] - gva[p] for p in gva}
        assert all(abs(v) <= 11 for p, v in gap.items() if p >= "2004-05"), f
        assert all(abs(v) > 11 for p, v in gap.items() if p < "2004-05"), f
        if f == "constant_price":
            assert 5e4 < max(abs(v) for v in gap.values()) < 2e5  # 'up to about 1 lakh crore'
    assert not bad, bad[:10]


def test_api_imports_positive_and_documented():
    """API imports are positive magnitudes (to be subtracted), and every API dataset holding them says so."""
    desc = json.loads((CLEAN / "_datasets.json").read_text(encoding="utf-8"))
    imp = [r for r in api_rows() if r["table_id"] == "NAS API getNASData indicator 15"]
    assert imp and all(r["value"] > 0 for r in imp)
    for name in {r["dataset"] for r in imp}:
        d = desc[name]
        assert "positive magnitude" in (d.get("description", "") if isinstance(d, dict) else str(d)), name


def test_api_gcf_by_industry_of_use_has_its_own_item_code():
    """Close-out c-1, fixed (final pass; was a strict xfail). A join on item_code must not mix three concepts:
    1.1 GCF (GFCF + CIS + valuables; old base also errors and omissions), API current-series 'GCF by industry of
    use' (GFCF + CIS, e.g. new base 2023-24 96,28,092 vs 1.1 GCF 1,00,04,323) and the API back series (2011-12
    34,03,008 = old 1.1 GCF, vs the current series' 2011-12 'Additional Revision' total 32,05,716).
    Now: current series (both bases) 'gcf_excl_valuables', the code NAS 2026 Statement 7.2 uses for the same
    concept; back series 'gcf_incl_errors_omissions', used nowhere else. Each code is grounded in raw JSON here:
    every current-series whole-economy total = GFCF + CIS of the same round and price field within 3 (74 cases),
    and never + valuables; every back-series year differs from GFCF + CIS + valuables by 14 crore or more (62 years,
    both price fields); a key join of the new-base rows with 7.2 matches all 150 cells within 0.5."""
    ind8 = "NAS API getNASData indicator 8"
    got, n8 = defaultdict(set), Counter()
    for r in api_rows():
        if r["table_id"] == ind8:
            ds = r["dataset"].removeprefix(f"{UNIT}_")
            got[ds].add(r["item_code"])
            n8[ds] += 1
            assert r["series_id"].startswith(f"api.{r['item_code']}."), r["series_id"]
    assert dict(got) == {"api_b2011_back": {"gcf_incl_errors_omissions"}, "api_b2011_annual": {"gcf_excl_valuables"},
                         "api_b2022_annual": {"gcf_excl_valuables"}}, dict(got)
    assert dict(n8) == {"api_b2011_back": 124, "api_b2011_annual": 1700, "api_b2022_annual": 150}, dict(n8)
    for name, rows in datasets().items():
        codes = {r["item_code"] for r in rows}
        if is_api(name):
            assert "gcf" not in codes, name
        else:
            assert "gcf_incl_errors_omissions" not in codes, name
            if "gcf_excl_valuables" in codes:  # only the 7.2 family, labelled 'GCF*' (excl. valuables)
                assert re.fullmatch(rf"{UNIT}_s7_2[a-c]?", name), name

    def tot(tag: str, ind: int) -> dict[tuple, float]:
        out: dict[tuple, float] = {}
        for (t, i, per), lst in api_index().items():
            if (t, i) == (tag, ind):
                for _, rec in lst:
                    for f in ("current_price", "constant_price"):
                        if national_total(rec) and rec[f] not in API_BLANK:
                            k = (per, rec.get("revision"), f)
                            assert abs(out.setdefault(k, float(rec[f])) - float(rec[f])) <= 1, (tag, ind, k)
        return out

    n_cur = 0
    for tag in ("b2011_current_a", "b2022_current_a"):
        g, fc, ci, va = (tot(tag, i) for i in (8, 9, 12, 13))
        assert g and set(g) <= set(fc) & set(ci), tag
        for k, v in g.items():
            n_cur += 1
            assert abs(v - fc[k] - ci[k]) <= 3 and abs(v - fc[k] - ci[k] - va[k]) > 1e5, (tag, k, v)
    assert n_cur == 74, n_cur  # year x round x price field: old base 68, new base 6
    g, fc, ci, va = (tot("b2011_back_a", i) for i in (8, 9, 12, 13))
    assert len(g) == 124 and all(abs(v - fc[k] - ci[k] - va.get(k, 0.0)) >= 14 for k, v in g.items())
    assert g[("2011-12", None, "current_price")] == 3403008 and g[("2011-12", None, "current_price")] - fc[
        ("2011-12", None, "current_price")] - ci[("2011-12", None, "current_price")] - va[
        ("2011-12", None, "current_price")] == -55740

    key = ("item_code", "industry", "period", "price_basis", "estimate_stage")
    s72 = {tuple(r[k] for k in key): r["value"] for r in datasets()[f"{UNIT}_s7_2"]
           if r["item_code"] == "gcf_excl_valuables"}
    api22 = [r for r in datasets()[f"{UNIT}_api_b2022_annual"] if r["table_id"] == ind8]
    miss = [r["series_id"] for r in api22 if abs(r["value"] - s72.get(tuple(r[k] for k in key), math.inf)) > 0.5]
    assert len(api22) == len(s72) == 150 and not miss, (len(api22), len(s72), miss[:5])


def test_api_gcf_concepts_differ_between_back_and_current_series():
    """Evidence for c-1 from raw: back-series indicator 8 (2011-12) equals old NAS 2025 1.1 GCF within 1, while
    the current series' 2011-12 total equals GFCF + CIS of the same round within 1."""
    back = [r for _, r in api_index()[("b2011_back_a", 8, "2011-12")] if national_total(r)]
    cur = {r["revision"]: r for _, r in api_index()[("b2011_current_a", 8, "2011-12")] if national_total(r)}
    old11 = {(r["item_code"], r["price_basis"]): r["value"] for r in datasets()["mospi_nas_2026_oldbase_nas2025_s1_1"]
             if r["period"] == "2011-12"}
    assert len(back) == 1 and abs(float(back[0]["current_price"]) - old11[("gcf", "current")]) < 1
    gfcf = {r["revision"]: r for _, r in api_index()[("b2011_current_a", 9, "2011-12")] if national_total(r)}
    cis = {r["revision"]: r for _, r in api_index()[("b2011_current_a", 12, "2011-12")] if national_total(r)}
    rd = "Additional Revision"
    c, g, k = (float(x[rd]["current_price"]) for x in (cur, gfcf, cis))
    assert abs(c - g - k) <= 1, (c, g, k)
    assert float(back[0]["current_price"]) - float(cur[rd]["current_price"]) > 1.5e5  # ~1.97 lakh crore concept gap


# ---- old-base estimate stages (issue mospi_nas_2026-9), re-derived from raw ----------------------------------------
NAS2025_API = {  # NAS 2025 Statement 1.1 item code -> API indicator (GCF left out: different concept, see c-1;
    # taxes / subsidies left out: lakh-labelled indicators)
    "gva_basic": 1, "gdp": 5, "cfc": 6, "ndp": 7, "gfcf": 9, "pfce": 10, "gfce": 11, "cis": 12, "valuables": 13,
    "exports": 14, "imports": 15, "primary_income_row_net": 16, "gni": 17, "other_current_transfers_row_net": 18,
    "gndi": 19, "gross_saving": 20,
}
NAS2024_API = {  # NAS 2024 Statement 1.15 SNA code -> API indicator (total economy)
    "b1g": 5, "p51c": 6, "b1n": 7, "p51g": 9, "p31": 10, "p32": 11, "p52": 12, "p53": 13,
}
OLD_STAGE_EXPECTED = {
    **{(ed, f"{y}-{str(y + 1)[2:]}"): "Revised" for ed in ("nas2024", "nas2025") for y in (2011, 2012, 2013)},
    **{(ed, f"{y}-{str(y + 1)[2:]}"): "TRE" for ed in ("nas2024", "nas2025") for y in range(2014, 2021)},
    ("nas2024", "2021-22"): "SRE", ("nas2024", "2022-23"): "FRE",
    ("nas2025", "2021-22"): "SRE", ("nas2025", "2022-23"): "Final", ("nas2025", "2023-24"): "FRE",
}


@cache
def oldbase_stage_table() -> dict[tuple[str, str], str]:
    """(edition, year) -> stage, from raw: each NAS 2025 1.1 / NAS 2024 1.15 level (census-verified against its
    workbook) is compared with every API revision round of the same indicator, year and price basis (whole-economy
    records; |diff| < 1 because the old-base API truncates to whole crore). A level that equals exactly one round
    votes for it; every year must get >= 2 votes, all for the same round."""
    rounds: dict[tuple, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for (tag, ind, per), lst in api_index().items():
        if tag == "b2011_current_a":
            for _, r in lst:
                if national_total(r):
                    for pb in ("current", "constant_2011_12"):
                        v = api_value(r, pb, "2011-12")
                        if v is not None:
                            rounds[(ind, per, pb)][r["revision"]].add(v)
    votes: dict[tuple, Counter] = defaultdict(Counter)
    for edition, ds, cmap in (("nas2025", "mospi_nas_2026_oldbase_nas2025_s1_1", NAS2025_API),
                              ("nas2024", "mospi_nas_2026_oldbase_soa_s1_15", NAS2024_API)):
        for r in datasets()[ds]:
            ind = cmap.get(r["item_code"])
            if ind is None or r["unit"] != "INR_crore":
                continue
            hit = {rd for rd, vals in rounds[(ind, r["period"], r["price_basis"])].items()
                   if any(abs(v - r["value"]) < 1 for v in vals)}
            if len(hit) == 1:
                votes[(edition, r["period"])][hit.pop()] += 1
    table = {}
    for k, c in votes.items():
        assert len(c) == 1 and sum(c.values()) >= 2, (k, c)  # 2011-12: SRE and AR mostly coincide
        table[k] = REV[next(iter(c))]
    return table


def test_oldbase_stage_table_derived_from_raw():
    """The builder's relabel (issue 9, `oldbase.STAGES`) re-derived independently, and the relabel census: exactly
    the 2,540 rows of (both editions, 2011-12..2013-14) and (NAS 2025, 2021-22 / 2022-23) changed stage."""
    assert oldbase_stage_table() == OLD_STAGE_EXPECTED
    groups: Counter = Counter()
    changed: Counter = Counter()
    for name, rows in datasets().items():
        if "_oldbase_" not in name:
            continue
        for r in rows:
            k = ("nas2024" if r["vintage"] == "2024-06-05" else "nas2025", r["period"])
            groups[k] += 1
            if r["estimate_stage"] != textbook_stage(r["vintage"], r["period"]):
                changed[k] += 1
    want = {k for k, v in OLD_STAGE_EXPECTED.items() if v != textbook_stage(
        "2024-06-05" if k[0] == "nas2024" else "2025-06-26", k[1])}
    assert set(changed) == want and all(changed[k] == groups[k] for k in want), (changed, want)
    assert sum(changed.values()) == 2540


def test_relabelled_rows_sample_against_raw():
    """Seeded sample (>= 10%, >= 30) of the 2,540 relabelled old-base rows: value and context located in the raw
    workbook (the relabel must not have moved anything) and stage = the raw-derived table."""
    prov = provenance()
    stages = oldbase_stage_table()
    rel = [r for name, rows in sorted(datasets().items()) if "_oldbase_" in name for r in rows
           if r["estimate_stage"] != textbook_stage(r["vintage"], r["period"])]
    rng = random.Random(SEED + 9)
    s = rng.sample(rel, max(30, math.ceil(0.10 * len(rel))))
    bad = []
    for r in s:
        ed = "nas2024" if r["vintage"] == "2024-06-05" else "nas2025"
        if locate(r, prov)[0] != "ok" or r["estimate_stage"] != stages[(ed, r["period"])]:
            bad.append((r["dataset"], r["series_id"], r["period"], r["estimate_stage"]))
    assert len(s) >= 254 and not bad, bad[:10]


if __name__ == "__main__":  # diagnostics: uv run python tests/verify/test_mospi_nas_2026_spotcheck.py
    checked, failures = run_spotcheck()
    print("checked", len(checked), "failed", len(failures))
    by_ds = Counter(r["dataset"] for r, _ in failures)
    print(by_ds)
    for k, v in unmatched_raw_numbers().items():
        print("UNMATCHED", k, len(v), v[:12])
    for r, info in failures[:80]:
        print(
            r["dataset"],
            r["series_id"],
            r["period"],
            r["value"],
            r["item_label"],
            r.get("industry"),
            r.get("institution"),
            r.get("dim_other"),
            r.get("side"),
        )
        for i in info[:3]:
            print("     ", i)
