# Verification: the `factors` block (SPEC s.3 rule 3)

Verifier: an independent agent (not the factors builder or integrator), 2026-09-30.

Scope: the factors block only. That covers refs V1a, V2a, V3, V4, F1, F1a, F2, F3, F3a, F3b, F3c, F4 and F4b, and the six satellites. I recomputed every entry, every constraint target and the recomputable satellite rows from the clean Parquet with DuckDB SQL and plain Python. I did not import or call the builder's code (`pipeline/sam/blocks/factors.py`, `_factors_lib.py`) or any `pipeline.sam` module.

Regression test: `tests/verify/test_sam_factors_spotcheck.py`. Against the 23:07 build it gives 20 passed and 5 strict xfails. Against the 22:30 build it gave 19 passed and 6 xfailed:
- five strict xfails, one each for V-F-1, V-F-2, V-F-4, V-F-5 and V-F-6;
- one conditional xfail for V-F-7, which becomes a pass once factors is rebuilt.

The test does not import `pipeline.sam` or polars.

Outputs checked: the build of 2026-09-30 22:30 (`factors_entries.parquet`), against the current production outputs and against the households outputs as they stood during the check. Households was rebuilt at 23:01 and again at 23:05, while this verification was running (see V-F-7). Another agent then rebuilt factors at 23:07 (`factors_entries.parquet` sha256 `a7a0b228…`). I re-ran the whole census against that build: every entry, constraint and satellite check still passes, and the dependency hashes are current, so the V-F-7 test now passes. V-F-1, V-F-2, V-F-4, V-F-5 and V-F-6 are still present in the 23:07 build.

## Verdict

**Every number is right. A few fixes are needed.** Every number the block writes matches my recomputation:

- **Entries:** all 227 match. The largest difference is 6.3e-6 crore (the RAS in V2a converges to that; everything else is within 5.0e-7, the 6-decimal rounding on write).
- **Constraint targets:** all 62 match.
- **Satellites:** every row I could recompute matches.

Totals:
- The block closes to the official totals: SUT CE, SUT OS/MI + CFC, NAS CE receivable, NAS 7.1C household gross OS/MI and the NAS sector GOS.
- The four factor accounts close on the assembled prior of the eight built blocks: F_LREG, F_LCAS and F_MIXD exactly, F_GOSC to −0.21. That −0.21 is fincorp's +0.22 on F4a, which is SUT-vs-NAS rounding.
- No other block writes factor cells, except fincorp's F4a, as the plan intends.

What needs attention:
- **V-F-1 (major):** the factors-3/-19 saving-profile problem, confirmed independently. It is an orchestrator decision for Checkpoint B, not a coding error.
- **V-F-2 and V-F-3:** method choices that are not documented.
- **V-F-4 and V-F-5:** two labels on satellite rows that are not honest.
- **V-F-6:** the wording error the builder already logged.
- **V-F-7:** staleness caused by the households rebuild at 23:01. The numbers are unchanged, but one provenance input now dangles.

## 1. Method (what I recomputed, and how)

1. **SUT targets.** CE, and OS/MI + CFC, by activity:
   - Source: `io_tables_sut_va` 2023-24, taking only the published-table record `io_tables:d1e9110c5674`. The dataset holds a second record per series (`edd1d843b20e`), which I excluded.
   - Aggregation: summed with `data/concordance/io_tables_sut_industry_to_sam34.csv`.
   - Result: equal to production's 34 `ce.*` and 34 `os_mi_cfc.*` targets within 1e-6. CE totals 94,42,896.46 and OS/MI + CFC 1,70,20,025.77.
2. **V1a (plan s.2.1).** For each of the 9 PLFS Table 20 groups g and each area s:
   - workers = WPR_s (ps+ss) × persons_s × Σ t26 section shares. persons_s is households' `pop_persons`, summed by area.
   - Regular bill = workers × t20 regular share × 12 × the Q1–Q4 2023-24 mean of API indicator 6.
   - Casual bill = workers × t20 casual share × w_g,s × D:
     - w_g,s is the t51 casual wage, weighted by t26 section shares. One area cell is missing (section L, urban), so it falls back to the section's all-area wage. This is logged as factors-7.
     - D = ASUSE informal emoluments per hired worker ÷ the API-7 all-India mean = 125,910 / 410.40 = **306.80 days**.
   - share_reg_g = Σ_s regular / Σ_s (regular + casual). Values: 01-03 0.1056, 05-09 0.8052, 10-33 0.9001, 35-39 0.9613, 41-43 0.1031, 45-47 0.9456, 49-53 0.8177, 55-56 0.8564, 58-99 0.9871.
   - A_PADM is 100% regular. There are no labour entries in A_DWEL, whose CE is 0.
3. **V2a (plan s.2.2).**
   - Household gross OS/MI by NAS group = 7.1C OS/MI + CFC. Transport is railways + road + water + transport services + storage.
   - Single-activity groups take the group value. Mining goes wholly to A_OMIN.
   - Manufacturing and other services use a two-column RAS, which I wrote myself:
     - rows are SUT GOS by activity; the columns are the household total and the rest;
     - the household prior is ASUSE unincorporated surplus: Σ(OAE, HWE) t4 × t37, minus t33 hired workers × emoluments per hired worker, on the plan's category mapping;
     - the rest prior is the activity's GOS.
   - Group 9:
     - household non-dwelling surplus = 7.1C group-9 CE 32,337.62 × ASUSE (GVA − emoluments)/emoluments of S7 + S10 + S11 + S12 (3.298750) = 1,06,673.70;
     - that is split between A_ITSV (S7) and A_BSRE (S10–S12) by ASUSE surplus;
     - dwellings take the rest of group 9, 18,63,447.91.
   - q_a = Σ(OAE, HWE) (t6 share of different-household partnerships + societies/trusts + co-operatives + others) × t4 × t37, divided by the categories' GVA. Then hh_quasi = q_a × the household part, and mixed income = the rest.
   - Dwellings:
     - s_imp = households' C4a imputed ÷ (imputed + actual + government housing) = 0.742769;
     - imputed = min(s_imp × GOS_DWEL, HH_DWEL) = 14,32,193.50;
     - actual = 4,31,254.42.
   - corp_gov = GOS_a − the household part.
4. **F1a (plan s.2.5).**
   - Factor totals come from V1a, plus V3 − V4 on F_LREG.
   - Each group's regular (casual) CE is split between rural and urban by that group's regular (casual) wage bills. A_PADM follows the 58-99 group; see V-F-8.
   - V3 − V4 goes pro rata to the regular rural/urban split.
   - Within an area, each household group gets persons × I_g, normalised. I_g = Σ_q xwalk_g,q × I_q, where I_q = IFPRI T10 factor share × T11 total spending per capita:
     - regular labour uses medium + high-educated labour;
     - casual labour uses low-educated labour.
5. **F2 (plan s.2.6).**
   - Farm (A_CROP, A_LVST, A_FOFI) is split between rural and urban by PLFS 01-03 workers × t20 self-employed share × 12 × the mean of API indicator 8.
   - Non-farm is split activity by activity:
     - by ASUSE surplus by area of the activity's categories;
     - mining and construction by the PLFS 05-09 and 41-43 self-employment earnings;
     - utilities by ASUSE category E (V-F-3).
   - Within an area, by the IFPRI index: crop land + agricultural capital for farm income, non-agricultural capital for non-farm income.
6. **F3a / F3b / F3c.**
   - F3a = imputed total × each group's share of households' C4a `imputed_rent` entries.
   - F3b = actual total × households' `aidis_fixed_assets` share.
   - F3c = hh_quasi, split between rural and urban by ASUSE non-proprietary GVA by area of each activity's categories, then within each area by the IFPRI non-agricultural capital index.
7. **F4 / F4b (plan s.2.8–2.9).**
   - GOS = GVA − CE − net production taxes:
     - public NFC = 7.1A total − 8.15.1 − 7.1A financial;
     - private NFC = 7.1B total − 7.1B financial.
   - FC = 7.1A financial OS + CFC + 7.1B financial OS + CFC.
   - GG = 8.15.1 CFC.
   - Centre share = (4.1 central government NVA + min(Union revenue grants-in-aid to autonomous bodies, 4.1 autonomous institutions)) / 4.1 NVA = (5,77,518.54 + 51,351.67) / 21,27,032.48 = **0.295656**.
8. **Constraint targets.** I recomputed all 62 from the same sources:
   - the 7.1A public-sector CE floors (transport includes air transport, 160.08);
   - the SUT caps;
   - the 7.1C group controls;
   - the F3a bands;
   - the NAS F1 and F2 + F3 totals;
   - the FC, GG and NFC GOS targets.
9. **Cross-block.** I read every built block's entries and constraints. From those I checked:
   - duplicate keys;
   - who writes factor cells;
   - the factor-account balance on the assembled prior;
   - that fincorp declares the same FC target as factors;
   - that the dependency hashes are current;
   - that every provenance input resolves.

## 2. Census record

| Item | Count | Checked | Result |
|---|---:|---|---|
| V1a entries | 65 | census | max diff 5.0e-7 |
| V2a entries | 86 | census | max diff 6.3e-6 (RAS convergence; with trade on ASUSE aggregate T, as built; V-F-2) |
| V3 / V4 | 2 | census | = NAS 6.1 (62,344.24 / 30,635.91); BoP within 0.24 |
| F1a | 20 | census | max diff 4.7e-7 |
| F2 | 20 | census | max diff 4.0e-7 |
| F3a / F3b / F3c | 30 | census | max diff 4.9e-7 |
| F4 / F4b | 4 | census | E_NFPU 11,67,179.33; E_NFPR 46,19,027.77; G_CEN 1,11,071.85; G_STA 2,64,607.31 |
| **Entries total** | **227** | census | all match |
| Constraint targets | 62 | census (20 equal, 10 band, 10 min, 22 max) | max diff 4.9e-7 |
| Satellites | 6 tables | sector_gos GOS rows; gg_centre_state_key; v1a_parameters (D, share_reg, national share); v1a_labour_split wage bills (all 36); va_split_by_activity (s_imp, group-9 ratio, all q_a, CFC sensitivity); factor_income_keys (levels vs entries, public_sector_wage_key, k = q sensitivity) | all match |
| Checks | 45 | target prov ids resolve; all `ok` | pass |

**Official totals.**
- V1a total 94,42,896.46 vs NAS 7.1 CE 94,42,896.63, a difference of −0.17.
- F1a total 94,74,604.79 vs NAS CE receivable 94,74,604.95, a difference of −0.17 (within the tolerance of 1).
- F2 + F3a + F3b + F3c = 97,71,430.53 = 7.1C, and each of the 14 7.1C groups holds to 0.01.
- Sector GOS: NFC + FC + GG + households = 1,70,20,025.76 vs SUT 1,70,20,025.77.
- The F4b total equals NAS 1.14 GG CFC.

**Floors and caps.** No floor binds:
- the smallest margin is mining, 12,061;
- public administration sits 0.12 above its floor by construction.

No household cap binds either. The two groups without a declared floor, agriculture and construction, are above their 7.1A public CE anyway.

## 3. Findings

| # | Severity | Finding | Evidence | Fix |
|---|---|---|---|---|
| V-F-1 | major (Checkpoint B; = factors-3, -19, confirmed) | The national-quintile crosswalk puts H_U4 and H_U5 wholly in national q5. The two top urban groups therefore get the same per-capita IFPRI index for every factor. | Regular-labour income per person is ₹2,29,494.67 for both H_U4 and H_U5. Factor income vs households' PFCE prior: H_U4 1.52×, H_U5 **0.86×**, the only group below 1. This matches the builder's factors-3/-19. The rural pattern (R1 1.42×, R5 1.09×) comes from the IFPRI gradient in both mappings. | Orchestrator decision at Checkpoint B (k = q, a within-quintile gradient, or saving-rate bands); then rebuild factors → taxes → government → fincorp. Strict xfail `test_top_urban_group_earns_more_regular_labour_income_per_person_than_u4`. |
| V-F-2 | minor | A_TRAD's partnership/trust share q uses the ASUSE **aggregate** category T. Every other activity uses sub-categories (M*, S1+S2, S3–S6, S10–S12). The provenance does not say this, and the issues file does not log it. The aggregate's ownership shares are published to one decimal (e.g. OAE different-household partnerships 0.3%), so precision is lost. | With T1–T5, q = 0.018021 against 0.014619 as built. hh_quasi would be 20,520.18 instead of 16,647.10: **+3,873.08** from F_MIXD/F2 to F_GOSC/F3c. Totals are unchanged. | Use T1–T5 as for the other activities, or state the choice in the V2a(b) method text and log it. Strict xfail `test_trade_quasi_share_uses_the_ASUSE_subcategories`. |
| V-F-3 | minor | A_UTIL is given q = 0 (no hh_quasi), yet its non-farm mixed income is split between rural and urban by ASUSE category **E**. The provenance does not say this, and factors-10 lists only farming, mining and construction as q = 0. E covers only non-captive electricity (NIC 3510x); household utilities are mostly water and waste (NIC 36–39), which ASUSE files under S15. E is also tiny: ₹15 crore of survey surplus. | `q_nonprop.a_util` = 0. The E key gives utilities mixed income a rural share of 0.144; PLFS 35-39 self-employment would give 0.215. That is ≈ ₹1,050 cr of the 14,738 moving between areas. | Log the choice in the issues file and the F2/V2a(b) method text; consider PLFS 35-39 (as for mining and construction) for the rural/urban key. |
| V-F-4 | minor (status honesty) | `gg_centre_state_key` row `gia.autonomous_bodies_revenue` (51,351.67) is `gia.cash.autonomous_bodies.total − capital_assets`, a computed difference. It sits under record `sam_factors:61a3a01459da`, which is `official` with the method "key inputs as published". | SAM_GUIDE s.5: `official` means "as published or pure aggregation"; a difference is `derived`. | Give that row a `derived` record. Strict xfail `test_computed_gia_difference_is_not_labelled_official`. |
| V-F-5 | minor (label) | The `v1a_labour_split` rows `wage_bill_index_regular/casual` carry unit `ratio`, but the values are rupee amounts: workers × annual earnings, e.g. 3.99e12 for 01-03 rural casual. | Satellite schema: unit is from `pipeline.core.units`. | Label the unit `INR`, or publish normalised shares. Strict xfail `test_wage_bill_index_unit_matches_its_values`. |
| V-F-6 | minor (wording; = factors-20) | The V1a method text says departmental enterprises' pensions are "paid back to households by government under R9d". Under D2-9, R9d is HH ← E_NFPU; government's entries show R9d railways 59,801.66 and posts 10,688.30 paid by E_NFPU. | Record `sam_factors:68d049319ab8`. | Fix at the next rebuild, as the builder planned. Strict xfail `test_v1a_method_text_names_the_right_r9d_payer`. |
| V-F-7 | minor (integration; new; **resolved by the 23:07 rebuild**) | **factors was stale against households** (state at 23:01–23:07). Households was rebuilt at 2026-09-30 23:01, after factors' 22:30 build, and all three hashes differ. The values factors reads did not change: my census against the new households outputs still matches. But the F3b record `sam_factors:ce1f0906f663` cites `sam_households:322c1b1cff56` (AIDIS), which no longer exists; the new key record is `505a53cea446`. So `test_sam_audit.py::test_every_sam_provenance_input_resolves` fails until factors is rebuilt. fincorp, capital_financial and rest_of_world also cite retired households records. The issues file's factors-21 ("taxes is stale") is also out of date: taxes, government and fincorp all record the current factors hashes. | Catalog `factors_block.json` `dependency_hashes.households` vs the current files. | Rebuild factors (with the V-F-6 wording fix and the V-F-1 decision if taken), then taxes → government → fincorp. Update factors-21. The test records this with a conditional `pytest.xfail` because other agents share the tree. |
| V-F-8 | info | The F1a method text does not say which PLFS group A_PADM's regular CE (12,42,220, 16.7% of F_LREG) follows for its rural/urban split. It follows 58-99 (regular rural share 0.2997). I reproduced that. | Recomputed F1a matches only with A_PADM in 58-99. | Add one clause to the F1a method text. |
| V-F-9 | info | The XR-22 F3a bands are fixed levels: prior F3a ± 10%. Their description says "link shares, not levels", but a fixed-level band bounds each group's F3a level. It does not follow a change in the C4a share or the F3a total. This is what XR-22 literally asked for. | `f3a_band.*` targets = the F3a entries. | Reword the description; the post-balancing share-drift report (plan s.8 item 3) is still owed. |

## 4. What I confirmed (no finding)

- **Plan s.8 / DECISIONS:**
  - XR-15: production's V1/V2 targets are not re-declared, and a test checks that the splits add up to them.
  - XR-20: the 14 7.1C group controls, 10 floors and 22 caps are declared. Public administration has no household sector in 7.1C, so no control is needed.
  - XR-22: the F3a bands are declared.
  - XR-10: the crosswalk, `pop_persons`, `aidis_fixed_assets` and the C4a entries are used.
  - `public_sector_wage_key` is F_LREG × PLFS t35, as CROSS_REVIEW §4.3 defines it. government and fincorp use it as shares. Its levels sum to 7.76 lakh cr, not the 28.9 lakh cr of public-sector CE, so it must not be used as a level.
  - D2-8: F4b uses the institutional view.
  - `f4.fc_gos` has the same selection and target as fincorp's `f4a.fc_gos_total`, so the two merge.
- **Double counting (plan s.6 risks 1–10):**
  - No F_MIXD entry in A_DWEL, A_FINS, A_INSR, A_PADM, A_COAL or A_OILG; no F_LCAS in A_PADM.
  - No factors entry in an E_RBI, E_BANK, E_NBFC or E_INSP row.
  - No F1 or F3 entries.
  - Only fincorp (7 F4a entries) writes a factor cell besides factors.
  - No duplicate keys across the 8 blocks.
  - Government writes no PM-KISAN in R10: the Centre's R10 is only LPG DBT and social security.
- **Status and role labels are honest:**
  - V3/V4 are `official` and `fixed`; F4 is `derived` and `fixed`.
  - V2a in single-activity groups is `derived` and `anchored` 0.02: a NAS household value or the SUT − NAS residual.
  - Everything else is `estimated` and `free`. Confidence is low for F1a, F2, F3b and F3c; high for A_PADM.
  - All entries are > 0; the smallest is 1.08.
  - Every entry's status equals its record's.
  - Every provenance input resolves, except the one V-F-7 input.
  - The 45 checks all pass, and their targets resolve.
- **Gaps and defaults logged in the issues file:**
  - D, the t51 fallback, the floors, the RAS, mining, the q = 0 sectors (except utilities, V-F-3), s_imp, the AIDIS proxy, IFPRI, the rural/urban keys, F4b and the dwelling CFC conflict are all logged.
  - Not logged: V-F-2, V-F-3 and V-F-8.

## 5. Suite

- `uv run python -m pipeline test tests/verify/test_sam_factors_spotcheck.py`:
  - against the 22:30 build: 19 passed, 6 xfailed (V-F-7 was stale then);
  - against the 23:07 rebuild: 20 passed, 5 strict xfailed.
- Full offline suite, run once (10 min, while other agents were building): 3,890 passed, 13 failed, 56 skipped, 32 xfailed. None of the 13 failures is in factors' files or mine:
  - `test_hygiene` order-shared (`pipeline/sam/blocks/households/__init__.py:96`, an unordered `group_by`);
  - the known FR-factors-1 framework test;
  - 2 rest_of_world verifier tests;
  - 7 solver-certificate verifier tests;
  - 2 timeseries verifier tests.

  `tests/sam/test_sam_factors.py` passes against the 23:07 build. Its fresh-build test failed at 23:03, while factors was stale (V-F-7).

## Re-verification (wave C close-out, 2026-10-01)

Verifier: an independent agent. I did not write the factors block, the D2-19 rebuild, the wave C fixes or any of the earlier edits to the regression test. Scope: the changes made after the verification above, which no different agent had checked:
- the 2026-09-30 maintenance fixes (V-F-2, V-F-3, V-F-4, V-F-5, V-F-6);
- the D2-19 rebuild (`IFPRI_MAPPING = "k_eq_q"`, with the crosswalk and HCES variants as sensitivity rows of `factor_income_keys`);
- the wave C audit items in `docs/phase2/issues/factors.md`: factors-23 (BS-12, the new `f4b.centre` band) and factors-24 (BS-8, a finding with no block change);
- the fixers' edits to `tests/verify/test_sam_factors_spotcheck.py`.

Build checked: `factors_*` of 2026-10-01 05:40 (entries sha256 `104bdbbd…`, constraints `39c488c2…`). These are the same hashes the balanced run records in `balancing_run.json`, and every factors entry equals its `prior` in `sam_entries_balanced.parquet` (227 of 227, difference 0).

### Method

I wrote a new script in my scratchpad. It uses DuckDB SQL and plain Python on `data/clean` and on the households outputs factors reads (`hh_keys`: pop_persons, aidis_fixed_assets, hces_total; `hh_national_quintile_xwalk`; the C4a entries). It does not import `pipeline.*`, and it does not import or copy the regression test. It recomputes the whole chain from scratch:
- the SUT targets;
- the PLFS wage bills, D and share_reg;
- the V2a RAS (my own loop) and group 9;
- q_a on ASUSE sub-categories (trade T1–T5);
- the dwellings split;
- the area keys (utilities on PLFS 35-39);
- the three within-area mappings (k = q, crosswalk, HCES);
- F3a/F3b, F4/F4b and every constraint target.

From the balanced SAM I also recomputed the figures in factors-23 and factors-24.

### Counts and results

| Item | Count | Result |
|---|---:|---|
| Entries (census) | 227 | All match, with none missing or extra. Max difference: V2a 6.3e-6 (RAS convergence); every other ref ≤ 5.1e-7. F1a, F2 and F3c are on k = q. |
| Constraint targets | 63 (20 equal, 11 band, 10 min, 22 max) | All match; max difference 4.9e-7. |
| `f4b.centre` | 1 | Target 1,11,071.850216 = 0.295656 × GG CFC 3,75,679.16. Kind `band`, rows G_CEN, cols F_GOSC, refs F4b, tol_abs 0. tol_rel 0.05 = max(5%, 1.04%), where 1.04% is the gap from sensitivity A (0.292582). |
| `factor_income_keys`, k = q (lreg, lcas, mixd_farm, mixd_nonfarm, quasi_corporate) | 50 levels + 50 shares + 10 area totals | All match (≤ 4.6e-6 and 4.9e-10). |
| `sensitivity_xwalk_*` | 50 levels + 50 area shares + 10 group totals | All match (≤ 4.9e-6). They reproduce the old crosswalk entries: regular-labour income is ₹2,29,494.67 per person for both H_U4 and H_U5, V-F-1's evidence. |
| `sensitivity_hces_*` | 50 levels + 50 area shares + 10 group totals | All match (≤ 4.6e-6). The definition used is weight = T10 share in quintile k × the group's hces_total, which is the record's "T10 × MPCE_g" times persons. |
| `sensitivity_labour_all` | 10 | Matches the k = q mapping (4.5e-10). It does not match the crosswalk (0.15). |
| Maintenance fixes | — | Confirmed. Trade q = 0.018021 and hh_quasi 20,520.18. Utilities' rural share is 0.215135. `gia.autonomous_bodies_revenue` has a `derived` record. Wage bills are in ₹ crore, regular and casual (all 36). The R9d payer text is correct. |
| Provenance of the changed records | 4 | The F1a, F2 and F3c method texts state k = q and D2-19. The sensitivity record `8d9df490b8ae` is `estimated`, and its inputs (IFPRI T10/T11; households pop_persons, hces_total, xwalk) resolve to the right records. Checks: 45 of 45 pass. |

The claims in the issues file hold:
- **factors-3:** factor income by group under k = q, the crosswalk and HCES (every figure in the "Household factor income by group" paragraph). Also H_U5 = 2.08 × H_U4's factor income per person, and factor income / PFCE is 1.08 for H_U4 and 1.21 for H_U5.
- **factors-19:** the HCES variant moves R5 by −6,88,908, U5 by −4,14,473 and R1 by +3,37,121.
- **factors-23:** G_CEN 1,11,071.85 → 1,16,625.44 (exactly +5%, the upper edge of the band). The share is 0.3104, against 0.3230 in the audited run. G_STA is 2,59,053.72. `gov.c2a.centre_own_output` ends at its −10% edge (7,86,844.42).
- **factors-24:** every group rate (31.3, 28.5, 29.4, 40.1, 13.5, 22.8, 23.5, 23.1, 24.1, 28.2). Rural / urban are 27.21 / 25.52 balanced and 25.94 / 24.21 in the prior. K4a z runs from 1.0622 to 1.0782. IFPRI-implied saving is 48.0 lakh, against NAS 58.9 lakh. PM-KISAN pays 48,460 of its 51,617 to the rural groups. The equal rate is 26.41%.

**Was anything forced?** D2-19 moves income only within each area, and every area total and constraint target is unchanged. The `k_eq_q` mapping is applied as D2-19 states, and the two variants it names are published. `f4b.centre` is declared openly: in the code, in factors-23, in `explanations/factors.yaml` and in BALANCING.md. Its 5% is a judgement, though (V-F-10).

### Regression test: the fixers' edits

The test file has never been committed, so there is no `git diff`. I compared it with sections 1–5 of this report.

Every changed expectation is **confirmed** by my recomputation:
- ASUSE T1–T5 for trade (V-F-2);
- PLFS 35-39 as utilities' area key, with no `q_nonprop.a_util` row (V-F-3);
- the gia row not `official` (V-F-4);
- wage bills in ₹ crore (V-F-5);
- the R9d text (V-F-6);
- `MAPPING = "k_eq_q"` in the census of F1a, F2 and F3c (D2-19);
- `sensitivity_xwalk_lreg` area shares;
- V-F-1 as an ordinary test (U5/U4 regular-labour income per person = 2.59 > 1.05);
- 63 constraints with 11 bands;
- the `f4b.centre` target equal to the census G_CEN.

Nothing was reverted. I added four tests:
- `test_d2_19_sensitivity_rows_recomputed[xwalk|hces]`: every sensitivity key's levels, area shares and group totals. The fixers' version checked only the crosswalk's lreg shares, and never the HCES rows.
- `test_casual_wage_bills_recomputed`.
- `test_f4b_centre_band_follows_its_stated_rule`: kind, selection, tol_abs and the max(5%, gap to sensitivity A) rule. Before, only the target was checked.

Result: `uv run python -m pipeline test tests/verify/test_sam_factors_spotcheck.py` gives 29 passed. `-k factors` gives 83 passed.

### Findings

| # | Severity | Finding | Evidence | Fix |
|---|---|---|---|---|
| V-F-10 | minor (honesty; Checkpoint B) | The ±5% of `f4b.centre` is a judgement, and it decides the balanced result. The code says the band "covers sensitivity A", but sensitivity A needs only 1.04%. No source bounds the Centre's share of GG CFC (factors-15). In the wave C run the band binds at its upper edge, so G_CEN (1,16,625.44, share 0.3104) is set by the 5%. The constraint cites the F4b entries' record `sam_factors:b68d202efe5e`, whose method text does not mention the band or its basis. | `factors_constraints.parquet`; `balancing_constraints.parquet` (`factors:f4b.centre` binding, balanced = hi). | Give the band its own `estimated` record, or add a sentence to the F4b record saying ±5% is a judgement band, not evidence. List it with factors-23 for the owner at Checkpoint B. |
| V-F-11 | minor (documentation) | The issues file's header still gives "62 constraints (20 equal, 10 band, …)", and so does the "Integration status" row ("62 of 62 hold"). The build has 63 constraints with 11 bands, because of `f4b.centre`. | `factors_block.json` constraints 63. | Update the counts. |
| V-F-12 | info (wording) | The sensitivity record `8d9df490b8ae` lists a `'k_eq_q'` variant among its sensitivity rows. No `sensitivity_k_eq_q_*` rows exist, because k = q is now the entries. | `factor_income_keys` keys. | Say that k = q is the entries' mapping and that only `xwalk` and `hces` are sensitivity rows. |
| V-F-13 | info (wording) | The factors-24 figure "about 0.94 lakh" moved from rural to urban at an equal 26.4% rate holds each area's consumption + saving fixed. Holding the SAM's consumption fixed instead, the move is 1.28 lakh. The text does not say which. | Recomputed from `sam_entries_balanced.parquet` (C1a/C4a/C4b/C4d and K4a by group). | State the basis. |
| V-F-14 | info (dated figures) | The counterfactual saving profiles in factors-19 were computed on the 01:34 prior: HCES R5 −9.0%, and the crosswalk's R5 12.4% / R4 27.7%. On the wave C prior, with the other blocks fixed and D1 pro rata to gross income (as it is in the prior, to 8e-13), they are HCES R5 −5.8% and R1 44.2%, and crosswalk R5 14.9%, R4 29.7% and U5 2.2%. The conclusions stand: HCES gives a falling profile with R5 negative, and the crosswalk flattens the urban top. | My recomputation. | Optional: mark the factors-19 figures as of the 01:34 prior, or refresh them. |

No defect in any number. V-F-1 to V-F-9 are closed in the build, and V-F-10 to V-F-14 are documentation and labelling. factors-19 and factors-24, the rural-top saving profile, stay Checkpoint B findings. I confirm them independently.
