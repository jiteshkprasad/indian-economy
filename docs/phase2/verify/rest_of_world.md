# Verification: the `rest_of_world` block (SPEC s.3 rule 3)

Verifier: an independent agent (not the rest_of_world builder), 2026-09-30.
Scope: the rest_of_world block only (refs R11/R11a, R12/R12a, R13, R14, R14a, K5, K8b, K8c, D2, S1-S3 and the interface and sensitivity satellites). I recomputed every entry, every constraint target and every check target from the clean Parquet with DuckDB SQL plus plain Python arithmetic. Where the plan says the block legitimately reads another block (households' `hh_state_xwalk` and `hh_keys`, production's P6), I read those published outputs. I did not import or call the builder's code; I read two of its lines only to locate the cause of V-ROW-1 and V-ROW-2 after the tests had found them.
Regression test: `tests/verify/test_sam_rest_of_world_spotcheck.py`. It does not import `pipeline.sam` or polars.
- Against the households output this block read: 17 passed and 2 strict xfails (V-ROW-1, V-ROW-2).
- After another agent rebuilt households at 23:01: 14 passed, 3 skipped (V-ROW-5: staleness guard) and 2 strict xfails.
- Full offline suite, run once at the end: 3,851 passed, 4 failed, 56 skipped, 32 xfailed. None of the 4 failures is in this block's files or mine:
  - `test_sam_framework::test_a_broken_sibling_module_does_not_stop_another_blocks_build`, which the builder already reported;
  - two tests in `test_sam_households_spotcheck`, caused by the concurrent households rebuild;
  - `test_sam_solver_certificate::test_the_proximal_fallback_path_is_deterministic_across_hash_seeds_and_threads`.
Outputs checked: the build of 2026-09-30 22:34 (`rest_of_world_entries.parquet`). Its catalog records the sha256 of the households and production outputs it read. When I ran the census, those hashes matched the files on disk, so every result below applies to that build.

Another agent rebuilt households at 23:01, after the census. The block is now stale on households (V-ROW-5).

## Verdict

**Sound, with minor fixes.** Every number the block writes matches my recomputation:

- **Entries: a census of all 81**, not a sample (51 of them are ≥ ₹10,000 crore). The largest difference is 4.9e-7 crore, which is the 6-decimal rounding on write.
- **Constraints: all 14.** Targets, selections, refs and components filters, kinds and tolerances all match.
- **Checks: the targets of all 29.**
- **Satellites:** every row of `row_property_income`, `row_financial_counterparts`, `s3_remittance_sources`, `r11a_sensitivity` and `r12a_sensitivity`. For S1 and S2, the totals and the ITES override.

Beyond the individual numbers:

- R_ROW and K_ROW close on the prior of all eight built blocks (to under ₹0.01 crore).
- Each constraint holds on that prior, within ₹1 crore.
- No other block writes any cell this block writes.
- capital_financial mirrors each K8b counterpart exactly once.

The two confirmed defects are in provenance, not in values:

- **V-ROW-1:** a record cites the wrong input.
- **V-ROW-2:** a method text has an unformatted placeholder.

V-ROW-3 is a cross-block ownership gap worth ₹5,411 crore on G_CEN that the builder and government each leave to the other. V-ROW-4 is a formatting break in the issues file. V-ROW-5 is staleness caused by a concurrent households rebuild; the fix is a rebuild.

## 1. Method (what I recomputed, and how)

Unless stated, each value is the latest vintage of that (series, period). Stock keys average 2023-03-31 and 2024-03-31. Rs crore, FY 2023-24.

1. **R11a.** Survey shares come from `remit.destination_state.*` (period 2023-24, vintage 2025-03-19; sum 100.0), normalised.
   - w_kg is State k's consumption in group g divided by its total. The source is households' `hh_state_xwalk` (`measure='consumption'`, `hces_class='all'`, rural + urban summed), with `geography` lower-cased ('IN-MH' → 'in-mh').
   - R11a_g = NAS 6.1 item 4 × Σ_k s_k w_kg. All 36 survey States are in the crosswalk.
2. **R12a.** NAS 6.1 item 9 goes to H_U4 and H_U5 in proportion to `hh_keys` `pfce_total` levels.
3. **R13 (recipients).**
   - **E_RBI `reserve_asset_income`** = RBI AR Sch 13(b) sub-total + Sch 14(b)(i) amortisation (vintage 2025-05-29) = 1,05,413.50.
   - **E_RBI `reserve_income_unexplained`** = BPM6 1.B.2.4 credit − that = 25,645.50 (D2-7, XR-4).
   - **DI and PI income** use the FSF RoW-liability F51 stocks (nfc_pvt → E_NFPR, fc_ofc → E_NBFC, fc_odc → E_BANK). The key is 94.96 / 4.99 / 0.05%.
   - **OI income** uses FSF RoW-liability F22_F29 + F4 stocks (fc_odc, nfc_pvt, gg_cen, fc_ofc). fc_rbi and F3 are excluded; the other counterparties are 0.
   - **Other primary income** = 48,821 + (NAS item 3 − the five BoP credit types = −0.68), spread pro rata to DI + PI + OI by recipient.
4. **R14a and R14 DI distributed.**
   - The FC share is FLA t8 financial equity / total equity (period 2024-03-31, vintage 2024-10-11) = 16.0454%.
   - E_BANK's total is foreign banks' profit, RTP income_total.fb − expenditure_total.fb (vintage 2025-12-29) = 26,885.
   - E_BANK's total is split reinvested : distributed in the ratio NAS reinvested earnings / BoP DI debit (0.3961). E_NBFC gets the FC remainder. E_NFPU and E_INSP get 0.
5. **R14 portfolio income (XR-12).**
   - The FPI holding share is the average of the T107 FPI shares at the two dates. Each interest line is multiplied by that share:
     - central: FA 2049.01.101 − FA 0049.03.116 − .117 (re-issue receipts);
     - T-bills: 2049.01.103 + .108 + .110;
     - SDLs: RBI SF App. 2 interest on market loans, all States/UTs.
   - `pi_other` = PI debit − those three. It is split NFC/FC by the FLA t8 key. The FC part is split E_BANK : E_NBFC by their DI payments (R14 `di_distributed` + R14a).
6. **R14 other investment income.**
   - `ext_assistance_interest` = FA 2049.02.total.
   - `nri_deposit_interest` = average NRI deposit stock × the SCB cost of deposits, 4.8%.
   - `oi_other_interest` = OI debit − the two lines above. Its key is FSF RoW-asset stocks:
     - F4 fc_odc + (F22_F29 fc_odc − the NRI average) → E_BANK;
     - F4 fc_ofc → E_NBFC;
     - F4 nfc_pvt → E_NFPR;
     - F22_F29 fc_rbi → E_RBI.
   - `reserve_asset_debit` = BPM6 1.B.2.4 debit, on E_RBI.
   - Other primary income = 15,293 + (NAS item 8 − the five debit types = +0.52), spread pro rata to every other R14 component by payer (R14a excluded).
7. **K5, K8c, D2.**
   - K5 = NAS 1.9 net capital inflow.
   - K8c = BPM6 3.5 debit.
   - D2 = SUT `supply.cif_adj.cif`.
8. **K8b.**
   - Each line is the old-format BoP net flow, sign-reversed on the asset side. There are two exceptions: `fdi_reinvested_earnings` = NAS 1.9 (= R14a) and `errors_omissions` = NAS 6.1 other liabilities to non-residents.
   - `bank_other_liabilities` = commercial banks' liabilities − NRI deposits.
   - FPI debt: I_GSEC = Σ over central, T-bills and SDLs of Δ(T107 FPI share × outstanding); I_CBND = BoP FII debt − I_GSEC.
   - The two reconciliation lines = NAS items 17 / 16 − Σ of the lines on that side.
9. **Satellites.**
   - `row_property_income` must equal the R13/R14/R14a entries row for row.
   - `row_financial_counterparts`: I recomputed the FLA t8 equity and debt keys, the ECB split, the F51 ODI key and the T107 SDL part. ECB is split by NIC 64 financial-services registrations / all registrations, ECB + RDB, both routes, 2023-24 = 30.73%.
   - S3 shares are re-normalised from 99.80 and multiplied by R11.
   - `r11a_sensitivity`: hub-neutral puts Maharashtra and Delhi at their share of all-India HCES consumption; consumption-only puts every State at its consumption share; the band is min/max. `r12a_sensitivity`: BoP 1.C.1.2 debit 29,820 goes on all 10 groups by `pfce_total`, the rest on H_U4/H_U5.
   - S1: US$ totals must equal IMTS World, and rupees = US$ × `t133.usd_fy_average` / 10.
   - S2: category totals must equal BPM6 1.A.b.1..13, and the USA/UK/Canada SI export shares must equal the ITES survey.

## 2. What was checked, and the value counts

| Check | Count | Result |
|---|---:|---|
| Entry values (census) | 81 / 81 | all within ₹1e-6 crore (max 4.9e-7) |
| Entry metadata: status, role, confidence, tol_rel, bop_function, record status = entry status | 81 | all as the plan (s.2, s.8) prescribes |
| Signs | 81 | positive except the five published negative net flows (short-term trade credit −6,741; rupee debt service −597; banks' foreign assets −1,28,732; the two reconciliation lines −1.48 / −110.63) |
| Constraint targets, selections, filters, kind, tolerance | 14 / 14 | all match; all hold on the assembled prior (≤ ₹1) |
| Check targets re-read from clean data | 20 of 29 (the other 9 are re-derived in `test_official_totals_and_bop_type_totals`) | all match; all 29 `ok` |
| Official totals and BoP type totals | R11, R12, R13, R14 + R14a, R14a, the 5 debit types, the 5 credit types, K5 = −CA surplus, K5 + BoP CA = BoP 1.C.2, K8b = NAS 17 / 16, NAS net lending = −(BoP CA + KA), BoP 3.1.A / 3.2.A / 3.1.B, E&O, K8c = FSF = four quarters, D2 = SUT imports − imports after CIF, P6 + D2 = NAS imports | all within ₹1 (BoP whole-crore rounding) |
| R_ROW and K_ROW closure over all 8 built blocks | 2 | R_ROW −0.0004, K_ROW 0.000001 |
| Satellites | row_property_income 41, row_financial_counterparts 41, s3 54, r11a_sensitivity 50, r12a_sensitivity 40; S1 and S2 totals (4 + 26) and the 3 ITES shares | all match |
| Provenance: inputs resolve (clean or SAM), official records over official inputs only, key records cite the clean records I used | 47 records | all resolve; V-ROW-1, V-ROW-2 |

**Plan conformance (docs/phase2/plans/rest_of_world.md, including s.8).**
- **XR-4 / D2-7 (E_RBI split).** Implemented as specified.
- **XR-12 (FPI interest).** Implemented with fincorp's formula, including re-issue netting: 12,721.29 + 123.49 + 166.17.
- **XR-13 (no FISIM on RoW property income).** Stated in the method texts.
- **XR-14.** government's K6 RoW entries net to NAS −7,110.25.
- **No R15.** No block writes an R15 entry.
- **D2 = SUT CIF (D2-3).** As specified.
- **Trade credit → I_OTHR.** As specified.
- **E_BANK ≡ ODC (XR-6).** As specified.

The block does not follow the plan body word for word in these places, and each departure is logged in the issues file:
- F3 is dropped from the R13 OI key (rest_of_world-5).
- The optional E_NFPU carve-out is not done (-12).
- S1 uses no monthly FX conversion (-21).
- S2 applies the ITES override for single-country regions only (-22).

**Double counting (all built blocks' `*_entries.parquet`).**
- No other block writes any (row, col) cell of this block.
- The only other blocks that touch R_ROW or K_ROW are production (P5, P6), factors (V3, V4) and government (K6).
- fincorp writes nothing on R_ROW or K_ROW.
- The X_DISC column holds only D2 (here), D3 and D4.
- I_RESV appears only in this block's K8c and K8b `reserve_assets`.
- capital_financial's K7b `row_cp_*` entries equal `row_financial_counterparts` one to one. The exceptions are the `reserve_assets` line, which is K8c here, and the three `unallocated_k9` lines.

## 3. Findings

| # | Severity | Finding | Evidence | Proposed fix | Status |
|---|---|---|---|---|---|
| V-ROW-1 | minor | **Wrong provenance input.** The record `sam_rest_of_world:fda06d79a3ac`, behind `r11a_sensitivity`, lists the R12a record `e816e0358b19` as an input instead of the R11a record `46590e3f1880`. | `_current.py` stores `pid` in `out.memo["r11a_inputs"]` only after the R12a `ctx.prov` call has rebound `pid`. The satellite's values are right; only the lineage is wrong. Strict xfail `test_r11a_sensitivity_record_cites_the_r11a_record`. | Store the R11a record id in the memo right after its `ctx.prov`, or use distinct variable names. Rebuild, then fincorp and capital_financial (the provenance hash changes). | OPEN (builder) |
| V-ROW-2 | minor | **Unformatted placeholder in a method text.** The S1 record `sam_rest_of_world:c8c1cd352528` says "UN Comtrade FY ({c.COMTRADE_FY})" literally. | One segment of the method string in `_trade.py` (about line 321) lacks the `f` prefix. A reader cannot tell which dataset was used; it is `trade_satellites_comtrade_fy_2324`. Strict xfail `test_method_texts_have_no_unformatted_placeholders`. | Add the `f` prefix. | OPEN (builder) |
| V-ROW-3 | minor | **The Union's SDR income has no owner.** The Union Finance Accounts show "Interest on SDR holdings received from IMF" of 5,411.10 (`fa8.0049.03.115`). government leaves it out of R7x as "RoW, rest_of_world R13" (government-5). This block puts all BoP reserve-asset income on E_RBI and gives G_CEN ← R_ROW only 959.60 (OI 646.97 + other primary income 312.64). The same doubt applies to the reserve-asset **debit** of 7,118 on E_RBI, which is probably charges on SDR allocations (rest_of_world-13, fincorp-1: it is why fincorp's `k2a.rbi_cash_basis_evidence` check misses by 7,120). | Both blocks name the other as owner; rest_of_world-3 lists SDR interest only as an unverified candidate. Balancing cannot move money between E_RBI and G_CEN cells, so the choice made now fixes the result. | Orchestrator decision. One option: an R13 G_CEN `sdr_interest` component from `fa8.0049.03.115` (derived, anchored about 10% for cash vs accrual), carved out of `reserve_income_unexplained` (25,645.50 → 20,234.40); and decide the payer of the 7,118 debit with fincorp. Otherwise, record in both issues files that G_CEN's SDR income sits inside E_RBI's reserve income by choice. | OPEN (orchestrator; rest_of_world, government, fincorp) |
| V-ROW-5 | minor | **The block is stale on households.** Another agent rebuilt households at 23:01, after this block's 22:34 build. | `hh_keys` `pfce_total` changed, so R12a would now be H_U4 34,921.92 and H_U5 64,990.89 instead of 34,920.14 and 64,992.67 (±1.78). The R12a and R12a-sensitivity records cite `sam_households:4d87a15befc1`, which no longer exists, so the audit test's input resolution fails until the block is rebuilt. The R11a key (`hh_state_xwalk`) did not change the R11a values. The verifier tests skip only the household-keyed checks while the block is stale and say so. | Rebuild in this order: `sam rest_of_world`, then fincorp and capital_financial. This is the builder's first remaining-integration item. | OPEN (orchestrator / builder) |
| V-ROW-4 | info | **Broken table in the issues file.** In `docs/phase2/issues/rest_of_world.md`, a blank line separates row rest_of_world-25 from the table above, so that row is not rendered as part of the issues table. | Line 35 is blank. | Delete the blank line. | OPEN (builder) |

Observations, not defects:
- **E_RBI `reserve_asset_income` is labelled `derived`**, although it is the sum of two published AR lines, which the guide would allow to be `official`. `derived` is the more cautious label, and the entry is anchored at 2% either way, so no change is needed.
- **Payer and recipient keys.** The per-account split of R13, R14 and R14a rests on stock keys (FSF, FLA, RTP) whose weaknesses the builder logs (rest_of_world-4 to -13). I recomputed them as specified; I did not judge whether they are the best keys.
- **Band vs prior for R11a.** For H_R1–H_R3 the prior sits at the bottom of the band (rest_of_world-1); that is a matter for Checkpoint B.
- **Other primary income on government.** R14 `other_primary_income` on G_CEN (1,190.19) and G_STA (4.66) falls inside fincorp's Union and State interest-payer bands (fincorp-8). This is harmless while the bands hold (3% / 1%).

## 4. Tests

`tests/verify/test_sam_rest_of_world_spotcheck.py` (marks `quality`, `sam`):

- **Values:** `test_entry_census_every_value`, with the staleness guard `test_dependencies_not_stale` (V-ROW-5).
- **Entry metadata and signs:** `test_entry_metadata_roles_status_confidence_tags`, `test_signs`.
- **Totals and constraints:** `test_official_totals_and_bop_type_totals`, `test_fpi_debt_split_and_sebi_crosscheck`, `test_constraints_census`, `test_checks_targets`.
- **Closure and double counting:** `test_r_row_and_k_row_close_on_the_prior_of_all_built_blocks`, `test_no_double_counting_with_other_blocks`.
- **Satellites:** `test_row_financial_counterparts_keys`, `test_row_property_income_mirrors_the_entries`, `test_s3_remittance_sources`, `test_r11a_sensitivity_variants` (with per-capita monotonicity), `test_r12a_sensitivity_variant`, `test_s1_s2_totals`.
- **Provenance:** `test_provenance_inputs_resolve_and_status_honest`.
- **Strict xfails:** V-ROW-1 and V-ROW-2.

The closure and double-counting tests read every built block. They must be re-run after any rebuild of production, factors, government or capital_financial.
