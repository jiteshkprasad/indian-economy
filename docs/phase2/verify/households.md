# Verification: the `households` block (SPEC s.3 rule 3)

Verifier: an independent agent (not the households builder), 2026-09-30.
Scope: the households block only (refs C1a, C4a, C4b, C4c, C4d, S8 and the `hh_*` satellites). I recomputed every entry, every constraint target and the numeric satellites from the clean Parquet with DuckDB SQL, plus a few lines of plain Python for the two log-MPCE placement models. I did not import or call the builder's code.
Regression test: `tests/verify/test_sam_households_spotcheck.py` (21 passed, 1 strict xfail that records finding V-HH-1). It does not import `pipeline.sam` or polars. Full offline suite after writing it: 3,839 passed, 28 xfailed, 1 failed. The failure is `test_sam_framework.py::test_a_broken_sibling_module_does_not_stop_another_blocks_build`, which the builder already reported (another agent's real `factors.py`); it is not in households' files or mine.
Outputs checked: the build of 2026-09-30 22:16 (`households_entries.parquet` sha256 `88297125…`). It was built against the current production outputs, and every dependent block (factors, taxes, rest_of_world, government, fincorp, capital_financial) records the same sha256, so none of them is stale.

## Verdict

**Sound, with minor fixes.** Every number the block writes matches my recomputation:

- all 1,230 entries (largest difference 5.0e-7 crore, which is the 6-decimal rounding on write);
- all 4 constraints;
- every satellite row that can be recomputed independently.

The block reproduces SUT PFCE exactly for each of the 31 commodities and in total. It is within ₹0.48 crore of NAS 1.1 PFCE and ₹0.47 crore of NAS 8.13 dwellings output. It does not double count against any other built block.

The one confirmed defect is a status label (V-HH-1). V-HH-2 is a small undocumented change of key. V-HH-3 is a question about the XR-5 method that belongs at Checkpoint B, not a coding error. V-HH-4 is a gap in the issues log.

## 1. Method

1. **Inputs, survey window only.** HCES A2 and A10F rows with period `2023-08/2024-07` (vintage 2025-01-30); A2 all-India (`IN`) rows only, the 24 fractile classes.
2. **Groups.** The plan's s.2.0 definition, typed as a table:
   - H_x1 = p00_05 + p05_10 + p10_20;
   - H_x2 = p20_30 + p30_40;
   - H_x3 = p40_50 + p50_60;
   - H_x4 = p60_70 + p70_80;
   - H_x5 = p80_90 + p90_95 + p95_100.

   Each group holds 20.00% of its area's persons (checked to 1e-4). Total persons: 1,217,643,800.
3. **HCES spending.** V(item, g) = A10F value per person (30 days) × A2 persons × 12 / 1e7, summed over the classes of g. Cells printed '-' are absent in the clean data and count as 0.
4. **C1a / C4d.** For every product keyed in the committed concordance `hces2324_item_to_sut_product.csv`, each group's entry is:

   SUT `use.pfce.sut_pNNN.current` × Σ_items V / Σ_g Σ_items V

   The row is the SAM commodity from `io_tables_sut_product_to_sam34.csv`. The component is `sut_pNNN` (C1a) or `oop_health` / `oop_education` (C4d). The expected confidence is `medium` for a `direct` key and `low` for a `proxy` key.
5. **C4a (dwellings).**
   - govt = `supply.output.sut_p144.sut_i67.current` (20,056).
   - rest = `use.pfce.sut_p144.current` − govt.
   - r = V520 / (V520 + V539) = 0.250230684.
   - actual = rest × r, keyed by item 520.
   - imputed = rest × (1 − r), keyed by item 539.
   - govt is keyed by item 520.
6. **C4b (FISIM, fees, insurance).**
   - Rates: r* = RTP SCB return on investments 6.7%, r_D = cost of deposits 4.8%, r_L = return on advances 9.4% (vintage 2025-12-29).
   - Stocks: D = mean of 31 Mar 2023 and 31 Mar 2024 T52(b) bank + non-bank deposits (1,36,26,176.50); L = mean of `t52b.fl` (1,11,76,172.65).
   - FISIM_D = NAS 1.13 FISIM × (r* − r_D)·D / [(r* − r_D)·D + (r_L − r*)·L] = 2,78,404.19. FISIM_L = 3,24,492.77.
   - Group keys: AIDIS 2019 i9/i5 per-household values by AIDIS class (household quintiles within the area). They are mapped to groups by overlap of cumulative HCES A2 household shares (groups ordered by MPCE) × the area's households. Loans are multiplied by the press-note institutional share (rural 66%, urban 87%). Deposits are multiplied by min(1, deposit share × assets per household / financial assets per household).
   - Explicit fees = SUT p142 − FISIM; insurance = SUT p143. Both are keyed by AIDIS financial assets.
7. **S8 (satellite).** A10F quantities of 061 / 062 (tonnes) × persons × 12. Their shares × SUT GFCE on paddy / wheat give each group's value. The memo rows for 070–075 use A10SW all-India rural/urban unit values (value ÷ quantity).
8. **Placement models** (`hh_national_quintile_xwalk`, `hh_state_xwalk`), from the method text:
   - Each class is spread uniformly in log MPCE between the log-midpoints to its neighbouring classes; the first and last classes are mirrored.
   - The national cut-offs are found by bisection on the pooled CDF.
   - The all-India area cut-offs (used for States) are the log-midpoints of the class means at the group boundaries.

   I wrote this code myself from that description.
9. **Cross-block checks.** I read every built block's `*_entries.parquet` and `*_constraints.parquet`.

## 2. Census record

### 2.1 Entries (tolerance ₹0.01 crore; all 1,230 checked)

| Ref | Cell | Entries (mine = theirs) | Σ value (₹ crore) | Confidence | Source total it reproduces |
|---|---|---|---|---|---|
| C1a | 26 commodities ← H_* (114 products × 10) | 1,140 = 1,140 | 1,20,27,521.0 | 850 medium, 290 low | SUT PFCE of the 114 products |
| C4a | C_DWEL ← H_* (actual, imputed, govt) | 30 = 30 | 21,48,044.0 | actual medium; imputed, govt low | SUT p144; govt = supply i67 20,056 |
| C4b | C_FINS, C_INSR ← H_* | 40 = 40 | 11,08,733.0 | low | NAS 1.13 FISIM 6,02,896.96; SUT p142, p143 |
| C4d | C_HLTH, C_EDUC ← H_* | 20 = 20 | 11,31,249.0 | medium | SUT p153, p152 |
| **All** | | **1,230 = 1,230** | **1,64,15,547.0** | 880 medium, 350 low | SUT total; NAS 1.1 +0.48 |

- **Value census:** 0 entries only in mine, 0 only in theirs, 0 with a difference above ₹0.01 crore. The largest difference is 5.0e-7 (write rounding).
- **Metadata:**
  - every entry is `estimated` / `free`, with no `tol_rel` and no bop tag;
  - no value is zero or negative;
  - confidence follows the concordance key quality product by product (one quality per product);
  - C4a is actual `medium`, imputed and govt `low`.
- **Refs per commodity:**
  - C_DWEL is only C4a; C_FINS and C_INSR only C4b; C_HLTH and C_EDUC only C4d; the other 26 commodities only C1a;
  - no entries on C_OILG, C_OMIN or C_MTLS, none on product 125 (jewellery), and none under C4c.
- **Components:**
  - `fisim_deposits` + `fisim_loans` = NAS 1.13 (to 1e-4);
  - adding `explicit_fees` gives SUT p142;
  - `actual_rent` + `imputed_rent` = 21,27,988.00, against NAS 8.13 ownership of dwellings 21,27,988.47 (the 0.47 is Use-table rounding).

### 2.2 Constraints (all 4 checked)

| id | Target (mine = theirs) | Source | tol | kind, filter |
|---|---|---|---|---|
| `hh.c1.total` | 1,64,15,546.524761 | `s1_1.pfce.current` | abs 1 | equal; 34 C_* × 10 H_*; no refs/components filter |
| `hh.c4a.govt_housing` | 20,056.0 | `supply.output.sut_p144.sut_i67.current` | abs 1 | equal; C_DWEL; refs C4a, component govt_housing |
| `hh.c4a.imputed_rent` | 15,95,500.107 | (SUT p144 − i67) × (1 − r) | rel 0.10 | band; C_DWEL; C4a, imputed_rent |
| `hh.c4b.fisim` | 6,02,896.961538 | `s1_13.private_final_consumption_expenditure.current` | abs 1 | equal; C_FINS; C4b, fisim_deposits + fisim_loans |

- Production's 34 `pfce.*` targets are **not** re-declared, as XR-15 requires. My recomputed per-commodity sums equal all 34 targets to ₹0.01 crore, including the three zero targets.
- `hh.c1.total` and production's per-commodity constraints can hold together: the prior sits 0.48 inside ±1.
- factors declares the 10 per-group `f3a_band.*` constraints, so XR-22 is closed on both sides.

### 2.3 Satellites (recomputed rows)

| Satellite | Checked | Result |
|---|---|---|
| `hh_keys` (510 rows) | every share = level / Σ level (1e-11). Recomputed levels: 80 AIDIS rows (8 keys × 10, overlap mapping), 20 pop, 40 hces_total/food/nonfood/durables, 70 c4a_*/c4b_* (= own entries by group), 10 pfce_total; `aidis_equity/mf/small_savings` = `aidis_fin_assets` exactly; 8 `fisim_params` rows | all match |
| `hh_group_map` (72) | persons, households and avg MPCE of 24 classes; class → group | match |
| `hh_hces_items` (3,788) | every row = V(item, g) | match (1e-6) |
| `hh_aidis_overlap` (54) | 18 overlapping-household rows | match |
| `hh_national_quintile_xwalk` (104) | 50 persons rows; group shares sum to 1; cut-offs ₹2,846 / 3,696 / 4,734 / 6,413 | match (rel 1e-6) |
| `hh_state_xwalk` (4,464) | all 1,140 class persons rows (and the implied zeros), 1,140 consumption rows (= persons × class MPCE × 12 / 1e7), 696 State × area `all` rows | match |
| `c1a_hces_nas_ratio` (438) | 116 product ratios (an item keying several products is split by SUT PFCE) | match (rel 1e-9) |
| `c4a_imputed_rent_sensitivity` (34) | AIDIS building-value rural share 0.401806; variant and diff by group; ₹2,10,681 crore moves to rural groups | match |
| `c4c_npish_memo` (3) | ICIO 2022-23 NPISH 10,152.6 and HFCE 20,41,862 (US$ mn); share 0.4948% | match |
| `s8_food_stik` (164) | 20 quantity and 20 value rows for rice and wheat, 2 unit values (₹39.38 and ₹50.55 per kg), group totals (Σ = SUT GFCE 1,63,971.75), 50 memo value rows at A10SW unit values, 2 `hces_valued` rows (1,04,097 and 36,373) | match |

The memo quantity rows (30), the commodity rows of `c1a_hces_nas_ratio` and the `weight` rows of `hh_state_xwalk` are implied by the rows above and were not compared one by one.

## 3. Checks against the plan, the gap map and the decisions

- **Concordance (D2-15, pending orchestrator approval).**
  - Every one of the 381 A10F leaf items is either used or excluded with a reason.
  - Only leaf codes are used, apart from memo 539 in C4a.
  - None of 640–643, 061–075, 282, 520, 539, 522, 405/406/408, 411–414, 421/422/424 is in a C1a key.
  - Every PFCE product except 142–144 has a key, and no product without PFCE has one.
  - The departures from the plan's Appendix A are logged (households-16, -11).
- **SUT memo rows.** `use.pfce.purchases_*` are not read. Their provenance record `io_tables:221b6f549118` is an input of no households record.
- **Survey window (P1-5).** The assumption record is an input of every C1a, C4a and C4d record.
- **Provenance.** Every input of the 143 records resolves to a clean record or a households record. Each entry's status equals its record's status. The C1a and C4d records cite the SUT product record (`io_tables:f6d331e96230`), A10F (`hces_consumption:50e52b2e99e0`) and A2 (`hces_consumption:e5e8a3696a31`).
- **Double counting across blocks.**
  - No other block writes COM ← HH, so NPISH, free grain and jewellery cannot re-enter PFCE.
  - Government's C2a food subsidy on C_CROP ← G_CEN (1,63,971.75) equals the S8 control. S8 stays a satellite.
  - fincorp reads the C4b FISIM components by group (XR-5), and its catalog records the current sha256.
- **Signs and plausibility.**
  - All entries are positive.
  - Rural share of PFCE is 51.77% (IFPRI 57.2%); H_R5 + H_U5 hold 39.84%.
  - The Engel food share falls from Q1 to Q5 in both areas.
  - S8 per person falls from Q1 to Q5 in both areas.
- **Figures in the issues file.** The group PFCE table, the HCES/SUT ratios (p114 70.6, p113 19.0, p137 0.039, …), the S8 figures, the FISIM split and the ₹2,10,681 crore sensitivity all match my recomputation.

## 4. Findings

| id | Severity | Status | Finding | Fix |
|---|---|---|---|---|
| V-HH-1 | minor | confirmed (strict xfail) | The target record of `hh.c4a.imputed_rent` (`sam_households:3913eac1d58c`) is `derived`. The same quantity is `estimated` on the 10 imputed_rent entries. The target is (SUT p144 − i67) × (1 − HCES V520/(V520+V539)): applying an HCES ratio to the NAS level is a modelling assumption, and the builder's own method says no NAS table separates tenant and owner rent. | Register the band's record as `estimated`, citing the same inputs. |
| V-HH-2 | minor | confirmed | FISIM_D is keyed by `aidis_deposits` = financial assets × min(1, press-note deposit share × assets / financial assets): rural 1.0966 capped to 1, urban 0.9711. Plan s.2.4 keys it by financial assets. The press-note shares are whole percent: urban 9% could be 8.5–9.5%, a ratio of 0.917–1.025, so 0.9711 adds noise rather than information. Effect: ₹1,893 crore of FISIM_D moves from urban to rural groups (H_U5 −775, H_R5 +640). households-5 logs the cap as a rounding artefact but not as a change of key from the plan. | Key FISIM_D by `aidis_fin_assets` as planned, or log the change of key and its impact in households-5. |
| V-HH-3 | minor | plausible (method question; XR-5 is binding) | The XR-5 split applies the loan margin to all household liabilities (T52(b) `fl`, which includes housing and enterprise loans). SNA books FISIM on those loans as intermediate consumption of dwellings and of unincorporated enterprises, not PFCE. The loan share of PFCE FISIM (53.8%, ₹3,24,493 crore) is therefore probably overstated. households-19 covers only the group key, not the level split. Also, the rate-based raw household FISIM (₹5,60,654 crore = 1.9% × D + 2.7% × L) is below NAS PFCE FISIM alone, so the formula is only a split rule. | Publish a Checkpoint B sensitivity (loan leg on consumer credit only, or deposits only) next to the stock-weight one, and add the level-split point to households-19. |
| V-HH-4 | minor | confirmed (logging) | A10F cells printed '-' are absent in the clean data and count as 0. 17 key items have fewer than 24 class rows (e.g. 005 cheese 19, 343 20, 503 air fare 21). The default is right (the plan prescribes it) and is stated in the `hh_hces_items` record, but the issues file does not list it among the defaults. | Add one line to the issues file listing the items. |

No finding changes a SAM number by more than ₹2,000 crore, apart from the V-HH-3 method question.

Observations, no action needed:

- The FISIM deposit weight (0.4618) and the ₹47,857 crore stock-weight sensitivity are published in `fisim_params`, and the numbers are right.
- The AIDIS class anomaly (households-4) is as served: in every table the five quintile values average to the area value (within rounding), so their order cannot be tested from these tables.

## 5. Issues-file completeness

Every gap, default and fallback I found is in `docs/phase2/issues/households.md`, apart from V-HH-2 (the change of key) and V-HH-4 (the '-' cells). That covers:

- the gap-map primary sources that cannot be followed (C4a AIDIS, C4b insurance, C4c spreading, government housing key);
- the new concordance and its amendments;
- the AIDIS anomaly;
- the proxies (households-7, -11);
- the S8 wheat valuation;
- the NAD questions;
- the population gap;
- the survey window.

The headline items for ISSUES.md stand as the builder lists them: H1, the imputed-rent split, the AIDIS class order, S8 wheat and the concordance approval. Add V-HH-3 to them.
