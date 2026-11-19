"""RBI files of the state_fiscal unit: State Finances 2025-26 (statements, appendix tables,
Appendices I-IV), Report on Municipal Finances (Nov 2024) and Finances of Panchayati Raj
Institutions (Jan 2024)."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

import openpyxl
import polars as pl
from openpyxl.utils import get_column_letter

from pipeline.core.unit import BuildContext, Dataset, RawFile
from pipeline.core.units import clean_label, conversion_note, inr_unit_from_label, parse_number, to_inr_crore

from .common import Geo, ItemRow, expect, norm, parse_item_rows, rbi_period, state_geo
from .sources import RBI_MUNI, RBI_PRI, RBI_SF

UNIT = "state_fiscal"
SF_VINTAGE = "2026-01-23"  # listing date of the 2025-26 edition on www.rbi.org.in
SF_RELEASE = "State Finances: A Study of Budgets of 2025-26 (RBI, 23 Jan 2026)"
MUNI_VINTAGE = "2024-11-13"
MUNI_RELEASE = "Report on Municipal Finances (RBI, 13 Nov 2024)"
PRI_VINTAGE = "2024-01-24"
PRI_RELEASE = "Finances of Panchayati Raj Institutions 2020-21 to 2022-23 (RBI, 24 Jan 2024)"

# Second lines of labels that RBI wraps over two rows.
CONTINUATIONS = {
    "callings and employment",
    "agriculture and rural development",
    "development corporation",
    "tribes and other backward classes",
    "balance investment account (net)",
    "advances and overdrafts from rbi (net)",
}


def _row(
    *,
    series_id: str,
    source_id: str,
    table_id: str,
    item_code: str,
    item_label: str,
    geo: Geo,
    period: str,
    period_type: str,
    value: float,
    unit: str,
    stage: str,
    vintage: str,
    prov: str,
    stock_flow: str = "flow",
    side: str | None = None,
    institution: str | None = None,
    extra_dim: str | None = None,
) -> dict[str, Any]:
    dims = [d for d in (geo.dim_other, extra_dim) if d]
    return {
        "series_id": series_id,
        "source_id": source_id,
        "table_id": table_id,
        "item_code": item_code,
        "item_label": clean_label(item_label),
        "institution": institution or geo.institution,
        "geography": geo.geography,
        "side": side,
        "dim_other": ";".join(sorted(dims)) or None,
        "stock_flow": stock_flow,
        "period": period,
        "period_type": period_type,
        "value": float(value),
        "unit": unit,
        "price_basis": "n/a" if unit in ("percent", "ratio") else "current",
        "vintage": vintage,
        "estimate_stage": stage,
        "status": "official",
        "prov_id": prov,
    }


# DECISIONS D1-9: J&K's FY 2019-20 rows straddle the reorganisation of 31 Oct 2019 (declared in __init__.py).
JK_2019_20 = (
    'Jammu and Kashmir, FY 2019-20: the State of J&K became the UTs of J&K and Ladakh on 31 Oct 2019, '
    'inside the year; the row is coded IN-JK (the UT) as printed, and its territory is not fixed for that '
    'year (DECISIONS D1-9; issues file state_fiscal-21). '
)


def _prov(
    ctx: BuildContext, raw: RawFile, table: str, locator: str, unit_pub: str, vintage: str, release: str, notes=None
) -> str:
    try:
        conv = conversion_note(inr_unit_from_label(unit_pub))
    except Exception:
        conv = "none"
    return ctx.prov(
        raw=raw,
        table_id=table,
        locator=locator,
        unit_as_published=unit_pub,
        conversion=conv,
        price_basis="n/a" if "per cent" in unit_pub.lower() or "percent" in unit_pub.lower() else "current",
        vintage=vintage,
        release=release,
        notes=notes,
    )


def _money(unit_caption: str) -> tuple[str, str]:
    """(clean unit, rupee key) for a sheet's printed unit caption such as '(₹ Lakh)'."""
    key = inr_unit_from_label(unit_caption)
    return "INR_crore", key


# ---------------------------------------------------------------------------------------------
# Appendices I-IV (and the PRI appendices, same layout): item rows x (geography x period) columns
# ---------------------------------------------------------------------------------------------


def _blocks(ws: Any, geo_row: int, period_row: int) -> list[tuple[str, dict[str, str]]]:
    """[(geography name, {column letter: period header})] for one sheet."""
    starts = [
        (c, ws.cell(geo_row, c).value)
        for c in range(3, ws.max_column + 1)
        if ws.cell(geo_row, c).value not in (None, "")
    ]
    out = []
    for i, (c, name) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else ws.max_column + 1
        cols = {
            get_column_letter(k): str(ws.cell(period_row, k).value)
            for k in range(c, end)
            if ws.cell(period_row, k).value not in (None, "")
        }
        out.append((clean_label(name), cols))
    return out


def _appendix_tables(
    raw: RawFile, title: str, *, first_data_row: int = 7
) -> dict[str, tuple[str, list[tuple[int, str, str, dict[str, Any]]], dict[str, str], str]]:
    """{geography name: (unit caption, [(row, sheet, label, {col: cell})...], {col: period}, sheets)} with a
    geography's rows concatenated across the workbook's sheets in order."""
    wb = openpyxl.load_workbook(raw.path, data_only=True)
    acc: dict[str, list] = {}
    cols_of: dict[str, dict[str, str]] = {}
    unit_of: dict[str, str] = {}
    sheets_of: dict[str, list[str]] = defaultdict(list)
    for ws in wb.worksheets:
        expect(ws, "B2", title)
        caption = clean_label(ws["B3"].value or "")
        for name, cols in _blocks(ws, 4, 5):
            key = norm(name)
            if key in cols_of and list(cols_of[key].values()) != list(cols.values()):
                raise ValueError(f"{raw.name} {ws.title}: period columns of {name} differ between sheets")
            cols_of.setdefault(key, cols)
            if unit_of.setdefault(key, caption) != caption:
                raise ValueError(f"{raw.name} {ws.title}: unit caption changed for {name}")
            sheets_of[key].append(ws.title)
            rows = acc.setdefault(key, [])
            for r in range(first_data_row, ws.max_row + 1):
                label = ws.cell(r, 2).value
                if label is None or str(label).strip() == "":
                    continue
                lab = clean_label(label)
                if _is_note(lab):
                    continue
                # map this block's columns onto the first sheet's column letters (blocks keep order)
                cells = {}
                for (c0, _), (c1, _) in zip(cols_of[key].items(), cols.items(), strict=True):
                    cells[c0] = ws[f"{c1}{r}"].value
                rows.append((r, ws.title, lab, cells))
    return {
        k: (unit_of[k], acc[k], cols_of[k], ", ".join(sheets_of[k]))
        for k in acc
    }


def _is_note(label: str) -> bool:
    n = norm(label)
    return (
        n.startswith(("note", "source", "re:", "re :", "rbi:", "also see", "*", "@", "$", "#", "+", "**", "'–'", "‘–’"))
        or n[:2] in ("* ", "@ ", "$ ", "# ", "+ ")
        or n.startswith(("2. as per the constitution", "2. *:", "2. data from", "3. all figures", "4. data from"))
    )


def build_appendices(ctx: BuildContext) -> Dataset:
    """Appendices I-IV of State Finances 2025-26: every line item for All States and UTs (Rs lakh -> crore)."""
    specs = (
        ("sf2526_appx1_all.xlsx", "Appendix I", "Appendix I : Revenue Receipts of States", "receipts"),
        ("sf2526_appx2_all.xlsx", "Appendix II", "Appendix II : Revenue Expenditure of States", "payments"),
        ("sf2526_appx3_all.xlsx", "Appendix III", "Appendix III : Capital Receipts of States", "receipts"),
        ("sf2526_appx4_all.xlsx", "Appendix IV", "Appendix IV : Capital Expenditure of States", "payments"),
    )
    rows: list[dict[str, Any]] = []
    for name, table, title, side in specs:
        raw = ctx.raw(RBI_SF, name)
        blocks = _appendix_tables(raw, title)
        allkey = next((k for k in blocks if k.startswith("all state")), None)
        if allkey is None:
            raise ValueError(f"{name}: no 'All States and UTs' block found (blocks: {sorted(blocks)})")
        caption, items_raw, cols, sheets = blocks[allkey]
        if inr_unit_from_label(caption) != "INR_lakh":
            raise ValueError(f"{name}: expected a Rs lakh caption, found {caption!r}")
        geo = Geo("IN", "state_group=all_states_uts")
        items = parse_item_rows(
            [(r, lab, cells) for r, _, lab, cells in items_raw], continuations=CONTINUATIONS, where=f"{name} {allkey}"
        )
        periods = {c: rbi_period(h) for c, h in cols.items()}
        first, last = items_raw[0][0], items_raw[-1][0]
        pid = _prov(
            ctx,
            raw,
            table,
            f"sheets {sheets}, block '{allkey}' (label col B, rows {first}-{last} of each sheet), period columns "
            f"{', '.join(f'{c}={h}' for c, h in cols.items())}; rows matched by printed label/numbering",
            caption,
            SF_VINTAGE,
            SF_RELEASE,
        )
        tcode = "app" + {"Appendix I": "1", "Appendix II": "2", "Appendix III": "3", "Appendix IV": "4"}[table]
        for it in items:
            for col, (period, stage) in periods.items():
                v = parse_number(it.cells.get(col))
                if v is None:
                    continue
                rows.append(
                    _row(
                        series_id=f"{tcode}.{it.code}.{geo.key}.{stage.lower()}",
                        source_id=RBI_SF,
                        table_id=table,
                        item_code=f"{tcode}.{it.code}",
                        item_label=it.label,
                        geo=geo,
                        period=period,
                        period_type="fy",
                        value=to_inr_crore(v, "INR_lakh"),
                        unit="INR_crore",
                        stage=stage,
                        vintage=SF_VINTAGE,
                        prov=pid,
                        side=side,
                        extra_dim=f"stage={stage.lower()}",
                    )
                )
    return Dataset(
        f"{UNIT}_rbi_sf_appendices",
        pl.DataFrame(rows, infer_schema_length=None),
        "RBI State Finances 2025-26 Appendices I-IV, All States and UTs, every line item, 2023-24 Accounts to 2025-26 BE (Rs crore)",
    )


def item_tree(ctx: BuildContext, name: str, source_id: str, title: str) -> list[ItemRow]:
    """Parsed item rows of the All-States block (used by tests through the build output)."""
    raw = ctx.raw(source_id, name)
    blocks = _appendix_tables(raw, title)
    allkey = next(k for k in blocks if k.startswith("all state"))
    return parse_item_rows(
        [(r, lab, cells) for r, _, lab, cells in blocks[allkey][1]], continuations=CONTINUATIONS, where=name
    )


# ---------------------------------------------------------------------------------------------
# State-wise statements
# ---------------------------------------------------------------------------------------------


def _state_rows(ws: Any, first: int) -> list[tuple[int, Geo, str]]:
    out = []
    for r in range(first, ws.max_row + 1):
        v = ws.cell(r, 2).value
        if v is None:
            continue
        lab = clean_label(v)
        n = norm(lab)
        if n.startswith(("re", "note", "source", "*", "'", "‘", "rbi")) and "states" not in n:
            continue
        if n.startswith(("re :", "re:", "‘*’", "'*'", "*", "‘–’")):
            continue
        out.append((r, state_geo(lab), lab))
    return out


def build_statements(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    # Statements 13 and 17: gross and net, three periods (+ variation columns, not ingested)
    for name, table, title, code, label in (
        ("sf2526_st13.xlsx", "Statement 13", "Statement 13: Interest Payments", "interest_payments", "Interest Payments"),
        (
            "sf2526_st17.xlsx",
            "Statement 17",
            "Statement 17: Devolution and Transfer of Resources from the Centre",
            "transfers_from_centre",
            "Devolution and Transfer of Resources from the Centre",
        ),
    ):
        raw = ctx.raw(RBI_SF, name)
        ws = openpyxl.load_workbook(raw.path, data_only=True).worksheets[0]
        expect(ws, "B2", title)
        expect(ws, "B3", "Crore")
        heads = {"C": ws["C4"].value, "E": ws["E4"].value, "G": ws["G4"].value}
        for c, sub in (("C", "Gross"), ("D", "Net"), ("E", "Gross"), ("F", "Net"), ("G", "Gross"), ("H", "Net")):
            expect(ws, f"{c}6", sub)
        states = _state_rows(ws, 8)
        pid = _prov(
            ctx,
            raw,
            table,
            f"sheet '{ws.title}', rows {states[0][0]}-{states[-1][0]} (States/UTs and All States and UTs), cols C:H "
            "(gross/net for 2023-24 Accounts, 2024-25 RE, 2025-26 BE); variation columns I:L not ingested",
            "Rs Crore",
            SF_VINTAGE,
            SF_RELEASE,
        )
        for r, geo, _ in states:
            for gcol, ncol, head in (("C", "D", heads["C"]), ("E", "F", heads["E"]), ("G", "H", heads["G"])):
                period, stage = rbi_period(head)
                for col, basis in ((gcol, "gross"), (ncol, "net")):
                    v = parse_number(ws[f"{col}{r}"].value)
                    if v is None:
                        continue
                    rows.append(
                        _row(
                            series_id=f"st{table.split()[-1]}.{code}_{basis}.{geo.key}.{stage.lower()}",
                            source_id=RBI_SF,
                            table_id=table,
                            item_code=f"{code}_{basis}",
                            item_label=f"{label} ({basis})",
                            geo=geo,
                            period=period,
                            period_type="fy",
                            value=v,
                            unit="INR_crore",
                            stage=stage,
                            vintage=SF_VINTAGE,
                            prov=pid,
                            extra_dim=f"stage={stage.lower()}",
                        )
                    )
    # Statements 14 and 15: shares of each State in the all-States total (per cent)
    for name, table, title, groups in (
        (
            "sf2526_st14.xlsx",
            "Statement 14",
            "Statement 14: Tax Revenue",
            (("C", "tax_revenue", "Tax Revenue"), ("F", "own_tax_revenue", "Own Tax Revenue"), ("I", "share_in_central_taxes", "Share in Central Taxes")),
        ),
        (
            "sf2526_st15.xlsx",
            "Statement 15",
            "Statement 15: Non",
            (("C", "non_tax_revenue", "Non-Tax Revenue"), ("F", "own_non_tax_revenue", "Own Non-Tax Revenue"), ("I", "grants", "Grants")),
        ),
    ):
        raw = ctx.raw(RBI_SF, name)
        ws = openpyxl.load_workbook(raw.path, data_only=True).worksheets[0]
        expect(ws, "B2", title)
        expect(ws, "B3", "Per cent")
        states = _state_rows(ws, 7)
        pid = _prov(
            ctx,
            raw,
            table,
            f"sheet '{ws.title}', rows {states[0][0]}-{states[-1][0]}, cols C:K (three items x 2023-24 Accounts, "
            "2024-25 RE, 2025-26 BE); each State's share of the all-States total",
            "Per cent (share of all States and UTs total)",
            SF_VINTAGE,
            SF_RELEASE,
        )
        for c0, code, label in groups:
            expect(ws, f"{c0}4", label.split("-")[0].replace("Non", "Non"))
            k0 = openpyxl.utils.column_index_from_string(c0)
            for k in range(k0, k0 + 3):
                col = get_column_letter(k)
                period, stage = rbi_period(ws[f"{col}5"].value)
                for r, geo, _ in states:
                    v = parse_number(ws[f"{col}{r}"].value)
                    if v is None:
                        continue
                    rows.append(
                        _row(
                            series_id=f"st{table.split()[-1]}.{code}_share.{geo.key}.{stage.lower()}",
                            source_id=RBI_SF,
                            table_id=table,
                            item_code=f"{code}_share",
                            item_label=f"{label}: share of all States and UTs",
                            geo=geo,
                            period=period,
                            period_type="fy",
                            value=v,
                            unit="percent",
                            stage=stage,
                            vintage=SF_VINTAGE,
                            prov=pid,
                            stock_flow="n/a",
                            extra_dim=f"stage={stage.lower()}",
                        )
                    )
    # Statement 36: subsidies, 2018-19 to 2025-26 BE
    raw = ctx.raw(RBI_SF, "sf2526_st36.xlsx")
    ws = openpyxl.load_workbook(raw.path, data_only=True).worksheets[0]
    expect(ws, "B2", "Statement 36: Subsidies")
    expect(ws, "B3", "Crore")
    cols = [get_column_letter(k) for k in range(3, 11)]
    states = _state_rows(ws, 6)
    # The 'All States and UTs' row sums only the States that report: those printing '-' are left out,
    # and the set changes by year (2023-24 omits Maharashtra, Andhra Pradesh, ...), so the total is not
    # comparable across years (issue state_fiscal-19). Checked here and written into the provenance.
    dashes = []
    for col in cols:
        period, stage = rbi_period(ws[f"{col}4"].value)
        tot = [parse_number(ws[f"{col}{r}"].value) for r, geo, _ in states if geo.geography == "IN"]
        parts = [(geo.geography, parse_number(ws[f"{col}{r}"].value)) for r, geo, _ in states if geo.geography != "IN"]
        if len(tot) != 1 or tot[0] is None:
            raise ValueError(f"Statement 36 {col}: no single All States and UTs total")
        got = sum(x for _, x in parts if x is not None)
        if abs(got - tot[0]) > 1.0:
            raise ValueError(f"Statement 36 {col}: total {tot[0]} != sum of reporting States {got}")
        miss = sorted(g for g, x in parts if x is None)
        dashes.append(f"{period}{'' if stage == 'Actuals' else ' ' + stage}: {', '.join(miss) if miss else 'none'}")
    pid = _prov(
        ctx,
        raw,
        "Statement 36",
        f"sheet '{ws.title}', rows {states[0][0]}-{states[-1][0]}, cols C:J (2018-19 to 2025-26 BE)",
        "Rs Crore",
        SF_VINTAGE,
        SF_RELEASE,
        notes="PARTIAL TOTAL: the 'All States and UTs' row equals the sum of the States that report (checked to Rs 1 "
        "crore); States printing '-' are left out, so the total understates and is not comparable across years. "
        + JK_2019_20
        + "States printing '-': " + "; ".join(dashes) + ".",
    )
    for col in cols:
        period, stage = rbi_period(ws[f"{col}4"].value)
        for r, geo, _ in states:
            v = parse_number(ws[f"{col}{r}"].value)
            if v is None:
                continue
            rows.append(
                _row(
                    series_id=f"st36.subsidies.{geo.key}.{stage.lower()}",
                    source_id=RBI_SF,
                    table_id="Statement 36",
                    item_code="subsidies",
                    item_label="Subsidies",
                    geo=geo,
                    period=period,
                    period_type="fy",
                    value=v,
                    unit="INR_crore",
                    stage=stage,
                    vintage=SF_VINTAGE,
                    prov=pid,
                    extra_dim=f"stage={stage.lower()}",
                )
            )
    return Dataset(
        f"{UNIT}_rbi_sf_statements",
        pl.DataFrame(rows, infer_schema_length=None),
        "RBI State Finances 2025-26 Statements 13, 14, 15, 17, 36 by State/UT (2023-24 Accounts, 2024-25 RE, 2025-26 BE; St 36 from 2018-19)",
    )


# ---------------------------------------------------------------------------------------------
# All-States appendix tables (time series)
# ---------------------------------------------------------------------------------------------


def _year_rows(ws: Any, first: int, cols: list[str], labels: dict[str, str], table: str) -> list[tuple[int, str, str, dict[str, Any]]]:
    """[(row, period, stage, {col: cell})] for tables with one row per year (skips averages and the
    per-cent-of-GDP rows printed under each year)."""
    out = []
    for r in range(first, ws.max_row + 1):
        y = ws.cell(r, 2).value
        if y is None:
            continue
        t = norm(y)
        if "avg" in t or not re.match(r"^\d{4}\s*-\s*\d{2}", t):
            continue  # 5-year averages and the note lines under the table
        period, stage = rbi_period(y)
        out.append((r, period, stage, {c: ws[f"{c}{r}"].value for c in cols}))
    return out


# Appendix Table 2, 2023-24 (Accounts): rows III (gross loans) and V (repayments and interest to the
# Centre) print exactly the 2022-23 values, and IV and VI are computed from them. Statement 17 and
# Appendices III/IV of the same edition give different, mutually consistent 2023-24 figures
# (gross transfers 18,00,210 = share 11,29,761 + grants 5,27,931 + loans 1,42,518), so these cells
# are not ingested.
AT2_STALE_2023_24 = {"iii", "iv", "v", "v.a", "v.b", "vi"}


def build_app_tables(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    geo = Geo("IN", "state_group=all_states_uts")

    def add(pid, table, tcode, code, label, period, stage, v, *, stock_flow="flow", ptype="fy"):
        rows.append(
            _row(
                series_id=f"{tcode}.{code}.{stage.lower()}",
                source_id=RBI_SF,
                table_id=table,
                item_code=code,
                item_label=label,
                geo=geo,
                period=period,
                period_type=ptype,
                value=v,
                unit="INR_crore",
                stage=stage,
                vintage=SF_VINTAGE,
                prov=pid,
                stock_flow=stock_flow,
                extra_dim=f"stage={stage.lower()}",
            )
        )

    def dl_py_note(wb_: Any, table: str) -> str:
        """The coverage break every appendix table notes: Delhi and Puducherry are included from 2017-18."""
        needle = "data from 2017-18 onwards include delhi and puducherry also"
        if not any(isinstance(c, str) and needle in norm(c) for w in wb_.worksheets for r in w.iter_rows(values_only=True) for c in r):
            raise ValueError(f"{table}: the Delhi/Puducherry coverage note is gone")
        return (
            "COVERAGE BREAK: data from 2017-18 onwards include Delhi and Puducherry (sheet note); earlier years are "
            "States (and J&K) only, so splice time series at 2017-18."
        )

    # Appendix Tables 1, 3, 9: one row per year, one column per item
    for name, table, tcode, title, hdr_row, first in (
        ("sf2526_app_t01.xlsx", "Appendix Table 1", "at1", "Appendix Table 1: Major Deficit Indicators", 4, 6),
        ("sf2526_app_t03.xlsx", "Appendix Table 3", "at3", "Appendix Table 3: Development and Non-Development Expenditure", 4, 6),
        ("sf2526_app_t09.xlsx", "Appendix Table 9", "at9", "Appendix Table 9: Financing of Gross Fiscal Deficit", 4, 6),
    ):
        raw = ctx.raw(RBI_SF, name)
        wb = openpyxl.load_workbook(raw.path, data_only=True)
        ws = wb.worksheets[0]
        dlpy = dl_py_note(wb, table)
        expect(ws, "B2", title)
        expect(ws, "B3", "Crore")
        expect(ws, f"B{hdr_row}", "Year")
        heads = {
            get_column_letter(k): clean_label(ws.cell(hdr_row, k).value)
            for k in range(3, ws.max_column + 1)
            if ws.cell(hdr_row, k).value not in (None, "")
        }
        yrs = _year_rows(ws, first, list(heads), heads, table)
        pid = _prov(
            ctx,
            raw,
            table,
            f"sheet '{ws.title}', year rows {yrs[0][0]}-{yrs[-1][0]} (col B), item cols {min(heads)}:{max(heads)}; "
            "the per-cent-of-GDP rows under each year and the 5-year averages are not ingested",
            "Rs Crore",
            SF_VINTAGE,
            SF_RELEASE,
            notes=("Appendix Table 1 note: a negative sign indicates a surplus in the deficit indicators. " if tcode == "at1" else "")
            + dlpy,
        )
        for r, period, stage, cells in yrs:
            for col, head in heads.items():
                v = parse_number(cells[col])
                if v is None:
                    continue
                code = _code(head)
                add(pid, table, tcode, code, head, period, stage, v)

    # Appendix Table 2: items in rows, years in columns, three sheets
    raw = ctx.raw(RBI_SF, "sf2526_app_t02.xlsx")
    wb = openpyxl.load_workbook(raw.path, data_only=True)
    dlpy = dl_py_note(wb, "Appendix Table 2")
    locs = []
    for ws in wb.worksheets:
        expect(ws, "B2", "Appendix Table 2: Devolution and Transfer of Resources from the Centre")
        expect(ws, "B3", "Crore")
        cols = {
            get_column_letter(k): ws.cell(4, k).value
            for k in range(3, ws.max_column + 1)
            if ws.cell(4, k).value not in (None, "")
        }
        # The fourth year column of the last sheet is printed '2023-24 (Budget Estimates)' but sits
        # where every other appendix table has 2024-25 (BE); its label cannot be trusted, so the
        # column is skipped (issues file state_fiscal-6).
        cols = {c: h for c, h in cols.items() if norm(h) != "2023-24 (budget estimates)"}
        body = []
        for r in range(6, ws.max_row + 1):
            lab = ws.cell(r, 2).value
            if lab is None or _is_note(clean_label(lab)) or norm(lab).startswith(("*:", "note", "source")):
                continue
            body.append((r, clean_label(lab), {c: ws[f"{c}{r}"].value for c in cols}))
        items = parse_item_rows(body, continuations=CONTINUATIONS, where=f"App T2 {ws.title}")
        locs.append(f"'{ws.title}' rows {body[0][0]}-{body[-1][0]} cols {min(cols)}:{max(cols)}")
        pid = _prov(
            ctx,
            raw,
            "Appendix Table 2",
            f"sheet {locs[-1]}; rows matched by printed label/numbering. Last sheet: column G "
            "(printed '2023-24 (Budget Estimates)') skipped; 2023-24 (Accounts) rows III-VI skipped (stale)",
            "Rs Crore",
            SF_VINTAGE,
            SF_RELEASE,
            notes=dlpy,
        )
        for it in items:
            for col, head in cols.items():
                v = parse_number(it.cells.get(col))
                if v is None:
                    continue
                period, stage = rbi_period(head)
                if (period, stage) == ("2023-24", "Actuals") and it.path in AT2_STALE_2023_24:
                    continue  # repeats 2022-23; contradicts St 17 and App III/IV (issue state_fiscal-5)
                add(pid, "Appendix Table 2", "at2", it.code, it.label, period, stage, v)

    # Appendix Table 11: outstanding liabilities at end-March (stocks)
    raw = ctx.raw(RBI_SF, "sf2526_app_t11.xlsx")
    wb = openpyxl.load_workbook(raw.path, data_only=True)
    ws = wb.worksheets[0]
    dlpy = dl_py_note(wb, "Appendix Table 11")
    expect(ws, "B2", "Appendix Table 11: Composition of Outstanding Liabilities")
    expect(ws, "C3", "As at end-March")
    expect(ws, "B4", "Crore")
    expect(ws, "B5", "Year")
    heads = {
        get_column_letter(k): clean_label(ws.cell(5, k).value)
        for k in range(3, ws.max_column + 1)
        if ws.cell(5, k).value not in (None, "")
    }
    yrs = []
    for r in range(7, ws.max_row + 1):
        y = ws.cell(r, 2).value
        if y is None or norm(y).startswith(("re", "note", "2.", "source")):
            continue
        t = norm(y)
        stage = "RE" if t.endswith("re") else "BE" if t.endswith("be") else "Actuals"
        year = int(t.split()[0])
        yrs.append((r, f"{year}-03-31", stage))
    pid = _prov(
        ctx,
        raw,
        "Appendix Table 11",
        f"sheet '{ws.title}', rows {yrs[0][0]}-{yrs[-1][0]} (end-March of the printed year), cols "
        f"{min(heads)}:{max(heads)}",
        "Rs Crore",
        SF_VINTAGE,
        SF_RELEASE,
        notes=dlpy,
    )
    for r, date, stage in yrs:
        for col, head in heads.items():
            v = parse_number(ws[f"{col}{r}"].value)
            if v is None:
                continue
            add(pid, "Appendix Table 11", "at11", _code(head), head, date, stage, v, stock_flow="stock", ptype="date")
    return Dataset(
        f"{UNIT}_rbi_sf_app_tables",
        pl.DataFrame(rows, infer_schema_length=None),
        "RBI State Finances 2025-26 Appendix Tables 1, 2, 3, 9, 11: All States and UTs time series (Rs crore)",
    )


def _code(head: str) -> str:
    from pipeline.core.units import slug

    return slug(head.replace("=", " eq "))[:60].rstrip("_")


# ---------------------------------------------------------------------------------------------
# Municipal corporations and village panchayats
# ---------------------------------------------------------------------------------------------


def build_municipal(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    for name, table, title, code in (
        ("muni_st01.xlsx", "Statement 1", "Statement 1: Revenue Receipts of Municipal Corporations", "revenue_receipts"),
        ("muni_st04.xlsx", "Statement 4", "Statement 4: Revenue Expenditure of Municipal Corporations", "revenue_expenditure"),
        ("muni_st08.xlsx", "Statement 8", "Statement 8: Capital Outlay of Municipal Corporations", "capital_outlay"),
    ):
        raw = ctx.raw(RBI_MUNI, name)
        ws = openpyxl.load_workbook(raw.path, data_only=True).worksheets[0]
        expect(ws, "B2", title)
        expect(ws, "B3", "lakh")
        expect(ws, "B4", "State")
        expect(ws, "H4", "Per cent of GSDP")
        level_cols = [get_column_letter(k) for k in range(3, 8)]
        pct_cols = [get_column_letter(k) for k in range(8, ws.max_column + 1)]
        heads = {c: ws[f"{c}4"].value for c in level_cols}
        pct_heads = {c: ws[f"{c}5"].value for c in pct_cols if ws[f"{c}5"].value not in (None, "")}
        body = []
        for r in range(6, ws.max_row + 1):
            v = ws.cell(r, 2).value
            # skip blanks, the column-number row ('1', '2', ...) and notes; State rows start at row 7 or 8
            if v is None or isinstance(v, (int, float)) or norm(v).startswith(("note", "source")):
                continue
            geo = Geo("IN", "state_group=all_states_uts") if norm(v) == "total" else state_geo(v)
            body.append((r, geo))
        label = title.split(": ", 1)[1].replace(" – State-wise", "")
        pid = _prov(
            ctx,
            raw,
            table,
            f"sheet '{ws.title}', rows {body[0][0]}-{body[-1][0]} (States; 'Total' = all reporting States), level cols "
            f"C:G ({', '.join(str(h) for h in heads.values())})",
            "Rs lakh",
            MUNI_VINTAGE,
            MUNI_RELEASE,
            notes="Municipal corporations only (not all urban local bodies). '-' = not available. "
            + JK_2019_20.strip(),
        )
        pid_pct = _prov(
            ctx,
            raw,
            table,
            f"sheet '{ws.title}', rows {body[0][0]}-{body[-1][0]}, per-cent-of-GSDP cols {pct_cols[0]}:{pct_cols[-1]} "
            f"(years in row 5: {', '.join(str(h) for h in pct_heads.values())})",
            "Per cent of GSDP",
            MUNI_VINTAGE,
            MUNI_RELEASE,
            notes="Municipal corporations only (not all urban local bodies); per cent of GSDP as printed. "
            "'-' = not available. " + JK_2019_20.strip(),
        )
        for r, geo in body:
            for col, head in heads.items():
                period, stage = rbi_period(head)
                v = parse_number(ws[f"{col}{r}"].value)
                if v is None:
                    continue
                rows.append(
                    _row(
                        series_id=f"m{table.split()[-1]}.{code}.{geo.key}.{stage.lower()}",
                        source_id=RBI_MUNI,
                        table_id=table,
                        item_code=code,
                        item_label=label,
                        geo=geo,
                        period=period,
                        period_type="fy",
                        value=to_inr_crore(v, "INR_lakh"),
                        unit="INR_crore",
                        stage=stage,
                        vintage=MUNI_VINTAGE,
                        prov=pid,
                        institution="gg_local_municipal_corp",
                        extra_dim=f"stage={stage.lower()}",
                    )
                )
            for col, head in pct_heads.items():
                period, stage = rbi_period(head)
                v = parse_number(ws[f"{col}{r}"].value)
                if v is None:
                    continue
                rows.append(
                    _row(
                        series_id=f"m{table.split()[-1]}.{code}_pct_gsdp.{geo.key}.{stage.lower()}",
                        source_id=RBI_MUNI,
                        table_id=table,
                        item_code=f"{code}_pct_gsdp",
                        item_label=f"{label} (per cent of GSDP)",
                        geo=geo,
                        period=period,
                        period_type="fy",
                        value=v,
                        unit="percent",
                        stage=stage,
                        vintage=MUNI_VINTAGE,
                        prov=pid_pct,
                        stock_flow="n/a",
                        institution="gg_local_municipal_corp",
                        extra_dim=f"stage={stage.lower()}",
                    )
                )
    return Dataset(
        f"{UNIT}_rbi_municipal",
        pl.DataFrame(rows, infer_schema_length=None),
        "RBI Report on Municipal Finances (Nov 2024) Statements 1, 4, 8: municipal corporations by State, 2019-20 to 2023-24 BE",
    )


def build_pri(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    for name, table, title, side in (
        ("pri_app1_part7.xlsx", "Appendix I", "Appendix I : Revenue Receipts of Village Panchayats", "receipts"),
        ("pri_app2_part7.xlsx", "Appendix II", "Appendix II : Revenue Expenditure of Village Panchayats", "payments"),
    ):
        raw = ctx.raw(RBI_PRI, name)
        blocks = _appendix_tables(raw, title)
        key = next((k for k in blocks if k.startswith("all states")), None)
        if key is None:
            raise ValueError(f"{name}: no All States/UTs block ({sorted(blocks)})")
        caption, items_raw, cols, sheets = blocks[key]
        if "per panchayat" not in norm(caption):
            raise ValueError(f"{name}: expected '(₹ per Panchayat)', found {caption!r}")
        items = parse_item_rows(
            [(r, lab, cells) for r, _, lab, cells in items_raw], continuations=CONTINUATIONS, where=f"{name} {key}"
        )
        pid = ctx.prov(
            raw=raw,
            table_id=table,
            locator=f"sheet(s) {sheets}, block '{key}', rows {items_raw[0][0]}-{items_raw[-1][0]}, cols "
            f"{', '.join(f'{c}={h}' for c, h in cols.items())}",
            unit_as_published="Rs per village panchayat (average)",
            conversion="none",
            price_basis="current",
            vintage=PRI_VINTAGE,
            release=PRI_RELEASE,
            notes="Averages per village panchayat, not totals; 'All States/UTs' covers 26 States/UTs (sheet note). "
            "Estimates based on eGramSwaraj data.",
        )
        geo = Geo("IN", "state_group=all_states_uts_26", institution="gg_local_village_panchayat")
        for it in items:
            for col, head in cols.items():
                period, stage = rbi_period(head)
                v = parse_number(it.cells.get(col))
                if v is None:
                    continue
                rows.append(
                    _row(
                        series_id=f"pri_{'app1' if table == 'Appendix I' else 'app2'}.{it.code}",
                        source_id=RBI_PRI,
                        table_id=table,
                        item_code=it.code,
                        item_label=it.label,
                        geo=geo,
                        period=period,
                        period_type="fy",
                        value=v,
                        unit="INR",
                        stage="Actuals",
                        vintage=PRI_VINTAGE,
                        prov=pid,
                        side=side,
                    )
                )
    rows += build_pri_chapter(ctx)
    return Dataset(
        f"{UNIT}_rbi_pri",
        pl.DataFrame(rows, infer_schema_length=None),
        "RBI Finances of PRIs (Jan 2024): Appendices I-II per-panchayat averages and Chapter II balanced-panel aggregates (Rs crore), 2020-21 to 2022-23",
    )


# Chapter II of the PRI report: aggregate tables for the balanced panel of village panchayats.
PRI_CH2_LINES = {  # (page, table heading, label regex) -> (code, printed label, table, occurrence)
    "rr": (3, "Table II.3: Revenue Receipts", r"Revenue Receipts", "Revenue Receipts"),
    "own_tax": (3, "Table II.3: Revenue Receipts", r"A\. Own Tax Revenue", "A. Own Tax Revenue"),
    "own_non_tax": (3, "Table II.3: Revenue Receipts", r"B\. Own Non-Tax Revenue", "B. Own Non-Tax Revenue"),
    "grants": (3, "Table II.3: Revenue Receipts", r"C\. Grants-in-aid", "C. Grants-in-aid"),
    "grants_centre": (3, "Table II.3: Revenue Receipts", r"\(i\) Grants from Central", "(i) Grants from Central Government"),
    "grants_state": (3, "Table II.3: Revenue Receipts", r"\(ii\) Grants from State Government", "(ii) Grants from State Government"),
    "rev_exp": (5, "Table II.5: Revenue Expenditure", r"Revenue Expenditure", "Revenue Expenditure"),
    "rev_exp_pr_programmes": (5, "Table II.5: Revenue Expenditure", r"Panchayati Raj Programmes", "Panchayati Raj Programmes"),
    "rev_exp_water_sanitation": (5, "Table II.5: Revenue Expenditure", r"Water Supply and Sanitation", "Water Supply and Sanitation"),
}


def build_pri_chapter(ctx: BuildContext) -> list[dict[str, Any]]:
    """Rows from Chapter II tables II.1, II.2 (counts), II.3 and II.5 (Rs crore, balanced panel)."""
    import pdfplumber

    raw = ctx.raw(RBI_PRI, "pri_ch2.pdf")
    with pdfplumber.open(raw.path) as pdf:
        pages = {i + 1: (p.extract_text() or "") for i, p in enumerate(pdf.pages)}
    rows: list[dict[str, Any]] = []
    geo = Geo("IN", "state_group=balanced_panel_26", institution="gg_local_village_panchayat")
    pid = ctx.prov(
        raw=raw,
        table_id="Chapter II Tables II.3 and II.5",
        locator="PDF p.3 (printed 12) Table II.3 'Revenue Receipts (₹ crore)' first panel; p.5 (printed 14) Table II.5 "
        "'Revenue Expenditure (₹ crore)' first panel; columns 2020-21, 2021-22, 2022-23",
        unit_as_published="Rs crore",
        price_basis="current",
        vintage=PRI_VINTAGE,
        release=PRI_RELEASE,
        notes="Aggregates of the balanced panel of village panchayats reporting on eGramSwaraj (80.8% of village "
        "panchayats for receipts, 69.1% for expenditure; Table II.2), not all-India totals.",
    )
    for code, (page, heading, rx, label) in PRI_CH2_LINES.items():
        text = pages[page]
        if heading not in text or "crore" not in text:
            raise ValueError(f"PRI chapter II p.{page}: {heading!r} (Rs crore) not found")
        m = re.search(rx + r"\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)", text)
        if not m:
            raise ValueError(f"PRI chapter II p.{page}: line {label!r} with three numbers not found")
        for period, cell in zip(("2020-21", "2021-22", "2022-23"), m.groups(), strict=True):
            rows.append(
                _row(
                    series_id=f"pri_ch2.{code}",
                    source_id=RBI_PRI,
                    table_id=heading.split(":")[0],
                    item_code=code,
                    item_label=label,
                    geo=geo,
                    period=period,
                    period_type="fy",
                    value=parse_number(cell),
                    unit="INR_crore",
                    stage="Actuals",
                    vintage=PRI_VINTAGE,
                    prov=pid,
                    side="receipts" if code.startswith(("rr", "own", "grants")) else "payments",
                )
            )
    # counts: Table II.1 (all village panchayats) and Table II.2 (balanced panel)
    p1, p2 = pages[1], pages[2]
    m1 = re.search(r"Number of Village Panchayats ([\d,]+)", p1)
    m2 = re.search(r"^Total (\d+) (\d+) [\d.]+ (\d+) [\d.]+$", p2, re.M)
    if "As of Dec. 31, 2022" not in p1 or not m1 or "Table II.2" not in p2 or not m2:
        raise ValueError("PRI chapter II: Table II.1/II.2 counts not found")
    pid_n = ctx.prov(
        raw=raw,
        table_id="Chapter II Tables II.1 and II.2",
        locator="PDF p.1 Table II.1 row 'Number of Village Panchayats' (as of 31 Dec 2022); p.2 Table II.2 row 'Total'",
        unit_as_published="count",
        price_basis="n/a",
        vintage=PRI_VINTAGE,
        release=PRI_RELEASE,
    )
    allvp = Geo("IN", None, institution="gg_local_village_panchayat")
    rows.append(
        _row(series_id="pri_ch2.n_village_panchayats", source_id=RBI_PRI, table_id="Table II.1",
             item_code="n_village_panchayats", item_label="Number of Village Panchayats", geo=allvp,
             period="2022-12-31", period_type="date", value=parse_number(m1.group(1)), unit="count",
             stage="Actuals", vintage=PRI_VINTAGE, prov=pid_n, stock_flow="stock")
    )  # fmt: skip
    for code, label, cell in (
        ("n_vp_total_table_ii2", "Total No. of Village Panchayats (Table II.2 States)", m2.group(1)),
        ("n_vp_panel_receipts", "No. of Panchayats in balanced panel: Revenue Receipts", m2.group(2)),
        ("n_vp_panel_expenditure", "No. of Panchayats in balanced panel: Revenue Expenditure", m2.group(3)),
    ):
        rows.append(
            _row(series_id=f"pri_ch2.{code}", source_id=RBI_PRI, table_id="Table II.2", item_code=code,
                 item_label=label, geo=geo, period="2022-23", period_type="fy", value=parse_number(cell),
                 unit="count", stage="Actuals", vintage=PRI_VINTAGE, prov=pid_n, stock_flow="n/a")
        )  # fmt: skip
    for r in rows:
        if r["unit"] == "count":
            r["price_basis"] = "n/a"
    return rows
