"""Households block: the SAM entries COM -> H_* (C1a, C4a, C4b, C4d) and their provenance records.
Private helper of the `households` block."""

from __future__ import annotations

import polars as pl

from pipeline.sam.framework import BlockContext, SamError, entry

from ._data import (
    C4D_COMPONENTS,
    HCES_SRC,
    HH,
    NAS113,
    NAS_SRC,
    RENT_ACTUAL,
    RENT_IMPUTED,
    RTP,
    SUPPLY,
    SUT_SRC,
    T52,
    VINTAGE,
)

H1 = (
    "Assumption H1 (gap map C1a): the HCES/NAS gap is distribution-neutral within each SUT product, so the "
    "SUT level is spread with HCES shares (uniform scaling within a product). NPISH final consumption (C4c) is "
    "inside the SUT PFCE of each product and is distributed with the same household key (not separable on the "
    "new base; C4c memo satellite)."
)
# FISIM on deposits: AIDIS financial assets (households plan s.2.4 step 3; verification V-HH-2), not aidis_deposits
FISIM_D_KEY = "aidis_fin_assets"
NPISH = "NPISH final consumption (C4c) is inside this SUT PFCE and is distributed with the same household key."


def _key(hh: HH, codes: list[str]) -> dict[str, float]:
    """HCES-scale value (Rs crore/yr) of the given A10F items by SAM group."""
    df = hh.item_groups.filter(pl.col("code").is_in(codes))
    by = dict(df.group_by("household_group", maintain_order=True).agg(pl.col("crore").sum()).iter_rows())
    return {g: float(by.get(g, 0.0)) for g in hh.groups}


def _spread(total: float, key: dict[str, float], what: str) -> dict[str, float]:
    s = sum(key.values())
    if not s > 0:
        raise SamError(f"{what}: key sums to {s} (no HCES spending on the key items)")
    return {g: total * v / s for g, v in key.items()}


def _emit(
    out: list[dict], row: str, ref: str, comp: str, values: dict[str, float], pid: str, conf: str, ctx: BlockContext
) -> None:
    zeros = [g for g, v in values.items() if v == 0]
    if zeros:
        ctx.log(f"{ref} {row}/{comp}: key is 0 for {zeros}: no entry (structural zero)")
    out += [
        entry(row, g, ref, v, prov_id=pid, status="estimated", role="free", component=comp, confidence=conf)
        for g, v in values.items()
        if v != 0
    ]


def product_keyed(ctx: BlockContext, hh: HH, ref: str) -> list[dict]:
    """C1a (26 commodities, product level) or C4d (C_EDUC p152, C_HLTH p153): for each SUT product p,
    entry(commodity <- H_g) = SUT PFCE_p x share of group g in the HCES value of p's key items."""
    out: list[dict] = []
    km = hh.keymap.filter(pl.col("ref") == ref)
    for p in km["product"].unique(maintain_order=True).sort().to_list():
        rows = km.filter(pl.col("product") == p)
        codes = rows["hces_item"].to_list()
        prod = hh.pfce.filter(pl.col("product") == p).row(0, named=True)
        quality = "proxy" if "proxy" in rows["key_quality"].to_list() else "direct"
        conf = "low" if quality == "proxy" else "medium"
        comp = C4D_COMPONENTS[p] if ref == "C4d" else p
        key = _key(hh, codes)
        pid = ctx.prov(
            ref=ref,
            status="estimated",
            source_id=HCES_SRC,
            inputs=[prod["prov_id"], hh.pid["a10f"], hh.pid["persons"], hh.pid["window"]],
            method=f"Gap map {ref}: SUT {ctx.year} PFCE of product {p[5:]} '{prod['label']}' ({prod['commodity']}; "
            f"{prod['series_id']}, Rs {prod['value']:,.2f} crore) split over the 10 household groups in proportion to "
            f"each group's HCES 2023-24 spending on A10F items {', '.join(codes)} (key {quality}: {rows['note'][0]}); "
            f"HCES spending = value per person (30 days) x A2 persons x 12, summed over the fractile classes of each "
            f"group ({hh.conc_note}). Entry = PFCE x share; the group shares sum to 1. {H1}",
            locator=f"{prod['series_id']}; hces_consumption_a10f_item_fractile items {', '.join(codes)}",
        )
        _emit(out, prod["commodity"], ref, comp, _spread(prod["value"], key, f"{ref} {p}"), pid, conf, ctx)
    return out


def dwellings(ctx: BlockContext, hh: HH) -> list[dict]:
    """C4a: C_DWEL (SUT p144) = government-provided housing (SUT supply of p144 by industry 67) + actual rent
    + imputed rent (the rest, split with the HCES ratio of rent paid to imputed rent)."""
    prod = hh.pfce.filter(pl.col("product") == "sut_p144").row(0, named=True)
    govt, gpid = ctx.value(SUPPLY, "supply.output.sut_p144.sut_i67.current", vintage=VINTAGE)
    own, opid = ctx.value(SUPPLY, "supply.output.sut_p144.sut_i57.current", vintage=VINTAGE)
    k_act, k_imp = _key(hh, [RENT_ACTUAL]), _key(hh, [RENT_IMPUTED])
    v_act, v_imp = sum(k_act.values()), sum(k_imp.values())
    ratio = v_act / (v_act + v_imp)
    rest = prod["value"] - govt
    hh.values.update(
        c4a_govt=govt,
        c4a_rest=rest,
        c4a_ratio=ratio,
        c4a_actual=rest * ratio,
        c4a_imputed=rest * (1 - ratio),
        c4a_own_supply=own,
    )
    hh.pid.update(c4a_govt_supply=gpid, c4a_own_supply=opid)
    base = (
        f"SUT {ctx.year} PFCE on ownership of dwellings (p144, {prod['series_id']}) = Rs {prod['value']:,.2f} "
        f"crore; government-provided housing = SUT supply of p144 by industry 67 (public administration, "
        f"supply.output.sut_p144.sut_i67.current) = Rs {govt:,.2f} crore (S&M 2026: PFCE housing = GVO of "
        f"ownership of dwellings + housing provided by government); the rest, Rs {rest:,.2f} crore (the supply "
        f"by industry 57 prints {own:,.2f}: Use-table rounding), is split into actual and imputed rent with the "
        f"HCES 2023-24 ratio r = V520/(V520+V539) = {v_act:,.2f}/({v_act:,.2f}+{v_imp:,.2f}) = {ratio:.9f} "
        f"(A10F item 520 house/garage rent actual; memo item 539 imputed rent; HCES scale, value x A2 persons "
        f"x 12). No NAS table separates tenant and owner-occupied rent."
    )
    ins = [prod["prov_id"], gpid, opid, hh.pid["a10f"], hh.pid["persons"], hh.pid["window"]]
    out: list[dict] = []
    specs = [
        (
            "actual_rent",
            rest * ratio,
            k_act,
            "medium",
            "actual_rent = rest x r, keyed by HCES item 520 (rent paid by tenants) by group.",
        ),
        (
            "imputed_rent",
            rest * (1 - ratio),
            k_imp,
            "low",
            "imputed_rent = rest x (1 - r), keyed by HCES memo item 539 (MoSPI's imputed rent of owner-occupiers, "
            "identical to A6 memo_imputed_rent). The gap-map primary key (AIDIS 2019 owner-occupier values) cannot be "
            "followed: AIDIS publishes only all-buildings / fixed-asset values by class (households-2).",
        ),
        (
            "govt_housing",
            govt,
            k_act,
            "low",
            "govt_housing = the industry-67 cell, keyed by HCES item 520 (tenant rent) as a proxy: the gap-map key "
            "(government-employee CE by group, F1a) is built by factors, which depends on households, so reading it "
            "would be a cycle; the proxy moves at most 0.9% of C_DWEL (households-3).",
        ),
    ]
    for comp, total, key, conf, how in specs:
        pid = ctx.prov(
            ref="C4a",
            status="estimated",
            inputs=ins,
            source_id=HCES_SRC,
            method=f"Gap map C4a, component {comp}: {base} {how} {NPISH} {hh.conc_note}.",
            locator="io_tables_sut_use/supply p144; hces_consumption_a10f_item_fractile 520, 539",
        )
        hh.pid[f"c4a_{comp}"] = pid
        _emit(out, "C_DWEL", "C4a", comp, _spread(total, key, f"C4a {comp}"), pid, conf, ctx)
    return out


def fisim_split(ctx: BlockContext, hh: HH) -> None:
    """Household (PFCE) FISIM split into deposit and loan parts with fincorp's reference-rate formula
    (CROSS_REVIEW XR-5): FISIM_D proportional to (r* - r_D) x D, FISIM_L to (r_L - r*) x L."""
    fisim, fpid = ctx.value(NAS113, "s1_13.private_final_consumption_expenditure.current", vintage=VINTAGE)
    rates, rpids = {}, []
    for name, sid in (
        ("r_star", "return_on_investments"),
        ("r_deposits", "cost_of_deposits"),
        ("r_loans", "return_on_advances"),
    ):
        v, p = ctx.value(RTP, f"rtp.scb_cost_return.{sid}.scb", vintage=VINTAGE, unit="percent", price_basis="n/a")
        rates[name], rpids = v, [*rpids, p]
    if not rates["r_deposits"] < rates["r_star"] < rates["r_loans"]:
        raise SamError(f"FISIM reference rate outside the deposit/loan rates: {rates}")
    stocks, spids = {}, []
    for date in ("2023-03-31", "2024-03-31"):
        for name, sid in (
            ("dep_bank", "t52b.fa_deposits_bank.current"),
            ("dep_ofi", "t52b.fa_deposits_nonbank_ofi.current"),
            ("loans", "t52b.fl.current"),
        ):
            v, p = ctx.value(T52, sid, period=date, vintage=VINTAGE)
            stocks[(name, date)], spids = v, [*spids, p]
    dep = sum(stocks[(n, d)] for n in ("dep_bank", "dep_ofi") for d in ("2023-03-31", "2024-03-31")) / 2
    loans = sum(stocks[("loans", d)] for d in ("2023-03-31", "2024-03-31")) / 2
    wd = (rates["r_star"] - rates["r_deposits"]) * dep
    wl = (rates["r_loans"] - rates["r_star"]) * loans
    d24 = stocks[("dep_bank", "2024-03-31")] + stocks[("dep_ofi", "2024-03-31")]
    hh.values.update(
        fisim=fisim,
        fisim_d=fisim * wd / (wd + wl),
        fisim_l=fisim * wl / (wd + wl),
        fisim_dep_share=wd / (wd + wl),
        fisim_dep_stock=dep,
        fisim_loan_stock=loans,
        fisim_dep_share_stocks=d24 / (d24 + stocks[("loans", "2024-03-31")]),
        **rates,
    )
    hh.pid.update(fisim_nas=fpid)
    hh.pid["fisim_split"] = ctx.prov(
        ref="C4b",
        status="estimated",
        source_id=NAS_SRC,
        inputs=[fpid, *rpids, *spids],
        method=f"Gap map C4b (CROSS_REVIEW XR-5, fincorp's formula and parameters): household FISIM (NAS 2026 "
        f"St 1.13 FISIM allocated to PFCE, Rs {fisim:,.6f} crore) split into deposits and loans in proportion to "
        f"(r* - r_D) x D and (r_L - r*) x L. ASSUMPTION r* = SCB return on investments {rates['r_star']}% "
        f"(G-sec-dominated portfolio as the risk-free reference rate; recorded once here and published in hh_keys "
        f"fisim_params); r_D = SCB cost of deposits {rates['r_deposits']}%, r_L = SCB return on advances "
        f"{rates['r_loans']}% (RBI Trend and Progress, rtp.scb_cost_return.*.scb, 2023-24, latest vintage). D = "
        f"household bank + other-FI deposits, L = household financial liabilities (RBI T52(b)), each the average of "
        f"31 Mar 2023 and 31 Mar 2024 (D {dep:,.2f}, L {loans:,.2f}). Deposit share {wd / (wd + wl):.9f}: FISIM_D "
        f"{fisim * wd / (wd + wl):,.6f}, FISIM_L {fisim * wl / (wd + wl):,.6f}. Sensitivity (the plan's first method, "
        f"end-March 2024 stock weights): deposit share {d24 / (d24 + stocks[('loans', '2024-03-31')]):.6f}.",
        locator=f"{NAS113}; {RTP}; {T52}",
    )


def financial(ctx: BlockContext, hh: HH, keys: pl.DataFrame, aidis_pid: str) -> list[dict]:
    """C4b: C_FINS (p142) = FISIM on deposits + FISIM on loans + explicit fees (p142 - FISIM); C_INSR (p143) =
    insurance service charge. Group keys from AIDIS 2019 mapped to the SAM groups (hh_keys aidis_*)."""
    fisim_split(ctx, hh)
    fins = hh.pfce.filter(pl.col("product") == "sut_p142").row(0, named=True)
    insr = hh.pfce.filter(pl.col("product") == "sut_p143").row(0, named=True)
    fees = fins["value"] - hh.values["fisim"]
    if fees <= 0:
        raise SamError(f"SUT p142 PFCE {fins['value']} is below NAS household FISIM {hh.values['fisim']}")
    hh.values["c4b_fees"] = fees

    def share(key: str) -> dict[str, float]:
        k = keys.filter(pl.col("key") == key)
        return dict(zip(k["household_group"].to_list(), k["level"].to_list(), strict=True))

    v = hh.values
    out: list[dict] = []
    specs = [
        (
            "C_FINS",
            "fisim_deposits",
            hh.values["fisim_d"],
            FISIM_D_KEY,
            [hh.pid["fisim_split"], hh.pid["fisim_nas"]],
            "FISIM_D (record of the reference-rate split) keyed by hh_keys aidis_fin_assets, as households plan s.2.4 "
            "step 3 prescribes: the AIDIS press-note deposit share of total assets is printed in whole percent, and "
            "deposit share x assets per household / financial assets per household is "
            f"{v['deposit_to_fin_assets_raw.rural']:.4f} rural and {v['deposit_to_fin_assets_raw.urban']:.4f} urban, "
            "i.e. deposits equal financial assets within that rounding (the share +-0.5 point gives "
            f"{v['deposit_to_fin_assets_lo.rural']:.3f}-{v['deposit_to_fin_assets_hi.rural']:.3f} rural and "
            f"{v['deposit_to_fin_assets_lo.urban']:.3f}-{v['deposit_to_fin_assets_hi.urban']:.3f} urban), so the "
            "area ratio would add noise, not information (verification V-HH-2; hh_keys aidis_deposits, which applies "
            "it, is published for fincorp R8a under XR-10 and is not used here)",
        ),
        (
            "C_FINS",
            "fisim_loans",
            hh.values["fisim_l"],
            "aidis_inst_loans",
            [hh.pid["fisim_split"], hh.pid["fisim_nas"]],
            "FISIM_L keyed by hh_keys aidis_inst_loans: AIDIS 2019 cash loans per household by class x the press-note "
            "institutional share of the area (FISIM arises only on loans from financial institutions)",
        ),
        (
            "C_FINS",
            "explicit_fees",
            fees,
            "aidis_fin_assets",
            [fins["prov_id"], hh.pid["fisim_nas"]],
            f"explicit financial fees = SUT p142 PFCE {fins['value']:,.2f} - NAS 1.13 household FISIM = "
            f"{fees:,.6f}, keyed by hh_keys aidis_fin_assets",
        ),
        (
            "C_INSR",
            "insurance_service",
            insr["value"],
            "aidis_fin_assets",
            [insr["prov_id"]],
            f"insurance service charge = SUT p143 PFCE {insr['value']:,.2f}, keyed by hh_keys aidis_fin_assets. The "
            "gap-map key (HCES insurance-premium items) does not exist: HCES 2023-24 has no premium item among its "
            "leaf items (households-6); sensitivity alternative: HCES non-food total (item 984)",
        ),
    ]
    for row, comp, total, key, ins, how in specs:
        pid = ctx.prov(
            ref="C4b",
            status="estimated",
            inputs=[*ins, aidis_pid, hh.pid["window"]],
            source_id=NAS_SRC if comp.startswith("fisim") else SUT_SRC,
            method=f"Gap map C4b, component {comp}: {how}. AIDIS classes are AIDIS's own household-expenditure "
            "quintiles (stocks at 30.06.2018), mapped to the SAM groups by cumulative household overlap with HCES "
            "2023-24 A2 households (hh_aidis_overlap); the AIDIS top class holds less than class 4 in both areas "
            f"(households-4). Only the distribution comes from AIDIS; the level is the official total. {NPISH} "
            "Confidence low.",
            locator=f"{NAS113}; io_tables_sut_use p142/p143; labour_enterprise_surveys_aidis_2019_*",
        )
        hh.pid[f"c4b_{comp}"] = pid
        _emit(out, row, "C4b", comp, _spread(total, share(key), f"C4b {comp}"), pid, "low", ctx)
    return out
