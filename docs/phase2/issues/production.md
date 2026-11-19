# production: Phase 2 issues

Block `pipeline/sam/blocks/production.py` (the template block), built 2026-09-30 from io_tables (SUT 2023-24, vintage 2026-08-31) and mospi_nas_2026 (Statements 1.1 and 7.1, vintage 2026-08-31). Outputs: 1,064 entries, 238 constraints, 1 satellite (`sut_memo`), 35 control-total checks (all pass), 19 provenance records.

| # | Severity | Issue | Impact / what the block does | Status |
|---|---|---|---|---|
| production-1 | minor | The published SUT is not exactly additive (not a whole-crore rounding effect: many cells carry decimals): per product, supply − use misses by up to ₹0.50 crore; per industry, output − (IC + CE + OS/MI + CFC + net production taxes) by up to ₹0.86 crore; the TTM column sums to +₹0.33 crore; the IC cells sum to ₹3,11,58,874.88 crore against the SUT's own 'Total Use' row ₹3,11,58,875.64 crore (−0.77). With `fixed` entries M_TTM and several commodities could never close to ₹0.01 crore | Entries built from SUT cells (P1–P6, I3) are `anchored` with an assumed ₹1 crore allowance per SUT cell aggregated (written unrounded since the Wave A review, V-1); tax vectors (P8, P9, P10) and D4 are `fixed`; constraint targets carry tol_abs = n_cells crore. Deviation 1 in FRAMEWORK_REQUESTS.md | OPEN (by design) |
| production-2 | minor | P6a (imports by using activity, optional multiplier variant) not implemented: it needs the ICIO/ADB import-share prior mapped to 34 activities and a RAS, which is not cheap | No SAM cell depends on it (memo only). Listed in the block catalog's `refs_not_implemented` | OPEN |
| production-3 | minor | S6 (energy physical SUT by activity) not implemented: io_tables_energy_psut is by ISIC industry group (PJ); mapping to the 34 activities needs a new committed concordance | Satellite only; listed in `refs_not_implemented` | OPEN |
| production-4 | minor | GDP by production from the aggregated SUT is ₹3.29 crore above NAS 1.1 (GVA +3.81; IC −3.79 against NAS 7.1, −1.12 against the SUT note's 3,11,58,876). All within the ₹5 crore check tolerance and consistent with RECONCILIATION.md (GDP-5/6: ≤ ₹3 crore) | Logged; no adjustment (the anchored allowance absorbs it in balancing) | OPEN (explained: SUT rounding) |
| production-5 | minor | SUT memo rows ('CIF' in the Supply table: imports −2,12,499, CIF Adj +2,12,499; 'Purchases of Residents abroad' 2,26,203; 'Purchases of Non-Residents in domestic market' −2,80,978 in PFCE / +2,80,978 in exports) are already spread over the product rows (gap map P5/P6 notes) | Excluded from every entry and constraint (only `sut_pNNN` rows and `sut_iNN` columns are summed); kept as published in satellite `sut_memo` with the CIF adjustment by commodity (C_TRNS −1,88,335; C_INSR −24,164) | CLOSED |
| production-6 | minor | Aggregated cells that are exactly 0 are not written (a structural zero is absent): P10 for A_PADM (the SUT prints 0 net production taxes for public administration). C_INSR has no imports after the CIF adjustment (imports 24,164 = CIF adjustment), so no R_ROW <- C_INSR entry | Logged at build time; no zero entries except D4 | CLOSED |
| production-7 | minor | NAS group check: SUT industry 58 (education & research) holds R&D, which NAS 7.1 files under professional services (group 9) (RECONCILIATION.md IND-re-output) | Output is checked by NAS group for groups 1–8 and 10, and for groups 9 + 11 together (−₹1.17 crore); the 34-sector mapping is unaffected (A_EDUC is education & research) | CLOSED |
| production-8 | minor | io_tables-1 (Q1): the 2023-24 rows of SUT products 43/44 are swapped relative to their labels | Both map to C_OILG: no effect on any SAM cell | CLOSED |
| production-9 | info | Q6 (pesticides carry −₹62,440 crore of product subsidy with zero imports) and Q7 (−₹1,05,007 crore of product subsidy on Trade with no documented composition) | Kept as published in T_PSUB <- C_CHEM and T_PSUB <- C_TRAD (fixed); the Centre/State split is the taxes block's (P9a) | OPEN (asked of NAD in Phase 0) |
| production-10 | info | Every read uses `vintage="latest"`; today io_tables and mospi_nas_2026 carry one vintage (31 Aug 2026) for 2023-24, so the choice changes nothing. If a later vintage arrives, the block follows it and the checks show any shift | Stated in the block docstring and each record's vintage | CLOSED |
| production-11 | minor | Wave A review (docs/phase2/verify/framework_production_block_verification_spec_rule_.md): V-1 anchored tol_rel was rounded to 6 decimals on write (5 entries at tol 0); V-4 the valuables constraints were described as 'I2' though their target is I2 + I2a; V-5 the valuables record named NAS as its source | V-1: tol_rel written unrounded (12 significant digits) by the framework; V-4: description and method now say 'valuables by commodity = I2 + I2a'; V-5: source_id now defaults to the inputs' source (mospi_sut_2022base). Rebuilt 2026-09-30 | CLOSED |

## Control totals vs sources (₹ crore, 2023-24; every target read from clean data)

| Check | SAM (production) | Source | Diff |
|---|---|---|---|
| GDP, production side (output − IC + product taxes + import duty + subsidies) vs NAS 1.1 GDP | 2,90,73,290.02 | 2,90,73,286.73 | +3.29 |
| GDP, expenditure side (PFCE + GFCE + GFCF + CIS + valuables + exports − imports) vs NAS 1.1 | 2,90,73,287.12 | 2,90,73,286.73 | +0.38 |
| GVA at basic prices vs NAS 1.1 | 2,64,05,483.79 | 2,64,05,479.98 | +3.81 |
| Output (P1) vs NAS 7.1 | 5,75,64,358.67 | 5,75,64,358.64 | +0.02 |
| Intermediate consumption (P2) vs NAS 7.1 | 3,11,58,874.88 | 3,11,58,878.67 | −3.79 |
| Intermediate consumption (P2) vs SUT note Table 9 | 3,11,58,874.88 | 3,11,58,876.00 | −1.12 |
| PFCE (C1 targets) vs NAS 1.1 | 1,64,15,547.00 | 1,64,15,546.52 | +0.48 |
| GFCE (C2 targets) vs NAS 1.1 | 31,21,027.14 | 31,21,027.37 | −0.24 |
| GFCF (I1 targets) vs NAS 1.1 | 92,45,762.49 | 92,45,762.46 | +0.03 |
| Change in inventories (I3) vs NAS 1.1 | 3,82,329.00 | 3,82,329.05 | −0.05 |
| Valuables (I2 targets) vs NAS 1.1 | 3,76,232.00 | 3,76,231.72 | +0.28 |
| Exports (P5) vs NAS 1.1 | 64,79,295.53 | 64,79,295.53 | −0.00 |
| Imports after CIF (P6) vs NAS 1.1 | 69,46,906.03 | 69,46,906.27 | −0.24 |
| Product taxes (P7 targets, 30,15,341.40) + import duty (P8, 2,28,887.27) vs NAS 1.1 taxes on products | 32,44,228.66 | 32,44,229.14 | −0.47 |
| Product subsidies (−P9) vs NAS 1.1 | 5,76,422.43 | 5,76,422.38 | +0.05 |
| CE (V1 targets) vs NAS 7.1 | 94,42,896.46 | 94,42,896.63 | −0.17 |
| OS/MI + CFC (V2 targets) vs NAS 7.1 | 1,70,20,025.77 | 1,70,20,025.76 | +0.02 |
| Net production taxes (P10) vs NAS 7.1 | −57,442.00 | −57,442.41 | +0.41 |
| Output by NAS group (1–8, 10; 9 + 11) vs NAS 7.1 | | | between −0.64 and +1.91 |
| Sums vs the SUT's own 'total' rows (imports after CIF, import duty, subsidies, product taxes, exports, PFCE) | | | 0.00; IC −0.77 |

No difference exceeds ₹5 crore; none needs an adjustment.

## Assumptions (each also a provenance record)

- The ₹1 crore-per-cell rounding allowance (production-1) is stated in every P1–P6/I3 record's method.
- D4: NAS 1.1 'Discrepancies' is 0 for 2023-24, so all 34 C_* <- X_DISC entries are 0 (fixed). A non-zero year needs an allocation rule by commodity first; the block stops with an error rather than inventing one.

## Framework requests

None open from this block (the framework agent built it; deviations are in FRAMEWORK_REQUESTS.md).
