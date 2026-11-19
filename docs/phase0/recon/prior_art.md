# Phase 0 recon: prior art (existing Indian SAMs, IO tables, multiplier estimates)

Source family id: `prior_art`
Recon date: 2026-09-29 (all fetches made on this date)
Scratch probes (not in repo): `C:\Users\PC\AppData\Local\Temp\claude\D--India-Economy-Model\861f3371-3ce9-4165-90f0-38a599b26329\scratchpad\prior_art\`

Purpose: find published Social Accounting Matrices (SAMs) and SAM/IO/fiscal multiplier estimates for India that we can use as (a) structural templates for our account design, (b) Phase 2 sanity checks on the balanced SAM, and (c) Phase 4 cross-checks on headline multipliers.

---

## 0. Context that changes how every prior SAM should be read

**MOSPI rebased GDP to 2022-23, and the new SUTs are out.** Fetched MOSPI/PIB press release PDF
`https://www.mospi.gov.in/uploads/latestReleases/latest_release_1778842800782_05f10605-5575-44cb-87cf-a770e5a80b1c_Press_Release_Page___Press_Information_Bureau.pdf` (HTTP 200, 199 KB). It says:

- "Release of Supply and Use Tables of 2022-23 and 2023-24 ... Posted On: 15 MAY 2026"
- "the first comprehensive set of Supply and Use Tables compiled under the revised base year of 2022-23, which replaced the earlier 2011-12 base year series. The new series of Annual National Accounts Estimates with base year 2022-23 was released on 27th February, 2026"
- "the estimates of 2022-23 and 2023-24 are reconciled at the final stage to eliminate statistical discrepancies between the production/income approach and the expenditure approach at current prices"
- Uses NIC 2025 and COICOP 2018. A WebSearch snippet (not the PDF) says the tables have 155 product groups and 67 industries. **Unverified:** I did not check that count in the PDF text.

**What this means:** every SAM listed below is built on the **old 2011-12 base series** and old SUT/IOT vintages. So:
- Their *levels* (₹) will not match the new series.
- Their *structure* (shares, coefficients, account layout) and their *multipliers* are still useful as templates and cross-checks.
- None of them uses the new SUT-integrated framework. In that framework the production–expenditure discrepancy is removed in final estimates, which changes how the "statistical discrepancy" cell should appear in our SAM.

Other agents own the NAS/SUT families. This note only records the point because it decides how prior art can be used.

---

## 1. Existing SAMs for India, newest first

### 1.1 IFPRI Nexus SAM, India 2022/23 (the most recent public national SAM)

- **Dataset:** Harvard Dataverse (IFPRI "sam" collection), DOI `10.7910/DVN/LDUDTE`
  - API fetched: `https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/LDUDTE` (HTTP 200 JSON)
  - Published 2024-11-08; version 1; productionDate 2024-10-01; time period 2022–2023.
  - Files: `001_ReadMe.txt` (1,065 B), `IFPRI_SAM_IND_2022-23_POP.tab` (948 B), `IFPRI_SAM_IND_2022-23_SAM.tab` (51,793 B, tab-separated; Dataverse usually also offers the original upload format).
  - **Download needs a guestbook form.** `guestbookId: 380`. Probing `https://dataverse.harvard.edu/api/access/datafile/10595685` returned HTTP 400: `"You may not download this file without the required Guestbook response for guestbookID 380."` I did **not** fill in the guestbook, since that would be submitting identity data on the owner's behalf. **Access request:** the owner downloads the files once through the web UI (the guestbook asks for name/email/institution-type fields), or authorises us to submit the guestbook.
  - **Licence:** the dataset JSON has `license: null` but carries the "IFPRI Datasets Terms of Use Statement (December 2019)". Section 4 says: "Except where there is a statement that a non-CC license is being used, materials will be made available under the Creative Commons Attribution 4.0 International (CC-BY-4.0)." Section 5 requires attribution plus a fixed adaptation sentence: "This data was provided by the International Food Policy Research Institute (IFPRI). IFPRI bears no responsibility for the analyses or interpretations of the data presented here."
  - **Quirk:** Section 3 of the same terms also says users may not "copy, print or download ... all or substantially all of the Content" or "publicly distribute, republish" without permission "Except as expressly permitted hereunder in Section 4". Section 4 grants CC-BY-4.0, so redistributing derived numbers with attribution appears allowed. The drafting is ambiguous. Recommendation: use it as a cross-check only; do not republish the raw matrix without confirming with IFPRI-Data@cgiar.org.
- **Data paper (CC-BY-4.0):** CGSpace item `https://cgspace.cgiar.org/items/eef0cc88-5e51-4e0a-8b04-1b8f02275bfa` (WebFetch OK). Handle `10568/155099`; `dcterms.license: CC-BY-4.0`; issued 2024-10-01. The PDF is 501 KB. Its text was pulled via the CGSpace REST API: `https://cgspace.cgiar.org/server/api/core/bitstreams/2728f757-2ca0-4c65-aae4-dd43886abc5d/content`.
- **Dimensions (from the paper):** 42 activities × 42 commodities; factors = labour ×3 by education (0–6, 7–11, 12+ years), agricultural land, capital; **10 households = rural/urban × national per-capita consumption quintiles**. Other accounts: 1 enterprise account (financial plus non-financial corporations combined), 1 government account, tax accounts (atax, dtax, etax, ftax, mtax, stax), transaction costs (trc), savings-investment (s-i), change in stocks (dstk), and rest of world (row).
- **Data vintages (Table 7 of the paper):**
  - NAS: MoSPI (2024), 2022/23
  - IOT/SUT: **SUT 2019/20** (MoSPI 2023)
  - Government finance: **IMF GFS 2022**
  - BoP: **IMF BPM6 2022**
  - Exchange rate: WDI 2022
  - Private consumption: **HCES 2022-23 (NSS Report 591)**
  - Labour: **PLFS 2022-23**
  - Manufacturing split: ASI
  - Tariffs: TRAINS 2021
  - Tax rates, margins, GFCE and GFCF commodity composition: taken from SUT 2019/20
- **Balancing (Section 4):**
  - The macro SAM is reconciled by hand using residual items. In the paper's words, "Foreign savings balances the rest of world account"; household and government savings balance their accounts; "Nexus SAMs always use national accounts data instead of trade data from BOPS or government consumption spending estimates from GFS".
  - The detailed SAM is then balanced by **cross-entropy** (Robinson et al. 2001), using the IFPRI SAM Toolkit (Excel template feeding GAMS).
- **Macro SAM, Table 8 (₹ billion, 2022/23):**
  - Activities total 495,422; commodities 669,859.
  - Value added (factors ← activities) 246,992; taxes on products 22,743; activity taxes −428.
  - Private marketed consumption 139,795; government consumption 28,836; investment 92,604; exports 61,334; imports 70,532.
  - Enterprise savings 49,632; household savings 47,714; **government savings −9,855**; foreign savings 5,113.
  - Implied GDP ≈ 246,992 − 428 + 22,743 = **₹269,307 bn (₹269.3 lakh crore)**. That is my own arithmetic on their table, done for cross-checking. It is on the old 2011-12 series, and I did not compare it with a specific NAS vintage.
- **Useful derived tables:**
  - Table 9: GDP / export / import shares by sector.
  - Table 10: household income sources by quintile. Overall labour 41.1%, crop land 6.0%, capital 41.8%, government transfers 7.1%, foreign transfers 4.0%.
  - Table 11: population and savings rate by quintile. All households 22.5% savings rate; population 1,406.6 million.
- **Nexus release note 2025** (CGSpace `608feaf1-...`, handle `10568/178883`, CC-BY-4.0, issued 2025-12-12). Its country table lists "India 2022-2023 ... 2019/20 ... Survey on Household Consumption Expenditure 2022/23 ... 2017/18". So **as of Dec 2025, 2022/23 is still IFPRI's latest India SAM.** I found no 2023/24 India SAM in the Dataverse search (`api/search?q="social accounting matrix" India`).

### 1.2 IFPRI SAM, India 2017-18 (Pal, Pradesha, Thurlow 2020)

- Dataverse DOI `10.7910/DVN/NYVJX8` (published 2021-04-23; guestbook id 9; same IFPRI terms of use). Files: `IND_X112_2017-18_Notes.tab` and `IND_X112_2017-18_SAM v112N.tab` (328 KB).
- Data paper: CGSpace `3e024cfa-...`, handle `10568/143193`, DOI `10.2499/p15738coll2.134178`, CC-BY-4.0, issued 2020-11-01. Text pulled from bitstream `0c8df0bb-...`.
- **Dimensions:**
  - 112 activities: 39 agriculture and allied, 18 agro-processing, 4 mining, 24 other manufacturing, 3 utilities, 1 construction, 23 services.
  - Factors: 8 labour types (rural/urban × 4 education levels), 4 capital types, 1 land.
  - Households: rural farm, rural non-farm and urban, each split into quintiles (15 in all).
- **Vintages (Table 9):** NAS 2017/18 (MoSPI 2019); **SUT 2015/16** and IOT 2007/08; IMF GFS 2017; BPM6 2017; COMTRADE 2017; **NSS 68th round (2011/12)** for consumption and employment.
- **Balancing:** two rounds of cross-entropy, as quoted: "Nexus SAMs use cross-entropy estimation techniques ... a second round of cross-entropy estimation".
- The CSTEP note (1.5) describes an older IFPRI SAM listing as "5 rural farm household classes, 5 rural non-farm household classes, 5 urban household classes".

### 1.3 IFPRI state SAMs (Odisha, Bihar, Uttar Pradesh, 2017/18)

- Dataverse: Odisha `10.7910/DVN/74YWV2` (2025-01-06), Bihar `10.7910/DVN/GOZMQU` (2024-08-08), UP `10.7910/DVN/FQHHM8` (2024-08-08). Found via a Dataverse search API call.
- CGSpace data papers are CC-BY-4.0: Odisha `79245ab1-...`, Bihar `803f48f4-...`, UP `ab92b94a-...`; a separate Odisha 2018 SAM is `e0a2d1c1-...`.
- These matter only if we later regionalise. They are not needed for the national SAM.

### 1.4 NCAER SAM, India 2021-22 (Chaudhuri, Pratap, Pohit)

- NCAER Working Paper 160 (5 Feb 2024).
  - Landing page: `https://ncaer.org/publication/estimation-of-sam-for-india-an-application-for-indias-energy-transition-targets/`
  - PDF: `https://ncaer.org/wp-content/uploads/2024/02/NCAER_WP160_Feb-2024.pdf` (HTTP 200, 1.68 MB, 59 pp.)
- Journal version: *Margin* 18(1-2): 74–133, DOI `10.1177/00252921241284278`. The SAGE page returned **HTTP 403** to WebFetch; the metadata came from IDEAS/RePEc `https://ideas.repec.org/a/sae/mareco/v18y2024i1-2p74-133.html`.
- **TLS quirk:** `https://www.ncaer.org/` fails TLS on Windows curl/schannel (`SEC_E_ILLEGAL_MESSAGE`). `https://ncaer.org/` (no www) works.
- **Dimensions:** "a 59×59 SAM for India, with base year of 2021-22 incorporating 3 factors of production and 10 categories of households". There are 39 producing sectors plus 7 electricity sub-sectors (nuclear, solar, wind, hydro, gas, coal, other), cement, aluminium and biomass split out. Four institutions: households, government, public non-departmental enterprises, private corporations. Households are rural/urban × quintiles.
- **Method:**
  - The IOT is built from the **SUT 2018-19** ("140 products and 66 industries (for 2018-19)").
  - It is benchmarked to 2021-22 macro data ("benchmarked with macro-data of the year 2021-22").
  - The household consumption split uses **NSSO 2011-12** consumption shares.
  - Balanced with **RAS**: "RAS technique is applied so that row total of each row matches the corresponding column total".
- **Headline SAM output multipliers (Table 6):**

  | Sector | Output multiplier |
  |---|---|
  | Agriculture and allied | 6.656 |
  | Primary energy | 2.355 |
  | Mining | 5.253 |
  | Fossil-fuel commercial energy | 4.132 |
  | Non-fossil commercial energy | 6.327 |
  | Manufacturing | 5.367 |
  | Construction | 6.453 |
  | Transport | 6.332 |
  | Other services | 6.440 |

- Table 5 gives GDP at basic prices for 2021-22 as ₹2,28,24,423 crore (old series).
- The SAM itself is in the "Supplementary file" (Appendix III) of the journal version. **Not verified**, because the SAGE page returned 403.
- **Licence:** no licence statement in the PDF. The site footer says "© 2026 Copyright NCAER. All Rights Reserved." (checked `https://ncaer.org/privacy-policy/`). Usable for citation and cross-checking only.

### 1.5 CSTEP SAM, India 2017-18 (energy-disaggregated extension of the IFPRI 2017-18 SAM)

- Technical note CSTEP-TN-2024-2 (Aug 2024), by Krithika Ravishankar; landing page `https://cstep.in/publication/social-accounting-matrix-construction-and-multiplier-analysis/` (WebFetch OK).
- PDF: `https://cstep.in/wp-content/uploads/2025/06/Social-accounting-matrix-construction-and-multiplier-analysis.pdf` (26 pp.).
- **Data file:** `https://cstep.in/wp-content/uploads/2025/06/CSTEP-SAM_2017-18-3.xlsx`. HEAD returned 200, 230,044 B, last-modified 2025-06-23. I made a small probe download to scratch:
  - Sheets: `Note` and `SAM`. Units: "10 Million Rupee" (= ₹ crore).
  - **209 accounts:** 92 activities and 87 commodities, trc, 8 labour, land, capital-other, ent, 10 households (hhd-r1..r5, hhd-u1..u5), gov, mtax, dtax, stax, s-i, dstk, row.
  - Balance check (my own computation): max |row − column| = 5.6e-9. It is balanced.
- **Licence:** "©2024 CSTEP. Any reproduction in full or part of this publication must mention the title and/or citation ... Due credit must be given to the copyright owners". This is not an open licence; attribution-required reuse is implied only.
- Its **Table 1 is a useful catalogue of every Indian SAM from 1979-80 to 2017-18.** Sarkar & Subbarao 1979-80; Sarkar & Panda 1983-84; Bhide & Pohit 1985-86; Pradhan & Sahoo 1989-90; Pradhan, Sahoo & Saluja 1994-95 (60 sectors); Pradhan, Saluja & Singh 1997-98 (57 sectors); Sinha et al. 1999-2000; Saluja & Yadav 2003-04 (73 sectors, 5+5 expenditure classes); Pradhan, Saluja & Sharma 2007-08 (85 sectors per CSTEP, 78 per the IEG paper); Pal, Pohit & Roy 2003-04 (85 sectors); Pal, Pradesha & Thurlow 2017-18 (112 sectors).

### 1.6 CSEP Environmentally-extended SAM, India 2019-20 (Chadha, Sivamani, Verma)

- Landing page: `https://csep.org/technical-note/developing-an-environmentally-extended-social-accounting-matrix-for-india-2019-20/` (WebFetch OK; published 22 Nov 2023 on the page; the PDF front matter says "Embargoed till ... 13 January, 2023").
- PDF: `https://csep.org/wp-content/uploads/2023/11/Developing-an-Environmentally-extended-Social-Accounting-Matrix-2.pdf` (10.2 MB, 64 pp.).
- **Dimensions:** 45 production sectors; **318 labour categories** (region × social group × employment type × education × gender, built from PLFS 2019-20); **80 household categories**; plus pollution accounts (air, water, land).
- **Method:**
  - The IOT 2019-20 is built by **RAS-updating CSEP's IOT 2015-16** (itself from the official SUT 2015-16) to 2019-20 NAS sectoral totals (Appendix E, "RAS Methodology").
  - Net indirect taxes by sector are carried forward from the 2015-16 ratios.
  - GDP checks: 2019-20 GDP ₹2,03,51,013 crore by both the expenditure and income approaches (Table 4).
- **Documented data issue:** merchandise exports in the IOTs are lower, and services exports higher, than in MoC/RBI data. The report attributes this to "IOTs allocating exported goods' trade and transport cost components to the relevant service sectors". **This matters for our BoP ↔ SUT reconciliation.**
- **Headline multipliers (Table 11, per ₹1 lakh of exogenous demand; totals are N1+N2+N3):**

  | Sector | Total output multiplier |
  |---|---|
  | Paddy | 6.380 |
  | Agriculture | 5.980 |
  | Livestock | 6.230 |
  | Food & tobacco | 6.443 |
  | Coal & lignite | 3.044 |
  | Crude petroleum | 1.558 |

  - Labour income multipliers (Table 12): paddy 0.844, agriculture 0.923, crude petroleum 0.077.
- **SAM data file:** I found no xlsx/csv link on the landing page (only PDFs, found by grepping the HTML for href .pdf/.xlsx/.zip).
- **Licence:** "All rights reserved. Short sections of text, not to exceed two paragraphs, may be quoted without explicit permission provided that full credit ... is given." The site footer reads "© 2026 Copyright CSEP. All Rights Reserved."

### 1.7 Older SAMs (2007-08 and earlier): structural templates only

- **Pradhan, Saluja & Sharma (2013), "A Social Accounting Matrix for India 2007-08"**, IEG Working Paper No. 326. `https://www.iegindia.org/upload/publication/Workpap/wp326.pdf` (HTTP 200, 48 pp.).
  - 78 sectors; 9 households (occupation × rural/urban); factors: labour (unskilled, semi-skilled, skilled), capital, land.
  - Sources: CSO IOTT 2007-08 (130 sectors), NSS 66th round (2009-10), NCAER IES 2004-05.
  - Method notes worth copying:
    - PFCE by sector comes from the CSO IOTT and is allocated to households using NSS shares.
    - Household income comes from NCAER income-expenditure ratios, "pro-rata adjusted to equate the total household income with total personal income ... given in NAS 2011".
    - Mixed income is split into wage and non-wage using 1989-90 NAS proportions.
    - Government saving = revenue − current expenditure; foreign savings close the gap between investment and saving.
  - Licence: no licence in the PDF. The IEG site footer reads "© 2022 Copyright IEG. All Rights Reserved." (checked `https://iegindia.org/disclaimer/`).
- **Pradhan, Saluja, Sharma & Yadav, "A Regional SAM for India 2007-08"**, IIOA 22nd conference paper, `https://www.iioa.org/conferences/22nd/papers/files/1856_...pdf`. Seen in search results only; not fetched.
- **Pal & Bandara (2017), "Value-added disaggregated SAM for the Indian economy 2007-08"**, *Journal of Economic Structures*, DOI `10.1186/s40008-017-0074-y`. Fetched via curl with cookies; the page says Creative Commons (open access). 78 sectors, 48 labour types, 80 household classes.
- **Pal, Pohit & Roy (2012), "Social Accounting Matrix for India"**, *Economic Systems Research* 24(1): 77–99, DOI `10.1080/09535314.2011.618824`. SAM 2003-04 with 85 sectors. T&F, paywalled; metadata taken from CGSpace `07271e0d-...`. **Not fetched in full.**
- **Venkatesh & Pal (2018), "Compilation of an IOT and SAM for India: 2012-13"**, CSTEP WP-2018-02; and the IIOA 2019 paper "From SUTs to SAMs for India: A Synthesis of Methodologies" (`https://www.iioa.org/conferences/27th/papers/files/3665_20190720111_AV_SUTtoSAM_AV_200717_final.pdf`, 25 pp., parsed locally). Builds a 140×140 commodity IOT from the SUT 2012-13 and a 140-sector SAM with income deciles. **This is the best methodological reference for converting a SUT to a SAM in the Indian context.**
- **Pradhan, Saluja & Singh (2006), *Social Accounting Matrix for India: Concepts, Construction and Applications*** (SAGE book, SAM 1997-98). Commercial; not fetched.
- **NCAER, "A Social Accounting Matrix for India 1994-95"**: page `https://ncaer.org/publication/a-social-accounting-matrix-for-india-1994-95/` seen in search results only.
- **Levy Institute / UNDP India, Appendix B**: a village SAM (Nana Kotda), not national. `https://www.levyinstitute.org/pubs/UNDP-Levy/India/Appendix_B.pdf` (HTTP 200, 5 pp.). Not relevant beyond noting it.

### 1.8 MOSPI / CSO official SAM

- **No official MOSPI SAM found.** The WebSearch "MOSPI OR CSO social accounting matrix official" returned only NAS and IOTT pages. The National Accounts Division lists IOTT and SUT among its outputs, not a SAM.
- The last official symmetric IOTT is 2007-08 (`https://mospi.gov.in/publication/input-output-transactions-table-2007-08`, seen in a search result). After that MOSPI publishes SUTs only (2011-12 onward; latest are 2022-23 and 2023-24, released 15 May 2026, see §0).
- **Verdict:** India has no official SAM. Every SAM is academic or think-tank work.

### 1.9 India multi-regional IO (MRIO), 32 states, 2011–2019 (new, open)

- Zheng, Li, Lu, Wang, Wang & Meng, *Scientific Data* (Nature), DOI `10.1038/s41597-026-07227-x`. Page dates include 2026-04-24; the figshare record was published 2026-06-30.
- Fetched with curl (a cookie jar was needed; WebFetch got a 303 to the idp login).
- Data: figshare `10.6084/m9.figshare.28736762`. The API (`https://api.figshare.com/v2/articles/28736762`) shows **licence CC BY 4.0**, v1, with 9 files `India_MRIO_2011.xlsx` … `India_MRIO_2019.xlsx` at about 45–48 MB each. Code: `https://github.com/HeranZheng/India-MRIO`. Also on CEADs.
- Structure: 66 sectors × 32 states, "aligned with India's official national supply–use tables". Current prices, **Rs lakh**. Five final-demand categories (PFCE, GFCE, GFCF, valuables, change in stocks). Entropy-based estimation, with RAS for the trade matrices. Imbalances are held under a 5% tolerance ("controlled within 5% as the tolerance benchmark").
- **Use for us:** a consistent annual IO time series for 2011–2019 (old series). It can support the "top ~50 flows" time series and give sanity bounds on how stable the coefficients are. It is not a SAM (value added is a single row).

---

## 2. Fiscal and other multiplier estimates (for Phase 4 cross-checks)

| Study | Method, sample | Capex multiplier | Revenue / current multiplier | Evidence |
|---|---|---|---|---|
| Jain & Kumar (2013), RBI WPS (DEPR) 07/2013, "Size of Government Expenditure Multipliers in India: A Structural VAR Analysis" | SVAR | Centre+States: impact 1.29, **peak 3.56 in year 4**; Centre: impact 0.39, peak 0.85 (yr 4); States: impact 2.13, cumulative peak **7.61** (yr 3) | Centre+States impact 0.37 (falls below baseline in yr 2); Centre impact 0.19; States 0.60 | WebFetch `https://rbi.org.in/scripts/PublicationsView.aspx?Id=15369` (18 Sep 2013) |
| RBI (2019), Monetary Policy Report, as quoted in RBI Bulletin Dec 2020, "Government Finances 2020-21: A Half-Yearly Review" (Agarwal, Padhi, Goyal, Behera, Misra) | not stated in the Bulletin | "for the central government, it is **2.45 in period t and 3.14 in period t+1**, while for state governments it is **close to 2**" | — | WebFetch `https://rbi.org.in/Scripts/BS_ViewBulletin.aspx?Id=19959` (24 Dec 2020). Primary MPR box **not fetched** (the RBI MPR listing uses JS postbacks) |
| Misra, Behera, Seth, Sood, RBI Bulletin June 2021, "Fiscal Framework and Quality of Expenditure in India" | review | "capital expenditure multiplier is also known to be higher than 2 in India"; capex peak effect after 2–3 years | revenue expenditure effects last "about a year" | WebFetch `https://rbi.org.in/scripts/BS_ViewBulletin.aspx?Id=20322` (16 Jun 2021). The rbidocs PDF of the same article returned a **CAPTCHA** page |
| Bose & Bhanumurthy (2013/2015), NIPFP WP 2013-125; *Margin* 9(4) 2015 | structural macroeconometric model, 1990–2012 | **2.45** | transfers 0.98, other revenue expenditure 0.99; tax multipliers ≈ −1 | PDF `https://www.nipfp.org.in/media/medialibrary/2013/09/WP_2013_125.pdf` (HTTP 200, 23 pp.), abstract quoted |
| Bose & Banerjee (Sept 2025), NIPFP WP 436, "Fiscal multipliers in India: A macro-model linking human development, growth and distribution" | demand-side macro model, 1990–2022 | cites 2.45 (Bose & Bhanumurthy 2015) | **social spending multiplier 1.67** | PDF `https://www.nipfp.org.in/media/documents/WP_436_2025.pdf` (HTTP 200, 46 pp.) |
| Mishra & Adiraju (2025), *IJEPEE* 21(1): 64–90 | SVAR, five multipliers | "impact multipliers in the range 0.23 to 1.85 and cumulative multipliers in the range 0.45 to 5.45" | — | WebFetch `https://www.inderscience.com/info/inarticle.php?artid=145416` (paywalled) |
| Esha Swaroop, IES seminar paper, "Estimation of Expenditure Multiplier for India" | ? | ? | ? | **Failed:** `https://www.ies.gov.in/...` TLS `SEC_E_WRONG_PRINCIPAL` (certificate name mismatch). Unverified |
| IMF | — | — | — | No India-specific IMF multiplier estimate found. IMF CR 25/55, fetched, turned out to be the FSAP FSSA and has no multipliers. CR 25/54 returned **403** to curl. Unverified |

**SAM (Leontief-type) output multipliers from published Indian SAMs.** These are *not* comparable with the fiscal multipliers above:
- NCAER 2021-22: 2.4–6.7 by broad sector.
- CSEP 2019-20: 1.6–6.4 by sector (sum across all endogenous accounts).

A SAM "output multiplier" sums gross output across all endogenous accounts. It is not a GDP multiplier, so it is much larger than 1–3. Our Phase 4 validation must compare like with like: a GDP / value-added multiplier from our SAM against the ~1–3.5 range of the macro and SVAR capex estimates.

**Remittance multipliers:** I found no India-wide quantified remittance multiplier.
- Shah (2024), *International Economics and Economic Policy*, DOI `10.1007/s10368-024-00611-1`: local projections over 1997Q2–2019Q4. It finds asymmetric effects (increases act immediately, decreases with a 6–8 quarter lag) but gives no multiplier value. Paywalled; abstract fetched via curl.
- Kannan & Hari (2020), *IJLE*, DOI `10.1007/s41027-020-00280-z`: a Kerala remittance series for 1972–2020 and "Modified State Income". Paywalled; abstract only.
- MOSPI-sponsored Odisha study (2016): `https://mospi.gov.in/sites/default/files/publication_reports/Report_The_Impact_of_Remittance.pdf` (HTTP 200, 101 pp.). It is qualitative about the "multiplier effect".
- A web-search snippet cites "Oxford Economics ... average multiplier of 0.4" (global, not India). Unverified and not usable.
- **Conclusion:** the remittance multiplier will have to come from our own SAM, with the gap in the literature logged.

---

## 3. Balancing methods used for Indian SAMs, and documented issues

- **Cross-entropy:** IFPRI Nexus SAMs 2017-18 and 2022-23 (GAMS, Robinson, Cattaneo & El-Said 2001). Macro-level imbalances are closed with named residuals first (foreign savings, household and government savings, transfers).
- **RAS:** NCAER 2021-22 SAM; CSEP 2019-20 (RAS projection of the IOT from 2015-16); India MRIO (trade matrices). Older IEG/NCAER SAMs used pro-rata scaling.
- **The PFCE gap between NAS and NSS/HCES.** This is the biggest documented issue for household accounts.
  - The Adhikari Committee report on PFCE (MOSPI, 2015), `https://mospi.gov.in/sites/default/files/publication_reports/Adhikari_Committee_PFCE_22may15.pdf` (HTTP 200, 97 pp.): "the difference has increased from 5 per cent to 45 per cent" (1972-73 to 2011-12). For 2011-12, NSS ₹28,29,566 crore vs NAS ₹51,67,446 crore, a −45.24% difference; food −28.29%, non-food −54.77%.
  - Kumar & Seth, EPW 61(5), 31 Jan 2026, "Bridging the Consumption Gap in India's Statistics": the divergence "widened from about 5% in 1972–73 to nearly 54% in 2023–24". Paywalled; figure taken from the page summary via WebFetch.
  - **Implication:** HCES can give only the *distribution* of consumption across quintiles and commodities, never the level. The level must come from NAS PFCE. Every prior SAM does this: IEG 2007-08, IFPRI (HCES shares scaled to NAS), NCAER (NSS 2011-12 shares). The non-food gap is much larger than the food gap, so scaling uniformly across items biases the distribution. This belongs in `ISSUES.md` and in the estimation method in the gap map.
- **Stale coefficients:** every prior SAM mixes years. IFPRI 2022-23 uses SUT 2019-20; NCAER 2021-22 uses SUT 2018-19 and NSS 2011-12; CSEP 2019-20 uses IOT 2015-16. The new base-2022-23 SUTs (2022-23, 2023-24) let us avoid this for the first time.
- **Trade classification:** as CSEP documents, IOT merchandise exports are lower than MoC/RBI figures because trade and transport margins on exports are reallocated to services.
- **Statistical discrepancy:** under the old series, the NAS carried a production–expenditure discrepancy that prior SAMs absorbed. The new series says it is eliminated at the final estimate. Unverified for the latest *provisional* year, which may still carry one (to be confirmed by the NAS agent).

---

## 4. Fetch log: everything tried

| URL | Tool | Result |
|---|---|---|
| dataverse.harvard.edu/api/datasets/...LDUDTE | curl | 200 JSON (metadata, terms, file list) |
| dataverse.harvard.edu/api/access/datafile/10595685 | curl | **400 guestbook required** |
| dataverse.harvard.edu/api/datasets/...NYVJX8 | curl | 200 JSON |
| dataverse.harvard.edu/api/search (India SAM; Indian State) | curl | 200 |
| cgspace.cgiar.org/items/eef0cc88-... | WebFetch | 200 |
| cgspace REST API items, bundles, bitstreams (2022-23, 2017-18, release note 2025) | curl | 200 |
| csep.org technical-note page | WebFetch + curl | 200 |
| csep.org/wp-content/uploads/2023/11/Developing-...-2.pdf | curl | 200 (10.2 MB) |
| cstep.in publication page | WebFetch + curl | 200 |
| cstep.in/wp-content/uploads/2025/06/CSTEP-SAM_2017-18-3.xlsx | curl | 200 (230 KB, probe only) |
| cstep.in/.../Social-accounting-matrix-...pdf | curl | 200 |
| iegindia.org/upload/publication/Workpap/wp326.pdf | curl | 200 |
| journals.sagepub.com/doi/10.1177/00252921241284278 | WebFetch | **403** |
| ideas.repec.org (Margin article; NCAER WP160) | WebFetch | 200 |
| www.ncaer.org/... | curl | **TLS fail (schannel SEC_E_ILLEGAL_MESSAGE, exit 35)** |
| ncaer.org/publication/... and NCAER_WP160_Feb-2024.pdf | curl | 200 |
| nipfp.org.in WP_2013_125.pdf and WP_436_2025.pdf | curl | 200 |
| rbidocs.rbi.org.in/.../03AR_16062021...PDF | curl + WebFetch | **CAPTCHA page ("What code is in the image?")**; not bypassed |
| rbi.org.in BS_ViewBulletin Id=20322, 19959, 20691; PublicationsView Id=15369, id=19331 (= MPR Oct 2019) | WebFetch | 200 |
| m.rbi.org.in/...id=19331 | WebFetch | 302 to rbi.org.in home |
| rbi.org.in MPR listing | WebFetch | links are JS postbacks; MPR April 2019 not reachable |
| rbi.org.in/Scripts/Disclaimer.aspx | curl | 200 (terms: © RBI, all rights reserved; deep-linking needs permission) |
| www.ies.gov.in/pdfs/Seminar_Paper_EshaSwaroop.pdf | curl | **TLS certificate name mismatch (exit 60)** |
| imf.org CR 25/54 and 25/55 PDFs | curl | **403**; 25/55 via WebFetch saved as binary, parsed locally = FSSA (not relevant) |
| nature.com/articles/s41597-026-07227-x | WebFetch 303 to idp; curl with cookie jar | 200 |
| api.figshare.com/v2/articles/28736762 | curl | 200 |
| link.springer.com (remittance papers; JES SAM 2007-08) | WebFetch 303; curl with cookies | 200 (abstracts) |
| mospi.gov.in SUT 2022-23/2023-24 press release PDF | curl | 200 |
| mospi.gov.in Adhikari Committee PDF | curl | 200 |
| mospi.gov.in remittance (Odisha) report | curl | 200 |
| epw.in 2026 consumption-gap commentary | WebFetch | 200 (paywalled full text) |
| inderscience.com artid=145416 | WebFetch | 200 (abstract) |
| levyinstitute.org Appendix_B.pdf | curl | 200 |
| iioa.org 27th conference SUT-to-SAM paper | WebFetch (binary, saved) + local parse | 200 |

---

## 5. Recommendations for Phase 0 synthesis

1. **Template:** use the IFPRI Nexus layout (activities / commodities / factors / enterprises / households / government plus separate tax accounts / s-i / dstk / RoW). Our SAM should then:
   - split enterprises into NFC-public, NFC-private and FC, as Section 4 of SPEC requires;
   - split government into Centre and States;
   - add a financial / flow-of-funds block that IFPRI does not have.

   IFPRI's 10 rural/urban × quintile households match SPEC §4 exactly. Their 42-sector list is too agri-heavy for our purpose; for industry and energy detail, the NCAER and CSTEP splits are better guides.
2. **Cross-check targets for Phase 2:** the IFPRI 2022-23 macro SAM shares, in particular:
   - household savings rate 22.5%;
   - government saving −₹9,855 bn;
   - income shares by quintile (Table 10);
   - GDP shares by sector (Table 9).

   Compare shares, not levels, because of the series change.
3. **Phase 4 cross-check band:**
   - Capex GDP multiplier: ~2–3.5 (RBI 2.45 / 3.14; NIPFP 2.45; Jain & Kumar peak 3.56).
   - Revenue expenditure multiplier: ~0.2–1.0.
   - A fixed-price SAM multiplier with excess capacity will overshoot these. That is expected, and we should explain it rather than "fix" it.
4. **Access requests:**
   - IFPRI Dataverse guestbook for DVN/LDUDTE and DVN/NYVJX8. Needs the owner's identity details; the licence is CC-BY-4.0 for the paper, and the dataset terms are IFPRI's.
   - Optional: the Margin (SAGE) supplementary file for the NCAER SAM, which may need institutional access.
   - Optional: EPW 2026 article (₹59).
