"""Taxes block: product taxes by type (P7a) and their valuation layer (P7b), product and production
subsidies/taxes by government (P9a, P10a), government tax receipts by type (T1/T1a Union, T2/T2x States),
income taxes of households by group (T3, T3a) and corporation tax by paying sector (T4, T4a), and the IGST
settlement memo (S7). Plan: docs/phase2/plans/taxes.md (its s.8 and DECISIONS D2-4, D2-11, D2-12, D2-14 win).

Reads (period 2023-24 unless stated; vintage 'latest' everywhere, an explicit choice: each series below has one
vintage for the period used, except the RBI RTP tables where 2025-12-29 is named):
- io_tables_sut_supply / io_tables_sut_use (SUT 2023-24, 31 Aug 2026): product taxes, subsidies, imports, output,
  PFCE/GFCF/exports by SUT product; data/concordance/io_tables_sut_product_to_sam34.csv.
- union_fiscal_rb_receipts (Receipt Budget 2025-26, actuals 2023-24; 2022-23 actuals from the 2024-25 budget),
  union_fiscal_fa_receipts / _fa_expenditure (Finance Accounts 2023-24), union_fiscal_exp_profile (St 7),
  union_fiscal_ppac_exchequer (PPAC, 2026-07-17), union_fiscal_pib_gst (Apr-May 2023).
- state_fiscal_rbi_sf_appendices (RBI State Finances, App I, accounts 2023-24, all States + UTs with legislature),
  state_fiscal_fc16_subsidies, state_fiscal_fc16_state_accounts (MH 0028, 2022-23), state_fiscal_ulb_cityfinance.
- mospi_nas_2026_s1_1, _s4_2, _s7_1 (NAS 2026); mospi_nas_2026_oldbase_soa_s2_1/s2_2/s3_1/s3_2/s5_0 (old base,
  NAS 2024 vintage, 2022-23 FRE); io_tables_ifpri_2223_datapaper (2022-23).
- finsector_markets_irdai_life / _nonlife (tax provisions), rbi_banking_corporate_rtp_nbfi / _coop / _banks
  (2025-12-29), rbi_financial_accounts_fsf_balance_sheets (end-March 2024), hces_consumption_a2_fractile_persons
  (2023-08/2024-07).
- production (entries P2, P5, P8, P9, P10, I3; constraints product_taxes.*, pfce.*, gfce.*, gfcf.*, valuables.*),
  households (satellites hh_group_map and, if published, hh_national_quintile_xwalk), factors (F1a F_LREG entries).

Writes entries: P7a (T_CGST..T_OPRT <- C_*, free), T1a (G_CEN <- tax accounts), T2x (G_STA <- tax accounts),
P9a (G_* <- T_PSUB), P10a (G_* <- T_PROD, components stamps_registration, land_revenue, property_tax,
other_production_taxes, gross_subsidies), T3 (T_PIT <- E_NFPR/E_BANK, quasi_corporate), T3a (T_PIT <- H_*,
income_tax and professions_tax), T4a (T_CIT <- E_*, FC accounts public/private). T1, T2, T4 are constraints only.
Satellites: p7a_precheck, p7b_tax_by_use (P7b), p9a_by_commodity, p10a_items, direct_tax_split, t3a_sensitivity,
s7_igst_settlement (S7), tax_classification (T1a; read by government).

Estimated (and how): P7a split by type (row = cash receipts scaled to the SUT total, column = SUT, RAS on a
product-level prior); T1a/T2x product-tax receipts (= P7a row totals split by cash shares: a cash-accrual/coverage
gap, not an accrual estimate); P9a/P10a payer split (identified heads, States residual); T3 household share of
MH 0021 (old-base NAS 2022-23); T3a (threshold-excess key on HCES fractiles, low confidence: no CBDT data);
T4a (old-base NAS D5 shares + IRDAI/RTP provisions, E_BANK residual split public/private by RTP bank net
profit). Skipped: nothing; see docs/phase2/issues/taxes.md for every default and conflict.
"""

from __future__ import annotations

import polars as pl

from pipeline.sam.framework import BlockContext, BlockResult, SamError, Satellite, constraint, entry

from . import direct, memo, p7a, subsidies
from .common import EXP, FA, NAS11, NAS71, PRODUCT_TAX_ACCOUNTS, SUPPLY, pids
from .receipts import read_cash

BLOCK = "taxes"
REFS = ["P7a", "P7b", "P9a", "P10a", "T1", "T1a", "T2", "T2x", "T3", "T3a", "T4", "T4a", "S7"]
DEPENDS = ["production", "households", "factors"]

CHECK_TOL = 5.0
# the source a mixed-input record mainly rests on (framework: must be among its inputs' sources)
SRC_RB, SRC_SF, SRC_FA = "mof_union_budget_2026_27", "rbi_state_finances_study", "cga_finance_accounts_aag"
SRC_SUT, SRC_NAS, SRC_OLD = "mospi_sut_2022base", "mospi_nas_2026_publication", "mospi_nas_old_base_2011_12"
SRC_HCES = "mospi_hces_2023_24"
BANDS_T1 = {"T_CGST": 0.05, "T_GCES": 0.05, "T_UEXC": 0.05}
BANDS_T2 = {"T_SGST": 0.05, "T_SVAT": 0.15, "T_SEXC": 0.15}


def _sat(ref: str, rows: list[dict], dims: list[str], pid: str, status: str, desc: str, unit_col: bool = False,
         decimals: int = 6) -> Satellite:  # fmt: skip
    schema = {"series_id": pl.String, **{d: pl.String for d in dims}, "value": pl.Float64, "unit": pl.String,
              "status": pl.String, "prov_id": pl.String}  # fmt: skip
    data = [
        {"series_id": r["series_id"], **{d: (None if r.get(d) is None else str(r[d])) for d in dims},
         "value": float(r["value"]), "unit": r.get("unit", "INR_crore") if unit_col else "INR_crore",
         "status": status, "prov_id": pid}
        for r in rows
    ]  # fmt: skip
    return Satellite(ref, pl.DataFrame(data, schema=schema, orient="row"), desc, decimals)


def build(ctx: BlockContext) -> BlockResult:
    acc = ctx.accounts
    hh = acc.in_group("HH")
    entries: list[dict] = []
    cons: list[dict] = []
    sats: dict[str, Satellite] = {}

    prod_e = ctx.block_entries("production")
    prod_c = ctx.block_constraints("production")
    cash = read_cash(ctx)

    # =============================================================================================
    # P7a: product taxes by type within commodity
    # =============================================================================================
    rows, oprt = p7a.rows_and_items(cash)
    sut = p7a.read_sut(ctx)
    ppac, ppac_ids = p7a.read_ppac(ctx)
    loads = p7a.build_prior(sut, rows, oprt, ppac)
    npv_products = sorted({ld.product.removeprefix("sut_") for ld in loads if ld.component == p7a.NON_POL_VAT})
    items = p7a.cells_from_loads(loads, sut.commodity)
    pc = prod_c.filter(pl.col("constraint_id").str.starts_with("product_taxes."))
    cols = {r["constraint_id"].split(".", 1)[1].upper(): r["target"] for r in pc.iter_rows(named=True)}
    fit = p7a.fit(items, rows, cols, ctx)
    itemv = p7a.item_values(items, fit)
    s = sum(cols.values()) / sum(rows.values())
    ctx.log(f"P7a: cash rows {sum(rows.values()):,.2f} scaled by {s:.6f} to the SUT total {sum(cols.values()):,.2f}; "
            f"RAS {fit.iterations} iterations, max row error {fit.max_rel_err:.2e}")  # fmt: skip
    moved = {a: fit.row_final[a] - fit.row_target[a] for a in rows if fit.row_final[a] != fit.row_target[a]}
    if moved:
        ctx.warn(f"P7a pre-check moved row targets (infeasible under the SUT columns): {moved}")
    pc_pid = sorted(set(pc["prov_id"].to_list()))
    p7a_pid = ctx.prov(
        ref="P7a",
        status="estimated",
        inputs=pids(sut.prov_ids, ppac_ids, cash.pids(), pc_pid),
        source_id="mospi_sut_2022base",
        notes="Assumptions: shape parameters of the prior (CESS_FACTOR 0.5, legal-base products, non-ITC list) and "
        "the licence-fee fallback; see method.",
        method="Gap map P7a: SUT 2023-24 product taxes by commodity (production's P7 targets, columns, exact) split "
        "into CGST, SGST, compensation cess, Union excise, State VAT, State excise and other product taxes. Rows = "
        "Union (Receipt Budget 2025-26 actuals) + State (RBI State Finances App I, all States + UTs) cash receipts "
        "by account (T_CGST = MH 0005 + MH 0008 + UTGST MH 0007; T_OPRT includes State + UT motor-vehicle tax "
        "(DECISIONS D2-4), electricity duty, goods and passengers, entertainment, other; Union MH 0044, MH 0045, "
        "export duty and CTT (D2-12)), scaled by one factor (SUT total / cash total) so the TAX-1 gap is spread "
        "pro rata (uniform scaling: an assumption), then a transportation-LP pre-check on the prior's pattern. "
        "Prior at SUT-product level: PPAC petroleum heads on p085 (excise, VAT, entry tax/octroi, GST = PPAC CGST "
        "and SGST/UTGST plus PPAC IGST split between the CGST and SGST priors in the ratio of their row targets; "
        "royalty and customs excluded; PPAC centre.a.others (51.50, unidentified) is not placed: the rows are cash, "
        "so it stays wherever it sits in them); PPAC cess + NCCD on crude on p043/p044 pro rata to their SUT tax "
        "(the SUT C_OILG tax equals it to the rupee); Union excise other than PPAC excise, cess and NCCD on p069 "
        "tobacco; State + UT excise on p065 "
        "up to its SUT tax, the excess as licence_fee_excess on p134 hotels and p132 trade pro rata to their SUT "
        "tax (gap-map fallback); electricity duty on p128; vehicle tax on p120/p121/p122 pro rata to PFCE + GFCF; "
        "goods and passengers on p136; entertainment on p155; MH 0045 on p149/p141 pro rata to imports; export "
        f"duty on goods (SUT products p001-p{p7a.GOODS_MAX:03d} that carry SUT product tax) pro rata to their "
        "exports; CTT on p142; non-petroleum VAT (State + UT sales tax less PPAC VAT on POL; component "
        f"{p7a.NON_POL_VAT}, low confidence) pro rata to the room left on p065, p043, p085 (it lands on "
        f"{', '.join(npv_products)}; on p085 beyond PPAC it is plan fallback (b)); "
        "MH 0044 + State other taxes less the PPAC entry tax/octroi pro rata to the GST residual "
        "(SUT tax less the loads above, GST products only: not p043, p044, p065, p085, p128); compensation cess "
        f"= {p7a.CESS_FACTOR} x GST residual on p064, p066, p069, p120, the rest pro rata to the GST residual of "
        "the other GST products except coal p042; CGST : SGST = their row targets on the rest. Aggregated to "
        "commodities with io_tables_sut_product_to_sam34; RAS to the targets (1e-10). No GST-rate schedule is "
        "ingested, so the SUT's own residual (MoSPI's PFCE x item-rate allocation) is the GST shape.",
        locator="union_fiscal_rb_receipts, state_fiscal_rbi_sf_appendices, union_fiscal_ppac_exchequer, "
        "io_tables_sut_supply/use, production constraints product_taxes.*",
    )
    for r in fit.cells.iter_rows(named=True):
        entries.append(entry(r["account"], r["commodity"], "P7a", r["value"], prov_id=p7a_pid, status="estimated",
                             role="free", component=r["component"],
                             confidence=p7a.confidence(r["account"], r["component"], r["commodity"])))  # fmt: skip
    sut_total, sut_total_pid = _sut_total(ctx, "product_taxes")
    p7t_pid = ctx.prov(
        ref="P7a", status="official", inputs=pc_pid,
        method="Gap map P7a total: the sum of production's P7 constraint targets (SUT 2023-24 product taxes by "
        "commodity, pure aggregation); allowance Rs 1 crore.",
    )  # fmt: skip
    cons.append(constraint("p7a.total", "P7a", PRODUCT_TAX_ACCOUNTS, acc.in_group("COM"), sum(cols.values()),
                           prov_id=p7t_pid, tol_abs=1.0, refs=["P7a"],
                           description="P7a entries add up to the SUT product-tax total (per-commodity totals are "
                           "production's product_taxes.* constraints, not re-declared: XR-15)"))  # fmt: skip

    # =============================================================================================
    # T1a / T2x: receipts by government (product taxes = P7a row totals split by cash shares)
    # =============================================================================================
    t1a_pid = ctx.prov(
        ref="T1a", status="estimated", inputs=[p7a_pid, *cash.pids()], source_id=SRC_RB,
        method="Gap map T1a: Union product-tax receipts by type = the P7a row total of each tax account x the "
        "Union's share of that account's cash (RB 2025-26 actuals; UTs without legislature are Union: UT sales tax, "
        "State excise, vehicle tax, goods & passengers, electricity duty). The difference from cash is the "
        "pro-rata share of the TAX-1 gap plus pre-check moves (a cash-accrual/coverage gap, not an accrual "
        "estimate). T_CGST is written in two components: total (CGST + unsettled IGST) and utgst (MH 0007).",
    )  # fmt: skip
    t2x_pid = ctx.prov(
        ref="T2x", status="estimated", inputs=[p7a_pid, *cash.pids()], source_id=SRC_SF,
        method="Gap map T2x: State product-tax receipts by type = the P7a row total of each tax account x the "
        "States' share of that account's cash (RBI SF App I 2023-24 accounts, all States + UTs with legislature). "
        "The difference from cash is the pro-rata TAX-1 gap share plus pre-check moves (cash-accrual/coverage gap).",
    )  # fmt: skip
    row_tot = {a: sum(r["value"] for r in fit.cells.iter_rows(named=True) if r["account"] == a)
               for a in PRODUCT_TAX_ACCOUNTS}  # fmt: skip
    for a in PRODUCT_TAX_ACCOUNTS:
        c_cash, s_cash = cash.by_account(a, "G_CEN"), cash.by_account(a, "G_STA")
        tot = c_cash + s_cash
        if a == "T_CGST":
            ut = cash.get("utgst").value
            entries.append(entry("G_CEN", a, "T1a", row_tot[a] * (c_cash - ut) / tot, prov_id=t1a_pid,
                                 status="estimated", role="free", confidence="medium"))  # fmt: skip
            entries.append(entry("G_CEN", a, "T1a", row_tot[a] * ut / tot, prov_id=t1a_pid, status="estimated",
                                 role="free", confidence="medium", component="utgst"))  # fmt: skip
            continue
        if c_cash:
            entries.append(entry("G_CEN", a, "T1a", row_tot[a] * c_cash / tot, prov_id=t1a_pid, status="estimated",
                                 role="free", confidence="medium"))  # fmt: skip
        if s_cash:
            entries.append(entry("G_STA", a, "T2x", row_tot[a] * s_cash / tot, prov_id=t2x_pid, status="estimated",
                                 role="free", confidence="medium"))  # fmt: skip
    # customs: = production's P8 entries (fixed)
    p8 = prod_e.filter(pl.col("ref") == "P8")
    cust_pid = ctx.prov(
        ref="T1a", status="official", inputs=sorted(set(p8["prov_id"].to_list())),
        method="Gap map T1a: Union customs receipts (G_CEN <- T_CUST) = the sum of production's P8 entries (SUT "
        "import duty by commodity), pure aggregation; the cash figure less export duty is the T1 band.",
    )  # fmt: skip
    entries.append(entry("G_CEN", "T_CUST", "T1a", float(p8["value"].sum()), prov_id=cust_pid, status="official",
                         role="fixed"))  # fmt: skip

    # =============================================================================================
    # T3 / T3a / T4 / T4a: direct taxes
    # =============================================================================================
    t3 = direct.t3_split(ctx, cash)
    pit_cash = cash.x("taxes_on_income") + cash.x("wealth_tax")
    pit_in = pids(cash.xp("taxes_on_income"), cash.xp("wealth_tax"))
    pit_pid = ctx.prov(
        ref="T1a", status="official", inputs=pit_in,
        method="Gap map T1a: Union taxes on income other than corporation tax, cash = RB 'total taxes on income' "
        "(MH 0021 + STT MH 0034 + MH 0023/0024/0026/0028) + wealth/estate duty arrears (MH 0031/0032), gross of "
        "devolution; anchored at 0.5% (no accrual data).",
    )  # fmt: skip
    entries.append(entry("G_CEN", "T_PIT", "T1a", pit_cash, prov_id=pit_pid, status="official", role="anchored",
                         tol_rel=0.005))  # fmt: skip
    cit_pid = ctx.prov(
        ref="T1a", status="official", inputs=cash.xp("cit"),
        method="Gap map T1a: corporation tax (MH 0020) cash, RB 2025-26 actuals, gross of devolution; anchored "
        "at 0.5% (no accrual data).",
    )  # fmt: skip
    entries.append(entry("G_CEN", "T_CIT", "T1a", cash.x("cit"), prov_id=cit_pid, status="official",
                         role="anchored", tol_rel=0.005))  # fmt: skip
    spit_pid = ctx.prov(
        ref="T2x", status="official", inputs=cash.xp("state_income_taxes"),
        method="Gap map T2x (DECISIONS D2-17): State taxes on income (professions tax + agricultural income tax), "
        "RBI SF App I 2023-24 accounts; anchored at 1%.",
    )  # fmt: skip
    entries.append(entry("G_STA", "T_PIT", "T2x", cash.x("state_income_taxes"), prov_id=spit_pid,
                         status="official", role="anchored", tol_rel=0.01))  # fmt: skip

    qc_pid = ctx.prov(
        ref="T3", status="estimated", inputs=pids(t3.inputs_share, t3.inputs_qc_bank, cash.xp("mh0021"),
                                                  cash.xp("firm_heads")),
        source_id=SRC_OLD,
        method="Gap map T3 extension (DECISIONS D2-11, D2-17): income tax paid by quasi-corporations = "
        f"(1 - {t3.share:.6f}) x MH 0021 (RB Sum of rb.tr.0021.*) + firm-only heads MH 0023/0024/0026. The household "
        "share = (old-base NAS 2022-23 household D5 (oldbase_soa_s5_0) - professions tax 2022-23 (FC16 State "
        "accounts MH 0028)) / MH 0021 2022-23 (old base, NAS 2024 vintage, 2022-23 FRE; cross-check IFPRI 2022-23 "
        f"household taxes / MH 0021 = {t3.ifpri_share:.4f}). Co-operative banks' tax provisions (RBI RTP 2025-12-29, "
        "UCB) go to E_BANK (private, D2-14); the rest to E_NFPR.",
    )  # fmt: skip
    entries.append(entry("T_PIT", "E_NFPR", "T3", t3.qc_nfpr, prov_id=qc_pid, status="estimated", role="free",
                         confidence="low", component="quasi_corporate"))  # fmt: skip
    entries.append(entry("T_PIT", "E_BANK", "T3", t3.qc_bank, prov_id=qc_pid, status="estimated", role="free",
                         confidence="low", component="quasi_corporate"))  # fmt: skip

    # T3a key
    hgm = ctx.satellite("households", "hh_group_map")
    table = direct.fractile_table(hgm)
    try:
        xwalk = ctx.satellite("households", "hh_national_quintile_xwalk")
    except SamError:
        xwalk = None
        ctx.warn("households publishes no hh_national_quintile_xwalk: T3a saving rates use IFPRI quintile n for "
                 "H_Rn/H_Un (logged in docs/phase2/issues/taxes.md)")  # fmt: skip
    fr = direct.fractiles(ctx, table, sorted(set(hgm["prov_id"].to_list())), xwalk)
    keys = {th: direct.t3a_key(fr, th) for th in direct.SENSITIVITY}
    key = keys[direct.THRESHOLD]
    hh_sat_ids = sorted(set(xwalk["prov_id"].to_list())) if xwalk is not None else []
    t3a_pid = ctx.prov(
        ref="T3a", status="estimated", inputs=pids(fr.inputs, t3.inputs_share, cash.xp("mh0021"), cash.xp("stt"),
                                                   cash.xp("mh0028"), cash.xp("wealth_tax"), hh_sat_ids),
        source_id=SRC_HCES,
        notes="No open input (ISSUES P1-4: CBDT data blocked); low confidence; very sensitive to the threshold "
        "(t3a_sensitivity).",
        method="Gap map T3a: household income tax (Union: household share of MH 0021 + STT + MH 0028 + MH 0031/32) "
        "split over the 10 groups by a threshold-excess key: for each HCES 2023-24 fractile class f (A2, "
        "2023-08/2024-07; class -> group from households' hh_group_map), income per household Y_f = 12 x MPCE_f x "
        "persons_f / households_f x k / (1 - s_g) (persons, households, MPCE as published in hh_group_map), "
        f"k = NAS 1.1 PFCE / HCES aggregate = {fr.k:.4f}, s_g = saving "
        f"rate ({fr.saving_note}); key_g = Sum_f households_f x max(0, Y_f - Y*), Y* = Rs {direct.THRESHOLD:,.0f} "
        "per household (the 2023-24 new-regime rebate limit, Finance Act 2023: an assumption parameter). Uniform "
        "NAS scaling and fractile averages bias the key toward R5 and away from the very top.",
    )  # fmt: skip
    for g in hh:
        if key.get(g, 0) > 0:
            entries.append(entry("T_PIT", g, "T3a", t3.hh_income_tax * key[g], prov_id=t3a_pid, status="estimated",
                                 role="free", confidence="low", component="income_tax"))  # fmt: skip
    f1a = ctx.block_entries("factors").filter((pl.col("ref") == "F1a") & (pl.col("col") == "F_LREG"))
    ce = {r["row"]: r["value"] for r in f1a.group_by("row", maintain_order=True).agg(pl.col("value").sum())
          .iter_rows(named=True)}  # fmt: skip
    if not ce or sum(ce.values()) <= 0:
        raise SamError("factors publishes no F1a entries F_LREG -> H_* (professions-tax key)")
    pt_pid = ctx.prov(
        ref="T3a", status="estimated",
        inputs=pids(cash.xp("state_income_taxes"), sorted(set(f1a["prov_id"].to_list()))), source_id=SRC_SF,
        method="Gap map T3a: State taxes on income (professions tax 7,872.88 + agricultural income tax, RBI SF App I "
        "2023-24) split over the 10 groups by regular-wage compensation of employees (factors' F1a entries "
        "H_* <- F_LREG); component professions_tax (plan C4: a tax on income, D5).",
    )  # fmt: skip
    ce_tot = sum(ce.values())
    for g in hh:
        if ce.get(g, 0) > 0:
            entries.append(entry("T_PIT", g, "T3a", t3.state_taxes * ce[g] / ce_tot, prov_id=pt_pid,
                                 status="estimated", role="free", confidence="low",
                                 component="professions_tax"))  # fmt: skip

    t4 = direct.t4a_split(ctx, cash, t3)
    t4a_pid = ctx.prov(
        ref="T4a", status="estimated", inputs=pids(t4.inputs_shares, t4.inputs_fc, cash.xp("cit"), [qc_pid]),
        source_id=SRC_OLD,
        method="Gap map T4a: corporation tax (MH 0020, RB cash) by paying sector. Corporate D5 prior = CIT + "
        "quasi-corporate MH 0021 (T3), split by old-base NAS 2022-23 D5 shares of public NFC, private NFC, public "
        "FC, private FC (oldbase_soa_s2_1/s2_2/s3_1/s3_2, NAS 2024 vintage); the quasi-corporate part is removed "
        "from the private sectors. FC sub-sectors bottom-up: E_INSP = IRDAI 2023-24 provisions for tax (life "
        "t24 + t25; non-life t51; public = LIC, public and specialised general insurers); E_NBFC = RBI RTP "
        "2025-12-29 tax provisions of NBFC-UL, NBFC-ML, HFCs and AIFIs, less the deposit-taking share (FSF "
        "end-March 2024 assets, fc_odc_nbfc_dt / fc_odc_hfc_dt) moved to E_BANK (XR-6; assumed private); NBFC public "
        "part = AIFIs + old-base public share of FC D5 on the rest; E_BANK = FC total - E_INSP - E_NBFC (residual). "
        "Within E_BANK (plan s.2.7 step 4): the moved deposit-taking share is private; the rest is split by RBI RTP "
        "2025-12-29 net profit 2023-24, public = PSBs + RRBs, private = PVBs + foreign + small finance + payments "
        "banks + local area banks (tax by bank group is not published; net profit assumes equal effective tax "
        f"rates; public share {t4.detail['bank_public_share_net_profit']:.4f}). E_RBI pays none (RBI Act s.48). "
        "Constraint bands t4a.fc and t4a.nfpu (public NFCs, audit BS-10): +-25% around the prior, a judgement "
        "tolerance with no source (t4a.nfpu copies t4a.fc's). The old-base series behind the shares "
        "(oldbase_soa_s2_1..s3_2, 2011-12 to 2022-23) puts 2022-23 at the lowest public NFC share of its 12 years, "
        "so the band is narrow on the upside; it can bind and then sets the level (close-out V-TX-6; Checkpoint B "
        "with taxes-27).",
    )  # fmt: skip
    for (a, comp), v in t4.cells.items():
        conf = "medium" if a in ("E_INSP", "E_NBFC") else "low"
        entries.append(entry("T_CIT", a, "T4a", v, prov_id=t4a_pid, status="estimated", role="free",
                             confidence=conf, component=comp))  # fmt: skip

    # =============================================================================================
    # P9a / P10a
    # =============================================================================================
    p9 = prod_e.filter(pl.col("ref") == "P9")
    p9s = subsidies.p9a_split(ctx, p9)
    p9_pids = sorted(set(p9["prov_id"].to_list()))
    p9a_pid = ctx.prov(
        ref="P9a", status="estimated", inputs=pids(p9_pids, p9s.inputs), source_id=SRC_SUT,
        method="Gap map P9a: SUT product subsidies (production's P9 entries) by paying government, commodity by "
        "commodity: C_CHEM, C_TREQ, C_RPET Union; C_UTIL, C_LVST, C_FOFI States; C_CROP Union = PM-AASHA (St 7), "
        "rest States; C_FINS Union = MISS (St 7), rest States; C_TRNS Union = air transport p137, rest States; "
        "C_TRAD States = FC16 21 States' food subsidies (XR-23, not grossed up), and the unexplained rest (C_TRAD "
        f"remainder, C_OSRV, C_EDUC, C_HLTH, C_BSRE, C_COMM, C_CNST) at the identified Centre share {p9s.ratio:.4f} "
        "(gap map Q7 rule).",
    )  # fmt: skip
    entries.append(entry("G_CEN", "T_PSUB", "P9a", p9s.centre, prov_id=p9a_pid, status="estimated", role="free",
                         confidence="medium"))  # fmt: skip
    entries.append(entry("G_STA", "T_PSUB", "P9a", p9s.state, prov_id=p9a_pid, status="estimated", role="free",
                         confidence="medium"))  # fmt: skip
    p9tot_pid = ctx.prov(ref="P9a", status="official", inputs=p9_pids,
                         method="Gap map P9a total: the sum of production's P9 entries (SUT product subsidies), "
                         "pure aggregation.")  # fmt: skip
    cons.append(constraint("p9a.total", "P9a", ["G_CEN", "G_STA"], ["T_PSUB"], float(p9["value"].sum()),
                           prov_id=p9tot_pid, tol_abs=0.5, refs=["P9a"],
                           description="Product subsidies paid by the two governments = SUT P9 total"))  # fmt: skip
    cons.append(constraint("p9a.centre", "P9a", ["G_CEN"], ["T_PSUB"], p9s.centre_identified, prov_id=p9a_pid,
                           tol_rel=0.35, kind="band", refs=["P9a"],
                           description="Union product subsidies near its identified heads (St 7 fertiliser, LPG, "
                           "MISS, PM-AASHA, UDAN, EV); the unexplained C_TRAD row is 18% of P9"))  # fmt: skip

    p10 = prod_e.filter(pl.col("ref") == "P10")
    p10_pids = sorted(set(p10["prov_id"].to_list()))
    p10s = subsidies.p10a_split(ctx, cash, p10, p10_pids)
    p10_tax_pid = ctx.prov(
        ref="P10a", status="derived", inputs=pids(*(i["inputs"] for i in p10s.items if i["value"] > 0)),
        source_id=SRC_NAS,
        method="Gap map P10a (gross taxes): gross D29 = NAS 4.2 GG subsidies (D31 + D39) - NAS 1.1 product "
        f"subsidies + P10 net (= {p10s.d29:,.2f}). Identified heads: Union stamps (MH 0030 + UT MH 0710) and UT "
        "land revenue; States' stamps and registration fees, land revenue (RBI SF App I), property tax = urban "
        "immovable property tax (App I) + cityfinance ULB property tax (284 ULBs only); other_production_taxes = "
        "D29 residual. Cash used as accrual; anchored at 3% (the residual is free).",
    )  # fmt: skip
    p10_sub_pid = ctx.prov(
        ref="P10a", status="estimated", inputs=pids(*(i["inputs"] for i in p10s.items if i["value"] < 0)),
        source_id=SRC_NAS,
        method="Gap map P10a (gross subsidies): gross D39 = NAS 4.2 GG subsidies - NAS 1.1 product subsidies "
        f"(= {p10s.d39:,.2f}); Union = St 7 interest subsidies less MISS and the LIC pension subsidy (government "
        "R18) + St 7 other subsidies less PM-AASHA + FC16 Union 'business' subsidies; States = the residual (low "
        "confidence). PM-KISAN (FA 2401.00.130) is not a D39 head (DECISIONS D2-24): NAS 4.2 does not itemise "
        "PM-KISAN, so its NAS treatment is inferred: St 4.2 current expenditure = consumption + subsidies + current "
        "transfers (subsidies and transfers are disjoint), and COFOG 04.agri current transfers are large enough to "
        "hold it, so it is taken to be outside the NAS subsidy total D39 is derived from; government writes it as "
        "R10 (government-30).",
    )  # fmt: skip
    for i in p10s.items:
        if i["component"] == "gross_subsidies":
            entries.append(entry(i["gov"], "T_PROD", "P10a", i["value"], prov_id=p10_sub_pid, status="estimated",
                                 role="free", confidence="low", component="gross_subsidies"))  # fmt: skip
        elif i["component"] == "other_production_taxes":
            entries.append(entry(i["gov"], "T_PROD", "P10a", i["value"], prov_id=p10_tax_pid, status="derived",
                                 role="free", confidence="low", component=i["component"]))  # fmt: skip
        else:
            entries.append(entry(i["gov"], "T_PROD", "P10a", i["value"], prov_id=p10_tax_pid, status="derived",
                                 role="anchored", tol_rel=0.03, component=i["component"]))  # fmt: skip
    p10net_pid = ctx.prov(ref="P10a", status="official", inputs=p10_pids,
                          method="Gap map P10a net: the sum of production's P10 entries (SUT net production taxes), "
                          "pure aggregation.")  # fmt: skip
    gov = ["G_CEN", "G_STA"]
    cons += [
        constraint("p10a.net", "P10a", gov, ["T_PROD"], p10s.net, prov_id=p10net_pid, tol_abs=0.5, refs=["P10a"],
                   description="Net production taxes received by the two governments = SUT P10 total"),
        constraint("p10a.gross_taxes", "P10a", gov, ["T_PROD"], p10s.d29, prov_id=p10_tax_pid, tol_rel=0.03,
                   kind="band", refs=["P10a"],
                   components=["stamps_registration", "land_revenue", "property_tax", "other_production_taxes"],
                   description="Gross other taxes on production (D29) = NAS 4.2 - 1.1 identity + P10 (XR-20)"),
        constraint("p10a.gross_subsidies", "P10a", gov, ["T_PROD"], -p10s.d39, prov_id=p10_sub_pid, tol_rel=0.03,
                   kind="band", refs=["P10a"], components=["gross_subsidies"],
                   description="Gross other subsidies on production (D39) = NAS 4.2 GG subsidies - NAS 1.1 product "
                   "subsidies (XR-20)"),
        constraint("p10a.centre_net", "P10a", ["G_CEN"], ["T_PROD"],
                   sum(i["value"] for i in p10s.items if i["gov"] == "G_CEN"), prov_id=p10_sub_pid, tol_rel=0.30,
                   kind="band", refs=["P10a"], description="Union net production taxes near its identified heads"),
    ]  # fmt: skip

    # =============================================================================================
    # constraints T1, T2, T3, T4, T4a
    # =============================================================================================
    t1_pid = ctx.prov(
        ref="T1", status="official", inputs=cash.pids(gov="G_CEN") + cash.xp("customs") + cash.xp("export_duty")
        + pit_in + cash.xp("cit"),
        method="Gap map T1: Union tax receipts by type, cash as published (Receipt Budget 2025-26, actuals 2023-24), "
        "mapped to the NAS accounts: CGST = MH 0005 + MH 0008 (unsettled IGST) + MH 0007 UTGST; customs = MH 0037 "
        "less export duty and export cesses (TAX-2 bridge); taxes on income incl. STT and wealth-tax arrears.",
    )  # fmt: skip
    for a, tol in BANDS_T1.items():
        cons.append(constraint(f"t1.{a[2:].lower()}", "T1", ["G_CEN"], [a], cash.by_account(a, "G_CEN"),
                               prov_id=t1_pid, tol_rel=tol, kind="band", refs=["T1a"],
                               description=f"Union {a} receipts near cash (band {tol:.0%})"))  # fmt: skip
    cons += [
        constraint("t1.cust", "T1", ["G_CEN"], ["T_CUST"], cash.x("customs") - cash.x("export_duty"), prov_id=t1_pid,
                   tol_rel=0.01, kind="band", refs=["T1a"],
                   description="Union customs (import duties) near cash less export duty (band 1%)"),
        constraint("t1.pit", "T1", ["G_CEN"], ["T_PIT"], pit_cash, prov_id=t1_pid, tol_rel=0.005, kind="band",
                   refs=["T1a"], description="Union taxes on income other than CIT near cash (band 0.5%)"),
        constraint("t1.cit", "T1", ["G_CEN"], ["T_CIT"], cash.x("cit"), prov_id=t1_pid, tol_rel=0.005, kind="band",
                   refs=["T1a"], description="Corporation tax near cash (band 0.5%)"),
    ]  # fmt: skip
    t2_pid = ctx.prov(
        ref="T2", status="official", inputs=cash.pids(gov="G_STA"),
        method="Gap map T2: State tax receipts by type, cash as published (RBI State Finances 2025-26, App I, "
        "accounts 2023-24, all States + UTs with legislature); own-tax lines only (devolution is R1).",
    )  # fmt: skip
    for a, tol in BANDS_T2.items():
        cons.append(constraint(f"t2.{a[2:].lower()}", "T2", ["G_STA"], [a], cash.by_account(a, "G_STA"),
                               prov_id=t2_pid, tol_rel=tol, kind="band", refs=["T2x"],
                               description=f"State {a} receipts near cash (band {tol:.0%})"))  # fmt: skip
    t3_tot_pid = ctx.prov(
        ref="T3", status="derived", inputs=pids(pit_in, cash.xp("state_income_taxes")), source_id=SRC_RB,
        method="Gap map T3 total: Union taxes on income other than CIT (RB total taxes on income + MH 0031/0032) + "
        "State taxes on income (RBI SF App I), cash.",
    )  # fmt: skip
    t3_hh_pid = ctx.prov(
        ref="T3", status="estimated", inputs=pids(t3.inputs_share, pit_in, cash.xp("state_income_taxes")),
        source_id=SRC_OLD,
        method="Gap map T3 households: household share of MH 0021 (old-base NAS 2022-23) x MH 0021 + STT + MH 0028 "
        "+ MH 0031/0032 + State taxes on income; band 10% (old base 0.786 vs IFPRI 0.902).",
    )  # fmt: skip
    cons += [
        constraint("t3.total", "T3", ["T_PIT"], [*hh, "E_NFPR", "E_BANK"], pit_cash + cash.x("state_income_taxes"),
                   prov_id=t3_tot_pid, tol_abs=1.0, refs=["T3", "T3a"],
                   description="Taxes on income other than CIT paid by households and quasi-corporations = cash"),
        constraint("t3.households", "T3", ["T_PIT"], hh, t3.household_total, prov_id=t3_hh_pid, tol_rel=0.10,
                   kind="band", refs=["T3a"], description="Household income taxes near the old-base share (10%)"),
    ]  # fmt: skip
    t4_pid = ctx.prov(ref="T4", status="official", inputs=cash.xp("cit"),
                      method="Gap map T4: corporation tax (MH 0020, RB 2025-26 actuals), as published.")  # fmt: skip
    cons.append(constraint("t4.total", "T4", ["T_CIT"], ["E_NFPU", "E_NFPR", "E_BANK", "E_NBFC", "E_INSP"],
                           cash.x("cit"), prov_id=t4_pid, tol_abs=1.0, refs=["T4a"],
                           description="Corporation tax by paying sector adds up to MH 0020"))  # fmt: skip
    cons += [
        constraint("t4a.fc", "T4a", ["T_CIT"], ["E_BANK", "E_NBFC", "E_INSP"], t4.fc_total, prov_id=t4a_pid,
                   tol_rel=0.25, kind="band", refs=["T4a"],
                   description="FC corporation tax near the old-base FC share (band 25%)"),
        constraint("t4a.insp", "T4a", ["T_CIT"], ["E_INSP"], t4.insp_target, prov_id=t4a_pid, tol_rel=0.15,
                   kind="band", refs=["T4a"], description="Insurers' tax near IRDAI provisions (band 15%)"),
        constraint("t4a.nbfc", "T4a", ["T_CIT"], ["E_NBFC"], t4.nbfc_target, prov_id=t4a_pid, tol_rel=0.15,
                   kind="band", refs=["T4a"], description="NBFC/HFC/AIFI tax near RBI RTP provisions (band 15%)"),
        # audit BS-10 (2026-10-01): balancing raised public NFCs' corporation tax 64% with no CPSE tax source
        # (taxes-27); like t4a.fc, the old-base public NFC share of corporate D5 is held within 25%
        constraint("t4a.nfpu", "T4a", ["T_CIT"], ["E_NFPU"], t4.cells[("E_NFPU", "total")], prov_id=t4a_pid,
                   tol_rel=0.25, kind="band", refs=["T4a"],
                   description="Public NFC corporation tax near the old-base public NFC share (band 25%, as t4a.fc)"),
    ]  # fmt: skip

    # =============================================================================================
    # satellites
    # =============================================================================================
    sats["p7a_precheck"] = _precheck_sat(fit, rows, cols, itemv, cash, p7a_pid)
    uses = p7a.uses_by_commodity(prod_e, prod_c)
    bvtb_alco = sut.output.get(p7a.P_ALCO, 0.0) / sum(
        v for p, v in sut.output.items() if sut.commodity.get(p) == "C_BVTB"
    )
    b, fb = p7a.p7b(itemv.filter(pl.col("final") > 0), uses, bvtb_alco)
    if fb:
        ctx.warn(f"P7b: {fb} tax item(s) had no eligible use under the rules and were spread over all domestic uses")
    p7b_pid = ctx.prov(
        ref="P7b", status="estimated", inputs=pids([p7a_pid], sorted(set(prod_e["prov_id"].to_list())), pc_pid,
                                                   sorted(set(prod_c["prov_id"].to_list()))),
        source_id=SRC_SUT,
        method="Gap map P7b: each P7a item (pre-balancing; parent entry key in the row) spread over its commodity's "
        "uses (production's P2 IC by activity, P5 exports, I3 CII; C1/C2/I1/I2 targets for PFCE, GFCE, GFCF, "
        "valuables) pro rata to use value x eligibility: exports carry no GST, cess, excise or VAT (export duty "
        "only on exports); GST/cess on IC only for non-ITC activities (A_CROP, A_LVST, A_FOFI, A_UTIL, A_RPET, "
        "A_DWEL, A_EDUC, A_HLTH, A_PADM, A_OSRV; A_FINS/A_INSR 50%; A_BVTB at the alcohol share of its output), "
        "on GFCF only for C_CNST and C_TREQ, none on CII; electricity duty on IC + PFCE; vehicle tax on PFCE + "
        "GFCF; State excise on alcohol on PFCE + A_HOTL. Phase 4 applies the balanced z of the parent P7a entry "
        "(FRAMEWORK_REQUESTS P-10).",
    )  # fmt: skip
    sats["p7b_tax_by_use"] = _sat("P7b", [
        {"series_id": f"p7b.{r['account'].lower()}.{r['component']}.{r['commodity'].lower()}.{r['use'].lower()}",
         "tax_account": r["account"], "component": r["component"], "commodity": r["commodity"], "use": r["use"],
         "use_type": r["use_type"], "parent_entry": f"{r['account']}<-{r['commodity']}[P7a/{r['component']}]",
         "value": r["value"]} for r in b.iter_rows(named=True) if r["value"] != 0],
        ["tax_account", "component", "commodity", "use", "use_type", "parent_entry"], p7b_pid, "estimated",
        "Product taxes by type x commodity x use (pre-balancing P7a)", decimals=9)  # fmt: skip

    sats["p9a_by_commodity"] = _sat("P9a", [
        {"series_id": f"p9a.{r['commodity'].lower()}.{r['payer'].lower()}.{r['basis'].split()[0].rstrip(':')}",
         "commodity": r["commodity"],
         "payer": r["payer"], "basis": r["basis"], "value": r["value"]} for r in p9s.rows],
        ["commodity", "payer", "basis"], p9a_pid, "estimated",
        "SUT product subsidies by commodity and paying government")  # fmt: skip
    # every row carries the record of what it is (verification V-TX-2): the entry rows cite the P10a entries' own
    # records; the Union's identified subsidy heads are published numbers (official: FC16 Union
    # 'business') or differences of published numbers (derived: St 7 heads less MISS/LIC pension/PM-AASHA),
    # written with the SAM's subsidy sign (negative); gross D39/D29 are derived.
    p10_rows = [{"series_id": f"p10a.{i['gov'].lower()}.{i['component']}", "government": i["gov"],
                 "item": i["component"], "basis": i["basis"], "value": i["value"],
                 **({"status": "estimated", "prov_id": p10_sub_pid} if i["component"] == "gross_subsidies"
                    else {"status": "derived", "prov_id": p10_tax_pid})} for i in p10s.items]  # fmt: skip
    item_pid = {}
    for st, words in (("official", "as published"), ("derived", "differences of published numbers")):
        its = [(k, x, ins) for k, x, ins in p10s.centre_subsidy_items if p10s.centre_subsidy_status[k] == st]
        if its:
            item_pid[st] = ctx.prov(
                ref="P10a", status=st, inputs=pids(*(ins for _, _, ins in its)),
                source_id=None,  # the inputs' own source (FC16 alone since PM-KISAN left P10a)
                method=f"Gap map P10a detail: the Union's identified production-subsidy heads ({words}), written "
                "negative (the SAM's subsidy sign): " + "; ".join(p10s.centre_subsidy_basis[k] for k, _, _ in its)
                + ". Their sum is the G_CEN gross_subsidies entry.",
            )  # fmt: skip
    p10_rows += [{"series_id": f"p10a.g_cen.subsidy_item.{k}", "government": "G_CEN", "item": k,
                  "basis": p10s.centre_subsidy_basis[k], "value": -x, "status": p10s.centre_subsidy_status[k],
                  "prov_id": item_pid[p10s.centre_subsidy_status[k]]}
                 for k, x, _ in p10s.centre_subsidy_items]  # fmt: skip
    p10_rows += [{"series_id": "p10a.derived.gross_d39", "government": None, "item": "gross_d39",
                  "basis": "NAS 4.2 GG subsidies - NAS 1.1 product subsidies", "value": p10s.d39,
                  "status": "derived", "prov_id": p10_tax_pid},
                 {"series_id": "p10a.derived.gross_d29", "government": None, "item": "gross_d29",
                  "basis": "gross D39 + P10 net", "value": p10s.d29, "status": "derived",
                  "prov_id": p10_tax_pid}]  # fmt: skip
    sats["p10a_items"] = _sat_rows("P10a", p10_rows, ["government", "item", "basis"],
                                   "Gross production taxes and subsidies by government and item")  # fmt: skip
    dts = [{"series_id": f"t4a.{a.lower()}.{c}", "item": f"{a}:{c}", "value": v} for (a, c), v in t4.cells.items()]
    dts += [{"series_id": f"t4a.detail.{k}", "item": k, "value": v,
             "unit": "ratio" if "share" in k else "INR_crore"} for k, v in t4.detail.items()]  # fmt: skip
    dts += [{"series_id": f"t3.{k}", "item": k, "value": v} for k, v in t3.parts.items()]
    dts += [{"series_id": "t3.household_share_mh0021", "item": "household_share_mh0021_old_base", "value": t3.share,
             "unit": "ratio"},
            {"series_id": "t3.household_share_ifpri", "item": "household_share_mh0021_ifpri_check",
             "value": t3.ifpri_share, "unit": "ratio"}]  # fmt: skip
    sats["direct_tax_split"] = _sat("T4a", dts, ["item"], t4a_pid, "estimated",
                                    "Direct-tax split: T4a cells, FC bottom-up provisions, T3 household/quasi-corp. "
                                    "parts (Rs crore; shares as ratios)", unit_col=True, decimals=9)  # fmt: skip
    t3s = [{"series_id": f"t3a.share.y{int(th)}.{g.lower()}", "household_group": g, "threshold_rs": f"{th:.0f}",
            "value": v, "unit": "ratio"} for th, kk in keys.items() for g, v in kk.items()]  # fmt: skip
    t3s += [{"series_id": f"t3a.fractile.income_per_household.{r['class']}", "household_group": r["group"],
             "threshold_rs": None, "unit": "INR",
             "value": 12 * r["avg_mpce"] * r["persons"] / r["households"] * fr.k / (1 - fr.saving[r["group"]])}
            for r in fr.table.iter_rows(named=True)]  # fmt: skip
    t3s += [{"series_id": "t3a.param.k_nas_hces", "household_group": None, "threshold_rs": None, "unit": "ratio",
             "value": fr.k}]  # fmt: skip
    sats["t3a_sensitivity"] = _sat("T3a", t3s, ["household_group", "threshold_rs"], t3a_pid, "estimated",
                                   "T3a key shares at Rs 5, 7 and 10 lakh thresholds; fractile incomes", unit_col=True,
                                   decimals=9)  # fmt: skip
    s7rows, s7in = memo.s7_rows(ctx)
    s7_pid = ctx.prov(ref="S7", status="official", inputs=s7in, source_id=SRC_FA,
                      method="Gap map S7: the IGST settlement route as published (Finance Accounts 2023-24 St 8: MH "
                      "0008 collections, ITC cross-utilisation, apportionment, advance apportionment; CGST-side "
                      "receipts; UTGST; compensation cess), and PIB monthly GST releases for April-May 2023. Memo "
                      "only: settled IGST is already inside CGST/SGST (no IGST account). State-by-month settlement "
                      "is blocked (GSTN, D1-1c).")  # fmt: skip
    sats["s7_igst_settlement"] = _sat("S7", s7rows, ["item", "label", "period", "source_series"], s7_pid, "official",
                                      "IGST settlement memo (annual FA St 8; PIB April-May 2023)")  # fmt: skip
    stat7 = {}
    st7_in = []
    for k, sid in (
        ("miss", "stat7.interest_subsidies.modified_interest_subvention_scheme"),
        ("lpg", "stat7.petroleum.lpg_subsidy"),
        ("fertiliser", "stat7.fertiliser"),
        ("aasha", "stat7.other_subsidies.pradhan_mantri_annadata_aay_sanrakshan_yojna"),
        ("food", "stat7.food"),
        ("lic", "stat7.interest_subsidies.interest_subsidy_to_lic_for_pension_plan_for_senior_citizens"),
    ):
        stat7[k], p = ctx.value(EXP, sid, vintage="latest")
        st7_in.append(p)  # fmt: skip
    lpg_p9 = float(p9.filter(pl.col("col") == "C_RPET")["value"].sum())
    cls_pid = ctx.prov(
        ref="T1a", status="derived", inputs=pids(cash.pids(), st7_in, p9_pids, p9s.inputs, [p10_sub_pid],
                                                 [p10s.pm_kisan[1]], cash.xp("professions_tax"), cash.xp("stt")),
        source_id=SRC_RB,
        method="Classification decisions (read by government, CROSS_REVIEW XR-18): each contested head, its 2023-24 "
        "amount as published (LPG DBT = St 7 LPG less the SUT P9 on C_RPET) and the one SAM cell it is booked in.",
    )  # fmt: skip
    cl = memo.classification_rows(cash, t3, p9s, p10s, lpg_p9, stat7)
    sats["tax_classification"] = _sat("T1a", [{**r, "series_id": f"class.{r['item']}"} for r in cl],
                                      ["item", "ref", "sam_cell", "government", "treatment"], cls_pid, "derived",
                                      "Where each contested tax/subsidy head is booked (booked once)")  # fmt: skip

    _checks(ctx, entries, cash, prod_e, sut_total, sut_total_pid)
    return BlockResult(entries=entries, constraints=cons, satellites=sats)


# ---------------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------------


def _sat_rows(ref, rows, dims, desc) -> Satellite:
    """A satellite whose rows carry their own status and prov_id (rows of different kinds)."""
    schema = {"series_id": pl.String, **{d: pl.String for d in dims}, "value": pl.Float64, "unit": pl.String,
              "status": pl.String, "prov_id": pl.String}  # fmt: skip
    data = [{"series_id": r["series_id"], **{d: r.get(d) for d in dims}, "value": float(r["value"]),
             "unit": "INR_crore", "status": r["status"], "prov_id": r["prov_id"]} for r in rows]  # fmt: skip
    return Satellite(ref, pl.DataFrame(data, schema=schema, orient="row"), desc)


def _sut_total(ctx: BlockContext, item: str) -> tuple[float, str]:
    df = ctx.rows(SUPPLY, vintage=p7a.SUT_VINTAGE, item_code=item, product="total")
    if df.height != 1:
        raise SamError(f"SUT total row for {item}: {df.height} rows")
    return float(df["value"][0]), str(df["prov_id"][0])


def _precheck_sat(fit, rows, cols, itemv, cash, pid) -> Satellite:
    out = []
    for a in PRODUCT_TAX_ACCOUNTS:
        final = sum(r["value"] for r in fit.cells.iter_rows(named=True) if r["account"] == a)
        for k, v in (
            ("cash", rows[a]),
            ("cash_centre", cash.by_account(a, "G_CEN")),
            ("cash_states", cash.by_account(a, "G_STA")),
            ("scaled_target", fit.row_target[a]),
            ("precheck_target", fit.row_final[a]),
            ("final", final),
            ("final_over_cash", final / rows[a]),
        ):
            out.append({"series_id": f"row.{a.lower()}.{k}", "kind": "row", "account": a, "measure": k,
                        "value": v, "unit": "ratio" if k == "final_over_cash" else "INR_crore"})  # fmt: skip
    for c, v in sorted(cols.items()):
        if v:
            out.append({"series_id": f"col.{c.lower()}.sut", "kind": "column", "account": c, "measure": "sut_target",
                        "value": v, "unit": "INR_crore"})  # fmt: skip
    for r in itemv.iter_rows(named=True):
        out.append({"series_id": f"item.{r['account'].lower()}.{r['component']}.{r['item']}.{r['commodity'].lower()}",
                    "kind": "item", "account": r["account"], "measure": f"{r['item']}:{r['commodity']}",
                    "value": r["final"], "unit": "INR_crore"})  # fmt: skip
        out.append({"series_id": f"prior.{r['account'].lower()}.{r['component']}.{r['item']}.{r['commodity'].lower()}",
                    "kind": "item_prior", "account": r["account"], "measure": f"{r['item']}:{r['commodity']}",
                    "value": r["prior"], "unit": "INR_crore"})  # fmt: skip
    return _sat("P7a", out, ["kind", "account", "measure"], pid, "estimated",
                "P7a row/column targets, pre-check, final accrual/cash ratio by type, prior and final items",
                unit_col=True, decimals=9)  # fmt: skip


def _checks(ctx: BlockContext, entries: list[dict], cash, prod_e: pl.DataFrame, sut_total: float,
            sut_total_pid: str) -> None:  # fmt: skip
    def s(ref: str, row: str | None = None, col: str | None = None) -> float:
        return sum(e["value"] for e in entries if e["ref"] == ref and (row is None or e["row"] == row)
                   and (col is None or e["col"] == col))  # fmt: skip

    def nas(sid: str, ds: str = NAS11) -> tuple[float, str]:
        return ctx.value(ds, sid, vintage="latest")

    p8 = float(prod_e.filter(pl.col("ref") == "P8")["value"].sum())
    p9 = float(prod_e.filter(pl.col("ref") == "P9")["value"].sum())
    tp, tpp = nas("s1_1.taxes_on_products.current")
    sp, _ = nas("s1_1.subsidies_on_products.current")
    imp, imp_pid = _sut_total(ctx, "import_duty")
    np_, npp = nas("s7_1.total.net_production_taxes.current", NAS71)
    checks = [
        ("p7a_total_sut", "P7a entries vs SUT 'total' product taxes", s("P7a"), sut_total, sut_total_pid, 1.0),
        ("product_taxes_nas", "P7a + import duty vs NAS 1.1 taxes on products", s("P7a") + p8, tp, tpp, CHECK_TOL),
        ("net_product_taxes_nas", "P7a + P8 + P9 vs NAS 1.1 taxes less subsidies on products", s("P7a") + p8 + p9,
         tp - sp, tpp, CHECK_TOL),
        ("p9a_total_nas", "P9a vs minus NAS 1.1 subsidies on products", -s("P9a"), sp, _pid(ctx, NAS11,
         "s1_1.subsidies_on_products.current"), 1.0),
        ("p10a_net_nas71", "P10a net vs NAS 7.1 net production taxes", s("P10a"), np_, npp, 1.0),
        ("t_cust_sut", "G_CEN <- T_CUST vs SUT 'total' import duty", s("T1a", "G_CEN", "T_CUST"), imp, imp_pid, 1.0),
        ("t_cust_cash", "G_CEN <- T_CUST vs RB customs less export duty (1%)", s("T1a", "G_CEN", "T_CUST"),
         cash.x("customs") - cash.x("export_duty"), cash.xp("customs")[0],
         0.01 * (cash.x("customs") - cash.x("export_duty"))),
        ("t4a_cit_cash", "Sum T4a vs RB corporation tax", s("T4a"), cash.x("cit"), cash.xp("cit")[0], 1.0),
        ("t3_pit_cash", "Sum T3 + T3a vs RB taxes on income + wealth + RBI SF State taxes on income",
         s("T3") + s("T3a"), cash.x("taxes_on_income") + cash.x("wealth_tax") + cash.x("state_income_taxes"),
         cash.xp("taxes_on_income")[0], 1.0),
        ("tax4_gst_total", "RB CGST + IGST + compensation cess vs RB total GST (TAX-4)",
         cash.get("cgst").value + cash.get("igst").value + cash.get("gst_compensation_cess").value,
         cash.x("gst_total"), cash.xp("gst_total")[0], 0.01),
    ]  # fmt: skip
    for cid, desc, v, t, tpid, tol in checks:
        ctx.check(cid, desc, v, t, target_prov_id=tpid, tol_abs=tol)
    # Receipt Budget gross = Finance Accounts net + the States' share (minor head 901)
    for key, rb_value, fa_total, fa_901 in (
        ("mh0005", cash.get("cgst").value, "fa8.0005.total", "fa8.0005.00.901"),
        ("mh0020", cash.x("cit"), "fa8.0020.total", "fa8.0020.00.901"),
        ("mh0021", cash.x("mh0021"), "fa8.0021.total", "fa8.0021.00.901"),
        ("mh0037", cash.x("customs"), "fa8.0037.total", "fa8.0037.00.901"),
        ("mh0038", cash.get("union_excise").value, "fa8.0038.total", "fa8.0038.01.901"),
    ):
        a, pa = ctx.value(FA, fa_total, vintage="latest")
        b, _ = ctx.value(FA, fa_901, vintage="latest")
        ctx.check(f"rb_vs_fa.{key}", f"RB {key} gross vs FA total - minor head 901", rb_value, a - b,
                  target_prov_id=pa, tol_abs=0.02)  # fmt: skip
    a, pa = ctx.value(FA, "fa8.0008.01.total", vintage="latest")
    b, _ = ctx.value(FA, "fa8.0008.02.total", vintage="latest")
    c, pc = ctx.value(FA, "fa8.0008.total", vintage="latest")
    ctx.check("s7_igst_identity", "FA MH 0008: imports + domestic = total (S7)", a + b, c, target_prov_id=pc,
              tol_abs=0.01)  # fmt: skip


def _pid(ctx: BlockContext, ds: str, sid: str) -> str:
    return ctx.value(ds, sid, vintage="latest")[1]
