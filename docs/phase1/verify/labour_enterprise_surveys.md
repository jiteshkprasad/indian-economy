# labour_enterprise_surveys: verifier notes (Phase 1, first pass, 2026-09-29)

This is an independent adversarial check. The verifier did not build the unit and did not import its code.

## What was run

| Step | Result |
|---|---|
| `fetch labour_enterprise_surveys --offline` | OK, 7 raw files |
| `build labour_enterprise_surveys` (offline, pinned raw) | OK, 10 datasets, 31,017 rows |
| `test -k labour_enterprise_surveys` | 119 passed: the 65 unit and generic tests plus the 54 verifier tests |
| `test tests/verify/test_labour_enterprise_surveys_spotcheck.py` | 54 passed (about 35 s) |
| `coverage labour_enterprise_surveys` | 12 refs, all `partial`, none BROKEN |
| `repro labour_enterprise_surveys` | The 3 builds are byte-identical and match `data/manifest.json` (12 files). The command still prints `REPRO FAILED`, only because `code_hash` changed between builds while other agents edited `pipeline/`. The builder saw the same thing. Re-run when the repo is quiet. |

## Method (tests/verify/test_labour_enterprise_surveys_spotcheck.py)

- **Own parsers, not the unit's.**
  - Upright pages are read with pdfplumber `extract_text`.
  - The landscape ASUSE report pages draw their glyphs rotated (char matrix `(0,1,-1,0)`). The unit reads them with pypdf. The verifier reads them with its own character-level reader (`_rot_lines`), which groups glyphs by x and orders them bottom-to-top.
  - Tables are found by their **printed title** inside a page window. The unit's page numbers are never used.
  - Rows are matched by printed label or code, through the verifier's own label-to-code maps and unit conversions:
    - Rs lakh to crore: x 0.01.
    - '00 to count: x 100.
    - million to count: x 1e6.
    - '000 mandays to count: x 1000.
    - per 1000 to percent: x 0.1.
- **Full census, both directions.**
  - All **31,017** clean values were compared with the re-parse at a relative tolerance of 1e-6. There are **0 mismatches**.
  - Every clean row was found in the PDF, and every published cell the verifier parsed has a clean row.
  - The only exceptions are the documented skips: 17 zero cells in PLFS T51 ("no sample observation"), and 29 cells in ASUSE T33, T35 and T37. Those 29 are per-worker values printed as 0 where the count is 0, or GVA printed as 0 where no market establishment exists. The test asserts that none of the 46 skipped cells was ingested.
- **Page ranges.** The pages the verifier found by title equal the provenance locators:
  - PLFS T26: pp.213-228.
  - ASUSE T4: pp.89-97. T6: pp.134-151. T29: pp.827-844. T31: pp.917-934. T33: pp.1007-1009. T35: pp.1022-1023. T37: pp.1032-1033.
  - ASI Vol I T3: pp.320-334.
- **HAND_ANCHORS.** 40 values were typed by hand from page text the verifier read during this pass, spread over every dataset, every period type (fy, fq, date, cy) and every unit type (percent, INR, INR_crore, count). The anchors include the hard formats: `1,83,070`, `2,000`, `17,97,278` in '00, per-1000 shares, lakh values and the `OT` row. Each anchor is checked against both the clean row and the parser.
- **Mutation check** (scratch run, not in the file): 20 seeded rows per dataset were perturbed by x1.01+0.5, x100 and /100. The comparison caught 584 of 600 changes. The 16 it missed are zero values, where x100 and /100 change nothing.
- **Semantic tests.**
  - The survey-year flags are present on every PLFS, SAS and ASUSE survey-year row, and absent from the PLFS `fq` rows and the ASI rows.
  - All rows are `official`.
  - `INR_crore` appears only on aggregate money items.

Seeded sample (seed 20260929), clean value vs PDF: `lfs.ur.ps_ss.15plus.rural.male` 2023-24 2.7/2.7; `st6.worker_share.helper.urban.female` 2023-24 13.8/13.8; `t26.worker_share.2393.rural.male` 0.09/0.09; `t51.casual_wage_day.p.rural.male` 215.45/215.45; `fs.gva_per_worker.asuse_m.total` 2023-24 112869/112869; `t37.gva_per_estt.asuse_s8.total.hwe` 4268756/4268756; `s3a.total_input` 2023-24 12868830.03/12868830.03 (Rs crore, from 1286883003 lakh); `v1t3.workers_direct.1313` 263874/263874; `pn.ava_per_hh.rural.all` 1592379/1592379; `s5_1a.income_total.agri_land_2.01-4.00` 16435/16435.

## Systematic-error hunt

| Check | Finding |
|---|---|
| Scale | Correct. <br>ASI Statements 3A/5A and Vol I Table 3 C-rows: lakh to crore x 0.01. <br>ASUSE factsheet '00: x 100. <br>SAS households, million: x 1e6. <br>ASI mandays '000: x 1000. <br>ASUSE T6 per-1000: x 0.1 to percent. <br>All confirmed against the PDFs by the census. |
| Signs | No net or negative items. ASI Statement 3B growth rates are not ingested. |
| Periods | PLFS and SAS rows (Jul-Jun) and ASUSE rows (Oct-Sep) are `fy` with the `survey_year` flag and a provenance note. PLFS Statements 10-12 use true fiscal quarters: Jul-Sep 2023 = Q2 2023-24, Apr-Jun 2024 = Q1 2024-25; quarter order was checked from the printed labels. AIDIS stocks are `date` 2018-06-30. AIDIS fixed capital expenditure is 2018-19 with the jul_jun flag. ASI is a true FY. See VER-3 for the Statement 10 reference-month lag. |
| Price basis / base year | Everything is current prices or n/a, which is correct for survey tables. |
| Vintages | Confirmed as follows. <br>PLFS 2024-09-23: printed on p.2 ("23rd September 2024"). <br>ASI 2025-09-30: HTTP Last-Modified header and the URL timestamp. <br>ASUSE 2024-12 and 2025-01: Last-Modified (no printed date). <br>AIDIS 2021-09-10: printed on p.2. <br>SAS 2021-09 (printed). The file's Last-Modified is 10 Mar 2023 (a re-upload, `_587m_0`); the values match the printed report, so the release date stands. |
| Dropped rows/columns | None among the tables ingested (the census runs both ways). One whole relevant table was skipped: VER-1. |
| Position vs label | All rows match by label or code. |
| Provenance | Every block's page and table locator matches what the verifier found by title. |
| Official vs derived | No derived numbers are labelled official. The AIDIS `asset_share_land_building` (urban) is correctly **not** synthesised: only the printed rural 91% is ingested. |
| D1-1 / D1-2 | Compliant. `fetch()` makes 7 plain `ctx.fetch` GETs of public MoSPI PDFs with `expect="pdf"`. There are no cookies, headers, logins or challenges. All sidecars show status 200 with no redirects. SOURCES holds no `*_unit_data`, no eSankhyiki source, and no GSTN/CBDT source. |

## Findings

| # | Severity | Finding | Fix |
|---|---|---|---|
| VER-1 | major | **PLFS AR Table (20) is in the pinned PDF but was not ingested.** It gives workers (ps+ss) by status in employment for each industry of work (pp.147-155). It has 9 blocks (R/U/R+U x male/female/person) of 11 NIC-division groups plus total, x 6 status columns, plus sample workers. This is the industry x status cross-tab that the V1a fallback method names. The issues file (#3, #14), the V1a coverage note and the builder's report all say that "PLFS publishes no industry x status cross-tab", and issue #14 files Table 20 among the State tables. | Ingest T20. Add it to the V1a coverage. Correct issues #3 and #14 and the coverage note. The verifier test `test_plfs_table20_industry_x_status_is_in_pinned_pdf` already parses all 9 blocks x 12 rows. |
| VER-2 | minor | Some coverage claims are stronger than the data. <br>**F3b** is `partial` on `asset_share_building`, but it needs rented-out residential property by group, which the press note does not give; the builder's own note calls this a "weak proxy". <br>**T3a** is `partial` on three urban average-earnings series, but it needs a taxable-income distribution. <br>**C4a**'s "owner-occupier value share" is not in the data; only the share of all buildings in total assets is. | Drop F3b (and arguably T3a) from the coverage file and log them as missing, or state explicitly in each note that the series is a proxy. |
| VER-3 | minor | PLFS Statement 10 is "earnings during the preceding calendar month". The fq label names the survey quarter, but the reference months lag by one (the Jul-Sep 2023 row covers roughly Jun-Aug 2023). The provenance note does not say so. | Add this to the Statement 10 provenance note and to issue #5. |
| VER-4 | minor | Several PLFS AR tables are skipped as out of scope although they are partly useful. <br>Table (35), workers by enterprise type (including government/public sector), has an all-India row; it is a public-sector worker share by R/U, a partial input to R9a. <br>Issue #15 says nothing usable exists. | Mention these in issue #15, or ingest Table (35). |
| VER-5 | minor | The `household_group` dimension holds the R/U location of ASUSE *establishments* (and `total` for R+U). The schema defines it as a household class. AIDIS keeps its household type (cultivator etc.) in `dim_other`. | Put the ASUSE sector in `dim_other` (`sector=rural`), or document the convention. |
| VER-6 | minor | Rounded prose values in the AIDIS press note ("about 35%", "about 7%", "about 15%", "around 49%") are stored with nothing on the row to mark them as rounded. The builder logged this (issue 17), but a user of the data cannot see it. | Add `precision=rounded_prose` to `dim_other` (or a provenance note) for those rows. |
| VER-7 | info | The `repro` code-hash failure is environmental: the outputs are identical. One URL guess for PLFS AR 2022-23 (`AnnualReport_PLFS2022-23F1.pdf`) returned 404. The WebSearch quota is exhausted, so the builder's "not located" claim could not be confirmed or refuted. | Re-run repro when the repo is quiet. |

No value errors were found. All 31,017 values match the original PDFs.

---

# Second pass (2026-09-29): VER-1 to VER-6 fixes and regression check

The verifier re-ran everything from the pinned raw files and did not import the unit's code. The spot-check test was **extended, not replaced**: the 54 first-pass tests are unchanged except that the last assertion of the VER-1 evidence test now checks that the table is ingested. There are 22 new tests, 76 in total.

## What was run

| Step | Result |
|---|---|
| `fetch labour_enterprise_surveys --offline` | OK, 7 raw files (unchanged pins) |
| `build labour_enterprise_surveys` | OK, 12 datasets, 31,881 rows (= builder's report) |
| `test tests/verify/test_labour_enterprise_surveys_spotcheck.py` | **76 passed** |
| `test -k labour_enterprise_surveys` | **152 passed** |
| `coverage labour_enterprise_surveys` | 11 refs, all `partial`, none BROKEN; F3b and T3a no longer declared |
| `repro labour_enterprise_surveys` | The 3 builds are byte-identical and match the manifest (14 files). The command still printed `REPRO FAILED` because `code_hash` changed during the run while other agents were editing `pipeline/`. This is environmental: the builder's clean run printed REPRO OK. |

## New checks in tests/verify/test_labour_enterprise_surveys_spotcheck.py

- **Census of the two new datasets.**
  - `plfs_industry_status`: PLFS Table (20), 702 rows.
  - `plfs_enterprise_type`: Table (35) all-India rows, 162 rows.
  - Both are added to `DATASETS`, so `test_census_clean_matches_pdf` compares every clean row with the verifier's re-parse, in both directions. There are 0 mismatches, 0 unmatched rows and 0 dropped cells.
- **How the new parsers find the data.**
  - Tables are located by printed title in a page window: pp.147-155 and pp.274-282.
  - Block headers are matched by text.
  - Table (20) rows are matched by NIC range label. The irregular labels are handled: `49-53( transport)` and `services))`.
  - Table (35) uses the `all India` and `sample workers ... x` rows.
- **Column semantics from word x-positions, on every page.**
  - Table (20): (5) is *regular wage/salary* (x ~ 576-587) and (6) is *casual labour* (x ~ 660-669). This is the pair that matters for V1a.
  - Table (35): the header words run in order proprietary < govt./ < autonomous < Public/(private ltd) < cooperative < trust/ < employer's < others < total < sample, each next to its column number (2)-(11). So autonomous bodies is col (4) and limited company is col (5), as the unit has it.
- **Identities and cross-table checks.**
  - Table (20), every row: (2)+(3)=(4) within 0.15, (4)+(5)+(6)=(7)=100 within 0.25.
  - Table (20) sample counts add exactly.
  - Each block's `total` row equals Statement 6 2023-24 cell by cell.
  - Each block's sample total equals the Table (26) `sample worker` count, e.g. 1,83,070 for R+U persons.
  - Table (35): shares add to 100 within 0.5, and sample counts add exactly to col (11). Sample counts also add male+female=person and rural+urban=total.
- **Page footers.** Every Table (20) and Table (35) page carries "Annual Report, PLFS, 2023-24", so there is no stale 2022-23 page. See INFO-2.
- **Provenance and flags.**
  - The locators of both new provenance records start with the page range the verifier found by title.
  - All rows are `official`, period 2023-24, `fy` with `survey_year=jul_jun`.
  - `count` is used only for `sample_workers` and `percent` for every share.
- **VER-6.** The test re-reads the printed number token of every AIDIS percent. Exactly the 23 tokens printed without a decimal point point to the ROUNDED provenance record, and that record's note names each series. No other percent points to it.
- **16 new HAND_ANCHORS**, typed from the page text of pp.147, 148, 151, 155, 274, 278 and 282. Examples: T20 R+U persons 58-99 regular 75.8; sample 1,83,070; T35 rural male govt/public 7.2; sample ltd company 2,496; R+U persons 1,10,937.
- **Mutation check** (scratch, not in the file):
  - 20 seeded rows per new dataset were perturbed by x1.01+0.5, x100 and /100. The comparison caught 120 of 120.
  - Relabelling every Table (20) `regular_wage` row as `casual_labour` gave 117 of 117 mismatches.

## Status of the first-pass findings

| # | Builder disposition | Verifier (second pass) |
|---|---|---|
| VER-1 (major) | Table (20) ingested as `plfs_industry_status`; V1a entry added; issues #3/#14 and notes corrected | **CLOSED.** All 702 values match the PDF, and the column semantics were confirmed independently. The V1a entry's series_ids resolve. Issue #3 now says correctly that industry x status *shares* are published but regular *earnings* by industry are not (Tables 38 and 50 give earnings by State and by NCO occupation). Issue #14 no longer calls Table 20 a State table. |
| VER-2 | F3b, T3a withdrawn; C4a/F3a "PROXY ONLY" | **CLOSED.** Checked in the coverage file and in the `coverage` output. |
| VER-3 | Statement 10 provenance note states the one-month lag | **CLOSED.** The note is on the Statement 10 record only; Statements 11 and 12 are unchanged, which is correct. |
| VER-4 | Table (35) all-India rows ingested; R9a partial | **CLOSED.** The values and the column order were verified. R9a stays a proxy, because it is a worker share across all statuses in non-agriculture, not public-sector earnings. The note says so. |
| VER-5 | Documented, not recoded | **ACCEPTED** as documented. The rationale (series identity, one R/U vocabulary) is reasonable. |
| VER-6 | Separate ROUNDED provenance record | **CLOSED.** The set was verified independently: 23 of 23. |

## New observations (none affect values)

| # | Severity | Finding |
|---|---|---|
| INFO-1 | info | Two documentation slips. <br>The VER-6 disposition in the issues file says 7 of the 23 whole-number AIDIS percents are introduced by "about"/"around", but the PDF has 6: urban any-asset 98, urban land 49, rural incidence 35, rural both-agency 7, rural FCE 35, urban FCE 15. The provenance note correctly stars 6. <br>The builder's report lists `F3` among `gap_refs_partial`, but the coverage file does not declare F3 (the `coverage` command shows 11 refs). |
| INFO-2 | info | The pinned PLFS AR 2023-24 PDF has **Table (50)** pages (pp.403-405, regular earnings by NCO division) whose footers read "Annual Report, PLFS, **2022-23**", and p.405 is titled "Table (33)". Table 50 is not ingested. If Phase 2 uses it, first confirm it is 2023-24 data and not a stale page. The ingested Table (51) pages (pp.406-408) carry 2023-24 footers. |
| INFO-3 | info | `repro` code-hash noise, as in the first pass. It is environmental only. |

D1-1/D1-2: no change.
- `fetch()` is still 7 plain `ctx.fetch` GETs of public MoSPI PDFs with `expect="pdf"`, with no headers, cookies or logins.
- SOURCES holds only `mospi_plfs_annual`, `mospi_asuse`, `mospi_asi`, `mospi_aidis_2019` and `mospi_sas_2019`: no `*_unit_data`, no GSTN/CBDT and no eSankhyiki source.

**Verdict: all first-pass findings are resolved. No value errors and no regressions: all 31,881 values match the pinned PDFs.**


---

# Close-out pass (2026-09-29): eSankhyiki API, `sy` periods, State codes

The verifier re-ran everything from the 65 pinned raw files and did not import the unit's code. The spot-check test was **re-keyed and extended, not weakened**. No value expectation changed: every changed expectation is a period label, and each window is re-derived from the printed text of the pinned documents. The file now holds **107 passing tests and 1 strict xfail** (it had 76): 15 census datasets and 74 HAND_ANCHORS.

## What was run

| Step | Result |
|---|---|
| `fetch labour_enterprise_surveys --offline` | OK, 65 raw files (7 PDF + 58 JSON) |
| `build labour_enterprise_surveys` | OK, 15 datasets, 37,125 rows (31,881 PDF + 5,244 API), as the builder reported |
| `test tests/verify/test_labour_enterprise_surveys_spotcheck.py` | **107 passed, 1 xfailed** (VER-C1, strict) |
| `test -k labour_enterprise_surveys` | **256 passed, 1 xfailed**, 0 failed |
| `coverage labour_enterprise_surveys` | 11 refs, all `partial`, none BROKEN |
| `repro labour_enterprise_surveys` | **REPRO OK**: 17 files byte-identical across hash seeds and thread counts, matching the manifest |

## Changes to the spot-check (tests/verify/test_labour_enterprise_surveys_spotcheck.py)

### Re-keying (label change only)

The census key includes the period, so the 57 failures the builder reported were all key misses. After re-keying, all **31,881 PDF rows still match the PDFs with 0 value mismatches, 0 unmatched rows and 0 dropped cells**. The windows come from the verifier's own rules, and each rule is asserted against the pinned text (`test_survey_windows_are_printed_in_the_documents`):

| Survey | Rule | Printed evidence |
|---|---|---|
| PLFS | July-June | PLFS AR p.22: "2023-24 refers to the period July 2023 – June 2024 and likewise for 2022-23 ... 2017-18" |
| ASUSE | October-September | Factsheet p.3: "ASUSE 2022-23 conducted during October 2022 to September 2023" and "ASUSE 2023-24 ... October 2023 to September 2024" |
| SAS | Window read from each statement's own title | Statements 1.1, 1.3, 5.1A and 5.1B print "July 2018 - June 2019". Statement 5.7 prints none, so it takes the report's "agricultural year 2018-19" (p.14). |
| AIDIS fixed capital expenditure | July-June | Press note p.2: "Agricultural Year 2018-19 (July-June)" |

Other changes in the re-keyed checks:
- The 43 survey HAND_ANCHORS were re-labelled mechanically; no value was touched.
- `survey_year` was removed from `IGNORED_DIMS`, so any stray survey_year key now breaks the census.
- `test_survey_period_flags` was replaced by `test_survey_periods`. It sets the expected period type and window for every table, including `fq` for Statements 10-12 and the API, `fy` for ASI, `date` for the AIDIS stocks and `cy` 2019 for bank-account shares. It also requires that no dataset carries `survey_year`.

### New checks on the 3 API datasets (5,244 rows)

**Full census.** All 5,244 rows are re-parsed from the 58 JSON pages by the verifier's own reader:
- `api_pages` checks each page's sha256 against its pin, the endpoint and query parameters (all-India state codes 37/99, page, limit), `statusCode`, the page numbers, 100 records per page except the last, and that the pages add up to `totalRecords`.
- The verifier's maps are its own:
  - The AIDIS class codes: `1..5`/`Q1..Q5` are quintiles, `1..10` are asset-holding classes, and 'All (Asset Holding Class)' is dropped as a duplicate.
  - PLFS fiscal quarters are derived from the calendar month.
  - The ASUSE activity names map to Annexure I codes.
- Result: 0 mismatches, 0 unmatched, 0 dropped, in both directions.
- A seeded 10% sample (525 rows, seed 20260929) is re-checked and printed on top of the census.

**Cross-source checks:**
- AIDIS i5/i9 all-class rows against the verifier's own parse of the press note PDF: 22 of 22 equal exactly. They cover AVA, cash loan (= AOD) and incidence of indebtedness (per 1000 / 10) by R/U x household type. The i9 'fixed' assets for all households equal the press note's *physical* assets, and 'financial' equals its financial assets.
- PLFS API agricultural year 2023-24 against AR Statements 10-12 (verifier's PDF parse): 108 of 108 cells within Rs 0.5 (the largest gap is rounding). This confirms the quarter mapping on its own (the AR prints month names). Q1 2023-24 (April-June 2023) is present for all 27 series and absent from the PDF dataset.

**Identities on the raw JSON:**
- AIDIS:
  - Each per-1000 distribution sums to 1000 (+-1).
  - For all households the five classes hold 200 each, so they are household quintiles.
  - Fixed + financial = assets within Rs 2 (the largest gap is Rs 1), and i9 cash loans = i5 cash loans exactly.
  - The asset-holding 'All' equals the quintile 'All'.
  - Fixed assets rise over asset classes 1-10 for every household type.
- ASUSE i36:
  - Owned + hired = all, within Rs 2 (900 of 900 cells).
  - 'All establishments' lies between OAE and HWE (1500 of 1500), and 'Combined' between Rural and Urban (1500 of 1500). This guards the establishment-type and sector labels.
  - No value is negative.

**Activity map.** The verifier's 50-name map was checked against Annexure I of the pinned ASUSE 2023-24 report (pp.30-31, found by title). Every name appears in the annexure text in code order (M1..M25, M, E, T1..T5, T, S1..S15, S). The only differences are punctuation: 'Semi- Trailers', and ', Manufacture' where the annexure has ';'. 'Other Services' is the S aggregate, as printed.

**Semantics and provenance** (`test_api_rows_semantics_and_provenance`):
- Units: INR, and percent only for the two per-1000 items (conversion "x 0.1").
- stock_flow: stock for assets and loans; flow for earnings, net addition, rent and interest; n/a for shares.
- All rows are `official`, `IN`, source `mospi_esankhyiki_api`.
- **Every row's provenance `raw_path` is the pinned page that actually holds its record**, and its sha256 equals the pin.
- Vintages:
  - AIDIS 2021-09-10: "10 September, 2021" is printed on press note p.2.
  - PLFS ay2023-24 2024-09-23: printed on AR p.2.
  - PLFS ay2022-23 and ASUSE 2025 use the date served, and the release text says so.
- The indicator 6 notes state the preceding-month lag.

**Coverage** (`test_api_coverage_entries`):
- Every series_id declared on the API datasets exists for the declared period, and all entries are `partial`.
- C4a and F3a start with "PROXY ONLY".
- The ASUSE 2025 dataset declares no ref, and F3b, R10, T3a and R9b are undeclared.
- The API refs are exactly S5, R8a, C4b, C4a and F3a (AIDIS) and V1a, F1a and F2 (PLFS).

**Access** (`test_api_pins_and_access`):
- 58 API pins: 2 + 5 + 6 + 45, out of 65 pins in all.
- Every sidecar shows GET, status 200, no redirects and no cookie or authorization header.
- The request spacing measured from the sidecars is at least 2.0 s (checked in scratch).

**Mutation check** (scratch, not in the file):
- Value perturbations: 100 seeded rows per API dataset, under x1.01+0.5, x100, /100, x0.1 and x10. **300 of 300 were detected.**
- Label swaps were caught for every cell whose two values differ:
  - PLFS Q1 2023-24 <-> Q4 2022-23: 54 of 54.
  - PLFS rural <-> urban: 144 of 144.
  - ASUSE M2 <-> M3: 180 of 180.
  - AIDIS d3 <-> d4: 16 of 16.
  - AIDIS rural_q1 <-> rural_q5: 46 of 48. The 2 misses are the equal 20.0% cells.
  - ASUSE OAE <-> HWE: 1176 of 1200. The misses are equal values, mostly zeros.

Seeded sample (API rows), clean value vs raw JSON:
- `i36.land_value_per_estt.asuse_m3.urban.hwe.fa_owned`: 2025, 78569 / 78569.
- `i36.interest_payable_per_estt.asuse_s11.urban.hwe`: 1440 / 1440.
- `i36.fixed_assets_value_per_estt.asuse_t.rural.hwe.fa_hired`: 315102 / 315102.
- `api_i6.regular_wage_earnings_month.total.female`: Q3 2022-23, 15741.2 / 15741.2.
- `i36.net_addition_fixed_assets_per_estt.asuse_s1.total.all`: 142332 / 142332.

## Systematic-error hunt (API and period changes)

| Check | Finding |
|---|---|
| Scale | Correct. AIDIS per 1000 is converted to percent (x 0.1). Rupee values are kept as INR per household or establishment, with no crore conversion. Confirmed by the census and by the press-note match. |
| Signs | No negatives in any API page. The 73 ASUSE zeros sit in populated cells (for example, interest 0 where the loan is Rs 1,251). They are not "no establishment" cells like those in T33/35/37, so ingesting them as values is correct. |
| Periods | See the re-keying table. All PDF `sy` windows are 12 months except SAS Statement 1.3 (**VER-C1**). PLFS API: Jul-Sep 2022 = Q2 2022-23 ... Apr-Jun 2023 = Q1 2023-24, confirmed against the AR's month labels. ASUSE 2025 is `cy` 2025, which rests only on the API's `year: 2025` (VER-C3). |
| Codes | Geography is `IN` only; the API state labels are "All-India" or "All India". The ASUSE activity codes equal Annexure I. The AIDIS classes are coded without mixing quintile and asset classes: asset-class rows have no `quintile_basis`, and quintile rows have no `asset_holding_class`. |
| Provenance | One record per page; each row points to its own page (tested). The AIDIS notes say the classes are NOT the SAM's quintiles. |
| Official vs derived | All rows are `official`. Nothing is summed or derived, and the 'All (Asset Holding Class)' duplicate is dropped only after an equality check (confirmed on the raw data). |
| Coverage claims | Verified as stated. The C4b note calls financial assets a "deposit proxy", which is an honest `partial`. Financial assets include more than deposits, so the builder's own "total financial assets only" remark for R8a applies to C4b too. |
| D1-1 / D1-6 | Compliant. The sidecars show GET only, with an `Accept` header and no cookies, keys or redirects, all on api.mospi.gov.in (the legacy-TLS host). |

## Findings

| # | Severity | Finding | Fix |
|---|---|---|---|
| VER-C1 | minor (label; 8 rows) | **SAS Statement 1.3 has the wrong window.** The unit gives it `sy` '2018-07/2018-12' and a provenance note "land possessed during July-December 2018 (visit 1)". The printed title on pp.76-77 reads "...by size class of land possessed (ha.) **for the agricultural year July 2018 – June 2019**". Statement 1.1 is also built from visit-1 data (p.75), and the unit rightly gives it the full-year window. Visit 1's "July-December 2018" is the reference period of the flow items collected in that visit, not of land possessed. | Label Statement 1.3 `2018-07/2019-06` and correct its provenance note and issue 4. The strict xfail `test_sas_statement_1_3_period_is_the_printed_window` then passes; remove it at that point. The census compares values under the printed window, and all 8 values match. |
| VER-C2 | minor | **SAS Statement 5.7 outstanding loans are a stock "as on date of survey", collected in visit 1** (para 3.5.6.1, p.123; visit 1 ran January-August 2019). They carry the agricultural-year window '2018-07/2019-06' with `stock_flow=stock`, and the provenance note does not say this. The same applies to the Statement 1.1 household counts. This predates this pass: it was `fy` 2018-19 before. | Add "outstanding as on the date of the visit-1 survey (Jan-Aug 2019)" to the Statement 5.7 provenance note. Keeping the survey window as the period is acceptable. |
| VER-C3 | minor | **ASUSE 2025 indicator 36 is not anchored to any document.** The vintage is the retrieval date (2026-09-29). The claim "calendar year 2025 (January-December)" in the provenance note comes only from the API's `year: "2025"`. The activity names equal the **2023-24** Annexure I exactly (tested), but the 2025 annexure was not read. WebSearch quota is exhausted, so the verifier could not confirm the release date or the survey window either. The builder logged this (issues 22, 25), and the dataset serves no gap-map ref. | Before Phase 2 uses it, read the ASUSE 2025 report or factsheet (dated 6 May 2026 and 24 Mar 2026 in the publication list): set the vintage and confirm the Jan-Dec window. Until then, soften "covers calendar year 2025 (January-December)" to "API year 2025". |
| VER-C4 | info | **`plfs_earnings` (AR PDF, whole rupees) and `plfs_earnings_api` (API, one decimal) overlap in 108 cells** (Q2 2023-24 to Q1 2024-25). Both have vintage 2024-09-23, and they differ by up to Rs 0.5. The series_ids differ (`st10.` vs `api_i6.`), so there is no key clash. | Phase 2 must pick one source per cell (the API has more precision) and never add the two. |
| VER-C5 | info | The AIDIS asset-holding classes 1-10 are called "deciles" in the module docstring. The API labels them only "asset holding class 1-10" and gives no household shares, so whether each holds 10% of households cannot be checked. They are ordered (fixed assets rise from 1 to 10, tested). The clean labels are neutral ("by household asset-holding class", `d1..d10`). The builder's "within Rs 2" for fixed + financial = assets is conservative: the largest gap is Rs 1. | Optional: say "asset-holding classes 1-10 (deciles per Report 588, unverified)". |
| VER-C6 | info | PLFS AR 2022-23's release date is still unverified (issue 22). The verifier could not check it either: WebSearch returned "budget exhausted (200/200)". | As logged. |

## Status of the builder's close-out claims

| Claim | Verifier |
|---|---|
| 58 JSON pages, one pin each (65 pins); `mospi_esankhyiki_api` in SOURCES | **Confirmed** (pins, sidecars, provenance). |
| `aidis_2019_quintile` 528 rows; the all-class rows equal the press note exactly; fixed + financial = assets within Rs 2; vintage 2021-09-10 | **Confirmed**: 22 of 22 exact, the largest gap is Rs 1, and the date is printed on press note p.2. |
| `plfs_earnings_api` 216 rows; 108 overlapping rows match Statements 10-12 within 0.5; adds Q1 2023-24 | **Confirmed**: 108 of 108 and 27 of 27 Q1 rows. |
| `asuse_2025_assets_loans` 4,500 rows, supporting data only, no gap ref | **Confirmed** (the census and coverage file agree). Its vintage and window are only as good as the API (VER-C3). |
| All survey rows moved to `sy`, and all other columns are identical to the committed outputs except period, period_type, dim_other and prov_id | **Confirmed for values**: the census finds 0 mismatches over 31,881 PDF rows, and no row keeps `survey_year`. **One window is wrong: SAS Statement 1.3 (VER-C1).** |
| Only `IN` is emitted; State labels go through `geo.state_code` | **Confirmed** for the data: every row is `IN`, and the API pages hold only all-India labels. The `geo.state_code` path is never exercised, because there are no State rows. |
| Coverage: 11 refs, no BROKEN; F3b and R10 unserved | **Confirmed.** |
| The 57 verifier failures were label-only | **Confirmed.** After re-keying, every earlier check passes on unchanged values. |

**Verdict: no value errors. All 37,125 values match their pinned sources: 31,881 against the PDFs and 5,244 against the API JSON. There is one period-label defect (VER-C1, 8 rows, tracked by a strict xfail) and two minor documentation or anchoring gaps (VER-C2, VER-C3).**


---

# Final pass (2026-09-29): VER-C1 fix and regression check

The verifier re-derived the fix from the pinned raw file and did not import the unit's code. For independence, the re-derivation used **pypdf** text plus **pdfplumber word coordinates**. The unit and the spot-check both read these pages with pdfplumber `extract_text`, so this is a different path.

## VER-C1 re-derived from the raw PDF

The raw file is `sas_2019_report_587.pdf`; its sha256 (119bbf39...) equals the pin.

| Check | Result |
|---|---|
| Title window | Both Statement 1.3 title blocks (pp.76 and 77) read "...by size class of land possessed (ha.) for the agricultural year July 2018 – June 2019". |
| Footnote and para 3.1.2.2 | p.77 prints "Note: Based on the land possessed by the household during July-December 2018". Para 3.1.2.2 (p.76) says the statement is "based on the visit-1 data". The builder's reading is right: the footnote dates the classifier (land possessed), and the title gives the window of the estimate. Statement 1.1 (visit-1 data, full-year title) is labelled the same way. |
| Column and block | p.77 has three blocks: 'Social Group: OBC', 'Others' and 'all'. In each block, header (2) sits at x 216-226 and its values are right-aligned at x 265. Header (3) sits at x 325 and its values at x 386. Header (4) sits at x 444 and its values at x 502. The 'all' block's column (2) reads 0.6 / 34.2 / 35.6 / 17.7 / 8.6 / 2.8 / 0.4 / 100.0. The seven classes sum to 99.9, which is rounding. |
| Clean rows | 8 of 8 values are equal. All 8 rows are `sy` '2018-07/2019-06'. Series ids and `dim_other` (null) are unchanged; `stock_flow` is n/a and the unit is percent. All 131 SAS rows now carry the one window '2018-07/2019-06' (1.1: 3 rows, 1.3: 8, 5.1A: 48, 5.1B: 48, 5.7: 24). |
| Provenance | Record `labour_enterprise_surveys:312645fa6379`, locator "p.77 (printed p.47), block 'Social Group: all', col (2)". The note quotes the title window and the footnote, and cites para 3.1.2.2. |

**VER-C1: CLOSED.**

## Regression hunt

| Check | Result |
|---|---|
| Whole-unit diff against HEAD | All 31,881 PDF rows were compared with the committed outputs, after mapping HEAD's `fy` label plus `survey_year` flag to `sy`. **This time there was no exception for Statement 1.3.** All 12 datasets are identical in every column except `prov_id`, with 0 differences. |
| Rebuild | `build labour_enterprise_surveys` (offline): 1 ok, 15 datasets, 37,125 rows. All 17 output files are byte-identical to the files present before the rebuild, so the builder's reported outputs are what the code produces. `manifest --check` is up to date. |
| `repro labour_enterprise_surveys` | **REPRO OK**: 17 files byte-identical across hash seeds and thread counts, matching the manifest. |
| Leftovers | Nothing in code, coverage, the gap map or other units references '2018-07/2018-12' or `jul_dec`. The only mentions are historical, in issue 24 and in the verifier's own comments. No coverage entry uses Statement 1.3, so coverage cannot be affected. `_pdf.SURVEY_WINDOWS` keeps only jul_jun and oct_sep, and both are still used. |
| `coverage labour_enterprise_surveys` | 11 refs, all `partial`, none BROKEN. |

## Changes to the spot-check (tests/verify/test_labour_enterprise_surveys_spotcheck.py)

These changes strengthen the file; nothing was weakened.
- The strict xfail mark was removed. `test_sas_statement_1_3_period_is_the_printed_window` is now a normal check. It asserts:
  - both Statement 1.3 title pages print the agricultural-year window;
  - all 8 rows are `sy` `SAS_AY`;
  - the p.77 footnote is printed;
  - the provenance note carries both the title window and "July-December 2018".
- `KNOWN_PERIOD_DEFECTS` (the census's one-label remap) was **removed** rather than left as a no-op. The census and `test_survey_periods` now key every row by the unit's own period, and every `sy` window must be 12 months, SAS Statement 1.3 included.
- Two new HAND_ANCHORS were typed from the p.77 word layout: St 1.3 '0.40 - 1.00' = 35.6 and '< 0.01' = 0.6. The file now has 76.
- **Mutation check** (scratch, not in the file). Relabelling Statement 1.3 back to '2018-07/2018-12' is caught 3 of 3 times: by the converted test, by the census ("8 clean rows the verifier cannot find in the PDF") and by `test_survey_periods`. Removing "July-December 2018" from the provenance note is caught by the converted test.

## What was run

| Step | Result |
|---|---|
| `test tests/units/test_labour_enterprise_surveys.py` | 20 passed |
| `test tests/verify/test_labour_enterprise_surveys_spotcheck.py` | **110 passed**, 0 xfailed or xpassed: the 107 earlier tests, the converted VER-C1 test and 2 new anchors |
| `test -k labour_enterprise_surveys` | **259 passed**, 0 failed |
| ruff on the spot-check | This pass adds no new violations. The long lines (E501) and 4 multi-statement lines (E702) already in the file are unchanged. |

## New observations (none affect values)

| # | Severity | Finding |
|---|---|---|
| FIN-1 | info | The issues file's "Close-out follow-up" bullet on survey periods still says "SAS Statement 1.3 gets its visit-1 window". Issues 4 and 16 and the VER-C1 disposition now say the opposite. The builder should reword or strike that sentence (the file is builder-owned). |
| FIN-2 | info | `sas._row` keeps a `window="jul_jun"` parameter that no caller passes any more. It is harmless, and could be inlined. |

## Status of the open close-out findings

VER-C2 (the Statement 5.7 stock is as on the visit-1 date) and VER-C3 (ASUSE 2025 is not anchored to any document) stay **OPEN**, both minor. VER-C4 to VER-C6 (info) are unchanged. The builder did not address them in this pass, and none of them affects values.

**Verdict: VER-C1 is fixed correctly: all 8 values are unchanged and the window equals the printed title. There are no regressions. All 37,125 values still match their pinned sources (31,881 against the PDFs, 5,244 against the API JSON), with no remapped periods left in the verifier's checks.**
