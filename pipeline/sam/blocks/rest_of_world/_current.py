"""R_ROW, the current account with the rest of the world: R11/R11a, R12/R12a, R13, R14, R14a, K5 and D2.

Rows receive, columns pay: `H_R1 <- R_ROW` is RoW paying remittances to rural quintile-1 households;
`R_ROW <- E_NFPR` is private corporations paying investment income abroad. Method: docs/phase2/plans/
rest_of_world.md s.2.1-2.5 and s.2.8, with the s.8 cross-plan amendments (DECISIONS D2-7: E_RBI in two
components; XR-12: FPI G-sec interest with fincorp's formula; XR-13: no FISIM adjustment on R13/R14).
"""

from __future__ import annotations

from typing import Any

import polars as pl

from pipeline.sam.blocks.rest_of_world import _common as c
from pipeline.sam.blocks.rest_of_world._common import Out
from pipeline.sam.framework import BlockContext, SamError, Satellite, constraint, entry

ROUND_TOL = 1.0  # Rs crore: BoP is printed in whole crore; NAS 6.1 totals differ from the BoP sums by <= 1
XWALK_MEASURE = "consumption"  # the hh_state_xwalk measure holding HCES consumption levels (CROSS_REVIEW XR-10)
XWALK_CLASS = "all"  # hh_state_xwalk rows summing a State x area's fractile classes by SAM group


def v(
    ctx: BlockContext,
    ds: str,
    sid: str,
    *,
    period: str | None = None,
    vintage: str | None = c.LATEST,
    unit: str | None = "INR_crore",
    price_basis: str | None = "current",
) -> tuple[float, str]:
    return ctx.value(ds, sid, period=period or ctx.year, vintage=vintage, unit=unit, price_basis=price_basis)


def avg_stock(
    ctx: BlockContext,
    ds: str,
    sid: str,
    *,
    vintage: str | None,
    unit: str | None = "INR_crore",
    price_basis: str | None = "current",
) -> tuple[float, list[str], list[float]]:
    """Average of the opening (2023-03-31) and closing (2024-03-31) stock; returns (avg, prov_ids, [open, close])."""
    vals, pids = [], []
    for d in c.STOCK_DATES:
        x, p = v(ctx, ds, sid, period=d, vintage=vintage, unit=unit, price_basis=price_basis)
        vals.append(x)
        pids.append(p)
    return c.mean(vals), pids, vals


def build_current(ctx: BlockContext, out: Out) -> None:
    hh = ctx.accounts.in_group("HH")
    _transfers(ctx, out, hh)
    _property_income(ctx, out)
    _k5_d2(ctx, out)
    _acceptance(ctx, out)


# ---------------------------------------------------------------------------------------------------
# R11 / R11a remittances received; R12 / R12a transfers paid abroad
# ---------------------------------------------------------------------------------------------------


def _transfers(ctx: BlockContext, out: Out, hh: list[str]) -> None:
    r11, r11_pid = v(ctx, c.NAS61, "s6_1.other_current_transfers_to_resident_sectors_other_than_gener.current")
    r12, r12_pid = v(ctx, c.NAS61, "s6_1.other_current_transfers_by_resident_sectors_other_than_gener.current")

    # --- R11a: State shares of inward remittances x State consumption by SAM group (gap map R11a) ------
    surv = ctx.rows(c.REMIT, vintage=c.V_REMIT, unit="percent", price_basis=None).filter(
        pl.col("series_id").str.starts_with("remit.destination_state.")
    )
    s_k = {sid.rsplit(".", 1)[1]: float(x) for sid, x in zip(surv["series_id"], surv["value"])}
    surv_pids = sorted(set(surv["prov_id"].to_list()))
    s_sum = sum(s_k.values())
    ctx.log(f"R11a: remittance survey 2023-24 destination shares: {len(s_k)} States/UTs, sum {s_sum:.2f}%")
    if abs(s_sum - 100.0) > 0.05:
        raise SamError(f"R11a: remittance survey State shares sum to {s_sum}, not 100 (+-0.05)")
    xw = ctx.satellite("households", "hh_state_xwalk")
    need = {"geography", "hces_class", "household_group", "measure", "value", "prov_id"}
    if not need <= set(xw.columns):
        raise SamError(
            f"households/hh_state_xwalk lacks columns {sorted(need - set(xw.columns))}: rest_of_world needs State x "
            f"SAM-group HCES consumption levels (measure={XWALK_MEASURE!r}; CROSS_REVIEW XR-10)"
        )
    # the State x area totals by group (hces_class 'all' = the sum of that State's fractile classes)
    xwc = xw.filter((pl.col("measure") == XWALK_MEASURE) & (pl.col("hces_class") == XWALK_CLASS))
    if xwc.height == 0:
        raise SamError(
            f"households/hh_state_xwalk has no rows with measure={XWALK_MEASURE!r} and hces_class={XWALK_CLASS!r} "
            f"(measures: {sorted(set(xw['measure'].to_list()))}); rest_of_world R11a needs State x group consumption"
        )
    xwc = xwc.with_columns(pl.col("geography").str.to_lowercase().alias("state"))  # 'IN-MH' -> survey code 'in-mh'
    key = c.state_consumption_key(xwc.select("state", "household_group", "value").to_dicts(), hh)
    xw_pids = sorted(set(xwc["prov_id"].to_list()))
    r11a = c.remittance_by_group(r11, s_k, key)
    r11a_pid = ctx.prov(
        ref="R11a",
        status="estimated",
        inputs=[r11_pid, *surv_pids, *xw_pids],
        source_id="rbi_remittances_survey",
        notes="Total from NAS 2026; State shares from the RBI remittances survey; consumption key from households.",
        method=(
            "Gap map R11a. Total = NAS 2026 St 6.1 'other current transfers to resident sectors other than GG' "
            f"({c.NAS61}, latest vintage). Step 1: State/UT shares of inward remittances from the RBI remittances "
            f"survey 2023-24 round ({c.REMIT} remit.destination_state.*, vintage {c.V_REMIT}; bank channel, 30 AD "
            "banks), normalised to 1. Step 2: within each State, shares of that State's HCES 2023-24 consumption "
            "falling in each national SAM group, from households' hh_state_xwalk "
            f"(measure '{XWALK_MEASURE}', hces_class '{XWALK_CLASS}', rural + urban; the national quintile "
            "placement of State fractile classes is households' estimate). R11a_g = total x "
            "sum_k s_k x w_kg. Assumptions (each stated here, low confidence): (a) the bank-channel State shares "
            "apply to all current transfers from abroad, including BoP 1.C.1.2 'other current transfers' (grants "
            "to NPISH, inside households) and non-bank channels; (b) within a State, receipts are proportional to "
            "consumption; (c) the survey's State is the State of the receiving bank branch (Maharashtra and Delhi "
            "may be inflated as banking hubs)."
        ),
    )
    for g in hh:
        if r11a.get(g, 0.0) != 0.0:
            out.entries.append(
                entry(
                    g,
                    "R_ROW",
                    "R11a",
                    r11a[g],
                    prov_id=r11a_pid,
                    status="estimated",
                    role="free",
                    confidence="low",
                    component="remittances",
                )
            )
    cpid = ctx.prov(
        ref="R11",
        status="official",
        inputs=[r11_pid],
        method="Gap map R11: current transfers from RoW to resident sectors other than GG = NAS 2026 St 6.1 item 4 "
        f"({c.NAS61} s6_1.other_current_transfers_to_resident_sectors_other_than_gener.current), as published; "
        "tolerance Rs 1 crore (BoP rounding).",
    )
    out.constraints.append(
        constraint(
            "row.r11_total",
            "R11",
            hh,
            ["R_ROW"],
            r11,
            prov_id=cpid,
            tol_abs=ROUND_TOL,
            refs=["R11a"],
            description="R11a over the 10 groups = NAS 6.1 item 4",
        )
    )
    out.memo["r11"] = (r11, r11_pid)

    # --- R12a: outward transfers on H_U4 and H_U5 by their consumption (deviation: consumption, not income) --
    keys = ctx.satellite("households", "hh_keys")
    pf = keys.filter((pl.col("key") == "pfce_total") & (pl.col("measure") == "level"))
    lv = {r["household_group"]: float(r["value"]) for r in pf.iter_rows(named=True)}
    miss = [g for g in ("H_U4", "H_U5") if g not in lv]
    if miss:
        raise SamError(f"households/hh_keys has no pfce_total level for {miss} (rest_of_world R12a)")
    r12a = c.allocate(r12, {g: lv[g] for g in ("H_U4", "H_U5")}, "R12a H_U4/H_U5 pfce_total")
    lrs_ids = ["lrs.inr.annual.lrs_1_4.current", "lrs.inr.annual.lrs_1_5.current", "lrs.inr.annual.lrs_1_7.current"]
    lrs = ctx.rows(c.LRS, series_id=lrs_ids, vintage=c.LATEST)
    lrs_sum = float(lrs["value"].sum())
    pf_pids = sorted(set(pf.filter(pl.col("household_group").is_in(["H_U4", "H_U5"]))["prov_id"].to_list()))
    r12a_pid = ctx.prov(
        ref="R12a",
        status="estimated",
        inputs=[r12_pid, *pf_pids, *sorted(set(lrs["prov_id"].to_list()))],
        source_id="mospi_nas_2026_publication",
        notes="Total from NAS 2026; key from the households block; LRS (RBI) only as evidence for the assumption.",
        method=(
            "Gap map R12a: NAS 2026 St 6.1 'other current transfers by resident sectors other than GG' "
            f"({c.NAS61}) allocated to urban quintiles 4 and 5 (H_U4, H_U5) only, in proportion to their "
            "consumption (households' hh_keys key 'pfce_total', measure 'level'). Deviation from the gap map's "
            "'in proportion to income': group income exists only at closure, which this block cannot read; "
            "consumption is the stated proxy. Evidence that the channel is high-income: LRS gifts + maintenance "
            f"of close relatives + donations = {lrs_sum:,.2f} crore ({c.LRS}), most of BoP 1.C.1.1 personal "
            "transfers debited. Assumption: all of BoP 1.C.1 debit (incl. 'other current transfers' and any "
            "corporate part) is paid by households, as the gap map says. Low confidence."
        ),
    )
    for g, x in r12a.items():
        out.entries.append(
            entry(
                "R_ROW",
                g,
                "R12a",
                x,
                prov_id=r12a_pid,
                status="estimated",
                role="free",
                confidence="low",
                component="outward_transfers",
            )
        )
    cpid = ctx.prov(
        ref="R12",
        status="official",
        inputs=[r12_pid],
        method="Gap map R12: current transfers by resident sectors other than GG to RoW = NAS 2026 St 6.1 item 9 "
        f"({c.NAS61} s6_1.other_current_transfers_by_resident_sectors_other_than_gener.current), as published; "
        "tolerance Rs 1 crore.",
    )
    out.constraints.append(
        constraint(
            "row.r12_total",
            "R12",
            ["R_ROW"],
            hh,
            r12,
            prov_id=cpid,
            tol_abs=ROUND_TOL,
            refs=["R12a"],
            description="R12a over the household groups = NAS 6.1 item 9",
        )
    )

    # checks against the BoP (read from clean data)
    b_cr, b_cr_pid = v(ctx, c.BPM6, "bpm6.inr.bpm6_1_c_1.credit.current")
    b_db, b_db_pid = v(ctx, c.BPM6, "bpm6.inr.bpm6_1_c_1.debit.current")
    inv, inv_pid = v(ctx, c.INVIS, "invis.inr.private_transfers.receipts.current")
    ctx.check(
        "r11_vs_bop",
        "R11a total vs BoP 1.C.1 secondary income credit (other sectors)",
        sum(r11a.values()),
        b_cr,
        target_prov_id=b_cr_pid,
        tol_abs=ROUND_TOL,
    )
    ctx.check(
        "r11_vs_invisibles",
        "R11a total vs HBS invisibles private transfers receipts",
        sum(r11a.values()),
        inv,
        target_prov_id=inv_pid,
        tol_abs=ROUND_TOL,
    )
    ctx.check(
        "r12_vs_bop",
        "R12a total vs BoP 1.C.1 secondary income debit (other sectors)",
        sum(r12a.values()),
        b_db,
        target_prov_id=b_db_pid,
        tol_abs=ROUND_TOL,
    )
    out.memo["r11a"] = r11a
    out.memo["r12a"] = r12a
    out.memo["remit_state_shares"] = s_k
    # V-ROW-1: each memo carries its own ref's record id (a shared `pid` name once let R12a's id leak into R11a's)
    out.memo["r11a_inputs"] = dict(key=key, pid=r11a_pid, surv_pids=surv_pids, xw_pids=xw_pids, r11_pid=r11_pid)
    out.memo["r12a_inputs"] = dict(
        r12=r12, r12_pid=r12_pid, levels=lv, pf_pids=sorted(set(pf["prov_id"].to_list())), pid=r12a_pid
    )


# ---------------------------------------------------------------------------------------------------
# Sensitivity bands for R11a and R12a (plan s.2.1 caveats, s.2.2 'sensitivity to log'; issues rest_of_world-1/-2)
# ---------------------------------------------------------------------------------------------------

HUB_STATES = ("in-mh", "in-dl")  # plan s.6: Maharashtra and Delhi may be inflated as banking hubs


def _sat_frame(rows: list[dict[str, Any]], dims: list[str]) -> pl.DataFrame:
    schema: dict[str, pl.DataType] = {"series_id": pl.String()}
    schema.update({d: pl.String() for d in dims})
    schema.update({"value": pl.Float64(), "unit": pl.String(), "status": pl.String(), "prov_id": pl.String()})
    return pl.DataFrame([{k: r.get(k) for k in schema} for r in rows], schema=schema, orient="row").sort("series_id")


def _band_rows(prefix: str, variants: dict[str, dict[str, float]], groups: list[str], pid: str) -> list[dict]:
    """One row per (variant, group) plus band_low / band_high (min / max over the variants) per group."""
    rows: list[dict[str, Any]] = []
    for name, alloc in variants.items():
        for g in groups:
            rows.append(
                dict(series_id=f"{prefix}.{name}.{g.lower()}", variant=name, household_group=g,
                     value=alloc.get(g, 0.0), unit="INR_crore", status="estimated", prov_id=pid)
            )  # fmt: skip
    for g in groups:
        vals = [alloc.get(g, 0.0) for alloc in variants.values()]
        for name, x in (("band_low", min(vals)), ("band_high", max(vals))):
            rows.append(
                dict(series_id=f"{prefix}.{name}.{g.lower()}", variant=name, household_group=g, value=x,
                     unit="INR_crore", status="estimated", prov_id=pid)
            )  # fmt: skip
    return rows


def transfer_sensitivities(ctx: BlockContext, out: Out) -> dict[str, Satellite]:
    """r11a_sensitivity and r12a_sensitivity: memo satellites (not SAM entries) with the alternative allocations
    the plan asks to show, and the per-group band (min / max over the variants, the prior included)."""
    hh = ctx.accounts.in_group("HH")
    r11, _ = out.memo["r11"]
    m = out.memo["r11a_inputs"]
    key: dict[str, dict[str, float]] = m["key"]
    s_k: dict[str, float] = out.memo["remit_state_shares"]

    # State shares of all-India HCES consumption (households' hh_state_xwalk, the same rows as the R11a key)
    cons_k = {k: sum(d.values()) for k, d in key.items()}
    cons_tot = sum(cons_k.values())
    cons_share = {k: 100.0 * x / cons_tot for k, x in cons_k.items()}
    missing = [h for h in HUB_STATES if h not in s_k or h not in cons_share]
    if missing:
        raise SamError(f"R11a sensitivity: hub State(s) {missing} missing from the survey or the consumption key")
    hub = dict(s_k)
    for h in HUB_STATES:
        hub[h] = cons_share[h]
    variants = {
        "prior": out.memo["r11a"],
        "hub_neutral": c.remittance_by_group(r11, hub, key),
        "consumption_only": c.remittance_by_group(r11, {k: x for k, x in cons_share.items() if x > 0}, key),
    }
    hub_txt = ", ".join(f"{h} survey {s_k[h]:.2f}% -> consumption {cons_share[h]:.2f}%" for h in HUB_STATES)
    for name in ("hub_neutral", "consumption_only"):
        alt = variants[name]
        top = alt.get("H_R5", 0.0) + alt.get("H_U5", 0.0)
        ctx.log(
            f"R11a sensitivity {name}: H_R5+H_U5 {top:,.2f} (prior "
            f"{variants['prior']['H_R5'] + variants['prior']['H_U5']:,.2f}); rural share "
            f"{sum(v for g, v in alt.items() if g.startswith('H_R')) / r11:.1%}"
        )
    pid11 = ctx.prov(
        ref="R11a",
        status="estimated",
        inputs=[m["pid"], m["r11_pid"], *m["surv_pids"], *m["xw_pids"]],
        source_id="rbi_remittances_survey",
        notes="Memo: sensitivity of the R11a prior (issues rest_of_world-1); not a SAM entry.",
        method=(
            "Sensitivity band for R11a (plan s.6 remittance-survey caveats). Three allocations of the same NAS 6.1 "
            "item 4 total with the same within-State consumption key (households' hh_state_xwalk, measure "
            f"'{XWALK_MEASURE}', hces_class '{XWALK_CLASS}'): 'prior' = the R11a entries (RBI remittances survey "
            f"2023-24 State shares, {c.REMIT} vintage {c.V_REMIT}); 'hub_neutral' = the survey shares with "
            "Maharashtra and Delhi (possible banking hubs: the survey records the State of the receiving branch) "
            "replaced by their share of all-India HCES consumption in the same key and all shares renormalised "
            f"({hub_txt}); 'consumption_only' = every State at its consumption share (no remittance information: "
            "R11a proportional to consumption, the least top-heavy bound). band_low / band_high = min / max over "
            "the three per group. Assumption: these bracket the plausible range; no survey of receiving "
            "households exists."
        ),
    )
    sat11 = _sat_frame(_band_rows("r11a", variants, hh, pid11), ["variant", "household_group"])

    # R12a: plan s.2.2 'sensitivity to log': BoP 1.C.1.2 'other current transfers' debit on all 10 groups
    m12 = out.memo["r12a_inputs"]
    oct_db, oct_pid = v(ctx, c.BPM6, "bpm6.inr.bpm6_1_c_1_2.debit.current")
    lv: dict[str, float] = m12["levels"]
    miss = [g for g in hh if g not in lv]
    if miss:
        raise SamError(f"R12a sensitivity: households/hh_keys has no pfce_total level for {miss}")
    r12 = m12["r12"]
    part = c.allocate(oct_db, {g: lv[g] for g in hh}, "R12a sensitivity: other current transfers, all groups")
    rest = c.allocate(r12 - oct_db, {g: lv[g] for g in ("H_U4", "H_U5")}, "R12a sensitivity: personal, U4/U5")
    alt12 = c.add_into(dict(part), rest)
    ctx.log(
        f"R12a sensitivity: BoP 1.C.1.2 other current transfers {oct_db:,.0f} on all 10 groups -> H_U4 "
        f"{alt12['H_U4']:,.2f} / H_U5 {alt12['H_U5']:,.2f} (prior {out.memo['r12a']['H_U4']:,.2f} / "
        f"{out.memo['r12a']['H_U5']:,.2f})"
    )
    pid12 = ctx.prov(
        ref="R12a",
        status="estimated",
        inputs=[m12["pid"], m12["r12_pid"], oct_pid, *m12["pf_pids"]],
        source_id="mospi_nas_2026_publication",
        notes="Memo: sensitivity of the R12a prior (issues rest_of_world-2); not a SAM entry.",
        method=(
            "Sensitivity for R12a (plan s.2.2): 'prior' = the R12a entries (all of NAS 6.1 item 9 on H_U4/H_U5 by "
            "households' hh_keys pfce_total); 'other_transfers_all_groups' = BoP 1.C.1.2 'other current transfers' "
            f"debit ({c.BPM6} bpm6.inr.bpm6_1_c_1_2.debit.current) spread over all 10 groups by pfce_total and the "
            "remainder of NAS 6.1 item 9 on H_U4/H_U5 as in the prior. band_low / band_high = min / max per group."
        ),
    )
    sat12 = _sat_frame(
        _band_rows("r12a", {"prior": out.memo["r12a"], "other_transfers_all_groups": alt12}, hh, pid12),
        ["variant", "household_group"],
    )
    return {
        "r11a_sensitivity": Satellite(
            "R11a",
            sat11,
            "R11a remittances by group: prior, hub-neutral and consumption-only variants, band",
            decimals=6,
        ),
        "r12a_sensitivity": Satellite(
            "R12a",
            sat12,
            "R12a outward transfers by group: prior and 'other transfers on all groups', band",
            decimals=6,
        ),
    }


# ---------------------------------------------------------------------------------------------------
# R13 property income received from RoW; R14 / R14a property income paid to RoW
# ---------------------------------------------------------------------------------------------------


def _fsf_avg(ctx: BlockContext, side: str, instr: str, cps: tuple[str, ...]) -> tuple[dict[str, float], list[str]]:
    """Average FSF RoW stocks (side 'liabilities' = RoW's liabilities = India's foreign assets; 'assets' = India's
    foreign liabilities) of one instrument by FSF counterparty."""
    vals, pids = {}, []
    for cp in cps:
        a, p, _ = avg_stock(ctx, c.FSF, f"fsf.row.{side}.outstanding.{instr}.{cp}.current", vintage=c.V_FSF)
        vals[cp] = a
        pids += p
    return vals, pids


def _to_sam(fsf_vals: dict[str, float]) -> dict[str, float]:
    outv: dict[str, float] = {}
    for cp, x in fsf_vals.items():
        if x:
            c.add_into(outv, {c.FSF_TO_SAM[cp]: x})
    return outv


def _property_income(ctx: BlockContext, out: Out) -> None:
    r13_tot, r13_pid = v(ctx, c.NAS61, "s6_1.property_and_entrepreneurial_income_from_rest_of_the_world.current")
    r14_tot, r14_pid = v(ctx, c.NAS61, "s6_1.property_and_entrepreneurial_income_to_the_rest_of_the_world.current")
    re_tot, re_pid = v(ctx, c.NAS19, "s1_9.reinvested_earnings_of_foreign_companies_in_private_corporat.current")
    typ = {}
    for t, sid in (
        ("di", "bpm6_1_b_2_1"),
        ("pi", "bpm6_1_b_2_2"),
        ("oi", "bpm6_1_b_2_3"),
        ("res", "bpm6_1_b_2_4"),
        ("other", "bpm6_1_b_3"),
    ):
        for side in ("credit", "debit"):
            typ[(t, side)] = v(ctx, c.BPM6, f"bpm6.inr.{sid}.{side}.current")
    sat = out.rows("row_property_income")

    def put(
        ref: str,
        row: str,
        col: str,
        comp: str,
        val: float,
        pid: str,
        status: str,
        role: str,
        *,
        confidence: str | None = None,
        tol_rel: float | None = None,
        bop: str | None = None,
        btype: str,
        direction: str,
    ) -> None:
        if val == 0.0:
            return
        out.entries.append(
            entry(
                row,
                col,
                ref,
                val,
                prov_id=pid,
                status=status,
                role=role,
                component=comp,
                confidence=confidence,
                tol_rel=tol_rel,
                bop_function=bop,
            )
        )
        acct = col if row == "R_ROW" else row
        sat.append(
            {
                "series_id": f"{direction}.{btype}.{comp}.{acct.lower()}",
                "direction": direction,
                "bop_type": btype,
                "component": comp,
                "account": acct,
                "ref": ref,
                "entry_status": status,
                "entry_prov_id": pid,
                "value": val,
                "unit": "INR_crore",
            }
        )

    # ---------------- R13: received from RoW ----------------
    ar13, ar13_pid = v(ctx, c.RBI_AR, "sch13.b.sub_total.current", vintage=c.V_RBI_AR)
    ar14, ar14_pid = v(
        ctx, c.RBI_AR, "sch14.b.amortisation_of_premium_discount_on_foreign_securities.current", vintage=c.V_RBI_AR
    )
    res_cr, res_cr_pid = typ[("res", "credit")]
    ar = ar13 + ar14
    unexpl = res_cr - ar
    if unexpl <= 0:
        raise SamError(f"R13: BoP reserve-asset income {res_cr} does not exceed the RBI AR figure {ar} (D2-7 split)")
    pid_ar = ctx.prov(
        ref="R13",
        status="derived",
        inputs=[ar13_pid, ar14_pid],
        method=(
            "Gap map R13, DECISIONS D2-7 (CROSS_REVIEW XR-4): RBI's income on foreign-currency reserves, as its "
            f"Annual Report books it: Schedule 13(b) foreign-source interest sub-total + Schedule 14(b)(i) "
            f"amortisation of premium/discount on foreign securities ({c.RBI_AR}, vintage {c.V_RBI_AR}, 2023-24 "
            "column). Written on E_RBI <- R_ROW, anchored +-2% (RBI accounting vs BoP accrual)."
        ),
        source_id=None,
    )
    pid_unx = ctx.prov(
        ref="R13",
        status="estimated",
        inputs=[res_cr_pid, ar13_pid, ar14_pid],
        method=(
            "Gap map R13, DECISIONS D2-7: BoP 1.B.2.4 reserve-asset income credit (bpm6.inr.bpm6_1_b_2_4.credit) "
            "less the RBI Annual Report figure (Sch 13(b) + Sch 14(b)(i)): the part of BoP reserve income the "
            "RBI accounts do not show (unexplained; candidates: accrual vs RBI accounting, income on gold, SDR "
            "interest that accrues to the Union, RTP). Assumption: the whole excess accrues to E_RBI, the holder of "
            "the reserves. Free, low confidence, so balancing may place it."
        ),
        source_id="rbi_hbs_external",
        notes="Inputs from the BoP (RBI HBS) and the RBI Annual Report; the residual rests on the BoP total.",
    )
    put(
        "R13",
        "E_RBI",
        "R_ROW",
        "reserve_asset_income",
        ar,
        pid_ar,
        "derived",
        "anchored",
        tol_rel=0.02,
        btype="reserves",
        direction="credit",
    )
    put(
        "R13",
        "E_RBI",
        "R_ROW",
        "reserve_income_unexplained",
        unexpl,
        pid_unx,
        "estimated",
        "free",
        confidence="low",
        btype="reserves",
        direction="credit",
    )

    f51, f51_pids = _fsf_avg(ctx, "liabilities", "f51", ("nfc_pvt", "nfc_pub", "fc_odc", "fc_ofc", "gg_cen"))
    k_eq = _to_sam(f51)
    oi_st: dict[str, float] = {}
    oi_pids: list[str] = []
    for instr in ("f22_f29", "f4"):
        vals, p = _fsf_avg(ctx, "liabilities", instr, ("nfc_pvt", "nfc_pub", "fc_odc", "fc_ofc", "gg_cen", "gg_sta"))
        c.add_into(oi_st, _to_sam(vals))
        oi_pids += p
    di_cr, di_cr_pid = typ[("di", "credit")]
    pi_cr, pi_cr_pid = typ[("pi", "credit")]
    oi_cr, oi_cr_pid = typ[("oi", "credit")]
    ot_cr, ot_cr_pid = typ[("other", "credit")]
    pid_eq = ctx.prov(
        ref="R13",
        status="estimated",
        inputs=[di_cr_pid, pi_cr_pid, *f51_pids],
        method=(
            "Gap map R13 (fallback: the FLA census ODI sector split is not ingested). BoP 1.B.2.1 direct-investment "
            "income credit (includes reinvested earnings on outward FDI) and 1.B.2.2 portfolio income credit, each "
            "split over recipients by the FSF RoW-liability equity stocks F51 by resident counterparty "
            f"({c.FSF} fsf.row.liabilities.outstanding.f51.<cp>, vintage {c.V_FSF}, average of 2023-03-31 and "
            "2024-03-31; they equal IIP DI + PI equity assets): nfc_pvt -> E_NFPR, fc_ofc -> E_NBFC, fc_odc -> "
            "E_BANK (E_BANK = FSF ODC, XR-6). No FISIM adjustment (XR-13). Low confidence."
        ),
        source_id="rbi_hbs_external",
        notes="BoP type totals (RBI HBS); recipient key from the RBI FSF.",
    )
    pid_oi = ctx.prov(
        ref="R13",
        status="estimated",
        inputs=[oi_cr_pid, *oi_pids],
        method=(
            "Gap map R13: BoP 1.B.2.3 other-investment income credit split over recipients by the FSF RoW-liability "
            "stocks of deposits (F22_F29) and loans (F4) by resident counterparty, average of 2023-03-31 and "
            f"2024-03-31 ({c.FSF}, vintage {c.V_FSF}); RBI (fc_rbi, reserves) excluded; fc_odc -> E_BANK, nfc_pvt "
            "-> E_NFPR, fc_ofc -> E_NBFC, gg_cen -> G_CEN. Deviation from the plan: debt securities (F3) are left "
            "out of the key, because income on debt securities is portfolio or direct-investment income in BPM6, "
            "not other investment, and the FSF F3 nfc_pvt stock mirrors its asset-side twin (plan s.6). Low."
        ),
        source_id="rbi_hbs_external",
        notes="BoP type total (RBI HBS); recipient key from the RBI FSF.",
    )
    di_r13 = c.allocate(di_cr, k_eq, "R13 DI income key (FSF F51)")
    pi_r13 = c.allocate(pi_cr, k_eq, "R13 PI income key (FSF F51)")
    oi_r13 = c.allocate(oi_cr, oi_st, "R13 OI income key (FSF F22_F29 + F4)")
    for acct, x in di_r13.items():
        put(
            "R13",
            acct,
            "R_ROW",
            "di_income",
            x,
            pid_eq,
            "estimated",
            "free",
            confidence="low",
            btype="di",
            direction="credit",
        )
    for acct, x in pi_r13.items():
        put(
            "R13",
            acct,
            "R_ROW",
            "pi_income",
            x,
            pid_eq,
            "estimated",
            "free",
            confidence="low",
            btype="pi",
            direction="credit",
        )
    for acct, x in oi_r13.items():
        put(
            "R13",
            acct,
            "R_ROW",
            "oi_income",
            x,
            pid_oi,
            "estimated",
            "free",
            confidence="low",
            btype="oi",
            direction="credit",
        )
    # other primary income + the NAS-vs-BoP rounding (NAS total - sum of the five BoP types)
    bop13 = di_cr + pi_cr + oi_cr + res_cr + ot_cr
    ot13 = ot_cr + (r13_tot - bop13)
    base13: dict[str, float] = {}
    for part in (di_r13, pi_r13, oi_r13):
        c.add_into(base13, part)
    pid_ot = ctx.prov(
        ref="R13",
        status="estimated",
        inputs=[ot_cr_pid, r13_pid, di_cr_pid, pi_cr_pid, oi_cr_pid, res_cr_pid, *f51_pids, *oi_pids],
        method=(
            "Gap map R13: BoP 1.B.3 'other primary income' credit (content not documented in the ingested tables; "
            "question for RBI/NAD), plus the rounding gap NAS 2026 St 6.1 item 3 minus the sum of the five BoP "
            f"primary-income types ({r13_tot - bop13:+.2f} crore) so that R13 adds up to NAS exactly. Assumption "
            "(key): pro rata to the non-reserve R13 allocations (DI + PI + OI) by recipient. Low confidence."
        ),
        source_id="rbi_hbs_external",
        notes="BoP type totals (RBI HBS) and NAS 6.1 total; keys from the RBI FSF.",
    )
    for acct, x in c.allocate(ot13, base13, "R13 other primary income").items():
        put(
            "R13",
            acct,
            "R_ROW",
            "other_primary_income",
            x,
            pid_ot,
            "estimated",
            "free",
            confidence="low",
            btype="other",
            direction="credit",
        )

    # ---------------- R14a reinvested earnings and R14 DI distributed ----------------
    di_db, di_db_pid = typ[("di", "debit")]
    fin_eq, fin_pid = v(
        ctx, c.FLA, "fla.t8.g.financial_and_insurance_activities.equity", period="2024-03-31", vintage=c.V_FLA
    )
    tot_eq, tot_pid = v(ctx, c.FLA, "fla.t8.total.equity", period="2024-03-31", vintage=c.V_FLA)
    fc_share = fin_eq / tot_eq
    fb_inc, fb_inc_pid = v(ctx, c.RTP, "rtp.scb_pl.income_total.fb.current", vintage=c.V_RTP)
    fb_exp, fb_exp_pid = v(ctx, c.RTP, "rtp.scb_pl.expenditure_total.fb.current", vintage=c.V_RTP)
    fb_pat = fb_inc - fb_exp
    re_ratio = re_tot / di_db
    di_dist = di_db - re_tot

    def fc_split(total: float, bank_part: float, what: str) -> dict[str, float]:
        """NFC / FC by the FLA t8 equity key; FC = E_BANK (bank_part) + E_NBFC (remainder)."""
        nfc = total * (1.0 - fc_share)
        fc = total - nfc
        if not 0.0 < bank_part < fc:
            raise SamError(f"{what}: foreign banks' part {bank_part:,.2f} is not inside the FC total {fc:,.2f}")
        return {"E_NFPR": nfc, "E_BANK": bank_part, "E_NBFC": fc - bank_part}

    r14a = fc_split(re_tot, fb_pat * re_ratio, "R14a")
    dist = fc_split(di_dist, fb_pat * (1.0 - re_ratio), "R14 di_distributed")
    fc_bank_ratio = (r14a["E_BANK"] + dist["E_BANK"]) / (
        r14a["E_BANK"] + r14a["E_NBFC"] + dist["E_BANK"] + dist["E_NBFC"]
    )
    key_method = (
        f"NFC vs FC by the FLA census 2023-24 round (vintage {c.V_FLA}), market-value equity at 2024-03-31: FC "
        f"share = fla.t8.g.financial_and_insurance_activities.equity / fla.t8.total.equity = {fc_share:.4%} "
        "(face-value sensitivity fla.t2b.fc.fdi_equity / fla.t2b.total.fdi_equity logged). E_NFPU = 0: the NAS memo "
        "is 'private corporations' and the FSF has no public-NFC RoW counterparty. FC sub-split: E_BANK = foreign "
        f"banks' profit ({c.RTP} rtp.scb_pl.income_total.fb - expenditure_total.fb, vintage {c.V_RTP}), divided "
        "reinvested : distributed in the national ratio (NAS reinvested earnings / BoP DI debit); the FC remainder "
        "goes to E_NBFC; E_INSP = 0 (no private-FC key is readable here: fincorp builds after this block; logged)."
    )
    pid_r14a = ctx.prov(
        ref="R14a",
        status="estimated",
        inputs=[re_pid, di_db_pid, fin_pid, tot_pid, fb_inc_pid, fb_exp_pid],
        method="Gap map R14a: total = NAS 2026 St 1.9 memo 'reinvested earnings of foreign companies in private "
        f"corporations' ({c.NAS19}). Payers: {key_method}",
        source_id="mospi_nas_2026_publication",
        notes="Total from NAS 2026; keys from the RBI FLA census and RBI Trend and Progress.",
    )
    for acct, x in r14a.items():
        put(
            "R14a",
            "R_ROW",
            acct,
            "reinvested_earnings",
            x,
            pid_r14a,
            "estimated",
            "free",
            confidence="medium" if acct == "E_NFPR" else "low",
            bop="FDI_reinvested_earnings",
            btype="di",
            direction="debit",
        )
    out.memo["r14a"] = r14a
    out.memo["re"] = (re_tot, re_pid)
    out.memo["key_pids"] = sorted({fin_pid, tot_pid, fb_inc_pid, fb_exp_pid})
    out.memo["fc_share"] = (fc_share, [fin_pid, tot_pid])
    out.memo["fc_bank_ratio"] = fc_bank_ratio
    pid_dist = ctx.prov(
        ref="R14",
        status="estimated",
        inputs=[di_db_pid, re_pid, fin_pid, tot_pid, fb_inc_pid, fb_exp_pid],
        method="Gap map R14, direct-investment income distributed: BoP 1.B.2.1 DI income debit "
        "(bpm6.inr.bpm6_1_b_2_1.debit, includes reinvested earnings under BPM6) less NAS 1.9 reinvested earnings "
        f"(written as R14a). Payers: {key_method} No FISIM adjustment on RoW property income (XR-13).",
        source_id="rbi_hbs_external",
        notes="BoP DI debit (RBI HBS) less the NAS 1.9 memo; keys from FLA and RTP.",
    )
    for acct, x in dist.items():
        put(
            "R14",
            "R_ROW",
            acct,
            "di_distributed",
            x,
            pid_dist,
            "estimated",
            "free",
            confidence="medium" if acct == "E_NFPR" else "low",
            btype="di",
            direction="debit",
        )

    # ---------------- R14 portfolio income: FPI interest on government paper (XR-12), the rest ----------------
    pi_db, pi_db_pid = typ[("pi", "debit")]
    ml, ml_pid = v(ctx, c.FA_EXP, "fa9.2049.01.101")
    reis = [v(ctx, c.FA_REC, s) for s in ("fa8.0049.03.116", "fa8.0049.03.117")]
    tb = [v(ctx, c.FA_EXP, s) for s in ("fa9.2049.01.103", "fa9.2049.01.108", "fa9.2049.01.110")]
    sdl, sdl_pid = v(
        ctx, c.SF_APP, "app2.total_expenditure.ii.c.2.ii.a-interest_on_market_loans.in.all_states_uts.actuals"
    )
    shares_t107 = {}
    t107_pids: list[str] = []
    for inst in ("gsec_central", "tbills", "sgs"):
        a, p, _ = avg_stock(ctx, c.T107, f"t107.{inst}.share.fpi", vintage=c.LATEST, unit="percent", price_basis=None)
        shares_t107[inst] = a / 100.0
        t107_pids += p
    ml_net = ml - sum(x for x, _ in reis)
    fpi_g = shares_t107["gsec_central"] * ml_net
    fpi_t = shares_t107["tbills"] * sum(x for x, _ in tb)
    fpi_s = shares_t107["sgs"] * sdl
    pid_fpi = ctx.prov(
        ref="R14",
        status="estimated",
        inputs=[ml_pid, *(p for _, p in reis), *(p for _, p in tb), sdl_pid, *t107_pids],
        method=(
            "Gap map R14, FPI interest on government paper, with fincorp's formula (CROSS_REVIEW XR-12): average of "
            f"the FPI holding shares at 2023-03-31 and 2024-03-31 ({c.T107} HBS T107 t107.<instrument>.share.fpi, "
            "latest vintage) x the payer's interest line. Central dated securities: Union Finance Accounts "
            f"'interest on market loans' ({c.FA_EXP} fa9.2049.01.101) net of the accrued interest and premium "
            f"received on re-issues ({c.FA_REC} fa8.0049.03.116 + .117; they arise on dated securities only, so "
            "each holder bears its pro-rata share). T-bills: fa9.2049.01.103 + .108 + .110 (the .103 line is "
            "treated as 91-day T-bills, as fincorp does). SDLs: RBI State Finances App. 2 'interest on market "
            f"loans', all States/UTs ({c.SF_APP}). Estimated: shares are of face value outstanding."
        ),
        source_id="cga_finance_accounts_aag",
        notes="Payer interest lines (Union Finance Accounts, RBI State Finances) x RBI HBS T107 FPI shares.",
    )
    put(
        "R14",
        "R_ROW",
        "G_CEN",
        "fpi_gsec_interest",
        fpi_g,
        pid_fpi,
        "estimated",
        "free",
        confidence="medium",
        btype="pi",
        direction="debit",
    )
    put(
        "R14",
        "R_ROW",
        "G_CEN",
        "fpi_tbill_interest",
        fpi_t,
        pid_fpi,
        "estimated",
        "free",
        confidence="low",
        btype="pi",
        direction="debit",
    )
    put(
        "R14",
        "R_ROW",
        "G_STA",
        "fpi_sdl_interest",
        fpi_s,
        pid_fpi,
        "estimated",
        "free",
        confidence="low",
        btype="pi",
        direction="debit",
    )
    pi_other = pi_db - fpi_g - fpi_t - fpi_s
    if pi_other <= 0:
        raise SamError(f"R14: FPI government interest {fpi_g + fpi_t + fpi_s:,.2f} exceeds BoP PI debit {pi_db:,.2f}")
    nfc = pi_other * (1.0 - fc_share)
    fc = pi_other - nfc
    pi_split = {"E_NFPR": nfc, "E_BANK": fc * fc_bank_ratio, "E_NBFC": fc * (1.0 - fc_bank_ratio)}
    pid_pio = ctx.prov(
        ref="R14",
        status="estimated",
        inputs=[pi_db_pid, fin_pid, tot_pid, fb_inc_pid, fb_exp_pid, ml_pid, sdl_pid, *t107_pids],
        method=(
            "Gap map R14, portfolio income other than FPI interest on government paper: BoP 1.B.2.2 PI debit less "
            "the three fpi_*_interest components (FPI equity dividends plus interest on FPI-held corporate bonds "
            f"and ADR/GDR). Payers: NFC vs FC by the FLA t8 equity key ({c.FLA}, vintage {c.V_FLA}); the FC part "
            "split E_BANK : E_NBFC in the ratio of their DI payments (R14 di_distributed + R14a). Low confidence "
            "(FPIs are heavier in listed financials than FDI is)."
        ),
        source_id="rbi_hbs_external",
        notes="BoP PI debit (RBI HBS); keys from FLA and RTP; government part as in the fpi_*_interest record.",
    )
    for acct, x in pi_split.items():
        put(
            "R14",
            "R_ROW",
            acct,
            "pi_other",
            x,
            pid_pio,
            "estimated",
            "free",
            confidence="low",
            btype="pi",
            direction="debit",
        )

    # ---------------- R14 other investment income ----------------
    oi_db, oi_db_pid = typ[("oi", "debit")]
    ea, ea_pid = v(ctx, c.FA_EXP, "fa9.2049.02.total")
    pid_ea = ctx.prov(
        ref="R14",
        status="derived",
        inputs=[ea_pid],
        method="Gap map R14, interest on sovereign external debt: Union Finance Accounts MH 2049.02 'interest on "
        f"external debt' ({c.FA_EXP} fa9.2049.02.total), a cash figure written on R_ROW <- G_CEN; anchored +-10% "
        "for cash vs accrual.",
    )
    put(
        "R14",
        "R_ROW",
        "G_CEN",
        "ext_assistance_interest",
        ea,
        pid_ea,
        "derived",
        "anchored",
        tol_rel=0.10,
        btype="oi",
        direction="debit",
    )
    nri_avg, nri_pids, _ = avg_stock(ctx, c.NRI, "nri.stock.inr.total.current", vintage=c.LATEST)
    cod, cod_pid = v(
        ctx, c.RTP, "rtp.scb_cost_return.cost_of_deposits.scb", vintage=c.V_RTP, unit="percent", price_basis=None
    )
    nri_int = nri_avg * cod / 100.0
    pid_nri = ctx.prov(
        ref="R14",
        status="estimated",
        inputs=[*nri_pids, cod_pid],
        method="Gap map R14, NRI-deposit interest -> E_BANK: average NRI deposit stock at 2023-03-31 and 2024-03-31 "
        f"({c.NRI} nri.stock.inr.total, latest vintage) x SCB cost of deposits 2023-24 ({c.RTP} "
        f"rtp.scb_cost_return.cost_of_deposits.scb, vintage {c.V_RTP}). Assumption: NRI deposits cost the "
        "all-SCB average rate (FCNR(B) pays less, NRE term more). Medium confidence.",
        source_id="rbi_nri_deposits",
        notes="NRI deposit stocks (RBI HBS) x the SCB cost of deposits (RBI Trend and Progress).",
    )
    put(
        "R14",
        "R_ROW",
        "E_BANK",
        "nri_deposit_interest",
        nri_int,
        pid_nri,
        "estimated",
        "free",
        confidence="medium",
        btype="oi",
        direction="debit",
    )
    oi_rest = oi_db - ea - nri_int
    if oi_rest <= 0:
        raise SamError(f"R14: OI debit {oi_db} does not cover external-debt and NRI interest ({ea + nri_int:,.2f})")
    loans, lp = _fsf_avg(ctx, "assets", "f4", ("fc_odc", "fc_ofc", "nfc_pvt", "nfc_pub"))
    deps, dp = _fsf_avg(ctx, "assets", "f22_f29", ("fc_odc", "fc_rbi"))
    odc_other_dep = deps["fc_odc"] - nri_avg
    if odc_other_dep < 0:
        raise SamError(f"R14: FSF ODC deposits held by RoW {deps['fc_odc']:,.0f} < NRI deposits {nri_avg:,.0f}")
    key_oi = _to_sam(loans)
    c.add_into(key_oi, {"E_BANK": odc_other_dep, "E_RBI": deps["fc_rbi"]})
    pid_oio = ctx.prov(
        ref="R14",
        status="estimated",
        inputs=[oi_db_pid, ea_pid, *nri_pids, cod_pid, *lp, *dp],
        method=(
            "Gap map R14, other-investment interest other than external assistance and NRI deposits (ECB, trade-"
            "related and other loans, other deposits): BoP 1.B.2.3 OI debit less ext_assistance_interest and "
            "nri_deposit_interest, split by payer in proportion to the FSF RoW-asset stocks (India's liabilities) "
            f"averaged over 2023-03-31 and 2024-03-31 ({c.FSF}, vintage {c.V_FSF}): loans F4 fc_odc -> E_BANK, "
            "fc_ofc -> E_NBFC, nfc_pvt -> E_NFPR; deposits F22_F29 fc_odc less the NRI deposit stock -> E_BANK, "
            "fc_rbi -> E_RBI. Left out: F4 gg_cen (its interest is ext_assistance_interest), F4 hh (tiny), trade "
            "credit F81 (mostly non-interest-bearing). No FISIM adjustment (XR-13). Low confidence."
        ),
        source_id="rbi_hbs_external",
        notes="BoP OI debit (RBI HBS) less the FA and NRI components; key from the RBI FSF.",
    )
    for acct, x in c.allocate(oi_rest, key_oi, "R14 OI other interest key").items():
        put(
            "R14",
            "R_ROW",
            acct,
            "oi_other_interest",
            x,
            pid_oio,
            "estimated",
            "free",
            confidence="low",
            btype="oi",
            direction="debit",
        )

    # ---------------- R14 reserve-asset debit, other primary income ----------------
    res_db, res_db_pid = typ[("res", "debit")]
    pid_rd = ctx.prov(
        ref="R14",
        status="estimated",
        inputs=[res_db_pid],
        method="Gap map R14: BoP 1.B.2.4 reserve-assets income debit (content undocumented in the ingested tables; "
        "probably charges on SDR allocations, IIP SDR liabilities). Assumption: all of it is paid by E_RBI; it "
        "might belong to G_CEN. Low confidence.",
    )
    put(
        "R14",
        "R_ROW",
        "E_RBI",
        "reserve_asset_debit",
        res_db,
        pid_rd,
        "estimated",
        "free",
        confidence="low",
        btype="reserves",
        direction="debit",
    )
    ot_db, ot_db_pid = typ[("other", "debit")]
    bop14 = di_db + pi_db + oi_db + res_db + ot_db
    ot14 = ot_db + (r14_tot - bop14)
    base14: dict[str, float] = {}
    for e in out.entries:
        if e["ref"] == "R14" and e["row"] == "R_ROW":
            c.add_into(base14, {e["col"]: e["value"]})
    pid_ot14 = ctx.prov(
        ref="R14",
        status="estimated",
        inputs=[ot_db_pid, r14_pid, di_db_pid, pi_db_pid, oi_db_pid, res_db_pid],
        method=(
            "Gap map R14: BoP 1.B.3 'other primary income' debit (content undocumented; question for RBI/NAD), plus "
            "the rounding gap NAS 2026 St 6.1 item 8 minus the sum of the five BoP primary-income types "
            f"({r14_tot - bop14:+.2f} crore) so that R14 + R14a add up to NAS exactly. Assumption (key): pro rata to "
            "the other R14 components by payer (R14a excluded). Low confidence."
        ),
        source_id="rbi_hbs_external",
        notes="BoP type totals (RBI HBS) and the NAS 6.1 total.",
    )
    for acct, x in c.allocate(ot14, base14, "R14 other primary income").items():
        put(
            "R14",
            "R_ROW",
            acct,
            "other_primary_income",
            x,
            pid_ot14,
            "estimated",
            "free",
            confidence="low",
            btype="other",
            direction="debit",
        )

    # ---------------- constraints ----------------
    accts = list(c.PROPERTY_ACCOUNTS)
    p13 = ctx.prov(
        ref="R13",
        status="official",
        inputs=[r13_pid],
        method=f"Gap map R13 total: NAS 2026 St 6.1 item 3, property and entrepreneurial income from RoW "
        f"({c.NAS61}), as published; tolerance Rs 1 crore (BoP rounding).",
    )
    out.constraints.append(
        constraint(
            "row.r13_total",
            "R13",
            accts,
            ["R_ROW"],
            r13_tot,
            prov_id=p13,
            tol_abs=ROUND_TOL,
            refs=["R13"],
            description="R13 by recipient = NAS 6.1 item 3",
        )
    )
    p14 = ctx.prov(
        ref="R14",
        status="official",
        inputs=[r14_pid],
        method=f"Gap map R14 total: NAS 2026 St 6.1 item 8, property and entrepreneurial income to RoW "
        f"({c.NAS61}; includes reinvested earnings, R14a), as published; tolerance Rs 1 crore.",
    )
    out.constraints.append(
        constraint(
            "row.r14_total",
            "R14",
            ["R_ROW"],
            accts,
            r14_tot,
            prov_id=p14,
            tol_abs=ROUND_TOL,
            refs=["R14", "R14a"],
            description="R14 + R14a by payer = NAS 6.1 item 8",
        )
    )
    p14a = ctx.prov(
        ref="R14a",
        status="official",
        inputs=[re_pid],
        method=f"Gap map R14a total: NAS 2026 St 1.9 memo, reinvested earnings of foreign companies in "
        f"private corporations ({c.NAS19}), as published; tolerance Rs 1 crore.",
    )
    out.constraints.append(
        constraint(
            "row.r14a_total",
            "R14a",
            ["R_ROW"],
            list(c.R14A_PAYERS),
            re_tot,
            prov_id=p14a,
            tol_abs=ROUND_TOL,
            refs=["R14a"],
            description="R14a by payer = NAS 1.9 reinvested earnings",
        )
    )
    # BoP debit type totals bind (components filter, FRAMEWORK_REQUESTS P-1); credit types do not (see issues)
    for t, comps, refs, tv in (
        ("di", ["di_distributed", "reinvested_earnings"], ["R14", "R14a"], typ[("di", "debit")]),
        (
            "pi",
            ["fpi_gsec_interest", "fpi_tbill_interest", "fpi_sdl_interest", "pi_other"],
            ["R14"],
            typ[("pi", "debit")],
        ),
        ("oi", ["ext_assistance_interest", "nri_deposit_interest", "oi_other_interest"], ["R14"], typ[("oi", "debit")]),
        ("reserves", ["reserve_asset_debit"], ["R14"], typ[("res", "debit")]),
    ):
        pt = ctx.prov(
            ref="R14",
            status="official",
            inputs=[tv[1]],
            method=f"Gap map R14: BoP {t} primary-income debit by type (RBI HBS, BPM6), as published, as the "
            f"total of the R14/R14a components {comps}; tolerance Rs 1 crore (whole-crore publication).",
        )
        out.constraints.append(
            constraint(
                f"row.r14_type.{t}",
                "R14",
                ["R_ROW"],
                accts,
                tv[0],
                prov_id=pt,
                tol_abs=ROUND_TOL,
                refs=refs,
                components=comps,
                description=f"R14 {t} components = BoP 1.B.2 {t} debit",
            )
        )

    # ---------------- checks ----------------
    inv14, inv14_pid = v(ctx, c.INVIS, "invis.inr.income.investment.payments.current")
    r14_sum = sum(e["value"] for e in out.entries if e["ref"] in ("R14", "R14a"))
    r13_sum = sum(e["value"] for e in out.entries if e["ref"] == "R13")
    ctx.check("r13_total", "R13 entries vs NAS 6.1 item 3", r13_sum, r13_tot, target_prov_id=r13_pid, tol_abs=0.01)
    ctx.check(
        "r14_total", "R14 + R14a entries vs NAS 6.1 item 8", r14_sum, r14_tot, target_prov_id=r14_pid, tol_abs=0.01
    )
    ctx.check(
        "r14_vs_invisibles",
        "R14 + R14a vs HBS invisibles investment income payments",
        r14_sum,
        inv14,
        target_prov_id=inv14_pid,
        tol_abs=ROUND_TOL,
    )
    ctx.check(
        "r14a_total",
        "R14a entries vs NAS 1.9 reinvested earnings",
        sum(r14a.values()),
        re_tot,
        target_prov_id=re_pid,
        tol_abs=0.01,
    )
    bre, bre_pid = v(ctx, c.BPM6, "bpm6.inr.bpm6_3_1_a_1_2.credit.current")
    ctx.check(
        "r14a_vs_bop",
        "R14a vs BoP 3.1.A.1.2 reinvested earnings (FDI in India)",
        sum(r14a.values()),
        bre,
        target_prov_id=bre_pid,
        tol_abs=ROUND_TOL,
    )
    ctx.check(
        "r13_reserves_vs_bop",
        "R13 E_RBI (both components) vs BoP 1.B.2.4 credit",
        ar + unexpl,
        res_cr,
        target_prov_id=res_cr_pid,
        tol_abs=ROUND_TOL,
    )
    ctx.log(
        f"R13 E_RBI (D2-7): RBI AR reserve income {ar:,.2f} vs BoP 1.B.2.4 credit {res_cr:,.2f}: the "
        f"unexplained BoP excess {unexpl:,.2f} ({unexpl / res_cr:.1%}) is its own free, low-confidence component"
    )
    fc_t2b, fc_t2b_pid = v(ctx, c.FLA, "fla.t2b.fc.fdi_equity", period="2024-03-31", vintage=c.V_FLA)
    tot_t2b, _ = v(ctx, c.FLA, "fla.t2b.total.fdi_equity", period="2024-03-31", vintage=c.V_FLA)
    ctx.log(
        f"R14a sensitivity: FC share face value (FLA t2b) {fc_t2b / tot_t2b:.4%} vs market value (t8) "
        f"{fc_share:.4%}: FC R14a would be {re_tot * fc_t2b / tot_t2b:,.2f} instead of {re_tot * fc_share:,.2f}"
    )
    out.memo["t2b_fc_share"] = fc_t2b / tot_t2b
    out.memo["r13_nas_minus_bop"] = r13_tot - bop13
    out.memo["r14_nas_minus_bop"] = r14_tot - bop14
    out.memo["r13_unexplained"] = unexpl


# ---------------------------------------------------------------------------------------------------
# K5 RoW saving; D2 the NAS-BoP CIF reconciliation
# ---------------------------------------------------------------------------------------------------


def _k5_d2(ctx: BlockContext, out: Out) -> None:
    nci, nci_pid = v(ctx, c.NAS19, "s1_9.net_capital_inflow_from_row.current")
    surplus, surplus_pid = v(ctx, c.NAS61, "s6_1.surplus_on_current_transactions.current")
    if abs(nci + surplus) > 0.01:
        raise SamError(f"K5: NAS 1.9 net capital inflow {nci} != -(NAS 6.1 surplus {surplus})")
    pid = ctx.prov(
        ref="K5",
        status="official",
        inputs=[nci_pid],
        method=f"Gap map K5: RoW saving = NAS 2026 St 1.9 net capital inflow from RoW ({c.NAS19}), as published; equal "
        "to minus NAS 6.1 surplus on current transactions (asserted to Rs 0.01 crore). NAS, not the BoP current "
        "account: NAS books government transfers with RoW (BoP 1.C.2) as capital transfers (external_sector-5).",
    )
    out.entries.append(entry("K_ROW", "R_ROW", "K5", nci, prov_id=pid, status="official", role="fixed"))
    ca, ca_pid = v(ctx, c.BPM6, "bpm6.inr.bpm6_1.net.current")
    gov, gov_pid = v(ctx, c.BPM6, "bpm6.inr.bpm6_1_c_2.net.current")
    ctx.check(
        "k5_vs_surplus",
        "K5 vs minus NAS 6.1 surplus on current transactions",
        nci,
        -surplus,
        target_prov_id=surplus_pid,
        tol_abs=0.01,
    )
    ctx.check(
        "k5_bop_bridge",
        "K5 + BoP current account balance vs BoP 1.C.2 government transfers (net): the NAS "
        "vs BoP difference is exactly the government transfers NAS moves to capital",
        nci + ca,
        gov,
        target_prov_id=gov_pid,
        tol_abs=ROUND_TOL,
    )
    out.memo["k5"] = (nci, nci_pid, ca_pid)

    cif, cif_pid = v(ctx, c.SUT_SUPPLY, "supply.cif_adj.cif.current")
    cif_tot, _ = v(ctx, c.SUT_SUPPLY, "supply.cif_adj.total.current")
    if cif_tot != 0.0:
        raise SamError(f"D2: SUT CIF-adjustment memo row nets to {cif_tot}, not 0 (io_tables-5)")
    imp, imp_pid = v(ctx, c.SUT_SUPPLY, "supply.imports.total.current")
    imp_after, _ = v(ctx, c.SUT_SUPPLY, "supply.imports_after_cif.total.current")
    nas_cif, nas_cif_pid = v(ctx, c.NAS61, "s6_1.adjustment_for_cif_in_import_of_services.current")
    pid = ctx.prov(
        ref="D2",
        status="official",
        inputs=[cif_pid],
        method=(
            "Gap map D2: NAS-BoP CIF reconciliation (CIF adjustment on imports of services), pinned, from the SUT "
            f"2023-24 Supply table memo row 'CIF' of the CIF-adjustment column ({c.SUT_SUPPLY} "
            "supply.cif_adj.cif.current), as published. The SUT value, not NAS 6.1 item 18 (rounded to whole "
            "crore), because production's P6 vector is the SUT's CIF-adjusted import column: P6 + D2 then equals "
            "NAS 6.1 imports and R_ROW closes to ~Rs 0.0004 crore. Rendered as 'NAS-BoP CIF reconciliation', "
            "never as money paid abroad."
        ),
    )
    out.entries.append(
        entry(
            "R_ROW", "X_DISC", "D2", cif, prov_id=pid, status="official", role="fixed", component="cif_reconciliation"
        )
    )
    ctx.check(
        "d2_vs_nas61",
        "D2 (SUT CIF memo) vs NAS 6.1 adjustment for CIF in imports of services",
        cif,
        nas_cif,
        target_prov_id=nas_cif_pid,
        tol_abs=ROUND_TOL,
    )
    ctx.check(
        "d2_vs_sut_imports",
        "D2 vs SUT imports - imports after CIF adjustment",
        cif,
        imp - imp_after,
        target_prov_id=imp_pid,
        tol_abs=0.01,
    )
    p6 = ctx.block_entries("production").filter(pl.col("ref") == "P6")
    nas_imp, nas_imp_pid = v(ctx, c.NAS61, "s6_1.imports.current")
    ctx.check(
        "p6_plus_d2_vs_nas_imports",
        "production P6 + D2 vs NAS 6.1 imports",
        float(p6["value"].sum()) + cif,
        nas_imp,
        target_prov_id=nas_imp_pid,
        tol_abs=0.01,
    )
    out.memo["d2"] = cif


# ---------------------------------------------------------------------------------------------------
# BoP acceptance totals (SPEC s.6(c)): current receipts and disbursements over every block's entries
# ---------------------------------------------------------------------------------------------------


def _acceptance(ctx: BlockContext, out: Out) -> None:
    a = ctx.accounts
    dom = (
        a.in_group("COM")
        + a.in_group("FAC")
        + a.in_group("HH")
        + a.in_group("NFC")
        + a.in_group("FC")
        + a.in_group("GOV")
    )
    rec, rec_pid = v(ctx, c.NAS61, "s6_1.current_receipts.current")
    dis, dis_pid = v(ctx, c.NAS61, "s6_1.current_disbursements.current")
    p1 = ctx.prov(
        ref="K5",
        status="official",
        inputs=[rec_pid],
        method=f"BoP acceptance total (SPEC s.6(c)): NAS 2026 St 6.1 current receipts ({c.NAS61}), as "
        "published: exports (production P5) + CE from RoW (factors V3) + property income (R13) + current "
        "transfers (R11; no R15, government books its RoW transfers as capital, K6). Rs 1 crore.",
    )
    p2 = ctx.prov(
        ref="K5",
        status="official",
        inputs=[dis_pid],
        method=f"BoP acceptance total (SPEC s.6(c)): NAS 2026 St 6.1 current disbursements ({c.NAS61}), as "
        "published: imports (production P6 + D2 CIF reconciliation) + CE to RoW (factors V4) + property "
        "income (R14, R14a) + current transfers (R12). Rs 1 crore.",
    )
    out.constraints.append(
        constraint(
            "row.current_receipts",
            "K5",
            dom,
            ["R_ROW"],
            rec,
            prov_id=p1,
            tol_abs=ROUND_TOL,
            description="Every block's entries paid by R_ROW to domestic accounts = NAS 6.1 current receipts",
        )
    )
    out.constraints.append(
        constraint(
            "row.current_disbursements",
            "K5",
            ["R_ROW"],
            [*dom, "X_DISC"],
            dis,
            prov_id=p2,
            tol_abs=ROUND_TOL,
            description="Every block's entries paid to "
            "R_ROW by domestic accounts and X_DISC = NAS 6.1 current disbursements",
        )
    )
    # R_ROW closure in the prior, with production's P5/P6 and V3/V4 read from NAS 6.1 (factors writes them)
    prod = ctx.block_entries("production")
    p5 = float(prod.filter(pl.col("ref") == "P5")["value"].sum())
    p6 = float(prod.filter(pl.col("ref") == "P6")["value"].sum())
    v3, _ = v(ctx, c.NAS61, "s6_1.compensation_of_employees_from_rest_of_the_world.current")
    v4, _ = v(ctx, c.NAS61, "s6_1.compensation_of_employees_to_the_rest_of_the_world.current")
    mine = out.entries

    def s(pred: Any) -> float:
        return sum(e["value"] for e in mine if pred(e))

    row_side = p6 + v4 + s(lambda e: e["row"] == "R_ROW")
    col_side = p5 + v3 + s(lambda e: e["col"] == "R_ROW")
    k5 = s(lambda e: e["ref"] == "K5")
    ctx.check(
        "r_row_disbursements",
        "R_ROW row (P6 + D2 + V4 from NAS + R12a + R14 + R14a) vs NAS 6.1 current disbursements",
        row_side,
        dis,
        target_prov_id=dis_pid,
        tol_abs=ROUND_TOL,
    )
    ctx.check(
        "r_row_receipts",
        "R_ROW column less K5 (P5 + V3 from NAS + R11a + R13) vs NAS 6.1 current receipts",
        col_side - k5,
        rec,
        target_prov_id=rec_pid,
        tol_abs=ROUND_TOL,
    )
    ctx.check(
        "r_row_closes",
        "R_ROW row - column in the prior (with V3/V4 from NAS 6.1): 0",
        row_side - col_side,
        0.0,
        target_prov_id=dis_pid,
        tol_abs=0.01,
    )
