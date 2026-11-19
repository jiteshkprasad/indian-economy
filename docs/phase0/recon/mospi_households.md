# Phase 0 recon — Household surveys (HCES, PLFS, ASUSE, AIDIS, SAS, others)

Family id: `mospi_households`
Recon date: 2026-09-29 (all fetches made on this date unless stated)
Scratch folder used for small probe downloads (outside repo):
`C:\Users\PC\AppData\Local\Temp\claude\D--India-Economy-Model\861f3371-...\scratchpad\hh`
Nothing was downloaded into the repo.

Method: WebSearch to locate documents, then `curl -L` with a browser User-Agent to confirm
HTTP status / content type / size, `pdftotext` to read PDFs, `openpyxl` to inspect Excel
tables, and direct calls to the public MoSPI API (`api.mospi.gov.in`) to confirm what is
machine-readable. WebFetch was used where it worked; PIB pages return 403 to WebFetch but
200 to curl, so PIB was read with curl.

---

## 0. Headline findings (read this first)

1. **HCES: only two rounds exist on the new design — 2022-23 (Aug 2022–Jul 2023) and 2023-24
   (Aug 2023–Jul 2024). There is no 2024-25 or 2025-26 HCES round**, and none is listed in
   MoSPI's Advance Release Calendar 2026-27 or in MoSPI's list of surveys planned for 2026-27
   (Annual Report 2025-26). So the latest household consumption distribution is **2023-24**.
2. HCES detailed reports ship with **Excel detailed tables** (item-level x 12 MPCE fractile
   classes x rural/urban; item-level x State; item-level x State *with imputation* of free
   PDS/scheme items). These are directly usable for the SAM household consumption block.
   Imputed values of free items are published **by State, not by fractile class** (MoSPI
   deliberately did not publish imputed values cross-classified by fractile).
3. **MoSPI now has a free, key-less JSON/CSV API** (`https://api.mospi.gov.in`, the
   eSankhyiki backend) with HCES, PLFS, ASUSE, NAS and more. Verified live today without any
   token. Swagger files and a MIT-licensed Python client are on GitHub (`nso-india`).
4. **PLFS changed design and calendar in Jan 2025**: annual reports are now calendar-year
   (first: PLFS Annual Report 2025, released 27 Mar 2026); **there is no July 2024–June 2025
   annual report**. Last agricultural-year report = 2023-24. 2025 results are flagged by MoSPI
   as "may not be strictly comparable" with earlier years.
5. PLFS **published tables do not give regular-wage earnings by industry** (only by
   occupation, state, gender, sector); casual wages are published by NIC section. Labour
   income by SAM sector x rural/urban therefore needs **PLFS unit-level data** (free with
   registration, non-commercial).
6. **India has no official household income distribution yet.** The first National Household
   Income Survey (NHIS) is in the field (April 2026 → March 2027 per PIB); no results exist.
   AIDIS/SAS next round is July 2026–June 2027; latest usable AIDIS/SAS = NSS 77th round (2019).
7. **Licence**: MoSPI's revised Guidelines for Statistical Data Dissemination (GSDD 2026,
   Gazette notification dated 27 Apr 2026) put NSS reports/factsheets in "Category A — open
   access, free of cost", and NSS unit-level data in "Category B — registered access", free
   **only for non-commercial use**, priced for commercial use. No explicit GODL-India
   statement was found on MoSPI's own pages. The project owner must decide/confirm whether a
   free public website run by Udgam Labs counts as non-commercial before we use unit data.
8. **HCES vs NAS gap (my computation, `estimated`)**: HCES 2023-24 per-capita consumption is
   about **51% of new-series (base 2022-23) NAS per-capita PFCE for 2023-24**, and HCES's own
   population estimate (1,217.6 mn) is ~13% below the population implied by NAS. The SAM must
   use HCES only for *shares/distribution* and NAS PFCE for *levels*.
9. **GDP base-year revision happened**: new NAS series with base year 2022-23 released
   27 Feb 2026 (PIB). PIB states the new series uses HCES for PFCE quarterisation and adopts
   direct estimation from ASUSE and PLFS for the household sector — so these surveys are now
   inputs to the official accounts, which helps consistency.

---

## 1. Fetch log (every URL, result)

### 1.1 MoSPI main site
| URL | Result |
|---|---|
| https://www.mospi.gov.in/ | 200, 2,644-byte React SPA shell (`<div id="root">`); no content without JS |
| https://www.mospi.gov.in/themes/product/71-household-consumption-expenditure-survey-hces | 200, same SPA shell |
| https://www.mospi.gov.in/themes/product/69-periodic-labour-force-survey-plfs | 200, SPA shell |
| https://www.mospi.gov.in/robots.txt | returns SPA shell HTML (no robots file served) |
| https://www.mospi.gov.in/copyrights-policy (WebFetch) | only page title returned; SPA — **could not read MoSPI's copyright policy text** |
| https://www.mospi.gov.in/assets/index-FXIi3u1F.js | 200, 5.8 MB bundle; shows internal endpoints under `https://www.mospi.gov.in/api/` |
| https://www.mospi.gov.in/api/main-site/product-search?search=... | **403 Forbidden** — did not pursue further (not a documented public API) |
| https://www.mospi.gov.in/uploads/latestReleases/...Press_Note_on_New_Series_of_GDP_Estimates_with_Base_Year_2022-23_27022026.pdf | **403 Forbidden** to curl (other `/uploads/` PDFs returned 200). Read the PIB version instead |
| Chrome-extension rendering | Not used: several browsers connected and a subagent cannot ask the user to pick one |

Direct PDF/XLSX links under `/sites/default/files/...` and most `/uploads/...` links work
with curl (200).

### 1.2 HCES
| URL | Result |
|---|---|
| https://www.mospi.gov.in/sites/default/files/press_release/HCES_Press_Note_2023-24_27122024_rev.pdf | 200 PDF 782 KB — factsheet press note, 27 Dec 2024 |
| https://mospi.gov.in/sites/default/files/press_release/HCES_Report202324_Press_Note_30012025.pdf | 200 PDF 275 KB — dated "30th January 2025"; "The detailed report of the Household Consumption Expenditure Survey: 2023-24 ... along with the unit level data is being released now." Also: "the detailed report and the unit level data of the survey of 2022-23 was released in June 2024." |
| https://www.mospi.gov.in/sites/default/files/publication_reports/Final_Report_HCES_2023-24L.pdf | 200 PDF 11.7 MB, 225 pages, "NSS Report no. 592" |
| https://www.mospi.gov.in/sites/default/files/publication_reports/Report_591_HCES_2022-23New.pdf | 200 PDF 7.5 MB, 228 pages, "Report no. 591 (HCES: 2022-23)" |
| https://www.mospi.gov.in/sites/default/files/publication_reports/Factsheet_HCES_2022-23.pdf | 200 PDF 5.9 MB |
| https://mospi.gov.in/sites/default/files/publication_reports/HCES-23-24/TableA1.xlsx | 200 xlsx 12 KB |
| .../HCES-23-24/TableA2.xlsx | 200 xlsx 96 KB (households/persons by fractile, State) |
| .../HCES-23-24/TableA6.xlsx | 200 xlsx 433 KB (broad item groups x 12 fractiles x State/All-India) |
| .../HCES-23-24/TableA10F-Fractile-class-All%20India.xlsx | 200 xlsx 577 KB (detailed items x 12 fractiles, All-India) |
| .../HCES-23-24/TableA10S-State.xlsx | 200 xlsx 1.6 MB (detailed items x State) |
| .../HCES-23-24/TableA10SW-State-WithImputation.xlsx | 200 xlsx 1.6 MB (detailed items x State, with imputation) |
| Other 2023-24 links extracted from the report PDF (A3, A4, A5, A7, A8R, A8U, A9) | listed in PDF annotations; not individually fetched |
| https://www.mospi.gov.in/sites/default/files/publication_reports/HCES-22-23N/Table%20A6.xlsx | 200 xlsx 437 KB |
| .../HCES-22-23N/Table%20A10F-Fractile%20class-All%20India.xlsx | 200 xlsx 635 KB |
| (2022-23 file list from report annotations: Table A1–A9, A10F, A10S, "A10SW-State (With Imputation)") | note spaces in 2022-23 filenames |
| https://www.pib.gov.in/PressReleasePage.aspx?PRID=2150168 (curl) | PIB 30 Jul 2025: "The last survey on Household Consumption Expenditure was conducted during August, 2023-July, 2024." WebFetch got 403 |
| https://microdata.gov.in/NADA/index.php/catalog/CEXP | 200; lists catalog/237 "HCES 2023-24", catalog/224 "HCES 2022-23", then older NSS rounds (68th 2011-12 etc.) |
| https://microdata.gov.in/NADA/index.php/catalog/237 | 200; ID DDI-IND-MOSPI-NSS-HCES23-24; created Apr 22 2025, last modified Apr 13 2026 |
| https://microdata.gov.in/NADA/index.php/catalog/237/get-microdata | "To access data for this study, user must be logged in ... register for a free account." |
| https://microdata.gov.in/NADA/index.php/catalog/237/related-materials | lists Layout_HCES 2023-24.xlsx, Readme, Imputation_Rate.xlsx, Survey methodology PDF, zip data |
| https://microdata.gov.in/NADA/index.php/catalog/237/data-dictionary | 15 data files "LEVEL-01 ... LEVEL-15" (section-wise) |
| https://microdata.gov.in/NADA/index.php/catalog/224 | ID DDI-IND-MOSPI-NSSO-HCES22-23; created Dec 20 2024 (portal entry; data first released June 2024), last modified Jul 23 2026 |

### 1.3 MoSPI API (eSankhyiki backend)
| URL | Result |
|---|---|
| https://github.com/nso-india/esankhyiki-mcp (WebFetch) | MCP server at https://mcp.mospi.gov.in/, code MIT; datasets incl. PLFS, HCES, ASUSE, NSS77, TUS |
| https://raw.githubusercontent.com/nso-india/mospi-esankhyiki/main/README.md | Python client, "500+ statistical indicators across 30 datasets" |
| .../esankhyiki/client.py | `# str = "https://api.mospi.gov.in" PROD` |
| .../swagger/swagger_user_hces.yaml | `/api/hces/getHcesRecords` with indicators incl. MPCE over 12 fractile classes, MPCE over broad categories, imputation_type_code, mpce_fractile_classes_code, item_category_code |
| .../swagger/swagger_user_plfs.yaml | `/api/plfs/getData`; declares a `bearerAuth` scheme, but calls succeed without a token |
| https://api.mospi.gov.in/api/hces/getHcesRecords?indicator_code=Monthly Per Capita Consumption Expenditure (MPCE) over Broad Categories in 30 Days&year=2023-24&sector_code=1&state_code=99 | 200 JSON; e.g. Rural, Without Imputation, "Cereal" value "204.76", unit "₹" |
| https://api.mospi.gov.in/api/hces/getHcesRecords?indicator_code=Average monthly per capita consumption expenditure (MPCE) (3 pages) | years present: 2022-23, 2023-24 only |
| https://api.mospi.gov.in/api/plfs/getIndicatorListByFrequency?frequency_code=1 | 8 annual indicators incl. 6 = regular wage/salary earnings, 7 = casual wage per day, 8 = self-employment gross earnings (30 days) |
| https://api.mospi.gov.in/api/plfs/getFilterByIndicatorId?indicator_code=6&frequency_code=1 | years: 2025, 2024, 2023-24, 2023, 2022-23, 2022, 2021-22 ... 2017-18; year_type Calendar/Agriculture; sector rural/urban/total; **no industry filter** |
| https://api.mospi.gov.in/api/plfs/getData?indicator_code=6&frequency_code=1&year_type_code=1&year=2023-24&state_code=99&sector_code=3&gender_code=3 | 200 JSON; quarterly values for 2023-24, e.g. Apr-Jun "21103.2" ₹ |
| .../getFilterByIndicatorId?indicator_code=1&frequency_code=2 | quarterly years 2018–2026 |
| .../getFilterByIndicatorId?indicator_code=1&frequency_code=3 | monthly years 2025, 2026 |
| https://api.mospi.gov.in/api/asuse/getAsuseIndicatorListByFrequency?frequency_code=1 | 200 JSON, indicator list (establishments, ownership, ...) |
| https://api.mospi.gov.in/api/nas/getNasIndicatorList | `{"error":"Please check the input parameters passed"}` (NAS is out of scope for this family) |

### 1.4 PLFS
| URL | Result |
|---|---|
| https://www.mospi.gov.in/uploads/latestReleases/latest_release_1774607827733_..._Press_note_AR_PLFS_2025_23032025_V2.1_26032026_final.pdf | 200 PDF 409 KB; dated "27th March 2026"; PLFS Annual Report 2025 [Jan–Dec 2025]; 2,70,472 households; earnings figures; unit-level first-visit data on microdata portal; comparability warning |
| https://www.mospi.gov.in/sites/default/files/publication_reports/PLFS_Changes-in-2025_rev.pdf | 200 PDF 4.3 MB (design change note) |
| https://www.mospi.gov.in/sites/default/files/publication_reports/AnnualReport_PLFS2023-24L2.pdf | 200 PDF 26.9 MB; Annual Report PLFS 2023-24; Appendix tables incl. Table 50 (regular wage earnings by NCO occupation division) and Table 51 (casual wage by NIC-2008 section) |
| https://www.mospi.gov.in/uploads/documents/releaseCalender/1770293210621-ADVANCE%20RELEASE%20CALENDAR%202026-27%20FINAL%2005.02.2026.pdf | 200 PDF; see §2.2 |
| https://www.pib.gov.in/PressReleaseDetail.aspx?PRID=2310427 (curl) | PLFS Monthly Bulletin August 2026: "The overall LFPR (15+ years) increased to 55.6% in August" |
| https://microdata.gov.in/NADA/index.php/catalog/PLFS | 200; studies 204–217 (2017-18 to 2023-24, CY2021–23), 254 (CY 2024 key indicators), 284 (CY 2025), 291 (monthly Apr–Dec 2025), 292 (quarterly Apr-Jun 2025 to Oct-Dec 2025) |
| https://microdata.gov.in/NADA/index.php/catalog/284/related-materials | FV_Data_LayoutPLFS_2025.xlsx, PLFStxt2csv2025.zip, schedules, README2025.docx |
| PLFS Annual Report 2025 full PDF | **not located** (press note says it is on mospi.gov.in; the SPA site could not be browsed). Unverified URL |

### 1.5 ASUSE
| URL | Result |
|---|---|
| https://www.mospi.gov.in/uploads/latestReleases/latest_release_1774347321466_..._Press_Note_ASUSE_2025_English.pdf | 200 PDF 472 KB; dated 24 Mar 2026; Table 1 key indicators ASUSE 2022-23 / 2023-24 / 2025 |
| https://microdata.gov.in/NADA/index.php/catalog/ENT | ASUSE 2021-22 (221), 2022-23 (222), 2023-24 (238), 2025 (293, created May 06 2026) |

### 1.6 AIDIS / SAS (NSS 77th round) and next round
| URL | Result |
|---|---|
| https://mospi.gov.in/sites/default/files/press_release/press_note-AIDIS--240821%20update.pdf | 200 PDF; NSS Report 588; press note dated 10 Sep 2021; assets as on 30.06.2018 |
| https://www.mospi.gov.in/sites/default/files/press_release/PressNote_AIDIS_SAS-Final.pdf | **404** |
| https://mospi.gov.in/sites/default/files/publication_reports/Report_587m_0.pdf | 200 PDF 60.5 MB (SAS report 587; not parsed) |
| https://www.pib.gov.in/PressReleasePage.aspx?PRID=1753856 (curl) | SAS 2019, 10 Sep 2021; "agricultural year July 2018 – June 2019" |
| https://www.pib.gov.in/PressReleasePage.aspx?PRID=2165638 (curl) | 11 Sep 2025: AIDIS and SAS "scheduled to be conducted from July 2026 to June 2027" |
| https://microdata.gov.in/NADA/index.php/catalog/156, /157 | AIDIS 77th round (156) and Land & Livestock + SAS 77th round (157) unit data listed |

### 1.7 Income survey and non-official sources
| URL | Result |
|---|---|
| https://www.pib.gov.in/PressReleasePage.aspx?PRID=2178574 (curl) | 13 Oct 2025: NHIS "scheduled to be launched in February, 2026 ... first-ever pan-India survey focused on measuring household income" |
| https://www.pib.gov.in/PressReleasePage.aspx?PRID=2241324 (curl) | 17 Mar 2026: "During its next survey (April 2026 to March 2026) [sic], NSO will be collecting data ... on 'National Household Income Survey'" |
| https://www.cmie.com/kommon/bin/sr.php?kall=wproducts&tabno=7010&prd=cpdx | 200; CPHS dx: record-level data "for the period of a valid subscription"; Income Pyramids released monthly; **no price shown** |
| https://www.price360.in/data-center-details.php?url=household-survey-on-indias-consumer-economy-and-citizens-environment-ice-360-survey-2021 | 200; ICE 360 2021 (Wave 3.0) household income/consumption/savings/debt; "Please Login/Register at this Link to obtain the Microdata"; site copyright "Reproduction is prohibited other than in accordance with the copyright notice" |
| https://ihds.umd.edu/data | 200; IHDS-1 and IHDS-2 via ICPSR; page says "The team is currently preparing IHDS 3" — **no IHDS-3 data release found** |
| https://ncaer.org/project/india-human-development-survey-round-3-ihds-3/ | 200; no release information extracted |
| https://wid.world/terms-of-use/ | 200 but no licence text extracted; **WID licence unverified** |

### 1.8 Licence / policy documents
| URL | Result |
|---|---|
| https://microdata.gov.in/NADA/index.php/dissemination | lists National Policy on Dissemination (1999), NSS publication policy (2017), Revised GSDD, OM on free microdata |
| https://mospi.gov.in/uploads/acts_and_policies/acts_and_policies1778231030122_..._272304_(1).pdf | 200 PDF (http:// version failed with curl code 000; https worked). **Revised GSDD 2026, Gazette notification dated 27 April 2026** |
| https://mospi.gov.in/sites/default/files/data_disemination/OM%20_to_disseminate_data%20free_.pdf | 200; OM 22.03.2019: free microdata via national repository from 1 Apr 2019 |
| https://mospi.gov.in/sites/default/files/main_menu/data_discremination/policy_nss_pub_25se17.pdf | 200 PDF 2.2 MB but **scanned image; pdftotext returned no text** — not read |
| https://microdata.gov.in/NADA/Guide_to_download_microdata.pdf | 200; register → activate by email → fill application form → agree data access agreement → download .rar (CSV/Nesstar) |
| https://pib.gov.in/Content/102_2_Copyright-Policy.aspx | PIB content "may be reproduced free of charge and there is no need for any prior approval" with source acknowledged |
| https://www.niip.gov.in/web/mospi/copyright-policy | curl failed (code 000) |
| MoSPI copyright page | Not readable (SPA). A search-engine snippet attributed to MoSPI says material may be reproduced free of charge "after taking proper permission by sending a mail" — **unverified**, needs manual check by owner in a browser |

### 1.9 NAS context (only as it affects this family)
| URL | Result |
|---|---|
| https://www.pib.gov.in/PressReleasePage.aspx?PRID=2233518 (curl) | 27 Feb 2026: new series base 2022-23. PFCE current prices ₹163.77 lakh crore (2023-24), ₹179.71 lakh crore (2024-25); per capita PFCE ₹1,17,356 (2023-24). Data-source table lists "Household Consumption Expenditure Survey for quarterization" under PFCE |
| https://www.mospi.gov.in/uploads/publications_reports/...MoSPI_Annual_Report_English_2025-26.pdf | 200 PDF 27.5 MB; surveys planned 2026-27: NHIS, SAS, AIDIS, Migration, ASISSE, co-operatives (no HCES) |

---

## 2. Source-by-source notes

### 2.1 HCES — Household Consumption Expenditure Survey (NSO/MoSPI)
- **Rounds**: 2022-23 (Aug 2022–Jul 2023; NSS Report 591) and 2023-24 (Aug 2023–Jul 2024;
  NSS Report 592). Before that, NSS 68th round 2011-12 (and 2017-18 was junked, never released).
- **Release dates**: 2022-23 factsheet Feb 2024, report + unit data June 2024 (per HCES
  2023-24 report press note and MoSPI Annual Report 2025-26). 2023-24 factsheet 27 Dec 2024;
  report + unit data 30 Jan 2025.
- **Lag**: ~5 months (factsheet) / ~6 months (report + microdata) after end of fieldwork.
- **Next round**: none scheduled. Not in ARC 2026-27; not in MoSPI's 2026-27 survey plan.
  A news report (Business Standard, via search) quotes the Secretary saying HCES would be done
  every three years — **unverified**.
- **Sample**: 2023-24: 2,61,953 households (1,54,357 rural, 1,07,596 urban); 14,827 FSUs.
- **Price basis**: current (nominal) prices of the survey year; report also gives MPCE at
  2011-12 prices (CPI-deflated). Home-produced food valued at ex-farm prices; free
  collections at local retail prices. Not linked to NAS base year.
- **Key numbers (2023-24, without imputation)**: MPCE Rural ₹4,122, Urban ₹6,996; with
  imputation of free items ₹4,247 / ₹7,078. Gini 0.237 rural, 0.284 urban (press note).
  Food share 47.04% rural / 39.68% urban (Table 3.5).
- **Tables (Excel, "Appendix A")**: A1 sample; A2 estimated households and persons by
  fractile (in '00) and average MPCE; A3 household size by fractile; A4/A5 cereals & pulses
  qty/value by fractile; **A6 value of broad item groups per person per 30 days x 12 fractile
  classes x State/All-India, rural/urban**; A7 distribution of households across all-India
  fractiles by State; A8R/A8U household type; A9 social group; **A10F detailed items (~400
  item codes) x 12 fractile classes, All-India, qty + value per person per 30 days**;
  **A10S detailed items x State**; **A10SW detailed items x State, with imputation** (includes
  items like "061 rice-free" with imputed values).
- **Fractile classes**: 12 classes (0-5, 5-10, 10-20, ..., 90-95, 95-100%), separately for
  rural and urban. Quintiles can be built exactly from these (0-20 = 0-5+5-10+10-20, etc.).
- **Imputation quirk**: "estimates of MPCE values with imputation as well as various types of
  cross-classifications of the same by fractile classes of MPCE have not been generated"
  (Report 592, §3.1.4). So free-item values by quintile require unit-level data. Free
  health (PM-JAY) and free education are **not** imputed (§2.2.4).
- **Units**: ₹ per person per 30 days (value), kg/number per person per 30 days (quantity);
  households/persons in hundreds ('00).
- **Unit-level data**: microdata.gov.in catalog 237 (2023-24), 224 (2022-23). 15 section-level
  data files (LEVEL-01 ... LEVEL-15), layout xlsx, imputation-rate xlsx, readme. Free login.
- **API**: `/api/hces/getHcesRecords` — MPCE, MPCE by 12 fractiles, broad categories (value
  and %), quantities, household type, social group, Gini; with/without imputation; years
  2022-23 and 2023-24.
- **SAM blocks**: household consumption by commodity split rural/urban x quintile (shares);
  household account disaggregation; in-kind transfers from government (PDS etc., State-level);
  CPI/COICOP mapping; ABM household heterogeneity (unit data).
- **Known quirks**: (a) HCES aggregate ≪ NAS PFCE (see §3); (b) HCES population estimate
  ~1.22 bn vs ~1.40 bn implied by NAS; (c) three-visit, three-questionnaire design (FDQ, CSQ,
  DGQ) differs from pre-2022 rounds — not comparable with 2011-12 without care; (d) survey year
  Aug–Jul, not Apr–Mar; (e) filenames for 2022-23 Excel contain spaces; 2023-24 do not;
  (f) rent in rural ₹23 per capita — imputed rent of owner-occupiers not included.

### 2.2 PLFS — Periodic Labour Force Survey
- **Design**: 2017-18 to 2023-24 annual reports on agricultural year (Jul–Jun), rural+urban
  usual status; quarterly bulletins (urban CWS) from 2018. From **January 2025** new design:
  rotational panel, monthly visits, 2.72 lakh households, monthly bulletins (rural+urban CWS),
  quarterly bulletins, and **calendar-year** annual report.
- **Latest**: Annual Report 2025 (CY 2025), press note dated 27 Mar 2026; unit data catalog 284
  (created 27 Mar 2026). Monthly bulletin August 2026 released (PIB, ~mid-Sep 2026). ARC
  2026-27: quarterly bulletin Apr–Jun 2026 on 15 Sep 2026; Annual Report CY 2026 with unit
  data on 25 Mar 2027 (scheduled, not yet happened).
- **No July 2024–June 2025 annual report exists.** CY 2024 key indicators exist (catalog 254,
  created 25 Aug 2025) and the API carries year "2024".
- **Earnings**: average regular wage/salary earnings in preceding calendar month (₹), casual
  wage per day (₹), self-employment gross earnings in last 30 days (₹); by sector, gender,
  State. 2025: regular wage male ₹24,217, female ₹18,353; self-employed male ₹17,914, female
  ₹6,374; casual male ₹455/day, female ₹315/day (press note).
- **Industry detail**: published appendix tables give casual wages by NIC-2008 section (Table
  51, 2023-24 report) but regular wages only by NCO occupation (Table 50). API earnings
  indicators have **no industry dimension** (industry codes apply only to indicator 4, worker
  distribution). → SAM labour income by sector needs unit data.
- **Lag**: annual ~3 months after end of reference period (CY 2025 → 27 Mar 2026); monthly
  bulletin ~2–6 weeks.
- **Units**: rates in %, earnings in ₹ (nominal). No base year (nominal survey values).
- **SAM blocks**: factor account split (compensation of employees vs mixed income by
  employment status), labour input by sector x rural/urban x gender, wage rates for ABM,
  employment weights for distributing NAS CE/mixed income across household groups.
- **Quirks**: 2025 break in series (explicit MoSPI caveat); worker counts are ratios —
  absolute workers need population projections (MoHFW); earnings are from first-visit CWS
  schedule; earnings under-report relative to NAS compensation.

### 2.3 ASUSE — Annual Survey of Unincorporated Sector Enterprises
- **Rounds**: 2021-22 (Apr 2021–Mar 2022), 2022-23 (Oct 2022–Sep 2023), 2023-24 (Oct 2023–Sep
  2024), **2025 (Jan–Dec 2025)**; note the gap Oct–Dec 2024. Quarterly bulletins from 2026.
- **Latest**: ASUSE 2025 factsheet/press note 24 Mar 2026; unit data catalog 293 created
  6 May 2026. Next: ASUSE 2026 factsheet scheduled 21 Mar 2027 (ARC).
- **Key indicators** (Table 1 of 2025 press note, all-India): GVA ₹15,42,409 cr (2022-23),
  ₹17,97,278 cr (2023-24), ₹19,92,577 cr (2025) — market establishments, current prices;
  workers 10.96 / 12.06 / 12.81 crore; emolument per hired worker ₹1,24,842 / ₹1,41,071 /
  ₹1,46,550.
- **Coverage**: unincorporated non-agricultural establishments in manufacturing, trade,
  other services, **excluding construction**; proprietorships, partnerships (not LLPs),
  co-ops, societies/trusts.
- **SAM blocks**: split of informal-sector GVA into emoluments (compensation) vs mixed income
  (operating surplus of own-account/household enterprises), by activity and rural/urban;
  household-enterprise production accounts; loans outstanding (household sector finance).
- **Quirks**: reference periods shift across rounds; excludes agriculture and construction;
  GVA figures are for market establishments only. Probably overlaps with an enterprise-survey
  recon agent — coordinate to avoid double entries.

### 2.4 AIDIS — All India Debt & Investment Survey (NSS 77th round, 2019)
- Report 588, released 10 Sep 2021 with unit data (catalog 156). Assets and debt stock as on
  30.06.2018; flows (capital expenditure, borrowing) for July 2018–June 2019 (per NSS design;
  flows reference period not re-read — **partly unverified**).
- AVA per household ₹15,92,379 rural (press note).
- Next round: July 2026–June 2027 (PIB 11 Sep 2025). Results likely 2028 (my inference).
- **SAM blocks**: household balance sheet (physical vs financial assets, debt by source —
  institutional vs non-institutional) for rural/urban and asset classes; ABM wealth
  distribution. Too old for the reference year → use as structural shares only, scaled to
  RBI household financial accounts.

### 2.5 SAS — Situation Assessment Survey of Agricultural Households (NSS 77th, 2019)
- Report 587 (60.5 MB PDF), PIB 10 Sep 2021; agricultural year July 2018–June 2019; unit data
  catalog 157 (combined with Land & Livestock Holdings).
- Gives agricultural household income by source (wages, crop cultivation, livestock,
  non-farm business, land leasing). Next round July 2026–June 2027.
- **SAM blocks**: split of agricultural mixed income vs wages among rural households; farm
  household income structure.

### 2.6 NHIS — National Household Income Survey 2026
- First official all-India household income survey. PIB 13 Oct 2025: launch scheduled Feb 2026,
  ~4.5 lakh households (4.5 lakh figure from secondary sources/press; PIB text read did not
  state it — partially unverified). PIB 17 Mar 2026: fieldwork "April 2026 to March 2026"
  (evident typo for March 2027). No data yet; "results by mid-2027" is from a secondary site
  — unverified.
- Confirms: **no official household income distribution exists for any past year.**

### 2.7 Other MoSPI household surveys (lower priority)
- Time Use Survey 2024 (report March 2025; catalog 236) — unpaid work, ABM time allocation.
- Household Social Consumption: Health (Jan–Dec 2025, catalog 290), Education (NSS 80th,
  catalog 255) — out-of-pocket health/education spending detail.
- Domestic Tourism Expenditure Survey (NSS 80th, Jul 2025–Jun 2026, catalog 307).
- CAMS (NSS 79th, 2022-23; catalog 220).

### 2.8 Non-official income/wealth sources
- **CMIE CPHS** (Consumer Pyramids dx): household panel ~170k+ households, monthly income by
  source, consumption, assets, debt; subscription-only; price not shown publicly → contact
  CMIE. Licence: proprietary; redistribution of record-level data not allowed (typical; terms
  not read). Methodological critiques exist (The India Forum, Pais 2021).
- **PRICE ICE 360°** 2021 (Wave 3): household income, expenditure, savings, debt; microdata via
  login/registration on price360.in; terms of reuse not read; site says reproduction
  prohibited except per copyright notice. Survey year 2020-21 (COVID-affected).
- **IHDS** (NCAER/UMD): IHDS-I 2004-05, IHDS-II 2011-12 on ICPSR (free account). IHDS-3
  fieldwork reportedly completed June 2024 (search snippet) but **no public release found**.
- **World Inequality Database (WID)**: India pre-tax/post-tax national income distribution
  consistent with NAS totals (DINA method); open access; licence not verified.
- **World Bank PIP**: uses HCES for poverty/inequality (not fetched in this pass).

---

## 3. HCES vs NAS PFCE — computed check (estimated, my calculation)
Inputs: HCES 2023-24 Table A2 (All-India "All classes" rows): rural persons = 6,369,630 +
2,177,724 ('00) = 854.7 mn at MPCE ₹4,121.79; urban persons = 2,895,339 + 733,741 ('00) =
362.9 mn at MPCE ₹6,996.26. NAS (base 2022-23, PIB 27 Feb 2026): PFCE 2023-24 = ₹163.77 lakh
crore; per-capita PFCE ₹1,17,356.

- HCES aggregate (x12 months) = ₹42.28 (R) + ₹30.47 (U) = **₹72.74 lakh crore** → 44% of NAS
  PFCE.
- Per-capita basis: HCES annual per-capita ≈ ₹59,700 vs NAS ₹1,17,356 → **~51%**.
- HCES population 1,217.6 mn vs NAS-implied 1,395.5 mn.
Caveats: survey year Aug–Jul vs FY Apr–Mar; HCES excludes imputed rent, FISIM, NPISH, free
health/education, etc. This is a Phase 0 screening number, not for publication.

---

## 4. Licence summary
- MoSPI GSDD 2026 (Gazette, 27 Apr 2026): Category A (open access, free): "Reports/factsheets
  of National Sample Surveys (NSS)". Category B (registered access): "Unit level NSS data",
  "free of cost only for non-commercial use including study/research purposes"; commercial use
  priced. Data Access Agreement: no onward sharing of unit data, cite the source, no
  re-identification, MoSPI may revoke access.
- No explicit GODL-India statement on MoSPI pages checked (MoSPI site unrenderable). GODL
  itself (data.gov.in, 2017) applies to data published on data.gov.in.
- MoSPI API/Python client: code MIT; data licence not stated in the repos.
- PIB content: reproducible free with source acknowledged (PIB copyright policy).
- **Action for owner**: confirm non-commercial status of the public site; if unclear, email
  MoSPI (gsdd-cicd@mospi.gov.in per GSDD §6) before using unit-level-derived aggregates.

---

## 5. Reference-year implications (household family)
| Dataset | Latest period available | Previous | Basis |
|---|---|---|---|
| HCES | 2023-24 (Aug 23–Jul 24) | 2022-23 | current prices, survey year |
| PLFS annual | CY 2025 (new design); Ag-year 2023-24 (old design) | CY 2024, 2022-23 | nominal ₹ |
| PLFS unit data by quarter | lets us assemble FY 2023-24 (Apr–Jun 2023 from 2022-23 round + Jul 2023–Mar 2024 from 2023-24 round) | | |
| ASUSE | CY 2025; 2023-24 (Oct 23–Sep 24) | 2022-23 | current prices |
| AIDIS | 2019 (stocks at 30.06.2018) | 2013 | current |
| SAS | Ag-year 2018-19 | 2012-13 | current |
| NHIS | none (fieldwork 2026-27) | – | – |

Household-side view: **FY 2023-24** is the latest year with a full household consumption
distribution *and* matching labour and informal-enterprise surveys. FY 2022-23 (the new NAS
base year) is equally well covered (HCES 2022-23, PLFS 2022-23, ASUSE 2022-23). FY 2024-25 or
later would have **no HCES** and would need the 2023-24 distribution rolled forward (estimated).

---

## 6. Failures / open items
- MoSPI main site is a JS SPA; product pages, copyright page and full PLFS 2025 report URL
  could not be read. Internal `/api/main-site/...` returns 403 (not pursued).
- MoSPI `/uploads/latestReleases/...GDP...27022026.pdf` returned 403; PIB copy used.
- `PressNote_AIDIS_SAS-Final.pdf` 404.
- `policy_nss_pub_25se17.pdf` is a scanned image (no text layer).
- GSDD PDF via `http://` failed (curl 000), `https://` worked.
- niip.gov.in copyright page: curl 000.
- Chrome rendering not available (multiple browsers connected; subagent cannot ask user).
- WID licence, CMIE price, PRICE terms, IHDS-3 release: unverified.
