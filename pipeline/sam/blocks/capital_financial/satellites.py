"""Satellites of capital_financial: S4 (who funds whom), S5 (household wealth), the K9 decomposition and memo
tables for closure, timeseries and the verifier (plan s.2.11, s.4.2)."""

from __future__ import annotations

import polars as pl

from pipeline.sam.blocks.capital_financial import fsf as F
from pipeline.sam.blocks.capital_financial import params as P
from pipeline.sam.framework import BlockContext, Satellite


def _frame(rows: list[dict], dims: list[str]) -> pl.DataFrame:
    schema = {
        "series_id": pl.String(),
        **{d: pl.String() for d in dims},
        "value": pl.Float64(),
        "unit": pl.String(),
        "status": pl.String(),
        "prov_id": pl.String(),
    }
    return pl.DataFrame(rows, schema=schema, orient="row").sort("series_id")


def _slug(s: str) -> str:
    return s.lower().replace(":", ".").replace("|", ".")


def all_satellites(
    ctx: BlockContext, val, rep, recon, hh_posts, row_posts, k9, pid_k9, gf, fsf_pids, deps, cpid, entries
) -> dict[str, Satellite]:
    sats: dict[str, Satellite] = {}
    sats["k9_decomposition"] = _k9(k9, pid_k9)
    sats["s4_fwtw_sam"] = _fwtw_sam(ctx, recon, hh_posts, row_posts, fsf_pids, deps)
    sats["s4_fsf_dual_reports"] = _dual(ctx, rep, fsf_pids)
    sats["s4_fwtw_fsf"] = _fwtw_fsf(ctx)
    sats["s4_hdfc_merger_memo"] = _merger(ctx, val, hh_posts, fsf_pids)
    sats["capital_formation_by_account"] = _capform(ctx, entries, cpid)
    sats["gg_gfcf_key"] = _gg_key(ctx, gf)
    sats["fsf_instrument_closure"] = _closure(ctx)
    s5 = _s5(ctx, val, deps)
    if s5 is not None:
        sats["s5_hh_wealth"] = s5
    return sats


def _k9(k9: dict[str, dict[str, float]], pid: str) -> Satellite:
    rows = []
    for acct, d in k9.items():
        for item, v in sorted(d.items()):
            if item.startswith("check"):
                continue
            rows.append(
                {
                    "series_id": f"k9.{acct.lower()}.{_slug(item)}",
                    "account": acct,
                    "item": item,
                    "value": v,
                    "unit": "INR_crore",
                    "status": "estimated",
                    "prov_id": pid,
                }
            )
    return Satellite(
        "K9",
        _frame(rows, ["account", "item"]),
        "K9 by domestic capital account: real (non-financial) net resources, SAM net financial "
        "transactions by layer (sam_hh, sam_row, sam_dom:<instrument>), FSF published net financial "
        "transactions (fsf_total), K9 and its exact decomposition (term:*); pair:* regroup the same terms "
        "(RoW as one term; household and domestic layers combined per instrument, hh_dom:<instrument>) and "
        "pos/neg, the K9 entries, are the sums of the positive and negative pair:* terms",
        decimals=6,
    )


def k9_sensitivity(sens: dict[str, dict[str, float]], pid: str) -> Satellite:
    """Plan T24: K9 by account under each variant, and its change from the base."""
    rows = []
    for variant, by_acct in sens.items():
        for acct in P.K_DOMESTIC:
            v = by_acct[acct]
            rows.append(
                {
                    "series_id": f"k9_sens.{variant}.{acct.lower()}",
                    "variant": variant,
                    "account": acct,
                    "item": "k9",
                    "value": v,
                    "unit": "INR_crore",
                    "status": "estimated",
                    "prov_id": pid,
                }
            )
            if variant != "base":
                rows.append(
                    {
                        "series_id": f"k9_sens.{variant}.{acct.lower()}.change",
                        "variant": variant,
                        "account": acct,
                        "item": "change_from_base",
                        "value": v - sens["base"][acct],
                        "unit": "INR_crore",
                        "status": "estimated",
                        "prov_id": pid,
                    }
                )
    return Satellite(
        "K9",
        _frame(rows, ["variant", "account", "item"]),
        "Plan T24 sensitivity (report only): K9 by domestic capital account as built (base) and with one "
        "rule changed: equity issuer control, no insurers' revaluation strip, D3 remainder all to K_NFPU",
        decimals=6,
    )


def _fwtw_sam(ctx, recon, hh_posts, row_posts, fsf_pids, deps) -> Satellite:
    pid = ctx.prov(
        ref="S4",
        status="estimated",
        inputs=sorted({*fsf_pids, *deps.row_pids}),
        source_id=P.SRC_FSF,
        method="Satellite S4 s4_fwtw_sam: the SAM's from-whom-to-whom flows, holder x issuer x instrument: "
        "the reconciled FSF domestic pairs (K7/K8/K8d), the household lines by counterparty (K7a/K8a "
        "via K7b hh_cp) and the RoW lines by domestic counterpart (K8b via K7b row_cp). Row and "
        "column sums equal the dom + hh_cp + row_cp entries.",
    )
    agg: dict[tuple[str, str, str], float] = {}

    def add(inst: str, holder: str, issuer: str, v: float) -> None:
        agg[(inst, holder, issuer)] = agg.get((inst, holder, issuer), 0.0) + v

    for p in recon.pairs:
        add(p.instrument, p.holder, p.issuer, p.value)
    for p in hh_posts:
        if p.side == "liability":
            add(p.instrument, "K_HH", p.account, p.value)
        else:
            add(p.instrument, p.account, "K_HH", p.value)
    for p in row_posts:
        if p.side == "liability":
            add(p.instrument, "K_ROW", p.account, p.value)
        else:
            add(p.instrument, p.account, "K_ROW", p.value)
    rows = [
        {
            "series_id": f"fwtw.{i.lower()}.{h.lower()}.{c.lower()}",
            "instrument": i,
            "holder": h,
            "issuer": c,
            "value": v,
            "unit": "INR_crore",
            "status": "estimated",
            "prov_id": pid,
        }
        for (i, h, c), v in sorted(agg.items())
        if v != 0.0
    ]
    return Satellite(
        "S4",
        _frame(rows, ["instrument", "holder", "issuer"]),
        "Who funds whom in the SAM (holder x issuer x instrument), Rs crore, 2023-24 flows",
    )


def _dual(ctx, rep, fsf_pids) -> Satellite:
    pid_o = ctx.prov(
        ref="S4",
        status="official",
        inputs=fsf_pids,
        method="Satellite S4 s4_fsf_dual_reports: for every (SAM instrument, holder, issuer) at FSF "
        "sector-code level, the holder's and the issuer's FSF 2023-24 transaction reports as "
        "published (sums of leaf-statement cells).",
    )
    pid_d = ctx.prov(
        ref="S4",
        status="derived",
        inputs=fsf_pids,
        method="Satellite S4 s4_fsf_dual_reports: the control side (params.CONTROL), the value it gives "
        "(chosen) and holder - issuer report (difference): the audit trail of the reconciliation.",
    )
    rows = []
    for r in F.dual_reports(rep).iter_rows(named=True):
        inst, h, c = r["instrument"], r["holder"], r["issuer"]
        ctrl = P.CONTROL.get(inst, "none")
        chosen = r["holder_report"] if ctrl == "holder" else r["issuer_report"] if ctrl == "issuer" else 0.0
        base = {"instrument": inst, "holder": h, "issuer": c, "control": ctrl, "unit": "INR_crore"}
        for m, v, st, pid in (
            ("holder_report", r["holder_report"], "official", pid_o),
            ("issuer_report", r["issuer_report"], "official", pid_o),
            ("chosen", chosen, "derived", pid_d),
            ("difference", r["holder_report"] - r["issuer_report"], "derived", pid_d),
        ):
            rows.append(
                {
                    **base,
                    "series_id": f"dual.{inst.lower()}.{h}.{c}.{m}",
                    "measure": m,
                    "value": v,
                    "status": st,
                    "prov_id": pid,
                }
            )
    return Satellite(
        "S4",
        _frame(rows, ["instrument", "holder", "issuer", "control", "measure"]),
        "FSF 2023-24 holder vs issuer reports by instrument and sector pair, the control side and the "
        "value chosen (plan s.2.6)",
    )


def _fwtw_fsf(ctx) -> Satellite:
    flows = ctx.rows(P.FSF6, vintage=P.LATEST, dim_other="measure=transaction")
    stocks = ctx.rows(P.FSF6, period="2024-03-31", vintage=P.LATEST, dim_other="measure=outstanding")
    df = pl.concat([flows, stocks], how="vertical")
    pid = ctx.prov(
        ref="S4",
        status="official",
        inputs=sorted(set(df["prov_id"].to_list())),
        method="Satellite S4 s4_fwtw_fsf: RBI FSF Statements 6.13.b (2023-24 transactions) and 6.13.a "
        "(outstanding at 2024-03-31) as published: sector x counterparty, uses and sources.",
    )
    rows = [
        {
            "series_id": f"{r['series_id']}.{r['period']}",
            "institution": r["institution"],
            "counterparty": r["counterparty"],
            "side": r["side"],
            "measure": r["dim_other"].split("=")[1],
            "period": r["period"],
            "value": float(r["value"]),
            "unit": "INR_crore",
            "status": "official",
            "prov_id": pid,
        }
        for r in df.iter_rows(named=True)
    ]
    return Satellite(
        "S4",
        _frame(rows, ["institution", "counterparty", "side", "measure", "period"]),
        "RBI FSF from-whom-to-whom (St 6.13.a stocks at 2024-03-31, 6.13.b 2023-24 flows), as published",
    )


def _merger(ctx, val, hh_posts, fsf_pids) -> Satellite:
    rows = []

    def add(sid: str, item: str, v: float, st: str, pid: str) -> None:
        rows.append({"series_id": sid, "item": item, "value": v, "unit": "INR_crore", "status": st, "prov_id": pid})

    nas = [
        (k, *val(P.NAS53, f"s5_3.{s}.current"))
        for k, s in (
            ("banks", "bank_advances"),
            ("coop_banks", "loans_and_advances_by_co_operative_banks_and_societies"),
            ("nbfc_hfc", "loans_by_financial_corporations_and_non_banking_companies"),
        )
    ]
    t52 = [
        (k, *val(P.HH52, f"t52a.{s}.current.fy", vintage=P.T52_VINTAGE))
        for k, s in (("scb", "fl_fc_banks_scb"), ("nbfc", "fl_fc_ofi_nbfc"), ("hfc", "fl_fc_ofi_hfc"))
    ]
    rtp = [
        (k, *val(P.RTP, f"rtp.scb_bs.{s}.scb.current", period="2024-03-31", vintage=P.RTP_VINTAGE))
        for k, s in (
            ("loans_with_merger", "loans_advances"),
            ("loans_excl_merger", "loans_advances_excl_merger"),
            ("deposits_with_merger", "deposits"),
            ("deposits_excl_merger", "deposits_excl_merger"),
        )
    ]
    pid_o = ctx.prov(
        ref="S4",
        status="official",
        inputs=sorted({p for _, _, p in nas + t52 + rtp}),
        source_id=P.SRC_RTP,
        method="Satellite S4 s4_hdfc_merger_memo: household borrowing by lender as published (NAS 2026 St "
        "5.3; RBI T52(a) 2023-24) and SCB loans and deposits at 2024-03-31 with and without the "
        "HDFC merger (RTP 2023-24, vintage 2024-12-26).",
    )
    for k, v, _ in nas:
        add(f"nas53.loans.{k}", f"NAS 5.3 household loans from {k}", v, "official", pid_o)
    for k, v, _ in t52:
        add(f"t52a.loans.{k}", f"RBI T52(a) household loans from {k}", v, "official", pid_o)
    for k, v, _ in rtp:
        add(f"rtp.scb.{k}", f"SCB {k.replace('_', ' ')} at 2024-03-31", v, "official", pid_o)
    r = {k: v for k, v, _ in rtp}
    pid_d = ctx.prov(
        ref="S4",
        status="derived",
        inputs=sorted({p for _, _, p in rtp}),
        method="Satellite S4 s4_hdfc_merger_memo: the merger's effect on SCB loans and deposits = with "
        "minus without merger (RTP 2023-24).",
    )
    add(
        "rtp.scb.merger_effect.loans",
        "HDFC merger effect on SCB loans",
        r["loans_with_merger"] - r["loans_excl_merger"],
        "derived",
        pid_d,
    )
    add(
        "rtp.scb.merger_effect.deposits",
        "HDFC merger effect on SCB deposits",
        r["deposits_with_merger"] - r["deposits_excl_merger"],
        "derived",
        pid_d,
    )
    pid_e = ctx.prov(
        ref="S4",
        status="estimated",
        inputs=fsf_pids,
        method="Satellite S4 s4_hdfc_merger_memo: household loans by lender in the SAM boundary (K7b "
        "hh_cp postings: HDFC Ltd, a deposit-taking HFC, sits inside K_BANK for the whole year).",
    )
    lend: dict[str, float] = {}
    for p in hh_posts:
        if p.side == "asset" and p.instrument == "I_LOAN":
            lend[p.account] = lend.get(p.account, 0.0) + p.value
    for a, v in sorted(lend.items()):
        add(f"sam.loans.{a.lower()}", f"SAM household loans from {a}", v, "estimated", pid_e)
    return Satellite(
        "S4",
        _frame(rows, ["item"]),
        "HDFC merger memo: household loans by lender (published and SAM "
        "boundary) and the merger's effect on SCB loans and deposits",
    )


def _capform(ctx, entries, cpid) -> Satellite:
    pid = ctx.prov(
        ref="I1a",
        status="estimated",
        inputs=[cpid],
        method="Satellite capital_formation_by_account: sums of this block's entries by capital account: "
        "GFCF (I1a), change in inventories (I3a), valuables (I2 + I2a), GCF, and the D3 allocation "
        "(for closure diagnostics and the time series).",
    )
    acc: dict[tuple[str, str], float] = {}
    for e in entries:
        item = {"I1a": "gfcf", "I3a": "cis", "I2": "valuables", "I2a": "valuables", "D3": "d3"}.get(e["ref"])
        if item is None:
            continue
        k = e["row"] if e["ref"] == "D3" else e["col"]
        acc[(k, item)] = acc.get((k, item), 0.0) + e["value"]
    for k in sorted({k for k, _ in acc}):
        acc[(k, "gcf")] = acc.get((k, "gfcf"), 0.0) + acc.get((k, "cis"), 0.0)
    rows = [
        {
            "series_id": f"capform.{k.lower()}.{i}",
            "account": k,
            "item": i,
            "value": v,
            "unit": "INR_crore",
            "status": "estimated",
            "prov_id": pid,
        }
        for (k, i), v in sorted(acc.items())
    ]
    return Satellite("I1a", _frame(rows, ["account", "item"]), "GFCF, CIS, valuables, GCF and D3 by capital account")


def _gg_key(ctx, gf) -> Satellite:
    pid = ctx.prov(
        ref="I1a",
        status="derived",
        inputs=gf["key_pids"],
        source_id=P.SRC_FA,
        method="Satellite gg_gfcf_key: the Centre/State GG GFCF key of I1a: Union capital outlay (Finance "
        "Accounts, capital heads section) less departmental commercial and investment heads "
        "(params.UNION_NON_GG_HEADS) plus IGAS-2 capital grants to autonomous bodies and to statutory "
        "bodies and development authorities (inside G_CEN, as government's K6 treats them), vs RBI State "
        "Finances total capital outlay plus IGAS-2 capital grants to urban local bodies; and RBI "
        "GFCF = change in net fixed assets + depreciation (RBI Annual Report 2023-24).",
    )
    rows = [
        {
            "series_id": f"gg_key.{k}",
            "item": k,
            "value": v,
            "unit": "ratio" if k == "centre_share" else "INR_crore",
            "status": "derived",
            "prov_id": pid,
        }
        for k, v in sorted(gf["key"].items())
    ]
    return Satellite("I1a", _frame(rows, ["item"]), "Centre/State GG GFCF key and RBI GFCF (inputs of I1a)", decimals=9)


def _closure(ctx) -> Satellite:
    subs = [*P.SUB_ACCOUNT, "row"]
    df = ctx.rows(
        P.FSF,
        vintage=P.LATEST,
        dim_other="measure=transaction",
        counterparty="all",
        institution=subs,
        instrument=["f1", "f21", "f22_f29", "f3", "f4", "f51", "f52", "f6", "f81", "f89", "other", "nec"],
    )
    pid = ctx.prov(
        ref="K7",
        status="official",
        inputs=sorted(set(df["prov_id"].to_list())),
        method="Satellite fsf_instrument_closure: FSF 2023-24 transactions by instrument summed over the "
        "leaf statements (params.SUB_ACCOUNT) and the RoW statement, assets and liabilities: the "
        "instrument markets do not clear (plan s.2.6).",
    )
    agg: dict[tuple[str, str], float] = {}
    for r in df.iter_rows(named=True):
        agg[(r["instrument"], r["side"])] = agg.get((r["instrument"], r["side"]), 0.0) + float(r["value"])
    rows = [
        {
            "series_id": f"fsf_closure.{i}.{s}",
            "fsf_instrument": i,
            "side": s,
            "value": v,
            "unit": "INR_crore",
            "status": "official",
            "prov_id": pid,
        }
        for (i, s), v in sorted(agg.items())
    ]
    return Satellite(
        "K7",
        _frame(rows, ["fsf_instrument", "side"]),
        "FSF 2023-24 sum of assets and of liabilities by instrument (leaf statements + RoW)",
    )


def _s5(ctx, val, deps) -> Satellite | None:
    keys = deps.hh_keys
    if keys is None or keys.height == 0:
        ctx.warn("households hh_keys missing: S5 not built")
        return None
    fa, fap = val(P.HH52, "t52b.fa.current", period="2024-03-31", vintage=P.T52_VINTAGE)
    fl, flp = val(P.HH52, "t52b.fl.current", period="2024-03-31", vintage=P.T52_VINTAGE)
    levels = _hh_levels(keys)
    pid = ctx.prov(
        ref="S5",
        status="estimated",
        inputs=sorted({fap, flp, *deps.hh_pids}),
        source_id=P.SRC_T52,
        method="Satellite S5 s5_hh_wealth (ABM calibration): financial assets and institutional debt by "
        "household group = RBI T52(b) stocks at 2024-03-31 x households' AIDIS keys "
        "(aidis_fin_assets, aidis_inst_loans; AIDIS 2019 mapped to the SAM groups by the households "
        "block). Physical assets and non-institutional debt are AIDIS 2018-06-30 levels, not "
        "rebased (no official 2024 control). D1-2 (no unit data) caps quality; low.",
    )
    rows = []
    for key, measure, total in (
        ("aidis_fin_assets", "financial_assets", fa),
        ("aidis_inst_loans", "institutional_debt", fl),
    ):
        lv = levels.get(key)
        if not lv:
            ctx.warn(f"hh_keys has no {key}: S5 {measure} not built")
            continue
        s = sum(lv.values())
        for g, v in sorted(lv.items()):
            rows.append(
                {
                    "series_id": f"s5.{measure}.{g.lower()}",
                    "household_group": g,
                    "measure": measure,
                    "basis": "2024-03-31",
                    "value": total * v / s,
                    "unit": "INR_crore",
                    "status": "estimated",
                    "prov_id": pid,
                }
            )
    for key, measure in (
        ("aidis_fixed_assets", "physical_assets_2018"),
        ("aidis_noninst_loans", "noninstitutional_debt_2018"),
    ):
        lv = levels.get(key)
        if not lv:
            ctx.warn(f"hh_keys has no {key}: S5 {measure} not built")
            continue
        for g, v in sorted(lv.items()):
            rows.append(
                {
                    "series_id": f"s5.{measure}.{g.lower()}",
                    "household_group": g,
                    "measure": measure,
                    "basis": "2018-06-30",
                    "value": v,
                    "unit": "INR_crore",
                    "status": "estimated",
                    "prov_id": pid,
                }
            )
    if not rows:
        return None
    return Satellite(
        "S5",
        _frame(rows, ["household_group", "measure", "basis"]),
        "Household financial assets and institutional debt by group (T52(b) 2024-03-31 x AIDIS keys); "
        "physical assets and non-institutional debt at AIDIS 2018 levels, not rebased",
    )


def _hh_levels(keys: pl.DataFrame) -> dict[str, dict[str, float]]:
    """Levels by key and household group from households' hh_keys (series_id `<key>.level.<group>`)."""
    out: dict[str, dict[str, float]] = {}
    for r in keys.iter_rows(named=True):
        parts = r["series_id"].split(".")
        key = r.get("key") or parts[0]
        measure = r.get("measure") or (parts[1] if len(parts) > 2 else "")
        group = r.get("household_group") or parts[-1].upper()
        if measure != "level" or not group.upper().startswith("H_"):
            continue
        out.setdefault(key, {})[group.upper()] = float(r["value"])
    return out
