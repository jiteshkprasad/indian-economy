"""P9a (product subsidies by paying government) and P10a (production taxes and subsidies by government,
gross sub-rows). Plan s.2.3-2.4 and CROSS_REVIEW XR-19 (component names), XR-20, XR-23."""

from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl

from pipeline.sam.framework import BlockContext, SamError

from .common import EXP, FA_EXP, FC16_SUB, NAS11, NAS42, SUPPLY, ULB, pids
from .p7a import SUT_VINTAGE

NAS_VINTAGE = "latest"  # NAS 2026 (31 Aug 2026) is the only vintage of 2023-24; an explicit choice
BUDGET_VINTAGE = "latest"

# commodity -> default paying government for the product subsidies the SUT books on it (plan s.2.3)
CENTRE_ALL = ("C_CHEM", "C_TREQ", "C_RPET")  # fertiliser + pesticides (St 7), EV purchase subsidy, LPG (St 7)
STATE_ALL = ("C_UTIL", "C_LVST", "C_FOFI")  # power subsidies (FC16 States), small State schemes
P_AIR = "sut_p137"  # air transport: UDAN viability-gap funding (Union)


@dataclass
class P9aSplit:
    centre: float
    state: float
    rows: list[dict] = field(default_factory=list)  # commodity, payer, value, basis
    centre_identified: float = 0.0
    state_identified: float = 0.0
    unexplained: float = 0.0
    ratio: float = 0.0
    food: float = 0.0  # FC16 States' food subsidies assigned to G_STA on C_TRAD (positive amount)
    util: float = 0.0  # C_UTIL product subsidy (States' power), positive amount
    inputs: list[str] = field(default_factory=list)


def p9a_split(ctx: BlockContext, p9: pl.DataFrame) -> P9aSplit:
    """p9: production's P9 entries (col = commodity, value negative)."""
    by = {r["col"]: r["value"] for r in p9.iter_rows(named=True)}
    aasha, pa = ctx.value(EXP, "stat7.other_subsidies.pradhan_mantri_annadata_aay_sanrakshan_yojna",
                          vintage=BUDGET_VINTAGE)  # fmt: skip
    miss, pm = ctx.value(EXP, "stat7.interest_subsidies.modified_interest_subvention_scheme", vintage=BUDGET_VINTAGE)
    sub = ctx.rows(SUPPLY, vintage=SUT_VINTAGE, item_code="product_subsidies", product=P_AIR)
    air = float(sub["value"].sum())
    food_ids = sorted(
        s for s in ctx.frame(FC16_SUB)["series_id"].unique().to_list()
        if s.startswith("sub.food.in-") and s.endswith(".gg_state")
    )  # fmt: skip
    food_rows = ctx.rows(FC16_SUB, series_id=food_ids, vintage="latest")
    food = float(food_rows["value"].sum())
    out = P9aSplit(0.0, 0.0)
    out.inputs = pids([pa, pm], sub["prov_id"].to_list(), food_rows["prov_id"].to_list())

    def add(com: str, payer: str, v: float, basis: str) -> None:
        if v != 0:
            out.rows.append({"commodity": com, "payer": payer, "value": v, "basis": basis})

    unexplained: dict[str, float] = {}
    for com, v in sorted(by.items()):
        if v > 0:
            raise SamError(f"P9 entry on {com} is positive ({v}); P9a expects subsidies to be negative")
        if com in CENTRE_ALL:
            add(com, "G_CEN", v, "identified: Union subsidy (St 7 fertiliser / LPG; EV purchase support)")
        elif com in STATE_ALL:
            if com == "C_UTIL":
                out.util = -v
            add(com, "G_STA", v, "identified: State subsidy (FC16 States' power; small State schemes)")
        elif com == "C_CROP":
            c = -min(aasha, -v)
            add(com, "G_CEN", c, "identified: PM-AASHA (St 7)")
            add(com, "G_STA", v - c, "identified: State procurement bonuses (remainder)")
        elif com == "C_FINS":
            c = -min(miss, -v)
            add(com, "G_CEN", c, "identified: Modified Interest Subvention Scheme (St 7)")
            add(com, "G_STA", v - c, "identified: State interest subvention (remainder)")
        elif com == "C_TRNS":
            c = max(v, air)  # both negative
            add(com, "G_CEN", c, "identified: air transport (UDAN), SUT product p137")
            add(com, "G_STA", v - c, "identified: State bus-fare schemes (remainder)")
        elif com == "C_TRAD":
            s = -min(food, -v)
            out.food = -s
            add(com, "G_STA", s, "identified: States' food subsidies, FC16 21 States (XR-23), not grossed up")
            if v - s != 0:
                unexplained[com] = v - s
        else:
            unexplained[com] = v
    out.centre_identified = sum(r["value"] for r in out.rows if r["payer"] == "G_CEN")
    out.state_identified = sum(r["value"] for r in out.rows if r["payer"] == "G_STA")
    out.ratio = out.centre_identified / (out.centre_identified + out.state_identified)
    out.unexplained = sum(unexplained.values())
    for com, v in sorted(unexplained.items()):
        add(com, "G_CEN", v * out.ratio, "unexplained (gap map Q7): identified Centre share")
        add(com, "G_STA", v * (1 - out.ratio), "unexplained (gap map Q7): identified State share")
    out.centre = sum(r["value"] for r in out.rows if r["payer"] == "G_CEN")
    out.state = sum(r["value"] for r in out.rows if r["payer"] == "G_STA")
    if abs(out.centre + out.state - sum(by.values())) > 1e-6:
        raise SamError("P9a split does not add up to the P9 total")
    return out


@dataclass
class P10aSplit:
    d39: float  # gross production subsidies (positive number)
    d29: float  # gross production taxes
    net: float  # P10 (production's entries)
    items: list[dict] = field(default_factory=list)  # gov, component, value, basis, inputs
    d39_inputs: list[str] = field(default_factory=list)
    # Union identified production-subsidy heads: (key, amount as a positive number, the prov_ids it is read from)
    centre_subsidy_items: list[tuple[str, float, list[str]]] = field(default_factory=list)
    centre_subsidy_status: dict[str, str] = field(default_factory=dict)  # official (as published) / derived
    centre_subsidy_basis: dict[str, str] = field(default_factory=dict)
    # PM-KISAN (FA 2401.00.130): read for the classification memo only; it is government's R10 `pm_kisan` (a
    # current transfer to households, as NAS 4.2 COFOG books it; government-30 / audit BS-5), not a D39 head
    pm_kisan: tuple[float, str] = (0.0, "")


def p10a_split(ctx: BlockContext, cash, p10: pl.DataFrame, p10_pids: list[str]) -> P10aSplit:
    """Gross D29/D39 from NAS 4.2 (GG subsidies = D31 + D39) less NAS 1.1 product subsidies; taxes and
    subsidies by government from identified budget heads, the States taking the residual."""
    net = float(p10["value"].sum())
    gg_sub, p1 = ctx.value(NAS42, "s4_2.subsidy.total.current", vintage=NAS_VINTAGE)
    prod_sub, p2 = ctx.value(NAS11, "s1_1.subsidies_on_products.current", vintage=NAS_VINTAGE)
    d39 = gg_sub - prod_sub
    d29 = d39 + net
    if d39 <= 0 or d29 <= 0:
        raise SamError(f"derived gross D39 {d39:,.2f} / D29 {d29:,.2f} not positive")
    out = P10aSplit(d39, d29, net, d39_inputs=sorted({p1, p2, *p10_pids}))
    ulb, pu = ctx.value(ULB, "ulb.property_tax.in.all_ulbs_in_dump", vintage="latest")

    def add(gov: str, comp: str, v: float, basis: str, inputs: list[str]) -> None:
        out.items.append({"gov": gov, "component": comp, "value": v, "basis": basis, "inputs": sorted(set(inputs))})

    add("G_CEN", "stamps_registration", cash.x("centre_stamps"), "RB MH 0030 + MH 0710 stamps (UTs)",
        cash.xp("centre_stamps"))  # fmt: skip
    add("G_CEN", "land_revenue", cash.x("centre_land_revenue"), "RB MH 0710 land revenue (UTs)",
        cash.xp("centre_land_revenue"))  # fmt: skip
    add("G_STA", "stamps_registration", cash.x("stamps"), "RBI SF App I stamps and registration fees",
        cash.xp("stamps"))  # fmt: skip
    add("G_STA", "land_revenue", cash.x("land_revenue"), "RBI SF App I land revenue", cash.xp("land_revenue"))
    add("G_STA", "property_tax", cash.x("urban_property_tax") + ulb,
        "RBI SF App I urban immovable property tax + cityfinance ULB property tax (284 ULBs)",
        [*cash.xp("urban_property_tax"), pu])  # fmt: skip
    other = d29 - sum(i["value"] for i in out.items)
    if other <= 0:
        raise SamError(f"identified production taxes exceed derived gross D29 by {-other:,.2f}")
    add("G_STA", "other_production_taxes", other, "residual: derived D29 less identified heads",
        sorted({p1, p2, *p10_pids}))  # fmt: skip

    # gross subsidies: Union identified heads; States = residual of D39
    kisan, pk = ctx.value(FA_EXP, "fa9.2401.00.130", vintage="latest")
    intsub, pi = ctx.value(EXP, "stat7.interest_subsidies", vintage=BUDGET_VINTAGE)
    miss, pm = ctx.value(EXP, "stat7.interest_subsidies.modified_interest_subvention_scheme", vintage=BUDGET_VINTAGE)
    lic, pl_ = ctx.value(EXP, "stat7.interest_subsidies.interest_subsidy_to_lic_for_pension_plan_for_senior_citizens",
                         vintage=BUDGET_VINTAGE)  # fmt: skip
    oth, po = ctx.value(EXP, "stat7.other_subsidies", vintage=BUDGET_VINTAGE)
    aasha, pa = ctx.value(EXP, "stat7.other_subsidies.pradhan_mantri_annadata_aay_sanrakshan_yojna",
                          vintage=BUDGET_VINTAGE)  # fmt: skip
    bus, pb = ctx.value(FC16_SUB, "sub.business.in.gg_centre", vintage="latest")
    # PM-KISAN is not a Union D39 head (government-30, audit BS-5 of 2026-10-01, DECISIONS D2-24): NAS 4.2 does not
    # itemise it; it is inferred to sit in COFOG 04.agri current transfers (58,325.32, large enough to hold it), not
    # in the GG subsidy total from which D39 is derived (V-TX-8), so counting it here
    # understated the States' D39 residual by its amount. government writes it as R10 `pm_kisan` (G_CEN -> H_*).
    out.pm_kisan = (kisan, pk)
    heads = (
        ("interest_subsidies_other", intsub - miss - lic, [pi, pm, pl_], "derived",
         "St 7 interest subsidies less MISS and less the LIC senior-citizen pension subsidy (government R18)"),
        ("other_subsidies_other", oth - aasha, [po, pa], "derived", "St 7 other subsidies less PM-AASHA"),
        ("fc16_union_business", bus, [pb], "official", "FC16 Union 'business' subsidies"),
    )  # fmt: skip
    out.centre_subsidy_items = [(k, x, sorted(set(ins))) for k, x, ins, _, _ in heads]
    out.centre_subsidy_status = {k: st for k, _, _, st, _ in heads}
    out.centre_subsidy_basis = {k: b for k, _, _, _, b in heads}
    centre = sum(v for _, v, _ in out.centre_subsidy_items)
    state = d39 - centre
    if state <= 0:
        raise SamError(f"Union identified production subsidies {centre:,.2f} exceed derived D39 {d39:,.2f}")
    csub_in = [pi, pm, pl_, po, pa, pb]
    add("G_CEN", "gross_subsidies", -centre,
        "St 7 interest subsidies less MISS and the LIC pension subsidy + St 7 other subsidies less PM-AASHA + FC16 "
        "Union 'business' subsidies (PM-KISAN is government's R10, not D39)", csub_in)  # fmt: skip
    add("G_STA", "gross_subsidies", -state, "residual: derived D39 less the Union's identified heads",
        [p1, p2, *csub_in])  # fmt: skip
    if abs(sum(i["value"] for i in out.items) - net) > 1e-6:
        raise SamError("P10a items do not add up to P10")
    return out
