"""R4 / R5: interest between financial corporations and the other resident sectors, on the SNA basis
(deposits: bank interest + FISIM; loans: bank interest - FISIM), plus the RBI <-> bank flows of the RBI AR.

Method (plan s.2.5 with CROSS_REVIEW XR-5, XR-6, XR-13): FSF 2023-24 who-to-whom stocks (average of end-
March 2023 and 2024) x RTP 2023-24 rates give each bilateral position's bank interest; each lender's
positions are scaled to its RTP P&L interest income / expended, after removing what is written elsewhere
(government securities: R3a; RoW: rest_of_world R13/R14; RBI: RBI AR). A flow between E_BANK and E_NBFC is
computed once, from E_BANK's side. GG creditors (deposits, and the bank/NBFC bonds and loans FSF shows GG
holding) are written here too (R4; government's R7x does not take them: verifier V-FIN-4, government-29).
FISIM: NAS 1.13 (domestic part only; RoW FISIM has no SAM interest counterpart, XR-13); households' FISIM by
group = the households block's C4b entries (XR-5), grossed up for household producers' IC FISIM; NFCs' FISIM
by the reference-rate formula, with the user split net of NAS 8.15.1 GG IC in every industry it publishes."""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline.sam.blocks.fincorp.core import FC, HH, Out, Q, Reader, SatOut, qsum, shares
from pipeline.sam.blocks.fincorp.deps import ROW_INTEREST_IN, ROW_INTEREST_OUT, Deps
from pipeline.sam.blocks.fincorp.f4a import RBI_AR_VINTAGE, RBIAR, RTPB, RTPC, RTPN, fsf
from pipeline.sam.blocks.fincorp.govint import GovInt
from pipeline.sam.framework import BlockContext, SamError

S113 = "mospi_nas_2026_s1_13"
IND113 = {  # NAS 1.13 user industry -> NAS 7.1 industry code
    "agriculture_livestock_forestry_and_fishing": "agri",
    "mining_and_quarrying": "mining",
    "manufacturing": "manufacturing",
    "electricity_gas_water_supply_and_other_utility_services": "utilities",
    "construction": "construction",
    "trade_repair_hotels_and_restaurants": "trade_hotels",
    "transport_storage_communication_and_services_related_to_broa": "transport_comm",
    "real_estate_ownership_of_dwelling_and_professional_services": "real_estate_prof",
    "public_administration_and_defence": "public_admin",
    "other_services": "other_services",
}
# NAS 8.15.1 publishes GG IC for exactly these industries (their sum must equal its total, else the build stops):
# all of it sits inside 7.1A's public-sector IC and is taken out of the public-NFC user base (verifier V-FIN-1)
GG_IC = ("construction", "other_services", "public_admin", "utilities")
S8151 = "mospi_nas_2026_s8_15_1"
CP = {"HH": "hh", "E_NFPU": "nfc_pub", "E_NFPR": "nfc_pvt", "G_CEN": "gg_cen", "G_STA": "gg_sta"}
GOV_CRED = ("G_CEN", "G_STA")
OFC_SUB = {"E_NBFC": "nbfc", "E_INSP": "fc_ofc_icpf", "MF": "fc_ofc_mf"}


@dataclass
class Params:
    r_dep: Q  # SCB cost of deposits
    r_loan: Q  # SCB return on advances
    r_borr: Q  # SCB cost of borrowings (also corporate-bond coupon proxy, r_corp)
    r_inv: Q  # SCB return on investments
    r_star: Q  # FISIM reference rate (assumption record)


@dataclass
class Interest:
    hh_recv: dict[tuple[str, str], Q] = field(default_factory=dict)  # (R8a component, payer) -> household total
    hh_recv_fisim: dict[tuple[str, str], dict[str, Q]] = field(default_factory=dict)  # (comp, payer) -> group FISIM_D
    fisim_total: Q = Q(0.0)
    nii: Q = Q(0.0)


def _stock(rd: Reader, sec: str, side: str, inst: str, cp: str) -> Q:
    """FSF stock; sec 'nbfc' = fc_ofc less fc_ofc_icpf less fc_ofc_mf (NBFCs, HFCs, AIFIs, SFCs, SIDCs)."""
    if sec == "nbfc":
        return (
            fsf(rd, "fc_ofc", side, inst, cp)
            - fsf(rd, "fc_ofc_icpf", side, inst, cp)
            - fsf(rd, "fc_ofc_mf", side, inst, cp)
        )
    return fsf(rd, sec, side, inst, cp)


def _ofc_split(ctx: BlockContext, rd: Reader, side: str, inst: str, cp: str, allowed: tuple[str, ...]) -> dict[str, Q]:
    """Split an FSF counterparty 'fc_ofc' over OFC sub-sectors by the sub-sectors' own positions (clipped at 0)."""
    w = {}
    for acct in allowed:
        q = _stock(rd, OFC_SUB[acct], side, inst, cp)
        if q.v < 0:
            ctx.log(f"R4: FSF {OFC_SUB[acct]} {side} {inst} cp {cp} is negative ({q.v:,.0f}); weight set to 0")
            q = Q(0.0, q.p)
        w[acct] = q
    if qsum(w.values()).v <= 0:
        return {"E_NBFC": Q(1.0, frozenset().union(*(q.p for q in w.values())))}
    return shares(w)


def build_interest(
    ctx: BlockContext, rd: Reader, out: Out, sat: SatOut, deps: Deps, gi: GovInt, prm: Params, dt_share: dict[str, Q]
) -> Interest:
    res = Interest()
    # --- lender P&L totals (RTP 2023-24, latest vintage) ---------------------------------------------
    B = lambda s, src=RTPB: rd.v(src, s)  # noqa: E731
    nbfc_inc = B("rtp.nbfc_layer_pl.fund_based_income.nbfc_ul.current", RTPN) + B(
        "rtp.nbfc_layer_pl.fund_based_income.nbfc_ml.current", RTPN
    )
    nbfc_exp = B("rtp.nbfc_layer_pl.financial_expenditure.nbfc_ul.current", RTPN) + B(
        "rtp.nbfc_layer_pl.financial_expenditure.nbfc_ml.current", RTPN
    )
    hfc_inc, hfc_exp = (
        B("rtp.hfc_pl.fund_income.hfc.current", RTPN),
        B("rtp.hfc_pl.financial_expenditure.hfc.current", RTPN),
    )
    bank_inc = (
        qsum(
            [
                B("rtp.scb_pl.interest_income.scb.current"),
                B("rtp.rrb_pl.interest_income.rrb.current"),
                B("rtp.ucb_pl.interest_income.ucb.current", RTPC),
                B("rtp.stcb_pl.interest_income.stcb.current", RTPC),
                B("rtp.dccb_pl.interest_income.dccb.current", RTPC),
            ]
        )
        + dt_share["nbfc"] * nbfc_inc
        + dt_share["hfc"] * hfc_inc
    )
    bank_exp = (
        qsum(
            [
                B("rtp.scb_pl.interest_expended.scb.current"),
                B("rtp.rrb_pl.interest_expended.rrb.current"),
                B("rtp.ucb_pl.interest_expended.ucb.current", RTPC),
                B("rtp.stcb_pl.interest_expended.stcb.current", RTPC),
                B("rtp.dccb_pl.interest_expended.dccb.current", RTPC),
            ]
        )
        + dt_share["nbfc"] * nbfc_exp
        + dt_share["hfc"] * hfc_exp
    )
    ofc_inc = (
        (1.0 - dt_share["nbfc"]) * nbfc_inc
        + (1.0 - dt_share["hfc"]) * hfc_inc
        + B("rtp.aifi_pl.interest_income.aifi.current", RTPN)
        + B("rtp.spd_pl.interest_discount.spd.current", RTPN)
    )
    ofc_exp = (
        (1.0 - dt_share["nbfc"]) * nbfc_exp
        + (1.0 - dt_share["hfc"]) * hfc_exp
        + B("rtp.aifi_pl.interest_expended.aifi.current", RTPN)
        + B("rtp.spd_pl.interest_expended.spd.current", RTPN)
    )
    res.nii = bank_inc - bank_exp + ofc_inc - ofc_exp

    # --- RBI <-> banks (RBI AR Sch. 13 A): LAF/SDF paid by RBI; MSF and loans received ------------------
    ar = lambda s: rd.v(RBIAR, f"sch13.a.{s}.current", vintage=RBI_AR_VINTAGE)  # noqa: E731
    rbi_paid = -(ar("net_interest_on_laf_operations") + ar("interest_on_sdf"))
    if rbi_paid.v <= 0:
        raise SamError(
            "fincorp R4: RBI AR net LAF + SDF interest is not a payment by RBI this year; revisit the method"
        )
    msf = ar("interest_on_msf_operations")
    out.method(
        "r4.rbi",
        "R4",
        "derived",
        f"Gap map R4, RBI <-> banks from the RBI Annual Report {ctx.year} (vintage {RBI_AR_VINTAGE}) Sch. 13 A: "
        "net LAF and SDF interest (negative in RBI's income: RBI paid) to E_BANK; MSF interest from E_BANK; "
        "interest on RBI loans and advances less the Centre's WMA interest (written under R3a) by FSF RBI loan "
        "assets to ODCs / OFCs / States (the States' part is R3a).",
    )
    out.add("E_BANK", "E_RBI", "laf_sdf", rbi_paid, key="r4.rbi", role="anchored", tol_rel=0.05)
    out.add("E_RBI", "E_BANK", "msf", msf, key="r4.rbi", role="anchored", tol_rel=0.05)
    out.add("E_RBI", "E_BANK", "rbi_loans", gi.rbi_loans_by["E_BANK"], key="r4.rbi", role="anchored", tol_rel=0.05)
    out.add("E_RBI", "E_NBFC", "rbi_loans", gi.rbi_loans_by["E_NBFC"], key="r4.rbi", role="anchored", tol_rel=0.05)

    # --- what is written elsewhere and removed from the P&L totals ---------------------------------------
    r3a_non_mf = {
        h: qsum(
            i["q"]
            for i in out.items
            if out.methods[i["key"]].ref == "R3a" and i["row"] == h and i["comp"] != "mf_lookthrough"
        )
        for h in ("E_BANK", "E_NBFC")
    }
    row_in = {h: deps.row_sum(row=h, col="R_ROW", refs=("R13",), comps=ROW_INTEREST_IN) for h in ("E_BANK", "E_NBFC")}
    row_out = {h: deps.row_sum(row="R_ROW", col=h, refs=("R14",), comps=ROW_INTEREST_OUT) for h in ("E_BANK", "E_NBFC")}

    # --- positions: (creditor, debtor, instrument, stock, rate, scaling group) ---------------------------
    pos: list[dict] = []

    def add(cred: str, debt: str, inst: str, stock: Q, rate: Q, group: str) -> None:
        if stock.v < 0:
            ctx.log(f"R4/R5: FSF stock {cred}<-{debt} {inst} negative ({stock.v:,.0f}); dropped")
            return
        if stock.v > 0:
            pos.append(dict(cred=cred, debt=debt, inst=inst, stock=stock, rate=rate, group=group))

    inst_rate = {
        "deposits": prm.r_dep,
        "borrowings": prm.r_borr,
        "bonds": prm.r_borr,
        "loans": prm.r_loan,
        "nongov_bonds": prm.r_inv,
    }
    fsf_inst = {"deposits": "f22_f29", "borrowings": "f4", "bonds": "f3", "loans": "f4", "nongov_bonds": "f3"}
    # E_BANK as debtor (deposits, borrowings, bonds), including GG as creditor: government's R7x books only fiscal
    # cash lines from non-financial payers (government-29), so the interest on GG's FSF holdings of bank bonds and
    # borrowings is written here (verifier V-FIN-4)
    for inst in ("deposits", "borrowings", "bonds"):
        f = fsf_inst[inst]
        for acct, cp in CP.items():
            add(acct, "E_BANK", inst, fsf(rd, "fc_odc", "liabilities", f, cp), inst_rate[inst], "bank_exp")
    # OFC claims on E_BANK: the ODC-side total over the three instruments, split over OFC sub-sectors and
    # instruments by the creditors' own FSF claims on ODCs (fincorp-4). The two sides agree in total (ODC 29.6 lakh,
    # OFC 31.3 lakh) but classify differently: ODCs report 18.5 lakh of 'borrowings' from OFCs that OFCs report as
    # deposits and CDs (MFs alone hold 10.3 lakh of ODC debt securities). Split instrument by instrument on the
    # ODC side, all the 'borrowings' fell to NBFCs (1.63 lakh of interest, more than AIFIs' whole interest income
    # of ~1.04 lakh; NBFCs, HFCs and SPDs are net borrowers from banks)
    odc_ofc = {
        inst: fsf(rd, "fc_odc", "liabilities", fsf_inst[inst], "fc_ofc") for inst in ("deposits", "borrowings", "bonds")
    }
    odc_total = qsum(odc_ofc.values())
    claims: dict[tuple[str, str], Q] = {}
    for acct in ("E_NBFC", "E_INSP", "MF"):
        for inst in ("deposits", "borrowings", "bonds"):
            q = _stock(rd, OFC_SUB[acct], "assets", fsf_inst[inst], "fc_odc")
            if q.v < 0:
                ctx.log(f"R4: FSF {OFC_SUB[acct]} assets {inst} on fc_odc negative ({q.v:,.0f}); weight set to 0")
                q = Q(0.0, q.p)
            claims[(acct, inst)] = q
    claims_total = qsum(claims.values())
    if claims_total.v <= 0:
        raise SamError("fincorp R4: OFC sub-sectors report no claims on ODCs (FSF)")
    ctx.log(
        "R4: OFC claims on E_BANK: ODC side "
        + ", ".join(f"{k} {q.v:,.0f}" for k, q in odc_ofc.items())
        + f" (total {odc_total.v:,.0f}); OFC side total {claims_total.v:,.0f}; split by the creditors' mix"
    )
    for (acct, inst), q in claims.items():
        add(acct, "E_BANK", inst, odc_total * q / claims_total, inst_rate[inst], "bank_exp")
    # E_BANK as creditor (loans, non-government bonds); government debtors are R3a
    for inst in ("loans", "nongov_bonds"):
        f = fsf_inst[inst]
        for acct in ("HH", "E_NFPU", "E_NFPR"):
            add("E_BANK", acct, inst, fsf(rd, "fc_odc", "assets", f, CP[acct]), inst_rate[inst], "bank_inc")
        stock = fsf(rd, "fc_odc", "assets", f, "fc_ofc")
        for acct, s in _ofc_split(ctx, rd, "liabilities", f, "fc_odc", ("E_NBFC", "E_INSP")).items():
            add("E_BANK", acct, inst, stock * s, inst_rate[inst], "bank_inc")
    # E_NBFC as creditor of non-FC borrowers
    for inst in ("loans", "nongov_bonds"):
        for acct in ("HH", "E_NFPU", "E_NFPR"):
            add(
                "E_NBFC",
                acct,
                inst,
                _stock(rd, "nbfc", "assets", fsf_inst[inst], CP[acct]),
                inst_rate[inst],
                "nbfc_inc",
            )
    # E_NBFC as debtor of non-bank creditors, GG included (FSF: the Centre holds AIFI and NBFC bonds, both
    # governments lend to NBFCs; verifier V-FIN-4)
    for inst in ("deposits", "borrowings", "bonds"):
        f = fsf_inst[inst]
        for acct in ("HH", "E_NFPU", "E_NFPR", *GOV_CRED):
            add(acct, "E_NBFC", inst, _stock(rd, "nbfc", "liabilities", f, CP[acct]), inst_rate[inst], "nbfc_exp")
        stock = _stock(rd, "nbfc", "liabilities", f, "fc_ofc")
        for acct, s in _ofc_split(ctx, rd, "assets", f, "fc_ofc", ("E_NBFC", "E_INSP", "MF")).items():
            if acct != "E_NBFC":  # NBFC <- NBFC is inside one account: dropped
                add(acct, "E_NBFC", inst, stock * s, inst_rate[inst], "nbfc_exp")
    # insurers' and mutual funds' claims on households / NFCs (unscaled: no separable P&L interest line)
    # corporate bonds held by insurers/PFs and MFs earn r_corp (the coupon proxy also used for NPS's corporate
    # bonds in R9c), not the SCB return on investments (a G-sec-dominated yield used only as a scaling weight)
    unscaled_rate = {"loans": prm.r_loan, "nongov_bonds": prm.r_borr}
    for cred, sec in (("E_INSP", "fc_ofc_icpf"), ("MF", "fc_ofc_mf")):
        for inst in ("loans", "nongov_bonds"):
            for acct in ("HH", "E_NFPU", "E_NFPR"):
                add(cred, acct, inst, fsf(rd, sec, "assets", fsf_inst[inst], CP[acct]), unscaled_rate[inst], "unscaled")

    # --- scale each group to its P&L total ------------------------------------------------------------
    def base(group: str) -> Q:
        return qsum(p["stock"] * p["rate"] for p in pos if p["group"] == group)

    bank_to_nbfc = lambda: qsum(p["amount"] for p in pos if p["group"] == "bank_exp" and p["cred"] == "E_NBFC")  # noqa: E731
    nbfc_to_bank = lambda: qsum(p["amount"] for p in pos if p["group"] == "bank_inc" and p["debt"] == "E_NBFC")  # noqa: E731
    targets = {
        "bank_inc": bank_inc - r3a_non_mf["E_BANK"] - rbi_paid - row_in["E_BANK"],
        "bank_exp": bank_exp - msf - gi.rbi_loans_by["E_BANK"] - row_out["E_BANK"],
    }
    scale: dict[str, Q] = {}
    for g in ("bank_inc", "bank_exp"):
        if targets[g].v <= 0:
            raise SamError(f"fincorp R4/R5: adjusted {g} total is {targets[g].v:,.0f}")
        scale[g] = targets[g] / base(g)
        for p in pos:
            if p["group"] == g:
                p["amount"] = p["stock"] * p["rate"] * scale[g]
    targets["nbfc_inc"] = ofc_inc - r3a_non_mf["E_NBFC"] - row_in["E_NBFC"] - bank_to_nbfc()
    targets["nbfc_exp"] = ofc_exp - gi.rbi_loans_by["E_NBFC"] - row_out["E_NBFC"] - nbfc_to_bank()
    for g in ("nbfc_inc", "nbfc_exp"):
        if targets[g].v <= 0:
            raise SamError(f"fincorp R4/R5: adjusted {g} total is {targets[g].v:,.0f}")
        scale[g] = targets[g] / base(g)
        for p in pos:
            if p["group"] == g:
                p["amount"] = p["stock"] * p["rate"] * scale[g]
    for p in pos:
        if p["group"] == "unscaled":
            p["amount"] = p["stock"] * p["rate"]
    for g, s in scale.items():
        ctx.log(f"R4/R5: {g} P&L-adjusted {targets[g].v:,.0f}, scale on stock x rate {s.v:.3f}")

    # --- FISIM (domestic; NAS 1.13) -------------------------------------------------------------------
    fis = {k: rd.v(S113, f"s1_13.{k}.current") for k in IND113}
    ic_fisim = rd.v(S113, "s1_13.allocation_of_fisim_as_ic_to_user_industry.current")
    pfce_fisim = rd.v(S113, "s1_13.private_final_consumption_expenditure.current")
    ctx.check(
        "fisim.ic_industries_add_up",
        "NAS 1.13 FISIM by user industry vs its IC total",
        qsum(fis.values()).v,
        ic_fisim.v,
        target_prov_id=next(iter(ic_fisim.p)),
        tol_abs=1.0,
    )
    # GG IC (NAS 8.15.1) by industry: every industry it publishes is taken out of 7.1A's public-sector IC
    gg_ic = {code: rd.v(S8151, f"s8_15_1.{code}.ic.current") for code in GG_IC}
    gg_ic_total = rd.v(S8151, "s8_15_1.total.ic.current")
    if abs(qsum(gg_ic.values()).v - gg_ic_total.v) > 1.0:
        raise SamError(
            f"fincorp FISIM: NAS 8.15.1 GG IC of {GG_IC} sums to {qsum(gg_ic.values()).v:,.2f}, not its total "
            f"{gg_ic_total.v:,.2f}: 8.15.1 publishes another industry; add it to interest.GG_IC"
        )
    missing = sorted(set(GG_IC) - set(IND113.values()))
    if missing:
        raise SamError(f"fincorp FISIM: 8.15.1 GG IC industries {missing} are not NAS 1.13 user industries")
    user = {"E_NFPU": Q(0.0), "E_NFPR": Q(0.0), "HH": Q(0.0)}
    for k, code in IND113.items():
        if fis[k].v == 0:
            continue
        ic_a = rd.v("mospi_nas_2026_s7_1a", f"s7_1a.{code}.ic.current")
        if code in gg_ic:
            ic_a = ic_a - gg_ic[code]
            if ic_a.v < 0:
                raise SamError(f"fincorp FISIM: 7.1A IC less 8.15.1 GG IC is negative for {code} ({ic_a.v:,.2f})")
        ic = {
            "E_NFPU": ic_a,
            "E_NFPR": rd.v("mospi_nas_2026_s7_1b", f"s7_1b.{code}.ic.current"),
            "HH": rd.v("mospi_nas_2026_s7_1c", f"s7_1c.{code}.ic.current"),
        }
        for s, sh in shares(ic).items():
            user[s] = user[s] + fis[k] * sh
    hh_c4b_total = qsum(deps.c4b_fisim["fisim_deposits"].values()) + qsum(deps.c4b_fisim["fisim_loans"].values())
    if abs(hh_c4b_total.v - pfce_fisim.v) > 1.0:
        ctx.warn(
            f"FISIM: households' C4b FISIM ({hh_c4b_total.v:,.2f}) differs from NAS 1.13 PFCE FISIM "
            f"({pfce_fisim.v:,.2f})"
        )
    gross_up = 1.0 + user["HH"] / hh_c4b_total  # household producers' IC FISIM, spread like consumers' FISIM
    fisim_hh = {c: {g: q * gross_up for g, q in deps.c4b_fisim[c].items()} for c in ("fisim_deposits", "fisim_loans")}
    fisim_nfc: dict[tuple[str, str], Q] = {}  # (sector, 'D'|'L') -> FISIM
    for s in ("E_NFPU", "E_NFPR"):
        loans = qsum(
            p["stock"] for p in pos if p["debt"] == s and p["inst"] == "loans" and p["cred"] in ("E_BANK", "E_NBFC")
        )
        deps_ = qsum(
            p["stock"] for p in pos if p["cred"] == s and p["inst"] == "deposits" and p["debt"] in ("E_BANK", "E_NBFC")
        )
        wl, wd = (prm.r_loan - prm.r_star) * loans, (prm.r_star - prm.r_dep) * deps_
        fisim_nfc[(s, "L")] = user[s] * wl / (wl + wd)
        fisim_nfc[(s, "D")] = user[s] * wd / (wl + wd)
    res.fisim_total = qsum(user.values()) + hh_c4b_total
    ctx.check(
        "fisim.domestic_total",
        "FISIM allocated in R4/R5/R8a (households + NFCs) vs NAS 1.13 IC + PFCE FISIM (RoW FISIM excluded, XR-13)",
        res.fisim_total.v,
        (ic_fisim + pfce_fisim).v,
        target_prov_id=next(iter(pfce_fisim.p)),
        tol_abs=1.0,
    )

    split_log: dict[tuple[str, str], dict[str, Q]] = {}

    def lender_split(side: str, sector: str) -> dict[str, Q]:
        """Share of each lender (E_BANK / E_NBFC) in a user's FISIM on deposits (side 'D') or loans ('L'): the
        reference-rate margin of each lender's position, SNA 2008 6.166: loans (interest - r* x stock), deposits
        (r* x stock - interest), with each lender's interest as scaled to its P&L (fincorp-2: the earlier key, bank-
        interest shares, ignored that NBFCs lend at a far wider margin over r* than banks). A lender with a
        negative margin gets no FISIM; if neither has a positive margin, interest shares are used (logged)."""
        inst, cred_is_user = ("deposits", True) if side == "D" else ("loans", False)
        interest: dict[str, Q] = {}
        margin: dict[str, Q] = {}
        for lend in ("E_BANK", "E_NBFC"):
            ps = [
                p
                for p in pos
                if p["inst"] == inst
                and ((p["cred"], p["debt"]) == ((sector, lend) if cred_is_user else (lend, sector)))
            ]
            amt, stock = qsum(p["amount"] for p in ps), qsum(p["stock"] for p in ps)
            m = (prm.r_star * stock - amt) if side == "D" else (amt - prm.r_star * stock)
            interest[lend], margin[lend] = amt, (m if m.v > 0 else Q(0.0, m.p))
        if qsum(margin.values()).v > 0:
            out_ = shares(margin)
        else:
            ctx.log(f"FISIM: no positive reference-rate margin for {sector} {side}; lender split by interest shares")
            out_ = shares(interest)
        split_log[(sector, side)] = out_
        return out_

    # --- entries -----------------------------------------------------------------------------------------
    out.method(
        "r4.fc",
        "R4",
        "estimated",
        "Gap map R4 (plan s.2.5): interest paid by E_BANK (FSF ODC incl. co-op banks and deposit-taking "
        "NBFCs/HFCs, XR-6) and E_NBFC on deposits, borrowings and bonds, by creditor: FSF 2023-24 who-to-whom "
        "stocks (average end-March 2023/2024) x RTP 2023-24 SCB cost of deposits / cost of borrowings, scaled "
        "to each lender's RTP P&L interest expended (SCBs, RRBs, UCBs, StCBs, DCCBs; NBFC-UL/ML interest "
        "financial expenditure (the narrower interest-payment line is too small for their FSF debt), HFC "
        "financial expenditure, AIFIs, SPDs; deposit-taking NBFC/HFC share by FSF loans) less interest to RBI "
        "(RBI AR), to RoW (rest_of_world R14 NRI-deposit and other-investment interest) and, for E_NBFC, to "
        "E_BANK (computed on E_BANK's "
        "side). OFC counterparties are split into NBFCs, insurers/PFs and mutual funds by the sub-sectors' FSF "
        "positions; mutual funds are looked through to unit holders (SEBI T72). Creditors include the Centre "
        "and the States (G_CEN, G_STA): their FSF deposits with ODCs, and their holdings of bank and NBFC/AIFI "
        "bonds and loans to banks and NBFCs (government's R7x books only fiscal cash lines from non-financial "
        "payers, government-29), all low confidence. SNA basis: deposit interest "
        "of NFCs includes FISIM on deposits (reference-rate split of NAS 1.13 IC FISIM, r* recorded); no "
        "FISIM on government or inter-FC positions (NAS 1.13).",
    )
    out.method(
        "r5.fc",
        "R5",
        "estimated",
        "Gap map R5 (plan s.2.5): interest received by E_BANK and E_NBFC on loans and non-government bonds "
        "from NFCs and household groups: FSF stocks x RTP SCB return on advances / return on investments, "
        "scaled to each lender's RTP P&L interest income less government-securities interest (R3a), RBI "
        "(RBI AR), RoW (rest_of_world R13 other-investment income) and, for E_NBFC, interest from E_BANK. "
        "E_INSP (policy and other "
        "loans, corporate bonds; FSF ICPF stocks x the same rates, unscaled). SNA basis: less FISIM on loans "
        "(NFCs: NAS 1.13 IC FISIM by user sector (IC shares of 7.1A less NAS 8.15.1 GG IC in every industry "
        "8.15.1 publishes (construction, other services, public administration, utilities) / 7.1B / 7.1C per "
        "industry) split "
        "deposits/loans by (r_L - r*)L and (r* - r_D)D; households: the households block's C4b "
        "`fisim_loans` by group, grossed up for household producers' IC FISIM). Household groups by "
        "hh_keys `aidis_inst_loans`.",
    )
    out.method(
        "r8.mf_nfc",
        "R8",
        "estimated",
        "Interest on NFC bonds held by mutual funds, looked through to corporate unit holders (E_NFPR; SEBI T72 "
        "'corporates'): an NFC <- NFC interest flow that no gap-map ref owns (CROSS_REVIEW XR-29); filed under "
        "R8 (distributed income between corporations) as the review proposes. FSF MF holdings x the corporate "
        "coupon parameter (RBI RTP 2023-24 SCB cost of borrowings; fincorp-30, fincorp-36: this text said the SCB "
        "return on investments, which the code stopped using in fincorp-30).",
    )
    flows: dict[tuple[str, str, str], Q] = {}
    for p in pos:
        holders = gi.mf_share.items() if p["cred"] == "MF" else [(p["cred"], Q(1.0))]
        for h, s in holders:
            comp = "mf_lookthrough" if p["cred"] == "MF" else p["inst"]
            k = (h, p["debt"], comp)
            flows[k] = flows.get(k, Q(0.0)) + p["amount"] * s

    fisim_d_total, fisim_l_total = Q(0.0), Q(0.0)
    fisim_by_lender = {"E_BANK": Q(0.0), "E_NBFC": Q(0.0)}
    for (cred, debt, comp), q in sorted(flows.items()):
        if cred == "HH":
            continue  # households' receipts: R8a (below, with FISIM by group)
        if debt == "HH":
            continue  # households' payments: R5 by group (below)
        if cred == debt and cred in ("E_NFPR", "E_NFPU"):
            out.add(cred, debt, "interest_mf_lookthrough", q, key="r8.mf_nfc", role="free", confidence="low")
            continue
        if cred in ("E_NFPU", "E_NFPR") and debt in ("E_NFPU", "E_NFPR"):
            out.add(cred, debt, "interest_mf_lookthrough", q, key="r8.mf_nfc", role="free", confidence="low")
            continue
        sna = q
        if cred in ("E_NFPU", "E_NFPR") and comp == "deposits" and debt in ("E_BANK", "E_NBFC"):
            f = fisim_nfc[(cred, "D")] * lender_split("D", cred)[debt]
            sna, fisim_d_total = q + f, fisim_d_total + f
            fisim_by_lender[debt] = fisim_by_lender[debt] + f
        if debt in ("E_NFPU", "E_NFPR") and comp == "loans" and cred in ("E_BANK", "E_NBFC"):
            f = fisim_nfc[(debt, "L")] * lender_split("L", debt)[cred]
            sna, fisim_l_total = q - f, fisim_l_total + f
            fisim_by_lender[cred] = fisim_by_lender[cred] + f
        if sna.v <= 0:
            raise SamError(f"fincorp R5: SNA interest {cred}<-{debt} [{comp}] is {sna.v:,.0f} after FISIM")
        ref_key = "r4.fc" if debt in FC else "r5.fc"
        # GG as creditor is low: the GG-held deposit interest may overlap government's R7x States' interest and
        # SAM GG income exceeds NAS (government-1, -26; V-FIN-7); GG-held bonds/borrowings rest on FSF alone (V-FIN-4)
        conf = "low" if comp == "mf_lookthrough" or cred == "E_INSP" or cred in GOV_CRED else "medium"
        out.add(cred, debt, comp, sna, key=ref_key, role="free", confidence=conf)

    # households as borrowers: R5 by group (interest x aidis_inst_loans key - FISIM_L by group)
    key_loans = shares(deps.key("aidis_inst_loans"))
    for lender in ("E_BANK", "E_NBFC", "E_INSP"):
        q = qsum(v for (c, d, comp), v in flows.items() if c == lender and d == "HH")
        split_l = lender_split("L", "HH")[lender] if lender in ("E_BANK", "E_NBFC") else Q(0.0)
        for g in HH:
            f = fisim_hh["fisim_loans"][g] * split_l
            v = q * key_loans[g] - f
            if v.v <= 0:
                raise SamError(f"fincorp R5: {lender}<-{g} SNA interest {v.v:,.0f} after FISIM (key mismatch)")
            fisim_l_total = fisim_l_total + f
            if lender in fisim_by_lender:
                fisim_by_lender[lender] = fisim_by_lender[lender] + f
            out.add(lender, g, "loans", v, key="r5.fc", role="free", confidence="low")
    # households as creditors: R8a totals by (component, payer) handed to assemble (with FISIM_D by group)
    for (cred, debt, comp), q in sorted(flows.items()):
        if cred != "HH":
            continue
        rcomp = {
            "deposits": "deposits_bank" if debt == "E_BANK" else "deposits_nbfc",
            "bonds": "debentures",
            "borrowings": "debentures",
            "mf_lookthrough": "mf_lookthrough",
        }.get(comp, comp)
        key = (rcomp, debt)
        res.hh_recv[key] = res.hh_recv.get(key, Q(0.0)) + q
        if comp == "deposits":
            fd = {g: fisim_hh["fisim_deposits"][g] * lender_split("D", "HH")[debt] for g in HH}
            res.hh_recv_fisim[key] = fd
            fisim_d_total = fisim_d_total + qsum(fd.values())
            fisim_by_lender[debt] = fisim_by_lender[debt] + qsum(fd.values())
    ctx.check(
        "fisim.written_total",
        "FISIM written (deposit adjustments added + loan adjustments removed) vs NAS 1.13 IC + PFCE FISIM",
        (fisim_d_total + fisim_l_total).v,
        (ic_fisim + pfce_fisim).v,
        target_prov_id=next(iter(ic_fisim.p)),
        tol_abs=1.0,
    )

    # --- FC net SNA interest (plan T17 diagnostic, reported): banks + NBFCs, received - paid ------------------
    lenders = ("E_BANK", "E_NBFC")
    sna_recv = (
        qsum(p["amount"] for p in pos if p["cred"] in lenders)
        - fisim_l_total
        + qsum(r3a_non_mf.values())
        + rbi_paid
        + qsum(row_in.values())
    )
    sna_paid = (
        qsum(p["amount"] for p in pos if p["debt"] in lenders)
        + fisim_d_total
        + msf
        + gi.rbi_loans_by["E_BANK"]
        + gi.rbi_loans_by["E_NBFC"]
        + qsum(row_out.values())
    )
    ctx.log(
        f"R4/R5: banks' + NBFCs' net SNA interest {(sna_recv - sna_paid).v:,.0f} vs RTP NII - domestic FISIM "
        f"{(res.nii - res.fisim_total).v:,.0f} (NII {res.nii.v:,.0f}); equal by construction of the P&L scaling"
    )

    # --- satellite interest_fisim_bridge -------------------------------------------------------------------
    sat.method(
        "ifb",
        "estimated",
        "fincorp R4/R5 interest matrix: FSF positions (average end-March 2023/2024), "
        "rates, bank interest, lender P&L totals and adjustments, scale factors, FISIM by user sector.",
    )
    for p in pos:
        base_id = f"pos.{p['cred'].lower()}.{p['debt'].lower()}.{p['inst']}"
        sat.add(
            f"{base_id}.stock",
            p["stock"],
            key="ifb",
            creditor=p["cred"],
            debtor=p["debt"],
            item=p["inst"],
            measure="stock",
        )
        sat.add(
            f"{base_id}.bank_interest",
            p["amount"],
            key="ifb",
            creditor=p["cred"],
            debtor=p["debt"],
            item=p["inst"],
            measure="bank_interest",
        )
    for name, q in (
        ("pl.bank_interest_income", bank_inc),
        ("pl.bank_interest_expended", bank_exp),
        ("pl.nbfc_interest_income", ofc_inc),
        ("pl.nbfc_interest_expended", ofc_exp),
        ("pl.net_interest_income", res.nii),
        ("diag.fc_net_sna_interest", sna_recv - sna_paid),
        ("adj.rbi_paid_to_banks", rbi_paid),
        ("adj.msf", msf),
        ("adj.r3a_bank", r3a_non_mf["E_BANK"]),
        ("adj.r3a_nbfc", r3a_non_mf["E_NBFC"]),
        ("adj.row_in_bank", row_in["E_BANK"]),
        ("adj.row_in_nbfc", row_in["E_NBFC"]),
        ("adj.row_out_bank", row_out["E_BANK"]),
        ("adj.row_out_nbfc", row_out["E_NBFC"]),
        *((f"target.{g}", q) for g, q in targets.items()),
        ("fisim.ic_households", user["HH"]),
        ("fisim.ic_nfc_public", user["E_NFPU"]),
        ("fisim.ic_nfc_private", user["E_NFPR"]),
        ("fisim.pfce", pfce_fisim),
        ("fisim.household_grossup", Q(gross_up.v - 1.0, gross_up.p)),
        *((f"fisim.{s.lower()}.{side}", q) for (s, side), q in fisim_nfc.items()),
    ):
        unit = "ratio" if name == "fisim.household_grossup" else "INR_crore"
        sat.add(name, q, key="ifb", unit=unit, creditor=None, debtor=None, item=name, measure="total")
    for g, s in scale.items():
        sat.add(f"scale.{g}", s, key="ifb", unit="ratio", creditor=None, debtor=None, item=g, measure="scale")
    for lend, q in fisim_by_lender.items():
        sat.add(
            f"fisim.by_lender.{lend.lower()}", q, key="ifb", creditor=lend, debtor=None, item="fisim", measure="total"
        )
    for (sector, side), sh in sorted(split_log.items()):
        for lend, q in sh.items():
            sat.add(
                f"fisim.lender_share.{sector.lower()}.{side}.{lend.lower()}",
                q,
                key="ifb",
                unit="ratio",
                creditor=lend,
                debtor=sector,
                item=f"fisim_{side}",
                measure="lender_share",
            )
    for (acct, inst), q in sorted(claims.items()):
        sat.add(
            f"ofc_claims_on_odc.{acct.lower()}.{inst}",
            q,
            key="ifb",
            creditor=acct,
            debtor="E_BANK",
            item=inst,
            measure="ofc_side_stock",
        )
    for inst, q in odc_ofc.items():
        sat.add(
            f"odc_liab_to_ofc.{inst}",
            q,
            key="ifb",
            creditor="OFC",
            debtor="E_BANK",
            item=inst,
            measure="odc_side_stock",
        )
    ctx.log(
        "FISIM by lender (reference-rate lender split): "
        + ", ".join(f"{k} {q.v:,.0f}" for k, q in fisim_by_lender.items())
    )
    return res
