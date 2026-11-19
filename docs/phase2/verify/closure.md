# Verification: the `closure` block (SPEC s.3 rule 3)

Verifier: an independent agent (not the closure builder or integrator), 2026-10-01.

Scope: the closure block only. That covers refs K4a and D1, its 2 constraints, 9 checks, 5 satellites and 19 provenance records. I recomputed every number from `data/clean` Parquet and from the other eight blocks' built outputs, using DuckDB SQL and plain Python. I did not import or call `pipeline.sam` or the builder's code. I read `closure.py` only to compare its stated method with the plan.

Regression test: `tests/verify/test_sam_closure_spotcheck.py`: **14 passed, no xfail** (on the builds of 00:49 and 00:56). It imports neither `pipeline.sam` nor polars. It recomputes everything from the dependency outputs as they stand at test time. If a dependency is rebuilt and closure is not, the tests fail, and the first one names the stale dependency.

Outputs checked: two builds, both in full.
- **2026-10-01 00:16** (`closure_*`: 20 entries, 2 constraints, 9 checks, 5 satellites, 19 records). Its dependency hashes matched the files on disk, but fincorp and capital_financial were stale against government.
- **2026-10-01 00:49**, rebuilt after fincorp (00:45) and capital_financial (00:49). Every block now reads the same government outputs.

closure was rebuilt once more at 00:56, after capital_financial's 00:51 rebuild. My recomputation gives the same numbers as for 00:49.

Both builds recompute exactly. The numbers below are from **00:49** unless marked otherwise. Section 4 lists what changed between the two.

## Verdict

**The block is sound. Every number it writes recomputes exactly, and the method follows the plan (option A, D2-3, the s.8 amendments).**

The headline findings are real and correctly traced:
- Z = −11,43,179.72;
- H_U5's negative saving;
- the institution gaps.

None of them is caused by closure's arithmetic. Four minor issues remain: wording in the issues file, status labels on the diagnostic satellites, over-broad provenance inputs on the D1 split, and a staleness hand-off. None changes a number.

- **Entries: census of all 20, every one of them ≥ ₹10,000 crore.**
  - Same keys as my recomputation; every value matches to 0.000000 in both builds.
  - K4a: `free`, `low`, `estimated`; nine positive, H_U5 negative; all above ₹1 crore in absolute value.
  - D1: `fixed`, `estimated`, all positive. The rounding remainder sits on H_R5, the group with the largest income (42,52,623.43).
- **Constraint targets: census, 2 of 2.**
  - `k4.hh_saving_total` = 58,90,330.446044. This value is identical in NAS St 1.9, 1.14 and 5.3. The constraint is `equal`, ±0.5. It exactly duplicates capital_financial's `cf.k4.hh_saving`, so the two merge.
  - `d1.published_total` = 5,71,133.272525, `band` ±1. It equals both the St 1.14 identity and the St 1.1 identity within 1e-6.
- **Checks: 9 of 9 recomputed.** Their targets are clean records. Eight pass. `k4.prior_sum_vs_nas` fails by Z, on purpose (closure-3).
- **Satellites: every row recomputed, 3,646 rows in all.**
  - `hh_saving`: 169 rows, largest relative difference 5e-10.
  - `xdisc_identity`: 10 rows.
  - `prior_imbalance`: 896 rows (128 accounts × 7 measures), including ranks.
  - `constraint_gaps`: 2,290 rows (all 387 declared constraints). Only the two K4 declarations lie outside their band.
  - `institution_gaps`: 281 rows, including the NAS requirement table 2.4-C.
- **Provenance: all 19 records resolve.**
  - Each K4a record cites **exactly** the prov_ids of the entries in its group's row and column, plus the group's D1 record and NAS St 1.9.
  - The D1 total record is `derived` over D2, D3, D4 and the published residual.
  - The K4 target record is `official` over St 1.9.
- **Double counting: none.**
  - Only closure writes `K_HH ← H_*` and `X_DISC ← H_*`.
  - There is no intra-household entry.
  - Every household-touching ref of the other blocks is on the whitelist: plan s.2.1 step 2, amended by s.8 item 2 and D2-9.
  - The X_DISC column holds only D2, D3 and D4.
  - D3 valuables reach K_HH only, never household income, and D3 → K_HH = I2a to the paisa.

## 1. Method (what I recomputed, and how)

All values are ₹ crore, 2023-24, current prices. NAS and SUT are vintage 2026-08-31; IFPRI is 2024-10-01 (period 2022-23).

1. **Inputs.** Every entry of the eight other blocks (`data/sam/2023-24/blocks/*_entries.parquet`: 3,840 entries at 00:16, 3,847 at 00:49) and every constraint (387 with closure's). From households' `hh_keys`, `pop_persons` (level).
2. **Group accounts.**
   - `inc_g` = Σ entries with row = H_g.
   - `out_g` = Σ entries with column = H_g.
   - `pfce_g` = Σ of those with a `C_*` row.
   - `paid_g` = `out_g` − `pfce_g`.
3. **D1 (D2-3, plan s.2.2).**
   - Total = Σ of the X_DISC column as the other blocks wrote it: D2 2,12,499.236490 (rest_of_world), D3 3,58,633.928552 (capital_financial) and D4 0 (production, 34 zero entries). That gives 5,71,133.165042.
   - Split: `D1_g = round(total × inc_g / Σ inc, 6)`, with the remainder on the group with the largest income.
4. **K4a (option A, plan s.2.1).** `K4a_g = round(inc_g − out_g − D1_g, 6)`. Z = Σ K4a − NAS St 1.9 household saving.
5. **Satellites.**
   - `hh_saving`: the plan's measures (rates on gross income, on disposable income and on PFCE + saving; option B = K4a − Z × income share; the D1 splits by PFCE and by population; per-person saving). IFPRI T11 rural and urban rates are read from clean data.
   - `prior_imbalance`: row, column, imbalance, % of the larger total, non-fixed counts and rank, over all nine blocks, for each of the 128 accounts in `accounts.yaml`.
   - `constraint_gaps`: my own filter over rows × cols, refs and components, with the band `target ± max(tol_abs, tol_rel·|target|)` (`min`/`max` one-sided).
   - `institution_gaps`:
     - Flow classes are set by the counterpart account's group (FAC, COM, CAP, DISC; TAX split into T_PIT/T_CIT current taxes versus other taxes on production and imports), then by ref (property income, social, other transfers).
     - Flows inside the institution set cancel.
     - Required net flows follow plan table 2.4-C. For each institution below, the required net flow is its NAS total less its primary income:

       | Institution | NAS total | Primary income |
       |---|---|---|
       | Households | St 1.14 GDI | CE receivable + 7.1C OS/MI + CFC |
       | Public NFC | St 1.9 saving | 7.1A OS + CFC, less the financial row, less 8.15.1 |
       | Private NFC | St 1.9 saving | 7.1B, less the financial row |
       | FC | St 1.9 saving | 7.1A + 7.1B financial rows |
       | GG | St 1.14 GDI | CFC + product taxes − product subsidies + 7.1A/B/C net production taxes |
6. **Checks.** Each target is recomputed from clean data (SUT CIF, NAS S-I errors, SUT valuables − St 1.9 gold, NAS 6.1 RoW net).
7. **Provenance.** Every input resolves against all clean and SAM provenance files. Entry status equals its record's status. The input sets are compared with the entries each number uses.

## 2. Values checked

| Item | Count | Result |
|---|---:|---|
| Entries (census) | 20 | all match (max diff 0.000000) |
| of which ≥ ₹10,000 crore | 20 | all in the census |
| Constraint targets (census) | 2 | match clean; kind, tolerance and refs filter as the plan says |
| Checks | 9 | targets recomputed; 8 pass, `k4.prior_sum_vs_nas` fails by Z as logged |
| `hh_saving` rows | 169 | match (≤ 5e-10 relative) |
| `xdisc_identity` rows | 10 | match (residual 0.107483; 0.343973 with the NAS 6.1 CIF) |
| `prior_imbalance` rows | 896 | match; Σ imbalance over 128 accounts = 1.2e-9 |
| `constraint_gaps` rows | 2,290 | match; outside band: only `capital_financial:cf.k4.hh_saving` and `closure:k4.hh_saving_total` (Z each) |
| `institution_gaps` rows | 281 | match (≤ 1e-4) |
| Provenance records | 19 | all resolve; K4a input sets exact |

Key numbers, recomputed on the 00:49 build (00:16 values in brackets where they differ):

- **Z = −11,44,073.444205** [−11,43,179.717472]. Σ K4a is 47,46,257.001839 against 58,90,330.446044. K_HH's prior imbalance is exactly Z. The 10 H_g accounts and X_DISC close to below 1e-5. The D1 total is unchanged at 5,71,133.165042.
- **Saving / gross income by group:**

  | Group | Rate |
  |---|---:|
  | R1 | 33.37% |
  | R2 | 25.98% |
  | R3 | 24.45% |
  | R4 | 27.68% |
  | R5 | 12.36% |
  | U1 | 20.17% |
  | U2 | 23.51% |
  | U3 | 26.67% |
  | U4 | 35.87% |
  | U5 | −5.52% |

  H_U5's K4a is −2,13,186.13 [−2,12,956.86].
- **Saving / (PFCE + saving):** rural 23.94% against IFPRI 21.3%; urban 20.73% against IFPRI 24.0%.
- **H_U4 and H_U5 get the same factor income per person** (the factors-3 crosswalk): F1a ₹2,41,635 per person and F2 ₹84,757 per person for both groups.
- **Required net distributive flows:**

  | Institution | Required net (₹ crore) |
  |---|---:|
  | Households | +36,30,974.76 |
  | Public NFC | −7,04,183.08 |
  | Private NFC | −22,08,619.25 |
  | FC | −95,261.20 |
  | GG | −1,83,400.52 |
  | Sum | +4,39,510.70 |

  The sum equals the NAS 6.1 RoW net 4,39,510.702906 within 0.0006.
- **Delivered − required:**

  | Institution | Delivered − required | [00:16] |
  |---|---:|---:|
  | Households | −11,44,072.91 | [−11,43,179.18] |
  | Private NFC | +6,45,250.16 | [+6,42,174.81] |
  | Public NFC | +2,43,838.89 | [+2,45,292.64] |
  | GG | +3,87,151.65 | [+3,77,748.23] |
  | FC | −1,32,167.79 | [−1,22,036.51] |
  | Domestic | 0.00 | |

  The builder's trace of Z is confirmed in structure. Its figures in the issues file are the 00:16 ones.
- **Largest prior account imbalances:**

  | Account | Imbalance |
  |---|---:|
  | K_HH | −11,44,073.44 |
  | E_NFPR | +6,45,250.16 |
  | G_STA | +4,84,089.85 |
  | E_NFPU | +2,43,838.89 |
  | E_NBFC | +1,74,533.95 |
  | E_BANK | −1,72,130.87 |
  | E_INSP | −1,60,216.14 |
  | G_CEN | −96,938.08 |
  | E_RBI | +25,645.50 |

  The K_GCEN/K_GSTA ±1,594.81 pair of the 00:16 build is gone. Everything else is under ₹1.5 crore.
- **Primary income against NAS:**

  | Institution | SAM − NAS (₹ crore) |
  |---|---:|
  | Households | −0.167 |
  | Public NFC | 0.000 |
  | Private NFC | 0.000 |
  | FC | +0.222 |
  | GG | −0.113 |

## 3. Findings

| # | Severity | Finding | Evidence | Recommended fix | Logged by builder? |
|---|---|---|---|---|---|
| V-CLO-1 | major (finding, not a defect) | **Z (−11,44,073.44 on the current build) and the implausible group saving profile, with H_U5 negative, are confirmed independently.** They come from the other blocks' distributive flows (fincorp's corporate distributed income, government's R9b and the K3a bridge, FC payouts) and from the factors-3 crosswalk, not from closure. Under option A, z ≥ 0 locks H_U5's sign. | Sections 1 and 2: Z, the institution gaps and the rates recompute exactly. Delivered − required sums to 0.001 over the domestic institutions. | Checkpoint B (closure-3, closure-16, closure-9). Fix upstream; do not override the K4a sign. | yes (closure-3, -9, -16) |
| V-CLO-2 | minor | **Wording in the issues file is inaccurate in four places.** (a) closure-16 says factor income is "85-88% of each group's gross income"; it is 73.3% (H_U5) to 88.4% (H_R1), and all urban groups are below 84%. (b) closure-3 and the Z table say each institution's primary income equals NAS "to 0.00"; the differences are −0.167 (HH), +0.222 (FC) and −0.113 (GG), which is rounding and does not change the conclusion. (c) The FC row of the Z table lists "E_MUTF", but `accounts.yaml` has no E_MUTF (only K_MUTF), and `institution_gaps` rightly uses E_RBI, E_BANK, E_NBFC and E_INSP. (d) closure-2 quotes 0.107482; the written total and the check give 0.107483. | `institution_gaps` `primary_income_gap`; F1a+F2+F3a+F3b+F3c / row total per group; accounts.yaml | Correct the text when the issues file is refreshed after the rebuild (closure-17). | no |
| V-CLO-3 | minor | **Status labels on the diagnostic satellites overstate or blur quality.** `prior_imbalance`, `constraint_gaps` and `institution_gaps` are labelled `derived`, but they aggregate estimated entries (K4a, C1a, R8a and others). The guide defines `derived` as arithmetic on official numbers. `hh_saving` labels every row `estimated`, including the official NAS K4 total (`all.k4_nas`), the `derived` hh_keys persons and the IFPRI rates. | Satellite `status` columns; SAM_GUIDE s.5 | Label aggregates over estimated entries `estimated` (or state the convention "diagnostic: derived from the prior" in the record's method), and give `all.k4_nas` its own `official` record. Cosmetic: no number changes. | no |
| V-CLO-4 | minor | **The D1 split record's inputs go beyond the key it uses.** Record `sam_closure:446853b25ad5` cites 147 inputs: every household-touching entry (households' C1a/C4*, taxes' T3a, fincorp's R5 and so on) plus the D1 total. The key uses only the row-side (income) entries and the total. | `closure_provenance.parquet`; test `test_provenance_records` checks only that the key's inputs are included | Restrict the inputs to the income-side prov_ids plus `sam_closure:7d5dfbf36ca4`. Lineage precision only. | no |
| V-CLO-5 | minor | **The issues file still describes the 00:16 build.** That build mixed two government vintages: fincorp and capital_financial had read government `entries` 72e7541b9922…, while closure read 9c4754380545…. After the rebuilds (fincorp 00:45, capital_financial 00:49, closure 00:49) every block reads 9c4754380545…, and closure is current. But `docs/phase2/issues/closure.md` still quotes the 00:16 figures: Z −11,43,179.72, the institution-gap table, the top-10 imbalances with K_GCEN ±1,594.81, and H_U5 −2,12,956.94. | `*_block.json` `dependency_hashes`; section 2 | Refresh the figures in the issues file (the closure-17 hand-off). No change to the block. | yes (closure-17) |

What I checked and found right (no finding):

- **Option A.** The prior residual is not rescaled, and each group's sign comes from its own account (plan C7).
- **D2-3.** D1 total = D2 + D3 + D4 as written; X_DISC closes exactly; the published residual is a ±₹1 band.
- **Rounding remainder.** It sits on the largest-income group.
- **Sign lock.** The |K4a| ≥ ₹1 guard is in place.
- **Whitelist.** It includes R7x/R9d (D2-9) and R9a (XR-11), and rejects R9, R3a, R8 and T3 on H_*.
- **Missing-group rule.** It is only a warning; R12a is exempted, as rest_of_world writes it on H_U4 and H_U5 only (closure-4).
- **The K4 constraint.** It is a duplicate of capital_financial's, with the same selection, kind and target.
- **Satellite definitions.** They match plan s.2.3, and `prior_imbalance` equals my own account totals.
- **Checks.** The `target_prov_id` values are clean records, or closure's own `derived` D1-total record for `x_disc.prior_closure`.

## 4. Rebuilds during verification

fincorp was rebuilt at 00:45, after closure's 00:16 build. For four minutes closure was stale, and my regression test failed as designed:
- `test_closure_read_the_dependency_outputs_on_disk` named fincorp;
- the census and satellite tests differed by the fincorp change (₹229.27 crore on H_U5's K4a).

capital_financial and closure were then rebuilt, at 00:49:36 and 00:49:41. On that build all 14 tests pass, and my scratch recomputation matches every entry, satellite row, check and provenance input set again.

The change between the two builds comes entirely from fincorp's household property income:
- Z moved by −893.73;
- gross income of all groups fell by 850.58.

The method did not change. The D1 total record has a new id (`sam_closure:be174b25f307`) because capital_financial's D3 records were re-registered; its value is unchanged.

closure was rebuilt again at 00:56, after capital_financial at 00:51. That build recomputes identically (Z −11,44,073.444205; every satellite row matches), and `tests/sam/test_sam_closure.py` plus this spot-check pass (39 tests).

**Full suite at 01:00:** 10 failures, none in this spot-check. They are:
- the households hygiene `group_by`;
- the audit's provenance-input test;
- the framework's broken-sibling test;
- the two timeseries tests (closure-18);
- the three capital_financial verifier tests;
- the capital_financial and closure fresh-build tests.

The two fresh-build tests failed only because their blocks were rebuilt while the 9.5-minute run was in progress. Re-run afterwards, the closure fresh-build test passes.
