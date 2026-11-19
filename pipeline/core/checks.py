"""Reusable data-quality checks for unit tests (ranges, identities, continuity, revisions).

Each `check_*` returns a DataFrame of violations (empty = pass). Tests wrap it in `assert_no_rows`,
which prints the offending rows. All functions take a clean long table (the clean schema) and
identify series by `series_id`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

import polars as pl

from pipeline.core.paths import Layout
from pipeline.core.units import period_order_key


def load_dataset(unit: str, dataset: str, layout: Layout | None = None) -> pl.DataFrame:
    """Read data/clean/<unit>/<dataset>.parquet (fails loudly if the unit was not built)."""
    layout = layout or Layout.default()
    p = layout.clean / unit / f"{dataset}.parquet"
    if not p.exists():
        raise FileNotFoundError(f"{p} not found: run `uv run python -m pipeline build {unit}`")
    return pl.read_parquet(p)


def load_provenance(unit: str, layout: Layout | None = None) -> pl.DataFrame:
    layout = layout or Layout.default()
    return pl.read_parquet(layout.clean / unit / "_provenance.parquet")


def value(df: pl.DataFrame, series_id: str, period: str, vintage: str | None = None) -> float:
    """The single value of one series in one period (and vintage, if the table holds several)."""
    q = df.filter((pl.col("series_id") == series_id) & (pl.col("period") == period))
    if vintage is not None:
        q = q.filter(pl.col("vintage") == vintage)
    if q.height != 1:
        raise LookupError(f"expected 1 row for {series_id} {period} {vintage or ''}, found {q.height}")
    return float(q["value"][0])


def assert_no_rows(violations: pl.DataFrame, what: str) -> None:
    """Fail with a readable table if `violations` has rows."""
    if violations.height:
        with pl.Config(tbl_rows=40, tbl_cols=12, fmt_str_lengths=60, tbl_width_chars=200):
            raise AssertionError(f"{what}: {violations.height} violation(s)\n{violations.head(40)}")


def _filter(df: pl.DataFrame, series_ids: Iterable[str] | None) -> pl.DataFrame:
    if series_ids is None:
        return df
    ids = list(series_ids)
    missing = sorted(set(ids) - set(df["series_id"].unique().to_list()))
    if missing:
        raise LookupError(f"series not found: {missing}")
    return df.filter(pl.col("series_id").is_in(ids))


def check_range(
    df: pl.DataFrame,
    *,
    lo: float | None = None,
    hi: float | None = None,
    series_ids: Iterable[str] | None = None,
) -> pl.DataFrame:
    """Rows whose value is outside [lo, hi]."""
    d = _filter(df, series_ids)
    cond = pl.lit(False)
    if lo is not None:
        cond = cond | (pl.col("value") < lo)
    if hi is not None:
        cond = cond | (pl.col("value") > hi)
    return d.filter(cond).select("series_id", "period", "vintage", "value")


def check_identity(
    df: pl.DataFrame,
    total: str,
    parts: Sequence[str] | Mapping[str, float],
    *,
    by: Sequence[str] = ("vintage", "period"),
    abs_tol: float = 1.0,
    rel_tol: float = 1e-6,
    missing_parts_as_zero: bool = False,
) -> pl.DataFrame:
    """Check total = sum(sign * part) for every group in `by` (default: each vintage and period).

    parts: a list (all +1) or {series_id: coefficient} (e.g. imports -1). Tolerance: |diff| <=
    max(abs_tol, rel_tol * |total|). Default abs_tol 1.0 absorbs publisher rounding to whole crore.
    A group where the total or any part is missing is reported (missing_parts), never skipped.
    missing_parts_as_zero=True: for tables that print '-' for a category that did not exist yet,
    an absent PART counts as 0 (the total must still be present). If such a group then fails, the
    zero-filled parts are listed in missing_parts to help the diagnosis.
    """
    coef = dict(parts) if isinstance(parts, Mapping) else {p: 1.0 for p in parts}
    ids = [total, *coef]
    d = _filter(df, ids)
    by = list(by)
    groups = d.select(by).unique(maintain_order=True)
    rows = []
    for g in groups.iter_rows(named=True):
        sub = d.filter(pl.all_horizontal([pl.col(k) == v for k, v in g.items()]))
        vals = dict(zip(sub["series_id"].to_list(), sub["value"].to_list(), strict=True))
        absent = [i for i in ids if i not in vals]
        zero_filled: list[str] = []
        if missing_parts_as_zero and absent and total in vals:
            zero_filled, absent = absent, []
            vals |= dict.fromkeys(zero_filled, 0.0)
        if absent:
            rows.append(
                {**g, "total": vals.get(total), "sum_parts": None, "diff": None, "missing_parts": ",".join(absent)}
            )
            continue
        s = sum(c * vals[p] for p, c in coef.items())
        diff = vals[total] - s
        if abs(diff) > max(abs_tol, rel_tol * abs(vals[total])):
            missing = ",".join(zero_filled) or None
            rows.append({**g, "total": vals[total], "sum_parts": s, "diff": diff, "missing_parts": missing})
    schema = {
        **{k: pl.String for k in by},
        "total": pl.Float64,
        "sum_parts": pl.Float64,
        "diff": pl.Float64,
        "missing_parts": pl.String,
    }
    return pl.DataFrame(rows, schema=schema, orient="row")


def check_continuity(
    df: pl.DataFrame,
    *,
    max_rel_change: float = 0.5,
    series_ids: Iterable[str] | None = None,
    min_abs_level: float = 0.0,
) -> pl.DataFrame:
    """Flag period-to-period jumps larger than max_rel_change (0.5 = 50%) within each series and
    vintage (periods ordered with the `period_type` column when present). Levels smaller than
    min_abs_level are ignored (tiny bases make huge percentages). A flagged break is not
    necessarily wrong; the unit test decides whether it is expected."""
    d = _filter(df, series_ids)
    out = []
    for (sid, vin), sub in d.group_by(["series_id", "vintage"], maintain_order=True):
        types = sub["period_type"].to_list() if "period_type" in sub.columns else [None] * sub.height
        pts = sorted(
            zip(sub["period"].to_list(), sub["value"].to_list(), types, strict=True),
            key=lambda t: period_order_key(t[0], t[2]),
        )
        for (p0, v0, _), (p1, v1, _) in zip(pts, pts[1:], strict=False):
            if abs(v0) < max(min_abs_level, 1e-12):
                continue
            ch = (v1 - v0) / abs(v0)
            if abs(ch) > max_rel_change:
                out.append(
                    {
                        "series_id": sid,
                        "vintage": vin,
                        "from_period": p0,
                        "to_period": p1,
                        "from_value": v0,
                        "to_value": v1,
                        "rel_change": ch,
                    }
                )
    schema = {
        "series_id": pl.String,
        "vintage": pl.String,
        "from_period": pl.String,
        "to_period": pl.String,
        "from_value": pl.Float64,
        "to_value": pl.Float64,
        "rel_change": pl.Float64,
    }
    return pl.DataFrame(out, schema=schema, orient="row")


def compare_vintages(
    df: pl.DataFrame,
    old: str,
    new: str,
    *,
    rel_tol: float = 0.0,
    series_ids: Iterable[str] | None = None,
) -> pl.DataFrame:
    """Revisions between two vintages of the same series: rows present in both whose values differ
    by more than rel_tol, plus rows present in only one vintage (status 'dropped'/'added')."""
    d = _filter(df, series_ids)
    a = d.filter(pl.col("vintage") == old).select("series_id", "period", pl.col("value").alias("old"))
    b = d.filter(pl.col("vintage") == new).select("series_id", "period", pl.col("value").alias("new"))
    j = a.join(b, on=["series_id", "period"], how="full", coalesce=True, maintain_order="left_right")
    j = j.with_columns(
        (pl.col("new") - pl.col("old")).alias("revision"),
        pl.when(pl.col("old").is_null())
        .then(pl.lit("added"))
        .when(pl.col("new").is_null())
        .then(pl.lit("dropped"))
        .otherwise(pl.lit("revised"))
        .alias("change"),
    )
    tol = rel_tol * pl.max_horizontal(pl.col("old").abs(), pl.col("new").abs())
    return j.filter((pl.col("change") != "revised") | (pl.col("revision").abs() > tol)).sort(
        "series_id", "period", maintain_order=True
    )


def all_clean_files(layout: Layout | None = None) -> list[Path]:
    from pipeline.core.runner import clean_files

    return clean_files(layout or Layout.default())
