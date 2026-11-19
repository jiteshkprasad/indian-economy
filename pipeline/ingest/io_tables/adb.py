"""ADB Key Indicators Database: 'IND IOT 2000, 2007-2024.xlsx' (India national input-output table,
35 x 35 WIOD sectors, current US$ million, 'as of August 2025').

One dataset, io_tables_adb_ind_iot: every published cell of the 19 year sheets (2000, 2007-2024):
- rows 'IND' c1..c35: domestic intermediate and final use (origin=domestic);
- rows 'IMP' c1..c35: imported intermediate and final use (origin=imports), the prior for the
  optional non-competitive import matrix (gap map P6a);
- rows M (total imports), r60 (intermediate input total), r99 (taxes less subsidies on products),
  r61/r62/r63 (CIF/FOB adjustment, direct purchases abroad, non-resident purchases; zero for India),
  r64 (value added at basic prices), trs (international transport margins), r69 (total);
- columns c1..c35 (using industry), F1..F6 (household, NPISH, government final consumption, GFCF,
  changes in inventories and valuables, exports) and TOTAL.
Explicit zeros are kept (ADB prints them); empty cells produce no row.

Year convention (registry `adb_mrio`, verifier-corrected, inference): the sheet label is the first
year of India's fiscal year, so sheet '2023' is FY 2023-24. The table is on India's OLD 2011-12
national-accounts base (registry: 2022 VA x 78.6045 = old-base GVA 246.47 lakh crore). It is a
labelled international prior, never a SAM cell by itself (status 'official' = as ADB published it).
Values stay in US$ million: no conversion to rupees here (that needs an INR_per_USD series).
"""

from __future__ import annotations

from typing import Any

import openpyxl
import polars as pl
from openpyxl.utils import get_column_letter

from pipeline.core.unit import BuildContext, Dataset
from pipeline.core.units import clean_label, parse_number

SRC = "adb_mrio"
FILE = "adb_ind_iot_2000_2007_2024.xlsx"
# Each year sheet carries its own 'as of <Month YYYY>' stamp in A3 (2017, 2022-2024: August 2025;
# 2018-2020: September 2024; 2021: August 2024). Sheets 2000-2016 have none: they get the file-level
# date ('Updated on August 2025' on the KIDB listing; HTTP Last-Modified 5 Dec 2025).
FILE_VINTAGE = "2025-08"
RELEASE = "ADB Key Indicators Database, national IOT 'IND IOT 2000, 2007-2024.xlsx' (updated August 2025)"
YEARS = ["2000", *[str(y) for y in range(2007, 2025)]]

SECTORS = (
    "Agriculture, hunting, forestry, and fishing",
    "Mining and quarrying",
    "Food, beverages, and tobacco",
    "Textiles and textile products",
    "Leather, leather products, and footwear",
    "Wood and products of wood and cork",
    "Pulp, paper, paper products, printing, and publishing",
    "Coke, refined petroleum, and nuclear fuel",
    "Chemicals and chemical products",
    "Rubber and plastics",
    "Other nonmetallic minerals",
    "Basic metals and fabricated metal",
    "Machinery, nec",
    "Electrical and optical equipment",
    "Transport equipment",
    "Manufacturing, nec; recycling",
    "Electricity, gas, and water supply",
    "Construction",
    "Sale, maintenance, and repair of motor vehicles and motorcycles; retail sale of fuel",
    "Wholesale trade and commission trade, except of motor vehicles and motorcycles",
    "Retail trade, except of motor vehicles and motorcycles; repair of household goods",
    "Hotels and restaurants",
    "Inland transport",
    "Water transport",
    "Air transport",
    "Other supporting and auxiliary transport activities; activities of travel agencies",
    "Post and telecommunications",
    "Financial intermediation",
    "Real estate activities",
    "Renting of M&Eq and other business activities",
    "Public administration and defense; compulsory social security",
    "Education",
    "Health and social work",
    "Other community, social, and personal services",
    "Private households with employed persons",
)
FINAL = {
    "F1": "Final consumption expenditure by households",
    "F2": "Final consumption expenditure by non-profit organisations serving households (NPISH)",
    "F3": "Final consumption expenditure by government",
    "F4": "Gross fixed capital formation",
    "F5": "Changes in inventories and valuables",
    "F6": "Exports",
}
# other rows: code -> (item_code, published label)
OTHER_ROWS = {
    "M": ("total_imports", "Total Imports"),
    "r60": ("intermediate_input_total", "Intermediate input total"),
    "r99": ("taxes_less_subsidies_on_products", "Taxes less subsidies on products"),
    "r61": ("cif_fob_adjustments_on_exports", "CIF / FOB adjustments on exports"),
    "r62": ("direct_purchases_abroad_by_residents", "Direct purchases abroad by residents"),
    "r63": ("purchases_by_nonresidents_in_domestic_territory", "Purchases on the domestic territory by non-residents"),
    "r64": ("value_added_basic_prices", "Value added at basic prices"),
    "trs": ("international_transport_margins", "International Transport Margins"),
    "r69": ("total", "TOTAL"),
}
FIRST_DATA_COL = 4  # column D
HEADER_LABEL_ROW, HEADER_CODE_ROW, FIRST_DATA_ROW = 5, 7, 8


_L = get_column_letter  # 1-based column number -> Excel letters, so the locator follows the layout constants


def _fy(sheet: str) -> str:
    y = int(sheet)
    return f"{y}-{(y + 1) % 100:02d}"


class _Grid:
    """A year sheet materialised as a list of rows (read-only openpyxl is slow on random access)."""

    def __init__(self, title: str, grid: list[list[Any]]) -> None:
        self.title, self.grid = title, grid

    def value(self, r: int, c: int) -> Any:
        row = self.grid[r - 1] if r - 1 < len(self.grid) else []
        return row[c - 1] if c - 1 < len(row) else None


MONTHS = {m: i for i, m in enumerate(("January", "February", "March", "April", "May", "June", "July", "August",
                                      "September", "October", "November", "December"), start=1)}


def _vintage(w: _Grid) -> tuple[str, str | None]:
    """The sheet's own 'as of <Month YYYY>' stamp (row 3), or the file-level update date if absent."""
    stamp = w.value(3, 1)
    if stamp is None:
        return FILE_VINTAGE, None
    text = clean_label(str(stamp))
    parts = text.split()
    if len(parts) != 4 or parts[:2] != ["as", "of"] or parts[2] not in MONTHS or not parts[3].isdigit():
        raise ValueError(f"ADB sheet {w.title!r} A3: unexpected vintage stamp {text!r}")
    return f"{parts[3]}-{MONTHS[parts[2]]:02d}", text


def _expect(ws: _Grid, r: int, c: int, text: str) -> None:
    got = clean_label(str(ws.value(r, c) or ""))
    if got != text:
        raise ValueError(f"ADB sheet {ws.title!r} R{r}C{c}: expected {text!r}, found {got!r}")


def build_adb(ctx: BuildContext) -> Dataset:
    raw = ctx.raw(SRC, FILE)
    wb = openpyxl.load_workbook(raw.path, data_only=True, read_only=True)
    if wb.sheetnames != ["Table of Contents", *YEARS]:
        raise ValueError(f"ADB IND IOT: sheets {wb.sheetnames}, expected Table of Contents + {YEARS}")
    rows: list[dict[str, Any]] = []
    for sheet in YEARS:
        ws = wb[sheet]
        grid = [list(r) for r in ws.iter_rows(values_only=True)]

        w = _Grid(sheet, grid)
        _expect(w, 1, 1, f"India Input-Output Table (35x35), {sheet}")
        _expect(w, 2, 1, "(at current prices, $ million)")
        vintage, stamp = _vintage(w)
        # column header: 35 sectors, F1..F6, TOTAL
        cols: dict[int, tuple[str, str]] = {}
        for i, name in enumerate(SECTORS):
            c = FIRST_DATA_COL + i
            _expect(w, HEADER_LABEL_ROW, c, name)
            _expect(w, HEADER_CODE_ROW, c, f"c{i + 1}")
            cols[c] = (f"adb_c{i + 1}", name)
        for j, (code, name) in enumerate(FINAL.items()):
            c = FIRST_DATA_COL + len(SECTORS) + j
            _expect(w, HEADER_LABEL_ROW, c, name)
            _expect(w, HEADER_CODE_ROW, c, code)
            cols[c] = (f"adb_{code}", name)
        c_tot = FIRST_DATA_COL + len(SECTORS) + len(FINAL)
        _expect(w, HEADER_LABEL_ROW, c_tot, "TOTAL")
        cols[c_tot] = ("adb_TOTAL", "TOTAL")
        # rows: IND c1..c35, IMP c1..c35, then the other rows by code
        seen: list[str] = []
        pid = ctx.prov(
            raw=raw,
            table_id=f"IND IOT {sheet}",
            locator=f"sheet '{sheet}', rows {FIRST_DATA_ROW}-{FIRST_DATA_ROW + 78} (IND c1-c35, IMP c1-c35, M, r60, "
            f"r99, r61-r64, trs, r69), cols {_L(FIRST_DATA_COL)}:{_L(c_tot)} (c1-c35 {_L(FIRST_DATA_COL)}:"
            f"{_L(FIRST_DATA_COL + len(SECTORS) - 1)}, F1-F6 {_L(FIRST_DATA_COL + len(SECTORS))}:{_L(c_tot - 1)}, "
            f"TOTAL {_L(c_tot)}); rows matched by country tag and code",
            unit_as_published="US$ million ('at current prices, $ million')",
            price_basis="current",
            vintage=vintage,
            release=RELEASE,
            notes=f"Sheet '{sheet}' read as India FY {_fy(sheet)} (registry adb_mrio: year label = FY start year; "
            "inference). Old 2011-12 NAS base. International prior only. Vintage: "
            + (f"sheet stamp '{stamp}'." if stamp else "no stamp on the sheet; file-level update date (Aug 2025)."),
        )
        for r in range(FIRST_DATA_ROW, len(grid) + 1):
            label, tag, code = w.value(r, 1), w.value(r, 2), w.value(r, 3)
            if label is None and tag is None and code is None:
                if any(v is not None for v in grid[r - 1]):
                    raise ValueError(f"ADB sheet {sheet!r} row {r}: values without a label")
                continue
            label = clean_label(str(label))
            if tag in ("IND", "IMP"):
                k = int(str(code)[1:]) - 1
                if str(code) != f"c{k + 1}" or label != SECTORS[k]:
                    raise ValueError(f"ADB sheet {sheet!r} row {r}: unexpected {tag} row {code!r} {label!r}")
                origin = "domestic" if tag == "IND" else "imports"
                row_key, product = f"{'dom' if tag == 'IND' else 'imp'}_c{k + 1}", f"adb_c{k + 1}"
                item = "domestic_use" if tag == "IND" else "imported_use"
            else:
                if tag is not None or str(code) not in OTHER_ROWS or OTHER_ROWS[str(code)][1] != label:
                    raise ValueError(f"ADB sheet {sheet!r} row {r}: unexpected row {tag!r} {code!r} {label!r}")
                origin, product = None, None
                item = OTHER_ROWS[str(code)][0]
                row_key = str(code).lower()
            seen.append(row_key)
            for c, (ccode, cname) in cols.items():
                v = parse_number(w.value(r, c))
                if v is None:
                    continue
                rows.append(
                    {
                        "series_id": f"adb.{row_key}.{ccode.removeprefix('adb_').lower()}.current",
                        "source_id": SRC,
                        "table_id": f"IND IOT {sheet}",
                        "item_code": item,
                        "item_label": f"{label} | {cname}",
                        "product": product,
                        "industry": ccode,
                        "geography": "IN",
                        "dim_other": f"origin={origin}" if origin else None,
                        "stock_flow": "flow",
                        "period": _fy(sheet),
                        "period_type": "fy",
                        "value": v,
                        "unit": "USD_million",
                        "price_basis": "current",
                        "vintage": vintage,
                        "estimate_stage": "n.a.",
                        "status": "official",
                        "prov_id": pid,
                    }
                )
        want = [f"dom_c{i}" for i in range(1, 36)] + [f"imp_c{i}" for i in range(1, 36)]
        want += [k.lower() for k in OTHER_ROWS]
        if seen != want:
            raise ValueError(f"ADB sheet {sheet!r}: row order {seen} differs from the expected layout")
    wb.close()
    return Dataset(
        "io_tables_adb_ind_iot",
        pl.DataFrame(rows),
        "ADB India national IOT 35x35 (domestic + imported use), US$ million, FY 2000-01 and 2007-08 to 2024-25",
    )
