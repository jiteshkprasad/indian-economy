# state_fiscal: independent verification

Verifier: an adversarial agent that did not build the unit (SPEC rule 3). The regression test re-parses the pinned raw files with its own code and does not import `pipeline.ingest.state_fiscal`.

The latest pass, the **Final pass** (verify-13 fix and the S9 declaration), is at the **end** of this file.

# Second pass (2026-09-29): confirming the fixes for verify-1 to verify-9

## Verdict

**Accepted.**
- The major item (verify-1, Statement 36 partial total) is fixed and documented correctly.
- No regression was found in any value: all 166,316 clean values match the raw files (0 mismatches).
- All three documentation items are new:
  - **verify-10 (minor):** a stale undivided-AP figure sits inside two C.8.a aggregates.
  - **verify-11 (info):** Andhra Pradesh's Statement 36 figure for 2022-23 repeats 2021-22.
  - **verify-12 (cosmetic):** some notes name AP_un as not compiled after it had ceased.

## What was run

| Step | Result |
|---|---|
| `fetch state_fiscal --offline` | OK, 28 pinned raw files |
| `build state_fiscal` (offline) | OK: 11 datasets, 166,316 rows (KFI 33,916) |
| `test tests/units/test_state_fiscal.py` | 45 passed |
| `test tests/verify/test_state_fiscal_spotcheck.py` | 25 passed, 1 xfailed (strict: verify-10) |
| `test -k state_fiscal` | 146 passed, 1 xfailed (the same) |
| `coverage state_fiscal` | 20 refs, none BROKEN. No coverage entry cites a KFI series or period that is flagged INCOMPLETE. |
| `repro state_fiscal` | **REPRO OK**: 13 files byte-identical, and they match the manifest |

## Fix-by-fix confirmation (all checked against raw by the verifier's own parser)

| Finding | Confirmed? | How |
|---|---|---|
| verify-1 St 36 partial total | **Yes** | 1. For all 8 columns, the All States and UTs total equals the sum of the reporting States (±1 crore). Every column has at least one '-' State.<br>2. The per-year '-' lists, read from raw, equal the provenance note exactly. The note begins 'PARTIAL TOTAL', and all 225 St 36 rows point to it.<br>3. The build now raises an error if the identity fails (`rbi.py` l.405-416).<br>4. The R18 and P9a coverage notes carry the caveat, with extent partial. Issue state_fiscal-19 is logged.<br>5. The shortfall in the issues file (MH 43,158.4 + AP 14,689.0 + UK 289.0 + AR 456.1 = 58,592.5) is correct.<br>Test: `test_statement36_partial_total_every_year_and_documented`. |
| verify-2 AP_un stocks after bifurcation | **Yes** | No AP_un row is dated 2015-03-31. The builder's correction is right: the C.8.a cell at 2015-03-31 was 55,536.02, not 0, and it repeats end-March 2014 (55,536). I declared that drop for the **AP_un block only** (`KFI_DECLARED_BLOCK_DROPS`), which is stricter than the builder's suggested `('c.8.a', 2015)` for every block. |
| verify-3 zero rule | **Yes** | The rule text in state_fiscal-3 was re-implemented independently, as a full reverse census of all 38,227 published KFI cells: it gives **exactly** the 33,916 clean keys. Zeros: 4,344 kept as nil, 4,091 dropped as not compiled. The only non-zero drops are the declared totals, except WB 2022-23, plus AP_un C.8.a 2015. WB 2022-23: A.11 = A.8 + A.9 + A.10 and B.11 = B.8 + B.9 + B.10 exactly. A.4.2.a is 0 and kept in 2019-20, 2022-23 and 2023-24. Test: `test_kfi_reverse_census_under_revised_rules`. |
| verify-3 incomplete totals | **Yes** | I derived the INCOMPLETE flags independently. Group rows: any existing member State not compiled. State rows: A.5, A.8, A.11, B.8 and B.11 built on a zero head. My derivation matches the unit's flags **row by row**: 397 rows, 0 under-flagged, 0 over-flagged. NEH membership (AR, AS, HP, MN, ML, MZ, NL, SK, TR, UK) was confirmed by sums. The flags reach back to 2011-12 for legitimate reasons: C.4-C.6, C.9 and the C.3 corpus are filled for only a few States each year; Punjab's public account is 0 in 2011-12 to 2016-17; Mizoram and Tripura B.10 are 0 in 2017-18 to 2021-22. Test: `test_kfi_incomplete_flags_match_independent_derivation`. |
| verify-4 K8e wording | Yes | The note now says 'cumulative ... received, not net of repayment'. |
| verify-5 GTR | Yes | 74 rows: gg_centre, geography IN, no counterparty, no dim_other (test extended). |
| verify-6 App. Table break | Yes | All 7 App. Table provenance records carry 'COVERAGE BREAK'. Issue state_fiscal-20. |
| verify-7, verify-9 | Yes | Logged (state_fiscal-4b, state_fiscal-12). |
| verify-8 local-body scope | Yes | The `_datasets.json` description says 'minor heads 191-198 only; excludes MH 3604'. |

**The builder's edits to this spot-check file were reviewed and accepted.** It removed the 3 strict-xfail markers because those defects are fixed. It changed `('a_4_2_a','2019-20') not in` to `== 0`, which is consistent with the fixed rule and stricter. Neither weakens a check.

## New findings (second pass)

| # | Severity | Finding | Suggested fix |
|---|---|---|---|
| verify-10 | minor | **The KFI All_States and non-NEH C.8.a (maximum amount guaranteed) at end-March 2015 include undivided AP's stale 55,536.02.** The 28 States alone sum to 5,38,623.06, and that already includes AP's 11,322.94 and Telangana's 21,240. The published All_States figure, 5,94,159.08, is that sum plus the AP_un cell, so AP's guarantees are counted twice and the aggregate is overstated by about 10%. The series falls to 4,94,329 at end-March 2016. The unit now drops the AP_un row but keeps both aggregates. Their INCOMPLETE note names only HR, JH and NL as not compiled, not the stale AP_un part. | Add to those two rows' note: 'includes undivided AP's end-March 2014 figure (55,536) as well as AP and TS; 28-State sum 5,38,623.06'. Or drop the two aggregates. Pinned by `test_kfi_c8a_2015_aggregate_includes_stale_undivided_ap` (source fact) and a strict xfail, `test_kfi_c8a_2015_aggregate_note_names_undivided_ap`. |
| verify-11 | info | Statement 36 prints Andhra Pradesh subsidies of 14,689.0 for both 2021-22 and 2022-23. It is the only State whose two years are identical, so the 2022-23 figure is probably carried forward. FC16 sector subsidies for AP differ widely between the two years. The ~58,600 shortfall in state_fiscal-19 uses this figure. | Mention it in state_fiscal-19. Test: `test_statement36_andhra_2022_23_repeats_2021_22`. |
| verify-12 | cosmetic | Some INCOMPLETE notes list AP_un as not compiled at dates after it ceased, e.g. the C.3 corpus at end-March 2015. AP_un C.10 GSDP is kept for 2015-16 to 2023-24. It equals AP + TS exactly (tested), so it is a territorial series, not an error. But a sum over State rows that ignores `dim_other` would double count it. | Optional: leave AP_un out of 'not compiled' lists after 2014-15. A Phase 2 reader must filter on `boundary=undivided`. |

## Access (D1-1/D1-2/D1-4), second pass
- `sources.py` (16:18) and all 28 `.meta.json` sidecars (15:48-16:10) are unchanged since the first pass.
- No fetch-code file contains a login, cookie, captcha or GSTN/CBDT pattern.
- The first-pass conclusion therefore stands.

## Counts (second pass)
Every clean row of all 11 datasets was compared with its raw cell by label: **166,316 values, 0 mismatches**. For the three derived datasets, the comparison is with an independent re-aggregation.
- The 31 PDF values (PRI Chapter II) are re-extracted with pypdf and checked against values typed from the page text.
- The KFI reverse census adds 38,227 raw cells, each checked for presence or absence under the stated rules.

---

# First pass (2026-09-29)

## Verdict

**Accepted, with one major item for the issues file and several minor fixes.**

- All 164,780 clean values match the pinned raw documents: 0 mismatches in a full census across all 11 datasets.
- The three derived datasets were re-aggregated independently and match exactly.
- The two source errors the builder found are real:
  - App. Table 2 repeats 2022-23 values in the 2023-24 (Accounts) column (state_fiscal-5).
  - KFI prints 0 where debt flows were not compiled (state_fiscal-3).
- Fetch code and meta sidecars comply with D1-1, D1-2 and D1-4.

The major item (verify-1) is a gap in the source that the unit does not log. The RBI Statement 36 "All States and UTs" subsidy total for 2023-24 (3,29,610) leaves out Maharashtra, Andhra Pradesh and four other States. The coverage file nonetheless presents it as the States' total for R18 and P9a.

## What was run

| Step | Result |
|---|---|
| `fetch state_fiscal --offline` | OK, 28 pinned raw files |
| `build state_fiscal` (offline from pins) | OK: 11 datasets, 164,780 rows (row counts as reported by the builder) |
| `test -k state_fiscal` | 133 passed, 3 xfailed (the 3 xfails are the verifier's strict-xfail defect markers below) |
| `test tests/verify/test_state_fiscal_spotcheck.py` | 17 passed, 3 xfailed (strict) |
| `coverage state_fiscal` | 20 refs, none BROKEN. OFFICIAL: T2 and R1 covered; R2, R3, R7 and R9 partial |
| `repro state_fiscal` | **REPRO OK**: 3 builds byte-identical and matching `data/manifest.json`. The builder's failure (state_fiscal-18) came from the parallel `code_hash` race and can be closed. |

## Method (`tests/verify/test_state_fiscal_spotcheck.py`)

- **Independence.**
  - Every XLSX is read with python-calamine cell grids. The unit uses openpyxl, or polars for the two large FC16 dumps.
  - The PRI Chapter II PDF is read with pypdf. The unit uses pdfplumber.
  - Clean parquet files are read with pyarrow.
  - Each raw file's sha256 is re-checked against `data/raw_pins/state_fiscal.yaml`.
  - The verifier wrote its own State-name/ISO map, FC16-code map (CH = Chhattisgarh), RBI period-header reader and number parser.
- **Matching** is always by label (item text, State name, printed year header), never by row position.
  - KFI blocks are matched by header and years by label: '2024' = FY 2023-24; stocks use end-March of the label year.
  - Appendices I-IV are matched by label. A label printed over two lines is joined with the next line. A label printed more than once, such as '4. Others' three times in App. III or the App. IV social-services items under both outlay and loans, is checked by its full four-period vector against every raw occurrence.
  - PRI appendix items are keyed by their parent number, because '(iii) Other Expenditure' appears under both 13 and 24.
- **Census in both directions.** Every clean row is matched to its raw cell, and every published raw cell must have a clean row. The only exceptions are the unit's declared exclusions, and each is checked:
  - KFI: 5,624 zero cells are dropped. 223 non-zero cells are dropped, all of them the declared incomplete totals A.5, A.8 and B.8 (2023-24), A.10 and B.10 (2022-23), and A.11 and B.11 (both years).
  - App. T2: 6 cells for 2023-24 (Accounts), rows III-VI. The test proves that III, V, V(a) and V(b) equal their 2022-23 values exactly.
  - App. T2: the column printed '2023-24 (Budget Estimates)'.
- **Derived datasets are recomputed from raw.**
  - `fc16_state_accounts` and `fc16_local_body_assistance`: 550,775 minor-head rows re-summed with `math.fsum`, then lakh ÷ 100.
  - `ulb_cityfinance`: 37,866 ULB-year rows re-summed, rupees × 1e-7, with a ULB count per item. The test also checks that exactly the balance-sheet columns 39-48 are stocks, and checks the "rupees" magnitude on Khategaon (11.9 crore).
  - Independent check of the builder's reconciliation claim: 2023-24 major-head sums reproduce KFI revenue receipts and capital expenditure for all 28 States (56 totals) and SGST 8,00,112.02.
- **PDF.** All 31 PDF-derived values (Tables II.1, II.2, II.3 and II.5) were read from the page text, typed into the test by hand, and are also re-extracted with pypdf. Both must agree with each other and with the clean rows.
- **Anchors.** The test pins the gap-map-critical 2023-24 figures:
  - KFI: SGST 8,00,112; VAT 3,97,467; State excise 2,49,133; vehicles 1,06,021; stamps 2,20,289; devolution 11,29,397; grants 4,72,466; GST compensation 43,788; interest 4,94,911; pensions 4,94,939.
  - FC16 transfers: grants (Statement 18) 7,39,260.
  - RBI: Statement 13 interest 5,07,175.4; Statement 17 gross transfers 18,00,210.2; Appendix I SGST 8,41,120.8; Appendix IV capital outlay 7,47,306.
- A seeded sample (seed 20260929, 3 rows per dataset) is printed. Five of them were compared by eye with the raw sheets, e.g. Municipal St 4 UP 2019-20: 4,51,144 lakh = 4,511.44 crore.

| Dataset | Values compared | Mismatched |
|---|---:|---:|
| fc16_kfi | 32,380 | 0 |
| fc16_transfers | 801 | 0 |
| fc16_subsidies | 1,738 | 0 |
| fc16_state_accounts (derived, recomputed) | 101,613 | 0 |
| fc16_local_body_assistance (derived, recomputed) | 2,523 | 0 |
| ulb_cityfinance (derived, recomputed) | 21,006 | 0 |
| rbi_sf_statements | 1,176 | 0 |
| rbi_sf_app_tables | 1,252 | 0 |
| rbi_sf_appendices | 1,280 | 0 |
| rbi_municipal | 779 | 0 |
| rbi_pri (incl. 31 PDF values) | 232 | 0 |
| **Total** | **164,780** | **0** |

## Systematic-error hunt

| Check | Finding |
|---|---|
| **Scale** | RBI Appendices I-IV and Municipal Statements are Rs lakh → ÷100: correct. The ULB dump is rupees → ×1e-7: the magnitude is plausible. PRI appendices are Rs per panchayat, kept in INR. KFI has no caption, but it is crore: KFI SGST equals the accounts-dump lakh sum ÷ 100 to 0.01. FC16 transfers are crore: the 2023-24 grants of 7,39,260 match Union Statement 18. |
| **Year labels** | KFI and the accounts dump both use '2024' = FY 2023-24: GST is zero through label 2017, and GST loans appear only under labels 2021-22. Their 2023-24 sums reconcile exactly with each other. App. T11 years are end-March dates, and '2026 BE' = 2025-26 BE. RBI "(Accounts)" is tagged Actuals. |
| **Stocks vs flows** | KFI C.1/C.2/C.3/C.5/C.8 are dated stocks; C.4 "Total Debt Receipts", C.5 "Repayments", C.6 and C.9 are flows. ULB columns 39-48 are stocks. All correct. |
| **Aggregates** | KFI All_States = Σ 28 States (+ AP_un in 2014-15) for every item and year except C.10 (India GDP, as documented). Group rows carry `dim_other`, so they are not double counted by geography. |
| **Sign conventions** | Stored as published. KFI deficits are negative (D.1 −1,03,369); RBI App. T1 deficits are positive, with the "negative = surplus" note in provenance. Users must not mix them without flipping the sign. |
| **Provenance** | 36 records. Locators, units and conversions are correct. Rows from summed data are `derived` and have a method. The vintages equal the listing release dates (SF 23 Jan 2026, Municipal 13 Nov 2024, PRI 24 Jan 2024) or the FC16 Last-Modified dates. |
| **Access (D1-1/D1-2/D1-4)** | All 28 sidecars show status 200 on the first attempt, no redirects, and no cookie or authorization headers. The 19 rbidocs requests were 10-14 s apart, and the PDF was requested in a later run. `sources.fetch_all` makes one attempt per file and stops rbidocs at the first `AccessBlocked`. There is no challenge solving, login, GSTN/CBDT source or microdata; the ULB dump is per-body government accounts. |

## Findings

| # | Severity | Finding | Suggested fix |
|---|---|---|---|
| verify-1 | **major** | **RBI Statement 36 "All States and UTs" subsidies for 2023-24 (3,29,610) is only the sum of the reporting States.** Maharashtra, Andhra Pradesh, Arunachal, Goa, Uttarakhand and J&K print '-' for 2023-24; their 2022-23 values include Maharashtra 43,158 and AP 14,689. The printed total equals the sum of the reporting States exactly (tested), so it understates by roughly 60,000 crore and breaks the comparison with 2022-23 (3,53,225). `coverage.yaml` cites 3,29,610 as "States' total subsidies" for R18 and P9a without a caveat, and the issues file does not mention it. | Log it in the issues file. Reword the R18/P9a coverage notes. Phase 2 must fill the missing States, e.g. from FC16 sector subsidies (which cover MH and AP) or Finance Accounts. Test: `test_statement36_all_states_2023_24_is_partial`. |
| verify-2 | minor | KFI undivided AP (AP_un) is ingested with 0 stocks at 2015-03-31 for C.1, C.1.1, C.2, C.2.1, C.2.5, C.3, C.3.a, C.5 and C.8 (9 rows). The 'alive' rule reads the FY 2014-15 flows (April-June 2014 before bifurcation). After bifurcation the block has no balance sheet, so these zeros mean "not applicable", not zero debt. | Drop AP_un stocks after 2014-06-02 (i.e. 2015-03-31). Strict xfail: `test_kfi_no_zero_stocks_for_undivided_ap_after_bifurcation`. |
| verify-3 | minor | **The KFI zero rule is broader than its reason.** The prefix regex (`a_4`, `b_6`, …) drops true zeros in years that were compiled: GST loans A.4.2.a before 2020-21 and after 2021-22 (364 cells), SASCI A.4.2.b before 2020-21, and WMA rows for States without WMA. After this rule, "no row" can mean either nil or not compiled. `KFI_INCOMPLETE` also drops West Bengal's apparently genuine A.10 and B.10 for 2022-23, since WB is the only State compiled. At the same time, C.8.a (maximum amount guaranteed) for 2022-23 is kept: most States are 0 that year, yet the All_States 2,42,793 (6,55,322 the year before) is ingested as complete. | Drop zeros only in years whose parent total (A.4/B.6) is 0. Keep per-State values where a State was compiled. Treat the C.8.a 2022-23 aggregates like A.10. Strict xfail: `test_kfi_gst_compensation_loan_nil_2023_24_is_kept`. |
| verify-4 | minor | The K8e coverage note calls KFI C.1.2.a "outstanding GST back-to-back loans at end-March 2024 (2,49,191)". The row is labelled "(cum)" and stays at 2,49,191 at end-March 2022, 2023 and 2024. It is cumulative loans received, so it cannot reflect the 78,104 recovered in 2023-24 that K8e is about. KFI itself removes it from liabilities (C.3.a = C.3 − C.1.2.a). | Reword the coverage note to "cumulative back-to-back loans received". |
| verify-5 | minor | The FC16 transfers series `tsm.gtr` (the Union's gross tax revenue, 34,65,519 in 2023-24) is tagged `institution=gg_state` and `state_group=all_states`. | Tag it `gg_centre` with no state group. Strict xfail: `test_fc16_gtr_is_tagged_as_union`. |
| verify-6 | minor | RBI App. Tables 1, 2, 3, 9 and 11 add Delhi and Puducherry from 2017-18 (the sheet notes say so). The whole series is labelled `all_states_uts`, and the coverage break is not in the issues file or the provenance notes. | Log it and add a provenance note. Phase 2 time series should splice at 2017-18. |
| verify-7 | minor | KFI C.3.a is labelled "(C.3+C.1.2.a)", but for all 104 non-zero cases the data equal C.3 − C.1.2.a (tested). This is the same kind of mislabel as D.2 (state_fiscal-4), but it is not logged. | Log it next to state_fiscal-4. |
| verify-8 | minor | `fc16_local_body_assistance` holds minor heads 191-198 only. It excludes MH 3604 (compensation and assignments to local bodies; KFI B.1.4 = 1,14,381 in 2023-24). | Say this in the dataset description, so no one reads the dataset as total transfers to local bodies. |
| verify-9 | info | Source inconsistency in RBI PRI: revenue receipts per panchayat for 2020-21 are 2,117 thousand in Table II.3 but 22,02,057 in Appendix I. 2021-22 and 2022-23 agree. The unit does not ingest the Table II.3 averages, so no clean value is affected. | Mention it in state_fiscal-12. |

**Confirmed builder claims**

| Issue | What was confirmed |
|---|---|
| state_fiscal-2 | Year labels. |
| state_fiscal-3 | The zero pattern is as described. The rule it motivates is too broad; see verify-3. |
| state_fiscal-4 | D.2 identity. |
| state_fiscal-5 | Stale App. T2 rows. Also St 17 gross = I + II + App. III ii (1,42,517.7). |
| state_fiscal-6 | The mislabelled column. |
| state_fiscal-10 | The accounts dump reproduces KFI. The 196 exact duplicate rows are small; the CH 2023-24 duplicates total 263 crore, and the CH totals still match KFI exactly, so summing them is right. |
| state_fiscal-13 | Municipal Andhra Pradesh rows present. |

**Can be closed:** state_fiscal-18 (repro OK). state_fiscal-14 can be closed too: the listing shows 23 Jan 2026 as the release date, and the guide defines vintage as the release date.

---

# Close-out pass (2026-09-29): D1-9 code map, undivided AP and J&K, verify-10 and verify-12

## Verdict

**Accepted.** The builder's summary is accurate on every point I could test.
- **Values:** all 11 datasets were compared row by row with the committed build (HEAD). Only geography, series ids and provenance changed. No value, period, unit or other dimension moved.
- **Censuses:** all 166,316 clean values still match raw (0 mismatches).
- **Geography:** every State row's code now matches the verifier's own territory calendar.
- **Fixes:** verify-10 and verify-12 are fixed and pass as ordinary tests; the strict xfail was removed.

There are three new items. None of them affects a value.
- **verify-13 (cosmetic):** 12 rows outside their territory's lifetime have no reason in their provenance.
- **verify-14 (minor):** the state_fiscal-16 re-check says no unit has pinned or ingested Expenditure Budget Statement 6. That is no longer true.
- **verify-15 (cosmetic):** two wording nits.

## What was run

| Step | Result |
|---|---|
| `test tests/verify/test_state_fiscal_spotcheck.py`, before any edit | 23 passed, 3 failed: KeyError 'IN-XJK' twice, and XPASS(strict) for verify-10. Exactly as the builder described in state_fiscal-24. |
| same, after this pass | **31 passed, 1 xfailed** (strict: verify-13) |
| `test tests/units/test_state_fiscal.py` | 51 passed |
| `test -k state_fiscal` | 158 passed, 1 xfailed |
| `test tests/hygiene` | 26 passed |
| `coverage state_fiscal` | no BROKEN refs |
| `repro state_fiscal` | **REPRO OK**: 13 files byte-identical across PYTHONHASHSEED 0/1 and 1/4 threads; they match `data/manifest.json` |
| row-by-row diff against the HEAD parquets (my own script) | For all 11 datasets, the multiset of rows is identical once geography, series_id and prov_id are ignored. |
| `ruff check` on the spot-check | 1 finding, the same pre-existing line as HEAD |

**Geography changes against HEAD.** These include the framework's earlier CT to CG change.

| Code change | KFI | Accounts | Local-body | Subsidies | RBI St | Municipal | ULB |
|---|---:|---:|---:|---:|---:|---:|---:|
| IN-CT to IN-CG | 1,142 | 2,117 | 140 | 79 | 38 | 30 | 738 |
| IN-AP to IN-XAP | 337 | 2,493 | 125 | | | | |
| IN-JK to IN-XJK | | 961 | 7 | | | | |

The CT to CG total is 4,284 rows, which matches FRAMEWORK_REQUESTS.md. Provenance records went from 138 to 140.

## Edits to the verifier-owned spot-check

Every changed expectation was re-derived from the raw files. No check was loosened.

1. **Undivided AP and J&K geography (state_fiscal-24).**
   - **Before:** the census mapped a clean row back to its FC16 block using `dim_other` or `ISO2FC16`. It therefore never checked the code itself, and it failed with a KeyError on `IN-XJK`.
   - **Now:** `_state_block` checks each code against the verifier's own calendar (`TERR_FROM`/`TERR_TO`, `fc16_geo_expected`):
     - 'AP_un' must be `IN-XAP`, and the `boundary=undivided` marker must be on exactly those rows.
     - FC16 'JK' must be `IN-XJK` for years ending by 30 Oct 2019 and `IN-JK` for years starting after it. A straddling J&K year fails.
   - The calendar comes from the appointed days of the reorganisation Acts. `test_territory_calendar_matches_geo_module_text` cross-checks it against `pipeline/core/geo.py`, read as text rather than imported.
   - **Mutation check:** each old coding is rejected: `IN-AP`+undivided, J&K 2018-19 as `IN-JK`, a UT year as `IN-XJK`, and `IN-XAP` without the marker.
   - This is stricter than the builder's suggested one-line fix, which was to add `"IN-XJK": "JK"` to `ISO2FC16`.
2. **verify-10.**
   - The strict xfail is removed from `test_kfi_c8a_2015_aggregate_note_names_undivided_ap`.
   - The test now requires the note to carry the total, the live-member sum and the stale cell, all re-derived from raw: All_States (594,159.08) = (538,623.06) + 55,536.02; non-NEH (579,546.56) = (524,010.54) + 55,536.02.
   - It also requires that C.8.a is the only undivided-AP stock that is non-zero at end-March 2015, and that no other row carries the 'STALE UNDIVIDED' note (the NEH C.8.a row does not).
3. **state_fiscal-22 (the framework's one-token IN-CT to IN-CG edit to this file): reviewed and re-signed.**
   - IN-CG is the current ISO code under D1-9. geo.py lists IN-CT as superseded; this is now asserted from the text.
   - All 4,284 Chhattisgarh rows are covered by the censuses, and 425 of them by the new second-path sample.

## New checks

| Test | What it proves |
|---|---|
| `test_geography_codes_match_territory_calendar` | Every row in all 11 datasets uses a known code. Every row whose period is not inside its territory's lifetime is one of the verifier's own expected cases (below), and every expected case occurs, so the unit's `TERRITORY_DECLARED` is exact. The 18 GSDP rows carry the new records: SUCCESSOR-TERRITORY for AP/TS FY 2011-12 to 2014-15; TERRITORIAL AGGREGATE for IN-XAP FY 2014-15 to 2023-24. No IN-XAP stock is dated after end-March 2014, and no AP/TS stock before end-March 2015. |
| `test_kfi_incomplete_notes_name_exactly_the_existing_uncompiled_blocks` (verify-12) | For all 397 INCOMPLETE rows, the blocks named as 'not compiled' equal my independent derivation, which counts only blocks that exist on that date. AP_un is still named for the FY 2014-15 flow memo rows (C.4, C.5, C.6, C.9), which is right: its accounts cover 1 April to 1 June 2014. It is not named for any stock dated after end-March 2014. |
| `test_fy_2000_01_partial_years_by_magnitude` | The builder's FY 2000-01 inference, from raw revenue receipts: UK 924 vs 2,608 the next year, JH 1,964 vs 4,444, UP 25,598 vs 27,821. Undivided AP's FY 2014-15 is about 2 months: 24,977 vs 1,10,719 a year earlier, with AP 65,695 and TS 51,042 covering the rest. The dump has J&K for FY 2013-14 to 2018-19 and 2020-21, with no 2019-20. |
| `test_changed_rows_seeded_sample_against_raw` | For each group of changed rows, max(10%, min(30, n)) rows were drawn with seed `20260929:<group>`: **865 of 7,461 rows (11.6%), 0 mismatches.** They were re-derived by a **second path**: direct cell addressing in the calamine grid (KFI, subsidies, Municipal, St 36) and Decimal sums over the raw minor-head rows (accounts). Groups: KFI IN-XAP 34/337, IN-CG 115/1,142, new KFI records 15/15; accounts IN-XAP 250/2,493, IN-XJK 97/961, IN-CG 212/2,117; local-body IN-XAP 30/125, IN-XJK 7/7, IN-CG 30/140; subsidies IN-CG 30/79; Municipal IN-CG 30/30 and J&K 2019-20 6/6; St 36 IN-CG 8/8 and J&K 2019-20 1/1. Each sampled row's series-id suffix was also checked (`.in-xap.undivided`, `.in-xjk`, `.in-cg`). |
| `test_every_out_of_lifetime_row_states_the_reason` | Strict xfail for verify-13, below. |

**Expected out-of-lifetime rows** (the verifier's own list):
- KFI: AP and TS GSDP for FY 2011-12 to 2013-14 (before either State existed); every AP, TS and undivided-AP row for FY 2014-15 (straddles 2 June 2014); undivided-AP GSDP for FY 2015-16 to 2023-24 (after it ceased).
- Accounts: undivided AP, AP and TS for FY 2014-15; UP, UK and JH for FY 2000-01.
- Local-body assistance: undivided AP, AP and TS for FY 2014-15; UP and JH for FY 2000-01.
- RBI St 36 and Municipal Finances: J&K FY 2019-20 (straddles 31 Oct 2019).

## Builder claims re-checked

| Claim | Result |
|---|---|
| Undivided AP is `IN-XAP` (337 KFI, 2,493 accounts, 125 local-body rows); former J&K is `IN-XJK` (961, 7); the UT's 2020-21 accounts stay `IN-JK` | Confirmed by count, and for every row against the verifier's calendar. |
| Every value and non-geography dimension is unchanged | Confirmed: multiset equality with HEAD for all 11 datasets. |
| KFI GSDP successor and territorial records | Confirmed. AP + TS = undivided AP exactly for all 13 years, from raw (the reverse census). |
| verify-10 notes and the build identity | Confirmed from raw (above). |
| verify-12: flags unchanged at 397, only the 2 C.3 notes changed | Confirmed. The HEAD vs current diff of INCOMPLETE records shows only 'AP_un' removed from the two C.3-corpus end-March 2015 notes, plus the 'STALE' sentence on the two C.8.a records. The other INCOMPLETE records only gained the ', state_fiscal-23' reference. |
| Territory guard with declared exceptions | Confirmed. The declarations equal the verifier's independent list, and `repro` passes with the guard. |
| FY 2000-01 partial years inferred from magnitudes | Confirmed from raw. The note says the attribution is inferred ('by magnitude'), so it is honest. |
| J&K FY 2019-20 kept as `IN-JK` with a note | Acceptable. St 36 has J&K 700 for 2019-20 and '-' elsewhere through 2022-23. Municipal J&K is municipal corporations only (Srinagar, Jammu), and both lie inside the UT. |
| state_fiscal-16: no capital-asset or capital-grant head in the dump; MH 1601 2023-24 split | Confirmed. 0 of 550,775 rows match capital asset, creation of capital or capital grant. MH 1601: 06 = 2,62,868.08; 07 = 1,44,958.97; 08 = 64,377.44; 01-04 = 261.38; total 4,72,465.88 (KFI A.1.4 4,72,465.87, a rounding difference). |
| state_fiscal-16: "no unit has pinned a new file that serves these refs (no Expenditure Budget Statement 6 in any `data/raw_pins/*.yaml`; union_fiscal-13 still lists it as not ingested)" | **Not true now.** See verify-14. |
| Recon and coverage are unaffected | Confirmed. RECONCILIATION GOV-5 uses `st13...in-jk` for 2023-24, which is still the UT. The TAX-6 regex `in-[a-z]{2}$` cannot pick up `in-xap` or `in-xjk`, and 2023-24 has neither anyway. No coverage entry cites an AP_un or J&K series. |
| (series_id, period, stage) keys | Unique in all 11 datasets. No series id spans two geographies. |

## New findings (close-out pass)

| # | Severity | Finding | Suggested fix |
|---|---|---|---|
| verify-13 | cosmetic | **12 rows outside their territory's lifetime have no reason in their provenance**, although the guard's docstring says it must be stated there. They are 9 KFI E.* ratio rows (AP, TS, IN-XAP × E.1-E.3, FY 2014-15; the ratio record has no notes) and 3 Municipal per-cent-of-GSDP rows for J&K FY 2019-20 (the J&K note went on the level record only). The E ratios are within-period ratios (e.g. interest/revenue receipts), so no GSDP mismatch arises. The undivided-AP ones cover about 2 months. | Add the territory sentence to the ratio record and to the Municipal pct record, or have `territory_problems` check the notes. Strict xfail: `test_every_out_of_lifetime_row_states_the_reason`. |
| verify-14 | minor | **The state_fiscal-16 re-check is stale.** union_fiscal pins Expenditure Budget Statement 6 ('Allocation under the object head Grants for Creation of Capital Assets') for three budgets (`b2425/b2526/b2627_stat6.xlsx`, retrieved 14:33 UTC today) and ingests it as `union_fiscal_gcca` (union_fiscal-22). It also ingests the audited IGAS-2 appendix as `union_fiscal_fa_gia`: grants to State Governments for creating capital assets, 1,19,435.32 crore in 2023-24. union_fiscal-13 now lists Statement 6 as ingested, and `union_fiscal_coverage.yaml` cites fa_gia and gcca for **K6** and **R2k** (partial / control_total). So "no unit serves these refs" and "no Statement 6 in any raw_pins" are both wrong as of this build (probably a same-hour race between the two units). No state_fiscal value is affected. | Reword state_fiscal-16: K6 and R2k have Union-side partial coverage in union_fiscal (fa_gia by grantee, gcca by scheme). What stays open is the State-side counterpart (the State sources split Centre grants by scheme type, not capital/current) and F4b. |
| verify-15 | cosmetic | (a) The TERRITORIAL AGGREGATE note says "for years after it was divided on 2 June 2014" but also covers FY 2014-15, which straddles the date. (b) Every INCOMPLETE record now cites state_fiscal-23, including ones that have nothing to do with undivided AP (e.g. the NEH C.8.a row). | Optional wording fixes. |

**Can be closed:**
- state_fiscal-22: the one-token CT to CG edit is reviewed and re-signed.
- state_fiscal-24: both requested edits are done, in a stricter form.
- state_fiscal-21 and state_fiscal-23: verifier re-check done.

state_fiscal-16 stays OPEN, reworded per verify-14.

## Counts (close-out pass)

| Check | Values | Mismatched |
|---|---:|---:|
| Full censuses, all 11 datasets (unchanged method, now with geography asserted against the calendar) | 166,316 | 0 |
| Second-path seeded sample of changed rows | 865 | 0 |
| INCOMPLETE notes, named blocks vs independent derivation | 397 | 0 |
| Territory classification, all rows | 166,316 | 0 unexpected; 12 without a stated reason (verify-13) |

---

# Final pass (2026-09-29): verify-13 fix and the S9 declaration

## Verdict

**Accepted.** verify-13 is fixed, and the S9 entry is correct.
- **verify-13:** confirmed. The strict xfail is removed, and the check now runs as an ordinary test that is stricter than before.
- **S9:** every figure and footnote in the entry was re-derived from the raw files and agrees.
- **Regressions:** none. Compared with the build before this pass, no value, period, geography, series id or other field moved.

Three cosmetic items are new (verify-16 to verify-18). None affects a value.

## What was run

| Step | Result |
|---|---|
| `fetch state_fiscal --offline` | OK, 28 pinned raw files |
| `build state_fiscal` (offline) | OK: 11 datasets, 166,316 rows, 140 provenance records. The build is byte-identical to the files on disk (all 13 compared). |
| `test tests/verify/test_state_fiscal_spotcheck.py`, before any edit | 31 passed, 1 failed: the expected XPASS(strict) of verify-13 |
| same, after this pass | **35 passed** (the converted test plus 3 new tests) |
| `test tests/units/test_state_fiscal.py` | 54 passed |
| `test -k state_fiscal` | 165 passed |
| `test tests/hygiene` | 26 passed |
| `coverage state_fiscal` | No BROKEN refs. S9 is OFFICIAL partial (OFFICIAL cells: 2 covered and 5 partial, of 7). |
| `repro state_fiscal` | **REPRO OK**: 13 files byte-identical across PYTHONHASHSEED 0/1 and 1/4 threads; they match `data/manifest.json` |
| `ruff check` on the spot-check | 1 finding, the same pre-existing line 330 as HEAD |

## verify-13 re-derived from raw (own parser: calamine grids)

**KFI, sheet 'State-wise', year column '2015' (FY 2014-15).**
- For AP, TS and AP_un, all three ratios hold exactly (difference 0.0):
  - E.1 = B.1.a / A.1
  - E.2 = (B.1.a + B.1.b + B.1.c) / A.1
  - E.3 = D.1 / D.2 (the same as D.1.a / D.2.a, because GST loans are nil in 2014-15)
- Example: AP_un E.1 = 2,090.95 / 24,977.05 = 0.0837149 (clean 0.083715).
- E.1 = B.1.a / A.1 holds in all 401 block-years with a non-zero A.1.
- The 9 clean values equal the raw ratios rounded to 6 decimals.
- So the ratios are within-block and within-year. The AP_un ratios describe 1 April to 1 June 2014, as its flows do.

**Municipal Statements 1, 4 and 8.**
- Row '11. Jammu and Kashmir', 'Per cent of GSDP', 2019-20 (Accounts): 0.09, 0.1 and 0.01 = the clean values.
- All 6 J&K FY 2019-20 records (levels and per cent) now carry the 31 Oct 2019 sentence.

**All out-of-lifetime rows.**
- 1,178 rows sit on 13 records.
- Every record states the reason with its specific dates: 2 June 2014 / 1 April-1 June 2014; 8, 9 or 15 Nov 2000; 31 Oct 2019; or the SUCCESSOR-TERRITORY or TERRITORIAL AGGREGATE heading.
- No row is silent.

**Guard mutation test** (scratch script; the unit's code was not edited):
- `territory_problems` with the notes passed reports the pre-fix ratio record (3 findings) and a Municipal per-cent record stripped of its J&K sentence (1 finding).
- It returns nothing on the current build.

## Regression hunt (current build vs HEAD, own script)

- **Datasets:** all 11 are equal as multisets once geography, series_id and prov_id are ignored.
- **Rows by key:** keyed on (series_id, period, stage), every row whose series id is unchanged is identical in every field except prov_id.
- **Series ids:** new series ids occur only for the known recodes. The counts match the close-out pass:
  - IN-CG: 4,284
  - IN-XAP: 2,955
  - IN-XJK: 968
- **Geography changes:** only IN-CT to IN-CG, IN-AP to IN-XAP and IN-JK to IN-XJK.
- **Provenance:** 140 records, against 138 at HEAD. Apart from notes and ids, the only additions are the 2 GSDP territory records from the close-out follow-up.
- **8 re-noted records:** the builder's count of 8 matches the records whose notes now carry the new sentences: the ratio record, 3 Municipal per-cent records, 3 Municipal level records and St 36.

## S9 (gross State GPF flows) re-derived from raw

RBI State Finances 2025-26, All States and UTs block, 2023-24 (Accounts), Rs lakh:

| Line | Receipts (App. III, sheet AP_3_T5) | Disbursements (App. IV, sheet 4APP_3) |
|---|---:|---:|
| 1. State Provident Funds | 1,03,89,237.1 (= 1,03,892.371 crore) | 91,39,849.3 (= 91,398.493 crore) |
| 2. Others | 1,58,75,757.5 | 1,50,63,292.9 |
| VI / VII, (1 + 2) | 2,62,64,994.7 | 2,42,03,142.2 |

- **Gross, not net: confirmed.**
  - App. III has two totals:
    - 'TOTAL CAPITAL RECEIPTS (I to XII)' is gross.
    - Only 'TOTAL CAPITAL RECEIPTS (Includes Public Accounts on a net basis)*' nets. Its footnote '*' says items IV to X, XII and I(4) are taken on a net basis.
  - App. IV's '$' total, 'Excluding Public Accounts', is items I to IV only, so item VII is outside it.
  - COVERAGE.md's remark that the RBI provident-fund lines are 'net public-account figures' is therefore wrong for these lines.
- **Clean and coverage:**
  - The clean rows equal raw ÷ 100 for all 4 periods, as flows in INR crore.
  - The two coverage series ids exist in the clean data.
  - The printed '(1 + 2)' sums hold.
- **Caveats in the coverage note:**
  - The J&K 'CAG, provisional' note is printed in both appendices.
  - Appendix II C.2.iii (54,183.144 crore, interest on small savings and State provident funds jointly) matches.
  - The Others figures quoted in the note match.
  - The '$ : State Provident Funds also includes other savings deposits' footnote is printed in App. III, but no label on the sheet carries the '$' marker. Quoting it as a caveat is the conservative reading.
- **FC16 accounts dump:** the builder's claim that it has no MH 8009 was covered by the earlier census of all 550,775 minor-head rows (major heads are revenue and capital heads only). It was not re-run here.

## Edits to the verifier-owned spot-check (`tests/verify/test_state_fiscal_spotcheck.py`)

1. **`test_every_out_of_lifetime_row_states_the_reason`:**
   - The strict xfail is removed, and the test is now an ordinary check.
   - It is stricter than before. Besides the generic reason marker, each of the 1,178 rows' records must carry the case-specific dates from the verifier's own calendar (`_territory_reason_expected`).
   - It also pins the 12 verify-13 rows by name.
   - **Mutation-tested** (scratch script that patches the provenance read). It fails on all three of:
     - the pre-fix ratio record (9 rows);
     - a Municipal per-cent record without the J&K sentence (1 row);
     - an accounts record reduced to a bare 'DECISIONS D1-9' citation (924 rows).

     The unit's guard accepts the last case.
2. **New `test_kfi_ratios_2014_15_are_within_block_from_raw`:** the E.1-E.3 identities above, the E.1 identity over all block-years, and clean = raw to 6 decimals.
3. **New `test_municipal_jk_2019_20_pct_rows_from_raw`:** the three per-cent rows from raw, and the 31 Oct 2019 note on all 6 records.
4. **New `test_s9_state_provident_funds_are_gross_lines_from_raw`:**
   - the anchors, the '(1 + 2)' sums and the period headers;
   - the '*' and '$' footnote texts, and the J&K CAG note;
   - the clean rows, and the S9 coverage entry (partial; exactly these two series; caveats present).

No check was loosened.

## New findings (final pass)

| # | Severity | Finding | Suggested fix |
|---|---|---|---|
| verify-16 | cosmetic | **Imprecise wording in notes and docstrings.** (a) The ratio record says each E.* ratio is "a ratio of two flows of the same block and year". E.2's numerator is three flows (B.1.a + B.1.b + B.1.c), and E.3 is D.1 / D.2 (balances). The within-block, within-year point, which is what matters, holds. (b) The S9 coverage note omits the "no State-wise split" caveat; it is in state_fiscal-25. (c) The docstring of the unit test `test_state_provident_funds_gross_flows` cites rows 39-41 and 21-23; the lines are rows 40-42 and 22-24 (1-based). | Optional rewording. |
| verify-17 | cosmetic | **The unit's guard checks that a reason is cited, not which one.** `TERRITORY_NOTE_MARKERS` accepts any record that contains 'DECISIONS D1-9'. The spot-check now enforces the specific dates, so a regression would still be caught. | Optional: key the marker to the declared reason (e.g. the date string in `TERRITORY_DECLARED`). |
| verify-18 | minor (docs, not this unit's file) | **COVERAGE.md is stale for S9.** Line 47 lists "gross State GPF flows" as missing. Line 58 calls the RBI SF provident-fund lines "net public-account figures". Row S9 (line 159) says "state_fiscal declares nothing for S9". All three are now wrong: `state_fiscal_rbi_sf_appendices` declares S9 partial with gross App. III VI.1 / App. IV VII.1. | For the integration owner of COVERAGE.md. |

**Can be closed:**
- state_fiscal-25(a): verify-13 is fixed, and the verifier action (removing the strict xfail) is done.
- state_fiscal-25(b): the S9 declaration is verified. S9 stays partial.
