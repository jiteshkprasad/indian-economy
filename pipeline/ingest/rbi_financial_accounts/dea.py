"""DEA (Ministry of Finance) public-debt reports, read from their PDF text layer.

- Quarterly Report on Public Debt Management, January-March 2023 (June 2023): Table 4.4
  ownership of GoI dated securities, end-March 2021 .. end-March 2023 (per cent, one decimal).
- Quarterly Report, January-March 2024 (file dated 27 Jun 2024): Table 4.4 dated securities and
  Table 4.5 treasury bills, end-March 2023 .. end-March 2024 (per cent).
- Status Paper on Government Debt 2023-24 (August 2025): Table 2.10 ownership of dated securities
  end-March 2020..2024; Table HB-5 quarterly ownership June 2014..March 2024 (two decimals);
  Tables HB-1A / HB-1B outstanding Central Government public debt and other (Public Account)
  liabilities, end-March 2002..2024 (Rs crore, 16 columns each).

Rows are matched by label/period and the printed column numbering is asserted. HB-5 prints
'2015 (End-March)' twice; the second one sits between 2015 (End-December) and 2016 (End-June)
and is read as end-March 2016 (checked against the strictly quarterly sequence; logged).
QR Jan-Mar 2023 T4.4 prints its 'Pension Fund' and 'Others' rows swapped; they are reassigned
(QR2023_SWAP, guarded by the printed '-' pattern and a build-time check against Status Paper T2.10).
"""

from __future__ import annotations

import re
from typing import Any

import pdfplumber
import polars as pl

from pipeline.core.unit import BuildContext, Dataset, RawFile
from pipeline.core.units import clean_label, normalize_fy, parse_number
from pipeline.ingest.rbi_financial_accounts import common as C

DOCS = {
    "dea_qr_jan_mar_2023.pdf": ("2023-06", "DEA Quarterly Report on Public Debt Management, Jan-Mar 2023 (June 2023)"),
    "dea_qr_jan_mar_2024.pdf": ("2024-06", "DEA Quarterly Report on Public Debt Management, Jan-Mar 2024 (June 2024)"),
    "dea_status_paper_2023_24.pdf": ("2025-08", "DEA Status Paper on Government Debt 2023-24 (August 2025)"),
}
HOLDERS = {
    "commercial banks": "commercial_banks",
    "co-operative banks": "cooperative_banks",
    "non-bank pds": "non_bank_pds",
    "insurance companies": "insurance",
    "mutual funds": "mutual_funds",
    "provident funds": "provident_funds",
    "pension funds": "pension_funds",
    "pension fund": "pension_funds",
    "financial institutions": "financial_institutions",
    "corporates": "corporates",
    "foreign portfolio investors": "fpi",
    "fpis": "fpi",
    "rbi": "rbi",
    "others": "others",
    "total": "total",
}
# HB-5 column order (printed numbers 2..13), established against HBS T107 end-March 2024.
HB5_COLS = (
    "commercial_banks",
    "cooperative_banks",
    "non_bank_pds",
    "insurance",
    "mutual_funds",
    "provident_funds",
    "pension_funds",
    "financial_institutions",
    "corporates",
    "fpi",
    "rbi",
    "others",
)
# Source misprint (issue rbi_financial_accounts-18): QR Jan-Mar 2023 Table 4.4 (p.18) prints the rows
# '11. Pension Fund' and '12. Others' swapped. Evidence: (1) Status Paper 2023-24 T2.10 (same publisher,
# same concept) has Pension Funds 3.5 / 4.0 and Others 4.5 / 5.6 at end-March 2022 / 2023, where QR23
# prints Pension 4.5 / 5.6 and Others 3.5 / 4.0; (2) QR Jan-Mar 2024 T4.4 Mar.23: Pension 4.0, Others 5.6;
# (3) HB-5 (two decimals) has pension funds '-' before March 2022, and QR23's '-' cells for Mar-Dec 2021
# sit on the printed 'Others' row, which is impossible for Others (always > 0). The other 10 holders
# agree with T2.10 at every common date. The rows are reassigned; values are unchanged. _qr2023 checks
# the printed '-' pattern first and build() re-checks every QR23 end-March value against T2.10.
QR2023_SWAP = {"11. Pension Fund": "others", "12. Others": "pension_funds"}
QR2023_SWAP_NOTE = (
    "Source misprint corrected (issue rbi_financial_accounts-18): the PDF prints rows '11. Pension Fund' and "
    "'12. Others' swapped. The row printed '11. Pension Fund' is ingested as Others and the row printed "
    "'12. Others' as pension funds (dim_other printed_as=<printed holder>; item_label as printed). Evidence: "
    "Status Paper 2023-24 Table 2.10 (Pension 3.5/4.0, Others 4.5/5.6 at end-March 2022/2023), QR Jan-Mar 2024 "
    "Table 4.4 Mar.23 (Pension 4.0, Others 5.6), and the '-' cells for Mar-Dec 2021 (pension funds not yet "
    "reported separately) printed on the 'Others' row. Values unchanged."
)
MONTHS = {
    "mar": "03-31",
    "jun": "06-30",
    "sep": "09-30",
    "sept": "09-30",
    "dec": "12-31",
    "march": "03-31",
    "june": "06-30",
    "september": "09-30",
    "december": "12-31",
}
HB1A_COLS = (
    ("dated_securities", "Dated Securities"),
    ("tbills_91d", "91-Day Treasury Bills"),
    ("tbills_182d", "182-Day Treasury Bills"),
    ("tbills_364d", "364-Day Treasury Bills"),
    ("market_loans", "Market Loans (2+3+4+5)"),
    ("tbills_14d", "14 Days Treasury Bills"),
    ("special_securities_tb_conversion", "Special Securities Issued in Conversion of Treasury Bills"),
    ("compensation_other_bonds", "Compensation and Other Bonds"),
    ("securities_to_ifis", "Securities Issued to International Financial Institutions"),
    ("securities_against_small_savings", "Special Securities against Small Savings"),
    ("others", "Others"),
    ("internal_debt", "Total Internal Debt [=sum(6:12)]"),
    ("external_debt_hist", "External Debt (Historical Exchange Rates)"),
    ("external_debt_curr", "External Debt (Current Exchange Rates)"),
    ("public_debt_hist", "Total Public Debt (13+14)"),
    ("public_debt_curr", "Total Public Debt (13+15)"),
)
HB1B_COLS = (
    ("nssf", "Small Savings / NSSF"),
    ("state_provident_funds", "State Provident Funds"),
    (
        "special_securities_in_lieu_of_subsidies",
        "Other Accounts: Special Securities issued to OMCs, FCI, Fertilizer Cos.",
    ),
    ("special_deposits_nongovt_pf", "Other Accounts: Special Deposits of Non-Govt. Provident Funds"),
    ("other_items", "Other Accounts: Other Items"),
    ("other_accounts", "Other Accounts: Total (4+5+6)"),
    ("reserve_funds_interest", "Reserve Funds: Bearing interest"),
    ("reserve_funds_no_interest", "Reserve Funds: Not bearing interest"),
    ("reserve_funds", "Reserve Funds: Total (8+9)"),
    ("deposits_interest", "Deposits: Bearing interest"),
    ("deposits_no_interest", "Deposits: Not bearing interest"),
    ("deposits", "Deposits: Total (11+12)"),
    ("other_liabilities", "Total Other Liabilities (2+3+7+10+13)"),
    ("public_debt_hist", "Total Public Debt (col 16 of HB-1A)"),
    ("total_liabilities_hist", "Total Liabilities (14+15)"),
    ("total_liabilities_curr", "Total Liabilities (external debt at current exchange rate)"),
)


def _lines(pdf: Any, pno: int) -> list[str]:
    return [clean_label(x) for x in (pdf.pages[pno].extract_text() or "").split("\n") if x.strip()]


def _find_page(pdf: Any, title: str) -> int:
    # a contents-page entry ends in its page number; the table itself does not
    hits = [
        i
        for i, _ in enumerate(pdf.pages)
        if any(ln.startswith(title) and not re.search(r"\s\d+$", ln) for ln in _lines(pdf, i))
    ]
    if len(hits) != 1:
        raise ValueError(f"expected one page starting a line with {title!r}, found {hits}")
    return hits[0]


def _split(line: str, n: int) -> tuple[str, list[float | None]] | None:
    """Split 'label v1 .. vn' where values are numbers or '-'; None if the line doesn't fit."""
    m = re.match(rf"^(.*?)((?:\s+(?:-?\d+(?:\.\d+)?\*?|-)){{{n}}})$", line)
    if not m:
        return None
    return clean_label(m.group(1)), [parse_number(t) for t in m.group(2).split()]


def _holder(label: str) -> str:
    key = re.sub(r"^\d+\.\s*", "", label).strip().lower()
    if key not in HOLDERS:
        raise ValueError(f"unknown holder label {label!r}")
    return HOLDERS[key]


def _row(doc: str, **kw: Any) -> dict[str, Any]:
    return {
        "source_id": C.SRC_DEA,
        "geography": "IN",
        "vintage": DOCS[doc][0],
        "estimate_stage": "Actuals" if doc.startswith("dea_status") else "Provisional",
        "status": "official",
        "dim_other": None,
    } | kw


def _prov(
    ctx: BuildContext, raw: RawFile, doc: str, table: str, locator: str, unit: str, *, notes: str | None = None
) -> str:
    return ctx.prov(
        raw=raw,
        table_id=table,
        locator=locator,
        unit_as_published=unit,
        conversion="none",
        price_basis="current" if "crore" in unit.lower() else "n/a",
        vintage=DOCS[doc][0],
        release=DOCS[doc][1],
        notes=notes,
    )


def _share_rows(
    ctx: BuildContext,
    raw: RawFile,
    doc: str,
    table: str,
    instr: str,
    lines: list[str],
    dates: list[str],
    pno: int,
    tag: str,
    notes: str | None = None,
    relabel: dict[str, str] | None = None,
    what: str = "holder rows",
) -> list[dict[str, Any]]:
    """relabel: printed label -> holder code, for rows the source prints under the wrong label
    (only QR Jan-Mar 2023 T4.4; see QR2023_SWAP). Those rows keep their printed item_label and carry
    dim_other 'printed_as=<printed holder code>'."""
    pid = _prov(
        ctx,
        raw,
        doc,
        table,
        f"page {pno + 1}: {table}, {what} x columns {dates[0]}..{dates[-1]}",
        "per cent of outstanding",
        notes=notes,
    )
    out = []
    for ln in lines:
        sp = _split(ln, len(dates))
        if sp is None:
            raise ValueError(f"{doc} {table}: cannot parse {ln!r}")
        label, vals = sp
        h = _holder(label)
        dim_other = None
        if relabel is not None:
            if label not in relabel:
                raise ValueError(f"{doc} {table}: {label!r} is not a relabelled row")
            dim_other, h = f"printed_as={h}", relabel[label]
        for d, v in zip(dates, vals, strict=True):
            if v is None:
                continue  # '-' printed (not separately reported)
            out.append(
                _row(
                    doc,
                    series_id=f"{tag}.{instr}.share.{h}",
                    table_id=table,
                    item_code="holder_share",
                    item_label=label,
                    instrument=instr,
                    counterparty=h,
                    dim_other=dim_other,
                    stock_flow="n/a",
                    period=d,
                    period_type="date",
                    value=v,
                    unit="percent",
                    price_basis="n/a",
                    prov_id=pid,
                )
            )
    return out


def _dates_from_header(tokens: str) -> list[str]:
    out = []
    for mon, yy in re.findall(r"(Mar|Jun|Sept?|Dec)\s*\.\s*(\d{2})", tokens):
        out.append(f"20{yy}-{MONTHS[mon.lower()]}")
    return out


def _block(lines: list[str], start: str, stop: str) -> list[str]:
    i = next(k for k, x in enumerate(lines) if x.startswith(start))
    j = next(k for k in range(i + 1, len(lines)) if lines[k].startswith(stop))
    return lines[i + 1 : j + 1]


def _qr2024(ctx: BuildContext) -> list[dict[str, Any]]:
    doc = "dea_qr_jan_mar_2024.pdf"
    raw = ctx.raw(C.SRC_DEA, doc)
    out = []
    with pdfplumber.open(raw.path) as pdf:
        p = _find_page(pdf, "Table 4. 4: Ownership Pattern of Government of India Dated Securities")
        lines = _lines(pdf, p) + _lines(pdf, p + 1)
        i = lines.index("Table 4. 4: Ownership Pattern of Government of India Dated Securities")
        if lines[i + 1] != "(Per cent of outstanding dated securities)":
            raise ValueError("QR 2024 T4.4 unit line")
        hdr = lines[i + 2]
        dates = _dates_from_header(hdr)
        if dates != ["2023-03-31", "2023-06-30", "2023-09-30", "2023-12-31", "2024-03-31"]:
            raise ValueError(f"QR 2024 T4.4 header {hdr!r}")
        body = [x for x in lines[i + 3 :] if re.match(r"^(\d+\.\s|Total\b)", x)]
        k = next(n for n, x in enumerate(body) if x.startswith("Total"))
        out += _share_rows(
            ctx, raw, doc, "QR Jan-Mar 2024 Table 4.4", "gsec_central", body[: k + 1], dates, p, "qr2024_t4_4"
        )
        q = lines.index("Table 4.5: Ownership Pattern of Treasury Bill")
        dates5 = _dates_from_header(lines[q + 1])
        if dates5 != dates:
            raise ValueError(f"QR 2024 T4.5 header {lines[q + 1]!r}")
        body5 = []
        for x in lines[q + 2 :]:
            if re.match(r"^(\d+\.\s|Total\b)", x):
                body5.append(x)
                if x.startswith("Total"):
                    break
        out += _share_rows(
            ctx,
            raw,
            doc,
            "QR Jan-Mar 2024 Table 4.5",
            "tbills",
            body5,
            dates,
            p + 1,
            "qr2024_t4_5",
            notes="'-' printed for RBI (no holding): no row.",
        )
    return out


def _qr2023(ctx: BuildContext) -> list[dict[str, Any]]:
    doc = "dea_qr_jan_mar_2023.pdf"
    raw = ctx.raw(C.SRC_DEA, doc)
    with pdfplumber.open(raw.path) as pdf:
        p = _find_page(pdf, "Table 4. 4: Ownership Pattern of Government of India Dated Securities")
        lines = _lines(pdf, p)
    i = lines.index("Table 4. 4: Ownership Pattern of Government of India Dated Securities")
    head = lines[i + 1 : i + 5]
    want = [
        "(Per cent of outstanding dated securities)",
        "Mar. Jun. Sep. Dec. Mar. Jun. Sept. Dec.",
        "Category Mar.23",
        "21 21 21 21 22 22 22 22",
    ]
    if head != want:
        raise ValueError(f"QR 2023 T4.4 header {head}")
    dates = [f"20{y}-{MONTHS[m]}" for y in ("21", "22") for m in ("mar", "jun", "sep", "dec")] + ["2023-03-31"]
    body = []
    for x in lines[i + 5 :]:
        body.append(x)
        if x.startswith("Total"):
            break
    # The printed rows '11. Pension Fund' and '12. Others' must still look exactly like the known misprint
    # before the swap is applied: 'Pension Fund' filled for all 9 dates, 'Others' '-' for the four 2021 dates.
    swapped = [x for x in body if _split(x, len(dates)) and _split(x, len(dates))[0] in QR2023_SWAP]
    pattern = {lab: [v is None for v in vals] for lab, vals in (_split(x, len(dates)) for x in swapped)}
    if pattern != {"11. Pension Fund": [False] * 9, "12. Others": [True] * 4 + [False] * 5}:
        raise ValueError(f"QR 2023 T4.4: the Pension Fund / Others rows no longer match the known misprint: {swapped}")
    return _share_rows(
        ctx,
        raw,
        doc,
        "QR Jan-Mar 2023 Table 4.4",
        "gsec_central",
        [x for x in body if x not in swapped],
        dates,
        p,
        "qr2023_t4_4",
        notes="Pension funds were reckoned under 'Others' until December 2021. Rows 11/12 (Pension Fund, Others) are "
        "printed swapped; they are in a separate provenance block.",
    ) + _share_rows(
        ctx,
        raw,
        doc,
        "QR Jan-Mar 2023 Table 4.4",
        "gsec_central",
        swapped,
        dates,
        p,
        "qr2023_t4_4",
        notes=QR2023_SWAP_NOTE,
        relabel=QR2023_SWAP,
        what="rows '11. Pension Fund' and '12. Others' (printed swapped; values reassigned, see notes)",
    )


def _status_paper(ctx: BuildContext) -> list[dict[str, Any]]:
    doc = "dea_status_paper_2023_24.pdf"
    raw = ctx.raw(C.SRC_DEA, doc)
    out: list[dict[str, Any]] = []
    with pdfplumber.open(raw.path) as pdf:
        # Table 2.10
        p = _find_page(pdf, "Table 2.10: Ownership Pattern of Government of India")
        lines = _lines(pdf, p)
        i = next(k for k, x in enumerate(lines) if x.startswith("Table 2.10:"))
        if lines[i + 1] != "(At end March, in per cent)" or lines[i + 2] != "Category 2020 2021 2022 2023 2024":
            raise ValueError(f"SP Table 2.10 header {lines[i + 1 : i + 3]}")
        dates = [f"{y}-03-31" for y in range(2020, 2025)]
        body = []
        for x in lines[i + 4 :]:
            body.append(x)
            if x.startswith("Total"):
                break
        out += _share_rows(
            ctx,
            raw,
            doc,
            "Status Paper Table 2.10",
            "gsec_central",
            body,
            dates,
            p,
            "sp_t2_10",
            notes="Others = State Govts, DICGC, PSUs, trusts, foreign central banks, HUF/individuals; "
            "pension funds were in 'Others' until December 2021 ('-' printed: no row).",
        )
        out += _hb5(ctx, raw, doc, pdf)
        out += _hb1(ctx, raw, doc, pdf)
    return out


def _hb5(ctx: BuildContext, raw: RawFile, doc: str, pdf: Any) -> list[dict[str, Any]]:
    p = _find_page(pdf, "Table HB-5: Ownership Pattern of Government of India Dated Securities")
    rows = []
    for pp in (p, p + 1):
        lines = _lines(pdf, pp)
        if "1 2 3 4 5 6 7 8 9 10 11 12 13" not in lines:
            raise ValueError(f"HB-5 page {pp + 1}: column numbering row missing")
        for x in lines:
            m = re.match(r"^(\d{4})\s*\(End[- ]?(March|June|September|December)\)\s+(.*)$", x)
            if m:
                rows.append((pp, int(m.group(1)), m.group(2).lower(), m.group(3)))
    # the printed periods must be strictly quarterly from June 2014 to March 2024
    seq = []
    y, q = 2014, 1  # quarter index: 0=Mar,1=Jun,2=Sep,3=Dec
    names = ["march", "june", "september", "december"]
    while (y, q) <= (2024, 0):
        seq.append((y, names[q]))
        q += 1
        if q == 4:
            y, q = y + 1, 0
    if len(rows) != len(seq):
        raise ValueError(f"HB-5: {len(rows)} rows, expected {len(seq)}")
    fixes = []
    out = []
    pids = {
        pp: _prov(
            ctx,
            raw,
            doc,
            "Status Paper Table HB-5",
            f"page {pp + 1}: Table HB-5 quarter rows, columns 2-13 "
            "(order: commercial banks, co-operative banks, non-bank PDs, insurance, MFs, PFs, pension funds, "
            "FIs, corporates, FIIs/FPIs, RBI, others)",
            "per cent of total",
            notes="The second '2015 (End-March)' row (between 2015 End-December and 2016 End-June) is read "
            "as end-March 2016. Pension funds were in 'Others' until Dec 2021 ('-': no row).",
        )
        for pp in (p, p + 1)
    }
    for (pp, yy, mon, rest), (ey, emon) in zip(rows, seq, strict=True):
        if (yy, mon) != (ey, emon):
            if (yy, mon, ey, emon) != (2015, "march", 2016, "march"):
                raise ValueError(f"HB-5: printed {yy} {mon}, expected {ey} {emon}")
            fixes.append((yy, mon, ey))
        vals = [parse_number(t) for t in rest.split()]
        if len(vals) != 12:
            raise ValueError(f"HB-5 {yy} {mon}: {len(vals)} values")
        d = f"{ey}-{MONTHS[emon]}"
        for h, v in zip(HB5_COLS, vals, strict=True):
            if v is None:
                continue
            out.append(
                _row(
                    doc,
                    series_id=f"sp_hb5.gsec_central.share.{h}",
                    table_id="Status Paper Table HB-5",
                    item_code="holder_share",
                    item_label=f"{h} ({yy} End-{mon.capitalize()})",
                    instrument="gsec_central",
                    counterparty=h,
                    stock_flow="n/a",
                    period=d,
                    period_type="date",
                    value=v,
                    unit="percent",
                    price_basis="n/a",
                    prov_id=pids[pp],
                )
            )
    if len(fixes) != 1:
        raise ValueError(f"HB-5: expected exactly one known period-label fix, got {fixes}")
    return out


def _hb1(ctx: BuildContext, raw: RawFile, doc: str, pdf: Any) -> list[dict[str, Any]]:
    out = []
    for title, cols, tag in (
        ("Table HB-1A: Outstanding Central Government Debt - Public Debt", HB1A_COLS, "hb1a"),
        ("Table HB-1B: Outstanding Central Government Debt - Other Liabilities", HB1B_COLS, "hb1b"),
    ):
        p = _find_page(pdf, title)
        lines = _lines(pdf, p)
        if "(Amount in ₹ crore)" not in lines or "1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17" not in lines:
            raise ValueError(f"{title}: unit or column-numbering line missing")
        data = [x for x in lines if re.match(r"^\d{4}-\d{2}\s", x)]
        years = [normalize_fy(x.split()[0]) for x in data]
        if years != [f"{y}-{(y + 1) % 100:02d}" for y in range(2001, 2024)]:
            raise ValueError(f"{title}: years {years[:3]}..{years[-3:]}")
        table = "Status Paper Table " + title.split(":")[0].replace("Table ", "")
        pid = _prov(
            ctx,
            raw,
            doc,
            table,
            f"page {p + 1}: {title}, rows 2001-02..2023-24 (end-March), columns 2-17",
            "Rs crore",
            notes="HB-1A 2019-20 market loans include Rs 80,000 crore of cash management bills (footnote *)."
            if tag == "hb1a"
            else None,
        )
        for x in data:
            toks = x.split()
            if len(toks) != 17:
                raise ValueError(f"{title}: {len(toks)} tokens in {x!r}")
            fy = normalize_fy(toks[0])
            for (code, label), t in zip(cols, toks[1:], strict=True):
                v = parse_number(t)
                if v is None:
                    raise ValueError(f"{title} {fy} {code}: blank")
                out.append(
                    _row(
                        doc,
                        series_id=f"sp_{tag}.{code}.current",
                        table_id=table,
                        item_code=code,
                        item_label=label,
                        institution="gg_cen",
                        side="liabilities",
                        stock_flow="stock",
                        period=f"{int(fy[:4]) + 1}-03-31",
                        period_type="date",
                        value=v,
                        unit="INR_crore",
                        price_basis="current",
                        prov_id=pid,
                    )
                )
    return out


def _check_qr2023_against_t2_10(qr23: list[dict[str, Any]], status: list[dict[str, Any]]) -> None:
    """Every QR Jan-Mar 2023 T4.4 end-March share (after the row swap) must equal Status Paper T2.10
    to one decimal. Guards the QR2023_SWAP override."""
    t210 = {(r["counterparty"], r["period"]): r["value"] for r in status if r["table_id"] == "Status Paper Table 2.10"}
    common = [(r["counterparty"], r["period"], r["value"]) for r in qr23 if (r["counterparty"], r["period"]) in t210]
    bad = [(c, p, v, t210[(c, p)]) for c, p, v in common if abs(v - t210[(c, p)]) > 0.05 + 1e-9]
    if len(common) < 30 or bad:
        raise ValueError(f"QR 2023 T4.4 vs Status Paper T2.10: {len(common)} common cells, disagreeing {bad}")


def build(ctx: BuildContext) -> list[Dataset]:
    status = _status_paper(ctx)
    qr23 = _qr2023(ctx)
    _check_qr2023_against_t2_10(qr23, status)
    own = qr23 + _qr2024(ctx) + [r for r in status if r["unit"] == "percent"]
    debt = [r for r in status if r["unit"] == "INR_crore"]
    return [
        Dataset(
            f"{C.UNIT}_dea_gsec_ownership",
            pl.DataFrame(own),
            "DEA ownership of GoI dated securities and T-bills: QR Jan-Mar 2023 T4.4, QR Jan-Mar 2024 T4.4/4.5, "
            "Status Paper 2023-24 T2.10 and HB-5 (quarterly 2014-2024). QR Jan-Mar 2023 T4.4 prints its Pension "
            "Fund and Others rows swapped; those rows are reassigned and flagged dim_other printed_as=<printed "
            "holder>. Holder 'total' = 100.",
        ),
        Dataset(
            f"{C.UNIT}_dea_central_debt",
            pl.DataFrame(debt),
            "DEA Status Paper 2023-24 HB-1A/HB-1B: outstanding Central Government public debt and Public Account "
            "liabilities by component, end-March 2002..2024",
        ),
    ]
