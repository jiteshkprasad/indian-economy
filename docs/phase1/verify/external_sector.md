# external_sector: independent verification (first pass and close-out pass)

Verifier: independent agent (did not build the unit). Date: 2026-09-29. Regression test: `tests/verify/test_external_sector_spotcheck.py` (41 tests; run with `uv run python -m pipeline test tests/verify/test_external_sector_spotcheck.py`).

## Verdict

**Pass, with one defect to fix and a few minor notes.** Every value I compared matches the pinned RBI pages: 3,052 of the 19,576 values (15.6%), 0 mismatches. Provenance, access policy, reproducibility and coverage claims all hold. One systematic error: 5 official LRS rows (plus the 5 rupee rows derived from them) are labelled FY 2025-26 but hold March 2026 only (V1 below).

## What I ran

| Step | Result |
|---|---|
| `fetch external_sector --offline` | OK, 44 files |
| `build external_sector` (offline, from pins) | OK, 16 datasets, 19,576 rows |
| `test tests/units/test_external_sector.py` | 53 passed |
| `test -k external_sector` (unit + generic + my verify file) | 205 passed, 1 xfailed (V1, strict) |
| `repro external_sector` | REPRO OK: builds byte-identical across hash seeds and 1/4 threads, and match `data/manifest.json` |
| `coverage external_sector` | 20 refs, none BROKEN; OFFICIAL covered 7, partial 5 |

## Method (independent of the unit's code)

- **Parser:** lxml with my own colspan/rowspan expansion. The unit uses BeautifulSoup and its own `_html.py`. Clean data is read with DuckDB; the unit writes with polars. The test never imports `pipeline.ingest.external_sector`.
- **Row location is by label, never by the unit's row order:**
  - BPM6 rows by printed item number, with the label text also checked.
  - Old-format BoP and external debt by printed label. A repeated label ("Equity", "IBRD", "ii) Abroad") is resolved as the first occurrence after its parent's row, and the parent is found the same way, recursively.
  - IIP by A./B. section and item number.
  - NRI by scheme header, T143/T144 by group header plus unit header, FLA and ITES by header text.
  - ECB by route section and printed serial number, with the borrower name checked.
- **Periods mapped independently:**
  - "April-June 2023" to Q1 2023-24.
  - "2023-24: Q4 PR" to 2024-03-31.
  - T144 FY row to end-March.
  - T205 year/month rows.
- **Unit conversions re-applied:**
  - ITES US$ bn x1000.
  - Debt release US$ bn x1000.
  - ECB US$ /1e6.
  - LRS rupee rows recomputed from raw US$ and the raw T133 FY-average rate.
- **Sample:** seed 20260929. 15% of each dataset, at least 40 rows each, stratified by (unit, period_type, vintage, table, status), so every edition, currency, period type and the derived rows are drawn. On top of that, every series named in the coverage yaml at its covered period (the gap-map-critical cells: V3, V4, R11-R15, K5, K8, K8b, K8c, R14a, P5, P6, S2, S3, R11a, R12a, R8).
- **Completeness:** for 11 tables (T125-T127, T196, T198, T130, T142-T144, T146, 2024-25 T199), I compared the count of numeric cells printed with the number of clean rows. They are equal, so no rows or columns were dropped.
- **Scale check:** Rs crore x10 / US$ mn / T133 rate is within ±3% for every gross BoP line over US$ 5 bn, ±5% for invisibles and ±10% for reserves (from 1994). This rules out lakh/crore/million slips.
- **Hand anchors:** 22 cells typed from the page text, plus the FY 2023-24 FX anchors.
- **No PDFs:** every source is HTML, so there was no PDF page-text check to do.

### Values checked per dataset (0 mismatches in every one)

| dataset | rows | checked |
|---|---|---|
| fx_inr_usd | 188 | 40 |
| bop_bpm6_annual | 1,700 | 288 |
| bop_bpm6_quarterly | 6,708 | 1,009 |
| bop_overall_annual | 2,172 | 330 |
| invisibles_annual | 1,440 | 216 |
| nri_deposits | 304 | 48 |
| foreign_investment | 308 | 48 |
| fx_reserves | 510 | 76 |
| external_debt | 2,432 | 368 |
| external_debt_by_sector | 289 | 53 |
| iip_quarterly | 872 | 130 |
| ecb_monthly_2324 | 1,287 | 200 |
| fla_census | 395 | 65 |
| remittance_survey | 143 | 44 |
| ites_survey | 610 | 93 |
| lrs_outward | 218 | 44 (incl. derived) |
| **total** | **19,576** | **3,052 (15.6%)** |

## Findings

| # | Severity | Finding | Evidence | Suggested fix |
|---|---|---|---|---|
| V1 | minor (wrong period label; values tiny, not the reference year) | **LRS travel sub-items 1.6.1-1.6.5 are stored as FY 2025-26 but hold one month.** In the June 2026 Bulletin table (No. 36) these items are printed only for Mar-2026 and Apr-2026. Their "2025-26" column equals the March value exactly: 16.05, 2.55, 2.79, 450.16, 623.05. So 5 official rows (`lrs.usd.annual.lrs_1_6_{1..5}.current`, 2025-26) are mislabelled. The 5 derived rupee rows built from them are also wrong in kind: they convert a March value at the full-year average rate (88.3071). The issues file (-15) mentions the sub-items but the rows still claim a full year. | Raw: `lrs_bulletin_2026-06.html`, rows 1.6.1-1.6.5, columns 2025-26 / Feb / Mar. Test `test_lrs_fy_rows_cover_the_full_year` (strict xfail). | Either drop the FY cells for 1.6.1-1.6.5 and keep only the monthly rows, or store them as `month` 2026-03. Don't derive rupee values for them. Then remove the xfail. |
| V2 | minor | **ECB and RDB "all routes" totals are missing for two months.** The `ecb.total.*.all` rows exist for Apr 2023-Jan 2024 but not for Feb and Mar 2024. Those pages print "Grand total", which the unit's total matcher does not read; the RDB totals for Mar 2024 are printed as "-". Anyone summing `...all` across FY 2023-24 would miss two months. Loans and route totals are complete. | Raw `ecb_2024-03.html` row "Grand total 7,73,35,56,768"; clean has no `ecb.total.ecb_fccb.all` for 2024-02 or 2024-03. | Treat "Grand total" as route=all, or document that FY totals must be built from the automatic and approval totals. |
| V3 | minor | **Unlogged same-day re-download.** `ecb_2023-12.html` was fetched twice about 8 s apart, and the pin points to `2026-09-29-r2/`. The two copies differ only in the F5 client-script token (`f5_cspm`), not in data. The issues file says "Revisions seen: none". | `data/raw/rbi_ecb_monthly/2026-09-29{,-r2}/external_sector/ecb_2023-12.html`; first byte difference at offset 120,936 (inside `<script id="f5_cspm">`). | Add one line to the issues file under "Revisions seen". |
| V4 | minor (information) | **FY 2025-26 T133 average vs monthly rates.** The FY-average INR/USD for 2025-26 (88.3071) is not the mean of the T205 monthly averages (88.3528). For 2022-23 to 2024-25 the two agree to 4 decimals. This is likely publisher method (a daily average), not a unit error. It matters only for rows derived for 2025-26. | My check against clean T133 and T205. | Nothing to fix. Note it if Phase 2 converts 2025-26 values. |
| V5 | minor (information) | **ECB industry slugs are fragmented.** For example, `financial_service_activities_except_insurance_and_pension` (30 loans) vs `..._funding` (161); 73 distinct slugs in all. Already logged (-11). | Clean ecb dataset. | Phase 2 mapping, as logged. |
| V6 | minor (project-wide) | **Telangana is coded `IN-TS`.** ISO 3166-2:IN changed it to `IN-TG` (2023). The unit is consistent with state_fiscal and hces_consumption, so this is a cross-unit decision, not a unit defect. | `surveys.py` REM_STATE; `state_fiscal/common.py`; `hces_consumption/_common.py`. | Orchestrator: decide once for all units. |
| V7 | unverified claim | **The claim that the 2023-24 FLA census round was "not found"** (issues -12, which forces an end-March 2025 structure for the R14a/R8 payer splits) could not be checked: the web-search quota was exhausted. RBI has usually published each FLA round as a press release as well as on the publication listing. | n/a | Builder or orchestrator: search the RBI press-release archive (roughly Nov 2024 to Jan 2025) for "Census on Foreign Liabilities and Assets ... 2023-24" before Phase 2 settles for the 2025 structure. |

### Builder claims I re-checked (all confirmed)

- **BoP 2023-24 (T127, Rs crore) equals the NAS 2026 figures quoted in the gap map:**
  - V3 1.B.1 credit 62,344.
  - V4 1.B.1 debit 30,636.
  - R11 1.C.1 credit 9,83,128.
  - R12 1.C.1 debit 99,913.
  - R13 1.B.2+1.B.3 credit 2,80,907.
  - R14 1.B.2+1.B.3 debit 7,24,611, against NAS 7,24,612.
  - R14a 3.1.A.1.2 credit 1,63,704.
- **K5:** CA net -2,15,248. NAS 1.9 net capital inflow is 2,08,891, and the gap of 6,357 equals 1.C.2 net (1,463 - 7,820) exactly.
  - Extra observation for Phase 2: NAS 6.1 net financial (liabilities 8,86,570 - assets 6,70,569 = 2,16,001) equals BoP FA net 2,12,681 plus E&O 3,320.
  - So 2,08,891 = 2,16,001 + KA (-753) + 1.C.2 net (-6,357). NAS counts errors and omissions and government current transfers differently from the BoP current balance.
- **BoP identity:** CA + KA + FA + E&O = 0 for 2023-24.
- **K8c reserve assets 2023-24:** debit 5,26,931, net -5,26,931. A reserve increase is a debit, so Phase 2 must flip the sign for the K_RBI acquisition.
- **Debt-to-GDP discrepancy:** end-March 2023 is 19.1 in T145 and 19.6 in T146, the only differing ratio cell. The 29 Jun 2026 release prints 19.6.
- **Q1 2024-25 goods exports:** US$ 111,158 mn (HBS 2024-25) became 115,169 mn (HBS 2025-26). The Q1 CAD moved from -8,647 to -4,454.
- **Gross external debt end-March 2024:** T145 US$ 668,883 mn vs release Table 1 668.9 bn. Consistent.
- **Stage labels follow the page notes:**
  - "Data for 2025-26 are preliminary estimates" on T127/T197.
  - "Data for 2024-25 are preliminary estimates" on the 2024-25 edition T196.
  - "provisional" on T143.
  - Other years are "n.a.", as the publisher flags nothing for them.
- **T124 vs T125 row-count asymmetry (6 rows):** the publisher prints SDR allocation as "0" in T125 and "-" in T124 for 2020-21 and 2022-23. Not a unit error.

## Systematic-error hunt

| Check | Result |
|---|---|
| Scale (lakh/crore/thousand crore; million/billion) | OK. All sampled conversions exact; INR/USD ratios match T133 within band (only the 1991-92/1992-93 dual-rate years deviate, which is the publisher). |
| Sign conventions | OK. RBI credit-debit net; identity closes; reserves increase negative (documented). |
| Mislabelled periods | **V1** (LRS 1.6.x). Everything else OK: IIP quarter-ends, T144 end-March, NRI "Year (end-March)", T205 end-month on the last calendar day (documented). |
| Wrong price basis or base year | None. All money is current prices; the external data carry no base year. |
| Mixed vintages | Intentional and keyed by `vintage`: quarterly BoP and IIP 2024-25 are in two editions; ITES 2024-25 is in two rounds. Consumers must filter by vintage. |
| Dropped rows or columns | None in the 11 tables censused. Other gaps are intended: "-" and "–" cells are emitted as no row (RBI uses "-" for nil or negligible), and the ECB "Grand total" rows are not read (V2). |
| Duplicated totals | None beyond published totals; the T145 and T146 ratio rows are kept as separate series on purpose. |
| Position-based matching | The unit matches by item number and full ordered label sequences, and raises on change. My label-based locator agrees on every sampled row. |
| Provenance pointing at the wrong table | None. All 19,576 rows join to a prov record with the same table_id, source_id, status, vintage and price_basis. Each (dataset, table, unit, vintage) block points to the right raw file, with correct caption and conversion. LRS table numbers (35/35/36) match the Bulletin section list. |
| "official" on derived numbers | None. The only arithmetic rows (38 LRS Rs crore) are `derived`, with the rate's prov_id in `inputs`, and they recompute exactly (but see V1 for 5 of them). |
| Coverage claims | Consistent. The "full" refs (V3, V4, R11, R12, R15, K8c, S3) are filled by these series and match NAS. K5 is correctly only partial. R15 must be reconciled with K5 in Phase 2, as the builder flags. |

## D1-1 / D1-2 compliance

- The code downloads only through `ctx.fetch`, with `referer=` and `expect="html"` and no custom headers. There is no httpx, requests or urllib, no cookies or auth, no rbidocs URL, and no microdata, GSTN or CBDT source.
- All 45 `.meta.json` sidecars (44 pins plus the superseded ECB Dec-2023 copy):
  - HTTP 200, GET, no redirects.
  - `final_url` is on `https://www.rbi.org.in/`.
  - Only the standard browser-like header set.
  - Minimum spacing between retrievals is 2.0 s.
- No raw file contains challenge markers (TSPD, CAPTCHA, cf-chl, "request rejected", a password field). All are table pages of 75-182 KB. The `f5_cspm` script present on RBI pages is a client monitoring script, not a challenge page.
- D1-4 was never triggered, since no rbidocs host was used.

## Files

- `tests/verify/test_external_sector_spotcheck.py`: the independent spot-check, completeness, scale, derived-row, hand-anchor, FX-anchor and V1 (strict xfail) tests.
- `docs/phase1/verify/external_sector.md`: this file.

## Close-out pass (2026-09-29)

Verifier: the same independent role (did not build the unit). Scope: the builder's V1-V4 fixes and the close-out follow-up:
- RBI "PR" stage now `Partially Revised`: 763 IIP rows and 40 debt-release rows.
- Remittance-survey State codes now come from `pipeline/core/geo.py` (D1-9), so the 2016-17 J&K row is `IN-XJK`.
- A new "INR/USD exchange rate: guide for Phase 2" in the issues file.

Nothing was fetched. Everything was checked against the 45 pinned raw pages.

### Verdict

**Pass. No data errors found in the changes.** Every expectation I changed was re-derived from the raw pages. No check was weakened.
- The 803 stage relabels match the flags printed on the pages and each page's own footnote legend. I checked every row of both datasets, not a sample.
- The single State recode is correct.
- The guide's coverage and conversion claims hold.
- The 6 V-S failures are gone.

### What I ran

| Step | Result |
|---|---|
| `test tests/verify/test_external_sector_spotcheck.py` | **50 passed** (was 35 passed, 6 failed) |
| `test -k external_sector` (unit, generic, hygiene, verify) | **218 passed**, 0 failed |
| `repro external_sector` | REPRO OK: 18 files byte-identical across hash seeds 0/1 and 1/4 threads, matching `data/manifest.json` |
| `coverage external_sector` | no BROKEN; OFFICIAL covered 7, partial 5 (unchanged) |
| ruff on the verify file | only E501 (5 pre-existing lines) |

Spot-check sample after this pass: 3,120 of 19,965 values (15.6%), 0 mismatches in every dataset. That includes 128 FLA rows across both rounds, 133 IIP, 52 debt by sector, 45 remittance survey, 200 ECB and 40 FX.

### Stale expectations updated (each re-derived from raw)

| Test | Old | New, and where it comes from |
|---|---|---|
| `test_raw_files_match_pins` | 44 pins | 45. The added pin is `rbi_fla_census/fla_census_2023_24.html`. sha256, size, www.rbi.org.in-only and no-challenge checks all pass. |
| `test_sample_size_meets_the_ten_percent_rule` | 19,576 rows | 19,965 = 19,576 - 10 (V1) + 3 (V2) + 396 (V4). Each delta has its own raw-derived test (below). The sampler now tops up to the 15%/40 minimum with the same seed. LRS fell to 38 by proportional rounding once it shrank to 208 rows. |
| `test_lrs_derived_rows_recomputed_from_raw` | 38 | 33. Counted from the three raw Bulletin tables as FY cells whose item is also printed in that FY's April column: 11 + 11 + 11. 1.6.1-1.6.5 of 2025-26 are excluded, as V1 asked. All 33 still recompute from raw US$ x raw T133. |
| `loc_fla` | always read the 2024-25 page and asserted year 2025 | Reads the page of the row's round, keyed by vintage. The vintage is the release date printed on the page ("Date : Oct 11, 2024" / "Oct 29, 2025"), which is tested. The single-date tables (2B, 8) now take their year from the caption's "end-March YYYY". |
| `loc_ecb` (route `all`) | did not recognise "Grand total" | Also matches "Grand total" / "Grand Total" (Feb/Mar 2024 pages, V2). |
| `test_hand_anchors` FLA 3B | 742,228 for every vintage | Split by round. 7,26,558 is typed from the 2023-24 page, Table 3B, 2024 / US$ million. 7,42,228 is typed from the 2024-25 page. This is a genuine publisher revision (issues -12). |

### New checks

- **`test_estimate_stages_follow_raw_flags`** covers all 872 IIP and 289 debt-release rows.
  - For each row, the flag printed next to its period is read from the raw page: IIP column header "2024-25:Q1 PR", release column header "2025 PR", or the Table 5 row label "2025 PR".
  - The flag is decoded through the legend parsed from that same page: "R: Revised. PR: Partially Revised. P: Provisional." on the release, and "PR: Partially Revised, P: Provisional" on HBS T198/T199 (2024-25) and T199/T200 (2025-26).
  - No flag means `n.a.`.
  - Result: 763 + 40 `Partially Revised`, 0 mismatches.
  - No HBS IIP header carries a bare "R", so the unit's HBS 'R' mapping is never exercised.
  - I also scanned every pinned page for flagged period cells in headers or row labels. Only these five pages carry flags, so the `n.a.`/`Preliminary` stages elsewhere are faithful to the pages. One consequence: end-March 2025 debt is `Partially Revised` in the release but `n.a.` in T145/T146. That is presentation, not an error.
- **`test_closeout_changed_rows_sample`** draws a seeded sample (seed 20260930) of the 804 changed rows: 81 rows (10.1%), including the recoded row.
  - The sample covers both IIP editions, all three units (US$, Rs, percent memo row) and the release's US$ and percent rows.
  - Each row's value is re-located in raw by label, its stage re-derived as above, and its geography re-derived as below. 0 mismatches.
- **`test_remittance_state_codes_independent`** uses a hand-typed printed-name -> ISO 3166-2:IN map (codes as amended 2023-11-23: IN-CG, IN-OD, IN-TS, IN-UK; plus IN-DH and IN-LA).
  - Rule: a J&K fiscal year ending by 30 Oct 2019 -> `IN-XJK`. A year that straddles the reorganisation, Ladakh printed before 31 Oct 2019, or DNH&DD printed before 26 Jan 2020 fails the test.
  - Every numeric cell of raw Table 2 maps to exactly one clean row with the expected geography and series id: 87 rows, and the set matches exactly.
  - DNH&DD 2020-21 -> IN-DH is right, since FY 2020-21 starts after the 26 Jan 2020 merger. 2016-17 J&K 0.2 -> IN-XJK.
  - The 2023-24 column sums to 100 +/- 0.2. No superseded code (IN-TG/CT/OR/UT/DD/DN) appears in any dataset.
  - V5 is closed: the builder is right that IN-TS is the current code, and my first-pass premise was reversed.
- **`test_fla_no_dropped_cells`**, per round: clean rows per table equal the numeric cells printed, for Tables 2B, 3A, 3B, 4, 5, 6 and 8. The "%" share/growth columns are not ingested, except 2B's "% share of FDI in Total Equity", which is. The 2023-24 round gives 396 rows and the 2024-25 round 395.
- **`test_ecb_route_totals_complete`**: every route total printed with a number on the 12 pages equals a clean row, and no row exists where the page prints "-" or a blank. That gives 69 totals, with `ecb_fccb.all` in all 12 months. The RDB Mar 2024 totals are printed "-" or blank and correctly have no row.
- **`test_fx_phase2_guide_claims`**:
  - 188 rows in 4 series. The period types and extents are re-derived from raw T133 (FY 1986-87..2025-26, 40) and T205 (2022-01..2026-06, 54). T205 prints nothing before January 2022.
  - One vintage and two prov records.
  - End-month rows fall on the last calendar day.
  - End-March rates are equal in T133 and T205 for 2022-2026. This is why the "filter to one series" rule matters, and `usd_million_to_inr_crore` does raise "duplicate exchange rates" (read in `pipeline/core/units.py`).
  - The worked example holds: US$ 1,000 mn x 82.7897 / 10 = Rs 8,278.97 crore.
  - The runner's INR_per_USD-in-inputs check exists (`pipeline/core/runner.py`).

### The builder's other claims, re-checked

- The trade_satellites coverage table in the guide matches that unit's clean files:
  - `comtrade_monthly_2324` 2023-04..2024-03.
  - `imf_imts_monthly` 2011-01..2026-05, so 2011-01..2021-12 has no rate.
  - `imf_imts_fy` 2011-12..2025-26.
  - `imf_imts_annual` 1948-2025 and `batis_*` 2005-2024, all calendar years.
  - One loose spot: the table groups `comtrade_fy_2324` with "fy 2011-12..2025-26", but that dataset holds only 2023-24. It is covered either way.
- Nothing downstream referenced the old `remit.destination_state.in-jk` 2016-17 row. The coverage yaml S3 entry uses in-mh/in-kl/in-up for 2023-24.
- `rem_state_code` logic, read in `surveys.py`:
  - Undivided AP (IN-XAP) is returned only for periods ending by 1 Jun 2014.
  - Telangana, Ladakh or DNH&DD printed before they existed raise an error.
  - Straddling periods raise an error.
  - None of these cases occurs in the pinned table. The only historical code used is IN-XJK.
- Provenance notes contain no stale "PR recorded as Revised" text. The unit docstring and `_datasets.json` describe the new stage and the four FX series.

### Findings

| # | Severity | Finding | Suggested action |
|---|---|---|---|
| C1 | minor (docs) | The issues file still says the verifier's spot-check has stale expectations (header paragraph and the **V-S** block). This pass resolves them: 50/50 pass, and `test -k external_sector` is 218/218. | Builder: mark V-S resolved and update the test counts in the header and close-out checks. |
| C2 | minor (docs) | The guide does not repeat first-pass V4: the T133 FY 2025-26 average (88.3071) is not the mean of the T205 monthly averages (88.3528). Anyone who builds calendar or FY averages from months (option (c)) will see this gap. | Add one caveat line to the guide. |
| C3 | minor (docs) | Guide coverage table: `comtrade_fy_2324` is listed with "fy 2011-12..2025-26", but it holds only 2023-24. | Split the row. |
| C4 | info | FLA R14a/R8 coverage at 2024-03-31 now matches two rounds of the same cell with different values (first estimate and revised), and the coverage entry does not pin a vintage. | Phase 2 chooses a round (already in -12). |

No blocker or major issues.
