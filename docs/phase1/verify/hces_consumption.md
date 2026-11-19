# hces_consumption: independent verification (first pass, 2026-09-29)

Verifier: an adversarial agent that did not build the unit (SPEC rule 3). I read no builder code into the check: the regression test re-parses the pinned raw files with its own code.

## Verdict

**Accepted with one major defect to fix.** All 328,697 clean values match the pinned raw documents as printed: 0 mismatches in a full census. The fetch code and meta sidecars comply with D1-1 and D1-2.

The defect is in units. In the 2022-23 round, the quantities of four fruit items are stored as tonnes, but they are counted in numbers. This affects 384 rows (verify-1 below).

## What was run

| Step | Result |
|---|---|
| `build hces_consumption` (offline from pins) | OK: 9 datasets, 328,697 rows. Two expected warnings, both for the known A6/A10S All-India rural total break. |
| `test -k hces_consumption` | 98 passed |
| `test tests/verify/test_hces_consumption_spotcheck.py` | 12 passed, **1 failed** (`test_kg_quantities_agree_with_labels_in_both_rounds`, verify-1) |
| `coverage hces_consumption` | 13 refs, all `partial`, none BROKEN |
| `repro hces_consumption` | **REPRO OK**: 3 builds byte-identical and matching `data/manifest.json`. The builder's earlier failure came from the `code_hash` race. |

## Method (`tests/verify/test_hces_consumption_spotcheck.py`)

- The test does not import `pipeline.ingest.hces_consumption`. The sha256 of each raw file is re-checked against `data/raw_pins/hces_consumption.yaml`.
- **Excel tables** (A2, A6, A10F, A10S, A10SW, CPI Annexure 5.3a-d): every clean row is checked (a census, not a sample), 328,313 values in all.
  - Parsing uses openpyxl, with the verifier's own State-name map, fractile map, A2 column map, and label normalisation.
  - Each row is matched to its raw cell by label or item code, never by position.
  - Unit conversions are re-applied independently: hundreds -> count (×100), kg -> tonnes (÷1000).
  - Completeness runs in both directions: every published value cell, and every A10F household-count cell, has a clean row.
  - The derived CPI All-India item weights are recomputed from 5.3d.
- **PDF tables** (Report 592 T3.17/3.18/3.19, Report 596 T2.21/2.24, Report 595 St. 2.3): all 384 values are checked against a pypdf re-parse (the unit uses pdfplumber). There are also 30 literal anchors that I typed by hand after reading the page text. Every PDF value was compared against the page text at least once.
- A random sample (seed 20260929) of A10F rows is printed with the raw record for eyeballing.

| Dataset | Values compared | Mismatched |
|---|---:|---:|
| a2_fractile_persons | 21,164 | 0 |
| a6_group_fractile | 81,705 | 0 |
| a10f_item_fractile (2023-24 / 2022-23) | 25,544 / 25,598 | 0 |
| a10s_state_item (2023-24 / 2022-23) | 41,893 / 42,345 | 0 |
| a10sw_state_item_imputed | 42,651 | 0 |
| cpi2024_weights (5.3a-d incl. 716 derived) | 47,413 | 0 |
| report592_mpce + health596 + cms_education_2025 (pypdf) | 384 | 0 |
| **Total** | **328,697** | **0** (value level) |

## Findings

| # | Severity | Finding | Evidence | Fix |
|---|---|---|---|---|
| verify-1 | **major** | **The 2022-23 quantities of 223 pineapple, 224 coconut, 225 green coconut and 228 orange/mausami are counts, but they are stored as kg -> tonnes.** HCES 2022-23 prints these labels without '(no.)', while the 2023-24 tables print 'pineapple (no.)', 'coconut (no.)', etc. `qty_unit()` falls back to kg for group 239. Affected: 384 rows (A10F 96, A10S 288), tagged `unit=tonnes`, `qty_published_unit=kg`, with a 'kg per person' provenance record. The 2023-24 series of the same codes are `count`. Phase 2 would join a count series to a tonnes series, and the 2022-23 values are off by a factor of 1000 and in the wrong unit. | Implied 2022-23 'kg' prices (All-India rural): orange Rs 8.22/kg, coconut Rs 20.46/kg, green coconut Rs 31.49/kg, pineapple Rs 40/kg. The 2023-24 per-number prices are orange Rs 8.61, coconut Rs 20.70, green coconut Rs 42.53 and pineapple Rs 52.17 per piece. A kg of oranges costs far more than Rs 8. Raw: `hces2223_table_a10f.xlsx` codes 223/224/225/228 have no unit tag; `hces2324_table_a10f.xlsx` has '(no.)'. | Treat these four codes as `number` in 2022-23 (explicit override, commented with the 2023-24 label), or skip their 2022-23 quantities. Log it in the issues file. The spot-check test `test_kg_quantities_agree_with_labels_in_both_rounds` passes once fixed. |
| verify-2 | minor | The HCES survey year (Aug-Jul) is labelled `period_type=fy`, and the NSS Jul-Jun rounds in T3.18 are labelled the same way. | Already logged (hces_consumption-1, FR1). Every provenance record carries the survey-period note (checked: 6 distinct notes, all explicit). | None beyond FR1. Phase 2 must use these as shares only. |
| verify-3 | minor | CMS Education St. 2.3 values are spending per student over the current *academic year*, labelled `period 2025-Q2, cq` (the survey quarter). A reader could take them for a quarterly flow. | Provenance notes say "expenditure during the current academic year"; `unit_as_published` says "(current academic year)". | Put `ref_period=academic_year` (or similar) in `dim_other`, or say it in the dataset description. |
| verify-4 | minor | The ISO codes differ across units. hces_consumption (and external_sector) use IN-CG for Chhattisgarh; state_fiscal uses IN-CT. IN-OD, IN-TS and IN-UK agree. | `state_fiscal_*` parquet files hold IN-CT; `hces_consumption_*` hold IN-CG. | Orchestrator: standardise (already raised as hces_consumption-20). |
| verify-5 | minor | CPI 5.3d 'share within State' rows carry `household_group=rural_all/urban_all`, but the share is of the State's *combined* basket (per-State shares sum to 100 across both sectors). | Builder's own check sums per State across sectors; my recomputation agrees. | Say "share of the State's combined (R+U) basket" in the item label or description. |

## Claims re-verified (all true)

- HCES 2023-24 All-India rural: food 1,938.50 + non-food 2,183.38 = 4,121.88, but A6 prints 4,121.78 (A6 rows 3226/3245/3246). The A2 MPCE is 4,121.79.
- HCES 2022-23 All-India rural persons are 869.82 mn, against 860.24 mn summed over the States: a gap of +1.11%. For 2023-24 the gap is +0.006%. Urban agrees within 0.0001%.
- The vintages match the server `Last-Modified` headers in the `.meta.json` sidecars: 2025-01-30 (HCES 2023-24 xlsx and Report 592), 2024-06-07 (HCES 2022-23 xlsx), 2026-01-29 (CPI Annexure 5.3), 2026-04-24 (Report 596, labelled 2026-04) and 2025-09-11 (Report 595, labelled 2025-08 from the cover).
- The PDF page and table locators are right. Report 592 PDF pp. 69/70/71 are report pp. 51/52/53. Report 596 pp. 55/58 are report pp. 29/32. Report 595 pp. 26-27 are report pp. 13-14.
- Price basis: T3.18 real rows are `constant_2011_12` with base_year 2011-12, and nominal rows are `current`. 'Status official' appears only on as-published numbers. A2 persons and the CPI All-India item weights are `derived`, with methods and inputs.
- Scale:
  - A2 and A10F household counts are published in hundreds and correctly multiplied by 100. The 2023-24 persons total is 1,217.6 mn (R+U).
  - Kilogram quantities: all 3-decimal kg values survive the 6-decimal tonne rounding exactly.
- Imputed rent (A6 memo, A10F 539) is published by R/U × fractile for both rounds. It sits outside every total (the build re-adds totals without it), and it matches between A6 and A10F. This matters for C4a/F3a: HCES does give an owner-occupied imputed-rent key. The gap map's statement "HCES excludes imputed rent" is true only of MPCE.
- Coverage is `partial` for all 13 refs. None is a gap-map OFFICIAL cell, and each declared series exists.

## D1-1 / D1-2 compliance

- `fetch()` uses only `ctx.fetch`: no httpx, requests or urllib, no cookies, no custom headers except a Referer for the CPI annexure, and no TLS work-around.
- All 13 sidecars show HTTP 200 with no redirects and `access_policy: D1-1`.
- `SOURCES` excludes `mospi_hces_unit_data` and the two NSS unit-data ids. The report-PDF registry additions have `requires: none` and state that the unit data are not used. No microdata.gov.in, GSTN or CBDT host was contacted.
- Not verifiable offline: the claimed HTTP 404 for the 2022-23 A10SW. I did not re-probe it (it needs network; the claim is plausible).

## Recommendation

Fix verify-1 (a small override in `qty_unit` for 2022-23 codes 223/224/225/228), rebuild, and re-run `tests/verify/test_hces_consumption_spotcheck.py`. Then the unit can be accepted. verify-3 and verify-5 are documentation tweaks. verify-4 is for the orchestrator.

---

# Second pass (2026-09-29): fix confirmation and regression hunt

## Verdict

**Accepted.** verify-1 is fixed and I found no regression. The V3 and V5 wording fixes are in the data. A full census of all 328,697 values against the raw files gives 0 mismatches. Remaining items are minor or belong to the orchestrator (see below).

## What was run

| Step | Result |
|---|---|
| `fetch hces_consumption --offline`, then `build hces_consumption` | OK: 13 raw files, 9 datasets, 328,697 rows. **A10F has 51,142 rows**, so the builder's report of 0 was only a reporting slip. The two known A6/A10S warnings still fire. |
| `test tests/units/test_hces_consumption.py tests/verify/test_hces_consumption_spotcheck.py` | 66 passed (45 unit + 21 spot-check) |
| `test -k hces_consumption` | 120 passed |
| `test tests/hygiene -k hces` | 2 passed |
| `repro hces_consumption` | REPRO OK (11 files byte-identical, matching the manifest) |
| `coverage hces_consumption` | 13 refs, all `partial`, none BROKEN |

## verify-1 fix: confirmed

- 2022-23 codes 223/224/225/228 are now `unit=count` with `qty_published_unit=number`: A10F 96 rows, A10S 288 rows.
- The values are printed as-is, not divided by 1000: all 384 were matched to raw by label.
- The 2022-23 raw labels really lack '(no.)'.
- Their provenance records say 'number per person per 30 days', conversion 'none', and the locator names the override. The 2023-24 records are unchanged.
- Anchor: 2022-23 A10F rural 0-5% coconut = 0.068.

## Regression hunt

- **Cross-round unit agreement.** 201 quantity codes in A10S; none carries different units in the two rounds. Four codes have a quantity in one round only:
  - 057, 058 and 060 are 2022-23 PDS maize/jowar/small-millet lines that are absent from the 2023-24 table.
  - 065 is the 2023-24 'maize-free' line.
- **Implied unit values** (value/qty, All-India, per round). No item comes near a x1000 ratio. Seventeen items lie outside x0.75-1.4, but all are tiny PDS/free-grain quantities (rounding noise) or high-variance goods (mobile handset, quilt).
- **Within-round prices.** kg prices range from Rs 2.9 (dung cake) and Rs 5.7 (PDS rice) to Rs 682 (almonds and other nuts). Items counted in numbers without a '(no.)' label are all durables or non-food goods (water bottle Rs 77 to mobile handset Rs 12,315). Nothing looks mislabelled.
- **Tag consistency.** In A10F, A10S and A10SW, every quantity row pairs `tonnes` with kg, 'kg per person' and x0.001, and `count` with number, 'number per person' and conversion none.
- **V3.** All 54 CMS rows carry `ref_period=current_academic_year` and the description explains 2025-Q2.
- **V5.** The 5.3d official rows carry `share_of=` tags. Within-State shares sum to 100 +/- 0.00002 per State over both sectors, which is what the tag claims.
- **D1-1/D1-2.** `fetch()` is unchanged: only `ctx.fetch`, with one Referer. All 13 sidecars show HTTP 200, no redirects and access_policy D1-1. No httpx, requests, urllib, cookie, login or TLS work-around appears in the unit code. No microdata.

## Tests added (spot-check file extended, nothing replaced)

- `test_quantity_unit_is_the_same_in_both_rounds` (A10F, A10S). Mutation-tested: re-injecting the old defect makes it fail on 223/224/225/228.
- `test_qty_published_unit_tag_agrees_with_unit_and_provenance` (A10F, A10S, A10SW).
- `test_implied_unit_values_join_across_rounds`. It covers 150 series, and the four fixed codes must lie within x0.7-1.5. Mutation-tested: dropping the kg -> tonnes conversion for 2022-23 fails at about x1000. It cannot see a label-only slip like verify-1; the docstring says so.
- `test_counted_fruit_2223_values_as_printed`: the 384 fixed rows against raw, plus an anchor.
- `test_wording_fixes_v3_v5`.

## Remaining findings (second pass)

| # | Severity | Finding | Fix |
|---|---|---|---|
| verify-6 | minor | The 716 derived All-India 5.3d rows (`status=derived`) have `dim_other` null. The official 5.3d rows now carry `share_of=all_india_combined_basket`, and the derived rows are the same kind of share. | Add the same tag to the derived rows, for consistency. |
| verify-7 | minor | The builder's report gives `rows: 0` for a10f. The true count is 51,142 (from the rebuild), and the total of 328,697 is right. | None in the data. The orchestrator should take row counts from `_datasets.json` or the manifest. |
| verify-2, verify-4 | minor | Unchanged: `fy` labels on survey years (FR1), and the Chhattisgarh ISO code IN-CG vs IN-CT (orchestrator). | As in the first pass. |

---

# Close-out pass (2026-09-29): survey-window periods, shared State codes, verify-6

## Verdict

**Accepted.** All three builder changes are right, and they changed only what the builder said they changed. I diffed the build myself against the previous clean output at git HEAD, joining on series_id, vintage and the old FY label mapped to the new window. All 328,697 rows match with 0 unmatched and 0 value changes. The only columns that changed are:
- `period` and `period_type` on every HCES and Report 592 row;
- `prov_id` on the same rows;
- `dim_other` on exactly the 716 derived CPI rows (null -> `share_of=all_india_combined_basket`).

Geographies, units and series ids are identical. The only provenance change apart from notes and ids is the `inputs` of the two derived A2 records, which now point to the re-issued ids of the same round's cols D:J records (correct).

I made no value-level findings. Two minor points are below.

## What was run

| Step | Result |
|---|---|
| `repro hces_consumption` | REPRO OK: 11 files byte-identical across seeds and threads, matching `data/manifest.json`. So the clean output on disk is what the current code builds. |
| `coverage hces_consumption` | 13 refs, all `partial`, none BROKEN. `coverage.py` requires every declared series to exist in the named `period`, so the new `2023-08/2024-07` entries were really resolved. |
| `test tests/verify/test_hces_consumption_spotcheck.py` | 30 passed (was 12 failed / 64 passed before this update, on empty selections) |
| `test -k hces_consumption` | **139 passed**, 0 failed |
| `test tests/cross` | 172 passed, 21 xfailed, **3 failed**: HH-1-2022-23, HH-1-2023-24, HH-7-2023-24. These are reconciliation-owned (`recon_lib.hces_aggregate` still selects `"2023-24"`/`"2022-23"`); see hces_consumption-26(b). Not fixed here: not my file. |
| Mutation test (9 injected defects on scratch copies of the clean output) | **All 9 caught** (see below). |

## Independent derivation of the windows (nothing taken from the unit)

- **HCES 2023-24 = `2023-08/2024-07`.** The test parses it from the pinned Report 592 text: p.3 cover "Survey on Household Consumption Expenditure: 2023-24 ... August, 2023 – July, 2024"; p.9 repeats it.
- **HCES 2022-23 = `2022-08/2023-07`.** Parsed from p.20: "last survey has been conducted in during August, 2022 to July, 2023 (2022-23)"; p.9 repeats it.
- **Table 3.18 NSS columns.** The page prints each heading with its round ("1999-'00 NSS (55th round)", 2004-05 61st, 2009-10 66th, 2011-12 68th); the test asserts those pairs from the page text. The months are **not printed** in the report. I re-checked them myself on 2026-09-29 in the IHSN catalogue, "dates of data collection":

  | Round | IHSN entry | Survey window |
  |---|---|---|
  | 55th | catalog.ihsn.org/catalog/2606 | 1 Jul 1999 - 30 Jun 2000 |
  | 61st | /1910 | 2004-07 to 2005-06 (four sub-rounds) |
  | 66th | /1903 | 2009-07 to 2010-06 |
  | 68th | /3281 | 2011-07 to 2012-06 |

  All four agree with the builder's labels. The provenance notes say where the months come from.
- **Kept calendar periods (hces_consumption-27): agreed.** Report 596 p.3 prints "January – December, 2025", so `cy 2025` is right under PIPELINE_GUIDE §5.2. Report 595 p.2 prints "April - June, 2025", so `cq 2025-Q2` is that exact window. For the CPI, `cy 2024` is the index base year; the HCES weight reference window is stated in every CPI provenance note. The annexure itself does not print the base year. The build does not rest on that label, and it is unchanged from the accepted earlier passes.

## Spot-check changes (tests/verify/test_hces_consumption_spotcheck.py)

**Updated, not loosened.** Every period selection now goes through `sy(round)`, which is parsed from the report text as above. Table 3.18 rows are keyed by their printed column heading (via the window-to-heading inverse), and the expected period of each PDF value is its column's window. No tolerance, count or expected value was changed. `git diff` shows the only removed logic is the old period literals. `ruff format` also re-wrapped some pre-existing lines, with no logic change.

**New tests:**
- `test_survey_windows_are_printed_in_the_documents`: checks the windows above against the raw PDF text.
- `test_period_census_every_row`: all 328,697 rows.
  - HCES Excel rows: the series tag (`hces2324`/`hces2223`) and `source_id` must agree and imply the window.
  - Report 592: `sy` throughout. T3.17/T3.19 carry the 2023-24 window. In T3.18, plain MPCE spans the six windows and "with imputation" only the two HCES windows.
  - Report 596, Report 595 and CPI keep their calendar periods.
- `test_provenance_notes_name_the_row_window`: all 41 records.
  - Each HCES note's "Survey reference period ..." window must equal its rows' period.
  - T3.18 notes must name each column and IHSN.
  - Each derived record's `inputs` (stored comma-separated) must point to same-source records whose rows carry the same periods (3 links).
- `test_cpi_derived_all_india_rows_closeout` (verify-6): the 716 rows (358 items x 2 sectors) must carry the tag, `status=derived`, geography `IN`, `2024`/`cy`, and a single derived provenance record. Separately, no 5.3d row may be untagged. A seeded sample of 80 rows (11%, seed 20260929) is re-summed from 5.3d col N with **python-calamine**. The existing `test_cpi_census` still re-sums all 716 with openpyxl.
- `test_calamine_seeded_sample_of_changed_rows[5 datasets]`: a seeded 10% sample of every changed HCES Excel row is re-read with calamine, a second xlsx reader (the unit and the census use openpyxl). Each sampled row must match on value, geography, household group and window. 0 mismatches:

  | Dataset | Sampled | Of |
  |---|---:|---:|
  | A2 | 2,117 | 21,164 |
  | A6 | 8,171 | 81,705 |
  | A10F | 5,115 | 51,142 |
  | A10S | 8,424 | 84,238 |
  | A10SW | 4,266 | 42,651 |
  | **Total** | **28,093** | |

  The census still covers 100% of values: 328,697 compared, 0 mismatched.

**Mutation test.** Each defect was injected into a scratch copy, never into data/clean:

| Injected defect | Caught by |
|---|---|
| A10F 2022-23 given the NSS-style `2022-07/2023-06` | period census, calamine sample |
| T3.18 2009-10/2011-12 windows swapped | PDF census, hand anchors |
| T3.18 NSS column left as FY `1999-00` | PDF census, period census |
| derived CPI tag removed | CPI close-out test |
| derived CPI values x1.01 | CPI close-out test |
| `IN-CG` -> `IN-CT` in A6 | A6 census, calamine sample |
| A2 rounds' windows swapped | period census, calamine sample |
| A10S kg not divided by 1000 | calamine sample |
| a 2023-24 prov note naming the 2022-23 window | provenance test |

## Other claims checked

- **State codes (D1-9).**
  - `state_geo` returns `IN` for All-India and otherwise `geo.state_code()`.
  - geo does not know "A & N Island" or "Andaman & N Island" (both raise KeyError); the unit maps them to the name "Andaman and Nicobar Islands", never to a code.
  - geo maps "Uttrakhand", "NCT of Delhi", "Orissa" and "Chattisgarh" itself.
  - The census, which uses the verifier's own State map, re-matches every geography. The HEAD diff shows no geography change.
- **FR5 / `ratio_sig_digits` revert: claim confirmed.** `tests/clean/test_clean_datasets.py::test_file_is_canonical` re-serialises with `io.parquet_bytes` at the default 6 decimals and never reads `ratio_sig_digits` from `_datasets.json`, so any opt-in dataset would fail it. The revert leaves the output as in the accepted passes.
- **eSankhyiki probe: not re-verified.** Re-checking it needs the network, and nothing was ingested or pinned. The stated count is internally consistent: 37 geographies x 2 sectors x 2 imputation types x 31 categories = 4,588. No gap-map cell depends on it.

## Findings (close-out pass)

| # | Severity | Finding | Fix |
|---|---|---|---|
| verify-8 | minor | The shared HCES provenance note says "Values are monthly (30-day) per-person averages over the survey year at current prices". It is attached to count records too: A2 households, adults and children persons (cols D:J), A2 sample households/persons (L:M), the derived A2 persons records, and A10F "households reporting" (col G). Those are estimated or sample counts, not per-person rupee averages. The wording predates this pass (same text at HEAD), and the values and units (`count`) are right. | Give the count records a count-specific note, keeping the window sentence. |
| verify-9 | minor (routed) | `tests/cross` HH-1-2022-23, HH-1-2023-24 and HH-7-2023-24 fail because `recon_lib.hces_aggregate` still selects the FY labels. This confirms hces_consumption-26(b). | Reconciliation owner: look up the HCES window of the FY being compared (FY 2023-24 -> `2023-08/2024-07`, FY 2022-23 -> `2022-08/2023-07`) and keep the Aug-Jul vs Apr-Mar note. |

**Status of the builder's issues:**
- hces_consumption-26(a) (the verifier's spot-check) is **done** in this pass.
- verify-2 (period types) and verify-6 (derived CPI tag) are **confirmed fixed**.
- hces_consumption-1 and -20 are confirmed resolved.
- hces_consumption-10 (eSankhyiki) is accepted as not needed.
