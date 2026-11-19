"""Numbers, units, periods and labels as they appear in Indian official publications.

- `parse_number` reads Indian-format cells: '2,61,77,001', '(1,234)', '-', 'NA', '..', '12.5%'.
- `inr_factor` / `to_inr_crore` convert lakh, thousand crore, Rs '000 crore, billion, ... to Rs crore.
- US$ values are converted only with an explicit exchange-rate series that has its own provenance
  (`usd_million_to_inr_crore`). There is deliberately no hard-coded exchange rate anywhere.
- `fy`, `fq`, `survey_period`, `normalize_fy`, `period_type_of` implement the period conventions in
  the guide (`sy` is an explicit survey window 'YYYY-MM/YYYY-MM' for surveys that do not run April-March).
- `round_sig_expr` gives significant-digit rounding for percent/ratio rows (Dataset.ratio_sig_digits).
- `clean_label` gives labels one canonical whitespace form (the schema insists on it).
"""

from __future__ import annotations

import calendar
import datetime as dt
import math
import re
import unicodedata
from typing import Any

import polars as pl

# ---------------------------------------------------------------------------------------------
# Controlled vocabulary for the `unit` column of clean tables
# ---------------------------------------------------------------------------------------------

UNITS: dict[str, str] = {
    "INR_crore": "Rupees crore (1 crore = 10^7 rupees). The default for every money value.",
    "INR": "Rupees (per-unit amounts only: per capita, per household, per month, prices).",
    "USD_million": "US dollars million (kept only where the source is in dollars; convert with fx).",
    "USD": "US dollars (per-unit amounts only).",
    "INR_per_USD": "Exchange rate, rupees per US dollar.",
    "percent": "Percent (12.5 means 12.5%). Shares, growth rates, interest rates.",
    "ratio": "Pure ratio (0.125 means 12.5%).",
    "index": "Index number (the base is described in item_label or the provenance notes).",
    "count": "Number of things (persons, households, enterprises, accounts). Never in thousands/lakh.",
    "tonnes": "Metric tonnes (physical quantities, e.g. trade volumes).",
    "years": "Years (e.g. residual maturity).",
    # Added at the Phase 1 close-out (docs/phase1/FRAMEWORK_REQUESTS.md). Physical quantities are
    # stored in the unit the source prints them in; a unit never converts between them silently.
    "kg": "Kilograms (physical quantities, e.g. per-person food consumption).",
    "gram": "Grams (small physical quantities, e.g. per-person consumption of spices).",
    "litre": "Litres (liquid quantities, e.g. milk, edible oil, fuel).",
    "metre": "Metres (length, e.g. cloth).",
    "kWh": "Kilowatt-hours (electricity quantities).",
    "PJ": "Petajoules (energy quantities; physical energy accounts).",
    "KToE": "Kilotonnes of oil equivalent (energy balance quantities).",
    "EUR_million": "Euro million (kept only where the source is in euro; there is no EUR->INR conversion yet).",
}
# Units whose rows may opt in to significant-digit rounding (Dataset.ratio_sig_digits).
SIG_DIGIT_UNITS = ("percent", "ratio")

# ---------------------------------------------------------------------------------------------
# Number parsing
# ---------------------------------------------------------------------------------------------

MISSING_TOKENS = frozenset(
    {"", "na", "n.a.", "n.a", "n/a", "..", "...", "-", "--", "---", "–", "—", "x", "nr", "neg", "*", "@"}
)
DASH_TOKENS = frozenset({"-", "--", "---", "–", "—"})
ZERO_TOKENS = frozenset({"nil", "0"})

_FOOTNOTE_TRAIL = re.compile(r"[\*#@\$\^†‡§¹²³]+$")
_NUMBER = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


class NumberParseError(ValueError):
    """A cell that should hold a number but does not parse. Never swallowed silently."""


def parse_number(cell: Any, *, dash_as_zero: bool = False) -> float | None:
    """Parse one spreadsheet/PDF cell into a float, or None when the publisher marks it missing.

    - Indian digit grouping is accepted: '2,61,77,001' -> 26177001.0.
    - Accounting negatives: '(1,234)' -> -1234.0. Unicode minus/en-dash prefixes are minus signs.
    - Missing markers ('', 'NA', 'n.a.', '..', '...', '-', en/em dash) -> None.
      `dash_as_zero=True` maps dashes to 0.0 for tables whose notes say '-' means nil.
    - 'Nil' -> 0.0. Trailing footnote marks (*, #, @, $, ^, daggers) and a '%' sign are dropped.
    - Currency marks (Rs, Rs., the rupee sign, INR, US$) and spaces are ignored.
    - Anything else raises NumberParseError: a bad cell must be looked at, not guessed.
    """
    if cell is None:
        return None
    if isinstance(cell, bool):
        raise NumberParseError(f"boolean is not a number: {cell!r}")
    if isinstance(cell, (int, float)):
        x = float(cell)
        return None if math.isnan(x) else x
    if not isinstance(cell, str):
        raise NumberParseError(f"cannot parse {type(cell).__name__} {cell!r} as a number")

    s = unicodedata.normalize("NFKC", cell).strip()
    low = s.lower()
    if low in DASH_TOKENS:
        return 0.0 if dash_as_zero else None
    if low in MISSING_TOKENS:
        return None
    if low == "nil":
        return 0.0

    s = _FOOTNOTE_TRAIL.sub("", s).strip()
    for mark in ("US$", "Rs.", "Rs", "INR", "₹", "$"):
        s = s.replace(mark, "")
    s = s.replace(" ", "").replace(" ", "").replace(",", "").replace("%", "")
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative, s = True, s[1:-1]
    if s[:1] in ("−", "–", "—"):  # unicode minus / en dash / em dash used as minus
        s = "-" + s[1:]
    if not s or not _NUMBER.match(s):
        raise NumberParseError(f"not a number: {cell!r}")
    x = float(s)
    return -x if negative else x


def parse_numbers(cells: list[Any], *, dash_as_zero: bool = False) -> list[float | None]:
    return [parse_number(c, dash_as_zero=dash_as_zero) for c in cells]


# ---------------------------------------------------------------------------------------------
# Rupee scale conversion
# ---------------------------------------------------------------------------------------------

# Multiply a value published in <key> by this factor to get Rs crore.
INR_TO_CRORE: dict[str, float] = {
    "INR": 1e-7,
    "INR_thousand": 1e-4,  # Rs '000
    "INR_lakh": 1e-2,
    "INR_million": 1e-1,
    "INR_crore": 1.0,
    "INR_billion": 1e2,
    "INR_thousand_crore": 1e3,  # also written Rs '000 crore
    "INR_lakh_crore": 1e5,
    "INR_trillion": 1e5,
}

_LABEL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"lakh\s*crore|lac\s*crore"), "INR_lakh_crore"),
    (re.compile(r"(thousand|'000|000's|‘000|’000)\s*crore"), "INR_thousand_crore"),
    (re.compile(r"\bcrore"), "INR_crore"),
    (re.compile(r"\btrillion"), "INR_trillion"),
    (re.compile(r"\bbillion|\bbn\b"), "INR_billion"),
    (re.compile(r"\bmillion|\bmn\b"), "INR_million"),
    (re.compile(r"\blakh|\blac\b|\blacs\b"), "INR_lakh"),
    (re.compile(r"(thousand|'000|‘000|’000)"), "INR_thousand"),
]


class UnitError(ValueError):
    """Unknown or ambiguous unit."""


def inr_unit_from_label(label: str) -> str:
    """Map a published unit caption such as '(Rs. crore)', 'Rs lakh crore', "(Rs '000 crore)" or
    'In Rs billion' to a key of INR_TO_CRORE. Raises UnitError for dollar captions or anything
    unrecognised; never guesses."""
    s = unicodedata.normalize("NFKC", label).lower().replace("₹", "rs ")
    if "us$" in s or "usd" in s or "dollar" in s:
        raise UnitError(f"{label!r} is a US dollar unit; convert with usd_million_to_inr_crore()")
    if re.search(r"\beur\b|euro|€", s):
        raise UnitError(f"{label!r} is a euro unit, not a rupee unit (keep it as EUR_million)")
    for pat, key in _LABEL_PATTERNS:
        if pat.search(s):
            return key
    raise UnitError(f"unrecognised rupee unit caption: {label!r}")


def inr_factor(from_unit: str) -> float:
    """Factor that converts `from_unit` (a key of INR_TO_CRORE) to Rs crore."""
    try:
        return INR_TO_CRORE[from_unit]
    except KeyError:
        raise UnitError(f"unknown rupee unit {from_unit!r}; known: {sorted(INR_TO_CRORE)}") from None


def to_inr_crore(value: Any, from_unit: str) -> Any:
    """Convert a float, polars Expr or Series from `from_unit` to Rs crore."""
    f = inr_factor(from_unit)
    return value if f == 1.0 else value * f


def conversion_note(from_unit: str) -> str:
    """Text for the provenance `conversion` field."""
    f = inr_factor(from_unit)
    return "none" if f == 1.0 else f"{from_unit} -> INR_crore: x {f:g}"


def usd_million_to_inr_crore(
    values: pl.DataFrame,
    rates: pl.DataFrame,
    *,
    on: str | list[str] = "period",
    value_col: str = "value",
    rate_col: str = "value",
    rate_prov_col: str = "prov_id",
) -> pl.DataFrame:
    """Convert US$ million to Rs crore with an explicit rate series (Rs per US$).

    `rates` must come from a clean dataset (unit INR_per_USD) and carry its own prov_id.
    Every row of `values` must find exactly one rate; a missing or duplicate rate is an error.
    Returns `values` with `value_col` converted, `unit`='INR_crore' (if a unit column exists) and a
    new column `fx_prov_id` that the caller cites in the provenance `inputs` of the converted rows
    (status 'derived'). 1 US$ million x rate Rs/US$ = rate x 10^6 Rs = rate / 10 Rs crore.
    """
    keys = [on] if isinstance(on, str) else list(on)
    r = rates.select(*keys, pl.col(rate_col).alias("_fx_rate"), pl.col(rate_prov_col).alias("fx_prov_id"))
    dup = r.group_by(keys, maintain_order=True).len().filter(pl.col("len") > 1)
    if dup.height:
        raise UnitError(f"duplicate exchange rates for {dup.select(keys).to_dicts()}")
    out = values.join(r, on=keys, how="left", maintain_order="left")
    missing = out.filter(pl.col("_fx_rate").is_null()).select(keys).unique(maintain_order=True)
    if missing.height:
        raise UnitError(f"no exchange rate for {missing.to_dicts()}")
    out = out.with_columns((pl.col(value_col) * pl.col("_fx_rate") / 10.0).alias(value_col)).drop("_fx_rate")
    if "unit" in out.columns:
        out = out.with_columns(pl.lit("INR_crore").alias("unit"))
    return out


# ---------------------------------------------------------------------------------------------
# Periods
# ---------------------------------------------------------------------------------------------

PERIOD_PATTERNS: dict[str, str] = {
    "fy": r"^\d{4}-\d{2}$",  # Indian fiscal year April-March: '2023-24'
    "fh": r"^H[12] \d{4}-\d{2}$",  # fiscal half-year: 'H1 2023-24' (Apr-Sep)
    "fq": r"^Q[1-4] \d{4}-\d{2}$",  # fiscal quarter: 'Q1 2026-27' (Q1 = Apr-Jun)
    "cy": r"^\d{4}$",  # calendar year: '2024'
    "cq": r"^\d{4}-Q[1-4]$",  # calendar quarter: '2024-Q1' (Jan-Mar)
    "month": r"^\d{4}-(0[1-9]|1[0-2])$",  # '2024-12'
    "date": r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$",  # stocks at a date: '2024-03-31'
    # survey window, first and last month inclusive: '2023-08/2024-07' (HCES 2023-24, Aug-Jul),
    # '2023-07/2024-06' (PLFS/SAS agricultural year, Jul-Jun), '2022-10/2023-09' (ASUSE, Oct-Sep)
    "sy": r"^\d{4}-(0[1-9]|1[0-2])/\d{4}-(0[1-9]|1[0-2])$",
}
_PERIOD_RE = {k: re.compile(v) for k, v in PERIOD_PATTERNS.items()}


def fy(start_year: int) -> str:
    """fy(2023) -> '2023-24'."""
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def fq(quarter: int, start_year: int) -> str:
    """fq(1, 2026) -> 'Q1 2026-27' (fiscal Q1 = April-June)."""
    if quarter not in (1, 2, 3, 4):
        raise ValueError(f"quarter must be 1-4, got {quarter}")
    return f"Q{quarter} {fy(start_year)}"


def survey_period(start_year: int, start_month: int, months: int = 12) -> str:
    """An `sy` label for a survey window of `months` months starting in start_year-start_month.

    survey_period(2023, 8) -> '2023-08/2024-07' (HCES 2023-24); survey_period(2023, 7) ->
    '2023-07/2024-06' (a July-June agricultural year); survey_period(2025, 1) -> '2025-01/2025-12'."""
    if not 1 <= start_month <= 12:
        raise ValueError(f"start_month must be 1-12, got {start_month}")
    if months < 1:
        raise ValueError(f"months must be >= 1, got {months}")
    end = start_year * 12 + (start_month - 1) + (months - 1)
    return f"{start_year:04d}-{start_month:02d}/{end // 12:04d}-{end % 12 + 1:02d}"


def agricultural_year(start_year: int) -> str:
    """The July-June agricultural year starting in July of start_year, as an `sy` label:
    agricultural_year(2023) -> '2023-07/2024-06' (PLFS 2023-24, SAS)."""
    return survey_period(start_year, 7)


def fy_start(label: str) -> int:
    """'2023-24' -> 2023 (validates that the two years are consecutive)."""
    m = re.fullmatch(r"(\d{4})-(\d{2})", label)
    if not m or (int(m.group(1)) + 1) % 100 != int(m.group(2)):
        raise ValueError(f"not a fiscal year label 'YYYY-YY': {label!r}")
    return int(m.group(1))


_FY_ANY = re.compile(r"(?<!\d)(\d{4})\s*[-–—/]\s*(\d{2}|\d{4})(?!\d)")


def normalize_fy(text: str) -> str:
    """Find one fiscal year in free text and return 'YYYY-YY'.

    Accepts '2023-24', '2023-2024', '2023–24', '2023/24', '2023-24 (FE)', 'FY 2023-24'.
    Raises ValueError if there is no year, more than one year, or the years are not consecutive.
    """
    found = _FY_ANY.findall(unicodedata.normalize("NFKC", str(text)))
    if len(found) != 1:
        raise ValueError(f"expected exactly one fiscal year in {text!r}, found {len(found)}")
    a, b = int(found[0][0]), int(found[0][1])
    if b >= 1000:
        ok = b == a + 1
    else:
        ok = b == (a + 1) % 100
    if not ok:
        raise ValueError(f"fiscal year years are not consecutive in {text!r}")
    return fy(a)


def period_ok(period: str, period_type: str) -> bool:
    """True if `period` is a valid label of `period_type` (fiscal years must be consecutive)."""
    rx = _PERIOD_RE.get(period_type)
    if rx is None or not rx.match(period):
        return False
    if period_type == "fy":
        return (int(period[:4]) + 1) % 100 == int(period[5:7])
    if period_type in ("fq", "fh"):
        y = period[3:]
        return (int(y[:4]) + 1) % 100 == int(y[5:7])
    if period_type == "date":
        try:
            dt.date.fromisoformat(period)
        except ValueError:
            return False  # e.g. '2024-02-31'
    if period_type == "sy":
        a, b = period.split("/")
        return (int(a[:4]), int(a[5:7])) <= (int(b[:4]), int(b[5:7]))  # may not end before it starts
    return True


def period_order_key(period: str, period_type: str | None = None) -> tuple[int, int, int, int, int, int, str]:
    """Total chronological order across period types: start, then end (the shorter period first),
    then the label. Two different periods never tie."""
    pt = period_type or period_type_of(period)
    end = period_end(period, pt)
    return (*period_sort_key(period, pt), end.year, end.month, end.day, period)


def period_start(period: str, period_type: str) -> dt.date:
    """First day of the period (the date itself for 'date')."""
    y, m, d = period_sort_key(period, period_type)
    return dt.date(y, m, d or 1)


def period_end(period: str, period_type: str) -> dt.date:
    """Last day of the period (the date itself for 'date')."""
    if not period_ok(period, period_type):
        raise ValueError(f"{period!r} is not a valid {period_type} period")
    if period_type == "date":
        return dt.date.fromisoformat(period)
    if period_type == "sy":
        y, m = int(period[8:12]), int(period[13:15])
    elif period_type == "month":
        y, m = int(period[:4]), int(period[5:7])
    else:
        months = {"fy": 12, "fh": 6, "fq": 3, "cy": 12, "cq": 3}[period_type]
        y0, m0, _ = period_sort_key(period, period_type)
        last = y0 * 12 + (m0 - 1) + months - 1
        y, m = last // 12, last % 12 + 1
    return dt.date(y, m, calendar.monthrange(y, m)[1])


EARLIEST_VINTAGE_YEAR = 1947


def vintage_problem(vintage: str, today: dt.date | None = None) -> str | None:
    """Why a vintage ('YYYY', 'YYYY-MM' or 'YYYY-MM-DD' publication date) is impossible, or None."""
    today = today or dt.date.today()
    m = re.fullmatch(r"(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?", vintage)
    if not m:
        return "not YYYY, YYYY-MM or YYYY-MM-DD"
    y, mo, d = int(m.group(1)), m.group(2), m.group(3)
    try:
        first = dt.date(y, int(mo) if mo else 1, int(d) if d else 1)
    except ValueError:
        return "not a real date"
    if y < EARLIEST_VINTAGE_YEAR:
        return f"before {EARLIEST_VINTAGE_YEAR}"
    if first > today:
        return f"after today ({today.isoformat()}): a vintage is a publication date"
    return None


def vintage_end(vintage: str) -> dt.date:
    """Latest date a (possibly partial) vintage can mean: '2026' -> 2026-12-31, '2026-02' -> 2026-02-28."""
    parts = [int(x) for x in vintage.split("-")]
    if len(parts) == 1:
        return dt.date(parts[0], 12, 31)
    if len(parts) == 2:
        return dt.date(parts[0], parts[1], calendar.monthrange(parts[0], parts[1])[1])
    return dt.date(parts[0], parts[1], parts[2])


def period_type_of(period: str) -> str:
    """The period_type of a label. Raises ValueError if none fits or if it is ambiguous:
    '2011-12' is both FY 2011-12 and December 2011 (true for FY 2000-01..2011-12), so data rows
    always carry an explicit period_type and code should pass it on."""
    kinds = [k for k in _PERIOD_RE if period_ok(period, k)]
    if len(kinds) == 1:
        return kinds[0]
    if not kinds:
        raise ValueError(f"period {period!r} matches no convention: {PERIOD_PATTERNS}")
    raise ValueError(f"period {period!r} is ambiguous ({' or '.join(kinds)}); pass period_type explicitly")


def period_sort_key(period: str, period_type: str | None = None) -> tuple[int, int, int]:
    """Chronological key of the period's START, across period types. It is not a total order:
    periods that start in the same month tie (FY 2023-24, H1 2023-24, Q1 2023-24 and 2023-04; the
    survey windows 2023-07/2023-12 and 2023-07/2024-06). Use period_order_key to order by it."""
    pt = period_type or period_type_of(period)
    if not period_ok(period, pt):
        raise ValueError(f"{period!r} is not a valid {pt} period")
    if pt == "fy":
        return (int(period[:4]), 4, 0)
    if pt == "fh":
        return (int(period[3:7]), 4 if period[1] == "1" else 10, 0)
    if pt == "fq":
        q, y = int(period[1]), int(period[3:7])
        month = 3 * q + 1  # Q1->Apr, Q2->Jul, Q3->Oct, Q4->Jan(next year)
        return (y + (1 if month > 12 else 0), (month - 1) % 12 + 1, 0)
    if pt == "cy":
        return (int(period), 1, 0)
    if pt == "cq":
        return (int(period[:4]), 3 * int(period[-1]) - 2, 0)
    if pt in ("month", "sy"):
        return (int(period[:4]), int(period[5:7]), 0)
    return (int(period[:4]), int(period[5:7]), int(period[8:10]))


# ---------------------------------------------------------------------------------------------
# Significant-digit rounding (opt-in, percent/ratio rows only)
# ---------------------------------------------------------------------------------------------

DEFAULT_VALUE_DECIMALS = 6  # the writer's default (pipeline.core.io.DEFAULT_DECIMALS)
MAX_VALUE_DECIMALS = 15  # float64 carries about 15-17 significant digits


def round_sig_expr(col: pl.Expr, sig_digits: int) -> pl.Expr:
    """Round to `sig_digits` significant digits, but never to fewer than 6 decimals (the default
    precision) and never to more than 15. Opting in therefore only ever keeps MORE precision: a
    weight share of 0.000123456789 stays 0.000123456789 (sig 9) instead of 0.000123 (6 decimals),
    while 12.5 or 1234.5678 are unchanged. Deterministic: one fixed `round(d)` per decimal count d."""
    if not 1 <= sig_digits <= MAX_VALUE_DECIMALS:
        raise ValueError(f"sig_digits must be 1-{MAX_VALUE_DECIMALS}, got {sig_digits}")
    mag = pl.when(col == 0).then(pl.lit(0.0)).otherwise(col.abs().log10().floor())
    d = (pl.lit(float(sig_digits - 1)) - mag).clip(DEFAULT_VALUE_DECIMALS, MAX_VALUE_DECIMALS)
    expr = col.round(DEFAULT_VALUE_DECIMALS)
    for k in range(DEFAULT_VALUE_DECIMALS + 1, MAX_VALUE_DECIMALS + 1):
        expr = pl.when(d == float(k)).then(col.round(k)).otherwise(expr)
    return expr


# ---------------------------------------------------------------------------------------------
# Labels and identifiers
# ---------------------------------------------------------------------------------------------


def clean_label(text: Any) -> str:
    """Canonical label text: NFC-normalised, whitespace runs collapsed to one space, stripped."""
    s = unicodedata.normalize("NFC", str(text))
    return re.sub(r"\s+", " ", s).strip()


def slug(text: str) -> str:
    """Lower-case snake_case identifier fragment: 'Gross Value Added (GVA)' -> 'gross_value_added_gva'."""
    s = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    if not s:
        raise ValueError(f"cannot make an identifier from {text!r}")
    return s
