# Phase 0 recon: External sector (BoP, IIP, trade, remittances, FDI/FPI/ECB)

Family id: `external`. Working notes by the external-sector recon agent. Fetch date for everything below: **2026-09-29** (IST). Every statement carries the URL actually fetched and what it showed. Anything not confirmed by a fetch is marked **UNVERIFIED**.

Tools used: Python `requests` + BeautifulSoup with a desktop-Chrome User-Agent, `curl`, WebSearch, WebFetch. Small probe files were written only to the session scratchpad (outside the repo). No bulk data was downloaded into the repo.

---

## 0. Headline findings (read this first)

1. **RBI BoP is current and moving to monthly.** The latest quarterly BoP is Q1 2026-27 (Apr-Jun 2026), released **2026-09-01**. The full-year **2025-26** BoP (Preliminary) came out with the Q4 release on **2026-06-08**, about 2.3 months after year-end (earlier than the usual end-June). Since **2026-06-15** RBI also publishes a **monthly BoP** (first month: April 2026). It comes out "by the 15th day or earlier of the second subsequent month". The latest is July 2026, released 2026-09-15.
2. **The annual BPM6 BoP in ₹ crore for 2025-26 is out** in RBI's *Handbook of Statistics on the Indian Economy 2025-26* (released 2026-07-31), Table 127. It has the full services breakdown, primary income (compensation of employees, investment income by type) and secondary income. This is the cleanest single input for the SAM RoW account.
3. **Stocks run to end-March 2026.** The International Investment Position (IIP) for end-March 2026 was released 2026-06-30. External debt for end-March 2026 was released 2026-06-29. The end-June 2026 IIP and external debt are **not yet released** as of 2026-09-29. RBI's press release list up to prid 63685 (29 Sep 2026) has neither. Past pattern suggests they come out around 30 Sep.
4. **2026-27 is a distorted year. Avoid it as a SAM reference year.** RBI ran a special concessional USD-INR swap window for FCNR(B) deposits, ECBs and OFCBs from **2026-06-08**. By 2026-08-31 it had mobilised **US$ 132,980 mn of FCNR(B) deposits**. The July 2026 monthly BoP shows NRI deposits at +US$ 33.5 bn in one month. Q1 2026-27 also shows a West-Asia-conflict oil shock: POL imports were US$ 60.6 bn, FPI outflow US$ 9.6 bn, and reserves fell US$ 8.1 bn on a BoP basis. The rupee is around ₹96/US$ (dbie.rbihub.in, 28-Sep-2026).
5. **A major licence problem sits on merchandise trade data.** The DGCI&S Data Dissemination Policy says the "copyright of trade data is reserved by DGCIS". Data "may not be re-disseminated in any form without the written permission from Director General, DGCIS". This applies even to free use in visualisation apps, and it covers TradeStat, which is sourced from DGCI&S. The permission is royalty-free if no more than 1,000 records are used, or if the data are "substantially different" from what DGCI&S provides. **Access request:** the owner should write to DG, DGCI&S. Alternatives: use the RBI HBS / BoP aggregates, or UN Comtrade under its own re-dissemination FAQ.
6. **RBI file downloads are blocked for scripts.** Every `rbidocs.rbi.org.in` file (the .xlsx/.pdf statements for BoP, external debt, IIP, invisibles, ODI and HBS) returns an F5/TSPD JavaScript-challenge page to curl/requests, and a **CAPTCHA** to WebFetch. The HTML pages on `www.rbi.org.in` (press releases, `PublicationsView.aspx`, `ECBUserView.aspx`) are *not* blocked and contain the same tables as HTML. We did not attempt to bypass the challenge. RBI's `robots.txt` itself returns "Unauthorised Access".
7. **RBI's website terms are restrictive, and there is no open-data licence.** The disclaimer at https://www.rbi.org.in/Scripts/Disclaimer.aspx says "caching and links to, and the framing of this Web Site or any of the contents are prohibited". Linking to the home page requires "notifying RBI in writing". Deep-linking requires "a specific request for, and secure permission from RBI". No GODL/NDSAP licence is stated. **Access request:** get written RBI permission for deep links and for re-publication, with attribution, of derived aggregates.
8. **GDP base-year change is reflected in RBI's ratios. This is inferred, not stated by RBI.** MOSPI's new GDP series (base 2022-23) was released on 2026-02-27, per MOSPI URLs in search results. Direct fetches of mospi.gov.in return HTTP 403. RBI's external-debt-to-GDP ratio for **end-March 2025** was 19.1% in the 27-Jun-2025 release but **19.8%** in the 29-Jun-2026 release. The debt stock barely changed (736.3 to 736.5 US$ bn), so the GDP denominator was revised. None of the RBI releases fetched states which GDP series it uses. Flag this for the national-accounts family.

---

## 1. RBI Balance of Payments: quarterly (BPM6)

- **Latest release:** "Developments in India's Balance of Payments during the First Quarter (April-June) of 2026-27", dated **Sep 01, 2026**, Press Release 2026-2027/1015.
  - URL fetched: https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63493 (HTTP 200)
  - Quote: "India's current account deficit stood at US$ 4.2 billion (0.5 per cent of GDP) in Q1:2026-27". Goods deficit is 86.1. Net services 51.6. Personal transfers 42.9. FDI net 6.1. FPI −9.6. NRI deposits 2.8. ECB 3.3. Reserves −8.1 (depletion). E&O 1.6. Table 1 is in US$ billion, credit/debit/net, with vintage flags "PR: Partially Revised; P: Preliminary".
  - Statements: https://rbidocs.rbi.org.in/rdocs/content/docs/BOPS01092026_1.xlsx and `_2.xlsx`. **Download FAILED.** They returned HTTP 200 but with a 47 KB HTML body containing a `TSPD` bot-challenge script, not an xlsx. We believe Statement I is the BPM6 presentation in US$ and Statement II is in ₹ crore, based on earlier rounds. **UNVERIFIED** because the files could not be opened.
- **Annual 2025-26 (Preliminary):** from the Q4 release "Developments in India's Balance of Payments during the Fourth Quarter (January-March) of 2025-26", dated **Jun 08, 2026**, PR 2026-2027/412.
  - URL: https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=62890
  - 2025-26 figures, credit / debit / net in US$ bn:
    - Current account: 1077.8 / 1103.0 / −25.2
    - Goods: 446.1 / 783.4 / −337.3
    - Services: 421.3 / 204.7 / 216.6
    - Primary income: 55.0 / 103.2 / −48.2
    - Secondary income: 155.3 / 11.7 / 143.6
    - Direct investment net 6.9; portfolio −16.4
    - "India's current account deficit stood at US$ 25.2 billion (0.6 per cent of GDP) in 2025-26"
    - "foreign exchange reserves depleted by US$ 23.6 billion (on a BoP basis)"
  - Footnote: the Q3 2025-26 CAD was "revised to US$ 15.5 billion ... from US$ 13.2 billion ... due to an upward revision of merchandise imports in Customs data". Footnote 2: "For longer time series data, please refer to: DBIE (https://data.rbi.org.in) › Statistics › External Sector › International Trade › Quarterly/Yearly."
- **Reserves variation (old BPM5-style format):** https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63494 (Q1 2026-27, Sep 01 2026) and https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=62891 (2025-26, Jun 08 2026).
  - Quote: "*: Based on the old format of BoP which may differ from the new format (BPM6) in the treatment of transfers ... and ADRs/GDRs".
  - The two formats disagree slightly: 2025-26 CAB is −25.4 here against −25.2 in BPM6.
  - Q1 2026-27 valuation change was −14.4 and the total reserve change −22.5 US$ bn.
- **Release lag:** about 2 months after quarter-end. Q1 ended 30 Jun and was released 1 Sep. Q4 was released 8 Jun, about 2.3 months.
- **SDDS release list page:** https://www.rbi.org.in/scripts/SDDS_ViewDetails.aspx?Id=5&IndexTitle=Balance+of+Payment (WebFetch). It lists BoP releases from 1999-2000 to 2026-27. The page did not state timeliness.

## 2. RBI Balance of Payments: monthly (new in 2026)

- **First release:** "Developments in India's Balance of Payments for the Month of April 2026", Jun 15 2026, PR 2026-2027/457. URL https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=62935. Quote: "Henceforth, India's BoP data for the reference month will be released by the 15th day or earlier of the second subsequent month."
- **June 2026 release:** Aug 14 2026, prid=63373. **July 2026 release:** Sep 15 2026, https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63596.
  - July 2026: CA −7.0; merchandise −31.7; services +17.6; "NRI Deposits (Net) 1.0 → 33.5"; overall balance +20.8 US$ bn.
- **Format:** HTML table only, with PDF link. It is **not BPM6**. Rows are "Transfers (Net)" and "Income (Net)", and "Errors and omissions are included under 'Other Capital'".
- **Quirk:** summing the monthly releases for Apr-Jun 2026 (June release) gives CA −3.1, transfers 41.4 and income −11.1. The quarterly BPM6 release gives CA −4.2, secondary income 40.8 and primary income −10.5. Use the monthly series for nowcasting only; never mix it into the SAM.

## 3. RBI detailed invisibles (services / primary / secondary income by category, quarterly)

- Listing page: https://rbi.org.in/Scripts/Data_IndiasInvisibles.aspx. The latest entry is "Jun 30, 2026 — Data on India's Invisibles for Fourth Quarter (January-March) of 2025-26". Earlier: Q3 on Mar 30 2026, Q2 on Dec 31 2025, Q1 on Sep 30 2025.
- Release: https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63056. It says data are released "as per the IMF's ... BPM6 format". The file is https://rbidocs.rbi.org.in/rdocs/content/docs/IRIPQ4E30062026.xlsx, which is **blocked (TSPD)**.
- Lag is about 3 months. Q1 2026-27 invisibles are expected around 30 Sep 2026 (inferred from the pattern).

## 4. RBI Handbook of Statistics on the Indian Economy 2025-26 (HBS), the best annual source

- Release: https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63268, "Jul 31, 2026 ... released 28th edition".
- Table index: https://www.rbi.org.in/scripts/AnnualPublications.aspx?head=Handbook%20of%20Statistics%20on%20Indian%20Economy&fromdate=07/30/2026&todate=08/01/2026. Each table is an HTML page `PublicationsView.aspx?id=NNNNN` (fetchable) plus XLSX/PDF on rbidocs (blocked).
- External tables confirmed (HTML id):
  - T111/112 Foreign trade US$/₹ (23936/23937)
  - T113-118 commodity exports/imports, including commodity × principal country
  - T119/120 direction of trade (23944/23945)
  - T121-123 trade indices (base 2012-13)
  - T124/125 overall BoP US$/₹
  - **T126/127 BPM6 standard presentation US$/₹ (23951/23952)**
  - T128/129 key components
  - **T130/131 invisibles by category US$/₹ (23955/23956)**
  - T132-137 exchange rates, NEER/REER
  - T138 external assistance
  - **T139-142 NRI deposits outstanding and flows (23964-23967)**
  - T143 foreign investment inflows (23968)
  - T144 forex reserves (23969)
  - T145/146 external debt
  - T147-150 IIP BPM5/BPM6 US$/₹ (23972-23975)
  - T181 net FPI investment
  - T190 international trade in services, monthly (24015)
- **Table 127, fetched and parsed:** "(₹ Crore)", columns 2024-25 and 2025-26, credit/debit/net.
  - "1 Current Account ... 2025-26: 9530151 / 9749904 / -219753".
  - Goods: general merchandise 3928433 / 6286162; merchanting 13823; non-monetary gold debit 640558.
  - Services 1.A.b.1-1.A.b.13 (EBOPS-style): e.g. "1.A.b.9 Telecommunications, computer, and information services 1827090 / 241082"; "1.A.b.10 Other business services 1098453 / 615791".
  - Primary income: "1.B.1 Compensation of employees 76038 / 39309"; "1.B.2 Investment income 325431 / 838517"; "1.B.2.1 Direct investment 111176 / 506075".
- Table 131 (invisibles, ₹ crore) starts in 2006-07. Table 139 (NRI deposits, US$ mn, by scheme FCNR(B)/NR(E)RA/NRO) covers end-March 2008 onward. Table 143 has FDI gross/repatriation/net and FDI by India in ₹ crore and US$ mn from 2004-05. Table 144 has reserves (SDR/gold/FCA/RTP) from 1968-69. Table 190 has monthly services from April 2019.
- **Quirk:** Table 7/8 (state NSVA) still says "(Base: 2011-2012)". Check which GDP base Table 1 uses (national-accounts family).

## 5. RBI International Investment Position (IIP)

- Release "India's International Investment Position (IIP), March 2026", **Jun 30, 2026**, PR 2026-2027/569. URL https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63047.
  - Quote: "Net claims of non-residents on India declined by US$ 52.4 billion during Q4:2025-26 to US$ 209.9 billion as at end-March 2026". Also: "ratio of net claims of non-residents on India to GDP improved significantly to (-)5.9 per cent in March 2026 from (-)9.0 per cent a year ago". Also: "Reserve assets accounted for 57.1 per cent of India's international financial assets".
  - File: https://rbidocs.rbi.org.in/rdocs/content/docs/IIP30062026.xlsx is **blocked**.
- Data-source note: https://www.rbi.org.in/scripts/IIPDetails.aspx?Id=150 ("Date : Jun 30, 2026"). It lists the sources feeding each BPM6 cell: FLA census, IBS, Portfolio Investment Positions by Counterpart Economy, BAL statement, the external debt data and so on.
- Listing: https://www.rbi.org.in/scripts/IIP.aspx (HTTP 200). Quarterly with a lag of about 3 months. End-June 2026 is not yet out as of 2026-09-29.

## 6. RBI India's External Debt (quarterly)

- "India's External Debt as at the end of March 2026", **Jun 29, 2026**, PR 2026-2027/563. URL https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63041.
  - "US$ 762.8 billion ... external debt to GDP ratio increased to 20.8 per cent at end-March 2026 from 19.8 per cent".
  - By sector: general government 167.5; deposit-taking corporations 202.1; other sectors 355.9 US$ bn.
  - Shares: NFCs 36.4%, DTCs 26.5%, GG 22.0%, OFCs 10.2%.
  - Currency: USD 55.5%, INR 29.4%.
  - Statements (IMF EDS format and old format): https://rbidocs.rbi.org.in/rdocs/content/docs/EXTERNALDEBT29062026_ST1.xlsx and ST2. These were **not fetched** because the rbidocs pattern is blocked.
- Previous vintage for comparison: https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=60729 (Jun 27 2025): "US$ 736.3 billion ... 19.1 per cent at end-March 2025". This is the evidence for the GDP-denominator revision in §0.8.
- Also fetched: https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=58788 (end-June 2024 release, Sep 30 2024). It confirms the end-June data release pattern of about 30 Sep.

## 7. Services trade: monthly (RBI)

- July 2026: https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63480 (Aug 31 2026). Values are in US$ million: receipts 38,253 and payments 20,606. "Data for April-July are provisional". Lag is about 1 month (~45 days is the stated norm). The June data (prid 63270) came out 31 Jul, and April (prid 62832) on 29 May.
- There is no category split in the monthly release. The categories come quarterly (§3) and annually (HBS T127/T131).

## 8. Remittances

- **RBI 6th round, India's Remittances Survey (reference year 2023-24):** RBI Bulletin article "Changing Dynamics of India's Remittances – Insights from the Sixth Round of India's Remittances Survey", **Mar 19, 2025**. URL https://rbi.org.in/scripts/BS_ViewBulletin.aspx?Id=23260 (HTTP 200; PDF on rbidocs not fetched).
  - "The share of the US in India's total remittances remained largest, rising to 27.7 per cent in 2023-24".
  - "UAE ... increasing from 18 per cent in 2020-21 to 19.2 per cent in 2023-24". UK 10.8%, Singapore 6.6%, Canada 3.8%, Australia 2.3%.
  - "The GCC countries (UAE, Saudi Arabia, Kuwait, Qatar, Oman and Bahrain) together contributed 38 per cent".
  - States: Maharashtra 20.5%, Kerala 19.7%, Tamil Nadu 10.4%, Telangana 8.1%, Karnataka 7.7%.
  - Coverage: "30 authorised dealer (AD) banks (covering around 99 per cent ...)". Total remittances US$ 118.7 bn in 2023-24.
  - No 7th round was found, per WebSearch on 2026-09-29. The rounds have been roughly 3-yearly (2016-17, 2020-21, 2023-24), so the next is likely around 2026-27. **UNVERIFIED.**
- **Aggregate remittances:** the BoP personal transfers credit is in secondary income. Q1 2026-27 personal transfer receipts were US$ 42.9 bn and Q4 2025-26 US$ 43.5 bn (see §1). The annual 2025-26 secondary income credit was US$ 155.3 bn.
- **World Bank WDI:** https://api.worldbank.org/v2/country/IND/indicator/BX.TRF.PWKR.CD.DT?format=json&mrv=3 returned `lastupdated 2026-07-13`: 2025 = 150,711,596,171 US$ (calendar year). The WB bilateral remittance matrix, per search, is at best 2021. **UNVERIFIED.** knomad.org/data/remittances redirects to a worldbank.org brief.
- **LRS outward remittances:** an RBI Bulletin Current Statistics table ("Outward Remittances under the Liberalised Remittance Scheme (LRS) for Resident Individuals") appears in the bulletin page text at https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx?yr=2026&mon=9. Monthly. Its table number could not be pinned down.

## 9. Forex reserves (Weekly Statistical Supplement)

- WSS extract, **Sep 25, 2026**: https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63666. "As on Sep. 18, 2026": total reserves ₹ 73,42,985 crore / US$ 765,901 mn. Components: FCA 630,980; gold 111,292; SDRs 18,739; reserve position in the IMF 4,890 (all US$ mn). Weekly change −14,881 US$ mn. Lag is 1 week (Friday release, previous Friday's data).
- Cross-check: dbie.rbihub.in shows "Foreign exchange reserves 18-Sep-2026 765.9 US$ bn".

## 10. NRI deposits

- Flows come in the BoP (quarterly and monthly, §1-2). Outstanding amounts by scheme are in HBS T139-T142 (annual, end-March) and in the monthly RBI Bulletin table "Outstanding Balances under Various Non-Resident Indian Deposit Schemes". That table appears as "No. 45" in the bulletin page text; the numbering may differ by edition.
- **2026 swap window:** https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63274 (Aug 01 2026): "facility for offering concessional swaps for fresh FCNR(B) deposits, OFCB and ECB inflows, on June 05, 2026 ... operationalised on June 08, 2026". https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63638 (Sep 21 2026): "FCNR(B) Deposits 1,32,980* ... OFCBs 5,320 ... ECBs 5,296 ... Total 1,43,596" (US$ mn; FCNR till 31 Aug 2026).

## 11. External Commercial Borrowings (monthly, RBI)

- "RBI releases data on ECB / FCCB / RDB for June 2026", Aug 05 2026 (prid 63293). The July 2026 release is prid 63537, Sep 07 2026.
- Data page: https://www.rbi.org.in/Scripts/ECBUserView.aspx?Id=274, "Data on ECB/FCCB for the Month of July 2026". It is an HTML table at **loan level**: borrower, "Economic sector of borrower" (NIC-like), "Equivalent Amount in USD", purpose, maturity, lender category. There are 186 rows under Automatic ("General Permission") and Approval routes. XLSX/PDF copies are on rbidocs (blocked).
- Lag is about 5-6 weeks. **Quirk:** these are *registrations/agreements*, not disbursements. BoP ECB flows are the disbursement-based measure.
- Listing: https://rbi.org.in/Scripts/ECBView.aspx (from the Statistics page).

## 12. FDI

- **DPIIT FDI factsheet (quarterly):** the March 2026 factsheet PDF was fetched: https://www.dpiit.gov.in/static/uploads/2026/06/41192ca92c1de34eb064800fbffa0379.pdf (200, application/pdf, 10 pages).
  - "FACT SHEET ON FOREIGN DIRECT INVESTMENT (FDI) INFLOW FROM APRIL, 2000 to March, 2026 (Updated up to March, 2026)".
  - Total FDI inflow 2025-26 is US$ 58,846 mn. The FDI equity month-wise values for 2025-26 are in INR crore.
  - "Figures are provisional, subject to reconciliation with RBI". Country-wise (Singapore, Mauritius, US …) and sector-wise tables are included.
- **June 2026 factsheet (Q1 2026-27):** the total is US$ 19.81 bn per Business Standard https://www.business-standard.com/economy/news/india-fdi-inflows-rise-6-to-19-81-bn-in-apr-jun-quarter-dpiit-data-126092501024_1.html (search result, URL dated 2026-09-25). The PDF URL was **not found**. DPIIT pages are a client-rendered Next.js app: https://www.dpiit.gov.in/publications/fdi-factsheet returns a 7 KB shell to curl, and WebFetch gets **HTTP 403**. DPIIT robots.txt: "User-agent: * Allow: /".
- DPIIT copyright/terms pages (https://www.dpiit.gov.in/copyright-policy, /website-policies, /terms-conditions) all return the same 7 KB JS shell. The licence text could not be read, so the DPIIT licence is **UNVERIFIED**.
- **RBI FDI:** BoP direct investment (quarterly and monthly, gross/repatriation/net) is in HBS T143 and in the monthly RBI Bulletin "Foreign Investment Inflows" table.
- **RBI Census on Foreign Liabilities and Assets (FLA) of Indian Direct Investment Entities 2024-25:** https://rbi.org.in/Scripts/PublicationsView.aspx?id=23438, "Date : Oct 29, 2025". Provisional. 45,702 entities responded. Market-value FDI/ODI positions by country, activity sector, listed/unlisted, plus trade parameters. The 2025-26 round is expected around Oct 2026 (inferred). The index page https://rbi.org.in/Scripts/AnnualPublications.aspx?head=Annual+Census+on+Foreign+Liabilities+and+Assets+of+Indian+Companies lists only 2024-25.

## 13. Overseas Direct Investment (ODI)

- Monthly: "Overseas Direct Investment for August 2026", Sep 18 2026 (prid 63623); July 2026 on Aug 18 2026 (https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63396). The data are XLSX only, e.g. https://rbidocs.rbi.org.in/rdocs/content/docs/OFDI18082026.xlsx (**blocked**).
- Listing: https://rbi.org.in/Scripts/Data_Overseas_Investment.aspx. Lag is about 3 weeks. The data are company-level commitments by JV/WOS, country and activity (known from past rounds, not re-verified).

## 14. Other RBI surveys found

- **Survey on Computer Software and ITES Exports 2025-26**, Sep 18 2026: https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63625. "exports of software services ... increased by 8.2 per cent ... to US$ 221.4 billion". "United States of America ... share of 54.1 per cent, followed by European countries (31.8 per cent)". Final estimates ₹ 19,55,947 crore. This gives destination shares for the largest services export line.
- **Survey of Foreign Liabilities and Assets of Mutual Funds 2025-26**, Aug 31 2026: https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63479. MF foreign liabilities are US$ 31.5 bn and overseas assets US$ 10.2 bn at end-March 2026. The implied rate is ₹2,98,200 cr / US$31,504 mn ≈ ₹94.7/US$ at end-March 2026.
- **Survey on International Trade in Banking Services (ITBS) 2025-26** launched Jun 30 2026 (prid 63055); no results yet.

## 15. RBI DBIE (time-series portal)

- `https://dbie.rbi.org.in/` **FAILS** TLS verification: "schannel: SNI or certificate check failed: SEC_E_WRONG_PRINCIPAL". With `-k` it redirects to https://data.rbi.org.in/DBIE/#/.
- https://data.rbi.org.in/ returns HTTP 200: an Angular SPA ("<title>DBIE</title>", 9.4 MB main.js). The bundle references an internal `/api/services/queryInterface` endpoint and a "DisclaimerDbie" component. There is **no documented public API**. Downloads are "Excel, CSV, and PDF" from the UI (per search snippet). We did not probe the internal API.
- https://dbie.rbihub.in/ returns HTTP 200: a Next.js "Database on Indian Economy — RBI DBIE" front-end with "FULL DATA" links and an "External" theme. Its headline tiles are consistent with official data (reserves 765.9 US$ bn at 18-Sep-2026, USD/INR 95.97 on 28-Sep-2026). But it shows "Real GDP growth Q2 2025-26 8.2%", which looks stale. Its content is client-rendered, and its terms and official status are **UNVERIFIED**.
- `https://data.rbi.org.in/robots.txt` returns a "Page Not Found" HTML page.

## 16. Merchandise trade: Department of Commerce TradeStat (EIDB/MEIDB)

- https://tradestat.commerce.gov.in/ redirects (200) to `/eidb/commodity_wise_export`. robots.txt: "User-agent: * / Disallow:" (allow all).
- **EIDB (annual, FY):** "Data available 2017-2018 to 2025-2026   Last data updated on 07/08/2026". Report types:
  - commodity-wise at the 2/4/6/8-digit HS level, in US$ mn, ₹ crore or quantity
  - chapter-wise
  - commodity-wise all countries
  - commodity × country
  - country-wise
  - country-wise all commodities
  - region-wise
  - predefined and customised country groups
  - total trade
- **MEIDB (monthly):** https://tradestat.commerce.gov.in/meidb/commoditywise_export: "Data available: Jan 2018 to Jul 2026 ((R) Revised Final upto Mar 2026, (F) Final upto Jul 2026) Data last updated on: 16/09/2026".
- **Access method:** a Laravel HTML form POST with `_token` (CSRF) and a session cookie. There is no captcha and no login. A probe POST to `/eidb/country_wise_export` (year=2025, country=all, US$ mn) returned a 242-row HTML table. Quote: "India's Total Export 437704.58 [2024-25] 441452.14 [2025-26]" (US$ mn). No CSV/Excel button was found in the HTML (export may be client-side JS; **UNVERIFIED**).
- **Disclaimer (from page JS):** "The data refrenced in the system do not have any legal sanctity and is for general refrence only. The user may like to verify official publications for DGCI&S". Ownership: "Website belongs to Department of Commerce. Designed, Developed & Hosted by National Informatics Centre". Data Source: "DGCI&S, Kolkata".
- Help text: "ITC HS Code of the Commodity is from latest HS Code Directory provided by DGCIS Kolkata on April 2024 ... UNIT of the commodity may be changed from April 2024". The page banner says "ITC HS Code of the Commodity is either dropped or re-allocated and the unit of the commodity may be changed from April 2026". There is a classification break at April 2026.
- **Licence:** none stated on TradeStat. The underlying DGCI&S policy applies (§17).

## 17. DGCI&S (dgciskol.gov.in) and its Foreign Trade Data Dissemination Portal

- https://www.dgciskol.gov.in/ (200):
  - "Latest Finalised Export and Import Data upto June, 2026 is uploaded in the Data Dissemination Portal"
  - "Latest Principal Commodity (PC) level Export and Import Data upto June, 2026"
  - "Laspeyres Indices of April 2026- June 2026 with Base 2022-23 New!" (a new trade-index base, 2022-23)
  - "Report of the committee on Base year Revission for Merchandise Trade Indices"
  - Quarterly Review Oct-Dec'25
  - ITC-HS 2003/2007/2012/2017 classification links
- Portal https://ftddp.dgciskol.gov.in/dgcis/ (200):
  - User groups GUEST / OFFICIAL / SUBSCRIBER, with captcha/OTP login.
  - "Now Foreign Trade Data can be purchased by logging in this protal as Guest User Group. Principal commodity level data can now be accessed free of cost".
  - Notice: "the State & District data at Principal Commodity level for July, 2026 could not be published".
- **Data Dissemination Policy** (https://www.dgciskol.gov.in/Writereaddata/Downloads/Data_dissemination_policy1.pdf, 200, 4 pages):
  - "The copyright of trade data is reserved by DGCIS, Kolkata and no part of the data ... except small portions for other than commercial purposes with appropriate acknowledgement to DGCIS, shall be reproduced or re-disseminated, without obtaining prior permission from Director General, DGCIS."
  - "Principal commodity level data for the past 24 months are also disseminated free of cost to private users".
  - "All private users are required to make payment ... Rs. 1.00 for each record/row".
  - "Annual Bulk Data ... INR 350,000/- per year". There is a 60% academic discount.
  - "DGCIS allows the use of trade data within data extraction and/or visualization/analytical applications, either free of charge or with fees. In both cases, a written permission from the Director General, DGCIS is necessary and a royalty fee may be applied. Permission will be granted without royalty fee if the amount of data used does not exceed 1000 records." and "If data being re-disseminated are substantially different from the data provided by DGCIS, then no royalty fee is required."
- Copyright page https://www.dgciskol.gov.in/copyright.aspx: footer reads "© Copyright reserved by Directorate General of Commercial Intelligence and Statistics". The body text could not be isolated from the navigation.
- robots.txt returns 404.
- **Services:** https://www.dgciskol.gov.in/Services_Trade.aspx lists "Report on Service Exports Reporting Form for 2024-25" (SERF). This is a firm-level services export survey, distinct from RBI BoP.
- **Merchandise trade quick estimates:** Ministry of Commerce/PIB monthly around the 15th. August 2026 merchandise exports were US$ 43.81 bn, per Forbes India (search result). The PIB release itself was not fetched: **UNVERIFIED**.

## 18. International sources (cross-checks and gaps)

- **UN Comtrade:** the public preview API needs no key and works.
  - `https://comtradeapi.un.org/public/v1/getDA/C/A/HS?reporterCode=699` shows the India annual HS (H6) datasets. Quote: "2025 H6 1597367 [records] ... lastReleased 2026-07-10".
  - Monthly: `preview/C/M/HS?...period=202606` returned the June 2026 record. **Calendar-year** basis (not FY), CIF imports.
  - Services (EBOPS 2010) for India only go to 2023 (`getDA/S/A/EB`).
  - Re-dissemination FAQ https://uncomtrade.org/docs/faqs-on-use-and-re-dissemination/ (WebFetch): "A not-for-profit data visualization system can present actual figures of UN Comtrade". "Transformed data from UN Comtrade is no longer subject to copyright restrictions". Original data above 100,000 records to non-subscribers needs a licence fee. A free API key gives "500 API calls per day" and "100K records per call" (search snippet).
- **IMF data API:** https://api.imf.org/external/sdmx/2.1/dataflow/all/all/latest returns 200 with no key.
  - Relevant dataflows: `IMF.STA:BOP(21.0.0)`, `IIP(13.0.0)`, `IRFCL`, `IMTS`, `ITG`, `IMF.RES:ITS`, `PIP` ("formerly CPIS"), `DIP` ("formerly CDIS"), `IIPCC`, plus monthly vintages (BOP_2026_MAY_VINTAGE and others).
  - `data/IMF.STA,BOP/IND....Q?startPeriod=2025` returned 777 series through **2026-Q2**. CAB 2026-Q2 = −4.219 bn US$ (matches RBI −4.2). CAB 2026-Q1 = +6.49 bn against RBI Q4 2025-26 +7.1 bn, so the IMF holds a different vintage. The IMF uses calendar quarters and years.
  - data.imf.org and the imf.org terms page return **HTTP 403** to curl/WebFetch.
  - IMF terms per search snippet (imf.org/en/about/copyright-and-terms): data free of charge, reuse with attribution "Source: International Monetary Fund, Database Name, <<link>>", and material transformations must be stated. Medium confidence.
- **World Bank:** the API is open. WDI licence is CC BY 4.0 per WB summary terms. That licence was not re-fetched this session (https://datacatalog.worldbank.org/public-licenses returned 200 but was not parsed).
- **data.gov.in (OGD, NDSAP/GODL):** per search, it has "Principal Commodity wise Export/Import" and "Country-wise India Exports by Principal Commodity" catalogs contributed by the Department of Commerce, and an "Overall Balance of Payments" catalog. **Not fetched:** https://www.data.gov.in/robots.txt says "User-agent: * Disallow: /". The sanctioned route is the api.data.gov.in API with a free key. This is an access request. If the Commerce datasets there are under GODL, they may be the cleanest-licensed partner × product trade data, but vintage and coverage are **UNVERIFIED**.

## 19. GDP base-year context (for this family)

- MOSPI new series base 2022-23. Per WebSearch results: "PRESS NOTE ON NEW SERIES OF GDP ESTIMATES WITH BASE YEAR 2022-23" at mospi.gov.in/uploads/latestReleases/..._27022026.pdf, released 27 Feb 2026, plus a Q1 2026-27 GDP press note.
- Direct curl/WebFetch of mospi.gov.in: **HTTP 403**. This is **UNVERIFIED by fetch**; the national-accounts agent should confirm.
- Implication for external data: BoP and IIP are current-price US$/₹ flows and stocks, with no base year. Only the "% of GDP" ratios depend on the GDP series (see §0.8). Trade unit-value/volume indices now have a 2022-23 base at DGCI&S. HBS T122/123 still use a 2012-13 base.

## 20. Failures and blocks log

| URL | Result |
|---|---|
| https://rbidocs.rbi.org.in/rdocs/content/docs/BOPS01092026_1.xlsx (and _2) | 200 but HTML with a `TSPD` JS bot challenge (47 KB), not xlsx. Same with a Referer header (curl returned 000 on retry). |
| https://rbidocs.rbi.org.in/rdocs/PressRelease/PDFs/PR101567BB18EC850443F3A88FBB19188FF0FA.PDF | curl: 200 HTML challenge. WebFetch: "CAPTCHA Verification Form ... support ID 679480896855011786". |
| https://www.rbi.org.in/robots.txt | "Unauthorised Access ... Support ID: 679480896859709071" |
| https://dbie.rbi.org.in/ | TLS SEC_E_WRONG_PRINCIPAL (certificate name mismatch); with -k it redirects to data.rbi.org.in/DBIE |
| https://www.dpiit.gov.in/publications/fdi-factsheet | curl 200, 7 KB JS shell only; WebFetch HTTP 403 |
| https://www.mospi.gov.in/uploads/latestReleases/...27022026.pdf | curl 403 (185 bytes); WebFetch 403 |
| https://data.imf.org/ , https://www.imf.org/en/about/copyright-and-terms | 403 |
| https://uncomtrade.org/docs/policies/ | 404 (the FAQ page worked instead) |
| https://www.commerce.gov.in/terms-conditions/ , /copyright-policy/ | 404 (guessed URLs) |
| https://www.data.gov.in/* | not fetched: robots.txt Disallow: / |

## 21. Reference-year view from the external sector

- **2025-26 is fully covered on the external side:**
  - annual BPM6 BoP in US$ and ₹ crore (HBS T126/T127, Preliminary)
  - IIP and external debt at end-March 2026
  - FY 2025-26 merchandise trade by HS × country (TradeStat EIDB)
  - services by category (HBS)
  - FDI by country (DPIIT March 2026 factsheet)
  - software exports by destination (2025-26 survey)
  - MF FLA 2025-26
  - FLA census: 2024-25 only, with 2025-26 expected around Oct 2026
  - remittance source shares: 2023-24 only (6th round)
- **2024-25** has "Partially Revised" BoP, the FLA census 2024-25 and the FY 2024-25 trade data. It is more stable on vintage.
- **Recommendation for this block:** 2025-26 is feasible, with 2024-25 as a fallback if production, FoF or government blocks stop at 2024-25. **Do not use 2026-27:** it is incomplete, and the FCNR(B) swap window and oil shock distort it.
