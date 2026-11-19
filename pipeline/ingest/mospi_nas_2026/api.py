"""MoSPI NAS API (eSankhyiki backend, api.mospi.gov.in): the long National Accounts time series.

Fetched through ctx.fetch with the host-scoped legacy-TLS opt-in (DECISIONS D1-6): keyless public GET,
JSON, at most 200 records per page (the API refuses `limit` > 200). Source `mospi_nas_api`.

Datasets (all `official`, values as served, unit '₹ Crore'):
- mospi_nas_2026_api_b2011_back: old base 2011-12 back series, annual 1950-51 to 2011-12 (current and
  constant 2011-12 prices). This is the only pre-2011-12 history in the project.
- mospi_nas_2026_api_b2011_annual: old base, 2011-12 to 2025-26, one record per revision round (FAE, SAE,
  PE, FRE, SRE, TRE, Final, 'Additional Revision'); the round is in series_id and dim_other `revision=`.
- mospi_nas_2026_api_b2011_quarterly: old base, quarterly 2011-12 to 2025-26 (no revision field).
- mospi_nas_2026_api_b2022_annual / _quarterly: new base 2022-23 (annual 2022-23 to 2025-26, quarterly
  Q1 2022-23 to Q1 2026-27). A cross-check of NAS 2026 plus the Q1 2026-27 quarter.
Indicators 1-20 (levels). Not ingested: 21/22 (growth rates: arithmetic on levels), 3/4 (taxes and
subsidies on products: the API labels them '₹ Lakh' although they are crore; see SKIPPED_LAKH_LABEL).
Indicator 8 ('GCF by industry of use') is not Statement 1.1 GCF and changes concept at the splice: item
gcf_excl_valuables (current series) and gcf_incl_errors_omissions (back series); see GCF_BY_USE.
The new base has no back series yet: one probe (GDP) is pinned and the build fails if data appear.

Vintage: the API prints no release date, so every row's vintage is the snapshot (retrieval) date of its
page, taken from the pin; revision rounds are told apart by the revision field, not by vintage.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

import polars as pl

from pipeline.core.unit import BuildContext, Dataset, FetchContext, RawFile
from pipeline.core.units import clean_label, normalize_fy, parse_number
from pipeline.ingest.mospi_nas_2026 import codes

SRC_API = "mospi_nas_api"
API = "https://api.mospi.gov.in/api/nas"
REFERER = "https://esankhyiki.mospi.gov.in/"
LIMIT = 200
# Level indicators 1-20 of getNasIndicatorList (account_code=1). 21/22 are growth rates (arithmetic on
# the levels; not ingested, as for the NAS statements: issue mospi_nas_2026-3).
ANNUAL_INDICATORS = tuple(range(1, 21))
QUARTERLY_INDICATORS = (1, 2, 5, 9, 10, 11, 12, 13, 14, 15)
# (base_year, series, frequency) queried. The new base has no back series yet (issue mospi_nas_2026-7):
# one probe for GDP records whether that is still so.
QUERIES: tuple[tuple[str, str, str, tuple[int, ...]], ...] = (
    ("2011-12", "Back", "Annually", ANNUAL_INDICATORS),
    ("2011-12", "Current", "Annually", ANNUAL_INDICATORS),
    ("2022-23", "Current", "Annually", ANNUAL_INDICATORS),
    ("2011-12", "Current", "Quarterly", QUARTERLY_INDICATORS),
    ("2022-23", "Current", "Quarterly", QUARTERLY_INDICATORS),
    ("2022-23", "Back", "Annually", (5,)),
)


def query_tag(base: str, series: str, freq: str) -> str:
    return f"b{base[:4]}_{series.lower()}_{'a' if freq == 'Annually' else 'q'}"


def page_name(base: str, series: str, freq: str, ind: int, page: int) -> str:
    return f"nasapi_{query_tag(base, series, freq)}_i{ind:02d}_p{page:02d}.json"


def page_url(base: str, series: str, freq: str, ind: int, page: int) -> str:
    return (f"{API}/getNASData?base_year={base}&series={series}&frequency_code={freq}&indicator_code={ind}"
            f"&Format=JSON&limit={LIMIT}&page={page}")


def total_pages(doc: dict[str, Any]) -> int:
    """Pages of a getNASData answer; 0 for 'No Data Found'."""
    meta = doc.get("meta_data") or {}
    if not doc.get("data"):
        return 0
    if meta.get("recordPerPage") != LIMIT:
        raise ValueError(f"NAS API ignored limit={LIMIT}: {meta}")
    return int(meta["totalPages"])


def fetch(ctx: FetchContext) -> None:
    ctx.fetch(SRC_API, f"{API}/getNasIndicatorList?account_code=1", name="nasapi_indicator_list.json", referer=REFERER)
    for base, series, freq, inds in QUERIES:
        for ind in inds:
            first = ctx.fetch(SRC_API, page_url(base, series, freq, ind, 1),
                              name=page_name(base, series, freq, ind, 1), referer=REFERER)
            for page in range(2, total_pages(first.read_json()) + 1):
                ctx.fetch(SRC_API, page_url(base, series, freq, ind, page),
                          name=page_name(base, series, freq, ind, page), referer=REFERER)


# ---------------------------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------------------------

# indicator_code -> (description as served by getNasIndicatorList and in every record, item code)
INDICATORS: dict[int, tuple[str, str]] = {
    1: ("Gross Value Added", "gva"),
    2: ("Net Taxes on Products", "net_taxes_on_products"),
    3: ("Taxes on Products", "taxes_on_products"),
    4: ("Subsidies on Products", "subsidies_on_products"),
    5: ("Gross Domestic Product", "gdp"),
    6: ("Consumption of Fixed Capital", "cfc"),
    7: ("Net Domestic Product", "ndp"),
    8: ("Gross Capital Formation by Industry of Use", "gcf_excl_valuables"),  # not 1.1 GCF: see GCF_BY_USE
    9: ("Gross Fixed Capital Formation", "gfcf"),
    10: ("Private Final Consumption Expenditure", "pfce"),
    11: ("Government Final Consumption Expenditure", "gfce"),
    12: ("Change in Stock", "cis"),
    13: ("Valuables", "valuables"),
    14: ("Export of Goods and Services", "exports"),
    15: ("Import of Goods and Services", "imports"),
    16: ("Primary Income Receivable Net From Row", "primary_income_row_net"),
    17: ("Gross National Income", "gni"),
    18: ("Other Current Transfers Net From Row", "other_current_transfers_row_net"),
    19: ("Gross National Disposable Income", "gndi"),
    20: ("Gross Saving", "gross_saving"),
    21: ("GVA Growth Rate", "gva_growth"),
    22: ("GDP Growth Rate", "gdp_growth"),
}
# Taxes and subsidies on products (3, 4) are served with unit '₹ Lakh', but taxes - subsidies equals net
# taxes on products (indicator 2, '₹ Crore') in every year, revision round and price basis (74 of 74 checks,
# old and new base), so the values are in crore and the label is wrong (issue mospi_nas_2026-31). We do not
# relabel a publisher's unit: both are skipped (NAS Statement 1.1 carries them on both bases). The build
# asserts the label is still '₹ Lakh', so a corrected API is noticed.
SKIPPED_LAKH_LABEL = (3, 4)
UNIT_CRORE, UNIT_LAKH = "₹ Crore", "₹ Lakh"
# Indicator 8 'Gross Capital Formation by Industry of Use' is not Statement 1.1 GCF, and its concept changes at
# the splice (verifier finding c-1, issue mospi_nas_2026-37). Current series, both bases: GFCF + CIS without
# valuables, the concept of NAS 2026 Statement 7.2, so it takes 7.2's item code `gcf_excl_valuables` (new base: equal
# to 7.2 in all 150 industry x year x price cells within 0.5 crore). Old-base back series: a whole-economy total only,
# equal to old-base NAS 2025 Statement 1.1 GCF at 2011-12 (the one overlapping year), which also holds valuables and
# errors and omissions (issue 14); GCF - GFCF - CIS - valuables is 14 crore or more in every year 1950-51..2011-12.
# Separate codes stop a join on item_code from mixing the three concepts; _check_gcf_concept fails the build if
# the served concept changes.
GCF_BY_USE = 8
ITEM_BACK = {GCF_BY_USE: "gcf_incl_errors_omissions"}
GCF_NOTE = {
    "Current": " Indicator 8 ('GCF by industry of use', item gcf_excl_valuables) is GFCF + CIS without valuables, as"
    " in NAS 2026 Statement 7.2; it is not Statement 1.1 GCF.",
    "Back": " Indicator 8 ('GCF by industry of use', item gcf_incl_errors_omissions) is a whole-economy total in the"
    " old Statement 1.1 GCF concept (incl. valuables and errors and omissions; equal to NAS 2025 1.1 GCF at 2011-12);"
    " do not splice it to the current series' gcf_excl_valuables.",
}

STAGE = {
    "First Advance Estimates": "FAE",
    "Second Advance Estimates": "SAE",
    "Provisional Estimates": "PE",
    "First Revised Estimates": "FRE",
    "Second Revised Estimates": "SRE",
    "Third Revised Estimates": "TRE",
    "Final Estimates": "Final",
    "Additional Revision": "Revised",  # an extra revision round the API shows for 2011-12 to 2013-14 (old base)
}

# API industry labels not in codes.INDUSTRY (normalised with codes.norm).
API_INDUSTRY = {
    "total gross value added": "total",
    "total gross capital formation": "total",
    "trade hotels transport communication and services related to broadcasting": "trade_transport_comm",
    "financial real estate and professional services": "financial_real_estate_prof",
    "transport by other means": "transport_other_means",  # back series: road + water + air + incidental
}
# API institutional-sector labels. 'Household Sector' (GFCF) is the NAS household sector incl. NPISH, as in
# Statements 1.11/1.14. 'Total ...' is the sum of the six sectors.
API_INSTITUTION = {
    **codes.INSTITUTION,
    "household sector": "households_npish",
    "total gross value added": "total_economy",
    "total consumption of fixed capital": "total_economy",
    "total gross fixed capital formation": "total_economy",
    "total gross saving": "total_economy",
}
RECORD_KEYS = {"base_year", "series", "year", "indicator", "frequency", "revision", "quarter", "industry",
               "subindustry", "institutional_sector", "state", "current_price", "constant_price", "unit"}
# Publisher data errors skipped by exact content (issue mospi_nas_2026-32): a Gross National Disposable Income
# record dated '1999' that repeats the 2025-26 First Advance Estimate at current prices (constant price null).
KNOWN_BAD = {("b2011_current_a", 19, "1999", "First Advance Estimates", "36204793", None)}
# How the API serves a blank price (e.g. GNDI and gross saving have no constant-price figure).
MISSING = (None, "", "nan", "NaN")

DATASETS = {
    ("2011-12", "Back", "Annually"): (
        "api_b2011_back", "NAS API (eSankhyiki), old base 2011-12 back series, annual 1950-51 to 2011-12"),
    ("2011-12", "Current", "Annually"): (
        "api_b2011_annual",
        "NAS API (eSankhyiki), old base 2011-12, annual 2011-12 to 2025-26, one series per revision round"),
    ("2011-12", "Current", "Quarterly"): (
        "api_b2011_quarterly", "NAS API (eSankhyiki), old base 2011-12, quarterly 2011-12 to 2025-26"),
    ("2022-23", "Current", "Annually"): (
        "api_b2022_annual",
        "NAS API (eSankhyiki), new base 2022-23, annual 2022-23 to 2025-26, one series per revision round"),
    ("2022-23", "Current", "Quarterly"): (
        "api_b2022_quarterly", "NAS API (eSankhyiki), new base 2022-23, quarterly Q1 2022-23 to Q1 2026-27"),
}
IMPORTS_NOTE = (" Imports (item imports) are the positive magnitudes served; subtract them in the expenditure"
                " identity.")


def _slug(s: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", s.lower())).strip("_")


def _industry(label: str) -> str:
    k = codes.norm(label)
    return API_INDUSTRY[k] if k in API_INDUSTRY else codes.industry_code(label)


def _institution(label: str) -> str:
    k = codes.norm(label)
    if k not in API_INSTITUTION:
        raise ValueError(f"NAS API: unmapped institutional sector {label!r} (normalised {k!r})")
    return API_INSTITUTION[k]


def _pages(ctx: BuildContext, base: str, series: str, freq: str, ind: int) -> list[tuple[RawFile, list[dict]]]:
    """The pinned pages of one query, with their pagination checked."""
    first = ctx.raw(SRC_API, page_name(base, series, freq, ind, 1))
    doc = first.read_json()
    n = total_pages(doc)
    if n == 0:
        if doc.get("msg") != "No Data Found":
            raise ValueError(f"NAS API {base}/{series}/{freq}/{ind}: empty answer without 'No Data Found': {doc}")
        return []
    out, total = [], int(doc["meta_data"]["totalRecords"])
    for p in range(1, n + 1):
        raw = first if p == 1 else ctx.raw(SRC_API, page_name(base, series, freq, ind, p))
        d = raw.read_json()
        meta = d["meta_data"]
        if (int(meta["page"]), int(meta["totalRecords"]), int(meta["totalPages"])) != (p, total, n):
            raise ValueError(f"NAS API {raw.name}: pagination changed between pages: {meta}")
        out.append((raw, d["data"]))
    if sum(len(recs) for _, recs in out) != total:
        raise ValueError(f"NAS API {base}/{series}/{freq}/{ind}: {total} records announced, a different number served")
    return out


def _check_indicator_list(ctx: BuildContext) -> None:
    doc = ctx.raw(SRC_API, "nasapi_indicator_list.json").read_json()["data"]
    got = {int(i["indicator_code"]): clean_label(i["description"]) for i in doc["indicator"]}
    want = {k: v[0] for k, v in INDICATORS.items()}
    if got != want:
        raise ValueError(f"NAS API indicator list changed: {got}")
    if {b["base_year"] for b in doc["base_year"]} != {"2011-12", "2022-23"}:
        raise ValueError(f"NAS API base years changed: {doc['base_year']}")


def build(ctx: BuildContext) -> list[Dataset]:
    _check_indicator_list(ctx)
    out: list[Dataset] = []
    for base, series, freq, inds in QUERIES:
        tag = query_tag(base, series, freq)
        if (base, series) == ("2022-23", "Back"):
            if any(_pages(ctx, base, series, freq, i) for i in inds):
                raise ValueError(
                    "NAS API now serves a new-base (2022-23) back series: ingest it (issue mospi_nas_2026-7)"
                )
            continue
        name, desc = DATASETS[(base, series, freq)]
        rows: list[dict[str, Any]] = []
        for ind in inds:
            rows += _indicator_rows(ctx, base, series, freq, ind, tag)
        note = IMPORTS_NOTE
        if GCF_BY_USE in inds:
            _check_gcf_concept(tag, series, rows)
            note += GCF_NOTE[series]
        df = pl.DataFrame(rows, infer_schema_length=None)
        out.append(Dataset(f"mospi_nas_2026_{name}", df, desc + "." + note))
    return out


def _check_gcf_concept(tag: str, series: str, rows: list[dict[str, Any]]) -> None:
    """Fail the build if indicator 8's whole-economy total stops being the concept its item code says: current
    series GCF = GFCF + CIS (within 3 crore, API rounding), back series GCF != GFCF + CIS + valuables (valuables
    served from 1999-2000 only) and no industry detail."""
    item = ITEM_BACK.get(GCF_BY_USE) if series == "Back" else INDICATORS[GCF_BY_USE][1]
    if series == "Back" and any(r["item_code"] == item and r["industry"] for r in rows):
        raise ValueError(f"NAS API {tag}: indicator 8 now has industry detail; re-check its concept (issue 37)")
    tot: dict[tuple, dict[str, float]] = {}
    for r in rows:
        if r["industry"] in (None, "total") and r["institution"] in (None, "total_economy"):
            tot.setdefault((r["period"], r["price_basis"], r["dim_other"]), {})[r["item_code"]] = r["value"]
    n, bad = 0, []
    for key, t in tot.items():
        if not {item, "gfcf", "cis"} <= set(t):
            continue
        n += 1
        gap = t[item] - t["gfcf"] - t["cis"] - (t.get("valuables", 0.0) if series == "Back" else 0.0)
        if (abs(gap) > 3) != (series == "Back"):
            bad.append((key, gap))
    if not n or bad:
        raise ValueError(f"NAS API {tag}: indicator 8 concept changed (issue mospi_nas_2026-37): {n} checks, {bad[:5]}")


def _indicator_rows(ctx: BuildContext, base: str, series: str, freq: str, ind: int, tag: str) -> list[dict[str, Any]]:
    desc, item = INDICATORS[ind]
    if series == "Back":
        item = ITEM_BACK.get(ind, item)
    pages = _pages(ctx, base, series, freq, ind)
    units = Counter(r.get("unit") for _, recs in pages for r in recs)
    if ind in SKIPPED_LAKH_LABEL:
        if set(units) - {UNIT_LAKH}:
            raise ValueError(f"NAS API {tag} indicator {ind}: unit label is now {dict(units)}; re-evaluate the skip")
        return []
    if pages and set(units) != {UNIT_CRORE}:
        raise ValueError(f"NAS API {tag} indicator {ind}: unexpected units {dict(units)}")
    quarterly = freq == "Quarterly"
    basis_con = f"constant_{base.replace('-', '_')}"
    seen: dict[tuple, tuple[Any, Any]] = {}
    rows: list[dict[str, Any]] = []
    for raw, recs in pages:
        prov: dict[str, str] = {}
        for rec in recs:
            if set(rec) - RECORD_KEYS:
                raise ValueError(f"NAS API {raw.name}: unknown record fields {sorted(set(rec) - RECORD_KEYS)}")
            if (rec["base_year"], rec["series"], rec["indicator"], rec["frequency"]) != (
                base, series, desc, "Quarterly" if quarterly else "Annual"
            ):
                raise ValueError(f"NAS API {raw.name}: record from another query: {rec}")
            if (tag, ind, rec["year"], rec.get("revision"), rec["current_price"], rec["constant_price"]) in KNOWN_BAD:
                continue
            if not re.fullmatch(r"(19|20)\d\d-(\d\d|(19|20)\d\d)", rec["year"]):  # '2011-12', '1999-2000'
                raise ValueError(f"NAS API {raw.name}: year {rec['year']!r} is not a fiscal-year label")
            period = normalize_fy(rec["year"])
            quarter = rec.get("quarter")
            if quarterly != bool(quarter) or (quarter and quarter not in ("Q1", "Q2", "Q3", "Q4")):
                raise ValueError(f"NAS API {raw.name}: quarter {quarter!r} in a {freq} record")
            if rec.get("state"):
                raise ValueError(f"NAS API {raw.name}: state-level record {rec}")
            revision = rec.get("revision")
            if (series == "Current" and not quarterly) != bool(revision):
                raise ValueError(f"NAS API {raw.name}: revision {revision!r} unexpected for {series}/{freq}")
            if revision and revision not in STAGE:
                raise ValueError(f"NAS API {raw.name}: unknown revision {revision!r}")
            dims: dict[str, Any] = {"geography": "IN", "industry": None, "institution": None, "dim_other": None}
            sid, label = f"api.{item}", [desc]
            ind_label, sub_label = rec.get("industry"), rec.get("subindustry")
            sec_label = rec.get("institutional_sector")
            if sec_label and (ind_label or sub_label):
                raise ValueError(f"NAS API {raw.name}: record with both an industry and a sector: {rec}")
            if sub_label and not ind_label:
                raise ValueError(f"NAS API {raw.name}: sub-industry without industry: {rec}")
            if ind_label:
                code = _industry(sub_label or ind_label)
                dims["industry"] = code
                sid += f".ind_{code}"
                label += [clean_label(ind_label)] + ([clean_label(sub_label)] if sub_label else [])
            if sec_label:
                code = _institution(sec_label)
                dims["institution"] = code
                sid += f".sec_{code}"
                label.append(clean_label(sec_label))
            if revision:
                dims["dim_other"] = f"revision={_slug(revision)}"
                sid += f".rev_{_slug(revision)}"
                label.append(revision)
            if quarter:
                period = f"{quarter} {period}"
            key = (sid, period)
            vals = (rec["current_price"], rec["constant_price"])
            if key in seen:
                if seen[key] != vals:
                    raise ValueError(f"NAS API {raw.name}: two different records for {key}: {seen[key]} vs {vals}")
                continue  # an exact duplicate record (issue mospi_nas_2026-32)
            seen[key] = vals
            for basis, cell in (("current", rec["current_price"]), (basis_con, rec["constant_price"])):
                if cell in MISSING:
                    continue
                v = parse_number(cell)
                if v is None:
                    continue
                if basis not in prov:
                    prov[basis] = _prov(ctx, raw, base, series, freq, ind, desc, basis)
                rows.append({
                    "series_id": f"{sid}.{basis}",
                    "source_id": SRC_API,
                    "table_id": f"NAS API getNASData indicator {ind}",
                    "item_code": item,
                    "item_label": " | ".join(label),
                    **dims,
                    "stock_flow": "flow",
                    "period": period,
                    "period_type": "fq" if quarterly else "fy",
                    "value": v,
                    "unit": "INR_crore",
                    "price_basis": basis,
                    "base_year": base,
                    "vintage": raw.retrieved_at[:10],
                    "estimate_stage": STAGE[revision] if revision else "n.a.",
                    "status": "official",
                    "prov_id": prov[basis],
                })
    return rows


def _prov(ctx: BuildContext, raw: RawFile, base: str, series: str, freq: str, ind: int, desc: str, basis: str) -> str:
    page = int(raw.name.rsplit("_p", 1)[1].removesuffix(".json"))
    field = "current_price" if basis == "current" else "constant_price"
    return ctx.prov(
        raw=raw,
        table_id=f"NAS API getNASData indicator {ind}",
        locator=f"getNASData base_year={base}, series={series}, frequency_code={freq}, indicator_code={ind} "
        f"('{desc}'), page {page} (limit {LIMIT}); JSON data[].{field}; a record is identified by year, quarter, "
        "revision, industry, subindustry and institutional_sector",
        unit_as_published="Rs crore",
        conversion="none",
        price_basis=basis,
        base_year=base,
        vintage=raw.retrieved_at[:10],
        release=f"MoSPI NAS API (eSankhyiki backend), base {base}, series {series}, {freq.lower()}; snapshot "
        f"retrieved {raw.retrieved_at[:10]} (the API prints no release date)",
        notes="API unit label '₹ Crore'. vintage = snapshot date; revision rounds are told apart by the revision "
        "field (series_id suffix rev_* and dim_other revision=), not by vintage.",
    )
