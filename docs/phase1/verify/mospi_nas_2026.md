# mospi_nas_2026: independent verification

## Final pass (2026-09-29): c-1 fix (API indicator 8 item codes)

**Verdict: accepted. c-1 is fixed.** I re-derived every figure the builder cites from raw with my own reader (JSON pages sha256-checked against the pins, NAS 2025 1.1 and NAS 2026 7.2 read from the raw workbooks with calamine; nothing imported from `api.py`). No regressions found. The strict xfail is removed and replaced by a normal check that grounds both new codes in raw.

### Re-derived from raw

| Claim | My result |
|---|---|
| Current series, indicator-8 total = GFCF (ind. 9) + CIS (ind. 12), without valuables | 74 of 74 year x round x price cases (old base 68, new base 6); max \|GCF - GFCF - CIS\| = 3 (old) and 1 (new). Adding valuables misses by at least 1,48,879. New base 2023-24 Final current: 96,28,092. |
| New base by industry = NAS 2026 7.2 GCF | 150 of 150 API cells located in raw 7.2 by value (0.5) and label. A key join of the clean rows with `s7_2` on (item_code, industry, period, price_basis, estimate_stage) matches 150 of 150 within 0.5 (max 0.496). Now that the codes coincide, a plain join works as intended, including the stage. |
| Back series: 62 records, no industry detail; 2011-12 = old 1.1 GCF | 62 records, 0 with industry, sub-industry or sector. 2011-12 = 34,03,008 at both price bases; raw NAS 2025 1.1 row 9 'GCF' = 34,03,007.9. 34,03,008 - 29,97,732 - 2,07,983 - 2,53,033 = **-55,740** (1.1: 34,03,007.9 - 29,97,732.9 - 2,07,983.2 - 2,53,033.3 = -55,741.5). The minimum \|residual\| over all 62 years x 2 price fields is **14** (1953-54, current). The current series' 2011-12 'Additional Revision' total is 32,05,716. |
| Output census | Indicator 8: 1,700 rows `gcf_excl_valuables` (api_b2011_annual), 150 `gcf_excl_valuables` (api_b2022_annual), 124 `gcf_incl_errors_omissions` (api_b2011_back); 1,974 in all. Every series_id starts `api.<item_code>.`. No API row is coded `gcf`. 1.1 GCF keeps `gcf` (s1_1 6 rows, old-base NAS 2025 s1_1 26 rows). Across **all units'** clean data, `gcf_excl_valuables` appears only in the API current series and 7.2/7.2A-C, and `gcf_incl_errors_omissions` only in api_b2011_back. (series_id, period) stays unique in all five API datasets. |
| Descriptions | The three datasets holding indicator 8 carry the note (back: old 1.1 concept, "do not splice"; current: GFCF + CIS, as 7.2, not 1.1). The quarterly datasets carry none, correctly (indicator 8 is not quarterly). |
| Build guard `_check_gcf_concept` | Passes on the real output. I mutated the real rows in memory; it caught all four: a back year set to GFCF + CIS + valuables; industry detail on a back row; a current total off by 4; and the old `gcf` coding (fails with "0 checks"). |

The census (`test_api_census_every_row_against_raw_json`) still locates all 15,775 API rows in raw, with the page-level provenance. So values, dims, stages and prov_ids did not move, consistent with the builder's snapshot diff.

### Spot-check file change

`test_api_gcf_by_industry_of_use_has_its_own_item_code` is no longer xfail. It now asserts:
- the exact code set per dataset and the 124 / 1,700 / 150 row counts;
- that every series_id carries its item code;
- that no API row is `gcf`, and that the back code is used nowhere else in the unit;
- from raw JSON, the 74 current-series GFCF + CIS identities (and the valuables gap), the at-least-14 residual in all 124 back values and the -55,740 at 2011-12;
- the 150-cell key join with 7.2.

In memory, it fails on the pre-fix coding, on the back series coded like the current series, and on a 1-crore change in one joined cell.

### What was run

| Step | Result |
|---|---|
| `test -k mospi_nas_2026` | **1,078 passed**, 0 failed, 0 xfailed (the builder's 1,077 plus the former xfail). |
| `test tests/verify/test_mospi_nas_2026_spotcheck.py` | **31 passed**, about 111 s. |
| `repro mospi_nas_2026` | REPRO OK: 88 files byte-identical and matching the manifest. |
| `coverage mospi_nas_2026` | OFFICIAL covered 18, partial 16 (of 34). Unchanged. |
| `manifest --check` | Up to date. |
| `ruff check` on api.py, test_mospi_nas_2026_api.py and the spot-check file | Clean. |
| Downstream | `tests/cross/recon_lib.py` reads api_b2022_annual only for GDP, PFCE and GFCE; no consumer of `api.gcf` exists. |

### Notes (information only, not blocking)

- **f-1: basis for "errors and omissions".** Neither pinned document names errors and omissions: NAS 2025 1.1 has no such line or footnote, and the NAS 2024 methodology PDF does not contain the words. The code name therefore rests on issue 14's citation of S&M 2026 s.23.4 (documentation, not pinned: issue 21) plus the non-zero residual, which is numerically solid (at least 14 in every year). Issue 37's phrase "confirmed by a document for 2011-12 only" refers to that unpinned citation. The Phase 2 guidance (link through GFCF, CIS and valuables, never splice) does not depend on the name.
- **f-2: ruff across the whole unit package** reports 5 E501 lines (`oldbase.py` 42, `stmts2026.py` 135/142/147/152). All five are already at git HEAD and are unrelated to c-1. The builder's "ruff check: clean" holds for the files the fix touched.

Files changed by me: `tests/verify/test_mospi_nas_2026_spotcheck.py` (the one test above) and this note. Nothing committed.

## Close-out pass (2026-09-29): NAS API datasets, old-base stage relabel, F1, 4.1 codes, code guard

**Verdict: accepted.** The 15,775 API values, the 2,540 stage relabels and the F1 row all check out against raw, with 0 mismatches. Issue 35 can be closed.

There are two new minor findings, neither blocking:
- **c-1:** the API's "GCF by industry of use" carries the item code `gcf`, but it is a different concept from Statement 1.1 GCF. It also changes meaning between the back series and the current series.
- **c-2:** total GVA is served twice in the API datasets, with the same label.

Three items are information only (c-3 to c-5). Nothing in the unit was changed by me. Section order in this file is newest first.

### What was run

| Step | Result |
|---|---|
| `fetch mospi_nas_2026 --offline` | 190 raw files match their pins (84 workbooks/PDF/listings + 106 API JSON pages). |
| `repro mospi_nas_2026` | REPRO OK: 88 files byte-identical across hash seeds and thread counts, and they match the manifest. |
| `coverage mospi_nas_2026` | OFFICIAL covered 18, partial 16 (of 34), no BROKEN. F1 is `covered` through `derived_residuals` (full). |
| `test -k mospi_nas_2026` (after my update) | **1,073 passed, 1 xfailed** (the xfail is my strict xfail for c-1). |
| `test tests/verify/test_mospi_nas_2026_spotcheck.py` | 30 passed, 1 xfailed (31 tests: 17 earlier + 14 new), about 65 s. ruff is clean on the file. |
| Clean output vs git HEAD, column by column | See the second table below. Only the changes the builder described appear. |

**Old-base datasets vs git HEAD.** In the 16 old-base datasets, only `estimate_stage` differs: 426 + 140 + 110 + 145 rows in the NAS 2025 datasets and 1,719 in the NAS 2024 sequences, **2,540 in all**. Values, series ids, prov_ids, periods and every other column are identical, and no row was added or removed.

**Other statement datasets vs git HEAD:**

| Dataset | What differs |
|---|---|
| `derived_residuals` | 3 rows added (F1). The 6 existing rows are identical. |
| `s4_1` | 6 `geography` cells: the earlier IN-CT to IN-CG change (D1-9). Nothing else. |
| Every other statement dataset | Unchanged. |

### How the spot-check file was updated (`tests/verify/test_mospi_nas_2026_spotcheck.py`)

**Why 8 tests failed.** Seven workbook tests failed because they sent the new `NAS API getNASData indicator N` rows to `file_key()`. The eighth, the stage test, failed because it encoded the old "textbook" stage cycle.

**What changed in existing tests.** No check was loosened for statement rows:
- The workbook tests now run on the statement datasets only, through `stmt_datasets()`.
- API rows get their own checks (listed below). The provenance test checks that each API row points to a pinned JSON page of its own query and indicator.
- The stage test now takes old-base stages from `oldbase_stage_table()`. That table is **derived from raw inside the test**, not copied from the unit, and is pinned to an explicit expected table.
- The stage test also requires the new-base API annual stages to equal the NAS 2026 press-release stages.
- `test_derived_residuals_recomputed_from_raw` now also recomputes F1 from raw 7.1 and 6.1 cells, located by label. It checks F1's provenance inputs too.

**New tests.** All use my own JSON reader: pages are read with `json` after their sha256 is checked against the pins, and nothing is imported from `api.py`.

| Test | What it proves |
|---|---|
| `test_api_pages_complete_and_pinned` | The 105 data pages plus the indicator list are pinned. Pagination is complete: page i of n, 200 per page, totalRecords = records served. Every record carries its page's base, series and frequency, and the URL parameters match. The new-base back-series probe, and the old-base back series of indicators 3 and 4, answer 'No Data Found'. The indicator list is 1-22, with 21 and 22 being growth rates. |
| `test_api_census_every_row_against_raw_json` | **All 15,775 API rows** (5,344 / 7,160 / 2,084 / 575 / 612) are found in raw by indicator, year, quarter, revision round and printed industry, sub-industry and sector labels. Each must have the same number in the row's price field. It must also agree on industry and institution (checked against my own maps from the raw labels), `dim_other` revision, stage (my own round-to-stage map), period type, unit (the record says '₹ Crore'), base year, price basis, source, status, vintage (the page's pinned retrieval date) and series-id suffixes. Its provenance must point at **the page that holds the record**. |
| `test_api_spotcheck_sample_by_value_search` | A seeded sample (seed 20260929+35): at least 10% and at least 30 rows per dataset, 1,580 rows in all. Each is found by *searching* the pages for the number, which is a second route alongside the keyed census. |
| `test_api_checker_rejects_mutations` | Mutations of 300 sampled rows (1,200+ in all) are all rejected, with 0 leaks. The mutations are: value + 1, another series' value, another period, the other price basis, another stage, another industry, and another vintage. |
| `test_api_every_raw_record_is_ingested_or_a_documented_skip` | A reverse sweep: every raw price that is not blank is in the clean data (15,775). The only raw records not ingested are exactly the documented ones:<br>• the 74 indicator-3/4 records labelled '₹ Lakh' (issue 31);<br>• one GNDI record dated '1999', which is a copy of the 2025-26 FAE current price of 3,62,04,793 (issue 32a);<br>• two exact duplicates, old-base quarterly agriculture GVA for Q1 and Q3 of 2019-20 (32b);<br>• blanks, which are served only as null or 'nan' (32c). |
| `test_api_lakh_label_is_a_label_error` | Issue 31 re-derived. Taxes − subsidies = net taxes (crore) within 2, in every record and price field on both bases. The new-base API taxes and subsidies also equal NAS 2026 1.1 (crore) within 1. The label is wrong, and skipping these indicators rather than relabelling them is the right call. |
| `test_api_new_base_equals_nas_2026_statements` | 133 whole-economy comparisons, all within 0.5 crore and with the same stage. This includes the GVA, CFC, GFCF and saving totals, which the builder's own test filters out (see c-4). |
| `test_api_quarters_add_up_to_annual` | New base: 10 indicators × 4 years × 2 price bases. Quarters add up to the annual figure within 2 crore, and within 1 for GDP. Q1 2026-27 GDP is 88,26,871. |
| `test_api_back_series_identities_and_additivity` | Issue 33 re-derived. GDP = GVA + net taxes, NDP = GDP − CFC and GNI = GDP + NPI hold within 2 in all 62 years at both price bases. The 11 industries add up to total GVA within 11 from 2004-05, and miss by more than 11 in all 54 earlier years at both bases. At constant prices the gap reaches about 1 lakh crore. |
| `test_api_imports_positive_and_documented` | API imports are positive, and each dataset description says so. |
| `test_api_gcf_concepts_differ_between_back_and_current_series`, plus strict xfail `test_api_gcf_by_industry_of_use_has_its_own_item_code` | Evidence for c-1. |
| `test_oldbase_stage_table_derived_from_raw`, `test_relabelled_rows_sample_against_raw` | The stage relabel. See the next section. |

### Old-base estimate stages (issue 9): builder's table accepted

**How I derived it.** I compared each NAS 2025 1.1 level and each NAS 2024 1.15 level with every API revision round of the same indicator, year and price basis. The indicators used were GVA, GDP, CFC, NDP, GFCF, PFCE, GFCE, CIS, valuables, trade, NPI, GNI, transfers, GNDI and saving. GCF is left out because of c-1, and taxes and subsidies because of the lakh label. Every clean level used here was already located in its workbook by the census.

**Tolerance.** The old-base API **truncates** to whole crore: of 432 matching values, 172 match only the floor and 31 only the rounded value. So a match means |diff| < 1, not 0.5.

**Result.** A level that equals exactly one round votes for that round. In every edition and year all votes point to the same round, with no conflict:
- **NAS 2025:** between 16 and 29 votes per year.
- **NAS 2024:** 2011-12 has 2 votes, GDP and CFC. CFC is decisive: Additional Revision 9,17,174 vs SRE 9,17,140. The other years have between 5 and 10 votes.

The derived table is:

| Years | NAS 2024 | NAS 2025 |
|---|---|---|
| 2011-12 to 2013-14 | Revised (API "Additional Revision") | Revised (API "Additional Revision") |
| 2014-15 to 2020-21 | TRE | TRE |
| 2021-22 | SRE | SRE |
| 2022-23 | FRE | **Final** |
| 2023-24 | — | FRE |

This equals `oldbase.STAGES`.

**The rounds explain the schedule.** For old-base 2021-22 the API has no TRE round, and for 2022-23 it has no SRE round: 2022-23 goes straight from FRE to 'Final Estimates'. So the NAS 2025 labels (2021-22 SRE, 2022-23 Final) reflect how MoSPI actually revised the old series, not a labelling slip. 'Revised' is in the PIPELINE_GUIDE §5 vocabulary.

**Relabel census.** Exactly the rows of the six changed (edition, year) groups changed, 2,540 in all. A seeded sample of 254 of them (10%) was located in the raw workbooks, and every one carries the table's stage.

### Other builder items re-checked

- **F1 is correct.** 7.1 'Total' × 'Compensation of employees' + 6.1 CE from RoW − 6.1 CE to RoW, all read from raw by label:
  - 2022-23: 86,80,252
  - 2023-24: 94,74,605 (94,42,896.6 + 62,344.2 − 30,635.9)
  - 2024-25: 1,06,64,336

  The rows are `derived` with stage Final/Final/FRE and vintage 2026-08-31. Their provenance inputs are exactly the prov_ids of the 7.1 and 6.1 rows. Coverage F1 `full` and 18 covered is fair: the row is the gap-map identity, and F1a (the split by household group) stays Phase 2.
- **4.1 codes.** The 31 States still carry their own ISO code (`test_4_1_state_rows_carry_their_own_iso_code` passes unchanged).
- **Code guard.** `test_oldbase_sna_code_is_the_hindi_side_code` passes unchanged. Output is unchanged, as claimed.
- **Access.** All 106 API sidecars show GET to api.mospi.gov.in, status 200, no redirects, and no Cookie or Authorization header. There is no network code in `pipeline/ingest/mospi_nas_2026/`: only `ctx.fetch`, with the D1-6 host-scoped TLS opt-in in the framework.

### Findings (close-out)

| # | Severity | Finding | Evidence | Suggested fix |
|---|---|---|---|---|
| c-1 | minor | **API indicator 8 ('GCF by industry of use') has item code `gcf`, the same code as Statement 1.1 GCF, but it is a different concept and changes concept at the splice.**<br>• Current series (both bases): the total is **GFCF + CIS, without valuables**. New base 2023-24: 96,28,092, against 1.1 GCF of 1,00,04,323. The gap of 3,76,231 is valuables.<br>• Old-base back series: the total **is the old 1.1 GCF**, which includes valuables and errors and omissions. 2011-12: 34,03,008, equal to NAS 2025 1.1 GCF of 34,03,008.2. The current series' 2011-12 'Additional Revision' total is 32,05,716.<br>• So a back-plus-current splice of `api.gcf` jumps by about 1.97 lakh crore (6%) in 2011-12 from definitions alone.<br>• A join on `item_code` (the builder's own cross-check joins API to 1.1 on item code) would compare unlike things. The builder's test avoids this only because it filters out rows with an industry.<br>• Issue 33 mentions only the 3-crore GDP difference at 2011-12. | `test_api_gcf_concepts_differ_between_back_and_current_series` (passes); strict xfail `test_api_gcf_by_industry_of_use_has_its_own_item_code`. | Give indicator 8 its own item code (e.g. `gcf_by_industry_of_use`). Record in issue 33 (or a new issue) that the back series' GCF is the 1.1 concept while the current series' is GFCF + CIS, and that Phase 2 must not splice them. When the code changes, the xfail turns into XPASS and fails, which flags it for removal. |
| c-2 | minor | **Total GVA is served twice, with identical labels.**<br>• Back series: two parallel total-GVA series for all 62 years: `api.gva.<basis>` (a record with no industry) and `api.gva.ind_total.<basis>` (industry 'Total Gross Value Added'), 124 rows each. They differ by 1 crore in 25 year-and-price-basis cases (e.g. 1998-99 current: 16,31,018 vs 16,31,019).<br>• Annual series: every round from FRE on has both `ind_total` and `sec_total_economy` rows, with the identical label 'Gross Value Added \| Total Gross Value Added \| <round>'.<br>• Summing a dataset by `item_code` or label double-counts. Neither point is documented. Issue 33's "differs from Total Gross Value Added" does not say which total. | Raw pages `nasapi_b2011_back_a_i01_p*.json`; the reverse sweep has to key on the label's role (industry vs sector) to keep the two apart. | Document both in issue 33/34, and say which total the additivity test uses. They are as published, so keep both. |
| c-3 | minor (documentation) | **API vintage is the snapshot date, 2026-09-29, not a publication date.** PIPELINE_GUIDE §5 defines `vintage` as the publication date of the release. The builder states the deviation (issue 34) and the reason (the API prints no dates). For the new-base annual rows, the numbers are exactly the NAS 2026 figures (vintage 2026-08-31), so the same number now appears under two vintages. | Every API row: `vintage` = pin `retrieved_at`. | Acceptable as a labelled assumption. The orchestrator should add it to the cross-unit list of vintage conventions. Phase 2 must pick rounds by `estimate_stage` / `revision`, not by vintage. |
| c-4 | info | **Two builder claims are slightly broader than the builder's own tests.**<br>• "Equals NAS 2026 1.1 and 8.17.1 within 0.5 crore for every aggregate": true, but the builder's test drops rows where `industry` or `institution` is set, so it never compared the GVA, CFC, GFCF and saving totals. My test covers them (133 comparisons, all within 0.5, same stage).<br>• "Quarters add up to the annual figure within 1 crore": holds for GDP (the builder's test). Across all 10 quarterly indicators the maximum is 2 crore (current-price imports), which is rounding. | `test_api_new_base_equals_nas_2026_statements`, `test_api_quarters_add_up_to_annual`. | None needed. Optionally, reword the claim. |
| c-5 | info | **Old-base API precision.** Old-base API values are truncated to whole crore, not rounded, so matching old editions to the API needs a tolerance under 1 crore. The builder's stage test uses 1, which is fine. New-base values are rounded (0.5 holds). | See the stage section above. | None. |

### Counts (close-out pass)

- **API values compared against raw JSON:** 15,775 of 15,775 (census), with 0 mismatches. On top of that:
  - a value-search sample of 1,580 (10.0%);
  - 1,200+ mutations, all rejected;
  - a reverse sweep of every raw record.
- **Stage relabel:** 2,540 of 2,540 rows checked for group membership. 254 of them were re-located in the raw workbooks, with 0 mismatches. The stage table was derived independently and equals `oldbase.STAGES`.
- **Derived rows:** 9 of 9 recomputed from raw, including F1.
- **Statement rows:** the census of 26,799 official rows still passes, with 0 mismatches.

---

## Second pass (2026-09-29): verify-1 to verify-8 re-checked

**Verdict: accepted.** Both major findings are fixed, and no regressions were found. What remains are two minor, non-blocking observations (s2-1, s2-2).

### What was run

| Step | Result |
|---|---|
| `fetch mospi_nas_2026 --offline` + `build mospi_nas_2026` | 84 raw files match the pins. Build OK: 81 datasets, 26,805 rows (s3_0 still has 593 rows). |
| `test -k mospi_nas_2026` (after extending the spot-check) | **915 passed**, 0 failed. That is the builder's 909 plus my 6 new tests. |
| `test tests/verify/test_mospi_nas_2026_spotcheck.py` | 17 passed (11 first-pass + 6 second-pass), about 100 s. |
| `coverage mospi_nas_2026` | OFFICIAL covered = 17, partial = 17 of 34, no BROKEN. I3a (1.14) is now `control_total`. |
| `repro mospi_nas_2026` | REPRO OK: byte-identical across hash seeds and thread counts, and matches the manifest. |

### Findings re-checked

| # | Status | Evidence |
|---|---|---|
| verify-1 (3.0 liabilities mis-coded) | **Fixed** | I read raw S3.0 rows 92-101 myself. Column A: '', F1..F8, B9. Column P: F1..F8, B9, ''. So P[r] = A[r+1] exactly. The clean 2022-23 rows are now: `net_incurrence_of_liabilities [-]` 42,77,019.5 (N92); `f2` Currency and deposits 20,05,617.5 (N94); `f3` 2,76,987.9; `f4` 6,79,655.9; `f5` 1,70,449.2; `f6` 4,94,101.9; `f8` Other accounts payable 6,50,207.1 (N100); `b9` NET LENDING 9,09,872.4 (N101). There are no `f1`/`f7` liability rows because they are blank in raw. New full-population test `test_oldbase_sna_code_is_the_hindi_side_code`: every one of the 6,908 old-base sequence rows is located in raw by the census checker, and its printed `[code]` and item code must equal the raw row's column-A code (the English column only when A is empty; A only inside the 3.0 shifted block). All pass. When I re-inserted the old coding in memory, this test and `test_oldbase_3_0_liability_anchors` both catch exactly **96 rows**. |
| verify-1, guard in the unit | Fixed, with a gap (s2-1) | `oldbase._row_code` fails the build when both columns hold a code and disagree. Outside the documented block it asserts the exact shift. My independent A-vs-P sweep of all 16 old-base files: the only disagreements are 3.0 rows 93-100. The only one-sided codes are 3.0 R92/R101 (the shift) and 1.15 R11, where A holds a corrupted formula string 'P1+34:3…' and P holds 'P1'. 'P1' is correct. |
| verify-2 (issue 13 / closure) | **Fixed** | Issue 13 no longer blames MoSPI for 3.0. The unit's closure test runs on all 12 sequences, with 6.0's `f` totals mapped. My new `test_oldbase_financial_accounts_close_in_clean` finds the totals by **label**, independently of codes. It confirms net acquisition − net incurrence = financial B9 = capital B9 within 3 crore, for all 12 datasets × 12 years. It also confirms RoW B9 (6.0) = −total-economy B9 (1.15) every year: 2022-23 is +5,35,134.8 vs −5,35,135.2. |
| verify-3 (I3a) | Fixed | The coverage entry is `control_total`, giving 17/17. |
| verify-4 ('Less') | Fixed | My own raw scan finds a 'Less'-captioned data row in exactly 16 workbooks and datasets. All 16 descriptions carry the positive-magnitude note, and none is missing (`test_less_items_are_documented`). The census already shows every such value has the raw sign. |
| verify-5 (dims) | Fixed; open point s2-2 | 4.1: the 31 State/UT rows carry their own ISO code (my own map), every other row is `IN`, and the codes are unique per State. The raw 4.1 State set equals the clean set (`test_4_1_state_rows_carry_their_own_iso_code`). 1.9/1.11: sector rows carry the sector named by their own label (my map). The six leaf sectors add up exactly to Gross Savings (1.9) and GFCF (1.11) in every period and price basis, so nothing is double-tagged, and the 1.11 shares add up to 100.00 (`test_1_9_and_1_11_institutions`). |
| verify-6, -7, -8 | Documented | Issue 9 has been extended and issue 27 is open. The report typo is acknowledged. |

### Builder's claim that the verifier's census blocked sub-row institutions

The claim is accurate: the first-pass institution check looked only at the row, the title and header rows. I made it parent-aware. It now also accepts the heading named by the item-code prefix. `parent_ok` separately proves that heading is the nearest parent above the cell in raw. Mutation check: of 396 wrong-institution mutations on 1.9/1.11 2023-24 rows, 34 were accepted. All 34 are the parent's own sector (32 asset sub-rows, plus 1.9 DE/NDE → `nfc_public`). No wrong sector was accepted, and 144 of 144 correct parent-derived tags on 1.11 sub-rows are accepted. The builder can therefore tag sub-rows later without the checker blocking it. Leaving them untagged is also acceptable: it avoids double counting when summing by institution.

### New observations (minor, non-blocking)

| # | Severity | Finding | Suggested fix |
|---|---|---|---|
| s2-1 | minor | `_row_code` cross-checks only when **both** code columns hold a code. A future re-issue that blanks one column while shifting the other, as 3.0 R92 does, is not caught outside the whitelisted block. Today the only such rows are 3.0 R92/R101 (covered) and 1.15 R11 (harmless, see above). | Treat a one-sided code as a disagreement too, whitelisting 1.15 R11, or rely on the new spot-check test, which already guards this on every build's output. |
| s2-2 | minor (cross-unit) | 4.1 uses IN-CT / IN-TS / IN-UK. Other units use IN-CG (and IN-TG is being discussed). This is issue 26, and the code set is an orchestrator decision. My test accepts both spellings for CT/CG, TS/TG and UK/UT. | Orchestrator: fix one ISO 3166-2:IN code set project-wide. |
| info | – | 1.9 tags NFC DE/NDE (`nfc_public_de`/`_nde`) but not FC DE/NDE, and no `fc_public_de` code exists. 6.0's financial totals have item code `f` (label `[F]`). Both are documented and consistent with raw. | None. |

### Counts (second pass)

- Values compared against raw: **26,805**. That is the census of all 26,799 official rows (value, label, period, price basis, dimensions, parent heading), plus the 6 derived rows recomputed from raw. The seeded, stratified sample within it is 3,552 rows (13.3%), across all 80 official datasets.
- On top of the census, all 6,908 old-base sequence rows had their SNA code identity checked against column A, and 144 financial/capital-account totals were checked for closure in clean data.
- Numeric mismatches: 0. Wrong identities: 0 (was 96).
- Access (D1-1/D1-2): no network code in `pipeline/ingest/mospi_nas_2026/` (no requests, urllib, cookies, auth or legacy-TLS workaround). FR-1 remains a framework request. No microdata.

---

# First pass (2026-09-29)

Verifier: an adversarial agent that did not build the unit (SPEC rule 3). The regression test re-parses the pinned raw workbooks with its own code. It does not import `pipeline.ingest.mospi_nas_2026`, its row specs or `codes.py`.

## Verdict

**Accepted with one major defect to fix.**

- Every number in the unit matches the pinned MoSPI workbooks. All 26,799 official rows were located, with full context, in their own statement file (a census, not a sample), and the 6 derived rows were recomputed from raw. That is 0 numeric mismatches.
- Every level number in every ingested workbook appears in the clean data. The only exceptions are the growth-rate blocks that the unit documents as skipped.
- New base and old base are strictly separated.
- Fetch code and sidecars comply with D1-1 and D1-2.

The defect: in old-base Statement 3.0 (NAS 2024, financial corporations), the financial-account liabilities block is **mis-coded**. The affected rows are 8 series × 12 years = **96 rows** (verify-1). As a consequence, the unit's issue mospi_nas_2026-13 blames MoSPI for a "3.0 financial account does not close" defect that is really an ingest artefact.

## What was run

| Step | Result |
|---|---|
| `build mospi_nas_2026` (offline from pins; `build` takes no `--offline` flag) | OK: 81 datasets, 26,805 rows, manifest regenerated |
| `fetch mospi_nas_2026 --offline` | OK: 84 raw files ready, hashes match the pins |
| `test -k mospi_nas_2026` | 897 passed, **1 failed**: `tests/verify/test_mospi_nas_2026_spotcheck.py::test_oldbase_sna_codes_match_labels` (verify-1) |
| `test tests/verify/test_mospi_nas_2026_spotcheck.py` | 11 tests: 10 passed, 1 failed (the same test) |
| `coverage mospi_nas_2026` | no BROKEN entries; OFFICIAL covered = 18, partial = 16 of 34 |
| `repro` | not re-run (the builder reports REPRO OK) |

## Method (`tests/verify/test_mospi_nas_2026_spotcheck.py`)

- **Parser.** python-calamine (the unit uses openpyxl), with `skip_empty_area=False` so cell references are real Excel coordinates. Each raw file's sha256 is re-checked against `data/raw_pins/mospi_nas_2026.yaml`. Clean data are read with pyarrow.
- **Search, not position.** For each clean row, every cell in the workbook holding the same number is a candidate. Population rows are converted back to millions first. A candidate is accepted only if its own context agrees with the row on all of these:
  - **Label.** Every part of `item_label` equals (after normalisation) a text in the cell's row or in its column-header chain. The old-base `[D1]`-style SNA code must also appear in the row.
  - **Parent heading.** For repeated labels, the dotted item-code prefix must match the nearest parent heading above the cell. Examples: `general_government.machinery_and_equipment` in 1.11, `public_financial_corporations.departmental_enterprises` in 1.9, `education.gg_ice` in 5.2.
  - **Period.** The nearest pure year header ('2023-24', '2024-25 (FRE)', 'Q1' + FY, '2023' → 2023-03-31, or the 4.2 sheet name) must equal `period`. Headers are never propagated across a panel's label column.
  - **Price basis.** The nearest 'current' or 'constant (2022-23)' marker (column header, then block caption, then title) must equal `price_basis`.
  - **Dimensions.** Industry, institution, COFOG (with parent column for the 'administration' sub-columns), NIC code, SNA account and side are checked against my own keyword maps, written from the raw labels.
- **Census plus sample.** `test_every_row_against_raw` checks all 26,799 official rows (about 40 s). `test_spotcheck_values_against_raw` is a seeded sample (seed 20260929, ≥12% and ≥10 rows per dataset, plus every 2023-24 row of 1.1, 1.9, 1.11, 1.14, 5.3 and 6.1: 316 rows). It covers 3,552 rows across all 80 official datasets, 33 periods (FY, FQ, 31-March dates), all four price bases, both base years, and the units INR_crore, percent, index and INR. `count` is covered by the census.
- **Self-test.** `test_checker_rejects_mutations` feeds the checker about 1,000 corrupted records: a value ×1.001, another series' value (row or column shift), another period, and the other price basis. All are rejected. In a wider manual run the checker rejected 2,126 of 2,126 such mutations, plus 1,826 of 1,828 institution, side, account, COFOG and NIC mutations. The two accepted ones are genuine equal-number coincidences: D63 resources = uses for the total economy, and B8n is equal in the two use-of-income accounts.
- **Reverse sweep.** `test_every_raw_number_is_ingested` checks every numeric cell of every ingested workbook, except serial and NIC-code columns, against the clean data. The only unmatched numbers are in 8.17.1, 8.17.2, 8.18.1 and 8.18.2, and `test_skipped_blocks_are_only_growth_rates` proves they are all under 'percentage change' / growth headers (issue -3). Nothing else was dropped, old base included.
- **Derived rows.** `test_derived_residuals_recomputed_from_raw` recomputes both gaps for 2022-23, 2023-24 and 2024-25 from raw cells located by label. Household GDI − FCE − saving (1.14) gives 5,71,133 in 2023-24. GCF (1.1) − finances for GCF (1.9 item 3) gives 3,58,634. The rows are `derived`, and their provenance has a method and inputs.
- **Full-population label checks.** Every row's provenance points to the pinned file of its own statement, and source, price basis, vintage and status equal the provenance record. Base, vintage and stage are checked on every row: new base is 2022-23 / 2026-08-31 with Final/Final/FRE/PE (quarters and 31-March stocks mapped to their FY); old base is 2011-12 with the unit's FRE/SRE/TRE rule. Old-base SNA codes are checked against canonical SNA instrument codes. The raw NAS 2024 financial accounts are checked for closure.

| Group | Datasets | Rows (census, all checked) | Of which in the seeded sample |
|---|---:|---:|---:|
| Template 1.1, 8.17.1 | 2 | 494 | 136 |
| Ch.1 (1.2-1.14) | 14 | 2,330 | 414 |
| Ch.4 (4.1, 4.2) | 2 | 1,608 | 194 |
| Ch.5 (5.1-5.3) | 3 | 678 | 106 |
| Ch.6 (6.1, 6.2) | 2 | 243 | 95 |
| Ch.7 (7.1x-7.4x) | 16 | 6,846 | 822 |
| Ch.8 (8.1-8.18) | 25 | 5,551 | 691 |
| Old base NAS 2024 sequences (1.15, 2.x, 3.x, 4.0, 5.0, 6.0) | 12 | 6,908 | 835 |
| Old base NAS 2025 (1.1, 1.9, 1.14, 5.3) | 4 | 2,141 | 259 |
| Derived residuals (recomputed from raw) | 1 | 6 | – |
| **Total** | **81** | **26,805** | **3,552** |

Numeric mismatches: **0**. Rows with the wrong identity (item code / SNA code): **96** (verify-1).

No values in this unit come from PDFs. The only PDF, the NAS 2024 methodology note, is used for the estimate-stage label only, so the PDF page-text check does not apply.

## Findings

| # | Severity | Finding | Evidence | Fix |
|---|---|---|---|---|
| verify-1 | **major** | **Old-base 3.0 financial-account liabilities are mis-coded.** In raw `nas2024_3.0.xlsx` the English-side code column P is shifted one row down on rows 92-100. P92 'F1' sits beside 'Net incurrence of liabilities', P93 'F2' beside 'Monetary gold and SDRs' … P100 'B9' beside 'Other accounts payable', and the NET LENDING row has no code. The Hindi-side code column A (F1…F8, B9) is correct and matches every other sequence file. The unit takes codes from column P, so 8 series × 12 years = 96 rows carry wrong codes and wrong `[code]` labels: `financial.liabilities.f1` is the *total* net incurrence; `f3` is currency and deposits; `f4` debt securities; `f5` loans; `f6` equity; `f7` insurance/pension; `b9` is **other accounts payable**; and the real B9 is `net_lending_net_borrowing [-]`. A Phase 2 consumer asking for FC F3 liabilities or FC B9 gets the wrong instrument. | `test_oldbase_sna_codes_match_labels` fails with 96 rows. Column A and column P disagree only in 3.0 (checked in all 12 NAS 2024 files). The unit's own anchor `oldbase_soa_s3_0.financial.liabilities.f3.current = 2005617.5` ('S3.0!N94') is currency and deposits, so the test encodes the wrong code. | Take the SNA code from column A, or read both columns and fail the build when they disagree. Then log the publisher's shifted column. Re-code the 8 series and fix the anchor. |
| verify-2 | **major** (consequence of verify-1) | **Issue mospi_nas_2026-13 is wrong for 3.0.** The 3.0 financial account closes exactly as published. The "−45,36,685 crore" non-closure is produced by the mis-coding, not by MoSPI. 6.0 (RoW) also closes, but the unit's closure test skips both 3.0 and 6.0, and the issues file gives no reason for 6.0: its totals are coded `f`, so the test's `net_acquisition_of_financial_assets` lookup finds nothing. | `test_oldbase_financial_accounts_close_in_raw` passes for all 12 NAS 2024 files. For 3.0 in 2022-23, net acquisition 51,86,891.9 − net incurrence 42,77,019.5 = 9,09,872.4 = B9 (financial) = B9 (capital), and it closes in every year 2011-12..2022-23 (≤1 crore). 6.0 closes likewise. | After verify-1, include s3_0 and s6_0 in `test_financial_account_matches_capital_account` (map 6.0's `f` totals). Remove the 3.0 clause from issue -13. The 1.15 capital-account and net-saving clauses are genuine: raw 1.15 notes 1-2 say so. 5.0 has no note of its own; the 1.15 note is the one cited. |
| verify-3 | minor | **I3a is declared `extent: full` but only 6 NAS sectors are official.** Gap-map I3a is 'CIS financed by each institution' for all `K_*` accounts. Its method says the FC sub-sectors and the Centre/State split are *estimated*. | The arithmetic itself checks: 2023-24 sector CIS (1.14 GCF − 1.11 GFCF) = 1,10,897 + 2,56,383 + 0 + 8,486 + 5,630 + 932 = 3,82,328, against 1.1 CIS 3,82,329 and 7.2A+B+C 3,82,329. | Change I3a to `partial` / `control_total`. The builder's "18 covered" becomes 17. |
| verify-4 | minor | **The "Less …" sign convention is undocumented.** Items published with a 'Less' caption are stored positive, as published. New base: 1.1 'Less Subsidies on Products' and 'Less Imports'; 1.9 'Less Financial liabilities#'; 1.1/8.17.1 import shares. Old base: P2, P51c, D3, D31, D9p. This is correct, but neither the module docstring nor the issues file says so, and item codes such as `subsidies_on_products` and `imports` hide the 'Less'. | Every such value equals the positive raw cell (census). The 1.9 household identity holds only with a minus: 36,02,199 − 19,09,287 + 40,25,292 + 1,72,127 = 58,90,330. | Add an issues row, and a sentence in the dataset descriptions: 'Less'-captioned items are stored as positive magnitudes and must be subtracted. |
| verify-5 | minor | **Dimension conventions.** 4.1 State rows have `geography=IN` and no institution; the State is only in `item_code` (`s4_1.andhra_pradesh`). PIPELINE_GUIDE §5 uses `IN-XX` for States. 1.9 and 1.11 sector rows carry the sector only in `item_code`, while 1.14 uses the `institution` column. | `s4_1` has 31 State series, all with geography IN. `s1_9` and `s1_11` have no institution values. | Tag 4.1 States with `geography=IN-XX` (plus institution gg, or `dim_other=level=state`). Fill `institution` in 1.9 and 1.11 using the codes 1.14 uses. |
| verify-6 | minor | **Old-base vintage dates cannot be checked.** 2024-06-05 (NAS 2024) and 2025-06-26 (NAS 2025) come from the MoSPI CMS listing. The sidecars' `Last-Modified` for the NAS 2025 files is 16 May 2025 10:17 GMT, before the claimed 26 Jun 2025 publication. The Phase 0 "migration stamp" explanation can't hold for a publication that didn't exist yet. | `data/raw/mospi_nas_old_base_2011_12/2026-09-29/mospi_nas_2026/nas2025_*.xlsx.meta.json`. The listing JSONs have no usable `published_date`. | Record in issue -9 (or the provenance notes) that the old-base vintage is the CMS listing date and contradicts the file timestamps. Values are unaffected. |
| verify-7 | minor | **The K7a "Phase 1 check" is not recorded.** The gap map asks for a Phase 1 check that PPF is not in both 'PF & pension' and 'small savings etc.' (5.3). No test or issues row mentions it. | `grep -i ppf` finds nothing in the issues file, tests or coverage. | Log it as open (it needs the S&M household-saving source table or an NAD answer), or record the check. |
| verify-8 | minor | **The builder's report miscounts the old-base sequences.** It says 7,408 rows for the 12 datasets; the actual count is 6,908. The report's total (26,805) and the issues file (9,049 old-base values) are right. | The datasets hold 912+565+553+396+541+520+593+585+551+624+600+468 = 6,908 rows. | None (report typo). |

## Claims re-verified (true)

- **Values.** All 64 NAS 2026 statements, plus 12 NAS 2024 and 4 NAS 2025 old-base statements, match raw (census). The template's 1.1 and 8.17.1 also match, including the 2025-26 PE and the 8.17.1 share rows.
- **Scale.** Money is ₹ crore as published (`conversion=none`). Population is 1,395.478 million → 1,395,478,000 `count`. Per-capita GDP 2023-24 = 2,90,73,287 crore / 1,395.478 mn = ₹2,08,339 ✓.
- **Periods.**
  - 7.4x is 'as on 31st March (at current prices)' (title row 2): headers 2023/2024/2025 → `2023-03-31`…`2025-03-31` ✓.
  - 8.18.x quarters are fiscal: Q1 2022-23 … Q4 2025-26 ✓.
  - 4.2's years come from the sheet names ✓.
  - Stages: 2022-23 and 2023-24 Final, 2024-25 FRE, 2025-26 PE, as in the NAS 2026 press release ✓.
- **Bases.** Old-base rows are all base 2011-12, price basis current or constant_2011_12, source `mospi_nas_old_base_2011_12`. New-base rows are all 2022-23, and no dataset mixes the two. The 2022-23 level break is new 2,61,77,001 vs old 2,68,90,473 = −2.65% ✓.
- **F4 arithmetic** (gap map). 7.1A total GVA 2022-23 = 42,32,624 = 12,58,014 (NFC public) + 6,45,812 (FC public) + 23,28,798 (GG). This holds exactly for 2022-23 and 2023-24, and 7.1B − financial = 1.14 private NFC.
- **D1 and D3** (derived) recompute exactly from raw. **D2**: 6.1 item 18 = 2,12,499. **D4**: 1.1 discrepancy 2023-24 = 0.
- **Access (D1-1, D1-2).**
  - All 84 sidecars show host www.mospi.gov.in and status 200.
  - Request headers are browser-like only: no Cookie or Authorization.
  - No network code outside `ctx.fetch`, and no challenge handling.
  - Sources are `mospi_nas_2026_publication` and `mospi_nas_old_base_2011_12` only, with no microdata.
  - The NAS API is blocked by TLS policy and is logged as FR-1, with no workaround in the code.

## Not verified / out of scope

- The NAS API long history (blocked, issue -6). No data exist to check.
- `repro` was not re-run.
