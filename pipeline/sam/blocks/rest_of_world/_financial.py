"""K_ROW, the rest of the world's capital and financial account: K8b (by instrument, with BoP functional
tags) and K8c (the reserve build-up), plus the `row_financial_counterparts` interface satellite.

Rows receive, columns pay. `I_x <- K_ROW` is RoW acquiring an Indian liability of instrument x (India's
net incurrence of foreign liabilities); `K_ROW <- I_x` is RoW incurring a liability to India (India's net
acquisition of foreign assets). Values are net flows as published (a negative value is a net reduction).
Method: docs/phase2/plans/rest_of_world.md s.2.6-2.7 and s.8.
"""

from __future__ import annotations

from typing import Any

from pipeline.sam.blocks.rest_of_world import _common as c
from pipeline.sam.blocks.rest_of_world._common import Out
from pipeline.sam.blocks.rest_of_world._current import ROUND_TOL, avg_stock, v
from pipeline.sam.framework import BlockContext, SamError, constraint, entry

OLD = "bop_old.inr.{}.net.current"
LINE_TOL = 2.0  # Rs crore: a sum of 2-3 BoP lines, each rounded to whole crore, vs the published total
RECON_MAX = 150.0  # Rs crore: a NAS-vs-BoP reconciliation line larger than this is an error (plan s.7 item 10)

# (component, old-format BoP path or None, sign, instrument, bop_function, counterpart rule)
# counterpart rules: an account code, or a named key resolved in build_financial.
LIABILITY_LINES: list[tuple[str, str | None, int, str, str, str]] = [
    ("fdi_equity", "ka.fdi.in_india.equity", 1, "I_EQTY", "FDI_equity", "fla_equity"),
    ("fdi_reinvested_earnings", None, 1, "I_EQTY", "FDI_reinvested_earnings", "r14a"),
    ("fdi_debt", "ka.fdi.in_india.other_capital", 1, "I_LOAN", "FDI_debt", "fla_debt"),
    ("fpi_equity", "ka.portfolio.in_india.fiis.equity", 1, "I_EQTY", "FPI_equity", "fla_equity"),
    ("ecb", "ka.loans.ecb.to_india", 1, "I_LOAN", "ECB", "ecb"),
    ("external_assistance", "ka.loans.external_assistance.to_india", 1, "I_LOAN", "other", "K_GCEN"),
    ("short_term_trade_credit", "ka.loans.short_term", 1, "I_OTHR", "short_term_credit", "K_NFPR"),
    ("nri_deposits", "ka.banking_capital.commercial_banks.nri_deposits", 1, "I_DEPO", "NRI_deposits", "K_BANK"),
    ("rbi_deposits", "ka.banking_capital.others", 1, "I_DEPO", "other", "K_RBI"),
    ("rupee_debt_service", "ka.rupee_debt_service", 1, "I_OTHR", "other", "K_GCEN"),
]
ASSET_LINES: list[tuple[str, str | None, int, str, str, str]] = [
    ("odi_equity", "ka.fdi.abroad.equity", -1, "I_EQTY", "ODI", "fsf_f51"),
    ("odi_reinvested_earnings", "ka.fdi.abroad.reinvested_earnings", -1, "I_EQTY", "ODI", "fsf_f51"),
    ("odi_debt", "ka.fdi.abroad.other_capital", -1, "I_LOAN", "ODI", "K_NFPR"),
    ("portfolio_abroad", "ka.portfolio.abroad", -1, "I_EQTY", "other", "K_NFPR"),
    ("loans_by_india", "ka.loans.ecb.by_india", -1, "I_LOAN", "other", "K_NFPR"),
    ("external_assistance_by_india", "ka.loans.external_assistance.by_india", -1, "I_LOAN", "other", "K_GCEN"),
    ("banks_foreign_assets", "ka.banking_capital.commercial_banks.assets", -1, "I_DEPO", "other", "K_BANK"),
    ("other_capital", "ka.other_capital", -1, "I_OTHR", "other", "K_NFPR"),
    ("reserve_assets", "monetary_movements.reserves", -1, "I_RESV", "reserves", "K_RBI"),
]
ECB_FC_INDUSTRIES = (  # external_sector-11: two slugs exist for the same NIC 64 label
    "financial_service_activities_except_insurance_and_pension_funding",
    "financial_service_activities_except_insurance_and_pension",
)


def build_financial(ctx: BlockContext, out: Out) -> None:
    inst = ctx.accounts.in_group("INST")
    sat = out.rows("row_financial_counterparts")
    liab_tot, liab_pid = v(ctx, c.NAS61, "s6_1.net_incurrence_of_foreign_liabilities.current")
    asset_tot, asset_pid = v(ctx, c.NAS61, "s6_1.net_acquisition_of_foreign_financial_assets.current")

    # --- counterpart keys --------------------------------------------------------------------------------
    fc_share, fla_eq_pids = out.memo["fc_share"]
    bank_ratio = out.memo["fc_bank_ratio"]
    fin_debt, p1 = v(
        ctx, c.FLA, "fla.t8.g.financial_and_insurance_activities.debt", period="2024-03-31", vintage=c.V_FLA
    )
    tot_debt, p2 = v(ctx, c.FLA, "fla.t8.total.debt", period="2024-03-31", vintage=c.V_FLA)
    fc_debt_share = fin_debt / tot_debt

    def nfc_fc(fc: float) -> dict[str, float]:
        return {"K_NFPR": 1.0 - fc, "K_BANK": fc * bank_ratio, "K_NBFC": fc * (1.0 - bank_ratio)}

    f51 = {}
    f51_pids: list[str] = []
    for cp in ("nfc_pvt", "nfc_pub", "fc_odc", "fc_ofc"):
        a, p, _ = avg_stock(ctx, c.FSF, f"fsf.row.liabilities.outstanding.f51.{cp}.current", vintage=c.V_FSF)
        if a:
            f51[c.INST_TO_K[c.FSF_TO_SAM[cp]]] = a
        f51_pids += p
    ecb = ctx.rows(
        c.ECB, vintage=c.LATEST, period=None, unit="USD_million", price_basis=None, item_code="ecb_registration"
    )
    ecb_tot = float(ecb["value"].sum())
    ecb_fc = float(ecb.filter(ecb["industry"].is_in(list(ECB_FC_INDUSTRIES)))["value"].sum())
    ecb_pids = sorted(set(ecb["prov_id"].to_list()))
    r14a = out.memo["r14a"]
    keys: dict[str, tuple[dict[str, float], list[str], str]] = {
        "fla_equity": (
            nfc_fc(fc_share),
            fla_eq_pids,
            "NFC/FC by the FLA 2023-24 t8 market-value equity key (as R14a), FC split E_BANK : E_NBFC as in R14",
        ),
        "fla_debt": (
            nfc_fc(fc_debt_share),
            [p1, p2],
            "NFC/FC by the FLA 2023-24 t8 debt key (fla.t8.*.debt), FC split E_BANK : E_NBFC as in R14",
        ),
        "r14a": (
            {c.INST_TO_K[k]: x / sum(r14a.values()) for k, x in r14a.items()},
            [],
            "the R14a payer split exactly (so income and flow match by payer)",
        ),
        "fsf_f51": (
            {k: x / sum(f51.values()) for k, x in f51.items()},
            f51_pids,
            "FSF RoW-liability F51 equity stocks by resident counterparty (as R13 DI income)",
        ),
        "ecb": (
            {"K_NFPR": 1.0 - ecb_fc / ecb_tot, "K_NBFC": ecb_fc / ecb_tot},
            ecb_pids,
            "ECB registrations 2023-24 by borrower industry (external_sector_ecb_monthly_2324): NIC 64 financial "
            "service activities -> K_NBFC, the rest -> K_NFPR (public NFC/FI borrowers not separated)",
        ),
    }

    # --- the BoP lines --------------------------------------------------------------------------------
    lines: list[dict[str, Any]] = []
    for direction, table in (("row_acquires", LIABILITY_LINES), ("row_incurs", ASSET_LINES)):
        for comp, path, sign, instr, bop, rule in table:
            if path is None:  # FDI reinvested earnings: the NAS value, so the flow equals R14a exactly
                val, pid_in = out.memo["re"]
                src = "NAS 2026 St 1.9 reinvested earnings (= Sum R14a; BoP 3.1.A.1.2 rounds it to whole crore)"
                status = "official"
            else:
                raw, pid_in = v(ctx, c.BOP_OLD, OLD.format(path))
                val = sign * raw
                src = f"BoP (old format) {OLD.format(path)}" + (
                    " with the sign reversed (asset acquisition)" if sign < 0 else ""
                )
                status = "official"
            lines.append(
                {
                    "direction": direction,
                    "comp": comp,
                    "val": val,
                    "pid_in": pid_in,
                    "instr": instr,
                    "bop": bop,
                    "rule": rule,
                    "src": src,
                    "status": status,
                }
            )
    # the two derived lines on the liability side: bank liabilities other than NRI deposits
    bl, bl_pid = v(ctx, c.BOP_OLD, OLD.format("ka.banking_capital.commercial_banks.liabilities"))
    nri_line = next(x for x in lines if x["comp"] == "nri_deposits")
    lines.append(
        {
            "direction": "row_acquires",
            "comp": "bank_other_liabilities",
            "val": bl - nri_line["val"],
            "pid_in": bl_pid,
            "pid_extra": [nri_line["pid_in"]],
            "instr": "I_DEPO",
            "bop": "other",
            "rule": "K_BANK",
            "src": "BoP commercial banks' liabilities less NRI deposits",
            "status": "derived",
        }
    )
    eo, eo_pid = v(ctx, c.NAS61, "s6_1.other_liabilities_to_non_residents.current")
    lines.append(
        {
            "direction": "row_acquires",
            "comp": "errors_omissions",
            "val": eo,
            "pid_in": eo_pid,
            "instr": "I_OTHR",
            "bop": "other",
            "rule": "unallocated_k9",
            "src": "NAS 2026 St 6.1 other liabilities to non-residents (= BoP errors and omissions)",
            "status": "official",
        }
    )

    # --- FPI debt: I_GSEC (change in FPI holdings of government paper, T107) and I_CBND (the rest) ---------
    fpi_debt, fpi_pid = v(ctx, c.BOP_OLD, OLD.format("ka.portfolio.in_india.fiis.debt"))
    held: dict[str, float] = {}
    t107_pids: list[str] = []
    for inst_ in ("gsec_central", "tbills", "sgs"):
        sh, p_sh, sh_v = avg_stock(
            ctx, c.T107, f"t107.{inst_}.share.fpi", vintage=c.LATEST, unit="percent", price_basis=None
        )
        _, p_os, os_v = avg_stock(ctx, c.T107, f"t107.{inst_}.outstanding.current", vintage=c.LATEST)
        held[inst_] = sh_v[1] / 100.0 * os_v[1] - sh_v[0] / 100.0 * os_v[0]
        t107_pids += p_sh + p_os
    gsec = sum(held.values())
    corp = fpi_debt - gsec
    if gsec <= 0 or corp <= 0:
        raise SamError(f"K8b FPI debt split: G-sec part {gsec:,.2f}, corporate part {corp:,.2f} (both must be > 0)")
    pid_split = ctx.prov(
        ref="K8b",
        status="estimated",
        inputs=[fpi_pid, *t107_pids],
        method=(
            "Gap map K8b, FPI debt split (the NSDL route is barred by its terms, finsector_markets-1, and the FSF "
            "books all FPI in F51 nfc_pvt): BoP old-format FII debt net inflow split into government paper (I_GSEC) "
            "= change in FPI holdings of central dated securities, T-bills and SDLs, each = HBS T107 FPI share x "
            f"outstanding at 2024-03-31 minus the same at 2023-03-31 ({c.T107}, latest vintage; face value, not "
            "transaction value), and corporate debt (I_CBND) = the remainder. Two free entries, medium confidence, "
            "bound by constraint row.fpi_debt."
        ),
        source_id="rbi_hbs_external",
        notes="BoP total (RBI HBS external); split key from RBI HBS T107.",
    )
    k_gsec = {"K_GCEN": held["gsec_central"] + held["tbills"], "K_GSTA": held["sgs"]}

    # --- K8b provenance, entries and counterpart rows -------------------------------------------------------
    by_status: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for ln in lines:
        by_status.setdefault((ln["status"], ln["direction"]), []).append(ln)
    pids: dict[tuple[str, str], str] = {}
    for (status, direction), lns in sorted(by_status.items()):
        ins = sorted({x for ln in lns for x in [ln["pid_in"], *ln.get("pid_extra", [])] if x})
        side = (
            "net incurrence of liabilities (I_x <- K_ROW)"
            if direction == "row_acquires"
            else "net acquisition of foreign assets (K_ROW <- I_x)"
        )
        what = "; ".join(f"{ln['comp']} = {ln['src']}" for ln in lns)
        pids[(status, direction)] = ctx.prov(
            ref="K8b",
            status=status,
            inputs=ins,
            method=(
                f"Gap map K8b, India's {side}, one entry per BoP functional line, value as published (net flow), "
                f"instrument and BoP functional tag as in plan s.2.6 (trade credit -> I_OTHR, plan s.5 item 15): "
                f"{what}. FDI/FPI instruments follow the BoP functional split, not the FSF (which puts all FDI and "
                "FPI in F51 nfc_pvt)."
            ),
            source_id="rbi_hbs_external" if status == "official" and direction == "row_acquires" else None,
            notes="BoP lines (RBI HBS); FDI reinvested earnings and errors and omissions from NAS 2026 (St 1.9, "
            "6.1) so they equal R14a and NAS item 17."
            if status == "official" and direction == "row_acquires"
            else None,
        )

    def counterpart_rows(
        ln_comp: str, direction: str, instr: str, bop: str, val: float, key: dict[str, float], pid: str, how: str
    ) -> None:
        """One row per domestic counterpart of a K8b entry (capital_financial posts them in K7b, row_cp:<fn>)."""
        keys_ = sorted(k for k, sh in key.items() if sh != 0)
        for i, k in enumerate(keys_):
            x = val * key[k] if i < len(keys_) - 1 else val - sum(val * key[j] for j in keys_[:-1])
            sat.append(
                {
                    "series_id": f"{direction}.{ln_comp}.{k.lower()}",
                    "line": ln_comp,
                    "instrument": instr,
                    "bop_function": bop,
                    "direction": direction,
                    "counterpart": k,
                    "key_method": how,
                    "entry_prov_id": pid,
                    "value": x,
                    "unit": "INR_crore",
                }
            )

    k8b_liab = k8b_asset = 0.0
    for ln in lines:
        pid = pids[(ln["status"], ln["direction"])]
        if ln["val"] == 0.0:
            ctx.log(f"K8b: line {ln['comp']} is 0 in 2023-24; not written")
            continue
        row, col = (ln["instr"], "K_ROW") if ln["direction"] == "row_acquires" else ("K_ROW", ln["instr"])
        out.entries.append(
            entry(
                row,
                col,
                "K8b",
                ln["val"],
                prov_id=pid,
                status=ln["status"],
                role="fixed",
                component=ln["comp"],
                bop_function=ln["bop"],
            )
        )
        if ln["direction"] == "row_acquires":
            k8b_liab += ln["val"]
        else:
            k8b_asset += ln["val"]
        rule = ln["rule"]
        if rule in keys:
            key, _, how = keys[rule]
        elif rule == "unallocated_k9":
            key, how = {"unallocated_k9": 1.0}, "no domestic counterpart: capital_financial's K9 residuals absorb it"
        else:
            key, how = {rule: 1.0}, f"single counterpart {rule} (plan s.2.6)"
        counterpart_rows(ln["comp"], ln["direction"], ln["instr"], ln["bop"], ln["val"], key, pid, how)
    for comp, instr, val, key, how in (
        (
            "fpi_debt_gsec",
            "I_GSEC",
            gsec,
            {k: x / gsec for k, x in k_gsec.items()},
            "issuer of the government paper (central dated + T-bills -> K_GCEN, SDLs -> K_GSTA), HBS T107",
        ),
        (
            "fpi_debt_corporate",
            "I_CBND",
            corp,
            keys["fla_equity"][0],
            "issuers by the FLA t8 equity key (low confidence)",
        ),
    ):
        out.entries.append(
            entry(
                instr,
                "K_ROW",
                "K8b",
                val,
                prov_id=pid_split,
                status="estimated",
                role="free",
                confidence="medium",
                component=comp,
                bop_function="FPI_debt",
            )
        )
        counterpart_rows(comp, "row_acquires", instr, "FPI_debt", val, key, pid_split, how)
        k8b_liab += val

    # --- NAS reconciliation lines (NAS 6.1 items 16/17 less the BoP lines) --------------------------------
    for direction, nas_tot, nas_pid, got in (
        ("row_acquires", liab_tot, liab_pid, k8b_liab),
        ("row_incurs", asset_tot, asset_pid, k8b_asset),
    ):
        gap = nas_tot - got
        comp = "nas_reconciliation_liab" if direction == "row_acquires" else "nas_reconciliation_assets"
        if abs(gap) > RECON_MAX:
            raise SamError(f"K8b {comp}: NAS 6.1 total less the BoP lines = {gap:,.2f} (> {RECON_MAX})")
        if gap == 0.0:
            continue
        side_ins = sorted({ln["pid_in"] for ln in lines if ln["direction"] == direction and ln["pid_in"]})
        pid = ctx.prov(
            ref="K8b",
            status="derived",
            inputs=[nas_pid, *side_ins, *([fpi_pid] if direction == "row_acquires" else [])],
            method=(
                f"Gap map K8b, NAS-BoP reconciliation ({direction}): NAS 2026 St 6.1 "
                + (
                    "item 17 net incurrence of foreign liabilities"
                    if direction == "row_acquires"
                    else "item 16 net acquisition of foreign financial assets"
                )
                + " minus the sum of the BoP functional lines written for that side. Asset side: mostly the BPM6 vs "
                "old-format difference in 'other capital' (NAS other financial assets 98,339.48 vs old-format "
                "98,450.04; EXT-13) plus whole-crore rounding; liability side: rounding. I_OTHR, fixed; no domestic "
                "counterpart (K9 absorbs it)."
            ),
            source_id="mospi_nas_2026_publication",
            notes="NAS 6.1 total less RBI HBS BoP lines.",
        )
        row, col = ("I_OTHR", "K_ROW") if direction == "row_acquires" else ("K_ROW", "I_OTHR")
        out.entries.append(
            entry(
                row, col, "K8b", gap, prov_id=pid, status="derived", role="fixed", component=comp, bop_function="other"
            )
        )
        counterpart_rows(
            comp,
            direction,
            "I_OTHR",
            "other",
            gap,
            {"unallocated_k9": 1.0},
            pid,
            "no domestic counterpart: capital_financial's K9 residuals absorb it",
        )
        out.memo[comp] = gap

    # --- K8c: the reserve build-up I_RESV <- K_RBI (the K_ROW <- I_RESV line above is its mirror) -----------
    res, res_pid = v(ctx, c.BPM6, "bpm6.inr.bpm6_3_5.debit.current")
    pid = ctx.prov(
        ref="K8c",
        status="official",
        inputs=[res_pid],
        method="Gap map K8c: change in foreign-exchange reserves on the BoP (flow) basis, BPM6 3.5 reserve assets "
        f"debit ({c.BPM6} bpm6.inr.bpm6_3_5.debit.current), as published; not the stock change in the WSS "
        "reserves table (which includes valuation). RBI holds the reserves: I_RESV <- K_RBI.",
    )
    out.entries.append(
        entry("I_RESV", "K_RBI", "K8c", res, prov_id=pid, status="official", role="fixed", component="reserve_assets")
    )

    # --- constraints -------------------------------------------------------------------------------------
    pl_ = ctx.prov(
        ref="K8b",
        status="official",
        inputs=[liab_pid],
        method=f"Gap map K8b total: NAS 2026 St 6.1 item 17 net incurrence of foreign liabilities ({c.NAS61}), "
        "as published; tolerance Rs 1 crore.",
    )
    pa_ = ctx.prov(
        ref="K8b",
        status="official",
        inputs=[asset_pid],
        method=f"Gap map K8b total: NAS 2026 St 6.1 item 16 net acquisition of foreign financial assets "
        f"({c.NAS61}), as published; tolerance Rs 1 crore.",
    )
    pf_ = ctx.prov(
        ref="K8b",
        status="official",
        inputs=[fpi_pid],
        method="Gap map K8b: BoP old-format FII debt net inflow (bop_old.inr.ka.portfolio.in_india.fiis.debt), "
        "as published: the total the I_GSEC / I_CBND split must keep; tolerance Rs 1 crore.",
    )
    out.constraints += [
        constraint(
            "row.k8b_liabilities_to_row",
            "K8b",
            inst,
            ["K_ROW"],
            liab_tot,
            prov_id=pl_,
            tol_abs=ROUND_TOL,
            refs=["K8b"],
            description="K8b I_* <- K_ROW = NAS 6.1 item 17",
        ),
        constraint(
            "row.k8b_assets_from_row",
            "K8b",
            ["K_ROW"],
            inst,
            asset_tot,
            prov_id=pa_,
            tol_abs=ROUND_TOL,
            refs=["K8b"],
            description="K8b K_ROW <- I_* = NAS 6.1 item 16",
        ),
        constraint(
            "row.fpi_debt",
            "K8b",
            ["I_GSEC", "I_CBND"],
            ["K_ROW"],
            fpi_debt,
            prov_id=pf_,
            tol_abs=ROUND_TOL,
            refs=["K8b"],
            description="FPI debt split I_GSEC + I_CBND = BoP FII debt",
        ),
    ]

    # --- checks ------------------------------------------------------------------------------------------
    def comp_sum(*comps: str) -> float:
        return sum(e["value"] for e in out.entries if e["ref"] == "K8b" and e["component"] in comps)

    nl, nl_pid = v(ctx, c.NAS61, "s6_1.net_lending_to_the_rest_of_the_world_13_14_15_16_or_18_19.current")
    for cid, desc, sv, sid, ds, tol in (
        (
            "k8b_fdi_in_india",
            "K8b FDI-in-India lines vs BoP 3.1.A net",
            comp_sum("fdi_equity", "fdi_reinvested_earnings", "fdi_debt"),
            "bpm6.inr.bpm6_3_1_a.net.current",
            c.BPM6,
            1.0,
        ),
        (
            "k8b_fpi_in_india",
            "K8b FPI-in-India lines vs BoP 3.2.A net",
            comp_sum("fpi_equity", "fpi_debt_gsec", "fpi_debt_corporate"),
            "bpm6.inr.bpm6_3_2_a.net.current",
            c.BPM6,
            LINE_TOL,
        ),
        (
            "k8b_errors_omissions",
            "K8b errors_omissions (NAS) vs BoP 5 errors and omissions",
            comp_sum("errors_omissions"),
            "bpm6.inr.bpm6_5.net.current",
            c.BPM6,
            1.0,
        ),
        (
            "k8b_odi_re_vs_bpm6",
            "K8b odi_reinvested_earnings vs BoP 3.1.B.1.2 debit",
            comp_sum("odi_reinvested_earnings"),
            "bpm6.inr.bpm6_3_1_b_1_2.debit.current",
            c.BPM6,
            1.0,
        ),
        (
            "k8b_nri_vs_hbs_flow",
            "K8b NRI deposits (BoP) vs HBS NRI deposit flows (0.5%)",
            comp_sum("nri_deposits"),
            "nri.flow.inr.total.current",
            c.NRI,
            0.005 * comp_sum("nri_deposits"),
        ),
        (
            "k8c_vs_fsf",
            "K8c vs FSF RoW-liability F3 transaction with RBI",
            res,
            "fsf.row.liabilities.transaction.f3.fc_rbi.current",
            c.FSF,
            1.0,
        ),
    ):
        tv, tp = v(ctx, ds, sid, vintage=c.V_FSF if ds == c.FSF else c.LATEST)
        ctx.check(cid, desc, sv, tv, target_prov_id=tp, tol_abs=tol)
    odi, odi_pid = v(ctx, c.BPM6, "bpm6.inr.bpm6_3_1_b.net.current")
    ctx.check(
        "k8b_odi",
        "K8b ODI lines vs minus BoP 3.1.B net",
        comp_sum("odi_equity", "odi_reinvested_earnings", "odi_debt"),
        -odi,
        target_prov_id=odi_pid,
        tol_abs=LINE_TOL,
    )
    ctx.check(
        "k8b_liabilities_total",
        "K8b I_* <- K_ROW vs NAS 6.1 item 17",
        k8b_liab + out.memo.get("nas_reconciliation_liab", 0.0),
        liab_tot,
        target_prov_id=liab_pid,
        tol_abs=0.01,
    )
    ctx.check(
        "k8b_assets_total",
        "K8b K_ROW <- I_* vs NAS 6.1 item 16",
        k8b_asset + out.memo.get("nas_reconciliation_assets", 0.0),
        asset_tot,
        target_prov_id=asset_pid,
        tol_abs=0.01,
    )
    ctx.check(
        "k8b_net_lending",
        "K8b liabilities - assets vs minus NAS 6.1 net lending to RoW",
        liab_tot - asset_tot,
        -nl,
        target_prov_id=nl_pid,
        tol_abs=1.0,
    )
    q = ctx.rows(c.BPM6Q, series_id="bpm6q.inr.bpm6_3_5.net.current", period=None, vintage=c.LATEST)
    q = q.filter(q["period"].str.ends_with(ctx.year))
    if q.height != 4:
        raise SamError(f"K8c: {q.height} quarters of bpm6q 3.5 for {ctx.year}, need 4")
    qpid = ctx.prov(
        ref="K8c",
        status="derived",
        inputs=sorted(set(q["prov_id"].to_list())),
        method="Sum of the four 2023-24 quarters of BoP BPM6 3.5 reserve assets, net (quarterly BoP), sign "
        "reversed (a check target for K8c).",
    )
    ctx.check(
        "k8c_vs_quarters",
        "K8c vs minus the sum of the four quarters of BoP 3.5 net",
        res,
        -float(q["value"].sum()),
        target_prov_id=qpid,
        tol_abs=1.0,
    )
    sebi, sebi_pid = v(ctx, c.SEBI_FPI, "t60.net_investment.debt_general.current")
    ctx.check(
        "fpi_gsec_vs_sebi",
        "K8b FPI G-sec part vs SEBI/NSDL FPI net investment in debt (general limit), 3%",
        gsec,
        sebi,
        target_prov_id=sebi_pid,
        tol_abs=0.03 * abs(sebi),
    )
    out.memo["fpi_split"] = {"gsec": gsec, "corporate": corp, **held}
    out.memo["counterpart_key_pids"] = sorted(
        {p for _, ps, _ in keys.values() for p in ps} | set(t107_pids) | set(out.memo["key_pids"])
    )
    out.memo["ecb_fc_share"] = ecb_fc / ecb_tot
