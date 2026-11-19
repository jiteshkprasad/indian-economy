# Phase 2 plan: `timeseries` (the top ~50 flows across years; DESIGN_BRIEF §8)

Written 2026-09-30 by the timeseries data scout / method planner. Research only: no code under `pipeline/`, no `pipeline build/sam/repro` runs. Every number below was read from `data/clean/**.parquet` with polars in a scratch folder outside the repo, and every series id was checked to exist. Amounts are ₹ crore, current prices, fiscal years (FY), in the SAM's sign convention (subsidies negative) unless stated. Indian digit grouping (1,64,15,547) is used as in the other Phase 0–2 documents.

Inputs read: `docs/phase2/DESIGN_BRIEF.md` (§2, §3, §6, §8); `docs/phase0/ACCOUNT_STRUCTURE.md` (§5, §7, §9, §11); `docs/phase0/GAP_MAP.md` and `data/gap_map.csv` (all refs whose cells the flows sum over); `docs/phase0/REFERENCE_YEAR.md` §4–5; `docs/phase0/STACK_AND_REPO.md` §4.3; `DECISIONS.md`; `ISSUES.md` (P0-6, P1-2, P1-6); `docs/phase1/COVERAGE.md`; `docs/phase1/RECONCILIATION.md` (GDP, GOV, TAX, EXT, HH, FIN tables); `docs/phase1/issues/mospi_nas_2026.md` (issues 7, 9, 14, 31, 33, 34, 37) and `state_fiscal.md` (state_fiscal-7); the framework as it stood at 19:13 on 30 Sep (`pipeline/sam/spec.py`, `framework.py`, `accounts.yaml`, `structure.yaml`).

---

## 1. Summary (plain English)

- **What the block is.** Not a SAM block: it writes no SAM entries and declares no balancing constraints. It builds a long table of **54 core flows** (plus 15 memo aggregates and 11 optional flows) for every year the clean data allow. Each flow is defined twice: as a sum of SAM cells for 2023-24 (so the Map's time slider and the balanced SAM tell the same story in the reference year) and as a year-by-year series from clean data.
- **How far back it goes.** Only the national-accounts expenditure aggregates, net primary income, the current-account balance, devolution and grants reach back to **1950-51/1952-53**. Household financial saving detail starts in **1983-84** (RBI HBS Table 12). BoP detail starts in 2004-05 (FDI) and 2006-07 (remittances, investment income); the full BoP only in 2020-21. Sector saving and investment, compensation of employees, profits, state taxes and state spending start in **2011-12**. The Union budget is in the clean data only for **2022-23 to 2024-25**. All 54 core flows exist together only for **2022-23 and 2023-24**.
- **The base break stays visible.** The old (2011-12) and new (2022-23) bases overlap in 2022-23 and 2023-24, and both are kept, labelled by `base_year`. The jump is large and uneven: GDP −2.7%, PFCE −9.6%, CFC +14.5%, private-corporate saving −23%. Some series also change definition at the break: imports of services are now net of a CIF adjustment, and food subsidy moved out of product subsidies into government consumption. So there is **no default splice**. An optional `linked_2022_23` variant (ratio-linked, status `derived`) is built only for 10 series whose new/old ratio is stable in both overlap years.
- **The 2023-24 check.** For ~35 national-accounts, BoP and saving flows, the 2023-24 value must equal the SAM definition exactly (≤ ₹5 cr). For fiscal cash series (GST, excise, grants, interest, subsidies), the SAM holds accrual, SUT-fitted numbers. There the difference must match a pre-registered bridge, or the test fails.
- **New findings** (details in §6.3):
  - The FC16 "time series of transfers" switches from States' receipts to Union-side figures in its last year, 2023-24 (grants 7,39,260 vs States' 5,27,931).
  - RBI HBS Table 12 equals the NAS 2025 old-base household financial saving to ₹0.5 cr in every year from 2011-12, so the household series joins at 1983-84 without a splice.
  - Old-base imports of services are not CIF-adjusted.
  - The old-base NAS split of income taxes by sector cannot stand in for corporation tax or personal income tax history.
  - The framework's provenance call needs a gap-map ref, and its `vintage='latest'` rule works per series, not per period. Both need a framework change before this block can be written.

---

## 2. Ref-by-ref table (here flow-by-flow: the block owns no gap-map refs)

### 2.0 Conventions for the builder

- **Entries to write: none in the SAM.** The block writes rows of `data/timeseries/top_flows.parquet`: one row per (flow, FY, base_year, variant). The key is unique: segments of one flow never overlap within the same `base_year` and `variant` (precedence rules below).
- **SAM definition notation.** `ROWS ← COLS [refs] {components} <bop_function tags>`. Rows receive, columns pay. A flow's 2023-24 SAM value is Σ `value` of balanced entries matching every filter, times the term's coefficient. Refs are always listed explicitly. §7 T4 guards against a new ref silently entering or leaving a cell block. Account groups follow `accounts.yaml`:
  - `C_goods` = the 19 commodities whose SUT products are 1–126: C_CROP, C_LVST, C_FOFI, C_COAL, C_OILG, C_OMIN, C_FOOD, C_BVTB, C_TXAP, C_WOOD, C_GJOM, C_RPET, C_CHEM, C_PHRM, C_NMMN, C_MTLS, C_MACH, C_ELEQ, C_TREQ;
  - `C_services` = the other 15 commodities (products 127–155), from C_CNST to C_PADM.

  I checked the split: SUT exports and imports on products 1–126 and 127–155 equal NAS 1.1 goods and services exactly in both 2022-23 and 2023-24 (exports 36,67,092 / 28,12,204; imports 56,84,221 / 12,62,685).
- **Status of time-series rows.**
  - `official`: a published value, or a pure sum of published components of one table.
  - `derived`: differences, sign flips of "Less" items, lags, the back-series current-account derivation, and the linked variant.
  - `estimated`: nothing is estimated in this plan.

  Each row keeps the source's `estimate_stage` and `vintage` (for sums: the least mature stage and the latest vintage among the inputs, with all inputs in the provenance record).
- **`base_year` column.**
  - `2011-12`: old-base NAS rows. RBI HBS T12 equals old-base NAS 5.3 only from 2011-12 (§6.3 F2); **amended (§9 A1):** T12 rows before 2011-12 splice earlier bases, so they carry `base_year` null (as their clean records do) and 2011-12 is flagged `base_change`.
  - `2022-23`: new-base NAS rows.
  - null: BoP, fiscal and FSF rows, which are not tied to a GDP base. Their concept notes say which NAS vintage they are consistent with.
- **Periods.** FY `YYYY-YY` only. Actuals, audited figures and NAS estimates only (Final/TRE/SRE/FRE/PE). **Budget RE/BE rows are never used**, and neither are the old-base API's 2024-25 PE/SAE and 2025-26 FAE (a discontinued base). The last period is 2025-26, the latest complete FY. RBI's cash surplus for FY 2026-27 is dropped (FY not closed).
- **Precedence inside a base.**
  - For 2011-12, NAS 2025 old-base statements beat the API back series. The back series' 2011-12 differs by ≤ ₹3 cr, e.g. GDP 87,36,331 vs 87,36,329 (mospi_nas_2026-33). Imports and exports are equal.
  - For old-base items that NAS 2025 did not publish as statements (GFCF by sector), use the API annual series with the latest-round rule of mospi_nas_2026-34: Final > TRE > SRE > FRE > PE > SAE > FAE, and 'Revised' for 2011-12..2013-14. Issue 9 confirms that each NAS 2025 1.1 level equals exactly one API round, the latest.
  - For BoP instruments, the BoP (RBI BoP annual, old-format table) beats older partial series from 2020-21.
- **Sign.** The SAM sign throughout: subsidies negative; NAS "Less" items (`subsidies_on_products`, `imports`, `financial_liabilities`) are stored positive in clean data and multiplied by −1 only where the SAM sign is negative (product subsidies). The definitions table carries a `display_sign` so the UI can show "subsidy paid" as positive.

### 2.1 Source segments (codes used in the tables)

| Code | Dataset / series pattern | Years | base_year | Vintage · stage |
|---|---|---|---|---|
| **NB** | `mospi_nas_2026_api_b2011_back` · `api.<item>.current` | 1950-51..2010-11 (valuables from 1999-00) | 2011-12 | API snapshot 2026-09-29 · `n.a.` |
| **NO** | `mospi_nas_2026_oldbase_nas2025_s1_1` / `_s1_9` / `_s1_14` / `_s5_3` · `oldbase_nas2025_<st>.<item>.current` | 2011-12..2023-24 | 2011-12 | 2025-06-26 · Revised (to 2013-14), TRE (2014-15..2020-21), SRE (2021-22), Final (2022-23), FRE (2023-24) |
| **NA** | `mospi_nas_2026_api_b2011_annual` · `api.<item>.rev_<round>.current`, latest round per year | 2011-12..2023-24 | 2011-12 | 2026-09-29 snapshot · as the round |
| **NS** | `mospi_nas_2026_oldbase_soa_s1_15` / `_s4_0` · `oldbase_soa_<st>.<account>.<side>.<code>.current` | 2011-12..2022-23 | 2011-12 | **2024-06-05 (NAS 2024, a different vintage from NO)** · 2022-23 FRE |
| **NN** | `mospi_nas_2026_s1_1`, `_s1_9`, `_s1_11`, `_s1_14`, `_s5_3`, `_s6_1`, `_s7_1`, `_derived_residuals` | 2022-23..2024-25 | 2022-23 | 2026-08-31 · Final (2022-23, 2023-24), FRE (2024-25) |
| **NP** | `mospi_nas_2026_api_b2022_annual` · `api.<item>.rev_provisional_estimates.current` | 2025-26 | 2022-23 | 2026-09-29 · PE |
| **T12** | `rbi_financial_accounts_hbs_saving` · `t12.assets.*` / `t12.liabilities.*` | 1983-84..2010-11 (used); equal to NO 5.3 in 2011-12..2023-24 | 2011-12 | 2026-07-31 · `n.a.` |
| **BI** | `external_sector_invisibles_annual` · `invis.inr.<item>.<side>.current` | 2006-07..2025-26 | null | 2026-07-31 · Preliminary (latest) |
| **BO** | `external_sector_bop_overall_annual` · `bop_old.inr.<item>.<side>.current` | 2020-21..2025-26 | null | 2026-07-31 |
| **B6** | `external_sector_bop_bpm6_annual` · `bpm6.inr.<code>.<side>.current` | 2022-23..2025-26 (cross-check only) | null | 2026-07-31 |
| **FI** | `external_sector_foreign_investment` · `t143.inr.<item>.current` | 2004-05..2025-26 | null | 2026-07-31 |
| **NR** | `external_sector_nri_deposits` · `nri.flow.inr.total.current` | 2007-08..2025-26 (used to 2019-20) | null | 2026-07-31 |
| **FT** | `state_fiscal_fc16_transfers` · `tsm.<item>.actuals` | 1952-53..2006-07 (used); see §6.3 F1 | null | 2026-02-03 · Actuals |
| **AT** | `state_fiscal_rbi_sf_app_tables` · `at2.<item>.actuals` | 2007-08..2023-24 | null | 2026-01-23 · Actuals |
| **KF** | `state_fiscal_fc16_kfi` · `kfi.<code>.in.all_states_28` (28 States) | 2011-12..2023-24 | null | 2026-02-03 · Audited |
| **SA** | `state_fiscal_rbi_sf_appendices` · `app*.…in.all_states_uts.actuals`; `state_fiscal_rbi_sf_statements` · `st13…all_states_uts.actuals` (all States and UTs) | 2023-24 (cross-check) | null | 2026-01-23 · Actuals |
| **RB** | `union_fiscal_rb_receipts` · `rb.tr.*` | 2022-23..2024-25 (one Receipt Budget per year: vintages 2024-07-23, 2025-02-01, 2026-02-01) | null | Actuals |
| **AF / FA** | `union_fiscal_afs` · `afs.*` (2022-23..2023-24); `union_fiscal_fa_expenditure` / `_fa_receipts` · `fa9.*` / `fa8.*` (2023-24) | as stated | null | Actuals / Audited |
| **EP** | `union_fiscal_exp_profile` · `stat7.*` | 2022-23..2024-25 | null | Actuals |
| **FS** | `state_fiscal_fc16_subsidies` · `sub.<item>.in.gg_centre` | 2018-19..2023-24 actuals | null | Actuals |
| **RS** | `rbi_banking_corporate_rbi_surplus_timing` · `r6.surplus_received_by_centre_cash.current` | 2022-23..2025-26 | null | Audited |
| **FF** | `rbi_financial_accounts_fsf_instrument_sector` · `fsf7.<sector>.<side>.transaction.<instr>.current` | 2012-13..2023-24 | null (consistent with old-base NAS, H4) | FSF 2023-24 |

### 2.2 Core flows (54)

Columns: **SAM definition** (owner block of the entries · role of those entries) | **Segments and years** | **2023-24: time-series value; expected SAM value** | **Method / notes** | **Status · check class** (classes defined in §7 T3).

#### A. Expenditure and trade

| ID | Flow | SAM definition 2023-24 | Segments → years | 2023-24 values | Method / notes | Status · class |
|---|---|---|---|---|---|---|
| F01 | Private final consumption (PFCE) | `C_* ← H_R1..H_U5` [C1a, C4a, C4b, C4c, C4d] · households · free entries held by production's C1 `equal` constraints | NB `api.pfce.current` 1950-51..2010-11 · NO `…s1_1.pfce` 2011-12..2023-24 · NN `s1_1.pfce.current` 2022-23..2024-25 · NP `api.pfce.rev_provisional_estimates.current` 2025-26 | TS **1,64,15,546.52** (NN, Final); SAM = `io_tables_sut_use` `use.pfce.total.current` 1,64,15,547; old base 2023-24 1,81,30,431 (FRE) | As published. Linked variant allowed (ratios 0.9039 / 0.9054) | official · A |
| F02 | Government final consumption (GFCE) | `C_* ← G_CEN, G_STA` [C2a] · government · held by C2 constraints | NB `api.gfce.current` · NO `gfce` · NN `s1_1.gfce.current` · NP 2025-26 | **31,21,027.37**; SAM `use.gfce.total.current` 31,21,027 | **Concept break:** new base includes free PDS grain (food subsidy as social transfer in kind) and FCI as non-market. No link (ratios 1.0640 / 1.0054 are unstable) | official · A |
| F03 | Gross fixed capital formation | `C_* ← K_*` [I1, I1a] · capital_financial · held by I1 constraints. Excludes valuables (I2, I2a) | NB `api.gfcf.current` · NO `gfcf` · NN `s1_1.gfcf.current` · NP `api.gfcf.rev_provisional_estimates.current` | **92,45,762.46**; SAM `use.gfcf.total.current` 92,45,762 | Link allowed (1.0068 / 1.0088) | official · A |
| F04 | Valuables (gold, silver ornaments) | `C_GJOM ← K_HH` [I2, I2a] · capital_financial. Not the D3 financing cell `K_HH ← X_DISC` | NB `api.valuables.current` **1999-00**..2010-11 · NO `valuables` · NN `s1_1.valuables.current` · NP 2025-26 | **3,76,231.72**; SAM `use.valuables.total.current` 3,76,232 = NAS 1.9 household 1,72,126.57 (I2) + unsectored 2,04,105 (I2a) | No link (1.0470 / 0.8854 unstable) | official · A |
| F05 | Exports of goods | `C_goods ← R_ROW` [P5] · production · fixed | NO `exports_goods` · NN `s1_1.exports_goods.current` | **36,67,091.58**; SAM Σ SUT exports on products 1–126 = 36,67,092 | Old base starts 2011-12 (the back series has no goods/services split). Link allowed (1.0106 / 1.0083) | official · A |
| F06 | Exports of services | `C_services ← R_ROW` [P5] · production · fixed | NO `exports_services` · NN `s1_1.exports_services.current` | **28,12,203.94**; SAM 28,12,204 | Link allowed (0.9953 / 0.9958) | official · A |
| F07 | Imports of goods | `R_ROW ← C_goods` [P6] · production · fixed | NO `imports_goods` · NN `s1_1.imports_goods.current` | **56,84,221.12**; SAM 56,84,221 | Link allowed (1.0076 / 1.0121) | official · A |
| F08 | Imports of services, CIF-adjusted (SAM concept) | `R_ROW ← C_services` [P6] · production · fixed | **NN only** `s1_1.imports_services.current` 2022-23..2024-25 | **12,62,685.15**; SAM 12,62,685 | Old-base 1.1 services imports are **not** CIF-adjusted: 14,63,226 in 2022-23, matching NAS 6.1 unadjusted 14,61,480, not the adjusted 11,68,704. So they are not this concept. Their history lives in M06 (imports, BoP basis) | official · A |

#### B. Income

| ID | Flow | SAM definition 2023-24 | Segments → years | 2023-24 values | Method / notes | Status · class |
|---|---|---|---|---|---|---|
| F09 | Compensation of employees (domestic) | `F_LREG, F_LCAS ← A_*` [V1, V1a] · factors · held by production's V1 constraints | NS `oldbase_soa_s1_15.generation_of_income.uses.d1.current` 2011-12..2022-23 · NN `s7_1.total.ce.current` 2022-23..2024-25 | **94,42,896.63**; SAM Σ `io_tables_sut_va` `va.ce.sut_iNN.current` 94,42,897 | Old base ends 2022-23 (89,31,129, FRE, **NAS 2024 vintage**). Single overlap and a different old vintage, so no link. Not the national concept: NAS "CE receivable by residents" (`derived.ce_receivable_by_residents.current`, 94,74,604.95) = V1 + V3 − V4 | official · A |
| F10 | Gross operating surplus + mixed income (incl. CFC) | `F_MIXD, F_GOSC ← A_*` [V2, V2a] · factors · held by V2 constraints | NS `…s1_15.generation_of_income.uses.b2n_b3n` + `…production.uses.p51c` 2011-12..2022-23 · NN `s7_1.total.os_mi.current` + `s7_1.total.cfc.current` | **1,70,20,025.76** (1,31,83,820.20 + 38,36,205.56); SAM Σ `va.os_mi` + `va.cfc` | Sum of net OS/MI and total-economy CFC (the old base publishes net only). Mixed income is not published separately on either base, so no separate MI flow | derived · A |
| F11 | Net primary income from RoW | + `F_LREG ← R_ROW` [V3] + `E_*, G_* ← R_ROW` [R13] − `R_ROW ← F_LREG` [V4] − `R_ROW ← E_*, G_*` [R14, R14a, R3a, R3b] · factors, rest_of_world, fincorp | NB `api.primary_income_row_net.current` 1950-51..2010-11 · NO `primary_income_row_net` · NN `s1_1.primary_income_row_net.current` | **−4,11,995.87** = 62,344.24 + 2,80,907.32 − 30,635.91 − 7,24,611.52 (NN 6.1); B6 `bpm6.inr.bpm6_1_b.net.current` −4,11,996 | Sign-changing balance, so no link. `E_*` = E_NFPU, E_NFPR, E_RBI, E_BANK, E_NBFC, E_INSP. R3a/R3b are listed because sovereign external-debt interest could be written under either (§6.1 D6) | derived · A |

#### C. Taxes

| ID | Flow | SAM definition 2023-24 | Segments → years | 2023-24 values | Method / notes | Status · class |
|---|---|---|---|---|---|---|
| F12 | Taxes on products incl. import duties | `T_CGST, T_SGST, T_GCES, T_UEXC, T_SVAT, T_SEXC, T_OPRT ← C_*` [P7a] + `T_CUST ← C_*` [P8] · taxes, production · P7 constraints by commodity | NO `taxes_on_products` 2011-12..2023-24 · NN `s1_1.taxes_on_products.current` | **32,44,229.14**; SAM = SUT product taxes 30,15,341 + import duty 2,28,887 | No back series: the API serves taxes and subsidies with a 'lakh' label, so they were not ingested (mospi_nas_2026-31); only net taxes go back (M07). No link (0.9907 / 0.9675) | official · A |
| F13 | Product subsidies (negative) | `T_PSUB ← C_*` [P9] · production · fixed | NO −`subsidies_on_products` · NN −`s1_1.subsidies_on_products.current` | **−5,76,422.38**; SAM −5,76,422 | Sign flip of a "Less" item. **Concept break:** the old base includes food subsidy, the new base does not (it is in GFCE) | derived · A |
| F14 | GST to the Centre (CGST incl. unsettled IGST, + compensation cess) | `G_CEN ← T_CGST, T_GCES` [T1a] · taxes · estimated conversion of cash to NAS accrual, fitted to the SUT | RB `rb.tr.0005.central_goods_and_services_tax_cgst` + `rb.tr.0008.integrated_goods_and_services_tax_igst` + `rb.tr.0009.gst_compensation_cess` 2022-23..2024-25 (= `rb.tr.total.total_goods_and_services_tax_gst`) | **9,57,207.82** (8,20,622.09 − 4,850.43 + 1,41,436.16); SAM = taxes' T1a value | UTGST (`rb.tr.0007…` 5,497.16) is **not** in RB "Total GST". Add it only if the taxes block puts UTGST in T_CGST (§5 C7). Partial cross-check: PPAC `ppac.centre.a.cgst` + `ppac.centre.a.igst` (petroleum only, 33,160) | official · C |
| F15 | SGST to States | `G_STA ← T_SGST` [T2x] · taxes | KF `kfi.a_1_1_2-state_goods_and_service_tax.in.all_states_28` **2017-18**..2023-24 (zero before GST: no rows) | **8,00,112.02** (28 States); SA all States+UTs `app1.total_revenue.i.a.3.vii-state_goods_and_services_tax.in.all_states_uts.actuals` 8,41,120.77; SAM = T2x (KFI + UTs with legislature, accrual) | Coverage bridge = UTs with legislature (TAX-5: 41,009) + T2x | official · C |
| F16 | Union excise duties | `G_CEN ← T_UEXC` [T1a] · taxes | RB `rb.tr.total.total_union_excise_duties` 2022-23..2024-25 | **3,05,362.18** | PPAC `ppac.centre.a.excise_duty` (petroleum only, 2014-15..2025-26; 2,73,684 in 2023-24) as a cross-check; **never spliced** into F16 | official · C |
| F17 | Customs duties | `G_CEN ← T_CUST` [T1a] · taxes (equals the `T_CUST` row = P8) | RB `rb.tr.total.total_customs` | **2,33,118.97**; SAM = SUT import duty 2,28,887 | Bridge (TAX-2): export duty 3,347.07 + cesses on exports −3.19, residual −888 | official · C |
| F18 | State sales tax / VAT | `G_STA ← T_SVAT` [T2x] · taxes | KF `kfi.a_1_1_1-taxes_on_sales_trade_etc.in.all_states_28` 2011-12..2023-24 | **3,97,467.06**; SA `app1.total_revenue.i.a.3.i-sales_tax…actuals` 4,06,404.10 | **Break 2017-18:** VAT subsumed into GST except petroleum and alcohol (5,81,435 in 2016-17 → 3,84,913 in 2017-18). Flag, don't adjust | official · C |
| F19 | State excise | `G_STA ← T_SEXC` [T2x] · taxes | KF `kfi.a_1_1_3-state_excise.in.all_states_28` 2011-12..2023-24 | **2,49,133.50**; SA `…i.a.3.ii-state_excise…actuals` 2,58,275.50 | The T2x licence-fee split may move part of it to other cells (GAP_MAP P7a); bridge = that split + UTs | official · C |
| F20 | Stamps & registration fees | `G_STA ← T_PROD` [P10a] {`stamps_registration`} · taxes | KF `kfi.a_1_1_5-stamps_and_registration_fees.in.all_states_28` 2011-12..2023-24 | **2,20,289.49**; SA `app1.total_revenue.i.a.2.ii-stamps_and_registration_fees…actuals` 2,28,154.98 | Needs the named component (§4.2). Production tax per S&M 2026 | official · C |
| F21 | Corporation tax | `G_CEN ← T_CIT` [T1a] (= Σ `T_CIT ← NFC, FC` [T4, T4a]) · taxes | RB `rb.tr.total.total_corporation_tax` 2022-23..2024-25 | **9,11,055.01** | The NAS old-base D5 by sector is **not** a history of this flow (§6.3 F4). Cash vs accrual bridge | official · C |
| F22 | Personal income tax (and other direct taxes of households) | `G_CEN ← T_PIT` [T1a] · taxes | RB Σ `rb.tr.0021.*` (7 items) 2022-23..2024-25 | **10,10,947.77**; + STT `rb.tr.0034.security_transaction_tax` 33,777.78 if taxes puts STT in T_PIT (GAP_MAP T3 says it does) | STT placement is open (§5 C8); the flow follows the taxes block's choice | official · C |

#### D. Government

| ID | Flow | SAM definition 2023-24 | Segments → years | 2023-24 values | Method / notes | Status · class |
|---|---|---|---|---|---|---|
| F23 | Tax devolution to States | `G_STA ← G_CEN` [R1] · government | FT `tsm.states_share.actuals` **1952-53**..2006-07 · AT `at2.i-states_share_in_central_taxes.actuals` 2007-08..2023-24 | **11,29,761.5** (AT); KF `kfi.a_1_3-…all_states_28` 11,29,396.72; Union FA minor head 901 11,29,494 | FT = AT within ₹0.5 cr in 2007-08..2022-23, so the join has no splice. FT's own 2023-24 value (11,29,494) is the Union figure (§6.3 F1), so it is not used | official · B (0.05%, GOV-1/2) |
| F24 | Grants from the Centre to States | `G_STA ← G_CEN` [R2] + `G_STA ← G_CEN` [T2b] {`compensation_grants`} + `K_GSTA ← K_GCEN` [R2k] · government | FT `tsm.total_grants.actuals` 1952-53..2006-07 · AT `at2.ii-grants_from_the_centre.actuals` 2007-08..2023-24 | **5,27,931** (AT, States' receipts, all States+UTs); KF 4,72,465.88 (28 States, incl. GST compensation 43,788.41); Union Statement 18 7,39,260 | States'-receipt measure for all years (the only one available before 2023-24). The SAM measure is the government block's H9 choice. Excludes the 78,104 of cess used for loan recovery (T2b component `cess_loan_recovery`) | official · C |
| F25 | Interest paid by the Centre | Σ `E_RBI, E_BANK, E_NBFC, E_INSP, H_*, E_NFPU, E_NFPR, R_ROW, G_STA ← G_CEN` [R3, R3a, R3b, R5, R14] · fincorp (R14: rest_of_world) | AF `afs.cfi_rev_disbursements.2049` 2022-23..2023-24 · FA `fa9.2049.total` (2023-24, equal) | **11,01,867.88** | Only two years of Union history in clean data (§6.2 G3). R5 is included in case government loan interest is written there (§6.1 D7) | official · B (R3 band) |
| F26 | Interest paid by States | Σ `… ← G_STA` [R3, R3a, R3b, R5] · fincorp (rows as F25, incl. `G_CEN ← G_STA` on Central loans) | KF `kfi.b_1_a-interest_payments.in.all_states_28` 2011-12..2023-24 | **4,94,910.97** (28 States); SA `st13.interest_payments_gross.in.all_states_uts.actuals` 5,07,175.4 | GOV-5 bridge: Delhi, J&K, Puducherry 13,786 | official · B/C |
| F27 | Pensions paid by the Centre | `H_* ← G_CEN` [R9, R9a] · government | AF `afs.cfi_rev_disbursements.2071` 2022-23..2023-24 · FA `fa9.2071.total` | **2,38,328.29** | R9 is cash as published. Excludes R9b (D612 paid back), R9c (GPF/PPF D44) and R10 | official · B |
| F28 | Pensions paid by States | `H_* ← G_STA` [R9, R9a] · government | KF `kfi.b_1_b-pension_and_other_retirement_benefits.in.all_states_28` 2011-12..2023-24 | **4,94,938.72** | as F27 | official · B |
| F29 | Food subsidy (free grain, inside GFCE) | `C_* ← G_CEN` [C2a] {`food_subsidy`} · government | EP `stat7.food` 2022-23..2024-25 | **2,11,814.39** (Statement 7); SAM ≈ SUT GFCE on paddy 1,01,441.21 + wheat 62,530.54 = 1,63,971.75 | FS `sub.food.in.gg_centre` (2018-19..2023-24; 2,30,756 in 2023-24) is a different definition (TAX-11), so it is kept as a separate `variant='fc16_definition'`, not spliced. The cash subsidy vs GFCE-on-grain gap (≈47,843) needs a registered explanation | official · C |
| F30 | Fertiliser subsidy (negative) | `T_PSUB ← C_CHEM` [P9] · production · fixed (the Centre's share via P9a) | FS −`sub.fertilizer.in.gg_centre` (actuals) 2018-19..2021-22 · EP −`stat7.fertiliser` 2022-23..2024-25 | **−1,88,291.62**; SAM −2,07,569.12 (SUT products 89 −1,45,129 and 90 −62,440, pesticides quirk Q6, + other chemicals) | FS `sub.fertilizer.in.gg_centre` equals St 7 in 2022-23 and 2023-24, so it can extend the series back to 2018-19 as `official` (same measure) | derived · C |
| F31 | RBI surplus to the Centre (cash) | `G_CEN ← E_RBI` [R6] · government | RS `r6.surplus_received_by_centre_cash.current` 2022-23..2025-26 | **87,416.22** (= FA `fa8.0050.00.106`) | RBI year *t* surplus is received in FY *t+1* (D0-7). FY 2026-27 (2,86,588) is dropped | official · A |
| F32 | General government gross saving | `K_GCEN, K_GSTA ← G_CEN, G_STA` [K3, K3a] · government · K3 `equal` | NO `…s1_9.general_government.current` 2011-12..2023-24 · NN `s1_9.general_government.current` | **−3,18,384.38** | Negative balance, so no link | official · A |
| F33 | General government GFCF ("public capex") | `C_* ← K_GCEN, K_GSTA` [I1a] · capital_financial · column totals = NAS 1.11 | NA `api.gfcf.sec_gg` (latest round) 2011-12..2023-24 · NN `s1_11.general_government.current` | **12,22,623.35** | No link (1.0774 / 1.0105) | official · A |
| F34 | Government net issuance of debt securities | `K_GCEN, K_GSTA ← I_GSEC` [K8, K8d, K7b] · capital_financial | FF `fsf7.gg.liabilities.transaction.f3.current` 2012-13..2023-24 | **18,83,882.95** | FSF is old-base-consistent. SAM − FSF = K7b postings (e.g. households' G-secs from NAS 5.3) + the FCI bridge; the capital_financial block lists them | official · D |

#### E. Households

| ID | Flow | SAM definition 2023-24 | Segments → years | 2023-24 values | Method / notes | Status · class |
|---|---|---|---|---|---|---|
| F35 | Household gross saving | `K_HH ← H_*` [K4a] · closure · K4 `equal` | NO `…s1_9.household_sector.current` · NN `s1_9.household_sector.current` | **58,90,330.45** | No link (1.0514 / 1.0786) | official · A |
| F36 | Household gross financial saving | Σ `I_* ← K_HH` [K7a] · capital_financial. **Not** K7b, K9, K9b | T12 `t12.assets.financial_assets.current` 1983-84..2010-11 · NO `…s5_3.gross_financial_saving` · NN `s5_3.gross_financial_saving.current` | **36,02,198.51**; old base 2023-24 34,30,640 (pre-Sep-2026 RBI revision) | T12 = NO to ≤ ₹0.5 cr in every year 2011-12..2023-24, so the join needs no splice (§6.3 F2). No link (1.0220 / 1.0500) | official · A |
| F37 | Household financial liabilities | Σ `K_HH ← I_*` [K8a] · capital_financial | T12 `t12.liabilities.financial_liabilities.current` · NO / NN `financial_liabilities` | **19,09,286.70** | Link allowed (1.0025 / 1.0161) | official · A |
| F38 | Household physical saving (GCF excl. valuables) | `C_* ← K_HH` [I1a] + `K_DSTK ← K_HH` [I3a] · capital_financial | NO / NN `saving_in_physical_assets` (s1_9) | **40,25,292.07** (GFCF 40,24,360.34 + CIS) | | official · A |
| F39 | Deposits with banks and co-op banks | `I_DEPO ← K_HH` [K7a] {`banks`, `coop_banks`} · capital_financial | T12 `t12.assets.bank_deposits.current` · NO / NN `with_banks` + `with_co_operative_banks_and_societies` | **14,68,714.45** (14,09,651.87 + 59,062.57) | T12 "bank deposits" = NAS banks + co-op exactly. Excludes non-bank deposits (−59,126.49) and trade debt (8,228.00) | official · A |
| F40 | Shares, debentures and MF units | `I_EQTY, I_CBND, I_MFUN ← K_HH` [K7a] · capital_financial | T12 `shares_debentures` + `units_of_uti` (to 2008-09) · NO / NN `shares_and_debentures` | **3,58,718.50** (of which MF 2,85,052.00) | Before 2009-10, T12 lists units of UTI separately; add them to keep the NAS concept (T12's total = the sum of its items to ₹2 cr) | official · A |
| F41 | Insurance, provident & pension funds | `I_INPE ← K_HH` [K7a] + `I_SSAV ← K_HH` [K7a] {`ppf`} · capital_financial | T12 `life_insurance_fund` + `pf_pension_fund` · NO / NN `insurance_funds` + `provident_and_pension_funds` | **13,72,113.03** (6,49,086.43 + 7,23,026.60) | T12 "life insurance fund" = NAS "insurance funds" in total. PPF may sit in I_SSAV (§6.1 D3) | official · A |
| F42 | Borrowing from banks and co-op banks | `K_HH ← I_LOAN` [K8a] {`banks`, `coop_banks`} · capital_financial | T12 `t12.liabilities.bank_advances.current` · NO / NN `bank_advances` + `loans_and_advances_by_co_operative_banks_and_societies` | **19,07,184.75** (18,56,520.63 + 50,664.12) | **HDFC merger** inflates 2023-24 (K8a note). The as-published series stays. The merger-adjusted memo is the capital_financial block's | official · A |
| F43 | Remittances received | `H_* ← R_ROW` [R11, R11a] · rest_of_world | BI `invis.inr.private_transfers.receipts.current` 2006-07..2025-26 | **9,83,127.72**; NN `s6_1.other_current_transfers_to_resident_sectors_other_than_gener.current` identical 2022-23..2024-25 (EXT-9) | Before 2006-07 only the net back series exists (M11) | official · A |
| F44 | Transfers sent abroad by households | `R_ROW ← H_*` [R12, R12a] · rest_of_world | BI `invis.inr.private_transfers.payments.current` 2006-07..2025-26 | **99,912.81**; NN `s6_1.other_current_transfers_by_resident_sectors_other_than_gener.current` identical | | official · A |

#### F. Corporations and finance

| ID | Flow | SAM definition 2023-24 | Segments → years | 2023-24 values | Method / notes | Status · class |
|---|---|---|---|---|---|---|
| F45 | Private NFC gross saving | `K_NFPR ← E_NFPR` [K1] · capital_financial · fixed | NO `…s1_9.private_non_financial_corporations` · NN `s1_9.private_non_financial_corporations.current` | **24,10,408.53** | Old/new 2022-23: 26,44,507 vs 20,40,884 (−23%). Sector boundary and method change, so no link | official · A |
| F46 | Private NFC GFCF ("private capex") | `C_* ← K_NFPR` [I1a] · capital_financial | NA `api.gfcf.sec_nfc_private` (latest round) · NN `s1_11.private_non_financial_corporations.current` | **28,69,934.71** | No link (0.9285 / 0.9669) | official · A |
| F47 | Financial corporations gross saving | `K_RBI, K_BANK, K_NBFC, K_INSP ← E_RBI, E_BANK, E_NBFC, E_INSP` [K2, K2a] · fincorp · K2 `equal` | NO `…s1_9.financial_corporations` · NN `s1_9.financial_corporations.current` | **9,91,447.76** (public 5,35,509.90 + private 4,55,937.86) | No link (1.1398 / 1.3133) | official · A |
| F48 | NFC net incurrence of liabilities ("corporate borrowing") | Σ `K_NFPU, K_NFPR ← I_*` [K8, K8b, K7b]. **Not** K9/K9b | FF `fsf7.nfc_pub.liabilities.transaction.total.current` + `fsf7.nfc_pvt.liabilities.transaction.total.current` 2012-13..2023-24 | **22,17,360.83** (1,20,128.30 + 20,97,232.53) | SAM − FSF = K7b postings + FCI moved to K_GCEN (K9 bridge) | official · D |

#### G. External

| ID | Flow | SAM definition 2023-24 | Segments → years | 2023-24 values | Method / notes | Status · class |
|---|---|---|---|---|---|---|
| F49 | Current-account deficit (RoW saving, NAS basis) | `K_ROW ← R_ROW` [K5] · rest_of_world · fixed | NB derived `api.gcf_incl_errors_omissions.current` − `api.gross_saving.current` 1950-51..2010-11 · NO `…s1_9.net_capital_inflow_from_row` · NN `s1_9.net_capital_inflow_from_row.current` | **2,08,890.71**; B6 `bpm6.inr.bpm6_1.net.current` −2,15,248 (EXT-6 bridge 6,357) | The derivation is exact in the old base: NO GCF − gross saving = NO NCI in all 13 years 2011-12..2023-24, and NB 2011-12 gives 3,76,171 = NO. Positive = deficit. No link | derived (NB) / official · A |
| F50 | Investment income paid abroad (incl. reinvested earnings) | `R_ROW ← E_*, G_*` [R14, R14a, R3a, R3b] · rest_of_world, fincorp | BI `invis.inr.income.investment.payments.current` 2006-07..2025-26 | **7,24,611.52** = NN `s6_1.property_and_entrepreneurial_income_to_the_rest_of_the_world.current` | Includes D43, the reinvested earnings of 1,63,704 (financial-account counterpart `bpm6.inr.bpm6_3_1_a_1_2.credit.current`). Evidence: NAS 1.9 deducts the same 1,63,704 from private-corporate saving, so for NAS to close it must be paid to RoW inside 6.1 item 8. GAP_MAP R14a still lists this as to-confirm. So R14 + R14a must add to 7,24,612 (§6.1 D1) | official · A |
| F51 | FDI into India (net) | `I_* ← K_ROW` <FDI_equity, FDI_reinvested_earnings, FDI_debt> [K8b] · rest_of_world | FI `t143.inr.fdi_to_india_net.current` 2004-05..2025-26 | **2,22,244** = 37,226 equity + 1,63,704 reinvested + 21,314 other capital (BO `bop_old.inr.ka.fdi.in_india.*`) | FI = BO = B6 `bpm6_3_1_a.net` in every overlap year (EXT-12) | official · A |
| F52 | Portfolio investment in India (FPI, net) | `I_EQTY, I_GSEC, I_CBND ← K_ROW` <FPI_equity, FPI_debt> [K8b] · rest_of_world | BO `bop_old.inr.ka.portfolio.in_india.net.current` 2020-21..2025-26 · proxy FI `t143.inr.portfolio_net.current` 2004-05..2019-20 as `variant='proxy_total_portfolio'` | **3,69,273** (equity 2,08,694 + debt 1,60,580) | FI is total portfolio *including* India's investment abroad (2023-24: 3,64,804). It is therefore a labelled proxy, never mixed into the main variant. NSDL/SEBI 3,39,065 is a cross-check only (EXT-15) | official · A |
| F53 | NRI deposits (net) | `I_DEPO ← K_ROW` <NRI_deposits> [K8b] · rest_of_world | BO `bop_old.inr.ka.banking_capital.commercial_banks.nri_deposits.net.current` 2020-21..2025-26 · NR `nri.flow.inr.total.current` 2007-08..2019-20 | **1,21,860** (NR 1,21,715) | Small source gaps in the overlap (2022-23: 73,143 vs 72,241). BoP wins from 2020-21 | official · A |
| F54 | Increase in forex reserves (BoP) | `I_RESV ← K_RBI` [K8c] · rest_of_world | BO −`bop_old.inr.monetary_movements.reserves.net.current` 2020-21..2025-26 | **5,26,931** (B6 `bpm6.inr.bpm6_3_5.net.current` −5,26,931) | Sign flipped so that an increase is positive. **Not** the change in the T144 stock (`external_sector_fx_reserves`), which includes valuation | derived · A |

### 2.3 Memo aggregates (M01–M15): denominators, totals and balancing items

| ID | Flow | SAM definition 2023-24 | Segments → years | 2023-24 value | Notes |
|---|---|---|---|---|---|
| M01 | GDP at market prices (the share-of-GDP denominator) | `F_* ← A_*` [V1, V1a, V2, V2a] + `T_PROD ← A_*` [P10] + `T_* ← C_*` [P7a, P8, P9] | NB `api.gdp.current` · NO `gdp` · NN `s1_1.gdp.current` · NP `api.gdp.rev_provisional_estimates.current` (3,45,36,796) | **2,90,73,286.73** | Link allowed (0.9735 / 0.9652) |
| M02 | GVA at basic prices | `F_* ← A_*` + `T_PROD ← A_*` | NB `api.gva.current` · NO `gva_basic` · NN `s1_1.gva_basic.current` · NP `api.gva.ind_total.rev_provisional_estimates.current` | **2,64,05,479.98** | Link allowed (0.9666 / 0.9633) |
| M03 | Exports of goods and services | F05 + F06 | NB `api.exports.current` · NO · NN · NP | **64,79,295.53** | Link allowed (1.0042 / 1.0028) |
| M04 | Imports, CIF-adjusted (SAM concept) | F07 + F08 | NN `s1_1.imports.current` · NP `api.imports.rev_provisional_estimates.current` | **69,46,906.27** | New base only; test that NP's concept = 1.1 in 2022-23..2024-25 |
| M05 | CIF adjustment (NAS–BoP reconciliation) | `R_ROW ← X_DISC` [D2] | NN `s6_1.adjustment_for_cif_in_import_of_services.current` | **2,12,499.00** (SUT 2,12,499.24) | UI: "reconciliation item", never "paid abroad" |
| M06 | Imports, BoP basis (before the CIF adjustment) | `R_ROW ← C_*` [P6] + `R_ROW ← X_DISC` [D2] | NB `api.imports.current` 1950-51..2010-11 · NO `imports` (old 1.1 has no CIF adjustment) · NN `s6_1.imports.current` | **71,59,405.27** | The long, consistent imports series. Link allowed (1.0058 / 1.0095) |
| M07 | Net taxes on products | F12 + F13 | NB `api.net_taxes_on_products.current` 1950-51..2010-11 · NO / NN derived · NP `api.net_taxes_on_products.rev_provisional_estimates.current` | **26,67,806.76** | No link (1.0491 / 0.9844) |
| M08 | Direct taxes on income (CIT + PIT) | F21 + F22 | NS `oldbase_soa_s4_0.secondary_distribution_of_income.resources.d5.current` (GG D5 receivable) 2011-12..2022-23 · RB CIT + Σ 0021 2022-23..2024-25 | **19,22,002.78** | 2022-23: D5 16,38,909 vs RB 16,34,055 (+0.30%, TAX-14). Segments stay separate (`base_year` 2011-12 vs null) |
| M09 | Household net financial saving | F36 − F37 | T12 · NO · NN | **16,92,911.81** | No link |
| M10 | Change in inventories | `C_* ← K_DSTK` [I3] | NB `api.cis.current` · NO `cis` · NN `s1_1.cis.current` · NP | **3,82,329.05** | No link (0.58 / 0.83) |
| M11 | Net current transfers from RoW (non-government) | F43 − F44 | NB `api.other_current_transfers_row_net.current` 1950-51..2010-11 · NO / NN `other_current_transfers_row_net` | **8,83,214.91** | The only long remittance-type series; old = new in 2022-23 |
| M12 | Household residual (statistical discrepancy) | `X_DISC ← H_*` [D1] · closure · fixed | NN `derived.household_residual.current` (`mospi_nas_2026_derived_residuals`) 2022-23..2024-25 | **5,71,133.27** | 2024-25 −1,28,402.90 |
| M13 | Household gross disposable income | Σ over `H_*` columns of rows `C_*` + `K_HH` + `X_DISC` | NO `oldbase_nas2025_s1_14.households_npish.gross_disposable_income.current` · NN `s1_14.households_npish.gross_disposable_income.current` | **2,28,77,010.24** = 1,64,15,546.52 + 58,90,330.45 + 5,71,133.27 | No link (0.9846 / 0.9656) |
| M14 | Union gross tax revenue | Σ `G_CEN ← T_CGST, T_GCES, T_CUST, T_UEXC, T_OPRT, T_PIT, T_CIT` [T1a] (+ Centre part of `G_CEN ← T_PROD` [P10a]) | FT `tsm.gtr.actuals` **1952-53**..2023-24 · RB `rb.tr.total.total_tax_revenue` − `rb.tr.0710.less_states_share` − `rb.tr.total.net_less_nccd_transferred_to_the_national_disaster_response_fund` for 2024-25 | **34,65,519** | RB derivation = FT exactly in 2022-23 (30,54,192) and 2023-24. Gross of devolution. Class C |
| M15 | General government property income paid (old base) | none (old base ends 2022-23) | NS `oldbase_soa_s4_0.allocation_of_primary_income.uses.d4.current` 2011-12..2022-23 | 2022-23: 14,32,470 | History of F25 + F26 on NAS concepts (consolidated, accrual). Not additive with F25 + F26 cash (2022-23: 9,57,690 + 4,46,198) |

### 2.4 Optional flows (build if the verifier has time; same method)

| ID | Flow | SAM definition | Segments | 2023-24 | Notes |
|---|---|---|---|---|---|
| X01 | Public NFC gross saving | `K_NFPU ← E_NFPU` [K1] | NO / NN `public_non_financial_corporations` (s1_9) | 4,62,996.25 | A |
| X02 | Public NFC GFCF | `C_* ← K_NFPU` [I1a] | NA `api.gfcf.sec_nfc_public` · NN `s1_11.public_non_financial_corporations.current` | 10,00,165.28 | A |
| X03 | Household GFCF | `C_* ← K_HH` [I1a] | NA `api.gfcf.sec_households_npish` · NN `s1_11.household_sector.current` | 40,24,360.34 | A |
| X04 | Household currency holdings | `I_CURR ← K_HH` [K7a] | T12 `currency` · NO / NN `currency` | 1,18,247.97 | Demonetisation story (2016-17) |
| X05 | Household claims on government (G-secs + small savings excl. PPF) | `I_GSEC ← K_HH` + `I_SSAV ← K_HH` excl. {`ppf`} [K7a] | T12 `claims_on_government` · NO / NN `claims_on_government` | 3,35,303.06 (25,552.16 + 3,09,750.90) | Depends on the PPF decision (§6.1 D3) |
| X06 | Direct investment by India (ODI, net outflow) | `K_ROW ← I_*` <ODI> [K8b] | FI `t143.inr.fdi_by_india.current` 2004-05..2025-26 | 1,38,223 | = BO `ka.fdi.abroad.net` × −1 |
| X07 | ECB to India (net) | `I_LOAN ← K_ROW` <ECB> [K8b] | BO `bop_old.inr.ka.loans.ecb.to_india.net.current` 2020-21..2025-26 | 28,969 | Only 6 years |
| X08 | Computer-services exports | `C_ITSV ← R_ROW` [P5] | BO `bop_old.inr.ca.services.misc.software.credit.current` 2020-21..2025-26 · NN `s6_1.miscellaneous_services.computer_services.current` | BoP/NAS 13,27,596; SAM (SUT product 150) 12,80,075 | Class C: product vs BoP classification |
| X09 | Investment income received from abroad | `E_*, G_* ← R_ROW` [R13] | BI `invis.inr.income.investment.receipts.current` | 2,80,907.32 | A |
| X10 | Bank (ODC) loans extended | `I_LOAN ← K_BANK` [K7, K7b] | FF `fsf7.fc_odc.assets.transaction.f4.current` 2012-13..2023-24 | 26,57,918.08 | D: the HDFC merger is removed from SAM transactions |
| X11 | Net production taxes | `T_PROD ← A_*` [P10] | NS `…s1_15.generation_of_income.uses.d29` − `…d39` · NN `s7_1.total.net_production_taxes.current` | −57,442.41 | A |

### 2.5 The linked (spliced) variant

- **Default is unspliced.** Both bases stay in the table for 2022-23 and 2023-24, with `base_year`. REFERENCE_YEAR §5 asks for an explicit break marker, to be replaced when MoSPI's new-base back series appears (P1-6, expected Dec 2026).
- **Optional `variant='linked_2022_23'`.** For t ≤ 2021-22: `linked(t) = old(t) × new(2022-23)/old(2022-23)`, status `derived`. Method text: "ratio-linked at the 2022-23 overlap; not additive across flows; replace with MoSPI's back series when published".
- **Allowed only when all of these hold:**
  - both overlap ratios exist;
  - |r(2022-23) − r(2023-24)| ≤ 0.02;
  - the flow keeps one sign;
  - the flow has no documented concept change at the break.
- **Allowed now (10):** M01 GDP (0.97347 / 0.96515), M02 GVA (0.9666 / 0.9633), F01 PFCE (0.9039 / 0.9054), F03 GFCF (1.0068 / 1.0088), M03 exports (1.0042 / 1.0028), F05 (1.0106 / 1.0083), F06 (0.9953 / 0.9958), F07 (1.0076 / 1.0121), M06 imports BoP basis (1.0058 / 1.0095), F37 household liabilities (1.0025 / 1.0161).
- **Refused, with the reason stored in the definitions table:**
  - concept change: F02, F08/M04, F13;
  - unstable ratio: F04, F12, M07, F33, F46, F35, F36, M13 (**amended, §9 A3:** M13's ratios 0.98462 / 0.96561 differ by 0.019, inside the 0.02 rule; its refusal is a plan decision, not a failing rule);
  - sign or residual: F11, F32, F49, M09, M10;
  - single overlap: F09, F10 (NAS 2024 ends 2022-23 and is a different vintage);
  - sector method change: F45, F47.
- **Scope.** The ratios are computed in code from the rows above, never typed in. Base-less flows (BoP, fiscal, FSF) are never linked.

### 2.6 Coverage by year (core flows with a published value, main variant)

| From | Core flows available | Added |
|---|---:|---|
| 1950-51 / 1952-53 | 7 | F01, F02, F03, F11, F49 (1950-51); F23, F24 (1952-53) |
| 1983-84 | 13 | F36, F37, F39, F40, F41, F42 |
| 1999-00 | 14 | F04 |
| 2004-05 | 15 | F51 |
| 2006-07 | 18 | F43, F44, F50 |
| 2007-08 | 19 | F53 |
| 2011-12 | 38 | F05, F06, F07, F09, F10, F12, F13, F18–F20, F26, F28, F32, F33, F35, F38, F45–F47 |
| 2012-13 | 40 | F34, F48 |
| 2017-18 | 41 | F15 |
| 2018-19 | 42 | F30 (FS, the same measure as St 7) |
| 2020-21 | 44 | F52, F54 |
| 2022-23 | 54 | F08, F14, F16, F17, F21, F22, F25, F27, F29, F31 |

2024-25 has 42, because 12 core flows end in 2023-24: the State series (KF: F15, F18–F20, F26, F28), AT (F23, F24), FSF (F34, F48) and AFS (F25, F27). 2025-26 has 12: F01–F04 (NP), F31 (RS) and seven BoP flows (F43, F44, F50–F54). The Map's time slider needs this matrix; the builder writes it as `top_flows_coverage.parquet` (flow × year → segment, status), in line with STACK_AND_REPO §4.3 ("a year is available only if the time series has official or derived data for it").

### 2.7 Output files and code layout

- **Code.**
  - `pipeline/timeseries/flows.yaml`: the declarative definitions. Per flow: id, name, group, tier, display_sign, SAM terms (rows, cols, refs, components, bop_functions, coef), segments (code, dataset, series ids with coefficients, period range, base_year, variant, precedence) and link policy. Reviewable by the verifier without reading code.
  - `pipeline/timeseries/build.py`
  - `pipeline/timeseries/explanations.yaml`: the registered 2023-24 bridges of §7 T3.
- **`data/timeseries/top_flows.parquet`.** Columns:
  - `flow_id`, `period`, `period_type` (`fy`), `value`, `unit` (`INR_crore`), `price_basis` (`current`), `base_year`, `variant` (`published` | `linked_2022_23` | `proxy_total_portfolio` | `fc16_definition`);
  - `segment`, `datasets`, `series_ids` (comma list), `estimate_stage`, `vintage`, `status`, `prov_id`, `note`.

  Sorted by key; floats rounded to 6 decimals.
- **`data/timeseries/top_flows_definitions.parquet`.** One row per flow:
  - the SAM terms as JSON, plain-English description, display_sign;
  - link policy and both overlap ratios (when computed);
  - the tolerance class and explanation id.
- **`data/timeseries/top_flows_sam_check.parquet`.** Per flow, for 2023-24:
  - the time-series value and its segment;
  - the SAM value, prior and balanced;
  - the difference and relative difference;
  - the class, the tolerance, the verdict and the explanation text.
- **`data/timeseries/top_flows_coverage.parquet`** (§2.6) and **`data/timeseries/_provenance.parquet`.**
- All files are written through `pipeline/core/io` and included in `data/manifest.json` and `repro` (DESIGN_BRIEF §6).

---

## 3. Constraints to declare

**None.** The block writes no entries and must not influence balancing. Its official totals already enter the SAM through the owning blocks' constraints. Examples:
- production's C1/C2/I1/P5/P6/P7 by commodity and V1/V2 by activity;
- capital_financial's K1/K4/K7a/K8a totals;
- fincorp's K2, government's K3 and R3 control;
- rest_of_world's K5, R11/R12/R13/R14 and K8b totals.

A duplicate here would add nothing, and a slightly different target (e.g. KFI 28 States vs all States and UTs) would create infeasibility. The block reports **non-binding checks** instead (§7 T3), in the spirit of the framework's `CHECK_DTYPES`.

What it relies on other blocks to constrain (so that class-A checks are exact after balancing):

| Official total | Constraint owner (expected) | Flows depending on it |
|---|---|---|
| SUT PFCE, GFCE, GFCF, CIS, valuables, exports and imports by commodity | production (C1, C2, I1, I3, P5, P6 are fixed or `equal`) | F01–F08, M03–M06, M10 |
| SUT CE, OS/MI + CFC by activity; P10 | production (V1, V2, P10) | F09, F10, X11, M01, M02 |
| NAS 1.9 saving by sector | capital_financial (K1, K4), fincorp (K2), government (K3) | F32, F35, F45, F47, X01 |
| NAS 1.11 GFCF by sector (I1a column totals) | capital_financial | F33, F38, F46, X02, X03 |
| NAS 5.3 household assets and liabilities by instrument (K7a/K8a) | capital_financial | F36, F37, F39–F42, X04, X05 |
| NAS 6.1 items 2, 3, 4, 7, 8, 9 and 1.9 net capital inflow; BoP instrument totals by tag | rest_of_world | F11, F43, F44, F49–F54 |

---

## 4. Interfaces

### 4.1 Needs from the framework (to go into `docs/phase2/FRAMEWORK_REQUESTS.md`)

1. **A post-SAM step.** The time series needs the balanced SAM only for the 2023-24 check. It should run after `sam` balancing, as `uv run python -m pipeline timeseries`, and be part of `repro`/`manifest`. Building the series itself needs only clean data, so the step can build first and check last.
2. **A provenance call without a gap-map ref.** `BlockContext.prov(ref=…)` rejects a ref not in `data/gap_map.csv`, and defaults `base_year` to 2022-23.
   - Needed: `ingest_unit='timeseries'` (or `sam_timeseries`), a flow id in place of `ref`, and `base_year` settable to `2011-12` or null.
   - Where a row is a single clean value copied unchanged, it may reuse the clean `prov_id` directly.
3. **Per-period vintage selection.** `select_vintage(vintage='latest')` keeps the latest vintage *per series*. For a time series that silently drops older periods: e.g. RB 2022-23 rows carry vintage 2024-07-23 and would be dropped because the series' latest is 2026-02-01.
   - Needed: read whole frames and assert one vintage per (series_id, period). I checked this holds today for every dataset in §2.1.
   - Alternatively: a `by_period=True` option.
4. **A reader for balanced SAM entries.** `sam_entries_balanced.parquet` and `sam_entries_prior.parquet` with ref, component and bop_function, plus the block constraints (for class-B bands).
5. **The component filter on constraints** (also requested in the households plan) is **not** needed here: the flows filter by component in their own code.

### 4.2 Needs from other blocks (names must be agreed and frozen; tests fail if they disappear)

| Block | What the time series needs | For |
|---|---|---|
| production | P5/P6 entries by commodity (so goods/services split by the commodity lists in §2.0); P9 on C_CHEM; P10; V1/V2 as constraints only (no total entries that duplicate factors' V1a/V2a) | F05–F08, F13, F30, X11 |
| households | C1a/C4a–C4d entries at group level; **no** duplicate NPISH entries on top of C1a (C4c must be inside the SUT PFCE, and the C1 `equal` constraints catch a breach) | F01, M13 |
| factors | V1a/V2a entries (V1, V2 as constraints); V3/V4 in the RoW cells | F09–F11 |
| taxes | tax-account → government cells under T1a/T2x. **Components on P10a**: at least `stamps_registration`, `land_revenue`, `other_production_taxes`, `production_subsidies`. A stated decision on **UTGST** (MH 0007) and **STT** (MH 0034) placement. P7a on the seven product-tax rows | F12, F14–F22, M08, M14 |
| government | R1; R2 and R2k; **T2b components** `compensation_grants` and `cess_loan_recovery`; R9/R9a by government; **C2a component** `food_subsidy` on the grain rows; R6; K3/K3a; the H9 choice for R2 (States' receipts or Union Statement 18), stated in its plan | F23, F24, F27–F29, F31, F32 |
| fincorp | Government interest written once, under R3/R3a/R3b, with column = paying government, including G_CEN ← G_STA interest on Central loans. **Not** repeated under R5 or R14 (§6.1 D6/D7). K2/K2a | F25, F26, F47, F50 |
| rest_of_world | R11/R11a, R12/R12a, R13, R14 **net of** R14a (§6.1 D1), K5, K8b with `bop_function` tags FDI_equity, FDI_reinvested_earnings, FDI_debt, FPI_equity, FPI_debt, NRI_deposits, ECB, ODI, reserves (the framework already accepts FDI_debt and short_term_credit), K8c | F11, F43, F44, F49–F54, X06, X07, X09 |
| capital_financial | I1a by sector column; I2/I2a on C_GJOM; I3a; K7a/K8a under those refs **only** for the NAS 5.3 values, with **components** `banks`, `coop_banks`, `nonbank_deposits`, `trade_debt` (I_DEPO), `ppf` (I_SSAV), `banks`, `coop_banks`, `nbfc`, `government`, `insurers` (I_LOAN liabilities); K7b postings and K9/K9b residuals under their own refs (never K7a/K8a); K8/K8d | F03, F04, F33–F42, F46, F48, X02–X05, X10 |
| closure | K4a and D1 at group level | F35, M12, M13 |

No block needs anything from the time series in Phase 2. `households` publishes `hh_keys`, but the time series does not use them: the flows are national totals.

### 4.3 Publishes

- `data/timeseries/top_flows.parquet`, `top_flows_definitions.parquet`, `top_flows_sam_check.parquet`, `top_flows_coverage.parquet`, `_provenance.parquet` (§2.7).
- **For Phase 3 (the Map):**
  - the per-year flow set and the coverage matrix;
  - a `display_sign` per flow and the break-marker rule (`base_year` changes between consecutive rows);
  - the share-of-GDP denominator rule. A NAS flow uses M01 of the same `base_year`. A base-less flow uses new-base M01 from 2022-23 and old-base M01 (NO, then NB) before.
- **For Checkpoint B:** the `top_flows_sam_check` table: which official series the SAM reproduces exactly, and the bridges for the rest.

---

## 5. Conflicts and choices (where official sources disagree)

| # | Topic | Values (2023-24 unless stated) | Control for the time series | Cross-check | Why |
|---|---|---|---|---|---|
| C1 | Grants Centre → States (H9) | RBI SF AT2 5,27,931 (States + UTs); FC16 KFI 4,72,465.88 (28 States, incl. GST compensation 43,788.41); Union Statement 18 7,39,260; AFS/FA MH 3601 5,39,963.59 | **AT2** (and FT before 2007-08, which equals AT2) | KFI, St 18, IGAS-2 | Only the States'-receipt measure exists as a long series. It matches FC16 after the UT bridge (GOV-8); RECONCILIATION recommends it for the cell |
| C2 | Devolution | AT2 11,29,761.5; FA 11,29,494 (901 heads); KFI 11,29,396.72 | **AT2** | FA, KFI (±0.05%) | Same long-series logic; all agree within 0.02% (GOV-1/2) |
| C3 | FC16 master time series vs RBI in 2023-24 | FT grants 7,39,260 vs AT2 5,27,931; FT devolution 11,29,494 vs AT2 11,29,761.5 | AT2 for 2007-08..2023-24 | FT only before 2007-08 | FT = AT2 within ₹0.5 cr for 2007-08..2022-23, then switches to Union-side figures (§6.3 F1) |
| C4 | Household financial saving, old vs new vintage | NAS 2026 36,02,198.51; NAS 2025 old base and T12 34,30,640 | New base for 2022-23+; old base (T12/NO) before | HBS T11 base 2022 (HH-6) | New-base NAS is the SAM control; the old/new gap is RBI's Sept-2026 revision (HH-9) |
| C5 | FPI | BoP 3,69,273; NSDL/SEBI 3,39,065 (EXT-15); FI total portfolio 3,64,804 | **BoP** | NSDL (licence limits reuse) | The BoP is what the SAM's K8b uses; FI is a different concept (includes portfolio abroad) |
| C6 | Food subsidy | Exp. Profile St 7 2,11,814.39; FC16 2,30,756; SUT GFCE on paddy + wheat 1,63,971.75 | **St 7** (matches the Union accounts, TAX-11) | FC16 as a separate `fc16_definition` variant; SUT GFCE in the SAM check | The SAM books GFCE on grain, not the cash subsidy. The gap is an explained bridge (FCI costs outside grain GFCE) |
| C7 | GST total | RB "Total GST" 9,57,207.82 excludes UTGST 5,497.16; TAX-7 adds UTGST to CGST | RB total (0005 + 0008 + 0009) | + UTGST if taxes puts it in T_CGST | Follow the taxes block; recorded in the definition |
| C8 | Personal income tax | Σ MH 0021 10,10,947.77; + STT 33,777.78; RB "Total taxes on income" 10,44,756.25 | Σ MH 0021 (+ STT per taxes' decision) | NAS old-base D5 (M08 only) | GAP_MAP T3 includes STT in T_PIT. TAX-14 suggests NAS D5 excludes STT: in 2022-23, D5 16,38,909 is +0.3% against CIT + MH 0021, but −1.2% if STT (25,085) is added. The taxes block must settle it |
| C9 | Corporate vs personal tax history | NAS old-base NFC D5 paid 8,35,813 (2022-23) > Union CIT 8,25,834; HH D5 6,42,596 < MH 0021 8,08,221 | Budget only (3 years) for F21/F22 | M08 total direct taxes (NAS GG D5, 2011-12..2022-23) | NAS allocates income tax by payer sector, not by tax head, so sector D5 is not a CIT/PIT series (§6.3 F4) |
| C10 | Imports concept across bases | New 1.1: CIF-adjusted 69,46,906.27; new 6.1 unadjusted 71,59,405.27; old 1.1 unadjusted 70,92,192 | F07/F08/M04 = SAM concept (new only); **M06** = BoP basis for history | CIF adjustment M05 | Only the unadjusted concept exists on both bases |
| C11 | Current-account balance | NAS 1.9 NCI 2,08,890.71; BPM6 CA −2,15,248; old-format BoP CA −2,15,890 | **NAS NCI** (= K5) | BPM6 (EXT-6 bridge 6,357) | K5 is the SAM cell. Note the two BoP presentations differ by 642 in 2023-24; use BPM6 for cross-checks |
| C12 | NRI deposits | BoP 1,21,860; NR 1,21,715 | **BoP** from 2020-21 | NR | The BoP feeds K8b. NR fills 2007-08..2019-20 (labelled segment) |
| C13 | State taxes coverage | KFI (28 States) vs RBI SF (all States + UTs): SGST 8,00,112.02 / 8,41,120.77; VAT 3,97,467.06 / 4,06,404.10; excise 2,49,133.50 / 2,58,275.50; stamps 2,20,289.49 / 2,28,154.98; interest 4,94,910.97 / 5,07,175.4 | **KFI** (13 consistent years) | RBI SF (2023-24) in the SAM bridge | RBI SF appendices have only 2023-24 Actuals in clean data, so coverage stays consistent over time |
| C14 | Fertiliser subsidy | St 7 1,88,291.62 = FC16; SUT C_CHEM product subsidies −2,07,569.12 | St 7 (FC16 extends it back to 2018-19, same measure) | SUT in the SAM check | The SUT row includes the NBS amount booked on pesticides (Q6) and other chemicals |

---

## 6. Risks, gaps and open questions

### 6.1 Double-counting risks in the flow definitions (and in the blocks they read)

| # | Risk | Guard |
|---|---|---|
| D1 | **Reinvested earnings counted twice.** NAS 6.1 item 8 (7,24,611.52) already contains D43 (1,63,704). If rest_of_world writes R14 = item 8 *and* R14a = 1,63,704, F50 and F11 overstate by 1,63,704 | rest_of_world writes R14 = item 8 − R14a. F50 class-A check against 7,24,611.52 catches it |
| D2 | **Household financial saving polluted by residual postings.** K9/K9b (net-lending residuals) and K7b counterpart postings can land in `I_* ↔ K_HH` cells | F36/F37 and F39–F42 filter refs K7a/K8a only; T4 fails if a K_HH instrument entry carries an unlisted ref |
| D3 | **PPF in two NAS lines** (mospi_nas_2026-27: S&M lists PPF in PF & pension; NAS 5.3 notes are silent on "small savings") | F41 = insurance + PF & pension, whether capital_financial books PPF under I_INPE or under I_SSAV `ppf`; X05 excludes `ppf`. If NAS itself counts PPF twice, F41 + X05 overstate: flag, don't fix |
| D4 | **Valuables inside GFCF.** Both are `C_* ← K_*` | F03 refs {I1, I1a} only; F04 refs {I2, I2a} only; D3 (K_HH ← X_DISC) excluded |
| D5 | **Food subsidy counted twice** (GFCE and product subsidy) on the new base | F29 is a component *of* F02; never add them. F13 new base excludes food; the old base includes it (concept break) |
| D6 | **Sovereign external-debt interest under both R3a and R14** (the gap map assigns ROW ← G_CEN to both) | fincorp and rest_of_world agree on one ref. F25 and F50 include both refs, so the check against R3 (cash + R3b) and against NAS 6.1 item 8 catches a duplicate |
| D7 | **Government interest to FCs under both R3a and R5** (R5 lists GOV as a payer) | fincorp writes it once. F25/F26 include R5 only as a safety net; the class-B check against the R3 control catches duplicates |
| D8 | **GST: IGST and cess.** Adding IGST collections to post-settlement CGST/SGST double-counts | F14 uses MH 0008 (unsettled residual, −4,850.43) only; IGST settlement is memo S7, never a flow here |
| D9 | **Devolution netted from Union taxes** | Union tax flows (F14, F16, F17, F21, F22, M14) are gross; devolution F23 is a separate transfer |
| D10 | **Grants and GST compensation.** KFI counts the GST compensation *loan* as a grant; T2b's 78,104 loan recovery is not a grant received | F24 = R2 + R2k + T2b `compensation_grants` only. The AT2 control's treatment of compensation is checked in the bridge (open question Q5) |
| D11 | **C1 (production) and C1a/C4c (households)** both on COM ← H | Production writes C1 as constraints only. Households' C4c must not add NPISH on top of SUT PFCE: the C1 `equal` constraints fail if it does |
| D12 | **Intra-government interest** (States → Centre on Central loans: FA receipt 13,641.26 vs States 15,072, GOV-7) | Included in F26 (paid by States), not in F25. Consolidated GG interest (M15 history) excludes it: stated in the M15 note |
| D13 | **CE: domestic vs national** | F09 = domestic (V1). "CE receivable by residents" = V1 + V3 − V4 is not a flow here |

### 6.2 Where the brief's §8 method cannot be followed as written, and the fallback

| # | Brief expects | Reality in clean data | Fallback (recommended) |
|---|---|---|---|
| G1 | "NAS API old-base series from 1950-51" for the top flows | The API back series (`mospi_nas_2026_api_b2011_back`, 95 series) covers only 1.1-type aggregates and GVA by industry: no CE, OS/MI, taxes by type or sector accounts. Its industry GVA does not add to the total before 2004-05 (mospi_nas_2026-33) | Aggregates from 1950-51; everything else from 2011-12 (NO/NS). No attempt to back-cast |
| G2 | Taxes and subsidies on products from the API | Not ingested (the API labels them 'lakh' while they are crore; mospi_nas_2026-31) | Gross taxes and subsidies from 2011-12 (NO); **net** taxes from 1950-51 (M07) |
| G3 | "budget … series" | Union budget only 2022-23..2024-25 (RB, three Receipt Budgets), AFS 2022-23..2023-24, FA 2023-24. There is no long Union history of CIT, PIT, excise, customs, interest or pensions | Keep the 2–3 year Union flows. Use FC16 GTR (M14, 1952-53+) and M08 (NAS D5, 2011-12..2022-23) for the long direct-tax story. **Ingest request to the orchestrator:** RBI HBS Union-finance tables or the Budget "at a glance" history (rbidocs is behind a challenge, D1-4, so it may need a manual download) |
| G4 | "BoP … series" | INR BoP detail only 2004-05+ (T143), 2006-07+ (invisibles), 2020-21+ (full BoP) | As in §2.2. The older BoP (HBS T127 history) is an ingest request |
| G5 | "RBI series" for flow of funds | FSF 2012-13..2023-24 only, old-base vintage (H4); HDFC merger in 2023-24 | FSF flows as published (class D check with K7b/K9/merger bridges) |
| G6 | A splice across the base break | No new-base back series (P1-6); unstable, concept-dependent ratios | Unspliced by default; whitelist-only linked variant (§2.5) |
| G7 | Test "2023-24 value = SAM definition" | For fiscal cash series the SAM holds accrual, SUT-fitted estimates by construction (T1a, T2x) | Pre-registered bridges (class C); the test fails only on an unexplained gap |

### 6.3 New data findings (for `docs/phase2/issues/timeseries.md`; headline items for ISSUES.md)

- **F1 — The FC16 master transfer series changes basis in 2023-24.**
  - `state_fiscal_fc16_transfers` `tsm.total_grants.actuals` and `tsm.states_share.actuals` equal RBI State Finances AT2 (`at2.ii-…`, `at2.i-…`) within ₹0.5 cr for 2007-08..2022-23.
  - For 2023-24 they hold Union-side values instead: grants 7,39,260 (Union Statement 18) vs AT2 5,27,931; devolution 11,29,494 (Union FA) vs AT2 11,29,761.5.
  - state_fiscal-7 lists the three grant measures but not this switch inside one series. Anyone using FT's last year as "States' receipts" gets a 2.1 lakh cr jump.
- **F2 — RBI HBS T12 is the old-base NAS household financial saving.**
  - T12 equals NAS 2025 old-base 5.3 within ₹0.5 cr in every year 2011-12..2023-24. This holds for gross financial saving, liabilities, currency, shares & debentures, PF & pension, insurance funds (T12 "life insurance fund" = NAS "insurance funds" total), claims on government, trade debt, non-bank deposits, bank deposits (= banks + co-op), and bank advances (= banks + co-op loans).
  - So the household financial series join at 1983-84 without a splice. **Amended (§9 A1):** no splice, but not one base either: T12 before 2011-12 is RBI's splice of earlier bases (level breaks expected at 2004-05 and 2011-12), labelled `base_year` null with a `base_change` flag at 2011-12.
- **F3 — Old-base imports of services are not CIF-adjusted.**
  - NAS 2025 old-base 1.1 imports of services are 14,63,226 in 2022-23. The new base's 6.1 unadjusted figure is 14,61,480; the new base's 1.1 CIF-adjusted figure is 11,68,704.
  - The new/old ratio for 1.1 services imports is therefore 0.80, a concept difference, not a level revision.
- **F4 — Old-base sector D5 cannot stand for CIT/PIT.** In 2022-23, NFC D5 paid (8,35,813) exceeds Union corporation tax (8,25,834), while household D5 (6,42,596) is well below income tax MH 0021 (8,08,221). Only the GG total D5 is comparable (TAX-14).
- **F5 — The base-break ratios are large and uneven.** New/old in 2022-23 and 2023-24:
  - PFCE 0.904 / 0.905; GFCE 1.064 / 1.005; CFC 1.145 / 1.142; CIS 0.58 / 0.83;
  - product subsidies 0.815 / 0.896; imports of services 0.80 / 0.86;
  - private NFC saving 0.77 / 0.84; FC saving 1.14 / 1.31;
  - household saving 1.05 / 1.08.

  Old-base 1.1 also carries a discrepancy of −4,74,817 (2022-23) that the new base does not. A single GDP ratio must not be applied to components.
- **F6 — Framework limits for this block.** `ctx.prov` requires a gap-map ref, and `select_vintage('latest')` works per series, not per period (§4.1).
- **F7 — Two BoP presentations disagree by 642 in 2023-24** (current account −2,15,890 in the old format vs −2,15,248 in BPM6). EXT checks use BPM6. Minor; logged.

### 6.4 Other risks

- **Vintage mixing inside the old base.**
  - NO (NAS 2025, 2025-06-26) and NS (NAS 2024, 2024-06-05) are different editions: 2022-23 GDP is 2,68,90,473 (Final) vs 2,69,49,646 (FRE).
  - CE and OS/MI (NS) therefore do not share a vintage with PFCE/GDP (NO) in old-base years. Label the vintage per row; never divide an NS flow by an NO GDP without saying so. REFERENCE_YEAR §5 already asks not to mix them for ratios.
  - NA (API latest round) is equivalent to NO for 1.1 items (issue 9). For sector GFCF this is assumed, not verified (no NAS 2025 1.11 ingested).
- **Estimate maturity.** Old base 2023-24 is FRE; new base 2024-25 FRE and 2025-26 PE; BoP 2025-26 preliminary. They are shown with `estimate_stage`, and the UI marks them.
- **Concept breaks at 2017-18 (GST)** in State VAT (F18) and at the new base in GFCE/subsidies (F02, F13, F29). They are shown, not adjusted.
- **HDFC merger (1 Jul 2023)** distorts F42 (household bank borrowing: 18,56,521 vs 11,91,385 the year before) and X10. The as-published series is kept; the merger-adjusted memo is capital_financial's.
- **Class-C checks depend on other blocks' choices** (R2 measure, UTGST/STT placement, T1a/T2x adjustments). If those plans change, the registered bridges change; the explanations file must be regenerated from their logged adjustments, not typed in.
- **Licence.** RBI series (T12, T143, AT2, invisibles, BoP, FSF) are for internal processing until RBI grants permission (D1-1d, P1-9). The public time slider is blocked on that, not on the pipeline.

### 6.5 Open questions (for the orchestrator; none block the builder)

1. Approve the flow set: 54 core, 15 memo and 11 optional. The brief says "~50".
2. Approve **no default splice** plus the whitelist-only `linked_2022_23` variant (§2.5), or ask for no linking at all until MoSPI's back series (Dec 2026).
3. Raise the ingest requests of §6.2 G3/G4 (long Union-finance and BoP history). Both are RBI documents behind the rbidocs challenge (D1-4), so a manual download may be needed.
4. Confirm the "latest complete FY" cut-off (2025-26) and the exclusion of budget RE/BE and old-base post-2023-24 API rounds.
5. Does RBI AT2 "grants from the Centre" include GST compensation grants in 2017-18..2023-24? This decides whether F24's control and the SAM's R2 + T2b `compensation_grants` are the same concept. The KFI note says it treats the GST compensation *loan* as a grant.

---

## 7. Tests the builder should write (`tests/timeseries/`, marker `sam` or a new `timeseries`)

Every expected value is read from clean Parquet in the test, never typed in. The numbers in brackets are what the data hold today, for orientation.

- **T1 — Segments reproduce their sources.**
  - For every row with a single source series: `value == coef × clean value` for that (dataset, series_id, period), and `prov_id` traces to that clean row.
  - For sums: equal to the sum of the listed clean rows.
  - Examples: F23 2023-24 = `at2.i-states_share_in_central_taxes.actuals` (11,29,761.5); F36 1990-91 = `t12.assets.financial_assets.current`; F49 1950-51 = `api.gcf_incl_errors_omissions.current` − `api.gross_saving.current`.
- **T2 — Joins without splices are real equalities** (they justify §2.1's precedence):
  - T12 = NO 5.3 for every component and year 2011-12..2023-24, within ₹1 cr (F2);
  - FT = AT2 for grants and devolution in 2007-08..2022-23, within ₹1 cr, and ≠ in 2023-24 (F1: the test documents the switch);
  - NB 2011-12 = NO 2011-12 within ₹5 cr for GDP, PFCE, GFCE, GFCF, exports, imports and GVA;
  - NO GCF − gross saving = NO NCI in all years 2011-12..2023-24 within ₹1 cr (the F49 derivation);
  - RB GTR derivation = FT GTR in 2022-23 and 2023-24;
  - FI `fdi_to_india_net` = BO `ka.fdi.in_india.net` for 2020-21..2025-26;
  - BI remittances and investment income = NN 6.1 for 2022-23..2024-25.
- **T3 — The 2023-24 SAM check** (against `sam_entries_balanced.parquet`; prior also reported).
  - **Class A** (official, held by fixed entries or `equal` constraints): |TS − SAM| ≤ max(₹5 cr, the owning constraint's tolerance). Flows: F01–F13, F31–F33, F35–F47, F49–F54, M01–M07, M09–M13, X01–X04, X09, X11. Key targets:
    - PFCE 1,64,15,546.52; GFCE 31,21,027.37; GFCF 92,45,762.46; valuables 3,76,231.72;
    - exports goods / services 36,67,091.58 / 28,12,203.94; imports goods / services 56,84,221.12 / 12,62,685.15;
    - CE 94,42,896.63; GOS + MI 1,70,20,025.76; net primary income −4,11,995.87;
    - taxes on products 32,44,229.14; subsidies −5,76,422.38; RBI surplus 87,416.22;
    - GG saving −3,18,384.38; GG GFCF 12,22,623.35; household saving 58,90,330.45;
    - household gross financial saving 36,02,198.51; household liabilities 19,09,286.70;
    - private NFC saving 24,10,408.53; FC saving 9,91,447.76;
    - NCI 2,08,890.71; remittances 9,83,127.72 / 99,912.81; investment income paid 7,24,611.52;
    - FDI 2,22,244; FPI 3,69,273; NRI 1,21,860; reserves 5,26,931;
    - GDP 2,90,73,286.73; household residual 5,71,133.27; household GDI 2,28,77,010.24.
  - **Class B** (official control, estimated conversion inside a band): within the owning block's constraint band. F23 (0.05%), F25/F26 (R3 band), F27/F28 (R9). **Amended (§9 A2):** only F23 stays class B; F25, F27 and F28 are class C with clean-series bridges.
  - **Class C** (cash vs accrual or coverage): |TS − SAM| > max(₹500 cr, 1%) needs an entry in `pipeline/timeseries/explanations.yaml`. The entry names the bridge items and their source: the owning block's logged adjustment or a clean series (e.g. F15: UTs 41,009 from TAX-5 + T2x; F17: export duty 3,347.07). F14–F22, F24, F29, F30, M08, M14, X08.
  - **Class D** (FSF/BoP with counterparty postings): the difference must equal Σ of the K7b/K9/merger postings the capital_financial block logged for those cells, within ₹5 cr. F34, F48, X10.
  - A missing explanation fails the test, mirroring DESIGN_BRIEF §5.3.
- **T4 — Definitions cover their cell blocks.**
  - Every ref, component and tag named in `flows.yaml` exists in the balanced entries.
  - For each (rows × cols) block a flow reads, every ref present there is either in the flow's list or in its explicit `excluded_refs`. A new ref cannot silently join or leave a flow (guards D1–D7, D11).
- **T5 — Identities on the time series itself** (new base 2022-23..2024-25, within ₹5 cr):
  - M01 = F01 + F02 + F03 + M10 + F04 + M03 − M04 + NAS `discrepancies` (0, 0, −1,07,438.04);
  - M03 = F05 + F06 and M04 = F07 + F08;
  - M06 = M04 + M05;
  - M02 = F09 + F10 + X11;
  - M09 = F36 − F37;
  - M13 = F01 + F35 + M12;
  - F36 = F39 + non-bank deposits + trade debt + X04 + F40 + F41 + X05 (2023-24: 36,02,198.51);
  - old base: M03 = F05 + F06 (2011-12..2023-24).
- **T6 — Base-year and variant rules.**
  - The key (flow_id, period, base_year, variant) is unique.
  - Every NAS-derived row has `base_year`; base-less rows have null.
  - Both bases are present in 2022-23 and 2023-24 for every flow with NO/NS and NN segments.
  - No `linked_2022_23` row for a flow outside the whitelist. Linked rows are `derived` and carry both overlap ratios in the definitions table; the ratios are recomputed in the test.
  - No row from RE/BE, old-base API rounds after 2023-24, or FY 2026-27.
- **T7 — Sign and unit conventions.**
  - F13 and F30 are ≤ 0 in every year; F54 is positive when reserves rise (2023-24: 5,26,931).
  - Every row is `INR_crore`, `current`.
- **T8 — Provenance.** Every row has a `prov_id` in `data/timeseries/_provenance.parquet` or in clean provenance. Derived rows list all input clean prov_ids and a non-empty method. No `estimated` row exists.
- **T9 — Determinism.** Byte-identical outputs across PYTHONHASHSEED 0/1 and 1/4 threads (`repro`), and every file is listed in `data/manifest.json`.
- **T10 — Coverage matrix.** `top_flows_coverage.parquet` agrees with the rows, and the counts in §2.6 are reproduced (54 core flows in 2022-23 and 2023-24, 42 in 2024-25, 12 in 2025-26).

---

## 8 Cross-plan review (2026-09-30, cross-plan critic; details and ids in `CROSS_REVIEW.md`)

What this block must change or confirm:

1. **XR-9 F25/F26 government interest: add the refs fincorp actually writes.**
   - Households' interest from government is in **R8a** (components `small_savings` ≈ 2,14,948 and `gsec_direct`, col G_CEN/G_STA).
   - GPF interest is in **R9c** (`gpf_union` 18,871.50, col G_CEN; `gpf_states` 54,183.14, col G_STA).
   - The current definitions ([R3, R3a, R3b, R5, R14]) would miss ≈ ₹2.3–2.9 lakh cr.
   - R3b has no entries (constraint and satellite only). R5 can stay as a guard.
2. **XR-19 component names, agreed with the owners:**
   - taxes P10a: `stamps_registration`, `land_revenue`, `property_tax`, `other_production_taxes`, `gross_subsidies` (F20 reads `stamps_registration`);
   - government C2a: `food_subsidy` on C_CROP ← G_CEN (F29);
   - capital_financial K7a: `banks`, `coop_banks`, `nonbank_deposits`, `trade_debt`, `ppf`;
   - capital_financial K8a: NAS 5.3 liability-line components (F39, F42);
   - government T2b: `compensation_grants`, `cess_loan_recovery` (F24).
3. **F14:** taxes puts UTGST in T_CGST (component `utgst`). Register the +5,497.16 bridge against RB "Total GST". **F22:** STT is in T_PIT (decision D-9), so the SAM value is MH 0021 + STT. Note that T3 also moves ≈ 2.17 lakh of MH 0021 to firms (T_PIT ← E_NFPR/E_BANK); `G_CEN ← T_PIT` still equals the cash total within the T1 band.
4. **F24 / F27 / F28:** government's pension group entries will carry ref **R9a** (XR-11); keep [R9, R9a]. If the orchestrator adopts the institutional Centre/State view (XR-7, decision D-5), R2 gains the components `css_outside_treasury` and `ulb_direct`. Decide whether F24 (the States'-receipt series AT2) excludes them; the class-C bridge must name them.
5. **F11/F50:** rest_of_world owns all R_ROW ↔ domestic property income (R14 = item 8 − R14a). Your D1/D6 guards stand.
6. **Framework prerequisites.**
   - Per-period vintage selection is done (FRAMEWORK_REQUESTS P-4).
   - The post-SAM step and provenance without a gap-map ref (P-16 / FR2-2) are still **OPEN**. Do not start the builder until they exist.
7. **Double-counting guards confirmed against the block plans:**
   - PPF is in I_SSAV{`ppf`} (capital_financial), so F41 must add it and X05 must exclude it, as planned;
   - valuables (I2, I2a) are separate from GFCF (I1, I1a) on C_GJOM;
   - F36/F37 read K7a/K8a only, so K9_HH (if government writes capital transfers to households, decision D-3) stays out.

## 9 Amendments after verification (2026-09-30; `docs/phase2/verify/timeseries.md`, dispositions in `docs/phase2/issues/timeseries.md`)

- **A1 (TSV-2) T12 before 2011-12 has no base.** The clean T12 records for 1983-84..2010-11 carry `base_year` null, and their Phase 1 note says RBI splices in earlier-base figures (level breaks expected at 2004-05 and 2011-12). The T12 = NAS 5.3 equality holds only from 2011-12, so it cannot give the earlier years a base. The T12 segments are now `base_year` null. The build checks that every row's `base_year` equals its clean inputs' base, and flags 2011-12 `base_change` for F36, F37, F39–F42 and M09. F37's linked variant now starts in 2011-12: the 2022-23 ratio is not applied to rows on an earlier base.
- **A2 (TSV-3, TSV-4, TSV-7) Government interest and pensions.** The owning controls are not the cash series. Government's R9 nets the NPS employer contribution and CGHS out of MH 2071, and uses RBI SF App. II (all States and UTs) net of the State employer NPS contribution. Fincorp's R3b puts MH 2049 on the NAS concept and nets intra-State items out of App. II. So:
  - F25, F27 and F28 are class C, with clean-series bridges in `explanations.yaml`;
  - F26's bridge now also subtracts App. II 'others' (fincorp's intra-State netting);
  - F25/F26 exclude R14 `other_primary_income`, which is not interest.

  Before balancing, the residuals are F25 −0.01, F26 −960 (fincorp's estimated SDL interest held by States, no clean series), F27 +0.01 and F28 0.00.
- **A3 (TSV-5) Link rules are evaluated for every flow.** The result is stored in `top_flows_definitions.link_rules`. The data rules hold for 14 flows: the 10 whitelisted plus F39, F42, M11 and M13. The four extra flows stay refused by plan policy until the orchestrator decides (issue timeseries-5). A refusal may not cite unstable ratios when the rules hold.
