# Plan: the `rest_of_world` block (Phase 2 SAM, FY 2023-24)

Prepared 2026-09-30 by the rest_of_world data scout (research only). I wrote no code under `pipeline/` and ran no `pipeline build/sam/repro`. Every number below was read from `data/clean/**` Parquet with polars on 2026-09-30, using scratch scripts outside the repo. Values are ₹ crore, current prices, FY 2023-24, unless stated.

"Indicative" numbers are my own arithmetic on clean data. They show that a method works and what size to expect. The builder recomputes them through `ctx.value` / `ctx.frame` and never types them into code.

Framework vocabulary used here is taken from `pipeline/sam/spec.py` as it stood on 2026-09-30: roles `fixed/anchored/free`, statuses `official/derived/estimated`, `BOP_FUNCTIONS`, which already include `FDI_debt` and `short_term_credit`, constraint kinds `equal/band`, and `ctx.check` for control totals.

---

## 1 Summary (plain English)

- This block builds the rest of the world's two accounts in the SAM:
  - **R_ROW**, the current account: what India pays abroad and receives from abroad.
  - **K_ROW**, the capital and financial account: foreign investment flows, by instrument, with FDI/FPI/ECB/NRI tags.
  - It also writes the reserve build-up (K8c) and the pinned NAS–BoP CIF reconciliation cell (D2).
- **The totals are official and they agree with each other.** NAS Statement 6.1 and the RBI balance of payments match exactly once three named bridges are applied (RECONCILIATION §2).
- **Both accounts close before any balancing.**
  - R_ROW: with production's SUT export and import vectors and the NAS compensation flows, it closes to **₹0.0004 crore**.
  - K_ROW: it closes exactly to NAS net lending of −2,16,000.96, *provided* the government block books government transfers with RoW as NAS does (capital, not current).
- **What is estimated is "who in India":**
  - which household group receives remittances. There is no survey of this, so the confidence is low.
  - which corporation or government pays or receives each type of foreign property income.
  - which domestic sector is the counterpart of each foreign capital flow.
  - how FPI debt splits between government securities and corporate bonds.
- **Three rules other blocks must honour:**
  1. Government's current transfers with RoW (BoP 1.C.2, net −6,357) are **not** written as R15. NAS books them as capital transfers (K6), and K5 = 2,08,890.71 assumes that treatment.
  2. This block owns **every** property-income flow with RoW. That includes interest on government external debt and on FPI-held G-secs, and dividends paid to foreigners. fincorp must leave RoW out of its R3a/R8/R4/R5 splits.
  3. The BoP-based financial flows here **replace** the FSF's rest-of-world counterparties wholesale. This matters because the FSF books all FDI and FPI, including FPI debt, as equity of private NFCs.
- **Main weaknesses:**
  - remittances by household group (low confidence);
  - payer and recipient keys for property income (low to medium);
  - the X_DISC account cannot close within ₹0.01 using the published rounded figures: it is off by 0.1075 crore. This is flagged for closure.

## 2 Ref-by-ref table

Rows receive, columns pay. "E_*" means E_NFPU E_NFPR E_RBI E_BANK E_NBFC E_INSP; "H_*" means the 10 groups. All clean series below have period `2023-24` unless a date is shown. Where a series has more than one vintage, the vintage to name in `ctx.value` is given.

| Ref | Cell (row ← col) | Entries to write (component) | Source datasets / series_id | 2023-24 value | Role (tol / confidence) | Status |
|---|---|---|---|---|---|---|
| R11 | H_* ← R_ROW (total) | **none** (constraint only, §3) | `mospi_nas_2026_s6_1`: `s6_1.other_current_transfers_to_resident_sectors_other_than_gener.current` (vintage 2026-08-31, Final). X-check `external_sector_bop_bpm6_annual`: `bpm6.inr.bpm6_1_c_1.credit.current` | 9,83,127.72 (BoP 9,83,128; of which personal transfers 9,56,954, other 26,174) | constraint `equal`, tol_abs 1 | official |
| R11a | H_R1..H_U5 ← R_ROW | 10 entries, component `remittances` | `external_sector_remittance_survey`: `remit.destination_state.<in-xx>` (vintage 2025-03-19); `hh_keys` from households (built from `hces_consumption_a2_fractile_persons` `a2.hces2324.persons.*`, `a2.hces2324.avg_mpce.*`, period `2023-08/2024-07`) | Σ = 9,83,127.72; indicative rural 47%, urban 53%, H_R5 ≈ 2.34 lakh, H_U5 ≈ 2.15 lakh | free, **low** | estimated |
| R12 | R_ROW ← H_* (total) | **none** (constraint) | `mospi_nas_2026_s6_1`: `s6_1.other_current_transfers_by_resident_sectors_other_than_gener.current`. X-check `bpm6.inr.bpm6_1_c_1.debit.current` | 99,912.81 (BoP 99,913 = personal 70,093 + other 29,820) | constraint `equal`, tol_abs 1 | official |
| R12a | R_ROW ← H_U4, H_U5 | 2 entries, `outward_transfers` | `hh_keys` (consumption of H_U4, H_U5); evidence `external_sector_lrs_outward` `lrs.inr.annual.lrs_1_4/1_7/1_5.current` | Σ = 99,912.81 | free, **low** | estimated |
| R13 | E_RBI, E_NFPR, E_NBFC, E_BANK, G_CEN ← R_ROW | `reserve_asset_income` (E_RBI); `di_income`, `pi_income`, `oi_income`, `other_primary_income` (others) | total `s6_1.property_and_entrepreneurial_income_from_rest_of_the_world.current`; types `bpm6.inr.bpm6_1_b_2_1/2_2/2_3/2_4.credit.current`, `bpm6_1_b_3.credit`; keys `rbi_financial_accounts_fsf_balance_sheets` `fsf.row.liabilities.outstanding.*` | 2,80,907.32 = DI 76,977 + PI 3,609 + OI 20,442 + reserves 1,31,059 + other 48,821 | E_RBI **anchored** tol_rel 0.02; rest free, low | official (E_RBI) / estimated |
| R14 | R_ROW ← E_NFPR, E_BANK, E_NBFC, E_INSP, E_RBI, G_CEN, G_STA | `di_distributed`, `fpi_gsec_interest`, `pi_other`, `ext_assistance_interest`, `nri_deposit_interest`, `oi_other_interest`, `reserve_asset_debit`, `other_primary_income` | total `s6_1.property_and_entrepreneurial_income_to_the_rest_of_the_world.current`; types `bpm6.inr.bpm6_1_b_2_1..2_4.debit`, `bpm6_1_b_3.debit`; keys in §2.4 | 7,24,611.52 (of which R14a 1,63,704.27) = DI 4,13,327 + PI 84,419 + OI 2,04,454 + reserves 7,118 + other 15,293 | G_CEN `ext_assistance_interest` **anchored** tol_rel 0.10; the rest free (medium/low) | derived / estimated |
| R14a | R_ROW ← E_NFPR, E_BANK, E_NBFC (E_INSP) | `reinvested_earnings`, tag `FDI_reinvested_earnings` | `mospi_nas_2026_s1_9`: `s1_9.reinvested_earnings_of_foreign_companies_in_private_corporat.current`; = `bpm6.inr.bpm6_3_1_a_1_2.credit.current`; key `external_sector_fla_census` `fla.t8.*` (vintage 2024-10-11) | 1,63,704.27; indicative NFC 1,37,437 / FC 26,267 | free (NFC/FC medium; FC sub-split low) | estimated |
| K5 | K_ROW ← R_ROW | 1 entry, `total` | `mospi_nas_2026_s1_9`: `s1_9.net_capital_inflow_from_row.current`; = −`s6_1.surplus_on_current_transactions.current` | 2,08,890.71 | **fixed** | official |
| K8b | I_* ← K_ROW (RoW acquires Indian liabilities) and K_ROW ← I_* (RoW incurs liabilities, i.e. India's foreign assets) | one entry per BoP line (§2.6), component = line slug, with `bop_function` | `external_sector_bop_overall_annual` `bop_old.inr.*.net.current`; `bpm6.inr.bpm6_3*`; totals `s6_1.net_incurrence_of_foreign_liabilities.current` / `s6_1.net_acquisition_of_foreign_financial_assets.current`; FPI split `rbi_financial_accounts_hbs_gsec_ownership` `t107.*` | Σ I_*←K_ROW = 8,86,570.33; Σ K_ROW←I_* = 6,70,569.37 | BoP lines **fixed**; FPI debt I_GSEC/I_CBND split free, medium | official / estimated (FPI split) / derived (reconciliation) |
| K8c | I_RESV ← K_RBI | 1 entry, `reserve_assets` | `bpm6.inr.bpm6_3_5.debit.current` | 5,26,931 | **fixed** | official |
| D2 | R_ROW ← X_DISC | 1 entry, `cif_reconciliation` | `io_tables_sut_supply`: `supply.cif_adj.cif.current` (vintage 2026-08-31). X-check `s6_1.adjustment_for_cif_in_import_of_services.current` | 2,12,499.23649 (NAS 2,12,499.00) | **fixed** (pinned X_DISC) | official |
| S1 | satellite (goods by partner × HS chapter) | `s1_goods_by_partner` | `trade_satellites_imf_imts_fy` / `_monthly`, `trade_satellites_comtrade_fy_2324` / `_monthly_2324`, FX `external_sector_fx_inr_usd` | IMTS FY world: exports 4,37,722.41, imports 6,72,860.72 US$ mn | — | estimated (derived where pure FX conversion) |
| S2 | satellite (services by partner × EBOPS) | `s2_services_by_partner` | category totals `bpm6.inr.bpm6_1_a_b_1..13.{credit,debit}`; shares `trade_satellites_batis_2023_2024` (balanced); `external_sector_ites_survey` `ites.t5.*` (vintage 2025-11-04) | services credit 28,24,167, debit 14,76,157 | — | estimated |
| S3 | satellite (remittance source countries) | `s3_remittance_sources` | `remit.source_country.<iso3>` (27 rows, 2023-24 round) × R11 | Σ shares 99.8 → normalise; × 9,83,127.72 | — | estimated |

The block also publishes two interface satellites, `row_property_income` and `row_financial_counterparts` (§4).

### 2.1 R11 / R11a: remittances to household groups

Gap-map method: State shares of remittances × State consumption distribution, re-mapped to national quintiles. It can be followed, provided households publishes a State-level key.

1. `s_k` = `ctx.value("external_sector_remittance_survey", f"remit.destination_state.{k}", "2023-24")` / 100 for the 36 States/UTs (codes as in `pipeline/core/geo.py`; they sum to 100.0; bank channel, 30 AD banks, about 99% of value; external_sector-13).
2. `w_{k,g}` = share of State k's HCES 2023-24 consumption that falls in SAM group g. It comes from `ctx.satellite("households", "hh_keys")` (component requested in §4). **The block must not re-derive quintiles** (DESIGN_BRIEF §4). The underlying data are A2 persons × average MPCE by State × area × State fractile, placed into national rural/urban quintiles by the households block's rule (gap map R11a step 3). HCES A2 publishes class averages, not class boundaries, so the national cut points are themselves an estimate made by households.
3. `R11a_g = R11 × Σ_k s_k · w_{k,g}`, where R11 is the NAS value 9,83,127.72. The result sums to R11 exactly.
4. Record three assumptions (one estimated provenance record each, with its reason):
   - (a) The bank-channel State shares apply to all transfers from abroad. That includes BoP 1.C.1.2 "other current transfers" (26,174, e.g. grants to NPISH, which sit inside households) and non-bank channels.
   - (b) Within a State, receipts are proportional to consumption (gap map).
   - (c) The survey's State is the State of the receiving bank branch.
5. Cross-check (qualitative, via `ctx.check` where numeric): the per-capita R11a must rise with the quintile. IFPRI 2022/23 (`io_tables_ifpri_2223_datapaper`, `ifpri.t10.transfers_world.q1`..`q5`, `.rural`, `.urban`, period 2022-23, old base) gives the RoW-transfer share of household income as 2.2% in Q1 rising to 5.3% in Q5, and 2.0% rural vs 6.5% urban.
6. **Indicative result.** My rough placement used midpoint cut points between national class averages: rural 2653/3330/4085/5324, urban 4020/5300/6767/9246 ₹/month. It gives:
   - rural 47.3% / urban 52.7%;
   - H_R1 25,550; H_R5 2,34,081; H_U1 28,323; H_U5 2,15,251.

   That is top-heavy, as expected. The State pattern drives it: Maharashtra 20.5%, Kerala 19.7%, Tamil Nadu 10.4%, Telangana 8.1%, Karnataka 7.7%.

### 2.2 R12 / R12a: outward transfers by household group

- Gap map: allocate to H_U4 and H_U5 "in proportion to their income". Group income is only known at closure, and this block does not depend on closure. **Deviation:** use H_U4/H_U5 consumption from `hh_keys` as the income proxy, labelled as an estimated assumption.
- Evidence that the channel is high-income: LRS FY 2023-24 gift 29,640.95 + maintenance of close relatives 38,178.72 + donations 93.64 = 67,913.31. This is 96.9% of BoP personal transfers debited (70,093).
  - The rupee LRS series are `derived`, converted at the FY-average rate by external_sector.
  - The US$ originals are `lrs.usd.annual.*` (vintage 2024-06-19).
- Sensitivity to log: put BoP 1.C.1.2 "other current transfers" (29,820 debit) on all 10 groups by consumption share instead.
- Risk: BoP 1.C.1 debit also covers corporations. The gap map assigns all of it to households; I keep that.

### 2.3 R13: property income received from RoW, by recipient

| Component | BoP type total (credit) | Recipient rule | Confidence |
|---|---|---|---|
| `reserve_asset_income` | 1,31,059 (`bpm6_1_b_2_4.credit`) | 100% E_RBI (sole holder of reserves) | anchored, tol_rel 0.02 |
| `di_income` (includes reinvested earnings on outward FDI, 47,898 = `bpm6_3_1_b_1_2.debit`) | 76,977 (`bpm6_1_b_2_1.credit`) | FSF RoW-liability **equity stocks** by counterparty, average of 2023-03-31 and 2024-03-31: `fsf.row.liabilities.outstanding.f51.nfc_pvt.current` 12,38,043, `.f51.fc_ofc` 65,001, `.f51.fc_odc` 653 → E_NFPR 94.97%, E_NBFC 4.99%, E_BANK 0.05%. These stocks equal IIP DI + PI equity assets at end-March 2024 (12,78,482 + 91,229 = 13,69,711) | low |
| `pi_income` | 3,609 (`bpm6_1_b_2_2.credit`) | same F51 key | low |
| `oi_income` | 20,442 (`bpm6_1_b_2_3.credit`) | FSF RoW-liability interest-bearing stocks (`f22_f29`, `f3`, `f4`) by counterparty, excluding `fc_rbi` (reserves): fc_odc (3,06,834 + 28,224 + 76,120), nfc_pvt (51,478 + 7,14,105 + 34,957), gg_cen (15,343 loans), fc_ofc (1,505) → E_BANK / E_NFPR / G_CEN / E_NBFC | low |
| `other_primary_income` | 48,821 (`bpm6_1_b_3.credit`) | pro rata to the non-reserve allocations above | low (open question §6) |

- **Deviation from the gap map.** "Outward FDI income by FLA census ODI sector" cannot be done: the FLA ODI sector split was not ingested (only `fla.6.*` by country and `fla.t3b.*` totals). The FSF stock key is the fallback.
- Cross-check for E_RBI, the RBI Annual Report: Schedule 13(b) foreign-source interest `sch13.b.sub_total.current` 1,03,177.64 + Schedule 14(b)(i) amortisation `sch14.b.amortisation_of_premium_discount_on_foreign_securities.current` 2,235.86 = 1,05,413.50. Dataset `rbi_banking_corporate_rbi_accounts`, vintage `2025-05-29`, identical to 2024-05-30. The BoP figure is 25,645 (24%) higher; log it (§5).

### 2.4 R14 / R14a: property income paid to RoW, by payer

**Direct-investment income.**
- Debit 4,13,327 includes reinvested earnings of 1,63,704.27.
- `di_distributed` = 4,13,327 − 1,63,704.27 = **2,49,622.73**.
- R14a `reinvested_earnings` = **1,63,704.27** (NAS 1.9 memo = BoP 3.1.A.1.2).

**Payer split for both.**
- **NFC vs FC:** FLA 2023-24 round (vintage `2024-10-11`, the only round with end-March 2024 sector detail), market-value equity: `fla.t8.g.financial_and_insurance_activities.equity` 9,39,517 / `fla.t8.total.equity` 58,55,360 = FC **16.05%**, NFC 83.95%. Sensitivity: face value `fla.t2b.fc.fdi_equity` 98,358 / `fla.t2b.total.fdi_equity` 9,05,207 = 10.87%.
- **E_NFPU = 0.** The NAS memo is "private corporations", and the FSF has no public-NFC counterparty for RoW.
- **FC sub-split.** Foreign banks' profit after tax is taken from `rbi_banking_corporate_rtp_banks`: `rtp.scb_pl.income_total.fb.current` − `rtp.scb_pl.expenditure_total.fb.current`, vintage `2025-12-29`: 1,29,838 − 1,02,953 = **26,885**.
  - This is E_BANK's total DI income.
  - It is split distributed : reinvested in the national ratio 60.4 : 39.6.
  - The FC remainder goes to E_NBFC. If fincorp publishes a private-FC key, split it E_NBFC/E_INSP by that key; otherwise E_INSP gets 0, low confidence, logged.
- **Indicative split.** R14a: NFC 1,37,437, FC 26,267 (t2b sensitivity: 17,788). `di_distributed`: NFC 2,09,557, FC 40,066.

**Portfolio income.** Debit 84,419.
- `fpi_gsec_interest`, G_CEN:
  - FPI central G-sec holdings are `t107.gsec_central.share.fpi` × `t107.gsec_central.outstanding.current` (`rbi_financial_accounts_hbs_gsec_ownership`, dates 2023-03-31 and 2024-03-31): 1.36% × 96,45,776 = 1,31,183 → 2.34% × 1,07,40,389 = 2,51,325. The average is 1,91,254.
  - Coupon = `union_fiscal_fa_expenditure` `fa9.2049.01.101` 7,26,415.54 / average outstanding 1,01,93,083 = 7.127%.
  - Indicative interest ≈ **13,630**, plus T-bills (`t107.tbills.*`, average FPI holding 1,690, small).
- `fpi_gsec_interest`, G_STA: SDLs (`t107.sgs.*`, average FPI holding 2,469) × the same coupon ≈ **176**.
- Cross-check: FSF `fsf.row.assets.outstanding.f3.gg_cen.current` averages 2,07,218.
- DEA's quarterly ownership (`rbi_financial_accounts_dea_gsec_ownership` `qr2024_t4_4.gsec_central.share.fpi` 1.4% → 2.3%) is the second source.
- `pi_other` = 84,419 − fpi_gsec_interest ≈ 70,600. This is FPI equity dividends plus FPI/ECB-bond interest of corporations. Split NFC/FC with the FLA t8 key; low confidence.

**Other investment income.** Debit 2,04,454.
- `ext_assistance_interest`, G_CEN = `union_fiscal_fa_expenditure` `fa9.2049.02.total` **29,616.74**.
  - This is the cash figure; derived, anchored tol_rel 0.10 for cash vs accrual.
  - Implied rate on the FSF `f4.gg_cen` average of 7,77,914 is 3.8%.
- `nri_deposit_interest`, E_BANK = average NRI deposits (`external_sector_nri_deposits` `nri.stock.inr.total.current`: 11,41,818 at 2023-03-31 and 12,66,272 at 2024-03-31; average 12,04,045) × SCB cost of deposits 4.8% (`rtp.scb_cost_return.cost_of_deposits.scb`, vintage `2025-12-29`) ≈ **57,794**. Medium confidence.
- `oi_other_interest` = remainder ≈ 1,17,043. Payers are keyed by FSF RoW-asset loan and deposit stocks (average of the two dates):
  - `fsf.row.assets.outstanding.f4.{fc_odc,fc_ofc,nfc_pvt}` 1,70,960 / 2,18,262 / 5,85,191;
  - ODC deposits other than NRI: `f22_f29.fc_odc` 12,24,013 less the NRI average 12,04,045 = 19,968;
  - `f22_f29.fc_rbi` 1,425.
  - These map to E_BANK / E_NBFC / E_NFPR / E_RBI. Trade credit (`f81`) is excluded as mostly non-interest-bearing; log this.
  - Optional carve-out to E_NFPU: public-sector non-government multilateral/bilateral borrowing (`external_sector_external_debt` `debt.inr.multilateral.nongovt.nonconcessional.public.current` 49,640 + `debt.inr.bilateral.nongovt.concessional.public.current` 20,581 + `...nonconcessional.public.current` 6,132, all at 2024-03-31) as a share of NFC loans. Low confidence.

**Reserve assets and other primary income.**
- `reserve_asset_debit` 7,118 goes to E_RBI; low confidence, content undocumented. It is probably charges on SDR allocations: IIP `iipq.inr.liabilities.3.5.current` 1,82,587.
- `other_primary_income` 15,293: allocated pro rata to the other R14 allocations; low confidence.

**Resolves the gap map's Phase 1 question.** NAS 6.1 item 8 includes reinvested earnings: it equals the BoP primary-income debit less CE (7,09,318 + 15,293 = 7,24,611), and BoP DI income includes reinvested earnings under BPM6.

### 2.5 K5: RoW saving

K_ROW ← R_ROW = **2,08,890.71**, fixed.

- Source: `ctx.value("mospi_nas_2026_s1_9", "s1_9.net_capital_inflow_from_row.current")`.
- Assert it equals −`s6_1.surplus_on_current_transactions.current` (−2,08,890.71).
- `ctx.check` against the BoP current account `bpm6.inr.bpm6_1.net.current` (−2,15,248). The gap of 6,357 equals `bpm6.inr.bpm6_1_c_2.net.current` (−6,357) exactly. This is external_sector-5: NAS moves government transfers with RoW into capital transfers.
- The gap map's note ("differs from the 1.1-implied balance by the CIF adjustment") is true of NAS 1.1, but the BoP difference is 1.C.2, not CIF.

### 2.6 K8b: RoW financial account by instrument

**Source structure.**
- Functional detail comes from the old-format BoP (`external_sector_bop_overall_annual`, series `bop_old.inr.<path>.net.current`).
- It is identical, line for line, to FSF Statement 5 (`fsf.row.{assets,liabilities}.transaction.*`, vintage 2026-01-21), which I checked to the decimal.
- The BPM6 equivalents are in brackets.
- The totals must equal NAS 6.1 items 17 and 16.

**Values.** Sign as published (net flow). The "counterpart" column is the domestic K_* account that capital_financial must post in the same instrument (K7b), and it is published in `row_financial_counterparts`.

*RoW acquires Indian liabilities* (row I_x, col K_ROW):

| Line (component) | series (`bop_old.inr.… .net.current`) | Value | Instrument | bop_function | Domestic counterpart (liability) |
|---|---|---:|---|---|---|
| `fdi_equity` | `ka.fdi.in_india.equity` (BPM6 3.1.A.1.1) | 37,226 | I_EQTY | FDI_equity | K_NFPR 83.95% / FC 16.05% (FLA t8) |
| `fdi_reinvested_earnings` | `ka.fdi.in_india.reinvested_earnings`; use the NAS value 1,63,704.27 so the entry equals R14a | 1,63,704.27 | I_EQTY | FDI_reinvested_earnings | same split as R14a |
| `fdi_debt` | `ka.fdi.in_india.other_capital` (3.1.A.2) | 21,314 | I_LOAN | FDI_debt | FLA t8 key |
| `fpi_equity` | `ka.portfolio.in_india.fiis.equity` (3.2.1 in India) | 2,08,694 | I_EQTY | FPI_equity | FLA t8 key (low; FPIs are heavier in financials) |
| `fpi_debt_gsec` | part of `ka.portfolio.in_india.fiis.debt` 1,60,580 | ≈1,19,903 (central 1,20,143, T-bills −3,206, SDL +2,967) | I_GSEC | FPI_debt | K_GCEN ≈1,16,937; K_GSTA ≈2,967 |
| `fpi_debt_corporate` | remainder of 1,60,580 | ≈40,677 | I_CBND | FPI_debt | issuers, FLA t8 key (low) |
| `adr_gdr` | `ka.portfolio.in_india.gdrs_adrs` | 0 | — | — | do not write (nil) |
| `ecb` | `ka.loans.ecb.to_india` | 28,969 | I_LOAN | ECB | K_NFPR; the FC part by `external_sector_ecb_monthly_2324` registrations (borrower industry "financial service activities…" → K_NBFC). Two slugs exist for that label (external_sector-11) |
| `external_assistance` | `ka.loans.external_assistance.to_india` | 63,051 | I_LOAN | other | K_GCEN |
| `short_term_trade_credit` | `ka.loans.short_term` | −6,741 | **I_OTHR** | short_term_credit | K_NFPR |
| `nri_deposits` | `ka.banking_capital.commercial_banks.nri_deposits` | 1,21,860 | I_DEPO | NRI_deposits | K_BANK |
| `bank_other_liabilities` | `…commercial_banks.liabilities` 1,96,680 − NRI 1,21,860 | 74,820 | I_DEPO | other | K_BANK |
| `rbi_deposits` | `ka.banking_capital.others` | 10,372 | I_DEPO | other | K_RBI |
| `rupee_debt_service` | `ka.rupee_debt_service` | −597 | I_OTHR | other | K_GCEN |
| `errors_omissions` | NAS `s6_1.other_liabilities_to_non_residents.current` (= BoP `bpm6_5.net` 3,320) | 3,319.55 | I_OTHR | other | none: absorbed by capital_financial's K9 residuals |
| `nas_reconciliation_liab` | NAS item 17 − Σ lines above | ≈ −1.5 (rounding) | I_OTHR | other | K9 (derived) |
| **Total** | = `s6_1.net_incurrence_of_foreign_liabilities.current` | **8,86,570.33** | | | |

*RoW incurs liabilities, i.e. India acquires foreign assets* (row K_ROW, col I_x):

| Line (component) | series | Value | Instrument | bop_function | Domestic counterpart (asset holder) |
|---|---|---:|---|---|---|
| `odi_equity` | −`ka.fdi.abroad.equity` | 45,537 | I_EQTY | ODI | K_NFPR 94.97% / K_NBFC 4.99% (FSF F51 stock key, as R13) |
| `odi_reinvested_earnings` | −`ka.fdi.abroad.reinvested_earnings` | 47,898 | I_EQTY | ODI | same; equals the RE inside R13 `di_income` |
| `odi_debt` | −`ka.fdi.abroad.other_capital` | 44,787 | I_LOAN | ODI | K_NFPR |
| `portfolio_abroad` | −`ka.portfolio.abroad` | 4,469 | I_EQTY | other | K_NFPR (FSF) |
| `loans_by_india` | −`ka.loans.ecb.by_india` | 30,158 | I_LOAN | other | K_NFPR (FSF `f4.nfc_pvt` 30,157.52) |
| `external_assistance_by_india` | −`ka.loans.external_assistance.by_india` | 1,182 | I_LOAN | other | K_GCEN |
| `banks_foreign_assets` | −`ka.banking_capital.commercial_banks.assets` | −1,28,732 | I_DEPO | other | K_BANK |
| `other_capital` | −`ka.other_capital` | 98,450 | I_OTHR | other | K_NFPR (FSF `f81.nfc_pvt`) |
| `reserve_assets` | −`monetary_movements.reserves` (= `bpm6_3_5.debit`) | 5,26,931 | I_RESV | reserves | K_RBI (this is K8c) |
| `nas_reconciliation_assets` | NAS item 16 − Σ lines above | ≈ −110.63 | I_OTHR | other | K9 (derived) |
| **Total** | = `s6_1.net_acquisition_of_foreign_financial_assets.current` | **6,70,569.37** | | | |

**Notes on the table.**
- **The −110.63 on the asset side** has two parts:
  - NAS 6.1 "other financial assets in respect of non-residents" is 98,339.48, against FSF/old-format other capital of 98,450.04, a gap of −110.56. This is the BPM6 vs old-format presentation difference (EXT-13).
  - Integer rounding of the BoP lines accounts for −0.06.
- **Roles.**
  - BoP lines: fixed, official.
  - FPI debt split: two free entries, medium confidence, bound by constraint `row.fpi_debt` (§3).
  - Reconciliation lines: fixed, derived.
- **FPI debt split method.** The gap map's NSDL route is barred by its terms (finsector_markets-1), and the FSF's RoW holdings do not split FPI debt (it is all F51 nfc_pvt). So the split uses the change in FPI holdings, computed as HBS T107 FPI share × outstanding for central G-secs, SDLs and T-bills at the two dates. That is face value against transaction value; log it.
- **Cross-check (`ctx.check`, tolerance 3%):** SEBI/NSDL FAR/general debt `finsector_markets_sebi_foreign` `t60.net_investment.debt_general.current` 1,21,059, VRR −2,972 and hybrid 12,767.

### 2.7 K8c: change in foreign-exchange reserves

I_RESV ← K_RBI = **5,26,931**, fixed, official, from `bpm6.inr.bpm6_3_5.debit.current`. It equals:
- `bpm6_3_5_4.debit` (FCA);
- `bop_old.inr.monetary_movements.reserves.net.current` (−5,26,931);
- FSF `fsf.row.liabilities.transaction.f3.fc_rbi.current` (5,26,931.23);
- the sum of the four quarters of `external_sector_bop_bpm6_quarterly` `bpm6q.inr.bpm6_3_5.net.current`.

Do **not** use the stock change in `external_sector_fx_reserves` `t144.inr.total.current` (47,54,265 → 53,91,256, a change of 6,36,991). It includes valuation, gold price changes among them.

The matching K_ROW ← I_RESV entry is the `reserve_assets` line in §2.6, so I_RESV clears inside this block.

### 2.8 D2: NAS–BoP CIF reconciliation

R_ROW ← X_DISC = **2,12,499.23649**, fixed and pinned, from `io_tables_sut_supply` `supply.cif_adj.cif.current`.

- **Why the SUT value and not NAS 6.1's 2,12,499.00:**
  - `supply.imports.total.current` 71,59,405.269 − `supply.imports_after_cif.total.current` 69,46,906.033 = 2,12,499.236.
  - Production's P6 vector sums to 69,46,906.033, so R_ROW then closes against NAS 6.1 current disbursements (80,14,565.52) to −0.0004.
  - The NAS value would leave −0.237.
- **Assertions:**
  - `supply.cif_adj.total.current` = 0 (the memo row nets to zero; io_tables-5);
  - Σ production P6 entries + D2 = `s6_1.imports.current` 71,59,405.27, within 0.01.
- `ctx.check` D2 against the NAS 6.1 item with tol_abs 1.

### 2.9 S1: goods trade by partner and HS chapter (satellite)

1. **Partner totals** come from IMF IMTS FY 2023-24: `trade_satellites_imf_imts_fy` `imts.exports_fob.<iso3>.current` / `imts.imports_cif.<iso3>.current`. World is `g001`: 4,37,722.41 / 6,72,860.72 US$ mn.
   - 68 partner-flows with missing months (3,756 US$ mn; trade_satellites-7) go to an explicit `partner_unallocated` row, so the world total holds.
2. **Chapter split within partner** comes from Comtrade FY 2023-24 (`trade_satellites_comtrade_fy_2324` `ct.{exports,imports}.<hs2>.<iso3>.current`) for the top 30 partners.
   - For every other partner, take World chapters (`.w00`) minus the top-30 chapters, allocated by partner IMTS totals (trade_satellites-2). Label these estimated.
3. **Reconcile the two sources** with a two-margin RAS: partner margins from IMTS, chapter margins from Comtrade World scaled to the IMTS world total. Comtrade world totals are 4,36,917.90 / 6,75,387.34.
4. **Special partners.**
   - Exclude `IND` (re-imports of 7,314.9 US$ mn; trade_satellites-15) from partner shares and show it as a `reimports` row.
   - Map Comtrade `S19` to `TWN` (trade_satellites-10).
5. **Convert to rupees.** Use monthly Comtrade/IMTS × `t205.usd_month_average` where monthly rows exist. Otherwise use FY US$ × `t133.usd_fy_average` (82.7897), which is derived; follow the external_sector FX guide (filter one series_id).
6. **Do not scale S1 to SAM P5/P6.** Customs basis differs from BoP/NAS: goods credit 36,55,128 BoP / 36,67,091.58 NAS; debit 56,83,248 / 56,84,221.12.
   - Publish shares, plus an optional `value_scaled_to_nas` column.
   - There is **no HS→SAM-commodity concordance** in `data/concordance/`, so S1 stays by HS chapter (gap, §6).

### 2.10 S2: services trade by partner and EBOPS (satellite)

1. **Category totals** are official BoP FY values: `bpm6.inr.bpm6_1_a_b_{1..13}.{credit,debit}.current`, e.g. telecom/computer/information 13,54,710 credit.
2. **Partner shares per category** come from BaTIS balanced values, `batis.{exports,imports}.<ebops>.<iso3>.balanced.current`.
   - FY share = 0.75 × CY2023 share + 0.25 × CY2024 share, labelled estimated (gap map S2).
   - Use shares only, never levels: balanced exports are 66% of reported (trade_satellites-3).
3. **Override for SI (computer) exports.** RBI ITES survey regional shares (`ites.t5.<region>.share`, 2023-24, vintage 2025-11-04, e.g. USA 54.1%, UK 14.1%, rest of Europe 30.8%) set the region totals. Split to countries within each region by BaTIS.
4. **Imports memo.** S2 is on the BoP basis (14,76,157). Add a memo row, CIF adjustment −2,12,499.24 on transport and insurance, plus goods-for-processing −973, to reach NAS 1.1 services imports of 12,62,685.15.

### 2.11 S3: remittance sources (satellite)

- `remit.source_country.<iso3>` plus `others` (27 rows, 2023-24 round, vintage 2025-03-19). The shares sum to 99.8; normalise to 100 and log (external_sector-13).
- Multiply by R11, 9,83,127.72. Status estimated: the shares are bank-channel, applied to the total.
- Do not use the 2016-17 or 2020-21 rounds; their territory scope is ambiguous (external_sector-20).

## 3 Constraints to declare

Every constraint cites the NAS 6.1 / 1.9 provenance of its target. tol_abs 1 covers publication rounding (BoP is printed in whole crore).

| constraint_id | ref | rows | cols | refs filter | target (source) | tol | kind |
|---|---|---|---|---|---|---|---|
| `row.r11_total` | R11 | H_R1..H_U5 | R_ROW | [R11a] | 9,83,127.72 (`s6_1.other_current_transfers_to_resident_sectors_other_than_gener.current`) | tol_abs 1 | equal |
| `row.r12_total` | R12 | R_ROW | H_R1..H_U5 | [R12a] | 99,912.81 (`s6_1.other_current_transfers_by_resident_sectors_other_than_gener.current`) | tol_abs 1 | equal |
| `row.r13_total` | R13 | E_NFPU, E_NFPR, E_RBI, E_BANK, E_NBFC, E_INSP, G_CEN, G_STA | R_ROW | [R13] | 2,80,907.32 (`s6_1.property_and_entrepreneurial_income_from_rest_of_the_world.current`) | tol_abs 1 | equal |
| `row.r14_total` | R14 | R_ROW | the same 8 E_*/G_* accounts | [R14, R14a] | 7,24,611.52 (`s6_1.property_and_entrepreneurial_income_to_the_rest_of_the_world.current`) | tol_abs 1 | equal |
| `row.r14a_total` | R14a | R_ROW | E_NFPU, E_NFPR, E_BANK, E_NBFC, E_INSP | [R14a] | 1,63,704.27 (`s1_9.reinvested_earnings_of_foreign_companies_in_private_corporat.current`) | tol_abs 1 | equal |
| `row.current_receipts` | K5 | all 34 C_*, F_LREG, F_LCAS, F_MIXD, F_GOSC, H_*, E_*, G_CEN, G_STA | R_ROW | none | 78,05,674.80 (`s6_1.current_receipts.current`) | tol_abs 1 | equal |
| `row.current_disbursements` | K5 | R_ROW | all C_*, F_*, H_*, E_*, G_*, X_DISC | none | 80,14,565.52 (`s6_1.current_disbursements.current`) | tol_abs 1 | equal |
| `row.k8b_liabilities_to_row` | K8b | all 11 I_* | K_ROW | [K8b] | 8,86,570.33 (`s6_1.net_incurrence_of_foreign_liabilities.current`) | tol_abs 1 | equal |
| `row.k8b_assets_from_row` | K8b | K_ROW | all 11 I_* | [K8b] | 6,70,569.37 (`s6_1.net_acquisition_of_foreign_financial_assets.current`) | tol_abs 1 | equal |
| `row.fpi_debt` | K8b | I_GSEC, I_CBND | K_ROW | [K8b] | 1,60,580 (`bop_old.inr.ka.portfolio.in_india.fiis.debt.net.current`) | tol_abs 1 | equal |

**Notes on the constraints.**
- `row.current_receipts` and `row.current_disbursements` are the BoP acceptance totals (SPEC §6(c)). They cover other blocks' entries: production's P5 and P6, factors' V3 and V4, and any R15. So they turn a government R15 current transfer, or a wrong P6/V3/V4, into a visible slack rather than a silent imbalance. Framework request: confirm a block may declare such cross-block acceptance constraints.
- **BoP type totals cannot be constraints.** Examples are DI 4,13,327 and OI 2,04,454. They are components inside the same cells, and constraints filter only on rows, cols and refs.
  - The prior satisfies them exactly.
  - The block test reports how far balancing moves them.
  - If they must bind, the framework would need a `components` filter (optional request).
- **Fixed entries need no constraint:** K5, K8c, D2 and the BoP K8b lines.

## 4 Interfaces

### Needs (DEPENDS = ["production", "households"], as allowed)

- **production** (`ctx.block_entries("production")`):
  - P5 entries (C_* ← R_ROW), Σ must be 64,79,295.53 = `use.exports.total.current`;
  - P6 entries (R_ROW ← C_*), Σ must be 69,46,906.03 = `supply.imports_after_cif.total.current`;
  - used for the D2 consistency assertion and the R_ROW closure check. If P6 were uncorrected for CIF, D2 would double-count 2,12,499.
- **households** (`ctx.satellite("households", "hh_keys")`). Requested components:
  - `state_area_group_consumption`: for each State/UT (36 codes, D1-9) × area (rural/urban) × SAM group, HCES 2023-24 consumption placed on **national** quintiles with the households block's rule. Each State's 10 values should sum to its HCES total. The government block's R10 needs the same key (gap map R11a note).
  - `group_consumption_share` (national, 10 groups): for R12a.
  - Group codes and HCES population by group: for per-capita plausibility checks.
  - If households will not publish the State-level component, that is a FRAMEWORK_REQUEST. The fallback (State area totals × national within-area shares) is lower quality and must be logged.

### What other blocks must do (they are not dependencies of this block)

- **factors** writes V3 = 62,344.24 (`s6_1.compensation_of_employees_from_rest_of_the_world.current`) and V4 = 30,635.91 (`…_to_the_rest_of_the_world.current`), both on F_LREG. Other values break `row.current_*`.
- **government:**
  - **R15 not written** (or recorded only in a memo satellite) for 2023-24.
  - K6 RoW entries on the NAS basis, so that K_ROW closes (net 7,110.25 paid by India):
    - `s6_1.capital_transfers_to_general_government_from_the_rest_of_the.current` −6,999.68;
    - `s6_1.capital_transfers_to_corporations_households_and_npishs_net.current` +1,555.69;
    - `s6_1.acquisitions_less_disposal_of_non_produced_non_financial_ass.current` −1,666.26.
- **fincorp:**
  - R3a and R8 must not write the R_ROW row. The RoW-held parts are here: `fpi_gsec_interest`, `ext_assistance_interest`, `di_distributed`, `pi_other`.
  - R4 must leave NRI-deposit interest out of bank deposit interest.
  - R5 and the bank income totals must leave out foreign-source interest (R13 `oi_income`).
  - E_RBI's current account must not add RBI AR foreign-source income (R13 `reserve_asset_income` covers it).
  - fincorp needs `row_property_income` to subtract the RoW parts from its totals. That requires **fincorp DEPENDS += rest_of_world**; there is no cycle (FRAMEWORK_REQUEST).
- **capital_financial** (already depends on rest_of_world):
  - read `row_financial_counterparts` and post every mirror entry in the same instrument (K7b);
  - **drop every FSF RoW-counterparty cell** in FSF St 5 and in the sector statements;
  - K8d must exclude K_ROW, because FPI G-sec purchases are in K8b;
  - do not map RBI's foreign securities or deposits to I_GSEC/I_CBND/I_DEPO, because K8c covers them;
  - absorb `errors_omissions` and the two `nas_reconciliation_*` lines in K9 (I_OTHR).
- **closure** must handle the X_DISC rounding: D1 − D2 − D3 − D4 = 5,71,133.27 − 2,12,499.24 − 3,58,633.93 − 0 = **0.1075** (≥ ₹0.01) with all cells pinned (§5).

### Publishes

- **Entries** as in §2 and **constraints** as in §3.
- Satellite `s1_goods_by_partner`: partner (ISO3 or group) × HS2 × flow, in US$ mn and ₹ crore, with share columns.
- Satellite `s2_services_by_partner`: partner × EBOPS × flow.
- Satellite `s3_remittance_sources`: country × share × ₹ crore.
- Satellite `row_property_income`: direction (credit/debit) × BoP type (DI/PI/OI/reserves/other_primary) × component × domestic account (E_*/G_*) × value, with prov_ids. fincorp and government read it.
- Satellite `row_financial_counterparts`: K8b line × SAM instrument × bop_function × direction (`row_acquires` = India's liability, `row_incurs` = India's asset) × domestic counterpart K_* (or `unallocated_k9`) × value. capital_financial reads it for K7b.
- Optional satellite `row_accounts_check`: the R_ROW and K_ROW closure table, for tests and BALANCING.md.

## 5 Conflicts and choices

| # | Item | Source A (control) | Source B (cross-check) | Difference | Recommendation and why |
|---|---|---|---|---|---|
| 1 | RoW saving (K5) vs BoP current account | NAS 1.9 NCI 2,08,890.71 = −NAS 6.1 surplus | BoP CA −2,15,248 | 6,357 = BoP 1.C.2 net government transfers | **NAS control.** D3 (S-I errors 3,58,633.93) is defined with this NCI, and X_DISC and the capital accounts depend on it. Government transfers with RoW are capital (K6, −6,999.68 net), so **R15 = 0**. Writing R15 from BoP (1,463 / 7,820) as well as K6 double-counts about 6,357 to 7,000 (external_sector-5). |
| 2 | D2 value | SUT CIF row 2,12,499.24 | NAS 6.1 item 18 2,12,499.00 | 0.24 | **SUT control.** It is consistent with production's P6 vector, so R_ROW closes to −0.0004 instead of −0.24. |
| 3 | Reserve-asset income (R13 E_RBI) | BoP 1.B.2.4 credit 1,31,059 | RBI AR Sch 13(b) + 14(b)(i) 1,05,413.50 | +25,645 (+24%) | **BoP control.** It is part of the NAS 6.1 item 3 total that R_ROW must meet. Anchored ±2%, explanation logged. Candidates: accrual vs RBI accounting, and income on gold/SDR/RTP. Unverified. fincorp must not also add the RBI AR figure. |
| 4 | FPI net flows | BoP 3.2.A 3,69,273 | SEBI/NSDL `t59.net_investment.current` 3,39,065 | +30,208 (+8.9%, EXT-15 xfail) | **BoP control** for K8b. NSDL/SEBI only as a markets cross-check (RECONCILIATION #12). |
| 5 | FDI to India | BoP 3.1.A 2,22,244 | HBS T143 and SEBI T58, both 2,22,244 | 0 | Agree (same RBI compilation). |
| 6 | Financial account totals | NAS 6.1 items 16/17: 6,70,569.37 / 8,86,570.33 | FSF St 5 RoW: 6,70,679.94 / 8,83,250.79 | −110.57 assets; liabilities +3,319.55 (E&O) | **NAS control.** Totals come from NAS; E&O becomes an I_OTHR line; the −110.63 BPM6-vs-old-format difference becomes a derived reconciliation line (K9). |
| 7 | NRI deposits flow | BoP 1,21,860 | HBS T139–142 `nri.flow.inr.total.current` 1,21,715 | 145 | BoP control; check within 0.5%. |
| 8 | Reserves change | BoP flow 5,26,931 | stock change 6,36,991 (T144) | valuation | Flow only (gap map K8c). |
| 9 | Reinvested earnings | NAS 1.9 memo 1,63,704.27 | BoP 3.1.A.1.2 1,63,704 | 0.27 | NAS control, used for both R14a and K8b so income and flow match exactly. |
| 10 | Property income totals | NAS 6.1 items 3/8: 2,80,907.32 / 7,24,611.52 | BoP 2,80,907 / 7,24,611; invisibles 7,24,612 | ≤ 1 | NAS control (rounding). |
| 11 | FPI share of G-secs | HBS T107 1.36% → 2.34% | DEA QR 1.4% → 2.3% | presentation | HBS control (2 decimals, with outstanding amounts in the same table). |
| 12 | FDI NFC/FC key | FLA t8 market value, FC 16.05% | FLA t2b face value, FC 10.87% | 5.2 pts | t8 control (reflects accumulated earnings); t2b as a logged sensitivity. Use the 2023-24 round (2024-10-11) consistently; the 2024-25 round revises end-March 2024 but has no t2b/t8 at that date (external_sector-12). |
| 13 | ROW ← GOV interest ownership | gap map R14 (cols NFC; FC; **GOV**) | gap map R3a (rows include **ROW**) | same cell | **rest_of_world owns it** (under R14), because it holds the binding BoP/NAS totals. fincorp's R3a covers domestic holders only. |
| 14 | Dividends to foreigners | R14 (this block) | R8 (fincorp: "RoW part matched to BoP") | same flows | **R14 owns them.** R8 writes no R_ROW entries. |
| 15 | Trade credit instrument | gap map K8b: "ECB & trade credit → I_LOAN" | SNA F81 and the ACCOUNT_STRUCTURE §7 FSF map (F8 → I_OTHR) | classification | **I_OTHR**, tags `short_term_credit` / other. This keeps the RoW side and capital_financial's FSF-based domestic trade credit in one instrument; otherwise every trade-credit rupee becomes a K7b re-posting. It deviates from the gap-map text. |
| 16 | FDI/FPI instruments | BoP functional split (equity/debt, G-sec/corporate) | FSF St 5: all FDI+FPI in F51 with nfc_pvt | classification and counterparty | **BoP split.** FSF's lumping puts FPI G-sec purchases on private NFCs. The K9 residuals absorb the resulting sector-balance shifts, and they are logged. |
| 17 | Goods exports | NAS 6.1 goods 36,67,091.58 | BoP goods 36,55,128; IMTS 4,37,722 US$ mn | goods for processing 11,963; customs vs BoP | S1 is a satellite on customs data; not scaled to SAM cells. |
| 18 | Government transfers, BPM6 vs old format | BPM6 1.C.2: 1,463 / 7,820 (net −6,357) | old-format official transfers: 1,558 / 8,557 (net −7,000 = NAS −6,999.68) | 643 | Irrelevant once R15 = 0 (item 1). NAS K6 uses the old-format net. |

## 6 Risks, gaps, open questions

**Double-counting risks** (each gets a test or an interface rule):
1. R15 (government) + K6 RoW (government) + K5: government transfers with RoW counted as both current and capital (item 1).
2. R14 vs fincorp R3a: interest on external assistance (29,616.74) and on FPI-held G-secs (≈13,630 central, plus small T-bill and SDL parts).
3. R14 vs fincorp R8: dividends to FDI and FPI holders.
4. R14 NRI-deposit interest (≈57,794) vs fincorp R4 bank deposit interest (STRBI totals include NRI deposits).
5. R13 reserve income (1,31,059) vs fincorp's E_RBI current account from RBI AR foreign income.
6. R13 `oi_income` to banks vs fincorp R5 bank interest income totals.
7. R14 DI debit (4,13,327) already includes R14a (1,63,704.27). R14 must use `di_distributed` = 2,49,622.73.
8. K8b vs capital_financial's FSF RoW-counterparty cells, if FSF cells are kept rather than replaced.
9. K8b FPI G-sec purchases vs K8d, whose holder list includes K_ROW.
10. K8c vs FSF RBI statement: foreign F3/F22 assets with RoW counterparty.
11. D2 vs P6: P6 must be the CIF-adjusted SUT column, or D2 double-counts.
12. Tourism is embedded in the SUT product rows (Q3). **No** ROW↔HH purchase cells may be added by households.

**Where the gap-map method cannot be followed as written, and the fallback:**
- **R13:** the FLA ODI sector split is not ingested. Fallback: FSF RoW-liability F51 stocks by counterparty, which are official and equal IIP equity assets.
- **R14:** "ECB interest by borrower sector". Only loan-level registrations (flows, `external_sector_ecb_monthly_2324`) exist, not stocks by sector. Fallback: FSF RoW-asset loan and deposit stocks by counterparty. "FPI debt interest by holdings": no NSDL, so HBS T107 × outstanding for government paper; the corporate part is residual.
- **R14 / R3a:** the gap map claims the ROW ← GOV cell for both refs. Resolved in favour of R14 (§5 item 13).
- **R14a:** there is no FC sub-sector split. Fallback: foreign banks' profit (RTP) for E_BANK, remainder to E_NBFC (E_INSP needs a fincorp key).
- **R11a step 3:** national MPCE boundaries are not published. households estimates them once, in `hh_keys`.
- **R12a:** "in proportion to income" is replaced by consumption (income by group only exists at closure).
- **K8b:**
  - FPI-debt split: NSDL is barred by its terms, and FSF RoW holdings do not split it. Fallback: HBS T107 × outstanding.
  - Trade credit goes to I_OTHR, not I_LOAN.
  - FSF counterparties for FDI/FPI are replaced.
- **S1:** there is no HS→SAM concordance; S1 stays by HS chapter. The Comtrade chapter split exists for the top 30 partners only (81.9% of trade); the rest is estimated.
- **S2:** BaTIS is calendar-year and its levels are unusable, so shares only; the SI override uses ITES regions (coarser than countries).

**Open questions and residual risks:**
- **"Other primary income"** (BPM6 1.B.3: credit 48,821, debit 15,293). Its content is not documented in the ingested tables. It is allocated pro rata, with low confidence. Question for RBI/NAD: does it include rent, taxes on production, or something else?
- **"Reserve assets" debit 7,118.** Probably charges on SDR allocations (IIP SDR liabilities 1,82,587), assigned to E_RBI. It might belong to G_CEN.
- **FSF RoW-liability `f3.nfc_pvt` stock** (6,86,745 → 7,41,466) nearly mirrors the RoW-asset `f3.nfc_pvt` stock (6,45,379 → 7,41,964). It dominates the `oi_income` key; check that it is not an FSF mirroring artefact before relying on it. If in doubt, drop F3 from the R13 OI key and log it.
- **FSF RoW-asset F3** (all counterparties, 12,25,497 at end-March 2024) = IIP PI debt securities 9,60,283 + DI debt 2,65,214. So `f3.nfc_pvt` includes intercompany debt. Do not use it as an FPI-bond key without netting DI debt.
- **Remittance survey caveats:** it covers banks only, and a State is where the receiving branch sits. Maharashtra (20.5%) and Delhi (4.3%) may be inflated as banking hubs, so R11a leans to urban and top groups; show a sensitivity band.
- **Public/private splits** of FDI and ECB payers are rough; public NFCs and public FIs (EXIM, REC, PFC) borrow abroad. E_NFPU gets only the optional external-debt carve-out.
- **X_DISC rounding:** 0.1075 crore with every cell pinned. Needs a closure/framework rule: either a documented ≤ ₹1 crore rounding allowance for X_DISC, or absorbing it in the (estimated) D1 or D3 allocation.
- **IMF IMTS licence** ("All Rights Reserved"; trade_satellites-11) and DGCI&S permission are pre-launch blockers for publishing S1, but not for building it.
- **Vintage mix:** FSF (old base, 2026-01-21) supplies keys only, never levels. The BoP (HBS 2025-26, 2026-07-31) and NAS 2026 (2026-08-31) supply all levels.

**Framework requests to file** (`docs/phase2/FRAMEWORK_REQUESTS.md`):
1. **fincorp DEPENDS += rest_of_world**, so R3a, R8, R4 and R5 can subtract the RoW parts from `row_property_income`. There is no cycle.
2. **hh_keys `state_area_group_consumption`** (households).
3. **X_DISC rounding rule** (closure / framework).
4. **Confirm that cross-block acceptance constraints are allowed** (`row.current_receipts`, `row.current_disbursements`).
5. **Optional:** a `components` filter on constraints, to bind BoP type totals.
6. **Optional:** bop_function tags `external_assistance`, `banking_capital`, `errors_omissions`, `portfolio_abroad`. Until then these use `other` with a descriptive component.

## 7 Tests the builder should write

All targets are read from clean data with `ctx.value`, never typed in. Tolerances are in ₹ crore.

1. **Current transfers.**
   - Σ R11a = `s6_1.other_current_transfers_to_resident_sectors_other_than_gener.current` (±1), and it matches `bpm6.inr.bpm6_1_c_1.credit.current` and `invis.inr.private_transfers.receipts.current` (±1).
   - Every R11a entry is ≥ 0.
   - The hh_keys State weights sum to 1 for each State.
   - The survey State shares sum to 100 (±0.05).
2. **Outward transfers.** Σ R12a = `s6_1.other_current_transfers_by_resident_sectors_other_than_gener.current` (±1) = `bpm6.inr.bpm6_1_c_1.debit.current` (±1). Only H_U4 and H_U5 are non-zero.
3. **Property income received.**
   - Σ R13 = `s6_1.property_and_entrepreneurial_income_from_rest_of_the_world.current` (±1).
   - Each BoP type component sum equals its `bpm6.inr.bpm6_1_b_2_{1..4}.credit` / `bpm6_1_b_3.credit` series in the prior (±1).
   - E_RBI `reserve_asset_income` = `bpm6_1_b_2_4.credit`.
4. **Property income paid.**
   - Σ R14 + R14a = `s6_1.property_and_entrepreneurial_income_to_the_rest_of_the_world.current` (±1) = `invis.inr.income.investment.payments.current` (±1).
   - Σ R14 `di_distributed` + R14a = `bpm6_1_b_2_1.debit` (±1).
   - G_CEN `ext_assistance_interest` = `fa9.2049.02.total` in the prior.
5. **Reinvested earnings.**
   - Σ R14a = `s1_9.reinvested_earnings_of_foreign_companies_in_private_corporat.current` = `bpm6.inr.bpm6_3_1_a_1_2.credit.current` (±1).
   - K8b `fdi_reinvested_earnings` equals Σ R14a exactly.
   - K8b `odi_reinvested_earnings` = `bpm6.inr.bpm6_3_1_b_1_2.debit.current`.
6. **RoW saving.**
   - K5 = `s1_9.net_capital_inflow_from_row.current` = −`s6_1.surplus_on_current_transactions.current` (±0.01).
   - Identity: K5 + `bpm6.inr.bpm6_1.net.current` = `bpm6.inr.bpm6_1_c_2.net.current` (2,08,890.71 − 2,15,248 = −6,357, ±1). This pins external_sector-5.
7. **D2.**
   - D2 = `supply.cif_adj.cif.current`.
   - `supply.imports.total.current` − `supply.imports_after_cif.total.current` = D2 (±0.01).
   - |D2 − `s6_1.adjustment_for_cif_in_import_of_services.current`| ≤ 1.
   - Σ production P6 + D2 = `s6_1.imports.current` (±0.01).
8. **R_ROW closes in the prior.** Using production P5/P6 entries, V3/V4 read from clean NAS 6.1, and this block's entries: row − col within ±0.01. Row = `s6_1.current_disbursements.current`; col − K5 = `s6_1.current_receipts.current` (±1). Assert no entry with ref R15 in the assembled prior (integration test).
9. **K_ROW closes.**
   - Σ I_* ← K_ROW = `s6_1.net_incurrence_of_foreign_liabilities.current` (±1).
   - Σ K_ROW ← I_* = `s6_1.net_acquisition_of_foreign_financial_assets.current` (±1).
   - Their difference = −`s6_1.net_lending_to_the_rest_of_the_world_13_14_15_16_or_18_19.current` (±1) = −(`bpm6.inr.bpm6_1.net.current` + `bpm6.inr.bpm6_2.net.current`) (EXT-7).
   - With government's K6 RoW entries, K_ROW row = col (±0.01; integration test).
10. **K8b reproduces BoP.**
    - FDI-in-India lines sum to `bpm6.inr.bpm6_3_1_a.net.current` (2,22,244 ±1).
    - FPI-in-India lines sum to `bpm6.inr.bpm6_3_2_a.net.current` (3,69,273 ±1).
    - `nri_deposits` = `bop_old.inr.ka.banking_capital.commercial_banks.nri_deposits.net.current`.
    - ODI lines sum to −`bpm6.inr.bpm6_3_1_b.net.current` (1,38,223 ±1).
    - `errors_omissions` = `s6_1.other_liabilities_to_non_residents.current` and `bpm6.inr.bpm6_5.net.current` (±1).
    - |each reconciliation line| ≤ 150.
    - Every K8b entry has a bop_function in `spec.BOP_FUNCTIONS`, and K_ROW is its row or column.
11. **FPI debt.**
    - I_GSEC + I_CBND ← K_ROW = `bop_old.inr.ka.portfolio.in_india.fiis.debt.net.current` (±1).
    - The G-sec part equals Δ(FPI share × outstanding) from `t107.*` (±1).
    - `ctx.check` vs SEBI `t60` debt (3%).
12. **Reserves.**
    - K8c = `bpm6.inr.bpm6_3_5.debit.current` = FSF `fsf.row.liabilities.transaction.f3.fc_rbi.current` (±1) = the sum of the four quarters of `bpm6q.inr.bpm6_3_5.net.current` (sign-adjusted, ±1).
    - I_RESV row = col inside the block.
13. **Counterparts.** `row_financial_counterparts` has one row per K8b entry with a non-null counterpart (or `unallocated_k9`), and the same total as the K8b entries.
14. **Keys and satellites.**
    - FLA shares come from vintage 2024-10-11 only.
    - S3 normalised shares sum to 1 and × R11 = R11.
    - S1 FY US$ totals reproduce `imts.exports_fob.g001.current` / `imts.imports_cif.g001.current`, allowing for the explicit unallocated and re-import rows.
    - S1 rupee values use the external_sector FX series only.
    - S2 category totals reproduce the `bpm6_1_a_b_*` credits and debits (±1).
    - S2 SI exports by region reproduce `ites.t5.*.share` (±0.05 pt).
15. **Structure and provenance.**
    - No FAC entries in R13/R14 (property income is not factor income).
    - Every estimated record has a method naming its key and its assumption.
    - The FX-converted records cite the `INR_per_USD` prov_id.

The independent verifier recomputes items 1–12 with DuckDB from the clean Parquet (not the builder's code).

---

## 8 Cross-plan review (2026-09-30, cross-plan critic; details and ids in `CROSS_REVIEW.md`)

What this block must change or confirm:

1. **XR-4 E_RBI reserve income (decision D-4).** Keep the R13 total at NAS 6.1 item 3 (2,80,907.32), but write E_RBI as two components:
   - `reserve_asset_income` = RBI AR `sch13.b.sub_total` 1,03,177.64 + `sch14.b` amortisation 2,235.86 = 1,05,413.50 (checked), anchored 0.02;
   - `reserve_income_unexplained` = BoP 1,31,059 − 1,05,413.50 = 25,645.50, free, low.

   fincorp's evidence for the cash-basis RBI surplus (E_RBI saving vs NAS public FC saving, within ₹122 cr) holds only with the AR figure. Balancing can then place the unexplained part transparently.
2. **XR-12 FPI interest on G-secs.** Use fincorp's formula so the Union payer constraint (which includes R14) adds up: average T107 FPI share (1.36% → 2.34%, checked) × the payer interest line net of the pro-rata re-issue receipts. The same for SDLs and T-bills. That gives ≈ 13,439 instead of 13,630. Record it in `row_property_income`.
3. **XR-13 RoW FISIM:** confirmed. Follow NAS: no FISIM adjustment on R13/R14. Say so in the R14 method text; fincorp logs the exported FISIM (29,793.73) as having no interest counterpart.
4. **XR-10 households key:** the State key is published as `hh_state_xwalk`. Households will add consumption levels, so it is not a `state_area_group_consumption` component of `hh_keys`. For R12a use `pfce_total` (or `hces_total`) of H_U4/H_U5 from `hh_keys`.
5. **XR-14:** government will make its K6 RoW entries net to NAS −6,999.684747. Your K_ROW closure test should use the NAS values (NPNFA is published **+1,666.26**, India acquiring; it enters net lending with a minus sign).
6. **XR-18 DAG:** fincorp will depend on you. Nothing changes in your DEPENDS. Publish `row_property_income` with the E_RBI split and the FPI formula above.
7. **XR-6 boundary:** FC sub-splits (R14/R14a/K8b counterparts) use E_BANK ≡ K_BANK ≡ FSF ODC, which includes deposit-taking NBFCs and HFCs.
8. **Confirmed consistent across plans:**
   - no R15 (government agrees);
   - you own every R_ROW ↔ domestic property-income cell (fincorp and timeseries agree);
   - R14 = item 8 − R14a;
   - K8b `fdi_reinvested_earnings` = R14a with the same payer split;
   - trade credit → I_OTHR and the FPI debt split are accepted by capital_financial;
   - D2 uses the SUT CIF (closure and capital_financial agree), and the X_DISC rounding is solved by closure's rule (XR-16);
   - `row.current_receipts/disbursements` as cross-block constraints are allowed (FRAMEWORK_REQUESTS P-6).
9. The components filter now exists (P-1), so the BoP type totals (DI/PI/OI/reserves/other) can be declared as `equal` constraints if you want them to bind.
