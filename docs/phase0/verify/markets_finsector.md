# Verification: Markets and non-bank financial sector (markets_finsector)

Verifier: independent adversarial agent (did not produce the recon). Date: 2026-09-29.
Method: I re-fetched everything with curl (browser User-Agent) and parsed it with openpyxl, xlrd and pypdf. WebFetch was used where noted. Probe files went to the session scratchpad only; nothing was downloaded into the repo.
Limitation: this session's WebSearch budget was already used up (200/200), so no search-engine checks were possible. Everything below rests on direct fetches.

## Verdict summary

| Source id | Verdict | Main correction / note |
|---|---|---|
| sebi_bulletin_monthly | corrected (minor) | T1 GDP denominator is not labelled "2022-23 base". Aug issue: FY26 PE ₹346.36 lakh cr "released on June 05, 2026". Sep issue: Budget 2026-27 GDP ₹393 lakh cr. Mcap/GDP jumps 140.7 → 125.1 across issues because the denominator changed. The AMFI-SEBI gap also hits Aug-2026 flows |
| sebi_handbook_statistics | confirmed | T11, T14 and T72 values reproduced exactly. The T11 2024-25 break is real |
| nsdl_fpi_monitor | corrected | The fortnightly sector dropdown goes back to **31 Jan 2012** (352 fortnights), not Jul 2022. Everything else reproduced. The DII endpoint is still WAF-blocked (new support ID 18072527208415018601) |
| nse_bse_market_data | confirmed (NSE) / BSE unverifiable | BSE disclaimer/terms return a 14 KB Angular shell with no text. WebFetch gives 403. The main JS bundle has no clause |
| amfi_monthly_quarterly | corrected (minor) | The monthly archive starts **Jul 1999**, not Apr 1999. The quarterly archive starts in 1998-99. I confirmed the gap directly from the AMFI Jul-26 xls: 8,575,656.52 vs SEBI 8,575,626.60 |
| ccil_factbook | confirmed | The factbook selector offers only 2024-2025. Terms clauses 4.1 and 4.8 reproduced |
| dea_public_debt_quarterly | **corrected (licence)** | The DEA Copyright Policy **requires e-mail permission**: "may not be reproduced partially or fully, without due permission". The archive is paginated (7 pages) and goes back well before 2024. No Jan-Mar 2025 report is on page 0 |
| rbi_hbs_market_tables | confirmed (what was claimed) | Listing and TSPD block reproduced. The RBI Disclaimer adds a **deep-linking restriction** that matters for the website |
| irdai_handbook_insurance | corrected (minor) | Editions are listed back to 2007-08, not 2013-14. The Feb release cadence is confirmed across 4 editions |
| irdai_monthly_business_figures | corrected (minor) | Non-life flash data to **Aug 2026 was released 15-09-2026**. Files are xlsx (life ~138 KB, non-life ~28 KB) |
| irdai_annual_report | corrected (minor) | Reports are listed back to 2006-07 |
| pfrda_nps_statistics | confirmed | M2/M6 Last-Modified Mon 28 Sep 2026 18:42/18:50 GMT, A2 Tue 29 Sep 01:12 GMT. HoNPSS 2024-25 Last-Modified 2025-10-14; HoNPSS 2025-26 returns 404 |
| epfo_annual_report_accounts | corrected (minor) | Accounts are listed **1982-83 to 2022-23** (2020-21 missing), annual reports from 2000-01. AR 2024-25 contains FY25 contributions (₹3,35,628.81 cr) |
| cdsl_periodic_stats | confirmed | August 2026 PDF Last-Modified 2026-09-04. The licence is still unverifiable (Disclaimer.aspx is 2,945 bytes with no text) |

## Evidence by source

### SEBI Bulletin
- Listing `HomeAction.do?doListing=yes&sid=4&ssid=80&smid=0` (200, 47.6 KB) shows: Sep 23, 2026 Bulletin Sep 2026; Aug 27, 2026 Aug 2026; Aug 17 Handbook 2025-26; **Aug 06, 2026 Annual Report 2025-26** (missed by the finder); Jul 27 Jul; Jul 03 "Jun 2026"; Jun 12 May; Apr 30 Apr. Before Nov 2025 the listing shows separate "[MSExcel] [Annexure Tables]" links, and Oct 2025 has "_MSExcel"/"_PDF". This matches the format-change claim.
- `SEBI%20Bulletin%20-%20September%202026_p.xlsx`: 200, 6,577,051 B, 67 sheets. `Bulletins%20Aug-26%20I_p.xlsx`: 200, 6,170,934 B, 67 sheets. The Aug file sits in the **sep-2026** folder.
- T56 (Sep issue): "2025-26 | 4464817.84 | 4617508.87 | -152691.03 | -16591.55"; "2026-08-31 | 359857.52 | 334365.97 | 25491.55 | 2671.35"; "$ indicates as on August 31, 2026 / Source: NSDL". The Aug issue has the extra "Cumulative Net Investment (US $ mn.)" column (FY26 286921.65). Column drift confirmed.
- Aug issue T6: "A. IPOs (Main Board) | 109 | 177029". T14: "2025-26 | 468 | 342169 | 1295 | 350677 | 161 | 206889.8 | 1924 | 899735.8". T60: FY26 net 736020.88, AUM 7373376.97. Jul-2026 AUM 8575626.60.
- T1 notes. Aug issue: "3PE of Annual GDP for FY 2025-26 (at Current Prices) estimated at ₹346.36 lakh crore is considered" and "GDP growth rate for 2025-26 is based on the Provisional Estimates ... released on June 05, 2026". Sep issue: "As per Union budget 2026-27, GDP for FY 2026-27 is estimated at ₹393 lakh crore" and "GDP at Current Prices in Q1 of FY 2026-27 is estimated at ₹88.27 lakh crore, released on September 01, 2026". IIP is labelled "(with base year 2022-23)". The GDP base is **not stated** in T1, so the finder's "Table 1 ratios use GDP (now the 2022-23 base)" is unverified.
- Sep T60, Aug-2026 row: gross 1,409,455.07, net 41,383.43, AUM 8,707,887.76. AMFI Aug-2026 xls: gross 1,409,425.16, net 41,353.60, AUM 8,707,887.74. So the ~30 cr gap sits in the flows, not only in the AUM.
- Website policy (200): "Material featured on this Website may be reproduced free of charge after taking proper permission by sending a mail to us ... the permission to reproduce this material shall not extend to any material which is identified as being copyright of a third party. Authorisation to reproduce such material must be obtained from respective copyright holders concerned." **Implication:** SEBI tables marked "Source: NSDL" (T56), "Source: AMFI" (HBS T72) or "Source: BSE and NSE" (T14) may still need NSDL/AMFI/exchange authorisation. Using the SEBI aggregates therefore does not by itself get around those licences.

### SEBI Handbook 2025-26
- Edition page (200) shows "Aug 17, 2026" and links attachdocs/aug-2026/1786967914812.pdf (200, 773,738 B). The PDF has 153 distinct /URI annotations to `/sebi_data/hbs2025-26/{annual,monthly}/*.xlsx`.
- T11 (200, 16,488 B): 2023-24 listed NFC 1,467,026.85 and 2024-25 1,053,957.97. Financial listed 2,331,582 → 3,201,537. Issuers 4,178 → 5,384. 2025-26 total 5,909,146.74. The break is confirmed.
- T14 (200): "2025-26 | 506 | 234872.28 | 1340 | 216072.09 | 43 | 11342.75 | 1924 | 899735.57 | 15 | 30325.66 | 3828 | 1392348.34". Starts 2013-14.
- T72 monthly (200, 39,345 B), Apr-2013 to Mar-2026: "2026-03 | 7373376.98 | 2703761.64 | 2596067.34 | 1999767.90 | 73780.10", "Source: AMFI". The 4 categories sum exactly to the total, so FPI holdings are not shown separately.
- A SEBI MF "Deployment of Funds by all Mutual Funds" page exists (https://www.sebi.gov.in/statistics/mutual-fund/deployment-of-funds-by-all-mutual-funds.html), but it is **stale**: the latest month offered is May 2025 (deployment/2025/debtmay25.html, 200). No current official MF asset-by-instrument table was found in this family.

### NSDL FPI Monitor
- Latest.aspx (200, 59 KB): "28-Sep-2026 Equity Stock Exchange 12676.31 16249.82 (3573.51) (372.66) Rs.95.8918". Disclaimer: "Reproduction, redistribution and transmission of any information contained on the website are strictly prohibited." Footer: "Website updated as on: 12 Sep 2026".
- RptType=6 (CY 2026): Apr -70885, May -29484, Jun 4669, Jul 40031, Aug 25492, Sep** -35686 "up to 28 Sep 2026".
- RptType=5 (FY): starts "1992-93 13"; "2025-26 ... -152691"; "2026-27 ** ... -65864".
- FPI_Fortnightly_Selection.aspx: `ddlfortnighly` has 352 options, from "SEP 15, 2026" back to "January 31, 2012". **Correction:** the finder's "from Jul 2022" is wrong.
- DIIGenerateReport.aspx?Rep=L: "Request Rejected ... support ID is: 18072527208415018601" (reproduced).

### NSE / BSE
- nse-terms-of-use (200, 327,501 B) reproduced two clauses: "prohibited to conduct any systematic or automated data collection activities (including scraping, data mining, data extraction and data harvesting)" and "shall not ... use or make the data or Content ... for any gaming, virtual trading or simulation activities".
- BSE `/static/about/disclaimer.htm` and `/static/about/termsofuse` both return the same 14,287 B Angular shell. `termsofuse.aspx` gives 301 to `/static/about/termsofuse`. WebFetch of disclaimer.htm returns 403. main-ICDVFOXQ.js (869 KB) contains no reproduction clause (lazy chunks). **The BSE clause is unverifiable.**

### AMFI
- amfi-data page (200, 258 KB) has embedded JSON with pdf_url/excel_url for "August 2026" → amaug2026repo.xls. HEAD: 200, Content-Length 116736, Last-Modified Thu, 10 Sep 2026 06:41:20 GMT. amsep2026repo.xls returns 404, as expected.
- xls Grand Total: "1985 | 283519085 | 1409425.16 | 1368071.56 | 41353.60 | 8707887.74 | 8830776.45". The same sheet also has SIP columns (SIP inflows, SIP accounts).
- Earliest monthly entries are amjul1999repo.html through amdec1999repo.html (HTML format). **Correction:** the archive starts Jul 1999. Quarterly labels begin "(January - March 1999)" and "(Apr - June 1999)".
- aqu-vol26-issueI.xls: 200, Last-Modified 06 Aug 2026. issueII returns 404.
- Terms of use (200): "for your personal and non-commercial use only"; "You may not publicly perform, publicly display, transmit, publish ... or create derivative works"; "You shall not store electronically any significant portion". Reproduced.

### CCIL
- /factbook (200): the only date parameter is `_date=2024-2025`. The Factbook PDF gives 200, 3,085,919 B, 329 pp, p.1 "FACTBOOK 2024-25".
- Terms-of-use PDF (200, 589,724 B): 4.1 "...for any commercial uses, except with the express written consent of CCIL"; 4.8 "shall not conduct any systematic or automated data collection activities ... scrapping, data mining". Reproduced.

### DEA Public Debt Management Quarterly Report
- Listing (200): "Quarterly Report ... January - March 2026 ... 13.07.2026 617.21 KB". The PDF gives 200, 632,025 B, Last-Modified Mon, 13 Jul 2026 11:49:29 GMT, 31 pp.
- Table 4.4, Mar-2026 column: Commercial Banks 32.99, Co-op 1.33, Non-bank PDs 0.51, Insurance 25.59, MFs 1.60, PFs 4.50, Pension 4.62, FIs 0.75, Corporates 1.22, FPIs 2.95, RBI 17.59, Others 6.35. Table 4.5 (T-bills) Mar-2026: banks 47.85, MFs 16.75, Others 16.33. All reproduced.
- Note under 4.5: "'Others' comprises of State Governments, DICGC, PSUs, Trusts, Foreign Central Banks, HUF/ Individuals". So "Others" mixes households, general government and RoW (foreign central banks). It cannot be assigned to households without an estimate.
- **Licence correction:** https://dea.gov.in/website-policies (200): "This contents of this website may not be reproduced partially or fully, without due permission from Department of Economic Affairs ... Material featured on this Website may be reproduced free of charge after taking proper permission by sending a mail to us." So `needs_access` should be "e-mail permission from DEA", not "none".
- **Coverage correction:** the listing is paginated (`?page=1` … `?page=7`). Page 1 contains reports for Jan-Mar 2022 through Oct-Dec 2023, plus "Data on Central Government Debt" and Status Papers. There is no Jan-Mar 2025 report on the first page (its data appears in later reports' 5-quarter windows). The Apr-Jun 2026 report was not out as of 2026-09-29.

### RBI Handbook 2025-26 (market tables)
- Listing (200, 423 KB): "Jul 31, 2026 Handbook of Statistics on the Indian Economy, 2025-26". Also "Table 107 : Ownership Pattern of Central and State Government Securities (Outstanding as on 31st March)", "Table 213 : Commercial Paper", "Table 214 : Issue of Certificates of Deposit by Scheduled Commercial Banks", "Table 13 : Institutional Sector-Wise Gross Capital Formation (At Current Prices) (Base Year: 2011-12)", "Table 155/156 ... New Series (Base : 2022-23)". Extra tables relevant here: T63 NBFC public deposits, T65 PSU bonds, T66 FI assistance, **T67 Investments by LIC**, T108/T109 small savings.
- 107T XLSX gives 200 text/html, 45,956 B, containing "TSPD" (5 times) and "bobcmn". This is a bot challenge, and it was not bypassed. (One earlier attempt with a Referer header gave curl code 000.)
- RBI Disclaimer.aspx (200): "caching and links to, and the framing of this Web Site or any of the contents are prohibited ... For hyper-Linking to an internal page of this Web Site (not being the Home Page) the user must make a specific request for, and secure permission from RBI". **This matters for the project's "source links" UI and the pipeline's raw caching.** It belongs to the RBI family but is flagged here. CopyrightPolicy.aspx returns 302.

### IRDAI
- handbook page (200): 2024-25 03-02-2026; 2023-24 17-02-2025; 2022-23 13-02-2024; 2021-22 03-02-2023; back to 2007-08 (01-04-2009). The zip gives 200, 6,573,360 B, 7 xlsx. Part I T20 "GRAND TOTAL ... 6778660.560079327" (2025). The growth-row quirk is confirmed: the "-13.8339" printed for 2017 is actually +13.83% (792,928/696,566).
- life page: "First year premium of Life Insurers as at 31.08.2026 09-09-2026 ... .xlsx 138 KB". non-life: "... Up to the Month of August 2026 15-09-2026 ... .xlsx 28 KB".
- annual-reports: "Annual Report 2024-25 30-12-2025", list back to 2006-07.
- website-policies: "Material featured on this site may be reproduced free of charge in any format or media without requiring specific permission." Reproduced.

### PFRDA
- statistical-data page (200, 675 KB) lists A1–A23, M1–M7, D1 xlsx.
- M6 (Last-Modified Mon 28 Sep 2026 18:50 GMT): "AUG-2026 | 1822758.49 | 387090.07 | 515521.71 | 857490.11 | 30771.14 | 6314.13 | 25571.33", from APR-2008.
- M2: from DEC-2014 to JUN-2026. MAR-2026 row present (SG 816,929.88; CG 428,619.73).
- A2: Mar-2010 to Mar-2025.
- HoNPSS 2024-25.pdf: 200, 2.6 MB, Last-Modified 2025-10-14. HoNPSS+2025-26.pdf returns 404.
- The terms/disclaimer pages show only "© - Copyright PFRDA. All rights reserved." /web/pfrda/copyright-policy returns 404. **No explicit licence found**, confirmed.

### EPFO
- annual-reports (200): links Annual-Report-2024-25.pdf (200, 15,364,363 B, Last-Modified 16 Sep 2026, 268 pp), list back to 2000-01. The PDF has "Contributions Received (All Three Schemes) 76", "Corpus and Category wise breakup of Investments (Unexempted Sector) 83", and "3,35,628.81 Cr" contribution received (FY2024-25 highlights page).
- annual-accounts (200): Consolidated_Annual_Accounts from 1982-83 to 2022-23. 2020-21 was not seen.
- copyright-policy (200): "Material featured on this site may be reproduced free of charge in any format or media without requiring specific permission." Reproduced.

### CDSL / NSDL depository
- periodicstats.aspx (200): 27 PDF links, top "August -2026.pdf". The file gives 200, 107,073 B, Last-Modified Fri, 04 Sep 2026. Content: BO accounts by DP type, "Total 188258094 ... 190997499", custody value.
- nsdl.co.in: every URL returns 301 to https://nsdl.co.in/ in an infinite loop, even with a cookie jar (8 redirects). WebFetch gives ECONNRESET. Reproduced.

### FIMMDA
- fimmda.org is a frameset. Default.aspx (200) has a "Commercial Paper & Certificate of Deposit" page (PageContent.aspx?Iid=MTQy) with "CP Traded Data Archive" and "CD Traded Data Archive". These are **secondary-market trades**, not issuance. The finder's "no data catalogue found" is therefore partly wrong, but it does not fill CP/CD issuance, which remains RBI (HBS T213/T214, DBIE).

### MOSPI base year (key fact)
- The press-note PDF returns 403 to curl and to WebFetch (reproduced). I could not confirm the 27-Feb-2026 date directly. The 2022-23 base is corroborated indirectly by the RBI HBS 2025-26 table titles "New Series (Base : 2022-23)" and by the IIP base 2022-23 cited in SEBI T1 and the DEA report. The DEA report also says "CPI, Base Year 2024" and "WPI ... 2011-12 series".

## Reference-year notes (for the SAM year decision)
- FY2025-26 GDP Provisional Estimates: SEBI Aug Bulletin T1 note says "released on June 05, 2026", ₹346.36 lakh crore at current prices. This is secondary evidence; confirm with the MOSPI family.
- Complete for FY2025-26: SEBI Bulletin/Handbook, NSDL, AMFI, DEA (Mar-2026), PFRDA monthly (Mar-2026 rows in M2/M6), IRDAI monthly premiums.
- Not yet available for FY2025-26: IRDAI Handbook (next expected early Feb 2027, based on 4 consecutive early-Feb releases), IRDAI Annual Report (Dec 2026 expected), CCIL Factbook (~Nov 2026), PFRDA A-series and HoNPSS 2025-26 (404), EPFO AR 2025-26, and SEBI MF deployment (stale since May 2025). RBI HBS 2025-26 contents could not be verified (blocked).
- FY2024-25: covered by all sources, but for EPFO only through the (unaudited) Annual Report 2024-25. The latest audited EPFO accounts are for 2022-23.

## Missed or under-described sources
1. SEBI Annual Report 2025-26 (released Aug 06, 2026; chapter PDFs): https://www.sebi.gov.in/reports-and-statistics/publications/aug-2026/annual-report-2025-26.html
2. SEBI MF deployment of funds (MF assets by instrument; stale to May 2025): https://www.sebi.gov.in/statistics/mutual-fund/deployment-of-funds-by-all-mutual-funds.html
3. RBI HBS T67 "Investments by LIC" and T63/T65/T66 (NBFC deposits, PSU bonds, FI assistance), on the same HBS listing. They are blocked by the same TSPD challenge.
4. DEA Status Paper on Government Debt (latest listed 2023-24) and "Data on Central Government Debt" quarterly, on the same DEA listing (permission needed).
5. FIMMDA CP/CD traded-data archive (secondary trades only).
6. NBFC statistics (RBI sectoral deployment to NBFCs, FSR, Trend & Progress) are in scope for "non-bank financial sector" but were not in this finder's output. They are covered in recon/rbi_core.md, so this is a cross-family dependency, not a gap, provided the RBI family owns them.

## Additional issues for ISSUES.md
- The SEBI third-party carve-out means SEBI tables "Source: NSDL/AMFI/BSE/NSE" may still need the original holder's permission.
- The RBI Disclaimer bans caching and requires permission to deep-link internal pages. This affects the website's per-flow source links and the pipeline's raw-data caching.
- DEA requires permission by e-mail before reproduction.
- The Mcap/GDP denominator in SEBI T1 changed between the Aug and Sep issues (140.73 → 125.08), so do not splice T1 ratios across issues.
- AMFI vs SEBI: a ~30 cr gap in gross mobilisation/net inflow (Aug-26) and in AUM (Jul-26). The two match exactly for Mar-26.
- DEA "Others" holder category mixes households, state governments and foreign central banks.
- The BSE terms, MOSPI press note, data.gov.in catalogue (JS SPA) and CDSL licence remain unverifiable.
