"""Display formatting, mirrored from web/src/lib/format.ts (docs/phase3/PLAN.md s.3.3). Owner: U1.

Both implementations must reproduce `pipeline/export/golden/format_cases.json` exactly
(tests/export/test_formats.py here; U2's format.test.ts in the browser).

Rules (the same text is in the golden file's `rules`):
- Rounding is half away from zero on the exact binary value of the float (JavaScript's
  `Intl.NumberFormat(..., {roundingMode: "halfExpand"})` and `Number.prototype.toFixed` on |v|). Python's
  `round()` (half to even) is NOT used. Every rule formats |v| and puts a leading U+2212 minus sign in front
  when v < 0 and the formatted magnitude is not zero.
- Tiers are chosen on the rounded magnitude, so a value never prints as "₹1000 crore" or "1.00%".
- `inr` (v in ₹ crore): r0 = |v| rounded to 0 dp. r0 >= 1,00,000 -> "₹{|v|/1e5, 2 dp} lakh crore";
  else |v| rounded to 1 dp >= 10 -> "₹{r0 with en-IN grouping} crore"; else "₹{|v|, 1 dp} crore".
- `pct_gdp` (v is a share of GDP, a fraction): p = 100|v|. p rounded to 1 dp >= 1 -> "{p, 1 dp}% of GDP";
  else p rounded to 2 dp >= 0.01 -> "{p, 2 dp}% of GDP"; v == 0 -> "0% of GDP"; else "<0.01% of GDP".
- `per100` (v in ₹ per ₹100): "₹{|v|, 1 dp}".
- `pct` (v is a fraction, not of GDP): "{100|v|, 1 dp}%".
- en-IN grouping on the integer part of every number: the last three digits, then groups of two
  (1,23,45,678; "₹1,234.57 lakh crore").
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

MINUS = "−"
RUPEE = "₹"
KINDS = ("inr", "pct_gdp", "per100", "pct")


def round_half_up(x: float, decimals: int) -> Decimal:
    """|x| rounded half away from zero on its exact binary value (x must be >= 0)."""
    if not math.isfinite(x):
        raise ValueError(f"cannot format non-finite {x!r}")
    if x < 0:
        raise ValueError("round_half_up takes a magnitude")
    return Decimal(x).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def group_en_in(digits: str) -> str:
    """'12345678' -> '1,23,45,678' (Indian grouping of an integer digit string)."""
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts) + "," + tail


def _num(a: float, decimals: int) -> str:
    """|value| rounded half away from zero, en-IN grouping on the integer part (as Intl.NumberFormat('en-IN'))."""
    text = f"{round_half_up(a, decimals):.{decimals}f}"
    whole, _, frac = text.partition(".")
    return group_en_in(whole) + ("." + frac if frac else "")


def _sign(v: float, magnitude_text: str) -> str:
    zero = all(ch in "0.," for ch in magnitude_text)
    return MINUS if v < 0 and not zero else ""


def fmt_inr(v: float) -> str:
    a = abs(v)
    r0 = round_half_up(a, 0)
    if r0 >= 100000:
        m = _num(a / 1e5, 2)
        return f"{_sign(v, m)}{RUPEE}{m} lakh crore"
    if round_half_up(a, 1) >= 10:
        m = _num(a, 0)
        return f"{_sign(v, m)}{RUPEE}{m} crore"
    m = _num(a, 1)
    return f"{_sign(v, m)}{RUPEE}{m} crore"


def fmt_pct_gdp(v: float) -> str:
    p = abs(v) * 100
    if round_half_up(p, 1) >= 1:
        m = _num(p, 1)
    elif round_half_up(p, 2) >= Decimal("0.01"):
        m = _num(p, 2)
    elif v == 0:
        return "0% of GDP"
    else:
        return f"{MINUS if v < 0 else ''}<0.01% of GDP"
    return f"{_sign(v, m)}{m}% of GDP"


def fmt_per100(v: float) -> str:
    m = _num(abs(v), 1)
    return f"{_sign(v, m)}{RUPEE}{m}"


def fmt_pct(v: float) -> str:
    m = _num(abs(v) * 100, 1)
    return f"{_sign(v, m)}{m}%"


def fmt(kind: str, v: float) -> str:
    if kind == "inr":
        return fmt_inr(v)
    if kind == "pct_gdp":
        return fmt_pct_gdp(v)
    if kind == "per100":
        return fmt_per100(v)
    if kind == "pct":
        return fmt_pct(v)
    raise ValueError(f"unknown format kind {kind!r}")
