"""ASUSE 2023-24 (October 2023-September 2024; NSO): factsheet key indicators and report tables.

Survey years are October-September (2022-23 = Oct 2022-Sep 2023; 2023-24 = Oct 2023-Sep 2024).
Rows carry `sy` periods ('2023-10/2024-09'; tagged survey_year=oct_sep by the parser and
converted by `_pdf.frame()`). Coverage:
unincorporated non-agricultural establishments in manufacturing, trade and other services
(excluding construction); GVA figures are for market establishments only. ASUSE 2023-24 widened
coverage (home tutors, domestic-service self-employed), so 2023-24 is not strictly comparable with
2022-23 (factsheet p.15).

household_group on these rows is the establishment's location sector (rural / urban / 'total' =
rural+urban), not a household class: it is the closest available proxy for the owning household's
rural/urban group. Every provenance record repeats this.

Report tables (Appendix A of 'Operational and Economic Characteristics', 1,280 pages): the
landscape pages are read with pypdf (which honours /Rotate); rows are keyed by the report's own
activity-category codes (Annexure I: M1-M25, E, T1-T5, S1-S15 and the totals M, T, S,
M+E+T+S) and block headers 'Sec:<sector> Est.:<establishment type>'.
"""

from __future__ import annotations

import re
from typing import Any

from pipeline.core.unit import BuildContext, Dataset
from pipeline.core.units import conversion_note, to_inr_crore

from ._pdf import NUM, Pdf, ShapeError, expect_text, frame, numbers

SRC = "mospi_asuse"
RAW_FS = "asuse_2023_24_factsheet.pdf"
RAW_REP = "asuse_2023_24_full_report.pdf"
# Neither PDF prints a release date. Vintages are the month of the server's Last-Modified header
# recorded at fetch time (factsheet 24 Dec 2024; report 30 Jan 2025): see the issues file.
VINTAGE_FS = "2024-12"
VINTAGE_REP = "2025-01"
RELEASE_FS = "Fact Sheet, Annual Survey of Unincorporated Sector Enterprises (ASUSE) 2023-24 (NSO, MoSPI; Dec 2024)"
RELEASE_REP = "ASUSE 2023-24 report 'Operational and Economic Characteristics' (NSO, MoSPI; Jan 2025)"
SURVEY_YEAR = "oct_sep"
# household_group convention for establishment rows (verifier finding VER-5): see the issues file.
HH_GROUP_NOTE = " household_group holds the LOCATION sector of the establishment (rural, urban; 'total' = rural+urban), used as a proxy for the owning household's rural/urban class; it is not a household classification."

# Annexure I (PDF pp.30-31): activity categories used in the report, with NIC-2008 codes.
ACTIVITIES: dict[str, str] = {
    "M1": "Cotton ginning, cleaning and bailing (NIC 01632)",
    "M2": "Manufacture of food products (NIC 10)",
    "M3": "Manufacture of beverages (NIC 11)",
    "M4": "Manufacture of tobacco products (NIC 12)",
    "M5": "Manufacture of textiles (NIC 13)",
    "M6": "Manufacture of wearing apparel (NIC 14)",
    "M7": "Manufacture of leather and related products (NIC 15)",
    "M8": "Manufacture of wood and products of wood and cork, except furniture (NIC 16)",
    "M9": "Manufacture of paper and paper products (NIC 17)",
    "M10": "Printing and reproduction of recorded media (NIC 18)",
    "M11": "Manufacture of coke and refined petroleum products (NIC 19)",
    "M12": "Manufacture of chemicals and chemical products (NIC 20)",
    "M13": "Manufacture of pharmaceuticals, medicinal chemical and botanical products (NIC 21)",
    "M14": "Manufacture of rubber and plastics products (NIC 22)",
    "M15": "Manufacture of other non-metallic mineral products (NIC 23)",
    "M16": "Manufacture of basic metals (NIC 24)",
    "M17": "Manufacture of fabricated metal products, except machinery and equipment (NIC 25)",
    "M18": "Manufacture of computer, electronic and optical products (NIC 26)",
    "M19": "Manufacture of electrical equipment (NIC 27)",
    "M20": "Manufacture of machinery and equipment n.e.c. (NIC 28)",
    "M21": "Manufacture of motor vehicles, trailers and semi-trailers (NIC 29)",
    "M22": "Manufacture of other transport equipment (NIC 30)",
    "M23": "Manufacture of furniture (NIC 31)",
    "M24": "Other manufacturing (NIC 32)",
    "M25": "Repair and installation of machinery and equipment (NIC 33)",
    "M": "Manufacturing activities (NIC 10-33, 01632)",
    "E": "Non-captive electricity generation and transmission (NIC 35103, 35105-35107, 35109)",
    "T1": "Wholesale and retail trade of motor vehicles and motor cycles (NIC 451, 453, 45401, 45402)",
    "T2": "Maintenance and repair of motor vehicles and motor cycles (NIC 452, 45403)",
    "T3": "Wholesale on a fee or contract basis (NIC 461)",
    "T4": "Other wholesale trade (NIC 462-466, 469)",
    "T5": "Other retail trade (NIC 47)",
    "T": "Trading activities (NIC 45-47)",
    "S1": "Accommodation (NIC 55)",
    "S2": "Food and accommodation service activities (NIC 56)",
    "S3": "Land transport (NIC 49211, 49219, 4922, 4923)",
    "S4": "Water transport (NIC 50)",
    "S5": "Warehousing and storage (NIC 521)",
    "S6": "Support activities for transportation, postal and courier activities (NIC 522, 53)",
    "S7": "Information and Communication (NIC 58-63)",
    "S8": "Financial service activities except insurance and pension funding (NIC 64193, 64300, 64309, 649)",
    "S9": "Other financial activities (NIC 6612, 6619, 662, 663)",
    "S10": "Real estate activities (NIC 68 excl. 68108, incl. 68109)",
    "S11": "Professional, Scientific and Technical activities (NIC 69-75)",
    "S12": "Administrative and support service activities (NIC 77-82)",
    "S13": "Education (NIC 85)",
    "S14": "Human Health and Social work activities (NIC 86-88)",
    "S15": "Other community, social and personal service activities (NIC 36-39, 90-93, 941, 9491, 9499, 95, 96)",
    "S": "Other services",
    "M+E+T+S": "All activities (M+E+T+S)",
}
TOTAL_ALIASES = {"M+T+E+S": "M+E+T+S"}  # printed this way in Tables 35/37


def act_code(code: str) -> str:
    """Report code -> industry dim value: 'M1' -> 'asuse_M1', 'M+E+T+S' -> 'asuse_all'."""
    return "asuse_all" if code == "M+E+T+S" else f"asuse_{code}"


def _dim(**kw: str) -> str:
    return ";".join(f"{k}={kw[k]}" for k in sorted(kw))


def _row(
    *,
    sid,
    table,
    item,
    label,
    sector,
    period,
    value,
    unit,
    prov,
    vintage,
    dims,
    industry=None,
    stock_flow="n/a",
    price_basis="n/a",
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
        "dim_other": _dim(survey_year=SURVEY_YEAR, **dims),
        "stock_flow": stock_flow,
        "period": period,
        "period_type": "fy",
        "value": value,
        "unit": unit,
        "price_basis": price_basis,
        "vintage": vintage,
        "estimate_stage": "n.a.",
        "status": "official",
        "prov_id": prov,
    }


# ---------------------------------------------------------------------------------------------
# Factsheet Tables 1-6 (ASUSE 2022-23 and 2023-24)
# ---------------------------------------------------------------------------------------------

FS_TABLES = (
    # (title, near page, columns: list of (period, dim key, dim value)), scope code
    ("Table 1: Key aggregate estimates of ASUSE 2022-23 and ASUSE 2023-24 (all-India)", 6, "ru", "M+E+T+S"),
    ("Table 2: Key aggregate estimates of ASUSE 2022-23 and ASUSE 2023-24 at BAC level (all-India)", 8, "bac", None),
    ("Table 3: Key indicators of ASUSE 2022-23 and ASUSE 2023-24 (all-India)", 10, "ru", "M+E+T+S"),
    ("Table 4: Key indicators of ASUSE 2022-23 and ASUSE 2023-24 (Manufacturing)", 11, "ru", "M"),
    ("Table 5: Key indicators of ASUSE 2022-23 and ASUSE 2023-24 (Trade)", 11, "ru", "T"),
    ("Table 6: Key indicators of ASUSE 2022-23 and ASUSE 2023-24 (Other Service)", 12, "ru", "S"),
)
# printed label start -> (item code, label, unit as published, clean unit, factor, stock_flow, price basis)
FS_ITEMS = (
    ("Number of", "establishments", "Number of establishments", "'00 (hundreds)", "count", 100.0, "stock", "n/a"),
    ("Workers", "workers", "Workers", "'00 (hundreds)", "count", 100.0, "stock", "n/a"),
    (
        "Gross Value Added*",
        "gva",
        "Gross Value Added (market establishments)",
        "Rs crore",
        "INR_crore",
        1.0,
        "flow",
        "current",
    ),
    (
        "Percentage of Market",
        "pct_market_estt",
        "Percentage of market establishments",
        "per cent",
        "percent",
        1.0,
        "n/a",
        "n/a",
    ),
    (
        "Percentage of Proprietary and",
        "pct_prop_partnership_estt",
        "Percentage of proprietary and partnership establishments",
        "per cent",
        "percent",
        1.0,
        "n/a",
        "n/a",
    ),
    (
        "Percentage of Hired Worker",
        "pct_hwe",
        "Percentage of hired worker establishments",
        "per cent",
        "percent",
        1.0,
        "n/a",
        "n/a",
    ),
    (
        "Emoluments (Rs.) per Formal",
        "emol_per_formal_hired_worker",
        "Emoluments per formal hired worker (annual)",
        "Rs",
        "INR",
        1.0,
        "flow",
        "current",
    ),
    (
        "Emoluments (Rs.) per Informal",
        "emol_per_informal_hired_worker",
        "Emoluments per informal hired worker (annual)",
        "Rs",
        "INR",
        1.0,
        "flow",
        "current",
    ),
    (
        "Emoluments (Rs.) per Hired",
        "emol_per_hired_worker",
        "Emoluments per hired worker (annual)",
        "Rs",
        "INR",
        1.0,
        "flow",
        "current",
    ),
    (
        "Gross Value of Output (GVO)*",
        "gvo_per_estt",
        "Gross value of output per establishment (market establishments)",
        "Rs",
        "INR",
        1.0,
        "flow",
        "current",
    ),
    (
        "GVA (Rs.) per",
        "gva_per_estt",
        "GVA per establishment (market establishments)",
        "Rs",
        "INR",
        1.0,
        "flow",
        "current",
    ),
    (
        "GVA per worker*",
        "gva_per_worker",
        "GVA per worker (market establishments)",
        "Rs",
        "INR",
        1.0,
        "flow",
        "current",
    ),
)
_SECT = {"R": "rural", "U": "urban", "R+U": "total"}


def _factsheet(ctx: BuildContext) -> list[dict[str, Any]]:
    raw = ctx.raw(SRC, RAW_FS)
    pdf = Pdf(raw.path)
    rows: list[dict[str, Any]] = []
    try:
        expect_text(pdf, 2, "ASUSE 2023-24 was conducted during October, 2023 to September, 2024")
        for title, near, layout, scope in FS_TABLES:
            (page,) = pdf.find_pages(title, near, window=3, count=1)
            lines = pdf.lines(page)
            start = [i for i, ln in enumerate(lines) if ln.startswith(title.split(":")[0] + ":")]
            if len(start) != 1:
                raise ShapeError(f"factsheet p.{page}: {title!r} not found once")
            body = lines[start[0] + 1 :]
            hdr = "R U R+U R U R+U" if layout == "ru" else "M T S M T S"
            if hdr not in body[:8]:
                raise ShapeError(f"factsheet {title}: column header {hdr!r} not found")
            cols = hdr.split(" ")
            seen: set[str] = set()
            provs: dict[str, str] = {}
            for ln in body:
                if ln.startswith("Table ") or ln.startswith("Note") or ln.startswith("*pertaining"):
                    break
                hit = [it for it in FS_ITEMS if ln.startswith(it[0] + " ") and re.search(rf"( {NUM}){{6}}$", ln)]
                if not hit:
                    continue
                if len(hit) != 1:
                    raise ShapeError(f"factsheet {title}: ambiguous row {ln!r}")
                prefix, item, label, uap, unit, factor, sf, pb = hit[0]
                if item in seen:
                    raise ShapeError(f"factsheet {title}: duplicate row {item}")
                seen.add(item)
                vals = numbers(ln.split(" ")[-6:], 6, f"factsheet {title} {item}")
                if uap not in provs:
                    provs[uap] = ctx.prov(
                        raw=raw,
                        table_id=title.split(":")[0],
                        locator=f"p.{page}, '{title}', rows by parameter label, cols (2)-(7) = 2022-23 then 2023-24 x {' '.join(cols[:3])}",
                        unit_as_published=uap,
                        conversion=(
                            "x 100 ('00 -> count)"
                            if factor == 100.0
                            else conversion_note("INR_crore")
                            if unit == "INR_crore"
                            else "none"
                        ),
                        price_basis=pb,
                        vintage=VINTAGE_FS,
                        release=RELEASE_FS,
                        notes="ASUSE years are October-September (2022-23 = Oct 2022-Sep 2023; 2023-24 = Oct 2023-Sep 2024). GVA and GVA/GVO ratios are for market establishments only." + HH_GROUP_NOTE,
                    )
                for j, v in enumerate(vals):
                    if v is None:
                        raise ShapeError(f"factsheet {title} {item}: blank cell {j}")
                    period = "2022-23" if j < 3 else "2023-24"
                    c = cols[j]
                    if layout == "ru":
                        sector, act = _SECT[c], scope
                    else:
                        sector, act = "total", c
                    rows.append(
                        _row(
                            sid=f"fs.{item}.{act_code(act).lower().replace('+', '')}.{sector}"
                            + (".current" if pb == "current" else ""),
                            table=f"Factsheet {title.split(':')[0]}",
                            item=item,
                            label=label,
                            sector=sector,
                            period=period,
                            value=v * factor if unit != "INR_crore" else to_inr_crore(v, "INR_crore"),
                            unit=unit,
                            prov=provs[uap],
                            vintage=VINTAGE_FS,
                            industry=act_code(act),
                            stock_flow=sf,
                            price_basis=pb,
                            dims={},
                        )
                    )
            need = (
                {"establishments", "workers", "gva"}
                if title.startswith(("Table 1", "Table 2"))
                else {it[1] for it in FS_ITEMS[3:]}
            )
            if seen != need:
                raise ShapeError(f"factsheet {title}: rows {sorted(seen)} != expected {sorted(need)}")
    finally:
        pdf.close()
    return rows


# ---------------------------------------------------------------------------------------------
# Report Appendix A tables by activity category
# ---------------------------------------------------------------------------------------------

_CODE_RE = re.compile(r"^(M\d{1,2}|T\d|S\d{1,2}|M|E|T|S|M\+E\+T\+S|M\+T\+E\+S)$")
_BLOCK_RE = re.compile(r"Sec:(Rural|Urban|Combined)(?: Est\.:(OAE|HWE|All))?")
SEC = {"Rural": "rural", "Urban": "urban", "Combined": "total"}
EST = {"OAE": "oae", "HWE": "hwe", "All": "all", None: None}


def _blocks(
    pdf: Pdf, pages: list[int], ncols: int, table: str
) -> dict[tuple[str, str | None], dict[str, list[float | None]]]:
    """{(sector, estt type): {activity code: values}} from pages whose blocks start with 'Sec:... Est.:...'.
    A page without a block header continues the previous block. Every block must hold all 50 codes."""
    out: dict[tuple[str, str | None], dict[str, list[float | None]]] = {}
    cur: tuple[str, str | None] | None = None
    for p in pages:
        for ln in pdf.lines(p):
            m = _BLOCK_RE.fullmatch(ln)
            if m:
                cur = (SEC[m.group(1)], EST[m.group(2)])
                if cur in out:
                    raise ShapeError(f"ASUSE {table} p.{p}: block {cur} appears twice")
                out[cur] = {}
                continue
            toks = ln.split(" ")
            if not _CODE_RE.match(toks[0]) or len(toks) != ncols + 1:
                continue
            if not all(re.fullmatch(NUM, t) for t in toks[1:]):
                continue
            if cur is None:
                raise ShapeError(f"ASUSE {table} p.{p}: data row before any block header")
            code = TOTAL_ALIASES.get(toks[0], toks[0])
            if code in out[cur]:
                raise ShapeError(f"ASUSE {table} p.{p}: code {code} twice in block {cur}")
            out[cur][code] = numbers(toks[1:], ncols, f"ASUSE {table} {cur} {code}")
    for blk, rows in out.items():
        if set(rows) != set(ACTIVITIES):
            raise ShapeError(f"ASUSE {table} block {blk}: codes {sorted(set(ACTIVITIES) ^ set(rows))} missing/extra")
    return out


def _cols_by_sector(pdf: Pdf, pages: list[int], ncols: int, table: str) -> dict[str, list[float | None]]:
    """Tables 35/37: no block header; columns (2)-(10) are Rural/Urban/Combined x OAE/HWE/all."""
    out: dict[str, list[float | None]] = {}
    for p in pages:
        for ln in pdf.lines(p):
            toks = ln.split(" ")
            if _CODE_RE.match(toks[0]) and len(toks) == ncols + 1 and all(re.fullmatch(NUM, t) for t in toks[1:]):
                code = TOTAL_ALIASES.get(toks[0], toks[0])
                if code in out:
                    raise ShapeError(f"ASUSE {table}: code {code} twice")
                out[code] = numbers(toks[1:], ncols, f"ASUSE {table} {code}")
    if set(out) != set(ACTIVITIES):
        raise ShapeError(f"ASUSE {table}: codes {sorted(set(ACTIVITIES) ^ set(out))} missing/extra")
    return out


REP_TABLES = {
    # key: (title, first PDF page (printed A-page + 81), page count)
    "t4": ("Table 4: Estimated number of establishments alongwith its percentage pursuing mixed", 89, 9),
    "t6": ("Table 6: Per 1000 distribution of establishments by type of ownership for each activity category", 134, 18),
    "t29": (
        "Table 29: Estimated number of workers by nature of employment and gender for each activity category",
        827,
        18,
    ),
    "t31": ("Table 31: Estimated number of workers by worker type for each activity category", 917, 18),
    "t33": ("Table 33: Estimated annual emoluments (Rs.) per hired worker for each activity category", 1007, 3),
    "t35": (
        "Table 35: Estimated annual GVA per worker (Rs.) by establishment type for each activity category",
        1022,
        2,
    ),
    "t37": ("Table 37: Estimated annual GVA per establishment (Rs.) by establishment type for each activity", 1032, 2),
}
OWNERSHIP = (  # Table 6 cols (2)-(11)
    ("proprietary_male", "proprietary, male owner"),
    ("proprietary_female", "proprietary, female owner"),
    ("proprietary_all", "proprietary, all (incl. transgender)"),
    ("partnership_same_hh", "partnership with members of same household"),
    ("partnership_diff_hh", "partnership with members of different households"),
    ("shg", "SHG"),
    ("society_trust", "society/trust/club/association/body of individuals"),
    ("cooperative", "co-operatives"),
    ("others", "others"),
    ("all", "all"),
)
WORKER_TYPES = ("working_owner", "formal_hired", "informal_hired", "unpaid_family", "other", "total")  # Table 31
SEXES3 = ("male", "female", "all")


def _report(ctx: BuildContext) -> list[dict[str, Any]]:
    raw = ctx.raw(SRC, RAW_REP)
    pdf = Pdf(raw.path, engine="pypdf")
    rows: list[dict[str, Any]] = []
    P = "2023-24"
    try:
        expect_text(pdf, 2, "(October 2023 – September 2024)")
        for code in ACTIVITIES:  # Annexure I lists every code the tables use
            if code not in ("M+E+T+S",):
                expect_text(
                    pdf,
                    30
                    if code[0] in "ME" or code in ("T1", "T2", "T3", "T4", "T5", "T", "S1", "S2", "S3", "S4", "S5")
                    else 31,
                    code,
                )
        pages = {
            k: pdf.find_pages(t, near + n // 2, window=n // 2 + 3, count=n) for k, (t, near, n) in REP_TABLES.items()
        }

        def prov(key: str, what: str, uap: str, conv: str = "none", pb: str = "n/a", notes: str = "") -> str:
            t, _, _ = REP_TABLES[key]
            pg = pages[key]
            return ctx.prov(
                raw=raw,
                table_id=t.split(":")[0],
                locator=f"PDF pp.{pg[0]}-{pg[-1]} (printed A{pg[0] - 81}-A{pg[-1] - 81}), {what}; rows by activity-category code",
                unit_as_published=uap,
                conversion=conv,
                price_basis=pb,
                vintage=VINTAGE_REP,
                release=RELEASE_REP,
                notes=("ASUSE 2023-24 = October 2023-September 2024. " + notes).strip() + HH_GROUP_NOTE,
            )

        # Table 4: estimated number of establishments by sector x establishment type
        b4 = _blocks(pdf, pages["t4"], 2, "Table 4")
        p4 = prov("t4", "col (2) estimated number of establishments per 'Sec:.. Est.:..' block", "number")
        for (sec, est), data in sorted(b4.items()):
            for code, (n, _mixed) in data.items():
                rows.append(
                    _row(
                        sid=f"t4.establishments.{act_code(code).lower().replace('+', '')}.{sec}.{est}",
                        table="Table 4",
                        item="establishments",
                        label=f"Estimated number of establishments: {ACTIVITIES[code]}",
                        sector=sec,
                        period=P,
                        value=n,
                        unit="count",
                        prov=p4,
                        vintage=VINTAGE_REP,
                        industry=act_code(code),
                        stock_flow="stock",
                        dims={"estt_type": est},
                    )
                )
        # Table 6: per-1000 distribution by type of ownership
        b6 = _blocks(pdf, pages["t6"], 12, "Table 6")
        p6 = prov(
            "t6",
            "cols (2)-(11) per-1000 distribution by type of ownership",
            "per 1000 establishments",
            "per 1000 -> percent: x 0.1",
            notes="Shares of establishment COUNTS; the report publishes no GVA or surplus by ownership type.",
        )
        for (sec, est), data in sorted(b6.items()):
            for code, vals in data.items():
                for (own, lbl), v in zip(OWNERSHIP, vals[:10], strict=True):
                    assert v is not None
                    rows.append(
                        _row(
                            sid=f"t6.estt_share.{own}.{act_code(code).lower().replace('+', '')}.{sec}.{est}",
                            table="Table 6",
                            item="estt_share_by_ownership",
                            label=f"Distribution of establishments by type of ownership: {lbl}",
                            sector=sec,
                            period=P,
                            value=round(v / 10, 6),
                            unit="percent",
                            prov=p6,
                            vintage=VINTAGE_REP,
                            industry=act_code(code),
                            dims={"estt_type": est, "ownership": own},
                        )
                    )
                if vals[10] != b4[(sec, est)][code][0]:
                    raise ShapeError(
                        f"ASUSE Table 6 {sec} {est} {code}: establishments {vals[10]} != Table 4 {b4[(sec, est)][code][0]}"
                    )
        # Table 29: workers by nature of employment (full/part time) and gender
        b29 = _blocks(pdf, pages["t29"], 11, "Table 29")
        p29 = prov(
            "t29",
            "cols (2)-(10) estimated number of workers (full time, part time, all) x (male, female, all*)",
            "number",
        )
        for (sec, est), data in sorted(b29.items()):
            for code, vals in data.items():
                for k, v in enumerate(vals[:9]):
                    nat, sex = ("full_time", "part_time", "all")[k // 3], SEXES3[k % 3]
                    assert v is not None
                    rows.append(
                        _row(
                            sid=f"t29.workers.{nat}.{sex}.{act_code(code).lower().replace('+', '')}.{sec}.{est}",
                            table="Table 29",
                            item="workers",
                            label=f"Estimated number of workers ({nat.replace('_', ' ')}, {sex}): {ACTIVITIES[code]}",
                            sector=sec,
                            period=P,
                            value=v,
                            unit="count",
                            prov=p29,
                            vintage=VINTAGE_REP,
                            industry=act_code(code),
                            stock_flow="stock",
                            dims={"employment": nat, "estt_type": est, "sex": sex},
                        )
                    )
                if vals[9] != b4[(sec, est)][code][0]:
                    raise ShapeError(f"ASUSE Table 29 {sec} {est} {code}: establishments {vals[9]} != Table 4")
        # Table 31: workers by worker type and gender
        b31 = _blocks(pdf, pages["t31"], 18, "Table 31")
        p31 = prov("t31", "cols (2)-(19) estimated number of workers by worker type x (male, female, all*)", "number")
        for (sec, est), data in sorted(b31.items()):
            for code, vals in data.items():
                for k, v in enumerate(vals):
                    wt, sex = WORKER_TYPES[k // 3], SEXES3[k % 3]
                    assert v is not None
                    rows.append(
                        _row(
                            sid=f"t31.workers.{wt}.{sex}.{act_code(code).lower().replace('+', '')}.{sec}.{est}",
                            table="Table 31",
                            item=f"workers_{wt}",
                            label=f"Estimated number of workers, {wt.replace('_', ' ')} ({sex}): {ACTIVITIES[code]}",
                            sector=sec,
                            period=P,
                            value=v,
                            unit="count",
                            prov=p31,
                            vintage=VINTAGE_REP,
                            industry=act_code(code),
                            stock_flow="stock",
                            dims={"estt_type": est, "sex": sex, "worker_type": wt},
                        )
                    )
        # Table 33: emoluments per hired worker and number of hired workers (HWEs)
        b33 = _blocks(pdf, pages["t33"], 8, "Table 33")
        p33e = prov(
            "t33",
            "cols (2)-(4) annual emoluments per hired worker (formal, informal, all*)",
            "Rs",
            pb="current",
            notes="HWEs only. A per-worker value is not ingested where the matching hired-worker count (cols 5-7) is 0 (printed as 0: no such workers).",
        )
        p33n = prov("t33", "cols (5)-(7) estimated number of hired workers (formal, informal, all*)", "number")
        for (sec, _est), data in sorted(b33.items()):
            for code, vals in data.items():
                for k, kind in enumerate(("formal", "informal", "all")):
                    emol, n = vals[k], vals[3 + k]
                    assert emol is not None and n is not None
                    ac = act_code(code).lower().replace("+", "")
                    rows.append(
                        _row(
                            sid=f"t33.hired_workers.{kind}.{ac}.{sec}",
                            table="Table 33",
                            item="hired_workers",
                            label=f"Estimated number of hired workers ({kind}), HWEs: {ACTIVITIES[code]}",
                            sector=sec,
                            period=P,
                            value=n,
                            unit="count",
                            prov=p33n,
                            vintage=VINTAGE_REP,
                            industry=act_code(code),
                            stock_flow="stock",
                            dims={"estt_type": "hwe", "worker_type": f"{kind}_hired"},
                        )
                    )
                    if n > 0:
                        rows.append(
                            _row(
                                sid=f"t33.emol_per_hired_worker.{kind}.{ac}.{sec}.current",
                                table="Table 33",
                                item="emol_per_hired_worker",
                                label=f"Annual emoluments per hired worker ({kind}), HWEs: {ACTIVITIES[code]}",
                                sector=sec,
                                period=P,
                                value=emol,
                                unit="INR",
                                prov=p33e,
                                vintage=VINTAGE_REP,
                                industry=act_code(code),
                                stock_flow="flow",
                                price_basis="current",
                                dims={"estt_type": "hwe", "worker_type": f"{kind}_hired"},
                            )
                        )
        # Tables 35/37: GVA per worker / per establishment by establishment type (market establishments)
        for key, item, lbl in (
            ("t35", "gva_per_worker", "Annual GVA per worker"),
            ("t37", "gva_per_estt", "Annual GVA per establishment"),
        ):
            data = _cols_by_sector(pdf, pages[key], 9, REP_TABLES[key][0].split(":")[0])
            pv = prov(
                key,
                "cols (2)-(10) = Rural (OAE, HWE, all), Urban (...), Combined (...)",
                "Rs",
                pb="current",
                notes="Market establishments only. A printed 0 means no market establishment of that type in the cell and is not ingested.",
            )
            for code, vals in data.items():
                for k, v in enumerate(vals):
                    sec, est = ("rural", "urban", "total")[k // 3], ("oae", "hwe", "all")[k % 3]
                    if v is None or v == 0:
                        continue
                    rows.append(
                        _row(
                            sid=f"{key}.{item}.{act_code(code).lower().replace('+', '')}.{sec}.{est}.current",
                            table=REP_TABLES[key][0].split(":")[0],
                            item=item,
                            label=f"{lbl} (market establishments): {ACTIVITIES[code]}",
                            sector=sec,
                            period=P,
                            value=v,
                            unit="INR",
                            prov=pv,
                            vintage=VINTAGE_REP,
                            industry=act_code(code),
                            stock_flow="flow",
                            price_basis="current",
                            dims={"estt_type": est, "market": "yes"},
                        )
                    )
    finally:
        pdf.close()
    return rows


def build(ctx: BuildContext, unit: str) -> list[Dataset]:
    return [
        Dataset(
            f"{unit}_asuse_key_indicators",
            frame(_factsheet(ctx)),
            "ASUSE factsheet Tables 1-6: establishments, workers, GVA and key ratios, 2022-23 and 2023-24 (Oct-Sep), R/U (establishment location, in household_group) and BAC",
        ),
        Dataset(
            f"{unit}_asuse_2324_activity",
            frame(_report(ctx)),
            "ASUSE 2023-24 report Tables 4, 6, 29, 31, 33, 35, 37 by activity category x sector (establishment location, in household_group) x establishment type",
        ),
    ]
