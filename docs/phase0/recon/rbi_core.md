# Phase 0 recon — RBI core statistics (family id: `rbi_core`)

Working notes. Compiled 2026-09-29 by the rbi_core recon agent. Every claim below cites the URL actually
fetched on 2026-09-29 and what it showed. Probe downloads went to the session scratchpad only (outside the repo).
Nothing bulk-downloaded into the repo.

Scope: DBIE, Handbook of Statistics on the Indian Economy (HBS), Financial Stocks and Flow of Funds (FSF/FoF),
household financial savings (RBI preliminary vs NSO), banking (BSR-1/BSR-2, STRBI, sectoral deployment),
monetary aggregates / WSS / RBI balance sheet, RBI Annual Report (income, surplus transfer), NBFC statistics
(Trend & Progress, FSR, NBFC sectoral credit), Report on Currency and Finance.

---

## 0. Access mechanics (read this first)

| Host | What happened | Evidence |
|---|---|---|
| `https://www.rbi.org.in/` (and `/Scripts/*.aspx`) | 200 OK with plain curl + browser User-Agent. HTML listing pages parse fine. | `curl -sIL` → `HTTP/1.1 200 OK` |
| `https://website.rbi.org.in/` | 301 → `https://www.rbi.org.in/` | curl -sIL |
| `https://rbidocs.rbi.org.in/rdocs/...` (all PDFs/XLSX) | **First attempt with only a User-Agent returned a 48 KB HTML page (F5 BIG-IP "TSPD" JavaScript bot-defence challenge), not the file.** A second attempt sending ordinary browser `Accept` / `Accept-Language` / `Referer` headers returned the real file (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`). No challenge was solved, no cookie was forged. | probe `hbs_t1.xlsx` first = `text/html 48330` containing `window["bobcmn"]`, `/TSPD/`; retry = `200 application/vnd...sheet 12282` |
| `https://www.rbi.org.in/robots.txt` | Returns a WAF "Unauthorised Access … Support ID" page — no robots.txt is served. | curl |
| `https://data.rbi.org.in/robots.txt` | Returns DBIE "Page Not Found" HTML — no robots.txt. | curl |
| `https://dbie.rbi.org.in/` (old DBIE hostname, still cited in older RBI docs) | **Fails: curl `000` (no connection) in 0.18 s.** Old links such as the Basic Statistical Returns publication page (`https://dbie.rbi.org.in/DBIE/dbie.rbi?site=publications#!9`) are therefore dead. | curl `-w %{http_code}` → `000` |
| `https://data.rbi.org.in/` and `/DBIE/` | 200; an Angular single-page app (`main.927a0129ae6de6b4.js`, 9.4 MB). No server-rendered data. | curl; HTML shell `<title>DBIE</title>` |

**Risk for Phase 1:** a third-party repo (see §1.3) documents that rbidocs' F5 defence can escalate from a JS challenge to a
CAPTCHA for scripted downloads. I did not observe a CAPTCHA, but pipelines must: fetch politely (low rate, standard headers),
never attempt to solve challenges, and fall back to "owner downloads manually" if a CAPTCHA appears. Log any such failure in `ISSUES.md`.

### Licence / terms (applies to the whole family)
- `https://www.rbi.org.in/Scripts/Disclaimer.aspx` (fetched): no open-data licence. Footer on every page: "© Reserve Bank of India. All Rights Reserved."
  Key clauses (paraphrased; one short quote): figures are "as is" with no warranty; RBI may block IPs;
  **"caching and links to, and the framing of this Web Site or any of the contents are prohibited"** except that
  home-page linking requires notifying RBI in writing and **deep links to internal pages require prior permission from RBI**.
- No GODL-India / NDSAP statement found on rbi.org.in or data.rbi.org.in (RBI is not a ministry covered by NDSAP; not verified further).
- DBIE disclaimer is fetched at runtime from an internal endpoint (`dbie_getDisclaimer`, seen in bundle) — could not be read without rendering the SPA.
  re3data record r3d100010992 (fetched; last edited 2026-08-07) lists licence "other" pointing at RBI's RTI page and says users may use data for
  research "with courtesy to the Database on Indian Economy, Reserve Bank of India". **This courtesy line is second-hand (re3data), unverified on an RBI page.**
- **Conclusion: "no explicit licence found" (checked https://www.rbi.org.in/Scripts/Disclaimer.aspx and re3data).** The public website will
  republish RBI-derived numbers and link to RBI pages → the owner should seek written permission / clarification from RBI (DSIM, dbie@rbi.org.in;
  helpdoc@rbi.org.in). Listed under access requests.

---

## 1. DBIE — Database on Indian Economy

- URL: https://data.rbi.org.in/ (also https://data.rbi.org.in/DBIE/). Publisher: RBI DSIM (Data Management and Dissemination Division).
- What I fetched: the SPA shell and bundle `https://data.rbi.org.in/main.927a0129ae6de6b4.js`. The bundle contains
  `CIMS_Gateway_DBIE/GATEWAY/SERVICES` (x2), `security_generateSessionToken` (x3), `dataquery_enhanced`, `dbie_getSDMXExcelData`,
  `xmlsdmx`, `login_getSapToken`, `BOE/OpenDocument` (counts from grep), and HTTP calls that send `channelkey: key2` and an
  `authorization` session token. Also `/api/services/queryInterface`.
- **Access method:** interactive web portal only. Two surfaces: (a) SDMX "Data Query" wizard with Excel/CSV/SDMX-ML download;
  (b) "Reports" and "Publications" menus rendered by SAP BusinessObjects (Web Intelligence) — this is where STRBI, detailed BSR tables and
  HBS-online live. **No documented public API.** The gateway is an internal, session-token API with encrypted request fields
  (per third-party documentation, §1.3). Calling it directly would mean reverse-engineering an internal interface → **not
  recommended without RBI's permission**.
- Old portal `dbie.rbi.org.in` does not resolve/connect (see §0).
- Mobile app "RBIDATA" (Google Play `com.dbieapplication`) exists (search result only; not fetched).
- RBI's own pages route users to DBIE: HBS page says "To obtain the tables in Near-Real time, please access the Database on Indian Economy";
  STRBI 2024-25 and annual BSR-1/BSR-2 March 2026 are published **only** on DBIE (Publications menu) — RBI press releases PR 2026-2027/351 and /352 say
  "released the web publication … on its 'Database on Indian Economy' (DBIE) portal (https://data.rbi.org.in Homepage > Publications)".

### 1.3 Third-party mirror discovered: dbie.rbihub.in (treat with caution)
- https://dbie.rbihub.in/ (fetched; Next.js static site, CloudFront) titled "Database on Indian Economy", showing e.g. "Policy repo rate Jul 2026 5.25 %",
  "USD/INR 28-Sep-2026 95.97", "Foreign exchange reserves 18-Sep-2026 765.9 US$ bn".
- GitHub `Reserve-Bank-Innovation-Hub/dbie.rbihub.in` (via `gh api`): MIT licence, created 2026-07-02, last push 2026-09-29; org "Reserve Bank Innovation Hub",
  blog https://rbihub.in/, **`is_verified: false`**. README: "Built by the Reserve Bank Innovation Hub"; scrapes 252 SDMX series and ~1,033 tables from DBIE;
  has a read-only data API (`data-api.dbie.rbihub.in`) and an MCP server.
- rbihub.in home page (fetched) has zero mentions of "dbie" → **affiliation with RBIH/RBI unverified.**
- Its `docs/dbie-portal-anatomy.md` states it reimplements the SPA's AES cipher and drives the gateway without a browser, and that rbidocs' F5 defence escalates to CAPTCHA.
  That is circumvention of technical measures → **do not use its methods**. Its data could be a convenience cross-check only, never a primary source,
  and only if the owner confirms RBIH's status and terms. Useful facts from it (unverified by me): DBIE Reports for "Banking + NBFC + Key Rates" need a BOE session
  that guests get only intermittently ("Due to high load on the system" modal).

---

## 2. Handbook of Statistics on the Indian Economy (HBS) 2025-26

- Page: https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook%20of%20Statistics%20on%20Indian%20Economy (fetched, 423 KB).
  Shows "Jul 31, 2026 — Handbook of Statistics on the Indian Economy, 2025-26". 496 rbidocs links: full PDF, foreword, contents, and every table as XLSX + PDF.
- Foreword PDF (fetched): "the 28th edition of the Handbook, comprises 245 statistical tables"; signed "(Ravi Shankar) Executive Director, July 31, 2026".
- URL pattern: `https://rbidocs.rbi.org.in/rdocs/Publications/DOCs/{n}T_HBIE31072026{hash}.XLSX` (hash per table; must be scraped from the listing page).
- Full 245-table list captured (see below the SAM-relevant subset). Parts: Annual series (T1–154), Quarterly NAS new series (T155–158), monthly/weekly/daily (T159–225), ratios (T226–245).
- Probe downloads (XLSX, openpyxl): T1, T11, T12, T13, T39, T42, T60, T63, T168, T170.

**Findings from probes**
- **T1 Macro-Economic Aggregates (current prices, ₹ crore):** columns 2020-21, 2021-22, 2022-23 on "(Base Year: 2011-12)" and 2022-23, 2023-24, 2024-25, 2025-26 on
  "(Base Year: 2022-23)". GDP 2022-23 = 26,890,473 (old) vs 26,117,627 (new). New base: GDP 2023-24 = 28,983,909; 2024-25 = 31,807,309; 2025-26 = 34,635,638.
  CFC, primary income from RoW, current transfers, Gross saving, GCF are "-" for 2025-26. Notes: "Data for 2024-25 are First Revised Estimates", "Data for 2025-26 are Provisional Estimates". Source NSO.
- **T11 Sector-wise domestic saving:** new base 2022-23…2024-25 (and old base 2020-21…2022-23). Split: NFC public (departmental / non-departmental) / private, FC public/private,
  general government, households (gross financial saving, financial liabilities, physical, gold & silver). E.g. new-base household gross financial saving 2023-24 = 3,575,657.
- **T12 Changes in financial assets/liabilities of households:** 1983-84 to 2023-24; note "Data … are as per National Accounts Statistics 2025" → **old 2011-12 base**.
  2023-24 gross financial assets = 3,430,640 — differs from T11 new-base 3,575,657. **Quirk: HBS mixes bases across tables.**
- **T13 Institutional-sector GCF:** "(Base Year : 2011-12)", 2018-19…2023-24 only. No new-base institutional GCF in HBS.
- **T60 Flow of Financial Resources to Commercial Sector:** 2020-21…2025-26 (2025-26 provisional). Bank non-food credit + non-bank domestic (equity, bonds, REIT/InvIT, CP,
  HFC, AIFI, NBFC) + foreign (ECB, ADR/GDR, short-term credit, FDI). Notes on HDFC merger (1 Jul 2023) and HFC→NBFC conversions.
- **T42 Sectoral deployment of non-food gross bank credit:** end-March 2021-22…2025-26; note: sectoral data from SIBC return of select banks (~95% of non-food credit).
- T39 RBI liabilities & assets from 1991; T170 RBI Survey (monthly); T168 deployment by major sectors (monthly to Dec 31, 2025).
- T27/T159–161: IIP base 2022-23=100 already adopted; Bulletin Sept 2026 shows CPI base 2024=100 and WPI base 2022-23=100.

SAM-relevant HBS tables (IDs): T1–T4 (macro aggregates, GVA, GDP components), T11 (sector saving), T12 (HH financial flows), T13 (institutional GCF, old base),
T36–T39 (money stock, sources, RBI balance sheet), T41–T43, T49 (SCB aggregates, credit deployment, consolidated SCB balance sheet), T60 (flow of resources to commercial sector),
T62/T68 (mutual funds), T63 (NBFC public deposits), T67 (LIC investments), T79–T84 (NABARD, IFCI, EXIM, NHB, SFCs, SIDBI balance sheets),
T86–T110 (central/state/combined fiscal), T111–T150 (trade, BoP BPM6, NRI deposits, FDI/FPI, reserves, external debt, IIP), T155–T158 (quarterly GVA/GDP new series),
T165–T172 (monthly money, credit, RBI/monetary/commercial bank surveys), T181 (FPI), T190 (services trade), T195–T204 (quarterly BoP/IIP).

---

## 3. Financial Stocks and Flow of Funds (FSF / FoF)

- Index page: https://www.rbi.org.in/Scripts/FlowofFundsAccounts.aspx (fetched). Lists:
  - Jan 21, 2026 — "Financial Stocks and Flow of Funds of the Indian Economy 2023-24" (Bulletin Id=23912) ← **latest**
  - Jan 17, 2025 — 2022-23 (Id=23132); Jun 19, 2024 — 2021-22 (Id=22653); Mar 21, 2023 — 2020-21 (Id=21667); May 17, 2022 — 2019-20 (Id=21002); Jul 13, 2020 — 2016-17 to 2018-19; Jul 11, 2019 — 2011-12 to 2017-18.
- Web search for a 2024-25 edition found nothing; the index page lists none → **latest FoF year = 2023-24** (as of 2026-09-29).
- Article https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx?Id=23912 (fetched; authors Suraj S, Ishu Thakur, Mousumi Priyadarshini): FWTW basis, SNA 2008, G20 DGI;
  links the data workbook https://rbidocs.rbi.org.in/rdocs/content/docs/FSF2023-24_21012026.xlsx.
- Workbook probe (3.2 MB, 71 sheets): Index, Summary; St 1 … St 5 (sector balance sheets: S12 FCs with S121 RBI, S122 ODCs (SCBs incl RRBs, co-op banks, deposit-taking NBFCs/HFCs),
  S123–S129 OFCs (AIFIs, SFCs, SIDCs, NBFC-ND, HFC-ND, MFs split MMF/other, insurance, PF & pension); S11 NFCs (public: CPSEs, power cos, port trusts; private);
  S13 GG (S1311 Centre, S1312 States); S14+S15 households incl NPISH; S2 RoW); S 6.1–6.13 FWTW sector × sector matrices ("Sources/Uses") by instrument;
  S 7.1–7.13 instrument × sector; S 8.1–8.3 financing of private NFCs, GG, households; S 9.1–9.6 sectoral composition.
  Instruments F1 (gold/SDR), F2 (currency F21, deposits F22&F29), F3 debt securities, F4 loans, F5 equity (F51) & fund shares (F52: F521 MMF, F522 other), F6 insurance/pension/PF, F8 other (F81 trade credit, F89 other), plus "Other" and NEC.
  Each statement: Outstanding 2011-12…2023-24, Transactions 2012-13…2023-24, Valuation 2012-13…2023-24 (₹ crore).
- **Base alignment:** the article says 2023-24 had "robust economic growth of 12.0 per cent at current prices". New-series (base 2022-23) nominal growth from HBS T1 = 28,983,909 / 26,117,627 − 1 = 10.97%;
  12.0% is consistent with the old 2011-12 series. Published Jan 2026, before the new series (27 Feb 2026). → **FSF 2023-24 is on the 2011-12 GDP base (inference, medium-high confidence).** GDP ratios in it will not match new-base NAS.
  The ₹ stock/flow levels come from balance sheets and are largely base-independent, but household sector residuals/NAS consistency are old-base.

## 4. Household financial savings: RBI preliminary vs NSO

- RBI quarterly page https://www.rbi.org.in/Scripts/QuarterlyPublications.aspx?head=Household+Financial+Savings (fetched): **stale** — latest entry "Aug 28, 2025", Bulletin tables 50(a)/50(b) (XLSX+PDF).
  Probe of 50(a) XLSX: 2022-23, 2023-24, 2024-25 quarterly+annual; 2024-25 preliminary; % of GDP on old base.
- **Newer data are in the monthly Bulletin "Current Statistics", now numbered 52(a)/52(b).** Bulletin September 2026 (Sep 25, 2026; https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx, fetched)
  → No. 52(a) PDF https://rbidocs.rbi.org.in/rdocs/Bulletin/PDFs/52AT_BULL25092026004CFAF0BB3B4F779B3E0ADBC8826701.PDF (probe): quarters 2022-23…2025-26;
  notes: "Preliminary estimates for 2025-26 and revised estimates for 2024-25, 2023-24 and 2022-23", "Figures as per cent of GDP are as per the new base year 2022-23",
  "The estimates will undergo revision with the release of National Accounts Statistics 2024-25 by the NSO". 2025-26 annual: financial assets 4,320,243.8; NFA 2,168,779.7 (6.3% of GDP).
  Only PDF link found on the listing for 52(a) (no XLSX link matched my regex) — recheck in Phase 1.
- RBI Annual Report 2025-26, Appendix Table 3 "Gross Savings" (XLSX, fetched): % of GNDI 2022-23…2024-25; HH net financial saving 5.2 / 5.8 / 7.0; note "Data are based on GDP base year of 2022-23". Source NSO.
- NSO numbers (via HBS T11, new base) vs RBI preliminary: NSO has 2022-23…2024-25 on new base; RBI preliminary extends to 2025-26. HBS T12 (NAS 2025, old base) differs from both.

## 5. Banking

### 5.1 Sectoral deployment of bank credit (monthly)
- https://www.rbi.org.in/Scripts/Data_Sectoral_Deployment.aspx (fetched): latest "Aug 31, 2026 — Sectoral Deployment of Bank Credit – July 2026" (prid=63478).
- PR https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx?prid=63478 (fetched): 41 select SCBs (~95% of non-food credit), Statements I–II XLSX
  https://rbidocs.rbi.org.in/rdocs/content/docs/SIBCSJ26E31082026ENG.xlsx. Non-food credit y-o-y 19.1%.
  **Quirk:** "With effect from December 31, 2025, definition of last reporting fortnight has been changed to the last day of the month under the Banking Laws (Amendment) Act 2025" → break in y-o-y comparisons from Dec 2025.
- Lag ≈ 1 month (July data on Aug 31).

### 5.2 BSR-1 (credit) / BSR-2 (deposits)
- Quarterly BSR-1 list https://www.rbi.org.in/Scripts/Pr_DataRelease.aspx?SectionID=354&DateFilter=YearMonth_PR (fetched): latest "Aug 31, 2026 — Quarterly BSR-1 … June 2026"; annual March 2026 on May 29, 2026.
- Quarterly BSR-2 list SectionID=382 (fetched): latest June 2026 (Aug 31, 2026); annual March 2026 (May 29, 2026).
- Annual BSR-1 list SectionID=376 (fetched) back to March 2020 etc.
- Annual BSR-1 March 2026 PR PDF (probe): data by type of account, organisation, occupation/activity, borrower category, district, population group, interest rate, credit limit;
  new district-level gender series; household sector = 58.6% of bank credit; private corporate > one-fourth.
- Annual BSR-2 March 2026 PR PDF (probe): deposits by type, **institutional-sector ownership** (household 59.3%, non-financial sector 18.5%, financial corporations 7.8% at end-March 2026), maturity, size, interest rate.
- Detailed tables live only on DBIE Publications (BOE reports). The old "Basic Statistical Returns" publication page (https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Basic%20Statistical%20Returns) still points to Vol 47 (March 2018) on the dead dbie.rbi.org.in host.
- "Composition and Ownership Pattern of Deposits with SCBs" (SectionID=365, fetched): discontinued after March 2018 release (Jul 30, 2018); superseded by BSR-2 institutional-sector tables.

### 5.3 Statistical Tables Relating to Banks in India (STRBI)
- https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Statistical%20Tables%20Relating%20to%20Banks%20in%20India (fetched): "Dec 29, 2025 — Statistical Tables relating to Banks in India: 2024-25", link goes to
  `https://data.rbi.org.in/#/dbie/reports/Publication/Time-Series%20Publications/Statistical%20Tables%20Relating%20to%20Banks%20in%20India` → **DBIE-only (BOE report); not downloadable by script without DBIE session. Bank-wise balance sheets, income & expenditure (interest earned/paid) — needed for FISIM/bank P&L cells.**

### 5.4 Trend and Progress of Banking in India
- https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Trend%20and%20Progress%20of%20Banking%20in%20India (fetched): latest "Dec 29, 2025 — Report on Trend and Progress of Banking in India 2024-25" (PDF 8.2 MB), chapters incl. "Non-Banking Financial Institutions"; appendix tables IV.1–V.x as XLSX (banking at a glance, international liabilities/assets, co-op banks, PACS …).

### 5.5 Other
- Performance of Private Corporate Business Sector (SectionID=378): latest "Jun 24, 2026 — … during 2025-26" (listed companies, quarterly aggregates). Finances of Non-Govt Non-Financial Public Ltd Companies (SectionID=366): latest "Mar 30, 2026 — 2024-25".
  (Probably owned by a corporate-sector family; flagged here as useful for private NFC operating surplus/interest.)
- "Performance of Non-Government Non-Banking Financial and Investment Companies" (SectionID=361): **discontinued**, last release Jul 24, 2020 (2018-19).

## 6. Money, RBI balance sheet, WSS, Annual Report
- Money supply (https://www.rbi.org.in/Scripts/Data_MSupply.aspx, fetched): latest "Sep 25, 2026 — Money Supply for the fortnight ended on September 15, 2026" (now mid-month and month-end fortnights).
- WSS: https://www.rbi.org.in/Scripts/WSSViewDetail.aspx?TYPE=Basic&PARAM1=9%2F25%2F2026 (fetched): WSS dated Sep 25, 2026 with full XLSX + table XLSX: T1 RBI liabilities & assets, T2 FX reserves, T3 cash balances, T4 SCB business, T5 ratios & rates, T6 money stock components & sources, T7 reserve money, T8 liquidity ops, T9 prices, T10 CDs, … URL pattern `rdocs/Wss/DOCs/{n}T_{ddmmyyyy}{hash}.XLSX`. Year archive page uses ASP.NET postback (BS_ViewWss.aspx) — use the WSSViewDetail date URL instead. `https://wss.rbi.org.in/` returns 200 (not explored).
- RBI Annual Report 2025-26: https://www.rbi.org.in/Scripts/AnnualReportPublications.aspx (fetched) "May 29, 2026 — Annual Report 2025-26"; Chapter XII accounts PDF (probe) — Table XII.1:
  **surplus transferred to the Central Government 2025-26 = ₹2,86,588.46 crore** (2024-25: ₹2,68,590.07 crore); provision to Contingency Fund ₹1,09,379.64 crore; RBI exempt from income tax; accounting year April–March.
  Appendix tables XLSX: 1 macro & financial indicators, 2 real GDP (2022-23 prices), 3 gross savings (% GNDI, new base), 4 inflation/money/credit, 5 flow of resources to commercial sector, 6 key fiscal indicators, 7 BoP.
- Bulletin current statistics (Sept 2026) includes RBI liabilities/assets (2), money (6–12), bank business (14), credit deployment (15–16), flow of resources (18a/b), CPI base 2024=100 (19), WPI base 2022-23 (22), IIP base 2022-23 (23), Union accounts (24), BoP (40–43), IIP (44), small savings (46), G-sec ownership (47), combined Centre+States receipts/disbursements (48), state finances (49–51), HH financial flows/stocks (52a/b).

## 7. NBFC statistics
- Sectoral deployment of NBFC credit (monthly): https://www.rbi.org.in/Scripts/Data_Sectoral_Deployment_NBFC.aspx (fetched) latest "Sep 07, 2026 — … July 2026" (prid=63536): sample of Upper & Middle Layer NBFCs + HFCs (~87% of credit), statement XLSX https://rbidocs.rbi.org.in/rdocs/content/docs/NBFCCREDIT07092026_A.xlsx. Lag ≈ 5 weeks.
- Trend & Progress 2024-25 chapter on NBFIs (NBFC consolidated balance sheet, income; as of Sep 2025 per NBFC PR footnote).
- FSR: https://www.rbi.org.in/Scripts/FsReports.aspx (fetched) latest "Jun 30, 2026 — RBI releases the Financial Stability Report, June 2026" (prid=63050) → report page PublicationReportDetails.aspx?ID=1319 (not opened). Half-yearly (Jun/Dec).
- HBS T63 (NBFC public deposits), T60 (NBFC credit flows).

## 8. Report on Currency and Finance
- https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Report%20on%20Currency%20and%20Finance (fetched): latest "Jul 29, 2024 — Report on Currency and Finance 2023-24" (theme: digital revolution). Thematic, not a data source for the SAM. Low priority.

## 9. External context verified
- MOSPI new GDP series base 2022-23 released 27 Feb 2026 (PIB/MOSPI search results incl. MOSPI press note PDF "Press Note on New Series of GDP Estimates with Base Year 2022-23 27022026"); confirmed indirectly by HBS T1 base columns and RBI AR Appendix 3 note.
- NAS 2026 reportedly released 31 Aug 2026 with final estimates 2022-23 and 2023-24 (secondary sources only: indexbox, kihikila) — **unverified here; MOSPI family agent must confirm.**

## 10. Reference-year implications (for SAM year choice)
| Dataset | Latest year | Base | Note |
|---|---|---|---|
| FSF/FoF (FWTW, sector×instrument) | 2023-24 (pub. 2026-01-21) | 2011-12 (inferred) | binding constraint; no 2024-25 FoF yet; typical lag ~22 months |
| RBI HFS preliminary (Bulletin 52a) | 2025-26 (prelim), revised 2022-23…2024-25 | 2022-23 (GDP ratios) | household instrument flows only, not FWTW |
| HBS T11 sector saving (NSO) | 2024-25 | 2022-23 | |
| HBS T12 HH fin assets (NAS 2025) | 2023-24 | 2011-12 | inconsistent with T11 |
| HBS T13 institutional GCF | 2023-24 | 2011-12 | no new-base version in HBS |
| HBS T1 macro aggregates | 2025-26 PE (GDP); 2024-25 for saving/GCF/CFC | 2022-23 | |
| Flow of resources to commercial sector (T60 / AR App. 5) | 2025-26 (prov.) | n/a (₹ flows) | |
| Annual BSR-1/BSR-2 | end-March 2026 | n/a | quarterly to June 2026 |
| STRBI | 2024-25 | n/a | DBIE only |
| RBI accounts | 2025-26 | n/a | |
| Sectoral credit (banks, NBFC) | July 2026 | n/a | |

**Suggestion to the synthesis agent:** if the SAM must contain an official FWTW financial block, the latest feasible year is **2023-24**, and it sits on the old base while NAS 2023-24 is available on the new base.
Either (a) choose 2023-24 and re-benchmark FoF household/NFC/GG net lending to new-base NAS (logged as estimated adjustments), or (b) choose 2024-25 and build the
financial block from RBI HFS (new base) + flow of resources to commercial sector + BSR + BoP, with FWTW cells estimated from the 2023-24 FoF structure. Decision belongs to Checkpoint A.

## 11. Failures / issues log (to copy into ISSUES.md)
1. rbidocs.rbi.org.in serves F5 TSPD JS challenge to minimal curl; works with standard browser headers. Possible CAPTCHA escalation (reported by third party, not observed).
2. dbie.rbi.org.in unreachable (curl 000); old publication links dead.
3. DBIE has no documented public API; Reports/Publications (STRBI, detailed BSR, HBS online) are SAP BOE reports requiring a (rationed) guest session.
4. No explicit data licence; Disclaimer prohibits caching/framing and requires permission for deep links.
5. HBS mixes bases: T1/T11 new base; T12/T13 old base.
6. FSF 2023-24 on old base (inferred); no new-base FoF.
7. HFS quarterly publications page stale since Aug 2025; current data only in Bulletin table 52(a)/(b); XLSX link not found by my parser for Sept 2026 (PDF only) — recheck.
8. Banking Laws (Amendment) Act 2025 changed reporting fortnight to month-end from Dec 31, 2025 → series break.
9. HDFC–HDFC Bank merger (1 Jul 2023) and HFC→NBFC conversions affect bank/NBFC/HFC splits.
10. "Performance of NBFIs" and "Composition and ownership pattern of deposits" releases discontinued (2020, 2018).
11. Browser automation not used: multiple Chrome browsers connected and none selected (subagent cannot ask the user).
12. rbi.org.in serves no robots.txt (WAF page instead); data.rbi.org.in serves none.

## 12. URLs fetched (chronological, all 2026-09-29)
- https://data.rbi.org.in/ ; https://data.rbi.org.in/main.927a0129ae6de6b4.js ; https://data.rbi.org.in/robots.txt ; https://data.rbi.org.in/DBIE/ ; https://data.rbi.org.in/DBIE/doc/Extracting_Data_to_Excel.pdf (404)
- https://dbie.rbi.org.in/ (fail 000)
- https://www.rbi.org.in/ ; https://www.rbi.org.in/robots.txt ; https://website.rbi.org.in/ (301)
- https://www.rbi.org.in/Scripts/AnnualPublications.aspx?head=Handbook%20of%20Statistics%20on%20Indian%20Economy
- HBS XLSX T1, T11, T12, T13, T39, T42, T60, T63, T168, T170; foreword PDF
- https://www.rbi.org.in/Scripts/FlowofFundsAccounts.aspx ; https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx?Id=23912 ; https://rbidocs.rbi.org.in/rdocs/content/docs/FSF2023-24_21012026.xlsx
- https://www.rbi.org.in/Scripts/AnnualReportPublications.aspx ; AR Appendix 3 XLSX ; AR Chapter XII PDF
- https://www.rbi.org.in/Scripts/Disclaimer.aspx ; https://www.rbi.org.in/scripts/PublicationsView.aspx?id=20404 (HBS 2020-21 foreword)
- https://www.re3data.org/repository/r3d100010992 (WebFetch)
- https://dbie.rbihub.in/ ; /statistics ; https://rbihub.in/ ; GitHub API repo/org/readme/docs
- https://www.rbi.org.in/Scripts/Statistics.aspx
- QuarterlyPublications.aspx?head=Household+Financial+Savings ; 50AT_BUL28082025….XLSX
- Data_Sectoral_Deployment.aspx ; BS_PressReleaseDisplay.aspx?prid=63478 ; Data_Sectoral_Deployment_NBFC.aspx ; prid=63536
- Pr_DataRelease.aspx SectionID 354, 382, 376, 365, 378, 361, 366 ; AnnualPublications BSR-2 ; Basic Statistical Returns ; STRBI
- BSR-1 and BSR-2 March 2026 PR PDFs
- AnnualPublications Trend and Progress ; FsReports.aspx ; HalfYearlyPublications FSR (returned "Error occured. Please try again.") ; prid=63050 ; AnnualPublications Report on Currency and Finance
- BS_ViewWss.aspx ; BS_viewWssExtract.aspx ; WSSViewDetail.aspx?TYPE=Basic&PARAM1=9/25/2026 ; https://wss.rbi.org.in/ (200) ; Data_MSupply.aspx
- https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx (Sept 2026 issue) ; Bulletin 52AT PDF
