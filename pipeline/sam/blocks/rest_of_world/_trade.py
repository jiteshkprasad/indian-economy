"""Memo satellites outside the SAM: S1 goods by partner x HS chapter, S2 services by partner x EBOPS, S3 remittance
sources by country (plan s.2.9-2.11). None of them is scaled into SAM cells (P5/P6 stay production's SUT vectors).
"""

from __future__ import annotations

from typing import Any

import polars as pl

from pipeline.sam.blocks.rest_of_world import _common as c
from pipeline.sam.blocks.rest_of_world._common import Out
from pipeline.sam.blocks.rest_of_world._current import v
from pipeline.sam.framework import BlockContext, SamError, Satellite

# BoP BPM6 services items 1.A.b.1..13 -> OECD-WTO BaTIS EBOPS 2010 codes (1.A.b.13 'others n.i.e.' has no EBOPS
# item: its partner shares are those of total services, 's')
BPM6_TO_EBOPS = {
    1: "sa",
    2: "sb",
    3: "sc",
    4: "sd",
    5: "se",
    6: "sf",
    7: "sg",
    8: "sh",
    9: "si",
    10: "sj",
    11: "sk",
    12: "sl",
    13: "s",
}
FY_WEIGHTS = {"2023": 0.75, "2024": 0.25}  # gap map S1/S2: FY 2023-24 = 9 months of CY2023 + 3 months of CY2024
ITES_SINGLE_COUNTRY = {"united_states_of_america": "usa", "united_kingdom": "gbr", "canada": "can"}
COMTRADE_TO_ISO = {"s19": "twn"}  # trade_satellites-10: Comtrade 'Other Asia, nes' (490) is Taiwan
SAT_DIMS_S1 = ["flow", "partner", "partner_type", "hs2", "measure"]
SAT_DIMS_S2 = ["flow", "bop_item", "ebops", "partner", "measure"]


def _frame(rows: list[dict[str, Any]], dims: list[str]) -> pl.DataFrame:
    schema: dict[str, pl.DataType] = {"series_id": pl.String()}
    schema.update({d: pl.String() for d in dims})
    schema.update({"value": pl.Float64(), "unit": pl.String(), "status": pl.String(), "prov_id": pl.String()})
    return pl.DataFrame([{k: r.get(k) for k in schema} for r in rows], schema=schema, orient="row").sort("series_id")


def build_trade(ctx: BlockContext, out: Out) -> dict[str, Satellite]:
    return {
        "s3_remittance_sources": _s3(ctx, out),
        "s2_services_by_partner": _s2(ctx, out),
        "s1_goods_by_partner": _s1(ctx, out),
    }


# ---------------------------------------------------------------------------------------------------
# S3 remittance sources
# ---------------------------------------------------------------------------------------------------


def _s3(ctx: BlockContext, out: Out) -> Satellite:
    r11, r11_pid = out.memo["r11"]
    rows = ctx.rows(c.REMIT, vintage=c.V_REMIT, unit="percent", price_basis=None).filter(
        pl.col("series_id").str.starts_with("remit.source_country.")
    )
    raw = {sid.rsplit(".", 1)[1]: float(x) for sid, x in zip(rows["series_id"], rows["value"])}
    tot = sum(raw.values())
    if abs(tot - 100.0) > 0.5:
        raise SamError(f"S3: remittance source-country shares sum to {tot} (not ~100)")
    ctx.log(f"S3: {len(raw)} source rows, shares sum to {tot:.2f}%; normalised to 100 (external_sector-13)")
    sh = c.shares(raw, "S3 source-country shares")
    pid = ctx.prov(
        ref="S3",
        status="estimated",
        inputs=[r11_pid, *sorted(set(rows["prov_id"].to_list()))],
        method=(
            "Gap map S3: RBI remittances survey 2023-24 round source-country shares "
            f"({c.REMIT} remit.source_country.<iso3> and 'others', vintage {c.V_REMIT}; bank channel), which sum to "
            f"{tot:.2f}% as published and are normalised to 100, applied to the R11 total (NAS 2026 St 6.1 item 4). "
            "Estimated: bank-channel shares applied to all transfers. The 2016-17 and 2020-21 rounds are not used "
            "(territory scope ambiguous, external_sector-20)."
        ),
        source_id="rbi_remittances_survey",
        notes="Shares from the RBI survey; total from NAS 2026.",
    )
    out_rows = []
    for k, s in sh.items():
        for measure, val, unit in (("share", s, "ratio"), ("inr_crore", r11 * s, "INR_crore")):
            out_rows.append(
                {
                    "series_id": f"s3.{k}.{measure}",
                    "country": k.upper() if k != "others" else "others",
                    "measure": measure,
                    "value": val,
                    "unit": unit,
                    "status": "estimated",
                    "prov_id": pid,
                }
            )
    return Satellite(
        "S3",
        _frame(out_rows, ["country", "measure"]),
        "Remittances received by source country (RBI survey 2023-24 shares x R11)",
        decimals=9,
    )


# ---------------------------------------------------------------------------------------------------
# S2 services by partner and EBOPS
# ---------------------------------------------------------------------------------------------------


def _batis_shares(ctx: BlockContext, flow: str, ebops: str) -> tuple[dict[str, float], list[str]]:
    """FY partner shares for one flow x EBOPS item: 0.75 x CY2023 share + 0.25 x CY2024 share, shares of
    BaTIS balanced values in the World ('w') total. Shares only: balanced levels are not BoP levels."""
    df = ctx.rows(c.BATIS, period=None, vintage=c.LATEST, unit="USD_million", price_basis=None, allow_empty=True)
    pre = f"batis.{flow}.{ebops}."
    df = df.filter(pl.col("series_id").str.starts_with(pre) & pl.col("series_id").str.ends_with(".balanced.current"))
    fy: dict[str, float] = {}
    for yr, w in FY_WEIGHTS.items():
        y = df.filter(pl.col("period") == yr)
        world = y.filter(pl.col("series_id") == f"{pre}w.balanced.current")
        if world.height != 1 or world["value"][0] <= 0:
            raise SamError(f"S2: BaTIS {flow} {ebops} {yr}: no positive World total")
        wv = float(world["value"][0])
        for sid, x in zip(y["series_id"], y["value"]):
            p = sid[len(pre) :].split(".")[0]
            if p != "w" and x > 0:
                fy[p] = fy.get(p, 0.0) + w * float(x) / wv
    return fy, sorted(set(df["prov_id"].to_list()))


def _s2(ctx: BlockContext, out: Out) -> Satellite:
    rows: list[dict[str, Any]] = []
    inputs: set[str] = set()
    ids = sorted(f"ites.t5.{r}.share" for r in ITES_SINGLE_COUNTRY)
    ites = ctx.rows(c.ITES, series_id=ids, vintage=c.LATEST, unit="percent", price_basis=None)
    ites_sh = {sid.split(".")[2]: float(x) / 100.0 for sid, x in zip(ites["series_id"], ites["value"])}
    inputs |= set(ites["prov_id"].to_list())
    for k, eb in BPM6_TO_EBOPS.items():
        for side, flow in (("credit", "exports"), ("debit", "imports")):
            tot, tpid = v(ctx, c.BPM6, f"bpm6.inr.bpm6_1_a_b_{k}.{side}.current")
            inputs.add(tpid)
            if tot == 0:
                continue
            sh, pids = _batis_shares(ctx, flow, eb)
            inputs |= set(pids)
            sh = c.shares(sh, f"S2 {flow} {eb}")
            if eb == "si" and flow == "exports":  # ITES survey override for the single-country regions
                fixed = {iso: ites_sh[r] for r, iso in ITES_SINGLE_COUNTRY.items()}
                rest = c.shares({p: x for p, x in sh.items() if p not in fixed}, "S2 si exports rest")
                sh = {**{p: x * (1.0 - sum(fixed.values())) for p, x in rest.items()}, **fixed}
            for p, s in sorted(sh.items()):
                rows.append(
                    {
                        "series_id": f"s2.{flow}.{eb}.{p}",
                        "flow": flow,
                        "bop_item": f"bpm6_1_a_b_{k}",
                        "ebops": eb.upper(),
                        "partner": p.upper(),
                        "measure": "inr_crore",
                        "value": tot * s,
                        "unit": "INR_crore",
                    }
                )
    # memo rows: the BoP -> NAS services-imports bridge (CIF adjustment, goods for processing)
    gfp, gfp_pid = v(ctx, c.BPM6, "bpm6.inr.bpm6_1_a_b_1.debit.current")
    nas_si, nas_si_pid = v(ctx, c.NAS61, "s6_1.import_of_services_adjusted_for_cost_insurance_and_freight_c.current")
    inputs |= {gfp_pid, nas_si_pid}
    for name, val in (("cif_adjustment", -out.memo["d2"]), ("goods_for_processing", -gfp)):
        rows.append(
            {
                "series_id": f"s2.imports.memo.{name}",
                "flow": "imports",
                "bop_item": "memo",
                "ebops": None,
                "partner": None,
                "measure": name,
                "value": val,
                "unit": "INR_crore",
            }
        )
    pid = ctx.prov(
        ref="S2",
        status="estimated",
        inputs=sorted(inputs),
        method=(
            "Gap map S2: services exports/imports by partner x EBOPS item. Totals = BoP BPM6 1.A.b.1..13 credits "
            f"(exports) and debits (imports), FY 2023-24 ({c.BPM6}); partner shares = OECD-WTO BaTIS balanced "
            f"values ({c.BATIS}), FY share = 0.75 x CY2023 share + 0.25 x CY2024 share within each item (shares "
            "only: balanced levels are ~66% of reported, trade_satellites-3); 1.A.b.13 'others n.i.e.' uses the "
            "total-services shares. Override for telecom/computer/information (SI) exports: the RBI ITES survey "
            f"2023-24 shares ({c.ITES} ites.t5.<region>.share) of the three single-country regions (USA, UK, "
            "Canada) are imposed and the other partners share the rest in BaTIS proportions (the survey's multi-"
            "country regions are not applied: no committed ISO3 -> region concordance). Memo rows (partner "
            "null): minus the SUT CIF adjustment (D2) and minus goods for processing, the bridge from BoP services "
            "imports to NAS 6.1 services imports adjusted for CIF (whole-crore rounding remains)."
        ),
        source_id="oecd_wto_batis",
        notes="Totals from the RBI HBS BoP; shares from BaTIS and the RBI ITES survey.",
    )
    for r in rows:
        r["status"], r["prov_id"] = "estimated", pid
    out.memo["s2_nas_services_imports"] = (nas_si, nas_si_pid)
    return Satellite(
        "S2",
        _frame(rows, SAT_DIMS_S2),
        "Services trade by partner x EBOPS 2010 item (BoP totals, BaTIS FY shares, ITES override), Rs crore",
        decimals=6,
    )


# ---------------------------------------------------------------------------------------------------
# S1 goods by partner and HS chapter
# ---------------------------------------------------------------------------------------------------


def _s1(ctx: BlockContext, out: Out) -> Satellite:
    rate, rate_pid = v(ctx, c.FX, "t133.usd_fy_average", unit="INR_per_USD", price_basis=None)
    imts = ctx.rows(c.IMTS_FY, vintage=c.LATEST, unit="USD_million", price_basis=None)
    ct = ctx.rows(c.COMTRADE_FY, vintage=c.LATEST, unit="USD_million", price_basis=None)
    rows: list[dict[str, Any]] = []
    stats: dict[str, Any] = {}
    for flow, imts_item in (("exports", "exports_fob"), ("imports", "imports_cif")):
        m = imts.filter(pl.col("series_id").str.starts_with(f"imts.{imts_item}."))
        world_row = m.filter(pl.col("series_id") == f"imts.{imts_item}.g001.current")
        if world_row.height != 1:
            raise SamError(f"S1: IMTS {flow} World (g001) not found once")
        world = float(world_row["value"][0])
        ctry = m.filter(pl.col("geography").is_not_null())
        partners = {sid.split(".")[2]: float(x) for sid, x in zip(ctry["series_id"], ctry["value"]) if x > 0}
        unalloc = world - sum(partners.values())
        if unalloc < -0.01:
            raise SamError(f"S1: IMTS {flow} country partners exceed World by {-unalloc:,.2f}")
        if unalloc > 0:
            partners["unallocated"] = unalloc
        # Comtrade chapters: World (w00) and the top-30 partners
        cf = ct.filter(pl.col("series_id").str.starts_with(f"ct.{flow}."))
        chap: dict[tuple[str, str], float] = {}
        for sid, x in zip(cf["series_id"], cf["value"]):
            _, _, hs2, p, _ = sid.split(".")
            if hs2 != "total":
                chap[(COMTRADE_TO_ISO.get(p, p), hs2)] = float(x)
        world_ch = {h: x for (p, h), x in chap.items() if p == "w00"}
        top = sorted({p for (p, _) in chap if p != "w00"})
        missing = [p for p in top if p not in partners]
        if missing:
            raise SamError(f"S1: Comtrade top partners without an IMTS {flow} total: {missing}")
        top_ch: dict[str, float] = {}
        for (p, h), x in chap.items():
            if p != "w00":
                top_ch[h] = top_ch.get(h, 0.0) + x
        rest_ch = {h: max(0.0, w - top_ch.get(h, 0.0)) for h, w in world_ch.items()}
        clipped = sorted(h for h, w in world_ch.items() if w - top_ch.get(h, 0.0) < 0)
        rest_p = {p: x for p, x in partners.items() if p not in top}
        rest_tot = sum(rest_p.values())
        seed: dict[tuple[str, str], float] = {k: x for k, x in chap.items() if k[0] != "w00" and x > 0}
        for p, x in rest_p.items():
            for h, rc in rest_ch.items():
                if rc > 0:
                    seed[(p, h)] = rc * x / rest_tot
        wct = sum(world_ch.values())
        col_t = {h: x * world / wct for h, x in world_ch.items() if x > 0}
        # a top partner whose IMTS total has no Comtrade chapter at all cannot be matched: error (not silent)
        row_t = dict(partners)
        fit = c.ras(seed, row_t, col_t, tol=1e-6 * world)
        stats[flow] = {
            "world": world,
            "comtrade_world": wct,
            "unallocated": unalloc,
            "clipped_chapters": clipped,
            "top": len(top),
        }
        for (p, h), x in fit.items():
            ptype = "unallocated" if p == "unallocated" else ("top30_comtrade" if p in top else "other_estimated")
            for measure, val, unit in (("usd_mn", x, "USD_million"), ("inr_crore", x * rate / 10.0, "INR_crore")):
                rows.append(
                    {
                        "series_id": f"s1.{flow}.{p}.{h}.{measure}",
                        "flow": flow,
                        "partner": p.upper() if p != "unallocated" else p,
                        "partner_type": ptype,
                        "hs2": h,
                        "measure": measure,
                        "value": val,
                        "unit": unit,
                    }
                )
        if flow == "imports":  # India re-imports (Comtrade partner IND): memo only, not a partner share
            ind = cf.filter(pl.col("series_id") == "ct.imports.total.ind.current")
            if ind.height == 1:
                x = float(ind["value"][0])
                for measure, val, unit in (("usd_mn", x, "USD_million"), ("inr_crore", x * rate / 10.0, "INR_crore")):
                    rows.append(
                        {
                            "series_id": f"s1.imports.memo_reimports.total.{measure}",
                            "flow": "imports",
                            "partner": "IND",
                            "partner_type": "memo_reimports",
                            "hs2": "total",
                            "measure": measure,
                            "value": val,
                            "unit": unit,
                        }
                    )
    for flow, st in stats.items():
        ctx.log(
            f"S1 {flow}: IMTS world {st['world']:,.2f} US$ mn, Comtrade world {st['comtrade_world']:,.2f}, "
            f"unallocated {st['unallocated']:,.2f}, top partners {st['top']}, chapters where the top-30 exceed "
            f"World (clipped to 0 for the rest): {st['clipped_chapters']}"
        )
    out.memo["s1_stats"] = stats
    inputs = sorted(set(imts["prov_id"].to_list()) | set(ct["prov_id"].to_list()) | {rate_pid})
    pid = ctx.prov(
        ref="S1",
        status="estimated",
        inputs=inputs,
        method=(
            "Gap map S1: goods exports (FOB) / imports (CIF) by partner x HS chapter, FY 2023-24, customs basis (not "
            f"scaled to SAM P5/P6). Partner totals: IMF IMTS FY ({c.IMTS_FY}, country rows; World g001 less the "
            "countries is an explicit 'unallocated' partner: not-specified areas and partner-months missing, "
            f"trade_satellites-7). Chapter split: UN Comtrade FY ({c.COMTRADE_FY}) for the top-30 partners (Comtrade "
            "'S19' mapped to TWN, trade_satellites-10); every other partner gets World chapters less the top-30 "
            "chapters (clipped at 0) in proportion to its IMTS total (trade_satellites-2). The two sources are "
            "reconciled by a two-margin RAS: partner margins = IMTS, chapter margins = Comtrade World chapters "
            "scaled to the IMTS World total. Rupees: US$ x the FY 2023-24 average rate "
            f"({c.FX} t133.usd_fy_average; derived; monthly conversion not applied). Re-imports (Comtrade partner "
            "IND) are a memo row. There is no HS -> SAM commodity concordance, so S1 stays by HS chapter."
        ),
        source_id="imf_sdmx",
        notes="Partner totals from IMF IMTS; chapters from UN Comtrade; FX from RBI HBS.",
        conversion="US$ million x INR per US$ (FY average) / 10 = Rs crore",
    )
    for r in rows:
        r["status"], r["prov_id"] = "estimated", pid
    return Satellite(
        "S1",
        _frame(rows, SAT_DIMS_S1),
        "Goods trade by partner x HS chapter (IMTS partner totals, Comtrade chapters, RAS), US$ mn and Rs crore",
        decimals=6,
    )
