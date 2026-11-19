"""SUT methodological note (NAD, MoSPI, revised 31 Aug 2026), Tables 9.1 and 9.2: GVA/GDP by the
production, expenditure and income approaches from SUT 2022-23 and 2023-24.

These are MoSPI's own published totals of the two SUTs. They are ingested as a small official
dataset (io_tables_sut_note_totals) so the unit tests can check the 155 x 67 cells against a total
printed in a different document, and so Phase 2 has the SUT control totals with provenance.

Parsing: pdfplumber tables on PDF pages 20-22. The rows of a table sometimes come out with a value
one row above its label (page 22), so labels and values are collected separately in reading order
and zipped; the label sequence must equal the expected sequence exactly, or the build fails.
"""

from __future__ import annotations

from typing import Any

import pdfplumber
import polars as pl

from pipeline.core.unit import BuildContext, Dataset
from pipeline.core.units import clean_label, parse_number

from .sut import BASE_YEAR, RELEASE, SRC, VINTAGE

NOTE = "sut_note_2022_23_2023_24.pdf"
NOTE_SHA = "054e062c"  # Phase 0 verifier's hash of the 31-Aug-2026 note

# (item_code, accepted labels) in the order the tables print them (production, expenditure, income)
SEQUENCE: list[tuple[str, tuple[str, ...]]] = [
    ("output", ("Output",)),
    ("ic", ("Intermediate Consumption",)),
    ("gva", ("Gross Value Added (GVA)",)),
    ("product_taxes_less_subsidies", ("Product Taxes less Subsidies",)),
    ("gdp", ("Gross Domestic Product (GDP)",)),
    ("pfce", ("PFCE",)),
    ("gfce", ("GFCE",)),
    ("gfcf", ("GFCF",)),
    ("cis", ("Change in Inventories (CII)", "Change in Stocks (CIS)")),
    ("valuables", ("Valuables",)),
    ("exports", ("Export",)),
    ("imports", ("Import",)),
    ("gdp_expenditure", ("Gross Domestic Product (GDP)",)),
    ("production_taxes_less_subsidies", ("Production Taxes less Subsidies",)),
    ("cfc", ("Consumption of Fixed Capital (CFC)",)),
    ("ce", ("Compensation to Employee (CE)",)),
    ("os_mi", ("Operating Surplus/Mixed Income (OS/MI)",)),
    ("gva_income", ("Gross Value Added (GVA)",)),
]
APPROACH = {**{k: "production" for k, _ in SEQUENCE[:5]}, **{k: "expenditure" for k, _ in SEQUENCE[5:13]}}
APPROACH |= {k: "income" for k, _ in SEQUENCE[13:]}
# PDF pages (1-based) -> the tables they hold, in order: (table id, period, part)
PAGES = {20: ["Table 9.1"], 21: ["Table 9.1", "Table 9.2"], 22: ["Table 9.2"]}
PERIODS = {"Table 9.1": "2022-23", "Table 9.2": "2023-24"}
PRINTED_PAGE_OFFSET = 6  # PDF page 20 carries the printed page number 14 (checked in the page header)
SKIP = {"", "Approach", "Item", "Value (Rs. Crore)", "Production", "Expenditure", "Income"}


def _cells(table: list[list[Any]]) -> tuple[list[str], list[float]]:
    labels: list[str] = []
    values: list[float] = []
    for row in table:
        for cell in row:
            if cell is None:
                continue
            text = clean_label(str(cell))
            if text in SKIP:
                continue
            if any(ch.isdigit() for ch in text) and not any(ch.isalpha() for ch in text):
                v = parse_number(text)
                if v is None:
                    raise ValueError(f"unparseable number {text!r} in the SUT note tables")
                values.append(v)
            else:
                labels.append(text)
    return labels, values


def build_note_totals(ctx: BuildContext) -> Dataset:
    raw = ctx.raw(SRC, NOTE)
    if not raw.sha256.startswith(NOTE_SHA):
        raise ValueError(f"{NOTE}: sha256 {raw.sha256[:12]} is not the 31-Aug-2026 note ({NOTE_SHA}...): revision")
    collected: dict[str, tuple[list[str], list[float]]] = {t: ([], []) for t in PERIODS}
    with pdfplumber.open(raw.path) as pdf:
        text20 = pdf.pages[19].extract_text() or ""
        text21 = pdf.pages[20].extract_text() or ""
        for page in PAGES:  # the printed page number ('...Government of India 14'), so the locator stays right
            lines = (pdf.pages[page - 1].extract_text() or "").splitlines()
            if not any(h.strip().endswith(f"Government of India {page - PRINTED_PAGE_OFFSET}") for h in lines):
                raise ValueError(f"SUT note PDF page {page}: printed page {page - PRINTED_PAGE_OFFSET} not found")
        if "Table 9.1: GVA/GDP by Production, Expenditure and Income Approach from SUT 2022" not in text20:
            raise ValueError("SUT note page 20: Table 9.1 caption not found (layout changed?)")
        if "Table 9.2: GVA/GDP by Production, Expenditure and Income Approach from SUT 2023" not in text21:
            raise ValueError("SUT note page 21: Table 9.2 caption not found (layout changed?)")
        for page, tables in PAGES.items():
            found = pdf.pages[page - 1].extract_tables()
            if len(found) != len(tables):
                raise ValueError(f"SUT note page {page}: {len(found)} tables, expected {len(tables)}")
            for tid, tab in zip(tables, found, strict=True):
                labs, vals = _cells(tab)
                collected[tid][0].extend(labs)
                collected[tid][1].extend(vals)
    rows: list[dict[str, Any]] = []
    for tid, (labels, values) in collected.items():
        if len(labels) != len(SEQUENCE) or len(values) != len(SEQUENCE):
            raise ValueError(f"SUT note {tid}: {len(labels)} labels / {len(values)} values, expected {len(SEQUENCE)}")
        for (code, accepted), label in zip(SEQUENCE, labels, strict=True):
            if label not in accepted:
                raise ValueError(f"SUT note {tid}: expected one of {accepted} for {code}, found {label!r}")
        period = PERIODS[tid]
        pdf_pages = [p for p, t in PAGES.items() if tid in t]
        printed = [p - PRINTED_PAGE_OFFSET for p in pdf_pages]
        pid = ctx.prov(
            raw=raw,
            table_id=tid,
            locator=f"SUT note PDF, {tid} (pages {'-'.join(str(p) for p in (pdf_pages[0], pdf_pages[-1]))} of the "
            f"PDF; printed pages {printed[0]}-{printed[-1]}): 'GVA/GDP by Production, Expenditure and Income "
            f"Approach from SUT {period}', column 'Value (Rs. Crore)'",
            unit_as_published="Rs crore ('Value (Rs. Crore)')",
            price_basis="current",
            base_year=BASE_YEAR,
            vintage=VINTAGE,
            release=RELEASE,
        )
        for (code, _), label, v in zip(SEQUENCE, labels, values, strict=True):
            rows.append(
                {
                    "series_id": f"note.{code}.current",
                    "source_id": SRC,
                    "table_id": tid,
                    "item_code": code,
                    "item_label": label,
                    "geography": "IN",
                    "dim_other": f"approach={APPROACH[code]}",
                    "stock_flow": "flow",
                    "period": period,
                    "period_type": "fy",
                    "value": v,
                    "unit": "INR_crore",
                    "price_basis": "current",
                    "base_year": BASE_YEAR,
                    "vintage": VINTAGE,
                    "estimate_stage": "Final",
                    "status": "official",
                    "prov_id": pid,
                }
            )
    return Dataset(
        "io_tables_sut_note_totals",
        pl.DataFrame(rows),
        "SUT note Tables 9.1/9.2: GVA/GDP by production, expenditure and income approach, 2022-23 and 2023-24",
    )
