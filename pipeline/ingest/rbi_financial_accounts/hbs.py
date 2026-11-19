"""RBI Handbook of Statistics on the Indian Economy 2025-26 (31 Jul 2026): HTML table views.

The Handbook's XLSX/PDF copies sit on rbidocs.rbi.org.in (challenge-prone, DECISIONS D1-4); the
same tables are served as HTML on www.rbi.org.in (PublicationsView.aspx?id=...), which carry the
full history for the tables read here:
- T11  Sector-wise domestic saving (Rs crore): 2020-21..2022-23 on base 2011-12 and 2022-23..2024-25
       on base 2022-23 (a pre-NAS-2026 vintage of the new series).
- T12  Changes in financial assets/liabilities of households (Rs crore), 1983-84..2023-24, NAS 2025
       (old base 2011-12).
- T49  Consolidated balance sheet of scheduled commercial banks (excl. RRBs), end-March 2006..2025.
- T107 Ownership of Central dated securities, State securities and T-bills: totals (Rs crore) and
       holder shares (per cent), end-March 2022..2026.
- T109 Small savings receipts and outstandings (deposits, certificates, PPF), 1986-87..2024-25.
T39 (RBI liabilities and assets) is pinned but not ingested: its three-panel HTML layout with
bracketed memo rows needs a dedicated parser; FSF Statement 1.1 carries RBI's balance sheet.

Every header text used for column identity is asserted; rows are matched by label or year.
"""

from __future__ import annotations

import re
from typing import Any

import polars as pl
from bs4 import BeautifulSoup

from pipeline.core.unit import BuildContext, Dataset, RawFile
from pipeline.core.units import clean_label, normalize_fy, parse_number
from pipeline.ingest.rbi_financial_accounts import common as C


def _grids(raw: RawFile) -> list[list[list[str]]]:
    """Innermost tables with at least 3 rows, as lists of rows of cell texts."""
    soup = BeautifulSoup(raw.read_bytes(), "lxml")
    out = []
    for t in soup.find_all("table"):
        if t.find("table"):
            continue
        rows = [
            [clean_label(c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"])] for tr in t.find_all("tr")
        ]
        if len(rows) >= 3:
            out.append(rows)
    return out


def _title(raw: RawFile, n: int) -> str:
    soup = BeautifulSoup(raw.read_bytes(), "lxml")
    for s in soup.find_all(string=True):
        t = clean_label(s)
        if re.match(rf"^Table {n}\s*:", t, re.IGNORECASE):
            return t
    raise ValueError(f"HBS T{n}: title not found")


def _expect(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)


def _prov(
    ctx: BuildContext,
    raw: RawFile,
    n: int,
    locator: str,
    unit: str,
    *,
    base_year: str | None = None,
    price_basis: str = "current",
    notes: str | None = None,
) -> str:
    return ctx.prov(
        raw=raw,
        table_id=f"HBS Table {n}",
        locator=f"PublicationsView HTML table view of Table {n}: {locator}",
        unit_as_published=unit,
        conversion="none",
        price_basis=price_basis,
        base_year=base_year,
        vintage=C.HBS_VINTAGE,
        release=C.HBS_RELEASE,
        notes=notes,
    )


def _row(**kw: Any) -> dict[str, Any]:
    return {
        "source_id": C.SRC_HBS,
        "geography": "IN",
        "vintage": C.HBS_VINTAGE,
        "estimate_stage": "n.a.",
        "status": "official",
    } | kw


def _data_rows(grid: list[list[str]], numbering: list[str]) -> list[list[str]]:
    """Rows after the column-numbering row (e.g. ['1','2',...]) up to the first non-data row."""
    i = next(k for k, r in enumerate(grid) if r == numbering)
    out = []
    for r in grid[i + 1 :]:
        if len(r) != len(numbering):
            break
        out.append(r)
    return out


# ---------------------------------------------------------------------------------------------
# T11 sector-wise domestic saving
# ---------------------------------------------------------------------------------------------

T11_ITEMS = {
    "1 Gross Savings": ("gross_saving", None),
    "1.1 Non-financial corporations": ("gross_saving_nfc", "nfc"),
    "1.1.1 Public non-financial corporations": ("gross_saving_nfc_pub", "nfc_pub"),
    "1.1.1.1 Departmental enterprises": ("gross_saving_nfc_pub_dept", "nfc_pub_dept"),
    "1.1.1.2 Non-departmental enterprises": ("gross_saving_nfc_pub_nondept", "nfc_pub_nondept"),
    "1.1.2 Private non-financial corporations": ("gross_saving_nfc_pvt", "nfc_pvt"),
    "1.2 Financial corporations": ("gross_saving_fc", "fc"),
    "1.2.1 Public financial corporations": ("gross_saving_fc_pub", "fc_pub"),
    "1.2.1.1 Departmental enterprises": ("gross_saving_fc_pub_dept", "fc_pub_dept"),
    "1.2.1.2 Non-departmental enterprises": ("gross_saving_fc_pub_nondept", "fc_pub_nondept"),
    "1.2.2 Private financial corporations": ("gross_saving_fc_pvt", "fc_pvt"),
    "1.3 General Government": ("gross_saving_gg", "gg"),
    "1.4 Household sector": ("gross_saving_hh", "hh"),
    "1.4.1.1 Gross financial saving": ("gross_financial_saving_hh", "hh"),
    "1.4.1.2 Less financial liabilities": ("financial_liabilities_hh", "hh"),
    "1.4.2 Saving in physical assets": ("saving_physical_assets_hh", "hh"),
    "1.4.3 Saving in the form of gold and silver ornaments": ("saving_gold_silver_hh", "hh"),
}


def _t11(ctx: BuildContext) -> list[dict[str, Any]]:
    raw = ctx.raw(C.SRC_HBS, "hbs_t11.html")
    _expect("Sector-Wise Domestic Savings (At Current Prices)" in _title(raw, 11), "T11 title changed")
    (g,) = _grids(raw)
    _expect(g[0] == ["(Amount in ₹ Crore)"], f"T11 unit row {g[0]}")
    _expect(g[1] == ["Item", "2020-21", "2021-22", "2022-23", "2022-23", "2023-24", "2024-25"], f"T11 header {g[1]}")
    _expect(g[3] == ["", "(Base Year: 2011-12)", "(Base Year: 2022-23)"], f"T11 base row {g[3]}")
    cols = [
        (1, "2020-21", "2011-12"),
        (2, "2021-22", "2011-12"),
        (3, "2022-23", "2011-12"),
        (4, "2022-23", "2022-23"),
        (5, "2023-24", "2022-23"),
        (6, "2024-25", "2022-23"),
    ]
    rows_ = [r for r in g[4:] if len(r) == 7]
    labels = [r[0] for r in rows_]
    _expect(labels == list(T11_ITEMS), f"T11 item labels changed: {labels}")
    pids = {
        b: _prov(
            ctx,
            raw,
            11,
            f"rows '1 Gross Savings'..'1.4.3', {'cols 2-4' if b == '2011-12' else 'cols 5-7'} "
            f"(Base Year {b}); rows by label",
            "Rs crore",
            base_year=b,
            notes="Pre-NAS-2026 vintage; NAS 2026 (31 Aug 2026) supersedes the base 2022-23 columns.",
        )
        for b in ("2011-12", "2022-23")
    }
    out = []
    for r in rows_:
        code, inst = T11_ITEMS[r[0]]
        for c, fy, base in cols:
            v = parse_number(r[c])
            if v is None:
                raise ValueError(f"T11 {r[0]} {fy}: blank")
            out.append(
                _row(
                    series_id=f"t11.{code}.base{base[:4]}.current",
                    table_id="HBS Table 11",
                    item_code=code,
                    item_label=r[0],
                    institution=inst,
                    stock_flow="flow",
                    period=fy,
                    period_type="fy",
                    value=v,
                    unit="INR_crore",
                    price_basis="current",
                    base_year=base,
                    prov_id=pids[base],
                )
            )
    return out


# ---------------------------------------------------------------------------------------------
# T12 household financial assets / liabilities (flows)
# ---------------------------------------------------------------------------------------------

T12_ASSETS = [
    ("Currency", "currency"),
    ("Bank Deposits", "bank_deposits"),
    ("Non-Banking Deposits", "nonbank_deposits"),
    ("Life Insurance Fund", "life_insurance_fund"),
    ("Provident and Pension Fund", "pf_pension_fund"),
    ("Claims on Government", "claims_on_government"),
    ("Shares & Debentures", "shares_debentures"),
    ("Units of UTI", "units_of_uti"),
    ("Trade Debt (Net)", "trade_debt_net"),
    ("Changes in Financial Assets (2 To 10)", "financial_assets"),
]
T12_LIABS = [
    ("Bank Advances", "bank_advances"),
    ("Loans & Advances from Other Financial Institutions", "loans_from_ofi"),
    ("Loans & Advances from Government", "loans_from_government"),
    ("Loans & Advances from Co-Operative Non-Credit Societies", "loans_from_coop_noncredit"),
    ("Changes in Financial Liabilities (12 To 15)", "financial_liabilities"),
]


def _t12(ctx: BuildContext) -> list[dict[str, Any]]:
    raw = ctx.raw(C.SRC_HBS, "hbs_t12.html")
    _expect("Changes in Financial Assets/Liabilities of the Household Sector" in _title(raw, 12), "T12 title")
    g1, g2 = _grids(raw)
    out = []
    for g, items, side, nums in (
        (g1, T12_ASSETS, "assets", [str(i) for i in range(1, 12)]),
        (g2, T12_LIABS, "liabilities", ["1"] + [str(i) for i in range(12, 17)]),
    ):
        hdr = next(r for r in g if r and r[0] == "Year")
        _expect(hdr[1:] == [lab for lab, _ in items], f"T12 {side} header {hdr}")
        _expect(any(r == ["(₹ Crore)"] for r in g), f"T12 {side}: unit row missing")
        data = _data_rows(g, nums)
        years = [normalize_fy(r[0]) for r in data]
        _expect(
            years[0] == "1983-84" and years[-1] == "2023-24" and len(years) == 41, f"T12 {side} years {years[:2]}.."
        )
        # NAS 2025 (base 2011-12) starts in 2011-12. Earlier rows are the older-base series the table
        # carries back to 1983-84; the table does not say which base, so base_year is left null there.
        pids = {
            new: _prov(
                ctx,
                raw,
                12,
                f"{side} panel (cols {nums[1]}-{nums[-1]}), rows "
                f"{'2011-12..2023-24' if new else '1983-84..2010-11'}; '-' = not available (no row)",
                "Rs crore",
                base_year="2011-12" if new else None,
                notes="Table note 1: as per National Accounts Statistics 2025 (old base 2011-12)."
                if new
                else "Years before 2011-12 predate the 2011-12 NAS series; the table splices in earlier-base "
                "figures without saying which base (base_year left null). Expect level breaks at the earlier "
                "base changes (e.g. 2004-05, 2011-12).",
            )
            for new in (True, False)
        }
        for r in data:
            fy = normalize_fy(r[0])
            new = fy >= "2011-12"
            for (label, code), cell in zip(items, r[1:], strict=True):
                v = parse_number(cell)
                if v is None:
                    continue  # '-' printed: not available
                out.append(
                    _row(
                        series_id=f"t12.{side}.{code}.current",
                        table_id="HBS Table 12",
                        item_code=code,
                        item_label=label,
                        institution="hh",
                        side=side,
                        stock_flow="flow",
                        period=fy,
                        period_type="fy",
                        value=v,
                        unit="INR_crore",
                        price_basis="current",
                        base_year="2011-12" if new else None,
                        prov_id=pids[new],
                    )
                )
    return out


# ---------------------------------------------------------------------------------------------
# T49 consolidated balance sheet of SCBs
# ---------------------------------------------------------------------------------------------

T49_LIABS = [
    ("Capital", "capital"),
    ("Reserves & Surplus", "reserves_surplus"),
    ("Deposits", "deposits"),
    ("Borrowings", "borrowings"),
    ("Other Liabilities and Provisions", "other_liabilities_provisions"),
]
T49_ASSETS = [
    ("Cash and Balances with RBI", "cash_balances_rbi"),
    ("Balances with Banks and Money at Call and Short Notice", "balances_banks_call_money"),
    ("Investments", "investments"),
    ("Loans and Advances", "loans_advances"),
    ("Fixed Assets", "fixed_assets"),
    ("Other Assets", "other_assets"),
    ("Total Liabilities/ Assets", "total"),
]


def _t49(ctx: BuildContext) -> list[dict[str, Any]]:
    raw = ctx.raw(C.SRC_HBS, "hbs_t49.html")
    _expect("Consolidated Balance Sheet of Scheduled Commercial Banks" in _title(raw, 49), "T49 title")
    g1, g2 = _grids(raw)
    _expect(
        g1[0] == ["(₹ Crore)"] and g1[1][1] == "Liabilities" and g1[2] == [lab for lab, _ in T49_LIABS],
        f"T49 liabilities header {g1[:3]}",
    )
    _expect(
        g2[0][1:] == ["Assets", "Total Liabilities/ Assets"] and g2[1] == [lab for lab, _ in T49_ASSETS[:-1]],
        f"T49 assets header {g2[:2]}",
    )
    out = []
    for g, items, side, nums in (
        (g1, T49_LIABS, "liabilities", [str(i) for i in range(1, 7)]),
        (g2, T49_ASSETS, "assets", ["1"] + [str(i) for i in range(7, 14)]),
    ):
        data = _data_rows(g, nums)
        _expect(data[0][0] == "2005-06" and len(data) == 20, f"T49 {side} years {data[0][0]}..{data[-1][0]}")
        pid = _prov(
            ctx,
            raw,
            49,
            f"{side} panel (cols {nums[1]}-{nums[-1]}), rows end-March 2006..2025 (printed '2005-06'..'2024-25')",
            "Rs crore",
        )
        for r in data:
            fy = normalize_fy(r[0])
            date = f"{int(fy[:4]) + 1}-03-31"
            for (label, code), cell in zip(items, r[1:], strict=True):
                v = parse_number(cell)
                if v is None:
                    raise ValueError(f"T49 {side} {fy} {code}: blank")
                out.append(
                    _row(
                        series_id=f"t49.{'total' if code == 'total' else side}.{code}.current",
                        table_id="HBS Table 49",
                        item_code=code,
                        item_label=label,
                        institution="fc_odc_scb_excl_rrb",
                        side=None if code == "total" else side,
                        stock_flow="stock",
                        period=date,
                        period_type="date",
                        value=v,
                        unit="INR_crore",
                        price_basis="current",
                        prov_id=pid,
                    )
                )
    return out


# ---------------------------------------------------------------------------------------------
# T107 ownership of government securities
# ---------------------------------------------------------------------------------------------

T107_PANELS = {
    "Central Government Dated Securities": "gsec_central",
    "State Governments Securities": "sgs",
    "Treasury Bills": "tbills",
}
T107_HOLDERS = {
    "1 Commercial Banks": "commercial_banks",
    "2 Co-operative Banks": "cooperative_banks",
    "3 Non-Bank PDs": "non_bank_pds",
    "4 Insurance Companies": "insurance",
    "5 Mutual Funds": "mutual_funds",
    "6 Provident Funds": "provident_funds",
    "7 Pension Funds": "pension_funds",
    "8 Financial Institutions": "financial_institutions",
    "9 Corporates": "corporates",
    "10 Foreign Portfolio Investors": "fpi",
    "11 RBI": "rbi",
    "12 Others": "others",
    "12.1 State Governments": "others_state_governments",
}


def _t107(ctx: BuildContext) -> list[dict[str, Any]]:
    raw = ctx.raw(C.SRC_HBS, "hbs_t107.html")
    _expect("Ownership Pattern of Central and State Government Securities" in _title(raw, 107), "T107 title")
    grids = _grids(raw)
    _expect(len(grids) == 3 and grids[0][0] == ["(Per cent)"], "T107: expected three panels in per cent")
    out = []
    for g in grids:
        hi = next(k for k, r in enumerate(g) if r and r[0] == "Category")
        instr = T107_PANELS[g[hi][1]]
        years = g[hi + 1]
        _expect(years == ["2022", "2023", "2024", "2025", "2026"], f"T107 years {years}")
        _expect(g[hi + 2] == [str(i) for i in range(1, 7)], f"T107 numbering {g[hi + 2]}")
        dates = [f"{y}-03-31" for y in years]
        body = [r for r in g[hi + 3 :] if len(r) == 6]
        total = body[0]
        _expect(re.match(r"^\([ABC]\) Total \(in ₹\. Crore\)$", total[0]) is not None, f"T107 total row {total[0]}")
        labels = [r[0] for r in body[1:]]
        _expect(labels == list(T107_HOLDERS), f"T107 {instr} holders {labels}")
        pid_amt = _prov(
            ctx, raw, 107, f"panel '{g[hi][1]}', row '{total[0]}', cols 2-6 (31 March 2022..2026)", "Rs crore"
        )
        pid_pct = _prov(
            ctx,
            raw,
            107,
            f"panel '{g[hi][1]}', holder rows 1-12.1, cols 2-6 (31 March 2022..2026)",
            "per cent of outstanding",
            price_basis="n/a",
        )
        for d, cell in zip(dates, total[1:], strict=True):
            out.append(
                _row(
                    series_id=f"t107.{instr}.outstanding.current",
                    table_id="HBS Table 107",
                    item_code="outstanding",
                    item_label=total[0],
                    instrument=instr,
                    counterparty="all",
                    stock_flow="stock",
                    period=d,
                    period_type="date",
                    value=parse_number(cell),
                    unit="INR_crore",
                    price_basis="current",
                    prov_id=pid_amt,
                )
            )
        for r in body[1:]:
            holder = T107_HOLDERS[r[0]]
            for d, cell in zip(dates, r[1:], strict=True):
                v = parse_number(cell)
                if v is None:
                    raise ValueError(f"T107 {instr} {holder} {d}: blank")
                out.append(
                    _row(
                        series_id=f"t107.{instr}.share.{holder}",
                        table_id="HBS Table 107",
                        item_code="holder_share",
                        item_label=r[0],
                        instrument=instr,
                        counterparty=holder,
                        stock_flow="n/a",
                        period=d,
                        period_type="date",
                        value=v,
                        unit="percent",
                        price_basis="n/a",
                        prov_id=pid_pct,
                    )
                )
    return out


# ---------------------------------------------------------------------------------------------
# T109 small savings receipts and outstandings
# ---------------------------------------------------------------------------------------------

T109_GROUPS = [
    ("Total Deposits", "deposits"),
    ("Total Certificates", "certificates"),
    ("Public Provident Fund", "ppf"),
    ("Total", "total"),
]


def _t109(ctx: BuildContext) -> list[dict[str, Any]]:
    raw = ctx.raw(C.SRC_HBS, "hbs_t109.html")
    _expect("Small Savings: Receipts and Outstanding" in _title(raw, 109), "T109 title")
    (g,) = _grids(raw)
    _expect(g[0] == ["(₹ Crore)"], "T109 unit")
    _expect(g[1] == ["Year"] + [lab for lab, _ in T109_GROUPS], f"T109 header {g[1]}")
    _expect(g[2] == ["Receipts", "Outstandings"] * 3 + ["Receipts (2+4+6)", "Outstandings (3+5+7)"], f"T109 {g[2]}")
    data = _data_rows(g, [str(i) for i in range(1, 10)])
    _expect(data[0][0] == "1986-87" and data[-1][0] == "2024-25", "T109 years")
    pid_r = _prov(ctx, raw, 109, "Receipts columns 2,4,6,8, rows 1986-87..2024-25", "Rs crore")
    pid_o = _prov(ctx, raw, 109, "Outstandings columns 3,5,7,9 (end of year), rows 1986-87..2024-25", "Rs crore")
    out = []
    for r in data:
        fy = normalize_fy(r[0])
        for k, (label, code) in enumerate(T109_GROUPS):
            for kind, cell in (("receipts", r[1 + 2 * k]), ("outstanding", r[2 + 2 * k])):
                v = parse_number(cell)
                if v is None:
                    continue  # '-' printed
                stock = kind == "outstanding"
                out.append(
                    _row(
                        series_id=f"t109.{code}.{kind}.current",
                        table_id="HBS Table 109",
                        item_code=f"{kind}.{code}",
                        item_label=f"{label} - {kind.capitalize()}",
                        instrument=f"small_savings_{code}",
                        counterparty="gg_cen",
                        stock_flow="stock" if stock else "flow",
                        period=f"{int(fy[:4]) + 1}-03-31" if stock else fy,
                        period_type="date" if stock else "fy",
                        value=v,
                        unit="INR_crore",
                        price_basis="current",
                        prov_id=pid_o if stock else pid_r,
                    )
                )
    return out


def build(ctx: BuildContext) -> list[Dataset]:
    return [
        Dataset(
            f"{C.UNIT}_hbs_saving",
            pl.DataFrame(_t11(ctx) + _t12(ctx)),
            "HBS 2025-26 T11 sector-wise gross saving (base 2011-12 and 2022-23) and T12 household financial "
            "asset/liability flows 1983-84..2023-24 (NAS 2025)",
        ),
        Dataset(
            f"{C.UNIT}_hbs_gsec_ownership",
            pl.DataFrame(_t107(ctx)),
            "HBS 2025-26 T107 ownership of Central dated securities, SGS and T-bills, end-March 2022..2026",
        ),
        Dataset(
            f"{C.UNIT}_hbs_small_savings",
            pl.DataFrame(_t109(ctx)),
            "HBS 2025-26 T109 small savings receipts and outstandings 1986-87..2024-25",
        ),
        Dataset(
            f"{C.UNIT}_hbs_scb_balance_sheet",
            pl.DataFrame(_t49(ctx)),
            "HBS 2025-26 T49 consolidated balance sheet of SCBs (excl. RRBs), end-March 2006..2025",
        ),
    ]
