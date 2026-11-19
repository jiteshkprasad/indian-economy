"""Independent verification of ingest unit io_tables (Phase 1 verifier, first pass, 2026-09-29).

This file does NOT import pipeline.ingest.io_tables. Every raw file is re-read with a different
parser than the unit uses:
- SUT and ADB workbooks: python-calamine (the unit uses openpyxl);
- OECD ICIO CSVs: pyarrow.csv + numpy (the unit uses polars);
- SUT note and IFPRI data paper PDFs: pypdf text (the unit uses pdfplumber tables/words), plus
  values transcribed by eye from the page text (constants below, with the page they come from).
Clean data are read with pyarrow.parquet directly.

The comparison is exhaustive where cheap (every clean row of every dataset is matched to its raw
cell, and every non-blank raw cell must appear in the clean table). A seeded random sample is
additionally printed per dataset/period for the verifier notes (docs/phase1/verify/io_tables.md).
"""

from __future__ import annotations

import csv
import hashlib
import io
import random
import re
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import pyarrow.csv as pacsv
import pyarrow.parquet as pq
import pytest
import yaml
from pypdf import PdfReader
from python_calamine import CalamineWorkbook

pytestmark = pytest.mark.quality

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "data" / "clean" / "io_tables"
SEED = 20260929
TOL = 1e-6  # clean values are rounded to 6 decimals on write


# --------------------------------------------------------------------------------------------- helpers
def _pins() -> dict:
    return yaml.safe_load((ROOT / "data" / "raw_pins" / "io_tables.yaml").read_text(encoding="utf-8"))["pins"]


def raw_path(key: str) -> Path:
    pin = _pins()[key]
    p = ROOT / pin["path"]
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    assert h == pin["sha256"], f"{key}: file hash {h} != pin {pin['sha256']}"
    return p


def clean(ds: str) -> list[dict]:
    return pq.read_table(CLEAN / f"{ds}.parquet").to_pylist()


def norm(s: object) -> str:
    return " ".join(str(s).split())


def is_num(v: object) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def close(a: float, b: float, rel: float = 0.0) -> bool:
    return abs(a - b) <= TOL + rel * max(abs(a), abs(b))


# --------------------------------------------------------------------------------------------- SUT
SUT_FILES = {"2022-23": "mospi_sut_2022base/sut_2022_23.xlsx", "2023-24": "mospi_sut_2022base/sut_2023_24.xlsx"}
SUPPLY_HDR = {
    "supply at bp": "supply_bp", "imports": "imports", "cif adj": "cif_adj",
    "imports after cif adjustment": "imports_after_cif", "import duty": "import_duty",
    "product taxes": "product_taxes", "subsidy on products": "product_subsidies",
    "trade and transport margins": "ttm", "supply at pp": "supply_pp",
}
USE_HDR = {
    "intermediate consumption": "ic_total", "pfce": "pfce", "gfce": "gfce", "gfcf": "gfcf", "cii": "cii",
    "net acquisition of valuables": "valuables", "export": "exports", "total use at pp": "total_use_pp",
}
MEMO = {
    "cif": "cif", "purchases of residents abroad": "purchases_residents_abroad",
    "purchases of non-residents in domestic market": "purchases_nonresidents_domestic",
    "total output": "total", "total use": "total",
}
VA = {
    "gva (by production approach)": "gva_production", "production taxes less subsidies": "net_production_taxes",
    "consumption of fixed capital": "cfc", "compensation of employees": "ce", "operating surplus": "os_mi",
    "gva (by income approach)": "gva_income",
}


def parse_sut(period: str) -> tuple[dict, dict, dict, dict]:
    """Independent parse. Returns (cells, row_labels, industry_labels, raw_rows) where cells maps
    (dataset, item_code, product, industry) -> value for every non-blank numeric cell."""
    wb = CalamineWorkbook.from_path(str(raw_path(SUT_FILES[period])))
    names = wb.sheet_names
    assert names == [f"Supply Table {period}", f"Use Table {period}"], names
    cells: dict = {}
    labels: dict = {}
    ind_labels: dict = {}
    sheets: dict = {}
    for kind, sheet in (("supply", names[0]), ("use", names[1])):
        rows = wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
        sheets[kind] = rows
        assert "Values in Rs. Crore" in [norm(x) for x in rows[0]], "unit caption"
        hdr = rows[1]
        # industries: the 67 columns C.. (0-based 2..68); the next ones are valuation/final-use columns
        for j in range(2, 69):
            ind_labels[j - 1] = norm(hdr[j])
            assert ind_labels[j - 1], f"blank industry header at col {j}"
        extra = {}
        hmap = SUPPLY_HDR if kind == "supply" else USE_HDR
        for j in range(69, len(hdr)):
            h = norm(hdr[j]).lower()
            if h:
                extra[j] = hmap[h]
        assert sorted(extra.values()) == sorted(hmap.values())
        matrix_item = "output" if kind == "supply" else "ic"
        ds = f"io_tables_sut_{kind}"
        va_mode = False
        for i in range(2, len(rows)):
            r = rows[i]
            a, b = r[0], norm(r[1]) if len(r) > 1 else ""
            if is_num(a):
                prod = f"sut_p{int(a):03d}"
            elif b.lower() in MEMO and not va_mode:
                prod = MEMO[b.lower()]
                if prod == "total":
                    va_mode = kind == "use"
            elif b.lower() in VA:
                prod = None
            else:
                assert all(x in ("", " ", None) for x in r), f"{sheet} row {i + 1}: unlabelled data {r[:5]}"
                continue
            labels[(kind, prod or VA[b.lower()])] = b
            for j, v in enumerate(r[2:], start=2):
                if isinstance(v, str):
                    assert v.strip() == "", f"{sheet} {i + 1},{j + 1}: text {v!r} in a value cell"
                    continue
                if not is_num(v):
                    continue
                if prod is None:  # value-added block
                    assert j <= 68, f"{sheet}: VA value outside industry columns at col {j + 1}"
                    cells[("io_tables_sut_va", VA[b.lower()], None, f"sut_i{j - 1:02d}")] = float(v)
                elif j <= 68:
                    cells[(ds, matrix_item, prod, f"sut_i{j - 1:02d}")] = float(v)
                else:
                    cells[(ds, extra[j], prod, None)] = float(v)
    return cells, labels, ind_labels, sheets


@pytest.fixture(scope="module")
def sut_raw() -> dict:
    return {p: parse_sut(p) for p in SUT_FILES}


@pytest.mark.parametrize("ds", ["io_tables_sut_supply", "io_tables_sut_use", "io_tables_sut_va"])
def test_sut_every_clean_row_matches_raw_cell(sut_raw: dict, ds: str) -> None:
    rows = clean(ds)
    bad, checked = [], 0
    for r in rows:
        cells, labels, ind_labels, _ = sut_raw[r["period"]]
        key = (ds, r["item_code"], r["product"], r["industry"])
        if key not in cells:
            bad.append(("no raw cell", r["series_id"], r["period"]))
            continue
        checked += 1
        if not close(r["value"], cells[key]):
            bad.append(("value", r["series_id"], r["period"], r["value"], cells[key]))
        # the label written with the row must be the label printed on that raw row / column
        kind = ds.split("_")[-1]
        row_label = r["item_label"].split(" | ")[0]
        want = labels[("use" if kind == "va" else kind, r["product"] or r["item_code"])]
        if norm(row_label) != want:
            bad.append(("row label", r["series_id"], r["period"], row_label, want))
        if r["industry"]:
            col_label = r["item_label"].split(" | ")[1]
            if norm(col_label) != ind_labels[int(r["industry"][5:])]:
                bad.append(("col label", r["series_id"], col_label))
        for col, want_v in (("unit", "INR_crore"), ("price_basis", "current"), ("base_year", "2022-23"),
                            ("period_type", "fy"), ("status", "official"), ("vintage", "2026-08-31"),
                            ("source_id", "mospi_sut_2022base")):
            if r[col] != want_v:
                bad.append((col, r["series_id"], r[col]))
    assert checked == len(rows)
    assert not bad, bad[:20]


@pytest.mark.parametrize("period", list(SUT_FILES))
def test_sut_no_raw_cell_dropped(sut_raw: dict, period: str) -> None:
    cells = sut_raw[period][0]
    have = set()
    for ds in ("io_tables_sut_supply", "io_tables_sut_use", "io_tables_sut_va"):
        for r in clean(ds):
            if r["period"] == period:
                have.add((ds, r["item_code"], r["product"], r["industry"]))
    missing = [k for k in cells if k not in have]
    extra = [k for k in have if k not in cells]
    assert not missing, missing[:20]
    assert not extra, extra[:20]


def test_sut_industry_numbering_matches_concordance(sut_raw: dict) -> None:
    """The industry number the unit writes (sut_iNN = column order) must be the one the committed
    concordance and ACCOUNT_STRUCTURE s.2 use: compare raw header labels with the concordance labels."""
    conc = {int(r["sut_industry"]): r["sut_industry_label"] for r in
            csv.DictReader((ROOT / "data/concordance/io_tables_sut_industry_to_sam34.csv").open(encoding="utf-8"))}
    prods = {int(r["sut_product"]): r["sut_product_label"] for r in
             csv.DictReader((ROOT / "data/concordance/io_tables_sut_product_to_sam34.csv").open(encoding="utf-8"))}
    for period in SUT_FILES:
        _, labels, ind_labels, _ = sut_raw[period]
        assert {k: norm(v) for k, v in conc.items()} == ind_labels, period
        for n, lab in prods.items():
            assert norm(lab) == labels[("supply", f"sut_p{n:03d}")] == labels[("use", f"sut_p{n:03d}")], (period, n)


def _ranges(spec: str) -> list[int]:
    out: list[int] = []
    for part in re.split(r",\s*", spec.replace("–", "-")):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def test_concordance_equals_account_structure_table() -> None:
    """Re-derive the SUT -> SAM34 map from the markdown table in ACCOUNT_STRUCTURE s.2."""
    text = (ROOT / "docs/phase0/ACCOUNT_STRUCTURE.md").read_text(encoding="utf-8")
    sec = text.split("## 2. Production activities and commodities", 1)[1].split("## 3.", 1)[0]
    ind, prod = {}, {}
    for line in sec.splitlines():
        cols = [c.strip() for c in line.split("|")]
        if len(cols) > 6 and cols[1].isdigit():
            code = cols[2]
            for i in _ranges(cols[4]):
                assert i not in ind
                ind[i] = f"A_{code}"
            for p in _ranges(cols[5]):
                assert p not in prod
                prod[p] = f"C_{code}"
    assert sorted(ind) == list(range(1, 68)) and sorted(prod) == list(range(1, 156))
    ci = {int(r["sut_industry"]): r["activity"] for r in
          csv.DictReader((ROOT / "data/concordance/io_tables_sut_industry_to_sam34.csv").open(encoding="utf-8"))}
    cp = {int(r["sut_product"]): r["commodity"] for r in
          csv.DictReader((ROOT / "data/concordance/io_tables_sut_product_to_sam34.csv").open(encoding="utf-8"))}
    assert ci == ind
    assert cp == prod
    # the sector table's range strings must agree with the item-level files
    for r in csv.DictReader((ROOT / "data/concordance/io_tables_sam34_sectors.csv").open(encoding="utf-8")):
        assert sorted(i for i, a in ci.items() if a == r["activity"]) == sorted(_ranges(r["sut_industries"])), r
        assert sorted(p for p, c in cp.items() if c == r["commodity"]) == sorted(_ranges(r["sut_products"])), r


def test_sut_product_43_44_swap_in_2023_24_raw(sut_raw: dict) -> None:
    """Quirk Q1 is real: in 2023-24 the row labelled 43 'Natural Gas' is produced by industry 6 (crude)."""
    c22, c23 = sut_raw["2022-23"][0], sut_raw["2023-24"][0]
    out = lambda c, p, i: c.get(("io_tables_sut_supply", "output", p, f"sut_i{i:02d}"), 0.0)  # noqa: E731
    assert out(c22, "sut_p043", 7) > 20000 and out(c22, "sut_p043", 6) == 0
    assert out(c23, "sut_p043", 6) > 150000 and out(c23, "sut_p043", 7) == 0
    assert out(c23, "sut_p044", 7) > 20000


def test_sut_memo_rows_total_rule_has_an_exception(sut_raw: dict) -> None:
    """Verifier finding V-io-2: the 'Total' row equals the 155 product rows in every column EXCEPT
    'CIF Adj', where it also includes the CIF memo row (+2,12,499), so the printed total is 0 while the
    product rows sum to -2,12,499. issue io_tables-5 states the product-rows-only rule without this
    exception."""
    for period in SUT_FILES:
        c = sut_raw[period][0]
        prod = lambda item: sum(v for (d, it, p, i), v in c.items()  # noqa: E731
                                if d == "io_tables_sut_supply" and it == item and p and p.startswith("sut_p"))
        tot = lambda item: c[("io_tables_sut_supply", item, "total", None)]  # noqa: E731
        cif = c[("io_tables_sut_supply", "cif_adj", "cif", None)]
        assert abs(prod("imports") - tot("imports")) < 1
        assert abs(prod("cif_adj") + cif) < 1 and abs(tot("cif_adj")) < 1
        assert abs(prod("imports") + prod("cif_adj") - tot("imports_after_cif")) < 1


def test_sut_totals_vs_note(sut_raw: dict) -> None:
    """Printed note totals (read by eye from the PDF, NOTE below) vs independent raw sums."""
    for period in SUT_FILES:
        c = sut_raw[period][0]
        n = NOTE[period]
        s = lambda ds, item: sum(v for (d, it, p, i), v in c.items() if d == ds and it == item and p and p.startswith("sut_p"))  # noqa: E731
        assert abs(s("io_tables_sut_supply", "output") - n["output"]) < 5
        assert abs(s("io_tables_sut_use", "ic") - n["ic"]) < 5
        assert abs(s("io_tables_sut_use", "pfce") - n["pfce"]) < 2
        assert abs(s("io_tables_sut_use", "exports") - n["exports"]) < 2
        assert abs(s("io_tables_sut_supply", "imports_after_cif") - n["imports"]) < 2
        va = lambda item: sum(v for (d, it, p, i), v in c.items() if d == "io_tables_sut_va" and it == item)  # noqa: E731
        assert abs(va("gva_production") - n["gva"]) < 5
        assert abs(va("ce") - n["ce"]) < 5


# --------------------------------------------------------------------------------------------- SUT note
# Transcribed by eye from the pypdf text of the note PDF, pages 20-22 (printed pages 14-16).
NOTE = {
    "2022-23": dict(output=53484478, ic=29661343, gva=23823136, product_taxes_less_subsidies=2353866,
                    gdp=26177001, pfce=14938852, gfce=2934060, gfcf=8452956, cis=174121, valuables=360668,
                    exports=6278722, imports=6962377, gdp_expenditure=26177001,
                    production_taxes_less_subsidies=-69725, cfc=3584380, ce=8653669, os_mi=11654812,
                    gva_income=23823136),
    "2023-24": dict(output=57564356, ic=31158876, gva=26405480, product_taxes_less_subsidies=2667806,
                    gdp=29073287, pfce=16415547, gfce=3121027, gfcf=9245762, cis=382329, valuables=376232,
                    exports=6479296, imports=6946906, gdp_expenditure=29073287,
                    production_taxes_less_subsidies=-57442, cfc=3836206, ce=9442896, os_mi=13183820,
                    gva_income=26405480),
}


def test_note_totals_vs_eye_transcription() -> None:
    rows = clean("io_tables_sut_note_totals")
    got = {(r["period"], r["item_code"]): r for r in rows}
    assert len(rows) == 36
    for period, items in NOTE.items():
        for code, v in items.items():
            r = got[(period, code)]
            assert r["value"] == v, (period, code, r["value"], v)
            assert r["table_id"] == {"2022-23": "Table 9.1", "2023-24": "Table 9.2"}[period]


def test_note_totals_vs_pypdf_text() -> None:
    """Second, mechanical read: the numbers in reading order on pages 20-22 (pypdf)."""
    pdf = PdfReader(str(raw_path("mospi_sut_2022base/sut_note_2022_23_2023_24.pdf")))
    text = "\n".join(pdf.pages[i].extract_text() for i in (19, 20, 21))
    t1 = text.split("Table 9.1:", 1)[1].split("9.2  Estimates", 1)[0]
    t2 = text.split("Table 9.2:", 1)[1]
    num = re.compile(r"(?m)\s(-?[\d,]{5,})\s*$")
    for period, block in (("2022-23", t1), ("2023-24", t2)):
        vals = [int(m.replace(",", "")) for m in num.findall(block)]
        assert vals == list(NOTE[period].values()), (period, vals)


# --------------------------------------------------------------------------------------------- ADB
ADB_ROW = {"M": "m", "r60": "r60", "r99": "r99", "r61": "r61", "r62": "r62", "r63": "r63", "r64": "r64",
           "trs": "trs", "r69": "r69"}


def parse_adb() -> tuple[dict, dict]:
    wb = CalamineWorkbook.from_path(str(raw_path("adb_mrio/adb_ind_iot_2000_2007_2024.xlsx")))
    cells, stamps = {}, {}
    for sheet in wb.sheet_names[1:]:
        y = int(sheet)
        period = f"{y}-{(y + 1) % 100:02d}"
        rows = wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
        assert norm(rows[0][0]) == f"India Input-Output Table (35x35), {sheet}"
        assert "$ million" in norm(rows[1][0])
        stamps[period] = norm(rows[2][0]) if len(rows) > 2 and rows[2] and rows[2][0] else ""
        # find the code row (c1 in the first data column) by search, not by position
        code_r = next(i for i, r in enumerate(rows) if len(r) > 3 and r[3] == "c1")
        codes = {j: str(v) for j, v in enumerate(rows[code_r]) if j >= 3 and v not in ("", None)}
        # TOTAL column has no code on the code row: take it from the label row above
        for j in range(3, len(rows[code_r])):
            if j not in codes and any(norm(rows[k][j]) == "TOTAL" for k in range(code_r) if j < len(rows[k])):
                codes[j] = "total"
        assert list(codes.values()) == [f"c{k}" for k in range(1, 36)] + [f"F{k}" for k in range(1, 7)] + ["total"]
        for r in rows[code_r + 1:]:
            if not any(x not in ("", None) for x in r):
                continue
            tag, code = r[1], str(r[2])
            if tag in ("IND", "IMP"):
                rk = ("dom_" if tag == "IND" else "imp_") + code
            else:
                rk = ADB_ROW[code]
            for j, cc in codes.items():
                v = r[j] if j < len(r) else ""
                if is_num(v):
                    cells[(period, f"adb.{rk}.{cc.lower()}.current")] = float(v)
    return cells, stamps


def test_adb_every_clean_row_matches_raw_and_nothing_dropped() -> None:
    cells, stamps = parse_adb()
    rows = clean("io_tables_adb_ind_iot")
    bad = []
    have = set()
    for r in rows:
        k = (r["period"], r["series_id"])
        have.add(k)
        if k not in cells:
            bad.append(("no raw", k))
        elif not close(r["value"], cells[k]):
            bad.append(("value", k, r["value"], cells[k]))
        if r["unit"] != "USD_million" or r["period_type"] != "fy" or r["price_basis"] != "current":
            bad.append(("dims", k))
        # vintage = the sheet's own 'as of Month YYYY' stamp, else the file-level August 2025
        st = stamps[r["period"]]
        want = "2025-08"
        if st:
            m = re.fullmatch(r"as of (\w+) (\d{4})", st)
            assert m, st
            mon = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                   "October", "November", "December"].index(m.group(1)) + 1
            want = f"{m.group(2)}-{mon:02d}"
        if r["vintage"] != want:
            bad.append(("vintage", k, r["vintage"], want))
    assert not bad, bad[:20]
    missing = [k for k in cells if k not in have]
    assert not missing, missing[:20]
    assert len(rows) == len(cells)


# --------------------------------------------------------------------------------------------- ICIO
ICIO_FD = ["HFCE", "NPISH", "GGFC", "GFCF", "INVNT", "DPABR"]


def parse_icio_year(zf: zipfile.ZipFile, year: str) -> dict:
    tab = pacsv.read_csv(io.BytesIO(zf.read(f"{year}_SML.csv")),
                         convert_options=pacsv.ConvertOptions(null_values=["NA"], strings_can_be_null=False))
    names = tab.column_names
    labels = [str(x) for x in tab.column(names[0]).to_pylist()]
    mat = np.column_stack([tab.column(c).to_numpy(zero_copy_only=False).astype(float) for c in names[1:]])
    cols = names[1:]
    cidx = {c: j for j, c in enumerate(cols)}
    ridx = {lab: i for i, lab in enumerate(labels)}
    ind_rows = [lab for lab in labels if lab.startswith("IND_")]
    inds = [lab[4:] for lab in ind_rows]
    assert len(inds) == 50
    use_cols = [f"IND_{c}" for c in inds + ICIO_FD]
    for c in use_cols:
        assert c in cidx, c
    period = f"{year}-{(int(year) + 1) % 100:02d}"
    out: dict = {}
    foreign_rows = [i for i, lab in enumerate(labels) if "_" in lab and not lab.startswith("IND_")]
    foreign_cols = [j for j, c in enumerate(cols) if not c.startswith("IND_") and c != "OUT"]
    for code in inds:
        i = ridx[f"IND_{code}"]
        fr = [k for k in foreign_rows if labels[k].split("_", 1)[1] == code]
        assert len(fr) == 80, (code, len(fr))
        for c in use_cols:
            j = cidx[c]
            v = mat[i, j]
            if not np.isnan(v):
                out[(period, f"icio.dom.{code.lower()}.{c[4:].lower()}.current")] = (float(v), "official")
            s = mat[fr, j]
            assert not np.isnan(s).any()
            out[(period, f"icio.imp.{code.lower()}.{c[4:].lower()}.current")] = (float(s.sum()), "derived")
        out[(period, f"icio.out.{code.lower()}.current")] = (float(mat[i, cidx["OUT"]]), "official")
        x = mat[i, foreign_cols]
        assert not np.isnan(x).any()
        out[(period, f"icio.exports.{code.lower()}.current")] = (float(x.sum()), "derived")
    for rcode, item in (("TLS", "tls"), ("VA", "va"), ("OUT", "out_row")):
        i = ridx[rcode]
        for c in use_cols:
            v = mat[i, cidx[c]]
            if not np.isnan(v):
                out[(period, f"icio.{item}.{c[4:].lower()}.current")] = (float(v), "official")
    return out


def test_icio_every_clean_row_matches_raw_and_nothing_dropped() -> None:
    zf = zipfile.ZipFile(raw_path("oecd_icio_2025/icio2025_2016_2022_sml.zip"))
    cells: dict = {}
    for y in range(2016, 2023):
        cells |= parse_icio_year(zf, str(y))
    rows = clean("io_tables_icio_india")
    bad = []
    for r in rows:
        k = (r["period"], r["series_id"])
        if k not in cells:
            bad.append(("no raw", k))
            continue
        v, status = cells[k]
        if not close(r["value"], v, rel=1e-9):
            bad.append(("value", k, r["value"], v))
        if r["status"] != status:
            bad.append(("status", k, r["status"], status))
    assert not bad, bad[:20]
    assert len(rows) == len(cells), (len(rows), len(cells))


# --------------------------------------------------------------------------------------------- IFPRI
# Table 8 (PDF page 24, 'Macro SAM for India in 2022/23 (Billions of Rupees)'), transcribed by eye.
# The printed rows leave blank cells, so columns were assigned by re-adding every row and column
# to its printed total (all close within 2 bn of rounding).
IFPRI_T8 = {
    ("activities", "commodities"): 478153, ("activities", "households"): 17269, ("activities", "total"): 495422,
    ("commodities", "activities"): 248859, ("commodities", "commodities"): 98431,
    ("commodities", "households"): 139795, ("commodities", "government"): 28836,
    ("commodities", "investment"): 92604, ("commodities", "rest_of_world"): 61334, ("commodities", "total"): 669859,
    ("factors", "activities"): 246992, ("factors", "rest_of_world"): 2231, ("factors", "total"): 249222,
    ("enterprises", "factors"): 122869, ("enterprises", "government"): 17643, ("enterprises", "rest_of_world"): 264,
    ("enterprises", "total"): 140776,
    ("households", "factors"): 120362, ("households", "enterprises"): 68289, ("households", "government"): 14989,
    ("households", "rest_of_world"): 8427, ("households", "total"): 212068,
    ("government", "enterprises"): 12993, ("government", "taxes"): 38717, ("government", "rest_of_world"): 17,
    ("government", "total"): 51727,
    ("taxes", "activities"): -428, ("taxes", "commodities"): 22743, ("taxes", "enterprises"): 9114,
    ("taxes", "households"): 7288, ("taxes", "total"): 38717,
    ("savings", "enterprises"): 49632, ("savings", "households"): 47714, ("savings", "government"): -9855,
    ("savings", "rest_of_world"): 5113, ("savings", "total"): 92604,
    ("rest_of_world", "commodities"): 70532, ("rest_of_world", "factors"): 5992,
    ("rest_of_world", "enterprises"): 748, ("rest_of_world", "government"): 113, ("rest_of_world", "total"): 77385,
    ("total", "activities"): 495422, ("total", "commodities"): 669859, ("total", "factors"): 249222,
    ("total", "enterprises"): 140776, ("total", "households"): 212068, ("total", "government"): 51727,
    ("total", "taxes"): 38717, ("total", "investment"): 92604, ("total", "rest_of_world"): 77385,
}


def test_ifpri_table8_transcription_is_internally_consistent() -> None:
    accts = ["activities", "commodities", "factors", "enterprises", "households", "government", "taxes"]
    for a in accts + ["savings", "rest_of_world"]:
        s = sum(v for (r, c), v in IFPRI_T8.items() if r == a and c != "total")
        assert abs(s - IFPRI_T8[(a, "total")]) <= 2, a
    for c in accts + ["investment", "rest_of_world"]:
        s = sum(v for (r, cc), v in IFPRI_T8.items() if cc == c and r != "total")
        assert abs(s - IFPRI_T8[("total", c)]) <= 2, c


def test_ifpri_table8_vs_clean() -> None:
    rows = [r for r in clean("io_tables_ifpri_2223_datapaper") if r["table_id"] == "Table 8"]
    got = {}
    for r in rows:
        kv = dict(p.split("=") for p in r["dim_other"].split(";"))
        got[(kv["row"], kv["col"])] = r
    assert set(got) == set(IFPRI_T8)
    for k, v in IFPRI_T8.items():
        r = got[k]
        assert r["unit"] == "INR_crore" and r["status"] == "estimated" and r["period"] == "2022-23"
        assert r["value"] == v * 100, (k, r["value"], v)  # Rs billion -> Rs crore: x 100


def _ifpri_group_lines(page_text: str, caption: str) -> dict[str, list[float]]:
    block = page_text.split(caption, 1)[1].split("Source:", 1)[0]
    groups = {"All households": "all", "Quintile 1": "q1", "Quintile 2": "q2", "Quintile 3": "q3",
              "Quintile 4": "q4", "Quintile 5": "q5", "Rural households": "rural", "Urban households": "urban"}
    out = {}
    for line in block.splitlines():
        line = line.strip()
        for lab, g in groups.items():
            if line.startswith(lab + " "):
                out[g] = [float(t.replace(",", "")) for t in line[len(lab):].split()]
    assert sorted(out) == sorted(groups.values())
    return out


def test_ifpri_tables_10_11_vs_pypdf_text() -> None:
    pdf = PdfReader(str(raw_path("ifpri_nexus_sam_india_2022_23_paper/ifpri_sam_india_2022_23_data_paper.pdf")))
    text = pdf.pages[25].extract_text()
    t10 = _ifpri_group_lines(text, "Table 10: Household Income Sources in India (2022/23)")
    t11 = _ifpri_group_lines(text, "Table 11: Household Populations and Expenditures in India (2022/23)")
    # eye check of a few printed cells (PDF page 26)
    assert t10["q5"][0] == 44.7 and t10["urban"][4] == 0.2 and t10["all"][9] == 4.0
    assert t11["all"][0] == 1406.6 and t11["q1"][3] == 45 and t11["urban"][6] == 24.0
    t10_cols = ["labour_all", "labour_low_educated", "labour_medium_educated", "labour_high_educated", "crop_land",
                "capital_all", "capital_agriculture", "capital_non_agriculture", "transfers_government",
                "transfers_world", "total"]
    t11_cols = [("population", 1e6), ("population_share", 1), ("consumption_share", 1),
                ("consumption_per_capita", 1e3), ("food_share", 1), ("total_spending_per_capita", 1e3),
                ("savings_rate", 1)]
    rows = {(r["table_id"], r["item_code"], r["household_group"]): r
            for r in clean("io_tables_ifpri_2223_datapaper") if r["table_id"] != "Table 8"}
    n = 0
    for g, vals in t10.items():
        assert len(vals) == 11
        for code, v in zip(t10_cols, vals, strict=True):
            r = rows[("Table 10", f"income_share.{code}", g)]
            assert r["value"] == v and r["unit"] == "percent", (g, code, r["value"], v)
            n += 1
    for g, vals in t11.items():
        assert len(vals) == 7
        for (code, f), v in zip(t11_cols, vals, strict=True):
            r = rows[("Table 11", code, g)]
            assert abs(r["value"] - v * f) < 1e-6, (g, code, r["value"], v * f)
            n += 1
    assert n == len(rows) == 144


# --------------------------------------------------------------------------------------------- energy PSUT
# Close-out pass (2026-09-29): io_tables_energy_psut (Energy Statistics India 2026, Ch. 9, Tables 9.2/9.3
# (A)/(B), PDF pages 12-15, PJ). Independent of energy.py in three ways:
# - text engine: PDFium (pypdfium2 char boxes); the unit uses pdfminer through pdfplumber;
# - column assignment: each column is anchored on the right edge of its own HEADER word ('A)', 'B)', ...,
#   'Transport*', 'Construct*', 'Industries', 'Househol*', 'Accumulati*', 'Export', 'Statsitical',
#   '(Imports)', 'Environm', 'Total'); the unit anchors on the numbers of the TOTAL SUPPLY/USE row;
# - the column assignment is then re-proved against the printed SUB-TOTAL rows ('Total', 'Total
#   Transformed Energy', 'Total End Use for Energy purposes', 'Total energy residuals'), which the unit
#   does not ingest, by comparing the non-zero column sums in column order with the printed numbers.
# Row codes come from the explicit maps below, not from the unit's slug().
PSUT_PDF = "mospi_energy_statistics/es2026_chapter_9.pdf"
PSUT_TABLES = {  # table_id -> (0-based PDF page, period, kind, caption)
    "Table 9.2 (A)": (11, "2023-24", "supply", "Table 9.2 (A) Physical Supply Table for Energy for the year 2023-24"),
    "Table 9.2 (B)": (12, "2023-24", "use", "Table 9.2 (B) Physical Use Table for Energy for the year 2023-24"),
    "Table 9.3 (A)": (13, "2024-25", "supply",
                      "Table 9.3 (A) Physical Supply Table for Energy for the year 2024-25 (P)"),
    "Table 9.3 (B)": (14, "2024-25", "use", "Table 9.3 (B) Physical Use Table for Energy for the year 2024-25 (P)"),
}
PSUT_SECTIONS = {"Energy from natural inputs:": "natural_inputs", "Energy Products:": "energy_products",
                 "Energy Residuals:": "residuals", "Other Residual Flows:": "other_residual_flows"}
PSUT_SUBSECTIONS = {"Natural resource inputs": "natural_resource_inputs",
                    "Production of energy products by SIEC class:": "production",
                    "Transformaton of energy products by SIEC class": "transformation",  # sic
                    "End-use of energy products by SIEC class:": "end_use"}
PSUT_ROWS = {
    "Coal": "coal", "Lignite": "lignite", "Crude Oil": "crude_oil", "Natural Gas": "natural_gas",
    "Nuclear": "nuclear", "Inputs from RES": "inputs_from_res", "Hydro": "hydro", "Oil Products": "oil_products",
    "Electricity": "electricity",
    "End-use of energy products for non-energy purposes": "end_use_of_energy_products_for_non_energy_purposes",
    "Distribution": "distribution", "Extraction": "extraction",
    "Other Losses (Coal Reject/other residuals)": "other_losses_coal_reject_other_residuals",
    "Other Energy Residuals": "other_energy_residuals",
    "Residuals from end-use for non-energy purposes": "residuals_from_end_use_for_non_energy_purposes",
    "Energy from solid waste": "energy_from_solid_waste",
}
PSUT_PRODUCTS = {"coal", "lignite", "crude_oil", "oil_products", "natural_gas", "electricity", "nuclear",
                 "inputs_from_res", "hydro"}
PSUT_SUBTOTALS = {"Total": None, "Total Transformed Energy": "energy_products.transformation",
                  "Total End Use for Energy purposes": "energy_products.end_use",
                  "Total energy residuals": "residuals"}
PSUT_INDUSTRY = ["isic_a", "isic_b", "isic_c", "isic_d", "transport_storage"]
PSUT_COLS = {
    "supply": PSUT_INDUSTRY + ["other_industries", "households", "accumulation", "rest_of_world_imports",
                               "environment", "total"],
    "use": PSUT_INDUSTRY + ["construction", "other_industries", "households", "accumulation", "exports",
                            "statistical_difference", "flows_to_environment", "total"],
}
PSUT_NUM = re.compile(r"-?\d+(?:\.\d+)?")


def _psut_words(page) -> list[dict]:
    """Words (text, left, right, baseline) from PDFium char boxes: a new word at whitespace or a gap."""
    tp = page.get_textpage()
    out: list[dict] = []
    cur = None
    for i in range(tp.count_chars()):
        ch = tp.get_text_range(i, 1)
        left, bottom, right, _top = tp.get_charbox(i, loose=True)  # loose: font box, same bottom for every glyph
        if not ch.strip():
            cur = None
            continue
        if cur is not None and abs(cur["y"] - bottom) < 2 and left - cur["r"] < 1.2:
            cur["t"] += ch
            cur["r"] = right
        else:
            cur = {"t": ch, "l": left, "r": right, "y": bottom}
            out.append(cur)
    return out


def _psut_lines(words: list[dict]) -> list[list[dict]]:
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: -w["y"]):
        if lines and abs(lines[-1][0]["y"] - w["y"]) <= 2.5:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(ln, key=lambda w: w["l"]) for ln in lines]


def _psut_anchors(lines: list[list[dict]], kind: str) -> dict[str, float]:
    """Right edge of each column's own header word (header = every line above the first section label)."""
    first = next(i for i, ln in enumerate(lines) if " ".join(w["t"] for w in ln) == "Energy from natural inputs:")
    hdr = [w for ln in lines[:first] for w in ln]

    def one(pred, what: str) -> float:
        hits = [w for w in hdr if pred(w)]
        assert len(hits) == 1, (kind, what, [(w["t"], w["r"]) for w in hits])
        return hits[0]["r"]

    isic_line = next(ln for ln in lines[:first] if any(w["t"] == "A)" for w in ln))
    a: dict[str, float] = {}
    for col, letter in zip(PSUT_INDUSTRY[:4], "ABCD", strict=True):
        hits = [w for w in isic_line if w["t"] == f"{letter})"]
        assert len(hits) == 1, (kind, letter)
        a[col] = hits[0]["r"]
    a["transport_storage"] = one(lambda w: w["t"].startswith("Transport"), "transport")
    # 'Other' / 'Industries' column: the 'Industries' word that is not the spanning 'Industries (by ISIC)'
    spans = {id(ln[i]) for ln in lines[:first] for i in range(len(ln) - 1) if ln[i + 1]["t"] == "(by"}
    a["other_industries"] = one(lambda w: w["t"] == "Industries" and id(w) not in spans, "other industries")
    a["households"] = one(lambda w: w["t"].startswith("Househol"), "households")
    a["accumulation"] = one(lambda w: w["t"].startswith("Accumulati"), "accumulation")
    total_hdr = [w for w in hdr if w["t"] == "Total"]
    assert len(total_hdr) == 1, kind
    a["total"] = total_hdr[0]["r"]
    if kind == "supply":
        a["rest_of_world_imports"] = one(lambda w: w["t"] == "(Imports)", "imports")
        a["environment"] = one(lambda w: w["t"] == "Environm", "environment")
    else:
        a["construction"] = one(lambda w: w["t"].startswith("Construct"), "construction")
        a["exports"] = one(lambda w: w["t"] == "Export", "exports")
        a["statistical_difference"] = one(lambda w: w["t"] == "Statsitical", "stat diff")  # sic
        a["flows_to_environment"] = one(lambda w: w["t"] == "Environm", "flows to environment")
    assert sorted(a) == sorted(PSUT_COLS[kind]), kind
    order = sorted(a, key=a.get)
    assert order == PSUT_COLS[kind], (kind, order)  # header words run left to right in the expected order
    return a


def _psut_label(words: list[dict]) -> str:
    return re.sub(r"\s*-\s*", "-", " ".join(w["t"] for w in words)).strip()


def parse_psut() -> tuple[dict, dict, list]:
    """Returns (cells, tokens, subtotal_checks): cells maps (table_id, item_code, column) -> value for every
    printed detail cell (sub-total rows excluded, grand total rows included as item 'total.total_<kind>')."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(raw_path(PSUT_PDF)))
    cells: dict = {}
    tokens: dict = {}
    subtotals: list = []
    try:
        for tid, (pno, _period, kind, caption) in PSUT_TABLES.items():
            page = pdf[pno]
            text = page.get_textpage().get_text_range()
            assert caption in " ".join(text.split()), (tid, "caption")
            assert "(Unit:PJ)" in text, (tid, "unit caption")
            lines = _psut_lines(_psut_words(page))
            anchors = _psut_anchors(lines, kind)
            cols = PSUT_COLS[kind]
            grand = "TOTAL SUPPLY" if kind == "supply" else "TOTAL USE"
            sec = sub = None
            for ln in lines:
                label_w = [w for w in ln if not PSUT_NUM.fullmatch(w["t"])]
                num_w = [w for w in ln if PSUT_NUM.fullmatch(w["t"])]
                label = _psut_label(label_w)
                if label in PSUT_SECTIONS:
                    sec, sub = PSUT_SECTIONS[label], None
                    continue
                if label in PSUT_SUBSECTIONS:
                    sub = PSUT_SUBSECTIONS[label]
                    continue
                if sec is None or label.startswith("|") or "P a g e" in label or label.isdigit():
                    continue
                # sub-total rows: keep the printed numbers in reading order (one label is overprinted
                # with its first number, 'purposes1133', so numbers are taken by regex from every word)
                st = next((k for k in PSUT_SUBTOTALS if re.sub(r"-?\d.*$", "", label).strip() == k), None)
                if st is not None and label != grand:
                    block = PSUT_SUBTOTALS[st] or ".".join(x for x in (sec, sub) if x)
                    nums = [float(m) for w in ln for m in PSUT_NUM.findall(w["t"])]
                    subtotals.append((tid, block, st, nums))
                    continue
                if label == grand:
                    item = f"total.{grand.lower().replace(' ', '_')}"
                else:
                    assert label in PSUT_ROWS, (tid, "unmapped row label", label)
                    item = ".".join(x for x in (sec, sub, PSUT_ROWS[label]) if x)
                row: dict[str, float] = {}
                for w in num_w:
                    col = min(anchors, key=lambda c: abs(anchors[c] - w["r"]))
                    assert abs(anchors[col] - w["r"]) <= 15, (tid, label, w["t"], w["r"], anchors)
                    assert col not in row, (tid, label, col)
                    row[col] = float(w["t"])
                    tokens[(tid, item, col)] = w["t"]
                if not row:  # printed fully blank (supply 'Energy from solid waste'): no cell, no clean row
                    assert (tid, label) in {(_A2, "Energy from solid waste"), (_A3, "Energy from solid waste")}, \
                        (tid, "unexpected blank row", label)
                    continue
                for col, v in row.items():
                    assert (tid, item, col) not in cells, (tid, item, col)
                    cells[(tid, item, col)] = v
            # the supply 'Accumulation' column is empty in both years; nothing may be assigned to it
            if kind == "supply":
                assert not [k for k in cells if k[0] == tid and k[2] == "accumulation"], tid
            assert {k[2] for k in cells if k[0] == tid} <= set(cols)
    finally:
        pdf.close()
    return cells, tokens, subtotals


@pytest.fixture(scope="module")
def psut_raw() -> tuple[dict, dict, list]:
    return parse_psut()


def _psut_key(r: dict) -> tuple[str, str, str]:
    kind = "supply" if r["table_id"].endswith("(A)") else "use"
    col = r["series_id"].rsplit(".", 1)[1]
    assert r["series_id"] == f"psut.{kind}.{r['item_code']}.{col}", r["series_id"]
    return r["table_id"], r["item_code"], col


def test_psut_every_clean_row_matches_raw_and_nothing_dropped(psut_raw) -> None:
    cells, tokens, _ = psut_raw
    rows = clean("io_tables_energy_psut")
    assert len(rows) == len(cells) == 324
    assert Counter(r["table_id"] for r in rows) == {"Table 9.2 (A)": 56, "Table 9.2 (B)": 106,
                                                    "Table 9.3 (A)": 56, "Table 9.3 (B)": 106}
    bad, have = [], set()
    for r in rows:
        k = _psut_key(r)
        have.add(k)
        if k not in cells:
            bad.append(("no raw cell", k))
            continue
        # the writer rounds to 6 decimals: the stored value must be the printed token rounded to 6 dp
        if r["value"] != round(cells[k], 6):
            bad.append(("value", k, r["value"], tokens[k]))
    assert not bad, bad[:20]
    assert set(cells) == have
    # the one printed value with more than 6 decimals (issue io_tables-17b)
    long = {k: t for k, t in tokens.items() if "." in t and len(t.split(".")[1]) > 6}
    assert long == {("Table 9.3 (B)", "energy_products.end_use.coal", "isic_a"): "0.16179072"}


def test_psut_metadata_and_provenance(psut_raw) -> None:
    rows = clean("io_tables_energy_psut")
    prov = {p["prov_id"]: p for p in pq.read_table(CLEAN / "_provenance.parquet").to_pylist()}
    pin = _pins()[PSUT_PDF]
    bad = []
    for r in rows:
        pno, period, kind, caption = PSUT_TABLES[r["table_id"]]
        want = {"source_id": "mospi_energy_statistics", "unit": "PJ", "price_basis": "n/a", "base_year": None,
                "status": "official", "vintage": "2026-03-30", "period": period, "period_type": "fy",
                "estimate_stage": "Provisional" if period == "2024-25" else "n.a.", "stock_flow": "flow",
                "geography": "IN", "side": "resources" if kind == "supply" else "uses"}
        bad += [(r["series_id"], c, r[c], v) for c, v in want.items() if r[c] != v]
        p = prov[r["prov_id"]]
        if not (p["table_id"] == r["table_id"] and p["raw_sha256"] == pin["sha256"] and p["unit_as_published"] == "PJ"
                and p["conversion"] == "none" and f"PDF page {pno + 1}:" in p["locator"] and caption in p["locator"]
                and p["vintage"] == r["vintage"] and p["status"] == "official"):
            bad.append(("prov", r["series_id"], p["locator"]))
    assert not bad, bad[:20]
    # vintage evidence: the release press note in the registry is dated 30 Mar 2026 (upload stamp
    # 1774858925751 ms), and the chapter PDF was last modified before that (/ModDate 2026-03-24)
    reg = yaml.safe_load((ROOT / "data" / "registry.yaml").read_text(encoding="utf-8"))
    src = next(s for s in (reg["sources"] if isinstance(reg, dict) else reg) if s["id"] == "mospi_energy_statistics")
    assert str(src["latest_release"]["date"]) == "2026-03-30"
    assert PdfReader(str(raw_path(PSUT_PDF))).metadata["/ModDate"].startswith("D:20260324")


PSUT_EXPECTED_DIMS = {
    "industry": {c: c for c in PSUT_INDUSTRY + ["construction", "other_industries"]},
    "institution": {"households": "households"},
    "counterparty": {"rest_of_world_imports": "rest_of_world", "exports": "rest_of_world",
                     "environment": "environment", "flows_to_environment": "environment"},
}


def test_psut_dimensions_follow_the_printed_column(psut_raw) -> None:
    bad = []
    for r in clean("io_tables_energy_psut"):
        _, item, col = _psut_key(r)
        if r["dim_other"] != f"psut_column={col}":
            bad.append(("dim_other", r["series_id"], r["dim_other"]))
        for dim, m in PSUT_EXPECTED_DIMS.items():
            if r[dim] != m.get(col):
                bad.append((dim, r["series_id"], r[dim], m.get(col)))
        leaf = item.rsplit(".", 1)[1]
        want_prod = leaf if item.startswith(("natural_inputs.", "energy_products.")) and leaf in PSUT_PRODUCTS else None
        if r["product"] != want_prod:
            bad.append(("product", r["series_id"], r["product"], want_prod))
        for dim in ("instrument", "household_group"):
            if r[dim] is not None:
                bad.append((dim, r["series_id"], r[dim]))
    assert not bad, bad[:20]


def test_psut_column_assignment_reproves_printed_subtotals(psut_raw) -> None:
    """The unit does not ingest the section sub-total rows, and some are printed centred or overprinted,
    so only their numbers in reading order are used: the non-zero column sums of the detail rows of
    the block (in column order) must equal the non-zero printed numbers, within 2 PJ of rounding.
    The grand TOTAL SUPPLY / TOTAL USE rows are ingested; they must equal the column sums of all detail
    rows except in the publication's oil-products gap (io_tables-8), which shows up only in 'total'."""
    cells, _, subtotals = psut_raw
    assert len(subtotals) == 14, [  # supply 3 x 2 tables, use 4 x 2 tables
        (t, b) for t, b, _, _ in subtotals]
    for tid, block, st, printed in subtotals:
        kind = PSUT_TABLES[tid][2]
        sums = []
        for col in PSUT_COLS[kind]:
            vals = [v for (t, it, c), v in cells.items() if t == tid and c == col and it.startswith(block + ".")
                    and it != "energy_products.end_use.end_use_of_energy_products_for_non_energy_purposes"]
            sums.append(sum(vals))
        want = [s for s in sums if abs(s) > 1e-9]
        got = [p for p in printed if p != 0]
        assert len(got) == len(want) and all(abs(a - b) <= 2 for a, b in zip(got, want, strict=True)), \
            (tid, st, got, want)
    for tid, (_, _, kind, _) in PSUT_TABLES.items():
        grand = f"total.total_{kind}"
        for col in PSUT_COLS[kind]:
            s = sum(v for (t, it, c), v in cells.items() if t == tid and c == col and it != grand)
            printed = cells.get((tid, grand, col), 0.0)
            assert abs(s - printed) <= 2, (tid, col, s, printed)
    # every printed row adds up to its own Total column (2 PJ of rounding)
    for tid in PSUT_TABLES:
        for item in {it for (t, it, _c) in cells if t == tid}:
            parts = sum(v for (t, it, c), v in cells.items() if t == tid and it == item and c != "total")
            if any(t == tid and it == item and c != "total" for (t, it, c) in cells):
                assert abs(parts - cells[(tid, item, "total")]) <= 2, (tid, item, parts)
    # the publication's own imbalance (io_tables-8): TOTAL USE exceeds TOTAL SUPPLY by 129 / 145 PJ
    for s_t, u_t, gap in (("Table 9.2 (A)", "Table 9.2 (B)", 129), ("Table 9.3 (A)", "Table 9.3 (B)", 145)):
        assert cells[(u_t, "total.total_use", "total")] - cells[(s_t, "total.total_supply", "total")] == gap


# Seeded by-eye sample (>= 10% of the 324 PSUT rows, min 30). Keys drawn with random.Random(SEED) from
# the sorted (table_id, series_id) list; values typed from the page text of PDF pages 12-15 (pypdf
# extract_text, one printed line per row), each number placed in its column by re-adding the
# printed rows and the printed sub-total rows of that page by hand.
_A2, _B2, _A3, _B3 = "Table 9.2 (A)", "Table 9.2 (B)", "Table 9.3 (A)", "Table 9.3 (B)"
PSUT_EYE: dict[tuple[str, str], float] = {
    # page 12, 9.2 (A). 'Crude Oil 1256 10024 11280': imports column (imports total 19226 = 5930+0+10024+2018+1231+22)
    (_A2, "psut.supply.energy_products.production.crude_oil.rest_of_world_imports"): 10024,
    (_A2, "psut.supply.natural_inputs.natural_resource_inputs.natural_gas.environment"): 1411,
    # 'Distribution 1143 1040 2183': ISIC D = 8475 - 7051 - 384 = 1040
    (_A2, "psut.supply.residuals.distribution.isic_d"): 1040,
    # page 13, 9.2 (B). Coal end use '0.089786 2.112574 6902 0 0 48 0 431 44 -344 7083'
    (_B2, "psut.use.energy_products.end_use.coal.statistical_difference"): -344,
    (_B2, "psut.use.energy_products.end_use.coal.transport_storage"): 0,  # transport 5783 = 5064+597+122
    # 'Crude Oil 1140 -1052 89': other industries 6472 = 48+39+1140+2778+484+1982 (+1 rounding)
    (_B2, "psut.use.energy_products.end_use.crude_oil.other_industries"): 1140,
    (_B2, "psut.use.energy_products.end_use.electricity.isic_b"): 1,  # 'Electricity 992 1 2162 384 ...'
    (_B2, "psut.use.energy_products.end_use.electricity.isic_c"): 2162,
    (_B2, "psut.use.energy_products.end_use.natural_gas.households"): 0,  # households 2582 = 1253 + 1329
    (_B2, "psut.use.energy_products.transformation.natural_gas.total"): 352,
    (_B2, "psut.use.natural_inputs.natural_resource_inputs.inputs_from_res.isic_d"): 844,  # D = 523+844+484
    (_B2, "psut.use.residuals.other_losses_coal_reject_other_residuals.total"): 0,
    (_B2, "psut.use.total.total_use.statistical_difference"): -376,
    (_B2, "psut.use.total.total_use.transport_storage"): 5783,
    # page 14, 9.3 (A)
    (_A3, "psut.supply.natural_inputs.natural_resource_inputs.inputs_from_res.total"): 964,
    (_A3, "psut.supply.natural_inputs.natural_resource_inputs.natural_gas.environment"): 1398,
    (_A3, "psut.supply.residuals.distribution.isic_b"): 1187,  # 'Distribution 1187 1088 2275'; B 22415-20712-516
    (_A3, "psut.supply.total.total_supply.total"): 113364,
    # page 15, 9.3 (B). Coal end use '0.16179072 1.880 7167 0 0 48 0 389 54 -1100 6560'
    (_B3, "psut.use.energy_products.end_use.coal.isic_a"): round(0.16179072, 6),  # writer keeps 6 decimals
    (_B3, "psut.use.energy_products.end_use.coal.isic_b"): 1.88,
    (_B3, "psut.use.energy_products.end_use.coal.total"): 6560,
    (_B3, "psut.use.energy_products.end_use.crude_oil.other_industries"): 1185,  # 'Crude Oil 1185 -1043 142'
    # 'Electricity 937 1 2211 404 124 0 2189 1471 38 67 7442': exports 2932 = 54+0+2840+0+38
    (_B3, "psut.use.energy_products.end_use.electricity.exports"): 38,
    (_B3, "psut.use.energy_products.end_use.electricity.isic_a"): 937,
    (_B3, "psut.use.energy_products.end_use.electricity.isic_c"): 2211,
    # 'Lignite 0 0.000 42 0 0 44 0 7 0 0 92'
    (_B3, "psut.use.energy_products.end_use.lignite.exports"): 0,
    (_B3, "psut.use.energy_products.end_use.lignite.isic_a"): 0,
    (_B3, "psut.use.energy_products.end_use.lignite.statistical_difference"): 0,
    # 'Natural Gas 6 442 1010 659 0 512 0 0 -192 2437'
    (_B3, "psut.use.energy_products.end_use.natural_gas.exports"): 0,
    (_B3, "psut.use.energy_products.end_use.natural_gas.households"): 0,
    (_B3, "psut.use.energy_products.end_use.natural_gas.isic_b"): 442,
    (_B3, "psut.use.energy_products.end_use.oil_products.construction"): 22,  # construction total 22
    (_B3, "psut.use.energy_products.transformation.crude_oil.total"): 11494,
    (_B3, "psut.use.natural_inputs.natural_resource_inputs.nuclear.isic_d"): 618,
    (_B3, "psut.use.residuals.distribution.flows_to_environment"): 2275,
    (_B3, "psut.use.residuals.other_energy_residuals.flows_to_environment"): 28579,
}


def test_psut_seeded_eye_sample() -> None:
    rows = {(r["table_id"], r["series_id"]): r for r in clean("io_tables_energy_psut")}
    keys = sorted(rows)
    sample = sorted(random.Random(SEED).sample(keys, 36))
    assert len(sample) >= max(30, len(keys) // 10)
    assert sorted(PSUT_EYE) == sample
    bad = [(k, rows[k]["value"], v) for k, v in PSUT_EYE.items() if rows[k]["value"] != v]
    assert not bad, bad


def test_psut_s6_coverage_claim(psut_raw) -> None:
    """S6 (physical energy use by industry, 2023-24) is declared partial with 37 series: every
    printed industry-column cell of Table 9.2 (B) in the transformation and end-use sections, and
    nothing else (no households, totals, natural-input extraction or statistical difference)."""
    cells, _, _ = psut_raw
    cov = yaml.safe_load((ROOT / "pipeline/ingest/io_tables_coverage.yaml").read_text(encoding="utf-8"))
    entries = cov if isinstance(cov, list) else next(v for v in cov.values() if isinstance(v, list))
    s6 = [e for e in entries if e.get("ref") == "S6"]
    assert len(s6) == 1
    e = s6[0]
    assert e["dataset"] == "io_tables_energy_psut" and str(e["period"]) == "2023-24" and e["extent"] == "partial"
    industry_cols = set(PSUT_INDUSTRY) | {"construction", "other_industries"}
    want = sorted(f"psut.use.{it}.{c}" for (t, it, c) in cells if t == "Table 9.2 (B)" and c in industry_cols
                  and it.startswith(("energy_products.transformation.", "energy_products.end_use."))
                  and it != "energy_products.end_use.end_use_of_energy_products_for_non_energy_purposes")
    assert sorted(e["series_ids"]) == want and len(want) == 37
    # the claimed series exist for 2023-24 in the written data
    have = {r["series_id"] for r in clean("io_tables_energy_psut") if r["period"] == "2023-24"}
    assert set(e["series_ids"]) <= have
    # the printed 'Total End Use for Energy purposes' industry sums (read by eye, page 13):
    # A 1183, B 497, C 10682, D 384, transport 5783, construction 19, other 6472
    eu = {c: sum(v for (t, it, cc), v in cells.items() if t == "Table 9.2 (B)" and cc == c
                 and it.startswith("energy_products.end_use.") and "non_energy" not in it)
          for c in ["isic_a", "isic_b", "isic_c", "isic_d", "transport_storage", "construction", "other_industries"]}
    for c, v in zip(eu, [1183, 497, 10682, 384, 5783, 19, 6472], strict=True):
        assert abs(eu[c] - v) <= 2, (c, eu[c], v)


# --------------------------------------------------------------------------------------------- sample log
def test_seeded_sample_report(sut_raw: dict, capsys: pytest.CaptureFixture[str]) -> None:
    """Seeded stratified sample, printed for the verifier notes (the exhaustive tests above already
    compare every row; this only records a human-readable slice)."""
    rng = random.Random(SEED)
    lines = []
    for ds in ("io_tables_sut_supply", "io_tables_sut_use", "io_tables_sut_va"):
        rows = clean(ds)
        strata = Counter((r["period"], r["item_code"]) for r in rows)
        for (period, item) in sorted(strata):
            pool = [r for r in rows if r["period"] == period and r["item_code"] == item]
            for r in rng.sample(pool, min(2, len(pool))):
                raw_v = sut_raw[period][0][(ds, item, r["product"], r["industry"])]
                assert close(r["value"], raw_v)
                lines.append(f"{ds} {period} {r['series_id']} clean={r['value']:.4f} raw={raw_v:.4f}")
    with capsys.disabled():
        print("\n" + "\n".join(lines))
