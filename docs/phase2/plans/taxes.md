# Phase 2 block plan: `taxes`

Written 2026-09-30 by the taxes data scout and method planner (research only; no code written, no `pipeline build/sam/repro` run). Every number below was read from `data/clean/<unit>/*.parquet` with DuckDB on 2026-09-30 (scratch queries only), or is arithmetic on those numbers (marked "derived"). Amounts are ₹ crore, current prices, FY 2023-24 unless stated. The builder must re-read every value through `ctx.value` / `ctx.frame`; never type these numbers into code.

Owned refs: **P7a P7b(satellite) P9a P10a T1 T1a T2 T2x T3 T3a T4 T4a**, satellite **S7**. Depends on: production, households, factors.

---

## 1. Summary (plain English)

- The SUT gives one official product-tax number per commodity (₹30.15 lakh cr in all). This block splits that number into CGST, SGST, compensation cess, Union excise, State VAT, State excise and "other" (P7a), using the Union and State budget receipts as row targets. The SUT total wins, and the gap to the budgets is logged, not forced.
- **The biggest single choice is State motor-vehicle tax (₹1.10 lakh cr).** Three independent checks (derived new-base production taxes D29, old-base income taxes D5, and the SUT-vs-budget gap TAX-1) all say NAS cannot hold it anywhere except in product taxes. We recommend treating it as a product tax on vehicles, which shrinks the unexplained product-tax gap from 5.5% to 1.6%. The owner or orchestrator should confirm this, because it reverses a Phase 0 default (R16).
- **Alcohol does not fit.** State excise alone (₹2.60 lakh cr) exceeds the SUT's tax on alcoholic beverages (₹2.34 lakh cr) before liquor VAT is added. The gap-map fallback (excess treated as licence fees on hotels and trade) applies, and the pre-check will quantify it.
- Direct taxes: corporation tax (₹9.11 lakh cr) is split across the five paying corporate sectors using old-base NAS shares plus the tax provisions of banks, NBFCs and insurers. A new finding: old-base NAS puts about **21% of "income tax other than corporation tax" (MH 0021) on quasi-corporations (firms), not households**. So the household income-tax row should be about ₹7.9 lakh cr, not ₹10.1 lakh cr.
- Personal income tax by household group (T3a) has no open data at all (CBDT is blocked). We propose a stated, low-confidence "income above the tax threshold" key built from HCES fractiles. It is very sensitive to the threshold, and we say so.
- Subsidies: the product-subsidy (P9a) and production-tax (P10a) totals are fixed by the SUT. Only their Centre/State split is estimated. NAS 4.2 lets us derive gross production subsidies (₹3.42 lakh cr) and gross production taxes (₹2.85 lakh cr) for the first time on the new base.
- **Double-counting hot spots, which the government block must respect:** vehicle tax, interest subvention (already in the SUT's product subsidy on financial services), the LPG subsidy, State food subsidies, professions tax and the securities transaction tax (STT).

---

## 2. Ref-by-ref table

Status labels: `official` = as published or pure aggregation; `derived` = arithmetic on official numbers; `estimated` = modelled (the site says "official total, estimated by type/group"). Roles and confidences follow DESIGN_BRIEF §3/§5.1.

| ref | SAM cell(s) | entries to write | source datasets / series (clean) | 2023-24 values (clean data) | role | method (details in §2.x) | status label |
|---|---|---|---|---|---|---|---|
| **P7a** | (T_CGST, T_SGST, T_GCES, T_UEXC, T_SVAT, T_SEXC, T_OPRT) ← C_* | ≤ 7 × 32 entries (C_DWEL, C_PADM have zero product tax); components `total`, plus `licence_fee_excess` on (T_SEXC, C_HOTL/C_TRAD) if the pre-check needs it | column targets: `io_tables_sut_supply` `supply.product_taxes.sut_pNNN.current` aggregated with `data/concordance/io_tables_sut_product_to_sam34.csv` (read production's P7 constraint targets rather than recomputing); total `supply.product_taxes.total.current`. Row targets: see T1/T2 rows. Priors: `union_fiscal_ppac_exchequer`, `union_fiscal_fa_receipts`, `state_fiscal_rbi_sf_appendices` | column total 30,15,341.40 (by commodity: C_RPET 7,00,419; C_CNST 3,24,456; C_BVTB 3,10,390; C_TREQ 2,91,920; C_CHEM 1,38,127; C_TXAP 1,37,042; C_FOOD 1,18,799; C_MACH 1,17,434; C_UTIL 75,037; C_TRAD 74,328; …). Row targets (cash, NAS basis) sum 29,67,958.27 (with vehicle tax) | free; confidence high (petroleum excise/VAT on C_RPET/C_OILG, State excise on C_BVTB), medium (GST cells, electricity duty on C_UTIL), low (T_GCES spread, T_OPRT except electricity duty, licence-fee cells) | two-margin GRAS on a product-level prior (155 SUT products → 34), feasibility LP pre-check, SUT column margin wins | estimated ("official total, estimated by type") |
| **P7b** | satellite (not a SAM cell) | `p7b_tax_by_use`: tax type × commodity × use (IC by 34 activities, PFCE, GFCE, GFCF, CII, valuables, exports) | P7a result + production's use entries (P2 IC, C1, C2, I1, P5) or `io_tables_sut_use` `use.{ic,pfce,gfce,gfcf,cii,valuables,exports}.*` | row/column totals = P7a | n/a (satellite) | exports carry zero GST, cess and domestic excise/VAT; GST on IC only for non-ITC activities; the rest pro rata to use value | estimated |
| **P9a** | G_CEN ← T_PSUB, G_STA ← T_PSUB (negative) | 2 entries (+ drill-down satellite `p9a_by_commodity`) | P9 row (production's entries, `supply.product_subsidies.*`); `union_fiscal_exp_profile` `stat7.fertiliser` 1,88,291.62, `stat7.petroleum.lpg_subsidy` 12,240.00, `stat7.interest_subsidies.modified_interest_subvention_scheme` 14,251.93, `stat7.other_subsidies.pradhan_mantri_annadata_aay_sanrakshan_yojna` 2,200.00; `state_fiscal_fc16_subsidies` `sub.power.*` (21 States 2,59,585.62); `state_fiscal_rbi_sf_statements` `st36.subsidies.in.all_states_uts.actuals` 3,29,610.4 (partial) | P9 total −5,76,422.43; by commodity C_CHEM −2,07,569.12, C_UTIL −1,95,549.01, C_TRAD −1,05,006.67, C_OSRV −19,480.44, C_CROP −15,166.11, C_FINS −14,325.54, C_TRNS −7,281.92, C_TREQ −4,192.06, C_BSRE −2,352.46, C_RPET −2,280.00, others (C_EDUC, C_HLTH, C_LVST, C_FOFI, C_CNST, C_COMM) −3,219.09 | free, medium (G_STA ← T_PSUB and G_CEN ← T_PSUB) | commodity-by-commodity paying-government map; unexplained rows split by the identified ratio. Indicative: G_CEN −2,97,427, G_STA −2,78,995 | estimated |
| **P10a** | G_CEN ← T_PROD, G_STA ← T_PROD | 4 entries: components `gross_taxes` (+), `gross_subsidies` (−) for each government | P10 row (production, `io_tables_sut_va` `va.net_production_taxes.*` = −57,441.998622); `mospi_nas_2026_s4_2` `s4_2.subsidy.total.current` 9,18,559.13; `mospi_nas_2026_s1_1` `s1_1.subsidies_on_products.current` 5,76,422.4; `mospi_nas_2026_s7_1` `s7_1.total.net_production_taxes.current` −57,442.4; RBI SF app1 stamps 2,28,154.98, land revenue 24,099.60, urban immovable property tax 2,262.58; FA `fa8.0029.total` 17.8208, `fa8.0030.total` 393.9377; `state_fiscal_ulb_cityfinance` `ulb.property_tax.in.all_ulbs_in_dump` 29,382.23; `union_fiscal_fa_expenditure` `fa9.2401.00.130` (Farmers Income Support) 51,616.91 | derived: gross D39 = 9,18,559.1 − 5,76,422.4 = **3,42,136.7**; gross D29 = 3,42,136.7 − 57,442.4 = **2,84,694.3**. G_CEN gross taxes 411.76 (UT stamps + land revenue) | gross_taxes anchored tol_rel 0.03; gross_subsidies free, low | gross totals from NAS 4.2 identity; Centre/State by identified items; States = residual | estimated (gross totals derived) |
| **T1** | G_CEN ← T_CGST, T_GCES, T_UEXC, T_CUST, T_PIT, T_CIT | **constraints only** (cash control totals, no entries) | `union_fiscal_rb_receipts` (vintage 2025-02-01, Actuals); cross-check `union_fiscal_fa_receipts` (gross = total − 901) and `union_fiscal_afs` | CGST 8,20,622.09 + IGST −4,850.43 + UTGST 5,497.16 = 8,21,268.82; cess 1,41,436.16; excise 3,05,362.18; customs 2,33,118.97 (less export duty 3,347.07 and export cesses −3.19 = 2,29,775.09); CIT 9,11,055.01; income-tax heads 10,10,947.77 + STT 33,777.78 | n/a (band constraints) | cash as published, mapped to NAS accounts | official |
| **T1a** | G_CEN ← T_CGST, T_GCES, T_UEXC, T_OPRT, T_SVAT, T_SEXC, T_CUST, T_PIT, T_CIT | 9 entries (T_OPRT/T_SVAT/T_SEXC Centre parts = UTs without legislature, equalisation levy, export duty, service-tax arrears, CTT) | as T1 + the P7a solution + P8 entries | = P7a row totals for product taxes (priors ≈ cash × 1.0160); T_CUST = ΣP8 = 2,28,887.27; T_PIT/T_CIT = cash | T_CUST **fixed** (derived); T_PIT, T_CIT anchored tol_rel 0.005; others free, medium | each Centre-received row total of P7a; direct taxes cash = accrual | estimated ("official total, estimated by type") |
| **T2** | G_STA ← T_SGST, T_SVAT, T_SEXC (+ T_OPRT, T_PIT extension, §6) | **constraints only** | `state_fiscal_rbi_sf_appendices` (vintage 2026-01-23, Accounts 2023-24, all States + UTs with legislature); cross-check `state_fiscal_fc16_kfi` (28 States) | SGST 8,41,120.77; sales tax/VAT 4,06,404.10; State excise 2,58,275.50 (FC16: 8,00,112.02; 3,97,467.06; 2,49,133.50) | n/a | cash control totals | official |
| **T2x** | G_STA ← T_SGST, T_SVAT, T_SEXC, T_OPRT, T_PIT | 5 entries | as T2 + P7a solution; professions tax `…i.a.1.ii-taxes_on_professions…` 7,872.88, agri income tax 0.94 | = P7a row totals (State parts); T_PIT (State) 7,873.82 | free, medium; (G_STA, T_PIT) anchored tol_rel 0.01 | as T1a | estimated |
| **T3** | T_PIT ← HH total; plus T_PIT ← E_NFPR / E_BANK (quasi-corporate part, §5 C3) | entries only for the non-household part (component `quasi_corporate`); the household total is a constraint over T3a entries | `union_fiscal_rb_receipts` `rb.tr.0021.*` (sum 10,10,947.77), `rb.tr.0034.security_transaction_tax` 33,777.78, `rb.tr.total.total_taxes_on_income` 10,44,756.25; FA `fa8.0021.total` 6,19,420.09 − `fa8.0021.00.901` −3,91,527.68; old-base `mospi_nas_2026_oldbase_soa_s5_0` `…secondary_distribution_of_income.uses.d5.current` 6,42,596.29 (2022-23); `io_tables_ifpri_2223_datapaper` `ifpri.t8.taxes.households.current` 7,28,800 (2022-23) | T3 (gap-map definition) = 10,10,947.77 + 33,777.78 + 22.32 (0028 14.89, 0031 1.31, 0032 6.12) = 10,44,747.87 (+ firm-only heads 0023/0024/0026 = 15.81). Household share of MH 0021 (old base 2022-23) = 78.55% → HH ≈ 7,94,08x; quasi-corporate ≈ 2,16,87x | quasi_corporate free, low | old-base NAS D5 household share applied to MH 0021; STT and wealth-tax arrears to households | estimated (total official) |
| **T3a** | T_PIT ← H_R1…H_U5 | 10 groups × components `income_tax`, `professions_tax` (≤ 20 entries) | households `hh_keys` (fractile persons, households, MPCE); `hces_consumption_a2_fractile_persons` (via hh_keys); `mospi_nas_2026_s1_1` `s1_1.pfce.current` 1,64,15,546.5; `io_tables_ifpri_2223_datapaper` `ifpri.t11.savings_rate.q1..q5`; factors F1a (F_LREG → H_*) for professions tax | none published; indicative key at a ₹7 lakh household threshold: U5 48.0%, R5 26.6%, U4 18.6%, U3 6.6%, U2 0.2% | free, **low** | threshold-excess key on NAS-scaled HCES fractile incomes (stated assumption); professions tax by regular-wage CE | estimated (low confidence, no open input: ISSUES P1-4) |
| **T4** | T_CIT ← corporations total | constraint only (entries are T4a) | `rb.tr.total.total_corporation_tax` 9,11,055.01 = FA `fa8.0020.total` 5,72,031.2198 − `fa8.0020.00.901` −3,39,023.79 | 9,11,055.01 | n/a | MH 0020 gross; RBI exempt | official |
| **T4a** | T_CIT ← E_NFPU, E_NFPR, E_BANK, E_NBFC, E_INSP (FC components `public`/`private`) | 5 accounts; FC accounts carry `public` and `private` components (≤ 8 entries) | old-base D5 2022-23: `oldbase_soa_s2_1` 66,477, `s2_2` 7,69,336, `s3_1` 31,678, `s3_2` 1,28,821 (all `…secondary_distribution_of_income.uses.d5.current`); `finsector_markets_irdai_life` `t24/t25.provision_for_tax.insurers_life.current` 5,906.13 / 223.42; `finsector_markets_irdai_nonlife` `t51.provision_for_tax.{general_public 507.60, general_private 2,196.70, health_standalone 389.01, general_specialized 1,018.07}`; `rbi_banking_corporate_rtp_nbfi` (vintage 2025-12-29) NBFC-UL 13,102, NBFC-ML 25,242, HFC 826, AIFI 4,631; `rbi_banking_corporate_rtp_banks` RRB 2,430, PB 68, SFB PBT 7,835 / net profit 6,219, SCB net profit by bank group; `rbi_banking_corporate_rtp_coop` UCB 1,620 | sum = 9,11,055.01; E_RBI none (RBI Act s.48) | free; medium (E_INSP, E_NBFC), low (E_NFPU vs E_NFPR, E_BANK residual) | old-base sector shares of corporate D5 → remove quasi-corporate part → FC sub-sectors bottom-up, E_BANK residual | estimated |
| **S7** | satellite `s7_igst_settlement` | annual IGST collection, ITC cross-utilisation and apportionment; monthly Apr–May 2023 | `union_fiscal_fa_receipts` `fa8.0008.*`, `fa8.0005.00.105/106/107/110`, `fa8.0007.*`, `fa8.0009.01/02.total`; `union_fiscal_pib_gst` `pib.gst.*` (2023-04, 2023-05) | IGST on imports 4,78,936.58; domestic IGST tax 3,93,458.85; ITC to CGST −3,53,607.92, to SGST −2,76,514.00, to UTGST −2,083.12; apportioned to CGST −1,33,430.77, to SGST −1,31,738.42, to UTGST −1,692.35; advance apportionment +9,000 / +8,951.40 / +48.60; residual MH 0008 total −4,850.43 | n/a | memo; IGST already sits inside T_CGST/T_SGST | official (partial: State-by-month settlement blocked, D1-1c) |

### 2.1 P7a: product taxes by type within commodity (hard problem H3)

**Row targets (cash, NAS net post-settlement basis).** Record each as a `derived` prov record listing its component series.

| row | receiving govt | components (dataset `series_id` → value) | cash target |
|---|---|---|---|
| T_CGST | G_CEN | `rb.tr.0005.central_goods_and_services_tax_cgst` 8,20,622.09 + `rb.tr.0008.integrated_goods_and_services_tax_igst` −4,850.43 + `rb.tr.0007.union_territories_goods_and_services_tax_utgst` 5,497.16 (UTGST: see §5 C6) | 8,21,268.82 |
| T_SGST | G_STA | `app1.total_revenue.i.a.3.vii-state_goods_and_services_tax.in.all_states_uts.actuals` | 8,41,120.77 |
| T_GCES | G_CEN | `rb.tr.0009.gst_compensation_cess` | 1,41,436.16 |
| T_UEXC | G_CEN | `rb.tr.total.total_union_excise_duties` (incl. NCCD 7,812.25, RIC 44,549.50, AIDC 53,778.06, SAED 1,46,619.61, cess on crude oil 18,803.41; do **not** net off the NDRF transfer `rb.tr.total.net_less_nccd…` −8,774.32, which is internal to G_CEN) | 3,05,362.18 |
| T_SVAT | G_STA / G_CEN | `app1.total_revenue.i.a.3.i-sales_tax…` 4,06,404.10 (of which CST 12,925.28; VAT 3,64,630.36; other receipts 28,838.70) + UT without legislature `rb.tr.0710.sales_tax` 1,492.59 | 4,07,896.69 |
| T_SEXC | G_STA / G_CEN | `app1.total_revenue.i.a.3.ii-state_excise…` 2,58,275.50 + `rb.tr.0710.state_excise_duties` 1,304.45 | 2,59,579.95 |
| T_OPRT | G_STA | electricity duty `…i.a.3.v…` 67,341.66 + **vehicle tax** `…i.a.3.iii…` 1,10,326.52 (§5 C1) + goods & passengers `…i.a.3.iv…` 1,757.01 + entertainment `…i.a.3.vi…` 62.67 + other taxes & duties `…i.a.3.viii…` 3,157.01 | 1,82,644.87 |
| T_OPRT | G_CEN | UT vehicles `rb.tr.0710.taxes_on_vehicles` 520.55 + UT goods & passengers 15.95 + UT electricity 0.09 (FA `fa8.0043.total` 0.0904; the Receipt Budget prints 0.10) + service-tax arrears `rb.tr.total.total_service_tax` 424.96 + MH 0045 (equalisation levy `fa8.0045.00.119` 3,933.40, R&D cess −4.32) `rb.tr.total.total_other_taxes_and_duties_on_commodities_and_services` 3,929.08 + export duty net (`rb.tr.0037.export_duty` 3,347.07 + `rb.tr.0037.cesses_on_exports` −3.19) 3,343.88 + CTT `rb.tr.total.total_commodity_transaction_tax` 414.32 | 8,648.83 |
| **Total** | | | **29,67,958.27** |

SUT column total 30,15,341.40, so the **TAX-1 residual gap is 47,383.13 (1.60%)** with vehicle tax as a product tax, or 1,58,230.20 (5.54%) without it.

**Steps.**
1. **Read column targets** from production's P7 constraints (one per commodity), so the two blocks' constraint targets are identical floats. Also read the product-level SUT vector `supply.product_taxes.sut_pNNN.current` to build the prior.
2. **Build the prior at SUT-product level (155 products)**, then aggregate to 34 commodities with the committed concordance. Place commodity-specific (non-GST) heads first. Each placement is a stated assumption recorded in its prov method:
   - Petroleum, from PPAC (`union_fiscal_ppac_exchequer`, vintage 2026-07-17):
     - T_UEXC: `ppac.centre.a.excise_duty` 2,73,683.88 → p085; `ppac.centre.a.cess_on_crude_oil` 19,580.39 and `ppac.centre.a.nccd_on_crude_oil` 1,190.92 → p044 crude (FA's audited cess on crude is 18,803.41: use PPAC only as a shape).
     - T_SVAT: `ppac.states.a.sales_tax_vat_on_pol_products` 2,92,716.41 → p085, with a p043 natural-gas share. PPAC does not split it, so use a stated default of p043 = 0 plus a residual (see step 4).
     - T_OPRT: `ppac.states.a.entry_tax_others` 301.47 and `…octroi_duties_incl_electricity_duty` 687.31 → p085.
     - GST: PPAC CGST 12,230.12, SGST 12,288.56 and IGST 20,929.70 → petroleum-product GST prior on p085.
     - **Exclude** royalty (`ppac.centre.a.royalty_on_crude_oil_natural_gas` 9,286.20; `ppac.states.a.royalty…` 12,529.50). It is rent, D45.
     - **Exclude** customs 13,133.73 (that is P8, production) and all of `ppac.centre.b.*` (direct taxes and dividends).
   - T_SEXC → p065 alcoholic beverages (a tiny share to p092 medicinal preparations is optional; default none).
   - T_UEXC non-petroleum residual = 3,05,362.18 − PPAC Centre excise items (2,94,455.19) = 10,906.99 → p069 tobacco products (NCCD, BED on tobacco). The default is 100% to p069.
   - T_SVAT non-petroleum residual (4,07,896.69 − 2,92,716.41 = 1,15,180.28) → p065 (liquor VAT), p043 (natural gas), p085 (ATF, if not in PPAC). The default prior shares are proportional to each product's SUT tax net of the loads already placed.
   - T_OPRT:
     - electricity duty → p128;
     - vehicle tax → p120/p121/p122 pro rata to (PFCE + GFCF) of each;
     - goods & passengers tax → p136;
     - entertainment → p155;
     - equalisation levy → p149, p141 pro rata to their imports;
     - export duty → goods products pro rata to exports (low confidence: no duty-by-product data);
     - CTT → p142;
     - service-tax arrears and "other taxes & duties" → pro rata to the GST residual.
   - T_GCES (legal base: tobacco, pan masala, aerated waters, motor cars, coal): no cess-by-product data are ingested. Prior: p069, p066, p064 and p120 carry cess at the same proportion of their GST residual (a stated factor). The coal part follows the SUT's PFCE spread, as the gap map says: the rest of T_GCES goes pro rata to the GST residual of all products, and **never on p042** (SUT coal product tax is only 3,062).
   - GST residual per product = max(0, SUT tax − specific loads). Split it into T_CGST and T_SGST in the ratio of their row targets (8,21,268.82 : 8,41,120.77). Alcoholic beverages (p065) and electricity (p128) are outside GST, so they get no GST prior.
3. **Why the gap-map GST prior cannot be followed as written.** The gap map asks for PFCE × item GST rate (HCES/CPI item map). No GST-rate schedule is in `data/clean`: hces coverage notes "GST rates (CBIC) are not registered". Fallback: use the SUT's own residual as the GST shape. MoSPI built that vector with exactly the PFCE × item-rate method (SUT note §6.7.2 and §8.4, raw `sut_note_2022_23_2023_24.pdf`), so this reproduces MoSPI's method implicitly. DESIGN_REVIEW line 161 already chose "the SUT's own PFCE-based GST allocation" as the P7a prior.
4. **Feasibility pre-check (a small LP, cvxpy).** Take the zero pattern of the prior. Test whether row targets scaled by s = 30,15,341.40 / 29,67,958.27 = 1.01596 can be met under the column targets (a transportation problem). If they cannot, solve min Σ |r'ᵢ − rᵢ|/rᵢ subject to feasibility. Then log each row's shortfall (`p7a_precheck` satellite) and apply the documented fallback order:
   (a) Open cells (T_SEXC, C_HOTL) and (T_SEXC, C_TRAD) with component `licence_fee_excess`, as the gap map says, sized at most at each column's GST-residual room.
   (b) Let T_SVAT move beyond PPAC on p085/C_RPET (see the finding below).
   (c) Only then let the row target fall below cash (the SUT margin wins), logged as a T2x cash–accrual/coverage gap.
   Expected pressure points, from clean data:
   - **C_BVTB** 3,10,390 (alcoholic 2,33,677; non-alcoholic 19,337; tobacco products 57,377) must hold State excise 2,59,579.95 plus the non-petroleum Union excise 10,906.99, which leaves 39,903 for all GST and cess on tobacco and aerated drinks and all liquor VAT. At product level, p065 (2,33,677) < State excise alone, by **25,903 before any liquor VAT**. This is infeasible as written.
   - **C_RPET + C_OILG** 7,21,190 exceeds all PPAC petroleum product taxes (6,33,660.26) by 87,530. The SUT therefore seems to carry about ₹0.9 lakh cr more tax on petroleum than PPAC reports, possibly non-petroleum VAT placed on POL. Log this for NAD. The GRAS will use that room.
   - **C_UTIL** 75,037 vs electricity duty 67,341.75 (with Union UTs): feasible but tight. p128 electricity alone (60,924) is below the duty.
   - **C_TREQ** 2,91,920 must hold vehicle tax (1,10,847.07) plus GST at 28% plus cess on cars. It is plausible, but check it.
5. **Run the framework GRAS** (or in-block RAS: all P7a cells are positive) to the column targets (exact) and the feasible row targets. Tolerance 1e-6 relative.
6. **Write the entries.** P7a (row = tax account, col = commodity) as free. T1a/T2x column entries = row totals, split by receiving government for T_SVAT, T_SEXC and T_OPRT. Log each row's final accrual/cash ratio.

### 2.2 P7b: valuation layer (satellite `p7b_tax_by_use`, ref P7b)

1. For each (tax type, commodity) P7a cell, distribute the value across the uses of that commodity. Use production's entries: IC by activity (P2), PFCE (C1 total), GFCE (C2), GFCF (I1), CII, valuables, exports (P5). Weights are use values at purchasers' prices, subject to these rules (each a stated assumption):
   - GST (T_CGST, T_SGST) and T_GCES: exports = 0.
     - IC only for **non-ITC activities**. The stated list: A_CROP, A_LVST, A_FOFI, A_UTIL (electricity is outside GST), A_RPET (outside GST), A_BVTB alcohol share, A_DWEL, A_FINS/A_INSR (partial reversal: the default is 50% non-ITC), A_EDUC, A_HLTH, A_PADM, A_OSRV.
     - GFCF bears GST for C_CNST (blocked credit on immovable property) and C_TREQ passenger vehicles; other GFCF bears GST only for the government/household share (default: GG share of GFCF from production's I1 split if published, else all creditable).
   - T_UEXC and T_SVAT on petroleum: all domestic uses including IC (not creditable); exports 0.
   - T_SEXC: PFCE + IC of A_HOTL; exports 0.
   - T_OPRT: electricity duty on IC + PFCE; vehicle tax on PFCE + GFCF; export duty **only** on exports.
2. Then rescale each (type, commodity) so the use cells add up to P7a (the row and column totals equal P7a by construction).
3. **Balancing drift.** P7a entries may move in balancing, but P7b is written from the pre-balancing P7a. Record in the satellite the P7a entry key for each cell, so Phase 4 can apply the balanced z-factor per (type, commodity). See §4 (a framework request).

### 2.3 P9a: product subsidies by paying government

P9 (T_PSUB ← C_*) is production's fixed row. P9a writes only the two column entries; a drill-down satellite `p9a_by_commodity` holds the commodity detail.

| commodity (SUT) | P9 value | default payer | evidence |
|---|---|---|---|
| C_CHEM (fertilisers p089 −1,45,129; pesticides p090 −62,440, Q6) | −2,07,569.12 | 100% G_CEN | St 7 fertiliser 1,88,291.62 = FC16 Union fertiliser 1,88,292.04 (TAX-10). The SUT is 19,277 higher; log it (accrual or arrears) |
| C_UTIL (electricity −1,92,370; water −3,179) | −1,95,549.01 | 100% G_STA | FC16 States' power 2,59,585.62 (21 States); Union power 1,100 |
| C_TRAD (Q7) | −1,05,006.67 | identified ratio (see below) | unexplained; candidate: States' food subsidies to State civil-supplies corporations (FC16 States' food 54,463.39, 21 States). Must be confirmed; see §6 R9 |
| C_OSRV, C_EDUC, C_HLTH, C_BSRE, C_COMM, C_CNST | −24,129.72 | identified ratio | no mapping data |
| C_CROP | −15,166.11 | G_CEN 2,200 (PM-AASHA, St 7); rest G_STA | State procurement bonuses; low |
| C_FINS | −14,325.54 | G_CEN 14,251.93 (MISS, St 7); rest G_STA | MISS ≈ the SUT row: MoSPI books crop-loan interest subvention as a product subsidy on financial services |
| C_TRNS | −7,281.92 | p137 air −301 → G_CEN (UDAN); rest G_STA (bus fare schemes) | FC16 States' transport 18,573.95 (12 States) |
| C_TREQ | −4,192.06 | G_CEN (EV purchase subsidy) | low |
| C_RPET | −2,280.00 | G_CEN (LPG) | St 7 LPG 12,240; the SUT holds only 2,280 (§6 R8) |
| C_LVST, C_FOFI | −922.28 | G_STA | low |

Identified: G_CEN −2,30,794.47, G_STA −2,16,491.57, so the Centre share is 0.516. The unexplained rows (−1,29,136.39) are split at that ratio, following the gap map's Q7 rule. **Indicative result: G_CEN −2,97,427.37, G_STA −2,78,995.07, sum −5,76,422.43.** Write both as free/medium, with an `equal` constraint to the P9 total. Food subsidy (`stat7.food` 2,11,814.39) is excluded: it is GFCE (C2a, government).

### 2.4 P10a: production taxes and subsidies by government (gross sub-rows)

1. **Gross totals** (derived, new base). This assumes NAS 4.2's "subsidy" column is general-government D3 = D31 + D39. Cross-check for 2022-23: derived D39 = 3,22,581.0 and D29 = 2,52,855.6 on the new base, against old-base SOA 4.0 D39 = 2,88,983 and D29 = 2,46,133 for the same year. That is the same order of magnitude.
   - D39 (gross production subsidies) = `s4_2.subsidy.total.current` 9,18,559.13 − `s1_1.subsidies_on_products.current` 5,76,422.43 = **3,42,136.70**.
   - D29 (gross production taxes) = D39 + P10 net (−57,441.998622, the SUT figure production uses) = **2,84,694.70**.
2. **Gross taxes by government.**
   - G_CEN = FA `fa8.0029.total` 17.8208 + `fa8.0030.total` 393.9377 = 411.76 (UTs without legislature).
   - G_STA = D29 − 411.76 = 2,84,282.94.
   - Identified State D29 items: stamps 2,28,154.98 + land revenue 24,099.60 + urban immovable property tax 2,262.58 = 2,54,517.16. The ULB property tax in the cityfinance dump is 29,382.23 (284 ULBs only).
   - The remaining State room is 29,765.78, which the ULB/PRI property taxes essentially fill. Hence **no room for vehicle tax or professions tax in D29** (§5 C1, C4).
   - Keep items as a `p10a_items` satellite.
3. **Gross subsidies by government** (low confidence).
   - G_CEN identified:
     - PM-KISAN `fa9.2401.00.130` 51,616.91 (this head may be partial; check the Budget scheme actual if it is ever ingested);
     - St 7 interest subsidies other than MISS: 19,515.82 − 14,251.93 = 5,263.89 (interest equalisation 3,699.99 = FA `fa9.3453.00.107`; do not count it twice);
     - St 7 other subsidies other than PM-AASHA: 3,036.67 − 2,200.00 = 836.67;
     - FC16 Union "business" `sub.business.in.gg_centre` 52,325.27 (composition unverified; it may include PLI);
     - total ≈ 1,10,042.74.
   - G_STA = 3,42,136.70 − G_CEN ≈ 2,32,093.96.
   - Cross-checks, reported but not imposed: FC16 States' agriculture 82,707.25, business 27,559.03, transport 18,573.95 (partial coverage); NAS 7.1A public-sector net production taxes `s7_1a.total.net_production_taxes.current` −1,35,166.25 (departmental-enterprise support).
4. **Write 4 entries.** gross_taxes are anchored (tol 0.03); gross_subsidies are free/low. Add a net constraint equal to P10.

### 2.5 T1 / T1a / T2 / T2x: government receipts by type

- T1/T2 are **constraints**, not entries. Cash is the control and the accrual version is the entry, as DESIGN_BRIEF §3's own example "Union CGST cash = G_CEN ← T_CGST within 3%" does.
- T1a/T2x entries = the P7a row totals by receiving government. Also:
  - (G_CEN, T_CUST) = ΣP8 (fixed; derived from production's P8 entries: 2,28,887.27);
  - (G_CEN, T_PIT) = T3 control; (G_CEN, T_CIT) = T4 control (anchored, 0.5%);
  - (G_STA, T_PIT) = State taxes on income 7,873.82 (anchored, 1%).
- No NAS new-base tax-by-type data exist (RECONCILIATION §4), so the "accrual conversion" cannot be observed. The difference between the entry and cash is the pro-rata share of the TAX-1 residual gap, plus any pre-check reallocation. Label it "cash–accrual/coverage gap", not an accrual estimate.

### 2.6 T3 / T3a: personal income tax

1. **T3 control** (cash, `derived` record):
   - MH 0021 gross 10,10,947.77 (= Σ `rb.tr.0021.*`; FA check 6,19,420.09 + 3,91,527.68);
   - + STT `rb.tr.0034.security_transaction_tax` 33,777.78 (gap-map default; §5 C2);
   - + MH 0028 14.89 + MH 0031 1.31 + MH 0032 6.12 = **10,44,747.87**.
   - Firm-only arrears (0023 0.34, 0024 19.93, 0026 −4.46 = 15.81) go to the quasi-corporate component.
2. **Household vs quasi-corporate split** (§5 C3). Old-base NAS 2022-23 household D5 is 6,42,596.29 against MH 0021 gross of 8,08,221.32 (`rb.tr.0021.*` 2022-23). Professions tax (FC16 MH 0028, 28 States, 2022-23: 7,752.0) is also inside household D5. So the household share of MH 0021 = (6,42,596.29 − 7,752.0)/8,08,221.32 = **0.7855**. For 2023-24:
   - HH MH 0021 = 7,94,08x;
   - quasi-corporate = 2,16,86x + 15.81;
   - IFPRI 2022-23 cross-check: households 7,28,800 against the same MH 0021 → 0.902.
   - Quasi-corporate goes to (T_PIT, E_NFPR), except co-operative banks' tax (UCB `rtp.ucb_pl.tax_provisions.ucb.current` 1,620, vintage 2025-12-29), which goes to (T_PIT, E_BANK) component `private`.
3. **T3a key (no open input; confidence low).**
   - Using households' `hh_keys` at fractile level (24 HCES classes; group membership R/U × quintile):
     - Y_f (income per household) = 12 × MPCE_f × (persons_f / households_f) × k / (1 − s_q), where k = NAS PFCE / HCES aggregate = 1,64,15,546.5 / 72,74,444 = **2.257** (HH-1, clean data) and s_q = the IFPRI T11 saving rate of the matching national quintile (18.4…23.9%);
     - key_g = Σ_{f∈g} households_f × max(0, Y_f − Y*), with Y* = ₹7,00,000 per household. This is the statutory new-regime rebate limit for 2023-24 (Finance Act 2023), recorded as an assumption parameter.
   - Indicative shares (computed here): **U5 48.0, R5 26.6, U4 18.6, U3 6.6, U2 0.2%**. Sensitivity: Y* = ₹5 lakh gives U5 29.7 / R5 26.6 / U4 14.4 / R4 10.5 …; Y* = ₹10 lakh gives U5 90.5 / R5 6.9 / U4 2.6. Publish all three in a `t3a_sensitivity` satellite.
   - Professions tax (7,872.88 + 0.94) goes to groups by regular-wage CE (factors F1a, F_LREG → H_*), component `professions_tax`.
   - Uniform NAS scaling across fractiles, plus fractile averages that hide the top tail, bias the key toward R5 and away from the very top. Say so on the methodology page.

### 2.7 T4 / T4a: corporation tax by paying sector

1. Corporate D5 (2023-24 prior) = CIT 9,11,055.01 + quasi-corporate MH 0021 (step 2.6.2).
2. Sector shares from old-base 2022-23 D5 (NAS 2024 SOA; vintage 2024-06-05, FRE; labelled "old base, NAS 2024 vintage (2022-23 FRE)"): public NFC 0.0667, private NFC 0.7722, public FC 0.0318, private FC 0.1293.
3. Subtract the quasi-corporate part (all private: E_NFPR, plus UCB → E_BANK) to get T_CIT by NFC/FC and public/private.
4. FC sub-sectors, bottom-up:
   - E_INSP = life (5,906.13 + 223.42) + non-life (507.60 + 2,196.70 + 389.01 + 1,018.07) = **10,240.93**. Public = LIC t24 5,825.16 + t25 111.42 + general_public 507.60 + general_specialized 1,018.07. EPFO/NPS funds are exempt; reinsurers are missing (GIC Re), so log it.
   - E_NBFC = NBFC-UL 13,102 + NBFC-ML 25,242 + HFC 826 + AIFI 4,631 = **43,801**. AIFIs are public; the NBFC public/private split uses the old-base FC ratio (low).
   - E_BANK = FC CIT − E_INSP − E_NBFC (residual). Cross-check: SCB net profit 3,49,603 (`rtp.scb_pl.net_profit.scb.current`) + RRB 2,430 + PB 68 + SFB (7,835 − 6,219 = 1,616). SCB tax is not printed (it is inside provisions & contingencies 2,41,331). Split public/private by `rtp.scb_pl.net_profit.psb` 1,41,202 vs pvb + fb + sfb (+ RRBs public).
5. E_NFPU vs E_NFPR: old-base share (low). DPE and RBI corporate-finance levels are not ingested (ISSUES P1-4). Scale everything so Σ T_CIT = 9,11,055.01 exactly.
6. The RTP datasets hold two vintages (2024-12-26 and 2025-12-29) for the same 2023-24 series, e.g. NBFC-ML tax 23,958 vs 25,242. `ctx.value` fails unless one is named: **use 2025-12-29 (latest)**.

### 2.8 S7: IGST route (satellite `s7_igst_settlement`)

Annual rows from FA Statement 8 (audited, vintage 2024-12-10):
- IGST collected on imports `fa8.0008.01.total` 4,78,936.58;
- domestic `fa8.0008.02.101` 3,93,458.85 (+ interest/penalty/fees/other: `.102` 2,829.95, `.103` 869.46, `.104` 4.16, `.800` 117.14);
- ITC cross-utilisation to CGST (`.105`) −3,53,607.92, SGST (`.106`) −2,76,514.00, UTGST (`.107`) −2,083.12;
- apportionment out, tax + interest: CGST (`.950`/`.951`) −1,33,430.77; SGST (`.953`/`.954`) −1,31,738.42; UTGST (`.956`/`.957`) −1,692.35;
- advance apportionment (`.959`/`.960`/`.961`) +9,000.00/+8,951.40/+48.60;
- residual `fa8.0008.total` −4,850.43 (the component already inside T_CGST);
- the CGST receiving side `fa8.0005.00.105` 3,53,607.92, `.106` 1,33,055.54, `.107` 375.23, `.110` −9,000.00;
- UTGST `fa8.0007.*`;
- cess on imports / domestic `fa8.0009.01.total` 11,622.13 / `fa8.0009.02.total` 1,29,814.03.

Monthly: PIB April and May 2023 `pib.gst.*` (e.g. `pib.gst.igst_settled_to_sgst` 37,959 / 29,769). The State-by-month settlement is blocked (GSTN D1-1c; PIB bot challenge, union_fiscal-1). Status official, partial.

---

## 3. Constraints to declare

Constraint = Σ entries with row ∈ rows, col ∈ cols (ref ∈ refs if given) within target ± max(tol_abs, tol_rel·|target|). Each target gets a `derived`/`official` prov record naming its series.

| constraint_id | ref | rows | cols | refs filter | target (series) | tol | kind |
|---|---|---|---|---|---|---|---|
| `taxes.P7.<C_x>` (one per commodity with non-zero SUT tax; 32) | P7a | T_CGST, T_SGST, T_GCES, T_UEXC, T_SVAT, T_SEXC, T_OPRT | C_x | P7a | production's P7 target for C_x (Σ `supply.product_taxes.sut_pNNN.current` over the concordance). **Copy production's float.** | tol_abs 0.5 | equal |
| `taxes.P7.total` | P7a | same 7 | all C_* | P7a | `supply.product_taxes.total.current` 30,15,341.397664 | tol_abs 1 | equal |
| `taxes.T1.cgst` | T1 | G_CEN | T_CGST | T1a | 8,21,268.82 (§2.1) | tol_rel 0.05 | band |
| `taxes.T1.gces` | T1 | G_CEN | T_GCES | T1a | `rb.tr.0009.gst_compensation_cess` 1,41,436.16 | 0.05 | band |
| `taxes.T1.uexc` | T1 | G_CEN | T_UEXC | T1a | `rb.tr.total.total_union_excise_duties` 3,05,362.18 | 0.05 | band |
| `taxes.T1.cust` | T1 | G_CEN | T_CUST | T1a | 2,33,118.97 − 3,347.07 + 3.19 = 2,29,775.09 (TAX-2 bridge) | 0.01 | band |
| `taxes.T1.pit` | T1 | G_CEN | T_PIT | T1a | 10,44,747.87 + 15.81 = 10,44,763.68 | 0.005 | band |
| `taxes.T1.cit` | T1 | G_CEN | T_CIT | T1a | `rb.tr.total.total_corporation_tax` 9,11,055.01 | 0.005 | band |
| `taxes.T2.sgst` | T2 | G_STA | T_SGST | T2x | RBI SF app1 SGST 8,41,120.77 | 0.05 | band |
| `taxes.T2.svat` | T2 | G_STA | T_SVAT | T2x | RBI SF app1 sales tax 4,06,404.10 | 0.15 | band |
| `taxes.T2.sexc` | T2 | G_STA | T_SEXC | T2x | RBI SF app1 State excise 2,58,275.50 | 0.15 | band |
| `taxes.T3.total` | T3 | T_PIT | H_R1…H_U5, E_NFPR, E_BANK | T3, T3a | 10,44,763.68 + 7,873.82 (State D5) = 10,52,637.50 | tol_abs 1 | equal |
| `taxes.T3.households` | T3 | T_PIT | H_R1…H_U5 | T3a | HH share (0.7855 × MH 0021 + STT + 0028/0031/0032 + State D5); prior ≈ 8,35,75x | 0.10 (old base vs IFPRI range) | band |
| `taxes.T4.total` | T4 | T_CIT | E_NFPU, E_NFPR, E_BANK, E_NBFC, E_INSP | T4a | 9,11,055.01 | tol_abs 1 | equal |
| `taxes.T4a.fc` | T4a | T_CIT | E_BANK, E_NBFC, E_INSP | T4a | step 2.7 prior | 0.25 | band |
| `taxes.T4a.insp` | T4a | T_CIT | E_INSP | T4a | 10,240.93 (IRDAI provisions) | 0.15 | band |
| `taxes.T4a.nbfc` | T4a | T_CIT | E_NBFC | T4a | 43,801 (RTP provisions) | 0.15 | band |
| `taxes.P9a.total` | P9a | G_CEN, G_STA | T_PSUB | P9a | `supply.product_subsidies.total.current` −5,76,422.431949 | tol_abs 0.5 | equal |
| `taxes.P9a.centre` | P9a | G_CEN | T_PSUB | P9a | −2,30,794.47 (identified Centre items; §2.3) | 0.35 (the unexplained C_TRAD row is 18% of the total) | band |
| `taxes.P10a.net` | P10a | G_CEN, G_STA | T_PROD | P10a | P10 net −57,441.998622 (production's value) | tol_abs 0.5 | equal |
| `taxes.P10a.centre_net` | P10a | G_CEN | T_PROD | P10a | 411.76 − 1,10,042.74 = −1,09,630.98 | 0.30 | band |

Notes:
- Constraints cannot filter by `component`, so the gross D29/D39 sub-row totals are held by entry roles (gross_taxes anchored at 3%), not by a constraint (FR in §6).
- Production also declares P7 and P10: the targets must be the **same floats**, so read them from `ctx.block_constraints("production")`.
- Balancing: account balance already forces T_CUST, T_PSUB and T_PROD columns to equal their fixed rows. The equal constraints above are redundant but document the source.

---

## 4. Interfaces

**Needs (from dependencies):**
- **production**
  - P7 constraint targets by commodity (the exact floats), P8 entries (T_CUST ← C_*), P9 entries (T_PSUB ← C_*), P10 entries (T_PROD ← A_*).
  - Use-side entries for P7b: P2 IC by activity, C1 PFCE by commodity (total), C2 GFCE, I1 GFCF, CII/valuables, P5 exports.
  - If published, the GG share of GFCF by commodity (P7b non-ITC rule).
- **households** (`hh_keys`)
  - group membership of the 24 HCES fractile classes (R/U × p00_05…p95_100);
  - persons, households and average MPCE per class (the 2023-08/2024-07 window);
  - the HCES → NAS PFCE scale factor, if households computes one (else taxes derives k = 2.257 from `s1_1.pfce.current` / HCES aggregate and records it).
- **factors**
  - F1a: CE of F_LREG by household group (professions-tax key and T3a sensitivity key);
  - F2: mixed income by group (T3a sensitivity only).
- **Framework**
  - `balance.gras` (or permission to run an in-block RAS);
  - cvxpy for the feasibility LP;
  - a way to carry P7a balancing factors to the P7b satellite (FR-1 below).

**Publishes (for other blocks):**
- **Entries**: P7a; T1a/T2x (**gross-of-devolution** tax receipts of G_CEN and G_STA by type); P9a and P10a (government subsidy outlays and production-tax receipts, gross sub-rows); T3/T3a (household direct taxes by group, for closure's household-saving residual); T4a (corporate taxes by sector with FC public/private components, needed by fincorp for FC saving public/private (F4a/K2a) and by capital_financial/closure for NFC saving).
- **Satellites** (each carries a ref, as the framework requires):
  - `s7_igst_settlement` (S7);
  - `p7b_tax_by_use` (P7b);
  - `p7a_precheck` (P7a: row targets, column targets, room, excess placements, final accrual/cash ratio by type);
  - `p9a_by_commodity` (P9a);
  - `p10a_items` (P10a: identified D29/D39 items and the derived gross totals);
  - `direct_tax_split` (T4a: corporate D5 prior, quasi-corporate MH 0021 part, FC bottom-up provisions);
  - `t3a_sensitivity` (T3a: shares at the ₹5, 7 and 10 lakh thresholds).
- **Classification decisions** (read by government): a small `tax_classification` satellite (ref T1a) listing where each contested head went, so government does not also book it:
  - vehicle tax → T_OPRT;
  - professions tax → T_PIT;
  - STT → T_PIT;
  - CTT, equalisation levy, export duty → T_OPRT;
  - MISS → P9 on C_FINS;
  - LPG DBT beyond 2,280 → not a product subsidy;
  - NCCD gross.

---

## 5. Conflicts and choices

### Classification choices (decide before building; C1–C3 go to the orchestrator for DECISIONS.md)

- **C1. State motor-vehicle tax (₹1,10,326.52 all States + UTs; + ₹520.55 Union UTs). Recommend a product tax (T_OPRT on C_TREQ).**
  - Phase 0 default: R16 (household D59) + P10a (business D29), pending NAD.
  - Evidence against that default:
    - (i) Derived new-base D29 (2,84,694.70) is fully used by stamps, land revenue and property taxes (identified 2,54,928.92 + ULB property ≈ 29.4k).
    - (ii) Old-base D5 (TAX-14) leaves 4,854 of room.
    - (iii) In 2022-23 old-base D29 (2,46,133) likewise had no room for vehicles (93,541.5).
    - (iv) It closes 1,10,847 of the 1,58,230 TAX-1 gap.
  - Consequence: government's R16 must exclude vehicle tax. If the orchestrator keeps the Phase 0 default instead, the P7a row total drops to 28,57,111 (a 5.54% gap), and R16 grows by up to 1.1 lakh cr of household D59 that NAS evidently does not record.
- **C2. STT (₹33,777.78) and CTT (₹414.32).**
  - The gap map and ACCOUNT_STRUCTURE put STT in T_PIT ("reported with income tax in the Budget").
  - Evidence the other way:
    - TAX-14: old-base D5 = CIT + income tax + 4,854 excludes STT (25,085 in 2022-23);
    - the Finance Accounts class STT under "taxes on property, capital and other transactions" (section (c) = 0029 + 0030 + 0031 + 0032 + 0034 = 34,196.97) and CTT under "taxes on commodities and services";
    - the SNA treats taxes on financial transactions as product taxes (D214).
  - The SUT's C_FINS product tax (43,768) is small, and it must also hold GST on financial services.
  - **Recommendation:** keep STT in T_PIT (the gap-map default; its payer is overwhelmingly households and FPIs). Put CTT in T_OPRT (on C_FINS). Log the question to NAD, with the risk that GG revenue is double-counted by ≤ 34k if NAS has STT inside SUT product taxes.
- **C3. Quasi-corporate share of MH 0021 (≈ ₹2.17 lakh cr).**
  - The gap map says to move the firm/AOP part to NFC/FC "if material". Old-base NAS 2022-23 implies 21.5%; IFPRI 2022-23 implies about 10%. That is material either way.
  - **Recommendation:** control = old-base NAS ratio (same concept as NAS), cross-check = IFPRI. Band constraint `taxes.T3.households` ±10%.
  - The quasi-corporate entries sit in (T_PIT, E_NFPR/E_BANK). The current framework draft validates cells only at the group level (TAX × NFC/FC is allowed), so this is feasible under ref T3. It is a gap-map extension: log it.
- **C4. Professions tax (₹7,872.88 + agri income tax 0.94).**
  - The gap map (P10a) lists it as a production tax.
  - Evidence: TAX-14's note puts it in old-base D5, and D29 has no room.
  - **Recommendation:** D5, i.e. T_PIT ← H_* (component `professions_tax`) and (G_STA, T_PIT) under T2x.
- **C5. State excise excess over C_BVTB.** Gap-map default (licence fees on C_HOTL/C_TRAD), sized by the pre-check (at least 25,903 at product level before liquor VAT). If hotel and trade room is short, the next fallback is VAT on petroleum room, then T2x below cash. Every step is logged. NAD question open.
- **C6. UTGST (₹5,497.16)** is received by G_CEN (UTs without legislature are Union). Put it in T_CGST (component `utgst`) rather than T_SGST, whose column pays G_STA only. Similarly, UT-without-legislature sales tax and State excise sit in T_SVAT/T_SEXC with a G_CEN column entry (ref T1a).
- **C7. Equalisation levy (₹3,933.40; MH 0045)** → T_OPRT (G_CEN) on imported digital services (low). **Export duty (₹3,343.88)** → T_OPRT on exported goods (the SUT's "import duty" column excludes it, TAX-2). **Sale of confiscated goods (₹4,230.11)** is inside customs receipts but is not a tax: it is excluded via the TAX-2 bridge.

### Where two official sources disagree (control vs cross-check)

| item | source A | source B | recommended control | cross-check / why |
|---|---|---|---|---|
| SGST | RBI SF app1 all States+UTs 8,41,120.77 | FC16 KFI 28 States 8,00,112.02 (= FC16 MH 0006) | RBI SF (coverage = G_STA) | FC16; the gap is 3 UTs (TAX-5) |
| Sales tax/VAT | RBI SF 4,06,404.10 | FC16 3,97,467.06 | RBI SF | FC16 |
| State excise | RBI SF 2,58,275.50 | FC16 2,49,133.50 | RBI SF | FC16 |
| Vehicle tax | RBI SF 1,10,326.52 | FC16 1,06,020.99 | RBI SF | FC16 |
| Stamps & registration | RBI SF 2,28,154.98 | FC16 KFI 2,20,289.49 / FC16 MH 0030 2,20,192.58 | RBI SF | FC16 (KFI and MH differ by 96.91) |
| Union taxes | Receipt Budget (gross) | Finance Accounts (net + 901) | Receipt Budget for gross; FA as audit check | they agree to the rupee for CGST, CIT, IT, customs, excise (TAX-3, TAX-13) |
| Product taxes total | SUT 30,15,341.40 (+ import duty 2,28,887.27 = NAS 1.1 32,44,229.1) | budgets 28,57,111 (without vehicles) / 29,67,958 (with) | **SUT (margin wins)** | gap logged by type (TAX-1, UNEXPLAINED xfail). The SUT note §8.5 says product taxes were a balancing vector ("adjustments are primarily made in other vectors (IC, TTM, Product Taxes)"), which is a documented reason |
| Import duty | SUT 2,28,887.27 | customs less export duty 2,29,775.09 | SUT (production's P8) | FA (TAX-2, 0.39%) |
| Product subsidies | SUT −5,76,422.43 | Union St 7 + States St 36: 5,33,179 (TAX-9) | SUT | budgets (St 36 is partial and mixes product with production subsidies) |
| Fertiliser subsidy | St 7 1,88,291.62 = FC16 1,88,292.04 | SUT C_CHEM 2,07,569.12 | SUT for the cell; St 7 for the payer | gap of 19,277 logged |
| LPG subsidy | St 7 12,240.00 | FC16 fuel 8,500.00; SUT C_RPET 2,280.00 | SUT for the cell | St 7 (TAX-12, unexplained) |
| Cess on crude oil | FA `fa8.0038.04.117` 18,803.41 | PPAC 19,580.39 (+ NCCD 1,190.92) | FA (audited) for totals | PPAC as prior shape only |
| Household share of income tax | old-base NAS 2022-23: 0.7855 | IFPRI 2022-23: ~0.90 | old-base NAS (same concept) | IFPRI |
| FC tax provisions (RTP) | vintage 2024-12-26 | vintage 2025-12-29 | 2025-12-29 (latest) | the earlier one |
| Gross D39/D29 | new-base derived 3,42,136.70 / 2,84,694.70 (2023-24) | old-base SOA 4.0 2022-23: 2,88,983 / 2,46,133 | new base (NAS 4.2 identity) | old base, same year: derived new-base 2022-23 is 3,22,581 / 2,52,856 |
| CGST vs SGST symmetry | CGST + UTGST 8,26,119 | SGST 8,41,121 | both kept as row targets | TAX-7 (1.8%, not bridged) |

---

## 6. Risks, gaps, open questions

**Double-counting risks** (each needs a test or an interface note):

| # | Risk | Where | Guard |
|---|---|---|---|
| R1 | P7 total written twice | production must declare P7 only as a constraint, never as entries | test: no production entry in rows T_CGST…T_OPRT |
| R2 | Vehicle tax in T_OPRT **and** R16/P10a | government R16 | `tax_classification` satellite; test Σ over all refs of vehicle-tax items ≤ 1,10,847.07 |
| R3 | Professions tax in T_PIT **and** P10a | this block | one component only |
| R4 | STT in T_PIT and inside SUT product taxes | unobservable | logged question (C2) |
| R5 | MISS interest subvention (14,251.93) is in P9 (C_FINS −14,325.54) **and** in government R18 (St 7 interest subsidies 19,515.82) or P10a D39 | government R18; P10a | P10a and R18 use St 7 interest subsidies **less** MISS (5,263.89); tell government |
| R6 | Interest equalisation counted twice (St 7 3,699.99 = FA `fa9.3453.00.107` "Export Subsidy" 3,699.99) | P10a | use St 7 only |
| R7 | Food subsidy (St 7 2,11,814.39) as product subsidy and as GFCE | P9a vs C2a | excluded from P9a |
| R8 | LPG: only 2,280 is a product subsidy in the SUT; the other 9,960 of St 7 LPG (DBT to consumers) must not also be a subsidy | government R10 may treat it as D62 | note to government; NAD question |
| R9 | States' food subsidies (FC16 54,463.39, 21 States): if they are the C_TRAD −1,05,007 row (Q7), government must not also put them in GFCE | government C2a | NAD question (Q7) |
| R10 | GST compensation cess: T_GCES pays all cess to G_CEN; compensation grants are T2b (government) | government must not book cess as State tax revenue; FC16 KFI treats the compensation *loan* as a grant (note) | test |
| R11 | Devolution: T1a is gross; R1 (government) moves 11,29,493.71 to States | the State side must not count its share of central taxes as own tax | test: T2 uses own-tax lines only |
| R12 | IGST counted twice | S7 is a memo; SGST (MH 0006) already includes settled IGST | no T_IGST entries; S7 is a satellite only |
| R13 | NCCD netted twice | the Receipt Budget total deducts NCCD transferred to NDRF (−8,774.32) | use gross excise and customs heads |
| R14 | PPAC royalty (9,286.20 + 12,529.50) and petroleum direct taxes treated as product taxes | P7a prior | excluded (royalty is D45, rent) |
| R15 | Quasi-corporate MH 0021 left in households **and** corporate saving built net of it by fincorp/factors | closure | T3 split published; closure uses T_PIT ← H_* only |
| R16 | Customs: sale of confiscated goods (4,230.11) and export duty treated as import duty | T1 constraint | TAX-2 bridge |

**Places where the gap-map method cannot be followed as written, and the fallback:**
1. P7a prior "PFCE × item GST rate": no GST-rate table is ingested. Fallback: the SUT residual (MoSPI's own allocation) at product level (§2.1 step 3).
2. P7a compensation cess by commodity: no cess-by-product data (GSTN not automated). Fallback: legal-base products plus a PFCE-spread remainder; low.
3. T3a: no CBDT data (ISSUES P1-4, union_fiscal-3). Fallback: an HCES threshold-excess key (§2.6); low; very sensitive to the threshold.
4. T4a: RBI corporate finances (NFC tax provisions) and STRBI (SCB tax) are DBIE-only. Fallback: old-base NAS D5 shares, IRDAI/RTP provisions, E_BANK residual.
5. T3 "share estimated from CBDT ITR statistics": replaced by old-base NAS household D5, cross-checked with IFPRI.
6. P9a States' side: FC16 subsidies cover 21 States, and St 36 omits 6 States (state_fiscal-19). Fallback: the commodity map; the unexplained rows use the identified ratio.
7. P10a: the gap map scales gross items "so net = SUT −57,442". **Better anchor found:** NAS 4.2 gives gross D3, so the gross D29/D39 totals are derived, not scaled.
8. T1a/T2x "cash-to-accrual adjustment": no new-base NAS tax-by-type exists, so it cannot be estimated separately. It is the pro-rata share of the TAX-1 gap plus pre-check moves, labelled as such.
9. Gap-map cell lists miss some cells: (G_CEN|G_STA, T_OPRT), (G_STA, T_PIT), (G_CEN, T_SVAT/T_SEXC) for UTs, and (T_PIT, E_NFPR/E_BANK). Recommend writing them under T1a/T2x/T3 and adding the accounts to those refs' lists in `data/gap_map.csv` (orchestrator edit).
10. S7: State-by-month settlement is blocked. It stays annual, plus April–May 2023.

**Framework requests** (for `docs/phase2/FRAMEWORK_REQUESTS.md`):
- **FR-1:** a post-balancing hook, or a documented method, to rescale satellites (P7b) by the balanced z-factor of their parent entries.
- **FR-2:** an optional `components` filter on constraints (to hold the gross D29/D39 sub-row totals directly).
- **FR-3:** government depends only on production/households/factors, yet its R10/R16/R18/C2a treatments must match this block's classifications (R2, R5, R8, R9). Make government depend on taxes, or have government read the `tax_classification` satellite after taxes is built (orchestrator decision).
- **FR-4:** confirm that a ref may write cells outside its gap-map row/col lists when the group structure allows them (C3, point 9 above).

**Open questions for MoSPI NAD** (add to the H12 list):
- vehicle tax class;
- State excise licence fees;
- STT/CTT class;
- the C_TRAD −1,05,007 subsidy (Q7) and pesticides −62,440 (Q6);
- why SUT petroleum tax exceeds PPAC by 87,530 while alcohol tax is below State excise;
- whether NAS 4.2 "subsidy" = GG D31 + D39;
- LPG DBT class;
- the new-base treatment of quasi-corporations' income tax.

**Other risks:**
- The T1/T2 bands (5%, 15%) are judgement calls. If balancing needs slack on them, that is a finding (listed in BALANCING.md and ISSUES.md), not a tuning signal.
- The ULB property-tax coverage (284 ULBs) makes the "D29 is full" argument indicative, not proof.
- The FA "Farmers Income Support" head (51,616.91) may understate PM-KISAN if part is booked elsewhere (e.g. grants to UTs or NE); not verified.
- The old-base ratios (T3, T4a) come from the 2011-12 base, 2022-23 FRE. Label them so on the site.

---

## 7. Tests the builder should write

All targets are read from clean data inside the test (never typed in):
1. **P7 by commodity:** for every SAM commodity, Σ P7a entries = Σ `io_tables_sut_supply` `supply.product_taxes.sut_pNNN.current` over the concordance (|diff| ≤ 0.5). Grand total = `supply.product_taxes.total.current` (3,015,341.397664).
2. **No P7a entry on C_DWEL or C_PADM.** No negative P7a entry. No T_GCES entry on C_COAL. No GST entry on p065/p128-only columns.
3. **Customs:** (G_CEN, T_CUST) = `supply.import_duty.total.current` (228,887.267225) = Σ production P8 entries; and within 1% of `rb.tr.total.total_customs` − `rb.tr.0037.export_duty` − `rb.tr.0037.cesses_on_exports`.
4. **Net product taxes:** Σ P7a + P8 + P9 = `s1_1.taxes_on_products.current` − `s1_1.subsidies_on_products.current` (2,667,806.7) within 1 (GDP-3).
5. **Subsidies:** (G_CEN + G_STA, T_PSUB) = `supply.product_subsidies.total.current` = −`s1_1.subsidies_on_products.current` within 1.
6. **Production taxes:** Σ P10a = Σ `io_tables_sut_va` `va.net_production_taxes.*` (−57,441.998622) and ≈ `s7_1.total.net_production_taxes.current` within 1. Σ gross_subsidies components = −(`s4_2.subsidy.total.current` − `s1_1.subsidies_on_products.current`) within 3%. Σ gross_taxes = that + P10 within 3%.
7. **Union identities:** T1 CGST target = `rb.tr.0005…` + `rb.tr.0008…` + `rb.tr.0007…`. `rb.tr.0005` = `fa8.0005.total` − `fa8.0005.00.901`, and likewise for 0020, 0021, 0037, 0038 (`fa8.0038.01.901`). TAX-4: CGST + IGST + cess = `rb.tr.total.total_goods_and_services_tax_gst` (957,207.82).
8. **Direct taxes:** Σ T_CIT entries = `rb.tr.total.total_corporation_tax` (911,055.01) exactly (±1). No (T_CIT, E_RBI) entry. Σ T_PIT entries = Σ `rb.tr.0021.*` + `rb.tr.0034.security_transaction_tax` + MH 0028/0031/0032/0023/0024/0026 + RBI SF professions and agricultural income tax (±1). Household share within [0.78, 0.91] × MH 0021 (old-base and IFPRI bounds).
9. **T3a:** Σ over the 10 groups = the household constraint target; every group ≥ 0; and the U5 + R5 share is reported (asserting nothing beyond > 50%; the gap map expects > 90%, and a failure there is a finding, not a test error).
10. **T4a:** E_INSP within 15% of Σ IRDAI tax provisions (life t24 + t25; non-life t51 four groups). E_NBFC within 15% of Σ RTP NBFC-UL/ML/HFC/AIFI provisions (vintage 2025-12-29).
11. **State side:** each T2 constraint target equals its RBI SF app1 series; the FC16 KFI values are within the TAX-5 coverage band (≤ 6%) of RBI SF.
12. **S7 satellite:** Σ `fa8.0008.01.total` + `fa8.0008.02.total` = `fa8.0008.total` (−4,850.4302). The CGST-side ITC (`fa8.0005.00.105`) equals minus the IGST-side ITC to CGST (`fa8.0008.02.105`) within 0.01. The S7 residual equals the `utgst`-excluded IGST component inside T_CGST.
13. **P7b satellite:** for each (type, commodity), Σ uses = the P7a entry. GST and T_GCES export cells = 0. Petroleum excise/VAT export cells = 0.
14. **Classification guard:** vehicle-tax, professions-tax and MISS items appear in exactly one ref across the taxes entries and the `tax_classification` satellite (and, once government is built, across government's entries).
15. **Provenance:** every entry, constraint and satellite row has a prov_id. Every `estimated` record has a non-empty method that cites the gap-map ref and the assumption: threshold ₹7 lakh; old-base ratios with their vintage; uniform TAX-1 gap scaling; licence-fee placement.

---

## 8 Cross-plan review (2026-09-30, cross-plan critic; details and ids in `CROSS_REVIEW.md`)

What this block must change or confirm:

1. **Decisions for the orchestrator (CROSS_REVIEW §7):**
   - D-1 vehicle tax as a product tax (recommended: accept; government already plans R16 = empty with a contingency);
   - D-8 quasi-corporate MH 0021 on E_NFPR/E_BANK (accept);
   - D-9 STT in T_PIT (accept; NAD question).

   Your extra cells need gap-map extensions: (G_*, T_OPRT), (G_STA, T_PIT), (G_CEN, T_SVAT/T_SEXC), (T_PIT, E_NFPR/E_BANK).
2. **XR-18 DAG:** approve government += taxes, so government reads `tax_classification` and your P9a/P10a entries. Keep `tax_classification` complete: vehicle tax, professions tax, STT, CTT, equalisation levy, export duty, MISS, LPG (2,280 in P9 / 9,960 not a product subsidy), NCCD, PM-KISAN (P10a D39), interest equalisation, PM-AASHA, FC16 Union "business".
3. **XR-15 do not tighten production's `product_taxes.*` targets.** Your `taxes.P7.<C_x>` (refs [P7a], tol 0.5) is a different selection from production's (refs none, tol = n_cells), so the tighter one binds. Copy production's target *and* tol_abs, or keep the equality as a test.
4. **XR-19 components on P10a.** The time series (F20) needs identified items. Split `gross_taxes` into `stamps_registration`, `land_revenue`, `property_tax` and `other_production_taxes` (State and Centre as they apply), and keep `gross_subsidies`. Freeze these names.
5. **XR-20:** with the components filter available, hold the gross D29/D39 sub-row totals as constraints (component sets), not only through entry roles.
6. **XR-23 P9a C_TRAD row (−1,05,006.67, Q7):** before applying the 0.516 identified ratio, assign to G_STA the States' food subsidies you identified (FC16 21 States 54,463.39, grossed up like government's R10). This records State food subsidies exactly once: government excludes them from GFCE and R10 on the understanding that they sit here. Log it as an assumption.
7. **XR-6 boundary:** in T4a, deposit-taking NBFCs and HFCs belong to E_BANK (E_BANK ≡ K_BANK ≡ FSF ODC). Move their share of the RTP NBFC/HFC tax provisions from E_NBFC to E_BANK, using FSF `fc_odc_nbfc_dt` / `fc_odc_hfc_dt` weights.
8. Minor text fix: §2 table P10a says gross D29 = 2,84,694.3; §2.4 says 2,84,694.70. Use one (the SUT P10 net −57,441.998622 gives 2,84,694.70).
9. timeseries F14 will register the UTGST (+5,497.16) bridge because you put UTGST in T_CGST (`utgst`); keep that component name.
