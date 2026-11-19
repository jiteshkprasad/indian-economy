# rbi_banking_corporate: independent verification (first pass)

Verifier run 2026-09-29. I did not build this unit. Regression test:
`tests/verify/test_rbi_banking_corporate_spotcheck.py` (10 tests, about 2 s, marker `quality`). It does not
import `pipeline.ingest.rbi_banking_corporate`.

## Verdict

**The values pass. No blocker or major findings against the build.** I compared all 3,055 clean values with
the pinned raw files, using my own parser, and found 0 mismatches:
- 3,017 HTML table cells;
- 30 press-release figures, each found in both the HTML page text and the rbidocs PDF text;
- 8 derived rows, recomputed from the raw tables.

No level row and no data column is silently dropped from the tables the unit ingests. Periods, bank groups,
the balance-sheet side, units and provenance are right. The unit meets D1-1, D1-2 and D1-4.

The builder's gap-map conclusions hold: R6 is covered, R8 and R9c are correctly left missing, and STRBI,
BSR detail and corporate-finance levels are DBIE-only. I have ten minor findings, listed below. Three are
coverage or labelling claims to tighten (K8, R13, the `scb` slug). Two correct statements in the builder's
report (revision sizes, the AIFI "does not close" finding). None of them changes a number.

## What I ran

| Step | Result |
|---|---|
| `fetch rbi_banking_corporate --offline` | OK, 17 raw files, hashes match the pins |
| `build rbi_banking_corporate` | OK, 7 datasets, row counts as reported (1172 / 8 / 1182 / 232 / 431 / 10 / 20 = 3,055) |
| `test tests/units/test_rbi_banking_corporate.py` and `test -k rbi_banking_corporate` | 109 passed (unit, generic and my 10 verify tests) |
| `test tests/verify/test_rbi_banking_corporate_spotcheck.py` | 10 passed |
| `repro rbi_banking_corporate` | REPRO OK (with a note that the manifest code_hash is older than the current code, because other agents are editing) |
| `coverage rbi_banking_corporate` | 11 refs, no BROKEN; OFFICIAL covered=1 (R6), partial=2 (K8, K8a) |

## Method (independent parser)

- **HTML tables** (AR chapter XII ×3 editions, RTP chapters IV/V/VI and appendix VI.6/VI.7 ×2 editions):
  - Parsed with `lxml.html` and my own colspan/rowspan expansion. The builder uses BeautifulSoup and its `_html.grid`.
  - The file comes from the row's vintage plus its table_id. The table is found by its printed caption; a
    schedule is cut from the "SCHEDULES FORMING PART..." table by its "Schedule N:" block.
  - The row is found by its printed label. Repeated labels are told apart by the printed section heading:
    "(b) Banks" for schedule sub-totals, "EXPENDITURE" for the income statement, "Financial Ratios" for
    level-vs-ratio rows, and the half of the balance sheet.
  - The column is found by the header text above it, not by position: year or end-March date, bank group,
    and measure for the cost-of-funds tables. Growth, variation, H1 and part-year columns are excluded.
  - The number is parsed by my own Indian-format parser, including the footnote digits in XII.1 ("1,29,800.68 4").
- **Exhaustive, not sampled:** every clean row of the four table datasets is located and compared (3,017).
  In reverse, every raw row with a number in a column the unit uses was listed. The only ones missing
  are the per-cent ratio blocks under the P&L tables, which issue -12 documents as a skip. The only unused
  numeric columns are XII.1/XII.10 2019-20 and 2020-21, which -7 documents.
- **Sensitivity (mutation) test:** on 300 seeded rows:
  - every perturbed value fails;
  - shifting the period by a year moves to a different raw cell or none (291 rows; VI.3 has no year column
    and its date is checked from the caption "(At end-March YYYY)");
  - swapping the bank group does the same (88 rows in grouped tables).
- **Derived rows:**
  - R6 is recomputed from ar2526 XII.1, re-dated from accounting year t to fiscal year t+1 (FY 2023-24 = 87,416.22).
  - K9b is recomputed from the Schedule 4 "Surplus payable" stocks of each edition (2023-24 = 1,23,457.77).
  - All 8 match.
- **Press releases** (BSR-1 March 2024, PCBS 2023-24): all 30 figures are captured by phrase regexes, e.g.
  "for manufacturing, non-IT services and IT" keeps the order of the margins. The regexes run on the HTML
  text and again on the pypdf text of the two rbidocs PDFs. No build value comes from a PDF; the PDFs are
  print copies of the releases, as the builder says.
- **Seeded 10% sample** (seed 20260929, stratified by dataset × table × vintage × unit): 304 rows in 103
  strata, all matching. `test_print_seeded_sample` prints each value and its raw cell. This duplicates the
  exhaustive check and is kept for the audit trail.
- **Other checks:**
  - Provenance: each row's url and sha256 are those of the file the value was found in. Its table_id is
    the row's, or "Schedules 1-12/13-15", and it is official.
  - Unit captions: INR rows come only from "₹ crore" tables, with no lakh, thousand crore or million.
  - Balance-sheet `side` is right (144 rows).
  - Vintages equal the "Date :" printed on each page.

## Systematic-error hunt

| Check | Result |
|---|---|
| Scale (lakh / thousand crore / million) | None. Every INR table is captioned ₹ crore; values equal the printed cells. |
| Sign conventions | Negatives kept as printed: Schedule 13 LAF/SDF interest, Schedule 14 losses, payments-bank reserves (−2,365) and 2023-24 net profit (−1). The merger-excluded figures printed in parentheses in RTP 2023-24 IV.1 are positive levels, not negatives, and are ingested correctly. |
| Period labelling | RBI accounting years 2021-22 onwards are April-March (fy). Balance-sheet and schedule columns headed "2023-24" are 2024-03-31 stocks. RTP IV.1 "2024" is 2024-03-31. VI.3 date comes from its caption. All verified by header, not assumed. |
| Rows matched by position | None found: every value resolves by label and header, and the mutation test shows the resolver is discriminating. |
| Duplicated totals | NBFC P&L is printed twice (VI.9 and appendix VI.6/VI.7) and payments banks twice (IV.3 SCB table vs IV.39/IV.40). Both are separate series, documented (-11), and identical where they should be. |
| Mixed vintages | Both RTP vintages kept, keyed by vintage. The AR accounts are identical across the three editions except XII.8's printed 5.31 vs 5.3. |
| Status | 3,047 official rows (as printed); 8 derived rows (R6, K9b) with method and inputs. No official label on arithmetic. |
| Access policy (D1-1/D1-2/D1-4) | Pass. Only `ctx.fetch`; no httpx, requests, cookies or browser. The 17 meta sidecars show status 200, no redirects and browser-like headers only. rbidocs was hit twice, 12 s apart (10:35:48Z and 10:36:00Z), after all www.rbi.org.in pages, with the gate stopping at the first challenge. No microdata, GSTN or CBDT. |

## Findings

| # | Severity | Finding | Suggested fix |
|---|---|---|---|
| V-1 | minor | **K8 coverage is a stock, but K8 is a flow cell** (incurrence of liabilities). The K8 entry declares `rtp.scb_bs.*` end-March stocks as `partial`, and the note itself says it is "a check ... not a fill". The coverage report then shows K8 as OFFICIAL/partial from this unit. | Drop the K8 entry, or move the note to the issues file as a cross-check for rbi_financial_accounts. Keep K8a (the merger memo). |
| V-2 | minor | **R13 lists `xii_8.fca_earnings`** (1,87,471.20 in 2023-24). XII.8 says it includes exchange gain/loss and capital gains on securities. Those are holding gains, not SNA property income. The note says "incl. valuation items", but a Phase 2 user could take it as the reserve-income figure. | Keep only `sch13.b.sub_total` (foreign-source interest, 1,03,177.64), plus Schedule 14(b)(i) amortisation if wanted, as R13's partial. List fca_earnings under R6's super-dividend test only. |
| V-3 | minor | **`scb` means two populations.** In the BSR-1 rows `scb` includes RRBs (the release: "SCBs {including Regional Rural Banks}"). In all RTP rows `scb` excludes RRBs (RTP IV.3 note 1; issue -13). | Use a distinct slug (e.g. `scb_incl_rrb`) for the BSR-1 rows, or record the scope in `dim_other`, before the Phase 2 crosswalk. |
| V-4 | minor | **Revision sizes understated in the builder's report.** It says "SCB balance sheet and P&L revisions are under 1.5%". Between RTP 2023-24 and 2024-25, end-March 2024 values move more: FB G-secs outside India 8,327 → 10,185 (+22%), FB non-approved securities 73,525 → 71,667 (−2.5%), SCB G-secs outside India +2.2%, and cost/return ratios by 0.1-0.2 pp. My exhaustive check confirms these are RBI's printed figures, not parse errors. Issue -9 lists the NBFC, StCB and DCCB revisions but not the FB ones. | Add them to issue -9. Phase 2 should use the 2025-12-29 vintage. |
| V-5 | minor | **The AIFI "does not close" finding (-8) is imprecise.** RTP 2024-25 VI.18 prints "Provisions for Contingencies" (2,935 / 2,936 / 3,357). The unit ingests it as `rtp.aifi_pl.provisions_contingencies`. With it, income − expenditure − contingencies − tax = PAT within ±1 for 2022-23 (12,567 vs 12,568) and 2023-24 (15,912 vs 15,913). What doesn't close is the "Operating Profit (PBT)" line, in every year, and the whole P&L in 2024-25 (18,710 vs PAT 19,773). | Reword -8. The table closes to PAT when contingency provisions are deducted, except 2024-25; the PBT line is inconsistent with its components. |
| V-6 | minor | **R6 cash series stops at FY 2022-23, though the raw file has two earlier receipts.** XII.1 in AR 2023-24 prints the 2019-20 surplus (57,127.53) and the 2020-21 transition-year surplus (99,122.00). The builder rightly keeps these out of the accounting-year series (not April-March), but *cash received by fiscal year* is still a fiscal-year flow. My understanding is 57,128 was paid in Aug 2020 (FY 2020-21) and 99,122 in May 2021 (FY 2021-22). I did not fetch those RBI press releases, so confirm before use. | Optional for the Phase 2 time series: add FY 2020-21 and FY 2021-22 to `r6.*` with the payment dates cited, or log the gap in -7/-14. |
| V-7 | minor | **Some item_labels are not "as published".** "(Issue Department assets total)" names an unlabelled printed sub-total. "3. Deposits (excl merger)" and similar are the builder's labels for the parenthesised figures. PIPELINE_GUIDE §5 asks for the published label. The values are right, and the locator explains them. | Keep the published label ("3. Deposits") and mark the merger exclusion in `dim_other` (e.g. `scope=excl_merger`). For the unlabelled sub-total, say in the locator that it is unlabelled. |
| V-8 | minor | **estimate_stage differs across editions for the same kind of table.** SFB P&L is "Audited" in RTP 2024-25 IV.37 but "n.a." in RTP 2023-24 IV.38. PB and LAB are "n.a.". SCB tables are "Audited" (source "Annual accounts of respective banks"). This is harmless, but compare_vintages users may read it as a stage change. | Align on the table's printed source note. |
| V-9 | minor | **The R6 2026-27 row (2,86,588.46) is an inference.** It assumes the 2025-26 surplus was paid in FY 2026-27. The vintage is the AR release (29 May 2026), before or around the payment. The builder documents it (-14). | Fine as `derived`. The union_fiscal cross-check should confirm it once the Union accounts for 2026-27 exist. |
| V-10 | minor | **Provenance table_id is grouped for schedules** ("Schedules 1-12", "Schedules 13-15") while rows carry "Schedule N". The locator is still findable within a minute. | None needed, or split the provenance per schedule. |

Builder claims I confirmed:
- RTP chapter tables, not the appendix, carry the bank-group P&L (the access checker's point).
- SCB tax provisions are not printed separately in RTP.
- PCBS and BSR-1 detail tables are DBIE-only: the release pages link only to DBIE and to the PDF print copies.
- R9c is not in the RBI AR.
- NBFC-ML revisions come from layer reclassification: the appendix notes use layer lists as on 31 March 2024 vs 31 December 2024.
- The public FI annual reports were not fetched and are not registered.

## Counts

- Total values in unit: 3,055. Values compared with raw documents: 3,055 (100%). Mismatches: 0.
- PDF text checks: 30 values, all matched in the pypdf text of the two rbidocs PDFs. No build value is PDF-derived.
- Seeded stratified sample quoted for the notes: 304 rows (10%), 0 mismatches.
