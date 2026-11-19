# Independent audit: the balanced SAM 2023-24

Auditor: an agent that built nothing in the SAM (SPEC rule 3). Audited on 2026-10-01 against the balanced run of 03:00 (`data/sam/2023-24/balancing_run.json`: NEWTON, direct path, status optimal, KKT certificate passed, objective 72,975.45, no slack). It also covers the explanation files written 03:14-03:35 and `BALANCING.md` as regenerated at 03:35. Amounts are Rs crore at current prices; "lakh" means 1,00,000 crore.

**Method.** I did not use the framework's code. The balanced entries, the constraint definitions and every target were read with DuckDB directly from Parquet: `data/sam/2023-24/*.parquet` and `data/clean/**`. Account order comes from `pipeline/sam/accounts.yaml`. Everything was recomputed with DuckDB and numpy. The tests are in `tests/verify/test_sam_balanced_audit.py`: 54 pass and 3 are strict xfails for confirmed defects. That file imports neither `pipeline.sam` nor `pipeline.core`.

## Verdict: needs fixes. The balancing is sound; the answer carries evidenced problems.

- **The arithmetic and the SPEC acceptance tests pass.** Every account balances, GDP matches NAS three ways, the government, BoP and flow-of-funds totals match their sources, fixed cells and X_DISC are untouched, and every over-threshold move has a logged item. An independent optimality check agrees with the solver's certificate.
- **The problems are economic.** Balancing had to find Rs 4.36 lakh crore of household income (Z) and move 5.0 lakh of the States' surplus. Most of that went to low-confidence entries whose own sources contradict the result:
  - State cash transfers rose 74%, so GG current transfers are 10% above NAS 4.2.
  - Railway pensions rose 86% above the AFS figure they were built from.
  - Outside-treasury CSS money fell 40%.
  - Financial-corporation saving was re-split with no evidence behind the new split.
- **33 of the 280 explanation items say, in their own words, "Unexplained".**

None of this is hidden: every item is logged in the owning block's issues file. But it is not yet a SAM whose large flows are all evidenced. These are Checkpoint B decisions, and most are fixable before then by declaring missing totals as constraints (see "What would fix most of it").

## 1. SPEC Phase 2 acceptance tests (recomputed)

| Test | Result | Measured (balanced minus source) | Tolerance used |
|---|---|---|---|
| Prior = the nine blocks' entries, exactly; balanced = prior + change | pass | 3,883 entries; max difference 0 | exact |
| Every account, row = column (all 128 accounts) | pass | max 0.000005 (H_U5) | 0.01 |
| Cell file and 128x128 matrix = entries; matrix in accounts.yaml order | pass | cells 2e-6; CSV 0.005 (printed to 2 decimals) | 1e-5 / 0.005 |
| GDP by production / income / expenditure vs NAS 1.1 | pass | +0.61 / +0.61 / +0.61 | 10 |
| D4 = NAS discrepancy (0); expenditure - production beyond D4 | pass | 0 / 0.00 | exact / 1 |
| GVA at basic prices; product taxes less subsidies | pass | +2.13; -1.52 | 5 |
| PFCE, GFCE vs NAS 1.1 | pass | -1.00, +1.00 (both on the edge of their +-1 bands) | 1 |
| CIS, exports, imports, GFCF + valuables | pass | -0.04, +0.72, +0.77, +1.04 | 5 |
| GG saving vs NAS 1.9; GG FCE and GDI vs NAS 1.14 | pass | +0.50; +1.00; +1.50 | 0.5; 1; 1.5 (sum of the two bands) |
| Union taxes vs Finance Accounts / Receipt Budget: CIT, income tax, Union excise, compensation cess, customs | pass | +0.00%, +0.01%, +3.75%, **+5.00%**, -1.82% | 0.5%, 1%, 5%, 5%, 2.5% |
| State taxes vs RBI SF App. I: SGST, VAT/sales tax, State excise, income taxes | pass | -1.27%, +0.06%, -0.25%, -0.79% | 5%, 15%, 15%, 1% |
| Union gross tax, five heads (with the correct series id `total_goods_and_services_tax_gst`) | pass | +1.77% (35,12,434 vs 34,51,500) | 5% |
| SGST at least 95% of FC16 (28 States) | pass | 103.8% | >= 95% |
| R1 devolution = FA 901 lines | pass | 0.00 | 1 |
| RoW current receipts / disbursements vs NAS 6.1; surplus; K5 | pass | +0.72 / +0.72; 0.00; 0.00 | 1; 2; 0.5 |
| D2 = SUT CIF; D2 vs NAS 6.1 CIF | pass | 0; +0.24 | 1e-6; 1 |
| CE from and to RoW | pass | 0, 0 | 0.5 |
| K8b foreign liabilities / assets vs NAS 6.1; R_ROW and K_ROW close | pass | 0 / 0; 0 | 1; 0.01 |
| All 11 instrument markets clear | pass | max 2e-6 | 0.01 |
| Household financial assets / liabilities / net vs NAS 5.3 | pass | 0 / 0 / 0 | 0.5 / 0.5 / 1 |
| Saving: households, public NFC, private NFC, FC, national (NAS 1.9) | pass | -0.50, 0, 0, +1.00, +1.00 | 0.5, 1, 1, 1, 2 |
| FC saving, public and private, vs NAS 1.9 | pass | within 1 | 1.5 |
| Household GDI vs NAS 1.14 | pass (see BS-3) | -1.61 = PFCE -1.00 + saving -0.50 + D1 -0.11 | 1.61 (sum of the parts' tolerances) |
| GNDI vs NAS 1.1 | pass | +0.89 | 3 |
| Fixed entries (195) and X_DISC unchanged; X_DISC closes; D1 vs published residual | pass | 0; 0; -0.107 | exact; 0.01; 1 |
| Anchored entries (1,062) inside their boxes | pass | 2 exactly on the box (C_TRAD <- M_TTM P3, C_FOFI <- A_CNST P2); none outside | tol_rel |
| All 385 declared constraints within band (recomputed from `constraints.parquet`) | pass | 0 violations; my sums equal `balancing_constraints.parquet` to 1e-3 | band |
| Cross-entropy optimality (independent stationarity check, below) | pass | residual 6e-9 over 1,361 entries | 1e-6 |
| Every over-threshold entry (190) and multi-entry cell (90) has exactly one current item in the right file, citing registry sources | pass | 280 items; none missing, stale, duplicated or orphaned; all 29 cited source ids exist in the registry | SAM_GUIDE s.12 |
| No item says "Unexplained" | **strict xfail (BS-1)** | 33 fincorp items | - |

**Independent optimality check.** At a cross-entropy optimum, every variable entry that is strictly inside its box and in no constraint at a bound must satisfy w * sign(a) * ln(balanced / prior) = lambda[row] - lambda[col] for one multiplier per account. I took the 1,361 such entries of Rs 1,000 crore or more and fitted lambda by least squares. Smaller entries carry 6-decimal rounding noise in ln z, so they were left out. The residual is 6e-9. So the published SAM is the minimum-information adjustment of the prior under the declared constraints; the result is not a solver artefact.

**Anchored (official) entries were not over-moved.** No anchored entry left its box. The largest anchored move is G_STA <- G_CEN R2 css_and_other, -1,438, which uses 6.7% of its 10% box. All 30 largest adjustments are free entries (26 low confidence, 4 medium). Two entries carry prior status official or derived but role free:

- R18 `psu_revenue_grants` (derived) was cut 44% (BS-11).
- One official entry moved Rs 11.

There are no sign changes. No entry was pushed towards zero: z runs from 0.517 (E_NFPU <- E_INSP R17 premium_supplement) to 1.936 (E_INSP <- E_NFPU R5 nongov_bonds and R8).

## 2. Economic plausibility

### Where the money moved (by flow, balanced minus prior)

| Flow | Prior | Balanced | Change | Evidence for the balanced level |
|---|---:|---:|---:|---|
| K4a household saving (10 groups) | 54,54,167 | 58,90,330 | +4,36,163 (+8.0%) | the NAS 1.9 total: yes. The split by group: none (closure-19) |
| R10 State `cash_schemes` to households | 2,14,325 | 3,72,073 | +1,57,748 (+73.6%) | none. GG current transfers become +10.0% over NAS 4.2 (BS-5) |
| R8a distributed income to households | 21,19,222 | 22,46,619 | +1,27,397 (+6.0%) | direction yes (old-base St 5.0 structure; fincorp-19) |
| R9d departmental pensions (E_NFPU -> HH) | 70,490 | 1,31,327 | +60,837 (+86.3%) | none. Railways 1,11,414 vs AFS 59,802 (BS-6) |
| R2 Centre -> States (css_outside_treasury -59,561) | 5,07,507 | 4,46,508 | -60,999 | compensating for unwritten agency outlays (BS-7) |
| R8 inter-corporate distributed income | 5,72,294 | 5,15,316 | -56,978 (-10.0%) | weak key |
| R5 interest paid by households (loans) | 7,41,008 | 6,87,965 | -53,043 (-7.2%) | weak key |
| C2a GFCE, Centre -> States (all commodities) | | | 69,162 shifted | inside gov.c2a.centre_own_output (+-10%) and every commodity band |
| T4a corporation tax, E_NFPU | 75,259 | 1,23,228 | +47,968 (+63.7%) | none; no CPSE tax series (BS-10) |
| K2a FC saving split (total held at NAS) | banks 4,58,959; NBFC 3,37,883; RBI 94,183; insurers 1,00,423 | 4,06,142; 3,92,900; 1,11,028; 81,378 | re-split | the evidence (fincorp-2) favours the prior. "Unexplained" (BS-1) |
| GG saving split (total held at NAS) | Centre -3,40,382; States +21,998 | -3,88,791; +70,407 | 48,409 moved to the States | direction supported by FSF (capital_financial `nas_vs_fsf`) |

Three things drive the pattern. The prior left households Rs 4.36 lakh short. It left G_STA +5.01 lakh over and E_NFPU +3.13 lakh over, with G_CEN -2.98 lakh short (closure `institution_gaps`). Cross-entropy then sends each account's gap to its largest low-weight entries, and it sends them by one multiplier per cell. So:

- R10 is the States' largest low-confidence payment to households.
- R9d and fincorp's R8a are E_NFPU's only low-confidence payments to households.
- R2 `css_outside_treasury` is the largest low-confidence Centre -> States receipt.

**Were the biggest moves where the prior was weakest?** Yes in the mechanical sense: every large move is on a free, low-confidence key. But four of those "weak" entries carry published levels that were never declared as constraints:

- R9d: the AFS railway pension line.
- R10: NAS 4.2 COFOG current transfers.
- R2 `css_outside_treasury`: Budget St 18 less MH 3601.06.
- R18: IGAS-2.

That is why balancing could double or halve them.

### Household saving by group (saving / gross income; saving / (consumption + saving))

| Group | Prior S/Y | Balanced S/Y | Prior S/(C+S) | Balanced S/(C+S) |
|---|---:|---:|---:|---:|
| H_R1 | 28.4% | 30.0% | 29.6% | 31.3% |
| H_R2 | 25.5% | 27.1% | 26.8% | 28.4% |
| H_R3 | 26.2% | 27.8% | 27.7% | 29.3% |
| H_R4 | 36.0% | 37.8% | 38.3% | 40.0% |
| H_R5 | 11.1% | 12.0% | 12.4% | 13.3% |
| H_U1 | 20.7% | 22.1% | 21.6% | 23.0% |
| H_U2 | 20.9% | 22.3% | 22.2% | 23.6% |
| H_U3 | 19.5% | 20.8% | 21.8% | 23.2% |
| H_U4 | 19.4% | 20.8% | 22.8% | 24.2% |
| H_U5 | 22.7% | 24.2% | 26.8% | 28.3% |
| Rural (IFPRI 2022/23: 21.3%) | 23.8% | 25.3% | 25.6% | **27.1%** |
| Urban (IFPRI 2022/23: 24.0%) | 21.1% | 22.6% | 24.2% | 25.7% |

This profile is not plausible yet (BS-8):

- The poorest rural fifth saves 31% of its consumption-plus-saving.
- The richest rural fifth saves 13%, the lowest of the ten groups.
- Rural households save more than urban ones, the reverse of IFPRI's order.
- Balancing moved rural further from IFPRI.

The cause is upstream: the factor-income keys (factors-19, D2-19) run against HCES consumption. Balancing spread Z almost proportionally (+7.2% to +8.6% per group), so it neither caused the shape nor fixed it.

### Sector saving vs NAS 1.9

All sectors are on NAS within their bands: households -0.50, public NFC 0, private NFC 0, FC +1.00, GG +0.50, national +1.00. Several totals sit exactly on a band edge:

- PFCE -1.00.
- GFCE +1.00.
- GG saving +0.50.
- K4 -0.50.
- CGST and compensation cess at +5.0% of their cash receipts.

Being on an edge shows where the solver pushed hardest.

## 3. The explanations (280 items in 7 block files)

Coverage is complete and current, checked independently: I recomputed the threshold rule myself, and it gives the same 190 entries and 90 cells as `balancing_log.parquet`. No item is missing, stale, duplicated, in the wrong file, or explaining nothing. Every `sources` id resolves to `data/registry.yaml` or `data/registry_additions`.

I spot-checked the figures cited against the log and clean data, and all of them match:

- Z and each institution's gap.
- GRAS values: R2 1,15,813; R9d 95,535; R10 2,25,186; K4a sum 56,70,561.
- The C2a shift of 69,162 and the Centre's own output of 8,05,110.
- The derivation 4,25,296 - 2,57,208 = 1,68,087.
- The T4a shares.

The texts are specific and honest; I found no vague item and no wrong figure. Their verdicts are what matters:

| File | Items | Verdict |
|---|---:|---|
| government | 86 | 38 "Explained"; **48 "Explained in direction; level unexplained"** (R10, R9d, R7x single-payer lines, H_g <- G_STA and H_g <- E_NFPU cells) |
| fincorp | 114 | 81 "Explained"; **33 "Unexplained"** (gross move Rs 3.97 lakh: K2a FC saving split, E_INSP <- E_NFPU +87%, R17 premium supplements that break fincorp's D71 = D72 basis, E_NFPU mf_lookthrough) |
| capital_financial 27, taxes 23, rest_of_world 15, closure 10, factors 5 | 80 | explained or stated as spill-over. Several say plainly "not a better estimate" (rest_of_world-27) or "no independent source" (factors-22) |

So SPEC acceptance (d) holds on paper: every move has a logged item. But 81 items (29%) state that the level they log has no evidence. BALANCING.md's headline "still unexplained: 0" counts only missing items and does not read the verdicts (BS-2).

## 4. BALANCING.md for a finance-trained reader

What works:

- It opens with "Result: BALANCED".
- The thresholds and weights are stated.
- The pre-balancing section traces Z by institution and flow class, which is exactly what a CFA reader needs.

What gets in the way (BS-2, framework `report.py`):

1. The summary prints raw JSON for the certificate, phase 1 and polish. The terms KKT, dual Newton, HiGHS LP and z have no glossary.
2. "still unexplained: 0" sits next to 33 items that begin "Unexplained:" and 48 "level unexplained". The summary should count verdicts.
3. There is no plain-English "what balancing did" section. The four moves that closed Z (R10 +1.58 lakh, R8a +1.27 lakh, R9d +0.61 lakh, R5 -0.53 lakh) must be pieced together from a 281-row table whose "Why" cells run to 1,500 characters. The file is 268 KB.
4. The acceptance results (GDP three ways, taxes vs Finance Accounts, BoP, flow of funds) are not in the report at all. They live only in test output.
5. The pre-balancing table lists 79 accounts, 70 of which are SUT rounding under Rs 1.5 crore.
6. The GRAS table shows the 60 largest of 230 findings and does not say it is truncated. GRAS ignores the constraints (closure-19), so its gaps are weak evidence. The report should say so.
7. `sam_balanced_matrix.csv` is printed to 2 decimals, so a reader summing it sees accounts off by up to 0.04 against the stated 0.01 tolerance. This should be noted, or more decimals printed.

## Findings

| # | Severity | Owner | Finding | Evidence | Fix (proposed, not done) |
|---|---|---|---|---|---|
| BS-1 | major | fincorp | 33 items self-declare "Unexplained" (gross Rs 3.97 lakh). K2a re-splits FC saving against fincorp-2's own evidence. E_INSP <- E_NFPU R5/R8 carry the highest z in the SAM (1.94). R17 supplements lose the D71 = D72 basis | `pipeline/sam/explanations/fincorp.yaml`; strict xfail `test_no_explanation_item_says_unexplained` | Declare FC sub-sector saving bands from the RTP business-account evidence (fincorp-2), bind R17 supplements to the IRDAI total, repair E_NBFC's GOS / distributive flows (fincorp-34), rerun; otherwise the owner accepts them at Checkpoint B |
| BS-2 | minor | framework | BALANCING.md hides the verdicts ("still unexplained: 0"), truncates the GRAS table without saying so, prints JSON, has no "what balancing did" or acceptance-results section, and its matrix CSV at 2 decimals shows 0.04 imbalances | s.4 above; `report.py` lines 263-300, 414-427 | Count verdicts in the summary; add a by-ref movement table and an acceptance-results table; state "top 60 of 230"; add a glossary; more decimals in the CSV |
| BS-3 | minor | closure | `test_household_gdi` fails at -1.61 against a Rs 1 tolerance, yet every part is inside its own declared band: PFCE on the hh.c1.total edge -1.00, K4 edge -0.50, D1 fixed -0.107. The balance-run summary's "there is no aggregate PFCE constraint" is wrong: `households:hh.c1.total` (+-1) exists and binds | `test_household_gdi_within_the_sum_of_its_parts_tolerances` passes at 1.61 | Set the test tolerance to the sum of the parts' tolerances, or tighten hh.c1.total / K4 if Rs 1 is the real requirement |
| BS-4 | minor | closure | `tests/sam/test_sam_identities.py:192` reads `rb.tr.total.total_goods_and_services_tax`, which does not exist | the correct `..._gst` (9,57,207.82) gives +1.77% against a 5% band; reproduced in `test_union_gross_tax_revenue_five_heads` | One-string fix |
| BS-5 | major | government | R10 `cash_schemes` +73.6% (every group z 1.73-1.75) takes R9a + R10 + R18 to 11,06,002, +10.0% over NAS 4.2 COFOG current transfers (10,05,630). The prior was -6.5%, so balancing overshot the source it should respect. GRAS gives only +5% | strict xfail `test_gg_current_transfers_within_5pct_of_nas_4_2`; government-31 | Settle PM-KISAN with taxes (government-30), then declare `gov.cofog.current_transfers` (+-5%) |
| BS-6 | major | government | R9d railway pensions 59,802 -> 1,11,414 (+86%) against its own source, AFS Railway Funds disbursements 59,801.66 (A-R9d-1). Posts pensions 10,688 -> 19,913 | strict xfail `test_r9d_railway_pensions_within_10pct_of_the_afs`; government-33 | Anchor R9d (+-10%) or constrain its total; E_NFPU's +3.13 lakh surplus must then leave through evidenced flows (a departmental surplus to GG? NAD question) |
| BS-7 | major | government | R2 `css_outside_treasury` 1,48,479 -> 88,918 (-40%). Outside-treasury CSS money is now 38.8% below IGAS-2 'Others' grantees (1,73,699). The balanced value is a net of unwritten agency outlays, not a transfer | government-34; the build check reads the prior only | Write the agencies' outlays inside G_STA, or book the treasury view; add a band on the transfer |
| BS-8 | major (Checkpoint B) | factors / closure | The group saving profile is implausible: H_R1 31% vs H_R5 13%; rural 27.1% vs urban 25.7%, the reverse of IFPRI (21.3% / 24.0%); rural moved away from IFPRI in balancing | s.2 table; closure-19, factors-19 | Revisit the factor-income gradient (D2-19 sensitivity); consider rural and urban saving-rate bands |
| BS-9 | minor | taxes | Union CGST (8,62,332) and compensation cess (1,48,508) end exactly on the +5% top of their cash-vs-accrual bands (t1.cgst, t1.gces), and SGST moved -2.8%. Union production subsidies were cut 30% (32,847 to the States) until p10a.centre_net bound. The bands, not evidence, set these levels, because G_CEN was short | `balancing_constraints.parquet`; taxes explanations | Narrow the bands to evidenced cash-accrual gaps (GST settlement timing) so the Centre/State gap must be resolved by government's flows |
| BS-10 | minor | taxes | T_CIT <- E_NFPU +64% (share of CIT 8.3% -> 13.5%) with no CPSE tax source (the DPE survey was unreadable, taxes-27) | taxes.yaml item | Find a CPSE income-tax figure (DPE Public Enterprises Survey, CAG) or band T4a by sector |
| BS-11 | minor | government | R18 `psu_revenue_grants` is `derived` from IGAS-2 but role free-low; cut 44% (24,017 -> 13,389) | prior_status derived, role free | Anchored, or a band on its published total |
| BS-12 | minor | factors / government | After balancing, the GG CFC split (F4b, States 0.677) and the C2a Centre/State split, built from the same key, have moved in opposite directions | factors-22 | Tie them with a constraint, or accept and document |
| BS-13 | minor | closure | `docs/phase2/issues/closure.md` still quotes the 01:10 figures (Z -11.44 lakh, H_U5 -5.5%) in closure-3, -9, -16 and the tables | closure-20 (OPEN) | Refresh before Checkpoint B |
| BS-14 | minor | timeseries | `timeseries` was rerun at 03:39. F35 and M13 now pass on the balanced SAM (closure-18 resolved). But `top_flows_sam_check.parquet` has 10 'unexplained' flows: F14, F15, F16, F24, F27-F30, F34, and F48 at +5.70 lakh | `top_flows_sam_check.parquet` | Outside this audit: for the timeseries owner and verifier |

## What would fix most of it

Declare as constraints the published totals that are now free: COFOG current transfers, R9d, outside-treasury CSS and R18 (government), FC sub-sector saving and the R17 supplement total (fincorp). Then rerun. The States' and E_NFPU's surpluses would have to leave through evidenced flows or show as slack. Slack is the honest outcome if the sources really conflict, and the SPEC treats it as a finding rather than a defect.

## Files

- Test: `tests/verify/test_sam_balanced_audit.py`: 54 passed, 3 strict xfail (BS-1, BS-5, BS-6). Run it with `uv run python -m pipeline test tests/verify/test_sam_balanced_audit.py`.
- Scratch recomputation scripts, not committed: in the session scratchpad (`audit1.py` to `audit6.py`).

## Re-verification (wave C close-out, 2026-10-01)

Re-verifier: an agent that built none of the SAM, the balancer or this audit (SPEC rule 3). Scope: the balanced run of 05:41 (`balancing_run.json`: NEWTON, path `interior-point fallback`, 249 steps; 3,893 entries, 3,698 variable, 195 fixed, 1,062 anchored; 429 constraints; objective 113,697.900089; no slack; certificate passed), and the edits the fixing agents made to `tests/verify/test_sam_balanced_audit.py` after the auditor wrote it. The file is untracked, so there is no `git diff`. I compared it with the report above and recomputed every changed expectation.

**Method.** I wrote my own scratch scripts in the session scratchpad (`rvc_kkt.py`, `rvc_ident.py`, `rvc_probe*.py`, `rvc_expl.py`), not committed. They read `data/sam/2023-24/*.parquet` and `data/clean/**` with DuckDB and numpy and import nothing from `pipeline`. The probes use the framework only to *drive* the solver; an independent certificate judges every answer. Weights come from DESIGN_BRIEF s.5.1, account groups from `accounts.yaml`.

### 1. Independent KKT certificate on the published balanced SAM

| Check | Result |
|---|---|
| Every account (all 128, including the sinks) row = column | max 7.0e-6 crore (C_TXAP) |
| Fixed entries unchanged; X_DISC entries all fixed and unchanged; sign flips | 0 of 195 changed; 0; 0 |
| Anchored boxes | max violation 4e-14 crore. 8 entries are on their bound, the same count as the run: A_COMM, A_HOTL, A_TRNS P1, C_FOFI <- A_CNST P2, C_TRAD <- M_TTM P3 (the Rs 1 crore SUT allowance), E_RBI <- F_GOSC F4a (-1%), E_RBI <- G_STA R3a sdl (-2%), G_STA <- T_PIT T2x (-1%) |
| 429 constraints recomputed from `constraints.parquet` (selection, kind, band) | 0 violated (max 3e-6 crore). Member counts and lo/hi equal `balancing_constraints.parquet` for all 429, so nothing was widened. My sums equal its `balanced_sum` to 8e-6. 92 selections are empty, all of them target-0 `equal` (89 production, 3 factors) or `max` |
| Bands at a bound (within 1e-3 crore) | 174, the same as the framework's `binding` count |
| Objective sum w\|a\|(z ln z - z + 1) | 113,697.900089, the same as the run |
| Multipliers by weighted least squares (lambda per account, mu per band at a bound; weight \|x\| capped at 1e4) | stationarity residual 4.4e-10 on interior entries of Rs 1,000 crore or more, 3.7e-7 on those of Rs 1 crore or more |
| Primal from dual: every variable entry = a clip(exp(-s(dlambda + sum mu)/w), box) | max 3.1e-5 crore (A_TRAD <- C_TRAD), so the 6-decimal rounding of the file. Signs at all 8 bounds are correct |
| Band multipliers on the wrong side | 0 of 174. Largest \|mu\|: `gov.r18.psu_revenue_grants` 0.640, `gov.r9d.railways` and `posts` 0.465, `r17.payer.e_nfpu.*` 0.46 |
| Own dual function q(lambda, mu) against f | gap 6.4e-7 crore, **5.7e-12 relative** (limit 1e-8): a proof of optimality that does not depend on the solver |

Re-solving the real prior (scratch probe; the wave-B verifier's own certificate judges it) reproduces the published entries to 5e-7 crore in three ways: as run, with the fallback forced (`NEWTON_FIRST_TRY = 1`), and with plain dual Newton allowed 2,000 steps. The last one converges *directly in 105 steps*, so the fallback was triggered here only because Newton's first-try budget is 100 (RV-C-4). One caveat on the published file: the wave-B certificate fits stationarity over every interior entry without weights, and on this file it reads 1.2e-3, because entries below about Rs 0.001 crore lose precision at 6 decimals. On the solver's unrounded x it passes. Any certificate run on the published file must weight by \|x\|, as mine does.

### 2. SPEC acceptance identities, recomputed with my own DuckDB SQL: 67 checks, all pass

| Identity | Balanced minus source | Tolerance |
|---|---:|---:|
| GDP by production / income / expenditure vs NAS 1.1; D4 = 0 | +0.61 / +0.61 / +0.61; 0 | 10; exact |
| GVA basic; product taxes less subsidies | +2.13; -1.52 | 5 |
| PFCE; GFCE (both on their +-1 band edge) | -1.00; +1.00 | 1 |
| CIS; exports; imports; GFCF + valuables | -0.04; +0.74; +0.79; +1.04 | 5 |
| GG saving vs NAS 1.9; GG FCE and GDI vs NAS 1.14 | +0.50; +1.00; +1.50 (all on edges) | 0.5; 1; 1.5 |
| Union CIT; income tax; excise; compensation cess; customs | -0.000%; +0.008%; **+5.000%**; **+5.000%**; -1.815% | 0.5%; 1%; 5%; 5%; 2.5% |
| States SGST; VAT; excise; income tax | -1.40%; -0.62%; -0.46%; **-1.000%** | 5%; 15%; 15%; 1% |
| Union gross tax, five heads; SGST / FC16 (28 States) | +1.88%; 103.65% | 5%; >= 95% |
| R1 devolution = FA 901 lines; tax accounts pass everything to GOV | 0.00; 0.00 | 1; 0.01 |
| RoW current receipts / disbursements vs NAS 6.1; surplus; K5 | +0.74 / +0.74; 0.00; 0.00 | 1; 2; 0.5 |
| D2 = SUT CIF; D2 vs NAS 6.1; CE from / to RoW | 0; +0.24; 0 / 0 | 1e-6; 1; 0.5 |
| K8b liabilities / assets vs NAS 6.1; R_ROW, K_ROW close | 0 / 0; 0 | 1; 0.01 |
| All 11 instrument markets clear; household financial assets / liabilities / net vs NAS 5.3 | max 1e-5; 0 / 0 / 0 | 0.01; 0.5 / 0.5 / 1 |
| Saving: households, public NFC, private NFC, FC, public FC, private FC, national | -0.50, 0, 0, +1.00, 0, +1.00, +1.00 | 0.5, 1, 1, 1, 1.5, 1.5, 2 |
| Household GDI (BS-3: the sum of the parts' tolerances); GNDI | -1.6075 (tolerance 1.6085); +0.89 | 1.61; 3 |
| X_DISC closes and is unchanged; D1 vs the published residual | 0; -0.1075 | 0.01; 1 |
| R9a + R10 + R18 vs NAS 4.2 COFOG current transfers (BS-5) | **+5.0000%** (10,55,911.73 vs 10,05,630.22) | 5% |
| R9d railways vs AFS Railway Funds (BS-6) | **+10.0000%** (65,781.83 vs 59,801.66) | 10% |

### 3. The fixers' edits to the audit test, and mine

| Expectation | Who | Verdict |
|---|---|---|
| BS-5 strict xfail removed; `test_gg_current_transfers_within_5pct_of_nas_4_2` now passes | government fixer | **Confirmed.** PM-KISAN (FA 2401.00.130, 51,616.9074 = the clean `fa9.2401.00.130`) is now R10 `pm_kisan` G_CEN -> H_* (10 entries). taxes' `p10a_items` no longer carries it, so it is not double counted. `gov.cofog.current_transfers` (R9a + R10 + R18, +-5% of NAS 4.2) is declared and binds at its top. The test body is unchanged, and the fix is the one the audit proposed |
| BS-6 strict xfail removed; `test_r9d_railway_pensions_within_10pct_of_the_afs` passes | government fixer | **Confirmed.** `gov.r9d.railways` / `posts` (+-10% of the AFS and MH 3201.07 totals) are declared and bind at their top. Test body unchanged |
| BS-1 xfail kept, reason now "12 fincorp items" | fincorp fixer | **Confirmed.** Exactly 12 items begin "Unexplained", all in fincorp.yaml (8 entries, 4 cells, the E_NFPU flows of fincorp-37). The verdict count over all 326 items is 224 explained, 90 "level unexplained", 12 unexplained, which equals BALANCING.md's new summary line |
| Every other tolerance and target | - | Unchanged against the report's table in s.1 |
| BS-5 and BS-6 tolerances + `NUM` | **me** | Both now sit exactly on a declared band edge. They passed by 1.0e-6 crore, i.e. by the file's last rounded digit (RV-C-2). Following the file's own convention for declared edges, `NUM` (1e-3) was added. The 5% and 10% expectations are not relaxed |
| Matrix CSV tolerance 0.005 -> 1e-5 | **me** | BS-2 (7) is confirmed fixed: the CSV prints 6 decimals. It differs from the entries by at most 2e-6, and its row - column gap is at most 3e-6 |
| z-range docstring | **me** | Was 0.517-1.936; now 0.155-6.46 (RV-C-1). The 0.1-10 bound still holds |
| New `test_duality_gap_and_primal_from_dual_independently` | **me** | The certificate of s.1 as a regression test (gap <= 1e-8 relative, primal from dual <= 1e-4 crore, multiplier signs) |

`uv run python -m pipeline test tests/verify/test_sam_balanced_audit.py`: **57 passed, 1 strict xfail (BS-1)**. That is 56 + 1 before my new test (the 54 + 3 of the report, with BS-5 and BS-6 now passing).

Wave C C-6 (per-block explanation files, D2-22), probed with temporary files. `report.load_explanations` reads the shared file and the per-block files. A key duplicated across files or within one file is an error naming the file, and so is a file not named after a DESIGN_BRIEF block. Cell items may sit in any file. My own threshold rule gives 223 entries and 103 multi-entry cells. That equals `balancing_log.parquet` and `balancing_run.json`, and the 326 items in the seven block files cover them one-to-one (the audit test passes).

### 4. Findings

| # | Severity | Owner | Finding | Evidence | Fix (proposed, not done) |
|---|---|---|---|---|---|
| RV-C-1 | major (Checkpoint B) | government / fincorp | **The Wave C bands bound the audited flows, but at their edges, and the pressure moved to the next weak entries.** COFOG current transfers sit at +5.000%, R9d railways and posts at +10%, R18 psu / coop at -10%, CSS outside treasury at -10%. The R17 E_NFPU lines, `r17.premiums`, `r17.supplements` and `k2a.rbi_ar_basis` are on their edges, and Union excise and compensation cess at +5% of cash. E_NFPU's prior surplus now lands on E_NFPU <- E_NFPR R8 (z 0.156, -84%), E_NFPU <- G_CEN R3a (z 0.171, -83%), E_BANK <- E_NFPU R5 `mf_lookthrough` (z 6.46) and R5 loans (+59%). The extreme z widened from 0.517-1.936 to 0.155-6.46, and the objective rose 56% (72,975 -> 1,13,698). Nothing is hidden: government-36, fincorp-37 and the 12 "Unexplained" items say so. But these levels are set by band edges, not by evidence | s.1 multipliers; `balancing_constraints.parquet` (174 binding); fincorp-37 | The E_NFPU and G_CEN prior gaps are the cause (a NAD question on departmental-enterprise surplus, fincorp-37 option 1; E_NFPU GOS, option 2). Decide at Checkpoint B; adding more bands would only move the surplus again |
| RV-C-2 | minor | verifier test (fixed here) | BS-5 / BS-6 tests passed with a 1e-6 crore margin, because the declared band equals the test tolerance and binds | s.2: +5.0000% and +10.0000%, margins 1.0e-6 | Done: `+ NUM`, as for the file's other edge tests |
| RV-C-3 | minor | framework | `balancing_run.json` (and BALANCING.md's summary and Technical detail) round the certificate and solver tolerances to 6 decimals. They print `"tolerance": 0.0`, `"kkt_tol": 0.0`, `"newton_tol_rel": 0.0`, `duality_gap_rel 0.0`, `stationarity 0.0`, while the actual values are KKT_TOL = 1e-8, NEWTON_TOL_REL = 1e-12 and a gap of about 6e-12. A reader is told that the tolerance is zero | `balancing_run.json` lines `certificate`, `tolerances` | Write these fields with significant digits (for example `%.3g`), which is still deterministic |
| RV-C-4 | minor (note) | framework | On the final problem the interior-point fallback ran only because direct Newton needs 105 steps against `NEWTON_FIRST_TRY` = 100. Allowed 2,000 steps, it converges directly to the same optimum (6.75e-7 crore). After C-1 the fallback is a safeguard here, not a necessity | scratch probe `rvc_probe.py` | None needed; worth one line in FRAMEWORK_REQUESTS "Results" |

**Verdict.** The balanced SAM is a certified optimum of the declared problem. My certificate is independent and the gap is 5.7e-12. Every SPEC acceptance identity holds when recomputed from source, and the fixers' changes to the audit test are confirmed. My edits are robustness only and do not relax any expectation. The economic findings stay Checkpoint B items: BS-1 (12 items), the other BS items as their owners dispositioned them, and RV-C-1.
