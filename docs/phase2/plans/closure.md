# Phase 2 block plan: `closure` (K4a, D1, pre-balancing diagnostics)

Written 2026-09-30 by the `closure` data scout (research only). Every value below was read from `data/clean/<unit>/*.parquet` as built on 2026-09-29 (manifest unchanged), using throw-away polars scripts in the session scratchpad. Nothing under `pipeline/` was written and no `build`/`sam`/`repro` command was run. Amounts are ₹ crore, current prices, FY 2023-24, unless stated. "NAS 2026" = vintage 2026-08-31, estimate stage Final for 2023-24, base 2022-23.

`docs/phase2/SAM_GUIDE.md` does not exist yet. This plan follows `docs/phase2/DESIGN_BRIEF.md`. Where the guide later differs, the guide wins and the builder notes the difference in `docs/phase2/FRAMEWORK_REQUESTS.md`.

---

## 1. Summary (plain English)

- `closure` runs last and writes only **20 cells**:
  - household gross saving for each of the 10 household groups (**K4a**, `K_HH ← H_g`);
  - each group's share of the published household discrepancy (**D1**, `X_DISC ← H_g`).

  It also produces the **pre-balancing diagnostics** (DESIGN_BRIEF §5.4).
- **Household saving by group is a residual**: each group's income, less its consumption, income tax, transfers paid and D1 share. The 10 residuals must add up to NAS household saving, **₹58,90,330.45 cr**. Before balancing they will not. The gap (called **Z** here) measures how far the other blocks' household property income and transfers are from what NAS implies. It is the headline number this block reports.
- **D1 = ₹5,71,133.27 cr**: NAS household disposable income less household consumption less household saving. It is pinned (never balanced) and split across groups in proportion to each group's gross income, as the gap map says.
- **Finding 1: two accounts contain only fixed cells, and their published pieces do not add up exactly.**
  - **X_DISC**: D1 − D2 − D3 = **+₹0.11 cr** (with the SUT CIF figure) or **+₹0.34 cr** (with the NAS 6.1 CIF figure). The balance tolerance is ₹0.01 cr, and the solver cannot fix an account that has no free cells. Recommended fix: write D1's total as D2 + D3 + D4 exactly as the other blocks wrote them, and log the ₹0.11 cr difference from the published D1.
  - **M_TTM**: the SUT margin column nets to **+₹0.33 cr**, not 0. This belongs to `production`.
- **Finding 2: official totals alone fix how much property income and transfers each institution must receive or pay, net.**

  | Institution | Net property income and current transfers, after income taxes (₹ cr) |
  |---|---:|
  | Households | receive +36,30,975 |
  | Private NFCs | pay −22,08,619 |
  | Public NFCs | pay −7,04,183 |
  | General government | pay −1,83,401 |
  | Public FCs | receive +1,01,277 |
  | Private FCs | pay −1,96,538 |

  These six sum exactly (to ₹0.001 cr) to the net inflow from the rest of the world, ₹4,39,511 cr. The old-base 2022-23 accounts show the same pattern (households +₹37,94,094 cr). Whatever the income-flow blocks (`fincorp`, `government`, `taxes`, `rest_of_world`) fail to deliver shows up as an imbalance in these institutions' accounts before balancing.
- **The largest swing items:**
  - the imputed pension contributions that households pay back to government (R9b, roughly ₹4.5–6.8 lakh cr). They push government and households in opposite directions;
  - whether household interest is recorded net of FISIM (household FISIM in PFCE is ₹6,02,897 cr);
  - the household share of income tax.
- **Everything else balances by construction to within about ₹1-2 cr of published rounding** if the blocks use the series named here: activities, commodities, factors, rest of the world (current and capital), households' capital account and inventories. The exceptions:
  - `I_OTHR`, which carries the FSF's own non-closure of ₹49,902 cr;
  - the tax accounts, if cash receipts are used instead of the SUT totals (gap ₹1,60,570 cr);
  - the Centre-versus-State split of grants (up to ₹1.41 lakh cr).

---

## 2. Ref-by-ref table

| Ref | Cell (row ← col) | Entries to write | Source datasets / series_ids | 2023-24 values (₹ cr) | Role | Method (summary; full steps in 2.1-2.2) | Status label |
|---|---|---|---|---|---|---|---|
| **K4a** | `K_HH ← H_R1 … H_U5` | 10 entries, one per group; `component = total`; `bop_function = null` | **Control total:** `mospi_nas_2026_s1_9` / `s1_9.household_sector.current` (prov `mospi_nas_2026:0e67570b45b0`). Identical: `mospi_nas_2026_s1_14` / `s1_14.households_npish.gross_savings.current` (`mospi_nas_2026:052393d058c2`) and `mospi_nas_2026_s5_3` / `s5_3.household_saving_1_2_3_4.current` (`mospi_nas_2026:6c29d7e7857c`). **Inputs:** every prior entry of other blocks in rows or columns `H_*` (read with `ctx.block_entries`). **Plausibility only:** `io_tables_ifpri_2223_datapaper` / `ifpri.t11.savings_rate.{q1..q5,rural,urban,all}` (period 2022-23, status estimated, vintage 2024-10-01, prov `io_tables:b2c30c4a6000`). **Cross-check, not used:** `rbi_financial_accounts_hbs_saving` / `t11.gross_saving_hh.base2022.current` | Total **58,90,330.446044** (NAS 2026, Final). HBS T11: 59,63,550 (vintage 2026-07-31). IFPRI savings rates: q1 18.4, q2 18.9, q3 20.7, q4 24.1, q5 23.9, rural 21.3, urban 24.0, all 22.5 (%, 2022-23, old base) | `free`, confidence `low` | Residual of each group's current account: gross income − all outlays other than saving − D1 share. Σ is constrained to the NAS total by the K4 constraint (§3). The prior is the pure residual (option A). The aggregate gap Z is reported, not pre-allocated | `estimated` (residual on an official total). UI: "official total, estimated by group" |
| **D1** | `X_DISC ← H_R1 … H_U5` | 10 entries; `component = total` | **Published total:** `mospi_nas_2026_derived_residuals` / `derived.household_residual.current` (derived from St 1.14 GDI − FCE − gross saving; prov `mospi_nas_2026:5ae8b8592c30`). Inputs of that derivation: `s1_14.households_npish.gross_disposable_income.current`, `…final_consumption_expenditure.current`, `…gross_savings.current`. **Identity cross-check:** `mospi_nas_2026_s1_1` `s1_1.gndi.current − s1_1.pfce.current − s1_1.gfce.current − s1_1.gross_saving.current`. **Written total:** Σ of the D2 (`rest_of_world`), D3 (`capital_financial`) and D4 (`production`) entries | Published **5,71,133.272525**. The same figure comes from the 1.1 identity (2,95,44,505.76 − 1,64,15,546.52 − 31,21,027.37 − 94,36,798.59). D2 + D3 + D4 = **5,71,133.165043** with the SUT CIF (2,12,499.23649 + 3,58,633.928553 + 0), or 5,71,132.928553 with the NAS 6.1 CIF (2,12,499.00) | `fixed` (X_DISC cells are pinned) | Total = D2 + D3 + D4 as written, so the all-fixed X_DISC account closes exactly. It must lie within ±₹1 cr of the published 5,71,133.27, and the difference (₹0.107 cr expected) is logged. Split pro rata to each group's prior gross income (H_g row total), with the rounding remainder placed on the largest group | Total `derived` (official figure; see §6 R9). Split `estimated`. UI: "statistical discrepancy (NAS household residual), allocated by income" |
| (§5.4 diagnostics) | no cells | Satellites only: `prior_imbalance`, `constraint_gaps`, `institution_gaps`, `hh_saving`, `xdisc_identity` (§4) | All built block entries and constraints, plus the official requirement series in 2.4 | See 2.4 | n/a | See 2.3 | `derived` |

Phase 1 coverage: K4a is **partial** (NAS 1.9 control total plus the IFPRI check; the split exists only as a residual of the other blocks). D1 is **covered** (`mospi_nas_2026_derived_residuals`, full).

### 2.1 K4a: steps for the builder

1. **Collect.** Read the entries of every other block (`production`, `households`, `factors`, `taxes`, `government`, `fincorp`, `rest_of_world`, `capital_financial`). Keep entries with `row ∈ H_*` (resources) or `col ∈ H_*` (uses).
2. **Validate. Fail loudly on any of these:**
   - an entry with `row ∈ H_*` **and** `col ∈ H_*` (intra-household flows are memo only per ACCOUNT_STRUCTURE §11, so they must be absent);
   - an H-touching ref outside this whitelist. Resources: F1a, F2, F3a, F3b, F3c, R8a, R9a, R9c, R10, R11a, R17, plus any ref `fincorp` declares for government or FC interest to households at group level. Uses: C1a, C4a, C4b, C4c, C4d, T3a, R9b, R16, R12a, R17, R5. Any other ref in an H column, e.g. PF or life-insurance contributions booked as current transfers, is a double count (§6 R12);
   - a missing group, i.e. a household ref present for some groups but not others;
   - a non-finite value.
3. **Gross income.** `inc_g` = Σ entries with row = H_g.
4. **Outlays.** `out_g` = Σ entries with col = H_g, other than K4a and D1.
5. **D1 split.** Compute D1_g as in §2.2 before the residual.
6. **Residual (option A).** `K4a_g = inc_g − out_g − D1_g`, at full precision, then rounded to 6 decimals. Fail if |K4a_g| < ₹1 cr: the entry would be absent or unstable, because z ≥ 0 locks its sign (§6 R6).
7. **Aggregate gap.** Z = Σ_g K4a_g − 58,90,330.446044. Report Z in `hh_saving` and in `docs/phase2/issues/closure.md` with its decomposition by flow class (see `institution_gaps`). **Do not rescale.**
   - The K4 constraint (§3) forces Σ K4a to the NAS total during balancing, so the solver moves the free household income and transfer entries by Z in total.
   - Option B (pre-shift each group by Z × gross-income share) is computed and published in `hh_saving` as an alternative, not written as entries. Rationale in §5 C7.
8. **Plausibility (findings, never constraints).** For each group compute:
   - saving / gross income;
   - saving / (gross income − T3a − R9b − R16 − R12a − R17 premiums − R5 interest);
   - saving / (PFCE + saving), the nearest analogue of IFPRI's "total spending" rate.

   Compare the rural and urban aggregates with IFPRI rural 21.3% and urban 24.0%. IFPRI quintiles are **national**, while ours are within rural and within urban, so they cannot be compared quintile by quintile. List each group whose sign differs from IFPRI (all IFPRI rates are positive) and each group with a rate outside [−25%, +50%] of gross income.
9. **Provenance.** One `ctx.prov(ref='K4a', status='estimated', …)` record per entry. `inputs` = the prov_ids of every H_g entry used plus the K4 control. `method` = "Residual of household group's current account (gap map K4a): gross income − consumption − current taxes − current transfers and property income paid − D1 share; Σ constrained to NAS 2026 St 1.9 household saving".

### 2.2 D1: steps for the builder

1. **Written total.** `D1_tot = Σ D2 entries (R_ROW ← X_DISC) + Σ D3 entries (K_* ← X_DISC) + Σ D4 entries (C_* ← X_DISC)`, read from the built blocks.
2. **Check.** |D1_tot − 5,71,133.272525| ≤ ₹1 cr, else fail. Expected difference +0.107 cr with the SUT CIF, or +0.344 cr with the NAS 6.1 CIF. Log it as "X_DISC identity rounding: GDP expenditure components of NAS 1.1 do not add to the published zero discrepancy at 2-decimal precision".
3. **Key.** `key_g = inc_g / Σ inc`, with inc_g as in 2.1 step 3, computed from **prior** entries.
4. **Split.** `D1_g = D1_tot × key_g`, rounded to 6 decimals. The largest-income group absorbs the rounding remainder so Σ D1_g = D1_tot exactly.
5. **Entries.** role `fixed`, status `estimated` (allocation). The total's prov record is `derived`, with inputs = the D2, D3 and D4 prov_ids plus `mospi_nas_2026:5ae8b8592c30`.
6. **Sensitivity.** Publish the alternative splits by PFCE share and by population share (both from `households`' `hh_keys`) in `hh_saving`, so the site can show the band.

### 2.3 Pre-balancing diagnostics: what the block computes

All computed on the **assembled prior**: all blocks' entries including `closure`'s own, before balancing.

1. **`prior_imbalance`.** One row per account in `accounts.yaml` (128), with:
   - `group`, `row_total`, `col_total`, `imbalance = row − col`, and `pct = imbalance / max(row_total, col_total)`;
   - `n_free_row` and `n_free_col` (count of non-fixed entries). Accounts with zero free entries are flagged: they cannot be balanced;
   - `rank` by |imbalance|.

   Assertion: Σ imbalance over all 128 accounts = 0 within 1e-6 (the global SAM identity; a failure means an entry was lost).
2. **`constraint_gaps`.** For every declared constraint of every block: prior sum, target, band, `gap = prior − target`, `outside_band` flag. This shows which official totals the prior misses before the solver moves anything.
3. **`institution_gaps`.** For each institution (each H_g, the 10-group total, E_NFPU, E_NFPR, E_RBI, E_BANK, E_NBFC, E_INSP, FC total, G_CEN, G_STA, GG total):
   - the **delivered** net distributive flows by flow class: property income received and paid (refs R3a, R4, R5, R6, R7, R8, R8a, R9c, R13, R14, R14a); current taxes (T3a, T4a, and T1/T1a on the government side); social flows (R9, R9a, R9b); other current transfers (R1, R2, T2b, R10, R11a, R12a, R15, R16, R17, R18);
   - the **required** amount from official totals (table 2.4-C);
   - `gap = delivered − required`.

   The investigating agent uses this to trace each large prior imbalance to the flow class and source that cause it, as DESIGN_BRIEF §5.4 requires.
4. **`xdisc_identity`.** D1 (published), D2, D3, D4, D1_tot as written, and the residual.
5. **Report hand-off.** `report.py` reads these satellites for the "before balancing" section of BALANCING.md. The builder adds a test that `prior_imbalance` equals the framework's own account totals from `assemble.py` (one computation, checked twice).

### 2.4 Expected pre-balancing imbalances, from official totals

**A. Accounts that balance by construction** (provided the named series are used). Imbalances are rounding only.

| Account(s) | Identity | Values (₹ cr) | Expected prior imbalance | Owner |
|---|---|---|---|---|
| ACT (34) | SUT output = IC + GVA per industry | max \|output − IC − GVA\| = 0.93 per SUT industry; Σ over 67 = 2.46 | ≤ ~₹2 cr per SAM activity. All entries are fixed, apart from the V1a/V2a splits under per-activity V1/V2 constraints, so those constraints need `tol_abs` ≥ ₹2 cr (§6 R8) | production |
| COM (34) | SUT supply (purchasers') = total use per product | max \|supply_pp − use_pp\| = 0.50 per SUT product; Σ over 155 = 1.47 | ≤ ~₹2 cr per commodity, if C1a, C2a, I1a, P7a, I2 and I2a each preserve the SUT commodity totals | production, households, government, capital_financial, taxes |
| **M_TTM** | Σ P4 (margins paid, positive TTM entries) = Σ P3 (margin services, negative entries) | P4 = 39,60,078.00; P3 = 39,60,077.67 (`io_tables_sut_supply` `supply.ttm.sut_pNNN.current`; the published `supply.ttm.total.current` = 0.0 is rounded) | **+₹0.33 cr, with every entry fixed: cannot be balanced** (§6 R1) | production |
| F_LREG + F_LCAS | V1 + V3 − V4 = F1 | 94,42,896.46 + 62,344.24 − 30,635.91 = 94,74,604.79 vs `derived.ce_receivable_by_residents.current` 94,74,604.95 | ~₹0.2 cr rounding; free V1a/F1a entries absorb it | factors |
| F_MIXD + F_GOSC | SUT OS/MI + CFC = Σ sector gross OS (7.1A, 7.1B, 8.15.1) + household gross OS/MI (7.1C) | SUT 1,31,83,819.78 + 38,36,205.99 = 1,70,20,025.77; NAS sectors 1,70,20,025.76 | ~0; F_GOSC closes only if F3 = household gross OS/MI (97,71,430.53) − F_MIXD | factors |
| R_ROW | imports + D2 + CE paid + property income paid + transfers paid = exports + CE received + property income received + transfers received + K5 | row 69,46,906.03 (SUT after CIF) + 2,12,499.24 (SUT CIF) + 30,635.91 + 7,24,611.52 + 99,912.81 = 80,14,565.51; col 64,79,295.53 + 62,344.24 + 2,80,907.32 + 9,83,127.72 + 2,08,890.71 = 80,14,565.52 | −₹0.01 cr with the **SUT** CIF; −₹0.24 cr with the NAS 6.1 CIF (2,12,499.00) | rest_of_world |
| K_ROW | K5 + India's acquisition of foreign assets = India's net incurrence of liabilities + net capital account with RoW | 2,08,890.71 + 6,70,569.37 = 8,79,460.08; 8,86,570.33 + (−6,999.68 + 1,555.69 − 1,666.26 = −7,110.25) = 8,79,460.08 (NAS 6.1 items 12-17) | 0 | rest_of_world |
| K_HH | K4 + liabilities (K8a) + D3→K_HH (= I2a) = GCF_hh + I2 + I2a + financial assets (K7a) | 58,90,330.45 + 19,09,286.70 = 77,99,617.15; 40,25,292.07 + 1,72,126.57 + 36,02,198.51 = 77,99,617.15 (I2a appears on both sides) | 0 **if and only if** Σ K4a = NAS total, the D3 posting to K_HH equals the valuables cell I2a to the paisa, and no other capital transfer is posted to K_HH | closure, capital_financial |
| K_DSTK | Σ sector CIS (1.14 GCF − 1.11 GFCF) = SUT CII | 96,28,091.52 − 92,45,762.47 = 3,82,329.05 vs `use.cii.total.current` 3,82,329.00 | +0.05, absorbed by free I3a entries | capital_financial |
| **X_DISC** | D1 = D2 + D3 + D4 | 5,71,133.27 vs 5,71,133.17 (SUT CIF) / 5,71,132.93 (NAS CIF) | +0.11 / +0.34 with the published D1; **0 with the method in 2.2** | closure |

**B. Accounts that will be out of balance, or whose closing residual is itself a finding**, from published disagreements in `docs/phase1/RECONCILIATION.md` (values recomputed from Parquet by `tests/cross`).

| Account(s) | Expected prior gap (₹ cr) | Cause | Owner to investigate |
|---|---|---|---|
| Tax accounts T_CGST … T_OPRT, T_CUST | **+1,60,570** (TAX-1: SUT product taxes + import duty 32,44,229 vs Union + State receipts 30,83,659) if any tax block writes G ← T at cash; 0 if T1a/T2x are fitted to the SUT (gap-map rule "the SUT margin wins") | State motor-vehicle tax 1,10,327 is the leading candidate. The remaining 50,243 is unexplained | taxes, government |
| T_PSUB | +43,244 (TAX-9, SUT vs budgets) if P9a is not scaled to the SUT per commodity | State St 36 mixes product and production subsidies; local bodies are missing | government |
| G_CEN vs G_STA (the GG total is unaffected) | Depends on the grants measure: GOV-9 +67,246 (Union AFS 3601 + UT transfers vs States' receipts); GOV-15 −1,41,341 (IGAS-2 vs MH 3601); GOV-16 −71,543; GOV-10 +4,605 (FC grants); GOV-7 −1,431 (interest on Central loans) | H9: releases outside State treasuries. If `G_STA ← G_CEN` uses States' receipts while K3a (Centre) is built from the full Union outflow, G_CEN's column is short by the Union-side excess | government |
| Institutional current accounts (H_*, E_*, G_*) | Delivered − required, table C below. Size unknown until the income-flow blocks run; lakh-crore scale is plausible (H6) | No new-base sequence of institutional accounts exists; the transfer flows are built bottom-up | fincorp, government, taxes, rest_of_world |
| K_NFPU, K_NFPR, K_RBI, K_BANK, K_NBFC, K_INSP, K_MUTF, K_GCEN, K_GSTA | 0 by construction **if** `capital_financial` posts K9 as each sector's residual. The K9 sizes are the finding: FIN-1 (NAS saving − GCF vs FSF net financial transactions) NFC −5,73,095 (−72%), FC +2,28,704, GG +1,20,394, before the D3 remainder of 1,54,529 is allocated | FSF 2023-24 is on the old base; HDFC merger; D3 is not sectored | capital_financial |
| K_HH | Z (the household aggregate gap) until the K4 constraint binds. The FIN-1 household gap (+2,95,178) is moved to counterparties by K7b, not to K_HH | see §6 R2 | closure, capital_financial |
| I_OTHR | ≈ −49,902 (FIN-3: FSF all-sector assets 1,38,43,741 vs liabilities 1,38,93,643), plus any asymmetric HDFC-merger treatment | Σ_s K9_s = FSF non-closure once K7b replaces the household and RoW rows | capital_financial |

**C. Required net distributive flows by institution (new base 2023-24) vs old base 2022-23.**

"Required" = what the SAM's property income, current taxes and current transfers (D4 + D5 + D6 + D7, net, gross basis) must deliver for each institution to reach its NAS totals:

- households: GDI − CE received − gross OS/MI;
- NFC and FC: gross saving − gross operating surplus (their GDI = saving);
- general government: GDI − GOS − net taxes on production and imports.

Once every account balances, the C1, C2, K1, K2, K3, K4 and D1 totals together imply these amounts. No extra constraint is needed (§3).

| Institution | New base 2023-24 inputs (₹ cr) | **Required net** | Old base 2022-23 (NAS 2024 SOA, base 2011-12, FRE, vintage 2024-06-05) |
|---|---|---:|---:|
| Households + NPISH | GDI 2,28,77,010.24 (`s1_14.households_npish.gross_disposable_income.current`) − CE received 94,74,604.95 (`derived.ce_receivable_by_residents.current`) − gross OS/MI 97,71,430.53 (`s7_1c.total.os_mi.current` 85,90,351.69 + `s7_1c.total.cfc.current` 11,81,078.84) | **+36,30,974.76** | +37,94,094 (D4 received 47,12,396; D4 paid 22,49,807; D5 6,42,596; D6+D7 received 19,74,102; `mospi_nas_2026_oldbase_soa_s5_0`) |
| Public NFC | saving 4,62,996.25 − gross OS 11,67,179.33 (7.1A total OS and CFC less the financial row and 8.15.1) | **−7,04,183.08** | −4,39,905 (`oldbase_soa_s2_1`) |
| Private NFC | saving 24,10,408.53 (already net of D43 1,63,704.27 paid to RoW) − gross OS 46,19,027.77 (7.1B total less the financial row) | **−22,08,619.25** | −24,96,168 (`oldbase_soa_s2_2`) |
| Public FC | saving 5,35,509.90 − gross OS 4,34,232.62 (`s7_1a.financial.os` + `.cfc`) | **+1,01,277.28** | +63,420 (`oldbase_soa_s3_1`) |
| Private FC | saving 4,55,937.86 − gross OS 6,52,476.34 (`s7_1b.financial.os` + `.cfc`) | **−1,96,538.48** | −2,75,744 (`oldbase_soa_s3_2`) |
| General government | GDI 28,02,642.99 − GOS (= CFC) 3,75,679.16 − net taxes on production and imports 26,10,364.35 (`s1_1.taxes_on_products` 32,44,229.14 − `s1_1.subsidies_on_products` 5,76,422.38 − 57,442.41 net production taxes from 7.1A/B/C) | **−1,83,400.52** | −2,23,374 (`oldbase_soa_s4_0`) |
| **Σ domestic** | | **+4,39,510.70** | +4,22,323 |
| RoW (India's net) | property income from RoW 2,80,907.32 − to RoW 7,24,611.52 + transfers to residents 9,83,127.72 − by residents 99,912.81 (NAS 6.1) | **+4,39,510.70** (equal to Σ domestic within ₹0.001 cr) | +4,22,323 |

What the table says for planning:

- **Households need ₹36.3 lakh cr net.** The only fully anchored pieces are:
  - net remittances, +8,83,215;
  - government pensions paid, Union `fa9.2071.total` 2,38,328.30 + States `app2 … ii.e-pensions` 4,90,983.18;
  - income tax, a deduction.

  The rest must come from `fincorp`'s property income (old base: net +24.6 lakh cr for 2022-23) and `government`'s R10/R16/R9b. A bottom-up build from FSF stocks × effective rates can easily land several lakh crore short. Each rupee short shows as a household deficit and an equal surplus in NFC and FC accounts. This is H6 (GAP_MAP §4.2) becoming visible, and the diagnostics must say so.
- **A GG sketch from anchored cash flows lands close to the requirement:**

  | Component | ₹ cr | Source |
  |---|---:|---|
  | CFC | 3,75,679.16 | NAS |
  | Net taxes on production and imports | 26,10,364.35 | NAS |
  | Current taxes on income (gross of devolution) | + 19,63,654.38 | CIT 9,11,055.01 = `fa8.0020.total` + devolved `fa8.0020.00.901`; income tax 10,10,947.77 = `fa8.0021.total` + `fa8.0021.00.901`; STT `fa8.0034.total` 33,777.78; States `app1 … i.a.1-taxes_on_income` 7,873.82 |
  | Property income received | + 2,71,331.48 | `fa8.0049.total` less 13,641.26 intra-GG; `fa8.0050.total` incl. RBI 87,416.22; States' interest receipts and dividends |
  | Interest paid | − 15,95,401.98 | `fa9.2049.total` + States `app2 … ii.c.2` less intra-GG |
  | Pensions paid | − 7,29,311.48 | |
  | **Sketch GDI** | **28,96,315.91** | vs NAS 28,02,642.99, i.e. **+₹93,673 cr** before R10, R16, R15, R17, R18 and R9b |

  **R9b alone could add +₹4.5 to 6.8 lakh cr to GG and take the same amount from households.** This is planning arithmetic with the gap-map formula: Centre civil OPS × (1 − 18/39) + defence + States unadjusted or adjusted. It is not an entry. Whether NAS 2026's GG GDI includes D612 receipts decides this (§6 R3).

---

## 3. Constraints to declare

| constraint_id | ref | rows | cols | refs filter | target (source) | kind | tol_abs / tol_rel | Why |
|---|---|---|---|---|---|---|---|---|
| `closure.k4.hh_saving_total` | K4a (description names K4) | `[K_HH]` | `[H_R1..H_R5, H_U1..H_U5]` | `[K4a]` | 58,90,330.446044, `mospi_nas_2026_s1_9` / `s1_9.household_sector.current`, prov `mospi_nas_2026:0e67570b45b0` | `equal` | 0.5 / 0 | K4 is official. K_HH closes exactly only at this total (2.4-A). `capital_financial` owns K4 and may declare the same constraint; **the target must be the same series and value**, or the framework reports a conflict |
| `closure.d1.published_total` | D1 | `[X_DISC]` | `[H_R1..H_U5]` | `[D1]` | 5,71,133.272525, `mospi_nas_2026_derived_residuals` / `derived.household_residual.current`, prov `mospi_nas_2026:5ae8b8592c30` | `band` | 1.0 / 0 | Documents that the written D1 (= D2 + D3 + D4) is the published residual up to rounding. It covers only fixed entries, so it is satisfied by construction; if the framework refuses constraints with no free member, make it a block test instead (§4 framework needs) |

**Deliberately not declared:**

- **Household GDI = 2,28,77,010.24.** It equals C1 + K4 + D1 once the H_* accounts balance, so it is redundant. With the SUT PFCE (1,64,15,547.00) and NAS FCE (1,64,15,546.52) differing by ₹0.48 cr, a tight duplicate could only create infeasibility. It becomes a post-balancing test (§7 T9).
- **Per-group saving-rate bands.** No official source exists, so these stay findings, not constraints.
- **X_DISC and K_HH balance.** These are account-balance conditions the framework already enforces.

---

## 4. Interfaces

### Needs (from other blocks and the framework)

| From | What `closure` needs | Why |
|---|---|---|
| **all income-flow blocks** | Every H-touching entry written **at group level** (H_R1 … H_U5), never as an "HH total". The gap map defines R3a, R4, R5 and R8 with row "HH(total)"; `fincorp` must write the household parts under R8a (or with group-level R4/R5 entries), with components naming the instrument | The residual needs per-group resources and uses |
| households | C1a, C4a, C4b, C4c, C4d entries (Σ over groups = SUT PFCE per commodity; C1 constraint). **`hh_keys` satellite** with, per group, persons and total PFCE (for per-capita saving and the PFCE-key D1 sensitivity) | Uses side; sensitivity; per-capita reporting |
| factors | F1a, F2, F3a, F3b, F3c group entries; F3 = household gross OS/MI (97,71,430.53) − F_MIXD | Resources side |
| taxes | T3a group entries (low confidence; T3a has no open input, ISSUES P1-4). A stated household share of MH 0021: old-base households paid 6,42,596 of D5 16,38,909 (39.2%) in 2022-23, so not all of income tax is household. STT must be in exactly one of T_PIT or the SUT product-tax vector | Uses side; ±₹2 lakh cr swing |
| government | R9a (pensions by group), R9b, R10 and R16 group entries. **An explicit statement of whether NAS 2026's GG GDI (28,02,642.99) includes D612 receipts**, and the GG GDI implied by its entries with and without R9b. Farm income support is not in R10 (it sits in P10, D39); free PDS grain is not in R10 (it is GFCE) | Resources and uses; the largest GG-vs-HH swing |
| fincorp | R8a (group-level property income incl. government and FC interest, dividends, MF look-through), R9c (D44), R17 (premiums and claims, **net of the service charge**, which is in PFCE via C4b), R5 (interest paid by groups). **A statement that interest is SNA interest** (deposits: actual + FISIM; loans: actual − FISIM), consistent with household FISIM in PFCE 6,02,896.96 (`s1_13.private_final_consumption_expenditure.current`) | Resources and uses; FISIM consistency |
| rest_of_world | R11a and R12a group entries (Σ = 9,83,127.72 and 99,912.81). **The D2 entry**: recommend `io_tables_sut_supply` / `supply.cif_adj.cif.current` = 2,12,499.23649 (it closes R_ROW with the SUT imports, 2.4-A). GG transfers with RoW are booked **once**: NAS 6.1 puts them in the capital account (−6,999.68), so R15 and K6 must not both carry them | Uses side; X_DISC identity; RoW closure |
| capital_financial | D3 entries, with the K_HH part **exactly equal** to the valuables cell I2a it writes. SUT valuables 3,76,232.00 vs NAS 1.1 3,76,231.72 give I2a 2,04,105.43 or 2,04,105.15; the same number must be used in both places. No domestic capital transfer to K_HH unless an I_OTHR household residual is also posted. The K4 constraint with the same target as §3. The K9 residuals by sector | K_HH closure; X_DISC identity; diagnostics |
| production | The D4 entry (0, written as a zero-valued entry per DESIGN_BRIEF §3); C1/C2/I1 constraints; **a fix for the +₹0.33 cr M_TTM rounding** (below) | X_DISC identity; all-fixed M_TTM |
| **framework** | (a) `closure` runs after all 8 blocks. (b) `ctx.block_entries(name)` for all of them, plus a way to read other blocks' **constraints** for `constraint_gaps` (e.g. `ctx.block_constraints(name)`). (c) The combination role `fixed` + status `estimated` is valid (D1 split; any X_DISC allocation). (d) A constraint whose members are all fixed is allowed as a check, or the framework says to use a test. (e) Accounts with zero free entries (X_DISC, M_TTM) get an explicit pre-solve check that fails with the account name rather than a solver slack. (f) Constraint `tol_abs` floors of ≥ ₹1-2 cr for official totals built from rounded published tables | Items (b)-(f) go to `docs/phase2/FRAMEWORK_REQUESTS.md` if the guide does not cover them |

### Publishes (for other blocks, the report and later phases)

- **Entries:** K4a × 10 (`K_HH ← H_g`, free, low); D1 × 10 (`X_DISC ← H_g`, fixed).
- **Constraints:** `closure.k4.hh_saving_total`; `closure.d1.published_total`.
- **Satellites (clean long schema: `series_id`, dims, `value`, `unit`, `status`, `prov_id`):**
  - `hh_saving`: per group gross income, outlays excluding saving, D1 key and D1_g, K4a (option A), option-B alternative, the three saving rates, persons, per-capita saving; Z and its flow-class decomposition; IFPRI comparison rows.
  - `prior_imbalance`: 128 accounts (2.3 item 1).
  - `constraint_gaps`: every block constraint (2.3 item 2).
  - `institution_gaps`: 2.3 item 3, including the required-flow table 2.4-C with its source series.
  - `xdisc_identity`: 2.3 item 4.
- **Issue file** `docs/phase2/issues/closure.md`, containing:
  - Z;
  - the X_DISC rounding (0.107 cr) and the M_TTM rounding (0.33 cr);
  - every group with an implausible saving rate or a sign contrary to IFPRI;
  - the top 10 prior account imbalances;
  - every institution gap over ₹5,000 cr, each traced to a flow class and source.
- **Consumers:** `report.py` (BALANCING.md "before balancing"); the balancing audit (explanations must cite `institution_gaps`); Phase 4 ABM (group saving); `pipeline/timeseries` (household saving is taken from NAS directly, not from K4a).

---

## 5. Conflicts and choices

| # | Item | Source A | Source B | Recommendation |
|---|---|---|---|---|
| C1 | Household saving total (K4) | NAS 2026 St 1.9 `s1_9.household_sector.current` **58,90,330.45** (= 1.14 = 5.3; RECONCILIATION HH-5 agree) | RBI HBS 2025-26 T11 `t11.gross_saving_hh.base2022.current` **59,63,550** (vintage 2026-07-31, pre-NAS-2026): −73,220, −1.23% (HH-6 "explained", vintage) | **Control: NAS 2026. Cross-check: HBS T11** (report only). For the financial component, NAS 5.3 net financial saving 16,92,911.81 vs RBI T52(a) `t52a.nfa.current.fy` 16,92,414.20 (HH-4 agree) is `capital_financial`'s cross-check |
| C2 | D1 total | NAS 1.14 derived `derived.household_residual.current` **5,71,133.27** (same from the 1.1 identity) | X_DISC identity D2 + D3 + D4: **5,71,133.17** (SUT CIF) / **5,71,132.93** (NAS 6.1 CIF) | **Entries = identity value** (the all-fixed account must close exactly). The **published value stays the constraint target** with a ±₹1 cr band; the difference is logged. The cause is rounding: NAS 1.1's expenditure components add to GDP − 0.35, while the published discrepancy is 0.00 |
| C3 | D2 value (owned by `rest_of_world`; decides C2's residual) | SUT `supply.cif_adj.cif.current` **2,12,499.24** | NAS 6.1 `s6_1.adjustment_for_cif_in_import_of_services.current` **2,12,499.00** | **SUT** (control): SUT imports after CIF 69,46,906.03 + SUT CIF = 71,59,405.27 = NAS 6.1 imports (to ₹0.0005 cr). With the NAS figure R_ROW is ₹0.24 cr off, with all its import cells fixed. NAS 6.1 is the cross-check |
| C4 | Household consumption total | SUT `use.pfce.total.current` **1,64,15,547.00** (integer per product) | NAS 1.14 FCE **1,64,15,546.52** | SAM uses **SUT** (production's C1 constraint). All household-GDI tests use tolerance ≥ ₹1 cr |
| C5 | Valuables (the I2a size and D3→K_HH) | SUT `use.valuables.total.current` **3,76,232.00** → I2a 2,04,105.43 | NAS 1.1 `s1_1.valuables.current` **3,76,231.72** → I2a 2,04,105.15 | **SUT** for the commodity cell (C_GJOM must balance); D3→K_HH must use the **same** I2a (`capital_financial`) |
| C6 | D1 allocation key | Gross income (gap map D1) | PFCE share; disposable income; population | **Gross income** = prior H_g row total. It is neutral between "income overstated" and "consumption or saving understated", the two readings of the NAS residual. PFCE and population splits are published as a sensitivity band |
| C7 | K4a prior form | **A: pure residual** (each H_g balances in the prior; Σ ≠ NAS by Z) | B: residual shifted by Z × income share (Σ = NAS in the prior; each H_g off by its share of Z) | **A.** It keeps each group's sign from its own evidence rather than from an arbitrary key for Z, which matters because cross-entropy never flips signs. It is also the gap-map method. The cost: Z shows in the diagnostics as a K4 constraint gap and a K_HH imbalance, so `institution_gaps` and the issue file must say it originates in the household current accounts. B is published in `hh_saving` |
| C8 | Saving-rate benchmark | IFPRI 2022/23 T11: all quintiles positive (18.4-23.9%), rural 21.3%, urban 24.0% (old base; national quintiles; its enterprise/household saving split is assumed, ISSUES Phase 0 raw log) | Gap map K4a note: "negative saving in bottom quintiles is expected and allowed" | **Flag only; do not constrain.** Compare rural and urban aggregates only. A negative bottom-group residual is reported with its cause (usually NAS-scaled HCES consumption, H1) |
| C9 | State pensions (owned by `government`; moves the HH/GG diagnostic by ~₹4,000 cr) | FC16 KFI `kfi.b_1_b-pension_and_other_retirement_benefits.in.all_states_28` **4,94,938.72** (gap-map primary) | RBI SF `app2.total_expenditure.ii.e-pensions.in.all_states_uts.actuals` **4,90,983.18** | `government`'s choice. `closure` records which one was used in `institution_gaps` |

---

## 6. Risks, gaps, open questions

- **R1 (blocking): all-fixed accounts with rounding residuals.**
  - **X_DISC** (+0.107 / +0.344 cr) is solved in 2.2 by deriving D1's total from D2 + D3 + D4.
  - **M_TTM** (+0.33 cr: P4 39,60,078.00 vs P3 39,60,077.67) belongs to `production`. Recommended fix: scale the six P3 entries (`C_TRAD`/`C_TRNS ← M_TTM`) by the ratio P4/P3 (a +0.0000084% change) as a `derived` step, logged. Alternative: mark P3 `anchored` with `tol_rel` = 1e-6. Without one of these, the ₹0.01 cr balance test fails with no free entry to move.
- **R2 (largest finding expected): the household aggregate gap Z (H6).** No new-base household property-income or transfer accounts exist. Official totals fix the household net at +36,30,975 (table 2.4-C). If `fincorp` builds interest and dividends bottom-up, Z could be several lakh crore. Balancing then pushes Z into the free household-income entries (R8a, R9c, R10) and the opposite way in NFC/FC. The explanation rule (≥ ₹5,000 cr) will fire many times; every explanation must cite `institution_gaps`. Mitigation, owned by `fincorp`: use the old-base 2022-23 household D4 structure (received 47,12,396; paid 22,49,807) as a labelled prior or cross-check.
- **R3: the R9b swing (₹4.5-6.8 lakh cr, planning range).** The design adds imputed OPS contributions (D612) paid by households to government, to offset the imputed CE. Old-base NAS had no D61 paid by households. The GG sketch without R9b is already within +₹0.94 lakh cr of NAS GG GDI before cash transfers and fees. If NAS 2026's GG GDI excludes D612 receipts, including R9b creates a ~₹5-7 lakh cr GG surplus and household deficit. **Open question for MoSPI NAD (add to the P0-10 list).** `government` must test GG GDI with and without R9b.
- **R4: FISIM consistency.** Household FISIM in PFCE is 6,02,896.96. If household interest is written as bank-reported interest instead of SNA interest:
  - deposit FISIM is left out of household income;
  - loan FISIM is counted twice in outlays.

  The Z error is up to ~₹6 lakh cr.
- **R5: household share of income tax.** Old-base households paid 39.2% of all current taxes on income (6,42,596 of 16,38,909) in 2022-23. The Union collects 10,10,947.77 in MH 0021 plus STT 33,777.78, and part of that is paid by firms and AOPs. Charging it all to H_* would overstate household taxes by roughly ₹2 lakh cr. STT counted both in T_PIT and in the SUT product-tax vector would be a ₹33,778 cr double count.
- **R6: sign lock.** With x = a·z, z ≥ 0, each K4a entry keeps the sign of its prior residual. A group whose residual is near zero with the wrong sign cannot be corrected by balancing. Mitigations: the step-6 check (|K4a_g| ≥ ₹1 cr), plus the IFPRI and plausibility flags. If a sign is judged wrong, the fix is upstream (the income or outlay keys), never a manual override.
- **R7: group-level entries.** Any H-touching ref written as a household total breaks the residual. This is a hard failure in step 2.
- **R8: rounding in official-total constraints.** SUT rounding is up to ₹0.93 cr per SUT industry and ₹0.50 cr per product. Per-activity V1/V2 and per-commodity C1/C2/I1/P7 constraints declared `equal` with zero tolerance will produce slack findings that are pure noise. They need `tol_abs` of about ₹1-2 cr (RECONCILIATION uses a ₹5 cr floor).
- **R9: status of the D1 total.** The published D1 is `derived` in clean data (an arithmetic residual of official statements). The gap map calls it OFFICIAL. The entries are `estimated` (allocation) and `fixed`. The framework must accept fixed + estimated.
- **R10: circular key.** The D1 key uses prior incomes, which balancing then moves. After balancing, D1_g shares differ slightly from the balanced income shares. Accepted and documented; the post-balancing difference is reported, and not iterated, because iterating would make a pinned cell depend on the solver.
- **R11: K_HH closure depends on `capital_financial`.** It needs D3→K_HH = I2a exactly (C5), no domestic capital transfers to K_HH without a matching household I_OTHR residual, and household instrument flows exactly = NAS 5.3 / 1.9.
- **R12: double-counting checks `closure` enforces or reports** (step 2 whitelist plus tests):
  - PF, pension and life-insurance contributions or claims as current transfers. They are financial (I_INPE); NAS saving already contains PF & pension 7,23,027 and insurance 6,49,086;
  - D3 valuables (2,04,105) as household **income**. It is a capital-account receipt only;
  - jewellery in PFCE (it is I2/I2a);
  - free PDS grain as R10 or PFCE (it is GFCE, C2a; S8 is a satellite);
  - farm income support in R10 (it is D39 in P10, reaching households via F_MIXD);
  - non-life premiums gross of the service charge (the charge is in PFCE via C4b);
  - GPF/PPF interest in both R3a and R9c. The Union pays 18,871.50 `fa9.2049.03.104` (State Provident Funds) and 18,841.04 `fa9.2049.03.108` (insurance and pension funds);
  - R9 without R9b, or R9b without R9;
  - intra-household flows;
  - GG transfers with RoW in both R15 and K6 (−6,999.68).
- **R13: benchmark quality.** The old-base SOA is NAS 2024 vintage, 2022-23 FRE, base 2011-12. Use it for structure and sign only, never as a level for 2023-24. IFPRI is also old base and uses different groups.
- **R14: dependency.** `closure` cannot run if any block fails. Ask the framework to compute the raw `prior_imbalance` in `assemble.py` too, so the diagnostics exist even when `closure` is blocked.

**Open questions:**

- **For MoSPI NAD (via the owner's access list):**
  - Does NAS 2026 GG GDI include D612 receipts (the imputed OPS contributions)?
  - How is MH 0021 split between households and other assessees in D5?
- **For the framework agent:** items (b)-(f) in the §4 framework row.

---

## 7. Tests the builder should write

All targets are **read from clean Parquet at test time** (never typed in). Tolerances as stated. Marker `sam`.

| # | Test | Reads | Assertion |
|---|---|---|---|
| T1 | K4a shape | block entries | Exactly 10 K4a entries, one per group, `row = K_HH`, role `free`, confidence `low`, status `estimated`, non-empty prov `method`, |value| ≥ 1 |
| T2 | K4 total after balancing | `mospi_nas_2026_s1_9` `s1_9.household_sector.current`; also `s1_14.households_npish.gross_savings.current` and `mospi_nas_2026_s5_3` `s5_3.household_saving_1_2_3_4.current` | Σ balanced K4a = each within ₹0.5 cr (the three sources are identical) |
| T3 | Prior residual identity | all prior entries | For each H_g: prior row total − prior column total (incl. K4a, D1) = 0 within 1e-6 (option A) |
| T4 | D1 shape and total | block entries; `mospi_nas_2026_derived_residuals` `derived.household_residual.current` | 10 D1 entries, role `fixed`, status `estimated`, all > 0. Σ = Σ D2 + Σ D3 + Σ D4 entries within 1e-6. \|Σ − published\| ≤ ₹1 cr. Also recompute the published value as `s1_14 GDI − FCE − gross_savings` and as `s1_1.gndi − s1_1.pfce − s1_1.gfce − s1_1.gross_saving`; both equal the derived series within ₹0.01 cr |
| T5 | D1 key | prior entries | D1_g / Σ D1 = inc_g / Σ inc within 1e-9; no entry with row and col both in H_* |
| T6 | X_DISC closure | balanced entries | X_DISC row = column within ₹0.01 cr, before and after balancing; its entries are unchanged by balancing |
| T7 | K_HH closure | prior entries of capital_financial + closure; `s1_9.less_financial_liabilities.current`, `s1_9.gross_financial_saving.current`, `s1_14.households_npish.gross_capital_formation.current`, `s1_9.saving_in_the_form_of_gold_and_silver_ornaments.current` | With Σ K4a = NAS: K_HH row − column within ₹0.5 cr, and D3→K_HH = I2a within 1e-6 |
| T8 | Required-flow identity (pure data test) | the series in table 2.4-C | Σ of the six institutional requirements = NAS 6.1 net property income + net transfers from RoW within ₹0.01 cr (today: 4,39,510.70 both) |
| T9 | Household GDI after balancing | `s1_14.households_npish.gross_disposable_income.current` | Σ over H_* columns of (COM rows + K_HH + X_DISC) = GDI within ₹1 cr (the SUT/NAS PFCE rounding is 0.48) |
| T10 | Other institutional GDIs after balancing | `s1_14.gg.gross_disposable_income.current`, `s1_14.gg.final_consumption_expenditure.current`, `s1_14.gg.gross_savings.current`, `s1_9` NFC/FC savings | GG: Σ (COM ← G_*) + Σ (K_GCEN, K_GSTA ← G_*) = GG GDI within ₹1 cr. NFC and FC: saving cells = NAS within their constraint bands |
| T11 | Whitelist | all entries touching H_* | Every ref is in the 2.1 step-2 whitelist; no `I_*`/`K_*` flows inside H columns other than K4a |
| T12 | Diagnostics integrity | `prior_imbalance` satellite | 128 rows; Σ imbalance = 0 within 1e-6; equals the assembler's own account totals; X_DISC and M_TTM flagged `n_free = 0` |
| T13 | X_DISC identity satellite | `xdisc_identity`; `io_tables_sut_supply` `supply.cif_adj.cif.current`; `mospi_nas_2026_s6_1` `s6_1.adjustment_for_cif_in_import_of_services.current`; `derived.si_errors_omissions.current` | The residual reported equals D1_published − D2_written − D3_written − D4_written. The D2 used is one of the two named series |
| T14 | Plausibility (warn, not fail) | `hh_saving`; `io_tables_ifpri_2223_datapaper` `ifpri.t11.savings_rate.rural` / `.urban` | Emit findings (never failures) for groups outside [−25%, +50%] of gross income, or with a sign contrary to IFPRI. Rural and urban aggregate rates are reported next to IFPRI 21.3% / 24.0% |
| T15 | Determinism | closure outputs | Byte-identical across two hash seeds and 1 vs 4 threads (part of `repro`) |

---

## 8 Cross-plan review (2026-09-30, cross-plan critic; details and ids in `CROSS_REVIEW.md`)

What this block must change or confirm:

1. **XR-16:**
   - **M_TTM is already solved.** Production writes the P1–P6/I3 SUT cells `anchored` with ₹1 per cell (FRAMEWORK_REQUESTS deviation 1). Drop the M_TTM request to production.
   - **Your X_DISC rule** (D1 written = D2 + D3 + D4 as written; the published 5,71,133.27 as a ±₹1 band) is agreed by rest_of_world and capital_financial. It should close FRAMEWORK_REQUESTS P-15 (orchestrator, decision D-13).
2. **XR-11 whitelist:** resources must include **R9a** (government's pension group entries; R9 is constraint-only), and **R7x/R9d** if the orchestrator creates them (XR-1, XR-2). R9d would be HH ← E_NFPU pensions. Uses already include R5 and R17. Fail loudly on R9, R3a or R8 entries touching H_*.
3. **XR-33 identity tests:** nobody owns DESIGN_BRIEF §7's identity tests (FRAMEWORK_REQUESTS FR2-1). Add to your tests:
   - GDP three ways vs NAS 1.1 (discrepancy 0);
   - GG: GDI, and the Centre/State tax totals vs their bands;
   - BoP: R_ROW and K_ROW closure with D2;
   - flow of funds: every I_* clears; household financial saving = NAS 5.3.
4. **XR-8 / XR-30 diagnostics to expect.** `institution_gaps` should show large prior gaps on:
   - E_NFPU: it must pay out a net 7,04,183, but D45 royalties, departmental pensions and NFC→GG interest have no owner until XR-1/XR-2 are fixed;
   - E_RBI: ≈ +25.6k unless XR-4 is adopted;
   - G_CEN/G_STA: the GG current account moves by ±3 lakh with R9b × R7x.

   Name these causes in the issue file.
5. **XR-3:** if government writes capital transfers to K_HH (recommended, decision D-3), K_HH closes only through capital_financial's K9_HH. Your T7 should then assert K_HH row − column = 0 *including* K9, and report K9_HH separately.
6. **XR-17:** K4a keeps option A (pure residual), and your |K4a_g| ≥ ₹1 check stays. The framework's sign-flexible pattern (paired `_pos`/`_neg` components, P-9) is available if a group's residual is judged sign-uncertain. Record the choice.
7. **Confirmed consistent across plans:**
   - fincorp writes all household property income at group level (R8a, R5, R9c, R17), as SNA interest consistent with PFCE FISIM 6,02,896.96 (XR-5 fixes the by-group match);
   - taxes publishes the household share of MH 0021 (0.7855) and puts STT once, in T_PIT;
   - government R9 is net of NPS and CGHS (6,71,638.24, not your sketch's 7,29,311.48);
   - rest_of_world uses the SUT CIF for D2;
   - capital_financial's D3 → K_HH = I2a.
