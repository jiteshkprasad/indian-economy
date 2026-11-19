"""Households block: private final consumption (PFCE) by commodity split over the 10 household groups
(rural/urban x HCES 2023-24 person quintile), the reusable household keys (`hh_keys` and companions) and S8.

Groups. H_R1..H_R5 and H_U1..H_U5 are person quintiles of monthly per-capita consumption (MPCE) within rural
and within urban India, built from the 24 published HCES 2023-24 fractile classes (Table A2: p00_05 + p05_10 +
p10_20 = quintile 1, ..., p80_90 + p90_95 + p95_100 = quintile 5). HCES runs Aug 2023 - Jul 2024: its shares
are applied to FY 2023-24 levels (one recorded assumption, cited by every HCES-keyed record; ISSUES P1-5).

Reads (clean data; vintages): hces_consumption A2, A10F, A10SW (HCES 2023-24, period 2023-08/2024-07, vintage
2025-01-30), health596 and cms_education_2025 (direction checks only); io_tables SUT 2023-24 use / supply
(latest vintage, 31 Aug 2026), ICIO India 2022-23 (C4c memo), IFPRI 2022/23 T11 (plausibility checks);
mospi_nas_2026 Statements 1.1, 1.13, 1.14, 5.1, 8.13 (latest); rbi_financial_accounts T52(b) household stocks
(31 Mar 2023 and 2024; latest) and rbi_banking_corporate Trend & Progress SCB cost/return rates (2023-24,
latest = 2025-12-29); labour_enterprise_surveys AIDIS 2019 (quintile table and press note, stocks 30.06.2018);
union_fiscal expenditure profile St 7 (food subsidy check). Concordances: io_tables_sut_product_to_sam34
(production's) and hces2324_item_to_sut_product (this block's, DECISIONS D2-15). Reads production's
constraints (pfce.* targets, checks only).

Writes entries (all `estimated`, role `free`):
- C1a: C_x <- H_g for the 26 commodities with PFCE other than C_DWEL, C_FINS, C_INSR, C_HLTH, C_EDUC, one
  entry per (SUT product, group), component `sut_pNNN`: SUT PFCE of the product x the group's share of HCES
  spending on the product's key items (confidence medium for direct keys, low for proxies).
- C4a: C_DWEL <- H_g, components actual_rent (HCES 520 key), imputed_rent (HCES 539 memo key) and
  govt_housing (SUT supply of p144 by industry 67; HCES 520 proxy key).
- C4b: C_FINS <- H_g components fisim_deposits / fisim_loans (NAS 1.13 FISIM split with fincorp's reference-
  rate formula, XR-5) and explicit_fees (SUT p142 - FISIM); C_INSR <- H_g insurance_service; AIDIS keys (low).
- C4d: C_HLTH <- H_g `oop_health` (p153), C_EDUC <- H_g `oop_education` (p152), HCES service items (medium).
- C4c: no entries (NPISH is inside the SUT PFCE of each product and distributed with it; entries would double
  count); memo satellite `c4c_npish_memo`.
Constraints: hh.c1.total (NAS 1.1 PFCE, tol 1), hh.c4b.fisim (NAS 1.13), hh.c4a.govt_housing (SUT cell) and
hh.c4a.imputed_rent (band +-10%, XR-22). Production's per-commodity pfce.* targets are not re-declared (XR-15).
Satellites: hh_keys, hh_group_map, hh_hces_items, hh_state_xwalk, hh_national_quintile_xwalk, hh_aidis_overlap,
c1a_hces_nas_ratio (ref C1a, the convention of FRAMEWORK_REQUESTS P-8), c4a_imputed_rent_sensitivity (C4a),
c4c_npish_memo (C4c), s8_food_stik (S8).

Excluded from every PFCE key: jewellery (valuables), free PDS/State-scheme items (GFCE, S8), meals received as
assistance (GFCE STiK), residential land rent (D45). Skipped: nothing in REFS; every gap-map method that cannot be
followed as written, and its fallback, is in docs/phase2/issues/households.md.
"""

from __future__ import annotations

import polars as pl

from pipeline.sam.framework import BlockContext, BlockResult

from . import _aidis, _checks, _data, _entries, _satellites

BLOCK = "households"
REFS = ["C1a", "C4a", "C4b", "C4c", "C4d", "S8"]
DEPENDS = ["production"]


def _load(ctx: BlockContext) -> _data.HH:
    classes = _data.read_classes(ctx)
    items, item_groups, a10f_pid = _data.read_items(ctx, classes)
    pfce, total, total_pid = _data.read_pfce(ctx)
    keymap = _data.read_keymap(ctx, items, pfce)
    groups = ctx.accounts.in_group("HH")
    if sorted(groups) != sorted(classes["household_group"].unique(maintain_order=True).to_list()):
        raise _data.SamError(f"HH accounts {groups} differ from the groups built from HCES classes")
    hh = _data.HH(groups=groups, classes=classes, items=items, item_groups=item_groups, pfce=pfce, keymap=keymap)
    hh.pid.update(
        persons=_data.one_prov(classes.rename({"pid_p": "prov_id"}), "A2 persons"),
        households=_data.one_prov(classes.select(pl.col("pid_households").alias("prov_id")), "A2 households"),
        mpce=_data.one_prov(classes.select(pl.col("pid_avg_mpce").alias("prov_id")), "A2 MPCE"),
        a10f=a10f_pid,
        pfce_total_row=total_pid,
        pfce_p144=str(pfce.filter(pl.col("product") == "sut_p144")["prov_id"][0]),
    )
    hh.values["pfce_total_row"] = total
    sha = ctx.concordances_read[_data.KEY_MAP][:12]
    hh.conc_note = f"concordance data/concordance/{_data.KEY_MAP}.csv sha256 {sha}"
    return hh


def build(ctx: BlockContext) -> BlockResult:
    hh = _load(ctx)
    hh.pid["window"] = ctx.prov(
        ref="C1a",
        status="estimated",
        inputs=[hh.pid["persons"], hh.pid["a10f"]],
        method="Survey-window assumption (ISSUES P1-5): HCES 2023-24 was fielded Aug 2023 - Jul 2024 (period "
        f"{_data.SURVEY}), 8 of whose 12 months fall in FY 2023-24. Its distribution shares (by group and item) are "
        "applied to FY 2023-24 levels, assuming the shares are stable over the 4-month offset. HCES levels (about 44% "
        "of NAS PFCE, RECONCILIATION HH-1) are never used as SAM levels.",
        locator=f"{_data.A2}, {_data.A10F}, period {_data.SURVEY}",
    )
    ctx.log(
        f"HCES groups: {hh.classes.height} classes; {hh.items['code'].n_unique()} A10F items with values; "
        f"{hh.keymap.height} concordance rows ({hh.conc_note})"
    )
    # A10F cells printed '-' are absent in the clean data and count as 0 (plan s.2.2; stated in the hh_hces_items
    # record): log every key item that has such cells (households issue file, V-HH-4)
    used = hh.keymap.filter(pl.col("ref") != "excluded")["hces_item"].unique().to_list()
    n_cls = (hh.items.filter(pl.col("code").is_in(used)).group_by("code", maintain_order=True)
             .agg(pl.col("hces_class").n_unique().alias("n")))  # fmt: skip
    short = sorted((c, n) for c, n in n_cls.filter(pl.col("n") < hh.classes.height).iter_rows())
    if short:
        ctx.log(
            f"A10F '-' cells counted as 0 (no value row) for {len(short)} key items: "
            + ", ".join(f"{c} ({n} of {hh.classes.height} classes)" for c, n in short)
        )

    entries = _entries.product_keyed(ctx, hh, "C1a") + _entries.product_keyed(ctx, hh, "C4d")
    entries += _entries.dwellings(ctx, hh)
    keys, ov, params, apids = _aidis.aidis_keys(ctx, hh)
    hh.values.update(params)
    hh.pid["aidis"] = ctx.prov(
        ref="C1a",
        status="estimated",
        source_id=_data.AIDIS_SRC,
        inputs=[*apids, hh.pid["households"], hh.pid["window"]],
        method="hh_keys aidis_* (households plan s.2.4 step 3; CROSS_REVIEW XR-10): AIDIS 2019 per-household values "
        "by AIDIS's own household-expenditure quintile class (5 equal household classes per area; stocks at "
        "30.06.2018; i9.financial_assets_per_hh, i9.cash_loan_per_hh, i9.fixed_assets_per_hh, i9.valuables_per_hh, "
        "i5.ava_per_hh) mapped to the SAM groups by cumulative household overlap: within an area the SAM groups, "
        "ordered by MPCE, cover ranges of cumulative HCES 2023-24 A2 household shares; level(group) = sum over AIDIS "
        "classes of overlapping households x per-household value / 1e7 (Rs crore; 2018 values on 2023-24 "
        "households, not rebased: use shares). aidis_inst_loans / aidis_noninst_loans = cash loans x the press-note "
        "institutional / non-institutional debt share of the area (rural 66/34, urban 87/13); aidis_deposits = "
        "financial assets x min(1, press-note deposit share of total assets x assets per household / financial "
        f"assets per household) (rural {params['deposit_to_fin_assets_raw.rural']:.4f} capped to "
        f"{params['deposit_to_fin_assets.rural']:.4f}, urban {params['deposit_to_fin_assets.urban']:.4f}; published "
        "for fincorp R8a under XR-10; the C4b FISIM on deposits is keyed by aidis_fin_assets, because both ratios "
        "are 1 within the rounding of the whole-percent share, households-5). The top "
        "AIDIS class holds less than class 4 in both areas, as served (households-4). ASSUMPTION: AIDIS classes "
        "and the HCES person quintiles rank households alike.",
    )
    hh.pid["aidis_proxy"] = ctx.prov(
        ref="C1a",
        status="estimated",
        inputs=[hh.pid["aidis"]],
        method="hh_keys aidis_equity, aidis_mf, aidis_small_savings (names from CROSS_REVIEW XR-10): the ingested "
        "AIDIS 2019 tables give no asset-class split beyond deposits (the press note publishes only the deposit "
        "share of total assets, which already equals financial assets within rounding), so each is published with "
        "exactly the aidis_fin_assets levels and shares, a stated proxy (confidence low; households-7). Consumers "
        "must not read their levels as holdings of that asset class.",
    )
    entries += _entries.financial(ctx, hh, keys, hh.pid["aidis"])

    sats: dict[str, _satellites.Satellite] = {}
    sats["hh_group_map"] = _satellites.group_map(ctx, hh)
    sats["hh_hces_items"] = _satellites.hces_items(ctx, hh)
    sats["hh_keys"] = _satellites.hh_keys(ctx, hh, entries, keys)
    sats["hh_aidis_overlap"] = _satellites.aidis_overlap(hh, ov)
    sats["c4a_imputed_rent_sensitivity"] = _satellites.imputed_rent_sensitivity(ctx, hh, entries)
    sats["c4b_fisim_split_sensitivity"] = _satellites.fisim_split_sensitivity(ctx, hh, entries, keys)
    sats["hh_state_xwalk"], assigned, reordered = _satellites.state_xwalk(ctx, hh)
    if reordered:
        ctx.log(
            f"hh_state_xwalk: {reordered} State x area class lists have non-increasing class means (re-ordered by MPCE)"
        )
    sats["hh_national_quintile_xwalk"] = _satellites.national_xwalk(ctx, hh)
    sats["c1a_hces_nas_ratio"], ratios = _satellites.hces_nas_ratio(ctx, hh)
    odd = {k: round(r, 3) for k, r in ratios.items() if not 0.05 <= r <= 1.5}
    if odd:
        ctx.log(f"HCES/NAS ratio outside [0.05, 1.5] for {odd} (c1a_hces_nas_ratio; households-11)")
    sats["c4c_npish_memo"], npish = _satellites.npish_memo(ctx)
    ctx.log(f"C4c memo: NPISH share of household + NPISH final consumption (ICIO 2022-23) = {npish:.4%}")
    sats["s8_food_stik"], s8 = _satellites.food_stik(ctx, hh)
    s8df = sats["s8_food_stik"].df
    for name in ("rice_free", "wheat_free"):
        s8[f"{name}_group_sum"] = float(
            s8df.filter((pl.col("item") == name) & (pl.col("measure") == "value"))["value"].sum()
        )

    cons = _checks.constraints(ctx, hh)
    _checks.checks(ctx, hh, entries, s8, assigned)
    return BlockResult(entries=entries, constraints=cons, satellites=sats)
