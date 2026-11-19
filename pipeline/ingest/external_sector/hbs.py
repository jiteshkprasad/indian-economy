"""RBI Handbook of Statistics on the Indian Economy (HBS): external-sector tables, read from the
HTML version of each table on www.rbi.org.in (PublicationsView.aspx?id=...).

Editions used
- HBS 2025-26 (28th edition, released 31 Jul 2026): annual BoP (T124-T127), invisibles (T130/T131),
  exchange rates (T133 annual, T205 monthly), NRI deposits (T139-T142), foreign investment (T143),
  reserves (T144), external debt (T145/T146), quarterly BoP (T197/T198) and quarterly IIP
  (T199/T200).
- HBS 2024-25 (released 29 Aug 2025), only for the quarters of 2023-24, which the 2025-26 edition
  no longer prints: quarterly BoP (T196/T197) and quarterly IIP (T198/T199). The two editions
  overlap on 2024-25; both vintages are kept (series ids are edition-independent).

Parsing: a long table is printed in several parts (one HTML <table> each) that repeat the header
block. Every part is read; rows are matched by the printed item number (BPM6 tables) or by the
full ordered label sequence (all other tables), so a reshaped table fails loudly.
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import polars as pl

from pipeline.core.unit import BuildContext, Dataset, RawFile
from pipeline.core.units import clean_label, fq, fy, normalize_fy, parse_number, slug

from ._html import Grid, is_colnum_row, leaf_tables, page_date

UNIT = "external_sector"
PV = "https://www.rbi.org.in/scripts/PublicationsView.aspx?id={}"
HBS_LANDING = "https://www.rbi.org.in/scripts/AnnualPublications.aspx?head=Handbook%20of%20Statistics%20on%20Indian%20Economy"
ED26, ED25 = "2026-07-31", "2025-08-29"  # release dates of the HBS 2025-26 and 2024-25 editions
REL = {
    ED26: "Handbook of Statistics on the Indian Economy 2025-26 (RBI, 31 Jul 2026)",
    ED25: "Handbook of Statistics on the Indian Economy 2024-25 (RBI, 29 Aug 2025)",
}

SRC_HBS = "rbi_hbs_external"
SRC_BOPQ = "rbi_bop_quarterly"
SRC_NRI = "rbi_nri_deposits"
SRC_DEBT = "rbi_external_debt"
SRC_IIP = "rbi_intl_investment_position"


@dataclass(frozen=True)
class Page:
    source: str
    name: str  # raw file name (pin key)
    pv_id: int
    table: str  # table id as printed in that edition
    edition: str  # ED26 / ED25


PAGES: tuple[Page, ...] = (
    Page(SRC_HBS, "hbs2026_t124.html", 23949, "Table 124", ED26),
    Page(SRC_HBS, "hbs2026_t125.html", 23950, "Table 125", ED26),
    Page(SRC_HBS, "hbs2026_t126.html", 23951, "Table 126", ED26),
    Page(SRC_HBS, "hbs2026_t127.html", 23952, "Table 127", ED26),
    Page(SRC_HBS, "hbs2026_t130.html", 23955, "Table 130", ED26),
    Page(SRC_HBS, "hbs2026_t131.html", 23956, "Table 131", ED26),
    Page(SRC_HBS, "hbs2026_t133.html", 23958, "Table 133", ED26),
    Page(SRC_HBS, "hbs2026_t143.html", 23968, "Table 143", ED26),
    Page(SRC_HBS, "hbs2026_t144.html", 23969, "Table 144", ED26),
    Page(SRC_HBS, "hbs2026_t205.html", 24030, "Table 205", ED26),
    Page(SRC_BOPQ, "hbs2026_t197.html", 24022, "Table 197", ED26),
    Page(SRC_BOPQ, "hbs2026_t198.html", 24023, "Table 198", ED26),
    Page(SRC_BOPQ, "hbs2025_t196.html", 23370, "Table 196", ED25),
    Page(SRC_BOPQ, "hbs2025_t197.html", 23371, "Table 197", ED25),
    Page(SRC_NRI, "hbs2026_t139.html", 23964, "Table 139", ED26),
    Page(SRC_NRI, "hbs2026_t140.html", 23965, "Table 140", ED26),
    Page(SRC_NRI, "hbs2026_t141.html", 23966, "Table 141", ED26),
    Page(SRC_NRI, "hbs2026_t142.html", 23967, "Table 142", ED26),
    Page(SRC_DEBT, "hbs2026_t145.html", 23970, "Table 145", ED26),
    Page(SRC_DEBT, "hbs2026_t146.html", 23971, "Table 146", ED26),
    Page(SRC_IIP, "hbs2026_t199.html", 24024, "Table 199", ED26),
    Page(SRC_IIP, "hbs2026_t200.html", 24025, "Table 200", ED26),
    Page(SRC_IIP, "hbs2025_t198.html", 23372, "Table 198", ED25),
    Page(SRC_IIP, "hbs2025_t199.html", 23373, "Table 199", ED25),
)
PAGE = {p.name: p for p in PAGES}

INR, USD = "INR_crore", "USD_million"
CAPTION = {INR: "Rs crore", USD: "US$ million"}


def fetch_all(ctx) -> None:
    for p in PAGES:
        ctx.fetch(p.source, PV.format(p.pv_id), name=p.name, referer=HBS_LANDING, expect="html")


# ---------------------------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------------------------


@dataclass
class Part:
    n: int  # 1-based part number within the page
    grid: Grid
    head: list[list[str]]  # rows above the column-number row
    body: list[list[str]]  # data rows (up to '(Continued)' / 'Notes')


_STOP = ("(continued)", "notes", "note", "source")


def parts(path: Path) -> list[Part]:
    out = []
    for g in leaf_tables(path):
        k = next((i for i, r in enumerate(g.rows) if is_colnum_row(r)), None)
        if k is None:
            continue
        body = []
        for r in g.rows[k + 1 :]:
            if r and r[0].lower().startswith(_STOP):
                break
            body.append(r)
        out.append(Part(len(out) + 1, g, g.rows[:k], body))
    if not out:
        raise ValueError(f"{path.name}: no data table found")
    return out


def expect_text(part: Part, *needles: str) -> None:
    text = " ".join(" ".join(r) for r in part.head).lower()
    for n in needles:
        if n.lower() not in text:
            raise ValueError(f"part {part.n}: expected {n!r} in the header block, got {text[:300]!r}")


def page_meta(ctx: BuildContext, name: str) -> tuple[Page, RawFile, str]:
    p = PAGE[name]
    raw = ctx.raw(p.source, name)
    d = page_date(raw.path)
    if d != p.edition:
        raise ValueError(f"{name}: page dated {d}, expected the {p.edition} edition (a new edition? update PAGES)")
    return p, raw, d


def num(cell: str) -> float | None:
    return parse_number(cell)


_MARKER = re.compile(r"^(\(?[ivxlcdm]+[.)]|\(?[a-z][.)]|[A-Z][.)]|\d+[.)]|[IVX]+\.)\s*")


def norm(label: str) -> str:
    """Label key that ignores list markers, case, spacing and punctuation ('ii) By India' ~ 'i) By India')."""
    return re.sub(r"[^a-z0-9]+", "", _MARKER.sub("", label.strip()).lower())


def match_sequence(labels: list[str], expected: list[tuple[str | None, str]], where: str) -> list[str | None]:
    """Map the table's ordered labels to codes. `expected` is [(code or None for a heading, label)].
    The whole sequence must match (by norm()); anything else raises."""
    if len(labels) != len(expected):
        raise ValueError(f"{where}: {len(labels)} rows, expected {len(expected)}: {labels}")
    codes = []
    for got, (code, want) in zip(labels, expected, strict=True):
        if norm(got) != norm(want):
            raise ValueError(f"{where}: row {got!r} where {want!r} was expected (table changed?)")
        codes.append(code)
    return codes


def base_row(p: Page, **kw: Any) -> dict[str, Any]:
    r = {
        "source_id": p.source,
        "table_id": p.table,
        "geography": "IN",
        "price_basis": "current",
        "vintage": p.edition,
        "status": "official",
    }
    r.update(kw)
    return r


def month_end(y: int, m: int) -> str:
    return f"{y}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"


def stage_from_note(period: str, prelim_fy: str | None) -> str:
    """HBS tables flag only the latest year ('Data for 2025-26 are preliminary estimates')."""
    if prelim_fy and (period == prelim_fy or period.endswith(prelim_fy)):
        return "Preliminary"
    return "n.a."


def prelim_year(path: Path) -> str | None:
    from ._html import page_text

    m = re.search(r"Data for (\d{4}-\d{2}) are (preliminary|provisional)", page_text(path))
    return m.group(1) if m else None


# ---------------------------------------------------------------------------------------------
# BPM6 standard presentation: annual (T126/T127) and quarterly (T197/T198; 2024-25 ed. T196/T197)
# ---------------------------------------------------------------------------------------------

BPM6_ITEMS = (
    "1 1.A 1.A.a 1.A.a.1 1.A.a.2 1.A.a.3 1.A.b 1.A.b.1 1.A.b.2 1.A.b.3 1.A.b.4 1.A.b.5 1.A.b.6 1.A.b.7 1.A.b.8 "
    "1.A.b.9 1.A.b.10 1.A.b.11 1.A.b.12 1.A.b.13 1.B 1.B.1 1.B.2 1.B.2.1 1.B.2.2 1.B.2.3 1.B.2.4 1.B.3 1.C 1.C.1 "
    "1.C.1.1 1.C.1.2 1.C.2 2 2.1 2.2 3 3.1 3.1.A 3.1.A.1 3.1.A.1.1 3.1.A.1.2 3.1.A.2 3.1.A.2.1 3.1.B 3.1.B.1 "
    "3.1.B.1.1 3.1.B.1.2 3.1.B.2 3.1.B.2.1 3.2 3.2.A 3.2.1 3.2.2 3.2.B 3.3 3.4 3.4.1 3.4.2 3.4.2.1 3.4.2.2 "
    "3.4.2.3 3.4.2.4 3.4.3 3.4.3.A 3.4.3.B 3.4.4 3.4.5 3.4.6 3.4.7 3.5 3.5.1 3.5.2 3.5.3 3.5.4 4 4.1 4.2 4.3 5"
).split()
_BPM6_NUM = re.compile(r"^(\d+(?:\.[0-9A-Za-z]+)*)\s+(.+)$")
_QTR = {"april-june": (1, 0), "july-september": (2, 0), "october-december": (3, 0), "january-march": (4, -1)}


def bpm6_code(number: str) -> str:
    return "bpm6_" + number.lower().replace(".", "_")


def _period_cdn(text: str, quarterly: bool) -> tuple[str, str]:
    if not quarterly:
        return normalize_fy(text), "fy"
    m = re.fullmatch(r"([A-Za-z]+-[A-Za-z]+) (\d{4})", text)
    if not m or m.group(1).lower() not in _QTR:
        raise ValueError(f"unexpected quarter header {text!r}")
    q, dy = _QTR[m.group(1).lower()]
    return fq(q, int(m.group(2)) + dy), "fq"


def _cdn_columns(part: Part, quarterly: bool) -> dict[int, tuple[str, str, str]]:
    """{column: (period, period_type, side)} from the period row and the Credit/Debit/Net row."""
    per = next(r for r in part.head if r and r[0].lower().startswith("item"))
    side = next(r for r in part.head if "Credit" in r)
    cols = {}
    for c in range(1, len(per)):
        s = side[c].lower()
        if s not in ("credit", "debit", "net"):
            raise ValueError(f"part {part.n}: column {c} side {side[c]!r}")
        period, pt = _period_cdn(per[c], quarterly)
        cols[c] = (period, pt, s)
    return cols


def build_bpm6(ctx: BuildContext, names: list[tuple[str, str]], quarterly: bool) -> list[dict[str, Any]]:
    """names: [(raw name, unit)]; returns clean rows for all pages."""
    rows: list[dict[str, Any]] = []
    for name, unit in names:
        p, raw, vintage = page_meta(ctx, name)
        prelim = prelim_year(raw.path)
        ps = parts(raw.path)
        seen: dict[str, str] = {}
        for part in ps:
            expect_text(part, "crore" if unit == INR else "million")
            cols = _cdn_columns(part, quarterly)
            got = []
            for r in part.body:
                m = _BPM6_NUM.match(r[0])
                if not m:
                    raise ValueError(f"{name} part {part.n}: row without a BPM6 item number: {r[0]!r}")
                number, label = m.group(1), clean_label(m.group(2))
                got.append(number)
                seen.setdefault(number, label)
                for c, (period, pt, side) in cols.items():
                    v = num(r[c])
                    if v is None:
                        continue
                    rows.append(
                        base_row(
                            p,
                            _page=name,
                            _part=part.n,
                            series_id=f"{'bpm6q' if quarterly else 'bpm6'}.{'inr' if unit == INR else 'usd'}."
                            f"{bpm6_code(number)}.{side}.current",
                            item_code=bpm6_code(number),
                            item_label=label,
                            side=side,
                            stock_flow="flow",
                            period=period,
                            period_type=pt,
                            value=v,
                            unit=unit,
                            estimate_stage=stage_from_note(period, prelim),
                        )
                    )
            if got != BPM6_ITEMS:
                raise ValueError(f"{name} part {part.n}: BPM6 item numbers differ from the expected list: {got}")
        _attach_prov(ctx, rows, name, p, raw, unit, ps, "rows matched by BPM6 item number; columns Credit/Debit/Net per period")
    return rows


def _attach_prov(
    ctx: BuildContext,
    rows: list[dict[str, Any]],
    name: str,
    p: Page,
    raw: RawFile,
    unit: str,
    ps: list[Part],
    how: str,
    *,
    unit_filter: Callable[[dict[str, Any]], bool] | None = None,
    caption: str | None = None,
    conversion: str = "none",
) -> None:
    """One provenance record per (page, unit): locator lists the parts and their periods."""
    mine = [r for r in rows if r.get("_page") == name and r["unit"] == unit and "prov_id" not in r]
    if unit_filter:
        mine = [r for r in mine if unit_filter(r)]
    if not mine:
        raise ValueError(f"{name}: no {unit} values parsed")
    desc = []
    for part in ps:
        pers = sorted({r["period"] for r in mine if r["_part"] == part.n})
        if pers:
            desc.append(f"part {part.n} ({pers[0]}..{pers[-1]})" if len(pers) > 1 else f"part {part.n} ({pers[0]})")
    pid = ctx.prov(
        raw=raw,
        table_id=p.table,
        locator=f"HTML page PublicationsView.aspx?id={p.pv_id}: {'; '.join(desc)}; {how}",
        unit_as_published=caption or CAPTION[unit],
        conversion=conversion,
        price_basis="current" if unit in (INR, USD) else "n/a",
        vintage=p.edition,
        release=REL[p.edition],
    )
    for r in mine:
        r["prov_id"] = pid


def finish(rows: list[dict[str, Any]]) -> pl.DataFrame:
    for r in rows:
        r.pop("_page", None)
        r.pop("_part", None)
        if r["unit"] not in (INR, USD):
            r["price_basis"] = "n/a"
    return pl.DataFrame(rows, infer_schema_length=None)


def dataset_bpm6_annual(ctx: BuildContext) -> Dataset:
    rows = build_bpm6(ctx, [("hbs2026_t126.html", USD), ("hbs2026_t127.html", INR)], quarterly=False)
    return Dataset(
        f"{UNIT}_bop_bpm6_annual",
        finish(rows),
        "BoP BPM6 standard presentation, annual 2022-23..2025-26, credit/debit/net, Rs crore and US$ mn (HBS T126/T127)",
    )


def dataset_bpm6_quarterly(ctx: BuildContext) -> Dataset:
    rows = build_bpm6(
        ctx,
        [
            ("hbs2025_t196.html", USD),
            ("hbs2025_t197.html", INR),
            ("hbs2026_t197.html", USD),
            ("hbs2026_t198.html", INR),
        ],
        quarterly=True,
    )
    return Dataset(
        f"{UNIT}_bop_bpm6_quarterly",
        finish(rows),
        "BoP BPM6 quarterly Q1 2023-24..Q4 2025-26 (HBS 2024-25 T196/T197 and 2025-26 T197/T198), Rs crore and US$ mn",
    )


# ---------------------------------------------------------------------------------------------
# Overall BoP, old (BPM5-style) format: T124 (US$) / T125 (Rs)
# ---------------------------------------------------------------------------------------------

H = None  # heading row without values
OLD_BOP: list[tuple[str | None, str]] = [
    (H, "A. Current account"),
    ("ca.merchandise", "1. Merchandise"),
    ("ca.invisibles", "2. Invisibles (a+b+c)"),
    ("ca.services", "a) Services"),
    ("ca.services.travel", "i) Travel"),
    ("ca.services.transportation", "ii) Transportation"),
    ("ca.services.insurance", "iii) Insurance"),
    ("ca.services.gnie", "iv) G.n.i.e."),
    ("ca.services.miscellaneous", "v) Miscellaneous"),
    ("ca.services.misc.software", "of which: Software services"),
    ("ca.services.misc.business", "Business services"),
    ("ca.services.misc.financial", "Financial services"),
    ("ca.services.misc.communication", "Communication services"),
    ("ca.transfers", "b) Transfers"),
    ("ca.transfers.official", "i) Official"),
    ("ca.transfers.private", "ii) Private"),
    ("ca.income", "c) Income"),
    ("ca.income.investment", "i) Investment income"),
    ("ca.income.compensation_of_employees", "ii) Compensation of employees"),
    ("ca.total", "Total Current account (1+2)"),
    (H, "B. Capital account"),
    ("ka.foreign_investment", "1. Foreign investment (a+b)"),
    ("ka.fdi", "a) Foreign direct investment (i+ii)"),
    ("ka.fdi.in_india", "i) In India"),
    ("ka.fdi.in_india.equity", "Equity"),
    ("ka.fdi.in_india.reinvested_earnings", "Reinvested earnings"),
    ("ka.fdi.in_india.other_capital", "Other capital"),
    ("ka.fdi.abroad", "ii) Abroad"),
    ("ka.fdi.abroad.equity", "Equity"),
    ("ka.fdi.abroad.reinvested_earnings", "Reinvested earnings"),
    ("ka.fdi.abroad.other_capital", "Other capital"),
    ("ka.portfolio", "b) Portfolio investment"),
    ("ka.portfolio.in_india", "i) In India"),
    ("ka.portfolio.in_india.fiis", "FIIs"),
    (H, "of which:"),
    ("ka.portfolio.in_india.fiis.equity", "Equity"),
    ("ka.portfolio.in_india.fiis.debt", "Debt"),
    ("ka.portfolio.in_india.gdrs_adrs", "GDRs/ADRs"),
    ("ka.portfolio.abroad", "ii) Abroad"),
    ("ka.loans", "2. Loans (a+b+c)"),
    ("ka.loans.external_assistance", "a) External assistance"),
    ("ka.loans.external_assistance.by_india", "i) By India"),
    ("ka.loans.external_assistance.to_india", "ii) To India"),
    ("ka.loans.ecb", "b) Commercial borrowings"),
    ("ka.loans.ecb.by_india", "i) By India"),
    ("ka.loans.ecb.to_india", "ii) To India"),
    ("ka.loans.short_term", "c) Short term to India"),
    ("ka.loans.short_term.above_180d", "i) Suppliers' Credit & Buyers' Credit >180 days"),
    ("ka.loans.short_term.upto_180d", "ii) Suppliers' credit up to 180 days"),
    ("ka.banking_capital", "3. Banking capital (a+b)"),
    ("ka.banking_capital.commercial_banks", "a) Commercial banks"),
    ("ka.banking_capital.commercial_banks.assets", "i) Assets"),
    ("ka.banking_capital.commercial_banks.liabilities", "ii) Liabilities"),
    ("ka.banking_capital.commercial_banks.nri_deposits", "of which: Non-resident deposits"),
    ("ka.banking_capital.others", "b) Others"),
    ("ka.rupee_debt_service", "4. Rupee debt service"),
    ("ka.other_capital", "5. Other capital"),
    ("ka.total", "Total capital account (1 to 5)"),
    ("errors_omissions", "C. Errors & omissions"),
    ("overall_balance", "D. Overall balance (A+B+C)"),
    ("monetary_movements", "E. Monetary movements (i+ii)"),
    ("monetary_movements.imf", "i) I.M.F."),
    ("monetary_movements.reserves", "ii) Foreign exchange reserves (Increase- / Decrease+)"),
    ("monetary_movements.reserves.sdr_allocation", "of which: SDR Allocation"),
]


def _norm_quotes(s: str) -> str:
    return s.replace("’", "'").replace("‘", "'")


def dataset_bop_old(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    for name, unit in (("hbs2026_t124.html", USD), ("hbs2026_t125.html", INR)):
        p, raw, _ = page_meta(ctx, name)
        prelim = prelim_year(raw.path)
        ps = parts(raw.path)
        for part in ps:
            expect_text(part, "crore" if unit == INR else "million")
            cols = _cdn_columns(part, quarterly=False)
            labels = [_norm_quotes(r[0]) for r in part.body]
            codes = match_sequence(labels, OLD_BOP, f"{name} part {part.n}")
            for r, code in zip(part.body, codes, strict=True):
                vals = {c: num(r[c]) for c in cols}
                if code is None:
                    if any(v is not None for v in vals.values()):
                        raise ValueError(f"{name}: heading row {r[0]!r} carries values")
                    continue
                for c, (period, pt, side) in cols.items():
                    if vals[c] is None:
                        continue
                    rows.append(
                        base_row(
                            p,
                            _page=name,
                            _part=part.n,
                            series_id=f"bop_old.{'inr' if unit == INR else 'usd'}.{code}.{side}.current",
                            item_code=code,
                            item_label=clean_label(r[0]),
                            side=side,
                            stock_flow="flow",
                            period=period,
                            period_type=pt,
                            value=vals[c],
                            unit=unit,
                            estimate_stage=stage_from_note(period, prelim),
                        )
                    )
        _attach_prov(ctx, rows, name, p, raw, unit, ps, "rows matched by the full ordered label sequence")
    return Dataset(
        f"{UNIT}_bop_overall_annual",
        finish(rows),
        "BoP old (BPM5-style) format with ECB, NRI deposits, short-term credit, 2020-21..2025-26 (HBS T124/T125)",
    )


# ---------------------------------------------------------------------------------------------
# Invisibles by category (T130 US$ / T131 Rs), 2006-07..2025-26
# ---------------------------------------------------------------------------------------------

INVISIBLES = [
    ("nonfactor_services", "I. Non-factor Services, Net (i to v)"),
    ("nonfactor_services.travel", "i) Travel, Net"),
    ("nonfactor_services.transportation", "ii) Transportation, Net"),
    ("nonfactor_services.insurance", "iii) Insurance, Net"),
    ("nonfactor_services.gnie", "iv) G.n.i.e., Net"),
    ("nonfactor_services.miscellaneous", "v) Miscellaneous, Net"),
    ("income", "II. Income, Net"),
    ("income.investment", "i) Investment income, Net"),
    ("income.compensation_of_employees", "ii) Compensation of Employees, Net"),
    ("private_transfers", "III. Private Transfers, Net"),
    ("official_transfers", "IV. Official Transfers, Net"),
    ("invisibles", "V. Invisibles, Net (I to IV)"),
]
INVIS_SEQ: list[tuple[str | None, str]] = []
for _c, _l in INVISIBLES:
    INVIS_SEQ += [(f"{_c}|net", _l), (f"{_c}|receipts", "Receipts"), (f"{_c}|payments", "Payments")]


def dataset_invisibles(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    labels_of = dict(INVISIBLES)
    for name, unit in (("hbs2026_t130.html", USD), ("hbs2026_t131.html", INR)):
        p, raw, _ = page_meta(ctx, name)
        prelim = prelim_year(raw.path)
        ps = parts(raw.path)
        for part in ps:
            hdr = next(r for r in part.grid.rows if r and r[0].lower().startswith("item"))
            cols = {c: normalize_fy(hdr[c]) for c in range(1, len(hdr))}
            codes = match_sequence([r[0] for r in part.body], INVIS_SEQ, f"{name} part {part.n}")
            for r, cs in zip(part.body, codes, strict=True):
                code, side = cs.split("|")
                for c, period in cols.items():
                    v = num(r[c])
                    if v is None:
                        continue
                    rows.append(
                        base_row(
                            p,
                            _page=name,
                            _part=part.n,
                            series_id=f"invis.{'inr' if unit == INR else 'usd'}.{code}.{side}.current",
                            item_code=code,
                            item_label=clean_label(labels_of[code].replace(", Net", "")),
                            side=side,
                            stock_flow="flow",
                            period=period,
                            period_type="fy",
                            value=v,
                            unit=unit,
                            estimate_stage=stage_from_note(period, prelim),
                        )
                    )
        caption = "Rs crore" if unit == INR else "US$ million"
        expect_text(ps[0], "crore" if unit == INR else "million")
        _attach_prov(ctx, rows, name, p, raw, unit, ps, "rows matched by the ordered label sequence (Net/Receipts/Payments)", caption=caption)
    return Dataset(
        f"{UNIT}_invisibles_annual",
        finish(rows),
        "Invisibles by category (services, income, private/official transfers), 2006-07..2025-26 (HBS T130/T131)",
    )


# ---------------------------------------------------------------------------------------------
# Exchange rate INR per USD: T133 (financial year average and end-year) and T205 (monthly)
# ---------------------------------------------------------------------------------------------

_MONTHS = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}


def _usd_columns(part: Part) -> tuple[int, int]:
    cur = next(r for r in part.head if "US Dollar" in r)
    kind = next(r for r in part.head if "Average" in r)
    cols = [c for c, v in enumerate(cur) if v == "US Dollar"]
    if len(cols) != 2:
        raise ValueError(f"expected two US Dollar columns, got {cols}")
    avg = next(c for c in cols if kind[c] == "Average")
    end = next(c for c in cols if kind[c].lower().startswith("end"))
    return avg, end


def dataset_fx(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    # T133: financial-year average and end-year (end-March) rates
    name = "hbs2026_t133.html"
    p, raw, _ = page_meta(ctx, name)
    (part,) = parts(raw.path)
    expect_text(part, "₹ per unit of foreign currency", "End-year")
    avg, end = _usd_columns(part)
    for r in part.body:
        period = normalize_fy(r[0])
        y2 = int(period[:4]) + 1
        for c, item, per, pt, lab in (
            (avg, "usd_fy_average", period, "fy", "US Dollar, average of the financial year"),
            (end, "usd_end_march", f"{y2}-03-31", "date", "US Dollar, end of financial year (end-March)"),
        ):
            v = num(r[c])
            if v is None:
                continue
            rows.append(
                base_row(
                    p,
                    _page=name,
                    _part=1,
                    series_id=f"t133.{item}",
                    item_code=item,
                    item_label=lab,
                    dim_other="currency=usd",
                    stock_flow="n/a",
                    period=per,
                    period_type=pt,
                    value=v,
                    unit="INR_per_USD",
                    price_basis="n/a",
                    estimate_stage="n.a.",
                )
            )
    _fx_prov(ctx, rows, name, p, raw, [part], "rows = financial years 1986-87..2025-26; US Dollar Average and End-year columns")
    # T205: monthly average and end-month rates, Jan 2022 onwards
    name = "hbs2026_t205.html"
    p, raw, _ = page_meta(ctx, name)
    (part,) = parts(raw.path)
    expect_text(part, "₹ per unit of foreign currency", "End-month")
    avg, end = _usd_columns(part)
    year = None
    for r in part.body:
        if re.fullmatch(r"\d{4}", r[0]):
            year = int(r[0])
            continue
        if r[0] not in _MONTHS or year is None:
            raise ValueError(f"{name}: unexpected row {r[0]!r}")
        m = _MONTHS[r[0]]
        for c, item, per, pt, lab in (
            (avg, "usd_month_average", f"{year}-{m:02d}", "month", "US Dollar, monthly average"),
            (end, "usd_end_month", month_end(year, m), "date", "US Dollar, end of month (last working day)"),
        ):
            v = num(r[c])
            if v is None:
                continue
            rows.append(
                base_row(
                    p,
                    _page=name,
                    _part=1,
                    series_id=f"t205.{item}",
                    item_code=item,
                    item_label=lab,
                    dim_other="currency=usd",
                    stock_flow="n/a",
                    period=per,
                    period_type=pt,
                    value=v,
                    unit="INR_per_USD",
                    price_basis="n/a",
                    estimate_stage="n.a.",
                )
            )
    _fx_prov(ctx, rows, name, p, raw, [part], "rows = months (year rows then Jan..Dec); US Dollar Average and End-month columns")
    return Dataset(
        f"{UNIT}_fx_inr_usd",
        finish(rows),
        "Rupee per US dollar (INR_per_USD), the rate series for US$ -> Rs conversion (DECISIONS D1-8): "
        "t133.usd_fy_average (fy 1986-87..2025-26) and t133.usd_end_march (date) from HBS T133; "
        "t205.usd_month_average (month 2022-01..2026-06) and t205.usd_end_month (date) from HBS T205. "
        "Filter to one series_id before joining on period; no calendar-year average",
    )


def _fx_prov(ctx, rows, name, p, raw, ps, how) -> None:
    mine = [r for r in rows if r.get("_page") == name]
    pid = ctx.prov(
        raw=raw,
        table_id=p.table,
        locator=f"HTML page PublicationsView.aspx?id={p.pv_id}: {how}",
        unit_as_published="Rs per unit of foreign currency (Rs per US dollar)",
        price_basis="n/a",
        vintage=p.edition,
        release=REL[p.edition],
        notes="Table notes: official exchange rates 1983-84 to 1991-92; FEDAI indicative rates from 1992-93 to April "
        "2012; RBI reference rates from May 2012; FBIL reference rates from 10 July 2018. End-period rows are dated "
        "to the last calendar day of the month; the rate is that of the last working day.",
    )
    for r in mine:
        r["prov_id"] = pid


# ---------------------------------------------------------------------------------------------
# NRI deposits: T139/T140 outstanding (end-March) and T141/T142 flows, by scheme
# ---------------------------------------------------------------------------------------------

NRI_SCHEMES = {
    "FCNR(A)": "fcnr_a",
    "FCNR(B)": "fcnr_b",
    "NR(E)RA": "nr_e_ra",
    "NR(NR)RD": "nr_nr_rd",
    "NRO": "nro",
    "FC(B&O)D": "fc_b_o_d",
    "FC(O)N": "fc_o_n",
    "Total": "total",
}


def dataset_nri(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    for name, unit, kind in (
        ("hbs2026_t139.html", USD, "stock"),
        ("hbs2026_t140.html", INR, "stock"),
        ("hbs2026_t141.html", USD, "flow"),
        ("hbs2026_t142.html", INR, "flow"),
    ):
        p, raw, _ = page_meta(ctx, name)
        (part,) = parts(raw.path)
        expect_text(part, "crore" if unit == INR else "million")
        hdr = next(r for r in part.head if "Total" in r)
        if hdr[1:] != list(NRI_SCHEMES):
            raise ValueError(f"{name}: scheme header {hdr}")
        prelim = prelim_year(raw.path)
        for r in part.body:
            if kind == "stock":
                if not re.fullmatch(r"\d{4}", r[0]):
                    raise ValueError(f"{name}: year {r[0]!r}")
                period, pt = f"{r[0]}-03-31", "date"
            else:
                period, pt = normalize_fy(r[0]), "fy"
            for c, scheme in enumerate(NRI_SCHEMES.values(), 1):
                v = num(r[c])
                if v is None:
                    continue
                rows.append(
                    base_row(
                        p,
                        _page=name,
                        _part=1,
                        series_id=f"nri.{kind}.{'inr' if unit == INR else 'usd'}.{scheme}.current",
                        item_code=f"nri_deposits_{'outstanding' if kind == 'stock' else 'flow'}",
                        item_label=("Non-resident deposits outstanding" if kind == "stock" else "Inflows(+)/outflows(-) under non-resident deposit schemes"),
                        instrument=scheme,
                        side="liabilities",
                        stock_flow=kind,
                        period=period,
                        period_type=pt,
                        value=v,
                        unit=unit,
                        estimate_stage=stage_from_note(period, prelim) if pt == "fy" else "n.a.",
                    )
                )
        _attach_prov(ctx, rows, name, p, raw, unit, [part], "rows = years, columns = deposit schemes (header matched)")
    return Dataset(
        f"{UNIT}_nri_deposits",
        finish(rows),
        "NRI deposits by scheme: outstanding end-March 2008-2026 and annual flows 2007-08..2025-26 (HBS T139-T142)",
    )


# ---------------------------------------------------------------------------------------------
# Foreign investment inflows (T143) and foreign exchange reserves (T144)
# ---------------------------------------------------------------------------------------------

T143_GROUPS = [
    ("fdi_gross_inflows", "Gross Inflows/ Gross Investments"),
    ("fdi_repatriation", "Repatriation/ Disinvestment"),
    ("fdi_to_india_net", "Direct Investment to India"),
    ("fdi_by_india", "FDI by India"),
    ("fdi_net", "Net Foreign Direct Investment"),
    ("portfolio_net", "Net Portfolio Investment"),
    ("foreign_investment_net", "Total"),
]


def dataset_foreign_investment(ctx: BuildContext) -> Dataset:
    name = "hbs2026_t143.html"
    p, raw, _ = page_meta(ctx, name)
    (part,) = parts(raw.path)
    grp, un = part.head[0], part.head[1]
    prelim = prelim_year(raw.path)
    cols = {}
    for c in range(1, len(grp)):
        g = next((code for code, lab in T143_GROUPS if norm(lab) == norm(grp[c])), None)
        if g is None:
            raise ValueError(f"{name}: unknown column group {grp[c]!r}")
        u = INR if "crore" in un[c].lower() else USD if "million" in un[c].lower() else None
        if u is None:
            raise ValueError(f"{name}: unit header {un[c]!r}")
        cols[c] = (g, u)
    if sorted(set(cols.values())) != sorted({(g, u) for g, _ in T143_GROUPS for u in (INR, USD)}):
        raise ValueError(f"{name}: column set {cols}")
    labels = dict(T143_GROUPS)
    rows: list[dict[str, Any]] = []
    for r in part.body:
        period = normalize_fy(r[0])
        for c, (g, u) in cols.items():
            v = num(r[c])
            if v is None:
                continue
            rows.append(
                base_row(
                    p,
                    _page=name,
                    _part=1,
                    series_id=f"t143.{'inr' if u == INR else 'usd'}.{g}.current",
                    item_code=g,
                    item_label=labels[g],
                    stock_flow="flow",
                    period=period,
                    period_type="fy",
                    value=v,
                    unit=u,
                    estimate_stage="Provisional" if period == prelim else "n.a.",
                )
            )
    for u in (INR, USD):
        _attach_prov(ctx, rows, name, p, raw, u, [part], f"rows = financial years; {'Rs crore' if u == INR else 'US$ million'} columns of each group")
    return Dataset(f"{UNIT}_foreign_investment", finish(rows), "Foreign investment inflows (FDI gross/repatriation/net, ODI, portfolio), 2004-05..2025-26 (HBS T143)")


T144_ITEMS = [("sdr", "SDRs"), ("gold", "Gold"), ("fca", "Foreign Currency Assets"), ("rtp", "Reserve Tranche Position"), ("total", "Total")]


def dataset_reserves(ctx: BuildContext) -> Dataset:
    name = "hbs2026_t144.html"
    p, raw, _ = page_meta(ctx, name)
    (part,) = parts(raw.path)
    grp, un = part.head[0], part.head[1]
    cols = {}
    for c in range(1, len(grp)):
        g = next((code for code, lab in T144_ITEMS if norm(re.sub(r"[#*]+", "", grp[c])) == norm(lab)), None)
        u = INR if "crore" in un[c].lower() else USD if "million" in un[c].lower() else None
        if g is None or u is None:
            raise ValueError(f"{name}: column {grp[c]!r} / {un[c]!r}")
        cols[c] = (g, u)
    labels = dict(T144_ITEMS)
    rows: list[dict[str, Any]] = []
    for r in part.body:
        period = normalize_fy(r[0])
        date = f"{int(period[:4]) + 1}-03-31"
        for c, (g, u) in cols.items():
            v = num(r[c])
            if v is None:
                continue
            rows.append(
                base_row(
                    p,
                    _page=name,
                    _part=1,
                    series_id=f"t144.{'inr' if u == INR else 'usd'}.{g}.current",
                    item_code=f"reserves_{g}",
                    item_label=f"Foreign exchange reserves: {labels[g]}",
                    instrument=g,
                    side="assets",
                    stock_flow="stock",
                    period=date,
                    period_type="date",
                    value=v,
                    unit=u,
                    estimate_stage="n.a.",
                )
            )
    for u in (INR, USD):
        _attach_prov(ctx, rows, name, p, raw, u, [part], f"rows = end of financial year (1968-69..2025-26), dated end-March; {'Rs crore' if u == INR else 'US$ million'} column of each component")
    return Dataset(f"{UNIT}_fx_reserves", finish(rows), "Foreign exchange reserves by component, end-March 1969-2026, Rs crore and US$ mn (HBS T144)")


# ---------------------------------------------------------------------------------------------
# External debt, end-March 2008-2026 (T145 US$ / T146 Rs)
# ---------------------------------------------------------------------------------------------

M = "multilateral"
B = "bilateral"
DEBT_A: list[tuple[str | None, str]] = [
    (M, "I. Multilateral"),
    (f"{M}.govt", "A. Government Borrowing"),
    (f"{M}.govt.concessional", "i) Concessional"),
    (f"{M}.govt.concessional.ida", "a) IDA"),
    (f"{M}.govt.concessional.others", "b) Others"),
    (f"{M}.govt.nonconcessional", "ii) Non-concessional"),
    (f"{M}.govt.nonconcessional.ibrd", "a) IBRD"),
    (f"{M}.govt.nonconcessional.others", "b) Others"),
    (f"{M}.nongovt", "B. Non-government Borrowing"),
    (f"{M}.nongovt.concessional", "i) Concessional"),
    (f"{M}.nongovt.nonconcessional", "ii) Non-concessional"),
    (f"{M}.nongovt.nonconcessional.public", "a) Public Sector"),
    (f"{M}.nongovt.nonconcessional.public.ibrd", "IBRD"),
    (f"{M}.nongovt.nonconcessional.public.others", "Others"),
    (f"{M}.nongovt.nonconcessional.fin_inst", "b) Financial Institutions"),
    (f"{M}.nongovt.nonconcessional.fin_inst.ibrd", "IBRD"),
    (f"{M}.nongovt.nonconcessional.fin_inst.others", "Others"),
    (f"{M}.nongovt.nonconcessional.private", "c) Private Sector"),
    (f"{M}.nongovt.nonconcessional.private.ibrd", "IBRD"),
    (f"{M}.nongovt.nonconcessional.private.others", "Others"),
    (B, "II. Bilateral"),
    (f"{B}.govt", "A. Government Borrowing"),
    (f"{B}.govt.concessional", "i) Concessional"),
    (f"{B}.govt.nonconcessional", "ii) Non-concessional"),
    (f"{B}.nongovt", "B. Non-government Borrowing"),
    (f"{B}.nongovt.concessional", "i) Concessional"),
    (f"{B}.nongovt.concessional.public", "a) Public Sector"),
    (f"{B}.nongovt.concessional.fin_inst", "b) Financial Institutions"),
    (f"{B}.nongovt.concessional.private", "c) Private Sector"),
    (f"{B}.nongovt.nonconcessional", "ii) Non-concessional"),
    (f"{B}.nongovt.nonconcessional.public", "a) Public Sector"),
    (f"{B}.nongovt.nonconcessional.fin_inst", "b) Financial Institutions"),
    (f"{B}.nongovt.nonconcessional.private", "c) Private Sector"),
    ("imf", "III. International Monetary Fund"),
    ("trade_credit", "IV. Trade Credit"),
    ("trade_credit.buyers", "a) Buyers credit"),
    ("trade_credit.suppliers", "b) Suppliers credit"),
    ("trade_credit.export_credit_bilateral", "c) Export credit component of bilateral credit"),
    ("trade_credit.export_credit_defence", "d) Export credit for defence purposes"),
]
DEBT_B: list[tuple[str | None, str]] = [
    ("commercial_borrowing", "V. Commercial Borrowing"),
    ("commercial_borrowing.bank_loans", "a) Commercial bank loans"),
    ("commercial_borrowing.securitized", "b) Securitized borrowings (inclu. IDBs and FCCBs)"),
    ("commercial_borrowing.guaranteed", "c) Loans/securitized borrowings, etc., with multilateral/bilateral guarantee and IFC(W)"),
    ("commercial_borrowing.self_liquidating", "d) Self liquidating loans"),
    ("nri_deposits", "VI. Non-resident Deposits"),
    ("rupee_debt", "VII. Rupee Debt"),
    ("rupee_debt.defence", "a) Defence"),
    ("rupee_debt.civilian", "b) Civilian"),
    ("long_term_total", "VIII. Total Long-term Debt (I to VII)"),
    ("short_term", "IX. Short-term Debt"),
    ("short_term.nri_deposits_upto_1y", "a) Non-resident deposits (up to 1 year maturity)"),
    ("short_term.trade_credit", "b) Trade-related credits"),
    ("short_term.trade_credit.above_180d", "1) Above 180 days"),
    ("short_term.trade_credit.upto_180d", "2) Up to 180 days"),
    ("short_term.fii_tbills_other", "c) FII investments on government treasury bills and other instruments"),
    ("short_term.tbills_foreign_cb", "d) Investments in treasury bills by foreign central banks and international institutions"),
    ("short_term.bank_liabilities", "e) External Debt Liabilities of (i+ii)"),
    ("short_term.bank_liabilities.central_bank", "i) Central Bank"),
    ("short_term.bank_liabilities.commercial_banks", "ii) Commercial Banks"),
    ("gross_external_debt", "X. Gross External Debt Position"),
    ("pct.concessional_share", "Concessional Debt as % of Total Debt"),
    ("pct.short_term_share", "Short-term Debt as % of Total Debt"),
    ("pct.debt_to_gdp", "Debt to GDP Ratio (%)"),
    ("pct.debt_service_ratio", "Debt Service Ratio (%)"),
]


def dataset_external_debt(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    for name, unit in (("hbs2026_t145.html", USD), ("hbs2026_t146.html", INR)):
        p, raw, _ = page_meta(ctx, name)
        ps = parts(raw.path)
        if len(ps) != 4:
            raise ValueError(f"{name}: expected 4 parts, got {len(ps)}")
        for part in ps:
            expect_text(part, "crore" if unit == INR else "million")
            hdr = next(r for r in part.head if r and r[0] == "Item")
            dates = {c: f"{int(hdr[c])}-03-31" for c in range(1, len(hdr))}
            seq = DEBT_A if norm(part.body[0][0]) == norm(DEBT_A[0][1]) else DEBT_B
            codes = match_sequence([r[0] for r in part.body], seq, f"{name} part {part.n}")
            for r, code in zip(part.body, codes, strict=True):
                assert code is not None
                is_pct = code.startswith("pct.")
                for c, date in dates.items():
                    v = num(r[c])
                    if v is None:
                        continue
                    rows.append(
                        base_row(
                            p,
                            _page=name,
                            _part=part.n,
                            series_id=f"debt.{p.table[-3:]}.{code}" if is_pct else f"debt.{'inr' if unit == INR else 'usd'}.{code}.current",
                            item_code=code,
                            item_label=clean_label(r[0]),
                            side="liabilities",
                            stock_flow="n/a" if is_pct else "stock",
                            period=date,
                            period_type="date",
                            value=v,
                            unit="percent" if is_pct else unit,
                            estimate_stage="n.a.",
                        )
                    )
        _attach_prov(ctx, rows, name, p, raw, unit, ps, "rows matched by the full ordered label sequence; columns = end-March of each year")
        pct = [r for r in rows if r.get("_page") == name and r["unit"] == "percent"]
        if pct:
            _attach_prov(
                ctx, rows, name, p, raw, "percent", ps, "ratio rows (% of total debt, % of GDP, debt service ratio)", caption="percent"
            )
    # The ratio rows are printed in both tables and are kept from both (series debt.145.* and
    # debt.146.*): they are not identical (debt/GDP end-March 2023: 19.1 in T145, 19.6 in T146;
    # logged as external_sector issue, checked in the unit tests).
    return Dataset(f"{UNIT}_external_debt", finish(rows), "India's external debt by creditor/instrument, end-March 2008-2026, Rs crore and US$ mn, plus ratios (HBS T145/T146)")


# ---------------------------------------------------------------------------------------------
# International investment position, quarterly, compact (T199/T200; 2024-25 ed. T198/T199)
# ---------------------------------------------------------------------------------------------

_IIP_NUM = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.+)$")
IIP_EXPECT = [
    "niip", "assets", "assets.1", "assets.1.1", "assets.1.2", "assets.2", "assets.2.1", "assets.2.2", "assets.3",
    "assets.3.1", "assets.3.2", "assets.3.3", "assets.3.4", "assets.4", "liabilities", "liabilities.1",
    "liabilities.1.1", "liabilities.1.2", "liabilities.2", "liabilities.2.1", "liabilities.2.2", "liabilities.3",
    "liabilities.3.1", "liabilities.3.2", "liabilities.3.3", "liabilities.3.4", "liabilities.3.5", "memo.assets_to_liabilities_pct",
]  # fmt: skip


def _iip_period(text: str) -> tuple[str, str]:
    m = re.fullmatch(r"(\d{4}-\d{2}):\s*Q([1-4])\s*(PR|P|R)?", text)
    if not m:
        raise ValueError(f"unexpected IIP quarter header {text!r}")
    y = int(m.group(1)[:4])
    q = int(m.group(2))
    date = {1: month_end(y, 6), 2: month_end(y, 9), 3: month_end(y, 12), 4: month_end(y + 1, 3)}[q]
    # Table notes: "PR: Partially Revised, P: Provisional". 'R' is not defined there; read as Revised.
    stage = {"PR": "Partially Revised", "P": "Provisional", "R": "Revised", None: "n.a."}[m.group(3)]
    return date, stage


def dataset_iip_quarterly(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    for name, unit in (
        ("hbs2025_t198.html", USD),
        ("hbs2025_t199.html", INR),
        ("hbs2026_t199.html", USD),
        ("hbs2026_t200.html", INR),
    ):
        p, raw, _ = page_meta(ctx, name)
        (part,) = parts(raw.path)
        expect_text(part, "crore" if unit == INR else "million")
        hdr = next(r for r in part.head if r and r[0] == "Period")
        cols = {c: _iip_period(hdr[c]) for c in range(1, len(hdr))}
        codes, side = [], None
        for r in part.body:
            lab = r[0]
            if lab.startswith("Net International Investment Position"):
                code = "niip"
            elif lab.startswith("A. Assets"):
                code, side = "assets", "assets"
            elif lab.startswith("B. Liabilities"):
                code, side = "liabilities", "liabilities"
            elif lab.lower().startswith("memo item"):
                code = "memo.assets_to_liabilities_pct"
            elif side == "liabilities" and norm(lab) == norm("of which: Special drawing rights (Net incurrence of liabilities)"):
                # HBS 2024-25 prints SDR allocations as 'of which' under 3.4, but they are additive
                # (3 = 3.1+..+3.4+SDR), exactly as item 3.5 of the 2025-26 edition: same series.
                code = "liabilities.3.5"
            else:
                m = _IIP_NUM.match(lab)
                if not m or side is None:
                    raise ValueError(f"{name}: unexpected IIP row {lab!r}")
                code = f"{side}.{m.group(1)}"
            codes.append(code)
            is_pct = code.startswith("memo")
            for c, (date, stage) in cols.items():
                v = num(r[c])
                if v is None:
                    continue
                rows.append(
                    base_row(
                        p,
                        _page=name,
                        _part=1,
                        series_id=f"iipq.{code}.pct" if is_pct else f"iipq.{'inr' if unit == INR else 'usd'}.{code}.current",
                        item_code=code,
                        item_label=clean_label(lab),
                        side={"assets": "assets", "liabilities": "liabilities"}.get(code.split(".")[0], "net" if code == "niip" else None),
                        stock_flow="n/a" if is_pct else "stock",
                        period=date,
                        period_type="date",
                        value=v,
                        unit="percent" if is_pct else unit,
                        estimate_stage=stage,
                        _pct_dup=is_pct and unit == USD,
                    )
                )
        if codes not in (IIP_EXPECT, IIP_EXPECT[:-1]):  # the memo ratio row is new in the 2025-26 edition
            raise ValueError(f"{name}: IIP rows differ from the expected layout: {codes}")
        _attach_prov(ctx, rows, name, p, raw, unit, [part], "rows matched by A./B. section and item number; columns = quarter-ends")
        if "memo.assets_to_liabilities_pct" in codes:
            _attach_prov(ctx, rows, name, p, raw, "percent", [part], "memo row: assets to liabilities ratio (%)", caption="percent")
    rows = [r for r in rows if not r.pop("_pct_dup", False)]
    return Dataset(
        f"{UNIT}_iip_quarterly",
        finish(rows),
        "International investment position (compact), quarter-ends Jun 2023..Mar 2026, Rs crore and US$ mn (HBS T198-T200)",
    )


def build_all(ctx: BuildContext) -> list[Dataset]:
    return [
        dataset_fx(ctx),
        dataset_bpm6_annual(ctx),
        dataset_bpm6_quarterly(ctx),
        dataset_bop_old(ctx),
        dataset_invisibles(ctx),
        dataset_nri(ctx),
        dataset_foreign_investment(ctx),
        dataset_reserves(ctx),
        dataset_external_debt(ctx),
        dataset_iip_quarterly(ctx),
    ]


__all__ = ["PAGES", "build_all", "fetch_all", "slug", "fy"]
