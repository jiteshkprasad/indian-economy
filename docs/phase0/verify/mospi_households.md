# Verification: Household surveys (HCES, PLFS, AIDIS, others) — `mospi_households`

Verifier: independent adversarial agent (did not produce the recon). Date of checks: 2026-09-29.
Method: every URL was re-fetched with curl (browser User-Agent) or the MoSPI API. Small probe files were saved to the session scratchpad (outside the repo) and read with pdftotext/openpyxl. Nothing was saved to the repo except this note.
Limitation: the WebSearch budget ran out partway through. After that, all checks used direct fetches only.

## Verdict summary

| source_id | verdict | main point |
|---|---|---|
| mospi_hces_2023_24 | confirmed (minor corrections) | All 8 URLs return 200. Report is 225 pp, "NSS Report no. 592". MPCE 4,122 / 6,996 and 4,247 / 7,078 confirmed. A10F *does* give free-item **quantities** by fractile; only the values are suppressed (`##`). |
| mospi_hces_2022_23 | confirmed | Report PDF 200 (7,521,404 bytes; Last-Modified 1 Jul 2024). Factsheet Feb 2024 and report + unit data Jun 2024 confirmed by the 2023-24 factsheet text. |
| mospi_hces_unit_data | corrected | Access rules confirmed. **But** HCES collects no income. A MoSPI "Rider" tells users not to use the auxiliary household variables for estimation. "Household income proxies" overstates what the data can do. |
| mospi_esankhyiki_api | corrected | No-key access confirmed. The HCES call **needs `indicator_code`**: without it the request hung (HTTP 000 after 120 s). PLFS "annual" earnings come back as 4 quarterly CWS values, not one annual figure. Repos are MIT-licensed and were pushed 28 Sep 2026. |
| mospi_plfs_annual | confirmed (with additions) | Press note 27 Mar 2026 confirmed. All earnings figures confirmed. The AR 2025 also presents **CY 2022–2024 results derived from unit data**. The full AR 2025 PDF is still not located. |
| mospi_plfs_bulletins | corrected | Quarterly Apr–Jun 2026 **is** out: the API returns LFPR rows for 2026 Jan–Mar and Apr–Jun. Monthly series runs to Aug 2026 (LFPR 55.6%, PIB 15 Sep 2026). |
| mospi_plfs_unit_data | confirmed | Catalogs 284/291/292/213/210/254 exist. Related materials list is as claimed. |
| mospi_asuse | corrected | Figures and dates confirmed. **Missed:** quarterly ASUSE is already live in the API for 2026 Jan–Mar and Apr–Jun (the ARC scheduled Apr–Jun for 28 Sep 2026). Unit data (cat 293) appeared on 6 May 2026, not in April as the press note promised. |
| mospi_aidis_2019 | confirmed | Press note (Report 588, 10 Sep 2021, stocks as on 30.6.2018, rural ₹15,92,379) confirmed. PIB 11 Sep 2025 says the next AIDIS/SAS runs Jul 2026–Jun 2027, so fieldwork is **under way now** and results are unlikely before 2028 (my inference). |
| mospi_sas_2019 | confirmed | 60,536,852-byte PDF; PIB text confirmed. |
| mospi_nhis_2026 | confirmed | PIB 13 Oct 2025 ("first-ever … scheduled to be launched in February, 2026") and PIB 17 Mar 2026 ("April 2026 to March 2026" typo) confirmed. The 4.5 lakh households figure and the "mid-2027" results date appear **only in secondary sources**: unverified. The MoSPI press note URL `Press%20Note%20NHIS%202026_13.10.2025.pdf` returns 404. |
| mospi_tus_2024 | unverifiable (partly) | Catalog 236 exists (created 15 Apr 2025). I did not re-verify the report release date (March 2025) against a primary source. |
| cmie_cphs | confirmed | CMIE page quotes reproduced. No price is shown on the page. |
| price_ice360 | confirmed | Page quotes and dates (Feb 05 2024 / Apr 08 2025) reproduced. |
| ihds | corrected | The ihds.umd.edu text is confirmed. ICPSR study 37382 returned **403** to curl, so it is unverified. Search snippets say IHDS-3 fieldwork finished in June 2024. No public IHDS-3 data found; NCAER posts monthly "IHDS Forum" pieces (July 2026). |
| wid_india | corrected | `https://wid.world/terms-of-use/` now returns **404**. The India page's active licence link is **CC BY-NC-SA 4.0** (`creativecommons.org/licenses/by-nc-sa/4.0`). A commented-out tooltip says "CC BY 4.0". So the data is **non-commercial and share-alike**, which matters for a company-run site. |
| mospi_gsdd_2026 | confirmed | Gazette text confirmed (27 Apr 2026; digitally signed 2026.05.07). The microdata portal still links it over **http://** and labels it "in accordance with NDSAP, 2012". No GODL-India wording. |

## Key facts re-checked

- **HCES 2023-24 is the latest round (Aug 2023–Jul 2024).** Confirmed by PIB 30 Jul 2025: "The last survey on Household Consumption Expenditure was conducted during August, 2023-July, 2024." The ARC 2026-27 lists no HCES release. "No further round scheduled" is **unverified**: a Business Standard search snippet reported the MoSPI Secretary saying HCES would be done again in ~3 years, and my search budget ran out before I could confirm it.
- **HCES aggregate vs NAS PFCE.** Recomputed from Table A2:
  - Persons: rural 854.7 mn, urban 362.9 mn, total 1,217.6 mn.
  - Annual consumption: rural ₹42.28 lakh crore, urban ₹30.47 lakh crore, total ₹72.75 lakh crore.
  - That is 44.4% of NAS PFCE 2023-24 (₹163.77 lakh crore, PIB 27 Feb 2026).
  - Per capita: ₹59,747 vs ₹1,17,356, i.e. 50.9%.
  - The recon's figures are reproduced. Label: estimated.
- **Imputed free items by fractile.** Report §3.1.4 says "…cross-classifications of the same by fractile classes of MPCE have not been generated." Confirmed. **Nuance:** Table A10F gives free-item *quantities* by fractile (e.g. rural 0-5%, item 061 "rice-free" 2.405 kg; value `##`). Combined with `HCES_2023_24_Imputation_Rate.xlsx` (listed in related materials), this allows an *estimated* quintile imputation without unit data.
- **Free health and education are not imputed.** Report §2.2.4: "no attempt has been made to impute the expenditure of health services availed by the households free of cost… free education services… has also not been imputed." Confirmed.
- **NAS new series uses ASUSE and PLFS.** The recon attributed this to "secondary summaries". It is in fact in the primary PIB release 2233518: "level estimates of the household sector will be compiled through regular surveys – ASUSE and PLFS". PFCE uses "Household Consumption Expenditure Survey for quarterization". Upgrade to high confidence.
- **PLFS tables.** 2023-24 AR Table (50) gives regular wages by NCO occupation division. Table (51) gives the casual wage by NIC section. There are no regular-wage-by-industry tables. The API indicator-6 filters include no industry dimension. Confirmed.
- **No PLFS Jul 2024–Jun 2025 annual report.** API year list: 2025, 2024, 2023-24, 2023, 2022-23 … Confirmed.

## Missed sources (from the microdata portal, sorted newest first)

- **Domestic Tourism Expenditure Survey, NSS 80th round, Jul 2025–Jun 2026** (catalog 307, created 23 Sep 2026). Household trip expenditure. Useful for PFCE tourism and hotels/transport commodity splits.
- **Survey on Household Social Consumption: Health, Jan–Dec 2025** (catalog 290, created 17 Apr 2026). Out-of-pocket health spending. This fills the health gap left by HCES, which does not impute free health services.
- **Comprehensive Modular Survey: Education, NSS 80th round, Apr–Jun 2025** (catalog 255). Household education expenditure, including fees, coaching and transport.
- **CAMS, NSS 79th round 2022-23** (catalog 220). Low priority.
- **MoSPI HCES unit-data "Rider"** (catalog 237, download 3951). Tells users not to use the auxiliary household variables for estimation, and not to estimate below State level.

## Reference-year implications (household side)

- HCES: 2022-23 and 2023-24 only. Survey years run Aug–Jul.
- PLFS:
  - Agricultural years to 2023-24.
  - CY 2024 key indicators.
  - CY 2025 under the new design (the 2025 AR also re-presents CY 2022–24).
  - Quarterly to Apr–Jun 2026; monthly to Aug 2026.
- ASUSE: 2022-23 (Oct–Sep), 2023-24 (Oct–Sep), CY 2025, and quarterly 2026 Q1–Q2. Oct–Dec 2024 is not covered.
- AIDIS/SAS: 2019 round only. The new round is in the field now.
- NHIS: in the field, no results.
- **Conclusion unchanged:** FY 2022-23 or FY 2023-24 are the only household-consistent reference years.

## Issues / failures observed

- `https://api.mospi.gov.in/api/hces/getHcesRecords?year=2023-24&sector_code=1&state_code=99` (no indicator_code) got no response within 120 s. With `indicator_code=3` it returned 200 and "Cereal" 204.76.
- `https://mcp.mospi.gov.in/` returns 405 to GET. This is probably normal for an MCP endpoint and was not tested further.
- `https://www.icpsr.umich.edu/web/ICPSR/studies/37382` returns 403 to curl.
- `https://wid.world/terms-of-use/` returns 404.
- `PressNote_AIDIS_SAS-Final.pdf` returns 404, and so does the MoSPI NHIS press note PDF.
- MoSPI copyright page: WebFetch saw only the page title (it is a JS single-page app). Still **unverified**; the owner should check it in a browser.
- The NSS publication-use policy PDF (`policy_nss_pub_25se17.pdf`, 2.2 MB) has no text layer. Confirmed.
