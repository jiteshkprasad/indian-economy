# SOURCES — India Economy Model

Phase 0 reconnaissance of the data sources for India's Social Accounting Matrix (SAM), the SAM multiplier model and the agent-based model.

- **Retrieval date for everything in this file:** 2026-09-29. Nothing here was taken from memory. Every fact came from a page or file fetched on the web during Phase 0.
- **How it was built:** one finder agent per source family, then an independent verifier agent per family that tried to break the finder's claims. The lead agent resolved the disagreements. Where the verifier corrected or refuted a claim, the lead re-checked the key points live (HTTP status, file contents, licence text) and used whatever could be evidenced. Points still unresolved are marked **disputed**, with both values kept.
- **Machine-readable companion:** `data/registry.yaml` (schema_version 1). It holds every field below, plus the finder's and verifier's evidence for each source.
- **Status meanings:** `verified` means the verifier confirmed the finder. `corrected` means the finder was wrong on at least one point and the corrected value is recorded. `disputed` means the evidence conflicts and both values are kept. `unverified` means the claim could not be confirmed (the reason is given).
- **Status rule (applied in the fix pass, 2026-09-29):** an entry counts as `verified` or `corrected` only if three things were confirmed: the source exists, its latest release was identified, and a licence or terms text was read. If no licence text was read, or the latest release was not identified, the entry is `unverified`. Smaller gaps (release date, lag, attribution clause, coverage end) are listed per entry under "Not confirmed" (`verification.unconfirmed_fields` in the registry). Entries added in the fix pass stay `unverified` until an independent verifier checks them.
- **Fix pass:** an independent checker reviewed both files after Phase 0. Its findings were fixed and re-checked live on 2026-09-29. The main changes: RBI State Finances units; 10 status downgrades; correct ASUSE and GST dates; a sourced CAG date; MoSPI licence terms URL; the rbidocs HTTP-200 trap; the IOTT landing; the rebasing percentage; and three new entries (ASUSE unit data, NSSF/small savings, DPE Public Enterprises Survey). Each changed entry records the evidence in `verification.verifier_evidence`, prefixed "Fix pass 2026-09-29".
- **Access values:** `none`, `registration`, `login`, `api_key`, `paid`, and `manual_download`. `manual_download` means the site blocks automated clients, so the owner has to download the files in a browser.
- **Release dates:** `latest_release.date` is the publication date, or the explicit sentinel `unknown` or `n/a`. It is never a server Last-Modified time.
- **Failed families:** none. All 10 families produced reconnaissance and verification.
- **Units:** ₹ crore unless stated. Indian digit grouping is used (₹2,61,77,001 crore = ₹261.77 lakh crore).

## 1. Summary table of all sources

162 sources in 10 families. Verification status: verified 94, corrected 51, disputed 2, unverified 15. 'Access' is what the owner must arrange (none = open). Full details are in `data/registry.yaml`.

| Family | Source (id) | Access | Licence (short) | Latest release | Lag | Status |
|---|---|---|---|---|---|---|
| mospi_nas | National Accounts Statistics 2026 (new base 2022-23), per-statement XLSX (`mospi_nas_2026_publication`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2026-08-31: NAS 2026: 60 statements (FE 2022-23 and 2023-24, FRE 2024-25) + 4 statements (PE 2025-26 and quar… | About 17 months after end of the latest FRE year… | corrected |
| mospi_nas | MoSPI NAS REST API (eSankhyiki backend) (`mospi_nas_api`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2026-08-31: Includes Q1 2026-27 (GDP current 88,26,871 cr) and annual 2022-23 to 2025-26, identical to NAS 20… | Same day as press releases | corrected |
| mospi_nas | eSankhyiki portal - Macro Indicators (NAS) (`mospi_esankhyiki_portal`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2026-08-31: Cited by Q1 2026-27 press note as location of detailed GDP data | Same as press releases | verified |
| mospi_nas | GDP press notes: Advance, Provisional and Quarterly estimates (new series) (`mospi_gdp_press_releases`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2026-08-31: Q1 2026-27 GDP estimates. Next: Q2 on 2026-11-30; FAE 2026-27 on 2027-01-07; SAE + Q3 + FRE 2025-… | ~2 months after quarter end. PE rule: 7 June or p… | corrected |
| mospi_nas | NAS 2024 and NAS 2025 (old base 2011-12) incl. sequences of accounts; old-base long series (`mospi_nas_old_base_2011_12`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2025-06-26: NAS 2025 (2011-12 to 2023-24) published 2025-06-26; NAS 2024 (last edition with full sequences of… | n/a (superseded) | verified |
| mospi_nas | Sources and Methods for Compilation of National Accounts Statistics (base 2022-23) (`mospi_nas_sources_methods_2026`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2026-09-21: Released (3.8 MB PDF) | ~7 months after new series | verified |
| mospi_nas | MoSPI Advance Release Calendar 2026-27 and PE release-date notice (`mospi_advance_release_calendar`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2026-09-01: ARC 2026-27 updated till August 2026 (created 2026-09-01); calendar-change note 12 May 2026 | n/a | verified |
| mospi_nas | State GSDP/GSVA (MoSPI API account_code=2; new-base compilation in progress) (`mospi_state_gsdp`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | n/a: API holds base 2011-12 only. New-base GSDP 2022-23 to 2024-25 under NAD-DES joint discussion (20 May - 1… | unknown for new base | verified |
| mospi_nas | Reports of Sub-Committees for the 2022-23 series (new data sources, rates and ratios; methodological improvements) (`mospi_nas_subcommittee_reports`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2026-02-24: SC-I report pub 2795 (24 Feb 2026); methodological sub-committee report (18 Feb 2026) | n/a | verified |
| mospi_nas | OGD Platform India (data.gov.in) mirrors: MoSPI National Accounts, 'Economic Classification of the Central Budget', Commerce trade-by-partner, RBI 'Overall BoP' (`data_gov_in_ogd`) | api_key | GODL-India per site footer ('licensed under the Government Open Data… | unknown: unverified: catalog pages timed out or returned 403 | unverified | unverified |
| mospi_io | Supply and Use Tables 2022-23 and 2023-24 (base 2022-23) (`mospi_sut_2022base`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2026-08-31: SUT 2022-23 and 2023-24 first released 2026-05-15; revised files (suffix _(1)) uploaded 2026-08-3… | ~26 months after FY 2023-24 (old series lag ~4 ye… | corrected |
| mospi_io | Supply and Use Tables 2011-12 to 2021-22 (old base 2011-12) (`mospi_sut_2011base`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2025-12-11: SUT 2020-21 and 2021-22 uploaded 2025-12-11 (note 2025-11-26) | ~3.7 years | verified |
| mospi_io | Input-Output Transactions Table 2007-08 (last official IOTT) (`mospi_iott_2007`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2012: IOTT 2007-08, published 2012 | n/a | corrected |
| mospi_io | Input Output Transactions Table: India 2015-16 (derived from SUT) (`csep_iott_2015`) | none | no explicit licence found | 2020-01: Draft for comments, January 2020 | n/a | verified |
| mospi_io | Annual Survey of Industries (ASI) (`mospi_asi`) | registration | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2025-09-30: ASI 2023-24 (results 2025-08-27; publications and unit data 2025-09-30). ASI 2024-25 results sche… | ~17-18 months | corrected |
| mospi_io | Index of Industrial Production (base 2022-23) (`mospi_iip_2022base`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2026-09-28: August 2026 Quick Estimate: index 123.3, growth 8.0% | ~28 days | corrected |
| mospi_io | Consumer Price Index (Rural/Urban/Combined), base 2024=100 (`mospi_cpi_2024base`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2026-09-14: August 2026: Combined 108.74, inflation 4.82% | ~12-14 days | verified |
| mospi_io | WPI and Producer Price Indices (Output PPI, trial Input PPI, Service PPIs), base 2022-23 (`oea_wpi_ppi_2022base`) | none | no explicit licence found | 2026-09-14: August 2026 provisional: WPI 110.8, inflation 9.92%; SPPI Q1 2026-27 | ~14 days provisional; final after 2 months | verified |
| mospi_io | Energy Statistics India 2026 (energy balance, physical energy SUT) (`mospi_energy_statistics`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2026-03-30: Energy Statistics India 2026 (33rd edition), covers FY 2024-25 (TPES 9,32,816 KToE) | ~12 months | corrected |
| mospi_io | eSankhyiki open API (api.mospi.gov.in) and MCP server (`mospi_esankhyiki_api`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2026-09-28: Served Aug-2026 IIP/CPI/WPI on 2026-09-29; repos pushed 2026-09-28 | Same day as releases (Energy lags) | corrected |
| mospi_io | Index of Services Production (trial, base 2024-25) (`mospi_isp_2024base`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2026-08-31: First release of sub-sectoral trial ISP 2026-07-14; June 2026 data released 2026-08-31 | ~2 months | verified |
| mospi_io | NIC 2025 (with NIC 2008 concordance) and NPC-MS 2011 (Revised) (`mospi_classifications`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2025-11-18: NIC 2025 released 2025-11-18 | n/a | corrected |
| mospi_io | Index of Eight Core Industries (base 2022-23; now 9 industries incl. iron ore) (`oea_ici_2022base`) | none | no explicit licence found | 2026-09-21: August 2026 provisional (4.8% YoY) | ~20 days | corrected |
| mospi_households | Household Consumption Expenditure Survey 2023-24 (NSS Report 592): report, factsheet, Excel detailed tables (`mospi_hces_2023_24`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2025-01-30: Detailed report + Excel tables + unit data released 30 Jan 2025 (factsheet 27 Dec 2024); survey A… | ~6 months after fieldwork end | verified |
| mospi_households | Household Consumption Expenditure Survey 2022-23 (NSS Report 591) (`mospi_hces_2022_23`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2024-06: Factsheet Feb 2024; report + unit data June 2024 | ~11 months | verified |
| mospi_households | HCES 2022-23 and 2023-24 unit-level data (microdata.gov.in NADA) (`mospi_hces_unit_data`) | registration | GSDD 2026 Category B (registered access): free for non-commercial use… | 2025-01-30: HCES 2023-24 unit data (catalog 237, DDI-IND-MOSPI-NSS-HCES23-24; created 22 Apr 2025, last modif… | ~6 months | corrected |
| mospi_households | Periodic Labour Force Survey - Annual Reports (July-June to 2023-24; calendar year from 2025) (`mospi_plfs_annual`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2026-03-27: PLFS Annual Report 2025 (Jan-Dec 2025), press note dated 27 Mar 2026; next CY 2026 report 25 Mar… | ~3 months | verified |
| mospi_households | PLFS Monthly and Quarterly Bulletins (`mospi_plfs_bulletins`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2026-09-15: Monthly bulletin August 2026 (LFPR 55.6%), posted 15 Sep 2026; quarterly Apr-Jun 2026 available | ~2-6 weeks | corrected |
| mospi_households | PLFS unit-level data (`mospi_plfs_unit_data`) | registration | GSDD 2026 Category B (registered access): free for non-commercial use… | 2026-03-27: CY 2025 (catalog 284, created 27 Mar 2026); monthly Apr-Dec 2025 (291) and quarterly (292) create… | ~3 months | verified |
| mospi_households | Annual Survey of Unincorporated Sector Enterprises (ASUSE) (`mospi_asuse`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2026-09-10: District-level press note 'insights from ASUSE 2025' on 10 Sep 2026 (latest ASUSE item in the MoS… | ~3 months (factsheet) | corrected |
| mospi_households | ASUSE unit-level data (microdata.gov.in NADA): 2025 (catalog 293) and 2023-24 (catalog 238) (`mospi_asuse_unit_data`) | registration | GSDD 2026 Category B (registered access): free for non-commercial use… | 2026-05-06: ASUSE 2025 (Jan-Dec 2025) unit data, catalog 293 'DDI-IND-NSO-ASUSE-Jan2025-Dec2025', created 6 M… | ~4 months after survey end | verified |
| mospi_households | All India Debt & Investment Survey, NSS 77th round 2019 (Report 588) (`mospi_aidis_2019`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2021-09-10: Report 588, press note 10 Sep 2021; stocks as on 30.06.2018 | ~21 months | verified |
| mospi_households | Situation Assessment Survey of Agricultural Households, NSS 77th round (Report 587) (`mospi_sas_2019`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2021-09-10: Report 587, 10 Sep 2021 | ~21 months | verified |
| mospi_households | National Household Income Survey (NHIS) 2026 - first official income survey (not yet available) (`mospi_nhis_2026`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | n/a: No data. Fieldwork from April 2026 (PIB 17 Mar 2026 prints 'April 2026 to March 2026', a typo) | unknown (mid-2027 per secondary sources, unverifi… | verified |
| mospi_households | Time Use Survey 2024 (`mospi_tus_2024`) | registration | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2025-04-15: 'Time Use in India, 2024' reportedly released March 2025; unit data catalog 236 created 15 Apr 20… | ~3 months | unverified |
| mospi_households | NSS Survey on Household Social Consumption: Health (Jan-Dec 2025) - unit data (`nss_health_2025`) | registration | GSDD 2026 Category B (registered access): free for non-commercial use… | 2026-04-17: Catalog 290 created 2026-04-17 | ~4 months | verified |
| mospi_households | NSS Comprehensive Modular Survey: Education, 80th round (Apr-Jun 2025) (`nss_cms_education_2025`) | registration | GSDD 2026 Category B (registered access): free for non-commercial use… | 2025-08-26: CMS Education, NSS 80th round (2025): unit data catalog 255 'DDI-IND-MOSPI-NSS-CMSE80-2025', crea… | unknown | verified |
| mospi_households | NSS Domestic Tourism Expenditure Survey, 80th round (Jul 2025-Jun 2026) (`nss_domestic_tourism_2025_26`) | registration | GSDD 2026 Category B (registered access): free for non-commercial use… | 2026-09-23: Unit data catalog 307 created 2026-09-23; press note listed in MoSPI latest-release feed | ~3 months | verified |
| mospi_households | CMIE Consumer Pyramids Household Survey (Consumer Pyramids dx) (`cmie_cphs`) | paid | Proprietary subscription; terms not read; redistribution of record-le… | unknown: unverified (subscription portal) | ~1 month (income) | unverified |
| mospi_households | PRICE ICE 360 Survey 2021 (Wave 3) (`price_ice360`) | registration | No open licence; 'Reproduction is prohibited other than in accordance… | 2025-04-08: Data page created 2024-02-05, last modified 2025-04-08 | ~3 years | verified |
| mospi_households | India Human Development Survey (IHDS-I 2004-05, IHDS-II 2011-12; IHDS-3 unreleased) (`ihds`) | registration | ICPSR terms of use (unverified: ICPSR page returned 403) | unknown: IHDS-II (2011-12) public; IHDS-3 not released | n/a | unverified |
| mospi_households | World Inequality Database - India income and wealth distribution (`wid_india`) | none | Creative Commons BY-NC-SA 4.0 (active licence link on India page); a… | 2026-09-09: Bulk file updated 2026-09-09; latest India data year unverified | unverified | corrected |
| mospi_households | MoSPI Revised Guidelines for Statistical Data Dissemination (GSDD) 2026 (`mospi_gsdd_2026`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2026-04-27: Notification dated 27 Apr 2026 (Gazette No. 122, 6 May 2026; digitally signed 7 May 2026), supers… | n/a | verified |
| rbi_core | Database on Indian Economy (DBIE) (`rbi_dbie`) | none | Archived DBIE disclaimer (2023): 'Reproduction is permitted provided… | n/a: Live portal; routes STRBI 2024-25 and annual BSR March 2026 | Same as underlying releases | corrected |
| rbi_core | Handbook of Statistics on the Indian Economy 2025-26 (`rbi_hbs`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-07-31: 28th edition 2025-26, 245 tables | ~4 months after FY end | verified |
| rbi_core | Financial Stocks and Flow of Funds (FSF) of the Indian Economy 2023-24 (`rbi_fsf_fof`) | none | RBI Bulletin imprint: '(c) Reserve Bank of India 2026. All rights res… | 2026-01-21: FSF 2023-24, RBI Bulletin January 2026; no 2024-25 edition as of 2026-09-29 | ~22 months | corrected |
| rbi_core | Household Financial Savings - RBI preliminary estimates (Bulletin Current Statistics 52(a)/(b)) (`rbi_hh_fin_savings`) | none | RBI Bulletin imprint: '(c) Reserve Bank of India 2026. All rights res… | 2026-09-25: Bulletin Sept 2026: preliminary 2025-26 (NFA Rs 21,68,779.7 cr = 6.3% of GDP), revised 2022-23 to… | ~6 months after FY end | verified |
| rbi_core | Sectoral Deployment of Bank Credit (monthly) (`rbi_sectoral_credit_bank`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-08-31: July 2026 data | ~1 month | verified |
| rbi_core | Basic Statistical Returns BSR-1 (credit) and BSR-2 (deposits) (`rbi_bsr`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-08-31: Quarterly June 2026 (2026-08-31); annual March 2026 (2026-05-29) | ~2 months | verified |
| rbi_core | Statistical Tables Relating to Banks in India (STRBI) (`rbi_strbi`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2025-12-29: STRBI 2024-25 | ~9 months | verified |
| rbi_core | Report on Trend and Progress of Banking in India 2024-25 (`rbi_trend_progress`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2025-12-29: 2024-25 edition | ~9 months | corrected |
| rbi_core | Sectoral Deployment of Credit by NBFCs (monthly; new series 2026) (`rbi_nbfc_sectoral_credit`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-09-07: July 2026 data (3rd release; first was May 2026 data on 2026-07-07) | ~5 weeks | corrected |
| rbi_core | Financial Stability Report (`rbi_fsr`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-06-30: June 2026 | ~3 months | corrected |
| rbi_core | RBI Annual Report 2025-26 (incl. RBI accounts, appendix tables) (`rbi_annual_report`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-05-29: Annual Report 2025-26 | ~2 months | verified |
| rbi_core | Weekly Statistical Supplement and Money Supply releases (`rbi_wss_money`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-09-25: WSS 25 Sep 2026; money supply fortnight ended 15 Sep 2026 | ~1-2 weeks | verified |
| rbi_core | RBI Bulletin - Current Statistics and articles (`rbi_bulletin_current_stats`) | none | RBI Bulletin imprint: '(c) Reserve Bank of India 2026. All rights res… | 2026-09-25: September 2026 issue | Varies by table | corrected |
| rbi_core | Performance of Private Corporate Business Sector; Finances of Non-Govt Non-Financial Public Ltd Companies (`rbi_corporate_finances`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-06-24: PCBS 2025-26 (2026-06-24); public ltd companies 2024-25 (2026-03-30) | ~3 months (listed); ~12 months (public ltd) | verified |
| rbi_core | Report on Currency and Finance (`rbi_rcf`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2024-07-29: 2023-24 (digital revolution theme) | n/a | verified |
| rbi_core | Scheduled Banks' Statement of Position in India (fortnightly Form-A) (`rbi_form_a_scheduled_banks`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | unknown: unverified | unverified | unverified |
| external | Developments in India's Balance of Payments (quarterly, BPM6) + Sources of Variation in Forex Reserves (`rbi_bop_quarterly`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-09-01: Q1 2026-27 (Apr-Jun 2026): CAD US$4.2 bn (0.5% GDP). FY 2025-26 (P) released 2026-06-08: CA -25.2… | ~2 months | verified |
| external | Developments in India's Balance of Payments for the Month (new monthly BoP) (`rbi_bop_monthly`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-09-15: July 2026 (CA -7.0 bn; NRI deposits +33.5 bn) | ~45 days | verified |
| external | RBI HBS 2025-26 external-sector tables (BPM6 BoP in US$ and Rs, invisibles, NRI deposits, FDI, reserves, debt, IIP, trade) (`rbi_hbs_external`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-07-31: HBS 2025-26, data to FY 2025-26 | ~4 months | verified |
| external | Data on India's Invisibles (BPM6, quarterly) (`rbi_invisibles_quarterly`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-06-30: Q4 2025-26 (Jan-Mar 2026); Q1 2026-27 likely 2026-09-30 (last year's Q1 came 2025-09-30). invisib… | ~3 months | verified |
| external | India's International Investment Position (IIP) (`rbi_intl_investment_position`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-06-30: End-March 2026: net claims of non-residents US$209.9 bn (-5.9% GDP); end-June 2026 likely 2026-09… | ~3 months | verified |
| external | India's External Debt (quarterly) (`rbi_external_debt`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-06-29: End-March 2026: US$762.8 bn, 20.8% of GDP; end-June 2026 likely 2026-09-30. India's external debt… | ~3 months | verified |
| external | Monthly Data on India's International Trade in Services (`rbi_services_monthly`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-08-31: July 2026: receipts 38,253, payments 20,606 US$ mn (provisional) | ~1 month | verified |
| external | India's Remittances Survey - 6th round (2023-24) (`rbi_remittances_survey`) | none | RBI Bulletin imprint: '(c) Reserve Bank of India 2026. All rights res… | 2025-03-19: 6th round, Bulletin March 2025; no 7th round found (not re-checked) | ~1 year | verified |
| external | RBI WSS - Foreign Exchange Reserves (`rbi_wss_forex_reserves`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-09-25: As on 18 Sep 2026: total US$765,901 mn (Rs 73,42,985 cr); FCA 630,980; gold 111,292; SDR 18,739;… | 1 week | verified |
| external | NRI deposits (by scheme) and 2026 FCNR(B)/ECB/OFCB swap-facility data (`rbi_nri_deposits`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-09-21: HBS 2025-26 to end-March 2026; swap-facility update 21 Sep 2026 (FCNR(B) 1,32,980; OFCB 5,320; EC… | ~1-2 months | corrected |
| external | External Commercial Borrowings / FCCB / RDB monthly data (`rbi_ecb_monthly`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-09-07: July 2026 data | ~5-6 weeks | verified |
| external | DPIIT Quarterly Fact Sheet on FDI Inflow (`dpiit_fdi_factsheet`) | none | unverified (copyright page is a JS shell) | 2026-06: March 2026 factsheet: 2025-26 FDI EQUITY inflow US$58,846 mn (excl. NRI schemes); total FDI Q4 2025-… | ~3 months | unverified |
| external | Census on Foreign Liabilities and Assets (FLA) of Indian Direct Investment Entities (`rbi_fla_census`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2025-10-29: 2024-25 round (provisional); 2025-26 round compiled internally but unpublished | ~7 months | verified |
| external | Overseas Direct Investment (monthly) (`rbi_odi_monthly`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-09-18: August 2026 (released 2026-09-18; URL not identified). OFDI18082026.xlsx / prid=63396 are JULY 20… | ~3 weeks | corrected |
| external | Survey on Computer Software and ITES Exports 2025-26 (`rbi_ites_survey`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-09-18: 2025-26: software services exports US$221.4 bn; US 54.1%, Europe 31.8% | ~6 months | verified |
| external | Survey of Foreign Liabilities and Assets of Mutual Funds 2025-26 (`rbi_mf_fla_survey`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-08-31: 2025-26: foreign liabilities US$31.5 bn; overseas assets US$10.2 bn | ~5 months | verified |
| external | Finances of Foreign Direct Investment Companies, 2024-25 (`rbi_fdi_company_finances`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-04-22: 2024-25 edition | ~13 months | verified |
| external | Survey on Foreign Collaboration in Indian Industry 2023-2025 (`rbi_foreign_collaboration_survey`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2025-12-02: Data release 2025-12-02 | n/a | verified |
| external | Survey on International Trade in Banking Services 2024-25 (`rbi_banking_services_trade_survey`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2025-09-26: 2024-25 edition | ~6 months | verified |
| external | Outward Remittances under the Liberalised Remittance Scheme (Bulletin table 36) (`rbi_lrs_outward_remittances`) | none | RBI Bulletin imprint: '(c) Reserve Bank of India 2026. All rights res… | 2026-09-25: September 2026 Bulletin | ~2 months | verified |
| external | Department of Commerce Export Import Data Bank - TradeStat (EIDB annual, MEIDB monthly) (`commerce_tradestat`) | none | No licence on TradeStat (disclaimer: 'do not have any legal sanctity… | 2026-09-16: EIDB to 2025-26 (updated 07/08/2026); MEIDB Jan 2018-Jul 2026 (updated 16/09/2026) | ~1.5 months | verified |
| external | DGCI&S Foreign Trade Statistics and Data Dissemination Portal (`dgcis_trade`) | paid | Copyright reserved by DGCI&S; 'internal use only'; re-dissemination (… | unknown: Finalised export/import data to June 2026; Laspeyres indices Apr-Jun 2026 (base 2022-23) | ~2-3 months | verified |
| external | World Bank WDI personal remittances (and discontinued KNOMAD bilateral matrix) (`worldbank_remittances`) | none | CC BY 4.0 (World Bank default; individual datasets may differ) | 2026-07-13: 2025 value US$150.7 bn (WDI lastupdated 2026-07-13) | ~6 months | verified |
| union_fiscal | Union Budget 2026-27 document set (Budget at a Glance, Receipt Budget, Expenditure Budget/Profile, AFS, FRBM statements) (`mof_union_budget_2026_27`) | none | indiabudget.gov.in copyright policy: may not be reproduced without Mi… | 2026-02-01: Budget 2026-27: Actuals 2024-25, BE 2025-26, RE 2025-26, BE 2026-27 | Actuals ~10 months after FY end | corrected |
| union_fiscal | Report of the Sixteenth Finance Commission (2026-27 to 2030-31) and Explanatory Memorandum (`mof_16th_finance_commission`) | none | No explicit licence found (copyright_policy page empty; footer 'Conte… | 2026-02-01: Submitted 17 Nov 2025; tabled 1 Feb 2026; Government accepted 41% vertical share | n/a | verified |
| union_fiscal | Economic Survey 2025-26 incl. Statistical Appendix (`mof_economic_survey_2025_26`) | none | indiabudget.gov.in copyright policy: may not be reproduced without Mi… | 2026-01-29: Economic Survey 2025-26 | Fiscal tables to 2024-25 PA | verified |
| union_fiscal | CGA Monthly Accounts of the Union Government and Provisional Accounts (`cga_monthly_accounts`) | none | No explicit licence (CGA Copyright-Policy page body is empty; footer… | 2026-08-31: July 2026 (Apr-Jul 2026-27); August due 2026-09-30. Provisional Accounts 2025-26: total expenditu… | Last day of following month; March by 31 May | corrected |
| union_fiscal | Union Government Finance Accounts, Appropriation Accounts and Accounts at a Glance (audited) (`cga_finance_accounts_aag`) | none | No explicit licence (CGA Copyright-Policy page body is empty; footer… | 2026-06-30: Finance Accounts 2024-25 (Statements 1-16, 14A, 9-Appendix; LM 22-23 Dec 2025); AAG 2024-25 (LM 3… | Finance Accounts ~9 months; AAG ~15 months | corrected |
| union_fiscal | An Economic and Functional Classification of the Central Government Budget (`dea_economic_functional_classification`) | none | DEA copyright policy: reproduction free of charge after taking permis… | 2019-11-07: 2017-18 edition published 07.11.2019; columns 2015-16 (A), 2016-17 (RE), 2017-18 (BE) | n/a | corrected |
| union_fiscal | DEA public debt: Quarterly Report on Public Debt Management (ownership of G-secs/T-bills), Status Paper on Government Debt, Central Government Debt data, Market Borrowing statement (`dea_public_debt_reports`) | none | DEA copyright policy: reproduction free of charge after taking permis… | 2026-08-13: QR Jan-Mar 2026 (13 Jul 2026); Central Govt Debt quarter ended Mar 2026 (30 Jun 2026); Market Bor… | QR ~3.5 months; Status Paper ~17 months | corrected |
| union_fiscal | GST revenue statistics (monthly revenue report PDF, state-wise collection/refund XLSX, IGST settlement XLSX) (`gstn_gst_statistics`) | none | No GODL. gst.gov.in Terms prohibit scraping; GST Council copyright: r… | unknown: August 2026 report (gross 1,99,853 cr, +14.8% vs revised Aug-25 1,74,116); XLSX 2026-27 data to 31 J… | Monthly PDF: publication date not established (se… | disputed |
| union_fiscal | CBDT Direct Tax Time Series (FY 2000-01 onward) and Income Tax Return statistics (`cbdt_time_series`) | manual_download | unverified (site 403) | unknown: Time series to FY 2024-25 (provisional; net direct taxes Rs 22.26 lakh cr; direct tax/GDP 6.73% on o… | ~7-12 months | unverified |
| union_fiscal | CBIC customs and central excise revenue (via Receipt Budget and CGA) (`cbic_indirect_tax`) | none | indiabudget.gov.in copyright policy: may not be reproduced without Mi… | 2026-02-01: Actuals 2024-25 in Budget 2026-27: customs 2,33,201 cr; union excise 3,00,253 cr | ~10 months | verified |
| union_fiscal | PPAC: Contribution of Petroleum Sector to Central and State Exchequer (`ppac_petroleum_exchequer`) | none | PPAC Terms & Conditions: material 'may be reproduced free of charge',… | 2026-07-17: Table posted 17.07.2026, period 2014-15 to 2025-26 (P); 2023-24 Central excise on petroleum 2,73,… | ~6 months | verified |
| union_fiscal | CAG Report No. 6 of 2026 (Financial Audit) on Accounts of the Union Government 2024-25 (`cag_union_accounts_audit_2024_25`) | none | CAG copyright policy: may be reproduced free of charge if accurate an… | 2026-04-02: Report 6 of 2026, reportedly tabled 2 Apr 2026 | ~12 months | verified |
| union_fiscal | National Small Savings: collections under National Savings Schemes (National Savings Institute) and NSSF (`nsi_small_savings_collections`) | none | NSI Copyright Policy: 'may not be reproduced partially or fully, with… | unknown: Annual table to 2025-26: gross deposits 12,53,943.04, net 4,31,205.74 (Rs crore). Publication date n… | unknown (2025-26 present by 2026-09-29) | verified |
| union_fiscal | Public Enterprises Survey (CPSE accounts), Department of Public Enterprises - could not be accessed in Phase 0 (`dpe_public_enterprises_survey`) | manual_download | unverified (site content not readable without JavaScript) | unknown: unverified: latest edition and date could not be read | unknown | unverified |
| state_fiscal | State Finances: A Study of Budgets of 2025-26 (`rbi_state_finances_study`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-01-23: 2025-26 edition: 2023-24 Accounts, 2024-25 RE, 2025-26 BE; 2026-27 edition not yet out (expected… | Accounts ~21-22 months | corrected |
| state_fiscal | Sixteenth Finance Commission relevant-data files (KFI, transfers, subsidies, salaries, SPSEs) (`fc16_relevant_data`) | none | No explicit licence found (copyright_policy page empty; footer 'Conte… | 2026-02-05: Files LM 3-5 Feb 2026 (SPSE file 9 Mar 2026) | KFI to 2023-24 accounts | verified |
| state_fiscal | FC16 ULB Data Dump (Cityfinance) (`fc16_ulb_cityfinance_dump`) | none | No explicit licence found (copyright_policy page empty; footer 'Conte… | 2026-02-19: LM 2026-02-19; data to 2023-24 | ~2 years | verified |
| state_fiscal | CAG State Finance Accounts and Appropriation Accounts (per state) (`cag_state_finance_accounts`) | login | CAG copyright policy: may be reproduced free of charge if accurate an… | 2026-03: 2024-25 Finance Accounts posted for all states with pages except Goa (Goa, Delhi, Puducherry pages e… | ~9-12 months | corrected |
| state_fiscal | CAG Monthly Key Indicators (Accounts at a Glance) of State Governments (`cag_monthly_key_indicators`) | none | CAG copyright policy: may be reproduced free of charge if accurate an… | 2026-09: August 2026 for 22 states; July for Arunachal, Nagaland; May for Manipur | ~1-2 months | corrected |
| state_fiscal | CAG Publication on State Finances 2024-25 (3rd edition; all 28 states, 10-year) (`cag_state_finances_publication`) | none | CAG copyright policy: may be reproduced free of charge if accurate an… | 2026-06-16: State Finances 2024-25 (2015-16 to 2024-25): RR Rs 40.52 lakh cr; expenditure 51.20 lakh cr (15.7… | ~15 months | corrected |
| state_fiscal | CAG State Finances Audit Reports 2024-25 (per state) (`cag_sfar_2024_25`) | none | CAG copyright policy: may be reproduced free of charge if accurate an… | 2026: Several 2024-25 SFARs (e.g. Report No. 1 of 2026; HP, Nagaland, Manipur, TN) | ~12 months | verified |
| state_fiscal | Union Budget Expenditure Profile Statement 18 and Demand No. 42 (Transfers to States) (`union_budget_transfers_to_states`) | none | indiabudget.gov.in copyright policy: may not be reproduced without Mi… | 2026-02-01: Budget 2026-27: Statement 18 grand total (excl. devolution) 9,38,628.46 (A 2024-25) ... 10,94,513… | ~10 months | verified |
| state_fiscal | PIB / MoF tax devolution instalment releases (state-wise) (`pib_tax_devolution_releases`) | none | not established (PIB copyright URL errors) | 2026-08-01: 1 Aug 2026 additional instalment Rs 1,09,019 cr (UP 19,208 = 17.619%) | Same day | unverified |
| state_fiscal | PRS Legislative Research state budget analyses and State of State Finances (`prs_state_budget_analyses`) | none | Creative Commons Attribution 4.0 International | 2025-11-14: 30 state budget analyses 2026-27; State of State Finances 2025-26 (PDF LM 14 Nov 2025) | Weeks | verified |
| state_fiscal | GST monthly revenue report: state-wise SGST pre/post settlement (`gst_monthly_state_revenue`) | none | See gstn_gst_statistics (no GODL; permission needed) | unknown: August 2026 report | unknown (publication date not established; server… | verified |
| state_fiscal | RBI Report on Municipal Finances (`rbi_municipal_finances`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2024-11-13: Report on Municipal Finances | unverified | verified |
| state_fiscal | RBI Finances of Panchayati Raj Institutions 2020-21 to 2022-23 (`rbi_pri_finances`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2024-01-24: Released 24 Jan 2024 | ~1 year | verified |
| state_fiscal | RBI Handbook of Statistics on Indian States 2024-25 (fiscal tables) (`rbi_handbook_indian_states`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2025-12-11: 2024-25 edition | ~1 year | verified |
| state_fiscal | eGramSwaraj Receipt and Expenditure Analysis Report (Union XV FC grants to PRIs) (`egramswaraj_panchayat_accounts`) | none | not checked | n/a: FY 2020-21 to 2026-27 | Near real-time | unverified |
| markets_finsector | SEBI Bulletin (monthly) with Annexure Tables (Excel) (`sebi_bulletin_monthly`) | none | SEBI website policy: reproduction free of charge after permission by… | 2026-09-23: September 2026 issue (data to 31 Aug 2026); August issue 2026-08-27 (data to 31 Jul 2026) | ~3-4 weeks | corrected |
| markets_finsector | SEBI Handbook of Statistics on Indian Securities Market 2025-26 (per-table XLSX) (`sebi_handbook_statistics`) | none | SEBI website policy: reproduction free of charge after permission by… | 2026-08-17: Handbook 2025-26 (to Mar 2026) | ~4.5 months | verified |
| markets_finsector | NSDL FPI Monitor (`nsdl_fpi_monitor`) | none | Proprietary: 'Reproduction, redistribution and transmission of any in… | 2026-09-29: Daily trends 28-Sep-2026; fortnightly sector data to 15 Sep 2026 | T+1 | corrected |
| markets_finsector | NSE / BSE market data (FII/DII activity, market cap, turnover) - NOT to be used (`nse_bse_market_data`) | paid | NSE Terms: no automated collection; no use for 'gaming, virtual tradi… | unknown: not accessed | Same day | unverified |
| markets_finsector | AMFI Monthly and Quarterly Mutual Fund Data (`amfi_monthly_quarterly`) | none | AMFI Terms: personal non-commercial use only; no public display, publ… | 2026-09-10: August 2026 monthly (net inflow 41,353.60; AUM 87,07,887.74 Rs crore; LM 10 Sep 2026); quarterly… | ~10 days | corrected |
| markets_finsector | CCIL Factbook 2024-25 and market statistics (`ccil_factbook`) | none | CCIL Terms: no commercial download/publish without express written co… | 2025-11-17: Factbook 2024-25 (uploaded ~2025-11-17) | ~7-8 months | verified |
| markets_finsector | RBI HBS 2025-26 market/NBFI tables (G-sec ownership, CP, CD, private placement, MF, FPI, LIC) (`rbi_hbs_market_tables`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2026-07-31: HBS 2025-26 | ~4 months | verified |
| markets_finsector | IRDAI Handbook on Indian Insurance Statistics 2024-25 (`irdai_handbook_insurance`) | none | IRDAI copyright policy: 'may be reproduced free of charge in any form… | 2026-02-03: 2024-25 edition; FY 2025-26 edition expected ~Feb 2027 (inference) | ~10 months | corrected |
| markets_finsector | IRDAI Monthly Business Figures (`irdai_monthly_business_figures`) | none | IRDAI copyright policy (reproduce with acknowledgement) | 2026-09-15: Life first-year premium to 31.08.2026 (09-09-2026); non-life flash to August 2026 (15-09-2026) | ~9-17 days | corrected |
| markets_finsector | IRDAI Annual Report 2024-25 (`irdai_annual_report`) | none | IRDAI copyright policy (reproduce with acknowledgement) | 2025-12-30: Annual Report 2024-25; 2025-26 expected ~Dec 2026 | ~9 months | corrected |
| markets_finsector | PFRDA NPS/APY Statistical Data and Handbook of NPS Statistics (`pfrda_nps_statistics`) | none | no explicit licence found ('(c) Copyright PFRDA. All rights reserved.… | 2026-09-29: M6 to Aug-2026 (AUM 18,22,758.49; G-sec 8,57,490; equity 5,15,522; corporate bonds 3,87,090); M2… | M6 ~1 month; M2 ~3 months; A-series >12 months | verified |
| markets_finsector | EPFO Annual Report and Consolidated Annual Accounts (`epfo_annual_report_accounts`) | none | EPFO copyright policy: reproduce free of charge without specific perm… | 2026-09-16: Annual Report 2024-25 (unaudited; contributions Rs 3,35,628.81 cr); Consolidated Annual Accounts… | AR ~1+ year; accounts ~3 years | corrected |
| markets_finsector | CDSL Periodic (monthly) Depository Statistics (`cdsl_periodic_stats`) | none | unverified (Disclaimer.aspx has no static text) | 2026-09-04: August 2026 (PDF LM 4 Sep 2026) | ~1 month | unverified |
| markets_finsector | SEBI Annual Report 2025-26 (`sebi_annual_report_2025_26`) | none | SEBI website policy: reproduction free of charge after permission by… | 2026-08-06: Annual Report 2025-26 | ~4 months | verified |
| markets_finsector | SEBI MF Deployment of Funds by all Mutual Funds (stale) (`sebi_mf_deployment_of_funds`) | none | SEBI website policy: reproduction free of charge after permission by… | 2025-05: May 2025 is latest month offered | n/a (stale) | verified |
| markets_finsector | FIMMDA CP/CD traded data archive (`fimmda_cp_cd_traded`) | none | not checked | unknown: unverified | unverified | unverified |
| international | OECD Inter-Country Input-Output tables (ICIO), 2025 edition (`oecd_icio_2025`) | none | OECD Terms & Conditions: Data may be extracted, copied, adapted, dist… | 2026-01: 2025 edition, second revision mid-Jan 2026 ('No further revisions are anticipated'); all files re-up… | ~3 years | verified |
| international | OECD national Input-Output Tables 2025 edition (incl. value-added components) (`oecd_national_iots_2025`) | none | OECD Terms & Conditions: Data may be extracted, copied, adapted, dist… | 2026-01-20: 2025 release (CSV dated 2026-01-20) | ~3 years | verified |
| international | OECD Trade in Value Added (TiVA) 2025 edition (SDMX) (`oecd_tiva_2025`) | none | OECD Terms & Conditions: Data may be extracted, copied, adapted, dist… | unknown: 2025 edition | ~3 years | verified |
| international | ADB Multiregional Input-Output Tables and India national IOT (`adb_mrio`) | none | KIDB terms: data 'may be copied, downloaded, distributed, adapted, du… | 2025-08: MRIO and 'IND IOT 2000, 2007-2024.xlsx' updated August 2025; no 2026 update yet | ~1 year | corrected |
| international | World Bank World Development Indicators (`wb_wdi`) | none | Creative Commons Attribution 4.0 | 2026-07-13: API lastupdated 2026-07-13; bulk files 2026-07-17 | Months | corrected |
| international | IMF SDMX API (BOP, IIP, IMTS, ANEA, GFS, MFS, DIP, PIP, WEO) (`imf_sdmx`) | none | IMF API LICENSE field: '(c) International Monetary Fund Copyright. Al… | 2026-09-28: BOP India updated 2026-09-28 (annual to 2025, CAB -20.23 bn); ANEA 2026-09-28; IMTS 2026-08-31; W… | BOP ~1 quarter | verified |
| international | UN Comtrade (goods HS; services EBOPS) (`un_comtrade`) | api_key | 'Provided for internal use only and may not be re-disseminated ... wi… | 2026-09-18: India goods annual CY2025 (released 2026-07-10); monthly to July 2026 (released 2026-09-18); serv… | Monthly ~2 months; annual ~6 months | corrected |
| international | BIS statistics (total credit, LBS, CBS, debt securities) (`bis_stats`) | none | BIS: use unrestricted provided BIS is cited, not misleading, no extra… | unknown: WS_TC, LBS, CBS, DSS to 2026-Q1; WS_DEBT_SEC2_PUB to 2026-Q2 | ~4-6 months | verified |
| international | UN National Accounts - Analysis of Main Aggregates (`un_snaama`) | none | UNdata terms: free to copy and distribute with UNdata cited | 2026-01: Upload January 2026; India to 2024 | ~1-2 years | verified |
| international | UNdata National Accounts Official Country Data - institutional sector accounts (Table 4.x) (`undata_sna_institutional`) | none | UNdata terms: free with citation | unknown: India latest shown FY 2019-20 | ~several years | verified |
| international | OECD-WTO Balanced Trade in Services (BaTIS) (`oecd_wto_batis`) | none | OECD Terms & Conditions: Data may be extracted, copied, adapted, dist… | unknown: Coverage to 2024 | ~1-2 years | verified |
| international | Eurostat FIGARO inter-country SUT/IOT (2026 edition) (`eurostat_figaro`) | none | Eurostat CC BY 4.0, EXCEPT data for non-EU/EFTA/candidate countries (… | 2026-07-20: 2026 edition; India 2022-2024 updated 2026-07-20 | ~1.5-2 years | corrected |
| international | Eora / Eora2 global MRIO (`eora_mrio`) | paid | Free only for academic use (1990-2017, <=200 raw points); commercial… | unknown: Eora2 1990-2024 | ~2 years | verified |
| international | GTAP Data Base v12 (`gtap_db`) | paid | Proprietary; not sold to re-sellers/third parties | 2026-02: GTAP 12, February 2026 | ~2-3 years | verified |
| international | EXIOBASE 3 (`exiobase3`) | none | DISPUTED: exiobase.eu says CC BY-SA 4.0; Zenodo (v3.9+ incl. v3.10.2)… | 2026-05-13: v3.10.2 published 2026-05-13 (IOT 1995-2024; real data to ~2021/22, nowcasts after) | 3-4 years real data | disputed |
| international | World Input-Output Database 2016 release (`wiod_2016`) | none | Creative Commons Attribution 4.0 | 2016: 2016 release | n/a | verified |
| international | World Bank WITS - UNCTAD TRAINS tariffs (`wb_wits_trains`) | none | not checked (unverified) | 2022-09-09: India latest 2021 (updated 2022-09-09) | Several years | unverified |
| prior_art | IFPRI Nexus SAM for India 2022/23 (dataset + data paper) (`ifpri_nexus_sam_india_2022_23`) | registration | CC BY 4.0 (CGSpace dataset record hdl 10568/163735; IFPRI Datasets Te… | 2024-11-08: 2022/23 SAM, Dataverse v1 2024-11-08; still latest per Nexus release note 2025-12-12 | ~1.5-2 years | corrected |
| prior_art | IFPRI SAM for India 2017-18 (Pal, Pradesha, Thurlow 2020) (`ifpri_sam_india_2017_18`) | registration | CC BY 4.0 (CGSpace dataset record hdl 10568/163735; IFPRI Datasets Te… | 2021-04-23: Dataverse 2021-04-23; paper 2020-11-01 | ~3 years | corrected |
| prior_art | IFPRI 2017/18 SAMs for Odisha, Uttar Pradesh, Bihar (`ifpri_state_sams_2017_18`) | registration | CC BY 4.0 (CGSpace dataset record hdl 10568/163735; IFPRI Datasets Te… | 2025-01-06: Odisha 2025-01-06; UP and Bihar 2024-08-08 | n/a | verified |
| prior_art | CSTEP energy-disaggregated SAM India 2017-18 (Excel) + CSTEP-TN-2024-2 (`cstep_sam_india_2017_18`) | none | (c) 2024 CSTEP; reproduction must cite title/citation and credit copy… | 2025-06-23: Technical note Aug 2024; XLSX LM 2025-06-23 | ~7 years | corrected |
| prior_art | NCAER SAM for India 2021-22 (WP 160; Margin 2024) (`ncaer_sam_india_2021_22`) | none | All rights reserved (site footer) | 2024-02-05: WP 160 (cover Jan 2024; web 2024-02-05) | ~2 years | corrected |
| prior_art | CSEP Environmentally-extended SAM for India 2019-20 (`csep_esam_india_2019_20`) | none | All rights reserved; short quotes (<=2 paragraphs) allowed with credit | 2023-11-22: Page 2023-11-22 (modified 2024-06-21) | ~3 years | corrected |
| prior_art | Pradhan, Saluja & Sharma (2013) SAM for India 2007-08, IEG WP 326 (`ieg_sam_india_2007_08`) | none | All rights reserved (site footer) | 2013: 2013 | ~5 years | verified |
| prior_art | Pal & Bandarlage (2017) value-added disaggregated SAM for India 2007-08, J. Economic Structures (`pal_bandarlage_2017`) | none | Creative Commons Attribution 4.0 | 2017: 2017 | n/a | verified |
| prior_art | Pal, Pohit & Roy (2012) SAM for India 2003-04, Economic Systems Research 24(1) (`pal_pohit_roy_2012`) | paid | Publisher copyright | 2012: 2012 | n/a | unverified |
| prior_art | India MRIO dataset, 32 states, 2011-2019 (Zheng et al., Scientific Data 2026) (`india_mrio_32states_2011_2019`) | none | CC BY 4.0 | 2026-06-30: Article 24 Apr 2026; figshare v1 2026-06-30 | ~7 years | verified |
| prior_art | RBI Monetary Policy Report April 2019, Box III.1 'Estimable Fiscal Multipliers for India' (`rbi_mpr_2019_fiscal_multipliers`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2019-04-04: 4 Apr 2019 | n/a | verified |
| prior_art | RBI Bulletin articles citing RBI (2019) capex multipliers (Dec 2020; Jun 2021) (`rbi_bulletin_capex_multipliers`) | none | RBI Bulletin imprint: '(c) Reserve Bank of India 2026. All rights res… | 2021-06-16: 24 Dec 2020 and 16 Jun 2021 | n/a | corrected |
| prior_art | Jain & Kumar (2013) Government Expenditure Multipliers in India: SVAR, RBI WPS 07/2013 (`rbi_jain_kumar_2013_multipliers`) | none | No open-data licence. RBI website Disclaimer: caching/framing prohibi… | 2013-09-18: 18 Sep 2013 | n/a | corrected |
| prior_art | NIPFP fiscal multiplier studies (WP 2013-125; WP 436 2025) (`nipfp_fiscal_multipliers`) | none | no explicit licence found | 2025-09: WP 436, September 2025 | n/a | corrected |
| prior_art | Goyal & Sharma (2018) Government Expenditure in India: Composition and Multipliers, J. Quantitative Economics (`goyal_sharma_2018`) | none | Publisher copyright | 2018-12: Dec 2018 | n/a | verified |
| prior_art | Mishra & Adiraju (2025) Estimation of fiscal multipliers for India, IJEPEE 21(1) (`mishra_adiraju_2025`) | none | Publisher copyright | 2025: 2025 | n/a | verified |
| prior_art | Report of the Committee on Private Final Consumption Expenditure (Adhikari Committee), MoSPI 2015 (`adhikari_pfce_committee`) | none | MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-… | 2015-05-22: 22 May 2015; EPW (Kumar & Seth) 31 Jan 2026 | n/a | verified |
| prior_art | Venkatesh & Pal: From SUTs to SAMs for India (IIOA 2019); IOT/SAM 2012-13 (CSTEP WP 2018) (`sut_to_sam_methodology_india`) | none | no explicit licence found | 2019-06: June 2019 | n/a | verified |

## 2. Key verified facts

| # | Fact | Evidence (fetched 2026-09-29) |
|---|---|---|
| 1 | **The current GDP base year is 2022-23.** MoSPI released the new series on **27 Feb 2026**, replacing base 2011-12. It updated the series on **31 Aug 2026** (NAS 2026) to use the new PPI, IIP and BkSPI. The base year did not change. | Q1 2026-27 press note: "released the New Series of Annual and Quarterly GDP estimates with base year 2022-23 on 27th February, 2026" — <https://www.mospi.gov.in/uploads/latestReleases/latest_release_1788172583113_d65a77cf-240e-4491-82ee-59f78618fa41_Press_Note_on_GDP_Estimates_for_Q1_2026-27.pdf>; Sources & Methods press note: "subsequently updated on 31st August 2026" — <https://www.mospi.gov.in/uploads/latestReleases/latest_release_1789988911616_c0cfdbfb-61e9-4316-a532-0dd2b52c0997_Press_Note_for_release_of_Sources_and_Methods_for_compilation_of_National_Accounts_Statistics.pdf> |
| 2 | **The new series has at least three vintages:** 27 Feb 2026 (SAE), 5 Jun 2026 (PE 2025-26) and 31 Aug 2026 (NAS 2026). For 2022-23, GDP moved from 2,61,17,627 to 2,61,77,001. For 2025-26, it went 3,45,47,157 → 3,46,35,638 → 3,45,36,796. The 2024-25 discrepancy flipped from +85,801 to −1,07,438. WDI, the RBI Handbook (T1) and the Budget ratios each carry older vintages. | NAS 2026 press release — <https://www.mospi.gov.in/uploads/latestReleases/latest_release_1788171660220_f2a7f5ed-3ce3-45cc-a5b2-eebc84623a01_Final_Press_Release_on_NAS_2026.pdf>; PE note — <https://www.mospi.gov.in/uploads/latestReleases/latest_release_1780655857536_5ac01869-ca4a-422d-b7a7-57b81da60932_Press_Note_on_GDP_Estimates_for_Q4_2025-26_and_PE_FY_2025-26_F.pdf> |
| 3 | **The latest NAS is NAS 2026 (31 Aug 2026).** It has 60 statements: Final Estimates for 2022-23 and 2023-24, and First Revised Estimates for 2024-25. It adds 4 statements for PE 2025-26 and the quarters. At current prices the discrepancy is **0 in the Final years**; it is −1,07,438 in the 2024-25 FRE. | NAS 2026 PR ("sixty statements based on the updated Final Estimates…"); statement 1.1 — <https://www.mospi.gov.in/uploads/publications_reports/NAS-2026-Statements/1.1.xlsx> (lead re-fetched: HTTP 200) |
| 4 | **Even in Final years the NAS does not close the capital or household accounts.** GCF minus (saving + net capital inflow) is +5,20,083 (2022-23), +3,58,634 (2023-24) and −2,79,181 (2024-25). Household GDI − PFCE − household saving is +8,12,857, +5,71,133 and −1,28,402. | Statements 1.1, 1.9, 1.14 — <https://www.mospi.gov.in/uploads/publications_reports/NAS-2026-Statements/1.9.xlsx>; Sources & Methods §26.6 ("attributed as errors and omissions") |
| 5 | **No sequences of accounts exist on the new base.** They are absent from NAS 2026 and NAS 2025. The last edition with full institutional sequences (D1–D8 by sector) is **NAS 2024, on the old base, for 2011-12 to 2022-23**. | <https://www.mospi.gov.in/sites/default/files/reports_and_publication/statistical_publication/National_Accounts/NAS2024/5.0.xlsx>; chapter API for pubs 2861/432/434 |
| 6 | **No back series on the new base yet.** MoSPI expects it by December 2026. At the rebasing (27 Feb 2026), MoSPI's own comparison puts 2022-23 GDP at 2,68,90,473 on the old base and 2,61,17,627 on the new one: **−2.9%**. That is the rebasing effect. Separately, NAS 2026 (31 Aug 2026) later revised new-base 2022-23 GDP up by 59,374, to 2,61,77,001. This is a vintage revision, not part of the rebasing. | FAQ — <https://www.mospi.gov.in/uploads/announcements/announcements_1772117257791_84ae898f-7be2-4b7d-a135-565e1a809513_FAQ_GDP_26022026_1902.pdf>; 27 Feb 2026 press note (HTTP 200, 1,552,814 B), comparison table row "GDP 26890473 26117627 -2.9" — <https://www.mospi.gov.in/uploads/latestReleases/latest_release_1781177791292_64ed3233-1794-4aef-9410-a371ce44a028_latest_release_1772189865181_f040336d-bc57-4aed-b80f-586d9ccb279e_Press_Note_on_New_Series_of_GDP_Estimates_with_Base_Year_2022-23_27022026-F.pdf>; NAS 2026 1.1.xlsx (26177001.4) |
| 7 | **The latest SUTs are 2022-23 and 2023-24 (base 2022-23), at 155 products × 67 industries.** They were first released on 15 May 2026 and revised on 31 Aug 2026. They reproduce NAS GDP exactly (2022-23: 26,177,001) at current prices only. | <https://www.mospi.gov.in/publications-reports/innerpage/847>; the MoSPI-hosted PIB PR "encompassing 155 products and 67 industries" — <https://www.mospi.gov.in/uploads/latestReleases/latest_release_1778842800782_05f10605-5575-44cb-87cf-a770e5a80b1c_Press_Release_Page___Press_Information_Bureau.pdf> |
| 8 | **The latest official IOTT is 2007-08** (130 sectors, factor cost, 2004-05 series). No official SAM exists. A symmetric IOT must be derived from the SUT. | <https://www.mospi.gov.in/sites/default/files/reports_and_publication/cso_national_accounts/input_output_transactions_table/2007_08/Binder1.pdf> |
| 9 | **The latest HCES is 2023-24** (fieldwork Aug 2023–Jul 2024). The report, Excel tables and unit data came out on 30 Jan 2025; 2022-23 also exists. HCES aggregate consumption is about 44% of NAS PFCE, so use it only for shares. The first official income survey (NHIS) went into the field from April 2026, and no results are out yet. | <https://mospi.gov.in/sites/default/files/press_release/HCES_Report202324_Press_Note_30012025.pdf>; PIB 30 Jul 2025 — <https://www.pib.gov.in/PressReleasePage.aspx?PRID=2150168&reg=48&lang=2> |
| 10 | **PLFS:** the first calendar-year report (CY 2025) was released on 27 Mar 2026. A design break in Jan 2025 means the figures are "not strictly comparable". There is no July 2024–June 2025 report. | <https://www.mospi.gov.in/uploads/latestReleases/latest_release_1774607827733_3e8964a9-268b-4cc9-ad65-cfc8a9e32f08_Press_note_AR_PLFS_2025_23032025_V2.1_26032026_final.pdf> |
| 11 | **The latest Flow of Funds is RBI FSF 2023-24,** published in the RBI Bulletin on 21 Jan 2026. It has 71 sheets, stocks from 2011-12 and flows from 2012-13. No 2024-25 edition exists. It is probably on the **old** GDP base: this is inferred, because it cites 12.0% nominal growth against 10.97% on the new base. Its FWTW tables are sector × sector only. | <https://www.rbi.org.in/Scripts/FlowofFundsAccounts.aspx>; <https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx?Id=23912> |
| 12 | **The latest RBI State Finances study is the 2025-26 edition** (23 Jan 2026). It covers 2023-24 Accounts, 2024-25 RE and 2025-26 BE; the 2026-27 edition is not out. **CAG's State Finances 2024-25** (3rd edition, audited, all 28 states, 2015-16 to 2024-25) was released on 16 Jun 2026, but only as a Tableau dashboard. CAG Finance Accounts for 2024-25 are posted for every state except Goa. | <https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=State%20Finances%20:%20A%20Study%20of%20Budgets>; <https://cag.gov.in/en/page-statefinances24-25> (lead: HTTP 200, embeds Tableau "Final1_1-StateFinance2024-25"); CAG press release dated "16th June, 2026": "released the third edition of the Publication on State Finances 2024-25 here today" — <https://cag.gov.in/uploads/PressRelease/PR-PRESS-RELEASE-on-PUBLICATION-on-STATE-FINANCES-2024-25-16-6-25-06a32183f4f8ce5-79805864.pdf> |
| 13 | **Latest BoP:** Q1 2026-27 was released on 1 Sep 2026 (CAD US$4.2 bn, 0.5% of GDP). The full year 2025-26 (P) came out on 8 Jun 2026 (CA −US$25.2 bn). The BPM6 rupee version for 2025-26 is in HBS Table 127. A new monthly BoP has run since June 2026. 2026-27 flows are distorted by the FCNR(B)/ECB swap window (US$143.6 bn mobilised). | <https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63493>; <https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=62890>; <https://www.rbi.org.in/scripts/PublicationsView.aspx?id=23952> |
| 14 | **Union finances:** Budget 2026-27 (1 Feb 2026) carries Actuals for 2024-25. Its %-of-GDP ratios use the **old-base** GDP (AE 2025-26 of 357,13,886). Audited Finance Accounts cover 2024-25; the CAG audit is Report 6 of 2026. CGA Provisional Accounts for 2025-26 show an FD of 15,19,169. The 16th FC keeps the states' share at 41%, which the government accepted. | <https://www.indiabudget.gov.in/doc/Budget_at_Glance/budget_at_a_glance.xlsx>; <https://cga.nic.in/MonthlyReport/Published/3/2025-2026.aspx>; <https://www.indiabudget.gov.in/doc/16fc.pdf> |
| 15 | **RBI Handbook of Statistics 2025-26** (28th edition, 245 tables) was released on 31 Jul 2026. It mixes bases: T1 and T11 are on the new base, T12 and T13 on the old. | <https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook%20of%20Statistics%20on%20Indian%20Economy> |
| 16 | **Other base years:** CPI is on 2024=100 (first release 12 Feb 2026). IIP is on 2022-23 (first release 1 Jun 2026, NIC 2025). WPI and the new PPIs are on 2022-23 (15 Jun 2026; weights from SUT 2022-23). The trial ISP is on 2024-25. | CPI Jan-26 PR; IIP PR Aug 2026; PIB 2272872 / 2267963; NSDP 1 Sep 2026 — <https://www.mospi.gov.in/uploads/public_documents/public_documents1788258449961_cfd300e9-0c0f-4603-adde-f64232dd52d4_NSDP_for_SDDS_English_1st_September_2026_English.pdf> |
| 17 | **ASI:** the latest published round is 2023-24. The 2024-25 results are **scheduled for today (29 Sep 2026)** in the ARC 2026-27, but they were not yet in the MoSPI release feed or API when the lead checked. | ARC — <https://www.mospi.gov.in/uploads/documents/releaseCalender/1788266096813-ARC%202026-27%20updated%20till%20August%202026.pdf>; <https://api.mospi.gov.in/api/asi/getAsiFilter?classification_year=2008> |
| 18 | **Upcoming releases that matter for the reference year:** Q2 GDP on 30 Nov 2026; the new-base back series by Dec 2026; FAE on 7 Jan 2027; **Final Estimates for 2024-25 plus FRE 2025-26 on 26 Feb 2027**, likely followed later by a 2024-25 SUT (an inference). End-June 2026 external debt, IIP and Q1 invisibles are likely out on 30 Sep 2026. | ARC 2026-27 (above); RBI listings for sections 355 and 356 |

**Data availability by candidate reference year.** This summarises the facts above; the recommendation itself belongs in the Phase 0 reference-year document.

| Year | NAS (new base) | SUT | Flow of Funds (RBI) | HCES | BoP | Union audited | States audited | Full sequences of accounts |
|---|---|---|---|---|---|---|---|---|
| 2022-23 | Final (discrepancy 0) | Yes | Yes (old base) | Yes (Aug 22–Jul 23) | Yes | Yes | Yes | Old base only (NAS 2024) |
| 2023-24 | Final (discrepancy 0) | Yes | Yes (old base, latest) | Yes (Aug 23–Jul 24, latest) | Yes | Yes | Yes (RBI SF + CAG) | No |
| 2024-25 | FRE (discrepancy −1,07,438) | No (expected after FE on 26 Feb 2027) | No | No | Yes | Yes | CAG only (RBI SF expected ~Dec 2026–Jan 2027) | No |
| 2025-26 | PE only | No | No | No | Yes (P) | Provisional (CGA) | No | No |

## 3. Per-family details

Each entry lists the landing URL, access, formats, coverage, price basis, main series and quirks. Evidence for each entry is in `data/registry.yaml` (`verification`).

### 3.1 MoSPI National Accounts (`mospi_nas`)

**National Accounts Statistics 2026 (new base 2022-23), per-statement XLSX** (`mospi_nas_2026_publication`, corrected)

- Publisher: National Accounts Division, NSO, MoSPI. Landing: <https://mospi.gov.in/publications-reports/innerpage/2861>
- Access: Bulk download, one XLSX per statement at /uploads/publications_reports/NAS-2026-Statements/<stmt>.xlsx. Landing page is a React SPA; file list via public JSON endpoint POST /api/publications-reports/get-web-chapter-data {publication_id:2861}. No combined workbook for 2026. Plain GET of files returned 200 on 2026-09-29 (lead re-check, no User-Agent). Missing files return 403, not 404. Requires: none. Formats: xlsx.
- Latest: 2026-08-31 - NAS 2026: 60 statements (FE 2022-23 and 2023-24, FRE 2024-25) + 4 statements (PE 2025-26 and quarterly Q1 2022-23 to Q4 2025-26); 64 sub-chapters. Frequency: Annual (plus reprints of PE and quarterly statements). Lag: About 17 months after end of the latest FRE year (2024-25). NAS 2025 came out 2025-06-26.
- Coverage: 2022-23 to 2024-25 (Detail 2022-23 to 2024-25; PE 2025-26 aggregates; no pre-2022-23 years on the new base (back series pending, expected by Dec 2026)). Basis: Base 2022-23; current and constant 2022-23 prices; Rs crore. Saving and disposable income current prices only. Double deflation for manufacturing and agriculture.
- Key series: 1.1 - Key aggregates: GVA, product taxes/subsidies, GDP, CFC, PFCE, GFCE, GFCF, CIS, valuables, X, M, discrepancies, primary income from RoW, GNI, NNI, current transfers, GNDI, gross saving [Rs crore]; 1.5 - Output, IC, GVA, CFC, CE, OS/MI, production taxes by activity; GCF by industry of use [Rs crore]; 1.6 - GVA by activity (~24 rows) [Rs crore]; 1.9 - Finances for GCF: gross saving by institution (NFC public DE/NDE, private; FC public/private; general govt; households: financial saving, liabilities, physical assets, gold/silver) + net capital inflow [Rs crore]; 1.11 - GFCF by asset x institutional sector [Rs crore]; 1.13 - FISIM by using industry [Rs crore]; 1.14 - Institutional key indicators: GVA, gross saving, GCF (excl. valuables), CFC for all 6 sectors; GDI and final consumption ONLY for general government and households incl. NPISH [Rs crore]; 4.1/4.2 - Value added by Centre and each State; COFOG expenditure of general government (no interest-payments row) [Rs crore]; 5.1/5.2/5.3 - PFCE by COICOP 2018; individual consumption; household financial assets and liabilities by instrument [Rs crore]; 6.1/6.2 - Detailed external transactions account (current account shown with services imports NOT CIF-adjusted); constant-price external aggregates [Rs crore]; 7.1-7.4C - Output, IC, GVA, net production taxes, CFC, CE, OS/MI (net of CFC) by industry: total, public, private corporate, household; GCF/GFCF/CIS/CFC/net capital stock [Rs crore]; 8.x - Disaggregated industry statements; 8.15 GG/DE/NDE; 8.17 PE 2025-26; 8.18 quarterly GDP by expenditure [Rs crore].
- SAM use: activity output and intermediate totals; value added: CE, OS/MI, CFC, net production taxes by industry; product taxes/subsidies totals; final demand totals (PFCE, GFCE, GFCF, CIS, valuables, X, M); PFCE by COICOP; institutional saving and GCF (6 sectors); household financial vs physical saving; RoW current/capital/financial account; government value added Centre vs States; COFOG.
- Quirks: (1) SPA landing page; use JSON API. (2) Missing /uploads/ files return 403. (3) Full sequences of accounts (1.3, 1.15, Ch 2, 3, 4.0, 5.0, 6.0) NOT published in NAS 2026 or NAS 2025 although Sources & Methods s.30.7 describes them. (4) Current-price discrepancy 0 only for Final years (2022-23, 2023-24); 2024-25 FRE -1,07,438 cr; constant 0 / -70,316 / +36,908. (5) Saving + NCI != GCF even in Final years (implied errors & omissions GCF-(saving+NCI): +5,20,083 / +3,58,634 / -2,79,181 cr). (6) Household GDI is a residual; HH GDI - PFCE - HH saving = +8,12,857 / +5,71,133 / -1,28,402 cr. (7) Mixed income not separated from OS; household sector includes NPISH and quasi-corporates. (8) At least three vintages of the new series: 27 Feb 2026, 5 Jun 2026 (PE), 31 Aug 2026 (NAS 2026). Always record vintage. (9) Bilingual Hindi/English label columns, merged headers.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**MoSPI NAS REST API (eSankhyiki backend)** (`mospi_nas_api`, corrected)

- Publisher: MoSPI (NSO), eSankhyiki. Landing: <https://api.mospi.gov.in/>
- Access: API: HTTP GET, no key, JSON. Endpoints getNasIndicatorList, getNasFilterByIndicatorId (needs frequency_code), getNASData. Official MIT Python client 'mospi-esankhyiki' (PyPI 0.2.1). Client default base_url is a private UAT IP (http://10.24.89.9:5000); set https://api.mospi.gov.in explicitly. Paginate (10 records/page). Requires: none. Formats: json.
- Latest: 2026-08-31 - Includes Q1 2026-27 (GDP current 88,26,871 cr) and annual 2022-23 to 2025-26, identical to NAS 2026. Frequency: Updated with each GDP release. Lag: Same day as press releases.
- Coverage: 1950-51 to Q1 2026-27 (Base 2022-23 'Current': annual 2022-23 to 2025-26, quarterly Q1 2022-23 to Q1 2026-27. Base 2011-12 'Current': 2011-12 to 2025-26 with a separate record per revision round. Base 2011-12 'Back': 1950-51 to 2011-12 (62 records). State GSDP (account_code=2) base 2011-12 only). Basis: current_price and constant_price fields; unit Rs crore.
- Key series: indicator_code 1 - GVA by industry_code 1-15, subindustry 1-18, institutional_code 1-7 [Rs crore]; indicator_code 2-4 - Net taxes / taxes / subsidies on products [Rs crore]; indicator_code 5-7 - GDP, CFC, NDP [Rs crore]; indicator_code 8-15 - GCF by industry of use, GFCF, PFCE, GFCE, CIS, valuables, exports, imports [Rs crore]; indicator_code 16-19 - Primary income from RoW, GNI, other current transfers, GNDI [Rs crore]; indicator_code 20 - Gross saving by institutional sector [Rs crore]; revision_code - 3 PE, 4 FRE, 8 Final [code].
- SAM use: macro control totals; GVA by industry and institutional sector; gross saving by institution; quarterly time series.
- Quirks: Format=CSV returns header only (use JSON). Headline aggregates only: no CE/OS by industry, no household financial detail, no RoW detail, no COFOG.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**eSankhyiki portal - Macro Indicators (NAS)** (`mospi_esankhyiki_portal`, verified)

- Publisher: MoSPI. Landing: <https://esankhyiki.mospi.gov.in/macroindicators?product=nas>
- Access: Interactive React SPA over api.mospi.gov.in; browser downloads. For pipelines use the API. Requires: none. Formats: html.
- Latest: 2026-08-31 - Cited by Q1 2026-27 press note as location of detailed GDP data. Frequency: With each GDP release. Lag: Same as press releases.
- Coverage: 2011-12 to Q1 2026-27 (Same as NAS API). Basis: 2022-23 and 2011-12 bases.
- Key series: nas - Same indicator set as NAS API [Rs crore].
- SAM use: cross-check only.
- Quirks: SPA; not scrapable. Bundle main.ca0c5168.js calls https://api.mospi.gov.in/api.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**GDP press notes: Advance, Provisional and Quarterly estimates (new series)** (`mospi_gdp_press_releases`, corrected)

- Publisher: NSO, MoSPI (also on PIB). Landing: <https://www.mospi.gov.in/api/latest-release/get-web-latest-release-list>
- Access: PDF press notes; release list via public JSON endpoint POST /api/latest-release/get-web-latest-release-list with body {"page_no":N} (other keys silently return page 1). Original 27 Feb URL (…_27022026.pdf without -F) returns 403; use the -F file. PIB pages block non-browser clients; prefer MoSPI copies. Requires: none. Formats: pdf.
- Latest: 2026-08-31 - Q1 2026-27 GDP estimates. Next: Q2 on 2026-11-30; FAE 2026-27 on 2027-01-07; SAE + Q3 + FRE 2025-26 + Final 2024-25 on 2027-02-26. Frequency: Quarterly (end-Feb, ~7 Jun, end-Aug, end-Nov) + FAE (~7 Jan) + SAE (~26 Feb). Lag: ~2 months after quarter end. PE rule: 7 June or previous working day (from 12 May 2026 notice); 2026 PE released 5 June 2026.
- Coverage: Q1 2022-23 to Q1 2026-27 (New base only). Basis: 2022-23; current and constant.
- Key series: quarterly - GVA by 8 sectors, GDP by expenditure (current/constant) [Rs crore]; annual AE/PE - GDP, GVA by activity, NNI, GNDI, per-capita income [Rs crore].
- SAM use: time-series layer; nowcast of years after the SAM reference year.
- Quirks: Embargo lines on every page. Large quarterly discrepancies (Q1 2026-27 current -69,478 cr; constant -1,06,005 cr). Vintages: 2025-26 GDP 3,45,47,157 (27 Feb SAE) -> 3,46,35,638 (5 Jun PE) -> 3,45,36,796 (31 Aug NAS 2026). The 1 Sep 2026 FAQ: 'The GDP base year continues to be 2022-23'.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**NAS 2024 and NAS 2025 (old base 2011-12) incl. sequences of accounts; old-base long series** (`mospi_nas_old_base_2011_12`, verified)

- Publisher: NSO, MoSPI. Landing: <https://www.mospi.gov.in/publications-reports/innerpage/434>
- Access: Bulk XLSX per statement; NAS 2024 also as all-statements workbook. Requires: none. Formats: xlsx.
- Latest: 2025-06-26 - NAS 2025 (2011-12 to 2023-24) published 2025-06-26; NAS 2024 (last edition with full sequences of accounts, 2011-12 to 2022-23) published 2024-06-05. Old-base annual/quarterly constant-price series pub 2711 (2025-08-29). Frequency: Superseded as headline series on 2026-02-27. Lag: n/a (superseded).
- Coverage: 2011-12 to 2023-24 (Sequences of accounts 2011-12 to 2022-23 (NAS 2024 only). CMS publication dates; file Last-Modified 16 May 2025 is a migration stamp). Basis: 2011-12; current and constant 2011-12.
- Key series: 1.15 - Sequence of accounts - total economy (SNA codes P1, P2, B1g, D1, D2, D21, D29...) [Rs crore]; 2.0-2.2 / 3.0-3.2 - NFC and FC sequences of accounts [Rs crore]; 4.0 / 5.0 / 6.0 - General government, household, RoW sequences of accounts [Rs crore].
- SAM use: pre-2022-23 time series; structure for institutional transfers (D4, D5, D6, D7) where the new base lacks detail - label estimated.
- Quirks: Level break vs new base: 2022-23 GDP old 2,68,90,473 vs new 2,61,17,627 cr at the rebasing (-2.9%, MoSPI 27 Feb 2026 press note); NAS 2026 later revised new-base 2022-23 to 2,61,77,001 (+59,374, a vintage revision, not a rebasing effect). Old series has large explicit discrepancy (2022-23 -4,74,817 cr). NAS 2025 sequence files return 404; NAS2025_All_Statements.xlsx does not exist.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**Sources and Methods for Compilation of National Accounts Statistics (base 2022-23)** (`mospi_nas_sources_methods_2026`, verified)

- Publisher: NSO, MoSPI. Landing: <https://www.mospi.gov.in/publications-reports/innerpage/2865>
- Access: PDF. Requires: none. Formats: pdf.
- Latest: 2026-09-21 - Released (3.8 MB PDF). Frequency: Once per base revision. Lag: ~7 months after new series.
- Coverage: 2022-23 (Methodology for base 2022-23). Basis: 2022-23.
- Key series: s.23.4 - Discrepancy set to 0 at current prices via SUT integration; headline GCF = GFCF+CIS+valuables [text]; s.26.6 / Table 26.1 - GCF by flow of funds vs commodity flow differ; difference = errors and omissions; old vs new saving by sector 2022-23 [text]; s.30.7 - Intended NAS chapter structure incl. sequences of accounts (not actually published) [text].
- SAM use: methodology and estimation ratios for gap filling.
- Quirks: Describes chapters 2-6 with sequences of accounts that NAS 2026 does not contain. s.30.10 gives no back-series date.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**MoSPI Advance Release Calendar 2026-27 and PE release-date notice** (`mospi_advance_release_calendar`, verified)

- Publisher: MoSPI. Landing: <https://www.mospi.gov.in/api/documents/get-latest-release-calender>
- Access: PDF (calendar located via GET /api/documents/get-latest-release-calender). Requires: none. Formats: pdf.
- Latest: 2026-09-01 - ARC 2026-27 updated till August 2026 (created 2026-09-01); calendar-change note 12 May 2026. Frequency: Updated periodically. Lag: n/a.
- Coverage: 2026-04 to 2027-03 (All NSO releases in FY 2026-27). Basis: n/a.
- Key series: ARC - Release dates: ASI 2024-25 results 29 Sep 2026; Q2 GDP 30 Nov 2026; FAE 7 Jan 2027; SAE + FRE 2025-26 + FE 2024-25 on 26 Feb 2027; PLFS AR CY2026 25 Mar 2027; ASUSE 2026 21 Mar 2027 [date].
- SAM use: reference-year choice; Phase 6 scheduler.
- Quirks: An older ARC (05.02.2026) also exists; use the 'updated till August 2026' version.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**State GSDP/GSVA (MoSPI API account_code=2; new-base compilation in progress)** (`mospi_state_gsdp`, verified)

- Publisher: MoSPI NAD with State DESs. Landing: <https://api.mospi.gov.in/api/nas/getNasIndicatorList?account_code=2>
- Access: API (JSON) for old base; new-base GSDP not yet published. Requires: none. Formats: json, pdf.
- Latest: n/a - API holds base 2011-12 only. New-base GSDP 2022-23 to 2024-25 under NAD-DES joint discussion (20 May - 19 Jun 2026); uniform GSVA guideline (base 2022-23) released 7 May 2026. Frequency: Annual. Lag: unknown for new base.
- Coverage: 2011-12 (Old base only in API). Basis: 2011-12 (API); 2022-23 forthcoming.
- Key series: indicator_code 23 - Gross State Domestic Product [Rs crore].
- SAM use: State-level context; Centre/States split cross-check.
- Quirks: All state fiscal %GSDP ratios currently use old-base GSDP.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).
- Not confirmed: release_lag (new base not yet released).

**Reports of Sub-Committees for the 2022-23 series (new data sources, rates and ratios; methodological improvements)** (`mospi_nas_subcommittee_reports`, verified)

- Publisher: MoSPI. Landing: <https://www.mospi.gov.in/publications-reports/innerpage/2795>
- Access: PDF. Requires: none. Formats: pdf.
- Latest: 2026-02-24 - SC-I report pub 2795 (24 Feb 2026); methodological sub-committee report (18 Feb 2026). Frequency: One-off. Lag: n/a.
- Coverage: 2022-23. Basis: 2022-23.
- Key series: rates_ratios - Official rates and ratios used in the new series [various].
- SAM use: justification for labelled estimation of unpublished SAM cells.
- Quirks: Report body not opened by verifier.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**OGD Platform India (data.gov.in) mirrors: MoSPI National Accounts, 'Economic Classification of the Central Budget', Commerce trade-by-partner, RBI 'Overall BoP'** (`data_gov_in_ogd`, unverified)

- Publisher: NIC / MeitY on behalf of ministries. Landing: <https://www.data.gov.in/>
- Access: JS-rendered catalog; resource API at api.data.gov.in needs a free API key (not tested; api.data.gov.in returned 503 on one probe). robots.txt 'User-agent: * Disallow: /' - do not crawl web pages; use API with key only. Requires: api_key. Formats: csv, xls, json.
- Latest: unknown - unverified: catalog pages timed out or returned 403. Frequency: unverified. Lag: unverified.
- Coverage: n/a (unverified). Basis: unverified.
- Key series: catalogs - National Accounts Key Aggregates; Quarterly GDP; Economic Classification of the Central Budget; Country-wise exports by principal commodity; Overall BoP (titles from search only) [various].
- SAM use: possible GODL-licensed copies only; prefer originals.
- Quirks: Footer currently says 'This is a sandbox environment created for testing and demonstration purposes only. The content, data, and functionality may be incomplete or inaccurate.' Do not rely on it until verified.
- Licence: GODL-India per site footer ('licensed under the Government Open Data License - India'); /Godl page is an SPA shell, text not rendered.

### 3.2 MoSPI Supply-Use / Input-Output, ASI, IIP, prices, energy, classifications (`mospi_io`)

**Supply and Use Tables 2022-23 and 2023-24 (base 2022-23)** (`mospi_sut_2022base`, corrected)

- Publisher: National Accounts Division, NSO, MoSPI. Landing: <https://www.mospi.gov.in/publications-reports/innerpage/847>
- Access: Bulk download XLSX; file list via POST /api/publications-reports/get-web-chapter-data {publication_id:'847'}. Not on api.mospi.gov.in. Plain GETs returned 200 on 2026-09-29 (verifier and lead); the finder's claim that Sec-Fetch browser headers are required was not reproducible. PIB copy of the PR blocks non-browser clients; use the MoSPI-hosted PR PDF. Requires: none. Formats: xlsx, pdf.
- Latest: 2026-08-31 - SUT 2022-23 and 2023-24 first released 2026-05-15; revised files (suffix _(1)) uploaded 2026-08-31 with NAS 2026. Frequency: Annual, integrated with NAS Final Estimates; revised when NAS is revised. Lag: ~26 months after FY 2023-24 (old series lag ~4 years).
- Coverage: 2022-23 to 2023-24 (New base only; a 2024-25 SUT cannot precede FE 2024-25 (due 2027-02-26) - inference). Basis: Base 2022-23; current prices only; Rs crore ('Values in Rs. Crore' in row 1 of every sheet). Supply at basic prices with valuation columns; Use at purchasers' prices.
- Key series: Supply - 155 products x 67 industries output at basic prices + imports, CIF adj, import duty, product taxes, subsidies, TTM, supply at PP [Rs crore]; Use - 155 x 67 intermediate consumption at PP + total IC + PFCE, GFCE, GFCF, CIS, valuables, exports [Rs crore]; Use VA block - GVA, production taxes less subsidies, CFC, CE, OS incl. mixed income, GVA (income) by 67 industries [Rs crore]; 2022-23 totals - CoE 86,53,669; OS/MI 1,16,54,812; CFC 35,84,380; GVA 2,38,23,136; GDP 2,61,77,001 (both sides) [Rs crore].
- SAM use: activity x commodity (make); commodity x activity intermediate use; commodity x final demand; imports by commodity; product taxes, subsidies, import duty by commodity; trade & transport margins; factor payments and net production taxes by activity.
- Quirks: (1) Classification contradiction inside MoSPI: PR (15 May 2026) says 'adoption of updated classifications like NIC 2025, COICOP 2018'; the methodological note s.5.2 says 'NIC 2008 and NPCMS 2011 (Revised)/ NPCSS have been used'. Treat SUT as NIC 2008-based. (2) Files replaced on 2026-08-31 without internal version stamp (announced in NAS 2026 PR para 9); May PR totals no longer match (supply at PP 2022-23 627.18 vs 628.01 lakh crore; 2023-24 669.88 vs 671.79). Hash every download. (3) No valuation matrices by use cell, no import-use matrix, single product-tax vector (no CGST/SGST/IGST split). (4) Blank cells stored as ' ' strings, trailing spaces in labels. (5) OS row includes mixed income. (6) Zero statistical discrepancy for Final years.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**Supply and Use Tables 2011-12 to 2021-22 (old base 2011-12)** (`mospi_sut_2011base`, verified)

- Publisher: National Accounts Division, NSO, MoSPI. Landing: <https://www.mospi.gov.in/publications-reports/innerpage/847>
- Access: Bulk XLSX, one per year. Requires: none. Formats: xlsx, pdf.
- Latest: 2025-12-11 - SUT 2020-21 and 2021-22 uploaded 2025-12-11 (note 2025-11-26). Frequency: Annual (discontinued with rebasing). Lag: ~3.7 years.
- Coverage: 2011-12 to 2021-22 (11 years). Basis: Base 2011-12, current prices; units vary (Rs lakh e.g. 2011-12, 2015-16; Rs crore 2021-22).
- Key series: SUT - 140 products x 66 industries with valuation columns and VA rows [Rs lakh / Rs crore].
- SAM use: historical IO structure (needs bridging to new base).
- Quirks: Not consistent with 2022-23-base NAS. Layouts, sheet names and units change by year. 2011-12 file name misspelt 'balaced'.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**Input-Output Transactions Table 2007-08 (last official IOTT)** (`mospi_iott_2007`, corrected)

- Publisher: CSO, MoSPI. Landing: <https://www.mospi.gov.in/sites/default/files/reports_and_publication/cso_national_accounts/input_output_transactions_table/2007_08/Binder1.pdf>
- Access: PDF (16.2 MB). No landing page on the current MoSPI site: the old path /publication/input-output-transactions-table-2007-08 returns the generic 2,644-byte SPA shell (as does any nonexistent path), and the publications API has no IOTT record. The direct PDF is the landing. Requires: none. Formats: pdf.
- Latest: 2012 - IOTT 2007-08, published 2012. Frequency: Discontinued (MoSPI publishes SUTs only). Lag: n/a.
- Coverage: 2007-08 to 2007-08. Basis: 2004-05 NAS series (NAS 2011); factor cost.
- Key series: Matrix-1 - 130 commodity x industry absorption matrix [Rs lakh]; Matrix-2 - Make matrix [Rs lakh]; Matrix-6 - 130 commodity x commodity IO matrix [Rs lakh]; Matrix-7 - Leontief inverse [ratio].
- SAM use: none for reference year; historical cross-check.
- Quirks: No official IOTT for any later year; symmetric IOT must be derived from the SUT (estimated).
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**Input Output Transactions Table: India 2015-16 (derived from SUT)** (`csep_iott_2015`, verified)

- Publisher: Brookings India / CSEP (Chadha, Saluja, Sivamani). Landing: <https://csep.org/wp-content/uploads/2020/01/Input-Output-Transactions-Table-India-2015-16.pdf>
- Access: PDF. Requires: none. Formats: pdf.
- Latest: 2020-01 - Draft for comments, January 2020. Frequency: One-off. Lag: n/a.
- Coverage: 2015-16 to 2015-16. Basis: 2011-12 NAS base; factor cost with NIT and TTM rows.
- Key series: IOTT - 131-sector symmetric IOT from SUT 2015-16 (140x66) [Rs lakh].
- SAM use: methodological reference / multiplier cross-check.
- Quirks: Third-party draft; PDF only.
- Licence: no explicit licence found.

**Annual Survey of Industries (ASI)** (`mospi_asi`, corrected)

- Publisher: NSO (Industrial Statistics Wing / FOD), MoSPI. Landing: <https://www.mospi.gov.in/uploads/latestReleases/latest_release_1759229537293_dfab5cc6-1531-4944-a17c-06ae83172ef9_PressNote_ASI_2023-24_publication_English-F.pdf>
- Access: Aggregates via keyless API (/api/asi/getASIData) and PDF volumes; unit data on microdata.gov.in after free registration and login. Registration needed only for unit-level data; aggregates need none. Requires: registration. Formats: json, csv, pdf.
- Latest: 2025-09-30 - ASI 2023-24 (results 2025-08-27; publications and unit data 2025-09-30). ASI 2024-25 results scheduled 2026-09-29 (ARC 2026-27): Not released as of 15:19 IST on 29 Sep 2026 (MoSPI release feed and the ASI API still end at 2023-24); due later on 29 Sep per the ARC. Frequency: Annual. Lag: ~17-18 months.
- Coverage: 2008-09 to 2023-24 (API 2008-09 to 2023-24 (NIC 2008); microdata back to 1970s-80s). Basis: Current prices; NIC 2008; products NPCMS 2011 (Revised).
- Key series: 57 API indicators - Factories, fixed/invested capital, total input, total output, GVA, emoluments/wages, employment, interest, rent, depreciation [Rs lakh / number]; Vol II - Materials consumed and products by NPC-MS 7-digit (e-publication) [Rs lakh].
- SAM use: manufacturing input structure; CoE vs OS for factory sector; energy use by industry; state split of manufacturing.
- Quirks: IIP uses NIC 2025 while ASI uses NIC 2008 (concordance needed). ASI 2024-25 schedule/manual published 2026-02-09; its NIC version not checked.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**Index of Industrial Production (base 2022-23)** (`mospi_iip_2022base`, corrected)

- Publisher: NSO, MoSPI. Landing: <https://esankhyiki.mospi.gov.in/macroindicators?product=iip>
- Access: Keyless API (JSON/CSV) + PDF press releases. Requires: none. Formats: json, csv, pdf.
- Latest: 2026-09-28 - August 2026 Quick Estimate: index 123.3, growth 8.0%. Frequency: Monthly (~28th of following month). Lag: ~28 days.
- Coverage: 2023-04 to 2026-08 (Old series (2011-12, 2004-05, 1993-94) via same API; sector linking factors). Basis: 2022-23=100 volume index; NIC 2025; 463 item groups.
- Key series: General/Sectoral - General, mining, manufacturing, electricity & gas, water supply/sewerage [index]; NIC 2-digit - Manufacturing by NIC 2-digit [index]; Use-based - 6 use-based categories [index].
- SAM use: time-series extrapolation of industrial volumes.
- Quirks: Linking factors only at sector level (General 1.3834); water/sewerage has none. GitHub swagger omits base 2022-23 but live API accepts it. '1,042 products' figure is unverified.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**Consumer Price Index (Rural/Urban/Combined), base 2024=100** (`mospi_cpi_2024base`, verified)

- Publisher: NSO, MoSPI. Landing: <https://esankhyiki.mospi.gov.in/macroindicators?product=cpi>
- Access: Keyless API: /api/cpi/getCPIData (base 2024; limit>=10); getCPIIndex/getItemIndex for bases 2012/2010. Requires: none. Formats: json, csv, pdf.
- Latest: 2026-09-14 - August 2026: Combined 108.74, inflation 4.82%. Frequency: Monthly (~12th). Lag: ~12-14 days.
- Coverage: 2025-01 to 2026-08 (General-index back series Jan 2013-Dec 2024 via linking factors (Combined 0.5267); 2012-base to Dec 2025). Basis: 2024=100; weights HCES 2023-24; COICOP 2018, 358 items.
- Key series: CPI - General R/U/C, CFPI, division to item indices, all-India and state [index].
- SAM use: household consumption deflators.
- Quirks: getCPIIndex returns 'No Data Found' for base 2024.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**WPI and Producer Price Indices (Output PPI, trial Input PPI, Service PPIs), base 2022-23** (`oea_wpi_ppi_2022base`, verified)

- Publisher: Office of the Economic Adviser, DPIIT, Ministry of Commerce & Industry. Landing: <https://eaindustry.nic.in/download_data_2223.asp>
- Access: XLSX bulk download (file names carry yyyymm stamp; scrape download_data_2223.asp); WPI also via MoSPI API. Requires: none. Formats: xlsx, pdf, json.
- Latest: 2026-09-14 - August 2026 provisional: WPI 110.8, inflation 9.92%; SPPI Q1 2026-27. Frequency: WPI/OPPI/IPPI monthly (14th); SPPI quarterly. Lag: ~14 days provisional; final after 2 months.
- Coverage: 2023-04 to 2026-08 (Trial IPPI from Mar 2026; SPPI from Q1 2023-24 (Air passenger from FY 2025-26)). Basis: 2022-23=100; WPI/OPPI/SPPI basic prices; IPPI purchasers' prices; OPPI/IPPI weights from SUT 2022-23.
- Key series: WPI - All commodities, major groups, 957 items [index]; OPPI - Output PPI by commodity (162 rows) [index]; IPPI - Trial input PPI, manufacturing (24 rows) [index]; SPPI - Banking, securities, insurance, pension, railways, air passenger, telecom [index].
- SAM use: producer price deflators by product; input cost deflators for ABM.
- Quirks: WPI to be discontinued 5 years after 15 Jun 2026. Crude petroleum & natural gas moved to Fuel & Power. Linking factor All Commodities 1.53.
- Licence: no explicit licence found.

**Energy Statistics India 2026 (energy balance, physical energy SUT)** (`mospi_energy_statistics`, corrected)

- Publisher: NSO, MoSPI. Landing: <https://www.mospi.gov.in/publications-reports/innerpage/2817>
- Access: PDF publication (24 files); energy balance via keyless API (requires use_of_energy_balance_code). Requires: none. Formats: pdf, json.
- Latest: 2026-03-30 - Energy Statistics India 2026 (33rd edition), covers FY 2024-25 (TPES 9,32,816 KToE). Frequency: Annual (~March). Lag: ~12 months.
- Coverage: 2012-13 to 2024-25 (API 2012-13 to 2023-24; book to 2024-25. Expert Committee on Energy Statistics report (pub 2848, 2026-07-07) may change future methodology). Basis: Physical units (KToE, PJ, GWh).
- Key series: Energy balance - Commodity x supply/end-use sector [KToE, PJ]; Ch 9 - Physical Supply and Use Tables for energy 2023-24 (Tables 9.2A/B) and 2024-25(P) (9.3A/B); physical asset accounts [PJ].
- SAM use: physical energy satellite account; energy commodity row split.
- Quirks: API lags book by a year; API HTTP 500 with leaked Postgres error if a required parameter is missing; filesize metadata unreliable. No monetary energy SUT.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**eSankhyiki open API (api.mospi.gov.in) and MCP server** (`mospi_esankhyiki_api`, corrected)

- Publisher: MoSPI (NSO); code on GitHub nso-india. Landing: <https://api.mospi.gov.in/>
- Access: REST GET with query params; Format=JSON (CSV partly broken). Swagger declares bearerAuth but unauthenticated calls return 200. MCP server mcp.mospi.gov.in (405 to plain GET). Access terms may change (bearer auth declared). Requires: none. Formats: json, csv.
- Latest: 2026-09-28 - Served Aug-2026 IIP/CPI/WPI on 2026-09-29; repos pushed 2026-09-28. Frequency: Follows each dataset. Lag: Same day as releases (Energy lags).
- Coverage: n/a (PLFS, CPI, IIP, ASI, NAS, WPI, Energy, ISP, HCES, ASUSE, NSS, TUS (28 swagger specs)). Basis: Per dataset.
- Key series: /api/hces/getHcesRecords - HCES MPCE by fractile/item category (indicator_code required) [Rs]; /api/plfs/getData - PLFS indicators 1-8 (LFPR, WPR, UR, worker distribution, earnings); needs year_type_code [% / Rs]; /api/asuse/getAsuseRecords - ASUSE indicators incl. quarterly 2026 [various]; /api/isp/getISPRecords - Index of Services Production (trial, base 2024-25) [index].
- SAM use: pipeline access layer for time series.
- Quirks: HCES call without indicator_code hangs (HTTP 000 after 120 s). PLFS 'annual' earnings return four quarterly CWS values. Some swagger YAMLs stale. Default page size 10.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**Index of Services Production (trial, base 2024-25)** (`mospi_isp_2024base`, verified)

- Publisher: NSO, MoSPI. Landing: <https://api.mospi.gov.in/api/isp/getISPRecords>
- Access: Keyless API (JSON). Requires: none. Formats: json.
- Latest: 2026-08-31 - First release of sub-sectoral trial ISP 2026-07-14; June 2026 data released 2026-08-31. Frequency: Monthly. Lag: ~2 months.
- Coverage: 2024-25 to 2026-06 (Trial index). Basis: 2024-25=100.
- Key series: ISP - Services production index by broad sub-sector (wholesale, retail, repair, ...) [index].
- SAM use: time-series extrapolation of service rows.
- Quirks: Trial series; base differs from NAS base.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**NIC 2025 (with NIC 2008 concordance) and NPC-MS 2011 (Revised)** (`mospi_classifications`, corrected)

- Publisher: MoSPI. Landing: <https://www.mospi.gov.in/uploads/latestReleases/latest_release_1763453965588_95ca7bee-f39a-4568-a061-bcfb9a35cdd6_Press_Note_NIC_2025.pdf>
- Access: PDF (concordance tables inside PDF). Requires: none. Formats: pdf.
- Latest: 2025-11-18 - NIC 2025 released 2025-11-18. Frequency: Irregular. Lag: n/a.
- Coverage: n/a. Basis: n/a.
- Key series: NIC2025-NIC2008 - 4-digit concordance (PDF page 257 of 323; printed pp. 239-291) [code]; NPC-MS 2011 Rev - National Product Classification for Manufacturing Sector (goods only, Dec 2015; no HS concordance) [code].
- SAM use: map IIP (NIC 2025) to SUT/ASI (NIC 2008); map SUT products to trade codes.
- Quirks: No machine-readable SUT product/industry concordance published; NPCSS (services) not found anywhere.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**Index of Eight Core Industries (base 2022-23; now 9 industries incl. iron ore)** (`oea_ici_2022base`, corrected)

- Publisher: Office of the Economic Adviser, DPIIT. Landing: <https://eaindustry.nic.in/ici_download_data.asp>
- Access: XLSX + PDF press release. Requires: none. Formats: xlsx, pdf.
- Latest: 2026-09-21 - August 2026 provisional (4.8% YoY). Frequency: Monthly. Lag: ~20 days.
- Coverage: 2026-08 (Old series file Core_Industries_2011_12_20260720.xlsx). Basis: 2022-23=100.
- Key series: ICI - Coal 5.596, natural gas 3.841, crude 7.43, refinery 22.572, fertilizers 2.731, steel 17.584, cement 4.41, electricity 30.932, iron ore 4.905 (weights) [index].
- SAM use: high-frequency volume indicator.
- Quirks: File names carry date stamps.
- Licence: no explicit licence found.

### 3.3 Household surveys (HCES, PLFS, ASUSE, AIDIS, others) (`mospi_households`)

**Household Consumption Expenditure Survey 2023-24 (NSS Report 592): report, factsheet, Excel detailed tables** (`mospi_hces_2023_24`, verified)

- Publisher: NSO, MoSPI. Landing: <https://www.mospi.gov.in/sites/default/files/publication_reports/Final_Report_HCES_2023-24L.pdf>
- Access: Direct download of PDF report and Excel detailed tables (Appendix A, hyperlinked from the PDF); also via MoSPI API. Requires: none. Formats: pdf, xlsx.
- Latest: 2025-01-30 - Detailed report + Excel tables + unit data released 30 Jan 2025 (factsheet 27 Dec 2024); survey Aug 2023-Jul 2024. Frequency: Irregular (2011-12, then 2022-23 and 2023-24). No round in ARC 2026-27; future round disputed (see quirks). Lag: ~6 months after fieldwork end.
- Coverage: 2023-08 to 2024-07 (All States/UTs; 2,61,953 households). Basis: Current prices of survey year (also MPCE at 2011-12 prices); independent of NAS base.
- Key series: A2 - Households/persons and average MPCE by 12 MPCE fractile classes x State x rural/urban [Rs/person/30 days]; A6 - Value of ~30 food/non-food groups x 12 fractiles x State x sector [Rs/person/30 days]; A10F - Item-level quantity and value x 12 fractiles, All-India; free-item quantities given by fractile, values suppressed ('##') [qty, Rs]; A10S / A10SW - Item-level by State; with imputation of free PDS/scheme items [Rs]; MPCE - Rural 4,122 / Urban 6,996 (without imputation); 4,247 / 7,078 with imputation [Rs/person/30 days].
- SAM use: household consumption shares by commodity (rural/urban x quintile); in-kind transfers (free items); ABM household heterogeneity.
- Quirks: HCES aggregate ~44% of NAS PFCE 2023-24 (per-capita ~51%; lead-agent computation, estimated); HCES population 1,217.6 mn vs ~1,395 mn NAS-implied. Use for shares only. Imputed free-item values not cross-classified by fractile (report s.3.1.4); free health (PM-JAY) and education not imputed; owner-occupied rent excluded. Quintiles must be built from 12 fractile classes. 'No further round' is DISPUTED: finder says none scheduled; a press snippet (not opened) quoted the MoSPI Secretary saying HCES would be repeated in about 3 years.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**Household Consumption Expenditure Survey 2022-23 (NSS Report 591)** (`mospi_hces_2022_23`, verified)

- Publisher: NSO, MoSPI. Landing: <https://www.mospi.gov.in/sites/default/files/publication_reports/Report_591_HCES_2022-23New.pdf>
- Access: Direct download PDF + Excel. Requires: none. Formats: pdf, xlsx.
- Latest: 2024-06 - Factsheet Feb 2024; report + unit data June 2024. Frequency: One-off (paired with 2023-24). Lag: ~11 months.
- Coverage: 2022-08 to 2023-07. Basis: Current prices of survey year.
- Key series: A1-A10SW - Same Appendix A table set as 2023-24 [Rs/person/30 days].
- SAM use: household consumption structure for a 2022-23 SAM; cross-check of 2023-24 shares.
- Quirks: Excel file names contain spaces (URL-encode).
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**HCES 2022-23 and 2023-24 unit-level data (microdata.gov.in NADA)** (`mospi_hces_unit_data`, corrected)

- Publisher: MoSPI. Landing: <https://microdata.gov.in/NADA/index.php/catalog/237>
- Access: Free registration + e-mail activation + online application + Data Access Agreement, then zip/rar download. Login required even to see the download page. Owner must register personally. Requires: registration. Formats: csv, txt, xlsx.
- Latest: 2025-01-30 - HCES 2023-24 unit data (catalog 237, DDI-IND-MOSPI-NSS-HCES23-24; created 22 Apr 2025, last modified 13 Apr 2026); catalog 224 last modified 23 Jul 2026. Frequency: With each round. Lag: ~6 months.
- Coverage: 2022-23 to 2023-24. Basis: Current prices.
- Key series: LEVEL-01..15 - Household characteristics, food, consumables & services, durables, free items [various]; Imputation_Rate.xlsx - Imputation rates for free items [Rs/unit]; Rider - Rider for users: do not use auxiliary household variables for estimation; do not estimate below State/UT level [text].
- SAM use: quintile x commodity consumption incl. imputed free items; ABM synthetic population.
- Quirks: HCES collects NO household income; do not use as income proxy. Files by section need merging on household ID. NADA 'created on' dates are portal-entry dates.
- Licence: GSDD 2026 Category B (registered access): free for non-commercial use incl. research; priced for commercial use; Data Access Agreement.

**Periodic Labour Force Survey - Annual Reports (July-June to 2023-24; calendar year from 2025)** (`mospi_plfs_annual`, verified)

- Publisher: NSO, MoSPI. Landing: <https://www.mospi.gov.in/uploads/latestReleases/latest_release_1774607827733_3e8964a9-268b-4cc9-ad65-cfc8a9e32f08_Press_note_AR_PLFS_2025_23032025_V2.1_26032026_final.pdf>
- Access: PDF reports; MoSPI API for headline indicators. Requires: none. Formats: pdf.
- Latest: 2026-03-27 - PLFS Annual Report 2025 (Jan-Dec 2025), press note dated 27 Mar 2026; next CY 2026 report 25 Mar 2027. Frequency: Annual. Lag: ~3 months.
- Coverage: 2017-18 to 2025 (Ag-years 2017-18..2023-24; CY 2024 key indicators; AR 2025 also presents CY 2022-2024 from unit data. No July 2024-June 2025 report). Basis: Nominal Rs.
- Key series: earnings - Regular wage (by NCO, State, sector); casual wage per day by NIC-2008 section (Table 51); self-employment earnings [Rs/month, Rs/day]; 2025 - Regular wage male 24,217, female 18,353; self-employed male 17,914, female 6,374; casual male 455/day, female 315/day [Rs].
- SAM use: labour income split wage vs self-employment; labour income by rural/urban; employment by sector.
- Quirks: Design break Jan 2025 (rotational panel, 2.72 lakh households) - 'may not be strictly comparable'. Regular wages not published by industry. Full AR 2025 PDF not located.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**PLFS Monthly and Quarterly Bulletins** (`mospi_plfs_bulletins`, corrected)

- Publisher: NSO, MoSPI. Landing: <https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2310427&reg=48&lang=1>
- Access: PDF bulletins; API frequency_code 2 (quarterly), 3 (monthly). Requires: none. Formats: pdf, json.
- Latest: 2026-09-15 - Monthly bulletin August 2026 (LFPR 55.6%), posted 15 Sep 2026; quarterly Apr-Jun 2026 available. Frequency: Monthly (from Jan 2025) and quarterly. Lag: ~2-6 weeks.
- Coverage: 2018 to 2026-08 (Pre-2025 quarterly bulletins urban only). Basis: Rates; nominal earnings.
- Key series: LFPR/WPR/UR - CWS monthly/quarterly [%].
- SAM use: time series / nowcast of employment.
- Quirks: Monthly series starts 2025.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**PLFS unit-level data** (`mospi_plfs_unit_data`, verified)

- Publisher: MoSPI (microdata.gov.in). Landing: <https://microdata.gov.in/NADA/index.php/catalog/PLFS>
- Access: Registration + application; zip download. Requires: registration. Formats: txt, csv, xlsx.
- Latest: 2026-03-27 - CY 2025 (catalog 284, created 27 Mar 2026); monthly Apr-Dec 2025 (291) and quarterly (292) created 5 May 2026. Frequency: Annual + monthly/quarterly from 2025. Lag: ~3 months.
- Coverage: 2017-18 to 2025. Basis: Nominal Rs.
- Key series: person-level - CWS earnings with NIC-2008 industry, NCO, rural/urban, State, household MPCE [Rs].
- SAM use: labour income by SAM sector x household class; FY construction from quarterly records.
- Quirks: Design break 2025; first-visit vs revisit schedules; weights need care across rounds.
- Licence: GSDD 2026 Category B (registered access): free for non-commercial use incl. research; priced for commercial use; Data Access Agreement.

**Annual Survey of Unincorporated Sector Enterprises (ASUSE)** (`mospi_asuse`, corrected)

- Publisher: NSO, MoSPI. Landing: <https://www.mospi.gov.in/uploads/latestReleases/latest_release_1774347321466_c16ddf22-bfff-4097-88a7-b3134e464d51_Press_Note_ASUSE_2025_English.pdf>
- Access: PDF press notes, factsheets and reports; eSankhyiki API (annual and quarterly QBUSE). Unit data is a separate entry (mospi_asuse_unit_data). Aggregates are open. Unit-level data needs microdata.gov.in registration: see mospi_asuse_unit_data. Requires: none. Formats: pdf, json.
- Latest: 2026-09-10 - District-level press note 'insights from ASUSE 2025' on 10 Sep 2026 (latest ASUSE item in the MoSPI release feed). ASUSE 2025 (Jan-Dec 2025) press note 24 Mar 2026; million-plus cities report 29 Jun 2026; QBUSE Jan-Mar 2026 on 21 May 2026 and Apr-Jun 2026 on 21 Aug 2026. Frequency: Annual (calendar year from 2025) + quarterly bulletins from 2026. Lag: ~3 months (factsheet).
- Coverage: 2021-22 to 2025 (2022-23 = Oct 22-Sep 23; 2023-24 = Oct 23-Sep 24; gap Oct-Dec 2024). Basis: Current prices.
- Key series: GVA - Market establishments: 15,42,409 (2022-23), 17,97,278 (2023-24), 19,92,577 (2025) [Rs crore]; workers - 10,96,260 / 12,05,998 / 12,80,518 ['00]; emolument - Per hired worker 1,24,842 / 1,41,071 / 1,46,550 [Rs].
- SAM use: unincorporated VA split: emoluments vs mixed income; household-enterprise production account.
- Quirks: Excludes agriculture, construction, LLPs; GVA for market establishments only; shifting reference periods; 2025 design change.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**ASUSE unit-level data (microdata.gov.in NADA): 2025 (catalog 293) and 2023-24 (catalog 238)** (`mospi_asuse_unit_data`, verified)

- Publisher: NSO, MoSPI. Landing: <https://microdata.gov.in/NADA/index.php/catalog/293>
- Access: Free registration + online application + Data Access Agreement, then download. get-microdata page: 'To access data for this study, user must be logged in.' Owner must register personally. Requires: registration. Formats: unit-level files (format not seen before login).
- Latest: 2026-05-06 - ASUSE 2025 (Jan-Dec 2025) unit data, catalog 293 'DDI-IND-NSO-ASUSE-Jan2025-Dec2025', created 6 May 2026, last modified 11 Jun 2026. Catalog 238 (ASUSE 2023-24) last modified 9 Sep 2026. Frequency: Annual (calendar year from 2025). Lag: ~4 months after survey end.
- Coverage: 2023-24 to 2025 (Catalog 222 (2022-23) also listed in SOURCES section 5; not re-checked in the fix pass). Basis: Current prices.
- Key series: unit records - Enterprise-level output, inputs, GVA, workers, emoluments [Rs, number].
- SAM use: unincorporated enterprise production account by activity and rural/urban; split of unincorporated VA into emoluments and mixed income.
- Quirks: Excludes agriculture and construction. 2025 design change and Oct-Dec 2024 gap (see mospi_asuse). NADA 'created on' is a portal-entry date.
- Licence: GSDD 2026 Category B (registered access): free for non-commercial use incl. research; priced for commercial use; Data Access Agreement.
- Not confirmed: formats (files not requested under DECISIONS D1-2).

**All India Debt & Investment Survey, NSS 77th round 2019 (Report 588)** (`mospi_aidis_2019`, verified)

- Publisher: NSO, MoSPI. Landing: <https://mospi.gov.in/sites/default/files/press_release/press_note-AIDIS--240821%20update.pdf>
- Access: PDF press note; report tables via eSankhyiki API /api/nss-77 (AIDIS module, survey_code=1); unit data via microdata portal. Phase 1 check 2026-09-29: the Report 588 PDF could not be located on the current MoSPI site (publications API lists only the latest 250 items; ten plausible /sites/default/files/publication_reports/ names returned 404; NADA catalog 156 related materials hold only schedules and instructions). The press note (HTTP 200) says the report is 'available on the website http://www.mospi.gov.in/'. The report's tables are, however, served by the keyless eSankhyiki API: GET https://api.mospi.gov.in/api/nss-77/getNss77AidisIndicatorList?survey_code=1 (HTTP 200) lists 22 AIDIS indicators, incl. 5 'Average value of assets and amount of cash loan per household by Quintile class of household expenditure', 4 '... by household asset holding class' and 11 '... by asset category'. Use /api/nss-77/getNss77Records with survey_code=1. Requires: none. Formats: pdf, csv.
- Latest: 2021-09-10 - Report 588, press note 10 Sep 2021; stocks as on 30.06.2018. Frequency: ~Decennial (1992, 2003, 2013, 2019); new round in the field Jul 2026-Jun 2027. Lag: ~21 months.
- Coverage: 2018-06-30 to 2018-06-30. Basis: Current prices (2018).
- Key series: assets - Average value of assets per household (rural Rs 15,92,379) by type [Rs]; debt - Incidence and amount of debt by source [Rs].
- SAM use: household balance sheet structure (shares only); ABM wealth priors.
- Quirks: Old; scale shares to RBI household financial accounts. No new results before ~2027-28 (inference).
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**Situation Assessment Survey of Agricultural Households, NSS 77th round (Report 587)** (`mospi_sas_2019`, verified)

- Publisher: NSO, MoSPI. Landing: <https://mospi.gov.in/sites/default/files/publication_reports/Report_587m_0.pdf>
- Access: PDF (60.5 MB); unit data via microdata portal. Requires: none. Formats: pdf, csv.
- Latest: 2021-09-10 - Report 587, 10 Sep 2021. Frequency: ~Decennial; next Jul 2026-Jun 2027. Lag: ~21 months.
- Coverage: 2018-07 to 2019-06. Basis: Current prices.
- Key series: income - Average monthly income per agricultural household by source (wages, crops, livestock, non-farm business, leasing) [Rs/month].
- SAM use: agricultural mixed income vs wages for rural groups.
- Quirks: Agricultural households only; old.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**National Household Income Survey (NHIS) 2026 - first official income survey (not yet available)** (`mospi_nhis_2026`, verified)

- Publisher: NSO, MoSPI. Landing: <https://www.pib.gov.in/PressReleasePage.aspx?PRID=2178574&reg=48&lang=2>
- Access: Not yet released. Requires: none. Formats: n/a (no data released yet).
- Latest: n/a - No data. Fieldwork from April 2026 (PIB 17 Mar 2026 prints 'April 2026 to March 2026', a typo). Frequency: First round. Lag: unknown (mid-2027 per secondary sources, unverified).
- Coverage: 2026-04 to 2027-03 (Planned; sample ~4.5 lakh households per secondary sources (unverified)). Basis: n/a.
- Key series: planned - Household income by source [Rs].
- SAM use: future household income distribution (not usable for 2022-23/2023-24).
- Quirks: Confirms no official household income distribution exists for any past year. MoSPI 23 Jun 2025 note: past income surveys were abandoned.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).
- Not confirmed: release_lag; sample size (secondary sources).

**Time Use Survey 2024** (`mospi_tus_2024`, unverified)

- Publisher: NSO, MoSPI. Landing: <https://microdata.gov.in/NADA/index.php/catalog/236>
- Access: Report PDF; unit data via microdata portal. Requires: registration. Formats: pdf, csv.
- Latest: 2025-04-15 - 'Time Use in India, 2024' reportedly released March 2025; unit data catalog 236 created 15 Apr 2025. Frequency: Irregular (2019, 2024). Lag: ~3 months.
- Coverage: 2024-01 to 2024-12. Basis: n/a.
- Key series: TUS - Time on paid/unpaid activities by gender, rural/urban [minutes/day].
- SAM use: ABM labour-supply calibration (not a SAM cell).
- Quirks: Low priority.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**NSS Survey on Household Social Consumption: Health (Jan-Dec 2025) - unit data** (`nss_health_2025`, verified)

- Publisher: NSO, MoSPI. Landing: <https://microdata.gov.in/NADA/index.php/catalog/290>
- Access: Microdata portal (registration). Requires: registration. Formats: csv.
- Latest: 2026-04-17 - Catalog 290 created 2026-04-17. Frequency: Irregular. Lag: ~4 months.
- Coverage: 2025-01 to 2025-12. Basis: Current prices.
- Key series: OOPE - Household out-of-pocket health expenditure [Rs].
- SAM use: health column of household consumption; government in-kind health transfers.
- Quirks: Report status not checked.
- Licence: GSDD 2026 Category B (registered access): free for non-commercial use incl. research; priced for commercial use; Data Access Agreement.

**NSS Comprehensive Modular Survey: Education, 80th round (Apr-Jun 2025)** (`nss_cms_education_2025`, verified)

- Publisher: NSO, MoSPI. Landing: <https://microdata.gov.in/NADA/index.php/catalog/255>
- Access: Microdata portal (registration). Requires: registration. Formats: csv.
- Latest: 2025-08-26 - CMS Education, NSS 80th round (2025): unit data catalog 255 'DDI-IND-MOSPI-NSS-CMSE80-2025', created 26 Aug 2025 (portal-entry date). Frequency: Irregular. Lag: unknown.
- Coverage: 2025-04 to 2025-06. Basis: Current prices.
- Key series: education - Household expenditure on education (fees, coaching, transport, books) [Rs].
- SAM use: education column of household consumption.
- Quirks: None recorded in Phase 0.
- Licence: GSDD 2026 Category B (registered access): free for non-commercial use incl. research; priced for commercial use; Data Access Agreement.
- Not confirmed: release_lag.

**NSS Domestic Tourism Expenditure Survey, 80th round (Jul 2025-Jun 2026)** (`nss_domestic_tourism_2025_26`, verified)

- Publisher: NSO, MoSPI. Landing: <https://microdata.gov.in/NADA/index.php/catalog/307>
- Access: Microdata portal (registration); press note on MoSPI. Requires: registration. Formats: csv, pdf.
- Latest: 2026-09-23 - Unit data catalog 307 created 2026-09-23; press note listed in MoSPI latest-release feed. Frequency: Irregular. Lag: ~3 months.
- Coverage: 2025-07 to 2026-06. Basis: Current prices.
- Key series: tourism - Trip expenditure by purpose and mode [Rs].
- SAM use: PFCE split into transport, hotels, restaurants.
- Quirks: Very new.
- Licence: GSDD 2026 Category B (registered access): free for non-commercial use incl. research; priced for commercial use; Data Access Agreement.

**CMIE Consumer Pyramids Household Survey (Consumer Pyramids dx)** (`cmie_cphs`, unverified)

- Publisher: Centre for Monitoring Indian Economy (private). Landing: <https://www.cmie.com/kommon/bin/sr.php?kall=wproducts&tabno=7010&prd=cpdx>
- Access: Paid subscription; record-level downloads. Requires: paid. Formats: unverified.
- Latest: unknown - unverified (subscription portal). Frequency: Income monthly; consumption per 4-month wave. Lag: ~1 month (income).
- Coverage: 2016-01. Basis: Nominal.
- Key series: Income Pyramids - Household income by source [Rs].
- SAM use: non-official income-distribution gap filler.
- Quirks: Non-official; sample-representativeness critiques. Price not published.
- Licence: Proprietary subscription; terms not read; redistribution of record-level data presumed prohibited.
- Not confirmed: license (terms not read); latest_release (subscription portal not accessed).

**PRICE ICE 360 Survey 2021 (Wave 3)** (`price_ice360`, verified)

- Publisher: People Research on India's Consumer Economy (PRICE). Landing: <https://www.price360.in/data-center-details.php?url=household-survey-on-indias-consumer-economy-and-citizens-environment-ice-360-survey-2021>
- Access: Login/registration to obtain microdata. Requires: registration. Formats: unverified.
- Latest: 2025-04-08 - Data page created 2024-02-05, last modified 2025-04-08. Frequency: Irregular (2014, 2016, 2021). Lag: ~3 years.
- Coverage: 2020-21 to 2020-21. Basis: Nominal.
- Key series: ICE360 - Household income, consumption, savings, debt, assets [Rs].
- SAM use: cross-check of income distribution.
- Quirks: COVID-year sample; private.
- Licence: No open licence; 'Reproduction is prohibited other than in accordance with the copyright notice'.

**India Human Development Survey (IHDS-I 2004-05, IHDS-II 2011-12; IHDS-3 unreleased)** (`ihds`, unverified)

- Publisher: NCAER and University of Maryland; ICPSR. Landing: <https://ihds.umd.edu/data>
- Access: ICPSR download with free account. Requires: registration. Formats: dta, sav.
- Latest: unknown - IHDS-II (2011-12) public; IHDS-3 not released. Frequency: Panel waves. Lag: n/a.
- Coverage: 2004-05 to 2011-12. Basis: Nominal.
- Key series: income - Household income by source [Rs].
- SAM use: dated structural priors.
- Quirks: Very old; IHDS-3 fieldwork reportedly ended June 2024 (snippet only).
- Licence: ICPSR terms of use (unverified: ICPSR page returned 403).
- Not confirmed: license (ICPSR terms page returned 403); latest_release.date.

**World Inequality Database - India income and wealth distribution** (`wid_india`, corrected)

- Publisher: World Inequality Lab. Landing: <https://wid.world/country/india/>
- Access: Web and bulk download (wid_all_data.zip, 882 MB, Last-Modified 2026-09-09). Requires: none. Formats: csv.
- Latest: 2026-09-09 - Bulk file updated 2026-09-09; latest India data year unverified. Frequency: Annual updates. Lag: unverified.
- Coverage: n/a (Latest year unverified). Basis: Distributional national accounts (model-based).
- Key series: pre-tax income shares - Percentile shares [%].
- SAM use: non-official prior for quintile income split (cross-check only).
- Quirks: Terms-of-use URL returns 404.
- Licence: Creative Commons BY-NC-SA 4.0 (active licence link on India page); a commented-out tooltip says CC BY 4.0.
- Not confirmed: coverage.end (latest India data year); release_lag.

**MoSPI Revised Guidelines for Statistical Data Dissemination (GSDD) 2026** (`mospi_gsdd_2026`, verified)

- Publisher: MoSPI (Gazette of India). Landing: <https://mospi.gov.in/uploads/acts_and_policies/acts_and_policies1778231030122_a1a3ee77-e36d-4895-8da5-b294751cbb1a_272304_(1).pdf>
- Access: PDF (use https; http:// fails). Requires: none. Formats: pdf.
- Latest: 2026-04-27 - Notification dated 27 Apr 2026 (Gazette No. 122, 6 May 2026; digitally signed 7 May 2026), supersedes GSDD 2019. Frequency: Periodic revision. Lag: n/a.
- Coverage: n/a. Basis: n/a.
- Key series: Cat A - Open access, free without registration: National Accounts, CPI, IIP, ASI Vol I, NSS reports/factsheets [policy]; Cat B - Registered access unit data: free non-commercial incl. research; priced commercial; DAA [policy].
- SAM use: licence basis for all MoSPI inputs.
- Quirks: Labelled 'in accordance with NDSAP, 2012' on the microdata portal; does not mention GODL-India. Commercial use defined broadly. DAA also requires compliance with CoS Act 2008, NDSAP 2012 and DPDP Act 2023.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

### 3.4 RBI statistics: DBIE, Handbook, Flow of Funds, banking, NBFC (`rbi_core`)

**Database on Indian Economy (DBIE)** (`rbi_dbie`, corrected)

- Publisher: Reserve Bank of India, DSIM. Landing: <https://data.rbi.org.in/DBIE/>
- Access: Interactive Angular SPA only: SDMX Data Query wizard (Excel/CSV/SDMX-ML) and SAP BusinessObjects reports (guest session). No documented public API (internal session-token gateway CIMS_Gateway_DBIE). Also RBIDATA mobile app. Browser use only. Programmatic/bulk access needs RBI permission. dbie.rbi.org.in presents the data.rbi.org.in certificate (strict clients fail SEC_E_WRONG_PRINCIPAL) and 301-redirects to data.rbi.org.in. dbie.rbihub.in is a third-party-looking front end of unverified status - do not use. Requires: none. Formats: xlsx, csv, sdmx-ml.
- Latest: n/a - Live portal; routes STRBI 2024-25 and annual BSR March 2026. Frequency: Continuous. Lag: Same as underlying releases.
- Coverage: n/a (Decades for most series (BoP from 1990-91)). Basis: Per series.
- Key series: SDMX data query - Time series elements (count unverified) [various]; Reports - STRBI, detailed BSR-1/BSR-2, HBS online, Statistics > External Sector > BoP [various].
- SAM use: financial sector balance sheets; bank credit by sector; deposits by institutional sector; RoW time series.
- Quirks: BOE guest sessions reportedly rationed (unverified).
- Licence: Archived DBIE disclaimer (2023): 'Reproduction is permitted provided an acknowledgement of the primary source is made.' Current SPA disclaimer unverified. RBI website Disclaimer (no caching/deep links without permission) applies.
- Not confirmed: license (current DBIE disclaimer not read; archived 2023 text used); latest_release.date.

**Handbook of Statistics on the Indian Economy 2025-26** (`rbi_hbs`, verified)

- Publisher: Reserve Bank of India, DSIM. Landing: <https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook%20of%20Statistics%20on%20Indian%20Economy>
- Access: Per-table XLSX/PDF on rbidocs (hashed URLs - scrape listing); HTML tables via PublicationsView.aspx?id=. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: xlsx, pdf, html.
- Latest: 2026-07-31 - 28th edition 2025-26, 245 tables. Frequency: Annual. Lag: ~4 months after FY end.
- Coverage: 1950-51 to 2025-26 (Varies by table). Basis: Mixed: T1/T11 new base 2022-23 (2022-23..2025-26; pre-NAS-2026 vintage, e.g. GDP 2022-23 26,117,627) plus old base to 2022-23; T12/T13 old base 2011-12.
- Key series: T1 - Macro aggregates current prices [Rs crore]; T11 - Sector-wise domestic saving (new base) [Rs crore]; T12 - Household financial assets/liabilities (NAS 2025, old base) [Rs crore]; T13 - Institutional GCF (base 2011-12) to 2023-24 [Rs crore]; T36-T43, T49 - Money, RBI balance sheet, SCB aggregates, credit deployment, consolidated SCB balance sheet (to 2024-25) [Rs crore]; T60 - Flow of financial resources to commercial sector (to 2025-26 P) [Rs crore]; T86-T110 - Central/state fiscal [Rs crore].
- SAM use: macro aggregates; institutional saving; household financial flows; financial balance sheets; fiscal cross-check.
- Quirks: Mixes GDP bases (T11 HH gross financial saving 2023-24 3,575,657 vs T12 3,430,640). T42 header 'last reporting Friday' but 2025-26 value is a 31-Mar-2026 month-end figure. No reproduction statement in HBS PDF.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Financial Stocks and Flow of Funds (FSF) of the Indian Economy 2023-24** (`rbi_fsf_fof`, corrected)

- Publisher: Reserve Bank of India (RBI Bulletin article + workbook). Landing: <https://www.rbi.org.in/Scripts/FlowofFundsAccounts.aspx>
- Access: Bulletin article + single XLSX workbook (71 sheets). rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: xlsx, html, pdf.
- Latest: 2026-01-21 - FSF 2023-24, RBI Bulletin January 2026; no 2024-25 edition as of 2026-09-29. Frequency: Annual (irregular timing). Lag: ~22 months.
- Coverage: 2011-12 to 2023-24 (Stocks 2011-12..2023-24; transactions and valuation 2012-13..2023-24). Basis: Current prices Rs crore; GDP ratios inferred to be on old 2011-12 base (article 12.0% nominal growth 2023-24 vs 10.97% new-base) - inference.
- Key series: St 1-5 - Sector financial balance sheets (S121 RBI, S122 ODCs, S123-S129 OFCs, S11 public/private NFC, S1311/S1312, S14+S15, S2) [Rs crore]; S 6.1-6.13 - From-whom-to-whom sector x sector (8 sectors, no instrument dimension) [Rs crore]; S 7.1-7.13 - Instrument (F1-F8) x sector [Rs crore]; S 8.1-8.3 - Financing of private NFCs, GG, households [Rs crore]; S 9.1-9.6 - Sectoral composition of claims/uses of RoW, ODCs, OFCs [Rs crore].
- SAM use: Flow of Funds / financial account; household financial assets/liabilities; NFC and GG financing; RoW financial account.
- Quirks: Not aligned to 2022-23 base. Unindexed legacy sheets S 8.4-8.7 labelled 'Rs Billion' with crore-magnitude values, covering only 2011-12..2017-18 - exclude. FWTW-by-instrument requires estimation.
- Licence: RBI Bulletin imprint: '(c) Reserve Bank of India 2026. All rights reserved. Reproduction is permitted provided an acknowledgement of the source is made.' Website Disclaimer (no deep links/caching without permission) still applies. The imprint text was read in the September 2026 Bulletin (license.url). The imprint of January 2026 was not checked; it is ASSUMED to carry the same reproduction clause.
- Not confirmed: license (imprint of January 2026 not checked; Sept 2026 imprint assumed).

**Household Financial Savings - RBI preliminary estimates (Bulletin Current Statistics 52(a)/(b))** (`rbi_hh_fin_savings`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx>
- Access: Monthly Bulletin table PDF (no XLSX for Sept 2026 issue); older quarterly page has XLSX to Aug 2025. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: pdf.
- Latest: 2026-09-25 - Bulletin Sept 2026: preliminary 2025-26 (NFA Rs 21,68,779.7 cr = 6.3% of GDP), revised 2022-23 to 2024-25. Frequency: Quarterly estimates, republished monthly. Lag: ~6 months after FY end.
- Coverage: 2022-23 Q1 to 2025-26 Q4. Basis: Current prices Rs crore; %GDP on new base 2022-23.
- Key series: 52(a) - Flow of household financial assets and liabilities by instrument [Rs crore]; 52(b) - Stocks of household financial assets and liabilities [Rs crore].
- SAM use: household financial account; household liabilities by lender.
- Quirks: Stale QuarterlyPublications page (latest Aug 2025, tables 50a/50b, old base). Large revisions (2024-25 NFA 19,94,202.4 -> 22,57,092.5, +13%). RBI 2023-24 gross financial assets 36,01,838.9 differ from NSO T11 35,75,657.
- Licence: RBI Bulletin imprint: '(c) Reserve Bank of India 2026. All rights reserved. Reproduction is permitted provided an acknowledgement of the source is made.' Website Disclaimer (no deep links/caching without permission) still applies. The imprint text was read in the September 2026 Bulletin (license.url). The imprint of the issue carrying the article was not checked; it is ASSUMED to carry the same reproduction clause.
- Not confirmed: license (imprint of the issue carrying the article not checked; Sept 2026 imprint assumed).

**Sectoral Deployment of Bank Credit (monthly)** (`rbi_sectoral_credit_bank`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/Data_Sectoral_Deployment.aspx>
- Access: Monthly press release + XLSX. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: xlsx, pdf.
- Latest: 2026-08-31 - July 2026 data. Frequency: Monthly. Lag: ~1 month.
- Coverage: 2010 to 2026-07. Basis: Outstanding Rs crore.
- Key series: Statement I - Deployment by major sectors [Rs crore]; Statement II - Industry-wise deployment [Rs crore].
- SAM use: bank credit by activity/sector.
- Quirks: 41 select SCBs (~95% of non-food credit). From 31 Dec 2025 reporting date = month-end (Banking Laws (Amendment) Act 2025); XLSX mixes Friday and month-end reference dates. HDFC merger (1 Jul 2023) affects comparisons.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Basic Statistical Returns BSR-1 (credit) and BSR-2 (deposits)** (`rbi_bsr`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/Pr_DataRelease.aspx?SectionID=354&DateFilter=YearMonth_PR>
- Access: Press-release PDFs; detailed tables only on DBIE Publications. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: pdf.
- Latest: 2026-08-31 - Quarterly June 2026 (2026-08-31); annual March 2026 (2026-05-29). Frequency: Quarterly (SCBs excl. RRBs); annual (incl. RRBs). Lag: ~2 months.
- Coverage: 2014-12 to 2026-06 (Annual BSR back decades; quarterly since Dec 2014). Basis: Outstanding Rs crore.
- Key series: BSR-1 - Credit by activity, organisation, borrower category (institutional sector), district, population group [Rs crore]; BSR-2 - Deposits by type, institutional ownership, maturity, size [Rs crore].
- SAM use: bank credit and deposits by institutional sector; rural/urban split.
- Quirks: Household sector 58.6% of credit; 59.3% of deposits (end-Mar 2026). Census 2011 population groups. New district-level gender series.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Statistical Tables Relating to Banks in India (STRBI)** (`rbi_strbi`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Statistical%20Tables%20Relating%20to%20Banks%20in%20India>
- Access: DBIE Publications (SAP BOE report) only. Needs DBIE BOE session; scripting needs RBI permission. Requires: none. Formats: xlsx.
- Latest: 2025-12-29 - STRBI 2024-25. Frequency: Annual. Lag: ~9 months.
- Coverage: 2024-25. Basis: Rs crore current.
- Key series: STRBI - Bank-wise and bank-group balance sheets; income and expenditure [Rs crore].
- SAM use: bank output / FISIM inputs; financial sector property income.
- Quirks: Not on rbidocs.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Report on Trend and Progress of Banking in India 2024-25** (`rbi_trend_progress`, corrected)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Trend%20and%20Progress%20of%20Banking%20in%20India>
- Access: Chapter PDFs + 40 appendix XLSX. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: pdf, xlsx.
- Latest: 2025-12-29 - 2024-25 edition. Frequency: Annual. Lag: ~9 months.
- Coverage: 2022-23 to 2025-09 (Appendix VI.1 end-March 2023, 2024, 2025 and end-September 2025). Basis: Rs crore current.
- Key series: App. VI.1-VI.9 - NBFC consolidated balance sheet (total, UL, ML, deposit-taking), NBFC credit by sector, NBFC-UL/ML financial performance, FIs, standalone PDs [Rs crore]; App. IV.x / V.x - Banking at a glance; co-operative banks, PACS, ARDBs [Rs crore].
- SAM use: NBFC institutional account; co-operative banks; financial sector.
- Quirks: NBFC total liabilities/assets end-March 2025 = 61,09,126 cr.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Sectoral Deployment of Credit by NBFCs (monthly; new series 2026)** (`rbi_nbfc_sectoral_credit`, corrected)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/Data_Sectoral_Deployment_NBFC.aspx>
- Access: Monthly press release + XLSX. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: xlsx, pdf.
- Latest: 2026-09-07 - July 2026 data (3rd release; first was May 2026 data on 2026-07-07). Frequency: Monthly. Lag: ~5 weeks.
- Coverage: 2024-07-31 to 2026-07-31 (Columns 31-Jul-2024, 31-Mar-2025, 31-Jul-2025, 31-Mar-2026, 31-Jul-2026). Basis: Outstanding Rs crore.
- Key series: NBFC credit - UL/ML NBFCs + HFCs credit to agriculture, industry, services, retail [Rs crore].
- SAM use: NBFC credit to sectors/households.
- Quirks: Sample ~87% of NBFC credit vs RTP 2024-25 (Sept 2025). Cannot supply a 2023-24 year.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Financial Stability Report** (`rbi_fsr`, corrected)

- Publisher: Reserve Bank of India / FSDC Sub-Committee. Landing: <https://www.rbi.org.in/Scripts/FsReports.aspx>
- Access: PDF only. Requires: none. Formats: pdf.
- Latest: 2026-06-30 - June 2026. Frequency: Half-yearly (June, December). Lag: ~3 months.
- Coverage: 2026-03. Basis: Ratios and Rs crore.
- Key series: FSR - SCB/NBFC capital and asset quality; household debt; interconnectedness [various].
- SAM use: cross-checks; ABM calibration.
- Quirks: HalfYearlyPublications.aspx?head=Financial Stability Report returns an error page; use FsReports.aspx.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**RBI Annual Report 2025-26 (incl. RBI accounts, appendix tables)** (`rbi_annual_report`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/AnnualReportPublications.aspx>
- Access: Chapter PDFs + 7 appendix XLSX. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: pdf, xlsx.
- Latest: 2026-05-29 - Annual Report 2025-26. Frequency: Annual (April-March). Lag: ~2 months.
- Coverage: 2021-22 to 2025-26. Basis: Rs crore; appendix macro on 2022-23 base.
- Key series: Ch XII - RBI income, expenditure; surplus to Centre 2025-26 Rs 2,86,588.46 cr (2024-25 2,68,590.07); CF provision 1,09,379.64 [Rs crore]; App. 3 - Gross savings % GNDI 2022-23..2024-25 (new base, NSO) [%]; App. 5-7 - Flow of resources to commercial sector; fiscal indicators; BoP [various].
- SAM use: RBI institutional account; government non-tax revenue.
- Quirks: RBI exempt from income tax (s.48 RBI Act).
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Weekly Statistical Supplement and Money Supply releases** (`rbi_wss_money`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/WSSViewDetail.aspx?TYPE=Basic&PARAM1=9%2F25%2F2026>
- Access: Per-issue HTML page with XLSX/PDF; date-parameterised URL. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: xlsx, pdf.
- Latest: 2026-09-25 - WSS 25 Sep 2026; money supply fortnight ended 15 Sep 2026. Frequency: Weekly; money supply fortnightly. Lag: ~1-2 weeks.
- Coverage: 2006 to 2026-09. Basis: Rs crore outstanding.
- Key series: T1 - RBI liabilities and assets [Rs crore]; T6/T7 - Money stock; reserve money [Rs crore]; T4 - SCB business in India [Rs crore].
- SAM use: RBI balance sheet; money and credit aggregates.
- Quirks: Year archive uses ASP.NET postback; wss.rbi.org.in redirects to BS_ViewWSS.aspx.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**RBI Bulletin - Current Statistics and articles** (`rbi_bulletin_current_stats`, corrected)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx>
- Access: Monthly issue page with per-table PDFs (Sept 2026: 73 PDFs, 0 XLSX). rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: pdf.
- Latest: 2026-09-25 - September 2026 issue. Frequency: Monthly. Lag: Varies by table.
- Coverage: n/a (Snapshots only; history via HBS/DBIE). Basis: CPI 2024=100; WPI, IIP 2022-23=100; HFS %GDP new base.
- Key series: 2, 6-12 - RBI liabilities/assets; money and monetary surveys [Rs crore]; 24, 48-51 - Union accounts; combined Centre+States; state finances [Rs crore]; 34 - Non-resident deposits [US$ mn]; 36 - LRS outward remittances [US$ mn]; 40-44 - BoP and IIP [US$ mn]; 52(a)/(b) - Household financial flows/stocks [Rs crore].
- SAM use: household financial flows; government financing; BoP cross-check.
- Quirks: Table numbering changes over time (HFS 50 -> 52). bulletin.rbi.org.in redirects to BS_ViewBulletin.aspx.
- Licence: RBI Bulletin imprint: '(c) Reserve Bank of India 2026. All rights reserved. Reproduction is permitted provided an acknowledgement of the source is made.' Website Disclaimer (no deep links/caching without permission) still applies.

**Performance of Private Corporate Business Sector; Finances of Non-Govt Non-Financial Public Ltd Companies** (`rbi_corporate_finances`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/Pr_DataRelease.aspx?SectionID=378&DateFilter=Year>
- Access: Press-release PDFs + DBIE tables. Requires: none. Formats: pdf, xlsx.
- Latest: 2026-06-24 - PCBS 2025-26 (2026-06-24); public ltd companies 2024-25 (2026-03-30). Frequency: Quarterly/annual (listed); annual (public ltd). Lag: ~3 months (listed); ~12 months (public ltd).
- Coverage: 2025-26. Basis: Rs crore current.
- Key series: PCBS - Sales, staff cost, operating profit, interest, tax of non-financial companies [Rs crore].
- SAM use: private NFC income and appropriation.
- Quirks: Sample-based, listed-company biased. NBFI performance series discontinued after 2018-19.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Report on Currency and Finance** (`rbi_rcf`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Report%20on%20Currency%20and%20Finance>
- Access: PDF chapters. Requires: none. Formats: pdf.
- Latest: 2024-07-29 - 2023-24 (digital revolution theme). Frequency: Irregular thematic. Lag: n/a.
- Coverage: n/a. Basis: n/a.
- Key series: RCF - Thematic; none directly usable [n/a].
- SAM use: narrative only.
- Quirks: Low priority.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Scheduled Banks' Statement of Position in India (fortnightly Form-A)** (`rbi_form_a_scheduled_banks`, unverified)

- Publisher: Reserve Bank of India. Landing: <https://data.rbi.org.in/>
- Access: DBIE: Home > Statistics > Data Release > Fortnightly > Scheduled Bank's Statement of Position in India. Requires: none. Formats: xlsx.
- Latest: unknown - unverified. Frequency: Fortnightly. Lag: unverified.
- Coverage: n/a. Basis: Rs crore outstanding.
- Key series: Form-A - Aggregate deposits and credit of all scheduled banks [Rs crore].
- SAM use: full-coverage bank totals to scale SIBC sample and reconcile BSR.
- Quirks: Not fetched by finder, verifier or lead.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

### 3.5 External sector: BoP, IIP, trade, remittances, FDI/FPI/ECB (`external`)

**Developments in India's Balance of Payments (quarterly, BPM6) + Sources of Variation in Forex Reserves** (`rbi_bop_quarterly`, verified)

- Publisher: Reserve Bank of India (DSIM). Landing: <https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63493>
- Access: HTML press-release tables (fetchable); Statement I/II XLSX on rbidocs; long series via DBIE. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: html, xlsx, pdf.
- Latest: 2026-09-01 - Q1 2026-27 (Apr-Jun 2026): CAD US$4.2 bn (0.5% GDP). FY 2025-26 (P) released 2026-06-08: CA -25.2 bn. Frequency: Quarterly (FY totals with Q4). Lag: ~2 months.
- Coverage: 1990-91 to 2026-27 Q1 (BPM6 presentation from 2011-12 (not re-checked)). Basis: Current US$ mn/bn and Rs crore.
- Key series: Table 1 - Major BoP items: goods, services, primary income, secondary income, DI, PI, other investment, reserves, E&O [US$ bn]; 2025-26 P - CA 1077.8/1103.0/-25.2; goods 446.1/783.4; services +216.6; primary -48.2; secondary +143.6; reserves -23.6 [US$ bn].
- SAM use: RoW current account; RoW primary and secondary income; RoW capital and financial account.
- Quirks: Vintage flags P/PR/R; large revisions (Q3 2025-26 CAD 13.2 -> 15.5). Old-format reserves table differs from BPM6 (-25.4 vs -25.2). FCNR(B) swap window 8 Jun-31 Aug 2026 and ECB/OFCB windows to 31 Dec 2026 distort 2026-27.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Developments in India's Balance of Payments for the Month (new monthly BoP)** (`rbi_bop_monthly`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63596>
- Access: HTML table in press release. Requires: none. Formats: html, pdf.
- Latest: 2026-09-15 - July 2026 (CA -7.0 bn; NRI deposits +33.5 bn). Frequency: Monthly (by 15th of second following month). Lag: ~45 days.
- Coverage: 2026-04 to 2026-07. Basis: Current US$ bn.
- Key series: monthly BoP - CA, merchandise, services, transfers, income, FDI, FPI, ECB, NRI deposits, other capital incl. E&O [US$ bn].
- SAM use: nowcast only - do not mix into SAM.
- Quirks: Old format, not BPM6; Apr-Jun 2026 CA -3.1 vs quarterly BPM6 -4.2.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**RBI HBS 2025-26 external-sector tables (BPM6 BoP in US$ and Rs, invisibles, NRI deposits, FDI, reserves, debt, IIP, trade)** (`rbi_hbs_external`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/scripts/PublicationsView.aspx?id=23952>
- Access: HTML tables per PublicationsView.aspx?id= (parse with pandas.read_html); XLSX on rbidocs. Requires: none. Formats: html, xlsx.
- Latest: 2026-07-31 - HBS 2025-26, data to FY 2025-26. Frequency: Annual. Lag: ~4 months.
- Coverage: 1968-69 to 2025-26 (T126/127 multi-year; T131 from 2006-07; T139 from 2008; T143 from 2004-05; T144 from 1968-69; T190 monthly from Apr 2019). Basis: Current Rs crore and US$ mn.
- Key series: T126/T127 - BPM6 standard presentation US$ / Rs crore incl. EBOPS services, CE, investment income, secondary income (2025-26 CA 95,30,151 / 97,49,904 / -2,19,753 Rs cr) [Rs crore / US$ mn]; T130/T131 - Invisibles by category [US$ / Rs crore]; T139-T142 - NRI deposits by scheme [US$ mn / Rs crore]; T143/T144 - Foreign investment inflows; forex reserves [US$ mn]; T145-T150 - External debt; IIP [US$ mn]; T198-T200 - Quarterly BPM6 BoP in rupees; quarterly IIP [Rs crore / US$ mn]; T1 - NSO macro aggregates incl. RoW primary income and transfers (2025-26 RoW items '-') [Rs crore].
- SAM use: RoW account in Rs crore; factor income to/from RoW; remittance receipts; NRI deposit flows.
- Quirks: 2025-26 BoP preliminary. T190 has two rows labelled 'March-2020' (February mislabelled). Merged HTML headers.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Data on India's Invisibles (BPM6, quarterly)** (`rbi_invisibles_quarterly`, verified)

- Publisher: Reserve Bank of India. Landing: <https://rbi.org.in/Scripts/Data_IndiasInvisibles.aspx>
- Access: XLSX on rbidocs. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: xlsx.
- Latest: 2026-06-30 - Q4 2025-26 (Jan-Mar 2026); Q1 2026-27 likely 2026-09-30 (last year's Q1 came 2025-09-30). invisibles data for Q1 2026-27: Not released as of 15:19 IST on 29 Sep 2026 (RBI press-release listing); expected 30 Sep 2026. Frequency: Quarterly. Lag: ~3 months.
- Coverage: 2026-03. Basis: Current US$ mn (Rs unverified).
- Key series: invisibles - Services by EBOPS; primary income; secondary income (personal transfers) [US$ mn].
- SAM use: services trade by category; remittance receipts; investment income.
- Quirks: XLSX structure unverified (bot challenge).
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**India's International Investment Position (IIP)** (`rbi_intl_investment_position`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63047>
- Access: HTML press tables; XLSX on rbidocs; HBS T149/T150/T199/T200. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: html, xlsx.
- Latest: 2026-06-30 - End-March 2026: net claims of non-residents US$209.9 bn (-5.9% GDP); end-June 2026 likely 2026-09-30. India's IIP at end-June 2026: Not released as of 15:19 IST on 29 Sep 2026 (RBI press-release listing); expected 30 Sep 2026. Frequency: Quarterly. Lag: ~3 months.
- Coverage: 2019-03 to 2026-03 (BPM6; HBS T150 from end-March 2019 in Rs). Basis: Stocks at market value.
- Key series: IIP - Assets/liabilities by DI, PI, other investment, reserves and sector [US$ bn].
- SAM use: RoW financial stocks; valuation checks.
- Quirks: Sources: FLA census, IBS, PIP (ex-CPIS), BAL.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**India's External Debt (quarterly)** (`rbi_external_debt`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63041>
- Access: HTML press tables; XLSX on rbidocs. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: html, xlsx.
- Latest: 2026-06-29 - End-March 2026: US$762.8 bn, 20.8% of GDP; end-June 2026 likely 2026-09-30. India's external debt at end-June 2026: Not released as of 15:19 IST on 29 Sep 2026 (RBI press-release listing); expected 30 Sep 2026. Frequency: Quarterly. Lag: ~3 months.
- Coverage: 2026-03. Basis: Stocks US$ bn; ratios to nominal GDP (series unstated).
- Key series: debt - By sector (GG, central bank, DTCs, OFC, NFC), instrument, maturity, currency; debt service ratio [US$ bn].
- SAM use: RoW liabilities of government, banks, corporates; interest cross-check.
- Quirks: Debt/GDP restated: end-Mar 2025 19.1% -> 19.8% (stock 736.3 -> 736.4), end-Mar 2024 18.5% -> 19.2% - consistent with the new GDP base but RBI does not say.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Monthly Data on India's International Trade in Services** (`rbi_services_monthly`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63480>
- Access: HTML press release; HBS T190. Requires: none. Formats: html.
- Latest: 2026-08-31 - July 2026: receipts 38,253, payments 20,606 US$ mn (provisional). Frequency: Monthly. Lag: ~1 month.
- Coverage: 2019-04 to 2026-07. Basis: Current US$ mn.
- Key series: services - Receipts and payments totals [US$ mn].
- SAM use: services time series.
- Quirks: No category breakdown.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**India's Remittances Survey - 6th round (2023-24)** (`rbi_remittances_survey`, verified)

- Publisher: Reserve Bank of India (Bulletin article). Landing: <https://rbi.org.in/scripts/BS_ViewBulletin.aspx?Id=23260>
- Access: HTML article. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: html, pdf.
- Latest: 2025-03-19 - 6th round, Bulletin March 2025; no 7th round found (not re-checked). Frequency: Irregular (2016-17, 2020-21, 2023-24). Lag: ~1 year.
- Coverage: 2016-17 to 2023-24. Basis: Shares (%); total inward US$118.7 bn 2023-24.
- Key series: Table 1 - Source-country shares (banks channel): US 27.7, UAE 19.2, UK 10.8, Singapore 6.6, Canada 3.8, Australia 2.3; GCC 38 [%]; Table 2 - State destination shares: Maharashtra 20.5, Kerala 19.7, TN 10.4, Telangana 8.1, Karnataka 7.7 [%].
- SAM use: source-region split of RoW->household transfers (estimated); regional allocation.
- Quirks: Bank-channel shares from 30 AD banks (~99% of value); applying to total BoP transfers is an estimate.
- Licence: RBI Bulletin imprint: '(c) Reserve Bank of India 2026. All rights reserved. Reproduction is permitted provided an acknowledgement of the source is made.' Website Disclaimer (no deep links/caching without permission) still applies. The imprint text was read in the September 2026 Bulletin (license.url). The imprint of March 2025 was not checked; it is ASSUMED to carry the same reproduction clause.
- Not confirmed: license (imprint of March 2025 not checked; Sept 2026 imprint assumed).

**RBI WSS - Foreign Exchange Reserves** (`rbi_wss_forex_reserves`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63666>
- Access: HTML weekly extract; HBS T144. Requires: none. Formats: html.
- Latest: 2026-09-25 - As on 18 Sep 2026: total US$765,901 mn (Rs 73,42,985 cr); FCA 630,980; gold 111,292; SDR 18,739; RTP 4,890. Frequency: Weekly. Lag: 1 week.
- Coverage: 1968-69 to 2026-09-18. Basis: Stocks at market value.
- Key series: reserves - Total, FCA, gold, SDR, RTP [Rs crore / US$ mn].
- SAM use: RBI foreign assets stock.
- Quirks: Includes valuation; use BoP reserve assets for flows.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**NRI deposits (by scheme) and 2026 FCNR(B)/ECB/OFCB swap-facility data** (`rbi_nri_deposits`, corrected)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/scripts/PublicationsView.aspx?id=23964>
- Access: HTML (HBS T139-142); monthly Bulletin table 34 is PDF-only on rbidocs. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: html, pdf.
- Latest: 2026-09-21 - HBS 2025-26 to end-March 2026; swap-facility update 21 Sep 2026 (FCNR(B) 1,32,980; OFCB 5,320; ECB 5,296; total 1,43,596 US$ mn). Frequency: Monthly (Bulletin) / annual (HBS). Lag: ~1-2 months.
- Coverage: 2008-03 to 2026-03. Basis: US$ mn / Rs crore.
- Key series: T139 - FCNR(B), NR(E)RA, NRO outstanding and flows [US$ mn].
- SAM use: RoW -> bank deposit liabilities.
- Quirks: FCNR(B) window 8 Jun-31 Aug 2026 (curtailed from 30 Sep); ECB/OFCB windows to 31 Dec 2026.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**External Commercial Borrowings / FCCB / RDB monthly data** (`rbi_ecb_monthly`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/ECBUserView.aspx?Id=274>
- Access: HTML table. Requires: none. Formats: html, xlsx.
- Latest: 2026-09-07 - July 2026 data. Frequency: Monthly. Lag: ~5-6 weeks.
- Coverage: 2026-07. Basis: US$ equivalent per loan.
- Key series: ECB - Borrower, sector, amount, purpose, maturity, lender category, route [US$].
- SAM use: sectoral split of RoW loans (financial account).
- Quirks: Registrations, not disbursements.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**DPIIT Quarterly Fact Sheet on FDI Inflow** (`dpiit_fdi_factsheet`, unverified)

- Publisher: Department for Promotion of Industry and Internal Trade. Landing: <https://www.dpiit.gov.in/publications/fdi-factsheet>
- Access: PDF (static URL fetchable); listing is client-rendered JS. Requires: none. Formats: pdf.
- Latest: 2026-06 - March 2026 factsheet: 2025-26 FDI EQUITY inflow US$58,846 mn (excl. NRI schemes); total FDI Q4 2025-26 US$20,876 mn; cumulative since Apr 2000 US$1,166,462 mn. June 2026 factsheet not located. Frequency: Quarterly. Lag: ~3 months.
- Coverage: 2000-04 to 2026-03. Basis: Current US$ mn and Rs crore.
- Key series: equity - FDI equity by month, country, sector, state [US$ mn].
- SAM use: RoW -> NFC equity by country and sector.
- Quirks: Provisional, subject to RBI reconciliation. Country/sector detail is equity-only.
- Licence: unverified (copyright page is a JS shell).
- Not confirmed: license (copyright page is a JavaScript shell); June 2026 factsheet URL.

**Census on Foreign Liabilities and Assets (FLA) of Indian Direct Investment Entities** (`rbi_fla_census`, verified)

- Publisher: Reserve Bank of India. Landing: <https://rbi.org.in/Scripts/PublicationsView.aspx?id=23438>
- Access: HTML tables. Requires: none. Formats: html, pdf.
- Latest: 2025-10-29 - 2024-25 round (provisional); 2025-26 round compiled internally but unpublished. Frequency: Annual. Lag: ~7 months.
- Coverage: 2024-25. Basis: Stocks at market and face value.
- Key series: FLA - FDI/ODI positions by country, activity, listed/unlisted [Rs crore / US$].
- SAM use: FDI stock by sector and source country.
- Quirks: Stocks incl. valuation.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Overseas Direct Investment (monthly)** (`rbi_odi_monthly`, corrected)

- Publisher: Reserve Bank of India. Landing: <https://rbi.org.in/Scripts/Data_Overseas_Investment.aspx>
- Access: XLSX on rbidocs only. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: xlsx.
- Latest: 2026-09-18 - August 2026 (released 2026-09-18; URL not identified). OFDI18082026.xlsx / prid=63396 are JULY 2026. Frequency: Monthly. Lag: ~3 weeks.
- Coverage: 2026-08. Basis: US$ mn (unverified).
- Key series: ODI - Commitments by Indian party, country, activity, equity/loan/guarantee (structure unverified) [US$ mn].
- SAM use: NFC -> RoW outward investment.
- Quirks: Commitments, not BoP flows.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Survey on Computer Software and ITES Exports 2025-26** (`rbi_ites_survey`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63625>
- Access: HTML press tables. Requires: none. Formats: html, pdf.
- Latest: 2026-09-18 - 2025-26: software services exports US$221.4 bn; US 54.1%, Europe 31.8%. Frequency: Annual. Lag: ~6 months.
- Coverage: 2025-26. Basis: Rs crore and US$ bn.
- Key series: ITES - Exports by activity, destination, mode, currency [US$ bn].
- SAM use: partner split for IT services exports.
- Quirks: Survey estimate (89% coverage).
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Survey of Foreign Liabilities and Assets of Mutual Funds 2025-26** (`rbi_mf_fla_survey`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63479>
- Access: HTML press tables. Requires: none. Formats: html.
- Latest: 2026-08-31 - 2025-26: foreign liabilities US$31.5 bn; overseas assets US$10.2 bn. Frequency: Annual. Lag: ~5 months.
- Coverage: 2026-03. Basis: Stocks end-March.
- Key series: MF FLA - MF units held by non-residents; overseas assets [Rs crore / US$ mn].
- SAM use: RoW <-> mutual funds positions.
- Quirks: Implied end-March 2026 rate ~Rs 94.7/US$.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Finances of Foreign Direct Investment Companies, 2024-25** (`rbi_fdi_company_finances`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/Pr_DataRelease.aspx?SectionID=363&DateFilter=Year>
- Access: Press release PDF. Requires: none. Formats: pdf.
- Latest: 2026-04-22 - 2024-25 edition. Frequency: Annual. Lag: ~13 months.
- Coverage: 2024-25. Basis: Rs crore.
- Key series: FDI cos - Profits, dividends, exports, imports of FDI companies by industry [Rs crore].
- SAM use: allocation of RoW direct-investment income payments by sector.
- Quirks: None recorded in Phase 0.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Survey on Foreign Collaboration in Indian Industry 2023-2025** (`rbi_foreign_collaboration_survey`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/Pr_DataRelease.aspx?SectionID=383&DateFilter=Year>
- Access: Press release. Requires: none. Formats: pdf.
- Latest: 2025-12-02 - Data release 2025-12-02. Frequency: Periodic. Lag: n/a.
- Coverage: 2023 to 2025. Basis: Rs crore.
- Key series: FCS - Royalty and technical fee payments by industry [Rs crore].
- SAM use: split of IP-charges services imports by sector.
- Quirks: None recorded in Phase 0.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Survey on International Trade in Banking Services 2024-25** (`rbi_banking_services_trade_survey`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/Pr_DataRelease.aspx?SectionID=367&DateFilter=Year>
- Access: Press release. Requires: none. Formats: pdf.
- Latest: 2025-09-26 - 2024-25 edition. Frequency: Annual. Lag: ~6 months.
- Coverage: 2024-25. Basis: Rs crore / US$.
- Key series: ITBS - Banks' cross-border financial services exports/imports [US$ mn].
- SAM use: RoW x financial services (banks).
- Quirks: None recorded in Phase 0.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Outward Remittances under the Liberalised Remittance Scheme (Bulletin table 36)** (`rbi_lrs_outward_remittances`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx?yr=2026&mon=9>
- Access: Monthly Bulletin table PDF on rbidocs. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: pdf.
- Latest: 2026-09-25 - September 2026 Bulletin. Frequency: Monthly. Lag: ~2 months.
- Coverage: n/a. Basis: US$ mn.
- Key series: 36 - LRS outflows by purpose: travel, relatives, gifts, education, investment [US$ mn].
- SAM use: household -> RoW outflows.
- Quirks: PDF only.
- Licence: RBI Bulletin imprint: '(c) Reserve Bank of India 2026. All rights reserved. Reproduction is permitted provided an acknowledgement of the source is made.' Website Disclaimer (no deep links/caching without permission) still applies. The imprint text was read in the September 2026 Bulletin (license.url). The imprint of the issue carrying the table was not checked; it is ASSUMED to carry the same reproduction clause.
- Not confirmed: license (imprint of the issue carrying the table not checked; Sept 2026 imprint assumed).

**Department of Commerce Export Import Data Bank - TradeStat (EIDB annual, MEIDB monthly)** (`commerce_tradestat`, verified)

- Publisher: Department of Commerce (data DGCI&S; hosted NIC). Landing: <https://tradestat.commerce.gov.in/eidb/commodity_wise_export>
- Access: HTML form POST (CSRF token + session cookie); HTML tables; client-side Excel export; robots allow all. Requires: none. Formats: html, xlsx.
- Latest: 2026-09-16 - EIDB to 2025-26 (updated 07/08/2026); MEIDB Jan 2018-Jul 2026 (updated 16/09/2026). Frequency: Annual (EIDB) and monthly (MEIDB). Lag: ~1.5 months.
- Coverage: 2017-18 to 2026-07. Basis: Current US$ mn / Rs crore / quantity; X FOB, M CIF.
- Key series: EIDB - Commodity (HS 2-8 digit), country, commodity x country, region [US$ mn / Rs crore]; 2025-26 - Total exports 441,452.14 US$ mn (BoP goods credit 446.1 bn) [US$ mn].
- SAM use: goods trade by product and partner.
- Quirks: ITC-HS codes dropped/re-allocated from April 2026.
- Licence: No licence on TradeStat (disclaimer: 'do not have any legal sanctity ... for general refrence only'); underlying DGCI&S data governed by DGCI&S dissemination policy (written permission to re-disseminate).

**DGCI&S Foreign Trade Statistics and Data Dissemination Portal** (`dgcis_trade`, verified)

- Publisher: Directorate General of Commercial Intelligence and Statistics, Kolkata. Landing: <https://www.dgciskol.gov.in/>
- Access: Portal login (Guest/Official/Subscriber, captcha/OTP); principal-commodity data free (24 months); detailed data paid. Rs 1 per record; annual bulk INR 3,50,000; 60% discount only for Indian academic institutions (not applicable to Udgam Labs). Requires: paid. Formats: unverified, pdf.
- Latest: unknown - Finalised export/import data to June 2026; Laspeyres indices Apr-Jun 2026 (base 2022-23). Frequency: Monthly. Lag: ~2-3 months.
- Coverage: 2026-06. Basis: Current values; unit value/volume indices base 2022-23 and 2012-13.
- Key series: 8-digit - HS x country x port trade [Rs / US$]; indices - Laspeyres trade indices base 2022-23 [index]; SERF - Services export report 2024-25 [various].
- SAM use: official goods trade by product/partner; trade price deflators.
- Quirks: State & district PC data for July 2026 not published.
- Licence: Copyright reserved by DGCI&S; 'internal use only'; re-dissemination (incl. visualisation apps) needs written permission of DG DGCIS; royalty-free if <=1000 records or substantially different data (permission still required).
- Not confirmed: latest_release.date.

**World Bank WDI personal remittances (and discontinued KNOMAD bilateral matrix)** (`worldbank_remittances`, verified)

- Publisher: World Bank. Landing: <https://api.worldbank.org/v2/country/IND/indicator/BX.TRF.PWKR.CD.DT?format=json&mrv=3>
- Access: REST API (no key). Requires: none. Formats: json, csv.
- Latest: 2026-07-13 - 2025 value US$150.7 bn (WDI lastupdated 2026-07-13). Frequency: Annual. Lag: ~6 months.
- Coverage: 2025. Basis: Current US$, calendar year.
- Key series: BX.TRF.PWKR.CD.DT - Personal remittances received [US$].
- SAM use: remittance cross-check.
- Quirks: KNOMAD 'active from 2013 until 2024' - no maintained bilateral matrix.
- Licence: CC BY 4.0 (World Bank default; individual datasets may differ).

### 3.6 Union government finances and taxes (`union_fiscal`)

**Union Budget 2026-27 document set (Budget at a Glance, Receipt Budget, Expenditure Budget/Profile, AFS, FRBM statements)** (`mof_union_budget_2026_27`, corrected)

- Publisher: Ministry of Finance (Budget Division, DEA). Landing: <https://www.indiabudget.gov.in/>
- Access: Static XLSX beside most PDF tables; no API. Use GET (HEAD returns 404). Site banner: Excel is system-generated; 'In case of any inconsistency, pdf files will be treated as final'. Statements 27/27a PDF only. WebFetch gets 403; curl works. Requires: none. Formats: xlsx, pdf.
- Latest: 2026-02-01 - Budget 2026-27: Actuals 2024-25, BE 2025-26, RE 2025-26, BE 2026-27. Frequency: Annual (1 Feb). Lag: Actuals ~10 months after FY end.
- Coverage: 1947-48 to 2026-27 (Archive 1947-1995 and 1996-97 to 2025-26 plus interim budgets). Basis: Current prices Rs crore. %GDP uses OLD 2011-12-base AE 2025-26 GDP (357,13,886 cr; 2026-27 assumed 393,00,393 cr); recompute on new base (2025-26 PE 346.36 lakh cr).
- Key series: BAG - Fiscal deficit A 2024-25 15,74,431; RE 2025-26 15,58,492; BE 2026-27 16,95,768; revenue/capital receipts; interest; effective capex [Rs crore]; BAG Receipts / tr.xlsx - Gross tax by type (corporation 0020, income 0021, customs 0037, excise 0038, CGST 0005, IGST 0008, comp cess 0009); States' share; non-tax [Rs crore]; BAG Transfer of Resources - Devolution 12,86,885 (A 2024-25) / 13,92,971 (RE 2025-26) / 15,26,255 (BE 2026-27); FC grants; CSS; total transfers BE 2026-27 26,20,769 [Rs crore]; AFS - Statements I-IX by major head [Rs crore]; EB stat 1/3a/4a/4b/7/9/18/20/21/23 - Establishment/CS/CSS/transfers; subsidies (food 1,99,867; fertiliser 1,70,683; LPG 14,479; interest 21,885 in A 2024-25); transfers to States; grants to foreign govts [Rs crore]; Receipt Budget annexes - State-wise devolution; tax expenditure; debt, guarantees, external assistance [Rs crore].
- SAM use: Union government current account; Union -> State transfers; taxes by instrument; Union capital account and deficit financing; government -> RoW; subsidies by product.
- Quirks: Last-Modified headers unreliable (allafs.xlsx LM 2024-08-07 with 2026-27 content). Internal inconsistencies: revenue receipts A 2024-25 3,036,613 (BAAG) vs 3,036,619 (Receipts); fertiliser BE 2026-27 170,781 (BAG) vs 170,799 (stat7). Budget 'actuals' are pre-audit. GST compensation cess nil in BE 2026-27 (abolished 1 Feb 2026). IGST negative actuals (apportionment). Bilingual labels; '..' for nil.
- Licence: indiabudget.gov.in copyright policy: may not be reproduced without Ministry of Finance permission; no GODL.

**Report of the Sixteenth Finance Commission (2026-27 to 2030-31) and Explanatory Memorandum** (`mof_16th_finance_commission`, verified)

- Publisher: Finance Commission / Ministry of Finance. Landing: <https://fincomindia.nic.in/commission-reports-sixteenth>
- Access: PDF. Requires: none. Formats: pdf.
- Latest: 2026-02-01 - Submitted 17 Nov 2025; tabled 1 Feb 2026; Government accepted 41% vertical share. Frequency: Every 5 years. Lag: n/a.
- Coverage: 2026-27 to 2030-31. Basis: Current prices.
- Key series: vertical - States' share 41% of divisible pool [%]; horizontal - Weights: income distance 42.5, population 17.5, forest 10, demographic performance 10, area 10, GDP contribution 10; tax effort dropped (UP 17.619%) [%]; grants - Local body grants Rs 7,91,493 cr 2026-31; no revenue-deficit, sector or state-specific grants [Rs crore].
- SAM use: Union -> States transfer rules.
- Quirks: Actual annual transfers come from Budget/CGA. 2025-26 was under the 15th FC.
- Licence: No explicit licence found (copyright_policy page empty; footer 'Content Owned by Sixteenth Finance Commission ... All Rights Reserved').

**Economic Survey 2025-26 incl. Statistical Appendix** (`mof_economic_survey_2025_26`, verified)

- Publisher: Ministry of Finance, DEA Economic Division. Landing: <https://www.indiabudget.gov.in/economicsurvey/>
- Access: PDF per table; chapter charts XLSX. Requires: none. Formats: pdf, xlsx.
- Latest: 2026-01-29 - Economic Survey 2025-26. Frequency: Annual (late Jan). Lag: Fiscal tables to 2024-25 PA.
- Coverage: 2017-18 to 2024-25. Basis: Current prices; ratios on OLD 2011-12 base.
- Key series: 2.3-2.7 - Central, State and general government receipts/expenditure; liabilities [Rs crore]; 2.8 - State-wise GST on domestic supply 2023-24 to 2025-26 (Apr-Nov) [Rs crore].
- SAM use: cross-check.
- Quirks: 2024-25 PA FD 15,77,270 differs from Budget actual 15,74,431.
- Licence: indiabudget.gov.in copyright policy: may not be reproduced without Ministry of Finance permission; no GODL.

**CGA Monthly Accounts of the Union Government and Provisional Accounts** (`cga_monthly_accounts`, corrected)

- Publisher: Controller General of Accounts. Landing: <https://cga.nic.in/Accountproc.aspx>
- Access: HTML tables at /MonthlyReport/Published/{month}/{FY}.aspx. Requires: none. Formats: html.
- Latest: 2026-08-31 - July 2026 (Apr-Jul 2026-27); August due 2026-09-30. Provisional Accounts 2025-26: total expenditure 49,05,151, receipts 33,85,982, FD 15,19,169 cr (4.40% of GDP, base unstated). Frequency: Monthly (cumulative). Lag: Last day of following month; March by 31 May.
- Coverage: 1997-98 to 2026-07. Basis: Current prices Rs crore.
- Key series: AAG - Revenue receipts, tax (net), non-tax, non-debt capital receipts, revenue expenditure incl. interest, capex, deficits, financing, major subsidies [Rs crore].
- SAM use: Union provisional actuals 2025-26; high-frequency time series.
- Quirks: '(Details)' sub-pages return 404 (some hrefs point to file:///D:/) - no tax-by-type or devolution detail. Recovery of loans PA 2025-26 = 24,617 identical to 2024-25 (unexplained). Urea subsidy 2024-25: 1,20,879.83 (CGA) vs 1,17,872.96 (Budget). HEAD 404.
- Licence: No explicit licence (CGA Copyright-Policy page body is empty; footer 'All rights reserved').

**Union Government Finance Accounts, Appropriation Accounts and Accounts at a Glance (audited)** (`cga_finance_accounts_aag`, corrected)

- Publisher: Controller General of Accounts (audited by C&AG). Landing: <https://cga.nic.in/FinanceReport/Published/2024-2025.aspx>
- Access: PDF. Requires: none. Formats: pdf.
- Latest: 2026-06-30 - Finance Accounts 2024-25 (Statements 1-16, 14A, 9-Appendix; LM 22-23 Dec 2025); AAG 2024-25 (LM 30 Jun 2026); 2025-26 page empty. Frequency: Annual. Lag: Finance Accounts ~9 months; AAG ~15 months.
- Coverage: 1976-77 to 2024-25. Basis: Current prices Rs crore.
- Key series: FA Statements - Receipts/disbursements by major head, debt, loans, guarantees, investments [Rs crore]; AAG App. 12 - Object-head expenditure 2024-25 (salaries, pension, GIA, subsidies 4,41,861.69, grants for capital assets) [Rs crore].
- SAM use: audited Union account; economic classification via object heads.
- Quirks: Object-head table extracts misaligned. Excludes IEBR of PSUs.
- Licence: No explicit licence (CGA Copyright-Policy page body is empty; footer 'All rights reserved').

**An Economic and Functional Classification of the Central Government Budget** (`dea_economic_functional_classification`, corrected)

- Publisher: DEA Economic Division, MoF. Landing: <https://dea.gov.in/reports-central-government-budget>
- Access: PDF (use dea.gov.in without www; www host TLS name mismatch). Requires: none. Formats: pdf.
- Latest: 2019-11-07 - 2017-18 edition published 07.11.2019; columns 2015-16 (A), 2016-17 (RE), 2017-18 (BE). Frequency: Was annual; no edition after 2017-18. Lag: n/a.
- Coverage: 2005-06 to 2015-16 (Latest ACTUALS year is 2015-16). Basis: Current prices; NAS concepts.
- Key series: EC - Economic classification: consumption, capital formation, transfers by recipient [Rs crore].
- SAM use: methodology template to rebuild Union economic classification for the SAM year.
- Quirks: Totals deliberately differ from budget documents. DEA 'Indian Public Finance Statistics' shows 'No Data Available'.
- Licence: DEA copyright policy: reproduction free of charge after taking permission by e-mail; no GODL.

**DEA public debt: Quarterly Report on Public Debt Management (ownership of G-secs/T-bills), Status Paper on Government Debt, Central Government Debt data, Market Borrowing statement** (`dea_public_debt_reports`, corrected)

- Publisher: DEA (Budget Division / PDMC), MoF. Landing: <https://dea.gov.in/reports-public-debt-management>
- Also referred to (gap map) as: `dea_public_debt_quarterly`.
- Access: PDF (tables need extraction); paginated listing ?page=1..7. dea.gov.in serves an incomplete TLS chain: Python/OpenSSL clients fail with CERTIFICATE_VERIFY_FAILED unless the OS trust store is used (truststore) - Windows curl/Schannel works. Requires: none. Formats: pdf.
- Latest: 2026-08-13 - QR Jan-Mar 2026 (13 Jul 2026); Central Govt Debt quarter ended Mar 2026 (30 Jun 2026); Market Borrowing 2025-26 (13 Aug 2026); Status Paper 2023-24 (29 Aug 2025). Apr-Jun 2026 QR not yet out (last year's came 3 Oct 2025). Frequency: QR quarterly; Status Paper annual. Lag: QR ~3.5 months; Status Paper ~17 months.
- Coverage: 2022 to 2026-03 (QR archive back to at least Jan-Mar 2022). Basis: % of outstanding; Rs crore stocks.
- Key series: QR Table 4.4 - Ownership of GoI dated securities Mar-2026: banks 32.99, insurance 25.59, RBI 17.59, pension 4.62, PF 4.50, FPI 2.95, MF 1.60, Others (mixed) [%]; QR Table 4.5 - Ownership of T-bills [%]; Status Paper - Central government liabilities incl. external, small savings, reserve funds [Rs crore].
- SAM use: holders of Central debt by sector (Flow of Funds); interest allocation to holders.
- Quirks: 'Others' mixes State govts, DICGC, PSUs, trusts, foreign central banks, HUF/individuals. State securities ownership not here (RBI HBS T107). Odd quarter labels ('Q1' = quarter ended March).
- Licence: DEA copyright policy: reproduction free of charge after taking permission by e-mail; no GODL.

**GST revenue statistics (monthly revenue report PDF, state-wise collection/refund XLSX, IGST settlement XLSX)** (`gstn_gst_statistics`, disputed)

- Publisher: Goods and Services Tax Network (GSTN). Landing: <https://www.gst.gov.in/download/gststatistics>
- Access: Direct file downloads from tutorial.gst.gov.in (robots Allow: /); listing page on www.gst.gov.in behind F5 challenge (not bypassed). gst.gov.in Terms list web scraping as unauthorised (IT Act s.43/45). Download named files only; ask permission for automation. Requires: none. Formats: xlsx, pdf.
- Latest: unknown - August 2026 report (gross 1,99,853 cr, +14.8% vs revised Aug-25 1,74,116); XLSX 2026-27 data to 31 Jul 2026. Frequency: Monthly. Lag: Monthly PDF: publication date not established (server Last-Modified reflects a bulk sync); XLSX: data to end-July posted by late September, i.e. ~2 months.
- Coverage: 2017-18 to 2026-08. Basis: Current prices Rs crore; provisional; cash/portal basis.
- Key series: All-India - CGST/SGST/IGST domestic, imports, gross, refunds, net; FY 2025-26 gross 22,27,095.73, net 19,34,465.16 [Rs crore]; state-wise - Domestic collections and refunds by state [Rs crore]; IGST settlement - Regular/ad-hoc IGST settlement to states [Rs crore].
- SAM use: GST by instrument; import IGST; Union vs State GST split; state tax incidence.
- Quirks: DISPUTED: whether totals exclude compensation cess (see verification). PIB stopped monthly GST press releases after May-2024 data (secondary sources only). GSTN figures differ from Budget/CGA accounting. Monthly PDF comparators use revised ex-cess prior-year numbers. File Last-Modified 2026-09-25 on all files (bulk sync).
- Licence: No GODL. gst.gov.in Terms prohibit scraping; GST Council copyright: reproduce after permission by e-mail.
- Not confirmed: latest_release.date (publication date not established).

**CBDT Direct Tax Time Series (FY 2000-01 onward) and Income Tax Return statistics** (`cbdt_time_series`, unverified)

- Publisher: Central Board of Direct Taxes. Landing: <https://www.incometaxindia.gov.in/documents/d/guest/final-time-series-data-pdf>
- Access: PDF (site blocks automated clients: HTTP 403 incl. robots.txt). Owner must download manually in a browser or request files from CBDT. Requires: manual_download. Formats: pdf.
- Latest: unknown - Time series to FY 2024-25 (provisional; net direct taxes Rs 22.26 lakh cr; direct tax/GDP 6.73% on old base) - secondary source dated 24 Nov 2025. Frequency: Annual. Lag: ~7-12 months.
- Coverage: 2000-01 to 2024-25. Basis: Current prices; ratios on old 2011-12 base.
- Key series: time series - Gross/net direct taxes; corporate vs personal; refunds; cost of collection; taxpayers [Rs crore]; ITR stats - Returns by income range (AY-wise) [number / Rs].
- SAM use: direct taxes by corporations vs households; income distribution by tax bracket (cross-check).
- Quirks: incometax.gov.in statistics page HTTP 500. Possible future switch to 'tax year' labels under Income-tax Act 2025 (unverified).
- Licence: unverified (site 403).

**CBIC customs and central excise revenue (via Receipt Budget and CGA)** (`cbic_indirect_tax`, verified)

- Publisher: CBIC; published through Union Budget and CGA. Landing: <https://www.cbic.gov.in/>
- Access: CBIC site is a JS app with no revenue statistics; use Receipt Budget (0037, 0038) and CGA. Requires: none. Formats: xlsx.
- Latest: 2026-02-01 - Actuals 2024-25 in Budget 2026-27: customs 2,33,201 cr; union excise 3,00,253 cr. Frequency: Annual (budget). Lag: ~10 months.
- Coverage: 2024-25. Basis: Current prices Rs crore.
- Key series: 0037 - Customs incl. BCD, cesses [Rs crore]; 0038 - Union excise incl. petroleum; additional excise on tobacco from 1 Feb 2026 [Rs crore].
- SAM use: import duties; excise on petroleum and tobacco.
- Quirks: No product-wise customs revenue; Health Security se National Security Cess on pan masala from 1 Feb 2026.
- Licence: indiabudget.gov.in copyright policy: may not be reproduced without Ministry of Finance permission; no GODL.

**PPAC: Contribution of Petroleum Sector to Central and State Exchequer** (`ppac_petroleum_exchequer`, verified)

- Publisher: Petroleum Planning & Analysis Cell, MoPNG. Landing: <https://ppac.gov.in/prices/contribution-to-central-and-state-exchequer>
- Also referred to (gap map) as: `ppac_exchequer`.
- Access: HTML page with one XLS ('Download Current FY Report'); file name carries an upload timestamp - scrape the link. XLS (OLE2) needs xlrd. Server Last-Modified 25 Sep 2026 differs from the in-file 'Table Posted: (17.07.2026)'. Requires: none. Formats: xls, html.
- Latest: 2026-07-17 - Table posted 17.07.2026, period 2014-15 to 2025-26 (P); 2023-24 Central excise on petroleum 2,73,683.88, customs 13,133.73, cess on crude 19,580.39 (Rs crore). Frequency: Annual (current FY report updated). Lag: ~6 months.
- Coverage: 2014-15 to 2025-26. Basis: Current prices Rs crore.
- Key series: Centre - Customs, excise, cess on crude, NCCD from petroleum [Rs crore]; States - VAT/sales tax/SGST on petroleum [Rs crore].
- SAM use: petroleum product taxes (Union excise and State VAT) allocation.
- Quirks: File name changes with each upload (timestamp prefix). Sheet 'Anx 1': Centre (cess, royalty, customs, NCCD, excise, IGST, CGST, dividends/income tax) and States (sales tax/VAT, SGST, royalty, dividends). Gap map refers to this entry as 'ppac_exchequer'.
- Licence: PPAC Terms & Conditions: material 'may be reproduced free of charge', accurately and not in a misleading context; permission does not extend to third-party copyright material.

**CAG Report No. 6 of 2026 (Financial Audit) on Accounts of the Union Government 2024-25** (`cag_union_accounts_audit_2024_25`, verified)

- Publisher: Comptroller and Auditor General of India. Landing: <https://cag.gov.in/webroot/uploads/download_audit_report/2026/6of2026UGEng-069ce496f1158e0.22682438.pdf>
- Access: PDF. Requires: none. Formats: pdf.
- Latest: 2026-04-02 - Report 6 of 2026, reportedly tabled 2 Apr 2026. Frequency: Annual. Lag: ~12 months.
- Coverage: 2024-25 to 2024-25. Basis: Rs crore.
- Key series: audit - Misclassification (Other Expenditure/Receipts minor heads), unaccounted expenditure [Rs crore].
- SAM use: accuracy caveats for Union economic reclassification.
- Quirks: Tabling date from secondary source.
- Licence: CAG copyright policy: may be reproduced free of charge if accurate and not misleading, source prominently acknowledged.

**National Small Savings: collections under National Savings Schemes (National Savings Institute) and NSSF** (`nsi_small_savings_collections`, verified)

- Publisher: National Savings Institute, Department of Economic Affairs, Ministry of Finance. Landing: <https://www.nsiindia.gov.in/InternalPage.aspx?Id_Pk=152>
- Access: HTML tables (ASP.NET WebForms; scheme-wise and state-wise years are selected by postback). Page 152 is a static HTML table. Year selection on pages 313/153 uses postbacks (not automated in Phase 0). Phase 1: the site uses ASP.NET cookieless sessions (redirect to /(S(...))/InternalPage.aspx); the redirect is ordinary and needs no cookie jar. Official alternatives for the SAM: Receipt Budget Annex 8 (Sources and Application of NSSF, Actual 2023-24) and Union Finance Accounts 2023-24 Statement 16 (position of NSSF), both open PDFs. Requires: none. Formats: html.
- Latest: unknown - Annual table to 2025-26: gross deposits 12,53,943.04, net 4,31,205.74 (Rs crore). Publication date not shown. 2023-24 net collection 4,21,678.35 matches Receipt Budget 2025-26 Annex 8 'Accretion to liabilities' total 4,21,678.36. Frequency: Annual (table extended each year). Lag: unknown (2025-26 present by 2026-09-29).
- Coverage: 2002-03 to 2025-26 (Withdrawals column is '-' from 2023-24 (only gross and net given)). Basis: Current prices, Rs crore (flows).
- Key series: Id_Pk=152 - Collection under National Savings Schemes: gross deposits, withdrawals, net, 2002-03 to 2025-26 [Rs crore]; Id_Pk=313 / 153 - Scheme-wise and state-wise collections by year [Rs crore (not checked)].
- SAM use: household deposits into small savings (household -> government financing); NSSF investment in Centre and State securities (with DEA public-debt reports and Budget 'Securities against Small Savings').
- Quirks: NSSF is a Public Account fund (since 1 Apr 1999); page 157: 'All deposits received under National Saving Schemes are credited to the National Small Saving Fund'. The Union's liability side is already in dea_public_debt_reports (QR Jan-Mar 2026 lines 'Securities against small savings', 'National Small Savings Fund', memo 'Securities issued by States to NSSF', 'NSSF Loans to other Public Agencies') and in Budget at a Glance 'Securities against Small Savings' (2024-25 Actuals 4,29,502; 2026-27 BE 3,86,772). NSSF audited annual accounts were not located. 2016-17 value carries four decimals.
- Licence: NSI Copyright Policy: 'may not be reproduced partially or fully, without due permission from NIC'; source to be acknowledged (read 2026-09-29 at InternalPage.aspx?Id_Pk=43).
- Not confirmed: latest_release.date (no publication date on the page); scheme-wise and state-wise tables (postback, not automated).

**Public Enterprises Survey (CPSE accounts), Department of Public Enterprises - could not be accessed in Phase 0** (`dpe_public_enterprises_survey`, unverified)

- Publisher: Department of Public Enterprises, Ministry of Finance. Landing: <https://www.dpe.gov.in/>
- Access: Unknown. dpe.gov.in is a client-rendered Next.js site; content is loaded by JavaScript from a separate CMS API. curl 2026-09-29: https://dpe.gov.in/ -> 200 (6,589 B shell); /en/public-enterprises-survey -> 200 (7,322 B shell, no survey text); /sitemap.xml -> 200 HTML shell; /sites/default/files/ -> 404. WebFetch of /en/public-enterprises-survey -> 403. robots.txt 'User-agent: * Allow: /'. The CMS API key embedded in the JavaScript was not used. Browser rendering was unavailable (several Chrome browsers connected, none selected). Owner to open the site in a browser. Phase 1 re-check 2026-09-29: /en/public-enterprises-survey still a 7,322 B Next.js shell (buildId JfZfdjzEVh46NBfNbAyVT); the page bundle loads content from a digifootprint.gov.in CMS with a key embedded in the JavaScript. Using that key or the owner's browser is outside DECISIONS D1-1, so the survey stays unread. Not needed for any gap-map cell: CPSE dividends come from Receipt Budget non-tax revenue (ntr.xls) and Finance Accounts Statement 11; public NFC aggregates from NAS 1.9/7.1A. Requires: manual_download. Formats: unknown.
- Latest: unknown - unverified: latest edition and date could not be read. Frequency: Annual (per DPE practice; unverified). Lag: unknown.
- Coverage: n/a (unverified). Basis: Company accounts (current prices); unverified.
- Key series: CPSE financials - Expected: CPSE balance sheets, profit and loss, dividends and taxes paid to the Centre, by cognate group (unverified) [unverified].
- SAM use: public vs private non-financial corporations (split of NFC accounts); dividends and interest from CPSEs to the Centre (cross-check).
- Quirks: Relevance: SPEC section 4 asks for public/private NFC split. NAS 2026 already gives public-sector aggregates: statement 1.9 (saving of public NFCs, departmental and non-departmental) and 7.1A/7.1B ('OUTPUT, VALUE ADDED, CE, OS BY INDUSTRY FOR PUBLIC SECTOR' / '... FOR PRIVATE CORPORATIONS', read from the XLSX headers), so the SAM does not depend on this survey; it would add CPSE-level detail and a cross-check only. Same-server SPA trap as MoSPI: HTTP 200 does not prove a page exists.
- Licence: unverified (site content not readable without JavaScript).
- Not confirmed: everything except the site's existence.

### 3.7 State government finances and Centre-State transfers (`state_fiscal`)

**State Finances: A Study of Budgets of 2025-26** (`rbi_state_finances_study`, corrected)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=State%20Finances%20:%20A%20Study%20of%20Budgets>
- Access: XLSX and PDF on rbidocs (hashed URLs per edition). rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: xlsx, pdf.
- Latest: 2026-01-23 - 2025-26 edition: 2023-24 Accounts, 2024-25 RE, 2025-26 BE; 2026-27 edition not yet out (expected ~Dec 2026-Jan 2027, inferred). Frequency: Annual (Dec/Jan). Lag: Accounts ~21-22 months.
- Coverage: 2002 to 2025-26. Basis: Current prices. Units differ by table (read from each XLSX header on 2026-09-29): Rs crore for most statements and appendix tables, per cent for ratio statements, Rs lakh for Appendices I-IV. %GDP ratios old base (inferred).
- Key series: Statements 2-5, 7, 9, 11-13, 16-19, 21, 23, 25, 28-31, 36, 37 - State-wise levels: revenue deficit (2), GFD (3), GFD decomposition (4), GFD financing 2023-24/2024-25/2025-26 (5, 7, 9), development (11) and non-development (12) expenditure, interest payments (13), loans from Centre (16), devolution and transfers from Centre (17), liabilities (18, 19), market borrowings (21), SGS maturity (23), treasury-bill investments (25), guarantees (28), wages and salaries (29), O&M (30), social sector expenditure (31), subsidies (36), health and WSS (37). Statements 11-13, 16 and 17 also carry 'Variation (Per cent)' columns [Rs crore]; Statements 1, 6, 8, 10, 14, 15, 20, 24, 26, 27, 32-35 - Ratios and shares: fiscal indicators (1), GFD financing shares (6, 8, 10), tax revenue shares incl. each state's share in central taxes (14), non-tax revenue shares (15), liabilities/GSDP (20), maturity shares (24), education and health shares (26, 27), social sector share (32), revenue receipts/expenditure/development ratios to GSDP (33-35) [per cent]; Statement 22 - Published as PDF only (no XLSX in the 2025-26 listing); unit not checked [unverified]; Appendix Tables 1-9, 11, 13 - All-states deficits (1), devolution and transfers from the Centre (2), development/non-development expenditure (3-6), social sector expenditure (7), GFD decomposition (8) and financing (9), outstanding liabilities (11), market borrowings (13) [Rs crore]; Appendix Tables 10, 12 - GFD financing and outstanding liabilities as per cent of total [per cent]; Appendices I-IV (nAPPENDIX...) - State-wise revenue receipts (I; SGST, VAT, excise, stamps, vehicles, electricity duty), revenue expenditure (II), capital receipts (III) and capital expenditure (IV) [Rs lakh (divide by 100 for Rs crore)].
- SAM use: State current and capital accounts; Centre -> State transfers; State GFD financing; State debt.
- Quirks: UTs with legislature in some statements. Units are mixed (Rs crore / per cent / Rs lakh): read the unit line in row 2 of every sheet and normalise; Appendices I-IV are in Rs lakh. Statement 22 is PDF only. Some crore statements embed 'Variation (Per cent)' columns.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**Sixteenth Finance Commission relevant-data files (KFI, transfers, subsidies, salaries, SPSEs)** (`fc16_relevant_data`, verified)

- Publisher: Sixteenth Finance Commission. Landing: <https://fincomindia.nic.in/commission-reports-sixteenth>
- Access: Direct bulk XLSX/PDF download (curl works). Requires: none. Formats: xlsx, pdf.
- Latest: 2026-02-05 - Files LM 3-5 Feb 2026 (SPSE file 9 Mar 2026). Frequency: One-off per Finance Commission. Lag: KFI to 2023-24 accounts.
- Coverage: 1952-53 to 2025-26 (KFI 2011-12..2023-24 (column '2024' = FY 2023-24); transfers 1952-53..2025-26 BE; subsidies 2018-19..2025-26 BE). Basis: Current Rs crore; GSDP old base (All-India 2023-24 3,01,22,956).
- Key series: KFI - ~95 items: taxes by type (sales tax, SGST, excise, vehicles, stamps), share in Union taxes, grants, interest, pensions, salaries, assignment to local bodies, capex, liabilities, deficits (2023-24 RR 37,93,278; SGST 8,00,112; share 11,29,397; public debt 67,87,363) [Rs crore]; Transfers - States' share, FC and non-FC grants, totals (2023-24+ from Union Budget Statement 18) [Rs crore]; Subsidies - State x sector (21 states + Union) [Rs crore]; Salary / SPSE - State salaries 2011-12..2023-24; SPSE financials 2022-23 [Rs crore].
- SAM use: State current account by type; Centre -> State transfers time series; subsidies by sector; State -> local bodies; State debt.
- Quirks: KFI: 28 states + undivided AP, no UTs; debt-flow rows all zero; GST compensation loans treated as grants; 'some nil values may be missing'.
- Licence: No explicit licence found (copyright_policy page empty; footer 'Content Owned by Sixteenth Finance Commission ... All Rights Reserved').

**FC16 ULB Data Dump (Cityfinance)** (`fc16_ulb_cityfinance_dump`, verified)

- Publisher: Sixteenth Finance Commission (data from MoHUA / cityfinance.in). Landing: <https://fincomindia.nic.in/asset/doc/commission-reports/16th-FC/relevant-data/FC16%20ULB%20Data%20Dump%20Cityfinance.xlsx>
- Access: Bulk XLSX (10.4 MB). Requires: none. Formats: xlsx.
- Latest: 2026-02-19 - LM 2026-02-19; data to 2023-24. Frequency: One-off. Lag: ~2 years.
- Coverage: 2015-16 to 2023-24 (3,725 ULBs (2015-16) to 4,620 (2023-24)). Basis: Current prices; units appear to be rupees (unlabelled).
- Key series: ULB - Property tax, other tax, fees, own revenue, CSS, FC grants, SFC devolution, salaries, pension, O&M, interest, capex (49 columns) [Rs].
- SAM use: urban local government account.
- Quirks: Data-quality jumps (e.g. Khategaon tax revenue 11x in one year).
- Licence: No explicit licence found (copyright_policy page empty; footer 'Content Owned by Sixteenth Finance Commission ... All Rights Reserved').

**CAG State Finance Accounts and Appropriation Accounts (per state)** (`cag_state_finance_accounts`, corrected)

- Publisher: Comptroller and Auditor General (Accountants General). Landing: <https://cag.gov.in/en/state-accounts-report>
- Access: PDF per state; machine-readable FA&AA data on CAG SharePoint behind Microsoft login. Public PDFs need no login. Requires: login. Formats: pdf.
- Latest: 2026-03 - 2024-25 Finance Accounts posted for all states with pages except Goa (Goa, Delhi, Puducherry pages empty). Frequency: Annual. Lag: ~9-12 months.
- Coverage: 2021-22 to 2024-25. Basis: Current Rs crore; audited.
- Key series: FA Vol I/II - Financial position, receipts and disbursements, receipts by source, expenditure by function/nature, borrowings [Rs crore].
- SAM use: audited State accounts; State -> local bodies.
- Quirks: URL parameter spelled 'defuat_state_id'; filenames vary.
- Licence: CAG copyright policy: may be reproduced free of charge if accurate and not misleading, source prominently acknowledged.

**CAG Monthly Key Indicators (Accounts at a Glance) of State Governments** (`cag_monthly_key_indicators`, corrected)

- Publisher: Comptroller and Auditor General. Landing: <https://cag.gov.in/en/state-accounts-report>
- Access: PDF per state per month; Excel versions on SharePoint (login). Requires: none. Formats: pdf.
- Latest: 2026-09 - August 2026 for 22 states; July for Arunachal, Nagaland; May for Manipur. Frequency: Monthly. Lag: ~1-2 months.
- Coverage: 2021-22 to 2026-08. Basis: Current Rs crore; unaudited.
- Key series: MKI - Revenue receipts (GST, stamps, land revenue, sales tax, excise, share of Union taxes), grants, borrowings, expenditure [Rs crore].
- SAM use: nowcasting State accounts.
- Quirks: Cumulative to date; inconsistent file names.
- Licence: CAG copyright policy: may be reproduced free of charge if accurate and not misleading, source prominently acknowledged.

**CAG Publication on State Finances 2024-25 (3rd edition; all 28 states, 10-year)** (`cag_state_finances_publication`, corrected)

- Publisher: Comptroller and Auditor General. Landing: <https://cag.gov.in/en/page-statefinances24-25>
- Access: 2024-25: Tableau Public workbook (personal profile) + press release; 2023-24: PDF (51 MB) + dashboards. Requires: none. Formats: pdf, tableau.
- Latest: 2026-06-16 - State Finances 2024-25 (2015-16 to 2024-25): RR Rs 40.52 lakh cr; expenditure 51.20 lakh cr (15.78% GSDP); liabilities 90.51 lakh cr at 31 Mar 2025. Frequency: Annual. Lag: ~15 months.
- Coverage: 2015-16 to 2024-25. Basis: Current Rs crore; audited; GSDP base of ratio unverified.
- Key series: annexures - State-wise receipts, SOTR components, subsidies, committed expenditure, debt, guarantees [Rs crore].
- SAM use: audited all-state accounts for 2024-25 reference year.
- Quirks: No 2024-25 PDF/annexure located, although the 16 Jun 2026 press release calls it 'a single, accessible volume'. Tableau on a personal profile - provenance to confirm with CAG.
- Licence: CAG copyright policy: may be reproduced free of charge if accurate and not misleading, source prominently acknowledged.

**CAG State Finances Audit Reports 2024-25 (per state)** (`cag_sfar_2024_25`, verified)

- Publisher: Comptroller and Auditor General. Landing: <https://cag.gov.in/en/audit-report/details/126203>
- Access: PDF per state. Requires: none. Formats: pdf.
- Latest: 2026 - Several 2024-25 SFARs (e.g. Report No. 1 of 2026; HP, Nagaland, Manipur, TN). Frequency: Annual. Lag: ~12 months.
- Coverage: 2024-25 to 2024-25. Basis: Rs crore.
- Key series: SFAR - SPSEs, guarantees, off-budget borrowings, committed expenditure [Rs crore].
- SAM use: State public corporations and liabilities.
- Quirks: None recorded in Phase 0.
- Licence: CAG copyright policy: may be reproduced free of charge if accurate and not misleading, source prominently acknowledged.

**Union Budget Expenditure Profile Statement 18 and Demand No. 42 (Transfers to States)** (`union_budget_transfers_to_states`, verified)

- Publisher: Ministry of Finance, Budget Division. Landing: <https://www.indiabudget.gov.in/doc/eb/vol1.pdf>
- Access: PDF (XLSX stat18 also available). Requires: none. Formats: pdf, xlsx.
- Latest: 2026-02-01 - Budget 2026-27: Statement 18 grand total (excl. devolution) 9,38,628.46 (A 2024-25) ... 10,94,513.94 (BE 2026-27). Frequency: Annual. Lag: ~10 months.
- Coverage: 2024-25 to 2026-27. Basis: Current Rs crore.
- Key series: St 18 - Transfers excl. devolution: NDRF/EAP/SASCI loans, FC grants, CSS, UTs [Rs crore]; BAG - Devolution + all transfers [Rs crore].
- SAM use: Centre -> State grants and loans.
- Quirks: Mixes grants and loans (EAP loans 34,409.84; SASCI 1,49,483.73 in 2024-25 A). CSS includes releases to implementing agencies outside state treasuries. GST compensation phased out from 2026-27.
- Licence: indiabudget.gov.in copyright policy: may not be reproduced without Ministry of Finance permission; no GODL.

**PIB / MoF tax devolution instalment releases (state-wise)** (`pib_tax_devolution_releases`, unverified)

- Publisher: Ministry of Finance via PIB. Landing: <https://www.pib.gov.in/PressReleasePage.aspx?PRID=2292912>
- Access: HTML press release (curl with cookie jar). Requires: none. Formats: html.
- Latest: 2026-08-01 - 1 Aug 2026 additional instalment Rs 1,09,019 cr (UP 19,208 = 17.619%). Frequency: Irregular. Lag: Same day.
- Coverage: n/a. Basis: Rs crore.
- Key series: devolution - State-wise instalment [Rs crore].
- SAM use: check on devolution by state.
- Quirks: Only extra instalments get press releases; a secondary outlet misreported UP as 17,908.
- Licence: not established (PIB copyright URL errors).
- Not confirmed: license (PIB copyright page errored; no terms text read).

**PRS Legislative Research state budget analyses and State of State Finances** (`prs_state_budget_analyses`, verified)

- Publisher: PRS Legislative Research. Landing: <https://prsindia.org/budgets/states>
- Access: HTML and PDF. Requires: none. Formats: html, pdf.
- Latest: 2025-11-14 - 30 state budget analyses 2026-27; State of State Finances 2025-26 (PDF LM 14 Nov 2025). Frequency: Annual. Lag: Weeks.
- Coverage: 2016-17 to 2026-27. Basis: Current Rs crore.
- Key series: analyses - Per-state receipts, expenditure, deficits, debt, GSDP projections [Rs crore].
- SAM use: cross-check only.
- Quirks: Secondary; UP 2026-27 GSDP growth 28% anomaly.
- Licence: Creative Commons Attribution 4.0 International.

**GST monthly revenue report: state-wise SGST pre/post settlement** (`gst_monthly_state_revenue`, verified)

- Publisher: GSTN / CBIC. Landing: <https://tutorial.gst.gov.in/downloads/news/aug_2026_gst_revenue_report_final_for_publishing_monthly.pdf>
- Access: Monthly PDF; file name changes monthly. Requires: none. Formats: pdf.
- Latest: unknown - August 2026 report. Frequency: Monthly. Lag: unknown (publication date not established; server Last-Modified reflects a bulk sync).
- Coverage: 2026-08. Basis: Rs crore; collections basis.
- Key series: Tables 1-4 - SGST and SGST portion of IGST settled; FY to date; state growth; state collections by formation [Rs crore].
- SAM use: State GST by state; IGST settlement flows.
- Quirks: September URL 404 (not yet). File Last-Modified is a bulk-sync time, not a release date.
- Licence: See gstn_gst_statistics (no GODL; permission needed).
- Not confirmed: latest_release.date (publication date not established); release_lag.

**RBI Report on Municipal Finances** (`rbi_municipal_finances`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Report%20on%20Municipal%20Finances>
- Access: XLSX/PDF on rbidocs. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: pdf, xlsx.
- Latest: 2024-11-13 - Report on Municipal Finances. Frequency: Irregular (2022, 2024). Lag: unverified.
- Coverage: n/a (Data years unverified). Basis: Current prices.
- Key series: Statements 1-8 - Municipal corporation receipts and expenditure by state [Rs crore].
- SAM use: urban local government.
- Quirks: Municipal corporations only.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.
- Not confirmed: release_lag.

**RBI Finances of Panchayati Raj Institutions 2020-21 to 2022-23** (`rbi_pri_finances`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/OccasionalPublications.aspx?head=Finances%20of%20Panchayati%20Raj%20Institutions>
- Access: XLSX on rbidocs. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: pdf, xlsx.
- Latest: 2024-01-24 - Released 24 Jan 2024. Frequency: One-off. Lag: ~1 year.
- Coverage: 2020-21 to 2022-23. Basis: Current prices.
- Key series: App. I/II - Village panchayat revenue receipts and expenditure by state [Rs crore].
- SAM use: rural local government.
- Quirks: Single edition.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**RBI Handbook of Statistics on Indian States 2024-25 (fiscal tables)** (`rbi_handbook_indian_states`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook%20of%20Statistics%20on%20Indian%20States>
- Access: XLSX/PDF on rbidocs. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: xlsx, pdf.
- Latest: 2025-12-11 - 2024-25 edition. Frequency: Annual. Lag: ~1 year.
- Coverage: n/a. Basis: Current prices; GSDP old base.
- Key series: T164-T178 - State-wise GFD, revenue expenditure, own tax/non-tax, interest, capex, social expenditure, liabilities, guarantees (177), market borrowings (178) [Rs crore].
- SAM use: State fiscal time series.
- Quirks: Derived from RBI SF study.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**eGramSwaraj Receipt and Expenditure Analysis Report (Union XV FC grants to PRIs)** (`egramswaraj_panchayat_accounts`, unverified)

- Publisher: Ministry of Panchayati Raj. Landing: <https://egramswaraj.gov.in/RecExpReportNew.do?finYear=2023-2024&scheme_uid=0>
- Access: HTML report (JS-loaded) with spreadsheet download. Requires: none. Formats: html, xlsx.
- Latest: n/a - FY 2020-21 to 2026-27. Frequency: Live. Lag: Near real-time.
- Coverage: 2020-21 to 2026-27. Basis: Current prices.
- Key series: XVFC - Receipts/expenditure of XV FC basic (untied) and tied grants by Zilla/Block/Village tier [Rs].
- SAM use: rural local government (FC grants only).
- Quirks: Not full panchayat finances.
- Licence: not checked.
- Not confirmed: license (not checked); latest_release.date.

### 3.8 Markets and non-bank financial sector (`markets_finsector`)

**SEBI Bulletin (monthly) with Annexure Tables (Excel)** (`sebi_bulletin_monthly`, corrected)

- Publisher: Securities and Exchange Board of India. Landing: <https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=4&ssid=80&smid=0>
- Access: One XLSX per issue (67 sheets) + PDF; scrape listing for file names. Download free; permission (e-mail) needed before republication; NSDL/AMFI/exchange-sourced tables may need original holders' authorisation. Requires: none. Formats: xlsx, pdf.
- Latest: 2026-09-23 - September 2026 issue (data to 31 Aug 2026); August issue 2026-08-27 (data to 31 Jul 2026). Frequency: Monthly. Lag: ~3-4 weeks.
- Coverage: 2025-04 to 2026-08 (Each issue: previous FY + current FY months; format changed Oct 2025). Basis: Nominal Rs crore (some US$ mn); T1 GDP denominator changes between issues (Aug: FY26 PE Rs 346.36 lakh cr; Sep: Budget FY27 Rs 393 lakh cr); only IIP labelled base 2022-23; CPI base 2024.
- Key series: T6/T7 - Primary market resource mobilisation by instrument; by financial/non-financial x private/public [Rs crore]; T12-T14 - QIPs; preferential; private placement of corporate debt (FY26 1,924 issues, 8,99,735.8 cr) [Rs crore]; T19-T21 - Category-wise cash turnover shares [%]; T56 - FPI gross/net (FY26 net -1,52,691.03 cr; Aug-2026 +25,491.55); source NSDL [Rs crore / US$ mn]; T60 - MF resource mobilisation (FY26 net 7,36,020.9; AUM 73,73,377) [Rs crore]; T1 - Mcap and Mcap/GDP [Rs lakh crore].
- SAM use: equity and bond issuance by NFC/FC; RoW portfolio flows; MF liabilities; markets time series.
- Quirks: Live formulas (read cached values). Month columns Excel dates with inconsistent day. Column drift between issues (Sep T56 dropped cumulative column). Never splice T1 ratios across issues. SEBI T60 vs AMFI Aug-2026 net 41,383.43 vs 41,353.60.
- Licence: SEBI website policy: reproduction free of charge after permission by e-mail; permission does not extend to third-party copyright material (NSDL, AMFI, BSE, NSE sourced tables).

**SEBI Handbook of Statistics on Indian Securities Market 2025-26 (per-table XLSX)** (`sebi_handbook_statistics`, verified)

- Publisher: SEBI. Landing: <https://www.sebi.gov.in/reports-and-statistics/publications/aug-2026/handbook-of-statistics-2025-26_103700.html>
- Access: PDF contents page with 153 links to per-table XLSX. Requires: none. Formats: xlsx, pdf.
- Latest: 2026-08-17 - Handbook 2025-26 (to Mar 2026). Frequency: Annual edition. Lag: ~4.5 months.
- Coverage: 2012-13 to 2025-26. Basis: Nominal Rs crore.
- Key series: T11 - Outstanding corporate bonds end-Mar 2026: 59,09,146.74 (financial 35,63,723; non-financial 23,45,423) [Rs crore]; T14 - Funds mobilised by all instruments FY26 13,92,348.34 (3,828 issues) [Rs crore]; T58-T63 - Foreign investment inflows; FPI trends; custodian AUC [Rs crore / US$ mn]; T64-T72 - MF mobilisation by category; SIPs; unit holding Mar-2026 (corporates 27,03,762; HNI 25,96,067; retail 19,99,768; banks 73,780) [Rs crore].
- SAM use: NFC/FC issuance; bond stock by issuer sector; MF liabilities by holder; RoW portfolio flows/stocks.
- Quirks: T11 reclassification break 2023-24 -> 2024-25 (listed NFC 14,67,027 -> 10,53,958; listed FC 23,31,582 -> 32,01,537). T58 garbled rupee glyph. T72 has no FPI category.
- Licence: SEBI website policy: reproduction free of charge after permission by e-mail; permission does not extend to third-party copyright material (NSDL, AMFI, BSE, NSE sourced tables).

**NSDL FPI Monitor** (`nsdl_fpi_monitor`, corrected)

- Publisher: National Securities Depository Ltd. Landing: <https://www.fpi.nsdl.co.in/web/Reports/Latest.aspx>
- Access: HTML tables; Excel export via ASP.NET postback; DII endpoint WAF-blocked. Requires: none. Formats: html.
- Latest: 2026-09-29 - Daily trends 28-Sep-2026; fortnightly sector data to 15 Sep 2026. Frequency: Daily; fortnightly sector-wise. Lag: T+1.
- Coverage: 1992-93 to 2026-09-28 (Fortnightly sector-wise from 31 Jan 2012 (352 fortnights)). Basis: Nominal Rs crore; US$ mn at daily rate.
- Key series: daily - FPI gross/net by route (equity, debt-general/VRR/FAR, hybrid, MF, AIF) [Rs crore]; fortnightly - Sector-wise FPI AUC and flows [Rs crore].
- SAM use: RoW portfolio flows (BoP cross-check).
- Quirks: Footer 'Website updated as on: 12 Sep 2026' despite daily data. Values match SEBI T56.
- Licence: Proprietary: 'Reproduction, redistribution and transmission of any information contained on the website are strictly prohibited.'.

**NSE / BSE market data (FII/DII activity, market cap, turnover) - NOT to be used** (`nse_bse_market_data`, unverified)

- Publisher: NSE; BSE Ltd. Landing: <https://www.nseindia.com/static/nse-terms-of-use>
- Access: Not accessed by design. Recommend NOT pursuing; use SEBI aggregates. Requires: paid. Formats: html, json.
- Latest: unknown - not accessed. Frequency: Daily. Lag: Same day.
- Coverage: n/a. Basis: Nominal Rs crore.
- Key series: FII/DII - Daily cash-market buy/sell/net [Rs crore].
- SAM use: substitute with SEBI T19-T21, T1, Handbook T70.
- Quirks: NSE 'simulation' clause conflicts with the ABM layer.
- Licence: NSE Terms: no automated collection; no use for 'gaming, virtual trading or simulation activities'; no reproduction. BSE clause (snippet only, unverified): reproduction prohibited.
- Not confirmed: latest_release (not accessed); BSE terms (snippet only).

**AMFI Monthly and Quarterly Mutual Fund Data** (`amfi_monthly_quarterly`, corrected)

- Publisher: Association of Mutual Funds in India. Landing: <https://www.amfiindia.com/research-information/amfi-data>
- Access: Static .xls/.pdf on portal.amfiindia.com; index JSON embedded in Next.js page. Requires: none. Formats: xls, pdf.
- Latest: 2026-09-10 - August 2026 monthly (net inflow 41,353.60; AUM 87,07,887.74 Rs crore; LM 10 Sep 2026); quarterly Apr-Jun 2026 (LM 6 Aug 2026). Frequency: Monthly; quarterly. Lag: ~10 days.
- Coverage: 1999-07 to 2026-08. Basis: Nominal Rs crore.
- Key series: MCR - Category x schemes, folios, mobilised, redemptions, net inflow, AUM; SIP columns [Rs crore].
- SAM use: MF sector flows and AUM.
- Quirks: Needs xlrd. ~30 cr gaps vs SEBI (Jul-2026 AUM 85,75,656.52 vs 85,75,626.60); Mar-2026 matches.
- Licence: AMFI Terms: personal non-commercial use only; no public display, publication or derivative works; no electronic storage of significant portions.

**CCIL Factbook 2024-25 and market statistics** (`ccil_factbook`, verified)

- Publisher: Clearing Corporation of India Ltd. Landing: <https://www.ccilindia.com/factbook>
- Access: PDF (329 pp); paid data services. Requires: none. Formats: pdf.
- Latest: 2025-11-17 - Factbook 2024-25 (uploaded ~2025-11-17). Frequency: Annual. Lag: ~7-8 months.
- Coverage: 2024-25 to 2024-25. Basis: Nominal Rs crore (settlement/turnover).
- Key series: tables - G-sec, repo, TREPS, call money turnover and category shares [Rs crore].
- SAM use: markets context (turnover only).
- Quirks: Rakshitra page 'temporarily unavailable'.
- Licence: CCIL Terms: no commercial download/publish without express written consent; no automated collection.

**RBI HBS 2025-26 market/NBFI tables (G-sec ownership, CP, CD, private placement, MF, FPI, LIC)** (`rbi_hbs_market_tables`, verified)

- Publisher: Reserve Bank of India. Landing: <https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+Economy>
- Access: Per-table XLSX on rbidocs; HTML via PublicationsView. rbidocs.rbi.org.in answers some requests with an F5/TSPD JavaScript challenge page instead of the file, still with HTTP 200, so the status code cannot detect a failed download. Re-check 2026-09-29 on a State Finances XLSX: browser User-Agent only, or User-Agent + Accept, gave 200 text/html (challenge); User-Agent + Accept + Accept-Language gave 200 and a valid XLSX; default curl has its TLS connection dropped. No challenge was solved. Phase 1 must check magic bytes (PK for XLSX, %PDF for PDF) and fail loudly on HTML. Whether sending ordinary browser headers is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access') is part of the RBI permission request (SOURCES section 5, item 1). robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 'Unauthorised Access' and rbidocs robots.txt returns the challenge page. Manual browser download is the fallback. Phase 1 refresh 2026-09-29: the same full browser header set (User-Agent, Accept, Accept-Language, Sec-Fetch-*) fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the challenge page (HTTP 200, text/html, 5,691 B) on every rbidocs file from ~15:00 IST. Per DECISIONS D1-1(b) probing stopped; www.rbi.org.in HTML pages (PublicationsView, press releases, listings) were not challenged. Treat rbidocs as intermittent: fetch at <=1 request per 5 s, stop the run on the first challenge, retry on a later day, and use the www.rbi.org.in HTML table where one exists. Requires: none. Formats: xlsx, pdf, html.
- Latest: 2026-07-31 - HBS 2025-26. Frequency: Annual. Lag: ~4 months.
- Coverage: n/a (Contents unverified (files not opened)). Basis: Nominal Rs crore.
- Key series: T107 - Ownership of Central and State Government securities (31 March) [%/Rs crore]; T213/T214 - Commercial paper; certificates of deposit [Rs crore]; T61-T68 - Private placement; MF net resources; NBFC deposits (63); PSU bonds (65); FI assistance (66); investments by LIC (67); MF AUM (68) [Rs crore]; T181 - Net FPI investment [Rs crore].
- SAM use: CGS/SGS holdings by sector; CP/CD flows; insurance assets (LIC).
- Quirks: None recorded in Phase 0.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**IRDAI Handbook on Indian Insurance Statistics 2024-25** (`irdai_handbook_insurance`, corrected)

- Publisher: Insurance Regulatory and Development Authority of India. Landing: <https://irdai.gov.in/handbook-of-indian-insurance>
- Access: Zip of XLSX (use GET; HEAD 403). Requires: none. Formats: xlsx.
- Latest: 2026-02-03 - 2024-25 edition; FY 2025-26 edition expected ~Feb 2027 (inference). Frequency: Annual (early Feb). Lag: ~10 months.
- Coverage: 2007-08 to 2024-25. Basis: Nominal Rs crore.
- Key series: T2/T3 - Life premium total and new business [Rs crore]; T20/T21 - Life insurer AUM by fund x asset (Mar-2025 67,78,660.56) [Rs crore]; T24-T26 - Life policyholders'/shareholders' accounts, balance sheet [Rs crore]; T40-T47 - Non-life premium, claims, AUM [Rs crore].
- SAM use: insurance corporations account; insurance assets by instrument; insurance service output.
- Quirks: Growth-rate rows have wrong signs (+13.8% printed '-13.83') - never parse; recompute.
- Licence: IRDAI copyright policy: 'may be reproduced free of charge in any format or media without requiring specific permission', accurate and acknowledged.

**IRDAI Monthly Business Figures** (`irdai_monthly_business_figures`, corrected)

- Publisher: IRDAI. Landing: <https://irdai.gov.in/life>
- Access: Listing with xlsx downloads. Requires: none. Formats: xlsx.
- Latest: 2026-09-15 - Life first-year premium to 31.08.2026 (09-09-2026); non-life flash to August 2026 (15-09-2026). Frequency: Monthly. Lag: ~9-17 days.
- Coverage: n/a. Basis: Nominal Rs crore.
- Key series: life - First-year premium by insurer [Rs crore]; non-life - Gross direct premium by insurer and segment [Rs crore].
- SAM use: insurance time series.
- Quirks: None recorded in Phase 0.
- Licence: IRDAI copyright policy (reproduce with acknowledgement).

**IRDAI Annual Report 2024-25** (`irdai_annual_report`, corrected)

- Publisher: IRDAI. Landing: <https://irdai.gov.in/annual-reports>
- Access: PDF (12.2 MB). Requires: none. Formats: pdf.
- Latest: 2025-12-30 - Annual Report 2024-25; 2025-26 expected ~Dec 2026. Frequency: Annual. Lag: ~9 months.
- Coverage: 2006-07 to 2024-25. Basis: Nominal Rs crore.
- Key series: AR - Premium, claims, investments [Rs crore].
- SAM use: insurance cross-check.
- Quirks: None recorded in Phase 0.
- Licence: IRDAI copyright policy (reproduce with acknowledgement).

**PFRDA NPS/APY Statistical Data and Handbook of NPS Statistics** (`pfrda_nps_statistics`, verified)

- Publisher: Pension Fund Regulatory and Development Authority. Landing: <https://www.pfrda.org.in/research-publications/statistics/statistical-data>
- Access: Direct XLSX (version query string changes). Requires: none. Formats: xlsx, pdf.
- Latest: 2026-09-29 - M6 to Aug-2026 (AUM 18,22,758.49; G-sec 8,57,490; equity 5,15,522; corporate bonds 3,87,090); M2 to Jun-2026; A2 to Mar-2025. Frequency: Monthly (M), annual (A). Lag: M6 ~1 month; M2 ~3 months; A-series >12 months.
- Coverage: 2008-04 to 2026-08. Basis: Nominal; units unlabelled, inferred Rs crore.
- Key series: M2 - Sector-wise AUM (CG, SG, corporate, all citizen, APY, ...) [Rs crore (inferred)]; M6 - Asset-class AUM [Rs crore (inferred)]; A5 - Contributions [Rs crore (inferred)].
- SAM use: pension fund account; pension assets by instrument.
- Quirks: Units inferred; HoNPSS 2025-26 not published (404).
- Licence: no explicit licence found ('(c) Copyright PFRDA. All rights reserved.').

**EPFO Annual Report and Consolidated Annual Accounts** (`epfo_annual_report_accounts`, corrected)

- Publisher: Employees' Provident Fund Organisation. Landing: <https://www.epfo.gov.in/annual-reports/>
- Access: PDF. Requires: none. Formats: pdf.
- Latest: 2026-09-16 - Annual Report 2024-25 (unaudited; contributions Rs 3,35,628.81 cr); Consolidated Annual Accounts 2022-23 (audited). Frequency: Annual. Lag: AR ~1+ year; accounts ~3 years.
- Coverage: 1982-83 to 2024-25. Basis: Nominal Rs crore.
- Key series: AR - Contributions (EPF/EPS/EDLI), investments by category [Rs crore].
- SAM use: provident fund account; PF assets.
- Quirks: Upload folder date (2025/08) is a migration stamp; exempted establishments' trusts not covered.
- Licence: EPFO copyright policy: reproduce free of charge without specific permission, with acknowledgement.

**CDSL Periodic (monthly) Depository Statistics** (`cdsl_periodic_stats`, unverified)

- Publisher: Central Depository Services (India) Ltd. Landing: <https://www.cdslindia.com/publications/periodicstats.aspx>
- Access: Monthly PDF. Requires: none. Formats: pdf.
- Latest: 2026-09-04 - August 2026 (PDF LM 4 Sep 2026). Frequency: Monthly. Lag: ~1 month.
- Coverage: 2024-08 to 2026-08. Basis: Counts; Rs crore.
- Key series: BO - Demat accounts, custody value [number / Rs crore].
- SAM use: context only.
- Quirks: NSDL depository site nsdl.co.in in a 301 loop.
- Licence: unverified (Disclaimer.aspx has no static text).
- Not confirmed: license (Disclaimer.aspx has no static text).

**SEBI Annual Report 2025-26** (`sebi_annual_report_2025_26`, verified)

- Publisher: SEBI. Landing: <https://www.sebi.gov.in/reports-and-statistics/publications/aug-2026/annual-report-2025-26.html>
- Access: PDF (full + chapters). Requires: none. Formats: pdf.
- Latest: 2026-08-06 - Annual Report 2025-26. Frequency: Annual. Lag: ~4 months.
- Coverage: 2025-26 to 2025-26. Basis: Nominal Rs crore.
- Key series: AR - Primary markets, MFs, FPIs, AIFs, intermediaries review [Rs crore].
- SAM use: reconciliation of Bulletin/Handbook totals.
- Quirks: None recorded in Phase 0.
- Licence: SEBI website policy: reproduction free of charge after permission by e-mail; permission does not extend to third-party copyright material (NSDL, AMFI, BSE, NSE sourced tables).

**SEBI MF Deployment of Funds by all Mutual Funds (stale)** (`sebi_mf_deployment_of_funds`, verified)

- Publisher: SEBI. Landing: <https://www.sebi.gov.in/statistics/mutual-fund/deployment-of-funds-by-all-mutual-funds.html>
- Access: HTML via iframe per month. Requires: none. Formats: html.
- Latest: 2025-05 - May 2025 is latest month offered. Frequency: Monthly (stopped). Lag: n/a (stale).
- Coverage: 2012 to 2025-05. Basis: Nominal Rs crore.
- Key series: deployment - MF assets by instrument [Rs crore].
- SAM use: MF asset side (stale; FY 2025-26 needs RBI FoF or estimation).
- Quirks: None recorded in Phase 0.
- Licence: SEBI website policy: reproduction free of charge after permission by e-mail; permission does not extend to third-party copyright material (NSDL, AMFI, BSE, NSE sourced tables).

**FIMMDA CP/CD traded data archive** (`fimmda_cp_cd_traded`, unverified)

- Publisher: Fixed Income Money Market and Derivatives Association of India. Landing: <https://www.fimmda.org/PageContent.aspx?Iid=MTQy>
- Access: HTML archive. Requires: none. Formats: html.
- Latest: unknown - unverified. Frequency: Daily/monthly (unverified). Lag: unverified.
- Coverage: n/a. Basis: Rs crore.
- Key series: CP/CD - Secondary-market CP and CD trades [Rs crore].
- SAM use: context; not a substitute for RBI T213/T214 issuance.
- Quirks: None recorded in Phase 0.
- Licence: not checked.
- Not confirmed: license (not checked); latest_release (not identified); release_lag.

### 3.9 International and cross-country datasets (`international`)

**OECD Inter-Country Input-Output tables (ICIO), 2025 edition** (`oecd_icio_2025`, verified)

- Publisher: OECD (STI/PIE). Landing: <https://www.oecd.org/en/data/datasets/inter-country-input-output-tables.html>
- Access: Bulk zipped CSV per year (curl with browser UA; WebFetch 403). Phase 1 check 2026-09-29: ReadMe_ICIO_small.xlsx HTTP 200, but 2016-2022_SML.zip and the OECD dataset page returned a Cloudflare 'Just a moment...' challenge (HTTP 403). Not solved (D1-1). Retry on another day; ADB MRIO or FIGARO are the open alternatives. Requires: none. Formats: csv, xlsx, rdata.
- Latest: 2026-01 - 2025 edition, second revision mid-Jan 2026 ('No further revisions are anticipated'); all files re-uploaded 18 May 2026. Frequency: ~Every 2 years. Lag: ~3 years.
- Coverage: 1995 to 2022 (80 economies + RoW; 50 ISIC Rev.4 industries; IND '2022' = FY 2022-23). Basis: Current USD mn, basic prices; India on OLD 2011-12 base (certain); official SUTs only for 2011-2019, 2020-22 OECD estimates.
- Key series: Z/FD/TLS/VA/X - Intermediate use, final demand (HFCE, NPISH, GGFC, GFCF, INVNT, DPABR), taxes less subsidies, VA, output; country IND [US$ mn].
- SAM use: A-matrix prior; imported intermediates by origin; exports by destination.
- Quirks: 166 MB zip; FX and FY/CY alignment needed.
- Licence: OECD Terms & Conditions: Data may be extracted, copied, adapted, distributed for any purpose incl. commercial, with credit to OECD (not labelled CC BY).

**OECD national Input-Output Tables 2025 edition (incl. value-added components)** (`oecd_national_iots_2025`, verified)

- Publisher: OECD. Landing: <https://www.oecd.org/en/data/datasets/input-output-tables.html>
- Access: Bulk zipped CSV. Requires: none. Formats: csv.
- Latest: 2026-01-20 - 2025 release (CSV dated 2026-01-20). Frequency: ~Every 2 years. Lag: ~3 years.
- Coverage: 1995 to 2022. Basis: Current US$ mn; old base; 2020-22 estimates.
- Key series: VA components - India 2022: VALU 3,042,971; LABR 1,025,205; NOPS 1,249,513; CFC 375,399; OTXS 392,853 [US$ mn].
- SAM use: factor split by 50 industries (labour vs capital prior).
- Quirks: Mixed income not separated from operating surplus.
- Licence: OECD Terms & Conditions: Data may be extracted, copied, adapted, distributed for any purpose incl. commercial, with credit to OECD (not labelled CC BY).

**OECD Trade in Value Added (TiVA) 2025 edition (SDMX)** (`oecd_tiva_2025`, verified)

- Publisher: OECD. Landing: <https://sdmx.oecd.org/public/rest/dataflow/OECD.STI.PIE/DSD_TIVA_MAINLV@DF_MAINLV/1.1>
- Access: SDMX API (no key). Requires: none. Formats: sdmx-ml, csv.
- Latest: unknown - 2025 edition. Frequency: With ICIO editions. Lag: ~3 years.
- Coverage: 1995 to 2022. Basis: US$.
- Key series: TiVA - Domestic VA content of exports, import content [US$ / %].
- SAM use: cross-check of trade and IO blocks.
- Quirks: None recorded in Phase 0.
- Licence: OECD Terms & Conditions: Data may be extracted, copied, adapted, distributed for any purpose incl. commercial, with credit to OECD (not labelled CC BY).
- Not confirmed: latest_release.date.

**ADB Multiregional Input-Output Tables and India national IOT** (`adb_mrio`, corrected)

- Publisher: Asian Development Bank (Key Indicators Database). Landing: <https://kidb.adb.org/globalization/current>
- Access: Direct XLSX downloads; file list in Inertia JSON. Requires: none. Formats: xlsx.
- Latest: 2025-08 - MRIO and 'IND IOT 2000, 2007-2024.xlsx' updated August 2025; no 2026 update yet. Frequency: Annual (August). Lag: ~1 year.
- Coverage: 2000 to 2024 (Year label = FY start year ('2024' = FY 2024-25)). Basis: Current US$ mn basic prices; OLD 2011-12 base (2022 VA 3,135,712 x 78.6045 = Rs 246.48 lakh cr = UN AMA old-base 246.467).
- Key series: IND IOT - 35x35 (WIOD-35), domestic and imported rows; r99 TLS, r64 VA; F1-F6 final demand [US$ mn].
- SAM use: latest free IO structure (2024) as RAS prior; import matrix.
- Quirks: r62, r63, trs rows zero for India. data.adb.org Cloudflare 403.
- Licence: KIDB terms: data 'may be copied, downloaded, distributed, adapted, duplicated, linked, displayed or included in other products for commercial and noncommercial purposes at no cost'.

**World Bank World Development Indicators** (`wb_wdi`, corrected)

- Publisher: World Bank. Landing: <https://datacatalog.worldbank.org/search/dataset/0037712/World-Development-Indicators>
- Access: REST API v2 (no key); bulk CSV. Requires: none. Formats: json, csv, xlsx.
- Latest: 2026-07-13 - API lastupdated 2026-07-13; bulk files 2026-07-17. Frequency: Several updates a year. Lag: Months.
- Coverage: 1960 to 2025. Basis: India national accounts base 2022/23, FY (2025 = FY 2025-26), VAB; values = 27 Feb 2026 SAE vintage (superseded).
- Key series: NY.GDP.MKTP.CN - GDP current LCU (2025 = 345.47 lakh cr, SAE vintage) [Rs]; BN.CAB.XOKA.CD - Current account (CALENDAR year) [US$].
- SAM use: cross-checks.
- Quirks: National accounts FY but BoP series CY (equal to IMF CY values 2022-24). Fiscal to 2022 only.
- Licence: Creative Commons Attribution 4.0.

**IMF SDMX API (BOP, IIP, IMTS, ANEA, GFS, MFS, DIP, PIP, WEO)** (`imf_sdmx`, verified)

- Publisher: International Monetary Fund. Landing: <https://api.imf.org/external/sdmx/2.1/dataflow>
- Also referred to (gap map) as: `imf_sdmx_portal`.
- Access: SDMX 2.1/3.0 REST, no key; data.imf.org blocks bots; dataservices.imf.org dead (DNS). Requires: none. Formats: sdmx-ml, csv, json.
- Latest: 2026-09-28 - BOP India updated 2026-09-28 (annual to 2025, CAB -20.23 bn); ANEA 2026-09-28; IMTS 2026-08-31; WEO Apr 2026 vintage. Frequency: Continuous; monthly vintage dataflows. Lag: BOP ~1 quarter.
- Coverage: 1948 to 2026-Q2 (BOP 1975-2025 (Q to 2026-Q2); IMTS 1948-2025; ANEA 2005-2025 (CY); GFS central to 2022, states to 2017; DIP to 2024). Basis: BOP US$ BPM6; ANEA India reference period 2022-2023 converted to CY; WEO FY new base.
- Key series: BOP - COUNTRY.BOP_ACCOUNTING_ENTRY.INDICATOR.UNIT.FREQ (e.g. IND.NETCD_T.CAB.USD.Q) [US$]; IMTS - Goods by partner (ex-DOTS) [US$]; ANEA - Annual national accounts (CY) [Rs]; GFS_SOO - Government (stale) [Rs]; DIP/PIP - FDI/portfolio positions by partner (ex-CDIS/CPIS) [US$]; WEO - NGDP etc. actuals to 2025, projections to 2031 [Rs].
- SAM use: RoW cross-check; partner splits (IMTS, DIP, PIP).
- Quirks: IFS discontinued as single dataset. OBS_VALUE in units despite SCALE=6 (do not rescale). DIP key 5 dimensions. Large CSVs; page queries. LICENSE field varies by dataset.
- Licence: IMF API LICENSE field: '(c) International Monetary Fund Copyright. All Rights Reserved.' Terms page Akamai-blocked (403) - clauses unverified.
- Not confirmed: license.attribution (IMF terms page returns 403; clause from a search snippet).

**UN Comtrade (goods HS; services EBOPS)** (`un_comtrade`, corrected)

- Publisher: UN Statistics Division. Landing: <https://comtradeplus.un.org/>
- Access: REST: keyless preview (500 records, 1 period/product per call, ~1 call/s); free key 500 calls/day, 100K records/call. Requires: api_key. Formats: json, csv.
- Latest: 2026-09-18 - India goods annual CY2025 (released 2026-07-10); monthly to July 2026 (released 2026-09-18); services EBOPS latest 2023 (World partner only). Frequency: Continuous. Lag: Monthly ~2 months; annual ~6 months.
- Coverage: 1962 to 2026-07. Basis: Current US$, calendar year; M CIF, X FOB; HS2022.
- Key series: C/A/HS - Goods by HS and partner, reporter 699 [US$]; S/A/EB - Services EBOPS 2010 (World only) [US$].
- SAM use: goods by product and partner (cross-check/licence alternative to DGCI&S).
- Quirks: 429 rate limits; data originate from DGCI&S - ask DGCI&S whether Comtrade-sourced display needs its permission.
- Licence: 'Provided for internal use only and may not be re-disseminated ... without UNSD's permission'; exemption: free-of-charge visualisation/analytics apps and free extraction apps up to 100,000 records.

**BIS statistics (total credit, LBS, CBS, debt securities)** (`bis_stats`, verified)

- Publisher: Bank for International Settlements. Landing: <https://stats.bis.org/api/v1/dataflow/BIS/all/latest>
- Access: SDMX REST (no key). Requires: none. Formats: csv, sdmx-ml.
- Latest: unknown - WS_TC, LBS, CBS, DSS to 2026-Q1; WS_DEBT_SEC2_PUB to 2026-Q2. Frequency: Quarterly. Lag: ~4-6 months.
- Coverage: 2026-Q2. Basis: Stocks; INR bn or US$ mn.
- Key series: WS_TC - Credit to government, private non-financial, households, NFCs [INR bn / US$]; WS_LBS_D_PUB - Cross-border bank claims vis-a-vis India [US$ mn]; WS_NA_SEC_DSS - Debt securities by issuer sector (key Q.N.IN...) [US$ mn].
- SAM use: Flow of Funds cross-checks; RoW bank and bond positions.
- Quirks: Stocks - flows need FX/valuation adjustment; calendar quarters.
- Licence: BIS: use unrestricted provided BIS is cited, not misleading, no extra charge in commercial products, translations marked 'not an official BIS translation', no investment advice.
- Not confirmed: latest_release.date.

**UN National Accounts - Analysis of Main Aggregates** (`un_snaama`, verified)

- Publisher: UN Statistics Division. Landing: <https://unstats.un.org/unsd/snaama/>
- Access: Excel via GET (HEAD 404). Requires: none. Formats: xlsx.
- Latest: 2026-01 - Upload January 2026; India to 2024. Frequency: Annual (December). Lag: ~1-2 years.
- Coverage: 1970 to 2024. Basis: India OLD 2011-12 base (2022 GDP 2,68,90,473 cr; total VA 246.467 lakh cr).
- Key series: file 1 - GDP and breakdown current prices NCU [Rs].
- SAM use: historical cross-check; old-base bridging.
- Quirks: 7 industries only.
- Licence: UNdata terms: free to copy and distribute with UNdata cited.

**UNdata National Accounts Official Country Data - institutional sector accounts (Table 4.x)** (`undata_sna_institutional`, verified)

- Publisher: UN Statistics Division. Landing: <https://data.un.org/Data.aspx?d=SNA&f=group_code%3a401%3bcountry_code%3a356>
- Access: HTML/CSV via UNdata. Requires: none. Formats: html, csv.
- Latest: unknown - India latest shown FY 2019-20. Frequency: Annual. Lag: ~several years.
- Coverage: 2019-20. Basis: Old base.
- Key series: Table 4.1 - Total economy sequence of accounts (India) [Rs].
- SAM use: structure cross-check for institutional sequences.
- Quirks: Stale.
- Licence: UNdata terms: free with citation.
- Not confirmed: latest_release.date.

**OECD-WTO Balanced Trade in Services (BaTIS)** (`oecd_wto_batis`, verified)

- Publisher: OECD and WTO. Landing: <https://www.wto.org/english/res_e/statis_e/gstdh_batis_e.htm>
- Access: OECD SDMX (no key; only the all-wildcard 8-dimension key works - partial keys give 500). Requires: none. Formats: csv, sdmx-ml.
- Latest: unknown - Coverage to 2024. Frequency: Annual. Lag: ~1-2 years.
- Coverage: 2005 to 2024. Basis: Current US$ mn; modelled balanced estimates.
- Key series: BATIS - Services X/M by partner and EBOPS category [US$ mn].
- SAM use: partner split of RoW services.
- Quirks: Modelled; WTO terms not checked.
- Licence: OECD Terms & Conditions: Data may be extracted, copied, adapted, distributed for any purpose incl. commercial, with credit to OECD (not labelled CC BY).
- Not confirmed: latest_release.date.

**Eurostat FIGARO inter-country SUT/IOT (2026 edition)** (`eurostat_figaro`, corrected)

- Publisher: Eurostat / JRC. Landing: <https://ec.europa.eu/eurostat/web/esa-supply-use-input-tables/database>
- Access: Eurostat dissemination API (naio_10_fcp_*) and CIRCABC bulk. Requires: none. Formats: json, csv, parquet.
- Latest: 2026-07-20 - 2026 edition; India 2022-2024 updated 2026-07-20. Frequency: Annual editions. Lag: ~1.5-2 years.
- Coverage: 2010 to 2024. Basis: EUR mn; India VA matches new-base CY-converted GVA within 0.2-0.9% (inference: only IO source already on new base).
- Key series: naio_10_fcp_ii4 - Industry-by-industry IOT 64 NACE industries incl. India [EUR mn].
- SAM use: open IO structure prior (non-commercial).
- Quirks: None recorded in Phase 0.
- Licence: Eurostat CC BY 4.0, EXCEPT data for non-EU/EFTA/candidate countries (incl. India) may not be reused commercially.

**Eora / Eora2 global MRIO** (`eora_mrio`, verified)

- Publisher: KGM & Associates. Landing: <https://worldmrio.com/licensing.jsp>
- Access: Login (institutional email) and download. Requires: paid. Formats: txt.
- Latest: unknown - Eora2 1990-2024. Frequency: Irregular. Lag: ~2 years.
- Coverage: 1990 to 2024. Basis: Current US$.
- Key series: Eora26 - 26 sectors x 190 countries [US$].
- SAM use: not recommended.
- Quirks: Eora1 licences do not carry over.
- Licence: Free only for academic use (1990-2017, <=200 raw points); commercial licence needed for websites.
- Not confirmed: latest_release.date.

**GTAP Data Base v12** (`gtap_db`, verified)

- Publisher: Center for Global Trade Analysis, Purdue. Landing: <https://www.gtap.agecon.purdue.edu/databases/default.asp>
- Access: Purchase + licensed download. Requires: paid. Formats: har.
- Latest: 2026-02 - GTAP 12, February 2026. Frequency: ~3 years. Lag: ~2-3 years.
- Coverage: n/a. Basis: US$ mn.
- Key series: GTAP12 - 65 sectors; country SAMs [US$ mn].
- SAM use: methods reference only.
- Quirks: Reference years (incl. 2023) and region count unverified. For-profit price from $5,980.
- Licence: Proprietary; not sold to re-sellers/third parties.

**EXIOBASE 3** (`exiobase3`, disputed)

- Publisher: EXIOBASE consortium. Landing: <https://exiobase.eu/>
- Access: Zenodo bulk download. Requires: none. Formats: txt, csv.
- Latest: 2026-05-13 - v3.10.2 published 2026-05-13 (IOT 1995-2024; real data to ~2021/22, nowcasts after). Frequency: Annual (recent). Lag: 3-4 years real data.
- Coverage: 1995 to 2024. Basis: EUR mn (presumed).
- Key series: IOT - 163 industries x 200 products [EUR mn].
- SAM use: cross-check only if licence permits.
- Quirks: India membership not confirmed by fetch.
- Licence: DISPUTED: exiobase.eu says CC BY-SA 4.0; Zenodo (v3.9+ incl. v3.10.2) says customised non-commercial CC-BY-SA-NC derivative.

**World Input-Output Database 2016 release** (`wiod_2016`, verified)

- Publisher: Groningen Growth and Development Centre. Landing: <https://www.rug.nl/ggdc/valuechain/wiod/wiod-2016-release>
- Access: Dataverse bulk download (DOI 10.34894/PJ2M1C). Requires: none. Formats: xlsx, dta.
- Latest: 2016 - 2016 release. Frequency: Discontinued. Lag: n/a.
- Coverage: 2000 to 2014. Basis: Current US$ mn.
- Key series: WIOT/SEA - 56 sectors; socio-economic accounts [US$ mn].
- SAM use: historical factor split only.
- Quirks: No longer maintained.
- Licence: Creative Commons Attribution 4.0.

**World Bank WITS - UNCTAD TRAINS tariffs** (`wb_wits_trains`, unverified)

- Publisher: World Bank / UNCTAD. Landing: <https://wits.worldbank.org/API/V1/wits/datasource/trn/dataavailability/country/356/year/all>
- Access: WITS API. Requires: none. Formats: xml.
- Latest: 2022-09-09 - India latest 2021 (updated 2022-09-09). Frequency: Annual (as reported). Lag: Several years.
- Coverage: 1990 to 2021. Basis: Tariff rates %.
- Key series: TRN 356 - Applied/MFN tariffs by HS [%].
- SAM use: customs duty rate cross-check.
- Quirks: Stale for India.
- Licence: not checked (unverified).
- Not confirmed: license (not checked).

### 3.10 Existing Indian SAMs and multiplier estimates (`prior_art`)

**IFPRI Nexus SAM for India 2022/23 (dataset + data paper)** (`ifpri_nexus_sam_india_2022_23`, corrected)

- Publisher: IFPRI Nexus Project. Landing: <https://doi.org/10.7910/DVN/LDUDTE>
- Access: Harvard Dataverse download gated by guestbook 380; data paper PDF free on CGSpace. Owner must fill guestbook (name, e-mail) in web UI. Data-paper URL corrected (earlier URL was the .txt bundle). Requires: registration. Formats: tab, pdf.
- Latest: 2024-11-08 - 2022/23 SAM, Dataverse v1 2024-11-08; still latest per Nexus release note 2025-12-12. Frequency: Irregular (previous 2017/18). Lag: ~1.5-2 years.
- Coverage: 2022-23 to 2022-23. Basis: Current Rs bn; NAS 2024 (OLD 2011-12 series); SUT 2019/20 coefficients; GFS/BoP '2022'; HCES 2022-23; PLFS 2022-23; TRAINS 2021.
- Key series: SAM.tab - 42 activities/commodities, 5 factors, 10 households (rural/urban x quintile), ent, gov, tax accounts (count unverified for India file), s-i, dstk, row [Rs bn]; Table 8 - Macro SAM: VA 246,992; product taxes 22,743; PFCE 139,795; GFCE 28,836; investment 92,604; X 61,334; M 70,532; savings ent 49,632 / hh 47,714 / gov -9,855 / RoW 5,113 [Rs bn].
- SAM use: structural template; household split template; Phase 2/4 cross-check.
- Quirks: Enterprise/household savings split ASSUMED (equal savings rates). Single enterprise and single government account; no financial block. Macro SAM balanced manually; detail by cross-entropy.
- Licence: CC BY 4.0 (CGSpace dataset record hdl 10568/163735; IFPRI Datasets Terms of Use Dec 2019 s.4); s.5 adaptation disclaimer mandatory; s.6 third-party content.

**IFPRI SAM for India 2017-18 (Pal, Pradesha, Thurlow 2020)** (`ifpri_sam_india_2017_18`, corrected)

- Publisher: IFPRI. Landing: <https://doi.org/10.7910/DVN/NYVJX8>
- Access: Dataverse (guestbook 9 configured; API returned 303 to S3 without guestbook - not followed). Requires: registration. Formats: tab, xlsx, pdf.
- Latest: 2021-04-23 - Dataverse 2021-04-23; paper 2020-11-01. Frequency: One-off. Lag: ~3 years.
- Coverage: 2017-18 to 2017-18. Basis: Old series; SUT 2015/16; NSS 2011/12 consumption.
- Key series: SAM - 112 sectors, 8 labour, 4 capital, land; rural farm/non-farm/urban quintiles [Rs].
- SAM use: structural template.
- Quirks: Two rounds of cross-entropy.
- Licence: CC BY 4.0 (CGSpace dataset record hdl 10568/163735; IFPRI Datasets Terms of Use Dec 2019 s.4); s.5 adaptation disclaimer mandatory; s.6 third-party content.

**IFPRI 2017/18 SAMs for Odisha, Uttar Pradesh, Bihar** (`ifpri_state_sams_2017_18`, verified)

- Publisher: IFPRI. Landing: <https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/74YWV2>
- Access: Dataverse. Requires: registration. Formats: tab.
- Latest: 2025-01-06 - Odisha 2025-01-06; UP and Bihar 2024-08-08. Frequency: One-off. Lag: n/a.
- Coverage: 2017-18 to 2017-18. Basis: Old series.
- Key series: state SAMs - Nexus-format state SAMs [Rs].
- SAM use: template for future regional split.
- Quirks: None recorded in Phase 0.
- Licence: CC BY 4.0 (CGSpace dataset record hdl 10568/163735; IFPRI Datasets Terms of Use Dec 2019 s.4); s.5 adaptation disclaimer mandatory; s.6 third-party content.

**CSTEP energy-disaggregated SAM India 2017-18 (Excel) + CSTEP-TN-2024-2** (`cstep_sam_india_2017_18`, corrected)

- Publisher: Center for Study of Science, Technology and Policy. Landing: <https://cstep.in/publication/social-accounting-matrix-construction-and-multiplier-analysis/>
- Access: Direct XLSX (no login). Requires: none. Formats: xlsx, pdf.
- Latest: 2025-06-23 - Technical note Aug 2024; XLSX LM 2025-06-23. Frequency: One-off. Lag: ~7 years.
- Coverage: 2017-18 to 2017-18. Basis: Current Rs crore ('10 Million Rupee'); derived from IFPRI 2017-18 + ASI.
- Key series: SAM - 209 accounts: 92 activities, 87 commodities, 8 labour, land, capital, ent, 10 households, gov, atax/mtax/dtax/stax, s-i, dstk, row [Rs crore].
- SAM use: balanced test SAM for multiplier code.
- Quirks: Balanced (max |row-col| 5.6e-9). Table 1 is a partial catalogue of Indian SAMs.
- Licence: (c) 2024 CSTEP; reproduction must cite title/citation and credit copyright owners.

**NCAER SAM for India 2021-22 (WP 160; Margin 2024)** (`ncaer_sam_india_2021_22`, corrected)

- Publisher: National Council of Applied Economic Research. Landing: <https://ncaer.org/publication/estimation-of-sam-for-india-an-application-for-indias-energy-transition-targets/>
- Access: PDF (use ncaer.org without www; www fails TLS). Requires: none. Formats: pdf.
- Latest: 2024-02-05 - WP 160 (cover Jan 2024; web 2024-02-05). Frequency: One-off. Lag: ~2 years.
- Coverage: 2021-22 to 2021-22. Basis: Current Rs crore; old series; SUT 2018-19 benchmarked to 2021-22; NSS 2011-12 shares.
- Key series: SAM - 59x59: 39 producing sectors (energy sectors within the 39), 3 factors, 10 households (quintiles), 4 institutions [Rs crore]; Table 6 - SAM output multipliers: agriculture 6.656 ... primary energy 2.355 ... construction 6.453 [ratio].
- SAM use: Phase 4 cross-check.
- Quirks: WP internally says '30 production sectors' in one place and 'decile' for quintiles. SAM in SAGE supplementary (access unverified). RAS balanced.
- Licence: All rights reserved (site footer).

**CSEP Environmentally-extended SAM for India 2019-20** (`csep_esam_india_2019_20`, corrected)

- Publisher: Centre for Social and Economic Progress. Landing: <https://csep.org/technical-note/developing-an-environmentally-extended-social-accounting-matrix-for-india-2019-20/>
- Access: PDF only. Requires: none. Formats: pdf.
- Latest: 2023-11-22 - Page 2023-11-22 (modified 2024-06-21). Frequency: One-off. Lag: ~3 years.
- Coverage: 2019-20 to 2019-20. Basis: Old series; IOT RAS-projected from 2015-16; PLFS 2019-20.
- Key series: ESAM - 45 sectors, 318 labour, 80 households; GDP 2,03,51,013 cr [Rs crore]; Table 11 - Output multipliers on an AGGREGATED ESAM (32 labour, 40 households): paddy 6.380, coal 3.044, crude 1.558 [ratio].
- SAM use: household/labour disaggregation template; Phase 4 cross-check.
- Quirks: Documents IOT merchandise exports understated vs MoC/RBI because export margins go to services.
- Licence: All rights reserved; short quotes (<=2 paragraphs) allowed with credit.

**Pradhan, Saluja & Sharma (2013) SAM for India 2007-08, IEG WP 326** (`ieg_sam_india_2007_08`, verified)

- Publisher: Institute of Economic Growth. Landing: <https://www.iegindia.org/upload/publication/Workpap/wp326.pdf>
- Access: PDF. Requires: none. Formats: pdf.
- Latest: 2013 - 2013. Frequency: One-off. Lag: ~5 years.
- Coverage: 2007-08 to 2007-08. Basis: 2004-05 series; IOTT 2007-08.
- Key series: SAM - 78 sectors, 9 households [Rs].
- SAM use: method template (household income pro-rata to NAS).
- Quirks: None recorded in Phase 0.
- Licence: All rights reserved (site footer).

**Pal & Bandarlage (2017) value-added disaggregated SAM for India 2007-08, J. Economic Structures** (`pal_bandarlage_2017`, verified)

- Publisher: Springer (open access). Landing: <https://link.springer.com/article/10.1186/s40008-017-0074-y>
- Access: Article. Requires: none. Formats: html, pdf.
- Latest: 2017 - 2017. Frequency: One-off. Lag: n/a.
- Coverage: 2007-08 to 2007-08. Basis: Old series.
- Key series: SAM - 78 sectors, 48 labour types, 80 households [Rs].
- SAM use: disaggregation template.
- Quirks: None recorded in Phase 0.
- Licence: Creative Commons Attribution 4.0.

**Pal, Pohit & Roy (2012) SAM for India 2003-04, Economic Systems Research 24(1)** (`pal_pohit_roy_2012`, unverified)

- Publisher: Taylor & Francis. Landing: <https://www.tandfonline.com/doi/full/10.1080/09535314.2011.618824>
- Access: Paywalled article. Requires: paid. Formats: pdf.
- Latest: 2012 - 2012. Frequency: One-off. Lag: n/a.
- Coverage: 2003-04 to 2003-04. Basis: Old series.
- Key series: SAM - 85 sectors, energy-disaggregated [Rs].
- SAM use: method reference.
- Quirks: None recorded in Phase 0.
- Licence: Publisher copyright.

**India MRIO dataset, 32 states, 2011-2019 (Zheng et al., Scientific Data 2026)** (`india_mrio_32states_2011_2019`, verified)

- Publisher: Scientific Data / figshare. Landing: <https://www.nature.com/articles/s41597-026-07227-x>
- Access: figshare bulk XLSX (API). Requires: none. Formats: xlsx.
- Latest: 2026-06-30 - Article 24 Apr 2026; figshare v1 2026-06-30. Frequency: One-off. Lag: ~7 years.
- Coverage: 2011 to 2019. Basis: Current Rs lakh; old series.
- Key series: MRIO - 66 sectors x 32 states; single VA row [Rs lakh].
- SAM use: coefficient bounds; optional regional extension.
- Quirks: Up to 5% tolerated imbalance.
- Licence: CC BY 4.0.

**RBI Monetary Policy Report April 2019, Box III.1 'Estimable Fiscal Multipliers for India'** (`rbi_mpr_2019_fiscal_multipliers`, verified)

- Publisher: Reserve Bank of India. Landing: <https://rbi.org.in/Scripts/PublicationsView.aspx?id=18941>
- Access: HTML. Requires: none. Formats: html.
- Latest: 2019-04-04 - 4 Apr 2019. Frequency: One-off. Lag: n/a.
- Coverage: 1980-81 to 2017-18. Basis: n/a.
- Key series: Table III.1.1 - Peak multipliers: Centre capex 3.25; States capex 2.00; Centre revenue exp 0.45; States revenue exp 0.82 (Bayesian SEM, annual) [ratio].
- SAM use: Phase 4 benchmark (primary source).
- Quirks: The Dec 2020 Bulletin paraphrase ('2.45 in t, 3.14 in t+1') differs; cite this primary box.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**RBI Bulletin articles citing RBI (2019) capex multipliers (Dec 2020; Jun 2021)** (`rbi_bulletin_capex_multipliers`, corrected)

- Publisher: Reserve Bank of India. Landing: <https://rbi.org.in/Scripts/BS_ViewBulletin.aspx?Id=19959>
- Access: HTML. Requires: none. Formats: html.
- Latest: 2021-06-16 - 24 Dec 2020 and 16 Jun 2021. Frequency: One-off. Lag: n/a.
- Coverage: n/a. Basis: n/a.
- Key series: paraphrase - Centre capex 2.45 in t, 3.14 in t+1; States close to 2 [ratio].
- SAM use: secondary only.
- Quirks: Secondary paraphrase of MPR 2019.
- Licence: RBI Bulletin imprint: '(c) Reserve Bank of India 2026. All rights reserved. Reproduction is permitted provided an acknowledgement of the source is made.' Website Disclaimer (no deep links/caching without permission) still applies. The imprint text was read in the September 2026 Bulletin (license.url). The imprint of December 2020 and June 2021 was not checked; it is ASSUMED to carry the same reproduction clause.
- Not confirmed: license (imprint of December 2020 and June 2021 not checked; Sept 2026 imprint assumed).

**Jain & Kumar (2013) Government Expenditure Multipliers in India: SVAR, RBI WPS 07/2013** (`rbi_jain_kumar_2013_multipliers`, corrected)

- Publisher: Reserve Bank of India. Landing: <https://rbi.org.in/scripts/PublicationsView.aspx?Id=15369>
- Access: HTML. Requires: none. Formats: html.
- Latest: 2013-09-18 - 18 Sep 2013. Frequency: One-off. Lag: n/a.
- Coverage: 1980-81 to 2011-12. Basis: Annual data.
- Key series: Table 1 - Capital outlay impact 1.29, peak 3.56 (yr 4); revenue exp 0.37; States capex 2.13 impact, 7.61 peak (yr 3); Centre capex 0.39/0.85 [ratio].
- SAM use: Phase 4 benchmark.
- Quirks: SVAR, not comparable with fixed-price SAM multipliers.
- Licence: No open-data licence. RBI website Disclaimer: caching/framing prohibited; deep links need prior RBI permission.

**NIPFP fiscal multiplier studies (WP 2013-125; WP 436 2025)** (`nipfp_fiscal_multipliers`, corrected)

- Publisher: National Institute of Public Finance and Policy. Landing: <https://www.nipfp.org.in/media/medialibrary/2013/09/WP_2013_125.pdf>
- Access: PDF. Requires: none. Formats: pdf.
- Latest: 2025-09 - WP 436, September 2025. Frequency: One-off. Lag: n/a.
- Coverage: 1991 to 2022. Basis: n/a.
- Key series: WP125 - Capex 2.45, transfers 0.98, other revenue exp 0.99, tax ~-1 (annual 1991-2012) [ratio]; WP436 - Social spending multiplier 1.67 (1990-2022) [ratio].
- SAM use: Phase 4 benchmark.
- Quirks: NIPFP 2.45 coincides numerically with the Bulletin paraphrase - do not conflate.
- Licence: no explicit licence found.

**Goyal & Sharma (2018) Government Expenditure in India: Composition and Multipliers, J. Quantitative Economics** (`goyal_sharma_2018`, verified)

- Publisher: Springer. Landing: <https://link.springer.com/article/10.1007/s40953-018-0122-y>
- Access: Article page. Requires: none. Formats: html.
- Latest: 2018-12 - Dec 2018. Frequency: One-off. Lag: n/a.
- Coverage: n/a. Basis: n/a.
- Key series: SVAR - Cumulative capex multiplier 2.4-6.5x the revex multiplier [ratio].
- SAM use: Phase 4 benchmark.
- Quirks: None recorded in Phase 0.
- Licence: Publisher copyright.

**Mishra & Adiraju (2025) Estimation of fiscal multipliers for India, IJEPEE 21(1)** (`mishra_adiraju_2025`, verified)

- Publisher: Inderscience. Landing: <https://www.inderscience.com/info/inarticle.php?artid=145416>
- Access: Article page. Requires: none. Formats: html.
- Latest: 2025 - 2025. Frequency: One-off. Lag: n/a.
- Coverage: n/a. Basis: n/a.
- Key series: SVAR - Impact 0.23-1.85; cumulative 0.45-5.45 [ratio].
- SAM use: Phase 4 benchmark.
- Quirks: None recorded in Phase 0.
- Licence: Publisher copyright.

**Report of the Committee on Private Final Consumption Expenditure (Adhikari Committee), MoSPI 2015** (`adhikari_pfce_committee`, verified)

- Publisher: MoSPI. Landing: <https://mospi.gov.in/sites/default/files/publication_reports/Adhikari_Committee_PFCE_22may15.pdf>
- Access: PDF (EPW commentary paywalled). Requires: none. Formats: pdf.
- Latest: 2015-05-22 - 22 May 2015; EPW (Kumar & Seth) 31 Jan 2026. Frequency: One-off. Lag: n/a.
- Coverage: 1972-73 to 2011-12. Basis: 2004-05 series comparisons.
- Key series: gap - 2011-12 NSS 28,29,566 vs NAS PFCE 51,67,446 cr (-45.24%; food -28.29%, non-food -54.77%); EPW abstract: ~54% in 2023-24 [Rs crore / %].
- SAM use: household consumption: HCES for distribution only.
- Quirks: Gap concentrated in non-food; uniform scaling biases quintiles.
- Licence: MoSPI copyright policy + GSDD 2026 Category A (open access); no GODL-India statement. Terms: <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>. license.url (GSDD 2026 Gazette) defines access categories only ('Category A (open access data)'); the reproduction and attribution clause ('may be reproduced, following the revised GSDD 2026 ... the source must be prominently acknowledged') is in the MoSPI copyright policy, served by POST to terms_url (JSON; GET returns 403; re-checked 2026-09-29).

**Venkatesh & Pal: From SUTs to SAMs for India (IIOA 2019); IOT/SAM 2012-13 (CSTEP WP 2018)** (`sut_to_sam_methodology_india`, verified)

- Publisher: CSTEP / IFPRI. Landing: <https://www.iioa.org/conferences/27th/papers/files/3665_20190720111_AV_SUTtoSAM_AV_200717_final.pdf>
- Access: PDF. Requires: none. Formats: pdf.
- Latest: 2019-06 - June 2019. Frequency: One-off. Lag: n/a.
- Coverage: 2012-13 to 2012-13. Basis: Old series.
- Key series: method - 140x140 commodity IOT from SUT; 140-sector SAM [Rs].
- SAM use: Phase 2 SUT->IOT->SAM method.
- Quirks: None recorded in Phase 0.
- Licence: no explicit licence found.

## 4. Licences and attribution requirements

**Headline:** no source used for the SAM states **GODL-India** on its own site. The only place GODL appears is the data.gov.in footer, and that site now calls itself a "sandbox" and could not be verified. Reuse therefore depends on each publisher's own terms. Udgam Labs is a company, so any "non-commercial" clause matters even though the website is free.

| Group | Sources | Terms (as fetched) | What we must do |
|---|---|---|---|
| **Open with attribution** | MoSPI aggregates (NAS, SUT, CPI, IIP, ASI Vol I, NSS reports), CAG, IRDAI, EPFO, OECD (ICIO, IOTs, TiVA, BaTIS), ADB KIDB, World Bank WDI, UNdata / UN AMA, PRS (CC BY 4.0), IFPRI (CC BY 4.0), figshare India MRIO (CC BY 4.0), WIOD (CC BY 4.0), BIS | MoSPI: "may be reproduced, following the revised GSDD 2026 … reproduced accurately … source must be prominently acknowledged". This clause is only in the copyright policy, served by POST to <https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data>; a GET returns 403. It was re-fetched on 2026-09-29 and is recorded as `license.terms_url` on every MoSPI entry. The GSDD 2026 Gazette (`license.url`) only defines the access categories: Category A = free, without registration. CAG, IRDAI, EPFO: reproduce free of charge with prominent acknowledgement. OECD: "for any purpose, even for commercial use … credit to the OECD". ADB KIDB: "commercial and noncommercial purposes at no cost" (lead fetched <https://kidb.adb.org/terms>). BIS: unrestricted if cited, not misleading, and translations marked "not an official BIS translation". IFPRI: CC BY 4.0 plus a mandatory disclaimer that the data were adapted. | Credit each figure's source on the site. Add the BIS translation disclaimer on Hindi pages. Add the IFPRI adaptation disclaimer. Exclude material that is third-party copyright. |
| **Reproduction permitted, but the website terms restrict linking** | RBI Bulletin content (household financial savings 52a/b, the FSF article, Current Statistics, remittance survey), DBIE (archived disclaimer) | Bulletin imprint: "© Reserve Bank of India 2026 All rights reserved. Reproduction is permitted provided an acknowledgement of the source is made." (lead fetched the Sept 2026 Bulletin PDF). The imprints of the older issues that carry the articles we use (Mar 2025 remittance survey, Dec 2020 and Jun 2021 multiplier articles, Jan 2026 FSF) were not checked. They are **assumed** to carry the same clause, and each entry says so. The RBI website Disclaimer separately says: "caching and links to, and the framing of this Web Site or any of the contents are prohibited"; deep links need prior permission; home-page links need written notice. | Acknowledge RBI. Get RBI permission for deep links and caching (see §5). Until then, cite RBI tables without deep links. |
| **No licence statement; all rights reserved** | RBI Handbook, BoP, external debt and other rbi.org.in releases; CGA; FC16 data files; PFRDA; OEA (WPI/PPI/ICI); NCAER, CSEP, IEG, CSTEP prior-art SAMs | No reuse clause found. The CGA and FC16 copyright pages are empty. The OEA disclaimer returns 404. | Ask for permission or clarification (§5). Cite methods and figures from prior-art SAMs; don't redistribute their files. |
| **Permission required before reproduction** | indiabudget.gov.in (Budget, Economic Survey, FC report copies), DEA, SEBI, GST Council/GSTN, DGCI&S | MoF: "may not be reproduced partially or fully, without due permission". DEA: reproduce "after taking proper permission by sending a mail". SEBI: the same by e-mail, and the permission does **not** extend to third-party material (NSDL, AMFI, BSE, NSE tables). gst.gov.in Terms class web scraping as unauthorised. DGCI&S: "internal use only … may not be re-disseminated in any form without the written permission from Director General"; royalty-free at ≤1,000 records or for substantially transformed data, but written permission is still required. | E-mail each of these for permission (§5). |
| **Non-commercial only** | MoSPI unit-level data (GSDD Category B), WID (CC BY-NC-SA 4.0), Eurostat FIGARO India cells, AMFI (personal use only), EXIOBASE (Zenodo licence) | GSDD 2026 B(ii): "free of cost only for non-commercial use including study/research purposes"; B(iii) defines commercial use to include "reports derived directly or indirectly from the data". Eurostat excludes non-EU/EFTA/candidate-country data from commercial reuse. | Decide and document whether a free site run by a company counts as non-commercial. Ask MoSPI before publishing aggregates derived from unit data. |
| **Prohibited or not recommended** | NSE, BSE, NSDL FPI Monitor, CCIL, Eora, GTAP, CMIE | NSE bans automated collection and use "for any gaming, virtual trading or simulation activities". NSDL: "Reproduction, redistribution and transmission … strictly prohibited". CCIL requires written consent. Eora and GTAP need paid licences. | Use SEBI aggregates instead, subject to the third-party carve-out; see §5. |
| **Free-visualisation exemption** | UN Comtrade | "internal use only" unless the use is a "Free-of-charge data visualization and/or data analytics application". | The site must stay free. Cite "UN Comtrade". |
| **Unverified** | IMF (the API field says "All Rights Reserved"; the terms page is Akamai 403), CBDT (site 403), DPIIT, CDSL, PPAC, WITS, PIB, eGramSwaraj, FIMMDA, ICPSR/IHDS, CMIE, data.gov.in, National Savings Institute (copyright policy is behind an ASP.NET postback), DPE (site content needs JavaScript) | Could not read, or not checked. Entries with no licence text read are `unverified` under the status rule. | Owner to check in a browser (§5). |

**Attribution format (proposal for the site):** "Source: <publisher>, <publication/table/series id>, <vintage or release date>, accessed <retrieval date>. <Licence/permission note>." Every figure also carries `estimated` when it was derived.

## 5. Access the owner needs to arrange

No login, paywall or CAPTCHA was bypassed in Phase 0, and no bot challenge was solved. One practice needs the owner's sign-off. rbidocs.rbi.org.in files were retrieved by sending ordinary browser headers (User-Agent, Accept, Accept-Language). With those headers the F5/TSPD challenge is not served. With fewer headers it is served, still as HTTP 200. See item 1(d).

**High priority (needed for Phase 1 or for publishing):**

1. **RBI (DSIM, dbie@rbi.org.in; Dept of Communication, helpdoc@rbi.org.in):**
   - (a) Written permission to deep-link RBI pages and files, to cache raw files in `data/raw`, and to republish derived aggregates (BoP, Handbook, FSF, State Finances, banking) on the public site.
   - (b) Programmatic or bulk access to DBIE (SDMX series and BOE reports: STRBI, detailed BSR). No public API exists.
   - (c) Fallback: if rbidocs.rbi.org.in escalates to a CAPTCHA, the owner downloads the RBI files by hand each release cycle. These are the HBS tables, the FSF workbook, the State Finances XLSX set, the Bulletin 52(a)/(b) tables, the BoP/IIP/debt/invisibles/ODI XLSX, and the Municipal/PRI finance tables.
   - (d) Confirm that automated downloads that send ordinary browser headers are acceptable. The RBI Disclaimer says RBI "reserves all right to deny or restrict access to this Web Site to any particular person". robots rules cannot be read: www.rbi.org.in/robots.txt returns 418 "Unauthorised Access", and rbidocs robots.txt returns the challenge page. Until RBI answers, prefer manual downloads for anything published.
2. **microdata.gov.in (MoSPI NADA):** free registration by the owner, then Category B applications for these catalogs:
   - HCES 2023-24 (237) and 2022-23 (224)
   - PLFS 2022-23 (210), 2023-24 (213) and CY 2025 (284)
   - ASUSE 2022-23 (222), 2023-24 (238) and 2025 (293, created 6 May 2026)
   - ASI 2023-24 (256)
   - AIDIS / SAS 2019 (156 / 157)
   - Optionally NSS Health 2025 (290), Education 2025 (255) and Domestic Tourism 2025-26 (307)

   You also need to decide whether the public site is "non-commercial" under GSDD 2026 (Udgam Labs is a company). If unsure, e-mail MoSPI before publishing anything derived from unit data. The finder proposed gsdd-cicd@mospi.gov.in; that address was not verified.
3. **SEBI:** e-mail permission to reproduce the Bulletin and Handbook tables. Also get NSDL and AMFI authorisation for the tables SEBI sources from them, or confirmation that SEBI's permission covers them.
4. **Ministry of Finance:** permission (or confirmation of an open licence) from the Budget Division (indiabudget.gov.in) and DEA (e-mail) to republish derived Budget and debt data. Also ask CGA to clarify reuse terms, since its copyright page is empty.
5. **GSTN / GST Council:** permission to use and redistribute GST statistics and to automate downloads from tutorial.gst.gov.in.
6. **DGCI&S (Director General, Kolkata):** written permission to re-disseminate goods trade aggregates by product group and partner. Alternatively, rely on UN Comtrade under its free-visualisation exemption, and ask DGCI&S whether that still needs their permission. The detailed portal (8-digit × country × port) is paid: ₹1 per record, or ₹3,50,000 a year for bulk.
7. **CBDT:** the owner should download in a normal browser the "Time Series Data FY 2000-01 to 2024-25" PDF and the latest Income Tax Return statistics. incometaxindia.gov.in returns 403 to every automated client. The registry records this as `requires: manual_download`. *Phase 1 (2026-09-29): optional. Under DECISIONS D1-1(c) CBDT is not automated; direct taxes come from Union Finance Accounts (MH 0020/0021) and Receipt Budget Annex 7.*
7a. **Department of Public Enterprises:** open <https://www.dpe.gov.in/> in a browser and find the latest Public Enterprises Survey. Record its edition, release date, file URLs and the site's copyright policy. The site renders only with JavaScript: automated fetches get an empty shell, and WebFetch gets 403. This is optional for the SAM, because NAS statements 1.9 and 7.1A/7.1B already give public-sector aggregates. *Phase 1 (2026-09-29): still unreadable (content served from a keyed CMS); not needed by any gap-map cell.*
7b. **National Savings Institute:** *done in Phase 1:* the Copyright Policy (InternalPage.aspx?Id_Pk=43) says the content 'may not be reproduced partially or fully, without due permission from NIC'. Ask NSI/NIC for permission before publishing the collection tables (the SAM itself can use Receipt Budget Annex 8 and Finance Accounts Statement 16).
8. **IFPRI Harvard Dataverse:** fill in the guestbook for DVN/LDUDTE (India SAM 2022/23, guestbook 380) and, to respect the terms, DVN/NYVJX8 (2017-18, guestbook 9). Optionally e-mail IFPRI-Data@cgiar.org to confirm redistribution of derived figures.

**Medium / optional:**

9. **UN Comtrade free API key:** partner × HS queries beyond the 500-record preview.
10. **data.gov.in free API key:** check whether any GODL-licensed mirror is current. The site currently says it is a sandbox.
11. **MoSPI National Accounts Division:**
    - (a) Will new-base institutional sequences of accounts (allocation of primary income, secondary distribution, use of income, capital account by sector) be published, or can they be shared?
    - (b) A machine-readable SUT concordance: 155 products ↔ NPCMS/NPCSS/ITC-HS, and 67 industries ↔ NIC 2008.
    - (c) Any SUT valuation or import-use matrices.
    - (d) An explanation of the NIC 2025 vs NIC 2008 contradiction between the SUT press release and the SUT note.
12. **CAG:**
    - (a) Access to the "FA&AA data" and MKI Excel folders on SharePoint (behind a Microsoft login), which hold machine-readable state Finance Accounts.
    - (b) Confirmation of the provenance and reuse terms for State Finances 2024-25, which is published only as Tableau Public on a personal profile.
13. **IMF:** open <https://www.imf.org/en/about/copyright-and-terms> in a browser and record the terms (automated clients get 403).
14. **Finance Commission, PFRDA, PPAC, DPIIT, CDSL, WITS, FIMMDA, eGramSwaraj, PIB:** confirm reuse terms. For DPIIT, also find the June 2026 FDI factsheet URL; the listing is JavaScript-only.
15. **WID and EXIOBASE:** optional clarification of their licences for a free site run by a company.
16. **NSE/BSE, NSDL, CCIL:** not recommended. If exchange-level FII/DII or CCIL detail is ever needed, a paid licence and written consent are required, and NSE's terms ban simulation use.
17. **Optional paid items:**
    - CMIE Consumer Pyramids (non-official household income by source; price not published)
    - PRICE ICE360 registration
    - ICPSR account for IHDS
    - SAGE (NCAER SAM supplementary file)
    - EPW article (₹59)
    - GTAP 12 (from US$5,980) or an Eora licence (neither is needed)
18. **Browser:** several verifiers could not use browser automation because more than one Chrome browser was connected. Choose one browser if later phases need pages rendered by JavaScript (DPIIT, BSE, the DBIE disclaimer).

Removed after verification: the ADB MRIO licence check. The KIDB terms are open for commercial and non-commercial use, and the lead confirmed this.

## 6. Disputed and unverified items

### 6.1 Disputed (conflicting evidence; both values kept)

| Item | Value A | Value B | Status after lead re-check |
|---|---|---|---|
| GSTN FY 2025-26 gross GST (22,27,095.73) and net (19,34,465.16): do they include compensation cess? | Finder: excludes cess, and the files have "no cess rows" | Verifier: the imports line is labelled "IGST and CESS on Import – All India" (5,95,326.35) and export refunds "IGST and CESS Refund on Exports" (1,28,568.44) | Lead downloaded the file and confirmed both "IGST and CESS" labels, with no separate cess column. **Unresolved.** Reconcile with Budget major head 0009 in Phase 1. |
| EXIOBASE 3 licence | exiobase.eu: CC BY-SA 4.0 | Zenodo (v3.9 onward, incl. v3.10.2): customised non-commercial CC-BY-SA-NC derivative | The publisher's own pages contradict each other. Treat it as non-commercial until the consortium clarifies. |
| Industry classification used in SUT 2022-23 and 2023-24 | MoSPI press release (15 May 2026): "adoption of updated classifications like NIC 2025" | SUT methodological note §5.2: "NIC 2008 and NPCMS 2011 (Revised)/ NPCSS have been used" | The contradiction is inside MoSPI's own documents. Working assumption: NIC 2008, per the note. Ask NAD (§5 item 11). |
| Will there be a future HCES round? | Finder: none scheduled (ARC 2026-27 has no HCES) | Press snippet (not opened): MoSPI Secretary said it would be repeated in about 3 years | Unresolved. It does not affect the reference year. |
| NCAER 2021-22 SAM sector count | WP 160: "39 producing sectors" | The same WP elsewhere: "30 production sectors" | The source is internally inconsistent. The registry uses 39 (the verifier's reading of the SAM structure). |

### 6.2 Resolved disagreements (finder vs verifier; corrected values used)

- MoSPI file access: the finder said browser Sec-Fetch headers were required. Refuted: plain GETs return 200. The lead re-checked NAS 1.1.xlsx without a User-Agent and got 200.
- ASI 2024-25 is "overdue": corrected. It is scheduled for 29 Sep 2026 and was not yet released when the lead checked.
- PE 2025-26 date: 5 Jun 2026, not 7 Jun. The 7 June rule applies from 2027.
- RBI licence: the finder said there was no explicit licence. For Bulletin content this is corrected: the imprint permits reproduction with acknowledgement (lead confirmed from the PDF). For other rbi.org.in content the site Disclaimer still applies.
- MoSPI copyright: an unverified snippet said "permission by mail". The lead fetched the policy via the MoSPI API: reproduction follows GSDD 2026 with acknowledgement, and no e-mail permission is needed.
- WID licence: CC BY-NC-SA 4.0. The lead confirmed the active licence link, and the terms page is 404.
- CAG State Finances: the latest edition is 2024-25 (16 Jun 2026), not 2023-24.
- ADB MRIO licence: open (KIDB terms, lead confirmed). ADB "2024" means FY 2024-25 on the old base.
- FIGARO: India is included, but India cells are **non-commercial** (not plain CC BY).
- RBI fiscal multipliers: use the primary MPR April 2019 Box III.1 (Centre capex 3.25, States 2.00; revenue 0.45 and 0.82), not the Bulletin paraphrase (2.45 in t, 3.14 in t+1). The lead confirmed the 3.25 / 2.0 text.
- DPIIT US$58,846 mn for 2025-26 is FDI **equity** only, not total FDI.
- NBFC monthly sectoral credit: a new series that started with the Jul 2026 release. It has no archive back to 2010.
- RTP NBFC data: Appendix VI.1–VI.9 are available as XLSX, not only PDF.
- UN Comtrade monthly data run to Jul 2026. The ODI file OFDI18082026.xlsx is July 2026 data.
- WDI BoP series are calendar-year. The 2025 current-account gap with the IMF is a vintage difference.
- NAS statement 1.14: GDI and final consumption are given only for general government and households.
- HCES unit data has no income variables. The "income proxy" use was removed.

### 6.3 Unverified (kept, marked `unverified` or noted in the entry)

- data.gov.in mirrors (NAS, budget, trade): catalog pages timed out or returned 403, the site is labelled a "sandbox", and robots.txt disallows crawling. Their content, licence and vintage are unverified.
- CBDT time series to FY 2024-25 (₹22.26 lakh crore): only a secondary source (24 Nov 2025) could be read. The site returns 403.
- Time Use Survey 2024 report date (March 2025): the catalog exists, but the date is not confirmed from a primary source.
- Scheduled Banks' Form-A series on DBIE: cited in a BSR press release, not fetched.
- Pal, Pohit & Roy (2012) SAM: tandfonline returned 403.
- IIP "1,042 products" (only 463 item groups are verified). GTAP 12 reference years and region count. EXIOBASE and GTAP India membership. The BSE reproduction clause (snippet only). The IMF terms page. The DBIE current disclaimer. BOE guest-session rationing. The ICPSR/IHDS terms. The WITS, PPAC, DPIIT, CDSL and PIB licences. The IHDS-3 release.
- No 7th-round RBI remittance survey found (not re-checked; search quota exhausted). No India-wide remittance multiplier found.
- NHIS sample size (4.5 lakh) and results date (mid-2027): secondary sources only.
- New-base State GSDP timetable (states adopting it during FY27): the MoSPI 19 May 2026 release confirms the joint discussions; the adoption requirement comes from a secondary source.
- PFRDA units are inferred as ₹ crore. (RBI State Finances units are now resolved from the files: see the entry. Most statements are in ₹ crore, the ratio statements are in per cent, and Appendices I–IV are in **₹ lakh**. Statement 22 is PDF-only and its unit was not checked.)
- Entries downgraded to `unverified` in the fix pass because no licence text was read and/or the latest release was not identified: `cmie_cphs`, `ppac_petroleum_exchequer` (re-verified in Phase 1, section 7), `pib_tax_devolution_releases`, `egramswaraj_panchayat_accounts`, `nse_bse_market_data`, `cdsl_periodic_stats`, `fimmda_cp_cd_traded`, `wb_wits_trains`, `ihds` and `dpiit_fdi_factsheet`.
- GST release dates: the date the monthly GSTN PDF and XLSX files are published could not be established. Server Last-Modified (25 Sep 2026 for all files) reflects a bulk sync, so both GST entries now record `date: unknown`.
- RBI Bulletin imprints for issues other than Sept 2026 were not checked; they are assumed to match.
- New entries added in the fix pass: `mospi_asuse_unit_data` and `nsi_small_savings_collections` were independently verified in the Phase 1 refresh (section 7); `dpe_public_enterprises_survey` is still unverified. The DPE survey could not be read at all.
- The base behind CAG SF 2024-25's 15.78% of GSDP ratio. The FSF 2023-24 base (old base is inferred).
- 2024-25 SUT timing: inferred to follow the Final Estimates on 26 Feb 2027.

### 6.4 Gaps and data problems to log in ISSUES.md

These are not source disputes, but they affect the SAM and must be logged loudly (SPEC rule 4):

1. There are no new-base institutional sequences of accounts. The D1–D8 transfers by institution must be estimated from old-base NAS 2024 (to 2022-23) and labelled `estimated`.
2. Saving–investment errors & omissions and the household GDI residual are non-zero even in Final years (see §2 fact 4).
3. Statement 6.1 shows services imports without the CIF adjustment (−5,27,525 vs −2,34,750 implied; the CIF adjustment is 2,92,776). The SAM RoW account needs one consistent treatment.
4. NAS 4.2 COFOG has no interest payments.
5. The SUT has no valuation or import-use matrices and no GST sub-split. A symmetric IOT must be derived.
6. HCES is about 44% of PFCE (and the Adhikari gap is 45% in 2011-12, about 54% in 2023-24), concentrated in non-food. There is no official household income distribution.
7. The PLFS design break in 2025 and the ASUSE gap for Oct–Dec 2024.
8. FSF/FoF exists only to 2023-24, on the old base (inferred), and its FWTW tables are sector × sector only. The FSF workbook has legacy sheets S 8.4–8.7 labelled "₹ Billion".
9. The RBI (52a) and NSO (T11) household financial saving estimates differ, and both are revised heavily between vintages.
10. SEBI Handbook T11 has a corporate-bond reclassification break between 2023-24 and 2024-25.
11. Budget and Economic Survey %-of-GDP ratios use the old base. CGA Provisional Accounts show recovery of loans at 24,617 in both years. The Urea subsidy differs between CGA and the Budget. The Budget XLSX files have small internal inconsistencies.
12. SUT files were revised on 31 Aug 2026 without a version stamp. Hash every download. The May PR totals no longer match.
13. Access behaviour to handle:
    - MoSPI and eSankhyiki are SPAs; use the JSON APIs. The MoSPI site answers **every** path, including nonexistent ones, with HTTP 200 and the same 2,644-byte shell, so a 200 does not prove a landing page exists. Validate landings through `POST /api/publications-reports/get-web-publications-report-list` (this was done for every MoSPI SPA landing in the registry). The 2007-08 IOTT has no page on the current site, so its landing is now the PDF. dpe.gov.in behaves the same way.
    - The rbidocs F5 challenge is served **with HTTP 200** (an HTML page in place of the file), so status checks cannot detect a failed download. Phase 1 must check each file's magic bytes (`PK` for XLSX, `%PDF` for PDF) and fail loudly on HTML. The dbie TLS mismatch and the RBI robots.txt 418 also need handling.
    - The gst.gov.in F5 challenge and anti-scraping terms.
    - The indiabudget and CGA HEAD requests return 404.
    - The IMF portal 403, UN Comtrade 429s, the OECD BaTIS partial-key 500 and the Energy API 500 on a missing parameter.
14. The FCNR(B)/ECB swap window and the oil shock distort 2026-27 external flows, so 2026-27 is unsuitable as a reference year.
15. Units are mixed inside a single publication. For example, the RBI State Finances study uses ₹ crore, per cent and ₹ lakh. Phase 1 must read the unit line of every sheet rather than assume a publication-wide unit.
16. The Phase 1 test suite should include a registry schema check that rejects empty required fields. `render.py` in the fix pass already asserts this, and every required field is now either filled or an explicit sentinel.
17. Coverage added in the fix pass: NSSF and small savings (household → government financing). NSI publishes annual gross, withdrawal and net collections for 2002-03 to 2025-26; the Union's NSSF liabilities are in the DEA public-debt reports and Budget at a Glance. The DPE Public Enterprises Survey is registered but unreadable (see §5 item 7a). The public vs private NFC split can rely on NAS 1.9 and 7.1A/7.1B in the meantime.

## 7. Phase 1 refresh (2026-09-29)

Done by the Phase 1 access-planner agent, which did not add any of the entries it verified. Checks ran 14:30-15:19 IST under DECISIONS D1-1 (browser-like headers, at least 2 s per host, no challenge solved, no login) and D1-2 (no unit-level data). The full access plan is in `docs/phase1/ACCESS_PLAN.md` and `data/access_plan.csv`.

### 7.1 Releases due 29-30 September 2026

| Release | Status at last check | Registry id |
|---|---|---|
| ASI 2024-25 results (ARC date 29 Sep) | Not released as of 15:19 IST on 29 Sep 2026 (MoSPI release feed and the ASI API still end at 2023-24); due later on 29 Sep per the ARC. | `mospi_asi` |
| External debt, end-June 2026 | Not released as of 15:19 IST on 29 Sep 2026 (RBI press-release listing); expected 30 Sep 2026. | `rbi_external_debt` |
| International investment position, end-June 2026 | Not released as of 15:19 IST on 29 Sep 2026 (RBI press-release listing); expected 30 Sep 2026. | `rbi_intl_investment_position` |
| Invisibles, Q1 2026-27 | Not released as of 15:19 IST on 29 Sep 2026 (RBI press-release listing); expected 30 Sep 2026. | `rbi_invisibles_quarterly` |
| BoP Q1 2026-27 | Already out on 1 Sep 2026 | `rbi_bop_quarterly` |
| DEA Quarterly Report on Public Debt, Apr-Jun 2026 | Not on the DEA listing | `dea_public_debt_reports` |
| RBI Bulletin Sept 2026 (household financial saving) | Out 25 Sep (already recorded) | `rbi_hh_fin_savings` |

None of these changes a 2023-24 number: the reference year uses ASI 2023-24, end-March 2024 external stocks and 2023-24 BoP from the RBI Handbook.

### 7.2 Verification of entries nobody had checked

| Entry | Before | After | Evidence |
|---|---|---|---|
| `mospi_asuse_unit_data` | unverified | **verified** | NADA catalogs 293 and 238 re-read (created/modified dates), get-microdata says 'must be logged in'; GSDD 2026 Category B text re-read. Formats not seen (files not requested under D1-2). |
| `nsi_small_savings_collections` | unverified | **verified** | Table re-read (2023-24 net 4,21,678.35); independent match with Receipt Budget 2025-26 Annex 8 (4,21,678.36); Copyright Policy read. Publication date still unknown. |
| `ppac_petroleum_exchequer` | unverified | **verified** | XLS 'Table Posted: (17.07.2026)', 2014-15 to 2025-26 (P); Terms & Conditions allow free reproduction with accuracy and acknowledgement. |
| `dpe_public_enterprises_survey` | unverified | unverified | Page is still an empty Next.js shell; content comes from a CMS called with a key embedded in the site's JavaScript, which D1-1 does not allow us to use. Not needed by any gap-map cell. |
| `cbdt_time_series` | unverified | unverified | Registry URL check got 403 (bot page) then 200 minutes later: intermittent blocking. Not automated (D1-1(c)); licence unread. |
| `gstn_gst_statistics` | disputed | disputed | Not automated (D1-1(c)). The cess question no longer matters for the SAM: T_GCES comes from Finance Accounts MH 0009. |

### 7.3 Access findings that change how Phase 1 fetches

- **rbidocs.rbi.org.in is intermittent.** The same full browser header set fetched 18 rbidocs files cleanly at 14:39-14:40 IST, then got the F5 challenge (HTTP 200, 5,691-byte HTML page) on every rbidocs file from about 15:00 IST. Probing stopped (D1-1(b)). www.rbi.org.in pages (listings, PublicationsView HTML tables, press releases) were never challenged. Every rbidocs-hosted entry now carries this note.
- **OECD ICIO 2025 zip** returned a Cloudflare challenge (HTTP 403); the ReadMe on the same host worked. ADB MRIO and FIGARO are the open alternatives for the P6a prior.
- **TLS:** api.mospi.gov.in needs legacy renegotiation (Python's OpenSSL refuses it even with the OS trust store); dea.gov.in and nsiindia.gov.in send incomplete certificate chains (fine with the OS trust store).
- **AIDIS 2019:** the Report 588 PDF could not be found on the current MoSPI site, but the report's tables are served by the eSankhyiki NSS-77 AIDIS API, including assets and loans by MPCE quintile.
- **Budget actuals for 2023-24** are in the Budget 2025-26 archive; there the receipt tables are `.xls` (the `.xlsx` names return 404). Receipt Budget Annex 8 gives NSSF sources and application for 2023-24, and Annex 7 gives return-filing distributions (a partial CBDT substitute).
- **Gap-map ids that are not registry ids:** `ppac_exchequer`, `dea_public_debt_quarterly` and `imf_sdmx_portal`. The registry records them as `aliases` of `ppac_petroleum_exchequer`, `dea_public_debt_reports` and `imf_sdmx`.
