# Verification: the `production` block (SPEC s.3 rule 3)

Verifier: an independent agent (not the framework/production builder), 2026-09-30.
Scope: one lens only, the production block. I recomputed every entry and every constraint from the clean SUT Parquet with DuckDB SQL and the committed concordances. I did not use the builder's code for this. I checked the totals against NAS 2026, the crude/gas label swap, the CIF adjustment, sign conventions, which entries are fixed and which are constraints, and provenance.
Regression test: `tests/verify/test_sam_production_spotcheck.py` (32 passed, 2 strict xfails that record defects V-1 and V-5 below). It does not import `pipeline.sam` or polars.

## Verdict

**Needs fixes.** Every number the block writes is right: 1,064 of 1,064 entries and 238 of 238 constraints match my recomputation, and every NAS control total is within ₹4 crore. But two problems sit between these numbers and a successful balancing run:

- **V-1 (major, confirmed).** The anchored rounding allowance the balancer reads is not the one the block declares. `tol_rel` is rounded to 6 decimals when the file is written. As a result, 5 large SUT entries (₹20–69 lakh crore each) are written with `tol_rel = 0`, which pins them, and 99 other entries get an allowance that is off by more than ₹0.05 crore.
- **V-2 (major, plausible).** With the ₹1-crore-per-cell boxes (relative widths of 1e-7 to 1e-5), Clarabel does not reach `optimal` on the production core. It stops at `optimal_inaccurate` both at the framework's tight tolerances and at its defaults. Under the framework's rule that status fails the run.

## 1. Census record

### 1.1 Entries (tolerance ₹0.01 crore)

Clean inputs: `io_tables_sut_supply`, `io_tables_sut_use` and `io_tables_sut_va` for 2023-24. All carry one vintage (2026-08-31). Only real cells are used: products `sut_p001..155` and industries `sut_i01..67`. The memo rows (`cif`, `purchases_*`) and the `total` rows/columns are excluded. Products and industries are mapped by `data/concordance/io_tables_sut_{product,industry}_to_sam34.csv`, which cover 155/155 products and 67/67 industries with no unmapped cell. The sha256 values match the block catalog (`8b534e01…`, `29772cb6…`).

| Ref | Cell | Rule (gap map) | Entries mine = theirs | Σ value (₹ crore) | Role |
|---|---|---|---|---|---|
| P1 | ACT ← COM | Supply `output` | 145 = 145 | 5,75,64,358.67 | anchored |
| P2 | COM ← ACT | Use `ic` | 715 = 715 | 3,11,58,874.88 | anchored |
| P3 | COM ← M_TTM | −(negative TTM cells): C_TRAD, C_TRNS only | 2 = 2 | 39,60,077.67 | anchored |
| P4 | M_TTM ← COM | positive TTM cells | 19 = 19 | 39,60,078.00 | anchored |
| P5 | COM ← R_ROW | Use `exports` | 31 = 31 | 64,79,295.53 | anchored |
| P6 | R_ROW ← COM | Supply `imports_after_cif` | 30 = 30 | 69,46,906.03 | anchored |
| P8 | T_CUST ← COM | Supply `import_duty` | 19 = 19 | 2,28,887.27 | fixed |
| P9 | T_PSUB ← COM | Supply `product_subsidies` (negative) | 16 = 16 | −5,76,422.43 | fixed |
| P10 | T_PROD ← ACT | VA `net_production_taxes` | 33 = 33 | −57,442.00 | fixed |
| I3 | COM ← K_DSTK | Use `cii` | 20 = 20 | 3,82,329.00 | anchored |
| D4 | C_* ← X_DISC | 0 (NAS 1.1 discrepancy = 0) | 34 = 34 | 0 | fixed |
| **All** | | | **1,064 = 1,064** | | |

- **Value census.** 0 entries only in mine, 0 only in theirs, 0 with a value difference above ₹0.01 crore. The largest absolute difference is 4.7e-10.
- **Metadata.** Roles match on every entry. Status is `official` everywhere, component is `total`, and no entry has a confidence or bop tag.
- **Zero aggregates.** The only aggregate that sums to exactly 0 is T_PROD ← A_PADM (P10). It is left out as a structural zero.
- **Negative published values, kept as published.** P2 C_BSRE ← A_DWEL is −0.147881. I3 has four negatives: C_COAL −9,654, C_GJOM −13,992, C_MACH −2,537 and C_OILG −42. The entropy form keeps the sign, which is correct.
- **Anchored `tol_rel` as written.** It equals `round(n_cells/|value|, 6)` on all 952 anchored entries. It does **not** equal `n_cells/|value|`: see V-1.

### 1.2 Constraints

I rebuilt all 238 constraints (7 refs × 34 commodities or activities) with ids `<stem>.<code>`:

- P7: the 7 product-tax accounts × commodity.
- C1: commodity × the 10 HH accounts.
- C2: commodity × G_CEN, G_STA.
- I1: commodity × the 11 CAP accounts, refs I1 and I1a.
- I2: commodity × CAP, refs I2 and I2a.
- V1: F_LREG + F_LCAS × activity.
- V2: F_MIXD + F_GOSC × activity, with OS/MI + CFC as the target.

Where the SUT has no cell the target is 0, and `tol_abs` equals the number of cells aggregated.

The comparison found no missing or extra ids, and no mismatch in rows, columns, refs filter, target (largest difference 1.2e-10), `tol_abs`, `tol_rel` (= 0), kind (`equal`) or components (null). Sums of the targets:

| Ref | Σ target | Zero targets |
|---|---|---|
| P7 | 30,15,341.40 | 2 (C_DWEL, C_PADM) |
| C1 | 1,64,15,547.00 | 3 (C_OILG, C_OMIN, C_MTLS) |
| C2 | 31,21,027.14 | 28 |
| I1 | 92,45,762.49 | 22 |
| I2 | 3,76,232.00 | 33 (only C_GJOM) |
| V1 | 94,42,896.46 | 1 (A_DWEL) |
| V2 | 1,70,20,025.77 | 0 |

### 1.3 Totals against NAS 2026 (all targets read from data/clean)

| Item | SAM (production) | NAS | Difference |
|---|---|---|---|
| GDP, production side (P1 − P2 + P7 + P8 + P9) | 2,90,73,290.02 | 1.1 GDP 2,90,73,286.73 | +3.29 |
| GDP, expenditure side (C1 + C2 + I1 + I3 + I2 + P5 − P6) | 2,90,73,287.12 | 1.1 2,90,73,286.73 | +0.38 |
| GDP, income side (V1 + V2 + P10 + net product taxes); not in the builder's checks | 2,90,73,286.47 | 1.1 | −0.26 |
| GVA at basic prices | 2,64,05,483.79 | 1.1 2,64,05,479.98 | +3.81 |
| PFCE | 1,64,15,547.00 | 1,64,15,546.52 | +0.48 |
| GFCE | 31,21,027.14 | 31,21,027.37 | −0.24 |
| GFCF | 92,45,762.49 | 92,45,762.46 | +0.03 |
| CIS | 3,82,329.00 | 3,82,329.05 | −0.05 |
| Valuables | 3,76,232.00 | 3,76,231.72 | +0.28 |
| Exports | 64,79,295.53 | 64,79,295.53 | −0.00 |
| Imports (after CIF) | 69,46,906.03 | 69,46,906.27 | −0.24 |
| Product taxes (P7 + P8) | 32,44,228.66 | 32,44,229.14 | −0.47 |
| Product subsidies (−P9) | 5,76,422.43 | 5,76,422.38 | +0.05 |
| Output | 5,75,64,358.67 | 7.1 5,75,64,358.64 | +0.02 |
| IC | 3,11,58,874.88 | 7.1 3,11,58,878.67 / SUT note 3,11,58,876 | −3.79 / −1.12 |
| CE | 94,42,896.46 | 7.1 94,42,896.63 | −0.17 |
| OS/MI | 1,31,83,819.78 | 7.1 1,31,83,820.20 | −0.42 |
| CFC | 38,36,205.99 | 7.1 and 1.1 38,36,205.56 | +0.43 |
| Net production taxes (P10) | −57,442.00 | 7.1 −57,442.41 | +0.41 |
| Output by NAS group 1–8, 10 and 9 + 11 | | 7.1 | −0.64 to +1.91; 9 + 11: −1.17 (groups 9 and 11 alone differ by ∓1,56,915, the R&D reclassification) |

All 35 rows of `production_checks.parquet` pass. I recomputed the SAM side of 14 of them and they match to ₹0.01 crore.

### 1.4 Specific checks

- **Crude/gas label swap (io_tables Q1).** Confirmed in the clean data. In 2023-24 the row `sut_p043` (label "Natural Gas") holds crude: output 1,79,517 from industry `sut_i06` (crude petroleum) and imports 11,67,334. The row `sut_p044` holds gas: 29,224 from `sut_i07`. The 2022-23 rows are the right way round. Both products map to C_OILG, and industries 6 and 7 both map to A_OILG, so no SAM cell is affected. The clean rows carry `dim_other = label_swap_period=2023-24;swap_partner=…`. The swap would matter only for S6 or any product-level satellite, and S6 is not implemented.
- **CIF adjustment.** For every one of the 155 products, imports + `cif_adj` = `imports_after_cif` (largest miss 1.8e-12). The adjustment sits only on air transport (−54,540), water transport (−1,33,795) and insurance (−24,164.24). It offsets the `cif` memo row (+2,12,499.24). P6 therefore excludes the CIF memo, the SUT total row equals NAS 1.1 imports, and C_INSR has no import entry (its imports equal its CIF adjustment). The `sut_memo` satellite holds the adjustment by commodity (C_TRNS −1,88,335; C_INSR −24,164.24) and the memo rows as published. The memo rows (purchases of residents abroad 2,26,203; of non-residents in India 2,80,978) are in no entry or constraint: the P5, P6 and C1 totals equal the SUT's own `total` rows.
- **Signs.** P9 is negative on all 16 entries. P3, P4, P5, P6 and P8 are positive. P3 is the negated negative TTM, and no commodity both supplies and pays margins. P10 has both signs (net). D4 is 34 fixed zeros.
- **Fixed vs constraint.** P8, P9, P10 and D4 are fixed. The SUT cell vectors (P1–P6, I3) are anchored, which is deviation 1 in FRAMEWORK_REQUESTS.md. P7, C1, C2, I1, I2, V1 and V2 are constraints. This matches the brief s.4 as amended by deviation 1. Downstream plans read production's own sums for the fixed vectors (taxes.md: P9a −5,76,422.431949, P10a −57,441.998622, not NAS), as they must.
- **Non-additivity of the SUT.** Confirmed: supply − use at purchasers' prices misses by up to ₹0.499 crore per product; industry output − (IC + CE + OS/MI + CFC + net production taxes) by up to ₹0.855 crore; the TTM column sums to +₹0.333 crore; and the IC cells are ₹0.77 crore below the SUT 'total' row. With the constraint targets standing in for other blocks, my prior has a largest account imbalance of ₹1.41 crore (A_TRNS). Next are A_OILG +1.33, A_COAL +0.97, C_CHEM −0.96 and C_FOOD +0.94, then M_TTM +0.33.
- **Provenance.** There are 19 records, and every entry and constraint `prov_id` resolves to one of them. Each record is `official` with a method. For every ref, its inputs are exactly the distinct clean `prov_id`s of the SUT cells aggregated, and each resolves to an `official` record in `data/clean/io_tables/_provenance.parquet`. The D4 input is the NAS 1.1 record that carries `s1_1.discrepancies.current = 0`. The check targets resolve to NAS 1.1 / 7.1 / SUT records. The exception is V-5.

## 2. Findings

### V-1 (major, confirmed): the anchored allowance is rounded away when the entries are written

- **Where.** `pipeline/sam/framework.py:922` writes the entries with `io.write_parquet(ent, …)` and the default `decimals`. `pipeline/core/io.py` (`canonical_floats`, `DEFAULT_DECIMALS = 6`) rounds every float column, including `tol_rel`. Balancing then reads the rounded file: `pipeline/sam/assemble.py:38` `read_entries` → `run.py` `problem_from_frames` → `balance.py:182` (`z ≥ 1 − tol`, `z ≤ 1 + tol`).
- **Evidence (census of 952 anchored entries).**
  - 5 entries are written with `tol_rel = 0.0`, so the balancer pins them:
    - P1 A_CNST ← C_CNST (69,16,804.62)
    - P3 C_TRAD ← M_TTM (26,61,010.42)
    - P1 A_ITSV ← C_ITSV (24,29,656)
    - P1 A_DWEL ← C_DWEL (21,27,988.47)
    - P1 A_FINS ← C_FINS (20,42,510)

    Each is 1 SUT cell, so each should move by ₹1 crore.
  - 99 entries have a written allowance (`tol_rel·|value|`) more than ₹0.05 crore away from n_cells. The extreme cases are P1 A_CROP ← C_CROP at ₹28.78 against 27, and P3 C_TRAD at 0 against 1.
  - The framework's own rule "an anchored entry needs tol_rel > 0" (`framework.py:706`) holds in memory, but the stored and balanced data break it.
  - The builder's test `test_built_outputs_equal_a_fresh_build` compares against `canonical_floats(fresh)`, so it cannot see this.
- **Why it matters.** The documented design (₹1 crore per SUT cell, FRAMEWORK_REQUESTS deviation 1, SAM_GUIDE s.3) is not the one being balanced. Any block that sets `tol_rel < 5e-7` (a small absolute allowance on a large cell) silently gets a fixed entry.
- **Fix.**
  1. Write entries with `decimals={"value": 6, "tol_rel": None}`, or store the allowance as an absolute `tol_abs` column that rounding cannot zero.
  2. Re-validate in `read_entries` (anchored ⇒ `tol_rel > 0`).
  3. Add a test that the `tol_rel` read back equals the in-memory value.
  4. Then remove the strict xfail `test_anchored_allowance_is_one_crore_per_cell_as_balanced`.

### V-2 (major, plausible): the ₹1-crore-per-cell boxes make Clarabel stop at `optimal_inaccurate`

- **Evidence.** This comes from a throwaway harness I built (scratch only, not in the repo) on the framework's own `balance.problem_from_frames` and `cross_entropy`.
  - **How the harness is built.** Start with the 1,064 production entries as written. Add one free (medium) pseudo-entry per non-zero constraint target, standing in for the other blocks (C1 on H_R1, C2 on G_CEN, I1 as I1a on K_NFPR, I2 on K_HH, P7 on T_CGST, V1 on F_LREG, V2 on F_MIXD). Close each non-production account with one free (low) entry against I_OTHR. Keep all 238 production constraints.
  - **Result.**

    | Variant | Status | Max residual (₹ crore) |
    |---|---|---|
    | As written | `optimal_inaccurate` at the tight tolerances, and again on the automatic retry at Clarabel's defaults | 1.41 |
    | Full-precision `tol_rel` (V-1 fixed) | still `optimal_inaccurate` | |
    | Anchored `tol_rel` floored at 1e-5 | `optimal_inaccurate` | |
    | Anchored `tol_rel` floored at 1e-4 | `optimal` | 2e-4 |
    | Anchored `tol_rel` floored at 1e-3 | `optimal` | 5e-5 |
    | Anchored turned into free/high | `optimal` | 2e-5 |
    | Anchored with `tol_rel < 1e-4` made fixed | infeasible | |

    Under SAM_GUIDE s.8 and `balance.cross_entropy`, any final status other than `optimal` fails the run.
  - **The cause.** Interior-point exponential cones with boxes of relative width 1e-7 to 1e-5 around z = 1. Nothing in the production block is wrong: the problem is how the allowance is modelled.
  - **A second weakness of the same design.** M_TTM has only anchored entries (P3, P4), and the exact polish works on free entries only (`balance.py:332`). If the solver leaves more than ₹0.01 crore on M_TTM, the polish cannot reach it and the run fails with `unreachable_accounts = [M_TTM]`.
  - **Caveat.** The other blocks' real entries will differ from my pseudo-entries, so this is a strong expectation, not a proof.
- **Fix (framework decision).** Model an anchored rounding allowance additively:
  - x = a + d with |d| ≤ n_cells crore and a quadratic or weighted-L1 cost on d (no exponential cone), or
  - keep the entropy term but put a documented floor on the anchored width (e.g. 1e-4 relative; that loosens A_CNST to ±₹692 crore, which is too loose for an "official" cell), or
  - make the SUT cells fixed and absorb the SUT's ≤ ₹1.41 crore account misses in a small set of logged free "SUT rounding" entries (new cells: needs a DECISIONS entry).

  Also let the polish use anchored entries within their bounds. In any case, add a smoke test now: the production prior closed with pseudo-entries (as above) must balance to `optimal` before the other blocks land.

### V-3 (minor): the "published in whole crore" premise is false

- **Where.** `pipeline/sam/blocks/production.py:24`, FRAMEWORK_REQUESTS.md deviation 1, and the production-1 wording.
- **Evidence.** The 2023-24 clean SUT cells that are not whole crore:

  | Column | Non-integer cells |
  |---|---|
  | IC | 1,691 of 2,792 |
  | Product taxes | 108 of 108 |
  | Import duty | 110 of 110 |
  | Imports after CIF | 124 of 124 |
  | Exports | 127 of 129 |
  | TTM | 131 of 133 |
  | Output | 77 of 496 |
  | CE / OS/MI / CFC | about 51 of 67 each |

  Only PFCE, CII and valuables are whole numbers. The non-additivity is real (see 1.4), but ₹1 crore per cell is a stated assumption sized to cover it, not a rounding bound.
- **Fix.** Reword: "the published SUT is not exactly additive (≤ ₹0.50 per product, ≤ ₹0.86 per industry, TTM +₹0.33); ₹1 crore per cell is an assumed allowance". Otherwise block builders who copy the pattern will justify allowances by rounding that does not exist.

### V-4 (minor): the I2 constraint is labelled "Gap map I2" but it is I2 + I2a

- **Where.** `production.py:144-145`.
- **Evidence.** The gap map defines I2 as NAS 1.9 household gold (1,72,127) on K_HH. The production constraint `valuables.c_gjom` is the SUT total valuables (3,76,232 = I2 + I2a) over all CAP accounts with refs I2 and I2a. The capital_financial plan uses exactly this reading, so the numbers are consistent. The description and method, however, say "Gap map I2".
- **Fix.** Name it "valuables by commodity (I2 + I2a, SUT)" in the description and method.

### V-5 (minor, confirmed): wrong `source_id` on the I2 constraint record

- **Evidence.** `sam_production:32d36a196321` has `source_id = mospi_nas_2026_publication`, which `ctx.prov` takes by default from the gap map's primary source for I2. Its only input, `io_tables:f6d331e96230`, is SUT (`mospi_sut_2022base`).
- **Fix.** Let `_prov` in `production.py:233` pass `source_id="mospi_sut_2022base"`. More generally, `ctx.prov` could default `source_id` from the inputs when they share one source. Then remove the strict xfail `test_record_source_id_matches_its_inputs`.

### Not findings (checked and fine)

- Brief deviation 1 (anchored rather than fixed) is justified by the non-additivity. It is the modelling of the allowance that needs fixing (V-2).
- The concordances are complete and consistent with `io_tables_sam34_sectors.csv`.
- `vintage="latest"` changes nothing today (one vintage).
- Zero-target constraints with `tol_abs = 0` encode "the SUT has no such use", and the downstream plans agree (C2a on 6 commodities; no PFCE on C_OILG, C_OMIN, C_MTLS).
- The constraint account lists are stored in accounts.yaml order, which is how duplicate constraints are detected.
- `tol_rel` above 1 on tiny cells (largest 74.2 on a ₹0.013 crore cell) is still only a ₹1 crore move.

## 3. How to reproduce

- `uv run python -m pipeline test tests/verify/test_sam_production_spotcheck.py` gives 32 passed, 2 xfailed (strict: V-1 and V-5).
- `uv run python -m pipeline test tests/sam tests/verify` gives 568 passed, 6 skipped (balancing audit, no full run), 2 xfailed.
- Hygiene tests pass, and `manifest --check` is up to date.
- The V-2 harness is described above. It needs only `pipeline.sam.balance` plus the written production parquet files.
