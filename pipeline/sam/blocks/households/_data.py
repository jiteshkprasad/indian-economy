"""Households block: reading and validating the clean inputs (HCES 2023-24 groups and items, SUT PFCE by
product, the committed HCES item -> SUT product key concordance). Private helper of the `households` block."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import polars as pl

from pipeline.sam.framework import BlockContext, SamError

SURVEY = "2023-08/2024-07"  # HCES 2023-24 survey window (period_type sy); ctx.rows defaults to 2023-24
VINTAGE = "latest"  # SUT / NAS / RBI reads (an explicit choice; stated in each method text)

A2 = "hces_consumption_a2_fractile_persons"
A10F = "hces_consumption_a10f_item_fractile"
A10SW = "hces_consumption_a10sw_state_item_imputed"
H596 = "hces_consumption_health596"
CMS = "hces_consumption_cms_education_2025"
SUPPLY, USE = "io_tables_sut_supply", "io_tables_sut_use"
ICIO = "io_tables_icio_india"
IFPRI = "io_tables_ifpri_2223_datapaper"
NAS11, NAS113, NAS114 = "mospi_nas_2026_s1_1", "mospi_nas_2026_s1_13", "mospi_nas_2026_s1_14"
NAS51, NAS813 = "mospi_nas_2026_s5_1", "mospi_nas_2026_s8_13"
T52 = "rbi_financial_accounts_hh_finsav_52ab"
RTP = "rbi_banking_corporate_rtp_banks"
AIDIS_Q = "labour_enterprise_surveys_aidis_2019_quintile"
AIDIS_PN = "labour_enterprise_surveys_aidis_2019_press_note"
UNION_EXP = "union_fiscal_exp_profile"
PRODUCT_MAP = "io_tables_sut_product_to_sam34"
KEY_MAP = "hces2324_item_to_sut_product"
# registry source ids a record names when its inputs come from several sources (the one the numbers rest on)
HCES_SRC, SUT_SRC, NAS_SRC, AIDIS_SRC = (
    "mospi_hces_2023_24",
    "mospi_sut_2022base",
    "mospi_nas_2026_publication",
    "mospi_aidis_2019",
)

AREAS = ("rural", "urban")
FRACTILES = (
    "p00_05",
    "p05_10",
    "p10_20",
    "p20_30",
    "p30_40",
    "p40_50",
    "p50_60",
    "p60_70",
    "p70_80",
    "p80_90",
    "p90_95",
    "p95_100",
)
QUINTILE = {
    "p00_05": 1,
    "p05_10": 1,
    "p10_20": 1,
    "p20_30": 2,
    "p30_40": 2,
    "p40_50": 3,
    "p50_60": 3,
    "p60_70": 4,
    "p70_80": 4,
    "p80_90": 5,
    "p90_95": 5,
    "p95_100": 5,
}
# SUT products whose PFCE is not keyed by C1a (C4a dwellings, C4b financial and insurance, C4d education, health)
NOT_C1A = {"sut_p142", "sut_p143", "sut_p144", "sut_p152", "sut_p153"}
FREE_ITEMS = ("061", "062", "070", "071", "072", "073", "074", "075")  # quantities only ('##' values)
JEWELLERY = ("640", "641", "642", "643")
ASSISTANCE_MEALS = "282"
LAND_RENT = "522"
RENT_ACTUAL, RENT_IMPUTED = "520", "539"
C4A_COMPONENTS = ("actual_rent", "imputed_rent", "govt_housing")
C4D_COMPONENTS = {"sut_p152": "oop_education", "sut_p153": "oop_health"}
TOTAL_CODES = {"981": "hces_food", "983": "hces_durables", "984": "hces_nonfood", "999": "hces_all_items"}


def group_code(area: str, quintile: int) -> str:
    return f"H_{'R' if area == 'rural' else 'U'}{quintile}"


def area_of(group: str) -> str:
    return "rural" if group.startswith("H_R") else "urban"


@dataclass
class HH:
    """Everything the block computes once and shares between its parts (frames and prov_ids)."""

    groups: list[str]  # H_R1..H_U5 in accounts.yaml order
    classes: pl.DataFrame  # 24 HCES classes: hces_class, area, fractile, household_group, persons, households, avg_mpce
    items: pl.DataFrame  # A10F values by item x class at HCES scale (Rs crore/yr): code, role, label, hces_class, crore
    item_groups: pl.DataFrame  # the same summed to the 10 groups: code, role, label, household_group, crore
    pfce: pl.DataFrame  # SUT PFCE by product: product, commodity, label, value, prov_id
    keymap: pl.DataFrame  # the committed concordance, validated
    pid: dict[str, str] = field(default_factory=dict)  # named prov_ids (clean and own)
    values: dict[str, float] = field(default_factory=dict)  # named scalars used in methods and checks
    conc_note: str = ""


def one_prov(df: pl.DataFrame, what: str) -> str:
    ids = df["prov_id"].unique(maintain_order=True).to_list()
    if len(ids) != 1:
        raise SamError(f"{what}: expected one clean provenance record, got {ids}")
    return str(ids[0])


def read_classes(ctx: BlockContext, geography: str = "IN") -> pl.DataFrame:
    """HCES 2023-24 Table A2: persons, households and average MPCE of the 24 fractile classes (12 per area)."""
    frames = {}
    for item, unit, basis in (
        ("persons", "count", "n/a"),
        ("households", "count", "n/a"),
        ("avg_mpce", "INR", "current"),
    ):
        df = ctx.rows(A2, period=SURVEY, geography=geography, item_code=item, unit=unit, price_basis=basis)
        frames[item] = df.filter(~pl.col("household_group").str.ends_with("_all"))
    out = frames["persons"].select(
        "household_group", pl.col("value").alias("persons"), pl.col("prov_id").alias("pid_p")
    )
    for item in ("households", "avg_mpce"):
        out = out.join(
            frames[item].select("household_group", pl.col("value").alias(item), pl.col("prov_id").alias(f"pid_{item}")),
            on="household_group",
            how="full",
            coalesce=True,
            maintain_order="left",
        )
    out = out.rename({"household_group": "hces_class"})
    want = [f"{a}_{f}" for a in AREAS for f in FRACTILES]
    got = sorted(out["hces_class"].to_list())
    if got != sorted(want) or out.select(pl.any_horizontal(pl.all().is_null()).any()).item():
        raise SamError(
            f"A2 {geography} {SURVEY}: expected the 24 fractile classes with persons, households, MPCE; got {got}"
        )
    return (
        out.with_columns(
            pl.col("hces_class").str.split("_").list.get(0).alias("area"),
            pl.col("hces_class").str.split("_").list.slice(1).list.join("_").alias("fractile"),
        )
        .with_columns(
            pl.struct("area", "fractile")
            .map_elements(lambda s: group_code(s["area"], QUINTILE[s["fractile"]]), return_dtype=pl.String)
            .alias("household_group")
        )
        .with_columns(pl.col("hces_class").replace_strict({c: i for i, c in enumerate(want)}).alias("_o"))
        .sort("_o")
        .drop("_o")
    )


def read_items(ctx: BlockContext, classes: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, str]:
    """HCES 2023-24 Table A10F values per person (30 days) -> Rs crore a year at HCES scale by item x class:
    value x persons (A2) x 12 / 1e7. Cells printed '-' are absent in clean data and count as 0."""
    v = ctx.rows(A10F, period=SURVEY, item_code="value_per_person_30d", unit="INR", price_basis="current")
    pid = one_prov(v, "A10F values")
    v = v.with_columns(
        pl.col("series_id").str.split(".").list.get(2).alias("code"),
        pl.col("dim_other").str.extract(r"item_role=(\w+)").alias("role"),
        pl.col("household_group").alias("hces_class"),
    ).drop("household_group")
    if v.select(pl.struct("code", "hces_class").is_duplicated().any()).item():
        raise SamError("A10F: an item has two value rows for one fractile class")
    bad = sorted(set(v["hces_class"].to_list()) - set(classes["hces_class"].to_list()))
    if bad or v["role"].null_count():
        raise SamError(f"A10F: unknown classes {bad} or items without item_role")
    items = (
        v.join(
            classes.select("hces_class", "persons", "household_group"),
            on="hces_class",
            how="left",
            maintain_order="left",
        )
        .with_columns((pl.col("value") * pl.col("persons") * 12.0 / 1e7).alias("crore"))
        .select("code", "role", pl.col("item_label").alias("label"), "hces_class", "household_group", "crore")
        .sort("code", "hces_class")
    )
    item_groups = (
        items.group_by("code", "role", "label", "household_group", maintain_order=True)
        .agg(pl.col("crore").sum())
        .sort("code", "household_group")
    )
    return items, item_groups, pid


def read_pfce(ctx: BlockContext) -> tuple[pl.DataFrame, float, str]:
    """SUT 2023-24 PFCE by product (product rows only: the two memo rows 'purchases of non-residents in the
    domestic market' / 'of residents abroad' are already inside the product rows, national concept, and are
    never read into an entry), mapped to the 34 commodities with production's concordance."""
    use = ctx.rows(USE, item_code="pfce", vintage=VINTAGE)
    total = use.filter(pl.col("product") == "total")
    if total.height != 1:
        raise SamError("SUT use.pfce.total not found exactly once")
    conc = ctx.concordance(PRODUCT_MAP).select(
        ("sut_p" + pl.col("sut_product").str.zfill(3)).alias("product"), "commodity"
    )
    prod = (
        use.filter(pl.col("product").str.starts_with("sut_p") & (pl.col("value") != 0))
        .join(conc, on="product", how="left", maintain_order="left")
        .select("product", "commodity", pl.col("item_label").alias("label"), "value", "prov_id", "series_id")
        .sort("product")
    )
    if prod["commodity"].null_count():
        raise SamError(
            f"SUT products missing from {PRODUCT_MAP}: {prod.filter(pl.col('commodity').is_null())['product']}"
        )
    if (prod["value"] < 0).any():
        raise SamError(f"negative SUT PFCE: {prod.filter(pl.col('value') < 0)['product'].to_list()}")
    return prod, float(total["value"][0]), str(total["prov_id"][0])


def read_keymap(ctx: BlockContext, items: pl.DataFrame, pfce: pl.DataFrame) -> pl.DataFrame:
    """The committed concordance data/concordance/hces2324_item_to_sut_product.csv (DECISIONS D2-15), validated:
    every rule of the households plan s.2.2 step 3 and s.7 test 9 fails the build when broken."""
    km = ctx.concordance(KEY_MAP)
    need = ["sut_product", "hces_item", "ref", "component", "key_quality", "note"]
    if km.columns != need:
        raise SamError(f"{KEY_MAP}: columns must be {need}, got {km.columns}")
    km = km.with_columns(pl.col(c).fill_null("") for c in need).with_columns(
        pl.when(pl.col("sut_product") != "")
        .then("sut_p" + pl.col("sut_product").str.zfill(3))
        .otherwise(pl.lit(""))
        .alias("product")
    )
    roles = dict(items.select("code", "role").unique(maintain_order=True).iter_rows())
    leaf_free = set(FREE_ITEMS)  # leaf items that carry quantities only (no value rows)
    leaves = {c for c, r in roles.items() if r == "leaf"} | leaf_free
    pf = set(pfce["product"].to_list())
    problems: list[str] = []
    for r in km.iter_rows(named=True):
        tag = f"row ({r['sut_product']}, {r['hces_item']}, {r['ref']})"
        if not re.fullmatch(r"\d{3}", r["hces_item"]):
            problems.append(f"{tag}: hces_item must be a 3-digit A10F code")
        if r["ref"] not in ("C1a", "C4a", "C4d", "excluded"):
            problems.append(f"{tag}: ref must be C1a, C4a, C4d or excluded")
        if r["ref"] == "excluded":
            if r["product"] or r["component"] or r["key_quality"]:
                problems.append(f"{tag}: an exclusion has no product, component or key_quality")
            if not r["note"]:
                problems.append(f"{tag}: an exclusion needs its reason in `note`")
            continue
        if r["key_quality"] not in ("direct", "proxy"):
            problems.append(f"{tag}: key_quality must be direct or proxy")
        if r["product"] not in pf:
            problems.append(f"{tag}: SUT product has no PFCE in {ctx.year}")
        is_memo_rent = r["ref"] == "C4a" and r["hces_item"] == RENT_IMPUTED
        if r["hces_item"] not in leaves and not (is_memo_rent and roles.get(RENT_IMPUTED) == "memo"):
            problems.append(f"{tag}: not an A10F leaf item (only 539, the imputed-rent memo, is allowed, in C4a)")
        if r["ref"] == "C1a" and (r["product"] in NOT_C1A or r["component"]):
            problems.append(f"{tag}: C1a keys only products outside {sorted(NOT_C1A)}, with an empty component")
        if r["ref"] == "C4a" and (r["product"] != "sut_p144" or r["component"] not in C4A_COMPONENTS):
            problems.append(f"{tag}: C4a keys product 144 with a component in {C4A_COMPONENTS}")
        if r["ref"] == "C4d" and C4D_COMPONENTS.get(r["product"]) != r["component"]:
            problems.append(f"{tag}: C4d keys products 152/153 with components {C4D_COMPONENTS}")
    excluded = set(km.filter(pl.col("ref") == "excluded")["hces_item"].to_list())
    used = set(km.filter(pl.col("ref") != "excluded")["hces_item"].to_list())
    if excluded & used:
        problems.append(f"items both excluded and used: {sorted(excluded & used)}")
    must_exclude = set(FREE_ITEMS) | set(JEWELLERY) | {ASSISTANCE_MEALS, LAND_RENT}
    if not must_exclude <= excluded:
        problems.append(f"items that must be excluded from every PFCE key: {sorted(must_exclude - excluded)}")
    c1a_items = set(km.filter(pl.col("ref") == "C1a")["hces_item"].to_list())
    special = set(km.filter(pl.col("ref").is_in(["C4a", "C4d"]))["hces_item"].to_list())
    if c1a_items & special:
        problems.append(f"C4a/C4d items used in a C1a key (double counting): {sorted(c1a_items & special)}")
    missing = sorted(leaves - used - excluded)
    if missing:
        problems.append(f"leaf items neither used nor excluded (with a reason): {missing}")
    keyed = set(km.filter(pl.col("ref") != "excluded")["product"].to_list())
    unkeyed = sorted(pf - keyed - {"sut_p142", "sut_p143"})
    if unkeyed:
        problems.append(f"SUT products with PFCE but no HCES key: {unkeyed}")
    if km.select(pl.struct("product", "hces_item", "ref", "component").is_duplicated().any()).item():
        problems.append("duplicate (product, item, ref, component) rows")
    if problems:
        raise SamError(f"{KEY_MAP}.csv: {len(problems)} problem(s)\n  " + "\n  ".join(problems[:30]))
    return km
