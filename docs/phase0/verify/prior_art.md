# Phase 0 verification: prior_art (existing Indian SAMs and multiplier estimates)

- Verifier: an independent adversarial agent. It did not produce the finder output.
- Date of checks: 2026-09-29.
- Method: every URL was re-fetched with curl (browser User-Agent) or WebFetch. PDFs were probed into the session scratchpad only; nothing was downloaded into the repo. No login, guestbook, CAPTCHA or bot wall was bypassed.
- The shared web-search budget ran out part-way through this check. Later checks used curl and WebFetch only.

## Summary

- **Correct overall.** The finder's picture holds up:
  - The newest national SAM is IFPRI's 2022/23 Nexus SAM, published on Dataverse 2024-11-08. Nothing newer exists on IFPRI Dataverse. IFPRI's 2025 release note (2025-12-12) lists India only under "SAMs released prior to 2025".
  - Every published Indian SAM is on the old 2011-12 series.
  - MOSPI's first SUTs on the new 2022-23 base were released 15 May 2026. They cover 2022-23 and 2023-24 at **155 products x 67 industries**, and final estimates carry no discrepancy.
- **One material correction: the RBI capex multiplier.** The primary source was reachable (the finder said it was not). RBI Monetary Policy Report, April 2019, Box III.1 "Estimable Fiscal Multipliers for India" is at https://rbi.org.in/Scripts/PublicationsView.aspx?id=18941.
  - Method: a Bayesian structural econometric model estimated on annual data, 1980-81 to 2017-18.
  - Table III.1.1 peak multipliers: Centre revenue expenditure 0.45; States revenue expenditure 0.82; **Centre capital expenditure 3.25**; **States capital expenditure 2.00**.
  - The "2.45 in t, 3.14 in t+1" path appears only in the Dec 2020 Bulletin's paraphrase. It is not in the primary box. Cite the primary table.
- **Factual errors in the NCAER entry:**
  - The finder wrote "39 producing sectors plus 7 electricity sources, cement, aluminium, biomass". The WP says the SAM has 39 producing sectors, and the electricity, cement, aluminium and biomass sectors are *within* those 39.
  - The WP is also internally inconsistent: one passage says "30 production sectors", and it calls the household groups "5 decile groups" when they are quintiles.
  - The WP cover is dated January 2024. The web page is dated 5 Feb 2024.
- **Licence evidence is stronger than the finder reported.** CGSpace has a separate *dataset* record for the 2022/23 India SAM with an explicit CC-BY-4.0 licence: hdl 10568/163735, `dcterms.license = CC-BY-4.0`, linked to doi:10.7910/dvn/ldudte. The IFPRI terms are also not truly contradictory. Section 3's restrictions open with "Except as expressly permitted hereunder in Section 4", and Section 4 grants CC-BY-4.0. What remains:
  - Section 5 requires an adaptation disclaimer.
  - Section 6 warns about third-party material. The SAM embeds MoSPI, IMF and UNCTAD data.
- **The finder's CGSpace URL is not the PDF.** It points to the TEXT bundle `IFPRI_SAM_IND_2022-23.pdf.txt`, served as text/plain. The real PDF is bitstream `ff7b1ece-8897-4567-be3a-4c99db75dca3` (`IFPRI_SAM_IND_2022-23.pdf`, 501,277 B). The same applies to the 2017-18 paper URL.
- **Quirk the finder missed in the IFPRI SAM:** the split of savings between enterprises and households is *assumed*: "Nexus SAMs assume that enterprises and households have similar savings rates, after enterprises have subtracted their allowance for the depreciation". So the 49,632 / 47,714 split is not NAS data.
- **Could not reproduce:**
  - The CSEP "embargoed till 13 Jan 2023" text. There is no "embargo" string anywhere in the current PDF text.
  - The "6 tax accounts" in the India 2022/23 file. The standard Nexus template has 6 (atax, dtax, etax, ftax, mtax, stax), but the India file is behind guestbook 380 and was not inspected.
- **Gating differs between the two IFPRI datasets:**
  - DVN/LDUDTE (2022/23): the API returns HTTP 400 "You may not download this file without the required Guestbook response for guestbookID 380". Confirmed.
  - DVN/NYVJX8 (2017-18), file 4493060: the API returned **HTTP 303 to an S3 signed URL**, meaning no guestbook enforcement at the API, although guestbookId 9 is configured. I did not follow the redirect. The owner should still complete the guestbook in the UI.

## Source-by-source

| id | Verdict | Key evidence I fetched | Corrections |
|---|---|---|---|
| ifpri_nexus_sam_india_2022_23 | corrected | Dataverse API (200): publicationDate 2024-11-08, v1.0, productionDate 2024-10-01, license null, guestbookId 380; files ReadMe 1,065 B, POP.tab 948 B, SAM.tab 51,793 B. Data paper PDF (CGSpace bitstream ff7b1ece…, 200, application/pdf) Table 8 matches every macro figure the finder quoted. Table 7 sources match. Cross-entropy text matches. Table 11 all-households savings rate is 22.5%. | The URL given as the data-paper PDF is the .txt bundle. CGSpace dataset record 10568/163735 has an explicit CC-BY-4.0 licence. The enterprise/household savings split is an assumption. "Calendar 2022" for GFS/BoP is an inference: the paper only labels the data year "2022". "6 tax accounts" is unverified. The "HCES scaled to NAS PFCE" wording is not stated verbatim; it is implied by "Nexus SAMs always use national accounts data". |
| ifpri_sam_india_2017_18 | corrected | Dataverse API: published 2021-04-23; guestbook 9; files IND_X112_2017-18_SAM v112N.tab 328,256 B (original xlsx 292,446 B) and Notes.tab. CGSpace 10568/143193: issued 2020-11-01, CC-BY-4.0, DOI 10.2499/p15738coll2.134178. Table 9: NAS MoSPI (2019), SUT 2015/16, IO 2007/08, GFS/BoP "2017", NSS 68th round 2011/12. Two rounds of cross-entropy confirmed ("a second round of cross-entropy"). | The API served a 303 to S3 without a guestbook response. The original upload format is XLSX. The TEXT bundle URL is not the PDF. |
| cstep_sam_india_2017_18 | corrected | HEAD 200, 230,044 B, Last-Modified 23 Jun 2025. My own probe: Note sheet reads "Units: 10 Million Rupee", "Year: 2017/18"; SAM sheet has 209 accounts (92 activities, 87 commodities); max\|row-col\| = 5.59e-9. Page datePublished 2025-06-10. PDF: "©2024 CSTEP … Any reproduction … must mention the title and/or citation", dated August 2024, CSTEP-TN-2024-2. | There are 4 tax accounts (**atax**, mtax, dtax, stax); the finder omitted atax. PDF Table 1 is a *partial* catalogue with 12 numbered entries (no. 9 missing). It omits NCAER 2021-22, CSEP 2019-20 and IFPRI 2022/23. |
| ncaer_sam_india_2021_22 | corrected | WP PDF (200, 1.68 MB): "59×59 SAM for India, with base year of 2021-22 incorporating 3 factors … 10 categories of households"; "RAS technique is applied"; NSS 2011-12 consumption shares; Table 6 multipliers match. The IO matrix for 2021-22 is in Appendix II of the WP; the SAM is in "Supplementary file". www.ncaer.org gives curl exit 35 (confirmed). The SAGE page returns 403 (confirmed). | The 7 electricity sources, cement, aluminium and biomass are part of the 39 sectors, not additions. The WP says "30 production sectors" in one place (an internal inconsistency). The factors are skilled labour, unskilled labour and capital. The cover says January 2024 and the web page says 5 Feb 2024. |
| csep_esam_india_2019_20 | corrected | PDF (200, 10.2 MB): 45 sectors, 318 labour, 80 households; GDP ₹2,03,51,013 cr (expenditure = income); RAS on IOT 2015-16; the merchandise-exports discrepancy is quoted verbatim; paddy 6.380, coal and lignite 3.044, crude petroleum 1.558 (total N). Page datePublished 2023-11-22, modified 2024-06-21. | The Table 11 multipliers are computed on an **aggregated ESAM** (32 labour, 40 households; Table 9 of the paper), not the full 318/80. The "embargoed till 13 Jan 2023" text is not in the current PDF, so that claim is unverifiable. |
| ieg_sam_india_2007_08 | confirmed | PDF (200, 48 pp.): "78 sectors and nine categories of households"; I-O 2007-08, NSSO 66th round, NCAER IES 2004-05; the pro-rata adjustment to NAS 2011 personal income is quoted. | The site footer now reads "© 2025 - 2026 Copyright IEG. All Rights Reserved.", not 2022. |
| india_mrio_32states_2011_2019 | confirmed | figshare API: published 2026-06-30, CC BY 4.0, 9 XLSX files of 45.6–48.6 MB. Nature page (reached after the idp cookie redirect) says "Published: 24 April 2026", "Rs Lakh … at current price", "controlled within 5%", and carries a CC BY 4.0 notice. The GitHub repo returns 200. | none |
| rbi_jain_kumar_2013_multipliers | corrected | Raw HTML Table 1: combined capital outlay 1.29 / 3.56 (yr 4); revenue expenditure 0.37; Centre capital outlay 0.39 / 0.85; States capital outlay 2.13 / 7.61 (yr 3); States revenue expenditure 0.60; Centre revenue expenditure impact 0.19 (peak 0.09). | The sample is **annual 1980-81 to 2011-12**, not "quarterly/annual". Additional estimates: non-defence capital outlay 1.81 / 5.88; Centre non-defence capital outlay 2.10 / 3.84. |
| rbi_bulletin_capex_multipliers | corrected | The Id=19959 quote was verified verbatim (24 Dec 2020). Id=20322 (16 Jun 2021): "higher than 2 in India (RBI, 2019; Jain and Kumar, 2013)". **Primary MPR Apr 2019 Box III.1 (id=18941): Centre capex 3.25, States 2.00, revenue expenditure 0.45 / 0.82 (peak).** | Use the primary source. The finder's note that the MPR was unreachable is wrong. rbidocs PDFs serve an F5/TSPD JavaScript bot challenge (confirmed; not bypassed). |
| nipfp_fiscal_multipliers | corrected | WP 2013-125 abstract matches (2.45 / 0.98 / 0.99 / about -1). WP 436, "No. 436 September-2025", social-spending multiplier 1.67 estimated over 1990–2022. | The WP 125 sample is "Annual data for the period **1991-2012**". Note that the NIPFP capex figure of 2.45 is numerically identical to the RBI Bulletin's "2.45 in t", so avoid conflating the two sources. |
| adhikari_pfce_committee | confirmed | PDF (200, 97 pp.): the 2011-12 row (NSS 2829566 vs NAS 5167446, -45.24%; food -28.29%, non-food -54.77%) and "increased from 5 per cent to 45 per cent" both match. The EPW page (Vol 61 No 5, 31 Jan 2026, Ashish Kumar & Payal Seth, ₹59 paywall) reads "nearly 54% in 2023–24". | Add that the committee's work relates to the 2004-05 series (para 1.2.4) and that the NSS figure is MMRP "type 2". The EPW figure comes from the free abstract only. |
| sut_to_sam_methodology_india | confirmed | IIOA PDF (200, 25 pp.) abstract matches. It also states "The latest [IOT] was published in 2012 for the reference year 2007-08". CGSpace 10568/146619 is the CSTEP WP 2018-02, issued 2018-11-07, Open Access, with an empty licence field. | none |
| mospi_sut_2022_23_series_release | confirmed | PIB PDF (200): "Posted On: 15 MAY 2026"; new series released 27 Feb 2026; NIC 2025 and COICOP 2018. | Add: 155 products x 67 industries. The MOSPI SUT page is JavaScript-rendered, so curl returned only a 2.6 KB shell; the table files were not inspected. |

## Missed sources (worth adding)

1. **IFPRI 2017/18 state SAMs:** Odisha (doi:10.7910/DVN/74YWV2, 2025-01-06), Uttar Pradesh (DVN/FQHHM8, 2024-08-08) and Bihar (DVN/GOZMQU, 2024-08-08). These are templates for a future States split.
2. **RBI MPR April 2019, Box III.1** (primary source): https://rbi.org.in/Scripts/PublicationsView.aspx?id=18941.
3. **Goyal & Sharma (2018)**, "Government Expenditure in India: Composition and Multipliers", *Journal of Quantitative Economics* 16. Quarterly SVAR; the cumulative capex multiplier is 2.4–6.5 times the revenue-expenditure multiplier. https://link.springer.com/article/10.1007/s40953-018-0122-y
4. **Mishra & Adiraju (2025)**, "Estimation of fiscal multipliers for India", *IJEPEE* 21(1). SVAR; impact multipliers 0.23–1.85, cumulative 0.45–5.45. https://www.inderscience.com/info/inarticle.php?artid=145416
5. **Pal & Bandarlage (2017)**, "Value-added disaggregated SAM for India 2007–08", *Journal of Economic Structures*, CC BY 4.0. 78 sectors, 48 labour types, 80 households. https://link.springer.com/article/10.1186/s40008-017-0074-y
6. **Pal, Pohit & Roy (2012)**, "Social Accounting Matrix for India", *Economic Systems Research* 24(1), SAM for 2003-04 (paywalled). https://www.tandfonline.com/doi/full/10.1080/09535314.2011.618824

## Reference-year implications

- The IFPRI 2022/23 SAM coincides with the new base year 2022-23. It is the natural structural cross-check, but its levels are on the old series.
- MOSPI SUTs exist for 2022-23 and 2023-24 on the new base, with no discrepancy in the final estimates.
- The EPW 2026 figure refers to 2023-24, which shows that HCES 2023-24 data exist. The HCES vintage belongs to the household-survey family.
- Every other prior SAM is 2021-22 or older.

## Issues to log

- Cite primary RBI MPR 2019 values (3.25 / 2.00 / 0.45 / 0.82), not the Bulletin's paraphrase.
- The IFPRI enterprise/household savings split is an assumption; treat it as a low-reliability cross-check.
- The Esha Swaroop IES paper is unreachable. www.ies.gov.in fails the certificate name check (curl 60, and WebFetch reports "not in the cert's altnames: DNS:ies.gov.in"). The same path on ies.gov.in returns HTTP 404.
- The BIS Papers 122 PDF (bispap122_j.pdf) now redirects to an HTML landing page; the India chapter was not checked.
- No India-specific IMF fiscal multiplier was verified. The search budget was exhausted, so this is still open.
