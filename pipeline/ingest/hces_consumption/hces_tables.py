"""HCES Appendix-A Excel tables: A2 (persons and MPCE by fractile), A6 (item groups by fractile),
A10F (items by fractile, All-India) and A10S / A10SW (items by State, without / with imputation).

Everything is parsed by label; every item code must be classified (leaf, subtotal, total, ...), and
the published sub-totals are re-added from their leaves inside build(), so a changed table fails
loudly instead of producing shifted numbers.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

import polars as pl

from pipeline.core.unit import BuildContext, Dataset
from pipeline.core.units import clean_label, parse_number, slug

from ._common import (
    FRACTILE_ORDER,
    ROUNDS,
    UNIT,
    col_letter,
    expect_text,
    first_row_with,
    fractile_code,
    geo_slug,
    sector_code,
    sheet_rows,
    state_geo,
    survey_note,
    sy_period,
)

NA = "n/a"


def _num(cell: Any) -> float | None:
    """A published number, or None for '##' (not collected), '-' (not estimated) and blanks."""
    if cell is None:
        return None
    if isinstance(cell, str) and cell.strip() in ("##", "#", "-", ""):
        return None
    return parse_number(cell)


def _rt(period: str) -> str:
    """Round tag in series ids: the two HCES rounds are different registry sources, so a series may
    not span both (SERIES_INVARIANTS); 'hces2324' / 'hces2223'."""
    return "hces" + period.replace("-", "")[2:]


def _base_row(period: str, src: str) -> dict[str, Any]:
    """`period` is the round key ('2023-24'); rows carry the survey window ('2023-08/2024-07', 'sy')."""
    r = ROUNDS[period]
    return {
        "source_id": src,
        "period": sy_period(period),
        "period_type": "sy",
        "vintage": r["vintage"],
        "estimate_stage": "n.a.",
    }


def _prov(ctx: BuildContext, raw: Any, period: str, table: str, locator: str, uap: str, conv: str, basis: str) -> str:
    r = ROUNDS[period]
    return ctx.prov(
        raw=raw,
        table_id=table,
        locator=locator,
        unit_as_published=uap,
        conversion=conv,
        price_basis=basis,
        vintage=r["vintage"],
        release=r["release"],
        notes=survey_note(period),
    )


# =============================================================================================
# Table A2: households, persons and average MPCE by State x sector x fractile class
# =============================================================================================

A2_COLS = {  # 1-based column -> (item_code, kind)
    4: ("households", "count00"),
    5: ("adults_male", "count00"),
    6: ("adults_female", "count00"),
    7: ("adults_persons", "count00"),
    8: ("children_male", "count00"),
    9: ("children_female", "count00"),
    10: ("children_persons", "count00"),
    11: ("avg_mpce", "inr"),
    12: ("sample_households", "sample"),
    13: ("sample_persons", "sample"),
}
A2_LABELS = {
    "households": "Estimated number of households",
    "adults_male": "Estimated number of adults (15 years or more): male (incl. transgender)",
    "adults_female": "Estimated number of adults (15 years or more): female",
    "adults_persons": "Estimated number of adults (15 years or more): persons",
    "children_male": "Estimated number of children (14 years or less): male (incl. transgender)",
    "children_female": "Estimated number of children (14 years or less): female",
    "children_persons": "Estimated number of children (14 years or less): persons",
    "avg_mpce": "Average MPCE (Rs.)",
    "sample_households": "Sample households",
    "sample_persons": "Sample persons",
    "persons": "Estimated number of persons (adults + children)",
}


def build_a2(ctx: BuildContext, period: str) -> list[dict[str, Any]]:
    rd = ROUNDS[period]
    src = rd["src"]
    raw = ctx.raw(src, rd["files"]["a2"][1])
    title, rows = sheet_rows(raw.path)
    where = f"{src} A2 {title}"
    expect_text(rows, 1, 1, "Table A2", where)
    expect_text(rows, 1, 1, "average MPCE for each fractile class", where)
    expect_text(rows, 2, 4, "Estimated no. (00)", where)
    expect_text(rows, 2, 11, "Average MPCE", where)
    expect_text(rows, 2, 12, "Sample households", where)
    expect_text(rows, 2, 13, "Sample persons", where)
    expect_text(rows, 3, 4, "Households", where)
    expect_text(rows, 3, 5, "Adults", where)
    expect_text(rows, 3, 8, "Children", where)
    for c, t in ((5, "Male"), (6, "Female"), (7, "Persons"), (8, "Male"), (9, "Female"), (10, "Persons")):
        expect_text(rows, 4, c, t, where)
    first = first_row_with(rows, 1, "(1)") + 1
    sector = state = None
    cells: list[tuple[int, str, str, str, dict[str, float]]] = []
    last = first
    for i in range(first, len(rows) + 1):
        r = rows[i - 1]
        if r[0] is not None and clean_label(str(r[0])).lower().startswith("note"):
            break
        if r[0] is not None:
            sector = sector_code(r[0])
        if r[1] is not None:
            state = state_geo(r[1])
        if r[2] is None:
            if any(v is not None for v in r[3:13]):
                raise ValueError(f"{where}: row {i} has numbers but no fractile label")
            continue
        lab = clean_label(str(r[2]))
        if lab.lower().startswith("sample no. of hhs"):
            continue  # sample counts by gender: survey design, not estimates (logged in issues)
        fr = fractile_code(lab)
        vals: dict[str, float] = {}
        for c, (code, _) in A2_COLS.items():
            v = _num(r[c - 1])
            if v is None:
                raise ValueError(f"{where}: blank cell {col_letter(c)}{i} ({code})")
            vals[code] = v
        assert sector is not None and state is not None
        cells.append((i, sector, state, fr, vals))
        last = i
    # completeness: 13 classes for each State x sector (Chandigarh etc. may lack rural)
    seen: dict[tuple[str, str], list[str]] = defaultdict(list)
    for _, s, g, fr, _ in cells:
        seen[(g, s)].append(fr)
    for k, frs in seen.items():
        if frs != FRACTILE_ORDER:
            raise ValueError(f"{where}: fractile classes for {k} are {frs}, expected {FRACTILE_ORDER}")
    if ("IN", "rural") not in seen or ("IN", "urban") not in seen:
        raise ValueError(f"{where}: All-India block missing")

    loc = f"sheet '{title}', rows {first}-{last}; rows matched by sector (col A), State/UT (col B) and fractile class (col C)"
    p_cnt = _prov(ctx, raw, period, "Table A2", f"{loc}; cols D:J (estimated number, in hundreds)",
                  "number (00)", "x 100 (hundreds -> count)", NA)
    p_smp = _prov(ctx, raw, period, "Table A2", f"{loc}; cols L:M (sample households, sample persons)",
                  "number", "none", NA)
    p_inr = _prov(ctx, raw, period, "Table A2", f"{loc}; col K (average MPCE)",
                  "Rs. per person per 30 days", "none", "current")
    p_der = ctx.prov(
        raw=raw, table_id="Table A2", locator=f"{loc}; cols G and J", unit_as_published="number (00)",
        conversion="x 100 (hundreds -> count)", price_basis=NA, vintage=rd["vintage"], release=rd["release"],
        status="derived", method="persons = adults persons (col 7) + children persons (col 10), both x 100",
        inputs=(p_cnt,), notes=survey_note(period),
    )
    out: list[dict[str, Any]] = []
    for _, sector, geo, fr, vals in cells:
        hg = f"{sector}_{fr}"
        items = [(code, vals[code]) for code in (v[0] for v in A2_COLS.values())]
        items.append(("persons", vals["adults_persons"] + vals["children_persons"]))
        for code, v in items:
            kind = "derived" if code == "persons" else next(k for c, (cc, k) in A2_COLS.items() if cc == code)
            if kind in ("count00", "derived"):
                val, unit, pid, sf = v * 100.0, "count", (p_der if kind == "derived" else p_cnt), "stock"
            elif kind == "sample":
                val, unit, pid, sf = v, "count", p_smp, "stock"
            else:
                val, unit, pid, sf = v, "INR", p_inr, "flow"
            basis = "current" if unit == "INR" else NA
            out.append({
                **_base_row(period, rd["src"]),
                "series_id": f"a2.{_rt(period)}.{code}.{geo_slug(geo)}.{hg}" + (".current" if unit == "INR" else ""),
                "table_id": "Table A2",
                "item_code": code,
                "item_label": A2_LABELS[code],
                "geography": geo,
                "household_group": hg,
                "stock_flow": sf,
                "value": val,
                "unit": unit,
                "price_basis": basis,
                "status": "derived" if kind == "derived" else "official",
                "prov_id": pid,
            })
    return out


def build_a2_dataset(ctx: BuildContext) -> Dataset:
    rows = build_a2(ctx, "2023-24") + build_a2(ctx, "2022-23")
    return Dataset(
        f"{UNIT}_a2_fractile_persons",
        pl.DataFrame(rows),
        "HCES 2022-23 and 2023-24 Table A2: households, persons and average MPCE by State x R/U x 12 MPCE "
        "fractile classes (survey years Aug-Jul: period 2023-08/2024-07 and 2022-08/2023-07, type sy)",
    )


# =============================================================================================
# Table A6: broad item groups x fractile class
# =============================================================================================

# label -> (code, role)
A6_ITEMS: dict[str, tuple[str, str]] = {
    "Cereal": ("cereal", "leaf"),
    "Gram": ("gram", "leaf"),
    "Cereal substitutes": ("cereal_substitutes", "leaf"),
    "Pulses & pulse products": ("pulses", "leaf"),
    "Sugar": ("sugar", "leaf"),
    "Salt": ("salt", "leaf"),
    "Milk and milk products": ("milk", "leaf"),
    "Vegetables": ("vegetables", "leaf"),
    "Fruits(fresh)": ("fruits_fresh", "leaf"),
    "Fruits(dry)": ("fruits_dry", "leaf"),
    "Egg, fish & meat": ("egg_fish_meat", "leaf"),
    "Edible oil": ("edible_oil", "leaf"),
    "Spices": ("spices", "leaf"),
    "Beverages": ("beverages", "leaf"),
    "Processed food, etc.": ("processed_food", "leaf"),
    "Beverages, Processed food, etc.": ("beverages_processed_food", "subtotal"),
    "Food: Total": ("food_total", "total"),
    "Pan": ("pan", "leaf"),
    "Tobacco": ("tobacco", "leaf"),
    "Intoxicants": ("intoxicants", "leaf"),
    "Pan, Tobacco & Intoxicants": ("pan_tobacco_intoxicants", "subtotal"),
    "Fuel and light": ("fuel_light", "leaf"),
    "Toilet articles": ("toilet_articles", "leaf"),
    "Other household consumables": ("other_hh_consumables", "leaf"),
    "Education": ("education", "leaf"),
    "Medical (Hospitalization)": ("medical_hosp", "leaf"),
    "Medical (Non-Hospitalization)": ("medical_nonhosp", "leaf"),
    "Conveyance": ("conveyance", "leaf"),
    "Consumer services excluding conveyance": ("consumer_services", "leaf"),
    "Entertainment": ("entertainment", "leaf"),
    "Rent": ("rent", "leaf"),
    "Other taxes & cesses": ("taxes_cesses", "leaf"),
    "Clothing & bedding": ("clothing_bedding", "leaf"),
    "Footwear": ("footwear", "leaf"),
    "Durable goods": ("durables", "leaf"),
    "Non-food Total": ("nonfood_total", "total"),
    "Total Expenditure": ("total_expenditure", "total"),
    # memo items printed below the total (not part of it)
    "Cooked meals recd. free in workplace": ("memo_meals_free_workplace", "memo"),
    "Cooked meals recd. as assistance": ("memo_meals_assistance", "memo"),
    "Clothing & footwear(2nd hand)": ("memo_clothing_footwear_2nd_hand", "memo"),
    "Books journals(2nd hand)": ("memo_books_2nd_hand", "memo"),
    "Durable goods (2nd hand)": ("memo_durables_2nd_hand", "memo"),
    "Imputed rent": ("memo_imputed_rent", "memo"),
}
A6_SKIP = ("estimated no. of household", "estimated no. of hhs", "sample no. of household", "sample no. of hhs")
A6_FOOD = ["cereal", "gram", "cereal_substitutes", "pulses", "sugar", "salt", "milk", "vegetables", "fruits_fresh",
           "fruits_dry", "egg_fish_meat", "edible_oil", "spices", "beverages", "processed_food"]
A6_NONFOOD = ["pan", "tobacco", "intoxicants", "fuel_light", "toilet_articles", "other_hh_consumables", "education",
              "medical_hosp", "medical_nonhosp", "conveyance", "consumer_services", "entertainment", "rent",
              "taxes_cesses", "clothing_bedding", "footwear", "durables"]
A6_IDENTITIES = {
    "beverages_processed_food": ["beverages", "processed_food"],
    "pan_tobacco_intoxicants": ["pan", "tobacco", "intoxicants"],
    "food_total": A6_FOOD,
    "nonfood_total": A6_NONFOOD,
    "total_expenditure": ["food_total", "nonfood_total"],
}
A6_TOL_PER_PART = 0.006  # values are rounded to 0.01 Rs
# Published totals that do not re-add from their published parts beyond rounding (a publisher
# inconsistency, logged in docs/phase1/issues/hces_consumption.md): (period, geo, household_group,
# total) -> largest accepted |difference| in Rs.
A6_KNOWN_BREAKS: dict[tuple[str, str, str, str], float] = {
    # Food 1,938.50 + non-food 2,183.38 = 4,121.88, printed total 4,121.78 (Table A2: 4,121.79)
    ("2023-24", "IN", "rural_all", "total_expenditure"): 0.11,
}


def build_a6(ctx: BuildContext, period: str, a2_households: dict[tuple[str, str], float]) -> list[dict[str, Any]]:
    rd = ROUNDS[period]
    src = rd["src"]
    raw = ctx.raw(src, rd["files"]["a6"][1])
    title, rows = sheet_rows(raw.path)
    where = f"{src} A6 {title}"
    expect_text(rows, 1, 1, "Table A6", where)
    expect_text(rows, 1, 1, "per person for a period of 30 days for each fractile class", where)
    expect_text(rows, 2, 3, "Item description", where)
    frac_cols = {}
    for c in range(4, 17):
        frac_cols[c] = fractile_code(rows[2][c - 1])
    if list(frac_cols.values()) != FRACTILE_ORDER:
        raise ValueError(f"{where}: unexpected fractile header {list(frac_cols.values())}")
    first = first_row_with(rows, 1, "(1)") + 1
    sector = geo = None
    data: dict[tuple[str, str], dict[str, dict[str, float]]] = defaultdict(dict)
    labels: dict[str, str] = {}
    last = first
    for i in range(first, len(rows) + 1):
        r = rows[i - 1]
        if r[0] is not None and clean_label(str(r[0])).lower().startswith("note"):
            break
        if r[0] is not None:
            sector = sector_code(r[0])
        if r[1] is not None:
            geo = state_geo(r[1])
        if r[2] is None:
            continue
        lab = clean_label(str(r[2]))
        assert sector is not None and geo is not None
        if lab.lower().startswith(A6_SKIP):
            if lab.lower().startswith("estimated"):
                # cross-check: households per fractile must equal Table A2 col 4
                for c, fr in frac_cols.items():
                    v = _num(r[c - 1])
                    want = a2_households.get((geo, f"{sector}_{fr}"))
                    if v is None or want is None or abs(v * 100 - want) > 0.5:
                        raise ValueError(f"{where}: row {i} households {v} != Table A2 {want} for {geo} {sector} {fr}")
            continue
        if lab not in A6_ITEMS:
            raise ValueError(f"{where}: row {i}: unmapped item group {lab!r}")
        code, _ = A6_ITEMS[lab]
        labels[code] = lab
        vals = {}
        for c, fr in frac_cols.items():
            v = _num(r[c - 1])
            if v is None:
                raise ValueError(f"{where}: blank value {col_letter(c)}{i} for {code}")
            vals[fr] = v
        if code in data[(geo, sector)]:
            raise ValueError(f"{where}: duplicate {code} for {geo} {sector}")
        data[(geo, sector)][code] = vals
        last = i
    # A group nobody in the State consumed is not printed (e.g. cereal substitutes in Assam): it
    # counts as zero in the identities and gets no row. Totals and sub-totals must always be there.
    required = {c for c, rl in A6_ITEMS.values() if rl in ("total", "subtotal")}
    missing = [(k, sorted(required - set(v))) for k, v in data.items() if not required <= set(v)]
    if missing:
        raise ValueError(f"{where}: totals missing in {missing[:3]}")
    n_absent = sum(len({c for c, _ in A6_ITEMS.values()} - set(v)) for v in data.values())
    ctx.log(f"{where}: {n_absent} State x sector x group lines not printed (zero consumption), no rows emitted")
    zero = dict.fromkeys(FRACTILE_ORDER, 0.0)
    # identities (published totals re-added from their parts)
    bad = []
    for (geo, sector), items in data.items():
        for tot, parts in A6_IDENTITIES.items():
            for fr in FRACTILE_ORDER:
                s = sum(items.get(p, zero)[fr] for p in parts)
                diff = abs(s - items[tot][fr])
                known = A6_KNOWN_BREAKS.get((period, geo, f"{sector}_{fr}", tot))
                if known is not None:
                    if diff > known:
                        bad.append((geo, sector, fr, tot, items[tot][fr], round(s, 2)))
                    else:
                        ctx.warn(f"{where}: known publisher break {geo} {sector} {fr} {tot}: printed "
                                 f"{items[tot][fr]} vs parts {s:.2f} (logged)")
                elif diff > 0.02 + A6_TOL_PER_PART * len(parts):
                    bad.append((geo, sector, fr, tot, items[tot][fr], round(s, 2)))
    if bad:
        raise ValueError(f"{where}: {len(bad)} group totals do not add up, e.g. {bad[:5]}")
    pid = _prov(ctx, raw, period, "Table A6",
                f"sheet '{title}', rows {first}-{last}, cols D:P (12 fractile classes and 'All Classes'); rows matched "
                "by sector (col A), State/UT (col B) and item group (col C)",
                "Rs. per person per 30 days", "none", "current")
    out = []
    for (geo, sector), items in data.items():
        for code, vals in items.items():
            role = next(rl for lab, (cc, rl) in A6_ITEMS.items() if cc == code)
            for fr, v in vals.items():
                hg = f"{sector}_{fr}"
                out.append({
                    **_base_row(period, src),
                    "series_id": f"a6.{_rt(period)}.{code}.{geo_slug(geo)}.{hg}.current",
                    "table_id": "Table A6",
                    "item_code": "value_per_person_30d",
                    "item_label": labels[code],
                    "product": f"hces_group:{code}",
                    "geography": geo,
                    "household_group": hg,
                    "dim_other": f"item_role={role}",
                    "stock_flow": "flow",
                    "value": v,
                    "unit": "INR",
                    "price_basis": "current",
                    "status": "official",
                    "prov_id": pid,
                })
    return out


def build_a6_dataset(ctx: BuildContext, a2: Dataset) -> Dataset:
    rows: list[dict[str, Any]] = []
    for period in ("2023-24", "2022-23"):
        sel = (pl.col("item_code") == "households") & (pl.col("period") == sy_period(period))
        hh = {
            (g, hg): v
            for g, hg, v in a2.df.filter(sel)
            .select("geography", "household_group", "value")
            .iter_rows()
        }
        rows += build_a6(ctx, period, hh)
    return Dataset(
        f"{UNIT}_a6_group_fractile",
        pl.DataFrame(rows),
        "HCES 2022-23 and 2023-24 Table A6: value of consumption (Rs per person per 30 days) of ~35 item groups "
        "by State x R/U x fractile class, incl. memo items (imputed rent, free meals)",
    )


# =============================================================================================
# Item-level tables A10F / A10S / A10SW: item classification
# =============================================================================================

SUBTOTALS = frozenset(
    "099 129 159 169 179 189 199 219 239 249 269 279 289 299 309 319 329 349 379 389 399 409 419 429 439 459 479 "
    "499 519 529 559 569 579 599 609 619 629 639 649".split()
)
SINGLE_GROUPS = frozenset({"139", "899"})  # one-item groups that count directly in a total
MEMO = frozenset({"539"})  # house/garage rent (imputed): printed, not part of any total
# Table A10SW only: imputed value of durables received free from schemes (991-995). They are printed
# after 649 but counted in the sub-totals 'other personal goods' (629: laptop, tablet, mobile) and
# 'transport equipment' (609: bicycle, motorcycle). The free school uniform (996) and shoes (997) are
# printed inside the clothing and footwear blocks and are ordinary leaves there.
FREE_IMPUTED: dict[str, str] = {"991": "629", "992": "629", "993": "629", "994": "609", "995": "609"}
TOTALS: dict[str, list[str]] = {
    "981": "129 139 159 169 179 189 199 219 239 249 269 279 289 299".split(),
    "982": "309 319 329 349 409 419 429 439 459 479 499 519 529 899".split(),
    "983": "099 379 389 399 559 569 579 599 609 619 629 639 649".split(),
    "984": ["982", "983"],
    "999": ["981", "984"],
}
# 'other ...' lines that are the sum of detailed lines printed next to them (the detail is kept as leaf)
AGGREGATES: dict[str, list[str]] = {
    "092": ["006", "007", "167"],
    "093": ["221", "223", "227", "233", "234", "235", "238"],
    "094": ["008", "010", "247"],
    "095": ["180", "185"],
    "096": ["333", "336", "337", "340", "341", "342", "343", "344", "345", "346"],
}
AGG_CHILD = {c: a for a, cs in AGGREGATES.items() for c in cs}
# Grain-wise PDS (055-060) and other-source (115-121) coarse-grain detail: printed inside the cereal
# block but NOT part of the cereal sub-total, which counts 001 (coarse grains PDS) and 002 (other
# sources) instead; the grain detail does not add up to 001/002 (logged in issues).
# Likewise the grain-wise free lines 063-068 are detail of 070 'coarse grains-free' (their imputed
# values in Table A10SW add up to 070, which is the line the cereal sub-total counts).
MEMO_DETAIL = frozenset({"055", "056", "057", "058", "059", "060", "115", "116", "117", "118", "120", "121",
                         "063", "064", "065", "066", "067", "068"})

# Same publisher inconsistency as Table A6 (food 1,938.50 + non-food 2,183.38 = 4,121.88 vs printed
# 4,121.78): (period, table, sector, State or fractile, code) -> largest accepted |difference|.
ITEM_KNOWN_BREAKS: dict[tuple[str, str, str, str, str], float] = {
    ("2023-24", "Table A10S", "rural", "IN", "999"): 0.11,
}

KG_GROUPS = frozenset({"129", "139", "159", "169", "179", "189", "199", "219", "239", "249"})
KG_FUEL = frozenset({"331", "333", "337", "338", "341"})
FOODLIKE_GROUPS = frozenset({*TOTALS["981"], "309", "319", "329", "349"})
_NO_RE = re.compile(r"\((no\.?|nos\.?)\)", re.I)
_OTHER_UNIT_RE = re.compile(r"\((litre|gm|metre|std\.? ?unit|box)\)", re.I)
# Items whose quantity is counted in numbers although the round's table omits '(no.)'.
# HCES 2022-23 prints 223 'pineapple', 224 'coconut', 225 'green coconut' and 228 'orange, mausami'
# without a unit; HCES 2023-24 prints the same codes '(no.)'. The 2022-23 implied unit values match
# the 2023-24 per-piece values (A10S All-India, value/qty, rural 2022-23 vs 2023-24: orange 8.22 vs
# 7.64, coconut 20.46 vs 20.99, green coconut 31.49 vs 36.55, pineapple 40.00 vs 41.43), so the
# 2022-23 quantities are numbers, not kg (verifier finding, hces_consumption-24).
QTY_NUMBER_OVERRIDE: dict[str, frozenset[str]] = {"2022-23": frozenset({"223", "224", "225", "228"})}


def item_role(code: str) -> str:
    if code in TOTALS:
        return "total"
    if code in SUBTOTALS:
        return "subtotal"
    if code in MEMO:
        return "memo"
    if code in AGGREGATES:
        return "aggregate"
    if code in MEMO_DETAIL:
        return "memo_detail"
    return "leaf"


def qty_unit(code: str, label: str, group: str, period: str | None = None) -> str | None:
    """Published unit of an item's quantity column, or None if it is not ingested.

    Table note 1: 'Quantity is in Kgs wherever applicable unless otherwise specified against the
    respective item of food, fuel, pan, tobacco and intoxicants. For other items quantity is in
    number wherever applicable.' Litre, gram, metre, standard-unit and box quantities are not
    ingested (no unit in the clean vocabulary; Framework request FR2). Kilograms are assumed only for
    the established food groups and five solid fuels; items added in 2022-23 (codes below 100 other
    than the free/PDS/coarse-grain lines) are skipped because at least one ('cheese') is visibly not
    in kg. Codes in QTY_NUMBER_OVERRIDE[period] are numbers even where the label omits '(no.)'.
    """
    if item_role(code) in ("subtotal", "total"):
        return None
    if _NO_RE.search(label) or code in QTY_NUMBER_OVERRIDE.get(period or "", frozenset()):
        return "number"
    if _OTHER_UNIT_RE.search(label):
        return None
    new_item = code < "100" and not ("055" <= code <= "075" or code in ("001", "002"))
    if group in KG_GROUPS:
        return None if new_item else "kg"
    if group == "349":
        return "kg" if code in KG_FUEL else None
    if group in FOODLIKE_GROUPS:
        return None
    return "number"


def assign_groups(seq: list[str], where: str) -> dict[str, str]:
    """Group of each code in one block's display order: the sub-total that closes it."""
    out: dict[str, str] = {}
    cur: list[str] = []
    for code in seq:
        if code in TOTALS:
            if cur:
                raise ValueError(f"{where}: items {cur} not closed by a sub-total before total {code}")
            out[code] = "total"
        elif code in SUBTOTALS:
            for m in cur:
                out[m] = code
            out[code] = code
            cur = []
        elif code in FREE_IMPUTED and not cur:
            out[code] = FREE_IMPUTED[code]
        elif code in SINGLE_GROUPS or code in MEMO:
            if cur:
                raise ValueError(f"{where}: items {cur} not closed by a sub-total before {code}")
            out[code] = code
        else:
            cur.append(code)
    if cur:
        raise ValueError(f"{where}: trailing items {cur} without a sub-total")
    return out


def check_block(values: dict[str, float | None], groups: dict[str, str], where: str) -> list[tuple[str, float, float, str]]:
    """Re-add every published sub-total, aggregate and total from its parts; return the failures."""
    bad = []

    def v(c: str) -> float:
        x = values.get(c)
        return 0.0 if x is None else x

    members: dict[str, list[str]] = defaultdict(list)
    for c, g in groups.items():
        if item_role(c) == "leaf" and g in SUBTOTALS:
            members[g].append(c)
    for s in SUBTOTALS & values.keys():
        if values[s] is None:
            continue
        parts = members.get(s, [])
        tot = sum(v(c) for c in parts)
        if abs(tot - values[s]) > 0.02 + 0.006 * len(parts):
            bad.append((s, values[s], tot, where))
    for a, cs in AGGREGATES.items():
        if a in values and values[a] is not None:
            tot = sum(v(c) for c in cs)
            if abs(tot - values[a]) > 0.02 + 0.006 * len(cs):
                bad.append((a, values[a], tot, where))
    for t, parts in TOTALS.items():
        if t in values and values[t] is not None:
            tot = sum(v(c) for c in parts)
            if abs(tot - values[t]) > 0.02 + 0.006 * len(parts):
                bad.append((t, values[t], tot, where))
    return bad


def _item_table(rows: list[tuple[Any, ...]], where: str, *, by: str) -> tuple[int, int, list[dict[str, Any]]]:
    """Parse A10F (by='fractile') or A10S/A10SW (by='state') into records."""
    expect_text(rows, 2, 3, "Item code", where)
    expect_text(rows, 2, 4, "Item description", where)
    expect_text(rows, 2, 5, "Quantity per person per 30 days", where)
    expect_text(rows, 2, 6, "Value per person per 30 days (Rs.)", where)
    expect_text(rows, 2, 7, "No. of households reporting consumption", where)
    expect_text(rows, 3, 7, "Estimated (00)", where)
    first = first_row_with(rows, 1, "(1)") + 1
    recs = []
    last = first
    for i in range(first, len(rows) + 1):
        r = rows[i - 1]
        if r[0] is None and r[2] is None:
            continue
        a = clean_label(str(r[0])) if r[0] is not None else ""
        if a.lower().startswith(("note", "2.", "3.")):
            break
        if r[2] is None:
            raise ValueError(f"{where}: row {i} has no item code")
        code = clean_label(str(r[2]))
        if not re.fullmatch(r"\d{3}", code):
            raise ValueError(f"{where}: row {i} bad item code {code!r}")
        rec = {
            "row": i,
            "sector": sector_code(r[0]),
            "key": fractile_code(r[1]) if by == "fractile" else state_geo(r[1]),
            "code": code,
            "label": clean_label(str(r[3])),
            "qty": _num(r[4]),
            "value": _num(r[5]),
            "hh": _num(r[6]),
            "qty_raw": r[4],
        }
        recs.append(rec)
        last = i
    return first, last, recs


def _classify(recs: list[dict[str, Any]], where: str) -> tuple[dict[str, str], dict[str, str]]:
    """Group and label of every item code, consistent across all blocks."""
    blocks: dict[tuple[str, str], list[str]] = defaultdict(list)
    labels: dict[str, str] = {}
    for rc in recs:
        blocks[(rc["sector"], rc["key"])].append(rc["code"])
        old = labels.setdefault(rc["code"], rc["label"])
        if old != rc["label"]:
            raise ValueError(f"{where}: item {rc['code']} has two labels {old!r} / {rc['label']!r}")
    groups: dict[str, str] = {}
    for k, seq in blocks.items():
        if len(seq) != len(set(seq)):
            raise ValueError(f"{where}: duplicate item codes in block {k}")
        for c, g in assign_groups(seq, f"{where} {k}").items():
            if groups.setdefault(c, g) != g:
                raise ValueError(f"{where}: item {c} in group {groups[c]} and {g}")
    for a, cs in AGGREGATES.items():
        for c in [a, *cs]:
            if c in groups and groups[c] != groups.get(a, groups[c]):
                raise ValueError(f"{where}: aggregate {a} and its detail {c} are in different groups")
    return groups, labels


def _item_rows(
    ctx: BuildContext, period: str, file_key: str, table_id: str, prefix: str, *, by: str, with_hh: bool
) -> list[dict[str, Any]]:
    rd = ROUNDS[period]
    src = rd["src"]
    raw = ctx.raw(src, rd["files"][file_key][1])
    title, rows = sheet_rows(raw.path)
    where = f"{src} {table_id}"
    expect_text(rows, 1, 1, table_id, where)
    expect_text(rows, 1, 1, "per capita quantity and value of consumption at detailed item level", where)
    if file_key == "a10sw":
        expect_text(rows, 1, 1, "With Imputation", where)
    first, last, recs = _item_table(rows, where, by=by)
    groups, labels = _classify(recs, where)
    # identity checks per block
    blockvals: dict[tuple[str, str], dict[str, float | None]] = defaultdict(dict)
    for rc in recs:
        blockvals[(rc["sector"], rc["key"])][rc["code"]] = rc["value"]
    bad: list[str] = []
    for k, vals in blockvals.items():
        for code, pub, parts, w in check_block(vals, groups, f"{where} {k}"):
            known = ITEM_KNOWN_BREAKS.get((period, table_id, k[0], k[1], code))
            if known is not None and abs(pub - parts) <= known:
                ctx.warn(f"{w}: known publisher break {code}: printed {pub} vs parts {parts:.2f} (logged)")
            else:
                bad.append(f"{w} {code}: published {pub} vs parts {parts:.2f}")
    if bad:
        raise ValueError(f"{where}: {len(bad)} published sub-totals do not re-add, e.g. {bad[:6]}")
    # a total per block must exist
    for k, vals in blockvals.items():
        if vals.get("999") is None:
            raise ValueError(f"{where}: block {k} has no Total Expenditure (999)")

    loc = (f"sheet '{title}', rows {first}-{last}; rows matched by sector (col A), "
           f"{'fractile class' if by == 'fractile' else 'State/UT'} (col B) and item code (col C)")
    p_val = _prov(ctx, raw, period, table_id, f"{loc}; col F (value)", "Rs. per person per 30 days", "none",
                  "current")
    p_kg = _prov(ctx, raw, period, table_id,
                 f"{loc}; col E (quantity) for items whose quantity is in kg (table note 1; see qty_unit rules)",
                 "kg per person per 30 days", "kg -> tonnes: x 0.001", NA)
    no_note = ""
    if QTY_NUMBER_OVERRIDE.get(period):
        no_note = (f" (incl. codes {', '.join(sorted(QTY_NUMBER_OVERRIDE[period]))}, printed without '(no.)' in this "
                   "round but '(no.)' in HCES 2023-24; implied unit values confirm counts)")
    p_no = _prov(ctx, raw, period, table_id, f"{loc}; col E (quantity) for items counted in numbers{no_note}",
                 "number per person per 30 days", "none", NA)
    p_hh = _prov(ctx, raw, period, table_id, f"{loc}; col G (estimated households reporting, in hundreds)",
                 "number (00)", "x 100 (hundreds -> count)", NA)
    out: list[dict[str, Any]] = []
    for rc in recs:
        code, sector, key = rc["code"], rc["sector"], rc["key"]
        g = groups[code]
        role = item_role(code)
        if by == "fractile":
            geo, hg = "IN", f"{sector}_{key}"
            tail = f"{sector}_{key}"
        else:
            geo, hg = key, f"{sector}_all"
            tail = f"{geo_slug(key)}.{sector}"
        common = {
            **_base_row(period, src),
            "table_id": table_id,
            "item_label": labels[code],
            "product": f"hces:{code}",
            "geography": geo,
            "household_group": hg,
            "stock_flow": "flow",
            "status": "official",
        }
        other = f"group={g};item_role={role}"
        if rc["value"] is not None:
            out.append({**common, "series_id": f"{prefix}.{_rt(period)}.{code}.value.{tail}.current",
                        "item_code": "value_per_person_30d", "dim_other": other, "value": rc["value"],
                        "unit": "INR", "price_basis": "current", "prov_id": p_val})
        qu = qty_unit(code, labels[code], g, period)
        if rc["qty"] is not None and qu is not None:
            if qu == "kg":
                val, unit, pid = rc["qty"] / 1000.0, "tonnes", p_kg
            else:
                val, unit, pid = rc["qty"], "count", p_no
            out.append({**common, "series_id": f"{prefix}.{_rt(period)}.{code}.qty.{tail}",
                        "item_code": "qty_per_person_30d", "dim_other": f"{other};qty_published_unit={qu}",
                        "value": val, "unit": unit, "price_basis": NA, "prov_id": pid})
        if with_hh and rc["hh"] is not None:
            out.append({**common, "series_id": f"{prefix}.{_rt(period)}.{code}.hh_reporting.{tail}",
                        "item_code": "households_reporting", "dim_other": other, "stock_flow": "stock",
                        "value": rc["hh"] * 100.0, "unit": "count", "price_basis": NA, "prov_id": p_hh})
    return out


def build_a10f_dataset(ctx: BuildContext) -> Dataset:
    rows = []
    for period in ("2023-24", "2022-23"):
        rows += _item_rows(ctx, period, "a10f", "Table A10F", "a10f", by="fractile", with_hh=True)
    return Dataset(
        f"{UNIT}_a10f_item_fractile",
        pl.DataFrame(rows),
        "HCES 2022-23 and 2023-24 Table A10F: item-level value, quantity and households reporting per person "
        "per 30 days by R/U x 12 fractile classes, All-India; item_role in dim_other (use leaf only for sums)",
    )


def build_a10s_dataset(ctx: BuildContext) -> Dataset:
    rows = []
    for period in ("2023-24", "2022-23"):
        rows += _item_rows(ctx, period, "a10s", "Table A10S", "a10s", by="state", with_hh=False)
    return Dataset(
        f"{UNIT}_a10s_state_item",
        pl.DataFrame(rows),
        "HCES 2022-23 and 2023-24 Table A10S: item-level value and quantity per person per 30 days by State/UT x "
        "R/U (no imputation of free items)",
    )


def build_a10sw_dataset(ctx: BuildContext) -> Dataset:
    rows = _item_rows(ctx, "2023-24", "a10sw", "Table A10SW", "a10sw", by="state", with_hh=False)
    return Dataset(
        f"{UNIT}_a10sw_state_item_imputed",
        pl.DataFrame(rows),
        "HCES 2023-24 Table A10SW: as A10S but with imputed values of free/PDS items (MPCE with imputation), "
        "by State/UT x R/U",
    )


__all__ = [
    "build_a2_dataset",
    "build_a6_dataset",
    "build_a10f_dataset",
    "build_a10s_dataset",
    "build_a10sw_dataset",
    "item_role",
    "qty_unit",
    "slug",
]
