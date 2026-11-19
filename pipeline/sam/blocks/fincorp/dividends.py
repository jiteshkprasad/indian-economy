"""R8: dividends paid by corporations to non-government resident holders (households: R8a; government: R7,
government block; RoW: R14, rest_of_world). Plan s.2.6.

Issuer totals: public NFCs and banks by 'government-share grossing': the dividends government's R7 books from
the issuer, divided by the FSF F51 equity share of the governments that book them (E_NFPU: Centre + States;
E_BANK: the Centre only, as the plan says, because only the Union's bank dividends are in R7: verifier V-FIN-3);
insurers from the IRDAI appropriations; private NFCs and NBFCs have no anchor (RBI corporate finances are
DBIE-only) and use the public NFCs' dividend/GOS ratio (an assumption record) x their GOS.

Holders: the government parts are government's R7 entries as booked (the SAM flows); the rest of each issuer total
goes to the non-government holders (households, corporations, RBI, RoW) by their FSF F51 equity shares, OFC
holdings split into NBFCs / insurers and PFs / mutual funds, mutual funds looked through to unit holders (SEBI
T72). So the private E_NBFC total never reaches government (its FSF government holdings are public NBFCs'), and
E_INSP's IRDAI total is net of what the Centre books from LIC (verifier V-FIN-6). The RoW part is a memo: rest_of_
world writes RoW dividends (R14) on its own basis, and the satellite shows both."""

from __future__ import annotations

from dataclasses import dataclass, field

from pipeline.sam.blocks.fincorp.core import Method, Out, Q, Reader, SatOut, qsum, register
from pipeline.sam.blocks.fincorp.deps import ROW_DIV, Deps
from pipeline.sam.blocks.fincorp.f4a import ENDS, IRL, IRN, fsf
from pipeline.sam.blocks.fincorp.govint import GovInt
from pipeline.sam.framework import BlockContext, SamError

ISSUER_SEC = {"E_NFPU": "nfc_pub", "E_NFPR": "nfc_pvt", "E_BANK": "fc_odc", "E_NBFC": "nbfc", "E_INSP": "fc_ofc_icpf"}
ISSUER_CP = {"E_NFPU": "nfc_pub", "E_NFPR": "nfc_pvt", "E_BANK": "fc_odc", "E_NBFC": "fc_ofc", "E_INSP": "fc_ofc"}
HOLDER_CP = {
    "HH": "hh",
    "E_NFPU": "nfc_pub",
    "E_NFPR": "nfc_pvt",
    "E_BANK": "fc_odc",
    "OFC": "fc_ofc",
    "E_RBI": "fc_rbi",
    "G_CEN": "gg_cen",
    "G_STA": "gg_sta",
    "ROW": "row",
}
GOVS = ("G_CEN", "G_STA")
GROSSED = ("E_NFPU", "E_BANK")  # issuer totals grossed up from government's R7
NO_R7 = ("E_NFPR", "E_NBFC")  # private-only totals: an R7 entry from them would contradict the method
NL_GROUPS = ("general_private", "general_public", "general_specialized", "health_standalone")


def _f51(rd: Reader, sec: str, side: str, cp: str) -> Q:
    if sec == "nbfc":
        return (
            fsf(rd, "fc_ofc", side, "f51", cp)
            - fsf(rd, "fc_ofc_icpf", side, "f51", cp)
            - fsf(rd, "fc_ofc_mf", side, "f51", cp)
        )
    return fsf(rd, sec, side, "f51", cp)


@dataclass
class Dividends:
    total: dict[str, Q] = field(default_factory=dict)  # issuer -> dividends paid (all holders)
    hh: dict[tuple[str, str], Q] = field(default_factory=dict)  # (R8a component, issuer) -> household total
    equity_yield: Q = Q(0.0)  # NFC dividends / NFC equity (FSF), for the NPS pass-through (R9c)
    received_fc: dict[str, Q] = field(default_factory=dict)


def build_dividends(
    ctx: BlockContext, rd: Reader, out: Out, sat: SatOut, deps: Deps, gi: GovInt, fc_gos: dict[tuple[str, str], Q]
) -> Dividends:
    dv = Dividends()
    eq = {i: _f51(rd, ISSUER_SEC[i], "liabilities", "all") for i in ISSUER_SEC}
    # government's R7 by issuer and government (the SAM flows); an R7 issuer this method does not know stops the build
    r7: dict[str, dict[str, Q]] = {i: {} for i in ISSUER_SEC}
    for (g, i), q in sorted(deps.r7.items()):
        if g not in GOVS or i not in ISSUER_SEC or i in NO_R7:
            raise SamError(f"fincorp R8: government R7 entry {g} <- {i} does not fit the dividend method (plan s.2.6)")
        r7[i][g] = q
    for i in GROSSED:
        # gross with the equity share of the governments whose receipts are in the numerator (V-FIN-3: the Union's
        # bank dividends over the Union's share of ODC equity; E_NFPU: Centre + States over both shares)
        govs = sorted(r7[i])
        num = qsum(r7[i].values())
        den = qsum(_f51(rd, ISSUER_SEC[i], "liabilities", HOLDER_CP[g]) for g in govs)
        if not govs or num.v <= 0 or den.v <= 0:
            raise SamError(f"fincorp R8: no government dividends (R7) or no government equity (FSF) for {i}")
        dv.total[i] = num / (den / eq[i])
        ctx.log(f"R8: {i} total {dv.total[i].v:,.2f} = R7 of {govs} {num.v:,.2f} / FSF F51 share {(den / eq[i]).v:.4f}")
    life = rd.v(IRL, "t25.appr_interim_dividends.insurers_life.current") + rd.v(
        IRL, "t25.appr_proposed_final_dividend.insurers_life.current"
    )
    nonlife = qsum(
        rd.v(IRN, f"t51.{a}.{g}.current")
        for a in ("appr_interim_dividends", "appr_proposed_final_dividend")
        for g in NL_GROUPS
    )
    dv.total["E_INSP"] = life + nonlife
    raw = dv.total["E_NFPU"] / deps.nfc_gos["E_NFPU"]
    pid = register(
        ctx,
        Method(
            "R8",
            "estimated",
            "Assumption parameter (plan s.2.6): private NFCs and private NBFCs distribute the same share "
            "of their GOS as dividends as public NFCs do (public NFC dividends grossed from government's R7 "
            "receipts / public NFC GOS from factors F4). No private dividend total is ingested (RBI corporate "
            f"finances are DBIE-only, ISSUES P1-4). Value {raw.v:.6f}; very low confidence; balancing sizes "
            "these flows through the NAS private NFC saving total.",
        ),
        raw.p,
    )
    ratio = Q(raw.v, frozenset({pid}))
    dv.total["E_NFPR"] = ratio * deps.nfc_gos["E_NFPR"]
    dv.total["E_NBFC"] = ratio * fc_gos[("E_NBFC", "private")]
    r7_insp = qsum(r7["E_INSP"].values())
    ctx.log(f"R8: E_INSP dividends (IRDAI) {dv.total['E_INSP'].v:,.2f}; R7 E_INSP to GG {r7_insp.v:,.2f}")
    # dividend yield at market value (NPS equity is held at market value; FSF F51 is at book value): all
    # corporate dividends estimated here / NSE market capitalisation (average end-March 2023 and 2024)
    mcap = rd.avg("finsector_markets_sebi_bonds_equity", "t23.market_cap.nse.current", ENDS)
    dv.equity_yield = qsum(dv.total.values()) / mcap

    out.method(
        "r8.div",
        "R8",
        "estimated",
        "Gap map R8 (plan s.2.6; RBI corporate finances not available): issuer totals: E_NFPU = dividends "
        "government books from it (government block R7, Centre + States) / the Centre's + States' share of its "
        "equity; E_BANK = the Union's R7 bank dividends / the Centre's share of ODC equity (FSF F51, average "
        "end-March 2023/2024; only the Union's bank dividends are in R7); E_INSP = IRDAI 2023-24 interim + "
        "proposed final dividends (life, non-life); E_NFPR and E_NBFC (private) = public NFCs' dividends / GOS "
        "ratio (assumption record) x their GOS (factors F4; F4a). Holders: the government parts are government's "
        "R7 entries (not written here); the issuer total less R7 goes to the non-government holders by their FSF "
        "F51 equity shares (government holders excluded: the private E_NBFC total has no government holder, "
        "E_INSP's total is net of the LIC dividend the Centre books); OFC holdings split into NBFCs / insurers "
        "and PFs / mutual funds by the sub-sectors' F51 assets; mutual funds looked through to unit holders (SEBI "
        "T72). The RoW part is a memo (rest_of_world writes R14 on its own basis); households' part is R8a. "
        "Intra-account holdings (E_NFPR <- E_NFPR) are kept (FRAMEWORK_REQUESTS P-5).",
    )
    sat.method(
        "dm",
        "estimated",
        "fincorp R8 dividend matrix: issuer totals; government parts = government's R7 as booked; the rest by the "
        "non-government holders' FSF F51 shares (R8, R8a, look-through, and the RoW memo); memo rows: the "
        "government amounts an FSF-share split would give, and rest_of_world's R14 direct-investment dividends.",
    )
    for issuer in ("E_NFPU", "E_NFPR", "E_BANK", "E_NBFC", "E_INSP"):
        sec, total = ISSUER_SEC[issuer], dv.total[issuer]
        hold = {h: _f51(rd, sec, "liabilities", cp) for h, cp in HOLDER_CP.items()}
        for h, q in list(hold.items()):
            if q.v < 0:
                ctx.log(f"R8: FSF F51 {sec} held by {h} negative ({q.v:,.0f}); set to 0")
                hold[h] = Q(0.0, q.p)
        base = qsum(hold.values())
        resid = eq[issuer] - base
        if abs(resid.v) > 0.01 * abs(eq[issuer].v):
            ctx.log(f"R8: FSF F51 {sec}: counterparties sum to {base.v:,.0f} vs 'all' {eq[issuer].v:,.0f}")
        gov_paid = qsum(r7[issuer].values())
        rest = total - gov_paid
        if rest.v <= 0:
            raise SamError(
                f"fincorp R8: {issuer} total {total.v:,.2f} does not exceed government's R7 {gov_paid.v:,.2f}"
            )
        fsf_gov = {g: total * hold[g] / base for g in GOVS}  # memo: what an FSF-share split would give government
        ng = {h: q for h, q in hold.items() if h not in GOVS}
        ng_base = qsum(ng.values())
        ofc = ng.pop("OFC")
        ofc_w = {
            "E_NBFC": _f51(rd, "nbfc", "assets", ISSUER_CP[issuer]),
            "E_INSP": _f51(rd, "fc_ofc_icpf", "assets", ISSUER_CP[issuer]),
            "MF": _f51(rd, "fc_ofc_mf", "assets", ISSUER_CP[issuer]),
        }
        ofc_w = {k: (q if q.v > 0 else Q(0.0, q.p)) for k, q in ofc_w.items()}
        wsum = qsum(ofc_w.values())
        parts: dict[str, Q] = {h: rest * q / ng_base for h, q in ng.items()}
        for k, w in ofc_w.items():
            parts[k] = rest * ofc / ng_base * (w / wsum) if wsum.v > 0 else Q(0.0)
        if wsum.v <= 0 and ofc.v > 0:
            parts["E_NBFC"] = rest * ofc / ng_base
        for g in GOVS:
            parts[g] = r7[issuer].get(g, Q(0.0))
        for h, q in sorted(parts.items()):
            sat.add(
                f"div.{issuer.lower()}.{h.lower()}",
                q,
                key="dm",
                issuer=issuer,
                holder=h,
                treatment={
                    "G_CEN": "R7 (government block, as booked)",
                    "G_STA": "R7 (government block, as booked)",
                    "ROW": "memo: FSF share, not a SAM flow (rest_of_world writes R14)",
                    "HH": "R8a dividends",
                    "MF": "look-through",
                }.get(h, "R8"),
            )
            if q.v == 0 or h in ("G_CEN", "G_STA", "ROW"):
                continue
            if h == "HH":
                dv.hh[("dividends", issuer)] = dv.hh.get(("dividends", issuer), Q(0.0)) + q
            elif h == "MF":
                for mh, s in gi.mf_share.items():
                    if mh == "HH":
                        dv.hh[("mf_lookthrough", issuer)] = dv.hh.get(("mf_lookthrough", issuer), Q(0.0)) + q * s
                    else:
                        out.add(mh, issuer, "mf_lookthrough", q * s, key="r8.div", role="free", confidence="low")
            else:
                out.add(h, issuer, "dividends", q, key="r8.div", role="free", confidence="low")
        sat.add(f"total.{issuer.lower()}", total, key="dm", issuer=issuer, holder=None, treatment="issuer total")
        for g, q in fsf_gov.items():
            sat.add(
                f"memo.fsf_share.{issuer.lower()}.{g.lower()}",
                q,
                key="dm",
                issuer=issuer,
                holder=g,
                treatment="memo: issuer total x FSF share, not a SAM flow (compare R7)",
            )
        sat.add(
            f"memo.r14_di_distributed.{issuer.lower()}",
            deps.row_sum(row="R_ROW", col=issuer, refs=("R14",), comps=(ROW_DIV,)),
            key="dm",
            issuer=issuer,
            holder="ROW",
            treatment="memo: rest_of_world R14 di_distributed (the SAM flow; FPI dividends sit in its pi_other)",
        )
    sat.add(
        "param.dividend_to_gos_ratio_nfc_public",
        ratio,
        key="dm",
        unit="ratio",
        issuer="E_NFPU",
        holder=None,
        treatment="assumption applied to E_NFPR and private E_NBFC",
    )
    sat.add(
        "param.dividend_yield_market",
        dv.equity_yield,
        key="dm",
        unit="ratio",
        issuer=None,
        holder=None,
        treatment="all corporate dividends here / NSE market cap (NPS equity pass-through, R9c)",
    )
    return dv


# ---------------------------------------------------------------------------------------------
# D2-21: private NFCs' other distributed income, sized by the old-base (NAS 2024) sector structure
# ---------------------------------------------------------------------------------------------

OLD_PNFC = "mospi_nas_2026_oldbase_soa_s2_2"  # NAS 2024 (old base 2011-12) St 2.2, private NFCs
OLD_PERIOD, OLD_SENS = "2022-23", ("2021-22", "2020-21")  # D2-21: the 2022-23 structure (FRE); earlier years shown
S19 = "mospi_nas_2026_s1_9"
D4_REFS = ("R3a", "R4", "R5", "R8", "R8a")  # fincorp's property-income refs (R17 premium supplements added below)
TOPUP = "distributed_income"  # R8 / R8a component of the top-up


def _old(rd: Reader, item: str, period: str) -> Q:
    return rd.v(OLD_PNFC, f"oldbase_soa_s2_2.{item}.current", period=period)


def oldbase_ratio(rd: Reader, period: str) -> tuple[Q, dict[str, Q]]:
    """Old-base private NFC net property income (D4 resources - D4 uses) / gross operating surplus (NOS + CFC)."""
    p = {
        "d4_resources": _old(rd, "allocation_of_primary_income.resources.d4", period),
        "d4_uses": _old(rd, "allocation_of_primary_income.uses.d4", period),
        "nos": _old(rd, "allocation_of_primary_income.resources.b2n_b3n", period),
        "cfc": _old(rd, "production.uses.p51c", period),
    }
    return (p["d4_resources"] - p["d4_uses"]) / (p["nos"] + p["cfc"]), p


def net_d4(out: Out, deps: Deps, acct: str) -> dict[str, Q]:
    """An account's net property income (D4) over every SAM entry fincorp can see, by source: fincorp's R3a, R4, R5,
    R8, R8a and R17 premium supplements (D44), rest_of_world's R13 / R14 / R14a, government's R7 / R7x. Flows inside
    the account are left out (they cancel)."""

    def d4(i: dict) -> bool:
        ref = out.methods[i["key"]].ref
        return ref in D4_REFS or (ref == "R17" and i["comp"] == "premium_supplement")

    parts = {
        "fincorp_received": qsum(i["q"] for i in out.items if i["row"] == acct and i["col"] != acct and d4(i)),
        "fincorp_paid": -qsum(i["q"] for i in out.items if i["col"] == acct and i["row"] != acct and d4(i)),
        "row_received": deps.row_sum(row=acct, col="R_ROW", refs=("R13",)),
        "row_paid": -deps.row_sum(row="R_ROW", col=acct, refs=("R14", "R14a")),
        "gov_r7_r7x_paid": -qsum(
            [*(q for (_, p), q in deps.r7.items() if p == acct), *(q for (_, p), q in deps.r7x.items() if p == acct)]
        ),
    }
    parts["net"] = qsum(parts.values())
    return parts


def build_oldbase_topup(
    ctx: BlockContext, rd: Reader, out: Out, sat: SatOut, deps: Deps, gi: GovInt, hh_key: dict[str, dict[str, Q]]
) -> Q:
    """DECISIONS D2-21. No new-base source gives private NFCs' distributed income (RBI corporate finances are DBIE-
    only, fincorp-11). The old-base NAS 2024 St 2.2 (2022-23) gives private NFCs' net property income as a share of
    their GOS; applied to the new-base 2023-24 GOS (factors F4) it is the prior for E_NFPR's net D4. The SAM's other
    E_NFPR property-income flows are kept as built (interest from FSF x rates scaled to the RTP P&Ls, RoW from BoP,
    government's R7x, the ratio-based dividends of R8); the difference is 'other distributed income' (D42 beyond the
    ratio-based dividends: dividends of unlisted companies and other distributions), written as R8 / R8a component
    `distributed_income` and paid to the non-government resident holders of private NFC equity other than private
    NFCs themselves and RBI (FSF F51 shares; the old-base structure has private NFCs' own D4 receipts at 6.5% of
    GOS, which the SAM's receipts already exceed, so no intra-sector part is added), mutual funds looked through
    (SEBI T72).
    Must run after every other E_NFPR property-income entry (R8a included). Returns the top-up total (0 if the SAM
    already pays at least the prior)."""
    acct = "E_NFPR"
    raw, inp = oldbase_ratio(rd, OLD_PERIOD)
    pid = register(
        ctx,
        Method(
            "R8",
            "estimated",
            "Assumption parameter (DECISIONS D2-21, 'estimated, old-base structure'): private NFCs' net property "
            "income (D4 resources - D4 uses) as a share of their gross operating surplus (net operating surplus + "
            "CFC), old-base NAS 2024 Statement 2.2, 2022-23 (First Revised Estimate): "
            f"({inp['d4_resources'].v:,.2f} - {inp['d4_uses'].v:,.2f}) / ({inp['nos'].v:,.2f} + {inp['cfc'].v:,.2f})"
            f" = {raw.v:.6f}. Applied to the new-base 2023-24 private NFC GOS as a prior for E_NFPR's net D4 only; "
            "new-base totals stay the controls.",
        ),
        raw.p,
    )
    ratio = Q(raw.v, frozenset({pid}))
    prior = ratio * deps.nfc_gos[acct]
    before = net_d4(out, deps, acct)
    gap = before["net"] - prior  # > 0: the SAM's E_NFPR keeps more property income than the old-base structure
    # holders: non-government residents other than private NFCs and RBI (RBI's income rests on its Annual Report, plan
    # C3/D0-7, which shows no such receipts)
    hold = {
        h: _f51(rd, "nfc_pvt", "liabilities", cp)
        for h, cp in HOLDER_CP.items()
        if h not in (*GOVS, "ROW", "E_RBI", acct)
    }
    hold = {h: (q if q.v > 0 else Q(0.0, q.p)) for h, q in hold.items()}
    ofc = hold.pop("OFC")
    ofc_w = {
        "E_NBFC": _f51(rd, "nbfc", "assets", "nfc_pvt"),
        "E_INSP": _f51(rd, "fc_ofc_icpf", "assets", "nfc_pvt"),
        "MF": _f51(rd, "fc_ofc_mf", "assets", "nfc_pvt"),
    }
    ofc_w = {k: (q if q.v > 0 else Q(0.0, q.p)) for k, q in ofc_w.items()}
    wsum = qsum(ofc_w.values())
    base = qsum(hold.values()) + ofc
    if base.v <= 0 or wsum.v <= 0:
        raise SamError("fincorp R8 (D2-21): FSF shows no non-government resident holders of private NFC equity")
    sh = {h: q / base for h, q in hold.items()}
    for k, w in ofc_w.items():
        sh[k] = sh.get(k, Q(0.0)) + ofc / base * (w / wsum)
    back = sh["MF"] * gi.mf_share.get(acct, Q(0.0))  # the part that returns to E_NFPR through its MF units
    if gap.v > 0:
        total = gap / (1.0 - back)
    else:
        total = Q(0.0, gap.p)
        ctx.warn(
            f"R8 (D2-21): E_NFPR's net D4 {before['net'].v:,.2f} is already at or below the old-base prior "
            f"{prior.v:,.2f}; no other distributed income written"
        )
    ctx.log(
        f"R8 (D2-21): E_NFPR net D4 before {before['net'].v:,.2f} vs old-base prior {prior.v:,.2f} (ratio "
        f"{ratio.v:.6f} x GOS {deps.nfc_gos[acct].v:,.2f}); other distributed income {total.v:,.2f} "
        f"(grossed up for the {back.v:.4f} that returns through MF units)"
    )
    out.method(
        "r8.oldbase",
        "R8",
        "estimated",
        "Gap map R8, private NFCs' other distributed income (DECISIONS D2-21, 'estimated, old-base structure'): the "
        "amount that brings E_NFPR's net property income over all SAM entries (fincorp R3a, R4, R5, R8, R8a, R17 "
        "premium supplements; rest_of_world R13, R14, R14a; government R7x) to the old-base NAS 2024 St 2.2 "
        "2022-23 ratio of private NFCs' net D4 to GOS times the new-base 2023-24 GOS (factors F4). Paid to the "
        "non-government resident holders of private NFC equity other than private NFCs and RBI (whose income rests on "
        "its Annual Report, plan C3) by FSF F51 shares (average "
        "end-March 2023/2024), OFC holdings split into NBFCs / insurers and PFs / mutual funds by their F51 assets, "
        "MF income looked through to unit holders (SEBI T72); the part that returns to E_NFPR through its MF units "
        "is grossed up. Households' part is R8a. Very low confidence (free, low): a prior for balancing.",
    )
    out.method(
        "r8a.oldbase",
        "R8a",
        "estimated",
        "Gap map R8a, households' part of private NFCs' other distributed income (DECISIONS D2-21, 'estimated, old-"
        "base structure'; method of R8 component distributed_income): direct holdings by hh_keys aidis_equity, the "
        "MF look-through by aidis_mf (AIDIS 2019 structure, low confidence).",
    )
    parts: dict[str, Q] = {h: total * s for h, s in sh.items()}
    hh_direct = parts.pop("HH")
    mf = parts.pop("MF")
    hh_mf = Q(0.0)
    for mh, s in gi.mf_share.items():
        if mh == "HH":
            hh_mf = mf * s
        else:
            out.add(mh, acct, f"{TOPUP}_mf", mf * s, key="r8.oldbase", role="free", confidence="low")
    for h, q in sorted(parts.items()):
        out.add(h, acct, TOPUP, q, key="r8.oldbase", role="free", confidence="low")
    for comp, q, key in ((TOPUP, hh_direct, "aidis_equity"), (f"{TOPUP}_mf", hh_mf, "aidis_mf")):
        k = hh_key[key]
        for g in sorted(k):
            out.add(g, acct, comp, q * k[g], key="r8a.oldbase", role="free", confidence="low")
    after = net_d4(out, deps, acct)
    ctx.log(f"R8 (D2-21): E_NFPR net D4 after {after['net'].v:,.2f} (prior {prior.v:,.2f})")

    # satellite rows: the structure, the before/after measurement and the holders
    sat.method(
        "ob",
        "estimated",
        "fincorp R8 D2-21: old-base NAS 2024 St 2.2 private NFC net D4 / GOS (2022-23; earlier years as "
        "sensitivities), the prior for E_NFPR's net D4 (x new-base GOS), the SAM's E_NFPR net D4 by source before "
        "and after the other distributed income, and its split by holder.",
    )
    sat.add(
        "oldbase.param.net_d4_to_gos",
        ratio,
        key="ob",
        unit="ratio",
        issuer=acct,
        holder=None,
        treatment=f"old-base {OLD_PERIOD} (used)",
    )
    for k, q in inp.items():
        sat.add(f"oldbase.input.{k}", q, key="ob", issuer=acct, holder=None, treatment=f"old-base {OLD_PERIOD}")
    for per in OLD_SENS:
        r, _ = oldbase_ratio(rd, per)
        sat.add(
            f"oldbase.sens.net_d4_to_gos.{per}",
            r,
            key="ob",
            unit="ratio",
            issuer=acct,
            holder=None,
            treatment="sensitivity, not used",
        )
        sat.add(
            f"oldbase.sens.prior.{per}",
            r * deps.nfc_gos[acct],
            key="ob",
            issuer=acct,
            holder=None,
            treatment="sensitivity, not used",
        )
    # cross-check: the old-base D4 share of private NFCs' net distributive flows x the new-base requirement
    o = {
        "d5": _old(rd, "secondary_distribution_of_income.uses.d5", OLD_PERIOD),
        "d67_res": _old(rd, "secondary_distribution_of_income.resources.d6_plus_d7", OLD_PERIOD),
        "d67_use": _old(rd, "secondary_distribution_of_income.uses.d6_plus_d7", OLD_PERIOD),
    }
    d4n = inp["d4_resources"] - inp["d4_uses"]
    share = d4n / (d4n - o["d5"] + o["d67_res"] - o["d67_use"])
    req = rd.v(S19, "s1_9.private_non_financial_corporations.current") - deps.nfc_gos[acct]
    sat.add(
        "oldbase.check.d4_share_of_net_distributive",
        share,
        key="ob",
        unit="ratio",
        issuer=acct,
        holder=None,
        treatment="cross-check, not used",
    )
    sat.add(
        "oldbase.check.prior_via_new_base_requirement",
        share * req,
        key="ob",
        issuer=acct,
        holder=None,
        treatment="cross-check, not used: old-base D4 share x (NAS 1.9 saving - GOS)",
    )
    sat.add("oldbase.e_nfpr.prior_net_d4", prior, key="ob", issuer=acct, holder=None, treatment="prior (used)")
    for tag, m in (("before", before), ("after", after)):
        for k, q in m.items():
            sat.add(f"oldbase.e_nfpr.{tag}.{k}", q, key="ob", issuer=acct, holder=None, treatment=f"SAM {tag}")
    sat.add(
        "oldbase.e_nfpr.returning_share",
        back,
        key="ob",
        unit="ratio",
        issuer=acct,
        holder="MF",
        treatment="share of the top-up returning to E_NFPR via MF units (grossed up)",
    )
    sat.add("oldbase.e_nfpr.total", total, key="ob", issuer=acct, holder=None, treatment="other distributed income")
    for h, s in sorted(sh.items()):
        sat.add(
            f"oldbase.e_nfpr.holder.{h.lower()}",
            total * s,
            key="ob",
            issuer=acct,
            holder=h,
            treatment="R8a distributed_income" if h == "HH" else ("look-through" if h == "MF" else "R8"),
        )
    return total
