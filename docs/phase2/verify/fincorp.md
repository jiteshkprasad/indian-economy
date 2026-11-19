# Verification: the `fincorp` block (SPEC s.3 rule 3)

Verifier: an independent agent (not the fincorp builder or its integrator), 2026-10-01.

Scope: the fincorp block only. Its refs are F4a, R3, R3a, R3b, R4, R5, R8, R8a, R9c, R17, K2 and K2a, plus the S9 satellite and the six bridge satellites.

Method in brief:
- I recomputed every entry, every constraint target and every check target from the clean Parquet with DuckDB SQL and plain Python.
- Where the plan says the block may read another block, I read that block's published outputs:
  - households: `hh_keys` and the C4b FISIM entries;
  - factors: F1a and F4 entries, and `public_sector_wage_key`;
  - government: R6 and R7;
  - rest_of_world: R13 and R14.
- I did not import or call the builder's code. I read three short passages of it only after a difference appeared, to locate its cause:
  - `f4a.py`, the profit proxy (V-FIN-8);
  - `interest.py`, the GG-IC industry list (V-FIN-1);
  - `interest.py`, the one-line comment on government-held bank debt (V-FIN-4).

Regression test: `tests/verify/test_sam_fincorp_spotcheck.py`. It does not import `pipeline.sam` or polars. Result: 10 passed, 4 strict xfails (V-FIN-1 to V-FIN-4) and 1 skip (the staleness guard, V-FIN-5).

Full offline suite, run once at the end: 4,007 passed, 8 failed, 51 skipped, 29 xfailed. None of the 8 failures is in my file. Two are fincorp's, and both are V-FIN-5 (the staleness after the government rebuild):
- `test_sam_fincorp::test_built_outputs_equal_a_fresh_build`;
- `test_sam_audit::test_every_sam_provenance_input_resolves` (three fincorp inputs, two capital_financial ones).

The other six belong to other blocks or the framework:
- capital_financial: its fresh-build test and K-account closure (it is stale too);
- timeseries: its fresh-build test and the timeseries spot-check;
- hygiene: `group_by` in `households/__init__.py:96`;
- the known framework test `test_a_broken_sibling_module_does_not_stop_another_blocks_build`.

Outputs checked: the build of 2026-09-30 23:58 (`fincorp_entries.parquet`), built against production, households, factors, government and rest_of_world. At 00:15 another agent rebuilt government. Its R6/R7 values did not change, but its record ids did, so fincorp is now stale against government (V-FIN-5). Every value fincorp reads from government was re-read by the census after the rebuild, so the census below applies to the current files.

## Verdict

**Sound, with minor fixes.** Every number the block writes matches my recomputation:

- **Entries: a census of all 455**, not a sample. 121 of them are ≥ ₹10,000 crore. The largest difference is 5e-7 crore, the 6-decimal rounding on write.
  - One condition applies: to get that match I reproduce the block's list of government industries in the FISIM user key. With the list the plan implies, 37 interest entries move, by up to ₹658 crore each (V-FIN-1).
- **Constraints: all 14.** Targets, selections, refs and components filters, kinds and tolerances all match.
  - All 14 hold on the prior assembled from the eight built blocks.
  - `f4a.fc_gos_total` is identical to factors' `f4.fc_gos`, so it is a duplicate, not a conflict.
- **Checks: the targets of all 14.**
  - The one failing check, `k2a.rbi_prior_vs_nas` (−7,119.90), is exactly rest_of_world's R14 `reserve_asset_debit` (7,118) plus the other R14 items on E_RBI, as fincorp-1 says.
  - The D0-7 evidence check, `k2a.rbi_cash_basis_evidence`, gives a difference of −1.90. It holds.
- **Satellites:**
  - every row of `s9_funded_schemes` (35), `gov_interest_bridge` (97), `d44_by_scheme` (16), `dividend_matrix` (62) and `mf_lookthrough` (5);
  - the inputs and GOS rows of `fc_public_private`;
  - every position, P&L total, adjustment, target, scale and FISIM row of `interest_fisim_bridge` (127).

The findings are method and labelling issues of minor size, plus one process item that needs a rebuild:

- **V-FIN-1:** the GG IC in utilities is not removed from the FISIM user key (₹1,227 crore of IC FISIM moves between sectors).
- **V-FIN-2:** the Union GPF group entries are labelled derived/anchored, although they rest on an estimated key.
- **V-FIN-3:** banks' dividends are grossed with the wrong government share, understating them by ₹7,489 crore.
- **V-FIN-4:** interest on government-held bank and NBFC debt is written by no block, although fincorp-20 says government writes it.
- **V-FIN-5:** fincorp is stale against government, and three provenance inputs no longer resolve (`test_sam_audit` fails).
- **V-FIN-6 to V-FIN-8:** smaller logging and memo points.

None of them changes the block's large totals. Those totals are pinned by constraints: FC GOS, FC saving, union and State interest, life D44, and non-life claims.

## 1. Method (what I recomputed, and how)

Each value is the latest vintage of that (series, period), unless a vintage is named. Stocks are averaged over 2023-03-31 and 2024-03-31. The pinned vintages are:
- RBI AR: 2024-05-30;
- RTP: 2025-12-29;
- EPFO AR: 2024-12.

Amounts are Rs crore, FY 2023-24.

1. **F4a (7 entries).**
   - E_RBI = NAS 8.12 S121 GVA − RBI employee cost = 370.62, which equals RBI depreciation.
   - E_BANK + E_NBFC = SUT i55 OS/MI + CFC − E_RBI. It is split in proportion to GVA − CE − NPT, where:
     - GVA is 8.12 S122 and S124–S127, scaled to SUT i55 GVA less S121;
     - bank CE = the RTP wage bills (SCB, RRB, UCB, StCB, DCCB), plus the deposit-taking NBFC/HFC share of NBFC/HFC opex × the SCB wage/opex ratio. The deposit-taking share is FSF `fc_odc_*_dt` / (dt + ndt) F4 assets: 16.69% for NBFCs, 75.09% for HFCs;
     - NBFC CE is the residual;
     - NPT is split pro rata to GVA.
   - Public shares:
     - banks = (PSB + RRB operating profit) / (all banks' operating profit + the deposit-taking proxy) = 40.44%. The proxy is NBFC-UL/ML PBT × 16.69% + HFC (fund income + fees − financial expenditure − opex) × 75.09%;
     - insurers = the life/non-life GVA weight × (LIC share of life opex, or the public + specialised share of non-life NPE) = 47.78%;
     - NBFCs = the residual to NAS 7.1A, which is 37.0%.
2. **R3 and R3a (35 entries).** Each payer line is multiplied by the HBS T107 holder shares. The lines are:
   - dated securities: MH 2049.01.101 less Receipt MH 0049.03.116/.117;
   - T-bills: .103 + .108 + .110;
   - SDLs: RBI SF App. II market loans.

   The FPI parts come from the T107 FPI share, and they equal rest_of_world's R14 components exactly (XR-12). The RBI part = AR Sch 13A rupee-securities interest + Sch 14A amortisation, 90,194.80, split between the Centre and the States by T107 RBI share × line. The remainder is spread over the other holders:
   - banks → E_BANK;
   - PDs and FIs → E_NBFC;
   - insurance, PF and pension funds → E_INSP;
   - mutual funds → look-through to unit holders by SEBI T72 AUM (banks 0.89%, corporates 37.11%, HNIs + retail 62.00%);
   - corporates → E_NFPU and E_NFPR by FSF gg F3 holdings;
   - 'others' less State governments → HH, E_NFPU and E_NFPR by FSF;
   - 'others: State governments' → the R3 `gsec_state_reserve_funds` (the SDL part is intra-G_STA and is dropped).

   Other Union securities (21,201.38) use the dated-security shares.
   - WMA (Centre) = MH 01.115.
   - The States' WMA/overdraft interest = AR loans-and-advances interest less the Centre's WMA, × the FSF RBI F4 share on gg_sta.
   - The States' other internal debt goes to E_BANK/E_NBFC by FSF gg_sta F4 liabilities.
3. **R3b targets.**
   - Union = the MH 2049 total, less:
     - intra-G_CEN interest (NSSF 01.121/.122/.125, reserve funds 05, FCI 60.107, PLI 60.111);
     - management of debt;
     - recoveries;
     - re-issue receipts;

     plus the NSSF interest to savers (the Union's NSSF interest + the States' NSSF interest) = 10,86,513.97.
   - States = App. II interest, less 'others', less SDLs held by States = 4,94,608.64.
4. **R4 and R5 (72 entries) and FISIM.** I rebuilt all 52 FSF who-to-whom positions from `rbi_financial_accounts_fsf_balance_sheets`. For OFC counterparties:
   - the ODC-side stock is split into NBFC, ICPF and MF parts by the OFC sub-sectors' own positions on fc_odc;
   - intra-OFC debt issued by NBFCs is split by the ICPF and MF holdings on fc_ofc.

   Then:
   - Bank interest = stock × the RTP SCB rate (return on advances 9.4%, return on investments 6.7%, cost of deposits 4.8%, cost of borrowings 8.1%) × a scale.
   - The scale makes each lender's total equal its RTP P&L. The P&L totals net out:
     - R3a (without the MF look-through);
     - LAF/SDF, MSF and RBI loans;
     - RoW R13 `oi_income` and R14 `nri_deposit_interest` + `oi_other_interest`;
     - for E_NBFC, the interest from and to E_BANK computed on the banks' side.
   - FISIM:
     - NAS 1.13 IC FISIM is split by user industry into public NFC, private NFC and household producers by NAS 7.1A (less GG IC from 8.15.1), 7.1B and 7.1C IC.
     - NFC FISIM is split into deposits and loans by (r_L − r*)L and (r* − r_D)D, with r* = 6.7%.
     - Household FISIM = households' C4b `fisim_deposits` / `fisim_loans` by group × (1 + household-producer IC FISIM / PFCE FISIM) = × 1.441645.
     - Lender shares of FISIM are proportional to bank interest.
   - SNA interest: loans = bank interest − FISIM_L; deposits = bank interest + FISIM_D.
   - Household groups are keyed by `aidis_inst_loans`, `aidis_deposits` and `aidis_fin_assets`.
5. **R8 and R8a (228 entries).**
   - Issuer totals:
     - E_NFPU = government R7 from E_NFPU / the gg share of FSF nfc_pub F51;
     - E_BANK = R7 banks / the gg share of fc_odc F51;
     - E_INSP = IRDAI interim + proposed final dividends;
     - E_NFPR and private E_NBFC = (E_NFPU dividends / factors' E_NFPU GOS = 0.086057) × GOS.
   - Holders are allocated by FSF F51 shares. The OFC holdings are split into NBFC, ICPF and MF by the sub-sectors' F51 assets, with MF looked through.
   - The other R8a components come from items 2 and 4 and from the R8a small-savings interest.
   - The group keys are `aidis_equity`, `aidis_mf`, `aidis_fin_assets` and `aidis_small_savings`.
6. **R9c (70 entries).**
   - Life = IRDAI t24 policyholders' interest, dividends and rent + amortisation.
   - EPF and EPS = average EPFO investments × 8.25%.
   - Exempted PFs = (FSF PF F6 − EPF − EPS − NPS AUM) × 8.25%.
   - NPS = the T107 pension-fund G-sec interest + NPS corporate bonds × 8.1% + NPS equity × the market dividend yield. That yield is all issuer dividend totals / average NSE market cap = 1.8193%.
   - GPF (Union) = MH 2049.03.104. The States' PF = App. II ii.c.2.iii.
   - Keys:
     - private regular wages = factors F1a F_LREG less `public_sector_wage_key`;
     - the public-sector key;
     - `pop_persons` of the bottom three quintiles for APY and NPS-lite;
     - NPS by the 2023-24 contribution shares (0.703 / 0.255 / 0.042).
7. **R17 (36 entries).**
   - Claims = premiums = IRDAI t44 net incurred claims by line.
   - Supplements = IRDAI summary investment income − the t51 shareholders' investment income, by line in proportion to NPE.
   - Payers: households by the block's assumption shares (0.70 / 0.55 / 0.10 / 0 / 0.30), keyed by `c4b_insurance_service`. The NFC part goes to E_NFPU and E_NFPR by factors' GOS.
8. **K2a (7 entries).**
   - E_RBI = all E_RBI receipts in the built SAM, except R13 `reserve_income_unexplained`, less all E_RBI payments (D2-7) = 94,157.38.
   - The others = their F4a public or private GOS × (NAS public saving − E_RBI) / (public GOS − E_RBI), or × private saving / private GOS.

## 2. Value counts

| Object | Count | Checked | Result |
|---|---:|---|---|
| Entries | 455 (121 ≥ ₹10,000 cr) | census | all within ₹0.01 cr (the block's GG-IC list); 37 differ under the corrected list (V-FIN-1) |
| Constraints | 14 | all: target, selection, kind, tolerance; holds on the prior of 8 blocks | all match; all hold |
| Checks | 14 | all targets; SAM values of the K2a pair | match; 13 pass, 1 fails by design (fincorp-1) |
| Provenance records | 42 | inputs resolve; entries cite a record of their own ref and status | 3 inputs no longer resolve after the government rebuild (V-FIN-5) |
| `s9_funded_schemes` | 35 rows | census vs EPFO, PFRDA, IRDAI, FA St 14, RBI SF App. III/IV, NSSF | match |
| `gov_interest_bridge` | 97 rows | census (65 FA/RBI SF lines, 20 holder allocations, 8 derived items, 2 targets, 2 others) | match |
| `interest_fisim_bridge` | 127 rows | census | match |
| `dividend_matrix` | 62 rows | census | match (differences < ₹0.004 cr: the block drops FSF 'other_resident', 0.1) |
| `d44_by_scheme`, `mf_lookthrough`, `fc_public_private` | 16 / 5 / 16 | census | match |

The prior imbalances in the issues file are confirmed on the current files:

| Account | Imbalance (₹ cr) |
|---|---:|
| E_BANK | −1,70,836.24 |
| E_NBFC | +1,81,330.00 |
| E_INSP | −1,58,175.55 |
| E_RBI | +25,645.50 |
| FC sector | −1,22,036.28 |
| K_RBI, K_BANK, K_NBFC, K_INSP, F_GOSC | about 0 |

## 3. Checks on method, labels and double counting

- **Plan and decisions.** The block follows the plan as amended by its s.8 and CROSS_REVIEW:
  - XR-4 and D2-7: E_RBI saving is taken from the SAM entries, without the unexplained reserve income.
  - XR-5: the households' C4b FISIM is used by group.
  - XR-6: E_BANK = the FSF ODC boundary, and there is no HDFC month-weighting.
  - XR-10: the key names.
  - XR-12: the FPI interest is read from R14 and is identical to the plan's formula.
  - XR-13: RoW FISIM is excluded, and domestic FISIM 12,30,782.43 is written exactly.
  - XR-29: the MF look-through NFC interest is logged under R8.
  - D2-14: co-operative banks are private.
  - D2-16 and D0-7: the RBI surplus is on a cash basis.

  The evidence is reproduced. The plan's RBI-AR-only computation is +121.81 against NAS. The SAM-based evidence is −1.90; the difference of 123.71 is fincorp's R8 dividends to E_RBI (245.75) less rest_of_world's R14 items (371.66) plus the AR interest expense (2.19). The accrual surplus would miss by about −1.2 lakh.

  The deviations from the plan are all logged: fincorp-3, -9, -13, -17, -20 and -21. Two are not: V-FIN-1 and V-FIN-3.
- **Signs and zeros.** Every entry is positive, and there are no zero entries. RBI's net LAF/SDF payment is written as E_BANK ← E_RBI (+12,668.88).
- **Roles and status.** The anchored entries are the ones with published totals:
  - E_RBI F4a;
  - R3 cash lines;
  - E_RBI ← G;
  - recap bonds;
  - RBI ↔ bank lines;
  - GPF (Union).

  Everything else is free and estimated, with a confidence. K2a and R8 are low; the key-based splits are low or medium. The one mislabel is V-FIN-2.
- **Double counting.** No other block writes a fincorp ref.
  - The cells fincorp shares with government carry different flows:
    - G_CEN ← E_BANK: R4 deposit interest and R7 dividends;
    - E_NFPU/E_NFPR/E_INSP ← G_CEN: R3a and R18;
    - H_* ← G_*: R8a/R9c and R9a/R10.
  - The plan's T14 guards hold:
    - no R_ROW entries;
    - no G ← E dividends;
    - no R3a to households;
    - no R5 on government;
    - no PPF in R9c;
    - no G_CEN ← G_CEN.
  - The MF look-through income goes only to E_BANK, E_NFPR and households, never to an MF account.
  - One cross-block overlap is open and is not in fincorp's issues file: V-FIN-7.
- **Gaps and defaults.** Every assumption parameter is its own provenance record:
  - r*;
  - r_corp;
  - the EPS and exempted-PF yield;
  - the NFC_pvt dividend ratio;
  - the R17 splits;
  - MF corporates → E_NFPR.

  The builder's list of what is not written (fincorp-20) is accurate except V-FIN-4.

## 4. Findings

| # | Severity | Finding | Evidence | Fix (for the builder) |
|---|---|---|---|---|
| V-FIN-1 | minor | **FISIM user key keeps GG's utilities IC in public NFCs.** The plan's rule is "IC shares of 7.1A less GG", and fincorp-13 describes it. NAS 8.15.1 publishes GG IC for construction, other services, public administration and **utilities** (36,031.26). The block subtracts only the first three (`GG_IC` in `interest.py`). | IC FISIM to public NFCs is 54,875.80 instead of 53,648.36 (+1,227.44); private NFCs 3,06,743.07 instead of 3,07,886.79; household producers 2,66,266.60 instead of 2,66,350.32. 37 R4/R5/R8a entries move, the largest being E_BANK ← E_NFPU R5 loans (−657.80) and E_BANK ← E_NFPR (+571.00). Strict xfail `test_ic_fisim_user_split_removes_all_gg_ic`. | Add utilities to the GG IC list (or subtract 8.15.1 IC for every industry it publishes), rebuild, and update fincorp-13. |
| V-FIN-2 | minor | **Union GPF group entries are labelled derived/anchored (2%).** The household split is factors' `public_sector_wage_key`, an *estimated* record (sam_factors:097aec5e9ffc), and it is an input of the derived record sam_fincorp:756d9499d48d. SAM_GUIDE says derived means arithmetic on official numbers. Anchoring each of the 10 group entries also locks the distribution by group at 2%, although the total is already held by `r9c.gpf_union` (equal, 2%). | 10 entries, 18,871.50 in total. Strict xfail `test_gpf_union_group_entries_are_labelled_estimated_and_free`. | Make the 10 entries estimated, free, medium. Keep the total in the constraint. |
| V-FIN-3 | minor | **Banks' dividends are grossed with the wrong government share.** The numerator is the Union's receipts only (R7 `banks` 14,295.56 = MH 0050.00.108 + .109). The denominator is the government's (Centre + States) share of FSF ODC equity (26.2%); the plan (s.2.6) specifies the gg_cen share (23.0%). The dividend memo also puts only 12,570.16 on G_CEN, against the 14,295.56 that government actually books. | Issuer total 54,563.61 instead of 62,053.06 (−7,489.45, −12%). The domestic R8/R8a flows from E_BANK are 12% too low (about −2,700). Strict xfail `test_bank_dividend_grossing_uses_the_union_share`. | Gross with the gg_cen share (or add the States' bank dividends to the numerator), and log the choice. |
| V-FIN-4 | minor | **Interest on government-held FC debt is written by no block.** FSF shows GG holding bank bonds and borrowings (G_CEN 11,529, G_STA 11,098) and OFC bonds and loans (gg_cen F3 1,66,983.53 + gg F4 17,629.74). fincorp drops these positions from its interest matrix, and the comment says "interest to GG is government's R7x". fincorp-20 says the same for the bank part. But government's R7x has no E_BANK or E_NBFC entry (only `interest_psu` and `interest_other_parties` from NFCs), and the NBFC part is not logged at all. | Unwritten interest about 2,045 (banks, at the scaled 8.1%) and 8,400–15,000 (NBFCs). Because the positions are left out of the scale denominators, the other creditors of NBFCs absorb it (the NBFC expended scale would be 0.503 with them, not 0.564). Strict xfail `test_interest_on_government_held_fc_debt_is_written_somewhere`. | Either write G_* ← E_BANK/E_NBFC interest (R4 `bonds`/`borrowings`, which is a fincorp cell), or agree with government that its R7x takes it. Log it either way. |
| V-FIN-5 | major (process) | **fincorp is stale against government, and its provenance no longer resolves.** Government was rebuilt at 00:15, after fincorp (23:58). The R6/R7 values fincorp reads are unchanged: the census re-read them. But the R7 record ids changed, so fincorp's R8, R9c, S9, K2a and R8a records cite `sam_government:36d8c125812a`, `3c356959e46f` and `65ca22ae32dc`, which no longer exist. | `tests/sam/test_sam_audit.py::test_every_sam_provenance_input_resolves` fails on these three (and on two capital_financial ones). The builder's `tests/sam/test_sam_fincorp.py::test_built_outputs_equal_a_fresh_build` also fails, because the record ids in the entries change. The staleness guard in the spot-check skips. | Rebuild fincorp, then capital_financial (or `sam` with no names). The result should be byte-identical in entries. |
| V-FIN-6 | minor | **The dividend memo does not describe the flows the SAM contains.** The private-only E_NBFC total (ratio × private GOS) is split with the whole OFC sector's holder shares, including 41.6% government (public NBFCs), so 11,544.58 of "private NBFC dividends" goes to a G memo that no block writes. The same holds for the E_INSP (1,815.91) and E_NFPU (1,222.64) RoW memos, which rest_of_world does not write. The G_CEN memos (E_NFPU 70,254 vs R7 64,906; E_INSP 2,936 vs R7 4,272.54) differ from what government books. | `dividend_matrix` rows labelled "memo: R7" or "memo: R14". | For the private E_NBFC total, use private holders' shares (exclude gg). Label the memo as "FSF-share memo, not the SAM flow", or reconcile it to R7/R14. Log it. |
| V-FIN-7 | minor | **Possible overlap with government's R7x, not logged in fincorp's issues.** fincorp's R4 bank-deposit interest to GG (G_CEN 18,847.02, G_STA 82,081.25) comes from FSF deposit stocks. government-26 notes that the treasury shows no such receipt except the States' interest receipts (28,493.58), which government books wholly from E_NFPU. It also notes that the SAM's GG disposable income is 1.93 lakh above NAS (government-1). | government-26 OPEN; no fincorp item. | Add an issue: which GG units hold the 15.3 lakh cr of State deposits (local and autonomous bodies?). Decide with government whether part of App. I ii.c.1 is this interest. |
| V-FIN-8 | minor | **The F4a method text is not reproducible as written.** It says "deposit-taking NBFC/HFC profit proxy" without defining it. The proxy is NBFC-UL/ML PBT × dt share + HFC (fund income + fee income − financial expenditure − operating expenditure) × dt share. It moves the bank public share from 43.73% (the plan) to 40.44%. | Record sam_fincorp:9aeeccaa9347 (and 0de7806b5ba6). | State the proxy's series in the method text, and log the change against the plan's 43.73%. |

Observations that are not defects:
- fincorp-3 and fincorp-4 are reproduced. The ODC-side FSF stock of borrowings from OFCs (18.48 lakh cr) is 4.5 times the OFC-side asset (4.11 lakh cr). The block uses the ODC side, which sets E_NBFC ← E_BANK interest at 1,63,585. Lender P&L totals are pinned, so this reallocates counterparties rather than changing the E_BANK or E_NBFC totals. Worth one line in fincorp-4.
- Three items total ₹11.97 crore:
  - FSF records 191 crore of OFC-held household debt securities;
  - the block puts their interest into E_NBFC's R5 `loans` component for households;
  - the census reproduces it.
- The R17 household entries are free medium, although the line splits are an assumption record marked low. This is defensible, because premiums equal claims by line and the split only moves the supplements between sectors.

## 5. Test file

`tests/verify/test_sam_fincorp_spotcheck.py`. It does not import `pipeline.sam` or polars; it uses DuckDB and plain Python. It contains:

- `test_entry_census_all_455_entries_recomputed`: every entry against my recomputation (tol ₹0.01 cr).
- `test_ref_totals_against_clean_sources`, which checks:
  - the F4a, K2a, life D44, GPF, R17 and small-savings totals;
  - FISIM written = NAS 1.13 IC + PFCE.
- `test_constraint_targets_and_selections` and `test_constraints_hold_on_the_assembled_prior`.
- `test_check_targets_and_the_rbi_saving_evidence`, which covers:
  - all 14 check targets;
  - the D0-7 evidence;
  - the plan's C3 figure (+121.81);
  - the accrual counterfactual.
- `test_satellite_bridges_reproduce` and `test_s9_funded_schemes_census`.
- `test_roles_statuses_and_structure`: the anchored set, statuses, confidences, the plan's T14 guards, and group-level household entries.
- `test_provenance_inputs_resolve_and_records_match_refs`. Unresolved inputs are tolerated only from a dependency fincorp is stale against (V-FIN-5).
- Strict xfails for V-FIN-1, V-FIN-2, V-FIN-3 and V-FIN-4.
- `test_dependency_outputs_read_are_current`, which skips with the V-FIN-5 message while fincorp is stale.

## Re-verification (wave C close-out, 2026-10-01)

Verifier: an agent that wrote none of the block, its D2-21 repair, the Wave C fixes, the original verification above or the fixers' edits to the regression test (SPEC s.3 rule 3). Scope: what changed after the original verification. That is the D2-21 repair (fincorp-27 to -31) and the Wave C audit fixes (fincorp-32 to -37: 16 new constraints, the R17 premium band narrowed from 5% to 1%, and the corrected `r8.mf_nfc` method text). It also covers every expectation the fixers changed in `tests/verify/test_sam_fincorp_spotcheck.py`. That file has never been committed, so there is no `git diff`. I compared it with the method in sections 1 and 5 above.

Files checked: the fincorp build of 2026-10-01 05:40 and the balanced run of 05:41 (`sam_entries_balanced.parquet`, `balancing_constraints.parquet`). Method: four scripts of my own. They use DuckDB on `data/clean` and the dependency entries in `data/sam/2023-24/blocks`. They do not import `pipeline` and do not use the test file's helpers.

### What was recomputed, with counts

| Item | Checked | Result |
|---|---|---|
| D2-21 top-up (fincorp-27): 26 entries, R8/R8a `distributed_income(_mf)` | All 26, from the old-base St 2.2 2022-23 clean rows, factors' F4, the FSF F51 holder key, SEBI T72 and hh_keys, plus E_NFPR's net D4 over every block's built entries | Max difference 5.3e-7. Ratio -0.314510 (St 2.2 is `nfc_private`, FRE). Net D4 before -7,20,692.43. Prior -14,52,730.35. Total 8,21,158.76. Returning share 0.108531. After the top-up, E_NFPR's net D4 equals the prior exactly. Labels: estimated, free, low. Both records say "estimated, old-base structure". No constraint pins the top-up, so it is a prior, as D2-21 requires. |
| Old-base satellite rows (`dividend_matrix` `oldbase.*`, 32) | Ratio, the 2021-22 and 2020-21 sensitivities, before/after by source, holder rows, the cross-check rows (D4 share of net distributive flows 0.657345; prior via the new-base requirement -14,51,824.16) | All match |
| fincorp-28 OFC claims on banks | 9 creditor/instrument claims and 8 position stocks, from FSF (ODC-side total 29,55,370.40 split by the OFC-side claims 31,24,894.94) | Exact (difference 0.0000) |
| All FSF position stocks in `interest_fisim_bridge` | 47 more positions, rebuilt from FSF by the documented mapping, including the 7 GG-held bank/NBFC positions (V-FIN-4) | Max difference 5e-5. None missing, none extra. |
| fincorp-30 and the lender scaling | 55 positions: bank interest = stock x RTP rate x lender scale, with r_corp 8.1% on insurers' and MFs' corporate bonds. The 4 scale targets were rebuilt from the P&L lines less R3a, LAF/SDF, RoW and RBI loans | 0 mismatches. The targets hold (for example, banks' income 18,69,415.47). Banks pay NBFCs 1,04,943.04. |
| fincorp-29 FISIM lender split | 12 lender shares by reference-rate margins (r* 6.7%). FL/FD per NFC user. The 8 NFC R5 loans / R4 deposits entries. Household loan FISIM by lender | All match. FISIM by lender: 10,79,484.94 + 1,51,297.49 = 12,30,782.43 (NAS 1.13 IC + PFCE). NBFC loan FISIM 1,50,226. |
| fincorp-31 E_INSP memo (7 rows) | IRDAI life policyholders 3,77,927.22, life shareholders 8,491.18 + 129.74, non-life 44,129.04, PF/pension D44 3,50,236.81. SAM receipts of E_INSP (R3a+R4+R5+R8, without the diagonal) | 7,80,914.00 vs 6,42,427.92, a shortfall of 1,38,486.08. The rows reproduce. The memo is reported only; nothing is forced. |
| Wave C constraints (16 new, plus `r17.premiums` 5% -> 1%) | Every target recomputed straight from the sources: IRDAI T44/T51/summary, NAS 1.9 and 7.1A less the R14 debit, RBI SF App. II, FSF x r_corp, SEBI T72, government R7 grossed by FSF F51. Kinds, tolerances and selections checked. Every target was also checked as the sum of its selection on the prior | All 18 targets within 1e-3. The `r8.nfpu_nongov_holders` target 30,714.07 decomposes as: non-government rest 28,622.63, less the RoW memo 1,222.64, less E_NFPU's own holding 2,921.23, plus households' MF-held public NFC bond interest 6,235.31 (V-FIN-10). `k2a.rbi_ar_basis` = 5,35,509.90 - 4,34,232.62 - 7,118 = 94,159.28. |
| Records | 55 (42 + 5 repair + 8 constraint-target records) | Count, statuses and method texts consistent. `r8.mf_nfc` (fincorp-36) now says the corporate coupon. |
| Balanced figures quoted in the Wave C table and fincorp-32 to -37 | Checked against `sam_entries_balanced` and `balancing_constraints` | Reproduced. Examples: supplements 37,465.46, K2a E_RBI 96,659.28 (upper edge), `reserve_income_unexplained` 25,645.50 -> 7,712.74, K2a banks 4,11,589.93 and NBFCs 4,05,217.51, E_INSP <- E_NFPU R5 41,481.26, the States' other internal debt 26,911.02, and the five E_NFPU flows of fincorp-37. `explanations/fincorp.yaml` has 171 items. |

Was anything quietly forced? No. No constraint targets Z, an account gap or E_NFPR's net D4. The top-up is a free, low prior. Each new band is centred on a source-based prior value: IRDAI, App. II, NAS less the R14 debit, or FSF x coupon. They bound balancing moves. They do not make a number land. The exception in kind is the R17 payer bands (V-FIN-9), which hold an assumption-based split tightly.

### Findings

| # | Severity | Finding | Evidence | Fix (for the builder) |
|---|---|---|---|---|
| V-FIN-9 | minor | **The R17 payer bands do not hold D71 = D72 by payer, and the 5% is not the split's uncertainty.** Each payer's premiums and claims are banded separately, each within 5% of the prior. Balancing therefore pushes them to opposite edges. The record (sam_fincorp:894a0f346519) says the bands stop premiums exceeding claims "by more than the split's uncertainty". But the split is an assumption record whose stated sensitivity is +-0.2 per line, far wider than 5%. The Wave C table says E_NFPU's premiums and claims end "within 5% of each other"; that is not so. | Balanced: E_NFPU premiums 16,323.48 vs claims 14,768.86 (+10.5%; both bands binding at opposite edges); E_NFPR 63,921.96 vs 59,133.75 (+8.1%); households 93,767.93 vs 96,664.94 (-3.0%). In total, `r17.premiums` is at +1% and `r17.claims` at -1%. Strict xfail `test_r17_premiums_equal_claims_by_payer_after_balancing`. | Hold premiums less claims by payer (a signed selection, if the framework allows one), or give the premium and claim of a payer one shared band. Otherwise state the up-to-10% spread, and the band's basis, honestly in the record and the issues file. |
| V-FIN-10 | minor | **`r8.nfpu_nongov_holders` is described as dividends but also bands bond interest.** Its selection (R8/R8a `dividends,mf_lookthrough`) includes households' R8a `mf_lookthrough` from E_NFPU, which carries MF-held public NFC bond interest. The record discloses this; the constraint's description ("Public NFC dividends to non-government holders near the R7-grossed issuer total") does not. The treatment of the MF bond interest is uneven: the part to private NFCs is in `r8.mf_bonds.e_nfpu`, the households' part in this dividend band, and the banks' part (R5 `mf_lookthrough`) in no band. | 6,235.31 of the 30,714.07 target (20%) is bond interest. The dividends in the selection are 24,478.76 (incl. E_BANK's MF dividends 142.95), against a non-government total of 28,622.63. The balanced sum is at the +25% edge, 38,392.58. | Split households' MF component into its dividend and interest parts, or band them separately. At least correct the description. |
| V-FIN-11 | minor (documentation) | **Stale or mis-transcribed figures in `docs/phase2/issues/fincorp.md`.** (a) fincorp-27's holder split (households 3,37,639 + 1,48,716, E_NFPU 94,866, E_NBFC 85,822, E_BANK 38,913 + 2,143, E_INSP 22,989, back to E_NFPR 89,005) sums to 8,20,093, not the stated 8,21,158.76. The entries give 3,38,077.85 + 1,48,908.97, 94,989.63, 85,933.83, 38,963.45 + 2,145.66, 23,018.52 and 89,120.84; fincorp-32 already uses 94,989.63. The households' 4,86,355 (fincorp-19, the repair section) is 4,86,986.82 in the entries. (b) The sensitivity ratios are -0.322348 (2021-22) and -0.372404 (2020-21), not -0.322288 / -0.372402 (the priors quoted with them are right). (c) The Wave C section speaks of "13 new constraints"; there are 16. (d) "within 5% of each other" (V-FIN-9). | Recomputed above; satellite `dividend_matrix` `oldbase.*`. | Correct the text. No numbers in the block change. |

Observations (not defects):
- **Z.** The prior on the current files gives Z = K4a 55,05,783.63 - NAS 1.9 households 58,90,330.45 = **-3,84,546.82**. The -4,36,163.72 of the repair was measured on the files of that time. Blocks rebuilt since then (closure now also writes an X_DISC D1 row) moved it. fincorp's part, the households' share of the top-up (4,86,986.82), is reproduced. The move from -9.58 lakh cannot be replayed on the current files and is not a fincorp question.
- **E_NFPR's net D4 counts rest_of_world's `other_primary_income`** (R13 38,741.70 received, R14 9,482.56 paid). Its content is undocumented (rest_of_world's records) and may not all be D4. Leaving it out would cut the top-up by about 32,821 (total about 7,88,337). The method text discloses it ("R13, R14"), and the size is inside the ratio's own sensitivity (2021-22: +36,204).
- The 25% bands of `r5.insp_bonds.*` and `r8.mf_bonds.e_nfpu` ("the spread of corporate bond coupons") cite no source for the 25%. They are labelled estimated. E_INSP <- E_NFPU ends at its edge, an implied yield of 10.1% on FSF holdings.
- `k2a.rbi_ar_basis` reads the debit from rest_of_world's entries. If rest_of_world-26 moves the debit to G_CEN, the target follows by itself. Balancing removed 17,933 of the 25,646 unexplained reserve income and kept 7,713, with K2a E_RBI at its upper edge. The wording "balancing now removes it" holds only in part.
- Outside this scope, for the balanced-SAM verifier: `r9c.gpf_union` (official, `equal`, 2%) ends at its +2% edge, 19,248.93 against the published 18,871.50.

### Test file

Run: `tests/verify/test_sam_fincorp_spotcheck.py` gives 18 passed and 1 strict xfail (V-FIN-9). `pytest -k fincorp` over `tests/` gives 62 passed and 1 xfailed. Every expectation the fixers changed was confirmed by my own recomputation, and **none was reverted**:

| Expectation changed by a fixer | Disposition (recomputed value) |
|---|---|
| Entry count 455 -> 462 -> 488 | Confirmed: 455 + 7 (V-FIN-4) + 26 (D2-21) = 488 |
| Entries >= 10,000: 121 -> 140 | Confirmed: 140 |
| Records 42 -> 47 -> 55 | Confirmed: 55 (5 repair records, 8 constraint-target records) |
| GG IC of all four 8.15.1 industries (V-FIN-1) | Confirmed: IC FISIM public NFCs 53,648.36 |
| E_BANK dividends grossed by the Centre's share (V-FIN-3) | Confirmed: 62,053.06 (share 23.04%) |
| GG-held bank/NBFC debt inside the scaling (V-FIN-4) | Confirmed: 7 FSF positions; R4 entries now 9,614.41 (the bank expended scale moved with fincorp-28) |
| Government dividend parts = R7; private E_NBFC to non-government holders (V-FIN-6) | Confirmed: E_RBI <- E_NBFC 48.99 |
| GPF groups left the anchored set (V-FIN-2) | Confirmed: 10 entries estimated, free, medium |
| D0-7 evidence bound < 30 | Confirmed: 94,182.60 + 7,118 - 1,01,277.28 = +23.32 |
| `positions()`: OFC claims by the creditors' mix (fincorp-28) | Confirmed (exact) |
| `positions()`: r_corp on E_INSP/MF corporate bonds (fincorp-30) | Confirmed (0 mismatches) |
| `interest_entries().split`: reference-rate margins (fincorp-29) | Confirmed (12 shares, 8 entries) |
| `oldbase_topup` (fincorp-27) | Confirmed: 8,21,158.76; max difference 5e-7 |
| Constraint set, `r17.premiums` at 1%, 16 Wave C targets | Confirmed from the sources (within 1e-3) |

Added: `test_wave_c_constraint_targets_recomputed_from_sources`. The fixer's targets came from this file's own recomputed entries; this test takes them from the sources and pins the V-FIN-10 decomposition. Also added: `test_oldbase_topup_satellite_rows` and the strict xfail for V-FIN-9. The file was run through `ruff format`, which reflowed the fixers' long lines. The docstring records the re-verification.
