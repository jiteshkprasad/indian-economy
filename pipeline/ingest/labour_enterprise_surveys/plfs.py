"""PLFS Annual Report 2023-24 (July 2023-June 2024; NSO, released 23 Sep 2024): published tables.

Survey years are agricultural years (July-June), not fiscal years. Rows for a survey year carry the
`sy` period '2023-07/2024-06' (PLFS 2023-24); the parsers tag them survey_year=jul_jun and
`_pdf.frame()` converts the tag into the period. Phase 2 takes only shares/ratios from them and
applies them to FY totals. The quarterly earnings statements are true calendar quarters and use
`fq` periods (July-September 2023 = Q2 2023-24).
"""

from __future__ import annotations

import re
from typing import Any

from pipeline.core.unit import BuildContext, Dataset
from pipeline.core.units import fq

from ._pdf import NUM, Pdf, ShapeError, expect_text, frame, numbers, split_label_numbers

SRC = "mospi_plfs_annual"
RAW = "plfs_ar_2023_24.pdf"
VINTAGE = "2024-09-23"  # release date on the title page, PDF p.2 ('23rd September 2024')
RELEASE = "Annual Report, Periodic Labour Force Survey (PLFS), July 2023-June 2024 (NSO, MoSPI; 23 Sep 2024)"

SECTORS = ("rural", "urban", "total")  # household_group codes; 'total' = rural+urban
SEXES = ("male", "female", "person")
COLS9 = [(s, x) for s in SECTORS for x in SEXES]  # the 9 data columns (2)-(10) of most PLFS tables


# Internal marker on every row whose period is a PLFS survey year ('2023-24' = July 2023-June
# 2024, not the fiscal year): _pdf.frame() turns it into the `sy` period '2023-07/2024-06'.
SURVEY_YEAR = "jul_jun"


def _dim(**kw: str) -> str:
    return ";".join(f"{k}={kw[k]}" for k in sorted(kw))


def _row(
    *,
    sid: str,
    table: str,
    item: str,
    label: str,
    sector: str,
    period: str,
    ptype: str,
    value: float,
    unit: str,
    prov: str,
    dims: dict[str, str],
    industry: str | None = None,
    stock_flow: str = "n/a",
    price_basis: str = "n/a",
) -> dict[str, Any]:
    return {
        "series_id": sid,
        "source_id": SRC,
        "table_id": table,
        "item_code": item,
        "item_label": label,
        "industry": industry,
        "geography": "IN",
        "household_group": sector,
        "dim_other": _dim(**dims),
        "stock_flow": stock_flow,
        "period": period,
        "period_type": ptype,
        "value": value,
        "unit": unit,
        "price_basis": price_basis,
        "vintage": VINTAGE,
        "estimate_stage": "n.a.",
        "status": "official",
        "prov_id": prov,
    }


_YEAR_HDR = re.compile(r"^PLFS \((20\d\d-\d\d)\)$")


# ---------------------------------------------------------------------------------------------
# Highlights tables D.1-3 (usual status) and E.1-3 (CWS): LFPR, WPR, UR 2017-18..2023-24
# ---------------------------------------------------------------------------------------------

LFS_TABLES = (
    # (printed title start, near page, indicator, activity status)
    ("Table 1: Labour force participation rates (in per cent) in usual status (ps+ss)", 22, "lfpr", "ps_ss"),
    ("Table2: WPR (in per cent) in usual status (ps+ss)", 23, "wpr", "ps_ss"),
    ("Table3: Unemployment Rate (in per cent) in usual status (ps+ss)", 24, "ur", "ps_ss"),
    ("Table 1: Labour force participation rates (in per cent) current weekly status", 25, "lfpr", "cws"),
    ("Table 2: Worker Population Ratio (in per cent) current weekly status", 26, "wpr", "cws"),
    ("Table 3: Unemployment Rate (in per cent) current weekly status", 27, "ur", "cws"),
)
LFS_LABEL = {"lfpr": "Labour force participation rate", "wpr": "Worker population ratio", "ur": "Unemployment rate"}
AGES = {"15 years and above": "15plus", "all ages": "all"}
LFS_YEARS = ("2023-24", "2022-23", "2021-22", "2020-21", "2019-20", "2018-19", "2017-18")


def _lfs(ctx: BuildContext, pdf: Pdf, raw: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for title, near, ind, status in LFS_TABLES:
        (page,) = pdf.find_pages(title, near, window=4, count=1)
        expect_text(pdf, page, "rural urban rural+urban")
        pid = ctx.prov(
            raw=raw,
            table_id=f"Highlights {'D' if status == 'ps_ss' else 'E'}, {title.split(':')[0]}",
            locator=f"p.{page} (printed page numbers vi-ix), rows by PLFS year and age group, cols (2)-(10)",
            unit_as_published="per cent",
            price_basis="n/a",
            vintage=VINTAGE,
            release=RELEASE,
            notes="PLFS years are July-June (e.g. 2023-24 = July 2023-June 2024), not fiscal years.",
        )
        lines = pdf.lines(page)
        year = None
        seen: set[tuple[str, str]] = set()
        i = 0
        while i < len(lines):
            ln = lines[i]
            m = _YEAR_HDR.match(ln)
            if m:
                year = m.group(1)
            else:
                for age_lbl, age in AGES.items():
                    if ln.startswith(age_lbl):
                        rest = ln[len(age_lbl) :].strip()
                        if not rest:  # numbers wrapped to the next line
                            i += 1
                            rest = lines[i]
                        if year is None:
                            raise ShapeError(f"PLFS p.{page}: data before a year header")
                        vals = numbers(rest.split(" "), 9, f"PLFS p.{page} {year} {age_lbl}")
                        if (year, age) in seen:
                            raise ShapeError(f"PLFS p.{page}: duplicate row {year} {age_lbl}")
                        seen.add((year, age))
                        for (sec, sex), v in zip(COLS9, vals, strict=True):
                            if v is None:
                                raise ShapeError(f"PLFS p.{page}: blank cell {year} {age_lbl}")
                            rows.append(
                                _row(
                                    sid=f"lfs.{ind}.{status}.{age}.{sec}.{sex}",
                                    table=f"Highlights table ({status})",
                                    item=ind,
                                    label=f"{LFS_LABEL[ind]}, {'usual status (ps+ss)' if status == 'ps_ss' else 'current weekly status'}, age {age_lbl}",
                                    sector=sec,
                                    period=year,
                                    ptype="fy",
                                    value=v,
                                    unit="percent",
                                    prov=pid,
                                    dims={
                                        "activity_status": status,
                                        "age_group": age,
                                        "sex": sex,
                                        "survey_year": SURVEY_YEAR,
                                    },
                                )
                            )
                        break
            i += 1
        want = {(y, a) for y in LFS_YEARS for a in AGES.values()}
        if seen != want:
            raise ShapeError(f"PLFS p.{page}: rows found {sorted(seen)} != expected {sorted(want)}")
    return rows


# ---------------------------------------------------------------------------------------------
# Statement 6: workers (ps+ss) by status in employment, 2021-22..2023-24
# ---------------------------------------------------------------------------------------------

STATUS6 = (
    ("own_account_employer", "own account worker and employer"),
    ("helper", "helper in household enterprise"),
    ("self_employed", "all self employed"),
    ("regular_wage", "regular wage/salary"),
    ("casual_labour", "casual labour"),
    ("all", "all"),
)
SECTOR_HDR = {"rural": "rural", "urban": "urban", "rural +urban": "total", "rural+urban": "total"}


def _statement6(ctx: BuildContext, pdf: Pdf, raw: Any) -> list[dict[str, Any]]:
    (page,) = pdf.find_pages(
        "Statement 6: Percentage distribution of workers in usual status (ps+ss) by status", 42, count=1
    )
    expect_text(pdf, page, "own account helper in all self casual")
    expect_text(pdf, page, "(1) (2) (3) (4) (5) (6) (7)")
    pid = ctx.prov(
        raw=raw,
        table_id="Statement 6",
        locator=f"p.{page} (printed p.13), blocks PLFS (2023-24), (2022-23), (2021-22); rows sector x sex; cols (2)-(7)",
        unit_as_published="per cent",
        price_basis="n/a",
        vintage=VINTAGE,
        release=RELEASE,
        notes="Percentage distribution of workers in usual status (ps+ss); PLFS years are July-June.",
    )
    rows: list[dict[str, Any]] = []
    year = sector = None
    seen = set()
    for ln in pdf.lines(page):
        m = _YEAR_HDR.match(ln)
        if m:
            year, sector = m.group(1), None
            continue
        if ln in SECTOR_HDR:
            sector = SECTOR_HDR[ln]
            continue
        sp = split_label_numbers(ln, 6)
        if sp and sp[0] in SEXES:
            if year is None or sector is None:
                raise ShapeError(f"PLFS Statement 6: row {ln!r} outside a year/sector block")
            sex = sp[0]
            vals = numbers(sp[1], 6, f"Statement 6 {year} {sector} {sex}")
            seen.add((year, sector, sex))
            for (code, lbl), v in zip(STATUS6, vals, strict=True):
                assert v is not None
                rows.append(
                    _row(
                        sid=f"st6.worker_share.{code}.{sector}.{sex}",
                        table="Statement 6",
                        item=f"worker_share_{code}",
                        label=f"Percentage distribution of workers (ps+ss) by status in employment: {lbl}",
                        sector=sector,
                        period=year,
                        ptype="fy",
                        value=v,
                        unit="percent",
                        prov=pid,
                        dims={
                            "activity_status": "ps_ss",
                            "employment_status": code,
                            "sex": sex,
                            "survey_year": SURVEY_YEAR,
                        },
                    )
                )
    want = {(y, s, x) for y in ("2023-24", "2022-23", "2021-22") for s in SECTORS for x in SEXES}
    if seen != want:
        raise ShapeError(f"PLFS Statement 6: missing rows {sorted(want - seen)}")
    return rows


# ---------------------------------------------------------------------------------------------
# Table (20): workers (ps+ss) by status in employment for each industry of work (2023-24)
# ---------------------------------------------------------------------------------------------

# Row groups as printed (NIC-2008 2-digit division ranges); 'total' = all industries.
GROUPS20 = {
    "01-03": "agriculture",
    "05-09": "mining & quarrying",
    "10-33": "manufacturing",
    "35-39": "electricity and water supply",
    "41-43": "construction",
    "05-43": "secondary",
    "45-47": "trade",
    "49-53": "transport",
    "55-56": "accommodation & food services",
    "58-99": "other services",
    "45-99": "tertiary",
    "total": "all industries",
}
_BLOCK_HDR = re.compile(r"^(?:all-India )?(rural|urban|rural\+urban) (male|female|persons?)$")
_SECTOR_OF = {"rural": "rural", "urban": "urban", "rural+urban": "total"}


def _block_of(pdf: Pdf, page: int, where: str) -> tuple[str, str]:
    hdr = [m for m in (_BLOCK_HDR.match(ln) for ln in pdf.lines(page)) if m]
    if len(hdr) != 1:
        raise ShapeError(f"PLFS {where} p.{page}: {len(hdr)} sector/sex block headers")
    sex = hdr[0].group(2)
    return _SECTOR_OF[hdr[0].group(1)], ("person" if sex.startswith("person") else sex)


def _table20(ctx: BuildContext, pdf: Pdf, raw: Any) -> list[dict[str, Any]]:
    title = "Table (20): Percentage distribution of workers in usual status (ps+ss) by broad status in employment for each industry of work"
    pages = pdf.find_pages(title, 151, window=8, count=9)
    # Header words are interleaved in the text layer; column order (own account, helper, all SE,
    # regular, casual, all) was checked by word x-position on pp.147 and 155, and the tests check
    # (2)+(3)=(4) and (4)+(5)+(6)=(7) on every row.
    for p in pages:
        for needle in ("own account", "helper in household", "all self", "regular", "wage/", "casual", "(1) (2) (3) (4) (5) (6) (7)"):
            expect_text(pdf, p, needle)
    pid = ctx.prov(
        raw=raw,
        table_id="Table (20)",
        locator=f"pp.{pages[0]}-{pages[-1]} (printed A-84 to A-92), one page per sector x sex block; rows NIC-2008 division groups (01-03 ... 45-99, total); cols (2)-(7)",
        unit_as_published="per cent",
        price_basis="n/a",
        vintage=VINTAGE,
        release=RELEASE,
        notes="Status shares within each industry group (each row sums to 100). PLFS 2023-24 = July 2023-June 2024. Groups 05-43 (secondary) and 45-99 (tertiary) are published aggregates of the rows above them.",
    )
    pid_n = ctx.prov(
        raw=raw,
        table_id="Table (20)",
        locator=f"pp.{pages[0]}-{pages[-1]}, row 'sample workers' of each block, cols (2)-(7)",
        unit_as_published="number (sample workers)",
        price_basis="n/a",
        vintage=VINTAGE,
        release=RELEASE,
        notes="Unweighted sample counts by status, printed for reference.",
    )
    rows: list[dict[str, Any]] = []
    blocks: set[tuple[str, str]] = set()
    for page in pages:
        sec, sex = _block_of(pdf, page, "Table 20")
        if (sec, sex) in blocks:
            raise ShapeError(f"PLFS Table 20: block {sec} {sex} printed twice")
        blocks.add((sec, sex))
        seen: set[str] = set()
        for ln in pdf.lines(page):
            sp = split_label_numbers(ln, 6)
            if not sp:
                continue
            label = sp[0]
            m = re.match(r"^(\d\d-\d\d)\s*\(", label)
            if m:
                code = m.group(1)
            elif label in ("total", "sample workers"):
                code = label
            else:
                raise ShapeError(f"PLFS Table 20 p.{page}: unmapped row {ln!r}")
            if code != "sample workers" and code not in GROUPS20:
                raise ShapeError(f"PLFS Table 20 p.{page}: unknown industry group {code!r}")
            if code in seen:
                raise ShapeError(f"PLFS Table 20 p.{page}: row {code} printed twice")
            seen.add(code)
            vals = numbers(sp[1], 6, f"Table 20 {sec} {sex} {code}")
            for (st, lbl), v in zip(STATUS6, vals, strict=True):
                if v is None:
                    raise ShapeError(f"PLFS Table 20 p.{page}: blank cell {code} {st}")
                dims = {"activity_status": "ps_ss", "employment_status": st, "sex": sex, "survey_year": SURVEY_YEAR}
                if code == "sample workers":
                    rows.append(
                        _row(
                            sid=f"t20.sample_workers.{st}.{sec}.{sex}",
                            table="Table (20)",
                            item="sample_workers",
                            label=f"Sample workers (usual status ps+ss), status: {lbl}",
                            sector=sec,
                            period="2023-24",
                            ptype="fy",
                            value=v,
                            unit="count",
                            prov=pid_n,
                            industry="nic2008_all",
                            dims=dims,
                        )
                    )
                    continue
                ind = "all" if code == "total" else code
                rows.append(
                    _row(
                        sid=f"t20.worker_share.{st}.{ind}.{sec}.{sex}",
                        table="Table (20)",
                        item=f"worker_share_{st}",
                        label=f"Percentage distribution of workers (ps+ss) by status in employment ({lbl}) within industry group NIC-2008 {code} ({GROUPS20[code]})",
                        sector=sec,
                        period="2023-24",
                        ptype="fy",
                        value=v,
                        unit="percent",
                        prov=pid,
                        industry=f"nic2008_{ind}",
                        dims=dims,
                    )
                )
        if seen != {*GROUPS20, "sample workers"}:
            raise ShapeError(f"PLFS Table 20 p.{page}: rows {sorted(seen)} != expected")
    if blocks != {(s, x) for s in SECTORS for x in SEXES}:
        raise ShapeError(f"PLFS Table 20: blocks {sorted(blocks)}")
    return rows


# ---------------------------------------------------------------------------------------------
# Table (35): non-agricultural workers (ps+ss) by enterprise type; all-India rows only
# ---------------------------------------------------------------------------------------------

ENT35 = (  # columns (2)-(10), in printed order (header words checked by position on PDF p.274)
    ("proprietary_partnership", "proprietary and partnership"),
    ("govt_public_sector", "govt./local body/public sector enterprises"),
    ("autonomous_bodies", "autonomous bodies"),
    ("pvt_public_ltd_company", "public/private limited company"),
    ("cooperative_societies", "cooperative societies"),
    ("trust_nonprofit", "trust/other non profit institutions"),
    ("employer_households", "employer's households"),
    ("others", "others"),
    ("all", "total"),
)


def _table35(ctx: BuildContext, pdf: Pdf, raw: Any) -> list[dict[str, Any]]:
    title = "Table (35): Percentage distribution of usually working (ps+ss) persons engaged in non-agriculture (industry divisions 05-99 of NIC-2008) by enterprise type for each State/ UT"
    pages = pdf.find_pages(title, 278, window=6, count=9)
    for p in pages:
        # header words are interleaved in the text layer; these are its printed lines
        for needle in (
            "proprietary govt./",
            "local body/ public autonomous cooperative trust/ other",
            "limited others total",
            "partnership sector enterprises bodies societies non profit inst households workers",
            "(1) (2) (3) (4) (5) (6) (7) (8) (9) (10) (11)",
        ):
            expect_text(pdf, p, needle)
    pid = ctx.prov(
        raw=raw,
        table_id="Table (35)",
        locator=f"pp.{pages[0]}-{pages[-1]} (printed A-211 to A-219), one page per sector x sex block; row 'all India', cols (2)-(10)",
        unit_as_published="per cent",
        price_basis="n/a",
        vintage=VINTAGE,
        release=RELEASE,
        notes="Workers in non-agriculture (NIC-2008 divisions 05-99), all statuses in employment. PLFS 2023-24 = July 2023-June 2024. State/UT rows are not ingested.",
    )
    pid_n = ctx.prov(
        raw=raw,
        table_id="Table (35)",
        locator=f"pp.{pages[0]}-{pages[-1]}, row 'sample workers' of each block, cols (2)-(10)",
        unit_as_published="number (sample workers)",
        price_basis="n/a",
        vintage=VINTAGE,
        release=RELEASE,
        notes="Unweighted all-India sample counts by enterprise type; col (10) equals col (11) of the 'all India' row (checked).",
    )
    rows: list[dict[str, Any]] = []
    blocks: set[tuple[str, str]] = set()
    for page in pages:
        sec, sex = _block_of(pdf, page, "Table 35")
        if (sec, sex) in blocks:
            raise ShapeError(f"PLFS Table 35: block {sec} {sex} printed twice")
        blocks.add((sec, sex))
        allind = [ln for ln in pdf.lines(page) if ln.startswith("all India ")]
        samp = [ln for ln in pdf.lines(page) if ln.startswith("sample workers ")]
        if len(allind) != 1 or len(samp) != 1:
            raise ShapeError(f"PLFS Table 35 p.{page}: 'all India' x{len(allind)}, 'sample workers' x{len(samp)}")
        shares = numbers(allind[0][len("all India ") :].split(" "), 10, f"Table 35 {sec} {sex} all India")
        stoks = samp[0][len("sample workers ") :].split(" ")
        if stoks[-1] != "x":
            raise ShapeError(f"PLFS Table 35 p.{page}: sample-workers row does not end in 'x'")
        counts = numbers(stoks[:-1], 9, f"Table 35 {sec} {sex} sample workers")
        if counts[-1] != shares[-1]:
            raise ShapeError(f"PLFS Table 35 p.{page}: sample total {counts[-1]} != all-India col (11) {shares[-1]}")
        for (code, lbl), share, n in zip(ENT35, shares[:9], counts, strict=True):
            if share is None or n is None:
                raise ShapeError(f"PLFS Table 35 p.{page}: blank cell {code}")
            dims = {"activity_status": "ps_ss", "enterprise_type": code, "sex": sex, "survey_year": SURVEY_YEAR}
            rows.append(
                _row(
                    sid=f"t35.worker_share.{code}.{sec}.{sex}",
                    table="Table (35)",
                    item="worker_share_enterprise_type",
                    label=f"Percentage distribution of usually working persons (ps+ss) in non-agriculture by enterprise type: {lbl}",
                    sector=sec,
                    period="2023-24",
                    ptype="fy",
                    value=share,
                    unit="percent",
                    prov=pid,
                    industry="nic2008_05-99",
                    dims=dims,
                )
            )
            rows.append(
                _row(
                    sid=f"t35.sample_workers.{code}.{sec}.{sex}",
                    table="Table (35)",
                    item="sample_workers",
                    label=f"Sample workers (ps+ss) in non-agriculture, enterprise type: {lbl}",
                    sector=sec,
                    period="2023-24",
                    ptype="fy",
                    value=n,
                    unit="count",
                    prov=pid_n,
                    industry="nic2008_05-99",
                    dims=dims,
                )
            )
    if blocks != {(s, x) for s in SECTORS for x in SEXES}:
        raise ShapeError(f"PLFS Table 35: blocks {sorted(blocks)}")
    return rows


# ---------------------------------------------------------------------------------------------
# Statement 7 (broad industry, 3 years) and Table 26 (NIC-2008 detail, 2023-24)
# ---------------------------------------------------------------------------------------------

BROAD7 = (  # (label prefix as printed, lower-case) -> (code, NIC sections)
    ("agriculture", "A"),
    ("mining & quarrying", "B"),
    ("manufacturing", "C"),
    ("electricity, water, etc.", "D-E"),
    ("construction", "F"),
    ("trade, hotel & restaurant", "G_I"),
    ("transport, storage &", "H_J"),
    ("other services", "K-U"),
    ("all", "all"),
)


def _statement7(ctx: BuildContext, pdf: Pdf, raw: Any) -> list[dict[str, Any]]:
    (page,) = pdf.find_pages(
        "Statement 7: Percentage distribution of workers in usual status (ps+ss) by broad industry", 44, count=1
    )
    expect_text(pdf, page, "sections K to U")
    pid = ctx.prov(
        raw=raw,
        table_id="Statement 7",
        locator=f"p.{page} (printed p.15), blocks PLFS (2023-24), (2022-23), (2021-22); rows broad industry; cols (2)-(10)",
        unit_as_published="per cent",
        price_basis="n/a",
        vintage=VINTAGE,
        release=RELEASE,
        notes="Broad industry divisions per Note 1: D-E = sections D & E; G_I = G & I; H_J = H & J; K-U = K to U.",
    )
    rows: list[dict[str, Any]] = []
    year = None
    seen = set()
    for ln in pdf.lines(page):
        m = _YEAR_HDR.match(ln)
        if m:
            year = m.group(1)
            continue
        if ln.lower() == "communications" or ln.lower() == "transport, storage &":
            continue  # wrapped label of the transport row
        sp = split_label_numbers(ln, 9)
        if not sp:
            continue
        label = sp[0].lower()
        if label == "communications":
            label = "transport, storage &"
        hit = [c for p, c in BROAD7 if label == p or (p == "transport, storage &" and label.startswith("transport"))]
        if len(hit) != 1:
            raise ShapeError(f"PLFS Statement 7: unmapped row label {sp[0]!r}")
        code = hit[0]
        if year is None:
            raise ShapeError("PLFS Statement 7: row before a year header")
        vals = numbers(sp[1], 9, f"Statement 7 {year} {code}")
        if (year, code) in seen:
            raise ShapeError(f"PLFS Statement 7: duplicate row {year} {code}")
        seen.add((year, code))
        for (sec, sex), v in zip(COLS9, vals, strict=True):
            assert v is not None
            rows.append(
                _row(
                    sid=f"st7.worker_share.{code.lower()}.{sec}.{sex}",
                    table="Statement 7",
                    item="worker_share_broad_industry",
                    label=f"Percentage distribution of workers (ps+ss) by broad industry division: {LABEL7[code]}",
                    sector=sec,
                    period=year,
                    ptype="fy",
                    value=v,
                    unit="percent",
                    prov=pid,
                    industry=f"nic2008_{code}",
                    dims={"activity_status": "ps_ss", "sex": sex, "survey_year": SURVEY_YEAR},
                )
            )
    want = {(y, c) for y in ("2023-24", "2022-23", "2021-22") for _, c in BROAD7}
    if seen != want:
        raise ShapeError(f"PLFS Statement 7: missing rows {sorted(want - seen)}")
    return rows


LABEL7 = {c: ("transport, storage & communications" if c == "H_J" else p) for p, c in BROAD7}
_NIC_CODE = re.compile(r"^(\d{2,4}|[A-U])$")


def _table26(ctx: BuildContext, pdf: Pdf, raw: Any) -> list[dict[str, Any]]:
    pages = pdf.find_pages(
        "Table (26): Percentage distribution of usually working persons (ps+ss) by industry of work",
        220,
        window=12,
        count=16,
    )
    pid = ctx.prov(
        raw=raw,
        table_id="Table (26)",
        locator=f"pp.{pages[0]}-{pages[-1]} (printed A-150 to A-165), rows NIC-2008 code (4-digit class, 3-digit group, 2-digit division, section letter), cols (2)-(10)",
        unit_as_published="per cent",
        price_basis="n/a",
        vintage=VINTAGE,
        release=RELEASE,
        notes="PLFS 2023-24 = July 2023-June 2024. Shares are of all usually working persons (ps+ss) in each column.",
    )
    pid_n = ctx.prov(
        raw=raw,
        table_id="Table (26)",
        locator=f"p.{pages[-1]} row 'sample worker', cols (2)-(10)",
        unit_as_published="number (sample workers)",
        price_basis="n/a",
        vintage=VINTAGE,
        release=RELEASE,
        notes="Unweighted sample counts, printed for reference.",
    )
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in pages:
        for ln in pdf.lines(page):
            toks = ln.split(" ")
            if ln.startswith("sample worker"):
                vals = numbers(toks[2:], 9, "Table 26 sample worker")
                for (sec, sex), v in zip(COLS9, vals, strict=True):
                    assert v is not None
                    rows.append(
                        _row(
                            sid=f"t26.sample_workers.{sec}.{sex}",
                            table="Table (26)",
                            item="sample_workers",
                            label="Sample workers (usual status ps+ss)",
                            sector=sec,
                            period="2023-24",
                            ptype="fy",
                            value=v,
                            unit="count",
                            prov=pid_n,
                            stock_flow="n/a",
                            dims={"activity_status": "ps_ss", "sex": sex, "survey_year": SURVEY_YEAR},
                        )
                    )
                seen.add("sample")
                continue
            code = toks[0]
            if not (_NIC_CODE.match(code) or code == "total") or len(toks) != 10:
                continue
            if not all(re.fullmatch(NUM, t) for t in toks[1:]):
                continue
            if code in seen:
                raise ShapeError(f"Table 26: NIC code {code} printed twice")
            seen.add(code)
            vals = numbers(toks[1:], 9, f"Table 26 {code}")
            level = (
                {1: "section", 2: "division", 3: "group", 4: "class"}.get(len(code), "total")
                if code != "total"
                else "total"
            )
            ind = "all" if code == "total" else code
            for (sec, sex), v in zip(COLS9, vals, strict=True):
                assert v is not None
                rows.append(
                    _row(
                        sid=f"t26.worker_share.{ind.lower()}.{sec}.{sex}",
                        table="Table (26)",
                        item=f"worker_share_nic_{level}",
                        label=f"Percentage distribution of usually working persons (ps+ss) by industry of work, NIC-2008 {level} {ind}",
                        sector=sec,
                        period="2023-24",
                        ptype="fy",
                        value=v,
                        unit="percent",
                        prov=pid,
                        industry=f"nic2008_{ind}",
                        dims={"activity_status": "ps_ss", "sex": sex, "survey_year": SURVEY_YEAR},
                    )
                )
    sections = {c for c in seen if re.fullmatch(r"[A-U]", c)}
    if "total" not in seen or "sample" not in seen or len(sections) < 20:
        raise ShapeError(f"Table 26: incomplete parse (sections {sorted(sections)}, total={'total' in seen})")
    return rows


# ---------------------------------------------------------------------------------------------
# Statements 10-12: quarterly average earnings by status (all-India, sector x sex)
# ---------------------------------------------------------------------------------------------

QUARTERS = (  # printed label fragments in order, and the fiscal quarter
    ("July- September", fq(2, 2023)),
    ("October", fq(3, 2023)),
    ("January – March", fq(4, 2023)),
    ("April- June 2024", fq(1, 2024)),
)
EARN = (
    # statement, title fragment, near page, item, label, unit description
    (
        "Statement 10",
        "Average wage/ salary earnings (in Rs) during the preceding calendar month by the regular wage/ salaried employees",
        47,
        "regular_wage_earnings_month",
        "Average wage/salary earnings during the preceding calendar month, regular wage/salaried employees (CWS)",
    ),
    (
        "Statement 11",
        "Average earnings (in Rs.) per day by casual labour engaged in works other than public works",
        48,
        "casual_wage_earnings_day",
        "Average earnings per day by casual labour in works other than public works (CWS)",
    ),
    (
        "Statement 12",
        "Average gross earnings (in Rs.) during the last 30 days from self-employment work",
        48,
        "self_employment_gross_earnings_30d",
        "Average gross earnings during the last 30 days from self-employment (CWS; zero/not reported excluded)",
    ),
)


def _block(pdf: Pdf, page: int, start: str) -> list[str]:
    """Lines from the one starting with `start` up to the next 'Statement NN:' or section/note heading."""
    lines = pdf.lines(page)
    idx = [i for i, ln in enumerate(lines) if ln.startswith(start + ":")]
    if len(idx) != 1:
        raise ShapeError(f"PLFS p.{page}: {start} title found {len(idx)} times")
    out = []
    for ln in lines[idx[0] + 1 :]:
        if re.match(r"^(Statement \d+:|2\.\d+(\.\d+)*\s?[A-Z])", ln):
            break
        out.append(ln)
    return out


def _statements_10_12(ctx: BuildContext, pdf: Pdf, raw: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for st, title, near, item, label in EARN:
        (page,) = pdf.find_pages(f"{st}: {title}", near, window=3, count=1)
        block = _block(pdf, page, st)
        text = " ".join(block)
        pos = [text.find(q) for q, _ in QUARTERS]
        if any(p < 0 for p in pos) or pos != sorted(pos):
            raise ShapeError(f"PLFS {st}: quarter labels missing or out of order: {pos}")
        data = [sp for sp in (split_label_numbers(ln, 9, strict=False) for ln in block) if sp is not None]
        if len(data) != 4:
            raise ShapeError(f"PLFS {st}: expected 4 quarterly data rows, got {len(data)}")
        pid = ctx.prov(
            raw=raw,
            table_id=st,
            locator=f"p.{page} (printed p.{18 if st == 'Statement 10' else 19}), 4 quarterly rows (Jul-Sep 2023 .. Apr-Jun 2024), cols (2)-(10)",
            unit_as_published="Rs",
            price_basis="current",
            vintage=VINTAGE,
            release=RELEASE,
            notes="Quarter rows are calendar quarters of the July 2023-June 2024 survey; Apr-Jun 2024 is Q1 of FY 2024-25."
            + (
                " Statement 10 wages are for the calendar month preceding the interview, so each row's"
                " reference months lag its survey-quarter label by one month (the Jul-Sep 2023 row"
                " covers wages of roughly Jun-Aug 2023)."
                if st == "Statement 10"
                else ""
            ),
        )
        for (_, per), (_, toks) in zip(QUARTERS, data, strict=True):
            vals = numbers(toks, 9, f"{st} {per}")
            for (sec, sex), v in zip(COLS9, vals, strict=True):
                assert v is not None
                rows.append(
                    _row(
                        sid=f"{st.lower().replace('statement ', 'st')}.{item}.{sec}.{sex}.current",
                        table=st,
                        item=item,
                        label=label,
                        sector=sec,
                        period=per,
                        ptype="fq",
                        value=v,
                        unit="INR",
                        prov=pid,
                        stock_flow="flow",
                        price_basis="current",
                        dims={"activity_status": "cws", "sex": sex},
                    )
                )
    return rows


# ---------------------------------------------------------------------------------------------
# Table 51: casual wage per day by NIC-2008 section (all-India, annual 2023-24)
# ---------------------------------------------------------------------------------------------

SECTIONS_51 = [*"ABCDEFGHIJKLMNOPQRSTU", "all"]
_T51_BLOCK = re.compile(r"^(rural|urban|rural\+urban) (male|female|person)$")


def _table51(ctx: BuildContext, pdf: Pdf, raw: Any) -> list[dict[str, Any]]:
    pages = pdf.find_pages(
        "Table (51): Average wage earnings (Rs.) per day from casual labour work by industry of work",
        407,
        window=5,
        count=3,
    )
    for p in pages:
        expect_text(pdf, p, "A B C D E F G H I J K L M N O P Q R S T U all")
    pid = ctx.prov(
        raw=raw,
        table_id="Table (51)",
        locator=f"pp.{pages[0]}-{pages[-1]} (printed A-343 to A-345), rows 'Average wage earnings (Rs.)' per sector x sex block, cols (2)-(23) = NIC sections A..U and all",
        unit_as_published="Rs",
        price_basis="current",
        vintage=VINTAGE,
        release=RELEASE,
        notes="First-visit schedule, all four quarters of July 2023-June 2024 combined. Note 2: a zero cell means no sample observation, so zero cells are not ingested. Note 4: high sampling fluctuations.",
    )
    pid_n = ctx.prov(
        raw=raw,
        table_id="Table (51)",
        locator=f"pp.{pages[0]}-{pages[-1]}, rows 'sample no. of days worked as casual labour', cols (2)-(23)",
        unit_as_published="number (sample person-days)",
        price_basis="n/a",
        vintage=VINTAGE,
        release=RELEASE,
        notes="Unweighted sample person-days; Note 3: sections may not add to 'all' (a worker can work in several sections in a day).",
    )
    rows: list[dict[str, Any]] = []
    seen = set()
    for p in pages:
        lines = pdf.lines(p)
        blk = None
        for i, ln in enumerate(lines):
            m = _T51_BLOCK.match(ln)
            if m:
                blk = ({"rural": "rural", "urban": "urban", "rural+urban": "total"}[m.group(1)], m.group(2))
                continue
            if blk is None:
                continue
            sec, sex = blk
            if ln.startswith("Average wage earnings (Rs.) "):
                vals = numbers(ln[len("Average wage earnings (Rs.) ") :].split(" "), 22, f"Table 51 {blk} wage")
                for s, v in zip(SECTIONS_51, vals, strict=True):
                    if v is None or v == 0:
                        continue  # Note 2: zero = no sample observation
                    rows.append(
                        _row(
                            sid=f"t51.casual_wage_day.{s.lower()}.{sec}.{sex}.current",
                            table="Table (51)",
                            item="casual_wage_earnings_day",
                            label=f"Average wage earnings per day from casual labour work, NIC-2008 section {s}",
                            sector=sec,
                            period="2023-24",
                            ptype="fy",
                            value=v,
                            unit="INR",
                            prov=pid,
                            industry=f"nic2008_{s}",
                            stock_flow="flow",
                            price_basis="current",
                            dims={"activity_status": "cws", "sex": sex, "survey_year": SURVEY_YEAR},
                        )
                    )
                seen.add((blk, "wage"))
            elif ln.startswith("labour ") and lines[i - 1].startswith("sample no. of days worked as casual"):
                vals = numbers(ln[len("labour ") :].split(" "), 22, f"Table 51 {blk} days")
                for s, v in zip(SECTIONS_51, vals, strict=True):
                    assert v is not None
                    rows.append(
                        _row(
                            sid=f"t51.sample_days.{s.lower()}.{sec}.{sex}",
                            table="Table (51)",
                            item="sample_casual_days",
                            label=f"Sample number of days worked as casual labour, NIC-2008 section {s}",
                            sector=sec,
                            period="2023-24",
                            ptype="fy",
                            value=v,
                            unit="count",
                            prov=pid_n,
                            industry=f"nic2008_{s}",
                            dims={"activity_status": "cws", "sex": sex, "survey_year": SURVEY_YEAR},
                        )
                    )
                seen.add((blk, "days"))
    want = {((s, x), k) for s in SECTORS for x in SEXES for k in ("wage", "days")}
    if seen != want:
        raise ShapeError(f"Table 51: missing blocks {sorted(want - seen)}")
    return rows


def build(ctx: BuildContext, unit: str) -> list[Dataset]:
    raw = ctx.raw(SRC, RAW)
    pdf = Pdf(raw.path)
    try:
        expect_text(pdf, 2, "23rd September 2024")
        lfs = _lfs(ctx, pdf, raw)
        st6 = _statement6(ctx, pdf, raw)
        ind = _statement7(ctx, pdf, raw) + _table26(ctx, pdf, raw)
        t20 = _table20(ctx, pdf, raw)
        t35 = _table35(ctx, pdf, raw)
        earn = _statements_10_12(ctx, pdf, raw) + _table51(ctx, pdf, raw)
    finally:
        pdf.close()
    return [
        Dataset(
            f"{unit}_plfs_lfs_indicators",
            frame(lfs),
            "PLFS LFPR, WPR, UR (usual status and CWS), sector x sex x age, survey years 2017-18..2023-24 (Jul-Jun)",
        ),
        Dataset(
            f"{unit}_plfs_status_dist",
            frame(st6),
            "PLFS Statement 6: workers (ps+ss) by status in employment, sector x sex, 2021-22..2023-24 (Jul-Jun)",
        ),
        Dataset(
            f"{unit}_plfs_industry_dist",
            frame(ind),
            "PLFS workers (ps+ss) by industry: Statement 7 broad divisions 2021-22..2023-24 and Table 26 NIC-2008 detail 2023-24",
        ),
        Dataset(
            f"{unit}_plfs_industry_status",
            frame(t20),
            "PLFS Table (20): workers (ps+ss) by status in employment within each NIC-2008 division group, sector x sex, 2023-24 (Jul-Jun)",
        ),
        Dataset(
            f"{unit}_plfs_enterprise_type",
            frame(t35),
            "PLFS Table (35) all-India rows: non-agricultural workers (ps+ss) by enterprise type (incl. government/public sector), sector x sex, 2023-24 (Jul-Jun)",
        ),
        Dataset(
            f"{unit}_plfs_earnings",
            frame(earn),
            "PLFS 2023-24 average earnings: regular, casual, self-employed by quarter (St 10-12); casual wage by NIC section (T51)",
        ),
    ]
