# Phase 0 recon — source family `mospi_io`
## MOSPI Supply-Use / Input-Output tables, ASI, IIP, CPI, WPI/PPI, Energy statistics, classifications

Recon date: 2026-09-29. Agent: mospi_io recon agent (Phase 0).
Probe downloads were saved only to the session scratchpad
(`C:\Users\PC\AppData\Local\Temp\claude\D--India-Economy-Model\861f3371-...\scratchpad\mospi_io\`), not to the repo.

---

## 0. Headline findings

1. **The GDP base year is now 2022-23.** MoSPI released the new National Accounts series (base 2022-23, replacing 2011-12) on **27 Feb 2026**. It **updated the series on 31 Aug 2026** in the "National Accounts Statistics 2026" publication, which uses the new PPI, IIP and BkSPI (all base 2022-23) released in June 2026. The NAS 2026 vintage contains Final Estimates (FE) for 2022-23 and 2023-24, First Revised Estimates (FRE) for 2024-25 and Provisional Estimates (PE) for 2025-26. The back series (pre-2022-23) is **not yet released**. The FAQ says it is "expected to be released by December 2026".
2. **Supply and Use Tables (SUT) exist on the new base for 2022-23 and 2023-24.** They were first released on **15 May 2026** and **revised on 31 Aug 2026** to match NAS 2026. They are 155 products x 67 industries, at current prices, in Rs crore, as Excel. Under the new series the SUT is *integrated* with the annual final estimates, so the statistical discrepancy is **zero** in those years. The revised SUT reproduces NAS 2026 GDP exactly: 2,61,77,001 crore in 2022-23 and 2,90,73,287 crore in 2023-24.
3. **The old-base SUTs (2011-12 base, 140 x 66) cover 2011-12 to 2021-22**, one file per year. They are still downloadable, but they are **not consistent with the new base**.
4. **MoSPI publishes no official symmetric Input-Output Transactions Table (IOTT) after 2007-08** (130 sectors). A Leontief/SAM model must derive a symmetric IOT from the SUT (for example under the industry-technology assumption). The only public derived IOT found for recent years is the Brookings India/CSEP IOTT 2015-16 (131 sectors, third party, old base).
5. **Price and quantity indices have all been rebased in 2026:**
   - IIP: base 2022-23 from April 2026 data (first release 1 Jun 2026; series from Apr 2023).
   - CPI: base 2024=100 from January 2026 data (first release 12 Feb 2026; series from Jan 2025, general-index back series via linking factor to Jan 2013).
   - WPI: base 2022-23 plus new Output PPI, trial Input PPI and Service PPIs (released 15 Jun 2026 by the Office of the Economic Adviser, DPIIT). WPI will be discontinued 5 years after that date.
6. **ASI: the latest is 2023-24** (results 27 Aug 2025, publications 30 Sep 2025). ASI 2024-25 results had **not** been released as of 28 Sep 2026 (see below). Unit-level data sit on microdata.gov.in behind a **free login**.
7. **MoSPI has a working, keyless open JSON/CSV API at `https://api.mospi.gov.in`** (eSankhyiki) covering IIP, CPI (incl. base 2024), WPI (incl. base 2022-23), ASI, NAS, Energy and ISP. There is also an official MCP server (mcp.mospi.gov.in) and an MIT-licensed client repo (github.com/nso-india/esankhyiki-mcp). The API **does not serve the SUT**, which is Excel-only.

---

## 1. Access quirks (important for the pipeline)

- **www.mospi.gov.in is a React SPA.** Every route (e.g. `/publications-reports/innerpage/847`) returns the same ~2.6 KB HTML shell, so page content cannot be scraped. The SPA loads data from a JSON backend by **POST** to `https://www.mospi.gov.in/api/...` (a GET returns 403). Useful endpoints (found in `/assets/index-FXIi3u1F.js`):
  - `POST /api/latest-release/get-web-latest-release-list` with body `{"page_size":50,"search_term":"","sort_field":"published_year","sort_order":"DESC","data_source":"web","page":1}`
  - `POST /api/publications-reports/get-web-publications-report-list` (same body)
  - `POST /api/publications-reports/get-web-chapter-data` with body `{"publication_id":"847","lang":"en","page_no":1,"page_size":100,"sort_field":"id","sort_order":"ASC"}` (this is the list of files in a publication)
  - `POST /api/copy-right-policy/get-copy-right-policy-data`, `/api/terms-and-conditions/get-terms-and-conditions-data`, `/api/disclaimer/get-disclaimer-data` with body `{"lang":"en"}`
  - `POST /api/release-calender/fetch-all-release-calender-Web` with body `{"lang":"en","year":"2026"}` (returned only 10 sparse entries, so it is not useful as a calendar)
- **File downloads (`/uploads/...`, `/sites/default/files/...`) return HTTP 403 to WebFetch and to plain curl.** They return HTTP 200 when curl sends ordinary browser navigation headers (`Sec-Fetch-Dest: document`, `Sec-Fetch-Mode: navigate`, `Sec-Fetch-Site: same-origin`, a browser User-Agent and a Referer). No login, CAPTCHA or cookie is involved: this is the header set any browser sends. `robots.txt` on www.mospi.gov.in returns the SPA shell (no robots rules published). Pipeline scripts must send these headers.
- **WebFetch returned 403** for www.mospi.gov.in PDFs and for www.pib.gov.in. curl with browser headers returned 200 for both.
- API file metadata can be wrong. In the publication-847 listing, several `filesize` values are nonsense (e.g. 351272960 for a PDF). In the Energy Statistics 2026 listing, Chapter 6 and Chapter 7 carry the same filesize (2300773), but the Chapter 7 file actually downloaded at 2,704,662 bytes. Do not trust `filesize`.
- **Vintage replacement without a version trail.** The May-2026 SUT xlsx files were silently replaced by files uploaded on 2026-08-31 (the filename suffix is `_(1)`, and the upload timestamp 1788173315135 decodes to 2026-08-31 10:48 UTC). The original May files are no longer listed. The **pipeline must hash and archive every downloaded file.**
- eSankhyiki (`esankhyiki.mospi.gov.in`) is also an SPA. Its robots.txt says `Allow: /` and it publishes `llms.txt`, `.well-known/ard.json` and an MCP server card. `api.mospi.gov.in/` serves a Swagger UI shell. The swagger YAMLs live in the GitHub repo `nso-india/esankhyiki-mcp/swagger/`.
- OEA site (`eaindustry.nic.in`): plain static files. They download with curl (200). The `disclaimer.asp` link on the home page returns **404**.

---

## 2. Sources (detailed)

### 2.1 MOSPI Supply and Use Tables (SUT) — new base 2022-23

- **Publication page:** https://www.mospi.gov.in/publications-reports/innerpage/847 (SPA). The file list comes from `get-web-chapter-data` with publication_id 847 (21 items, fetched 2026-09-29).
- **Files (new base):**
  - SUT 2022-23: `https://www.mospi.gov.in/uploads/publications_reports/publications_reports1788173286808_21cfcaa3-bdab-4e6a-9d0e-fda61f69f2ad_Supply_Use_table_2022-23_(1).xlsx` (189,097 bytes; sha256 415955ee…df19; published_date 2026-08-31)
  - SUT 2023-24: `https://www.mospi.gov.in/uploads/publications_reports/publications_reports1788173315135_8fb39764-d999-48c2-a479-67aee1e91051_Supply_Use_table_2023-24_(1).xlsx` (173,434 bytes; sha256 6fbaa0e9…fafd)
  - Methodological note: `https://www.mospi.gov.in/uploads/publications_reports/publications_reports1788173257610_f0d5f86d-0465-410e-85e8-f1c271803f26_Note_Supply_Use_Tables_2022-23,2023-24_(1).pdf` (818,198 bytes)
  - National Metadata Structure: `https://www.mospi.gov.in/sites/default/files/NMDS_SUT.xlsx` (16,149 bytes)
- **Press release (15 May 2026, PIB Release ID 2261377):** https://www.pib.gov.in/PressReleasePage.aspx?PRID=2261377 . A PDF copy is on MoSPI: `uploads/latestReleases/latest_release_1778842800782_…_Press_Release_Page___Press_Information_Bureau.pdf`. Quotes:
  - "it is the first comprehensive set of Supply and Use Tables compiled under the revised base year of 2022-23"
  - "compiled at a level of detail encompassing 155 products and 67 industries"
  - "the number of products have been increased to 155 from 140 in the previous base SUT"
  - "Total supply of goods and services at purchasers' prices in the economy amounted to 627.18 lakh crore in 2022-23 and 669.88 lakh crore in 2023-24". These are **May-vintage** numbers. The Aug-revised file gives Supply at PP of 6,28,00,721.7 crore for 2022-23.
- **NAS 2026 press release (31 Aug 2026), para 9:** "The Supply and Use Tables (SUTs) for 2022-23 and 2023-24 have also been updated to incorporate the above indicated changes. The revised SUTs along with the accompanying 'Methodological Note' are available … innerpage/847."
- **Structure, verified by opening the xlsx with openpyxl:**
  - Two sheets: `Supply Table 2022-23` and `Use Table 2022-23` (likewise for 2023-24). Title: "Supply Table at Current Prices".
  - 155 numbered product rows (Paddy … Recreation, entertainment…), plus rows for CIF, "Purchases of Residents abroad", "Purchases of Non-Residents in domestic market" and Total.
  - 67 industry columns (Agriculture … Public administration & defence).
  - The Supply sheet adds 9 valuation columns: Supply at BP, Imports, CIF Adj, Imports after cif adjustment, Import Duty, Product taxes, Subsidy on Products, Trade and Transport Margins, Supply at PP.
  - The Use sheet adds: Intermediate Consumption, PFCE, GFCE, GFCF, CII, Net Acquisition of Valuables, Export, Total Use at PP. Its value-added block has rows GVA (production approach), Production Taxes less Subsidies, Consumption of Fixed Capital, Compensation of Employees, Operating Surplus (which includes mixed income, "OS/MI" in the note), and GVA (income approach).
- **Units:** Rs crore. The xlsx has no unit label, but the Use-sheet sums equal the note's tables in "Value (Rs. Crore)".
  - 2022-23: GVA 2,38,23,136; NPT 23,53,866; GDP 2,61,77,001; CE 86,53,669; OS/MI 1,16,54,812; CFC 35,84,380.
  - 2023-24: GVA 2,64,05,480; GDP 2,90,73,287.
  - The xlsx sums I computed match: 2022-23 GVA 23,823,135.6 and NPT (import duty + product taxes – subsidies) 2,353,866; 2023-24 GVA 26,405,480.3.
- **Classifications:** the note (§5.2) says "NIC 2008 and NPCMS 2011 (Revised)/NPCSS have been used for classification and identification of products and industries", and §8.3 lists "NIC 2008, Revised NPCMS 2011, NPCSS, COICOP 2018, COFOG, and ITC-HS, with systematic mapping to 155 SUT products and 67 industries". **Contradiction:** the 15-May press release says "adoption of updated classifications like NIC 2025, COICOP 2018". I treat the note (the technical document) as authoritative (NIC 2008) and log the contradiction.
- **Quirks:**
  - Current prices only. No constant-price SUT.
  - Use table is at **purchasers' prices only**. There are no published valuation matrices (TTM and tax by use cell) and no import-use matrix: only supply-side vectors of TTM, product taxes, subsidies and import duty by product.
  - Blank cells are stored as the string `' '`, not as empty or 0.
  - Row and column labels have trailing spaces.
  - Product taxes are one vector, with no GST split (CGST/SGST/IGST/cess).
  - Balancing adjusted several vectors (IC, TTM, taxes, GFCF, CIS), per note §8.5.
- Licence: see §3.

### 2.2 MOSPI SUT — old base 2011-12 (2011-12 to 2021-22)

- Same publication 847. Files verified with a ranged GET, all HTTP 206 with the right content-type:
  - 2011-12: `…/National_Accounts/SUT_2011-12_balaced_supply__28092016.xlsx`
  - 2012-13: `…/balanced_SUT_12-13_dated_280916.xlsx`
  - 2013-14, 2014-15, 2015-16: `SUT_2013-14.xlsx`, `SUT_2014-15.xlsx`, `SUT_2015-16.xlsx`
  - 2016-17, 2017-18, 2018-19: `SUT%202016-17.xlsx`, `SUT%202017-18.xlsx`, `SUT%202018-19.xlsx`
  - 2019-20: `…/statistical_publication/SUT_2019-20_m.xlsx`
  - 2020-21 and 2021-22: `https://www.mospi.gov.in/uploads/documents/documents/1765449127276-Supply  Use Table 2020-21.xlsx` and `…1765449221032-Supply  Use Table 2021-22.xlsx`. Note the double space in the name. Uploaded 2025-12-11.
  - Notes: 2013-16, 2016-17, 2017-19, 2019-20, 2020-22.
- Dimensions: 140 products x 66 industries. I checked the 2021-22 file: 143 row labels = 140 products + CIF + Purchases abroad + Total.
- Units differ by vintage. SUT 2015-16 is in **"Value in Rs Lakh"**; SUT 2021-22 is "Values in Rs. Crore".
- Layouts differ too. The 2021-22 Supply sheet has "Total Output at Producer price", "Final Import" etc.; the 2015-16 sheet is named `Use bal 2015-16`.
- Use for a pre-2022-23 time series only with explicit bridging, because these tables are on the 2011-12 NAS vintage.

### 2.3 Input-Output Transactions Table (IOTT)

- Official: **IOTT 2007-08 (130 sectors)** is the last one MoSPI (CSO) published. PDF: https://www.mospi.gov.in/sites/default/files/reports_and_publication/cso_national_accounts/input_output_transactions_table/2007_08/Binder1.pdf (HTTP 200, application/pdf, 16.2 MB). Appendix 1 PDF: 206 OK.
- MoSPI API searches for "Input-Output", "Input Output Transactions", "IOTT" and "Transactions Table" all returned 0 records in publications, latest releases, public docs and announcements. **No IOTT exists for 2022-23 or 2023-24.**
- Third party: Brookings India (now CSEP), "Input Output Transactions Table: India 2015-16" (Chadha, Saluja, Sivamani, Jan 2020, draft for comments). It is a 131-sector IOT derived from SUT 2015-16. PDF: https://csep.org/wp-content/uploads/2020/01/Input-Output-Transactions-Table-India-2015-16.pdf (200). Quote: "using the latest publication of SUT 2015-16, the Input-Output Transactions Table 2015-16 has been constructed"; "There are 66 columns and 140 rows in the tables". Old base, PDF tables only.
- Third party: arXiv 2506.13936, 7-digit product-level SUT/IOT from ASI 2016-2022 (manufacturing only). Page returns HTTP 200. Not assessed further.
- **Implication:** the project must derive its own symmetric IOT from the 2022-23 or 2023-24 SUT. This is an estimation step: technology assumption, splitting imports and margins out of purchasers'-price uses, and aggregation to 20–35 sectors.

### 2.4 Annual Survey of Industries (ASI)

- Press release, ASI 2023-24 publications (30 Sep 2025): `https://www.mospi.gov.in/uploads/latestReleases/latest_release_1759229537293_dfab5cc6-…_PressNote_ASI_2023-24_publication_English-F.pdf` (200). Quotes: "released the results of Annual Survey of Industries (ASI) for the reference periods April 2023 to March 2024 … on 27th August, 2025 in the form of press note and seven (07) website tables"; "The results are released at 2/3/4-digit industry-code wise [National Industrial Classification (NIC), 2008]"; "Volume II … classified as per National Product Classification for Manufacturing Sector (NPC-MS), 2011 (Revised)"; "Volume II is disseminated as an e-publication"; "Unit level data of ASI 2023-24 are also available".
- Files:
  - Vol I 2023-24: `uploads/publications_reports/publications_reports1759229853481_…_ASI_Vol_I_2023-24C-2.pdf` (8.9 MB)
  - Summary Results: `…1759229789833_…_ASI_Summary_Results_2023-24C.pdf`
  - Write-up/tables: `…1757588795681_…_Table_0_ASI_Write_Up_2023-24_R.pdf` (fetched; "The final data for ASI 2023-24 are now ready")
- **API:** `GET https://api.mospi.gov.in/api/asi/getAsiFilter?classification_year=2008` returned years 2008-09 … **2023-24** and 57 indicators (Number of Factories, Fixed Capital, Invested Capital, …). NIC classification years available: 2008, 2004, 1998, 1987. Data endpoint: `/api/asi/getASIData`.
- **Unit-level:** microdata.gov.in NADA catalog `https://microdata.gov.in/NADA/index.php/catalog/ASI` lists "Annual Survey of Industries 2023-24 … ID: DDI-IND-NSO-ASI-2023-24 Last modified: Feb 25, 2026". `https://microdata.gov.in/NADA/index.php/catalog/256/get-microdata` says: "To access data for this study, user must be logged in. … register for a free account." Earlier years (2015-16 …) are also listed as "Public use data files".
- **ASI 2024-25:** the schedule and instruction manual were published on 2026-02-09 (publications 2786 and 2787), and the schedule still uses "5-digit level of NIC-2008". The MoSPI latest-release API list (111 items, 2025-09-30 → 2026-09-28) contains **no ASI 2024-25 results release**. A web search found nothing either. Status: not released as of 2026-09-28. The expected date is unverified; by precedent (2023-24 results came out 27 Aug 2025) it is overdue.
- Also: an announcement on 2026-05-29 sought stakeholder feedback on ASI 2025-26.
- SAM use: the manufacturing input structure (materials by NPCMS in Vol II), CE vs OS split within the factory sector, fuel consumption, and state splits. ASI feeds the SUT's IC structure.

### 2.5 Index of Industrial Production (IIP), base 2022-23

- First release: 1 Jun 2026 (April 2026 data). `uploads/latestReleases/latest_release_1786014640160_…_Press_Release_IIP_2022-23f.pdf` (200). Quotes:
  - "revised the base year of the All India Index of Industrial Production (IIP) from 2011-12 to 2022-23"
  - "The revised basket consists of 1,042 products mapped to 463 item groups as compared to 839 items mapped to 407 item groups"
  - "The National Industrial Classification 2025 will be used in the compilation and dissemination of the new series"
  - "the practice of using the Wholesale Price Index (WPI) to deflate item groups … will continue. The Output PPI will be used once it is released"
  - A new sector was added: Water Supply, Sewerage & Waste Management.
  - Linking factors (old/new): Mining 1.1890, Manufacturing 1.3700, Electricity 1.8495, General 1.3834.
  - "detailed tables … for new series from April 2023 onwards are available at e-Sankhyiki".
- Latest: August 2026 Quick Estimate, released 28 Sep 2026 (`…latest_release_1790590696008_…_IIP_Press_Release_August_2026.pdf`, 200): "IIP stands at 123.3 against 114.2 in August 2025"; "released on 28th of every month".
- **API verified:** `GET https://api.mospi.gov.in/api/iip/getIipData?base_year=2022-23&frequency=Monthly&year=2026&month_code=8&type=General&Format=JSON` returned `{"base_year":"2022-23","year":2026,"month":"August",…"index":"123.3","growth_rate":"8.0"}`. The old base also works (2011-12 annual 2024-25 index 152.6). Quirk: the swagger YAML in the GitHub repo still lists only 2011-12, 2004-05 and 1993-94 in the `base_year` enum, but the live API accepts 2022-23.
- NSDP/SDDS page (1 Sep 2026) note: "Base year for IIP has been revised from 2011-12 to 2022-23 from April, 2026."
- SAM use: time-series extrapolation of industrial output volumes (not SAM levels).

### 2.6 Consumer Price Index (CPI), base 2024=100

- First release: 12 Feb 2026 (January 2026 data). `…latest_release_1770891893893_…_Press_Relase_of_CPI_for_Jan26.pdf` (200). Quotes:
  - "FIRST PRESS RELEASE OF CONSUMER PRICE INDEX ON BASE 2024=100"
  - "Base revised from 2012 to 2024 using Household Consumption Expenditure Survey 2023-24"
  - "12 Divisions in place of 6 Groups in accordance to … COICOP 2018"
  - "the number of weighted items has increased from 299 to 358"
  - Linking factors (general index only): Rural 0.5222, Urban 0.5320, Combined 0.5267. Back series: "All India General Indices … January 2013 to December 2024". "the two series can be directly linked only for general index level."
- Latest: August 2026, released 14 Sep 2026: "Retail inflation … August, 2026 is 4.82%", Combined index 108.74.
- **API verified:** `GET https://api.mospi.gov.in/api/cpi/getCPIData?base_year=2024&year=2026&month_code=8&Format=JSON&limit=10` returned Combined CPI (General) 108.74, inflation 4.82. Quirks: `getCPIIndex` returns "No Data Found" for base 2024 (it serves only 2012/2010), and `limit` must be ≥10 ("Invalid limit parameter. Minimum allowed is 10.").
- SAM use: household-consumption deflators by COICOP division for the time series, and CPI weights (HCES 2023-24) as a cross-check on PFCE composition.

### 2.7 WPI / Output PPI / Input PPI / Service PPI, base 2022-23 (Office of the Economic Adviser, DPIIT)

- PIB 2 Jun 2026 (PRID 2267963) and 15 Jun 2026 (PRID 2272872), both fetched with curl (200). Quotes:
  - "Office of Economic Adviser, DPIIT is releasing the revised series of WPI with base year 2022-23 … will replace the existing series of WPI with base year 2011-12"
  - "Output Producer Price Index (OPPI), Trial Input Producer Price Index (IPPI), and Service Producer Price Index (Service PPI) of seven services, viz., Banking, Securities Transaction, Insurance, Management of Pension Funds, Railways, Air (Passenger), and Telecom"
  - "this index [WPI] will be released for five years … and will be discontinued thereafter"
  - "The weights for Output PPI and Input PPI have been derived using the Supply Table and Use Table respectively of Supply & Use Table of National Accounts for the year 2022-23. WPI, Output PPI and Service PPI are being compiled on the basis of Basic Price … Input PPI … Purchaser's Price"
  - Items: 697 → 957. WPI and OPPI back series from April 2023 (37 months). Service PPI back series from Q1 2023-24. Trial IPPI from March 2026. Linking factor, All Commodities: 1.53.
- Latest: August 2026 provisional, released 14 Sep 2026 (`https://eaindustry.nic.in/press_release/press_release_202608.pdf`, 200): "WPI inflation for August 2026 is 9.92 per cent … index … 110.8". Service PPI Q1 2026-27 press release: `press_release/sppi/sppi_press_release_202608.pdf`.
- Download page (200): https://eaindustry.nic.in/download_data_2223.asp. Files:
  - `indx_download_2223/wpi_monthly_index_202609.xlsx` (1,138 rows: Level, Commodity Name, Code, Weight, Apr-23 … Aug-26)
  - `oppi_monthly_index_202609.xlsx` (162 rows, Apr-23 … Aug-26)
  - `trial_ippi_monthly_index_202609.xlsx`
  - `SPPIs_quarterly_index_202608.xlsx`
  - `wpi_yearly_index_202606.xlsx`, `oppi_yearly_index_202606.xlsx`, `SPPIs_yearly_index_202608.xlsx`
  - Metadata `uploaded_files/wpi/WPI_PPIs_Meta_Data_20260716.pdf`; linking factor page `linking_factor2223.asp`
  - Older series: `download_data_1112.asp`
- **Quirk:** filenames carry a yyyymm stamp that changes each month, so the pipeline must scrape the download page for current links.
- **API also serves WPI:** `GET https://api.mospi.gov.in/api/wpi/getWpiRecords?base_year=2022-23&year=2026&month_code=8&Format=JSON&limit=3` returned All-commodities 110.8 (1,137 records).
- Also on OEA: the Index of Eight Core Industries, also rebased to 2022-23 (`uploaded_files/ici/ICI_Press_Note.pdf`), latest press release 2026-09-21. Not verified further.
- NSDP note: "Base year for WPI has been revised from 2011-12 to 2022-23 from May, 2026."
- SAM use: basic-price producer deflators by product (OPPI ≈ SUT supply-table structure), input deflators (IPPI), and service deflators, for constant-price SUT/SAM series and ABM calibration.

### 2.8 Energy Statistics India 2026 (MoSPI NSO)

- Press release 30 Mar 2026 (`…latest_release_1774858925751_…_ES_2026_Press_release.pdf`, 200): "33rd edition"; "During the FY 2024-25 … Total Primary Energy Supply (TPES) … stood at 9,32,816 KToE". Contains the Energy Balance, a Sankey diagram, and "Chapter 9-Energy Accounts" (SEEA-Energy).
- Publication 2817: 24 PDFs (full book 20 MB, chapter PDFs, Annexure IV "Energy Balance Table of India from 2012-13 to 2021-22"). **PDF only.**
- API: `GET https://api.mospi.gov.in/api/energy/getEnergyFilterByIndicatorId?indicator_code=1&use_of_energy_balance_code=1` lists years 2012-13 … **2023-24** only, so the API lags the 2026 book, which covers 2024-25. `getEnergyRecords` returned the 2023-24 energy balance in KToE by end-use sector and sub-sector (e.g. coal final consumption 200,947.38 KToE).
- Report of the Expert Committee on Energy Statistics, released 3 Aug 2026 (publication 2848). It recommends NIC-2025 and SIEC alignment.
- SAM use: a physical satellite (energy use by sector), used to split energy rows (coal, petroleum, electricity, gas) and to cross-check SUT energy products.

### 2.9 Classifications and concordances

- **NIC 2025**: released 18 Nov 2025 (press note: "aligned with ISIC Revision 5"; "new 6-digit coding structure"). The full document `uploads/public_documents/public_documents1763453850334_…_NIC_2025_Final_A4.pdf` (5.1 MB, 200) contains "CONCORDANCE BETWEEN 4-DIGIT INDUSTRY CLASSES OF NIC-2025 AND NIC-2008" (pp. 239–291, PDF table). The IIP new series uses NIC 2025; ASI 2023-24 and 2024-25 and the SUT note use NIC 2008. **A NIC 2008↔2025 bridge is needed** to map IIP to SUT industries.
- **NPCMS 2011 (Revised)**: https://www.mospi.gov.in/sites/default/files/main_menu/national_product_classification/NPCMS_2011_revised.pdf (206 OK). The original NPC-MS 2011: `…/NPC-MS_21sep11.pdf` (206 OK). NPCSS (services) is named in the SUT note, but I did not locate a standalone downloadable NPCSS file (unverified).
- **SUT product ↔ NPCMS and industry ↔ NIC mapping**: the SUT note describes the method (ASI output "computed at seven-digit NPCMS codes, then the major products are selected"; "most disaggregated level (7-digit NPCMS × 5-digit NIC codes) and then reduced using the mapping"). **No machine-readable SUT↔NIC/NPCMS concordance file was found in publication 847.** `NMDS_SUT.xlsx` is metadata, not a concordance (downloaded, 16 KB, not fully parsed). The pipeline may have to transcribe the concordance from the note, or request it from MoSPI NAD. I have not listed this as an access request because I did not confirm that the concordance exists.
- SUT 67 industries → NAS: the 67 industries roll up into the 11 NAS broad activities (note Table 5.1: Agri 4/41, Mining 6/10, Manufacturing 30/75, Utilities 4/4, Construction 1/1, Trade/Hotels 2/3, Transport/Storage/Comm 7/7, Financial 2/2, Real estate/prof 6/7, Public admin 1/1, Other services 4/4, counted as industries/products). The pdftotext layout interleaves rows of this table, so the counts should be re-verified from the PDF.

### 2.10 Other relevant MoSPI items seen (not in this family's core scope)

- NAS 2026 publication (31 Aug 2026), publication 2861, with statements as xlsx under `uploads/publications_reports/NAS-2026-Statements/`. Belongs to the NAS family.
- Sources & Methods for NAS (new series), released 21 Sep 2026 (publication 2865).
- Index of Services Production (ISP), trial, base 2024-25. First release 14 Jul 2026; latest 31 Aug 2026 (June 2026 data); API `/api/isp/getISPRecords`.
- ASUSE 2025 (released 24 Mar 2026 / 6 May 2026). HCES 2023-24. Both feed the SUT but belong to other families.
- NSDP for SDDS (1 Sep 2026) consolidates the base years: "(i) Base year for National Accounts has been revised from 2011-12 to 2022-23. (ii) … IIP … 2022-23 from April, 2026. (iii) Base year for CPI (R/U/C) has been revised from 2012 to 2024. … (v) Base year for WPI has been revised from 2011-12 to 2022-23 from May, 2026".

---

## 3. Licence / terms checked

- **MoSPI Copyright Policy.** Fetched via `POST https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data` (rendered at `/CopyrightPolicy`): "Material featured on this website may be reproduced, following the revised GSDD 2026 (Guidelines for Statistical Data Dessimination). However, the material has to be reproduced accurately and not to be used in a derogatory manner or in a misleading context. Wherever the material is being published or issued to others, the source must be prominently acknowledged." **This is not GODL-India by name.** It is a reproduce-with-attribution permission.
  - I could not locate the "GSDD 2026" text itself. Only the Feb 2019 GSDD and a Jan 2025 draft revision were found by search. It is unverified whether GSDD 2026 carries a formal licence.
  - Terms & Conditions (`/api/terms-and-conditions/...`) cover privacy and the chatbot only.
  - A MoSPI data-access FAQ string in the SPA bundle references NDSAP 2012 (the policy that underlies GODL) for unit-level data access.
- **eSankhyiki** llms.txt: "Data provided through eSankhyiki is published by the Ministry of Statistics and Programme Implementation (MoSPI)" and asks users to "preserve the dataset name, indicator, value, unit, reference period, source". No explicit licence.
- **esankhyiki-mcp client code**: MIT License (GitHub API `license.spdx_id = MIT`). This covers the *code* only, not the data.
- **microdata.gov.in**: login required. It shows a disclaimer only. `/NADA/index.php/terms` returns 404. I did not check the "Policies and Guidelines" page content.
- **OEA (eaindustry.nic.in)**: no explicit licence found. The home page links `disclaimer.asp`, which returns HTTP 404 (checked 2026-09-29).
- **CSEP/Brookings IOTT 2015-16**: no licence checked (third-party draft). Treat as reference only.

---

## 4. Reference-year inputs (from this family)

| Dataset | Latest year available | Base / price basis | Note |
|---|---|---|---|
| MoSPI SUT (new) | 2023-24 (also 2022-23) | Base 2022-23, current prices, Rs crore | Aug-2026 revised vintage = NAS 2026 final estimates; zero discrepancy |
| MoSPI SUT (old) | 2021-22 | Base 2011-12 | Not consistent with the new series |
| Official IOTT | 2007-08 | 2004-05 series | None since; derive from SUT |
| NAS (context) | FE 2023-24; FRE 2024-25; PE 2025-26; Q1 2026-27 | Base 2022-23 | Back series pending (Dec 2026 expected) |
| ASI | 2023-24 (results Aug 2025) | NIC 2008; current prices | 2024-25 not released as of 2026-09-28 |
| IIP | Aug 2026 (monthly) | 2022-23=100, series from Apr 2023; old series linkable | NIC 2025 |
| CPI | Aug 2026 (monthly) | 2024=100 from Jan 2025; general-index back series to Jan 2013 | COICOP 2018 |
| WPI / OPPI | Aug 2026 (monthly) | 2022-23=100 from Apr 2023 | basic prices; OPPI weights from SUT 2022-23 supply table |
| Service PPIs | Q1 2026-27 | 2022-23=100 from Q1 2023-24 | 7 services only |
| Energy balance | 2024-25 (ES 2026 PDF); 2023-24 via API | physical (KToE, PJ) | |

**Implication for the SAM reference year (this family's view):** **2023-24** is the latest year with a published, balanced, discrepancy-free SUT on the current base, final NAS estimates, and ASI results. 2022-23 is the fallback: it is the base year itself, with HCES 2022-23 and 2023-24 nearby. A 2024-25 SUT would come only when 2024-25 reaches Final Estimate. By the pattern of this cycle that is probably the Feb 2027 or Aug 2027 NAS update, but this is an inference and unverified. Other families must confirm that BoP, government accounts and RBI Flow of Funds are available for 2023-24.

---

## 5. Log of fetches (chronological, abbreviated)

| URL | Method | Result |
|---|---|---|
| WebSearch "MOSPI new GDP series base year 2022-23 released February 2026" | search | Found MoSPI press note URL and PIB PRID 2226269 |
| mospi.gov.in …Press_Note_on_New_Series_of_GDP…27022026.pdf | WebFetch | **403** |
| pib.gov.in PRID=2226269 | WebFetch | **403** |
| same MoSPI PDF | curl + UA | **403** (185-byte nginx page) |
| same, + Referer + Accept | curl | **403** |
| https://www.mospi.gov.in/ | curl -I | 200, nginx; SPA shell |
| https://www.mospi.gov.in/robots.txt | curl | returns SPA shell (no robots file) |
| /assets/index-FXIi3u1F.js | curl | 200, 5.79 MB; API routes extracted |
| GET /api/latest-release/get-web-latest-release-list | curl | 403 |
| POST same | curl | 200 JSON |
| POST search "Supply" | curl | id 3573 "Release of Supply and Use Tables of 2022-23and 2023-24", 2026-05-15; publication 847 |
| uploads/latestReleases/…PIB.pdf (SUT PR) | curl + Sec-Fetch headers | **200**, 199,255 bytes |
| POST get-web-chapter-data (847) | curl | 21 files listed |
| SUT 2022-23 / 2023-24 xlsx, note PDF, 2021-22 xlsx, NMDS, 2015-16 xlsx | curl + headers | all 200; saved to scratch |
| POST latest-release list, pages 1–4 | curl | 111 items, 2025-09-30 → 2026-09-28 |
| IIP Aug 2026, IIP first release, CPI Aug/Jan 2026, ASI 2023-24 PR, ES 2026 PR, NAS 2026 PR, Q1 2026-27 GDP, S&M PR, NIC 2025 PR, Energy expert PR, PE 2025-26, new GDP series PDFs | curl + headers | all 200 |
| WebSearch "Producer Price Index base 2022-23 … WPI" | search | PIB PRIDs 2272872, 2267963, 2284374 |
| pib.gov.in PRID 2272872/2267963/2284374/2261377 | curl + headers | 200 |
| https://eaindustry.nic.in/ and /download_data_2223.asp | curl | 200 |
| eaindustry.nic.in/index.asp | curl | 404 |
| eaindustry.nic.in/disclaimer.asp | curl | 404 (IIS "file or directory does not exist") |
| OEA wpi/oppi/SPPI xlsx; press_release_202608.pdf | curl | 200 |
| POST copy-right-policy, disclaimer, terms-and-conditions | curl | 200 JSON (quoted above) |
| POST release-calender (no year) | curl | 400 "Year is required." |
| POST release-calender year=2026 | curl | 10 sparse entries |
| POST documents/get-latest-release-calender | curl | 403 |
| WebSearch "India Input-Output Transactions Table latest official MOSPI 2007-08" | search | IOTT 2007-08; CSEP 2015-16 |
| mospi IOTT 2007-08 Binder1.pdf | curl | 200, 16.2 MB (not saved) |
| csep.org IOTT 2015-16 PDF | curl | 200; read pp. 1–6 |
| WebSearch "Annual Survey of Industries 2024-25 results released" | search | nothing on 2024-25 results |
| drishtiias ASI 2024-25 page | WebFetch | irrelevant (UP factory counts, Apr 2025) |
| microdata.gov.in NADA ASI catalog | curl | 200; 2023-24 latest |
| catalog/256/get-microdata | curl | login required (free) |
| NADA /terms | curl | 404 |
| esankhyiki.mospi.gov.in, robots.txt, ard.json, llms.txt | curl | 200 (ard.json first attempt hung >120 s; retried with -m 30, 200) |
| api.mospi.gov.in/ | curl | 200 Swagger UI shell |
| mcp.mospi.gov.in server-card.json | curl | "Method Not Allowed" |
| WebSearch "api.mospi.gov.in eSankhyiki API" | search | GitHub nso-india/esankhyiki-mcp |
| github README (WebFetch), GitHub API contents/swagger, repo meta, client.py | fetch | MIT; 28 swagger YAMLs; endpoints |
| api.mospi.gov.in /api/iip/getIipData (2022-23 monthly; 2011-12 annual) | curl, no auth | 200 JSON |
| /api/cpi/getCPIIndex base 2024 | curl | "No Data Found" |
| /api/cpi/getCPIData base 2024 limit=3 | curl | error, min limit 10 |
| /api/cpi/getCPIData limit=10 | curl | 200 data |
| /api/wpi/getWpiRecords 2022-23 | curl | 200 |
| /api/asi/getNicClassificationYear, getAsiFilter | curl | 200 |
| /api/energy/getEnergyIndicatorList, getEnergyFilterByIndicatorId, getEnergyRecords | curl | 200 |
| NIC 2025 full PDF | curl + headers | 200, concordance section found |
| WebSearch NPCMS; NPCMS_2011_revised.pdf, NPC-MS_21sep11.pdf | curl range | 206 |
| data.gov.in search / GODL page | curl | 200 (Nuxt SPA, not parsed) |
| api.data.gov.in/lists | curl | **503** |
| WebSearch GSDD 2026; static.pib.gov.in doc202657865101.pdf | curl | 200, but it is the GSVA guideline, not GSDD |
| MoSPI API search "Dissemination" | curl | GSDD 2026 not found; NSDP for SDDS monthly PDFs found |
| NSDP for SDDS 1 Sep 2026 PDF | curl + headers | 200; base-year notes quoted |
| NAS 2026 publication 2861 chapter list | curl | 7 entries (xlsx statements) |
| Energy Statistics 2026 publication 2817 chapter list; Ch 7 and Ch 9 PDFs | curl | 200 |
| ASI publication list; ASI schedule 2024-25 PDF; ASI Table_0 write-up | curl + headers | 200 |

---

## 6. Issues to log in ISSUES.md

1. The SUT press release (NIC 2025) contradicts the SUT methodological note (NIC 2008) on the industry classification.
2. The SUT 2022-23 and 2023-24 files were silently replaced on 2026-08-31, with no version label. The May totals (627.18 lakh crore supply at PP) no longer match the files (628.01 lakh crore).
3. There is no official IOTT after 2007-08. The symmetric IOT must be derived (estimation).
4. The SUT has no valuation matrices, no import-use matrix and no GST sub-split, so these must be estimated.
5. ASI 2024-25 is unreleased as of 2026-09-28, which looks overdue compared with the 27 Aug 2025 release of 2023-24.
6. The NAS back series before 2022-23 is not yet released (expected Dec 2026). The old-base SUTs 2011-12 to 2021-22 are not comparable.
7. The MoSPI licence is a copyright policy referencing an unlocated "GSDD 2026", not GODL by name. The OEA site has no licence page (disclaimer 404).
8. www.mospi.gov.in returns 403 to WebFetch and to plain curl for files. It works only with browser-style Sec-Fetch headers.
9. The eSankhyiki Energy API lags the publication by a year (2023-24 vs 2024-25). The swagger for IIP in the GitHub repo omits base 2022-23, which the live API supports.
10. API `filesize` metadata on MoSPI is unreliable.
