"""fincorp assembly: assumption records, the ref modules in order, household property income by group (R8a),
FC saving by sub-sector (K2a), the constraints, the control-total checks and the satellites."""

from __future__ import annotations

from pipeline.sam.blocks.fincorp.core import FC, HH, KFC, Method, Out, Q, Reader, SatOut, qsum, register, shares
from pipeline.sam.blocks.fincorp.deps import ROW_RBI_DEBIT, ROW_RBI_UNEXPLAINED, Deps
from pipeline.sam.blocks.fincorp.dividends import build_dividends, build_oldbase_topup
from pipeline.sam.blocks.fincorp.f4a import IRL, RBI_AR_VINTAGE, RBIAR, RTPB, S71A, S71B, SUTVA, build_f4a
from pipeline.sam.blocks.fincorp.govint import build_govint
from pipeline.sam.blocks.fincorp.insurance import EPFO, EPFO_V, HH_SHARE, build_r9c, build_r17, s9_satellite
from pipeline.sam.blocks.fincorp.interest import Params, build_interest
from pipeline.sam.framework import BlockContext, BlockResult, SamError, constraint

S19 = "mospi_nas_2026_s1_9"
R8A_KEY = {
    "small_savings": "aidis_small_savings",
    "gsec_direct": "aidis_fin_assets",
    "mf_lookthrough": "aidis_mf",
    "deposits_bank": "aidis_deposits",
    "deposits_nbfc": "aidis_deposits",
    "debentures": "aidis_fin_assets",
    "dividends": "aidis_equity",
}


def _param(ctx: BlockContext, ref: str, value: Q, text: str, notes: str | None = None) -> Q:
    """An assumption parameter as its own provenance record (SPEC rule 1); returns it as a tracked number."""
    pid = register(ctx, Method(ref, "estimated", text, notes=notes), value.p)
    return Q(value.v, frozenset({pid}))


def params(ctx: BlockContext, rd: Reader) -> tuple[Params, Q, Q, str, str]:
    cr = lambda s: rd.pct(RTPB, f"rtp.scb_cost_return.{s}.scb")  # noqa: E731
    r_inv = cr("return_on_investments")
    r_star = _param(
        ctx,
        "R4",
        r_inv,
        "Assumption parameter r* (FISIM reference rate) = RBI RTP 2023-24 SCB return on investments "
        f"({r_inv.v:.4f}): a portfolio dominated by government securities approximates the risk-free "
        "rate. Sensitivity 6.5-7.2% (plan s.2.5 step 4c). Used for NFCs' deposit/loan FISIM split; "
        "households' split is the households block's C4b (XR-5), with the same parameters.",
    )
    r_borr = cr("cost_of_borrowings")
    r_corp = _param(
        ctx,
        "R4",
        r_borr,
        f"Assumption parameter r_corp = RBI RTP 2023-24 SCB cost of borrowings ({r_borr.v:.4f}), used as the "
        "coupon on bank/NBFC bonds and borrowings and on NPS corporate bonds (no corporate-bond yield is "
        "ingested). Sensitivity 7.5-9%.",
    )
    prm = Params(
        r_dep=cr("cost_of_deposits"), r_loan=cr("return_on_advances"), r_borr=r_corp, r_inv=r_inv, r_star=r_star
    )
    rate = rd.pct(EPFO, "app5vii.epf_interest_rate", vintage=EPFO_V)
    eps_pid = next(
        iter(
            _param(
                ctx,
                "R9c",
                rate,
                f"Assumption parameter: EPS and exempted-PF funds earn the EPF declared rate ({rate.v:.4f}) "
                "on their average investments (EPS is defined-benefit, so no rate is credited; exempted "
                "trusts must credit at least the EPF rate). Sensitivity 7-8.5%.",
            ).p
        )
    )
    corp = rd.v("finsector_markets_sebi_mf", "t72.aum.corporates.current", period="2024-03-31")
    mf_corp = _param(
        ctx,
        "R8a",
        Q(1.0, corp.p),
        "Assumption parameter: mutual-fund units held by 'corporates' (SEBI T72) belong to private NFCs "
        "(E_NFPR); share 1.0. Banks' units go to E_BANK; HNIs and retail to households.",
    )
    split_pid = ctx.prov(
        ref="R17",
        status="estimated",
        inputs=[],
        method="Assumption parameters (plan s.2.9 step 4): share of each non-life line's premiums, "
        "claims and supplements attributed to households (rest to NFCs): "
        + ", ".join(f"{k} {v:.2f}" for k, v in HH_SHARE.items())
        + ". Retail motor (two-wheelers, cars) dominates motor; group (employer) health is roughly "
        "half of health; fire, marine and engineering are business lines; 'others' holds crop and "
        "personal-accident cover (government-paid crop premiums attributed to farmer households). "
        "No retail/group split is ingested; low confidence; sensitivity +-0.2 per line.",
        notes="no data: stated assumption (docs/phase2/issues/fincorp.md)",
        vintage="2026-09-30",
    )
    return prm, r_corp, mf_corp, eps_pid, split_pid


def assemble(ctx: BlockContext, deps: Deps) -> BlockResult:
    rd = Reader(ctx)
    out = Out(ctx)
    prm, r_corp, mf_corp, eps_pid, split_pid = params(ctx, rd)
    sats = {
        "fc_public_private": SatOut(ctx, "F4a", ["account", "part", "item"]),
        "gov_interest_bridge": SatOut(ctx, "R3b", ["payer", "item", "destination"]),
        "interest_fisim_bridge": SatOut(ctx, "R4", ["creditor", "debtor", "item", "measure"]),
        "dividend_matrix": SatOut(ctx, "R8", ["issuer", "holder", "treatment"]),
        "mf_lookthrough": SatOut(ctx, "R8a", ["holder", "item"]),
        "d44_by_scheme": SatOut(ctx, "R9c", ["scheme", "item"]),
        "s9_funded_schemes": SatOut(ctx, "S9", ["scheme", "flow"]),
    }
    f4 = build_f4a(ctx, rd, out, sats["fc_public_private"])
    gi = build_govint(ctx, rd, out, sats["gov_interest_bridge"], deps, mf_corp)
    it = build_interest(ctx, rd, out, sats["interest_fisim_bridge"], deps, gi, prm, f4.dt_share)
    dv = build_dividends(ctx, rd, out, sats["dividend_matrix"], deps, gi, f4.gos)
    d44 = build_r9c(ctx, rd, out, sats["d44_by_scheme"], deps, gi, r_corp, dv.equity_yield, eps_pid)
    r17 = build_r17(ctx, rd, out, deps, split_pid)
    s9_satellite(ctx, rd, sats["s9_funded_schemes"], d44)
    _r8a(ctx, out, deps, gi, it, dv)
    # D2-21: after every other E_NFPR property-income entry (R8a included), size private NFCs' other distributed
    # income by the old-base sector structure
    hh_key = {k: shares(deps.key(k)) for k in ("aidis_equity", "aidis_mf")}
    build_oldbase_topup(ctx, rd, out, sats["dividend_matrix"], deps, gi, hh_key)
    _insp_income_anchor(ctx, rd, out, sats["d44_by_scheme"], d44)
    _mf_satellite(sats["mf_lookthrough"], gi)
    rbi_target = _k2a(ctx, rd, out, deps, f4.gos)
    cons = _constraints(ctx, rd, gi, r17, rbi_target)
    cons += _insp_bond_bands(ctx, out)
    _checks(ctx, rd, out, deps, it)
    if out.dropped:
        ctx.log(f"{len(out.dropped)} zero-valued entries left out (structural zeros): {out.dropped[:8]}")
    entries = out.entries()
    return BlockResult(
        entries=entries, constraints=cons, satellites={name: s.build(_DESC[name]) for name, s in sats.items()}
    )


_DESC = {
    "fc_public_private": "F4a GOS by FC sub-sector x public/private, with the inputs of the split",
    "gov_interest_bridge": (
        "Union MH 2049 and States' interest lines, their destinations, holder allocation, R3b targets"
    ),
    "interest_fisim_bridge": "R4/R5 interest matrix: FSF positions, rates, bank interest, P&L totals, scale, FISIM",
    "dividend_matrix": "R8 dividends by issuer x holder incl. the government (R7) and RoW (R14) memo parts",
    "mf_lookthrough": "Mutual-fund unit-holder shares (SEBI T72) and the MF income looked through to holders",
    "d44_by_scheme": "R9c D44 by scheme and the stocks/rates behind it",
    "s9_funded_schemes": "S9: gross flows of funded schemes (EPF/EPS/EDLI, NPS, life, GPF, State PF, PPF, PLI, CGEGIS)",
}


def _r8a(ctx: BlockContext, out: Out, deps: Deps, gi, it, dv) -> None:
    totals: dict[tuple[str, str], Q] = {}
    for src in (gi.hh, it.hh_recv, dv.hh):
        for k, q in src.items():
            totals[k] = totals.get(k, Q(0.0)) + q
    out.method(
        "r8a.small_savings",
        "R8a",
        "estimated",
        "Gap map R8a, small savings (savings deposits, certificates and PPF; D41 paid by the NSSF inside "
        "G_CEN): NSSF interest income = Union interest to the NSSF (MH 2049.01.121/.122/.125) + States' "
        "interest on NSSF loans (RBI SF App. II), passed to small savers (the NSSF ran close to balance: "
        "accumulated deficit 8,772.61 at end-March 2024); groups by hh_keys aidis_small_savings.",
    )
    out.method(
        "r8a.other",
        "R8a",
        "estimated",
        "Gap map R8a: household property income by group. Totals: government securities held directly (T107 "
        "'others' household part by FSF, sovereign gold bonds, gold monetisation; R3a), mutual-fund look-"
        "through of government, bank, NBFC, NFC interest and of dividends (SEBI T72 HNIs + retail), bank and "
        "NBFC deposit interest on the SNA basis (bank interest + FISIM on deposits: the households block's C4b "
        "fisim_deposits by group, grossed up for household producers' IC FISIM), NBFC/bank bonds held by "
        "households (R4 method) and dividends (R8 method). Keys: hh_keys aidis_deposits (deposits), "
        "aidis_equity (dividends), aidis_mf (MF), aidis_fin_assets (securities); AIDIS 2019 structure (low).",
    )
    for (comp, payer), q in sorted(totals.items()):
        key = shares(deps.key(R8A_KEY[comp]))
        fisim = it.hh_recv_fisim.get((comp, payer), {})
        for g in HH:
            v = q * key[g] + fisim.get(g, Q(0.0))
            if comp == "small_savings":
                out.add(g, payer, comp, v, key="r8a.small_savings", role="free", confidence="medium")
            else:
                out.add(g, payer, comp, v, key="r8a.other", role="free", confidence="low")


def _insp_income_anchor(ctx: BlockContext, rd: Reader, out: Out, sat: SatOut, d44) -> None:
    """fincorp-2 (E_INSP): the investment income E_INSP needs by the administrative sources behind D44 and R17 vs
    the investment income the SAM gives it from FSF stocks x rates (R3a, R4, R5, R8). Reported, not forced: the SAM
    figure has no P&L anchor (fincorp-15), and no single position can carry the shortfall at a plausible yield."""
    life_sh = rd.v(IRL, "t25.inv_interest_dividends_rent_gross.insurers_life.current") + rd.v(
        IRL, "t25.inv_amortisation.insurers_life.current"
    )
    nonlife = rd.v("finsector_markets_irdai_summary", "sum_c.investment_income.current")
    pf = qsum(q for k, q in d44.by_scheme.items() if k not in ("life", "gpf_union", "gpf_states"))
    admin = d44.by_scheme["life"] + life_sh + nonlife + pf
    sam = qsum(
        i["q"]
        for i in out.items
        if i["row"] == "E_INSP" and i["col"] != "E_INSP" and out.methods[i["key"]].ref in ("R3a", "R4", "R5", "R8")
    )
    sat.method(
        "insp",
        "estimated",
        "fincorp-2: E_INSP investment income by administrative sources (IRDAI 2023-24 life policyholders' and "
        "shareholders' interest, dividends and rent + amortisation; IRDAI non-life investment income; D44 of the "
        "PF and pension schemes, which is their investment income by construction) vs the SAM's R3a + R4 + R5 + R8 "
        "receipts of E_INSP (FSF stocks x rates, no P&L anchor). A memo, not a constraint.",
    )
    for name, q in (
        ("memo.insp_income.life_policyholders", d44.by_scheme["life"]),
        ("memo.insp_income.life_shareholders", life_sh),
        ("memo.insp_income.nonlife", nonlife),
        ("memo.insp_income.pf_pension_d44", pf),
        ("memo.insp_income.admin_total", admin),
        ("memo.insp_income.sam_receipts", sam),
        ("memo.insp_income.shortfall", admin - sam),
    ):
        sat.add(name, q, key="insp", scheme="insp", item=name)
    ctx.log(
        f"E_INSP investment income: administrative sources {admin.v:,.2f} vs SAM receipts {sam.v:,.2f} "
        f"(shortfall {(admin - sam).v:,.2f}; fincorp-2)"
    )


def _mf_satellite(sat: SatOut, gi) -> None:
    sat.method(
        "mf",
        "estimated",
        "SEBI T72 AUM shares by investor class (average end-March 2023/2024) as applied "
        "to mutual-fund income (look-through; corporates -> E_NFPR by an assumption record).",
    )
    for h, s in gi.mf_share.items():
        sat.add(f"share.{h.lower()}", s, key="mf", unit="ratio", holder=h, item="holder_share")
    for (comp, payer), q in sorted(gi.hh.items()):
        if comp == "mf_lookthrough":
            sat.add(
                f"hh_income.gov.{payer.lower()}", q, key="mf", holder="HH", item=f"government interest from {payer}"
            )


def _k2a(ctx: BlockContext, rd: Reader, out: Out, deps: Deps, gos: dict) -> Q:
    fc_tot = rd.v(S19, "s1_9.financial_corporations.current")
    pub = rd.v(S19, "s1_9.public_financial_corporations.current")
    prv = rd.v(S19, "s1_9.private_financial_corporations.current")
    # E_RBI: the balance of its current account over every entry built so far (fincorp + R13/R14 + R6), leaving
    # out rest_of_world's unexplained BoP reserve income (D2-7, XR-4): the prior then rests on the RBI AR figure
    rec = qsum(i["q"] for i in out.items if i["row"] == "E_RBI") + deps.row_sum(
        row="E_RBI", col="R_ROW", refs=("R13",), exclude=(ROW_RBI_UNEXPLAINED,)
    )
    pay = (
        qsum(i["q"] for i in out.items if i["col"] == "E_RBI")
        + deps.row_sum(row="R_ROW", col="E_RBI", refs=("R14",))
        + deps.r6
    )
    rbi = rec - pay
    unexplained = deps.row_sum(row="E_RBI", col="R_ROW", refs=("R13",), comps=(ROW_RBI_UNEXPLAINED,))
    ctx.log(f"K2a: E_RBI saving prior {rbi.v:,.2f} (R13 unexplained reserve income left out: {unexplained.v:,.2f})")
    pub_gos = qsum(q for (a, p), q in gos.items() if p == "public" and a != "E_RBI")
    prv_gos = qsum(q for (a, p), q in gos.items() if p == "private")
    ratio_pub, ratio_prv = (pub - rbi) / pub_gos, prv / prv_gos
    if ratio_pub.v <= 0:
        raise SamError(f"fincorp K2a: public FC saving less RBI's is {(pub - rbi).v:,.0f}")
    out.method(
        "k2a.rbi",
        "K2a",
        "estimated",
        "Gap map K2a, E_RBI: RBI's saving = the balance of E_RBI's current account over the SAM entries: GOS "
        "(F4a), interest received from government, banks and NBFCs (R3a, R4; RBI AR accrual), reserve income "
        "from RoW (rest_of_world R13, RBI AR component only: the unexplained BoP excess is left to balancing, "
        "D2-7), less interest paid (R4, R14) and the surplus paid to the Centre on the cash basis (government "
        "R6, D0-7/D2-16). Holding gains and provisions are not income.",
    )
    out.method(
        "k2a.other",
        "K2a",
        "estimated",
        "Gap map K2a (plan s.2.11; no dividend or tax data by FC sub-sector): each sub-sector's public and "
        "private saving = its F4a GOS part x (NAS 2026 St 1.9 public FC saving less E_RBI's, over public GOS "
        "excluding RBI) or x (private FC saving / private FC GOS). Reproduces the NAS public and private "
        "totals; low confidence (balancing makes K2a the residual of each FC account).",
    )
    if rbi.v == 0:
        raise SamError("fincorp K2a: E_RBI saving is exactly zero")
    out.add("K_RBI", "E_RBI", "public", rbi, key="k2a.rbi", role="free", confidence="low", sign=1 if rbi.v > 0 else -1)
    for (a, p), q in sorted(gos.items()):
        if a == "E_RBI":
            continue
        out.add(
            KFC[a],
            a,
            p,
            q * (ratio_pub if p == "public" else ratio_prv),
            key="k2a.other",
            role="free",
            confidence="low",
        )
    nas_rbi = pub - rd.v(S71A, "s7_1a.financial.os.current") - rd.v(S71A, "s7_1a.financial.cfc.current")
    # plan C3 (D0-7 evidence) is on the RBI Annual Report basis. The AR shows no charge on SDR allocations (its
    # interest expense is 2.19), so rest_of_world's reserve-asset debit on E_RBI is left out of the evidence; the
    # K2a prior keeps it (D2-7: saving from the SAM entries) and is compared with NAS in a check of its own
    debit = deps.row_sum(row="R_ROW", col="E_RBI", refs=("R14",), comps=(ROW_RBI_DEBIT,))
    ctx.log(f"K2a: E_RBI saving without rest_of_world's R14 '{ROW_RBI_DEBIT}' ({debit.v:,.2f}): {(rbi + debit).v:,.2f}")
    ctx.check(
        "k2a.rbi_cash_basis_evidence",
        "E_RBI saving on the RBI AR basis (SAM entries without rest_of_world's R14 reserve-asset debit, which the "
        "RBI AR does not show) vs NAS public FC saving less public FC GOS (D0-7 evidence; plan C3: ~Rs 122 cr)",
        (rbi + debit).v,
        nas_rbi.v,
        target_prov_id=next(iter(pub.p)),
        tol_abs=2500.0,
    )
    ctx.check(
        "k2a.rbi_prior_vs_nas",
        "E_RBI saving prior (K2a, all SAM entries incl. rest_of_world's R14 reserve-asset debit, D2-7) vs NAS "
        "public FC saving less public FC GOS (fincorp-1: fails by the debit while it sits on E_RBI)",
        rbi.v,
        nas_rbi.v,
        target_prov_id=next(iter(pub.p)),
        tol_abs=2500.0,
    )
    ctx.check(
        "k2.total_equals_parts",
        "NAS 1.9 FC saving vs public + private",
        (pub + prv).v,
        fc_tot.v,
        target_prov_id=next(iter(fc_tot.p)),
        tol_abs=0.01,
    )
    # audit BS-1 / fincorp-34 (a): the target of the K2a E_RBI band = the NAS-derived RBI saving (the D0-7 evidence
    # of check k2a.rbi_cash_basis_evidence) less rest_of_world's reserve-asset debit, which sits on E_RBI in the SAM
    return nas_rbi - debit


def _insp_bond_bands(ctx: BlockContext, out: Out) -> list[dict]:
    """Audit BS-1 (2026-10-01): insurers' and pension funds' interest on NFC bonds is an unscaled stock x rate
    (FSF ICPF holdings x the corporate coupon, fincorp-30); balancing raised the public NFC line to an implied
    yield of 16-22% (fincorp-32). Each payer's line is held within 25% of FSF stock x coupon."""
    cons = []
    for payer in ("E_NFPU", "E_NFPR"):
        q = out.total(ref="R5", rows=["E_INSP"], cols=[payer], comps=["nongov_bonds"])
        pid = _cons_pid(
            ctx,
            "R5",
            "estimated",
            q,
            f"Constraint target for R5 E_INSP <- {payer} nongov_bonds (audit BS-1, fincorp-32): RBI FSF ICPF "
            "holdings of the payer's bonds (average of end-March 2023 and 2024) x the corporate coupon (RBI RTP "
            "2023-24 SCB cost of borrowings), unscaled (fincorp-30); band 25%, the spread of corporate bond "
            "coupons around it.",
        )
        cons.append(constraint(f"r5.insp_bonds.{payer.lower()}", "R5", ["E_INSP"], [payer], q.v, prov_id=pid,
                               tol_rel=0.25, kind="band", refs=["R5"], components=["nongov_bonds"],
                               description=f"Insurers' interest on {payer} bonds near FSF stock x coupon (band 25%)"))
    # the same stock x coupon evidence for public NFC bonds held by MFs and looked through to private NFC unit
    # holders (R8 interest_mf_lookthrough; fincorp-30): a trial run of the Wave C fix multiplied it by 5.4 once the
    # insurers' line was held
    q = out.total(ref="R8", rows=["E_NFPR"], cols=["E_NFPU"], comps=["interest_mf_lookthrough"])
    pid = _cons_pid(
        ctx,
        "R8",
        "estimated",
        q,
        "Constraint target for R8 E_NFPR <- E_NFPU interest_mf_lookthrough (audit BS-1, fincorp-32): RBI FSF MF "
        "holdings of public NFC bonds x the corporate coupon (fincorp-30), looked through to private NFC unit "
        "holders by SEBI T72; band 25%, the spread of corporate bond coupons around it.",
    )
    cons.append(constraint("r8.mf_bonds.e_nfpu", "R8", ["E_NFPR"], ["E_NFPU"], q.v, prov_id=pid, tol_rel=0.25,
                           kind="band", refs=["R8"], components=["interest_mf_lookthrough"],
                           description="MF-held public NFC bond interest looked through to private NFCs near FSF "
                           "stock x coupon (band 25%)"))  # fmt: skip
    # fincorp-32 (a): public NFCs' dividends to non-government holders (direct, and through MF units) are the R7-
    # grossed issuer total (satellite dividend_matrix, total.e_nfpu) less government's R7 and E_NFPU's own holding;
    # balancing multiplied them by 1.7-3.3 with nothing behind it (a non-government holder cannot earn several times
    # the government's dividend per unit of book equity). Held within 25%. The MF look-through component carries
    # the MF-held bond interest for households too (fincorp-32), so the target is the prior sum of the entries.
    holders = ["E_BANK", "E_NBFC", "E_INSP", "E_NFPR", *HH]
    q = out.total(rows=holders, cols=["E_NFPU"], comps=["dividends", "mf_lookthrough"], ref="R8") + out.total(
        rows=holders, cols=["E_NFPU"], comps=["dividends", "mf_lookthrough"], ref="R8a"
    )
    pid = _cons_pid(
        ctx,
        "R8",
        "estimated",
        q,
        "Constraint target for R8/R8a paid by E_NFPU to non-government holders (fincorp-32 (a), audit BS-1): the "
        "dividend matrix's public NFC issuer total (government R7 grossed up by FSF F51 holder shares) less R7 and "
        "E_NFPU's own holding, direct and looked through MF units (the households' MF component includes MF-held "
        "bond interest); band 25%.",
    )
    cons.append(constraint("r8.nfpu_nongov_holders", "R8", holders, ["E_NFPU"], q.v, prov_id=pid, tol_rel=0.25,
                           kind="band", refs=["R8", "R8a"], components=["dividends", "mf_lookthrough"],
                           description="Public NFC dividends to non-government holders near the R7-grossed issuer "
                           "total, including households' MF-held public NFC bond interest (mf_lookthrough) (band "
                           "25%)"))  # fmt: skip
    return cons


def _cons_pid(ctx: BlockContext, ref: str, status: str, q: Q, text: str) -> str:
    return register(ctx, Method(ref, status, text), q.p)


def _constraints(ctx: BlockContext, rd: Reader, gi, r17: dict, rbi_target: Q) -> list[dict]:
    hh, nfc = HH, ["E_NFPU", "E_NFPR"]
    k_rows = [KFC[a] for a in FC]
    a_os, a_cfc = rd.v(S71A, "s7_1a.financial.os.current"), rd.v(S71A, "s7_1a.financial.cfc.current")
    b_os, b_cfc = rd.v(S71B, "s7_1b.financial.os.current"), rd.v(S71B, "s7_1b.financial.cfc.current")
    fc_gos = a_os + a_cfc + b_os + b_cfc
    pub, prv = a_os + a_cfc, b_os + b_cfc
    i55 = rd.v(SUTVA, "va.os_mi.sut_i55.current") + rd.v(SUTVA, "va.cfc.sut_i55.current")
    i56 = rd.v(SUTVA, "va.os_mi.sut_i56.current") + rd.v(SUTVA, "va.cfc.sut_i56.current")
    k2 = {
        k: rd.v(S19, f"s1_9.{k}.current")
        for k in ("financial_corporations", "public_financial_corporations", "private_financial_corporations")
    }
    p_f4a = _cons_pid(
        ctx,
        "F4a",
        "official",
        fc_gos + i55 + i56,
        "Constraint targets for F4a: NAS 2026 St 7.1A + 7.1B financial OS + CFC (FC GOS; public = 7.1A, "
        "private = 7.1B), SUT 2023-24 industry 55 and 56 OS/MI + CFC; as published, summed.",
    )
    p_k2 = _cons_pid(
        ctx,
        "K2",
        "official",
        qsum(k2.values()),
        "Constraint targets for K2: NAS 2026 St 1.9 gross saving of financial corporations, total, public "
        "and private, as published.",
    )
    p_r3b = _cons_pid(
        ctx,
        "R3b",
        "estimated",
        gi.targets["union"] + gi.targets["states"],
        "Constraint targets for R3b (plan s.2.3): Union = MH 2049 total less intra-G_CEN interest (NSSF "
        "special securities, reserve funds, FCI and PLI securities), management of debt, recoveries and "
        "the accrued interest and premium received on re-issues, plus the NSSF's interest to small savers "
        "(estimated); States = App. II interest less 'others' (intra-G_STA) and SDLs held by State "
        "governments. Every destination is in the satellite gov_interest_bridge.",
    )
    p_r9c = _cons_pid(
        ctx,
        "R9c",
        "official",
        gi.gpf_union,
        "Constraint target for R9c GPF: Union Finance Accounts "
        "2023-24 MH 2049.03.104 interest credited to GPF, as published.",
    )
    life = rd.v("finsector_markets_irdai_life", "t24.inv_interest_dividends_rent_gross.insurers_life.current") + rd.v(
        "finsector_markets_irdai_life", "t24.inv_amortisation.insurers_life.current"
    )
    p_life = _cons_pid(
        ctx,
        "R9c",
        "derived",
        life,
        "Constraint target for R9c life D44: IRDAI 2023-24 policyholders' "
        "account investment income (interest, dividends, rent, gross) + amortisation, life insurers.",
    )
    p_r17 = _cons_pid(
        ctx,
        "R17",
        "official",
        r17["claims"],
        "Constraint target for R17: IRDAI 2023-24 net incurred "
        "claims, all direct general and health insurers (T44 total), as published; D71 = D72 (expected-"
        "claims approach).",
    )
    # --- Wave C audit (2026-10-01, BS-1): published totals that balancing moved freely are declared ----------------
    p_supp = _cons_pid(
        ctx,
        "R17",
        "derived",
        r17["supplement"],
        "Constraint target for R17 premium supplements (fincorp-33, audit BS-1): IRDAI 2023-24 non-life investment "
        "income (summary) less shareholders' investment income (T51), the figure the R17 entries split; band 1% "
        "(the claims tolerance), so balancing cannot cut the supplements and break D71 = D72 by payer.",
    )
    p_rbi = _cons_pid(
        ctx,
        "K2a",
        "derived",
        rbi_target,
        "Constraint target for K2a E_RBI (fincorp-34 (a), audit BS-1): NAS 2026 St 1.9 public FC saving less St "
        "7.1A financial OS and CFC (the D0-7 evidence of check k2a.rbi_cash_basis_evidence) less rest_of_world's "
        "R14 reserve-asset debit on E_RBI; band Rs 2,500 crore (the check's tolerance). Balancing then removes "
        "the unexplained BoP reserve income (D2-7) from E_RBI instead of saving it.",
    )
    p_sol = _cons_pid(
        ctx,
        "R3a",
        "derived",
        gi.targets["states_other_internal"],
        "Constraint target for R3a (fincorp-35, audit BS-1): States' interest on other internal debt = RBI State "
        "Finances App. II interest on internal debt less market loans and NSSF (all States and UTs), the cash "
        "line that R3a state_loans (E_BANK, E_NBFC) and E_RBI wma_od split; band 2% (as the r3.cash anchors).",
    )
    p_payer = _cons_pid(
        ctx,
        "R17",
        "estimated",
        qsum(r17["by_sector"].values()),
        "Constraint targets for R17 by payer sector (fincorp-33, audit BS-1): each sector's net non-life claims = "
        "its net premiums (D71 = D72 line by line, the expected-claims approach), and its premium supplements, from "
        "the R17 payer split (households' share by line an assumption record; NFCs by factors' NFC GOS). Band 5% on "
        "each, set separately for premiums and for claims: the framework has no signed selection, so premiums less "
        "claims cannot be held at 0 by payer, and one payer's premiums and claims can end up to about 10% apart "
        "(each at an opposite edge; E_NFPU +10.5% and E_NFPR +8.1% in the wave C balanced run). The 5% is a "
        "judgement, not the split's measured uncertainty (the split's assumption record states a sensitivity of "
        "+-0.2 per line). Close-out V-FIN-9; FRAMEWORK_REQUESTS FR-C-3 asks for signed selections.",
    )
    all_int_rows = [*FC, *nfc, *hh, "G_STA", "R_ROW"]
    payer_rows = {"HH": hh, "E_NFPU": ["E_NFPU"], "E_NFPR": ["E_NFPR"]}
    wave_c = [
        constraint(
            f"r17.payer.{s.lower()}.{c}",
            "R17",
            ["E_INSP"] if c == "premium" else payer_rows[s],
            payer_rows[s] if c == "premium" else ["E_INSP"],
            r17["by_sector"][(s, "premium_supplement" if c == "premium_supplement" else "claim")].v,
            prov_id=p_payer,
            tol_rel=0.05,
            kind="band",
            refs=["R17"],
            components=[c],
            description=f"R17 {c}s of payer {s} near its prior (D71 = D72 by line; band 5%)",
        )
        for s in ("HH", "E_NFPU", "E_NFPR")
        for c in ("premium", "claim", "premium_supplement")
    ]
    wave_c += [
        constraint(
            "r17.supplements",
            "R17",
            [*hh, *nfc],
            ["E_INSP"],
            r17["supplement"].v,
            prov_id=p_supp,
            tol_rel=0.01,
            kind="band",
            refs=["R17"],
            components=["premium_supplement"],
            description="Non-life premium supplements = IRDAI investment income attributed to policyholders (1%)",
        ),
        constraint(
            "k2a.rbi_ar_basis",
            "K2a",
            ["K_RBI"],
            ["E_RBI"],
            rbi_target.v,
            prov_id=p_rbi,
            tol_abs=2500.0,
            kind="band",
            refs=["K2a"],
            description="RBI saving near the NAS-derived figure on the RBI AR basis (band Rs 2,500 crore)",
        ),
        constraint(
            "r3a.states_other_internal_debt",
            "R3a",
            ["E_BANK", "E_NBFC", "E_RBI"],
            ["G_STA"],
            gi.targets["states_other_internal"].v,
            prov_id=p_sol,
            tol_rel=0.02,
            kind="band",
            refs=["R3a"],
            components=["state_loans", "wma_od"],
            description="States' interest on other internal debt (state_loans + wma_od) near RBI SF App. II (2%)",
        ),
    ]
    return wave_c + [
        constraint(
            "f4a.fc_gos_total",
            "F4a",
            FC,
            ["F_GOSC"],
            fc_gos.v,
            prov_id=p_f4a,
            tol_abs=1.0,
            refs=["F4a"],
            description="FC GOS = NAS 7.1A + 7.1B financial OS + CFC (same as factors' f4.fc_gos)",
        ),
        constraint(
            "f4a.fins_gos",
            "F4a",
            ["E_RBI", "E_BANK", "E_NBFC"],
            ["F_GOSC"],
            i55.v,
            prov_id=p_f4a,
            tol_abs=1.0,
            refs=["F4a"],
            description="RBI + banks + NBFCs GOS = SUT industry 55 OS/MI + CFC",
        ),
        constraint(
            "f4a.insp_gos",
            "F4a",
            ["E_INSP"],
            ["F_GOSC"],
            i56.v,
            prov_id=p_f4a,
            tol_abs=1.0,
            refs=["F4a"],
            description="Insurance and pension GOS = SUT industry 56 OS/MI + CFC",
        ),
        constraint(
            "f4a.public",
            "F4a",
            FC,
            ["F_GOSC"],
            pub.v,
            prov_id=p_f4a,
            tol_abs=1.0,
            refs=["F4a"],
            components=["public"],
            description="Public FC GOS = NAS 7.1A financial OS + CFC",
        ),
        constraint(
            "f4a.private",
            "F4a",
            FC,
            ["F_GOSC"],
            prv.v,
            prov_id=p_f4a,
            tol_abs=1.0,
            refs=["F4a"],
            components=["private"],
            description="Private FC GOS = NAS 7.1B financial OS + CFC",
        ),
        constraint(
            "k2.fc_saving_total",
            "K2",
            k_rows,
            FC,
            k2["financial_corporations"].v,
            prov_id=p_k2,
            tol_abs=1.0,
            refs=["K2a"],
            description="FC gross saving = NAS 1.9",
        ),
        constraint(
            "k2.public",
            "K2",
            k_rows,
            FC,
            k2["public_financial_corporations"].v,
            prov_id=p_k2,
            tol_abs=1.0,
            refs=["K2a"],
            components=["public"],
            description="Public FC gross saving = NAS 1.9",
        ),
        constraint(
            "k2.private",
            "K2",
            k_rows,
            FC,
            k2["private_financial_corporations"].v,
            prov_id=p_k2,
            tol_abs=1.0,
            refs=["K2a"],
            components=["private"],
            description="Private FC gross saving = NAS 1.9 (co-op banks private, D2-14)",
        ),
        constraint(
            "r3b.union_nas_concept",
            "R3b",
            all_int_rows,
            ["G_CEN"],
            gi.targets["union"].v,
            prov_id=p_r3b,
            tol_rel=0.03,
            kind="band",
            refs=["R3", "R3a", "R8a", "R9c", "R14"],
            description="Union interest paid on the NAS concept (band 3%: NSSF interest to savers is estimated)",
        ),
        constraint(
            "r3b.states_nas_concept",
            "R3b",
            [*FC, *nfc, *hh, "G_CEN", "R_ROW"],
            ["G_STA"],
            gi.targets["states"].v,
            prov_id=p_r3b,
            tol_rel=0.01,
            kind="band",
            refs=["R3", "R3a", "R8a", "R9c", "R14"],
            description="States' interest paid, net of intra-State items (band 1%)",
        ),
        constraint(
            "r9c.gpf_union",
            "R9c",
            hh,
            ["G_CEN"],
            gi.gpf_union.v,
            prov_id=p_r9c,
            tol_rel=0.02,
            refs=["R9c"],
            description="Union GPF interest credited = MH 2049.03.104",
        ),
        constraint(
            "r9c.life",
            "R9c",
            hh,
            ["E_INSP"],
            life.v,
            prov_id=p_life,
            tol_rel=0.05,
            kind="band",
            refs=["R9c"],
            components=["life"],
            description="Life policyholders' investment income (IRDAI), band 5%",
        ),
        constraint(
            "r17.claims",
            "R17",
            [*hh, *nfc],
            ["E_INSP"],
            r17["claims"].v,
            prov_id=p_r17,
            tol_rel=0.01,
            refs=["R17"],
            components=["claim"],
            description="Net non-life claims (D72) = IRDAI net incurred claims",
        ),
        constraint(
            "r17.premiums",
            "R17",
            ["E_INSP"],
            [*hh, *nfc],
            r17["claims"].v,
            prov_id=p_r17,
            tol_rel=0.01,
            kind="band",
            refs=["R17"],
            components=["premium"],
            description="Net non-life premiums (D71) = claims (expected-claims approach), band 1% as the claims "
            "(fincorp-33, audit BS-1; was 5%)",
        ),
    ]


def _checks(ctx: BlockContext, rd: Reader, out: Out, deps: Deps, it) -> None:
    f4a = out.total(ref="F4a")
    if deps.factors_fc_gos is not None:
        ctx.check(
            "f4a.equals_factors_fc_gos",
            "Sum of F4a entries vs factors' FC GOS constraint target",
            f4a.v,
            deps.factors_fc_gos.v,
            target_prov_id=next(iter(deps.factors_fc_gos.p)),
            tol_abs=1.0,
        )
    for act, rows in (("A_FINS", ["E_RBI", "E_BANK", "E_NBFC"]), ("A_INSR", ["E_INSP"])):
        if act in deps.prod_os:
            t = deps.prod_os[act]
            ctx.check(
                f"f4a.equals_production_{act.lower()}",
                f"F4a of {', '.join(rows)} vs production's OS/MI+CFC target for {act}",
                out.total(ref="F4a", rows=rows).v,
                t.v,
                target_prov_id=next(iter(t.p)),
                tol_abs=1.0,
            )
    rbi_dep = rd.v(RBIAR, "is.exp_interest.current", vintage=RBI_AR_VINTAGE)
    ctx.log(f"R4: RBI's own interest expense ({rbi_dep.v:,.2f}, counterparty not published) is not written")
