"""Households block: AIDIS 2019 asset and debt keys mapped to the 10 SAM groups by cumulative household
overlap (households plan s.2.4 step 3; CROSS_REVIEW XR-10). Private helper of the `households` block."""

from __future__ import annotations

import polars as pl

from pipeline.sam.framework import BlockContext, SamError

from ._data import AIDIS_PN, AIDIS_Q, AREAS, HH, area_of, group_code

AIDIS_PERIOD = "2018-06-30"  # AIDIS 2019 stocks (NSS 77th round, visit 1 reference date)
# key -> (dataset table prefix, series stem): per-household values by AIDIS household-expenditure quintile class
PER_HH = {
    "aidis_fin_assets": "i9.financial_assets_per_hh",
    "aidis_cash_loans": "i9.cash_loan_per_hh",
    "aidis_fixed_assets": "i9.fixed_assets_per_hh",
    "aidis_valuables": "i9.valuables_per_hh",
    "aidis_total_assets": "i5.ava_per_hh",
}
# Keys that the ingested AIDIS tables cannot separate from total financial assets (no asset-class split by
# class and no equity / MF / small-savings share even at R/U level): published with the aidis_fin_assets
# distribution, as a stated proxy (CROSS_REVIEW XR-10 asks for them by name).
FIN_ASSET_PROXIES = ("aidis_equity", "aidis_mf", "aidis_small_savings")


def overlap(hh: HH) -> pl.DataFrame:
    """Households of each SAM group attributed to each AIDIS class (5 equal household classes per area):
    within an area the SAM groups are ordered by MPCE and each covers a range of cumulative household shares
    (HCES 2023-24 A2 households); overlap = length of the intersection with the AIDIS class range x area households."""
    rows = []
    for area in AREAS:
        gs = [group_code(area, q) for q in range(1, 6)]
        n = {g: float(hh.classes.filter(pl.col("household_group") == g)["households"].sum()) for g in gs}
        total = sum(n.values())
        cum, lo = {}, 0.0
        for g in gs:
            cum[g] = (lo, lo + n[g] / total)
            lo += n[g] / total
        for g in gs:
            a, b = cum[g]
            for k in range(1, 6):
                ov = max(0.0, min(b, k / 5) - max(a, (k - 1) / 5))
                if ov > 0:
                    rows.append(
                        {
                            "area": area,
                            "aidis_class": f"{area}_q{k}",
                            "household_group": g,
                            "households": ov * total,
                            "group_lo": a,
                            "group_hi": b,
                        }
                    )
    return pl.DataFrame(rows)


def read_aidis(ctx: BlockContext) -> tuple[pl.DataFrame, dict[str, float], list[str]]:
    """Per-household values by AIDIS class (INR, stocks at 30.06.2018) and the press-note R/U shares."""
    sids = [f"{stem}.{a}_q{k}.all.current" for stem in PER_HH.values() for a in AREAS for k in range(1, 6)]
    q = ctx.rows(AIDIS_Q, series_id=sids, period=AIDIS_PERIOD, unit="INR", price_basis="current")
    if q.height != len(sids):
        raise SamError(f"AIDIS quintile table: {q.height} rows for {len(sids)} series")
    per_hh = q.select(
        pl.col("series_id").str.split(".").list.slice(0, 2).list.join(".").alias("stem"),
        pl.col("household_group").alias("aidis_class"),
        "value",
        "prov_id",
    )
    pct = [
        f"pn.{s}.{a}.all"
        for s in ("debt_share_institutional", "debt_share_noninstitutional", "asset_share_deposits")
        for a in AREAS
    ]
    inr = [f"pn.{s}.{a}.all.current" for s in ("ava_per_hh", "ava_financial_per_hh") for a in AREAS]
    pn = pl.concat(
        [
            ctx.rows(AIDIS_PN, series_id=pct, period=AIDIS_PERIOD, unit="percent", price_basis="n/a"),
            ctx.rows(AIDIS_PN, series_id=inr, period=AIDIS_PERIOD, unit="INR", price_basis="current"),
        ]
    )
    if pn.height != len(pct) + len(inr):
        raise SamError("AIDIS press note: expected one row per series")
    shares = dict(pn.select("series_id", "value").iter_rows())
    pids = sorted(set(per_hh["prov_id"].to_list()) | set(pn["prov_id"].to_list()))
    return per_hh, shares, pids


def aidis_keys(ctx: BlockContext, hh: HH) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, float], list[str]]:
    """Levels (Rs crore) by SAM group for every AIDIS key: sum over AIDIS classes of overlap households
    (HCES 2023-24) x per-household value (AIDIS 2019), / 1e7. Returns (keys long frame, overlap, params, inputs)."""
    ov = overlap(hh)
    per_hh, pn, pids = read_aidis(ctx)
    params: dict[str, float] = {}
    rows = []
    for key, stem in PER_HH.items():
        vals = dict(per_hh.filter(pl.col("stem") == stem).select("aidis_class", "value").iter_rows())
        for area in AREAS:
            if vals[f"{area}_q5"] < vals[f"{area}_q4"]:
                ctx.log(
                    f"AIDIS {stem} {area}: top class {vals[f'{area}_q5']:,.0f} < class 4 {vals[f'{area}_q4']:,.0f} "
                    "per household (as served; households-4)"
                )
        for r in ov.iter_rows(named=True):
            rows.append(
                {
                    "key": key,
                    "household_group": r["household_group"],
                    "level": r["households"] * vals[r["aidis_class"]] / 1e7,
                }
            )
    base = pl.DataFrame(rows).group_by("key", "household_group", maintain_order=True).agg(pl.col("level").sum())
    lvl = {(k, g): v for k, g, v in base.iter_rows()}
    derived = []
    for g in hh.groups:
        a = area_of(g)
        inst = pn[f"pn.debt_share_institutional.{a}.all"] / 100.0
        noninst = pn[f"pn.debt_share_noninstitutional.{a}.all"] / 100.0
        # deposits as a fraction of financial assets in the area (press note: deposits share of total assets x
        # total assets per household / financial assets per household), capped at 1 (the share is printed in whole
        # percent: rural 5% gives 1.097, a rounding artefact; households-5)
        d_raw = (
            pn[f"pn.asset_share_deposits.{a}.all"]
            / 100.0
            * pn[f"pn.ava_per_hh.{a}.all.current"]
            / pn[f"pn.ava_financial_per_hh.{a}.all.current"]
        )
        params[f"deposit_to_fin_assets_raw.{a}"] = d_raw
        params[f"deposit_to_fin_assets.{a}"] = min(1.0, d_raw)
        # the range the whole-percent share allows (share +- 0.5 point): both areas straddle 1 or sit above it, so
        # FISIM on deposits is keyed by financial assets (verification V-HH-2)
        dep_pct = pn[f"pn.asset_share_deposits.{a}.all"]
        params[f"deposit_to_fin_assets_lo.{a}"] = d_raw * (dep_pct - 0.5) / dep_pct
        params[f"deposit_to_fin_assets_hi.{a}"] = d_raw * (dep_pct + 0.5) / dep_pct
        params[f"inst_share.{a}"] = inst
        params[f"noninst_share.{a}"] = noninst
        fa, cl = lvl[("aidis_fin_assets", g)], lvl[("aidis_cash_loans", g)]
        derived += [
            {"key": "aidis_inst_loans", "household_group": g, "level": cl * inst},
            {"key": "aidis_noninst_loans", "household_group": g, "level": cl * noninst},
            {"key": "aidis_deposits", "household_group": g, "level": fa * min(1.0, d_raw)},
        ] + [{"key": k, "household_group": g, "level": fa} for k in FIN_ASSET_PROXIES]
    keys = pl.concat([base, pl.DataFrame(derived)]).with_columns(
        (pl.col("level") / pl.col("level").sum().over("key")).alias("share")
    )
    return keys, ov, params, pids
