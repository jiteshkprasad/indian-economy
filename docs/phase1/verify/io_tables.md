# io_tables: independent verification (first pass)

Verifier run 2026-09-29. I did not build this unit. Regression test:
`tests/verify/test_io_tables_spotcheck.py` (18 tests, ~17 s, marker `quality`). It does not import
`pipeline.ingest.io_tables`.

## Verdict

**The values pass. No blocker or major findings.** Every one of the 114,970 clean values was compared with
the raw file it comes from, using a different parser from the builder's. There were 0 mismatches and no
raw cell was dropped. The unit's own claims hold: the build is reproducible, the sha256 pins match, the
43/44 swap is real, the note totals are right, and the concordance is complete. Eight minor findings follow
(provenance wording, documentation, one process question). None of them changes a number.

## What I ran

| Step | Result |
|---|---|
| `fetch io_tables --offline` | OK, 10 raw files, hashes match the pins |
| `build io_tables` | OK, 7 datasets (row counts as reported); PJ warning for the energy PSUT |
| `test -k io_tables` | 156 passed |
| `test tests/verify/test_io_tables_spotcheck.py` | 18 passed |
| `repro io_tables` | "REPRO FAILED: code_hash changed between builds" (other agents were editing `pipeline/`). The three builds were byte-identical and matched `data/manifest.json` for all 9 files. This confirms io_tables-15 and FR-3 |
| `coverage io_tables` | 31 refs, no BROKEN; OFFICIAL covered=17, partial=2 |

## Method (independent parser)

- **SUT xlsx:** read with python-calamine (the builder uses openpyxl).
  - Products are keyed by the serial number in column A, memo rows by their label, and industries by
    column position C..BQ.
  - Valuation and final-use columns are keyed by header text through my own map.
  - Every clean row of `sut_supply`, `sut_use` and `sut_va` is matched to its raw cell: value within 1e-6,
    plus the row label, column label, unit, price basis, base year, vintage and status.
  - In reverse, every non-blank numeric raw cell must be in the clean table.
  - Mutation checks confirmed the tests catch problems. They catch a changed value, two swapped industry
    codes, a wrong period and a dropped row.
- **SUT note PDF:** 36 values, checked two ways.
  - (a) By eye: I read the pypdf page text of PDF pages 20-22 and copied the numbers into the test
    constant `NOTE`.
  - (b) Mechanically: the numbers in reading order from pypdf. The builder uses pdfplumber tables.
- **ADB xlsx:** calamine. The code row is found by searching, not by position.
  - All 19 sheets and all 63,042 cells are compared both ways.
  - Each sheet's vintage is checked against its own 'as of ...' stamp.
- **OECD ICIO zip:** pyarrow.csv plus numpy (the builder uses polars).
  - I recomputed the domestic block, the imports summed over the 80 non-India economies, the exports summed
    over all non-IND columns, and TLS/VA/OUT.
  - All 41,076 values match to a relative 1e-9, and the official/derived status matches for every row.
  - The CSV structure checks out: 81 economies with 3-letter codes, 50 industries plus 6 final-demand
    columns each, and no extra columns.
- **IFPRI PDF:**
  - Table 8 (50 cells): I copied the values by eye from page 24. The printed rows leave cells blank, so I
    assigned each number to its column by re-adding every row and column to its printed total, within
    2 bn. Clean = value x 100 (bn to crore) in every cell.
  - Tables 10 and 11 (144 cells): parsed from the pypdf text of page 26, plus 6 cells checked by eye.
- **Concordance:** I rebuilt the SUT-to-SAM34 map from the markdown table in ACCOUNT_STRUCTURE s.2.
  - It equals both item-level CSVs.
  - The range strings in `io_tables_sam34_sectors.csv` agree with the item-level files.
  - The concordance labels equal the raw header and row labels in both years.

Seed 20260929. `test_seeded_sample_report` prints 100 stratified rows (2 per dataset x period x item). For
example, `supply.cif_adj.sut_p143` 2023-24 = -24,164.2365 in both clean and raw, and
`use.gfce.sut_p001` 2023-24 = 1,01,441.2133 in both.

### Counts

| Dataset | Values | Compared | Mismatched |
|---|---|---|---|
| io_tables_sut_supply | 2,839 | 2,839 | 0 |
| io_tables_sut_use | 6,979 | 6,979 | 0 |
| io_tables_sut_va | 804 | 804 | 0 |
| io_tables_sut_note_totals (PDF) | 36 | 36 (all by eye + pypdf) | 0 |
| io_tables_adb_ind_iot | 63,042 | 63,042 | 0 |
| io_tables_icio_india | 41,076 | 41,076 | 0 |
| io_tables_ifpri_2223_datapaper (PDF) | 194 | 194 (50 by eye, 144 by pypdf + 6 by eye) | 0 |
| **Total** | **114,970** | **114,970** | **0** |

## Systematic checks

| Check | Result |
|---|---|
| Scale | SUT is Rs crore as captioned. IFPRI Table 8 is Rs bn converted x 100. IFPRI population is millions converted to a count, per-capita spending Rs '000 converted to Rs. ADB and ICIO stay US$ million. No lakh/crore slip |
| Signs | Subsidies negative as published (total -5,76,422). Margins supplied by trade and transport are negative on products 132 and 135-139 (sum -39,60,078). Net production taxes negative in total (-57,442, = note). No flips |
| Period labels | SUT sheets are named by FY. ADB sheet Y becomes FY Y-(Y+1): with the 2022-23 sheet, VA (US$ 3,135,712 mn) x 78.6045 = Rs 246.48 lakh crore, which is the registry's old-base FY 2022-23 GVA check. This is still an inference (see V-7). ICIO year Y becomes FY Y-(Y+1), per the registry |
| Base and price basis | SUT is `current`, base 2022-23. ADB and ICIO have no base_year, and the provenance notes say "old 2011-12 base". IFPRI is `estimated` |
| Vintages | SUT and note 2026-08-31 (HTTP Last-Modified 31 Aug 2026). ADB uses each sheet's stamp (2024-08 / 2024-09 / 2025-08). ICIO 2026-05-18 (Last-Modified). IFPRI 2024-10-01 (cover) |
| Dropped rows/columns | None. Every non-blank raw cell is present for SUT, ADB and ICIO under their definitions |
| Duplicated totals | 'Total' rows and memo rows carry their own product codes (`total`, `cif`, ...). Sums over `sut_p*` are safe. See V-2 for the CIF Adj exception |
| Label vs position | SUT, ADB and ICIO rows are asserted by label/code, and my test confirms the labels on every row. The IFPRI Table 8 columns come from x-positions, and my by-eye copy agrees in all 50 cells |
| Status | Only ICIO imports and exports sums are `derived`, with a method in the provenance. IFPRI rows are `estimated`. Nothing derived is marked `official` |
| Coverage claims | Each claimed total matches raw: P3 -39,60,078; P5 64,79,296; P6 69,46,906; P7 30,15,341; P8 2,28,887; P9 -5,76,422; C1 1,64,15,547; C2 31,21,027; I1 92,45,762; I3 3,82,329; I2/I2a valuables 3,76,232, all on product 125; D2 CIF +2,12,499; V1 94,42,896. S6, F3, F4 and T3a are correctly not declared |
| 43/44 swap (Q1) | Confirmed in the raw 2023-24 file. The row labelled 43 'Natural Gas' is produced by industry 6 (1,79,517) and carries 11,67,334 of imports. In 2022-23, product 43 is produced by industry 7 |

## D1-1 / D1-2 compliance

- Every download went through `ctx.fetch`.
  - Each meta sidecar shows one attempt, HTTP 200, no redirects and no request body except the MoSPI
    listing POST (the site's own public JSON API).
  - Request headers are the standard browser-like set (no Cookie, Authorization or token).
- No GSTN, CBDT or microdata source is used. The IFPRI Dataverse dataset (guestbook) is not fetched.
- OECD ICIO:
  - The zip was served with HTTP 200 by a Cloudflare edge, with no challenge.
  - The fetch code catches `AccessBlocked` and only logs it; it never retries.
  - The registry's access note from the same day says the zip returned a Cloudflare 403. Nothing suggests a
    challenge was solved. The note is out of date and the orchestrator should update it.
- IFPRI paper licence: confirmed through the CGSpace API (`/server/api/pid/find?id=hdl:10568/155099`):
  `dcterms.license: CC-BY-4.0`, `dcterms.accessRights: Open Access`. This closes the open point in
  io_tables-12. For the process side, see V-4.

## Findings

| # | Severity | Finding | Suggested fix |
|---|---|---|---|
| V-1 | minor | The ADB provenance locator says cols `D:AR (c1-c35, F1-F6, TOTAL)`, but TOTAL is in column **AS**: c1 is in D, c35 in AL, F1-F6 in AM-AR. A reader would land on Exports | In `adb.py`, change the locator to `D:AS` or compute it with `get_column_letter` |
| V-2 | minor | io_tables-5 says the 'Total' rows equal the 155 product rows. This is true for every column except **CIF Adj**. There the product rows sum to -2,12,499, the CIF memo row is +2,12,499, and the printed Total is 0, so it includes the memo row. `supply.cif_adj.total` = 0 is a trap for Phase 2 | Add the exception to io_tables-5 and to the D2/P6 coverage notes. Pinned by `test_sut_memo_rows_total_rule_has_an_exception` |
| V-3 | minor | The Q1 swap is flagged only in the provenance notes. The same `series_id` (`...sut_p043...`) means gas in 2022-23 and crude in 2023-24, and the 2023-24 `item_label` says 'Natural Gas' on crude data. A time series of the top ~50 flows (Phase 2) would show a spurious 5x jump | Add a machine-readable flag to the 2023-24 p043/p044 rows (e.g. `dim_other='label_swap=q1'`), or record it in the Phase 2 input spec. Values unchanged |
| V-4 | minor (process) | The IFPRI paper was added as a new registry id (`..._paper`) next to a source the policy refuses (`requires: registration`). Guide s.4 says: "If another source has a public part, file a Framework request; do not work around the refusal." In substance it complies: it is a different CGSpace item, Open Access, CC-BY-4.0, with no guestbook | The orchestrator decides: accept the registry addition (licence now confirmed; set verification to verified) or move it to `PUBLIC_PARTS` |
| V-5 | minor | The note locator for Table 9.2 says "printed pages 14-16"; Table 9.2 is on printed pages 15-16 | Build the printed page range per table |
| V-6 | minor | `repro io_tables` fails on code_hash whenever another agent edits `pipeline/`. The outputs are byte-identical | FR-3 as filed by the builder |
| V-7 | minor | The ADB convention "year label = FY start year" is still an inference. It is consistent with the registry check, which reproduces old-base FY 2022-23 GVA, but no ADB document confirms it | Keep the 'inference' note. Confirm in the ADB MRIO documentation before any time series uses ADB levels |
| V-8 | minor | The registry says ICIO was blocked by a Cloudflare challenge; the unit pinned it the same day without one. The registry quirk "r62, r63, trs rows zero" is wrong for trs in 2000 and 2007-2014 (io_tables-6b) | Orchestrator: update the `oecd_icio_2025` access notes and the `adb_mrio` quirks |

Not verified: the energy PSUT (Energy Statistics Ch. 9). It is parsed but no dataset is written until the
`PJ` unit exists (FR-1). Its 324 cells should be spot-checked against the PDF when that dataset first
appears. (Done in the close-out pass below.)

## Close-out pass (2026-09-29): energy PSUT and S6

Verifier run 2026-09-29, after the builder's S6 follow-up (energy.py dimensions, S6 coverage entry, new
PSUT unit tests). I did not build this unit. Scope: the new dataset `io_tables_energy_psut` (324 rows),
the S6 coverage claim, and the builder's statements in the issues file ('S6 follow-up', io_tables-7/14/16/17).

### Verdict

**The values pass, and so do the dimension relabelling and the S6 claim. No blocker or major findings.**
All 324 PSUT rows match the PDF under a second text engine and an independent way of assigning columns.
There are 0 mismatches and no printed cell is dropped. Every builder statement I checked holds. The
four findings below are minor (a Phase 2 caution, two documentation points and one orchestrator
item), and none of them changes a number. This closes io_tables-16 from the verifier side.

### What I ran

| Step | Result |
|---|---|
| `fetch io_tables --offline` | OK, 10 raw files; `es2026_chapter_9.pdf` sha256 `d4ebae86...` matches its pin |
| `test tests/verify/test_io_tables_spotcheck.py` before my edits | 18 passed. No expectation was stale, so none was changed |
| `test -k io_tables` before my edits | 198 passed (as the builder reported) |
| `test tests/verify/test_io_tables_spotcheck.py` after my edits | **24 passed** (18 unchanged + 6 new PSUT tests), ~27 s |
| `test -k io_tables` after my edits | **204 passed** |
| `repro io_tables` | REPRO OK (10 files byte-identical, matching the manifest) |
| `coverage io_tables` | OFFICIAL covered=17, partial=3 (of 20); S6 `partial` from `io_tables_energy_psut`; no BROKEN |

### Changes to the spot-check (`tests/verify/test_io_tables_spotcheck.py`)

- No existing test or expectation was changed. The first-pass tests still pass against the current pins.
- Six tests were added. They still do not import `pipeline.ingest.io_tables`.
  - `test_psut_every_clean_row_matches_raw_and_nothing_dropped`: an **exhaustive** check of all 324 rows,
    both ways. Each stored value must equal its printed token rounded to 6 dp. The only token with more
    than 6 decimals is 0.16179072 (Table 9.3 (B), coal, ISIC A), which confirms io_tables-17b.
  - `test_psut_metadata_and_provenance`: unit, price basis, status, period and `fy`, estimate stage
    (2023-24 `n.a.`, 2024-25 `Provisional`), stock_flow, geography, side, and vintage. It also checks
    every row's provenance record: table id, pin hash, `PJ` and no conversion, and a locator that names
    the right PDF page and caption.
  - `test_psut_dimensions_follow_the_printed_column`: each column's industry, institution and
    counterparty come from my own map, the product from my own row map, and `dim_other=psut_column=<col>`.
  - `test_psut_column_assignment_reproves_printed_subtotals`: see the method below. It also checks the
    row identities, the TOTAL rows, and the io_tables-8 gap of 129 / 145 PJ.
  - `test_psut_seeded_eye_sample`: **36 rows** (11% of 324, above the minimum of 30), drawn with
    `random.Random(20260929)` from the sorted (table_id, series_id) keys. I typed the values from the
    pypdf page text and placed each number in its column by re-adding the printed rows and sub-totals by
    hand. The derivation is in the comments of the `PSUT_EYE` constant.
  - `test_psut_s6_coverage_claim`: see 'S6 claim' below.
- Mutation checks were run from a scratch harness that swaps the clean rows or the raw parse. Each
  planted error made at least one new test fail:
  - a changed value (6902 -> 6903);
  - a flipped sign on a statistical-difference cell;
  - an industry code swapped (transport -> construction);
  - a wrong period;
  - a wrong vintage;
  - a missing product;
  - a dropped row;
  - a raw column shift (gas transport -> ISIC D), which simulates a parser misassignment. The sub-total
    test and the S6 test both caught this one.

### Method (independent of energy.py)

- **Text engine: PDFium (`pypdfium2`)**, reading character boxes. The unit uses pdfminer through
  pdfplumber. Words are split on whitespace or on gaps. Loose (font) boxes are used so that descenders
  do not break lines apart.
- **Columns anchored on the header words.** Each column is anchored on the right edge of its own header:
  'A)'-'D)' on the ISIC line, 'Transport*', 'Construct*', the second 'Industries', 'Househol*',
  'Accumulati*', 'Export', 'Statsitical', '(Imports)', 'Environm' and 'Total'. The anchors must run left
  to right in the expected order, and every number must lie within 15 pt of its nearest anchor. The unit
  instead anchors on the TOTAL row's numbers, so a shared error would need both methods to fail in the
  same way.
- **A second proof from rows the unit does not ingest.** The printed sub-total rows are:
  - 'Total' (natural inputs; supply production);
  - 'Total Transformed Energy';
  - 'Total End Use for Energy purposes' (overprinted as 'purposes1133' in 2024-25);
  - 'Total energy residuals'.

  For each one (14 in all), I compared the non-zero column sums of its block, in column order, with the
  printed non-zero numbers. All agree within 2 PJ. This matters because the blanks in rows such as
  2023-24 coal end use ('0.089786 2.112574 6902 0 0 48 0 431 44 -344 7083', with 11 numbers for 13
  columns) cannot be placed from the text alone. The position check and the sub-total check agree with
  the unit on every cell: ISIC D and Construction are blank there, and 48 is Other industries.
- **Row codes come from an explicit label map**, not from the unit's `slug()`. The two printed blank
  rows (supply 'Energy from solid waste') are allowed by name only.

### Builder claims checked

| Claim | Result |
|---|---|
| 324 rows; values, series ids, labels and provenance unchanged | 324 rows (56/106/56/106), and every value equals the PDF. The 4 provenance records point to PDF pages 12-15 with the right captions, and the sha256 matches the pin |
| Only the 7 industry columns set `industry`; households set `institution`; imports/exports set RoW; flows from/to the environment set `environment`; `psut_column` on every row | Holds for all 324 rows |
| Energy rows carry their product | Holds. Every row in the natural-inputs and energy-products sections whose label is a product gets it; 'End-use ... non-energy purposes', residuals and totals get none. See finding C-2 on the naming |
| S6 = 37 series of Table 9.2 (B), 2023-24, partial | Holds exactly (see below) |
| End use by industry adds up to the printed 'Total End Use' row within 2 PJ | Reproduced independently: 1183, 497, 10682, 384, 5783, 19, 6472 |
| Each printed row adds up to its Total column in all 4 tables | Reproduced independently (2 PJ) |
| Coverage 17 covered + 3 partial of 20 | Reproduced by `coverage io_tables` |
| `KToE` not applicable | Confirmed: all four tables print '(Unit:PJ)' only |
| io_tables-17(a): '(ISIC M)' under Transportation & Storage in all four tables, plus a stray '(ISIC D)' on the use pages | Confirmed on all four pages |
| Vintage 2026-03-30 | Consistent with the evidence. The registry's press-release date is 30 Mar 2026 (upload stamp 1774858925751 ms). The PDF `/ModDate` is 24 Mar 2026, before the release. The server's Last-Modified (15 Apr 2026) is only the upload date |

### S6 claim

The 37 declared series are exactly the printed cells of Table 9.2 (B) that sit in the seven industry
columns, in the transformation and end-use sections, excluding 'End-use ... for non-energy purposes':

- 32 end-use cells: coal, lignite, oil products and natural gas each have 6 (not ISIC D, which is
  printed blank); crude oil has 1 (other industries); electricity has 7;
- 5 transformation cells: crude oil in ISIC C; coal, lignite, oil products and gas in ISIC D.

Nothing else is included: no households, totals, natural-input extraction or statistical difference.
All 37 series exist for 2023-24. `partial` is the right extent, because the table has 7 groups while S6
needs 34 activities.

### Findings

| # | Severity | Finding | Suggested fix |
|---|---|---|---|
| C-1 | minor (Phase 2 caution) | **Crude oil 'end use' by Other industries** is 1,140 PJ in 2023-24 and 1,185 in 2024-25 (P). The statistical difference almost cancels it (-1,052 / -1,043), leaving printed totals of only 89 / 142. The position is certain (x = 355 under 'Industries'), and the column sums reproduce the printed Other-industries end use of 6,472. So this is as published, not a parsing error. But crude oil is hardly ever an end-use fuel, and the cell is one of the 37 S6 series. It makes up about 18% of 'other industries' energy use in 2023-24 (1,140 of 6,472). Neither the S6 coverage note nor the issues file mentions it | Unit: add it to io_tables-17 and to the S6 note. Phase 2: before splitting other industries across SAM activities, treat it as a probable publication artefact (for example, compare it with the Energy Balance / API series) |
| C-2 | minor (docs) | **`product` codes are shared between the natural-inputs and energy-products sections.** Natural-input 'Coal' (extraction, 16,906 PJ) and the energy product 'Coal' (supply 22,836) both carry `product=coal`. The docstring calls `nuclear`, `inputs_from_res` and `hydro` 'SIEC class slugs', but they are natural-input types. A filter on `product` alone mixes resource extraction with product flows | Unit: say in the docstring and issues that `item_code` (section) must be combined with `product`. Values are unaffected |
| C-3 | minor (docs) | **The TOTAL SUPPLY / TOTAL USE rows carry the column dims** (for example, `psut.use.total.total_use.isic_b` has `industry=isic_b`). Rows from other sections also carry industry dims, for example natural-input extraction in ISIC B. So `industry == 'isic_b'` returns natural inputs, end use and the grand total together, and summing it double-counts. The builder's claim ('only the 7 industry groups are marked as industries') is true per column. This is about what a filter on `industry` returns | Unit: note in the docstring that sums by industry must filter on `item_code` (S6 users should take the coverage series list). No data change needed |
| C-4 | minor (orchestrator) | `docs/phase1/COVERAGE.md` still lists S6 as missing in three places. The builder flagged this | Orchestrator: S6 is now `partial` from `io_tables_energy_psut` (37 series, 2023-24) |

### Counts (this pass)

| Dataset | Values | Compared | Mismatched |
|---|---|---|---|
| io_tables_energy_psut | 324 | 324 exhaustive (PDFium + header anchors), 36 more by eye (seeded) | 0 |
| All other io_tables datasets | 114,970 | 114,970 (first-pass tests, rerun unchanged, all pass) | 0 |
