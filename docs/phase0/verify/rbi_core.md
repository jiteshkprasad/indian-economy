# Verification notes: rbi_core (RBI statistics: DBIE, HBS, FSF, banking, NBFC)

Verifier: independent adversarial verifier (did not produce the recon). Date of checks: 2026-09-29.
Method: `curl` with an ordinary browser User-Agent and browser `Accept` headers, then text extraction (python/openpyxl, pdftotext). Probe files were saved to the session scratchpad only; nothing was written to `data/`. Web search ran out of quota part-way through (200/200), so the late checks used `curl` only.

## Access behaviour (re-tested)

| Probe | Result |
|---|---|
| `rbidocs` XLSX, plain curl UA (`curl/8.10.1`) | TLS connection dropped: `schannel: server closed abruptly`, http 000 |
| `rbidocs` XLSX, browser UA only (Accept `*/*`) | 200 `text/html`, 45 KB F5 TSPD challenge (`TSPD` x5, `bobcmn`) |
| `rbidocs` XLSX, browser UA plus browser Accept/Accept-Language | 200, real `application/vnd.openxmlformats...` file. No challenge was solved. |
| `www.rbi.org.in/robots.txt`, `rbidocs.../robots.txt` | 418 "Unauthorised Access" page |
| `data.rbi.org.in/robots.txt` | 404 "Page Not Found" |
| `dbie.rbi.org.in` | **The recon was imprecise here.** DNS resolves (1.6.226.73). HTTPS gives `SEC_E_WRONG_PRINCIPAL` because the server presents the cert for `CN=data.rbi.org.in`. A diagnostic HEAD request that ignored the cert returned `301 Location: https://data.rbi.org.in/DBIE/#/DBIE/dbie.rbi?site=home`. Port 80 did not connect. So old links still redirect server-side, but strict clients fail with a certificate error. |
| `wss.rbi.org.in` | 200 after redirect to `rbi.org.in/scripts/BS_ViewWSS.aspx` |
| `bulletin.rbi.org.in` | 200 after redirect to `rbi.org.in/scripts/BS_ViewBulletin.aspx` |
| `HalfYearlyPublications.aspx?head=Financial Stability Report` | 200 page with the text "Error occured. Please try again." (confirmed) |

## Licence: material correction

- `https://www.rbi.org.in/Scripts/Disclaimer.aspx`: confirmed verbatim. "Except as set forth below, caching and links to, and the framing of this Web Site or any of the contents are prohibited." Linking to the home page requires "notifying RBI in writing". Internal-page links require that the user "secure permission from RBI prior to hyper-linking". The footer reads "© Reserve Bank of India. All Rights Reserved."
- **Missed by the recon:** the RBI Bulletin (September 2026 full issue PDF `0BULLETIN2509202621D08B72415142418C554CACFF40EC41.PDF`, imprint page) says: "© Reserve Bank of India 2026 All rights reserved. **Reproduction is permitted provided an acknowledgement of the source is made.**" This is an explicit reproduction permission. It covers Bulletin content, including the Current Statistics tables 52(a)/(b) and the FSF article, which is a Bulletin article.
- **Missed by the recon:** an archived DBIE disclaimer (Wayback snapshot 2023-06-10 of `dbie.rbi.org.in/DBIE/doc/disclaimer.html`) says: "Reproduction is permitted provided an acknowledgement of the primary source is made." The current `data.rbi.org.in` disclaimer is an SPA route (`/dbie/disclaimer`, seen in main.js) and could not be read statically. Static paths `/DBIE/doc/disclaimer.html` and `/doc/disclaimer.html` return 404. The current DBIE wording is therefore unverified.
- HBS 2025-26 full PDF (`0HSIE31072026...PDF`): no reproduction or copyright statement found in the extracted text. For HBS itself, "no explicit licence found" still holds.
- Neither is GODL-India. Reproduction with attribution looks permitted for Bulletin/DBIE content. The website Disclaimer's deep-link and framing restriction is separate and still needs an owner request to RBI.

## Per-source verdicts

### rbi_dbie: corrected
- The SPA shell has `<title>DBIE</title>` and `main.927a0129ae6de6b4.js` (9,416,256 bytes). The bundle contains `CIMS_Gateway_DBIE` (x2), `security_generateSessionToken` (x3), `dataquery_enhanced`, `dbie_getSDMXExcelData`, `xmlsdmx`, `login_getSapToken` and `BOE/OpenDocument`. **Confirmed.**
- Old host: see the table above. It is a cert-mismatch redirect, not a dead host.
- Licence: see the archived disclaimer above.
- Additional access channel: the HBS imprint says to "Install the mobile application 'RBIDATA'". The privacy policy at `data.rbi.org.in/PrivacyPolicy` covers the "Mobile Application".
- "Guest SAP session rationed" and "about 252 SDMX elements": **unverifiable** (not reproduced).

### rbi_hbs: confirmed
- The listing shows "Jul 31, 2026 Handbook of Statistics on the Indian Economy, 2025-26". The listing has 245 "Table N :" entries (Table 1 to Table 245) and 496 rbidocs file links. The foreword says: "the 28th edition of the Handbook, comprises 245 statistical tables", dated July 31, 2026.
- T1: columns `(Base Year: 2011-12)` 2020-21..2022-23 and `(Base Year: 2022-23)` 2022-23..2025-26. New-base GDP: 2022-23 26,117,627; 2023-24 28,983,909; 2024-25 31,807,309; 2025-26 34,635,638. Notes: "2024-25 are First Revised Estimates", "2025-26 are Provisional Estimates". CFC, primary income, transfers, saving and GCF are "-" for 2025-26.
- T11: new base runs to 2024-25. HH gross financial saving 2023-24 = 3,575,657 (new base). T12 2023-24 = 3,430,640, with the note "as per National Accounts Statistics 2025". Liabilities 1,879,000 vs 1,878,999 (identical); only the asset side differs.
- T13: "(Base Year : 2011-12)", 2018-19..2023-24. T60: 2020-21..2025-26, "2025-26 are provisional".
- Extra quirk: the T42 header says "last reporting Friday in March", but its 2025-26 non-food credit of 21,291,163 equals the SIBC 31-Mar-2026 month-end figure, so the label is stale after the reporting-date change.
- T49 (consolidated SCB balance sheet) runs to 2024-25, source "Annual accounts of banks".

### rbi_fsf_fof: corrected (key_series and licence)
- The FoF listing shows Jan 21, 2026 (2023-24) as the top entry, then Jan 17, 2025 (2022-23), Jun 19, 2024 and Mar 21, 2023. There is no 2024-25 edition. **Confirmed.**
- The article (Id=23912) says "robust economic growth of 12.0 per cent at current prices". The new-base growth from HBS T1 is 28,983,909 / 26,117,627 − 1 = 10.97%, so the old-base inference is well supported, but it is still an inference.
- The workbook `FSF2023-24_21012026.xlsx` (3,224,680 bytes) has 71 sheets. **Confirmed.** Missed structure:
  - `S 9.1`–`S 9.6` give the sectoral composition of claims and uses of RoW, ODCs and OFCs.
  - `S 8.4`–`S 8.7` (financing of ODCs, central bank, OFCs, RoW) are **not in the Index sheet**. They cover only 2011-12..2017-18 and are labelled "(₹ Billion)", but the magnitudes match crore (for example, ODC resources 2011-12 = 9,214,349). This looks like stale legacy sheets with a wrong unit label. Do not ingest them blindly.
  - `S 6.x` is sector × sector (8 sectors × Sources/Uses), with no instrument dimension. `S 7.x` is instrument × sector. There is no 3-D from-whom-to-whom by instrument.
  - Sector detail (Index): S121, S122 (SCBs incl. RRBs, co-op banks, deposit-taking NBFCs/HFCs), S123–S129 (AIFIs, SFCs, SIDCs, non-deposit-taking NBFC/HFC, MFs, insurance, PF), S11 (CPSEs, power companies, port trusts, private), S1311/S1312, S14+S15, S2.
- Licence: as a Bulletin article it falls under the Bulletin reproduction permission.

### rbi_hh_fin_savings: confirmed (licence corrected)
- The Sept 2026 Bulletin page lists "52 (a). Flow of Financial Assets and Liabilities of Households - Instrument-wise". The PDF link `52AT_BULL25092026004CFAF0BB3B4F779B3E0ADBC8826701.PDF` returned 200. The page has 73 PDFs and **0 XLSX** links; guessing a DOCs/XLSX path gave 404.
- 2025-26 NFA 2,168,779.7 (6.3% of GDP). Notes: "Preliminary estimates for 2025-26 and revised estimates for 2024-25, 2023-24 and 2022-23"; "The estimates will undergo revision with the release of National Accounts Statistics 2024-25 by the NSO"; "Figures as per cent of GDP are as per the new base year 2022-23".
- Vintage sensitivity (important for the reference year): 2024-25 NFA was 1,994,202.4 in the Aug-2025 table (50a) and is 2,257,092.5 in the Sept-2026 table, a revision of +13%. The RBI 2023-24 gross assets figure (3,601,838.9) also differs from NSO new-base T11 (3,575,657). The RBI and NSO household series are different estimates.
- The QuarterlyPublications HFS page is stale (top entry Aug 28, 2025; 50AT/50BT XLSX). **Confirmed.** The old-base label is inferred: 2022-23 NFA 1,330,635 is 4.9% of GDP, which matches the old-base GDP of 26,890,473.

### rbi_sectoral_credit_bank: confirmed
- The listing top entry is "Aug 31, 2026 Sectoral Deployment of Bank Credit – July 2026". PR prid=63478 says "41 select scheduled commercial banks … about 95 per cent" and "With effect from December 31, 2025, definition of last reporting fortnight has been changed to the last day of the month under the Banking Laws (Amendment) Act 2025."
- `SIBCSJ26E31082026ENG.xlsx` has Statement 1 and Statement 2. Its reference dates mix fortnight Fridays (26-Jul-2024, 25-Jul-2025) with month-end (31-Mar-2026, 31-Jul-2026).

### rbi_bsr: confirmed (old-host detail corrected)
- SectionID=354: quarterly BSR-1 June 2026 (Aug 31, 2026); annual March 2026 (May 29, 2026). SectionID=382: BSR-2, same dates. SectionID=376: annual BSR-1 May 29, 2026; May 30, 2025; Jun 04, 2024.
- BSR-1 PR: "released the web publication … on its 'Database on Indian Economy' (DBIE) portal"; "The sector's share in total bank credit stood at 58.6 per cent"; "quarterly BSR-1 … since December 2014"; Census 2011 population groups. It also mentions "a new data series presenting district level gender wise information".
- BSR-2 PR: "accounting for 59.3 per cent of total deposits".

### rbi_strbi: confirmed
- The listing shows "Dec 29, 2025 Statistical Tables relating to Banks in India: 2024-25", linking only to `data.rbi.org.in/#/dbie/reports/Publication/Time-Series%20Publications/...`. There are no rbidocs files. The need for a BOE session was not independently reproduced.

### rbi_trend_progress: corrected
- The listing shows "Dec 29, 2025 Report on Trend and Progress of Banking in India 2024-25". **Correction:** NBFC data are **not** PDF-only. The listing includes Appendix Tables VI.1–VI.9 as XLSX: VI.1 NBFC consolidated balance sheet, VI.2 NBFC-UL, VI.3 NBFC-ML, VI.4 NBFC-D, VI.5 credit to sectors by NBFCs, VI.6/VI.7 financial performance of UL/ML, VI.8 FIs, VI.9 standalone PDs. `31APPTVI_1...XLSX` was downloaded: "Consolidated Balance Sheet of NBFCs (₹ crore)", end-March 2023, 2024, 2025 and end-September 2025 (total assets end-March 2025 = 6,109,126). There are 40 XLSX links in total.

### rbi_nbfc_sectoral_credit: corrected
- July 2026 data were released Sep 07, 2026. **Confirmed.** The "about 87 per cent" footnote is confirmed and is benchmarked to RTP 2024-25, outstanding as on September 2025.
- **Correction:** this is a **new release series**. The listing has only 3 entries: Jul 07, 2026 (May 2026, prid=63099), Aug 07, 2026 (June 2026) and Sep 07, 2026 (July 2026). The "2010…2026" year buttons are page chrome shared with the bank-credit page and do not mean archives exist. The statement's earliest column is 31-Jul-2024 (plus 31-Mar-2025, 31-Mar-2026). It cannot give a full-year history for 2023-24.

### rbi_fsr: corrected (format)
- FsReports.aspx shows "Jun 30, 2026 RBI releases the Financial Stability Report, June 2026". **Confirmed.** The report page PublicationReportDetails.aspx?ID=1319 ("Date : 30 Jun 2026") lists only PDFs (chapters, annexes, full `0FSRJUNE2026_...PDF`). No XLSX or chart data were found.

### rbi_annual_report: confirmed
- The listing shows "May 29, 2026 Annual Report 2025-26".
- Ch. XII PDF: "overall surplus of 2,86,588.46 crore as against 2,68,590.07 crore"; "A provision of 1,09,379.64 crore was made and transferred to Contingency Fund". The 5-year row "Surplus transferred to the Central Government" reads 30,307.45 / 87,416.22 / 2,10,873.99 / 2,68,590.07 / 2,86,588.46. On tax: "Under Section 48 of the RBI Act, 1934, the Reserve Bank is not liable to pay income tax or super tax".
- There are 7 appendix XLSX files. Appendix 3 "GROSS SAVINGS (Per cent of GNDI)" covers 2022-23..2024-25, with the note "Data are based on GDP base year of 2022-23".

### rbi_wss_money: confirmed
- WSSViewDetail for 9/25/2026 has the title "Weekly Statistical Supplement (September 25, 2026)" and tables "Reserve Bank of India - Liabilities and Assets", "Money Stock : Components and Sources" and "Reserve Money : Components and Sources". The Data_MSupply top entry is "Sep 25, 2026 Money Supply for the fortnight ended on September 15, 2026". `wss.rbi.org.in` redirects to BS_ViewWSS.aspx.

### rbi_bulletin_current_stats: corrected
- The September 2026 issue page lists tables 1–52(b), including "19 (a) Consumer Price Index (Base: 2024=100)". **Confirmed.**
- **Correction:** "XLSX for some" does not hold for the current issue, whose page has 0 XLSX links (73 PDFs).
- **Correction:** the licence is explicit (the reproduction permission above).
- Relevant articles in the same issue: "Credit-Deposit Divergence: A Balance Sheet Decomposition" and "Private Corporate Investment: Growth in 2025-26 and Outlook for 2026-27".

### rbi_corporate_finances: confirmed
- SectionID=378: Jun 24, 2026 (2025-26). SectionID=366: Mar 30, 2026 (2024-25). SectionID=361: last entry Jul 24, 2020 (2018-19).

### rbi_rcf: confirmed
- The listing top entry is "Jul 29, 2024 Report on Currency and Finance 2023-24", Chapter I "India's Digital Revolution: Opportunities and Challenges". I found no later edition; web search quota was exhausted, so no secondary check was possible.

## Reference-year inputs (re-checked)

| Dataset | Latest year | Base | Verdict |
|---|---|---|---|
| FSF (FWTW) | 2023-24 | 2011-12 (inferred) | confirmed |
| Bulletin 52(a) HH flows | 2025-26 prelim | % GDP on 2022-23 | confirmed; large revisions between vintages |
| HBS T11 sector saving | 2024-25 | 2022-23 | confirmed |
| HBS T1 | 2025-26 PE (GDP/GNI/NDP/NNI/GNDI); 2024-25 FRE for CFC/saving/GCF/RoW | 2022-23 | confirmed |
| HBS T13 institutional GCF | 2023-24 | 2011-12 | confirmed |
| HBS T12 HH fin. assets/liabs | 2023-24 | NAS 2025 (old) | confirmed |
| HBS T60 / AR App. 5 | 2025-26 prov. | n/a | T60 confirmed |
| Annual BSR-1/2 | end-March 2026 | n/a | confirmed |
| STRBI | 2024-25 | n/a | confirmed |
| RBI accounts | 2025-26 | n/a | confirmed |
| RTP NBFC balance sheet | end-March 2025 (+ end-Sept 2025) | n/a | confirmed and extended |
| HBS T49 SCB balance sheet | 2024-25 | n/a | added |
| AR App. 3 gross saving % GNDI | 2024-25 | 2022-23 | added |

Implication: an official RBI FWTW exists only up to 2023-24, and only on the old base. A 2023-24 SAM would pair a new-base real side (T1/T11) with an old-base financial account (FSF, T12, T13). Any year after 2023-24 needs the FWTW block estimated, for example by projecting FSF 2023-24 with 52(a), BSR, SIBC, RTP VI.x and WSS/HBS monetary data.

## Unverifiable or not reproduced
- The BOE guest-session rationing, the "about 252 SDMX elements", and the dbie.rbihub.in affiliation (not probed; as recommended, it is not used).
- The current DBIE disclaimer wording (SPA-only route).
- NAS 2026 release date (MOSPI family).
- The discontinuation of "Composition and Ownership Pattern of Deposits" (not re-checked).
