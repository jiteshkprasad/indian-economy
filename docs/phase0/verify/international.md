# Verification notes: international (international and cross-country datasets)

Verifier: independent adversarial verifier (did not produce the recon). Date of checks: 2026-09-29.
Method: `curl` with an ordinary browser User-Agent, SDMX/REST API calls, and WebFetch for a few HTML pages. Small probe files were saved to the session scratchpad only. Nothing was written to `data/`. The web-search quota was exhausted (200/200) before this run, so every check below comes from a direct fetch.

## Headline findings (what changes for the SAM)

1. **The ADB MRIO licence is verified and open.** The recon marked it "unverified" and filed an access request, but that request is not needed. `https://kidb.adb.org/terms` (200) says: "Unless otherwise indicated, all data and metadata provided in ADB's Key Indicators Database System (KIDB) Online may be copied, downloaded, distributed, adapted, duplicated, linked, displayed or included in other products for commercial and noncommercial purposes at no cost." Required attribution: "Asian Development Bank: Key Indicators Database Online (https://kidb.adb.org). Accessed on [date]." Sub-licences must pass the attribution requirement on. `adb.org/terms-use` (200) incorporates the KIDB terms by reference ("for the Key Indicators Database … ADB has specific terms of use, which are hereby incorporated by reference"). The MRIO files are served from `kidb.adb.org/download/mrio-file/{id}`.
2. **ADB India IOT: the year convention and base are now established, not just inferred.** The 2022 sheet's value added (sum of r64 over c1-c35) is 3,135,712 $mn. Multiplied by the WDI calendar-2022 exchange rate (PA.NUS.FCRF 2022 = 78.6045), that gives ₹246.48 lakh crore. The UN AMA (Jan 2026) old-base India "Total Value Added" for 2022 (FY2022-23) is ₹246.467 lakh crore, a 0.005% difference. New-base FY2022-23 GVA (WDI NY.GDP.FCST.CN) is ₹237.64 lakh crore. **So ADB's "2022" is FY2022-23, on the old 2011-12 base, converted at the calendar-year average rate.** For 2024: 3,598,908 × 83.669 = ₹301.1 lakh crore vs old-base ₹300.2 lakh crore (0.3%, a vintage difference). Also: rows r62, r63 and `trs` are **all zeros** for India, so direct purchases abroad and by non-residents are not in the IOT. **No 2025 table yet.** As of 2026-09-29 the newest files are still "Updated on August 2025" (2024 tables). The usual August cycle has slipped this year.
3. **FIGARO includes India, but its licence is narrower than claimed.** The Eurostat SDMX structure for `NAIO_10_FCP_II1` lists `IN` in both C_ORIG and C_DEST, with UNIT `MIO_EUR`. The JSON API (`naio_10_fcp_ii4`, "2022 and onwards") returns India data for 2022, 2023 and 2024, updated `2026-07-20T11:00`. **Licence correction:** the Eurostat copyright notice says: "The following Eurostat data and documents may not be reused for commercial purposes, but non-commercial reuse is possible without restriction: … Data for countries other than: Member States of the EU, … EFTA, official EU acceding and candidate countries. Examples are data for the United States of America, Japan or China." So FIGARO's India cells are **non-commercial only**, not plain CC BY 4.0. **FIGARO also looks like the only IO source already on India's new base.** India VA (D1 + B2A3G + D29X39, c_orig = DOM) is €2,784,699 mn (2022), €2,871,416 mn (2023) and €3,111,270 mn (2024). At ECB EUR/INR annual averages (82.686, 89.300, 90.556) that gives ₹230.3, ₹256.4 and ₹281.7 lakh crore. Calendar-year new-base GVA (0.75·FY_t + 0.25·FY_t−1 from WDI NY.GDP.FCST.CN) is ₹232.3, ₹256.8 and ₹282.2 lakh crore; old base would be about ₹300 lakh crore for 2024. This is an **inference** (medium confidence): new base, calendar-year converted.
4. **OECD ICIO 2025 must be on the old base, not just "probably".** The page says "The current database, released mid-January 2026 … No further revisions are anticipated". MOSPI's new series was released on 27 Feb 2026, after that. All 2025-edition files on webfs-sti (zip, ReadMe, annex, 3.3 GB R zips, IOT files) have `Last-Modified: Mon, 18 May 2026`. That is a whole-folder re-upload, not a silent single-file change. The file inside `IOTs/2025/IOTs_VA.zip` is dated 2026-01-20. India rows are FY-based: annex footnote "* India (1 April to 31 March)", so ICIO "2022" = FY2022-23.
5. **Missed source: OECD national IOTs 2025 edition.** It gives the value-added split by industry for India (LABR compensation of employees, CFC, NOPS, OTXS), 1995-2022, 50 industries. See "Missed sources" below. This is the only free source found with a factor split by industry for India after WIOD (2014).
6. **WDI mixes year bases and is one to two MOSPI vintages behind.** National accounts are FY (metadata). But `BN.CAB.XOKA.CD` for 2022/2023/2024 (−79.05 / −31.96 / −32.02 bn) is **identical** to IMF BOP calendar-year CAB. So WDI BOP series are **calendar year**, and the 2025 gap (−16.49 vs IMF −20.23) is a vintage difference (WDI 13 Jul vs IMF 28 Sep). The recon left this "unresolved"; it is now resolved. WDI GDP 2025 = 345,471,567,964,600 = ₹3,45,47,157 crore. That is the **27 Feb 2026 SAE** value, not the 5 Jun PE (3,46,35,638) or NAS 2026 of 31 Aug (3,45,36,796), per `verify/mospi_nas.md`. WDI 2022 = 2,61,17,627 is the pre-NAS-2026 value (now 2,61,77,001).
7. **BIS licence has a translation clause** that matters for the planned Hindi site. `data.bis.org/help/legal` says: "if the statistics will be translated into another language, a statement must be included in your publication or product that the translation is not an official BIS translation". The recon omitted it.
8. **EXIOBASE is newer than claimed.** The Zenodo API (`/api/records/15689391/versions`, 200) shows the latest version **3.10.2, published 2026-05-13** (record 20051562), with IOT files for **1995-2024**. The changelog says "v3.10.2 - Released May 2026"; "v3.10.1 - Released March 2026"; v3.10.0 "Update to data to end year of 2022, including: Figaro (aggregate SUT) data to 2021; Bilateral trade data to 2022". Licence text in 3.10.2: "EXIOBASE v3.9 and later is released under a customized derivative of the CC-BY-SA-NC license … Commercial licenses … are under development." The exiobase.eu page still says CC BY-SA 4.0, so the contradiction remains. The Zenodo record (the distribution point) should govern.
9. **Comtrade monthly data now runs to 2026-07,** not 2026-06. The 202607 preview returned 1 record (X = 44,302,522,916 USD); 202608 returned 0.

## Access behaviour (re-tested)

| Probe | Result |
|---|---|
| oecd.org ICIO page, curl with browser UA | 200 (1.49 MB) |
| webfs-sti.oecd.org `ICIO/2026/…` | 404, so there is no 2026 edition folder |
| kidb.adb.org/globalization/current | 200, Inertia `data-page` JSON with 109 files |
| data.adb.org dataset page | 403 "Just a moment" (Cloudflare). Not bypassed and not needed (KIDB terms apply). |
| kidb.adb.org/terms | 200, licence text quoted above |
| api.worldbank.org v2 | 200. One multi-call batch timed out in a 120 s shell; single calls fine |
| datacatalog.worldbank.org via curl | 308. WebFetch works. The catalog API gave 429 once. |
| api.imf.org/external/sdmx/2.1 | 200, no key, 221 dataflows |
| DIP with 6 key parts | 403. The correct key has 5 dimensions (COUNTRY.DV_TYPE.INDICATOR.COUNTERPART_COUNTRY.FREQUENCY) |
| www.imf.org/external/terms.htm, /en/about/copyright-and-terms, data.imf.org | 403 "Access Denied" (Akamai), also via WebFetch |
| dataservices.imf.org | curl exit 6 (DNS). Confirmed dead. |
| comtradeapi preview | 200. Full `data/v1/get` gives 401 "missing subscription key" |
| stats.bis.org api v1 | 200, no key |
| sdmx.oecd.org BaTIS | 200 with the finder's 8-dimension wildcard. A partially-specified key (`IND.W.X+M.S.S.A..`) gave **500 Internal server error** |
| Eurostat SDMX/JSON API | 200, no key |
| zenodo.org API | 200 for me (the recon got 403, which was transient) |
| mospi.gov.in press note URL in recon key fact | **403** for me. The "-F" variant is reported as 200 by `verify/mospi_nas.md` |

## Per-source verdicts

### oecd_icio_2025: confirmed (minor corrections)
- Page text is confirmed verbatim (80 economies + RoW; "released mid-January 2026 … second revision … end of August 2025 … mid-October 2025"). Also: "No further revisions are anticipated."
- 2016-2022_SML.zip: 166,241,019 bytes, Last-Modified 18 May 2026 14:52. **Correction:** every 2025 file shares the 18 May 2026 timestamp (ReadMe 14:52:08, annex 14:56:37, EXT R zips 3.3 GB each). It was a folder-wide re-upload. Still record checksums.
- ReadMe: "2025 edition", "Data are expressed in current USD, million", "36 IND India", 50 activities A01…T, at basic prices. TLS = "Taxes less subsidies on intermediate and final products".
- Annex Table 3: `IND* 0000000000000000111111111000` = SUT-only 2011-2019, none for 2020-2022. Footnote "India (1 April to 31 March)".
- Correction to access: "Rdata-econA/B/VB/Z/Other" are the extended-version R files by year block, not per-economy files.
- Base year: old 2011-12 base is **certain** by timing (see headline 4), not just "implied".
- Licence (OECD T&C "Permitted Use") confirmed verbatim. The T&C also say the OECD "in no way represents or warrants that it owns or controls all rights in all Data"; users must check third-party ownership.

### adb_mrio: corrected (licence verified; year convention and base established)
- File list confirmed: `ADB-MRIO-2024_August 2025-62 .xlsx` (id 469, 72.7 MB, Last-Modified 6 Feb 2026), `ADB-MRIO72-2024_August 2025.xlsx` (446), `ADB-MRIO-2024-August 2025.xlsx` (445, 74 economies), `IND IOT 2000, 2007-2024.xlsx` (211, 921,068 bytes, Last-Modified 5 Dec 2025). id 179 is `Correspondence_ISIC4-ISIC31-MRIO.xlsx` (Nov 2024), a useful concordance.
- IND IOT header confirmed: "India Input-Output Table (35x35), 2024 (at current prices, $ million) as of August 2025". VA sums are confirmed exactly: 2022 = 3,135,712.18; 2024 = 3,598,908.03.
- **Licence:** open, commercial use permitted, attribution required (KIDB terms). Drop the access request.
- **Year = Indian FY** (2022 = FY2022-23), **old base**, converted at the calendar-year average rate. The evidence is exact to 0.005% (headline 2).
- Rows r62, r63 and trs are zero-filled for India.
- There is no 2025-reference table as of 2026-09-29.

### wb_wdi: corrected (year-basis quirk wrong for BOP; vintage)
- Catalog (WebFetch): "Creative Commons Attribution 4.0"; metadata last updated "Jul 20, 2026"; files "Jul 17, 2026" (`WDI_CSV_2026_07_15.zip`). Confirmed.
- API: NY.GDP.MKTP.CN 2025 = 345471567964600, lastupdated 2026-07-13. Metadata: `Nationalaccountsbaseyear` "2022/23", "fiscal year-based (fiscal year-end: March 31)", `SNApricevaluation` "Value added at basic prices (VAB)". Confirmed.
- GC.TAX.TOTL.CN latest 2022; GC.REV.XGRT.CN 2022 (with gaps; the previous value is 2018); DT.DOD.DECT.CD 2024; SI.DST.FRST.20 2022 = 10.4; BX.TRF.PWKR.CD.DT 2025 = 150.71 bn. All confirmed.
- **Correction:** "India year label is FY" holds for national accounts only. BOP (BN.CAB.XOKA.CD) equals IMF calendar-year values for 2022-2024. PA.NUS.FCRF is also calendar-year (2022 = 78.60). The metadata itself says "the exchange rate … differs from the official exchange rate (CY)".
- **Correction:** the national accounts are the 27 Feb 2026 SAE vintage, not the latest MOSPI vintage.

### imf_sdmx_portal: confirmed (additions)
- 221 dataflows at `/sdmx/2.1/dataflow`, including BOP 21.0.0, IMTS 1.0.0, ANEA 6.0.1, QNEA 7.0.0, GFS_SOO 12.0.0, GFS_COFOG 11.0.0, DIP 12.0.1, PIP 5.0.0, IIP 13.0.0, ER 4.0.1, IL 13.0.1, MFS_CBS 24.0.0, IRFCL 12.0.0, and monthly `*_2026_*_VINTAGE` flows. There is also **WEO (IMF.RES 9.0.0)**, which the recon did not mention.
- BOP `IND.NETCD_T.CAB.*.A`: 2025 = −20,227,690,000, UPDATE_DATE 2026-09-28T22:00:56. Confirmed.
- ANEA: B1GQ V XDC 2024 = 3.111801e14, 2025 = 3.374256e14; REFERENCE_PERIOD_REPORTED "2022-2023"; UPDATE 2026-09-28. Confirmed. Note: the "0.75·FY + 0.25·FY" formula is only approximate. It gives 311.0 for 2024 (vs 311.18) and 339.3 for 2025 (vs 337.4), so the IMF probably aggregates quarters.
- GFS_SOO non-null: S1311B 2014-2022, S1312MIXED 2014-2017, S1314 to 2022. Confirmed. Rows exist to 2023 but are empty.
- IMTS IND MG_CIF_USD CHN: 2025 = 124,836,340,000, UPDATE 2026-08-31. Confirmed.
- DIP: data to 2024 (258 counterparts), UPDATE 2025-12-10. Confirmed.
- Licence varies by dataset. BOP/IMTS/GFS/WEO rows say "© International Monetary Fund Copyright. All Rights Reserved." ANEA rows carry a citation string instead ("International Monetary Fund. 2024. National Economic Accounts (NEA) … Accessed on [current date]"). The IMF terms pages are still 403, so the access request stands.
- Not re-checked: IIP to 2026-Q1, GFS_COFOG to 2018, PIP truncation, the 149 MB size.

### un_comtrade: corrected (reference-year input)
- Preview 2025 annual: M 752,731,081,941 and X 445,769,600,047 (H6). 213 partner rows for 2025 M. Services: 2023 cmd 200 has partner 0 only (M 177.4 bn, X 336.2 bn); 2024 has 0 records. Confirmed.
- **Monthly latest is 2026-07,** not 2026-06.
- Subscriptions (WebFetch): preview "Limited to 500 records and 1 single period and product per call", 1 call/s. Free: "max 100K records per call", "500 calls/day". Bulk is premium only. Confirmed.
- Policy: "provided for internal use only and may not be re-disseminated in any form without UNSD's permission". Exemptions include free visualisation and analytics applications and free extraction apps up to 100,000 records. For-profit applications pay fees. Cite "UN Comtrade". Confirmed. Caveat: the owner is a company (Udgam Labs), so the site must stay free-of-charge to rely on the exemption.

### bis_stats: confirmed (licence addition)
- WS_TC Q.IN: 110 rows, 22 series, to 2026-Q1. LBS key: to 2026-Q1. DSS Q.N.IN: 24 series to 2026-Q1. WS_DEBT_SEC2_PUB Q.IN: 704 series to **2026-Q2**. WS_CBS_PUB: to 2026-Q1. All confirmed.
- Legal page confirmed, plus the **translation clause** and "no additional charge" condition.

### un_snaama: confirmed
- Page: "Latest Data Upload: January 2026"; "updated in December of each year".
- File 1 (`Download-GDPcurrent-NCU-countries.xlsx`): India GDP 2022 = 2.689047e14 (= old-base FY2022-23 2,68,90,473 crore), 2024 = 3.306815e14; total VA 2022 = 2.464670e14. Old base confirmed.

### oecd_wto_batis: confirmed
- SDMX query: 49,936 rows, periods 2023 and 2024 only in the requested window. Unit USD_EXC, UNIT_MULT 6. The WTO page gives coverage "2005-24".
- Not reproduced: the claim that documentation flags India's services imports as over-reported, and the WTO API 401.

### eurostat_figaro: corrected (India confirmed; licence; currency; access)
- India is included (codelists), unit MIO_EUR, India data 2022-2024 in `naio_10_fcp_ii4`, updated 2026-07-20.
- Access correction: FIGARO is also on the **Eurostat dissemination API** (`naio_10_fcp_ii1..4`, `_ip1..4`, `_s1..4`, `_u1..4`, JSON/SDMX, no key), not only CIRCABC. Datasets are split by period (II1 = 2010-2013 … II4 = "2022 and onwards").
- Licence: **non-commercial only for India data** (quoted above).
- Base: probably the new base, calendar-year converted (inference, headline 3).

### eora_mrio: confirmed
- worldmrio.com (200 today): "A new version of Eora (Eora2) is now available"; read-only "through June 30, 2026", but still online on 2026-09-29.
- Licensing: free academic 1990-2017, "no more than 200 individual raw data points"; commercial licence needed for "reports …, software tools, websites".
- eora.org: "complete timeseries for 1990-2024"; personal emails not supported. Also: "The licensing has shifted to an annual subscription model … Eora licenses do not carry over to Eora2."

### gtap_db: confirmed in part (reference years unverifiable)
- "GTAP 12 Data Base … February 2026" and the pricing table are confirmed verbatim. "not sold to re-sellers/third parties" is confirmed. 65 sectors is confirmed (sector list ends "65 dwe Dwellings").
- **Unverifiable:** the reference years (2004…2023) and "145 countries + 18 regions". The v12 pages fetched do not state them (the regions page URL guessed gave 404). The search quota was exhausted.

### exiobase3: corrected (latest release)
- Latest is v3.10.2 (2026-05-13), IOT files 1995-2024. The v3.9.6 record says "There is a newer version of the record available".
- Real SUT data run to about 2021 (FIGARO aggregate SUT to 2021; trade to 2022). Later years are nowcasts.
- "44 countries (27 EU member plus 17 major economies)". India membership was **not** confirmed by fetch (the full country list was not retrieved).

### wiod_2016: confirmed
- "no longer maintained"; CC BY 4.0; 43 countries, 2000-2014, 56 sectors, ISIC Rev. 4; Dataverse DOI 10.34894/PJ2M1C.

### wb_wits_trains: confirmed (licence still unverified)
- Availability XML: last India entries (2020, 2021/08/30) and (2021, 2022/09/09).

## Missed sources

1. **OECD national Input-Output Tables, 2025 edition**: https://www.oecd.org/en/data/datasets/input-output-tables.html. Files are at `webfs-sti.oecd.org/files/STI-PIE/IOTs/2025/` (`IOTs_VA.zip` 4.6 MB, `IOTs_TTL.zip` 24 MB, `IOTs_DOMIMP.zip`, Leontief inverses, ReadMe). ReadMe: "National Input-Output Tables (IOTs), 2025 edition"; "current million USD"; India listed. The VA probe for India has LABR, CFC, NOPS, OTXS, DISC and VALU for 1995-2022 (1,400 rows each). 2022: VALU 3,042,971; LABR 1,025,205 (33.7%); NOPS 1,249,513; CFC 375,399; OTXS 392,853 ($mn). This gives a ready **factor split (labour vs capital vs production taxes) by 50 industries** and the domestic/import split. Licence: OECD T&C (attribution). Caveats: old base, mixed income sits in NOPS, 2020-2022 are estimates.
2. **IMF WEO via the SDMX API** (`IMF.RES,WEO`, and `WEO_2025_OCT_VINTAGE`): `IND.NGDP.A` gives 2023 = 289.8391, 2024 = 318.0731, 2025 = 346.5115 lakh crore, projections to 2031. UPDATE 2026-04-15. These are FY-based and new-base (2023/2024 match WDI and MOSPI FY values). Useful as a new-base FY cross-check and for forward years. "All Rights Reserved" licence.
3. **UNdata SNA Official Country Data (Table 4.x institutional sector accounts)**: https://data.un.org/Data.aspx?d=SNA&f=group_code%3a401%3bcountry_code%3a356. India Table 4.1 total-economy sequence (production → capital account), "Fiscal year beginning 1 April", SNA 2008. The default view shows 2019 (FY2019-20) only, on the old base. Low value because stale, but it is the one international copy of India's full sequence of accounts. The recon said the Datamart URL 404'd; this URL works.
4. **WID.world** (household income distribution by percentile; relevant to the Section 4 household split): the bulk file `wid.world/bulk_download/wid_all_data.zip` gave HEAD 200, 882 MB, Last-Modified 9 Sep 2026. **Licence not verified** (not found on the pages fetched).
5. **OECD TiVA 2025 edition** (SDMX `OECD.STI.PIE,DSD_TIVA_*`). This is derived from ICIO, so it is a cross-check only.

## Reference-year corrections (summary)
- Comtrade monthly goods: latest **2026-07** (not 2026-06).
- WDI national accounts "2025" = **SAE of 27 Feb 2026** (₹345.47 lakh crore). It is superseded by PE (5 Jun, 346.36) and NAS 2026 (31 Aug, 345.37; 2022-23 revised to 261.77). WDI BOP years are **calendar** years.
- ADB IOT "2024" = **FY2024-25, old base** (high confidence). There is no 2025 table yet.
- OECD ICIO / national IOTs "2022" = **FY2022-23, old base** (certain by timing).
- FIGARO: India to **2024**, EUR, probably new base on a calendar-year basis (inference). Non-commercial licence for India cells.
- EXIOBASE: v3.10.2 (May 2026), tables to **2024** (real data to about 2021/22).
- IMF WEO: FY new-base, actuals to 2025 (Apr 2026 vintage).
- GTAP 12 reference year 2023: **unverifiable**.

## Issues
- The IMF terms pages are still Akamai-403, even with a browser UA and via WebFetch. Keep the access request.
- The BaTIS SDMX query with some fixed dimensions gave HTTP 500. Only the all-wildcard key worked. Pipelines should pull wide and filter locally.
- IMF DIP returns 403 if the key has the wrong number of dimensions (6 instead of 5). This is not a block.
- WDI API: a batch of calls exceeded 120 s once. The catalog API returned 429. Throttle calls.
- The recon's MOSPI press-note URL returns 403. Use the "-F" URL recorded in `recon/mospi_nas.md`.
- The EXIOBASE licence contradiction remains (website CC BY-SA 4.0 vs the Zenodo customised non-commercial licence). The owner should email the consortium if EXIOBASE is ever used.
- Every IO source except FIGARO is on the old 2011-12 base. Any IO structure taken from ICIO, OECD IOTs or ADB must be rescaled to new-base totals. The GVA level gap for FY2022-23 is −3.6% (246.47 → 237.64 lakh crore), and sector shares differ too.
