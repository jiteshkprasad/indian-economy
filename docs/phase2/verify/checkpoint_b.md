# Verification: docs/phase2/CHECKPOINT_B.md

Verifier: an agent that built nothing in Phase 2 and wrote no part of the note (SPEC s.3 rule 3). Date: 2026-10-01. Object: `docs/phase2/CHECKPOINT_B.md` as written at 10:52 on 2026-10-01, against the final run written at 10:10 (`data/sam/2023-24/balancing_run.json`: NEWTON, 83 iterations, objective 114,127.730687, certificate ok). Amounts in Rs crore unless stated; 1 lakh crore = 1,00,000 crore; GDP 2023-24 = 2,90,73,286.73 crore (NAS 1.1, clean `s1_1.gdp.current`).

**Verdict: the note's numbers are sound.** Every table cell in sections 2 and 3, every measured acceptance figure in section 1 and every count in section 4 recomputes from the Parquet files. Of 883 figures checked, 873 are confirmed as written. 10 are flagged in 7 findings: 3 are wrong at their stated precision (the D2-11 alternative, 1.18 not 1.17 lakh; the income-tax and customs bands, 0.5% and 1% declared, not 1% and 2.5%) and 7 are right on an unstated or mixed basis (2,203 "non-empty" cells, three "." cells, 304, 1.61 vs 1.58, RBI 0.97 vs 1.01). There is 1 wrong cross-reference, and 14 more findings where the figure is right but its label or framing would mislead a finance-trained reader: 22 findings in all. Three are medium: "almost entirely on low-confidence entries" (29% of the moves are on medium-confidence entries), "taxes by type held to within a rupee crore or two" (several are 1.4% to 5% off cash), and the RBI saving comparison in 5.7 (not like-for-like).

## Method

- No pipeline code was imported to compute anything. I read Parquet with DuckDB (and pandas for pivots) in scratch scripts in the session scratchpad, not committed: `s2*.py` (section 2), `s3*.py` (section 3), `s4*.py` (section 4), `acc.py` (acceptance identities from `data/clean/**`), `s5a.py`, `tx.py`, `ts*.py`, `stale.py`.
- Account groups come from `pipeline/sam/accounts.yaml`: COM + MRG = Commodities; CAP + DSTK = Capital; INST = Financial instruments; DISC = Discrepancy; HH split by `H_R*` / `H_U*`; GOV split into `G_CEN` / `G_STA`.
- Source targets for the acceptance tests were read from `data/clean/mospi_nas_2026`, `union_fiscal`, `state_fiscal` and `io_tables` by series id (the same ids the audit test names; the SQL is mine).
- Text claims were checked against `BALANCING.md`, `DECISIONS.md`, `ISSUES.md`, `docs/phase1/RECONCILIATION.md`, `docs/phase2/issues/*.md`, `docs/phase2/FRAMEWORK_REQUESTS.md`, the satellites in `data/sam/2023-24/blocks/*_satellites/` and `pipeline/sam/explanations/*.yaml`.
- I also ran `pipeline manifest --check` (up to date), counted `data/manifest.json` (338 files), collected the offline suite (4,246 collected, 1 deselected) and re-ran it (result below). I did not re-run `pipeline repro`; its 338-file result is recorded in `docs/phase2/FRAMEWORK_REQUESTS.md`.

## Counts

| Section | Figures checked | Confirmed | Discrepant (see table) |
|---|---:|---:|---:|
| Header, conventions | 2 | 2 | 0 |
| 1. Build, outputs, run result | 27 | 26 | 1 (2,203 "non-empty") |
| 1. Acceptance table | 68 | 66 | 2 (income-tax and customs bands; plus 1 wrong cross-reference in the text) |
| 1. Tests and repro | 7 | 7 (6 re-run or recounted; repro from its record only) | 0 |
| 2. Aggregated SAM (15 x 15 cells, incl. 120 "." cells) | 225 | 222 | 3 "." cells are non-zero (label) |
| 2. How-to-read, shares, moves | 25 | 24 | 1 (304: definition unstated) |
| 3. Household table (13 rows x 15 numeric columns) | 195 | 195 | 0 |
| 3. Text and caveats | 25 | 25 | 0 |
| 4. Balancing report | 81 | 81 | 0 (4 labels) |
| 5. Surprises | 117 | 115 | 2 (1.61 vs 1.58 basis; RBI 0.97 vs 1.01 basis), plus labels |
| 6a / 6b / 6c | 89 | 88 | 1 (D2-11: 1.17 should be 1.18) |
| 8. Phase 3 reliance, time series; run record | 22 | 22 | 0 (2 framings) |
| **Total** | **883** | **873** | **10 figures; 22 findings in all** |

"Confirmed" means equal to my recomputation at the stated precision, or to the cited file where the figure is a quotation of an issue (for example the ratios of 5.2). The findings table lists every case, including the ones where the number is right but the wording is not.

## What was recomputed, by section

**Section 1.**
- Account counts from `accounts.yaml`: 34 + 34 + 1 + 4 + 10 + 6 + 2 + 12 + 1 + 11 + 1 + 11 + 1 = 128. Entries 3,893; constraints 429; fixed 195 (all 52 X_DISC entries are fixed; none moved); 128 x 128 CSV.
- Run record (`balancing_run.json`): 83 iterations, max balance residual 2.32e-07, relative duality gap 3.15e-13, total slack 0, nothing widened, objective 114,127.730687. "BALANCED" is BALANCING.md's wording (the JSON says `optimal`, `ok: true`).
- Acceptance table, from `sam_entries_balanced.parquet` against clean targets. Every value matches:

| Test | Recomputed (balanced minus source) |
|---|---|
| GDP production / income / expenditure | +0.6086 / +0.6086 / +0.6086; NAS discrepancy 0, SAM D4 0 |
| GVA basic; net product taxes | +2.1330; -1.5244 |
| PFCE, GFCE, CIS, exports, imports, GFCF + valuables | -1.0000, +1.0000, -0.0431, +0.7395, +0.7869, +1.0431 |
| GG saving; GG FCE; GG GDI | +0.5000; +1.0000; +1.5000 |
| Union CIT, income tax, excise, compensation cess, customs | -0.0001%, +0.0082%, +5.0000%, +5.0000%, -1.8153% |
| States SGST, VAT, State excise, income taxes | -1.4043%, -0.6177%, -0.4598%, -1.0000% |
| Union gross tax, five heads; devolution | +1.8761%; 11,29,493.71 both sides |
| RoW receipts, disbursements; CA balance; foreign assets, liabilities | +0.7395, +0.7395; -2,08,890.71 both; 6,70,569.37 and 8,86,570.33 both |
| Instruments; HH financial assets / liabilities / net | max gap 1.0e-06; 36,02,198.51 / 19,09,286.70 / 16,92,911.81 exact |
| Saving: HH, public NFC, private NFC, FC, national | -0.5000, 0, 0, +1.0000, +1.0000 |
| Household GDI; GNDI | -1.6075 (identity-test tolerance 2.5 = PFCE 1 + K4 0.5 + D1 1, read from `constraints.parquet`); +0.8925 |
| Explanations | 223 entries and 103 multi-entry cells need one (my threshold rule); 326 items cover them, 0 missing, 0 stale (change within max(20%, Rs 500) of the item); verdicts 224 / 90 / 12 |

- Largest account gap in the published file is 9.0e-06 crore (6-decimal rounding of the file); the note's "0.000000" is the solver's value. Not a finding.

**Section 2.** All 105 numeric cells of the aggregated table, its row and column totals and the grand total 2,532.21 match to 0.01 lakh; row totals equal column totals to 1.3e-10. How-to-read cells: K_GCEN <- G_CEN -4,27,343 and K_GSTA <- G_STA +1,08,959 (GG -3,18,384 = -1.095% of GDP); G_STA <- G_CEN = R1 11,29,494 + R2 4,76,308 + T2b 1,23,050 + R3 16,451; Taxes <- Activities is T_PROD only (-57,442); X_DISC <- H_* 5,71,133 (1.964% of GDP). Shares of the balanced absolute value (2,678.11 lakh) by `prior_status`: official 47.11%, derived 8.42%, estimated 44.47%. Sum of absolute changes 28,38,075 (9.762% of GDP, 1.060% of SAM value); free 28.26 lakh; anchored 12,238.6 crore; fixed 0.

**Section 3.** Columns defined by the paying (receipts) or receiving (outlays) account group: labour = F_LREG + F_LCAS; mixed income = F_MIXD; GOS = F_GOSC; from corporations = all E_* (R8a, R9c, R9d, R17); from government = G_CEN + G_STA (this includes R8a small-savings and G-sec interest); from abroad = R_ROW; consumption = COM + MRG; income tax = all T_* (only T_PIT has entries); saving = K_HH. Persons = sum of `persons` in `households_satellites/hh_group_map.parquet`. Saving rates use prior and balanced entries. Every one of the 195 cells matches at the stated precision (borderline roundings checked: R3 prior 28.0495%, R5 prior 12.6538%, U1 balanced 22.8496%). Text: U5 5.96% of persons, 21.70% of receipts, 21.85% of saving; R4 21.51% of saving; IFPRI-rate saving 48.006 lakh; factor income 192.4604 lakh, 69.99% (U4) to 85.50% (R1) of receipts; K4a rise 6.22% (R4) to 7.82% (U4). Caveat figures match households-1, -2, -4, -15, factors-19/-24, taxes-8, V-GOV-14.

**Section 4.** Prior gaps from `sam_prior.parquet` (row minus column): G_STA +4,50,425.77, K_HH -3,84,546.82, E_NFPU +3,12,829.18, G_CEN -2,98,947.95, E_NBFC +2,32,892.60, E_INSP -1,21,568.42, E_NFPR -1,13,892.24, E_BANK -1,02,837.81, E_RBI +25,645.50; everything else at most 1.41 crore. Gross move by block and share of the block's absolute prior: all nine rows match (production 151.78 crore, 0.000136%). 2,229 moved entries is the framework's count (`abs(change) >= 1`; 11 entries sit at exactly 1.000000 crore, so a recount on the 6-decimal file gives 2,223 to 2,234 depending on the inequality). 174 constraints at a band edge: my own test (within min(1e-3, 1e-3 x width) + 1e-6 of a bound, members > 0) gives 174. Largest-moves table: K4a 55,05,784 -> 58,90,330; R8a to households +2,14,518; K3a Centre -3,39,090 -> -4,27,343, States +20,705 -> +1,08,959; C2a Centre -87,427; E_NFPU <- E_NFPR R8 1,17,172 -> 18,299 (-84.4%); R5 E_NFPU to banks and NBFCs 2,02,444 -> 3,12,194 (+54.2%; the four "Unexplained" entries alone 2,02,354 -> 3,11,616); K2a banks 4,58,959 -> 4,11,607, NBFCs 3,37,883 -> 4,05,210, insurers 1,00,423 -> 77,972, RBI 94,183 -> 96,659; GG R4 deposit interest 1,05,296 -> 47,407; R10 State cash schemes 2,14,325 -> 2,77,357 (+29.4%), COFOG band 10,05,630 -> 10,55,912. Direction-only items: fincorp 32 (entry items' moves 2.52 lakh), rest_of_world 23, government 18, taxes 17. The 12 "Unexplained" items: 8 entries (moves 1.45 lakh) and 4 cells, all E_NFPU. GRAS: K4a +1,90,794 against +3,84,546 (about half); 229 GRAS findings; on tax rows GRAS leaves CGST, SGST and Union excise at the prior and moves P9a by 54,865.

**Sections 5 and 6.** Z path -11,44,073.44 / -9,57,528.03 / -4,36,163.72 / -3,84,546.82 (closure-3, government-1, fincorp repair table); household closing moves R8a +2.15, R5 +0.85, R10 net +0.58. Ratios of 5.2 equal timeseries-5; TAX-8 -3.81% (RECONCILIATION). K9 net: K_BANK -4,90,718 -> -5,21,890; K_GSTA -2,17,039. F48 27,87,865 vs 22,17,361 (+25.73%). States' subsidies P9a 3,45,719 + P10a 3,00,929 = 6,46,648 vs St 36 3,29,610 (1.962x; 2.224% and 1.134% of GDP). T3 2,16,881 -> 2,34,195 (0.806% of GDP); PM-KISAN 51,617 -> 49,036. MH 0021 = 10,10,947.77 (Receipt Budget heads and FA total + 901 line agree). Band table 6b: every target, balanced value and edge matches `balancing_constraints.parquet`; government 28 of 38 bind. 6c sizes match fincorp-34, -37, factors-24, households-1, -19, capital_financial-30(d), government-2 (remainder 28,079), government-28, rest_of_world-27 (current run: E_NBFC +23,217), V-FIN-9, V-FIN-10.

**Section 8.** `top_flows.parquet`: 2,504 rows, 69 flows (54 F, 15 M), 1950-51 to 2025-26, 633 derived (476 linked + 157); the 10 linked flows are F01, F03, F05, F06, F07, F37, M01, M02, M03, M06. `top_flows_sam_check.parquet`: 57 pass, 11 explained, 1 no_check.

## Findings

Severity: **medium** = a reader would draw a wrong conclusion; **low** = imprecise or ambiguous, conclusion unaffected; **trivial** = cosmetic.

| # | Where | Note's text | Correct value or framing, with source | Severity |
|---|---|---|---|---|
| CB-1 | s.2 "Where the numbers come from" | "The moves sit almost entirely on estimated, low-confidence entries" | Estimated: 28.22 of 28.38 lakh (99.4%). But low-confidence entries carry 19.78 lakh (70%) and medium-confidence 8.26 lakh (29%) (`sam_entries_balanced`, by `confidence`) | medium |
| CB-2 | s.8 "Reliable: official totals, held to within a rupee crore or two" | lists "Taxes by type at cash (within their stated bands)" | Taxes by type are not within a crore or two of cash: Union excise +15,268 (+5.0%), compensation cess +7,072 (+5.0%), CGST at its +5% ceiling, SGST -11,812 (-1.4%), customs -4,232 (-1.8%) (acceptance recomputation). Only devolution is exact | medium |
| CB-3 | s.5.7 RBI | "It ends at 0.97 lakh of saving, against 1.01 lakh on the RBI Annual Report basis" | Not like-for-like. The 1.01 lakh (NAS public FC saving less public FC GOS, 1,01,277; the prior's AR-basis figure was 1,01,301, `k2a.rbi_cash_basis_evidence`) excludes the 7,118 SDR-charge debit the SAM books on the RBI; the balanced 96,659 includes it and sits on the upper edge of `k2a.rbi_ar_basis` (94,159 +- 2,500). On the AR basis the balanced RBI saving is 96,659 + 7,119 = 1,03,778, i.e. 1.04 lakh, Rs 2,500 crore **above** the 1.01 (fincorp-1, fincorp-34, constraints.parquet) | medium |
| CB-4 | s.1 acceptance table, last row | "all on public NFCs (section 5.5)" | Section 5.6 (5.5 is the States' subsidies) | low |
| CB-5 | s.5.6 | "its interest and dividend receipts are cut by up to 84%. These are the 12 'Unexplained' items." | The -84% is E_NFPU <- E_NFPR R8 (distributed income), verdict "level unexplained", not one of the 12. The 12 cover R5 interest paid (+54%) and interest received: R4 deposits -37%, R3a G-secs -83% (fincorp-37; `explanations/fincorp.yaml`) | low |
| CB-6 | s.5.9; s.5.11 row 2; s.6a D2-4 | "Phase 1 found ... 1.61 lakh (5.2%) ... cuts the gap to 0.47 lakh (1.60%)"; D2-4: "goes back to 1.58 lakh (5.5%)" | Two bases. Phase 1 TAX-1 (incl. import duty) 1,60,570 (5.21%) less vehicle tax leaves 50,243 (1.6%). The taxes block's basis (excl. customs) is 1,58,230 (5.5%) less 1,10,848 = 47,383 (1.60%) (RECONCILIATION TAX-1; taxes-1). As written, 1.61 - 1.11 does not give 0.47 | low |
| CB-7 | s.6a D2-11, "Effect" | "About 1.17 lakh more income tax on households (0.116 x MH 0021, derived here)" | 0.9017332 - 0.7854833 = 0.1162499; x MH 0021 10,10,947.77 = 1,17,523 crore = **1.18 lakh** (`taxes_satellites/direct_tax_split`; FA 0021 total + 901; RB 0021 heads). 1.17 comes from rounding the factor to 0.116 | low |
| CB-8 | s.1 "The independent audit ..." | report "in docs/phase2/verify/balanced_sam.md" recomputes all of these | The report audits the 03:00 run and re-verifies the 05:41 run (objective 113,697.90); the final run (10:10, objective 114,127.73) was written after it. Its test file does re-check the final run when the suite runs; the report does not | low |
| CB-9 | s.2 table note | "A '.' means zero." | Three "." cells are non-zero, under 0.005 lakh: Centre <- HH rural 20.7, Centre <- HH urban 39.9, RoW <- States 158.3 crore | low |
| CB-10 | s.1 Outputs | "2,203 non-empty cells" | 2,203 stored cells, of which 2,169 non-zero; 34 are explicit zeros (C_* <- X_DISC, D4 = 0) | low |
| CB-11 | s.2 shares table | "Entries moved by 10% or more (304 entries)" | 304 counts entries that moved by 10% or more **and** by at least Rs 1 crore; without the Rs 1 crore floor it is 325. The 2.0% share is the same either way (1.997%) | low |
| CB-12 | s.1 build; s.4 | "429 constraints: published totals, each with a tolerance"; "174 of the 429 constraints end on a band edge" | 92 of the 429 select no entries (target-0 placeholders: 89 production, 3 factors); 32 are floors or caps (factors `v1a_floor`, `v2a_cap`); several are judgement bands (f4b, t4a). 174 of the 337 non-empty constraints bind | low |
| CB-13 | s.4 largest moves, R8a row | "Households' property income from FCs and NFCs (R8a) ... +2.15" | +2.15 is all R8a to households: +1.97 from FCs and NFCs (1,97,439) and +0.17 from the Centre and States (17,079: small savings and G-sec interest) | low |
| CB-14 | s.4 largest moves, C2a row | "GFCE: public administration, Centre to States (C2a) ... 0.87 moved" | 0.87 is all of C2a: PADM 0.71, EDUC 0.07, CNST 0.06, HLTH 0.03 | low |
| CB-15 | s.5.1; s.4 | "State cash transfers (+0.58)" | +0.58 is R10 net: the States' cash schemes +0.63, the Centre's R10 lines -0.05 | low |
| CB-16 | s.4 Cross-check | "+35% instead of +86% on R9d in the earlier audited run" | True of the 03:00 run, but in the final run R9d is bounded: cross-entropy +10% (band edge), GRAS +35% (24,593 of 70,490), i.e. GRAS now moves it **more**. A current example of "same way, by less": R8a to households +2.15 lakh vs GRAS +0.24 | low |
| CB-17 | s.8 time series | "The 11 explained include five moved by balancing (Union GST +5.6% vs cash, SGST, Union excise +5.0%, grants, pensions; timeseries-26)" | Seven flows carry a balancing move: F14, F15, F16, F24, F25 (Union interest, +23,190, all of its residual), F27, F28. F14's +5.6% is against the Receipt Budget "Total GST", which excludes UTGST; like-for-like it is +5.0%, the band ceiling | low |
| CB-18 | s.6a D2-21, "Effect" | "Z would be about -1.90 lakh, FCs about -1.16 and E_NFPU about +2.18 lakh (fincorp-27)" | These are on the fincorp-27 repair build (Z -4.36 then, before PM-KISAN), not on the current prior (Z -3.85). Say so, or recompute | low |
| CB-19 | s.6a D2-7, "Effect" | "The RBI's unexplained reserve income falls from 25,646 to 18,717 crore" | That is on the prior. In the balanced SAM balancing already removed most of it: `reserve_income_unexplained` 25,645.50 -> 7,713.51 | low |
| CB-20 | s.5.6 | "passing 95.6% of their primary income on to GG" | The source says "on as D6 + D7" (social benefits and other transfers, incl. pensions to households). government-33 reads it as the pattern of a surplus passed to GG and notes that St 2.1A does not split D62 from D7 | low |
| CB-21 | s.1 acceptance table, Union taxes row | "-0.00%, +0.01%, +5.00%, +5.00%, -1.82% (bands 0.5%, 1%, 5%, 5%, 2.5%)" | The measured values are right, but two "bands" are the audit test's tolerances, not the declared ones. Declared (`constraints.parquet`, t1.*): CIT 0.5%, income tax **0.5%**, excise 5%, cess 5%, customs **1%**. Customs' -1.82% is against the Receipt Budget total incl. export duty, which the SAM books in T_OPRT (D2-12); against its band's target (cash less export duty, 2,29,775.09) it is -0.39% | low |
| CB-22 | s.6b row 3 | "Railway and postal pensions (R9d) +-10% of AFS" | Railways: AFS 59,801.66. Posts: Finance Accounts MH 3201.07 less NPS (10,688.30), not AFS (government-33; `gov.r9d.posts`) | trivial |

### Recommended replacement text

- CB-1: "The moves sit almost entirely on estimated (free) entries: 28.22 of the 28.38 lakh. Low-confidence entries carry 19.78 lakh and medium-confidence ones 8.26 lakh."
- CB-2: move taxes out of the "within a rupee crore or two" list and add: "Taxes by type: within their cash-vs-accrual bands, up to +-5% of cash (Union CGST, compensation cess and excise sit at +5%; SGST -1.4%; customs -1.8%). Devolution is exact."
- CB-3: "RBI. It ends at 0.97 lakh of saving, the upper edge of its band (0.94 +- 0.025 lakh: the NAS-derived 1.01 lakh less the 0.07 lakh SDR-charge debit the SAM books on the RBI). On the RBI Annual Report basis, which leaves that debit out, that is 1.04 lakh against NAS's 1.01 lakh."
- CB-4: "(section 5.6)".
- CB-5: "Its interest to banks and NBFCs rises by 54%, and its interest receipts on bank deposits and Union G-secs are cut by 37% and 83%: these are the 12 'Unexplained' items. Its receipts of private NFCs' distributed income are cut by 84% ('level unexplained')."
- CB-6 (5.9): "Phase 1 found SUT product taxes 1.61 lakh (5.2%) above Union + State receipts (TAX-1, import duty included). On the taxes block's basis, which leaves customs out of both sides, the gap is 1.58 lakh (5.5%). Booking State motor-vehicle tax (1.11 lakh) as a product tax (D2-4) cuts it to 0.47 lakh (1.60%)." In 5.11 row 2: "SUT product taxes vs receipts +1.61 lakh (Phase 1 basis; 1.58 on the taxes block's basis) | 0.47 lakh after D2-4 (5.9)".
- CB-7: "About 1.18 lakh more income tax on households (0.1162 x MH 0021 of 10.11 lakh, derived here), or 2.17 lakh; Z widens by the same".
- CB-8: "The independent audit, written by an agent that built nothing, recomputes all of these from Parquet without the pipeline code: `tests/verify/test_sam_balanced_audit.py`, which the suite runs on the final run. Its report, `docs/phase2/verify/balanced_sam.md`, covers the 03:00 run and the re-verified 05:41 run; the close-out changes after it did not change any acceptance figure."
- CB-9: "A '.' means zero or under Rs 500 crore."
- CB-10: "`data/sam/2023-24/sam_balanced.parquet`: 2,203 cells (2,169 non-zero)."
- CB-11: "Entries moved by 10% or more and by at least Rs 1 crore (304 entries)".
- CB-12: "There are 429 constraints (337 select entries; 92 are empty target-0 placeholders): mostly published totals, plus some floors, caps and judgement bands, each with a tolerance." In section 4: "174 of the 337 non-empty constraints end on a band edge."
- CB-13: "Households' property income (R8a) | +2.15 (1.97 from FCs and NFCs, 0.17 from government)".
- CB-14: "GFCE, Centre to States (C2a; 0.71 of it public administration) | 0.87 moved".
- CB-15: "State cash transfers (+0.63; R10 net +0.58)".
- CB-16: "For the large moves it often goes the same way but by less: about half the K4a rise, and +0.24 instead of +2.15 lakh on households' R8a. Sometimes it goes further where the cross-entropy run is held by a band (R9d +35% against +10%), or takes a different route ..."
- CB-17: "The 11 explained include seven moved by balancing: Union GST (+5.0% of cash including UTGST, the band ceiling; +5.6% against the Receipt Budget total), SGST, Union excise (+5.0%), grants, Union interest, and Union and State pensions (timeseries-26, -29)."
- CB-18: "... (fincorp-27, on the repair build when Z was -4.36 lakh; not recomputed after PM-KISAN)".
- CB-19: "The RBI's unexplained reserve income in the prior falls from 25,646 to 18,717 crore (balancing already removes most of it: 7,714 is left in the balanced SAM)".
- CB-20: "passing 95.6% of their primary income on as D6 + D7, the pattern of a surplus passed to GG".
- CB-21: "-0.00%, +0.01%, **+5.00%**, **+5.00%**, -1.82% (declared bands 0.5%, 0.5%, 5%, 5%, 1%; customs is -0.39% of its band's target, cash less export duty, which the SAM books as another product tax under D2-12)".
- CB-22: "Railway and postal pensions (R9d) +-10% of AFS (railways) and MH 3201.07 (posts)".

## Not independently verifiable here

- `pipeline repro` (338 files byte-identical across hash seeds and threads): not re-run; recorded in FRAMEWORK_REQUESTS.md ("Repro"), and `data/manifest.json` lists 338 files.
- "Every institution's primary income matches NAS to rounding" (s.4): quoted from closure-3 (`institution_gaps`); not recomputed institution by institution.
- Sources' own values quoted through issue files (IFPRI rates, RTP bank and NBFC saving, IRDAI income, AIDIS class order, HCES persons) were checked against the issue files and satellites, not against the raw publications.

## Test suite

Re-run by me at 11:05 on 2026-10-01 (`uv run python -m pipeline test -q -p no:cacheprovider`): **4,221 passed, 1 deselected, 25 xfailed** in 9 min 47 s, the same counts as the note. 4,246 tests were collected (4,221 + 25), with 1 deselected. The run changed no tracked file. `pipeline manifest --check`: "data/manifest.json is up to date".
