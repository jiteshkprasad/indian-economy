"""RBI releases outside the Handbook, all HTML pages on www.rbi.org.in:

- ECB/FCCB/RDB registrations, monthly, April 2023 - March 2024 (loan level, with route totals).
- Census on Foreign Liabilities and Assets (FLA) of direct investment entities, 2023-24 round
  (released 11 Oct 2024) and 2024-25 round (29 Oct 2025, provisional); positions at end-March
  2023, 2024 and 2025. The round is the `vintage`.
- India's Remittances Survey, 6th round (2023-24), RBI Bulletin March 2025: Tables 1 and 2.
  Destination States/UTs are coded with pipeline/core/geo.py (DECISIONS D1-9); the 2016-17
  Jammu and Kashmir share is the former State incl. Ladakh, IN-XJK.
- Survey on computer software and ITES exports: 2024-25 round (4 Nov 2025; years 2023-24 and
  2024-25) and 2025-26 round (18 Sep 2026; years 2024-25 and 2025-26), Tables 2-8.
- LRS outward remittances by purpose, Bulletin 'Current Statistics' table (No. 35 in June 2024
  and June 2025, No. 36 in June 2026): FY total plus four months each.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

import polars as pl

from pipeline.core import geo
from pipeline.core.unit import BuildContext, Dataset, RawFile
from pipeline.core.units import (
    clean_label,
    normalize_fy,
    parse_number,
    period_end,
    period_start,
    slug,
    usd_million_to_inr_crore,
)

from ._html import Grid, find_grid, is_colnum_row, leaf_tables, page_date, page_text

UNIT = "external_sector"

SRC_ECB = "rbi_ecb_monthly"
SRC_FLA = "rbi_fla_census"
SRC_REM = "rbi_remittances_survey"
SRC_ITES = "rbi_ites_survey"
SRC_LRS = "rbi_lrs_outward_remittances"

ECB_URL = "https://www.rbi.org.in/Scripts/ECBUserView.aspx?Id={}"
ECB_LISTING = "https://rbi.org.in/Scripts/ECBView.aspx"
# ECBUserView ids of the monthly pages April 2023 .. March 2024 (id 235 = April 2023; each page's
# own heading "Data on ECB/FCCB for the month of <Month YYYY>" is asserted at build time).
ECB_IDS = {f"{2023 + (m < 4)}-{m:02d}": 235 + i for i, m in enumerate([4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3])}

FLA_URL = "https://www.rbi.org.in/Scripts/PublicationsView.aspx?id=23438"
FLA_2324_PRID = 58874
FLA_LANDING = "https://rbi.org.in/Scripts/AnnualPublications.aspx?head=Annual+Census+on+Foreign+Liabilities+and+Assets+of+Indian+Companies"
REM_URL = "https://www.rbi.org.in/scripts/BS_ViewBulletin.aspx?Id=23260"
PR_URL = "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid={}"
ITES_PRIDS = {"2024-25": 61562, "2025-26": 63625}  # survey round -> press release id
LRS_IDS = {"2024-06": 22690, "2025-06": 23490, "2026-06": 24281}  # Bulletin issue -> table page id
BULLETIN = "https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx?Id={}"

MONTHS = "January February March April May June July August September October November December".split()


def fetch_all(ctx) -> None:
    for month, i in ECB_IDS.items():
        ctx.fetch(SRC_ECB, ECB_URL.format(i), name=f"ecb_{month}.html", referer=ECB_LISTING, expect="html")
    ctx.fetch(SRC_FLA, FLA_URL, name="fla_census_2024_25.html", referer=FLA_LANDING, expect="html")
    # 2023-24 round (press release of 11 Oct 2024), linked from the 2024-25 page as "the previous data release"
    ctx.fetch(SRC_FLA, PR_URL.format(FLA_2324_PRID), name="fla_census_2023_24.html", expect="html")
    ctx.fetch(SRC_REM, REM_URL, name="remittances_survey_r6.html", expect="html")
    for rnd, prid in ITES_PRIDS.items():
        ctx.fetch(SRC_ITES, PR_URL.format(prid), name=ites_name(rnd), expect="html")
    for issue, i in LRS_IDS.items():
        ctx.fetch(SRC_LRS, BULLETIN.format(i), name=f"lrs_bulletin_{issue}.html", expect="html")


def ites_name(rnd: str) -> str:
    return f"ites_survey_{rnd.replace('-', '_')}.html"


def num(cell: str) -> float | None:
    return parse_number(cell)


def _row(source: str, table: str, vintage: str, **kw: Any) -> dict[str, Any]:
    r = {"source_id": source, "table_id": table, "vintage": vintage, "status": "official", "price_basis": "current"}
    r.update(kw)
    if r["unit"] not in ("INR_crore", "USD_million"):
        r["price_basis"] = "n/a"
    return r


def _prov_blocks(ctx: BuildContext, rows: list[dict[str, Any]], raw: RawFile, release: str, locator_of, caption_of) -> None:
    """One provenance record per (table_id, unit) block of rows without a prov_id yet."""
    blocks: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in rows:
        if "prov_id" not in r:
            blocks.setdefault((r["table_id"], r["unit"]), []).append(r)
    for (table, unit), rs in blocks.items():
        caption, conversion = caption_of(unit)
        pid = ctx.prov(
            raw=raw,
            table_id=table,
            locator=locator_of(table, unit, rs),
            unit_as_published=caption,
            conversion=conversion,
            price_basis="current" if unit in ("INR_crore", "USD_million") else "n/a",
            vintage=rs[0]["vintage"],
            release=release,
        )
        for r in rs:
            r["prov_id"] = pid


# ---------------------------------------------------------------------------------------------
# ECB / FCCB / RDB registrations, April 2023 - March 2024
# ---------------------------------------------------------------------------------------------

# 'Grand total' (Feb and Mar 2024 pages) is the all-routes total, printed under a different label.
_TOTAL_ROUTE = [("automatic route+approval route", "all"), ("automatic route + approval route", "all"),
                ("automatic route", "automatic"), ("approval route", "approval"), ("", "all"),
                ("grand", "all")]  # fmt: skip


def _ecb_table(g: Grid, month: str, kind: str) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """Loans and published totals from one ECB/FCCB or RDB table of a monthly page."""
    hdr = next(r for r in g.rows if "Borrower" in r)
    def find(prefix: str) -> int:
        hits = [i for i, h in enumerate(hdr) if h.lower().startswith(prefix.lower())]
        if len(hits) != 1:
            raise ValueError(f"ECB {month} {kind}: column {prefix!r} not unique in header {hdr}")
        return hits[0]

    col = {name: find(name) for name in ("Borrower", "Economic sector of borrower", "Equivalent Amount in USD",
                                         "Purpose", "Maturity", "Lender Category")}  # fmt: skip
    inst_col = next((i for i, h in enumerate(hdr) if h in ("ECB/ FCCB", "RDB")), None)
    if inst_col is None:
        raise ValueError(f"ECB {month} {kind}: no instrument column in header {hdr}")
    serial_col = inst_col - 1 if inst_col >= 1 else None  # some RDB tables print no serial-number column
    route = None
    loans, totals = [], {}
    seq = 0
    for r in g.rows:
        if "AUTOMATIC ROUTE" in r[0]:
            route = "automatic"
            continue
        if "APPROVAL ROUTE" in r[0]:
            route = "approval"
            continue
        if r is hdr or "Borrower" in r:
            continue
        is_loan = (
            re.fullmatch(r"\d+", r[serial_col]) is not None
            if serial_col is not None
            else r[inst_col].lower() in ("ecb", "fccb", "rdb")
        )
        if is_loan and r[col["Borrower"]].upper() == "NIL":
            continue  # a numbered 'NIL' row (e.g. RDB, March 2024): no registrations
        if is_loan:
            seq += 1
            if route is None:
                raise ValueError(f"ECB {month}: loan row before a route heading")
            inst = r[inst_col].lower()
            if inst not in ("ecb", "fccb", "rdb"):
                raise ValueError(f"ECB {month}: instrument {r[inst_col]!r}")
            v = num(r[col["Equivalent Amount in USD"]])
            if v is None:
                raise ValueError(f"ECB {month}: loan row {r} without an amount")
            loans.append({"serial": int(r[serial_col]) if serial_col is not None else seq, "route": route, "instrument": inst, "usd": v,
                          "borrower": r[col["Borrower"]], "sector": r[col["Economic sector of borrower"]],
                          "purpose": r[col["Purpose"]], "maturity": r[col["Maturity"]],
                          "lender": r[col["Lender Category"]]})  # fmt: skip
            continue
        lab = next((c for c in r if re.match(r"(grand\s+)?total\b", c.lower())), None)
        if lab:
            key = lab.lower().replace("(", "").replace(")", "").replace("total", "").strip()
            rt = next((v for k, v in _TOTAL_ROUTE if key == k), None)
            if rt is None:
                raise ValueError(f"ECB {month}: unknown total row {lab!r}")
            v = num(r[col["Equivalent Amount in USD"]])
            if v is not None:
                if rt in totals:
                    raise ValueError(f"ECB {month} {kind}: two total rows for route {rt!r}")
                totals[rt] = v
    return loans, totals


def dataset_ecb(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    for month in ECB_IDS:
        raw = ctx.raw(SRC_ECB, f"ecb_{month}.html")
        y, m = int(month[:4]), int(month[5:])
        label = f"{MONTHS[m - 1]} {y}"
        grids = leaf_tables(raw.path)
        g_ecb = find_grid(grids, "Data on ECB/FCCB for the month of")
        g_rdb = find_grid(grids, "Data on RDB for the month of")
        for g in (g_ecb, g_rdb):
            if not g.title.endswith(label):
                raise ValueError(f"ecb_{month}.html: heading {g.title!r} is not for {label}")
        vintage = raw.retrieved_at[:10]
        for g, kind in ((g_ecb, "ecb_fccb"), (g_rdb, "rdb")):
            loans, totals = _ecb_table(g, month, kind)
            table = f"Data on {'ECB/FCCB' if kind == 'ecb_fccb' else 'RDB'} for the month of {label}"
            for ln in loans:
                other = {
                    "lender": slug(ln["lender"]) if ln["lender"] else "not_stated",
                    "maturity": slug(ln["maturity"]) if ln["maturity"] else "not_stated",
                    "purpose": slug(ln["purpose"]) if ln["purpose"] else "not_stated",
                    "route": ln["route"],
                }
                rows.append(
                    _row(
                        SRC_ECB,
                        table,
                        vintage,
                        _block=kind,
                        series_id=f"ecb.{month}.{kind}.{ln['route']}.{ln['serial']:03d}",
                        item_code="ecb_registration",
                        item_label=clean_label(ln["borrower"]),
                        industry=slug(ln["sector"]) if ln["sector"] else None,
                        instrument=ln["instrument"],
                        side="liabilities",
                        dim_other=";".join(f"{k}={v}" for k, v in sorted(other.items())),
                        stock_flow="flow",
                        period=month,
                        period_type="month",
                        value=ln["usd"] / 1e6,
                        unit="USD_million",
                        estimate_stage="n.a.",
                    )
                )
            for rt, v in totals.items():
                rows.append(
                    _row(
                        SRC_ECB,
                        table,
                        vintage,
                        _block=kind,
                        series_id=f"ecb.total.{kind}.{rt}",
                        item_code="ecb_registrations_total",
                        item_label=f"Total ({'Automatic Route+Approval Route' if rt == 'all' else rt.title() + ' Route'})",
                        instrument=kind,
                        side="liabilities",
                        dim_other=f"route={rt}",
                        stock_flow="flow",
                        period=month,
                        period_type="month",
                        value=v / 1e6,
                        unit="USD_million",
                        estimate_stage="n.a.",
                    )
                )
        mine = [r for r in rows if r["period"] == month and "prov_id" not in r]
        for kind in ("ecb_fccb", "rdb"):
            blk = [r for r in mine if r["_block"] == kind]
            if not blk:
                continue
            pid = ctx.prov(
                raw=raw,
                table_id=blk[0]["table_id"],
                locator=f"HTML page ECBUserView.aspx?Id={ECB_IDS[month]}: table '{blk[0]['table_id']}', one row per "
                "registration (serial number, borrower, sector, 'Equivalent Amount in USD', purpose, maturity, lender) "
                "under I Automatic Route and II Approval Route, plus the printed route totals",
                unit_as_published="US$ (Equivalent Amount in USD)",
                conversion="US$ -> US$ million: x 1e-6",
                price_basis="current",
                vintage=vintage,
                release=f"RBI, Data on ECB/FCCB/RDB for the month of {label} (www.rbi.org.in ECB data releases)",
                notes="The page prints no release date; vintage is the date the page was retrieved (raw pin). "
                "Registrations (loan agreements given a loan registration number), not disbursements.",
            )
            for r in blk:
                r["prov_id"] = pid
    for r in rows:
        r.pop("_block")
    return Dataset(
        f"{UNIT}_ecb_monthly_2324",
        pl.DataFrame(rows, infer_schema_length=None),
        "ECB/FCCB/RDB registrations Apr 2023-Mar 2024, loan level (US$ mn) with borrower sector, plus route totals",
    )


# ---------------------------------------------------------------------------------------------
# FLA census 2024-25 round
# ---------------------------------------------------------------------------------------------

FLA_COUNTRY = {
    "United States of America": "USA", "Singapore": "SGP", "Mauritius": "MUS", "United Kingdom": "GBR",
    "Netherlands": "NLD", "Japan": "JPN", "Switzerland": "CHE", "Germany": "DEU", "France": "FRA",
    "South Korea": "KOR", "United Arab Emirates": "ARE", "China": "CHN", "Jersey": "JEY", "Bermuda": "BMU",
}  # fmt: skip
# FLA census rounds: raw name -> (end-March year of the single-date tables 2B and 8, page, release).
# Both rounds print end-March of the previous year too (tables 3A-6), so end-March 2024 appears in two
# vintages: as first published (2023-24 round) and revised (2024-25 round). Series ids are the same.
FLA_ROUNDS = {
    "fla_census_2024_25.html": (2025, "PublicationsView.aspx?id=23438",
                                "RBI, Census on Foreign Liabilities and Assets of Indian Direct Investment Entities, 2024-25 (29 Oct 2025)"),
    "fla_census_2023_24.html": (2024, f"BS_PressReleaseDisplay.aspx?prid={FLA_2324_PRID}",
                                "RBI press release, Census on Foreign Liabilities and Assets of Indian Direct Investment Entities for 2023-24 (11 Oct 2024)"),
}  # fmt: skip
# Table 8 activity names that changed wording between rounds -> the 2024-25 round's slug
FLA_ACTIVITY_ALIAS = {"other_services_activities": "other_service_activities"}
_EM = "-03-31"


def _fla_years(row: list[str], cols: list[int]) -> dict[int, str]:
    out = {}
    for c in cols:
        if not re.fullmatch(r"\d{4}", row[c]):
            raise ValueError(f"FLA: year header {row[c]!r}")
        out[c] = row[c] + _EM
    return out


def dataset_fla(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    for name, (end_year, page, release) in FLA_ROUNDS.items():
        rows += _fla_round(ctx, name, end_year, page, release)
    return Dataset(
        f"{UNIT}_fla_census",
        pl.DataFrame(rows, infer_schema_length=None),
        "FLA census 2023-24 and 2024-25 rounds: inward/outward DI and other investment, by listing, country, activity, "
        "FC/NFC (end-March 2023/2024/2025)",
    )


def _fla_round(ctx: BuildContext, name: str, end_year: int, page: str, release: str) -> list[dict[str, Any]]:
    raw = ctx.raw(SRC_FLA, name)
    vintage = page_date(raw.path)
    stage = "Provisional" if "provisional" in page_text(raw.path).lower() else "n.a."
    grids = leaf_tables(raw.path)
    rows: list[dict[str, Any]] = []
    end = f"{end_year}{_EM}"

    def add(table, series, item, label, value, unit, period, **dims):
        if value is None:
            return
        rows.append(
            _row(SRC_FLA, table, vintage, series_id=series, item_code=item, item_label=clean_label(label),
                 stock_flow="stock" if unit != "percent" else "n/a", period=period, period_type="date",
                 value=value, unit=unit, estimate_stage=stage, **dims)  # fmt: skip
        )

    # Table 2B: foreign equity participation, financial vs non-financial (face value, end-March of the round)
    g = find_grid(grids, "Table 2B:")
    body = g.rows[g.rows.index(next(r for r in g.rows if is_colnum_row(r))) + 1 :]
    if [r[0] for r in body] != ["Financial", "Non-Financial", "Total"]:
        raise ValueError(f"FLA 2B rows {[r[0] for r in body]}")
    if f"face value, end-March {end_year}" not in g.rows[1][0]:
        raise ValueError(f"FLA 2B caption {g.rows[1][0]!r}")
    for r in body:
        inst = {"Financial": "fc", "Non-Financial": "nfc", "Total": "total"}[r[0]]
        t = "Table 2B"
        add(t, f"fla.t2b.{inst}.entities", "fla_entities", f"{r[0]}: No of Entities", num(r[1]), "count", end, institution=inst)
        add(t, f"fla.t2b.{inst}.puc", "fla_paid_up_capital_face", f"{r[0]}: Paid Up Capital (PUC)", num(r[2]), "INR_crore", end, institution=inst)
        add(t, f"fla.t2b.{inst}.equity", "fla_total_equity_face", f"{r[0]}: Total Equity (PUC excluding Non-Participating Preference Share)", num(r[3]), "INR_crore", end, institution=inst)
        add(t, f"fla.t2b.{inst}.fdi_equity", "fla_fdi_equity_face", f"{r[0]}: Equity exclusively under FDI scheme", num(r[4]), "INR_crore", end, institution=inst)
        add(t, f"fla.t2b.{inst}.fdi_share", "fla_fdi_share_of_equity", f"{r[0]}: % share of FDI in Total Equity", num(r[5]), "percent", end, institution=inst)

    # Table 3A: inward DI, listed vs unlisted (market value), end-March 2024 and 2025
    g = find_grid(grids, "Table 3A:")
    k = next(i for i, r in enumerate(g.rows) if is_colnum_row(r))
    grp, yrs = g.rows[k - 2], g.rows[k - 1]
    for r in g.rows[k + 1 :]:
        item = {"Equity": "equity", "Debt": "debt", "Total": "total"}[r[0]]
        for c in range(1, 7):
            cat = {"Listed Entities": "listed", "Unlisted Entities": "unlisted", "Total": "total"}[grp[c]]
            per = yrs[c] + _EM
            add("Table 3A", f"fla.t3a.inward.{cat}.{item}", f"fla_inward_di_{item}", f"Inward direct investment, {grp[c]}: {r[0]}",
                num(r[c]), "INR_crore", per, side="liabilities", dim_other=f"listing={cat}")  # fmt: skip

    # Tables 3B and 4: inward/outward DI and other investment, Rs crore and US$ million
    for tab, key, items in (
        ("Table 3B", "Table 3B:", {"Equity": "equity", "Debt": "debt", "Total": "total"}),
        ("Table 4", "Table 4:", {"Trade Credits": "trade_credit", "Loans": "loans", "Currency & Deposits": "currency_deposits",
                                  "Other receivable and payable accounts": "other_accounts", "Total": "total"}),
    ):  # fmt: skip
        g = find_grid(grids, key)
        k = next(i for i, r in enumerate(g.rows) if is_colnum_row(r))
        grp, yrs, uns = g.rows[k - 3], g.rows[k - 2], g.rows[k - 1]
        body = g.rows[k + 1 :]
        body = [r for r in body if not r[0].startswith("Note")]
        # the 2023-24 round prints 'Currency and Deposits' where 2024-25 prints 'Currency & Deposits'
        if [r[0].replace(" and D", " & D") for r in body] != list(items):
            raise ValueError(f"FLA {tab} rows {[r[0] for r in body]}")
        for r in body:
            key = r[0].replace(" and D", " & D")
            for c in range(1, 9):
                side = {"Inward": "liabilities", "Outward": "assets", "Outstanding liabilities with unrelated party": "liabilities",
                        "Outstanding assets with unrelated party": "assets"}[grp[c]]  # fmt: skip
                unit = "INR_crore" if "crore" in uns[c] else "USD_million" if "million" in uns[c] else None
                if unit is None:
                    raise ValueError(f"FLA {tab}: unit {uns[c]!r}")
                t = tab.lower().replace("table ", "t")
                what = "di" if tab == "Table 3B" else "other_investment"
                add(tab, f"fla.{t}.{side}.{items[key]}.{'inr' if unit == 'INR_crore' else 'usd'}",
                    f"fla_{what}_{items[key]}", f"{grp[c]}: {r[0]}", num(r[c]), unit, yrs[c] + _EM,
                    side=side, instrument=items[key])  # fmt: skip

    # Tables 5 and 6: country-wise inward / outward DI (market value)
    for tab, key, side in (("Table 5", "Table 5:", "liabilities"), ("Table 6", "Table 6:", "assets")):
        g = find_grid(grids, key)
        k = next(i for i, r in enumerate(g.rows) if is_colnum_row(r))
        grp, yrs = g.rows[k - 2], g.rows[k - 1]
        for r in g.rows[k + 1 :]:
            if r[0] in ("Other Countries", "All Countries"):
                partner, other = None, f"partner={slug(r[0])}"
            else:
                partner, other = FLA_COUNTRY[r[0]], None
            code = (partner or slug(r[0])).lower()
            for c in range(1, 7):
                inst = {"Equity": "equity", "Debt": "debt", "Total FDI": "total", "Total ODI": "total"}[grp[c]]
                add(tab, f"fla.{tab[-1]}.{side}.{code}.{inst}", f"fla_di_by_country_{inst}", f"{r[0]}: {grp[c]}", num(r[c]),
                    "INR_crore", yrs[c] + _EM, side=side, instrument=inst, geography=partner, dim_other=other)  # fmt: skip

    # Table 8: activity-wise inward FDI (market value, end-March of the round)
    g = find_grid(grids, "Table 8:")
    k = next(i for i, r in enumerate(g.rows) if is_colnum_row(r))
    hdr = g.rows[k - 1]
    if hdr[1:5] != ["No. of entities", "Equity", "Debt", "Total FDI"]:
        raise ValueError(f"FLA T8 header {hdr}")
    section = None
    for r in g.rows[k + 1 :]:
        m = re.match(r"^([A-G])\.\s+(.*)$", r[0])
        if m:
            section, level, name = m.group(1).lower(), "section", m.group(2)
        elif r[0] == "Total":
            section, level, name = None, "total", "Total"
        else:
            if section not in ("c", "g"):
                raise ValueError(f"FLA T8: sub-activity {r[0]!r} outside C/G")
            level, name = "subsection", re.sub(r"^\d+\.\s*", "", r[0])  # 2023-24 numbers the services rows '1.'..'7.'
        ind = "total" if level == "total" else f"{section}.{FLA_ACTIVITY_ALIAS.get(slug(name), slug(name))}" if level == "subsection" else f"{section}_{slug(name)}"
        other = f"level={level}" + (f";section={section}" if level == "subsection" else "")
        for c, (item, unit) in {1: ("entities", "count"), 2: ("equity", "INR_crore"), 3: ("debt", "INR_crore"), 4: ("total", "INR_crore")}.items():
            add("Table 8", f"fla.t8.{ind}.{item}", f"fla_inward_fdi_by_activity_{item}", f"{r[0]}: {hdr[c]}", num(r[c]),
                unit, end, side="liabilities", industry=ind, dim_other=other)  # fmt: skip

    def caption(unit):
        return {"INR_crore": ("Rs crore", "none"), "USD_million": ("US$ million", "none"),
                "count": ("number of entities", "none"), "percent": ("per cent", "none")}[unit]  # fmt: skip

    def locator(table, unit, rs):
        return (f"HTML page {page}, {table} ({unit} cells); rows and columns matched by label; "
                f"periods {sorted({r['period'] for r in rs})}")  # fmt: skip

    _prov_blocks(ctx, rows, raw, release, locator, caption)
    return rows


# ---------------------------------------------------------------------------------------------
# Remittances survey, 6th round
# ---------------------------------------------------------------------------------------------

REM_COUNTRY = {
    "United States": "USA", "United Arab Emirates": "ARE", "United Kingdom": "GBR", "Saudi Arabia": "SAU",
    "Singapore": "SGP", "Kuwait": "KWT", "Qatar": "QAT", "Canada": "CAN", "Oman": "OMN", "Australia": "AUS",
    "Bahrain": "BHR", "Hong Kong": "HKG", "Germany": "DEU", "Belgium": "BEL", "Malaysia": "MYS",
    "New Zealand": "NZL", "Ireland": "IRL", "Netherlands": "NLD", "Japan": "JPN", "Switzerland": "CHE",
    "France": "FRA", "Italy": "ITA", "Indonesia": "IDN", "Thailand": "THA", "South Africa": "ZAF", "Spain": "ESP",
}  # fmt: skip
# Table 2 destination names are coded with the project-wide map in pipeline/core/geo.py
# (DECISIONS D1-9); this unit keeps no State code list of its own. Printed spellings that geo does
# not recognise are respelled first: 'Delhi NCT' (word order) and 'Lakshwadeep' (misspelt in the
# article). Everything else is passed to geo.state_code as printed, which raises on an unknown name.
REM_STATE_SPELLING = {"Delhi NCT": "NCT of Delhi", "Lakshwadeep": "Lakshadweep"}
_STATE_CODE = re.compile(r"\bIN-[A-Z]{2}\b")


def rem_state_code(printed: str, period: str, period_type: str = "fy") -> str:
    """Geography code for a destination State/UT printed in the survey round `period`.

    The current code comes from geo.state_code. If the period falls before a reorganisation that
    changed that territory, the row describes the older territory and gets its historical project
    code from geo.HISTORICAL, but only when the older territory carried the same name (Jammu and
    Kashmir in 2016-17 is the State incl. Ladakh, IN-XJK; to 30 Oct 2019). A period that straddles
    the change, or a successor printed for a time before it existed as a separate unit (Ladakh or
    DNH&DD before their creation), raises: that figure has no single code.
    """
    code = geo.state_code(REM_STATE_SPELLING.get(printed, printed))
    start, end = period_start(period, period_type), period_end(period, period_type)
    for hist, (hname, last, replaced_by) in sorted(geo.HISTORICAL.items()):
        if code not in _STATE_CODE.findall(replaced_by) or start > dt.date.fromisoformat(last):
            continue
        if end > dt.date.fromisoformat(last) or not hname.startswith(geo.state_name(code) + " ("):
            raise ValueError(f"remittance survey: {printed!r} ({code}) in {period} has no single code: "
                             f"{hist} {hname} existed to {last}")  # fmt: skip
        return hist
    return code


def dataset_remittance_survey(ctx: BuildContext) -> Dataset:
    raw = ctx.raw(SRC_REM, "remittances_survey_r6.html")
    vintage = page_date(raw.path)
    grids = leaf_tables(raw.path)
    rows: list[dict[str, Any]] = []
    for key, table, head, code_of, kind in (
        ("Table 1: Source Country-wise Share", "Table 1", "Source Country", lambda n, _p: REM_COUNTRY[n], "source_country"),
        ("Table 2: State-wise/UT-wise Share", "Table 2", "Destination State", rem_state_code, "destination_state"),
    ):
        g = find_grid(grids, key)
        hdr = g.rows[1]
        if hdr[0] != head or [normalize_fy(h) for h in hdr[1:]] != ["2016-17", "2020-21", "2023-24"]:
            raise ValueError(f"remittance {table}: header {hdr}")
        body = [r for r in g.rows[2:] if not r[0].startswith("Note")]
        for r in body:
            for c in (1, 2, 3):
                v = num(r[c])
                if v is None:
                    continue
                period = normalize_fy(hdr[c])
                geo_code = None if r[0] == "Others" else code_of(r[0], period)
                code = "others" if geo_code is None else geo_code.lower()
                rows.append(
                    _row(
                        SRC_REM, table, vintage,
                        series_id=f"remit.{kind}.{code}",
                        item_code=f"inward_remittance_share_by_{kind}",
                        item_label=clean_label(f"{r[0]}: share in India's inward remittances (banks)"),
                        geography=geo_code,
                        dim_other="partner=others" if geo_code is None else None,
                        side="credit",
                        stock_flow="n/a",
                        period=period,
                        period_type="fy",
                        value=v,
                        unit="percent",
                        estimate_stage="n.a.",
                    )  # fmt: skip
                )

    def locator(table, unit, rs):
        return (f"HTML Bulletin article BS_ViewBulletin.aspx?Id=23260, {table}; rows matched by country/State name, "
                "columns 2016-17, 2020-21, 2023-24 (survey rounds)")  # fmt: skip

    _prov_blocks(ctx, rows, raw, "RBI Bulletin, March 2025: 'Changing Dynamics of India's Remittances - Insights from the Sixth Round of India's Remittances Survey' (19 Mar 2025)", locator, lambda u: ("per cent", "none"))
    return Dataset(
        f"{UNIT}_remittance_survey",
        pl.DataFrame(rows, infer_schema_length=None),
        "RBI remittances survey: source-country and destination-State shares of inward remittances (banks), 2016-17/2020-21/2023-24",
    )


# ---------------------------------------------------------------------------------------------
# Software / ITES exports survey
# ---------------------------------------------------------------------------------------------

ITES_TABLES = {2: "activity", 3: "ites_industry", 4: "organisation", 5: "destination", 6: "invoice_currency",
               7: "type_of_service", 8: "mode"}  # fmt: skip
ITES_GEO = {"United States of America": "USA", "Canada": "CAN", "United Kingdom": "GBR"}
_MARK = re.compile(r"^(\(?[ivxlcdm]+\)|[A-Z]\.)\s*")


def dataset_ites(ctx: BuildContext) -> Dataset:
    rows: list[dict[str, Any]] = []
    for rnd in ITES_PRIDS:
        raw = ctx.raw(SRC_ITES, ites_name(rnd))
        vintage = page_date(raw.path)
        grids = leaf_tables(raw.path)
        for n, dim in ITES_TABLES.items():
            g = find_grid(grids, f"Table {n}:")
            yrs, uns = g.rows[1], g.rows[2]
            k = next(i for i, r in enumerate(g.rows) if is_colnum_row(r))
            if k != 3:
                raise ValueError(f"ITES {rnd} Table {n}: layout")
            for r in g.rows[k + 1 :]:
                if r[0].lower().startswith("of which") or r[0].startswith("#") or r[0].startswith("Note"):
                    continue
                label = r[0]
                code = slug(_MARK.sub("", label.replace("(A+B)", "")))
                partner = ITES_GEO.get(label) if n == 5 else None
                for c in range(1, 7):
                    u = uns[c]
                    unit, scale, tag = (
                        ("INR_crore", 1.0, "inr") if "crore" in u else ("USD_million", 1000.0, "usd") if "billion" in u
                        else ("percent", 1.0, "share") if "Share" in u else (None, None, None)
                    )  # fmt: skip
                    if unit is None:
                        raise ValueError(f"ITES {rnd} Table {n}: unit header {u!r}")
                    v = num(r[c])
                    if v is None:
                        continue
                    rows.append(
                        _row(
                            SRC_ITES, f"Table {n}", vintage,
                            _round=rnd,
                            series_id=f"ites.t{n}.{code}.{tag}",
                            item_code=f"software_exports_by_{dim}",
                            item_label=clean_label(label),
                            geography=partner,
                            dim_other=f"{dim}={code}",
                            side="credit",
                            stock_flow="flow" if unit != "percent" else "n/a",
                            period=normalize_fy(yrs[c]),
                            period_type="fy",
                            value=v * scale,
                            unit=unit,
                            estimate_stage="n.a.",
                        )  # fmt: skip
                    )
        prid = ITES_PRIDS[rnd]

        def caption(unit):
            return {"INR_crore": ("Rs crore", "none"), "USD_million": ("US$ billion", "US$ billion -> US$ million: x 1000"),
                    "percent": ("per cent (share)", "none")}[unit]  # fmt: skip

        def locator(table, unit, rs, prid=prid):
            return (f"HTML press release BS_PressReleaseDisplay.aspx?prid={prid}, {table}, {unit} columns; rows matched by "
                    f"label; years {sorted({r['period'] for r in rs})}")  # fmt: skip

        mine = [r for r in rows if r.get("_round") == rnd]
        _prov_blocks(ctx, mine, raw, f"RBI press release: Survey on Computer Software and ITES Exports: {rnd} ({vintage})", locator, caption)
    for r in rows:
        r.pop("_round")
    return Dataset(
        f"{UNIT}_ites_survey",
        pl.DataFrame(rows, infer_schema_length=None),
        "Software/ITES exports survey 2023-24..2025-26 by activity, destination, currency, organisation, mode (Rs cr, US$ mn, %)",
    )


# ---------------------------------------------------------------------------------------------
# LRS outward remittances, with derived Rs crore for the FY totals
# ---------------------------------------------------------------------------------------------

_LRS_NUM = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")
_MON = {m[:3]: i for i, m in enumerate(MONTHS, 1)}


def dataset_lrs(ctx: BuildContext, fx: pl.DataFrame) -> Dataset:
    rows: list[dict[str, Any]] = []
    for issue in LRS_IDS:
        raw = ctx.raw(SRC_LRS, f"lrs_bulletin_{issue}.html")
        vintage = page_date(raw.path)
        if not page_text(raw.path).count("Liberalised Remittance Scheme"):
            raise ValueError(f"LRS {issue}: not the LRS table page")
        g = next(g for g in leaf_tables(raw.path) if g.title == "(US $ Million)")
        yr, mo = g.rows[1], g.rows[2]
        if yr[0] != "Item" or mo[1] != yr[1]:
            raise ValueError(f"LRS {issue}: header {yr} / {mo}")
        cols: dict[int, tuple[str, str]] = {1: (normalize_fy(yr[1]), "fy")}
        for c in range(2, len(yr)):
            cols[c] = (f"{int(yr[c])}-{_MON[mo[c].rstrip('.')]:02d}", "month")
        body = [r for r in g.rows[3:] if _LRS_NUM.match(r[0])]
        if not body or not body[0][0].startswith("1 Outward Remittances under the LRS"):
            raise ValueError(f"LRS {issue}: first row {body[:1]}")
        # First month of the printed financial year (April of its first calendar year). An item that is blank
        # in that month was introduced part-way through the year (the June 2026 table's travel sub-items
        # 1.6.1-1.6.5 start in March 2026): its financial-year cell covers only the printed months, so it is
        # not stored as an FY value (the months are kept as monthly rows).
        fy_start = f"{cols[1][0][:4]}-04"
        c_start = next((c for c, (per, _) in cols.items() if per == fy_start), None)
        if c_start is None:
            raise ValueError(f"LRS {issue}: no {fy_start} column to check FY coverage")
        for r in body:
            m = _LRS_NUM.match(r[0])
            code = "lrs_" + m.group(1).replace(".", "_")
            partial_year = num(r[c_start]) is None
            for c, (per, pt) in cols.items():
                v = num(r[c])
                if v is None or (pt == "fy" and partial_year):
                    continue
                rows.append(
                    _row(
                        SRC_LRS, "Outward Remittances under the Liberalised Remittance Scheme (LRS) for Resident Individuals", vintage,
                        _issue=issue,
                        series_id=f"lrs.usd.{'annual' if pt == 'fy' else 'monthly'}.{code}.current",
                        item_code=code,
                        item_label=clean_label(m.group(2)),
                        side="debit",
                        stock_flow="flow",
                        period=per,
                        period_type=pt,
                        value=v,
                        unit="USD_million",
                        estimate_stage="n.a.",
                    )  # fmt: skip
                )
        tno = {"2024-06": "35", "2025-06": "35", "2026-06": "36"}[issue]
        pid = ctx.prov(
            raw=raw,
            table_id=f"Bulletin Current Statistics No. {tno}",
            locator=f"HTML page BS_ViewBulletin.aspx?Id={LRS_IDS[issue]} (RBI Bulletin {issue}, table No. {tno}); rows "
            "matched by item number; columns: financial year total and four months",
            unit_as_published="US$ million",
            price_basis="current",
            vintage=vintage,
            release=f"RBI Bulletin, {MONTHS[int(issue[5:]) - 1]} {issue[:4]}, Current Statistics No. {tno} ({vintage})",
        )
        for r in rows:
            if r.get("_issue") == issue:
                r["prov_id"] = pid
                r["table_id"] = f"Bulletin Current Statistics No. {tno}"
    # Derived: FY totals in Rs crore with the FY-average rate (HBS T133).
    rates = fx.filter(pl.col("series_id") == "t133.usd_fy_average").select("period", "value", "prov_id", "vintage")
    annual = [r for r in rows if r["period_type"] == "fy"]
    derived = []
    for r in annual:
        rate = rates.filter(pl.col("period") == r["period"])
        conv = usd_million_to_inr_crore(pl.DataFrame([{"period": r["period"], "value": r["value"]}]), rate.drop("vintage"))
        vint = max(r["vintage"], rate["vintage"][0])
        pid = ctx.prov(
            raw=None,
            source_id=SRC_LRS,
            table_id=r["table_id"],
            locator=f"derived from {r['series_id']} ({r['period']}, vintage {r['vintage']})",
            unit_as_published="US$ million",
            price_basis="current",
            vintage=vint,
            release="derived (this unit)",
            status="derived",
            method="Rs crore = US$ million x (Rs per US$, financial-year average, RBI HBS 2025-26 Table 133) / 10",
            inputs=[r["prov_id"], conv["fx_prov_id"][0]],
        )
        derived.append(
            {**r, "series_id": r["series_id"].replace("lrs.usd.", "lrs.inr."), "value": conv["value"][0],
             "unit": "INR_crore", "vintage": vint, "status": "derived", "prov_id": pid}  # fmt: skip
        )
    rows += derived
    for r in rows:
        r.pop("_issue", None)
    return Dataset(
        f"{UNIT}_lrs_outward",
        pl.DataFrame(rows, infer_schema_length=None),
        "LRS outward remittances by purpose (US$ mn; FY 2023-24..2025-26 and months), with derived Rs crore FY totals",
    )


def build_all(ctx: BuildContext, fx: pl.DataFrame) -> list[Dataset]:
    return [dataset_ecb(ctx), dataset_fla(ctx), dataset_remittance_survey(ctx), dataset_ites(ctx), dataset_lrs(ctx, fx)]
