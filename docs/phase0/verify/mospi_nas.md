# Verifier notes: MOSPI National Accounts (`mospi_nas`)

- Verifier: independent adversarial agent (did not produce the recon).
- Date: 2026-09-29.
- Method: I re-fetched every URL with curl (browser User-Agent) and used MoSPI's public JSON endpoints under `https://www.mospi.gov.in/api/`. Probe files went to a scratch folder outside the repo; nothing was saved into the repo apart from this note. PDF text was extracted with pdftotext and XLSX files were read with openpyxl.
- WebSearch was unavailable: the session's search budget (200 of 200) was used up, so every check below comes from direct fetches.

## Verdict summary

| Source | Verdict | Main correction |
|---|---|---|
| mospi_nas_2026_publication | corrected | 1.14 has GDI and final consumption only for General Government and Households, not all 6 sectors. There are at least 3 vintages of the new series, not 2. Also missed: saving−investment errors & omissions, the household GDI/saving residual, and the CIF treatment in 6.1 (see "Critical findings"). |
| mospi_nas_api | corrected | The Back series (base 2011-12) runs 1950-51 to 2011-12 (62 records), not "at least 2002-03". Everything else reproduced. |
| mospi_esankhyiki_portal | confirmed | SPA shell and bundle API base reproduced. |
| mospi_gdp_press_releases | corrected | PE 2025-26 was released on **5 June 2026**, not 7 June. The 7 June rule applies from now on, and the 12 May 2026 note itself scheduled 2026 for 5 June. The 5 June PE vintage (2025-26 GDP 3,46,35,638) is a separate vintage. |
| mospi_nas_old_base_2011_12 | confirmed | Official chapter listings confirm that NAS 2025 (pub 432) has no sequence-of-accounts statements and NAS 2024 (pub 434) does. |
| mospi_nas_sources_methods_2026 | confirmed | Also covers errors & omissions (§23.4, §26.6) and Formula 12 (household GDI derived residually), which the finder did not surface. |
| datagov_in_nas_mirror | unverifiable | Catalog still times out or returns 403. New: the data.gov.in footer currently says "This is a sandbox environment created for testing and demonstration purposes only…". |

## Evidence log (what I actually fetched)

### NAS 2026 publication (pub 2861)
- `POST https://www.mospi.gov.in/api/publications-reports/get-web-chapter-data {"publication_id":2861}` → 200 with 7 chapters and 64 sub-chapters (60 statements + 4 PE/quarterly statements, 8.17.1, 8.17.2, 8.18.1, 8.18.2). There is no 1.3, no 1.15, no Chapter 2 or 3, and no 4.0, 5.0 or 6.0.
- `NAS-2026-Statements/1.1.xlsx` → 200, Last-Modified Mon 31 Aug 2026 06:38:34 GMT. `1.15.xlsx` and `5.0.xlsx` → 403. A made-up file name (`zzzz_nonexistent.xlsx`) also → 403, which confirms that missing files return 403.
- 1.1 (current prices, 2022-23 | 2023-24 | 2024-25):
  - GDP 26177001.4 | 29073286.7 | 31798524.1
  - Discrepancies 0 | 0 | -107438.0
  - At constant prices the discrepancies are 0 | -70315.7 | +36907.5
  - Note (iii): "Estimates of Savings and Disposable Income are compiled only at current prices."
- 1.9 household rows, 2023-24: 5890330.4 total; 3602198.5 financial; 1909286.7 liabilities; 4025292.1 physical; 172126.6 gold/silver. All match the finder.
- 1.14 lists "Gross Disposable Income" and "Final Consumption Expenditure" **only** for General Government and for Households incl. NPISH. The four corporate sectors have GVA, saving, GCF and CFC only. Sector GCF excludes valuables: the 6 sectors sum to 86,27,076 = GCF 89,87,744 − valuables 3,60,668 (2022-23).
- 7.1 columns: output, IC, GVA, "Production taxes less production subsidies", CFC, CE, "Operating Surplus/Mixed Income" (net). Manufacturing is one row. The totals identity closes: 8653669 + 11654812 + 3584380 − 69725 = 23823136.
- 6.1 reports imports of services "without adjustment for CIF" and a "surplus on current transactions" of -527525 (2022-23). Row 18 is "adjustment for CIF in Import of Services" = 292776. Row 17 notes "@ Including errors and omissions".
- 4.2 COFOG has one sheet per year (2022-23, 2023-24, 2024-25). Rows are CE, net purchases, subsidy, other current transfers and capital expenditure. **There is no interest-payments row** (property income is outside COFOG as shown).
- 8.17.1: PE 2025-26 current-price discrepancy -118500 and GDP 34536796. Confirms the finder.
- NAS 2026 press release PDF → 200, Last-Modified 31 Aug 2026. It says: "sixty statements based on the updated Final Estimates for the financial years 2022–23 and 2023–24, and First Revised Estimates for 2024–25". Its table gives 2022-23 GDP as 2,61,17,627 before and 2,61,77,001 after, and 2025-26 PE as 3,46,35,638 before and 3,45,36,796 after.

### Vintages of the new series (correction)
- 27 Feb 2026 (`...27022026-F.pdf`, 200): 2022-23 GDP 2,61,17,627; 2025-26 (SAE) 3,45,47,157.
- 5 Jun 2026 PE note (`..._PE_FY_2025-26_F.pdf`, 200, embargo "till 4:00 PM of 5th June, 2026"): 2022-23 to 2024-25 unchanged; 2025-26 PE 3,46,35,638; discrepancies 0 | 0 | 85,801 | −1,12,748.
- 31 Aug 2026 (NAS 2026): 2,61,77,001 … 3,45,36,796. The 2024-25 discrepancy flipped from +85,801 to −1,07,438.
- So there are **three vintages** for 2025-26 and two for 2022-23 to 2024-25. Provenance must record the vintage for every value.

### Press releases and calendar
- The latest-release list API paginates with body `{"page_no":N}` (111 items, 12 pages). Other parameter names are ignored. Q1 2026-27 (31 Aug), the NAS 2026 PR (31 Aug), the additional-info PR (2 Sep), the S&M press note (21 Sep), the PE note (5 Jun), the calendar-change note (11/12 May), the SDP joint-discussion PR (19 May), the GSVA guideline PR (7 May) and the SUT PR (15 May) are all present.
- Calendar-change press release (`uploads/latestReleases/Press Note_Release Calendar Change.pdf`, 200, dated 12 May 2026): "from last working day of May to 7th June (or the previous working day if 7th June is a holiday) … scheduled to be released on 5th June, 2026."
- ARC 2026-27 (200): "Released on 5th June 2026" for PE; 30 Nov (Q2); 7 Jan (FAE 2026-27); 26 Feb (SAE 2026-27 + Q3 + FRE 2025-26 + Final 2024-25).
- The original 27 Feb URL returns 403; the "-F" URL returns 200.
- Q1 2026-27 note: GDP current 88,26,871; discrepancy −69,478 (current) and −1,06,005 (constant). Next quarterly release is 30 Nov 2026.

### API (api.mospi.gov.in)
- `getNasIndicatorList?account_code=1` → base_year [2011-12, 2022-23], series [Back, Current], indicators 1–22. `account_code=2` → base_year 2011-12 only (GSDP).
- `getNASData … indicator_code=5` (2022-23 base) → 4 annual records: 2025-26 PE 34536796, 2024-25 FRE 31798524, 2023-24 Final 29073287, 2022-23 Final 26177001. These match NAS 2026. The quarterly record for 2026-27 Q1 is 8826871.
- The four 2022-23 quarters sum to 26,177,001, which is consistent.
- `Format=CSV` → header row only (reproduced).
- Back series (2011-12 base, GDP) → 62 records, **1950-51 to 2011-12**.
- 2011-12 Current → 66 records, including a separate record for each revision round (FAE, SAE, PE, FRE …). This is useful for vintage analysis.
- `getNasFilterByIndicatorId` needs `frequency_code`. For GVA it returns industries 1–15, sub-industries 1–18 and institutional sectors.
- GitHub `nso-india/mospi-esankhyiki`: MIT licence, pushed 2026-09-28. `client.py` line 43 is `def __init__(self, base_url: str = "http://10.24.89.9:5000")`, with a comment marking it as UAT. On PyPI `mospi-esankhyiki` is at 0.2.1. The swagger says "2011-12 supports Current & Back series, 2022-23 supports Current only".

### Old base (NAS 2024 and 2025)
- NAS2025/1.1 GDP for 2022-23 is 26890473 and the discrepancy is −474817. That puts the new base about 2.65% lower.
- The NAS2024 sequence files (1.15, 2.0, 3.0, 4.0, 5.0, 6.0 and the all-statements workbook) return 200/206. NAS2025 1.15 and 5.0 return 404, and there is no NAS2025 all-statements workbook (404).
- The CMS listing gives NAS 2025 as pub 432 (published 2025-06-26) and NAS 2024 as pub 434 (published 2024-06-05). These are CMS dates. File Last-Modified for both editions is 16 May 2025, which looks like a migration stamp, so the CMS dates cannot be cross-checked that way.

### Sources & Methods (21 Sep 2026)
- PDF: 200, 3,801,146 bytes.
- §23.4: "discrepancy … has been made '0' at current prices … the headline GCF is now taken as sum of GFCF, CIS and Valuables."
- §26.6: GCF by flow of funds (saving + net capital inflow) and GCF by commodity flow "differ … attributed as errors and omissions".
- §30.7 promises sequence-of-accounts chapters 2–6. These are **not** in NAS 2026.
- §30.10 gives no back-series date. The only date source remains the Feb FAQ and press note: "expected to be released by December 2026".

### Licence
- `POST /api/copy-right-policy/get-copy-right-policy-data` → "Material featured on this website may be reproduced, following the revised GSDD 2026 … reproduced accurately … not … misleading … source must be prominently acknowledged."
- Terms & conditions endpoint: privacy and chatbot text only, with no data licence.
- GSDD 2026 (Gazette No. 122, 6 May 2026; notification dated 27 Apr 2026): "Category A (open access data) … (i) Data relating to National Accounts"; "available free without registration".
- There is no explicit GODL statement on mospi.gov.in.

### data.gov.in
- The catalog page timed out after 45 s with curl twice, and WebFetch returned HTTP 403.
- `/Godl` → 200 (SPA shell, title "Government Open Data License - India"). `/government-open-data-license-india` → redirects to `/page_not_found`.
- The footer says "licensed under the Government Open Data License - India". It also says "This is a sandbox environment created for testing and demonstration purposes only. The content, data, and functionality may be incomplete or inaccurate." Treat data.gov.in as unreliable for this project.

## Critical findings the recon missed (they affect the SAM)

1. **The saving–investment account does not close, even in Final years.** Gross saving plus net capital inflow does not equal GCF (GFCF + CIS + valuables). The gap is the unpublished "errors & omissions" (S&M §26.6):
   - 2022-23: 84,67,662 vs 89,87,744, gap +5,20,083 cr (1.99% of GDP)
   - 2023-24: +3,58,634 cr (1.23%)
   - 2024-25: −2,79,181 cr (−0.88%)

   A zero expenditure discrepancy does **not** mean a closed capital account.
2. **Household GDI is a residual (Formula 12, 27 Feb press note), and household saving is estimated independently** (RBI financial saving plus physical saving). So household GDI − PFCE − household saving ≠ 0:
   - 2022-23: +8,12,857 cr
   - 2023-24: +5,71,133 cr
   - 2024-25: −1,28,402 cr

   Equivalently, GNDI − PFCE − GFCE ≠ published gross saving by the same amounts. The household row and column of the SAM will not balance on published figures. This needs an explicit, logged decision.
3. **CIF/FOB in the RoW account.** In 6.1 the current-account surplus is −5,27,525 cr (2022-23) with services imports *not* adjusted for CIF. The 1.1 aggregates use CIF-adjusted services imports: 11,68,704 vs 14,61,480, a difference of 2,92,776 = row 18. The implied external balance from 1.1 is −2,34,750 cr. The SAM needs one consistent treatment.
4. **No interest payments in the NAS government statements** (4.2 COFOG). Government property income (D41) has to come from budget or RBI data, or from the old-base 4.0.
5. **New-base State GSDP is in preparation.** The GSVA uniform guideline for base 2022-23 was released 7 May 2026, and joint NAD–DES discussions on 2022-23 to 2024-25 GSDP ran 20 May to 19 Jun 2026. It is not yet in the API (base 2011-12 only).

## Missed or under-cited sources in this family
- Calendar-change press release, 12 May 2026: https://www.mospi.gov.in/uploads/latestReleases/Press%20Note_Release%20Calendar%20Change.pdf
- FAQ on updating the GDP estimates with the new PPI/IIP, 1 Sep 2026: https://www.mospi.gov.in/uploads/announcements/announcements_1788245116303_5af38d5e-20eb-4db7-b111-ef975621c041_FAQ_on_updation_of_GDP_estimates.pdf
- Uniform Guideline for GSVA (base 2022-23), 7 May 2026: https://www.mospi.gov.in/uploads/latestReleases/latest_release_1778150493365_01356f8c-2a63-4c29-8426-f024d4a1ae68_Press_release.pdf
- SDP joint discussions on the new base, 19 May 2026: https://www.mospi.gov.in/uploads/latestReleases/latest_release_1779191728262_c804045a-df0e-4366-9f42-3b9a8e77dcbc_Press_Release19052026.pdf
- Report of the Sub-Committee on new data sources, rates and ratios (pub 2795, 24 Feb 2026), plus the Sub-Committee on Methodological Improvements (18 Feb 2026). These give the rates and ratios needed to justify estimation.
- "Annual and Quarterly Estimates of GDP at constant prices, 2011-12 series" (pub 2711, 29 Aug 2025): the old-base long quarterly series.
- The MoSPI announcement list API `POST /api/announcement/get-web-announcement-list`. The latest-release list paginates with `{"page_no":N}`.

## Reference-year check
- The latest *Final* year on the new base is 2023-24, with a zero current-price expenditure discrepancy and a SUT (pub 847: the 2023-24 SUT xlsx has Last-Modified 31 Aug 2026).
- 2024-25 is FRE (discrepancy −1,07,438 cr).
- Final 2024-25 is due 26 Feb 2027.
- 2023-24 is the right NAS-side candidate. It still carries the capital-account errors & omissions (+3,58,634 cr) and the household residual (+5,71,133 cr) described above.
- Institutional D4–D7 detail on the new base does not exist for any year. The latest old-base sequence of accounts is 2022-23 (NAS 2024).
