"""OECD-WTO Balanced Trade in Services (BaTIS, BPM6 / EBOPS 2010), India as reporter.

Files (OECD SDMX REST, keyless; only the all-wildcard key `IND........` works, partial keys give
HTTP 500 per the registry):
- the dataflow with its codelists (partner and EBOPS names; the edition, read from the bulk-file
  name in the EXT_RESOURCE annotation, e.g. 'December2025' -> vintage 2025-12);
- India, calendar years 2023-2024 (every partner x EBOPS item x measure);
- India, calendar years 2005-2022 (history).

BaTIS publishes three measures (ADJUSTMENT): N 'Reported' (India's own figures; partner World
only), F 'Adjusted and/or imputed' and B 'Balanced' (exports = mirror imports). N rows are
`official`; F and B rows are OECD-WTO model estimates and are ingested as `estimated`, unchanged.
The balanced World total for India is far below India's reported total (2023 exports: B 223.3 bn
vs N 337.5 bn US$), so B is only usable as partner *shares*: see the issues file.

Calendar years only: BaTIS has no fiscal-year data. The FY 2023-24 weighting (0.75 x 2023 +
0.25 x 2024, gap map S2) is a Phase 2 estimate and is not done here.
"""

from __future__ import annotations

import re
from typing import Any

import polars as pl
from lxml import etree

from pipeline.core.unit import BuildContext, Dataset, FetchContext, RawFile
from pipeline.core.units import clean_label

from ._common import UNIT, partner_dims, sid

SRC = "oecd_wto_batis"
BASE = "https://sdmx.oecd.org/public/rest"
FLOW_REF = "OECD.SDD.TPS,DSD_BATIS@DF_BATIS,1.0"
DATAFLOW = "OECD.SDD.TPS:DSD_BATIS@DF_BATIS(1.0)"
Q = "dimensionAtObservation=AllDimensions&format=csvfile"
F_STRUCT = "batis_dataflow.xml"
F_REF = "batis_ind_2023_2024.csv"
F_HIST = "batis_ind_2005_2022.csv"
FILES = {
    F_STRUCT: f"{BASE}/dataflow/OECD.SDD.TPS/DSD_BATIS@DF_BATIS/1.0?references=all",
    F_REF: f"{BASE}/data/{FLOW_REF}/IND........?startPeriod=2023&endPeriod=2024&{Q}",
    F_HIST: f"{BASE}/data/{FLOW_REF}/IND........?startPeriod=2005&endPeriod=2022&{Q}",
}
FLOWS = {"X": ("exports", "Exports"), "M": ("imports", "Imports")}
MEASURES = {
    "B": ("balanced", "Balanced", "estimated"),
    "F": ("adjusted_imputed", "Adjusted and/or imputed", "estimated"),
    "N": ("reported", "Reported", "official"),
}
WORLD = "W"
COLS = (
    "DATAFLOW",
    "REF_AREA",
    "COUNTERPART_AREA",
    "TRADE_FLOW",
    "PRODUCT_TYPE",
    "SERVICE",
    "FREQ",
    "UNIT_MEASURE",
    "ADJUSTMENT",
    "TIME_PERIOD",
    "OBS_VALUE",
    "OBS_STATUS",
    "METHODOLOGY_TYPE",
    "UNIT_MULT",
    "CURRENCY",
)
MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
     "November", "December"], start=1)}
METHOD = (
    "OECD-WTO BaTIS model values, as published and not changed by this unit. 'Adjusted and/or imputed' adds "
    "OECD-WTO adjustments and gap-filling estimates to reported data; 'Balanced' reconciles each bilateral flow "
    "with its mirror (symmetry-index weighted average of reported and mirror values). Methodology: 'The OECD-WTO "
    "Balanced Trade in Services (BaTIS)', https://doi.org/10.1787/c321a7a7-en"
)


def fetch(ctx: FetchContext) -> None:
    for name, url in FILES.items():
        ctx.fetch(SRC, url, name=name, expect="xml" if name.endswith(".xml") else "csv")


# ---------------------------------------------------------------------------------------------
# structure: names and edition
# ---------------------------------------------------------------------------------------------

_NS = {
    "str": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure",
    "com": "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common",
}
_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def _structure(raw: RawFile) -> tuple[dict[str, str], dict[str, str], str, str]:
    """(area names, EBOPS item names, vintage 'YYYY-MM', edition text)."""
    tree = etree.parse(str(raw.path))
    lists: dict[str, dict[str, str]] = {}
    for cl in tree.iterfind(".//str:Codelist", _NS):
        names = {}
        for c in cl.findall("str:Code", _NS):
            en = [n.text for n in c.findall("com:Name", _NS) if n.get(_LANG) == "en"]
            if en:
                names[c.get("id")] = clean_label(en[0])
        lists[cl.get("id")] = names
    for need in ("CL_AREA", "CL_BOP6_ITEM"):
        if need not in lists:
            raise ValueError(f"{raw.name}: codelist {need} missing")
    flows = [f for f in tree.iterfind(".//str:Dataflow", _NS) if f.get("id") == "DSD_BATIS@DF_BATIS"]
    if len(flows) != 1:
        raise ValueError(f"{raw.name}: dataflow DSD_BATIS@DF_BATIS not found")
    texts = [t.text or "" for t in flows[0].iterfind(".//com:AnnotationText", _NS)]
    hits = sorted({m.groups() for t in texts for m in re.finditer(r"BATIS_BPM6_([A-Za-z]+)(\d{4})_bulk", t)})
    if len(hits) != 1 or hits[0][0] not in MONTHS:
        raise ValueError(f"{raw.name}: cannot read the BaTIS edition from the bulk-download annotation: {hits}")
    month, year = hits[0]
    return lists["CL_AREA"], lists["CL_BOP6_ITEM"], f"{year}-{MONTHS[month]:02d}", f"{month} {year}"


# ---------------------------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------------------------


def _read(raw: RawFile, years: tuple[int, int]) -> pl.DataFrame:
    df = pl.read_csv(raw.path, infer_schema_length=0)
    missing = [c for c in COLS if c not in df.columns]
    if missing:
        raise ValueError(f"{raw.name}: columns missing: {missing}")
    fixed = {
        "DATAFLOW": DATAFLOW,
        "REF_AREA": "IND",
        "PRODUCT_TYPE": "S",
        "FREQ": "A",
        "UNIT_MEASURE": "USD_EXC",
        "UNIT_MULT": "6",
        "CURRENCY": "USD",
    }
    for col, want in fixed.items():
        got = set(df[col].unique().to_list())
        if got != {want}:
            raise ValueError(f"{raw.name}: {col} is {sorted(map(str, got))}, expected {want!r}")
    for col, allowed in (("TRADE_FLOW", FLOWS), ("ADJUSTMENT", MEASURES)):
        got = set(df[col].unique().to_list())
        if not got <= set(allowed):
            raise ValueError(f"{raw.name}: unexpected {col} values {sorted(got - set(allowed))}")
    yrs = df["TIME_PERIOD"].cast(pl.Int32)
    if yrs.min() != years[0] or yrs.max() != years[1]:
        raise ValueError(f"{raw.name}: years {yrs.min()}..{yrs.max()}, expected {years[0]}..{years[1]}")
    if df.filter(pl.col("OBS_VALUE").is_null()).height:
        raise ValueError(f"{raw.name}: empty OBS_VALUE cells")
    df = df.with_columns(pl.col("OBS_VALUE").cast(pl.Float64))
    if df.filter(pl.col("OBS_VALUE") < 0).height:
        raise ValueError(f"{raw.name}: negative values (BaTIS flows are gross, non-negative)")
    key = ["COUNTERPART_AREA", "TRADE_FLOW", "SERVICE", "ADJUSTMENT", "TIME_PERIOD"]
    if df.select(key).is_duplicated().any():
        raise ValueError(f"{raw.name}: duplicate observations")
    return df


def _rows(
    df: pl.DataFrame, areas: dict[str, str], items: dict[str, str], prov: dict[str, str], vintage: str
) -> pl.DataFrame:
    unknown = sorted(set(df["COUNTERPART_AREA"].unique().to_list()) - set(areas)) + sorted(
        set(df["SERVICE"].unique().to_list()) - set(items)
    )
    if unknown:
        raise ValueError(f"BaTIS: codes without a name in the dataflow codelists: {unknown}")
    rows: list[dict[str, Any]] = []
    for area, flow, svc, adj, year, v in df.select(
        "COUNTERPART_AREA", "TRADE_FLOW", "SERVICE", "ADJUSTMENT", "TIME_PERIOD", "OBS_VALUE"
    ).iter_rows():
        fcode, flabel = FLOWS[flow]
        mcode, mlabel, status = MEASURES[adj]
        dims = partner_dims(area)
        other = f"batis_measure={mcode}" + (f";{dims['dim_other']}" if dims["dim_other"] else "")
        rows.append(
            {
                "series_id": f"batis.{fcode}.{sid(svc)}.{sid(area)}.{mcode}.current",
                "source_id": SRC,
                "table_id": DATAFLOW,
                "item_code": fcode,
                "item_label": f"{flabel} | {svc} {items[svc]} | partner: {areas[area]} ({area}) | {mlabel}",
                "product": svc,
                "geography": dims["geography"],
                "dim_other": other,
                "stock_flow": "flow",
                "period": year,
                "period_type": "cy",
                "value": v,
                "unit": "USD_million",
                "price_basis": "current",
                "vintage": vintage,
                "estimate_stage": "n.a.",
                "status": status,
                "prov_id": prov[adj],
            }
        )
    return pl.DataFrame(rows, infer_schema_length=None).sort("series_id", "period")


def _provs(ctx: BuildContext, raw: RawFile, df: pl.DataFrame, vintage: str, edition: str, subset: str) -> dict[str, str]:
    out = {}
    for adj in sorted(df["ADJUSTMENT"].unique().to_list()):
        mcode, mlabel, status = MEASURES[adj]
        sub = df.filter(pl.col("ADJUSTMENT") == adj)
        meth = sub.group_by("METHODOLOGY_TYPE", "OBS_STATUS", maintain_order=True).len().sort("METHODOLOGY_TYPE", "OBS_STATUS", nulls_last=True)
        flags = ", ".join(f"{m or '-'}/{s}={n}" for m, s, n in meth.iter_rows())
        out[adj] = ctx.prov(
            raw=raw,
            table_id=DATAFLOW,
            locator=f"SDMX-CSV rows ADJUSTMENT={adj} ({mlabel}), REF_AREA=IND, {subset}, TIME_PERIOD "
            f"{sub['TIME_PERIOD'].min()}..{sub['TIME_PERIOD'].max()}; column OBS_VALUE",
            unit_as_published="US$ million (UNIT_MEASURE USD_EXC, UNIT_MULT 6)",
            conversion="none",
            price_basis="current",
            vintage=vintage,
            release=f"OECD-WTO BaTIS (BPM6), {edition} edition (bulk file name), OECD Data Explorer SDMX API",
            status=status,
            method=None if status == "official" else METHOD,
            notes=f"Calendar years. METHODOLOGY_TYPE/OBS_STATUS counts: {flags} (ME model estimate, AG aggregation, "
            "IE interpolation/extrapolation, AD adjustment; OBS_STATUS I = imputed, A = normal). Licence: OECD terms "
            "(reuse with credit).",
        )
    return out


def build(ctx: BuildContext) -> list[Dataset]:
    areas, items, vintage, edition = _structure(ctx.raw(SRC, F_STRUCT))
    raw_ref, raw_hist = ctx.raw(SRC, F_REF), ctx.raw(SRC, F_HIST)
    ref = _read(raw_ref, (2023, 2024))
    hist = _read(raw_hist, (2005, 2022))
    hist = hist.filter((pl.col("SERVICE") == "S") | (pl.col("COUNTERPART_AREA") == WORLD))
    ref_df = _rows(ref, areas, items, _provs(ctx, raw_ref, ref, vintage, edition, "every partner x EBOPS item"), vintage)
    hist_df = _rows(
        hist,
        areas,
        items,
        _provs(ctx, raw_hist, hist, vintage, edition, "SERVICE=S for every partner, plus every SERVICE for partner W"),
        vintage,
    )
    return [
        Dataset(
            f"{UNIT}_batis_2023_2024",
            ref_df,
            "OECD-WTO BaTIS: India services exports/imports by partner x EBOPS 2010 item, balanced / adjusted / "
            "reported measures, calendar 2023 and 2024, US$ mn",
        ),
        Dataset(
            f"{UNIT}_batis_history",
            hist_df,
            "OECD-WTO BaTIS: India total services by partner, and World by EBOPS item, all measures, calendar "
            "2005-2022, US$ mn",
        ),
    ]
