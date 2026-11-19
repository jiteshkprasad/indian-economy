"""PDF text helpers for the labour_enterprise_surveys unit (private; not shared with other units).

Every table is found by its printed title, never by a fixed page number alone: `find_pages`
searches a window around the page where the title was printed in the pinned file and fails
loudly if the title moved out of the window or appears a different number of times. Rows are
then matched by their printed labels (`expect_line`, regexes on whole lines), and a label that
is missing, duplicated or unparseable raises, so a changed report never ingests shifted numbers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber
import polars as pl

from pipeline.core.units import clean_label, fy_start, parse_number, survey_period

NUM = r"-?[\d,]*\.?\d+"  # one published number: '1,23,456', '17.5', '0', '.5'


class ShapeError(ValueError):
    """The PDF does not look the way the parser expects (title moved, label missing, bad cell)."""


@dataclass
class Pdf:
    """A pinned PDF's page texts. engine 'pdfplumber' (default) or 'pypdf'; pypdf honours the
    page /Rotate entry, which the landscape tables of the ASUSE report need."""

    path: Path
    engine: str = "pdfplumber"
    _pages: dict[int, str] = field(default_factory=dict)
    _n: int | None = None

    def __post_init__(self) -> None:
        if self.engine == "pdfplumber":
            self._doc = pdfplumber.open(self.path)
        elif self.engine == "pypdf":
            import pypdf

            self._doc = pypdf.PdfReader(self.path)
        else:
            raise ValueError(f"unknown engine {self.engine!r}")
        self._n = len(self._doc.pages)

    def close(self) -> None:
        if self.engine == "pdfplumber":
            self._doc.close()

    @property
    def n_pages(self) -> int:
        assert self._n is not None
        return self._n

    def text(self, page: int) -> str:
        """Text of a 1-based page number (cached)."""
        if page not in self._pages:
            if not 1 <= page <= self.n_pages:
                raise ShapeError(f"{self.path.name}: page {page} out of range 1..{self.n_pages}")
            self._pages[page] = self._doc.pages[page - 1].extract_text() or ""  # same call in both engines
        return self._pages[page]

    def lines(self, page: int) -> list[str]:
        return [clean_label(x) for x in self.text(page).splitlines() if x.strip()]

    def find_pages(self, title: str, near: int, *, window: int = 15, count: int | None = None) -> list[int]:
        """Pages within `near` +- `window` whose text contains `title` (whitespace-insensitive).

        `count`, if given, is the exact number of pages the table must span."""
        want = _squash(title)
        lo, hi = max(1, near - window), min(self.n_pages, near + window)
        hits = [p for p in range(lo, hi + 1) if want in _squash(self.text(p))]
        if not hits:
            raise ShapeError(f"{self.path.name}: title {title!r} not found on pages {lo}-{hi}")
        if count is not None and len(hits) != count:
            raise ShapeError(f"{self.path.name}: title {title!r} on {len(hits)} pages {hits}, expected {count}")
        return hits


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


def expect_text(pdf: Pdf, page: int, needle: str) -> None:
    if _squash(needle) not in _squash(pdf.text(page)):
        raise ShapeError(f"{pdf.path.name} p.{page}: expected text {needle!r}")


def numbers(tokens: list[str], n: int, where: str) -> list[float | None]:
    """Parse exactly n number tokens; raises on a wrong count or a non-number."""
    if len(tokens) != n:
        raise ShapeError(f"{where}: expected {n} numbers, got {len(tokens)}: {tokens}")
    out = []
    for t in tokens:
        try:
            out.append(parse_number(t))
        except ValueError as e:
            raise ShapeError(f"{where}: {e}") from None
    return out


def split_label_numbers(line: str, n: int, *, strict: bool = True) -> tuple[str, list[str]] | None:
    """'Andhra Pradesh 1 2 3' -> ('Andhra Pradesh', ['1','2','3']) if the line ends in exactly n numbers.

    strict: also refuse a line whose label ends in a number (more than n numbers on the line);
    pass False for labels that end in a year ('April- June 2024 18200 ...')."""
    toks = line.split(" ")
    if len(toks) < n:
        return None
    tail = toks[-n:]
    if not all(re.fullmatch(NUM, t) for t in tail):
        return None
    head = " ".join(toks[:-n]).strip()
    if strict and head and re.fullmatch(NUM, head.split(" ")[-1]):
        return None  # more than n numbers on the line
    return head, tail


ROW_COLUMNS = (
    "series_id",
    "source_id",
    "table_id",
    "item_code",
    "item_label",
    "institution",
    "industry",
    "product",
    "instrument",
    "counterparty",
    "geography",
    "household_group",
    "side",
    "dim_other",
    "stock_flow",
    "period",
    "period_type",
    "value",
    "unit",
    "price_basis",
    "base_year",
    "vintage",
    "estimate_stage",
    "status",
    "prov_id",
)


# Survey windows (PIPELINE_GUIDE s.5.2, period type `sy`). The parsers read a survey's own year
# label ('2023-24') and tag the row with the internal marker survey_year=<window> in dim_other;
# `frame()` turns every tagged row into an `sy` period ('2023-07/2024-06') and removes the marker,
# so no output row carries it. Window = (first month, number of months), starting in the first
# year of the label.
SURVEY_WINDOWS: dict[str, tuple[int, int]] = {
    "jul_jun": (7, 12),  # PLFS and SAS agricultural years; AIDIS capital-expenditure year
    "oct_sep": (10, 12),  # ASUSE 2022-23 and 2023-24
}


def survey_row(row: dict) -> dict:
    """A row tagged survey_year=<window> (with an `fy`-style label) -> the same row with an `sy`
    period and the marker removed. Untagged rows are returned unchanged."""
    dims = dict(kv.split("=", 1) for kv in (row.get("dim_other") or "").split(";") if kv)
    window = dims.pop("survey_year", None)
    if window is None:
        return row
    if row.get("period_type") != "fy" or window not in SURVEY_WINDOWS:
        raise ShapeError(f"survey_year={window} on a {row.get('period_type')} row: {row.get('series_id')}")
    month, months = SURVEY_WINDOWS[window]
    out = dict(row)
    out["period"] = survey_period(fy_start(row["period"]), month, months)
    out["period_type"] = "sy"
    out["dim_other"] = ";".join(f"{k}={dims[k]}" for k in sorted(dims)) or None
    return out


def frame(rows: list[dict]) -> pl.DataFrame:
    """Rows -> a DataFrame with an explicit schema (every column String except value Float64).
    Survey-year rows are converted to `sy` periods first (see `survey_row`)."""
    if not rows:
        raise ShapeError("no rows parsed")
    schema = {c: (pl.Float64 if c == "value" else pl.String) for c in ROW_COLUMNS}
    rows = [survey_row(r) for r in rows]
    return pl.DataFrame([{c: r.get(c) for c in ROW_COLUMNS} for r in rows], schema=schema, orient="row")
