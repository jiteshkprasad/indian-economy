# Phase 2 plan: block `factors` (FY 2023-24)

Written 2026-09-30 by the factors data scout and method planner. This is research only: nothing under `pipeline/` was written and no `pipeline build`/`sam`/`repro` was run. Every number was read from `data/clean/<unit>/*.parquet` with polars (scratch scripts outside the repo), or is arithmetic on such numbers. Rows marked *indicative* are my own trial computation of an **estimate**, given only to show magnitudes and to set test bands. The builder recomputes them, and a different agent verifies them. Amounts are ₹ crore, current prices, FY 2023-24, new base 2022-23, NAS 2026 vintage (2026-08-31, stage `Final`) unless stated.

Refs owned: V1a V2a V3 V4 F1 F1a F2 F3 F3a F3b F3c F4 F4b. F4a (the FC sub-sector split) belongs to `fincorp`. `factors` only declares the FC GOS total as a constraint. Depends on: `production`, `households`.

---

## 1 Summary

- **What the block does.** The SUT fixes value added by activity: wages (CE) and profits (OS/MI + CFC), fixed and official. The factors block decides three things. (a) How each activity's wages split between **regular-salaried** and **casual** labour. (b) How its profits split between **mixed income** of the self-employed and **operating surplus**, meaning companies, government, household-owned dwellings and household partnerships or trusts. (c) Who receives the income: which of the 10 household groups, which company sectors, and Centre or States.
- **The sector totals are official and close exactly.** NAS 7.1A, 7.1B, 7.1C, 8.15.1 and 1.14 give gross operating surplus (GOS) as follows. Public NFCs 11,67,179.33. Private NFCs 46,19,027.77. Financial corporations 10,86,708.96. General government 3,75,679.16. Households' gross OS/MI 97,71,430.53. These add up to the SUT's 1,70,20,025.77 (a difference of ₹0.01 cr). Labour income to households is 94,74,604.95 (NAS derived row).
- **Everything below the sector line is estimated from published tables only (no microdata, D1-2).**
  - Regular vs casual pay comes from PLFS status shares × earnings. Indicatively about 79% of CE is regular and 21% casual.
  - Mixed income vs dwelling rent vs partnership surplus comes from NAS 7.1C by industry group, plus ASUSE.
  - The rural/urban split comes from PLFS and ASUSE.
  - The split across quintiles within rural and within urban comes from IFPRI 2022/23: old base, national quintiles, **low confidence**.
- **Two findings for Checkpoint B.**
  - (1) The SUT puts 6,95,681 cr of CFC on dwellings, but the whole NAS household real-estate/professional group has only 4,92,818 cr of CFC. So dwelling ownership (household vs corporate) cannot be read from CFC. I recommend a GOS-level method (§2.2) and a question to NAD.
  - (2) NAS books almost all of group 9's production taxes (1,92,249 of 1,92,711) on the household sector, while the SUT spreads them pro rata (Q2). A_DWEL's SUT surplus is therefore probably overstated by roughly 1.2 lakh cr, and IT/business services understated by the same amount.
- **Where the gap-map method cannot be followed as written:**
  - V2a within-group keys come from ASUSE by RAS, not from SUT OS shares, because those are pro rata to GVA.
  - F1a, F2 and F3c quintile keys come from IFPRI, not PLFS unit data.
  - F3b uses an AIDIS asset proxy, because rented-out property is not published.
  - F4b's autonomous-bodies split uses only the Union side, because the States' side is not ingested.

---

## 2 Ref-by-ref table

Legend for roles: `fixed` never moves. `anchored` may move within `tol_rel`. `free` carries a confidence of high/medium/low. Status is `official`, `derived` or `estimated`, as in DESIGN_BRIEF §3. "H_g" means the 10 groups H_R1..H_R5, H_U1..H_U5.

| Ref | Cell (row ← col) | Entries to write | Source datasets / series (2023-24) | 2023-24 values | Role | Method (detail in §2.x) | Status label |
|---|---|---|---|---|---|---|---|
| **V1a** | F_LREG / F_LCAS ← A_* | 65 entries: F_LREG and F_LCAS for 32 activities, F_LREG only for A_PADM, none for A_DWEL (SUT CE = 0) | Targets: `io_tables_sut_va` `va.ce.sut_iNN.current` (prov `io_tables:d1e9110c5674`), aggregated by `data/concordance/io_tables_sut_industry_to_sam34.csv`, the same as production's V1 constraints. Keys: `labour_enterprise_surveys_plfs_industry_status` `t20.worker_share.{regular_wage,casual_labour}.<nic>.<r/u>.person` (2023-07/2024-06, `:78d16299f7f1`); `..._plfs_industry_dist` `t26.worker_share.<section>.<r/u>.person` (`:27f6407a21ac`); `..._plfs_earnings_api` `api_i6.regular_wage_earnings_month.<r/u>.person.current` Q1–Q4 2023-24; `..._plfs_earnings` `t51.casual_wage_day.<section>.<r/u>.person.current` (`:ecac3c87645e`); `..._plfs_lfs_indicators` `lfs.wpr.ps_ss.all.<r/u>.person` (`:71144ccdc694`); `..._asuse_2324_activity` `t33.emol_per_hired_worker.informal.asuse_all.total.current` (`:c670ee2fb2d2`); floor: `mospi_nas_2026_s7_1a` `s7_1a.<grp>.ce.current` (`:b032b9cee2f7`) | Σ CE = **94,42,896.46** (SUT 67 industries); NAS `s7_1.total.ce.current` 94,42,896.63. Per-activity CE in §2.1 table. *Indicative:* regular ≈ 74.3 lakh cr (78.7%), casual ≈ 20.1 lakh cr | `free`. A_PADM high (it is the only labour entry in its column, so V1 pins it). Services 58-99, trade, utilities and manufacturing: medium. Agriculture, mining, construction, transport, hotels: low | PLFS regular/casual wage-bill share by the 9 PLFS industry groups × R/U, applied to SUT CE by activity. Floor: regular CE ≥ public-sector CE (7.1A), except agriculture and construction. A_PADM 100% regular | `estimated` |
| **V2a** | F_MIXD / F_GOSC ← A_* | (F_MIXD, A_x, `mixed_income`) for activities with household MI. (F_GOSC, A_x) with components `corp_gov`, `hh_quasi`, `hh_dwelling_imputed`, `hh_dwelling_actual` | Targets: `io_tables_sut_va` `va.os_mi.sut_iNN.current` + `va.cfc.sut_iNN.current` (production's V2 constraints). Household anchor: `mospi_nas_2026_s7_1c` `s7_1c.<grp>.os_mi.current` + `s7_1c.<grp>.cfc.current` (`:97dbbe46cb26`). Keys: ASUSE `t4.establishments…` (`:ed5ce75f9169`), `t37.gva_per_estt…` (`:25c03090d0bd`), `t33.hired_workers…`/`t33.emol_per_hired_worker…`, `t6.estt_share.<ownership>…` (`:eff56354f323`), all 2023-10/2024-09; `s7_1c.real_estate_prof.ce.current` | Σ = **1,70,20,025.77** (SUT) = NAS 7.1 OS/MI 1,31,83,820.20 + CFC 38,36,205.56. Household gross OS/MI **97,71,430.53** (by group, §2.2). *Indicative:* F_MIXD ≈ 78 lakh cr; household dwellings ≈ 18.6 lakh cr; household partnerships/trusts ≈ 1.1 lakh cr | F_MIXD/`corp_gov` in single-activity groups (crops, livestock, forestry+fishing, utilities, construction, trade, hotels, transport, communication, finance, public admin): `anchored` 0.02. Multi-activity groups: `free` medium. `hh_dwelling_*`: `free` low. `hh_quasi`: `free` low | Household share by NAS group from 7.1C (exact). Within multi-activity groups, a 2-column RAS with ASUSE keys, except group 9, which uses a ratio method. Partnership/trust/cooperative share from ASUSE ownership. Dwellings are all F_GOSC | `derived` for single-activity splits; otherwise `estimated` |
| **V3** | F_LREG ← R_ROW | 1 entry | `mospi_nas_2026_s6_1` `s6_1.compensation_of_employees_from_rest_of_the_world.current` (`:9d4d0601fb96`). Cross-check `external_sector_bop_bpm6_annual` `bpm6.inr.bpm6_1_b_1.credit.current` (`:606677acd791`, vintage 2026-07-31) | **62,344.24** (BoP 62,344) | `fixed` | As published; 100% to regular labour (gap-map assumption: seafarers, mission staff) | `official` (factor assignment stated) |
| **V4** | R_ROW ← F_LREG | 1 entry | `s6_1.compensation_of_employees_to_the_rest_of_the_world.current`. Cross-check `bpm6.inr.bpm6_1_b_1.debit.current` | **30,635.91** (BoP 30,636) | `fixed` | As published; paid from F_LREG (gap-map assumption) | `official` |
| **F1** | H_* ← F_LREG+F_LCAS (total) | no entries (constraint only) | `mospi_nas_2026_derived_residuals` `derived.ce_receivable_by_residents.current` (`:78ca71e7034e`) | **94,74,604.95** (= 94,42,896.63 + 62,344.24 − 30,635.91) | constraint | Identity; the F1a entries must sum to it | `derived` (official total) |
| **F1a** | H_g ← F_LREG, H_g ← F_LCAS | 20 entries | R/U: by-product of V1a (PLFS). Within R/U: `io_tables_ifpri_2223_datapaper` `ifpri.t10.labour_{low,medium,high}_educated.q1..q5` (`io_tables:61932231baf1`) × `ifpri.t11.total_spending_per_capita.q1..q5` (`io_tables:4e231715d421`), period 2022-23, status `estimated`, old base. Groups and persons from households' `hh_keys` | Totals: F_LREG col = Σ V1a(reg) + 62,344.24 − 30,635.91; F_LCAS col = Σ V1a(cas) | `free` low | PLFS R/U wage bills per factor, then IFPRI per-capita labour-income gradients within R/U | `estimated` |
| **F2** | H_g ← F_MIXD | 20 entries (components `farm`, `nonfarm`) | R/U: PLFS `t20.worker_share.self_employed.<nic>.<r/u>.person`, `t26…`, `api_i8.self_employment_gross_earnings_30d.<r/u>.person.current`; ASUSE R/U (GVA − emoluments). Within R/U: IFPRI `ifpri.t10.crop_land.*`, `.capital_agriculture.*`, `.capital_non_agriculture.*` × T11. Cross-check: `labour_enterprise_surveys_sas_2019_income_by_landclass` `s5_1a.*` (2018-07/2019-06) | Total = Σ V2a F_MIXD (*indicative* ≈ 78 lakh cr) | `free` low | Farm MI: R/U by PLFS farm self-employment. Non-farm MI: R/U by ASUSE. Quintiles by IFPRI capital-income gradients | `estimated` |
| **F3** | H_* ← F_GOSC (total) | no entries (constraint on F2 + F3) | `s7_1c.total.os_mi.current` + `s7_1c.total.cfc.current` | F2 + F3 = **97,71,430.53** | constraint | F3 = household gross OS/MI − F_MIXD, so F_GOSC clears | `estimated` (the official total is on F2 + F3) |
| **F3a** | H_g ← F_GOSC (imputed rent) | 10 entries | Total = Σ V2a `hh_dwelling_imputed`. Key: households' imputed-rent key (the same one C4a uses; built from `hces_consumption_a6_group_fractile` `a6.hces2324.memo_imputed_rent.*` / `a10f` 'house/garage rent (imputed)') | *Indicative* total ≈ s_imp × 19,28,182.04 (s_imp from households) | `free` medium | Each group's imputed-rent income ∝ its imputed-rent consumption | `estimated` |
| **F3b** | H_g ← F_GOSC (actual rent to household landlords) | 10 entries | Total = Σ V2a `hh_dwelling_actual`. Key: households' AIDIS asset key (`labour_enterprise_surveys_aidis_2019_quintile` `i9.fixed_assets_per_hh.<r/u>_q1..q5.all.current`; press note `pn.asset_share_building.<r/u>.all`), stocks at 2018-06-30 | Residual of the household dwelling GOS | `free` low | Keyed by owners of property, not tenants (proxy: fixed assets) | `estimated` |
| **F3c** | H_g ← F_GOSC (partnerships, trusts, NPISH) | 10 entries | Total = Σ V2a `hh_quasi`. R/U: ASUSE non-proprietary GVA by R/U. Within R/U: IFPRI `capital_non_agriculture` gradient | *Indicative* ≈ 1.1 lakh cr | `free` low | ASUSE ownership shares × GVA/establishment | `estimated` |
| **F4** | E_NFPU, E_NFPR ← F_GOSC (entries); FC and GG totals (constraints) | 2 entries + 2 constraints | `mospi_nas_2026_s7_1a` (`:b032b9cee2f7`), `s7_1b` (`:0418737e2fef`), `s8_15_1` (`:9e4f45b4c032`), `s1_14` (`:052393d058c2`), `s8_16` (`:242a755578d6`) | E_NFPU **11,67,179.33**; E_NFPR **46,19,027.77**; FC constraint **10,86,708.96**; GG constraint **3,75,679.16** | NFC entries `fixed`; FC and GG are constraints | GOS = GVA − CE − net production taxes, sector by sector (§2.8) | `derived` |
| **F4b** | G_CEN, G_STA ← F_GOSC | 2 entries | `mospi_nas_2026_s4_1` `s4_1.{central_government,state_government,local_bodies,autonomous_institutions}.current` (`:b0ec75bad6fb`); `union_fiscal_fa_gia` `gia.cash.autonomous_bodies.total` − `gia.cash.autonomous_bodies.capital_assets` (vintage 2024-12-10, Audited) | Sum 3,75,679.16. *Indicative:* G_CEN 1,11,071.85 (29.566%), G_STA 2,64,607.31 | `free` medium; the sum is pinned by the GG constraint | Split pro rata to NAS 4.1 NVA, with central autonomous bodies' NVA proxied by Union revenue grants-in-aid | `estimated` |

### 2.1 V1a: regular vs casual CE by activity

**Targets (CE by activity, SUT 2023-24, `io_tables_sut_va`, summed with the committed concordance).** A_CROP 6,50,969.00 · A_LVST 29,037.00 · A_FOFI 47,428.00 · A_COAL 25,540.46 · A_OILG 28,570.80 · A_OMIN 54,328.62 · A_FOOD 93,576.01 · A_BVTB 34,474.47 · A_TXAP 1,12,251.59 · A_WOOD 69,407.17 · A_GJOM 34,584.98 · A_RPET 74,953.51 · A_CHEM 1,25,748.04 · A_PHRM 65,370.72 · A_NMMN 63,725.98 · A_MTLS 1,05,253.00 · A_MACH 1,28,218.07 · A_ELEQ 70,678.60 · A_TREQ 1,24,002.50 · A_CNST 11,96,040.00 · A_UTIL 68,978.00 · A_TRAD 4,54,020.00 · A_HOTL 1,28,236.00 · A_TRNS 3,04,153.00 · A_COMM 1,50,979.00 · A_FINS 5,08,700.79 · A_INSR 61,975.15 · A_DWEL 0.00 · A_BSRE 8,73,647.74 · A_ITSV 12,47,905.79 · A_EDUC 6,91,431.14 · A_HLTH 2,45,816.15 · A_OSRV 3,30,675.17 · A_PADM 12,42,220.00. Total 94,42,896.46.

**Steps.**
1. Read production's V1 constraint targets with `ctx.block_constraints('production')`. Assert that they equal the sums above to within ₹0.01 cr. The two blocks must not disagree.
2. Map the 9 PLFS Table (20) groups to activities, using `t26` sections to size them and `t51` sections for casual wages:
   - 01-03 (A): A_CROP, A_LVST, A_FOFI
   - 05-09 (B): A_COAL, A_OILG, A_OMIN
   - 10-33 (C): the 13 manufacturing activities
   - 35-39 (D+E): A_UTIL
   - 41-43 (F): A_CNST
   - 45-47 (G): A_TRAD
   - 49-53 (H): A_TRNS
   - 55-56 (I): A_HOTL
   - 58-99 (J–U): A_COMM, A_FINS, A_INSR, A_BSRE, A_ITSV, A_EDUC, A_HLTH, A_OSRV (A_PADM is handled separately, step 7)
3. Compute, for s ∈ {rural, urban} and group g:
   - workers_{g,s} ∝ WPR_s × pop_s × Σ_{sections∈g} t26 share_{sec,s}.
     - WPR (ps+ss, all ages, 2023-07/2024-06): rural 45.6, urban 38.9 (`lfs.wpr.ps_ss.all.<s>.person`).
     - pop_s is households' `population` key: HCES `a2.hces2324.persons.in.rural_all` 85,47,35,400 and `…urban_all` 36,29,08,000 (`hces_consumption:e5e8a3696a31`). Only the ratio is used.
   - Regular workers = workers × t20 regular share; casual workers = workers × t20 casual share.
   - Regular annual earnings E_s = 12 × mean of `api_i6.regular_wage_earnings_month.<s>.person.current`, Q1–Q4 2023-24. FY means: rural 16,488.03 and urban 23,618.60 per month.
   - Casual daily wage w_{g,s} = `t51.casual_wage_day.<sec>.<s>.person.current`, weighted by t26 section shares within g. Use `.total.` where a R/U cell is missing (log it). Examples: A 332/365, C 432/464, F 429/536, all-sector 392.07/501.05 (R/U).
4. Casual days per year: D = ASUSE informal emoluments per hired worker ÷ PLFS FY-mean casual wage = 1,25,910 ÷ 410.40 = **306.8 days**.
   - Write D as an `estimated` parameter record, stating the reason: "annual pay of informal hired workers expressed in casual-wage days".
   - Run a sensitivity at D = 250.
5. Compute share_reg_g = Σ_s Reg·E / Σ_s (Reg·E + Cas·w·D). *Indicative* values, computed by me: 01-03 0.106 · 05-09 0.805 · 10-33 0.900 · 35-39 0.961 · 41-43 0.103 · 45-47 0.946 · 49-53 0.818 · 55-56 0.856 · 58-99 0.987.
6. Apply the floor. For each NAS 7.1 group except agriculture and construction, regular CE must be at least the public-sector CE (`s7_1a.<grp>.ce.current`, e.g. mining 75,257.53, manufacturing 1,13,252.38, utilities 37,442.11, transport rows (railways + road + air + water + transport services + storage) 1,70,965.09, communication 39,999.16, other_services 8,09,359.58).
   - Agriculture and construction are excluded because government and departmental own-account construction (8.15.1 construction CE 45,850.08; 8.15.2 26,133.96) and departmental farms and forests can employ muster-roll or casual labour. MGNREGA is an open question (§6).
   - If the floor binds, raise share_reg_g and log it. Indicatively no floor binds.
7. A_PADM is 100% F_LREG (stated assumption). NAS GG CE includes imputed OPS pension contributions, which accrue to regular employees only.
8. For each activity: CE_reg_a = share_reg_{g(a)} × CE_a and CE_cas_a = CE_a − CE_reg_a.
   - Within manufacturing and within 58-99 every activity gets its group's share. The SUT's own CE is pro rata within MoSPI groups (Q2), so no finer information exists.
   - Cross-check manufacturing against ASI (`labour_enterprise_surveys_asi_2324_industry` `v1t3.workers_contract.all` 64,54,421 of `v1t3.workers.all` 1,55,19,957) and report only. Contract workers are often "regular" in PLFS.
9. Keep the per-group R/U wage-bill decomposition (Reg·E and Cas·w·D by s). F1a uses it, and it is published in the `v1a_labour_split` satellite.

### 2.2 V2a: mixed income vs operating surplus by activity

**Targets (GOS_a = OS/MI + CFC, SUT).** A_CROP 27,40,964.00 · A_LVST 12,36,708.00 · A_FOFI 6,19,781.00 · A_COAL 1,00,574.87 · A_OILG 1,12,507.95 · A_OMIN 2,13,939.71 · A_FOOD 2,34,971.98 · A_BVTB 86,566.36 · A_TXAP 2,81,866.87 · A_WOOD 1,74,283.34 · A_GJOM 86,843.86 · A_RPET 1,88,210.35 · A_CHEM 3,15,756.83 · A_PHRM 1,64,147.70 · A_NMMN 1,60,017.72 · A_MTLS 2,64,293.23 · A_MACH 3,21,959.17 · A_ELEQ 1,77,475.94 · A_TREQ 3,11,375.75 · A_CNST 10,75,588.00 · A_UTIL 6,74,437.35 · A_TRAD 14,53,361.00 · A_HOTL 2,03,814.00 · A_TRNS 7,80,846.00 · A_COMM 2,66,471.00 · A_FINS 9,68,693.09 · A_INSR 1,18,016.09 · A_DWEL 19,28,182.04 · A_BSRE 3,11,275.24 · A_ITSV 4,44,620.79 · A_EDUC 3,85,968.17 · A_HLTH 1,37,220.51 · A_OSRV 1,84,587.86 · A_PADM 2,94,700.00. Total 1,70,20,025.77.

**Household gross OS/MI by NAS group (7.1C OS/MI + CFC) vs SUT GOS of the mapped activities.** Every figure is from the data and checked (7.1C leaves sum to 7.1C totals).

| NAS 7.1C group | Activities | Household gross | SUT GOS | Household share |
|---|---|---:|---:|---:|
| crops | A_CROP | 26,42,640.19 | 27,40,964.00 | 0.964 |
| livestock | A_LVST | 12,35,695.93 | 12,36,708.00 | 0.999 |
| forestry + fishing | A_FOFI | 5,96,601.61 | 6,19,781.00 | 0.963 |
| mining | A_COAL, A_OILG, A_OMIN | 1,27,756.39 | 4,27,022.53 | 0.299 |
| manufacturing | 13 activities | 4,73,836.83 | 27,67,769.11 | 0.171 |
| utilities | A_UTIL | 14,738.14 | 6,74,437.35 | 0.022 |
| construction | A_CNST | 3,73,548.98 | 10,75,588.00 | 0.347 |
| trade_repair | A_TRAD | 11,38,697.65 | 14,53,361.00 | 0.783 |
| hotels | A_HOTL | 1,57,877.45 | 2,03,814.00 | 0.775 |
| railways+road+water+transport_services+storage (7.1C has no air row) | A_TRNS | 5,59,067.10 | 7,80,846.00 | 0.716 |
| communication | A_COMM | 10,740.34 | 2,66,471.00 | 0.040 |
| financial | A_FINS, A_INSR | 0.00 | 10,86,709.18 | 0 |
| real_estate_prof | A_DWEL, A_BSRE, A_ITSV | 19,70,121.61 | 26,84,078.06 | 0.734 |
| other_services | A_EDUC, A_HLTH, A_OSRV | 4,70,108.31 | 7,07,776.54 | 0.664 |
| public_admin | A_PADM | 0 | 2,94,700.00 | 0 |
| **total** | | **97,71,430.53** | 1,70,20,025.77 | |

(The SUT R&D bridge: NAS group 9 includes R&D, while the SUT keeps it in industry 58, i.e. A_EDUC. Household R&D is nil, so this affects only the `corp_gov` remainder. Group-level NAS-vs-SUT comparisons for groups 9 and 11 must use the NAS 8.13 bridge; see RECONCILIATION IND-re.)

**Steps.**
1. Read production's V2 constraint targets and assert equality with the table above.
2. **Single-activity groups** (crops, livestock, forestry+fishing, utilities, construction, trade, hotels, transport, communication):
   - HH_a = the group value.
   - `corp_gov_a` = GOS_a − HH_a. For example A_CROP 98,323.81; A_TRAD 3,14,663.35.
   - Status `derived`.
3. **Mining:** HH_OMIN = 1,27,756.39. A_COAL and A_OILG have no household share. This is an assumption: household mining is sand, stone and minor-mineral quarrying. Check HH_OMIN ≤ GOS_OMIN 2,13,939.71.
4. **Manufacturing and other_services:** use a 2-column RAS within the group.
   - Rows are GOS_a. Columns are HH_g and (Σ GOS_a − HH_g).
   - Household-column prior: ASUSE gross surplus of unincorporated enterprises = (Σ_OAE,HWE `t4.establishments` × `t37.gva_per_estt`) − (`t33.hired_workers.all` × `t33.emol_per_hired_worker.all`), by ASUSE category.
   - Other-column prior: GOS_a.
   - ASUSE → SAM mapping:
     - M2 → A_FOOD
     - M3+M4 → A_BVTB
     - M1+M5+M6+M7 → A_TXAP
     - M8+M9+M10+M23 → A_WOOD
     - M24 → A_GJOM
     - M11 → A_RPET
     - M12+M14 → A_CHEM
     - M13 → A_PHRM
     - M15 → A_NMMN
     - M16 → A_MTLS
     - M17+M20+M25 → A_MACH
     - M18+M19 → A_ELEQ
     - M21+M22 → A_TREQ
     - S13 → A_EDUC; S14 → A_HLTH; S15 → A_OSRV
   - *Indicative ASUSE surplus* (₹ cr, survey levels, used only as shares): M total 2,62,734; M6 apparel 70,641; M2 food 47,629; S13 55,583; S14 48,638; S15 1,09,913.
   - *Indicative RAS result* for other_services: household share EDUC 0.55, HLTH 0.75, OSRV 0.84.
   - Manufacturing: no cap binds even without RAS. For example A_TXAP gets about 61% household and A_RPET under 0.1%.
   - **Why not the gap map's "SUT OS shares within the group":** SUT VA is pro rata within MoSPI groups (Q2), so that key would give A_RPET the same 17% household share as apparel.
5. **real_estate_prof (A_DWEL, A_BSRE, A_ITSV), ratio method:**
   - HH_nondwell = household CE in group 9 × ASUSE (GVA − emoluments)/emoluments for S7+S10+S11+S12, i.e. `s7_1c.real_estate_prof.ce.current` 32,337.62 × *indicative* 3.2987 ≈ **1,06,673.72**. Ownership of dwellings has no CE (SUT i57 CE = 0), so all household group-9 CE belongs to BSRE/ITSV-type enterprises.
   - HH_DWEL = 19,70,121.61 − HH_nondwell ≈ **18,63,447.89** (96.64% of GOS_DWEL), capped at GOS_DWEL.
   - Split HH_nondwell between A_BSRE (S10+S11+S12) and A_ITSV (S7) by ASUSE surplus (≈ 89/11), each capped at its GOS.
   - The CFC-based alternative and why it is rejected are in §5 (C7).
6. **Partnerships, trusts, cooperatives:** for each non-farm, non-dwelling activity with ASUSE coverage, compute q_a:
   - q_a = [Σ_OAE,HWE (share partnership_diff_hh + society_trust + cooperative + others) × GVA_type] / GVA_all, from `t6.estt_share.*` (counts, stored as percent) and the t4 × t37 GVA.
   - *Indicative:* manufacturing 1.3%, trade 1.5%, services 8.1% (education 36.3%, other community/personal 12.2%, health 4.0%), all activities 4.1%.
   - Proprietary units, same-household partnerships and SHGs stay mixed income. Farming, mining and construction get q = 0: ASUSE does not cover them, and this is logged.
   - `hh_quasi_a` = q_a × HH_a goes to F_GOSC; the rest goes to F_MIXD.
7. **Dwellings:**
   - `hh_dwelling_imputed` = min(s_imp × GOS_DWEL, HH_DWEL).
   - `hh_dwelling_actual` = HH_DWEL − imputed.
   - s_imp = the imputed-rent share of dwelling-services output, taken from households' C4a split: imputed ÷ (imputed + actual + government-provided housing).
   - There is no F_MIXD ← A_DWEL entry.
8. `corp_gov_a` = GOS_a − HH_a for every activity. It must be ≥ 0. This holds by construction (RAS or caps).
9. No zero entries: `spec.ZERO_ENTRY_REFS` allows zeros only for D4. So write no F_MIXD for A_COAL, A_OILG, A_FINS, A_INSR, A_PADM or A_DWEL, and no `hh_quasi` where q = 0.

### 2.3 V3, V4
Copy NAS 6.1 as published. The factor assignment (100% F_LREG for both) is the gap-map assumption, recorded in each provenance `method`. BoP BPM6 (₹ cr, rounded) agrees to within ₹0.24 cr. Record a `ctx.check` against the BoP.

### 2.4 F1
No entries. It is the constraint `factors.f1.total` (§3). The identity holds automatically once F_LREG and F_LCAS balance. The only gap is 0.17 cr of SUT-vs-NAS rounding in CE, so tol_abs = 1.

### 2.5 F1a: labour income by household group
1. Factor totals:
   - F_LREG = Σ V1a(F_LREG) + V3 − V4.
   - F_LCAS = Σ V1a(F_LCAS).
2. R/U split per factor:
   - Regular: Σ_g CE_reg_g × (Reg·E)_{g,s} / Σ_s (Reg·E)_g.
   - Casual: likewise with Cas·w·D.
   - V3 − V4 (net 31,708.33) is allocated pro rata to the regular R/U split (stated assumption).
   - *Indicative* rural share of each group's wage bill: regular 0.30 (58-99) to 0.83 (01-03); casual 0.39 (58-99) to 0.95 (01-03).
3. Within R or U, the five SAM quintiles hold 20% of persons each (HCES person quintiles). Shares are the normalised IFPRI per-capita index I_q = share_q(T10) × total_spending_per_capita_q(T11). The q-th national quintile's index is applied to the k-th sector quintile, with k = q (a stated assumption). If households publish a national-quintile crosswalk, use I_k = Σ_q x_{k,q} I_q instead.
   - Regular ← IFPRI medium+high-educated labour: 6.47 / 10.10 / 13.70 / 19.43 / 50.30 %.
   - Casual ← IFPRI low-educated labour: 16.75 / 18.36 / 17.70 / 23.61 / 23.58 %.
   - Sensitivity: `labour_all` for both, 7.60 / 11.04 / 14.14 / 19.88 / 47.35 %.
   - All from `ifpri.t10.*` × `ifpri.t11.total_spending_per_capita.*`, 2022-23, old base, national quintiles.
4. Confidence is low. The UI shows a band.

### 2.6 F2: mixed income by household group
1. Totals: farm = Σ V2a F_MIXD for A_CROP, A_LVST, A_FOFI; non-farm = the rest.
2. R/U split:
   - **Farm:** PLFS farm self-employed workers by R/U × self-employment earnings. Inputs:
     - t26 A: rural 59.84%, urban 6.73% of workers;
     - t20 01-03 self_employed: rural 82.3, urban 74.9;
     - WPR × pop;
     - × FY mean `api_i8.self_employment_gross_earnings_30d.<s>.person.current`: rural 11,325.12, urban 19,903.15.
     - The gap map's "100% rural" is the sensitivity.
   - **Non-farm:** ASUSE (GVA − emoluments) by R/U for the category that matches the activity (M: rural 1,11,845 / urban 1,50,890; T: 1,81,890 / 3,38,554; S: 2,41,913 / 3,48,819, *indicative* sums). Mining and construction use PLFS 05-09 and 41-43 self-employed counts (t20 self_employed R/U) × `api_i8` R/U.
   - ASUSE `household_group` is the establishment's location, a proxy for the household's R/U (labour_enterprise_surveys issue VER-5).
3. Within R/U quintiles, using IFPRI gradients (normalised per-capita index):
   - Farm ← crop_land + capital_agriculture: 10.43 / 14.79 / 19.68 / 34.18 / 20.92 %.
   - Non-farm ← capital_non_agriculture: 7.16 / 11.32 / 16.31 / 22.63 / 42.59 %.
   - Cross-check (report only): SAS 2019 income by land class (`s5_1a.income_crop_production_net.*`, `s5_1a.income_farming_animals_net.*`). SAS land classes are not MPCE quintiles.
4. Components `farm` and `nonfarm` keep the two keys visible. Confidence is low.

### 2.7 F3, F3a, F3b, F3c
- **F3** has no entries. It is covered by the F2 + F3 constraint (§3).
- **F3a:** total = Σ `hh_dwelling_imputed`. The key is households' imputed-rent key, bit-for-bit the one C4a uses. Test: shares equal the C4a imputed-rent shares within 1e-9. Confidence medium. HCES records imputed rent by fractile (A6 memo, A10F item), so the distribution is informative; the level is the weak part (§5 C7).
- **F3b:** total = Σ `hh_dwelling_actual`. The key is owners' assets, not tenants' rent. Households publish it from AIDIS 2019 (`i9.fixed_assets_per_hh.<r/u>_q1..q5` × households per class; press-note building share by R/U). This is a proxy: AIDIS Report 588 tables on rented-out property are not located (labour_enterprise_surveys-2, -19). Confidence low, with a band on the site.
- **F3c:** total = Σ `hh_quasi`. R/U by ASUSE non-proprietary GVA by R/U. Within R/U by the IFPRI `capital_non_agriculture` gradient (as for non-farm F2). Confidence low.

### 2.8 F4: sector GOS (derived, exact)

The gap-map formula, recomputed. Every identity closes against NAS 1.14 to within ₹0.0005 cr.

| Sector | GVA | CE | Net prod. taxes | CFC | OS | **GOS** | Source arithmetic |
|---|---:|---:|---:|---:|---:|---:|---|
| Public NFC (E_NFPU) | 15,19,219.96 | 4,87,577.82 | −1,35,537.20 | 4,48,494.21 | 7,18,685.12 | **11,67,179.33** | `s7_1a.total.*` − `s8_15_1.total.*` − `s7_1a.financial.*` |
| Private NFC (E_NFPR) | 85,82,258.78 | 39,56,594.08 | 6,636.92 | 17,51,893.60 | 28,67,134.17 | **46,19,027.77** | `s7_1b.total.*` − `s7_1b.financial.*` |
| Public FC | 7,14,051.72 | 2,79,448.15 | 370.95 | 16,628.71 | 4,17,603.91 | **4,34,232.62** | `s7_1a.financial.*` |
| Private FC | 9,44,003.27 | 2,91,227.64 | 299.29 | 62,431.04 | 5,90,045.30 | **6,52,476.34** | `s7_1b.financial.*` |
| General government | 25,02,920.71 | 21,27,241.55 | 0.00 | 3,75,679.16 | 0.00 | **3,75,679.16** | `s8_15_1.total.*` |
| Households incl. NPISH | 1,21,43,025.55 | 23,00,807.39 | 70,787.63 | 11,81,078.84 | 85,90,351.69 (OS/MI) | **97,71,430.53** | `s7_1c.total.*` |
| **Total** | 2,64,05,479.97 | 94,42,896.63 | −57,442.41 | 38,36,205.56 | 1,31,83,820.20 | **1,70,20,025.76** | = `s7_1` totals |

Cross-checks:
- GVA vs `s1_14.<sector>.gross_value_added_at_basic_prices.current`: differences ≤ 0.0005.
- CFC vs `s1_14.<sector>.consumption_of_fixed_capital.current`: equal.
- Public NFC CFC = `s8_16.departmental_enterprises.cfc` 79,014.86 + `s8_16.non_financial.cfc` 3,69,479.35.
- Public FC GVA = 8.15.2 financial 13,191.55 + 8.15.3 financial 7,00,860.17.
- GOS computed as GVA − CE − NPT equals OS + CFC for every sector.

Entries and constraints:
- Entries: (E_NFPU, F_GOSC, F4) = 11,67,179.33 and (E_NFPR, F_GOSC, F4) = 46,19,027.77. Both `derived`, `fixed`.
- FC: constraint only, on E_RBI+E_BANK+E_NBFC+E_INSP ← F_GOSC (refs F4a) = 10,86,708.96. The SUT A_FINS + A_INSR GOS is 10,86,709.18 (cross-check).
- GG: constraint only, on G_CEN+G_STA ← F_GOSC (refs F4b) = 3,75,679.16. The same value appears in `s8_15_1.total.cfc.current`, `s1_14.gg.consumption_of_fixed_capital.current`, `s4_1.consumption_of_fixed_capital.current` and `s8_16.administrative_departments.cfc.current`.

### 2.9 F4b: GG GOS (= CFC) Centre vs States
1. NAS 4.1 NVA (current): Centre 5,77,518.54; States 11,78,216.69; local bodies 2,18,133.04; autonomous institutions 1,53,164.21; total 21,27,032.48.
2. Central autonomous bodies' NVA is proxied by Union revenue grants-in-aid to autonomous bodies. From the Finance Accounts IGAS-2: `gia.cash.autonomous_bodies.total` 1,91,248.34 − `gia.cash.autonomous_bodies.capital_assets` 1,39,896.67 = **51,351.67**, capped at 1,53,164.21. The States' own grants to their autonomous bodies are not in clean data, so the rest of the block (1,01,812.54) goes to G_STA.
3. Centre share = (5,77,518.54 + 51,351.67) / 21,27,032.48 = **0.295656**. G_CEN = 1,11,071.85; G_STA = 2,64,607.31 (*indicative*). The gap map assumes equal CFC/NVA ratios.
4. Sensitivity A: autonomous bodies split pro rata to the rest of GG NVA (Centre 0.292582, so G_CEN 1,09,917.00).
5. Sensitivity B: capital-stock proxy from 2023-24 capital outlays. Union: `union_fiscal_fa_expenditure` capital section less railways, i.e. `fa9.5002.total` 2,42,537.91 and `fa9.5003.total` 110.55. States: `state_fiscal_rbi_sf_appendices` `app4.total_capital_disbursements.i-total_capital_outlay.in.all_states_uts.actuals` 7,47,305.79. Report only.
6. Publish the key as the `gg_centre_state_key` satellite. Government's C2a own-output split must use the same key.

---

## 3 Constraints to declare

Each constraint is: Σ entries with row ∈ rows and col ∈ cols (and ref ∈ refs) = target ± max(tol_abs, tol_rel·|target|). Every target is read from clean data at build time, never typed in.

| constraint_id | ref | rows | cols | refs | target (2023-24) | source series | tol_abs | kind | note |
|---|---|---|---|---|---:|---|---:|---|---|
| `factors.v1.<act>` × 33 (all but A_DWEL) | V1a | F_LREG, F_LCAS | A_<act> | V1a | SUT CE_a (§2.1) | Σ `io_tables_sut_va` `va.ce.sut_iNN.current` | 0.01 | equal | Duplicates production's V1. Targets must be identical (test) |
| `factors.v2.<act>` × 34 | V2a | F_MIXD, F_GOSC | A_<act> | V2a | SUT GOS_a (§2.2) | Σ `va.os_mi.*` + `va.cfc.*` | 0.01 | equal | Duplicates production's V2 |
| `factors.f1.total` | F1 | H_R1…H_U5 | F_LREG, F_LCAS | F1a | 94,74,604.95 | `mospi_nas_2026_derived_residuals` `derived.ce_receivable_by_residents.current` | 1.0 | equal | Implied by account balance; tolerance covers the 0.17 SUT/NAS rounding |
| `factors.f2f3.hh_gross_os_mi` | F3 | H_R1…H_U5 | F_MIXD, F_GOSC | F2, F3a, F3b, F3c | 97,71,430.53 | `s7_1c.total.os_mi.current` + `s7_1c.total.cfc.current` | 1.0 | equal | The key household-sector anchor |
| `factors.f4.fc_gos` | F4 | E_RBI, E_BANK, E_NBFC, E_INSP | F_GOSC | F4a | 10,86,708.96 | `s7_1a.financial.{os,cfc}` + `s7_1b.financial.{os,cfc}` | 1.0 | equal | fincorp may declare the same (same target) |
| `factors.f4.gg_gos` | F4 | G_CEN, G_STA | F_GOSC | F4b | 3,75,679.16 | `s8_15_1.total.cfc.current` (= `s1_14.gg.consumption_of_fixed_capital.current`) | 0.5 | equal | |
| `factors.f4.nfc_public` | F4 | E_NFPU | F_GOSC | F4 | 11,67,179.33 | 7.1A − 8.15.1 − 7.1A financial | 0.01 | equal | Redundant with the fixed entry; documents the source |
| `factors.f4.nfc_private` | F4 | E_NFPR | F_GOSC | F4 | 46,19,027.77 | 7.1B − 7.1B financial | 0.01 | equal | same |

Not declared, because the framework cannot express them yet (FRAMEWORK_REQUESTS candidates, §6):
- the 15 NAS 7.1C group-level household controls (they need a filter on `component`);
- the public/private FC GOS targets 4,34,232.62 and 6,52,476.34 (fincorp's components);
- one-sided rules: the regular-CE floor and the household cap HH_a ≤ GOS_a.

Until then these hold exactly in the prior, and the block tests assert them.

---

## 4 Interfaces

### 4.1 Needs from other blocks
| From | What | Why |
|---|---|---|
| production | V1 and V2 constraint targets by activity (`ctx.block_constraints('production')`), same concordance | Must equal factors' duplicate constraints; factors does not re-aggregate independently except as a check |
| households (`hh_keys` satellite) | (1) The group list and R/U membership of H_R1..H_U5. (2) `population`: persons by group and R/U totals (HCES A2). (3) `imputed_rent`: the exact key C4a uses. (4) The C4a dwelling-services split in ₹ cr (imputed rent, actual rent, government-provided housing) or its shares. (5) An AIDIS asset key by group (fixed assets or buildings; for F3b). (6) Optional: a national-quintile crosswalk (share of each group's persons in national MPCE quintiles q1..q5) to re-map IFPRI's national-quintile priors | F1a, F2, F3a, F3b, F3c keys; s_imp for V2a |

### 4.2 Publishes for other blocks
| Satellite / output | Content | Used by |
|---|---|---|
| entries F1a, F2, F3a, F3b, F3c | Household factor income by group | closure (K4a resources whitelist: F1a F2 F3a F3b F3c), taxes (T3a PIT keyed on regular wages and non-farm MI), government (R9a) |
| `sector_gos` | GVA, CE, NPT, CFC, OS, GOS for nfc_public, nfc_private, fc_public, fc_private, gg, households_npish (the §2.8 table, with prov) | fincorp (F4a/K2a public 4,34,232.62 / private 6,52,476.34 targets), capital_financial and closure checks |
| `gg_centre_state_key` | Centre/State shares of GG NVA incl. the autonomous-bodies split, inputs and method | government (C2a own-output split must match F4b) |
| `factor_income_keys` | By group: shares of F_LREG, F_LCAS, F_MIXD farm, F_MIXD non-farm, imputed rent, actual rent received, quasi-corporate surplus; R/U totals | taxes (T3a), government (R9a public-sector pension proxy), closure |
| `va_split_by_activity` | Per activity: CE_reg, CE_cas (and R/U), HH MI, HH dwelling imputed/actual, hh_quasi, corp_gov | timeseries (CE, OS/MI flows), multiplier engine, verifier |
| `v1a_parameters` | D (306.8 days), share_reg by PLFS group, floors applied, sensitivities | verifier, BALANCING.md |

Notes other blocks must respect:
- **fincorp:** write the F4a entries (with public/private parts) summing to `factors.f4.fc_gos`. Do not write any F4-ref entry.
- **government:**
  - GG GOS is CFC only (OS = 0).
  - Farm income support (PM-KISAN etc.) sits in SUT agriculture's production subsidies (P10), so it reaches households through F_MIXD. It must not also appear in R10.
  - Imputed OPS pension contributions are inside CE (V1, mainly A_PADM, A_EDUC, A_HLTH) and reach households via F_LREG. R9b returns them.
- **rest_of_world:** V3 and V4 are owned here. Do not write R_ROW ↔ FAC entries.
- **closure:** IFPRI shares are used to build the F1a and F2 priors. The IFPRI saving-rate plausibility check in closure is therefore not independent of the income side (§6).

---

## 5 Conflicts and choices (both values, control vs cross-check)

| # | Item | Source A | Source B | Recommendation |
|---|---|---|---|---|
| C1 | Domestic CE total | SUT Σ67 `va.ce.*` 94,42,896.46 | NAS `s7_1.total.ce.current` 94,42,896.63 | **Control SUT** (activity detail; production's V1). NAS is the cross-check. The 0.17 gap is rounding; tol 1 |
| C2 | OS/MI + CFC total | SUT 1,70,20,025.77 | NAS 7.1 1,70,20,025.76; Σ sectors 1,70,20,025.76 | Control SUT for activities; NAS sectors for F4. Tol 1 |
| C3 | CE from/to RoW | NAS 6.1: 62,344.24 / 30,635.91 | BoP BPM6 (₹ cr): 62,344 / 30,636 | **Control NAS 6.1** (same vintage as F1). BoP is the cross-check (rounded) |
| C4 | FC GOS | NAS sectors 10,86,708.96 | SUT A_FINS + A_INSR 10,86,709.18 | **Control NAS sectors**; SUT is the cross-check |
| C5 | GG GVA | NAS 4.1 25,02,711.64 (NVA 21,27,032.48) | 1.14 / 8.15.1 25,02,920.71 (CE 21,27,241.55) | **Control 1.14** (gap 209.07; mospi_nas_2026-10). 4.1 is used only as a key |
| C6 | GG CFC | 8.15.1, 1.14, 4.1 and 8.16 admin departments: all 3,75,679.16 | — | Agree |
| C7 | **Dwelling CFC vs household sector** | SUT A_DWEL CFC 6,95,681.33 (GOS 19,28,182.04) | 7.1C household real_estate_prof CFC 4,92,817.71 (gross 19,70,121.61); 7.1B private corporate group-9 CFC 3,04,772.68 | At least 2,02,863.62 of dwelling CFC must sit outside households. A CFC-consistent split caps the household dwelling share at ≤ 70.84% and pushes ≥ 6,04,205.61 of group-9 household surplus into BSRE/ITSV, i.e. households would own about 80% of IT and business-services surplus. That is implausible, given the corporate IT sector. **Recommend the GOS-level ratio method** (§2.2 step 5, household dwellings ≈ 96.64% of A_DWEL GOS). The SAM is gross, so CFC composition enters no cell. Log it; question to NAD. Sensitivity: household dwelling share 70.84% (moves ≈ 4,97,531.89 between F3a/F3b and F2; totals unchanged) |
| C8 | Group-9 production taxes | SUT pro rata (Q2): A_DWEL 76,157.75, A_ITSV 66,850.00, A_BSRE 46,801.09 | NAS: household group 9 bears 1,92,248.94 of the group's 1,92,710.89; private corporate 561.12 | SUT stays the control (production's fixed P10/V2). Flag to production/taxes: A_DWEL GOS is probably overstated by about 1.16 lakh cr and IT/BSRE understated by the same. This makes the household cap on A_DWEL looser than reality. Log in issues |
| C9 | PLFS earnings Q2–Q4 2023-24 | AR `st10/st11/st12` (e.g. rural regular 16,261) | API `api_i6/i7/i8` (16,260.90), vintage 2024-09-23 | **Control API** for all four quarters (Q1 exists only in the API, vintage 2026-09-29). AR is the cross-check. Mind the Statement 10 one-month reference lag (labour_enterprise_surveys-5) |
| C10 | Survey levels vs NAS levels | PLFS casual wage × workers; ASUSE market GVA 17,97,278 (`fs.gva.asuse_all.total.current`, 2023-10/2024-09) | NAS household sector CE 23,00,807.39; household GVA 1,21,43,025.55 | Surveys are used **only as shares or ratios**, never as levels. Example: calibrating D so that PLFS casual pay equals NAS household agricultural CE would need more than 365 days a year |
| C11 | V2a within-group key | Gap map: SUT OS shares | ASUSE surplus by category, RAS | **ASUSE RAS.** The SUT shares are pro rata (Q2) |
| C12 | Farm MI R/U | Gap map: 100% rural | PLFS: urban workers are 6.73% in section A; urban farm self-employed exist | **PLFS**; 100% rural as sensitivity |
| C13 | Autonomous-bodies split (F4b) | Union revenue GIA key: Centre 0.295656 | Pro rata: 0.292582 | **Union GIA** (closer to the gap map). The difference is ≈ ₹1,155 cr. Capital-outlay key as a report-only sensitivity |
| C14 | State CE, GOV-12 xfail | NAS 4.1 States 11,78,216.69 | FC16 salaries 10,86,649 (+8.43%) | Irrelevant to F4b (NAS is used as the key). Noted |
| C15 | IFPRI priors | IFPRI 2022/23: national quintiles, old base, 2022-23 | SAM: HCES 2023-24 person quintiles within R/U | IFPRI is used only as gradients within R/U, labelled "old base, national quintiles". The crosswalk from households is preferred if it is published |

---

## 6 Risks, gaps, open questions

**Double-counting risks (each needs a test):**
1. Household dwelling surplus counted twice, in F_MIXD and in F3a/F3b. Rule: no F_MIXD ← A_DWEL entry.
2. Corporate-owned dwellings counted in both E_NFPR (via F4) and F3b. Rule: F3b = HH_DWEL − imputed only; the corporate part stays in `corp_gov`, and Σ `corp_gov` = F4 NFC + FC + GG totals.
3. Partnership/trust surplus counted in both F_MIXD and F3c. Rule: V2a carves `hh_quasi` out of HH_a before F_MIXD.
4. FC GOS written by both factors and fincorp. Rule: factors writes only the constraint.
5. GG GOS: only F4b entries, no F4 GOV entry.
6. CE with RoW written by both factors and rest_of_world. Rule: V3/V4 only here.
7. Farm income support in both F_MIXD (through P10) and R10 (government).
8. OPS imputed contributions in CE and netted again. Keep them in V1/F1a; R9b returns them.
9. The IFPRI prior used both to build incomes (F1a, F2) and to judge household saving rates (closure).
10. An F1 entry written in addition to F1a (F1 is a constraint only).

**Where the gap-map method cannot be followed, and the fallback:**
- **V1a:** no PLFS unit data (D1-2), no regular earnings by industry, and usual status (Table 20) is mixed with CWS earnings. Fallback: group-level status × R/U average earnings, the D parameter and the NAS floor.
- **V2a:** no GVA by ownership type (labour_enterprise_surveys-6). Fallback: count shares × OAE/HWE GVA per establishment.
- **F1a, F2, F3c:** no MPCE-linked earnings. Fallback: IFPRI gradients.
- **F3b:** no rented-out property table. Fallback: AIDIS asset proxy.
- **F4b:** no States' grants to autonomous bodies. Fallback: Union side only.

**Open questions (to NAD or the owner):**
- (a) How is dwelling ownership split between the household and corporate sectors, and why does 7.1C group-9 CFC fall short of SUT dwelling CFC (C7)?
- (b) Are MGNREGA wages NAS CE, and in which sector and industry? Union `fa9.2505.02.total` 89,153.79; Expenditure Profile St 6 `stat6.item.ministry_of_rural_development.mgnrega_programme_component` 88,751.06 is classed as a grant for capital assets. This decides whether public construction CE is casual. The floor already excludes construction.
- (c) Is government-provided housing produced inside A_DWEL (GG-owned), and is it therefore outside F3a?
- (d) Are cooperatives and different-household partnerships in the household sector or the private corporate sector in NAS 2026? If corporate, carving them out of 7.1C gives the wrong key, though the totals are unaffected.
- (e) Non-market NPISH CFC is not separable. It stays in F_MIXD for other services unless ASUSE society/trust coverage catches it.

**Data risks:**
- ASUSE runs Oct 2023–Sep 2024, PLFS Jul–Jun, AIDIS stocks are dated 2018-06-30, SAS covers 2018-19, and IFPRI covers 2022-23. All are used as shares with the period stated.
- AIDIS `i9.fixed_assets_per_hh` falls from q4 to q5 in both R and U (e.g. urban q4 38,48,836 vs q5 27,50,466), so the classes may not be what they seem. Households must confirm the classification.
- The PLFS `t51` casual wage by section has missing urban/rural cells for some sections; use the `.total.` fallback and log it.
- There is a gap of about 1% between the t4 × t37 ASUSE GVA (≈ 18.16 lakh cr, my computation) and `fs.gva.asuse_all.total.current` 17,97,278. Only shares are used, so the effect is small.

**Balancing risks:**
- The low-confidence group entries (F1a, F2, F3b, F3c) will absorb most of the household-account imbalance, together with K4a.
- The V1 and V2 activity constraints and the household total pin every total, so only group, factor-type and Centre/State splits can move.
- If the prior makes some F_MIXD_a or `corp_gov_a` tiny, balancing cannot flip its sign (z ≥ 0). Keep every entry at least ₹1 cr or omit it.

**Framework requests (for `docs/phase2/FRAMEWORK_REQUESTS.md`):**
- FR-f1: constraints filtered by `component`, for the 7.1C group controls and the fincorp public/private FC targets.
- FR-f2: one-sided (≤ / ≥) constraints, for the household caps and the regular-CE floor.
- FR-f3: confirm that refs used only in constraints (F1, F3) satisfy `check_contract`.

**Issues file:** the builder opens `docs/phase2/issues/factors.md` with C7, C8, D, the MGNREGA question, the IFPRI mapping, the AIDIS anomaly, and every capped or floored value.

---

## 7 Tests the builder should write

All targets are read from clean data (`ctx.value` / `pl.read_parquet`) inside the test, never typed in. The tolerance is ₹0.01 cr unless stated.

1. **V1 by activity:** for each of 33 activities, Σ (F_LREG, F_LCAS) ← A_x = Σ `io_tables_sut_va` `va.ce.sut_iNN.current` over its concordance industries. There is no labour entry ← A_DWEL. The total is within ₹1 of `s7_1.total.ce.current` 94,42,896.63.
2. **V2 by activity:** for each of 34 activities, Σ (F_MIXD, F_GOSC) ← A_x = Σ (`va.os_mi` + `va.cfc`). The total is within ₹1 of `s7_1.total.os_mi.current` + `s7_1.total.cfc.current` = 1,70,20,025.76.
3. **Duplicate constraints agree:** factors' V1/V2 targets equal production's (`ctx.block_constraints('production')`).
4. **Household anchor by NAS group (prior):** for the 15 groups in §2.2, Σ over the group's activities of (F_MIXD + `hh_quasi` + `hh_dwelling_*`) = `s7_1c.<grp>.os_mi.current` + `s7_1c.<grp>.cfc.current`. The total is 97,71,430.53.
5. **F2 + F3 total:** Σ H_* ← {F_MIXD, F_GOSC} = 97,71,430.53 (tol 1).
6. **F1 total:** Σ H_* ← {F_LREG, F_LCAS} = `derived.ce_receivable_by_residents.current` 94,74,604.95 (tol 1). F_LREG row = column and F_LCAS row = column in the prior (exact).
7. **V3/V4:** they equal `s6_1` (62,344.24 / 30,635.91), and are within ₹1 of `bpm6.inr.bpm6_1_b_1.{credit,debit}.current`.
8. **F4 NFC:**
   - E_NFPU = 11,67,179.33 and E_NFPR = 46,19,027.77, recomputed from `s7_1a`, `s7_1b` and `s8_15_1`.
   - GVA and CFC by sector equal `s1_14` (5 GVA + 5 CFC checks).
   - GOS as GVA − CE − NPT equals OS + CFC.
   - Public NFC CFC = `s8_16.departmental_enterprises.cfc` + `s8_16.non_financial.cfc`.
9. **FC and GG constraints:**
   - The FC target is 10,86,708.96, within ₹1 of SUT A_FINS + A_INSR GOS.
   - The GG target is 3,75,679.16 and equals `s1_14.gg.consumption_of_fixed_capital`, `s4_1.consumption_of_fixed_capital` and `s8_16.administrative_departments.cfc`.
   - F4 NFC + FC + GG + households = the V2 total.
10. **F_GOSC closes in the prior:** row (Σ V2a F_GOSC) = column (F4 entries + F3a + F3b + F3c + F4b entries + FC constraint target).
11. **Structure and signs:**
    - All entries > 0 and none equal to zero.
    - No F_MIXD ← {A_DWEL, A_FINS, A_INSR, A_PADM, A_COAL, A_OILG}. No F_LCAS ← A_PADM.
    - No factors entry with row in {E_RBI, E_BANK, E_NBFC, E_INSP}. No F4-ref entry with row in GOV.
12. **Caps and floors:**
    - Household part of each activity ≤ GOS_a, and `corp_gov_a` ≥ 0.
    - Regular CE by NAS group ≥ `s7_1a.<grp>.ce.current` for every group except agriculture and construction.
    - A_PADM is all F_LREG.
13. **Keys:**
    - F3a group shares equal the households C4a imputed-rent shares (1e-9).
    - The F4b G_CEN share equals (`s4_1.central_government` + min(GIA_rev, `s4_1.autonomous_institutions`)) / `s4_1.net_value_added`, with GIA_rev = `gia.cash.autonomous_bodies.total` − `gia.cash.autonomous_bodies.capital_assets`.
    - The F1a and F2 within-R/U shares equal the normalised IFPRI indices, and R/U totals equal the V1a by-product.
14. **Parameter D:** D = `t33.emol_per_hired_worker.informal.asuse_all.total.current` ÷ the mean of `api_i7.casual_wage_earnings_day.total.person.current` over Q1–Q4 2023-24 (306.8), recorded as an `estimated` prov record.
15. **Sanity bands (warn, not fail):**
    - National regular share of CE in [0.70, 0.85] (indicative 0.787).
    - Household dwelling share of A_DWEL GOS in [0.70, 1.00] (indicative 0.966; the lower bound is the CFC-consistent value).
    - F3c/household gross in [0, 0.05].
    - G_CEN share in [0.25, 0.35].
16. **Provenance:** every entry and constraint has a prov_id whose `inputs` resolve to clean prov_ids (list in §2), and every `estimated` record has a non-empty `method` citing its gap-map ref and assumption.

---

## 8 Cross-plan review (2026-09-30, cross-plan critic; details and ids in `CROSS_REVIEW.md`)

What this block must change or confirm:

1. **XR-15 do not re-declare production's V1/V2 targets.** Production already declares `ce.<act>` and `os_mi_cfc.<act>` with tol_abs = ₹1 × SUT cells and refs = none. Your `factors.v1.*` / `factors.v2.*` (refs [V1a]/[V2a], tol 0.01) are separate selections, so both would bind, and the tighter one would undo the rounding allowance. Keep the equality as a test against `ctx.block_constraints("production")`.
2. **XR-20 the framework now supports what you listed as blocked.** Declare:
   - the 15 NAS 7.1C group-level household controls (components filter on `mixed_income`, `hh_quasi`, `hh_dwelling_imputed`, `hh_dwelling_actual`);
   - the regular-CE floor (`kind="min"`);
   - the household caps HH_a ≤ GOS_a (`kind="max"`).

   The FC public/private GOS targets stay with fincorp (`fincorp.f4a.public/private`). `factors.f4.fc_gos` must equal `fincorp.f4a.fc_gos_total` (same series and arithmetic, tol 1).
3. **XR-22 C4a ↔ F3a:** declare per-group `band` constraints on F3a entries, target = F3a total × households' `c4a_imputed_rent` share, ±10%. The levels legitimately differ (output vs surplus), so link the shares only. Add a post-balancing share-drift report.
4. **XR-10 key names:** read households' `pop_persons`, `c4a_imputed_rent`, `aidis_fixed_assets` and the new `hh_national_quintile_xwalk`. Use the crosswalk to map IFPRI national-quintile gradients onto within-R/U groups instead of assuming k = q.
5. **Publish `public_sector_wage_key`** (F_LREG by group × PLFS t35 public-sector share, R/U) inside `factor_income_keys`. government (R9a/R9b) and fincorp (R9c NPS/GPF) both need one common public-employee key.
6. **XR-7 Centre/State:** `gg_centre_state_key` is institutional (NAS 4.1, local bodies and State autonomous bodies in G_STA). If the orchestrator adopts the institutional view (recommended), nothing changes here. If it keeps the treasury view, the F4b/C2a key must be recomputed on the treasury basis.
7. **XR-2 note:** if a ref for departmental-enterprise pensions (HH ← E_NFPU) is created, its imputed contributions sit in public-NFC CE (V1); say so in the V1a method text.
8. Confirmed consistent across plans:
   - V3/V4 only here (rest_of_world agrees);
   - no F4 FC or GG entries;
   - PM-KISAN in P10 → F_MIXD, not R10 (government and taxes agree);
   - OPS imputed contributions in CE (government's R9b returns them; its size is decision D-2).
