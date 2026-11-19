# Phase 0 recon: Markets and non-bank financial sector (`markets_finsector`)

Working notes. Retrieval date for everything below: **2026-09-29** (unless a different date is stated).
Method: WebSearch and WebFetch, plus `curl` with a normal Chrome User-Agent. Small probe downloads went to the session scratchpad (outside the repo) and were opened with openpyxl, xlrd or pypdf to confirm structure. No bulk data went into the repo.

---

## 0. Headline findings (read this first)

1. **Licensing is the main risk in this family, not data availability.** Most market data is technically easy to download, but several publishers forbid reuse:
   - **NSE** Terms of Use ban automated collection, reproduction and redistribution. They also say the data must not be used "for any gaming, virtual trading or **simulation** activities". That clause hits our ABM directly. **Do not use nseindia.com directly.**
   - **BSE**: the disclaimer (seen only through a search-engine snippet, because the page is JS-rendered and WebFetch got 403) says "reproduction, redistribution or transmission ... is strictly prohibited".
   - **NSDL FPI Monitor** disclaimer: "Reproduction, redistribution and transmission of any information contained on the website are strictly prohibited."
   - **AMFI** Terms of Use allow only "personal and non-commercial use". They forbid publishing, creating derivative works and storing "any significant portion" electronically.
   - **CCIL** Terms of Use ban automated collection and ban commercial use without written consent. Non-scraped, downloadable content for non-commercial use is not explicitly banned.
   - **SEBI** Website Policy: material "may be reproduced free of charge **after taking proper permission by sending a mail to us**". So we need permission by e-mail.
   - **IRDAI** and **EPFO** copyright policies are permissive: reproduction is free, without specific permission, with attribution. **PFRDA** states only "Copyright PFRDA. All rights reserved" and has no reuse clause.
   - **None** of these sources states a GODL-India / NDSAP licence.
   - **Recommendation:** use **SEBI** (Bulletin and Handbook) as the single aggregator for NSE, BSE, NSDL and AMFI figures, and e-mail SEBI for permission. Use IRDAI, EPFO and the DEA/MoF debt report directly. Ask NSDL, AMFI and CCIL for permission only if we need their granular data.
2. **SEBI Bulletin annexure (Excel, 67 sheets) is the backbone for this family.** It is monthly, with FY totals. The latest is the **September 2026 issue, released 23 Sep 2026, with data to Aug 2026**. It covers primary issuance (IPO, FPO, rights, QIP, preferential, public and private-placement debt, REITs/InvITs), public vs private and financial vs non-financial splits, cash-market category turnover shares (FPI, MF, banks, proprietary), FPI flows (sourced from NSDL), MF flows and AUM, AUC and depository statistics. The **SEBI Handbook of Statistics 2025-26 (released 17 Aug 2026)** has **per-table xlsx files, annual and monthly, from 2013-14 to 2025-26**.
3. **Ownership of G-secs (a key Flow of Funds input) is openly available** from the **DEA/MoF Public Debt Management Quarterly Report**. The latest is **Jan–Mar 2026**, a PDF with Last-Modified 13 Jul 2026. It covers dated G-sec and T-bill ownership by 12 holder categories, in % shares, quarterly.
4. **Automated download of `rbidocs.rbi.org.in` files is blocked by a CAPTCHA / bot challenge (F5 "TSPD").** RBI Handbook tables on G-sec ownership (T107), CP (T213), CD (T214), private placements (T61) and FPI (T181) could not be opened by script. Use a manual browser download or the DBIE API. The RBI family agent should confirm the DBIE route.
5. **Base year:** the market data here is nominal ₹ crore at current market values and has no base year. The **GDP base-year change to 2022-23 did happen**. The RBI HBS 2025-26 page (released 31 Jul 2026) lists "Quarterly Estimates of GDP ... New Series (Base : 2022-23)" and IIP "Base : 2022-23 = 100". The search index shows a MOSPI "Press Note on New Series of GDP Estimates with Base Year 2022-23", dated 27-02-2026; the MOSPI PDF itself returned **HTTP 403** to both curl and WebFetch. The same RBI HBS page still lists "Institutional Sector-Wise Gross Capital Formation (At Current Prices) (**Base Year: 2011-12**)", so institutional-sector accounts may still be on the old base. This matters for the reference year. SEBI Bulletin Table 1 now shows "CPI Inflation (BASE 2024=100)". Any ratio to GDP (e.g. Mcap/GDP) in SEBI tables now uses new-series GDP.
6. **Reference-year implication (this family):** every source here has **FY 2024-25** complete, including the slow annual books (IRDAI Handbook 2024-25, CCIL Factbook 2024-25, PFRDA annual A-tables, EPFO AR 2024-25). **FY 2025-26** is complete for SEBI, NSDL, AMFI, DEA ownership (Mar-2026) and PFRDA monthly. It is **not yet** complete for the IRDAI Handbook (FY25-26 edition expected ~Feb 2027 on past cadence), the CCIL Factbook (~Nov 2026) or the EPFO annual accounts (latest is 2022-23).

---

## 1. SEBI Bulletin (monthly)

- Listing: `https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=4&ssid=80&smid=0` (fetched with curl, 36 KB). Rows seen:
  - "Sep 23, 2026 ... SEBI Bulletin - September 2026 [Annexure Tables]"
  - "Aug 27, 2026 ... SEBI Bulletin - August 2026"
  - "Aug 17, 2026 Handbook of Statistics 2025-26"
  - "Jul 27, 2026 ... July 2026"
  - "Jul 03, 2026 ... Jun 2026"
  - "Jun 12, 2026 ... May 2026"
  - "Apr 30, 2026 ... April 2026"
  - "Mar 27, 2026 ... March2026"
  - "Dec 10, 2025 Handbook of Statistics 2024-25"
  - "Oct 29, 2025 ... [October 25 Bulletin Annexure Tables_MSExcel] [..._PDF]"
  - "Sep 24, 2025 ... [MSExcel] [Annexure Tables]"
  - and so on back through 2025.
- Sep 2026 issue page: `https://www.sebi.gov.in/reports-and-statistics/publications/sep-2026/sebi-bulletin-september-2026_104675.html`, showing "Sep 23, 2026".
  - PDF: `https://www.sebi.gov.in/sebi_data/attachdocs/sep-2026/1790161152660.pdf`
  - Excel: `https://www.sebi.gov.in/sebi_data/commondocs/sep-2026/SEBI%20Bulletin%20-%20September%202026_p.xlsx` (6.58 MB, HTTP 200).
- Aug 2026 issue page: `.../aug-2026/sebi-bulletin-august-2026_104049.html`, showing "Aug 27, 2026". Excel: `https://www.sebi.gov.in/sebi_data/commondocs/sep-2026/Bulletins%20Aug-26%20I_p.xlsx` (6.17 MB, 67 sheets: "Data Summary" plus sheets `1` to `66`).
- Sheet titles checked (Aug 2026):
  - T1 "Indian Economy and Capital Markets at a Glance"
  - T3 "Company-Wise Capital Raised through Public and Rights Issues (Equity)"
  - **T6 "Consolidated Resource Mobilisation by Corporates/Other Entities through Primary Markets"**
  - **T7 "Resource Mobilisation by Financial/Non-Financial Institutions through Primary Markets"**: private/public × financial/non-financial, for IPO, FPO, rights, preferential, QIP, bond public issue, private placement and REIT/InvIT
  - T8 OFS through exchanges
  - T9 industry-wise capital raised
  - T12 QIPs
  - T13 preferential allotments
  - **T14 "Private Placement of Corporate Debt listed at BSE and NSE"**
  - T15–T17 cash-segment trends
  - **T19–T21 "Category-wise Share of Turnover in Cash Segment" (Proprietary / FPIs / Mutual Funds / Banks / Others, %)**
  - T30–T36 equity derivatives
  - T37–T48 currency derivatives and IRF
  - T49–T55 commodities
  - **T56 "Trends in Foreign Portfolio Investment" (Gross purchase, gross sales and net in ₹ crore; net in US$ mn; "Source: NSDL")**
  - T57 ODIs vs AUC
  - T58 AUC of custodians
  - T59 FVCI
  - **T60 "Trends in Resource Mobilization by Mutual Funds (₹crore)" (Gross mobilisation, redemption, net inflow and AUM, split Pvt/Public sector)**
  - T61 scheme-wise MF
  - T62 PMS AUM
  - T63–T65 depository statistics
  - T66 AMC Repo Clearing
- Values checked (Aug 2026 issue):
  - T6: FY2025-26 main-board IPOs = 109 issues, ₹177,029 cr (OFS 107,706, fresh 69,323). SME IPOs = 257 issues, ₹11,587 cr.
  - T14: FY2025-26 private placement total = 1,924 issues, ₹899,735.8 cr.
  - T56: FY2025-26 FPI net = −₹152,691.03 cr (−US$16,591.55 mn). Apr-26 −70,884.98; May −29,483.96; Jun 4,668.86; Jul 40,030.73.
  - T60: FY2025-26 MF net inflow ₹736,020.9 cr; AUM ₹7,373,377 cr.
  - T20: NSE cash-segment share FY2025-26: Proprietary 30.9%, FPIs 14.27%, MFs 10.13%, Banks 0.21%, Others 44.49%.
- Sep 2026 issue T56 now runs to Aug-2026 (net +25,491.55 cr). **Layout drift:** the "Cumulative Net Investment" column present in the Aug issue is **absent** in the Sep issue.
- **Quirks:**
  - The xlsx contains live formulas (e.g. `=SUM(C7:C8)`). The cached values are present (openpyxl `data_only=True` works), but the parser must read cached values, not formulas.
  - Month columns are Excel dates (e.g. 2026-04-30 or 2026-04-01; the day-of-month used is inconsistent).
  - FY-to-date rows are flagged with `$` ("$ indicates as on July...").
  - The file name pattern changes every month (`Bulletins Aug-26 I_p.xlsx`, `SEBI Bulletin - September 2026_p.xlsx`, `Monthly SEBI Bulletin 27.07.2026_p.xlsx`, `Annexure Tables-30.04.2026_p.xlsx`), so the listing page must be scraped for the link.
  - Up to Sep 2025, issues had separate "[MSExcel]" and "[Annexure Tables]" links; the format changed from the Oct 2025 issue.
  - The ₹ symbol breaks cp1252 consoles; force UTF-8.
- **Licence:** `https://www.sebi.gov.in/website-policy.html` (WebFetch): "Material featured on this Website may be reproduced free of charge after taking proper permission by sending a mail to us." Also: "...the source must be prominently acknowledged". Also: "does not extend to any material which is identified as being copyright of a third party". There is no GODL/NDSAP mention. Tables sourced from NSE, BSE or NSDL may count as third-party material, so the permission request should ask about these explicitly.

## 2. SEBI Handbook of Statistics (annual)

- 2025-26 edition page: `https://www.sebi.gov.in/reports-and-statistics/publications/aug-2026/handbook-of-statistics-2025-26_103700.html`, showing "Aug 17, 2026". PDF `https://www.sebi.gov.in/sebi_data/attachdocs/aug-2026/1786967914812.pdf` (4 pages).
- The PDF is only a **contents page with 153 hyperlinks** to per-table xlsx files under `https://www.sebi.gov.in/sebi_data/hbs2025-26/annual/...` and `.../monthly/...`. It lists 87 tables across these sections: Primary Market, Secondary Market, Depository, Foreign Investment, Mutual Funds, Alternative Investment Vehicles, Intermediaries, Global markets.
- 2024-25 edition page: `.../dec-2025/handbook-of-statistics-2024-25_98300.html` ("Dec 10, 2025").
- Probe downloads (all HTTP 200, 14–40 KB each):
  - T8 annual "Resource Mobilisation through Private Placement of Corporate Debt": 2013-14 to 2025-26, No. of ISINs and ₹ crore, by BSE-only / NSE-only / both. FY26 total 1,924 issues, ₹899,736.57 cr, which agrees with Bulletin T14.
  - **T11 "Outstanding Corporate Bonds"**: 2012-13 to 2025-26, Rs crore. Financial vs non-financial corporations × listed vs unlisted. FY26 total ₹5,909,146.7 cr (financial 3,563,723; non-financial 2,345,423).
  - T14 "Funds Mobilised by all Instruments": 2013-14 to 2025-26. FY26 total ₹1,392,348 cr (equity public 234,872; QIP+pref 216,072; debt public 11,343; debt PP 899,736; REIT/InvIT 30,326).
  - T58 "Foreign Investment Inflows" (Source: RBI): 2013-14 to 2025-26, ₹ bn and US$ mn. FY26 gross FDI inflow US$94,836 mn; net FDI US$6,947 mn; net portfolio −US$17,792 mn.
  - T60 "FPI Instrument wise" (Source: NSDL): Equity / Debt / VRR / FAR / Hybrid / AIF-MF. FY26: equity −180,831; debt 12,428; VRR −2,071; FAR 15,449; total −152,691 ₹ cr.
  - T63 FPI AUC by category (annual and monthly from Apr-2013).
  - T64 MF category-wise mobilisation, 2013-14 to 2025-26.
  - T69 SIPs (Source: AMFI), 2019-20 to 2025-26, lakh accounts and ₹ crore.
  - **T72 (monthly) "Unit Holding Pattern of Mutual Funds"**: AUM held by Corporates / HNIs / Retail / Banks, Apr-2013 to Mar-2026, ₹ crore and %. Mar-2026: total 7,373,377; corporates 2,703,762; HNIs 2,596,067; retail 1,999,768; banks 73,780. This is key for splitting MF liabilities by holder sector. (Source: AMFI.)
- **Quirks:**
  - Handbook T8 puts "Only BSE" first while Bulletin T14 puts "Only NSE" first (column order differs; values agree).
  - **T11 shows a break in 2024-25:** listed non-financial bonds fall from 1,467,027 (2023-24) to 1,053,958 (2024-25) while the financial total jumps from 2.45 mn to 3.34 mn cr. This looks like a reclassification. Log it in ISSUES.md when ingested.
  - T58 uses a garbled rupee glyph ("` Billion").
  - One file name has "discontinued" (T15 annual ratings).
  - Some annual/monthly tables have no FY column; headers are multi-row.
- Old SEBI "Unit Holding Pattern" HTML page (`https://www.sebi.gov.in/statistics/mutual-fund/unit-holding.html`) is **stale** (shows "as on March 31, 2010"). Use Handbook T72 instead.
- Other SEBI statistics pages fetched (`/statistics/corporate-bonds.html`, `/statistics/mutual-fund/deployment-of-funds-by-all-mutual-funds.html`, `/statistics/fpi-investment/asset-under-custody.html`) returned 200 but have JS-loaded content with no static table. Not pursued; the Bulletin and Handbook cover them.
- SEBI Annual Report 2025-26: press release `.../aug-2026/sebi-releases-its-annual-report-for-fy-2025-26_103417.html`, dated "Aug 06, 2026". PDF `https://www.sebi.gov.in/sebi_data/attachdocs/aug-2026/1786022295675.pdf` (not parsed).

## 3. NSDL FPI Monitor (daily, fortnightly, monthly, FY)

- `https://www.fpi.nsdl.co.in/web/Reports/Latest.aspx` (curl 200). Shows "Daily Trends in FPI Investments on 28-Sep-2026". Rows are Equity (Stock Exchange / Primary market & others), Debt-General Limit, Debt-VRR, Debt-FAR, Hybrid, Mutual Funds (by scheme type) and AIFs. Columns are gross purchases, gross sales and net (Rs crore), plus net in US$ mn and the conversion rate. Example: equity net (3,573.51) cr on 28-Sep-2026 at "Rs.95.8918". Derivative trades and OI are also shown. "Website updated as on: 12 Sep 2026".
- `Yearwise.aspx?RptType=6` (calendar year, monthly) shows CY2026 months. Jan–Aug and Sep "** up to 28 Sep 2026". Apr −70,885; May −29,484; Jun 4,669; Jul 40,031; Aug 25,492 ₹ cr. These **match SEBI Bulletin T56 exactly** (cross-check passed).
- `Yearwise.aspx?RptType=5` (financial year) runs from 1992-93 onwards, with columns Equity / Debt-General / VRR / FAR / Hybrid / MF (5 types) / AIF / Total / Cumulative.
- `FPI_Fortnightly_Selection.aspx` offers fortnightly sector-wise AUC and flows from Jul 2022 to "SEP 15, 2026".
- `ReportsListing.aspx` lists these reports: Latest; DII (Latest/Archive); FPI Investment Details CY/FY; Quarterly; Fortnightly sector-wise; Debt utilisation; AUC; AUC country-wise (top 10); AUC category-wise; ODI/PN; trade-wise equity/debt data.
- **Failures:**
  - `DIIGenerateReport.aspx?Rep=L` returned "**Request Rejected** ... Your support ID is: 18072527208414543657" (WAF).
  - `https://www.fpi.nsdl.co.in/web/Index.aspx` also returned "Request Rejected".
  - Export is via an ASP.NET postback ("Export to Excel" button, `__doPostBack`). There is no static file URL.
  - The page runs JS that disables right-click, F12 and Ctrl+S.
- **Licence:** the disclaimer on the page says: "All proprietary rights in the information received shall remain the property of NSDL. **Reproduction, redistribution and transmission of any information contained on the website are strictly prohibited.**" The footer shows "© Copyright 2014, National Securities Depository Ltd. (NSDL)". The "Terms and Condition" text is boilerplate copied from NSDL's e-voting service and is not data-specific. **Access request:** written permission from NSDL. Otherwise use the SEBI T56/T60 aggregates (subject to SEBI permission).

## 4. NSE / BSE (FII/DII activity, market cap)

- `https://www.nseindia.com/` returned **HTTP 403** to curl (browser UA). `https://www.nseindia.com/reports/fii-dii` returned 200 (304 KB). `https://www.nseindia.com/api/fiidiiTradeReact` returned 200 (216 B). **Not used further, because of the terms below.**
- NSE Terms of Use (`https://www.nseindia.com/static/nse-terms-of-use`; WebFetch timed out; fetched with curl, 200, 327 KB):
  - "User is prohibited to conduct any systematic or automated data collection activities (including scraping, data mining, data extraction and data harvesting)..."
  - "...shall not, in any form and manner, use or make the data or Content available on the Website ... for any gaming, virtual trading or **simulation** activities under any circumstances whatsoever."
  - "...shall not be copied, modified, ... reproduced, ... published, ... distributed in any form, withou[t]..."
- BSE: `https://www.bseindia.com/static/about/termsofuse.aspx` redirects (301) to `/static/about/termsofuse`, which is a JS shell (114 chars of text). WebFetch gave **403**. `https://www.bseindia.com/static/about/disclaimer.htm` is also a JS shell. The search-engine snippet of the BSE disclaimer reads: "Any reproduction, redistribution or transmission, for consideration or otherwise, of any such information contained on the Website is strictly prohibited". **Unverified by direct fetch.**
- **Substitutes:**
  - SEBI Bulletin T15–T21 (exchange turnover, category shares incl. FPI/MF/banks) and T1 (market cap BSE/NSE/all-India, ₹ lakh crore). Aug issue: all-India mcap Jul-2026 = 487.43.
  - SEBI Handbook T23, T28 and T70 ("Trends in Transactions on Stock Exchanges by Mutual Funds").
  - For DII: MF net equity purchases come from SEBI Handbook T70. Insurance flows come from IRDAI (§8).

## 5. AMFI (mutual fund AUM, flows, SIP)

- The site was rebuilt as Next.js. `https://www.amfiindia.com/research-information/amfi-data` (curl 200, 258 KB) embeds a JSON `monthlyData` / `quarterlyData` payload.
  - Monthly reports run from **"April 1999-March 2000" to "April 2026-March 2027"** (28 FY groups).
  - Latest monthly: "August 2026" with `https://portal.amfiindia.com/spages/amaug2026repo.xls` and `.pdf`.
  - Latest quarterly: "Issue I (Apr - June 2026)" with `https://portal.amfiindia.com/spages/aqu-vol26-issueI.xls`.
- Probe: `amaug2026repo.xls` returned HTTP 200, 116,736 bytes, **Last-Modified: Thu, 10 Sep 2026 06:41:20 GMT**. BIFF .xls with sheets `MCR_MonthlyReport` and `NSR`.
  - Columns: schemes, folios, funds mobilised, redemption, net inflow, net AUM, average AUM, segregated portfolios, etc.
  - Rows: category-wise (Overnight, Liquid, ... FoF overseas).
  - "Grand Total" row: net inflow 41,353.6; **net AUM 8,707,887.74 ₹ cr**. A news search reports "₹87,07,887.74 crore", which agrees.
- Quarterly `aqu-vol26-issueI.xls`: HTTP 200, Last-Modified 06 Aug 2026. Sheets `MCR QTRY` and `NSR`.
- **Cross-check:** SEBI T60 Jul-2026 AUM 8,575,626.6 vs AMFI Jul-2026 8,575,656.52 (per news), a ≈₹30 cr gap. The definitions differ slightly; note it when both are used.
- **Licence:** `https://www.amfiindia.com/terms-of-use` (curl):
  - "AMFI grants you a non-exclusive, personal, non-transferable ... right to access, use and display this Site ... for your personal and non-commercial use only"
  - "You may not publicly perform, publicly display, transmit, **publish**, ... or **create derivative works** based on anything available through the Site"
  - "You shall not **store electronically any significant portion** of any part of the Site."
  - **This blocks our use without written permission.** Access request: AMFI permission, or rely on SEBI Handbook/Bulletin tables that carry AMFI data (T60, T64, T69, T72).
- Quirks: .xls (BIFF8) needs `xlrd`. File naming `am{mon}{yyyy}repo.xls` is predictable, but the JSON listing is the reliable index.

## 6. CCIL (G-sec, money market, repo; Factbook)

- `https://www.ccilindia.com/` (curl 200; Liferay). Links found: factbook, rakshitra, india-debt-market-quarterly, business-statistics-daily, money-market-rates-and-volumes, otherservice-data-services, terms of use.
- **Factbook 2024-25:** `https://www.ccilindia.com/documents/43866/111570/Factbook%202025_All%20Pages_BCC_251115.pdf/...?download=true`. HTTP 200, 3.09 MB, 329 pages. The upload timestamp t=1763356051645 ≈ 17 Nov 2025.
  - Tables cover: securities settlement; category-wise buying/selling share (T2, T3); outright by instrument; SDL trading; forex; money market comparison (T33); repo by instrument (T34); category-wise repo/reverse repo shares (T36, T37); TREPS lending/borrowing shares (T39–T41); NDS-Call; IRS; **F-TRAC historical summary (T54)**.
  - These are turnover and settlement volumes, not stocks. Use them for market-activity context, not SAM cells.
  - WebFetch claimed "requires user sign-in to download", but the curl download worked without login.
- Rakshitra (monthly): WebFetch showed "Rakshitra_Monthly is temporarily unavailable." **Failed.**
- Data services (`/otherservice-data-services`) offer "Delayed Data, Value added Data, Aggregation Data" via a Data Request Form. This is a commercial/subscription service; the price is not stated.
- **Licence:** Terms of Use PDF `https://www.ccilindia.com/documents/d/ccil/terms-of-use` (6 pp):
  - 4.1: "shall not ... download/ modify/ ... publish/distribute ... any Content ... for any commercial uses, except with the express written consent of CCIL"
  - 4.8: "shall not conduct any systematic or automated data collection activities ... scrapping, data mining"
  - 5.2: "Any Content that is not available in a downloadable form ... shall not be copied, web-scraped..."
  - A non-commercial public site using downloadable PDFs is arguably allowed, but ask CCIL to be safe.

## 7. Ownership of Central/State Government securities

- **DEA/MoF Public Debt Management Quarterly Report:** listing `https://dea.gov.in/reports-public-debt-management` (curl 200).
  - Latest: "...for the quarter January-March 2026 (1).pdf", `https://dea.gov.in/files/public_debt_management_documents/Quarterly%20Report%20on%20Public%20Debt%20Management%20for%20the%20quarter%20January-March%202026%20%281%29.pdf`. HTTP 200, **Last-Modified 13 Jul 2026**, 31 pages.
  - **Table 4.4 "Ownership Pattern of Government of India Dated Securities (at quarter end) (Per cent of outstanding dated securities)"**, Mar-25 to Mar-26. Mar-2026 shares: Commercial Banks 32.99, Co-op Banks 1.33, Non-Bank PDs 0.51, Insurance 25.59, MFs 1.60, PFs 4.50, Pension Funds 4.62, FIs 0.75, Corporates 1.22, FPIs 2.95, RBI 17.59, Others 6.35.
  - Table 4.5 covers T-bills.
  - Outstanding totals appear nearby ("Total 12183645 11969561", ₹ crore).
  - **Gap:** state government securities (SGS) ownership is not in this table set. Use RBI HBS T107 (annual, 31 March) or DBIE.
- **RBI Handbook of Statistics on the Indian Economy 2025-26** (released "Jul 31, 2026"; listing `https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook+of+Statistics+on+Indian+Economy`, curl 200). Relevant tables:
  - "Table 107 : Ownership Pattern of Central and State Government Securities (Outstanding as on 31st March)"
  - "Table 213 : Commercial Paper"
  - "Table 214 : Issue of Certificates of Deposit by Scheduled Commercial Banks"
  - "Table 61 : Resource Mobilisation in the Private Placement Market"
  - "Table 62 : Net Resources Mobilised by Mutual Funds (Entity Wise)"
  - "Table 68 : Assets Under Management of Mutual Funds"
  - "Table 179/64 : New Capital Issues by Non-Government Public Limited Companies"
  - "Table 181 : Net Investment by FPIs in the Indian Capital Market"
  - **Failure:** all `https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/...XLSX` links returned an HTML bot-challenge page ("TSPD", `window["bobcmn"]`) to curl, and **a CAPTCHA page** ("What code is in the image?") to WebFetch. **Not bypassed.** Table contents are **unverified**. Use a manual browser download or the DBIE API (the RBI family agent should confirm).
- RBI Weekly Statistical Supplement page (`/Scripts/WSSView.aspx`) returned "Error occured. Please try again." **Failed.**
- RBI Bulletin page (`/Scripts/BS_ViewBulletin.aspx?yr=2026&mon=9`) uses ASP.NET postbacks. The table list was not extracted.
- DBIE `https://dbie.rbihub.in/tables` is a JS SPA (17 text lines statically); no table IDs could be extracted.

## 8. IRDAI (insurance)

- Plain GET to `https://irdai.gov.in/` returned 200. A **HEAD request returned 403**, so use GET.
- Handbook listing `https://irdai.gov.in/handbook-of-indian-insurance`: "Handbook on Indian Insurance Statistics **2024-25**, **03-02-2026**" (zip). Earlier editions: 2023-24 (17-02-2025), 2022-23 (13-02-2024), ... back to 2013-14. **Cadence: early February, ~10–11 months after FY end.**
- Zip `https://irdai.gov.in/documents/37343/825690/Handbook+on+Indian+Insurance+Statistics+2024-25.zip/...?download=true`: HTTP 200, 6.57 MB. It contains `Index 2024-25.xlsx`, `Part I.xlsx` (life), `Part II.xlsx` (non-life), `Part III.xlsx` (health), `Part IV.xlsx` (reinsurance), `Part V.xlsx` (distribution) and `Summary.xlsx`.
- Key tables:
  - T2 and T3 total and new business premium (life)
  - T12 linked/non-linked premium
  - **T20 "Assets Under Management (Investments) of Life Insurers"** (As on 31 March, ₹ crore, 2016–2025): Life Fund, Pension & General Annuity, ULIP × Central Govt Sec / State Govt & other approved / Infrastructure / Approved / Other. Grand total Mar-2025 = ₹6,778,660.6 cr.
  - T22 equity capital
  - **T24–T26 policyholders' account, shareholders' account and balance sheet of life insurers**
  - T40 and T41 gross direct premium (non-life)
  - T44 net premium earned and claims
  - **T46 AUM of general/health/reinsurers**
  - T80 and T81 reinsurance
- **Quirk (T20):** growth-rate rows are interleaved under each value row. Signs and parentheses are inconsistent: e.g. +13.8% growth is printed as "-13.8339...", while other years use "(12.69)". **Never parse the growth rows; recompute them.**
- Annual Report listing `https://irdai.gov.in/annual-reports`: "IRDAI Annual Report **2024-25**, 30-12-2025" (PDF); 2023-24 (23-12-2024).
- Monthly business figures:
  - `https://irdai.gov.in/life`: "First year premium of Life Insurers as at 31.08.2026, 09-09-2026" (monthly, ~9–12 days after month end).
  - `https://irdai.gov.in/non-life`: "Gross Direct Premium- Flash figures of Non-life Insurers-For and Up to the Month of August 2026". The July edition is dated 17-08-2026.
- **Licence:** `https://irdai.gov.in/website-policies`, CopyRight policy: "Material featured on this site may be reproduced free of charge in any format or media **without requiring specific permission**. This is subject to the material being reproduced accurately ... the source must be prominently acknowledged." This is permissive. It is not GODL, but compatible with our use.

## 9. PFRDA (NPS / APY)

- Statistical data page `https://www.pfrda.org.in/research-publications/statistics/statistical-data` (curl 200). It has xlsx series A1–A23 (annual), M1–M8 (monthly) and D1 (daily NAV) under `/documents/33652/2024xx/...xlsx?v=...`. Files show `last-modified: Tue, 29 Sep 2026` (regenerated automatically).
  - **A2 "Sector-wise Asset Under Management"**: last business day of FY, Mar-2010 to **Mar-2025** (FY2025-26 row not yet present). Columns APY / All Citizen / CG / Corporate / NPS Lite / Vatsalya / SG.
  - A5 contributions: 2008-09 to 2024-25.
  - **M2 "Sector-wise Asset Under Management"** (monthly): Dec-2014 to **Jun-2026**. Adds MSF Tier-I/II, TTS and Tier-II.
  - **M6 "Asset Class-wise classification of AUM"** (monthly): Apr-2008 to **Aug-2026**. Columns AUM / Corporate bond / Equity / G-Sec / NCA / REIT & InvIT / Short-term. Aug-2026 AUM 1,822,758.5.
  - M4 sector-wise NPS contribution (monthly).
- **Units are not labelled in the files.** The M2 row sum for Jun-2026 (≈1,782,749) matches M6 Jun-2026 AUM 1,782,755.18, so the unit is ₹ crore (inferred; mark it as inferred in provenance).
- M6 disclaimer: "Data as per Pension Funds Portfolio as on last business day of each month... exclusive of AUM values of deregistered Pension Funds."
- Handbook of NPS Statistics: `https://www.pfrda.org.in/documents/33652/203559/HoNPSS+2024-25.pdf` (link seen, not downloaded).
- Annual Reports page: no static document links were found (JS).
- **Licence:** `https://www.pfrda.org.in/web/pfrda/terms-and-conditions` has only accuracy and liability disclaimers. The footer says "© - Copyright PFRDA. All rights reserved." **No explicit licence or reuse permission found.**
- NPS Trust (`https://www.npstrust.org.in/`) returned **HEAD 403**. Not pursued (PFRDA covers aggregates).

## 10. EPFO

- `https://www.epfindia.gov.in/` redirects to `https://www.epfo.gov.in/`. The old `/site_en/Annual_Reports.php` path returns 404 (site restructured).
- Annual reports: `https://www.epfo.gov.in/annual-reports/`, latest **Annual-Report-2024-25.pdf** (`https://pmvbry-cdn.epfindia.gov.in/wp-content/uploads/2025/08/Annual-Report-2024-25.pdf`). HTTP 200, 15.4 MB, 268 pp, Last-Modified 16 Sep 2026. The 2025/08 upload folder holds all files, so it is a migration date, not the release date. The contents list covers: Contributions Received (All Three Schemes); Investment of Funds by EPFO; Investment of Pension Fund; Portfolio Management; Corpus and category-wise break-up of investments (Unexempted Sector); Appendix 5(ix) Investment Pattern.
- Annual accounts: `https://www.epfo.gov.in/annual-accounts/`, latest **Consolidated_Annual_Accounts-2022-23.pdf** (≈3-year lag).
- Payroll (monthly net member additions) comes as PIB releases (search shows the July 2025 release, PRID=2169975). The 2026 releases were not located. Low priority for SAM.
- **Licence:** `https://www.epfo.gov.in/copyright-policy/`: "Material featured on this site may be reproduced free of charge in any format or media without requiring specific permission..." This is permissive.

## 11. Depositories (NSDL, CDSL)

- `https://nsdl.co.in/` returns **301 to itself** (redirect loop to curl), and `https://www.nsdl.co.in/` redirects there too. **Failed.** NSDL depository statistics were not reached.
- CDSL: `https://www.cdslindia.com/publications/periodicstats.aspx` (200) lists monthly PDFs ("August -2026.pdf" ... back to Aug-2024), 27 files. `/Disclaimer.aspx` returned 200 but had no static text. **Licence unverified.**
- Substitute: SEBI Bulletin T63–T65 and Handbook T55–T57 (dematerialisation statistics).

## 12. CP / CD issuance

- The RBI HBS tables T213 (CP) and T214 (CD) exist per the listing, but the downloads are CAPTCHA-blocked (see §7).
- FIMMDA `https://www.fimmda.org/` is a frameset (`Default.aspx`). No data catalogue was found statically, and FIMMDA is mainly a valuation body.
- CCIL F-TRAC (reporting platform for CP/CD/corporate bonds) has only a historical summary in Factbook T54.
- **Status:** CP/CD issuance flows need RBI DBIE/HBS (RBI family) or a manual download. **Unverified here.**

## 13. Other candidate sources noted (not deeply verified)

- **RBI Report on Trend and Progress of Banking in India 2024-25** (NBFC chapter; released ~29 Dec 2025 per newsonair/Business Standard search results). This is the NBFC balance-sheet source and belongs to the RBI family. Not fetched from rbi.org.in.
- SEBI AIF, PMS and REIT/InvIT statistics (Handbook T13, T73, T75). These are minor flows.
- data.gov.in: no SEBI, AMFI, NSDL, CCIL, IRDAI or PFRDA dataset under GODL was confirmed. Search results pointed to third-party aggregators (dataful.in), which should not be used as primary sources.

## 14. Failures log (for ISSUES.md)

| URL | Result |
|---|---|
| https://www.sebi.gov.in/statistics.html | 404 (the correct path is /statistics/statistics.html) |
| https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=4&ssid=32&smid=0 | "No record(s) available" (the handbook listing lives under ssid=80) |
| https://www.nseindia.com/ | 403 |
| NSE terms page | WebFetch timeout 60 s (curl OK) |
| https://www.bseindia.com/static/about/termsofuse | JS shell; WebFetch 403 |
| https://www.fpi.nsdl.co.in/web/Reports/DIIGenerateReport.aspx?Rep=L | "Request Rejected" (WAF) |
| https://www.fpi.nsdl.co.in/web/Index.aspx | "Request Rejected" |
| https://nsdl.co.in/ | 301 redirect loop |
| https://irdai.gov.in/ | HEAD 403 (GET works) |
| https://www.npstrust.org.in/ | HEAD 403 (not retried) |
| https://www.mospi.gov.in/uploads/latestReleases/...Press_Note_on_New_Series_of_GDP_Estimates_with_Base_Year_2022-23_27022026.pdf | 403 (curl and WebFetch) |
| https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/107T_HBIE31072026....XLSX (and T61/T68/T181/T213/T214) | bot challenge / CAPTCHA, not bypassed |
| https://www.rbi.org.in/Scripts/WSSView.aspx | "Error occured. Please try again." |
| https://www.ccilindia.com/rakshitra | "Rakshitra_Monthly is temporarily unavailable" |
| https://www.amfiindia.com/research-information/amfi-data | data embedded in Next.js payload (worked via curl; WebFetch saw no links) |
| https://dbie.rbihub.in/tables | JS SPA, no static content |
