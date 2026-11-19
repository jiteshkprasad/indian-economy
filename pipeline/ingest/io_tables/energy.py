"""MoSPI Energy Statistics India 2026, Chapter 9 (Energy Accounts): physical supply and use tables
for energy (PSUT, SEEA-Energy), in petajoules.

- Table 9.2 (A)/(B): physical supply / use table, 2023-24;
- Table 9.3 (A)/(B): the same for 2024-25 (P).
Rows: natural inputs, energy products (production; transformation; end use) and energy residuals by
SIEC class; columns: ISIC industry groups (A agriculture, B mining, C manufacturing, D electricity,
transport & storage, construction (use only), other industries), households, accumulation, flows
from/to the rest of the world, the environment, statistical difference, total. Gap map S6.

Dataset `io_tables_energy_psut` (324 rows, unit `PJ`, price basis n/a, status official, vintage
2026-03-30; 2023-24 as printed, 2024-25 estimate stage Provisional). Values are kept as printed (no
unit conversion). Gap map S6 is served from the 2023-24 use table (declared `partial` in
io_tables_coverage.yaml: seven ISIC industry groups, not the 34 SAM activities).

Dimensions. `series_id` = `psut.<supply|use>.<section>.<row>.<column>`, where <column> is one of
SUPPLY_COLS / USE_COLS. Every row carries `dim_other` `psut_column=<column>`, so one printed column is
one filter whatever its kind. In addition:
- the seven industry columns (`isic_a`, `isic_b`, `isic_c`, `isic_d`, `transport_storage`,
  `construction`, `other_industries`) set `industry` to that code (printed headers: Agriculture,
  Forestry & Fishery (ISIC A); Mining & Quarrying (ISIC B); Manufacturing (ISIC C); Electricity, gas,
  steam & air conditioning supply (ISIC D); Transportation & Storage; Construction; Other Industries).
  The PDF prints '(ISIC M)' under Transportation & Storage (ISIC Rev.4 H); the code follows the
  column name, not that letter (issue io_tables-17);
- `households` sets `institution=households`;
- imports / exports set `counterparty=rest_of_world`; flows from / to the environment set
  `counterparty=environment`;
- `accumulation`, `statistical_difference` and `total` have only `psut_column`;
- rows in the energy-products and natural-inputs sections set `product` to the SIEC class slug
  (`coal`, `lignite`, `crude_oil`, `oil_products`, `natural_gas`, `electricity`, `nuclear`,
  `inputs_from_res`, `hydro`; SIEC_PRODUCTS); other rows (residuals, 'End-use of energy products for
  non-energy purposes', the grand totals) have no product.
Cells printed blank have no row; a printed 0 is a row with value 0.

Precision: the writer rounds to 6 decimals, so the one printed value with more (Table 9.3 (B), coal,
ISIC A: 0.16179072) is stored as 0.161791 (issue io_tables-17).

Parsing (pdfplumber words with x positions; the PDF has no usable table grid):
- the column anchors are the right edges of the numbers in the table's TOTAL SUPPLY / TOTAL USE row,
  mapped in order to the expected columns (the supply 'Accumulation' column is empty in both years
  and must stay empty: a number between the households and imports anchors is an error);
- every number is assigned to the anchor whose right edge is within 7 pt, else the build fails;
- section sub-total rows ('Total', 'Total Transformed Energy', 'Total End Use for Energy purposes',
  'Total energy residuals') are not ingested: they are sums, one of them is printed centred rather
  than right-aligned, and another has its first number overprinted on the label ('purpo1s1e8s3');
- every detail row must add up to its printed Total column, and in every column the detail rows must
  add up to the printed TOTAL SUPPLY / TOTAL USE row (both within 2 PJ of rounding), or the build fails.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pdfplumber
import polars as pl

from pipeline.core.unit import BuildContext, Dataset
from pipeline.core.units import clean_label, parse_number, slug

SRC = "mospi_energy_statistics"
FILE = "es2026_chapter_9.pdf"
VINTAGE = "2026-03-30"
RELEASE = "Energy Statistics India 2026, Chapter 9 Energy Accounts (NSO, MoSPI; released 30 Mar 2026)"
UNIT_PJ = "PJ"  # pipeline/core/units.UNITS (added for framework request io_tables FR-1)

SUPPLY_COLS = ["isic_a", "isic_b", "isic_c", "isic_d", "transport_storage", "other_industries", "households",
               "rest_of_world_imports", "environment", "total"]
USE_COLS = ["isic_a", "isic_b", "isic_c", "isic_d", "transport_storage", "construction", "other_industries",
            "households", "accumulation", "exports", "statistical_difference", "flows_to_environment", "total"]
INDUSTRY_COLS = ("isic_a", "isic_b", "isic_c", "isic_d", "transport_storage", "construction", "other_industries")
COUNTERPARTY = {
    "rest_of_world_imports": "rest_of_world",
    "exports": "rest_of_world",
    "environment": "environment",
    "flows_to_environment": "environment",
}
PRODUCT_SECTIONS = ("natural_inputs.", "energy_products.")
# SIEC classes / natural-input types printed as row labels in those sections (slugs). Any other row
# there (e.g. 'End-use of energy products for non-energy purposes') gets no product.
SIEC_PRODUCTS = ("coal", "lignite", "crude_oil", "oil_products", "natural_gas", "electricity", "nuclear",
                 "inputs_from_res", "hydro")


def column_dims(column: str) -> dict[str, str]:
    """Dimension columns for one printed PSUT column (module docstring, 'Dimensions')."""
    if column not in SUPPLY_COLS and column not in USE_COLS:
        raise ValueError(f"unknown PSUT column {column!r}")
    dims = {"dim_other": f"psut_column={column}"}
    if column in INDUSTRY_COLS:
        dims["industry"] = column
    elif column == "households":
        dims["institution"] = "households"
    elif column in COUNTERPARTY:
        dims["counterparty"] = COUNTERPARTY[column]
    return dims


@dataclass(frozen=True)
class Table:
    table_id: str
    page: int  # 1-based PDF page
    period: str
    stage: str
    kind: str  # supply | use
    caption: str


TABLES = [
    Table("Table 9.2 (A)", 12, "2023-24", "n.a.", "supply",
          "Table 9.2 (A) Physical Supply Table for Energy for the year 2023-24"),
    Table("Table 9.2 (B)", 13, "2023-24", "n.a.", "use",
          "Table 9.2 (B) Physical Use Table for Energy for the year 2023-24"),
    Table("Table 9.3 (A)", 14, "2024-25", "Provisional", "supply",
          "Table 9.3 (A) Physical Supply Table for Energy for the year 2024-25 (P)"),
    Table("Table 9.3 (B)", 15, "2024-25", "Provisional", "use",
          "Table 9.3 (B) Physical Use Table for Energy for the year 2024-25 (P)"),
]
SECTIONS = {
    "Energy from natural inputs:": "natural_inputs",
    "Energy Products:": "energy_products",
    "Energy Residuals:": "residuals",
    "Other Residual Flows:": "other_residual_flows",
}
SUBSECTIONS = {
    "Natural resource inputs": "natural_resource_inputs",
    "Production of energy products by SIEC class:": "production",
    "Transformaton of energy products by SIEC class": "transformation",
    "End-use of energy products by SIEC class:": "end_use",
}
NUM = re.compile(r"^-?\d+(\.\d+)?$")
TOL_X = 7.0
TOL_ROW = 2.0


@dataclass
class Cell:
    table: Table
    section: str
    label: str
    column: str
    value: float
    top: float


def _lines(page: Any) -> list[list[dict[str, Any]]]:
    words = sorted(page.extract_words(), key=lambda w: (round(w["top"]), w["x0"]))
    lines: list[list[dict[str, Any]]] = []
    for w in words:
        if lines and abs(lines[-1][0]["top"] - w["top"]) < 3:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(ln, key=lambda w: w["x0"]) for ln in lines]


def _split(line: list[dict[str, Any]]) -> tuple[str, list[tuple[float, float]]]:
    """(label, [(x1, value)]) for one printed line."""
    label_parts: list[str] = []
    nums: list[tuple[float, float]] = []
    for w in line:
        t = w["text"]
        if NUM.match(t):
            v = parse_number(t)
            assert v is not None
            nums.append((w["x1"], v))
        else:
            label_parts.append(t)
    return " ".join(label_parts), nums


def parse_table(pdf: Any, tab: Table) -> list[Cell]:
    page = pdf.pages[tab.page - 1]
    text = page.extract_text() or ""
    if tab.caption not in text or "(Unit:PJ)" not in text:
        raise ValueError(f"{tab.table_id}: caption or '(Unit:PJ)' not found on PDF page {tab.page}")
    lines = _lines(page)
    total_label = "TOTAL SUPPLY" if tab.kind == "supply" else "TOTAL USE"
    cols = SUPPLY_COLS if tab.kind == "supply" else USE_COLS
    tl = [ln for ln in lines if _split(ln)[0].startswith(total_label)]
    if len(tl) != 1:
        raise ValueError(f"{tab.table_id}: expected one '{total_label}' row, found {len(tl)}")
    anchors = [x for x, _ in _split(tl[0])[1]]
    if len(anchors) != len(cols):
        raise ValueError(f"{tab.table_id}: {len(anchors)} numbers in {total_label}, expected {len(cols)}")
    if tab.kind == "supply":  # the empty 'Accumulation' header must sit between households and imports
        acc = [w for ln in lines for w in ln if w["text"].startswith("Accumulati")]
        if len(acc) != 1 or not anchors[6] < acc[0]["x1"] < anchors[7]:
            raise ValueError(f"{tab.table_id}: 'Accumulation' column not where expected")
    cells: list[Cell] = []
    section = sub = ""
    started = False
    for ln in lines:
        label, nums = _split(ln)
        if label in SECTIONS:
            section, sub, started = SECTIONS[label], "", True
            continue
        if not started:
            continue
        if label in SUBSECTIONS:
            sub = SUBSECTIONS[label]
            continue
        if label.endswith("| Page") or re.match(r"^\| Page", label) or not label:
            continue
        if label == "Total" or label.startswith("Total "):  # section sub-totals: sums, not ingested (docstring)
            continue
        key = ".".join(x for x in (section, sub) if x)
        row_vals: dict[str, float] = {}
        for x1, v in nums:
            j = min(range(len(anchors)), key=lambda k: abs(anchors[k] - x1))
            if abs(anchors[j] - x1) > TOL_X:
                raise ValueError(f"{tab.table_id} row {label!r}: number {v} at x1={x1:.0f} matches no column")
            if cols[j] in row_vals:
                raise ValueError(f"{tab.table_id} row {label!r}: two numbers in column {cols[j]}")
            row_vals[cols[j]] = v
        if row_vals:
            parts = sum(v for c, v in row_vals.items() if c != "total")
            if "total" not in row_vals:
                raise ValueError(f"{tab.table_id} row {label!r}: no Total column value")
            if len(row_vals) > 1 and abs(parts - row_vals["total"]) > TOL_ROW:
                raise ValueError(f"{tab.table_id} row {label!r}: parts {parts} != total {row_vals['total']}")
        for c, v in row_vals.items():
            cells.append(Cell(tab, key if label != total_label else "total", label, c, v, ln[0]["top"]))
    grand = {c.column: c.value for c in cells if c.label == total_label}
    if not grand:
        raise ValueError(f"{tab.table_id}: parse lost the total row")
    for col in cols:
        s = sum(c.value for c in cells if c.column == col and c.label != total_label)
        if abs(s - grand.get(col, 0.0)) > TOL_ROW:
            raise ValueError(f"{tab.table_id} column {col}: detail rows sum to {s}, printed total {grand.get(col)}")
    return cells


def parse_all(path: str) -> list[Cell]:
    with pdfplumber.open(path) as pdf:
        return [c for tab in TABLES for c in parse_table(pdf, tab)]


def build_energy(ctx: BuildContext) -> list[Dataset]:
    raw = ctx.raw(SRC, FILE)
    cells = parse_all(str(raw.path))
    rows: list[dict[str, Any]] = []
    prov: dict[str, str] = {}
    for tab in TABLES:
        prov[tab.table_id] = ctx.prov(
            raw=raw,
            table_id=tab.table_id,
            locator=f"Chapter 9 PDF page {tab.page}: '{tab.caption}' (Unit: PJ); rows by label within section, "
            "columns by position under the header",
            unit_as_published="PJ",
            price_basis="n/a",
            vintage=VINTAGE,
            release=RELEASE,
        )
    for c in cells:
        label = clean_label(c.label)
        item = slug(label)
        dims = column_dims(c.column)
        if c.section.startswith(PRODUCT_SECTIONS) and item in SIEC_PRODUCTS:
            dims["product"] = item
        rows.append(
            {
                "series_id": f"psut.{c.table.kind}.{c.section}.{item}.{c.column}",
                "source_id": SRC,
                "table_id": c.table.table_id,
                "item_code": f"{c.section}.{item}",
                "item_label": label,
                "institution": dims.get("institution"),
                "industry": dims.get("industry"),
                "product": dims.get("product"),
                "counterparty": dims.get("counterparty"),
                "geography": "IN",
                "side": "resources" if c.table.kind == "supply" else "uses",
                "dim_other": dims["dim_other"],
                "stock_flow": "flow",
                "period": c.table.period,
                "period_type": "fy",
                "value": c.value,
                "unit": UNIT_PJ,
                "price_basis": "n/a",
                "vintage": VINTAGE,
                "estimate_stage": c.table.stage,
                "status": "official",
                "prov_id": prov[c.table.table_id],
            }
        )
    schema = {k: pl.Utf8 for k in rows[0] if k != "value"} | {"value": pl.Float64}
    df = pl.DataFrame(rows, schema=schema)
    return [
        Dataset(
            "io_tables_energy_psut",
            df,
            "Energy Statistics 2026 Ch. 9 physical supply and use tables for energy, 2023-24 and 2024-25 (P), PJ",
        )
    ]
