"""MoSPI eSankhyiki API (api.mospi.gov.in; keyless, public; legacy TLS opt-in per DECISIONS D1-6).

Queries (all-India only; every page of a paginated answer is pinned as its own JSON file):
- NSS-77 AIDIS 2019 (survey_code 1), indicator 5: average value of assets, average cash loan,
  incidence of indebtedness and the distribution of households by quintile class of household
  expenditure x occupational category (rural: cultivator, non-cultivator; urban: self-employed,
  others; plus all). Indicator 9: average value of fixed assets, financial assets, valuables and
  cash loans by the same quintile classes and by household asset-holding class (deciles).
  -> dataset aidis_2019_quintile.
- PLFS annual indicators 6 (regular wage/salary earnings, preceding calendar month), 7 (casual wage
  per day) and 8 (self-employment gross earnings, last 30 days), agricultural years 2022-23 and
  2023-24, by quarter x rural/urban x sex. 2022-23 supplies April-June 2023 (= Q1 2023-24), which
  the PLFS AR 2023-24 PDF does not print. -> dataset plfs_earnings_api.
- ASUSE indicator 36 (ASUSE 2025, calendar year 2025; the API serves no earlier year for it):
  market value of land and fixed assets, net addition to fixed assets, outstanding loans, annual
  interest payable and annual rent payable on hired fixed assets, per establishment, by activity
  category x rural/urban x establishment type. -> dataset asuse_2025_assets_loans.

Not used: PLFS indicator 4 (worker distribution; its all-India cross-tabs are the AR tables
already read from the PDF), the ASUSE indicators that repeat the 2023-24 report tables, and the
ASI API (it repeats ASI Summary Results / Volume I, which are ingested from the PDFs).

Vintages. AIDIS: 2021-09-10, the release of NSS Report 588 (the press note of that date announces
it). PLFS agricultural year 2023-24: 2024-09-23 (AR 2023-24; the API values equal the AR's
Statements 10-12 to their printed precision, tested). PLFS agricultural year 2022-23 and ASUSE 2025
indicator 36: the release date of the report behind these numbers was not verified, so the vintage
is the date the API served them (2026-09-29) and the provenance says so.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode

from pipeline.core import geo
from pipeline.core.unit import BuildContext, Dataset, FetchContext
from pipeline.core.units import fq, parse_number

from ._pdf import ShapeError, frame

SRC = "mospi_esankhyiki_api"
API = "https://api.mospi.gov.in"
LIMIT = 100

# (pin-name stem, endpoint path, query parameters without page/limit)
QUERIES: list[tuple[str, str, dict[str, Any]]] = [
    (
        "nss77_aidis_i5_allindia",
        "/api/nss-77/getNss77AidisRecords",
        {"indicator_code": 5, "survey_code": 1, "state_code": 37},
    ),
    (
        "nss77_aidis_i9_allindia",
        "/api/nss-77/getNss77AidisRecords",
        {"indicator_code": 9, "survey_code": 1, "state_code": 37},
    ),
    *[
        (
            f"plfs_i{ind}_ay{year.replace('-', '_')}_allindia",
            "/api/plfs/getData",
            {"indicator_code": ind, "frequency_code": 1, "year_type_code": 1, "year": year, "state_code": 99},
        )
        for ind in (6, 7, 8)
        for year in ("2022-23", "2023-24")
    ],
    (
        "asuse_i36_allindia",
        "/api/asuse/getAsuseRecords",
        {"indicator_code": 36, "frequency_code": 1},
    ),
]


def url(path: str, params: dict[str, Any], page: int) -> str:
    return f"{API}{path}?{urlencode({**params, 'limit': LIMIT, 'page': page})}"


def fetch(ctx: FetchContext) -> None:
    """Page 1 of each query, then the remaining pages that page 1's meta_data announces."""
    for stem, path, params in QUERIES:
        first = ctx.fetch(SRC, url(path, params, 1), name=f"{stem}_p1.json", expect="json", headers=_ACCEPT)
        pages = _meta(first.read_json(), stem)["totalPages"]
        for page in range(2, pages + 1):
            ctx.fetch(SRC, url(path, params, page), name=f"{stem}_p{page}.json", expect="json", headers=_ACCEPT)


_ACCEPT = {"Accept": "application/json"}


def _meta(doc: dict[str, Any], where: str) -> dict[str, int]:
    meta = doc.get("meta_data")
    if not isinstance(meta, dict) or doc.get("statusCode") is not True:
        raise ShapeError(f"{where}: unexpected API answer: {str(doc)[:200]}")
    return meta


def pages(ctx: BuildContext, stem: str) -> list[tuple[Any, list[dict[str, Any]]]]:
    """[(raw file, records)] for every pinned page of a query; checks the page count and that the
    pages together hold exactly totalRecords records."""
    first = ctx.raw(SRC, f"{stem}_p1.json")
    meta = _meta(first.read_json(), stem)
    out = []
    for page in range(1, meta["totalPages"] + 1):
        raw = first if page == 1 else ctx.raw(SRC, f"{stem}_p{page}.json")
        doc = raw.read_json()
        m = _meta(doc, f"{stem} p{page}")
        if m["totalRecords"] != meta["totalRecords"] or m["page"] != page:
            raise ShapeError(f"{stem} p{page}: meta_data {m} disagrees with page 1 {meta}")
        out.append((raw, doc["data"]))
    n = sum(len(recs) for _, recs in out)
    if n != meta["totalRecords"]:
        raise ShapeError(f"{stem}: {n} records on {meta['totalPages']} pages, API says {meta['totalRecords']}")
    return out


def geography(name: str) -> str:
    """API state label -> project geography code (DECISIONS D1-9 via pipeline.core.geo)."""
    if re.fullmatch(r"all[- ]india", name.strip(), re.I):
        return "IN"
    return geo.state_code(name)


def _num(v: Any, where: str) -> float | None:
    if v is None:
        return None
    x = parse_number(str(v))
    if x is None and str(v).strip() not in ("", "-", "NA"):
        raise ShapeError(f"{where}: unparseable value {v!r}")
    return x


def _dim(**kw: str) -> str | None:
    return ";".join(f"{k}={kw[k]}" for k in sorted(kw)) or None


def _row(**kw: Any) -> dict[str, Any]:
    return {
        "source_id": SRC,
        "geography": "IN",
        "estimate_stage": "n.a.",
        "status": "official",
        **kw,
    }


def _check_unique(rows: list[dict[str, Any]], what: str) -> None:
    seen: set[tuple[str, str]] = set()
    for r in rows:
        k = (r["series_id"], r["period"])
        if k in seen:
            raise ShapeError(f"{what}: duplicate record {k}")
        seen.add(k)


# ---------------------------------------------------------------------------------------------
# AIDIS 2019 (NSS 77th round) by quintile class of household expenditure
# ---------------------------------------------------------------------------------------------

AIDIS_VINTAGE = "2021-09-10"  # NSS Report 588 release; announced by the press note of that date
AIDIS_RELEASE = (
    "NSS Report No. 588, All India Debt & Investment Survey 2019 (NSS 77th round; NSO, MoSPI; 10 Sep 2021), "
    "tables served by the eSankhyiki NSS-77 AIDIS API (survey_code 1)"
)
AIDIS_STOCK_DATE = "2018-06-30"
SECTORS = {"Rural": "rural", "Urban": "urban"}
OCC = {  # API occupational_category -> hh_type (same codes as the press-note dataset)
    ("rural", "Cultivator"): "cultivator",
    ("rural", "Non-cultivator"): "non_cultivator",
    ("rural", "All"): "all",
    ("urban", "Self-employed"): "self_employed",
    ("urban", "Others"): "other",
    ("urban", "All"): "all",
}
QUINTILE_BASIS = "aidis_hh_expenditure"
# indicator 5 sub-indicators: label -> (item_code, unit, stock_flow, published unit)
AIDIS5 = {
    "Per 1000 number of households": ("hh_distribution", "percent", "n/a", "per 1000 households"),
    "Average value of assets per household (Rs.)": ("ava_per_hh", "INR", "stock", "Rs per household"),
    "Number of households reporting cash loan per 1000 households": (
        "incidence_of_indebtedness",
        "percent",
        "n/a",
        "per 1000 households",
    ),
    "Average amount of cash loan per household (Rs.)": ("aod_per_hh", "INR", "stock", "Rs per household"),
}
AIDIS5_LABEL = {
    "hh_distribution": (
        "Distribution of households of the category over quintile classes of household expenditure "
        "(per 1000, stored as per cent)"
    ),
    "ava_per_hh": "Average value of assets per household",
    "incidence_of_indebtedness": "Households reporting cash loan outstanding (per 1000 households, stored as per cent)",
    "aod_per_hh": "Average amount of cash loan outstanding per household",
}
AIDIS9 = {
    "Average value (Rs.) of fixed assets": ("fixed_assets_per_hh", "Average value of fixed assets per household"),
    "Average value (Rs.) of financial assets": (
        "financial_assets_per_hh",
        "Average value of financial assets per household",
    ),
    "Average value (Rs.) of valuables": ("valuables_per_hh", "Average value of valuables per household"),
    "Average value (Rs.) of cash loan outstanding": ("cash_loan_per_hh", "Average cash loan outstanding per household"),
}
PER1000 = "per 1000 -> percent: x 0.1"


def _quintile_group(sector: str, q: str, where: str) -> str:
    """'1'..'5' or 'Q1'..'Q5' -> '<sector>_q1'..; 'All...' -> sector."""
    m = re.fullmatch(r"Q?([1-5])", q)
    if m:
        return f"{sector}_q{m.group(1)}"
    if q == "All" or q.startswith("All (Q"):
        return sector
    raise ShapeError(f"{where}: unknown quintile class {q!r}")


def _aidis(ctx: BuildContext, unit: str) -> Dataset:
    rows: list[dict[str, Any]] = []
    notes_common = (
        "Stocks as on 30.06.2018 (AIDIS 2019 visit 1). Quintile classes are AIDIS's own quintile classes of household "
        "expenditure (API label), coded household_group <sector>_q1..q5 with dim_other "
        f"quintile_basis={QUINTILE_BASIS}; they are NOT the SAM's HCES 2023-24 person-MPCE quintiles, and their "
        "exact definition (Report 588) could not be "
        "read because the report PDF was not located. household_group '<sector>' = all quintile classes."
    )
    pids: dict[tuple[str, str, str], str] = {}

    def prov(raw: Any, table: str, unit_pub: str, pb: str, locator: str) -> str:
        key = (raw.name, unit_pub, pb)
        if key not in pids:
            pids[key] = ctx.prov(
                raw=raw,
                table_id=table,
                locator=locator,
                unit_as_published=unit_pub,
                conversion=PER1000 if unit_pub.startswith("per 1000") else "none",
                price_basis=pb,
                vintage=AIDIS_VINTAGE,
                release=AIDIS_RELEASE,
                notes=notes_common,
            )
        return pids[key]

    # indicator 5
    for raw, recs in pages(ctx, "nss77_aidis_i5_allindia"):
        for r in recs:
            where = f"AIDIS i5 {raw.name}"
            if geography(r["state"]) != "IN":
                raise ShapeError(f"{where}: state {r['state']!r} (all-India query)")
            sec = SECTORS[r["sector"]]
            hh_type = OCC[(sec, r["occupational_category"])]
            item, unit_, sf, unit_pub = AIDIS5[r["sub_indicator"]]
            hg = _quintile_group(sec, r["quintile_class"], where)
            x = _num(r["value"], where)
            if x is None:
                continue
            if unit_ == "percent":
                x = round(x * 0.1, 6)
            pb = "current" if unit_ == "INR" else "n/a"
            rows.append(
                _row(
                    series_id=f"i5.{item}.{hg}.{hh_type}" + (".current" if pb == "current" else ""),
                    table_id="NSS-77 AIDIS indicator 5",
                    item_code=item,
                    item_label=AIDIS5_LABEL[item],
                    household_group=hg,
                    dim_other=_dim(hh_type=hh_type, quintile_basis=QUINTILE_BASIS),
                    stock_flow=sf,
                    period=AIDIS_STOCK_DATE,
                    period_type="date",
                    value=x,
                    unit=unit_,
                    price_basis=pb,
                    vintage=AIDIS_VINTAGE,
                    prov_id=prov(
                        raw,
                        "NSS-77 AIDIS indicator 5",
                        unit_pub,
                        pb,
                        f"{raw.name}: getNss77AidisRecords indicator_code=5 state_code=37, records with sub_indicator "
                        "per the item, by sector x occupational_category x quintile_class",
                    ),
                )
            )
    # indicator 9: quintile classes Q1..Q5 (+ all) and asset-holding classes 1..10
    totals: dict[tuple[str, str, str], dict[str, float]] = {}
    for raw, recs in pages(ctx, "nss77_aidis_i9_allindia"):
        for r in recs:
            where = f"AIDIS i9 {raw.name}"
            if geography(r["state"]) != "IN":
                raise ShapeError(f"{where}: state {r['state']!r} (all-India query)")
            sec = SECTORS[r["sector"]]
            hh_type = OCC[(sec, r["occupational_category"])]
            item, label = AIDIS9[r["sub_indicator"]]
            cls = r["asset_quintile_class"]
            x = _num(r["value"], where)
            if x is None:
                continue
            if cls.startswith("All ("):  # the two class totals must agree; only the quintile one is kept
                totals.setdefault((sec, hh_type, item), {})[cls] = x
                if not cls.startswith("All (Q"):
                    continue
            m = re.fullmatch(r"(10|[1-9])", cls)
            if m:
                hg, dims = sec, {"asset_holding_class": f"d{m.group(1)}"}
            else:
                hg, dims = _quintile_group(sec, cls, where), {"quintile_basis": QUINTILE_BASIS}
            rows.append(
                _row(
                    series_id=f"i9.{item}.{hg}.{hh_type}" + (f".ahc_d{m.group(1)}" if m else "") + ".current",
                    table_id="NSS-77 AIDIS indicator 9",
                    item_code=item,
                    item_label=label + (" by household asset-holding class" if m else ""),
                    household_group=hg,
                    dim_other=_dim(hh_type=hh_type, **dims),
                    stock_flow="stock",
                    period=AIDIS_STOCK_DATE,
                    period_type="date",
                    value=x,
                    unit="INR",
                    price_basis="current",
                    vintage=AIDIS_VINTAGE,
                    prov_id=prov(
                        raw,
                        "NSS-77 AIDIS indicator 9",
                        "Rs per household",
                        "current",
                        f"{raw.name}: getNss77AidisRecords indicator_code=9 state_code=37, by sector x "
                        "occupational_category "
                        "x asset_quintile_class ('Q1'-'Q5' quintile classes, '1'-'10' asset-holding classes)",
                    ),
                )
            )
    for key, t in totals.items():
        if len(t) != 2 or len(set(t.values())) != 1:
            raise ShapeError(f"AIDIS i9 {key}: the asset-holding-class and quintile-class totals differ: {t}")
    _check_unique(rows, "AIDIS")
    return Dataset(
        f"{unit}_aidis_2019_quintile",
        frame(rows),
        "AIDIS 2019 (NSS-77) via eSankhyiki API: assets, cash loans and indebtedness by expenditure quintile class "
        "(and asset-holding class) x rural/urban x household type, all-India, as on 30.06.2018",
    )


# ---------------------------------------------------------------------------------------------
# PLFS quarterly earnings (annual indicators 6-8)
# ---------------------------------------------------------------------------------------------

PLFS_ITEMS = {  # indicator -> (item code as in plfs_earnings, label, PDF statement)
    6: (
        "regular_wage_earnings_month",
        "Average wage/salary earnings during the preceding calendar month from regular wage/salaried employment",
        "Statement 10",
    ),
    7: (
        "casual_wage_earnings_day",
        "Average wage earnings per day from casual labour work other than public works",
        "Statement 11",
    ),
    8: (
        "self_employment_gross_earnings_30d",
        "Average gross earnings during last 30 days from self-employment",
        "Statement 12",
    ),
}
PLFS_SECTOR = {"rural": "rural", "urban": "urban", "rural + urban": "total"}
PLFS_SEX = {"male": "male", "female": "female", "person": "person"}
# quarter of an agricultural year starting in July of year Y -> (fiscal quarter, FY start year offset)
PLFS_QUARTER = {"Jul-Sep": (2, 0), "Oct-Dec": (3, 0), "Jan-Mar": (4, 0), "Apr-Jun": (1, 1)}
PLFS_VINTAGE = {
    "2023-24": (
        "2024-09-23",
        "Annual Report, PLFS, July 2023-June 2024 (NSO, MoSPI; 23 Sep 2024), Statements 10-12, as served by the "
        "eSankhyiki PLFS API",
    ),
    "2022-23": (
        "2026-09-29",
        "PLFS agricultural year July 2022-June 2023 (NSO, MoSPI) as served by the eSankhyiki PLFS API on 29 Sep 2026; "
        "vintage = date served, because the release date of the PLFS Annual Report 2022-23 was not verified",
    ),
}


def _plfs(ctx: BuildContext, unit: str) -> Dataset:
    rows: list[dict[str, Any]] = []
    for ind, (item, label, stmt) in PLFS_ITEMS.items():
        for year in ("2022-23", "2023-24"):
            vintage, release = PLFS_VINTAGE[year]
            y0 = int(year[:4])
            for raw, recs in pages(ctx, f"plfs_i{ind}_ay{year.replace('-', '_')}_allindia"):
                pid = ctx.prov(
                    raw=raw,
                    table_id=f"PLFS annual indicator {ind}",
                    locator=f"{raw.name}: getData indicator_code={ind} frequency_code=1 year_type_code=1 (agricultural "
                    f"year) year={year} state_code=99, records by quarter x sector x gender",
                    unit_as_published="Rs (API unit '₹')",
                    price_basis="current",
                    vintage=vintage,
                    release=release,
                    notes=(
                        f"Current weekly status; the same series as PLFS AR {stmt} (agricultural year {year}: quarters "
                        f"July {y0}-June {y0 + 1}; Apr-Jun = Q1 of FY {y0 + 1}-{str(y0 + 2)[-2:]}). The API prints one "
                        "decimal where the AR prints whole rupees."
                        + (
                            " Indicator 6 refers to the calendar month before the interview, so each quarter's "
                            "reference months lag its label by one month."
                            if ind == 6
                            else ""
                        )
                    ),
                )
                for r in recs:
                    where = f"PLFS i{ind} {raw.name}"
                    if geography(r["state"]) != "IN" or r["year"] != year or r["unit"] != "₹":
                        raise ShapeError(f"{where}: unexpected record {r}")
                    if r["year_type"] != "Agriculture Year" or r["frequency"] != "Annually":
                        raise ShapeError(f"{where}: unexpected year type {r}")
                    q, off = PLFS_QUARTER[r["quarter"]]
                    sec, sex = PLFS_SECTOR[r["sector"]], PLFS_SEX[r["gender"]]
                    x = _num(r["value"], where)
                    if x is None:
                        continue
                    rows.append(
                        _row(
                            series_id=f"api_i{ind}.{item}.{sec}.{sex}.current",
                            table_id=f"PLFS annual indicator {ind}",
                            item_code=item,
                            item_label=label,
                            household_group=sec,
                            dim_other=_dim(activity_status="cws", sex=sex),
                            stock_flow="flow",
                            period=fq(q, y0 + off),
                            period_type="fq",
                            value=x,
                            unit="INR",
                            price_basis="current",
                            vintage=vintage,
                            prov_id=pid,
                        )
                    )
    _check_unique(rows, "PLFS API")
    return Dataset(
        f"{unit}_plfs_earnings_api",
        frame(rows),
        "PLFS earnings (regular monthly, casual daily, self-employed 30-day) by quarter x rural/urban x sex, "
        "Q2 2022-23..Q1 2024-25, via eSankhyiki API (fills Q1 2023-24 = Apr-Jun 2023)",
    )


# ---------------------------------------------------------------------------------------------
# ASUSE 2025, indicator 36: land, fixed assets, loans, interest and rent per establishment
# ---------------------------------------------------------------------------------------------

ASUSE_VINTAGE = "2026-09-29"
ASUSE_RELEASE = (
    "ASUSE 2025 (calendar year 2025; NSO, MoSPI), indicator 36 as served by the eSankhyiki ASUSE API on "
    "29 Sep 2026; vintage = date served (MoSPI's publication list dates the ASUSE 2025 report 6 May 2026 and its "
    "factsheet 24 Mar 2026, but these API values were not matched to either document)"
)
ASUSE36 = {  # sub_indicator -> (item, label, stock_flow)
    "Market Value (Rs.) of Land Per Estt.": ("land_value_per_estt", "Market value of land per establishment", "stock"),
    "Market Value (Rs.) of Fixed Assets Per Estt.": (
        "fixed_assets_value_per_estt",
        "Market value of fixed assets per establishment",
        "stock",
    ),
    "Net Addition to Fixed Assets (Rs.) Per Estt. During Last 365 Days/ Last Year": (
        "net_addition_fixed_assets_per_estt",
        "Net addition to fixed assets per establishment during the last 365 days / last year",
        "flow",
    ),
    "Outstan-ding Loan (Rs.) Per Estt.": ("outstanding_loan_per_estt", "Outstanding loan per establishment", "stock"),
    "Annual Interest Payable (Rs.) Payable Per Estt.": (
        "interest_payable_per_estt",
        "Annual interest payable per establishment",
        "flow",
    ),
    "Annual Rental (Rs.) Payable on Hired Fixed Assets Per Estt.": (
        "rent_payable_hired_fixed_assets_per_estt",
        "Annual rent payable on hired fixed assets per establishment",
        "flow",
    ),
}
ASUSE_SECTOR = {"Rural": "rural", "Urban": "urban", "Combined": "total"}
ASUSE_EST = {
    "Hired Worker Establishments(HWE)": "hwe",
    "Own Account Establishments(OAE)": "oae",
    "All Establishments(All)": "all",
}
ASUSE_FA = {"Owned": "owned", "Hired": "hired", "All": "all"}


def _norm(s: str) -> str:
    s = re.sub(r"\(NIC[^)]*\)", "", s)
    s = s.replace("- ", "-").replace("&", "and")
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _asuse_codes() -> dict[str, str]:
    """Normalised ASUSE report activity names (2023-24 report, Annexure I) -> report code; aliases for
    the API's spellings are listed explicitly (checked by hand against Annexure I). The API's 50
    ASUSE 2025 categories are the same 50 names (the 2025 report's own annexure was not read)."""
    from .asuse import ACTIVITIES

    out = {_norm(v): k for k, v in ACTIVITIES.items()}
    out.update({_norm(k): v for k, v in ASUSE_ALIASES.items()})
    return out


# API activity_category spellings that differ from Annexure I, mapped to the report's codes.
ASUSE_ALIASES: dict[str, str] = {
    "All": "M+E+T+S",
    "Manufacture of Wood and Products of Wood and Cork, Except Furniture, Manufacture of Articles of Straw and "
    "Plaiting Materials": "M8",
}


def _asuse(ctx: BuildContext, unit: str) -> Dataset:
    from .asuse import act_code

    codes = _asuse_codes()
    rows: list[dict[str, Any]] = []
    for raw, recs in pages(ctx, "asuse_i36_allindia"):
        pid = ctx.prov(
            raw=raw,
            table_id="ASUSE indicator 36",
            locator=f"{raw.name}: getAsuseRecords indicator_code=36 frequency_code=1, by sector x activity_category x "
            "sub_indicator x establishment_type x fixed_assets",
            unit_as_published="Rs per establishment",
            price_basis="current",
            vintage=ASUSE_VINTAGE,
            release=ASUSE_RELEASE,
            notes=(
                "ASUSE 2025 covers calendar year 2025 (January-December). Stocks (land, fixed assets, loans) are as "
                "reported by each establishment during the survey, so their period is the survey year, not a date. "
                "household_group holds the LOCATION sector of the establishment (rural, urban; 'total' = combined), "
                "a proxy for the owning household's rural/urban class. fixed_assets owned/hired/all splits the "
                "fixed-asset value; rent payable is on hired fixed assets."
            ),
        )
        for r in recs:
            where = f"ASUSE i36 {raw.name}"
            if geography(r["state/UT"]) != "IN" or r["year"] != "2025" or r["frequency"] != "Annually":
                raise ShapeError(f"{where}: unexpected record {r}")
            name = _norm(r["activity_category"])
            if name not in codes:
                raise ShapeError(f"{where}: unmapped activity category {r['activity_category']!r}")
            code = codes[name]
            item, label, sf = ASUSE36[r["sub_indicator"]]
            sec, est = ASUSE_SECTOR[r["sector"]], ASUSE_EST[r["establishment_type"]]
            dims = {"establishment_type": est}
            if r.get("fixed_assets") is not None:
                dims["fixed_assets"] = ASUSE_FA[r["fixed_assets"]]
            x = _num(r["value"], where)
            if x is None:
                continue
            rows.append(
                _row(
                    series_id=f"i36.{item}.{act_code(code).lower()}.{sec}.{est}"
                    + (f".fa_{dims['fixed_assets']}" if "fixed_assets" in dims else "")
                    + ".current",
                    table_id="ASUSE indicator 36",
                    item_code=item,
                    item_label=label,
                    industry=act_code(code),
                    household_group=sec,
                    dim_other=_dim(**dims),
                    stock_flow=sf,
                    period="2025",
                    period_type="cy",
                    value=x,
                    unit="INR",
                    price_basis="current",
                    vintage=ASUSE_VINTAGE,
                    prov_id=pid,
                )
            )
    _check_unique(rows, "ASUSE i36")
    return Dataset(
        f"{unit}_asuse_2025_assets_loans",
        frame(rows),
        "ASUSE 2025 via eSankhyiki API: land and fixed-asset value, net addition, outstanding loans, interest and rent "
        "payable per establishment, by activity x rural/urban (location) x establishment type",
    )


def build(ctx: BuildContext, unit: str) -> list[Dataset]:
    return [_aidis(ctx, unit), _plfs(ctx, unit), _asuse(ctx, unit)]
