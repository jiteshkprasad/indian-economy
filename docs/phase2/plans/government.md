# Phase 2 plan: `government` block

Written 2026-09-30 by the data scout for `government`. This is research only: no code, no build. Every value was read from `data/clean/<unit>/*.parquet` with polars (scratch scripts outside the repo). "Indicative" means my own arithmetic on clean values, which the builder must recompute in the block. Amounts are ₹ crore, current prices, FY 2023-24.

- **Refs owned:** C2a R1 R2 R2k T2b R6 R7 R9 R9a R9b R10 R15 R16 R18 K3 K3a K6 K8e.
- **Depends on:** production, households, factors.
- **Inputs read:** DESIGN_BRIEF.md; ACCOUNT_STRUCTURE §4.4, §4.5, §5, §7, §9, §11; GAP_MAP §3–§4 and `data/gap_map.csv`; DECISIONS D0-5, D0-7, D1-2; ISSUES P0-10, P1-1, P1-2; COVERAGE and RECONCILIATION (GOV-1…18, EXT-14, FIN-1, TAX-1, TAX-14); `pipeline/ingest/{union_fiscal,state_fiscal,mospi_nas_2026,external_sector,rbi_banking_corporate,rbi_financial_accounts,io_tables,hces_consumption,labour_enterprise_surveys}_coverage.yaml`; `pipeline/sam/structure.yaml` and `accounts.yaml`; and the sibling plans `factors.md`, `households.md`, `taxes.md`, `rest_of_world.md` and `closure.md`, read for their interfaces.

---

## 1. Summary (plain English)

- **Most of the government block is official money moving between known accounts:**
  - devolution (₹11.29 lakh cr);
  - Centre-to-State grants;
  - the RBI surplus (₹87,416 cr, cash);
  - dividends;
  - pensions;
  - the two GST-compensation uses of the cess (₹44,946 cr in grants, and ₹78,104 cr that repaid the 2020-22 back-to-back loans). The ₹78,104 cr turns out to be derivable exactly from clean data.
- **The "grants don't reconcile" problem (H9, GOV-9/15/16) is essentially solved.** Two items explain the Union-vs-State gaps to within ₹180 cr:
  - The Union's grant head MH 3601 carries ₹68,345 cr of net transfers into its own reserve funds, which are not grants.
  - The IGAS-2 grantee view files ₹73,176 cr of Finance Commission local-body and health grants under other grantees.

  Union releases then match the States' receipts to within ₹172 cr (0.03%). The States' receipts become the control.
- **The government's own consumption (₹31.2 lakh cr GFCE) is split Centre vs States.**
  - Free grain (₹1.64 lakh cr) goes 100% to the Centre.
  - Own services (administration, education, health, construction, water) are split with budget functional keys, pinned to the NAS value-added split that `factors` already publishes.
  - The Centre comes out at about a third.
- **Government saving (−₹3.18 lakh cr) is split with a bridge from the budget revenue balances.**
  - The bridge explains only part of the NAS total; about ₹2.1 lakh cr remains and must be allocated and shown.
  - The States' saving is close to zero, so its sign is fragile. Balancing cannot flip a sign, so this needs a framework decision.
- **Three things in the gap map cannot be followed as written:**
  1. Government transfers with the rest of the world are capital transfers in NAS, not current. So R15 stays empty and they go to K6.
  2. Motor-vehicle tax is not a household transfer (R16); `taxes` books it as a product tax. So R16 is essentially empty.
  3. The imputed-pension return flow (R9b) cannot be the gap map's ≈₹4.3 lakh cr: NAS State wages have no room for it. I recommend Centre-only (₹1.87 lakh cr) pending a MoSPI answer.
- **Two ownership gaps must go to the orchestrator.** No ref owns the government's interest receipts from non-government units, or its rents and royalties (mining royalties to States alone are ₹1.26 lakh cr). Without them, government income is short by lakhs of crores.

---

## 2. Ref-by-ref table

Conventions:

- "row ← col": rows receive, columns pay.
- H_g = H_R1…H_U5.
- **Role:** fixed, anchored (with tol_rel), or free (with confidence).
- **Label:** the entry `status`: official, derived or estimated.
- Series ids are exact. Periods are `2023-24` unless stated.
- Vintages:
  - `union_fiscal_fa_*`: 2024-12-10, Audited.
  - `union_fiscal_afs`, `_exp_profile`, `_gcca`, `_rb_receipts`: 2025-02-01, Actuals.
  - `state_fiscal_rbi_sf_*`: 2026-01-23, Actuals.
  - `state_fiscal_fc16_*`: 2026-02-03 / 2026-02-05.
  - `mospi_nas_2026_*`: 2026-08-31, Final.
  - `io_tables_sut_*`: 2026-08-31.
  - `external_sector_*`: 2026-07-31.
  - `finsector_markets_pfrda_sg`: 2026-09-28, derived.

| Ref | Cell (row ← col) | Entries (component) | Source datasets / series_id | 2023-24 values (₹ cr) | Role / confidence | Method (details in §2.x) | Label |
|---|---|---|---|---|---|---|---|
| **C2a** | C_c ← G_CEN, C_c ← G_STA, for c ∈ {CROP, PADM, EDUC, HLTH, CNST, UTIL} | 10 entries: `total`. No C_CROP ← G_STA; no C_UTIL ← G_CEN, because the Centre seed is 0 | Targets: `io_tables_sut_use` `use.gfce.sut_p001/p002/p127/p130/p131/p151/p152/p153.current`, mapped by `data/concordance/io_tables_sut_product_to_sam34.csv` (or production's C2 constraints). Keys: `union_fiscal_fa_expenditure` sections `fa9.section.{organs_of_state,fiscal_services,administrative_services,defence_services}`, `fa9.2202/2203/2204/2205/2210/2211/3054/2059.total`; `state_fiscal_rbi_sf_appendices` `app2.total_expenditure.{ii.a,ii.b,ii.d,ii.f,i.a.1,i.a.2,i.a.3,i.a.4,i.b.7.i,ii.d.iv}…in.all_states_uts.actuals`; factors' `gg_centre_state_key` | SUT GFCE by commodity: CROP 1,63,971.75; PADM 17,82,644.45; EDUC 7,41,336.46; HLTH 2,29,757.34; CNST 1,15,146.84; UTIL 88,170.30. Σ 31,21,027.14 (NAS 1.14 31,21,027.37). *Indicative* G_CEN: CROP 1,63,971.75; PADM ≈7,86,973; EDUC ≈52,918; HLTH ≈19,616; CNST ≈14,762; total ≈10,38,240 (33.3%) | C_CROP←G_CEN **fixed**. Others free: PADM, EDUC, HLTH medium; CNST, UTIL low | Grain 100% Centre. Own output: 2-margin RAS, with seed = functional revenue keys and Centre column total = F4b key × own-output GFCE (§2.1) | CROP derived; rest estimated |
| **R1** | G_STA ← G_CEN | 7 entries by tax: `cgst`, `corporation_tax`, `income_tax`, `customs`, `union_excise`, `service_tax`, `other_commodity_taxes` | `union_fiscal_fa_receipts` `fa8.0005.00.901`, `fa8.0020.00.901`, `fa8.0021.00.901`, `fa8.0037.00.901`, `fa8.0038.01.901`, `fa8.0044.00.901`, `fa8.0045.00.901` (sign flipped) | 3,42,787.33; 3,39,023.79; 3,91,527.68; 39,581.66; 14,978.57; 210.42; 1,384.26. **Σ 11,29,493.71** | fixed | As published (Union audited). Cross-checks §5 C2 | official |
| **R2** | G_STA ← G_CEN | 2 entries: `fc_grants`, `css_and_other` (current part only) | Control: `state_fiscal_rbi_sf_appendices` `app1.total_revenue.ii.d-grants_from_the_centre.in.all_states_uts.actuals`; parts `…ii.d.5-finance_commission_grants…`, `…ii.d.3-centrally_sponsored_schemes…`, `…ii.d.7-other_grants…`, `…ii.d.6…`, `…ii.d.1…`, `…ii.d.2…` | Control 5,27,931.05 = FC 1,43,917.18 + CSS 2,76,511.79 + other 1,06,811.03 (incl. GST comp 45,464.24) + Art. 275 605.07 + plan −16.71 + 102.69. **R2 current = 5,27,931.05 − T2b(i) 44,945.51 − R2k 1,23,957.73 = 3,59,027.80**: `fc_grants` 1,43,917.18 and `css_and_other` 2,15,110.62 | `fc_grants` fixed; `css_and_other` anchored, tol_rel 0.10 (it absorbs the R2k estimate) | Total from the States' receipts, less the T2b(i) and R2k parts (§2.2) | fc official; css derived |
| **R2k** | K_GSTA ← K_GCEN | 1 entry `igas2_capital` | `union_fiscal_fa_gia` `gia.cash.state_governments.capital_assets`, `gia.cash.ut_governments.capital_assets` | 1,19,435.32 + 4,522.41 = **1,23,957.73**. Excluded: ULB 1,479.24; PRI 0 (§2.2) | free, medium | IGAS-2 grants "for creation of capital assets" to State and UT governments | derived |
| **T2b** | G_STA ← G_CEN | 2 entries: `compensation_grants`, `cess_loan_recovery` | (i) `union_fiscal_fa_expenditure` `fa9.3601.08.112` + `fa9.3602.08.106`. (ii) `union_fiscal_afs` `afs.pa_disbursements.xi_goods_and_service_tax_compensation_fund` + `fa9.3601.08.904` + `fa9.3602.08.904` | (i) 43,788.41 + 1,157.11 = **44,945.51**; KFI `kfi.a_1_4_a…all_states_28` 43,788.41 is identical for the 28 States. (ii) 1,21,159.00 − 41,897.89 − 1,157.11 = **78,104.00** | (i) fixed; (ii) fixed | (ii) is exact arithmetic: GST Compensation Fund outgo less the grants it financed. Current, per the gap-map default; §5 C7 | (i) official; (ii) derived |
| **R6** | G_CEN ← E_RBI | 1 entry `cash_basis` | `union_fiscal_fa_receipts` `fa8.0050.00.106`; cross-check `rbi_banking_corporate_rbi_surplus_timing` `r6.surplus_received_by_centre_cash.current` | **87,416.2162**; cross-check 87,416.22 (GOV-11) | fixed | Cash basis (D0-7). The super-dividend test is reported, not applied (§5 C8) | official |
| **R7** | G_CEN ← E_NFPU / E_BANK / E_INSP; G_STA ← E_NFPU | 4 entries: `public_undertakings` (101 + 200), `banks` (108 + 109), `lic` (107), `state_enterprises` | `union_fiscal_fa_receipts` `fa8.0050.00.101/.107/.108/.109/.200`, `fa8.0050.total`; `state_fiscal_rbi_sf_appendices` `app1.total_revenue.ii.c.2-dividends_and_profits.in.all_states_uts.actuals` | E_NFPU 63,827.41 + 1,078.79 = 64,906.20; E_BANK 13,806.57 + 488.99 = 14,295.56; E_INSP 4,272.54. **Union Σ 83,474.29** (= 1,70,890.51 − RBI 87,416.22). States 6,914.54 | fixed. The payer mapping of 101 is an assumption (§6) | By payer type as published; RBI excluded (it is R6) | official |
| **R9** | H_g ← G_CEN, H_g ← G_STA | 20 entries (group split = R9a) | Union `fa9.2071.total`, less `fa9.2071.01.117` + `.01.902` (NPS employer contribution) and `fa9.2071.01.118` (CGHS medical). States `app2.total_expenditure.ii.e-pensions.in.all_states_uts.actuals`, less `finsector_markets_pfrda_sg` `m7d.annual_contribution_employer.state_govt.current` | Union 2,38,328.30 − 9,398.08 − 4,282.72 = **2,24,647.49**. States 4,90,983.18 − 43,992.43 = **4,46,990.75** | Group entries free, low. Totals banded (§3) | Gross D62 cash, net of items that are CE (NPS) or GFCE (CGHS) (§2.4) | derived total; estimated split |
| **R9a** | (the group split of R9) | as R9 | factors' `factor_income_keys` (F_LREG share by group); `labour_enterprise_surveys_plfs_enterprise_type` `t35.worker_share.govt_public_sector.{rural,urban}.person` (period `2023-07/2024-06`) | Public-sector worker share: rural 11.0%, urban 10.1%. IFPRI `io_tables_ifpri_2223_datapaper` `ifpri.t10.transfers_government.q1..q5` (2022-23; 2.9/3.3/3.8/4.9/11.0% of income) is a cross-check | free, low | Key ∝ F_LREG income by group × R/U public-sector share (§2.4) | estimated |
| **R9b** | G_CEN ← H_g, G_STA ← H_g | Recommended: 10 entries (G_CEN only). Sensitivity: 20 | `fa9.2071.01.total`, `fa9.2071.02.total` and the R9 deductions; State formula inputs as R9 | **Recommended prior: G_CEN = civil (96,235.30 − 9,398.08 − 4,282.72 = 82,554.50) × 21/39 = 44,452.42 + defence 1,42,093.00 = 1,86,545.42. G_STA = 0.** Sensitivity (gap map as written): G_STA 4,46,990.75 × 21/39 = 2,40,687.33 | free, low | S&M §3.1.1 factor (1 − 18/39) for Centre civil, defence unadjusted. States held at 0 because NAS 4.1 State CE leaves no room (§5 C5). Key = R9a key | estimated |
| **R10** | H_g ← G_CEN, H_g ← G_STA | 20 group entries per component: G_CEN `social_security`, `lpg_dbt`; G_STA `cash_schemes` | `state_fiscal_fc16_subsidies` `sub.cash_transfers.in-*.gg_state` (20 States), `sub.social_security.in-*.gg_state` (21 States), `sub.social_security.in.gg_centre`; gross-up with `state_fiscal_fc16_state_accounts` `fa.revenue_expenditure.mh2235.in-*` and `app2.total_expenditure.i.a.9-social_security_and_welfare…all_states_uts`; `union_fiscal_exp_profile` `stat7.petroleum` less production's P9 entry on C_RPET | States (21): 88,719.54 + 1,17,667.29 = 2,06,386.82. × g1 1.01319 (MH 2235 28 States 2,37,115.92 / the 21 States 2,34,028.24) × g2 1.02494 (2,43,029.49 / 2,37,115.92) ≈ **2,14,300** (indicative). Centre 18,603.44 + LPG DBT 12,240.00 − 2,280 = 9,960.00 | free, low | Scheme totals by government; group keys from `hh_keys` / `hh_state_xwalk` (§2.5). **Excludes** PM-KISAN (P10a), free grain (C2a), health and education in kind (GFCE) | estimated |
| **R15** | G ← R_ROW, R_ROW ← G | **none** | `external_sector_bop_bpm6_annual` `bpm6.inr.bpm6_1_c_2.{credit,debit}.current` | 1,463 / 7,820 (net −6,357) | — | NAS 6.1 books these as capital transfers. Written in K6 instead (§5 C6) | — |
| **R16** | G ← H_g | **none** in the prior. Contingent component `vehicle_tax` only if the orchestrator rejects taxes' C1 | — | Vehicle tax (all States + UTs) `app1.total_revenue.i.a.3.iii-taxes_on_vehicles…` 1,10,326.52 goes to taxes' T_OPRT | — | Fees are sales of non-market output, already in PFCE / net GFCE. Old-base NAS households pay no D7. Fines are unquantifiable on the State side (§2.6) | — |
| **R18** | E_NFPU ← G_CEN, E_INSP ← G_CEN, E_NFPU ← G_CEN (co-ops) | 3 entries: `psu_revenue_grants`, `lic_pension_subsidy`, `coop_revenue_grants` | `union_fiscal_fa_gia` `gia.cash.public_sector_undertakings.{total,capital_assets}`, `gia.cash.cooperatives.{total,capital_assets}`; `union_fiscal_exp_profile` `stat7.interest_subsidies.interest_subsidy_to_lic_for_pension_plan_for_senior_citizens` | 40,451.61 − 16,434.16 = **24,017.45**; 134.96; 1,351.72 − 159.15 = **1,192.57** | free, low | Only current transfers that `taxes` does not classify as D31/D39 (§2.7) | estimated |
| **K3** | K_GCEN ← G_CEN + K_GSTA ← G_STA | constraint only (entries are K3a) | `mospi_nas_2026_s1_9` `s1_9.general_government.current` | **−3,18,384.38** | constraint, equal | — | official |
| **K3a** | K_GCEN ← G_CEN, K_GSTA ← G_STA | 2 entries `gross_saving` | Bridge (§2.8): `afs.cfi_rev_receipts.excess_of_disbursements_over_receipts_revenue_deficit`; FA 797 / "met from" lines; `union_fiscal_gcca` `stat6.grand_total`; T2b(ii); `app4.a-surplus_deficit_on_revenue_account…`; `app2…ii.c.1-appropriation_for_reduction…`; factors' F4b | Bridge before CFC: Centre −3,64,449.89; States −1,21,826.77. Unexplained remainder vs NAS −2,07,786.88 (after CFC 3,75,679.16). *Indicative*: G_CEN ≈ −3,55,000; G_STA ≈ +36,700 | free, low. **Sign risk on G_STA** | Budget balance → NAS concept; remainder allocated by revenue-expenditure shares and logged | estimated |
| **K6** | K_ROW ↔ K_GCEN; K_ROW ↔ resident K_*; K_* ← K_GCEN / K_GSTA | RoW: `gg_payments`, `gg_receipts`, `nongg_net`, `npnfa`. Domestic: by COFOG function × payer (§2.9) | RoW: `external_sector_invisibles_annual` `invis.inr.official_transfers.{payments,receipts}.current`; `mospi_nas_2026_s6_1` `s6_1.capital_transfers_to_general_government_from_the_rest_of_the.current`, `…to_corporations_households_and_npishs_net…`, `…acquisitions_less_disposal_of_non_produced…`. Domestic: `mospi_nas_2026_s4_2` `s4_2.capital_transfer.<fn>.current`; `union_fiscal_fa_gia` capital by grantee | RoW: 8,557 paid / 1,558 received (net −6,999 vs NAS −6,999.68); non-GG +1,555.69; NPNFA −1,666.26. Net −7,110.25 (as rest_of_world expects). Domestic GG → non-GG: COFOG **1,76,709.98** (incl. ~8.5k to RoW, §6). Union identifiable non-GG capital grants 38,581.91 | RoW anchored, tol 0.01; domestic free, low | §2.9 | RoW official; domestic estimated |
| **K8e** | K_GSTA ← I_LOAN; I_LOAN ← K_GCEN | 2 entries `gst_b2b_repayment` | as T2b(ii) | **−78,104.00** each | fixed, **conditional** on capital_financial netting it out of FSF (§4.3) | Negative incurrence (States) and negative acquisition (Centre) | derived |

### 2.1 C2a: GFCE by commodity, Centre vs States

1. **Totals.** Read the six SUT GFCE commodity totals, using production's C2 constraints if the framework exposes them. Otherwise recompute them from `io_tables_sut_use` `use.gfce.sut_pNNN.current` with the committed concordance. Only 8 SUT products are non-zero: p001 paddy 1,01,441.21, p002 wheat 62,530.54, p127 construction 1,15,146.84, p130 water 58,037.74, p131 other utilities 30,132.56, p151 PADM 17,82,644.45, p152 education 7,41,336.46, p153 health 2,29,757.34.
2. **C_CROP → 100% G_CEN, fixed.** Free PDS grain is a social transfer in kind, FCI sits inside G_CEN, and S&M says food-subsidy GFCE is compiled from CGA food-subsidy data. No C_CROP ← G_STA entry. Cross-checks, not imposed:
   - `stat7.food.food_subsidy` 2,11,814.39;
   - `fa9.2408.01.102` 1,84,468.93;
   - FC16 `sub.food.in.gg_centre` 2,30,755.71;
   - COFOG 10 social-protection FCE 2,48,473.62 ≥ grain 1,63,971.75.
3. **Own-output commodities (PADM, EDUC, HLTH, CNST, UTIL): 5×2 RAS.**
   - **Seed** = cash functional revenue expenditure by level, excluding interest, pensions, intergovernmental grants, subsidies and lotteries:
     - Centre (FA): PADM = organs of state 13,458.28 + fiscal services 47,147.89 + administrative 1,44,395.31 + defence 2,97,738.47 = 5,02,739.95; EDUC = 2202 + 2203 + 2204 + 2205 = 90,335.39; HLTH = 2210 + 2211 = 39,750.22; CNST = 3054 + 2059 = 18,891.02; UTIL = 0. The Union's MH 2215 (71,386.36) is Jal Jeevan transfers and capital, not own output.
     - States (RBI SF all States + UTs): PADM = ii.a 46,749.71 + ii.b 40,535.11 + ii.d 2,72,523.94 + ii.f 20,418.85 − lotteries 11,543.26 = 3,68,684.35; EDUC = i.a.1 6,81,183.32; HLTH = i.a.2 2,10,580.93 + i.a.3 36,251.11 = 2,46,832.03; CNST = i.b.7.i 60,611.97 + ii.d.iv 13,849.22 = 74,461.19; UTIL = i.a.4 45,751.43.
     - Seed Centre shares: PADM 0.5769, EDUC 0.1171, HLTH 0.1387, CNST 0.2024, UTIL 0.
   - **Row totals** = the SUT commodity totals (fixed).
   - **Column total for G_CEN** = factors' F4b key (`gg_centre_state_key`, Centre share 0.295655 = (NAS 4.1 Centre 5,77,518.54 + Union revenue GIA to autonomous bodies 51,351.67) / NVA 21,27,032.48) × own-output total 29,57,055.38 = **8,74,268.21**. factors requires that "C2a own-output split must use the same key".
   - Assumption, stated and labelled: the non-CE cost structure (IC + CFC − sales) is proportional to CE across levels. This probably understates the Centre, because defence IC is heavy. Log it.
   - *Indicative* result (Centre share): PADM 0.4415 (≈7,86,973), EDUC 0.0714, HLTH 0.0854, CNST 0.1282, UTIL 0.
4. **Diagnostics** (report only):
   - implied Centre share of GFCE (≈33.3%) against NAS 4.1 Centre-plus-autonomous NVA share;
   - EDUC + HLTH G_STA against KFI `kfi.b_5_a/b_5_b` (health 2,66,969.82, education 6,72,224.88, incl. capital);
   - C_CROP against households' `s8_food_stik` total (must equal 1,63,971.75).

### 2.2 R1, R2, R2k, T2b: Centre → States

- **R1.** The Union minor head 901 lines give Σ 11,29,493.71. This equals `rb.tr.0710.less_states_share` −11,29,493.71, `afs.cfi_rev_receipts.state_s_share_excluded_from_the_consolidated_fund` 11,29,493.71 and `state_fiscal_fc16_transfers` `tsm.states_share.actuals` 11,29,494.0 (GOV-3).
- **The H9 bridge** (new; add it to BALANCING.md and to a `gov_grants_bridge` satellite). The data show the following.
  - **MH 3601 decomposes as:** `fa9.3601.total` 5,39,963.59 = releases 4,71,916.39 (this includes −2,608.03 "Recoveory of unspent balance", misspelt, in 06.913) + other recoveries −297.77 + transfers to reserve funds (minor head 797) 1,98,235.88 + "Deduct – amount met from … Fund" −1,29,890.92.
  - **Net releases** = 4,71,618.62 to States. MH 3602 gives 56,484.84 to UTs with legislature. Together **5,28,103.46**, against RBI SF 5,27,931.05: **+172.42 (0.03%)**. States-only against KFI 4,72,465.88: −847.26.
  - **The ₹68,344.96 cr net fund transfer inside MH 3601 is the GOV-9 "UNEXPLAINED" gap** (+67,246). Remove it and the GOV-9 measure (net releases + St 18 IV 55,213.15 = 5,26,831.77) sits 1,099.28 (0.2%) below RBI SF.
  - **GOV-15.** IGAS-2 "State Government" (cash + kind) is 3,98,622.97. Net releases 4,71,618.62 − 3,98,622.97 = 72,995.66, against FC local-body and health grants `fa9.3601.07.102` 47,260.15 + `.103` 21,223.04 + `.106` 4,692.62 = 73,175.81. **Residual −180.15.**
  - **GOV-16** is the same local-body item seen from the other side.
- **Control choice.** `G_STA ← G_CEN` grants (R2 + T2b(i)) and R2k together equal the States' treasury receipts, RBI SF 5,27,931.05 (all States + UTs with legislature, the G_STA coverage). This is the "treasury view":
  - CSS money released outside State treasuries stays G_CEN spending. It sits in the Union's own functional heads, e.g. MH 2505 rural employment 89,153.79 and MH 2215 water 71,386.36. Statement 18's CSS revenue 4,25,295.58 exceeds MH 3601.06 net (2,38,795.63) by 1,86,499.95.
  - Union grants paid directly to ULBs are also outside the control: IGAS-2 `gia.cash.urban_local_bodies.total` 70,748.92, which includes the FC urban grants that do pass through States; the ULB dump shows `ulb.grants_for_centre_s_initiatives` 54,108.73. They stay with G_CEN too. Log this as a known limit (§6).
- **T2b(i) GST compensation grants: Union 44,945.51.** Recommended because it is the payer's audited figure and equals KFI for the 28 States exactly. RBI SF `…ii.d.7.gst_compensation_2…` is 45,464.24 (+518.72, into R2 `css_and_other`).
- **R2k = IGAS-2 capital to State + UT governments = 1,23,957.73.**
  - States book every central grant as revenue (RECONCILIATION §4), so R2k comes out of the States' current receipts.
  - ULB capital (1,479.24) is excluded for consistency with the treasury view.
  - The Stmt 6 and IGAS-2 totals tie (GOV-14: 3,03,915.55 vs 3,03,915.56).
- **R2 current = 3,59,027.80**: `fc_grants` 1,43,917.18 (RBI SF FC grants) + `css_and_other` 2,15,110.62 (residual).
- **T2b(ii) = 78,104.00** (derived exactly):
  - The GST Compensation Fund took in 1,43,109.49 (`afs.pa_receipts.xi_…`; cess `fa8.0009.total` 1,41,436.16).
  - It paid out 1,21,159.00: grants 43,055.00 plus **78,104.00**, which matches the Receipt Budget statement quoted in the gap map.
  - Accumulation of 21,950.49 stays in G_CEN (saving).

### 2.3 R6, R7: RBI surplus and dividends

- **R6 = 87,416.2162** (cash, D0-7). E_RBI's accrued 2023-24 surplus `xii_1.surplus_transferred` (2023-24) 2,10,873.99 is capital_financial's K9b timing item, not an R6 entry. `rbi_banking_corporate_rbi_accounts` holds 3 vintages per period, so use `rbi_surplus_timing`, or pass `vintage`.
- **R7.**
  - Union dividends are 1,70,890.51 in total (FA). The Receipt Budget `rb.ntr.total.total_dividends_and_profits` gives 1,70,876.97 (−13.54). Use FA.
  - Take out RBI 87,416.22 (that is R6; counting it again is a double count).
  - Map 101 "Public Undertakings" and 200 "other investments" to E_NFPU, 108/109 to E_BANK, and 107 LIC to E_INSP.
  - States: 6,914.54 → E_NFPU. Cross-check FC16 State accounts MH 0050 (24 States) 6,698.5.

### 2.4 R9, R9a, R9b: pensions and the imputed contribution

1. **R9 totals.** Remove two items so they are not counted twice:
   - the employer NPS contribution, which is CE and reaches households through F_LREG, and then I_INPE;
   - CGHS pensioners' medical costs (4,282.72), a social transfer in kind already in health GFCE.
   Values:
   - Union: 2,24,647.49.
   - States: 4,46,990.75. Assumption, stated: the PFRDA State-sector employer contribution (43,992.43) is booked inside the States' pension head. Most States use MH 2071 "Government contribution for DCPS".
   Delhi pensions paid by the Union (`fa9.2071.01.120`, 4,401.72) stay with G_CEN as payer.
2. **R9a key.** For each group: F_LREG income (factors' `factor_income_keys` or F1a entries) × the PLFS public-sector worker share of its area (rural 11.0%, urban 10.1%). Normalise within G_CEN and G_STA separately, with the same key for both. Report the IFPRI t10 profile as a cross-check. No microdata (D1-2), so confidence is low.
3. **R9b.** The gap-map formula is Centre civil OPS × (1 − k/39), k = 18 (2023-24 − 2005-06), plus defence and OPS States unadjusted. S&M §3.1.1, as quoted in DESIGN_REVIEW row 54: "only the remaining portion will be treated as CE"; "States where OPS is still operational, no adjustments have been made".
   - **Recommended prior: G_CEN 1,86,545.42, G_STA 0** (§5 C5). Keyed with the R9a key (the same key as government CE by group).
   - Sensitivity run with G_STA 2,40,687.33, using a uniform k for all States. The OPS/NPS State list is not in clean data and must not be typed from memory.
   - **Test:** GG GDI with and without R9b (closure's R3 request, §7 T14).

### 2.5 R10: cash transfers to households

1. **G_STA `cash_schemes`** = FC16 States' `cash_transfers` + `social_security` for the 21 reporting States (2,06,386.82). Gross it up twice:
   - to 28 States with FC16 State-accounts MH 2235 (g1 = 1.01319);
   - to States + UTs with RBI SF social security and welfare (g2 = 1.02494).
   Result ≈ 2,14,300.
2. **G_CEN**:
   - `social_security` 18,603.44 (FC16 Centre). Flag: if it includes NSAP released through MH 3601, it is double counted with States. No clean NSAP split exists (the Union's own `fa9.2235.03.total` is 7.57).
   - `lpg_dbt` 9,960.00 = `stat7.petroleum` 12,240.00 − production's P9 entry on C_RPET (2,280.00, per taxes' R8 note). SNA 2008 treats transfers to households as consumers as social benefits.
3. **Excluded**, each with its reason logged:
   - PM-KISAN: taxes' P10a (`fa9.2401.00.130` 51,616.91); factors also rules it out of R10.
   - MISS: P9 on C_FINS.
   - Education fee reimbursement and PM-JAY-type health: social transfers in kind inside GFCE (C2).
   - Housing grants to beneficiaries and loan waivers (FC16 States `housing` 12,913.5, `loan_waiver` 24,505.3): capital transfers, K6.
   - State food subsidies (54,463.39): taxes' Q7 / C_TRAD candidate.
4. **Group keys** from `hh_keys` (`pop_persons`). State schemes go through `hh_state_xwalk` when State detail is used. Confidence is low.

### 2.6 R15 and R16: why no entries

- **R15.** NAS 6.1 carries general-government transfers with RoW only as capital, "capital transfers to GG from RoW, net" −6,999.68. It equals the old-format BoP official transfers net −7,000 (EXT-14). The NAS 1.9 net capital inflow (2,08,890.71), which K5 and D3 use, assumes this treatment. Writing R15 as current would count −6,357 to −7,000 twice (rest_of_world item 1). R15 therefore gets no entries, and the transfers go into K6 (§2.9).
- **R16.**
  - Fees and user charges are sales of non-market output: they are already netted in GFCE or recorded as PFCE (households' C_PADM PFCE 1,76,293; C4d fees).
  - The old-base NAS household account (`mospi_nas_2026_oldbase_soa_s5_0`, 2022-23) records no D6/D7 paid; its only use is D5 6,42,596.29.
  - Taxes' C1 books vehicle tax as a product tax (TAX-1, TAX-14).
  - Fines are identifiable only on the Union side and are tiny (`fa8.0070.01.102` 23.39).
  - Result: no R16 entries in 2023-24, logged in `docs/phase2/issues/government.md`. Contingency: if C1 is rejected, write `vehicle_tax` = household share of 1,10,326.52 with the HCES vehicle-item key from `hh_hces_items`, and taxes drops it from T_OPRT.

### 2.7 R18: transfers to corporations

- Only what `taxes` does not treat as a subsidy:
  - revenue grants to PSUs (24,017.45);
  - to co-operatives (1,192.57);
  - the LIC senior-citizen pension subsidy (134.96).
- **Not R18** (taxes' P9a/P10a): MISS 14,251.93, interest equalisation 3,699.99, PM-AASHA 2,200.00, FC16 Union `business` 52,325.27, State transport and business subsidies.
- Statutory bodies' revenue grants (12,356.12 − 1,594.81 = 10,761.31) are not written until they are classified as GG or corporations (§6).
- Publish a `gov_transfer_classification` satellite that mirrors taxes' `tax_classification`.

### 2.8 K3, K3a: saving split

Bridge from cash to the NAS concept, with each step a provenance record:

- **Centre.**

  | Step | ₹ cr | Source |
  |---|---:|---|
  | Revenue balance | −7,65,907.57 | AFS |
  | + net transfers to Public Account funds booked as revenue expenditure (all 2xxx/3xxx minor heads 797, 4,97,014.59, less "met from" deducts −3,21,368.46) | +1,75,646.13 | FA |
  | + grants for creation of capital assets (capital transfers, or capital formation by central autonomous bodies) | +3,03,915.55 | Stmt 6 |
  | − T2b(ii), paid outside the revenue account | −78,104.00 | |
  | **Subtotal** | **−3,64,449.89** | |
  | + CFC (F4b; *indicative* 1,11,071.6) | | factors |

- **States.**

  | Step | ₹ cr | Source |
  |---|---:|---|
  | Revenue balance | −93,436.89 | RBI SF App IV A |
  | − R2k (booked as revenue receipts) | −1,23,957.73 | |
  | + T2b(ii) | +78,104.00 | |
  | + sinking-fund appropriations (internal) | +17,463.85 | `app2…ii.c.1` |
  | **Subtotal** | **−1,21,826.77** | |
  | + CFC (*indicative* 2,64,607.6) | | factors |

  (With ULB capital included in R2k the subtotal would be −1,23,306.01.)

- **Remainder.** Bridge sum + CFC = −1,10,597.50 against NAS −3,18,384.38, leaving **−2,07,786.88 unexplained**. Candidates:
  - sales and fee receipts inside non-tax revenue, which NAS nets in GFCE;
  - spectrum and royalty classification;
  - accruals (T1a, R3b);
  - local bodies;
  - State capital transfers booked as revenue.
  Allocate the remainder by revenue expenditure (AFS 38,54,082.21 vs RBI SF 40,23,677.09) and log it.
- *Indicative*, with the remainder split 0.48924 / 0.51076 by revenue expenditure: G_CEN ≈ −3,64,450 + 1,11,072 − 1,01,658 ≈ −3,55,000; G_STA ≈ −1,21,827 + 2,64,608 − 1,06,129 ≈ +36,700.
- **Sign check.** If |G_STA prior| < 50,000, stop and follow §6 R1.
- The entries are priors only. Their final values are set by balancing under the K3 constraint, and closure reports the pre-balancing imbalance.

### 2.9 K6: capital transfers

- **RoW (fixed shape, as rest_of_world expects):**
  - K_ROW ← K_GCEN 8,557 (`invis…payments`);
  - K_GCEN ← K_ROW 1,558 (`invis…receipts`);
  - resident non-GG from RoW net +1,555.69: K_HH ← K_ROW (assumption, low);
  - NPNFA: K_ROW ← K_NFPR 1,666.26 (assumption, low).
  - Net −7,110.25.
- **Domestic GG → non-GG, total** = COFOG `s4_2.capital_transfer.total.current` 1,76,709.98 less the RoW payments if the check in §6 confirms they are inside it.
- **Recipient by COFOG function:**
  - to K_HH: 06 housing 72,391.15, 10 social protection 6,214.79, 09 education 4,418.65, 07 health 1,247.46, 08 recreation 1,921.99, 04.agri 3,746.05;
  - to K_NFPU: 04.energy 46,364.62, 04.transport 12,940.37, 04.mining/mfg/constr 13,435.28, 04.water 1,101.14, 04.other 1,501.93, 04.admin 48.55;
  - 01 GPS 11,775.98: RoW, rest K_NFPU;
  - 03 38.21; 05 −436.19 (negative; drop and log).
- **Payer:** G_CEN = Union IGAS-2 capital to non-GG grantees (PSUs 16,434.16, NGOs 130.95, co-ops 159.15, statutory 1,594.81, others 20,262.84 = 38,581.91). G_STA = the rest.

---

## 3. Constraints to declare

`tol` = max(tol_abs, tol_rel·|target|). Targets are read in-block through `ctx.value`, never typed.

| constraint_id | ref | rows | cols | refs filter | target (series) | kind | tol_abs / tol_rel | Description |
|---|---|---|---|---|---|---|---|---|
| `gov.c2.<c>` × 6 (CROP, PADM, EDUC, HLTH, CNST, UTIL) | C2a | [C_c] | [G_CEN, G_STA] | [C2a] | Σ SUT `use.gfce.sut_pNNN.current` for c (e.g. PADM 17,82,644.45) | equal | 0.5 / 0 | Same targets as production's C2 constraints; duplicates are fine if identical |
| `gov.c2.total` | C2a | 6 C_c | [G_CEN, G_STA] | [C2a] | `s1_14.gg.final_consumption_expenditure.current` 31,21,027.37 | band | 1.0 / 0 | NAS vs SUT differ by 0.24 |
| `gov.k3.gg_saving` | K3 | [K_GCEN, K_GSTA] | [G_CEN, G_STA] | [K3a] | `s1_9.general_government.current` −3,18,384.38 | equal | 0.5 / 0 | The cells K_GCEN←G_STA and K_GSTA←G_CEN do not exist |
| `gov.grants.state_receipts` | R2 | [G_STA, K_GSTA] | [G_CEN, K_GCEN] | [R2, T2b, R2k] | RBI SF grants 5,27,931.05 **+ T2b(ii) 78,104.00 = 6,06,035.05** (derived target: the constraint cannot filter by component) | band | 0 / 0.005 | State treasury receipts of central grants (FR-gov-2 would remove the +78,104) |
| `gov.r1.devolution` | R1 | [G_STA] | [G_CEN] | [R1] | Σ FA 901 = 11,29,493.71 | equal | 0.5 / 0 | Documents the fixed entries |
| `gov.t2b.cess_uses` | T2b | [G_STA] | [G_CEN] | [T2b] | 44,945.51 + 78,104.00 = 1,23,049.51 | equal | 0.5 / 0 | Documents the fixed entries |
| `gov.r7.union` | R7 | [G_CEN] | [E_NFPU, E_BANK, E_INSP] | [R7] | `fa8.0050.total` − `fa8.0050.00.106` = 83,474.29 | equal | 0.5 / 0 | Union dividends excluding RBI |
| `gov.r9.centre` | R9 | H_g | [G_CEN] | [R9] | 2,24,647.49 (derived from FA) | band | 0 / 0.02 | Cash pensions net of NPS and CGHS |
| `gov.r9.states` | R9 | H_g | [G_STA] | [R9] | 4,46,990.75 (derived) | band | 0 / 0.03 | Wider band: NPS deduction and KFI/RBI SF spread |
| `gov.cofog.current_transfers` | R9 | H_g, E_NFPU, E_INSP (all non-GG rows) | [G_CEN, G_STA] | [R9, R10, R18] | `s4_2.current_transfer.total.current` 10,05,630.22 | band | 0 / 0.05 | Official consolidated GG current transfers. The prior sum is ≈9.30 lakh (−7.5%), so balancing will pull R10/R18 up. Declare only after the PM-KISAN classification is settled with taxes (§5 C10) |
| `gov.cofog.capital_transfers` | K6 | [K_HH, K_NFPU, K_NFPR, K_ROW] | [K_GCEN, K_GSTA] | [K6] | `s4_2.capital_transfer.total.current` 1,76,709.98 | band | 0 / 0.05 | Official GG capital transfers paid |
| `gov.k6.row_gg_net` | K6 | [K_GCEN, K_ROW] | [K_ROW, K_GCEN] | [K6] | Not expressible as a plain Σ (net of two directions). Make it a **block test** instead: receipts − payments = `s6_1.capital_transfers_to_general_government_from_the_rest_of_the.current` −6,999.68 ± 1 | test | — | — |

Not declared, as tests only:

- GG GDI 28,02,642.99 (`s1_14.gg.gross_disposable_income.current`). It is implied by C2 + K3 once the accounts balance.
- R2k and R9b bands, which have no official target.

---

## 4. Interfaces

### 4.1 Needs

| From | What | Why |
|---|---|---|
| production | C2 per-commodity targets (constraints or entries), and the P9 entry on C_RPET | C2a row totals; R10 `lpg_dbt` |
| factors | `gg_centre_state_key` (Centre share 0.295655 and its inputs); F4b entries (CFC by government); `factor_income_keys` (F_LREG share by group) or the F1a entries | C2a column target (same key as F4b); K3a bridge; R9a/R9b key |
| households | `hh_keys` (`pop_persons` by group); `hh_state_xwalk`; `s8_food_stik` (cross-check); `hh_hces_items` only if R16 `vehicle_tax` is activated | R10 keys; C2a check |
| framework | (1) confirm that `ctx` exposes other blocks' constraints (for C2 targets); (2) FR-gov-1…5 (§6) | |

### 4.2 Publishes

- **Entries:** all refs above.
  - **fincorp:** R6 (E_RBI pays 87,416.22 cash) and R7 (E_BANK 14,295.56, E_INSP 4,272.54 paid to government), for the FC current accounts.
  - **capital_financial:** R2k, K6, K8e and K3a, for the K_* accounts.
  - **rest_of_world:** K6 RoW entries (net −7,110.25), and the absence of R15.
  - **closure:** everything (H-touching refs R9a, R9b, R10 at group level; no R16).
- **Satellites** (each with a ref; FR-gov-4):
  - `gov_grants_bridge` (ref R2): the H9 decomposition above;
  - `gov_fiscal_bridge` (ref K3a): the saving bridge, remainder and allocation;
  - `gov_c2a_keys` (ref C2a): seed, targets and RAS result;
  - `gov_transfer_classification` (ref R18): every St 7 / FC16 subsidy-or-transfer line → P9a, P10a, C2a, R10, R18 or K6. It mirrors taxes' `tax_classification`, so the verifier can check that nothing lands twice;
  - `gov_r9b_sensitivity` (ref R9b).

### 4.3 Coordination with blocks that are not dependencies (they read government, or run in parallel)

- **taxes:**
  - T1a routes 100% of Union taxes, gross of devolution, to G_CEN. R1 is the only route of the States' share; if taxes wrote net-of-901 amounts, R1 would double count.
  - Vehicle tax → T_OPRT (so no R16).
  - MISS, PM-KISAN, interest equalisation, PM-AASHA and FC16 Union "business" stay in P9a/P10a (not R10/R18).
  - State food subsidies are not GFCE.
  - Government's R9 excludes NPS employer contributions. taxes does not touch these.
- **capital_financial:**
  - The FSF Centre→States loan flow `fsf.gg_cen.assets.transaction.f4.gg_sta.current` 41,791.65 equals the Union's net lending (1,40,863.34 − 92,856.68 − 6,215.00 = 41,791.66). The Union's recoveries exceed the States' own repayments (`app4…iii` 27,483.21) by 71,588.47, which is consistent with the cess-financed recovery sitting inside the Union's figure.
  - So capital_financial **must write the Centre–State I_LOAN flow net of K8e** (41,791.65 + 78,104.00 = 1,19,895.65), or government drops K8e. Test: the sum = FSF.
  - Also: K3a feeds K9 residuals, and GFCF by level must follow the treasury view (outside-treasury CSS assets = G_CEN).
- **fincorp:** R3 (interest paid by governments, including the intra-GG 13,641.26 / 15,072.31, GOV-7) and R9c (GPF interest) are fincorp's. R7's 101 line puts financial PSUs' dividends on E_NFPU (§6).
- **rest_of_world:** agrees that R15 = 0 and K6 is on the NAS basis. R14 carries the Union's external interest (29,616.74).
- **closure:** use R9 net of NPS and CGHS (6,71,638.24), not the gross 7,29,311.48 in its sketch. R9b recommended at 1,86,545.42, not 4.5–6.8 lakh.

---

## 5. Conflicts and choices

| # | Item | Source A | Source B | Recommendation (control / cross-check) |
|---|---|---|---|---|
| C1 | Grants to States (H9) | Union MH 3601 + 3602 net releases 5,28,103.46; St 18 grants 7,39,260 (States only, excl. loans); IGAS-2 State + UT 4,56,388.26 | RBI SF 5,27,931.05 (all States + UTs); KFI 4,72,465.88 (28 States) | **Control: RBI SF** (G_STA coverage). Cross-check: Union net releases (+172, 0.03%) and KFI via the GOV-8 UT bridge. St 18 is broader (outside-treasury CSS), and not a G_STA receipt under the treasury view |
| C2 | Devolution | Union FA 11,29,493.71 (= RB, = AFS) | RBI SF 11,29,761.46; KFI 11,29,396.72 | **Control: Union FA** (audited, by tax); State figures as cross-checks (≤0.02%, GOV-1/2) |
| C3 | GST compensation grants | Union 44,945.51 (= KFI for 28 States) | RBI SF 45,464.24 | **Control: Union**; the +518.72 difference stays in R2 `css_and_other` |
| C4 | State pensions | RBI SF 4,90,983.18 (States + UTs) | KFI 4,94,938.72 (28 States); FC16 State accounts MH 2071 4,79,248.1 (28 States) | **Control: RBI SF** (coverage = G_STA), less the NPS employer contribution 43,992.43. KFI (gap-map primary) as cross-check; its extra 15,690 over MH 2071 is not explained |
| C5 | R9b size | Gap-map formula: Centre 1,86,545.42 + States 2,40,687.33 (uniform k) = 4,27,232.75 | NAS 4.1 State CE 11,78,216.69 − KFI salaries 10,86,648.64 − UT NVA 60,011.37 − State NPS employer 43,992.43 = **−12,435.75**: no room for any State imputed pension in NAS CE. The GG GDI sketch also overshoots NAS by lakhs with the full formula | **Centre per formula, States 0 in the prior**, sensitivity logged. **Orchestrator decision + NAD question.** This departs from the gap map as written |
| C6 | GG transfers with RoW | BoP BPM6 1.C.2 current 1,463 / 7,820 (net −6,357) | NAS 6.1 capital −6,999.68 = old-format BoP 1,558 / 8,557 (EXT-14) | **NAS** (K5, D3 and K3 use it): no R15; K6 on the old-format gross values |
| C7 | Class of T2b(ii) | Gap map: current (default) | SNA 2008 §10.201: debt assumption/cancellation is a capital transfer | Keep **current** for the prior build (no framework churn). Flag for Checkpoint B: moving it to capital changes only the K3a split (±78,104) |
| C8 | RBI surplus | Cash 87,416.22 (D0-7) | Accrued 2,10,873.99. Super-dividend test: RBI 2022-23 net income 87,420.22 includes FX gains of 1,03,308.35 (`sch14.b.exchange_gain_loss…`, 2022-23) | **Cash, as NAS income.** Applying SNA §7.131 would move the whole 87,416 into I_EQTY and break K3. Report as a finding and NAD question |
| C9 | GG saving | NAS 2026 −3,18,384.38 | HBS T11 −3,20,171 (GOV-13, vintage) | **NAS 2026** |
| C10 | PM-KISAN class | Gap-map default D39 (taxes P10a: `fa9.2401.00.130` 51,616.91) | NAS 4.2 COFOG 04.agri current transfers 58,325.32 is of a size that could be it | **Keep D39** (factors, taxes and the gap map agree), but test the COFOG current-transfers band before imposing it. If NAS turns out to treat it as D7, it moves to R10 |
| C11 | Motor-vehicle tax | Gap-map R16 (household D59) | Taxes C1: product tax (TAX-1, TAX-14, derived D29 has no room) | **Taxes C1**; R16 has no entries |
| C12 | Food subsidy scale | St 7 2,11,814.39 | FC16 Centre 2,30,755.71; FA `fa9.2408.01.102` 1,84,468.93; SUT GFCE grain 1,63,971.75 | **SUT GFCE** is the cell (fixed); the others are cross-checks only (TAX-11) |
| C12b | Outside-treasury CSS | Treasury view (recommended) | Institutional view (State societies are State autonomous bodies, so their receipts are G_STA) | **Treasury view**: it is consistent with each government's own books. GG totals are unaffected. The Centre share of GFCE/GFCF is higher than the institutional view would give; log it |

---

## 6. Risks, gaps, open questions

**Framework requests (FR-gov-n)**

1. **R1 (blocking design): sign lock on K3a.**
   - The State saving prior is near zero (≈ +36.7k, on a bridge with a 2.08 lakh remainder), so balancing (z ≥ 0) cannot flip it.
   - Options: (a) represent K3a per government as two components, `saving_pos` and `saving_neg`, so the net can cross zero; (b) exclude K3a from z-scaling and let the framework solve it as a signed residual; (c) accept the sign and report slack.
   - Recommend (b) or (a); decision for the framework agent.
2. **Component filter in constraints.** The R2 receipts constraint currently needs the +78,104 target workaround.
3. **Ownership gap A: GG property income other than dividends.** No ref owns:
   - government **interest receipts** from non-GG units: Union `fa8.0049.03.total` 65,032.85, of which PSUs 7,686.33, DCUs 1,600.47, SDR interest 5,411.10 (RoW → R13), cash-balance investment 9,643.04 (intra-G_CEN), and premium/accrued interest on market loans 12,312.11 + 26,465.89 (R3b offsets); States `app1…ii.c.1-interest_receipts` 28,493.58;
   - **rent / royalties (D45):** States' mining royalties, FC16 State-accounts MH 0853 1,26,178.5 (28 States; RBI SF "industries" 1,27,121.53); Union petroleum `fa8.0802.total` 17,352.43; telecom licence/spectrum `fa8.1275.total` 90,659.26, whose class (rent vs NPNFA disposal) is a NAD question.

   The SUT's mining production taxes are only ≈2,566, so royalties are not in P10. Proposal: a new ref "R7x: other property income received by GG" owned by government (NFC/FC/HH payers keyed from ingested data), or assign interest to fincorp. Without it, GG income is short by up to ≈2.5–3.5 lakh and balancing will force it elsewhere.
4. **Satellites for government** (`gov_*`, §4.2). Confirm the ref convention.
5. **Ownership gap B: pensions paid by departmental enterprises (E_NFPU).**
   - Railways: pensions come out of the Railway Pension Fund; the AFS shows only "Railway Funds" disbursements 59,801.66.
   - Posts: `fa9.3201.07.total` 11,674.49, including NPS 986.20.
   - No ref covers HH ← E_NFPU pensions.

**Data gaps and weak spots**

- **No microdata (D1-2).** R9a, R9b and R10 group keys are proxies (low confidence).
- **R10 coverage.** FC16 subsidies cover 20–21 States. The Centre's `social_security` may overlap NSAP grants.
- **K3a.** About 2.08 lakh cr of the saving bridge is unexplained. Local bodies are partial: the ULB dump covers 4,620 ULBs for 2023-24, and PRIs only run to 2022-23.
- **K6.**
  - Whether COFOG 01 capital transfers (11,775.98) include the RoW grants (Stmt 20 grants 7,455.62; BoP payments 8,557) is unverified.
  - The recipient split of 04.* COFOG capital transfers is assumed.
  - States' capital transfers are a residual.
  - The class of statutory bodies and development authorities (IGAS-2 12,356.12, capital 1,594.81), GG vs corporations, is unknown.
- **K8e / FSF.** The inference that FSF already contains the −78,104 rests on the Union-vs-State recovery gap (71,588.47, residual −6,515.53). It needs a test and, ideally, a NAD/CGA confirmation.
- **R7 payer mapping.** Head 101 "Public Undertakings" (63,827.41) includes financial PSUs (NBFC/insurer dividends), but all of it goes to E_NFPU. fincorp may supply a public-FC dividend key later.
- **Vintage and period traps:**
  - `rbi_banking_corporate_rbi_accounts` has 3 vintages per period;
  - PLFS t35 uses period `2023-07/2024-06`;
  - HCES uses `2023-08/2024-07`;
  - the FSF "stock" series use period `2024-03-31`.
- **Double-counting risks** (each gets a test in §7):
  1. RBI surplus in both R6 and R7.
  2. Devolution in both T1a (net) and R1.
  3. GST compensation grants in both R2 and T2b.
  4. R2k inside R2 current.
  5. R15 current plus K6 RoW.
  6. Vehicle tax in both R16 and T_OPRT.
  7. PM-KISAN / MISS in both R10/R18 and P9a/P10a.
  8. Free grain in both C2a and PFCE or R10.
  9. NPS employer contributions in both CE and R9.
  10. CGHS pensioners' medical costs in both GFCE and R9.
  11. K8e inside the FSF Centre–State loans.
  12. Fees in both R16 and PFCE/GFCE.
  13. Transfers into reserve funds counted as grants (MH 3601 797 lines).
  14. Interest on back-to-back loans (GOV-7 −1,431), fincorp's.

**Questions for MoSPI NAD** (add to P0-10)

- R9b: which OPS pension share is inside NAS CE for States and for defence?
- The class of T2b(ii).
- Mining royalties and spectrum.
- The RBI super-dividend.
- Whether GG GDI includes D612.
- Direct Union grants to ULBs.

---

## 7. Tests the builder should write

All targets are read from clean data or from other blocks' outputs inside the test, never typed. File: `tests/sam/test_block_government.py`.

1. **C2 reproduction.** For each of the 6 commodities, Σ C2a = SUT GFCE for the commodity (±0.5). Σ all = `io_tables_sut_use` `use.gfce.total.current` 31,21,027.14 (±1) and NAS `s1_14.gg.final_consumption_expenditure.current` (±1). C_CROP ← G_CEN = `use.gfce.sut_p001` + `sut_p002`, and there is no C_CROP ← G_STA.
2. **C2a key.** The implied G_CEN share of own-output GFCE equals the `gg_centre_state_key` Centre share × own-output total (±1).
3. **R1.** Σ R1 entries = −Σ `union_fiscal_fa_receipts` `fa8.*.00.901` (2023-24) = 11,29,493.71 (±0.01). Also within 0.05% of `app1…i.b-share_in_central_taxes…` and `kfi.a_1_3…`.
4. **H9 bridge.** For MH 3601 and 3602, releases + recoveries + 797 + "met from" = `fa9.<mh>.total` (±0.01). Net releases (3601 + 3602) are within 0.1% of RBI SF `app1…ii.d-grants_from_the_centre…`. IGAS-2 State (cash + kind) + FC local-body and health grants is within 0.1% of MH 3601 net releases.
5. **R2 + T2b(i) + R2k** = RBI SF grants (±0.5%). R2k = IGAS-2 State + UT capital (exact). R2 `fc_grants` = `app1…ii.d.5…` (exact).
6. **T2b.** `cess_loan_recovery` = `afs.pa_disbursements.xi_…` + `fa9.3601.08.904` + `fa9.3602.08.904` = 78,104.00 (±0.01). `compensation_grants` = `fa9.3601.08.112` + `fa9.3602.08.106`. Σ T2b ≤ `afs.pa_receipts.xi_…` (1,43,109.49).
7. **R6** = `fa8.0050.00.106` = `r6.surplus_received_by_centre_cash.current` (2023-24) (±0.01). No R7 entry with E_RBI in the column.
8. **R7.** Union Σ = `fa8.0050.total` − `fa8.0050.00.106` (±0.01). States = `app1…ii.c.2-dividends_and_profits…`.
9. **R9.** Σ H ← G_CEN within 2% of (`fa9.2071.total` − NPS − CGHS). Σ H ← G_STA within 3% of (RBI SF pensions − PFRDA SG employer). The prior group entries sum exactly.
10. **R9b.** G_CEN total prior = civil base × 21/39 + `fa9.2071.02.total` (±1). No G_STA R9b entries in the primary run. R9b ≤ R9 for each government.
11. **K3.** K_GCEN ← G_CEN + K_GSTA ← G_STA = `s1_9.general_government.current` (±0.5) after balancing. The prior signs match the bridge signs, and the `gov_fiscal_bridge` rows sum to the priors.
12. **K6 RoW.** K_GCEN ← K_ROW − K_ROW ← K_GCEN = `s6_1.capital_transfers_to_general_government_from_the_rest_of_the.current` (±1). The net of all K6 RoW entries = −7,110.25 (±1), i.e. the sum of the three `s6_1` items. Domestic GG K6 paid is within 5% of `s4_2.capital_transfer.total.current`.
13. **K8e.** Both entries = −T2b(ii). Integration test (with capital_financial): Σ Centre→State I_LOAN flows, all refs = `fsf.gg_cen.assets.transaction.f4.gg_sta.current` 41,791.65 (±1).
14. **GG GDI (post-balancing).** Σ government resources outside GG less current transfers and property income paid outside GG = `s1_14.gg.gross_disposable_income.current` 28,02,642.99 (±1). Also report the pre-balancing value with and without R9b (closure's R3).
15. **COFOG current transfers.** Σ (R9 + R10 + R18) is within 5% of `s4_2.current_transfer.total.current` 10,05,630.22 (report pre-balancing; enforce post-balancing only if the constraint is declared).
16. **Exclusion tests** (double counting):
    - no R15 entries;
    - no R16 entries unless `vehicle_tax` is activated (and then taxes' T_OPRT excludes it);
    - no R10/R18 component named after MISS, PM-KISAN or food;
    - `gov_transfer_classification` assigns every line exactly once;
    - no G_STA ← G_CEN entry under ref R2 contains the MH 3601 797 lines.
17. **Structure and provenance.** Every entry's (row group, col group) is in `structure.yaml`; its ref is in the owned list; its `prov_id` resolves; every `estimated` record has a method; each prov's inputs trace to the clean prov_ids of the series named above.

---

## 8 Cross-plan review (2026-09-30, cross-plan critic; details and ids in `CROSS_REVIEW.md`)

What this block must change or confirm:

1. **XR-1 (critical) new ref for GG property income other than dividends.** Recommended `R7x` (orchestrator edits the gap map and `accounts.OWNERSHIP`), owned here. It covers:
   - interest receipts from non-GG units: Union `fa8.0049.total` 78,674.11 less intra-GG and the R13 SDR part; States 28,493.58;
   - D45 rent: States' mining royalties 1,26,178.5; Union petroleum royalty 17,352.43; spectrum 90,659.26, whose class is a NAD question.

   Payers: NFCs keyed by mining GOS (public/private from 7.1A/7.1B); PSU loan interest to E_NFPU. Without it, E_NFPU/E_NFPR and G_* are mis-stated by ₹2.5–3.5 lakh cr.
2. **XR-2 departmental-enterprise pensions (HH ← E_NFPU):** Railways (AFS "Railway Funds" 59,801.66) and Posts (`fa9.3201.07.total` 11,674.49). Recommended: extend R9a to payer E_NFPU, or add a new ref `R9d`, owned here.
3. **XR-11 ref discipline:** write the pension group entries under **R9a** (R9 is constraint-only). Use refs `[R9a]` in `gov.r9.centre/states` and `[R9a, R10, R18]` in `gov.cofog.current_transfers`. closure's whitelist lists R9a.
4. **XR-7 Centre/State boundary.** C2a's column target uses factors' institutional NAS 4.1 key, while R2/K3a use the treasury view. G_STA then consumes CSS-society and ULB spending that it never receives. Recommended (decision D-5): the institutional view. Add R2 components:
   - `css_outside_treasury` (St 18 CSS − MH 3601.06 net = 1,86,499.95, split current/capital with the IGAS-2 capital share);
   - `ulb_direct`, the Union grants to ULBs not routed through State treasuries. `ulb.grants_for_centre_s_initiatives` 54,108.73 is an upper bound.

   This also eases the G_STA saving sign risk. Keep the treasury view as a sensitivity.
5. **XR-17 K3a sign:** write each government's saving as two entries, `saving_pos` (+) and `saving_neg` (−) (FRAMEWORK_REQUESTS P-9), so the net can cross zero.
6. **XR-20:** replace the +78,104 workaround in `gov.grants.state_receipts` with a components filter that excludes `cess_loan_recovery`; target RBI SF 5,27,931.05.
7. **XR-14 K6 RoW:** make the GG entries net to NAS `s6_1.capital_transfers_to_general_government_from_the_rest_of_the.current` −6,999.684747 (checked), e.g. payments 8,557 and receipts 8,557 − 6,999.68 = 1,557.32, or scale both. BoP gross 8,557 / 1,558 nets to −6,999 and leaves K_ROW ₹0.68 cr out. NAS publishes NPNFA as +1,666.26 (India acquires, so K_ROW ← K_NFPR +1,666.26); keep it positive in the cell.
8. **XR-3 capital transfers to K_HH (decision D-3):** recommended to write them (COFOG housing etc. ≈ 89,940 + RoW 1,555.69) and let capital_financial's K9_HH show the NAS inconsistency. If the orchestrator chooses memo only instead, restrict `gov.cofog.capital_transfers` to non-household recipients.
9. **XR-8 R9b:** decide the size (decision D-2) only after R7x exists. Run T14 (GG GDI with and without R9b) with R7x included. The cross-plan sketch in CROSS_REVIEW §6 shows the answer moves by ±3 lakh cr with R7x.
10. **XR-18 DAG:** DEPENDS += taxes (read `tax_classification`, P9a/P10a).
11. **XR-19 component names:** C_CROP ← G_CEN component `food_subsidy`; T2b `compensation_grants`, `cess_loan_recovery` (already so). Freeze them (timeseries F24, F29).
12. **XR-23:** State food subsidies (54,463.39) are recorded once, in taxes' P9a on C_TRAD with a G_STA assignment. Keep them out of C2a and R10 (as planned).
13. **Confirmed:**
    - fincorp writes all government interest (R3/R3a/R8a/R9c); rest_of_world writes R_ROW ← G_* under R14. Write no interest entries here.
    - The debt-management fee (2,921.79) is a purchase (inside SUT GFCE), not D41.
    - T2b(ii) = 78,104 is derived from clean data, which answers capital_financial's Q7. capital_financial writes FSF − K8e = 1,19,895.65.
