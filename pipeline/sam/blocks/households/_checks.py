"""Households block: constraints (official totals) and control-total checks. Private helper."""

from __future__ import annotations

import polars as pl

from pipeline.sam.framework import BlockContext, constraint

from ._data import (
    A2,
    CMS,
    H596,
    HCES_SRC,
    HH,
    IFPRI,
    NAS11,
    NAS51,
    NAS113,
    NAS114,
    NAS813,
    SUPPLY,
    SURVEY,
    UNION_EXP,
    USE,
    VINTAGE,
    area_of,
)

FOOD_SUBSIDY_TOL = 0.30  # S8 vs the Union cash food subsidy: a concept gap, not rounding (docstring of checks)
PLAUSIBILITY_TOL = 10.0  # percentage points: this SAM's shares vs IFPRI 2022/23 (old base, other quintiles)
HCES_ROUNDING = 1e-5  # relative: A10F prints values per person to 2 decimals, so item sums miss totals slightly
XWALK_TOL = 0.02  # relative: State class lists re-placed on all-India cut-offs vs the all-India group persons


def constraints(ctx: BlockContext, hh: HH) -> list[dict]:
    """Official totals this block's split must respect. Production's per-commodity PFCE targets (pfce.*) are not
    re-declared (CROSS_REVIEW XR-15): they are tested against ctx.block_constraints('production')."""
    com, hhs = ctx.accounts.in_group("COM"), ctx.accounts.in_group("HH")
    nas, npid = ctx.value(NAS11, "s1_1.pfce.current", vintage=VINTAGE)
    p = ctx.prov(
        ref="C1a",
        status="official",
        inputs=[npid],
        method="Constraint hh.c1.total: all COM -> H_* entries (C1a + C4a + C4b + C4d) sum to NAS 2026 "
        "Statement 1.1 PFCE at current prices, as published; tolerance Rs 1 crore (the SUT product rows sum "
        "to 1,64,15,547, 0.48 above NAS: rounding).",
    )
    out = [
        constraint(
            "hh.c1.total",
            "C1a",
            com,
            hhs,
            nas,
            prov_id=p,
            tol_abs=1.0,
            description="NAS 1.1 PFCE = sum of all COM -> household-group entries",
        )
    ]
    p = ctx.prov(
        ref="C4b",
        status="official",
        inputs=[hh.pid["fisim_nas"]],
        method="Constraint hh.c4b.fisim: C_FINS <- H_* components fisim_deposits + fisim_loans sum to NAS 2026 "
        "Statement 1.13 FISIM allocated to PFCE, as published (tolerance Rs 1 crore).",
    )
    out.append(
        constraint(
            "hh.c4b.fisim",
            "C4b",
            ["C_FINS"],
            hhs,
            hh.values["fisim"],
            prov_id=p,
            tol_abs=1.0,
            refs=["C4b"],
            components=["fisim_deposits", "fisim_loans"],
            description="NAS 1.13 household FISIM = FISIM on deposits + on loans over the 10 groups",
        )
    )
    p = ctx.prov(
        ref="C4a",
        status="official",
        inputs=[hh.pid["c4a_govt_supply"]],
        method="Constraint hh.c4a.govt_housing: C_DWEL <- H_* component govt_housing sums to the SUT 2023-24 "
        "supply of product 144 (ownership of dwellings) by industry 67 (public administration), as published; "
        "tolerance Rs 1 crore (one SUT cell, production's allowance).",
    )
    out.append(
        constraint(
            "hh.c4a.govt_housing",
            "C4a",
            ["C_DWEL"],
            hhs,
            hh.values["c4a_govt"],
            prov_id=p,
            tol_abs=1.0,
            refs=["C4a"],
            components=["govt_housing"],
            description="Government-provided housing = SUT supply of p144 by industry 67",
        )
    )
    # status `estimated`, the inputs of the C4a imputed_rent entries' record (verification V-HH-1): no NAS table
    # separates tenant and owner-occupied rent, so applying the HCES ratio to the SUT level is a modelling step
    p = ctx.prov(
        ref="C4a",
        status="estimated",
        source_id=HCES_SRC,
        inputs=[
            hh.pid["pfce_p144"],
            hh.pid["c4a_govt_supply"],
            hh.pid["c4a_own_supply"],
            hh.pid["a10f"],
            hh.pid["persons"],
            hh.pid["window"],
        ],
        method=f"Constraint hh.c4a.imputed_rent (CROSS_REVIEW XR-22; kind band, +-10%): C_DWEL <- H_* component "
        f"imputed_rent stays within 10% of its prior total, (SUT PFCE p144 - SUT supply p144 by industry 67) x "
        f"(1 - r), r = HCES V520/(V520+V539) = {hh.values['c4a_ratio']:.9f}, so balancing cannot move owner-"
        "occupied rent (C4a, consumption) far from the imputed-rent income factors keys on it (F3a); factors "
        "declares the per-group F3a bands. The target is an estimate, like the imputed_rent entries it bounds: "
        "no NAS table separates tenant and owner-occupied rent, so the HCES 2023-24 rent ratio applied to the SUT "
        "level is a modelling assumption (same inputs as the entries' record).",
    )
    out.append(
        constraint(
            "hh.c4a.imputed_rent",
            "C4a",
            ["C_DWEL"],
            hhs,
            hh.values["c4a_imputed"],
            prov_id=p,
            tol_rel=0.10,
            kind="band",
            refs=["C4a"],
            components=["imputed_rent"],
            description="Imputed rent of owner-occupiers within 10% of its prior (link to F3a)",
        )
    )
    return out


def _entries_df(entries: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(entries).select("row", "col", "ref", "component", "value")


def checks(ctx: BlockContext, hh: HH, entries: list[dict], s8: dict[str, float], assigned: dict[str, float]) -> None:
    """Every total this block builds, against figures read from clean data (or production's official records).
    Directional checks (C4d) compare signs (+1 rising, -1 falling): the NSS reports differ in year, unit and class."""
    e = _entries_df(entries)
    tot = float(e["value"].sum())

    def v(ds: str, sid: str, **kw) -> tuple[float, str]:
        return ctx.value(ds, sid, vintage=kw.pop("vintage", VINTAGE), **kw)

    def s(ref: str | None = None, row: str | None = None, comps: list[str] | None = None) -> float:
        d = e
        if ref:
            d = d.filter(pl.col("ref") == ref)
        if row:
            d = d.filter(pl.col("row") == row)
        if comps:
            d = d.filter(pl.col("component").is_in(comps))
        return float(d["value"].sum())

    c = ctx.check
    t, p = v(NAS11, "s1_1.pfce.current")
    c("pfce.total_nas11", "All COM -> H_* entries vs NAS 1.1 PFCE", tot, t, target_prov_id=p, tol_abs=1.0)
    c(
        "pfce.total_sut",
        "All COM -> H_* entries vs the SUT 'Total Use' PFCE row",
        tot,
        hh.values["pfce_total_row"],
        target_prov_id=hh.pid["pfce_total_row"],
        tol_abs=0.01,
    )
    t, p = v(NAS114, "s1_14.households_npish.final_consumption_expenditure.current")
    c(
        "pfce.total_nas114",
        "All COM -> H_* entries vs NAS 1.14 households+NPISH FCE",
        tot,
        t,
        target_prov_id=p,
        tol_abs=1.0,
    )
    prod = ctx.block_constraints("production").filter(pl.col("constraint_id").str.starts_with("pfce."))
    for r in prod.filter(pl.col("target") != 0).iter_rows(named=True):
        com = r["rows"]
        c(
            f"pfce.{com.lower()}",
            f"{com}: sum over the 10 groups vs production's SUT PFCE target",
            s(row=com),
            r["target"],
            target_prov_id=r["prov_id"],
            tol_abs=r["tol_abs"],
        )
    # C4a
    t, p = v(SUPPLY, "supply.output.sut_p144.sut_i67.current")
    c(
        "c4a.govt_housing",
        "C4a govt_housing vs SUT supply of p144 by industry 67",
        s("C4a", comps=["govt_housing"]),
        t,
        target_prov_id=p,
        tol_abs=0.01,
    )
    t, p = v(NAS813, "s8_13.ownership_of_dwellings.output.current")
    c(
        "c4a.owner_tenant_vs_nas813",
        "C4a actual + imputed rent vs NAS 8.13 output of ownership of dwellings",
        s("C4a", comps=["actual_rent", "imputed_rent"]),
        t,
        target_prov_id=p,
        tol_abs=1.0,
    )
    # C4b
    fis = s("C4b", comps=["fisim_deposits", "fisim_loans"])
    t, p = v(NAS113, "s1_13.private_final_consumption_expenditure.current")
    c("c4b.fisim_nas113", "C4b FISIM components vs NAS 1.13 FISIM to PFCE", fis, t, target_prov_id=p, tol_abs=0.01)
    t, p = v(NAS51, "s5_1.financial_intermediation_services_indirectly_measured.current")
    c("c4b.fisim_nas51", "C4b FISIM components vs NAS 5.1 FISIM", fis, t, target_prov_id=p, tol_abs=0.01)
    for com, prod_code in (
        ("C_FINS", "sut_p142"),
        ("C_INSR", "sut_p143"),
        ("C_EDUC", "sut_p152"),
        ("C_HLTH", "sut_p153"),
        ("C_DWEL", "sut_p144"),
    ):
        r = hh.pfce.filter(pl.col("product") == prod_code).row(0, named=True)
        c(
            f"sut.{com.lower()}",
            f"{com} entries vs SUT PFCE {r['series_id']}",
            s(row=com),
            r["value"],
            target_prov_id=r["prov_id"],
            tol_abs=0.01,
        )
    # C4d vs NAS 5.1 (COICOP, domestic concept)
    t, p = v(NAS51, "s5_1.education.current")
    c("c4d.c_educ_nas51", "C_EDUC entries vs NAS 5.1 education", s(row="C_EDUC"), t, target_prov_id=p, tol_abs=1.0)
    t, p = v(NAS51, "s5_1.health_services.current")
    c(
        "c4d.c_hlth_nas51",
        "C_HLTH entries vs NAS 5.1 health services (domestic concept; gap logged, households-9)",
        s(row="C_HLTH"),
        t,
        target_prov_id=p,
        tol_abs=0.005 * t,
    )
    pop = {g: float(hh.classes.filter(pl.col("household_group") == g)["persons"].sum()) for g in hh.groups}
    for area, a in (("rural", "R"), ("urban", "U")):
        hl = {
            g: float(e.filter((pl.col("row") == "C_HLTH") & (pl.col("col") == g))["value"].sum()) / pop[g]
            for g in hh.groups
            if area_of(g) == area
        }
        nss = ctx.rows(
            H596,
            series_id=[f"t2_21.oop_per_hosp_case_avg.{area}_hh_q{k}" for k in (1, 5)],
            period="2025",
            unit="INR",
            price_basis="current",
        )
        n = dict(nss.select("series_id", "value").iter_rows())
        sam_dir = 1.0 if hl[f"H_{a}5"] > hl[f"H_{a}1"] else -1.0
        nss_dir = (
            1.0
            if n[f"t2_21.oop_per_hosp_case_avg.{area}_hh_q5"] > n[f"t2_21.oop_per_hosp_case_avg.{area}_hh_q1"]
            else -1.0
        )
        c(
            f"c4d.health_gradient_{area}",
            f"Direction (+1 rising) of health spending from q1 to q5, {area}: C_HLTH per "
            "person (SAM) vs NSS 2025 OOP per hospitalisation case (Report 596)",
            sam_dir,
            nss_dir,
            target_prov_id=str(nss["prov_id"][0]),
            tol_abs=0.0,
        )
    ed = {
        a: sum(
            float(e.filter((pl.col("row") == "C_EDUC") & (pl.col("col") == g))["value"].sum())
            for g in hh.groups
            if area_of(g) == a
        )
        / sum(pop[g] for g in hh.groups if area_of(g) == a)
        for a in ("rural", "urban")
    }
    cms = ctx.rows(
        CMS,
        series_id=[f"s2_3.exp_per_student.all.person.{a}_all" for a in ("rural", "urban")],
        period="2025-Q2",
        unit="INR",
        price_basis="current",
    )
    cm = dict(cms.select("series_id", "value").iter_rows())
    c(
        "c4d.education_urban_rural",
        "Direction (+1: urban above rural) of education spending: C_EDUC per person (SAM) "
        "vs CMS 2025 spending per student",
        1.0 if ed["urban"] > ed["rural"] else -1.0,
        1.0
        if cm["s2_3.exp_per_student.all.person.urban_all"] > cm["s2_3.exp_per_student.all.person.rural_all"]
        else -1.0,
        target_prov_id=str(cms["prov_id"][0]),
        tol_abs=0.0,
    )
    # S8
    t, p = v(USE, "use.gfce.sut_p001.current")
    c(
        "s8.rice_gfce",
        "S8 free rice value over the groups vs SUT GFCE paddy",
        s8["rice_free_group_sum"],
        t,
        target_prov_id=p,
        tol_abs=0.01,
    )
    t, p = v(USE, "use.gfce.sut_p002.current")
    c(
        "s8.wheat_gfce",
        "S8 free wheat value over the groups vs SUT GFCE wheat",
        s8["wheat_free_group_sum"],
        t,
        target_prov_id=p,
        tol_abs=0.01,
    )
    t, p = v(UNION_EXP, "stat7.food.food_subsidy", vintage=None)
    c(
        "s8.vs_union_food_subsidy",
        "S8 total vs Union food subsidy (cash, Actuals; includes FCI economic cost and "
        f"storage, so S8 is lower: tolerance {FOOD_SUBSIDY_TOL:.0%} of the target, households-10)",
        s8["rice_free_group_sum"] + s8["wheat_free_group_sum"],
        t,
        target_prov_id=p,
        tol_abs=FOOD_SUBSIDY_TOL * t,
    )
    # plausibility vs IFPRI 2022/23 (old base, national quintiles; bands only)
    by_g = dict(e.group_by("col", maintain_order=True).agg(pl.col("value").sum()).iter_rows())
    rural = 100.0 * sum(by_g[g] for g in hh.groups if area_of(g) == "rural") / tot
    t, p = v(
        IFPRI, "ifpri.t11.consumption_share.rural", period="2022-23", unit="percent", price_basis="n/a", vintage=None
    )
    c(
        "plaus.rural_share_ifpri",
        f"Rural share of PFCE (%) vs IFPRI 2022/23 SAM (band +-{PLAUSIBILITY_TOL:g} pp)",
        rural,
        t,
        target_prov_id=p,
        tol_abs=PLAUSIBILITY_TOL,
    )
    top = 100.0 * (by_g["H_R5"] + by_g["H_U5"]) / tot
    t, p = v(IFPRI, "ifpri.t11.consumption_share.q5", period="2022-23", unit="percent", price_basis="n/a", vintage=None)
    c(
        "plaus.top_quintiles_ifpri",
        "Share of PFCE (%) of H_R5 + H_U5 (within-area top quintiles) vs IFPRI national "
        f"top quintile (band +-{PLAUSIBILITY_TOL:g} pp; different quintile definitions)",
        top,
        t,
        target_prov_id=p,
        tol_abs=PLAUSIBILITY_TOL,
    )
    # HCES internal consistency
    leaf = float(hh.item_groups.filter(pl.col("role") == "leaf")["crore"].sum())
    t999 = float(hh.item_groups.filter(pl.col("code") == "999")["crore"].sum())
    c(
        "hces.leaf_items_vs_total",
        "HCES scale: sum of A10F leaf items vs A10F item 999 total expenditure (rounding "
        "of 2-decimal values per person)",
        leaf,
        t999,
        target_prov_id=hh.pid["a10f"],
        tol_abs=HCES_ROUNDING * t999,
    )
    a2t = float(hh.classes.select((pl.col("persons") * pl.col("avg_mpce") * 12.0 / 1e7).sum()).item())
    c(
        "hces.a2_vs_a10f_total",
        "HCES scale: A2 persons x MPCE x 12 vs A10F item 999 total (rounding)",
        a2t,
        t999,
        target_prov_id=hh.pid["mpce"],
        tol_abs=HCES_ROUNDING * t999,
    )
    allp = ctx.rows(
        A2,
        period=SURVEY,
        geography="IN",
        item_code="persons",
        household_group=["rural_all", "urban_all"],
        unit="count",
        price_basis="n/a",
    )
    c(
        "pop.persons_vs_a2_all",
        "Persons over the 10 groups vs A2 rural_all + urban_all (rounding)",
        sum(pop.values()),
        float(allp["value"].sum()),
        target_prov_id=str(allp["prov_id"][0]),
        tol_abs=1000.0,
    )
    for g in hh.groups:
        c(
            f"xwalk.state_persons.{g.lower()}",
            f"hh_state_xwalk: persons the 36 State/UT class lists place in {g} vs "
            "the all-India class persons of the group (informative; households-8)",
            assigned[g],
            pop[g],
            target_prov_id=hh.pid["persons"],
            tol_abs=XWALK_TOL * pop[g],
        )
