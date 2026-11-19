"""RBI Bulletin September 2026, Current Statistics No. 52(a) and 52(b): household financial saving.

52(a): flows of household financial assets and liabilities by instrument, quarterly and annual,
2022-23 to 2025-26 (Rs crore; per cent of GDP on the 2022-23 base). Stage per note 2: 2025-26
preliminary, 2022-23..2024-25 revised.
52(b): stocks at quarter ends, June 2022 to March 2026 (Rs crore; per cent of GDP).

The PDFs have a text layer. Every page must list exactly the item lines below, in this order;
any other line (or a missing one) is an error, so a relabelled or reordered table fails loudly.
"""

from __future__ import annotations

import re
from typing import Any

import pdfplumber
import polars as pl

from pipeline.core.unit import BuildContext, Dataset, RawFile
from pipeline.core.units import clean_label, fq, parse_number
from pipeline.ingest.rbi_financial_accounts import common as C

RELEASE = "RBI Bulletin September 2026, Current Statistics (released 25 Sep 2026)"
# (printed label, item code, is_percent). 'Per cent of GDP' codes are set from the row above.
T52A_ITEMS: tuple[tuple[str, str], ...] = (
    ("Net Financial Assets (I-II)", "nfa"),
    ("Per cent of GDP", "nfa_pct_gdp"),
    ("I. Financial Assets", "fa"),
    ("Per cent of GDP", "fa_pct_gdp"),
    ("1. Total Deposits (a+b)", "fa_deposits"),
    ("(a) Bank Deposits", "fa_deposits_bank"),
    ("i. Commercial Banks", "fa_deposits_bank_scb"),
    ("ii. Co-operative Banks", "fa_deposits_bank_coop"),
    ("(b) Non-Bank Deposits", "fa_deposits_nonbank"),
    ("Other Financial Institutions (i+ii)", "fa_deposits_nonbank_ofi"),
    ("i. Non-Banking Financial Companies", "fa_deposits_nonbank_ofi_nbfc"),
    ("ii. Housing Finance Companies", "fa_deposits_nonbank_ofi_hfc"),
    ("2. Life Insurance Funds", "fa_life_insurance"),
    ("3. Provident and Pension Funds (including PPF)", "fa_pf_pension_incl_ppf"),
    ("4. Currency", "fa_currency"),
    ("5. Investments", "fa_investments"),
    ("(a) Mutual Funds", "fa_investments_mf"),
    ("(b) Equity", "fa_investments_equity"),
    ("6. Small Savings (excluding PPF)", "fa_small_savings_excl_ppf"),
    ("II. Financial Liabilities", "fl"),
    ("Per cent of GDP", "fl_pct_gdp"),
    ("1. Financial Corporations (a+b)", "fl_fc"),
    ("(a) Banking Sector", "fl_fc_banks"),
    ("i. Commercial Banks", "fl_fc_banks_scb"),
    ("(b) Other Financial Institutions", "fl_fc_ofi"),
    ("i. Non-Banking Financial Companies", "fl_fc_ofi_nbfc"),
    ("ii. Housing Finance Companies", "fl_fc_ofi_hfc"),
    ("iii. Insurance Corporations", "fl_fc_ofi_insurance"),
    ("2. Non-Financial Corporations (Private Corporate Business)", "fl_nfc_pvt"),
    ("3. General Government", "fl_gg"),
)
T52B_ITEMS: tuple[tuple[str, str], ...] = (
    ("Financial Assets (a+b+c+d+e+f+g+h)", "fa"),
    ("Per cent of GDP", "fa_pct_gdp"),
    ("(a) Bank Deposits (i+ii)", "fa_deposits_bank"),
    ("i. Commercial Banks", "fa_deposits_bank_scb"),
    ("ii. Co-operative Banks", "fa_deposits_bank_coop"),
    ("Other Financial Institutions", "fa_deposits_nonbank_ofi"),
    ("i. Non-Banking Financial Companies", "fa_deposits_nonbank_ofi_nbfc"),
    ("ii. Housing Finance Companies", "fa_deposits_nonbank_ofi_hfc"),
    ("(c) Life Insurance Funds", "fa_life_insurance"),
    ("(d) Currency", "fa_currency"),
    ("(e) Investments", "fa_investments"),
    ("(i) Mutual funds", "fa_investments_mf"),
    ("(ii) Equity", "fa_investments_equity"),
    ("(f) Public Provident Fund (PPF)", "fa_ppf"),
    ("(g) Pension Funds", "fa_pension_funds"),
    ("(h) Small Savings (excluding PPF)", "fa_small_savings_excl_ppf"),
    ("Financial Liabilities (a+b)", "fl"),
    ("Per cent of GDP", "fl_pct_gdp"),
    ("(a) Banking Sector", "fl_banks"),
    ("i. Commercial Banks", "fl_banks_scb"),
    ("ii. Co-operative Banks", "fl_banks_coop"),
    ("(b) Other Financial Institutions", "fl_ofi"),
    ("i. Non-Banking Financial Companies", "fl_ofi_nbfc"),
    ("ii. Housing Finance Companies", "fl_ofi_hfc"),
    ("iii. Insurance Corporations", "fl_ofi_insurance"),
)
# Lines that are headings, not items (52(b) prints '(b) Non-Bank Deposits' as a heading only)
SKIP_52A = frozenset({"of which:", "Loans/Borrowings"})
SKIP_52B = SKIP_52A | {"(b) Non-Bank Deposits"}
_NUM = r"-?\d+(?:\.\d+)?"
MONTH_END = {"Jun": "06-30", "Sep": "09-30", "Dec": "12-31", "Mar": "03-31"}


def _page_lines(page: Any) -> list[str]:
    return [clean_label(x) for x in (page.extract_text() or "").split("\n") if x.strip()]


def _items(
    lines: list[str], start: int, spec: tuple[tuple[str, str], ...], ncol: int, skip: frozenset[str], where: str
) -> list[tuple[str, str, list[float]]]:
    """Match lines[start:] against spec in order; return (code, label, values) per item. Every
    line must be an expected item or a known heading; the page must end after the last item
    (apart from notes and the page footer)."""
    out = []
    i = start
    pat = re.compile(rf"^(.*?)((?:\s+{_NUM}){{{ncol}}})$")
    for label, code in spec:
        while i < len(lines) and lines[i] in skip:
            i += 1
        if i >= len(lines):
            raise ValueError(f"{where}: ran out of lines looking for {label!r}")
        m = pat.match(lines[i])
        if not m or clean_label(m.group(1)) != label:
            raise ValueError(f"{where}: expected {label!r} with {ncol} numbers, found {lines[i]!r}")
        vals = [parse_number(t) for t in m.group(2).split()]
        if any(v is None for v in vals):
            raise ValueError(f"{where}: blank in {lines[i]!r}")
        out.append((code, label, vals))  # type: ignore[arg-type]
        i += 1
    rest = [x for x in lines[i:] if not (x.startswith("RBI Bulletin") or re.match(r"^\d+ RBI Bulletin", x))]
    if rest and not rest[0].startswith("Notes"):
        raise ValueError(f"{where}: unexpected line after the last item: {rest[0]!r}")
    return out


def _base(**kw: Any) -> dict[str, Any]:
    return {
        "source_id": C.SRC_HHFS,
        "institution": "hh",
        "geography": "IN",
        "vintage": C.HHFS_VINTAGE,
        "status": "official",
    } | kw


def build(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    rows += _build_52a(ctx, ctx.raw(C.SRC_HHFS, C.HHFS_52A_NAME))
    rows += _build_52b(ctx, ctx.raw(C.SRC_HHFS, C.HHFS_52B_NAME))
    return Dataset(
        f"{C.UNIT}_hh_finsav_52ab",
        pl.DataFrame(rows),
        "RBI Bulletin Sep 2026 tables 52(a) household financial flows by instrument (quarterly+annual, 2022-23.."
        "2025-26) and 52(b) household financial stocks (quarter ends Jun 2022..Mar 2026)",
    )


def _prov(ctx: BuildContext, raw: RawFile, table: str, page: int, pct: bool, locator: str) -> str:
    return ctx.prov(
        raw=raw,
        table_id=table,
        locator=f"page {page}: {locator}",
        unit_as_published="per cent of GDP" if pct else "Rs crore",
        conversion="none",
        price_basis="current" if not pct else "n/a",
        vintage=C.HHFS_VINTAGE,
        release=RELEASE,
        base_year="2022-23" if pct else None,
        notes="Per cent of GDP is on the new base 2022-23 (table note)." if pct else None,
    )


def _build_52a(ctx: BuildContext, raw: RawFile) -> list[dict[str, Any]]:
    rows = []
    with pdfplumber.open(raw.path) as pdf:
        if len(pdf.pages) != 4:
            raise ValueError(f"52(a): expected 4 pages, found {len(pdf.pages)}")
        for pno, page in enumerate(pdf.pages, 1):
            lines = _page_lines(page)
            if not lines[1].startswith("No. 52 (a): Flow of Financial Assets and Liabilities of Households"):
                raise ValueError(f"52(a) p{pno}: title {lines[1]!r}")
            if lines[2] != "(Amount in ₹ Crore)":
                raise ValueError(f"52(a) p{pno}: unit line {lines[2]!r}")
            m = re.fullmatch(r"Item (\d{4}-\d{2})", lines[3])
            if not m or lines[4] != "Q1 Q2 Q3 Q4 Annual":
                raise ValueError(f"52(a) p{pno}: header {lines[3:5]!r}")
            fy = m.group(1)
            stage = "Preliminary" if fy == "2025-26" else "Revised"
            items = _items(lines, 6, T52A_ITEMS, 5, SKIP_52A, f"52(a) p{pno}")
            start_y = int(fy[:4])
            periods = [(fq(q, start_y), "fq") for q in range(1, 5)] + [(fy, "fy")]
            pids = {
                p: _prov(
                    ctx,
                    raw,
                    "Bulletin Table 52(a)",
                    pno,
                    p,
                    f"{fy}, cols Q1-Q4 and Annual, "
                    f"{'Per cent of GDP rows' if p else 'Rs crore item rows'}; rows matched by label",
                )
                for p in (False, True)
            }
            for code, label, vals in items:
                pct = code.endswith("_pct_gdp")
                for (period, ptype), v in zip(periods, vals, strict=True):
                    rows.append(
                        _base(
                            series_id=f"t52a.{code}.{'n_a' if pct else 'current'}.{ptype}",
                            table_id="Table 52(a)",
                            item_code=code,
                            item_label=label,
                            side="liabilities"
                            if code.startswith("fl")
                            else "assets"
                            if code.startswith("fa")
                            else "net",
                            stock_flow="n/a" if pct else "flow",
                            period=period,
                            period_type=ptype,
                            value=v,
                            unit="percent" if pct else "INR_crore",
                            price_basis="n/a" if pct else "current",
                            base_year="2022-23" if pct else None,
                            estimate_stage=stage,
                            prov_id=pids[pct],
                        )
                    )
    return rows


def _build_52b(ctx: BuildContext, raw: RawFile) -> list[dict[str, Any]]:
    rows = []
    with pdfplumber.open(raw.path) as pdf:
        if len(pdf.pages) != 4:
            raise ValueError(f"52(b): expected 4 pages, found {len(pdf.pages)}")
        for pno, page in enumerate(pdf.pages, 1):
            lines = _page_lines(page)
            if not lines[1].startswith("No. 52 (b): Stocks of Financial Assets and Liabilities of Households"):
                raise ValueError(f"52(b) p{pno}: title {lines[1]!r}")
            if lines[2] != "(Amount in ₹ Crore)":
                raise ValueError(f"52(b) p{pno}: unit line {lines[2]!r}")
            hdr = re.fullmatch(r"Item ((?:\s?(?:Jun|Sep|Dec|Mar)-\d{4}){4})", lines[3])
            if not hdr or lines[4] != "1 2 3 4":
                raise ValueError(f"52(b) p{pno}: header {lines[3:5]!r}")
            dates = []
            for tok in hdr.group(1).split():
                mon, yr = tok.split("-")
                dates.append(f"{yr}-{MONTH_END[mon]}")
            items = _items(lines, 5, T52B_ITEMS, 4, SKIP_52B, f"52(b) p{pno}")
            pids = {
                p: _prov(
                    ctx,
                    raw,
                    "Bulletin Table 52(b)",
                    pno,
                    p,
                    f"quarter ends {dates[0]}..{dates[-1]}, "
                    f"{'Per cent of GDP rows' if p else 'Rs crore item rows'}; rows matched by label",
                )
                for p in (False, True)
            }
            for code, label, vals in items:
                pct = code.endswith("_pct_gdp")
                for d, v in zip(dates, vals, strict=True):
                    rows.append(
                        _base(
                            series_id=f"t52b.{code}.{'n_a' if pct else 'current'}",
                            table_id="Table 52(b)",
                            item_code=code,
                            item_label=label,
                            side="liabilities" if code.startswith("fl") else "assets",
                            stock_flow="n/a" if pct else "stock",
                            period=d,
                            period_type="date",
                            value=v,
                            unit="percent" if pct else "INR_crore",
                            price_basis="n/a" if pct else "current",
                            base_year="2022-23" if pct else None,
                            estimate_stage="n.a.",
                            prov_id=pids[pct],
                        )
                    )
    return rows
