"""R9c (D44: investment income attributed to policyholders and PF/pension members), R17 (net non-life
premiums and claims) and satellite S9 (gross flows of funded schemes). Plan s.2.8, 2.9, 2.12."""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline.sam.blocks.fincorp.core import HH, Out, Q, Reader, SatOut, qsum, shares
from pipeline.sam.blocks.fincorp.deps import Deps
from pipeline.sam.blocks.fincorp.f4a import ENDS, IRL, IRN, fsf
from pipeline.sam.blocks.fincorp.govint import GovInt
from pipeline.sam.framework import BlockContext, SamError

EPFO, EPFO_V = "finsector_markets_epfo_ar", "2024-12"  # EPFO Annual Report 2023-24 (plan C11)
NPS, NPSG = "finsector_markets_pfrda_nps", "finsector_markets_pfrda_sg"
SUMM = "finsector_markets_irdai_summary"
LINES = ("motor", "health", "fire", "marine", "others")
NL_GROUPS = ("general_private", "general_public", "general_specialized", "health_standalone")
# R17 payer split by line: share paid by households (assumption parameters, plan s.2.9 step 4; see the record)
HH_SHARE = {"motor": 0.70, "health": 0.55, "fire": 0.10, "marine": 0.0, "others": 0.30}
NPS_SECTORS = {
    "public": ("central_govt", "state_govt"),
    "private": ("corporate", "all_citizen", "tier2", "tier2_tax_saver"),
    "low_income": ("apy", "nps_lite"),
}


@dataclass
class D44:
    by_scheme: dict[str, Q] = field(default_factory=dict)


def _key(levels: dict[str, Q]) -> dict[str, Q]:
    return shares({g: (q if q.v > 0 else Q(0.0, q.p)) for g, q in levels.items()})


def build_r9c(
    ctx: BlockContext,
    rd: Reader,
    out: Out,
    sat: SatOut,
    deps: Deps,
    gi: GovInt,
    r_corp: Q,
    div_yield: Q,
    eps_rate_pid: str,
) -> D44:
    d = D44()
    life = rd.v(IRL, "t24.inv_interest_dividends_rent_gross.insurers_life.current") + rd.v(
        IRL, "t24.inv_amortisation.insurers_life.current"
    )
    rate = rd.pct(EPFO, "app5vii.epf_interest_rate", vintage=EPFO_V)
    epf_stock = rd.avg(EPFO, "invest.epf.total.current", ENDS, vintage=EPFO_V)
    eps_stock = rd.avg(EPFO, "invest.eps.total.current", ENDS, vintage=EPFO_V)
    eps_rate = Q(rate.v, frozenset({eps_rate_pid}))
    nps_bonds = rd.avg(NPS, "m6.aum_by_asset_class.corporate_bonds.current", ENDS)
    nps_equity = rd.avg(NPS, "m6.aum_by_asset_class.equity.current", ENDS)
    nps_aum = rd.avg(NPS, "m6.aum_by_asset_class.total.current", ENDS)
    nps_gsec = qsum(q for (c, g), q in gi.by_cat.items() if c == "pension_funds")
    d.by_scheme = {
        "life": life,
        "epf": epf_stock * rate,
        "eps": eps_stock * eps_rate,
        "nps": nps_gsec + nps_bonds * r_corp + nps_equity * div_yield,
        "gpf_union": gi.gpf_union,
        "gpf_states": gi.gpf_states,
    }
    pf_stock = fsf(rd, "fc_ofc_icpf_pf", "liabilities", "f6", "all")
    exempt_stock = pf_stock - epf_stock - eps_stock - nps_aum
    if exempt_stock.v > 0:
        d.by_scheme["exempted_pf"] = exempt_stock * eps_rate
    else:
        ctx.warn(f"R9c: FSF PF entitlements less EPF, EPS and NPS is {exempt_stock.v:,.0f}: no exempted-PF D44 written")

    # keys: private regular wages = F1a F_LREG less the public-sector wage key (floored at 0 per group)
    priv = {g: deps.wage_regular[g] - deps.wage_public[g] for g in HH}
    for g, q in priv.items():
        if q.v < 0:
            ctx.log(f"R9c: public-sector wage key exceeds F_LREG wages in {g}; private key floored at 0")
    k_priv, k_pub = _key(priv), _key(deps.wage_public)
    pop = deps.key("pop_persons")
    k_low = _key({g: (pop[g] if g[-1] in "123" else Q(0.0, pop[g].p)) for g in HH})
    k_life = _key(deps.key("aidis_fin_assets"))
    contrib = {s: qsum(rd.v(NPS, f"m4d.annual_contribution.{c}.current") for c in cs) for s, cs in NPS_SECTORS.items()}
    nps_key = {s: c / qsum(contrib.values()) for s, c in contrib.items()}

    out.method(
        "r9c.gpf_union",
        "R9c",
        "estimated",
        "Gap map R9c: Union interest credited to GPF (Finance Accounts 2023-24 MH 2049.03.104 'interest on State "
        "Provident Funds', i.e. the Union's GPF, official) split over household groups by factors' estimated "
        "public-sector wage key; the groups are estimates (free, medium) and the published total is held by the "
        "constraint r9c.gpf_union (verifier V-FIN-2).",
    )
    out.method(
        "r9c.est",
        "R9c",
        "estimated",
        "Gap map R9c (plan s.2.8; the RBI AR has no policyholder income): life = IRDAI 2023-24 policyholders' "
        "account interest, dividends and rent (gross) + amortisation (holding gains excluded), key hh_keys "
        "aidis_fin_assets; EPF = average EPF investments (EPFO AR 2023-24, end-March 2023/2024) x the declared "
        "rate; EPS = average EPS investments x the EPF rate (assumption record: EPS is defined-benefit); "
        "exempted PFs = FSF PF entitlements less EPF, EPS and NPS assets x the EPF rate; EPF/EPS/exempted keyed "
        "by private regular wages (factors F1a F_LREG less the public-sector wage key); NPS = pension funds' "
        "government-securities interest (R3a T107 'pension funds') + corporate bonds x SCB cost of borrowings "
        "+ equity x the market dividend yield (R8 dividends / NSE market capitalisation), split by 2023-24 "
        "contributions: government sectors by the "
        "public-sector wage key, corporate/all-citizen/tier II by private regular wages, APY/NPS-lite by "
        "persons in the bottom three quintiles; State PF (RBI SF App. II 'interest on small savings, State PF', "
        "all treated as State PF) by the public-sector key. PPF interest is R8a, not here; the non-life premium "
        "supplement is R17.",
    )
    for scheme, q in d.by_scheme.items():
        if scheme == "nps":
            parts = {
                g: q
                * (nps_key["public"] * k_pub[g] + nps_key["private"] * k_priv[g] + nps_key["low_income"] * k_low[g])
                for g in HH
            }
        else:
            key = {
                "life": k_life,
                "epf": k_priv,
                "eps": k_priv,
                "exempted_pf": k_priv,
                "gpf_union": k_pub,
                "gpf_states": k_pub,
            }[scheme]
            parts = {g: q * key[g] for g in HH}
        col = {"gpf_union": "G_CEN", "gpf_states": "G_STA"}.get(scheme, "E_INSP")
        for g, v in parts.items():
            if scheme == "gpf_union":
                out.add(g, col, scheme, v, key="r9c.gpf_union", role="free", confidence="medium")
            else:
                conf = "medium" if scheme in ("life", "epf", "gpf_states") else "low"
                out.add(g, col, scheme, v, key="r9c.est", role="free", confidence=conf)
    sat.method(
        "d44", "estimated", "fincorp R9c D44 by scheme, the stocks and rates behind each, and the NPS contribution key."
    )
    for scheme, q in d.by_scheme.items():
        sat.add(f"d44.{scheme}", q, key="d44", scheme=scheme, item="d44")
    for name, q, unit in (
        ("stock.epf", epf_stock, "INR_crore"),
        ("stock.eps", eps_stock, "INR_crore"),
        ("stock.nps_aum", nps_aum, "INR_crore"),
        ("stock.exempted_pf", exempt_stock, "INR_crore"),
        ("rate.epf", rate, "ratio"),
        ("nps.gsec_interest", nps_gsec, "INR_crore"),
        *((f"nps.key.{s}", q, "ratio") for s, q in nps_key.items()),
    ):
        sat.add(name, q, key="d44", unit=unit, scheme=name.split(".")[1], item=name)
    return d


def build_r17(ctx: BlockContext, rd: Reader, out: Out, deps: Deps, split_pid: str) -> dict[str, Q]:
    t44 = "t44.{}.{}.insurers_general_direct.current"
    claims = {ln: rd.v(IRN, t44.format("claims_incurred_net", ln)) for ln in LINES}
    npe = {ln: rd.v(IRN, t44.format("net_premium_earned", ln)) for ln in LINES}
    tot_claims = rd.v(IRN, t44.format("claims_incurred_net", "total"))
    ctx.check(
        "r17.claims_lines_add_up",
        "IRDAI net claims by line vs the published total",
        qsum(claims.values()).v,
        tot_claims.v,
        target_prov_id=next(iter(tot_claims.p)),
        tol_abs=1.0,
    )
    supp = rd.v(SUMM, "sum_c.investment_income.current") - qsum(
        rd.v(IRN, f"t51.inv_interest_dividend_rent_gross.{g}.current") for g in NL_GROUPS
    )
    if supp.v <= 0:
        raise SamError(f"fincorp R17: premium supplement is {supp.v:,.2f}")
    service = qsum(npe.values()) + supp - qsum(claims.values())
    nl_gva = rd.v("mospi_nas_2026_s8_12", "s8_12.non_life_insurance_s_128.current")
    ctx.log(f"R17: implied non-life service charge {service.v:,.2f} vs NAS 8.12 non-life GVA {nl_gva.v:,.2f}")
    k_hh = _key(deps.key("c4b_insurance_service"))
    k_nfc = shares({s: deps.nfc_gos[s] for s in ("E_NFPU", "E_NFPR")})
    out.method(
        "r17",
        "R17",
        "estimated",
        "Gap map R17 (plan s.2.9; SNA 2008 17.33, actual claims taken as expected): D72 claims = IRDAI 2023-24 "
        "net incurred claims by line (insurers_general_direct: public, private, specialised, stand-alone "
        "health; reinsurers excluded); D71 net premiums = claims (so D71 = D72 by line); premium supplements = "
        "IRDAI non-life investment income (summary) less shareholders' investment income (T51), by line in "
        "proportion to net premium earned. Payer split by line: households' share an assumption record "
        "(motor, health, fire, marine, others), NFCs' part by factors' NFC GOS (E_NFPU/E_NFPR); household "
        "groups by hh_keys c4b_insurance_service (the C4b service-charge key, XR-10). Premiums, claims and "
        "supplements of a line use the same split.",
    )
    hh_share = {ln: Q(HH_SHARE[ln], frozenset({split_pid})) for ln in LINES}
    agg: dict[tuple[str, str], Q] = {}
    for ln in LINES:
        s_ln = supp * npe[ln] / qsum(npe.values())
        for comp, amt in (("claim", claims[ln]), ("premium", claims[ln]), ("premium_supplement", s_ln)):
            for g in HH:
                agg[(comp, g)] = agg.get((comp, g), Q(0.0)) + amt * hh_share[ln] * k_hh[g]
            for s in ("E_NFPU", "E_NFPR"):
                agg[(comp, s)] = agg.get((comp, s), Q(0.0)) + amt * (1.0 - hh_share[ln]) * k_nfc[s]
    for (comp, sector), q in sorted(agg.items()):
        conf = "medium" if sector in HH else "low"
        if comp == "premium":
            out.add("E_INSP", sector, comp, q, key="r17", role="free", confidence=conf)
        else:
            out.add(sector, "E_INSP", comp, q, key="r17", role="free", confidence=conf)
    # per payer sector (households, E_NFPU, E_NFPR): D71 premiums = D72 claims (the same split of each line), the
    # targets of the r17.payer.* bands (fincorp-33, audit BS-1)
    by_sector = {(s, comp): qsum(q for (c, g), q in agg.items() if c == comp and (g == s or (s == "HH" and g in HH)))
                 for s in ("HH", "E_NFPU", "E_NFPR") for comp in ("claim", "premium_supplement")}  # fmt: skip
    return {"claims": tot_claims, "supplement": supp, "service": service, "by_sector": by_sector}


def s9_satellite(ctx: BlockContext, rd: Reader, sat: SatOut, d44: D44) -> None:
    rows = [
        ("s9.epf.contributions", EPFO, "app5i.epf_contribution.current", EPFO_V, "epf", "contributions"),
        ("s9.epf.payments", EPFO, "app5i.epf_payment.current", EPFO_V, "epf", "benefits"),
        ("s9.eps.contributions", EPFO, "para54.eps_contribution_total.current", EPFO_V, "eps", "contributions"),
        (
            "s9.eps.pensions",
            "finsector_markets_epfo_eps_outgo",
            "eps_outgo.pension_disbursed.current",
            EPFO_V,
            "eps",
            "benefits",
        ),
        (
            "s9.eps.withdrawals",
            "finsector_markets_epfo_eps_outgo",
            "eps_outgo.withdrawal_benefits.current",
            EPFO_V,
            "eps",
            "benefits",
        ),
        ("s9.edli.contributions", EPFO, "app5i.edli_contribution.current", EPFO_V, "edli", "contributions"),
        ("s9.edli.payments", EPFO, "app5i.edli_payment.current", EPFO_V, "edli", "benefits"),
        (
            "s9.nps.contributions.state_govt.employer",
            NPSG,
            "m7d.annual_contribution_employer.state_govt.current",
            "latest",
            "nps",
            "contributions",
        ),
        (
            "s9.nps.contributions.state_govt.employee",
            NPSG,
            "m7d.annual_contribution_employee.state_govt.current",
            "latest",
            "nps",
            "contributions",
        ),
        ("s9.life.premiums", IRL, "t24.premium.insurers_life.current", "latest", "life", "contributions"),
        ("s9.life.benefits", IRL, "t24.benefits_paid_net.insurers_life.current", "latest", "life", "benefits"),
        (
            "s9.gpf_union.additions",
            "union_fiscal_fa_provident_funds",
            "fa14.8009.total.additions",
            "latest",
            "gpf_union",
            "additions_incl_interest",
        ),
        (
            "s9.gpf_union.discharges",
            "union_fiscal_fa_provident_funds",
            "fa14.8009.total.discharges",
            "latest",
            "gpf_union",
            "benefits",
        ),
        (
            "s9.gpf_states.receipts",
            "state_fiscal_rbi_sf_appendices",
            "app3.total_capital_receipts.vi.1-state_provident_funds.in.all_states_uts.actuals",
            "latest",
            "gpf_states",
            "additions_incl_interest",
        ),
        (
            "s9.gpf_states.disbursements",
            "state_fiscal_rbi_sf_appendices",
            "app4.total_capital_disbursements.vii.1-state_provident_funds.in.all_states_uts.actuals",
            "latest",
            "gpf_states",
            "benefits",
        ),
        ("s9.ppf.net_accretion", "union_fiscal_nssf", "nssf.ppf.additions", "latest", "ppf", "net_accretion"),
        (
            "s9.pli.additions",
            "union_fiscal_fa_provident_funds",
            "fa14.8014.total.additions",
            "latest",
            "pli",
            "additions_incl_interest",
        ),
        (
            "s9.pli.discharges",
            "union_fiscal_fa_provident_funds",
            "fa14.8014.total.discharges",
            "latest",
            "pli",
            "benefits",
        ),
        (
            "s9.cgegis.additions",
            "union_fiscal_fa_provident_funds",
            "fa14.8011.total.additions",
            "latest",
            "cgegis",
            "additions_incl_interest",
        ),
        (
            "s9.cgegis.discharges",
            "union_fiscal_fa_provident_funds",
            "fa14.8011.total.discharges",
            "latest",
            "cgegis",
            "benefits",
        ),
    ]
    sat.method(
        "s9.official",
        "official",
        "S9: gross flows of funded schemes as published (EPFO AR 2023-24; PFRDA; "
        "IRDAI 2023-24; Union Finance Accounts St. 14 (GPF MH 8009, CGEGIS 8011, PLI 8014); RBI State Finances "
        "App. III/IV (State PF, incl. other savings deposits); NSSF PPF). Memo only: these are financial "
        "flows (I_INPE / I_SSAV), not current transfers.",
    )
    sat.method(
        "s9.derived",
        "derived",
        "S9: flows the clean data mark as derived, as ingested (e.g. PFRDA NPS "
        "contributions by subscriber sector, annualised from the monthly bulletin; EPS outgo by type).",
    )
    sat.method("s9.est", "estimated", "S9: interest / investment income credited by scheme = the R9c D44 estimates.")

    def key_of(q: Q) -> str:  # the record's status follows the clean input's status
        return (
            "s9.official" if all((ctx.lookup_prov(p) or {}).get("status") == "official" for p in q.p) else "s9.derived"
        )

    for sid, ds, series, vint, scheme, flow in rows:
        q = rd.v(ds, series, vintage=vint)
        sat.add(sid, q, key=key_of(q), scheme=scheme, flow=flow)
    for c in ("central_govt", "state_govt", "corporate", "all_citizen", "apy", "nps_lite", "tier2", "tier2_tax_saver"):
        q = rd.v(NPS, f"m4d.annual_contribution.{c}.current")
        sat.add(f"s9.nps.contributions.{c}", q, key=key_of(q), scheme="nps", flow="contributions")
    for scheme, q in d44.by_scheme.items():
        sat.add(f"s9.{scheme}.interest_credited", q, key="s9.est", scheme=scheme, flow="interest_credited")
