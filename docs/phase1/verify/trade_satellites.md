# trade_satellites: independent verification (first pass)

Verifier: independent agent (did not build the unit). Date: 2026-09-29. Regression test: `tests/verify/test_trade_satellites_spotcheck.py` (30 tests, about 7 s; run with `uv run python -m pipeline test tests/verify/test_trade_satellites_spotcheck.py`).

## Verdict

**Pass.** No value defects and no blockers. I compared every one of the unit's 240,746 values with the pinned raw files and found 0 mismatches, with no dropped and no invented rows.

- Status labels, vintages, units, period types, provenance, access-policy compliance, reproducibility and the `partial` coverage claims for S1/S2 all hold.
- There are six minor findings (V1–V6 below): one failing framework raw-pin test that was already logged, and five labelling or documentation points. None changes a number.
- The builder's major issues (TradeStat not fetched; partner × HS chapter only for the top 30 partners; BaTIS balanced ≈ 66% of reported; BaTIS calendar-year only; IMF annual world imports understated before 2006) are real. I reproduced each of them from the raw files.

## What I ran

| Step | Result |
|---|---|
| `build trade_satellites` (offline, from pins) | OK, 7 datasets, 240,746 rows |
| `fetch trade_satellites --offline` | OK, 212 raw files |
| `test tests/units/test_trade_satellites.py` | 52 passed |
| `test -k trade_satellites` (unit + generic + my verify file) | 325 passed, 1 failed: the known raw-pin sidecar timestamp (V1) |
| `repro trade_satellites` | REPRO OK: byte-identical builds that match `data/manifest.json` |
| `coverage trade_satellites` | S1 partial, S2 partial, nothing BROKEN |

## Method (independent of the unit's code)

- **Parsers:**
  - The test never imports `pipeline.ingest.trade_satellites` or polars.
  - Raw SDMX-CSV files (IMF, BaTIS) are read with Python's `csv` module; the unit uses polars.
  - Comtrade JSON is read with `json`.
  - Clean parquet is read with DuckDB.
  - The mappings are my own: indicator codes, partner codes (geography, or `partner_group` in dim_other), IMF `YYYY-Mmm` periods, Indian fiscal year (April–March), BaTIS measures (B/F/N), and US$ units → US$ million.
- **Full comparison, not a sample.**
  - Every clean row is keyed by label, never by row order:
    - IMF: indicator, partner, period.
    - Comtrade: flow, HS chapter, partner ISO, month.
    - BaTIS: partner, flow, EBOPS item, measure, year.
  - Each row is compared with its raw observation, within 1.5e-6 because values are rounded to 6 decimals on write.
  - The raw key set must equal the clean key set, which catches dropped or invented rows.
  - The partner code printed in each `item_label` must match the raw code.
- **Derived FY rows are recomputed from raw.**
  - IMF FY: 5,663 rows. Comtrade FY 2023-24: 4,460 rows.
  - Each is the sum of the 12 raw months (April to March). Only partner-years or series with all 12 months are kept, and the kept set must equal the unit's set exactly.
- **Second route (text level):**
  - A seeded, stratified 10% sample (seed 20260929; strata = dataset × period_type × status × year): 23,052 rows.
  - Each sampled row is located again in the raw file text without the csv/json readers: the SDMX-CSV line is split naively on commas, and the Comtrade record is found as a literal JSON fragment by regex.
- **Hand anchors:** 7 values typed from the raw files (IMF Aruba rows, Comtrade April 2023 World/USA/S19 totals, BaTIS reported World exports 2023 and SJ imports 2024).
- **Mutation check:** I perturbed one IMF value by 0.1%, swapped two BaTIS year labels, and deleted one Comtrade row in scratch copies. The full-comparison tests caught all three.

| Dataset | Rows | Compared in full | Text-route sample | Mismatches |
|---|---|---|---|---|
| imf_imts_monthly | 76,069 | 76,069 | 7,607 | 0 |
| imf_imts_fy (derived) | 5,663 | 5,663 (recomputed) | – | 0 |
| imf_imts_annual | 24,798 | 24,798 | 2,481 | 0 |
| comtrade_monthly_2324 | 62,443 | 62,443 | 6,244 | 0 |
| comtrade_fy_2324 (derived) | 4,460 | 4,460 (recomputed) | – | 0 |
| batis_2023_2024 | 49,936 | 49,936 | 4,992 | 0 |
| batis_history | 17,377 | 17,377 | 1,728 | 0 |
| **Total** | **240,746** | **240,746** | **23,052** | **0** |

There are no PDF-derived values in this unit, so no PDF page-text check applies.

## Systematic-error hunt

| Check | Result |
|---|---|
| Scale | IMF OBS_VALUE is in US$ units even though SCALE=6. April 2023 world exports = 3.47e10, i.e. US$ 34.7 bn. The ÷1e6 is right. Comtrade primaryValue is in US$ units (÷1e6). BaTIS is USD_EXC with UNIT_MULT 6, i.e. already US$ million, and is not converted. |
| FOB/CIF | IMF: XG_FOB_USD = exports FOB, MG_CIF_USD = imports CIF. Comtrade: primaryValue equals fobvalue for X and cifvalue for M in every record (asserted). |
| Periods | Monthly and calendar-year rows are labelled `month` / `cy`, and FY rows `fy`. The FY is the April–March sum, recomputed independently. BaTIS is `cy` only. Calendar vs fiscal year and US$ vs ₹ are explicit throughout. |
| Cross-source | IMF FY world exports vs the TradeStat totals quoted in Phase 0 recon: within 0.5% for 2024-25 and 2025-26 (recomputed from raw). IMF vs Comtrade FY 2023-24 world: within 1% (exports 437,722 vs 436,918; imports 672,861 vs 675,387). IMF CY 2011–2025 = sum of months, within 0.2%. Comtrade chapters sum to TOTAL every month. BaTIS balanced partners sum to World. |
| Top-30 partners | Re-ranked from the raw TOTAL pulls: the set of partners with HS-chapter pulls equals my top 30 (excluding World and "Areas nes"). They cover 81.9% of the total, as claimed. |
| Status | IMF monthly/annual and Comtrade monthly are `official`; FY sums are `derived`; BaTIS B/F are `estimated` and N is `official` (asserted per row). See V5. |
| Vintages | IMF 2026-08-31 = PUBLICATION_DATE, the only value in the attribute file. Comtrade = each month's `lastReleased` in getDA (2024-05-28..31), and the FY vintage = the latest of those. BaTIS 2025-12 = "December2025" in the dataflow's bulk-file annotation (V6). |
| Provenance | 233 records. Each official record points to the right raw file and slice (checked per Comtrade pull, per IMF indicator and per BaTIS measure). Derived records carry `inputs` and a method. |
| Builder's claims re-derived | FY 2023-24 IMF partner-years dropped (<12 months): 3,756 US$ mn ✔. Comtrade dropped series: 14,639 ✔. BaTIS balanced/reported 2023 exports: 223,337 / 337,540 ✔. IMF CY imports < exports in 2000–2004 and +67% in 2006 ✔. The ISO partners' sum is 99.1% of World (FY 2023-24 exports) ✔. |
| Comtrade `legacyEstimationFlag` = 4 on 33,343 of 62,443 records | Every one of them has `isNetWgtEstimated = true`, and no record flags an estimated value. The flag is about net weight, so values stay `official`. Information only. |

## D1-1 / D1-2 compliance

- Every one of the 212 pins is a GET, with status 200 and no request body. All go to keyless public endpoints: `api.imf.org/external/sdmx/2.1/`, `sdmx.oecd.org/public/rest/`, and `comtradeapi.un.org/public/v1/` (the fw-15 / D1-3 public part).
- No sidecar carries Cookie, Authorization or API-key headers (asserted in the test). The unit imports no network library; all downloads go through `ctx.fetch`.
- No challenge solving, no login, no GSTN/CBDT, no microdata.
- TradeStat was correctly **not** automated. Its form POST needs a CSRF token and a session cookie, which `ctx.fetch` does not allow, and DGCI&S re-dissemination needs written permission.
- The Comtrade 403 (an anonymous quota) was stopped, logged, and retried once, 30 minutes later, with the same plain request. That is consistent with the guide's "fetch again later" and is not a workaround.

## Findings

| # | Severity | Finding | Suggested fix |
|---|---|---|---|
| V1 | minor | **1 failing generic test:** `test_pinned_raw_file[trade_satellites:un_comtrade/ct_m_ag2_p634_251_202402.json]`. The pin and the sidecar `retrieved_at` differ (10:47:31Z vs 10:47:03Z); sha256 and bytes are identical. This is already logged as trade_satellites-14. The data are unaffected, but "`test -k <unit>` passes" (guide §10) is not met. | Orchestrator: apply the framework fix (reconcile the sidecar on reuse), or authorise a targeted re-pin of that one file. Do not hand-edit. |
| V2 | minor | **Withdrawn ISO codes in `geography`:** IMF partners YAR (Yemen Arab Republic) and YMD (Yemen, People's Democratic Republic) are stored as `geography`. The unit's own rule sends withdrawn codes (SUN, YUG, CSK, DDR, ANT, SCG) to `dim_other`. They are historical rows only (IMF annual). | Add YAR and YMD to `NON_ISO_3` in `_common.py`. The verify test pins the current state, so it will need updating when this is fixed. |
| V3 | minor | **Comtrade partner `IND` (India, code 699) = India's re-imports**, 7,315 US$ mn over FY 2023-24 in the TOTAL pulls. It sits in `geography=IND` next to ordinary foreign partners. Phase 2 could mistake it for a foreign partner, or double-count it. | Document it in the issues file. Phase 2 should exclude it or treat it as re-imports when building partner shares. |
| V4 | minor | **Issue text overstates one number:** trade_satellites-7 says FY 2017-18 drops 35,519 US$ mn of imports. That sum includes the IMF group aggregate GX901 (CIS, 11,769), which double-counts RUS/UKR/KAZ. The non-duplicated drop (countries plus TX codes) is 23,750. | Correct the issue text to about 23.8 bn of country partner-years (of which TX898 "not specified" is 8.6 bn). |
| V5 | minor | **Conservative labelling:** BaTIS measure F rows with OBS_STATUS `A` (88 in 2023–24, 785 in history) are exactly equal to the India-reported N values, yet they are labelled `estimated`. Nothing is wrongly called official. | Optional: note it in the issues file, or mark those F rows `official`. Low priority. |
| V6 | minor | **Stale issue and an inferred vintage.** (a) trade_satellites-9 says no unit publishes `INR_per_USD`. `external_sector_fx_inr_usd` now does (FY averages from 1986-87 and monthly averages from 2022-01). (b) The BaTIS vintage 2025-12 is inferred from the bulk-file name in the dataflow annotation: the HTTP Last-Modified (2024-03-10) is not credible because 2024 data are present. The dataflow also carries the annotation `NonProductionDataflow=true`, whose meaning I could not confirm. | (a) Optionally add `DEPENDS=["external_sector"]` and emit `derived` ₹ crore FY rows once external_sector passes verification; otherwise update the issue text. (b) Keep it, and note the annotation in the issues file. |

Confirmed as correctly logged by the builder (no action from me): TradeStat blocked; the Comtrade partner × chapter matrix covers only the top 30 partners (81.9%); BaTIS balanced ≈ 66% of reported, so shares only; S2 calendar-year only, with FY weighting left to Phase 2; IMF annual world imports understated before 2006; IMF DERIVATION_TYPE M; IMF licence "All Rights Reserved" needs owner confirmation; the Comtrade FY 2023-24 datasets were last released in May 2024, while the IMF vintage is August 2026. Different vintages may explain part of the 0.1–0.4% Comtrade–IMF gap; I have not verified this.

## Close-out pass (2026-09-29)

Verifier: the same independent agent role (did not build the unit). Scope: re-run the spot-check against the pins and build as they stand now, re-derive anything that changed, and add checks where the first pass left a gap.

### Verdict

**Pass. 0 mismatches in 240,746 values, and every first-pass finding is closed or dispositioned.** No value expectation needed to change.

### What changed since the first pass

| Change | Who | Effect on this unit | Re-checked how |
|---|---|---|---|
| Pin repair for trade_satellites-14 (fw-19). `retrieved_at` of `un_comtrade/ct_m_ag2_p634_251_202402.json` changed from 10:47:31Z to 10:47:03Z. | framework | This is the only line changed in `data/raw_pins/trade_satellites.yaml` (`git diff`). sha256 `ae5fc37a…` and 273,243 bytes are unchanged. It changes provenance record `trade_satellites:7d250ea47274` and the derived record `trade_satellites:b52cce2fc063` that cites it. | Pin = sidecar for all 212 pins (sha256, bytes, url, retrieved_at). The record now carries 10:47:03Z. Recounted from the clean tables: **277** monthly rows point to the repaired record, and **235** FY rows point to the one derived record citing it. That matches FRAMEWORK_REQUESTS.md. All values are unchanged: the full comparison still passes. |
| V2 fix: YAR/YMD moved to `dim_other`. | builder | The spot-check assertion was already the strict form: neither code in `geography`. | Still passes. |
| D1-9 geography code set (`pipeline/core/geo.py`, schema check). | framework | None. It governs `IN-..` codes only; this unit writes partner ISO 3166-1 alpha-3 codes. | Build validates; `repro` OK. |
| Unit code and unit tests. | none | `pipeline/ingest/trade_satellites/` and `tests/units/test_trade_satellites.py` have no diff against HEAD. | `git diff --stat` |

### Changes to `tests/verify/test_trade_satellites_spotcheck.py`

- **Checks and expectations:** none weakened, none changed. All 30 first-pass tests pass unchanged against the current pins.
- **Added: section 7, provenance against the current pins.** The first pass checked provenance by hand but never pinned it in the test. There are 4 new tests, now 34 in total, about 8 s:
  - `test_pins_agree_with_sidecars`: for every one of the 212 pins, the pin equals its `.meta.json` (sha256, bytes, url, retrieved_at), and the file size matches. The repaired pin's 10:47:03Z and sha256 are typed in.
  - `test_provenance_records_match_current_pins`: every one of the 233 records that cites a raw file cites it exactly as pinned now (sha256, url, retrieved_at, source_id). Every data pin is cited. Only the 4 metadata files are uncited: the IMF attribute file, the `CL_IMTS_COUNTRY` codelist, the getDA listing and the BaTIS dataflow. Every record is used by at least one row, and no row points to a missing record.
    - When I first wrote this test, it flagged `imts_cl_country.xml` as uncited. I opened it: it is the SDMX codelist (359 codes), used for partner names, and it carries no values. So the test's expectation was wrong, not the unit, and I added the file to the metadata list.
  - `test_rows_point_to_the_raw_file_that_holds_them`: for all 230,623 official and estimated rows, the record's status and vintage equal the row's. For each Comtrade row, the JSON file named by its record actually contains that (flow, HS chapter, partner, month) record. IMF and BaTIS rows point to the right CSV.
  - `test_derived_fy_rows_cite_their_monthly_inputs`: each IMF and Comtrade FY row's derived record lists the prov_ids of the 12 monthly rows it sums, and all its inputs are official.
- **Mutation check for the new tests:** run on in-memory copies. Each of these 4 perturbations was caught:
  - putting back the pre-repair 10:47:31Z;
  - pointing one Apr-2023 Comtrade row at a May-2023 pull;
  - dropping one input from a derived FY record;
  - adding an orphan record.

### Runs (all offline, from pins)

| Step | Result |
|---|---|
| `fetch trade_satellites --offline` | OK, 212 raw files |
| `repro trade_satellites` | REPRO OK: 9 files byte-identical across hash seeds and 1 or 4 threads, and they match `data/manifest.json` |
| `manifest --check` | up to date |
| `test tests/verify/test_trade_satellites_spotcheck.py` | **34 passed** |
| `test -k trade_satellites` | **332 passed, 0 failed.** The first pass had 325 passed and 1 failed. The raw-pin test `test_pinned_raw_file[trade_satellites:un_comtrade/ct_m_ag2_p634_251_202402.json]` now passes. |
| `coverage trade_satellites` | S1 partial, S2 partial, nothing BROKEN |
| `ruff check` on the spot-check file | clean |

### Builder's corrected issue text, re-derived from raw

- **trade_satellites-7 (V4).** IMF monthly raw, FY 2017-18 imports, partner-years with fewer than 12 months:
  - countries 15,121.2, of which Russia 7,776.9 (11 months);
  - TX codes 8,629.1, of which TX898 8,622.5;
  - group GX901 11,768.9.
  - The non-group total is **23,750**, as the issue text now says ✔. FY 2023-24 drops 68 partner-flows worth 3,756.0, with no IMF group among them ✔.
  - A pitfall I hit while re-deriving: codes like GIB/GRL/GRD are countries. Groups are `G<digit>` or `GX<digit>`, not every code that starts with G.
- **trade_satellites-15 (V3).** Comtrade partner IND: 12 records, all imports TOTAL, sum **7,314.873** US$ mn ✔.
- **trade_satellites-5 (V5).** BaTIS F cells with OBS_STATUS A: 88 in 2023-24 and 785 in 2005-22. All equal the N value within 1e-6. No B cell has status A ✔.

### Status of first-pass findings

| # | Status now |
|---|---|
| V1 | **Closed.** The framework fixed it (fw-19). The raw-pin test passes, and the new `test_pins_agree_with_sidecars` guards against a recurrence. |
| V2 | Closed (fixed by the builder; strict assertion passes). |
| V3 | Closed (documented as trade_satellites-15; value re-derived). |
| V4 | Closed (issue text corrected; value re-derived). |
| V5 | Dispositioned (labelling kept per measure; documented in trade_satellites-5). |
| V6 | (a) The text is updated, and D1-8 defers INR conversion to Phase 2, so no DEPENDS is needed. (b) Recorded in the issues file. |

### Documentation nits (no data impact; for the orchestrator)

- **C1.** `docs/phase1/issues/trade_satellites.md` is stale in two places:
  - The verifier-findings table's V1 row still says "Still OPEN as trade_satellites-14", while the -14 row says RESOLVED.
  - The closing line still reads "327 passed, 1 failed (V1 only)".
  - Both are superseded by the framework close-out paragraph.
- **C2.** `docs/phase1/COVERAGE.md` is stale in two places:
  - Line 25 counts trade_satellites-14 among the failing tests.
  - Line 90 says "pass (1 generic raw-pin test fails, trade_satellites-14)".
  - That test now passes, so the trade_satellites row should read "pass".
