# Phase 2 plan: `households` block (C1a, C4a, C4b, C4c, C4d; satellites S8 and `hh_keys`)

Written 2026-09-30 by the households data scout / method planner. Research only: no code under `pipeline/`, no `pipeline build/sam/repro` runs. Every number below was read from `data/clean/**.parquet` with DuckDB/polars in a scratch folder outside the repo (FY 2023-24, ₹ crore, current prices, unless stated). Numbers marked *indicative* come from my scratch prototype of the method; the builder must recompute them in code, and the verifier must recompute them independently. They are there so the builder knows what "right" roughly looks like, not to be typed into the block.

Inputs read: `docs/phase2/DESIGN_BRIEF.md`; `docs/phase0/ACCOUNT_STRUCTURE.md` §4.1, §5, §9, §11; `docs/phase0/GAP_MAP.md` and `data/gap_map.csv` rows C1, C1a, C4a–C4d, S8, F3a–F3c, R8a, R9a, R11a, R16, R17, K4a, D1 and hard problems H1, H5, H7, H11, H12; `DECISIONS.md` (D0-5, D1-2); `ISSUES.md` (P0-4, P1-4, P1-5); `docs/phase1/COVERAGE.md`; `docs/phase1/RECONCILIATION.md` (HH-1…HH-9, FIN-1); `docs/phase1/issues/hces_consumption.md`, `labour_enterprise_surveys.md`; `pipeline/ingest/*_coverage.yaml`; the framework as it stood at 18:50 on 30 Sep (`pipeline/sam/framework.py`, `spec.py`, `accounts.py`).

---

## 1. Summary (plain English)

- The households block splits **private consumption (PFCE, ₹1,64,15,547 cr)** across the 10 household groups (rural/urban × consumption quintile), commodity by commodity. The *level* of each commodity always comes from the official Supply-Use Table; the household survey (HCES 2023-24) only decides *who* gets what share. HCES itself captures only 44% of national-accounts consumption, so we never use its levels.
- The 10 groups are HCES 2023-24 **person** quintiles within rural and within urban (each rural group ≈ 171 mn people, each urban group ≈ 73 mn). The published fractile tables aggregate exactly to these quintiles, so the lack of unit-level microdata (D1-2) costs nothing for consumption.
- Four slices need their own keys because HCES does not cover them the normal way: **housing** (₹21.5 lakh cr: actual rent, imputed rent of owner-occupiers, government-provided housing), **bank and insurance services** (₹11.1 lakh cr, mostly FISIM), **health and education fees** (₹11.3 lakh cr) and **NPISH** consumption (not separable; left embedded).
- The biggest judgement is **imputed rent** (₹16 lakh cr). The gap map planned an AIDIS-based proxy, but HCES 2023-24 publishes MoSPI's own imputed rent by fractile, which is better. It puts 73% of imputed rent in urban households; the AIDIS building-value proxy would put about 60% there. That choice moves about ₹2 lakh cr between rural and urban groups, so it is shown as a sensitivity band.
- The block also publishes **`hh_keys`**: population, households, HCES spending by item, housing and financial-service splits, and AIDIS asset/debt keys already mapped to the 10 groups, plus a State-to-national-quintile crosswalk. Every later block (wages, taxes, pensions, remittances, interest) uses these instead of re-deriving quintiles.
- **S8** (free PDS grain by group, outside the SAM) comes from HCES free-grain quantities, valued so that the totals equal the SUT's government consumption of paddy and wheat (₹1,63,972 cr). Over half of it goes to the bottom three rural groups.
- All entries are `estimated`, role `free`, confidence `medium` (direct HCES keys) or `low` (proxy keys). They are pinned by 31 commodity constraints and a total constraint, so balancing can only move money *between groups within a commodity*, never change what a commodity's total consumption is.

---

## 2. Ref-by-ref table

### 2.0 Group definition (used by every ref)

| SAM group | HCES 2023-24 fractile classes (A2/A10F `household_group`) | Persons (mn) | Households (mn) | HCES consumption, ₹ cr/yr at HCES scale (A2 persons × MPCE × 12) |
|---|---|---:|---:|---:|
| H_R1 | rural_p00_05 + p05_10 + p10_20 | 170.95 | 30.86 | 4,48,682 |
| H_R2 | rural_p20_30 + p30_40 | 170.95 | 33.80 | 6,14,919 |
| H_R3 | rural_p40_50 + p50_60 | 170.95 | 37.07 | 7,55,265 |
| H_R4 | rural_p60_70 + p70_80 | 170.95 | 41.60 | 9,42,527 |
| H_R5 | rural_p80_90 + p90_95 + p95_100 | 170.94 | 50.46 | 14,66,252 |
| H_U1 | urban_p00_05 + p05_10 + p10_20 | 72.58 | 14.34 | 2,79,665 |
| H_U2 | urban_p20_30 + p30_40 | 72.58 | 16.51 | 4,06,356 |
| H_U3 | urban_p40_50 + p50_60 | 72.59 | 18.28 | 5,20,673 |
| H_U4 | urban_p60_70 + p70_80 | 72.59 | 20.59 | 6,77,308 |
| H_U5 | urban_p80_90 + p90_95 + p95_100 | 72.58 | 28.17 | 11,62,797 |
| Total | | 1,217.64 | 291.67 | 72,74,444 (= 44.3% of NAS PFCE; RECONCILIATION HH-1) |

Source: `hces_consumption_a2_fractile_persons`, series `a2.hces2324.persons.in.<class>`, `a2.hces2324.households.in.<class>`, `a2.hces2324.avg_mpce.in.<class>.current`, geography `IN`, **period `2023-08/2024-07` (period_type `sy`)**, vintage 2025-01-30, prov `hces_consumption:e5e8a3696a31`. `ctx.rows()` defaults to `period="2023-24"`, so every HCES read must pass the survey window explicitly. Fractile sums differ from the `rural_all`/`urban_all` rows by 300 and 100 persons (rounding); use the fractile rows.

Survey window: HCES runs Aug 2023–Jul 2024 (8 of 12 months overlap FY 2023-24). Per P1-5 the mapping must be recorded: one `derived` provenance record, "HCES 2023-24 distribution shares applied to FY 2023-24 levels; shares assumed stable over the 4-month offset", cited as an input by every HCES-keyed record.

### 2.1 The table

Values are FY 2023-24, ₹ crore. "SUT" = `io_tables_sut_use` (vintage 2026-08-31, Final; product series prov `io_tables:f6d331e96230`, total prov `io_tables:221b6f549118`).

| Ref | Cell | Entries to write | Source datasets / series | 2023-24 values | Role | Method (short; detail in 2.2–2.8) | Status label |
|---|---|---|---|---|---|---|---|
| (C1, owned by production) | COM → HH total | none (declared as constraints only; see §3) | `io_tables_sut_use` `use.pfce.sut_pNNN.current` (119 products); `use.pfce.total.current`; `mospi_nas_2026_s1_1` `s1_1.pfce.current` | 1,64,15,547.0 (SUT); 1,64,15,546.52 (NAS 1.1) | — | Targets of constraints `hh.c1.*` | OFFICIAL control |
| **C1a** | C_x → H_R1…H_U5 for the 26 commodities with PFCE other than C_DWEL, C_FINS, C_INSR, C_HLTH, C_EDUC | one entry per (commodity, group, SUT product) → component = SUT product slug, e.g. `sut_p060`; 114 products × 10 groups ≈ 1,140 entries | SUT `use.pfce.sut_pNNN.current`; HCES `hces_consumption_a10f_item_fractile` `a10f.hces2324.<code>.value.<class>.current` (leaf codes only, `dim_other` `item_role=leaf`); A2 persons; concordances `io_tables_sut_product_to_sam34` and a new `hces2324_item_to_sut_product` | Sum of the 26 commodities = 1,20,27,521 (= 1,64,15,547 − C_DWEL 21,48,044 − C_FINS 8,52,794 − C_INSR 2,55,939 − C_HLTH 4,93,394 − C_EDUC 6,37,855) | free; confidence `medium` where the SUT product has a direct HCES counterpart, `low` where the key is a proxy (Appendix A) | For each SUT product p: share_g = Σ_items HCES value(g) / Σ_g …; entry = SUT PFCE_p × share_g | ESTIMATED; gap-map method followable (A10F is item × fractile, so D1-2 costs nothing); refined to SUT-product level |
| **C4a** | C_DWEL → H_* | 3 components × 10 groups: `actual_rent`, `imputed_rent`, `govt_housing` | SUT `use.pfce.sut_p144.current`; `io_tables_sut_supply` `supply.output.sut_p144.sut_i57.current` and `…sut_i67.current` (prov `io_tables:6a316c71cfc7`); HCES A10F items 520 (rent paid) and 539 (imputed rent memo, `item_role=memo`); cross-checks `mospi_nas_2026_s8_13` `s8_13.ownership_of_dwellings.output.current`, `mospi_nas_2026_s5_1` `s5_1.gross_rentals_equipment_and_material_for_housing.current`, AIDIS press note | PFCE 21,48,044; of which supplied by ownership of dwellings (SUT ind. 57) 21,27,988.47 and by public administration (ind. 67) 20,056.0 = government-provided housing. HCES scale: rent paid 2,13,935; imputed 6,41,016 → actual share 0.250231. *Indicative*: actual 5,32,488; imputed 15,95,500; govt 20,056 | free; `actual_rent` medium, `imputed_rent` low, `govt_housing` low | Sizes from SUT supply + HCES ratio; keys HCES 520 (actual and govt housing) and HCES 539 (imputed) | ESTIMATED; **gap-map primary (AIDIS 2019) cannot be followed** (Report 588 not located; only all-buildings/fixed-asset proxies) → HCES 2023-24 imputed-rent memo instead |
| **C4b** | C_FINS → H_*; C_INSR → H_* | C_FINS: `fisim_deposits`, `fisim_loans`, `explicit_fees`; C_INSR: `insurance_service` (40 entries) | SUT `use.pfce.sut_p142.current`, `use.pfce.sut_p143.current`; `mospi_nas_2026_s1_13` `s1_13.private_final_consumption_expenditure.current` (prov `mospi_nas_2026:0e7bdd089aeb`); `rbi_financial_accounts_hh_finsav_52ab` `t52b.fa_deposits_bank.current`, `t52b.fa_deposits_nonbank_ofi.current`, `t52b.fl.current` (period `2024-03-31`, vintage 2026-09-25); `labour_enterprise_surveys_aidis_2019_quintile` `i9.financial_assets_per_hh.<ru>_q<k>.all.current`, `i9.cash_loan_per_hh.<ru>_q<k>.all.current` (period `2018-06-30`); `labour_enterprise_surveys_aidis_2019_press_note` `pn.debt_share_institutional.<ru>.all` | C_FINS 8,52,794 = FISIM 6,02,896.96 + explicit fees 2,49,897.04 (derived); C_INSR 2,55,939. Stocks 31 Mar 2024: deposits 1,41,79,504 + 1,27,257.3; liabilities 1,21,30,649 → deposit weight 0.5412. *Indicative* FISIM split 3,26,261 deposits / 2,76,636 loans | free; confidence low | FISIM keyed by deposit and institutional-loan holdings (AIDIS mapped to groups); fees and insurance by financial assets | ESTIMATED; partly followable. **Insurance key (HCES premium items) does not exist** in HCES 2023-24 → AIDIS financial-assets key |
| **C4c** | (inside COM → H_*) | **no entries** (would double count); one memo satellite `c4c_npish_memo` | `io_tables_icio_india` `icio.{dom,imp}.*.npish.current`, `icio.tls.npish.current` vs `…hfce…` (2022-23, USD mn, international) | NPISH FCE ≈ 0.50% of household+NPISH FCE in OECD ICIO 2022-23 (10,152.6 of 20,41,862 USD mn); not separable in any NAS 2026 table | — | NPISH consumption is already inside the SUT PFCE by product, so C1a/C4a/C4b/C4d spread it by each product's HCES key (the gap-map rule applied commodity by commodity). State this in every C1a provenance record | ESTIMATED; implemented as "embedded + memo" |
| **C4d** | C_HLTH → H_*; C_EDUC → H_* | components `oop_health` (SUT p153), `oop_education` (SUT p152); 20 entries | SUT `use.pfce.sut_p153.current`, `use.pfce.sut_p152.current`; HCES A10F items 411–414, 421, 422, 424 (health services) and 405, 406, 408 (education); checks `hces_consumption_health596` `t2_21.oop_per_hosp_case_avg.<ru>_hh_q<k>` (2025), `hces_consumption_cms_education_2025` `s2_3.exp_per_student.all.person.<ru>_all` (2025-Q2) | C_HLTH 4,93,394 (NAS 5.1 health services 4,91,886.01); C_EDUC 6,37,855 (NAS 5.1 6,37,855.06). HCES scale: health services 1,73,131, education fees 2,61,815 | free; confidence medium | HCES items; the two NSS reports as directional checks only | ESTIMATED; followable at published-table level |
| **S8** | satellite GOV × HH (not a SAM cell) | satellite `s8_food_stik`: per group × grain: quantity (kg), value (₹ cr), plus memo rows for State free items | HCES A10F `a10f.hces2324.061.qty.<class>` (rice-free), `062` (wheat-free), `070` (coarse-free), 071–075 (pulses, gram, salt, sugar, oil: State schemes); `hces_consumption_a10sw_state_item_imputed` (imputed values, State × R/U only); SUT `use.gfce.sut_p001.current`, `use.gfce.sut_p002.current`; check `union_fiscal_exp_profile` `stat7.food.food_subsidy` | Free rice 2,57,59,081 t, wheat 1,23,71,240 t (annual, HCES population). SUT GFCE paddy 1,01,441.21, wheat 62,530.54 (total 1,63,971.75). Union food subsidy 2,11,814.39 (Actuals, cash). *Indicative* S8: H_R1 29,891 … H_U5 1,953 | n/a (satellite, status estimated) | Quantity × uniform national GFCE unit value per grain (= quantity shares × SUT GFCE) | ESTIMATED satellite; followable |
| **hh_keys** (+ `hh_hces_items`, `hh_group_map`, `hh_state_xwalk`, `c1a_hces_nas_ratio`) | satellites (register with `ref="C1a"`, the framework requires a REFS ref) | see §4.2 | A2, A10F, AIDIS i9 and press note, RBI T52(b), the block's own entries | see §4.2 | n/a | see §2.8 | new; not a gap-map ref |

### 2.2 C1a: method, step by step

1. **Read PFCE by SUT product.** `ctx.rows("io_tables_sut_use", …)` for series matching `^use\.pfce\.sut_p\d{3}\.current$`, period `2023-24` (119 rows, sum 1,64,15,547.0 = `use.pfce.total.current`). **Do not read** `use.pfce.purchases_nonresidents_domestic.current` (−2,80,978) or `use.pfce.purchases_residents_abroad.current` (+2,26,203): the product rows are already on the national concept (they sum to the NAS 1.1 national PFCE), and these two are memo rows. Adding them would understate PFCE by 54,775.
2. **Map products to SAM commodities** with `ctx.concordance("io_tables_sut_product_to_sam34")` (the one production uses). PFCE exists on 31 commodities; C_OILG, C_OMIN and C_MTLS have none (no entries there). C_GJOM PFCE (25,054) is product 126 (misc. manufacturing) only; product 125 (gems & jewellery) has no PFCE, only valuables (3,76,232).
3. **Build the key concordance** `data/concordance/hces2324_item_to_sut_product.csv` (columns `sut_product, hces_item, key_quality {direct|proxy}, note`), committed and read via `ctx.concordance()` so its sha256 is recorded. Appendix A is my tested draft: every one of the 116 C1a/C4d products (114 + 2) gets a non-empty key, and the prototype reproduces their PFCE, 1,31,58,770 (C1a 1,20,27,521 + C4d 11,31,249), exactly. Rules the builder must enforce (and test):
   - only codes with `item_role=leaf` in `dim_other` (373 leaf codes carry values in 2023-24; 8 more leaf codes, the free items 061, 062, 070–075, carry only quantities); never `subtotal`, `total`, `aggregate`, `memo_detail`. The single exception is 539 (`item_role=memo`), used only by C4a.
   - **excluded from every PFCE key**: 640–643 jewellery (valuables, I2/K_HH); 061, 062, 070–075 free items (no value is published, '##'; free PDS grain is GFCE, C2a/S8); 282 "cooked meals received as assistance" (₹53,212 cr at HCES scale; mostly PM-POSHAN/ICDS meals, which are government STiK in GFCE); 520/539 (C4a only); 405–408 and 411–414/421–424 (C4d only); 522 residential land rent (rent on land is property income D45, not PFCE); 899 other consumer taxes & cesses is used only as the proxy key for C_PADM (fees to government), never as consumption of a good.
   - items that serve several SUT products (e.g. rice items key both paddy p001 and milled rice p060) are allowed; the share is a distribution, not a level.
   - every leaf item must be either used by at least one product key or listed in an explicit exclusion list with a reason. My draft leaves 470 (flowers), 471 (mosquito repellent), 633 (other durables) and 523 (other consumer rent) to be placed (suggest p027, p093, p126, p145).
4. **Aggregate HCES to groups:** for each leaf item i and fractile class f, annual value = `value_per_person_30d(i,f)` × persons(f) × 12 / 10^7 (₹ crore/yr at HCES scale); sum classes into the 10 groups (2.0). A10F cells printed '-' are absent in clean data (17 leaf items have fewer than 24 value rows, e.g. 005 cheese has 19); treat absent as 0. The unit build already asserts that leaves re-add to the published sub-totals, so this is consistent.
5. **Key and entry:** key_p(g) = Σ_{i ∈ items(p)} V_i(g); share_p(g) = key_p(g)/Σ_g key_p(g); entry(C_x ← H_g, ref C1a, component `sut_pNNN`) = PFCE_p × share_p(g). A group with key 0 gets no entry (structural zero; the framework rejects zero-valued entries). Uniform scaling within each product is the H1 assumption ("the HCES/NAS gap is distribution-neutral within each product"); state it in the method text.
6. **Status/role/confidence:** `status=estimated`, `role=free`, `confidence` from `key_quality` (direct → medium, proxy → low). One provenance record per SUT product (inputs: the SUT product prov, the A10F prov records, the A2 prov, the survey-window assumption record, the concordance). Method text cites C1a, the item list, H1, and that NPISH (C4c) is embedded.
7. **Why product level, not commodity level:** HCES/NAS ratios differ a lot within a commodity (e.g. air fares: HCES 2,053 vs SUT 52,076; milk 4,12,792 vs 10,66,018), so keying at the 34-commodity level would let the HCES mix, not the SUT mix, weight products inside a commodity. Product components also give the site its SUT drill-down (ACCOUNT_STRUCTURE D6). If the orchestrator prefers fewer balancing variables, collapse components to `total` after computing at product level; the prior per cell is identical.

### 2.3 C4a: dwelling services (21,48,044)

1. **Sizes.** Government-provided housing = `supply.output.sut_p144.sut_i67.current` = 20,056.0 (S&M 2026: PFCE housing = GVO of ownership of dwellings + housing services provided by government; DESIGN_REVIEW row 58). Ownership of dwellings = PFCE − 20,056 = 21,27,988.0 (the supply side prints 21,27,988.47; the 0.47 is Use-table integer rounding: control on the Use value). Split 21,27,988 into actual and imputed rent with the HCES ratio r = V_520 / (V_520 + V_539) = 2,13,935.12 / 8,54,951.60 = 0.250231 → actual ≈ 5,32,488, imputed ≈ 15,95,500 (*indicative*). One `estimated` record for the split ratio (no NAS table separates tenant and owner-occupied rent).
2. **Keys.** `actual_rent`: HCES item 520 "house/garage rent (actual)" by group (tenant side; 55% in H_U5). `imputed_rent`: HCES item 539 "house/garage rent (imputed)" by group (identical to A6 `memo_imputed_rent`; 27.0% rural). `govt_housing`: HCES 520 as proxy (low). The gap map wanted government-employee CE by group (F1a), but that is built by `factors`, which depends on `households`, so reading it would be a cycle; at 0.9% of C_DWEL the proxy is harmless. Log it.
3. **Entries:** 3 components × 10 groups, ref C4a, free; confidence medium (actual), low (imputed, govt).
4. **Publish** the three components by group in `hh_keys` (`c4a_actual_rent`, `c4a_imputed_rent`, `c4a_govt_housing`): `factors` needs the imputed-rent consumption by group for F3a (income keyed exactly like consumption) and the actual-rent total for F3b (whose *distribution* must follow landlords, not tenants).
5. *Indicative* C4a by group: H_R1 19,587; H_R2 36,388; H_R3 56,453; H_R4 1,01,395; H_R5 2,68,862; H_U1 1,29,487; H_U2 1,94,835; H_U3 2,60,347; H_U4 3,61,607; H_U5 7,19,084.

### 2.4 C4b: FISIM, explicit financial fees, insurance service (11,08,733)

1. **Sizes.** FISIM = `s1_13.private_final_consumption_expenditure.current` = 6,02,896.961538 (equal to `s5_1.financial_intermediation_services_indirectly_measured.current`). Explicit fees = SUT p142 − FISIM = 2,49,897.04 (`derived`). Insurance service = SUT p143 = 2,55,939.
2. **FISIM deposits vs loans.** No NAS table splits household FISIM by instrument. Split by end-March 2024 household stocks (stated assumption: equal margins either side of the reference rate): deposits (1,41,79,504 + 1,27,257.3) vs liabilities 1,21,30,649 → 0.5412 / 0.4588. Recorded as an `estimated` parameter record.
3. **Group keys (AIDIS 2019 → SAM groups).** AIDIS publishes per-household values by *its own* household-expenditure quintile classes (each 20% of households within R/U, stocks at 30.06.2018), not by our person quintiles (labour_enterprise_surveys-21). Map by cumulative household share: within R/U, order the SAM groups by MPCE and compute each group's household range from HCES A2 households (rural H_R1 = 0–15.9%, H_R2 15.9–33.4%, H_R3 33.4–52.5%, H_R4 52.5–74.0%, H_R5 74.0–100%; urban 0–14.6–31.5–50.2–71.2–100%); group total = Σ_k overlap(group, AIDIS class k) × R/U households × per-household value_k. This gives R/U totals and within-R/U shares in one step.
   - deposit key: `i9.financial_assets_per_hh` (the press-note "deposits" share, 5% rural / 9% urban of assets, equals financial assets within rounding, so AIDIS financial assets are the deposit proxy);
   - loan key: `i9.cash_loan_per_hh` × institutional share by R/U (`pn.debt_share_institutional` 66 rural, 87 urban; FISIM arises only on institutional loans);
   - *indicative* shares (% of all-India): financial assets H_R1 2.52, R2 3.96, R3 7.03, R4 10.54, R5 12.28, U1 2.43, U2 5.41, U3 11.11, U4 18.65, U5 26.06; cash loans 2.87, 5.30, 9.15, 15.44, 16.81, 1.53, 3.79, 8.51, 14.89, 21.72.
4. **Explicit fees and insurance service:** financial-assets key (low). HCES 2023-24 has **no insurance-premium item** (checked: none of the 373 leaf items), so the gap-map key cannot be built. Sensitivity alternative: HCES non-food total (984). Record both in the method text.
5. **Entries:** C_FINS × {fisim_deposits, fisim_loans, explicit_fees} and C_INSR × {insurance_service}, 40 entries, ref C4b, free, low. Publish all four components by group in `hh_keys` for `fincorp` (R4/R5 FISIM adjustment by group; R17 non-life net premiums must exclude the service charge).

### 2.5 C4c: NPISH consumption (embedded)

The gap-map method ("spread in proportion to each group's total PFCE") would **double count** if written as extra entries, because SUT PFCE by product already includes NPISH consumption and C1a/C4a/C4b/C4d already distribute all of it. Implementation: keep C4c in `REFS`; write no entries; write satellite `c4c_npish_memo` (ref C4c) with the international memo (OECD ICIO 2022-23 India: NPISH FCE 10,152.6 USD mn incl. `icio.tls.npish.current` 136.7, against HFCE 20,41,862 USD mn → 0.50%; status `estimated`, method says "international, old base, memo only; not used in any SAM value"). Every C1a/C4 provenance method states that NPISH is embedded and distributed by each product's household key (a documented simplification the methodology page must show). If the orchestrator prefers, C4c can instead be listed in `refs_not_implemented` with this reason; I recommend the memo because it records the decision in data.

### 2.6 C4d: out-of-pocket health and education

Keys: C_HLTH (p153, 4,93,394) ← HCES 411 X-ray/tests, 412 doctor's fee, 413 hospital charges, 414 other (hospitalisation) + 421, 422, 424 (non-hospitalisation). Medicines (410, 420) key C_PHRM under C1a, not C4d. C_EDUC (p152, 6,37,855) ← HCES 405 tuition and fees, 406 private tutor/coaching, 408 other. Books/stationery (400, 401, 404) key C_WOOD products under C1a. The SUT C_EDUC has no PFCE on p147 (R&D). Entries: components `oop_health`, `oop_education`, ref C4d, free, medium.
Checks (`ctx.check`, not enforced): (a) HCES health-services share of H_R5+H_U5 vs NSS 596 OOP per hospitalisation case rising from q1 to q5 in both sectors (rural 25,704 → 39,582; urban 25,178 → 53,531; different survey, class definition and unit: direction only); (b) urban/rural ratio of HCES education fees per person vs CMS 2025 per-student spending (urban 23,470 vs rural 8,382). Unit data for either NSS survey would upgrade these (D1-2).

### 2.7 S8: food subsidy (free PDS grain) as social transfer in kind, by group

1. Annual free quantities by group: `a10f.hces2324.061.qty.<class>` (rice-free), `062` (wheat-free) × persons × 12 (stored in tonnes, kg/1000: hces_consumption-25). Totals at HCES scale: rice 2,57,59,081 t, wheat 1,23,71,240 t, coarse 3,69,218 t.
2. Value = quantity × uniform national GFCE unit value per grain, i.e. quantity shares × SUT GFCE: rice → `use.gfce.sut_p001.current` 1,01,441.21 (implied ₹39.38/kg), wheat → `use.gfce.sut_p002.current` 62,530.54 (implied ₹50.55/kg). This is the gap-map "GFCE unit value"; the SUT GFCE is the same value C2a writes to G_CEN, so S8 reconciles with the SAM.
3. Memo rows (not scaled, no SAM counterpart): coarse grains-free (070) and State free items 071–075 valued at A10SW All-India R/U imputed unit values (`a10sw.hces2324.<code>.{value,qty}.in.{rural,urban}`), labelled `estimated`. The SUT has GFCE only on paddy and wheat among food products, so where NAS books these is an open NAD question (§6).
4. Checks: S8 total vs Union food subsidy 2,11,814.39 (ratio 0.774; the cash subsidy includes FCI economic cost and storage, so it is a cross-check only); HCES-valued free grain (A10SW modal prices × HCES persons: rice 1,04,112, wheat 36,392) vs SUT GFCE (rice 0.98×, wheat 1.72×).
5. *Indicative*: H_R1 29,891; H_R2 29,792; H_R3 28,147; H_R4 26,089; H_R5 20,829; H_U1 10,164; H_U2 7,539; H_U3 5,596; H_U4 3,972; H_U5 1,953. S8 is never added to PFCE or to household income inside the SAM (D0-5).

### 2.8 hh_keys and companion satellites: method

- `hh_group_map` (24 rows): fractile class → SAM group, with persons and households (A2).
- `hh_hces_items`: every leaf item + 539 by group, ₹ crore/yr at HCES scale (≈ 3,740 rows), with dims `hces_item`, `item_role`, `hces_group`. Consumers pick items (e.g. R16 fees: 405, 413, 899; R12a: air fare 503, foreign-travel proxies).
- `hh_keys`: one row per key × group × measure, series_id `<key>.<level|share>.<h_r1…h_u5>`, dims `household_group` (H_R1…), `key`, `measure`, `basis_period` (`2023-08/2024-07`, `2018-06-30` or `2023-24`). Store **levels** (count, ₹ crore) and **shares** (unit `ratio`). Shares are rounded to 6 decimals on write, which is coarse for tiny shares (rural rent paid in H_R1 is 0.05%): consumers should normalise the levels themselves; a framework helper would help (§4.1).
- `hh_state_xwalk`: State × R/U × State fractile class → national SAM group weights (for R11a and R10; gap-map C1/B9 fix). National fractile boundaries are **not published** (A2 gives class means only), so estimate each national quintile cut-off as the log-midpoint of the adjacent class means (e.g. rural 20% cut = √(2,473.14 × 2,833.26)); assign each State cell (`a2.hces2324.{persons,avg_mpce}.in-xx.<class>`) by its mean MPCE, splitting a cell across two groups only when its own log-midpoint range (to its neighbouring State classes) straddles a cut, linearly in log-MPCE. Nominal MPCE, no spatial deflator (stated). Status estimated, low.
- `c1a_hces_nas_ratio`: HCES-scale value vs SUT PFCE by commodity (items that key several products split in proportion to those products' SUT PFCE), so the site can show the H1 gap by commodity (gap-map C1a note).

---

## 3. Constraints to declare

All `kind="equal"` unless stated; prov = a `derived` record whose inputs are the clean prov_ids listed. Production also declares C1 targets; duplicates with the same target are fine, conflicting ones are an error, so **agree the ids and targets with production** (§4.1). Proposed ids use the `hh.` prefix unless production's ids are adopted.

| constraint_id | ref | rows | cols | refs | target (source series) | tol | description |
|---|---|---|---|---|---|---|---|
| `hh.c1.c_crop` … one per commodity (31) | C1a (C4a for C_DWEL, C4b for C_FINS/C_INSR, C4d for C_HLTH/C_EDUC) | [C_x] | H_R1…H_U5 | null | Σ `use.pfce.sut_pNNN.current` over the products of C_x (below) | tol_abs 0.01 | SUT PFCE of C_x = Σ over the 10 groups |
| `hh.c1.total` | C1a | all 34 C_* | H_R1…H_U5 | null | `s1_1.pfce.current` 1,64,15,546.524761 (prov `mospi_nas_2026:c13be7d6469b`) | tol_abs 1.0 (SUT sum is 1,64,15,547.0; 0.475 is rounding) | NAS 1.1 PFCE = all COM → H_* |

Commodity targets (Σ of the SUT products; product lists from the committed concordance): C_DWEL 21,48,044 [144]; C_CROP 15,70,714 [1–9, 11–13, 17–27]; C_FOOD 15,54,744 [52–64, 67, 68]; C_LVST 14,65,644 [28, 30–35]; C_RPET 11,21,150 [85, 86]; C_FINS 8,52,794 [142]; C_TXAP 7,43,943 [70–78]; C_TRNS 7,02,280 [135–139]; C_TREQ 6,44,554 [120–122, 124]; C_EDUC 6,37,855 [152]; C_OSRV 5,72,342 [154, 155]; C_HLTH 4,93,394 [153]; C_HOTL 4,83,183 [134]; C_BVTB 3,92,576 [65, 66, 69]; C_PHRM 3,51,156 [92]; C_FOFI 3,38,854 [37, 39–41]; C_CHEM 3,06,416 [83, 84, 91, 93]; C_UTIL 3,06,092 [128, 130, 131]; C_COMM 2,64,200 [141]; C_INSR 2,55,939 [143]; C_WOOD 2,50,145 [79–82]; C_BSRE 2,11,064 [145, 148, 149]; C_ELEQ 1,89,901 [109, 111–117]; C_CNST 1,80,474 [127]; C_PADM 1,76,293 [151]; C_TRAD 75,321 [133]; C_MACH 62,244 [102–108]; C_GJOM 25,054 [126]; C_NMMN 21,389 [96, 97]; C_ITSV 15,997 [150]; C_COAL 1,791 [42]. Sum 1,64,15,547.

Wanted but **not expressible** with the current constraint schema (no component filter; FRAMEWORK_REQUESTS item, §4.1):

| constraint | target | why it matters |
|---|---|---|
| `hh.c4b.fisim` = Σ C_FINS ← H_* components `fisim_*` | 6,02,896.961538 (`s1_13.private_final_consumption_expenditure.current`) | official FISIM total, used by fincorp's R4/R5 adjustment |
| `hh.c4a.govt_housing` | 20,056.0 (`supply.output.sut_p144.sut_i67.current`) | official (derived) size |
| `hh.c4a.imputed_rent` band ±10% | the derived imputed total | keeps F3a (income) and C4a (consumption) consistent after balancing |

No group-level constraint is declared: there is no official total for any household group (HCES levels are 44% of NAS and are used for shares only). The group accounts close through K4a (closure).

---

## 4. Interfaces

### 4.1 Needs

From **production** (DEPENDS): (a) that it writes no COM → H_* entries (it cannot: there is no single household account) and declares C1 per commodity with the same targets and ids as §3 (production's brief says "C1 … final uses by commodity"); (b) that both blocks aggregate with the same concordance `io_tables_sut_product_to_sam34` and exclude the two SUT PFCE memo series. Nothing else numeric: households reads SUT and NAS series directly from clean data.

From the **framework** (FRAMEWORK_REQUESTS.md candidates):
1. A `components` filter on constraints (for the three constraints in the second table of §3).
2. Confirmation that a ref may be implemented only by a satellite (C4c memo), or guidance to list it in `refs_not_implemented`.
3. `hh_keys` is not a gap-map ref, but `Satellite.ref` must be in REFS: confirm `ref="C1a"` is the intended convention for `hh_keys`, `hh_hces_items`, `hh_group_map`, `hh_state_xwalk`, `c1a_hces_nas_ratio`.
4. A helper to read a satellite key and normalise its levels to shares (avoids 6-decimal rounding of small shares), e.g. `ctx.hh_share(key)`.
5. A decision on linking C4a `imputed_rent` (households) with F3a (factors) after balancing: either a band constraint (above) or an equality-link constraint type (x_e1 = x_e2 by group), otherwise balancing can move them apart.
6. Where the new committed concordance lives: I assume `data/concordance/hces2324_item_to_sut_product.csv` (read with `ctx.concordance`); the orchestrator should confirm, since `data/concordance` so far only holds Phase 1 files.

No needs from factors, taxes, government, fincorp, rest_of_world or closure (they all depend on households).

### 4.2 Publishes

| Output | Contents | Consumers (ref) |
|---|---|---|
| Entries C1a, C4a, C4b, C4d | ≈1,230 entries COM → H_* | assemble; closure (PFCE by group for K4a, D1 allocation base) |
| `hh_group_map` | fractile class → group; persons, households | all household-keyed blocks |
| `hh_keys` | `pop_persons`, `pop_households`, `hces_total` (A2 persons × MPCE), `hces_food` (981), `hces_nonfood` (984), `hces_durables` (983), `pfce_total` (sum of this block's entries), `c4a_actual_rent`, `c4a_imputed_rent`, `c4a_govt_housing`, `c4b_fisim_deposits`, `c4b_fisim_loans`, `c4b_explicit_fees`, `c4b_insurance_service`, `aidis_fin_assets`, `aidis_cash_loans`, `aidis_inst_loans`, `aidis_fixed_assets`, `aidis_valuables`, `aidis_total_assets` (AIDIS mapped by cumulative household overlap; level = per-hh value × HCES 2023-24 households, basis 2018-06-30), each as level and share | factors: F1a/F2 (persons, households, MPCE), F3a (`c4a_imputed_rent`), F3b (actual-rent total; landlord key from `aidis_fixed_assets`/`aidis_total_assets`, never the tenant key), F3c; fincorp: R8a (`aidis_fin_assets` scaled to T52(b) stocks), R4/R5 (`c4b_fisim_*`), R9c, R17 (`c4b_insurance_service` for the service-charge exclusion); taxes: T3a fallback (`hces_total`, top groups); government: R9a, R16 (items 405, 413, 899 via `hh_hces_items`); capital_financial: S5 (AIDIS keys) |
| `hh_hces_items` | all leaf items + 539 × group, HCES scale | government R16; rest_of_world R12a; taxes P7a/P7b priors (PFCE × item GST rate uses item detail) |
| `hh_state_xwalk` | State × R/U × State fractile → group weights | rest_of_world R11a; government R10 |
| `s8_food_stik` | S8 by group × grain (+ State free-item memo) | site "who benefits" story; government (C2a cross-check) |
| `c4c_npish_memo`, `c1a_hces_nas_ratio` | memo/diagnostic | methodology page, BALANCING.md |

Interface warnings to pass on: (1) fincorp must record SNA interest net of FISIM (R4 = actual interest received + FISIM on deposits; R5 = actual interest paid − FISIM on loans), otherwise C4b double counts; (2) government's R16 (fees, fines) must exclude fees the SUT already records as PFCE on public administration (C_PADM 1,76,293) and education/health fees in C4d; (3) factors' government-employee CE should include CE in kind that finances `c4a_govt_housing` (20,056).

---

## 5. Conflicts and choices

### 5.1 Where official sources disagree

| Item | Source A | Source B | Control | Cross-check / note |
|---|---|---|---|---|
| PFCE total | SUT Σ products 1,64,15,547.0 (`use.pfce.total.current`) | NAS 1.1 `s1_1.pfce.current` 1,64,15,546.52 (also 1.12 and 1.14 households incl. NPISH) | SUT for cells; NAS 1.1 for `hh.c1.total` with tol 1.0 | eSankhyiki API equals 1.1 (GDP-8 agree) |
| PFCE concept | SUT product rows (national) | NAS 5.1/5.2 COICOP, domestic market 1,64,70,321.26 (= national + 2,80,977.78 non-resident − 2,26,203.05 resident abroad) | SUT | 5.1 COICOP only as checks; never add the SUT memo rows |
| Dwellings | SUT PFCE p144 21,48,044; supply i57 21,27,988.47 + i67 20,056 | NAS 8.13 ownership of dwellings output 21,27,988.47 (agrees with i57); NAS 5.1 "gross rentals, equipment and material for housing" 22,83,027.68 (broader: includes COICOP 04.3 repair materials) | SUT | 8.13 agrees exactly; 5.1 not comparable |
| Financial services | SUT p142 8,52,794 | NAS 5.1 financial services 8,42,538.01 (domestic); FISIM 6,02,896.96 in both 1.13 and 5.1 | SUT for C_FINS; NAS 1.13 for the FISIM component | +10,256 is the national/domestic bridge (not verified) |
| Insurance | SUT p143 2,55,939 | NAS 5.1 2,50,365.45 | SUT | as above |
| Health / education | SUT p153 4,93,394; p152 6,37,855 | NAS 5.1 health services 4,91,886.01; education 6,37,855.06 | SUT | |
| Food STiK | SUT GFCE paddy 1,01,441.21 + wheat 62,530.54 = 1,63,971.75 | Union Exp. Profile St 7 food subsidy 2,11,814.39 (Actuals, cash); HCES-imputed value 1,40,504 (HCES scale) | SUT (same value C2a writes) | Implied GFCE unit value for wheat (₹50.5/kg) is 1.77× the HCES modal price (₹28.6/kg rural) while rice is ~1.0×: HCES probably under-reports free wheat, or SUT wheat GFCE carries other costs. Logged, not forced |
| Imputed rent R/U split | HCES 539: 27.0% rural | AIDIS proxy: building value/hh × households (22% × 15,92,379 × 193.8 mn rural vs 38% × 27,17,081 × 97.9 mn urban) ≈ 40% rural | HCES (reference-year, same groups, MoSPI's own imputation and very likely the NAS input: confirm in S&M 2026 dwellings section) | AIDIS variant published as a sensitivity; ≈ ₹2 lakh cr moves between rural and urban groups |
| Household consumption distribution | this method (*indicative*): rural 51.8% of PFCE; H_R5 + H_U5 39.8% | IFPRI 2022/23 SAM T11 (old base; national quintiles): rural 57.2%, Q5 41.6% | this method | IFPRI is a plausibility band only; the rural gap is mostly the imputed-rent split |
| Household deposits and loans | AIDIS 2019 per-household stocks (30.06.2018) | RBI T52(b) stocks 31.03.2024 | RBI for levels and deposit/loan weights | AIDIS for distribution only |
| HCES aggregate | Σ leaf items = 72,74,438 | A2 persons × MPCE = 72,74,444 | A10F leaves for item keys, A2 for `hces_total` | rounding (hces_consumption-4/-5) |

### 5.2 Method choices made here (and why)

1. **SUT-product-level keys** (not commodity level): the SUT product mix within a commodity must weight the keys (2.2 step 7).
2. **Imputed rent from HCES 539**, not the gap-map AIDIS fallback: HCES 2023-24 now publishes MoSPI's imputation by fractile; AIDIS has no owner-occupied dwelling values by class (only all buildings / all fixed assets, 2018).
3. **Dwelling sizes from the SUT supply matrix** (government housing is i67 output, 20,056), actual vs imputed from the HCES ratio.
4. **FISIM split by stock weights** and AIDIS keys mapped by cumulative-household overlap.
5. **C4c embedded** + memo; no separate entries.
6. **S8 at uniform GFCE unit values** (quantity shares); A10SW R/U prices only for the unscaled State-scheme memo.
7. **Item 282 (meals as assistance) excluded** from the C_HOTL key: government-provided meals are STiK in GFCE. Part may be NPISH/temple meals (which belong in PFCE); the key effect is small and it is logged.
8. **Store key levels, not only shares**, in satellites.

---

## 6. Risks, gaps, open questions

**Double-counting risks (each needs a test, §7):**
1. SUT PFCE memo rows (−2,80,978 / +2,26,203) added to product rows.
2. The same commodity written under two refs: C_DWEL only C4a; C_FINS/C_INSR only C4b; C_HLTH/C_EDUC only C4d; everything else only C1a. HCES items 520, 539, 405–408, 411–414, 421–424 must not appear in any C1a key.
3. C4c written as extra entries (NPISH already inside SUT PFCE).
4. Free PDS grain in PFCE or household income: HCES 061–075 excluded from keys; S8 stays a satellite; GFCE on grain belongs to C2a.
5. Jewellery 640–643 in PFCE (it is valuables, I2/I2a → K_HH).
6. FISIM counted as both consumption (C4b) and unadjusted interest (fincorp R4/R5).
7. Insurance: premiums of life insurance/PF are financial (I_INPE); only the service charge is PFCE; non-life net premiums/claims (R17) must exclude the service charge.
8. Fees: C_PADM PFCE (1,76,293) and education/health fees (C4d) vs government R16 fees and fines.
9. Government housing: PFCE (C4a) financed by CE in kind (factors) is correct once; it must not also appear as a government transfer.
10. Land rent (HCES 522) is D45 property income, not PFCE.
11. Owner-occupier minor repairs (HCES 632) key C_CNST PFCE (SUT puts 1,80,474 there); NAS treats owner-occupier repairs as intermediate consumption of dwellings. Here it is only a key; flag for NAD.

**Gap-map methods that cannot be followed as written, and the fallback:**
- C4a primary source AIDIS 2019 (owner-occupier value shares) → HCES 539 memo (better); government-housing key (government-employee CE) → HCES 520 (cycle with factors).
- C4b insurance key (HCES premium items: none exist) → AIDIS financial assets (low), HCES non-food as sensitivity. "AIDIS scaled to NAS 5.3 stocks": 5.3 has flows, not stocks → RBI T52(b) stocks.
- C4c written as spread entries → embedded (double count otherwise).
- C4d checks "if unit data are granted" → published tables only, directional.
- S8: GFCE unit value is not published → implied from SUT GFCE ÷ HCES quantities (equivalent).
- R11a/R10 national placement needs national fractile boundaries, which are not published → log-midpoint estimate in `hh_state_xwalk`.

**Data risks and open questions:**
1. **H1 (HCES ≈ 44% of NAS):** uniform scaling within product assumes the gap is distribution-neutral; the literature says it is concentrated at the top. Optional satellite variant `c1a_top_heavy` (e.g. assign the non-food gap disproportionately to H_R5/H_U5) for the band the gap map promises; the exact rule needs an owner decision at Checkpoint B.
2. **AIDIS quintile anomaly:** in both sectors the top AIDIS class has *lower* assets and loans per household than class 4 (rural assets 17.1 vs 23.9 lakh; urban 30.9 vs 42.4 lakh; loans likewise). The labour verifier's census matched every API value to the pinned raw JSON, so they are as served, but the pattern is implausible. Ask the labour unit to check the API class order against AIDIS Report 588 (still not located). It affects C4b and every AIDIS key. All AIDIS-based entries are `low`.
3. AIDIS classes are 2018 household quintiles of AIDIS's own expenditure measure, mapped to 2023-24 person quintiles by household overlap (labour_enterprise_surveys-21).
4. HCES population 1,217.6 mn vs NAS-implied ~1,395 mn: shares are fine; per-capita stories need a population control that is not ingested (RGI projections).
5. HCES 071–075 (State free pulses, gram, salt, sugar, oil) and 070 coarse grains: no SUT GFCE line holds them. Where does NAS book them? (NAD question; tiny).
6. Item 282 classification (government STiK vs NPISH vs PFCE): NAD question.
7. HCES 539 methodology (how MoSPI imputes rural rent; whether NAS uses it): confirm from S&M 2026 before Checkpoint B.
8. FISIM on housing and enterprise loans is intermediate consumption in NAS, not PFCE; AIDIS cash loans do not separate purpose by class. Deposit-only key as a sensitivity.
9. Proxy keys (low): C_PADM (899), C_BSRE p149 (027, 497), C_ITSV (622, 496), C_TRAD p133 (vehicle fuel), C_MACH, C_NMMN, C_CNST (632), C_UTIL p131 (540), p113 communication equipment (SUT 2,318 vs HCES mobile handsets 44,060: SUT probably books phones in p115).
10. Balancing can separate C4a imputed rent from F3a income (framework request 5).
11. Satellite share precision at 6 decimals (hces_consumption-12 analogue): store levels.
12. The HCES 2022-23 validation SAM (optional) can reuse the code with period `2022-08/2023-07`, but A10SW does not exist for 2022-23 (hces_consumption-17), so S8 memo rows cannot be valued that year; the scaled S8 still works.
13. IFPRI is old base, national quintiles, and its household saving split is assumed (ISSUES line 491): cross-check only.

---

## 7. Tests the builder should write

Every expected value is read from clean data in the test (never typed in). Suggested file `tests/sam/test_households.py`; marker `sam`.

**Official totals the block must reproduce**
1. For each of the 31 commodities, Σ_g entries (C_x ← H_g, all refs) = Σ `use.pfce.sut_pNNN.current` over its products (concordance), |diff| ≤ 0.01.
2. Σ all COM → H_* entries = `use.pfce.total.current` (≤ 0.01) and = `s1_1.pfce.current` and `s1_14.households_npish.final_consumption_expenditure.current` (≤ 1.0).
3. Σ product series = `use.pfce.total.current`, and the two memo series `use.pfce.purchases_nonresidents_domestic.current` / `use.pfce.purchases_residents_abroad.current` are not among the block's provenance inputs.
4. C4a: component `govt_housing` total = `supply.output.sut_p144.sut_i67.current`; `actual_rent` + `imputed_rent` = `use.pfce.sut_p144.current` − that (and within 0.5 of `s8_13.ownership_of_dwellings.output.current`); C_DWEL total = `use.pfce.sut_p144.current`; actual/(actual+imputed) = HCES V_520/(V_520+V_539) to 1e-9.
5. C4b: `fisim_deposits` + `fisim_loans` = `s1_13.private_final_consumption_expenditure.current`; + `explicit_fees` = `use.pfce.sut_p142.current`; C_INSR = `use.pfce.sut_p143.current`; deposit weight = (T52b bank + non-bank deposits)/(those + `t52b.fl.current`).
6. C4d: C_HLTH = `use.pfce.sut_p153.current`; C_EDUC = `use.pfce.sut_p152.current`.
7. S8: Σ_g rice = `use.gfce.sut_p001.current`; Σ_g wheat = `use.gfce.sut_p002.current`; `ctx.check` against `stat7.food.food_subsidy` recorded (not asserted equal).

**Structure and double counting**
8. Refs per commodity: C_DWEL only C4a; C_FINS/C_INSR only C4b; C_HLTH/C_EDUC only C4d; all others only C1a; no entries on C_OILG, C_OMIN, C_MTLS; no entry uses SUT product 125; no C4c entries; no zero-valued entries.
9. Key concordance: only `item_role=leaf` codes (plus 539 in C4a); none of 640–643, 061–075, 282, 520, 539, 522, 405–408, 411–414, 421–424 in any C1a key; every leaf item is used or explicitly excluded; every PFCE product except 142–144, 152, 153 has a non-empty key.
10. Group definition: Σ persons over the 10 groups = Σ of the 24 A2 class rows (1,217,643,800); each rural group holds 20% ± 0.01 pp of rural persons, each urban group 20% ± 0.01 pp of urban persons; `hh_group_map` has 24 rows, each class in exactly one group.
11. For every product, Σ_g share = 1 (1e-12) and every share ≥ 0; entries / PFCE_p equal the HCES shares recomputed independently from A10F × A2.
12. Survey window: every HCES input row has period `2023-08/2024-07`; the survey-window assumption record is an input of every HCES-keyed record.

**Satellites**
13. `hh_keys`: for each key, shares sum to 1 (1e-5) and equal level/Σ level; `pop_persons` levels equal A2; `c4a_*` and `c4b_*` levels equal the block's own entries by group; AIDIS overlap weights sum to 1 per AIDIS class and per SAM group range.
14. `hh_state_xwalk`: for each State × R/U, weights over groups sum to 1 per State class; Σ over States of persons assigned to each group is reported against the national group persons as a `ctx.check` (the gap is informative, not an error).
15. `c4c_npish_memo` share equals ICIO NPISH / (NPISH + HFCE) recomputed from `io_tables_icio_india`.

**Plausibility (`ctx.check`, recorded; fail only if wildly off)**
16. Rural share of total PFCE in [45%, 62%] (IFPRI 57.2%, *indicative* 51.8%); H_R5 + H_U5 in [30%, 50%] (*indicative* 39.8%).
17. Engel: food share (C_CROP + C_FOOD + C_LVST + C_FOFI) of each group's PFCE falls from Q1 to Q5 within each sector.
18. S8 per person falls from H_R1 to H_R5 and from H_U1 to H_U5.
19. HCES/NAS ratio by commodity (`c1a_hces_nas_ratio`) between 0.05 and 1.5 for every commodity with a direct key (flags mapping errors).

Provenance: every entry, constraint and satellite row has a `sam_households:` prov_id; every `estimated` record has a method naming the gap-map ref, the key items and the assumption.

---

## Appendix A. Draft SUT product → HCES 2023-24 A10F leaf-item keys (scout's draft; tested in scratch)

"proxy" = low confidence. Codes are A10F item codes (`hces:NNN`). The draft covers all 116 C1a/C4d products; total written reproduces their PFCE, 1,31,58,770. Unplaced leaf items: 470, 471, 633, 523.

| SUT product(s) | Key items | Note |
|---|---|---|
| 1 paddy, 60 rice (mill) | 101, 102, 103, 105, 106 | purchased PDS (101) included; free rice 061 excluded |
| 2 wheat, 58 wheat (mill) | 107, 108, 110, 111, 112, 114 | |
| 3 coarse cereals | 001, 002, 122 | 61 others (mill): same + 012 breakfast cereals |
| 4 gram; 5 arhar; 6 other pulses | 141, 142; 140; 143–146, 148, 158 | 59 pulse (mill): 140–148, 150, 152, 158 |
| 7 groundnut; 8, 9 oilseeds (proxy) | 241; 260 | |
| 11 sugar crop (proxy); 12 coconut; 13 tobacco leaf (proxy) | 173; 224, 225, 240; 312 | |
| 17 mango; 18 banana; 19 citrus & grape; 20 other fruit | 231; 220; 216, 228, 237; 008, 010, 221–223, 226, 227, 230, 232–236, 238, 242, 243, 245–247 | |
| 21–25 vegetables | 200; 201; 202; 211, 212; 203–206, 208, 210, 213–215, 217 | |
| 26 spices; 27 other food crops (proxy) | 207, 250–257, 261, 263; 139, 300, 302 | |
| 28 milk; 30 egg; 31 poultry; 32 beef; 33 mutton; 34 other meat; 35 other livestock products (proxy) | 160; 190; 195; 193; 192; 194, 196; 333, 175 | 52 processed poultry: 195; 53 processed meat: 192–194; 54 processed fish: 191 |
| 37 firewood; 39–41 fish | 331, 341; 191 | |
| 42 coal | 337 | |
| 55 processed fruit & veg; 56 dairy products; 57 edible oils | 294, 295; 003, 005, 006, 007, 161–167; 180–185, 188 | |
| 62 sugar, gur; 63 bakery; 64 misc. food | 171–174, 004; 013, 113, 290; 014, 015, 170, 178, 258, 278, 291–293, 296 | |
| 65 alcohol; 66 non-alcoholic; 67 tea; 68 coffee; 69 tobacco products | 320–325; 011, 274–276; 271; 273; 301, 310, 311, 313–317 | |
| 70–73 textiles; 74 carpets; 75 garments; 76 misc. textiles; 77 footwear; 78 leather products | 350–353, 371, 380 (70); 351–353 (71); 355, 374, 381 (72); 351 (73); 555; 030–034, 354, 356–358, 360–368, 370, 372, 373, 375; 382–386, 472; 390–395; 553, 554 | |
| 79 wood (proxy); 80 paper; 81 printing; 82 furniture | 550–552, 557; 022, 404, 456, 462; 400–402; 550–552, 557, 383 | |
| 83 rubber; 84 plastic; 91 paints (proxy); 93 soaps & cosmetics | 603, 393, 423; 050, 018, 451, 464; 632; 016, 017, 020, 021, 450, 452–455, 457, 465–467 | |
| 85 petroleum products; 86 coal tar (proxy) | 512, 513, 338, 334, 335, 340, 344–346; 337, 346 | LPG and vehicle fuel dominate |
| 92 drugs & medicines | 410, 420 | C1a, not C4d |
| 96 cement (proxy); 97 non-metallic (proxy) | 632; 463, 573, 630 | |
| 102–108 machinery (proxy) | 442; 570–572, 586, 587; 600–604; 621; 621; 621; 584, 590, 592, 582 | |
| 109, 111–117 electrical/electronic | 582; 461; 043–048, 580, 581, 585, 588, 591, 592; 623, 624 (proxy); 023, 460, 583, 631; 035, 560, 562, 564, 622, 625; 040–042, 440, 561, 610, 611; 620 | |
| 120 cars; 121 two-wheelers; 122 bicycles; 124 other | 602; 601; 600; 604 | |
| 126 misc. manufacturing | 036, 037, 097, 432, 441, 556, 563, 468, 342, 336 | |
| 127 construction (proxy) | 632 | |
| 128 electricity; 130 water; 131 other utility (proxy) | 332; 540; 540, 343 | |
| 133 vehicle repair (proxy) | 512, 513 | |
| 134 hotels & restaurants | 076, 270, 272, 280, 281, 283, 284, 521 | 282 excluded |
| 135 rail; 136 road; 137 air; 138 water; 139 support (proxy) | 024; 025, 500, 501, 504–506, 508, 510, 511, 514; 503; 026; 497 | |
| 141 communication | 437, 487, 488, 490, 496 | 437 cable/DTH could be p155 |
| 145 real estate (proxy); 148 legal; 149 business services (proxy); 150 IT (proxy); 151 public administration (proxy) | 520; 493; 027, 497; 622, 496; 899 | |
| 152 education (C4d); 153 health (C4d) | 405, 406, 408; 411–414, 421, 422, 424 | |
| 154 community & personal; 155 recreation | 027, 435, 480–486, 492, 494, 495, 497; 028, 430, 433, 438 | |

## Appendix B. Indicative results of the scratch prototype (for orientation only)

Full PFCE by group (C1a + C4a + C4b + C4d; C1a/C4d at product level, C4a and C4b as in 2.3–2.4), ₹ lakh crore and % of 1,64,15,547: H_R1 7.82 (4.8%), H_R2 11.23 (6.8%), H_R3 14.46 (8.8%), H_R4 19.00 (11.6%), H_R5 32.50 (19.8%), H_U1 6.28 (3.8%), H_U2 9.56 (5.8%), H_U3 12.91 (7.9%), H_U4 17.63 (10.7%), H_U5 32.77 (20.0%). Rural 51.8%. Selected HCES key shares by group (%, H_R1…H_R5, H_U1…H_U5): rent paid 0.05, 0.18, 0.37, 1.31, 7.54, 1.97, 5.21, 10.07, 18.19, 55.08; imputed rent 1.21, 2.22, 3.41, 5.90, 14.24, 7.43, 10.41, 12.83, 16.36, 25.99; free rice (quantity) 18.47, 17.68, 16.58, 15.62, 13.05, 5.87, 4.56, 3.70, 2.94, 1.52.

---

## 8 Cross-plan review (2026-09-30, cross-plan critic; details and ids in `CROSS_REVIEW.md`)

What this block must change or confirm:

1. **XR-5 FISIM split, one source.** Compute the deposit/loan split of PFCE FISIM (6,02,896.96) with fincorp's reference-rate formula: FISIM_D ∝ (r* − r_D)·D and FISIM_L ∝ (r_L − r*)·L, with r* = 6.7% (SCB return on investments), r_D = cost of deposits 4.8% and r_L = return on advances 9.4% (`rbi_banking_corporate_rtp_banks` `rtp.scb_cost_return.*`, vintage 2025-12-29), on the same T52(b) stocks. Record r* once, as an assumption record. Publish the parameters as `fisim_params` in `hh_keys`. fincorp will read your C4b `fisim_deposits` / `fisim_loans` group entries as the household FISIM_D / FISIM_L, so the two blocks can no longer disagree by group. The stock-weight split (0.5412 / 0.4588) becomes a logged sensitivity.
2. **XR-10 publish the keys consumers need, under the names in CROSS_REVIEW §4.3:**
   - `hh_national_quintile_xwalk`: SAM group × national MPCE quintile, person shares. factors uses it for the IFPRI priors in F1a/F2/F3c and taxes for the IFPRI saving rates in T3a. You already estimate the national cut points for `hh_state_xwalk`.
   - `avg_mpce` per class in `hh_group_map` (taxes T3a).
   - HCES consumption **levels** in `hh_state_xwalk` (rest_of_world R11a, government R10).
   - `aidis_noninst_loans` (capital_financial S5).
   - `aidis_deposits`, `aidis_equity`, `aidis_mf`, `aidis_small_savings` = `aidis_fin_assets` × AIDIS press-note R/U asset-class shares, labelled low (fincorp R8a).
   - Life insurance uses `aidis_fin_assets`; non-life premiums use `c4b_insurance_service` shares. State in the satellite description that HCES has no premium item.
3. **XR-15 do not re-declare production's `pfce.*` constraints** with tol 0.01. Production's targets are identical and carry tol_abs = ₹1 × SUT cells (FRAMEWORK_REQUESTS deviation 1); a tighter duplicate wins and removes the rounding allowance. Keep the per-commodity equality as a **test** against `ctx.block_constraints("production")`, and keep `hh.c1.total` (NAS 1.1, tol 1).
4. **XR-20 declare the constraints you marked "not expressible"**, since the components filter now exists:
   - `hh.c4b.fisim` = 6,02,896.96 (components `fisim_deposits`, `fisim_loans`);
   - `hh.c4a.govt_housing` = 20,056;
   - an imputed-rent band.
5. **XR-22 imputed rent link:** factors will declare per-group F3a bands from your `c4a_imputed_rent` shares. Publish those shares at ≥ 9 decimals, or as levels.
6. Confirmations requested by other plans:
   - no COM → H_* entries by production (confirmed from the built block);
   - C4c as a memo satellite is accepted (FRAMEWORK_REQUESTS P-7);
   - `ref="C1a"` for `hh_*` satellites is accepted (P-8);
   - the new concordance `data/concordance/hces2324_item_to_sut_product.csv` needs orchestrator approval (CROSS_REVIEW D-12).
7. Nothing else conflicts. Your exclusions (jewellery, free grain, item 282, land rent 522, SUT memo rows) match taxes, government, capital_financial and timeseries.
