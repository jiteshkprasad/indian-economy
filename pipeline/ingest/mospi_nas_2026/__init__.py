"""MoSPI National Accounts Statistics: NAS 2026 (new base 2022-23, released 31 Aug 2026) in full,
plus old-base (2011-12) sequences of accounts and key series for ratios and history.

New base, NAS 2026 (source mospi_nas_2026_publication), one dataset per statement:
- mospi_nas_2026_s1_1 and _s8_17_1: hand-mapped (the template); see the functions below.
- the other 62 statements (1.2, 1.4-1.14, 4.1, 4.2, 5.1-5.3, 6.1, 6.2, 7.1-7.4C, 8.1.1-8.16,
  8.17.2, 8.18.1, 8.18.2): stmts2026.py. Years 2022-23 (Final), 2023-24 (Final), 2024-25 (FRE);
  8.17.x add 2025-26 (PE); 8.18.x are quarterly (Q1 2022-23 to Q4 2025-26); 7.4x are net capital
  stocks at 31 March 2023/2024/2025. Current and constant (2022-23) prices as published.
  Rows are industries (dim `industry`), institutional sectors (dim `institution`) or line items
  (item_code), COFOG functions of 4.2 go in dim_other `cofog=`, NIC codes of 8.6.x in `nic=`.
- mospi_nas_2026_derived_residuals: rows computed from the statements (status derived): the two
  official gaps, i.e. the household GDI-FCE-saving residual (1.14) and the saving-investment errors
  and omissions (1.1 GCF minus 1.9 finances for GCF), and the gap-map F1 identity, compensation of
  employees receivable by residents = domestic CE (7.1) + CE from RoW - CE to RoW (6.1).
Not ingested: the growth-rate blocks of 8.17.1/8.17.2/8.18.x (arithmetic on the levels) and
'Abbreviation.xlsx' (a glossary).

Old base 2011-12 (source mospi_nas_old_base_2011_12), never mixed with the new base (own
datasets, base_year 2011-12, price basis current/constant_2011_12, the edition's vintage):
oldbase.py -- NAS 2024 sequences of accounts 1.15, 2.0-2.2, 3.0-3.2, 4.0, 5.0, 6.0
(2011-12 to 2022-23) and NAS 2025 Statements 1.1, 1.9, 1.14, 5.3 (2011-12 to 2023-24).

NAS API (source mospi_nas_api, api.mospi.gov.in through the host-scoped legacy-TLS opt-in, DECISIONS
D1-6): api.py -- the old-base back series 1950-51 to 2011-12, the old-base annual series by revision
round and quarterly series to 2025-26, and the new-base annual and quarterly series (to Q1 2026-27).
Datasets mospi_nas_2026_api_*. The new base has no back series yet (checked by a pinned probe).

Sources and Methods 2026 is documentation, not data, and is not ingested.

Access (docs/phase0/recon/mospi_nas.md s1.2): the publication pages are a JavaScript app, so file
lists come from the public JSON endpoint the page itself calls (POST get-web-chapter-data); the
statement files are plain XLSX, fetched with browser-style headers (D1-1a). Parsing is by English
label: every statement is checked against a frozen row spec (spec_nas2026.json /
spec_oldbase.json: labels, header/data role, blank-cell pattern, codes), so a reshuffled or
relabelled statement fails loudly instead of ingesting shifted numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import openpyxl
import polars as pl

from pipeline.core.unit import BuildContext, Dataset, FetchContext, RawFile
from pipeline.core.units import clean_label, normalize_fy, parse_number, slug

UNIT = "mospi_nas_2026"
SOURCES = ["mospi_nas_2026_publication", "mospi_nas_old_base_2011_12", "mospi_nas_api"]

SRC = "mospi_nas_2026_publication"
SRC_OLD = "mospi_nas_old_base_2011_12"
PUBLICATION_ID = 2861
LANDING = f"https://mospi.gov.in/publications-reports/innerpage/{PUBLICATION_ID}"
CHAPTER_API = "https://www.mospi.gov.in/api/publications-reports/get-web-chapter-data"
FILE_BASE = "https://www.mospi.gov.in/uploads/publications_reports/NAS-2026-Statements/"
STATEMENTS = ("1.1", "8.17.1")

VINTAGE = "2026-08-31"
RELEASE = "National Accounts Statistics 2026 (NSO, MoSPI; released 31 Aug 2026)"
BASE_YEAR = "2022-23"
# Estimate stage of each year in the NAS 2026 vintage (NAS 2026 press release; 8.17.1 headers).
STAGES = {"2022-23": "Final", "2023-24": "Final", "2024-25": "FRE", "2025-26": "PE"}
CURRENT, CONSTANT = "current", "constant_2022_23"


def fetch(ctx: FetchContext) -> None:
    listing = ctx.fetch(
        SRC,
        CHAPTER_API,
        name="chapters_2861.json",
        method="POST",
        json_body={"publication_id": PUBLICATION_ID},
        referer=LANDING,
    )
    urls = _statement_urls(listing.read_json())
    for st in STATEMENTS:
        if st not in urls:
            raise RuntimeError(f"statement {st} is not in the NAS 2026 chapter listing")
    # every statement in the listing (64; 'Abbreviation' is a glossary, not data)
    for st in sorted(urls, key=_stmt_key):
        if st == "Abbreviation":
            continue
        ctx.fetch(SRC, urls[st], name=f"{st}.xlsx", referer=LANDING)
    # Old base (2011-12): NAS 2024 sequences of accounts (the last edition that has them) and the
    # NAS 2025 key statements (2011-12..2023-24) for the time series. Ratios/history only.
    for pub, edition, wanted in OLD_FILES:
        doc = ctx.fetch(
            SRC_OLD,
            CHAPTER_API,
            name=f"chapters_{pub}.json",
            method="POST",
            json_body={"publication_id": pub},
            referer=f"https://mospi.gov.in/publications-reports/innerpage/{pub}",
        ).read_json()
        found = _listing_files(doc)
        if edition == "nas2024":  # the edition's own notes: estimate stage of each year
            ctx.fetch(SRC_OLD, found["Method_NAS2024.pdf"], name="nas2024_Method_NAS2024.pdf")
        for stem in wanted:
            fname = f"{stem}.xlsx"
            if fname not in found:
                raise RuntimeError(f"{edition} statement {stem} is not in the chapter listing of publication {pub}")
            ctx.fetch(
                SRC_OLD,
                found[fname],
                name=f"{edition}_{fname}",
                referer=f"https://mospi.gov.in/publications-reports/innerpage/{pub}",
            )
    # NAS API (api.mospi.gov.in; legacy TLS opt-in, D1-6): the long time series, see api.py.
    from pipeline.ingest.mospi_nas_2026 import api

    api.fetch(ctx)


# (publication id, edition tag, statements) of the old-base (2011-12) editions this unit reads.
OLD_FILES = (
    (434, "nas2024", ("1.15", "2.0", "2.1", "2.1A", "2.1B", "2.2", "3.0", "3.1", "3.2", "4.0", "5.0", "6.0")),
    (432, "nas2025", ("1.1", "1.9", "1.14", "5.3")),
)


def _listing_files(doc: dict[str, Any]) -> dict[str, str]:
    """{file name: url} of every file in a MoSPI chapter listing (chapters and sub-chapters)."""
    out: dict[str, str] = {}
    for ch in doc["data"]:
        for node in (ch, *ch["sub_chapters"]):
            for slot in ("file_one", "file_two", "file_three"):
                f = node.get(slot)
                if f:
                    name = f["path"].rsplit("/", 1)[-1]
                    if name in out and out[name] != f["path"]:
                        raise RuntimeError(f"two listing entries for {name}")
                    out[name] = f["path"]
    return out


def _stmt_key(st: str) -> tuple:
    import re as _re

    return tuple(int(p) if p.isdigit() else p for p in _re.findall(r"\d+|[A-Za-z]+", st))


def _statement_urls(doc: dict[str, Any]) -> dict[str, str]:
    """{file stem: url} from the chapter listing, e.g. '1.1', '1.6B', '8.6.1A', '8.17.1'.

    Keyed by file name, not by the listing's `statement_no`: that field is empty for the four
    PE/quarterly statements (8.17.x, 8.18.x) and shared by Part I/II files (8.6.1A/B, 1.6/1.6B).
    """
    out: dict[str, str] = {}
    for ch in doc["data"]:
        for sc in ch["sub_chapters"]:
            for slot in ("file_one", "file_two", "file_three"):
                f = sc.get(slot)
                if not f:
                    continue
                url = f["path"]
                if not url.startswith(FILE_BASE) or not url.endswith(".xlsx"):
                    raise RuntimeError(f"unexpected statement URL in listing: {url}")
                stem = url[len(FILE_BASE) : -len(".xlsx")]
                if stem in out and out[stem] != url:
                    raise RuntimeError(f"two listing entries for statement file {stem}")
                out[stem] = url
    return out


# ---------------------------------------------------------------------------------------------
# sheet reading
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Item:
    code: str
    kind: str  # level | pct | growth | per_capita | population


@dataclass
class Cell:
    row: int
    col: str
    section: str
    label: str
    period: str
    value: float | None


def _panel(ws: Any, *, label_col: str, sno_col: str, year_cols: dict[str, str], first: int, last: int) -> list[Cell]:
    """Read one panel: rows first..last; a row with a label and no serial number is a section header."""
    cells: list[Cell] = []
    section = ""
    for r in range(first, last + 1):
        label = ws[f"{label_col}{r}"].value
        sno = ws[f"{sno_col}{r}"].value
        if label is None:
            continue
        label = clean_label(label)
        if sno is None:
            section = slug(label)
            continue
        for col, period in year_cols.items():
            cells.append(Cell(r, col, section, label, period, parse_number(ws[f"{col}{r}"].value)))
    return cells


def _year_header(ws: Any, cols: list[str], row: int) -> dict[str, str]:
    return {c: normalize_fy(str(ws[f"{c}{row}"].value)) for c in cols}


def _expect(ws: Any, cell: str, needle: str) -> None:
    got = clean_label(ws[cell].value or "")
    if needle.lower() not in got.lower():
        raise ValueError(f"sheet {ws.title!r} {cell}: expected text containing {needle!r}, found {got!r}")


def _rows(
    ctx: BuildContext,
    raw: RawFile,
    sheet: str,
    table: str,
    cells: list[Cell],
    items: dict[tuple[str, str], Item],
    basis: str,
    allow_missing: set[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Map parsed cells to clean rows; unmapped labels and unexpected blanks are errors."""
    unknown = sorted({(c.section, c.label) for c in cells} - set(items))
    if unknown:
        raise ValueError(f"{table} {basis}: labels not in the item map (statement changed?): {unknown}")
    absent = sorted(set(items) - {(c.section, c.label) for c in cells})
    rows: list[dict[str, Any]] = []
    blocks: dict[str, list[Cell]] = {}
    for c in cells:
        it = items[(c.section, c.label)]
        if c.value is None:
            if (it.code, c.period) in allow_missing or (it.code, "*") in allow_missing:
                continue
            raise ValueError(f"{table} {basis}: blank cell {c.col}{c.row} for {it.code} {c.period}")
        blocks.setdefault(it.kind, []).append(c)
    prov: dict[str, str] = {}
    for kind, bc in blocks.items():
        rws = sorted({c.row for c in bc})
        cols = sorted({c.col for c in bc})
        unit_pub, conv = {
            "level": ("Rs crore", "none"),
            "pct": ("percent", "none"),
            "growth": ("percent", "none"),
            "per_capita": ("Rs", "none"),
            "population": ("million persons", "x 1,000,000 (million -> count)"),
        }[kind]
        prov[kind] = ctx.prov(
            raw=raw,
            table_id=f"Statement {sheet}",
            locator=f"sheet '{sheet}', rows {rws[0]}-{rws[-1]}, cols {cols[0]}:{cols[-1]} ({kind} rows, "
            f"{'current' if basis == CURRENT else 'constant 2022-23'} prices); rows matched by English label",
            unit_as_published=unit_pub,
            conversion=conv,
            price_basis="n/a" if kind == "population" else basis,
            base_year=BASE_YEAR,
            vintage=VINTAGE,
            release=RELEASE,
        )
    for c in (c for c in cells if c.value is not None):
        it = items[(c.section, c.label)]
        is_pop = it.kind == "population"
        pb = "n/a" if is_pop else basis
        rows.append(
            {
                "series_id": f"{table}.{it.code}" + ("" if is_pop else f".{pb}"),
                "source_id": SRC,
                "table_id": f"Statement {sheet}",
                "item_code": it.code,
                "item_label": c.label,
                "geography": "IN",
                "stock_flow": {"level": "flow", "per_capita": "flow", "population": "stock"}.get(it.kind, "n/a"),
                "period": c.period,
                "period_type": "fy",
                "value": c.value * 1e6 if is_pop else c.value,
                "unit": {"level": "INR_crore", "per_capita": "INR", "population": "count"}.get(it.kind, "percent"),
                "price_basis": pb,
                "base_year": BASE_YEAR,
                "vintage": VINTAGE,
                "estimate_stage": STAGES[c.period],
                "status": "official",
                "prov_id": prov[it.kind],
            }
        )
    if absent:
        raise ValueError(f"{table} {basis}: mapped labels not found in the sheet (statement changed?): {absent}")
    return rows


# ---------------------------------------------------------------------------------------------
# Statement 1.1
# ---------------------------------------------------------------------------------------------

L, P, G = "level", "pct", "growth"
S1_1_ITEMS: dict[tuple[str, str], Item] = {
    ("domestic_product", "GVA at basic prices"): Item("gva_basic", L),
    ("domestic_product", "Taxes on Products including import duties"): Item("taxes_on_products", L),
    ("domestic_product", "Less Subsidies on Products"): Item("subsidies_on_products", L),
    ("domestic_product", "GDP (1+2-3)"): Item("gdp", L),
    ("domestic_product", "CFC"): Item("cfc", L),
    ("domestic_product", "NDP(4-5)"): Item("ndp", L),
    ("final_expenditure", "PFCE"): Item("pfce", L),
    ("final_expenditure", "GFCE"): Item("gfce", L),
    ("final_expenditure", "GCF"): Item("gcf", L),
    ("final_expenditure", "GFCF"): Item("gfcf", L),
    ("final_expenditure", "CIS"): Item("cis", L),
    ("final_expenditure", "Valuables"): Item("valuables", L),
    ("final_expenditure", "Exports of goods and services"): Item("exports", L),
    ("final_expenditure", "Export of goods"): Item("exports_goods", L),
    ("final_expenditure", "Export of services"): Item("exports_services", L),
    ("final_expenditure", "Less Imports of goods and services"): Item("imports", L),
    ("final_expenditure", "Import of goods"): Item("imports_goods", L),
    ("final_expenditure", "Import of services"): Item("imports_services", L),
    ("final_expenditure", "Discrepancies"): Item("discrepancies", L),
    ("final_expenditure", "GDP"): Item("gdp_expenditure", L),
    ("final_expenditure", "Primary income receivable from ROW (net)"): Item("primary_income_row_net", L),
    ("final_expenditure", "GNI(13+14)"): Item("gni", L),
    ("final_expenditure", "NNI (15-5)"): Item("nni", L),
    ("final_expenditure", "Other current transfers (net) from ROW"): Item("other_current_transfers_row_net", L),
    ("final_expenditure", "GNDI(15+17)"): Item("gndi", L),
    ("final_expenditure", "NNDI(18-5)"): Item("nndi", L),
    ("final_expenditure", "Gross Saving"): Item("gross_saving", L),
    ("final_expenditure", "Net Saving (19-5)"): Item("net_saving", L),
    ("rates", "Gross Saving to GNDI"): Item("gross_saving_pct_gndi", P),
    ("rates", "GCF to GDP"): Item("gcf_pct_gdp", P),
    ("rates", "GCF excluding Valuables to GDP"): Item("gcf_excl_valuables_pct_gdp", P),
    ("rates", "PFCE to NNI"): Item("pfce_pct_nni", P),
    ("rates_of_expenditure_components_to_gdp", "PFCE"): Item("pfce_pct_gdp", P),
    ("rates_of_expenditure_components_to_gdp", "GFCE"): Item("gfce_pct_gdp", P),
    ("rates_of_expenditure_components_to_gdp", "GFCF"): Item("gfcf_pct_gdp", P),
    ("rates_of_expenditure_components_to_gdp", "CIS"): Item("cis_pct_gdp", P),
    ("rates_of_expenditure_components_to_gdp", "Valuables"): Item("valuables_pct_gdp", P),
    ("rates_of_expenditure_components_to_gdp", "Export of goods and services"): Item("exports_pct_gdp", P),
    ("rates_of_expenditure_components_to_gdp", "Export of goods"): Item("exports_goods_pct_gdp", P),
    ("rates_of_expenditure_components_to_gdp", "Export of services"): Item("exports_services_pct_gdp", P),
    ("rates_of_expenditure_components_to_gdp", "Less Import of goods and services"): Item("imports_pct_gdp", P),
    ("rates_of_expenditure_components_to_gdp", "Import of goods"): Item("imports_goods_pct_gdp", P),
    ("rates_of_expenditure_components_to_gdp", "Import of services"): Item("imports_services_pct_gdp", P),
    ("rates_of_expenditure_components_to_gdp", "Discrepancies"): Item("discrepancies_pct_gdp", P),
    ("percentage_change_over_previous_year", "GVA at basic prices"): Item("gva_basic_growth", G),
    ("percentage_change_over_previous_year", "GDP"): Item("gdp_growth", G),
}
# Current prices only (statement note iii), so blank in the constant-price block.
S1_1_CURRENT_ONLY = (
    "other_current_transfers_row_net",
    "gndi",
    "nndi",
    "gross_saving",
    "net_saving",
    "gross_saving_pct_gndi",
)


def _build_s1_1(ctx: BuildContext) -> Dataset:
    raw = ctx.raw(SRC, "1.1.xlsx")
    ws = openpyxl.load_workbook(raw.path, data_only=True, read_only=False)["1.1"]
    _expect(ws, "B2", "STATEMENT 1.1: KEY AGGREGATES OF NATIONAL ACCOUNTS")
    _expect(ws, "C4", "At Current Prices")
    _expect(ws, "F4", "At constant (2022-23) Prices")
    _expect(ws, "H5", "crore")
    cur = _year_header(ws, ["C", "D", "E"], 6)
    con = _year_header(ws, ["F", "G", "H"], 6)
    if list(cur.values()) != ["2022-23", "2023-24", "2024-25"] or list(con.values()) != list(cur.values()):
        raise ValueError(f"unexpected year header in 1.1: {cur} {con}")
    last = max(r for r in range(9, ws.max_row + 1) if isinstance(ws[f"J{r}"].value, (int, float)))
    growth_first = {(i.code, "2022-23") for i in S1_1_ITEMS.values() if i.kind == G}
    rows = []
    for basis, cols, allow in (
        (CURRENT, cur, growth_first),
        (CONSTANT, con, growth_first | {(c, "*") for c in S1_1_CURRENT_ONLY}),
    ):
        cells = _panel(ws, label_col="I", sno_col="J", year_cols=cols, first=8, last=last)
        rows += _rows(ctx, raw, "1.1", "s1_1", cells, S1_1_ITEMS, basis, allow)
    return Dataset(f"{UNIT}_s1_1", pl.DataFrame(rows), "NAS 2026 Statement 1.1 key aggregates, 2022-23 to 2024-25")


# ---------------------------------------------------------------------------------------------
# Statement 8.17.1
# ---------------------------------------------------------------------------------------------

PC, POP = "per_capita", "population"
_S8 = {
    ("domestic_product", "GVA at Basic Prices"): Item("gva_basic", L),
    ("domestic_product", "Net Taxes on Products"): Item("net_taxes_on_products", L),
    ("domestic_product", "Gross Domestic Product (GDP)"): Item("gdp", L),
    ("domestic_product", "Net Domestic Product (NDP)"): Item("ndp", L),
    ("national_income", "Gross National Income (GNI)"): Item("gni", L),
    ("national_income", "Net National Income (NNI)"): Item("nni", L),
    ("national_income", "Gross National Disposable Income (GNDI)"): Item("gndi", L),
    ("national_income", "Net National Disposable Income (NNDI)"): Item("nndi", L),
    ("per_capita_income_gdp_and_final_consumption", "Population (in million)"): Item("population", POP),
    ("per_capita_income_gdp_and_final_consumption", "Per Capita GDP (₹)"): Item("gdp_per_capita", PC),
    ("per_capita_income_gdp_and_final_consumption", "Per Capita GNI (₹)"): Item("gni_per_capita", PC),
    ("per_capita_income_gdp_and_final_consumption", "Per Capita NNI (₹)"): Item("nni_per_capita", PC),
    ("per_capita_income_gdp_and_final_consumption", "Per Capita GNDI (₹)"): Item("gndi_per_capita", PC),
    ("per_capita_income_gdp_and_final_consumption", "Per Capita PFCE (₹)"): Item("pfce_per_capita", PC),
}
for _label, _code in (
    ("Private Final Consumption Expenditure (PFCE)", "pfce"),
    ("Government Final Consumption Expenditure (GFCE)", "gfce"),
    ("Gross Fixed Capital Formation (GFCF)", "gfcf"),
    ("Changes in Stocks (CIS)", "cis"),
    ("Valuables", "valuables"),
    ("Exports", "exports"),
    ("Imports", "imports"),
    ("Discrepancies", "discrepancies"),
    ("GDP", "gdp"),
):
    _S8[("expenditure_components", _label)] = Item(_code if _code != "gdp" else "gdp_expenditure", L)
    _S8[("share_in_gdp", _label)] = Item(f"{_code}_pct_gdp", P)
S8_17_1_ITEMS = _S8
# Items printed in only one of the two panels (the statement's own layout).
S8_CONSTANT_ONLY = ("population",)
S8_CURRENT_ONLY = ("gndi", "nndi", "gndi_per_capita")


def _build_s8_17_1(ctx: BuildContext) -> Dataset:
    raw = ctx.raw(SRC, "8.17.1.xlsx")
    ws = openpyxl.load_workbook(raw.path, data_only=True)["8.17.1"]
    _expect(ws, "B2", "STATEMENT 8.17.1: PROVISIONAL ESTIMATES OF NATIONAL INCOME")
    _expect(ws, "A4", "at Constant Prices")
    _expect(ws, "K4", "at Current Prices")
    _expect(ws, "F5", "crore")
    _expect(ws, "P5", "crore")
    for cell, tag in (("E6", "FRE"), ("F6", "PE"), ("O6", "FRE"), ("P6", "PE")):
        _expect(ws, cell, tag)  # the stage tags must match STAGES
    con = _year_header(ws, ["C", "D", "E", "F"], 6)
    cur = _year_header(ws, ["M", "N", "O", "P"], 6)
    want = ["2022-23", "2023-24", "2024-25", "2025-26"]
    if list(con.values()) != want or list(cur.values()) != want:
        raise ValueError(f"unexpected year header in 8.17.1: {con} {cur}")
    last = max(
        r
        for r in range(9, ws.max_row + 1)
        if isinstance(ws[f"A{r}"].value, (int, float)) or isinstance(ws[f"K{r}"].value, (int, float))
    )
    rows = []
    for basis, label_col, sno_col, cols, only_other in (
        (CONSTANT, "B", "A", con, S8_CURRENT_ONLY),
        (CURRENT, "L", "K", cur, S8_CONSTANT_ONLY),
    ):
        items = {k: v for k, v in S8_17_1_ITEMS.items() if v.code not in only_other}
        cells = _panel(ws, label_col=label_col, sno_col=sno_col, year_cols=cols, first=8, last=last)
        rows += _rows(ctx, raw, "8.17.1", "s8_17_1", cells, items, basis, set())
    return Dataset(
        f"{UNIT}_s8_17_1",
        pl.DataFrame(rows),
        "NAS 2026 Statement 8.17.1 macro aggregates incl. 2025-26 PE, levels, shares, per capita",
    )


def build(ctx: BuildContext) -> list[Dataset]:
    from pipeline.ingest.mospi_nas_2026 import api, oldbase, stmts2026

    new = [_build_s1_1(ctx), _build_s8_17_1(ctx), *stmts2026.build(ctx)]
    out = [*new, _derived_residuals(ctx, {d.name: d.df for d in new}), *oldbase.build(ctx), *api.build(ctx)]
    return [_with_less_note(d) for d in out]


LESS_NOTE = (" 'Less'-captioned items ({}) are stored as the positive magnitudes published; subtract them"
             " (item codes such as subsidies_on_products or imports do not carry the minus).")


def _with_less_note(d: Dataset) -> Dataset:
    """Verifier finding verify-4: document the sign convention of 'Less ...' items in the description."""
    labels = sorted({lab for lab in d.df["item_label"].to_list() if lab.lower().lstrip().startswith("less")})
    if not labels:
        return d
    shown = "; ".join(labels[:4]) + ("; ..." if len(labels) > 4 else "")
    return Dataset(d.name, d.df, d.description.rstrip(" .") + "." + LESS_NOTE.format(shown))


# ---------------------------------------------------------------------------------------------
# derived: the two official gaps the SAM carries in X_DISC (gap map D1, D3), and the F1 identity
# ---------------------------------------------------------------------------------------------

RESIDUALS = (
    (
        "household_residual",
        "Household residual: GDI less final consumption less gross saving (households incl. NPISH)",
        "Statements 1.1, 1.9, 1.14 (derived)",
        {
            "s1_14.households_npish.gross_disposable_income.current": 1,
            "s1_14.households_npish.final_consumption_expenditure.current": -1,
            "s1_14.households_npish.gross_savings.current": -1,
        },
        "Statement 1.14 households incl. NPISH: Gross Disposable Income minus Final Consumption Expenditure "
        "minus Gross Savings. Household GDI is compiled residually and household saving independently "
        "(RBI financial + physical saving), so the difference is an official, unpublished gap.",
    ),
    (
        "si_errors_omissions",
        "Saving-investment errors and omissions: GCF less finances for GCF (gross saving + net capital inflow)",
        "Statements 1.1, 1.9, 1.14 (derived)",
        {"s1_1.gcf.current": 1, "s1_9.finances_for_gross_capital_formation_1_2.current": -1},
        "Statement 1.1 GCF (GFCF + CIS + valuables, current prices) minus Statement 1.9 item 3 'finances for "
        "gross capital formation (1+2)' = gross saving + net capital inflow from RoW (Sources and Methods 2026 "
        "s.26.6: the difference is errors and omissions).",
    ),
    (
        "ce_receivable_by_residents",
        "Compensation of employees receivable by resident households: domestic CE + CE from RoW - CE to RoW",
        "Statements 7.1, 6.1 (derived)",
        {
            "s7_1.total.ce.current": 1,
            "s6_1.compensation_of_employees_from_rest_of_the_world.current": 1,
            "s6_1.compensation_of_employees_to_the_rest_of_the_world.current": -1,
        },
        "Gap map F1 (labour income to households, total): Statement 7.1 'Total | Compensation of employee' "
        "(CE paid by resident producers, domestic concept) plus Statement 6.1 'compensation of employees from rest "
        "of the world' minus 6.1 'compensation of employees to the rest of the world' (SNA 2008: D1 resources of "
        "the household sector = D1 paid by resident producers + D1 from RoW - D1 to RoW).",
    ),
)


def _derived_residuals(ctx: BuildContext, frames: dict[str, pl.DataFrame]) -> Dataset:
    allrows = pl.concat(
        [frames[f"{UNIT}_{t}"] for t in ("s1_1", "s1_9", "s1_14", "s6_1", "s7_1")], how="diagonal_relaxed"
    )
    out: list[dict[str, Any]] = []
    for code, label, table, parts, method in RESIDUALS:
        sub = allrows.filter(pl.col("series_id").is_in(list(parts)))
        periods = sorted(set(sub["period"].to_list()))
        pid = ctx.prov(
            raw=None,
            source_id=SRC,
            table_id=table,
            locator=f"computed from series {', '.join(parts)}",
            unit_as_published="Rs crore",
            conversion="none",
            price_basis=CURRENT,
            base_year=BASE_YEAR,
            vintage=VINTAGE,
            release=RELEASE,
            status="derived",
            method=method + " Sum with signs: " + ", ".join(f"{c:+d} x {k}" for k, c in parts.items()),
            inputs=sorted(set(sub["prov_id"].to_list())),
        )
        for per in periods:
            vals = {r["series_id"]: r["value"] for r in sub.filter(pl.col("period") == per).iter_rows(named=True)}
            if set(vals) != set(parts):
                raise ValueError(f"{code} {per}: inputs missing: {sorted(set(parts) - set(vals))}")
            out.append(
                {
                    "series_id": f"derived.{code}.current",
                    "source_id": SRC,
                    "table_id": table,
                    "item_code": code,
                    "item_label": label,
                    "geography": "IN",
                    "institution": "households_npish" if code == "household_residual" else None,
                    "stock_flow": "flow",
                    "period": per,
                    "period_type": "fy",
                    "value": round(sum(c * vals[k] for k, c in parts.items()), 6),
                    "unit": "INR_crore",
                    "price_basis": CURRENT,
                    "base_year": BASE_YEAR,
                    "vintage": VINTAGE,
                    "estimate_stage": STAGES[per],
                    "status": "derived",
                    "prov_id": pid,
                }
            )
    return Dataset(
        f"{UNIT}_derived_residuals",
        pl.DataFrame(out),
        "NAS 2026 derived rows: household GDI-FCE-saving residual; saving-investment errors & omissions; "
        "CE receivable by residents (gap map F1)",
    )
