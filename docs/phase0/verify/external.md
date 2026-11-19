# Phase 0 verification: External sector (family id `external`)

**Verifier's role:** I independently and adversarially re-checked the finder's reconnaissance. I did not produce that reconnaissance.
**Date:** 2026-09-29.
**Method:** I re-fetched every source live with curl (browser User-Agent) and parsed the HTML/PDF text with Python. WebFetch was used for spot checks. Probe files went to the session scratchpad (`scratchpad/vext`, `scratchpad/v`, `scratchpad/ext`), outside the repo.

**Limits of this verification (read first):**
- The session's WebSearch budget was exhausted (200/200) before I started. I could not run new searches. This matters in three places: (a) the June 2026 DPIIT factsheet reported by the press, (b) the absence of a 7th-round RBI remittance survey, (c) the licence of the data.gov.in catalogs. Each is marked **unverifiable** below.
- data.gov.in: I made one GET on a catalog page to check it existed. It timed out. robots.txt for that site says `Disallow: /`, so I made no further requests there.
- I did not bypass any login, CAPTCHA or bot challenge.

## 1. Headline verdict

The finder's reconnaissance is mostly accurate. Every RBI headline number I re-fetched matched to the decimal. Six things need correcting:

1. **DPIIT FDI figure is equity only, not total.** The US$58,846 mn for 2025-26 is *FDI equity inflow, excluding NRI schemes*. It is not total FDI. The factsheet PDF has no FY total-FDI line: total FDI (equity + reinvested earnings + other capital) appears only for Q4 (US$20,876 mn) and cumulatively (US$1,166,462 mn).
2. **ODI URL points to the wrong month.** prid=63396 (Aug 18, 2026) is *ODI for July 2026*. The August 2026 ODI release (Sep 18, 2026) exists on the listing page, but the finder's URL and file (`OFDI18082026.xlsx`) are July's.
3. **UN Comtrade monthly data run to July 2026, not June.** Period 202607 was released on 2026-09-18.
4. **NRI deposits in the RBI Bulletin are PDF only.** Current Statistics Table 34 (NRI deposits) and Table 36 (LRS outward remittances) in the September 2026 Bulletin are PDFs on rbidocs, which is blocked for scripts. Neither has an HTML version, so the finder's "HTML (Bulletin current statistics table)" is wrong. Only the HBS annual tables are HTML.
5. **Swap-window dates.** The FCNR(B) window closed on **31 Aug 2026**; it had originally run to 30 Sep. The ECB/OFCB windows stay open to **31 Dec 2026**. The finder described the window as "June-Dec 2026".
6. **GDP base year now independently confirmed.** RBI HBS 2025-26 Table 1 (source: NSO) prints "(Base Year: 2022-23)" for 2022-23 onward and "(Base Year: 2011-12)" for 2020-21 to 2022-23. The 27 Feb 2026 release date itself could not be re-confirmed: mospi.gov.in returns 403 and the search budget is spent.

**The most important new point concerns the reference year.** HBS Table 1 shows national-accounts rest-of-world (RoW) items for **2025-26 as "-" (not yet published)**. The missing items are primary income from RoW, other current transfers from RoW, gross saving, gross capital formation (GCF) and consumption of fixed capital (CFC). BoP 2025-26 does exist. For **2024-25**, national accounts and BoP agree almost exactly:
- NAS current transfers from RoW (net) = ₹10,53,958 cr, identical to BoP T127 1.C.1 net.
- NAS primary income (net) = -₹4,09,303 cr, against BoP -₹4,09,118 cr.

So 2024-25 is the latest year in which the external block and the national-accounts closure both exist.

## 2. Source-by-source verdicts

| id | verdict | what I re-fetched / found |
|---|---|---|
| rbi_bop_quarterly | confirmed | prid=63493 (Sep 01, 2026, PR 2026-2027/1015): CAD 4.2 (0.5% GDP); goods -86.1; services 51.6; primary -10.5; secondary 40.8; personal transfers 42.9; FDI 6.1; FPI -9.6; NRI 2.8; ECB 3.3; reserves 8.1 depleted; E&O 1.6. prid=62890 (Jun 08, 2026, PR/412): FY25-26 CA 1077.8/1103.0/-25.2; goods 446.1/783.4; services 216.6 net; primary -48.2; secondary 143.6; reserves 23.6 depleted; footnote Q3 revision 13.2 to 15.5. prid=62891 old-format CAB -25.4. rbidocs `BOPS01092026_1.xlsx` returned 46,648-byte `text/html` with TS* cookies (bot challenge). BPM6 back to 2011-12 not checked. |
| rbi_bop_monthly | confirmed | prid=62935 (Jun 15, 2026) "Henceforth ... by the 15th day or earlier of the second subsequent month". prid=63373 (Aug 14): Apr-Jun 2026 CA -3.1, transfers 41.4. prid=63596 (Sep 15, PR/1118): July CA -7.0, NRI deposits 33.5, "Errors and omissions are included under 'Other Capital'". |
| rbi_hbs_external | confirmed | prid=63268 (Jul 31, 2026) 28th edition. PublicationsView id=23952 = T127 ₹ crore: 2025-26 CA 9530151/9749904/-219753; 1.A.b.9 1827090/241082; 1.B.1 76038/39309; "Data for 2025-26 are preliminary estimates". T131 from 2006-07, T139 from 2008, T143 from 2004-05, T144 from 1968-69, T190 from Apr-2019 all confirmed. **Additions:** T198 = quarterly BPM6 BoP in ₹; T199/T200 = quarterly IIP. **Quirk:** T190 labels two rows "March-2020" (the Feb-2020 row is mislabelled). |
| rbi_invisibles_quarterly | confirmed (existence and latest release); file structure unverifiable | Listing: latest "Jun 30, 2026 ... Fourth Quarter (January-March) of 2025-26"; no Q1 2026-27 as of Sep 29. Last year's Q1 came out Sep 30, 2025, so Q1 2026-27 is likely due Sep 30, 2026. XLSX returns the bot challenge. |
| rbi_iip | confirmed | prid=63047 (Jun 30, 2026, PR/569): net claims 209.9, -5.9% vs -9.0% of GDP. SectionID=356 listing: latest is Mar 2026 (Jun 30, 2026); end-June 2025 came out Sep 30, 2025, so end-June 2026 is likely due Sep 30, 2026. IIPDetails Id=150 "Sources of Data" lists FLA, IBS, PIP (erstwhile CPIS), BAL. |
| rbi_external_debt | confirmed | prid=63041 (Jun 29, 2026, PR/563): 762.8 bn, 20.8% vs 19.8%. Table 3 restates end-March 2025 as **736.4** (finder derived 736.5) and end-March 2024 at 19.2% (was 18.5%). prid=60729 (Jun 27, 2025): 736.3, 19.1%. Supporting evidence for the "new GDP denominator" inference: HBS T1 shows 2022-23 GDP ₹2,68,90,473 cr (2011-12 base) vs ₹2,61,17,627 cr (2022-23 base), a ~3% lower level, consistent with the ratios rising. RBI still does not say which GDP series it uses, so this remains an inference. |
| rbi_services_monthly | confirmed | prid=63480 (Aug 31, 2026, PR/1002): July-2026 38,253 / 20,606 US$ mn; "Data for April-July are provisional". SectionID=352 listing confirms roughly 1-month lag. |
| rbi_remittances_survey | confirmed (absence of a 7th round not checked) | Bulletin Id=23260 (Mar 19, 2025) sixth round 2023-24: US 27.7, UAE 19.2, UK 10.8, Singapore 6.6, Canada 3.8, Australia 2.3, GCC 38%, total US$118.7 bn, 30 AD banks ~99% of value. **Caveat:** Table 1 is titled "Source Country-wise Share ... (Banks)", i.e. bank channel only; MTOs and fintechs are not in the shares. No 7th-round check was possible (search budget). |
| rbi_wss_forex_reserves | confirmed | prid=63666 (Sep 25, 2026): as on Sep 18, 2026 total reserves 7342985 ₹ cr / 765901 US$ mn; FCA 630980; gold 111292; SDR 18739; RTP 4890. |
| rbi_nri_deposits | corrected | HBS T139 (id=23964) confirmed: end-March 2008 onward, end-March 2026 total US$165,654 mn. prid=63638 (Sep 21, 2026, PR/1160): FCNR(B) 1,32,980 (to Aug 31), OFCB 5,320, ECB 5,296, total 1,43,596. **Corrections:** Bulletin Table 34 is PDF-only on rbidocs (blocked). The FCNR(B) window closed Aug 31, 2026 (per prid=63638, citing the Aug 14 PR); prid=63274 (Aug 1) had said Sep 30. ECB/OFCB windows run to Dec 31, 2026. |
| rbi_ecb_monthly | confirmed | ECBUserView Id=274 "Data on ECB/FCCB for the Month of July 2026 ... Economic sector of borrower ... Equivalent Amount in USD". I found prid=63537 = "Date : Sep 07, 2026 ... RBI releases data on ECB / FCCB / RDB for July 2026". prid=63293 (Aug 05) = June 2026. |
| dpiit_fdi_factsheet | corrected | Static PDF (HTTP 200, application/pdf) "Updated up to March, 2026". **58,846 US$ mn = FDI EQUITY inflow 2025-26, excluding NRI schemes** (50,018 in 2024-25, +18%). Total FDI Q4 2025-26 = US$20,876 mn; cumulative total US$1,166,462 mn. Top 2025-26 equity sources: Singapore 19,802; USA 11,171; Mauritius 6,576. Listing page is a Next.js shell (7 KB); WebFetch 403. June 2026 factsheet: **unverifiable**. robots.txt `Allow: /`. |
| rbi_fla_census | confirmed | PublicationsView id=23438 (Oct 29, 2025) 2024-25 round, 45,702 respondents. The listing shows nothing newer. The MF survey (prid=63479) says AMC data were "taken from the annual census on FLA for the reference period 2025-26", so the 2025-26 round exists internally but is unpublished. |
| rbi_odi_monthly | corrected | Listing: "Sep 18, 2026 Overseas Direct Investment for August 2026". But prid=63396 (Aug 18, 2026) is "Overseas Direct Investment for **July** 2026" and its file `OFDI18082026.xlsx` is July's. All XLSX files are blocked. |
| rbi_ites_survey | confirmed | prid=63625 (Sep 18, 2026, PR/1147): US$221.4 bn (+8.2%), US 54.1%, Europe 31.8%, 89% coverage, off-site 91.7%, incl. foreign affiliates US$239.3 bn. |
| rbi_mf_fla_survey | confirmed | prid=63479 (Aug 31, 2026, PR/998): liabilities US$31.5 bn, assets US$10.2 bn; Table 1 ₹2,98,200 cr / US$31,504 mn, implying ₹94.66/US$. |
| rbi_dbie | confirmed | data.rbi.org.in/DBIE/ 200 `<title>DBIE`. dbie.rbi.org.in: `SEC_E_WRONG_PRINCIPAL`. dbie.rbihub.in: `<title>Database on Indian Economy`, shows "Foreign exchange reserves 18-Sep-2026 765.9 US$ bn", "USD/INR 28-Sep-2026 95.97", and a stale "Real GDP growth Q2 2025-26 8.2 %". |
| commerce_tradestat | confirmed | EIDB "Data available 2017-2018 to 2025-2026 Last data updated on 07/08/2026"; MEIDB "Jan 2018 to Jul 2026 ... 16/09/2026". My CSRF POST gave "India's Total Export 437,704.58 441,452.14" (US$ mn). robots.txt `Disallow:` (empty). Disclaimer: "do not have any legal sanctity". Ownership: Dept of Commerce/NIC. **Addition:** there is a client-side "Excel" export button (tableToExcel.js). |
| dgcis_trade | confirmed | Home: "Latest Finalised Export and Import Data upto June, 2026"; "Laspeyres Indices of April 2026- June 2026 with Base 2022-23". Portal: "State & District data at Principal Commodity level for July, 2026 could not be published". Policy PDF (4 pp.) is quoted in the key-facts table. Details: Rs 1.00/record; INR 350,000/yr bulk; **60% discount only for Indian academic/research institutions or libraries (IP subscription, non-commercial undertaking)**; royalty-free still requires written permission. copyright.aspx: "may not be reproduced partially or fully, without due permission from DGCI&S". |
| un_comtrade_india | corrected | getDA annual: 2025 H6 1,597,367 records, lastReleased 2026-07-10. Preview CY2025: X FOB 445.77 bn, M CIF 752.73 bn. **Monthly getDA: 202607 released 2026-09-18**, so monthly data run to Jul 2026, not Jun. Services EB10 last period 2023 (released 2024-08-28). FAQ quotes are confirmed. |
| imf_bop_iip_api | confirmed (licence unverifiable) | Dataflows BOP 21.0.0, IIP 13.0.0, PIP 5.0.0, DIP 12.0.1, IMTS 1.0.0, ITS 3.0.1. India CAB: 2025-Q4 -16.06 bn, 2026-Q1 +6.49 bn, 2026-Q2 -4.22 bn. **Quirk:** OBS_VALUE is in US$ units even though a `SCALE="6"` attribute is present. imf.org terms page 403, data.imf.org 403. |
| worldbank_remittances | confirmed | API lastupdated 2026-07-13; 2025 = 150,711,596,171 US$ (calendar year). datacatalog.worldbank.org/public-licenses: WBG licenses datasets under CC BY 4.0 unless labelled otherwise. knomad.org/data/remittances redirects to worldbank.org brief 2024/09/18, which states "KNOMAD ... was active from 2013 until 2024", so the bilateral matrix is effectively discontinued. |
| ogd_commerce_trade | unverifiable | robots.txt `User-agent: * Disallow: /` confirmed; catalog page timed out; licence and vintage not reproducible. |

## 3. Sources the finder missed

All of these were fetched from RBI's Statistics > Data Releases index (`https://www.rbi.org.in/Scripts/Statistics.aspx`):

- **Finances of Foreign Direct Investment Companies, 2024-25** (Apr 22, 2026). SectionID=363. Gives profits, dividends, and exports/imports of FDI companies. It is needed to split RoW investment-income payments (₹8.4 lakh cr debit in 2025-26) by sector.
- **Survey on Foreign Collaboration in Indian Industry 2023-2025** (Dec 02, 2025). SectionID=383. Royalty and technical-fee payments by industry: the "charges for the use of intellectual property" services import (₹1.65 lakh cr debit 2025-26) by sector.
- **Survey on International Trade in Banking Services 2024-25** (Sep 26, 2025). SectionID=367. Banks' financial-services exports and imports: the RoW x financial-services cell.
- **Outward remittances under LRS (RBI Bulletin Current Statistics Table 36, monthly).** The household to RoW outflow side (travel, maintenance, gifts, overseas investment). The PDF is on rbidocs (blocked); use DBIE or a manual download.
- **HBS 2025-26 Table 1 (NSO macro aggregates).** Not a new publisher, but it independently confirms the 2022-23 GDP base. It also carries the NAS RoW primary-income and transfer lines used to reconcile with BoP (see section 1).
- **HBS T198 (quarterly BPM6 BoP in ₹) and T199/T200 (quarterly IIP).** HTML alternatives to the blocked quarterly XLSX files.
- Not useful: **International Banking Statistics of India** (SectionID=353). IIP lists IBS as a source, but the public release stopped in 2018 (last: Jul 18, 2018).

## 4. Reference-year notes

- **2025-26:** BoP is Preliminary. National accounts have no RoW primary income, RoW transfers, saving, GCF or CFC yet (HBS T1 shows "-"). FLA 2025-26 is unpublished. The FDI factsheet is provisional. The external block alone is complete; the closure with national accounts is not.
- **2024-25:** BoP is Partially Revised. NAS is First Revised Estimates on the 2022-23 base. NAS and BoP RoW lines match (see section 1). FLA 2024-25 is published. The remittance survey is the nearest round (2023-24). **This is the latest year with a full external block plus national-accounts closure.**
- **Due tomorrow (Sep 30, 2026, inferred from last year's dates):** end-June 2026 external debt, end-June 2026 IIP, and Q1 2026-27 invisibles. Re-check before the registry is frozen.
- **GDP-ratio break:** debt/GDP and IIP/GDP were restated on the new base (end-March 2024 debt/GDP 18.5% became 19.2%). Any time series of ratios before 2022-23 mixes two bases.

## 5. Additional issues

- RBI robots.txt returns **HTTP 418** with "Unauthorised Access ... Support ID ...". The robots rules cannot be read.
- Bulletin Current Statistics tables (NRI deposits T34, LRS T36) are PDF-only on rbidocs (blocked).
- HBS T190 has a duplicate "March-2020" row label (February mislabelled).
- In the IMF SDMX API, OBS_VALUE is in units while `SCALE="6"` is declared. Guard against scaling values twice.
- UN Comtrade's India goods data originate from DGCI&S. Comtrade's own terms allow not-for-profit visualisation of actual figures, but DGCI&S's policy governs the national source. Ask DGCI&S whether a Comtrade-sourced display needs its permission.
- DPIIT publishes only equity inflows by country and sector. Total-FDI splits by country and sector need RBI FLA (stocks) or an estimate.
- The RBI remittance-survey country shares cover the bank channel only.
- KNOMAD has been discontinued (World Bank brief), so there is no maintained bilateral remittance matrix.
