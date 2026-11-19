"""R3 (inter-government interest), R3a (government interest by holder), R3b (cash -> NAS-concept bridge).

Every line of Union MH 2049 (Finance Accounts 2023-24) and of the States' interest (RBI State Finances
App. II, all States and UTs) is given one destination; the bridge satellite `gov_interest_bridge` lists them
and must reproduce each payer's published total (plan s.2.2-2.4, CROSS_REVIEW XR-12).

Destinations written elsewhere by fincorp: household parts (R8a `small_savings`, `gsec_direct`,
`mf_lookthrough`), GPF / State PF interest (R9c). Written by rest_of_world (R14): external-debt interest
and FPI-held G-sec interest; fincorp reads the FPI part and allocates only the remainder to domestic holders."""

from __future__ import annotations

from dataclasses import dataclass, field

import polars as pl

from pipeline.sam.blocks.fincorp.core import Out, Q, Reader, SatOut, qsum, shares
from pipeline.sam.blocks.fincorp.deps import ROW_FPI, ROW_NOT_INTEREST, Deps
from pipeline.sam.blocks.fincorp.f4a import ENDS, RBI_AR_VINTAGE, RBIAR, fsf
from pipeline.sam.framework import BlockContext, SamError

FAE, FAR = "union_fiscal_fa_expenditure", "union_fiscal_fa_receipts"
SF = "state_fiscal_rbi_sf_appendices"
T107 = "rbi_financial_accounts_hbs_gsec_ownership"
SEBI = "finsector_markets_sebi_mf"
KFI = "state_fiscal_fc16_kfi"
SFI = "app2.total_expenditure.ii.c.2{}.in.all_states_uts.actuals"
CATS = (
    "commercial_banks",
    "cooperative_banks",
    "non_bank_pds",
    "financial_institutions",
    "insurance",
    "provident_funds",
    "pension_funds",
    "mutual_funds",
    "corporates",
    "others",
    "fpi",
    "rbi",
)
HOLDER = {
    "commercial_banks": "E_BANK",
    "cooperative_banks": "E_BANK",
    "non_bank_pds": "E_NBFC",
    "financial_institutions": "E_NBFC",
    "insurance": "E_INSP",
    "provident_funds": "E_INSP",
    "pension_funds": "E_INSP",
}

# Union MH 2049 lines: destination of each (lines not listed must be zero, else the build fails)
UNION_DATED = "01.101"
UNION_TBILLS = ("01.103", "01.108", "01.110")
UNION_OTHER_SEC = ("01.118", "01.134", "01.200", "60.101", "60.106", "60.109")
UNION_RECAP = ("01.132", "01.133", "60.110")
UNION_PUBLIC_ACCOUNT = ("03.108", "03.109")
UNION_WMA, UNION_ITB, UNION_GPF = "01.115", "01.116", "03.104"
UNION_SGB = ("01.129", "01.130")
UNION_NSSF = ("01.121", "01.122", "01.125")  # intra-G_CEN (NSSF is inside G_CEN)
UNION_INTRA_OTHER = ("05.101", "05.103", "05.105", "60.107", "60.111")  # reserve funds, FCI, PLI: intra-G_CEN
UNION_NOT_INTEREST = ("01.305",)  # management of debt: a fee, not D41
UNION_RECOVERIES = ("01.911", "03.911", "05.911")
UNION_EXTERNAL_PREFIX = "02."  # R14 (rest_of_world)


@dataclass
class GovInt:
    hh: dict[tuple[str, str], Q] = field(default_factory=dict)  # (R8a component, payer) -> household total
    by_cat: dict[tuple[str, str], Q] = field(default_factory=dict)  # (T107 category, payer) -> interest
    domestic_fc: dict[str, Q] = field(default_factory=dict)  # holder account -> all R3a received (for R4/R5)
    gpf_union: Q = Q(0.0)
    gpf_states: Q = Q(0.0)
    targets: dict[str, Q] = field(default_factory=dict)  # 'union' / 'states' NAS-concept targets and bridge items
    mf_share: dict[str, Q] = field(default_factory=dict)  # MF unit-holder shares (E_BANK, E_NFPR, HH)
    rbi_loans_by: dict[str, Q] = field(default_factory=dict)  # RBI loans-and-advances interest by payer


def mf_holders(ctx: BlockContext, rd: Reader, mf_corp: Q) -> dict[str, Q]:
    """SEBI T72 AUM shares (average of end-March 2023 and 2024): banks -> E_BANK, corporates -> E_NFPR
    (assumption record `mf_corp`), HNIs + retail -> households."""
    lv = {c: rd.avg(SEBI, f"t72.aum.{c}.current", ENDS) for c in ("banks", "corporates", "hnis", "retail")}
    s = shares(lv)
    return {"E_BANK": s["banks"], "E_NFPR": s["corporates"] * mf_corp, "HH": s["hnis"] + s["retail"]}


def _t107(rd: Reader, inst: str) -> dict[str, Q]:
    return {
        c: rd.avg(T107, f"t107.{inst}.share.{c}", ENDS, unit="percent") / 100.0
        for c in (*CATS, "others_state_governments")
    }


def build_govint(ctx: BlockContext, rd: Reader, out: Out, sat: SatOut, deps: Deps, mf_corp: Q) -> GovInt:
    gi = GovInt()
    gi.mf_share = mf_holders(ctx, rd, mf_corp)

    # --- Union lines ------------------------------------------------------------------------------
    fa = ctx.rows(FAE, vintage="latest").filter(pl.col("series_id").str.starts_with("fa9.2049."))
    line = {
        r["series_id"].removeprefix("fa9.2049."): Q(r["value"], frozenset({r["prov_id"]}))
        for r in fa.iter_rows(named=True)
    }
    total_u = line.pop("total")
    subtotals = {k: line.pop(k) for k in [k for k in line if k.endswith(".total")]}
    known = {
        UNION_DATED,
        *UNION_TBILLS,
        *UNION_OTHER_SEC,
        *UNION_RECAP,
        *UNION_PUBLIC_ACCOUNT,
        UNION_WMA,
        UNION_ITB,
        UNION_GPF,
        *UNION_SGB,
        *UNION_NSSF,
        *UNION_INTRA_OTHER,
        *UNION_NOT_INTEREST,
        *UNION_RECOVERIES,
    }
    unmapped = sorted(k for k in line if k not in known and not k.startswith(UNION_EXTERNAL_PREFIX) and line[k].v != 0)
    if unmapped:
        raise SamError(f"fincorp R3a: Union MH 2049 lines without a destination: {unmapped}")
    L = lambda ks: qsum(line.get(k, Q(0.0)) for k in ([ks] if isinstance(ks, str) else ks))  # noqa: E731
    ctx.check(
        "r3.union_lines_add_up",
        "Union MH 2049: sum of lines vs the published total",
        qsum(line.values()).v,
        total_u.v,
        target_prov_id=next(iter(total_u.p)),
        tol_abs=0.05,
    )
    external = qsum(v for k, v in line.items() if k.startswith(UNION_EXTERNAL_PREFIX))
    reissue = rd.v(FAR, "fa8.0049.03.117") + rd.v(FAR, "fa8.0049.03.116")
    dated = L(UNION_DATED) - reissue
    tbills = L(UNION_TBILLS)
    nssf_int = L(UNION_NSSF)

    # --- States lines -----------------------------------------------------------------------------
    S = lambda s: rd.v(SF, SFI.format(s))  # noqa: E731
    total_s = S("-interest_payments")
    s_central, s_nssf = S(".i-interest_on_loans_from_the_centre"), S(".ii.b-interest_on_nssf")
    sdl = S(".ii.a-interest_on_market_loans")
    s_other_internal = S(".ii-interest_on_internal_debt") - sdl - s_nssf
    s_pf, s_others = S(".iii-interest_on_small_savings_state_provident_funds"), S(".iv-others")
    ctx.check(
        "r3.states_lines_add_up",
        "States' interest: sum of lines vs the published total (RBI SF App. II)",
        (s_central + sdl + s_nssf + s_other_internal + s_pf + s_others).v,
        total_s.v,
        target_prov_id=next(iter(total_s.p)),
        tol_abs=0.05,
    )
    kfi = rd.v(KFI, "kfi.b_1_a-interest_payments.in.all_states_28")
    ctx.check(
        "r3.states_vs_fc16_kfi",
        "States' interest, RBI SF (all States+UTs) vs FC16 KFI (28 States): cross-check within 3% (GOV-5 bridge)",
        total_s.v,
        kfi.v,
        target_prov_id=next(iter(kfi.p)),
        tol_abs=0.03 * kfi.v,
    )

    # --- RoW parts read from rest_of_world (XR-12) ---------------------------------------------------
    sh_c, sh_s, sh_t = _t107(rd, "gsec_central"), _t107(rd, "sgs"), _t107(rd, "tbills")
    own = {"dated": sh_c["fpi"] * dated, "tbills": sh_t["fpi"] * tbills, "sdl": sh_s["fpi"] * sdl}
    fpi: dict[str, Q] = {}
    for inst, (g, comp) in ROW_FPI.items():
        r14 = deps.row_sum(row="R_ROW", col=g, refs=("R14",), comps=(comp,))
        if r14.v > 0:
            fpi[inst] = r14
            if abs(r14.v / own[inst].v - 1) > 0.05:
                ctx.warn(
                    f"R3a: rest_of_world R14 '{comp}' ({r14.v:,.0f}) differs from T107 FPI share x line "
                    f"({own[inst].v:,.0f}) by more than 5%"
                )
        else:
            fpi[inst] = Q(0.0)
            ctx.warn(
                f"R3a: rest_of_world wrote no R14 '{comp}' on {g}: the FPI share of {inst} interest "
                f"({own[inst].v:,.0f}) is left unallocated (memo only)"
            )
    own_fpi = {"G_CEN": own["dated"] + own["tbills"], "G_STA": own["sdl"]}
    fpi_comps = tuple(c for _, c in ROW_FPI.values())
    ext_row = deps.row_sum(row="R_ROW", col="G_CEN", refs=("R14",), exclude=(*fpi_comps, ROW_NOT_INTEREST))
    if abs(ext_row.v - external.v) > 1.0:
        ctx.warn(
            f"R3a: rest_of_world R14 R_ROW <- G_CEN interest other than FPI ({ext_row.v:,.2f}) differs from the "
            f"Union's external-debt interest ({external.v:,.2f})"
        )
    for g in ("G_CEN", "G_STA"):
        opi = deps.row_sum(row="R_ROW", col=g, refs=("R14",), comps=(ROW_NOT_INTEREST,))
        if opi.v:
            ctx.log(
                f"R3b: rest_of_world R14 '{ROW_NOT_INTEREST}' on {g} ({opi.v:,.2f}) falls inside the {g} payer band"
            )

    # --- RBI: RBI Annual Report securities income (accrual), split Centre/States by T107 holdings ----
    rbi_ar = rd.v(RBIAR, "sch13.a.interest_on_holding_of_rupee_securities.current", vintage=RBI_AR_VINTAGE) + rd.v(
        RBIAR, "sch14.a.amortisation_of_premium_discount_on_rupee_securities.current", vintage=RBI_AR_VINTAGE
    )
    if sh_t["rbi"].v != 0:
        raise SamError("fincorp R3a: T107 shows RBI T-bill holdings; the RBI split assumes none")
    w_c, w_s = sh_c["rbi"] * dated, sh_s["rbi"] * sdl
    rbi_part = {"G_CEN": rbi_ar * w_c / (w_c + w_s), "G_STA": rbi_ar * w_s / (w_c + w_s)}
    ctx.log(f"R3a: RBI AR G-sec income {rbi_ar.v:,.2f} vs T107 share x coupon {(w_c + w_s).v:,.2f}")

    # --- domestic holders of each instrument --------------------------------------------------------
    fsf_nfc = {
        g: {
            "E_NFPU": fsf(rd, sec, "liabilities", "f3", "nfc_pub"),
            "E_NFPR": fsf(rd, sec, "liabilities", "f3", "nfc_pvt"),
        }
        for g, sec in (("G_CEN", "gg_cen"), ("G_STA", "gg_sta"))
    }
    fsf_oth = {
        g: {"HH": fsf(rd, sec, "liabilities", "f3", "hh"), **fsf_nfc[g]}
        for g, sec in (("G_CEN", "gg_cen"), ("G_STA", "gg_sta"))
    }
    alloc: dict[tuple[str, str, str], Q] = {}  # (holder, payer, component) -> interest

    def put(holder: str, payer: str, comp: str, q: Q) -> None:
        alloc[(holder, payer, comp)] = alloc.get((holder, payer, comp), Q(0.0)) + q

    def allocate(amount: Q, sh: dict[str, Q], payer: str, comp: str, *, intra_state_drop: bool = False) -> Q:
        """Split `amount` (net of FPI and RBI) over the other T107 holders; returns the intra-G_STA part dropped."""
        cats = [c for c in CATS if c not in ("fpi", "rbi")]
        base = qsum(sh[c] for c in cats)
        dropped = Q(0.0)
        for c in cats:
            part = amount * sh[c] / base
            gi.by_cat[(c, payer)] = gi.by_cat.get((c, payer), Q(0.0)) + part
            if c in HOLDER:
                put(HOLDER[c], payer, comp, part)
            elif c == "mutual_funds":
                for h, s in gi.mf_share.items():
                    if h == "HH":
                        gi.hh[("mf_lookthrough", payer)] = gi.hh.get(("mf_lookthrough", payer), Q(0.0)) + part * s
                    else:
                        put(h, payer, "mf_lookthrough", part * s)
            elif c == "corporates":
                for h, s in shares(fsf_nfc[payer]).items():
                    put(h, payer, comp, part * s)
            elif c == "others":
                st = part * sh["others_state_governments"] / sh["others"]
                if payer == "G_STA":
                    dropped = dropped + st  # SDLs held by State governments: intra-G_STA
                else:
                    put("G_STA", payer, "gsec_state_reserve_funds", st)
                for h, s in shares(fsf_oth[payer]).items():
                    if h == "HH":
                        gi.hh[("gsec_direct", payer)] = gi.hh.get(("gsec_direct", payer), Q(0.0)) + (part - st) * s
                    else:
                        put(h, payer, comp, (part - st) * s)
        return dropped

    put("E_RBI", "G_CEN", "dated_securities", rbi_part["G_CEN"])
    put("E_RBI", "G_STA", "sdl", rbi_part["G_STA"])
    allocate(dated - fpi["dated"] - rbi_part["G_CEN"], sh_c, "G_CEN", "dated_securities")
    allocate(tbills - fpi["tbills"], sh_t, "G_CEN", "tbills")
    sdl_intra = allocate(sdl - fpi["sdl"] - rbi_part["G_STA"], sh_s, "G_STA", "sdl")
    # other Union securities: domestic dated-security holders excluding RBI and FPI (low confidence)
    allocate(L(UNION_OTHER_SEC), sh_c, "G_CEN", "other_securities")
    put("E_BANK", "G_CEN", "recap_bonds", L(UNION_RECAP))
    put("E_INSP", "G_CEN", "public_account_funds", L(UNION_PUBLIC_ACCOUNT))
    put("E_RBI", "G_CEN", "wma", L(UNION_WMA))
    gi.hh[("gsec_direct", "G_CEN")] = gi.hh.get(("gsec_direct", "G_CEN"), Q(0.0)) + L(UNION_SGB)
    gi.hh[("small_savings", "G_CEN")] = nssf_int + s_nssf  # NSSF passes its interest income to small savers
    gi.gpf_union, gi.gpf_states = L(UNION_GPF), s_pf

    # States' other internal debt (NABARD, banks, NCDC): by FSF State loan liabilities to ODC / OFC
    st_key = {
        "E_BANK": fsf(rd, "gg_sta", "liabilities", "f4", "fc_odc"),
        "E_NBFC": fsf(rd, "gg_sta", "liabilities", "f4", "fc_ofc"),
    }
    # States' WMA/overdraft interest to RBI: RBI loans-and-advances interest less the Centre's WMA, by FSF RBI
    # loan assets (fc_odc / fc_ofc / gg_sta); assumed inside the States' 'other internal debt' line
    rbi_loans = rd.v(RBIAR, "sch13.a.interest_on_loans_and_advances.current", vintage=RBI_AR_VINTAGE) - L(UNION_WMA)
    rbi_loan_key = {
        "E_BANK": fsf(rd, "fc_rbi", "assets", "f4", "fc_odc"),
        "E_NBFC": fsf(rd, "fc_rbi", "assets", "f4", "fc_ofc"),
        "G_STA": fsf(rd, "fc_rbi", "assets", "f4", "gg_sta"),
    }
    rbi_loans_by = {k: rbi_loans * s for k, s in shares(rbi_loan_key).items()}
    put("E_RBI", "G_STA", "wma_od", rbi_loans_by["G_STA"])
    state_loans = s_other_internal - rbi_loans_by["G_STA"]
    for h, s in shares(st_key).items():
        put(h, "G_STA", "state_loans", state_loans * s)
    gi.rbi_loans_by = rbi_loans_by  # E_BANK / E_NBFC parts are written by interest.py (R4)

    # --- entries -----------------------------------------------------------------------------------
    out.method(
        "r3.cash",
        "R3",
        "derived",
        "Gap map R3: interest between governments, by payer, cash as published: States' interest on loans "
        "from the Centre and on NSSF loans (RBI State Finances 2025-26 App. II, all States and UTs; NSSF is "
        "inside G_CEN) to G_CEN; Union interest on 14-day Treasury Bills (MH 2049.01.116; held only by "
        "State governments) to G_STA.",
    )
    out.method(
        "r3.reserve_funds",
        "R3",
        "estimated",
        "Gap map R3: Union dated-security and T-bill interest received by State governments' reserve funds "
        "(HBS T107 'others: State governments' share, average of end-March 2023/2024, of the payer lines "
        "net of FPI and RBI parts).",
    )
    out.add("G_CEN", "G_STA", "central_loans", s_central, key="r3.cash", role="anchored", tol_rel=0.02)
    out.add("G_CEN", "G_STA", "nssf", s_nssf, key="r3.cash", role="anchored", tol_rel=0.02)
    out.add("G_STA", "G_CEN", "itb_14d", L(UNION_ITB), key="r3.cash", role="anchored", tol_rel=0.02)
    out.add(
        "G_STA",
        "G_CEN",
        "gsec_state_reserve_funds",
        alloc.pop(("G_STA", "G_CEN", "gsec_state_reserve_funds")),
        key="r3.reserve_funds",
        role="free",
        confidence="medium",
    )

    out.method(
        "r3a.rbi",
        "R3a",
        "derived",
        f"Gap map R3a, E_RBI: RBI Annual Report {ctx.year} (vintage {RBI_AR_VINTAGE}) interest on rupee "
        "securities (Sch. 13 A) plus amortisation of premium/discount (Sch. 14 A), accrual, split Centre/"
        "States by HBS T107 RBI holding shares x the payer lines; the Centre's WMA interest (MH 2049.01.115).",
    )
    out.method(
        "r3a.known",
        "R3a",
        "derived",
        "Gap map R3a, instruments with a known holder: recapitalisation bonds (MH 2049.01.132/.133) and SBI "
        "special bonds (60.110) to E_BANK.",
    )
    out.method(
        "r3a.public_account",
        "R3a",
        "estimated",
        "Gap map R3a: Union interest on 'insurance and pension funds' (MH 2049.03.108) and 'special deposits "
        "and accounts' (03.109) to E_INSP; inference (plan C14): EPFO's EPS deposit in the Public Account and "
        "non-government PF special deposits. E_INSP then pays D44 (R9c).",
    )
    out.method(
        "r3a.holders",
        "R3a",
        "estimated",
        "Gap map R3a (plan s.2.4): each payer line x HBS T107 holder shares (average of end-March 2023 and "
        "2024): dated securities = MH 2049.01.101 less accrued interest and premium received on re-issues "
        "(Receipt MH 0049.03.116/.117); T-bills = 01.103+.108+.110; SDLs = RBI SF App. II market loans. FPI "
        "parts are rest_of_world's R14 (read, XR-12) and RBI's part is the RBI AR figure; the remainder is "
        "spread over the other holders: banks (commercial, co-operative) E_BANK; primary dealers and FIs "
        "E_NBFC; insurance, provident and pension funds E_INSP; mutual funds looked through to unit holders "
        "(SEBI T72: banks E_BANK, corporates E_NFPR); corporates E_NFPU/E_NFPR and 'others' (less State "
        "governments) by FSF counterparty holdings of government securities. Other Union securities "
        "(conversion, green, other internal debt, deposits, petroleum and fertiliser bonds) use the dated-"
        "security holder shares (low). States' other internal debt (App. II ii less market loans and NSSF, "
        "less States' WMA/overdraft interest to RBI) to E_BANK/E_NBFC by FSF State loan liabilities to ODCs "
        "/ OFCs; States' WMA/overdraft interest = RBI AR loans-and-advances interest less the Centre's WMA, "
        "by FSF RBI loan assets. Households' parts are R8a; GPF/State PF interest is R9c.",
    )
    for (h, g, comp), q in sorted(alloc.items()):
        if h == "E_RBI" and comp in ("dated_securities", "sdl", "wma"):
            out.add(h, g, comp, q, key="r3a.rbi", role="anchored", tol_rel=0.02)
        elif comp == "recap_bonds":
            out.add(h, g, comp, q, key="r3a.known", role="anchored", tol_rel=0.02)
        elif comp == "public_account_funds":
            out.add(h, g, comp, q, key="r3a.public_account", role="free", confidence="medium")
        else:
            conf = (
                "low"
                if comp in ("other_securities", "state_loans", "wma_od", "mf_lookthrough") or h in ("E_NFPU", "E_NFPR")
                else "medium"
            )
            out.add(h, g, comp, q, key="r3a.holders", role="free", confidence=conf)
        if h in ("E_RBI", "E_BANK", "E_NBFC", "E_INSP"):
            gi.domestic_fc[h] = gi.domestic_fc.get(h, Q(0.0)) + q

    # --- R3b: NAS-concept targets and the bridge ----------------------------------------------------
    intra_u = nssf_int + L(UNION_INTRA_OTHER)
    target_u = (
        total_u - intra_u - L(UNION_NOT_INTEREST) - L(UNION_RECOVERIES) - reissue + gi.hh[("small_savings", "G_CEN")]
    )
    target_s = total_s - s_others - sdl_intra
    gi.targets.update(
        union=target_u,
        states=target_s,
        union_cash=total_u,
        states_cash=total_s,
        reissue=reissue,
        sdl_intra=sdl_intra,
        own_fpi_cen=own_fpi["G_CEN"],
        own_fpi_sta=own_fpi["G_STA"],
        external=external,
        states_other_internal=s_other_internal,
    )
    ctx.log(f"R3b: Union NAS-concept interest {target_u.v:,.2f} (cash {total_u.v:,.2f}); States {target_s.v:,.2f}")

    sat.method(
        "bridge.lines",
        "official",
        "Union MH 2049 lines (Finance Accounts 2023-24) and States' interest "
        "lines (RBI State Finances App. II), as published, each with the destination fincorp gives it.",
    )
    sat.method(
        "bridge.alloc",
        "estimated",
        "Government interest by T107 holder category and payer, as allocated "
        "for R3a (net of RBI and FPI parts); plus the derived bridge items and NAS-concept targets.",
    )
    dest = {
        **{k: "R3a dated securities (holders)" for k in [UNION_DATED]},
        **{k: "R3a T-bills (holders)" for k in UNION_TBILLS},
        **{k: "R3a other securities" for k in UNION_OTHER_SEC},
        **{k: "R3a E_BANK recap bonds" for k in UNION_RECAP},
        **{k: "R3a E_INSP public-account funds" for k in UNION_PUBLIC_ACCOUNT},
        UNION_WMA: "R3a E_RBI WMA",
        UNION_ITB: "R3 G_STA 14-day T-bills",
        UNION_GPF: "R9c gpf_union",
        **{k: "R8a gsec_direct" for k in UNION_SGB},
        **{k: "intra-G_CEN (NSSF): excluded; NSSF pays R8a small_savings" for k in UNION_NSSF},
        **{k: "intra-G_CEN: excluded" for k in UNION_INTRA_OTHER},
        **{k: "not interest (fee): excluded" for k in UNION_NOT_INTEREST},
        **{k: "recoveries of overpayments: excluded" for k in UNION_RECOVERIES},
    }
    for k, q in sorted(line.items()):
        d = "R14 external debt (rest_of_world)" if k.startswith(UNION_EXTERNAL_PREFIX) else dest.get(k, "zero")
        sat.add(f"union.line.{k}", q, key="bridge.lines", payer="G_CEN", item=f"MH 2049.{k}", destination=d)
    for k, q in sorted(subtotals.items()):
        sat.add(
            f"union.subtotal.{k}", q, key="bridge.lines", payer="G_CEN", item=f"MH 2049.{k}", destination="subtotal"
        )
    sat.add("union.total", total_u, key="bridge.lines", payer="G_CEN", item="MH 2049 total", destination="cash total")
    sat.add(
        "union.reissue_receipts",
        reissue,
        key="bridge.lines",
        payer="G_CEN",
        item="Receipt MH 0049.03.116 + .117",
        destination="deducted from dated-security interest (accrual)",
    )
    for sid, q, d in (
        ("states.central_loans", s_central, "R3 G_CEN central_loans"),
        ("states.market_loans", sdl, "R3a SDL holders"),
        ("states.nssf", s_nssf, "R3 G_CEN nssf"),
        ("states.other_internal_debt", s_other_internal, "R3a state_loans + R3a E_RBI wma_od"),
        ("states.small_savings_pf", s_pf, "R9c gpf_states"),
        ("states.others", s_others, "intra-G_STA (reserve funds, deposits): excluded"),
        ("states.total", total_s, "cash total"),
    ):
        sat.add(sid, q, key="bridge.lines", payer="G_STA", item=sid, destination=d)
    for (c, g), q in sorted(gi.by_cat.items()):
        sat.add(f"alloc.{g.lower()}.{c}", q, key="bridge.alloc", payer=g, item=c, destination="T107 holder category")
    for sid, g, q, d in (
        ("derived.union.nssf_to_savers", "G_CEN", gi.hh[("small_savings", "G_CEN")], "R8a small_savings (estimated)"),
        ("derived.union.fpi_own_formula", "G_CEN", own_fpi["G_CEN"], "memo: T107 FPI share x lines"),
        ("derived.union.fpi_in_r14", "G_CEN", fpi["dated"] + fpi["tbills"], "R14 (rest_of_world)"),
        ("derived.union.rbi_ar", "G_CEN", rbi_part["G_CEN"], "R3a E_RBI"),
        ("derived.states.fpi_in_r14", "G_STA", fpi["sdl"], "R14 (rest_of_world)"),
        ("derived.states.rbi_ar", "G_STA", rbi_part["G_STA"], "R3a E_RBI"),
        ("derived.states.sdl_held_by_states", "G_STA", sdl_intra, "intra-G_STA: excluded"),
        ("derived.states.wma_od_to_rbi", "G_STA", rbi_loans_by["G_STA"], "R3a E_RBI wma_od"),
        ("target.union_nas_concept", "G_CEN", target_u, "fincorp:r3b.union_nas_concept"),
        ("target.states_nas_concept", "G_STA", target_s, "fincorp:r3b.states_nas_concept"),
    ):
        sat.add(sid, q, key="bridge.alloc", payer=g, item=sid, destination=d)
    return gi
