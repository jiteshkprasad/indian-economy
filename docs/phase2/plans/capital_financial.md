# Block plan: `capital_financial` (capital accounts, inventories, financial instruments, K9 residuals)

Written 2026-09-30 by the capital_financial data scout. Research only: no code under `pipeline/`, no `pipeline build/sam/repro` run. Every number below was read from `data/clean/<unit>/*.parquet` with polars (scratch scripts outside the repo), not from memory. Amounts are ₹ crore, current prices, FY 2023-24, unless stated. Digit grouping follows the data (western).

- **Refs owned:** I1a I2 I2a I3a K1 K4 K7 K7a K7b K8 K8a K8d K9 K9b D3; satellites S4 S5.
- **DEPENDS (brief):** production, rest_of_world, government, fincorp. **Requested addition:** households (for `hh_keys` in S5; acyclic, FR-cf-1 in §6.5).
- **Sibling plans read for interfaces:** `rest_of_world.md`, `government.md`, `fincorp.md`, `closure.md`, `households.md` (all in this folder). Where they already fixed a choice that touches this block, this plan follows it and says so.

---

## 1 Summary (plain English)

1. This block fills the SAM's "investment and financing" corner: who buys the country's machines, buildings and software (GFCF by commodity × investor), who holds inventories and gold, how much each sector saves, and how each sector's surplus or deficit is financed through 11 financial instruments (deposits, loans, G-secs, equity, and so on).
2. The physical side is solid. NAS 2026 publishes GFCF by sector and asset (St 1.11) and gross capital formation by sector (St 1.14); the SUT publishes GFCF by product. Only the product × investor matrix and a few sub-sector splits (banks vs NBFCs, Centre vs States) are estimated.
3. The financial side is the hard part. The only from-whom-to-whom source is RBI's Flow of Funds (FSF 2023-24, Jan 2026), which is on the old GDP base. **New finding:** the FSF does not clear instrument by instrument. Holders report ₹19.5 lakh cr of equity purchases while issuers report ₹3.6 lakh cr of issuance, and insurance, loans, deposits and "other" are off by ₹2-4 lakh cr each. The gap map assumed FSF "clears by construction"; it does not. So FSF cannot be copied into the SAM as fixed official cells.
4. The plan reconciles FSF pair by pair: for each instrument, the side with the better data wins (deposit-takers for deposits, governments for G-secs, lenders for loans, holders for equity and bonds). Households are then replaced by NAS 5.3 and the rest of the world by the BoP, with every difference posted to the named counterparty (the gap map's K7b rule). Each sector's leftover goes to "other accounts" (I_OTHR) as its K9 residual, one entry per sector, with a four-way breakdown published.
5. A scratch prototype suggests this reconciliation removes most of the "unexplained" NAS-vs-FSF gaps in RECONCILIATION.md: the public-NFC gap of −₹6.7 lakh cr shrinks to about +₹0.6 lakh cr, mainly because FSF's public-NFC statement covers CPSEs, power and ports only, while lenders' and the Centre's reports (Railways' budget support alone is ₹2.4 lakh cr) cover all public NFCs. The builder's numbers will differ; the direction is the point.
6. The FIN-1 household gap (+₹2.95 lakh cr, an xfail) is mostly an artefact: NAS 1.14 GCF excludes valuables, but NAS household saving includes gold (₹1,72,127 cr). Net of gold the gap is ₹1,23,052 cr, which RBI's own Sept 2026 revision explains (HH-9).
7. The HDFC merger needs no separate adjustment inside the SAM: HDFC Ltd was a deposit-taking HFC, which FSF counts inside "other depository corporations" (= K_BANK). So the merger is internal to K_BANK, and the holder/lender control rules remove its reclassification artefacts. A merger memo is published in S4.
8. Main risks: the K9 residuals will still be lakh-crore-sized for some sectors; a few FSF quirks (insurers' equity, SIDC/SFC holdings) need rules; and the RBI-surplus basis (cash vs accrual) in NAS general-government saving is uncertain (§6.4 Q1).

---

## 2 Ref by ref

### 2.0 Conventions for the builder

- **Accounts.** K_HH, K_NFPU, K_NFPR, K_RBI, K_BANK, K_NBFC, K_INSP, K_MUTF, K_GCEN, K_GSTA, K_ROW; K_DSTK; I_CURR, I_DEPO, I_LOAN, I_GSEC, I_SSAV, I_CBND, I_EQTY, I_MFUN, I_INPE, I_RESV, I_OTHR; X_DISC. Rows receive, columns pay. An asset acquisition is `I_x ← K_s` (row I_x, col K_s); a liability incurred is `K_s ← I_x`.
- **FSF extraction.** Dataset `rbi_financial_accounts_fsf_balance_sheets`, vintage 2026-01-21 (single vintage), `estimate_stage` n.a.
  - Transactions: `period='2023-24'`, `dim_other='measure=transaction'`. Stocks: `period='2023-03-31'`/`'2024-03-31'`, `measure=outstanding`.
  - Series id pattern: `fsf.<institution>.<side>.transaction.<instrument>.<counterparty>.current`, e.g. `fsf.gg_cen.liabilities.transaction.f22_f29.hh.current` = 421,678.3467.
  - Rows are **not additive** (rbi_financial_accounts-20). Use leaf institutions and leaf counterparties only. Counterparties: `fc_rbi, fc_odc, fc_ofc, gg_cen, gg_sta, hh, nfc_pub, nfc_pvt, other_resident, row`. Never `residents` or `gg`. "Unallocated" = `all` − Σ leaf counterparties.
  - Use component rows for RBI F6 (whose printed total exceeds its components by 2,566) and for the money-market-MF F8 (+1,100 hierarchy error) (rbi_financial_accounts-4). For the MF sector use counterparty rows, not the residents subtotal (rbi_financial_accounts-3).
- **FSF sub-sector → SAM capital account.**

  | SAM | FSF leaf institutions (statement) |
  |---|---|
  | K_HH | `hh` (St 4), replaced by NAS 5.3 |
  | K_NFPU | `nfc_pub` (St 2.1: CPSEs, ports, power only) |
  | K_NFPR | `nfc_pvt` (St 2.2) |
  | K_RBI | `fc_rbi` (St 1.1) |
  | K_BANK | `fc_odc` = `fc_odc_scb` + `fc_odc_coop` + `fc_odc_nbfc_dt` + `fc_odc_hfc_dt` (St 1.2.x). HDFC Ltd was in `fc_odc_hfc_dt` |
  | K_NBFC | `fc_ofc_aifi` + `fc_ofc_nbfc_ndt` + `fc_ofc_hfc_ndt` + `fc_ofc_sfc` + `fc_ofc_sidc` (St 1.3.1-1.3.5) |
  | K_MUTF | `fc_ofc_mf` (St 1.3.6) |
  | K_INSP | `fc_ofc_icpf` = `fc_ofc_icpf_ins` + `fc_ofc_icpf_pf` (St 1.3.7) |
  | K_GCEN / K_GSTA | `gg_cen` (St 3.1) / `gg_sta` (St 3.2) |
  | K_ROW | `row` (St 5): not used for values. rest_of_world writes all K_ROW cells from the BoP |

- **Entry components** (unique per row, col, ref, component):
  - domestic-counterparty part from reconciled FSF: component `dom`, ref K7 (assets), K8 (liabilities), K8d (I_GSEC holders);
  - household-facing counterpart part: component `hh_cp`, ref K7b;
  - RoW-facing counterpart part: component `row_cp:<bop_function>`, ref K7b, with `bop_function` set;
  - FSF trade credit and other payables as each sector reports them: component `fsf_f81` / `fsf_f89`, ref K7/K8;
  - K9 residual: one entry per sector, component `residual`, ref K9; K9b as its own components.
- **Keys with mixed signs.** Any allocation of a control total T over units with reported values r_i (any sign) uses the absolute-share adjustment x_i = r_i + (T − Σr)·|r_i|/Σ|r|. If Σ|r| = 0, use the stated default counterparty. Log every use.
- **No zero entries.** Do not write zero-valued entries (DESIGN_BRIEF §3, D4 rule), e.g. public-FC inventories are 0.00.

### 2.1 Ref-by-ref table

Role key: F = fixed, A = anchored (tol_rel), Fr = free (confidence).

| Ref | Cell | Entries to write | Source datasets / series | 2023-24 values | Role | Method (details in the section named) | Status |
|---|---|---|---|---|---|---|---|
| I1a | C_x ← K_s (x = 12 commodities with GFCF; s = K_HH, K_NFPU, K_NFPR, K_RBI, K_BANK, K_NBFC, K_INSP, K_GCEN, K_GSTA) | ≤ 108 entries, component `total` (FC accounts: `public`/`private`) | `io_tables_sut_use` `use.gfcf.sut_pNNN.current` (row targets); `mospi_nas_2026_s1_11` `s1_11.<sector>.<asset>.current` (column targets and asset prior); `union_fiscal_fa_expenditure` `fa9.section.expenditure_heads_capital_account` and `fa9.<MH>.total`; `union_fiscal_fa_gia` `gia.cash.autonomous_bodies.capital_assets`, `gia.cash.urban_local_bodies.capital_assets`; `state_fiscal_rbi_sf_appendices` `app4.total_capital_disbursements.i-total_capital_outlay.in.all_states_uts.actuals`; `rbi_banking_corporate_rbi_accounts` `sch12.x.fixed_assets_net_of_accumulated_depreciation.current`, `is.exp_depreciation.current` (vintage 2024-05-30); fincorp satellite `fc_public_private` | SUT total 9,245,762.485522; NAS 1.11 total 9,245,762.459521; by sector: public NFC 1,000,165.28, private NFC 2,869,934.71, public FC 25,804.05, private FC 102,874.74, GG 1,222,623.35, HH 4,024,360.34 | Fr medium | Biproportional (RAS) fit to SUT commodity rows and NAS sector columns, prior from NAS 1.11 asset mix; Centre/State and FC sub-sector column keys (§2.2) | estimated |
| I2 | C_GJOM ← K_HH | 1, `gold_silver_ornaments` | `mospi_nas_2026_s1_9` `s1_9.saving_in_the_form_of_gold_and_silver_ornaments.current` (= `s5_3.saving_in_form_of_gold_and_silver_ornaments.current`) | 172,126.567611 | F | As published (§2.3) | official |
| I2a | C_GJOM ← K_HH | 1, `unsectored_valuables` | `io_tables_sut_use` `use.valuables.total.current` (= `use.valuables.sut_p125.current`) − I2 | 376,232.00 − 172,126.567611 = **204,105.432389** | F | SUT valuables less NAS household gold; financed by D3 → K_HH (§2.3) | derived |
| I3a | K_DSTK ← K_s | ≤ 8 entries | `mospi_nas_2026_s1_14` `s1_14.<sector>.gross_capital_formation.current` − `mospi_nas_2026_s1_11` `s1_11.<sector>.current`; control `io_tables_sut_use` `use.cii.total.current`; check `mospi_nas_2026_s7_2` `s7_2.total.cis.current`, `s7_2a.public_admin.cis.current` | NFC pub 110,896.96; NFC pvt 256,383.46; FC pub 0.00; FC pvt 8,486.48; GG 5,630.42; HH 931.73; Σ 382,329.05 vs SUT 382,329.00 | A 0.001 (NAS-sector values); Fr medium (FC sub-split) | Sector CIS = GCF − GFCF; scale by 382,329.00/382,329.05; GG → K_GCEN; FC private by I1a private-part shares (§2.4) | derived / estimated |
| K1 | K_NFPU ← E_NFPU; K_NFPR ← E_NFPR | 2, `total` | `mospi_nas_2026_s1_9` `s1_9.public_non_financial_corporations.current`, `s1_9.private_non_financial_corporations.current` | 462,996.248646; 2,410,408.526921 | F | As published (§2.5) | official |
| K4 | K_HH ← H_R1..H_U5 | **constraint only** (closure writes K4a) | `mospi_nas_2026_s1_9` `s1_9.household_sector.current` | 5,890,330.446044 | constraint | Same id target as closure's `closure.k4.hh_saving_total` (§2.5) | official |
| K7 | I_x ← K_s, s ∉ {K_HH, K_ROW}, x ≠ I_GSEC, I_RESV | `dom`, `fsf_f81`, `fsf_f89` | `rbi_financial_accounts_fsf_balance_sheets` (transactions 2023-24) | FSF assets of these sectors (by K, published): K_NFPU 146,430; K_NFPR 1,280,051; K_RBI 697,531; K_BANK 3,525,544; K_NBFC 1,023,508; K_INSP 1,673,227; K_MUTF 355,801; K_GCEN 518,837; K_GSTA 294,180 | A 0.10 (control-side values); Fr medium (derived side); Fr low (`fsf_f8x`) | Pairwise control-side reconciliation (§2.6-2.7) | derived / estimated |
| K8 | K_s ← I_x, s ∉ {K_HH, K_ROW} | `dom`, `fsf_f81`, `fsf_f89` | same | FSF liabilities (published): K_NFPU 120,128; K_NFPR 2,097,233; K_RBI 603,505; K_BANK 3,501,158; K_NBFC 602,420; K_INSP 1,587,147; K_MUTF 355,801 (leaf sum); K_GCEN 1,731,475; K_GSTA 748,575 | as K7 | as K7; Centre→State I_LOAN written net of government's K8e (§2.7) | derived / estimated |
| K8d | I_GSEC ← K_s, s ∉ {K_HH, K_ROW} | `dom` | FSF `fsf.gg_cen.liabilities.transaction.f3.<cp>.current`, `fsf.gg_sta.liabilities.transaction.f3.<cp>.current`; OFC split from `fsf.fc_ofc_<sub>.assets.transaction.f3.gg_cen/gg_sta.current`; cross-checks `rbi_financial_accounts_hbs_gsec_ownership` (T107), `rbi_financial_accounts_dea_gsec_ownership` | issuance 1,202,664.620849 (Centre), 681,218.324265 (States) | Fr medium | Issuer-side holder split (§2.7) | estimated |
| K7a | I_x ← K_HH | one entry per SAM instrument, components per NAS 5.3 line (§2.8) | `mospi_nas_2026_s5_3` (13 lines); `union_fiscal_nssf` `nssf.ppf.additions` | Σ = `s5_3.gross_financial_saving.current` 3,602,198.51 | F | Line → instrument map; PPF moved from PF&pension to I_SSAV (§2.8) | official / derived |
| K8a | K_HH ← I_LOAN | 1, `total` | `mospi_nas_2026_s5_3` `s5_3.financial_liabilities.current` | 1,909,286.70 | F | As published; lender detail in provenance (§2.8) | official |
| K7b | household- and RoW-facing counterpart parts of every I_x cell of domestic sectors | `hh_cp`, `row_cp:<fn>` | K7a/K8a entries; FSF issuer/lender counterparty keys; rest_of_world satellite `row_financial_counterparts` | HH: 3,602,198.51 assets / 1,909,286.70 liabilities; RoW: NAS 6.1 886,570.33 / 670,569.37 | Fr high | Post the NAS/BoP values to the named counterparty in the same instrument (§2.9) | estimated |
| K9 | I_OTHR ← K_s or K_s ← I_OTHR | 1 per domestic sector, `residual` | all K_* entries of all blocks; NAS 1.14/1.9; FSF | expected lakh-crore scale (§2.10, §5 C1) | Fr low | Residual that closes each K_s; four-way decomposition in satellite `k9_decomposition` | estimated |
| K9b | K_RBI ← I_OTHR; I_OTHR ← K_GCEN | 2, `rbi_surplus_payable` / `rbi_surplus_receivable` | `rbi_banking_corporate_rbi_surplus_timing` `k9b.change_in_surplus_payable.current` (single vintage 2024-05-30); FSF `fsf.fc_rbi.liabilities.transaction.f89.gg_cen.current` | 123,457.77 each (FSF 121,647.69) | A 0.02 | Replaces the FSF F89 RBI↔Centre pair; −1,810.08 remainder kept in `fsf_f89` (§2.10) | derived |
| D3 | K_s ← X_DISC | K_HH `unsectored_valuables`; K_NFPU, K_NFPR, K_RBI, K_BANK, K_NBFC, K_INSP `si_errors` | `mospi_nas_2026_derived_residuals` `derived.si_errors_omissions.current` | total 358,633.928553; K_HH 204,105.432389; remainder 154,528.496164 | F (X_DISC pinned) | Remainder pro rata to corporate GCF (§2.3) | official total / estimated allocation |
| S4 | satellites | `s4_fwtw_fsf`, `s4_fwtw_sam`, `s4_fsf_dual_reports`, `s4_hdfc_merger_memo` | `rbi_financial_accounts_fsf_fwtw` (St 6.13.a/b); the block's own reconciliation; `rbi_banking_corporate_rtp_banks`; `rbi_financial_accounts_hh_finsav_52ab` | FSF St 6 totals 13,843,741 uses / 13,892,543 sources | — | §2.11 | official + estimated |
| S5 | satellite `s5_hh_wealth` | 10 groups × measures | households `hh_keys` (AIDIS keys); `rbi_financial_accounts_hh_finsav_52ab` `t52b.fa.current`, `t52b.fl.current` (2024-03-31) | financial assets 41,470,111.9; liabilities 12,130,649.0 | — | §2.11 | estimated |

### 2.2 I1a: GFCF by commodity × investor

1. **Row targets.** Σ over the 155 SUT products into the 34 commodities with the committed concordance `data/concordance/io_tables_sut_product_to_sam34.csv`. Non-zero rows (₹ cr): C_CNST 5,426,852.95 [p127]; C_TREQ 1,258,164.86 [p118-124]; C_ELEQ 933,891.77 [p109-117]; C_ITSV 833,679.17 [p150]; C_MACH 646,457.89 [p102-108]; C_EDUC 90,688.97 [p147, R&D]; C_WOOD 30,475.48 [p082]; C_LVST 11,941.37 [p035]; C_OSRV 6,989.15 [p155]; C_CROP 4,746.67 [p027]; C_GJOM 1,776.68 [p125 0.38 + p126]; C_PHRM 97.53 [p092]. Σ 9,245,762.49. These equal production's I1 constraints.
2. **Column targets.** NAS 1.11 by sector (table above). Scale all six by the SUT total / NAS total (9,245,762.485522 / 9,245,762.459521; the 0.026 is rounding, log it).
   - **GG → K_GCEN / K_GSTA** by a capital-spending key, following government's "treasury view" (government.md §4.3):
     - Centre = Union capital outlay `fa9.section.expenditure_heads_capital_account` 807,180.34, less the departmental-commercial and financial heads (Railways `fa9.5002.total` 242,537.9 + `fa9.5003.total` 110.6; Posts `fa9.5201.total` 1,136.9; telecom `fa9.5225.total` 161.0 and `fa9.5275.total` 59,380.6 (BSNL/MTNL equity); investment heads `fa9.4416.total` 0, `fa9.5465.total` 11,958.5, `fa9.5466.total` 7,309.8, `fa9.5467.total` 0), ≈ 484,585; plus IGAS-2 grants for capital assets to central autonomous bodies `gia.cash.autonomous_bodies.capital_assets` 139,896.67. Total ≈ 624,482.
     - States = RBI SF total capital outlay 747,305.791 plus IGAS-2 capital grants to ULBs 1,479.24. Total ≈ 748,785.
     - Indicative: Centre 45.5% ≈ 556,000; States ≈ 667,000. Confidence low-medium.
     - Caveats, logged: capital outlay includes land and equity in State PSUs; NHAI's sector is unknown (§6.4 Q3). R2k (Centre→State capital grants) is spent by States and is inside State outlay, so it is not added again.
   - **FC → sub-sectors.** K_RBI = RBI AR additions ≈ Δ net fixed assets + depreciation = (2,042.64 − 981.57) + 370.62 = **1,431.69** (derived), all public. The rest of public FC (25,804.05 − 1,431.69) and all of private FC (102,874.74) are split across K_BANK, K_NBFC and K_INSP in proportion to fincorp's published sub-sector CFC by ownership part (satellite `fc_public_private`; fall back to GOS if CFC is not published). Components `public`/`private`. The NAS public/private FC totals can be enforced only with a components filter (FR-cf-2).
3. **Prior.** p(c, s) = V(S(s), a(c)) × w_s × SUT(c) / SUT(a(c)), where:
   - V = NAS 1.11 sector × asset value;
   - w_s = the account's share of its NAS sector (step 2);
   - a(c) = the asset group of commodity c: structures {C_CNST}; machinery & equipment {C_TREQ, C_ELEQ, C_MACH, C_WOOD, C_GJOM, C_PHRM}; IPP {C_ITSV, C_EDUC, C_OSRV}; cultivated biological resources {C_CROP, C_LVST}.
4. **RAS** (biproportional) to the step-1 rows and step-2 columns; iterate to 1e-9 relative. Zero priors stay zero (e.g. FC has no cultivated assets).
5. **Why the asset classes are not constraints.** NAS asset totals do not match the SUT product groups: structures 5,344,187.19 vs C_CNST 5,426,852.95 (+82,665.76); M&E 2,886,310.48 vs 2,870,864.21 (−15,446.27); IPP 998,576.75 vs 931,357.29 (−67,219.46); CBR equal (16,688.04). So about ₹82,666 cr of SUT construction output is classed by NAS as IPP (probably mineral exploration) and M&E. The asset mix is used in the prior only, as the gap map says.
6. Entries free, medium. Constraints: production's I1 per commodity plus `cf.i1a.gfcf.<sector>` (§3).

### 2.3 I2, I2a, D3: valuables and saving-investment errors

- **I2 = 172,126.567611**, fixed, on C_GJOM ← K_HH.
- **I2a = 204,105.432389** = SUT valuables 376,232.00 − I2. Use the SUT, not NAS 1.1 `s1_1.valuables.current` 376,231.72, so the C_GJOM valuables row equals production's constraint exactly (closure.md C5 agrees). Jewellery is valuables, never PFCE: the SUT has no PFCE on p125 (households.md C_GJOM PFCE = p126 only).
- **D3 total = `derived.si_errors_omissions.current` = 358,633.928553**, the NAS figure. closure writes D1 = D2 + D3 + D4 as written, which absorbs the 0.107 rounding (closure.md §2.2). This block does **not** re-derive D3 from D1 − D2, so only one block absorbs the rounding.
- **D3 → K_HH = I2a exactly** (component `unsectored_valuables`), so K_HH closes (closure.md T7).
- **D3 remainder = 154,528.496164**, allocated to the corporate capital accounts pro rata to their GCF (GFCF + CIS). NAS shares: public NFC 1,111,062.24 (25.40%), private NFC 3,126,318.17 (71.47%), FC 137,165.27 (3.14%, split across K_RBI/K_BANK/K_NBFC/K_INSP by their I1a + I3a GCF). Indicative: K_NFPU ≈ 39,248; K_NFPR ≈ 110,435; FC ≈ 4,845.
  - **Deviation from the gap map**, which says "to the sector(s) where FSF net lending and NAS disagree most". After the §2.7 reconciliation, those disagreements are mostly FSF-internal (§5 C1), so the rule would chase artefacts.
  - Why corporates only: household saving is measured from the asset side (it equals GCF + gold + NAS 5.3 net financial saving exactly), and GG saving and GCF both come from budget accounts. Corporate saving (company-accounts samples, blown up) is the least directly measured.
  - Alternative (logged, orchestrator's call): 100% to K_NFPU, as the gap map intended.
- D3 entries are X_DISC cells: fixed, never balanced. Status: total `derived` (from `official` inputs), allocation `estimated`.

### 2.4 I3a: change in inventories by financing sector

| NAS sector | GCF (1.14) | GFCF (1.11) | CIS | SAM account(s) |
|---|---:|---:|---:|---|
| Public NFC | 1,111,062.24 | 1,000,165.28 | 110,896.96 | K_NFPU |
| Private NFC | 3,126,318.17 | 2,869,934.71 | 256,383.46 | K_NFPR |
| Public FC | 25,804.05 | 25,804.05 | 0.00 | none (no zero entries) |
| Private FC | 111,361.22 | 102,874.74 | 8,486.48 | K_BANK/K_NBFC/K_INSP private parts, pro rata to their I1a private GFCF |
| GG | 1,228,253.77 | 1,222,623.35 | 5,630.42 | **K_GCEN 100%** |
| Households | 4,025,292.07 | 4,024,360.34 | 931.73 | K_HH |
| **Total** | | | **382,329.05** | vs SUT CII 382,329.00 |

- Scale all six by 382,329.00 / 382,329.05 before writing, so K_DSTK's row equals production's fixed I3 column exactly. Log the 0.05.
- Cross-check: 7.2A public CIS 116,527.4 = 110,896.96 + 5,630.42 (+0 FC); 7.2B 264,869.9 = 256,383.46 + 8,486.48; 7.2C 931.7.
- **GG → K_GCEN, not pro rata GFCF (deviation from the gap map).** NAS 7.2A puts public-sector CIS in public administration & defence (`s7_2a.public_admin.cis.current` 5,605.3 ≈ GG CIS). Defence stores and FCI food stocks are central (FCI is inside G_CEN in NAS 2026). Confidence low; the pro-rata alternative is logged.

### 2.5 K1, K4

- **K1:** two fixed entries (table). NAS 1.9 private-NFC saving is already net of foreign reinvested earnings (163,704.27, rest_of_world's R14a), so no adjustment here.
- **K4:** constraint only. K_HH ← H_* Σ = 5,890,330.446044, tol_abs 0.5. The id and target are identical to closure's `closure.k4.hh_saving_total` (same series, same value), so the framework sees duplicates, not a conflict.

### 2.6 Why FSF cannot be used as fixed official cells (evidence)

FSF 2023-24 transactions, summed over the SAM capital accounts (leaf statements, published):

| FSF instrument | Σ assets | Σ liabilities | Gap (A − L) |
|---|---:|---:|---:|
| F1 monetary gold & SDR | 65,379 | −434 | 65,813 |
| F21 currency | 122,418 | 129,795 | −7,377 |
| F22/F29 deposits | 3,216,093 | 3,447,356 | −231,263 |
| F3 debt securities | 2,516,222 | 2,625,185 | −108,963 |
| F4 loans | 3,767,968 | 4,064,888 | −296,920 |
| F51 equity | 1,946,596 | 363,783 | **1,582,813** |
| F52 investment fund shares | 390,615 | 344,380 | 46,235 |
| F6 insurance, pension | 1,196,278 | 1,623,388 | −427,111 |
| F81 trade credit | 214,357 | 397,762 | −183,405 |
| F89 other payables | 272,995 | 334,296 | −61,301 |
| VIII other / IX NEC | 134,820 | 562,144 | −427,323 |
| **Total** | 13,843,741 | 13,892,543 | −48,802 (St 7 printed: −49,902.47, FIN-3; the 1,100 is the MMF F8 hierarchy error) |

Pairwise comparisons (holder's report vs issuer's report of the same flow) show where the differences come from. Examples (₹ cr):

| Instrument, holder → issuer | Holder says | Issuer says | Reading |
|---|---:|---:|---|
| F51, Centre → public NFCs | 271,178.19 | 42,285.55 | Centre's equity funding includes Railways' budget support (Union MH 5002 = 242,537.9). FSF's nfc_pub statement covers CPSEs, ports and power only, not departmental enterprises |
| F4, banks → public NFCs | 194,814.80 | −34,148.51 | Lenders' "public sector" is broader than FSF's nfc_pub statement |
| F51, RoW → private NFCs | 591,517 (St 5) | −91,312 | FSF St 5 books all FDI + FPI (222,244 + 369,273 = 591,517) as equity in private NFCs |
| F51, insurers → "OFC" | 600,014.27 (all to counterparty `fc_ofc`) | — | Label problem; the 600,014 is the stock change, while the published valuation column is 777,800 |
| F62, insurers' life liability vs households' life asset | 589,065 (hh) | 1,033,563.07 (insurers) | Insurers' figure includes revaluation of policyholder funds; NAS 5.3 life insurance is 642,399.00 |
| F22, banks → RBI (reserves) | 117,677.40 | 286,587.72 | RBI's own balance sheet is the reliable side |
| F4, OFC → ODC | 71,298 | 306,639 | ODC side carries HDFC Ltd bonds reclassified as borrowings after the merger |
| F3, domestic holders → ODC | +50,400 (OFC 50,392 + ODC 589 − NFC 581) | −145,614 in total (of which HFC-DT −179,664) | HDFC Ltd bonds leave the issuer side; holders booked no transaction |

So K7/K8 become **derived/estimated**, not fixed official cells. Only households (NAS 5.3) and RoW (BoP) are official controls.

### 2.7 K7, K8, K8d: reconciled FSF (domestic pairs)

**Step A: instrument map and control side.**

| SAM instrument | FSF source (issuer condition) | Control side | Why | Households | RoW (rest_of_world K8b) |
|---|---|---|---|---|---|
| I_CURR | F21 | issuer (RBI, 129,794.83) | RBI balance sheet | NAS 118,247.97 | none |
| I_DEPO | F22/F29 issued by ODC, RBI, OFC, NFC | issuer (deposit-takers) | Deposit-takers' returns are the primary source; RBI's reserve liabilities (286,587.72) beat banks' 117,677.40 | NAS 1,409,587.95 | NRI 121,860; bank other 74,820; RBI 10,372; banks' foreign assets −128,732 |
| I_SSAV | F22/F29 issued by gg_cen, gg_sta | issuer (Finance Accounts, NSSF) | Public account | NAS 421,678.36 (small savings + PPF) | none |
| I_GSEC | F3 issued by gg_cen, gg_sta | issuer (1,202,664.62; 681,218.32) | Debt management knows its holders | NAS 25,552.16 | FPI G-sec ≈119,903 |
| I_CBND | F3 issued by resident non-GG | holder | Portfolio returns (banks, MFs, insurers); issuer side distorted by the HDFC reclassification | 0 (assumption, §2.8) | FPI corporate ≈40,677 |
| I_LOAN | F4 | lender | Banks'/NBFCs' loan returns (BSR); borrower sides carry RBI round-number estimates | NAS 1,909,286.70 | ECB, external assistance, FDI/ODI debt, loans by India |
| I_EQTY | F51 | holder, with the insurer fix (Step C) | Issuer side is book-value paid-up capital (private-NFC equity stock 33.8 lakh cr vs RoW holdings alone 52 lakh cr); holders include GG budget data, MF (SEBI-consistent) and BoP | NAS 73,666.50 | FDI eq 37,226 + RE 163,704.27 + FPI eq 208,694; ODI 45,537 + RE 47,898; PI abroad 4,469 |
| I_MFUN | F52 | issuer (MF 344,281.21) | AMFI/SEBI-consistent | NAS 285,052.00 | none |
| I_INPE | F6 (F61, F62, F63, F6_pf; components only) | holder (NAS households) | NAS 5.3 is the control; FSF issuer side includes revaluation | NAS 1,260,185.57 | none |
| I_RESV | F1 and RBI's RoW-counterparty F22/F3/F4 | none: **rest_of_world writes all of I_RESV** (K8c 526,931) | BoP flow excludes valuation (RBI's FSF foreign assets 714,817 include gold revaluation 67,820 and more) | — | K8c |
| I_OTHR | F81, F89: each sector's own reports (no pairing). VIII "other" and IX "NEC" **not written** (FSF balancing items, e.g. nfc_pvt other liabilities 300,000, coop banks 187,969); they fall into K9 | residual | — | trade debt 8,228 | E&O 3,319.55; short-term credit −6,741; other capital 98,450; rupee debt −597; reconciliation lines |

**Step B: domestic pairs.** For each instrument and each pair (holder H, issuer C) of domestic non-household sectors, X(H, C) = the control side's report. H's asset `dom` = Σ_C X; C's liability `dom` = Σ_H X.
- Where a counterparty is `fc_ofc` (not split in FSF), split it across K_NBFC/K_MUTF/K_INSP with the OFC sub-sector statements' own reports for that instrument and counterparty (absolute-share rule). For OFC↔OFC pairs, use holder sub-shares × issuer sub-shares.
- `other_resident` and unallocated amounts on the control side go to a stated default: currency 10,469 → K_NFPR; deposits → K_NFPR; otherwise leave them out, and they fall into K9.
- **Intra-sector pairs** (e.g. private NFC equity 34,500 held vs −116,344 issued; interbank deposits −37,121 vs 93,947): both sides take the control-side value, so they cancel inside the account.
- **Drop** every FSF pair whose counterparty is `row` or `hh` (Steps D and E rebuild them), MF monetary gold (F11 1,100) with its F8 1,100, and gg_cen SDRs (F12 −3,998 assets / −434 liabilities; not in the BoP flow, which is all FCA).

**Step C: special rules.**
1. **Insurers' equity.**
   - Replace the counterparty (all `fc_ofc`, a label error) with the MF sector's issuer mix (`fsf.fc_ofc_mf.assets.transaction.f51.<cp>.current`: fc_odc 46,030, fc_ofc 33,820, nfc_pub 24,319, nfc_pvt 41,117, row 4,527).
   - Strip revaluation: insurers' equity acquisitions = 600,014.27 − (insurers' F62 1,033,563.07 − NAS life 642,399.00) = 600,014.27 − 391,164.07 = **208,850.20**. This keeps K_INSP's net financial transactions close to FSF's own (86,079) when I_INPE is cut to NAS.
   - Estimated, low. Sensitivity: no strip.
2. **PF sub-sector equity** is printed as three equal parts (5,954 each, to fc_odc/nfc_pub/nfc_pvt): kept as published, flagged (§6.3).
3. **SFC/SIDC F52** (MF-unit holdings, stocks 2.89 and 5.46 lakh cr) are implausible. Exclude them as I_MFUN holders; their flows fall into K9 (§6.3).
4. **Centre ↔ States loans.**
   - FSF `fsf.gg_cen.assets.transaction.f4.gg_sta.current` = `fsf.gg_sta.liabilities.transaction.f4.gg_cen.current` = 41,791.65. This equals the Union's net lending 140,863.34 − 92,856.68 − 6,215.00 = 41,791.66 (`union_fiscal_afs` `afs.cfi_cap_disbursements.7601`, `afs.cfi_cap_receipts.state_governments`, `…union_territories_with_legislature`), which includes the 78,104 GST back-to-back recovery.
   - So write `dom` = 41,791.65 − (government's K8e value) = **119,895.65** when government writes K8e = −78,104.00 (government.md K8e, fixed, conditional). If government writes no K8e, write 41,791.65.
   - Test: Σ over refs = FSF.
5. **Centre equity in public NFCs** = 271,178.19 (holder control). It includes Railways' budget support. government's K6 must not also carry it as a capital transfer: government's COFOG-based K6 to K_NFPU is ≈ 75k (04.* functions), so Railways GBS (242.5k) is not in it. Flag any overlap (§6.1 D4).
6. **RBI.** RBI's RoW-facing assets are replaced by K8c (rest_of_world). RBI's F6 (2,566, printed only in the total) is dropped (component rule).

**Step D: households** (§2.8). **Step E: RoW** (§2.9).

**Step F: G-sec holders (K8d).**
- Issuer-side holder split for Centre: fc_rbi −43,108; fc_odc 623,963; fc_ofc 446,069 (OFC sub-sector holder reports: insurers 255,597, PF 170,909, MF 26,008, AIFI 31,219, NBFC-ND 17,036, HFC-ND −2,927); gg_sta 16,532; nfc_pub −24,582; nfc_pvt −5,116. For States: fc_rbi 22; fc_odc 268,677; fc_ofc 425,592 (insurers 137,296, PF 150,155, MF 9,029, NBFC-ND 1,825, AIFI −2,170); gg_cen −35,926 (NSSF's special State securities: `nssf.special_sgs_post1999` 15,080.23 − 51,006.71 = −35,926.48); gg_sta 996; nfc_pvt 15,654. The hh and row pairs are rebuilt in Steps D and E.
- Cross-check only: T107 / DEA ownership shares × outstanding. Their end-March 2024 shares are distorted by the HDFC merger (rbi_financial_accounts-2), so they must not be read as flows. This deviates from the gap map's K8d method (§6.2).

**Indicative effect (scratch prototype; domestic pairs + households + insurer fix, RoW not yet replaced, before D3).**

| NAS sector | NAS net lending (S − GCF; households also − gold) | FSF published net financial transactions | After Steps B-D | NAS − FSF (FIN-1) | NAS − reconciled |
|---|---:|---:|---:|---:|---:|
| Public NFC | −648,065.99 | 26,302 | ≈ −711,757 | −674,368 | ≈ +63,700 |
| Private NFC | −715,909.64 | −817,182 | ≈ −794,430 | +101,272 | ≈ +78,500 |
| GG | −1,546,638.15 | −1,667,032 | ≈ −1,580,779 | +120,394 | ≈ +34,100 |
| FC | 854,282.49 | 625,578 | ≈ 693,041 | +228,704 | ≈ +161,200 |
| Households | 1,692,911.81 | 1,569,860 | 1,692,911.81 | +123,052 (FIN-1 shows 295,178 because it omits gold) | 0 |

- Caution: the same rules on 2022-23 help public NFCs (gap −474k → −320k) but hurt private NFCs (+283k → +554k), because of an intra-sector equity asymmetry in FSF (295,500 held vs −17,900 issued).
- The builder must publish K9 by sector for 2023-24 under both equity control choices (holder and issuer), and for 2022-23 as a validation run.

### 2.8 K7a, K8a: households (NAS 5.3 line → SAM instrument → counterparty)

| NAS 5.3 line (series `s5_3.*.current`) | Value | SAM instrument | K7a component | Counterparty (the `hh_cp` posting) |
|---|---:|---|---|---|
| currency | 118,247.97 | I_CURR | `currency` | K_RBI |
| with_banks | 1,409,651.87 | I_DEPO | `banks` | Split of the three deposit lines by FSF issuer-side counterparty=hh: K_BANK 1,419,013 (scb 1,416,771 + coop 55,806 + nbfc_dt 11,202 + hfc_dt −64,766); K_NBFC 1,954 (AIFI); K_NFPR 36,880 (company deposits). Scale to 1,409,587.95. NAS's "non-banks −59,126" is mostly HDFC Ltd, which is inside K_BANK in the SAM boundary |
| with_co_operative_banks_and_societies | 59,062.57 | I_DEPO | `coop` | (same key) |
| with_non_banking_companies | −59,126.49 | I_DEPO | `non_banks` | (same key) |
| trade_debt_net | 8,228.00 | I_OTHR | `trade_debt` | K_NFPR (FSF `fsf.hh.assets.transaction.f81.nfc_pvt.current` = 8,228) |
| shares_and_debentures − mutual_funds | 358,718.50 − 285,052.00 = 73,666.50 | I_EQTY | `shares_debentures` | Issuers by FSF issuer-side F51 counterparty=hh: nfc_pvt 36,747, fc_odc 1,813, fc_ofc 2,866 (the 361.03 co-operative shares → K_BANK) |
| mutual_funds | 285,052.00 | I_MFUN | `mutual_funds` | K_MUTF |
| investment_in_government_securities | 25,552.16 | I_GSEC | `gsec` | K_GSTA 2,762 (FSF); K_GCEN the rest (retail instruments such as SGBs are Central) |
| investment_in_small_savings_etc | 309,750.90 | I_SSAV | `small_savings` | K_GCEN |
| PPF (from `union_fiscal_nssf` `nssf.ppf.additions`) | 111,927.46 | I_SSAV | `ppf` | K_GCEN |
| life_insurance_funds | 642,399.00 | I_INPE | `life_insurance` | K_INSP |
| postal_insurance | −1,811.08 | I_INPE | `postal_insurance` | K_GCEN |
| state_insurance | 8,498.51 | I_INPE | `state_insurance` | K_GSTA (§6.4 Q2) |
| provident_and_pension_funds − PPF | 723,026.60 − 111,927.46 = 611,099.14 | I_INPE | `pf_pension` | K_GCEN GPF 5,058.84 (`fsf.gg_cen.liabilities.transaction.f6_pf.all.current` = FA MH 8009 68,989.35 − 63,930.50); K_GSTA 32,099.70 (`fsf.gg_sta.liabilities.transaction.f6_pf.all.current`); K_INSP the rest, 573,940.60 |
| **Σ assets** | **3,602,198.51** | | = `s5_3.gross_financial_saving.current` | |
| financial_liabilities (K8a) | 1,909,286.70 | I_LOAN | `total` | Government 334.00 (split 122 K_GCEN / 212 K_GSTA as FSF hh L F4); insurers 8,190.90 → K_INSP; the remaining 1,900,761.80 by FSF lender-side counterparty=hh: K_BANK 1,833,823 (scb 1,879,898, coop 16,063, nbfc_dt 67,942, hfc_dt −130,080); K_NBFC 255,855 (nbfc_ndt 280,194, hfc_ndt −24,719, sfc 320, aifi 60); K_RBI 1,820 (≈ K_BANK 87.7%, K_NBFC 12.2%) |

- **PPF is proven, not assumed.** NSSF net collection 421,678.36 = savings deposits 252,892.84 + certificates 56,858.06 + PPF 111,927.46. NAS small savings 309,750.90 = the first two. The T52(b) PPF stock change 939,449.0 → 1,051,376.5 = 111,927.5. So PPF sits only in NAS "PF & pension" and moves to I_SSAV here; I_INPE ← K_HH excludes it (double-count guard). I_SSAV ← K_HH = 421,678.36 = FSF `fsf.gg_cen.liabilities.transaction.f22_f29.hh.current` 421,678.3467, so the K_GCEN posting equals FSF exactly.
- **Household loans lender view.** The SAM view gives K_NBFC ≈ +2.3 lakh cr against NAS's label "NBFC −6,423". The difference is HDFC Ltd (a deposit-taking HFC) sitting inside K_BANK, where the SAM boundary (FSF S122) puts it. The published NAS/T52a lender view (banks 1,856,136.4; NBFC 327,000.7; HFC −333,423.7; T52a) goes to S4's merger memo.
- **Equity vs debentures.** NAS does not split "shares, debentures, hybrid instruments in primary market" (72,487.32). All of it goes to I_EQTY, and the FSF household statement shows no corporate-debt holdings. Low; logged.
- K7a/K8a entries are fixed (official values or sums of them); status `official`, or `derived` for the PPF move and the net deposit sum.

### 2.9 K7b: counterparty postings

- **Households.** Write `hh_cp` entries on the counterparty accounts from the table in §2.8. Rule (gap map K7b): the FSF household statement is never used for counterparty values once NAS 5.3 is used. Keys come from the counterparties' own statements (issuer side for deposits, equity and G-secs; lender side for loans).
  - Two consequences, logged:
    - States' deposits from households (`fsf.gg_sta.liabilities.transaction.f22_f29.hh.current` −37,841) disappear, since NAS has no such household line;
    - RBI's currency liability rises by 221.97 (118,247.97 − 118,026).
- **RoW.** Mirror rest_of_world's satellite `row_financial_counterparts` (rest_of_world.md §2.6, §4): one `row_cp:<bop_function>` entry per K8b line in the same instrument, on the domestic counterpart it names, with the same value and `bop_function`.
  - Where it names "FC" without a sub-sector, split by FSF's RoW-held stocks of issuers at 2023-03-31: F51 fc_odc 128,231 / fc_ofc (nbfc_ndt 19,904 + hfc_ndt 24,439 + sidc 558) / icpf_ins 18,224, i.e. K_BANK 67%, K_NBFC 23%, K_INSP 10%.
  - For `fdi_reinvested_earnings` use rest_of_world's R14a payer entries exactly (same split), so income and financing match.
  - Lines marked `unallocated_k9` (E&O 3,319.55; the two NAS reconciliation lines) get no posting; K9 absorbs them.
  - FSF domestic RoW-counterparty cells are **all dropped** (rest_of_world.md §4).
- **Roles:** free, high (they mirror fixed official cells on the other side of each market).

### 2.10 K9, K9b

- **K9 per domestic sector s** (K_NFPU, K_NFPR, K_RBI, K_BANK, K_NBFC, K_INSP, K_MUTF, K_GCEN, K_GSTA, K_HH): K9_s = [row total of K_s excluding K9] − [column total excluding K9], computed on all blocks' prior entries:
  - saving: K1 here; fincorp K2a; government K3a; for K_HH the NAS K4 total, since closure runs later;
  - capital transfers: government K6 and R2k, including RoW;
  - D3; GFCF, CIS, valuables; all instrument entries.
  - If K9_s > 0, write I_OTHR ← K_s (asset); if < 0, write K_s ← I_OTHR (liability). One entry, `residual`, free, low. |K9_s| < ₹1 cr: write nothing and log.
- **Decomposition** (satellite `k9_decomposition`, one row per sector × component; the components sum to K9_s):
  1. `nas_vs_fsf` = SAM saving + net capital transfers + D3 − GCF − valuables − FSF published net financial transactions (leaf basis);
  2. `fsf_reconciliation` = −(change from Steps B-C);
  3. `hh_counterparty` = −(change from Step D);
  4. `row_counterparty` = −(change from Step E);
  5. `fsf_unwritten` = VIII/IX items and dropped quirks.
- **Walras check.** After K9, every K_s balances and every I_x except I_OTHR clears. So I_OTHR clears automatically if all blocks' saving, GCF, capital transfers and RoW totals are NAS-consistent. Test |I_OTHR row − col| ≤ ₹1 cr. A failure means some block's totals are inconsistent (report which).
- **K_HH:** K9_HH = net capital transfers posted to K_HH (≈ 91,496 if government writes its COFOG housing and other grants 89,940 plus the RoW 1,555.69), else 0. See §6.1 D7: the orchestrator should decide before the build.
- **K_ROW:** no K9 (rest_of_world closes it).
- **K9b** (RBI surplus timing):
  - K_RBI ← I_OTHR `rbi_surplus_payable` 123,457.77 and I_OTHR ← K_GCEN `rbi_surplus_receivable` 123,457.77, anchored 2%.
  - Written on both sides because FSF records the Centre's receivable (`fsf.gg_cen.assets.transaction.f89.fc_rbi.current` 121,647.69), as the gap map requires.
  - The FSF F89 RBI→Centre pair (121,647.69) is replaced by K9b plus a −1,810.08 `fsf_f89` remainder on both sides (RBI's other payables to GoI, FIN-4).
  - R6 stays cash (87,416.22, government.md). See §6.4 Q1.

### 2.11 Satellites S4 and S5

- **S4 (who funds whom).**
  - `s4_fwtw_fsf`: FSF St 6.13.b flows and 6.13.a stocks as published (`rbi_financial_accounts_fsf_fwtw`, 9 sectors × 10 counterparties, uses and sources), status official.
  - `s4_fwtw_sam`: the reconciled holder K × issuer K × SAM instrument matrix X from §2.7 Steps B-E, the SAM-consistent "who funds the deficit" data (e.g. GG liabilities by holder: I_GSEC by holder, I_SSAV from households, I_LOAN from banks and RoW), status estimated. Row and column sums equal the `dom` + `hh_cp` + `row_cp` entries.
  - `s4_fsf_dual_reports`: every (instrument, holder, issuer) with holder report, issuer report, control side, chosen value and difference. This is the audit trail for the verifier.
  - `s4_hdfc_merger_memo`:
    - household borrowing by lender as published (NAS 5.3; T52a `t52a.fl_fc_banks_scb` 1,856,136.4, `t52a.fl_fc_ofi_nbfc` 327,000.7, `t52a.fl_fc_ofi_hfc` −333,423.7) and in the SAM boundary;
    - SCB loans with/without the merger at 2024-03-31: `rtp.scb_bs.loans_advances.scb.current` 17,142,340 − `rtp.scb_bs.loans_advances_excl_merger.scb.current` 16,617,066 = 525,274;
    - deposits 21,733,443 − 21,623,329 = 110,114 (vintage 2024-12-26 for both, pass `vintage`). This matches FSF HFC-DT deposit liabilities −110,419.
- **S5 (household wealth and debt, ABM calibration).**
  - Use households' `hh_keys` AIDIS keys, already mapped to the 10 groups by household overlap (households.md §2.4): `financial_assets` and institutional `debt`. Levels = key share × RBI T52(b) end-March 2024 stocks: `t52b.fa.current` 41,470,111.9 (by class: deposits 14,179,504.0, currency 3,239,762.1, equity 8,406,842.8, MF 3,628,236.4, life 6,820,611.8, PPF 1,051,376.5, pension 1,172,651.0, small savings 2,096,314.2) and `t52b.fl.current` 12,130,649.0 (banks 10,024,680.4; OFIs 2,105,968.6).
  - Physical assets and non-institutional debt stay at AIDIS 2018-06-30 per-household values × hh_keys households, labelled "not rebased, 2018". There is no official 2024 control, and inventing a growth factor would break rule 1.
  - Status estimated, low. D1-2 (no unit data) caps quality.
  - households flags an AIDIS class-order anomaly (top class below class 4). S5 inherits it.

---

## 3 Constraints to declare

Targets are read in-block with `ctx.value`, never typed. `tol` = max(tol_abs, tol_rel·|target|).

| constraint_id | ref | rows | cols | refs | target (source series) | kind | tol_abs / tol_rel | description |
|---|---|---|---|---|---|---|---|---|
| `cf.i1a.gfcf.nfc_pub` | I1a | all C_* | [K_NFPU] | [I1a] | `s1_11.public_non_financial_corporations.current` 1,000,165.28 (× SUT/NAS scale) | equal | 1 / 0 | NAS 1.11 GFCF, public NFC |
| `cf.i1a.gfcf.nfc_pvt` | I1a | all C_* | [K_NFPR] | [I1a] | `s1_11.private_non_financial_corporations.current` 2,869,934.71 | equal | 1 / 0 | |
| `cf.i1a.gfcf.fc` | I1a | all C_* | [K_RBI, K_BANK, K_NBFC, K_INSP] | [I1a] | `s1_11.public_financial_corporations.current` + `s1_11.private_financial_corporations.current` = 128,678.79 | equal | 1 / 0 | Public/private parts need FR-cf-2 |
| `cf.i1a.gfcf.gg` | I1a | all C_* | [K_GCEN, K_GSTA] | [I1a] | `s1_11.general_government.current` 1,222,623.35 | equal | 1 / 0 | |
| `cf.i1a.gfcf.hh` | I1a | all C_* | [K_HH] | [I1a] | `s1_11.household_sector.current` 4,024,360.34 | equal | 1 / 0 | |
| `cf.i1a.gfcf.total` | I1a | all C_* | all K_* | [I1a] | `use.gfcf.total.current` 9,245,762.485522 | equal | 0.01 / 0 | Duplicate of production's I1 total (same series) |
| `cf.valuables.total` | I2 | [C_GJOM] | [K_HH] | [I2, I2a] | `use.valuables.total.current` 376,232.00 | equal | 0.01 / 0 | Same target as production's valuables constraint |
| `cf.i3a.cis.<sector>` × 5 (nfc_pub, nfc_pvt, fc, gg, hh) | I3a | [K_DSTK] | the sector's K accounts | [I3a] | `s1_14.<sector>.gross_capital_formation.current` − `s1_11.<sector>.current` (FC: private only; public is 0) | band | 0.1 / 0 | NAS sector CIS (rounding band) |
| `cf.i3a.cis.total` | I3a | [K_DSTK] | all K_* | [I3a] | `use.cii.total.current` 382,329.00 | equal | 0.01 / 0 | K_DSTK row = production's fixed I3 column |
| `cf.k4.hh_saving` (= closure's `closure.k4.hh_saving_total`; adopt closure's id if the framework dedupes by id) | K4 | [K_HH] | [H_R1..H_U5] | [K4a] | `s1_9.household_sector.current` 5,890,330.446044 | equal | 0.5 / 0 | Official household saving |
| `cf.k7a.hh_assets` | K7a | all I_* | [K_HH] | [K7a] | `s5_3.gross_financial_saving.current` 3,602,198.51 | equal | 0.01 / 0 | Documents the official total. All members are fixed; convert to a block test if the framework rejects all-fixed constraints |
| `cf.k8a.hh_liabilities` | K8a | [K_HH] | all I_* | [K8a] | `s5_3.financial_liabilities.current` 1,909,286.70 | equal | 0.01 / 0 | As above |
| `cf.k8.gsec_centre` | K8 | [K_GCEN] | [I_GSEC] | [K8, K7b] | FSF `fsf.gg_cen.liabilities.transaction.f3.all.current` 1,202,664.62 + household posting (25,552.16 − 13,312) + RoW posting difference | band | 0 / 0.05 | Centre's net G-sec issuance; cross-check DEA HB-1A stock change |
| `cf.k8.gsec_states` | K8 | [K_GSTA] | [I_GSEC] | [K8, K7b] | FSF `fsf.gg_sta.liabilities.transaction.f3.all.current` 681,218.32, adjusted likewise | band | 0 / 0.05 | Cross-check T107 SDL stock change |
| `cf.k8.ssav_centre` | K8 | [K_GCEN] | [I_SSAV] | [K8, K7b] | `union_fiscal_nssf` `nssf.net_collection` 421,678.36 + FSF nfc_pub 13,045 | equal | 1 / 0 | Small savings + PPF + PSU deposits |
| `cf.k8.mfun` | K8 | [K_MUTF] | [I_MFUN] | [K8, K7b] | `fsf.fc_ofc_mf.liabilities.transaction.f52.all.current` 344,281.21 | band | 0 / 0.05 | MF net sales |
| `cf.k8.curr` | K8 | [K_RBI] | [I_CURR] | [K8, K7b] | `fsf.fc_rbi.liabilities.transaction.f21.all.current` 129,794.83 + 221.97 | equal | 1 / 0 | Currency issued |

- No constraints on NAS sector net lending: it is implied by fixed saving, constrained GCF and free K9.
- No constraint on I_* clearing: the framework enforces account balance.
- rest_of_world's `row.*` constraints cover the RoW side.

---

## 4 Interfaces

### 4.1 Needs

| From | What | Why |
|---|---|---|
| production | Nothing numeric beyond its constraints: I1 per commodity, valuables on C_GJOM, I3 fixed entries (Σ 382,329.00). This block reads the SUT directly | Consistency of I1a/I2a/I3a with production's targets |
| rest_of_world | K8b and K8c entries; satellite `row_financial_counterparts` (line × instrument × bop_function × direction × domestic counterpart or `unallocated_k9`); R14a entries (payer split); K5 entry; its D2 entry (for the X_DISC test only). Its instrument choices (trade credit → I_OTHR; FPI debt split into I_GSEC ≈119,903 / I_CBND ≈40,677) are **accepted** | K7b RoW postings; K9 |
| government | K3a entries (K_GCEN/K_GSTA ← G_*); K6 (all capital transfers, domestic and RoW) and R2k entries; K8e entries (−78,104.00 each); confirmation that K6 carries neither Railways/Posts budget support nor equity in PSUs (both are I_EQTY here) | K9; Centre–State I_LOAN netting |
| fincorp | K2a entries (components `public`/`private`); satellite `fc_public_private` with sub-sector CFC (or GOS) by ownership part | K9; FC GFCF/CIS split |
| households (**FR-cf-1: add to DEPENDS**) | `hh_keys`: `financial_assets`, institutional `debt` (and non-institutional), `pop_persons`, households by group | S5 |
| framework | FR-cf-1…5 (§6.5) | |

### 4.2 Publishes

- **Entries:** all refs in §2.1. **Constraints:** §3.
- **Satellites:**
  - S4 (four tables) and S5 (§2.11);
  - `k9_decomposition` (sector × component);
  - `capital_formation_by_account` (GFCF, CIS, valuables, GCF by K account, and the D3 allocation shares), for closure diagnostics and `pipeline/timeseries`;
  - `gg_gfcf_key` (the Centre/State capital-spending key and its inputs);
  - `fsf_instrument_closure` (the §2.6 table, recomputed).
- **For closure:** K_HH entries exactly as §2.8, D3 → K_HH = I2a to the paisa (closure.md C5), and the K4 constraint with the same series and value.
- **For timeseries:** definitions of the flows this block owns (GFCF by sector, household financial saving and borrowing, government borrowing by instrument). Their long history comes from NAS 1.9/1.11/5.3 and HBS series, not from FSF.

---

## 5 Conflicts and choices

| # | Item | Source A | Source B | Difference | Control and why |
|---|---|---|---|---|---|
| C1 | Sector net lending | NAS 1.14 (S − GCF) | FSF sector net financial transactions | FIN-1: NFC −573,095 (public −674,368; private +101,272); FC +228,704; GG +120,394; HH +295,178 | **NAS control**, FSF residual in K9. Most of the gap is FSF-internal (§2.6-2.7). The household number is an artefact of the check: net of gold (172,126.57) it is 123,052 = HH-9. Recommend the orchestrator correct `tests/cross` FIN-1-hh (report only; not edited here) |
| C2 | Household financial saving | NAS 5.3: 3,602,198.51 / 1,909,286.70 | RBI T52(a) (Sep 2026): 3,601,838.90 / 1,909,424.70; FSF St 4: 3,445,383 / 1,875,522 | 0.01% / 4.4% | **NAS 5.3** (official new base); T52(a) cross-check (HH-2/3); FSF vintage-bridged by HH-9 |
| C3 | RoW financial account | BoP (rest_of_world K8b; NAS 6.1 totals 670,569.37 / 886,570.33) | FSF St 5: 670,680 / 883,251; domestic sectors' own RoW-counterparty reports | St 5 lumps FDI+FPI into F51/nfc_pvt; domestic reports differ widely | **BoP** via rest_of_world; all FSF RoW-counterparty cells dropped |
| C4 | FSF holder vs issuer reports | per-instrument control side (§2.7 table) | the other side | §2.6 | Control side per instrument, audit trail in `s4_fsf_dual_reports` |
| C5 | G-sec holders | FSF issuer side | DEA QR / HBS T107 share changes | shares shifted by the HDFC merger at end-March 2024 | **FSF** (flows); DEA/T107 cross-check only |
| C6 | Small savings and PPF | NSSF net collection 421,678.36 = NAS small savings 309,750.90 + PPF 111,927.46 = FSF 421,678.35 | HBS T109 receipts 232,460 (gross receipts, different concept) | — | **NSSF/NAS**; T109 not used |
| C7 | State provident funds (households' claim on States) | FSF `gg_sta` F6_pf 32,099.70 | RBI SF App III VI.1 − App IV VII.1: 103,892.37 − 91,398.49 = 12,493.88 (includes "other savings deposits"; interest treatment unstated) | 19,606 | **FSF** (consistent with the FSF gg_sta statement used for K9); SF as cross-check. Low; the total I_INPE ← K_HH is fixed anyway, so only the K_INSP/K_GSTA split moves |
| C8 | Postal life insurance | NAS 5.3 −1,811.08 | Union FA MH 8014: 16,793.08 − 12,852.69 = +3,940.39 | 5,751 | **NAS** (household side fixed) |
| C9 | RBI surplus payable | RBI AR 123,457.77 | FSF F89 121,647.69 | 1,810.08 = other payables (FIN-4) | **AR** for K9b; remainder kept in `fsf_f89` |
| C10 | Centre–State loans | Union AFS net 41,791.66 = FSF 41,791.65 (incl. 78,104 cess-funded recovery) | States: RBI SF loans from Centre 142,517.7 − repayment 27,483.2 | the recovery is booked only on the Union side | **FSF/Union**, net of government's K8e |
| C11 | GFCF total and asset mix | SUT 9,245,762.485522, C_CNST 5,426,852.95 | NAS 1.11 9,245,762.459521, structures 5,344,187.19 | 0.026; 82,666 between asset classes | **SUT for commodities, NAS for sectors**; asset mix in the prior only |
| C12 | Valuables | SUT 376,232.00 | NAS 1.1 376,231.72 | 0.28 | **SUT** (production constraint); I2a and D3→K_HH use the same 204,105.432389 |
| C13 | CIS total | NAS sector sum 382,329.05 | SUT CII 382,329.00 | 0.05 | **SUT**; scale I3a |
| C14 | X_DISC identity | D1 published 571,133.272525 | D2 (rest_of_world, SUT CIF 212,499.23649) + D3 358,633.928553 | 0.107 | **closure absorbs it** (D1 := D2 + D3 + D4); D3 stays the NAS value |
| C15 | Household loans by lender | NAS 5.3 labels (banks 1,856,520.63; NBFC & HFC −6,422.95) | SAM boundary (FSF S122 includes HFC-DT) via FSF lender shares | K_NBFC ≈ +2.3 lakh cr vs −6,423 | **SAM boundary** (consistent with every other K_BANK/K_NBFC cell); published view in the S4 merger memo |
| C16 | D3 remainder | gap map: sector(s) with the largest NAS–FSF disagreement | this plan: corporate GCF pro rata | allocation only | **Pro rata** (§2.3); alternative logged |
| C17 | GG inventories | gap map: pro rata GFCF | this plan: 100% K_GCEN | 5,630 | **K_GCEN** (FCI and defence are central) |
| C18 | Public NFC equity from the Centre | Centre's F51 asset 271,178.19 | public NFCs' F51 liability 42,285.55 | 228,893 | **Holder** (includes Railways; NAS public NFC includes departmental enterprises) |

---

## 6 Risks, gaps, open questions

### 6.1 Double-counting risks (each needs a test)

- **D1.** Government's **K8e** (−78,104) vs FSF Centre→State loans, which already include it. Write FSF − K8e (§2.7 C4). Test: the Centre→State I_LOAN sum over all refs = 41,791.65.
- **D2.** **K9b** vs FSF F89 RBI↔Centre. Replace the pair; never keep both.
- **D3.** **I_RESV / K8c** vs RBI's FSF RoW-counterparty assets (F1, F22 row, F3 row, F4 row: 714,817). This block writes nothing to I_RESV and drops those FSF cells.
- **D4.** **Railways budget support** as I_EQTY (Centre's F51 271,178) vs government's **K6** capital transfers to K_NFPU. government must keep GBS and PSU equity out of K6.
- **D5.** **PPF** in I_SSAV and in I_INPE: only in I_SSAV (test).
- **D6.** **Gold/jewellery** in I2/I2a vs PFCE: households must keep jewellery out of C_GJOM PFCE (the SUT has none on p125).
- **D7. Capital transfers to K_HH vs NAS asset-side household saving.**
  - NAS measures household "saving" as GCF + gold + net financial saving, so any capital transfer received is already inside it.
  - government's plan writes COFOG housing and other grants to K_HH (≈ 89,940) plus RoW 1,555.69. That would give households resources twice. K9_HH (an I_OTHR household asset not in NAS 5.3) makes it visible.
  - **Recommendation:** government writes household capital transfers as a memo only. Alternatively, closure lowers the K4a target by the same amount (which also changes D1's meaning). The orchestrator's decision is needed before the build.
- **D8.** Reinvested earnings: R14a (current) and FDI_reinvested_earnings (financial) are both required, not a double count. The domestic counterpart must equal R14a's payer split.
- **D9.** FSF intra-sector pairs: kept on both sides with one value (they cancel). Never take the holder value on one side and the issuer value on the other.
- **D10.** RoW E&O and reconciliation lines: no domestic posting; K9 absorbs them.
- **D11.** GPF: I_INPE (claims on K_GCEN/K_GSTA) plus D44 interest (fincorp R9c). government must not add GPF flows as current transfers.
- **D12.** MF look-through: households hold I_MFUN only. MF-held equity and bonds are K_MUTF's assets, not attributed to K_HH.

### 6.2 Where the gap-map method cannot be followed as written

| Ref | Gap map | Problem | Recommended fallback and why |
|---|---|---|---|
| K7, K8 | OFFICIAL, FSF mapped to 11 instruments; "FSF clears by construction" | FSF instrument markets do not clear (§2.6) | Pairwise control-side reconciliation; status derived/estimated; roles anchored/free |
| K7b | Post NAS/BoP differences to named counterparties | Needs a clearing base, which FSF lacks | Generalized: HH and RoW parts are rebuilt entirely (`hh_cp`, `row_cp`) from counterparty keys |
| K8 (HDFC) | Remove the reclassification from K_BANK/K_NBFC transactions "if confirmed" | HDFC Ltd is inside FSF ODC, so the merger is internal to K_BANK. The only visible artefacts (HFC-DT F3 −179,664, ODC borrowing from OFC 306,639, HFC-DT loans "to RoW" −235,254) vanish under the control rules | No explicit adjustment; memo in S4 |
| K8d | FSF holder flows × DEA share changes | T107/HB-5 shares shift at end-March 2024 because of the merger (rbi_financial_accounts-2) | Issuer-side holder split with FSF OFC sub-sector detail; DEA/T107 cross-check only |
| K9 (FCI bridge) | Move FCI from K_NFPU to K_GCEN with its instruments | No FCI balance sheet in clean data. NSSF loans to FCI are no longer material (`nssf.public_agencies.reductions` −350, MTNL only) | Not quantifiable; FCI stays inside the K9 of K_NFPU/K_GCEN; logged |
| K9 | FSF net financial transactions vs NAS net lending | FSF sector boundaries differ (nfc_pub = CPSEs, power, ports only) | K9 decomposition separates boundary/reconciliation from vintage |
| D3 | Remainder to the sector(s) disagreeing most | The disagreement is mostly FSF-internal | Corporate GCF pro rata (§2.3) |
| I3a | Centre/State pro rata GFCF | GG CIS is central | 100% K_GCEN |
| I1a | Centre vs States from capital outlay; FC from STRBI/RBI AR fixed-asset additions | No STRBI fixed-asset additions for banks; outlay includes non-GG heads | Treasury-view key (§2.2); RBI from AR; others by fincorp CFC |
| S5 | AIDIS scaled to FSF/NAS stocks | NAS publishes no stocks; no physical-wealth control | RBI T52(b) financial stocks; physical kept at 2018 values |
| K8b trade credit | "ECB & trade credit → I_LOAN" | Domestic side is FSF F81 | I_OTHR (agreed with rest_of_world) |

### 6.3 FSF quirks the builder must handle (all logged in `docs/phase2/issues/capital_financial.md`)

1. Insurers' equity: all counterparty `fc_ofc`; transaction 600,014.27 = stock change; valuation column 777,800 inconsistent with it.
2. PF equity split into three equal parts (5,954.21 each, to fc_odc/nfc_pub/nfc_pvt). It may be a merged cell in the source or an ingest effect. Ask the rbi_financial_accounts verifier to look at the raw cell.
3. SFC and SIDC hold implausible MF units (stocks 289,056 and 546,277 at end-March 2024). SIDC also shows 94,913 of trade-credit assets and almost no liabilities.
4. nfc_pvt round-number balancing items: other liabilities 300,000; other assets 100,100; intra F4 200,100/182,100; F81 52,500/270,000; F89 200,100/20,000.
5. FSF St 5 books RoW F3 = 0 and lumps FDI+FPI into F51/nfc_pvt.
6. RBI F6 2,566 appears only in the printed total; MMF F8 +1,100.
7. RBI foreign assets include revaluation (714,817 vs BoP reserves 526,931).
8. FSF nfc_pub covers CPSEs, ports and power only (sub-statements `nfc_pub_cpse`, `nfc_pub_ports`, `nfc_pub_power`).

### 6.4 Open questions (orchestrator / NAD)

- **Q1. Does NAS 2026 GG saving use the RBI surplus on a cash or an accrual basis?**
  - In 2022-23, FSF GG (which includes the accrued receivable, +57,331) agrees with NAS within 1,847 (FIN-1-gg). That would be unlikely if NAS were cash-based, since cash vs accrual differed by ≈57,109 that year.
  - If NAS is accrual-based, D0-7 (R6 cash 87,416.22) leaves a 123,458 hole in G_CEN's current account. Balancing would push it into other G_CEN entries, and K9_GCEN would carry a mirror item.
  - Evidence, not proof. Ask NAD; government and fincorp are affected.
- **Q2.** NAS 5.3 "state insurance" 8,498.51: State Government insurance funds (K_GSTA, default) or ESIC (a Central social security fund)?
- **Q3.** NHAI's institutional sector in NAS 2026 (GG or public NFC)? It changes the Centre GFCF key and K9.
- **Q4.** NAS 5.3 "shares, debentures, hybrid instruments in primary market" 72,487.32: is there an equity/debenture split?
- **Q5.** Railways' budget support: equity injection (FSF) or capital transfer in NAS 2026? It decides whether it belongs in I_EQTY or K6.
- **Q6. Size of K9.** Even after reconciliation, expect residuals of ₹0.5-2 lakh cr in some sectors (prototype: FC ≈ +1.6 lakh cr before the RoW step). They are findings, not balancing targets. BALANCING.md must list them with their decomposition.
- **Q7.** The GST back-to-back 78,104 is not in clean data (union_fiscal-13). If government cannot source it, K8e is absent and this block writes the full FSF figure (no double count, but the story cell is lost).

### 6.5 Framework requests (to `docs/phase2/FRAMEWORK_REQUESTS.md`, orchestrator to file)

- **FR-cf-1:** add `households` to capital_financial DEPENDS (for `hh_keys` in S5). It is acyclic: households depends only on production.
- **FR-cf-2:** a `components` filter on constraints (FC public/private GFCF; also requested by fincorp and households).
- **FR-cf-3:** a sign-flexible residual for K9. With x = a·z, z ≥ 0, a K9 entry cannot change sign during balancing. Either allow K9 as a signed free variable, or let the block write paired `residual_pos`/`residual_neg` entries. The same issue affects government's K3a and closure's K4a.
- **FR-cf-4:** a block-local parameter file (e.g. `pipeline/sam/blocks/capital_financial/params.yaml`) for the instrument control-side table, default counterparties and key choices, so the verifier can audit them and the sensitivity runs (equity control, insurer strip, D3 rule) are switches, not code edits.
- **FR-cf-5:** permit constraints whose members are all fixed (e.g. `cf.k7a.hh_assets`) as documentation, or state that they must be block tests.

---

## 7 Tests the builder should write

All targets are read from clean data inside the test (never typed). Tolerances are ₹ crore.

| # | Test | Official total / source | Tol |
|---|---|---|---|
| T1 | I1a column sums by NAS sector = NAS 1.11 (6 series `s1_11.<sector>.current`), after the SUT/NAS scale | NAS 1.11 | 1 |
| T2 | I1a row sums by commodity = SUT GFCF by product aggregated with the concordance (12 non-zero commodities); total = `use.gfcf.total.current` 9,245,762.485522 | SUT | 0.01 |
| T3 | I2 = `s1_9.saving_in_the_form_of_gold_and_silver_ornaments.current` 172,126.567611 = `s5_3.saving_in_form_of_gold_and_silver_ornaments.current`; I2 + I2a = `use.valuables.total.current` 376,232.00 | NAS, SUT | 1e-6 |
| T4 | I3a by NAS sector = `s1_14.<s>.gross_capital_formation.current` − `s1_11.<s>.current` (within scaling); Σ I3a = `use.cii.total.current` 382,329.00; public I3a = `s7_2a.total.cis.current` 116,527.4 (±0.1) | NAS, SUT | 0.1 / 0.01 |
| T5 | K1 = `s1_9.public_non_financial_corporations.current` 462,996.248646 and `s1_9.private_non_financial_corporations.current` 2,410,408.526921 | NAS 1.9 | 1e-6 |
| T6 | K4 constraint target = `s1_9.household_sector.current` = `s1_14.households_npish.gross_savings.current` = `s5_3.household_saving_1_2_3_4.current` (5,890,330.45) | NAS | 0.5 |
| T7 | K7a: Σ = `s5_3.gross_financial_saving.current` 3,602,198.51. Each NAS 5.3 line maps to exactly one instrument (census). I_SSAV ← K_HH = `nssf.net_collection` 421,678.36 = small savings + `nssf.ppf.additions`. I_INPE ← K_HH = insurance_funds + provident_and_pension_funds − PPF = 1,260,185.57. PPF appears in no I_INPE component | NAS 5.3, NSSF | 0.01 |
| T8 | K8a = `s5_3.financial_liabilities.current` 1,909,286.70; household net = `s5_3.net_financial_saving_of_household_sector_1_4.current` 1,692,911.81 | NAS 5.3 | 0.01 |
| T9 | PPF check: T52(b) `t52b.fa_ppf.current` (2024-03-31) − (2023-03-31) = `nssf.ppf.additions` | RBI, NSSF | 0.1 |
| T10 | FSF extract reproduces St 7 and statement totals before reconciliation: `fsf7.all.assets.transaction.total.current` 13,843,740.93, `fsf7.all.liabilities.transaction.total.current` 13,893,643.40; per-K leaf sums equal §2.1; the §2.6 non-closure table recomputes | FSF | 1 |
| T11 | Reconciliation audit: for every instrument except I_OTHR and I_RESV, Σ domestic holders' `dom` = Σ domestic issuers' `dom` exactly; every row of `s4_fsf_dual_reports` has the control-side value equal to its source cell | FSF | 1e-6 |
| T12 | Household counterparts: for each instrument, Σ `hh_cp` on counterparties = the K7a/K8a value | NAS 5.3 | 1e-6 |
| T13 | RoW counterparts: for each K8b line, Σ `row_cp` in the same instrument = rest_of_world's entry (or 0 for `unallocated_k9`); `fdi_reinvested_earnings` counterparts = R14a entries by payer | rest_of_world | 1e-6 |
| T14 | Prior market clearing: every I_* except I_OTHR has row = column (with all blocks' prior entries) | all | 0.01 |
| T15 | Walras: I_OTHR row = column in the prior. Failure points to a block whose saving/GCF/K6/RoW totals are not NAS-consistent | all | 1 |
| T16 | Every domestic K_* balances in the prior (K9 closes it); Σ `k9_decomposition` components = K9_s; K9_HH = net capital transfers to K_HH (0 if D7 is resolved as recommended) | all | 0.01 |
| T17 | X_DISC: Σ D3 = `derived.si_errors_omissions.current` 358,633.928553; D3→K_HH = I2a to 1e-6; remainder shares sum to 1 and equal the published GCF shares | NAS | 1e-6 |
| T18 | K9b = `k9b.change_in_surplus_payable.current` 123,457.77; K9b + `fsf_f89` remainder = `fsf.fc_rbi.liabilities.transaction.f89.gg_cen.current` 121,647.69 | RBI AR, FSF | 0.01 |
| T19 | Centre→State I_LOAN, all refs (`dom` + government K8e) = `fsf.gg_cen.assets.transaction.f4.gg_sta.current` 41,791.65 = `afs.cfi_cap_disbursements.7601` − `afs.cfi_cap_receipts.state_governments` − `afs.cfi_cap_receipts.union_territories_with_legislature` (±0.1) | FSF, AFS | 0.1 |
| T20 | Currency: K_RBI ← I_CURR = `fsf.fc_rbi.liabilities.transaction.f21.all.current` + (NAS − FSF household currency) | FSF, NAS | 0.01 |
| T21 | HDFC memo: `rtp.scb_bs.loans_advances.scb.current` − `…loans_advances_excl_merger…` = 525,274 and deposits difference = 110,114 (vintage 2024-12-26) | RTP | 0 |
| T22 | Structural guards: no entry by this block with row or col K_ROW, I_RESV or R_ROW; no zero-valued entries; no `other`/`nec` FSF item written; RBI F6 not written; MF monetary gold not written | structural | exact |
| T23 | Roles: K7a, K8a, K1, I2, I2a, D3 fixed; K9 free low; `hh_cp`/`row_cp` free high; estimated entries have non-empty provenance `method` | structural | exact |
| T24 (report, non-blocking) | Sensitivity table: K9 by sector under (a) equity holder vs issuer control, (b) insurer strip on/off, (c) D3 rule pro rata vs all-to-K_NFPU; plus the 2022-23 FSF run of the same rules against FIN-1 2022-23 | FSF, NAS | report |
| T25 | S5: financial assets Σ over groups = `t52b.fa.current` 41,470,111.9 and institutional debt = `t52b.fl.current` 12,130,649.0; group shares = hh_keys shares | RBI T52(b) | 1 |

---

## 8 Cross-plan review (2026-09-30, cross-plan critic; details and ids in `CROSS_REVIEW.md`)

What this block must change or confirm:

1. **XR-3 capital transfers to K_HH (decision D-3).** Recommended: government writes them (COFOG ≈ 89,940 + RoW 1,555.69). You post K9_HH (an I_OTHR household asset) as a named finding: NAS household saving is measured from the asset side, so it cannot see them. This keeps GG capital transfers equal to NAS 4.2. If the orchestrator chooses memo only, K9_HH = 0.

   Either way, F36/F37 (timeseries) read K7a/K8a only, so the NAS 5.3 household series is unaffected.
2. **XR-17 sign lock on K9:** write each sector's K9 as a `residual_pos` / `residual_neg` pair (FRAMEWORK_REQUESTS P-9), so balancing can cross zero. Do not rely on the prior's sign.
3. **XR-27 Q1 (RBI surplus basis):** fincorp's new-base 2023-24 evidence (E_RBI saving on cash vs NAS public FC saving − GOS, within ₹122 cr) outweighs the FSF 2022-23 hint. Close Q1 as cash (D0-7). State in K9b's method that, with cash-basis income, the two K9b legs (1,23,457.77) are offset by equal and opposite parts of K9_GCEN and K9_RBI (a financial reclassification with no income counterpart).
4. **XR-6 boundary:** E_BANK ≡ K_BANK ≡ FSF ODC. Your choice (HDFC Ltd inside K_BANK; no merger adjustment) is now the rule for fincorp too. Use fincorp's `fc_public_private` on that boundary. It carries GOS, not CFC, so use your GOS fallback for the FC GFCF split and log it.
5. **XR-19 component names (timeseries):**
   - K7a I_DEPO components `banks`, `coop_banks` (rename `coop`), `nonbank_deposits` (rename `non_banks`), `trade_debt`, and `ppf` on I_SSAV;
   - write **K8a** as NAS 5.3 liability-line components (`banks`, `coop_banks`, `nbfc`, `government`, `insurers`, …) summing to 19,09,286.70, not one `total` entry. The lender split for K7b stays in `hh_cp`.

   Freeze these names.
6. **XR-15:** `cf.i1a.gfcf.total` (tol 0.01) and `cf.valuables.total` duplicate production's `gfcf.*` / `valuables.*` targets (tol = SUT cells). Drop them or copy production's tol_abs; keep them as tests.
7. **XR-18 DAG:** DEPENDS += households, for S5 (recommended for approval). Read `aidis_fin_assets`, `aidis_inst_loans`, `aidis_noninst_loans` (to be published), `pop_households`.
8. **XR-7 Centre/State:** your I1a Centre/State key follows the treasury view, like government. If the orchestrator adopts the institutional view (decision D-5), move GFCF by CSS societies and ULB capital financed directly by the Union to G_STA/K_GSTA. Keep the treasury key as a sensitivity.
9. **Confirmed consistent across plans:**
   - PPF only in I_SSAV;
   - D3 → K_HH = I2a (2,04,105.432389) and D3 total = NAS 3,58,633.928553; closure absorbs the 0.107 X_DISC rounding (XR-16);
   - Centre→State I_LOAN `dom` = 41,791.65 + 78,104 = 1,19,895.65. government derives T2b(ii) 78,104 exactly from clean data (AFS GST Compensation Fund outgo less grants), which answers your Q7;
   - all FSF RoW-counterparty cells dropped and rebuilt from K8b;
   - GG inventories 100% K_GCEN.

   The components filter (P-1) now makes the FC public/private GFCF totals expressible: declare them. All-fixed documentation constraints (FR-cf-5) are not confirmed by the framework; if they are rejected, keep them as tests.
