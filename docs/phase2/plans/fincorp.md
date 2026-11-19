# Block plan: `fincorp` (financial corporations, interest, dividends, D44, non-life insurance)

Written 2026-09-30 by the fincorp data scout / method planner (research only; no code written, no `pipeline build`/`sam`/`repro` run). Contract: `docs/phase2/DESIGN_BRIEF.md`. Every number below was read from `data/clean/<unit>/*.parquet` with polars in a scratch script outside the repo. Amounts are ₹ crore, current prices, FY 2023-24 unless stated. Values in the "indicative" columns are the planner's sizing arithmetic on clean data; the builder recomputes every one of them in code and must not type them in.

Refs owned: **F4a R3 R3a R3b R4 R5 R8 R8a R9c R17 K2 K2a**, satellite **S9**. Allowed DEPENDS today: `production`, `households`, `factors` (framework `BLOCK_DEPENDS`). Two extra dependencies are requested in §4.3.

---

## 1. Summary (plain English)

- **What the block does.** It builds the income side of India's financial sector: how much operating surplus each of RBI, banks, NBFCs and insurance/pension funds earns; the interest the Centre and States pay and who receives it; interest between banks, NBFCs and their depositors and borrowers; dividends; the investment income that insurers and PF/pension funds pass to their members (D44); non-life premiums and claims; and financial corporations' saving. It also publishes the gross flows of PF, NPS, GPF, PPF and life insurance as a memo table (S9).
- **Better anchors than the gap map expected.** NAS 2026 Statement 8.12 publishes the **GVA of each financial sub-sector** (central bank ₹8,260.73 cr; deposit-taking ₹8,95,216.41 cr; other financial ₹5,74,513.41 cr; insurance and pension ₹1,80,064.43 cr). RBI's GVA equals RBI's employee cost plus depreciation to the rupee. So the operating-surplus split (F4a) rests mostly on official numbers, and only the wage bill of banks versus NBFCs has to be estimated.
- **The official totals the block must hit:** financial-corporation gross saving ₹9,91,447.76 cr (public ₹5,35,509.90 cr, private ₹4,55,937.86 cr); FC operating surplus ₹10,86,708.96 cr; Union interest paid ₹11,01,867.87 cr cash; States ₹5,07,175.37 cr; NAS FISIM ₹12,60,576.16 cr.
- **What is weak.** No source for dividends paid by private companies (RBI corporate finances are DBIE-only), no STRBI or BSR (DBIE-only), no yields on corporate bonds or equities, and no distribution of financial assets by household quintile newer than AIDIS 2019. These cells are estimated with low confidence, and balancing will move them.
- **Two findings for the owner.** (1) The RBI's 2023-24 SNA income less the cash surplus it actually paid the Centre (₹87,416 cr) is ₹1,01,399 cr. NAS's public-FC saving exceeds public-FC operating surplus by ₹1,01,277 cr, which matches within ₹122 cr. That supports decision D0-7 (RBI surplus on a cash basis). (2) NAS "small savings" in Statement 5.3 (₹3,09,750.90 cr) equals the NSSF accretion to savings deposits and certificates exactly. So PPF (₹1,11,927.46 cr) is only in "PF & pension", and the gap map's PPF double-count worry is settled by data.
- **Main risks.** The same interest or dividend could be written twice, by this block and by `rest_of_world` or `government` (§5). FISIM handling must match the households block's FISIM in PFCE. And insurers' current account may not close to a small saving (§6).

---

## 2. Ref-by-ref plan

### 2.0 Overview table

Status label = what the entry's `status` field will say. Role/confidence follow DESIGN_BRIEF §3 (anchored weight 16; free high 4 / medium 1 / low 0.25).

| Ref | Cell (row ← col) | Entries to write | Main sources (dataset: series) | 2023-24 key values | Role | Status |
|---|---|---|---|---|---|---|
| F4a | E_RBI, E_BANK, E_NBFC, E_INSP ← F_GOSC | 7 entries: E_RBI/public; E_BANK, E_NBFC, E_INSP × {public, private} | `mospi_nas_2026_s8_12`; `io_tables_sut_va` i55/i56; `rbi_banking_corporate_rbi_accounts`; `rbi_banking_corporate_rtp_banks`, `_rtp_coop`; `mospi_nas_2026_s7_1a/b` | FC GOS 10,86,708.96; FINS GOS 9,68,693.09; INSR GOS 1,18,016.09; E_RBI 370.62 | E_RBI, E_INSP anchored (tol 0.01); E_BANK, E_NBFC free medium; public/private components free medium | derived (E_RBI, E_INSP), estimated (rest) |
| R3 | G_CEN ↔ G_STA (interest between governments) + the payer control totals | G_CEN←G_STA loans and NSSF; G_STA←G_CEN 14-day ITBs and G-secs in States' reserve funds | `union_fiscal_fa_expenditure` fa9.2049.*; `state_fiscal_rbi_sf_appendices` app2 C.2.*; `union_fiscal_fa_receipts` fa8.0049.* | Union 11,01,867.87; States 5,07,175.37; States→Centre loans 15,072.31, NSSF 29,585.96 | anchored tol 0.02 (cash lines); holdings-based parts free medium | official / derived |
| R3b | (no entries) NAS-concept bridge | constraint + `gov_interest_bridge` satellite | as R3 plus fa8.0049.03.116/.117, `union_fiscal_nssf` | accrual netting 38,778.00; intra-G consolidation 1,88,602.86; NSSF interest to savers ≈2,14,947.87 | — | derived / estimated |
| R3a | E_RBI, E_BANK, E_NBFC, E_INSP, E_NFPU, E_NFPR ← G_CEN, G_STA | by holder × instrument component | `rbi_financial_accounts_hbs_gsec_ownership` t107.*; `rbi_financial_accounts_dea_gsec_ownership`; `rbi_financial_accounts_dea_central_debt`; `rbi_financial_accounts_fsf_balance_sheets`; RBI AR sch13 | market loans 7,26,415.54; SDLs 3,69,267.41; T-bills 60,237.27; RBI G-sec income 90,194.80 | E_RBI anchored; recap bonds anchored; rest free medium | estimated |
| R4 | NFC, GOV, FC ← E_BANK, E_NBFC, E_RBI (household part goes to R8a) | SNA interest on deposits and borrowings by counterparty | `rbi_banking_corporate_rtp_banks/_coop/_nbfi`; `rbi_financial_accounts_fsf_balance_sheets`; `mospi_nas_2026_s1_13` | SCB interest expended 11,53,173; SCB cost of deposits 4.8% | free low–medium | estimated |
| R5 | E_BANK, E_NBFC, E_INSP ← H_R1..H_U5, E_NFPU, E_NFPR | SNA interest on loans (and on non-government debt securities held by FCs) | same as R4; `rbi_banking_corporate_bsr1_mar2024`; `rbi_financial_accounts_hh_finsav_52ab` | SCB interest income 20,09,929; return on advances 9.4% | free low–medium | estimated |
| R8 | E_NFPU, E_NFPR, E_BANK, E_NBFC, E_INSP ← E_NFPU, E_NFPR, E_BANK, E_NBFC, E_INSP (household part in R8a; GOV = R7; ROW = R14) | dividends by issuer × domestic corporate holder | `union_fiscal_fa_receipts` fa8.0050.*; `rbi_financial_accounts_fsf_balance_sheets` F51; `finsector_markets_irdai_life/_nonlife` appropriations; `finsector_markets_sebi_mf` t72 | Union CPSE dividends 63,827.41; LIC 4,272.54; nationalised banks 13,806.57 | free low | estimated |
| R8a | H_R1..H_U5 ← G_CEN, G_STA, E_BANK, E_NBFC, E_INSP, E_NFPU, E_NFPR | household property income by group, component per instrument | inputs of R3a/R4/R8 + `households` hh_keys | NSSF liabilities avg 29,36,851.67; household bank deposits avg 1,34,48,266.75 | free low | estimated |
| R9c | H_R1..H_U5 ← E_INSP, G_CEN, G_STA | D44 by scheme component | `finsector_markets_irdai_life`; `finsector_markets_epfo_ar`; `finsector_markets_pfrda_nps`; `union_fiscal_fa_expenditure`; `state_fiscal_rbi_sf_appendices` | life 3,77,927.22; EPF ≈1,16,887.34; GPF Union 18,871.50 | GPF Union anchored; life free medium; others free low | estimated |
| R17 | E_INSP ← H_*, E_NFPU, E_NFPR (premiums); H_*, E_NFPU, E_NFPR ← E_INSP (claims, premium supplements) | by line of business | `finsector_markets_irdai_nonlife` t44, t51; `finsector_markets_irdai_summary` sum_c | net claims 1,72,290.46; net premium earned 2,08,791.32; policyholder investment income ≈37,843.90 | free medium (totals), low (payer split) | estimated |
| K2 | K_RBI, K_BANK, K_NBFC, K_INSP ← E_RBI, E_BANK, E_NBFC, E_INSP (total) | constraint only | `mospi_nas_2026_s1_9` | 9,91,447.755011 (public 5,35,509.8992; private 4,55,937.855811) | fixed via constraint | official |
| K2a | same cells, split | 7 entries (E_RBI public; others × public/private) | K2 + F4a + RBI AR | RBI prior 1,01,399.09 | free low | estimated |
| S9 | satellite `s9_funded_schemes` | ~30 rows | EPFO, PFRDA, IRDAI, Union FA St 14, RBI SF App. III/IV, NSSF | see §2.13 | — | official / derived / estimated per row |

### 2.1 F4a: FC operating surplus by sub-sector

**Anchors (all 2023-24, vintage 2026-08-31 unless stated):**

| Item | Dataset: series_id | Value |
|---|---|---:|
| GVA central bank S121 | `mospi_nas_2026_s8_12`: `s8_12.central_bank_s_121.current` | 8,260.73 |
| GVA deposit-taking excl. central bank S122 (+S123 MMFs, per label) | `s8_12.deposit_taking_corporations_excluding_central_bank_s_122_and.current` | 8,95,216.41 |
| GVA OFC S124–S127 | `s8_12.other_financial_corporations_s_124_to_s_127.current` (= S124+S125 3,04,040.84 + S126 1,75,704.50 + S127 94,768.08) | 5,74,513.41 |
| GVA ICPF S128–S129 | `s8_12.insurance_corporation_and_pension_funds_s_128_to_s_129.current` (life 88,576.95; non-life 91,487.48; pension funds S129 **0.00**) | 1,80,064.43 |
| GVA S12 total | `s8_12.gross_value_added_s_12.current` (= `s1_14.fc_public` 7,14,051.72 + `fc_private` 9,44,003.27) | 16,58,054.98 |
| SUT Financial services (ind. 55): GVA / CE / NPT / OS / CFC | `io_tables_sut_va`: `va.gva_production.sut_i55.current`, `va.ce.sut_i55.current`, `va.net_production_taxes.sut_i55.current`, `va.os_mi.sut_i55.current`, `va.cfc.sut_i55.current` | 14,77,990.82 / 5,08,700.79 / 597.24 / 8,98,218.98 / 70,474.11 → **GOS 9,68,693.09** |
| SUT Insurance (ind. 56) | same with `sut_i56` | 1,80,064.00 / 61,975.15 / 72.76 / 1,09,430.21 / 8,585.88 → **GOS 1,18,016.09** |
| Public FC GOS | `mospi_nas_2026_s7_1a`: `s7_1a.financial.os.current` 4,17,603.91 + `s7_1a.financial.cfc.current` 16,628.71 | **4,34,232.62** |
| Private FC GOS | `mospi_nas_2026_s7_1b`: `s7_1b.financial.os.current` 5,90,045.30 + `.cfc` 62,431.04 | **6,52,476.34** |
| RBI employee cost / depreciation | `rbi_banking_corporate_rbi_accounts`: `is.exp_employee_cost.current` 7,890.11; `is.exp_depreciation.current` 370.62 (vintage 2024-05-30 = AR 2023-24; 2025-05-29 repeats the same values; name one) | |

Industry 55 GVA equals 8.12 S121+S122+S124–S127 (difference ₹0.26 cr), and industry 56 GVA equals 8.12 S128–S129 (₹0.43 cr). So in NAS the FC sector coincides with SUT industries 55+56, and 7.1C shows zero household-sector financial output.

**Steps:**
1. **E_RBI** = 8.12 S121 GVA − RBI employee cost = 8,260.73 − 7,890.11 = **370.62**, which equals RBI depreciation exactly (output of the central bank is valued at cost). Component `public` only. Role anchored, tol_rel 0.01, status derived.
2. **E_INSP** = SUT ind. 56 GOS = **1,18,016.09** (GVA − CE − NPT). Anchored tol 0.01, status derived. Pension funds (S129) have zero GVA, so all of it is insurers' (life ≈ half, non-life ≈ half by 8.12 GVA).
3. **E_BANK and E_NBFC:** GVA from 8.12, scaled by 14,77,990.82 / 14,77,990.55 so that E_RBI + E_BANK + E_NBFC = SUT ind. 55. CE split: E_BANK CE = bank wage bills, RTP vintage 2025-12-29: `rtp.scb_pl.wage_bill.scb.current` 2,94,488 + `rtp.rrb_pl.wage_bill.rrb.current` 15,305 + `rtp.ucb_pl.staff_expenses.ucb.current` 7,365 + `rtp.stcb_pl.wage_bill.stcb.current` 2,077 + `rtp.dccb_pl.wage_bill.dccb.current` 7,430 = 3,26,665. E_NBFC CE = SUT ind. 55 CE − RBI − banks = 1,74,145.68 (residual). NPT of ind. 55 (597.24) is split pro rata to GVA between E_BANK and E_NBFC. Indicative: **E_BANK ≈ 5,68,187.63; E_NBFC ≈ 4,00,134.27**. Both free, medium confidence, status estimated.
   - Cross-check: bank "GVA proxy" = operating profit + wage bill (SCB groups, RRB, UCB, StCB, DCCB) = 9,55,261 against 8.12 S122 8,95,216 (+6.7%). Log it; do not use it to override 8.12.
4. **Public/private components** (the gap map's "public part + private part"):
   - E_BANK public = PSBs + RRBs. Share = (PSB + RRB operating profit) / all bank operating profit = (2,58,964 + 15,938) / 6,28,596 = 43.73% (`rtp.scb_pl.operating_profit.{psb,pvb,fb,sfb,pb}`, `rtp.rrb_pl.operating_profit.rrb`, `rtp.{ucb,stcb,dccb}_pl.operating_profit.*`, vintage 2025-12-29). **Co-operative banks go to private** (see §5 C1).
   - E_INSP public = LIC + public general insurers + specialised (AIC, ECGC). Life: LIC share of operating expenses 48,121.68 / 89,043.91 (`finsector_markets_irdai_life`: `t24.operating_expenses.lic.current`, `t24.operating_expenses.insurers_life.current`). Non-life: (public + specialised) share of net premium earned (80,188.34 + 6,915.85) / 2,08,791.32 (`finsector_markets_irdai_nonlife`: `t44.net_premium_earned.total.{general_public,general_specialized,insurers_general_direct}.current`). Life vs non-life GOS in proportion to 8.12 GVA (88,576.95 : 91,487.48).
   - E_NBFC public = **residual** so that the public parts sum to 4,34,232.62. Indicative ≈ 1,29,000, about 32% of E_NBFC. Plausibility check against `rtp.nbfc_ownership.asset_share_government.nbfc` (37.5%, end-March 2024) plus AIFIs (all public; `rtp.aifi_pl.*`). Log the residual's share; if it falls outside 20–50%, raise it in `docs/phase2/issues/fincorp.md`.
   - Private parts = sub-sector total − public part; they sum to 6,52,476.34 by construction.
5. Declare the constraints in §3 (C-F4a-1…4).

### 2.2 R3: government interest, cash, by payer (control totals + inter-government entries)

**Union (`union_fiscal_fa_expenditure`, Finance Accounts 2023-24, vintage 2024-12-10):** `fa9.2049.total` **11,01,867.87** = internal debt `fa9.2049.01.total` 10,10,670.85 + external `fa9.2049.02.total` 29,616.74 + small savings/PF `fa9.2049.03.total` 48,712.69 + reserve funds `fa9.2049.05.total` 1,111.55 + other obligations `fa9.2049.60.total` 11,756.04. Cross-check: AFS equals it (RECONCILIATION GOV-6).

**States (`state_fiscal_rbi_sf_appendices`, RBI State Finances 2025-26, vintage 2026-01-23, all States and UTs with legislature):** `app2.total_expenditure.ii.c.2-interest_payments.in.all_states_uts.actuals` **5,07,175.37** = loans from Centre (`…ii.c.2.i-…`) 15,072.31 + internal debt (`…ii.c.2.ii-…`) 4,26,313.59 [market loans `…ii.a-…` 3,69,267.41; NSSF `…ii.b-…` 29,585.96; other internal debt, derived, 27,460.22] + small savings/State PF (`…ii.c.2.iii-…`) 54,183.14 + others (`…ii.c.2.iv-…`) 11,606.33. Cross-check: FC16 KFI 28 States `state_fiscal_fc16_kfi`: `kfi.b_1_a-interest_payments.in.all_states_28` 4,94,910.97 (bridge GOV-5: residual 0.3%).

**Entries under R3 (government ← government; official cash):**

| Entry | Value | Source | Role |
|---|---:|---|---|
| G_CEN ← G_STA, component `central_loans` | 15,072.31 | States' payment (above) | anchored 0.02 |
| G_CEN ← G_STA, component `nssf` | 29,585.96 | States' interest on NSSF (NSSF is inside G_CEN: ACCOUNT_STRUCTURE I_SSAV) | anchored 0.02 |
| G_STA ← G_CEN, component `itb_14d` | 1,976.32 | `fa9.2049.01.116` (14-day T-bills are held only by State governments) | anchored 0.02 |
| G_STA ← G_CEN, component `gsec_state_reserve_funds` | ≈14,783 + ≈3,927 | T107 `others_state_governments` share × market loans / T-bills (§2.4) | free medium |

The Union books only 13,641.26 as received (`union_fiscal_fa_receipts`: `fa8.0049.01.total` 13,555.62 + `fa8.0049.02.total` 85.64). This is RECONCILIATION GOV-7 (UNEXPLAINED, −1,431). The SAM follows the payer; log the difference.

### 2.3 R3b: from cash to NAS-concept interest (constraint + bridge satellite, no entries)

NAS 1.13 allocates **zero** FISIM to public administration (`mospi_nas_2026_s1_13`: `s1_13.public_administration_and_defence.current` = 0.00), so no FISIM adjustment is made to government interest. The bridge for the Union:

| Step | Series | Value |
|---|---|---:|
| A. Cash interest | `fa9.2049.total` | 11,01,867.87 |
| B. less intra-G_CEN (consolidated): interest to NSSF | `fa9.2049.01.121` 6,779.76 + `.122` 1,12,843.89 + `.125` 65,738.26 | −1,85,361.91 |
| … reserve funds | `fa9.2049.05.total` | −1,111.55 |
| … special securities to FCI (FCI is in G_CEN on the new base) | `fa9.2049.60.107` | −911.74 |
| … PLI securitisation securities (PLI is a Public Account scheme, MH 8014) | `fa9.2049.60.111` | −1,217.66 |
| C. less non-interest: management of debt (a fee, not D41) | `fa9.2049.01.305` | −2,921.79 |
| D. less accrued interest and premium received on re-issues (Receipt Budget nets them against expenditure) | `union_fiscal_fa_receipts`: `fa8.0049.03.117` 26,465.89 + `fa8.0049.03.116` 12,312.11 | −38,778.00 |
| E. plus NSSF interest paid to small savers (estimated; NSSF is inside G_CEN) | proxy = NSSF interest receipts 1,85,361.91 + States' NSSF interest 29,585.96 | +2,14,947.87 |
| **NAS-concept Union interest (indicative)** | | **10,86,513.09** |

- E's proxy implies 7.32% on average small-savings liabilities of 29,36,851.67. Those liabilities are the savings deposits + certificates + PPF opening balances in `union_fiscal_nssf`: `nssf.{savings_deposits,savings_certificates,ppf}.opening`, 2023-03-31 (vintage 2025-02-01) = 27,26,012.49 and 2024-03-31 (vintage 2026-02-01) = 31,47,690.85. The end-March 2024 figure equals `nssf.total_deposits` and FSF `fsf.gg_cen.liabilities.outstanding.f22_f29.hh.current`. The NSSF accumulated deficit `nssf.accumulated_income_expenditure_balance` of 8,772.61 at 2024-03-31 shows the fund runs close to balance. That justifies the proxy; confidence medium.
- D is a choice (§5 C4); the alternative (cash) is +38,778 higher.
- **States:** A = 5,07,175.37; less `…ii.c.2.iv-others` 11,606.33, treated as reserve-fund/deposit interest internal to G_STA (**to verify**: the line is not itemised); no accrual data → **4,95,569.04 (indicative)**.
- The satellite `gov_interest_bridge` stores every line above, plus the holder allocation (§2.4) including the RoW part and all intra-G items, with prov_ids.

### 2.4 R3a: government interest by holder

**Holder shares** (`rbi_financial_accounts_hbs_gsec_ownership`, HBS T107, vintage 2026-07-31; identical to DEA Status Paper HB-5 in `rbi_financial_accounts_dea_gsec_ownership` `sp_hb5.*`, vintage 2025-08). Average of 2023-03-31 and 2024-03-31, in %:

| T107 category | Central G-secs `t107.gsec_central.share.*` | SDLs `t107.sgs.share.*` | T-bills `t107.tbills.share.*` | SAM account |
|---|---:|---:|---:|---|
| commercial_banks | 37.135 | 34.025 | 56.225 | E_BANK |
| cooperative_banks | 1.555 | 3.515 | 1.480 | E_BANK |
| non_bank_pds | 0.575 | 0.610 | 2.255 | E_NBFC |
| insurance | 25.975 | 26.470 | 5.585 | E_INSP |
| mutual_funds | 2.855 | 2.015 | 13.595 | look-through to unit holders (SEBI T72) |
| provident_funds | 4.590 | 21.820 | 0.125 | E_INSP |
| pension_funds | 4.250 | 4.785 | 0.040 | E_INSP |
| financial_institutions | 0.765 | 1.715 | 5.440 | E_NBFC |
| corporates | 1.485 | 2.010 | 4.745 | E_NFPU/E_NFPR by FSF `nfc_pub`:`nfc_pvt` holdings of gg F3 |
| fpi | 1.850 | 0.045 | 0.205 | **R_ROW, written by `rest_of_world` under R14** (§5 C5) |
| rbi | 13.285 | 0.675 | 0.000 | E_RBI (replaced by the RBI AR control, below) |
| others | 5.680 | 2.310 | 10.305 | of which `others_state_governments` 2.035 / 0.260 / 6.520 → G_STA (R3, above; the SDL part is intra-G_STA, drop); rest → H_*, E_NFPU, E_NFPR in proportion to FSF `fsf.gg_cen.liabilities.outstanding.f3.{hh,nfc_pub,nfc_pvt}` (low confidence) |

**Steps:**
1. **Market loans** `fa9.2049.01.101` 7,26,415.54 (net of D's share of the re-issue receipts, pro rata) × central shares. Indicative gross: banks 2,69,754; insurance 1,88,686; PF 33,342; pension 30,873; MF 20,739; others 41,260; FPI 13,439.
2. **SDLs** `…ii.c.2.ii.a-interest_on_market_loans` 3,69,267.41 × SDL shares. Indicative: banks 1,25,643; insurance 97,745; PF 80,574; pension 17,669.
3. **T-bills** `fa9.2049.01.103` 10,809.07 + `.108` 19,369.59 + `.110` 30,058.62 = 60,237.27 × T-bill shares. The `.103` line is labelled "T-bills issued to RBI", but no 91-day line exists and T107 shows RBI holding 0 T-bills. Treat it as 91-day T-bills (inference, logged).
4. **E_RBI control:** RBI interest on rupee securities `sch13.a.interest_on_holding_of_rupee_securities.current` 92,589.51 + amortisation `sch14.a.amortisation_of_premium_discount_on_rupee_securities.current` −2,394.71 = **90,194.80** (SNA accrual). Split between G_CEN and G_STA by T107 RBI holdings. Anchored tol 0.02. The T107 RBI share × market loans gives 96,504, 7% above; the other holders are scaled so each instrument still sums to its payer line. WMA interest from the Centre (`fa9.2049.01.115` 394.38) is a separate E_RBI ← G_CEN component `wma`. It is **inside** RBI's `sch13.a.interest_on_loans_and_advances.current` 2,094.09, so §2.5 step 7 must subtract it (and any States' WMA/overdraft interest) from that line before using the remainder for RBI ↔ bank/NABARD flows.
5. **Instrument lines with a known holder:** recapitalisation bonds `fa9.2049.01.132` 17,689.57 + `.133` 1,603.20 and SBI special bonds `fa9.2049.60.110` 834.67 → E_BANK (public component), anchored. Union interest on "insurance and pension funds" `fa9.2049.03.108` 18,841.04 and "special deposits and accounts" `fa9.2049.03.109` 11,000.76 → **E_INSP** (EPFO's EPS deposit in the Public Account is 2,26,530.85 at end-March 2024, `finsector_markets_epfo_ar`: `invest.eps.public_account_central_govt.current`; 18,841/2,26,531 ≈ 8.3%; special deposits of non-government PFs `rbi_financial_accounts_dea_central_debt` `sp_hb1b.special_deposits_nongovt_pf.current` 97,701). This is an inference; log it. Petroleum `fa9.2049.60.106` 6,847.71, fertiliser `.109` 604.00, green bonds `fa9.2049.01.134` 1,151.20, conversion securities `.118` 1,243.07, other internal debt `fa9.2049.01.200` 10,015.13 and deposits `fa9.2049.60.101` 1,340.26 → market-loan holder shares excluding RBI, low confidence. Sovereign gold bonds `fa9.2049.01.129` 1,468.20 and gold monetisation `.130` 193.54 → households (R8a).
6. **States' other internal debt** 27,460.22 (NABARD, banks, LIC, NCDC loans) → E_NBFC/E_BANK/E_INSP pro rata FSF `fsf.gg_sta.liabilities.outstanding.f4.{fc_odc,fc_ofc}`, low confidence.
7. **Households' share** (small savings E, 'others' HH part, SGBs, MF look-through share) is written in **R8a**, not here. **GPF/State PF interest** is written in **R9c**, not here. The **FPI and external-debt part** is written by `rest_of_world` (R14), not here. fincorp computes those numbers only for the bridge satellite and the payer constraints.

### 2.5 R4 and R5: interest between FCs and non-government sectors (SNA basis)

Lender P&L totals (bank-interest basis; `rbi_banking_corporate_rtp_banks`, `_rtp_coop`, `_rtp_nbfi`; use vintage **2025-12-29** where present, else 2024-12-26, and record which):

| Lender | Interest income | Interest expended |
|---|---:|---:|
| SCBs `rtp.scb_pl.interest_income.scb.current` / `interest_expended` | 20,09,929 | 11,53,173 |
| RRBs `rtp.rrb_pl.interest_income.rrb` / `interest_expended` | 61,341 | 33,237 |
| UCB / StCB / DCCB `rtp.{ucb,stcb,dccb}_pl.interest_income/expended` | 50,698 / 30,974 / 49,989 | 30,282 / 23,793 / 32,731 |
| NBFC-UL / ML `rtp.nbfc_layer_pl.fund_based_income` / `interest_payment` | 1,71,480 / 3,77,011 | 42,930 / 96,303 |
| HFCs `rtp.hfc_pl.fund_income` / `financial_expenditure` | 1,02,451 | 61,796 |
| AIFIs `rtp.aifi_pl.interest_income` / `interest_expended` | 1,03,922 | 75,912 |

Rates (`rtp.scb_cost_return.*.scb`, 2025-12-29): cost of deposits 4.8%, cost of borrowings 8.1%, return on advances 9.4%, return on investments 6.7%.

**Steps:**
1. **Counterparty stocks:** FSF (`rbi_financial_accounts_fsf_balance_sheets`, vintage 2026-01-21), average of 2023-03-31 and 2024-03-31. ODC liabilities F22_F29 by counterparty: hh 1,28,56,060 → 1,42,75,072; nfc_pvt 28,38,412 → 33,20,100; nfc_pub 6,73,718 → 6,95,638; gg_sta 14,10,105 → 16,55,549; gg_cen 3,26,902 → 3,77,016; fc_ofc 6,75,029 → 7,94,767; row → rest_of_world. ODC assets F4 by counterparty: hh 90,69,426 → 1,09,30,155; nfc_pvt 33,71,433 → 39,42,990; nfc_pub 12,16,647 → 14,11,462; fc_ofc 15,66,339 → 19,05,084. Use the same series for OFC sub-sectors (`fc_ofc_nbfc_ndt`, `fc_ofc_hfc_ndt`, `fc_ofc_aifi`, `fc_ofc_icpf_*`). Remove intra-ODC and intra-OFC positions (inside one SAM account).
2. **HDFC merger:** the HDFC Ltd book (`rtp.scb_bs.loans_advances.scb.current` − `rtp.scb_bs.loans_advances_excl_merger.scb.current` at 2024-03-31 = 1,71,42,340 − 1,66,17,066 = 5,25,274, vintage 2024-12-26) sat with HFCs for 3 months and with banks for 9. Weight the average stocks accordingly for the counterparty shares. P&L totals are left as published, since each lender's P&L already covers its own months.
3. **Bank-interest matrix:** for each lender, interest expended by counterparty ∝ stock × rate (deposits at cost of deposits, borrowings at cost of borrowings). Interest income by counterparty ∝ loans × return on advances, plus non-government securities × return on investments. **Government-securities interest is taken from R3a, not here**, and subtracted from the lender's interest income before scaling. Then scale each lender's row to its P&L total. **RoW positions** (NRI deposits, ECB, foreign-currency loans) are excluded from the entries (they are `rest_of_world`'s R13/R14), but their memo value is removed from the P&L totals first (§4.3).
4. **FISIM (NAS 1.13 as the control):** total FISIM F = `s1_13.allocation_of_fisim_as_ic_to_user_industry.current` 6,27,885.47 + `s1_13.private_final_consumption_expenditure.current` 6,02,896.96 + `s1_13.rest_of_world_row.current` 29,793.73 = **12,60,576.16**.
   - (a) Split IC FISIM (10 user industries in 1.13) between NFC and household producers with each broad industry's corporate (7.1A+7.1B) vs household (7.1C) output shares. GG gets 0 (1.13 PADM = 0).
   - (b) Household FISIM = PFCE FISIM 6,02,896.96 (the official household control, shared with `households` C4b) + the household-producer IC share.
   - (c) Split each user sector's FISIM into loan and deposit parts ∝ (r_L − r*)·L_s and (r* − r_D)·D_s. The reference rate r* is an **assumption parameter** = SCB return on investments 6.7% (G-sec-dominated portfolio ≈ risk-free rate), recorded as an estimated record with its reason; sensitivity 6.5–7.2%.
   - (d) SNA interest: **R5 (FC ← s) = bank interest on loans to s − FISIM_L,s**; **R4 (s ← FC) = bank interest on deposits of s + FISIM_D,s**.
   - (e) RoW FISIM (29,793.73) is `rest_of_world`'s adjustment on its own interest cells (interface).
   - Inter-FC and GOV positions get no FISIM adjustment (NAS allocates none to financial or PADM users).
5. **Households** are written at group level: R5 entries `E_BANK|E_NBFC|E_INSP ← H_g` (key hh_keys `debt_institutional`; E_INSP ← H via policy loans, `mospi_nas_2026_s5_3` `loans_from_insurance_corporations` flow 8,190.90, stock `rbi_financial_accounts_hh_finsav_52ab` `t52b.fl_ofi_insurance.current` 1,18,156.70 → 1,26,347.60). Deposit interest to households is written in **R8a** (component `deposits_bank`, `deposits_nbfc`).
6. **GOV:** interest received by G_CEN/G_STA on their bank deposits = R4 (`G_* ← E_BANK`), no FISIM. Interest GOV pays to FCs on loans is in R3a, never R5.
7. **Inter-FC** (R4, FC rows, cols E_BANK/E_NBFC/E_RBI):
   - E_NBFC ← E_BANK (OFC deposits in banks);
   - E_BANK ← E_NBFC (bank loans to NBFCs, FSF ODC F4 to fc_ofc);
   - E_INSP ← E_BANK / E_NBFC (insurers' and PFs' bank deposits and FC bonds);
   - **RBI ↔ banks from RBI AR:** net LAF `sch13.a.net_interest_on_laf_operations.current` −7,052.08, SDF `sch13.a.interest_on_sdf.current` −5,616.80, MSF `sch13.a.interest_on_msf_operations.current` 3,413.37, loans and advances `sch13.a.interest_on_loans_and_advances.current` 2,094.09 **less the WMA interest already written under R3a** (Centre 394.38; States' part unidentified, logged). The four lines net to −7,161.42 before that deduction: RBI **paid** banks on balance. Write gross cells (E_BANK ← E_RBI for SDF and reverse repo; E_RBI ← E_BANK for repo and MSF) where the AR gives them; otherwise write the net in the direction of the net flow and note it. Anchored tol 0.05.
8. **Consistency test (the FISIM closure):** Σ over FC lenders of [SNA interest received (R5 + R3a + inter-FC + R13 memo) − SNA interest paid (R4 + R8a deposit components + R14 memo)] ≈ Σ lender NII − FISIM. Indicative NII: SCB 8,56,756 + RRB 28,104 + co-ops 44,855 + NBFI ≈ 3,67,001 ≈ 12.97 lakh cr, against FISIM 12.61 lakh cr, so FCs' net SNA interest is small. Band ±20% of NII (NBFC "fund-based income" includes non-interest items); failures are logged.

### 2.6 R8: dividends (corporate holders; households in R8a; government = R7; RoW = R14)

No dividend total is ingested: RBI corporate finances are DBIE-only (ISSUES P1-4), and the BoP has no dividend split (`external_sector_bop_bpm6_annual` gives only `bpm6.inr.bpm6_1_b_2.debit.current` 7,09,318). So:

1. **Issuer totals by "government-share grossing"** (one rule for every issuer the government holds). D_issuer = government dividends received from that issuer ÷ government's share of that issuer's equity in FSF (average of 2023-03-31 and 2024-03-31, `fsf.<issuer>.liabilities.outstanding.f51.{gg_cen,gg_sta,all}.current`):
   - NFC_pub (incl. public NBFCs, which the Finance Accounts do not separate): `union_fiscal_fa_receipts` `fa8.0050.00.101` 63,827.41 + `fa8.0050.00.200` 1,078.79 + States' dividends `state_fiscal_rbi_sf_appendices` `app1.total_revenue.ii.c.2-dividends_and_profits.in.all_states_uts.actuals` 6,914.54 ÷ gg share of nfc_pub F51 (gg_cen 2,46,947.92 → 2,89,233.46 of 3,50,670.51 → 4,15,912.93).
   - ODC: `fa8.0050.00.108` 13,806.57 (nationalised banks) + `fa8.0050.00.109` 488.99 (IDBI) ÷ gg share of fc_odc F51 (gg_cen 79,707.69 → 80,700.52 of 3,36,681.29 → 3,59,606.52).
   - E_INSP: **not grossed**. IRDAI appropriations give insurers' dividends directly: life `t25.appr_interim_dividends.insurers_life.current` 2,834.44 + `t25.appr_proposed_final_dividend.insurers_life.current` 3,142.89; non-life `t51.appr_interim_dividends.*` + `t51.appr_proposed_final_dividend.*` 1,761.56. Cross-check: LIC paid 4,427.50 and the Centre booked 4,272.54 (`fa8.0050.00.107`), i.e. 96.5%.
   - **NFC_pvt and private NBFCs: no anchor.** Prior = (NFC_pub dividends ÷ NFC_pub GOS) × NFC_pvt GOS (GOS from `factors` F4 entries). Very low confidence, recorded as an assumption parameter. **Owner access request:** RBI "Finances of Non-Government Non-Financial Public Limited Companies 2023-24" (dividends paid), DBIE. Balancing will size this through NAS private-NFC saving 24,10,408.53 (`s1_9.private_non_financial_corporations.current`).
2. **Holder split** of each issuer's dividends by FSF F51 holder shares (e.g. nfc_pvt end-March 2024: hh 6,98,943.52; row 8,47,496.39; fc_ofc 8,16,378; nfc_pvt 8,20,244; nfc_pub 2,07,950; fc_odc 83,033).
   - The fc_ofc holding is split into MFs (look-through), E_INSP and E_NBFC with FSF `fc_ofc_mf`, `fc_ofc_icpf_*` and the other OFC sub-sector F51 assets.
   - The gg part is `government`'s R7; the row part is `rest_of_world`'s R14. fincorp writes neither. Their values go into the `dividend_matrix` satellite as memo.
3. **MF look-through:** dividends on MF-held equity go to unit holders by SEBI T72 AUM shares (`finsector_markets_sebi_mf` `t72.aum.{banks,corporates,hnis,retail,total}.current`, average of the two end-Marches: banks 0.89%, corporates 37.11%, HNIs 35.06%, retail 26.94%). Corporates → E_NFPR (default; low confidence); banks → E_BANK; HNIs + retail → households (R8a).
4. Inter-corporate dividends within one SAM account (nfc_pvt → nfc_pvt) are **kept**: the E_NFPR ← E_NFPR diagonal cell is a legitimate SAM flow. Confirm the framework allows diagonal institution cells (§4.3).

### 2.7 R8a: household property income by group

Components (each a separate entry per group H_R1…H_U5; key from `households` hh_keys):

| Component | Paid by (col) | Total from | Key |
|---|---|---|---|
| `small_savings` (savings deposits, certificates, PPF; D41) | G_CEN | R3b step E (≈2,14,947.87) | `small_savings` |
| `gsec_direct` (T107 'others' HH part, SGBs, GMS) | G_CEN, G_STA | §2.4 steps 1, 5 | `financial_assets` |
| `deposits_bank` (SNA: bank interest + FISIM_D) | E_BANK | §2.5 | `deposits` |
| `deposits_nbfc` | E_NBFC | §2.5 (household NBFC/HFC deposits `t52b.fa_deposits_nonbank_ofi.current` 2,28,562.20 → 1,27,257.30) | `deposits` |
| `dividends` (direct holdings) | E_NFPU, E_NFPR, E_BANK, E_NBFC, E_INSP | §2.6 | `equity` |
| `mf_lookthrough` | each issuer | §2.4 MF share + §2.6 step 3 + MF-held bonds/deposits | `mf` |
| `debentures` (corporate bonds held directly) | E_NFPR, E_NBFC | FSF hh holdings of F3 non-government × r_corp (assumption: SCB cost of borrowings 8.1%) | `financial_assets` |

**Scaling stocks** (`rbi_financial_accounts_hh_finsav_52ab`, RBI Bulletin T52(b), vintage 2026-09-25; 2023-03-31 → 2024-03-31): bank deposits 1,27,17,029.5 → 1,41,79,504.0; small savings excl. PPF 17,86,563.5 → 20,96,314.2; PPF 9,39,449.0 → 10,51,376.5; MF 24,45,222.9 → 36,28,236.4; equity 53,66,910.0 → 84,06,842.8. These are cross-checks on FSF household stocks, not SAM controls.

AIDIS 2019 gives only total financial assets and cash loans per household by AIDIS quintile (`labour_enterprise_surveys_aidis_2019_quintile` `i9.financial_assets_per_hh.*`, `i9.cash_loan_per_hh.*`), not by asset class (coverage note). Deposit, equity and MF keys therefore differ only through the R/U asset-share structure in `labour_enterprise_surveys_aidis_2019_press_note` (`pn.asset_share_deposits.*`). Low confidence; the site shows a band.

Benchmark (closure plan R2): old-base 2022-23 household D4 received 47,12,396 and paid 22,49,807 (`mospi_nas_2026_oldbase_soa_s5_0` `…allocation_of_primary_income.resources.d4.current` / `.uses.d4.current`). Report the bottom-up total against it; structure and sign only.

### 2.8 R9c: investment income attributed to policyholders and PF/pension members (D44)

| Component | Col | Method | Value (indicative) | Role / conf. |
|---|---|---|---:|---|
| `life` | E_INSP | Policyholders' account investment income: `finsector_markets_irdai_life` `t24.inv_interest_dividends_rent_gross.insurers_life.current` 3,73,478.12 + `t24.inv_amortisation.insurers_life.current` 4,449.10. Excludes profit on sale (1,30,673.91) and fair-value change (93,595.52), which are holding gains; excludes the shareholders' account (`t25.inv_interest_dividends_rent_gross` 8,491.18). ULIP fund income stays inside | 3,77,927.22 | free medium |
| `epf` | E_INSP | Interest credited ≈ average EPF investments (`finsector_markets_epfo_ar` `invest.epf.total.current` 13,04,264.41 → 15,29,368.04, vintage 2024-12) × declared rate `app5vii.epf_interest_rate` 8.25 | 1,16,887.34 | free medium |
| `eps` | E_INSP | Investment income of the EPS fund ≈ average EPS investments (`invest.eps.total.current` 7,70,604.05 → 8,76,163.50) × 8.25% (assumption; EPS is defined-benefit, so no rate is credited) | ≈67,929 | free low |
| `nps` | E_INSP | Pass-through of NPS asset income: the pension-fund G-sec/SDL/T-bill interest from R3a (T107 `pension_funds`) + corporate-bond interest (average `finsector_markets_pfrda_nps` `m6.aum_by_asset_class.corporate_bonds.current` 2,45,846.66 → 2,78,492.31 × r_corp) + dividends on equity (`…equity.current` 1,48,844.45 → 2,21,738.83, dividend yield taken from the R8 issuer totals ÷ FSF equity) | ≈ R3a pension part + … | free low |
| `exempted_pf` | E_INSP | FSF non-government PF F6 stock (`fsf.fc_ofc_icpf_pf.liabilities.outstanding.f6.all.current` 38,75,290.91 → 49,21,119.25) less EPF, EPS and NPS stocks, × 8.25% | residual | free low; log |
| `gpf_union` | G_CEN | `fa9.2049.03.104` (credited to GPF accounts) | 18,871.50 | anchored 0.02 |
| `gpf_states` | G_STA | `…ii.c.2.iii-interest_on_small_savings_state_provident_funds` (the line also covers "small savings etc."; treat it all as State PF interest, logged) | 54,183.14 | free medium |

- **Keys:** EPF/EPS/exempted PF → private formal regular wage earnings (`factors` F1a F_LREG group shares, excluding the public-sector part). NPS central/State sectors (`m4d.annual_contribution.{central_govt,state_govt}`) and GPF → public-sector earnings key (the same key `government` uses for R9a/R9b). NPS corporate/all-citizen → regular wages. APY/NPS-lite → population key of the bottom three quintiles (assumption, logged). Life → hh_keys `insurance_life`.
- **PPF interest is not here** (it is R8a `small_savings`). CMPF has no source (gap). PLI (`union_fiscal_fa_provident_funds` MH 8014) D44 is omitted (tiny, no interest line; logged).
- **Non-life premium supplements** (≈ `finsector_markets_irdai_summary` `sum_c.investment_income.current` 44,129.04 − shareholders' `t51.inv_interest_dividend_rent_gross.*` 6,285.14 = 37,843.90) are written in **R17** (component `premium_supplement`), because R9c's rows are households only and part of it belongs to NFC policyholders.
- NAS consistency: NAS 5.3 PF & pension 7,23,026.60 and insurance 6,49,086.43 (`s5_3.provident_and_pension_funds.current`, `s5_3.insurance_funds.current`) are financed partly by D44. The builder reports D44 as a share of these; the check only flags values above 100%.

### 2.9 R17: net non-life premiums and claims

Source `finsector_markets_irdai_nonlife` (vintage 2026-02-03), "insurers_general_direct" = public + private + specialised + stand-alone health; reinsurers (GIC Re) are not in these tables.

| Line | Net claims incurred `t44.claims_incurred_net.<line>.insurers_general_direct.current` | Net premium earned `t44.net_premium_earned.<line>…` |
|---|---:|---:|
| motor | 63,599.26 | 77,579.02 |
| health | 80,784.88 | 93,550.52 |
| fire | 7,178.15 | 9,163.99 |
| marine | 2,219.94 | 3,066.50 |
| others | 18,508.22 | 25,431.28 |
| **total** | **1,72,290.46** | **2,08,791.32** |

**Steps (SNA 2008 §17.33, expected-claims approach):**
1. D72 claims (component `claim`: H_*, E_NFPU, E_NFPR ← E_INSP) = net claims by line.
2. D71 net premiums (component `premium`: E_INSP ← H_*, E_NFPU, E_NFPR) = premiums earned + premium supplements − service charge. With actual claims taken as expected, **Σ D71 = Σ D72 = 1,72,290.46**, allocated by line in proportion to claims.
3. Premium supplements (D44 on non-life reserves, component `premium_supplement`: H_*, E_NFPU, E_NFPR ← E_INSP) = 37,843.90, allocated like premiums.
4. **Payer split by line (assumption parameters, low confidence):** motor and health by retail/commercial proxies; fire, marine and "others" mostly NFC, except crop insurance (inside "others", not separable in ingested data). Premiums and claims of a line use the **same** payer split, so the assumption moves income between sectors only through supplements and cross-line differences.
5. Household-group key: hh_keys `insurance_nonlife` (HCES premium items, as C4b).
6. Implied non-life service charge = NPE + supplements − claims = 2,08,791.32 + 37,843.90 − 1,72,290.46 = 74,344.76. This is **below** NAS 8.12 non-life GVA 91,487.48, so NAS measures non-life output on a different basis (gross of reinsurance, or including reinsurers). Log it; the service charge itself is `households`/`production`'s C4b/C_INSR, not written here.

### 2.10 K2: FC gross saving (official total)

`mospi_nas_2026_s1_9`: `s1_9.financial_corporations.current` **9,91,447.755011** = `s1_9.public_financial_corporations.current` 5,35,509.8992 (departmental 2,580.42; non-departmental 5,32,929.4792) + `s1_9.private_financial_corporations.current` 4,55,937.855811. Equal to `mospi_nas_2026_s1_14` `s1_14.fc_{public,private}.gross_savings.current`. Cross-check: HBS T11 (`rbi_financial_accounts_hbs_saving` `t11.gross_saving_fc_pub.base2022.current` 5,35,510; `t11.gross_saving_fc_pvt.base2022.current` 4,58,132; RECONCILIATION FIN-6). NAS 2026 is the control. K2 is written only as constraints (§3); the entries are K2a.

### 2.11 K2a: FC saving by sub-sector (prior only; balancing makes it the residual)

1. **E_RBI (public)** = GOS 370.62 + RBI SNA property income − interest paid − R6 cash surplus = 370.62 + (`sch13.a.sub_total` 85,428.09 + `sch14.a.amortisation…rupee` −2,394.71 + `sch13.b.sub_total` 1,03,177.64 + `sch14.b.amortisation…foreign` 2,235.86) − `is.exp_interest` 2.19 − `rbi_banking_corporate_rbi_surplus_timing` `r6.surplus_received_by_centre_cash.current` (2023-24) 87,416.22 = **1,01,399.09**. Excluded: FX and securities holding gains (`sch14.b.exchange_gain_loss_from_foreign_exchange_transactions` 83,615.86, etc.) and transfers to provisions (an appropriation, retained). On the accrual surplus (`xii_1.surplus_transferred.current` 2,10,873.99) RBI saving would be −22,058.68. See §5 C3.
2. **Other sub-sectors:** prior ∝ GOS within each ownership part. Public (excl. RBI): ratio = (5,35,509.90 − 1,01,399.09) / (4,34,232.62 − 370.62) = 1.00057. Private: 4,55,937.86 / 6,52,476.34 = 0.69878. This reproduces the public and private NAS totals exactly and uses no dividend or tax data the block lacks.
3. **Cross-check (gap-map method), where P&L exists:** insurers' retained profit + CFC (life PAT `t25.profit_after_tax.insurers_life.current` 47,407.28 − dividends 5,977.33; non-life PAT Σ `t51.profit_after_tax.*` − 1,761.56; + INSR CFC 8,585.88). Banks and NBFCs lack dividend data, so no cross-check.
4. All free, low confidence. Components `public`/`private`.

### 2.12 S9 satellite `s9_funded_schemes` (memo; not SAM cells)

Long table: `series_id`, `scheme`, `flow` (contributions / benefits / interest_credited / net_accretion), `sector` (payer or subscriber group), `value`, `unit`, `status`, `prov_id`.

| series_id (proposed) | Source (dataset: series) | Value | Status |
|---|---|---:|---|
| `s9.epf.contributions` | `finsector_markets_epfo_ar`: `app5i.epf_contribution.current` (v2024-12; the AR 2024-25 revision 2,33,489.80 includes past accumulations, so it is not used) | 2,26,198.57 | official |
| `s9.epf.payments` | `app5i.epf_payment.current` | 1,18,690.66 | official |
| `s9.eps.contributions` | `para54.eps_contribution_total.current` (employer 62,423.93 + Government 9,356.48) | 71,780.41 | official |
| `s9.eps.pensions` / `s9.eps.withdrawals` | `finsector_markets_epfo_eps_outgo`: `eps_outgo.pension_disbursed.current` / `eps_outgo.withdrawal_benefits.current` (App. 5(i) total 23,410.17; unexplained 371.23, finsector_markets-37) | 15,130.68 / 7,908.25 | official |
| `s9.edli.contributions` / `.payments` | `app5i.edli_contribution.current` / `app5i.edli_payment.current` | 3,358.10 / 2,051.84 | official |
| `s9.nps.contributions.<sector>` | `finsector_markets_pfrda_nps` `m4d.annual_contribution.{central_govt,state_govt,corporate,all_citizen,apy,nps_lite,tier2,tier2_tax_saver}.current` | 36,875.76 / 77,599.20 / 27,642.37 / 12,544.61 / 6,659.06 / 173.46 / 1,339.50 / 4.39 | derived |
| `s9.nps.contributions.state_govt.{employer,employee}` | `finsector_markets_pfrda_sg` `m7d.annual_contribution_{employer,employee}.state_govt.current` | 43,992.43 / 33,606.78 | derived |
| `s9.life.premiums` / `.benefits` | `finsector_markets_irdai_life` `t24.premium.insurers_life.current` / `t24.benefits_paid_net.insurers_life.current` (LIC 4,75,751.92 / 3,85,949.15) | 8,29,929.46 / 5,77,020.95 | official |
| `s9.gpf_union.additions` / `.discharges` | `union_fiscal_fa_provident_funds` `fa14.8009.total.additions` / `.discharges` (additions include interest credited) | 68,989.35 / 63,930.50 | official |
| `s9.gpf_states.receipts` / `.disbursements` | `state_fiscal_rbi_sf_appendices` `app3.total_capital_receipts.vi.1-state_provident_funds.in.all_states_uts.actuals` / `app4.total_capital_disbursements.vii.1-state_provident_funds.in.all_states_uts.actuals` (include "other savings deposits"; no State-wise split) | 1,03,892.37 / 91,398.49 | official (caveat) |
| `s9.ppf.net_accretion` | `union_fiscal_nssf` `nssf.ppf.additions` (net of withdrawals, incl. interest) | 1,11,927.46 | official |
| `s9.pli.additions` / `.discharges` | `fa14.8014.total.additions` / `.discharges` | 16,793.08 / 12,852.69 | official |
| `s9.cgegis.additions` / `.discharges` | `fa14.8011.total.additions` / `.discharges` | 466.67 / 549.24 | official |
| `s9.<scheme>.interest_credited` | from R9c components | per §2.8 | estimated |
| exempted PF trusts, CMPF, NPS withdrawals | not published (finsector_markets-6, -32) | absent (logged, not zero) | — |

---

## 3. Constraints to declare

The framework's `constraint()` filters only by rows, cols and refs (`pipeline/sam/framework.py`). Several fincorp totals sit on **components** of cells shared with other components, so **FR-fincorp-1** (§4.3) asks for an optional `components` filter. Rows marked † need it; without it they become `ctx.check()` control-total checks recorded in the block result, not balancing constraints.

| constraint_id | ref | rows | cols | refs | target (source series) | kind | tol |
|---|---|---|---|---|---|---|---|
| `fincorp.k2.fc_saving_total` | K2 | K_RBI, K_BANK, K_NBFC, K_INSP | E_RBI, E_BANK, E_NBFC, E_INSP | [K2a] | 9,91,447.755011 (`s1_9.financial_corporations.current`) | equal | tol_abs 1 |
| `fincorp.k2.public` † | K2 | same | same | [K2a] + components [public] | 5,35,509.8992 (`s1_9.public_financial_corporations.current`) | equal | tol_abs 1 |
| `fincorp.k2.private` † | K2 | same | same | [K2a] + [private] | 4,55,937.855811 (`s1_9.private_financial_corporations.current`) | equal | tol_abs 1 |
| `fincorp.f4a.fc_gos_total` | F4a | E_RBI, E_BANK, E_NBFC, E_INSP | F_GOSC | [F4a] | 10,86,708.958617 = `s7_1a.financial.os`+`.cfc`+`s7_1b.financial.os`+`.cfc`. **Must be byte-identical to `factors`' FC GOS constraint (same series, same arithmetic, same tol), or the framework reports a conflict** | equal | tol_abs 1 |
| `fincorp.f4a.fins_gos` | F4a | E_RBI, E_BANK, E_NBFC | F_GOSC | [F4a] | 9,68,693.089687 (`io_tables_sut_va` i55 `os_mi` + `cfc`) | equal | tol_abs 1 (E_INSP then = 1,18,015.87 vs SUT 1,18,016.09: within tol) |
| `fincorp.f4a.public` † | F4a | same four | F_GOSC | [F4a] + [public] | 4,34,232.619481 | equal | tol_abs 1 |
| `fincorp.f4a.private` † | F4a | same four | F_GOSC | [F4a] + [private] | 6,52,476.339136 | equal | tol_abs 1 |
| `fincorp.r3.union_nas_concept` | R3b | all accounts that can receive government interest: E_*, H_*, E_NFPU, E_NFPR, G_STA, R_ROW | G_CEN | [R3, R3a, R8a, R9c, R14] | 10,86,513.09 (bridge §2.3; cash `fa9.2049.total` minus stated items plus the NSSF estimate) | band | tol_rel 0.03 (E is ~20% of the total and ±10% uncertain) |
| `fincorp.r3.union_cash_part` † | R3 | same | G_CEN | same refs, components excluding `small_savings` | 8,71,565.22 (= A − B − C − D; all official lines) | band | tol_rel 0.005 |
| `fincorp.r3.states` | R3b | E_*, H_*, E_NFPU, E_NFPR, G_CEN, R_ROW | G_STA | [R3, R3a, R8a, R9c, R14] | 4,95,569.04 (`…ii.c.2-interest_payments` minus `…ii.c.2.iv-others`) | band | tol_rel 0.01 |
| `fincorp.r3a.rbi_gsec_income` | R3a | E_RBI | G_CEN, G_STA | [R3a] | 90,589.18 (90,194.80 AR securities income, accrual + Centre WMA 394.38 `fa9.2049.01.115`) | equal | tol_rel 0.02 (or simply make the entries anchored; then drop this constraint) |
| `fincorp.r9c.gpf_union` | R9c | H_R1..H_U5 | G_CEN | [R9c] | 18,871.4957 (`fa9.2049.03.104`) | equal | tol_rel 0.02 |
| `fincorp.r9c.life` † | R9c | H_* | E_INSP | [R9c] + [life] | 3,77,927.22 (IRDAI t24 lines) | band | tol_rel 0.05 |
| `fincorp.r17.claims` † | R17 | H_*, E_NFPU, E_NFPR | E_INSP | [R17] + [claim] | 1,72,290.46 (`t44.claims_incurred_net.total.insurers_general_direct.current`) | equal | tol_rel 0.01 |
| `fincorp.r17.premiums` | R17 | E_INSP | H_*, E_NFPU, E_NFPR | [R17] | 1,72,290.46 (D71 = D72) | band | tol_rel 0.05 |

**Not declared on purpose:**
- the FISIM total, because it is not a sum of SAM cells: it becomes a block test on the `interest_fisim_bridge` satellite (§7 T6);
- any household-total property-income constraint, because no official total exists;
- dividends totals, which are not official.

---

## 4. Interfaces

### 4.1 Needs

| From | What | Why |
|---|---|---|
| `production` | V2 entries F_GOSC ← A_FINS, A_INSR (or read the same SUT series) | F4a must equal the SUT operating surplus the factor account receives |
| `factors` | Its FC GOS constraint (`target`, `tol`) and F4 entries for E_NFPU/E_NFPR (GOS). F1a entries H_* ← F_LREG, with a public-sector sub-key | Identical F4a total; NFC_pvt dividend prior (§2.6); D44 keys for EPF/NPS/GPF (§2.8) |
| `households` | `hh_keys` satellite with at least: `deposits`, `debt_institutional`, `financial_assets`, `equity`, `mf`, `small_savings`, `insurance_life`, `insurance_nonlife`, `population`; plus C4b entries (household FISIM by group) | R8a, R5 (household side), R9c, R17 keys. The deposit/loan FISIM by group must match C4b's split |
| framework | `components` filter in constraints (FR-fincorp-1); confirmation that diagonal institution cells (E_NFPR ← E_NFPR, E_BANK ← E_BANK) are allowed or must be dropped (FR-fincorp-3) | §3; §2.6 step 4 |

### 4.2 Publishes

| To | What |
|---|---|
| all (SAM) | Entries for F4a, R3, R3a, R4, R5, R8, R8a, R9c, R17, K2a; constraints §3 |
| `closure` | Every household-touching entry **at group level** (R8a, R9c, R17, R5), as the closure plan requires; a statement in provenance that **interest is SNA interest** (deposits: actual + FISIM; loans: actual − FISIM), consistent with PFCE FISIM 6,02,896.96 |
| `capital_financial` | K2a entries (FC saving by sub-sector, public/private components); the HDFC-merger weights used for interest (to stay consistent with K8a) |
| `government` | Nothing to compute. **Warning:** `government` must not write any government-interest entry. All D41 paid by G_CEN/G_STA is fincorp's (R3/R3a/R8a/R9c), except ROW ← G, which is `rest_of_world`'s R14 (§5 C5) |
| `rest_of_world` | `gov_interest_bridge` memo rows for ROW ← G_CEN (external debt `fa9.2049.02.total` 29,616.74; FPI share of market loans ≈13,439; SDL/T-bill FPI parts) so R14 uses the same numbers; the `dividend_matrix` RoW column memo |
| satellites | `s9_funded_schemes` (S9); `fc_public_private` (F4a/K2a parts + inputs); `gov_interest_bridge` (R3 → R3b → holder, incl. intra-G and RoW memo); `interest_fisim_bridge` (lender × counterparty: bank interest, FISIM_L/D, SNA interest, stocks, rates); `dividend_matrix` (issuer × holder incl. GOV and ROW memo); `d44_by_scheme`; `mf_lookthrough` (holder shares and income by issuer) |

### 4.3 Framework requests (to `docs/phase2/FRAMEWORK_REQUESTS.md`)

- **FR-fincorp-1:** an optional `components` filter on constraints (list of component slugs). Without it, the public/private totals (K2, F4a), the cash-vs-estimated split of Union interest, and life-D44/claims totals cannot be balancing constraints.
- **FR-fincorp-2:** allow `fincorp` DEPENDS += [`government`, `rest_of_world`]. This is acyclic: neither depends on fincorp; `capital_financial` and `closure` come after. It lets fincorp read:
  - R7 (government dividend receipts), for R8 grossing, instead of re-reading `fa8.0050.*`;
  - R6;
  - R13/R14 (RoW interest and dividends by domestic payer and recipient), to remove the RoW share from lender P&L totals, and to know which ROW ← G entries exist so the payer constraints are complete.

  Fallback if refused: fincorp reads the same clean series itself, and a cross-block test after all blocks build asserts equality within 5%.
- **FR-fincorp-3:** confirm whether same-account diagonal cells (inter-NFC dividends, E_BANK ↔ E_BANK) are allowed by `structure.yaml`. If not, fincorp consolidates them away and logs the amount.

---

## 5. Conflicts and choices

| # | Issue | Values | Recommendation (control vs cross-check) |
|---|---|---|---|
| C1 | Co-operative banks public or private? Gap map F4a says State co-operative banks are public | NAS 1.9 memo `s1_9.savings_of_co_operatives_banks_and_societies.current` 32,958.04 sits under the corporate totals as co-operatives, not public | **Private** (NAS convention: co-operatives are in the private corporate sector). RRBs public. Log the deviation from the gap map |
| C2 | FC sub-sector split: gap map (shares of operating profit from STRBI) vs NAS 8.12 official GVA | STRBI not available (DBIE only) | **NAS 8.12 GVA is the control**; CE split from RBI AR and RTP wage bills; RTP operating profits as cross-check (bank GVA proxy 9,55,261 vs 8.12 8,95,216) |
| C3 | RBI surplus cash vs accrual | cash 87,416.22 (`r6…cash`) vs accrued 2,10,873.99 (`xii_1.surplus_transferred`) | **Cash** (D0-7). Supported by data: RBI SNA saving on cash = 1,01,399.09, while NAS public-FC saving − public-FC GOS = 1,01,277.28 (diff 121.81). Accrual gives −22,058.68. The accrued surplus also exceeds RBI's SNA income (1,88,815 before the surplus) by ~22,059: a super-dividend under accrual, none under cash |
| C4 | Union interest cash vs net of re-issue receipts | cash 11,01,867.87; re-issue accrued interest 26,465.89 + premium 12,312.11 | **Net** (Receipt Budget nets them; SNA accrual). Cross-check: cash. The difference (38,778) is logged in the bridge |
| C5 | Gap map overlap: ROW ← G interest is in both R3a (fincorp) and R14 (`rest_of_world`); ROW ← NFC/FC dividends in both R8 and R14 | external debt interest 29,616.74; FPI G-sec interest ≈13,439 | **`rest_of_world` writes all ROW rows (R14)**, because the ROW row must hit the BoP investment-income debit (NAS 6.1 item 8 = 7,24,612 via `external_sector_bop_overall_annual` `bop_old.inr.ca.income.investment.debit.current`). fincorp publishes the memo numbers and includes ref R14 in its payer constraints. Orchestrator to confirm |
| C6 | States' interest: RBI SF (all States & UTs) vs FC16 KFI (28 States) | 5,07,175.37 vs 4,94,910.97 | **RBI SF control** (SAM G_STA includes UTs with legislature); KFI cross-check via the GOV-5 bridge (residual 1,522, 0.3%) |
| C7 | Interest on Central loans: States paid vs Union received | 15,072.31 vs 13,641.26 (GOV-7 UNEXPLAINED) | **Payer (States) control** (R3 is by payer); the 1,431 gap stays in G_CEN's account for balancing and is logged |
| C8 | G-sec holder shares: DEA/T107 vs FSF counterparty | FSF gg_cen F3 held by RoW 7,64,260 at end-March 2024 vs T107 FPI 2.34% of 1,07,40,389 central dated securities ≈2.5 lakh cr | **T107 (instrument-specific, debt manager's data) is the control** for dated securities; FSF splits T107 'others' and 'corporates' only. Log the RoW discrepancy (FSF probably includes foreign central banks and other items) |
| C9 | RBI G-sec income: RBI AR vs T107 share × coupon | 90,194.80 (AR, accrual) vs 96,504 | **RBI AR control**; other holders scaled |
| C10 | RTP vintages | e.g. NBFC-ML fund-based income 3,68,892 (v2024-12-26) vs 3,77,011 (v2025-12-29) | **Latest (2025-12-29)** where present; name the vintage in every `ctx.value` call |
| C11 | EPFO EPF contributions | AR 2023-24: 2,26,198.57 vs AR 2024-25: 2,33,489.80 | **AR 2023-24** (the revision includes past accumulations; coverage note) |
| C12 | FC saving: NAS 2026 vs HBS T11 | private 4,55,937.86 vs 4,58,132 | **NAS 2026 control** (FIN-6, vintage) |
| C13 | PPF in small savings? (gap-map K7a note) | NAS 5.3 small savings 3,09,750.90 = NSSF savings deposits 2,52,892.84 + certificates 56,858.06 exactly | **Settled:** PPF (1,11,927.46) is only in NAS "PF & pension". For income, PPF interest is D41 in R8a `small_savings`, never in R9c |
| C14 | Treatment of `fa9.2049.03.108` 18,841.04 "insurance and pension funds" | D44 paid by G, or interest to EPFO's EPS Public-Account deposit | **R3a E_INSP** (inference: 8.3% on the 2,26,530.85 EPS deposit). The EPFO then pays D44 via R9c `eps`. Never both |

---

## 6. Risks, gaps, open questions

**Double counting: rules the builder must encode (and test, §7):**
1. PPF interest only in R8a `small_savings`; GPF interest only in R9c; never in R3a (closure plan R12).
2. Centre → NSSF interest (1,85,361.91) is intra-G_CEN and never written. Only NSSF → households (R8a) and States → NSSF (R3) are written.
3. All interest paid by G_CEN/G_STA to FCs is R3a, never R5 (R5 is household and NFC borrowers only).
4. Household parts of R3a/R4/R8 appear only as R8a group entries. No "HH total" entries.
5. ROW ← G interest and ROW ← NFC/FC dividends only in R14 (`rest_of_world`). GOV ← NFC/FC dividends only in R7 (`government`). RBI surplus only in R6.
6. Life premiums and claims, and PF/NPS contributions and withdrawals, are never current transfers (they sit in S9 and in K7a I_INPE). Only D44 (R9c) and non-life (R17) are current.
7. The non-life premium supplement is written once (R17 `premium_supplement`), not also in R9c.
8. MF-held securities' income goes only through `mf_lookthrough`. It is not also attributed to E_NBFC or K_MUTF, nor to the DEA "mutual_funds" holder as a final recipient.
9. Deposit-taking NBFCs/HFCs are in FSF ODC (E_BANK boundary) but their P&L is in the RTP NBFC/HFC tables. Allocate them to one account (recommend E_BANK via FSF `fc_odc_nbfc_dt` and `fc_odc_hfc_dt` stocks) and remove them from the E_NBFC P&L totals.
10. HDFC merger: use month-weighted stocks, not end-March 2024 bank stocks, for the whole year.
11. FISIM: household FISIM in PFCE (C4b, 6,02,896.96) and the FISIM adjustment in R4/R5/R8a must use the same household total and group keys, or household income is double-counted or missed by up to ~6 lakh cr.
12. Management-of-debt fee (2,921.79) is not interest. Tell `government` it belongs in purchases (GFCE/IC), not in D41.

**Places where the gap-map method cannot be followed as written, with the fallback:**
- **F4a:** STRBI/NABARD bank-wise data not available → NAS 8.12 GVA + RTP wage bills (better anchored than planned). PACS and ARDBs are not ingested, so their CE falls into the E_NBFC residual. Logged.
- **R3a:** SDL ownership comes from HBS T107 (ingested), not a manual download. The DEA "others" category is split with FSF counterparty shares (ISSUES: "cannot be assigned without an estimate").
- **R4/R5:** STRBI rates by counterparty and BSR-1 borrower detail not available → RTP group P&L and cost/return rates + FSF stocks. BSR-1 only gives household shares of SCB credit (`rbi_banking_corporate_bsr1_mar2024` `bsr1.share_credit_individuals.scb` 47.4%, `bsr1.share_credit_other_households.scb` 10.4%) as a cross-check on FSF household loans. The reference rate is an assumption parameter.
- **R8:** RBI corporate finances not available → government-share grossing plus a GOS-ratio prior for private NFCs (very low confidence). **Owner access request** (DBIE corporate finance tables).
- **R8a:** AIDIS by asset class by quintile not available (only total financial assets by AIDIS quintile), and no microdata (D1-2) → coarse keys, wide band.
- **R9c:** the gap map names `rbi_annual_report` as primary, but the RBI AR has no policyholder or PF investment income (rbi_banking_corporate coverage note). Use IRDAI/EPFO/PFRDA/Finance Accounts instead. EPFO interest credited is not published in rupees, so it is corpus × declared rate. EPS, NPS and exempted-trust income are estimated.
- **R17:** no retail/group or crop split within lines → payer split is an assumption. Government-sponsored health and crop schemes, where the government pays the premium, are attributed to the beneficiary sector (households). Government's funding of them is `government`'s concern (R10/production subsidies). Logged.
- **K2a:** retained earnings need dividends and taxes by sub-sector, which are not available → GOS-proportional prior within ownership parts.
- **S9:** exempted PF trusts, CMPF and NPS withdrawals not published.

**Open questions (for the orchestrator or NAD):**
- Q1. ROW ← G and ROW ← corporate dividends: confirm `rest_of_world` owns them (C5).
- Q2. Does NAS 8.12 S122 include deposit-taking NBFCs (FSF includes them in ODCs)? This affects the E_BANK/E_NBFC boundary only.
- Q3. Is PLI (MH 8014) inside G_CEN in NAS 2026, or an insurer? Default G_CEN; D44 omitted (tiny).
- Q4. Composition of States' interest "others" (11,606.33), treated as intra-G_STA.
- Q5. NAS non-life output basis (74,345 implied from IRDAI vs GVA 91,487): reinsurers or gross premiums?

**Risks to balancing:**
- **E_INSP saving may not come out "small".** GOS 1,18,016 (NAS) is well above insurers' book PBT (life 47,631 + non-life ~14,109). If D44 is set to the full policyholder income, E_INSP saving ≈ GOS + shareholders' income − taxes − dividends ≈ 1.1–1.2 lakh cr, against "CFC + retained profit" ≈ 58,000. Expect balancing to move D44 (life) or K2a. The size is reported, not forced.
- **Household aggregate gap** (closure plan R2). Bottom-up property income may leave households short of their required net +36,30,974.76. D44 (~6–7 lakh cr) and the FISIM-adjusted deposit interest are the two biggest levers fincorp controls. Report them against the old-base D4 (received 47,12,396; paid 22,49,807).
- **FSF vintage:** FSF is old-base (P0-3). Stocks are used only as allocation keys, never as levels.
- **Assumption parameters**, each recorded as an estimated record with its reason and a sensitivity range in `docs/phase2/issues/fincorp.md`:
  - r* 6.7%;
  - r_corp 8.1%;
  - EPS yield 8.25%;
  - exempted-PF rate 8.25%;
  - NFC_pvt dividend ratio;
  - R17 payer splits;
  - MF "corporates" → E_NFPR.

---

## 7. Tests the builder should write (`tests/sam/test_fincorp.py`; every target read from clean data, never typed)

| # | Test | Target (read via ctx.value / polars) | Tolerance |
|---|---|---|---|
| T1 | Σ F4a entries = FC GOS; and = `factors`' constraint target | `s7_1a.financial.os`+`.cfc`+`s7_1b…` | ₹1 cr |
| T2 | E_RBI F4a = `s8_12.central_bank_s_121` − `is.exp_employee_cost` and = `is.exp_depreciation` | RBI AR, NAS 8.12 | ₹0.01 cr |
| T3 | E_INSP F4a = SUT i56 `os_mi` + `cfc`; E_RBI+E_BANK+E_NBFC = SUT i55 `os_mi` + `cfc` | `io_tables_sut_va` | ₹1 cr |
| T4 | Public F4a components sum to 4,34,232.62 and private to 6,52,476.34 (prior) | 7.1A/7.1B | ₹1 cr |
| T5 | Σ K2a = `s1_9.financial_corporations`; public/private components = `s1_9.public_…` / `private_…` (prior) | NAS 1.9 | ₹1 cr |
| T6 | FISIM bridge: Σ FISIM removed or added across R4/R5/R8a (+ RoW memo) = `s1_13` IC + PFCE + RoW; household part = PFCE FISIM + household-producer IC share, and equals the C4b total used by `households` | NAS 1.13 | ₹1 cr |
| T7 | Union bridge: satellite lines reproduce `fa9.2049.total` from its components; the total written to G_CEN's column across [R3, R3a, R8a, R9c] + R14 memo = the bridge target | FA 2049 lines | ₹1 cr (pre-balancing) |
| T8 | States: sum of lines = `app2…ii.c.2-interest_payments`; KFI bridge reproduces GOV-5 | RBI SF, FC16 KFI | 0.5% |
| T9 | Each instrument's holder allocation sums to its payer line (market loans 7,26,415.54 net of re-issue share; SDL 3,69,267.41; T-bills 60,237.27) | FA / RBI SF | ₹1 cr |
| T10 | E_RBI ← G interest = `sch13.a.interest_on_holding_of_rupee_securities` + `sch14.a.amortisation…rupee` + WMA `fa9.2049.01.115`; and RBI ↔ bank entries + WMA = the four `sch13.a` LAF/SDF/MSF/loans lines (no WMA counted twice) | RBI AR, FA | ₹1 cr |
| T11 | R9c `gpf_union` = `fa9.2049.03.104`; `life` = t24 interest/dividends/rent + amortisation | FA, IRDAI | ₹1 cr |
| T12 | R17: Σ `claim` = `t44.claims_incurred_net.total.insurers_general_direct`; Σ `premium` = Σ `claim`; Σ `premium_supplement` = `sum_c.investment_income` − Σ `t51.inv_interest_dividend_rent_gross.*` | IRDAI | ₹1 cr |
| T13 | S9 rows equal their source series exactly (census of the satellite) | EPFO, PFRDA, IRDAI, FA St 14, RBI SF, NSSF | ₹0.01 cr |
| T14 | No-double-count guards:<br>• no fincorp entry with row R_ROW;<br>• no fincorp entry G_* ← E_NFP*/E_* under R8 (dividends to government are R7);<br>• no R3a entry with row H_*;<br>• no R5 entry with col G_*;<br>• no R9c entry with component `ppf`;<br>• no G_CEN ← G_CEN entry;<br>• no life-premium or PF-contribution entry in any current-account cell | structural | exact |
| T15 | Every household-touching fincorp entry is at group level (H_R1…H_U5); for each R8a component, the 10 group shares sum to 1 and match the named hh_keys key | hh_keys | 1e-9 |
| T16 | Provenance: every entry has a prov_id; every `estimated` record has a method; each assumption parameter (r*, r_corp, EPS yield, exempted-PF rate, NFC_pvt dividend ratio, R17 splits, MF corporates) exists as its own record | framework | exact |
| T17 | Diagnostics, reported not asserted:<br>• E_INSP implied saving vs retained profit + CFC;<br>• FC net SNA interest vs Σ NII − FISIM (band ±20%);<br>• household property income vs old-base D4 (structure only);<br>• RBI saving (cash) vs NAS public-FC saving − GOS (expect ≈ ₹122 cr difference) | clean data | report |
| T18 | Vintage pinning: every `ctx.value` on a multi-vintage dataset (RTP, RBI AR, EPFO, NSSF, DEA) names its vintage, and the test re-reads with that vintage | — | exact |

---

## 8 Cross-plan review (2026-09-30, cross-plan critic; details and ids in `CROSS_REVIEW.md`)

What this block must change or confirm:

1. **XR-18 DAG:** DEPENDS += government, rest_of_world (acyclic; recommended for approval). Then read the following instead of recomputing them:
   - R6 and R7 (government);
   - R13/R14 and `row_property_income` (rest_of_world).
2. **XR-4 RBI foreign income.** Your K2a E_RBI prior (1,01,399.09) uses the RBI AR foreign income (1,05,413.50). rest_of_world's R13 writes BoP 1,31,059 on E_RBI, so E_RBI would be ≈ ₹25.6k out and `fincorp.k2.public` (tol 1) would force the difference onto other public FCs. Recommended (decision D-4):
   - rest_of_world splits E_RBI's R13 into `reserve_asset_income` = AR 1,05,413.50 (anchored) and `reserve_income_unexplained` 25,645.50 (free, low);
   - you compute the K2a E_RBI prior from the SAM entries you read.

   The C3 test (≈ ₹122 cr against NAS public FC saving − GOS) stays as your evidence for D0-7 cash.
3. **XR-5 household FISIM.** Use households' C4b entries `fisim_deposits` / `fisim_loans` **by group** as FISIM_D / FISIM_L for households. households will compute them with your reference-rate formula and parameters (r* 6.7%, 4.8%, 9.4%, same T52(b) stocks), recorded once in `hh_keys` `fisim_params`. Apply your rate method to non-household sectors only. Test: per group, the R8a deposit adjustment = C4b `fisim_deposits` and the R5 adjustment = C4b `fisim_loans`.
4. **XR-6 E_BANK boundary:** E_BANK ≡ K_BANK ≡ FSF ODC (SCBs, co-op banks, deposit-taking NBFCs and deposit-taking HFCs, incl. HDFC Ltd all year).
   - Move the deposit-taking NBFC/HFC share of the RTP NBFC/HFC P&L and wage bills to E_BANK (FSF `fc_odc_nbfc_dt`, `fc_odc_hfc_dt` stock shares), in F4a, R4, R5, K2a and `fc_public_private`.
   - **Drop the HDFC month-weighting**: the merger is internal to E_BANK, as capital_financial also assumes. §6 item 9 of this plan already points this way.
5. **XR-12 FPI interest on G-secs:** rest_of_world will write it with your formula (T107 average FPI share × payer line, net of the pro-rata re-issue receipts). Read its R14 G_* entries and allocate only the remainder to domestic holders. The payer constraints already include R14.
6. **XR-13 RoW FISIM (29,793.73):** rest_of_world follows NAS 6.1 (R13/R14 = BoP, no FISIM adjustment). Treat RoW FISIM as exported output with no SAM interest counterpart in `interest_fisim_bridge`. Test T6 then checks the domestic FISIM, 12,30,782.43 (IC 6,27,885.47 + PFCE 6,02,896.96); log the RoW part.
7. **XR-10 key names:**
   - use households' `aidis_fin_assets`, `aidis_inst_loans`, `aidis_deposits`, `aidis_equity`, `aidis_mf` and `aidis_small_savings` (to be published);
   - `pop_persons`;
   - life: `aidis_fin_assets`; non-life premiums: `c4b_insurance_service` shares. There is no HCES premium item, so "insurance_nonlife (HCES premium items)" cannot be built.
8. **Keys for R9c:** read factors' `public_sector_wage_key` (new) for NPS central/State and GPF; use F_LREG shares less that key for EPF/EPS.
9. **XR-29:** interest between NFCs has no ref; log it in your issues file (small) or propose extending R8.
10. **Confirmed consistent:**
    - PPF interest only in R8a; GPF only in R9c; MH 2049.03.108 → R3a E_INSP → R9c `eps`;
    - no R_ROW entries; no G_* ← E_* dividends (R7 is government's);
    - co-op banks private (decision D-11);
    - `fincorp.f4a.fc_gos_total` must equal `factors.f4.fc_gos` (same series, tol 1).

    The † constraints are now expressible (components filter, FRAMEWORK_REQUESTS P-1): declare them.
