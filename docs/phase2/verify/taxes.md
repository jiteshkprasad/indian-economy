# Verification: the `taxes` block (SPEC s.3 rule 3)

Verifier: an independent agent (not the taxes builder or integrator), 2026-09-30.

Scope: the taxes block only. That covers the refs P7a, P7b, P9a, P10a, T1, T1a, T2, T2x, T3, T3a, T4, T4a and S7, and the eight satellites. I recomputed every entry, every constraint target and the recomputable satellite rows from the clean Parquet with DuckDB SQL, plain Python and numpy. I did not import or call the builder's code (`pipeline/sam/blocks/taxes/`) or any `pipeline.sam` module. I read the builder's code only to locate the choices its method text leaves open, and I list those choices under V-TX-4.

Regression test: `tests/verify/test_sam_taxes_spotcheck.py`. It gives 22 passed and 3 strict xfails (V-TX-1, V-TX-2, V-TX-3). It does not import `pipeline.sam` or polars.

Outputs checked: the build of 2026-09-30 23:07:02 (`taxes_*`). It was built against production (21:37), households (23:05) and factors (23:07:01). The dependency hashes recorded in `taxes_block.json` match the current files, so the block is **not stale**. The test re-checks this every time it runs.

## Verdict

**Every number is right. Four small fixes are recommended (V-TX-2 to V-TX-5), and one split (V-TX-1) should be revisited at Checkpoint B.**

Every number the block writes matches my recomputation:
- **Entries:** all 180 match (a census). The largest difference is 4.2e-5 crore, on (T_SVAT, C_RPET), which is RAS convergence noise. 84 entries are at or above Rs 10,000 crore, and all of them are in the census.
- **Constraint targets:** all 22 match (a census). The largest difference is 4.0e-7.
- **Satellites:** every recomputable row matches, in all eight satellites.
- **Checks:** all 16 control-total checks pass.
- **Provenance:** all 25 records resolve.

Totals:
- The block closes to its official totals:
  - SUT product taxes by commodity and in total (30,15,341.40);
  - the NAS 1.1 taxes and subsidies on products (P7a + P8 + P9 is 0.52 below NAS, which is SUT-vs-NAS rounding);
  - the SUT P9 and P10 totals;
  - the Receipt Budget corporation tax and taxes on income;
  - the RBI State Finances taxes on income.
- All 12 tax accounts close on the assembled prior of the eight built blocks, to within 1e-3.
- No other block writes a tax-account cell except production's P8, P9 and P10, as designed.

The block's product-tax and income-tax receipts reconcile to the budgets to the rupee:
- **Union:** the SAM Union tax receipts (T1a) are 34,84,646.27. Receipt Budget gross tax revenue, before devolution and before the NCCD transfer to the NDRF, is 34,65,518.58. The difference is +19,127.69, which splits exactly as follows:
  - +20,427.27: the TAX-1 scaling of the Union's product-tax rows (x1.015965);
  - −887.82: SUT import duty against cash customs less export duty;
  - −411.76: UT stamps and land revenue, which are booked in P10a rather than T1a.
- **States:** the SAM State tax receipts (T2x) are 17,23,274.91. This equals App I own-tax revenue (19,50,836.23), less the property and capital heads booked in P10a (2,54,517.16), plus the TAX-1 scaling (+26,955.83), to within 0.002.
- **Consequence:** no tax head is counted twice, and none is missing, on either government's side.

What needs attention (all minor):
- **V-TX-1:** the public/private split of the E_BANK corporation tax. The builder already flagged this in taxes-10; I quantify it.
- **V-TX-2:** a status label that is not honest, on four `p10a_items` rows.
- **V-TX-3:** a confidence label that is too high, on one P7a cell.
- **V-TX-4:** three parameters used in the code are not stated in any method text or issue.
- **V-TX-5:** the issues file is slightly out of date.

## 1. Method (what I recomputed, and how)

1. **Cash receipts.** I read every head from `union_fiscal_rb_receipts` (vintage 2025-02-01, actuals 2023-24) and `state_fiscal_rbi_sf_appendices` (App I, all States + UTs, vintage 2026-01-23), then mapped them to the seven product-tax accounts:
   - **T_CGST** = MH 0005 + MH 0008 + UTGST MH 0007 = 8,21,268.82.
   - **T_SGST** = App I SGST, 8,41,120.77.
   - **T_GCES** = MH 0009, 1,41,436.16.
   - **T_UEXC** = total Union excise, 3,05,362.18.
   - **T_SVAT** = App I sales tax + UT sales tax, 4,07,896.69.
   - **T_SEXC** = App I State excise + UT excise, 2,59,579.95.
   - **T_OPRT** = App I vehicles, goods and passengers, electricity, entertainment and other taxes, plus Union UT vehicles, goods and electricity, service tax (MH 0044), MH 0045, export duty net and CTT: 1,91,293.73.
   - The cash total is 29,67,958.30.
   - Identities I checked:
     - TAX-4 holds;
     - Receipt Budget gross = Finance Accounts net + minor head 901, for MH 0005, 0020, 0021, 0037 and 0038;
     - RB "total taxes on income" = MH 0021 + STT + MH 0023/0024/0026 + MH 0028.
2. **P7a column targets.** I summed the SUT `supply.product_taxes.sut_pNNN` series with `io_tables_sut_product_to_sam34.csv`:
   - the result equals production's 34 `product_taxes.*` targets within 1e-6;
   - C_DWEL and C_PADM are 0;
   - the total is 30,15,341.397664 (the SUT total).
3. **P7a prior.** I rebuilt it at SUT-product level from the P7a record's method text, placing the heads in this order:
   1. PPAC excise, VAT, entry tax/octroi and GST on p085.
   2. PPAC cess + NCCD on crude on p043/p044, pro rata to their SUT tax. The SUT's C_OILG tax equals PPAC cess + NCCD to the rupee (confirmed).
   3. Union excise other than PPAC on p069 tobacco: 10,906.99.
   4. State excise on p065, up to its SUT tax. The excess (25,903.18) is the licence fee, placed on p134/p132.
   5. Electricity duty on p128.
   6. Vehicle tax on p120–p122, by PFCE + GFCF.
   7. The rest of T_OPRT on their stated bases.
   8. Non-POL VAT, pro rata to the room left on p065/p043/p085. All of it lands on p085.
   9. MH 0044 + State other taxes, less PPAC entry tax/octroi, over the GST residual.
   10. Compensation cess: 0.5 x the GST residual on p064/p066/p069/p120, and the rest on the other GST products except coal.
   11. CGST : SGST in the ratio of their row targets.

   I then aggregated to commodities. Exactly one prior cell falls below Rs 0.001 crore and is dropped: (T_OPRT, C_OILG) 0.00017, as logged in taxes-6. My aggregated prior equals the block's `p7a_precheck` item priors to 1.7e-4, and that residual is the dropped cell.
4. **P7a fit.** I wrote my own RAS, which updates columns first (the builder updates rows first). The row targets are cash x (SUT total / cash total) = x1.0159648809. The column targets are production's. The fit converges to 1e-12. Because the scaled rows are feasible on the prior's pattern (the RAS converges), the pre-check moves nothing, as the block reports. All 136 P7a cells match.
5. **T1a/T2x.** Each P7a row total is split by each government's cash share, with T_CGST split into `total` (CGST + IGST) and `utgst`. The other entries:
   - G_CEN ← T_CUST = Σ production P8 (2,28,887.27);
   - G_CEN ← T_PIT = RB taxes on income + MH 0031/32 (10,44,763.68);
   - G_CEN ← T_CIT = 9,11,055.01;
   - G_STA ← T_PIT = App I taxes on income (7,873.82).
6. **T3.** The household share h = (old-base s5_0 household D5 2022-23, 6,42,596.29, − FC16 State accounts MH 0028 2022-23, 7,751.98 from 19 States) / RB MH 0021 2022-23 (8,08,221.32) = **0.785483**. The IFPRI cross-check gives 0.901733. From this:
   - the quasi-corporate part = (1 − h) x MH 0021 2023-24 + MH 0023/0024/0026 = 2,16,881.03;
   - of that, 1,620.00 (UCB tax provisions, RTP 2025-12-29) goes to E_BANK and 2,15,261.03 to E_NFPR.
7. **T3a.**
   - For each HCES class in households' `hh_group_map`: Y_f = 12 x MPCE x persons/households x k / (1 − s_g). Here k = NAS PFCE / HCES aggregate = 1,64,15,546.52 / 72,74,443.99 = **2.2566**, and s_g is the IFPRI T11 rate weighted by persons over households' `hh_national_quintile_xwalk`.
   - The key is Σ households x max(0, Y − 7 lakh). Shares:
     - U5 46.66%, R5 25.98%, U4 17.93%, U3 8.45%, U2 0.99%;
     - R1–R4 and U1 are exactly 0, so they get no entry.
   - Income tax = key x (h x MH 0021 + STT + MH 0028 + MH 0031/32) = key x 8,27,882.65.
   - Professions tax = App I taxes on income x factors' F1a (F_LREG) shares.
   - The 5 lakh and 10 lakh sensitivity keys match `t3a_sensitivity` to 1e-8.
8. **T4a.**
   - Old-base 2022-23 D5 shares (s2_1/s2_2/s3_1/s3_2) are applied to CIT + the quasi-corporate MH 0021 (11,27,936.04). The quasi-corporate part is then removed from private NFC and private FC.
   - E_INSP = IRDAI tax provisions (life t24 + t25, non-life t51 four groups). Public = LIC + public + specialised general insurers.
   - E_NBFC = RTP (2025-12-29) NBFC-UL + ML + HFC + AIFI, less the deposit-taking share, which moves to E_BANK. That share is FSF end-March 2024 assets: NBFC 0.157953, HFC 0.729555, moving 6,659.18. Public = AIFI + the old-base public FC ratio on the rest.
   - E_BANK is the residual.
   - All 8 cells match. They sum to CIT exactly.
9. **P9a.** I applied the commodity-by-commodity payer map to production's P9 entries:
   - C_CHEM, C_TREQ, C_RPET: Union.
   - C_UTIL, C_LVST, C_FOFI: States.
   - C_CROP: Union takes PM-AASHA; the rest goes to States.
   - C_FINS: Union takes MISS; the rest goes to States.
   - C_TRNS: Union takes SUT p137 air; the rest goes to States.
   - C_TRAD: States take the FC16 food subsidies of 21 States first (54,463.39).
   - The unexplained rest is split at the identified Centre share, **0.459980**.
   - Result: G_CEN −2,65,142.52, G_STA −3,11,279.91.
10. **P10a.** Gross D39 = NAS 4.2 GG subsidies 9,18,559.13 − NAS 1.1 product subsidies 5,76,422.38 = 3,42,136.75. Gross D29 = D39 + P10 (−57,441.998622) = 2,84,694.75. The identified heads (RB and App I; cityfinance ULB property tax) leave `other_production_taxes` = 383.60. Union gross subsidies (1,09,907.78) are:
    - PM-KISAN (FA 2401.00.130);
    - St 7 interest subsidies less MISS and less the LIC pension subsidy;
    - St 7 other subsidies less PM-AASHA;
    - FC16 Union "business".

    The States take the residual.
11. **Constraints.** I recomputed all 22 targets from the same numbers, and every one of the block's constraints holds on the block's own entries. Production's 32 non-zero `product_taxes.*` constraints hold on the P7a columns to 1e-6.
12. **Satellites.**
    - `p7a_precheck`: the row and column rows, and the final/cash ratio 1.015965 for all seven accounts.
    - `p7b_tax_by_use`: the uses of each parent add up to the P7a entry, for all 136 parents. Every row is positive. There are no GST, cess, excise, VAT or State-excise rows on exports. GST and cess on IC fall only on the non-ITC list (plus A_BVTB), on GFCF only for C_CNST/C_TREQ, and never on CII. T_OPRT export rows (3,323.4) are exactly the export-duty items.
    - `p9a_by_commodity`: all 27 rows.
    - `p10a_items`: all 14 rows.
    - `direct_tax_split`: all T4a cells, the shares and the details.
    - `t3a_sensitivity`: all 55 rows.
    - `s7_igst_settlement`: all 49 rows equal their FA St 8 / PIB source series.
    - `tax_classification`: all 23 values.
13. **Provenance.**
    - Every input of the 25 records resolves in data/clean or in a block's provenance.
    - Official records have only official inputs.
    - The status of every entry, constraint and satellite row equals its record's status.
    - Every check's `target_prov_id` resolves.
    - The T4a record cites the RTP 2025-12-29 records, not those of 2024-12-26.
14. **Double counting.**
    - No block other than production writes a T_* cell.
    - Government has no R16 entry (vehicle tax is a product tax, D2-4).
    - Government has no vehicle, professions-tax, PM-KISAN or STT component.
    - LPG: government R10 `lpg_dbt` totals 9,960, which is St 7 LPG 12,240 − SUT P9 on C_RPET 2,280. So LPG is booked once.
    - There is no State food component in government's C2a (XR-23).
    - The LIC pension subsidy sits in government R18 and is excluded from P10a.
    - Stamps, land revenue and property tax appear only in P10a. Professions tax appears only in T3a/T2x.
15. **Plan and decision compliance.** I checked the block against plan s.2 and s.3:
    - its s.8 items: XR-6, XR-15 (taxes-22), XR-19 component names, XR-20 component constraints, XR-23;
    - DECISIONS D2-4, D2-11, D2-12, D2-14 and D2-17.

    It follows them all. Two documented deviations were logged by the builder:
    - taxes-4: cess on crude placed on p043/p044;
    - taxes-11: FC16 food not grossed up, because no all-State series exists.

## 2. What was checked (value counts)

| Object | Count | Coverage | Result |
|---|---:|---|---|
| Entries | 180 | census (84 are ≥ Rs 10,000 crore) | all match; max \|diff\| 4.2e-5 |
| Constraint targets | 22 | census | all match; max \|diff\| 4.0e-7 |
| Constraints holding on the block's entries | 22 + 32 production `product_taxes.*` | census | all hold |
| Satellite rows | 1,721 p7b + 403 p7a_precheck (rows, columns, aggregated item priors) + 27 + 14 + 36 + 55 + 49 + 23 | all recomputable rows | all match |
| Checks | 16 | census | all pass |
| Provenance records | 25 | census | inputs resolve; statuses consistent |
| Tax accounts on the assembled prior | 12 | census | all close to < 1e-3 |

## 3. Findings

| id | Severity | Finding | Evidence | Proposed fix |
|---|---|---|---|---|
| V-TX-1 | minor | **The public/private split of E_BANK's corporation tax does not match the 2023-24 profit evidence.** The block gives public banks 17,353.19 of E_BANK's 1,32,700.49 (13.1%). PSBs earned 40.4% of SCB net profit in 2023-24 (RTP `rtp.scb_pl.net_profit.psb` 1,41,202 / `scb` 3,49,603), which would put about 53,600 on public banks. The split is an arithmetic residual: old-base public-FC D5 share (3.18% of corporate D5, 35,863) less LIC and public general insurers (7,462) less AIFI-led NBFC public (11,048). No constraint touches the components, so balancing will keep the prior proportions. This feeds fincorp's public/private FC saving (F4a/K2a) by about 36,000. The builder logged the cross-check (taxes-10) but did not reconcile it. | `test_v_tx_1_…` (strict xfail): public share 0.131 vs PSB profit share 0.404 | Split the E_BANK residual public/private by RTP net profit (PSB + RRB vs private, foreign, SFB and payments banks), or add a band constraint on the `public` component around the profit-share figure. Flag it at Checkpoint B together with taxes-10. |
| V-TX-2 | minor | **A status label is not honest.** In `p10a_items`, the four Union subsidy rows get `status` from the sign of the value (`estimated` if negative). Two of them are published numbers as published: `pm_kisan` 51,616.91 (FA 9 2401.00.130) and `fc16_union_business` 52,325.27. The other two are differences of published numbers: `interest_subsidies_other` 5,128.93 and `other_subsidies_other` 836.67. They should be `official` / `derived`. The P10a entries themselves are labelled correctly: the `gross_subsidies` entries are a classification estimate. | `test_v_tx_2_…` (strict xfail) | Give the item rows the status of their inputs: a `derived` record over the St 7/FA/FC16 records, not the estimated P10a subsidy record. |
| V-TX-3 | minor | **A confidence label is too high.** (T_SVAT, C_RPET) = 4,14,408.71 is `free/high` (weight 4). Of its prior (4,07,896.69), 1,15,180.28 (28.2%) is non-petroleum VAT (CST, other receipts, liquor, gas, ATF) that the plan's fallback (b) forces onto POL for lack of room elsewhere (taxes-3), not VAT on POL. The plan table gives "high" to petroleum excise/VAT on C_RPET, meaning PPAC-backed amounts. | `test_v_tx_3_…` (strict xfail) | Make the cell `medium`, or split it into components `ppac_vat_pol` (high) and `non_pol_vat_fallback` (low) so that balancing can move the fallback part more cheaply. |
| V-TX-4 | minor | **Three parameters are not stated in any method text or issue ("no silent defaults").** They are all immaterial to the totals: (a) the export-duty base is SUT products p001–p126 *that carry SUT product tax* (`GOODS_MAX = 126`); (b) PPAC IGST on POL (20,929.70) is split between the CGST and SGST priors in the ratio of their row targets; (c) PPAC `centre.a.others` (51.50) is not used. Only (a) and (b) shape the prior. A related wording point: taxes-3 calls the 46,834.00 GST prior on C_RPET "PPAC CGST + SGST + IGST". But PPAC's three heads total 45,448.38, and the other 1,385.62 is the GST residual of the other C_RPET products. | code `p7a.py` vs the P7a record's method text | Add one sentence to the P7a method text and one line to the issues file's Assumptions. |
| V-TX-5 | minor | **The issues file is slightly out of date.** The integration paragraph says factors is still stale and that taxes must be rebuilt once more. The current build (23:07:02) is against factors 23:07:01, and the hashes match, so the block is current. The prior-imbalance table has also drifted a little since households was rebuilt: H_U5 is now −1,19,609 (the file says −1,20,729), and without T3a it would be +2,68,397 (the file says +2,67,277). The conclusions do not change. | `taxes_block.json` dependency hashes; assembled prior | Refresh the paragraph and the table at the next rebuild. |

## 4. Observations (checked, no finding)

- **Low-confidence cells.** These are the plan's own fallbacks, and the builder logged each one:
  - GST on POL is squeezed to 0.38 x the PPAC prior;
  - Union excise on tobacco is doubled (10,906.99 prior → 22,141.14);
  - the licence-fee excess grows to 30,861 (taxes-2, taxes-3).

  All three are consequences of the SUT column margins (C_RPET 7,00,419; C_BVTB 3,10,390). The RAS reproduces them exactly, and they are free entries that balancing may move.
- **Compensation cess.** 46% of it (65,908) lands on C_TREQ and none on coal, because the SUT's coal product tax is only 3,062 (taxes-5). In the real world coal carries a large share of the cess. The SUT evidently does not book it on coal, so this belongs with the TAX-1 NAD questions, not with a fix here.
- **T3a threshold.** The key applies the Rs 7 lakh threshold to household income, while the rebate limit applies to individual taxpayers. So multi-earner households are over-weighted. This is stated in the record and is low confidence (taxes-8). The H_U5 deficit (taxes-23) is confirmed: factors' F1a totals for U4/U5 are 17,53,950 / 17,53,742, against a PFCE ratio near 1.9.
- **D29 room.** Gross D29 has almost no room after the identified heads (383.60 left). This supports D2-4 (vehicle tax is not D29) and plan C4 (professions tax is not D29), with the ULB-coverage caveat in taxes-13.
- **Staleness.** The block is not stale: every recorded dependency hash matches the current files. The test xfails, and does not fail, if a later rebuild of production, households or factors makes it stale.
- **Other test failures.** A hygiene failure is present in the suite at `pipeline/sam/blocks/households/__init__.py:96`. It belongs to another agent's in-progress edit, not to taxes.
- **Full offline suite (2026-09-30, end of this verification).** 3,929 passed, 11 failed, 56 skipped, 27 xfailed. None of the 11 failures are in taxes files:
  - hygiene: `households/__init__.py:96`;
  - `test_sam_framework`: the broken-sibling test (FR-factors-1);
  - eight `test_sam_factors_spotcheck` tests: factors was rebuilt at 23:07, which belongs to the factors verifier;
  - the solver-certificate proximal-fallback determinism test.

  `tests/verify/test_sam_taxes_spotcheck.py`: 22 passed and 3 strict xfails.

## Re-verification (wave C close-out, 2026-10-01)

Verifier: an independent agent that wrote none of the wave C changes (SPEC s.3 rule 3). Scope: the wave C audit fixes of `docs/phase2/issues/taxes.md` "Wave C audit": BS-5 / taxes-28 (PM-KISAN out of P10a), BS-10 / taxes-29 (`t4a.nfpu` band), BS-9 / taxes-30 (no change to the block; edges reproduced), and every expectation the fixing agents changed in `tests/verify/test_sam_taxes_spotcheck.py`. Outputs checked: the taxes build of 2026-10-01 05:40 (`taxes_entries` sha256 f913e50a..., `taxes_constraints` 0a16940..., the hashes the balanced run `balancing_run.json` records, so the balanced SAM is built on exactly these outputs). I recomputed with my own DuckDB SQL and Python from data/clean and the dependency outputs (production P10 entries, government entries, the balanced run); I did not import `pipeline` or the test file's helpers.

### Verdict

**Every changed number is right, and the reclassification is consistent with the evidence. Three minor findings (V-TX-6..8): one band that ignores evidence already in clean data, one stale finding whose gap the fix widened, and one method text that states an inference as a fact.** Nothing was forced to make a number land: the new band `t4a.nfpu` is centred on the unchanged prior and binds openly at its edge, and the PM-KISAN move leaves gross D39, gross D29 and P10 (= NAS 7.1) unchanged.

### What I recomputed (27 own checks, all pass)

| Object | Recomputed | Result |
|---|---|---|
| P10a entries | all 8 (G_CEN stamps 393.94, land revenue 17.82, gross subsidies -58,290.87; G_STA stamps 2,28,154.975, land revenue 24,099.605, property tax 31,644.81, other production taxes 383.60, gross subsidies -2,83,845.88) | all match (max diff 6e-11); sum = production P10 -57,441.998622 |
| Union identified D39 heads | St 7 interest subsidies 19,515.82 - MISS 14,251.93 - LIC pension 134.96 = 5,128.93; St 7 other 3,036.67 - PM-AASHA 2,200 = 836.67; FC16 Union 'business' 52,325.27; total 58,290.87 (was 1,09,907.78 with PM-KISAN 51,616.9074) | match |
| States' D39 residual | NAS 4.2 GG subsidies 9,18,559.13 - NAS 1.1 product subsidies 5,76,422.38 = 3,42,136.75, less 58,290.87 = 2,83,845.88 (was 2,32,228.97; +51,616.91 exactly) | match |
| Constraint targets | `p10a.centre_net` -57,879.11 (band 30%), `p10a.gross_subsidies` -3,42,136.75, `p10a.gross_taxes` 2,84,694.75, `p10a.net` -57,442.00, `t4a.nfpu` 75,259.09 (band 25%, = `t4a.fc`'s tolerance, prov = the T4a record) | all 5 match |
| T4a E_NFPU | (CIT 9,11,055.01 + (1 - h) x MH 0021 + MH 0023/24/26) x old-base 2022-23 public NFC share 0.0667228 = 11,27,936.04 x 0.0667228 = 75,259.09; h = 0.785483 | match |
| `p10a_items` | all 13 rows (14 before; `pm_kisan` gone); statuses official (FC16 business), derived (St 7 differences), estimated (the two entry rows) | match |
| `tax_classification` | `pm_kisan` 51,616.9074, ref `none`, cell `government R10 H_* <- G_CEN {pm_kisan}`; 23 rows | match |
| Double counting | PM-KISAN appears once in all block entries: government R10 `pm_kisan` (10 household entries, G_CEN) = 51,616.9074 = FA St 9 2401.00.130; not in any taxes entry or `p10a_items` | confirmed |
| Provenance | P10a subsidy record (`b25834524312`) no longer cites FA St 9 and its method text describes the new heads; the official record `1964b1ae7819` now has FC16 only; the classification record cites FA St 9 | consistent |
| Balanced run (taxes-29/30 claims) | G_CEN <- T_CGST 8,62,332.26, T_GCES 1,48,507.97, T_UEXC 3,20,630.29 (each +5% of cash, binding); SGST 8,29,319.98 (-1.40% of cash 8,41,120.77); E_NFPU 94,073.86 (+25%, binding); E_NFPR 6,38,727.91 (-2.59%); `p10a.centre_net` -40,515.38 (the +30% edge, binding), G_CEN gross subsidies -40,929.42; G_CEN prior imbalance -2,97,655.41 | all as reported |
| Explanations (`pipeline/sam/explanations/taxes.yaml`) | 23 items, 6 "Explained", 17 "Explained in direction; level unexplained"; every item's prior and balanced value equals the balanced run | match |

The evidence behind the PM-KISAN move, rechecked: NAS 4.2 GG current expenditure 46,69,538.88 = consumption 27,45,349.53 + subsidies 9,18,559.13 + current transfers 10,05,630.22 (diff 0.0025), so subsidies and current transfers are disjoint in NAS 4.2; COFOG 04.agri current transfers are 58,325.32, which can hold PM-KISAN (51,616.91 = 88.5%); and SNA 2008 treats an unconditional per-family income support as a current transfer to households, not a subsidy on production. The reclassification is sound. FC16 Union 'business' (used) is distinct from FC16 Union 'agriculture' (88,641.24, not used), so the remaining Union head does not also carry PM-KISAN.

### Test file: expectations the fixing agents changed

The file is untracked, so I compared it with this report's section 1 and the maintainer's documented V-TX edits.

| Changed expectation | My recomputation | Kept / reverted |
|---|---|---|
| `p10a()`: the Union `items` no longer include `pm_kisan` | Union heads 58,290.87, States -2,83,845.88 | confirmed, kept |
| `expected_constraints()`: `t4a.nfpu` = the E_NFPU cell | 75,259.09 | confirmed, kept |
| `test_double_counting_guards_with_government`: R10 `pm_kisan` = FA 2401.00.130 and not in `p10a_items` (replaces "no PM-KISAN component in government") | 51,616.9074, booked once | confirmed, kept |
| `test_s7_and_classification_satellites_are_as_published`: `pm_kisan` listed explicitly (it used to come from `p10a()["items"]`) | 51,616.9074, 23 rows | confirmed, kept |
| `test_v_tx_2_...`: `"pm_kisan" not in st` (was `official`) | the row is gone | confirmed, kept |
| Earlier maintainer edits (V-TX-1..3, 2026-09-30): E_BANK split by RTP net profit; `non_pol_vat`; 181 entries; three former xfails | bank share (1,41,202 + 7,571) / 3,57,209 = 0.416487, public 1,26,041.31 x 0.416487 = 52,494.60; `non_pol_vat` 1,15,180.28 x 1.0159649 = 1,17,019.12 and `total` 2,92,716.41 x 1.0159649 = 2,97,389.59 | confirmed, kept |

Added (by me): `test_wave_c_reverification_p10a_without_pm_kisan`, `test_wave_c_reverification_t4a_nfpu_band` and `test_wave_c_reverification_balanced_edges_as_reported` (it xfails if the balanced run predates the taxes build). One lint fix (`kind` -> `_kind`, an unused loop variable). Result: `tests/verify/test_sam_taxes_spotcheck.py` 28 passed; `pipeline test -k taxes` 71 passed. The only failure in the hygiene suite is `pipeline/sam/blocks/households/__init__.py:96` (not taxes).

### Findings

| id | Severity | Finding | Evidence | Proposed fix |
|---|---|---|---|---|
| V-TX-6 | minor | **The `t4a.nfpu` band (BS-10) is a typed tolerance, though clean data hold evidence for one.** It is +-25% of the 2022-23 old-base public NFC share of corporate D5 (6.67%), copied from `t4a.fc`, and the balanced value sits on its upper edge (94,073.86 = 8.34%), so the tolerance, not evidence, sets E_NFPU's tax. The same old-base series (`oldbase_soa_s2_1..s3_2`, 2011-12 to 2022-23, already read by the block) shows that 2022-23 is the lowest of 12 years: 8.05% (2019-20), 10.42% (2020-21), 8.12% (2021-22), and 10.2-16.3% in 2011-12 to 2018-19. The audited +64% value (1,23,228 = 10.9%) is therefore not out of line with the series. The disposition of BS-9 rejects narrower GST bands because they "would be a typed number", which applies equally to this 25%. Neither the T4a record's method text nor the Assumptions list states the band. | `test_wave_c_reverification_t4a_nfpu_band` | Derive the band from the series (for example the 2019-20 to 2022-23 range, about 75,300 to 1,17,500), or state the 25% and its basis in the T4a record and under Assumptions. Take it to Checkpoint B with taxes-27. |
| V-TX-7 | minor | **taxes-24 was not refreshed, and the PM-KISAN move widened its gap.** taxes-24 still says the States' subsidies are 5,43,508.88 against RBI SF St 36 3,29,610.40 (gap 2,13,898). After taxes-28 they are 5,95,125.79 in the prior (P9a 3,11,279.91 + P10a 2,83,845.88; gap 2,65,515.39) and 6,46,222.94 balanced (gap 3,16,612.54, 1.96x St 36), because balancing then moves Union subsidies to the States up to the `p10a.centre_net` edge. The body of taxes-14 and the G_CEN/G_STA rows of the prior-imbalance table still show PM-KISAN in P10a (P10a -1,09,496.02 / +52,054.02). The fix moves the D39 total's residual further from the only State-level subsidy evidence, and no part of the wave C write-up says so. | `p10a_items`; St 36 `st36.subsidies.in.all_states_uts.actuals`; the balanced run | Refresh taxes-24 and taxes-14 and mark the table as pre-wave-C. Put the States' D39 residual against St 36 on the Checkpoint B list with taxes-13 (is NAS 4.2 "subsidy" = D31 + D39?). |
| V-TX-8 | minor | **An inference is stated as a fact, and the classification has no DECISIONS entry.** The P10a record (`b25834524312`) and the `tax_classification` treatment say "NAS 4.2 books it [PM-KISAN] in COFOG 04.agri current transfers". NAS 4.2 does not itemise PM-KISAN; the evidence is indirect (the expenditure identity, the size of 04.agri transfers, SNA). The move of 51,617 from a production subsidy (D39) to a current transfer (R10), across two blocks, is the same kind of choice as D2-4 (vehicle tax), but it is recorded only in the issues files (government-30, taxes-28). | provenance method texts; DECISIONS.md has no PM-KISAN entry | Reword to "inferred from ... (NAS 4.2 does not itemise it)". Add a DECISIONS D2-x entry with a NAD question. |

### Observations (no finding)

- BS-9: the block did not change, and every edge in taxes-30 reproduces (above). Not narrowing the cash bands is consistent with "no fabricated data", given that no settlement-timing series exists in clean data. V-TX-6 asks for the same standard on `t4a.nfpu`.
- The PM-KISAN move does not change any tax-account total: gross D39, gross D29, P10a net = P10, and the 16 checks still pass. All 12 tax accounts still close on the assembled prior (the existing census test).
- RTP payments banks: `rtp.scb_pl.net_profit.pb` (-1, used; the SCB groups then add up to the SCB total 3,49,603) differs from `rtp.pb_pl.net_profit.pb` (94). The difference is immaterial (the public share moves by less than 0.0002).
