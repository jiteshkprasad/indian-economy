# Phase 0 recon: international and cross-country sources (family `international`)

Working notes by the recon agent for the `international` source family. Checked on **2026-09-29**.
Every fetched URL is listed with what it returned. "Unverified" means I could not confirm it in this session, with the reason given.
Probe downloads went to the session scratchpad (outside the repo). Nothing was written to `data/`.

---

## 0. Headline findings (read this first)

1. **India's GDP base year is now 2022-23, and the international databases have partly caught up.**
   - The World Bank WDI country metadata (API, fetched) says `Nationalaccountsbaseyear : 2022/23` and `SNApricevaluation : Value added at basic prices (VAB)`. The special note says India's national accounts are **fiscal-year based (FY ending 31 March)**. WDI was last updated 2026-07-13.
   - The IMF `ANEA` (annual national accounts) India series carries `REFERENCE_PERIOD_REPORTED = 2022-2023`, so it is on the new base.
   - **These sources are still on the OLD 2011-12 base:**
     - UN AMA ("Latest Data Upload: January 2026"): India GDP for 2024 is ₹330.68 lakh crore, which is the old-series FY2024-25 figure.
     - ADB MRIO 2022-2024 (released Jul/Aug 2025): its India 2022 value added is about $3.136 tn. That matches old-base FY2022-23 GVA converted to USD. This is my inference, medium confidence.
     - OECD ICIO 2025 edition: released Aug 2025, revised Oct 2025 and Jan 2026. It only goes up to 2022, and its India inputs are MOSPI SUTs for 2011-2019. I infer, but have not confirmed, that it uses the old base.
   - Web search shows MOSPI's press note "New Series of GDP Estimates with Base Year 2022-23" dated 27-02-2026 (mospi.gov.in and PIB). The MOSPI recon agent should verify that directly. I only confirmed it indirectly, through the WDI and IMF metadata.
2. **Year conventions differ, so beware of hidden level shifts.** For the same label "2024":
   - WDI India nominal GDP = ₹318.07 lakh crore. This is FY2024-25.
   - IMF ANEA = ₹311.18 lakh crore. This is a **calendar-year** figure: 0.75×FY24-25 + 0.25×FY23-24 = 311.0, which checks.
   - Never mix these without an explicit year-basis conversion.
3. **Best non-official IO fallback: ADB MRIO.**
   - It has a national IOT for India covering 2000 and 2007-2024: 35×35 industries, current USD million, domestic and imported blocks separated, released Aug 2025.
   - The download is free and needs no login.
   - The licence is not stated on the data page itself. The ADB Data Library terms page is behind a Cloudflare challenge; see Issues.
4. **Best open licence for an IO structure: OECD ICIO 2025.**
   - It covers 1995-2022 with 50 ISIC Rev.4 industries.
   - OECD data terms allow any use, including commercial use, with attribution.
   - Its India data for 2020-2022 are modelled, not based on an Indian SUT.
5. **Licences that block republishing on a public site:**
   - **Eora** (a commercial licence is needed for websites).
   - **GTAP 12** (paid, $3,890-$10,000 for a lower-middle-income or high-income for-profit buyer).
   - **EXIOBASE** (Zenodo record v3.9.6 now states a customised non-commercial CC-BY-SA-NC-style licence. This contradicts exiobase.eu, which says CC BY-SA 4.0).
   - **UN Comtrade** (re-dissemination as-is needs permission. However, a free-of-charge visualisation or analytics app is explicitly allowed without permission).
6. **IMF legacy access is gone.**
   - `dataservices.imf.org` does not resolve (curl exit 6, DNS).
   - IFS as a single dataset was discontinued. Its content is now split into ER, IL, MFS_*, CPI, ANEA and others, flagged `IFS_FLAG`.
   - DOTS is replaced by `IMTS`.
   - The new SDMX API at `api.imf.org/external/sdmx/{2.1|3.0}` works with **no key**.

---

## 1. OECD Inter-Country Input-Output tables (ICIO), 2025 edition

**Fetched:** `https://www.oecd.org/en/data/datasets/inter-country-input-output-tables.html`
- WebFetch returned **403**.
- curl with a browser User-Agent returned **200** (1.49 MB).
- The page shows two versions: "regular ICIO including 80 economies and rest of the world, and extended ICIO including 80 countries with China and Mexico split".
- Page note: "The current database, released mid-January 2026, is a second revision of the database first published at the end of August 2025 and subsequently revised mid-October 2025 … No further revisions are anticipated."
- Downloads are grouped into year blocks "1995-2000 … 2016-2022". Links:
  - `https://webfs-sti.oecd.org/files/STI-PIE/ICIO/2025/2016-2022_SML.zip` (regular CSV). A HEAD request returned 200, Content-Length 166,241,019, Last-Modified Mon, 18 May 2026 14:52:17 GMT. Note that the server date is later than the "mid-January 2026" text. Possibly a silent re-upload; unverified.
  - `.../2025/*_EXT.zip`, `ICIO2025econA/B/VB/Z/OTHER.zip` (R data)
  - `ReadMe_ICIO_small.xlsx`, `ReadMe_ICIO_extended.xlsx`, `ICIO2025annex.pdf`
- Earlier editions are still posted: 2023 (1995-2020), 2021 (1995-2018) and 2018 (2005-2015).

**Probe download:** `ReadMe_ICIO_small.xlsx` (328 KB)
- ReadMe: "OECD, Inter-Country Input-Output (ICIO) Tables 2025 edition". "Data are expressed in current USD, million". Cite as "OECD. (2025) OECD Inter-Country Input-Output Tables, https://oe.cd/icio".
- Structure sheet:
  - Intermediate block Z has 81 country blocks × 50 industries.
  - Final demand columns are HFCE, NPISH, GGFC, GFCF, INVNT and DPABR.
  - Rows include TLS (taxes less subsidies on products), VA (value added at basic prices) and X (output at basic prices).
  - Files are "one year per CSV file".
- Area_Activities sheet: `36 IND India`. There are 50 industries on ISIC Rev.4, running from A01, A02, A03, B05…B09, C10T12 … C24A, C24B … C301, C302T309 … J58T60, J61, J62_63, K, L, M, N, O, P, Q, R, S to T. "80 economies (i.e. 38 OECD countries and 42 non-OECD economies) and the Rest of the World".

**Probe download:** `ICIO2025annex.pdf` (316 KB, 6 pages)
- Table 3, "Availability of SUTs and IOTs": the India row (flagged `IND*`, "Annual tables based on national fiscal years … India (1 April to 31 March)") has code 1 (SUTs only) for **2011-2019** and 0 for 1995-2010 and 2020-2022.
- So OECD used Indian SUTs for 2011-12 to 2019-20. India's cells for 2020-2022 are OECD estimates.

**Licence.** Fetched `https://www.oecd.org/en/about/terms-conditions.html` with curl (200). Section 3, "Data":
- "Except where additional restrictions apply … you can extract from, download, copy, adapt, print, distribute, share and embed Data for any purpose, even for commercial use. You must give appropriate credit to the OECD…"
- The same terms also warn: "The OECD may … modify the amount of Data you may request in a single query, to modify the number of queries…"
- The OECD does not name this CC BY 4.0. Written content published from 1 July 2024 is CC BY 4.0, but the data terms are their own attribution licence.

**Related OECD SDMX API.** `https://sdmx.oecd.org/public/rest/dataflow/all` returned 200 and lists:
- `DSD_TIVA_*` "Trade in Value Added (TiVA) 2025 edition"
- `DSD_BATIS@DF_BATIS` (see §10)
- `DSD_BIMTS@*` (balanced merchandise trade)

I did not find a national IOTs dataflow for India by name in that listing.

**SAM use.**
- Fallback or cross-check for the inter-industry structure (A matrix) if MOSPI's official SUT/IOT is stale.
- Import-use split by partner and industry, which gives the RoW import column by industry.
- Separate TLS row and DPABR.
- Concord ISIC Rev.4 A-T to NIC 2008.

---

## 2. ADB Multiregional Input-Output tables (MRIO)

**Fetched:** `https://kidb.adb.org/globalization/current` (curl 200, 94 KB)
- This is an Inertia.js page. I parsed the JSON in its `data-page` attribute.
- Blurb: "ADB compiles MRIO tables at current prices for 62 and 72 economies and aggregated Rest of the World. More recent tables at current prices will cover 74 economies". India is one of the 29 named Asia-Pacific economies.

File list, all at `https://kidb.adb.org/download/mrio-file/{id}`:

| Series | Years | Updated |
|---|---|---|
| 62 economies | 2000, 2007-2016 | Jun 2022 |
| 62 economies | 2017 | Aug 2025 |
| 62 economies | 2018-2020 | Sep 2024 |
| 62 economies | 2021 | Aug 2024 |
| 62 economies | 2022-2023 | Jul 2025 |
| 62 economies | 2024 | Aug 2025 |
| 72 economies | 2017-2024 | same dates as above |
| 74 economies | 2022-2023 | Jul 2025 |
| 74 economies | 2024 | Aug 2025 |
| 71 economies incl. Latin America | 2007, 2011, 2017 | Mar 2022 |

- National IOTs: "IND IOT 2000, 2007-2024.xlsx", id 211, "Updated on August 2025".
- A HEAD request on id 211 returned 200, Content-Length 921,068, Last-Modified Fri, 05 Dec 2025, `Content-Disposition: attachment; filename="IND IOT 2000, 2007-2024.xlsx"`.
- There is also a concordance file, `Correspondence_ISIC4-ISIC31-MRIO.xlsx` (id 179).

**Probe download:** IND IOT (921 KB)
- There is one sheet per year: 2000 and 2007 to 2024.
- Header: "India Input-Output Table (35x35), 2024 / (at current prices, $ million) / as of August 2025".
- Rows are IND c1..c35 (domestic) plus IMP c1..c35 (imports), then:
  - r60 intermediate input total
  - r99 taxes less subsidies on products
  - r61 CIF/FOB adjustments
  - r62 direct purchases abroad
  - r63 purchases by non-residents
  - r64 value added at basic prices
  - trs international transport margins
  - r69 total
- Final demand columns are F1 HH, F2 NPISH, F3 Govt, F4 GFCF, F5 inventories and F6 exports.
- Sectors follow the classic WIOD-35 ISIC Rev.3.1-based list (c1 agriculture … c35 private households).
- Sum of r64 across 35 industries: 2019 = $2,606,507 mn; 2022 = $3,135,712 mn; 2023 = $3,318,752 mn; 2024 = $3,598,908 mn.
- For comparison, WDI (API) GVA at basic prices is $2,957,036 mn for 2022 (FY22-23, new base).
- My inference (medium confidence) is that the ADB 2022 table reflects the **old 2011-12 base**, FY2022-23, with USD conversion. The ADB year label "2022" probably means India's FY2022-23. This is **unverified**, as no ADB methodology note was accessible.

**Licence.**
- `https://www.adb.org/terms-use` via WebFetch returned 200. It covers publications: "Materials published and copyrighted solely by ADB under a Creative Commons Attribution (CC BY 3.0 IGO)". It covers project data: "…may be copied, downloaded, distributed, adapted… for commercial and noncommercial purposes at no cost". For Data Library datasets, it says to "refer to their specific terms of use", which are on a separate page.
- `https://data.adb.org/*` (dataset page and terms) returned **403 with a Cloudflare "Just a moment..." JS challenge**. I did not bypass it.
- The kidb page footer only says "ADB encourages websites and blogs to link to its web pages."
- So the MRIO licence is **unverified**. It is commonly cited as CC BY 3.0 IGO, but I did not confirm that.
- `https://www.adb.org/what-we-do/data/regional-input-output-tables` also returned 403 to curl.

**SAM use.**
- The most recent free IO structure for India (2024, 35 sectors), with the domestic/import split.
- Useful for updating the A matrix to the reference year, or as a RAS prior.
- Also gives exports by sector and bilateral intermediate trade in the MRIO.
- Quirks:
  - USD not INR.
  - Probably old base.
  - Aggregated services (e.g. c28 financial intermediation).
  - r99 TLS is a single row, with no GST split.

---

## 3. World Bank World Development Indicators (WDI)

**Fetched:** `https://datacatalog.worldbank.org/search/dataset/0037712/World-Development-Indicators` (WebFetch 200)
- License: "Creative Commons Attribution 4.0".
- "Metadata last updated on Jul 20, 2026".
- Excel (77.9 MB zip) and CSV (269.7 MB zip) are both "updated Jul 17, 2026". Periodicity: Annual.

**API (no key):**
- `https://api.worldbank.org/v2/sources/2?format=json` returns `"lastupdated":"2026-07-13"`.
- `https://api.worldbank.org/v2/country/IND/indicator/NY.GDP.MKTP.CN?format=json&mrv=5` returns 2025 = 345,471,567,964,600 (₹345.47 lakh crore), 2024 = 318.07, 2023 = 289.84, 2022 = 261.18, 2021 = 235.97.
- `…/BX.TRF.PWKR.CD.DT` (personal remittances received) returns 2025 = $150.7 bn and 2024 = $137.7 bn.
- `mrnev=1` checks (latest non-empty):

| Series | Latest year |
|---|---|
| NE.CON.PRVT.CN | 2025 |
| NE.CON.GOVT.CN | 2025 |
| NE.GDI.TOTL.CN | 2025 |
| NV.IND.MANF.CN | 2025 |
| NY.GNP.MKTP.CN | 2025 |
| BN.CAB.XOKA.CD | 2025 = -16.49 bn |
| BX.KLT.DINV.CD.WD | 2025 |
| GC.TAX.TOTL.CN | **2022** |
| GC.REV.XGRT.CN | **2022** |
| DT.DOD.DECT.CD | 2024 |
| SI.DST.FRST.20 | 2022 |

- Country metadata: `https://api.worldbank.org/v2/sources/2/country/IND/series/all/metadata?format=json`:
  - `Nationalaccountsbaseyear : 2022/23`
  - `BalanceofPaymentsManualinuse : BPM6`
  - `GovernmentAccountingconcept : Consolidated central government`
  - `SpecialNotes : … fiscal year-based (fiscal year-end: March 31)`
  - `Latesttradedata : 2018`
- The endpoint `…/sources/2/country/IND/metatypes/all` returned an error ("Data not found"). The `series/all/metadata` path works instead.
- Other sources' lastupdated values: IDS (6) 2025-12-03; QEDS SDDS (22) 2026-08-07.

**Quirks.**
- The WDI current account for 2025 (-16.49 bn) differs from IMF BOP 2025 (-20.23 bn). This is probably FY vs CY or a vintage difference; unresolved.
- Central-government-only fiscal data, ending in 2022.

**SAM use.**
- Cross-check for the expenditure aggregates.
- Remittances.
- Distribution shares for household quintile calibration (SI.DST.*).
- Not a primary source.

---

## 4. IMF data (new portal and SDMX API)

**Portal.**
- `https://data.imf.org/` and `https://data.imf.org/en/Resource-Pages/IMF-API` returned **403 (Akamai "Access Denied")** to curl.
- WebFetch of `https://data.imf.org/en/news/accessing-international-financial-statistics` worked. It shows "Publication Date: Mar 24, 2025", "International Financial Statistics (IFS) data is now organized around topics with indicators accessible via existing datasets", "Discontinued as a single Dataset, Data by topic remains", and filtering via `IFS_FLAG`.
- Web search results (not fetched directly) say the new portal launched on 31 Mar 2025 and the legacy portal was retired, with legacydata.imf.org access to 30 Jun 2025. Retirement dates vary in snippets, so treat them as unverified.
- `https://dataservices.imf.org/REST/SDMX_JSON.svc/Dataflow` failed with **curl exit 6 (host did not resolve)**. The legacy JSON API is dead.

**API (no key needed):**
- `https://api.imf.org/external/sdmx/2.1/dataflow` returned 200 (444 KB). `…/sdmx/3.0/structure/dataflow` returned 200.
- The data endpoint is `https://api.imf.org/external/sdmx/2.1/data/IMF.STA,{FLOW}/{key}`, using the header `Accept: application/vnd.sdmx.data+csv;version=1.0.0`.

Relevant dataflows seen (agency, id and version as listed):

| Dataflow | Version | Dimensions |
|---|---|---|
| `IMF.STA:BOP` | 21.0.0 | COUNTRY.BOP_ACCOUNTING_ENTRY.INDICATOR.UNIT.FREQUENCY |
| `IMF.STA:IIP` | 13.0.0 | |
| `IMF.STA:IMTS` | 1.0.0 | COUNTRY.INDICATOR.COUNTERPART_COUNTRY.FREQUENCY; replaces DOTS |
| `IMF.STA:ITG` | | |
| `IMF.STA:ANEA` | 6.0.1 | COUNTRY.INDICATOR.PRICE_TYPE.TYPE_OF_TRANSFORMATION.FREQUENCY |
| `IMF.STA:QNEA` | | |
| `IMF.STA:GFS_SOO` | 12.0.0 | COUNTRY.SECTOR.GFS_GRP.INDICATOR.TYPE_OF_TRANSFORMATION.FREQUENCY |
| `GFS_BS`, `GFS_COFOG`, `GFS_SSUC`, `GFS_SOEF`, `GFS_SFCP`, `QGFS` | | |
| `MFS_CBS`, `MFS_ODC`, `MFS_DC`, `MFS_OFC`, `MFS_FC`, `MFS_MA`, `MFS_IR`, `MFS_FMP` | | |
| `ER`, `IL`, `IRFCL` | | |
| `DIP` (formerly CDIS) | | |
| `PIP` (formerly CPIS) | | |
| `COFER`, `FSIC`, `WEO` (IMF.RES), `FM` (IMF.FAD), `GDD`, `HPD` | | |

Monthly vintage flows also exist (e.g. `BOP_2026_MAY_VINTAGE`), which help with reproducibility.

**India probes (CSV, full series):**

| Dataflow | Size | India coverage |
|---|---|---|
| BOP `IND.*.*.*.A` | 21.9 MB | 1975-**2025**. Last UPDATE_DATE 2026-09-28. 2025 values (USD): CAB NETCD_T -20.23 bn; G credit 449.5 bn / debit 762.6 bn; S credit 412.3 bn / debit 202.7 bn; IN1 net -50.5 bn; IN2 credit 145.7 bn. |
| IMTS `IND.*.*.A` | 22.9 MB | 1948-**2025**, indicators XG_FOB_USD, MG_CIF_USD, MG_FOB_USD, TBG_USD, by partner. 2025: exports to USA $92.5 bn; imports from CHN $124.8 bn; world exports $445.1 bn. |
| ANEA `IND.*.*.*.A` | 1.6 MB | 2005-**2025**. REFERENCE_PERIOD_REPORTED "2022-2023". Nominal B1GQ 2024 = ₹311.18 lakh crore (calendar year; see §0). Indicators: B1GQ, B1G, B1G_A/C/F/L68/..., P3, P3_S13, P5, P51G, P52, P53, P6, P7, D29X39. |
| GFS_SOO `IND.*.*.*.*.A` | 149 MB | Budgetary central govt `S1311B` 1974-**2022**; state govt `S1312MIXED` 1974-**2017**; local `S1314` to 2022. |
| GFS_COFOG | | to **2018** |
| QGFS | | 2007-2016 only |
| IIP | | to **2026-Q1** |
| DIP | | 2009-**2024** |
| PIP | | Query returned data, but the CSV was truncated (tokenizer EOF). Partially verified. |

**Licence.**
- `https://www.imf.org/external/terms.htm` and `https://www.imf.org/en/about/copyright-and-terms` returned **403 (Akamai)** to both curl and WebFetch.
- The API's own `LICENSE` field on every row says: "© International Monetary Fund Copyright. All Rights Reserved. https://www.imf.org/external/terms.htm".
- A web search snippet of the IMF Copyright and Usage page says that redistributed data must be attributed ("Source: International Monetary Fund, Database Name, <<link>>"), and if sold as a standalone product, purchasers must be told the data is free from the IMF.
- So this is **not an open licence**. Use with attribution appears allowed, but the exact clauses are **unverified**, because the page is blocked.

**SAM use.**
- BOP by BPM6 item: the full RoW account, i.e. goods, services, primary income (COE and investment income), secondary income (remittances IN2) and the financial account.
- IMTS: goods trade by partner.
- DIP/PIP/IIP: partner stocks.
- GFS: government in SNA-style classification. It is stale for India (2022 central, 2017 states), so only a cross-walk.
- MFS: RBI and banking sector balance sheets.
- Everything is also available from RBI. The IMF is a consistency cross-check and a partner breakdown source.

---

## 5. UN Comtrade (goods) and UN Service Trade (services)

**API.**
- `https://comtradeapi.un.org/public/v1/preview/C/A/HS?reporterCode=699&period=2024&partnerCode=0&flowCode=X,M&cmdCode=TOTAL` returned 200 with no key. It shows India 2024 imports $697.7 bn (CIF), classification H6.
- Period 2025 (annual) returns data.
- Period 2026 annual has no data yet.
- Monthly `C/M/HS … period=202606` returned 3 records, so monthly data runs to **Jun 2026**.
- A second quick call returned `429 "Rate limit is exceeded. Try again in 2 seconds."`.
- `https://comtradeapi.un.org/data/v1/get/...` without a key returned **401 "missing subscription key"**.
- Services (typeCode S, classification EB = EBOPS 2010):
  - India `S/A/EB period=2022` gives 145 records, **partner = World (0) only**. Code 200 (total services) exports $309.4 bn, imports $176.8 bn.
  - 2023 gives 38 records.
  - 2024 gives 0.
  - So UN Service Trade is now served inside Comtrade (web search: "UN ServiceTrade … trade in services from 2000 onward … by EBOPS category and partner country"). India reports no partner detail.

**Tiers.** Fetched `https://uncomtrade.org/docs/subscriptions/` (200):
- Anonymous preview: "Limited to 500 records and 1 single period and product per call".
- Free registered: "data API access for up to 500 calls/day", 100K records per call.
- Premium: 5000 calls/day or unlimited, bulk and async API. The price is on shop.un.org; a web search said about $2,000 per year for individuals, which is unverified.

**Licence.** Fetched `https://uncomtrade.org/docs/policy-on-use-and-re-dissemination/` (200):
- "UN Comtrade data are provided for internal use only and may not be re-disseminated in any form without UNSD's permission."
- **But** "permission is not required for … Free-of-charge data visualization and/or data analytics application" and "Free-of-charge data extraction … offering only a small number of records (up to 100,000)".
- "To re-disseminate UN Comtrade data, a user must be an active premium subscriber" applies only to for-profit cases.
- Citation: "UN Comtrade".

**SAM use.**
- Goods trade by partner × HS product. This gives import and export columns by commodity, mapped HS→NIC/SAM sector.
- It is a cross-check for DGCI&S. Prefer DGCI&S (official) and use Comtrade for mirror data. HS is on calendar year.

---

## 6. BIS statistics

**API.** `https://stats.bis.org/api/v1/dataflow/BIS/all/latest` returned 200. Relevant flows:
- `WS_TC` (total credit)
- `WS_DSR`
- `WS_CREDIT_GAP`
- `WS_LBS_D_PUB` (locational banking)
- `WS_CBS_PUB` (consolidated banking)
- `WS_DEBT_SEC2_PUB` (international debt securities)
- `WS_NA_SEC_DSS` (debt securities statistics)
- `WS_GLI`, `WS_CBPOL`, `WS_EER`, `WS_XRU`, `WS_SPP`, `WS_CPMI_*`

India probes (CSV, no key):

| Query | Result |
|---|---|
| `WS_TC/Q.IN?format=csv&startPeriod=2020` | 200. 22 series to **2026-Q1**, e.g. "India - Credit to General government from All sectors at Nominal value - domestic currency" (INR bn) and "Credit to Private non-financial sector from Banks…" |
| `WS_LBS_D_PUB/Q.S.C.A.TO1.A.5J.A.5A.A.IN.N` | 200, to **2026-Q1** (all reporting banks' claims on India, USD mn) |
| `WS_DEBT_SEC2_PUB/Q.IN` | 200, to 2026-Q2 |
| `WS_NA_SEC_DSS/Q.IN` | 404 (wrong key) |
| `WS_NA_SEC_DSS/Q.N.IN` | 200, to **2026-Q1** (e.g. "India - Debt sec, issued by central gov, all markets…") |

**Licence.**
- Fetched `https://www.bis.org/terms_conditions.htm` (it redirects to /about/terms-conditions, 200). It points data use to the Data Portal terms.
- Fetched `https://data.bis.org/help/legal` (200): "The use of the statistics is unrestricted, provided that: if the statistics are reproduced, the BIS must be cited…; … if the statistics will be used in a commercial publication or product, their inclusion … will not result in any additional charge…".

**SAM use.**
- Cross-border bank claims and liabilities vis-à-vis India (the RoW financial account, by counterparty sector).
- Debt securities stocks by issuer sector (Flow of Funds cross-check).
- Total credit to households and non-financial corporations (FoF cross-check).
- These are stocks, so flows need differencing and FX/valuation adjustment.

---

## 7. UN national accounts (UNSD AMA / UNdata)

- `https://unstats.un.org/unsd/snaama/` (200): "Latest Data Upload: January 2026". "The database is updated in December of each year". Covers 1970 onwards.
- `https://unstats.un.org/unsd/snaama/Downloads` (200) lists Excel files served from `https://unstats.un.org/unsd/amaapi/api/file/{n}`. A HEAD request on file/1 returned **404**, but a GET returned the file. The quirk is that the server rejects HEAD.
- Probe of file/1 (GDP and breakdown, current prices, national currency): India rows 2021-2024. GDP 2024 = ₹330.68 lakh crore and 2023 = ₹301.23 lakh crore. These are old-base (2011-12) FY figures. Constant prices are "constant 2020 prices".
- UNdata terms: `https://data.un.org/Host.aspx?Content=UNdataUse` (200): "All data and metadata provided on UNdata's website are available free of charge and may be copied freely, duplicated and further distributed provided that UNdata is cited as the reference."
- UNSD "Official country data" (SNA detailed tables): `https://data.un.org/Datamart/Explorer.aspx?d=SNA` returned 404. I did not probe further; unverified.
- **SAM use:** a long-run historical cross-check only. It is stale, being on the old base.

---

## 8. Eora MRIO

- `https://worldmrio.com/` (200): "Eora2 Released … Please access … https://eora.org. This website and all Eora1 downloads are now in read-only mode. This website will be kept open through June 30, 2026." That date has passed; the site still answered 200 on 2026-09-29. Eora1 covers 1990-2022, 190 countries, and Eora26 has 26 sectors.
- `https://eora.org/` (200): "Eora2 … 19640 sectors across 190 countries, a complete timeseries for 1990-2024". Login is by magic link, and "Accounts at personal email addresses (e.g. gmail…) are not supported."
- `https://worldmrio.com/licensing.jsp` (200): "Eora provides data for years 1990-2017 for free for academic users". "A commercial license is required for all other use cases … This includes use in reports …, software tools, websites". The academic licence has a limit: "may not publish or redistribute any more than 200 individual raw data points".
- **Verdict:** not usable for a public website without a paid commercial licence.

---

## 9. GTAP

- `https://www.gtap.agecon.purdue.edu/databases/default.asp` (200): "GTAP 12 Data Base … February 2026" (release date column). The site header shows "Log In disabled (maintenance mode)".
- `https://www.gtap.agecon.purdue.edu/databases/pricing.asp` (200): "Private Sector (for profit) $10,000 … Lower-Middle Income Economy Price … $5,980". "The GTAP Data Base is not sold to re-sellers/third parties."
- Web search (JGEA vol 10(2), Dec 2025) says GTAP 12 has 7 reference years (2004, 2007, 2011, 2014, 2017, 2019, **2023**), 145 countries plus 18 aggregate regions, and 65 sectors. This was not fetched directly, so it is medium confidence.
- Older versions are available free under "Archived (Free) Releases". I did not check which.
- **Verdict:** paid, with a restrictive licence. Only useful as a methods reference (e.g. how GTAP builds the India SAM from national IO). Not recommended.

---

## 10. OECD-WTO BaTiS (balanced trade in services), an added source

- WTO page `https://www.wto.org/english/res_e/statis_e/gstdh_batis_e.htm` (WebFetch 200): "2005-24".
- OECD SDMX `DSD_BATIS@DF_BATIS` 1.0 with key `IND........` from startPeriod 2023 returned 200: 49,936 obs, periods 2023-**2024**, bilateral by partner and EBOPS 2010 item, USD mn.
- Licence: OECD data terms (see §1). The WTO API needs a key: `https://api.wto.org/timeseries/v1/indicators` returned 401 "missing subscription key". A free key is available via apiportal.wto.org.
- **SAM use:** the partner split of services exports and imports (IT/BPO to the USA and UK, etc.). India reports services by partner only partially, and not at all to Comtrade.

## 11. Eurostat FIGARO, an added source

- `https://ec.europa.eu/eurostat/web/esa-supply-use-input-tables/database` (200): "EU inter-country supply, use and input-output tables (2026 edition) … Coverage 64 industries by NACE rev. 2 / 64 products by CPA 2.1 / Time series 2010-2024". Files are CSV and Excel (with Parquet for detailed data) on CIRCABC.
- India coverage comes from a web search snippet ("15 main trading partners including India"), which is medium confidence and was not fetched on the official page.
- Licence: `https://ec.europa.eu/eurostat/help/copyright-notice` (200): "licensed under the Creative Commons Attribution 4.0 International licence".
- **SAM use:** a second open IO structure for India, up to **2024**, with both SUT and IOT. It is worth evaluating against ADB MRIO in Phase 1.

## 12. EXIOBASE

- `https://exiobase.eu/` (200): "EXIOBASE3 is licensed under a Creative Commons Attribution-ShareAlike 4.0 International License … Data updates are now housed on Zenodo … https://zenodo.org/records/15689391". It has 163 industries × 200 products.
- `https://zenodo.org/records/14869924` via curl (200) shows v3.9.5, published Feb 14, 2025: "1995 to 2020 (plus now-casted tables for 2021 and 2022) for 44 countries (27 EU member plus 17 major economies)…". It says "a version 3.10 with updates to 2022 and nowcasts to 2024 is in beta".
- `https://zenodo.org/records/15689391` via WebFetch shows v3.9.6, published June 18, 2025, with a "newer version" available. The licence is now stated as "Non-commercial academic use operates under a customized CC-BY-SA-NC derivative. Commercial licenses are under development."
- The Zenodo REST API `https://zenodo.org/api/records/15689391` returned **403 "restricted due to unusual traffic"**. I did not retry aggressively.
- Web search says v3.10.1 came out in Mar 2026 and v3.10.2 in May 2026. This is unverified.
- India's inclusion among the 17 major economies was **not confirmed in this session**, though it is widely known.
- **Verdict:** a licence conflict (see Issues). Avoid it for a public site until clarified.

## 13. WIOD

- `https://www.rug.nl/ggdc/valuechain/wiod/` (200): "The World Input-Output Database is licensed under a Creative Commons Attribution 4.0 International License". Release 2016 covers 43 countries plus RoW for **2000-2014**, 56 ISIC Rev.4 sectors.
- `…/wiod-2016-release` (200): Dataverse DOI 10.34894/PJ2M1C.
- India is in WIOD, with Socio-Economic Accounts (labour compensation, capital) to 2014.
- **SAM use:** historical only (the factor split by industry in 2000-2014). Superseded.

## 14. World Bank WITS / TRAINS tariffs, an added source

- `https://wits.worldbank.org/API/V1/wits/datasource/trn/dataavailability/country/356/year/all` (200, XML): India TRAINS tariff years run to **2021**, last updated 2022-09-09.
- A data query `…/SDMX/V21/datasource/TRN/reporter/356/…/year/2024/…` returned "NoRecordsFound".
- **SAM use:** customs duty rates by product, to check the customs row. Stale. Prefer CBIC and the Budget.

---

## Issues log (to carry into ISSUES.md)

- OECD ICIO page: WebFetch 403; curl with a browser User-Agent 200.
- data.adb.org is behind a Cloudflare JS challenge (403). The ADB MRIO licence cannot be confirmed. adb.org/what-we-do/... also returned 403 to curl.
- IMF: data.imf.org and imf.org terms pages returned Akamai 403. The licence was inferred from the API LICENSE field ("All Rights Reserved"). The legacy API host `dataservices.imf.org` does not resolve.
- IMF PIP India CSV came back truncated (parse error). This needs a paged query in Phase 1.
- UN Comtrade: HTTP 429 on back-to-back preview calls (1 call per second limit); 401 on the full data API without a key.
- UN AMA download server: HEAD returns 404, GET works.
- Zenodo API: 403 "unusual traffic".
- **EXIOBASE licence contradiction:** exiobase.eu says CC BY-SA 4.0, while Zenodo v3.9.6 says a customised non-commercial licence.
- **Vintage mismatch:** ADB MRIO, OECD ICIO and UN AMA use the pre-Feb-2026 (2011-12 base) Indian national accounts. WDI and IMF ANEA are on the 2022-23 base.
- **Year-basis mismatch:** WDI India uses FY labels (2024 = FY24-25). IMF ANEA converts to calendar years. IMF BOP annual is presumably CY. Comtrade uses CY.
- **Value mismatch:** WDI CA balance 2025 (-16.49 bn) vs IMF BOP CAB 2025 (-20.23 bn). The cause is unresolved.
- ICIO server Last-Modified (18 May 2026) is later than the "mid-January 2026" text on the page. A possible silent update, unverified.
- worldmrio.com said it would stay open until 30 Jun 2026, and it is still up. It may disappear.

## Access requests for the owner

1. **UN Comtrade free API key** (register at comtradeplus.un.org and subscribe to the free product on comtradedeveloper.un.org). This gives 500 calls/day and 100K records per call, needed for HS×partner pulls. Premium is not needed for a free visualisation site, per the UNSD policy.
2. **WTO API free key** (apiportal.wto.org), only if we use the WTO timeseries API rather than the OECD SDMX for BaTiS. It is optional.
3. **Manual check of the ADB Data Library terms** (data.adb.org is behind Cloudflare). Please open https://data.adb.org/dataset/multiregional-input-output-tables in a browser and screenshot the licence field, or email ADB.
4. **Manual check of the IMF Copyright and Usage page** (https://www.imf.org/en/about/copyright-and-terms is Akamai-blocked for bots).
5. **Optional, and I recommend against:** GTAP 12 licence (from $5,980) and an Eora commercial licence. Neither is needed if ADB MRIO, OECD ICIO and FIGARO are used.
