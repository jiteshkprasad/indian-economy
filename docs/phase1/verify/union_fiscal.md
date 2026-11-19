# union_fiscal: independent verification (first pass, 2026-09-29)

Verifier: an adversarial agent that did not build the unit (SPEC rule 3). The regression test `tests/verify/test_union_fiscal_spotcheck.py` re-parses the pinned raw files with its own code. It does not import `pipeline.ingest.union_fiscal` or `pipeline.core`.

## Verdict

**Accepted, with minor fixes. Every one of the 6,510 clean values matches its raw cell (0 mismatches in a full census of all 8 datasets).**

- Scale, signs, periods, vintages and price basis are right:
  - Finance Accounts Rs thousand × 1e-4 = crore, proven against the AFS (a different document).
  - The IGST apportionment heads, the minor head 901 devolution, and the Deduct and Less lines are all negative as printed.
- The Budget files carry the correct Actuals year in every vintage. The stale Interim `tr.xls` is not used.
- The gap-map anchors hold: CGST 8,20,622.09; IGST -4,850.43; compensation cess 1,41,436.16; GST 9,57,207.82; RBI surplus 87,416.2162; food subsidy 2,11,814.39.
- D1-1 and D1-2 are respected.
- No major defect was found. The findings are:
  - one aggregation trap: Statement 21 headings double count;
  - two series-identity breaks across Budget vintages;
  - one dropped nil row;
  - a few metadata and coverage-note refinements.

## What was run

| Step | Result |
|---|---|
| `fetch union_fiscal --offline` | OK, 30 pinned raw files; all sha256 re-checked by the test |
| `build union_fiscal` (offline from pins) | OK: 8 datasets, 6,510 rows (row counts as reported by the builder) |
| `test -k union_fiscal` | 126 passed, 3 xfailed. The 3 xfails are the verifier's strict defect markers. |
| `test tests/verify/test_union_fiscal_spotcheck.py -s` | 26 passed, 3 xfailed (strict) |
| `coverage union_fiscal` | no BROKEN; OFFICIAL covered=4, partial=12 (of 16) |
| `repro union_fiscal` | 3 builds byte-identical and equal to `data/manifest.json` (10 files). See the repro line at the end. |

## Method (`tests/verify/test_union_fiscal_spotcheck.py`)

- **Independent parsers.**
  - Finance Accounts St 8 / St 9, Budget 2025-26 `tr.pdf` / `ntr.pdf` and both Annex 8 PDFs: pypdf page text. The unit uses pdfplumber word x-positions.
  - Every xlsx and the PPAC `.xls`: python-calamine. The unit uses openpyxl / xlrd.
  - NSI: lxml.html. The unit uses BeautifulSoup.
  - Clean data: pyarrow.
  - The verifier wrote its own number reader. It also has its own reader for the Finance Accounts amount format: 2-digit groups from the right, so '8,74,16,21,62' = 87,416.2162 crore. The em-dash minus comes out as U+FFFD in pypdf, and the reader handles that too.
- **Matching is by code or label, never by position.**
  - Finance Accounts: English head-of-account code, under the right major and sub-major head.
  - Receipt Budget: printed label plus major head. For the PDF, the label is matched character by character across line wraps.
  - AFS: major head, or the English label.
  - Expenditure Profile: heading, label and component. After tightening, no row has more than one candidate value.
  - Annex 8: section and label.
  - PPAC: block, part and label.
  - NSI: year and column.
  - Every file's Actuals / year header is asserted: 2022-23 for b2425, 2023-24 for b2526, 2024-25 for b2627.
- **Finance Accounts, three layers:**
  1. Census: every one of the 3,009 values, converted back to Rs thousand, is printed with the same sign on the PDF page its provenance names.
  2. Line level: 2,296 of 2,364 minor heads were read from their own line, with the correct major and sub-major context. In St 9 the value read is column 3 (Total), not the charged amount printed on the line above. There were 0 mismatches. 68 heads (2.9%) stay unresolved by the verifier's simple parser, because of glyph-split codes such as '80 0' or '79 7' and 'lncome'. Those heads are covered by layer 1 and by eye.
  3. Totals: 537 sub-major and major totals were read from their TOTAL lines, with 0 mismatches and 5 unresolved.
- **Reverse census.**
  - Every minor-head code printed in St 8 and St 9 has a clean row on its page. The exceptions are two heads printed with no amount in any column, and the one nil head in verify-3.
  - For PPAC and NSI, the number of published cells equals the number of clean rows.
- **Hand-typed from page text: 61 values.**
  - Finance Accounts, 39 values: pages 1, 4, 5, 7 and 21 of St 8 and pages 8, 20, 52, 94 and 95 of St 9. They include the RBI surplus, the MH 0050 payers, CGST and its 901, the IGST apportionment, the St 9 grand total and capital major heads, and a glued voted/total pair.
  - Budget 2025-26 `tr.pdf` / `ntr.pdf`, 12 values.
  - Annex 8, 10 values.

| Dataset | Values | Compared | Mismatched | How |
|---|---:|---:|---:|---|
| fa_receipts | 1,063 | 1,063 (+825 line level, 191 totals, 25 hand-typed) | 0 | pypdf |
| fa_expenditure | 1,946 | 1,946 (+1,471 line level, 346 totals, 14 hand-typed) | 0 | pypdf |
| rb_receipts | 772 | 772 (+12 hand-typed) | 0 | pypdf for 2023-24, calamine for the others |
| afs | 990 | 990 | 0 | calamine |
| exp_profile | 1,294 | 1,294 | 0 | calamine |
| nssf | 65 | 65 (+10 hand-typed) | 0 | pypdf |
| ppac_exchequer | 311 | 311 | 0 | calamine (.xls) |
| nsi_collections | 69 | 69 | 0 | lxml |
| **Total** | **6,510** | **6,510 distinct values; 9,404 comparisons** | **0** | |

## Systematic-error hunt

| Check | Finding |
|---|---|
| **Scale** | Finance Accounts are Rs thousand, converted × 1e-4. Every value is a whole number of thousands. Gross CGST, corporation tax, income tax and customs (total minus minor head 901) each equal the AFS by major head to 0.01. The IGST residual and the cess also equal the AFS. St 9 revenue and AFS total revenue disbursements are both 38,54,082.21. The Budget, PPAC and NSI are published in crore and stored as published. |
| **Closures (independent)** | The major-head totals add up to the printed totals: St 8 revenue 30,88,174.64 and capital 45,280.68; St 9 revenue 38,54,082.21 and capital 8,07,180.34. |
| **Signs** | Stored as published. IGST apportionment out of MH 0008 (950-957) is negative. The advance apportionments 959-961 are positive, as printed. Minor head 901 is negative everywhere. The FBT refund (-4.84) and NCCD transfers (-962.07 and -7,812.25) are negative. `Deduct—Refunds 4,50` in MH 0047 is printed without a minus and kept that way. |
| **Periods / vintages** | The Finance Accounts cover only 2023-24 (Audited). Each Budget vintage contributes only its own Actuals year, and the headers are asserted. There is no mixing of BE or RE into actuals. PPAC 2025-26 is tagged Provisional. NSSF stocks are dated, not fiscal-year: see verify-5. |
| **Voted / charged (St 9)** | Column 3 (Total) is taken throughout. The charged amounts printed in italics on the line above are never taken. For example, 2071-02-101 Army is 1,21,210.79, not the voted 1,21,210.48. |
| **Duplicates / aggregates** | St 8 and St 9 have one row per head. Receipt Budget aggregate parents are dropped in favour of the printed 'Total-' lines, with no loss. Statement 7, 18 and 20 heading rows each add up to their Grand Total. **Statement 21 heading rows add up to twice its Grand Total** (verify-1). |
| **Series identity across vintages** | Statement 18 relabels are already logged (union_fiscal-11). Not logged: the receipt-budget section totals and two glued PDF labels (verify-2). |
| **Provenance** | The Finance Accounts locators name the right PDF page for all 3,009 values; the census depends on this. The Budget records point at the file of the matching vintage and table (tested). All rows are `official`; there are no derived numbers. |
| **Coverage claims** | T1 (full): the values equal the gap-map figures. T4 and R6 (full): MH 0020 and MH 0050-106 are exact. T3 (full) is acceptable as an official total; see the note in verify-6. The notes for R3a, R9c, T2b, S7, R7 and K3a cite the heads they claim (checked label by label). K6: see verify-6. |
| **Access (D1-1 / D1-2)** | All 30 sidecars show status 200 on the first attempt, with no cookie or authorization headers. The only redirect is NSI's ASP.NET cookieless-session URL, which is not a login. Only `ctx.fetch` is used, with no custom headers. SOURCES has no GSTN, CBDT or microdata. The PPAC landing page is never fetched. The XLS comes from the registry's own `urls.data` entry (`access.requires: none`) with no login, so no challenge or login is bypassed. I agree with the builder's reading; the orchestrator should confirm FR-uf-1. No PIB request was made. |

## Findings

| # | Severity | Finding | Suggested fix |
|---|---|---|---|
| verify-1 | minor | **Statement 21 heading rows double count.** The statement prints ministry headings ('Ministry of Home Affairs' 10.51) and department headings under them ('28. Ministry of Home Affairs' 3.94, '29. Cabinet' 6.57). Both carry `level=heading`, and a repeated name becomes a `.nx` series. The heading rows sum to exactly 2 × Grand Total in 2022-23 and 2023-24 (5,288.72 = 2 × 2,644.36); in 2024-25 the ratio is 2.002. Values are correct, and R15 uses `stat21.grand_total`, which is unaffected. A user summing headings gets double. | Tag the two levels (`level=ministry` / `level=department`) and key the department series by its name, not `.nx`. Log it. Strict xfail: `test_stat21_heading_rows_do_not_double_count`. |
| verify-2 | minor | **More series splits across Budget vintages (not in union_fiscal-11).** (a) The non-tax section totals print 'Total-X' in the 2024-25 and 2026-27 xlsx but 'Net-X' in the Budget 2025-26 PDF. The concept is the same: BE 2025-26 Transport is 37,673.25 in both. So Transport, Energy, Social Services, and Agriculture & Allied each become two series (`rb.ntr.total.total_*` for 2022-23 and 2024-25; `rb.ntr.total.net_*` for 2023-24). (b) PDF word-gluing yields labels 'OtherRural Development Programme' and 'Oil andOil Seeds', which become separate series from the xlsx 'Other Rural…' and 'Oil and Oil Seeds'. Also cosmetic: 'Less -Receipts' for the printed 'Less - Receipts'. | Key section totals by section name, stripping the 'Total-'/'Net-' prefix. Repair glued words, or add them to `LABEL_ALIASES`. Add a test that the key totals exist in all three vintages. Strict xfail: `test_rb_section_totals_one_series_across_vintages`. |
| verify-3 | minor | **St 8 MH 0032 (Taxes on Wealth) minor head 901 is printed '–—' (nil) and has no clean row.** `_DASHES` does not contain '–—', so the line is read as a label without an amount. Other nil heads ('—') are kept as 0.0, and union_fiscal-5 says '–—' is handled. The value is nil, so no total is affected. | Add '–—' to `_DASHES`. Strict xfail: `test_fa_nil_901_under_mh0032_kept`. |
| verify-4 | minor | **The Finance Accounts vintage is the C&AG certificate date (2024-12-10), not a publication date.** The three PDFs' Last-Modified dates are 16-18 Dec 2024. The guide defines vintage as the publication date of the release. | Use 2024-12 (or the Last-Modified date) and say so in the provenance, or state in the issues file that the certificate date is used as a proxy. |
| verify-5 | minor | **The same NSSF stock carries two dates.** Opening stocks are dated `YYYY-04-01`, and closing totals `YYYY+1-03-31`. The 2023-24 closing total deposits (2024-03-31, 31,47,690.85) equals the sum of the 2024-25 openings, which are dated 2024-04-01 (tested). A stock series then has a spurious one-day gap between vintages. | Date opening stocks at the previous 31 March (e.g. 2023-03-31), which is the RBI / guide convention for end-March stocks. |
| verify-6 | minor | **Coverage-note precision.** (a) K6 cites `stat18.transfers_to_states_other_than_i_ii.capital_transfers`, which is 0.63 crore in 2023-24. That is not the substantive Centre-to-State capital flow; SASCI is 1,09,554, but it is a loan. The series id also exists only in the 2023-24 vintage, because the label reads 'Transfers' there and 'Transfer' elsewhere; the same holds for R2 and R2k. (b) T3 is declared `full` from MH 0021 (net of 901) and MH 0034. The gap map's 'etc.' also takes in MH 0023, 0024, 0026, 0028, 0031 and 0032. They are in the dataset (a few crore) but not listed. | Reword K6 ('capital transfers as printed; SASCI is a loan (K-account), see R2k'). Note in R2, R2k and K6 that the cited ids are the 2023-24 vintage's. Optionally list the minor direct-tax heads under T3. |
| verify-7 | info | The b2526 `stat7.xlsx` and `stat18.xlsx` have a Last-Modified date of 16 Apr 2025, after the 1 Feb 2025 presentation, so the Excel files were re-uploaded. The headers read Actuals 2023-2024, and the Statement 7 and 18 totals agree with other sources (food subsidy 2,11,814.39; Statement 18 total 9,35,335.03). | Mention this in union_fiscal-14. |

## Confirmed builder claims

| Issue | What was confirmed |
|---|---|
| union_fiscal-4 | `tr.pdf` / `ntr.pdf` read 'Actual 2023-2024', and the unit uses them. Every Budget file used carries the expected Actuals year (asserted independently). |
| union_fiscal-5 | All six St 9 fix-ups produce values equal to the printed page. Checked by the census, and by hand for the p94 grants and grand total, p95 capital and p52 glued pair. The three p57-58 footnote lines are not table rows. |
| union_fiscal-7 | The Finance Accounts tax revenue (23,36,024.87) minus the Receipt Budget Grand Total (23,27,250.55) = 8,774.32 = NCCD customs 962.07 + NCCD excise 7,812.25 (tr.pdf). |
| union_fiscal-8 | 1,70,890.51 − 1,70,876.97 = 13.54. |
| union_fiscal-9 | The PPAC 2025-26 State rows sum to 3,41,513.26, against a printed sub-total (A) of 3,42,180.50. (A) + (B) = 3,42,488.28 against a printed total of 3,42,488.20. So the sub-total is consistent with the total, and the rows are not. |
| union_fiscal-10 | NSI 2024-25 net is 3,38,985.70 and Annex 8 is 3,38,985.20. For 2023-24 the figures are 4,21,678.35 and 4,21,678.36. |
| Access-checker issues | The stale `tr.xls` is avoided and its header is asserted. R7 uses St 8 MH 0050 minor heads. Each file has exactly one source id (Statement 18 → `union_budget_transfers_to_states`, Annex 8 → `mof_union_budget_2026_27`). |

**Repro (union_fiscal-18).** The verifier ran `repro union_fiscal` twice, the second time with no edits of its own under way. Both times the result was the same:

- builds 1 vs 2 (PYTHONHASHSEED=1, 1 thread) and builds 1 vs 3 (PYTHONHASHSEED=0, 4 threads): all 10 files byte-identical;
- all 10 files equal `data/manifest.json`;
- the command still printed `REPRO FAILED: code_hash changed between builds`.

The unit's own files (`pipeline/ingest/union_fiscal/*`, last modified 16:43 IST) and `pipeline/core/*` (last modified 15:39 IST) were not modified during either run. The hash change therefore comes from other agents' concurrent edits, as the builder said. Determinism is confirmed. The item stays open only until someone runs `repro` while the repo is quiet (FR-uf-3).

## Close-out pass (2026-09-29)

Same verifier role, different session from the builder. Scope: the builder's follow-up, which added four datasets (2,012 values, 14 provenance records, 11 pins), fixed verify-1/2/3/5/6 and resolved union_fiscal-21. I changed only the verifier-owned `tests/verify/test_union_fiscal_spotcheck.py` and this file. No unit code, pins, clean data or issues file was touched.

### Verdict

**Accepted, with minor findings. All 2,012 new values match their raw cells: a full census with independent parsers found 0 mismatches.**

- The 8 datasets verified in the first pass are byte-identical to the committed versions (sha256 compared with `git show HEAD:`).
- All 185 earlier provenance records are unchanged, and 14 new ones were added.
- The census of the 8 earlier datasets still passes with 0 mismatches.
- The six failures in the spot-check file were stale expectations, not data errors. Each was re-derived from the raw document before being changed (see below). No real defect was hidden.

### What was run

| Step | Result |
|---|---|
| `test -k union_fiscal` | **183 passed**, 0 failed (was 164 passed, 6 failed) |
| `test tests/verify/test_union_fiscal_spotcheck.py -s` | 42 passed. `SPOTCHECK TOTAL: checked=11700 mismatched=0` |
| Mutation run (scratch, in memory) | One value, label, sign, period or geography was perturbed in each new dataset and in exp_profile. All 8 perturbations were caught by the census tests. |
| `fetch union_fiscal --offline` | OK, 41 raw files. It logs that PIB June 2023 has no pin, as expected. |
| `coverage union_fiscal` | No BROKEN. OFFICIAL covered=4, partial=12 (of 16) |
| `repro union_fiscal` | **REPRO OK**: 14 files byte-identical across seeds and thread counts, and they match `data/manifest.json` |
| `manifest --check` | Up to date |

### Stale spot-check items: what changed and why each change is legitimate

| Test | Change | Re-derived from |
|---|---|---|
| `test_all_pinned_files_hash_ok` | Pin count 30 → **41**. It now also checks that every provenance `raw_path` is pinned. The only unused pins are the C&AG certificate and the four PIB archive pages that locate the releases. | Pin file: +2 Finance Accounts PDFs, +3 `stat6.xlsx`, +6 PIB pages; all 41 sha256 re-checked |
| `test_stat21_heading_rows_do_not_double_count` (verify-1) | Strict xfail removed. It now passes, so the defect is fixed. | Clean heading rows = Grand Total |
| `test_stat21_headings_are_twice_the_grand_total` | **Replaced** by `test_stat21_levels_each_add_to_grand_total`. The old test documented the defect. The new one reads the raw grid by printed level: unnumbered ministry headings, 'N. Name' departments, items numbered in their own cell, and '3.01'/'4.01' sub-items. It checks that ministries = departments = items = Grand Total in all three files, and that the clean data carry the same sum at each level. The sub-item equals its item (ASI) in each year (2024-25: 5.62). | `b24xx_stat21.xlsx` grids |
| `test_exp_profile_census` | The verifier's index now reads '3.01'-style lines as sub-items, not headings. The first pass read it as a heading and grouped '4. Central Secretariat Library' under it. The census matches `level=subitem` rows too. 1,294/1,294 match, 0 ambiguous. | `b2425_stat21.xlsx` rows 59-61 are '3. Archaeological Survey of India' / '3.01 Contribution for hoisting UNESCO ...' / '4. Central Secretariat Library', all under '12. Ministry of Culture'. The builder was right (union_fiscal-21). |
| `test_rb_section_totals_one_series_across_vintages` (verify-2) | Strict xfail removed. It also asserts that the 2023-24 row keeps its printed 'Net-X' label and that no glued-word series remain. | Census values unchanged |
| `test_fa_nil_901_under_mh0032_kept` (verify-3) | Strict xfail removed. It now asserts value 0.0 on PDF page 9, that the page prints the nil marker, and that MH 0032 still closes. The reverse census no longer excuses this head. | St 8 page 9 text |
| `test_units_periods_and_stages`, `test_provenance_points_at_the_right_file` | Extended to the 4 new datasets. Period type, stock/flow, stage and vintage are checked, and so are the file, caption and conversion each provenance record names. | |

### New datasets: independent checks

| Dataset | Values | How (the unit's parser in brackets) | Mismatched |
|---|---:|---|---:|
| gcca (Statement 6, 3 vintages) | 1,610 | calamine (openpyxl). Items are paired with value lines in print order inside each demand block, asserted one-to-one and numbered 1..n. That absorbs, with no special cases, the wrapped labels, the label head printed above '8.' (b2526 row 714) and the two items in one cell (rows 727-728). **Census:** each row matched by level, item number, demand number, department and label. **Reverse census:** every printed line has exactly one row (561/517/532). **Closures:** items = demand and ministries = demands = items = Grand Total, in all 4 columns of all 3 files, to 0.015. | 0 |
| fa_gia (Appendix to St 9) | 40 | pypdf lines (pdfplumber). Rs lakh × 0.01. Right page, printed category as the label head, all 20 cells per table. | 0 |
| fa_provident_funds (St 14) | 184 | pypdf lines, amounts read from the right end of the line (pdfplumber x-positions). My own parse is checked first: opening + additions − discharges = closing on all 46 heads, and minor heads = sub-major totals = major-head TOTAL, **exactly** to the thousand rupees. Then every value × 1e4 must equal the printed amount on the page the provenance names. | 0 |
| pib_gst (April, May 2023) | 178 | lxml (BeautifulSoup). The headline paragraph's 11 amounts are parsed in print order. The State table's names are mapped to ISO codes by my own list. Vintage = 'Posted On' date. | 0 |
| **Fixed-seed locator sample** (seed 20260929; 10% per dataset, min 30) | 251 | A second route: following only the provenance locator (xlsx column letter and row range, or PDF/release page), the value is found as printed. | 0 |

Hand-typed anchors (31): gcca 9, fa_provident_funds 10, pib_gst 12. The fa_gia census compares all 40 printed cells directly.

**Builder claims confirmed:**
- Statement 6 Grand Totals are 3,06,263.98 / 3,03,915.55 / 2,72,655.92.
- Closures hold in all four columns (independent parse).
- The b2526 glitch pairing is correct. The neighbouring Budgets' BE columns confirm it: NYKS 3.0 (BE 2024-25) and 3.5 (BE 2025-26); RGNIYD 2.5 and 3.0.
- IGAS-2 figures:
  - State Government 3,98,428.04, of which capital 1,19,435.32.
  - UT Governments 57,748.91 / 4,522.41.
  - The capital column sums to 3,03,915.5611 against Statement 6's 3,03,915.55.
  - The State Government total is 1,41,535.55 below MH 3601 (5,39,963.59).
- GPF additions 68,989.35 and discharges 63,930.50 equal AFS Statement III '(i) State Provident Fund' (68,989.34 / 63,930.50, read with calamine).
- PIB headline identities hold: April gross is exact; May is 1 crore off from rounding; post-settlement figures are exact. State rows add up to the Grand Total within 4 crore (rounding).
- Scale:
  - Rs lakh × 0.01 and Rs thousand × 1e-4 are both proven by the exact matches above.
  - Negative stocks are kept as printed: PLI policy loans (e.g. 8014-01-108) and the defence/misc PF heads.

**Access (D1-1, D1-7):**
- All 11 new sidecars show status 200 on the first attempt, with no Cookie or Authorization header and no redirect.
- The PIB archive posts send only the page's own hidden fields and the filters, which is the case D1-7 allows.
- The challenge event itself leaves no artefact, because nothing is saved on a challenge. This is consistent with the missing June pin.

### Findings (close-out)

| # | Severity | Finding | Suggested fix |
|---|---|---|---|
| close-1 | minor | **Registry addition `pib_gst_monthly_releases` states two things that are no longer true.** `access.method` says "no challenge was served on 2026-09-29", but one was (union_fiscal-1). `coverage.notes` says "This unit ingests the 12 releases", but it ingests 2. | Reword both before the orchestrator merges the addition. |
| close-2 | minor | **Series split across Statement 6 vintages.** Demand No. 44 'Department of Animal Husbandry and Dairying' is `stat6.demand.ministry_of_fisheries_animal_husbandry_and_dairying` in 2022-23 and 2023-24 (the ministry's only demand in those files), but `...ministry_of_fisheries_animal_husbandry_and_dairying.department_of_animal_husbandry_and_dairying` in 2024-25 (when Demand 43 Fisheries appears). Same demand, same printed label, two series. The values are right. | Key a demand by ministry and department whenever the file prints a department line, or log it next to union_fiscal-22. |
| close-3 | minor | **Coverage precision.** (a) K6 declares `stat6.grand_total` as `control_total`. It is not a control total for K6: it includes grants to units inside general government (e.g. central autonomous bodies, 1,39,896.67 of the 3,03,915.56 capital) and excludes the RoW and other parts of K6. `partial` is the honest extent (the coverage state is the same either way). (b) The R2k `fa_gia` note cites union_fiscal-22 for the bridge caveat; it is union_fiscal-23. (c) Several notes and issue rows say "Expenditure Budget Statement 6". The document is the **Expenditure Profile** (sheet header 'Expenditure Profile 2024-2025'), as `table_id` correctly says. | Edit the coverage YAML and the wording. |
| close-4 | minor | **Statement 14 provenance note.** The note says the server Last-Modified dates are "16-18 Dec 2024". The St 14 sidecar says **24 Dec 2024**. (The b2526 `stat6.xlsx` was also re-uploaded on 16 Apr 2025, like verify-7; its header reads Actuals 2023-2024 and it closes.) | Say "16-24 Dec 2024" in the proxy note (union_fiscal-20). |
| close-5 | info | PIB headline rows carry slug text as `item_label` ('cgst', 'gross gst', 'igst settled to cgst'), not the published wording ('CGST', 'gross GST revenue', 'settled ... to CGST ... from IGST'). The guide asks for the English label as published. | Cosmetic. Use the printed phrase. |
| close-6 | info (Phase 2) | **MH 8014 is not the AFS PLI line.** AFS Statement III '(ii) Postal Insurance and Life Annuity Fund' (52,132.49 / 53,943.57) equals St 14 group (d) 'TOTAL- POST OFFICE INSURANCE FUND', which is MH 8014 + 8015 (investments of the fund) + 8016 (its income and expenditure). MH 8014 alone is 16,793.08 / 12,852.69 (tested). 8015 and 8016 are not ingested. For S9 (premiums and claims), 8014 is the right block, but nobody should reconcile it to the AFS line. | Add one line to union_fiscal-24. |
| close-7 | info (policy) | PIB served an F5 challenge. Every online `fetch union_fiscal` will send one more request to that host and stop, which is D1-1b-compliant but repeats contact with a host that has challenged us. The builder also disclosed about 6 exploratory curl requests to PIB the same afternoon, made outside `ctx.fetch` (public pages, no bypass). | Agree with FR-uf-4: the orchestrator should decide on a D1-4-style rule (or skip PIB unless asked) before the next online fetch. Future exploration should go through `ctx.fetch`'s host lock. |

No major finding. Every value in the unit matches its source: 11,700 comparisons over 8,523 values.
