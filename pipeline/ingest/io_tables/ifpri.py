"""IFPRI Nexus Project, '2022/23 Social Accounting Matrix for India' data paper (1 Oct 2024),
printed tables only (the SAM.tab dataset itself is behind the Dataverse guestbook, D1-1).

Dataset io_tables_ifpri_2223_datapaper, FY 2022-23, all rows status 'estimated' (IFPRI's own SAM
estimates on the old 2011-12 NAS base, transcribed without change; labelled priors only):
- Table 8 'Macro SAM for India in 2022/23 (Billions of Rupees)': 10 x 10 accounts, converted to Rs
  crore (x 100). Row and column totals are checked on the way in.
- Table 10 'Household Income Sources in India (2022/23)': shares of household income (%) by source,
  for all households, national quintiles 1-5, rural and urban. Prior for F1a, R9a, R11a.
- Table 11 'Household Populations and Expenditures in India (2022/23)': population (converted from
  millions to persons), shares, per-capita spending (converted from Rs '000 to Rs), food share and
  savings rate. Prior for C1a and the K4a plausibility check.
Tables 1-7 and 9 are not ingested (structure descriptions, sources, and sector shares on IFPRI's own
42-sector classification). Quintiles are national per-capita-expenditure quintiles, not the SAM's
rural/urban x quintile groups.
"""

from __future__ import annotations

from typing import Any

import pdfplumber
import polars as pl

from pipeline.core.unit import BuildContext, Dataset
from pipeline.core.units import clean_label, conversion_note, parse_number, to_inr_crore

SRC = "ifpri_nexus_sam_india_2022_23_paper"
FILE = "ifpri_sam_india_2022_23_data_paper.pdf"
VINTAGE = "2024-10-01"  # cover page: '01 October 2024'
RELEASE = "IFPRI Nexus Project, 2022/23 Social Accounting Matrix for India (data paper, 1 Oct 2024)"
PERIOD = "2022-23"
METHOD = (
    "IFPRI's own Social Accounting Matrix estimates for India 2022/23 (old 2011-12 NAS base, SUT 2019-20 "
    "coefficients, HCES/PLFS 2022-23), printed in the data paper and transcribed without change except the "
    "stated unit conversion. Used only as a labelled prior."
)
ACCOUNTS = ["activities", "commodities", "factors", "enterprises", "households", "government", "taxes",
            "investment", "rest_of_world", "total"]
T8_ROWS = ["Activities", "Commodities", "Factors", "Enterprises", "Households", "Government", "Taxes", "Savings",
           "Rest of the World", "Total"]
T8_ROW_CODES = ["activities", "commodities", "factors", "enterprises", "households", "government", "taxes",
                "savings", "rest_of_world", "total"]
GROUPS = {"All households": "all", "Quintile 1": "q1", "Quintile 2": "q2", "Quintile 3": "q3", "Quintile 4": "q4",
          "Quintile 5": "q5", "Rural households": "rural", "Urban households": "urban"}
T10_COLS = [
    ("labour_all", "Labor by education level: All workers"),
    ("labour_low_educated", "Labor by education level: Low educated"),
    ("labour_medium_educated", "Labor by education level: Medium educated"),
    ("labour_high_educated", "Labor by education level: High educated"),
    ("crop_land", "Crop land"),
    ("capital_all", "Capital: All"),
    ("capital_agriculture", "Capital: Agriculture"),
    ("capital_non_agriculture", "Capital: Non-agriculture"),
    ("transfers_government", "Transfers: Government"),
    ("transfers_world", "Transfers: World"),
    ("total", "Total"),
]
T11_COLS = [
    ("population", "Population: Millions of people", "count", 1e6),
    ("population_share", "Population: Share of total (%)", "percent", 1.0),
    ("consumption_share", "Consumption spending: Share of total (%)", "percent", 1.0),
    ("consumption_per_capita", "Consumption spending: Per capita (1000 Rupees)", "INR", 1e3),
    ("food_share", "Consumption spending: Food share (%)", "percent", 1.0),
    ("total_spending_per_capita", "Total spending: Per capita (1000 Rupees)", "INR", 1e3),
    ("savings_rate", "Total spending: Savings rate (%)", "percent", 1.0),
]
TOL_X = 9.0


def _lines(words_in: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    words = sorted(words_in, key=lambda w: (round(w["top"]), w["x0"]))
    lines: list[list[dict[str, Any]]] = []
    for w in words:
        if lines and abs(lines[-1][0]["top"] - w["top"]) < 3:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(ln, key=lambda w: w["x0"]) for ln in lines]


def _is_num(t: str) -> bool:
    try:
        return parse_number(t) is not None
    except ValueError:
        return False


def _table8(page: Any) -> dict[tuple[str, str], float]:
    text = page.extract_text() or ""
    if "Table 8: Macro SAM for India in 2022/23 (Billions of Rupees)" not in text:
        raise ValueError("IFPRI paper page 24: Table 8 caption not found")
    words = page.extract_words()  # numbers and labels sit ~2 pt apart vertically: group them separately
    numeric = [ln for ln in _lines([w for w in words if _is_num(w["text"])]) if len(ln) >= 2]
    labels = _lines([w for w in words if not _is_num(w["text"])])
    if len(numeric) != len(T8_ROWS):
        raise ValueError(f"IFPRI Table 8: {len(numeric)} number lines, expected {len(T8_ROWS)}")
    anchors = [w["x1"] for w in numeric[-1]]  # the Total row fills all 9 account columns
    if len(anchors) != 9:
        raise ValueError(f"IFPRI Table 8: Total row has {len(anchors)} numbers, expected 9")
    total_x1 = max(w["x1"] for ln in numeric[:-1] for w in ln)
    anchors.append(total_x1)
    out: dict[tuple[str, str], float] = {}
    for label, code, ln in zip(T8_ROWS, T8_ROW_CODES, numeric, strict=True):
        first = label.split()[0]
        near = [lab for lab in labels if abs(lab[0]["top"] - ln[0]["top"]) < 8 and lab[0]["text"] == first]
        if not near:
            raise ValueError(f"IFPRI Table 8: row label {label!r} not found next to its numbers")
        for w in ln:
            j = min(range(len(anchors)), key=lambda k: abs(anchors[k] - w["x1"]))
            if abs(anchors[j] - w["x1"]) > TOL_X:
                raise ValueError(f"IFPRI Table 8 row {label!r}: {w['text']} matches no column")
            key = (code, ACCOUNTS[j])
            if key in out:
                raise ValueError(f"IFPRI Table 8 row {label!r}: two numbers in column {ACCOUNTS[j]}")
            v = parse_number(w["text"])
            assert v is not None
            out[key] = v
    # every row and column adds up to its printed total (1 bn rounding per cell)
    for r in T8_ROW_CODES[:-1]:
        s = sum(v for (rr, c), v in out.items() if rr == r and c != "total")
        if abs(s - out[(r, "total")]) > 5:
            raise ValueError(f"IFPRI Table 8: row {r} sums to {s}, printed total {out[(r, 'total')]}")
    for c in ACCOUNTS[:-1]:
        s = sum(v for (rr, cc), v in out.items() if cc == c and rr != "total")
        if abs(s - out[("total", c)]) > 5:
            raise ValueError(f"IFPRI Table 8: column {c} sums to {s}, printed total {out[('total', c)]}")
    return out


def _group_rows(page: Any, caption: str, ncols: int) -> dict[str, list[float]]:
    text = page.extract_text() or ""
    if caption not in text:
        raise ValueError(f"IFPRI paper: caption {caption!r} not found")
    start = text.index(caption)
    block = text[start:].split("Source: 2022/23 India SAM.", 1)[0]
    out: dict[str, list[float]] = {}
    for line in block.splitlines():
        for lab, code in GROUPS.items():
            if line.startswith(lab + " "):
                toks = line[len(lab) :].split()
                vals = [parse_number(t) for t in toks]
                if len(vals) != ncols or any(v is None for v in vals):
                    raise ValueError(f"IFPRI {caption[:9]}: row {lab!r} has {toks}, expected {ncols} numbers")
                out[code] = [float(v) for v in vals if v is not None]
    if sorted(out) != sorted(GROUPS.values()):
        raise ValueError(f"IFPRI {caption[:9]}: rows found {sorted(out)}")
    return out


def build_ifpri(ctx: BuildContext) -> Dataset:
    raw = ctx.raw(SRC, FILE)
    with pdfplumber.open(raw.path) as pdf:
        if "2022/23 Social Accounting Matrix for India" not in (pdf.pages[0].extract_text() or ""):
            raise ValueError("IFPRI paper: title page changed")
        t8 = _table8(pdf.pages[23])
        t10 = _group_rows(pdf.pages[25], "Table 10: Household Income Sources in India (2022/23)", len(T10_COLS))
        t11 = _group_rows(pdf.pages[25], "Table 11: Household Populations and Expenditures in India (2022/23)",
                          len(T11_COLS))
    common: dict[str, Any] = dict(raw=raw, price_basis="current", vintage=VINTAGE, release=RELEASE,
                                  status="estimated", method=METHOD)
    p8 = ctx.prov(table_id="Table 8", locator="data paper p. 24 (PDF page 24), 'Table 8: Macro SAM for India in "
                  "2022/23 (Billions of Rupees)'; rows by label order, columns by position under the header",
                  unit_as_published="Rs billion ('Billions of Rupees')", conversion=conversion_note("INR_billion"),
                  **common)
    p10 = ctx.prov(table_id="Table 10", locator="data paper p. 26, 'Table 10: Household Income Sources in India "
                   "(2022/23)', share of total household income (%)", unit_as_published="percent", **common)
    common_na = common | {"price_basis": "n/a"}
    p11 = {
        u: ctx.prov(table_id="Table 11", locator="data paper p. 26, 'Table 11: Household Populations and Expenditures "
                    f"in India (2022/23)' ({what})", unit_as_published=uap, conversion=conv,
                    **(common if u == "INR" else common_na))
        for u, what, uap, conv in (
            ("count", "population", "millions of people", "x 1,000,000 (million -> count)"),
            ("percent", "shares, food share, savings rate", "percent", "none"),
            ("INR", "per-capita spending, annual", "1000 Rupees per person", "x 1,000 (Rs '000 -> Rs)"),
        )
    }
    base: dict[str, Any] = {"source_id": SRC, "geography": "IN", "period": PERIOD, "period_type": "fy",
                            "vintage": VINTAGE, "estimate_stage": "n.a.", "status": "estimated"}
    rows: list[dict[str, Any]] = []
    for (r, c), val in sorted(t8.items()):
        rows.append(base | {
            "series_id": f"ifpri.t8.{r}.{c}.current", "table_id": "Table 8", "item_code": f"macro_sam.{r}.{c}",
            "item_label": clean_label(f"Macro SAM: row {r.replace('_', ' ')}, column {c.replace('_', ' ')}"),
            "dim_other": f"col={c};row={r}", "stock_flow": "flow", "value": to_inr_crore(val, "INR_billion"),
            "unit": "INR_crore", "price_basis": "current", "prov_id": p8})
    for g, vals in t10.items():
        for (code, label), val in zip(T10_COLS, vals, strict=True):
            rows.append(base | {
                "series_id": f"ifpri.t10.{code}.{g}", "table_id": "Table 10", "item_code": f"income_share.{code}",
                "item_label": label, "household_group": g, "stock_flow": "n/a", "value": val, "unit": "percent",
                "price_basis": "current", "prov_id": p10})
    for g, vals in t11.items():
        for (code, label, unit, factor), val in zip(T11_COLS, vals, strict=True):
            rows.append(base | {
                "series_id": f"ifpri.t11.{code}.{g}", "table_id": "Table 11", "item_code": code, "item_label": label,
                "household_group": g, "stock_flow": "stock" if unit == "count" else ("flow" if unit == "INR" else "n/a"),
                "value": val * factor, "unit": unit, "price_basis": "current" if unit == "INR" else "n/a",
                "prov_id": p11[unit]})
    return Dataset(
        "io_tables_ifpri_2223_datapaper",
        pl.DataFrame(rows),
        "IFPRI India SAM 2022/23 data paper: macro SAM (Table 8) and household income/spending by quintile (10, 11)",
    )
