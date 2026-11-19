"""Shared helpers for the finsector_markets unit (rows, provenance blocks, sheet reading)."""

from __future__ import annotations

import calendar
import io
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import openpyxl

from pipeline.core.unit import BuildContext, RawFile
from pipeline.core.units import clean_label, fy_start, normalize_fy, parse_number

MONEY_UNITS = ("INR_crore", "USD_million")


def fy_end(fy_label: str) -> str:
    """'2023-24' -> '2024-03-31' (the date of an end-of-year stock)."""
    return f"{fy_start(fy_label) + 1}-03-31"


def month_end(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}-{calendar.monthrange(year, month)[1]:02d}"


def fy_label(text: Any) -> str:
    """A fiscal-year header cell ('2023-24', '2020-21.', '2025-26$', '2019-20 ') -> '2023-24'."""
    return normalize_fy(str(text))


def expect(ws: Any, cell: str, needle: str) -> None:
    got = clean_label(ws[cell].value or "")
    if needle.lower() not in got.lower():
        raise ValueError(f"sheet {ws.title!r} {cell}: expected text containing {needle!r}, found {got!r}")


def cell_text(ws: Any, row: int, col: int) -> str:
    v = ws.cell(row, col).value
    return "" if v is None else clean_label(v)


def load_xlsx(raw: RawFile) -> openpyxl.Workbook:
    return openpyxl.load_workbook(raw.path, data_only=True)


def load_zip_member(raw: RawFile, suffix: str) -> tuple[openpyxl.Workbook, str]:
    """Open the one workbook in a zip whose name ends with `suffix`; returns (workbook, member name)."""
    with zipfile.ZipFile(raw.path) as z:
        names = [n for n in z.namelist() if n.endswith(suffix)]
        if len(names) != 1:
            raise ValueError(f"{raw.name}: expected exactly one member ending {suffix!r}, found {names}")
        data = z.read(names[0])
    return openpyxl.load_workbook(io.BytesIO(data), data_only=True), names[0]


def num(cell: Any) -> float | None:
    """parse_number, but also None for the publisher's 'NA'/'-' markers inside text cells."""
    return parse_number(cell)


@dataclass
class Rows:
    """Collects clean rows for one dataset. Every row names its provenance block explicitly."""

    ctx: BuildContext
    source_id: str
    vintage: str
    estimate_stage: str = "n.a."
    rows: list[dict[str, Any]] = field(default_factory=list)

    def prov(
        self,
        raw: RawFile,
        *,
        table_id: str,
        locator: str,
        unit_as_published: str,
        release: str,
        money: bool,
        conversion: str = "none",
        notes: str | None = None,
    ) -> str:
        return self.ctx.prov(
            raw=raw,
            table_id=table_id,
            locator=locator,
            unit_as_published=unit_as_published,
            conversion=conversion,
            price_basis="current" if money else "n/a",
            vintage=self.vintage,
            release=release,
            notes=notes,
        )

    def add(
        self,
        *,
        prov_id: str,
        series_id: str,
        table_id: str,
        item_code: str,
        item_label: str,
        value: float,
        unit: str,
        stock_flow: str,
        period: str,
        period_type: str,
        estimate_stage: str | None = None,
        status: str = "official",
        **dims: str | None,
    ) -> None:
        row: dict[str, Any] = {
            "series_id": series_id,
            "source_id": self.source_id,
            "table_id": table_id,
            "item_code": item_code,
            "item_label": clean_label(item_label),
            "geography": "IN",
            "stock_flow": stock_flow,
            "period": period,
            "period_type": period_type,
            "value": float(value),
            "unit": unit,
            "price_basis": "current" if unit in MONEY_UNITS else "n/a",
            "vintage": self.vintage,
            "estimate_stage": estimate_stage or self.estimate_stage,
            "status": status,
            "prov_id": prov_id,
        }
        for k, v in dims.items():
            if v is not None:
                row[k] = v
        self.rows.append(row)


def frame(rows: Iterable[dict[str, Any]]):  # -> pl.DataFrame
    """Rows (with possibly different optional dims) -> one DataFrame with all dims as columns."""
    import polars as pl

    rows = list(rows)
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    schema = {c: (pl.Float64 if c == "value" else pl.String) for c in cols}
    return pl.DataFrame([{c: r.get(c) for c in cols} for r in rows], schema=schema, orient="row")
