"""Households block: satellites (hh_keys and its companions, S8, the C4c memo) and their provenance records.
Private helper of the `households` block."""

from __future__ import annotations

import math
import re

import polars as pl

from pipeline.sam.framework import BlockContext, SamError, Satellite

from . import _xwalk
from ._aidis import AIDIS_PERIOD
from ._data import (
    A2,
    A10F,
    A10SW,
    AIDIS_PN,
    AREAS,
    FRACTILES,
    FREE_ITEMS,
    HCES_SRC,
    HH,
    ICIO,
    NAS_SRC,
    SURVEY,
    T52,
    TOTAL_CODES,
    USE,
    VINTAGE,
    area_of,
    group_code,
)
from ._entries import FISIM_D_KEY

SAT_DECIMALS = 12  # shares published at 12 decimals (XR-22 asks for >= 9); levels too


def frame(rows: list[dict], dims: list[str]) -> pl.DataFrame:
    schema: dict[str, pl.DataType] = {
        "series_id": pl.String(),
        **{d: pl.String() for d in dims},
        "value": pl.Float64(),
        "unit": pl.String(),
        "status": pl.String(),
        "prov_id": pl.String(),
    }
    return pl.DataFrame([{k: r.get(k) for k in schema} for r in rows], schema=schema, orient="row")


def group_map(ctx: BlockContext, hh: HH) -> Satellite:
    pid = ctx.prov(
        ref="C1a",
        status="derived",
        inputs=[hh.pid["persons"], hh.pid["households"], hh.pid["mpce"], hh.pid["window"]],
        method="SAM household groups (satellite hh_group_map): the 24 HCES 2023-24 Table A2 fractile classes (12 per "
        "area) mapped to the 10 groups, H_R1/H_U1 = p00_05 + p05_10 + p10_20, H_x2 = p20_30 + p30_40, H_x3 = p40_50 + "
        "p50_60, H_x4 = p60_70 + p70_80, H_x5 = p80_90 + p90_95 + p95_100 (person quintiles within rural and within "
        f"urban), with each class's persons, households and average MPCE (Rs per person per 30 days) as published "
        f"(period {SURVEY}, geography IN).",
    )
    hh.pid["group_map"] = pid
    rows = []
    for r in hh.classes.iter_rows(named=True):
        for m, unit in (("persons", "count"), ("households", "count"), ("avg_mpce", "INR")):
            rows.append(
                {
                    "series_id": f"{r['hces_class']}.{m}",
                    "hces_class": r["hces_class"],
                    "area": r["area"],
                    "household_group": r["household_group"],
                    "measure": m,
                    "value": r[m],
                    "unit": unit,
                    "status": "derived",
                    "prov_id": pid,
                }
            )
    df = frame(rows, ["hces_class", "area", "household_group", "measure"])
    return Satellite("C1a", df, "HCES 2023-24 fractile classes -> SAM household groups: persons, households, avg MPCE")


def hces_items(ctx: BlockContext, hh: HH) -> Satellite:
    pid = ctx.prov(
        ref="C1a",
        status="derived",
        inputs=[hh.pid["a10f"], hh.pid["persons"], hh.pid["window"]],
        method="HCES 2023-24 spending by A10F item and SAM group at HCES scale (satellite hh_hces_items): value per "
        "person (30 days, Table A10F, all-India fractile classes) x persons (Table A2) x 12 / 1e7, Rs crore a year, "
        "summed over the classes of each group. Leaf items, the imputed-rent memo 539 and the totals 981/982/983/984/"
        "999; cells printed '-' are absent (0). HCES scale is about 44% of NAS PFCE (RECONCILIATION HH-1): use "
        "shares, not levels.",
    )
    hh.pid["hces_items"] = pid
    df = hh.item_groups.filter(pl.col("role").is_in(["leaf", "memo", "total"]))
    rows = [
        {
            "series_id": f"hces.{r['code']}.{r['household_group'].lower()}",
            "hces_item": r["code"],
            "item_role": r["role"],
            "item_label": r["label"],
            "household_group": r["household_group"],
            "value": r["crore"],
            "unit": "INR_crore",
            "status": "derived",
            "prov_id": pid,
        }
        for r in df.iter_rows(named=True)
    ]
    return Satellite(
        "C1a",
        frame(rows, ["hces_item", "item_role", "item_label", "household_group"]),
        "HCES 2023-24 item spending by SAM group, Rs crore/yr at HCES scale (leaf items, 539, totals)",
    )


def _key_rows(key: str, levels: dict[str, float], unit: str, basis: str, status: str, pid: str) -> list[dict]:
    total = sum(levels.values())
    if not total > 0:
        raise SamError(f"hh_keys {key}: levels sum to {total}")
    rows = []
    for g, v in levels.items():
        base = {
            "key": key,
            "household_group": g,
            "area": area_of(g),
            "basis_period": basis,
            "status": status,
            "prov_id": pid,
        }
        rows.append({**base, "series_id": f"{key}.level.{g.lower()}", "measure": "level", "value": v, "unit": unit})
        rows.append(
            {**base, "series_id": f"{key}.share.{g.lower()}", "measure": "share", "value": v / total, "unit": "ratio"}
        )
    return rows


def hh_keys(ctx: BlockContext, hh: HH, entries: list[dict], aidis: pl.DataFrame) -> Satellite:
    """The reusable keys other blocks read (CROSS_REVIEW s.4.3, names exact)."""
    rows: list[dict] = []
    cl = hh.classes
    pid = ctx.prov(
        ref="C1a",
        status="derived",
        inputs=[hh.pid["persons"], hh.pid["households"], hh.pid["window"]],
        method="hh_keys pop_persons / pop_households: HCES 2023-24 Table A2 persons and households of the "
        "fractile classes summed to the 10 SAM groups (counts; HCES population, 1,217.6 mn persons, not the "
        "NAS population).",
    )
    for key, col in (("pop_persons", "persons"), ("pop_households", "households")):
        lv = {g: float(cl.filter(pl.col("household_group") == g)[col].sum()) for g in hh.groups}
        rows += _key_rows(key, lv, "count", SURVEY, "derived", pid)
    pid = ctx.prov(
        ref="C1a",
        status="derived",
        inputs=[hh.pid["persons"], hh.pid["mpce"], hh.pid["a10f"], hh.pid["window"]],
        method="hh_keys hces_total = A2 persons x average MPCE x 12 / 1e7 by group (Rs crore/yr, HCES "
        "scale); hces_food / hces_nonfood / hces_durables = A10F totals 981 / 984 / 983 (value per person x "
        "A2 persons x 12 / 1e7). HCES levels are ~44% of NAS PFCE: consumers use the shares.",
    )
    lv = {
        g: float(
            cl.filter(pl.col("household_group") == g)
            .select((pl.col("persons") * pl.col("avg_mpce") * 12.0 / 1e7).sum())
            .item()
        )
        for g in hh.groups
    }
    rows += _key_rows("hces_total", lv, "INR_crore", SURVEY, "derived", pid)
    for code, key in TOTAL_CODES.items():
        if key == "hces_all_items":
            continue
        d = dict(hh.item_groups.filter(pl.col("code") == code).select("household_group", "crore").iter_rows())
        rows += _key_rows(key, {g: float(d[g]) for g in hh.groups}, "INR_crore", SURVEY, "derived", pid)
    # this block's entries by group
    ent = pl.DataFrame(entries).select("row", "col", "ref", "component", "value", "prov_id")
    pid = ctx.prov(
        ref="C1a",
        status="estimated",
        source_id=HCES_SRC,
        inputs=sorted(set(ent["prov_id"].to_list())),
        method="hh_keys pfce_total, c4a_* and c4b_*: this block's COM -> H_* entries summed by group "
        "(pfce_total = all C1a + C4a + C4b + C4d entries; c4a_<component> = C_DWEL entries of that "
        "component; c4b_<component> = C_FINS / C_INSR entries of that component), Rs crore, FY 2023-24 "
        "(priors before balancing).",
    )

    def by_group(df: pl.DataFrame) -> dict[str, float]:
        d = dict(df.group_by("col", maintain_order=True).agg(pl.col("value").sum()).iter_rows())
        return {g: float(d.get(g, 0.0)) for g in hh.groups}

    rows += _key_rows("pfce_total", by_group(ent), "INR_crore", ctx.year, "estimated", pid)
    for ref, comps in (
        ("C4a", ("actual_rent", "imputed_rent", "govt_housing")),
        ("C4b", ("fisim_deposits", "fisim_loans", "explicit_fees", "insurance_service")),
    ):
        for c in comps:
            sub = ent.filter((pl.col("ref") == ref) & (pl.col("component") == c))
            rows += _key_rows(f"{ref.lower()}_{c}", by_group(sub), "INR_crore", ctx.year, "estimated", pid)
    # AIDIS keys
    basis = "2018-06-30 x " + SURVEY
    for key in aidis["key"].unique(maintain_order=True).sort().to_list():
        k = aidis.filter(pl.col("key") == key)
        lv = dict(zip(k["household_group"].to_list(), k["level"].to_list(), strict=True))
        p = hh.pid["aidis_proxy"] if key in ("aidis_equity", "aidis_mf", "aidis_small_savings") else hh.pid["aidis"]
        rows += _key_rows(key, {g: float(lv[g]) for g in hh.groups}, "INR_crore", basis, "estimated", p)
    # FISIM parameters (XR-5), one row each
    v = hh.values
    pid = ctx.prov(
        ref="C1a",
        status="estimated",
        inputs=[hh.pid["fisim_split"]],
        method="hh_keys fisim_params: the parameters and results of the C4b household FISIM split, copied "
        "from its record (reference rate r*, deposit and loan rates in percent; average T52(b) stocks and "
        "FISIM parts in Rs crore; deposit share and the stock-weight sensitivity as ratios), so fincorp "
        "reads them instead of recomputing (CROSS_REVIEW XR-5).",
    )
    for name, val, unit in (
        ("r_star", v["r_star"], "percent"),
        ("r_deposits", v["r_deposits"], "percent"),
        ("r_loans", v["r_loans"], "percent"),
        ("deposits_avg_stock", v["fisim_dep_stock"], "INR_crore"),
        ("loans_avg_stock", v["fisim_loan_stock"], "INR_crore"),
        ("fisim_total", v["fisim"], "INR_crore"),
        ("fisim_deposits", v["fisim_d"], "INR_crore"),
        ("fisim_loans", v["fisim_l"], "INR_crore"),
        ("deposit_share", v["fisim_dep_share"], "ratio"),
        ("deposit_share_stock_weights_sensitivity", v["fisim_dep_share_stocks"], "ratio"),
    ):
        rows.append(
            {
                "series_id": f"fisim_params.{name}",
                "key": "fisim_params",
                "measure": name,
                "household_group": None,
                "area": None,
                "basis_period": ctx.year,
                "value": val,
                "unit": unit,
                "status": "estimated",
                "prov_id": pid,
            }
        )
    df = frame(rows, ["key", "measure", "household_group", "area", "basis_period"])
    return Satellite(
        "C1a",
        df,
        "Reusable household keys by SAM group (levels and shares = level / sum of levels; consumers should normalise "
        "the levels): population, HCES spending, this block's PFCE, C4a and C4b components, AIDIS 2019 asset and "
        "debt keys, FISIM parameters. aidis_equity / aidis_mf / aidis_small_savings equal aidis_fin_assets (no "
        "asset-class split exists in the ingested AIDIS tables); life insurance: use aidis_fin_assets; non-life "
        "premiums: use c4b_insurance_service (HCES 2023-24 has no insurance-premium item).",
        decimals=SAT_DECIMALS,
    )


def aidis_overlap(hh: HH, ov: pl.DataFrame) -> Satellite:
    rows = []
    for r in ov.iter_rows(named=True):
        g, k = r["household_group"], r["aidis_class"]
        tot_k = float(ov.filter(pl.col("aidis_class") == k)["households"].sum())
        tot_g = float(ov.filter(pl.col("household_group") == g)["households"].sum())
        for m, val, unit in (
            ("households", r["households"], "count"),
            ("share_of_aidis_class", r["households"] / tot_k, "ratio"),
            ("share_of_group", r["households"] / tot_g, "ratio"),
        ):
            rows.append(
                {
                    "series_id": f"{k}.{g.lower()}.{m}",
                    "area": r["area"],
                    "aidis_class": k,
                    "household_group": g,
                    "measure": m,
                    "value": val,
                    "unit": unit,
                    "status": "estimated",
                    "prov_id": hh.pid["aidis"],
                }
            )
    return Satellite(
        "C1a",
        frame(rows, ["area", "aidis_class", "household_group", "measure"]),
        "AIDIS 2019 household-expenditure quintile classes -> SAM groups: overlapping households "
        "(HCES 2023-24) and weights",
        decimals=SAT_DECIMALS,
    )


def _state_classes(ctx: BlockContext) -> pl.DataFrame:
    df = ctx.rows(A2, period=SURVEY, item_code=["persons", "avg_mpce"], unit=None, price_basis=None)
    ok = ((pl.col("item_code") == "persons") & (pl.col("unit") == "count")) | (
        (pl.col("item_code") == "avg_mpce") & (pl.col("unit") == "INR")
    )
    bad = df.filter(~ok)
    if bad.height:
        raise SamError(f"A2: unexpected units {bad.select('item_code', 'unit').unique(maintain_order=True).rows()}")
    df = df.filter(~pl.col("household_group").str.ends_with("_all"))
    wide = (
        df.select("geography", "household_group", "item_code", "value")
        .pivot(on="item_code", index=["geography", "household_group"], values="value", maintain_order=True)
        .with_columns(
            pl.col("household_group").str.split("_").list.get(0).alias("area"),
            pl.col("household_group").str.split("_").list.slice(1).list.join("_").alias("fractile"),
        )
        .sort("geography", "household_group")
    )
    if wide.select(pl.any_horizontal(pl.col("persons", "avg_mpce").is_null()).any()).item():
        raise SamError("A2 State rows: a class without persons or MPCE")
    return wide


def state_xwalk(ctx: BlockContext, hh: HH) -> tuple[Satellite, dict[str, float], int]:
    """State x area x State fractile class -> national (all-India) area quintile groups."""
    wide = _state_classes(ctx)
    pid = ctx.prov(
        ref="C1a",
        status="estimated",
        inputs=[hh.pid["persons"], hh.pid["mpce"], hh.pid["window"]],
        method="hh_state_xwalk (gap map C1/R11a note; for rest_of_world R11a and government R10): each State x area x "
        "State fractile class of HCES 2023-24 Table A2 (persons, average MPCE) is placed on the all-India area "
        "quintiles that define the SAM groups. The all-India quintile cut-offs are not published: each is estimated "
        "as the log-midpoint of the adjacent all-India class means (e.g. rural 20% cut = sqrt(MPCE p10_20 x MPCE "
        "p20_30)). A State class's persons are spread uniformly in log MPCE between the log-midpoints to its "
        "neighbouring State classes (first and last class mirrored around their mean) and split across groups by "
        "overlap. weight = share of the class in the group; persons = weight x class persons; consumption = weight x "
        "persons x MPCE x 12 / 1e7 (Rs crore/yr, HCES scale; class mean applied to both parts of a split class). "
        "Rows with hces_class 'all' sum a State x area over its classes. Nominal MPCE, no spatial deflator. "
        "ASSUMPTION (estimated, low).",
    )
    hh.pid["state_xwalk"] = pid
    ind = hh.classes
    cuts: dict[str, list[float]] = {}
    for area in AREAS:
        means = [float(ind.filter(pl.col("hces_class") == f"{area}_{f}")["avg_mpce"].item()) for f in FRACTILES]
        if means != sorted(means):
            raise SamError(f"all-India {area} class means are not increasing: {means}")
        iv = _xwalk.log_intervals(means)
        cuts[area] = [iv[i][1] for i in (2, 4, 6, 8)]  # upper ends of p10_20, p30_40, p50_60, p70_80
        hh.values.update({f"cut_{area}_{j + 1}": math.exp(c) for j, c in enumerate(cuts[area])})
    rows, assigned, reordered = [], {g: 0.0 for g in hh.groups}, 0
    for (geo, area), cls in wide.filter(pl.col("geography") != "IN").group_by("geography", "area", maintain_order=True):
        cls = cls.with_columns(pl.col("fractile").replace_strict({f: i for i, f in enumerate(FRACTILES)}).alias("_o"))
        cls = cls.sort("avg_mpce", "_o")
        if cls["_o"].to_list() != sorted(cls["_o"].to_list()):
            reordered += 1
        iv = _xwalk.log_intervals([float(m) for m in cls["avg_mpce"].to_list()])
        agg: dict[str, list[float]] = {}
        for r, (lo, hi) in zip(cls.iter_rows(named=True), iv, strict=True):
            w = _xwalk.weights(lo, hi, cuts[area])
            cons = r["persons"] * r["avg_mpce"] * 12.0 / 1e7
            for q, wq in enumerate(w, start=1):
                if wq <= 0:
                    continue
                g = group_code(area, q)
                assigned[g] += wq * r["persons"]
                a = agg.setdefault(g, [0.0, 0.0])
                a[0] += wq * r["persons"]
                a[1] += wq * cons
                sid = f"{geo.lower()}.{area}.{r['fractile']}.{g.lower()}"
                for m, val, unit in (
                    ("weight", wq, "ratio"),
                    ("persons", wq * r["persons"], "count"),
                    ("consumption", wq * cons, "INR_crore"),
                ):
                    rows.append(
                        {
                            "series_id": f"{sid}.{m}",
                            "geography": geo,
                            "area": area,
                            "hces_class": r["fractile"],
                            "household_group": g,
                            "measure": m,
                            "value": val,
                            "unit": unit,
                            "status": "estimated",
                            "prov_id": pid,
                        }
                    )
        tot = sum(v[1] for v in agg.values())
        for g, (p, c) in sorted(agg.items()):
            sid = f"{geo.lower()}.{area}.all.{g.lower()}"
            for m, val, unit in (
                ("persons", p, "count"),
                ("consumption", c, "INR_crore"),
                ("consumption_share", c / tot, "ratio"),
            ):
                rows.append(
                    {
                        "series_id": f"{sid}.{m}",
                        "geography": geo,
                        "area": area,
                        "hces_class": "all",
                        "household_group": g,
                        "measure": m,
                        "value": val,
                        "unit": unit,
                        "status": "estimated",
                        "prov_id": pid,
                    }
                )
    sat = Satellite(
        "C1a",
        frame(rows, ["geography", "area", "hces_class", "household_group", "measure"]),
        "HCES 2023-24 State x area x State fractile class -> SAM groups (all-India area quintiles): "
        "weights, persons and consumption (Rs crore/yr, HCES scale)",
        decimals=SAT_DECIMALS,
    )
    return sat, assigned, reordered


def national_xwalk(ctx: BlockContext, hh: HH) -> Satellite:
    """SAM group x national (rural + urban) MPCE person quintile: person shares (XR-10)."""
    pid = ctx.prov(
        ref="C1a",
        status="estimated",
        inputs=[hh.pid["persons"], hh.pid["mpce"], hh.pid["window"]],
        method="hh_national_quintile_xwalk (CROSS_REVIEW XR-10; for factors F1a/F2/F3c and taxes T3a IFPRI priors, "
        "which are by national person quintile): the 24 all-India HCES 2023-24 A2 classes (rural and urban) are "
        "spread uniformly in log MPCE between the log-midpoints of adjacent class means within their area (first and "
        "last class mirrored around the mean); the national quintile cut-offs are the MPCE levels at which the "
        "pooled persons reach 20/40/60/80% (bisection); each class's persons are split by overlap and summed by SAM "
        "group. share = persons of the group in national quintile q / persons of the group. Nominal MPCE, no rural/"
        "urban price deflator. ASSUMPTION (estimated, low).",
    )
    cl = hh.classes
    ivs, persons, groups = [], [], []
    for area in AREAS:
        sub = cl.filter(pl.col("area") == area)
        ivs += _xwalk.log_intervals([float(m) for m in sub["avg_mpce"].to_list()])
        persons += [float(p) for p in sub["persons"].to_list()]
        groups += sub["household_group"].to_list()
    cuts = _xwalk.quantile_cuts(ivs, persons, [0.2, 0.4, 0.6, 0.8])
    hh.values.update({f"national_cut_{j + 1}": math.exp(c) for j, c in enumerate(cuts)})
    acc = {(g, q): 0.0 for g in hh.groups for q in range(1, 6)}
    for (lo, hi), p, g in zip(ivs, persons, groups, strict=True):
        for q, w in enumerate(_xwalk.weights(lo, hi, cuts), start=1):
            acc[(g, q)] += w * p
    rows = []
    for g in hh.groups:
        tot = sum(acc[(g, q)] for q in range(1, 6))
        for q in range(1, 6):
            for m, val, unit in (("persons", acc[(g, q)], "count"), ("share", acc[(g, q)] / tot, "ratio")):
                rows.append(
                    {
                        "series_id": f"{g.lower()}.q{q}.{m}",
                        "household_group": g,
                        "national_quintile": f"q{q}",
                        "measure": m,
                        "value": val,
                        "unit": unit,
                        "status": "estimated",
                        "prov_id": pid,
                    }
                )
    for j, c in enumerate(cuts, start=1):
        rows.append(
            {
                "series_id": f"cut.q{j}_q{j + 1}",
                "household_group": None,
                "national_quintile": f"q{j}|q{j + 1}",
                "measure": "cut_mpce",
                "value": math.exp(c),
                "unit": "INR",
                "status": "estimated",
                "prov_id": pid,
            }
        )
    return Satellite(
        "C1a",
        frame(rows, ["household_group", "national_quintile", "measure"]),
        "Persons of each SAM group by national (rural+urban) MPCE person quintile q1..q5, and the "
        "estimated national cut-offs (Rs per person per 30 days)",
        decimals=SAT_DECIMALS,
    )


def hces_nas_ratio(ctx: BlockContext, hh: HH) -> tuple[Satellite, dict[str, float]]:
    """HCES-scale spending vs SUT PFCE by product and commodity (gap-map C1a note: publish the H1 gap)."""
    km = (
        hh.keymap.filter(pl.col("ref") != "excluded")
        .select("product", "hces_item", "key_quality")
        .unique(subset=["product", "hces_item"], maintain_order=True)
    )
    pf = dict(hh.pfce.select("product", "value").iter_rows())
    allin = dict(hh.item_groups.group_by("code", maintain_order=True).agg(pl.col("crore").sum()).iter_rows())
    users: dict[str, list[str]] = {}
    for p, i, _ in km.iter_rows():
        users.setdefault(i, []).append(p)
    hces: dict[str, float] = {}
    for i, ps in users.items():
        tot = sum(pf[p] for p in ps)
        for p in ps:
            hces[p] = hces.get(p, 0.0) + allin.get(i, 0.0) * pf[p] / tot
    quality = {
        p: ("proxy" if "proxy" in km.filter(pl.col("product") == p)["key_quality"].to_list() else "direct")
        for p in hces
    }
    pid = ctx.prov(
        ref="C1a",
        status="estimated",
        source_id=HCES_SRC,
        inputs=[hh.pid["a10f"], hh.pid["persons"], *sorted(set(hh.pfce["prov_id"])), hh.pid["window"]],
        method="c1a_hces_nas_ratio (gap map C1a note, hard problem H1): HCES 2023-24 spending at HCES scale (A10F "
        "value per person x A2 persons x 12 / 1e7, all-India) on the key items of each SUT product, against the SUT "
        "2023-24 PFCE of that product; an item that keys several products is split across them in proportion to their "
        "SUT PFCE (ASSUMPTION). Commodity rows sum the products of a commodity; C_FINS and C_INSR have no HCES key.",
    )
    rows, ratios = [], {}
    com = dict(hh.pfce.select("product", "commodity").iter_rows())
    for level, keyf in (("product", lambda p: p), ("commodity", lambda p: com[p])):
        agg: dict[str, list] = {}
        for p in sorted(hces):
            a = agg.setdefault(keyf(p), [0.0, 0.0, set()])
            a[0] += hces[p]
            a[1] += pf[p]
            a[2].add(quality[p])
        for k, (hv, pv, qs) in sorted(agg.items()):
            q = "proxy" if "proxy" in qs else "direct"
            if level == "commodity":
                ratios[k] = hv / pv
            for m, val, unit in (
                ("hces_value", hv, "INR_crore"),
                ("sut_pfce", pv, "INR_crore"),
                ("ratio", hv / pv, "ratio"),
            ):
                rows.append(
                    {
                        "series_id": f"{level}.{k.lower()}.{m}",
                        "level": level,
                        "code": k,
                        "key_quality": q,
                        "measure": m,
                        "value": val,
                        "unit": unit,
                        "status": "estimated",
                        "prov_id": pid,
                    }
                )
    return (
        Satellite(
            "C1a",
            frame(rows, ["level", "code", "key_quality", "measure"]),
            "HCES-scale spending vs SUT PFCE by product and commodity (the H1 gap)",
            decimals=SAT_DECIMALS,
        ),
        ratios,
    )


def npish_memo(ctx: BlockContext) -> tuple[Satellite, float]:
    df = ctx.rows(ICIO, period="2022-23", unit=None, price_basis=None)
    pat = re.compile(r"^icio\.((dom|imp)\.[^.]+|tls)\.(npish|hfce)\.current$")
    df = df.filter(pl.col("series_id").map_elements(lambda s: bool(pat.match(s)), return_dtype=pl.Boolean))
    if df.height == 0 or set(df["unit"].to_list()) != {"USD_million"}:
        raise SamError(f"ICIO NPISH/HFCE columns: {df.height} rows, units {sorted(set(df['unit'].to_list()))}")
    df = df.with_columns(pl.col("series_id").str.split(".").list.get(-2).alias("col"))
    npish = float(df.filter(pl.col("col") == "npish")["value"].sum())
    hfce = float(df.filter(pl.col("col") == "hfce")["value"].sum())
    pid = ctx.prov(
        ref="C4c",
        status="estimated",
        inputs=sorted(set(df["prov_id"].to_list())),
        method="Gap map C4c (NPISH final consumption inside PFCE), implemented as embedded + memo: NPISH consumption "
        "is not separable in any NAS 2026 table and is already inside the SUT PFCE by product, so C1a/C4a/C4b/C4d "
        "spread it with each product's household key (writing C4c entries would double count). Memo only, never "
        "used in a SAM value: OECD ICIO India 2022-23 (international, old base), NPISH column = sum of domestic + "
        "imported icio.*.npish rows + icio.tls.npish; HFCE likewise; share = NPISH / (NPISH + HFCE). US$ million as "
        "published (a ratio needs no conversion).",
    )
    share = npish / (npish + hfce)
    rows = [
        {"series_id": "npish_fce", "measure": "npish_fce", "period": "2022-23", "value": npish, "unit": "USD_million"},
        {"series_id": "hfce", "measure": "hfce", "period": "2022-23", "value": hfce, "unit": "USD_million"},
        {
            "series_id": "npish_share",
            "measure": "npish_share_of_hfce_plus_npish",
            "period": "2022-23",
            "value": share,
            "unit": "ratio",
        },
    ]
    for r in rows:
        r.update(status="estimated", prov_id=pid)
    return Satellite(
        "C4c",
        frame(rows, ["measure", "period"]),
        "C4c memo: NPISH final consumption share (OECD ICIO 2022-23); NPISH stays embedded in PFCE",
        decimals=SAT_DECIMALS,
    ), share


def imputed_rent_sensitivity(ctx: BlockContext, hh: HH, entries: list[dict]) -> Satellite:
    """C4a imputed rent under the rural/urban split of the gap map's AIDIS fallback (plan s.1, s.5.1): the
    sensitivity band for the largest estimated distribution (the SAM uses HCES item 539)."""
    sids = [f"pn.asset_share_building.{a}.all" for a in AREAS]
    pn = ctx.rows(AIDIS_PN, series_id=sids, period=AIDIS_PERIOD, unit="percent", price_basis="n/a")
    ava = ctx.rows(
        AIDIS_PN,
        series_id=[f"pn.ava_per_hh.{a}.all.current" for a in AREAS],
        period=AIDIS_PERIOD,
        unit="INR",
        price_basis="current",
    )
    share = dict(pn.select("series_id", "value").iter_rows())
    assets = dict(ava.select("series_id", "value").iter_rows())
    hhs = {a: float(hh.classes.filter(pl.col("area") == a)["households"].sum()) for a in AREAS}
    bld = {
        a: share[f"pn.asset_share_building.{a}.all"] / 100 * assets[f"pn.ava_per_hh.{a}.all.current"] * hhs[a]
        for a in AREAS
    }
    imp = {r["col"]: r["value"] for r in entries if r["ref"] == "C4a" and r["component"] == "imputed_rent"}
    total = sum(imp.values())
    area_tot = {a: sum(v for g, v in imp.items() if area_of(g) == a) for a in AREAS}
    pid = ctx.prov(
        ref="C4a",
        status="estimated",
        source_id=HCES_SRC,
        inputs=[
            hh.pid["c4a_imputed_rent"],
            *sorted(set(pn["prov_id"].to_list()) | set(ava["prov_id"].to_list())),
            hh.pid["households"],
        ],
        method="C4a imputed-rent sensitivity (satellite c4a_imputed_rent_sensitivity, households-2): the C4a "
        "imputed_rent total split between rural and urban by the AIDIS 2019 building-value proxy (press-note share "
        "of buildings in total assets x average assets per household x HCES 2023-24 A2 households of the area) "
        "instead of HCES item 539, keeping the HCES 539 distribution within each area. Memo only (the SAM entries "
        "use HCES 539); diff = variant - SAM prior.",
    )
    rows = []
    for g in hh.groups:
        a = area_of(g)
        variant = total * bld[a] / sum(bld.values()) * imp[g] / area_tot[a]
        for m, val in (("sam_prior", imp[g]), ("aidis_building_variant", variant), ("diff", variant - imp[g])):
            rows.append(
                {
                    "series_id": f"{m}.{g.lower()}",
                    "measure": m,
                    "household_group": g,
                    "value": val,
                    "unit": "INR_crore",
                    "status": "estimated",
                    "prov_id": pid,
                }
            )
    for a in AREAS:
        for m, val in (
            ("rural_urban_share_sam_prior", area_tot[a] / total),
            ("rural_urban_share_aidis_building", bld[a] / sum(bld.values())),
        ):
            rows.append(
                {
                    "series_id": f"{m}.{a}",
                    "measure": m,
                    "household_group": None,
                    "value": val,
                    "unit": "ratio",
                    "status": "estimated",
                    "prov_id": pid,
                }
            )
    return Satellite(
        "C4a",
        frame(rows, ["measure", "household_group"]),
        "C4a imputed rent: SAM prior (HCES 539) vs the AIDIS building-value rural/urban split (band)",
        decimals=SAT_DECIMALS,
    )


def fisim_split_sensitivity(ctx: BlockContext, hh: HH, entries: list[dict], keys: pl.DataFrame) -> Satellite:
    """C4b household FISIM by group under other deposit/loan splits (verification V-HH-3, for Checkpoint B). The
    SAM keeps the XR-5 reference-rate split (binding); this memo shows how far the loan leg could be overstated."""
    v = hh.values
    hfc, hpids = [], []
    for date in ("2023-03-31", "2024-03-31"):
        x, p = ctx.value(T52, "t52b.fl_ofi_hfc.current", period=date, vintage=VINTAGE)
        hfc, hpids = [*hfc, x], [*hpids, p]
    hfc_avg = sum(hfc) / 2
    rs, rd, rl = v["r_star"], v["r_deposits"], v["r_loans"]
    dep, loans, fisim = v["fisim_dep_stock"], v["fisim_loan_stock"], v["fisim"]
    raw_d, raw_l = (rs - rd) / 100 * dep, (rl - rs) / 100 * loans
    wd, wl_x = (rs - rd) * dep, (rl - rs) * (loans - hfc_avg)
    dshare = {
        "xr5_sam_prior": v["fisim_dep_share"],
        "stock_weights": v["fisim_dep_share_stocks"],
        "loans_excl_hfc": wd / (wd + wl_x),
        "deposits_only": 1.0,
    }

    def key(name: str) -> dict[str, float]:
        k = keys.filter(pl.col("key") == name)
        return dict(zip(k["household_group"].to_list(), k["share"].to_list(), strict=True))

    kd, kl = key(FISIM_D_KEY), key("aidis_inst_loans")
    prior = {g: 0.0 for g in hh.groups}
    for r in entries:
        if r["ref"] == "C4b" and r["component"] in ("fisim_deposits", "fisim_loans"):
            prior[r["col"]] += r["value"]
    variants = {m: {g: fisim * (s * kd[g] + (1 - s) * kl[g]) for g in hh.groups} for m, s in dshare.items()}
    off = {g: variants["xr5_sam_prior"][g] - prior[g] for g in hh.groups}
    if max(abs(x) for x in off.values()) > 1e-6:
        raise SamError(f"c4b_fisim_split_sensitivity: the XR-5 variant does not reproduce the C4b entries: {off}")
    pid = ctx.prov(
        ref="C4b",
        status="estimated",
        source_id=NAS_SRC,
        inputs=[hh.pid["fisim_split"], hh.pid["aidis"], *sorted(set(hpids))],
        method="C4b FISIM split sensitivity (satellite c4b_fisim_split_sensitivity; verification V-HH-3; memo for "
        "Checkpoint B, not used in any SAM value). The SAM splits NAS 1.13 household (PFCE) FISIM "
        f"Rs {fisim:,.2f} crore with the XR-5 reference-rate formula on ALL household deposits and liabilities "
        "(T52(b) fl). SNA books FISIM on housing loans as intermediate consumption of ownership of dwellings and on "
        "loans to unincorporated enterprises as their intermediate consumption; only consumer-credit FISIM is PFCE, "
        "so the XR-5 loan share probably overstates the PFCE loan leg. No purpose split of household loans is "
        "ingested (BSR-1 gives only the personal-loan share of SCB credit, which includes housing loans), so a "
        "consumer-credit-only variant cannot be built. Variants, each keeping the NAS total and the SAM group keys "
        f"(deposits {FISIM_D_KEY}, loans aidis_inst_loans): xr5_sam_prior (deposit share "
        f"{dshare['xr5_sam_prior']:.6f}, equals the C4b entries); stock_weights (end-March 2024 stocks, "
        f"{dshare['stock_weights']:.6f}); loans_excl_hfc (XR-5 with housing-finance-company loans, T52(b) "
        f"fl_ofi_hfc averaged over 31 Mar 2023 and 2024 = ({hfc[0]:,.2f} + {hfc[1]:,.2f}) / 2 = Rs {hfc_avg:,.2f} "
        "crore, removed from L: the only housing-loan stock the data separate, and bank housing loans stay in L (the "
        "HFC stock falls between the two dates as HDFC Ltd merged into HDFC Bank in July 2023), so a lower bound "
        f"on the correction; {dshare['loans_excl_hfc']:.6f}); "
        "deposits_only (all PFCE FISIM on deposits: the upper bound). diff = variant - SAM prior. Also: the raw "
        f"rate-based FISIM (r* - r_D) x D + (r_L - r*) x L = {raw_d:,.2f} + {raw_l:,.2f} = {raw_d + raw_l:,.2f} "
        f"crore is {(raw_d + raw_l) / fisim:.4f} x NAS PFCE FISIM alone (household producers' FISIM would come on "
        "top), so the formula serves only as a split rule.",
    )
    rows: list[dict] = []

    def add(sid: str, variant: str | None, measure: str, g: str | None, val: float, unit: str) -> None:
        rows.append(
            {
                "series_id": sid,
                "variant": variant,
                "measure": measure,
                "household_group": g,
                "value": val,
                "unit": unit,
                "status": "estimated",
                "prov_id": pid,
            }
        )

    for m, s in dshare.items():
        add(f"deposit_share.{m}", m, "deposit_share", None, s, "ratio")
        add(f"fisim_deposits.{m}", m, "fisim_deposits", None, fisim * s, "INR_crore")
        add(f"fisim_loans.{m}", m, "fisim_loans", None, fisim * (1 - s), "INR_crore")
        rural = sum(x for g, x in variants[m].items() if area_of(g) == "rural")
        add(f"rural_share.{m}", m, "rural_share", None, rural / fisim, "ratio")
        for g in hh.groups:
            add(f"value.{m}.{g.lower()}", m, "value", g, variants[m][g], "INR_crore")
            if m != "xr5_sam_prior":
                add(f"diff.{m}.{g.lower()}", m, "diff", g, variants[m][g] - prior[g], "INR_crore")
    for name, val in (
        ("raw_rate_fisim_deposits", raw_d),
        ("raw_rate_fisim_loans", raw_l),
        ("raw_rate_fisim_total", raw_d + raw_l),
        ("hfc_loans_avg_stock", hfc_avg),
        ("loans_excl_hfc_avg_stock", loans - hfc_avg),
    ):
        add(f"param.{name}", None, name, None, val, "INR_crore")
    add("param.raw_rate_to_nas_ratio", None, "raw_rate_to_nas_ratio", None, (raw_d + raw_l) / fisim, "ratio")
    return Satellite(
        "C4b",
        frame(rows, ["variant", "measure", "household_group"]),
        "C4b household FISIM by group: SAM prior (XR-5 split) vs stock weights, loans excluding HFC housing loans, "
        "and deposits only (V-HH-3; memo for Checkpoint B)",
        decimals=SAT_DECIMALS,
    )


def food_stik(ctx: BlockContext, hh: HH) -> tuple[Satellite, dict[str, float]]:
    """S8: free PDS grain by group (quantities from HCES, valued at the SUT GFCE unit value), plus memo rows."""
    q = ctx.rows(A10F, period=SURVEY, item_code="qty_per_person_30d", unit=None, price_basis=None)
    q = q.with_columns(pl.col("series_id").str.split(".").list.get(2).alias("code")).filter(
        pl.col("code").is_in(list(FREE_ITEMS))
    )
    if set(q["unit"].to_list()) != {"tonnes"}:
        raise SamError(f"A10F free-item quantities: units {sorted(set(q['unit'].to_list()))} (expected tonnes)")
    qpid = sorted(set(q["prov_id"].to_list()))
    if len(qpid) != 1:
        raise SamError(f"A10F quantities: several provenance records {qpid}")
    q = q.join(
        hh.classes.select(
            pl.col("hces_class").alias("household_group"), "persons", pl.col("household_group").alias("group")
        ),
        on="household_group",
        how="left",
        maintain_order="left",
    ).with_columns((pl.col("value") * pl.col("persons") * 12.0).alias("tonnes"))
    tons = {
        (c, g): v
        for c, g, v in q.group_by("code", "group", maintain_order=True).agg(pl.col("tonnes").sum()).iter_rows()
    }
    labels = dict(q.select("code", "item_label").unique(maintain_order=True).iter_rows())
    rice, rpid = ctx.value(USE, "use.gfce.sut_p001.current", vintage=VINTAGE)
    wheat, wpid = ctx.value(USE, "use.gfce.sut_p002.current", vintage=VINTAGE)
    pid = ctx.prov(
        ref="S8",
        status="estimated",
        inputs=[*qpid, hh.pid["persons"], rpid, wpid, hh.pid["window"]],
        source_id=HCES_SRC,
        method="Gap map S8 (satellite; not a SAM cell, never added to PFCE or household income, D0-5): free PDS grain "
        "received by each SAM group = HCES 2023-24 A10F quantities of items 061 rice-free and 062 wheat-free (tonnes "
        "per person per 30 days x A2 persons x 12), valued at a uniform national GFCE unit value per grain, i.e. "
        f"quantity shares x SUT {ctx.year} GFCE on paddy (use.gfce.sut_p001.current, Rs {rice:,.2f} crore) and wheat "
        f"(use.gfce.sut_p002.current, Rs {wheat:,.2f} crore), the same values government's C2a writes to G_CEN. The "
        "unit values are implied (GFCE / HCES quantity), since no GFCE unit value is published.",
    )
    rows, totals = [], {}
    for code, gfce, name in (("061", rice, "rice_free"), ("062", wheat, "wheat_free")):
        tq = sum(tons.get((code, g), 0.0) for g in hh.groups)
        totals[f"{name}_tonnes"] = tq
        totals[f"{name}_value"] = gfce
        for g in hh.groups:
            t = tons.get((code, g), 0.0)
            for m, val, unit in (("qty", t, "tonnes"), ("value", gfce * t / tq, "INR_crore")):
                rows.append(
                    {
                        "series_id": f"{name}.{m}.{g.lower()}",
                        "item": name,
                        "hces_item": code,
                        "measure": m,
                        "household_group": g,
                        "value": val,
                        "unit": unit,
                        "status": "estimated",
                        "prov_id": pid,
                    }
                )
        rows.append(
            {
                "series_id": f"{name}.unit_value_inr_per_kg",
                "item": name,
                "hces_item": code,
                "measure": "unit_value_inr_per_kg",
                "household_group": None,
                "value": gfce * 1e7 / (tq * 1000.0),
                "unit": "INR",
                "status": "estimated",
                "prov_id": pid,
            }
        )
    for g in hh.groups:
        v = sum(r["value"] for r in rows if r["measure"] == "value" and r["household_group"] == g)
        rows.append(
            {
                "series_id": f"total.value.{g.lower()}",
                "item": "total",
                "hces_item": None,
                "measure": "value",
                "household_group": g,
                "value": v,
                "unit": "INR_crore",
                "status": "estimated",
                "prov_id": pid,
            }
        )
    # memo: other free items valued at A10SW all-India R/U imputed unit values; HCES-valued free rice / wheat
    sw = ctx.rows(A10SW, period=SURVEY, geography="IN", unit=None, price_basis=None)
    sw = sw.with_columns(pl.col("series_id").str.split(".").list.get(2).alias("code")).filter(
        pl.col("code").is_in(list(FREE_ITEMS))
    )
    swv = {(r["code"], r["item_code"], r["household_group"]): r["value"] for r in sw.iter_rows(named=True)}
    mpid = ctx.prov(
        ref="S8",
        status="estimated",
        inputs=[*qpid, hh.pid["persons"], *sorted(set(sw["prov_id"].to_list())), hh.pid["window"]],
        method="S8 memo rows (no SAM counterpart; the SUT has GFCE only on paddy and wheat among food products, so "
        "where NAS books State free pulses, gram, salt, sugar, oil and free coarse grains is an open NAD question): "
        "HCES 2023-24 A10F quantities of items 070-075 by group valued at the A10SW all-India rural/urban imputed "
        "unit value (A10SW value per person / quantity per person); items whose A10SW quantity rounds to 0 tonnes "
        "are not valued. hces_valued rows: free rice / wheat at A10SW all-India imputed values (value per person x "
        "area persons x 12 / 1e7), the check against the SUT GFCE.",
    )
    unvalued = []
    for code in FREE_ITEMS[2:]:
        name = f"memo_{code}"
        for g in hh.groups:
            t = tons.get((code, g), 0.0)
            ag = f"{area_of(g)}_all"
            qv, vv = swv.get((code, "qty_per_person_30d", ag)), swv.get((code, "value_per_person_30d", ag))
            rows.append(
                {
                    "series_id": f"{name}.qty.{g.lower()}",
                    "item": labels.get(code, code),
                    "hces_item": code,
                    "measure": "qty",
                    "household_group": g,
                    "value": t,
                    "unit": "tonnes",
                    "status": "estimated",
                    "prov_id": mpid,
                }
            )
            if qv and vv is not None:
                rows.append(
                    {
                        "series_id": f"{name}.value.{g.lower()}",
                        "item": labels.get(code, code),
                        "hces_item": code,
                        "measure": "value",
                        "household_group": g,
                        "value": t * (vv / qv) / 1e7,
                        "unit": "INR_crore",
                        "status": "estimated",
                        "prov_id": mpid,
                    }
                )
            elif code not in unvalued:
                unvalued.append(code)
    if unvalued:
        ctx.log(f"S8 memo: A10SW quantity rounds to 0 for items {unvalued}: quantities only, no value")
    totals["memo_unvalued"] = float(len(unvalued))
    persons_area = {a: float(hh.classes.filter(pl.col("area") == a)["persons"].sum()) for a in AREAS}
    for code, name in (("061", "rice_free"), ("062", "wheat_free")):
        v = sum(swv[(code, "value_per_person_30d", f"{a}_all")] * persons_area[a] * 12.0 / 1e7 for a in AREAS)
        totals[f"{name}_hces_valued"] = v
        rows.append(
            {
                "series_id": f"{name}.hces_valued",
                "item": name,
                "hces_item": code,
                "measure": "hces_valued",
                "household_group": None,
                "value": v,
                "unit": "INR_crore",
                "status": "estimated",
                "prov_id": mpid,
            }
        )
    hh.pid.update(s8=pid, s8_memo=mpid)
    return (
        Satellite(
            "S8",
            frame(rows, ["item", "hces_item", "measure", "household_group"]),
            "S8: free PDS rice and wheat by SAM group (tonnes; Rs crore at the SUT GFCE unit value) and memo "
            "rows (other free items; HCES-valued grain)",
            decimals=SAT_DECIMALS,
        ),
        totals,
    )
