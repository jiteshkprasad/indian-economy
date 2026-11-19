"""Independent verification of ingest unit state_fiscal (Phase 1 verifier, first and second pass, 2026-09-29).

Second pass added: block-specific declared drop (AP_un C.8.a 2015), a full KFI reverse census under the
builder's revised zero/incomplete rules re-implemented from the rule text, a row-by-row check of the
'INCOMPLETE' provenance flags, the Statement 36 partial-total check for every year against the provenance
note and coverage caveat, and verify-10/11 source facts (see docs/phase1/verify/state_fiscal.md).

Close-out pass (after the builder adopted the D1-9 code set): the geography of every State row is now
checked against the verifier's OWN territory calendar (appointed days of the reorganisation Acts), not
just mapped back; the out-of-lifetime rows must be exactly the expected ones, with a reason in their
provenance; the verify-10 note must carry the raw-derived sums; INCOMPLETE notes must name exactly the
blocks that exist and are not compiled (verify-12); and a seeded >=10% sample of the rows the follow-up
changed is re-derived from raw by a second path (Decimal sums, direct cell addressing).

Final pass (verify-13 fix, S9 declaration): the verify-13 strict xfail is removed and the check now also
requires the case-specific dates in each out-of-lifetime row's record; the KFI E.* ratios for FY 2014-15,
the J&K FY 2019-20 Municipal per-cent rows and the S9 State Provident Funds lines are re-derived from raw.

This file does NOT import pipeline.ingest.state_fiscal (nor pipeline.core). Every pinned raw file is
re-read with a different parser than the unit uses:
- every XLSX: python-calamine cell grids (the unit uses openpyxl for all but two; for the two big
  FC16 dumps it uses polars.read_excel, here the grid is aggregated in plain Python with math.fsum);
- the PRI Chapter II PDF: pypdf page text (the unit uses pdfplumber), plus literal values typed by
  the verifier after reading the page text (constants below, with the page they come from).
Clean data are read with pyarrow.parquet directly. State names/codes use the verifier's own map.

The comparison is a census: every clean row of every dataset is matched to its raw cell (or, for the
three derived datasets, to an independent re-aggregation of the raw rows) by LABEL, never by
position, and in the other direction every published raw cell must have a clean row unless it is on
the unit's declared exclusion list (checked explicitly). Each test prints
'SPOTCHECK <dataset>: checked=N mismatched=M' (run with -s to see the counts).
"""

from __future__ import annotations

import hashlib
import math
import random
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow.parquet as pq
import pytest
import yaml
from pypdf import PdfReader
from python_calamine import CalamineWorkbook

pytestmark = pytest.mark.quality

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean" / "state_fiscal"
SEED = 20260929


# --------------------------------------------------------------------------------------------- helpers
def _pins() -> dict:
    return yaml.safe_load((ROOT / "data" / "raw_pins" / "state_fiscal.yaml").read_text(encoding="utf-8"))["pins"]


def raw_path(key: str) -> Path:
    pin = _pins()[key]
    p = ROOT / pin["path"]
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    assert h == pin["sha256"], f"{key}: file hash {h} != pin {pin['sha256']}"
    return p


def grid(key: str, sheet: str | int = 0) -> list[list]:
    wb = CalamineWorkbook.from_path(str(raw_path(key)))
    name = wb.sheet_names[sheet] if isinstance(sheet, int) else sheet
    return wb.get_sheet_by_name(name).to_python(skip_empty_area=False)


def sheets(key: str) -> dict[str, list[list]]:
    wb = CalamineWorkbook.from_path(str(raw_path(key)))
    return {n: wb.get_sheet_by_name(n).to_python(skip_empty_area=False) for n in wb.sheet_names}


def clean(ds: str) -> list[dict]:
    return pq.read_table(CLEAN / f"state_fiscal_{ds}.parquet").to_pylist()


def norm(s: object) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(s if s is not None else ""))).strip().lower()


def num(x: object) -> float | None:
    """Verifier's own cell reader. Missing markers -> None; anything unexpected raises."""
    if x is None or isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return None if (isinstance(x, float) and math.isnan(x)) else float(x)
    s = unicodedata.normalize("NFKC", str(x)).strip()
    if s in ("", "-", "–", "—", "‘–’", "NA", "n.a.", "..."):
        return None
    t = s.replace(",", "")
    if re.fullmatch(r"-?\d+(\.\d+)?", t):
        return float(t)
    raise ValueError(f"unexpected cell text {x!r}")


def close(a: float, b: float) -> bool:
    return abs(a - b) <= 1e-6 + 1e-9 * abs(b)


def report(ds: str, checked: int, bad: list) -> None:
    print(f"SPOTCHECK {ds}: checked={checked} mismatched={len(bad)}")
    assert not bad, f"{ds}: {len(bad)} mismatches, e.g. {bad[:8]}"


def sample(rows: list, k: int) -> list:
    rnd = random.Random(SEED)
    return rnd.sample(rows, min(k, len(rows)))


# The verifier's own ISO 3166-2:IN map (names as printed across the files, lower-case).
ISO = {
    "andhra pradesh": "IN-AP", "arunachal pradesh": "IN-AR", "assam": "IN-AS", "bihar": "IN-BR",
    "chhattisgarh": "IN-CG", "goa": "IN-GA", "gujarat": "IN-GJ", "haryana": "IN-HR",
    "himachal pradesh": "IN-HP", "jharkhand": "IN-JH", "karnataka": "IN-KA", "kerala": "IN-KL",
    "madhya pradesh": "IN-MP", "maharashtra": "IN-MH", "manipur": "IN-MN", "meghalaya": "IN-ML",
    "mizoram": "IN-MZ", "nagaland": "IN-NL", "odisha": "IN-OD", "punjab": "IN-PB", "rajasthan": "IN-RJ",
    "sikkim": "IN-SK", "tamil nadu": "IN-TN", "telangana": "IN-TS", "tripura": "IN-TR",
    "uttar pradesh": "IN-UP", "uttarakhand": "IN-UK", "west bengal": "IN-WB",
    "jammu and kashmir": "IN-JK", "nct delhi": "IN-DL", "delhi": "IN-DL", "puducherry": "IN-PY",
}  # fmt: skip
# FC16 two-letter codes -> ISO (FC16 uses CH for Chhattisgarh and OD, TS, UK).
FC16 = {
    "AP": "IN-AP", "AR": "IN-AR", "AS": "IN-AS", "BR": "IN-BR", "CH": "IN-CG", "GA": "IN-GA", "GJ": "IN-GJ",
    "HP": "IN-HP", "HR": "IN-HR", "JH": "IN-JH", "KA": "IN-KA", "KL": "IN-KL", "MH": "IN-MH", "ML": "IN-ML",
    "MN": "IN-MN", "MP": "IN-MP", "MZ": "IN-MZ", "NL": "IN-NL", "OD": "IN-OD", "PB": "IN-PB", "RJ": "IN-RJ",
    "SK": "IN-SK", "TN": "IN-TN", "TR": "IN-TR", "TS": "IN-TS", "UK": "IN-UK", "UP": "IN-UP", "WB": "IN-WB",
    "JK": "IN-JK", "DL": "IN-DL", "PY": "IN-PY",
}  # fmt: skip


# Close-out pass (DECISIONS D1-9). The verifier's own territory calendar, from the appointed days of the
# reorganisation Acts: Andhra Pradesh Reorganisation Act 2014 (2 June 2014); J&K Reorganisation Act 2019
# (31 Oct 2019); MP, UP and Bihar Reorganisation Acts 2000 (Chhattisgarh 1 Nov, Uttaranchal 9 Nov,
# Jharkhand 15 Nov 2000); DNH & DD merger (26 Jan 2020). TERR_FROM = first day the CURRENT territory of the
# code exists; TERR_TO = last day of a historical territory. Historical project codes (not ISO): IN-XAP,
# IN-XJK. The dates are cross-checked against pipeline/core/geo.py by reading its text (no import).
TERR_FROM = {
    "IN-AP": "2014-06-02", "IN-TS": "2014-06-02", "IN-JK": "2019-10-31", "IN-LA": "2019-10-31",
    "IN-CG": "2000-11-01", "IN-MP": "2000-11-01", "IN-UK": "2000-11-09", "IN-UP": "2000-11-09",
    "IN-JH": "2000-11-15", "IN-BR": "2000-11-15", "IN-DH": "2020-01-26",
}  # fmt: skip
TERR_TO = {"IN-XAP": "2014-06-01", "IN-XJK": "2019-10-30"}
HIST_FC16 = {"IN-XAP": "AP_un", "IN-XJK": "JK"}  # historical code -> FC16 block / 'State Abb'


def period_span(period: str, period_type: str) -> tuple[str, str]:
    if period_type == "fy":
        y = int(period[:4])
        return f"{y}-04-01", f"{y + 1}-03-31"
    assert period_type == "date", period_type
    return period, period


def territory_class(geography: str, period: str, period_type: str) -> str | None:
    """None if the code's territory existed for the whole period, else 'before' / 'after' / 'straddle'."""
    p0, p1 = period_span(period, period_type)
    if geography in TERR_FROM:
        s = TERR_FROM[geography]
        if p1 < s:
            return "before"
        if p0 < s:
            return "straddle"
    if geography in TERR_TO:
        e = TERR_TO[geography]
        if p0 > e:
            return "after"
        if p1 > e:
            return "straddle"
    return None


def fc16_geo_expected(abbr: str, yl: int) -> str:
    """Verifier's mapping of an FC16 block / 'State Abb' and year label (2024 = FY 2023-24; for stocks the
    end-March year) to the project geography. 'AP_un' is undivided AP whatever the year (the FC16 files
    say 'consolidated Andhra Pradesh prior to 2015'); 'JK' is the former State for years ending before
    31 Oct 2019 and the UT for years starting after it; a straddling J&K year must not occur in FC16 data."""
    if abbr == "AP_un":
        return "IN-XAP"
    if abbr == "JK":
        if f"{yl}-03-31" <= TERR_TO["IN-XJK"]:
            return "IN-XJK"
        assert f"{yl - 1}-04-01" >= TERR_FROM["IN-JK"], f"FC16 J&K year label {yl} straddles 31 Oct 2019"
        return "IN-JK"
    return FC16[abbr]


def state_iso(printed: str) -> str:
    n = norm(printed)
    n = re.sub(r"^\d+\.\s*", "", n).replace("&", "and")
    if n.startswith("all states"):
        return "ALL"
    if n == "total":
        return "ALL"
    return ISO[n]


def geo_of(row: dict) -> str:
    """Clean row -> verifier geography key (ISO code, or 'ALL' for an all-States aggregate)."""
    if row["geography"] == "IN":
        return "ALL"
    return row["geography"]


def fy_of(p: str) -> str:
    y = int(p[:4])
    return f"{y}-{(y + 1) % 100:02d}"


def rbi_head(h: object) -> tuple[str, str]:
    """Verifier's own RBI period-header reader: '2024-25 (Revised Estimates)' -> ('2024-25', 'RE')."""
    t = norm(h).replace("$", "")
    m = re.match(r"^(\d{4})\s*-\s*(\d{2,4})\s*(?:\((.*)\))?\s*$", t)
    assert m, h
    y0 = int(m.group(1))
    tag = (m.group(3) or "").strip()
    stage = {"": "Actuals", "accounts": "Actuals", "re": "RE", "revised estimates": "RE", "be": "BE",
             "budget estimates": "BE"}[tag]  # fmt: skip
    return f"{y0}-{(y0 + 1) % 100:02d}", stage


# --------------------------------------------------------------------------------------------- FC16 KFI
KFI_BLOCK = {"state_group=all_states_28": "All_States", "state_group=non_neh_states": "non-NEH_States",
             "state_group=neh_states": "NEH_States", "boundary=undivided": "AP_un"}  # fmt: skip
ISO2FC16 = {v: k for k, v in FC16.items()}


def _state_block(r: dict, yl: int) -> str:
    """Clean State row -> FC16 block / 'State Abb'. Close-out pass: the geography must be what the verifier's
    own calendar expects for that block and year (IN-XAP for undivided AP, IN-XJK for the former State of
    J&K), and the redundant 'boundary=undivided' marker must sit on exactly the IN-XAP rows."""
    g = r["geography"]
    undivided = bool(r["dim_other"]) and "boundary=undivided" in r["dim_other"]
    assert undivided == (g == "IN-XAP"), (g, r["dim_other"], r["series_id"])
    abbr = HIST_FC16.get(g) or ISO2FC16[g]
    assert fc16_geo_expected(abbr, yl) == g, (abbr, yl, g, r["series_id"])
    return abbr


def _kfi_year_label(r: dict) -> int:
    if r["period_type"] == "fy":
        return int(r["period"][:4]) + 1
    assert r["period_type"] == "date" and r["period"].endswith("-03-31"), r["period"]
    return int(r["period"][:4])


def _kfi_block(r: dict) -> str:
    if r["geography"] == "IN":
        assert r["dim_other"].startswith("state_group="), r["dim_other"]
        return KFI_BLOCK[r["dim_other"]]
    return _state_block(r, _kfi_year_label(r))
# Cells the unit declares it drops although they are non-zero (issues file state_fiscal-3): totals
# built on not-compiled debt-flow rows. Year labels are KFI labels (2024 = FY 2023-24).
KFI_DECLARED_NONZERO_DROPS = {
    ("a.5", 2024), ("a.8", 2024), ("b.8", 2024), ("a.10", 2023), ("b.10", 2023),
    ("a.11", 2023), ("a.11", 2024), ("b.11", 2023), ("b.11", 2024),
}  # fmt: skip
# Second pass: declared drops that are specific to one block. Undivided AP ceased on 2 June 2014; its
# C.8.a at end-March 2015 (55,536.02) repeats end-March 2014 (55,536) and is dropped (verify-2 fix).
# This list is block-specific on purpose: ('c.8.a', 2015) for every block would be too loose.
KFI_DECLARED_BLOCK_DROPS = {("c.8.a", "AP_un", 2015)}
# West Bengal is the only State with a complete public account for 2022-23; it is kept (verify-3 fix).
KFI_KEPT_EXCEPTIONS = {("WB", 2023)}


def _kfi_raw():
    g = grid("fc16_relevant_data/fc16_kfi.xlsx", "State-wise")
    head = g[0]
    assert norm(head[1]) == "s.n" and norm(head[2]) == "description"
    blocks = [(j, c) for j, c in enumerate(head) if isinstance(c, str) and c and j >= 4]
    assert len(blocks) == 32
    for j, _ in blocks:
        assert [int(x) for x in head[j + 1 : j + 14]] == list(range(2012, 2025))
    raw: dict[tuple, float] = {}
    sn_of: dict[str, str] = {}
    labels = Counter()
    for r in g[1:]:
        desc = r[2]
        if not (isinstance(desc, str) and desc.strip()):
            continue  # the unlabelled %-of-GSDP rows
        vals = [r[j + 1 + k] for j, _ in blocks for k in range(13)]
        if all(v in ("", None) for v in vals):
            continue
        lab = norm(desc)
        labels[lab] += 1
        sn_of[lab] = norm(r[1])
        for j, b in blocks:
            for k in range(13):
                cell = r[j + 1 + k]
                if isinstance(cell, str) and cell.strip() == "#DIV/0!":
                    continue
                v = num(cell)
                if v is not None:
                    raw[(lab, b, 2012 + k)] = v
    assert all(n == 1 for n in labels.values()), [k for k, n in labels.items() if n > 1]
    return raw, sn_of


def test_kfi_census():
    raw, sn_of = _kfi_raw()
    rows = clean("fc16_kfi")
    bad, seen = [], set()
    for r in rows:
        block = _kfi_block(r)  # close-out: also asserts IN-XAP for AP_un (was: mapped back via dim_other)
        if r["period_type"] == "fy":
            yl = int(r["period"][:4]) + 1
            assert r["stock_flow"] in ("flow", "n/a")
        else:
            assert r["period_type"] == "date" and r["period"].endswith("-03-31") and r["stock_flow"] == "stock"
            yl = int(r["period"][:4])
        key = (norm(r["item_label"]), block, yl)
        seen.add(key)
        v = raw.get(key)
        if v is None or not close(r["value"], v):
            bad.append((key, r["value"], v))
    report("fc16_kfi", len(rows), bad)
    # reverse direction: every published cell is in clean, except zeros and the declared totals
    missing = {k: v for k, v in raw.items() if k not in seen}
    nonzero = {k: v for k, v in missing.items() if v != 0}
    undeclared = [
        (k, v)
        for k, v in nonzero.items()
        if (sn_of[k[0]], k[2]) not in KFI_DECLARED_NONZERO_DROPS and (sn_of[k[0]], k[1], k[2]) not in KFI_DECLARED_BLOCK_DROPS
    ]
    assert not undeclared, f"KFI non-zero cells dropped without a declared reason: {undeclared[:10]}"
    print(f"KFI: {len(missing)} published cells not ingested ({len(missing) - len(nonzero)} zeros, "
          f"{len(nonzero)} declared incomplete totals)")  # fmt: skip


def test_kfi_year_labels_and_stock_flow():
    """'2024' = FY 2023-24: GST starts in FY 2017-18, GST loans in 2020-21/2021-22; stocks at end-March."""
    rows = [r for r in clean("fc16_kfi") if r["dim_other"] == "state_group=all_states_28"]
    by = {(r["item_code"].split("-")[0], r["period"]): r["value"] for r in rows}
    assert by[("a_1_1_2", "2016-17")] == 0 and by[("a_1_1_2", "2017-18")] > 2.6e5
    assert by[("a_4_2_a", "2020-21")] > 0 and by[("a_4_2_a", "2021-22")] > 0
    # true nil (A.4 compiled that year): kept since the builder's verify-3 fix (was: dropped, asserted 'not in')
    assert by[("a_4_2_a", "2019-20")] == 0
    assert round(by[("c_1_2_a", "2024-03-31")]) == 249191
    # E.* ratios are unitless, C.10 GSDP is the old base
    for r in rows:
        if r["item_code"].startswith("e_"):
            assert r["unit"] == "ratio" and r["stock_flow"] == "n/a"
        if r["item_code"].startswith("c_10-"):
            assert r["base_year"] == "2011-12"


# --------------------------------------------------------------------------------------------- FC16 transfers
def _year_stage(t: object) -> tuple[str, str] | None:
    s = norm(t)
    m = re.fullmatch(r"(\d{4})-(\d{2})\s*(re|be)?", s)
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}", {"re": "RE", "be": "BE", None: "Actuals"}[m.group(3)]


def test_fc16_transfers_census():
    sh = sheets("fc16_relevant_data/fc16_transfers.xlsx")
    raw: dict[tuple, float] = {}
    for sheet, table, ycol in (("Time series of transfers - mast", "Time series of transfers (master)", 1),
                               ("Grants - details RBI", "Grants - details RBI", 0)):  # fmt: skip
        g = sh[sheet]
        head = [norm(h) for h in g[1]]
        for r in g[2:]:
            ys = _year_stage(r[ycol])
            if not ys:
                continue
            for j, h in enumerate(head):
                if j <= ycol or not h:
                    continue
                v = num(r[j])
                if v is not None:
                    raw[(table, h, *ys)] = v
    rows = clean("fc16_transfers")
    bad, seen = [], set()
    for r in rows:
        key = (r["table_id"], norm(r["item_label"]), r["period"], r["estimate_stage"])
        seen.add(key)
        v = raw.get(key)
        if v is None or not close(r["value"], v):
            bad.append((key, r["value"], v))
    report("fc16_transfers", len(rows), bad)
    labels = {(k[0], k[1]) for k in seen}
    missing = [k for k in raw if (k[0], k[1]) in labels and k not in seen]
    assert not missing, missing[:10]
    # the ratio columns (per cent of GTR/GDP) must not be ingested
    assert not any("%" in k[1] or "/" in k[1] for k in seen)


# --------------------------------------------------------------------------------------------- FC16 subsidies
def test_fc16_subsidies_census():
    g = grid("fc16_relevant_data/fc16_subsidies.xlsx")
    assert "rs. crore" in norm(g[0][9])
    periods = {}
    for j in range(2, 10):
        m = re.fullmatch(r"(\d{4}-\d{2})\s*(?:\((re|be)\))?", norm(g[1][j]))
        periods[j] = (m.group(1), {"re": "RE", "be": "BE", None: "Actuals"}[m.group(2)])
    raw = {}
    for r in g[2:]:
        if not r[0]:
            continue
        for j, (p, st) in periods.items():
            v = num(r[j])
            if v is not None:
                raw[(norm(r[0]), norm(r[1]), p)] = (v, st)
    rows = clean("fc16_subsidies")
    bad, seen = [], set()
    name_of = {v: k for k, v in ISO.items() if k != "nct delhi"}
    for r in rows:
        st = "union" if r["institution"] == "gg_centre" else name_of[r["geography"]]
        sector = norm(r["item_label"].split(":", 1)[1])
        key = (st, sector, r["period"])
        seen.add(key)
        got = raw.get(key)
        if got is None or not close(r["value"], got[0]) or r["estimate_stage"] != got[1]:
            bad.append((key, r["value"], got))
    report("fc16_subsidies", len(rows), bad)
    assert set(raw) == seen


# --------------------------------------------------------------------------------------------- FC16 accounts dump
_ACC = {"Revenue Rec": "revenue_receipts", "Revenue Exp": "revenue_expenditure",
        "Capital Exp": "capital_expenditure", "Capital Rec": "capital_receipts"}  # fmt: skip


@pytest.fixture(scope="module")
def accounts():
    g = grid("fc16_relevant_data/fc16_state_accounts.xlsx", "ServiceHeads")
    head = g[0]
    ix = {h: i for i, h in enumerate(head)}
    mh: dict[tuple, list] = defaultdict(list)
    lb: dict[tuple, list] = defaultdict(list)
    for r in g[1:]:
        a = num(r[ix["Amount"]])
        if a is None:
            continue
        st, yr, cl = r[ix["State Abb"]], int(float(r[ix["Year"]])), r[ix["Classification"]]
        m = str(r[ix["Major Head"]])
        mh[(st, yr, cl, m)].append(a)
        mn = str(r[ix["Minor Head"]])
        if mn in ("191", "192", "193", "196", "197", "198") and cl in ("Revenue Exp", "Capital Exp"):
            lb[(st, yr, cl, mn)].append(a)
    return ({k: math.fsum(v) / 100 for k, v in mh.items()}, {k: math.fsum(v) / 100 for k, v in lb.items()})


def _acc_state(r: dict) -> str:
    if r["institution"] == "gg_centre":
        assert r["geography"] == "IN"
        return "#BH"
    # close-out: the geography is checked against the verifier's calendar ('AP_un' -> IN-XAP, 'JK' FY 2013-14
    # to 2018-19 -> IN-XJK, FY 2020-21 -> IN-JK), not just mapped back (was: KeyError on IN-XJK, state_fiscal-24)
    return _state_block(r, int(r["period"][:4]) + 1)


def _acc_account(r: dict) -> str:
    d = dict(kv.split("=") for kv in r["dim_other"].split(";"))
    return {v: k for k, v in _ACC.items()}[d["account"]]


def test_fc16_state_accounts_census(accounts):
    mh, _ = accounts
    rows = clean("fc16_state_accounts")
    bad, seen = [], set()
    for r in rows:
        assert r["status"] == "derived" and r["period_type"] == "fy"
        key = (_acc_state(r), int(r["period"][:4]) + 1, _acc_account(r), r["item_code"].removeprefix("mh_"))
        seen.add(key)
        v = mh.get(key)
        if v is None or not close(r["value"], v):
            bad.append((key, r["value"], v))
    report("fc16_state_accounts", len(rows), bad)
    assert set(mh) == seen, f"{len(set(mh) - seen)} raw groups not in clean"


def test_fc16_local_body_assistance_census(accounts):
    _, lb = accounts
    rows = clean("fc16_local_body_assistance")
    bad, seen = [], set()
    for r in rows:
        key = (_acc_state(r), int(r["period"][:4]) + 1, _acc_account(r), r["item_code"].removeprefix("minor_"))
        seen.add(key)
        v = lb.get(key)
        if v is None or not close(r["value"], v):
            bad.append((key, r["value"], v))
        want = "gg_local_urban" if key[3] in ("191", "192", "193") else "gg_local_rural"
        assert r["counterparty"] == want
    report("fc16_local_body_assistance", len(rows), bad)
    assert set(lb) == seen


def test_accounts_dump_reproduces_kfi_2023_24(accounts):
    """The builder's claim: 2023-24 major-head sums reproduce KFI A.1 and B.2 State by State."""
    mh, _ = accounts
    raw, _ = _kfi_raw()
    n = 0
    for abbr in FC16:
        if abbr in ("JK", "DL", "PY"):
            continue
        rr = math.fsum(v for k, v in mh.items() if k[0] == abbr and k[1] == 2024 and k[2] == "Revenue Rec")
        ce = math.fsum(v for k, v in mh.items() if k[0] == abbr and k[1] == 2024 and k[2] == "Capital Exp")
        assert abs(rr - raw[("revenue receipts", abbr, 2024)]) < 0.05, abbr
        assert abs(ce - raw[("capital expenditure", abbr, 2024)]) < 0.05, abbr
        n += 2
    sgst = math.fsum(v for k, v in mh.items() if k[1] == 2024 and k[3] == "0006" and k[0] not in ("#BH",))
    assert abs(sgst - 800112.0157) < 0.05
    print(f"accounts dump vs KFI 2023-24: {n} State totals agree")


# --------------------------------------------------------------------------------------------- ULB dump
ULB_STOCK_COLS = set(range(39, 49))  # 1-based: borrowings (39-43), receivables (44-47), cash (48)


def test_ulb_cityfinance_census():
    g = grid("fc16_ulb_cityfinance_dump/fc16_ulb_cityfinance.xlsx", "Financial & Docs_All_ULBs clean")
    head = [norm(h) for h in g[0]]
    assert head[7] == "property tax" and head[47] == "total cash and bank balance"
    # magnitude check of the 'rupees' assumption: Khategaon (pop. 25,540) total revenues 2023-24
    kh = [r for r in g[1:] if r[2] == "Khategaon Town Panchayat" and r[5] == "2023-24"][0]
    assert 1e8 < kh[26] < 2e8  # 11.9 crore in rupees; in lakh or thousand it would be absurd
    sums: dict[tuple, list] = defaultdict(list)
    for r in g[1:]:
        st, yr = state_iso(r[1]), r[5]
        for c in range(8, 49):
            v = num(r[c - 1])
            if v is None:
                continue
            sums[(st, yr, c)].append(v)
            sums[("ALL", yr, c)].append(v)
    by_label: dict[str, list[int]] = defaultdict(list)
    for c in range(8, 49):
        by_label[head[c - 1]].append(c)
    rows = clean("ulb_cityfinance")
    bad, seen = [], set()
    for r in rows:
        lab = norm(r["item_label"])
        is_n = lab.startswith("number of ulbs reporting: ")
        lab = lab.removeprefix("number of ulbs reporting: ")
        cols = by_label[lab]
        if len(cols) > 1:  # 'Others' twice: revenue-expenditure (col 30) and borrowings (col 42)
            cols = [30] if "revenue_expenditure_others" in r["item_code"] else [42]
        c = cols[0]
        yr = r["period"] if r["period_type"] == "fy" else fy_of(str(int(r["period"][:4]) - 1))
        if not is_n:
            assert (r["stock_flow"] == "stock") == (c in ULB_STOCK_COLS), (lab, r["stock_flow"])
        key = (geo_of(r), yr, c)
        seen.add(key)
        vals = sums.get(key)
        if vals is None:
            bad.append((key, r["value"], None))
            continue
        if is_n:
            want = float(len(vals))
        elif lab == "number of registered properties":
            want = math.fsum(vals)
        else:
            want = math.fsum(vals) / 1e7
        if not close(r["value"], want):
            bad.append((key, is_n, r["value"], want))
    report("ulb_cityfinance", len(rows), bad)
    assert set(sums) == seen


# --------------------------------------------------------------------------------------------- RBI SF statements
def _statement_rows(g: list[list], first: int) -> list[tuple[str, list]]:
    out = []
    for r in g[first:]:
        lab = r[1]
        if not isinstance(lab, str) or not lab.strip():
            continue
        n = norm(lab)
        if not (re.match(r"^\d+\.", n) or n.startswith("all states")):
            continue  # notes and sources
        out.append((state_iso(lab), r))
    return out


def test_rbi_sf_statements_census():
    raw: dict[tuple, float] = {}
    for key, code in (("sf2526_st13.xlsx", "interest_payments"), ("sf2526_st17.xlsx", "transfers_from_centre")):
        g = grid(f"rbi_state_finances_study/{key}")
        assert "crore" in norm(g[2][1])
        for gc in (2, 4, 6):
            p, st = rbi_head(g[3][gc])
            for c, basis in ((gc, "gross"), (gc + 1, "net")):
                assert norm(g[5][c]).startswith(basis)
                for iso, r in _statement_rows(g, 7):
                    v = num(r[c])
                    if v is not None:
                        raw[(f"{code}_{basis}", iso, p, st)] = v
    st14 = {2: "tax_revenue", 5: "own_tax_revenue", 8: "share_in_central_taxes"}
    st15 = {2: "non_tax_revenue", 5: "own_non_tax_revenue", 8: "grants"}
    for key, groups in (("sf2526_st14.xlsx", st14), ("sf2526_st15.xlsx", st15)):
        g = grid(f"rbi_state_finances_study/{key}")
        assert "per cent" in norm(g[2][1])
        for gc, code in groups.items():
            assert re.sub(r"[-–]", " ", norm(g[3][gc])).startswith(code.replace("_", " ")[:8]), g[3][gc]
            for c in range(gc, gc + 3):
                p, st = rbi_head(g[4][c])
                for iso, r in _statement_rows(g, 6):
                    v = num(r[c])
                    if v is not None:
                        raw[(f"{code}_share", iso, p, st)] = v
    g = grid("rbi_state_finances_study/sf2526_st36.xlsx")
    assert "crore" in norm(g[2][1])
    for c in range(2, 10):
        p, st = rbi_head(g[3][c].replace("(", " ("))
        for iso, r in _statement_rows(g, 5):
            v = num(r[c])
            if v is not None:
                raw[("subsidies", iso, p, st)] = v
    rows = clean("rbi_sf_statements")
    bad, seen = [], set()
    for r in rows:
        key = (r["item_code"], geo_of(r), r["period"], r["estimate_stage"])
        seen.add(key)
        v = raw.get(key)
        if v is None or not close(r["value"], v):
            bad.append((key, r["value"], v))
        assert (r["unit"] == "percent") == r["item_code"].endswith("_share")
    report("rbi_sf_statements", len(rows), bad)
    assert set(raw) == seen, sorted(set(raw) ^ seen)[:10]


def test_statement36_all_states_2023_24_is_partial():
    """Documents verify-2: the All States and UTs subsidy total for 2023-24 (3,29,610) is the sum of the
    reporting States only; Maharashtra, Andhra Pradesh, Arunachal, Goa, Uttarakhand and J&K print '-'."""
    g = grid("rbi_state_finances_study/sf2526_st36.xlsx")
    rows = _statement_rows(g, 5)
    col = 7  # 2023-24
    assert norm(g[3][col]) == "2023-24"
    total = [num(r[col]) for iso, r in rows if iso == "ALL"][0]
    parts = [num(r[col]) for iso, r in rows if iso != "ALL"]
    missing = sorted(iso for iso, r in rows if iso != "ALL" and num(r[col]) is None)
    assert abs(math.fsum(p for p in parts if p is not None) - total) < 1.0
    assert missing == ["IN-AP", "IN-AR", "IN-GA", "IN-JK", "IN-MH", "IN-UK"]
    prev = [num(r[col - 1]) for iso, r in rows if iso == "IN-MH"][0]
    assert prev > 40000  # Maharashtra 2022-23: 43,158 crore, absent from the 2023-24 total


def test_statement36_partial_total_every_year_and_documented():
    """Second pass on verify-1 (builder's state_fiscal-19): for EVERY column the All States and UTs row is the
    sum of the reporting States; the '-' States per column (read here from raw) must be exactly the lists
    written into the Statement 36 provenance note; every St 36 clean row must point to that record; and
    the R18/P9a coverage notes must carry the caveat."""
    g = grid("rbi_state_finances_study/sf2526_st36.xlsx")
    rows = _statement_rows(g, 5)
    want_parts = []
    for c in range(2, 10):
        p, st = rbi_head(g[3][c].replace("(", " ("))
        total = [num(r[c]) for iso, r in rows if iso == "ALL"][0]
        parts = [num(r[c]) for iso, r in rows if iso != "ALL"]
        assert abs(math.fsum(x for x in parts if x is not None) - total) < 1.0, (p, st)
        miss = sorted(iso for iso, r in rows if iso != "ALL" and num(r[c]) is None)
        assert miss, (p, st)  # every year has at least one missing State
        want_parts.append(f"{p}{'' if st == 'Actuals' else ' ' + st}: {', '.join(miss)}")
    prov = {r["prov_id"]: r for r in pq.read_table(CLEAN / "_provenance.parquet").to_pylist()}
    st36 = [r for r in clean("rbi_sf_statements") if r["table_id"] == "Statement 36"]
    notes = {prov[r["prov_id"]]["notes"] for r in st36}
    assert len(notes) == 1
    note = notes.pop()
    assert note.startswith("PARTIAL TOTAL")
    assert note.endswith("States printing '-': " + "; ".join(want_parts) + "."), note
    cov = yaml.safe_load((ROOT / "pipeline" / "ingest" / "state_fiscal_coverage.yaml").read_text(encoding="utf-8"))
    cov = cov if isinstance(cov, list) else cov.get("entries", cov.get("coverage", []))
    st36_cov = [e for e in cov if "st36.subsidies.in.all_states_uts.actuals" in (e.get("series_ids") or [])]
    assert {e["ref"] for e in st36_cov} == {"R18", "P9a"}
    assert all(e["extent"] == "partial" and "PARTIAL TOTAL" in e["note"] for e in st36_cov)
    issues = (ROOT / "docs" / "phase1" / "issues" / "state_fiscal.md").read_text(encoding="utf-8")
    assert "state_fiscal-19" in issues and "partial total" in issues.lower()


def test_statement36_andhra_2022_23_repeats_2021_22():
    """Second pass, verify-11 (info): Statement 36 prints Andhra Pradesh subsidies 14,689.0 for both 2021-22
    and 2022-23, an exact repeat (every other State differs), so 2022-23 AP is probably carried forward.
    FC16 sector-wise subsidies for AP differ widely between the two years. Pinned here as a source fact."""
    g = grid("rbi_state_finances_study/sf2526_st36.xlsx")
    rows = dict(_statement_rows(g, 5))
    assert [norm(g[3][c]) for c in (5, 6)] == ["2021-22", "2022-23"]
    assert num(rows["IN-AP"][5]) == num(rows["IN-AP"][6]) == 14689.0
    repeats = [iso for iso, r in rows.items() if iso != "ALL" and num(r[5]) is not None and num(r[5]) == num(r[6])]
    assert repeats == ["IN-AP"], repeats


# --------------------------------------------------------------------------------------------- RBI SF appendix tables
def _year_row(t: object) -> tuple[str, str] | None:
    s = norm(t)
    if not re.match(r"^\d{4}\s*-\s*\d{2}", s) or "avg" in s:
        return None
    return rbi_head(s)


def test_rbi_sf_app_tables_census():
    raw: dict[tuple, float] = {}
    for key, tid in (("sf2526_app_t01.xlsx", "Appendix Table 1"), ("sf2526_app_t03.xlsx", "Appendix Table 3"),
                     ("sf2526_app_t09.xlsx", "Appendix Table 9")):  # fmt: skip
        g = grid(f"rbi_state_finances_study/{key}")
        assert "crore" in norm(g[2][1]) and norm(g[3][1]) == "year"
        head = {j: norm(h) for j, h in enumerate(g[3]) if j >= 2 and h not in ("", None)}
        for r in g[5:]:
            ys = _year_row(r[1])
            if not ys:
                continue
            for j, h in head.items():
                v = num(r[j])
                if v is not None:
                    raw[(tid, h, *ys)] = v
    # App Table 2: items in rows, years in columns, three sheets
    stale = {}
    for g in sheets("rbi_state_finances_study/sf2526_app_t02.xlsx").values():
        heads = {j: h for j, h in enumerate(g[3]) if j >= 2 and h not in ("", None)}
        for r in g[5:]:
            lab = r[1]
            if not isinstance(lab, str) or not re.match(r"^([IVX]+\.|\d+\.|[a-e]\)|\([iv]+\)|[iv]+\))", lab.strip()):
                continue
            for j, h in heads.items():
                if norm(h) == "2023-24 (budget estimates)":
                    continue  # the mislabelled column (issues state_fiscal-6)
                v = num(r[j])
                if v is None:
                    continue
                p, st = rbi_head(h)
                k = ("Appendix Table 2", norm(lab), p, st)
                raw[k] = v
                if (p, st) in (("2023-24", "Actuals"), ("2022-23", "Actuals")):
                    stale[(norm(lab), p)] = v
    g = grid("rbi_state_finances_study/sf2526_app_t11.xlsx")
    assert "end-march" in norm(g[2][2]) and "crore" in norm(g[3][1]) and norm(g[4][1]) == "year"
    head = {j: norm(h) for j, h in enumerate(g[4]) if j >= 2 and h not in ("", None)}
    for r in g[6:]:
        m = re.fullmatch(r"(\d{4})(?:\s+(re|be))?", norm(r[1]).removesuffix(".0"))
        if not m:
            continue
        date, st = f"{m.group(1)}-03-31", {"re": "RE", "be": "BE", None: "Actuals"}[m.group(2)]
        for j, h in head.items():
            v = num(r[j])
            if v is not None:
                raw[("Appendix Table 11", h, date, st)] = v
    rows = clean("rbi_sf_app_tables")
    bad, seen = [], set()
    for r in rows:
        key = (r["table_id"], norm(r["item_label"]), r["period"], r["estimate_stage"])
        seen.add(key)
        v = raw.get(key)
        if v is None or not close(r["value"], v):
            bad.append((key, r["value"], v))
        assert (r["period_type"] == "date") == (r["table_id"] == "Appendix Table 11")
    report("rbi_sf_app_tables", len(rows), bad)
    missing = sorted(k for k in raw if k not in seen)
    # the only published cells not ingested: App T2 rows III-VI for 2023-24 (Accounts), declared stale
    stale_rx = r"^(iii|iv|v|vi)\.|^[ab]\)"
    assert all(
        k[0] == "Appendix Table 2" and k[2:] == ("2023-24", "Actuals") and re.match(stale_rx, k[1]) for k in missing
    ), missing
    # and they really are copies of 2022-23 (III and V) or computed from them
    for lab in (
        "iii. gross loans from the centre",
        "v. repayment of loans and interest payments liabilities (a+b)",
        "a) repayment of loans to the centre",
        "b) interest payments on the loans from the centre",
    ):
        assert stale[(lab, "2023-24")] == stale[(lab, "2022-23")], lab
    print(f"App tables: {len(missing)} declared-stale App T2 2023-24 cells not ingested")


# --------------------------------------------------------------------------------------------- RBI SF Appendices I-IV
def _appendix_all_states(key: str) -> tuple[list[tuple[str, list]], list[tuple[str, str]]]:
    """[(label, [cells x4])] of the All States and UTs block in sheet order, and its period headers."""
    items, periods = [], None
    for g in sheets(key).values():
        hdr = g[3]
        cols = [j for j, c in enumerate(hdr) if isinstance(c, str) and norm(c).startswith("all state")]
        if not cols:
            continue
        j0 = cols[0]
        assert "lakh" in norm(g[2][1])
        ph = [rbi_head(h) for h in g[4][j0 : j0 + 4]]
        assert periods in (None, ph)
        periods = ph
        for r in g[6:]:
            lab = r[1]
            if isinstance(lab, str) and lab.strip():
                items.append((norm(lab), r[j0 : j0 + 4]))
    return items, periods


def test_rbi_sf_appendices_census():
    rows = clean("rbi_sf_appendices")
    total = 0
    bad = []
    for key, tid in (("sf2526_appx1_all.xlsx", "Appendix I"), ("sf2526_appx2_all.xlsx", "Appendix II"),
                     ("sf2526_appx3_all.xlsx", "Appendix III"), ("sf2526_appx4_all.xlsx", "Appendix IV")):  # fmt: skip
        items, periods = _appendix_all_states(f"rbi_state_finances_study/{key}")
        # candidate raw vectors per label (a label may be printed on two lines: join with the next)
        cand: dict[str, list[tuple]] = defaultdict(list)
        for i, (lab, cells) in enumerate(items):
            cand[lab].append(tuple(num(c) for c in cells))
            if i + 1 < len(items):
                nxt_lab, nxt = items[i + 1]
                joined = tuple(num(a) if num(a) is not None else num(b) for a, b in zip(cells, nxt, strict=True))
                cand[f"{lab} {nxt_lab}"].append(joined)
        mine = [r for r in rows if r["table_id"] == tid]
        by_item: dict[str, dict] = defaultdict(dict)
        for r in mine:
            assert r["unit"] == "INR_crore" and r["geography"] == "IN"
            by_item[r["item_code"]][(r["period"], r["estimate_stage"])] = r
        used: Counter = Counter()
        for code, cells in by_item.items():
            lab = norm(next(iter(cells.values()))["item_label"])
            vecs = cand.get(lab)
            if not vecs:
                bad.append((tid, code, "label not found in raw"))
                continue
            # the clean vector (x100 back to lakh) must equal one raw occurrence of that label
            clean_vec = tuple(cells[p]["value"] * 100 if p in cells else None for p in periods)
            hit = [i for i, v in enumerate(vecs) if all(
                (a is None and b is None) or (a is not None and b is not None and abs(a - b) <= 1e-3 + 1e-9 * abs(b))
                for a, b in zip(clean_vec, v, strict=True))]  # fmt: skip
            total += len(cells)
            if not hit:
                bad.append((tid, code, clean_vec, vecs))
            used[lab] += 1
        # every raw item line with a number is in clean (bare 'of which:' markers carry none)
        raw_numbered = Counter(lab for lab, cells in items if any(num(c) is not None for c in cells))
        short = {lab: n for lab, n in raw_numbered.items() if used[lab] < n and not any(
            (k.startswith(lab + " ") or k.endswith(" " + lab)) and used[k] for k in used)}  # fmt: skip
        assert not short, (tid, short)
    report("rbi_sf_appendices", total, bad)
    assert total == len(rows)


# --------------------------------------------------------------------------------------------- RBI municipal
def test_rbi_municipal_census():
    raw: dict[tuple, float] = {}
    for key, code in (("muni_st01.xlsx", "revenue_receipts"), ("muni_st04.xlsx", "revenue_expenditure"),
                      ("muni_st08.xlsx", "capital_outlay")):  # fmt: skip
        g = grid(f"rbi_municipal_finances/{key}")
        assert "lakh" in norm(g[2][1]) and "per cent of gsdp" in norm(g[3][7])
        for r in g[5:]:
            lab = r[1]
            if not isinstance(lab, str) or not (re.match(r"^\d+\.", lab.strip()) or norm(lab) == "total"):
                continue
            iso = state_iso(lab)
            for c in range(2, 7):
                v = num(r[c])
                if v is not None:
                    raw[(code, iso, *rbi_head(g[3][c]))] = v / 100  # Rs lakh -> Rs crore
            for c in range(7, 12):
                v = num(r[c])
                if v is not None:
                    raw[(f"{code}_pct_gsdp", iso, *rbi_head(g[4][c]))] = v
    rows = clean("rbi_municipal")
    bad, seen = [], set()
    for r in rows:
        key = (r["item_code"], geo_of(r), r["period"], r["estimate_stage"])
        seen.add(key)
        v = raw.get(key)
        if v is None or not close(r["value"], v):
            bad.append((key, r["value"], v))
    report("rbi_municipal", len(rows), bad)
    assert set(raw) == seen, sorted(set(raw) ^ seen)[:10]


# --------------------------------------------------------------------------------------------- RBI PRI
# Typed by the verifier from the page text of pri_ch2.pdf (Chapter II, PDF p.3 = printed p.12
# Table II.3; p.5 = printed p.14 Table II.5; p.1 Table II.1; p.2 Table II.2).
PRI_PDF_TYPED = {
    ("rr", "2020-21"): 41744, ("rr", "2021-22"): 37971, ("rr", "2022-23"): 35354,
    ("own_tax", "2020-21"): 703, ("own_tax", "2021-22"): 786, ("own_tax", "2022-23"): 737,
    ("own_non_tax", "2020-21"): 1365, ("own_non_tax", "2021-22"): 1415, ("own_non_tax", "2022-23"): 1494,
    ("grants", "2020-21"): 39675, ("grants", "2021-22"): 35770, ("grants", "2022-23"): 33123,
    ("grants_centre", "2020-21"): 30264, ("grants_centre", "2021-22"): 27060, ("grants_centre", "2022-23"): 24699,
    ("grants_state", "2020-21"): 9138, ("grants_state", "2021-22"): 8412, ("grants_state", "2022-23"): 8148,
    ("rev_exp", "2020-21"): 24600, ("rev_exp", "2021-22"): 21248, ("rev_exp", "2022-23"): 20712,
    ("rev_exp_pr_programmes", "2020-21"): 18377, ("rev_exp_pr_programmes", "2021-22"): 13737,
    ("rev_exp_pr_programmes", "2022-23"): 13137,
    ("rev_exp_water_sanitation", "2020-21"): 3277, ("rev_exp_water_sanitation", "2021-22"): 4717,
    ("rev_exp_water_sanitation", "2022-23"): 5616,
    ("n_village_panchayats", "2022-12-31"): 255623, ("n_vp_total_table_ii2", "2022-23"): 258561,
    ("n_vp_panel_receipts", "2022-23"): 208848, ("n_vp_panel_expenditure", "2022-23"): 178572,
}  # fmt: skip
_N3 = r"\s+([\d,]+)\s+(?:\(\d+\)\s+)?([\d,]+)\s+(?:\(\d+\)\s+)?([\d,]+)"  # pypdf puts the (share) under each number
PRI_PDF_LINES = {  # code -> (0-based page, regex on the pypdf page text); first match = the Rs crore panel
    "rr": (2, r"Revenue Receipts" + _N3),
    "own_tax": (2, r"A\. Own Tax Revenue" + _N3),
    "own_non_tax": (2, r"B\. Own Non-Tax Revenue" + _N3),
    "grants": (2, r"C\. Grants-in-aid" + _N3),
    "grants_centre": (2, r"\(i\) Grants from Central\s+Government" + _N3),
    "grants_state": (2, r"\(ii\) Grants from State Government" + _N3),
    "rev_exp": (4, r"Revenue Expenditure" + _N3),
    "rev_exp_pr_programmes": (4, r"Panchayati Raj Programmes" + _N3),
    "rev_exp_water_sanitation": (4, r"Water Supply and Sanitation" + _N3),
}


def test_rbi_pri_census():
    rows = clean("rbi_pri")
    # Appendices I-II: 'ALL STATES/UTs*' block, Rs per village panchayat
    raw: dict[tuple, float] = {}
    for key, tid in (("pri_app1_part7.xlsx", "Appendix I"), ("pri_app2_part7.xlsx", "Appendix II")):
        for g in sheets(f"rbi_pri_finances/{key}").values():
            cols = [j for j, c in enumerate(g[3]) if isinstance(c, str) and norm(c).startswith("all states")]
            if not cols:
                continue
            assert "per panchayat" in norm(g[2][1])
            j0 = cols[0]
            per = [str(int(h)) if isinstance(h, float) else str(h) for h in g[4][j0 : j0 + 3]]
            parent = ""
            for r in g[6:]:
                lab = r[1]
                if not isinstance(lab, str) or not lab.strip():
                    continue
                m = re.match(r"^(\d+) ", lab.strip())
                if m or not lab.strip().startswith("("):
                    parent = m.group(1) if m else ""
                    under = ""
                else:  # '(iii) Other Expenditure' appears under both 13 and 24: key by parent number
                    under = parent
                for k, p in enumerate(per):
                    v = num(r[j0 + k])
                    if v is not None:
                        key = (tid, under, norm(lab), p)
                        assert key not in raw, key
                        raw[key] = v
    # Chapter II PDF: pypdf text
    reader = PdfReader(str(raw_path("rbi_pri_finances/pri_ch2.pdf")))
    text = {i: re.sub(r"[ \t]+", " ", reader.pages[i].extract_text() or "") for i in range(6)}
    pdf: dict[tuple, float] = {}
    for code, (pg, rx) in PRI_PDF_LINES.items():
        m = re.search(rx, text[pg])
        assert m, (code, pg)
        for p, cell in zip(("2020-21", "2021-22", "2022-23"), m.groups(), strict=True):
            pdf[(code, p)] = float(cell.replace(",", ""))
    m1 = re.search(r"Number of Village Panchayats ([\d,]+)", text[0])
    m2 = re.search(r"Total (\d+) (\d+) [\d.]+ (\d+) [\d.]+", text[1])
    pdf[("n_village_panchayats", "2022-12-31")] = float(m1.group(1).replace(",", ""))
    pdf[("n_vp_total_table_ii2", "2022-23")] = float(m2.group(1))
    pdf[("n_vp_panel_receipts", "2022-23")] = float(m2.group(2))
    pdf[("n_vp_panel_expenditure", "2022-23")] = float(m2.group(3))
    assert pdf == {k: float(v) for k, v in PRI_PDF_TYPED.items()}  # pypdf re-parse == values read by eye
    bad, seen, n_pdf = [], set(), 0
    for r in rows:
        if r["series_id"].startswith("pri_ch2."):
            key = (r["item_code"], r["period"])
            v = pdf.get(key)
            n_pdf += 1
        else:
            path = r["item_code"].split("-")[0].split(".")
            under = path[-2] if norm(r["item_label"]).startswith("(") else ""
            key = (r["table_id"], under, norm(r["item_label"]), r["period"])
            v = raw.get(key)
            assert r["unit"] == "INR"
        seen.add(key)
        if v is None or not close(r["value"], v):
            bad.append((key, r["value"], v))
    report("rbi_pri", len(rows), bad)
    assert n_pdf == 31
    assert set(raw) | set(pdf) == seen


# --------------------------------------------------------------------------------------------- anchors
def test_gap_map_anchor_values():
    """Gap-map-critical 2023-24 figures, typed from the documents (and docs/phase0/GAP_MAP.md)."""
    kfi = {(r["item_code"].split("-")[0], r["period"]): r["value"] for r in clean("fc16_kfi")
           if r["dim_other"] == "state_group=all_states_28"}  # fmt: skip
    anchors = {"a_1_1_2": 800112, "a_1_1_1": 397467, "a_1_1_3": 249133, "a_1_1_4": 106021, "a_1_1_5": 220289,
               "a_1_3": 1129397, "a_1_4": 472466, "a_1_4_a": 43788, "b_1_a": 494911, "b_1_b": 494939}  # fmt: skip
    for code, want in anchors.items():
        assert round(kfi[(code, "2023-24")]) == want, code
    tr = {(r["series_id"], r["period"]): r["value"] for r in clean("fc16_transfers")}
    assert tr[("tsm.total_grants.actuals", "2023-24")] == 739260
    assert tr[("tsm.states_share.actuals", "2023-24")] == 1129494
    st = {(r["series_id"], r["period"]): r["value"] for r in clean("rbi_sf_statements")}
    assert st[("st13.interest_payments_gross.in.all_states_uts.actuals", "2023-24")] == 507175.4
    assert st[("st17.transfers_from_centre_gross.in.all_states_uts.actuals", "2023-24")] == 1800210.2
    assert st[("st36.subsidies.in.all_states_uts.actuals", "2023-24")] == 329610.4
    ap = {(r["series_id"], r["period"]): r["value"] for r in clean("rbi_sf_appendices")}
    sgst = "app1.total_revenue.i.a.3.vii-state_goods_and_services_tax.in.all_states_uts.actuals"
    assert abs(ap[(sgst, "2023-24")] - 841120.772) < 1e-6  # 8,41,12,077.2 lakh
    capout = "app4.total_capital_disbursements.i-total_capital_outlay.in.all_states_uts.actuals"
    assert round(ap[(capout, "2023-24")]) == 747306


def test_random_sample_printout():
    """Seeded sample across all datasets, printed with its raw locator for the verifier notes."""
    for ds in ("fc16_kfi", "fc16_transfers", "fc16_subsidies", "fc16_state_accounts", "fc16_local_body_assistance",
               "ulb_cityfinance", "rbi_sf_statements", "rbi_sf_app_tables", "rbi_sf_appendices", "rbi_municipal",
               "rbi_pri"):  # fmt: skip
        for r in sample(clean(ds), 3):
            print(ds, r["series_id"], r["period"], r["value"], r["unit"], r["status"])


# --------------------------------------------------------------------------------------------- systematic checks
def test_kfi_all_states_is_sum_of_states_and_c3a_sign():
    """All_States = sum of the 28 States (+ undivided AP) for every item and year except C.10 (India
    GDP by design); and C.3.a, labelled '(C.3+C.1.2.a)', is in fact C.3 - C.1.2.a (verify-7)."""
    raw, sn = _kfi_raw()
    inv = {v: k for k, v in sn.items()}
    states = [b for b in FC16 if b not in ("JK", "DL", "PY")] + ["AP_un"]
    for lab, s in sn.items():
        if s.startswith("e.") or s == "c.10":
            continue
        for yl in range(2012, 2025):
            a = raw.get((lab, "All_States", yl))
            if a is not None:
                assert abs(a - math.fsum(raw.get((lab, b, yl), 0) for b in states)) <= max(1, 1e-4 * abs(a)), (s, yl)
    c3 = next(k for k, v in sn.items() if v == "c.3" and k.startswith("outstanding"))
    n = 0
    for (lab, b, yl), x in raw.items():
        if lab == inv["c.3.a"] and raw.get((inv["c.1.2.a"], b, yl), 0):
            assert abs(x - (raw[(c3, b, yl)] - raw[(inv["c.1.2.a"], b, yl)])) < 0.01
            n += 1
    assert n > 100


# verify-2, fixed by the builder: strict xfail marker removed so this now guards against regression.
def test_kfi_no_zero_stocks_for_undivided_ap_after_bifurcation():
    bad = [r for r in clean("fc16_kfi") if r["dim_other"] == "boundary=undivided" and r["period"] == "2015-03-31"]
    assert not bad, [(r["item_code"], r["value"]) for r in bad]


# verify-3, fixed by the builder: strict xfail marker removed so this now guards against regression.
def test_kfi_gst_compensation_loan_nil_2023_24_is_kept():
    rows = {
        (r["item_code"].split("-")[0], r["period"])
        for r in clean("fc16_kfi")
        if r["dim_other"] == "state_group=all_states_28"
    }
    assert ("a_4_2_a", "2023-24") in rows and ("a_4_2_a", "2019-20") in rows


# verify-5, fixed by the builder: strict xfail marker removed so this now guards against regression.
def test_fc16_gtr_is_tagged_as_union():
    g = [r for r in clean("fc16_transfers") if r["item_code"] == "gtr"]
    assert g and all(r["institution"] == "gg_centre" for r in g)
    # second pass: no counterparty and no state_group either
    assert all(r["counterparty"] is None and not r["dim_other"] and r["geography"] == "IN" for r in g)


# --------------------------------------------------------------------------------------------- second pass (KFI rules)
# The builder's revised KFI rules (issues state_fiscal-3, after verify-2/3), re-implemented here from the
# rule TEXT only, then compared with the clean data in both directions.
KFI_NEH = ["AR", "AS", "HP", "MN", "ML", "MZ", "NL", "SK", "TR", "UK"]  # confirmed by sums below
KFI_28 = [b for b in FC16 if b not in ("JK", "DL", "PY")]
KFI_GROUPS = {
    "state_group=all_states_28": KFI_28 + ["AP_un"],
    "state_group=non_neh_states": [b for b in KFI_28 if b not in KFI_NEH] + ["AP_un"],
    "state_group=neh_states": KFI_NEH,
}
KFI_DEPENDENT = {"a.5": ["a.4"], "a.8": ["a.4"], "a.11": ["a.4", "a.10"], "b.8": ["b.6"], "b.11": ["b.6", "b.10"]}
KFI_HEADLESS = {"off-budget borrowings", "maximum amount guaranteed", "contingency fund (corpus)",
                "total debt receipts during the year", "total debt repayments", "total debt available (c.4-c.5)",
                "increase(+)/ decrease(-) in cash balance"}  # fmt: skip
KFI_FLOW_MEMO = {"total debt receipts during the year", "total debt repayments", "total debt available (c.4-c.5)",
                 "increase(+)/ decrease(-) in cash balance"}  # fmt: skip


class _Kfi:
    def __init__(self):
        self.raw, self.sn = _kfi_raw()
        self.lab = defaultdict(list)
        for lab, s in self.sn.items():
            self.lab[s].append(lab)
        self.rr = self.lab["a.1"][0]

    def v(self, sn: str, b: str, yl: int) -> float:
        return self.raw.get((self.lab[sn][0], b, yl), 0)

    def head(self, sn: str) -> str | None:
        if sn.startswith("a.4"):
            return "a.4"
        if sn.startswith("b.6"):
            return "b.6"
        return {"a.9": "a.10", "a.10": "a.10", "b.9": "b.10", "b.10": "b.10"}.get(sn)

    def alive_flow(self, b: str, yl: int) -> bool:
        return b not in ("AP", "TS", "AP_un") or self.raw.get((self.rr, b, yl), 0) != 0

    def is_stock(self, lab: str) -> bool:
        s = self.sn[lab]
        return s.startswith("c.") and s not in ("c.6", "c.9", "c.10") and lab not in KFI_FLOW_MEMO

    def not_compiled(self, b: str, yl: int, lab: str) -> list[str]:
        """Reasons why the (State) cell b/lab/yl is 'not compiled' under the builder's stated rule."""
        sn = self.sn[lab]
        if lab in KFI_HEADLESS:
            return ["self"] if self.raw.get((lab, b, yl), 0) == 0 else []
        if sn in ("a.4.2.a", "a.4.2.b"):
            return ["a.4.2"] if not any(self.v(s, b, yl) for s in ("a.4", "a.4.2.a", "a.4.2.b")) else []
        out = [h for h in [self.head(sn)] if h and self.v(h, b, yl) == 0]
        return out + [h for h in KFI_DEPENDENT.get(sn, []) if self.v(h, b, yl) == 0]


@pytest.fixture(scope="module")
def kfi():
    return _Kfi()


def _kfi_clean_key(r: dict) -> tuple[str, str, int]:
    return norm(r["item_label"]), _kfi_block(r), _kfi_year_label(r)


def test_kfi_reverse_census_under_revised_rules(kfi):
    """Every published KFI cell is either in clean or dropped by a stated rule, and nothing else: zeros are
    kept unless 'not compiled' (family head A.4/B.6/A.10/B.10 zero; A.4.2.a/b need A.4 or either of them
    non-zero; headless memo rows and C.8.a drop every zero); declared incomplete totals are dropped except
    West Bengal 2022-23; undivided AP has no stocks after end-March 2014 and no flows after 2014-15, AP/TS
    no stocks before end-March 2015. C.10 GSDP is a territorial series and is kept for all blocks (AP_un
    GSDP = AP + TS in every year, tested)."""
    raw, sn = kfi.raw, kfi.sn
    gsdp = kfi.lab["c.10"][0]
    for yl in range(2012, 2025):
        assert abs(raw[(gsdp, "AP_un", yl)] - raw[(gsdp, "AP", yl)] - raw[(gsdp, "TS", yl)]) < 0.01
    for grp, mem in (("NEH_States", KFI_NEH), ("non-NEH_States", KFI_GROUPS["state_group=non_neh_states"])):
        for yl in range(2012, 2025):
            assert abs(raw[(kfi.rr, grp, yl)] - math.fsum(raw.get((kfi.rr, b, yl), 0) for b in mem)) < 1
    expected = set()
    for (lab, b, yl), x in raw.items():
        s = sn[lab]
        if b in ("All_States", "non-NEH_States", "NEH_States") or s == "c.10":
            alive = True
        elif kfi.is_stock(lab):
            alive = (yl <= 2014) if b == "AP_un" else ((yl >= 2015) if b in ("AP", "TS") else True)
        else:
            alive = kfi.alive_flow(b, yl)
        if not alive:
            continue
        if x == 0 and kfi.not_compiled(b, yl, lab):
            continue
        if x != 0 and (s, yl) in KFI_DECLARED_NONZERO_DROPS and (b, yl) not in KFI_KEPT_EXCEPTIONS:
            continue
        expected.add((lab, b, yl))
    got = {_kfi_clean_key(r) for r in clean("fc16_kfi")}
    assert not expected - got, sorted(expected - got)[:10]
    assert not got - expected, sorted(got - expected)[:10]
    kept_zero = sum(1 for k in got if raw[k] == 0)
    n_zero = sum(1 for x in raw.values() if x == 0)
    print(f"KFI reverse census: {len(raw)} raw cells, {len(got)} clean, {kept_zero} zeros kept as nil, "
          f"{n_zero - kept_zero} zeros dropped")  # fmt: skip


def test_kfi_incomplete_flags_match_independent_derivation(kfi):
    """verify-3 second pass: a clean row must carry an 'INCOMPLETE' provenance record iff (group rows) some
    alive member State is not compiled for that item/year, or (State rows) the row is a total built on a
    not-compiled head. Derived here independently; must agree row by row (397 flagged rows)."""
    prov = {r["prov_id"]: r for r in pq.read_table(CLEAN / "_provenance.parquet").to_pylist()}
    under, over, n_flag = [], [], 0
    for r in clean("fc16_kfi"):
        lab, block, yl = _kfi_clean_key(r)
        flagged = "INCOMPLETE" in str(prov[r["prov_id"]]["notes"])
        n_flag += flagged
        if r["dim_other"] in KFI_GROUPS:
            alive = [b for b in KFI_GROUPS[r["dim_other"]] if kfi.alive_flow(b, yl)]
            exp = any(kfi.not_compiled(b, yl, lab) for b in alive)
        else:
            exp = kfi.sn[lab] in KFI_DEPENDENT and bool(kfi.not_compiled(block, yl, lab))
        if exp and not flagged:
            under.append((lab, block, yl, r["value"]))
        if flagged and not exp:
            over.append((lab, block, yl, r["value"]))
    assert not under, under[:10]
    assert not over, over[:10]
    assert n_flag == 397
    print(f"KFI INCOMPLETE flags: {n_flag} rows, independent derivation agrees")


def _c8a_2015_aggregates() -> list[dict]:
    return [
        r
        for r in clean("fc16_kfi")
        if r["item_code"].startswith("c_8_a")
        and r["period"] == "2015-03-31"
        and r["dim_other"] in ("state_group=all_states_28", "state_group=non_neh_states")
    ]


def test_kfi_c8a_2015_aggregate_includes_stale_undivided_ap(kfi):
    """verify-10 (second pass): the published All_States and non-NEH C.8.a at end-March 2015 equal the 28
    States PLUS undivided AP's stale 55,536.02 (a repeat of its end-March 2014 figure), although AP and
    Telangana report their own end-March 2015 guarantees. The unit drops the AP_un row but keeps the
    aggregates. This pins the source fact."""
    L = "maximum amount guaranteed"
    raw = kfi.raw
    un = raw[(L, "AP_un", 2015)]
    assert abs(un - raw[(L, "AP_un", 2014)]) < 0.05 and un > 55000
    assert raw[(L, "AP", 2015)] > 0 and raw[(L, "TS", 2015)] > 0
    s28 = math.fsum(raw.get((L, b, 2015), 0) for b in KFI_28)
    assert abs(raw[(L, "All_States", 2015)] - (s28 + un)) < 0.05
    non = [b for b in KFI_28 if b not in KFI_NEH]
    assert abs(raw[(L, "non-NEH_States", 2015)] - (math.fsum(raw.get((L, b, 2015), 0) for b in non) + un)) < 0.05
    assert len(_c8a_2015_aggregates()) == 2


# verify-10, fixed by the builder (state_fiscal-23): strict xfail marker removed in the close-out pass and the
# check made stricter: the note must carry the sums, re-derived here from raw, and no other row may carry it.
def test_kfi_c8a_2015_aggregate_note_names_undivided_ap(kfi):
    L = "maximum amount guaranteed"
    raw = kfi.raw
    # the only end-March-2015 stock of undivided AP that is non-zero is C.8.a (so only C.8.a aggregates are stale)
    stale_labels = {lab for (lab, b, yl), x in raw.items() if b == "AP_un" and yl == 2015 and kfi.is_stock(lab) and x}
    assert stale_labels == {L}, stale_labels
    prov = {r["prov_id"]: r for r in pq.read_table(CLEAN / "_provenance.parquet").to_pylist()}
    un = raw[(L, "AP_un", 2015)]
    want = {
        "state_group=all_states_28": ("All_States", KFI_28),
        "state_group=non_neh_states": ("non-NEH_States", [b for b in KFI_28 if b not in KFI_NEH]),
    }
    rows = _c8a_2015_aggregates()
    assert {r["dim_other"] for r in rows} == set(want)
    for r in rows:
        blk, mem = want[r["dim_other"]]
        tot = raw[(L, blk, 2015)]
        live = math.fsum(raw.get((L, b, 2015), 0) for b in mem)
        assert abs(tot - live - un) < 0.05 and close(r["value"], tot)
        note = prov[r["prov_id"]]["notes"]
        for piece in ("INCLUDES A STALE UNDIVIDED-AP FIGURE", f"({tot:,.2f})", f"({live:,.2f})", f"{un:,.2f}"):
            assert piece in note, (blk, piece, note)
    # typed from the second-pass notes (docs/phase1/verify/state_fiscal.md, verify-10)
    assert (round(raw[(L, "All_States", 2015)], 2), round(un, 2)) == (594159.08, 55536.02)
    tagged = [r for r in clean("fc16_kfi") if "STALE UNDIVIDED" in (prov[r["prov_id"]]["notes"] or "")]
    assert sorted(r["dim_other"] for r in tagged) == sorted(want), [(r["series_id"], r["period"]) for r in tagged]


def _kfi_stock_exists(kfi: _Kfi, b: str, lab: str, yl: int) -> bool:
    """Block b has a figure for (lab, yl): flows while the block was alive that FY; end-March stocks only
    while the territory existed on that date (undivided AP to end-March 2014, AP/TS from end-March 2015)."""
    if not kfi.is_stock(lab):
        return kfi.alive_flow(b, yl)
    if b == "AP_un":
        return yl <= 2014
    if b in ("AP", "TS"):
        return yl >= 2015
    return True


def test_kfi_incomplete_notes_name_exactly_the_existing_uncompiled_blocks(kfi):
    """verify-12 (close-out): an INCOMPLETE note must name exactly the blocks that (a) exist at that date or
    in that year and (b) are not compiled under the stated rule, derived here independently. In particular
    undivided AP may not be named for stocks dated after it ceased (C.3 corpus, end-March 2015)."""
    prov = {r["prov_id"]: r for r in pq.read_table(CLEAN / "_provenance.parquet").to_pylist()}
    bad, n = [], 0
    tok = r"(?:AP_un|[A-Z]{2})(?![A-Za-z_])"
    for r in clean("fc16_kfi"):
        note = prov[r["prov_id"]]["notes"] or ""
        if "INCOMPLETE" not in note:
            continue
        n += 1
        lab, block, yl = _kfi_clean_key(r)
        named: set[str] = set()
        for m in re.finditer(rf"not compiled for ({tok}(?:, {tok})*)", note):
            named |= set(m.group(1).split(", "))
        if r["dim_other"] in KFI_GROUPS:
            mem = KFI_GROUPS[r["dim_other"]]
            exp = {b for b in mem if _kfi_stock_exists(kfi, b, lab, yl) and kfi.not_compiled(b, yl, lab)}
        else:
            exp = {block}
        if named != exp:
            bad.append((r["series_id"], r["period"], sorted(named ^ exp)))
    assert n == 397
    assert not bad, bad[:10]
    print(f"KFI INCOMPLETE notes: {n} rows, named blocks agree with the independent derivation")


# --------------------------------------------------------------------------------------------- close-out pass (D1-9)
ALL_DATASETS = ("fc16_kfi", "fc16_transfers", "fc16_subsidies", "fc16_state_accounts", "fc16_local_body_assistance",
                "ulb_cityfinance", "rbi_sf_statements", "rbi_sf_app_tables", "rbi_sf_appendices", "rbi_municipal",
                "rbi_pri")  # fmt: skip
TERRITORY_REASON = ("SUCCESSOR-TERRITORY FIGURE", "TERRITORIAL AGGREGATE, NOT ADDITIVE", "1 April-1 June 2014",
                    "Territories (DECISIONS D1-9)", "31 Oct 2019")  # fmt: skip


def _fy_range(a: int, b: int) -> list[str]:
    return [f"{y}-{(y + 1) % 100:02d}" for y in range(a, b + 1)]


def _expected_territory_exception(ds: str, r: dict, cls: str) -> bool:
    """The verifier's own list of rows that may sit outside their territory's existence (derived from what the
    raw files contain, not from the unit's TERRITORY_DECLARED)."""
    g, p, gsdp = r["geography"], r["period"], r["item_code"].startswith("c_10-")
    if ds == "fc16_kfi":
        if cls == "before":  # successor-territory GSDP only
            return g in ("IN-AP", "IN-TS") and p in _fy_range(2011, 2013) and gsdp
        if cls == "straddle":  # FY 2014-15: accounts split at 2 June 2014
            return g in ("IN-AP", "IN-TS", "IN-XAP") and p == "2014-15"
        if cls == "after":  # undivided-AP GSDP as a territorial series only
            return g == "IN-XAP" and p in _fy_range(2015, 2023) and gsdp
    if ds in ("fc16_state_accounts", "fc16_local_body_assistance") and cls == "straddle":
        return (g in ("IN-AP", "IN-TS", "IN-XAP") and p == "2014-15") or (
            g in ("IN-UP", "IN-UK", "IN-JH") and p == "2000-01"
        )
    if ds in ("rbi_sf_statements", "rbi_municipal") and cls == "straddle":
        return g == "IN-JK" and p == "2019-20"
    return False


def _territory_rows() -> tuple[dict, dict]:
    prov = {r["prov_id"]: r for r in pq.read_table(CLEAN / "_provenance.parquet").to_pylist()}
    out: dict[tuple, list] = defaultdict(list)
    known = set(ISO.values()) | set(TERR_TO) | {"IN"}
    for ds in ALL_DATASETS:
        for r in clean(ds):
            assert r["geography"] in known, (ds, r["geography"])
            cls = territory_class(r["geography"], r["period"], r["period_type"])
            if cls:
                out[(ds, r["geography"], r["period"], cls)].append(r)
    return out, prov


def test_geography_codes_match_territory_calendar():
    """Close-out (D1-9): every row's geography is a territory that existed for the whole period, except exactly
    the expected cases (successor-territory and territorial GSDP; the FY 2014-15 AP split; FY 2000-01 in the
    accounts; J&K FY 2019-20 in RBI St 36 and Municipal Finances). Each expected case must be present, the
    GSDP cases must carry their own provenance records, and IN-XAP / IN-XJK must never appear outside them."""
    out, prov = _territory_rows()
    unexpected = [
        (k, len(v)) for k, v in out.items() if not all(_expected_territory_exception(k[0], r, k[3]) for r in v)
    ]
    assert not unexpected, unexpected
    found = set(out)
    must = {("fc16_kfi", g, p, "before") for g in ("IN-AP", "IN-TS") for p in _fy_range(2011, 2013)}
    must |= {("fc16_kfi", g, "2014-15", "straddle") for g in ("IN-AP", "IN-TS", "IN-XAP")}
    must |= {("fc16_kfi", "IN-XAP", p, "after") for p in _fy_range(2015, 2023)}
    must |= {("fc16_state_accounts", g, "2014-15", "straddle") for g in ("IN-AP", "IN-TS", "IN-XAP")}
    must |= {("fc16_state_accounts", g, "2000-01", "straddle") for g in ("IN-UP", "IN-UK", "IN-JH")}
    must |= {("fc16_local_body_assistance", g, "2014-15", "straddle") for g in ("IN-AP", "IN-TS", "IN-XAP")}
    must |= {("fc16_local_body_assistance", g, "2000-01", "straddle") for g in ("IN-UP", "IN-JH")}
    must |= {(ds, "IN-JK", "2019-20", "straddle") for ds in ("rbi_sf_statements", "rbi_municipal")}
    assert found == must, sorted(found ^ must)
    # GSDP records: successor-territory for AP/TS FY 2011-12..2014-15; territorial for undivided AP from 2014-15
    n = 0
    for r in clean("fc16_kfi"):
        if not r["item_code"].startswith("c_10-") or r["geography"] not in ("IN-AP", "IN-TS", "IN-XAP"):
            continue
        note = prov[r["prov_id"]]["notes"]
        succ = r["geography"] != "IN-XAP" and r["period"] <= "2014-15"
        terr = r["geography"] == "IN-XAP" and r["period"] >= "2014-15"
        assert note.startswith("SUCCESSOR-TERRITORY FIGURE") == succ, (r["series_id"], r["period"])
        assert note.startswith("TERRITORIAL AGGREGATE, NOT ADDITIVE") == terr, (r["series_id"], r["period"])
        n += succ + terr
    assert n == 18
    # no IN-XAP stock after end-March 2014 and no AP/TS stock before end-March 2015
    kfi = clean("fc16_kfi")
    stocks = [r for r in kfi if r["period_type"] == "date"]
    assert not [r for r in stocks if r["geography"] == "IN-XAP" and r["period"] > "2014-03-31"]
    assert not [r for r in stocks if r["geography"] in ("IN-AP", "IN-TS") and r["period"] < "2015-03-31"]


def test_fy_2000_01_partial_years_by_magnitude(accounts):
    """The builder's inference (provenance of the accounts): FY 2000-01 UK and JH rows cover only the months after
    creation, UP's the whole year. Re-derived from raw revenue receipts (Rs crore): UK 924 vs 2,608 next year,
    JH 1,964 vs 4,444, UP 25,598 vs 27,821. Also: undivided AP's FY 2014-15 is about two months, and the dump
    has no J&K FY 2019-20."""
    mh, _ = accounts

    def rr(st: str, yl: int) -> float:
        return math.fsum(v for k, v in mh.items() if k[0] == st and k[1] == yl and k[2] == "Revenue Rec")

    got = {st: (round(rr(st, 2001)), round(rr(st, 2002))) for st in ("UK", "JH", "UP")}
    assert got == {"UK": (924, 2608), "JH": (1964, 4444), "UP": (25598, 27821)}, got
    assert rr("UK", 2001) / rr("UK", 2002) < 0.5 and rr("JH", 2001) / rr("JH", 2002) < 0.5
    assert rr("UP", 2001) / rr("UP", 2002) > 0.85
    ap_un, ap, ts, prev = rr("AP_un", 2015), rr("AP", 2015), rr("TS", 2015), rr("AP_un", 2014)
    assert 0.1 < ap_un / prev < 0.3 and 0.9 < (ap_un + ap + ts) / prev < 1.5, (ap_un, ap, ts, prev)
    jk = sorted({k[1] for k in mh if k[0] == "JK"})
    assert jk == [2014, 2015, 2016, 2017, 2018, 2019, 2021], jk


def test_territory_calendar_matches_geo_module_text():
    """The verifier's calendar agrees with the project code set (read as TEXT, not imported)."""
    t = (ROOT / "pipeline" / "core" / "geo.py").read_text(encoding="utf-8")
    for code, last, succ, start in (("IN-XAP", "2014-06-01", "IN-AP + IN-TS", "2014-06-02"),
                                    ("IN-XJK", "2019-10-30", "IN-JK + IN-LA", "2019-10-31"),
                                    ("IN-XMP", "2000-10-31", "IN-MP + IN-CG", "2000-11-01"),
                                    ("IN-XUP", "2000-11-08", "IN-UP + IN-UK", "2000-11-09"),
                                    ("IN-XBR", "2000-11-14", "IN-BR + IN-JH", "2000-11-15")):  # fmt: skip
        m = re.search(rf'"{code}": \("[^"]*", "{last}", "{re.escape(succ)}[^"]* from {start}"\)', t)
        assert m, code
        for c in succ.split(" + "):
            assert TERR_FROM[c] == start, c
        assert TERR_TO.get(code, last) == last
    # state_fiscal-22 (framework's one-token edit to this file): IN-CT is superseded by IN-CG
    assert '"IN-CG": ("Chhattisgarh", "state")' in t and '"IN-CT": "IN-CG' in t


def _territory_reason_expected(ds: str, r: dict, cls: str) -> tuple[str, ...]:
    """Final pass: the CASE-SPECIFIC text (verifier's calendar dates or GSDP record heading) that the record of an
    out-of-lifetime row must carry. Stricter than the unit's guard, which accepts any 'DECISIONS D1-9' citation."""
    g, p, gsdp = r["geography"], r["period"], ds == "fc16_kfi" and r["item_code"].startswith("c_10-")
    if gsdp and g in ("IN-AP", "IN-TS"):
        return ("SUCCESSOR-TERRITORY FIGURE", "2 June 2014")
    if gsdp and g == "IN-XAP":
        return ("TERRITORIAL AGGREGATE, NOT ADDITIVE", "2 June 2014")
    if p == "2014-15" and g in ("IN-AP", "IN-TS", "IN-XAP"):
        return ("1 April-1 June 2014", "2 June 2014")
    if p == "2000-01":
        return {"IN-UP": ("8 Nov 2000",), "IN-UK": ("9 Nov 2000",), "IN-JH": ("15 Nov 2000",)}[g]
    if p == "2019-20" and g == "IN-JK":
        return ("31 Oct 2019",)
    raise AssertionError(("unexpected out-of-lifetime row", ds, g, p, cls))


def test_every_out_of_lifetime_row_states_the_reason():
    """verify-13, FIXED in the final pass (strict xfail removed, check made stricter). Every row outside its
    territory's lifetime (1,178 rows) must sit on a record whose notes (a) carry the generic reason marker and
    (b) state the case-specific dates from the verifier's own calendar. Before the fix the KFI E.* ratio record
    (AP, TS, undivided AP FY 2014-15; 9 rows) and the J&K FY 2019-20 Municipal per-cent-of-GSDP records (3 rows)
    had no such notes."""
    out, prov = _territory_rows()
    n, silent, unspecific = 0, [], []
    for (ds, _g, _p, cls), v in out.items():
        for r in v:
            n += 1
            note = prov[r["prov_id"]]["notes"] or ""
            if not any(s in note for s in TERRITORY_REASON):
                silent.append((ds, r["series_id"], r["period"]))
            if not all(s in note for s in _territory_reason_expected(ds, r, cls)):
                unspecific.append((ds, r["series_id"], r["period"]))
    assert n == 1178, n
    assert not silent, (len(silent), silent[:12])
    assert not unspecific, (len(unspecific), unspecific[:12])
    # the 12 rows of verify-13 by name: 9 KFI E.* rows + 3 Municipal pct rows, now each on a noted record
    e_rows = [r for (ds, g, p, _), v in out.items() for r in v if ds == "fc16_kfi" and r["item_code"].startswith("e_")]
    pct = [r for (ds, g, p, _), v in out.items() for r in v if ds == "rbi_municipal" and "_pct_gsdp" in r["item_code"]]
    assert len(e_rows) == 9 and {r["geography"] for r in e_rows} == {"IN-AP", "IN-TS", "IN-XAP"}
    assert len({r["prov_id"] for r in e_rows}) == 1 and len(pct) == 3
    assert {r["table_id"] for r in pct} == {"Statement 1", "Statement 4", "Statement 8"}
    print(f"out-of-lifetime rows: {n}, all on records stating the case-specific reason")


def test_kfi_ratios_2014_15_are_within_block_from_raw(kfi):
    """verify-13 fix, re-derived from raw: the E.* ratios are within-block, within-year ratios, so the FY 2014-15
    AP_un ratios describe 1 April-1 June 2014 exactly as its flows do (the ratio record now says so).
    KFI 'State-wise', year column '2015': E.1 = B.1.a / A.1, E.2 = (B.1.a + B.1.b + B.1.c) / A.1 and
    E.3 = D.1 / D.2, to machine precision, for AP, TS and AP_un. E.1 = B.1.a / A.1 also holds for every block
    and year with A.1 != 0. The clean values equal the raw ratios to 6 decimals."""
    rel = lambda a, b: abs(a - b) <= 1e-12 * max(1.0, abs(b))  # noqa: E731
    want = {}
    for b in ("AP", "TS", "AP_un"):
        a1, ia, pn, sal = (kfi.v(s, b, 2015) for s in ("a.1", "b.1.a", "b.1.b", "b.1.c"))
        d1, d2 = kfi.v("d.1", b, 2015), kfi.v("d.2", b, 2015)
        e = [kfi.v(s, b, 2015) for s in ("e.1", "e.2", "e.3")]
        assert a1 and d2, b
        assert rel(e[0], ia / a1) and rel(e[1], (ia + pn + sal) / a1) and rel(e[2], d1 / d2), (b, e)
        want[{"AP": "IN-AP", "TS": "IN-TS", "AP_un": "IN-XAP"}[b]] = e
    assert round(want["IN-XAP"][0], 6) == 0.083715  # 2,090.95 / 24,977.05
    n = 0
    for (lab, b, yl), v in kfi.raw.items():
        if kfi.sn[lab] == "e.1" and kfi.v("a.1", b, yl):
            n += 1
            assert rel(v, kfi.v("b.1.a", b, yl) / kfi.v("a.1", b, yl)), (b, yl)
    assert n > 350, n
    got = {(r["geography"], int(r["item_code"][2]) - 1): r["value"] for r in clean("fc16_kfi")
           if r["period"] == "2014-15" and r["item_code"].startswith("e_")
           and r["geography"] in ("IN-AP", "IN-TS", "IN-XAP")}  # fmt: skip
    assert len(got) == 9
    for (g, k), val in got.items():
        assert abs(val - want[g][k]) <= 5.000001e-7, (g, k, val, want[g][k])


def test_municipal_jk_2019_20_pct_rows_from_raw():
    """verify-13 fix: the three J&K FY 2019-20 per-cent-of-GSDP rows, read from raw row '11. Jammu and Kashmir'
    of Statements 1, 4 and 8 (column '2019-20 (Accounts)' under 'Per cent of GSDP'): 0.09, 0.1 and 0.01. Each
    sits on a record carrying the 31 Oct 2019 sentence, like the level rows."""
    prov = {r["prov_id"]: r for r in pq.read_table(CLEAN / "_provenance.parquet").to_pylist()}
    mine = {(r["table_id"], r["item_code"].endswith("_pct_gsdp")): r for r in clean("rbi_municipal")
            if r["geography"] == "IN-JK" and r["period"] == "2019-20"}  # fmt: skip
    assert len(mine) == 6
    for k, want in (("01", 0.09), ("04", 0.1), ("08", 0.01)):
        g = grid(f"rbi_municipal_finances/muni_st{k}.xlsx")
        row = [x for x in g if isinstance(x[1], str) and norm(x[1]) == "11. jammu and kashmir"]
        hdr = next(x for x in g if any(norm(c) == "per cent of gsdp" for c in x))
        j = [c for c, h in enumerate(hdr) if norm(h) == "per cent of gsdp"][0]
        assert len(row) == 1 and num(row[0][j]) == want, (k, row)
        r = mine[(f"Statement {int(k)}", True)]
        assert r["value"] == want and r["unit"] == "percent", r
        for pct in (True, False):
            assert "31 Oct 2019" in prov[mine[(f"Statement {int(k)}", pct)]["prov_id"]]["notes"]


def test_s9_state_provident_funds_are_gross_lines_from_raw():
    """S9 (state_fiscal-25b), re-derived from raw. RBI SF 2025-26, All States and UTs, 2023-24 (Accounts),
    Rs lakh: Appendix III VI.1 'State Provident Funds' 1,03,89,237.1 and Appendix IV VII.1 91,39,849.3
    (= 1,03,892.371 / 91,398.493 crore). Both are gross public-account lines: App III's footnote '*' says only
    the '(Includes Public Accounts on a net basis)' total nets items IV-X and XII, and App IV's '$' total
    'Excluding Public Accounts' is items I-IV only. The coverage entry cites exactly these two series."""
    ids = {}
    for key, tid, top, star in (("sf2526_appx3_all.xlsx", "app3", "vi. state provident funds, etc. (1 + 2)",
                                 "items iv to x, xii and i(4) are on a net basis"),
                                ("sf2526_appx4_all.xlsx", "app4", "vii. state provident funds, etc. (1 + 2)",
                                 "sum of items i to iv")):  # fmt: skip
        items, periods = _appendix_all_states(f"rbi_state_finances_study/{key}")
        labs = [lab for lab, _ in items]
        i = labs.index(top)
        assert labs.count(top) == 1 and labs[i + 1] == "1. state provident funds" and labs[i + 2] == "2. others"
        tot, one, two = (tuple(num(c) for c in items[i + k][1]) for k in range(3))
        assert all(abs(a - (b + c)) <= 0.2 for a, b, c in zip(tot, one, two, strict=True)), (tot, one, two)
        assert periods[0] == ("2023-24", "Actuals"), periods
        assert any(star in lab for lab in labs), star
        ids[tid] = (one[0], two[0])
        assert any("jammu and kashmir for 2023-24" in lab and "cag" in lab for lab in labs)
    assert ids["app3"][0] == 10389237.1 and ids["app4"][0] == 9139849.3, ids
    items3, _ = _appendix_all_states("rbi_state_finances_study/sf2526_appx3_all.xlsx")
    assert any("state provident funds also includes other savings deposits" in lab for lab, _ in items3)
    # clean rows and the coverage declaration
    cov = yaml.safe_load((ROOT / "pipeline" / "ingest" / "state_fiscal_coverage.yaml").read_text(encoding="utf-8"))
    assert cov["unit"] == "state_fiscal"
    s9 = [e for e in cov["entries"] if e["ref"] == "S9"]
    assert len(s9) == 1 and s9[0]["extent"] == "partial" and s9[0]["dataset"] == "state_fiscal_rbi_sf_appendices"
    sids = s9[0]["series_ids"]
    rows = {r["series_id"]: r for r in clean("rbi_sf_appendices") if r["period"] == "2023-24"
            and r["estimate_stage"] == "Actuals"}  # fmt: skip
    assert len(sids) == 2 and all(s in rows for s in sids), sids
    got = sorted(rows[s]["value"] for s in sids)
    assert abs(got[0] - 91398.493) < 1e-6 and abs(got[1] - 103892.371) < 1e-6, got
    assert all(rows[s]["stock_flow"] == "flow" and rows[s]["unit"] == "INR_crore" for s in sids)
    note = s9[0]["note"]
    for must in ("1,03,892.37", "91,398.49", "other savings deposits", "not claimed", "provisional"):
        assert must in note, must


def _changed_row_frame() -> dict[str, list[tuple[str, dict]]]:
    """Rows changed by the D1-9 follow-up (and the framework's CT -> CG edit, state_fiscal-22), by group.
    Frame restricted to datasets re-derived here by direct cell addressing; the ULB and St 13-17 IN-CG rows are
    covered by the full censuses above."""
    prov = {r["prov_id"]: r for r in pq.read_table(CLEAN / "_provenance.parquet").to_pylist()}
    marks = ("SUCCESSOR-TERRITORY", "TERRITORIAL AGGREGATE", "STALE UNDIVIDED")
    fr: dict[str, list] = defaultdict(list)
    for ds in ("fc16_kfi", "fc16_state_accounts", "fc16_local_body_assistance", "fc16_subsidies", "rbi_municipal",
               "rbi_sf_statements"):  # fmt: skip
        for r in clean(ds):
            g, note = r["geography"], prov[r["prov_id"]]["notes"] or ""
            if ds == "rbi_sf_statements" and r["table_id"] != "Statement 36":
                continue
            if g in ("IN-XAP", "IN-XJK", "IN-CG"):
                fr[f"{ds}:{g}"].append((ds, r))
            elif ds == "fc16_kfi" and (
                any(m in note for m in marks)
                or (r["item_code"].startswith("c_3-") and r["period"] == "2015-03-31" and g == "IN")
            ):
                fr["fc16_kfi:new records"].append((ds, r))
            elif g == "IN-JK" and r["period"] == "2019-20":
                fr[f"{ds}:IN-JK 2019-20"].append((ds, r))
    return fr


def test_changed_rows_seeded_sample_against_raw():
    """Close-out sample: in every group of changed rows, max(10%, min(30, n)) rows (seeded from 20260929) are
    re-derived from the pinned raw file by a SECOND path: KFI and RBI/FC16 tables by direct cell addressing
    (header + label lookup in the calamine grid), the accounts dump by Decimal sums over the raw minor-head
    rows. Value, period, geography (verifier's calendar) and series-id suffix must all agree."""
    from decimal import Decimal

    fr = _changed_row_frame()
    picks: list[tuple[str, dict]] = []
    for grp in sorted(fr):
        rows = sorted(fr[grp], key=lambda t: (t[1]["series_id"], t[1]["period"], t[1]["estimate_stage"]))
        k = max(math.ceil(0.10 * len(rows)), min(30, len(rows)))
        picks += random.Random(f"{SEED}:{grp}").sample(rows, k)
        print(f"sample {grp}: {k} of {len(rows)}")
    # KFI: direct addressing (block header column + year offset, row by printed description)
    kg = grid("fc16_relevant_data/fc16_kfi.xlsx", "State-wise")
    kcol = {c: j for j, c in enumerate(kg[0]) if isinstance(c, str) and c and j >= 4}
    krow: dict[str, list] = {}
    for r in kg[1:]:
        if isinstance(r[2], str) and r[2].strip():
            assert norm(r[2]) not in krow
            krow[norm(r[2])] = r
    # accounts dump: Decimal sums over the raw minor-head rows of the sampled keys only
    acc_keys, lb_keys = set(), set()
    for ds, r in picks:
        base = (_acc_state(r), int(r["period"][:4]) + 1, _acc_account(r)) if ds.startswith("fc16_") and (
            ds.endswith("accounts") or ds.endswith("assistance")) else None  # fmt: skip
        if ds == "fc16_state_accounts":
            acc_keys.add((*base, r["item_code"].removeprefix("mh_")))
        if ds == "fc16_local_body_assistance":
            lb_keys.add((*base, r["item_code"].removeprefix("minor_")))
    sums: dict[tuple, Decimal] = defaultdict(Decimal)
    g = grid("fc16_relevant_data/fc16_state_accounts.xlsx", "ServiceHeads")
    ix = {h: i for i, h in enumerate(g[0])}
    for r in g[1:]:
        a = r[ix["Amount"]]
        if a in ("", None):
            continue
        base = (r[ix["State Abb"]], int(float(r[ix["Year"]])), r[ix["Classification"]])
        ka, kl = (*base, str(r[ix["Major Head"]])), (*base, str(r[ix["Minor Head"]]))
        if ka in acc_keys:
            sums[("mh", *ka)] += Decimal(str(a))
        if kl in lb_keys:
            sums[("mn", *kl)] += Decimal(str(a))
    sub = grid("fc16_relevant_data/fc16_subsidies.xlsx")
    muni = {f"Statement {int(k[-2:])}": grid(f"rbi_municipal_finances/muni_st{k}.xlsx") for k in ("01", "04", "08")}
    st36 = grid("rbi_state_finances_study/sf2526_st36.xlsx")
    bad, n = [], 0
    for ds, r in picks:
        g, v = r["geography"], r["value"]
        if g != "IN":
            suffix = g.lower() + (".undivided" if g == "IN-XAP" else "")
            assert f".{suffix}" in r["series_id"], (r["series_id"], suffix)
        if ds == "fc16_kfi":
            yl = _kfi_year_label(r)
            want = num(krow[norm(r["item_label"])][kcol[_kfi_block(r)] + 1 + (yl - 2012)])
        elif ds in ("fc16_state_accounts", "fc16_local_body_assistance"):
            st, yl, cl = _acc_state(r), int(r["period"][:4]) + 1, _acc_account(r)
            if ds == "fc16_state_accounts":
                key = ("mh", st, yl, cl, r["item_code"].removeprefix("mh_"))
            else:
                key = ("mn", st, yl, cl, r["item_code"].removeprefix("minor_"))
            want = float(sums[key] / 100) if key in sums else None
        elif ds == "fc16_subsidies":
            sector = norm(r["item_label"].split(":", 1)[1])
            row = [x for x in sub[2:] if norm(x[0]) == "chhattisgarh" and norm(x[1]) == sector]
            cols = [j for j in range(2, 10) if norm(sub[1][j]).split(" ")[0] == r["period"]]
            assert len(row) == 1 and len(cols) == 1, (sector, r["period"])
            want = num(row[0][cols[0]])
        elif ds == "rbi_municipal":
            mg = muni[r["table_id"]]
            numbered = [x for x in mg[5:] if isinstance(x[1], str) and re.match(r"^\d+\.", x[1].strip())]
            row = [x for x in numbered if state_iso(x[1]) == g]
            pct = r["item_code"].endswith("_pct_gsdp")
            hdr_row, rng = (4, range(7, 12)) if pct else (3, range(2, 7))
            cols = [c for c in rng if rbi_head(mg[hdr_row][c]) == (r["period"], r["estimate_stage"])]
            assert len(row) == 1 and len(cols) == 1, (r["series_id"], r["period"])
            x = num(row[0][cols[0]])
            want = None if x is None else x / (1 if pct else 100)
        else:  # Statement 36
            row = [x for iso, x in _statement_rows(st36, 5) if iso == g]
            want_head = (r["period"], r["estimate_stage"])
            cols = [c for c in range(2, 10) if rbi_head(st36[3][c].replace("(", " (")) == want_head]
            assert len(row) == 1 and len(cols) == 1, (r["series_id"], r["period"])
            want = num(row[0][cols[0]])
        n += 1
        if want is None or abs(v - want) > 1e-6 * max(1.0, abs(want)):
            bad.append((ds, r["series_id"], r["period"], v, want))
    report("changed-rows sample", n, bad)
    total = sum(len(v) for v in fr.values())
    assert n >= max(30, math.ceil(0.10 * total)), (n, total)
