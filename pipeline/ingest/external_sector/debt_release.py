"""RBI press release "India's External Debt as at the end of March 2026" (29 Jun 2026, prid 63041):
external debt by borrowing sector (general government, central bank, deposit-taking corporations,
other financial corporations, non-financial corporations, households/NPISHs, intercompany lending)
and by instrument, end-March 2023-2026, plus the key-indicator history since 1991 (Table 5).

HBS T145/T146 give creditor and instrument types but not the borrower-sector split that the SAM
needs to allocate interest paid abroad (gap map R14). Table 2 (residual maturity, end-March 2026
only) is not ingested. The '(As percentage of GDP)' rows of Table 3 are ingested as percent.
"""

from __future__ import annotations

import re
from typing import Any

import polars as pl

from pipeline.core.unit import BuildContext, Dataset
from pipeline.core.units import clean_label, parse_number

from ._html import find_grid, is_colnum_row, leaf_tables, page_date

UNIT = "external_sector"
SRC = "rbi_external_debt"
PRID = 63041
URL = f"https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid={PRID}"
NAME = "external_debt_end_march_2026_release.html"
RELEASE = "RBI press release: India's External Debt as at the end of March 2026 (29 Jun 2026)"
# Footnote under Tables 1, 3 and 4: "R: Revised. PR: Partially Revised. P: Provisional."
STAGE = {"R": "Revised", "PR": "Partially Revised", "P": "Provisional", None: "n.a."}

T1 = [
    ("I. General Government", "gg", "gg"),
    ("II. Central Bank", "central_bank", "central_bank"),
    ("III. Deposit-taking Corporations, except the Central Bank", "deposit_taking_corporations", "dtc"),
    ("IV. Other Sectors", "other_sectors", "other_sectors"),
    ("IV.1. Other financial corporations", "other_sectors.ofc", "ofc"),
    ("IV.2. Non-financial corporations", "other_sectors.nfc", "nfc"),
    ("IV.3. Households and nonprofit institutions serving households (NPISHs)", "other_sectors.hh_npish", "hh_npish"),
    ("V. Direct Investment: Intercompany Lending", "di_intercompany_lending", "di_intercompany"),
    ("Total Debt (I to V)", "total", None),
    ("Memo Items:", None, None),
    ("A. Long-term Debt (original maturity) @", "memo.long_term_original_maturity", None),
    ("B. Short-term Debt (original maturity) #", "memo.short_term_original_maturity", None),
]
T3 = [
    ("A. Government Debt (I+II)", "government", None),
    ("(As percentage of GDP)", "government.pct_gdp", None),
    ("I. External Debt on Government Account under External Assistance", "government.external_assistance", None),
    ("II. Other Government External Debt @", "government.other", None),
    ("B. Non-government Debt", "non_government", None),
    ("(As percentage of GDP)", "non_government.pct_gdp", None),
    ("B.1. Central Bank", "non_government.central_bank", "central_bank"),
    ("B.2. Deposit-taking Corporations, except the Central Bank", "non_government.deposit_taking_corporations", "dtc"),
    ("B.3. Other Financial Corporations", "non_government.ofc", "ofc"),
    ("B.4. Non-financial Corporations", "non_government.nfc", "nfc"),
    ("B.5. Households and nonprofit institutions serving households (NPISHs)", "non_government.hh_npish", "hh_npish"),
    ("B.6. Direct Investment: Intercompany Lending", "non_government.di_intercompany_lending", "di_intercompany"),
    ("C. Total Debt (A+B)", "total", None),
    ("(As percentage of GDP)", "total.pct_gdp", None),
]
T4 = [
    ("1. Special Drawing Rights (allocations)", "sdr_allocations"),
    ("2. Currency and Deposits", "currency_deposits"),
    ("3. Debt Securities", "debt_securities"),
    ("4. Loans", "loans"),
    ("5. Trade Credit and Advances", "trade_credit"),
    ("6. Other Debt Liabilities", "other"),
    ("7. Direct Investment: Intercompany Lending", "di_intercompany_lending"),
    ("Total Debt", "total"),
]
T5 = {
    "External Debt (US$ billion)": "external_debt",
    "Ratio of External Debt to GDP": "debt_to_gdp",
    "Debt Service Ratio": "debt_service_ratio",
    "Ratio of Foreign Exchange Reserves to Total Debt": "reserves_to_debt",
    "Ratio of Concessional Debt to Total Debt": "concessional_to_debt",
    "Ratio of Short-term Debt (original maturity) to Foreign Exchange Reserves": "short_term_to_reserves",
    "Ratio of Short-term Debt (original maturity) to Total Debt": "short_term_to_debt",
}


def fetch(ctx) -> None:
    ctx.fetch(SRC, URL, name=NAME, expect="html")


def _year(cell: str) -> tuple[str, str]:
    m = re.fullmatch(r"(\d{4})\s*(R|PR|P)?", cell)
    if not m:
        raise ValueError(f"external debt release: year header {cell!r}")
    return f"{m.group(1)}-03-31", STAGE[m.group(2)]


def _num(cell: str) -> float | None:
    return parse_number(cell.strip("()"))


def build(ctx: BuildContext) -> Dataset:
    raw = ctx.raw(SRC, NAME)
    vintage = page_date(raw.path)
    if vintage != "2026-06-29":
        raise ValueError(f"{NAME}: dated {vintage}, expected 2026-06-29")
    grids = leaf_tables(raw.path)
    rows: list[dict[str, Any]] = []

    def add(table, code, label, value, unit, period, stage, inst=None):
        if value is None:
            return
        is_pct = unit == "percent"
        rows.append({
            "series_id": f"edr.{table.lower().replace('table ', 't')}.{code}" + ("" if is_pct else ".usd.current"),
            "source_id": SRC, "table_id": table, "item_code": f"external_debt.{code}", "item_label": clean_label(label),
            "institution": inst, "side": "liabilities", "stock_flow": "n/a" if is_pct else "stock", "period": period,
            "period_type": "date", "value": value * (1 if is_pct else 1000.0), "unit": unit,
            "price_basis": "n/a" if is_pct else "current", "vintage": vintage, "estimate_stage": stage, "status": "official",
        })  # fmt: skip

    for key, table, spec in (("Table 1:", "Table 1", T1), ("Table 3:", "Table 3", T3), ("Table 4:", "Table 4", T4)):
        g = find_grid(grids, key)
        if "US$ billion" not in g.rows[1][0]:
            raise ValueError(f"{table}: caption {g.rows[1][0]!r}")
        k = next(i for i, r in enumerate(g.rows) if is_colnum_row(r))
        hdr = g.rows[k - 1]
        ncols = 3 if table == "Table 1" else 4
        years = {c: _year(hdr[c]) for c in range(1, ncols + 1)}
        body = [r for r in g.rows[k + 1 :] if not re.match(r"^(R:|@:|#:|Note)", r[0])]
        labels = [r[0] for r in body]
        want = [s[0] for s in spec]
        if [clean_label(x).replace(" @", "@").replace(" #", "#") for x in labels] != [w.replace(" @", "@").replace(" #", "#") for w in want]:
            raise ValueError(f"{table}: rows {labels}")
        for r, s in zip(body, spec, strict=True):
            code, inst = s[1], (s[2] if len(s) > 2 else None)
            if code is None:
                continue
            unit = "percent" if code.endswith("pct_gdp") else "USD_million"
            for c, (period, stage) in years.items():
                add(table, code, r[0], _num(r[c]), unit, period, stage, inst)

    g = find_grid(grids, "Table 5:")
    k = next(i for i, r in enumerate(g.rows) if is_colnum_row(r))
    hdr = g.rows[k - 1]
    cols = {c: T5[hdr[c]] for c in range(1, len(hdr))}
    for r in g.rows[k + 1 :]:
        if not re.match(r"^\d{4}", r[0]):
            continue
        period, stage = _year(r[0])
        for c, code in cols.items():
            v = _num(r[c].rstrip("#"))
            unit = "USD_million" if code == "external_debt" else "percent"
            add("Table 5", code, f"{r[0].split()[0]}: {hdr[c]}", v, unit, period, stage)

    blocks: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in rows:
        blocks.setdefault((r["table_id"], r["unit"]), []).append(r)
    for (table, unit), rs in blocks.items():
        pid = ctx.prov(
            raw=raw,
            table_id=table,
            locator=f"HTML press release BS_PressReleaseDisplay.aspx?prid={PRID}, {table}; rows matched by the full ordered "
            f"label list; columns = end-March {sorted({r['period'][:4] for r in rs})[0]}..{sorted({r['period'][:4] for r in rs})[-1]}"
            + ("" if unit == "percent" else " (level columns only; variation columns not ingested)"),
            unit_as_published="per cent" if unit == "percent" else "US$ billion",
            conversion="none" if unit == "percent" else "US$ billion -> US$ million: x 1000",
            price_basis="n/a" if unit == "percent" else "current",
            vintage=vintage,
            release=RELEASE,
        )
        for r in rs:
            r["prov_id"] = pid
    return Dataset(
        f"{UNIT}_external_debt_by_sector",
        pl.DataFrame(rows, infer_schema_length=None),
        "External debt by borrowing sector and instrument, end-March 2023-2026, plus key indicators since 1991 (RBI, 29 Jun 2026)",
    )
