# Phase 0 recon: State government finances and Centre-State transfers (`state_fiscal`)

Working notes, written 2026-09-29. Every fetch below was made on 2026-09-29 unless stated otherwise.
Tools: `curl` with a desktop-browser User-Agent (status, headers, HTML), WebFetch, WebSearch.
Probe files went to the session scratchpad only, never into the repo.

Status labels: **verified** means I fetched the primary page or file and saw it. **secondary** means I only saw it in
press or aggregator coverage. **unverified** means I could not confirm it.

---

## 0. Headline findings

1. **RBI "State Finances: A Study of Budgets of 2025-26"** is the latest edition, released **23 Jan 2026** (verified,
   RBI publication page). It covers 2023-24 Accounts, 2024-25 RE and 2025-26 BE. It has 37 Statements, 13 Appendix
   Tables and state-wise Appendices I-IV, each offered as XLSX and PDF. The 2026-27 edition is not out yet (the page
   still lists the 23 Jan 2026 edition as latest on 2026-09-29).
2. **Blocker:** `rbidocs.rbi.org.in`, which hosts every XLSX and PDF, serves an F5/TSPD JavaScript bot challenge to curl
   (HTTP 200, `text/html`, `window["bobcmn"]` script). WebFetch gets an image CAPTCHA page ("What code is in the
   image?"). I did not try to get around it. Automated ingestion of RBI files will need manual download by the owner or
   RBI permission. RBI's Terms of Use also restrict deep-linking and caching (see §9).
3. **16th Finance Commission (FC16)** submitted its report to the President on **17 Nov 2025**. It was tabled with the
   Union Budget on **1 Feb 2026** and covers **2026-27 to 2030-31** (verified: Explanatory Memorandum PDF and PRS summary).
   - Vertical share stays at **41%**. The Government accepted this.
   - Horizontal weights: income distance 42.5, population (2011) 17.5, forest 10, demographic performance 10, area 10,
     and a new **contribution to GDP 10**. The tax and fiscal effort criterion was dropped.
   - There are **no revenue-deficit, sector or state-specific grants**. Local body grants total ₹7,91,493 crore
     (EM para 8). Total grants are about ₹9.47 lakh crore (PRS).
4. **FC16 published its data annexes as open XLSX files** (verified, HTTP 200, not blocked). They include:
   - a Centre-to-State transfers time series 1952-53 to 2025-26 BE;
   - state-wise Key Fiscal Indicators 2012-2024, from CAG accounts, about 100 line items for every state;
   - sector- and type-wise subsidies 2018-19 to 2025-26 BE (Union plus states);
   - a 53 MB State Finance Accounts revenue and expenditure dump;
   - a ULB-level finance dump from cityfinance.in, 2015-16 to 2023-24, about 4,600 ULBs a year.

   This is the best machine-readable, unblocked source for state fiscal flows.
5. **CAG** publishes several things:
   - Per-state **Finance Accounts** (Vol I and II). **2024-25 accounts are already published** for many states (for
     example Maharashtra, Uttar Pradesh and Gujarat were uploaded around Jan-Mar 2026).
   - **Monthly Key Indicators (MKI)**, current to **August 2026** for Maharashtra, as PDF.
   - The all-states **"State Finances 2023-24"** publication, released **31 Dec 2025** with 10-year state-wise
     annexures from 2014-15 to 2023-24. The first edition (2022-23) came out in Sept 2025.
   - "FA&AA data" machine-readable folders. These sit on CAG SharePoint and **need a Microsoft login**.
6. **Base-year interaction:**
   - MoSPI released the 2022-23-base GDP series on **27 Feb 2026**. It covers 2022-23 to 2025-26. The back series is
     "expected to be released by December 2026" (PIB FAQ).
   - The RBI 2025-26 study (Jan 2026) and the FC16 files (Feb 2026) came out **before** the new series. Their
     %-of-GDP/GSDP ratios therefore use the **2011-12 base**. This is inferred from dates; I could not open the RBI files
     to confirm.
   - The rupee flows themselves (accounts data) do not depend on base year. Only the ratios need recomputing.
   - States are moving GSDP to the 2022-23 base during FY27. MoSPI guidelines were issued 7 May 2026 (secondary).
7. **Suggested reference year for this block:** **2023-24** is the latest year with *audited* all-state accounts in
   compiled, consistent form (RBI Accounts, the CAG State Finances 2023-24 publication and the FC16 KFI file). 2024-25
   Accounts exist state by state in CAG Finance Accounts PDFs and should reach the next RBI study, expected around
   Dec 2026 or Jan 2027. That expected date is my inference from the release pattern, not confirmed.

---

## 1. RBI — State Finances: A Study of Budgets

**Fetched:** `https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=State%20Finances%20:%20A%20Study%20of%20Budgets`
returned HTTP 200 (194,927 bytes).
- Page text: "Jan 23, 2026 State Finances: A Study of Budgets of 2025-26". The theme chapter is "III. Demographic
  Transition in India – Implications for State Finances".
- Archive year links: 2026, 2024, 2023, 2021, 2020 … 2002. There is no "2025" entry because the 2025-26 edition fell
  in Jan 2026.
- Footer: "Website last updated date: Sep 29, 2026".

**Contents listed on the page (all offered as XLSX and PDF):**
- **Appendix Tables 1–13** (all-states consolidated):
  1. Major Deficit Indicators
  2. Devolution and Transfer of Resources from the Centre
  3. Development / Non-Development Expenditure (aggregate)
  4. Development Expenditure by Major Head
  5. Non-Development Expenditure by Major Head
  6. Development and Non-Development Expenditure
  7. Composition of Social Sector Expenditure
  8. Decomposition of GFD
  9. Financing of GFD
  10. Financing of GFD as % of total
  11. Composition of Outstanding Liabilities of States and UTs
  12. Outstanding Liabilities as % of total
  13. State Government Market Borrowings
- **Statements 1–37** (state-wise), including:
  - 1 Major Fiscal Indicators; 2 Revenue Deficit; 3 GFD; 4 Decomposition of GFD
  - 5–10 Financing of GFD for 2023-24 (Accounts), 2024-25 (RE) and 2025-26 (BE)
  - 11 Development Expenditure; 12 Non-Development Expenditure; 13 Interest Payments; **14 Tax Revenue**;
    15 Non-Tax Revenue; 16 Loans from Centre; **17 Devolution and Transfer of Resources from the Centre**
  - 18–20 Outstanding Liabilities; 21–22 Market Borrowings / SDLs; 23–24 SDL maturity profile; 25 T-bill investments
  - 26–27 Education and health shares; 28 Guarantees; **29 Wages and Salaries**; 30 O&M; 31–32 Social sector
  - **33 Revenue Receipts of States and UTs**; **34 Revenue Expenditure of States and UTs**; 35 Development
    Expenditure select indicators; **36 Subsidies**; 37 Health, water and sanitation expenditure
- **Appendices I–IV** (state by state, split into several XLSX files): I Revenue Receipts; II Revenue Expenditure;
  III Capital Receipts; IV Capital Expenditure. These hold the full line-item receipts and expenditure by state. They
  include the tax-type breakdown: SGST, sales tax/VAT, state excise, stamps and registration, vehicles, electricity
  duty, land revenue and others. There are about 29 Appendix IV files.
- There is also an `ESTATES23012026…XLSX` file, probably a note or table on "e-States" (unverified).

**File URLs follow this pattern:**
- `https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/14_ST230120264DFE56A61A0F424C823D5A84BE4C0294.XLSX` (Statement 14, Tax Revenue)
- `https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/17_ST2301202683B49BF6F4584A6985B2CCCAA41B020E.XLSX` (Statement 17, Devolution)
- `https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/02_APP23012026B2830D87C491433F932392727168FB91.XLSX` (Appendix Table 2)
- `https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/1APPENDIX23012026_17425ACAC5CC04CA89C85718ED3D03279.XLSX` (Appendix I, part 1)

The filenames contain a hash, so they cannot be predicted from edition to edition. The listing page has to be scraped
for links each year.

**Probe download failed (bot protection):**
- `curl` returned HTTP 200 `text/html` of about 42–49 KB for each of 6 XLSX URLs. The body is an F5/TSPD challenge
  page: `window["bobcmn"] = …/TSPD/…` and a `failureConfig` string.
- WebFetch on the PDF equivalent (`…/PDFs/14_ST2301…PDF`) got a CAPTCHA page: "This question is for testing whether you
  are a human visitor…", "What code is in the image?".
- I did **not** attempt to solve or circumvent it. **Action:** the owner downloads the XLSX set manually from a browser,
  or asks RBI for bulk access or permission. Logged as an access request.

**Coverage and base:**
- Each edition covers Accounts for T-2, RE for T-1 and BE for T. Older editions go back to 2002 on the page.
- The %-of-GDP/GSDP ratios in the Jan 2026 edition must use the 2011-12-base GDP, because the new series only came out
  on 27 Feb 2026. This is inferred from dates, not read from the file.
- Secondary coverage (drishtiias, visionias) quotes: GFD 3.3% of GDP in 2025-26 BE; capex 3.2% of GDP; liabilities
  28.1% of GDP at end-March 2024, rising to 29.2% by March 2026.

**Units:** ₹ lakh or ₹ crore, to be confirmed. Recent editions use ₹ crore for statements and ₹ lakh in the state
appendices. This is unverified because the files could not be opened.

**Related RBI publications (verified listing pages, same bot block on files):**
- *Handbook of Statistics on Indian States 2024-25*, released **11 Dec 2025**. Fiscal tables 164–176 cover state-wise
  GFD, revenue expenditure, primary deficit, own tax revenue, own non-tax revenue, interest payments, capital
  expenditure, social sector expenditure and composition of outstanding liabilities. Tables 19–52 are GSDP/GSVA, almost
  certainly on the 2011-12 base.
  URL: `https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook%20of%20Statistics%20on%20Indian%20States`
- *Report on Municipal Finances*: latest **13 Nov 2024**; the earlier edition was 2022. Statements 1–8 cover municipal
  corporation revenue receipts, own revenue, revenue expenditure, establishment, admin, O&M and capital outlay, state
  by state. Appendices I–IV hold state-level MC receipts and expenditure.
  URL: `https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Report%20on%20Municipal%20Finances`
- *Finances of Panchayati Raj Institutions*: the only edition is **24 Jan 2024**, covering 2020-21 to 2022-23. It has
  Appendices I (revenue receipts of village panchayats) and II (revenue expenditure).
  URL: `https://www.rbi.org.in/Scripts/OccasionalPublications.aspx?head=Finances%20of%20Panchayati%20Raj%20Institutions`
- DBIE (`https://data.rbi.org.in/DBIE/`) returned HTTP 200 but is a JavaScript SPA. Search results say it carries state
  deficit, receipts, expenditure and GFD-financing tables. I did not inspect it; that belongs to the RBI family.
  `dbie.rbihub.in` also responds, but it is on the Reserve Bank Innovation Hub domain. It is not confirmed as an
  official RBI dissemination point, so do not use it.

---

## 2. Finance Commission (15th and 16th)

**Fetched:**
- `https://fincomindia.nic.in/commission-reports`: HTTP 200. Lists "Report of Sixteenth Finance Commission for
  2026-2031" and "Report of Fifteenth Finance Commission for 2021-26 & … 2020-21".
- `https://fincomindia.nic.in/commission-reports-sixteenth`: HTTP 200. Links found:
  - Reports: `asset/doc/commission-reports/16th-FC/reports/Vol1-Main-Report.pdf` (7.4 MB, Last-Modified 1 Feb 2026)
    and `Vol2-Annexures.pdf` (5.8 MB), plus Hindi versions.
  - `16fc-EM.pdf`: Explanatory Memorandum on action taken.
  - **relevant-data/** (all HTTP 200 on HEAD, XLSX MIME):
    - `State Finance Accounts - Revenue and Expenditure.xlsx`: 53,376,635 bytes, Last-Modified 3 Feb 2026
    - `State Finances - Key Fiscal Indicators.xlsx`: 530,793 bytes, 3 Feb 2026
    - `Time series of transfer of resources from Centre to States.xlsx`: 96,812 bytes, 3 Feb 2026
    - `Horizontal Devolution.xlsx`: 24,005 bytes, 3 Feb 2026
    - `Sector wise Subsidies and Transfers.xlsx`: 39,108 bytes, 5 Feb 2026
    - `Type wise Subsidies and Transfers.xlsx`: 29,144 bytes, 5 Feb 2026
    - `FC16 ULB Data Dump Cityfinance.xlsx`: 10,380,666 bytes, 19 Feb 2026
    - Also listed, not probed: `Financial Data of SPSEs in various State.xlsx`, `Sector-wise Profit and Losses of SPSEs
      in various States.xlsx`, `Accounts in Arrear of SPSEs in various States.xlsx`, `Salary Data.xlsx`,
      `Rural Urban transition data.xlsx`, `Trends in expenditure - Centre.xlsx`
  - Commissioned studies (PDF). Examples: "A Study of Off-Budget Borrowings in India by WB", "A study on Subsidies and
    Transfers in India by ADB", "Macroeconomic and Fiscal Policy Simulations for the 16th FC by MSE".
- `https://fincomindia.nic.in/commission-reports-fifteenth`: HTTP 200. Has the 15th FC Vols I–IV (PDF and digitised
  DOCX/PDF) and studies.

**Probe results (scratchpad only):**
- **Time series of transfers.xlsx**: sheets 'Time series of transfers - mast', 'Grants - details RBI', 'GDP',
  'FC XII report annex 2.1', 'RBI Bulletin references', 'GRR'.
  - Columns: FC, Year, States' share, FC grants, Total transfers through FC, Non-FC grants, Total grants, Total
    transfers, % GTR, GTR, FC share, % GDP.
  - Rows run from 1952-53 to **2025-26BE**. Example: 2023-24 share 11,29,494; FC grants 1,48,522; total transfers
    18,68,754 (₹ crore).
  - Source notes say "2016-17 to 2023-24: Statement 18 of expenditure profile of Union Budget as IPFS reports were
    discontinued" and "RBI data on actuals is available only till 2022-23".
- **Horizontal Devolution.xlsx**: state-wise population (1971, 2011, 2018-19 to 2023-24 estimates), area, and
  comparable GSDP 2018-19 to 2023-24 (₹ crore; All States 2023-24 = 2,21,00,500). Sources: Census, MoSPI, Survey of
  India. These are the criterion inputs. The final shares are in Vol I, Table 8.9, per the EM.
- **Key Fiscal Indicators.xlsx**: sheet 'State-wise', 483 columns, organised as blocks for All_States, non-NEH, NEH,
  and each state, with year columns 2012–2024.
  - About 100 line items (A.1 … E.3), including:
    - A.1.1.1 Taxes on Sales, Trade; A.1.1.2 SGST; A.1.1.3 State Excise; A.1.1.4 Taxes on Vehicles; A.1.1.5 Stamps and
      Registration; A.1.1.6 Land Revenue; A.1.1.7 Other Taxes
    - A.1.2 Non-Tax; A.1.3 Share in Union taxes; A.1.4 Grants from GoI; A.1.4.a GST compensation
    - A.4.2.b SASCI loans
    - B.1.a Interest; B.1.b Pensions; B.1.c Salaries; B.1.4 Assignment and compensation to Local Bodies
    - C.1 Public Debt; C.2 Public Account liabilities; C.8 Guarantees; C.10 GSDP; D.1–D.3 deficits
  - Notes: source is "Compilation of State Finance Accounts/ Audit reports"; GSDP from MoSPI; "For All_States, India
    GDP figure is used in place of combined GSDP"; "Some of the 'nil' values may be missing values"; "Off-budget
    borrowing data is not complete"; "GST compensation loan has been considered as central grants".
  - **Year label "2024" = FY 2023-24.** Evidence: C.1 Public Debt, All States, "2024" = 67,87,363 crore, which matches
    CAG's "₹67.87 lakh crore … as of March 31, 2024".
  - 2023-24 All-States values (₹ crore):

    | Item | Value |
    |---|---|
    | Revenue receipts | 37,93,278 |
    | Own tax | 18,79,708 |
    | SGST | 8,00,112 |
    | Sales tax/VAT | 3,97,467 |
    | State excise | 2,49,133 |
    | Stamps | 2,20,289 |
    | Vehicles | 1,06,021 |
    | Share in Union taxes | 11,29,397 |
    | Grants | 4,72,466 |
    | Revenue expenditure | 38,96,647 |
    | Capex | 7,27,926 |
    | Interest | 4,94,911 |
    | Salaries | 10,86,649 |
    | Pensions | 4,94,939 |
    | Fiscal deficit | −8,64,160 |

  - GSDP used: 3,01,22,956. This is the old-base 2023-24 GDP level.
- **Sector wise Subsidies and Transfers.xlsx**: "(Rs. Crore)", by State × Sector (Agriculture, Business, Cash Transfers,
  Education, Food, Health, Power, Social Security …), for 2018-19 to 2023-24 plus 2024-25 (RE) and 2025-26 (BE).
  Includes a "Union" block.
- **ULB data dump.xlsx**: sheets 'Demographic_Data_All_ULBs' (4,860 rows) and 'Financial & Docs_All_ULBs clean'
  (37,867 rows × 49 columns).
  - Years 2015-16 to 2023-24; 4,620 ULBs in 2023-24.
  - Columns: Property Tax, Other Tax, Fees and User Charges, Total Own Revenue, CSS, Union FC Grants, SFC Devolution,
    Total Grants, Assigned Revenue, Salaries, Pension, O&M, Interest, and more.
  - **Values appear to be in rupees, not crore.** Khategaon Town Panchayat property tax is 56,082,096 in 2023-24.
    Units are unverified; normalise before use.

**FC16 facts (verified):**
- `16fc-EM.pdf`: "SUBMITTED TO THE PRESIDENT ON NOVEMBER 17, 2025", covering "2026-27 to 2030-31 commencing from
  April 1, 2026". It says: "recommended to retain the States' share at 41 per cent", "The Government has accepted",
  "not recommended revenue deficit grants", "not recommended any sectorspecific or Statespecific grants", and "total
  grants for duly constituted RLBs and ULBs of 7,91,493 crore".
- PRS summary (`https://prsindia.org/policy/report-summaries/report-of-the-16th-finance-commission-for-2026-31`):
  tabled 1 Feb 2026. Weights: income distance 42.5, population 2011 17.5, forest 10, demographic performance 10, area
  10, contribution to GDP 10. RLB ₹4.35 lakh crore, ULB ₹3.56 lakh crore, disaster ₹1.55 lakh crore, total grants
  ₹9.47 lakh crore.
- The Vol I text (pdftotext) contains "41 per cent" repeatedly and "November 2025". I did not extract the state-share
  table (Table 8.9). Secondary coverage says UP's share went from 17.939% to 17.619%; unverified against Table 8.9.

**Licence:**
- `https://fincomindia.nic.in/copyright_policy` returned HTTP 200 via curl, but the body has **no policy text**. Only
  the footer is there: "© Copyright 2023-2025 Content Owned by Sixteenth Finance Commission, Government of India All
  Rights Reserved."
- WebFetch of the same page returned 403.
- Conclusion: **no explicit open licence found.** These are government works, so attribute them and ask if in doubt.

---

## 3. Union Budget — transfers to States (Centre-side view)

- `https://www.indiabudget.gov.in/doc/eb/vol1.pdf` (Expenditure Profile 2026-27, 13.5 MB): HTTP 200 via curl.
  WebFetch returns 403 on indiabudget.gov.in, so use curl.
- **Statement 18, "Total Transfer of Resources to States and UTs with Legislature (excluding States' share of Net
  Proceeds of Union Taxes and Duties)"**, page 215, ₹ crore. Values for 2024-25 Actuals / 2025-26 BE / 2025-26 RE /
  2026-27 BE:

  | Item | 2024-25 A | 2025-26 BE | 2025-26 RE | 2026-27 BE |
  |---|---|---|---|---|
  | I. Important items (NDRF/NDMF assistance, EAP grants and loans, Art 275(1) proviso, SASCI loans, Special Assistance) | 2,02,663.57 | 2,29,031.48 | 2,30,144.00 | 2,79,110.01 |
  | II. FC grants (ULB/RLB, SDRF, SDMF, Health, Post-Devolution RD grants) | 1,20,858.16 | 1,32,767.00 | 1,52,953.00 | 1,29,396.60 |
  | III. Other transfers (CSS Revenue, Central Sector, Other, Capital) | 5,55,099.66 | 7,17,041.50 | 4,98,159.00 | 6,09,007.53 |
  | …of which CSS | 3,82,335.71 | — | — | 5,20,333.39 |
  | IV. Delhi, Puducherry, J&K | 60,007.07 | … | … | 76,999.80 |
  | **Grand Total** | **9,38,628.46** | **11,37,320.41** | **9,43,172.86** | **10,94,513.94** |

  - Row II at 2026-27 BE has no revenue deficit or health grants, consistent with FC16.
  - The Grand Total for 2026-27 BE is 10,94,513.94; the other years are as shown.
  - Footnote: "Compensation to States/UTs for revenue losses on roll out of GST has been phased out w.e.f. 2026-2027."
- `https://www.indiabudget.gov.in/doc/eb/sbe42.pdf` (Demand No. 42, Transfers to States, 331 KB): HTTP 200 via curl.
  Detailed heads: FC grants by component, Special Assistance (SASCI), EAP, NDRF/NDMF. The PDF layout is multi-column
  and messy, so manual verification is needed when parsing.
- A search result puts devolution in 2026-27 BE at **₹15,26,255 crore** (9.6% over 2025-26 RE). Unverified against
  Budget at a Glance.

**Tax devolution instalments (PIB):**
- `https://www.pib.gov.in/PressReleasePage.aspx?PRID=2292912`: HTTP 200 via curl (WebFetch 403). "Posted On: 01 AUG
  2026". Additional instalment of ₹1,09,019 crore, "in addition to the normal monthly devolution to be released on 10th
  August 2026". The state-wise table "Net Proceeds of Union Taxes and Duties for August 2026" includes UP 19,208,
  Bihar 10,845, MP 8,010, WB 7,866, Maharashtra 7,022 and Sikkim 365.
- **Contradiction:** one secondary outlet (etvbharat, via search snippet) reported UP at 17,908. The official PIB table
  says 19,208. Use PIB only.
- Secondary sources say devolution comes in 14 instalments a year (12 monthly plus advance instalments). The monthly
  PIB releases are HTML tables; use them for checks, not as a series.

**PFMS:**
- `https://pfms.nic.in/Home.aspx` returned HTTP 200. The page is mostly login-gated modules (Login, Create Login id,
  Helpdesk Login) and has no public report on state-wise releases.
- The PIB GDP FAQ says MoSPI's new series uses "Data from the PFMS … to compile central government estimates and
  allocate them among states".
- No public bulk extract was found. **Not a usable open source**; fall back on Budget Statement 18 and CGA accounts.

---

## 4. CAG — State accounts, MKI, State Finances publication

**State Accounts Report page:** `https://cag.gov.in/en/state-accounts-report?defuat_state_id={64..92}` returned
HTTP 200 for each of the 29 IDs. "defuat" is CAG's own spelling. The state list:
- Andhra Pradesh 64 … West Bengal 92
- Delhi 69, J&K (up to 30-Oct-2019) 74
- Telangana and Puducherry are also listed but have different IDs

Each state page has tabs: Accounts at a Glance, Appropriation Accounts, Finance Accounts, **Monthly Key Indicators**,
and **FA&AA data**.

- **Maharashtra (79) finance accounts:** Finance Accounts-I 2024-25 (8.89 MB) and II 2024-25 (37.22 MB), plus 2023-24
  and earlier.
- **Maharashtra (79) MKI:** 2026-27 April to **August 2026**; all 12 months of 2025-26; 2024-25.
  Sample file: `https://cag.gov.in/uploads/state_accounts_report/account-report-MKI-August-2026-06ab3b9b9821545-07859602.pdf`
  (HTTP 200, PDF, 412 KB).
  - Content: "GOVERNMENT OF MAHARASHTRA ACCOUNTS AT A GLANCE (At the end of August 2026) (UNAUDITED PROVISIONAL
    FIGURES)", in ₹ crore.
  - Rows: Revenue Receipts; Tax Revenue split into GST, Stamps and Registration, Land Revenue, Sales Tax, State Excise,
    State's Share of Union Taxes and Other; Non-Tax; Grants-in-aid; Capital receipts; Borrowings; Revenue Expenditure
    (interest, salaries, pensions, subsidies); Capital Expenditure.
  - Columns: BE, actuals to date, % of BE, and % for the same period last year.
  - Format is PDF only. Excel was not seen: none of the 29 state pages had `.xls` links.
- **Uttar Pradesh (90):** Finance Accounts Vol I and II 2024-25 (English) were uploaded; the hex timestamp in the
  filename decodes to about Jan 2026. MKI runs to July 2026.
- **Default page:** Finance Accounts 2024-25 were uploaded with a timestamp of about 6 Mar 2026.
- **Coverage of 2024-25:** my crude link scan found 2024-25 Finance Accounts links on most state pages. This is
  imprecise because filenames vary; Maharashtra's are labelled only by tab year. The exact list of states with 2024-25
  accounts needs a Phase 1 check.
- **FA&AA data tab:** links to `https://cagiaad-my.sharepoint.com/:f:/g/personal/iswing1_cag_gov_in/…` (folder
  "FA&AA DATA/Maharashtra/2024-25"). The HEAD request gives a 302 to OneDrive, then a redirect to
  **login.microsoftonline.com**. This is **login-gated**, so it goes on the access request list. It is probably the
  machine-readable Finance Accounts data.

**CAG "State Finances 2023-24" publication (all 28 states):**
- Press release `https://cag.gov.in/uploads/PressRelease/PR-English-press-release-31-12-25-0695604bf7f4099-76760551.pdf`:
  HTTP 200. Dated "31st December, 2025": "second edition of the Publication on State Finances 2023-24 … all 28 States …
  10 year period from 2014-15 to 2023-24", with "expanded set of annexures providing 10 year, State-wise fiscal data",
  new SOTR and subsidy analysis, and "interactive dashboards".
- PDF `https://cag.gov.in/uploads/media/State-Finances-2023-24-30-12-25-069550a999e5002-23252834.pdf`: HEAD returned
  200, 51,074,088 bytes, Last-Modified 31 Dec 2025. Not downloaded.
- The first edition, "State Finances 2022-23: A Decadal Analysis" (Sept 2025), is confirmed only by secondary coverage
  (policyedge, nextias).
- `https://cag.gov.in/en/page-sf-dashboard`: HTTP 200, title "State Finances 2022-23". Dashboard content is rendered
  with JavaScript and was not inspected.
- `https://www.digitalreports.cag.gov.in/` ("SFAR — State Finances Audit Reports") is a Next.js app showing "2024-25".
  The report count loads client-side.
- The per-state State Finances Audit Reports are listed at `https://cag.gov.in/en/audit-report?report_type=53`. Example:
  "Report No. 3 of the year 2025 – State Finances Audit Report" at `/en/audit-report/details/122272`.

**Licence:** `https://cag.gov.in/en/page-copyright` (WebFetch): material may be reproduced if it is "reproduced
accurately and not to be used in a derogatory manner or in a misleading context", and "The source must be prominently
acknowledged". Third-party copyright material is excluded. This is a permissive-with-attribution policy, not GODL.
`/en/page-terms-conditions` returned HTTP 200; I did not extract its body text.

---

## 5. PRS Legislative Research

- `https://prsindia.org/budgets/states`: HTTP 200. **30 state budget analyses for 2026-27** are linked, plus archives
  from 2016-17.
  - Footer: "PRS Legislative Research is licensed under a **Creative Commons Attribution 4.0 International License**"
    (link to creativecommons.org/licenses/by/4.0).
  - Disclaimer: "PRS does not represent that this information is accurate or complete."
- `https://prsindia.org/budgets/states/policy/state-of-state-finances-2025` gives "State of State Finances 2025-26",
  analysing all states plus Delhi, J&K and Puducherry, "based on their budget documents and CAG accounts". The PDF is
  `https://prsindia.org/files/budget/budget_state_finance_report/2025/SOSF_2025.pdf`, dated October 2025 per the search
  snippet.
- Sample: `https://prsindia.org/budgets/states/uttar-pradesh-budget-analysis-2026-27` says UP's budget was presented
  11 Feb 2026, with 2026-27 GSDP projected at ₹39.8 lakh crore, "growth of 28% over the revised estimate for 2025-26".
  That growth rate looks anomalous, possibly a base change or projection quirk. Flag it; do not use it as GSDP.
- Format: HTML and PDF narrative with tables. No bulk data. Use it as a **cross-check and secondary source only** (it
  is derived from state budgets and CAG).
- `https://prsindia.org/terms-of-use` returned 404.

---

## 6. GST — SGST by state (overlaps with the tax family)

- `https://tutorial.gst.gov.in/downloads/news/aug_2026_gst_revenue_report_final_for_publishing_monthly.pdf`: HTTP 200,
  PDF, 1.07 MB. It contains:
  - "Table 1: SGST & SGST portion of IGST settled to States/UTs in August, 2026", pre- and post-settlement, ₹ crore
  - "Table-2 … till August, 2026" (fiscal year to date)
  - "Table 3: State-wise growth of GST Revenues"
  - "Table 4: State Wise/ Approving Authority wise Domestic Collection", CGST/SGST/IGST split by Centre and State
    formations
- Secondary: August 2026 gross GST was ₹1,99,853 crore; post-settlement states' revenue was ₹95,531 crore.
- The filename pattern changes month to month, so there is no stable URL. Find the file from the GST news listing.
- `https://www.gst.gov.in/download/gststatistics` returned HTTP 200 but embeds a CAPTCHA audio element. Not used.
- The GST Council revenue page (`/gst-revenue-collection`) returned 404.
- Licence for gst.gov.in / tutorial.gst.gov.in was not checked here. Defer to the tax family.
- For **annual SGST by state (accounts basis)**, prefer CAG Finance Accounts, FC16 KFI A.1.1.2, or RBI SF Appendix I.

---

## 7. Local bodies

| Source | Status | Latest | Notes |
|---|---|---|---|
| RBI Report on Municipal Finances | verified listing | 13 Nov 2024 | Municipal corporations only; state-wise statements; files blocked by rbidocs bot wall |
| RBI Finances of PRIs | verified listing | 24 Jan 2024 (data to 2022-23) | Village panchayats; 2.58 lakh panchayats (secondary) |
| FC16 ULB dump (cityfinance) | verified, opened | Feb 2026 (data to 2023-24) | Best ULB microdata, ~4,600 ULBs/yr; units look like rupees |
| cityfinance.in (MoHUA/Janaagraha) | HTTP 200 (redirects to /home) | unknown | JavaScript portal; no licence text found in page HTML |
| eGramSwaraj (MoPR) | HTTP 200 | live | Public receipt/expenditure reports exist (`RecExpReportNew.do?finYear=…`), scheme-wise; structure not probed |
| FC16 Vol I ch. on local bodies / Vol II annexures | verified PDFs | Feb 2026 | Grant design; state-wise LB grant allocations |
| Budget Statement 18 row II | verified | 2026-27 BE | Centre→LB FC grants (via states) |

For the SAM, local government is best treated as **part of "State and local government"**. Flows from state to local
bodies come from KFI B.1.4 (Assignment and Compensation to Local Bodies, ₹1,14,381 crore in 2023-24) plus FC local
body grants. ULB own revenue can be estimated from the cityfinance dump. The PRI own-source revenue is tiny (about 1% of
revenue, per secondary coverage of RBI).

---

## 8. Other sources found

- **NITI Aayog Fiscal Health Index 2026**: `https://niti.gov.in/sites/default/files/2026-03/Fiscal-Health-Index-2026.pdf`
  returns 307 then HTTP 200 on www.niti.gov.in (PDF, 9.96 MB). It is a composite index, so it gives no SAM flows.
  Useful only for context.
- **State budget documents** (each state finance department): the primary source, but fragmented across 28 or more
  websites with varied formats. RBI, CAG and FC16 already compile them, so do not ingest them directly.
- **Aggregators** (dataful.in, factly): republish RBI data. Do not use as a primary source.

---

## 9. Licences and terms summary

| Publisher | Page checked | Finding |
|---|---|---|
| RBI | `https://www.rbi.org.in/Scripts/Disclaimer.aspx` | No open licence. Terms: "caching and links to, and the framing of this Web Site or any of the contents are prohibited" except as allowed; home page linking "upon notifying RBI in writing"; deep links need a "specific request for, and secure permission from RBI". **This restricts the site's plan to deep-link sources.** Access request: ask RBI for permission, or cite without hyperlinks. |
| CAG | `https://cag.gov.in/en/page-copyright` | Reproduction allowed if accurate, not misleading, and the source prominently acknowledged |
| Finance Commission | `https://fincomindia.nic.in/copyright_policy` | Page body empty; footer "All Rights Reserved". No explicit licence found |
| PRS | `https://prsindia.org/budgets/states` footer | **CC BY 4.0** |
| Ministry of Finance (indiabudget.gov.in, PIB) | not checked in depth | No licence verified. GODL-India may apply via data.gov.in, but no state-fiscal dataset on data.gov.in was confirmed |
| data.gov.in | `https://data.gov.in/` HTTP 200 (first attempt timed out) | Could not find state-finance datasets or GODL page (`/government-open-data-license-india` led to page_not_found) |

---

## 10. Reference-year inputs

| Dataset | Latest audited/actual year | Latest any-vintage year | Base-year note |
|---|---|---|---|
| RBI SF 2025-26 (Jan 2026) | 2023-24 Accounts | 2025-26 BE | Ratios on 2011-12 base GDP/GSDP (inferred). Next edition, expected ~Dec 2026/Jan 2027, should add 2024-25 Accounts (inferred) |
| CAG State Finances 2023-24 (31 Dec 2025) | 2023-24 | 2023-24 | Audited; flows independent of base; ratios use old-base GSDP |
| CAG Finance Accounts per state | 2024-25 (many states; uploaded Jan–Mar 2026) | 2024-25 | Audited |
| CAG MKI | provisional to Aug 2026 (Maharashtra) | Aug 2026 | Unaudited, monthly |
| FC16 KFI xlsx | "2024" = 2023-24 | 2023-24 | GSDP in file = old-base (2023-24 All-India 301.2 lakh crore) |
| FC16 transfers time series | 2023-24 actuals | 2025-26 BE | Nominal ₹ crore |
| FC16 subsidies xlsx | 2023-24 actuals | 2025-26 BE | Nominal ₹ crore |
| FC16 ULB dump | 2023-24 | 2023-24 | Nominal, apparently rupees |
| Union Budget Statement 18 | 2024-25 Actuals | 2026-27 BE | Nominal ₹ crore |
| RBI Municipal Finances | ~2022-23/2023-24 (unverified) | — | — |
| RBI PRI Finances | 2022-23 | 2022-23 | — |
| GST monthly state tables | Aug 2026 | Aug 2026 | Collections basis, not accounts |

**Implication for the SAM reference year:** for the state government block, **2023-24** is fully covered by audited,
consolidated data from RBI, CAG and FC16. **2024-25** is feasible from per-state CAG Finance Accounts in PDF, but needs
28-plus PDF extractions unless the CAG SharePoint "FA&AA data" is opened to us or the next RBI study lands. On the GDP
side, the new 2022-23-base national accounts cover 2022-23 onward. The 2023-24 state fiscal flows can therefore sit in
a new-base 2023-24 SAM, with only the %-of-GDP ratios recomputed.

---

## 11. Failures and issues log

1. `rbidocs.rbi.org.in`: F5/TSPD JavaScript challenge for curl; image CAPTCHA for WebFetch. All RBI XLSX and PDF files
   are affected. Not bypassed.
2. RBI Terms of Use prohibit caching, framing and deep linking without permission. This conflicts with the planned
   per-number source links on the site.
3. CAG FA&AA machine-readable data sits on SharePoint behind Microsoft login.
4. `fincomindia.nic.in/copyright_policy`: WebFetch 403; curl 200 but empty policy body.
5. `indiabudget.gov.in`, `pib.gov.in`, `mospi.gov.in`: WebFetch 403. curl works for indiabudget and PIB.
   `mospi.gov.in` PDFs return 403 even to curl (the press note on the new GDP series).
6. `cag.gov.in/en/state-accounts` returned 404 (wrong path). The correct path is `/en/state-accounts-report`.
7. `prsindia.org/terms-of-use` returned 404. The licence is taken from the site footer instead.
8. `gstcouncil.gov.in/gst-revenue-collection` returned 404. `gst.gov.in/download/gststatistics` embeds a CAPTCHA.
9. `openbudgetsindia.org/organization/reserve-bank-of-india` returned 404.
10. `data.gov.in`: the first request timed out (curl code 000); the retry returned 200. The GODL page path was not found.
11. Contradiction: UP's August 2026 devolution instalment is 19,208 in the PIB official table versus 17,908 in one
    secondary report.
12. Quirk: the FC16 KFI year headers are calendar-style ("2024") but mean FY 2023-24.
13. Quirk: the FC16 ULB dump appears to be in rupees while the other FC16 files are in ₹ crore.
14. Quirk: RBI SF file URLs carry hashes that change every edition.
15. Quirk: CAG MKI and Finance Accounts are PDF only, with varied filenames per state. The Budget Demand PDFs use a
    multi-column layout that is hard to parse.
16. Unverified: RBI SF units, the exact state list with 2024-25 CAG Finance Accounts, the FC16 horizontal share table,
    and the devolution 2026-27 BE of ₹15,26,255 crore.
