"""IMF International Trade in Goods by partner (IMTS, formerly DOTS), India as reporter.

Files (IMF SDMX 2.1 REST API, keyless; api.imf.org):
- the partner codelist CL_IMTS_COUNTRY (names of partners and partner groups);
- monthly, FY 2023-24 only, with all SDMX attributes: gives the publication date (the vintage),
  the unit, the derivation type, and cross-checks the long file;
- monthly, January 2011 to latest, data only (no attributes; smaller);
- annual (calendar year), all years, data only.

Only exports FOB (XG_FOB_USD) and imports CIF (MG_CIF_USD) are ingested: those are the two
indicators India reports (MG_FOB_USD has no India rows; TBG_USD is exports minus imports).

Quirk (registry `imf_sdmx.quirks`, verified here): OBS_VALUE is in US$ units although the SCALE
attribute says 6. The build checks the magnitude of the world total before converting to
US$ million.
"""

from __future__ import annotations

from typing import Any

import polars as pl
from lxml import etree

from pipeline.core.unit import BuildContext, Dataset, FetchContext, RawFile
from pipeline.core.units import clean_label

from ._common import CONV_USD_UNITS, UNIT, USD_UNITS_TO_MILLION, fy_sums, partner_dims, sid

SRC = "imf_sdmx"
BASE = "https://api.imf.org/external/sdmx/2.1"
CSV_ACCEPT = {"Accept": "application/vnd.sdmx.data+csv;version=1.0.0"}
KEY = "IND.XG_FOB_USD+MG_CIF_USD.*"
DATAFLOW = "IMF.STA:IMTS(1.0.0)"
INDICATORS = {
    "XG_FOB_USD": ("exports_fob", "Exports of goods, Free on board (FOB), US dollar"),
    "MG_CIF_USD": ("imports_cif", "Imports of goods, Cost insurance freight (CIF), US dollar"),
}
F_CODELIST = "imts_cl_country.xml"
F_ATTRS = "imts_ind_m_2023_24_attrs.csv"
F_MONTHLY = "imts_ind_m_2011on.csv"
F_ANNUAL = "imts_ind_a.csv"
FILES = {
    F_CODELIST: (f"{BASE}/codelist/IMF.STA/CL_IMTS_COUNTRY/latest", "xml", None),
    F_ATTRS: (f"{BASE}/data/IMF.STA,IMTS/{KEY}.M?startPeriod=2023-04&endPeriod=2024-03", "csv", CSV_ACCEPT),
    F_MONTHLY: (f"{BASE}/data/IMF.STA,IMTS/{KEY}.M?startPeriod=2011-01&detail=dataonly", "csv", CSV_ACCEPT),
    F_ANNUAL: (f"{BASE}/data/IMF.STA,IMTS/{KEY}.A?detail=dataonly", "csv", CSV_ACCEPT),
}
WORLD = "G001"
RELEASE = "IMF International Trade in Goods (by partner country), IMF.STA:IMTS(1.0.0), SDMX API"
EXPECTED_COLS = ("DATAFLOW", "COUNTRY", "INDICATOR", "COUNTERPART_COUNTRY", "FREQUENCY", "TIME_PERIOD", "OBS_VALUE")


def fetch(ctx: FetchContext) -> None:
    for name, (url, expect, headers) in FILES.items():
        ctx.fetch(SRC, url, name=name, expect=expect, headers=headers)


# ---------------------------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------------------------


def _partner_names(raw: RawFile) -> dict[str, str]:
    ns = {
        "str": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure",
        "com": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common",
    }
    tree = etree.parse(str(raw.path))
    lists = tree.findall(".//str:Codelist", ns)
    if len(lists) != 1 or lists[0].get("id") != "CL_IMTS_COUNTRY":
        raise ValueError(f"{raw.name}: expected exactly the codelist CL_IMTS_COUNTRY")
    out: dict[str, str] = {}
    for code in lists[0].findall("str:Code", ns):
        names = {n.get("{http://www.w3.org/XML/1998/namespace}lang"): n.text for n in code.findall("com:Name", ns)}
        if "en" not in names:
            raise ValueError(f"{raw.name}: code {code.get('id')} has no English name")
        out[code.get("id")] = clean_label(names["en"])
    if out.get(WORLD) != "World" or out.get("USA") is None:
        raise ValueError(f"{raw.name}: codelist does not look like CL_IMTS_COUNTRY (G001={out.get(WORLD)!r})")
    return out


def _read(raw: RawFile, freq: str) -> pl.DataFrame:
    """Observations of one SDMX-CSV file: indicator, partner, period ('YYYY-MM' or 'YYYY'), value (US$)."""
    df = pl.read_csv(raw.path, infer_schema_length=0)
    missing = [c for c in EXPECTED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{raw.name}: SDMX-CSV columns missing: {missing}")
    # Series-level rows carry attributes but no observation (TIME_PERIOD and OBS_VALUE empty).
    bad = df.filter(pl.col("TIME_PERIOD").is_null() & pl.col("OBS_VALUE").is_not_null())
    if bad.height:
        raise ValueError(f"{raw.name}: {bad.height} observation(s) without a TIME_PERIOD")
    obs = df.filter(pl.col("TIME_PERIOD").is_not_null())
    if obs.filter(pl.col("OBS_VALUE").is_null()).height:
        raise ValueError(f"{raw.name}: observations with an empty OBS_VALUE")
    for col, want in (("DATAFLOW", DATAFLOW), ("COUNTRY", "IND"), ("FREQUENCY", freq)):
        got = set(obs[col].unique().to_list())
        if got != {want}:
            raise ValueError(f"{raw.name}: {col} is {sorted(map(str, got))}, expected {want!r}")
    inds = set(obs["INDICATOR"].unique().to_list())
    if inds != set(INDICATORS):
        raise ValueError(f"{raw.name}: indicators {sorted(inds)}, expected {sorted(INDICATORS)}")
    pat = r"^\d{4}-M(0[1-9]|1[0-2])$" if freq == "M" else r"^\d{4}$"
    if not obs["TIME_PERIOD"].str.contains(pat).all():
        raise ValueError(f"{raw.name}: unexpected TIME_PERIOD format")
    period = pl.col("TIME_PERIOD").str.replace("-M", "-") if freq == "M" else pl.col("TIME_PERIOD")
    out = obs.select(
        pl.col("INDICATOR").alias("indicator"),
        pl.col("COUNTERPART_COUNTRY").alias("partner"),
        period.alias("period"),
        pl.col("OBS_VALUE").cast(pl.Float64).alias("usd"),
        *[pl.col(c) for c in ("DERIVATION_TYPE", "UNIT", "SCALE", "PUBLICATION_DATE", "SERIES_NAME") if c in obs.columns],
    )
    if out.select(["indicator", "partner", "period"]).is_duplicated().any():
        raise ValueError(f"{raw.name}: duplicate observations")
    if out.filter(pl.col("usd") < 0).height:
        raise ValueError(f"{raw.name}: negative trade values")
    return out


def _vintage_and_notes(attrs: pl.DataFrame) -> tuple[str, str]:
    pub = set(attrs["PUBLICATION_DATE"].unique().to_list())
    if len(pub) != 1 or None in pub:
        raise ValueError(f"{F_ATTRS}: expected one PUBLICATION_DATE, got {sorted(map(str, pub))}")
    vintage = next(iter(pub))[:10]
    units = set(attrs["UNIT"].unique().to_list())
    if units != {"USD"}:
        raise ValueError(f"{F_ATTRS}: UNIT {units}, expected USD")
    for ind, (_, label) in INDICATORS.items():
        names = set(attrs.filter(pl.col("indicator") == ind)["SERIES_NAME"].unique().to_list())
        if names != {label}:
            raise ValueError(f"{F_ATTRS}: SERIES_NAME of {ind} is {names}, expected {label!r}")
    deriv = attrs.group_by("DERIVATION_TYPE", maintain_order=True).len().sort("DERIVATION_TYPE")
    deriv_txt = ", ".join(f"{d}={n}" for d, n in deriv.iter_rows())
    notes = (
        f"IMF attribute file {F_ATTRS} (FY 2023-24 months): PUBLICATION_DATE {next(iter(pub))}; "
        f"DERIVATION_TYPE counts {deriv_txt} (M = 'Mixed-type data': reported by India's authorities, "
        "possibly completed with IMF staff estimates; the API does not flag which months). OBS_VALUE is "
        "in US$ units although SCALE=6 (registry quirk; checked on the world total). Partner = "
        "COUNTERPART_COUNTRY; exports FOB, imports CIF, as reported by India (not mirror data)."
    )
    return vintage, notes


def _check_units(monthly: pl.DataFrame) -> None:
    """The SCALE quirk: India's monthly world exports must be tens of billions of US$ in units."""
    w = monthly.filter((pl.col("partner") == WORLD) & (pl.col("indicator") == "XG_FOB_USD"))
    if w.height < 100:
        raise ValueError("IMTS monthly: world exports series is too short")
    lo, hi = w["usd"].min(), w["usd"].max()
    if not (5e9 <= lo and hi <= 2e11):
        raise ValueError(
            f"IMTS monthly world exports range {lo:.4g}..{hi:.4g}: not US$ units (SCALE quirk changed?)"
        )


def _rows(
    obs: pl.DataFrame,
    names: dict[str, str],
    *,
    period_type: str,
    prov: dict[str, str],
    vintage: str,
    status: str,
    value_col: str = "usd",
    scale: float = USD_UNITS_TO_MILLION,
) -> pl.DataFrame:
    unknown = sorted(set(obs["partner"].unique().to_list()) - set(names))
    if unknown:
        raise ValueError(f"IMTS: partner codes not in CL_IMTS_COUNTRY: {unknown}")
    rows: list[dict[str, Any]] = []
    for ind, partner, period, v in obs.select("indicator", "partner", "period", value_col).iter_rows():
        code, label = INDICATORS[ind]
        rows.append(
            {
                "series_id": f"imts.{code}.{sid(partner)}.current",
                "source_id": SRC,
                "table_id": DATAFLOW,
                "item_code": code,
                "item_label": f"{label} | partner: {names[partner]} ({partner})",
                **partner_dims(partner),
                "stock_flow": "flow",
                "period": period,
                "period_type": period_type,
                "value": v * scale,
                "unit": "USD_million",
                "price_basis": "current",
                "vintage": vintage,
                "estimate_stage": "n.a.",
                "status": status,
                "prov_id": prov[ind],
            }
        )
    return pl.DataFrame(rows, infer_schema_length=None).sort("series_id", "period")


# ---------------------------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------------------------


def build(ctx: BuildContext) -> list[Dataset]:
    raw_cl, raw_attr, raw_m, raw_a = (ctx.raw(SRC, f) for f in (F_CODELIST, F_ATTRS, F_MONTHLY, F_ANNUAL))
    names = _partner_names(raw_cl)
    attrs = _read(raw_attr, "M")
    vintage, notes = _vintage_and_notes(attrs)
    monthly = _read(raw_m, "M")
    annual = _read(raw_a, "A")
    _check_units(monthly)

    # The data-only long file must repeat the attribute file exactly for FY 2023-24.
    a = attrs.select("indicator", "partner", "period", "usd")
    b = monthly.filter(pl.col("period").is_between(pl.lit("2023-04"), pl.lit("2024-03"))).select("indicator", "partner", "period", "usd")
    j = a.join(b, on=["indicator", "partner", "period"], how="full", coalesce=True, suffix="_b")
    diff = j.filter(pl.col("usd").is_null() | pl.col("usd_b").is_null() | (pl.col("usd") != pl.col("usd_b")))
    if diff.height:
        raise ValueError(f"{F_MONTHLY} and {F_ATTRS} disagree on {diff.height} FY 2023-24 observations: {diff.head(5)}")

    first_m, last_m = monthly["period"].min(), monthly["period"].max()
    prov_m = {
        ind: ctx.prov(
            raw=raw_m,
            table_id=DATAFLOW,
            locator=f"SDMX-CSV rows COUNTRY=IND, INDICATOR={ind}, FREQUENCY=M, every COUNTERPART_COUNTRY, "
            f"TIME_PERIOD {first_m}..{last_m}; column OBS_VALUE",
            unit_as_published="US$ (units)",
            conversion=CONV_USD_UNITS,
            price_basis="current",
            vintage=vintage,
            release=RELEASE,
            notes=notes,
        )
        for ind in INDICATORS
    }
    first_a, last_a = annual["period"].min(), annual["period"].max()
    prov_a = {
        ind: ctx.prov(
            raw=raw_a,
            table_id=DATAFLOW,
            locator=f"SDMX-CSV rows COUNTRY=IND, INDICATOR={ind}, FREQUENCY=A (calendar years), every "
            f"COUNTERPART_COUNTRY, TIME_PERIOD {first_a}..{last_a}; column OBS_VALUE",
            unit_as_published="US$ (units)",
            conversion=CONV_USD_UNITS,
            price_basis="current",
            vintage=vintage,
            release=RELEASE,
            notes=notes,
        )
        for ind in INDICATORS
    }
    monthly_df = _rows(monthly, names, period_type="month", prov=prov_m, vintage=vintage, status="official")
    annual_df = _rows(annual, names, period_type="cy", prov=prov_a, vintage=vintage, status="official")

    complete, incomplete = fy_sums(monthly.rename({"usd": "value"}), ["indicator", "partner"])
    prov_fy = {
        ind: ctx.prov(
            raw=raw_m,
            table_id=DATAFLOW,
            locator=f"sums of the monthly rows of {F_MONTHLY} (INDICATOR={ind}), April..March",
            unit_as_published="US$ (units)",
            conversion=CONV_USD_UNITS,
            price_basis="current",
            vintage=vintage,
            release=RELEASE,
            status="derived",
            method=(
                "Indian fiscal year (April-March) = sum of the 12 monthly IMTS values April of year t to March "
                "of t+1 for each partner. Emitted only when all 12 months are published; a partner-year with "
                "a missing month is not summed (a missing month is not assumed to be zero) and is listed in "
                "docs/phase1/issues/trade_satellites.md."
            ),
            inputs=[prov_m[ind]],
            notes=notes,
        )
        for ind in INDICATORS
    }
    fy_df = _rows(
        complete.select("indicator", "partner", pl.col("fy").alias("period"), "value"),
        names,
        period_type="fy",
        prov=prov_fy,
        vintage=vintage,
        status="derived",
        value_col="value",
    )
    dropped = incomplete.filter(pl.col("fy") == "2023-24")
    ctx.log(
        f"IMTS FY: {complete.height} complete partner-years; {incomplete.height} partner-years with <12 months "
        f"not summed ({dropped.height} in FY 2023-24, US$ {dropped['value'].sum() / 1e6:,.1f} mn)"
    )
    return [
        Dataset(
            f"{UNIT}_imf_imts_monthly",
            monthly_df,
            f"IMF IMTS: India goods exports FOB / imports CIF by partner, monthly {first_m}..{last_m}, US$ mn",
        ),
        Dataset(
            f"{UNIT}_imf_imts_fy",
            fy_df,
            "IMF IMTS: India goods exports FOB / imports CIF by partner, Indian fiscal years summed from "
            "complete monthly data (derived), US$ mn",
        ),
        Dataset(
            f"{UNIT}_imf_imts_annual",
            annual_df,
            f"IMF IMTS: India goods exports FOB / imports CIF by partner, calendar years {first_a}..{last_a}, US$ mn",
        ),
    ]
