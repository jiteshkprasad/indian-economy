"""SEBI Handbook of Statistics on the Indian Securities Market 2025-26 (released 17 Aug 2026): parsers.

One pinned XLSX per published table. Each table is described by its title, the header cells it
must show and a column map; data rows are the rows whose first cell is a fiscal year (or, for
Table 72, a month). Anything else in column A ends the block. Notes and derived columns
(percentages, growth) are not read.

Third-party content: the Handbook marks some tables 'Source: NSDL' (T59, T60, T63), 'Source: AMFI'
(T69, T72), 'Source: NSE/BSE' (T1, T7, T8, T14) or 'Source: RBI' (T58). SEBI's reproduction
permission does not extend to third-party material (registry licence note); the pipeline uses the
numbers internally, and publication needs the holders' permission (logged in the issues file).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from pipeline.core.unit import BuildContext, Dataset
from pipeline.core.units import conversion_note, to_inr_crore

from .common import Rows, cell_text, expect, frame, fy_end, fy_label, load_xlsx, month_end, num

SRC = "sebi_handbook_statistics"
VINTAGE = "2026-08-17"
RELEASE = "SEBI Handbook of Statistics on Indian Securities Market 2025-26 (released 17 Aug 2026)"

# kinds of columns: (clean unit, unit_as_published, conversion, factor)
KINDS = {
    "crore": ("INR_crore", "Rs crore", "none", 1.0),
    "count": ("count", "number", "none", 1.0),
    "usd_mn": ("USD_million", "US$ million", "none", 1.0),
    "inr_bn": ("INR_crore", "Rs billion", conversion_note("INR_billion"), 100.0),
    "lakh_count": ("count", "lakh (number)", "x 100,000 (lakh -> count)", 1e5),
}


@dataclass(frozen=True)
class Col:
    col: str  # column letter
    code: str  # item code (unique within the table)
    label: str  # published header text (joined levels)
    kind: str  # key of KINDS
    dims: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Table:
    num: str  # published table number
    raw: str  # pinned raw file name
    sheet: str
    title: str
    headers: tuple[tuple[str, str], ...]  # (cell, text it must contain)
    cols: tuple[Col, ...]
    first_row: int
    stock: bool = False  # True: values are stocks at the end of the fiscal year
    notes: str | None = None


def _c(col: str, code: str, label: str, kind: str = "crore", **dims: str) -> Col:
    return Col(col, code, label, kind, tuple(sorted(dims.items())))


T1 = Table("1", "hbs2526_t1_a.xlsx", "1A", "Table 1: Resource Mobilisation through Public and Rights",
           (("A2", "Period"), ("B2", "Total"), ("D3", "IPOs (Mainboard)"), ("F3", "IPOs (SME platform)"),
            ("J3", "FPOs"), ("L3", "Rights"), ("C4", "crore"), ("M4", "crore")),
           (_c("B", "total_issues", "Total: No. of issues", "count"), _c("C", "total_amount", "Total: Amount"),
            _c("D", "ipo_mainboard_issues", "IPOs (Mainboard): No. of issues", "count"),
            _c("E", "ipo_mainboard_amount", "IPOs (Mainboard): Amount"),
            _c("F", "ipo_sme_issues", "IPOs (SME platform): No. of issues", "count"),
            _c("G", "ipo_sme_amount", "IPOs (SME platform): Amount"),
            _c("H", "ipo_total_issues", "IPOs Total: No. of issues", "count"),
            _c("I", "ipo_total_amount", "IPOs Total: Amount"),
            _c("J", "fpo_issues", "FPOs: No. of issues", "count"), _c("K", "fpo_amount", "FPOs: Amount"),
            _c("L", "rights_issues", "Rights: No. of issues", "count"), _c("M", "rights_amount", "Rights: Amount")),
           5, notes="Equity public and rights issues by listing date; Source: NSE/BSE/MSEI")
T7 = Table("7", "hbs2526_t7_a.xlsx", "7A", "Table 7: Resource Mobilisation through Public Issue of C",
           (("A2", "Year"), ("B2", "No. of Issues"), ("C2", "Rs. crore")),
           (_c("B", "issues", "No. of Issues", "count"), _c("C", "amount", "Amount")), 3,
           notes="Public issues of corporate bonds by closing date; Source: BSE and NSE")
T8 = Table("8", "hbs2526_t8_a.xlsx", "8A", "Table 8: Resource Mobilisation through Private Placement",
           (("A2", "Period"), ("B2", "Only BSE"), ("D2", "Only NSE"), ("F2", "Both NSE and BSE"), ("H2", "Total"),
            ("C3", "crore"), ("I3", "crore")),
           (_c("B", "bse_only_issues", "Only BSE: No of issues (ISINs)", "count"), _c("C", "bse_only_amount", "Only BSE: Amount"),
            _c("D", "nse_only_issues", "Only NSE: No of issues (ISINs)", "count"), _c("E", "nse_only_amount", "Only NSE: Amount"),
            _c("F", "both_issues", "Both NSE and BSE: No of issues (ISINs)", "count"),
            _c("G", "both_amount", "Both NSE and BSE: Amount"),
            _c("H", "total_issues", "Total: No of issues (ISINs)", "count"), _c("I", "total_amount", "Total: Amount")),
           4, notes="Private placement of corporate debt listed on BSE/NSE; Source: NSE/BSE")
T11 = Table("11", "hbs2526_t11_a.xlsx", "11A", "Table 11: Outstanding corporate bonds",
            (("H1", "Crore"), ("A2", "As at the end of the Financial Year"), ("B2", "No. of Issuers"),
             ("C2", "Financial Corporations"), ("F2", "Non-Financial Corporations"), ("C3", "Listed"), ("D3", "Unlisted"),
             ("F3", "Listed"), ("G3", "Unlisted"), ("I2", "Total Value of Outstanding Corporate Bonds")),
            (_c("B", "issuers", "No. of Issuers", "count"),
             _c("C", "outstanding", "Financial Corporations: Listed corporate bonds", institution="fc", dim_other="listing=listed"),
             _c("D", "outstanding", "Financial Corporations: Unlisted corporate bonds", institution="fc", dim_other="listing=unlisted"),
             _c("E", "outstanding", "Total value of corporate bonds issued by Financial Corporations", institution="fc", dim_other="listing=all"),
             _c("F", "outstanding", "Non-Financial Corporations: Listed corporate bonds", institution="nfc", dim_other="listing=listed"),
             _c("G", "outstanding", "Non-Financial Corporations: Unlisted corporate bonds", institution="nfc", dim_other="listing=unlisted"),
             _c("H", "outstanding", "Total value of corporate bonds issued by Non-Financial Corporations", institution="nfc", dim_other="listing=all"),
             _c("I", "outstanding", "Total value of outstanding corporate bonds", institution="all_corporations", dim_other="listing=all")),
            4, stock=True, notes="Source: SEBI")
T13 = Table("13", "hbs2526_t13_a.xlsx", "13A", "Table 13: Fund raising by REITs and InvITs",
            (("B2", "REITs"), ("D2", "InvITs"), ("H2", "Total"), ("B3", "Listed"), ("D3", "Public Issue"),
             ("F3", "Private Placement"), ("C4", "Crore"), ("I4", "Crore")),
            (_c("B", "reit_listed_issues", "REITs listed: Number of issues", "count"), _c("C", "reit_listed_amount", "REITs listed: Amount"),
             _c("D", "invit_public_issues", "InvITs public issue: Number of issues", "count"),
             _c("E", "invit_public_amount", "InvITs public issue: Amount"),
             _c("F", "invit_private_issues", "InvITs private placement: Number of issues", "count"),
             _c("G", "invit_private_amount", "InvITs private placement: Amount"),
             _c("H", "total_issues", "Total: Number of issues", "count"), _c("I", "total_amount", "Total: Amount")),
            5, notes="Source: SEBI")
T14 = Table("14", "hbs2526_t14_a.xlsx", "14A", "Table 14: Funds Mobilised by all instruments",
            (("B2", "Equity (Public issues)"), ("D2", "Equity (QIP &Preferential)"), ("F2", "Debt (Public issues)"),
             ("H2", "Debt (Private Placement)"), ("J2", "REITs/InvITs"), ("L2", "Total Funds Mobilized"),
             ("C3", "crore"), ("M3", "crore")),
            (_c("B", "equity_public_issues", "Equity (Public issues): No. of issues", "count"),
             _c("C", "equity_public_amount", "Equity (Public issues): Amount"),
             _c("D", "equity_qip_pref_issues", "Equity (QIP & Preferential): No. of issues", "count"),
             _c("E", "equity_qip_pref_amount", "Equity (QIP & Preferential): Amount"),
             _c("F", "debt_public_issues", "Debt (Public issues): No. of issues", "count"),
             _c("G", "debt_public_amount", "Debt (Public issues): Amount"),
             _c("H", "debt_private_placement_issues", "Debt (Private Placement): No. of issues", "count"),
             _c("I", "debt_private_placement_amount", "Debt (Private Placement): Amount"),
             _c("J", "reit_invit_issues", "REITs/InvITs: No. of issues", "count"),
             _c("K", "reit_invit_amount", "REITs/InvITs: Amount"),
             _c("L", "total_issues", "Total Funds Mobilized: No. of issues", "count"),
             _c("M", "total_amount", "Total Funds Mobilized: Amount")),
            4, notes="Source: NSE, BSE and SEBI")
T23 = Table("23", "hbs2526_t23_a.xlsx", "23A", "Table 23: Averages of Major Indices and Market Capitali",
            (("B2", "BSE"), ("F2", "NSE"), ("J2", "MSEI"), ("C3", "Market Capitalisation"), ("G3", "Market Capitalisation"),
             ("K3", "Market Capitalisation"), ("C3", "crore"), ("G3", "crore"), ("K3", "crore")),
            (_c("C", "market_cap", "BSE market capitalisation (end of period)", dim_other="exchange=bse"),
             _c("G", "market_cap", "NSE market capitalisation (end of period)", dim_other="exchange=nse"),
             _c("K", "market_cap", "MSEI market capitalisation (end of period)", dim_other="exchange=msei")),
            4, stock=True,
            notes="Only the market-capitalisation columns are read ('Market capitalisation is as at the end of period'); "
            "index averages are not ingested. Sources: BSE, NSE, MSEI")
T58 = Table("58", "hbs2526_t58_a.xlsx", "58A", "Table 58: Foreign Investment Inflows",
            (("B2", "Gross inflows/Gross Investments"), ("D2", "Repatriation/ Disinvestment"),
             ("F2", "Direct Investment to India"), ("H2", "FDI by India"), ("J2", "Net Foreign Direct Investment"),
             ("L2", "Net Portfolio Investment"), ("N2", "Total"), ("B3", "Billion"), ("C3", "US $ Million"),
             ("N3", "Billion"), ("O3", "US $ Million")),
            tuple(
                c
                for code, lab, cb, cu in (
                    ("fdi_gross_inflows", "Gross inflows/Gross investments", "B", "C"),
                    ("fdi_repatriation", "Repatriation/Disinvestment", "D", "E"),
                    ("fdi_direct_investment_to_india", "Direct investment to India", "F", "G"),
                    ("fdi_by_india", "FDI by India", "H", "I"),
                    ("fdi_net", "Net foreign direct investment", "J", "K"),
                    ("portfolio_net", "Net portfolio investment", "L", "M"),
                    ("total_foreign_investment_net", "Total (net FDI + net portfolio)", "N", "O"),
                )
                for c in (_c(cb, code, lab, "inr_bn"), _c(cu, code, lab, "usd_mn"))
            ),
            4, notes="BoP-basis foreign investment; Source: RBI. The rupee caption is printed with a garbled glyph "
            "('` Billion'), read as Rs billion. Signs as printed (table note 3: 'Negative (-) sign indicates outflow "
            "(except in case of FDI by India)'): fdi_repatriation and fdi_by_india are printed positive but are "
            "OUTFLOWS; direct investment to India = gross inflows - repatriation; net FDI = direct investment to "
            "India - FDI by India (2023-24 US$ mn: 71,302 - 44,472 = 26,830; 26,830 - 16,678 = 10,152). Do not add "
            "these columns without the sign.")
T59 = Table("59", "hbs2526_t59_a.xlsx", "59A", "Table 59: Trends in Foreign Portfolio Investment",
            (("B2", "Gross Purchases"), ("B2", "crore"), ("C2", "Gross Sales"), ("D2", "Net Investment"),
             ("E2", "US $ mn"), ("F2", "Cumulative Net Investment")),
            (_c("B", "gross_purchases", "Gross purchases"), _c("C", "gross_sales", "Gross sales"),
             _c("D", "net_investment", "Net investment"), _c("E", "net_investment", "Net investment", "usd_mn")),
            4, notes="FPI flows (all instruments), conversion at daily RBI reference rate; Source: SEBI, NSDL & CDSL; "
            "'2025-26$' = as on 31 March 2026. The cumulative column is not read (a running sum).")
T60 = Table("60", "hbs2526_t60_a.xlsx", "60A", "Table 60: Foreign Portfolio Investment Instrument wise",
            (("B2", "Equity"), ("C2", "Debt"), ("D2", "Debt-VRR"), ("E2", "Debt-FAR"), ("F2", "Hybrid"),
             ("G2", "AIFs/MFs"), ("H2", "Total"), ("B2", "crore"), ("H2", "crore")),
            (_c("B", "net_investment", "Equity", instrument="equity"), _c("C", "net_investment", "Debt (general limit)", instrument="debt_general"),
             _c("D", "net_investment", "Debt-VRR", instrument="debt_vrr"), _c("E", "net_investment", "Debt-FAR", instrument="debt_far"),
             _c("F", "net_investment", "Hybrid", instrument="hybrid"), _c("G", "net_investment", "AIFs/MFs", instrument="aif_mf"),
             _c("H", "net_investment", "Total", instrument="total")),
            4, notes="FPI net investment by instrument; '-' = category not yet in existence; Source: NSDL")
_T62_CATS = (
    ("B", "fpi_fii_sa", "FPI / FII/SA"), ("D", "insurance_companies", "Insurance Company"),
    ("F", "mutual_funds", "Mutual Funds"), ("H", "fdi_investments", "FDI Investments"),
    ("J", "foreign_depositories", "Foreign Depository"), ("L", "banks", "Banks"),
    ("N", "financial_institutions", "Financial Institutions"), ("P", "local_pension_funds", "Local Pension Funds"),
    ("R", "fvci", "Foreign Venture Capital Investment"), ("T", "corporates", "Corporates"),
    ("V", "pms", "Portfolio Management Services"), ("X", "nris", "NRIs"), ("Z", "gdrs", "Global Depository Receipts"),
    ("AB", "ocbs", "OCBs"), ("AD", "others", "Others"), ("AF", "total", "Total"),
)


def _next(col: str) -> str:
    from openpyxl.utils import column_index_from_string, get_column_letter

    return get_column_letter(column_index_from_string(col) + 1)


T62 = Table("62", "hbs2526_t62_a.xlsx", "62A", "Table 62: Assets under the Custody of Custodians",
            (("AF2", "crore"), ("A3", "Period"), *((f"{c}3", lab) for c, _, lab in _T62_CATS), ("B4", "No."), ("C4", "Amt")),
            tuple(
                c
                for col, code, lab in _T62_CATS
                for c in (_c(col, "clients", f"{lab}: No. of clients", "count", counterparty=code),
                          _c(_next(col), "assets_under_custody", f"{lab}: Amount", counterparty=code))
            ),
            5, stock=True, notes="Assets under custody of custodians by client type, end of FY; Source: SEBI")
_T63_BLOCKS = (("B", "category_i", "Category I"), ("G", "category_ii", "Category II"), ("L", "category_iii", "Category III"))
_T63_INSTR = (("equity", "Equity"), ("debt", "Debt"), ("debt_vrr", "Debt-VRR"), ("hybrid", "Hybrid"), ("total", "Total"))


def _shift(col: str, k: int) -> str:
    for _ in range(k):
        col = _next(col)
    return col


T63 = Table("63", "hbs2526_t63_a.xlsx", "63A", "Table 63: FPI/FII AUC category wise data",
            (("B2", "Category I"), ("G2", "Category II"), ("L2", "Category III"), ("B3", "Equity"), ("F3", "Total"),
             ("P3", "Total")),
            tuple(
                _c(_shift(c0, i), "assets_under_custody", f"{blab}: {ilab}", instrument=icode, dim_other=f"fpi_category={bcode}")
                for c0, bcode, blab in _T63_BLOCKS
                for i, (icode, ilab) in enumerate(_T63_INSTR)
            ),
            4, stock=True,
            notes="No unit caption is printed in Table 63; Rs crore inferred because Category I+II+III totals equal the "
            "FPI amount of Table 62 (captioned Rs crore) within Rs 2 crore at end-March 2016-2019 and 2024 and within "
            "0.1% in 2015 and 2020-2023 (they differ by 2-4% in 2025 and 2026). Source: NSDL")
T64 = Table("64", "hbs2526_t64_a.xlsx", "64A", "Table 64: Category-wise Resource Mobilisation by Mutual",
            (("A1", "crore"), ("B2", "Gross Mobilisation"), ("E2", "Redemption"), ("H2", "Net Inflow"),
             ("K2", "Assets at the End of"), ("B3", "Private Sector"), ("C3", "Public Sector"), ("D3", "Total")),
            (_c("B", "gross_mobilisation", "Gross mobilisation: Private sector", institution="mf_private"),
             _c("C", "gross_mobilisation", "Gross mobilisation: Public sector", institution="mf_public"),
             _c("D", "gross_mobilisation", "Gross mobilisation: Total", institution="mf_all"),
             _c("E", "redemption", "Redemption: Private sector", institution="mf_private"),
             _c("F", "redemption", "Redemption: Public sector", institution="mf_public"),
             _c("G", "redemption", "Redemption: Total", institution="mf_all"),
             _c("H", "net_inflow", "Net inflow: Private sector", institution="mf_private"),
             _c("I", "net_inflow", "Net inflow: Public sector", institution="mf_public"),
             _c("J", "net_inflow", "Net inflow: Total", institution="mf_all")),
            5, notes="Rs crore per the title caption in A1 ('Table 64: Category-wise Resource Mobilisation by Mutual "
            "Funds (₹ crore)'). Source: SEBI")
T64_STOCK = Table("64", "hbs2526_t64_a.xlsx", "64A", T64.title, (("K2", "Assets at the End of"),),
                  (_c("K", "assets_end_of_period", "Assets at the end of period", institution="mf_all"),), 5, stock=True,
                  notes=T64.notes)
T70 = Table("70", "hbs2526_t70_a.xlsx", "70A", "Table 70 Trends in Transactions on Stock Exchanges by Mu",
            (("B2", "Equity"), ("E2", "Debt"), ("H2", "Total"), ("B3", "Gross Purchase"), ("C3", "Gross Sales"),
             ("D3", "Net Purchase/Sales")),
            tuple(
                _c(_shift(c0, i), code, f"{ilab}: {lab}", instrument=icode)
                for c0, icode, ilab in (("B", "equity", "Equity"), ("E", "debt", "Debt"), ("H", "total", "Total"))
                for i, (code, lab) in enumerate((("gross_purchase", "Gross purchase"), ("gross_sales", "Gross sales"),
                                                 ("net_purchase", "Net purchase/sales")))
            ),
            5, notes="Transactions by mutual funds on stock exchanges; title says (Rs crore). Source: SEBI")

DATASETS: dict[str, tuple[str, tuple[Table, ...]]] = {
    "sebi_primary": ("SEBI Handbook 2025-26 primary market: equity public/rights (T1), bond public issues (T7), "
                     "debt private placement (T8), REIT/InvIT (T13), all instruments (T14), 2013-14 to 2025-26",
                     (T1, T7, T8, T13, T14)),
    "sebi_bonds_equity": ("SEBI Handbook 2025-26 outstanding corporate bonds by issuer sector (T11) and exchange "
                          "market capitalisation (T23), end-March 2013..2026", (T11, T23)),
    "sebi_foreign": ("SEBI Handbook 2025-26 foreign investment: FDI/FPI (T58, RBI), FPI flows (T59) and by instrument "
                     "(T60), custodian AUC by client (T62), FPI AUC by category (T63)", (T58, T59, T60, T62, T63)),
    "sebi_mf": ("SEBI Handbook 2025-26 mutual funds: mobilisation, redemption, net inflow and AUM (T64), exchange "
                "transactions (T70), SIP AUM (T69), unit-holding pattern monthly (T72)", (T64, T64_STOCK, T70)),
}


def _annual(rows: Rows, ctx: BuildContext, t: Table) -> None:
    raw = ctx.raw(SRC, t.raw)
    ws = load_xlsx(raw)[t.sheet]
    expect(ws, "A1", t.title)
    for cell, needle in t.headers:
        expect(ws, cell, needle)
    data: list[tuple[int, str]] = []
    r = t.first_row
    while r <= ws.max_row:
        a = ws.cell(r, 1).value
        try:
            fy = fy_label(a) if a is not None else None
        except ValueError:
            fy = None
        if fy is None:
            break
        data.append((r, fy))
        r += 1
    if len(data) < 10 or data[-1][1] != "2025-26":
        raise ValueError(f"SEBI T{t.num}: year rows {[f for _, f in data]} (expected ..2025-26)")
    by_kind: dict[str, list[Col]] = {}
    for c in t.cols:
        by_kind.setdefault(c.kind, []).append(c)
    for kind, cols in by_kind.items():
        unit, pub, conv, factor = KINDS[kind]
        pid = rows.prov(
            raw,
            table_id=f"Table {t.num}",
            locator=f"sheet '{t.sheet}', rows {data[0][0]}-{data[-1][0]} ({data[0][1]}..{data[-1][1]}), cols "
            f"{','.join(c.col for c in cols)}",
            unit_as_published=pub,
            conversion=conv,
            release=RELEASE,
            money=unit in ("INR_crore", "USD_million"),
            notes=t.notes,
        )
        for c in cols:
            dims = dict(c.dims)
            dim_key = ".".join(v.split("=")[-1] for _, v in c.dims)
            sid = f"t{t.num}.{c.code}" + (f".{dim_key}" if dim_key else "")
            sid += {"INR_crore": ".current", "USD_million": ".usd"}.get(unit, "")
            for rr, fy in data:
                v = num(ws[f"{c.col}{rr}"].value)
                if v is None:
                    continue
                rows.add(
                    prov_id=pid,
                    series_id=sid,
                    table_id=f"Table {t.num}",
                    item_code=c.code,
                    item_label=c.label,
                    value=v * factor if kind != "inr_bn" else to_inr_crore(v, "INR_billion"),
                    unit=unit,
                    stock_flow="stock" if t.stock else "flow",
                    period=fy_end(fy) if t.stock else fy,
                    period_type="date" if t.stock else "fy",
                    **dims,
                )


def _t69(rows: Rows, ctx: BuildContext) -> None:
    """SIPs: one block of 8 columns per year; the 'Total' row (T-30 + B-30)."""
    raw = ctx.raw(SRC, "hbs2526_t69_a.xlsx")
    ws = load_xlsx(raw)["69A"]
    expect(ws, "A1", "Table 69 Resource Mobilisation through Systematic")
    if cell_text(ws, 7, 1) != "Total":
        raise ValueError("SEBI T69: row 7 is not 'Total'")
    blocks = []
    c = 1
    while ws.cell(2, c).value is not None:
        blocks.append((c, fy_label(ws.cell(2, c).value)))
        c += 8
    if [f for _, f in blocks] != [f"{y}-{(y + 1) % 100:02d}" for y in range(2019, 2026)]:
        raise ValueError(f"SEBI T69: unexpected year blocks {blocks}")
    fields = (  # (column offset, code, label, kind, stock: False | "open" (31 March before the FY) | "close", header)
        (1, "sips_existing_beginning", "Existing SIPs at the beginning of the period (excluding STP)", "lakh_count", "open",
         "Existing at the beginning"),
        (2, "sips_registered", "SIPs registered during the period", "lakh_count", False, "Registered during"),
        (3, "sips_matured", "SIPs matured during the period", "lakh_count", False, "Matured during"),
        (4, "sips_terminated", "SIPs terminated prematurely during the period", "lakh_count", False,
         "Terminated prematurely"),
        (5, "sips_closing", "Closing no. of SIPs at the end of the period", "lakh_count", "close", "Closing no. of SIPs"),
        (7, "sip_aum_end", "SIP AUM at the end of the period", "crore", "close", "AUM at the end"),
    )
    for kind in ("lakh_count", "crore"):
        unit, pub, conv, _ = KINDS[kind]
        pid = rows.prov(
            raw, table_id="Table 69",
            locator="sheet '69A', row 7 ('Total'), one 8-column block per year (2019-20 at A:H .. 2025-26 at AW:BD); "
            f"{'columns +1..+5 (in lakh)' if kind == 'lakh_count' else 'column +7 (AUM end, Rs crore)'}",
            unit_as_published=pub, conversion=conv, release=RELEASE, money=unit == "INR_crore",
            notes="Source: AMFI. The opening-AUM column is not read (equals the previous year's closing AUM)."
            + (" 'Existing SIPs at the beginning of the period' is a stock dated 31 March before the FY (e.g. the "
               "2023-24 block's value is dated 2023-03-31); from 2023-24 it equals the previous block's closing count."
               if kind == "lakh_count" else ""),
        )
        for c0, fy in blocks:
            for off, code, label, k, stock, needle in fields:
                if k != kind:
                    continue
                hdr = cell_text(ws, 3, c0 + off)
                if needle.lower() not in hdr.lower():
                    raise ValueError(f"SEBI T69 {fy}: column +{off} header {hdr!r} does not match {label!r}")
                v = num(ws.cell(7, c0 + off).value)
                if v is None:
                    continue
                rows.add(prov_id=pid, series_id=f"t69.{code}" + (".current" if unit == "INR_crore" else ""),
                         table_id="Table 69", item_code=code, item_label=label,
                         value=v * KINDS[kind][3], unit=unit, stock_flow="stock" if stock else "flow",
                         period={"open": f"{int(fy[:4])}-03-31", "close": fy_end(fy)}.get(stock, fy),
                         period_type="date" if stock else "fy")


T72_COLS = (("B", "total", "Total AUM"), ("C", "corporates", "AUM held by Corporates"), ("D", "hnis", "AUM held by HNIs"),
            ("E", "retail", "AUM held by Retail Investors"), ("F", "banks", "AUM held by Banks"))


def _t72(rows: Rows, ctx: BuildContext) -> None:
    raw = ctx.raw(SRC, "hbs2526_t72_m.xlsx")
    ws = load_xlsx(raw)["72M"]
    expect(ws, "A1", "Table 72: Unit Holding Pattern of Mutual Funds")
    for cell, needle in (("A2", "Month"), ("B2", "TOTAL AUM (INR crore)"), ("C2", "AUM held by (in INR crore)"),
                         ("C3", "Corporates"), ("D3", "HNIs"), ("E3", "Retail Investors"), ("F3", "Banks")):
        expect(ws, cell, needle)
    data = []
    r = 4
    while isinstance(ws.cell(r, 1).value, dt.datetime):
        d = ws.cell(r, 1).value
        data.append((r, month_end(d.year, d.month)))
        r += 1
    if data[0][1] != "2013-04-30" or data[-1][1] != "2026-03-31":
        raise ValueError(f"SEBI T72: months {data[0][1]}..{data[-1][1]}")
    pid = rows.prov(
        raw, table_id="Table 72",
        locator=f"sheet '72M', rows {data[0][0]}-{data[-1][0]} (Apr-2013..Mar-2026), cols B:F; the percentage columns "
        "G:J are not read",
        unit_as_published="Rs crore", release=RELEASE, money=True,
        notes="Monthly unit-holding pattern; the month label (first of month) is read as the month-end position "
        "(Mar-2026 total equals T64 assets at end of 2025-26). Source: AMFI",
    )
    for col, code, label in T72_COLS:
        for rr, d in data:
            v = num(ws[f"{col}{rr}"].value)
            if v is None:
                continue
            rows.add(prov_id=pid, series_id=f"t72.aum.{code}.current", table_id="Table 72", item_code="aum_held_by",
                     item_label=label, value=v, unit="INR_crore", stock_flow="stock", period=d, period_type="date",
                     counterparty=code if code != "total" else "all_holders")


def build(ctx: BuildContext, unit: str) -> list[Dataset]:
    out = []
    for name, (desc, tables) in DATASETS.items():
        rows = Rows(ctx, SRC, VINTAGE)
        for t in tables:
            _annual(rows, ctx, t)
        if name == "sebi_mf":
            _t69(rows, ctx)
            _t72(rows, ctx)
        out.append(Dataset(f"{unit}_{name}", frame(rows.rows), desc))
    return out
