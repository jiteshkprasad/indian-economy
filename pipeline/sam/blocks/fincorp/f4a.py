"""F4a: FC gross operating surplus by sub-sector (E_RBI, E_BANK, E_NBFC, E_INSP) x ownership (public/private).

Anchors: NAS 2026 St 8.12 GVA by FC sub-sector; SUT 2023-24 industries 55 (financial services) and 56
(insurance) for OS/MI + CFC; RBI Annual Report 2023-24 employee cost; RTP 2023-24 wage bills and operating
profits; IRDAI 2023-24; NAS 7.1A / 7.1B financial OS + CFC for the public / private totals (plan s.2.1)."""

from __future__ import annotations

from dataclasses import dataclass

from pipeline.sam.blocks.fincorp.core import Out, Q, Reader, SatOut, qsum
from pipeline.sam.framework import BlockContext, SamError

S812, SUTVA, S71A, S71B = "mospi_nas_2026_s8_12", "io_tables_sut_va", "mospi_nas_2026_s7_1a", "mospi_nas_2026_s7_1b"
RBIAR, RBI_AR_VINTAGE = "rbi_banking_corporate_rbi_accounts", "2024-05-30"  # RBI AR 2023-24 (2025-05-29 repeats it)
RTPB, RTPC, RTPN = "rbi_banking_corporate_rtp_banks", "rbi_banking_corporate_rtp_coop", "rbi_banking_corporate_rtp_nbfi"
FSF = "rbi_financial_accounts_fsf_balance_sheets"
IRL, IRN = "finsector_markets_irdai_life", "finsector_markets_irdai_nonlife"
ENDS = ("2023-03-31", "2024-03-31")  # FSF / T107 stocks: average of the two end-Marches


def fsf(rd: Reader, sector: str, side: str, inst: str, cp: str) -> Q:
    """Average outstanding FSF stock (end-March 2023 and 2024), Rs crore."""
    return rd.avg(FSF, f"fsf.{sector}.{side}.outstanding.{inst}.{cp}.current", ENDS)


@dataclass
class F4aResult:
    gos: dict[tuple[str, str], Q]  # (account, 'public'|'private') -> GOS
    dt_share: dict[str, Q]  # 'nbfc' / 'hfc' -> share of deposit-taking companies in the RTP NBFC / HFC books


def build_f4a(ctx: BlockContext, rd: Reader, out: Out, sat: SatOut) -> F4aResult:
    y = ctx.year
    s121 = rd.v(S812, "s8_12.central_bank_s_121.current")
    s122 = rd.v(S812, "s8_12.deposit_taking_corporations_excluding_central_bank_s_122_and.current")
    ofc = rd.v(S812, "s8_12.other_financial_corporations_s_124_to_s_127.current")
    life_gva = rd.v(S812, "s8_12.life_insurance_s_128.current")
    nonlife_gva = rd.v(S812, "s8_12.non_life_insurance_s_128.current")
    rbi_ce = rd.v(RBIAR, "is.exp_employee_cost.current", vintage=RBI_AR_VINTAGE)
    rbi_dep = rd.v(RBIAR, "is.exp_depreciation.current", vintage=RBI_AR_VINTAGE)
    gva55 = rd.v(SUTVA, "va.gva_production.sut_i55.current")
    ce55, npt55 = rd.v(SUTVA, "va.ce.sut_i55.current"), rd.v(SUTVA, "va.net_production_taxes.sut_i55.current")
    gos55 = rd.v(SUTVA, "va.os_mi.sut_i55.current") + rd.v(SUTVA, "va.cfc.sut_i55.current")
    gos56 = rd.v(SUTVA, "va.os_mi.sut_i56.current") + rd.v(SUTVA, "va.cfc.sut_i56.current")
    pub_total = rd.v(S71A, "s7_1a.financial.os.current") + rd.v(S71A, "s7_1a.financial.cfc.current")

    # --- E_RBI: central-bank output is valued at cost, so GOS = GVA - CE (= depreciation) ----------------
    e_rbi = s121 - rbi_ce
    ctx.check(
        "f4a.rbi_gos_equals_depreciation",
        "E_RBI GOS (NAS 8.12 S121 GVA - RBI employee cost) vs RBI AR depreciation",
        e_rbi.v,
        rbi_dep.v,
        target_prov_id=next(iter(rbi_dep.p)),
        tol_abs=0.01,
    )

    # --- deposit-taking NBFC/HFC share (XR-6: they sit in E_BANK = FSF ODC) -------------------------------
    def dt(dt_sec: str, ndt_sec: str) -> Q:
        a, b = fsf(rd, dt_sec, "assets", "f4", "all"), fsf(rd, ndt_sec, "assets", "f4", "all")
        return a / (a + b)

    dt_share = {"nbfc": dt("fc_odc_nbfc_dt", "fc_ofc_nbfc_ndt"), "hfc": dt("fc_odc_hfc_dt", "fc_ofc_hfc_ndt")}
    nbfc_opex = rd.v(RTPN, "rtp.nbfc_layer_pl.operating_expenditure.nbfc_ul.current") + rd.v(
        RTPN, "rtp.nbfc_layer_pl.operating_expenditure.nbfc_ml.current"
    )
    hfc_opex = rd.v(RTPN, "rtp.hfc_pl.operating_expenditure.hfc.current")
    scb_wage_ratio = rd.v(RTPB, "rtp.scb_pl.wage_bill.scb.current") / rd.v(
        RTPB, "rtp.scb_pl.operating_expenses.scb.current"
    )
    dt_ce = (dt_share["nbfc"] * nbfc_opex + dt_share["hfc"] * hfc_opex) * scb_wage_ratio
    bank_wages = qsum(
        [
            rd.v(RTPB, "rtp.scb_pl.wage_bill.scb.current"),
            rd.v(RTPB, "rtp.rrb_pl.wage_bill.rrb.current"),
            rd.v(RTPC, "rtp.ucb_pl.staff_expenses.ucb.current"),
            rd.v(RTPC, "rtp.stcb_pl.wage_bill.stcb.current"),
            rd.v(RTPC, "rtp.dccb_pl.wage_bill.dccb.current"),
        ]
    )
    ce_bank = bank_wages + dt_ce
    ce_nbfc = ce55 - rbi_ce - ce_bank
    if ce_nbfc.v <= 0:
        raise SamError(f"fincorp F4a: residual NBFC CE is {ce_nbfc.v:,.2f} (bank wage bills exceed SUT ind. 55 CE)")
    scale = (gva55 - s121) / (s122 + ofc)
    gva_bank, gva_nbfc = s122 * scale, ofc * scale
    npt_bank = npt55 * gva_bank / (gva_bank + gva_nbfc)
    raw_bank = gva_bank - ce_bank - npt_bank
    raw_nbfc = gva_nbfc - ce_nbfc - (npt55 - npt_bank)
    rest = gos55 - e_rbi
    e_bank = rest * raw_bank / (raw_bank + raw_nbfc)
    e_nbfc = rest - e_bank

    # --- public parts ---------------------------------------------------------------------------------
    def op(grp: str, src: str = RTPB, stem: str = "scb_pl") -> Q:
        return rd.v(src, f"rtp.{stem}.operating_profit.{grp}.current")

    bank_op = qsum(
        [
            op("scb"),
            op("rrb", RTPB, "rrb_pl"),
            op("ucb", RTPC, "ucb_pl"),
            op("stcb", RTPC, "stcb_pl"),
            op("dccb", RTPC, "dccb_pl"),
        ]
    )
    nbfc_pbt = rd.v(RTPN, "rtp.nbfc_layer_pl.profit_before_tax.nbfc_ul.current") + rd.v(
        RTPN, "rtp.nbfc_layer_pl.profit_before_tax.nbfc_ml.current"
    )
    hfc_op = (
        rd.v(RTPN, "rtp.hfc_pl.fund_income.hfc.current")
        + rd.v(RTPN, "rtp.hfc_pl.fee_income.hfc.current")
        - rd.v(RTPN, "rtp.hfc_pl.financial_expenditure.hfc.current")
        - hfc_opex
    )
    dt_op = dt_share["nbfc"] * nbfc_pbt + dt_share["hfc"] * hfc_op
    bank_pub_share = (op("psb") + op("rrb", RTPB, "rrb_pl")) / (bank_op + dt_op)
    bank_pub_share_banks_only = (op("psb") + op("rrb", RTPB, "rrb_pl")) / bank_op  # the plan's s.2.1 figure
    ctx.log(
        f"F4a: E_BANK public share {bank_pub_share.v:.4f} with the deposit-taking NBFC/HFC profit proxy "
        f"({dt_op.v:,.2f}); banks only (plan s.2.1) {bank_pub_share_banks_only.v:.4f}"
    )
    life_w = life_gva / (life_gva + nonlife_gva)
    lic_share = rd.v(IRL, "t24.operating_expenses.lic.current") / rd.v(
        IRL, "t24.operating_expenses.insurers_life.current"
    )
    npe = "t44.net_premium_earned.total.{}.current"
    nl_pub_share = (rd.v(IRN, npe.format("general_public")) + rd.v(IRN, npe.format("general_specialized"))) / rd.v(
        IRN, npe.format("insurers_general_direct")
    )
    insp_pub_share = life_w * lic_share + (1.0 - life_w) * nl_pub_share
    bank_pub, insp_pub = e_bank * bank_pub_share, gos56 * insp_pub_share
    nbfc_pub = pub_total - e_rbi - bank_pub - insp_pub
    share = nbfc_pub.v / e_nbfc.v
    if not 0 < share < 1:
        raise SamError(f"fincorp F4a: the public NBFC residual is {nbfc_pub.v:,.2f} ({share:.1%} of E_NBFC GOS)")
    if not 0.20 <= share <= 0.50:
        ctx.warn(f"F4a: public share of E_NBFC GOS (residual) is {share:.1%}, outside the plausible 20-50% band")
    ctx.log(f"F4a: public share of E_NBFC GOS {share:.1%} (RTP government NBFC asset share is a cross-check)")

    gos = {
        ("E_RBI", "public"): e_rbi,
        ("E_BANK", "public"): bank_pub,
        ("E_BANK", "private"): e_bank - bank_pub,
        ("E_NBFC", "public"): nbfc_pub,
        ("E_NBFC", "private"): e_nbfc - nbfc_pub,
        ("E_INSP", "public"): insp_pub,
        ("E_INSP", "private"): gos56 - insp_pub,
    }

    out.method(
        "f4a.rbi",
        "F4a",
        "derived",
        f"Gap map F4a, E_RBI: NAS 2026 St 8.12 GVA of the central bank (S121) minus RBI Annual Report {y} "
        f"employee cost (vintage {RBI_AR_VINTAGE}); central-bank output is valued at cost, so this equals "
        "RBI depreciation (checked). All public.",
    )
    out.method(
        "f4a.split",
        "F4a",
        "estimated",
        "Gap map F4a (STRBI unavailable; plan s.2.1): E_BANK + E_NBFC = SUT 2023-24 industry 55 OS/MI + CFC "
        "less E_RBI, split in proportion to (GVA - CE - net production taxes) where GVA = NAS 8.12 S122 "
        "(deposit-taking) and S124-S127 (other FCs) scaled to SUT ind. 55 GVA less S121; CE of E_BANK = RTP "
        "wage bills of SCBs, RRBs, UCBs, StCBs, DCCBs plus the deposit-taking NBFC/HFC share (XR-6: FSF ODC "
        "boundary; share = FSF fc_odc_*_dt / (dt + ndt) loans, average end-March 2023/2024) of RTP NBFC and "
        "HFC operating expenditure times the SCB wage-bill/operating-expense ratio; CE of E_NBFC = SUT ind. 55 "
        "CE - RBI employee cost - E_BANK CE (residual: PACS, ARDBs, auxiliaries); net production taxes pro "
        "rata GVA. E_INSP = SUT industry 56 OS/MI + CFC (pension funds S129 have zero GVA). Public parts: "
        "E_BANK x (PSB + RRB operating profit) / (operating profit of SCBs, RRBs, UCBs, StCBs and DCCBs + the "
        "deposit-taking NBFC/HFC profit proxy), where the proxy = RTP NBFC-UL + NBFC-ML profit before tax x the "
        "deposit-taking NBFC share + RTP HFC (fund income + fee income - financial expenditure - operating "
        "expenditure) x the deposit-taking HFC share (the XR-6 boundary puts them in E_BANK; without the proxy "
        "the share is the plan's banks-only figure, kept in the satellite); co-operative banks and deposit-"
        "taking NBFCs are private (D2-14); E_INSP x (life GVA "
        "weight x LIC share of life operating expenses + non-life weight x public+specialised share of "
        "non-life net premium earned); E_NBFC public = NAS 7.1A financial OS + CFC less the other public "
        "parts (residual, AIFIs and government NBFCs). Private = sub-sector total - public part. RTP "
        "latest vintage (2025-12-29 where present).",
    )
    for (acct, part), q in gos.items():
        if acct == "E_RBI":
            out.add(acct, "F_GOSC", part, q, key="f4a.rbi", role="anchored", tol_rel=0.01)
        else:
            out.add(acct, "F_GOSC", part, q, key="f4a.split", role="free", confidence="medium")

    sat.method(
        "fpp",
        "estimated",
        "fincorp F4a public/private GOS by FC sub-sector and the inputs of the split "
        "(same arithmetic as the F4a entries; memo for capital_financial, which has no FC CFC split).",
    )
    for (acct, part), q in gos.items():
        sat.add(f"gos.{acct.lower()}.{part}", q, key="fpp", account=acct, part=part, item="gos")
    for name, q in (
        ("ce_bank", ce_bank),
        ("ce_nbfc", ce_nbfc),
        ("ce_dt_nbfc_hfc", dt_ce),
        ("gva_bank", gva_bank),
        ("gva_nbfc", gva_nbfc),
        ("bank_public_share", bank_pub_share),
        ("bank_public_share_banks_only", bank_pub_share_banks_only),
        ("dt_profit_proxy", dt_op),
        ("insp_public_share", insp_pub_share),
        ("dt_share_nbfc", dt_share["nbfc"]),
        ("dt_share_hfc", dt_share["hfc"]),
    ):
        unit = "ratio" if "share" in name else "INR_crore"
        sat.add(f"input.{name}", q, key="fpp", unit=unit, account=None, part=None, item=name)
    return F4aResult(gos, dt_share)
