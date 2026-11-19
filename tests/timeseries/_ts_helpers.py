"""Shared helpers for the time-series tests: independent readers of clean data and of the outputs.

Nothing here imports pipeline.timeseries: the tests recompute from data/clean (polars) and compare."""

from __future__ import annotations

import datetime as dt
import json
from functools import cache
from pathlib import Path

import polars as pl
import pytest

from pipeline.core.paths import Layout

LAYOUT = Layout.default()
TS_DIR = LAYOUT.clean.parent / "timeseries"
EXCLUDED_STAGES = ("BE", "RE")


def _vintage_key(v: str) -> tuple[dt.date, str]:
    parts = [int(x) for x in v.split("-")]
    if len(parts) == 1:
        d = dt.date(parts[0], 12, 31)
    elif len(parts) == 2:
        d = dt.date(parts[0] + (parts[1] == 12), parts[1] % 12 + 1, 1) - dt.timedelta(days=1)
    else:
        d = dt.date(*parts)
    return d, v


@cache
def dataset_path(dataset: str) -> Path:
    for cat in sorted(LAYOUT.clean.glob("*/_datasets.json")):
        if dataset in json.loads(cat.read_text(encoding="utf-8")):
            return cat.parent / f"{dataset}.parquet"
    raise KeyError(dataset)


@cache
def clean(dataset: str) -> pl.DataFrame:
    return pl.read_parquet(dataset_path(dataset))


@cache
def clean_prov() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for f in sorted(LAYOUT.clean.glob("*/_provenance.parquet")):
        for r in pl.read_parquet(f, columns=["prov_id", "status", "vintage", "source_id"]).iter_rows(named=True):
            out[r["prov_id"]] = r
    return out


def series(dataset: str, series_id: str) -> dict[str, tuple[float, str, str]]:
    """{period: (value, vintage, prov_id)}: FY rows, BE/RE excluded, the latest vintage of each period."""
    df = clean(dataset).filter(
        (pl.col("series_id") == series_id)
        & (pl.col("period_type") == "fy")
        & ~pl.col("estimate_stage").is_in(list(EXCLUDED_STAGES))
    )
    assert df.height, f"{dataset}/{series_id}: no rows"
    out: dict[str, tuple[float, str, str]] = {}
    for r in df.iter_rows(named=True):
        cur = out.get(r["period"])
        if cur is None or _vintage_key(r["vintage"]) > _vintage_key(cur[1]):
            out[r["period"]] = (float(r["value"]), r["vintage"], r["prov_id"])
    return out


def series_base(dataset: str, series_id: str) -> dict[str, str | None]:
    """{period: base_year} of the clean rows `series` selects (same rules: FY, BE/RE excluded, latest vintage)."""
    df = clean(dataset).filter(
        (pl.col("series_id") == series_id)
        & (pl.col("period_type") == "fy")
        & ~pl.col("estimate_stage").is_in(list(EXCLUDED_STAGES))
    )
    pick = series(dataset, series_id)
    return {
        r["period"]: r["base_year"]
        for r in df.iter_rows(named=True)
        if r["period"] in pick and r["prov_id"] == pick[r["period"]][2] and r["vintage"] == pick[r["period"]][1]
    }


def value(dataset: str, series_id: str, period: str) -> float:
    return series(dataset, series_id)[period][0]


def output(name: str) -> pl.DataFrame:
    p = TS_DIR / name
    if not p.exists():
        pytest.fail(f"{p} does not exist: run `uv run python -m pipeline timeseries`")
    return pl.read_parquet(p)


def fy_start(p: str) -> int:
    return int(p[:4])
