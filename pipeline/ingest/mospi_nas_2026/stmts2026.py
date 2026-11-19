"""NAS 2026 (new base 2022-23) statements other than 1.1 and 8.17.1 (those two are hand-mapped in
__init__.py). Each statement is described by a `Cfg`: where its labels, years, price panels and
column variables are, and what its rows are (line items, or industries/institutions as a dim).
Header texts are asserted, and rows are checked against the frozen spec `spec_nas2026.json`
(labels, header/data role, blank-cell pattern), so a changed statement fails loudly.

One dataset per statement: `mospi_nas_2026_s<stmt>` (e.g. mospi_nas_2026_s7_1a).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import openpyxl
import polars as pl
from openpyxl.utils import column_index_from_string, get_column_letter

from pipeline.core import geo
from pipeline.core.unit import BuildContext, Dataset, RawFile
from pipeline.ingest.mospi_nas_2026 import grid
from pipeline.ingest.mospi_nas_2026.codes import industry_code, institution_code, is_industry, is_institution, var_code

SPEC_FILE = "spec_nas2026.json"
UNIT = "mospi_nas_2026"
SRC = "mospi_nas_2026_publication"
VINTAGE = "2026-08-31"
RELEASE = "National Accounts Statistics 2026 (NSO, MoSPI; released 31 Aug 2026)"
BASE_YEAR = "2022-23"
STAGES = {"2022-23": "Final", "2023-24": "Final", "2024-25": "FRE", "2025-26": "PE"}
CUR, CON = "current", "constant_2022_23"

PCT_ROW = re.compile(r"\bratio\b|\bpercentage\b|\bshare\b", re.I)


@dataclass(frozen=True)
class Panel:
    cols: str  # 'C:E'
    basis: str  # CUR | CON
    check: str | None  # cell whose text must name the price basis ('C4'); None = checked via title


@dataclass(frozen=True)
class Cfg:
    stmt: str
    title: str  # text expected in the title cell
    label: str  # English label column
    year_row: int
    panels: tuple[Panel, ...]
    first: int  # first data row
    title_cell: str = "B2"
    sheet: str | None = None  # default: the only / first sheet
    kind: str = "level"  # level | pct | growth | index
    var_row: int | None = None  # row of column variables (two-level headers)
    rows: str = "item"  # item | industry | institution: what a row is
    section: str | None = None  # None | industry | institution: header rows set this dim
    measure: str | None = None  # item code when rows are a dim and there is no column variable
    institution: str | None = None  # statement-wide institution dim
    unit_cell: str | None = None  # cell that must mention 'crore'
    extra: tuple[str, ...] = ()  # extra label columns kept (e.g. NIC code)
    stock: bool = False  # stocks at end-March (7.4): year header is a calendar year
    period_fy: str | None = None  # fixed period (4.2: one sheet per year)
    quarterly: bool = False  # 8.18: var row holds Q1..Q4
    last: int | None = None  # explicit last data row (8.18: stop before the growth-rate block)
    dataset: str | None = None
    key: str | None = None  # spec key (default stmt)
    sno: str | None = None  # serial-number column (default: the column right of the label; '' = none)
    notes: str = ""

    @property
    def serial_cols(self) -> tuple[str, ...]:
        if self.label == "A" or self.sno == "":
            return ()
        nxt = self.sno or get_column_letter(column_index_from_string(self.label) + 1)
        return (nxt, "A")

    @property
    def tbl(self) -> str:
        return "s" + self.stmt.lower().replace(".", "_")

    @property
    def spec_key(self) -> str:
        return self.key or self.stmt


def _p(cols: str, basis: str, check: str | None) -> Panel:
    return Panel(cols, basis, check)


CUR_CE = (_p("C:E", CUR, "C4"),)
TWO_CH = (_p("C:E", CUR, "C4"), _p("F:H", CON, "F4"))

CFGS: tuple[Cfg, ...] = (
    Cfg("1.2", "STATEMENT 1.2: PER CAPITA INCOME", "F", 6, (_p("C:E", CUR, None),), 8, kind="special_1_2"),
    Cfg("1.4", "STATEMENT 1.4: PRICE AND QUANTUM INDICES", "F", 4, (_p("C:E", "n/a", None),), 6, kind="index"),
    Cfg("1.5", "STATEMENT 1.5: OUTPUT BY ECONOMIC ACTIVITY", "I", 6, TWO_CH, 8, section="industry", unit_cell="H5"),
    Cfg("1.6", "STATEMENT 1.6: GROSS VALUE ADDED BY ECONOMIC ACTIVITY", "I", 6, TWO_CH, 8, rows="industry",
        measure="gva", unit_cell="H5"),
    Cfg("1.6A", "STATEMENT 1.6A: PERCENTAGE SHARE OF GROSS VALUE ADDED", "I", 5, TWO_CH, 7, rows="industry",
        measure="gva_share", kind="pct"),
    Cfg("1.6B", "STATEMENT 1.6 B: PERCENTAGE CHANGE IN GROSS VALUE ADDED", "G", 5,
        (_p("C:D", CUR, "C4"), _p("E:F", CON, "E4")), 7, rows="industry", measure="gva_growth", kind="growth"),
    Cfg("1.7", "STATEMENT 1.7: NET VALUE ADDED (NVA) BY ECONOMIC ACTIVITY", "I", 6, TWO_CH, 8, rows="industry",
        measure="nva", unit_cell="H5"),
    Cfg("1.8", "STATEMENT 1.8: CONSUMPTION OF FIXED CAPITAL (CFC) BY ECONOMIC ACTIVITY", "I", 6, TWO_CH, 8,
        rows="industry", measure="cfc", unit_cell="H5"),
    Cfg("1.9", "STATEMENT 1.9: FINANCES FOR GROSS CAPITAL FORMATION", "F", 6, CUR_CE, 8, unit_cell="E5"),
    Cfg("1.10", "STATEMENT 1.10: GROSS CAPITAL FORMATION BY INDUSTRY OF USE", "I", 6, TWO_CH, 8, rows="industry",
        measure="gcf", unit_cell="H5"),
    Cfg("1.11", "STATEMENT 1.11: GROSS FIXED CAPITAL FORMATION BY ASSET & INSTITUTIONAL SECTOR", "I", 6, TWO_CH, 8,
        unit_cell="H5"),
    Cfg("1.12", "STATEMENT 1.12: PRIVATE FINAL CONSUMPTION EXPENDITURE", "I", 6, TWO_CH, 8, unit_cell="H5"),
    Cfg("1.13", "STATEMENT 1.13: FISIM BY USES", "F", 6, CUR_CE, 8, unit_cell="E5"),
    Cfg("1.14", "STATEMENT 1.14: INSTITUTIONAL SECTORAL ACCOUNTS", "F", 6, CUR_CE, 8, section="institution",
        unit_cell="E5"),
    Cfg("4.1", "STATEMENT 4.1: VALUE ADDED BY CENTRAL AND STATE GOVERNMENTS", "I", 6, TWO_CH, 8, unit_cell="H5"),
    *(
        Cfg("4.2", "STATEMENT 4.2: EXPENDITURE OF GENERAL GOVERNMENT CLASSIFIED BY FUNCTION", "Y", 0,
            (_p("C:X", CUR, None),), 8, sheet=sh, var_row=6, period_fy=fy, unit_cell="X4", key=f"4.2/{fy}")
        for sh, fy in (("4.2(2022-23)", "2022-23"), ("4.2(2023-24) ", "2023-24"), ("4.2(2024-25)", "2024-25"))
    ),
    Cfg("5.1", "STATEMENT 5.1: PRIVATE FINAL CONSUMPTION EXPENDITURE CLASSIFIED BY ITEM", "I", 6, TWO_CH, 8,
        unit_cell="H5"),
    Cfg("5.2", "STATEMENT 5.2: INDIVIDUAL CONSUMPTION EXPENDITURE BY HOUSEHOLDS AND GENERAL GOVERNMENT", "U", 5,
        (_p("C:K", CUR, "C4"), _p("L:T", CON, "L4")), 9, var_row=7),
    Cfg("5.3", "STATEMENT 5.3: FINANCIAL ASSESTS AND LIABILITIES OF HOUSEHOLD SECTOR", "F", 6, CUR_CE, 8,
        institution="households_npish", unit_cell="E5"),
    Cfg("6.1", "STATEMENT 6.1: DETAILED EXTERNAL TRANSACTIONS ACCOUNTS", "F", 6, CUR_CE, 8, unit_cell="E5"),
    Cfg("6.2", "STATEMENT 6.2: SELECTED AGGREGATES OF EXTERNAL TRANSACTIONS", "F", 7, (_p("C:E", CON, "E5"),), 9,
        unit_cell="E6"),
    *(
        Cfg(s, f"STATEMENT {s}: OUTPUT, VALUE ADDED, CE, OS", "X", 4, (_p("C:W", CUR, None),), 7, var_row=6,
            rows="industry", institution=inst)
        for s, inst in (("7.1", None), ("7.1A", "public_sector"), ("7.1B", "private_corporate"), ("7.1C", "households_npish"),
                        ("8.15.1", "gg"), ("8.15.2", "public_departmental_enterprises"),
                        ("8.15.3", "public_non_departmental_enterprises"))
    ),
    *(
        Cfg(s, f"STATEMENT {s}: GCF, GFCF, CIS, CFC BY INDUSTRY", "AA", 5, (_p("C:N", CUR, "C4"), _p("O:Z", CON, "O4")),
            8, var_row=7, rows="industry", institution=inst)
        for s, inst in (("7.2", None), ("7.2A", "public_sector"), ("7.2B", "private_corporate"), ("7.2C", "households_npish"))
    ),
    *(
        Cfg(s, f"STATEMENT {s}: GFCF BY TYPE OF ASSET, BY INDUSTRY", "R", 4, (_p("C:Q", CUR, None),), 7, var_row=6,
            rows="industry", institution=inst)
        for s, inst in (("7.3", None), ("7.3A", "public_sector"), ("7.3B", "private_corporate"), ("7.3C", "households_npish"))
    ),
    *(
        Cfg(s, f"STATEMENT {s}: NET CAPITAL STOCK BY INDUSTRY OF USE", "L", 4, (_p("C:K", CUR, None),), 7, var_row=6,
            rows="industry", institution=inst, stock=True)
        for s, inst in (("7.4", None), ("7.4A", "public_sector"), ("7.4B", "private_corporate"), ("7.4C", "households_npish"))
    ),
    *(
        Cfg(s, t, "I", 6, TWO_CH, 8, unit_cell="H5")
        for s, t in (
            ("8.1.1", "STATEMENT 8.1.1: OUTPUT & VALUE ADDED FROM CROP SECTOR"),
            ("8.1.2", "STATEMENT 8.1.2: CROP-WISE VALUE OF OUTPUT"),
            ("8.2", "STATEMENT 8.2: OUTPUT & VALUE ADDED FROM LIVESTOCK SECTOR"),
            ("8.3", "STATEMENT 8.3: OUTPUT & VALUE ADDED FROM FORESTRY & LOGGING"),
            ("8.4", "STATEMENT 8.4: OUTPUT & VALUE ADDED FROM FISHING & AQUACULTURE"),
            ("8.5", "STATEMENT 8.5: OUTPUT & VALUE ADDED FROM MINING & QUARRYING"),
            ("8.7", "STATEMENT 8.7: OUTPUT & VALUE ADDED FROM ELECTRICITY"),
            ("8.10", "STATEMENT 8.10: OUTPUT & VALUE ADDED FROM TRANSPORT SERVICES"),
            ("8.11", "STATEMENT 8.11: OUTPUT & VALUE ADDED FROM STORAGE"),
            ("8.12", "STATEMENT 8.12: VALUE ADDED FROM FINANCIAL SERVICES"),
            ("8.13", "STATEMENT 8.13: OUTPUT & VALUE ADDED FROM REAL ESTATE"),
            ("8.14", "STATEMENT 8.14: OUTPUT & VALUE ADDED FROM OTHER SERVICES"),
        )
    ),
    Cfg("8.8", "STATEMENT 8.8: OUTPUT AND VALUE ADDED FROM CONSTRUCTION", "I", 7,
        (_p("C:E", CUR, "C5"), _p("F:H", CON, "F5")), 9, title_cell="B3", unit_cell="H6"),
    Cfg("8.9", "STATEMENT 8.9: OUTPUT & VALUE ADDED FROM TRADE", "I", 6, TWO_CH, 8, unit_cell="F5"),
    *(
        Cfg(s, t, "J", 6, (_p("D:F", CUR, "D4"), _p("G:I", CON, "G4")), 8, extra=("K",), unit_cell="I5", sno="L")
        for s, t in (
            ("8.6.1A", "STATEMENT 8.6.1 PART I: OUTPUT FROM MANUFACTURING IN CORPORATE SECTOR"),
            ("8.6.1B", "STATEMENT 8.6.1 PART II: VALUE ADDED FROM MANUFACTURING IN CORPORATE SECTOR"),
            ("8.6.2A", "STATEMENT 8.6.2 PART I: OUTPUT FROM MANUFACTURING IN HOUSEHOLD SECTOR"),
            ("8.6.2B", "STATEMENT 8.6.2 PART II: VALUE ADDED FROM MANUFACTURING IN HOUSEHOLD SECTOR"),
        )
    ),
    Cfg("8.16", "STATEMENT 8.16: DEPRECIATION (DEP) AS PROVIDED IN THE BOOKS OF ACCOUNTS", "I", 4,
        (_p("C:H", CUR, None),), 7, var_row=6),
    Cfg("8.17.2", "PROVISIONAL ESTIMATES OF GROSS VALUE ADDED BY ECONOMIC ACTIVITY", "A", 6, (_p("B:E", CON, "A4"),),
        8, title_cell="A2", rows="industry", measure="gva", unit_cell="E5", key="8.17.2/constant"),
    Cfg("8.17.2", "PROVISIONAL ESTIMATES OF GROSS VALUE ADDED BY ECONOMIC ACTIVITY", "J", 6, (_p("K:N", CUR, "J4"),),
        8, title_cell="A2", rows="industry", measure="gva", unit_cell="N5", key="8.17.2/current"),
    Cfg("8.18.1", "QUARTERLY ESTIMATES OF GDP ALONG WITH EXPENDITURE COMPONENTS AT CONSTANT", "A", 5,
        (_p("B:Q", CON, None),), 8, title_cell="A2", var_row=7, quarterly=True, unit_cell="P4", last=31),
    Cfg("8.18.2", "QUARTERLY ESTIMATES OF GDP ALONG WITH EXPENDITURE COMPONENTS AT CURRENT", "A", 5,
        (_p("B:Q", CUR, None),), 8, title_cell="A2", var_row=7, quarterly=True, unit_cell="P4", last=31),
)


# ---------------------------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------------------------


@dataclass
class ValueCol:
    col: str
    period: str
    period_type: str
    basis: str
    var: str | None = None
    var_label: str | None = None


@dataclass
class Parsed:
    cfg: Cfg
    ws: Any
    vcols: list[ValueCol]
    rows: list[grid.Row]
    sections: list[str] = field(default_factory=list)  # section label per row ('' if none)
    serials: list[str] = field(default_factory=list)


def open_sheet(raw: RawFile, cfg: Cfg) -> Any:
    wb = openpyxl.load_workbook(raw.path, data_only=True)
    if cfg.sheet is not None:
        return wb[cfg.sheet]
    if len(wb.worksheets) != 1:
        raise ValueError(f"{cfg.stmt}: expected one sheet, found {wb.sheetnames}")
    return wb.worksheets[0]


def value_cols(ws: Any, cfg: Cfg) -> list[ValueCol]:
    grid.expect(ws, cfg.title_cell, cfg.title)
    if cfg.unit_cell:
        grid.expect(ws, cfg.unit_cell, "crore")
    out: list[ValueCol] = []
    for panel in cfg.panels:
        if panel.check:
            want = "current" if panel.basis == CUR else "constant"
            grid.expect(ws, panel.check, want)
        elif panel.basis in (CUR, CON) and cfg.kind != "special_1_2":
            want = "current" if panel.basis == CUR else "constant"
            if want not in grid.text(ws, cfg.title_cell).lower():
                raise ValueError(f"{cfg.stmt}: title does not state the price basis {want!r}")
        year = None
        for c in grid.cols(panel.cols):
            if cfg.period_fy:
                year = cfg.period_fy
            else:
                t = grid.english(grid.text(ws, f"{c}{cfg.year_row}"))
                if t:
                    year = str(int(float(t))) if cfg.stock else grid.normalize_fy(t)
                elif cfg.var_row is None:
                    raise ValueError(f"{cfg.stmt}: no year in {c}{cfg.year_row}")
            if year is None:
                raise ValueError(f"{cfg.stmt}: value column {c} precedes the first year header")
            var = var_label = None
            if cfg.var_row is not None:
                var_label = grid.english(grid.text(ws, f"{c}{cfg.var_row}"))
                if not var_label:
                    raise ValueError(f"{cfg.stmt}: no column variable in {c}{cfg.var_row}")
                var = var_code(cfg.stmt, c, var_label)
            if cfg.stock:
                period, ptype = f"{year}-03-31", "date"
            elif cfg.quarterly:
                if not re.fullmatch(r"Q[1-4]", var_label or ""):
                    raise ValueError(f"{cfg.stmt}: expected Q1..Q4 in {c}{cfg.var_row}, found {var_label!r}")
                period, ptype, var, var_label = f"{var_label} {year}", "fq", None, None
            else:
                period, ptype = year, "fy"
            out.append(ValueCol(c, period, ptype, panel.basis, var, var_label))
    return out


def parse(raw: RawFile, cfg: Cfg) -> Parsed:
    ws = open_sheet(raw, cfg)
    vcols = value_cols(ws, cfg)
    rows = grid.read_rows(
        ws, label_col=cfg.label, first=cfg.first, value_cols=[v.col for v in vcols], extra_cols=cfg.extra,
        last=cfg.last,
    )
    sections, cur = [], ""
    known = {"industry": is_industry, "institution": is_institution}.get(cfg.section or "", lambda _: True)
    for r in rows:
        if not r.has_data and known(r.label):
            cur = r.label
        sections.append(cur)
    serials = [grid.serial(ws, r.row, cfg.serial_cols) for r in rows]
    return Parsed(cfg, ws, vcols, rows, sections, serials)


def mask(row: grid.Row, vcols: list[ValueCol]) -> str:
    return "".join("0" if row.values[v.col] is None else "1" for v in vcols)


# ---------------------------------------------------------------------------------------------
# spec generation (used by make_spec.py; the build only checks against the frozen spec)
# ---------------------------------------------------------------------------------------------


def spec_rows(p: Parsed) -> list[list[str]]:
    cfg = p.cfg
    labels = [r.label for r in p.rows]
    data = [r.has_data for r in p.rows]
    if cfg.rows == "industry":
        codes = [industry_code(lab) if d else "" for lab, d in zip(labels, data, strict=True)]
    elif cfg.rows == "institution":
        codes = [institution_code(lab) if d else "" for lab, d in zip(labels, data, strict=True)]
    elif cfg.section:
        codes = [grid._short_slug(lab) if d else "" for lab, d in zip(labels, data, strict=True)]
    else:
        codes = grid.derive_codes(labels, data, p.serials, OVERRIDES.get(cfg.spec_key.split('/')[0]))
    codes = [POS_OVERRIDES.get((cfg.spec_key, i), c) for i, c in enumerate(codes)]
    return [[r.label, "d" if r.has_data else "h", c, mask(r, p.vcols)] for r, c in zip(p.rows, codes, strict=True)]


# label -> slug overrides applied before duplicate qualification (per statement)
OVERRIDES: dict[str, dict[str, str]] = {
    "1.2": {
        "at_current_prices": "current",
        "at_constant_2022_23_prices": "constant",
        "percentage_change_over_previous_year_at_constant_2022_23_pri": "growth",
    },
    "1.4": {"price_indices": "price", "quantum_indices": "quantum"},
    "1.11": {"institutional_sector_wise_gfcf_percentage_share": "pct_share"},
    "6.1": {"exports_of_goods_and_services": "exports", "imports_of_goods_and_services": "imports"},
    "6.2": {"exports_of_goods_and_services": "exports", "imports_of_goods_and_services": "imports"},
    "8.18.1": {"expenditure_components": "exp"},
    "8.18.2": {"expenditure_components": "exp"},
}
# (statement key, row index) -> code, for the few rows the generic rule names badly
POS_OVERRIDES: dict[tuple[str, int], str] = {}


# ---------------------------------------------------------------------------------------------
# dims carried in the item code (verifier finding verify-5)
# ---------------------------------------------------------------------------------------------

# 4.1: the State-government rows (3.2.1-3.2.31) get the project-wide State/UT code of their printed name
# (pipeline/core/geo.state_code, DECISIONS D1-9), so this unit can never drift from the shared code set: an
# unknown name fails the build. Every other 4.1 row is an all-India item (S4_1_NATIONAL). Every 4.1 row is
# general government by definition; `institution` stays empty because the statement never prints the words
# (its title is 'value added by Central and State governments').
S4_1_NATIONAL = frozenset({
    "gross_value_added", "consumption_of_fixed_capital", "net_value_added", "central_government",
    "state_government", "local_bodies", "autonomous_institutions",
})
# 1.9 / 1.11: institutional sector of a row whose own label names the sector, from its (frozen) item
# code; the same codes 1.14 uses, plus the old-base codes nfc / fc (sector totals) and nfc_public_de /
# nfc_public_nde (2.1A / 2.1B). Sub-rows that name the sector only through their parent heading (1.11
# assets under a sector, 1.9 FC departmental / non-departmental and the household components 1.4.1-1.4.4)
# keep the sector in the item-code prefix and no institution: the independent spot-check can verify an
# institution only from the row, its title or header rows, and summing by institution would otherwise
# double-count a sector total and its own components.
SECTOR_SLUG: dict[str, str] = {
    "public_non_financial_corporations": "nfc_public", "private_non_financial_corporations": "nfc_private",
    "public_financial_corporations": "fc_public", "private_financial_corporations": "fc_private",
    "general_government": "gg", "household_sector": "households_npish",
    "non_financial_corporations": "nfc", "financial_corporations": "fc",
}
S1_9_INSTITUTION: dict[str, str] = {
    **SECTOR_SLUG,
    "public_non_financial_corporations.departmental_enterprises": "nfc_public_de",
    "public_non_financial_corporations.non_departmental_enterprises": "nfc_public_nde",
}


def item_dims(stmt: str, code: str, label: str = "") -> dict[str, str]:
    """Dims implied by a line item (only for 1.9, 1.11 and 4.1); 4.1 States by their printed name."""
    if stmt == "4.1":
        return {} if code in S4_1_NATIONAL else {"geography": geo.state_code(label)}
    if stmt == "1.9":
        return {"institution": S1_9_INSTITUTION[code]} if code in S1_9_INSTITUTION else {}
    if stmt == "1.11":
        head = code.removeprefix("pct_share.")
        return {"institution": SECTOR_SLUG[head]} if head in SECTOR_SLUG else {}
    return {}


# ---------------------------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------------------------

KIND_UNIT = {
    "level": ("INR_crore", "Rs crore", "none"),
    "pct": ("percent", "percent", "none"),
    "growth": ("percent", "percent", "none"),
    "index": ("index", "index (2022-23=100)", "none"),
    "per_capita": ("INR", "Rs", "none"),
    "population": ("count", "million persons", "x 1,000,000 (million -> count)"),
}


def _stage(period: str, ptype: str) -> str:
    if ptype == "fy":
        return STAGES[period]
    if ptype == "fq":
        return STAGES[period[3:]]
    y = int(period[:4])  # stock at 31 March y = end of FY (y-1)-(y)
    return STAGES[f"{y - 1}-{str(y)[2:]}"]


def _row_kind(cfg: Cfg, row: grid.Row, section: str) -> tuple[str, str]:
    """(kind, basis override or '') for one row."""
    if cfg.kind == "special_1_2":
        s = section.lower()
        if row.label.startswith("Population"):
            return "population", "n/a"
        if "percentage change" in s:
            return "growth", CON
        if "constant" in s:
            return "per_capita", CON
        if "current" in s:
            return "per_capita", CUR
        raise ValueError(f"1.2: row {row.label!r} has no price section")
    if cfg.kind != "level":
        return cfg.kind, ""
    if PCT_ROW.search(row.label) or PCT_ROW.search(section):
        return "pct", ""
    return "level", ""


def build_statement(ctx: BuildContext, cfgs: list[Cfg]) -> Dataset:
    first = cfgs[0]
    raw = ctx.raw(SRC, f"{first.stmt}.xlsx")
    out: list[dict[str, Any]] = []
    prov_cache: dict[tuple, str] = {}
    for cfg in cfgs:
        p = parse(raw, cfg)
        spec = grid.load_spec(SPEC_FILE).get(cfg.spec_key)
        if spec is None:
            raise ValueError(f"{cfg.spec_key}: no row spec in {SPEC_FILE}")
        got = spec_rows(p)
        if got != spec:
            diff = [f"row {r.row}: file {g} vs spec {w}" for r, g, w in zip(p.rows, got, spec, strict=False) if g != w]
            raise ValueError(f"{cfg.spec_key}: rows differ from the frozen spec (statement changed?): "
                             f"{diff[:6] or (len(got), len(spec))}")
        out += _rows(ctx, raw, p, [s[2] for s in spec], prov_cache)
    title = grid.text(p.ws, first.title_cell)
    return Dataset(f"{UNIT}_{first.tbl}", pl.DataFrame(out), f"NAS 2026 {grid.english(title)[:150]}")


def _rows(ctx: BuildContext, raw: RawFile, p: Parsed, codes: list[str], prov_cache: dict) -> list[dict[str, Any]]:
    cfg = p.cfg
    out: list[dict[str, Any]] = []
    for row, code, section in zip(p.rows, codes, p.sections, strict=True):
        if not row.has_data:
            continue
        kind, basis_override = _row_kind(cfg, row, section)
        unit, unit_pub, conv = KIND_UNIT[kind]
        dims: dict[str, str | None] = {"geography": "IN", "institution": cfg.institution}
        other: dict[str, str] = {}
        if cfg.section == "industry":
            dims["industry"] = industry_code(section)
        elif cfg.section == "institution":
            dims["institution"] = institution_code(section)
        if cfg.rows == "item":
            dims |= item_dims(cfg.stmt, code, row.label)
        if "K" in cfg.extra and row.extra.get("K"):
            other["nic"] = re.sub(r"\s+", "", row.extra["K"])
        for v in p.vcols:
            val = row.values[v.col]
            if val is None:
                continue
            basis = basis_override or v.basis
            if kind == "index":
                basis = "n/a"
            if cfg.rows in ("industry", "institution"):
                dims[cfg.rows] = code
                item = v.var or cfg.measure
                if item is None:
                    raise ValueError(f"{cfg.stmt}: rows are a dim but there is no column variable or measure")
                label = row.label if not v.var_label else f"{row.label} | {v.var_label}"
            else:
                item = code if not v.var else f"{code}.{v.var}"
                label = row.label if not v.var_label else f"{row.label} | {v.var_label}"
            o = dict(other)
            if cfg.stmt == "4.2" and v.var:
                o["cofog"] = v.var
                item = code
            dim_other = ";".join(f"{k}={o[k]}" for k in sorted(o)) or None
            key_parts = [cfg.tbl]
            if cfg.section:
                key_parts.append(dims[cfg.section] or "")
            if cfg.rows in ("industry", "institution"):
                key_parts.append(code)
            key_parts.append(item)
            if "cofog" in o:
                key_parts.append(o["cofog"])
            sid = ".".join(key_parts) + ("" if basis == "n/a" else f".{basis}")
            pk = (cfg.spec_key, kind, basis)
            if pk not in prov_cache:
                rws = [r.row for r in p.rows]
                cl = [c.col for c in p.vcols if (c.basis == v.basis)]
                prov_cache[pk] = ctx.prov(
                    raw=raw,
                    table_id=f"Statement {cfg.stmt}",
                    locator=f"sheet '{p.ws.title}', rows {rws[0]}-{rws[-1]}, cols {cl[0]}:{cl[-1]} ({kind} rows, "
                    f"{basis}); rows matched by English label in column {cfg.label} against spec_nas2026.json",
                    unit_as_published=unit_pub,
                    conversion=conv,
                    price_basis=basis,
                    base_year=BASE_YEAR,
                    vintage=VINTAGE,
                    release=RELEASE,
                )
            out.append(
                {
                    "series_id": sid,
                    "source_id": SRC,
                    "table_id": f"Statement {cfg.stmt}",
                    "item_code": item,
                    "item_label": label,
                    **dims,
                    "dim_other": dim_other,
                    "stock_flow": "stock" if cfg.stock else ("flow" if unit in ("INR_crore", "INR") else
                                                             ("stock" if kind == "population" else "n/a")),
                    "period": v.period,
                    "period_type": v.period_type,
                    "value": val * 1e6 if kind == "population" else val,
                    "unit": unit,
                    "price_basis": basis,
                    "base_year": BASE_YEAR,
                    "vintage": VINTAGE,
                    "estimate_stage": _stage(v.period, v.period_type),
                    "status": "official",
                    "prov_id": prov_cache[pk],
                }
            )
    return out


def build(ctx: BuildContext) -> list[Dataset]:
    groups: dict[str, list[Cfg]] = {}
    for c in CFGS:
        groups.setdefault(c.stmt, []).append(c)
    return [build_statement(ctx, cs) for cs in groups.values()]
