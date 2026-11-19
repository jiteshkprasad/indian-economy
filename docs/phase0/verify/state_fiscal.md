# Verification: State government finances & Centre-State transfers (`state_fiscal`)

Verifier: independent adversarial check of the finder output (`docs/phase0/recon/state_fiscal.md`).
Date of checks: 2026-09-29. Method: curl with a browser User-Agent (HTTP status, headers, bodies), plus small probe downloads into the session scratchpad (outside the repo) opened with openpyxl / pdftotext. WebSearch was used for discovery until the session search budget ran out. No bot walls, logins or CAPTCHAs were bypassed.

## Headline findings (what the finder got wrong or missed)

1. **Missed: CAG "Publication on State Finances 2024-25" (third edition), released 16 June 2026.** The finder says the latest edition is 2023-24 (31 Dec 2025). That is out of date. Press release: https://cag.gov.in/uploads/PressRelease/PR-PRESS-RELEASE-on-PUBLICATION-on-STATE-FINANCES-2024-25-16-6-25-06a32183f4f8ce5-79805864.pdf (HTTP 200, 452,681 bytes, Last-Modified 17 Jun 2026). It reads: "16th June, 2026 ... released the third edition of the Publication on State Finances 2024-25 ... all 28 States ... ten-year period, from 2015-16 to 2024-25". Key numbers: revenue receipts of the 28 states Rs 40.52 lakh crore in 2024-25; budgetary expenditure Rs 51.20 lakh crore (15.78% of combined GSDP); total liabilities Rs 90.51 lakh crore at 31 Mar 2025. Landing page: https://cag.gov.in/en/page-statefinances24-25 (HTTP 200). It embeds a Tableau Public workbook, `Final1_1-StateFinance2024-25`, which is hosted on a *personal* Tableau profile ("deep.kumar7104", last updated 2026-07-27, 19 views). **I could not find a PDF or annexure file for the 2024-25 edition** (search and page scan found none). This matters: **audited 2024-25 accounts already exist for all 28 states.**
2. **Missed: CAG State Finances Audit Reports (SFAR) for 2024-25**, per state. The CAG home page lists them for Tamil Nadu (Report 2024-25), Himachal Pradesh, Nagaland, Manipur, Chhattisgarh and others (e.g. https://cag.gov.in/uploads/download_audit_report/2026/State-Finances-for-the-year-2024-25,-Government-of-Chhattisgarh-06a561aee44d541.96727754.pdf, found via search). They are useful for SPSE, off-budget borrowing and guarantee detail.
3. **Missed FC16 relevant-data files** (all HTTP 200, open download): `Salary Data.xlsx` (state-wise salaries 2011-12 to 2023-24), `Type wise Subsidies and Transfers.xlsx`, `Financial Data of SPSEs in various State.xlsx` (state PSE counts and turnover, 2022-23, from CAG SFAR 2024; relevant to the public non-financial corporations account), `Sector-wise Profit and Losses of SPSEs...`, `Accounts in Arrear of SPSEs...`, `Trends in expenditure - Centre.xlsx`, `Rural Urban transition data.xlsx`, and `Vol2-Annexures.pdf` (5.77 MB).
4. **Refuted detail:** "CAG MKI ... UP to July 2026" is wrong. The Uttar Pradesh page (`defuat_state_id=90`) lists "August, 2026 (0.62 MB) Download". Across all state pages, August 2026 MKI is posted for 22 states; Arunachal Pradesh and Nagaland stop at July; Manipur stops at May 2026.
5. **New gap:** the CAG state-accounts pages for **Goa** (id 70), Delhi (69) and Puducherry (366) are empty. They show only the tab headers, with no files. Goa's CAG Finance Accounts and MKI are therefore **not on the central CAG page**. They must come from the AG Goa site (not checked) or from RBI/FC16.
6. **New access blocker:** the per-month "Click Here" links beside the MKI PDFs point to SharePoint Excel files (`cagiaad-my.sharepoint.com/:x:/...iswing1_cag_gov_in...`), which redirect to login.microsoftonline.com. This is the same gate as the FA&AA data. Machine-readable MKI is therefore also login-gated (tested with curl only, not in a signed-out browser).
7. **Warning:** `openbudgetsindia.org` (named in the finder's issues) now redirects to unrelated commercial or casino pages. The domain appears lapsed or hijacked. **Do not use or link it.**
8. **FC16 KFI limitation not flagged by the finder:** in the KFI file, *all* debt-flow rows are 0 for every state and year checked, including in 2023-24: A.4 Public Debt Receipts, A.10 Public Account Receipts, B.6 Repayment and B.10 Public Account disbursements. Only stocks (C.*) and deficits are populated. KFI therefore cannot provide gross borrowing or financing flows; RBI Appendix Table 9 or Statements 5-10, or the CAG Finance Accounts, are required for those. In addition, KFI covers **28 states + undivided AP only (no Delhi, J&K or Puducherry)**, and the FC16 **subsidies files cover only 21 states + Union** (no Arunachal, Manipur, Meghalaya, Mizoram, Nagaland, Sikkim or Tripura).

## Source-by-source verdicts

### rbi_state_finances_study: CONFIRMED (minor corrections)
- The listing https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=State%20Finances%20:%20A%20Study%20of%20Budgets returned HTTP 200 (194,927 bytes). Text: "Jan 23, 2026 State Finances: A Study of Budgets of 2025-26". It lists Appendix Tables 1-13, Statements 1-37 (Statement 5 "Financing of GFD – 2023-24 (Accounts)", Statement 7 "2024-25 (Revised Estimates)", Statement 9 "2025-26 (Budget Estimates)") and Appendices I-IV. No 2026-27 edition is listed. WebSearch also found none.
- All 3 cited XLSX URLs appear verbatim in the listing HTML (187 rbidocs links). `02_APP...` is **Appendix Table 2 (Devolution and Transfer of Resources from the Centre)**, not Appendix II. Appendices I-IV use a different prefix (`1APPENDIX...`, `2APPENDIX...`).
- Bot wall reproduced: `14_ST...XLSX` and its PDF twin both returned HTTP 200 `text/html` (44,284 and 43,804 bytes) containing the `bobcmn`/TSPD challenge. Not bypassed.
- Terms reproduced from https://www.rbi.org.in/Scripts/Disclaimer.aspx: "caching and links to, and the framing of this Web Site or any of the contents are prohibited ... For hyper-Linking to an internal page ... the user must make a specific request for, and secure permission from RBI". Linking to the home page requires "notifying RBI in writing". No reproduction or licence clause was found on that page.
- Units (crore vs lakh) remain unverified because the files could not be opened.

### fc16_relevant_data: CONFIRMED (with corrections and additions)
- HEAD requests on all 8 URLs returned 200. KFI: 530,793 bytes, Last-Modified 3 Feb 2026. Transfers: 96,812 bytes, 3 Feb. Subsidies: 39,108 bytes, 5 Feb. State Finance Accounts: 53,376,635 bytes, 3 Feb. Horizontal: 24,005 bytes, 3 Feb. Vol1: 7.43 MB, 1 Feb. EM: 288,851 bytes, 1 Feb.
- KFI 2023-24 (column header `2024`): Revenue Receipts 3,793,278.12; SGST 800,112.02; share in Union taxes 1,129,396.72; FD -864,160.38; C.1 public debt 6,787,363.18. **All reproduced.** The GSDP row C.10 = 30,122,955.9 = the old-base 2023-24 GDP, which confirms both the year label and the old base. There are about 95 coded items (not "~100"). The Notes sheet confirms: "Off-budget borrowing data is not complete", "GST compensation loan has been considered as central grants", "For All_States, India GDP figure is used".
- Transfers master (all-India only, not state-wise): the last rows are 2023-24 (1,868,754), 2024-25RE (2,060,052) and 2025-26BE (2,308,451). **Reproduced.** Per the sheet note, figures for 2023-24 onward come from the **Union Budget (Statement 18)**, not state accounts: "RBI data on actuals is available only till 2022-23. The data for 2023-24 is taken from Statement 18 of Union Budget".
- Subsidies: State × 13 sectors, 2018-19 to 2025-26 BE. **Only 21 states + Union.**
- Horizontal Devolution.xlsx: population, area, comparable GSDP 2018-19..2023-24, and forest cover for 2015 and 2023.
- Licence: https://fincomindia.nic.in/copyright_policy returned 200 (24,835 bytes of HTML) but has **no policy text**. The footer reads "© Copyright 2023-2025 Content Owned by Sixteenth Finance Commission, Government of India All Rights Reserved." **No explicit licence found.**

### fc16_ulb_cityfinance_dump: CONFIRMED (evidence mislabelled)
- HEAD 200, 10,380,666 bytes, Last-Modified 19 Feb 2026. Sheet `Financial & Docs_All_ULBs clean`: 37,867 rows including the header, 49 columns. Year counts reproduced (2015-16: 3,725 ... 2023-24: 4,620). There is also a `Demographic_Data_All_ULBs` sheet (4,860 rows).
- **Correction:** for Khategaon 2023-24, `Property Tax` is blank. The value 56,082,096 sits in the **`Tax Revenue`** column. The same ULB shows 4,876,701 in 2022-23 (an 11× jump), a data-quality flag. Rupee units are supported by plausibility (a town of about 33,600 people with Rs 11.9 crore of total revenue), but no unit label exists, so they remain unverified.

### cag_state_finance_accounts: CONFIRMED (corrections)
- https://cag.gov.in/en/state-accounts-report and the `?defuat_state_id=79` / `=90` pages returned 200. Maharashtra: "2024 - 25 Finance Accounts-I (8.89 MB) ... Finance Accounts-II (37.22 MB)". **Reproduced.**
- Scan of all 31 state ids: **2024-25 Finance Accounts are posted for all 27 states that have pages, i.e. every state except Goa.** The Goa, Delhi and Puducherry pages are empty. One upload date is visible in a filename: Arunachal Vol-I "19-12-2025", so some uploads date from Dec 2025 (not only Jan-Mar 2026).
- FA&AA SharePoint: `.../iswing1_cag_gov_in/...` → 302 to `onedrive.aspx?id=/personal/iswing1_cag_gov_in/Documents/FA&AA DATA/Maharashtra/2024-25` → login.microsoftonline.com. **Reproduced.** The page also carries a disclaimer: "The data contained in the PDF version ... shall be treated as final in case of any discrepancy".
- Copyright: https://cag.gov.in/en/page-copyright returned 200: "Material featured on CAG website may be reproduced free of charge ... reproduced accurately ... the source must be prominently acknowledged." **Reproduced.** The hyperlinking-policy URL `/en/page-hyperlinking-policy` returns 404.

### cag_monthly_key_indicators: CORRECTED
- The Maharashtra August 2026 PDF returned 200 (`application/pdf`, 411,704 bytes). It reads "ACCOUNTS AT A GLANCE (At the end of August 2026) (UNAUDITED PROVISIONAL FIGURES)" and "(i) GST 187094.70" (BE 2026-27). **Reproduced.**
- **The claim "UP to July 2026" is wrong: UP has August 2026.** Coverage varies: Manipur to May 2026; Arunachal and Nagaland to July; Goa absent.
- Rows also include Land Revenue, Sales Tax, State Excise, State's Share of Union Taxes, and Grants-in-aid.
- The per-month Excel ("Click Here") versions are on SharePoint and login-gated.
- The annual "Accounts at a Glance" is a separate annual publication on the same page. The finder's name conflates it with MKI.

### cag_state_finances_publication: CORRECTED (superseded)
- The 2023-24 press release (200, 784,974 bytes) reproduced: "31st December, 2025 ... second edition ... all 28 States ... 2014-15 to 2023-24". The PDF HEAD returned 200, 51,074,088 bytes, Last-Modified 31 Dec 2025. **Reproduced.**
- **But the latest edition is 2024-25 (released 16 Jun 2026, covering 2015-16 to 2024-25).** See Headline 1. The dashboard for 2024-25 is on Tableau Public. Export or download capability was not tested. For the 2023-24 edition, https://cag.gov.in/en/page-sf-dashboard renders only via JavaScript (empty static HTML).

### union_budget_transfers_to_states: CONFIRMED
- vol1.pdf: HEAD 200, 13,525,814 bytes, Last-Modified 31 Jan 2026. Statement 18 reproduced: "Grand Total 938628.46 1137320.41 943172.86 1094513.94". Footnote: "# Compensation to States/UTs for revenue losses on roll out of GST has been phased out w.e.f. 2026-2027."
- Further footnote: "* [CSS] includes releases made to States both through State treasuries and other implementing agencies". CSS transfers here therefore ≠ state-treasury receipts (a SAM reconciliation issue).
- Statement 18 mixes grants with **loans** (EAP loans 34,409.84; SASCI 1,49,483.73 in 2024-25), which must be separated in the SAM.
- sbe42.pdf: 200, 331,327 bytes.
- **Previously "unverified" 2026-27 BE devolution Rs 15,26,255 crore is now VERIFIED** in Budget at a Glance (https://www.indiabudget.gov.in/doc/Budget_at_Glance/budget_at_a_glance.pdf, 200): "Devolution of States share in taxes ... 1286885 [2024-25 A] ... 1392971 [2025-26 RE] 1526255 [2026-27 BE]"; total transfers 2026-27 BE 26,20,769.
- Licence: https://www.indiabudget.gov.in/termsofuse.php has **no licence or reproduction clause**. No explicit licence found.

### pib_tax_devolution_releases: CONFIRMED
- curl without cookies returns 302. With a cookie jar it returns 200 (`...PRID=2292912&reg=48&lang=2`): "Posted On: 01 AUG 2026 1:40PM ... additional instalment of tax devolution ... Rs. 1,09,019 crore", table "UTTAR PRADESH 19208", "BIHAR 10845". **Reproduced.** Cross-check: 19,208/1,09,019 = 17.619% and 10,845/1,09,019 = 9.948%, exactly the FC16 Table 8.9 shares.
- PIB copyright page: `/CopyrightPolicy.aspx` redirects to an error page. Licence not established.

### prs_state_budget_analyses: CONFIRMED (date unverified)
- https://prsindia.org/budgets/states returned 200. Footer: "PRS Legislative Research is licensed under a Creative Commons Attribution 4.0 International License". It has 30 unique `*-budget-analysis-2026-27` links. `/terms-of-use` returns 404. **Reproduced.**
- SOSF 2025-26 page: 200. PDF: 200, 2,000,814 bytes, **Last-Modified 14 Nov 2025**. "Oct 2025" is unverified; no SOSF 2026 exists yet (the `state-of-state-finances-2026` URL returns 404).
- UP analysis: "GSDP ... 2026-27 ... Rs 39.8 lakh crore, amounting to growth of 28% over the revised estimate for 2025-26". **Reproduced.**

### gst_monthly_state_revenue: CONFIRMED (date corrected)
- 200, `application/pdf`, 1,073,357 bytes. Contains "Table 1: SGST & SGST portion of IGST settled to States/UTs in August, 2026", "Table-2 ... till August, 2026", Table 3 and Table 4 ("Period : Apr-26 to Aug-26").
- Server **Last-Modified is 25 Sep 2026**, not "early September". The actual publication date is unverified.
- The September URL pattern returns 404 (not yet out). Licence not checked (deferred to the tax family).

### rbi_municipal_finances: CONFIRMED
- Listing 200: "Nov 13, 2024 Report on Municipal Finances", Statements 1-8 and Appendices I-IV (municipal corporations, state-wise). Data years unverified (files are bot-walled).

### rbi_pri_finances: CONFIRMED
- Listing 200: "Jan 24, 2024 Finances of Panchayati Raj Institutions 2020-21 to 2022-23", Appendix I (Revenue Receipts) and II (Revenue Expenditure) of Village Panchayats.

### rbi_handbook_indian_states: CONFIRMED (minor correction)
- Listing 200: "Dec 11, 2025 Handbook of Statistics on Indian States 2024-25". The fiscal block runs from **Table 164 to Table 178** (177 Outstanding Guarantees, 178 Market Borrowings), not 164-176.

### egramswaraj_panchayat_accounts: CORRECTED (scope narrower than implied)
- Home page 200. `RecExpReportNew.do?finYear=2023-2024&scheme_uid=0` returns 200 (162 KB, an Angular template). The title is "Receipt And Expenditure Analysis Report ... XV Finance Commission-XVFC". Columns: Basic (untied) and Tied grants by Zilla, Block and Village Panchayat; FY 2020-21 to 2026-27; a "Download to Spreadsheet" option; data loaded by JavaScript.
- **It covers only the flows of Union FC grants to PRIs, not full panchayat finances.** No licence statement was checked.

## Key facts: verdict summary
- RBI SF 2025-26 edition, 23 Jan 2026, latest: **confirmed**.
- rbidocs bot challenge: **confirmed** (TSPD HTML on curl; the CAPTCHA via WebFetch was not re-tested).
- RBI ToU prohibits deep links: **confirmed**.
- FC16 submitted 17 Nov 2025, 41% share, accepted: **confirmed** (EM: "The Government has accepted the above recommendations").
- No RD/sector/state-specific grants; LB grants Rs 7,91,493 crore: **confirmed** (EM and Vol1 para 10.84). The Government "takes note" of the assessment.
- Tabled 1 Feb 2026 with the stated weights: **confirmed** (PRS summary; Vol1 Table 8.8: Population 17.5, Demographic Performance 10, Area 10, Forest 10, Per Capita GSDP Distance 42.5, Contribution to GDP 10). Tax effort is absent from Table 8.8. UP share 17.619% (Table 8.9) is now **verified**.
- KFI 2023-24 numbers: **confirmed**.
- CAG SF 2023-24 on 31 Dec 2025: **confirmed, but superseded** by the 2024-25 edition (16 Jun 2026).
- 2024-25 FA "many states"; MKI to Aug 2026: **corrected** (all states except Goa; MKI end month varies).
- FA&AA SharePoint login: **confirmed**.
- Statement 18 figures and GST compensation phase-out: **confirmed**.
- MoSPI 2022-23 base, 27 Feb 2026, back series by Dec 2026, PFMS: **confirmed** (PIB FAQ NoteId 157582).
- States moving GSDP to the new base; guidelines 7 May 2026: **unverifiable at primary level**. Devdiscourse (dated 07-05-2026) says "all States and Union Territories will now be required to adopt the new base year". No MoSPI primary source was fetched (mospi.gov.in returned 403 per the finder, and I had no search budget left to find one).
- PIB UP 19,208: **confirmed**.
- PRS CC BY 4.0: **confirmed**.
- CAG copyright: **confirmed**.
- RBI municipal 13 Nov 2024; PRI 24 Jan 2024: **confirmed**.

## Reference-year implications (the most important correction)
- **2023-24** is fully covered by audited, all-state sources: RBI SF 2025-26 (Accounts, incl. UTs with legislature), FC16 KFI, CAG SF 2023-24 and CAG FAs. The RBI and FC16 ratios use old-base GSDP.
- **2024-25** audited state accounts **already exist**: CAG SF 2024-25 publication (28 states, June 2026) and per-state FA 2024-25 (27 of 28 states on the CAG page; Goa missing). The centre side is covered by Union Budget 2026-27 (2024-25 Actuals). RBI's next SF edition (expected Dec 2026 to Jan 2027, inferred from the Dec/Jan pattern) should add 2024-25 Accounts in a consistent, machine-readable (but bot-walled) format. **The state-government block does not constrain the reference year to 2023-24; 2024-25 is feasible now** (via CAG PDFs and dashboard), and conveniently so after the next RBI edition.
- Local bodies are the binding constraint: ULB (FC16 cityfinance) to 2023-24; RBI PRI only to 2022-23; eGramSwaraj covers only FC grant flows.

## Access requests (additions to the finder's list)
- CAG: SharePoint access for FA&AA data **and** the monthly MKI Excel files. Ask CAG for the PDF or annexure tables of the **State Finances 2024-25** publication, or confirm whether the Tableau Public workbook (personal profile) is an official channel and whether its data may be downloaded and reused.
- Goa: locate Finance Accounts and MKI on the AG (A&E) Goa website (not checked).
- The RBI and FC items listed by the finder stand.

## Failures and quirks encountered
- rbidocs: TSPD challenge (not bypassed).
- PIB: 302 without cookies, 200 with a cookie jar.
- CAG `/en/page-hyperlinking-policy`: 404.
- PIB `/CopyrightPolicy.aspx`: redirects to an error page.
- openbudgetsindia.org: domain now serves unrelated sites.
- The CAG SF dashboard pages are rendered by JavaScript or Tableau.
- The WebSearch budget (200) was exhausted mid-task, so later discovery used curl only.
