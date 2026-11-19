"""RBI Financial Stocks and Flow of Funds 2023-24 (workbook FSF2023-24_21012026.xlsx).

Statements read (all Rs crore, current prices; stocks at end-March, flows for the fiscal year):
- St 1 ... St 5 (32 sheets): each sector / sub-sector's financial balance sheet, liabilities and
  assets, by SNA 2008 instrument (F1..F8, plus 'Other' and 'NEC') and, for F21, F22+F29, F3, F4,
  F51, F81 and F89, by counterparty sector. Measures: outstanding (end-March 2012..2024),
  transactions (2012-13..2023-24) and valuation changes (2012-13..2023-24, only on the sheets
  that print them).
- S 6.1 ... 6.13: sector x sector from-whom-to-whom matrices (outstanding and flows).
- S 7.1 ... 7.13: instrument x sector matrices (outstanding and flows).
- S 8.1 ... 8.3: financing of private NFCs, general government and households.

Not read: 'Summary' (a re-cut of St 1-5), S 8.4-8.7 (legacy sheets labelled 'Rs Billion' with
crore-magnitude values, 2011-12..2017-18 only; registry quirk), S 9.1-9.6 (percentage
compositions derivable from S 6/S 7).

Parsing is by label: every instrument row is identified by its SNA code (or, for the four rows
without a code, by its label), every counterparty block must list the twelve counterparty labels
in the published order, and every year/measure header is asserted. A reshaped sheet fails loudly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import openpyxl
import polars as pl

from pipeline.core.unit import BuildContext, Dataset, RawFile
from pipeline.core.units import clean_label, normalize_fy, parse_number
from pipeline.ingest.rbi_financial_accounts import common as C

# Sheet -> (institution slug, keyword that the sheet title must contain)
ST_SHEETS: dict[str, tuple[str, str]] = {
    "St 1": ("fc", "Financial Corporations"),
    "St 1.1": ("fc_rbi", "Reserve Bank of India"),
    "St 1.2": ("fc_odc", "Other Depository Corporations"),
    "St 1.2.1": ("fc_odc_scb", "Scheduled Commercial Banks"),
    "St 1.2.2": ("fc_odc_coop", "Co-operative Banks"),
    "St 1.2.3": ("fc_odc_nbfc_dt", "Non-Banking Finance Companies - Deposit Taking"),
    "St 1.2.4": ("fc_odc_hfc_dt", "Housing Finance Companies - Deposit taking"),
    "St 1.3": ("fc_ofc", "Other Financial Corporations"),
    "St 1.3.1": ("fc_ofc_aifi", "All-India Financial Institutions"),
    "St 1.3.2": ("fc_ofc_sfc", "State Finance Corporations"),
    "St 1.3.3": ("fc_ofc_sidc", "State Industrial Development Corporations"),
    "St 1.3.4": ("fc_ofc_nbfc_ndt", "Non-Banking Finance Companies-Non-Deposit Taking"),
    "St 1.3.5": ("fc_ofc_hfc_ndt", "Housing Finance Companies - Non-Deposit Taking"),
    "St 1.3.6": ("fc_ofc_mf", "Mutual Funds"),
    "St 1.3.6.1": ("fc_ofc_mf_other", "Other Mutual Funds"),
    "St 1.3.6.2": ("fc_ofc_mf_mmf", "Money Market Mutual Funds"),
    "St 1.3.7": ("fc_ofc_icpf", "Insurance and Pension and Provident Funds"),
    "St 1.3.7.1": ("fc_ofc_icpf_ins", "Insurance"),
    "St 1.3.7.2": ("fc_ofc_icpf_pf", "Provident & Pension Funds (Non- Government)"),
    "St 2": ("nfc", "Non-financial Corporations"),
    "St 2.1": ("nfc_pub", "Public Non-Financial Corporations"),
    "St 2.1.1": ("nfc_pub_cpse", "Central Public Sector Enterprises"),
    "St 2.1.2": ("nfc_pub_power", "Power Companies"),
    "St 2.1.3": ("nfc_pub_ports", "Port Trusts"),
    "St 2.2": ("nfc_pvt", "Private Non-Financial Corporations"),
    "St 3": ("gg", "General Government"),
    "St 3.1": ("gg_cen", "Central Government"),
    "St 3.2": ("gg_sta", "State Governments"),
    "St 4": ("hh", "Households including Non-Profit Institutions Serving Households"),
    "St 5": ("row", "Rest of the World"),
}

# SNA instrument code as printed in column C -> (instrument slug, label keyword(s) that must match)
INSTRUMENTS: dict[str, tuple[str, tuple[str, ...]]] = {
    "F1": ("f1", ("monetary gold and sdrs",)),
    "F11": ("f11", ("monetary gold",)),
    "F12": ("f12", ("sdrs", "fca")),  # St 2.1.2 prints 'FCA' against F12 on the asset side
    "F2": ("f2", ("currency and deposits",)),
    "F21": ("f21", ("currency",)),
    "F22 & F29": ("f22_f29", ("deposits",)),
    "F3": ("f3", ("debt securities",)),
    "F4": ("f4", ("loans",)),
    "F5": ("f5", ("equity and investment fund shares",)),
    "F51": ("f51", ("equity",)),
    "F52": ("f52", ("investment fund shares",)),
    "F521": ("f521", ("money market funds",)),
    "F522": ("f522", ("other investment fund shares",)),
    "F6": ("f6", ("insurance",)),
    "F61": ("f61", ("non-life",)),
    "F62": ("f62", ("life insurance",)),
    "F63": ("f63", ("pension entitlements",)),
    "F64": ("f64", ("claims of pension funds",)),
    "F66": ("f66", ("standardised guarantees",)),
    "F8": ("f8", ("other account receivable / payable",)),
    "F81": ("f81", ("trade credit and advances",)),
    "F89": ("f89", ("except trade credit",)),
}
# Rows without an SNA code: label prefix -> instrument slug
UNCODED = (
    ("provident fund", "f6_pf"),
    ("viii. other liabilities", "other"),
    ("viii. other assets", "other"),
    ("ix. nec", "nec"),
    ("gross financial liabilities", "total"),
    ("gross financial assets", "total"),
)
# Cells the workbook leaves blank (published as missing: no row is emitted). Anything else blank
# is an error. St 1 assets, loans to 'Residents', transaction columns R:AC are empty in the file.
KNOWN_BLANKS = {("St 1", "assets", "f4", "residents", "transaction")}
WITH_COUNTERPARTY = {"f21", "f22_f29", "f3", "f4", "f51", "f81", "f89"}

# Counterparty rows, in the published order (labels normalised by _norm)
COUNTERPARTIES: tuple[tuple[str, str], ...] = (
    ("residents", "residents"),
    ("central bank", "fc_rbi"),
    ("other depository corporations", "fc_odc"),
    ("other financial corporations", "fc_ofc"),
    ("general government", "gg"),
    ("central government", "gg_cen"),
    ("state and local government", "gg_sta"),
    ("public nonfinancial corporations", "nfc_pub"),
    ("private nonfinancial corporations", "nfc_pvt"),
    ("other resident sectors", "other_resident"),
    ("households including npishs", "hh"),
    ("rest of the world", "row"),
)
# Sector headings used by S 6.x / S 7.x / S 8.x (column sectors and row counterparties)
SECTORS = {
    "central bank": "fc_rbi",
    "other depository corporations": "fc_odc",
    "other financial corporations": "fc_ofc",
    "general government": "gg",
    "public nonfinancial corporations": "nfc_pub",
    "private nonfinancial corporations": "nfc_pvt",
    "other resident sectors": "other_resident",
    "households including npishs": "hh",
    "rest of the world": "row",
    "total": "all",
}
MEASURES = {"outstanding": "outstanding", "transaction": "transaction", "valuation": "valuation"}


def _norm(text: Any) -> str:
    s = (
        clean_label(text or "")
        .lower()
        .replace("non-financial", "nonfinancial")
        .replace("non financial", "nonfinancial")
    )
    s = re.sub(r"[()]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _period(measure: str, fy: str) -> tuple[str, str, str]:
    """(period, period_type, stock_flow): stocks at end-March of the FY, flows for the FY."""
    if measure == "outstanding":
        return f"{int(fy[:4]) + 1}-03-31", "date", "stock"
    return fy, "fy", "flow"


def _row(**kw: Any) -> dict[str, Any]:
    base = {
        "source_id": C.SRC_FSF,
        "geography": "IN",
        "unit": "INR_crore",
        "price_basis": "current",
        "vintage": C.FSF_VINTAGE,
        "estimate_stage": "n.a.",
        "status": "official",
    }
    return base | kw


def _prov(ctx: BuildContext, raw: RawFile, table_id: str, locator: str) -> str:
    return ctx.prov(
        raw=raw,
        table_id=table_id,
        locator=locator,
        unit_as_published="Rs crore",
        conversion="none",
        price_basis="current",
        vintage=C.FSF_VINTAGE,
        release=C.FSF_RELEASE,
        notes="FSF 2023-24 was compiled before the NAS 2022-23 base revision (27 Feb 2026); its sector "
        "boundaries and GDP ratios follow the 2011-12 series.",
    )


def load(ctx: BuildContext) -> tuple[RawFile, Any]:
    raw = ctx.raw(C.SRC_FSF, C.FSF_XLSX_NAME)
    return raw, openpyxl.load_workbook(raw.path, data_only=True)


# ---------------------------------------------------------------------------------------------
# St 1 ... St 5: sector balance sheets by instrument x counterparty
# ---------------------------------------------------------------------------------------------


@dataclass
class _Block:
    side: str  # liabilities | assets
    header_row: int  # the row with 'Outstanding' / 'Transaction' / 'Valuation'
    year_row: int
    first: int
    last: int  # the 'Gross Financial ...' row


def _measure_cols(ws: Any, header_row: int, year_row: int) -> dict[int, tuple[str, str]]:
    """{column index: (measure, fiscal year)} from the measure and year header rows."""
    starts = []
    for c in range(1, ws.max_column + 1):
        v = ws.cell(header_row, c).value
        if isinstance(v, str) and _norm(v) in MEASURES:
            starts.append((c, MEASURES[_norm(v)]))
            unit = clean_label(ws.cell(header_row + 1, c).value or "")
            if "crore" not in unit.lower():
                raise ValueError(f"{ws.title} r{header_row + 1}c{c}: expected '(Rs crore)', found {unit!r}")
    if [m for _, m in starts][:2] != ["outstanding", "transaction"] or len(starts) not in (2, 3):
        raise ValueError(f"{ws.title} r{header_row}: unexpected measure header {starts}")
    out: dict[int, tuple[str, str]] = {}
    for i, (c0, m) in enumerate(starts):
        c1 = starts[i + 1][0] if i + 1 < len(starts) else ws.max_column + 1
        for c in range(c0, c1):
            v = ws.cell(year_row, c).value
            if v is None:
                continue
            out[c] = (m, normalize_fy(str(v)))
    years = {m: [fy for (mm, fy) in out.values() if mm == m] for _, m in starts}
    if years["outstanding"] != [normalize_fy(f"{y}-{(y + 1) % 100:02d}") for y in range(2011, 2024)]:
        raise ValueError(f"{ws.title}: outstanding years {years['outstanding']}")
    for m in ("transaction", "valuation"):
        if m in years and years[m] != years["outstanding"][1:]:
            raise ValueError(f"{ws.title}: {m} years {years[m]}")
    return out


def _blocks(ws: Any) -> list[_Block]:
    blocks = []
    for side, head, total in (
        ("liabilities", "financial liabilities/sources", "gross financial liabilities"),
        ("assets", "financial assets/uses", "gross financial assets"),
    ):
        yr = next(r for r in range(1, ws.max_row + 1) if _norm(ws.cell(r, 2).value) == head)
        last = next(r for r in range(yr, ws.max_row + 1) if _norm(ws.cell(r, 2).value) == total)
        hdr = next(r for r in range(yr - 1, 0, -1) if _norm(ws.cell(r, 4).value) == "outstanding")
        blocks.append(_Block(side, hdr, yr, yr + 1, last))
    return blocks


def _classify(ws: Any, r: int) -> tuple[str, str]:
    """(kind, slug) for row r: ('instrument', f4) or ('counterparty', hh)."""
    label, code = _norm(ws.cell(r, 2).value), clean_label(ws.cell(r, 3).value or "")
    if code:
        if code not in INSTRUMENTS:
            raise ValueError(f"{ws.title} r{r}: unknown SNA code {code!r} ({label!r})")
        slug, keys = INSTRUMENTS[code]
        if not any(k in label for k in keys):
            raise ValueError(f"{ws.title} r{r}: label {label!r} does not match code {code}")
        return "instrument", slug
    for prefix, slug in UNCODED:
        if label.startswith(prefix):
            return "instrument", slug
    for lab, slug in COUNTERPARTIES:
        if label == lab:
            return "counterparty", slug
    raise ValueError(f"{ws.title} r{r}: unmapped row label {label!r}")


def build_balance_sheets(ctx: BuildContext, raw: RawFile, wb: Any) -> Dataset:
    have = [s for s in wb.sheetnames if s.startswith("St ")]
    if sorted(have) != sorted(ST_SHEETS):
        raise ValueError(f"FSF St sheets changed: {sorted(set(have) ^ set(ST_SHEETS))}")
    rows: list[dict[str, Any]] = []
    for sheet, (inst, keyword) in ST_SHEETS.items():
        ws = wb[sheet]
        title = clean_label(ws["B2"].value)
        if _norm(keyword) not in _norm(title):
            raise ValueError(f"{sheet}: title {title!r} does not name {keyword!r}")
        table_id = "Statement " + sheet.split(" ", 1)[1]
        for b in _blocks(ws):
            cols = _measure_cols(ws, b.header_row, b.year_row)
            pids = {}
            for m in sorted({m for m, _ in cols.values()}):
                mc = [c for c, (mm, _) in cols.items() if mm == m]
                pids[m] = _prov(
                    ctx,
                    raw,
                    table_id,
                    f"sheet '{sheet}', {b.side} block rows {b.first}-{b.last}, cols "
                    f"{openpyxl.utils.get_column_letter(min(mc))}:{openpyxl.utils.get_column_letter(max(mc))} "
                    f"({m}); instrument rows by SNA code, counterparty rows by label",
                )
            instrument, instr_label, expect_cp = "", "", 0
            for r in range(b.first, b.last + 1):
                if ws.cell(r, 2).value is None:
                    continue
                kind, slug = _classify(ws, r)
                if kind == "instrument":
                    if expect_cp:
                        raise ValueError(f"{sheet} r{r}: counterparty block of {instrument} is incomplete")
                    instrument, instr_label = slug, clean_label(ws.cell(r, 2).value)
                    cp, cp_label = "all", ""
                    expect_cp = len(COUNTERPARTIES) if slug in WITH_COUNTERPARTY else 0
                    cp_index = 0
                else:
                    if not expect_cp or COUNTERPARTIES[cp_index][1] != slug:
                        raise ValueError(f"{sheet} r{r}: counterparty {slug!r} out of place under {instrument}")
                    cp, cp_label = slug, clean_label(ws.cell(r, 2).value)
                    cp_index += 1
                    expect_cp -= 1
                label = instr_label + (f" | {cp_label}" if cp_label else "")
                for c, (m, fy) in cols.items():
                    v = parse_number(ws.cell(r, c).value)
                    if v is None:
                        if (sheet, b.side, instrument, cp, m) in KNOWN_BLANKS:
                            continue
                        raise ValueError(f"{sheet} r{r}c{c}: blank cell for {instrument}/{cp} {m} {fy}")
                    period, ptype, sf = _period(m, fy)
                    rows.append(
                        _row(
                            series_id=f"fsf.{inst}.{b.side}.{m}.{instrument}.{cp}.current",
                            table_id=table_id,
                            item_code=f"{m}.{instrument}",
                            item_label=label,
                            institution=inst,
                            instrument=instrument,
                            counterparty=cp,
                            side=b.side,
                            dim_other=f"measure={m}",
                            stock_flow=sf,
                            period=period,
                            period_type=ptype,
                            value=v,
                            prov_id=pids[m],
                        )
                    )
            if expect_cp:
                raise ValueError(f"{sheet}: counterparty block of {instrument} is incomplete at the end")
    return Dataset(
        f"{C.UNIT}_fsf_balance_sheets",
        pl.DataFrame(rows),
        "FSF 2023-24 St 1-5: 30 sector/sub-sector balance sheets by instrument x counterparty; stocks 2012-2024, "
        "transactions and valuation 2012-13..2023-24. Not additive across rows: institutions nest (fc > fc_odc > "
        "fc_odc_scb ..., gg > gg_cen/gg_sta, nfc > nfc_pub > nfc_pub_cpse ...), counterparty 'all' = 'residents' + "
        "'row' and 'residents'/'gg' are subtotals of their parts, and instruments nest (total > f1..f8 > f11, f51, "
        "...). Sum only leaf codes, or use the printed totals.",
    )


# ---------------------------------------------------------------------------------------------
# S 6.x (sector x sector) and S 7.x (instrument x sector)
# ---------------------------------------------------------------------------------------------

S7_INSTRUMENTS = {
    "i. monetary gold and sdrs": "f1",
    "monetary gold and sdrs": "f1",
    "monetary gold": "f11",
    "sdrs": "f12",
    "currency and deposits": "f2",
    "currency": "f21",
    "deposits": "f22_f29",
    "debt securities": "f3",
    "loans": "f4",
    "equity and investment fund shares": "f5",
    "equity": "f51",
    "investment fund shares/ units": "f52",
    "insurance, pension, provident and standardised guarantee schemes": "f6",
    "non-life insurance technical reserves": "f61",
    "life insurance and annuity entitlements": "f62",
    "pension entitlements": "f63",
    "provident funds": "f6_pf",
    "claims of pension funds on pension managers": "f64",
    "provisions for calls under standardised guarantees": "f66",
    "other account receivable / payable": "f8",
    "trade credit and advances": "f81",
    "other account receivable / payable, except trade credit and advances": "f89",
    "foreign claims not elsewhere classified": "foreign_nec",
    "other items not elsewhere classified": "other_nec",
    "total": "total",
}


def _matrix_titles(ws: Any, pattern: str) -> list[tuple[int, str, str, str]]:
    """[(title row, table id, measure, fiscal year)] for the matrix blocks on a S 6/S 7 sheet."""
    out = []
    for r in range(1, ws.max_row + 1):
        v = ws.cell(r, 2).value
        if not isinstance(v, str):
            continue
        t = clean_label(v)
        m = re.match(pattern, t, re.IGNORECASE)
        if not m:
            continue
        tid = f"Statement {m.group(1)}"
        kind = m.group(2).lower()
        measure = "outstanding" if "outstanding" in kind else "transaction" if "flow" in kind else None
        if measure is None:
            raise ValueError(f"{ws.title} r{r}: unknown matrix kind in {t!r}")
        fy = normalize_fy(re.search(r"(\d{4}-\d{2})", t).group(1))
        out.append((r, tid, measure, fy))
    return out


def _matrix_columns(ws: Any, head_row: int) -> dict[int, tuple[str, str]]:
    """{col: (institution slug, side)} from a 'sector' header row and the Sources/Uses row below."""
    out: dict[int, tuple[str, str]] = {}
    sector = None
    for c in range(4, ws.max_column + 1):
        v = ws.cell(head_row, c).value
        if v is not None:
            key = _norm(v)
            if key not in SECTORS:
                raise ValueError(f"{ws.title} r{head_row}c{c}: unknown sector heading {v!r}")
            sector = SECTORS[key]
        su = _norm(ws.cell(head_row + 1, c).value)
        if su in ("sources", "uses"):
            if sector is None:
                raise ValueError(f"{ws.title} r{head_row + 1}c{c}: Sources/Uses without a sector")
            out[c] = (sector, "liabilities" if su == "sources" else "assets")
    if len(out) != 18:
        raise ValueError(f"{ws.title} r{head_row}: expected 9 sectors x Sources/Uses, got {len(out)} columns")
    return out


def build_fwtw(ctx: BuildContext, raw: RawFile, wb: Any) -> Dataset:
    sheets = [f"S 6.{i}" for i in range(1, 14)]
    rows: list[dict[str, Any]] = []
    for sheet in sheets:
        ws = wb[sheet]
        titles = _matrix_titles(ws, r"Statement\s*(6\.\d+(?:\.[ab])?)\s*:\s*Financial (Outstanding|Flows)")
        want = 1 if sheet == "S 6.1" else 2
        if len(titles) != want:
            raise ValueError(f"{sheet}: expected {want} matrices, found {titles}")
        for tr, tid, measure, fy in titles:
            if clean_label(ws.cell(tr + 1, 21).value or "").lower() != "(₹ crore)":
                raise ValueError(f"{sheet} r{tr + 1}: expected (Rs crore)")
            head = tr + 2
            if _norm(ws.cell(head, 3).value) != "sector/financial transactions with other sectors":
                raise ValueError(f"{sheet} r{head}: unexpected matrix header")
            cols = _matrix_columns(ws, head)
            period, ptype, sf = _period(measure, fy)
            first, last = head + 2, head + 11
            pid = _prov(
                ctx,
                raw,
                tid,
                f"sheet '{sheet}', rows {first}-{last} (holder/issuer sector rows I-X), cols D:U "
                f"(column sector x Sources=liabilities / Uses=assets), {measure} {fy}",
            )
            seen = []
            for r in range(first, last + 1):
                key = _norm(ws.cell(r, 3).value)
                if key not in SECTORS:
                    raise ValueError(f"{sheet} r{r}: unknown row sector {ws.cell(r, 3).value!r}")
                cp = SECTORS[key]
                seen.append(cp)
                for c, (inst, side) in cols.items():
                    v = parse_number(ws.cell(r, c).value)
                    if v is None:
                        raise ValueError(f"{sheet} r{r}c{c}: blank")
                    rows.append(
                        _row(
                            series_id=f"fsf6.{inst}.{side}.{measure}.{cp}.current",
                            table_id=tid,
                            item_code=f"{measure}.fwtw",
                            item_label=f"{clean_label(ws.cell(head, c if ws.cell(head, c).value else c - 1).value)}"
                            f" {'Sources' if side == 'liabilities' else 'Uses'} | {clean_label(ws.cell(r, 3).value)}",
                            institution=inst,
                            counterparty=cp,
                            side=side,
                            dim_other=f"measure={measure}",
                            stock_flow=sf,
                            period=period,
                            period_type=ptype,
                            value=v,
                            prov_id=pid,
                        )
                    )
            if seen != list(SECTORS.values()):
                raise ValueError(f"{sheet}: row sectors {seen}")
    return Dataset(
        f"{C.UNIT}_fsf_fwtw",
        pl.DataFrame(rows),
        "FSF 2023-24 S 6.1-6.13: from-whom-to-whom sector x sector matrices, stocks end-March 2012-2024 and "
        "flows 2012-13..2023-24. Institution 'all' (column totals) and counterparty 'all' (row totals) are "
        "subtotals: do not add them to the sector cells.",
    )


def build_instrument_sector(ctx: BuildContext, raw: RawFile, wb: Any) -> Dataset:
    rows: list[dict[str, Any]] = []
    for i in range(1, 14):
        sheet = f"S 7.{i}"
        ws = wb[sheet]
        titles = _matrix_titles(ws, r"STATEMENT\s*(7\.\d+(?:\.[ab])?)\s*:\s*FINANCIAL (OUTSTANDING|FLOWS)")
        want = 1 if i == 1 else 2
        if len(titles) != want:
            raise ValueError(f"{sheet}: expected {want} matrices, found {titles}")
        for tr, tid, measure, fy in titles:
            head = next(r for r in range(tr + 1, tr + 4) if _norm(ws.cell(r, 4).value) == "central bank")
            if _norm(ws.cell(head + 1, 3).value) != "instrument/sector":
                raise ValueError(f"{sheet} r{head + 1}: expected 'Instrument/Sector'")
            cols = _matrix_columns(ws, head)
            period, ptype, sf = _period(measure, fy)
            first = head + 2
            last = next(r for r in range(first, ws.max_row + 1) if _norm(ws.cell(r, 3).value) == "total")
            pid = _prov(
                ctx,
                raw,
                tid,
                f"sheet '{sheet}', rows {first}-{last} (instruments), cols D:U (sector x Sources=liabilities / "
                f"Uses=assets), {measure} {fy}",
            )
            for r in range(first, last + 1):
                lab = ws.cell(r, 3).value
                if lab is None:
                    continue
                key = _norm(lab)
                if key not in S7_INSTRUMENTS:
                    raise ValueError(f"{sheet} r{r}: unknown instrument label {lab!r}")
                instrument = S7_INSTRUMENTS[key]
                for c, (inst, side) in cols.items():
                    v = parse_number(ws.cell(r, c).value)
                    if v is None:
                        raise ValueError(f"{sheet} r{r}c{c}: blank")
                    rows.append(
                        _row(
                            series_id=f"fsf7.{inst}.{side}.{measure}.{instrument}.current",
                            table_id=tid,
                            item_code=f"{measure}.{instrument}",
                            item_label=clean_label(lab),
                            institution=inst,
                            instrument=instrument,
                            side=side,
                            dim_other=f"measure={measure}",
                            stock_flow=sf,
                            period=period,
                            period_type=ptype,
                            value=v,
                            prov_id=pid,
                        )
                    )
    df = pl.DataFrame(rows)
    dup = df.group_by("series_id", "period", maintain_order=True).len().filter(pl.col("len") > 1)
    if dup.height:
        raise ValueError(f"S 7.x: an instrument label maps twice within a matrix: {dup.head(5)}")
    return Dataset(
        f"{C.UNIT}_fsf_instrument_sector",
        df,
        "FSF 2023-24 S 7.1-7.13: instrument x sector matrices, stocks end-March 2012-2024 and flows 2012-13..2023-24. "
        "Not additive across rows: institution 'all' is the sector total, and instruments nest (total > f1..f8 > "
        "f11, f51, ...; f6_pf etc. are components).",
    )


# ---------------------------------------------------------------------------------------------
# S 8.1-8.3: financing of private NFCs, general government, households
# ---------------------------------------------------------------------------------------------

S8_SHEETS = {
    "S 8.1": ("nfc_pvt", "Private Non-financial Corporations"),
    "S 8.2": ("gg", "General Government"),
    "S 8.3": ("hh", "Households"),
}
S8_ITEMS = {
    "financial resources": "financial_resources",
    "financial uses": "financial_uses",
    "financial deficit": "financial_deficit",
}


def build_financing(ctx: BuildContext, raw: RawFile, wb: Any) -> Dataset:
    rows: list[dict[str, Any]] = []
    for sheet, (inst, keyword) in S8_SHEETS.items():
        ws = wb[sheet]
        titles = []
        for r in range(1, ws.max_row + 1):
            t = clean_label(ws.cell(r, 2).value or "")
            m = re.match(r"Statement\s*(8\.\d\.[ab])\s*:\s*Financing of the (.+?)\s*[\[(](Outstanding|Flow)[\])]", t)
            if m:
                if _norm(keyword) not in _norm(m.group(2)):
                    raise ValueError(f"{sheet} r{r}: title {t!r}")
                titles.append(
                    (r, f"Statement {m.group(1)}", "outstanding" if m.group(3) == "Outstanding" else "transaction")
                )
        if len(titles) != 2:
            raise ValueError(f"{sheet}: expected 2 blocks, found {titles}")
        for tr, tid, measure in titles:
            head = next(r for r in range(tr + 1, tr + 4) if _norm(ws.cell(r, 3).value) == "item")
            years = {
                c: normalize_fy(str(ws.cell(head, c).value))
                for c in range(4, ws.max_column + 1)
                if ws.cell(head, c).value is not None
            }
            want = [f"{y}-{(y + 1) % 100:02d}" for y in range(2011 if measure == "outstanding" else 2012, 2024)]
            if list(years.values()) != want:
                raise ValueError(f"{sheet} r{head}: years {list(years.values())}")
            first, last = head + 1, head + 13
            last_col = openpyxl.utils.get_column_letter(max(years))
            pid = _prov(ctx, raw, tid, f"sheet '{sheet}', rows {first}-{last}, cols D:{last_col} ({measure})")
            in_financed = False
            for r in range(first, last + 1):
                lab = _norm(ws.cell(r, 3).value)
                if lab.startswith("deficit financed by"):
                    in_financed = True
                    continue
                if in_financed:
                    if lab not in SECTORS:
                        raise ValueError(f"{sheet} r{r}: unknown sector {lab!r}")
                    item, cp = "financed_by", SECTORS[lab]
                else:
                    if lab not in S8_ITEMS:
                        raise ValueError(f"{sheet} r{r}: unknown item {lab!r}")
                    item, cp = S8_ITEMS[lab], None
                for c, fy in years.items():
                    v = parse_number(ws.cell(r, c).value)
                    if v is None:
                        raise ValueError(f"{sheet} r{r}c{c}: blank")
                    period, ptype, sf = _period(measure, fy)
                    rows.append(
                        _row(
                            series_id=f"fsf8.{inst}.{measure}.{item}" + (f".{cp}" if cp else "") + ".current",
                            table_id=tid,
                            item_code=f"{measure}.{item}",
                            item_label=clean_label(ws.cell(r, 3).value),
                            institution=inst,
                            counterparty=cp,
                            dim_other=f"measure={measure}",
                            stock_flow=sf,
                            period=period,
                            period_type=ptype,
                            value=v,
                            prov_id=pid,
                        )
                    )
    return Dataset(
        f"{C.UNIT}_fsf_financing",
        pl.DataFrame(rows),
        "FSF 2023-24 S 8.1-8.3: financing of private NFCs, general government and households by lending sector",
    )
