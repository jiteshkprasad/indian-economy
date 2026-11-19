# Phase 0 recon — MOSPI National Accounts (family id: `mospi_nas`)

Working notes. Retrieval date for everything below: **2026-09-29** (live fetches from this session).
Probe files were saved only to the session scratchpad (outside the repo); nothing was written to `data/`.

---

## 0. Headline findings (read this first)

1. **The GDP base year is now 2022-23.** MOSPI released the new series (base 2022-23) on **27 Feb 2026**, replacing base 2011-12. It was **updated on 31 Aug 2026** to take in the new PPI, IIP and BkSPI (all base 2022-23, released June 2026). That update was published as **National Accounts Statistics (NAS) 2026**.
2. **The new series only goes back to 2022-23.** It has annual data for 2022-23 to 2025-26 and quarterly data from Q1 2022-23 to Q1 2026-27. **No back series has been published yet.** MOSPI says it is "expected to be released by December 2026" (Feb-2026 press note and FAQ). A BusinessLine headline dated 21 Sep 2026 says "likely by year-end". MOSPI's latest-release list, checked up to 28 Sep 2026, shows no back-series release.
3. **NAS 2026 detail covers only three years:** 2022-23 (Final), 2023-24 (Final) and 2024-25 (First Revised Estimate, FRE). For 2025-26 there are **Provisional Estimate (PE) aggregates only**: Statements 8.17.1 and 8.17.2.
4. **Statistical discrepancy has changed.** In the new series, current-price GDP from production equals GDP from expenditure: the discrepancy is **0 in 2022-23 and 2023-24 (Final)**. The discrepancy is balanced away inside the Supply-Use Table (SUT) framework rather than shown. It is still non-zero at constant prices, in the latest estimates (2024-25 FRE: -1,07,438 crore at current prices; 2025-26 PE: -1,18,500 crore) and in quarterly data. In the old series it was large: 2022-23 was -4,74,817 crore (-1.8% of GDP) in NAS 2025.
5. **Full institutional sequence of accounts is missing on the new base.**
   - NAS 2024 (old base) had full sequences of accounts for 2011-12 to 2022-23: Statement 1.15 for the total economy, Ch. 2 for non-financial corporations (2.0-2.2), Ch. 3 for financial corporations (3.0-3.2), 4.0 for general government, 5.0 for households and 6.0 for the rest of the world. These run production → generation of income → allocation of primary income → secondary distribution → use of income → capital account.
   - **NAS 2025 and NAS 2026 dropped all of these statements.** NAS 2026 gives only Statement 1.14 ("Institutional Sectoral Accounts – Key Economic Indicators": GVA, GDI, final consumption, saving, GCF and CFC by sector), Statement 1.9 (saving by institution) and Statement 5.3 (household financial assets and liabilities).
   - MOSPI's own *Sources and Methods* (21 Sep 2026, §30.7) says the NAS publication contains these sequence-of-accounts chapters. The published NAS 2026 does not. This is a documented gap for the SAM.
6. **Access:** NAS data are open access with no registration: "Category A (open access data)… (i) Data relating to National Accounts" (GSDD 2026 Gazette notification). Sources:
   - NAS 2026 as per-statement XLSX files;
   - a public no-key REST API (`api.mospi.gov.in/api/nas/getNASData`) for headline aggregates;
   - the eSankhyiki portal (a JavaScript front-end on the same API).

---

## 1. URLs fetched and what they showed

### 1.1 Base-year revision / release notes

| URL | Result | What it showed |
|---|---|---|
| WebSearch "MOSPI new GDP series base year 2022-23 released February 2026" | ok | Found the Feb-2026 press note, the FAQ and the Q1 2026-27 press note |
| `https://www.mospi.gov.in/uploads/latestReleases/latest_release_1772189865181_..._27022026.pdf` (original press-note URL from search) | **HTTP 403** (nginx "403 Forbidden", 185 bytes) | The file was replaced. The current copy is the "-F" URL below. MOSPI returns 403 (not 404) for missing files under `/uploads/` |
| `https://www.mospi.gov.in/uploads/latestReleases/latest_release_1781177791292_..._27022026-F.pdf` | 200, 62 pp | "Press Note on New Series of GDP Estimates with Base Year 2022-23". Part A: SAE 2025-26 and quarterly Q1 2022-23 to Q3 2025-26. Part B: annual 2022-23 to 2024-25. Part C: back-series plan. Quote: "Back series is expected to be released by December 2026." Also: "Lower Discrepancy: Supply Use Table Framework will be integrated with National Accounts Framework". Old vs new GDP 2022-23: 2,68,90,473 → 2,61,17,627 crore (-2.9%) |
| `.../latest_release_1781177791447_..._Part_A_Statements.xls` | 200 (141 KB xls) | Statements accompanying the Feb press note (not parsed in detail) |
| `https://www.mospi.gov.in/uploads/announcements/announcements_1772117257791_..._FAQ_GDP_26022026_1902.pdf` | 200 | FAQ Q5: "The back series is expected to be released by December 2026… extended back to 1950-51 using… splicing". FAQ Q17: the SUT "matches what is produced with how it is used and mismatches… are adjusted and therefore, discrepancy is minimized/eliminated." Also: India will move to SNA 2025 at the *next* base revision |
| `.../latest_release_1780655857536_..._PE_FY_2025-26_F.pdf` (+ `Statements.xls`) | 200 | PE 2025-26 and Q4 2025-26, released **5 Jun 2026** |
| `.../Press%20Note_Release%20Calendar%20Change.pdf` | 200 | Dated 12 May 2026: the PE and Q4 release moved "from last working day of May to 7th June… of every year" |
| `.../latest_release_1788171660220_..._Final_Press_Release_on_NAS_2026.pdf` | 200, 4 pp | Dated 31 Aug 2026: "released the 'National Accounts Statistics – 2026' publication for the base year 2022-23… sixty statements based on the updated Final Estimates for… 2022–23 and 2023–24, and First Revised Estimates for 2024–25". Also: "four statements on updated Provisional Estimates of GDP for… 2025-26 and the quarterly estimates… 2022-23 to 2025-26". Revised GDP: 2022-23 2,61,77,001; 2023-24 2,90,73,287; 2024-25 3,17,98,524; 2025-26 (PE) 3,45,36,796 crore |
| `.../latest_release_1788172583113_..._Q1_2026-27.pdf` | 200, 12 pp | Q1 2026-27 GDP released 31 Aug 2026: nominal 88.27 lakh crore, real 81.36 lakh crore. "Next release… Q2… scheduled on 30th November, 2026" |
| `.../latest_release_1788359345406_..._Press_Release_Page___Press_Information_Bureau.pdf` (PIB PRID 2305896) | 200 | Q&A dated 2 Sep 2026: "At the time of release of final estimates at current prices, the discrepancies will be very insignificant or zero as was found in case of FY2022-23 and FY 2023-24." It also explains negative manufacturing deflators under double deflation |
| `.../latest_release_1789988911616_..._Sources_and_Methods...pdf` | 200 | Dated 21 Sep 2026: *Sources and Methods for Compilation of NAS* released. "eighth base year revision" |
| `https://www.mospi.gov.in/uploads/documents/pressRelease/1789976245319-Sources%20and%20Methods%20for%20Compilation%20of%20National%20Accounts%20Statistics.pdf` | 200, 3.8 MB | §23.4: "the statistical discrepancy between production side and expenditure side estimates of GDP has been made '0' at current prices". §30.7 describes NAS Chapters 2-6 as containing sequences of accounts (contradicts NAS 2026 contents). §30.10: the back-series methodology "is documented separately" |
| `https://www.mospi.gov.in/uploads/documents/releaseCalender/1788266096813-ARC 2026-27 updated till August 2026.pdf` (via API `documents/get-latest-release-calender`) | 200, 8 pp | Upcoming dates: 30 Nov 2026 Q2 GDP; **7 Jan 2027** FAE 2026-27; **26 Feb 2027** SAE 2026-27 + Q3 + "First Revised Estimates of GDP for FY 2025-26 and Final Estimates of GDP for FY 2024-25". No back-series or NAS-publication date is listed |
| WebSearch "MoSPI back series GDP base 2022-23 release 2026" | ok | PressReader/BusinessLine, 21 Sep 2026: "Release of pre-FY23 GDP back series likely by year-end: MoSPI Secretary" (headline only; paywalled, not opened) |

### 1.2 NAS publications (the MOSPI site is a React SPA; data comes from its public JSON API)

- `https://mospi.gov.in/publications-reports/innerpage/2861` returns only an SPA shell (2.6 KB, `<div id="root">`), so it cannot be scraped as HTML.
- The bundle `/assets/index-FXIi3u1F.js` shows the API base `https://www.mospi.gov.in/api/`. The page itself calls `POST publications-reports/get-web-chapter-data {publication_id, lang, page_no, page_size}`. I used the same public call a browser makes; no login or token is involved.
- `POST .../publications-reports/get-web-publications-report-list` (search "National Accounts") returned:
  - 2865 "Sources and Methods…" (2026-09-21)
  - **2861 "National Accounts Statistics 2026" (2026-08-31)**
  - 432 NAS 2025 (2025-06-26)
  - 434 NAS 2024 (2024-06-05)
  - 435 NAS 2023
  - 436 NAS 2022
  - 844 NAS 2021
- NAS 2026 chapter list (publication 2861):
  - Abbreviations; Ch 1 (1.1, 1.2, 1.4–1.14; **no 1.3, no 1.15**); Ch 4 (4.1, 4.2); Ch 5 (5.1–5.3); Ch 6 (6.1, 6.2); Ch 7 (7.1–7.4C); Ch 8 (8.1.1–8.18.2).
  - **No Ch 2 or Ch 3.** No "all statements" workbook.
  - Files: `https://www.mospi.gov.in/uploads/publications_reports/NAS-2026-Statements/<id>.xlsx`. All 32 probed returned 200 (XLSX, 20–110 KB), `Last-Modified: Mon, 31 Aug 2026`.
  - `1.3`, `1.15`, `2.0`, `2.1`, `3.0`, `4.0`, `5.0` and `6.0` under NAS-2026 return **403**, meaning they do not exist.
- NAS 2025 (publication 432, old base 2011-12): same chapters as 2026 (1, 4, 5, 6, 7, 8). The same sequence-of-accounts files return **404** under `/NAS2025/`.
- NAS 2024 (publication 434, old base): the sequence-of-accounts files `1.15, 2.0–2.2, 3.0–3.2, 4.0, 5.0, 6.0` and `NAS2024_All_Statements.xlsx` all exist (**200**). The files under `/NAS2024/` confirmed 200 are `1.3, 1.15, 2.0, 2.1, 3.0, 4.0, 5.0, 6.0`. `5.0` = "Sequence of Accounts - Households", 2011-12 … 2022-23, with SNA codes P1, P2, B1g, D1, D29…
- SUT publication (847): lists "Supply Use table 2022-23" and "…2023-24" (new base) plus old SUTs 2011-12 … 2021-22 (another agent's family; noted here because the SUT is what now sets the discrepancy to zero). The NAS 2026 press release (¶9) says the SUTs for 2022-23 and 2023-24 "have also been updated". The SUT release dated 15 May 2026 appears in the latest-release list.

### 1.3 Probe contents of NAS 2026 statements (all ₹ crore; years 2022-23 | 2023-24 | 2024-25)

- **1.1 Key aggregates** (current and constant 2022-23 prices):
  - GVA 2,38,23,136 | 2,64,05,480 | 2,88,45,683
  - Taxes on products 29,63,201 | …; subsidies on products 6,09,335 | …
  - GDP 2,61,77,001 | 2,90,73,287 | 3,17,98,524
  - CFC; PFCE 1,49,38,852 | 1,64,15,547 | 1,80,78,011; GFCE
  - GCF = GFCF + CIS + Valuables
  - Exports and imports, split goods/services
  - **Discrepancies 0 | 0 | -1,07,438** (constant prices: 0 | -70,316 | 36,908)
  - Primary income from RoW (net) -3,70,307 | …; GNI; NNI; other current transfers (net) 8,19,212 | …; GNDI; NNDI
  - Gross saving 79,40,137 | 94,36,799 | 1,10,48,415
  - Notes: "Estimates of Savings and Disposable Income are compiled only at current prices." "Import of Services have been adjusted for Cost, Insurance & Freight (CIF)."
- **1.9 Finances for GCF**:
  - Gross saving by sector:
    - Public NFC: departmental enterprises (DE) and non-departmental enterprises (NDE)
    - Private NFC
    - Public FC (DE/NDE)
    - Private FC
    - General government: -5,91,900 | -3,18,384 | -99,729
    - Households: 52,68,223 | 58,90,330 | 68,47,097, split as gross financial saving, less financial liabilities, saving in physical assets, and gold and silver ornaments
  - Net capital inflow from RoW
  - Memo items: reinvested earnings of foreign companies; co-operatives
  - Note: "GCF… estimated by two approaches… flow of funds… and… commodity flow… The difference… due to different data sources." Sources and Methods says that in the new series the headline GCF is the expenditure-side total and the difference goes to "errors and omissions".
- **1.14 Institutional sectoral accounts – key indicators:** GVA, gross saving, GCF and CFC for public NFC, private NFC, public FC, private FC, general government (plus GDI and final consumption) and households incl. NPISH (plus GDI and final consumption).
  - Household GDI 2,10,19,933 | 2,28,77,010 | 2,47,96,706
  - General government GDI 23,42,160 | 28,02,643 | 33,45,610
- **5.3 Household financial assets and liabilities (flows):**
  - Assets: currency; deposits (banks, NBFCs, co-ops, trade debt); shares and debentures (primary, co-op, mutual funds, secondary market); claims on government (G-secs, small savings); insurance (life, postal, state); provident and pension funds
  - Liabilities: bank advances, co-op loans, NBFC/FC loans, government loans, insurance loans
  - Net financial saving 13,91,548 | 16,92,912 | 22,57,602
  - Note: includes quasi-corporates
- **6.1 Detailed external transactions account:**
  - Exports: goods (merchandise f.o.b., merchanting, processing) and services (detailed: computer, business, financial incl. FISIM, …)
  - Compensation of employees in/out; property income in/out; other current transfers in/out
  - Current-account surplus: -5,27,525 | -2,08,891 | -1,79,997
  - Capital transfers; net lending; net acquisition of foreign financial assets and liabilities by instrument
  - Notes: "Data on Export and Import of goods and services as per BPM compiled by RBI"; "@ Including errors and omissions"
- **7.1 Output, IC, GVA, production taxes less subsidies, CFC, CE, OS/MI by industry** (current prices), about 24 rows:
  - Agriculture (crops, livestock, forestry, fishing)
  - Mining
  - Manufacturing (1 row)
  - Utilities
  - Construction
  - Trade & repair; hotels
  - Railways, road, water and air transport, services incidental to transport, storage, communication
  - Finance
  - Real estate & professional services
  - Public administration
  - Other services
  - 7.1A / 7.1B / 7.1C split this by public sector / private corporations / households. 2022-23 totals: output 5,34,84,479; IC 2,96,61,344; CE 86,53,669; OS/MI 1,16,54,812.
- **1.6 GVA by activity** adds 5 manufacturing sub-groups: food/beverages/tobacco; textiles/apparel/leather; metal products; machinery & equipment; other.
- **1.5 / 1.10 / 1.11 / 7.2–7.4:** capital formation by industry, asset (dwellings/structures, machinery, cultivated biological resources, IPP) and institutional sector; net capital stock.
- **1.13:** FISIM by using industry.
- **4.1:** value added of central government and of state governments, state-wise.
- **4.2:** COFOG expenditure, one sheet per year (2022-23, 2023-24, 2024-25), with rows for final consumption expenditure (compensation of employees and intermediate consumption), subsidies, other current transfers, etc.
- **5.1:** PFCE by COICOP 2018 item. **5.2:** individual consumption by households and general government.
- **8.17.1:** PE 2025-26 macro aggregates (GDP 3,45,36,796 current; GNDI 3,53,03,081; discrepancy -1,18,500 current). **8.17.2:** PE GVA by activity.
- **8.18.1 / 8.18.2:** quarterly GDP and expenditure components, Q1 2022-23 to Q4 2025-26. The quarterly current-price discrepancies are non-zero even in 2022-23 (e.g. Q1 -41,323), although they sum to zero for the year.

### 1.4 Old series (base 2011-12) — still needed for the time series

- NAS 2025 `1.1.xlsx` (`/sites/default/files/reports_and_publication/statistical_publication/National_Accounts/NAS2025/`): 2011-12 … 2023-24. GDP 2022-23 = 2,68,90,473 and 2023-24 = 3,01,22,956 (old base); discrepancy 2022-23 = -4,74,817.
- NAS 2025 `1.9`, `5.3`: 2011-12 … 2023-24; household saving 2011-12 = 20,65,566.
- NAS 2024 `1.15`, `5.0` etc.: full sequences of accounts, 2011-12 … 2022-23.
- MOSPI API, `base_year=2011-12`:
  - `series=Back`: 62 records for GDP; the first page shows 2002-03 … 2011-12 (paginated back to the 1950s; not fully paged).
  - `series=Current`: 66 records, including a 2025-26 "First Advance Estimates" on the old base (current 3,57,13,886).

### 1.5 MOSPI NAS API / eSankhyiki

- `https://api.mospi.gov.in/` → 200. It is a Swagger-UI SPA.
- GitHub `nso-india/mospi-esankhyiki`: MIT licence, pushed 2026-09-28. It is the official Python client (`pip install mospi-esankhyiki`, v0.1.4). **Quirk:** the client's default `base_url` is a UAT private IP `http://10.24.89.9:5000`; the production URL `https://api.mospi.gov.in` must be passed explicitly. The swagger file `swagger_user_nas.yaml` lists endpoint `/api/nas/getNASData` with these parameters: base_year (2022-23 | 2011-12), series (Current | Back), frequency_code (Annually | Quarterly), indicator_code, quarterly_code, year, approach_code, revision_code, account_code, institutional_code, industry_code, subindustry_code, page, Format (JSON | CSV).
- `GET https://api.mospi.gov.in/api/nas/getNasIndicatorList?account_code=1` → 200, **no key**. Annual indicators 1–22:
  - GVA; net taxes, taxes and subsidies on products; GDP; CFC; NDP
  - GCF by industry of use; GFCF; PFCE; GFCE; change in stocks; valuables; exports; imports
  - Primary income from RoW; GNI; other current transfers; GNDI; gross saving
  - GVA and GDP growth rates
  - Quarterly subset available. `account_code=2` = state GSDP, **still base 2011-12 only**.
- `getNasFilterByIndicatorId?...indicator_code=1` → years 2022-23 to 2025-26; 15 industries plus 18 sub-industries; institutional codes 1–7; revision codes 3 (PE), 4 (FRE), 8 (Final).
- `getNASData?base_year=2022-23&series=Current&frequency_code=Annually&indicator_code=5&Format=JSON` → GDP values matching NAS 2026 exactly (e.g. 2022-23 current 26177001, "Final Estimates"). The quarterly query returns Q1 2026-27 (8826871 current).
- `indicator_code=20` → gross saving by institutional sector (matches 1.9/1.14).
- **Quirk:** `Format=CSV` returned the header row only (no data rows) for three queries that returned data as JSON. Use JSON.
- CORS headers allow GET. No rate-limit headers were observed.
- `https://esankhyiki.mospi.gov.in/macroindicators?product=nas` → SPA shell (WebFetch saw only a title). Its bundle calls `https://api.mospi.gov.in/api` and `https://api.mospi.gov.in/api/esankhyiki/`, i.e. the same backend. The Q1 press note says: "Detailed data pertaining to GDP is available at https://esankhyiki.mospi.gov.in/macroindicators?product=nas".

### 1.6 Licence / terms

- MOSPI copyright policy (`POST https://www.mospi.gov.in/api/copy-right-policy/get-copy-right-policy-data`): "Material featured on this website may be reproduced, following the revised GSDD 2026… the material has to be reproduced accurately and not to be used in a derogatory manner or in a misleading context… the source must be prominently acknowledged."
- GSDD 2026 (Gazette of India Extraordinary No. 122, 6 May 2026; notification dated 27 Apr 2026), at `https://www.mospi.gov.in/uploads/acts_and_policies/acts_and_policies1778231030122_a1a3ee77-e36d-4895-8da5-b294751cbb1a_272304_(1).pdf`:
  - "in accordance with NDSAP, 2012"
  - "Category A (open access data): Aggregated/analyzed information and publications which will be shared free of cost with users… (i) Data relating to National Accounts"
  - §5.7.1: "available free without registration"
  - Registration and pricing apply only to Category B/C (unit-level) data.
- The terms-and-conditions and disclaimer endpoints cover only registration privacy and the AI chatbot. **No explicit GODL text on mospi.gov.in.**
- data.gov.in: the search page footer says "published on data.gov.in is owned by the respective Ministry… and licensed under the Government Open Data License - India". But `/government-open-data-license-india` → 302 to page_not_found (the licence page is `/Godl`, not fetched). Catalog pages `national-accounts-key-aggregates` and `quarterly-estimates-gdp-constant-prices` were found by search but **timed out or returned 403** to curl/WebFetch, so whether they carry the 2022-23 base is unverified.
- The GitHub client is MIT-licensed; that covers the code only, not the data.

---

## 2. Revision cycle (new series), from ARC 2026-27 and press releases

For fiscal year t:

| Estimate | When released |
|---|---|
| First Advance Estimate (FAE) | ~7 Jan of year t |
| Second Advance Estimate (SAE) | ~26/27 Feb of year t |
| Provisional Estimate (PE) | 7 Jun (or previous working day) after year-end; 5 Jun in 2026 |
| First Revised Estimate (FRE) | end-Feb of t+2 |
| Final | end-Feb of t+3 |

- The NAS publication then reprints the latest vintage. **NAS 2026 came out on 31 Aug 2026** together with Q1 GDP, which is later than the old June practice (NAS 2025: 26 Jun 2025; NAS 2024: 5 Jun 2024).
- Quarterly GDP comes out about 2 months after the quarter ends (31 Aug, 30 Nov, end-Feb, 7 Jun).
- The old series had FRE, SRE and TRE vintages. The new API exposes only revision codes PE, FRE and Final for 2022-23+.

## 3. SAM relevance summary

| SAM block | NAS 2026 source | Notes |
|---|---|---|
| Activity output, IC, GVA by industry | 7.1, 1.5, 1.6, 8.x | 24 industry rows; manufacturing is one row in 7.1 (5 sub-groups in 1.6 GVA only; corporate/household manufacturing detail in 8.6.x) |
| Factor payments (CE, OS/MI, CFC) by industry | 7.1 / 7.1A-C | Mixed income is not separated from OS |
| Net production taxes by industry; product taxes/subsidies total | 7.1; 1.1 | Product-level taxes come from the SUT |
| Final demand (PFCE by COICOP, GFCE, GFCF by asset/sector/industry, CIS, valuables, X, M) | 1.1, 1.10, 1.11, 5.1, 5.2, 7.2-7.3, 4.2 | |
| Institutional GDI, consumption, saving, GCF | 1.14, 1.9 | Only key indicators on the new base; no primary/secondary distribution detail |
| Household financial vs physical saving | 1.9, 5.3 | Instrument detail for financial saving |
| RoW current and capital account, financial account by instrument | 6.1 | BPM-based via RBI |
| Government value added (Centre/States), COFOG | 4.1, 4.2 | |
| Full sequence of accounts (D1–D8 by sector) | **not on new base**; NAS 2024 old base to 2022-23 | Gap |

## 4. Reference-year inputs (this family)

- **2022-23:** Final (new base); full NAS detail; SUT available; discrepancy 0. Also the last year with old-base sequences of accounts (NAS 2024 and 2025 editions).
- **2023-24:** Final (new base); full NAS detail; SUT available; discrepancy 0 at current prices. **The best candidate from the NAS side.**
- **2024-25:** FRE; full NAS detail; no SUT; discrepancy -1,07,438 crore (-0.34%). It becomes Final on 26 Feb 2027.
- **2025-26:** PE aggregates only (no institutional or industry detail beyond GVA by activity).

## 5. Issues log (for ISSUES.md)

1. Sequence-of-accounts statements (1.3, 1.15, 2.x, 3.x, 4.0, 5.0, 6.0) are absent from NAS 2025 and NAS 2026. *Sources and Methods* §30.7 says they are part of NAS. Ask MOSPI NAD whether new-base sequences of accounts will be published.
2. The original 27-Feb-2026 press-note URL now returns 403; replaced by a "-F" file. MOSPI `/uploads/` returns 403 for non-existent files, so broken links look like access blocks.
3. `api.mospi.gov.in` `Format=CSV` returns the header only; JSON works.
4. The esankhyiki Python client defaults to a private UAT IP.
5. No back series on the new base yet (expected Dec 2026). Any time series before 2022-23 must use old-base 2011-12 data, a level break of about -2.7% in 2022-23 GDP. A time series built from these must flag the level break.
6. data.gov.in catalog pages timed out (curl, 90 s, twice) or returned 403 (WebFetch).
7. State GSDP in the API is still base 2011-12 only.
8. Constant-price discrepancies and quarterly discrepancies remain non-zero.
9. Two versions of the new series exist (27 Feb 2026 and 31 Aug 2026). For example, 2022-23 GDP changed from 2,61,17,627 to 2,61,77,001 crore. Always cite the vintage (NAS 2026, 31 Aug 2026).
