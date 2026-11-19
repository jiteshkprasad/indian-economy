"""Independent verification of ingest unit union_fiscal (Phase 1 verifier, first pass, 2026-09-29).

This file does NOT import pipeline.ingest.union_fiscal (nor pipeline.core). Every pinned raw file is
re-read with a different parser than the unit uses:
- Finance Accounts St 8 / St 9 and the Budget 2025-26 PDFs (tr, ntr, Annex 8): pypdf page text
  (the unit uses pdfplumber word positions). Values are matched by the head-of-account code or the
  printed label, never by position; the Rs-thousand amounts are compared digit for digit in the
  publisher's 2-digit grouping ('8,74,16,21,62' = 87,416.2162 crore).
- every XLSX and the PPAC XLS: python-calamine cell grids (the unit uses openpyxl / xlrd).
- the NSI HTML table: lxml.html (the unit uses BeautifulSoup).
- literal values typed by the verifier after reading the page text (HAND_* constants below).
Clean data are read with pyarrow.parquet.

Coverage: a census of every clean row of all 8 datasets against its raw cell, plus a line-level
check (code + context + value column) of every Finance Accounts minor head, and a reverse check
that every head printed in the Finance Accounts has a clean row. Each test prints
'SPOTCHECK <dataset>: checked=N mismatched=M' (run with -s to see the counts).

Close-out pass (2026-09-29): the three strict xfails (verify-1/2/3) became real tests after the
builder's fixes; the Statement 21 index knows '3.01'-style sub-items; the pin count is 41. The four
new datasets are checked by their own independent parsers (census of every row, reverse census,
closures and cross-document identities) plus a fixed-seed provenance-locator sample:
- union_fiscal_gcca (Expenditure Profile Statement 6): calamine grid; items are paired with value
  lines in print order inside each demand block, so wrapped labels, a label head printed above its
  number and two items printed in one cell are handled without special cases (the unit: openpyxl).
- union_fiscal_fa_gia (Finance Accounts, Appendix to St 9) and union_fiscal_fa_provident_funds
  (St 14): pypdf page text, amounts read from the right of each line (the unit: pdfplumber words
  split by x-position).
- union_fiscal_pib_gst: lxml text and innermost table (the unit: BeautifulSoup).
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections import Counter, defaultdict
from functools import cache
from pathlib import Path

import lxml.html
import pyarrow.parquet as pq
import pytest
import yaml
from pypdf import PdfReader
from python_calamine import CalamineWorkbook

pytestmark = pytest.mark.quality

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean" / "union_fiscal"
CGA = "cga_finance_accounts_aag"
MOF = "mof_union_budget_2026_27"
TRF = "union_budget_transfers_to_states"
VINTAGE_YEAR = {"2024-07-23": "2022-23", "2025-02-01": "2023-24", "2026-02-01": "2024-25"}
TAG = {"2024-07-23": "b2425", "2025-02-01": "b2526", "2026-02-01": "b2627"}
TOTALS: Counter = Counter()


# --------------------------------------------------------------------------------------------- helpers
@cache
def _pins() -> dict:
    return yaml.safe_load((ROOT / "data" / "raw_pins" / "union_fiscal.yaml").read_text(encoding="utf-8"))["pins"]


@cache
def raw_path(key: str) -> Path:
    pin = _pins()[key]
    p = ROOT / pin["path"]
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    assert h == pin["sha256"], f"{key}: file hash {h} != pin {pin['sha256']}"
    return p


@cache
def clean(ds: str) -> list[dict]:
    return pq.read_table(CLEAN / f"union_fiscal_{ds}.parquet").to_pylist()


@cache
def prov() -> dict[str, dict]:
    return {r["prov_id"]: r for r in pq.read_table(CLEAN / "_provenance.parquet").to_pylist()}


@cache
def pdf_pages(key: str) -> tuple[str, ...]:
    return tuple(p.extract_text() or "" for p in PdfReader(str(raw_path(key))).pages)


@cache
def grid(key: str, sheet: int | str = 0) -> list[list]:
    wb = CalamineWorkbook.from_path(str(raw_path(key)))
    name = wb.sheet_names[sheet] if isinstance(sheet, int) else sheet
    return wb.get_sheet_by_name(name).to_python(skip_empty_area=False)


@cache
def sheets(key: str) -> dict[str, list[list]]:
    wb = CalamineWorkbook.from_path(str(raw_path(key)))
    return {n: wb.get_sheet_by_name(n).to_python(skip_empty_area=False) for n in wb.sheet_names}


def norm(s: object) -> str:
    s = unicodedata.normalize("NFKC", str(s if s is not None else ""))
    return re.sub(r"\s+", " ", s).strip().lower()


def squash(s: object) -> str:
    """Letters and digits only (label comparison that ignores spacing and punctuation)."""
    return re.sub(r"[^a-z0-9]", "", norm(s))


def num(x: object) -> float | None:
    """Verifier's own Budget cell reader: '...' and '..' are nil (0), blanks and '-' are missing."""
    if x is None or isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return None if (isinstance(x, float) and math.isnan(x)) else float(x)
    s = unicodedata.normalize("NFKC", str(x)).strip()
    if s in ("", "-", "–", "—"):
        return None
    if s in ("...", "..", "…"):
        return 0.0
    s = s.replace(",", "")
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        return float(s)
    raise ValueError(f"unexpected cell {x!r}")


def cellnum(x: object) -> float | None:
    """num() for grids whose value column also holds header text: text cells are not numbers."""
    try:
        return num(x)
    except ValueError:
        return None


def dims(r: dict) -> dict[str, str]:
    return dict(kv.split("=", 1) for kv in (r.get("dim_other") or "").split(";") if kv)


def report(name: str, checked: int, bad: list, unresolved: int = 0) -> None:
    TOTALS["checked"] += checked
    TOTALS["mismatched"] += len(bad)
    print(f"\nSPOTCHECK {name}: checked={checked} mismatched={len(bad)} unresolved={unresolved}")
    for b in bad[:25]:
        print("   ", b)


def close(a: float, b: float, tol: float = 0.005) -> bool:
    return abs(a - b) <= tol


# --------------------------------------------------------------------------------------------- raw pins
def test_all_pinned_files_hash_ok():
    """41 pins after the follow-up pass: the first pass's 30, plus the Finance Accounts St 14 and the
    Appendix to St 9, three Statement 6 xlsx and six PIB pages (form, three archive listings, two
    releases). Every provenance record points at a pinned file, and the only pins no record uses are
    the C&AG certificate and the PIB archive pages that locate the releases."""
    keys = list(_pins())
    assert len(keys) == 41
    for k in keys:
        raw_path(k)
    pinned = {_pins()[k]["path"]: k for k in keys}
    used = {r["raw_path"] for r in prov().values() if r["raw_path"]}
    assert used <= set(pinned), used - set(pinned)
    unused = {pinned[p] for p in set(pinned) - used}
    assert unused == {f"{CGA}/fa2324_cag_certificate.pdf", "pib_gst_monthly_releases/pib_allrel_form.html",
                      *(f"pib_gst_monthly_releases/pib_allrel_mof_2023-0{m}-01.html" for m in (5, 6, 7))}, unused


# ============================================================================ Finance Accounts (pypdf)
FA_FILE = {"8": f"{CGA}/fa2324_statement8.pdf", "9": f"{CGA}/fa2324_statement9.pdf"}
FA_DS = {"8": "fa_receipts", "9": "fa_expenditure"}
_D = "�—–\\-"  # pypdf renders the printed minus (em dash) as U+FFFD on most pages
_TOK = re.compile(
    rf"(?P<neg>[{_D}]\s?)?(?P<n>\d{{1,2}}(?:,\d{{2}})+|\d{{1,3}})(?![\d,])|(?<!\S)(?P<dash>[{_D}]{{1,2}})(?!\S)"
)
_TAIL = re.compile(rf"^(?:\s*(?:[{_D}]{{1,2}}|[#*@$^]*[{_D}]?\s?\d[\d,]*))*\s*$")
_MH = re.compile(r"^\s*[-–—]*\s*(\d{4})(?![,\d])")
_SM = re.compile(r"^\s*[-–—]?\s*(\d{2})(?![,\d])\s*[-–—]?\s*($|[A-Z])")


def fa_fmt(k: int) -> str:
    """Rs thousand as printed in the Finance Accounts: 2-digit groups from the right."""
    s, g = str(abs(k)), []
    while len(s) > 2:
        g.insert(0, s[-2:])
        s = s[:-2]
    g.insert(0, s)
    return ",".join(g)


def fa_on_page(text: str, k: int) -> bool:
    """The amount (with the right sign) is printed somewhere on the page."""
    if k == 0:
        return True
    for m in re.finditer(r"(?<!,)" + re.escape(fa_fmt(k)) + r"(?!,\d)", text):
        pre = text[max(0, m.start() - 3) : m.start()].replace(" ", "")
        if (bool(pre) and pre[-1] in "�—–-") == (k < 0):
            return True
    return False


def fa_amounts(line: str, allow_bare: bool = False) -> list[int]:
    out = []
    for m in _TOK.finditer(line):
        rest = line[m.end() :]
        if m.group("dash"):
            if _TAIL.match(rest):
                out.append(0)
            continue
        n = m.group("n")
        if "," not in n and not (allow_bare and _TAIL.match(rest)):
            continue
        v = int(n.replace(",", ""))
        out.append(-v if m.group("neg") else v)
    return out


def _unglue(line: str) -> str:
    """'—1,42,51,92,59—1,42,51,92,59' (voted and total printed without a space) -> two tokens."""

    def rep(m: re.Match) -> str:
        s = m.group(0)
        h = len(s) // 2
        return s[:h] + " " + s[h:] if s[:h] == s[h:] else s

    return re.sub(rf"[{_D}]?[\d,]{{9,}}", rep, line)


def _eng_code(line: str) -> str | None:
    """The English minor-head code: 3 digits followed by an English label."""
    m = re.search(r"(?:^|\s|[^\x00-\x7f]|[a-z;,'\]])(\d{3})\s+(?=[A-Z(])", line)
    return m.group(1) if m else None


def _is_break(line: str) -> bool:
    return bool(_eng_code(line) or _MH.match(line) or "TOTAL" in line)


def fa_minor_values(lines: list[str], major: str, sub: str, minor: str, st: str) -> list[int | None]:
    """Value(s) printed for minor head `minor` under major `major` / sub-major `sub` on one page.
    St 8: the single value column. St 9: the last of >= 2 amounts on the head's line (col 3 Total);
    the charged amount printed alone on the line above is never taken."""
    vals: list[int | None] = []
    for i, ln in enumerate(lines):
        if _eng_code(ln) != minor:
            continue
        mh = sm = None
        for j in range(i - 1, -1, -1):
            if sm is None and _SM.match(lines[j]):
                sm = _SM.match(lines[j]).group(1)
            if _MH.match(lines[j]):
                mh = _MH.match(lines[j]).group(1)
                break
        if mh not in (None, major) or (sub != "00" and sm not in (None, sub)):
            continue
        blk = [_unglue(ln)]
        for l2 in lines[i + 1 : i + 5]:
            if _is_break(l2):
                break
            blk.append(_unglue(l2))
        need = 1 if st == "8" else 2
        v = None
        for b in blk:
            a = fa_amounts(b, allow_bare=(st == "8"))
            if len(a) >= need:
                v = a[-1]
                break
        vals.append(v)
    return vals


def fa_page(r: dict) -> int:
    return int(re.search(r"PDF page (\d+)", prov()[r["prov_id"]]["locator"]).group(1))


@pytest.mark.parametrize("st", ["8", "9"])
def test_fa_census_every_value_printed_on_its_page(st):
    """Census: every clean value, converted back to Rs thousand, is printed (same sign) on the PDF
    page its provenance names."""
    pages = pdf_pages(FA_FILE[st])
    rows = clean(FA_DS[st])
    bad = []
    for r in rows:
        k = round(r["value"] * 1e4)
        assert abs(r["value"] * 1e4 - k) < 1e-6, f"{r['series_id']}: not a whole number of Rs thousand"
        if not fa_on_page(pages[fa_page(r) - 1], k):
            bad.append((r["series_id"], r["value"], fa_page(r)))
    report(f"{FA_DS[st]} (census, page text)", len(rows), bad)
    assert not bad


@pytest.mark.parametrize("st", ["8", "9"])
def test_fa_minor_heads_line_level(st):
    """Every minor head: its own line (English code, under the right major and sub-major head) carries
    exactly the clean value in the value column. No mismatch allowed; the parser may leave a few
    heads unresolved (glyph-split codes such as '80 0', '79 7'); those are covered by the census."""
    pages = [p.splitlines() for p in pdf_pages(FA_FILE[st])]
    rows = [r for r in clean(FA_DS[st]) if "minor_head" in dims(r) and dims(r)["minor_head"] != "000"]
    bad, unresolved = [], 0
    for r in rows:
        d = dims(r)
        vals = fa_minor_values(pages[fa_page(r) - 1], d["major_head"], d.get("sub_major_head", "00"), d["minor_head"], st)
        k = round(r["value"] * 1e4)
        if k in vals:
            continue
        if all(v is None for v in vals):
            unresolved += 1
        else:
            bad.append((r["series_id"], r["value"], fa_page(r), vals))
    report(f"{FA_DS[st]} (minor heads, line level)", len(rows) - unresolved, bad, unresolved)
    assert not bad
    assert unresolved <= 0.05 * len(rows)


@pytest.mark.parametrize("st", ["8", "9"])
def test_fa_subtotals_and_major_totals_line_level(st):
    """Sub-major totals '(nn) TOTAL (nn)' and major-head 'TOTAL' lines: the clean value is the value
    column of that TOTAL line (St 9: the last amount = column 3). Capital major heads of St 9 carry
    their amount on the head line itself."""
    pages = [p.splitlines() for p in pdf_pages(FA_FILE[st])]
    rows = [r for r in clean(FA_DS[st]) if r["series_id"].endswith(".total")]
    need = 1 if st == "8" else 2
    bad, unresolved = [], 0
    for r in rows:
        d, lines = dims(r), pages[fa_page(r) - 1]
        k = round(r["value"] * 1e4)
        if "sub_major_head" in d:
            pat = re.compile(rf"(?:\(\s*{d['sub_major_head']}\s*\)\s*)?(?i:TOTAL)\s*\(\s*{d['sub_major_head']}\s*\)")
        else:
            pat = re.compile(r"^\s*\+?\s*(?i:TOTAL)(?!\s*\(|\s*[-–—]+\s*[A-Za-z(])")
        vals = []
        for i, ln in enumerate(lines):
            if pat.search(ln):
                for l2 in (ln, *lines[i + 1 : i + 3]):
                    a = fa_amounts(_unglue(l2), allow_bare=(st == "8"))
                    if len(a) >= need:
                        vals.append(a[-1])
                        break
        if k not in vals and st == "9" and "sub_major_head" not in d:
            for i, ln in enumerate(lines):  # capital major head: amount on the head line / its wrap
                if re.search(rf"(?:^|\s){d['major_head']}[.\-–\s]", ln):
                    for l2 in lines[i : i + 3]:
                        a = fa_amounts(_unglue(l2))
                        if len(a) >= 2:
                            vals.append(a[-1])
                            break
        if k in vals:
            continue
        if not vals:
            unresolved += 1
        else:
            bad.append((r["series_id"], r["value"], fa_page(r), vals[:6]))
    report(f"{FA_DS[st]} (sub-major / major totals, line level)", len(rows) - unresolved, bad, unresolved)
    assert not bad
    assert unresolved <= 0.05 * len(rows)


@pytest.mark.parametrize("st", ["8", "9"])
def test_fa_reverse_every_printed_head_has_a_row(st):
    """Reverse census: every minor-head code printed on a page has a clean row on that page, except
    the heads printed with no amount at all. (The nil head MH 0032-901, printed '–—', was dropped in
    the first pass (verify-3); it now has a row, so nothing is excused any more.)"""
    known_dropped: set = set()
    blank_heads = {("9", 48, "198"), ("9", 86, "800")}  # printed with no amount in any column
    pages = pdf_pages(FA_FILE[st])
    per_page = defaultdict(Counter)
    for r in clean(FA_DS[st]):
        d = dims(r)
        if "minor_head" in d and d["minor_head"] != "000":
            per_page[fa_page(r)][d["minor_head"]] += 1
    missing = []
    for pg, text in enumerate(pages, 1):
        raw = Counter(c for c in (_eng_code(ln) for ln in text.splitlines()) if c)
        for code, n in (raw - per_page[pg]).items():
            if (st, pg, code) not in known_dropped | blank_heads:
                missing.append((pg, code, n))
    print(f"\nSPOTCHECK {FA_DS[st]} reverse: printed heads without a clean row (unexplained) = {missing}")
    assert not missing


# Values typed by the verifier from the page text (Rs thousand as printed -> Rs crore).
HAND_FA = [
    # St 8, PDF page 21 (printed p117): MH 0049 / 0050
    ("8", "fa8.0050.00.106", 87416.2162),  # '8,74,16,21,62' Share of Surplus Profits from the RBI
    ("8", "fa8.0050.00.101", 63827.4120),  # '6,38,27,41,20' Dividends from Public Undertakings
    ("8", "fa8.0050.00.107", 4272.5360),  # '42,72,53,60' LIC
    ("8", "fa8.0050.00.108", 13806.5683),  # '1,38,06,56,83' Nationalised Banks
    ("8", "fa8.0050.00.109", 488.9872),  # '4,88,98,72' IDBI
    ("8", "fa8.0050.00.200", 1078.7858),  # '10,78,78,58' other investments
    ("8", "fa8.0050.total", 170890.5055),  # 'TOTAL 17,08,90,50,55'
    ("8", "fa8.0049.03.110", 9643.0366),  # '96,43,03,66'
    ("8", "fa8.0049.03.900", -0.4683),  # 'Deduct—Refunds —46,83'
    ("8", "fa8.0049.03.total", 65032.8464),  # '(03) TOTAL (03) 6,50,32,84,64'
    ("8", "fa8.section.b_interest_receipts_dividends_and_profits", 249564.6159),  # '24,95,64,61,59'
    # St 8, PDF page 1 (p97): CGST
    ("8", "fa8.0005.00.101", 337032.1292),  # '33,70,32,12,92'
    ("8", "fa8.0005.00.106", 133055.5407),  # '13,30,55,54,07' apportionment of IGST, tax
    ("8", "fa8.0005.00.110", -9000.0),  # '#—90,00,00,00' advance apportionment recovered
    ("8", "fa8.0005.00.901", -342787.3300),  # '—34,27,87,33,00' States' share
    ("8", "fa8.0005.total", 477834.7626),  # 'TOTAL 47,78,34,76,26'
    # St 8, PDF pages 4-5 (p100-101): IGST and compensation cess
    ("8", "fa8.0008.02.950", -133055.5406),  # '#—13,30,55,54,06'
    ("8", "fa8.0008.02.953", -131367.4715),  # '##—13,13,67,47,15'
    ("8", "fa8.0008.02.105", -353607.9152),  # '*—35,36,07,91,52'
    ("8", "fa8.0008.02.960", 8951.4000),  # '89,51,40,00' advance apportionment to SGST
    ("8", "fa8.0008.total", -4850.4302),  # 'TOTAL —48,50,43,02'
    ("8", "fa8.0009.total", 141436.1610),  # 'TOTAL 14,14,36,16,10'
    ("8", "fa8.section.a_goods_and_service_tax", 619917.6510),  # '61,99,17,65,10'
    # St 8, PDF page 7 (p103): Fringe Benefit Tax, detached minus
    ("8", "fa8.0026.00.101", -4.8381),  # '* — 4,83,81'
    ("8", "fa8.0026.total", -4.4588),  # 'TOTAL — 4,45,88'
    # St 9, PDF page 8 (p148): MH 2042
    ("9", "fa9.2042.00.101", 5099.7768),  # '50,99,77,68 50,99,77,68'
    ("9", "fa9.2042.00.911", -6.9948),  # '—6,99,48'
    ("9", "fa9.2042.total", 5875.7935),  # 'TOTAL 58,75,79,35 58,75,79,35'
    # St 9, PDF page 20 (p160): pensions; charged amounts on the line above must not be taken
    ("9", "fa9.2071.02.101", 121210.7931),  # voted 12,12,10,47,79, total 12,12,10,79,31
    ("9", "fa9.2071.02.total", 142092.9954),  # '(02) TOTAL (02) 14,20,92,66,14 14,20,92,99,54'
    ("9", "fa9.2071.total", 238328.2957),  # 'TOTAL 23,79,44,66,08 23,83,28,29,57'
    ("9", "fa9.2075.00.108", 26200.3634),  # '2,62,00,06,26 2,62,00,36,34'
    # St 9, PDF pages 94-95 (p234-235): grants, grand total, capital heads
    ("9", "fa9.3605.00.912", -66.2021),  # '—66,20,21'
    ("9", "fa9.3605.total", 7455.6235),  # 'TOTAL 74,55,62,35 74,55,62,35'
    ("9", "fa9.section.expenditure_heads_revenue_account", 3854082.2138),  # '3,85,40,82,21,38'
    ("9", "fa9.4076.total", 154256.2764),  # '15,41,63,23,60 15,42,56,27,64'
    ("9", "fa9.4055.total", 9994.6120),  # '99,93,52,90 99,94,61,20' (charged 1,08,30 on the label line)
    ("9", "fa9.section.a_capital_account_of_general_services", 177839.6836),  # '17,78,39,68,36'
    # St 9, PDF page 52 (p212): glued voted/total pair
    ("9", "fa9.2416.00.904", -14251.9259),  # '—1,42,51,92,59—1,42,51,92,59'
]


def test_fa_hand_typed_values():
    by_sid = {("8", r["series_id"]): r["value"] for r in clean("fa_receipts")}
    by_sid |= {("9", r["series_id"]): r["value"] for r in clean("fa_expenditure")}
    bad = [(sid, v, by_sid.get((st, sid))) for st, sid, v in HAND_FA if not close(by_sid.get((st, sid), math.inf), v, 1e-4)]
    report("fa (hand-typed from page text)", len(HAND_FA), bad)
    assert not bad


def test_fa_scale_and_cross_document_identities():
    """Scale (Rs thousand -> crore) and the net-of-901 convention, against the AFS (a different
    document, read here with calamine)."""
    fa = {r["series_id"]: r["value"] for r in clean("fa_receipts")}
    fe = {r["series_id"]: r["value"] for r in clean("fa_expenditure")}
    afs = afs_raw_by_mh("b2526")
    for mh in ("0005", "0020", "0021", "0037"):
        gross = fa[f"fa8.{mh}.total"] - sum(v for k, v in fa.items() if re.fullmatch(rf"fa8\.{mh}\.\d\d\.901", k))
        assert close(gross, afs[("cfi_rev_receipts", mh)], 0.01), (mh, gross, afs[("cfi_rev_receipts", mh)])
    assert close(fa["fa8.0008.total"], afs[("cfi_rev_receipts", "0008")], 0.01)  # IGST residual -4,850.43
    assert close(fa["fa8.0009.total"], afs[("cfi_rev_receipts", "0009")], 0.01)  # cess 1,41,436.16
    assert close(fa["fa8.0050.00.106"], 87416.2162, 1e-4)  # gap map R6
    assert close(fe["fa9.section.expenditure_heads_revenue_account"], 3854082.2138, 1e-4)
    # sign conventions: IGST apportionment out of MH 0008 is negative, 901 devolution is negative
    for k, v in fa.items():
        if re.fullmatch(r"fa8\.0008\.02\.95[0-7]", k) or k.endswith(".901"):
            assert v <= 0, (k, v)


# ============================================================================ Receipt Budget
def _rb_xlsx_index(key: str, year: str) -> tuple[list[tuple[str, str, str, float | None]], str]:
    g = grid(key)
    hdr_i = next(i for i, r in enumerate(g) if any(norm(c) == "major head" for c in r))
    hdr = [norm(c) for c in g[hdr_i]]
    mh_col = hdr.index("major head")
    act = [j for j, c in enumerate(hdr) if c.startswith("actual")]
    assert len(act) == 1, hdr
    y = re.search(r"(20\d\d)-(20\d\d)", hdr[act[0]])
    assert f"{y.group(1)}-{y.group(2)[2:]}" == year, hdr[act[0]]
    out = []
    for r in g[hdr_i + 1 :]:
        texts = [str(c).strip() for c in r[:mh_col] if isinstance(c, str) and c.strip()]
        if not texts:
            continue
        label = texts[-1] if re.fullmatch(r"\d+(\.\d+)*\.?", texts[0]) else texts[0]
        out.append((squash(label), str(r[mh_col]).strip(), texts[0], num(r[act[0]])))
    return out, hdr[act[0]]


def _rb_pdf_text(key: str, year: str) -> str:
    pages = pdf_pages(key)
    body = []
    for t in pages:
        if "Actual" not in t or "Major Head" not in t:
            continue
        m = re.search(r"Actual\s+(20\d\d)-(20\d\d)", t)
        assert m and f"{m.group(1)}-{m.group(2)[2:]}" == year, key
        body.append(t)
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", " ".join(body)))


def test_rb_receipts_census():
    bad, checked, unresolved = [], 0, 0
    rows = clean("rb_receipts")
    for r in rows:
        tag, year = TAG[r["vintage"]], VINTAGE_YEAR[r["vintage"]]
        assert r["period"] == year
        tab = r["series_id"].split(".")[1]
        mh = dims(r).get("major_head", "")
        is_total = ".total." in r["series_id"]
        if tag == "b2526":
            text = _rb_pdf_text(f"{MOF}/b2526_{tab}.pdf", year)
            chars = [re.escape(c) for c in unicodedata.normalize("NFKC", r["item_label"]) if not c.isspace()]
            pat = r"(?<![A-Za-z])" + r"\s*".join(chars) + (rf"\s+{mh}" if mh else "") + r"\s+(-?\d+\.\d\d|\.\.\.)\s"
            found = [num(m.group(1)) for m in re.finditer(pat, text)]
        else:
            idx, _ = _rb_xlsx_index(f"{MOF}/{tag}_{tab}.xlsx", year)
            lab = squash(r["item_label"])
            found = [v for (l, m, first, v) in idx if l == lab and (is_total or m == mh) and v is not None]
        if not found:
            unresolved += 1
            bad.append(("NOT FOUND", tag, r["series_id"], r["value"]))
        elif not any(close(v, r["value"]) for v in found):
            bad.append((tag, r["series_id"], r["value"], found))
        checked += 1
    report("rb_receipts (census; 2023-24 from pypdf text, others calamine)", checked, bad, unresolved)
    assert not bad


HAND_RB = [  # Budget 2025-26 tr.pdf / ntr.pdf page text, column 'Actual 2023-2024'
    ("rb.tr.total.total_corporation_tax", 911055.01),
    ("rb.tr.0020.collections", 810869.81),
    ("rb.tr.0034.security_transaction_tax", 33777.78),
    ("rb.tr.0026.fringe_benefit_tax", -4.46),
    ("rb.tr.0037.cesses_on_exports", -3.19),
    ("rb.tr.total.total_customs", 233118.97),
    ("rb.tr.0009.gst_compensation_cess", 141436.16),
    ("rb.tr.total.total_goods_and_services_tax_gst", 957207.82),
    ("rb.tr.0038.nccd_union_excise", -7812.25),
    ("rb.ntr.total.total_dividends_and_profits", 170876.97),
    ("rb.ntr.total.grand_total", 401785.34),
    ("rb.ntr.1002.less_receipts", -252540.84),
]


def test_rb_hand_typed_2023_24():
    v = {r["series_id"]: r["value"] for r in clean("rb_receipts") if r["period"] == "2023-24"}
    bad = [(s, x, v.get(s)) for s, x in HAND_RB if not close(v.get(s, math.inf), x)]
    report("rb_receipts (hand-typed, Budget 2025-26 PDF)", len(HAND_RB), bad)
    assert not bad


def test_rb_gst_gap_map_anchors():
    """Gap map T1: CGST 8,20,622.09; IGST -4,850.43; cess 1,41,436.16; GST 9,57,207.82 (2023-24)."""
    v = {r["series_id"]: r["value"] for r in clean("rb_receipts") if r["period"] == "2023-24"}
    assert close(v["rb.tr.0005.central_goods_and_services_tax_cgst"], 820622.09)
    assert close(v["rb.tr.0008.integrated_goods_and_services_tax_igst"], -4850.43)
    assert close(v["rb.tr.0009.gst_compensation_cess"], 141436.16)
    assert close(v["rb.tr.total.total_goods_and_services_tax_gst"], 957207.82)


def test_rb_section_totals_one_series_across_vintages():
    """verify-2 (fixed): the non-tax section totals printed 'Total-X' (xlsx) and 'Net-X' (2025-26 PDF)
    are one series each; the 2023-24 row keeps its printed 'Net-X' label (checked by the census)."""
    periods, labels = defaultdict(set), {}
    for r in clean("rb_receipts"):
        periods[r["series_id"]].add(r["period"])
        labels[(r["series_id"], r["period"])] = r["item_label"]
    for sec in ("transport", "energy", "social_services", "agriculture_and_allied_activities"):
        assert periods[f"rb.ntr.total.total_{sec}"] == {"2022-23", "2023-24", "2024-25"}, sec
        assert labels[(f"rb.ntr.total.total_{sec}", "2023-24")].startswith("Net-"), sec
    assert not [s for s in periods if re.search(r"otherrural|andoil|rb\.ntr\.total\.net_(transport|energy)", s)]


# ============================================================================ AFS
AFS_TITLES = {
    "cfi_rev_receipts": ("STATEMENT I", "REVENUE ACCOUNT - RECEIPTS"),
    "cfi_rev_disbursements": ("STATEMENT I", "REVENUE ACCOUNT - DISBURSEMENTS"),
    "cfi_cap_receipts": ("STATEMENT I", "CAPITAL ACCOUNT - RECEIPTS"),
    "cfi_cap_disbursements": ("STATEMENT I", "CAPITAL ACCOUNT - DISBURSEMENTS"),
    "pa_receipts": ("STATEMENT III", "PUBLIC ACCOUNT OF INDIA - RECEIPTS"),
    "pa_disbursements": ("STATEMENT III", "PUBLIC ACCOUNT OF INDIA - DISBURSEMENTS"),
}


@cache
def afs_sheet_index(tag: str) -> dict[str, tuple[list[list], int, int | None]]:
    """{key: (grid, actuals column, major-head column)}, sheets identified by their English title."""
    year = {"b2425": "2022-23", "b2526": "2023-24"}[tag]
    out = {}
    for name, g in sheets(f"{MOF}/{tag}_allafs.xlsx").items():
        head = re.sub(r"\s+", " ", " ".join(str(c) for r in g[:8] for c in r if isinstance(c, str))).upper()
        for key, (st, part) in AFS_TITLES.items():
            if re.search(rf"{st}\s*-", head) and part in re.sub(r"\s*-\s*", " - ", head):
                hdr_i, act = next((i, j) for i, r in enumerate(g[:12]) for j, c in enumerate(r) if "Actuals" in str(c))
                y = re.search(r"(20\d\d)-(20\d\d)", str(g[hdr_i][act]))
                assert f"{y.group(1)}-{y.group(2)[2:]}" == year, (tag, name, g[hdr_i][act])
                mh = next((j for j, c in enumerate(g[hdr_i]) if "Major" in str(c)), None)
                assert key not in out, (tag, key)
                out[key] = (g, act, mh)
    assert set(out) == set(AFS_TITLES), (tag, set(out))
    return out


def afs_raw_by_mh(tag: str) -> dict[tuple[str, str], float]:
    out = {}
    for key, (g, act, mhc) in afs_sheet_index(tag).items():
        for r in g:
            if mhc is not None and re.fullmatch(r"\d{4}", str(r[mhc]).strip()) and cellnum(r[act]) is not None:
                out.setdefault((key, str(r[mhc]).strip()), cellnum(r[act]))
    return out


def test_afs_census():
    bad, unresolved = [], 0
    rows = clean("afs")
    for r in rows:
        tag = TAG[r["vintage"]]
        key = r["series_id"].split(".")[1]
        g, act, mhc = afs_sheet_index(tag)[key]
        mh = dims(r).get("major_head")
        found = []
        for row in g:
            v = cellnum(row[act]) if act < len(row) else None
            if v is None:
                continue
            if mh:
                if mhc is not None and str(row[mhc]).strip() == mh:
                    found.append(v)
                continue
            eng = [str(c) for c in row[: mhc if mhc is not None else act] if isinstance(c, str) and re.search(r"[A-Za-z]", c)
                   and not re.search(r"[ऀ-ॿ]", c)]
            if eng and (squash(" ".join(eng)) == squash(r["item_label"]) or squash(r["item_label"]).endswith(squash(eng[-1]))):
                found.append(v)
        if not found:
            unresolved += 1
            bad.append(("NOT FOUND", tag, r["series_id"]))
        elif not any(close(v, r["value"]) for v in found):
            bad.append((tag, r["series_id"], r["value"], found[:4]))
    report("afs (census, calamine)", len(rows), bad, unresolved)
    assert not bad


# ============================================================================ Expenditure Profile
EP_FILE = {"stat1": MOF, "stat7": MOF, "stat18": TRF, "stat20": MOF, "stat21": MOF}
_ENUM = re.compile(r"^\s*(?:\d+\.|[a-z]\.?|[IVX]+\.)\s+")


@cache
def ep_index(tag: str, st: str) -> list[tuple[str, str, bool, bool, dict[str, float | None]]]:
    """(group heading, label, is_heading, is_subitem, {component: value}). Item rows carry a printed
    item number ('1.', 'a' or the number in its own cell); rows with values and no number are
    headings; rows without values continue the label above. A sub-item numbered '3.01' (Statement 21,
    'Contribution for hoisting UNESCO World Heritage event ...' under '3. Archaeological Survey of
    India') is part of the item above it: it is neither a heading nor a new group (close-out pass;
    the first pass read it as a heading and grouped the next item under it)."""
    g = grid(f"{EP_FILE[st]}/{tag}_{st}.xlsx")
    year = VINTAGE_YEAR[{v: k for k, v in TAG.items()}[tag]]
    hdr_i, act = next((i, j) for i, r in enumerate(g[:12]) for j, c in enumerate(r) if "Actual" in str(c))
    y = re.search(r"(20\d\d)-(20\d\d)", str(g[hdr_i][act]))
    assert f"{y.group(1)}-{y.group(2)[2:]}" == year, (tag, st, g[hdr_i][act])
    sub = g[hdr_i + 1] if hdr_i + 1 < len(g) else []
    if str(sub[act]).strip() in ("Revenue", "Grant"):
        cols = {str(sub[j]).strip().lower(): j for j in range(act, act + 3)}
        start = hdr_i + 2
    else:
        cols, start = {"": act}, hdr_i + 1
    out: list[list] = []
    head_i = -1
    for r in g[start:]:
        cells = [c for c in r[:act] if str(c).strip()]
        texts = [str(int(c)) if isinstance(c, float) and c.is_integer() else str(c).strip() for c in cells]
        if not texts:
            continue
        vals = {c: cellnum(r[j]) for c, j in cols.items()}
        has_vals = any(str(r[j]).strip() for j in range(act, len(r)))
        sub_item = bool(re.fullmatch(r"\d+\.\d+", texts[0]))
        numbered = sub_item or bool(re.fullmatch(r"(\d+|[a-z]|[ivx]+)\.?", texts[0])) or bool(re.match(r"^\s*(\d+\.|[a-z])\s{3,}\S", str(cells[0])))
        label = " ".join(texts[1:]) if (sub_item or re.fullmatch(r"(\d+|[a-z]|[ivx]+)\.?", texts[0])) else " ".join(texts)
        if not has_vals:
            if out and not numbered and out[-1][1] != "Grand Total":
                out[-1][1] += " " + label  # wrapped label
            continue
        if not numbered:
            head_i = len(out)
        out.append([head_i if numbered else None, label, not numbered, sub_item, vals])
    # headings keep their printed number ('28. Ministry of Home Affairs' is a department heading under the
    # ministry heading 'Ministry of Home Affairs'); item labels are compared without it
    return [(squash(out[gi][1]) if gi is not None and gi >= 0 else "", squash(lb if h else _ENUM.sub("", lb)), h, s, v)
            for gi, lb, h, s, v in out]


def test_exp_profile_census():
    """Every Statement 1/7/18/20/21 row, matched by (heading, label, component) in the vintage's own
    file; a row must match exactly one printed line (or several printing the same value)."""
    bad, unresolved, ambiguous = [], 0, 0
    rows = clean("exp_profile")
    for r in rows:
        tag, st = TAG[r["vintage"]], r["series_id"].split(".")[0]
        comp = dims(r).get("component", "")
        m = re.match(r"^(.*?)(?: \[(.*)\])?$", r["item_label"])
        level = dims(r).get("level")
        is_sub = level == "subitem"  # label printed '3.01 Contribution ...', no group suffix
        is_item = level == "item" or is_sub
        lab = squash(re.sub(r"^\d+\.\d+\s+", "", m.group(1)) if is_sub else _ENUM.sub("", m.group(1)) if is_item else r["item_label"])
        grp = squash(m.group(2) or "") if is_item else ""
        found = [v.get(comp) for (g, l, h, s, v) in ep_index(tag, st)
                 if l == lab and h == (not is_item) and s == is_sub and (not is_item or is_sub or g == grp)
                 and v.get(comp) is not None]
        if len(set(found)) > 1:
            ambiguous += 1
        if not found:
            unresolved += 1
            bad.append(("NOT FOUND", tag, r["series_id"]))
        elif not any(close(v, r["value"]) for v in found):
            bad.append((tag, r["series_id"], r["value"], found[:4]))
    report(f"exp_profile (census, calamine; {ambiguous} rows with >1 candidate value)", len(rows), bad, unresolved)
    assert not bad
    assert ambiguous == 0


def test_exp_profile_identities_2023_24():
    v = {r["series_id"]: r["value"] for r in clean("exp_profile") if r["period"] == "2023-24"}
    assert close(v["stat18.grand_total"], 935335.03)
    parts = ["stat18.some_important_items_of_transfer", "stat18.finance_commission_grants",
             "stat18.transfers_to_states_other_than_i_ii", "stat18.transfers_to_delhi_puducherry_and_jammu_kashmir"]
    assert close(sum(v[p] for p in parts), v["stat18.grand_total"], 0.02)
    assert close(v["stat7.food.food_subsidy"], 211814.39)
    assert close(v["stat1.total_expenditure_through_budget_1_5.total"], 4443447.23)


# ============================================================================ NSSF (Annex 8, pypdf)
def _a8_entries(tag: str, year: str) -> list[tuple[str, str, float | None]]:
    lines = [ln.strip() for p in pdf_pages(f"{MOF}/{tag}_annex8.pdf") for ln in p.splitlines() if ln.strip()]
    hdr = next(ln for ln in lines if ln.startswith("Particulars"))
    m = re.search(r"Actual (20\d\d)-(20\d\d)", hdr)
    assert f"{m.group(1)}-{m.group(2)[2:]}" == year
    out, section = [], ""
    valre = re.compile(r"^(?P<l>.*?)\s+(?P<a>-?[\d,]+\.\d\d|-|\.\.\.)\s+(?P<b>\S+)\s+(?P<c>\S+)$")
    for ln in lines:
        mv = valre.match(ln)
        if not mv:
            if not ln.startswith(("Particulars", "Receipt Budget", "SOURCES AND", "AS ON")) and not re.fullmatch(r"\d+|\S*[^\x00-\x7f]\S*", ln):
                section = ln if not re.search(r"(Securities against|issued from|Reinvestment of)\s*$", ln) else ln
            continue
        out.append((section, mv.group("l"), num(mv.group("a"))))
    return out


def test_nssf_census():
    bad = []
    rows = clean("nssf")
    for r in rows:
        tag, year = TAG[r["vintage"]], VINTAGE_YEAR[r["vintage"]]
        m = re.match(r"^(.*?)(?: \[(.*)\])?$", r["item_label"])
        lab, sec = m.group(1), m.group(2)
        found = [v for (s, l, v) in _a8_entries(tag, year)
                 if squash(l) == squash(lab) and v is not None and (sec is None or squash(sec) in squash(s) or squash(s).endswith(squash(sec)))]
        if not any(close(v, r["value"]) for v in found):
            bad.append((tag, r["series_id"], r["value"], found))
    report("nssf (census, pypdf)", len(rows), bad)
    assert not bad


HAND_A8 = [  # Receipt Budget Annex 8 page text, column 'Actual'
    ("2025-02-01", "nssf.net_collection", 421678.36),
    ("2025-02-01", "nssf.total_deposits", 3147690.85),
    ("2025-02-01", "nssf.total_investments", 3134086.84),
    ("2025-02-01", "nssf.cash_balance", 4831.40),
    ("2025-02-01", "nssf.special_cgs_post1999.reductions", -172760.85),
    ("2025-02-01", "nssf.ppf.additions", 111927.46),
    ("2026-02-01", "nssf.net_collection", 338985.20),
    ("2026-02-01", "nssf.cash_balance", -3987.14),
    ("2026-02-01", "nssf.special_cgs_pre1999_balances.additions", -64569.19),
    ("2026-02-01", "nssf.total_investments", 3474479.60),
]


def test_nssf_hand_typed_and_identities():
    v = {(r["vintage"], r["series_id"]): r for r in clean("nssf")}
    bad = [(k, s, x) for k, s, x in HAND_A8 if not close(v[(k, s)]["value"], x)]
    report("nssf (hand-typed from page text)", len(HAND_A8), bad)
    assert not bad
    for vin in ("2025-02-01", "2026-02-01"):
        acc = sum(v[(vin, f"nssf.{s}.additions")]["value"] for s in ("savings_deposits", "savings_certificates", "ppf"))
        assert close(acc, v[(vin, "nssf.net_collection")]["value"], 0.02)
        opening = sum(v[(vin, f"nssf.{s}.opening")]["value"] for s in ("savings_deposits", "savings_certificates", "ppf"))
        assert close(opening + acc, v[(vin, "nssf.total_deposits")]["value"], 0.02)
        # the closing total is dated end-March of the actuals year, the opening 1 April of it
        assert v[(vin, "nssf.total_deposits")]["period"].endswith("-03-31")


# ============================================================================ PPAC (calamine on the XLS)
def test_ppac_census():
    g = grid("ppac_petroleum_exchequer/ppac_contribution_to_exchequer.xls", "Anx 1")
    assert any("Table Posted: (17.07.2026)" in str(c) for r in g for c in r)
    assert any(str(c).strip() == "(Rs. Crore)" for r in g for c in r)
    hdr_i = next(i for i, r in enumerate(g) if str(r[0]).strip() == "Particulars")
    years = {}
    for j, c in enumerate(g[hdr_i]):
        m = re.match(r"(20\d\d)-(\d\d)", str(c))
        if m:
            years[j] = f"{m.group(1)}-{m.group(2)}"
    raw: dict[tuple[str, str, str], float] = {}
    block = part = ""
    for r in g[hdr_i + 1 :]:
        a, b = str(r[0]).strip(), str(r[1]).strip()
        if a.startswith("1. Contribution to Central"):
            block = "centre"
            continue
        if a.startswith("2. Contribution to State"):
            block = "states"
            continue
        if b[:2] in ("A.", "B."):
            part = b[0].lower()
            continue
        label = a or b
        if not label or label.startswith(("(P)", "Note")):
            continue
        if label.startswith("Total Contribution of Petroleum"):
            key = ("all", "total", "total")
        elif label.startswith("Total Contribution to"):
            key = (block, "total", "total")
        elif label.startswith("Sub Total"):
            key = (block, part, "subtotal")
        else:
            key = (block, part, squash(label))
        for j, y in years.items():
            v = num(r[j])
            if v is not None:
                raw[(*key, y)] = v
    bad = []
    rows = clean("ppac_exchequer")
    for r in rows:
        _, blk, prt, code = r["series_id"].split(".", 3)
        k = (blk, prt, "subtotal" if code == "subtotal" else "total" if code in ("total", "total_contribution") else squash(r["item_label"]), r["period"])
        if k not in raw or not close(raw[k], r["value"], 0.006):
            bad.append((r["series_id"], r["period"], r["value"], raw.get(k)))
    # reverse: every published cell has a row
    assert len(rows) == len(raw), (len(rows), len(raw))
    report("ppac_exchequer (census, calamine)", len(rows), bad)
    assert not bad
    v = {(r["series_id"], r["period"]): r["value"] for r in rows}
    # registry latest_release anchors (2023-24)
    assert close(v[("ppac.centre.a.excise_duty", "2023-24")], 273683.88)
    assert close(v[("ppac.centre.a.customs_duty", "2023-24")], 13133.73)
    assert close(v[("ppac.centre.a.cess_on_crude_oil", "2023-24")], 19580.39)


# ============================================================================ NSI (lxml)
def test_nsi_census():
    doc = lxml.html.fromstring(raw_path("nsi_small_savings_collections/nsi_collections_id152.html").read_bytes())
    tabs = [t for t in doc.xpath("//table[not(.//table)]") if "Gross" in t.text_content()]
    assert len(tabs) == 1
    raw = {}
    for tr in tabs[0].xpath(".//tr"):
        cells = [re.sub(r"\s+", " ", c.text_content()).strip() for c in tr.xpath("./td|./th")]
        if cells and re.fullmatch(r"\d{4}-\d{2}", cells[0]):
            for item, c in zip(("gross_deposits", "withdrawals", "net_collections"), cells[1:4], strict=True):
                if num(c) is not None:
                    raw[(item, cells[0])] = num(c)
    rows = clean("nsi_collections")
    bad = [(r["series_id"], r["period"], r["value"], raw.get((r["series_id"][4:], r["period"])))
           for r in rows if not close(raw.get((r["series_id"][4:], r["period"]), math.inf), r["value"])]
    assert len(rows) == len(raw)
    report("nsi_collections (census, lxml)", len(rows), bad)
    assert not bad


# ============================================================================ Statement 6 GCCA (calamine)
_S6_DEM = re.compile(r"^Demand\s*No\.?\s*(\d+)$", re.I)
_S6_NUM = re.compile(r"^(\d+)\.(?:\s+(.*))?$", re.S)


def _s6_lines(key: str) -> tuple[str, list[str], list[tuple[int, list[str], list | None]]]:
    """(actuals year, value-column headers, [(sheet row, printed text lines, values or None)]).
    A cell may hold several printed lines ('\\n'), and the item number may sit in its own cell."""
    g = grid(key)
    hdr_i = next(i for i, r in enumerate(g[:10]) if any("Actuals" in str(c) for c in r))
    vcols = [j for j, c in enumerate(g[hdr_i]) if re.search(r"20\d\d-20\d\d", str(c))]
    assert len(vcols) == 4 and "Actuals" in str(g[hdr_i][vcols[0]]), (key, g[hdr_i])
    act = vcols[0]
    out = []
    for i, r in enumerate(g[hdr_i + 1 :], hdr_i + 2):
        vals = [num(r[j]) if j < len(r) else None for j in vcols]  # num() raises on stray text
        texts = [str(c) for c in r[:act] if isinstance(c, str) and c.strip()]
        if not texts and all(v is None for v in vals):
            continue
        sub = [norm_keep(x) for t in texts for x in t.split("\n") if x.strip()]
        if len(sub) >= 2 and re.fullmatch(r"\d+\.", sub[0]):
            sub = [sub[0] + " " + " ".join(sub[1:])]
        out.append((i, sub, vals if any(v is not None for v in vals) else None))
    y = re.search(r"(20\d\d)-(20\d\d)", str(g[hdr_i][act]))
    return f"{y.group(1)}-{y.group(2)[2:]}", [str(g[hdr_i][j]) for j in vcols], out


def norm_keep(s: object) -> str:
    """Whitespace-normalised text, case kept."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(s))).strip()


@cache
def s6_tree(tag: str) -> tuple[str, list[dict]]:
    """Statement 6 as ministries, demands, items and the Grand Total. Inside each demand block the
    item starts and the lines carrying values are paired in print order (asserted one-to-one, items
    numbered 1..n). This absorbs every quirk of the PDF-converted Budget 2025-26 file without special
    cases: labels wrapped over several rows, a label head printed above its item number in the same
    cell, and two items printed in one cell whose second value line is the next row."""
    key = f"{MOF}/{tag}_stat6.xlsx"
    year, _, lines = _s6_lines(key)
    out: list[dict] = []
    ministry: dict | None = None
    k, n = 0, len(lines)

    def is_dem(t: list[str]) -> re.Match | None:
        return _S6_DEM.match(" ".join(t))

    def wrapped_after(j: int) -> int:  # skip label lines without values and without an item number
        while j < n and lines[j][2] is None and not _S6_NUM.match(lines[j][1][0]) and not is_dem(lines[j][1]):
            j += 1
        return j

    while k < n:
        row, sub, vals = lines[k]
        text = " ".join(sub)
        if text == "Grand Total":
            out.append({"level": "total", "label": text, "values": vals, "row": row})
            k += 1
            continue
        m = is_dem(sub)
        if m:
            dem = {"level": "demand", "number": int(m.group(1)), "values": vals, "row": row}
            out.append(dem)
            j = wrapped_after(k + 1)
            dept = [s for ln in lines[k + 1 : j] for s in ln[1]]
            dem["dept"] = " ".join(dept) if dept else ministry["label"]
            k = j
            items, vrows = [], []
            while k < n:
                row2, sub2, vals2 = lines[k]
                if " ".join(sub2) == "Grand Total" or is_dem(sub2):
                    break
                if vals2 is not None and not any(_S6_NUM.match(s) for s in sub2):
                    j = wrapped_after(k + 1)
                    if j < n and is_dem(lines[j][1]):
                        break  # a ministry heading (followed by a Demand line)
                if any(_S6_NUM.match(s) for s in sub2):
                    pre: list[str] = []
                    for s in sub2:
                        mm = _S6_NUM.match(s)
                        if mm:
                            items.append({"level": "item", "number": int(mm.group(1)), "parts": [*pre, mm.group(2) or ""],
                                          "demand": dem["number"], "dept": dem["dept"], "row": row2})
                            pre = []
                        elif items and items[-1]["row"] == row2:
                            items[-1]["parts"].append(s)
                        else:
                            pre.append(s)
                    assert not pre, (key, row2, sub2)
                else:
                    assert items, (key, row2, sub2)
                    items[-1]["parts"] += sub2  # wrapped label line (it may carry the next item's values)
                if vals2 is not None:
                    vrows.append((row2, vals2))
                k += 1
            assert [it["number"] for it in items] == list(range(1, len(items) + 1)), (key, dem["number"])
            assert len(items) == len(vrows), (key, dem["number"], len(items), len(vrows))
            for it, (vr, vv) in zip(items, vrows, strict=True):
                it.update(values=vv, vrow=vr, label=" ".join(p for p in it.pop("parts") if p))
                out.append(it)
            continue
        assert vals is not None, (key, row, sub)  # a ministry heading carries values ...
        j = wrapped_after(k + 1)
        assert j < n and is_dem(lines[j][1]), (key, row, sub)  # ... and is followed by a Demand line
        ministry = {"level": "ministry", "label": " ".join([text] + [s for ln in lines[k + 1 : j] for s in ln[1]]),
                    "values": vals, "row": row}
        out.append(ministry)
        k = j
    return year, out


S6_TAGS = {"2022-23": "b2425", "2023-24": "b2526", "2024-25": "b2627"}


def test_gcca_closures_all_columns():
    """Independent parse: items = their demand, demands = ministries = Grand Total, in all four printed
    columns (Actuals, BE, RE, BE) of all three files, to 0.015 crore. Also the published row counts."""
    counts = {}
    for year, tag in S6_TAGS.items():
        y, tree = s6_tree(tag)
        assert y == year
        gt = next(x for x in tree if x["level"] == "total")["values"]
        for c in range(4):
            def f(x: dict, c: int = c) -> float:
                return x["values"][c] or 0.0

            for lvl in ("ministry", "demand", "item"):
                assert close(sum(f(x) for x in tree if x["level"] == lvl), gt[c], 0.015), (tag, c, lvl)
            for d in (x for x in tree if x["level"] == "demand"):
                its = sum(f(x) for x in tree if x["level"] == "item" and x["demand"] == d["number"])
                assert close(its, f(d), 0.015), (tag, c, d["number"], its, f(d))
        counts[year] = Counter(x["level"] for x in tree)
    assert {y: sum(c.values()) for y, c in counts.items()} == {"2022-23": 561, "2023-24": 517, "2024-25": 532}


def test_gcca_census_and_reverse():
    """Every clean row is matched to exactly one printed line of its vintage's file by level, item
    number, demand number, department/ministry name and label (letters and digits), and carries its
    Actuals value; every printed line has exactly one clean row (reverse census)."""
    bad, used = [], Counter()
    rows = clean("gcca")
    for r in rows:
        tag = S6_TAGS[r["period"]]
        assert TAG[r["vintage"]] == tag, (r["series_id"], r["vintage"])
        tree = s6_tree(tag)[1]
        lev, lab = dims(r)["level"], r["item_label"]
        if lev == "total":
            c = [x for x in tree if x["level"] == "total"]
        elif lev == "ministry":
            c = [x for x in tree if x["level"] == "ministry" and squash(x["label"]) == squash(lab)]
        elif lev == "demand":
            m = re.fullmatch(r"Demand No\. (\d+) \[(.*)\]", lab)
            c = [x for x in tree if x["level"] == "demand" and x["number"] == int(m.group(1)) and squash(x["dept"]) == squash(m.group(2))]
        else:
            m = re.fullmatch(r"(\d+)\. (.*) \[Demand No\. (\d+): (.*)\]", lab, re.S)
            c = [x for x in tree if x["level"] == "item" and x["number"] == int(m.group(1)) and x["demand"] == int(m.group(3))
                 and squash(x["label"]) == squash(m.group(2)) and squash(x["dept"]) == squash(m.group(4))]
        if len(c) != 1 or not close(c[0]["values"][0], r["value"]):
            bad.append((tag, lev, lab[:80], r["value"], [x["values"][0] for x in c]))
        else:
            used[(tag, c[0]["row"], c[0].get("number"), lev)] += 1
    printed = sum(len(s6_tree(t)[1]) for t in S6_TAGS.values())
    report("gcca (census, calamine)", len(rows), bad)
    assert not bad
    assert max(used.values()) == 1 and len(used) == printed == len(rows), (len(used), printed, len(rows))


def test_gcca_pdf_conversion_glitches_resolved_by_other_vintages():
    """Budget 2025-26 row 727 prints items 10 and 11 of Demand 102 in one cell; the second item's
    values are on row 728. The pairing is confirmed by the BE columns the neighbouring Budgets print
    for the same schemes: BE 2024-25 (Budget 2024-25: NYKS 3.0, RGNIYD 2.5) and BE 2025-26 (Budget
    2026-27: NYKS 3.5, RGNIYD 3.0) equal the b2526 BE columns of the values each item received."""
    items = {(x["demand"], x["number"]): x for x in s6_tree("b2526")[1] if x["level"] == "item"}
    nyks, rgn = items[(102, 10)], items[(102, 11)]
    assert squash(nyks["label"]) == "nehruyuvakendrasangathan" and squash(rgn["label"]).startswith("rajivgandhinat")
    assert (nyks["vrow"], rgn["vrow"]) == (727, 728)
    for tree, col_prev, tag in ((s6_tree("b2425")[1], 3, "BE 2024-25"), (s6_tree("b2627")[1], 1, "BE 2025-26")):
        prev = {squash(x["label"]): x["values"][col_prev] for x in tree if x["level"] == "item" and x["demand"] == 102}
        col_now = 1 if col_prev == 3 else 3
        assert close(prev["nehruyuvakendrasangathan"], nyks["values"][col_now]), tag
        assert close(prev["rajivgandhinationalinstituteofyouthdevelopment"], rgn["values"][col_now]), tag
    v = {r["item_label"]: r["value"] for r in clean("gcca") if r["period"] == "2023-24" and "Demand No. 102:" in r["item_label"]}
    assert close(v["10. Nehru Yuva Kendra Sangathan [Demand No. 102: Ministry of Youth Affairs and Sports]"], 0.93)
    # item 8 of Demand 101: label head 'Saksham Anganwadi and POSHAN 2.0 (Umbrella' printed above '8.'
    sak = items[(101, 8)]
    assert squash(sak["label"]).startswith("sakshamanganwadiandposhan20umbrellaicds") and close(sak["values"][0], 586.66)


HAND_GCCA = [  # (period, series_id, value) typed from the calamine grids printed during the check
    ("2022-23", "stat6.grand_total", 306263.98),  # b2425 row 634
    ("2023-24", "stat6.grand_total", 303915.55),  # b2526 row 730
    ("2024-25", "stat6.grand_total", 272655.92),  # b2627 row 611
    ("2023-24", "stat6.demand.ministry_of_finance.transfers_to_states", 6460.38),  # Demand 42
    ("2023-24", "stat6.item.ministry_of_finance.additional_central_assistance_for_externally_aided_projects_grants", 5478.83),
    ("2023-24", "stat6.item.ministry_of_finance.special_assistance", 981.55),
    ("2022-23", "stat6.item.department_of_atomic_energy.education_society_aees", -0.01),  # printed negative
    ("2022-23", "stat6.demand.ministry_of_ayush", 761.99),
    ("2024-25", "stat6.demand.department_of_atomic_energy", 920.81),
]


def test_gcca_hand_typed():
    v = {(r["period"], r["series_id"]): r["value"] for r in clean("gcca")}
    bad = [(p, s, x, v.get((p, s))) for p, s, x in HAND_GCCA if not close(v.get((p, s), math.inf), x)]
    report("gcca (hand-typed)", len(HAND_GCCA), bad)
    assert not bad


# ============================================================================ Finance Accounts Appendix to St 9 (pypdf)
GIA_FILE = f"{CGA}/fa2324_statement9_appendix.pdf"
GIA_CATS = {  # printed English grantee category -> clean slug (both tables print the same ten, in this order)
    "State Government": "state_governments",
    "Union Territories Government": "ut_governments",
    "Urban Local Bodies": "urban_local_bodies",
    "Panchayati Raj Institutions": "panchayati_raj_institutions",
    "Public Sector Undertakings": "public_sector_undertakings",
    "Non-Governmental Organisations (NGOs)": "ngos",
    "Autonomous Bodies": "autonomous_bodies",
    "Co-operative Societies and Co-operative Institutions": "cooperatives",
    "Statutory Bodies and Development Authorities": "statutory_bodies_and_development_authorities",
    "Others": "others",
}


@cache
def gia_raw() -> dict[tuple[str, str, str], tuple[float, int, str]]:
    """{(form, grantee, measure): (Rs lakh as printed, PDF page, printed label)}."""
    pages = pdf_pages(GIA_FILE)
    out = {}
    for pg, form, title in ((2, "cash", "Total Funds released during the Year 2023-24 as Grants-in-aid"),
                            (3, "in_kind", "Total value of grants-in-aid in kind released during the Year 2023-24")):
        text = pages[pg - 1]
        assert title in re.sub(r"\s+", " ", text) and "(Rupees in lakhs)" in text, pg
        seen = []
        for ln in text.splitlines():
            m = re.fullmatch(r"(.+?) (\d+\.\d\d) (\d+\.\d\d)", ln.strip())
            if m and m.group(1) in GIA_CATS:
                seen.append(m.group(1))
                out[(form, GIA_CATS[m.group(1)], "total")] = (float(m.group(2)), pg, m.group(1))
                out[(form, GIA_CATS[m.group(1)], "capital_assets")] = (float(m.group(3)), pg, m.group(1))
        assert seen == list(GIA_CATS), (pg, seen)
    return out


def test_fa_gia_census():
    """All 40 rows: Rs lakh as printed x 0.01 = clean crore, on the page the provenance names, with the
    printed category as the label's head; and every printed cell has a row."""
    raw, bad = gia_raw(), []
    rows = clean("fa_gia")
    for r in rows:
        d = dims(r)
        k = (d["form"], d["grantee"], d["measure"])
        lakh, pg, lab = raw.get(k, (math.inf, 0, ""))
        if not (close(lakh / 100, r["value"], 1e-6) and fa_page(r) == pg and r["item_label"].startswith(lab + ":")
                and r["series_id"] == f"gia.{k[0]}.{k[1]}.{k[2]}"):
            bad.append((r["series_id"], r["value"], lakh, pg, fa_page(r)))
    report("fa_gia (census, pypdf)", len(rows), bad)
    assert not bad and len(rows) == len(raw) == 40


def test_fa_gia_capital_equals_statement6_and_bridge_gap():
    """The IGAS-2 capital column (ten categories) equals Statement 6's Actuals 2023-24 Grand Total, both
    read from raw here (3,03,915.56 vs 3,03,915.55). The 'State Government' total is below Finance
    Accounts MH 3601 (grants to State Governments), the gap the builder logs as union_fiscal-23."""
    raw = gia_raw()
    cap = sum(v for (f, _, m), (v, _, _) in raw.items() if f == "cash" and m == "capital_assets") / 100
    gt = next(x for x in s6_tree("b2526")[1] if x["level"] == "total")["values"][0]
    assert round(cap, 2) == 303915.56 and close(cap, gt, 0.02), (cap, gt)  # 3,03,915.5611 vs 3,03,915.55
    assert not any(v for (f, _, m), (v, _, _) in raw.items() if f == "in_kind" and m == "capital_assets")
    fe = {r["series_id"]: r["value"] for r in clean("fa_expenditure")}
    state = raw[("cash", "state_governments", "total")][0] / 100
    assert close(state, 398428.0358, 1e-4) and close(fe["fa9.3601.total"] - state, 141535.55, 0.01)


# ============================================================================ Finance Accounts St 14 (pypdf)
PF_FILE = f"{CGA}/fa2324_statement14.pdf"
PF_MH = ("8009", "8011", "8014")
_PF_T = r"(?:[*#$@^]*[—–\-�]?\d{1,2}(?:,\d{2})*|[—–])"
_PF_TAIL = re.compile(rf"^(?P<head>.*?)\s*(?<!\S)(?P<a>{_PF_T})\s+(?P<b>{_PF_T})\s+(?P<c>{_PF_T})\s+(?P<d>{_PF_T})\s*$")


def _pf_amt(tok: str) -> int:
    """Rs thousand: '—' alone is nil; a leading dash is a minus; footnote marks are dropped."""
    t = tok.lstrip("*#$@^")
    if t in ("—", "–"):
        return 0
    neg = t[0] in "—–-�"
    v = int(t.lstrip("—–-�").replace(",", ""))
    return -v if neg else v


@cache
def pf_raw() -> dict[tuple[str, str, str], tuple[tuple[int, int, int, int], int]]:
    """{(major, sub-major or '00', minor or 'total'/'mh_total'): ((opening, additions, discharges,
    closing) in Rs thousand, PDF page)} for MH 8009, 8011 and 8014, read line by line: the English
    head code ('101— General ...', em dash; the Hindi code uses an en dash) opens a head, whose four
    amounts are the right end of that line or of the first following line that has four."""
    out: dict = {}
    mh, sm, pending = None, "00", None
    for pg, text in enumerate(pdf_pages(PF_FILE), 1):
        for ln in text.splitlines():
            if re.fullmatch(r"\s*1 1 2 3 4 5\s*", ln):
                continue
            m = re.search(r"(?<!\d)(80\d\d)—\s*[A-Z]", ln)
            if m:
                mh, sm, pending = m.group(1), "00", None
                continue
            if mh not in PF_MH:
                continue
            mi = re.search(r"(?<![\d,])(\d{3})—\s*[A-Z\"']", ln)
            ms = re.search(r"(?<![\d,])(\d{2})—\s*[A-Z]", ln)
            mt = re.search(r"Total\s*\((\d\d)\)", ln)
            if mi:
                pending = (mh, sm, mi.group(1))
            elif ms:
                sm, pending = ms.group(1), None
            elif mt:
                assert mt.group(1) == sm, (pg, ln)
                pending = (mh, sm, "total")
            elif re.search(r"(?:TOTAL|Total)\s*[-—–]\s*[A-Z]", ln):
                pending = (mh, "00", "mh_total")
            t = _PF_TAIL.match(ln)
            if t and pending:
                assert pending not in out, (pending, pg)
                out[pending] = (tuple(_pf_amt(t.group(x)) for x in "abcd"), pg)
                if pending[2] == "mh_total":
                    mh = None  # the block ends with its major-head TOTAL
                pending = None
    return out


def test_fa_pf_raw_parse_closes():
    """The verifier's own parse closes before it is used: opening + additions - discharges = closing on
    every head, minor heads = their 'Total (nn)' line, sub-major totals (or minors, for MH 8011 which
    has no sub-major level) = the major-head TOTAL, all to the thousand rupees."""
    raw = pf_raw()
    assert {k[0] for k in raw} == set(PF_MH) and len(raw) == 46, len(raw)
    for k, ((o, a, d, c), _) in raw.items():
        assert o + a - d == c, (k, o, a, d, c)
    for mh in PF_MH:
        sms = {k[1] for k in raw if k[0] == mh and k[2] not in ("total", "mh_total")}
        for sm in sms:
            minors = [v for k, (v, _) in raw.items() if k[:2] == (mh, sm) and re.fullmatch(r"\d{3}", k[2])]
            if sm != "00":
                assert [sum(x) for x in zip(*minors, strict=True)] == list(raw[(mh, sm, "total")][0]), (mh, sm)
        parts = [v for k, (v, _) in raw.items() if k[0] == mh and (k[2] == "total" or (k[1] == "00" and re.fullmatch(r"\d{3}", k[2])))]
        assert [sum(x) for x in zip(*parts, strict=True)] == list(raw[(mh, "00", "mh_total")][0]), mh


def test_fa_pf_census():
    """All 184 rows: each clean value x 1e4 is exactly the printed Rs-thousand amount of its head and
    column (opening -> balance at 2023-03-31, closing -> balance at 2024-03-31), on the page the
    provenance names (the page where the head's amounts are printed); every printed cell has a row."""
    raw, bad, seen = pf_raw(), [], set()
    col = {("balance", "2023-03-31"): 0, ("additions", "2023-24"): 1, ("discharges", "2023-24"): 2, ("balance", "2024-03-31"): 3}
    rows = clean("fa_provident_funds")
    for r in rows:
        parts = r["series_id"].split(".")
        assert parts[0] == "fa14"
        if parts[2] == "total":
            key = (parts[1], "00", "mh_total")
        else:
            key = (parts[1], parts[2], parts[3])
        j = col[(parts[-1], r["period"])]
        amts, pg = raw.get(key, ((None,) * 4, 0))
        k = round(r["value"] * 1e4)
        if not (abs(r["value"] * 1e4 - k) < 1e-6 and amts[j] == k and fa_page(r) == pg):
            bad.append((r["series_id"], r["period"], r["value"], amts[j], pg, fa_page(r)))
        seen.add((key, j))
        d = dims(r)
        assert d["major_head"] == parts[1] and d.get("minor_head", "total") == (parts[3] if parts[2] != "total" else "total")
    report("fa_provident_funds (census, pypdf)", len(rows), bad)
    assert not bad
    assert len(seen) == len(rows) == 4 * len(raw), (len(seen), len(rows), len(raw))


def test_fa_pf_gpf_equals_afs_statement_iii():
    """MH 8009 gross additions and discharges 2023-24 = AFS Statement III '(i) State Provident Fund'
    receipts and disbursements (another document, read with calamine): 68,989.35 vs 68,989.34 and
    63,930.50. MH 8014 alone is NOT the AFS '(ii) Postal Insurance and Life Annuity Fund' line
    (52,132.49 / 53,943.57): that is group (d) Post Office Insurance Fund = MH 8014 + 8015 + 8016,
    whose TOTAL line prints the same figures; 8015/8016 are not ingested."""
    raw = pf_raw()
    (_, a, d, _), _ = raw[("8009", "00", "mh_total")]
    afs = {}
    for key in ("pa_receipts", "pa_disbursements"):
        g, act, _ = afs_sheet_index("b2526")[key]
        for r in g:
            lab = " ".join(str(c) for c in r[:act] if isinstance(c, str))
            if re.search(r"\(i\)\s+State Provident Fund", lab):
                afs[(key, "spf")] = cellnum(r[act])
            if re.search(r"\(ii\)\s+Postal Insurance and Life Annuity Fund", lab):
                afs[(key, "pli")] = cellnum(r[act])
    assert close(a / 1e4, afs[("pa_receipts", "spf")], 0.01) and close(d / 1e4, afs[("pa_disbursements", "spf")], 0.01)
    (_, a14, d14, _), _ = raw[("8014", "00", "mh_total")]
    assert not close(a14 / 1e4, afs[("pa_receipts", "pli")], 1000.0)
    text = re.sub(r"\s+", " ", " ".join(pdf_pages(PF_FILE)))
    m = re.search(r"TOTAL-\s*POST OFFICE INSURANCE FUND (\S+) (\S+) (\S+) (\S+)", text)
    assert close(_pf_amt(m.group(2)) / 1e4, afs[("pa_receipts", "pli")], 0.01)
    assert close(_pf_amt(m.group(3)) / 1e4, afs[("pa_disbursements", "pli")], 0.01)


HAND_PF = [  # (series_id, period, Rs crore) typed from St 14 page text (Rs thousand as printed)
    ("fa14.8009.total.additions", "2023-24", 68989.3453),  # '6,89,89,34,53'
    ("fa14.8009.total.discharges", "2023-24", 63930.4999),  # '6,39,30,49,99'
    ("fa14.8009.total.balance", "2023-03-31", 262348.9866),  # '26,23,48,98,66'
    ("fa14.8009.total.balance", "2024-03-31", 267407.8320),  # '26,74,07,83,20'
    ("fa14.8009.01.101.balance", "2023-03-31", 129510.7148),  # GPF civil '12,95,10,71,48'
    ("fa14.8009.02.106.discharges", "2023-24", -0.0470),  # '*—4,70'
    ("fa14.8011.total.balance", "2023-03-31", 4246.5526),  # 'FUNDS 42,46,55,26' (wrapped TOTAL line)
    ("fa14.8011.00.105.additions", "2023-24", -0.0023),  # '#—23'
    ("fa14.8014.total.additions", "2023-24", 16793.0818),  # '1,67,93,08,18'
    ("fa14.8014.01.108.balance", "2024-03-31", -3296.5928),  # '—32,96,59,28'
]


def test_fa_pf_hand_typed():
    v = {(r["series_id"], r["period"]): r["value"] for r in clean("fa_provident_funds")}
    bad = [(s, p, x, v.get((s, p))) for s, p, x in HAND_PF if not close(v.get((s, p), math.inf), x, 1e-4)]
    report("fa_provident_funds (hand-typed)", len(HAND_PF), bad)
    assert not bad


# ============================================================================ PIB GST releases (lxml)
PIB_STATES = {  # printed State/UT name -> ISO 3166-2:IN (current codes, D1-9), typed by the verifier
    "Jammu and Kashmir": "IN-JK", "Himachal Pradesh": "IN-HP", "Punjab": "IN-PB", "Chandigarh": "IN-CH",
    "Uttarakhand": "IN-UK", "Haryana": "IN-HR", "Delhi": "IN-DL", "Rajasthan": "IN-RJ", "Uttar Pradesh": "IN-UP",
    "Bihar": "IN-BR", "Sikkim": "IN-SK", "Arunachal Pradesh": "IN-AR", "Nagaland": "IN-NL", "Manipur": "IN-MN",
    "Mizoram": "IN-MZ", "Tripura": "IN-TR", "Meghalaya": "IN-ML", "Assam": "IN-AS", "West Bengal": "IN-WB",
    "Jharkhand": "IN-JH", "Odisha": "IN-OD", "Chhattisgarh": "IN-CG", "Chattisgarh": "IN-CG", "Madhya Pradesh": "IN-MP",
    "Gujarat": "IN-GJ", "Dadra and Nagar Haveli and Daman and Diu": "IN-DH", "Maharashtra": "IN-MH",
    "Karnataka": "IN-KA", "Goa": "IN-GA", "Lakshadweep": "IN-LD", "Kerala": "IN-KL", "Tamil Nadu": "IN-TN",
    "Puducherry": "IN-PY", "Andaman and Nicobar Islands": "IN-AN", "Telangana": "IN-TS", "Andhra Pradesh": "IN-AP",
    "Ladakh": "IN-LA",
}
PIB_OTHER = {"Other Territory": "other_territory", "Center Jurisdiction": "centre_jurisdiction", "Grand Total": "grand_total"}
PIB_HEAD = ("gross_gst", "cgst", "sgst", "igst", "igst_on_imports", "cess", "cess_on_imports",
            "igst_settled_to_cgst", "igst_settled_to_sgst", "cgst_post_settlement", "sgst_post_settlement")
MON = {m: i for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"), 1)}


@cache
def pib_raw(month: str) -> dict:
    """{'posted': date, 'head': {item: crore}, 'states': {(key, period): crore}} for one release."""
    doc = lxml.html.fromstring(raw_path(f"pib_gst_monthly_releases/pib_gst_{month}.html").read_bytes())
    text = re.sub(r"\s+", " ", doc.text_content())
    p = re.search(r"Posted On: (\d\d) ([A-Z]{3}) (20\d\d)", text)
    posted = f"{p.group(3)}-{MON[p.group(2).title()]:02d}-{p.group(1)}"
    y, m = map(int, month.split("-"))
    para = re.search(r"The gross [^.]*?revenue collected in the month of (\w+), (20\d\d) is (.*?) for the SGST", text)
    assert para and MON[para.group(1)[:3]] == m and int(para.group(2)) == y, month
    amts = [int(a.replace(",", "")) for a in re.findall(r"₹\s?([\d,]+) crore", para.group(3))]
    assert len(amts) == 11, amts
    tabs = [t for t in doc.xpath("//table[not(.//table)]") if "State/UT" in t.text_content()]
    grids = [[[re.sub(r"\s+", " ", c.text_content()).strip() for c in tr.xpath("./td|./th")] for tr in t.xpath(".//tr")]
             for t in tabs]
    assert grids and all(g == grids[0] for g in grids), len(grids)  # the page prints the table twice (identical)
    trs = grids[0]
    hdr = trs[0]
    assert hdr[0] == "State/UT" and hdr[3].startswith("Growth"), hdr
    per = []
    for h in hdr[1:3]:
        mm = re.fullmatch(r"([A-Z][a-z]{2})-(\d\d)", h)
        per.append(f"20{mm.group(2)}-{MON[mm.group(1)]:02d}")
    assert per == [f"{y - 1}-{m:02d}", f"{y}-{m:02d}"], per
    states = {}
    for tr in trs[1:]:
        if not tr or not tr[0]:
            continue
        key = PIB_STATES.get(tr[0]) or PIB_OTHER[tr[0]]
        for pp, c in zip(per, tr[1:3], strict=True):
            states[(key, pp)] = int(c.replace(",", ""))
    assert len({k for k, _ in states}) == 39, len(states)
    return {"posted": posted, "head": dict(zip(PIB_HEAD, amts, strict=True)), "states": states}


def test_pib_census_and_identities():
    """All 178 rows against the release text (headline paragraph, parsed in print order) and the
    State-wise table (innermost table, names mapped to ISO codes by the verifier's own list); the
    vintage is the 'Posted On' date; every published number has a row; and the release's own
    identities hold: gross = CGST + SGST + IGST + cess (to 1 crore of rounding), post-settlement =
    collection + IGST settled, State rows + Other Territory + Centre = Grand Total."""
    bad, n = [], 0
    rows = clean("pib_gst")
    by_month = defaultdict(list)
    for r in rows:
        by_month[r["vintage"]].append(r)
    assert set(by_month) == {"2023-05-01", "2023-06-01"}
    for month in ("2023-04", "2023-05"):
        raw = pib_raw(month)
        mrows = by_month[raw["posted"]]
        h, s = raw["head"], raw["states"]
        assert abs(h["cgst"] + h["sgst"] + h["igst"] + h["cess"] - h["gross_gst"]) <= 1, h
        assert h["cgst"] + h["igst_settled_to_cgst"] == h["cgst_post_settlement"]
        assert h["sgst"] + h["igst_settled_to_sgst"] == h["sgst_post_settlement"]
        for pp in {p for _, p in s}:
            parts = sum(v for (k, p), v in s.items() if p == pp and k != "grand_total")
            assert abs(parts - s[("grand_total", pp)]) <= 5, (month, pp, parts, s[("grand_total", pp)])
        for r in mrows:
            n += 1
            if r["series_id"].startswith("pib.gst."):
                item = r["series_id"][len("pib.gst."):]
                ok = r["period"] == month and h.get(item) == r["value"] and r["geography"] == "IN"
            else:
                key = r["geography"] if r["geography"] != "IN" else dims(r)["gst_jurisdiction"]
                ok = s.get((key, r["period"])) == r["value"] and r["series_id"] == f"pib.gst_domestic_by_state.{key.lower()}"
            if not ok:
                bad.append((month, r["series_id"], r["period"], r["value"]))
        assert len(mrows) == len(h) + len(s), (month, len(mrows), len(h) + len(s))
    report("pib_gst (census, lxml)", n, bad)
    assert not bad and n == 178


def test_pib_hand_typed():
    v = {(r["series_id"], r["period"]): r["value"] for r in clean("pib_gst")}
    hand = [  # release text as printed (PRID 1921186 posted 01 MAY 2023; PRID 1929031 posted 01 JUN 2023)
        ("pib.gst.gross_gst", "2023-04", 187035), ("pib.gst.igst", "2023-04", 89158),
        ("pib.gst.igst_settled_to_cgst", "2023-04", 45864), ("pib.gst.cess_on_imports", "2023-04", 901),
        ("pib.gst.sgst_post_settlement", "2023-05", 65597), ("pib.gst.igst_on_imports", "2023-05", 41772),
        ("pib.gst_domestic_by_state.grand_total", "2023-04", 151162), ("pib.gst_domestic_by_state.grand_total", "2022-05", 102485),
        ("pib.gst_domestic_by_state.in-mh", "2023-04", 33196), ("pib.gst_domestic_by_state.in-cg", "2023-05", 2525),
        ("pib.gst_domestic_by_state.in-ld", "2022-05", 1), ("pib.gst_domestic_by_state.centre_jurisdiction", "2023-05", 187),
    ]
    bad = [(s, p, x, v.get((s, p))) for s, p, x in hand if v.get((s, p)) != x]
    report("pib_gst (hand-typed)", len(hand), bad)
    assert not bad


# ============================================================================ new datasets: fixed-seed provenance sample
def test_new_datasets_seeded_locator_sample():
    """A fixed-seed sample (seed 20260929; 10% of each new dataset, at least 30 rows) is looked up a
    second way, through its provenance locator alone: the xlsx column letter and row range it names,
    or the PDF / release page it names, must carry the clean value as printed. Different from the
    census, this checks that a user following the locator lands on the number."""
    import random

    rng = random.Random(20260929)
    p = prov()
    n_total = checked = 0
    bad = []
    for ds in ("gcca", "fa_gia", "fa_provident_funds", "pib_gst"):
        rows = clean(ds)
        n_total += len(rows)
        sample = rng.sample(rows, max(30, math.ceil(0.10 * len(rows))))
        for r in sample:
            pr = p[r["prov_id"]]
            path = ROOT / pr["raw_path"]
            loc = pr["locator"]
            if ds == "gcca":
                mm = re.search(r"column ([A-Z]), rows (\d+)-(\d+)", loc)
                j = ord(mm.group(1)) - 65
                g = grid(next(k for k, v in _pins().items() if ROOT / v["path"] == path))
                ok = any(cellnum(g[i - 1][j]) is not None and close(cellnum(g[i - 1][j]), r["value"])
                         for i in range(int(mm.group(2)), int(mm.group(3)) + 1))
            elif ds == "fa_gia":
                ok = f"{r['value'] * 100:.2f}" in pdf_pages(GIA_FILE)[fa_page(r) - 1]
            elif ds == "fa_provident_funds":
                ok = fa_on_page(pdf_pages(PF_FILE)[fa_page(r) - 1], round(r["value"] * 1e4))
            else:
                text = re.sub(r"\s+", " ", lxml.html.fromstring(path.read_bytes()).text_content())
                v = int(r["value"])
                ok = bool(re.search(rf"(?<![\d,]){re.escape(f'{v:,}')}(?![\d,])|(?<![\d,]){v}(?![\d,])", _indian(text)))
            checked += 1
            if not ok:
                bad.append((ds, r["series_id"], r["period"], r["value"], loc[:60]))
    report("new datasets (seeded provenance-locator sample)", checked, bad)
    assert not bad and checked >= max(30, 0.10 * n_total), (checked, n_total)


def _indian(text: str) -> str:
    """Rewrites Indian digit grouping ('1,87,035') as Western ('187,035') so one pattern finds both."""
    return re.sub(r"\d{1,3}(?:,\d{2})+,\d{3}(?!\d)", lambda m: f"{int(m.group(0).replace(',', '')):,}", text)


# ============================================================================ metadata / systematic
def test_units_periods_and_stages():
    for ds in ("fa_receipts", "fa_expenditure", "rb_receipts", "afs", "exp_profile", "nssf", "ppac_exchequer", "nsi_collections"):
        for r in clean(ds):
            assert r["unit"] == "INR_crore" and r["price_basis"] == "current" and r["status"] == "official", (ds, r["series_id"])
            if ds.startswith("fa_"):
                assert (r["period"], r["estimate_stage"], r["vintage"]) == ("2023-24", "Audited", "2024-12-10")
            if ds in ("rb_receipts", "afs", "exp_profile"):
                assert r["period"] == VINTAGE_YEAR[r["vintage"]] and r["estimate_stage"] == "Actuals"
    # the four datasets added in the follow-up pass
    for ds in ("gcca", "fa_gia", "fa_provident_funds", "pib_gst"):
        for r in clean(ds):
            assert (r["unit"], r["price_basis"], r["status"]) == ("INR_crore", "current", "official"), (ds, r["series_id"])
            if ds == "gcca":
                assert (r["period"], r["period_type"], r["stock_flow"], r["estimate_stage"]) == (VINTAGE_YEAR[r["vintage"]], "fy", "flow", "Actuals")
            elif ds == "fa_gia":
                assert (r["period"], r["period_type"], r["stock_flow"], r["estimate_stage"], r["vintage"]) == ("2023-24", "fy", "flow", "Audited", "2024-12-10")
            elif ds == "fa_provident_funds":
                assert (r["estimate_stage"], r["vintage"]) == ("Audited", "2024-12-10")
                expect = {"balance": ("stock", "date"), "additions": ("flow", "fy"), "discharges": ("flow", "fy")}[r["series_id"].rsplit(".", 1)[1]]
                assert (r["stock_flow"], r["period_type"]) == expect and r["period"] in ("2023-03-31", "2024-03-31", "2023-24")
                assert (r["period"] == "2023-24") == (expect[1] == "fy")
            else:
                assert (r["period_type"], r["stock_flow"], r["estimate_stage"]) == ("month", "flow", "Provisional")
                # a release dated the 1st of month M+1 carries month M and the same month a year earlier
                y, m = int(r["vintage"][:4]), int(r["vintage"][5:7]) - 1
                assert r["period"] in (f"{y}-{m:02d}", f"{y - 1}-{m:02d}") and r["vintage"].endswith("-01"), (r["series_id"], r["period"])


def test_provenance_points_at_the_right_file():
    p = prov()
    for ds in ("rb_receipts", "afs", "exp_profile", "nssf"):
        for r in clean(ds):
            path = p[r["prov_id"]]["raw_path"]
            assert f"/{TAG[r['vintage']]}_" in path, (ds, r["series_id"], path)
            if ds == "rb_receipts":
                assert path.endswith((f"_{r['series_id'].split('.')[1]}.pdf", f"_{r['series_id'].split('.')[1]}.xlsx")), path
    expect = {"gcca": lambda r: f"/{TAG[r['vintage']]}_stat6.xlsx", "fa_gia": lambda r: "/fa2324_statement9_appendix.pdf",
              "fa_provident_funds": lambda r: "/fa2324_statement14.pdf",
              "pib_gst": lambda r: f"/pib_gst_{r['vintage'][:4]}-{int(r['vintage'][5:7]) - 1:02d}.html"}
    for ds, f in expect.items():
        for r in clean(ds):
            pr = p[r["prov_id"]]
            assert pr["raw_path"].endswith(f(r)), (ds, r["series_id"], pr["raw_path"])
            if ds in ("fa_gia",):
                assert pr["unit_as_published"].startswith("Rs lakh") and pr["conversion"].startswith("INR_lakh -> INR_crore: x 0.01")
            if ds == "fa_provident_funds":
                assert pr["unit_as_published"].startswith("Rs thousand") and pr["conversion"].startswith("INR_thousand -> INR_crore: x 0.0001")
            if ds in ("gcca", "pib_gst"):
                assert pr["unit_as_published"].startswith("Rs crore") and pr["conversion"] == "none"


def test_stat21_heading_rows_do_not_double_count():
    """verify-1 (fixed): the rows tagged level=heading (ministries) add up to the Grand Total, not
    to twice it."""
    for year in ("2022-23", "2023-24", "2024-25"):
        rows = [r for r in clean("exp_profile") if r["period"] == year and r["series_id"].startswith("stat21.")]
        gt = next(r["value"] for r in rows if r["series_id"] == "stat21.grand_total")
        heads = sum(r["value"] for r in rows if "level=heading" in (r["dim_other"] or "") and r["series_id"] != "stat21.grand_total")
        assert close(heads, gt, 0.05), (year, heads, gt)


def _stat21_raw_levels(tag: str) -> dict[str, float]:
    """Statement 21 sums by printed level, read from the raw grid: unnumbered ministry headings,
    numbered department headings ('28. Ministry of Home Affairs', number and name in one cell), items
    (number in its own cell) and sub-items ('3.01'/'4.01')."""
    g = grid(f"{MOF}/{tag}_stat21.xlsx")
    hdr_i, act = next((i, j) for i, r in enumerate(g[:12]) for j, c in enumerate(r) if "Actual" in str(c))
    sums: Counter = Counter()
    for r in g[hdr_i + 1 :]:
        texts = [str(c).strip() for c in r[:act] if isinstance(c, str) and c.strip()]
        v = cellnum(r[act])
        if not texts or v is None:
            continue
        t0 = texts[0]
        kind = ("grand_total" if t0 == "Grand Total" else "subitem" if re.fullmatch(r"\d+\.\d+", t0)
                else "item" if re.fullmatch(r"\d+\.", t0) else "department" if re.match(r"\d+\.\s+\S", t0) else "ministry")
        sums[kind] += v
    return sums


def test_stat21_levels_each_add_to_grand_total():
    """Replaces the first pass's 'headings are twice the Grand Total' (which documented verify-1).
    Re-derived from the raw grid, independently of the clean data: ministries, departments and items
    each add up to the printed Grand Total in all three files, and sub-items sit inside their item
    (so they are not part of any level sum). The clean data then carry exactly these sums per level."""
    for tag, year in (("b2425", "2022-23"), ("b2526", "2023-24"), ("b2627", "2024-25")):
        raw = _stat21_raw_levels(tag)
        for lvl in ("ministry", "department", "item"):
            assert close(raw[lvl], raw["grand_total"], 0.02), (tag, lvl, raw[lvl], raw["grand_total"])
        rows = [r for r in clean("exp_profile") if r["period"] == year and r["series_id"].startswith("stat21.")]
        by = Counter()
        for r in rows:
            by[dims(r).get("level", "total") if r["series_id"] != "stat21.grand_total" else "grand_total"] += r["value"]
        for raw_lvl, clean_lvl in (("ministry", "heading"), ("department", "department"), ("item", "item"),
                                   ("subitem", "subitem"), ("grand_total", "grand_total")):
            assert close(raw[raw_lvl], by[clean_lvl], 0.02), (tag, raw_lvl, raw[raw_lvl], by[clean_lvl])
    # the sub-item is the whole of its item in every year (e.g. 2024-25: 4.01 = 4. ASI = 5.62)
    sub = {r["period"]: r["value"] for r in clean("exp_profile") if dims(r).get("level") == "subitem"}
    asi = {r["period"]: r["value"] for r in clean("exp_profile") if r["series_id"].endswith("ministry_of_culture.archaeological_survey_of_india")}
    assert sub == asi and close(sub["2024-25"], 5.62), (sub, asi)


def test_fa_major_heads_close_to_statement_totals():
    """Independent closure: the major-head totals add up to the printed grand totals (Rs crore)."""
    f8 = {r["series_id"]: r["value"] for r in clean("fa_receipts")}
    f9 = {r["series_id"]: r["value"] for r in clean("fa_expenditure")}
    mh = lambda d, st, first: sum(v for k, v in d.items() if re.fullmatch(rf"fa{st}\.[{first}]\d{{3}}\.total", k))  # noqa: E731
    assert close(mh(f8, 8, "01"), f8["fa8.section.revenue_receipts"], 0.001)  # 30,88,174.64
    assert close(mh(f8, 8, "4"), f8["fa8.section.capital_receipts"], 0.001)  # 45,280.68
    assert close(mh(f9, 9, "23"), f9["fa9.section.expenditure_heads_revenue_account"], 0.001)  # 38,54,082.21
    assert close(mh(f9, 9, "45"), f9["fa9.section.expenditure_heads_capital_account"], 0.001)  # 8,07,180.34
    # AFS (another document) agrees on both expenditure totals
    afs = {(r["series_id"], r["period"]): r["value"] for r in clean("afs")}
    assert close(afs[("afs.cfi_rev_disbursements.total_revenue_disbursements", "2023-24")],
                 f9["fa9.section.expenditure_heads_revenue_account"], 0.01)


def test_fa_nil_901_under_mh0032_kept():
    """verify-3 (fixed): MH 0032 minor head 901 is printed '–—' (nil) on St 8 PDF page 9; it is kept
    as 0.0 like the other nil heads, and MH 0032 still closes to its printed TOTAL."""
    v = {r["series_id"]: r for r in clean("fa_receipts")}
    assert v["fa8.0032.00.901"]["value"] == 0.0 and fa_page(v["fa8.0032.00.901"]) == 9
    page = pdf_pages(FA_FILE["8"])[8]
    assert re.search(r"901\s+Share of Net Proceeds.*?[–—]\s?[–—]", page, re.S), "nil marker not printed"
    parts = sum(r["value"] for k, r in v.items() if re.fullmatch(r"fa8\.0032\.\d\d\.\d{3}", k))
    assert close(parts, v["fa8.0032.total"]["value"], 1e-4)


def test_zz_print_totals():
    print(f"\nSPOTCHECK TOTAL: checked={TOTALS['checked']} mismatched={TOTALS['mismatched']}")
