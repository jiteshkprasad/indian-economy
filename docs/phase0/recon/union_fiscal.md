# Phase 0 recon — Union government finances & taxes (`union_fiscal`)

Agent working notes. Retrieval date for everything below: **2026-09-29** (machine clock; Windows 11, Git Bash curl + Python, WebFetch/WebSearch).
Probe downloads went to the session scratchpad (outside the repo), nothing was saved into `data/`.

Conventions: **VERIFIED** = I fetched the URL and saw the quoted content. **SECONDARY** = only seen in press/aggregator articles. **UNVERIFIED** = could not confirm; reason given.

---

## 0. Headline findings (read this first)

1. **Latest Union Budget = 2026-27**, presented 1 Feb 2026. VERIFIED: the Budget at a Glance xlsx columns read `2024-2025 Actuals | 2025-2026 BE | 2025-2026 RE | 2026-2027 BE`. `doc/Budget_Speech.pdf` Last-Modified `Sun, 01 Feb 2026 00:41:42 GMT`.
2. **Budget %-of-GDP ratios use the OLD 2011-12 base.** BAG note (i): "The GDP for FY 2026-27 is estimated at 393,00,393 crore, which is 10% over the Advance Estimates for FY 2025-26 of 357,13,886 crore released by NSO." MoSPI released the **new 2022-23-base GDP series on 27 Feb 2026**, after the Budget. Its PE press note (5 Jun 2026) puts nominal GDP 2025-26 at **₹346.36 lakh crore** and 2024-25 at **₹318.07 lakh crore**. The Budget's 357.14 lakh crore was on the old base. **All fiscal ratios must be recomputed on the new-base GDP.** Do not copy the Budget's ratios.
3. **Union accounts vintages available now:**
   - **2024-25:** audited *Finance Accounts* on CGA (PDF Last-Modified 22 Dec 2025). Also the "Actuals" column of Budget 2026-27.
   - **2025-26:** *Provisional Actuals* (unaudited). CGA monthly accounts for March 2025-26, published end-May 2026 per the CGA release calendar.
   - **2026-27:** monthly through **July 2026**. August 2026 is due 30 Sep 2026. On 2026-09-29 the site returned "No Details Available For This Month".
4. **The Economic & Functional Classification (EFC) of the Central Government Budget is stale.** The DEA listing (page last updated 28.09.2026) has **2017-18 (published 07.11.2019)** as its newest edition. I found nothing newer. This is the key SAM-relevant gap: for 2024-25 the economic classification must be rebuilt from other sources:
   - Object heads: CGA *Accounts at a Glance* 2024-25, Appendix 12 "Object Head Wise Expenditure".
   - Major heads (function): Annual Financial Statement.
   - Expenditure Budget statements: subsidies, transfers, CSS.
   - MoSPI NAS general-government accounts (another agent's family).
5. **GST data moved off PIB.** PIB stopped the monthly GST press release after the May-2024 data (SECONDARY: BusinessToday, 3 Jul 2024). Monthly data now comes from GSTN:
   - A PDF revenue report on `tutorial.gst.gov.in/downloads/news/...`. The August 2026 report is dated about 1-2 Sep 2026.
   - Excel files on `gst.gov.in/download/gststatistics`: all-India monthly figures, state-wise collections and refunds, and IGST settlement to states.
   - The GSTN Excel files **exclude compensation cess**.
6. **GST Compensation Cess ended 1 Feb 2026.** It was replaced by additional central excise on tobacco and a "Health Security se National Security Cess" on pan masala. (newsonair.gov.in, 1 Jan 2026.) Budget figures for the cess:
   - Actuals 2024-25: ₹1,50,570 cr
   - RE 2025-26: ₹88,000 cr
   - BE 2026-27: ".." (nil)
7. **16th Finance Commission** (award 2026-27 to 2030-31) keeps vertical devolution at **41%** of the divisible pool. Its report is on indiabudget.gov.in (`doc/16fc.pdf`, `doc/16fcvol1.pdf`, `doc/16fcvol2.pdf`).
8. **Licence problem.** indiabudget.gov.in's copyright policy reads: "contents of this website may not be reproduced partially or fully, without due permission from Ministry of Finance". DEA and GST Council have similar wording ("may be reproduced free of charge after taking proper permission by sending a mail"). The gst.gov.in Terms list "web scraping" as an unauthorised activity. **None of these sites states GODL-India.** The owner should seek written permission from MoF (Budget Division/DEA, CGA, GSTN), or we source GODL copies via data.gov.in where they exist.
9. **openbudgetsindia.org is compromised.** On 2026-09-29 the CBGA open-data domain redirected to `indiabullsmf.com`, and its 404 page is titled "Casino Sites India". **Do not use it.** Log it as a dead source.
10. **incometaxindia.gov.in returns HTTP 403** to curl (all paths, including robots.txt) and to WebFetch. The CBDT Time Series and ITR statistics could not be fetched directly. They are known only via search snippets and secondary articles.

---

## 1. URLs fetched, and what they showed

### 1.1 indiabudget.gov.in (Union Budget 2026-27)
- `https://www.indiabudget.gov.in/`: 200. The home page links the full 2026-27 document set. Each table has a PDF, and most have an xlsx beside it:
  - `doc/Budget_at_Glance/budget_at_a_glance.{pdf,xlsx}` and `bag1..7`.
  - `doc/AFS/afs1..9 + allafs.{pdf,xlsx}`.
  - `doc/rec/` Receipt Budget: `tr.xlsx`, `ntr.xlsx`, `ctr.xlsx`, `allrec.pdf`, annexes 1-14.
  - `doc/eb/` Expenditure Budget: `stat1..27a`, `sbe1..102`, `dg1..102`, `railstat1..7`, `allsbe`, `alldg`, `vol1.pdf`.
  - `doc/frbm1.pdf`, `frbm2.pdf`, `doc/memo.pdf`, `doc/Finance_Bill.pdf`.
  - `doc/16fc*.pdf`, `doc/Key_to_Budget_Document_2026.pdf`, `doc/OutcomeBudgetE2026_2027.pdf`.
- **Quirk: HEAD returns 404 for .xlsx and .pdf files** (IIS behaviour) while GET returns 200. For example:
  - HEAD `doc/Budget_at_Glance/budget_at_a_glance.xlsx` → 404.
  - GET on the same file → 200, 28,188 bytes, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.
  - Pipelines must use GET (or a ranged GET) to check freshness.
- `doc/Budget_at_Glance/budget_at_a_glance.xlsx`: sheets `BAAG`, `Deficit Statistics`, `Receipts`, `Expenditure of GOI`, `Transfer of Resources`. Units "(In ₹ crores)", bilingual row labels. Values seen:
  - Revenue Receipts 2024-25 A = 3,036,613. BE 2026-27 = 3,533,150.
  - Tax Revenue (Net to Centre) A 2024-25 = 2,500,039.
  - Interest Payments: A 2024-25 = 1,115,575. RE 2025-26 = 1,274,338. BE 2026-27 = 1,403,972.
  - Fiscal Deficit: A 2024-25 = 1,574,431 (4.8%). RE 2025-26 = 1,558,492 (4.4%). BE 2026-27 = 1,695,768 (4.3%).
  - Sources of FD financing: Market Borrowings (G-sec) 1,074,512 / 1,040,439 / 1,173,210; Securities against Small Savings 429,502 / 372,192 / 386,772; External debt 47,271 / 20,462 / 15,385.
  - Gross Tax Revenue 2024-25 A = 3,796,382. It splits as Corporation Tax 986,767, Taxes on Income 1,235,171, Customs 233,201, Union Excise 300,253, GST 1,027,041 (CGST 908,954, IGST −32,483, Comp. Cess 150,570).
  - Less States' share 1,286,885.
  - Transfer of Resources:
    - Devolution 1,286,885 (A 2024-25), 1,392,971 (RE 25-26), 1,526,255 (BE 26-27).
    - FC grants 120,858 / 152,953 / 129,397.
    - Total transfers other than devolution 555,100 / 498,159 / 609,008. CSS component: 382,336 / 399,854 / 520,333.
- `doc/Budget_at_Glance/budget_at_a_glance.pdf` (pdftotext): GDP footnote as quoted in §0.2.
- `doc/rec/tr.xlsx` (Receipt Budget, Tax Revenue): one sheet, `ReceiptReport123`. Detail is by major head (0020 Corporation Tax, 0021 Taxes on Income) with sub-items (collections, surcharge, Health & Education Cess, penalties, interest recoveries …) and columns A 2024-25 / BE 25-26 / RE 25-26 / BE 26-27. Example: Corporation Tax total A 2024-25 = 986,766.59.
- `doc/AFS/allafs.xlsx`: nine sheets, Statement I Consolidated Fund. Rows are by major head: 0005 CGST 908,954.11; 0007 UTGST; 0008 IGST −32,482.83; 0009 GST Comp Cess 150,569.84; 0020; 0021; …
- `doc/eb/stat1.xlsx` (Expenditure Profile, Statement 1 "Summary of Expenditure"). Revenue/Capital split for Central Expenditure (Establishment, Central Sector Schemes, Other Central Expenditure) and Transfers (CSS, FC Transfers, Other Transfers). Total Expenditure A 2024-25 = 4,652,867.4. "Resources of Public Enterprises" (IEBR) = 488,590.03.
- `doc/eb/stat4a.xlsx`: Centrally Sponsored Schemes by Demand No. and scheme, Rev/Cap.
- `doc/eb/stat7.xlsx` (Statement 7 "Subsidies and Subsidy related schemes"), A 2024-25 / BE / RE / BE:
  - Food 199,867.09 / 203,420 / 228,153.65 / 227,629.
  - Fertiliser 170,682.96 (NBS 52,810; Urea 117,872.96).
  - Petroleum (LPG) 14,479.01.
  - Interest subsidies 21,885.18 (MISS 17,811.72).
  - Other subsidies 15,692.25.
- `doc/eb/stat18.xlsx`: Transfer of Resources to States & UTs with legislature (NDRF/NDMF, EAP grants/loans, Art. 275(1), SASCI capex loans 149,483.73, FC grants by type).
- Expenditure Budget statement titles (from home-page anchors):
  - 1 Summary; 2a/2b variations; 3a Ministry expenditure; 4a CSS; 4aa SNA balances; 4b CS schemes; 4c Other Central Exp.; 4d Other Transfers; 5 UT transfers.
  - 6 Grants for creation of capital assets; 7 Subsidies; 8 DCU net budget support; 9 Grants to private institutions; 10a-13 SC/ST/NER/Children/Gender.
  - 14 Charged; 15 Reserve Funds; 15a Sovereign Green Bonds; 16 Provisions by Head of Account; 17 Reconciliation DG/AFS/EP; 18 Transfers to States.
  - 19 EAPs; 20 Grants & loans to foreign governments; 21 Contributions to international bodies; 22 Establishment; 23 GIA salaries; 24 Autonomous bodies.
  - 25 Resources of PEs; 26 Investment in PEs; 27 EBR (fully serviced bonds); 27a EBR of commercially-run undertakings.
- Receipt Budget annexes (titles): 1 Trends in receipts; 2 Analysis of tax/non-tax; 3 Reconciliation AFS vs RB; 4/4A/4B **State-wise distribution of net proceeds of Union taxes**; 4C CAG-certified net proceeds; 5 Tax arrears; 6 NTR arrears; **7 Revenue impact of tax incentives (tax expenditure)**; 8 NSSF sources and application; 9 Debt position; 9(i)-(iv) Liabilities / Assets / Guarantees / Asset register; 10 Rupee loans; 10a-k special securities (oil, fertiliser, FCI bonds, PSB recap, back-to-back GST loans to states); 11 NSSF; 12 Annuity liabilities; 13 External assistance; 14 Market loans due 2026-27.
- `doc/16fc.pdf` (Explanatory Memorandum on the 16th FC): award period "2026-27 to 2030-31 commencing from April 1, 2026"; vertical devolution "share at 41 per cent of the net proceeds (divisible pool)". Also mentions a state fiscal-deficit cap of 3% of GSDP. 16fcvol1.pdf Last-Modified 23 Jan 2026.
- `previous_union_budget.php`: archive of all Union Budgets from 1996-97 to 2025-26, including interim budgets. Two URL schemes: `budget_archive/ubYYYY-YY/…` (old) and `budgetYYYY-YY/index.php` (2019-20 onward).
- `website-policies.php`: copyright policy as quoted in §0.8. `termsofuse.php` has only the standard linked-sites disclaimer. robots.txt → 404 (none).

### 1.2 Economic Survey 2025-26 (indiabudget.gov.in/economicsurvey/)
- Page lists "Economic Survey 2025-26" chapters 1-16, "Charts & Tables" xlsx per chapter (`doc/tabchart/tabchartN.xlsx`), and the Statistical Appendix as per-table PDFs (`doc/stat/tabX.Y.pdf`) plus a full PDF.
- Date: `doc/Statistical-Appendix-in-English.pdf` Last-Modified 28 Jan 2026; `doc/stat/tab2.3.pdf` Last-Modified 29 Jan 2026. The Survey was released around 29 Jan 2026.
- Fiscal tables:
  - 2.3 Receipts & expenditure of the Central Government (2017-18 to 2024-25 PA, ₹ crore). Its source note reads "Union Budget documents and Controller General of Accounts".
  - 2.4 Same as % of GDP (**old base**).
  - 2.5 Outstanding liabilities of the Centre.
  - 2.6/2.7 States and General Government.
  - 2.8 GST revenue.
  - 9.1 GST in monthly high-frequency indicators (HFIs).
- **Quirk:** the statistical appendix is PDF-only, and pdftotext layout interleaves columns badly (seen in tab2.3). The Survey predates the new GDP series, so its NAS tables and %-of-GDP figures are on the 2011-12 base.

### 1.3 CGA (cga.nic.in)
- `https://cga.nic.in/`: 200. The "Accounts" section is filled in by JS. The underlying page is `https://cga.nic.in/Accountproc.aspx`: an ASP.NET WebForms page with dropdowns for Monthly Accounts (1997-98 → 2026-27), Finance Accounts (1976-77 → 2024-25), Accounts at a Glance (1999-2000 → 2024-25) and Appropriation Accounts (2003-04 → 2024-25).
- A form POST (not a login; ordinary public form) redirects to stable GET URLs:
  - `https://cga.nic.in/MonthlyReport/Published/{m}/{FY}.aspx`. Example: `/7/2026-2027.aspx`. Apr/May/Jun/Jul 2026-27 are listed.
  - `https://cga.nic.in/FinanceReport/Published/2024-2025.aspx`: statement PDFs such as `https://cga.gov.in//writereaddata/file/Fin20242025Statement2.pdf`, …Statement15, …NoteofAccount, …CAGCert. `Fin20242025Statement2.pdf` Last-Modified **22 Dec 2025**.
  - `https://cga.nic.in/GlanceReport/Published/2024-2025.aspx` → `writereaddata/file/AccountsataGlance%202024-25English.pdf`.
  - `https://cga.nic.in/AppropriateReport/Published/2024-2025.aspx`: per-grant Appropriation Accounts PDFs.
- Monthly report July 2026 (HTML table "UNION GOVERNMENT ACCOUNTS AT A GLANCE AS AT THE END OF JULY 2026", Rs crore):
  - Revenue Receipts BE 3,533,150, actual 1,267,573 (35.9%).
  - Tax (Net) 844,560. Non-tax 423,013.
  - Interest 426,566. Capex 450,635. Total Expenditure 1,761,853.
  - Also: sources of financing the deficit, Major Subsidies, and detail pages.
  - Footer "Last Updated Date: 29 Sep 2026".
- August 2026 POST → alert "No Details Available For This Month". This matches the calendar (due 30 Sep).
- `MonthlyReport/Published/3/2025-2026.aspx` = "PROVISIONAL ACCOUNTS FOR 2025-2026":
  - Revenue Receipts 3,302,225; Tax (Net) 2,623,264; Non-tax 678,961.
  - Revenue Exp 3,836,032; Interest 1,242,575; Capex 1,069,119; Total Exp 4,905,151.
  - Total receipts 3,385,982. Implied FD = **1,519,169**.
  - **Possible data error:** "Recovery of Loans" PA 2025-26 = 24,617, identical to the 2024-25 Actuals figure in the Budget. Flag it for the verifier.
  - The HTML is Word-exported and carries MS-Word metadata junk ("Sridhar, Normal, HP, …2026-01-23T06:41:00Z").
- `https://cga.nic.in/Page/Advance-Release-Calendar.aspx`: "Every month, the data is disseminated on the last date of the month following the reference month except in the case of March … it would be released only by 31st May."
- `https://cga.nic.in/NSD/Published/list.aspx`: National Summary Data Page (IMF SDDS "Central Government Operations"), 1998-99 → 2026-27. `/NSD/Published/7/2026.aspx` gives Apr-Jul 2026 FD 455,144 vs 468,416 in the previous year. Plain HTML.
- AAG 2024-25 PDF contents:
  - Ten-year summary (App. 1), NTR (2), Commercial receipts (3), Major schemes (4), Rev/Cap by major items (5), **Pay & allowances (6)**, **Subsidies (7)**, Ministry expenditure (8), Maturity profile (9), **Object Head-wise expenditure 2024-25 (12)**.
  - Object-head examples (₹ crore, total): 01 Salaries 1,52,792.42; 04 Pensionary charges ~3,41,384; 31 Grants-in-aid general 5,16,672.84; 33 Subsidies 4,41,861.69; 35 Grants for creation of capital assets 2,72,655.81; 36 GIA salaries 59,461.92.
  - The PDF text layout is misaligned in places; Phase 1 needs a table extractor and manual checks.
- Quirks:
  - HEAD returns 404 but GET works (IIS).
  - Mixed hosts `cga.gov.in` / `cga.nic.in` in the links.
  - The CGA `Page/Copyright-Policy.aspx` page has an **empty** body. `Page/Terms-of-Use.aspx` has only the linked-sites disclaimer.
  - No robots.txt (404).
  - No explicit licence.

### 1.4 DEA (dea.gov.in)
- **TLS quirk:** `https://www.dea.gov.in/…` fails with schannel `SEC_E_WRONG_PRINCIPAL` (certificate name mismatch). `https://dea.gov.in/…` (no www) works.
- `https://dea.gov.in/reports-central-government-budget` (EFC listing; "Last Updated On: 28.09.2026") lists these editions:
  - 2017-18 (07.11.2019, `/files/other_reports_documents/Economic_Functional_Statics_2017_2018.pdf`).
  - 2016-17 (10.07.2018).
  - 2015-16 (06.06.2016).
  - Undated edition (17.03.2016).
  - 2005-06 … 2010-11.
  - Page 2: FunClass201112 … 201415.
  - The 2017-18 PDF was downloaded (583 KB). Contents: "I. Economic Classification; II. Economic-cum-Functional Classification; Appendix". The preface says the methodology follows national income accounting, and that EFC totals "do not tally with figures given in the Budget documents" (interest to DCUs and loans written off are excluded; the capital account includes railways/posts own funds).
  - No edition after 2017-18 was found. Whether the series was formally discontinued is UNVERIFIED.
- `https://dea.gov.in/reports-public-debt-management`:
  - Quarterly Report on Public Debt Management Jan-Mar 2026 (13.07.2026). Earlier quarters: Oct-Dec 2025 (27.03.2026), Jul-Sep 2025 (01.01.2026), Apr-Jun 2025 (03.10.2025).
  - **Status Paper on Government Debt for 2023-24 (29.08.2025)**; for 2022-23 (31.07.2025); for 2021-22 (23.10.2023).
  - No Status Paper for 2024-25 yet. The Apr-Jun 2026 quarterly report has not been posted.
- Jan-Mar 2026 QR (pdftotext):
  - Table 4.4, ownership pattern of G-secs: commercial banks 32.99% (Mar 2026) vs 36.18% (Mar 2025); FPIs 2.95%; pension funds 4.62%.
  - Table 4.5: T-bill ownership.
  - The report also notes that CPI from Jan 2026 is on the revised base year 2024.
- `https://dea.gov.in/reports-central-government-borrowings`:
  - "Market Borrowing by Central Government during 2025-26" (13.08.2026, `English_statement_Market_Borrowing_2025-26.pdf`).
  - Quarterly "Central Government Debt for the quarter ended March 2026 Q1" (30.06.2026). Quarter naming quirk: Jan-Mar is labelled "Q1" and Oct-Dec "Q4".
- `https://dea.gov.in/website-policies`: copyright text quoted in §0.8. robots.txt is the Drupal default.

### 1.5 GST (GSTN / GST Council)
- `https://www.gst.gov.in/download/gststatistics`: curl gets an F5 "TSPD" JavaScript bot-challenge page. I did **not** try to defeat it. WebFetch rendered the page and returned the file list:
  - `//tutorial.gst.gov.in/offlineutilities/gst_statistics/statewise_GST_collection_{2025-26,2026-27}.xlsx`
  - `Settlement-of-IGST-to-State-{2025-2026,2026-2027}.xlsx`
  - `9YearsReport.pdf`, `Yearwise-Pre-GST-revenue.pdf`
  - GSTR-1/3B filing statistics and e-way bill statistics.
- `tutorial.gst.gov.in` (robots: `Allow: /`) serves the files directly:
  - `statewise_GST_collection_2025-26.xlsx`: 200, 73 KB, Last-Modified 25 Sep 2026. Sheets `GST_Revenue-All_India`, `Collections-Statewise`, `Refund-Statewise`. "Data upto : 31st Mar 2026", Rs crore, CGST/SGST/IGST/Total by month. FY 2025-26 figures:
    - Gross ₹2,227,095.73 cr (domestic 1,631,769.38 + imports IGST 595,326.35).
    - Refunds 292,630.57.
    - Net 1,934,465.16.
    - **No cess rows.**
  - `statewise_GST_collection_2026-27.xlsx`: "Data upto : 31st Jul 2026". It lags the August PDF report.
  - `Settlement-of-IGST-to-State-2025-2026.xlsx`: state-wise regular and ad-hoc IGST settlement by month.
- `https://tutorial.gst.gov.in/downloads/news/aug_2026_gst_revenue_report_final_for_publishing_monthly.pdf`: 200, 1.07 MB. "GST Gross and Net Collections as on 31/8/2026 (Amount in crores)":
  - Total Gross GST Revenue Aug-26 1,99,853 vs 1,74,116 (+14.8%).
  - Net 1,68,057 (+8.3%).
  - Apr-Aug gross 10,42,757 (+11.0%).
  - Tables 1-4 give SGST settlement and state-wise figures.
  - Note: "The above numbers are provisional".
  - `grep cess` found nothing.
  - The file name pattern appears to be `{mon}_{yyyy}_gst_revenue_report_final_for_publishing_monthly.pdf`. Only the August 2026 name is VERIFIED; other months may use a different pattern.
- `https://www.gst.gov.in/policies/termsandconditions` (via WebFetch): lists "web scraping" among unauthorised activities punishable under the IT Act ss.43/45. This matters for Phase 1 automation: **download the published xlsx and PDF files at low frequency, do not crawl the portal, and ideally get permission.**
- `https://gstcouncil.gov.in/compensation`: only the Compensation Act and Rules. No live cess or compensation status data.
- `https://gstcouncil.gov.in/en/copyright-policy`: "may be reproduced free of charge after taking proper permission by sending a mail to us … source must be prominently acknowledged".
- Compensation cess end: newsonair.gov.in (1 Jan 2026) says the new tobacco excise and Health & National Security Cess "will replace the compensation cess" from 1 Feb 2026. SECONDARY articles (BusinessToday, 31 Jan 2026) say the ₹2.69 lakh crore back-to-back loan was to be fully repaid by 31 Jan 2026.
- Monthly PIB release discontinued: SECONDARY (BusinessToday, 3 Jul 2024, "Eyebrows raised after Centre stops release of monthly GST data").

### 1.6 CBDT / Income Tax
- `https://www.incometaxindia.gov.in/*`: **HTTP 403** to curl with a browser UA and Accept headers, including `/robots.txt`. WebFetch also got 403 for `https://www.incometaxindia.gov.in/documents/d/guest/final-time-series-data-pdf`. Search snippets show:
  - "Time Series Data Financial Year 2000-01 to 2024-25" at that URL and at `/w/direct_tax_collections_as_on_16.03.2025.pdf`.
  - "Income Tax Return statistics for Assessment Year 2023-24" at `/w/income-tax-return-statistics-for-assessment-year-2023-24-1`.
- `https://www.incometax.gov.in/iec/foportal/statistics-data`: HTTP 500 (curl and WebFetch).
- PIB (curl works; WebFetch got 403): `https://www.pib.gov.in/PressReleaseIframePage.aspx?PRID=2065693` "CBDT releases Updated Time Series data upto FY 2023-24", dated 17 OCT 2024.
- Time series to FY 2024-25: SECONDARY (caclubindia, updated 24 Nov 2025). Provisional FY 2024-25 figures:
  - Net direct taxes ₹22.26 lakh crore; corporate tax 9.86; non-corporate 12.35.
  - Direct tax/GDP 6.73% (old base).
  - Taxpayers 12.13 crore; ITRs 9.18 crore.
  - Exact release date UNVERIFIED.
- In-year direct-tax collection updates (SECONDARY): net direct taxes ₹12.12 lakh crore up to 17 Sep 2026 (+12.96%); FY26 net ₹23.40 lakh crore (Business Standard, 4 May 2026). The primary release channel is UNVERIFIED because the site is blocked.
- The Chrome-extension route was not used: 4 browsers were connected and choosing one needs the owner's input.

### 1.7 CBIC / Department of Revenue
- `https://www.cbic.gov.in/`: 200 but a 3.3 KB JS single-page-app shell; no static content. I found no structured revenue-statistics page for customs or central excise.
- **Best customs/excise sources are the Receipt Budget (`doc/rec/tr.xlsx`, major heads 0037 Customs, 0038 Union Excise) and the CGA accounts.** Customs gross 2024-25 A = 233,201; Union Excise 300,253 (BAG Receipts sheet).
- `https://dor.gov.in/`: 200. `/annual-report` → 404. The DoR home page links to gst.gov.in statistics.

### 1.8 data.gov.in / other
- `https://www.data.gov.in/catalog/economic-classification-central-budget`: WebFetch 403. curl 200, but the content is JS-rendered (static HTML "No Result Found...").
  - Footer: "licensed under the Government Open Data License - India".
  - Odd footer text: "This is a sandbox environment created for testing and demonstration purposes only." Log this as a quirk.
  - I could not see which years the dataset holds (UNVERIFIED). The api.data.gov.in API needs a (free) API key, which is an access request.
- `https://openbudgetsindia.org/`: redirects to `https://indiabullsmf.com/`. `/api/3/action/package_search` → 404 page titled "Casino Sites India". **Domain compromised / lapsed.** Their GitHub (github.com/cbgaindia) was not checked.
- `https://doe.gov.in/`: intermittent schannel "failed to receive handshake" on the first try; 200 with `--tlsv1.2` and via Python.
- MoSPI (context only; another agent owns it):
  - PE 2025-26 press note (`…Press_Note_on_GDP_Estimates_for_Q4_2025-26_and_PE_FY_2025-26_F.pdf`, dated 5 Jun 2026): "The Ministry has released the New Series of Annual and Quarterly GDP estimates with base year 2022-23 on 27th February, 2026". Nominal GDP 2025-26 346.36 lakh crore, 2024-25 318.07 lakh crore.
  - Q1 2026-27 GDP note: URL timestamp 31 Aug 2026.

---

## 2. Failures / blocks (for ISSUES.md)
| What | Result | Action |
|---|---|---|
| incometaxindia.gov.in (all paths) | 403 to curl and WebFetch | Owner: open in a normal browser or ask CBDT; possibly WAF/geo filtering |
| incometax.gov.in statistics-data | 500 | retry later |
| gst.gov.in pages | F5 JS bot challenge; ToS forbids scraping | use tutorial.gst.gov.in direct files; seek GSTN permission |
| www.dea.gov.in | TLS cert name mismatch | use dea.gov.in |
| doe.gov.in | intermittent TLS handshake failure | retry / TLS 1.2 |
| indiabudget / CGA HEAD requests | 404 on HEAD, 200 on GET | use GET |
| data.gov.in catalog | JS-rendered; WebFetch 403 | API key needed |
| openbudgetsindia.org | hijacked → casino/MF redirect | do not use |
| CGA Aug-2026 monthly | not yet published (due 30 Sep) | expected |
| DEA EFC | latest 2017-18 | rebuild the classification from object heads and NAS |
| CGA PA 2025-26 "Recovery of loans" = 24,617 (= 2024-25 actual) | suspicious | verifier to check against Budget 2027-28 actuals when released |

## 3. Reference-year view (Union fiscal)
- Audited full-year accounts: **2024-25** (Finance Accounts, Dec 2025; also the Actuals in Budget 2026-27).
- Provisional full year: 2025-26 (CGA PA, end-May 2026). Audited 2025-26 actuals arrive with Budget 2027-28 (~1 Feb 2027) and Finance Accounts (~Dec 2026 to early 2027).
- Tax detail: 2024-25 actual by major head (Receipt Budget / AFS). CBDT time series to 2024-25 (provisional). GST 2025-26 full year from GSTN (excluding cess).
- Debt stock: Status Paper to 2023-24. Quarterly debt data to Mar 2026.
- EFC: 2017-18 only. The 2024-25 economic classification must be built (object head + major head mapping).
- Any SAM year ≤ 2024-25 is fully covered on the Union side. 2025-26 is covered only provisionally.
