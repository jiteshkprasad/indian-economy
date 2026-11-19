# finsector_markets: independent verification (first pass, second pass; close-out and final passes at the end)

## Second pass (re-verification of the builder's fixes, 2026-09-29, evening)

Verifier: separate agent, did not build the unit. Scope: the builder's fixes for V1-V10 (V1, the major one, in detail), the new dataset `finsector_markets_pfrda_sg` (PFRDA Table M7), and regressions in the other 9 datasets.

### Verdict

- **V1 is fixed as far as the published text allows.** The 7,320.22 cr footnote is in the provenance notes of all three AR 2024-25 contribution records: para 5.4, para 5.5 and App. 5(i). None of the AR 2023-24 records carries it. Issue -5 now advises using 2,26,198.57 for 2023-24 and subtracting 7,320.22 for 2024-25. The claim that neither PDF explains the +7,291.23 revision is true: a full-text search of both PDFs (all 259 and 268 pages, forward and mirrored text) finds "past accumulation" only on AR 2024-25 pp.70, 78, 137 and 236, and every hit is about 2024-25.
- Two residual caveats remain (V11, V12 below). Neither changes a number.
- **No regressions.** A full census of the 10 datasets compared 11,847 of 11,847 values and found 0 mismatches.
- The two spot-check failures the builder reported were caused by the verifier's own resolver, not by the data. The resolver now reads the T69 opening SIP count from the block of the FY that starts the day after its date. With that change the 7 rows match (for example, 2021-03-31 opening = 36,800,000, from the 2021-22 block).

### What was done

1. **Rebuild and tests.**
   - `fetch finsector_markets --offline`: OK, 28 files. `build finsector_markets`: 10 datasets, 11,847 rows.
   - `repro finsector_markets`: **REPRO OK**. The 12 files are byte-identical across hash seeds and thread counts and match the manifest.
   - `coverage`: 8 refs, all partial, none BROKEN. The new `pfrda_sg` M7d series are listed under S9.
   - `test -k finsector_markets`: 129 passed.
   - The unit tests (28) and the extended spot-check (29) pass together: 57 passed.
2. **Census extended to the new dataset.** `pfrda_sg` is resolved with the verifier's own locator: the month label in row 2, the measure caption in row 3, and the row whose column A reads `Total`. All 556 monthly cells (139 months × 4 measures) and the 33 derived FY sums, recomputed from the raw monthly cells, match.
   - The Total row equals the sum of the 32 state rows in every one of the 556 columns, so it is the national total, not a stray row.
   - FY sums exist only for complete FYs (2015-16..2025-26). Dec-2014..Mar-2015 is correctly left out.
   - An independent recomputation confirms the M7-vs-M4 agreement for SG: within 0.3 cr in every FY from 2015-16 to 2024-25, except 2022-23 and 2024-25 (within 12 cr). For 2023-24, M7d is 77,599.18 against M4d 77,599.20.

   | dataset | rows | compared | mismatches |
   |---|---|---|---|
   | irdai_summary | 1,140 | 1,140 | 0 |
   | irdai_life | 1,284 | 1,284 | 0 |
   | irdai_nonlife | 2,124 | 2,124 | 0 |
   | epfo_ar (PDF) | 361 | 361 (+36 hand anchors, +5 new PDF-text checks) | 0 |
   | pfrda_nps | 3,749 | 3,749 | 0 |
   | pfrda_sg (new) | 589 | 589 (33 derived recomputed) | 0 |
   | sebi_primary | 512 | 512 | 0 |
   | sebi_bonds_equity | 151 | 151 | 0 |
   | sebi_foreign | 868 | 868 | 0 |
   | sebi_mf | 1,069 | 1,069 | 0 |
3. **V1 checks against the raw PDFs** (in `test_v1_epfo_past_accumulation_in_raw_and_provenance`).
   - p.78, read with pdfplumber: "2,58,132.93\*\*" and "includes the amount of Past Accumulation of Rs. 7,320.22 Crore".
   - p.236, read with pypdf because pdfplumber mirrors this rotated page:
     - the line "Past Accumulation 7,320.22\*\* 7,320.22";
     - the table note "include the Contributions, Securities received on cancellation of exemption and Past accumulations";
     - the 22 zone rows sum to 2,50,812.70, which is exactly 7,320.22 below the Total of 2,58,132.93.
   - AR 2023-24 App. 5(i) (p.235): the 22 zones add to the Total in all 8 columns. There is no central line and no note.
   - The +7,291.23 revision of 2023-24 total contribution sits entirely in EPF.
4. **Other fixes checked** (in `test_second_pass_metadata_fixes`).
   - **V4:** the T69 opening count is `stock`, dated 2019-03-31..2025-03-31, and equals the previous closing count from 2023.
   - **V5:** the T58 note on outflows is present.
   - **V6:** T64 A1 ends with "(₹ crore)", and the provenance cites the caption.
   - **V7:** no M4 label says "cumulative".
   - **V9:** the T24 and T2 notes carry 398.15 and 476.25.
   - **V10:** the investment notes say '-' is read as nil.
   - **V3:** M7 is fetched through `ctx.fetch`. The sidecar shows HTTP 200 on the first attempt, no redirects, and framework default headers only.
   - **V2** is a wording change only, and the new text is accurate.
5. **Access (D1-1/D1-2): still compliant.**
   - The only new fetch is the public M7 XLSX on www.pfrda.org.in. It uses no login, cookies or challenge solving.
   - NSDL and AMFI are not contacted, and there is no microdata.

### New findings (second pass)

| # | Severity | Finding | Evidence | Suggested fix |
|---|---|---|---|---|
| V11 | minor | **Subtracting 7,320.22 cr is not a complete clean-up of EPF "contributions" for S9, and the advice presents it as one.** The App. 5(i) note covers the whole table, zone rows included: "The above figures include the Contributions, Securities received on cancellation of exemption and Past accumulations". So the 22 zonal EPF figures (2,50,812.70) may also contain corpus transfers from exempted trusts, and they cannot be separated. AR 2023-24 prints no such note, so it is also unknown whether its 2,26,198.57 is free of such transfers. It may simply not say so. | AR 2024-25 p.236 note. AR 2024-25 p.137 describes the new "Online System for Surrender of Exemption and Transfer of Past Accumulations", which transfers "funds including government securities to credit member balances in the statutory fund". That explains why 2024-25 has a central line. It does not show that the zones contain none. | In issue -5 and the para 5.4/5.5/App. 5(i) notes, add that the note covers zonal figures as well. Say that 2,58,132.93 − 7,320.22 = 2,50,812.70 is an upper bound for new contributions, and that the transfer-in part of the zonal figures is not published. Phase 2 should carry this as an uncertainty on S9. |
| V12 | minor | **The AR 2024-25 EPS payment (27,963.41) includes two central lines that the provenance does not mention.** They are CPPS 6,813.22 (Centralised Pension Payment System) and "Adjustment of Pension Disbursement Savings A/c Balance" 381.88. The 22 zones sum to 20,768.29. CPPS is a real pension payment moved from the zones to the centre: zonal EPS payments fall from 23,410.17 in 2023-24 to 20,768.29, while the total rises 19%. The 381.88 is an account-balance adjustment, and whether it is a benefit payment is not stated. The total payment of 1,75,909.82 carries both lines. | p.236, pypdf text: lines "CPPS 6813.22 6813.22" and "Adjustment of Pension Disbursement Savings A/c Balance 381.88 381.88". Pinned in `test_epfo_ar2425_app5i_central_lines_in_eps_payment`. | Add both lines to the App. 5(i) 2024-25 provenance note, which currently says only that the central lines are "not read". Log for S9 benefits: EPS pensions 2024-25 include 381.88 cr of an adjustment that may not be a payment, and the year-on-year jump comes from the CPPS change of channel. |

### Framework request (acknowledged)

The builder's request to change `res_t69` is done in `tests/verify/test_finsector_markets_spotcheck.py`. The existing test was extended, not replaced: its docstring gains a "Second pass" paragraph, `pfrda_sg` is added to `DATASETS` and to the resolvers, and 5 tests are new.

---


## First pass

Verifier: separate agent, did not build the unit. Date: 2026-09-29. Scope: IRDAI Handbook 2024-25, EPFO Annual Reports 2023-24 and 2024-25, PFRDA NPS statistics (A2, A5, M2, M4, M6), and SEBI Handbook 2025-26 (T1, T7, T8, T11, T13, T14, T23, T58-T60, T62-T64, T69, T70, T72).
Regression test: `tests/verify/test_finsector_markets_spotcheck.py` (23 tests, about 20 s). It does not import the unit's code.

### Verdict

**The unit is accurate as a transcription of the published tables.** Every one of the 11,258 clean values matches its raw cell or PDF number. No value was mis-scaled, shifted, or matched to the wrong row or period. None of the findings below changes a number. Two of them concern how Phase 2 should use EPFO and NPS figures for S9, and the rest are metadata or documentation fixes.

### What was done

1. **Rebuild.** `fetch finsector_markets --offline` returned OK with 27 files. `build finsector_markets` produced 11,258 rows in 9 datasets. The unit tests passed (25 of 25), and `test -k finsector_markets` passed 92 of 92 before my file was added. `coverage finsector_markets` declares 8 refs, all partial, with none BROKEN. The `repro` result is below.
2. **Full census, not a sample: 11,258 of 11,258 values compared, 0 mismatches.** Each clean row is traced back to its source with the verifier's own locators:
   - **IRDAI:** openpyxl on the zip members.
     - Summary rows are found by (section header, label), and the unit caption in column C is applied (Lakhs × 1e5).
     - T24 and T25 are read by (block header `LIC`/`TOTAL`, year row, label) and divided by 100 (Rs lakh).
     - T40, T41, T44 and T51 are read by group-total label and segment block. T44's measure header is searched inside each block.
     - T20 and T46 are read by fund/category label.
   - **EPFO:** pdfplumber text. The unit used pypdf. Pages are found by anchor search in a window, and values by the verifier's own regexes.
     - The rotated Appendix-5(i) page of AR 2024-25 comes out mirrored in pdfplumber. It was read by reversing the tokens, which gives an independent route to those 8 values.
     - 36 literal numbers were also typed by hand from the PDF page text (`HAND_ANCHORS`).
   - **PFRDA:** openpyxl, with sector headers matched by the verifier's own map. The 73 derived M4 annual differences were recomputed from the raw file.
   - **SEBI:** openpyxl, with rows matched by FY label and columns by the verifier's own map, checked against header text. T58 is converted from Rs billion (× 100), and T69 from lakh counts (× 1e5).
   - **T72:** months read as month-ends. Two rows (Sep and Oct 2016) are typed as the 16th in the file and are handled correctly.

   | dataset | rows | compared | mismatches |
   |---|---|---|---|
   | irdai_summary | 1,140 | 1,140 | 0 |
   | irdai_life | 1,284 | 1,284 | 0 |
   | irdai_nonlife | 2,124 | 2,124 | 0 |
   | epfo_ar (PDF) | 361 | 361 (+36 hand anchors) | 0 |
   | pfrda_nps | 3,749 | 3,749 (73 derived recomputed) | 0 |
   | sebi_primary | 512 | 512 | 0 |
   | sebi_bonds_equity | 151 | 151 | 0 |
   | sebi_foreign | 868 | 868 | 0 |
   | sebi_mf | 1,069 | 1,069 | 0 |

   A seeded sample (seed 20260929, 2 rows per table, 76 rows) is printed by `test_seeded_sample_report` for eyeballing.
3. **Completeness (the other direction).** Every published number in each ingested block has a clean row. This holds for all SEBI tables, all PFRDA files, T72, IRDAI T2, T20, T40 and T41, T24, T25 and T51 (LIC/TOTAL and the four group blocks), and the Summary sheets apart from the declared skips (Swiss Re `#` rows, grievance rows, empty profit/loss-company rows). The heading rows of T24, T25 and T51 are zero, with one exception (item 8 below).
4. **Systematic-error hunt.** Each check below is in the test file.
   - **Scale.**
     - T24 (Rs lakh ÷ 100) premium equals T2 (Rs crore) for LIC and the industry, 2019-20, 2023-24 and 2024-25.
     - T51, which has no caption, gives a four-group PAT equal to Summary C PAT, so its unit is Rs crore.
     - The rupee rate implied by T58 (Rs billion × 100 against US$ mn) is 60-90 in every year checked.
     - Lakh counts are converted.
   - **Cross-table agreement for 2022-23 to 2024-25** (checked ad hoc, not in the test file). It holds to rounding:
     - T41 total with Summary C segment total;
     - T46 with Summary C AUM;
     - T20 grand total with Summary B AUM;
     - T24 benefits with Summary B benefits;
     - T44 claims with Summary A minus Summary B;
     - T59 net with T60 total.
   - **Periods.**
     - FY flows are dated FY.
     - End-March stocks are dated YYYY-03-31. The T11, T23, T62 and T63 captions say "end of FY", "end of period" and "as on 31st March".
     - The T23 NSE and MSEI blocks are row-aligned with column A: their own year cells E and I equal A.
     - T72's first-of-month labels are month-end positions: March totals equal T64 end-of-FY AUM within 0.2% for 2022-2026.
   - **Status.** Only the PFRDA M4 annual differences are `derived`, and they carry a method and inputs. Everything else is `official`.
   - **EPFO revisions.** Across the two vintages, 82 values overlap. The only difference is EPF contributions 2023-24, which is +7,291.23 cr in the later report.
5. **Access (D1-1/D1-2).**
   - All fetches go through `ctx.fetch`, and the unit imports no HTTP library.
   - No headers are added beyond the framework defaults. There are no cookies, tokens or logins.
   - All 27 sidecars show HTTP 200 on the first attempt, with no redirects.
   - Hosts: irdai.gov.in, pmvbry-cdn.epfindia.gov.in, www.pfrda.org.in, www.sebi.gov.in.
   - NSDL and AMFI are not in `SOURCES` and were not contacted. There is no GSTN/CBDT source and no microdata. **Compliant.**
   - I agree with the builder's framework request: `nsdl_fpi_monitor` and `amfi_monthly_quarterly` have `access.requires: none` in the registry, so the code policy would not stop another unit from fetching them.

### Findings

| # | Severity | Finding | Evidence | Suggested fix |
|---|---|---|---|---|
| V1 | major | **The EPF contribution for 2024-25 includes Rs 7,320.22 cr of "Past Accumulation" accounted at the central level**, and the 2023-24 revision (+7,291.23) is very probably the same kind of item. Past accumulations are existing balances transferred into EPFO, mainly from exempted PF trusts when their exemption is cancelled. They are not new contributions by households or employers. The issues file (finsector_markets-5) says "Phase 2 should use the later vintage". For S9 household contributions, that would count about 7.3k cr of transfers inside the funded-pension sector as contributions. The provenance of the AR 2024-25 rows does not mention the footnote. | AR 2024-25 p.78 para 5.4, footnote on EPF 2,58,132.93\*\*: "The figure includes the amount of Past Accumulation of Rs. 7,320.22 Crore which is accounted for at the Central level". The p.236 App. 5(i) has a separate "Past Accumulation 7,320.22" line above Total, and its note says figures "include the Contributions, Securities received on cancellation of exemption and Past accumulations". AR 2023-24 zone totals (App. 5(i) p.235) give 2,26,198.57. | Add the footnote to the notes of the AR 2024-25 para 5.4 / 5.5 / App. 5(i) provenance records. In issue -5, change the advice: for S9, use AR 2023-24's 2,26,198.57 (or the later figure minus central past accumulations) and treat past accumulations as a transfer from exempted trusts. |
| V2 | minor | **The EPFO exempted-establishment table genuinely does not add up as printed.** It is not a text-layer loss. | Rendered pages 97-98 (PDF pp.98-99) show only three category rows: 1,397.11 + 2,46,513.82 + 1,47,102.54 = 3,95,013.47, against a TOTAL GROSS of 4,56,848.78. | Reword finsector_markets-6: the gap is in the publication. |
| V3 | minor | **An independent check on the "M4 is cumulative" reading exists and was not used.** The NPS Handbook (pinned, p.15) defines Table M7, "State-wise Subscribers and Contribution under SG Sector", as contributions "received for the given month ... in crores", which is a flow. The handbook's M4 definition (p.14) does not say "cumulative", so the derived `m4d.*` rows rest on inference. | HoNPSS 2024-25 pp.14-15, data definitions for M4 and M7. | Fetch PFRDA M7. Check that the SG annual sum of M7 for 2023-24 matches `m4d.annual_contribution.state_govt` (77,599.20). If it does, the reading is confirmed. If it does not, drop the m4d rows. |
| V4 | minor | **T69 "Existing SIPs at the beginning of the period" is labelled `stock_flow=flow` with an FY period.** It is an opening stock. From 2023-24 it equals the previous year's closing count. | `t69.sips_existing_beginning` 2023-24 = 62,934,396 = `t69.sips_closing` 2023-03-31. | Make it `stock`, dated the previous 31 March (or drop it as a duplicate of the closing stock). |
| V5 | minor | **The T58 sign convention is not recorded.** "FDI by India" and "Repatriation/Disinvestment" are printed positive but are outflows (note 3: "Negative (-) sign indicates outflow (except in case of FDI by India)"). | The 2023-24 identities 71,302 - 44,472 = 26,830 and 26,830 - 16,678 = 10,152 (US$ mn) hold only with those columns read as outflows. | Add the convention to the T58 provenance notes. |
| V6 | minor | **The T64 provenance note says "the table carries no caption".** The A1 title ends "(₹ crore)". | `hbs2526_t64_a.xlsx` A1: "Table 64: Category-wise Resource Mobilisation by Mutual Funds (₹ crore)". | Correct the note. The unit is unaffected. |
| V7 | minor | **The M4 `item_label` adds an inference.** "Contribution as on month-end (cumulative)": the published header says only "Sector-wise NPS Contribution", and the guide wants the label as published. | `m4.cumulative_contribution.*` rows. | Keep the inference in provenance and item_code, and drop "(cumulative)" from item_label. |
| V8 | minor | **A stray value on a T25 heading row is not ingested.** The TOTAL block, 2018-19, prints 41.75 lakh (0.42 cr) on "Provisions (Other than taxation)". | Part I.xlsx sheet 25, row 16. | Negligible. Log it as INFO. |
| V9 | minor | **The LIC premium includes out-of-India business**, which is not logged. | T24 note 3: "In respect of LIC, the premium figure include ₹398.15 crore (PY ₹476.25 crore) from out of India business" (T2 LIC premium carries the same caveat). | Log it for S9/R17 (a RoW share of life premium). |
| V10 | minor | **EPFO category cells printed "-" (Public Account, EPF) are emitted as 0.0.** The percentage column shows 0.00%, so "-" means nil here. That is acceptable, but it departs from the guide's rule of "no row for missing". | AR 2023-24 p.92 and AR 2024-25 p.86, EPF item 5. | Keep it, and say so in provenance. |

The builder had already found and logged the following. I confirmed each:
- the EPFO 2023-24 revision;
- the table non-additions: IRDAI T40 vs Summary C (10.26), T44 2019-20 (743.21), SEBI T64 2017-18, T70, and T72 before Dec-2019;
- the T11 FC/NFC reclassification at end-March 2025;
- the T23 Sensex 2024-25 anomaly (not ingested);
- the T63 unit inference (T63 Category I+II+III for 2023-24 is 6,953,987, equal to T62 FPI AUC 6,953,987.69);
- the PFRDA Feb-2026 break;
- the 'NA' and '-' blanks in T13, T60 and T63;
- the `2020-21**` footnote marker in T44 (a corrected typo);
- the Sep/Oct 2016 dates in T72, which are typed as the 16th.

### Coverage claims

All 8 refs are declared `partial`, which is honest.
- **S9 (OFFICIAL):** EPFO un-exempted contributions and payments, NPS (derived) and life premiums/benefits are present. Exempted trusts, CMPF, GPF, PPF and NPS withdrawals are missing. See V1 on EPFO past accumulations.
- **K8b (OFFICIAL):** FPI by instrument (T60), BoP FDI/portfolio (T58) and AUC (T63) are present. The G-sec vs corporate split of FPI debt is missing (NSDL terms).
- **Estimated refs (R17, R9c, F4a, K2a, T4a, R8):** each lists the inputs it provides, and none claims `full`.

### Reproducibility

`repro finsector_markets` (run by the verifier at about 16:30 IST):
- All three builds were byte-identical: hash seeds 0 and 1, and 1 and 4 threads.
- All 11 files match `data/manifest.json`.
- The command still printed `REPRO FAILED` because `code_hash changed between builds`. `code_hash` covers all of `pipeline/`, and other units' modules (external_sector, hces_consumption, io_tables, rbi_financial_accounts, among others) were being edited at the time.
- The unit's own files (`pipeline/ingest/finsector_markets/*.py`, last modified 16:01-16:15 IST) are older than the verifier's first build and did not change during verification.
- Conclusion: the outputs are reproducible. Re-run `repro` once the parallel agents are idle to get a clean `REPRO OK`.


---


## Close-out pass (builder's EPFO/EPS provenance follow-up, 2026-09-29, late)

Verifier: separate agent, did not build the unit. Scope:
- the rewritten EPFO provenance notes (AR 2024-25 para 5.4, para 5.5 and App. 5(i); AR 2023-24 App. 5(i));
- issues -5 and -37;
- the new build check `_check_app5i_lines` in `epfo.py`;
- the NSDL/AMFI terms block and its new unit test.

The builder reports that no values or rows changed. That is confirmed.

### Verdict

**Almost all of the follow-up checks out against the raw PDFs.** One piece of new S9 advice is wrong: the new notes call the whole EPS payment "EPS pensions" (V13 below).

What checks out:
- **Four central lines on p.236.** There are exactly four lines above 'Total' that are not zone rows, and each sits in the columns the notes state. I placed every line by its print position, independently of the builder's placement.
- **The 0.19 line.** "Adjustments of remittances at Head Office level 0.19" is printed in the EPS-contribution column. The second-pass verifier did miss it. Total contribution also needs the 0.19: without it the residual is 0.23, with it 0.04.
- **Numbers and quotes.** Every number the new notes state re-derives from the raw PDFs. Every quoted passage is verbatim on the cited PDF page.
- **Build check.** It is strict: a changed Total, a missing central line or an altered central value fails the build.
- **AR 2023-24.** App. 5(i) has no central line, and its zones equal Total in all 8 columns.

What is wrong or missing:
- **V13 (major, notes only):** the notes miss the report's own EPS outgo table, which splits the payment into pensions and withdrawal benefits.
- **V14 (minor):** the "Total" contribution labels hide that the Central Government's EPS share is excluded.
- **Rounding slip:** the stated "19.5%" rise is 19.4%.

No number in the data is affected.

### What was done

1. **Rebuild and tests.**
   - `fetch --offline`: OK, 28 files. `build`: 10 datasets, 11,847 rows; `epfo_ar` still has 361.
   - `repro finsector_markets`: **REPRO OK** (12 files byte-identical, matching the manifest).
   - `coverage`: 8 refs, all partial, none broken.
   - `test -k finsector_markets`: 140 passed, 2 xfailed (both are the strict xfails for the new findings).
   - Unit tests (31) plus the spot-check (37, and 2 strict xfails): 68 passed, 2 xfailed.
   - One CRLF regression was introduced by the verifier's own edit (Windows `write_text`) and fixed at once. The hygiene test is green.
2. **Full census re-run.** 11,847 of 11,847 values match the raw files, 0 mismatches. No expectation in the existing spot-check needed changing: all counts are current, and no strict-xfail has been fixed.
3. **A third, independent route to App. 5(i).** The new `app5i_positional` reads pdfplumber **word coordinates**. The unit reads pypdf text, and the earlier census reads pdfplumber text lines.
   - The rotated p.236 returns mirrored tokens: the row axis is x0 and the column axis is top. Columns are anchored on the Total row's own eight positions, so a line with one or two values is placed where it is printed.
   - Results, for both reports:
     - 22 zones × 8 columns equal the pypdf read cell by cell (176 cells each).
     - Totals equal the clean rows.
     - The 2024-25 central lines are Past Accumulation 7,320.22 (EPF contribution, total contribution), CPPS 6,813.22 (EPS payment, total payment), the Pension Disbursement Savings A/c adjustment 381.88 (EPS payment, total payment) and head-office remittances 0.19 (EPS contribution only).
     - Total = zones + central lines in all 8 columns, with a total column taking the central values of its scheme columns.
4. **Every number in the new notes, re-derived:**
   - zone sums: EPS payment 20,768.29; total payment 1,68,714.70; EPS contribution 73,788.18; total contribution 3,28,308.36; EPF contribution 2,50,812.70;
   - 27,581.53 = 27,963.41 − 381.88;
   - 23,410.17 (AR 2023-24 Total, which equals its zones);
   - the residuals +0.02, +0.03 and +0.04;
   - para 5.5 2024-25 = App. 5(i) Total in all 8 columns.
   - **Exception:** "the total rises 19.5%" is 27,963.41 / 23,410.17 − 1 = **19.4498%, i.e. 19.4%**.
5. **Quotes.** Nine passages were checked verbatim in the pdfplumber text of the cited PDF pages:
   - p.45: CPPS "Since Jan 2025";
   - p.136: "fully implemented in December 2024 ... over 69 lakh pensioners";
   - p.137: 30 Nov 2024, 24 ROs, 9,30,448 pensioners, 213.55 crore;
   - p.137: "Online System for Surrender of Exemption and Transfer of Past Accumulations" and "transfer of funds including government securities ...";
   - p.68 and AR 2023-24 p.72: the corpus-transfer rule;
   - p.70: the online surrender module of 13.08.2024.

   A full-text search of both PDFs (pypdf, forward and mirrored) finds "Pension Disbursement Savings" only on p.236, so "not explained anywhere in the report" is literally true (but see V13). The p.108 hit for CPPS is a social-media topic list and is irrelevant. The exempted-establishment chapters (AR 2024-25 pp.62-73, AR 2023-24 pp.66-77) state no crore amount for transfers on surrender, so "the zonal share of transfers is not published" holds.
6. **Changed rows.** All 61 rows whose provenance was rewritten (100%, above the 10%/30 minimum) were re-resolved: AR 2024-25 para 5.4 (5), para 5.5 (40) and App. 5(i) (8), and AR 2023-24 App. 5(i) (8). App. 5(i) goes through the positional parser; the rest go through the verifier's pdfplumber regexes. A seeded sample of 30 (seed 20260929) is printed by `test_closeout_changed_rows_seeded_census`. 0 mismatches.
7. **Build check (`_check_app5i_lines`).** Read and exercised. The zone regex requires 8 amounts. Each central line must match exactly once, and every column must satisfy Total = zones + central lines within 0.05. AR 2023-24 fails the build if 'Past Accumulation', 'CPPS', 'Adjustment' or 'cancellation of exemption' appears on its page. The unit test perturbs a Total and a central value and gets the expected `ValueError`. A new central line would break the Total identity and so also fails.
8. **NSDL/AMFI (D1-1b).** `policy.py` refuses both ids, plus the hosts `fpi.nsdl.co.in` and `amfiindia.com` with subdomains, which covers `portal.amfiindia.com`.
   - The verifier checked this against the registry file itself: every landing and data URL of both sources is refused by `url_refusal` and `denied_host`.
   - No finsector_markets pin or sidecar URL is on either host.
   - The builder's reason for not using `data/registry_additions` matches PIPELINE_GUIDE §8: an addition may not redeclare an id already in `registry.yaml`, and doing so breaks the owning unit. The `access.requires` edit correctly stays an orchestrator follow-up.

### New findings (close-out)

| # | Severity | Finding | Evidence | Suggested fix |
|---|---|---|---|---|
| V13 | major (notes only; no value wrong) | **The new notes call the whole EPS payment "EPS pensions" and miss the report's own split.** The note and issue -37 say "EPS pensions paid in 2024-25 lie between 27,581.53 and 27,963.41". The report's own EPS outgo table (para 2.16, Table 5, PDF pp.40-41) splits 2024-25 into **Pension Disbursed 18,957.86** and **Withdrawal Benefits 9,005.90**, total 27,963.76. The note under that table reconciles it to the Balance-Sheet **27,963.41**, differing only by a 0.35 Life Assurance Benefit entry. So about 9,006 cr of the "pensions" are lump-sum withdrawal benefits. EPFO's own outgo split ties to the printed 27,963.41, which includes the 381.88; that bears on the 381.88 question even though no text explains the line. Also unlogged: in every earlier year the App. 5(i)/para 5.5 EPS payment **exceeds** the Table 5 outgo total, by 38.03 (2020-21), 382.46 (2021-22), 315.97 (2022-23) and 371.23 (2023-24; AR 2023-24 p.39 prints the same Table 5 values). Only 2024-25 ties, to within 0.35. Minor slip in the same note: "rises 19.5%" is 19.4% (19.4498). | AR 2024-25 PDF pp.40-41 "Table 5: Employee's Pension Fund outgo distribution" and its note; AR 2023-24 PDF p.39 "EPS Payments". Pinned in `test_v13_raw_eps_outgo_table_splits_pensions_from_withdrawal_benefits`. The fix is pinned in the strict xfail `test_v13_notes_cite_eps_outgo_split`. | In the App. 5(i)/para 5.5 notes and issue -37, say "EPS payments (pensions and withdrawal benefits)", not "EPS pensions". Cite Table 5: for 2024-25, pensions 18,957.86 and withdrawal benefits 9,005.90, which together tie to the printed total; the 381.88 is therefore inside EPFO's own outgo split, so state its range for the total payment rather than for pensions. Log the 38-382 cr excess of App. 5(i) over Table 5 in 2020-21..2023-24 as a Phase 2 uncertainty on S9 EPS benefits. Correct 19.5% to 19.4%. Consider ingesting Table 5 (six FYs in two vintages), because S9 needs pensions and lump sums separately more than it needs zones. |
| V14 | minor | **The App. 5(i) "Total EPS contribution" and "Total contribution" exclude the Central Government's EPS share.** In both reports, App. 5(i) EPS contribution equals para 5.4's **employers'** share (62,423.93; 73,788.40). Total contribution = EPF + EPS employers' share + EDLI. The Government's share (9,356.48 in 2023-24; 10,049.70 in 2024-25) is in neither, but the item labels say "Total". The new AR 2024-25 note mentions "(employers' share)" in passing; the AR 2023-24 note does not. S9 coverage already lists `para54.eps_contribution_government` separately, so nothing is lost; a user could still add the two and double count, or take "Total contribution" as complete. The employers' share 73,788.40 also contains the 0.19 head-office adjustment (negligible). | `test_v14_raw_app5i_eps_contribution_is_employers_share_only` (raw fact); strict xfail `test_v14_notes_say_government_share_excluded`. | Add a sentence to both App. 5(i) notes (and to the para 5.5 note, whose column is already labelled employers' share): "EPS and total contribution exclude the Central Government's EPS share (para 5.4 b), 9,356.48 / 10,049.70." |

### Spot-check changes (`tests/verify/test_finsector_markets_spotcheck.py`)

The existing tests are unchanged, because none was stale: counts, pins and all 29 earlier tests still pass. Added:
- **Parser:** `app5i_positional`, the third independent route to App. 5(i).
- **Seven passing tests:** zone-by-zone agreement with pypdf; central lines by print position; the notes' numbers re-derived; verbatim quotes; the census of the 61 changed rows with a seeded sample; the NSDL/AMFI host and pin check; and V13/V14 raw facts (2).
- **Two strict xfails** for the V13 and V14 provenance fixes.

The docstring gains a "Close-out pass" paragraph.


---


## Final pass (V13/V14 fixes and the new EPS outgo dataset, 2026-09-29)

Verifier: separate agent, did not build the unit. Scope:
- the builder's fixes for V13 and V14 (provenance notes of AR 2024-25 App. 5(i) and para 5.5, and AR 2023-24 App. 5(i));
- the new dataset `finsector_markets_epfo_eps_outgo` (30 rows);
- the two strict xfails that were XPASSing.

### Verdict

- **V13 is fixed.** Every statement in the new notes was re-checked against the pinned PDFs:
  - The notes now call the App. 5(i)/para 5.5 EPS payment "pensions AND withdrawal benefits". The phrase "EPS pensions" no longer appears in any `epfo_ar` note.
  - They cite Table 5 (PDF pp.40-41): Pension Disbursed 18,957.86, Withdrawal Benefits 9,005.90, total 27,963.76. They also cite its 0.35 Life Assurance Benefit reconciliation to 27,963.41.
  - They give 27,581.53 as the alternative figure for total EPS payments, not for pensions.
  - They log the earlier-year excess (38-382 cr; 371.23 in 2023-24) and say 19.4%.
  - The AR 2023-24 App. 5(i) note gives its own gap: 23,410.17 − 23,038.94 = 371.23.
- **V14 is fixed.** Both App. 5(i) notes and the AR 2024-25 para 5.5 note say that 'Total EPS contribution' is the employers' share only (62,423.93; 73,788.40) and that 'Total contribution' excludes the Central Government's share (9,356.48; 10,049.70), "despite the word 'Total'". The raw facts hold:
  - para 5.4 employers' + Government's share = the printed 'Total:' (71,780.41; 83,838.10);
  - App. 5(i) EPS contribution = the employers' share;
  - App. 5(i) total contribution = EPF + employers' share + EDLI, within 0.015 (2,58,132.93 + 73,788.40 + 3,707.48 = 3,35,628.81).
- **The new dataset is accurate. The census now covers all 11 datasets: 11,877 of 11,877 values compared, 0 mismatches** (`epfo_eps_outgo` 30 of 30).
- **The strict xfails are now ordinary passing checks.** The spot-check has 0 failures and 0 xfails.
- **No new findings.** There are two cosmetic observations below. Neither needs a change.

### What was done

1. **Tests.**
   - `test tests/verify/test_finsector_markets_spotcheck.py`: 42 passed. That is 37 earlier tests, the 2 converted xfails, the new census parameter `epfo_eps_outgo` and 2 new tests.
   - `test -k finsector_markets`: 153 passed, 0 failed. Before this pass it was 148 passed and 2 failed (the XPASSing strict xfails).
   - `test tests/hygiene`: 26 passed, and the edited files use LF line endings.
   - `fetch finsector_markets --offline`: ok. `manifest --check`: up to date.
   - I did not rebuild. The verified parquet files are the ones `data/manifest.json` records.
2. **The EPS outgo table, independently re-derived.** A fourth route to the EPFO PDFs, `eps_outgo_positional`, uses pdfplumber word coordinates. The unit reads pypdf text, and the close-out `eps_table5` reads pdfplumber text lines. The method:
   - Pages are found by searching PDF pp.25-60 for a line that carries Pension, Disbursed, Withdrawal, Benefits and Total. The search finds exactly p.39 (AR 2023-24) and pp.40-41 (AR 2024-25; the header is repeated on p.41). These are the pages the provenance locators name.
   - Columns are anchored on the right edges of 'Disbursed', 'Benefits' and 'Total', because the amounts are right-aligned.
   - A row is a FY label ('2019-20' or '2020-2021') followed by exactly three amounts, each within 30 pt of its anchor.
   - On p.41, the spaced chart label "2 0 2 4 - 2 0 2 5" and the note are correctly not read as rows.
   
   Results:
   - **Census:** 30 of 30 values match, including series id, FY period, flow, INR crore and `official` status.
   - **Completeness in both directions:** 5 FYs × 3 columns per vintage. Every published cell has exactly one clean row, and every clean row has exactly one published cell.
   - **Identities:** Pension Disbursed + Withdrawal Benefits = Total within 0.015 in all 10 FY-rows. The two vintages are identical for 2020-21..2023-24. The positional read equals the text-line read and the hand-typed `EPS_TABLE5` values.
   - **Seeded sample (seed 20260929)**, printed for eyeballing: Para 2.15 withdrawal benefits 2022-23 = 7,352.25 and 2021-22 = 7,989.01; Table 5 total 2024-25 = 27,963.76 and withdrawal benefits 2022-23 = 7,352.25. Clean equals raw in all four.
3. **Numbers in the new notes, re-derived from the raw pages rather than copied:**
   - The excess of the para 5.5 EPS payment over the Table 5 total: 38.03 (2020-21), 382.46 (2021-22), 315.97 (2022-23), 371.23 (2023-24) and −0.35 (2024-25).
   - The EPS payment 2024-25 of 27,963.41 and 27,963.41 − 381.88 = 27,581.53, both from the positional App. 5(i) read.
   - Pension Disbursed rises by 18,957.86 / 15,130.68 − 1 = 25.3%.
   - The rise in the total EPS payment is 19.4%.
4. **Quotes checked verbatim** (pdfplumber, whitespace collapsed):
   - AR 2024-25 p.41: the Table 5 note ("The total outgo Rs. 27,963.76 Cr shown above ... entry in Balance Sheet.");
   - p.36: the withdrawal-benefit definition;
   - p.46: GSR 326 (E) of 14.06.2024, "Now withdrawal benefits are available even for 1 month contribution";
   - p.40: the Table 5 caption;
   - AR 2023-24 p.39: the para 2.15 heading and the "EPS Payments ( Rs. in crores )" caption.
5. **Spot-check changes** (`tests/verify/test_finsector_markets_spotcheck.py`):
   - The xfail marks were removed from `test_v13_notes_cite_eps_outgo_split` and `test_v14_notes_say_government_share_excluded`. Both were strengthened: they now re-derive every number the fixed notes state from the raw pages, and they pin that neither "EPS pensions" nor "19.5%" comes back.
   - `epfo_eps_outgo` was added to `DATASETS` and `RESOLVER` (`res_eps_outgo`), so the census, the seeded sample and the status test cover it.
   - Two tests are new: `test_final_eps_outgo_pages_completeness_and_identities` and `test_final_eps_outgo_note_numbers_and_quotes_rederived`.
   - The docstring gains a "Final pass" paragraph.

### Observations (no action needed)

- **Withdrawal-benefit quote.** The `epfo_eps_outgo` notes quote the definition in AR 2024-25's wording (p.36) and cite AR 2023-24 p.37 alongside it. AR 2023-24 prints it without the comma and without "the" ("... on superannuation provided member has not rendered service eligible for pension"). The meaning is the same. The test pins both wordings.
- **'Unaudited' flag.** Only the report year of each vintage (2023-24 in AR 2023-24, 2024-25 in AR 2024-25) is flagged `Unaudited`. The outgo table itself prints no audit mark. The flag follows the report-wide statements (para 5.4 "* Unaudited" and "*The provided figures are un-audited") and the Table 5 note ("as per details in Balance Sheet for FY 2024-25"). This matches how the rest of `epfo_ar` is flagged.

### For the orchestrator

Two lines in `docs/phase1/COVERAGE.md` are now stale; I did not edit that file:
- The finsector_markets row can read 11,877 values checked of 11,877 (100%), with the regression test passing.
- Open verifier item 1 is done: the xfail marks are removed and `epfo_eps_outgo` is in the census.

The builder's issues-file rows for V13 and V14 still say the xfails XPASS. That file is the builder's.
