# Phase 1 coverage of the gap map

Final Phase 1 integration run, 2026-09-29, by an agent that built none of the units. It supersedes the close-out check and the earlier integration check of the same day. Sources for this page:

- `uv run python -m pipeline coverage --json`, run on a from-scratch build of all 11 units (193 datasets);
- `data/gap_map.csv`, 115 refs;
- the units' `pipeline/ingest/<unit>_coverage.yaml` files;
- `docs/phase1/issues/*.md` and `docs/phase1/verify/*.md`.

**How to read "coverage".** It comes from `pipeline/core/coverage.py`:

- `covered`: at least one declared entry has extent `full` and its series have a row in the reference year (FY 2023-24 unless the entry names another period);
- `partial`: only `partial` or `control_total` entries pass;
- `missing`: nothing is declared.

No ref is `BROKEN`, and the coverage command reports no errors.

## Integration run (all 11 units, offline)

| Command | Result |
|---|---|
| `verify-raw` | 663/663 pinned raw files present and hash-verified (exit 0), before and after the run |
| `fetch --offline` | 11 ok, 0 failed (663 raw files). union_fiscal logs that the PIB June 2023 release has no pin (blocked online, union_fiscal-1) |
| `build (all units, into an emptied data/clean, 249 s)` | 11 ok, 0 failed; 193 datasets, 215 files, 1,201,543 values. Output byte-identical to the data/clean it replaced (sha256 of every file), and data/manifest.json unchanged. 2 warnings: the known HCES A6/A10S publisher break (logged) |
| `test (full offline suite, 444 s)` | **3,370 passed, 0 failed**, 23 xfailed, 1 deselected (live). All 23 xfails are UNEXPLAINED reconciliation checks in `tests/cross`, each with a written reason. No verifier strict xfail is left: finsector_markets V13/V14, labour VER-C1, mospi c-1 and state_fiscal verify-13 are all closed and now run as ordinary tests. 3 library warnings (a polars deprecation in a state_fiscal unit test; two openpyxl workbook-style notices), none from the pipeline |
| `test tests/cross` (inside the full run) | 207 tests: 184 passed, 23 xfailed. Unchanged since the close-out check |
| `repro (all units, 801 s)` | REPRO OK: 215 files byte-identical across PYTHONHASHSEED 0/1 and 1/4 threads, and equal to data/manifest.json |
| `manifest --check` | up to date (after the build, the test run and the repro) |
| `coverage --json` | exit 0, no errors; OFFICIAL covered 46, partial 10, missing 0 (of 56); no BROKEN |

**Nothing was changed at this run** apart from this page. No unit code, test, pin, runner or core module was edited. Since the close-out check, the units and verifiers closed the open items: the finsector_markets verifier dropped the V13/V14 marks and added `epfo_eps_outgo` to its census; labour VER-C1, mospi c-1 and state_fiscal verify-13 were fixed by their builders and the verifiers removed the marks; and state_fiscal declared its gross State provident-fund lines for S9 (state_fiscal-25, verified). Those fixes were already in the built data when this run started: the rebuilt data/clean and data/manifest.json are byte-identical to the ones before it, and the dataset, file and value counts are the same as at the close-out check.

## Headline

**46 of 56 OFFICIAL refs are fully covered (82.1%)**, the same as at the close-out check (45 at the earlier check: F1 became covered, and S6 moved from missing to partial). **No OFFICIAL ref is missing.** The only change in the coverage report since the close-out is that S9 gained a State-side input (gross State provident-fund flows, below); it stays partial. The 10 that are not fully covered:

| Ref | Coverage | Why, in one line |
|---|---|---|
| I3a | partial | Not published at SAM detail. NAS gives change in stocks for 6 sectors only; the FC sub-sector and Centre/State splits are Phase 2 estimates, as the gap map says. |
| R2 | partial | Published totals disagree (H9). All of them are ingested, including the new IGAS-2 grantee view; they span about 3.4 lakh crore. |
| R3 | partial | Covered in combination: Union (Finance Accounts MH 2049) + States (FC16 KFI / RBI SF). Each unit declared its half as `partial`. |
| R7 | partial | Covered in combination: Union dividends (MH 0050 by payer) + States' dividends (RBI SF App. I). |
| R9 | partial | Covered in combination: Union pensions (MH 2071) + States' pensions (FC16 KFI B.1.b). |
| K6 | partial | Inputs now ingested (Statement 6 GCCA, IGAS-2 capital by grantee; RoW part). Classifying grantees into SAM institutions is Phase 2. |
| K8b | partial | One split is blocked by terms. Instrument totals are in; the FPI-debt G-sec vs corporate-bond split needs NSDL, whose terms forbid reproduction. The gap map already marks that split estimated. |
| S7 | partial | Blocked by policy (GSTN, D1-1c) and by a PIB bot challenge after 2 of 12 monthly releases. The annual IGST apportionment is in. |
| S9 | partial | Partly not published. Missing: exempted PF trusts, CMPF, NPS withdrawals. Union GPF, gross State provident-fund flows (all States, no State-wise split) and the EPS pension/withdrawal split are in. |
| S6 | partial | Source granularity. The energy PSUT (now written, declared and verified) has 7 industry groups, not 34 activities. |

**Reading past the tool's strict rule:** R3, R7 and R9 are complete once the Union and State halves are put together. Counting them gives **49 of 56 (87.5%)**.

The OFFICIAL refs that are genuinely short:

| Ref | Problem | Fix |
|---|---|---|
| R2 | Published totals disagree (H9): Union Statement 18, MH 3601 and IGAS-2 against the States' RBI SF and FC16 figures | Phase 2 must choose a measure and log the residual. RECONCILIATION GOV-9/15/16 give the sizes. |
| K6 (and R2k) | No single series matches the cell: the capital-grant inputs are Union-side and by grantee type | Phase 2 classifies Statement 6 / IGAS-2 grantees into SAM institutions (union_fiscal-23). |
| S9 | Funded-scheme flows missing: exempted PF trusts, CMPF, NPS withdrawals (none published as amounts) | None in Phase 1: they are not published. Gross State provident-fund flows are now declared from RBI State Finances App. III VI.1 / App. IV VII.1 (gross public-account lines, all States and UTs; state_fiscal-25). Phase 2 must handle their caveats: they include "other savings deposits", and whether receipts include interest credited is not stated. |
| S6 | 7 industry groups, not 34 activities | Phase 2 splits the groups with SUT energy-product use (an estimate). |
| S7 | Blocked by D1-1c; PIB challenged after 2 releases | Stays annual unless the owner arranges GSTN access or PIB allows the archive (FR-uf-4). |
| K8b | FPI-debt split blocked by NSDL terms | None: Phase 2 estimates the split, as the gap map already plans. |
| I3a | Splits not published | None: Phase 2 estimates them, as the gap map already plans. |

Only S7 (policy and a bot challenge) and the FPI-debt detail of K8b (terms) are short because of access limits. No other OFFICIAL ref lacks data because a download failed.

**Other statuses:**

- ESTIMATED (56 refs): 55 have partial inputs ingested. **T3a (personal income tax by household group) has none.** CBDT is not automated, and no open document gives an ITR income-range distribution.
- INTERNATIONAL (3 refs: P6a, S1, S2): all partial, as expected. They are priors and satellites. S1 has goods by partner, and HS chapter by partner for the top 30 partners only; TradeStat was not fetched (D1-7).

## Values spot-checked by independent verifiers (SPEC Phase 1: at least 10%)

"Values" = rows in `data/clean/<unit>/*.parquet` after today's from-scratch build (one row = one number). "Checked" = values the unit's verifier compared with the pinned raw files, taken from the latest pass in `docs/phase1/verify/<unit>.md`. "Regression test today" = the verifier's `tests/verify/test_<unit>_spotcheck.py` in this run.

| Unit | Datasets | Values in clean data | Checked | Share | Verifier method | Regression test today |
|---|---:|---:|---:|---:|---|---|
| mospi_nas_2026 | 86 | 42,583 | 42,583 | 100% | Census, 3 passes. Close-out pass: all 15,775 API values against the raw JSON pages, and the 3 derived F1 rows against their inputs. | pass (c-1 closed; its xfail is now an ordinary test) |
| io_tables | 8 | 115,294 | 115,294 | 100% | Census. Close-out pass: all 324 energy-PSUT values, with a second PDF engine. | pass |
| hces_consumption | 9 | 328,697 | 328,697 | 100% | Census, 3 passes. The close-out pass re-keyed to the `sy` survey windows and re-read 28,093 changed rows with a second xlsx reader. | pass |
| labour_enterprise_surveys | 15 | 37,125 | 37,125 | 100% | Census, 3 passes. Close-out pass: all 5,244 API values against the raw JSON, plus 31,881 PDF values re-keyed to `sy`. | pass (VER-C1 closed; its xfail is now an ordinary test) |
| union_fiscal | 12 | 8,523 | 8,523 | 100% | Census, 2 passes. Close-out pass: all 2,012 values of the 4 new datasets, with independent parsers. | pass |
| state_fiscal | 11 | 166,316 | 166,316 | 100% | Census, 2 passes, plus a KFI reverse census of 38,227 raw cells. | pass (verify-13 closed; its xfail is now an ordinary test. The final pass also re-derived the S9 lines from raw) |
| rbi_financial_accounts | 11 | 227,362 | 227,362 | 100% | Census, 2 passes | pass |
| rbi_banking_corporate | 7 | 3,055 | 3,055 | 100% | Census, plus a 10% sample for metadata | pass |
| external_sector | 16 | 19,965 | 3,120 | 15.63% | Stratified sample of 15%, plus all gap-map-critical series. The close-out pass covers both FLA rounds. | pass (the 6 stale expectations of the earlier check were fixed by the verifier's close-out pass) |
| finsector_markets | 11 | 11,877 | 11,877 | 100% | Census, 4 passes, over all 11 datasets. The final pass added `epfo_eps_outgo` (30 of 30, with a positional pdfplumber reader). | pass (V13/V14 marks removed; both now ordinary, strengthened tests) |
| trade_satellites | 7 | 240,746 | 240,746 | 100% | Census. The close-out pass added provenance-to-pin checks. | pass (trade_satellites-14 pin repaired, fw-19) |
| **Total** | **193** | **1,201,543** | **1,184,698** | **98.6%** | | |

Every unit is at or above 10%; the lowest is external_sector at 15.6%. Ten units are censused in full. Since the earlier check, 23,388 values have been added (mospi_nas_2026 +15,778 API and F1 rows, labour_enterprise_surveys +5,244 API rows, union_fiscal +2,012, io_tables +324 energy PSUT, finsector_markets +30), and all of them have now been censused by their verifiers.

**Open verifier items: none that affect data or tests.** The earlier list (finsector_markets V13/V14 marks and the `epfo_eps_outgo` census; strict xfails for labour VER-C1, mospi c-1 and state_fiscal verify-13) is closed. What is left is wording and declaration precision, with no effect on any value, test or coverage state:

1. **union_fiscal close-3 (minor, union_fiscal builder).** In `pipeline/ingest/union_fiscal_coverage.yaml`: (a) K6 declares `union_fiscal_gcca` `stat6.grand_total` as `control_total`; `partial` is the honest extent, because it includes grants to units inside general government and excludes the RoW part (K6 is `partial` either way); (b) the R2k `fa_gia` note cites union_fiscal-22 for the bridge caveat, which should be union_fiscal-23; (c) some notes and issue rows say "Expenditure Budget Statement 6"; the document is the Expenditure Profile.
2. **Stale issue-file text (cosmetic, each unit's builder).** `docs/phase1/issues/finsector_markets.md` still says V13/V14 are XPASSing strict xfails (they are now ordinary passing tests); `docs/phase1/issues/trade_satellites.md` still says "Still OPEN as trade_satellites-14" in its V1 row and "327 passed, 1 failed" (verify C1; the test passes).
3. **state_fiscal verify-16 (cosmetic, state_fiscal builder).** Imprecise wording in the ratio-record notes, the S9 coverage note (omits "no State-wise split"; the caveat is in state_fiscal-25) and a unit-test docstring's row numbers.

## Per-ref detail

The dataset lists come from the coverage report; every dataset is in `data/clean/<unit>/`. An `(extent)` in the dataset column is what the unit declared for it. The amounts in the reasons are ₹ crore, FY 2023-24, and were checked in clean data for this page.

### OFFICIAL refs: 56 refs (covered 46, partial 10)

| Ref | Cell | Coverage | Datasets serving it (extent) | Why not fully covered |
|---|---|---|---|---|
| P1 | Make/supply matrix: domestic output of each commodity by producing activity, basic prices (34x3… | covered | `io_tables_sut_supply` (full)<br>`mospi_nas_2026_s7_1` (control total) |  |
| P2 | Intermediate consumption by commodity and using activity, purchasers' prices | covered | `io_tables_sut_use` (full)<br>`mospi_nas_2026_s7_1` (control total) |  |
| P3 | Trade and transport margin services supplied into the margin account (C_TRAD, C_TRNS only) | covered | `io_tables_sut_supply` (full) |  |
| P4 | Margins paid on each commodity | covered | `io_tables_sut_supply` (full) |  |
| P5 | Exports by commodity (goods f.o.b. + services), incl. non-resident purchases in India | covered | `external_sector_bop_bpm6_annual` (control total)<br>`io_tables_sut_use` (full)<br>`mospi_nas_2026_s1_1` (control total) |  |
| P6 | Imports by commodity, c.i.f.-adjusted (competitive imports) | covered | `external_sector_bop_bpm6_annual` (control total)<br>`io_tables_sut_supply` (full)<br>`mospi_nas_2026_s1_1` (control total) |  |
| P7 | All product taxes by commodity, total (excluding import duty) | covered | `io_tables_sut_supply` (full) |  |
| P8 | Import duties by commodity | covered | `io_tables_sut_supply` (full)<br>`union_fiscal_fa_receipts` (control total) |  |
| P9 | Product subsidies by commodity (negative), total | covered | `io_tables_sut_supply` (full)<br>`union_fiscal_exp_profile` (partial) |  |
| P10 | Other taxes less subsidies on production, by activity | covered | `io_tables_sut_va` (full)<br>`mospi_nas_2026_s7_1` (control total) |  |
| V1 | Compensation of employees by activity (total labour) | covered | `io_tables_sut_va` (full)<br>`mospi_nas_2026_s7_1` (control total) |  |
| V2 | Gross operating surplus + mixed income (incl. CFC) by activity, total | covered | `io_tables_sut_va` (full)<br>`mospi_nas_2026_s7_1` (control total) |  |
| V3 | Compensation of employees received from rest of world | covered | `external_sector_bop_bpm6_annual` (full)<br>`mospi_nas_2026_s6_1` (full) |  |
| V4 | Compensation of employees paid to non-residents | covered | `external_sector_bop_bpm6_annual` (full)<br>`mospi_nas_2026_s6_1` (full) |  |
| F1 | Labour income to households, total (domestic CE + CE from RoW - CE to RoW) | covered | `io_tables_sut_va` (partial)<br>`mospi_nas_2026_derived_residuals` (full)<br>`mospi_nas_2026_s6_1` (partial)<br>`mospi_nas_2026_s7_1` (partial) |  |
| F4 | Gross operating surplus of corporations and general government, by NAS sector | covered | `mospi_nas_2026_s1_14` (full)<br>`mospi_nas_2026_s7_1a` (partial)<br>`mospi_nas_2026_s7_1b` (partial)<br>`mospi_nas_2026_s8_15_1` (partial) |  |
| C1 | Private final consumption by commodity, total (households incl. NPISH, national concept) | covered | `io_tables_sut_use` (full)<br>`mospi_nas_2026_s1_1` (control total)<br>`mospi_nas_2026_s1_12` (control total) |  |
| C2 | Government final consumption by commodity, total | covered | `io_tables_sut_use` (full)<br>`mospi_nas_2026_s1_1` (control total)<br>`mospi_nas_2026_s1_14` (control total) |  |
| I1 | Gross fixed capital formation by commodity, total | covered | `io_tables_sut_use` (full)<br>`mospi_nas_2026_s1_1` (control total) |  |
| I2 | Valuables acquired by households (gold and silver ornaments) | covered | `io_tables_sut_use` (partial)<br>`mospi_nas_2026_s1_9` (full) |  |
| I3 | Change in inventories by commodity | covered | `io_tables_sut_use` (full)<br>`mospi_nas_2026_s1_1` (control total) |  |
| I3a | Change in inventories financed by each institution | **partial** | `mospi_nas_2026_s1_14` (control total)<br>`mospi_nas_2026_s7_2a` (partial) | **not published at SAM detail.** NAS publishes change in stocks for the 6 NAS sectors only (1.14 GCF less 1.11 GFCF; 7.2A-C), and those are ingested. The FC sub-sector split and the Centre/State split are not published. The gap map already says they are estimated pro rata to GFCF (Phase 2). |
| T1 | Union tax receipts by type, cash, as published (control totals) | covered | `union_fiscal_afs` (full)<br>`union_fiscal_fa_receipts` (full)<br>`union_fiscal_rb_receipts` (full) |  |
| T2 | State product-tax receipts by type, cash, as published (control totals) | covered | `state_fiscal_fc16_kfi` (partial)<br>`state_fiscal_rbi_sf_appendices` (full) |  |
| T3 | Personal income tax (incl. STT and other direct taxes on households), total | covered | `union_fiscal_fa_receipts` (full) |  |
| T4 | Corporation tax, total | covered | `union_fiscal_fa_receipts` (full) |  |
| R1 | Tax devolution (States' share of Union taxes) | covered | `state_fiscal_fc16_kfi` (full)<br>`state_fiscal_fc16_transfers` (partial)<br>`union_fiscal_fa_receipts` (partial)<br>`union_fiscal_rb_receipts` (partial) |  |
| R2 | Grants from Centre to States (FC grants, CSS, special assistance), total as published | **partial** | `state_fiscal_fc16_kfi` (partial)<br>`state_fiscal_rbi_sf_app_tables` (partial)<br>`union_fiscal_exp_profile` (partial)<br>`union_fiscal_fa_expenditure` (partial) | **published sources disagree (H9).** All the published totals are ingested: Union Statement 18 (in `state_fiscal_fc16_transfers`, 7,39,260), Finance Accounts MH 3601 (5,39,964, `union_fiscal_fa_expenditure`), RBI State Finances for all States and UTs (5,27,931), FC16 KFI for 28 States (4,72,466), and, new at the close-out, the Finance Accounts IGAS-2 grantee view (State Governments 3,98,428 cash + 195 in kind; `union_fiscal_fa_gia`, declared under R2k). They differ by up to about 3.4 lakh crore. The main cause is CSS money released outside State treasuries (H9, state_fiscal-7). RECONCILIATION GOV-9, GOV-15 and GOV-16 quantify it. The SAM cell is the current part (total less R2k), and its capital share is a Phase 2 bridge (union_fiscal-23). |
| R3 | Interest paid by Centre and States, cash, as published (control total by payer) | **partial** | `state_fiscal_fc16_kfi` (partial)<br>`state_fiscal_rbi_sf_statements` (partial)<br>`union_fiscal_fa_expenditure` (partial) | **covered in combination.** Union interest (Finance Accounts MH 2049, `union_fiscal_fa_expenditure`) and States' interest (FC16 KFI 4,94,911; RBI SF all States 5,07,175) are both ingested. Each unit serves one payer, so it declared `partial`. Together they fill the cell as the gap map defines it. |
| R6 | RBI surplus transfer to the Centre (cash basis) | covered | `rbi_banking_corporate_rbi_accounts` (partial)<br>`rbi_banking_corporate_rbi_surplus_timing` (full)<br>`union_fiscal_fa_receipts` (full) |  |
| R7 | Dividends from public enterprises, PSBs and LIC/GIC to governments | **partial** | `state_fiscal_rbi_sf_appendices` (partial)<br>`union_fiscal_fa_receipts` (partial) | **covered in combination.** Union dividends by payer type (Finance Accounts MH 0050) and States' dividends (RBI SF Appendix I) are both ingested. Each unit serves one side and declared `partial`. |
| R9 | Government employee pensions paid (unfunded Old Pension Scheme, civil + defence), gross D62 | **partial** | `state_fiscal_fc16_kfi` (partial)<br>`union_fiscal_fa_expenditure` (partial) | **covered in combination.** Union pensions (Finance Accounts MH 2071) and States' pensions (FC16 KFI B.1.b 4,94,939, the gap-map primary) are both ingested. Each unit serves one side and declared `partial`. |
| R11 | Remittances and other current transfers from abroad to households (incl. NPISH) | covered | `external_sector_bop_bpm6_annual` (full)<br>`mospi_nas_2026_s6_1` (full) |  |
| R12 | Current transfers from households to abroad (outward remittances, gifts) | covered | `external_sector_bop_bpm6_annual` (full)<br>`mospi_nas_2026_s6_1` (full) |  |
| R15 | Government current transfers with RoW (grants received, contributions paid) | covered | `external_sector_bop_bpm6_annual` (full)<br>`union_fiscal_exp_profile` (partial) |  |
| K1 | Gross saving of public and private non-financial corporations | covered | `mospi_nas_2026_s1_9` (full)<br>`rbi_financial_accounts_hbs_saving` (partial) |  |
| K2 | Gross saving of financial corporations, total (public 5,35,510; private 4,55,938) | covered | `mospi_nas_2026_s1_9` (full) |  |
| K3 | Gross saving of general government, total (-3,18,384) | covered | `mospi_nas_2026_s1_9` (full) |  |
| K4 | Gross saving of households incl. NPISH, total (58,90,330) | covered | `mospi_nas_2026_s1_9` (full)<br>`rbi_financial_accounts_hbs_saving` (partial) |  |
| K5 | Rest-of-world saving = India's current-account deficit (BoP basis) | covered | `external_sector_bop_bpm6_annual` (partial)<br>`mospi_nas_2026_s1_9` (full)<br>`mospi_nas_2026_s6_1` (full) |  |
| K6 | Capital transfers and acquisition of non-produced assets (domestic and with RoW) | **partial** | `mospi_nas_2026_s6_1` (partial)<br>`union_fiscal_exp_profile` (partial)<br>`union_fiscal_fa_gia` (partial)<br>`union_fiscal_gcca` (control total) | **inputs now ingested; the grantee classification is Phase 2.** The RoW part (NAS 6.1 items 12-14) was already in. New at the close-out: Expenditure Profile Statement 6, grants for creation of capital assets (`union_fiscal_gcca`, Actuals 2023-24 3,03,915.55, by ministry, demand and scheme), and the audited IGAS-2 capital column by grantee (`union_fiscal_fa_gia`: State Governments 1,19,435.32; UT Governments 4,522.41; autonomous bodies 1,39,896.67). The two tie to Rs 0.01 cr (RECONCILIATION GOV-14). No ingested series equals the cell by itself. Part of the capital grants goes to units inside general government, such as central autonomous bodies, and States record no capital-grant line. The verifier also noted that `stat6.grand_total` is declared `control_total` for K6 where `partial` is the honest extent (union_fiscal close-3, still open at the final run; the coverage state is the same either way). |
| K7 | Acquisition of financial assets by sector and instrument | covered | `mospi_nas_2026_s5_3` (partial)<br>`rbi_financial_accounts_fsf_balance_sheets` (full) |  |
| K8 | Incurrence of liabilities by sector and instrument | covered | `external_sector_external_debt` (partial)<br>`external_sector_external_debt_by_sector` (partial)<br>`mospi_nas_2026_s5_3` (partial)<br>`rbi_financial_accounts_fsf_balance_sheets` (full) |  |
| K7a | Household financial assets by instrument (new base) | covered | `mospi_nas_2026_s5_3` (full)<br>`rbi_financial_accounts_hh_finsav_52ab` (partial)<br>`union_fiscal_nssf` (partial) |  |
| K8a | Household borrowing (new base) | covered | `mospi_nas_2026_s5_3` (full)<br>`rbi_banking_corporate_bsr1_mar2024` (partial)<br>`rbi_banking_corporate_rtp_banks` (partial)<br>`rbi_financial_accounts_hh_finsav_52ab` (partial) |  |
| K8b | Rest-of-world financial account by instrument with bop_function tags (FDI, FPI, ECB, NRI deposi… | **partial** | `external_sector_bop_bpm6_annual` (partial)<br>`external_sector_bop_overall_annual` (partial)<br>`external_sector_iip_quarterly` (partial)<br>`finsector_markets_sebi_foreign` (partial)<br>`mospi_nas_2026_s6_1` (partial)<br>`rbi_financial_accounts_fsf_balance_sheets` (partial) | **one split blocked by terms.** BoP financial-account instrument totals are ingested (external_sector BPM6 and old-format BoP; NAS 6.1 items 16-17; SEBI FPI by instrument). The FPI-debt split between G-secs and corporate bonds is not in the SEBI tables. NSDL's FPI Monitor forbids reproduction (finsector_markets-1), so it was not fetched. The gap map already treats that split as estimated (fallback: FSF RoW holdings, which are ingested). |
| K8c | Change in foreign-exchange reserves (BoP basis, excluding valuation) | covered | `external_sector_bop_bpm6_annual` (full)<br>`external_sector_bop_bpm6_quarterly` (partial) |  |
| D1 | Household residual: NAS household GDI - PFCE - household saving (5,71,133) | covered | `mospi_nas_2026_derived_residuals` (full) |  |
| D2 | NAS-BoP reconciliation: CIF adjustment on imports of services (2,12,499) | covered | `io_tables_sut_supply` (full)<br>`mospi_nas_2026_s6_1` (full) |  |
| D3 | Official saving-investment errors and omissions: GCF - saving - net capital inflow (3,58,634) | covered | `mospi_nas_2026_derived_residuals` (full) |  |
| D4 | GDP expenditure discrepancy | covered | `mospi_nas_2026_s1_1` (full) |  |
| S7 | IGST collections and settlement between Centre and States (the 'GST rupee' route) | **partial** | `union_fiscal_fa_receipts` (partial)<br>`union_fiscal_pib_gst` (partial) | **blocked source (policy), plus a bot challenge.** GSTN settlement files are not automated (D1-1c). The Finance Accounts give the annual IGST collection and apportionment. New at the close-out: PIB's monthly GST releases for April and May 2023 (`union_fiscal_pib_gst`, 178 rows, which also carry the April-May 2022 comparison columns). The June 2023 release request met an F5 bot challenge, and the unit stopped as D1-1b requires (union_fiscal-1). So 2 of 12 months of 2023-24 are in. S7 is a memo satellite: IGST already sits inside the post-settlement T_CGST/T_SGST. |
| S9 | Gross social contributions and benefits of funded schemes (EPF/EPS, NPS, CMPF, GPF, PPF, life i… | **partial** | `finsector_markets_epfo_ar` (partial)<br>`finsector_markets_epfo_eps_outgo` (partial)<br>`finsector_markets_irdai_life` (partial)<br>`finsector_markets_pfrda_nps` (partial)<br>`finsector_markets_pfrda_sg` (partial)<br>`state_fiscal_rbi_sf_appendices` (partial)<br>`union_fiscal_fa_provident_funds` (partial)<br>`union_fiscal_nssf` (partial) | **partly not published.** Ingested: EPFO un-exempted contributions and payments, and the EPS outgo split into monthly pensions and withdrawal benefits (`finsector_markets_epfo_eps_outgo`, new; 2023-24: 15,130.68 + 7,908.25 = 23,038.94). Also ingested: NPS contributions, life premiums and benefits, PPF accretion, and the Union GPF gross flows from Finance Accounts Statement 14 (MH 8009: additions 68,989.35, discharges 63,930.50, new; they equal the AFS, RECONCILIATION GOV-17/18). New at the final run: gross State provident-fund flows, 2023-24 Accounts, all States and UTs with legislature, from RBI State Finances 2025-26 (`state_fiscal_rbi_sf_appendices`: App. III VI.1 receipts 1,03,892.37 and App. IV VII.1 disbursements 91,398.49; state_fiscal-25, verified from raw). These are gross public-account lines, not net figures. Caveats: RBI says they also include "other savings deposits", the file does not say whether receipts include interest credited, and there is no State-wise split. Still missing: exempted PF trusts (not published, finsector_markets-6), CMPF (no registered source) and NPS withdrawals (not published as amounts, finsector_markets-32). |
| S3 | Remittance sources by country | covered | `external_sector_remittance_survey` (full) |  |
| S4 | From-whom-to-whom financial flows (who funds whom) | covered | `rbi_financial_accounts_fsf_fwtw` (full) |  |
| S6 | Physical energy use by industry | **partial** | `io_tables_energy_psut` (partial) | **partial by design of the source.** Energy Statistics 2026 Ch. 9 physical supply-use tables (`io_tables_energy_psut`, 324 values in PJ, 2023-24 and 2024-25 P) are now written and declared. They cover 7 industry groups (ISIC A, B, C, D, transport and storage, construction, other industries), not the 34 SAM activities (io_tables-14). Independently verified at the close-out, 324 of 324 (io_tables verify, close-out pass). |

### ESTIMATED refs (inputs only; the estimate itself is Phase 2): 56 refs (missing 1, partial 55)

| Ref | Cell | Coverage | Datasets serving it (extent) | Note |
|---|---|---|---|---|
| P7a | Product taxes split by tax type within each commodity | partial | `hces_consumption_a10f_item_fractile` (partial)<br>`hces_consumption_cpi2024_weights` (partial)<br>`io_tables_sut_supply` (control total)<br>`mospi_nas_2026_s1_1` (control total)<br>`state_fiscal_fc16_kfi` (control total)<br>`union_fiscal_fa_receipts` (partial)<br>`union_fiscal_ppac_exchequer` (partial) |  |
| P7b | Valuation layer: product taxes by commodity x tax type x use category (IC by activity group, PF… | partial | `hces_consumption_cpi2024_weights` (partial)<br>`io_tables_sut_supply` (control total)<br>`mospi_nas_2026_s1_1` (control total)<br>`union_fiscal_ppac_exchequer` (partial) |  |
| P9a | Product subsidies split by paying government (Centre vs States) | partial | `state_fiscal_fc16_subsidies` (partial)<br>`state_fiscal_rbi_sf_statements` (partial)<br>`union_fiscal_exp_profile` (partial) |  |
| P10a | Production taxes/subsidies split Centre vs States | partial | `state_fiscal_fc16_kfi` (partial) |  |
| V1a | Split of CE into regular-salaried vs casual wages by activity | partial | `labour_enterprise_surveys_asi_2324_industry` (partial)<br>`labour_enterprise_surveys_asuse_2324_activity` (partial)<br>`labour_enterprise_surveys_plfs_earnings` (partial)<br>`labour_enterprise_surveys_plfs_earnings_api` (partial)<br>`labour_enterprise_surveys_plfs_industry_dist` (partial)<br>`labour_enterprise_surveys_plfs_industry_status` (partial)<br>`labour_enterprise_surveys_plfs_status_dist` (partial) |  |
| V2a | Split of OS/MI into mixed income vs operating surplus by activity | partial | `labour_enterprise_surveys_asi_2324_industry` (partial)<br>`labour_enterprise_surveys_asuse_2324_activity` (partial)<br>`mospi_nas_2026_s7_1c` (partial) |  |
| F1a | Labour income split across the 10 household groups | partial | `io_tables_ifpri_2223_datapaper` (partial)<br>`labour_enterprise_surveys_plfs_earnings` (partial)<br>`labour_enterprise_surveys_plfs_earnings_api` (partial)<br>`labour_enterprise_surveys_plfs_status_dist` (partial) |  |
| F2 | Mixed income to the 10 household groups | partial | `hces_consumption_a2_fractile_persons` (partial)<br>`labour_enterprise_surveys_asuse_key_indicators` (partial)<br>`labour_enterprise_surveys_plfs_earnings` (partial)<br>`labour_enterprise_surveys_plfs_earnings_api` (partial)<br>`labour_enterprise_surveys_sas_2019_income_by_landclass` (partial) |  |
| F3 | Household-sector gross operating surplus paid to household groups, total | partial | `mospi_nas_2026_s7_1c` (partial) |  |
| F3a | Owner-occupied dwellings: imputed-rent operating surplus by group | partial | `hces_consumption_a6_group_fractile` (partial)<br>`labour_enterprise_surveys_aidis_2019_press_note` (partial)<br>`labour_enterprise_surveys_aidis_2019_quintile` (partial)<br>`mospi_nas_2026_s8_13` (partial) |  |
| F3b | Actual rent received by household landlords, by group | partial | `hces_consumption_a10f_item_fractile` (partial) |  |
| F3c | Operating surplus of household partnerships, trusts and NPISH, by group | partial | `labour_enterprise_surveys_asuse_2324_activity` (partial) |  |
| F4a | Split of financial-corporation GOS across RBI, banks, NBFCs, insurance & pension | partial | `finsector_markets_irdai_life` (partial)<br>`finsector_markets_irdai_nonlife` (partial)<br>`rbi_banking_corporate_rbi_accounts` (partial)<br>`rbi_banking_corporate_rtp_banks` (partial)<br>`rbi_banking_corporate_rtp_coop` (partial)<br>`rbi_banking_corporate_rtp_nbfi` (partial) |  |
| F4b | Split of general-government GOS (= CFC) between Centre and States | partial | `mospi_nas_2026_s4_1` (partial)<br>`union_fiscal_fa_expenditure` (partial) |  |
| C1a | PFCE by commodity split across the 10 household groups | partial | `hces_consumption_a10f_item_fractile` (partial)<br>`hces_consumption_a2_fractile_persons` (partial)<br>`io_tables_ifpri_2223_datapaper` (partial)<br>`io_tables_sut_use` (control total) |  |
| C4a | Dwelling services (21,48,044 cr = actual rent + imputed rent + government-provided housing) by … | partial | `hces_consumption_a10f_item_fractile` (partial)<br>`hces_consumption_a6_group_fractile` (partial)<br>`labour_enterprise_surveys_aidis_2019_press_note` (partial)<br>`labour_enterprise_surveys_aidis_2019_quintile` (partial)<br>`mospi_nas_2026_s5_1` (partial) |  |
| C4b | FISIM and insurance service charges consumed by households | partial | `labour_enterprise_surveys_aidis_2019_press_note` (partial)<br>`labour_enterprise_surveys_aidis_2019_quintile` (partial)<br>`mospi_nas_2026_s1_13` (partial)<br>`mospi_nas_2026_s5_1` (partial)<br>`rbi_banking_corporate_bsr1_mar2024` (partial) |  |
| C4c | NPISH final consumption included in PFCE | partial | `mospi_nas_2026_s1_14` (control total) |  |
| C4d | Out-of-pocket health and education spending | partial | `hces_consumption_a10f_item_fractile` (partial)<br>`hces_consumption_cms_education_2025` (partial)<br>`hces_consumption_health596` (partial) |  |
| C2a | GFCE by commodity split Centre vs States (incl. local bodies) | partial | `mospi_nas_2026_s4_1` (partial)<br>`state_fiscal_rbi_sf_appendices` (control total)<br>`union_fiscal_exp_profile` (partial)<br>`union_fiscal_fa_expenditure` (partial) |  |
| I1a | GFCF by commodity x investing institution | partial | `io_tables_sut_use` (control total)<br>`mospi_nas_2026_s1_11` (partial)<br>`state_fiscal_rbi_sf_appendices` (control total)<br>`union_fiscal_fa_expenditure` (partial) |  |
| I2a | Valuables with no institutional sector in NAS (3,76,232 SUT total - 1,72,127) | partial | `io_tables_sut_use` (partial)<br>`mospi_nas_2026_s1_1` (partial) |  |
| T1a | Union taxes converted to NAS accrual concept and fitted to the SUT product-tax margin | partial | `io_tables_sut_supply` (control total)<br>`mospi_nas_2026_s1_1` (control total)<br>`union_fiscal_fa_receipts` (partial) |  |
| T2x | State taxes converted to NAS accrual concept and fitted to the SUT product-tax margin | partial | `io_tables_sut_supply` (control total)<br>`mospi_nas_2026_oldbase_soa_s4_0` (partial)<br>`state_fiscal_rbi_sf_appendices` (control total) |  |
| T2b | Uses of GST compensation cess: grants to States and cess applied to back-to-back loan recovery | partial | `state_fiscal_fc16_kfi` (partial)<br>`state_fiscal_rbi_sf_appendices` (partial)<br>`union_fiscal_fa_expenditure` (partial)<br>`union_fiscal_fa_receipts` (partial) |  |
| T3a | Personal income tax by household group | **missing** | - | No input ingested. CBDT is not automated (D1-1c), no open document gives an ITR income-range distribution, and IFPRI prints no usable table (union_fiscal-3, io_tables-14). The Phase 2 method must rest on PLFS published tables and IFPRI shares, or the cell stays unfilled. |
| T4a | Corporation tax by paying sector | partial | `finsector_markets_irdai_life` (partial)<br>`finsector_markets_irdai_nonlife` (partial)<br>`mospi_nas_2026_oldbase_soa_s2_1` (partial)<br>`mospi_nas_2026_oldbase_soa_s2_2` (partial)<br>`rbi_banking_corporate_rtp_banks` (partial)<br>`rbi_banking_corporate_rtp_coop` (partial)<br>`rbi_banking_corporate_rtp_nbfi` (partial) |  |
| R2k | Capital grants Centre to States (grants for creation of capital assets) | partial | `union_fiscal_exp_profile` (partial)<br>`union_fiscal_fa_gia` (partial)<br>`union_fiscal_gcca` (partial) |  |
| R3b | Government interest converted to accrual SNA interest | partial | `mospi_nas_2026_s1_13` (partial)<br>`state_fiscal_rbi_sf_appendices` (control total)<br>`union_fiscal_fa_expenditure` (partial) |  |
| R3a | Government interest split by holder sector | partial | `rbi_financial_accounts_dea_central_debt` (partial)<br>`rbi_financial_accounts_dea_gsec_ownership` (partial)<br>`rbi_financial_accounts_hbs_gsec_ownership` (partial)<br>`union_fiscal_fa_expenditure` (partial) |  |
| R4 | Interest paid by financial corporations on deposits and borrowings (SNA interest, net of FISIM) | partial | `mospi_nas_2026_s1_13` (partial)<br>`rbi_banking_corporate_rtp_banks` (partial)<br>`rbi_banking_corporate_rtp_nbfi` (partial)<br>`rbi_financial_accounts_fsf_balance_sheets` (partial) |  |
| R5 | Interest paid to financial corporations on loans (SNA interest) | partial | `mospi_nas_2026_s1_13` (partial)<br>`rbi_banking_corporate_rtp_banks` (partial)<br>`rbi_banking_corporate_rtp_coop` (partial)<br>`rbi_banking_corporate_rtp_nbfi` (partial)<br>`rbi_financial_accounts_fsf_balance_sheets` (partial) |  |
| R8 | Dividends and other distributed income of corporations to non-government holders | partial | `external_sector_fla_census` (partial)<br>`finsector_markets_sebi_mf` (partial)<br>`rbi_financial_accounts_fsf_instrument_sector` (partial) |  |
| R8a | Household property income (interest, dividends, MF look-through) by household group | partial | `labour_enterprise_surveys_aidis_2019_press_note` (partial)<br>`labour_enterprise_surveys_aidis_2019_quintile` (partial)<br>`rbi_financial_accounts_hh_finsav_52ab` (partial)<br>`union_fiscal_nsi_collections` (partial) |  |
| R9b | Imputed social contributions for OPS pensions returned by households to government (D612) | partial | `state_fiscal_fc16_kfi` (control total)<br>`union_fiscal_fa_expenditure` (partial) |  |
| R9c | Investment income attributed to insurance policyholders and PF/pension members (D44) | partial | `finsector_markets_epfo_ar` (partial)<br>`finsector_markets_irdai_life` (partial)<br>`finsector_markets_irdai_nonlife` (partial)<br>`union_fiscal_fa_expenditure` (partial) |  |
| R9a | Government pensions (R9) by household group | partial | `hces_consumption_a2_fractile_persons` (partial)<br>`io_tables_ifpri_2223_datapaper` (partial)<br>`labour_enterprise_surveys_plfs_enterprise_type` (partial) |  |
| R10 | Current cash transfers to households that NAS treats as D62/D7 (State cash schemes for women, s… | partial | `hces_consumption_a2_fractile_persons` (partial)<br>`state_fiscal_fc16_subsidies` (partial)<br>`union_fiscal_fa_expenditure` (partial) |  |
| R11a | Remittances by household group | partial | `external_sector_remittance_survey` (partial)<br>`hces_consumption_a10s_state_item` (partial)<br>`hces_consumption_a2_fractile_persons` (partial)<br>`io_tables_ifpri_2223_datapaper` (partial) |  |
| R12a | Outward transfers by household group | partial | `external_sector_lrs_outward` (partial)<br>`mospi_nas_2026_s6_1` (control total) |  |
| R13 | Property income received from RoW, by domestic recipient | partial | `external_sector_bop_bpm6_annual` (partial)<br>`external_sector_fla_census` (partial)<br>`mospi_nas_2026_s6_1` (control total)<br>`rbi_banking_corporate_rbi_accounts` (partial) |  |
| R14 | Property income paid to RoW, by domestic payer | partial | `external_sector_bop_bpm6_annual` (partial)<br>`external_sector_ecb_monthly_2324` (partial)<br>`external_sector_external_debt` (partial)<br>`external_sector_external_debt_by_sector` (partial)<br>`mospi_nas_2026_s6_1` (control total) |  |
| R14a | Reinvested earnings on inward FDI (D43), paid to RoW | partial | `external_sector_bop_bpm6_annual` (partial)<br>`external_sector_fla_census` (partial)<br>`mospi_nas_2026_s1_9` (control total) |  |
| R16 | Fees, fines and other current transfers from households to government (incl. motor-vehicle tax … | partial | `hces_consumption_a10f_item_fractile` (partial)<br>`state_fiscal_rbi_sf_appendices` (partial)<br>`union_fiscal_rb_receipts` (partial) |  |
| R17 | Net non-life insurance premiums and claims | partial | `finsector_markets_irdai_nonlife` (partial)<br>`finsector_markets_irdai_summary` (control total)<br>`mospi_nas_2026_s8_12` (partial) |  |
| R18 | Non-product subsidies and other current transfers to corporations (e.g. interest subvention, vi… | partial | `state_fiscal_rbi_sf_statements` (partial)<br>`union_fiscal_exp_profile` (partial) |  |
| K2a | FC saving split by sub-sector | partial | `finsector_markets_irdai_life` (partial)<br>`finsector_markets_irdai_nonlife` (partial)<br>`rbi_banking_corporate_rbi_accounts` (partial)<br>`rbi_banking_corporate_rtp_banks` (partial)<br>`rbi_banking_corporate_rtp_nbfi` (partial) |  |
| K3a | Government saving split Centre vs States | partial | `mospi_nas_2026_s1_9` (control total)<br>`state_fiscal_fc16_kfi` (partial)<br>`state_fiscal_ulb_cityfinance` (partial)<br>`union_fiscal_afs` (partial) |  |
| K4a | Household saving by group | partial | `io_tables_ifpri_2223_datapaper` (partial)<br>`mospi_nas_2026_s1_9` (control total) |  |
| K7b | Counterparty rule when NAS 5.3 / BoP replace FSF values | partial | `external_sector_bop_bpm6_annual` (partial)<br>`mospi_nas_2026_s5_3` (partial)<br>`rbi_financial_accounts_fsf_balance_sheets` (partial)<br>`union_fiscal_nssf` (partial) |  |
| K8d | Net purchases of Central and State government securities by holder | partial | `rbi_financial_accounts_fsf_balance_sheets` (partial)<br>`rbi_financial_accounts_hbs_gsec_ownership` (partial) |  |
| K8e | States' repayment of GST back-to-back loans, financed from compensation cess | partial | `state_fiscal_fc16_kfi` (partial) |  |
| K9 | Per-sector reconciliation residual: NAS net lending (saving - GCF + capital transfers) minus FS… | partial | `mospi_nas_2026_s1_14` (partial)<br>`rbi_financial_accounts_fsf_balance_sheets` (partial) |  |
| K9b | RBI surplus timing item (accrued surplus payable vs cash transferred) | partial | `rbi_banking_corporate_rbi_accounts` (partial)<br>`rbi_banking_corporate_rbi_surplus_timing` (partial)<br>`rbi_financial_accounts_fsf_balance_sheets` (partial)<br>`union_fiscal_fa_receipts` (partial) |  |
| S8 | Food subsidy (free PDS grain) as social transfer in kind by household group - actual final cons… | partial | `hces_consumption_a10f_item_fractile` (partial)<br>`hces_consumption_a10sw_state_item_imputed` (partial)<br>`union_fiscal_exp_profile` (control total) |  |
| S5 | Household wealth and debt by group (ABM calibration) | partial | `labour_enterprise_surveys_aidis_2019_press_note` (partial)<br>`labour_enterprise_surveys_aidis_2019_quintile` (partial)<br>`labour_enterprise_surveys_sas_2019_income_by_landclass` (partial)<br>`rbi_financial_accounts_hh_finsav_52ab` (partial) |  |

### INTERNATIONAL refs: 3 refs (partial 3)

| Ref | Cell | Coverage | Datasets serving it (extent) | Note |
|---|---|---|---|---|
| P6a | Memo/variant only: imports by using activity (non-competitive import matrix) for an optional mu… | partial | `io_tables_adb_ind_iot` (partial)<br>`io_tables_icio_india` (partial) |  |
| S1 | Goods exports/imports by partner and product group | partial | `trade_satellites_comtrade_fy_2324` (partial)<br>`trade_satellites_imf_imts_fy` (partial) |  |
| S2 | Services trade by partner and EBOPS category | partial | `external_sector_ites_survey` (partial)<br>`trade_satellites_batis_2023_2024` (partial) |  |
