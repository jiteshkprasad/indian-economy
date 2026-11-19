# Verification notes: Union government finances and taxes (`union_fiscal`)

- Verifier: independent adversarial verifier (did not produce the recon)
- Date of checks: 2026-09-29
- Method: re-fetched every URL with curl (browser User-Agent), parsed the XLSX files with openpyxl and the PDFs with pdftotext 4.00, and used WebFetch/WebSearch where curl was blocked. Probe files were kept in the session scratchpad, outside the repo. No bulk data was written to the repo.
- Verdict legend: **confirmed** = I reproduced the evidence myself. **corrected** = the core claim holds but some fields are wrong or incomplete. **refuted** = the claim is wrong. **unverifiable** = I could not reproduce the evidence.

## Summary

| Source id | Verdict | Main point |
|---|---|---|
| mof_union_budget_2026_27 | corrected | Figures reproduced. Archive also covers 1947-1995. Last-Modified is unreliable (allafs.xlsx says 2024-08-07 but holds 2026-27 data). Site says PDF prevails over Excel. Statements 27/27a have no xlsx. Small internal inconsistencies. |
| mof_16th_finance_commission | confirmed | 41% retained and **accepted by Government**. 16fc.pdf is the Explanatory Memorandum (Feb 2026). |
| mof_economic_survey_2025_26 | confirmed | Tab 2.3 covers 2017-18 to 2024-25 (PA). Tab 2.8 is state-wise domestic GST 2023-24 to 2025-26 (Apr-Nov). |
| cga_monthly_accounts | corrected | July 2026 is the latest; PA 2025-26 confirmed. **The "Details" sub-pages (tax, non-tax, non-debt, total expenditure) are broken links (HTTP 404).** No devolution-to-States figure on the page. |
| cga_finance_accounts_aag | corrected | Finance Accounts has Statements 1-16 plus 14A and 9-Appendix (not 2-15). AAG 2024-25 PDF Last-Modified 2026-06-30, so its lag is about 15 months, not 9. The 2025-26 Finance Accounts page exists but is empty. |
| dea_economic_functional_classification | corrected | Latest edition is 2017-18 (published 07.11.2019), but its **latest actuals year is 2015-16** (columns 2015-16 A, 2016-17 RE, 2017-18 BE). |
| dea_public_debt_reports | confirmed | All four listing entries and dates reproduced. QR Apr-Jun 2026 is not overdue (last year's came 03.10.2025). |
| gstn_gst_statistics | corrected | Files and totals reproduced. **"No cess rows" is wrong**: the state-wise sheet labels imports "IGST and CESS on Import" and export refunds "IGST and CESS Refund on Exports". |
| cbdt_time_series | unverifiable | Every incometaxindia.gov.in path returns 403, and the e-filing statistics page returns 500. Secondary article dated 24 Nov 2025. |
| cbic_indirect_tax | confirmed | cbic.gov.in is a 3,372-byte JS shell. BAG customs and excise figures reproduced. PPAC was missed for petroleum taxes. |
| data_gov_in_budget | unverifiable | JS-rendered page ("No Result Found"), GODL footer and "sandbox" footer all reproduced. Contents still unknown. |

## Per-source evidence

### mof_union_budget_2026_27 — corrected
- `https://www.indiabudget.gov.in/` returned 200. The page shows "Union Budget Documents 2026-2027" and "Press Conference ... on Union Budget 2026-27". There is no newer (e.g. interim) budget.
- `budget_at_a_glance.xlsx`: 200, 28,188 B, Last-Modified 2026-02-25. Sheets: BAAG, Deficit Statistics, Receipts, Expenditure of GOI, Transfer of Resources. Reproduced:
  - "17. Fiscal Deficit | 1574431 | 1568936 | 1558492 | 1695768"
  - "I. Devolution of States share in taxes | 1286885 | 1392971 | 1526255"
  - "c. Customs | 233201 | 240000 | 258290 | 271200"
  - "d. Union Excise Duties | 300253 | 317000 | 336550 | 388910"
  - "-GST Compensation Cess | 150570 | 167110 | 88000 | .."
  - "-IGST | -32483 | .. | .. | .."
  - Financing: "Market Borrowings (G-sec) 1074512 | ... | 1040439 | 1173210", "Securities against Small Savings 429502 | ... | 372192 | 386772"
- `budget_at_a_glance.pdf` (Last-Modified 2026-01-31) footnote: "The GDP for FY 2026-27 is estimated at 393,00,393 crore, which is 10% over the Advance Estimates for FY 2025-26 of 357,13,886 crore released by NSO." This confirms the old-base denominator.
- `tr.xlsx` (Last-Modified 2026-02-06): "Corporation Tax | 0020 | 986766.59 | 1082000.0 | 1109000.0 | 1231000.0", with Collections, Surcharge, and Health and Education Cess sub-items. Confirmed.
- `stat7.xlsx` (Last-Modified 2026-02-24): Food 199867.09; Fertiliser 170682.96 (NBS 52810, Urea 117872.96); LPG 14479.01; Interest Subsidies 21885.18; Grand Total 422606.49. Confirmed.
- `stat1.xlsx`, `stat18.xlsx`, `stat4a/9/20/23/25/26.xlsx`, `ntr.xlsx`, `ctr.xlsx` and `rec/annex7.pdf` all returned 200.
- **Corrections and quirks found:**
  - `allafs.xlsx` has Last-Modified **Wed, 07 Aug 2024**, yet its content is the 2026-27 AFS ("Actuals 2024-2025 | ... | Budget Estimates 2026-2027"). Last-Modified cannot be used to judge freshness on this server. Check the column headers instead.
  - `doc/eb/stat27.xlsx`, `stat27a.xlsx` and `stat27A.xlsx` return 404, while `stat27.pdf` and `stat27a.pdf` return 200. Not every statement has an xlsx.
  - Site banner: "The Budget data in excel has been generated from System. In case of any inconsistency, pdf files will be treated as final." This must go into provenance: the PDF is the authoritative version.
  - Internal inconsistencies:
    - Revenue Receipts A 2024-25 = 3036613 (BAAG sheet) vs 3036619 (Receipts sheet total).
    - Fertiliser BE 2026-27 = 170781 (BAG "Expenditure of Major Items") vs 170799 (stat7).
  - The BAG "Transfer of Resources" sheet has only three columns (A 2024-25, RE 2025-26, BE 2026-27), with no BE 2025-26.
  - The archive is wider than the recon claimed. `previous_union_budget.php` lists 2025-26 back to 1996-97, plus interim budgets and "1947-1995 (Budget Documents since 1947 to 1995)".
- HEAD returns 404 while GET returns 200: reproduced (`curl -sI .../tr.xlsx` gives "HTTP/1.1 404 Not Found").
- Licence: `website-policies.php` says "This contents of this website may not be reproduced partially or fully, without due permission from Ministry of Finance, Govt. of India. If referred to as a part of another publication, the source must be appropriately acknowledged." No GODL. Confirmed.

### mof_16th_finance_commission — confirmed
- `16fc.pdf`: 200, Last-Modified 2026-01-29. It is the "Explanatory Memorandum as to the Action Taken on the Recommendations Made by the Sixteenth Finance Commission, February, 2026". It says:
  - "report submitted to the President on November 17, 2025"
  - "covering the financial years 2026-27 to 2030-31 commencing from April 1, 2026"
  - "retain the States' share at 41 per cent of the net proceeds (divisible pool)"
  - "**The Government has accepted the above recommendations**"
  - "The Commission has not recommended revenue deficit ..." grants. This is consistent with the absence of PDRD grants in BE 2026-27.
  - Local body grants total 7,91,493 crore; the disaster allocation is 79,406 crore.
- `16fcvol1.pdf` (7.4 MB) and `16fcvol2.pdf` (5.8 MB): 200, Last-Modified 2026-01-23.
- `https://fincomindia.nic.in/` (the 16th FC's own site) returned 200 and has a "16th Finance Commission Report" section. It is an alternative host.

### mof_economic_survey_2025_26 — confirmed
- `/economicsurvey/` returned 200 and shows "Economic Survey 2025-26".
- The Statistical Appendix PDF has Last-Modified 2026-01-28.
- `tab2.3.pdf` has Last-Modified 2026-01-29. It reads "Table 2.3: Receipts and Expenditure of the Central Government", with columns 2017-18 to 2024-25 (PA) and the note "Source: Union Budget documents and Controller General of Accounts".
- In ES tab 2.3, the fiscal deficit for 2024-25 (PA) is 1577270, while the Budget 2026-27 Actual for 2024-25 is 1574431. The PA and Actual vintages differ.
- `tab2.8.pdf` is "Details of total revenue received ... under the head of GST on the domestic supply", state-wise for 2023-24, 2024-25 and 2025-26 (April to November).
- `tabchart1.xlsx` returned 200.

### cga_monthly_accounts — corrected
- `/MonthlyReport/Published/7/2026-2027.aspx` returned 200: "UNION GOVERNMENT ACCOUNTS AT A GLANCE AS AT THE END OF JULY 2026 ... 1 Revenue Receipts 3533150 1267573 35.9 %". Total financing up to July was 455143.82, which matches press reports of an Apr-Jul fiscal deficit of Rs 4,55,144 cr (Business Standard, 31 Aug 2026).
- `/MonthlyReport/Published/8/2026-2027.aspx` returned 200, but the page lists only "April, May, June, July 2026-2027", so August is not published. I did **not** find the literal text "No Details Available For This Month" that the recon quoted. The substance holds.
- `/MonthlyReport/Published/3/2025-2026.aspx` reads "PROVISIONAL ACCOUNTS FOR 2025-2026 ... Total Expenditure (8+10) 4964842 4905151 ... Fiscal Deficit (12-7) 1558492 1519169". The financing table gives TOTAL FINANCING 1519169.24. The page also states "Fiscal Deficit is 4.40 % of GDP", but it does not say which GDP base.
- Recovery of Loans on the PA 2025-26 page is "5 Recovery of Loans 30190 24617 81.5% (94.7%)". This is identical to the BAG 2024-25 actual of 24617, and the COPPY ratio implies that the prior year was also 24617. The anomaly is reproduced and still unexplained. Flag it.
- **Correction:** the "(Details)" links for Tax Revenue, Non-Tax Revenue, Non-Debt Capital Receipts and Total Expenditure point to `DTL12526.HTM`, `Nontax2603.HTM`, `Nondebt2603.HTM` and `TotalExpenditure2603.HTM`. All of these return **HTTP 404**, both at `/MonthlyReport/Published/3/` and at `/MonthlyReport/Published/`. Some hrefs even point to `file:///D:/...` paths.
  - What the page does carry inline: the headline table, Sources of Financing, and Major Subsidies.
  - There is no tax-by-type detail and no devolution-to-States figure on the page, so the recon's key series "tax revenue detail; devolution to States" cannot be reproduced.
- CGA vs Budget "actual" mismatch: the Major Subsidies table on the PA page shows COPPY (2024-25) Urea = 120879.83, while Budget stat7 gives the 2024-25 Urea actual as 117872.96.
- Release calendar (`/Page/Advance-Release-Calendar.aspx`): "the data is disseminated on the last date of the month following the reference month except in the case of March ... it would be released only by 31st May." Confirmed.
- Licence: the body of `/Page/Copyright-Policy.aspx` is empty; only the heading "Copyright Policy" appears. The footer says "This website belongs to Controller General of Accounts ... All rights reserved". So no explicit licence was found, and the "All rights reserved" footer counts against open reuse.

### cga_finance_accounts_aag — corrected
- `/FinanceReport/Published/2024-2025.aspx` returned 200. It links `Fin20242025Statement1..16`, `Statement14A`, `Statement9Appendix`, `Introduction`, `NoteofAccount`, `CAGCert`, `CGACert` and `TableofContents` on the cga.gov.in host. So the statements run 1-16, not 2-15.
- Ranged GET results:
  - Statement2: 206, Last-Modified Mon, 22 Dec 2025
  - Statement16: 22 Dec 2025
  - CAGCert: Tue, 23 Dec 2025
- `/FinanceReport/Published/2025-2026.aspx` returned 200 but has no content. 2025-26 is not yet published.
- `AccountsataGlance%202024-25English.pdf`: 200, 3.05 MB, **Last-Modified Tue, 30 Jun 2026**.
  - Contents: "6. Expenditure on Pay and Allowances 48", "7. Statement of Subsidies 54", "12. Object Head Wise Expenditure for 2024-25 86".
  - The object-head table reads "01 SALARIES 1,52,655.11 137.31" and "33 SUBSIDIES 4,41,861.69 0.00 4,41,861.69". Column misalignment is confirmed: the Total column is shifted onto the next row.
- The Appropriation Accounts 2024-25 page lists per-grant PDFs under `writereaddata/AppAccount/FY20242025/`.

### dea_economic_functional_classification — corrected
- `https://www.dea.gov.in/` fails TLS with "schannel: SEC_E_WRONG_PRINCIPAL (0x80090322)" (reproduced). `https://dea.gov.in/` works.
- The listing (two pages) runs from "An Economic and Functional Classification of the Central Government Budget 2017-18 | 07.11.2019" down to 2005-06. The page footer says "Last Updated On: 28.09.2026". Confirmed: nothing is newer than the 2017-18 edition.
- `Economic_Functional_Statics_2017_2018.pdf` returned 200 (583 KB). The preface says "Since 1957-58, the Economic Division ... has been preparing an economic classification".
- **Correction:** the tables' year columns are 2015-16, 2016-17 (RE) and 2017-18 (BE). So the latest *actuals* year classified is **2015-16**. For the SAM, the usable reference is 2015-16 actuals, not 2017-18.
- Related check: DEA "Indian Public Finance Statistics" (`/reports-public-finance-statistics`) returned 200 but shows "No Data Available". It is not a usable substitute.

### dea_public_debt_reports — confirmed
- `reports-public-debt-management` lists:
  - "Quarterly Report on Public Debt Management for the quarter January - March 2026 ... 13.07.2026"
  - "... April-June 2025 ... 03.10.2025"
  - "Status Paper on Government Debt for 2023-24 29.08.2025"
  - "Status Paper ... 2022-23 31.07.2025"
- `reports-central-government-borrowings` lists:
  - "Market Borrowing by Central Government during 2025-26 13.08.2026"
  - "Central Government Debt for the quarter ended March 2026 Q1 30.06.2026"
- QR Jan-Mar 2026 PDF: 200, 632 KB. It contains "Commercial Banks' share decreased to 32.99 per cent in March 2026" and Tables 4.4 and 4.5 (ownership). Confirmed.
- The Market Borrowing 2025-26 PDF and the Status Paper 2023-24 URL both returned 200.
- The DEA copyright policy allows reproduction "free of charge after taking proper permission by sending a mail to us". Confirmed.

### gstn_gst_statistics — corrected
- `www.gst.gov.in/download/gststatistics` returns 200, but the body is an F5 "TSPD"/"bobcmn" JS challenge. Reproduced; not bypassed.
- `gst.gov.in/policies/termsandconditions` via WebFetch: "Unauthorised activities includes any activity which is punishable under section 43 (for eg web scraping, altering source code, hacking, introducing viruses etc.)". Confirmed.
- `tutorial.gst.gov.in/robots.txt` reads "User-agent: * / Allow: /". Confirmed.
- `statewise_GST_collection_2025-26.xlsx`: "Data upto : 31st Mar 2026".
  - Gross Revenue: CGST 444309.48, SGST 551301.6, IGST 1231484.65, total 2227095.73.
  - Net: 1934465.16.
  - Both reproduced.
- `statewise_GST_collection_2026-27.xlsx`: "Data upto : 31st Jul 2026". Confirmed.
- **Correction on cess:**
  - The `Collections-Statewise` sheet labels the imports row "**IGST and CESS on Import - All India**", with value 595326.35. This equals the All-India "Imports" figure exactly.
  - The `Refund-Statewise` sheet labels "**IGST and CESS Refund on Exports (disbursed by Customs)**", with value 128568.44. This equals the All-India "Export Refund" figure.
  - So the import and export-refund lines may include compensation cess. The recon's statement that the FY 2025-26 total of 22,27,096 is "excluding cess" is **not verified**. Domestic cess is absent, but import cess may be inside.
  - Ask GSTN, or reconcile against CGA/Budget major head 0009 before using these figures.
- Aug-2026 PDF: "GST Gross and Net Collections as on 31/8/2026 ... Total Gross GST Revenue 1,74,116 [Aug-25] ... 1,99,853 [Aug-26] ... 14.8%". Reproduced. The Aug-25 comparator (1,74,116) is a *revised, ex-cess* figure (search snippet: "up 14.8% from the revised August 2025 figure"). It is not the originally published Aug-2025 headline.
- Every tutorial.gst.gov.in file shows Last-Modified 2026-09-25 19:11-19:43, which looks like a bulk sync. Last-Modified does not tell us the publication date.
- `sep_2026_...pdf` returned 404, as expected before about 1 Oct.
- PIB's halt of the monthly GST press release in July 2024 is corroborated only by secondary sources: ThePrint and BusinessToday (3 Jul 2024). I found no PIB-hosted note announcing it.

### cbdt_time_series — unverifiable
- curl on `incometaxindia.gov.in/`, `/robots.txt`, `/documents/d/guest/final-time-series-data-pdf` and the RSS-feed content page all returned 403. WebFetch on the PDF also returned 403.
- `incometax.gov.in/iec/foportal/statistics-data` returned 500.
- A search result title confirms that the document exists: "Income Tax Department Time Series Data Financial Year 2000-01 to 2024-25".
- The caclubindia article is dated **24 Nov 2025** (via WebFetch). It quotes net direct tax of 22.26 lakh crore and direct tax/GDP of 6.73%. The exact CBDT release date is still unverified.
- 22.26 / 0.0673 ≈ 330.8 lakh crore, which is the old 2011-12-base nominal GDP for 2024-25. So the ratio uses the old base, as the recon said.
- The primary channel for monthly direct-tax updates appears to be incometaxindia.gov.in PDFs such as `direct_tax_collections_as_on_16.03.2025.pdf` (seen in search results). That site is blocked. The 2026-27 figure (Rs 12.12 lakh crore to 17 Sep 2026) was seen only in ANI and A2Z Taxcorp.
- Unverified secondary signal: a CBDT FAQ on transition to the "Income-tax Act, 2025" appears in search results. If AY is renamed to "tax year", future ITR statistics labels may change.

### cbic_indirect_tax — confirmed
- `https://www.cbic.gov.in/` returned 200 with 3,372 B (a JS shell). Reproduced.
- The BAG Receipts figures for customs and excise were reproduced (see above).
- **Missed:** PPAC (`https://ppac.gov.in/prices/contribution-to-central-and-state-exchequer`, 200). It has a table from 2014-15 to 2025-26 (P) covering cess on crude, customs duty, NCCD and excise duty on petroleum, plus state VAT/SGST, with an XLS download (`uploads/page-images/1790331603_PP_4_ContributionToExchequer(1).xls`). Example: "Excise Duty ... 2,76,562.9 [2024-25]". This gives product-level taxes for the petroleum sector. Licence not checked.

### data_gov_in_budget — unverifiable
- The catalog URL returned 200 (1 MB), but the static HTML shows "No Result Found...".
- Footer: "licensed under the Government Open Data License - India" and "This is a sandbox environment created for testing and demonstration purposes only". Both reproduced.
- A search snippet describes the dataset as "Incomings Net increase in financial liabilities-Balancing, Decrease in cash balance and Outgoings Deficit on transactions in commodities and services & transfers". This looks like the EFC summary table. Years are unknown.

### Other checks
- `openbudgetsindia.org` returns 301 to `https://indiabullsmf.com/`, whose title is "Best Online Casino India 2026". The recon quoted a different title ("Page not found - Casino Sites India"), but the substance (a hijacked domain) is confirmed.
- MoSPI press note (`latest_release_1780655857536_...pdf`): 200, Last-Modified 2026-06-05.
  - "GDP estimates with base year 2022-23 on 27th February, 2026"
  - "a level of 346.36 lakh crore in the year 2025-26, against 318.07 lakh crore in 2024-25"
  - Confirmed.

## Missed sources (verified to exist)
1. **PPAC: Contribution of Petroleum Sector to Exchequer.** Central and State taxes on petroleum products, 2014-15 to 2025-26 (P), in XLS. This is key for splitting excise, customs and state VAT by product.
2. **CAG Report No. 6 of 2026 (Financial Audit) on Accounts of the Union Government for 2024-25.** The PDF returned 200 and its title page was confirmed. Reportedly tabled on 2 Apr 2026 (secondary source). It gives audit adjustments and misclassification flags (e.g. "Other expenditure" booking) that matter for the economic classification.
3. **fincomindia.nic.in** is the 16th FC's own site and an alternative host for the report and its annexes.
4. Cross-family pointers, not verified here: MoSPI NAS general government accounts (the economic classification of general government on the 2022-23 base) and the RBI Handbook/DBIE central government finance tables. These are the main cross-checks for the rebuilt economic classification.

## Reference-year implications
- Union side: **2024-25** is the latest year that has Budget actuals, audited Finance Accounts (Dec 2025), AAG object heads (Jun 2026) and the CAG audit (Apr 2026). 2025-26 exists only as CGA provisional accounts (FD 15,19,169 cr); Budget actuals for 2025-26 will arrive with Budget 2027-28 (about 1 Feb 2027).
- The latest EFC actuals are 2015-16, not 2017-18.
- All MoF, CGA and CBDT %-of-GDP ratios use the old 2011-12 base. Recompute them on the 2022-23 base.
