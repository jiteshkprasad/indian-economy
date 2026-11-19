"""CPI (base 2024=100) weights, derived from HCES 2023-24: Expert Group report Annexure 5.3
(5.3a division, 5.3b group, 5.3c State x sector, 5.3d State x sector x item with COICOP 2018 codes).

5.3d has no All-India item rows, so All-India item weights (rural, urban) are derived as the sum of the
States' 'share in All India' (status derived). These weights are the HCES item -> CPI item -> COICOP
bridge that the P7a/P7b GST-rate prior needs.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import polars as pl

from pipeline.core.unit import BuildContext, Dataset
from pipeline.core.units import clean_label, parse_number

from ._common import UNIT, expect_text, geo_slug, sheet_rows, state_geo

SRC = "mospi_cpi_2024base"
FILE = "cpi2024_annex_5_3_weights.xlsx"
URL = "https://www.mospi.gov.in/uploads/documents/documents/1769670019171-Annex_5.3.xlsx"
REPORT_URL = "https://www.mospi.gov.in/uploads/documents/documents/1769670534541-Export_report_CPI.pdf"
PR_URL = ("https://www.mospi.gov.in/uploads/latestReleases/latest_release_1770891893893_6b458c0a-c327-4fef-a554-"
          "41131ea67273_Press_Relase_of_CPI_for_Jan26.pdf")
VINTAGE = "2026-01-29"  # file Last-Modified; linked from the Expert Group report and the 12 Feb 2026 press release
RELEASE = ("Report of the Expert Group on Comprehensive Updation of CPI (base 2024=100), Annexure 5.3 weights "
           "(NSO, MoSPI, Jan 2026)")
NOTE = (
    "Weights of CPI 2024=100 (weight reference period HCES 2023-24, survey Aug 2023-Jul 2024; price reference "
    "period calendar 2024); period '2024' is the index base year. Percent of the All-India CPI basket unless the "
    "series says 'share within state'. Values are stored rounded to 6 decimals, so the smallest State x item "
    "shares (below ~0.0005%) lose relative precision."
)
SECTOR = {"1": "rural", "2": "urban"}


def _base() -> dict[str, Any]:
    return {"source_id": SRC, "vintage": VINTAGE, "estimate_stage": "n.a.", "period": "2024", "period_type": "cy",
            "stock_flow": "n/a", "unit": "percent", "price_basis": "n/a"}


def build_cpi_weights(ctx: BuildContext) -> Dataset:
    raw = ctx.raw(SRC, FILE)
    rows: list[dict[str, Any]] = []

    def prov(sheet: str, loc: str, status: str = "official", method: str | None = None,
             inputs: tuple[str, ...] = ()) -> str:
        return ctx.prov(raw=raw, table_id=f"Annexure {sheet}", locator=loc, unit_as_published="percent (weight)",
                        conversion="none", price_basis="n/a", vintage=VINTAGE, release=RELEASE, notes=NOTE,
                        status=status, method=method, inputs=inputs)

    # ---- 5.3d items ------------------------------------------------------------------------
    title, r = sheet_rows(raw.path, "5.3d")
    where = "CPI Annexure 5.3d"
    expect_text(r, 2, 1, "All India and State wise item level weights", where)
    heads = ["State", "State Name", "Sector", "Item Name", "Item Code", "Subclass Code", "Subclass Name", "Class Code",
             "Class Name", "Group Code", "Group Name", "Division Code", "Division Name", "Share in All India",
             "Share within State"]
    for c, h in enumerate(heads, start=1):
        expect_text(r, 4, c, h, where)
    div_names: dict[str, str] = {}
    items: list[tuple[int, str, str, str, str, str, float, float]] = []
    last = 5
    for i in range(5, len(r) + 1):
        row = r[i - 1]
        if row[0] is None:
            if row[4] is not None:
                raise ValueError(f"{where}: row {i} has an item code but no State")
            continue
        geo = state_geo(row[1])
        sec = SECTOR[str(row[2]).strip()]
        code = clean_label(str(row[4]))
        a, s = parse_number(row[13]), parse_number(row[14])
        if a is None or s is None:
            raise ValueError(f"{where}: row {i} blank share")
        div_names[clean_label(str(row[12]))] = clean_label(str(row[11]))
        items.append((i, geo, sec, code, clean_label(str(row[3])), clean_label(str(row[9])), a, s))
        last = i
    tot = sum(x[6] for x in items)
    if abs(tot - 100.0) > 1e-6:
        raise ValueError(f"{where}: shares in All India sum to {tot}, not 100")
    per_state: dict[str, float] = defaultdict(float)
    for x in items:
        per_state[x[1]] += x[7]
    off = {g: v for g, v in per_state.items() if abs(v - 100.0) > 1e-6}
    if off:
        raise ValueError(f"{where}: shares within State do not sum to 100 for {off}")
    labels: dict[str, str] = {}
    for x in items:
        if labels.setdefault(x[3], x[4]) != x[4]:
            raise ValueError(f"{where}: item {x[3]} has two names {labels[x[3]]!r} / {x[4]!r}")
    loc = f"sheet '{title}', rows 5-{last}; rows matched by State code/name (A:B), sector (C) and item code (E)"
    p_all = prov("5.3d", f"{loc}; col N (share in All India)")
    p_st = prov("5.3d", f"{loc}; col O (share within State: percent of the State's combined rural + urban basket; "
                "a State's rural and urban rows together sum to 100)")
    for _, geo, sec, code, name, _, a, s in items:
        common = {**_base(), "table_id": "Annexure 5.3d", "item_label": name, "product": f"coicop2018:{code}",
                  "geography": geo, "household_group": f"{sec}_all", "status": "official"}
        rows.append({**common, "series_id": f"w5_3d.{code}.{geo_slug(geo)}.{sec}.share_all_india",
                     "item_code": "weight_share_all_india", "value": a, "prov_id": p_all,
                     "dim_other": "share_of=all_india_combined_basket"})
        # col O is a share of the State's COMBINED rural + urban basket: a State's rows sum to 100 over both
        # sectors together (checked above), not within each sector.
        rows.append({**common, "series_id": f"w5_3d.{code}.{geo_slug(geo)}.{sec}.share_within_state",
                     "item_code": "weight_share_within_state", "value": s, "prov_id": p_st,
                     "dim_other": "share_of=state_combined_rural_urban_basket"})
    # derived All-India item weights
    p_der = prov("5.3d", f"{loc}; col N summed over States", status="derived",
                 method="All-India item weight (rural or urban) = sum over the 36 States/UTs of col N 'Share in All "
                 "India' for that item and sector (5.3d has no All-India item rows).", inputs=(p_all,))
    agg: dict[tuple[str, str], float] = defaultdict(float)
    for x in items:
        agg[(x[3], x[2])] += x[6]
    for (code, sec), v in sorted(agg.items()):
        rows.append({**_base(), "series_id": f"w5_3d.{code}.in.{sec}.share_all_india", "table_id": "Annexure 5.3d",
                     "item_code": "weight_share_all_india", "item_label": labels[code],
                     "product": f"coicop2018:{code}", "geography": "IN", "household_group": f"{sec}_all",
                     "value": v, "status": "derived", "prov_id": p_der,
                     # the same kind of share as the official col N rows it sums (verifier finding verify-6)
                     "dim_other": "share_of=all_india_combined_basket"})

    # ---- 5.3a divisions --------------------------------------------------------------------
    title, r = sheet_rows(raw.path, "5.3a")
    where = "CPI Annexure 5.3a"
    expect_text(r, 2, 1, "All India Division Wise Weights", where)
    hdr = next(i for i, row in enumerate(r, 1) if row[0] is not None and clean_label(str(row[0])) == "Division name")
    for c, h in ((2, "Rural"), (3, "Urban"), (4, "Combined")):
        expect_text(r, hdr, c, h, where)
    p = prov("5.3a", f"sheet '{title}', rows {hdr + 1}-{len(r)}, cols B:D; rows matched by division name")
    seen = 0
    for row in r[hdr:]:
        if row[0] is None:
            continue
        name = clean_label(str(row[0]))
        code = "total" if name == "Grand Total" else div_names.get(name)
        if code is None:
            raise ValueError(f"{where}: division {name!r} not in 5.3d")
        seen += 1
        for c, sec in ((1, "rural"), (2, "urban"), (3, "all")):
            rows.append({**_base(), "series_id": f"w5_3a.div_{code}.{sec}", "table_id": "Annexure 5.3a",
                         "item_code": "weight_share_all_india", "item_label": name,
                         "product": f"coicop2018:{code}" if code != "total" else None, "geography": "IN",
                         "household_group": f"{sec}_all" if sec != "all" else "all", "value": float(row[c]),
                         "status": "official", "prov_id": p})
    if seen != 13:
        raise ValueError(f"{where}: {seen} rows, expected 12 divisions + total")

    # ---- 5.3b groups -----------------------------------------------------------------------
    title, r = sheet_rows(raw.path, "5.3b")
    where = "CPI Annexure 5.3b"
    expect_text(r, 2, 1, "All India Group Wise Weights", where)
    hdr = next(i for i, row in enumerate(r, 1) if row[0] is not None and clean_label(str(row[0])) == "Group Code")
    for c, h in ((2, "Group Name"), (3, "Rural"), (4, "Urban"), (5, "Combined")):
        expect_text(r, hdr, c, h, where)
    p = prov("5.3b", f"sheet '{title}', rows {hdr + 1}-{len(r)}, cols C:E; rows matched by group code")
    for row in r[hdr:]:
        if row[1] is None:
            continue
        name = clean_label(str(row[1]))
        code = clean_label(str(row[0])) if row[0] is not None else ("total" if name == "Total" else None)
        if code is None:
            raise ValueError(f"{where}: row without group code: {row}")
        for c, sec in ((2, "rural"), (3, "urban"), (4, "all")):
            rows.append({**_base(), "series_id": f"w5_3b.grp_{code}.{sec}", "table_id": "Annexure 5.3b",
                         "item_code": "weight_share_all_india", "item_label": name,
                         "product": f"coicop2018:{code}" if code != "total" else None, "geography": "IN",
                         "household_group": f"{sec}_all" if sec != "all" else "all", "value": float(row[c]),
                         "status": "official", "prov_id": p})

    # ---- 5.3c States -----------------------------------------------------------------------
    title, r = sheet_rows(raw.path, "5.3c")
    where = "CPI Annexure 5.3c"
    expect_text(r, 3, 1, "State Wise Sector Wise Weights", where)
    hdr = next(i for i, row in enumerate(r, 1) if row[0] is not None and clean_label(str(row[0])) == "State Code")
    for c, h in ((2, "State name"), (3, "Rural"), (4, "Urban"), (5, "Combined")):
        expect_text(r, hdr, c, h, where)
    p = prov("5.3c", f"sheet '{title}', rows {hdr + 1}-{len(r)}, cols C:E; rows matched by State name")
    for row in r[hdr:]:
        if row[1] is None:
            continue
        geo = state_geo(row[1])
        for c, sec in ((2, "rural"), (3, "urban"), (4, "all")):
            if row[c] is None:
                continue  # Chandigarh has no rural CPI
            rows.append({**_base(), "series_id": f"w5_3c.{geo_slug(geo)}.{sec}", "table_id": "Annexure 5.3c",
                         "item_code": "weight_share_all_india", "item_label": f"CPI weight of {clean_label(str(row[1]))}",
                         "geography": geo, "household_group": f"{sec}_all" if sec != "all" else "all",
                         "value": float(row[c]), "status": "official", "prov_id": p})
    return Dataset(f"{UNIT}_cpi2024_weights", pl.DataFrame(rows),
                   "CPI 2024=100 weights from HCES 2023-24 (Annexure 5.3): division, group, State and State x item "
                   "(COICOP 2018) shares, plus derived All-India item weights. 'weight_share_within_state' is a share "
                   "of the State's COMBINED rural + urban CPI basket (sums to 100 over both sectors), not a "
                   "within-sector share")
