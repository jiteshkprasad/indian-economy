"""Shared constants and helpers for the hces_consumption unit (not a unit module itself)."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

import openpyxl

from pipeline.core import geo
from pipeline.core.units import clean_label, survey_period

UNIT = "hces_consumption"

# ---------------------------------------------------------------------------------------------
# HCES rounds
# ---------------------------------------------------------------------------------------------

SURVEY_NOTE = (
    "Survey reference period {survey} ({round_name}), NOT fiscal year {period}: rows carry period '{sy}' with "
    "period_type 'sy' (survey window, first/last month). Values are monthly (30-day) per-person averages over the "
    "survey year at current prices of the survey period. Use them for shares and distributions applied to FY "
    "totals, not as FY levels (HCES aggregate is about 44% of NAS PFCE)."
)

ROUNDS: dict[str, dict[str, Any]] = {
    "2023-24": {
        "src": "mospi_hces_2023_24",
        "base": "https://mospi.gov.in/sites/default/files/publication_reports/HCES-23-24/",
        "files": {
            "a2": ("TableA2.xlsx", "hces2324_table_a2.xlsx"),
            "a6": ("TableA6.xlsx", "hces2324_table_a6.xlsx"),
            "a10f": ("TableA10F-Fractile-class-All%20India.xlsx", "hces2324_table_a10f.xlsx"),
            "a10s": ("TableA10S-State.xlsx", "hces2324_table_a10s.xlsx"),
            "a10sw": ("TableA10SW-State-WithImputation.xlsx", "hces2324_table_a10sw.xlsx"),
        },
        "vintage": "2025-01-30",
        "release": "HCES 2023-24 (NSS Report No. 592) detailed report and Appendix-A Excel tables (NSO, MoSPI, 30 Jan 2025)",
        "survey": "August 2023 - July 2024",
        "round_name": "HCES 2023-24",
        "sy": survey_period(2023, 8),  # '2023-08/2024-07' (Report 592 p.3: 'August, 2023 - July, 2024')
    },
    "2022-23": {
        "src": "mospi_hces_2022_23",
        "base": "https://www.mospi.gov.in/sites/default/files/publication_reports/HCES-22-23N/",
        "files": {
            "a2": ("Table%20A2.xlsx", "hces2223_table_a2.xlsx"),
            "a6": ("Table%20A6.xlsx", "hces2223_table_a6.xlsx"),
            "a10f": ("Table%20A10F-Fractile%20class-All%20India.xlsx", "hces2223_table_a10f.xlsx"),
            "a10s": ("Table%20A10S-State.xlsx", "hces2223_table_a10s.xlsx"),
        },
        # The Excel files carry Last-Modified 7 Jun 2024; Report 591 was released in June 2024.
        "vintage": "2024-06",
        "release": "HCES 2022-23 (NSS Report No. 591) Appendix-A Excel tables (NSO, MoSPI, June 2024)",
        "survey": "August 2022 - July 2023",
        "round_name": "HCES 2022-23",
        "sy": survey_period(2022, 8),  # '2022-08/2023-07' (Report 592 p.20: 'August, 2022 to July, 2023')
    },
}


def survey_note(period: str) -> str:
    """Provenance note for an HCES round; `period` is the round key ('2023-24', '2022-23')."""
    r = ROUNDS[period]
    return SURVEY_NOTE.format(survey=r["survey"], round_name=r["round_name"], period=period, sy=r["sy"])


def sy_period(period: str) -> str:
    """The clean `period` label (period_type 'sy') of an HCES round key: '2023-24' -> '2023-08/2024-07'."""
    return ROUNDS[period]["sy"]


# ---------------------------------------------------------------------------------------------
# Classifications
# ---------------------------------------------------------------------------------------------

SECTORS = {"rural": "rural", "urban": "urban"}

FRACTILES: dict[str, str] = {
    "0-5%": "p00_05",
    "5-10%": "p05_10",
    "10-20%": "p10_20",
    "20-30%": "p20_30",
    "30-40%": "p30_40",
    "40-50%": "p40_50",
    "50-60%": "p50_60",
    "60-70%": "p60_70",
    "70-80%": "p70_80",
    "80-90%": "p80_90",
    "90-95%": "p90_95",
    "95-100%": "p95_100",
    "all classes": "all",
}
FRACTILE_ORDER = list(FRACTILES.values())

# State/UT codes come from the project-wide code set (pipeline/core/geo.py, DECISIONS D1-9). The only
# local knowledge is the All-India row and the printed variants that geo.state_code() does not know;
# they map to a canonical name, never to a code, so every code is still geo's.
ALL_INDIA = {"all india"}
NAME_VARIANTS: dict[str, str] = {
    "andaman and n island": "Andaman and Nicobar Islands",  # HCES A6/A10S
    "a and n island": "Andaman and Nicobar Islands",  # HCES A2
}


def norm_name(text: Any) -> str:
    s = clean_label(str(text)).lower().replace("&", " and ")
    s = re.sub(r"[^a-z ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^the ", "", s)
    return s


def state_geo(name: Any) -> str:
    """'IN' for the All-India row, else the State/UT code from pipeline/core/geo.py (raises if unknown)."""
    key = norm_name(name)
    if key in ALL_INDIA:
        return "IN"
    try:
        return geo.state_code(NAME_VARIANTS.get(key, str(name)))
    except KeyError as e:
        raise ValueError(f"unmapped State/UT name {name!r} (normalised {key!r})") from e


def geo_slug(geo: str) -> str:
    return geo.lower()


def fractile_code(label: Any) -> str:
    key = clean_label(str(label)).lower()
    if key not in FRACTILES:
        raise ValueError(f"unknown fractile class label {label!r}")
    return FRACTILES[key]


def sector_code(label: Any) -> str:
    key = clean_label(str(label)).lower()
    if key not in SECTORS:
        raise ValueError(f"unknown sector label {label!r}")
    return SECTORS[key]


# ---------------------------------------------------------------------------------------------
# Sheet helpers
# ---------------------------------------------------------------------------------------------


def sheet_rows(path: Any, sheet: str | None = None) -> tuple[str, list[tuple[Any, ...]]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[sheet] if sheet else wb.worksheets[0]
        return ws.title, [tuple(r) for r in ws.iter_rows(values_only=True)]
    finally:
        wb.close()


def expect_text(rows: Sequence[tuple[Any, ...]], r: int, c: int, needle: str, where: str) -> None:
    """Assert that cell (row r, col c; 1-based) contains `needle` (case-insensitive)."""
    row = rows[r - 1] if r - 1 < len(rows) else ()
    got = clean_label(str(row[c - 1])) if c - 1 < len(row) and row[c - 1] is not None else ""
    if needle.lower() not in got.lower():
        raise ValueError(f"{where}: cell r{r}c{c} expected text containing {needle!r}, found {got!r}")


def first_row_with(rows: Sequence[tuple[Any, ...]], col: int, text: str) -> int:
    """1-based index of the first row whose column `col` (1-based) equals `text` after clean_label."""
    for i, r in enumerate(rows, start=1):
        if len(r) >= col and r[col - 1] is not None and clean_label(str(r[col - 1])) == text:
            return i
    raise ValueError(f"no row with {text!r} in column {col}")


def col_letter(c: int) -> str:
    return openpyxl.utils.get_column_letter(c)
