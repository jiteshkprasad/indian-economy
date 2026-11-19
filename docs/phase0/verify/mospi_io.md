# Phase 0 verification: family `mospi_io` (MoSPI SUT/IOTT, ASI, IIP, CPI, WPI/PPI, Energy, classifications)

Verifier: independent adversarial agent. Date: 2026-09-29 (checks run about 07:00 UTC, which is 12:30 IST).
Method: I re-fetched every finder URL myself with curl (Git Bash) and WebFetch. I opened and parsed the xlsx and PDF files in a scratch folder outside the repo, and queried the MoSPI SPA JSON backend and api.mospi.gov.in. WebSearch was not available (the session search budget was exhausted), so every finding below comes from direct fetches.

## Headline results

1. **Confirmed.** The latest official SUTs are for **2022-23 and 2023-24** on the **2022-23 base**: 155 products x 67 industries, current prices, Rs crore. They were first released on 2026-05-15 and replaced with revised files on 2026-08-31 to match NAS 2026. I recomputed the GDP identities from the xlsx and they close exactly with zero statistical discrepancy:
   - GVA 2,38,23,136 + product taxes 27,53,061 + import duty 2,10,139 - product subsidies 6,09,335 = **GDP 2,61,77,001** (2022-23). This equals the "Updated" figure in the NAS 2026 press release.
   - Expenditure side: PFCE 1,49,38,852 + GFCE 29,34,060 + GFCF 84,52,956 + CII 1,74,121 + valuables 3,60,668 + exports 62,78,722 - imports 69,62,377 = 2,61,77,001.
   - 2023-24 GVA is 2,64,05,480 and GDP is 2,90,73,287. Both match note Table 9.2 and the NAS 2026 press release.
2. **Corrected: ASI 2024-25 is not overdue.** The MoSPI Advance Release Calendar 2026-27 ("updated till August 2026", served by `GET /api/documents/get-latest-release-calender`) schedules "**29th Sep – Annual Survey of Industries (ASI) results 2024-25**", which is today. At 12:35 IST it was not yet in the release feed or in the API year list (the API still tops out at 2023-24). The finder's claim that it "appears overdue" is wrong. The pipeline should re-check after 4 PM IST today.
3. **Corrected: access method.** Today every `www.mospi.gov.in/uploads/...` and `/sites/default/files/...` file returned HTTP 200 to plain curl with no User-Agent, to a python-requests UA, and to WebFetch (the SUT note PDF came back as 200 binary). I could not reproduce the finder's claim that Sec-Fetch headers are required or that WebFetch gets 403. The limits that do still apply:
   - The SPA's `/api/...` endpoints need POST (GET returns 403). The exception is `documents/get-latest-release-calender`, which needs GET with CORS-style headers.
   - PIB (`pib.gov.in`) returned 401/403 to plain curl and 403 to WebFetch. It returned 200 only with full browser navigation headers plus a cookie jar.

   This WAF behaviour may be intermittent, so the pipeline should retry, log failures, and never spoof around an actual block.
4. **Corrected: the SUT xlsx does carry a unit label.** Every sheet of both new-series files has `'Values in Rs. Crore'` in row 1 (column index 75 or 76). The finder said "No unit label in the xlsx".
5. **Corrected: "silently replaced" is overstated.** The August revision was announced in the NAS 2026 press release (31 Aug 2026, para 9: "The Supply and Use Tables (SUTs) for 2022-23 and 2023-24 have also been updated") and in note §2.2. What is true is that the file itself has no version label, and the May press-release totals no longer match the files:
   - Supply at PP 2022-23: the press release says 627.18 lakh crore; the revised file gives 628.01.
   - Supply at PP 2023-24: the press release says 669.88; the revised file gives 671.79.

   The chapter list now shows only the `_(1)` files, with `published_date` 2026-08-31.
6. **Corrected: the Eight Core Industries index now has nine components.** Iron Ore was added in the 2022-23 base, with weight 4.905. The weights are Coal 5.596, Natural Gas 3.841, Crude 7.43, Refinery 22.572, Fertilizers 2.731, Steel 17.584, Cement 4.41, Electricity 30.932 and Iron Ore 4.905. The August 2026 press release is dated 21 Sep 2026. The finder's unopened entry listed eight components and "coverage unverified". The xlsx `eight_core_infra/Core_Industries_2022_23_20260921.xlsx` exists on `ici_download_data.asp`.
7. **Corrected: `NMDS_SUT.xlsx` is old-series metadata.** It cites "Sources and Methods 2012" and lists NIC 2008 and NPC-MS as the classifications. It should not be listed under the 2022-base SUT source.
8. **Corrected: Energy Statistics Chapter 7 has extractable text.** pdftotext returned 38 KB of text, so the finder's "appears image-based" is wrong. Chapter 9 contains **Physical Supply and Use Tables for energy for 2023-24 and 2024-25(P)** (Tables 9.2A/B and 9.3A/B) plus physical asset accounts for 2024-25(P). It has no monetary energy SUT.

## Source-by-source verdicts

| id | verdict | notes |
|---|---|---|
| mospi_sut_2022base | corrected | Three URLs (the chapter list and the three `_(1)` files) returned 200. Parsed: 155 numbered products, 67 industries, identical industry headers in Supply and Use. Supply sheet columns: Supply at BP, Imports, CIF Adj, Imports after cif adjustment, Import Duty, Product taxes, Subsidy on Products, TTM, Supply at PP. Use sheet columns: 67 industries, **Intermediate Consumption (total)**, PFCE, GFCE, GFCF, CII, Net Acquisition of Valuables, Export, Total Use at PP. The VA block has GVA (production), Production Taxes less Subsidies, CFC, CoE, Operating Surplus, and GVA (income). Corrections: (a) a unit label is present; (b) the revision was announced, not silent; (c) NMDS_SUT.xlsx is old-series metadata; (d) no Sec-Fetch headers were needed today. The NIC contradiction is confirmed: the MoSPI copy of the press release says "adoption of updated classifications like NIC 2025", while note §5.2 says "NIC 2008 and NPCMS 2011 (Revised)/ NPCSS have been used". The PIB URL itself was not reproducible (401 to curl, 403 to WebFetch); the MoSPI-hosted PDF copy was used instead. SHA-256: 2022-23 `415955ee…df19`, 2023-24 `6fbaa0e9…dafd`, note `054e062c…dcdb`. |
| mospi_sut_2011base | confirmed | All 11 xlsx files and 5 notes returned 206 with the correct MIME type on ranged GETs. SUT 2011-12 and 2015-16 are in "Value in Rs Lakh"; 2021-22 is in "Values in Rs. Crore". Each has 140 numbered products. The 2011-12 file (misspelt "balaced") has both Supply and Use sheets. |
| mospi_iott_2007 | corrected (minor) | Binder1.pdf: 206, 16,188,160 bytes. It contains Matrix-1 (commodity x industry absorption), Matrix-2 (make), Matrix-6 (**commodity x commodity**) and Matrix-7 (Leontief inverse). It has 130 sectors at factor cost, is based on NAS 2011 (2004-05 series), and the cover year is 2012. The finder's "130x130 commodity-by-commodity absorption matrix" mixes up two matrices: the absorption matrix is commodity x industry, and the separate commodity x commodity matrix is Matrix-6. Nothing in MoSPI's publication list (252 items) is an IOTT after 2007-08. |
| csep_iott_2015 | confirmed | Both URLs returned the same 2,245,434-byte PDF. It is labelled "Brookings India … Draft for comments" and uses a "131-Sector Structure". The only rights-like text is "All content reflects the individual views of the authors". No licence was found. |
| mospi_asi | corrected | The API filter returns 16 years (2008-09 to 2023-24) and 57 indicators; getASIData returns 2023-24 rows at NIC-2008 3-digit. NADA: DDI-IND-NSO-ASI-2023-24, "Last modified Feb 25, 2026", login required; `/NADA/index.php/terms` returns 404. The 30 Sep 2025 press note confirms Vol I at NIC 2008 2/3/4-digit and Vol II products and materials by **NPC-MS 2011 (Revised)** as an e-publication. The "2024-25 overdue" claim is wrong because the release calendar gives 29 Sep 2026. The ASI 2024-25 schedule and instruction manual were published 2026-02-09 (publications 2786 and 2787); I did not open them to check their NIC version. |
| mospi_iip_2022base | corrected (minor) | The API returns 123.3 / 8.0% for August 2026; April 2023 = 100.4; old base 2011-12 also works (March 2026 = 173.2). First release 1 Jun 2026 confirmed: "The National Industrial Classification 2025 will be used", 463 item groups, and linking factors Mining 1.1890, Manufacturing 1.3700, Electricity 1.8495, General 1.3834, with none for water/sewerage. The "1,042 products" figure is **not in the first press release** (grep found no match), so it is unverified. The swagger enum still lists only 2011-12, 2004-05 and 1993-94, which confirms the finder's point. |
| mospi_cpi_2024base | confirmed | The API returns Rural 109.27/5.23, Urban 108.07/4.31 and Combined 108.74/4.82. limit<10 returns a 400 error, and getCPIIndex with base 2024 returns "No Data Found". The January 2026 press release confirms HCES 2023-24 weights, COICOP 2018 and 358 items, with linking factors R 0.5222, U 0.5320, C 0.5267 and a back series from January 2013. December 2025 is the final month on base 2012. The August press release is dated 14 Sep 2026. |
| oea_wpi_ppi_2022base | confirmed | All OEA files returned 200. WPI xlsx: 957 items, Apr-23 to Aug-26, All = 110.8. OPPI: 161 rows. Trial IPPI: from March 2026, 24 rows (manufacturing). The SPPI covers 7 services; **Air (Passenger) has no index before FY 2025-26** (price reference period 2025-26). PIB 2272872 (15 Jun 2026): linking factor All Commodities 1.53; "released for five years … and will be discontinued thereafter"; crude petroleum & natural gas shifted to Fuel & Power. PIB 2267963 (2 Jun 2026): OPPI and IPPI weights come from SUT 2022-23. `disclaimer.asp` returns 404. |
| mospi_energy_statistics | corrected (minor) | The press release is dated 30-Mar-26, 33rd edition, TPES FY 2024-25 = 9,32,816 KToE. Publication 2817 has 24 files. The API has data for 2012-13 to 2023-24; 2024-25 and 2011-12 return "No Data Found". The 2023-24 coal final consumption figure of 200,947.38 KToE is reproduced. Corrections: Chapter 7 has text; Chapter 9 has physical energy SUTs for 2023-24 and 2024-25(P), which is useful for a satellite account. Omitting `use_of_energy_balance_code` gives a 500 error with a Postgres error leak. |
| mospi_esankhyiki_api | confirmed | GitHub reports licence MIT, pushed 2026-09-28T09:49Z, and 28 swagger specs. The llms.txt quote is exact. Unauthenticated GETs return 200. mcp.mospi.gov.in returns 405 to a GET (expected for MCP). The NAS swagger says base 2022-23 supports the "Current" series only. |
| mospi_classifications | corrected (minor) | The NIC 2025 PDF (5,143,225 bytes, 323 pages) has its concordance at 4-digit NIC-2025 <-> NIC-2008, starting at PDF page 257 (printed pp. 239-291). The press note (18 Nov 2025) confirms the 6-digit code replaces the 5-digit one and that NIC 2025 aligns with ISIC Rev.5. `NPCMS_2011_revised.pdf` is the **National Product Classification for Manufacturing Sector 2011 (Revised), Dec 2015**: manufacturing and goods only, 7-digit, with no HS concordance inside. NPCSS was not found anywhere on the site (unverified). No SUT-product to NPCMS/NIC mapping file exists in publication 847. |
| oea_ici_2022base | corrected | See headline point 6. Base 2022-23 and 9 industries confirmed. Download xlsx: `Core_Industries_2022_23_20260921.xlsx`; the old series is in `Core_Industries_2011_12_20260720.xlsx`. |

## Key-fact checks

- Base year 2022-23, released 27 Feb 2026 and updated 31 Aug 2026: **confirmed** by the Sources & Methods press note (text quoted exactly).
- NAS 2026 has FE for 2022-23 and 2023-24, FRE for 2024-25 and PE for 2025-26. GDP at current prices: 2,61,77,001 / 2,90,73,287 / 3,17,98,524; 2025-26 PE is 3,45,36,796. **Confirmed.**
- SUT dimensions and dates: **confirmed**.
- Zero discrepancy: **confirmed** by recomputing from the xlsx.
- VA block sums: **confirmed** exactly (CoE 86,53,668.9; OS/MI 1,16,54,811.7; CFC 35,84,380.4; production taxes less subsidies -69,725.4).
- NIC contradiction: **confirmed**.
- No IOTT after 2007-08: **confirmed**. No IOTT appears among the 252 publications.
- Back series expected by December 2026: **confirmed** (FAQ line 55: "series is expected to be released by December 2026").
- IIP, CPI and WPI facts: **confirmed**. IIP "1,042 products" is **unverified**.
- ASI latest is 2023-24: **corrected**. ASI 2024-25 is scheduled for 2026-09-29 and was not yet published at the time of checking.
- ASI microdata needs a free login: **confirmed**.
- The API works without a key: **confirmed**.
- Copyright policy: **confirmed** word for word (fetched via `POST /api/copy-right-policy/get-copy-right-policy-data`). GSDD 2026 is not present in the acts/policies, public documents or announcement lists.
- NSDP base years: **confirmed** (lines 190-194).
- Energy Statistics 2026: **confirmed**.
- NIC concordance: **confirmed**.

## Missed sources (this family)

1. **MoSPI Advance Release Calendar 2026-27.** URL: `https://www.mospi.gov.in/uploads/documents/releaseCalender/1788266096813-ARC%202026-27%20updated%20till%20August%202026.pdf`, found via `GET /api/documents/get-latest-release-calender`. It gives ASI 2024-25 on 29 Sep 2026 and "First Revised Estimates of GDP for FY 2025-26 and Final Estimates of GDP for FY 2024-25" on 26 Feb 2027. A SUT for 2024-25 would logically follow the FE (inference). The pipeline scheduler needs this calendar.
2. **Index of Services Production (trial, base 2024-25).**
   - Endpoint: `/api/isp/getISPRecords`.
   - Release history: first release 14 Jul 2026; June 2026 index released 31 Aug 2026; ARC lists another ISP release on 29 Sep 2026.
   - Relevance: the only official high-frequency volume indicator for services, which are about 52% of supply at basic prices.
3. **Sources and Methods for Compilation of NAS (2026).** Publication 2865, released 21 Sep 2026. This is the authoritative method document for the 2022-23 series SUT and GVA compilation, and it is needed to map SUT industries to NAS sectors.
4. **Energy Statistics India 2026, Chapter 9.** Physical energy SUT for 2023-24 and 2024-25(P). The finder only mentioned "SEEA-Energy accounts".
5. **Report of the Expert Committee on Energy Statistics.** Publication 2848, press release 3 Aug 2026. It may change energy-balance methods.
6. **Also relevant but outside this family:**
   - ASUSE 2025 (unincorporated enterprises). Relevant for mixed income and informal input structure.
   - ASISSE (incorporated services survey), launched April 2026. No data yet.
   - Report of the Sub-Committee for Constant Price Estimates (20 Feb 2026). Relevant for deflator mapping.

## Reference-year implications

- The only official SUT years on the current base are 2022-23 and 2023-24. The Aug-2026 vintage is integrated with the NAS Final Estimates.
- **2023-24 is the latest year with an official product x industry structure and zero discrepancy.** 2024-25 is only at FRE; its FE is due 26 Feb 2027.
- ASI 2024-25 arrives today, but it does not change the SUT year.
- Energy has a physical PSUT for 2023-24 (final) and 2024-25 (provisional).
- Price indices (IIP, CPI, WPI/PPI) run monthly to August 2026 and cover 2023-24 fully. CPI 2024 covers it only through the back-linked general index.

## Issues to log (ISSUES.md candidates)

- The PIB press release pages are not machine-fetchable without browser emulation, so use the MoSPI-hosted PDF copies.
- SUT files carry no version stamp. Hash each file on every run and alert on change. The May vintage is not archived publicly.
- The Energy API returns a 500 error with a leaked SQL error when a required parameter is missing. Validate parameters client-side.
- NPCSS could not be located. No official SUT-product <-> NPCMS/NIC/HS concordance file was found.
- GSDD 2026 (the reuse terms cited by MoSPI's copyright policy) could not be found. This is an access and clarification request for the owner.
- `eaindustry.nic.in/disclaimer.asp` returns 404, so no OEA licence statement was found.
