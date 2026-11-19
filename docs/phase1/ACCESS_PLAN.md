# Phase 1 access plan

Prepared 2026-09-29 (last checks 15:19 IST) by the registry-refresh / access-planner agent. Machine-readable version: [`data/access_plan.csv`](../../data/access_plan.csv) (one row per source, every URL that was checked, the substitute and the gap-map refs that lose precision). Rules applied: DECISIONS D1-1 (public files only, browser-like headers allowed, >= 2 s per host, no challenge solving, no logins, GSTN and CBDT not automated) and D1-2 (no unit-level microdata).

Nothing was downloaded into the repo. Probe files sit in the session scratch folder outside the repo and are not evidence for any number.

## 1. Summary

- **70 sources** planned: every id in `data/gap_map.csv` (primary and secondary columns, 53 ids) plus the sources named only in its method column.
- Obtainable: **yes** 44, **yes-with-browser-headers** 14, **blocked-login** 4, **blocked-terms** 4, **blocked-challenge** 2, **manual-only** 2.
- **Every OFFICIAL SAM cell keeps a primary source that can be fetched under D1-1.** The one OFFICIAL row with a blocked primary is the satellite **S7** (IGST settlement memo, GSTN not automated): it falls back to annual Finance Accounts and FC16 totals and loses its State-by-month detail. Seven ESTIMATED or INTERNATIONAL cells have a blocked primary and use the substitutes in section 5: **P6a** (ICIO challenge), **V1a, F1a, F2, R9a** (PLFS unit data, D1-2), **F4a** (STRBI on DBIE only), **T3a** (CBDT, D1-1c).
- **rbidocs.rbi.org.in is intermittent.** The full browser header set fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then every rbidocs URL returned the F5 challenge page (HTTP 200, 5,691 B of HTML) from about 15:00 IST. Probing stopped there, as D1-1(b) requires. www.rbi.org.in HTML pages were never challenged. 13 sources use rbidocs files; most also have an HTML table on www.rbi.org.in.
- Three gap-map ids are not registry ids: `ppac_exchequer` = `ppac_petroleum_exchequer`, `dea_public_debt_quarterly` = `dea_public_debt_reports`, `imf_sdmx_portal` = `imf_sdmx`. The registry now carries them as `aliases`; the gap map itself was not edited.
- Two sources used by the method column are not in the registry yet: PIB monthly GST releases (the GSTN substitute) and the annual reports of public financial institutions (NABARD, SIDBI, EXIM, NHB, PFC, REC, IRFC, LIC, HDFC Bank). The GST-rate schedule behind the P7a prior (CBIC rate notifications) is also unregistered.

## 2. Releases due 29-30 September 2026

| Release | Registry id | Status at last check | Effect on the 2023-24 SAM |
|---|---|---|---|
| ASI 2024-25 results (MoSPI ARC: 29 Sep) | `mospi_asi` | Not released as of 15:19 IST on 29 Sep 2026 (MoSPI release feed and the ASI API still end at 2023-24); due later on 29 Sep per the ARC. | None: V1a cross-check uses ASI 2023-24 (Vol I and Summary Results PDFs re-confirmed). |
| External debt, end-June 2026 | `rbi_external_debt` | Not released as of 15:19 IST on 29 Sep 2026 (RBI press-release listing); expected 30 Sep 2026. | None: 2023-24 uses end-March 2024 (HBS T145/T146). |
| International investment position, end-June 2026 | `rbi_intl_investment_position` | Not released as of 15:19 IST on 29 Sep 2026 (RBI press-release listing); expected 30 Sep 2026. | None (context only). |
| Invisibles, Q1 2026-27 | `rbi_invisibles_quarterly` | Not released as of 15:19 IST on 29 Sep 2026 (RBI press-release listing); expected 30 Sep 2026. | None: 2023-24 invisibles are in HBS T126/T127. |
| BoP Q1 2026-27 | `rbi_bop_quarterly` | Already out (1 Sep 2026, press release 63493 re-fetched). | None. |
| DEA Quarterly Report on Public Debt, Apr-Jun 2026 | `dea_public_debt_reports` | Not on the DEA listing (last year's came 3 Oct). | None: R3a/K8d use Jan-Mar 2023 and Jan-Mar 2024 reports (both located). |
| CGA monthly accounts, August 2026 | `cga_monthly_accounts` | Due 30 Sep; not a gap-map source. | None. |
| RBI Bulletin September 2026 (household financial saving 52(a)/(b)) | `rbi_hh_fin_savings` | Out 25 Sep (press release 28 Sep); already in the registry. | Revised 2023-24 household financial saving; K7a uses NAS 5.3 anyway. |
| PFRDA monthly statistics | `pfrda_nps_statistics` | M6 to Aug 2026 already recorded (29 Sep). | None. |
| MoSPI release feed | all MoSPI ids | Latest items: IIP Aug 2026 and infrastructure flash report (28 Sep). Nothing new for gap-map sources. | None. |

## 3. How to fetch (rules for the ingest agents)

Units download only through `ctx.fetch` (docs/phase1/PIPELINE_GUIDE.md s.4), which already sends browser-like headers, waits 2 s per host, uses the OS trust store and raises `AccessBlocked` on challenges. The points below are what this plan found on top of that.

- Headers: User-Agent (current Chrome), Accept, Accept-Language, Sec-Fetch-Dest/Mode/Site/User, Upgrade-Insecure-Requests. No cookies carried between runs; session cookies set by the site during one request chain (ASP.NET cookieless redirects on NSI, PIB) are ordinary.
- Rate: at least 2 s between requests to one host; use 5 s for rbidocs.rbi.org.in. Hash every file (sha256) into the raw manifest, keep the server Last-Modified separately.
- Validate content, not status: check magic bytes (`PK` XLSX/zip, `%PDF`, OLE2 `D0 CF 11 E0` for .xls, JSON). rbidocs, OECD (Cloudflare) and gst.gov.in return challenge pages; MoSPI returns 403 for missing files and 200 for any SPA path.
- On the first challenge page from a host: stop that host for the run, log it in docs/phase1/issues/<unit>.md, and retry on a later run. Never solve it, never switch to a browser session.
- TLS quirks: api.mospi.gov.in needs legacy renegotiation (Python OpenSSL refuses; Windows curl/Schannel works, or an SSL context with OP_LEGACY_SERVER_CONNECT). dea.gov.in and nsiindia.gov.in send incomplete chains (use the OS trust store, e.g. `truststore`).
- MoSPI file lists: `POST https://www.mospi.gov.in/api/publications-reports/get-web-chapter-data` with `{"publication_id": "2861"}` (NAS 2026), `"847"` (SUT), `"434"` (NAS 2024). GET returns 403.
- RBI hashed URLs: scrape them from the www.rbi.org.in listing pages (AnnualPublications.aspx?head=..., ECBView.aspx, BS_ViewBulletin.aspx) rather than hard-coding.
- Changing file names: PPAC (upload timestamp prefix), PFRDA (?v= query), GSTN (not used). Scrape the link each run.
- **Framework request:** api.mospi.gov.in (eSankhyiki: PLFS, ASUSE, ASI, HCES, NSS-77 AIDIS, NAS API) fails TLS in Python with UNSAFE_LEGACY_RENEGOTIATION_DISABLED even with the OS trust store; `ctx.fetch` needs an opt-in legacy-renegotiation SSL context for that host (or the units fall back to the PDF reports).
- Sources not yet in the registry (PIB GST releases, CBIC GST rates, public financial institutions' annual reports) go into `data/registry_additions/<unit>.yaml` as the guide's s.8 describes.
- Budget actuals for 2023-24 live in the **Budget 2025-26 archive** (`/budget2025-26/doc/...`); receipt tables there are `.xls`, not `.xlsx`.

## 4. Source-by-source plan

Refs: **bold** = the source is the primary source of that cell; plain = secondary; *italic* = named in the method column only. Full URLs are in the CSV.

| Source | Unit | Gap-map refs | Obtainable | Files for 2023-24 |
|---|---|---|---|---|
| `mospi_nas_2026_publication` | mospi_nas_2026 | **C2a** **C4b** **C4c** **D1** **D2** **D3** **D4** **F3** **F4** **F4b** **I1a** **I2** **I3a** **K1** **K2** **K3** **K4** **K4a** **K5** **K6** **K7a** **K7b** **K8a** **K9** **R11** **R12** **R12a** **R14a** **V2a** **V3** **V4** C1 C2 C4a F1 F3a I1 I2a K3a K7 K8 K8b P1 P10 P2 P5 P6 R13 R14 R17 R3b R4 R5 S8 T1a T2x V1 V2 | yes | All 65 NAS 2026 statement XLSX (FE 2022-23, FE 2023-24, FRE 2024-25; PE 2025-26 in 8.17/8.18). Needed first: 1.1, 1.5, 1.6, 1.9, 1.11, 1.13, 1.14, 4.1, 4.2, 5.1, 5.2, 5.3, 6.1, 6.2, 7.1, 7.1A, 7.1B, 7.1C, 7.2, 8.15.1. File list from POST /api/publications-reports/get-web-chapter-data {"publication_id":"2861"}. |
| `mospi_sut_2022base` | io_tables | **C1** **C2** **F1** **I1** **I2a** **I3** **P1** **P10** **P2** **P3** **P4** **P5** **P6** **P7** **P7a** **P7b** **P8** **P9** **V1** **V2** D2 F3 F4 I1a I2 T1a T2x | yes | Supply_Use_table_2023-24_(1).xlsx (reference year) and Supply_Use_table_2022-23_(1).xlsx (validation year), plus the methodological note PDF. |
| `mospi_nas_api` | mospi_nas_2026 | - | yes | getNASData for base_year=2022-23 headline aggregates (cross-check only; statements are the primary input). |
| `mospi_nas_sources_methods_2026` | mospi_nas_2026 | C4a D3 K7a P10 P7a P7b R9b T1a | yes | Sources and Methods 2026 PDF (method reference: s.3.1.1, 4.4, 4.6, 7.4.8, 23.4, 26.6, 27.6.8, 30.7). Text only - no numbers are taken from it. |
| `mospi_nas_old_base_2011_12` | mospi_nas_2026 | **T4a** | yes | NAS 2024 (old base) sequences: 1.15, 2.0-2.2 (NFC), 3.0-3.2 (FC), 4.0 (GG), 5.0 (households), 6.0 (RoW); or NAS2024_All_Statements.xlsx. Used as priors for T4a (D5 by sector) and P10a (D29/D39). |
| `mospi_energy_statistics` | io_tables | **S6** | yes | Energy Statistics India 2026, Chapter 9 PDF (physical energy SUT 2023-24, Tables 9.2A/B). |
| `mospi_hces_2023_24` | hces_consumption | **C1a** **C4d** **S8** C4a F2 F3a F3b R10 R11a R16 R9a *P7a* | yes | HCES 2023-24 Appendix-A Excel tables: TableA2 (households/persons/MPCE by 12 fractiles x State x R/U), TableA6 (item groups x fractile), TableA10F-Fractile-class-All India (item x fractile, value and quantity), TableA10S-State and TableA10SW (State item tables, without/with imputation), TableA1, TableA3; Report 592 PDF. |
| `mospi_hces_unit_data` | hces_consumption | C1a C4d | blocked-login | HCES 2023-24 unit data, NADA catalog 237 (and 224 for 2022-23). |
| `mospi_cpi_2024base` | hces_consumption | *P7a* *P7b* | yes | CPI 2024=100 item list and weights (to build the HCES item -> CPI item -> GST rate map used as the P7a/P7b prior). |
| `nss_health_2025` | hces_consumption | *C4d* | yes | Report No. 596 'Household Social Consumption: Health' (Jan-Dec 2025) PDF - published tables only. |
| `nss_cms_education_2025` | hces_consumption | *C4d* | yes | CMS: Education 2025 report PDF (NSS 80th round, Apr-Jun 2025) - published tables only. |
| `mospi_plfs_annual` | labour_enterprise_surveys | F1a V1a *R10* *T3a* | yes | PLFS Annual Report July 2023-June 2024 PDF (Table 51 casual wages by NIC section; regular wages by sector/State; worker distribution by industry x status); eSankhyiki PLFS API indicator 4 (worker distribution, year 2023-24) and 6-8 (earnings). |
| `mospi_esankhyiki_api` | labour_enterprise_surveys | *C4a* *F1a* *F2* *F3c* *R8a* *V1a* | yes | Shared API client for PLFS / HCES / ASUSE / ASI / NSS-77 (AIDIS, SAS) indicator tables. |
| `mospi_plfs_unit_data` | labour_enterprise_surveys | **F1a** **F2** **R9a** **V1a** F3c R9b T3a | blocked-login | PLFS unit data 2022-23 (catalog 210), 2023-24 (213), CY2025 (284). |
| `mospi_asuse` | labour_enterprise_surveys | **F3c** F2 V1a V2a | yes | ASUSE 2023-24 full report PDF and factsheet; eSankhyiki ASUSE API annual indicators 3/4 (ownership type), 30-35 (emoluments, GVA per worker/establishment) for year 2023-24 by R/U and activity. |
| `mospi_asuse_unit_data` | labour_enterprise_surveys | *F2* *F3c* *V2a* | blocked-login | ASUSE 2023-24 unit data (catalog 238); 2025 (catalog 293). |
| `mospi_asi` | labour_enterprise_surveys | V1a V2a | yes | ASI 2023-24 Volume I PDF and Summary Results PDF; ASI API (year 2023-24, NIC 2008) for emoluments/wages by industry (cross-check for V1a). |
| `mospi_aidis_2019` | labour_enterprise_surveys | **C4a** **F3a** **F3b** **R8a** **S5** C4b | yes | AIDIS 2019 report tables via eSankhyiki NSS-77 AIDIS module (survey_code=1): indicator 5 (assets and cash loans by MPCE quintile), 4 (by asset-holding class), 11 (by asset category), 12 (bullion/ornaments), 26-38 (loans by agency); press note PDF. |
| `mospi_sas_2019` | labour_enterprise_surveys | F2 V2a | yes | SAS 2019 Report 587 PDF (income by source x land-size class); NSS-77 land & livestock API module as a machine-readable alternative. |
| `cga_finance_accounts_aag` | union_fiscal | **K3a** **P10a** **R10** **R3** **R3b** **R7** **R9** **R9b** **T1** **T1a** **T3** **T4** C2a F4b I1a K6 K9b P7a P8 R1 R16 R18 R6 R9c S9 | yes | Union Finance Accounts 2023-24: Statement 1 (summary), 8 (receipts by minor head: MH 0005, 0008, 0009, 0020, 0021, 0037, 0038), 9 (expenditure by minor head incl. MH 2049 interest, 2071 pensions) + 9-Appendix (grants-in-aid), 10, 11 (investments/dividends), 13, 14/14A (debt), 16 (NSSF). AAG 2023-24 not located; AAG 2024-25 App. 12 (object heads) as fallback. |
| `mof_union_budget_2026_27` | union_fiscal | **K8e** **P9a** **R18** **R2k** F4b P9 R1 R15 R7 R9 S7 S8 T1 T2b T3 T4 | yes | 2023-24 ACTUALS come from the Budget 2025-26 archive: Receipt Budget tr.xls (tax by major head), ntr.xls (non-tax incl. dividends by enterprise), annex7.pdf (revenue impact of tax incentives), annex8.pdf (NSSF sources and application, Actual 2023-24), annex11.pdf; Expenditure Profile stat1/stat7 (subsidies)/stat18/stat20/stat21 XLSX; AFS allafs.xlsx; Budget at a Glance bag1/bag3/bag5 XLSX. Budget 2026-27 set only for 2024-25 actuals. |
| `union_budget_transfers_to_states` | union_fiscal | **R2** **T2b** K8e R2k | yes | Expenditure Profile 2025-26 Statement 18 (transfers to States, Actual 2023-24) stat18.xlsx; Demand 42 SBE sbe42.pdf (GST compensation grants). |
| `ppac_petroleum_exchequer` (gap map: `ppac_exchequer`) | union_fiscal | P7a P7b | yes | 'Contribution of Petroleum Sector to Exchequer' XLS (sheet Anx 1), 2014-15 to 2025-26(P): 2023-24 Central excise 2,73,683.88; customs 13,133.73; State VAT/SGST rows. |
| `nsi_small_savings_collections` | union_fiscal | *K7a* *K7b* *R3a* *R8a* | yes | NSI Id_Pk=152 table (gross, withdrawals, net collections 2002-03 to 2025-26). For 2023-24 use together with Receipt Budget 2025-26 Annex 8 (NSSF by instrument) and Finance Accounts 2023-24 Statement 16. |
| `pib_gst_monthly_releases (not in registry)` | union_fiscal | *P7a* *S7* *T2* | yes-with-browser-headers | Ministry of Finance monthly GST collection releases on PIB for Apr 2023-Mar 2024 (published 1st of the following month; PIB stopped them after May-2024 data). PRIDs still to be listed from PIB's release archive. |
| `gstn_gst_statistics` | union_fiscal | **S7** P7a P7b | blocked-terms | (not fetched) statewise_GST_collection_2023-24.xlsx, IGST settlement 2023-24. |
| `gst_monthly_state_revenue` | union_fiscal | S7 | blocked-terms | (not fetched) monthly GST revenue report PDFs. |
| `cbdt_time_series` | union_fiscal | **T3a** T3 T4 | blocked-challenge | (not fetched) Direct Tax Time Series FY 2000-01 to 2024-25; ITR statistics AY 2024-25. |
| `dpe_public_enterprises_survey` | union_fiscal | *F4* *R7* | manual-only | Public Enterprises Survey 2023-24 (edition and file not identified). |
| `pib_tax_devolution_releases` | union_fiscal | *R1* | yes-with-browser-headers | Not needed for 2023-24: devolution comes from Finance Accounts and FC16 KFI A.1.3. |
| `fc16_relevant_data` | state_fiscal | **R1** **T2** **T2x** K3a K8e P10a P7a P9a R2 R3 R9 R9b T2b | yes | 'State Finances - Key Fiscal Indicators.xlsx' (KFI: A.1.1.2 SGST, A.1.3 devolution, A.1.4 grants, B.1.a interest, B.1.b pensions, stamps, vehicles), 'Time series of transfer of resources from Centre to States.xlsx', 'Sector wise Subsidies and Transfers.xlsx', 'State Finance Accounts - Revenue and Expenditure.xlsx'. |
| `rbi_state_finances_study` | state_fiscal | **R16** C2a F4b I1a K3a K6 P10a P7a P9a R1 R10 R18 R2 R2k R3 R3b R7 T2 | yes-with-browser-headers | State Finances 2025-26 edition (2023-24 Accounts): Statements 13 (interest), 14 (tax revenue), 15 (non-tax), 17 (transfers), 36 (subsidies), Appendix Table 2, Appendices I-IV (State-wise detail, Rs lakh). Hashed rbidocs links are listed on the www.rbi.org.in listing page. |
| `cag_state_finance_accounts` | state_fiscal | C2a R10 T2 | yes | Per-State Finance Accounts 2023-24 Vol I/II PDFs from the CAG state-accounts page (public). Machine-readable FA&AA Excel is on CAG SharePoint behind a Microsoft login (not used). |
| `fc16_ulb_cityfinance_dump` | state_fiscal | *C2a* *K3a* | yes | FC16 ULB Data Dump Cityfinance.xlsx (ULB revenue/expenditure to 2023-24). |
| `rbi_municipal_finances` | state_fiscal | *C2a* *K3a* | yes-with-browser-headers | Report on Municipal Finances (Nov 2024) Statements 1-8 (municipal corporations, to 2023-24 BE/RE). |
| `rbi_pri_finances` | state_fiscal | *C2a* *K3a* | yes-with-browser-headers | Finances of Panchayati Raj Institutions (Jan 2024), App. I/II (to 2022-23). |
| `rbi_fsf_fof` | rbi_financial_accounts | **K7** **K8** **K8d** **R4** **R5** **R8** **S4** K1 K7a K7b K8a K8b K9 K9b R3a R8a | yes-with-browser-headers | FSF2023-24_21012026.xlsx (71 sheets: St 1-5 sub-sector balance sheets, 6.1-6.13 FWTW, 7.1-7.13 instrument x sector, 8.1-8.3); Bulletin article (Jan 2026) HTML. |
| `rbi_hh_fin_savings` | rbi_financial_accounts | K4 K7 K7a K8a R8a S5 | yes-with-browser-headers | Bulletin Sept 2026 Current Statistics tables 52(a) flows and 52(b) stocks (2022-23 to 2025-26). |
| `rbi_hbs` | rbi_financial_accounts | K7 K8d R12a R3a | yes-with-browser-headers | HBS 2025-26 T11 (sector saving), T12 (HH financial assets/liabilities), T107 (ownership of Central and State securities), T108/T109 (small savings), T36-T49 (RBI, SCB aggregates). Table index with hashed XLSX and HTML links built from the listing page. |
| `dea_public_debt_reports` (gap map: `dea_public_debt_quarterly`) | rbi_financial_accounts | **R3a** K8 K8d R3a S4 | yes | Quarterly Report on Public Debt Management Jan-Mar 2023 and Jan-Mar 2024 (ownership of G-secs/T-bills, Tables 4.x); Status Paper on Government Debt 2023-24. |
| `rbi_annual_report` | rbi_banking_corporate | **K2a** **K9b** **R6** **R9c** F4a R13 | yes-with-browser-headers | RBI Annual Report 2025-26 Ch XII accounts (5-year surplus row: 87,416.22 paid in 2023-24) and appendix XLSX; for RBI's 2023-24 income/expenditure the AR 2024-25 accounts chapter (prior-year column) - locate via the year selector on the AR listing. |
| `rbi_strbi` | rbi_banking_corporate | **F4a** K2a R4 R5 T4a | manual-only | STRBI 2023-24 bank-group income, expenditure and balance sheets. |
| `rbi_trend_progress` | rbi_banking_corporate | F4a K2a R5 T4a | yes | RTP 2024-25 appendix tables (HTML PublicationsView ids 23642-23681; 2023-24 shown as prior year). RTP 2023-24 edition for full 2023-24 detail via the listing year selector. |
| `rbi_bsr` | rbi_banking_corporate | C4b F4a R4 | yes | Annual BSR-1 March 2024 press release (credit by borrower category/occupation) prid=58036; quarterly June 2023-Dec 2023 releases; detailed tables on DBIE (manual). |
| `rbi_corporate_finances` | rbi_banking_corporate | R8 T4a | yes | 'Performance of Private Corporate Business Sector during 2023-24' press release prid=58186 (sales, staff cost, interest, tax, dividends of listed NGNF companies). |
| `aifi_psu_financial_annual_reports (not in registry)` | rbi_banking_corporate | *F4a* *K2a* *K8* *K8a* *R5* | yes | Annual reports 2023-24 of NABARD, SIDBI, EXIM, NHB, PFC, REC, IRFC, LIC (public-sector FC split, F4a/K2a) and HDFC Bank (merger adjustment, K8a). |
| `rbi_hbs_external` | external_sector | **K8b** **R13** **R14** **R15** K5 K7b K8c P5 P6 R11 R12 R14a V3 V4 | yes-with-browser-headers | HBS 2025-26 T126/T127 (BPM6 BoP US$/Rs), T124/T125, T139-T142 (NRI deposits), T145/T146 (external debt end-March), T149/T150 (IIP BPM6), T197/T198 (quarterly BoP), T199-T204 (quarterly IIP). |
| `rbi_bop_quarterly` | external_sector | **K8c** | yes-with-browser-headers | Quarterly BoP 2023-24 (HBS T198 rupees) and reserve-asset flows (K8c); press releases for vintage flags. |
| `rbi_external_debt` | external_sector | K8 R14 | yes-with-browser-headers | End-March 2024 external debt by borrower/instrument: HBS T145/T146; quarterly release June 2024 for detail. |
| `rbi_nri_deposits` | external_sector | K8b R14 | yes | HBS T139-T142 (outstanding and flows by scheme, 2023-24). |
| `rbi_ecb_monthly` | external_sector | K8b R14 | yes | ECB/FCCB monthly registrations Apr 2023-Mar 2024 = ECBUserView.aspx?Id=235 ... Id=246. |
| `rbi_fla_census` | external_sector | K8b R13 R14 R14a R8 | yes | FLA census 2024-25 round (positions end-March 2024 and 2025, by activity, NFC vs FC) PublicationsView id=23438. |
| `rbi_remittances_survey` | external_sector | **R11a** **S3** | yes | 6th round (2023-24) Bulletin article, Tables 1-2 (source-country and State shares) - HTML article page. |
| `rbi_ites_survey` | external_sector | S2 | yes | Survey on Computer Software & ITES exports for 2023-24 (destination shares) - press release to be pinned from the RBI release archive; 2025-26 round prid=63625 as template. |
| `rbi_lrs_outward_remittances` | external_sector | *R12a* | yes-with-browser-headers | Bulletin Current Statistics table 36 (LRS by purpose), FY 2023-24 (April 2024 or later issue). |
| `rbi_intl_investment_position` | external_sector | *K8b* | yes-with-browser-headers | HBS T149/T150 end-March 2024 (stock context for K8b). |
| `irdai_handbook_insurance` | finsector_markets | **R17** F4a K2a R9c S9 T4a | yes | Handbook on Indian Insurance Statistics 2024-25 zip (T2/T3 life premium, T20/T21 AUM, T24-T26 life accounts, T40-T47 non-life premium/claims; 2023-24 in the time series). |
| `epfo_annual_report_accounts` | finsector_markets | **S9** F4a R9c | yes | EPFO Annual Report 2023-24 ('71.pdf', 27 MB): contributions, settlements, interest credited, investments. |
| `pfrda_nps_statistics` | finsector_markets | R9c S9 | yes | A2 sector-wise AUM (annual, to Mar 2025), M2/M6 monthly AUM; Handbook of NPS Statistics 2024-25 PDF (contributions 2023-24). |
| `sebi_handbook_statistics` | finsector_markets | R8 *K8b* | yes | SEBI Handbook 2025-26 per-table XLSX: T11 corporate bonds, T14 funds mobilised, T56/T58-T63 FPI flows and custodian AUC, T64-T72 MF (2023-24 in the series). |
| `nsdl_fpi_monitor` | finsector_markets | *K8b* | blocked-terms | (not used) FPI investment by instrument. |
| `amfi_monthly_quarterly` | finsector_markets | - | blocked-terms | (not used) |
| `commerce_tradestat` | trade_satellites | S1 | yes | EIDB annual 2023-24 commodity x country export/import tables (HS 2-digit x partner). |
| `imf_sdmx` (gap map: `imf_sdmx_portal`) | trade_satellites | **S1** | yes | IMTS India goods by partner, monthly (for FY 2023-24 partner shares) and annual; BOP for cross-checks. |
| `un_comtrade` | trade_satellites | S1 | yes | Keyless preview API (<=500 records per call): India HS 2-digit x partner, monthly 2023-04..2024-03. |
| `oecd_wto_batis` | trade_satellites | **S2** | yes | BaTIS India services by partner x EBOPS, CY2023 and CY2024 (all-wildcard key). |
| `oecd_icio_2025` | io_tables | **P6a** | blocked-challenge | ICIO 2025 small 2016-2022_SML.zip (India 2022 import-use shares). |
| `adb_mrio` | io_tables | P6a | yes | 'IND IOT 2000, 2007-2024.xlsx' and MRIO files (2023, 2024). |
| `eurostat_figaro` | io_tables | P6a | yes | naio_10_fcp_ii4 with c_orig=IN (India 2022-2024). |
| `ifpri_nexus_sam_india_2022_23` | io_tables | C1a F1a K4a R11a R9a T3a | blocked-login | SAM.tab 2022/23 (Dataverse, guestbook 380); data paper PDF (open). |

## 5. Blocked or restricted sources, substitutes and precision loss

| Source | Status | Why | Best open substitute | Refs that lose precision |
|---|---|---|---|---|
| `mospi_hces_unit_data` | blocked-login | microdata.gov.in registration + Data Access Agreement; DECISIONS D1-2 excludes unit data. | mospi_hces_2023_24 published tables (A2, A6, A10F, A10S, A10SW) and the eSankhyiki HCES API. | C4d (checks against NSS Health/Education only at published-table level); C1a loses nothing the method needs (it was built on A10F). |
| `mospi_plfs_unit_data` | blocked-login | Registration + DAA; DECISIONS D1-2. | mospi_plfs_annual published tables + API (worker distribution by industry x status, earnings by status/sector/State, casual wage by NIC section) crossed with HCES fractile structure; IFPRI data-paper shares as a labelled prior. | V1a (regular/casual split only at NIC-section level, not 34 activities); F1a (no person-level MPCE link: labour income by quintile becomes a coarse estimate); F2 and F3c (self-employment earnings by quintile); R9a and R9b (public-sector earnings by quintile); T3a (taxable income distribution). |
| `mospi_asuse_unit_data` | blocked-login | Registration + DAA; DECISIONS D1-2. | ASUSE 2023-24 report tables and API (ownership type x activity x R/U; GVA and emoluments per worker). | V2a (proprietary vs partnership share of OS only at published activity groups); F2 (R/U split of mixed income by activity group); F3c. |
| `gstn_gst_statistics` | blocked-terms | DECISIONS D1-1(c): gst.gov.in terms class scraping as unauthorised; www.gst.gov.in listing behind an F5 challenge. Not automated. | Union Finance Accounts 2023-24 (MH 0005 CGST, 0008 IGST residual, 0009 cess) + FC16 KFI A.1.1.2 (post-settlement SGST by State) + RBI State Finances St 14 + PIB monthly GST releases (Apr 2023-Mar 2024). | S7 (IGST settlement memo: annual totals only, no regular/ad-hoc settlement detail by State); T2 (SGST split cross-check); P7a/P7b (no monthly GSTN detail - not needed by the method). |
| `gst_monthly_state_revenue` | blocked-terms | Same GSTN host and terms as gstn_gst_statistics (D1-1c). | FC16 KFI SGST (annual, post-settlement) and RBI SF Statement 14. | S7 (State pre/post-settlement monthly detail). |
| `cbdt_time_series` | blocked-challenge | DECISIONS D1-1(c): CBDT actively blocks automated clients (29 Sep: first request 403 bot page, retry 200 - intermittent). Not automated; nothing downloaded. | Union Finance Accounts 2023-24 (MH 0020 corporation tax, MH 0021 income tax, STT) + Receipt Budget 2025-26 Annex 7 (revenue impact of tax incentives: return-filing distributions) + PLFS published earnings. | T3a (tax by household group: no ITR income-range distribution, so the schedule is applied to survey earnings only); T3 (share paid by firms/AOPs); T4 (cross-check only). |
| `dpe_public_enterprises_survey` | manual-only | Content is rendered from a CMS called with a key embedded in the site's JavaScript; using it or the owner's browser is outside D1-1. | Receipt Budget ntr.xls (CPSE dividends), Finance Accounts Statement 11 (investments in CPSEs), NAS 1.9 / 7.1A (public NFC aggregates). | None of the gap-map cells (optional cross-check for R7/F4 only). |
| `cag_state_finance_accounts` | yes | Excel version: blocked-login (SharePoint). | - | - |
| `rbi_strbi` | manual-only | Only on DBIE (Angular SPA + SAP BusinessObjects guest session); programmatic use needs RBI permission. | RBI Trend & Progress 2024-25 appendix tables (HTML PublicationsView: IV.1 banking at a glance, IV.14 RRBs, V.1-V.15 co-operatives, VI.1-VI.9 NBFCs; each with the 2023-24 column) + HBS bank tables. | F4a and K2a (bank-group P&L at RTP aggregation, not bank-wise); R4/R5 (effective rates by bank group only); I1a (FC fixed-asset additions); T4a (SCB tax provisions from RTP). |
| `nsdl_fpi_monitor` | blocked-terms | NSDL terms: 'Reproduction, redistribution and transmission ... strictly prohibited'. | SEBI Handbook T56/T58 (FPI flows by equity/debt) + RBI HBS T127 portfolio investment + FSF RoW holdings. | K8b (FPI-debt split between G-secs and corporate bonds: SEBI debt totals + FSF RoW holdings instead of NSDL route detail). |
| `amfi_monthly_quarterly` | blocked-terms | AMFI terms: personal non-commercial use only; no publication or derivative works. | NAS 5.3 MF component and SEBI HBS T64-T72. | None (no gap-map cell needs AMFI). |
| `un_comtrade` | yes | Full API: registration. | - | S1 only if preview limits bind (HS detail). |
| `oecd_icio_2025` | blocked-challenge | Cloudflare challenge on the zip (29 Sep); not solved (D1-1b). Retry on another day. | ADB MRIO India national IOT (domestic and imported rows, 2000, 2007-2024) or Eurostat FIGARO India cells (API). | P6a (memo import matrix prior: ADB 35-sector WIOD classification instead of ICIO ISIC 45). |
| `ifpri_nexus_sam_india_2022_23` | blocked-login | Dataverse guestbook requires the owner's name and e-mail (identity = registration); not filled by an agent. | IFPRI data paper tables (macro SAM, household-group structure) as labelled priors. | F1a, T3a, R9a fallback priors (quintile shares only as printed in the paper); K4a plausibility check; C1a, R11a checks. |

Distributional cells hit hardest (all already ESTIMATED in the gap map; they become coarser, never unfillable): **F1a** labour income by quintile, **F2/F3c** mixed income and partnership surplus by group, **T3a** income tax by group, **R9a/R9b** pensions and imputed contributions by group, **V1a/V2a** regular-casual and proprietary-partnership splits, **F4a/K2a** financial sub-sector split. Each must carry a wider band on the site and a line in ISSUES.md.

## 6. Ingest units

11 units, each a coherent family one agent can own. Every gap-map ref has its primary source inside exactly one unit's scope; a ref can also appear in other units as a secondary input. Dataset names below are shorthand: prefix each with `<unit>_` (PIPELINE_GUIDE s.5). Effort: S < 0.5 day, M ~1 day, L ~2 days, XL > 3 days of agent time.

| Unit | Effort | Sources | Refs served |
|---|---|---|---|
| `mospi_nas_2026` - National accounts (new base) plus old-base priors | L | `mospi_nas_2026_publication`, `mospi_nas_api`, `mospi_nas_sources_methods_2026`, `mospi_nas_old_base_2011_12` | C1 C2 C2a C4a C4b C4c D1 D2 D3 D4 F1 F3 F3a F4 F4b I1 I1a I2 I2a I3a K1 K2 K3 K3a K4 K4a K5 K6 K7 K7a K7b K8 K8a K8b K9 P1 P10 P2 P5 P6 P7a P7b R11 R12 R12a R13 R14 R14a R17 R3b R4 R5 R9b S8 T1a T2x T4a V1 V2 V2a V3 V4 |
| `io_tables` - Supply-use tables and input-output priors | M | `mospi_sut_2022base`, `mospi_energy_statistics`, `oecd_icio_2025`, `adb_mrio`, `eurostat_figaro`, `ifpri_nexus_sam_india_2022_23` | C1 C1a C2 D2 F1 F1a F3 F4 I1 I1a I2 I2a I3 K4a P1 P10 P2 P3 P4 P5 P6 P6a P7 P7a P7b P8 P9 R11a R9a S6 T1a T2x T3a V1 V2 |
| `hces_consumption` - Household consumption distribution | M | `mospi_hces_2023_24`, `mospi_hces_unit_data`, `mospi_cpi_2024base`, `nss_health_2025`, `nss_cms_education_2025` | C1a C4a C4d F2 F3a F3b P7a P7b R10 R11a R16 R9a S8 |
| `labour_enterprise_surveys` - Labour, enterprise and wealth surveys (published tables only, D1-2) | L | `mospi_plfs_annual`, `mospi_esankhyiki_api`, `mospi_plfs_unit_data`, `mospi_asuse`, `mospi_asuse_unit_data`, `mospi_asi`, `mospi_aidis_2019`, `mospi_sas_2019` | C4a C4b F1a F2 F3a F3b F3c R10 R8a R9a R9b S5 T3a V1a V2a |
| `union_fiscal` - Union government accounts and taxes | L | `cga_finance_accounts_aag`, `mof_union_budget_2026_27`, `union_budget_transfers_to_states`, `ppac_petroleum_exchequer`, `nsi_small_savings_collections`, `pib_gst_monthly_releases (not in registry)`, `gstn_gst_statistics`, `gst_monthly_state_revenue`, `cbdt_time_series`, `dpe_public_enterprises_survey`, `pib_tax_devolution_releases` | C2a F4 F4b I1a K3a K6 K7a K7b K8e K9b P10a P7a P7b P8 P9 P9a R1 R10 R15 R16 R18 R2 R2k R3 R3a R3b R6 R7 R8a R9 R9b R9c S7 S8 S9 T1 T1a T2 T2b T3 T3a T4 |
| `state_fiscal` - State and local government finances | L | `fc16_relevant_data`, `rbi_state_finances_study`, `cag_state_finance_accounts`, `fc16_ulb_cityfinance_dump`, `rbi_municipal_finances`, `rbi_pri_finances` | C2a F4b I1a K3a K6 K8e P10a P7a P9a R1 R10 R16 R18 R2 R2k R3 R3b R7 R9 R9b T2 T2b T2x |
| `rbi_financial_accounts` - Flow of funds, household financial saving, public-debt ownership | L | `rbi_fsf_fof`, `rbi_hh_fin_savings`, `rbi_hbs`, `dea_public_debt_reports` | K1 K4 K7 K7a K7b K8 K8a K8b K8d K9 K9b R12a R3a R4 R5 R8 R8a S4 S5 |
| `rbi_banking_corporate` - RBI, banks, NBFCs and corporate finance | M | `rbi_annual_report`, `rbi_strbi`, `rbi_trend_progress`, `rbi_bsr`, `rbi_corporate_finances`, `aifi_psu_financial_annual_reports (not in registry)` | C4b F4a K2a K8 K8a K9b R13 R4 R5 R6 R8 R9c T4a |
| `external_sector` - Balance of payments, external debt, remittances | M | `rbi_hbs_external`, `rbi_bop_quarterly`, `rbi_external_debt`, `rbi_nri_deposits`, `rbi_ecb_monthly`, `rbi_fla_census`, `rbi_remittances_survey`, `rbi_ites_survey`, `rbi_lrs_outward_remittances`, `rbi_intl_investment_position` | K5 K7b K8 K8b K8c P5 P6 R11 R11a R12 R12a R13 R14 R14a R15 R8 S2 S3 V3 V4 |
| `finsector_markets` - Insurance, pensions and securities markets | M | `irdai_handbook_insurance`, `epfo_annual_report_accounts`, `pfrda_nps_statistics`, `sebi_handbook_statistics`, `nsdl_fpi_monitor`, `amfi_monthly_quarterly` | F4a K2a K8b R17 R8 R9c S9 T4a |
| `trade_satellites` - Trade by partner and services by partner (satellites S1, S2) | M | `commerce_tradestat`, `imf_sdmx`, `un_comtrade`, `oecd_wto_batis` | S1 S2 |

### mospi_nas_2026

- **Scope:** National accounts (new base) plus old-base priors. Effort L.
- **Sources:** `mospi_nas_2026_publication`, `mospi_nas_api`, `mospi_nas_sources_methods_2026`, `mospi_nas_old_base_2011_12`.
- **Files:** `mospi_nas_2026_publication`: All 65 NAS 2026 statement XLSX (FE 2022-23, FE 2023-24, FRE 2024-25; PE 2025-26 in 8.17/8.18). Needed first: 1.1, 1.5, 1.6, 1.9, 1.11, 1.13, 1.14, 4.1, 4.2, 5.1, 5.2, 5.3, 6.1, 6.2, 7.1, 7.1A, 7.1B, 7.1C, 7.2, 8.15.1. File list from POST /api/publications-reports/get-web-chapter-data {"publication_id":"2861"}. `mospi_nas_api`: getNASData for base_year=2022-23 headline aggregates (cross-check only; statements are the primary input). `mospi_nas_sources_methods_2026`: Sources and Methods 2026 PDF (method reference: s.3.1.1, 4.4, 4.6, 7.4.8, 23.4, 26.6, 27.6.8, 30.7). Text only - no numbers are taken from it. `mospi_nas_old_base_2011_12`: NAS 2024 (old base) sequences: 1.15, 2.0-2.2 (NFC), 3.0-3.2 (FC), 4.0 (GG), 5.0 (households), 6.0 (RoW); or NAS2024_All_Statements.xlsx. Used as priors for T4a (D5 by sector) and P10a (D29/D39).
- **Primary for refs:** C2a C4b C4c D1 D2 D3 D4 F3 F4 F4b I1a I2 I3a K1 K2 K3 K4 K4a K5 K6 K7a K7b K8a K9 R11 R12 R12a R14a T4a V2a V3 V4; **also feeds:** C1 C2 C4a F1 F3a I1 I2a K3a K7 K8 K8b P1 P10 P2 P5 P6 P7a P7b R13 R14 R17 R3b R4 R5 R9b S8 T1a T2x V1 V2.
- **Expected datasets:** mospi_nas_2026_<statement> for all 65 NAS 2026 statements (long format: statement, item, year, estimate stage FE/FRE/PE, price basis, value); mospi_nas_2026_api_check (headline aggregates from the API, cross-check only); mospi_nas_2026_oldbase_<stmt> for NAS 2024 sequences 1.15, 2.x, 3.x, 4.0, 5.0, 6.0 (priors for T4a, P10a; status official, base_year 2011-12).
- **Notes:** This is the existing template unit (pipeline/ingest/mospi_nas_2026.py, which already ingests 1.1 and 8.17.1): the plan extends it to the other 63 statements. Bilingual merged headers; parse by label.

### io_tables

- **Scope:** Supply-use tables and input-output priors. Effort M.
- **Sources:** `mospi_sut_2022base`, `mospi_energy_statistics`, `oecd_icio_2025`, `adb_mrio`, `eurostat_figaro`, `ifpri_nexus_sam_india_2022_23`.
- **Files:** `mospi_sut_2022base`: Supply_Use_table_2023-24_(1).xlsx (reference year) and Supply_Use_table_2022-23_(1).xlsx (validation year), plus the methodological note PDF. `mospi_energy_statistics`: Energy Statistics India 2026, Chapter 9 PDF (physical energy SUT 2023-24, Tables 9.2A/B). `adb_mrio`: 'IND IOT 2000, 2007-2024.xlsx' and MRIO files (2023, 2024). `eurostat_figaro`: naio_10_fcp_ii4 with c_orig=IN (India 2022-2024).
- **Primary for refs:** C1 C2 F1 I1 I2a I3 P1 P10 P2 P3 P4 P5 P6 P6a P7 P7a P7b P8 P9 S6 V1 V2; **also feeds:** C1a D2 F1a F3 F4 I1a I2 K4a R11a R9a T1a T2x T3a.
- **Expected datasets:** io_tables_sut_2023_24_supply, io_tables_sut_2023_24_use, io_tables_sut_2023_24_va (155 products x 67 industries; 2022-23 set for validation); io_tables_energy_psut_2023_24 (S6); io_tables_adb_ind_iot; io_tables_figaro_india; io_tables_icio2025_india_2022 (when the challenge clears); io_tables_ifpri_2223_datapaper (printed tables only).
- **Notes:** SUT 2023-24 is the core of the SAM (27 cells). International tables are labelled priors only. The SUT product 43/44 label swap (Q1) is handled in the concordance, not in the raw table.

### hces_consumption

- **Scope:** Household consumption distribution. Effort M.
- **Sources:** `mospi_hces_2023_24`, `mospi_hces_unit_data`, `mospi_cpi_2024base`, `nss_health_2025`, `nss_cms_education_2025`.
- **Files:** `mospi_hces_2023_24`: HCES 2023-24 Appendix-A Excel tables: TableA2 (households/persons/MPCE by 12 fractiles x State x R/U), TableA6 (item groups x fractile), TableA10F-Fractile-class-All India (item x fractile, value and quantity), TableA10S-State and TableA10SW (State item tables, without/with imputation), TableA1, TableA3; Report 592 PDF. `mospi_cpi_2024base`: CPI 2024=100 item list and weights (to build the HCES item -> CPI item -> GST rate map used as the P7a/P7b prior). `nss_health_2025`: Report No. 596 'Household Social Consumption: Health' (Jan-Dec 2025) PDF - published tables only. `nss_cms_education_2025`: CMS: Education 2025 report PDF (NSS 80th round, Apr-Jun 2025) - published tables only.
- **Primary for refs:** C1a C4d S8; **also feeds:** C4a F2 F3a F3b P7a P7b R10 R11a R16 R9a.
- **Expected datasets:** hces2324_a2_fractile_persons; hces2324_a6_group_fractile; hces2324_a10f_item_fractile (leaf codes only, value and quantity, R/U); hces2324_a10s_state_item; cpi2024_item_weights; nss_health_596_tables; cms_education_2025_tables.
- **Notes:** Also owns the HCES item -> SUT commodity map inputs and the CPI item list that the P7a GST-rate prior needs.

### labour_enterprise_surveys

- **Scope:** Labour, enterprise and wealth surveys (published tables only, D1-2). Effort L.
- **Sources:** `mospi_plfs_annual`, `mospi_esankhyiki_api`, `mospi_plfs_unit_data`, `mospi_asuse`, `mospi_asuse_unit_data`, `mospi_asi`, `mospi_aidis_2019`, `mospi_sas_2019`.
- **Files:** `mospi_plfs_annual`: PLFS Annual Report July 2023-June 2024 PDF (Table 51 casual wages by NIC section; regular wages by sector/State; worker distribution by industry x status); eSankhyiki PLFS API indicator 4 (worker distribution, year 2023-24) and 6-8 (earnings). `mospi_esankhyiki_api`: Shared API client for PLFS / HCES / ASUSE / ASI / NSS-77 (AIDIS, SAS) indicator tables. `mospi_asuse`: ASUSE 2023-24 full report PDF and factsheet; eSankhyiki ASUSE API annual indicators 3/4 (ownership type), 30-35 (emoluments, GVA per worker/establishment) for year 2023-24 by R/U and activity. `mospi_asi`: ASI 2023-24 Volume I PDF and Summary Results PDF; ASI API (year 2023-24, NIC 2008) for emoluments/wages by industry (cross-check for V1a). `mospi_aidis_2019`: AIDIS 2019 report tables via eSankhyiki NSS-77 AIDIS module (survey_code=1): indicator 5 (assets and cash loans by MPCE quintile), 4 (by asset-holding class), 11 (by asset category), 12 (bullion/ornaments), 26-38 (loans by agency); press note PDF. `mospi_sas_2019`: SAS 2019 Report 587 PDF (income by source x land-size class); NSS-77 land & livestock API module as a machine-readable alternative.
- **Primary for refs:** C4a F1a F2 F3a F3b F3c R8a R9a S5 V1a; **also feeds:** C4b R10 R9b T3a V2a.
- **Expected datasets:** plfs_2324_worker_dist (industry x status x R/U, API ind 4); plfs_2324_earnings (regular by sector/State, casual by NIC section T51, self-employed); asuse_2324_ownership_activity (API 3/4, 30-35 + report tables); asi_2324_industry (API); aidis_2019_quintile_assets_debt (NSS-77 API ind 4, 5, 11, 12, 26-38); sas_2019_income_by_landclass.
- **Notes:** PDF table extraction for PLFS AR and ASUSE report; the APIs need legacy-TLS handling.

### union_fiscal

- **Scope:** Union government accounts and taxes. Effort L.
- **Sources:** `cga_finance_accounts_aag`, `mof_union_budget_2026_27`, `union_budget_transfers_to_states`, `ppac_petroleum_exchequer`, `nsi_small_savings_collections`, `pib_gst_monthly_releases (not in registry)`, `gstn_gst_statistics`, `gst_monthly_state_revenue`, `cbdt_time_series`, `dpe_public_enterprises_survey`, `pib_tax_devolution_releases`.
- **Files:** `cga_finance_accounts_aag`: Union Finance Accounts 2023-24: Statement 1 (summary), 8 (receipts by minor head: MH 0005, 0008, 0009, 0020, 0021, 0037, 0038), 9 (expenditure by minor head incl. MH 2049 interest, 2071 pensions) + 9-Appendix (grants-in-aid), 10, 11 (investments/dividends), 13, 14/14A (debt), 16 (NSSF). AAG 2023-24 not located; AAG 2024-25 App. 12 (object heads) as fallback. `mof_union_budget_2026_27`: 2023-24 ACTUALS come from the Budget 2025-26 archive: Receipt Budget tr.xls (tax by major head), ntr.xls (non-tax incl. dividends by enterprise), annex7.pdf (revenue impact of tax incentives), annex8.pdf (NSSF sources and application, Actual 2023-24), annex11.pdf; Expenditure Profile stat1/stat7 (subsidies)/stat18/stat20/stat21 XLSX; AFS allafs.xlsx; Budget at a Glance bag1/bag3/bag5 XLSX. Budget 2026-27 set only for 2024-25 actuals. `union_budget_transfers_to_states`: Expenditure Profile 2025-26 Statement 18 (transfers to States, Actual 2023-24) stat18.xlsx; Demand 42 SBE sbe42.pdf (GST compensation grants). `ppac_petroleum_exchequer`: 'Contribution of Petroleum Sector to Exchequer' XLS (sheet Anx 1), 2014-15 to 2025-26(P): 2023-24 Central excise 2,73,683.88; customs 13,133.73; State VAT/SGST rows. `nsi_small_savings_collections`: NSI Id_Pk=152 table (gross, withdrawals, net collections 2002-03 to 2025-26). For 2023-24 use together with Receipt Budget 2025-26 Annex 8 (NSSF by instrument) and Finance Accounts 2023-24 Statement 16. `pib_gst_monthly_releases (not in registry)`: Ministry of Finance monthly GST collection releases on PIB for Apr 2023-Mar 2024 (published 1st of the following month; PIB stopped them after May-2024 data). PRIDs still to be listed from PIB's release archive. `pib_tax_devolution_releases`: Not needed for 2023-24: devolution comes from Finance Accounts and FC16 KFI A.1.3.
- **Primary for refs:** K3a K8e P10a P9a R10 R18 R2 R2k R3 R3b R7 R9 R9b S7 T1 T1a T2b T3 T3a T4; **also feeds:** C2a F4 F4b I1a K6 K7a K7b K9b P7a P7b P8 P9 R1 R15 R16 R3a R6 R8a R9c S8 S9 T2.
- **Expected datasets:** union_fa_2324_receipts_minorhead (St 8); union_fa_2324_expenditure_minorhead (St 9 + appendix); union_fa_2324_debt (St 14/14A); union_nssf_2324 (FA St 16 + Receipt Budget Annex 8 + NSI table); union_budget_actuals_2324 (tr.xls, ntr.xls, stat7 subsidies, stat18 transfers, stat20/21, AFS); union_tax_incentive_annex7_2324; ppac_petroleum_exchequer; pib_gst_monthly_2324.
- **Notes:** Finance Accounts PDFs are the audited anchor that replaces CBDT and GSTN (D1-1c). Heavy PDF extraction.

### state_fiscal

- **Scope:** State and local government finances. Effort L.
- **Sources:** `fc16_relevant_data`, `rbi_state_finances_study`, `cag_state_finance_accounts`, `fc16_ulb_cityfinance_dump`, `rbi_municipal_finances`, `rbi_pri_finances`.
- **Files:** `fc16_relevant_data`: 'State Finances - Key Fiscal Indicators.xlsx' (KFI: A.1.1.2 SGST, A.1.3 devolution, A.1.4 grants, B.1.a interest, B.1.b pensions, stamps, vehicles), 'Time series of transfer of resources from Centre to States.xlsx', 'Sector wise Subsidies and Transfers.xlsx', 'State Finance Accounts - Revenue and Expenditure.xlsx'. `rbi_state_finances_study`: State Finances 2025-26 edition (2023-24 Accounts): Statements 13 (interest), 14 (tax revenue), 15 (non-tax), 17 (transfers), 36 (subsidies), Appendix Table 2, Appendices I-IV (State-wise detail, Rs lakh). Hashed rbidocs links are listed on the www.rbi.org.in listing page. `cag_state_finance_accounts`: Per-State Finance Accounts 2023-24 Vol I/II PDFs from the CAG state-accounts page (public). Machine-readable FA&AA Excel is on CAG SharePoint behind a Microsoft login (not used). `fc16_ulb_cityfinance_dump`: FC16 ULB Data Dump Cityfinance.xlsx (ULB revenue/expenditure to 2023-24). `rbi_municipal_finances`: Report on Municipal Finances (Nov 2024) Statements 1-8 (municipal corporations, to 2023-24 BE/RE). `rbi_pri_finances`: Finances of Panchayati Raj Institutions (Jan 2024), App. I/II (to 2022-23).
- **Primary for refs:** R1 R16 T2 T2x; **also feeds:** C2a F4b I1a K3a K6 K8e P10a P7a P9a R10 R18 R2 R2k R3 R3b R7 R9 R9b T2b.
- **Expected datasets:** rbi_sf_2526_statements (St 1-37, 2023-24 Accounts column; units normalised from each sheet's unit line); rbi_sf_appendices_I_IV (Rs lakh -> crore); fc16_kfi; fc16_transfers_timeseries; fc16_sector_subsidies; fc16_state_accounts; ulb_cityfinance; rbi_municipal_statements; rbi_pri_appendix.
- **Notes:** rbidocs XLSX (intermittent challenge) - schedule this unit's rbidocs pulls away from the other RBI units (separate day or slot).

### rbi_financial_accounts

- **Scope:** Flow of funds, household financial saving, public-debt ownership. Effort L.
- **Sources:** `rbi_fsf_fof`, `rbi_hh_fin_savings`, `rbi_hbs`, `dea_public_debt_reports`.
- **Files:** `rbi_fsf_fof`: FSF2023-24_21012026.xlsx (71 sheets: St 1-5 sub-sector balance sheets, 6.1-6.13 FWTW, 7.1-7.13 instrument x sector, 8.1-8.3); Bulletin article (Jan 2026) HTML. `rbi_hh_fin_savings`: Bulletin Sept 2026 Current Statistics tables 52(a) flows and 52(b) stocks (2022-23 to 2025-26). `rbi_hbs`: HBS 2025-26 T11 (sector saving), T12 (HH financial assets/liabilities), T107 (ownership of Central and State securities), T108/T109 (small savings), T36-T49 (RBI, SCB aggregates). Table index with hashed XLSX and HTML links built from the listing page. `dea_public_debt_reports`: Quarterly Report on Public Debt Management Jan-Mar 2023 and Jan-Mar 2024 (ownership of G-secs/T-bills, Tables 4.x); Status Paper on Government Debt 2023-24.
- **Primary for refs:** K7 K8 K8d R3a R4 R5 R8 S4; **also feeds:** K1 K4 K7a K7b K8a K8b K9 K9b R12a R8a S5.
- **Expected datasets:** fsf_2324_balance_sheets (St 1-5); fsf_2324_fwtw (6.x); fsf_2324_instrument_sector (7.x); fsf_2324_financing (8.1-8.3); rbi_hh_finsav_52a_52b; hbs_t11_t12_t107_t108_t109; dea_qr_ownership_mar2023_mar2024; dea_status_paper_2324.
- **Notes:** FSF 71-sheet workbook; 52(a)/(b) is PDF-only on rbidocs.

### rbi_banking_corporate

- **Scope:** RBI, banks, NBFCs and corporate finance. Effort M.
- **Sources:** `rbi_annual_report`, `rbi_strbi`, `rbi_trend_progress`, `rbi_bsr`, `rbi_corporate_finances`, `aifi_psu_financial_annual_reports (not in registry)`.
- **Files:** `rbi_annual_report`: RBI Annual Report 2025-26 Ch XII accounts (5-year surplus row: 87,416.22 paid in 2023-24) and appendix XLSX; for RBI's 2023-24 income/expenditure the AR 2024-25 accounts chapter (prior-year column) - locate via the year selector on the AR listing. `rbi_trend_progress`: RTP 2024-25 appendix tables (HTML PublicationsView ids 23642-23681; 2023-24 shown as prior year). RTP 2023-24 edition for full 2023-24 detail via the listing year selector. `rbi_bsr`: Annual BSR-1 March 2024 press release (credit by borrower category/occupation) prid=58036; quarterly June 2023-Dec 2023 releases; detailed tables on DBIE (manual). `rbi_corporate_finances`: 'Performance of Private Corporate Business Sector during 2023-24' press release prid=58186 (sales, staff cost, interest, tax, dividends of listed NGNF companies). `aifi_psu_financial_annual_reports (not in registry)`: Annual reports 2023-24 of NABARD, SIDBI, EXIM, NHB, PFC, REC, IRFC, LIC (public-sector FC split, F4a/K2a) and HDFC Bank (merger adjustment, K8a).
- **Primary for refs:** F4a K2a K9b R6 R9c; **also feeds:** C4b K8 K8a R13 R4 R5 R8 T4a.
- **Expected datasets:** rbi_ar_accounts (surplus 5-year row; 2023-24 income/expenditure); rtp_appendix_2425 (IV, V, VI tables incl. 2023-24 column); bsr1_mar2024_summary; pcbs_2324; fin_psu_annual_reports_2324 (after registration).
- **Notes:** STRBI is manual-only (DBIE); RTP HTML is the substitute.

### external_sector

- **Scope:** Balance of payments, external debt, remittances. Effort M.
- **Sources:** `rbi_hbs_external`, `rbi_bop_quarterly`, `rbi_external_debt`, `rbi_nri_deposits`, `rbi_ecb_monthly`, `rbi_fla_census`, `rbi_remittances_survey`, `rbi_ites_survey`, `rbi_lrs_outward_remittances`, `rbi_intl_investment_position`.
- **Files:** `rbi_hbs_external`: HBS 2025-26 T126/T127 (BPM6 BoP US$/Rs), T124/T125, T139-T142 (NRI deposits), T145/T146 (external debt end-March), T149/T150 (IIP BPM6), T197/T198 (quarterly BoP), T199-T204 (quarterly IIP). `rbi_bop_quarterly`: Quarterly BoP 2023-24 (HBS T198 rupees) and reserve-asset flows (K8c); press releases for vintage flags. `rbi_external_debt`: End-March 2024 external debt by borrower/instrument: HBS T145/T146; quarterly release June 2024 for detail. `rbi_nri_deposits`: HBS T139-T142 (outstanding and flows by scheme, 2023-24). `rbi_ecb_monthly`: ECB/FCCB monthly registrations Apr 2023-Mar 2024 = ECBUserView.aspx?Id=235 ... Id=246. `rbi_fla_census`: FLA census 2024-25 round (positions end-March 2024 and 2025, by activity, NFC vs FC) PublicationsView id=23438. `rbi_remittances_survey`: 6th round (2023-24) Bulletin article, Tables 1-2 (source-country and State shares) - HTML article page. `rbi_ites_survey`: Survey on Computer Software & ITES exports for 2023-24 (destination shares) - press release to be pinned from the RBI release archive; 2025-26 round prid=63625 as template. `rbi_lrs_outward_remittances`: Bulletin Current Statistics table 36 (LRS by purpose), FY 2023-24 (April 2024 or later issue). `rbi_intl_investment_position`: HBS T149/T150 end-March 2024 (stock context for K8b).
- **Primary for refs:** K8b K8c R11a R13 R14 R15 S3; **also feeds:** K5 K7b K8 P5 P6 R11 R12 R12a R14a R8 S2 V3 V4.
- **Expected datasets:** hbs_bop_bpm6_annual (T124-T127); hbs_bop_quarterly (T197/T198); hbs_nri_deposits (T139-T142); hbs_external_debt (T145/T146); hbs_iip (T149/T150, T199-T204); ecb_monthly_2324 (Id 235-246); fla_census; remittance_survey_r6_tables; ites_survey_2324; lrs_table36_2324.
- **Notes:** Mostly www.rbi.org.in HTML (never challenged); HTML views carry only the latest two years, so 2023-24 comes from the XLSX or the HBS 2024-25 HTML.

### finsector_markets

- **Scope:** Insurance, pensions and securities markets. Effort M.
- **Sources:** `irdai_handbook_insurance`, `epfo_annual_report_accounts`, `pfrda_nps_statistics`, `sebi_handbook_statistics`, `nsdl_fpi_monitor`, `amfi_monthly_quarterly`.
- **Files:** `irdai_handbook_insurance`: Handbook on Indian Insurance Statistics 2024-25 zip (T2/T3 life premium, T20/T21 AUM, T24-T26 life accounts, T40-T47 non-life premium/claims; 2023-24 in the time series). `epfo_annual_report_accounts`: EPFO Annual Report 2023-24 ('71.pdf', 27 MB): contributions, settlements, interest credited, investments. `pfrda_nps_statistics`: A2 sector-wise AUM (annual, to Mar 2025), M2/M6 monthly AUM; Handbook of NPS Statistics 2024-25 PDF (contributions 2023-24). `sebi_handbook_statistics`: SEBI Handbook 2025-26 per-table XLSX: T11 corporate bonds, T14 funds mobilised, T56/T58-T63 FPI flows and custodian AUC, T64-T72 MF (2023-24 in the series).
- **Primary for refs:** R17 S9; **also feeds:** F4a K2a K8b R8 R9c T4a.
- **Expected datasets:** irdai_handbook_2425 (life/non-life premium, claims, AUM, policyholder accounts); epfo_ar_2324; pfrda_aum_contributions; sebi_hbs_2526 (T11, T14, T56, T58-T63, T64-T72).
- **Notes:** NSDL and AMFI are excluded on terms; SEBI tables cover their gap-map use.

### trade_satellites

- **Scope:** Trade by partner and services by partner (satellites S1, S2). Effort M.
- **Sources:** `commerce_tradestat`, `imf_sdmx`, `un_comtrade`, `oecd_wto_batis`.
- **Files:** `commerce_tradestat`: EIDB annual 2023-24 commodity x country export/import tables (HS 2-digit x partner). `imf_sdmx`: IMTS India goods by partner, monthly (for FY 2023-24 partner shares) and annual; BOP for cross-checks. `un_comtrade`: Keyless preview API (<=500 records per call): India HS 2-digit x partner, monthly 2023-04..2024-03. `oecd_wto_batis`: BaTIS India services by partner x EBOPS, CY2023 and CY2024 (all-wildcard key).
- **Primary for refs:** S1 S2; **also feeds:** -.
- **Expected datasets:** tradestat_eidb_2324_hs2_partner; imf_imts_india_monthly; comtrade_preview_hs2_partner_2324; batis_india_2023_2024.
- **Notes:** Rate-limited APIs (Comtrade 429, BaTIS 500 on first call): build retries with backoff.

## 7. Registry changes made with this plan

- `mospi_asuse_unit_data`: unverified -> **verified** (catalog pages 293/238 and the GSDD 2026 Category B text re-read by an agent that did not add the entry). Formats stay unconfirmed (files not requested, D1-2).
- `nsi_small_savings_collections`: unverified -> **verified** (table re-read; Copyright Policy read via its postback target Id_Pk=43; 2023-24 net 4,21,678.35 matches Receipt Budget 2025-26 Annex 8). Publication date still unknown.
- `ppac_petroleum_exchequer`: unverified -> **verified** (XLS 'Table Posted: (17.07.2026)', 2014-15 to 2025-26; Terms & Conditions read). Alias `ppac_exchequer`.
- `dpe_public_enterprises_survey`: stays **unverified** (content comes from a keyed CMS; not usable under D1-1). Not needed by any cell.
- `cbdt_time_series`: stays unverified; intermittent 403/200 recorded; not automated (D1-1c). `gstn_gst_statistics`: stays disputed; moot for the SAM (T_GCES from MH 0009).
- `mospi_aidis_2019`: report tables found in the eSankhyiki NSS-77 AIDIS API (22 indicators incl. quintile of MPCE); Report 588 PDF not located.
- `dea_public_debt_reports`: Jan-Mar 2023 and Jan-Mar 2024 quarterly reports added; alias `dea_public_debt_quarterly`. `imf_sdmx`: alias `imf_sdmx_portal`.
- `epfo_annual_report_accounts`: AR 2023-24 file added. `oecd_icio_2025`: Cloudflare challenge on the zip recorded. All rbidocs-hosted entries: intermittent-challenge note added.
- `mospi_asi`, `rbi_external_debt`, `rbi_intl_investment_position`, `rbi_invisibles_quarterly`: release status recorded (section 2).

## 8. Open items for the orchestrator

- Register: PIB monthly GST releases (and pin the 12 PRIDs for Apr 2023-Mar 2024 data); CBIC GST rate notifications (P7a prior); public financial institutions' annual reports (F4a/K2a).
- Fix the three gap-map ids (or keep the registry aliases and make the pipeline resolve them).
- Locate: AIDIS Report 588 PDF (optional now that the API has the tables); AAG 2023-24 (CGA); RBI Annual Report 2024-25 accounts chapter; RBI ITES survey 2023-24 release; FLA census round showing end-March 2024; PLFS AR 2022-23 PDF.
- Re-try later (not today): rbidocs files, OECD ICIO zip. Re-check on 30 Sep: ASI 2024-25 and the RBI end-June releases.
- Owner, pre-launch: RBI permission (deep links, caching), MoF/DEA/SEBI/NSI/DGCI&S permissions to republish; decide on GSDD 'non-commercial' before any unit-data use.
