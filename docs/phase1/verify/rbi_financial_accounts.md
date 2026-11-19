# rbi_financial_accounts: independent verification

Verifier: an adversarial agent that did not build the unit (SPEC rule 3). The regression test re-parses the pinned raw files with its own code; it imports nothing from `pipeline.ingest.rbi_financial_accounts`.

## Second pass (2026-09-29): verify-1 fix confirmed, no regressions

**Verdict: accepted.** The major finding (verify-1) is fixed correctly. The four minor findings are handled as the builder reported. The full census still matches 227,362 of 227,362 values in both directions, with 0 mismatches.

| Step | Result |
|---|---|
| `fetch --offline` | OK, 14 raw files, sha256 unchanged |
| `build rbi_financial_accounts` | OK; row counts identical to the first pass (dea_gsec_ownership 750, total 227,362) |
| `test -k rbi_financial_accounts` (unit tests, generic tests, extended spot-check) | **113 passed, 0 failed** |
| `coverage rbi_financial_accounts` | OFFICIAL covered=3, partial=5; no BROKEN |
| `repro rbi_financial_accounts` | 13 files byte-identical across the 3 builds, and they match `data/manifest.json`. It still prints REPRO FAILED, only because `code_hash` changed mid-run while other agents were editing; this unit's files were not touched during the run. |

**How the fix was checked, without trusting the builder's mapping:**
- **Page text.** I re-read QR23 p.18, SP p.35 (T2.10) and QR24 p.17 (T4.4) with pypdf.
  - QR23 prints "11. Pension Fund 7.3 7.4 8.8 7.7 4.5 4.6 5.1 5.5 5.6" and "12. Others - - - - 3.5 3.6 3.8 3.9 4.0".
  - T2.10 has Pension "- - 3.5 4.0 4.5" and Others "7.2 7.3 4.5 5.6 5.8" (2020-2024).
  - QR24 has Mar.23 Pension 4.0 and Jun.23 Pension 4.2.
- **Census swap.** `dea_expected()` now derives the swap from the printed '-' pattern itself. It asserts that the printed Pension Fund row has no dashes and the printed Others row has exactly four 2021 dashes, and fails loudly if the PDF text ever differs. Only then does it key the rows as others and pension_funds. With that, the census gives 1,486 compared, 0 mismatched and 0 missing/extra.
- **Cross-table agreement.** After the swap, QR23 T4.4 agrees with every other DEA table within 0.05 (one-decimal rounding):
  - T2.10: 38 common cells, 5 of them pension/others.
  - QR24 T4.4 Mar.23: 13 cells, 2 pension/others.
  - HB-5 (two decimals, all nine quarters): 104 cells, 14 pension/others.
  - Examples: Others Sep-21 8.8 vs HB-5 8.79; Pension Mar-23 4.0 vs 3.98.
- **No early pension rows.** No DEA table has a pension-fund row before March 2022.
- **Traceability.** All 14 reassigned rows are traceable:
  - `dim_other` is `printed_as=pension_funds` (9 rows, now others) or `printed_as=others` (5 rows, now pension_funds).
  - `item_label` is the printed text, and `series_id` and `counterparty` carry the corrected holder.
  - They have their own provenance block: page 18, status official, notes citing T2.10 and QR24.
  - No other DEA row carries a `dim_other` flag.
- **Build-time guard.** `_check_qr2023_against_t2_10` in the unit would fail the build if the swap went wrong.

**Regression hunt (other tables that could hide the same kind of misprint):**
- QR24 T4.4 vs HB-5: 60 cells, max |diff| 0.05.
- T2.10 vs HB-5: 58 cells, max 0.05.
- QR24 T4.5 (T-bills) vs HBS T107 T-bills: 22 cells, max 0.05.
- Every table-date column in dea_gsec_ownership sums to 100 ± 0.2.
- No other row swap or column shift was found.

**Minor fixes re-checked:**
- verify-3: HBS T12 has base_year 2011-12 for 2011-12..2023-24 (168 rows) and null for 1983-84..2010-11 (417 rows), with separate provenance blocks.
- verify-4: the T107 merger note is logged under issue -2.
- verify-5: the three FSF dataset descriptions warn about non-additivity.
- verify-2: the timing disclosure is exact.
- T11 base-year tags are unchanged (51 + 51 rows).
- Fetch code (`fetching.py`) is unchanged since the first pass. There is no Cookie/Authorization header, no challenge handling and no GSTN/CBDT/microdata. The sidecars show only public dea.gov.in, www.rbi.org.in and rbidocs URLs.

**Spot-check test changes (`tests/verify/test_rbi_financial_accounts_spotcheck.py`, extended, nothing removed):**
- `dea_expected()`: independent, pattern-guarded QR23 swap.
- `test_qr2023_pension_others_labels_agree_with_status_paper`: now also compares against QR24 T4.4 and HB-5, checks for pension rows in every table, and checks page-text values.
- New `test_qr2023_swap_flags_and_provenance`: checks `dim_other`, the printed `item_label` (re-parsed from the PDF), the separate provenance block and its notes.
- New `test_second_pass_minor_fixes`: checks the T12 base_year and the FSF descriptions.
- 10 new hand anchors typed from QR23 p.18, SP p.35, QR24 p.17 and HB-5. There are now 49 anchors, of which 44 are PDF values.

**Residual notes (minor, no action required):**
- **verify-6: `item_label` is the misprinted text on the 14 reassigned rows.** The rows with counterparty `others` have item_label "11. Pension Fund". This is deliberate and flagged in `dim_other` and the provenance, but a consumer that selects rows by `item_label` would get the misprint back. Phase 2 should key on `counterparty`/`series_id`, never on `item_label`. Optionally, the unit could use a label such as "Others (printed as '11. Pension Fund')".
- **R3a/K8d.** The coverage file cites only `qr2024_t4_4`, `qr2024_t4_5` and `sp_hb5` series for R3a. The Jan-Mar 2023 end point that R3a averages is now correct in all three DEA sources (QR23, QR24 Mar.23 and T2.10/HB-5), and they agree within rounding.

# First pass (2026-09-29)

## Verdict

**Accepted with one major defect to fix.** A full census found that all 227,362 clean values equal the pinned raw documents as printed, with 0 value mismatches. Completeness holds in both directions: every non-blank raw cell has a clean row and every clean row has a raw cell. Scale, sign, period and price-basis handling are correct. The fetch code and sidecars comply with D1-1, D1-2 and D1-4 (one timing note, verify-2).

The defect is a publisher misprint that the unit ingested as printed. In DEA QR Jan-Mar 2023 Table 4.4, the "Pension Fund" and "Others" rows are swapped, so 14 official rows carry the wrong holder label (verify-1). The gap map's R3a method names this report.

## What was run

| Step | Result |
|---|---|
| `fetch rbi_financial_accounts --offline` | OK, 14 raw files, sha256 re-verified |
| `build rbi_financial_accounts` (offline from pins) | OK, 11 datasets, 227,362 rows |
| `test -k rbi_financial_accounts` (before adding the verify file) | 97 passed |
| `test -k rbi_financial_accounts` (with `tests/verify/test_rbi_financial_accounts_spotcheck.py`) | 109 passed, **1 failed**: `test_qr2023_pension_others_labels_agree_with_status_paper` (verify-1, by design) |
| `coverage rbi_financial_accounts` | OFFICIAL covered=3, partial=5; no BROKEN |
| `repro rbi_financial_accounts` | All 13 files byte-identical across seeds and 1 vs 4 threads, and they match `data/manifest.json`. The command still prints REPRO FAILED only because `code_hash` changed while other units were being edited (the same race the builder reported). |

## Method (`tests/verify/test_rbi_financial_accounts_spotcheck.py`)

- Each raw file's sha256 is re-checked against `data/raw_pins/rbi_financial_accounts.yaml`.
- **FSF workbook**: openpyxl in read-only/values mode (the unit uses random-access mode).
  - The verifier has its own maps: sheet title to sector (so a sheet mapped to the wrong sector would show), SNA code to instrument, counterparty labels, S 6/S 7 sector and instrument labels, and S 8 items.
  - Measure/year columns are read from the header rows. Stock headers `YYYY-YY` map to end-March of the later year; the article confirms the convention ("NFW ... at end-March 2024, up from ... 2022-23").
  - Workbook blanks: exactly the 12 documented cells (St 1 row 167, R:AC).
- **Bulletin 52(a)/(b)**: pypdf text (the unit uses pdfplumber). Every numeric row is checked against the verifier's own ordered row list, with a label assertion on each row.
- **HBS T11/T12/T49/T107/T109**: pandas.read_html/lxml (the unit uses BeautifulSoup), with the verifier's own label and column maps. The two T11 2022-23 columns are keyed by base year.
- **DEA PDFs**: pypdf text.
  - HB-1A and HB-1B have 16 columns each. The HB-1A column order was confirmed from pdfplumber word x-positions.
  - For HB-5, pypdf's split decimals ("7. 21") are re-joined, and the quarterly sequence is rebuilt independently. The second "2015 (End-March)" can only be end-March 2016.
  - T2.10, QR T4.4 and T4.5 are read including their Total rows.
- **39 hand anchors** were typed from the page, sheet or HTML text. 34 of them are PDF values across 52(a), 52(b), HB-1A, HB-1B, HB-5, T2.10 and QR T4.4/T4.5, including the pypdf split-decimal cells and the HB-1A 2019-20 '*' row.
- **Semantics**:
  - FWTW orientation: row HH × column Central-bank "Sources" = 1,18,026, which is RBI's currency liability to households. This equals St 4 HH F21 and St 1.1 RBI F21 to HH.
  - The HDFC merger figures and the K9b RBI F89 payable to the Centre (1,21,648 flow; 2,22,372 stock).
  - 52(a) stages follow note 2, and all percent rows carry base 2022-23.
  - The T11 base-year tags.
  - Every PDF provenance locator's page contains its table.
- A seeded random sample (seed 20260929) of 12 FSF cells is printed with the raw value.

| Dataset | Values compared | Value mismatches |
|---|---:|---:|
| fsf_balance_sheets (St 1-5, 30 sheets) | 207,228 | 0 |
| fsf_fwtw (S 6.1-6.13) | 4,500 | 0 |
| fsf_instrument_sector (S 7.1-7.13) | 10,800 | 0 |
| fsf_financing (S 8.1-8.3) | 900 | 0 |
| hh_finsav_52ab (PDF, pypdf) | 1,000 | 0 |
| hbs_saving + gsec_ownership + small_savings + scb_balance_sheet | 1,448 | 0 |
| dea_central_debt + dea_gsec_ownership (PDF, pypdf) | 1,486 | 0 |
| **Total** | **227,362** (census) | **0**; 14 values carry the wrong label (verify-1) |

## Findings

| # | Severity | Finding | Evidence | Fix |
|---|---|---|---|---|
| verify-1 | **major** | **QR Jan-Mar 2023 Table 4.4 prints "11. Pension Fund" and "12. Others" swapped, and the unit ingests them under the printed labels.** This affects 14 official rows: `qr2023_t4_4.gsec_central.share.pension_funds` (9 rows, Mar-21..Mar-23) and `...share.others` (5 rows, Mar-22..Mar-23). The dataset now holds three different end-March 2023 pension-fund shares for the same concept: 5.6 (QR23), 4.0 (QR24 T4.4 and SP T2.10) and 3.98 (HB-5/T107). The gap map's R3a method averages the "QR Jan-Mar 2023 and Jan-Mar 2024" ownership shares, so Phase 2 would give pension funds about 1.6 pp of Central G-sec interest that belongs to "Others". The same applies to K8d share changes. The unit's own provenance note ("pension funds were reckoned under 'Others' until December 2021, '-' printed: no row") contradicts its rows, because the '-' cells sit on the printed "Others" row. | QR23 PDF p.18 (printed p.14): "11. Pension Fund 7.3 7.4 8.8 7.7 4.5 4.6 5.1 5.5 5.6" and "12. Others - - - - 3.5 3.6 3.8 3.9 4.0". Status Paper 2023-24 T2.10 (p.35): Pension 3.5 (2022) and 4.0 (2023); Others 7.3 (2021), 4.5 (2022) and 5.6 (2023). QR24 T4.4, Mar.23 column: Pension 4.0, Others 5.6. The other 10 holders agree with T2.10 at every common date. The QR23 text itself misstates "pension fund ... 5.6 per cent", so the misprint is the publisher's. | Swap the two rows with an explicit, commented override, citing T2.10, QR24 and the '-' pattern. Alternatively, drop the two rows and log them as unusable. Add a QR-vs-Status-Paper cross-check to the unit tests and log the misprint in the issues file. The verify test passes once the rows are fixed or removed. |
| verify-2 | minor | **rbidocs spacing, measured end-to-start, was about 7 s for the second request.** `retrieved_at` is stamped after the response arrives. The stamps are FSF xlsx 10:23:15Z, 52(a) 10:23:22Z and 52(b) 10:23:32Z. D1-4 ("at least 10 s between requests") was met start-to-start only. | `.meta.json` sidecars; `pipeline/core/fetch.py` sets `retrieved_at` after `http_request`. | None needed now. The builder disclosed it (issues file preamble) and the gate now waits 10 s from the end of the previous response. No challenge was served, and every sidecar shows status 200, no redirects and no cookies. |
| verify-3 | minor | **HBS T12 rows for 1983-84..2010-11 carry `base_year=2011-12`.** Those years predate the 2011-12 series; they come from older-base series spliced into the Handbook table. | All `t12.*` series have base_year 2011-12 from 1983-84 on. The T12 note only says "as per NAS 2025". | Set base_year to null before 2011-12, or add a provenance note that pre-2011-12 values are from earlier bases (level breaks at 1999-2000, 2004-05 and 2011-12). |
| verify-4 | minor | **HBS T107 note 5 is not logged: "Data since March 2024 includes the impact of the merger of a non-bank with a bank."** From March 2024, the holder shares shift HDFC Ltd's holdings to commercial banks. K8d uses changes in shares × stock. | T107 notes cell (HTML). | Log it in the issues file next to rbi_financial_accounts-2 (HDFC). Phase 2 must not read the Mar-23 to Mar-24 bank-share rise as net purchases. |
| verify-5 | minor | **FSF datasets mix parents and components on both axes.** Institutions include fc, fc_odc and fc_odc_scb, etc. Counterparties include residents, gg, gg_cen and gg_sta, and S 6/S 7 include "all" and "total". Summing across rows double-counts. | Structure of `fsf_balance_sheets`, `fsf_fwtw` and `fsf_instrument_sector`. | Say so in the `_datasets.json` descriptions, or add a `level`/`is_subtotal` tag in `dim_other`. |

## Claims re-verified (all true)

- Household gross financial asset flows for 2023-24: FSF St 4 34,45,383 (3,445,382.5); 52(a) 36,01,839; HBS T11 (base 2022-23) 35,75,657; HBS T12 34,30,640. Liabilities: FSF 18,75,522; 52(a) 19,09,425; T11 18,79,000; T12 18,78,999.
- HDFC: FSF St 4 household loans from ODC were 12,52,313 (2022-23) and 18,77,458 (2023-24); from OFC they were 3,43,354 and 1,208. 52(a) HFC loans were -3,33,423.7 (annual) and -4,04,294.0 in Q2 2023-24.
- The FSF instrument figures in S 7.13.a match the builder's non-closure notes: RBI F6 "Sources" = 38,100.3 at end-March 2024, with all F61-F66 components 0.
- The DEA HB-1A 2013-14 market loans are printed at 38,53,399, while the components sum to 38,53,593 (a 194 gap). 2019-20 includes Rs 80,000 crore of CMBs, per the footnote.
- The HB-5 column order is commercial banks, co-op banks, non-bank PDs, insurance, MFs, PFs, pension funds, FIs, corporates, FPIs, RBI, others. The printed header is scrambled and omits pension funds. The order is confirmed by an exact match with HBS T107 at end-March 2022-2024 (36 values).
- HB-1A headers by x-position: col 7 "14 Days Treasury Bills", col 8 "Special Securities Issued in Conversion of Treasury Bills", col 9 "Compensation and Other Bonds", col 10 "Other Special Securities Issued to International Financial Institutions", col 11 "Securities [against] Small Savings Fund", col 12 "Others#". These match the unit's mapping.
- Units: every money value is in Rs crore as published (FSF "(₹ crore)"; 52(a)/(b) "Amount in ₹ Crore"; HBS "₹ Crore"; DEA "₹ crore"), and every conversion is `none`. Shares are `percent`. There is no lakh or billion scaling anywhere; the S 8.4-8.7 "Rs Billion" sheets are correctly not ingested.
- Status: every row and provenance record is `official`. No derived or estimated numbers are passed off as official.
- Access (D1-1/D1-2): only public URLs on www.rbi.org.in, rbidocs.rbi.org.in and dea.gov.in; browser-like headers only, with no Cookie or Authorization header; no redirects; no challenge; no GSTN/CBDT; no microdata. The rbidocs gate stops at the first `AccessBlocked` and never retries.
- Coverage: the K7/K8 "full" claims rest on FSF St 1-5 2023-24 transactions (old-base vintage, as the gap map itself notes), and the S4 "full" claim rests on S 6.13.b. Both are consistent with the gap map. R12a is correctly left undeclared.
