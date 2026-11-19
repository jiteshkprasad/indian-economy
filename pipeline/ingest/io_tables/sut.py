"""MoSPI Supply and Use Tables 2022-23 and 2023-24 (base 2022-23, revised files of 31 Aug 2026).

Three datasets, each holding both years in long form (one row = one published cell):
- io_tables_sut_supply: Supply sheet. Domestic output at basic prices by product (155) x industry
  (67), the 'Total Output' row, and the valuation columns (Supply at BP, Imports, CIF Adj, Imports
  after cif adjustment, Import Duty, Product taxes, Subsidy on Products, Trade and Transport
  Margins, Supply at PP) including the memo rows CIF, Purchases of Residents abroad and Purchases
  of Non-Residents in domestic market.
- io_tables_sut_use: Use sheet at purchasers' prices. Intermediate consumption product x industry,
  the 'Total Use' row (total intermediate input of each industry) and the final-use columns
  (Intermediate Consumption, PFCE, GFCE, GFCF, CII, Net Acquisition of Valuables, Export, Total
  Use at PP), with the same memo rows.
- io_tables_sut_va: the value-added block under the Use sheet by industry: GVA (production
  approach), Production Taxes less Subsidies, CFC, Compensation of Employees, Operating Surplus
  (incl. mixed income) and GVA (income approach).

Blank cells (stored by MoSPI as ' ') are empty cells of the matrix and produce no row; a cell
absent from the clean table is therefore zero. Explicit zeros are kept. Values are ingested as
published (Rs crore, full floating precision, MoSPI's signs: subsidies and the margin-supplying
products' TTM entries are negative).

Codes: product = 'sut_p001'..'sut_p155' (SUT serial number) or a memo code (cif,
purchases_residents_abroad, purchases_nonresidents_domestic, total); industry = 'sut_i01'..
'sut_i67' (column order of the sheet, = ACCOUNT_STRUCTURE 'SUT ind.').

Known quirk kept as published (issue io_tables-1): in the 2023-24 file the data rows of products
43 and 44 are swapped relative to their labels ('Natural Gas' row holds crude petroleum and vice
versa). Both map to C_OILG in the concordance, so the SAM is unaffected. Every row of the two
products' series carries a machine-readable flag in dim_other,
'label_swap_period=2023-24;swap_partner=sut_p044' (p043) and '...;swap_partner=sut_p043' (p044): in
that period the row holds the partner product's data. (dims must be constant within a series_id, so
the flag names the period instead of sitting on the 2023-24 rows only.) The provenance notes of every
2023-24 block say so too. Values and labels stay as published.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import openpyxl
import polars as pl

from pipeline.core.unit import BuildContext, Dataset, RawFile
from pipeline.core.units import clean_label, parse_number

SRC = "mospi_sut_2022base"
VINTAGE = "2026-08-31"
RELEASE = "Supply and Use Tables 2022-23 and 2023-24, revised files (NAD, NSO, MoSPI; uploaded 31 Aug 2026 with NAS 2026)"
BASE_YEAR = "2022-23"
STAGE = "Final"  # the SUTs are integrated with the Final Estimates of NAS 2026 (SUT note s.2.2, s.9)

# pin name -> (period, sha256 of the Aug-2026 file as recorded by the Phase 0 verifier)
FILES = {
    "sut_2022_23.xlsx": ("2022-23", "415955ee"),
    "sut_2023_24.xlsx": ("2023-24", "6fbaa0e9"),
}
SWAP_NOTE = (
    "Quirk Q1 (issue io_tables-1): in this 2023-24 file the data rows of products 43 'Natural Gas' and 44 "
    "'Crude petroleum' are swapped relative to their labels (the row labelled Natural Gas is produced by industry 6 "
    "Crude Petroleum and carries the crude imports). Ingested as published; both products map to C_OILG."
)
# Q1: the 2023-24 rows of products 43/44 carry the other product's data. Flag the two series (dim_other,
# all periods: a series' dims must not vary) so a product-level time series does not read crude
# petroleum as natural gas in 2023-24. Values and labels unchanged.
SWAP_PERIOD = "2023-24"
SWAP_FLAG = {
    "sut_p043": f"label_swap_period={SWAP_PERIOD};swap_partner=sut_p044",
    "sut_p044": f"label_swap_period={SWAP_PERIOD};swap_partner=sut_p043",
}

PRODUCTS = (
    "Paddy", "Wheat", "Coarse cereals", "Gram", "Arhar", "Other pulses", "Groundnut", "Rapeseed and mustard",
    "Other oil seeds", "Fibre Crop", "Sugar crop", "Coconut", "Tobacco", "Tea", "Coffee", "Rubber", "Mango",
    "Banana", "Citrus & grape fruit", "Other Fruit", "Potato", "Onions", "Tomato", "Cabbage and couliflower",
    "Other Vegetable", "Spices and Condiments", "Other food crops", "Milk", "Wool", "Egg", "Poultry Meat", "Beef",
    "Mutton", "Other Meat", "Other livestock products", "Industry Wood", "Firewood", "Other forestry products",
    "Inland Fish", "Marine Fish", "Prawn", "Coal and Lignite", "Natural Gas", "Crude petroleum", "Iron ore",
    "Manganese ore", "Bauxite", "Copper ore", "Other Metallic minerals", "Limestone", "Other non metallic minerals",
    "Processed poultry meat & poultry meat products", "Processed other meat & meat products",
    "Processed fish & fish products", "Processed fruits & Processed Vegetables", "Dairy products",
    "Edible Oils and Fats", "wheat (Grain Mill Products)", "Pulse (Grain Mill Products)",
    "Rice (Grain Mill Products)", "Others (Grain Mill Products)", "Sugar , Starch and Gur", "Bread & Bakery products",
    "Miscellaneous food products", "Alcoholic beverages", "Non alcoholic beverages", "Tea processed",
    "Coffee processed", "Tobacco Products", "Cotton Yarn and Cotton Textiles", "Synthetic yarn and synthetic textiles",
    "Wool yarn and woolen textiles", "Silk yarn and silk textiles", "Carpet weaving", "Ready made garments",
    "Misc. textile products", "Leather footwear", "Leather and leather products except footwear",
    "Wood and wood products except furniture", "Paper, Paper products and newsprint",
    "Publishing, printing and allied activities", "Furniture & Fixtures", "Rubber products", "Plastic products",
    "Petroleum products", "Coal tar products", "Inorganic chemicals", "Organic chemicals", "Fertilizers",
    "Pesticides", "Paints, varnishes and lacquers", "Drugs and medicine", "Soaps, cosmetics and glycerin",
    "Synthetic fibres, resin", "Other chemicals and chemical products", "Cement", "Non metallic mineral products",
    "Iron and steel Ferro alloys", "Iron and steel casting and forging", "Iron and steel foundries",
    "Non ferrous basic metals (including alloys)", "Hand tools, hardware", "Miscellaneous metal products",
    "Tractors and other agricultural implements", "Industrial machinery for food and textile industry",
    "Industrial machinery (except food and textile)", "Machine tools", "Other non electrical machinery",
    "Electrical industrial machinery", "Electrical cables, wires", "Batteries", "Electrical appliances",
    "Communication equipment", "Other electrical machinery", "Electronic equipment including T.V",
    "Medical precision, optical instrument", "Watches and clocks", "Ships and boats", "Rail equipment",
    "Motor vehicles", "Motor cycles and scooters", "Bicycles, cycle-rickshaw", "Aircrafts & Spacecrafts",
    "Other transport equipment", "Gems & jewellery", "Miscellaneous manufacturing", "Construction", "Electricity",
    "Gas", "Water Supply", "Other Utility Services", "Trade", "Repair & Maintenance of Motor Vehicle",
    "Hotels & Restaurant", "Railway Transport", "Land transport", "Air transport", "Water Transport",
    "Supportive and Auxiliary transport activities", "Storage and warehousing", "Communication services",
    "Financial services", "Insurance services", "Ownership of dwellings", "Real estate services",
    "Renting of machinery & equipment", "Research & Development Services", "Legal services",
    "Other Business services", "Computer related services", "Public administration and defence",
    "Education services", "Human health and social care services", "Community, social and personal services",
    "Recreation, entertainment and radio & TV broadcasting and other services",
)
INDUSTRIES = (
    "Agriculture", "Livestock", "Forestry and Logging", "Fishing & Aquaculture", "Coal & Lignite",
    "Crude Petroleum", "Natural Gas", "Iron Ore", "Non ferrous metal ores", "Other Mining",
    "Production, processing and preservation of meat, fish, fruit, vegetables, oils and fats",
    "Manufacture of dairy products", "Manufacture of grain mill products, etc. and animal feeds",
    "Manufacture of other food products", "Manufacture of beverages", "Manufacture of tobacco products",
    "Manufacture of textiles + cotton ginning", "Manufacture of wearing apparel, except custom tailoring",
    "Manufacture of leather and related products", "Manufacture of Basic Iron and Steel + Casting of iron and steel",
    "Manufacture of basic precious and non-ferrous metals + Casting of non-ferrous metals",
    "Manufacture of fabricated metal products, except machinery and equipments",
    "Manufacture of electronic component, consumer electronics, magnetic and optical media",
    "Manufacture of computer and peripheral equipment", "Manufacture of communication equipments",
    "Manufacture of optical and electronics products n.e.c.", "Manufacture of Electrical equipments",
    "Manufacture of machinery and equipments n.e.c.", "Manufacture of Transport",
    "Manufacture of coke and refined petroleum products",
    "Manufacture of chemical and chemical products except pharmaceuticals, medicinal and botanical products",
    "Manufacture of pharmaceutical; medicinal chemicals and botanical products",
    "Manufacture of rubber & plastic products", "Manufacture of other non-metallic mineral products",
    "Manufacture of wood and of products of wood and cork, except furniture; manufacture of articles of straw and "
    "plaiting material",
    "Manufacture of paper and paper products", "Printing and reproduction of recorded media except publishing",
    "Manufacture of furniture", "Other Manufacturing", "Repair and installation of machinery and equipments",
    "Construction", "Electricity", "Gas", "Water supply", "Other Utility Services", "Railway Transport",
    "Land Transport", "Water Transport", "Air Transport", "Supportive & Auxiliary transport activities",
    "Storage & warehousing", "Communication", "Trade", "Hotels & Restaurant", "Financial Services",
    "Insurance Services", "Ownership of dwellings", "Education & Research", "Medical and Health",
    "Computer and related services", "Other Business services", "Renting of machinery and equipment",
    "Real estate activities", "Legal Services", "Community, Social & personal services", "Other services",
    "Public administration. & defence",
)
assert len(PRODUCTS) == 155 and len(INDUSTRIES) == 67

FIRST_COL = 3  # column C = industry 1
FIRST_ROW = 3  # row 3 = product 1

# valuation / final-use columns after the 67 industries: published label -> item_code
SUPPLY_COLS = {
    "Supply at BP": "supply_bp",
    "Imports": "imports",
    "CIF Adj": "cif_adj",
    "Imports after cif adjustment": "imports_after_cif",
    "Import Duty": "import_duty",
    "Product taxes": "product_taxes",
    "Subsidy on Products": "product_subsidies",
    "Trade and Transport Margins": "ttm",
    "Supply at PP": "supply_pp",
}
USE_COLS = {
    "Intermediate Consumption": "ic_total",
    "PFCE": "pfce",
    "GFCE": "gfce",
    "GFCF": "gfcf",
    "CII": "cii",
    "Net Acquisition of Valuables": "valuables",
    "Export": "exports",
    "Total Use at PP": "total_use_pp",
}
# memo / total rows under the 155 products: published label -> product code
MEMO_ROWS = {
    "CIF": "cif",
    "Purchases of Residents abroad": "purchases_residents_abroad",
    "Purchases of Non-Residents in domestic market": "purchases_nonresidents_domestic",
}
TOTAL_ROW = {"supply": "Total Output", "use": "Total Use"}
VA_ROWS = {
    "GVA (by Production Approach)": "gva_production",
    "Production Taxes less Subsidies": "net_production_taxes",
    "Consumption of Fixed Capital": "cfc",
    "Compensation of Employees": "ce",
    "Operating Surplus": "os_mi",
    "GVA (by Income Approach)": "gva_income",
}


def product_code(n: int) -> str:
    return f"sut_p{n:03d}"


def industry_code(n: int) -> str:
    return f"sut_i{n:02d}"


def _col(n: int) -> str:
    return openpyxl.utils.get_column_letter(n)


def _expect(ws: Any, cell: str, text: str) -> None:
    got = clean_label(str(ws[cell].value or ""))
    if got != text:
        raise ValueError(f"sheet {ws.title!r} {cell}: expected {text!r}, found {got!r}")


@dataclass
class _Sheet:
    ws: Any
    extra: dict[int, str]  # column index -> item_code of the valuation/final-use columns
    rows: dict[int, str]  # row index -> product code (products + memo + total)
    total_row: int
    last_col: int


def _layout(ws: Any, kind: str) -> _Sheet:
    """Check the header and row labels; return where everything is. Raises on any surprise."""
    _expect(ws, "A1", {"supply": "Supply Table at Current Prices", "use": "Use Table at Current Prices"}[kind])
    _expect(ws, "A2", "Sl. No.")
    _expect(ws, "B2", "Product * Industry")
    units = [c for c in ws[1] if c.value and "crore" in str(c.value).lower()]
    if len(units) != 1 or clean_label(units[0].value) != "Values in Rs. Crore":
        raise ValueError(f"sheet {ws.title!r}: unit caption 'Values in Rs. Crore' not found in row 1")
    for i, name in enumerate(INDUSTRIES):
        _expect(ws, f"{_col(FIRST_COL + i)}2", name)
    want = SUPPLY_COLS if kind == "supply" else USE_COLS
    extra: dict[int, str] = {}
    c = FIRST_COL + len(INDUSTRIES)
    while ws.cell(2, c).value not in (None, "", " "):
        label = clean_label(str(ws.cell(2, c).value))
        if label not in want:
            raise ValueError(f"sheet {ws.title!r}: unexpected column header {label!r} at {_col(c)}2")
        extra[c] = want[label]
        c += 1
    if sorted(extra.values()) != sorted(want.values()):
        raise ValueError(f"sheet {ws.title!r}: columns {sorted(set(want.values()) - set(extra.values()))} missing")
    last_col = c - 1
    # nothing to the right of the last header
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=last_col + 1, max_col=ws.max_column):
        for cell in row:
            if cell.row > 1 and cell.value not in (None, "", " "):
                raise ValueError(f"sheet {ws.title!r}: value outside the table at {cell.coordinate}")
    rows: dict[int, str] = {}
    for i, name in enumerate(PRODUCTS, start=1):
        r = FIRST_ROW + i - 1
        if ws.cell(r, 1).value != i:
            raise ValueError(f"sheet {ws.title!r}: A{r} should be serial {i}, found {ws.cell(r, 1).value!r}")
        _expect(ws, f"B{r}", name)
        rows[r] = product_code(i)
    r = FIRST_ROW + len(PRODUCTS)
    for label, code in MEMO_ROWS.items():
        _expect(ws, f"B{r}", label)
        rows[r] = code
        r += 1
    _expect(ws, f"B{r}", TOTAL_ROW[kind])
    rows[r] = "total"
    return _Sheet(ws, extra, rows, r, last_col)


def _prod_label(ws: Any, r: int) -> str:
    return clean_label(str(ws.cell(r, 2).value))


def _read_sheet(
    ctx: BuildContext, raw: RawFile, period: str, ws: Any, kind: str, notes: str | None
) -> list[dict[str, Any]]:
    lay = _layout(ws, kind)
    table = "Supply Table" if kind == "supply" else "Use Table"
    matrix_item = "output" if kind == "supply" else "ic"
    prod_rows = sorted(r for r, c in lay.rows.items() if c.startswith("sut_p"))
    memo_rows = sorted(r for r, c in lay.rows.items() if not c.startswith("sut_p"))
    ind_last = FIRST_COL + len(INDUSTRIES) - 1

    def prov(rows_: str, cols_: str, what: str) -> str:
        return ctx.prov(
            raw=raw,
            table_id=f"{table} {period}",
            locator=f"sheet '{ws.title}', {rows_}, {cols_} ({what}); product rows matched by serial number and "
            "label, columns by header label",
            unit_as_published="Rs crore ('Values in Rs. Crore', row 1)",
            price_basis="current",
            base_year=BASE_YEAR,
            vintage=VINTAGE,
            release=RELEASE,
            notes=notes,
        )

    p_matrix = prov(
        f"rows {prod_rows[0]}-{prod_rows[-1]} (products 1-155)",
        f"cols {_col(FIRST_COL)}:{_col(ind_last)} (industries 1-67)",
        "domestic output at basic prices" if kind == "supply" else "intermediate consumption at purchasers' prices",
    )
    p_memo = prov(
        f"rows {memo_rows[0]}-{memo_rows[-1]} (memo rows and '{TOTAL_ROW[kind]}')",
        f"cols {_col(FIRST_COL)}:{_col(lay.last_col)}",
        "memo and total rows",
    )
    p_extra = prov(
        f"rows {prod_rows[0]}-{prod_rows[-1]} (products 1-155)",
        f"cols {_col(ind_last + 1)}:{_col(lay.last_col)}",
        "valuation columns" if kind == "supply" else "total IC and final-use columns",
    )
    out: list[dict[str, Any]] = []
    for r, pcode in lay.rows.items():
        plabel = _prod_label(ws, r)
        for c in range(FIRST_COL, lay.last_col + 1):
            v = parse_number(ws.cell(r, c).value)
            if v is None:
                continue
            if c <= ind_last:
                icode, item = industry_code(c - FIRST_COL + 1), matrix_item
                col_label = INDUSTRIES[c - FIRST_COL]
            else:
                icode, item = None, lay.extra[c]
                col_label = clean_label(str(ws.cell(2, c).value))
            pid = p_memo if not pcode.startswith("sut_p") else (p_matrix if icode else p_extra)
            sid = f"{kind}.{item}.{pcode}" + (f".{icode}" if icode else "") + ".current"
            out.append(
                {
                    "series_id": sid,
                    "source_id": SRC,
                    "table_id": f"{table} {period}",
                    "item_code": item,
                    "item_label": f"{plabel} | {col_label}",
                    "product": pcode,
                    "industry": icode,
                    "geography": "IN",
                    "dim_other": SWAP_FLAG.get(pcode),
                    "stock_flow": "flow",
                    "period": period,
                    "period_type": "fy",
                    "value": v,
                    "unit": "INR_crore",
                    "price_basis": "current",
                    "base_year": BASE_YEAR,
                    "vintage": VINTAGE,
                    "estimate_stage": STAGE,
                    "status": "official",
                    "prov_id": pid,
                }
            )
    return out


def _read_va(ctx: BuildContext, raw: RawFile, period: str, ws: Any) -> list[dict[str, Any]]:
    lay = _layout(ws, "use")
    found: dict[str, int] = {}
    for r in range(lay.total_row + 1, ws.max_row + 1):
        label = ws.cell(r, 2).value
        if label in (None, "", " "):
            # an empty row must be empty everywhere
            if any(ws.cell(r, c).value not in (None, "", " ") for c in range(1, lay.last_col + 1)):
                raise ValueError(f"sheet {ws.title!r}: row {r} has numbers but no label")
            continue
        label = clean_label(str(label))
        if label not in VA_ROWS:
            raise ValueError(f"sheet {ws.title!r}: unexpected value-added row label {label!r} at B{r}")
        found[VA_ROWS[label]] = r
    if sorted(found) != sorted(VA_ROWS.values()):
        raise ValueError(f"sheet {ws.title!r}: value-added rows missing: {sorted(set(VA_ROWS.values()) - set(found))}")
    ind_last = FIRST_COL + len(INDUSTRIES) - 1
    rr = sorted(found.values())
    pid = ctx.prov(
        raw=raw,
        table_id=f"Use Table {period} (value-added block)",
        locator=f"sheet '{ws.title}', rows {rr[0]}-{rr[-1]} (GVA production, net production taxes, CFC, CE, OS/MI, "
        f"GVA income), cols {_col(FIRST_COL)}:{_col(ind_last)} (industries 1-67); rows matched by label",
        unit_as_published="Rs crore ('Values in Rs. Crore', row 1)",
        price_basis="current",
        base_year=BASE_YEAR,
        vintage=VINTAGE,
        release=RELEASE,
    )
    out = []
    for item, r in found.items():
        label = clean_label(str(ws.cell(r, 2).value))
        for c in range(FIRST_COL, ind_last + 1):
            v = parse_number(ws.cell(r, c).value)
            if v is None:
                raise ValueError(f"sheet {ws.title!r}: blank value-added cell {_col(c)}{r}")
            icode = industry_code(c - FIRST_COL + 1)
            out.append(
                {
                    "series_id": f"va.{item}.{icode}.current",
                    "source_id": SRC,
                    "table_id": f"Use Table {period} (value-added block)",
                    "item_code": item,
                    "item_label": f"{label} | {INDUSTRIES[c - FIRST_COL]}",
                    "industry": icode,
                    "geography": "IN",
                    "stock_flow": "flow",
                    "period": period,
                    "period_type": "fy",
                    "value": v,
                    "unit": "INR_crore",
                    "price_basis": "current",
                    "base_year": BASE_YEAR,
                    "vintage": VINTAGE,
                    "estimate_stage": STAGE,
                    "status": "official",
                    "prov_id": pid,
                }
            )
        for c in range(ind_last + 1, lay.last_col + 1):
            if ws.cell(r, c).value not in (None, "", " "):
                raise ValueError(f"sheet {ws.title!r}: unexpected value-added total at {_col(c)}{r}")
    return out


def build_sut(ctx: BuildContext) -> list[Dataset]:
    supply: list[dict[str, Any]] = []
    use: list[dict[str, Any]] = []
    va: list[dict[str, Any]] = []
    for name, (period, sha_prefix) in FILES.items():
        raw = ctx.raw(SRC, name)
        if not raw.sha256.startswith(sha_prefix):
            raise ValueError(
                f"{name}: sha256 {raw.sha256[:12]} is not the 31-Aug-2026 file ({sha_prefix}...) the unit was written "
                "against: MoSPI replaced the file. Record the revision in docs/phase1/issues/io_tables.md, re-check the "
                "anchor values and update VINTAGE/FILES."
            )
        wb = openpyxl.load_workbook(raw.path, data_only=True)
        want = [f"Supply Table {period}", f"Use Table {period}"]
        if wb.sheetnames != want:
            raise ValueError(f"{name}: sheets {wb.sheetnames}, expected {want}")
        notes = SWAP_NOTE if period == "2023-24" else None
        supply += _read_sheet(ctx, raw, period, wb[want[0]], "supply", notes)
        use += _read_sheet(ctx, raw, period, wb[want[1]], "use", notes)
        va += _read_va(ctx, raw, period, wb[want[1]])
    return [
        Dataset(
            "io_tables_sut_supply",
            pl.DataFrame(supply, infer_schema_length=None),
            "SUT Supply table 2022-23 and 2023-24 (155 products x 67 industries + valuation columns), Rs crore",
        ),
        Dataset(
            "io_tables_sut_use",
            pl.DataFrame(use, infer_schema_length=None),
            "SUT Use table 2022-23 and 2023-24 at purchasers' prices (155 x 67 IC + final uses), Rs crore",
        ),
        Dataset(
            "io_tables_sut_va",
            pl.DataFrame(va),
            "SUT value-added block by 67 industries (GVA, net production taxes, CFC, CE, OS/MI), 2022-23 and 2023-24",
        ),
    ]
