"""Helpers shared by the three trade_satellites source modules (IMF IMTS, UN Comtrade, BaTIS)."""

from __future__ import annotations

import re
from typing import Any

import polars as pl

UNIT = "trade_satellites"

# Publishers give trade values in US$ units (IMF IMTS, UN Comtrade) or US$ million (BaTIS).
USD_UNITS_TO_MILLION = 1e-6
CONV_USD_UNITS = "USD -> USD_million: x 1e-06"

# Three-letter partner codes that are NOT current ISO 3166-1 alpha-3 country codes. They go in
# dim_other as `partner_group=<code>` instead of `geography` (the schema reserves geography for ISO
# codes). Codes starting with 'X' are in ISO's user-assigned range (e.g. XKV/XKX Kosovo) and are
# treated the same way.
NON_ISO_3 = frozenset(
    {
        "WXD",  # BaTIS: Rest of the world
        "KOS",  # IMF: Kosovo, Republic of (not ISO)
        "WBG",  # IMF: West Bank and Gaza (ISO is PSE)
        "CSK",  # Czechoslovakia (withdrawn ISO code)
        "DDR",  # German Democratic Republic (withdrawn)
        "ANT",  # Netherlands Antilles (withdrawn)
        "SCG",  # Serbia and Montenegro (withdrawn)
        "SUN",  # USSR (withdrawn)
        "YUG",  # Yugoslavia (withdrawn)
        "YAR",  # IMF: Yemen Arab Republic (North Yemen, withdrawn 1990; now YEM)
        "YMD",  # IMF: Yemen, People's Democratic Republic (South Yemen, withdrawn 1990; now YEM)
        "W00",  # UN Comtrade: World
    }
)
_ISO3 = re.compile(r"^[A-Z]{3}$")


def is_iso3(code: str) -> bool:
    return bool(_ISO3.match(code)) and code not in NON_ISO_3 and not code.startswith("X")


def partner_dims(code: str) -> dict[str, Any]:
    """{'geography': ISO3} for a country, else {'dim_other': 'partner_group=<code>'}."""
    code = code.strip()
    if is_iso3(code):
        return {"geography": code, "dim_other": None}
    if not code or ";" in code or "=" in code:
        raise ValueError(f"unusable partner code {code!r}")
    return {"geography": None, "dim_other": f"partner_group={code}"}


def sid(code: str) -> str:
    """A series-id fragment from a publisher code: 'USA' -> 'usa', 'S19' -> 's19', '_X ' -> 'x'."""
    s = re.sub(r"[^a-z0-9]+", "_", code.strip().lower()).strip("_")
    if not s:
        raise ValueError(f"cannot make a series-id fragment from {code!r}")
    return s


def fy_label(year: int, month: int) -> str:
    """Indian fiscal year (April-March) of a calendar month: (2024, 3) -> '2023-24'."""
    start = year if month >= 4 else year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def fy_sums(
    monthly: pl.DataFrame, keys: list[str], *, value_col: str = "value", month_col: str = "period"
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Sum monthly rows ('YYYY-MM') into Indian fiscal years per `keys`.

    Returns (complete, incomplete): `complete` has one row per keys x FY with all 12 months
    present (columns keys + fy + value + n_months); `incomplete` lists the key-FYs with fewer
    than 12 months (never summed: a missing month is not assumed to be zero).
    """
    m = monthly.with_columns(
        pl.col(month_col).str.slice(0, 4).cast(pl.Int32).alias("_y"),
        pl.col(month_col).str.slice(5, 2).cast(pl.Int32).alias("_m"),
    ).with_columns(
        pl.when(pl.col("_m") >= 4).then(pl.col("_y")).otherwise(pl.col("_y") - 1).alias("_fys"),
    )
    g = (
        m.group_by([*keys, "_fys"], maintain_order=True)
        .agg(pl.col(value_col).sum().alias(value_col), pl.col("_m").n_unique().alias("n_months"), pl.len().alias("_n"))
        .with_columns(
            (
                pl.col("_fys").cast(pl.String)
                + "-"
                + ((pl.col("_fys") + 1) % 100).cast(pl.String).str.zfill(2)
            ).alias("fy")
        )
    )
    if g.filter(pl.col("_n") != pl.col("n_months")).height:
        raise ValueError("duplicate months inside one series: cannot sum to fiscal years")
    g = g.drop("_n", "_fys")
    return g.filter(pl.col("n_months") == 12), g.filter(pl.col("n_months") < 12)
