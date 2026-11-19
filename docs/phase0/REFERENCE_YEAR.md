# SAM reference year — recommendation (Phase 0)

Prepared 2026-09-29 by the SAM architect. Built on the verified reconnaissance (`docs/phase0/recon/*`, `docs/phase0/verify/*`), plus my own re-checks listed in section 8. Where a finder and a verifier disagreed, I used the verifier's value unless I re-checked it myself. **Revised the same day after three independent design critiques** (DESIGN_REVIEW.md). The recommendation is unchanged. Changes: the summary now says plainly that new-base institutional income accounts exist for no year and that the Flow of Funds is old-base; "Final" is qualified; the old-base vintage is labelled; one growth figure is corrected; the validation SAM is compared in ratios, not levels.

---

## Summary for the owner (plain English)

- **India's GDP base year is now 2022-23.** MoSPI published the new series on 27 Feb 2026, replacing the 2011-12 base. It has since been revised twice, on 5 Jun 2026 and 31 Aug 2026 ("NAS 2026"). The level break is large: 2022-23 GDP is ₹2,61,77,001 crore on the new base against ₹2,68,90,473 crore on the old one (−2.65%).
- **Recommended SAM reference year: FY 2023-24 (April 2023 – March 2024), on the new 2022-23 base, pinned to the NAS 2026 vintage (31 Aug 2026).** It is the latest year for which every block the SAM needs exists, **with one exception that applies to every year** (below):
  - national accounts labelled Final (updated 31 Aug 2026), with zero expenditure discrepancy;
  - the Supply-Use Table (MoSPI publishes no input-output table after 2007-08);
  - the household consumption survey (HCES 2023-24; no later round exists);
  - PLFS and ASUSE on the old survey design;
  - audited Union and State accounts;
  - the full balance of payments;
  - RBI's Flow of Funds (FSF 2023-24, the latest edition). It is on the **old** GDP base, as is every FSF edition so far.
- **The exception: the institutional income-distribution block does not exist on the new base for any year.** This covers interest, dividends, income taxes, social contributions and benefits, and other transfers by sector (SNA D4–D7), including the distribution side of the public/private company split. The only official version is the old-base NAS 2024 sequence of accounts, and it covers 2022-23 only (as a First Revised estimate). So this block is built bottom-up from administrative sources for any year I choose. Choosing 2023-24 costs a one-year roll of the old-base ratios used as priors. Choosing 2022-23 would avoid that roll, but the ratios would still be old-base.
- **Why not 2024-25?** Its national accounts are still "First Revised" (discrepancy −₹1.07 lakh crore). It has no SUT, no Flow of Funds and no household survey. PLFS changed design mid-year (January 2025).
- **Why not 2022-23?** It is equally feasible and is the base year, and it avoids the one-year roll above. But it is one year older, its capital-account errors are larger (±₹5.2 lakh crore against ₹3.6 lakh crore), and its household residual is larger (₹8.1 against ₹5.7 lakh crore). I propose building 2022-23 as a cheap second "validation SAM" with the same pipeline. It can be compared with IFPRI's 2022/23 SAM and with the old-base sequence of institutional accounts **in shares and ratios, not levels**, because both are on the 2011-12 base: GDP is 2.65% higher, sector shares differ, and IFPRI uses SUT 2019-20 coefficients.
- **Two numbers will not close even in the official 2023-24 data, and the SAM will show them openly rather than hide them in balancing:**
  - Households' disposable income exceeds their consumption plus saving by **₹5,71,133 crore**. NAS derives household income as a residual but estimates household saving independently.
  - National accounts and the balance of payments treat the CIF adjustment differently, a gap of **₹2,12,499 crore**.

  Together these two items explain exactly the official saving–investment gap of **₹3,58,634 crore** (my derivation from NAS 2026 Statements 1.1, 1.9 and 1.14; see section 5).
- **When to roll forward:** move to 2024-25 only once both a 2024-25 SUT and an FSF 2024-25 are published. The earliest plausible date is early-to-mid 2027. Even then the household block would rest on rolled-forward 2023-24 survey shares, because there is no newer HCES.

---

## 1. Current GDP base year (verified)

| Fact | Value | Evidence |
|---|---|---|
| Base year | **2022-23** (replaced 2011-12) | Q1 2026-27 press note (31 Aug 2026): "The Ministry has released the New Series of Annual and Quarterly GDP estimates with base year 2022-23 on 27th February, 2026" — https://www.mospi.gov.in/uploads/latestReleases/latest_release_1788172583113_d65a77cf-240e-4491-82ee-59f78618fa41_Press_Note_on_GDP_Estimates_for_Q1_2026-27.pdf |
| Vintages of the new series | **3 so far**: 27 Feb 2026 (SAE), 5 Jun 2026 (PE 2025-26), **31 Aug 2026 (NAS 2026, updated to the new PPI/IIP/BkSPI)** | NAS 2026 press release: 2022-23 GDP revised "2,61,17,627 → 2,61,77,001". The 2025-26 GDP moved 3,45,47,157 → 3,46,35,638 → 3,45,36,796 (mospi_nas verifier) |
| Final vs revised years | 2022-23 and 2023-24 **Final (updated 31 Aug 2026)**; 2024-25 **First Revised**; 2025-26 **Provisional** | NAS 2026 PR: "sixty statements based on the updated Final Estimates for the financial years 2022–23 and 2023–24, and First Revised Estimates for 2024–25". **Label conflict:** the Q1 2026-27 press note issued the same day says the NAS publication "publishes the updated Annual Revised Estimates for the FY 2022-23, 2023-24 and 2024-25 using New Series of Output Producer Price Index (PPI); Banking Services Price Index (BkSPI) …" (q1 press note PDF, re-read 2026-09-29). MoSPI's FAQ "Updation of GDP Estimates with New series of PPI and IIP", Q6: "The incorporation of the new PPI and IIP affected both annual and quarterly estimates from FY 2022-23 onwards" (local copy fetched earlier today by the mospi_nas verifier; I re-read that copy). So "Final" 2023-24 has already been revised once after being called Final. Likely re-pin points: the back series (by Dec 2026) and 26 Feb 2027. Phase 1 test: alert on any change to the 2023-24 control totals |
| Expenditure discrepancy (current prices) | 0 (2022-23), **0 (2023-24)**, −1,07,438 (2024-25) | NAS-2026-Statements/1.1.xlsx row 12 (re-fetched by me, sha256 55164fe3…) |
| Back series on the new base | **Not released**; "expected to be released by December 2026" | FAQ_GDP_26022026 PDF (mospi_nas verifier) |
| State GSDP on the new base | Not yet published (the API has base 2011-12 only) | api.mospi.gov.in getNasIndicatorList?account_code=2 |
| Next national-accounts events | FAE 2026-27 on 7 Jan 2027; **Final 2024-25 + FRE 2025-26 on 26 Feb 2027** | MoSPI Advance Release Calendar 2026-27 |

## 2. Latest year available, by dataset

"Base" is the GDP base year the dataset is consistent with. "n/a" means the dataset is not a national-accounts product (surveys, administrative data, market data).

| # | Dataset (SAM block it feeds) | Latest year available | Base / basis | Source id |
|---|---|---|---|---|
| 1 | NAS production: output, IC, GVA, CE, OS/MI, CFC by industry (7.1, 1.5, 1.6) | 2024-25 FRE; **2023-24 Final** | 2022-23 | mospi_nas_2026_publication |
| 2 | NAS expenditure: PFCE by COICOP (5.1), GFCE, GFCF by asset × sector (1.11), CIS, valuables, X, M | 2024-25 FRE; 2023-24 Final | 2022-23 | mospi_nas_2026_publication |
| 3 | NAS income & saving: GNI, GNDI, gross saving by 6 sectors (1.9), sector key indicators (1.14) | 2024-25 FRE; 2023-24 Final | 2022-23 | mospi_nas_2026_publication |
| 4 | NAS household financial assets and liabilities by instrument (5.3) | 2024-25 FRE | 2022-23 | mospi_nas_2026_publication |
| 5 | NAS external account (6.1), general government Centre/State VA (4.1), COFOG (4.2) | 2024-25 FRE | 2022-23 | mospi_nas_2026_publication |
| 6 | **NAS full institutional sequence of accounts (D1–D8 by sector)** | **2022-23 only, old base, NAS 2024 vintage** (so its 2022-23 column is the old-base **First Revised** estimate, GDP 2,69,49,646; the old-base Final is in NAS 2025, GDP 2,68,90,473, which has no sequence of accounts). Absent from NAS 2025 and NAS 2026 (NAS 2026 folder returns 403 for 1.15, 2.1, 3.1) | **2011-12** | mospi_nas_old_base_2011_12 |
| 7 | **Supply-Use Table** (155 products × 67 industries) | **2023-24** (also 2022-23). First released 15 May 2026, revised 31 Aug 2026 | 2022-23 | mospi_sut_2022base |
| 8 | Official input-output transactions table | 2007-08 (discontinued) | 2004-05 | mospi_iott_2007 |
| 9 | **HCES** (consumption by fractile × item, rural/urban) | **2023-24** (Aug 2023–Jul 2024); also 2022-23. No later round | survey prices | mospi_hces_2023_24 |
| 10 | PLFS (earnings, employment by status/industry) | Agricultural year 2023-24 (old design); CY 2025 (new design, break in Jan 2025) | nominal | mospi_plfs_annual, mospi_plfs_unit_data |
| 11 | ASUSE (unincorporated enterprises: GVA, emoluments) | 2023-24 (Oct 2023–Sep 2024); CY 2025; gap Oct–Dec 2024 | current prices | mospi_asuse |
| 12 | ASI (factory sector) | 2023-24 (2024-25 scheduled 29 Sep 2026 per ARC; not yet out at verification) | current prices, NIC 2008 | mospi_asi |
| 13 | AIDIS / SAS (household assets, debt, farm income) | 2019 round (stocks at 30.06.2018); next round is in the field now | current prices | mospi_aidis_2019, mospi_sas_2019 |
| 14 | Union accounts, audited (Finance Accounts, AAG object heads) | **2024-25** (2023-24 also available) | current prices | cga_finance_accounts_aag |
| 15 | Union Budget actuals | 2024-25 (in Budget 2026-27). 2023-24 actuals are in the Budget 2025-26 archive | current prices; %GDP on old base | mof_union_budget_2026_27 |
| 16 | State accounts: RBI "State Finances" | **2023-24 Accounts** (2025-26 edition) | nominal; %GSDP old base | rbi_state_finances_study |
| 17 | State accounts: CAG | 2024-25 all-state publication (Tableau only); Finance Accounts 2024-25 PDFs for 27 states (not Goa) | nominal | cag_state_finances_publication, cag_state_finance_accounts |
| 18 | FC16 key fiscal indicators (state-wise, machine-readable) | 2023-24 (labelled "2024") | nominal | fc16_relevant_data |
| 19 | Local bodies | ULBs 2023-24; panchayats only to 2022-23 | nominal | fc16_ulb_cityfinance_dump, rbi_pri_finances |
| 20 | Balance of payments (BPM6, ₹ and US$) | 2025-26 P; 2024-25 partially revised; quarterly to Q1 2026-27 | n/a | rbi_bop_quarterly, rbi_hbs_external |
| 21 | International investment position; external debt | end-March 2026 | n/a | rbi_iip, rbi_external_debt |
| 22 | **RBI Flow of Funds (FSF)** — sector × instrument, from-whom-to-whom | **2023-24** (published 21 Jan 2026). No 2024-25 edition | old base (inferred) | rbi_fsf_fof |
| 23 | RBI household financial saving (Bulletin 52a) | 2025-26 preliminary (large revisions between vintages) | 2022-23 | rbi_hh_fin_savings |
| 24 | Banking: STRBI, BSR; NBFC balance sheets (RTP App. VI) | STRBI 2024-25; BSR Mar 2026; NBFC end-Mar 2025 | n/a | rbi_strbi, rbi_bsr, rbi_trend_progress |
| 25 | Markets: SEBI Handbook; IRDAI; PFRDA; EPFO | SEBI FY2025-26; IRDAI 2024-25; PFRDA monthly to Aug 2026; EPFO AR 2024-25 (audited accounts 2022-23) | n/a | sebi_handbook_statistics, irdai_handbook_insurance, pfrda_nps_statistics, epfo_annual_report_accounts |
| 26 | G-sec ownership by holder | March 2026 | n/a | dea_public_debt_quarterly |
| 27 | Energy physical SUT | 2023-24; 2024-25 (P) | physical units | mospi_energy_statistics |
| 28 | International IO structures | ICIO 2022 (old base); ADB IOT 2024 (old base); FIGARO 2024 (new base inferred, non-commercial licence for India cells) | mixed | oecd_icio_2025, adb_mrio, eurostat_figaro |
| 29 | Prior Indian SAM (cross-check) | IFPRI 2022/23 (old base, SUT 2019-20 coefficients) | 2011-12 | ifpri_nexus_sam_india_2022_23 |

## 3. Candidate years side by side

✅ = available and consistent with the new base · 🟡 = available but estimated, rolled forward or old-base · ❌ = missing

| Block | 2022-23 | **2023-24** | 2024-25 |
|---|---|---|---|
| NAS status | ✅ Final, discrepancy 0 | ✅ **Final, discrepancy 0** | 🟡 FRE, discrepancy −1,07,438 |
| SUT (production/use structure) | ✅ | ✅ | ❌ (expected only after Final on 26 Feb 2027) |
| Institutional income distribution (D4–D7) | 🟡 old-base SoA **for this exact year** (ratios only; levels are old-base) | 🟡 old-base 2022-23 structure, rolled 1 year | 🟡 rolled 2 years |
| (no new-base D4–D7 exists for **any** year; every column builds this block bottom-up) | | | |
| Household consumption distribution | ✅ HCES 2022-23 | ✅ HCES 2023-24 | 🟡 HCES 2023-24 rolled forward |
| Labour income split | ✅ PLFS 2022-23 | ✅ PLFS 2023-24 (old design) | 🟡 FY straddles the Jan 2025 design break |
| Unincorporated sector | ✅ ASUSE 2022-23 | ✅ ASUSE 2023-24 | 🟡 Oct–Dec 2024 gap |
| Union government (audited) | ✅ | ✅ | ✅ |
| State government | ✅ | ✅ RBI SF accounts + CAG + FC16 KFI | 🟡 CAG only (RBI SF accounts due ~Jan 2027) |
| Local bodies | ✅ ULB + PRI | 🟡 ULB ✅, PRI rolled 1 year | 🟡 both rolled |
| Balance of payments | ✅ | ✅ | ✅ |
| Flow of Funds | 🟡 FSF 2022-23 (old base) | 🟡 **FSF 2023-24 (latest; old base)** | ❌ |
| Saving–investment E&O (GCF − saving − NCI) | +5,20,083 | **+3,58,634** | −2,79,181 |
| Household residual (GDI − PFCE − saving) | +8,12,857 | **+5,71,133** | −1,28,402 |

(The last two rows are derived from NAS 2026 Statements 1.1, 1.9 and 1.14, as reproduced by the mospi_nas verifier. I re-derived the 2023-24 values myself; see section 5.)

**Recommendation: 2023-24.** It is the latest column with no ❌, and it carries smaller unexplained residuals than 2022-23.

## 4. Which series the SAM uses: old 2011-12 vs new 2022-23 base

**Rule: all SAM *levels* (control totals) come from the new 2022-23 series, NAS 2026 vintage (31 Aug 2026), and from the matching SUT 2023-24 file (revised 31 Aug 2026). Old-base material may supply *shares and ratios* only. Each such use is labelled `estimated` and states the ratio used.**

Reasons:
1. The new series is the official current series. Every future update (Final 2024-25, back series, State GSDP) will be on it.
2. The levels differ materially. The 2022-23 GDP gap is −2.65%. GVA falls from ₹246.47 to ₹238.23 lakh crore (−3.3%; UN AMA old base vs SUT 2022-23 new base). Sector shares also differ, so mixing levels would put breaks inside the SAM.
3. The new series is SUT-integrated (zero discrepancy for Final years), so production, expenditure and income close by construction for 2023-24. That is the SAM's own first identity.

Where old-base material is still needed, and how it is used:

| Need | Why the new base cannot supply it | How old-base data is used |
|---|---|---|
| Property income and transfers between sectors (interest, dividends, taxes on income, social contributions/benefits, other transfers) | NAS 2025 and 2026 publish no sequence of accounts; only Statement 1.14 key indicators exist | NAS 2024 Statements 1.15, 2.x, 3.x, 4.0, 5.0 and 6.0 (2022-23, old base): **ratios** (e.g. interest paid by private NFCs as a share of their GVA) applied to new-base 2023-24 totals. Label `estimated (old base, NAS 2024 vintage, 2022-23 FRE)`. When checking ratios against levels, use NAS 2024 levels (2022-23 GDP 2,69,49,646), not NAS 2025 (2,68,90,473), so vintages are not mixed |
| Pre-2022-23 time series (the Map's time slider) | No new-base back series until ~Dec 2026 | Old-base series shown with an explicit break marker at 2022-23; replaced when the back series appears |
| Flow of Funds | FSF 2023-24 predates the new series (base inferred from 12.0% nominal growth, against 11.06% on the new base: NAS 2026 St 1.1, 2,61,77,001 → 2,90,73,287) | FSF **financial flows** are mostly base-independent (they come from balance sheets). Household and RoW rows are replaced by NAS 5.3 and BoP, with every difference posted to the counterparty in the same instrument; then each sector's net lending is reconciled to new-base NAS saving − GCF and residuals are logged (GAP_MAP K7b, K9). The 2023-24 FSF is also distorted by the HDFC merger (GAP_MAP K8). The workbook cannot be fetched by script (a GET returns an HTML bot challenge, re-checked 2026-09-29): **manual download required** |
| International IO structures (ICIO, ADB) | Compiled on old Indian inputs | Only as priors or cross-checks. The SAM does not need them, because the new-base SUT exists |

**Vintage pinning.** The pipeline records, for every NAS/SUT value, the release date and sha256 of the file. Files I fetched on 2026-09-29 for this analysis (probe copies in the session scratchpad, not the repo):

| File | sha256 |
|---|---|
| SUT 2023-24 xlsx (`…1788173315135…Supply_Use_table_2023-24_(1).xlsx`) | `6fbaa0e96982394e1ed2d6e1448acb681176e5541a36f744c285a96b921dfafd` |
| SUT 2022-23 xlsx (`…1788173286808…_(1).xlsx`) | `415955ee0fc8f7ad4c9c0c8b61473dcc02e333ef647ac83de3d5a2612547df19` (matches the mospi_io verifier) |
| NAS 2026 Statement 1.1 | `55164fe36bcd12bb3debb840d3f5c6f1ed0c9e8ec6fcaa549707ffc4f4e78309` |
| NAS 2026 Statement 1.9 | `6bcbeecce6734ad88479cf968dd7ec04b9e1fad869a47142fbeb3e05cd861b9e` |
| NAS 2026 Statement 1.14 | `8b0cd987000e150d0d7abbb7628246b2c8099c797de99924fc31e67d2477357c` |
| NAS 2026 Statement 7.1C | `bc1852793febc4c2687b0b9bc40f0b2a92bf3cd5126a6f8ff25882de1894a2e4` |

## 5. The 2023-24 control totals and the gaps that will not close

All values are ₹ crore, current prices, NAS 2026 vintage. They come from `NAS-2026-Statements/1.1.xlsx`, `1.9.xlsx` and `1.14.xlsx` (https://www.mospi.gov.in/uploads/publications_reports/NAS-2026-Statements/<stmt>.xlsx, fetched 2026-09-29) and from SUT 2023-24.

| Aggregate | 2023-24 |
|---|---|
| GVA at basic prices | 2,64,05,480 |
| Taxes on products incl. import duties | 32,44,229 |
| Subsidies on products | 5,76,422 |
| **GDP** | **2,90,73,287** |
| CFC | 38,36,206 |
| PFCE / GFCE | 1,64,15,547 / 31,21,027 |
| GFCF / CIS / valuables (GCF total 1,00,04,323) | 92,45,762 / 3,82,329 / 3,76,232 |
| Exports / imports (imports CIF-adjusted) | 64,79,296 / 69,46,906 |
| Expenditure discrepancy | **0** |
| Net primary income from RoW / other current transfers from RoW | −4,11,996 / +8,83,215 |
| GNDI | 2,95,44,506 |
| Gross saving | 94,36,799, of which: public NFC 4,62,996 · private NFC 24,10,409 · public FC 5,35,510 · private FC 4,55,938 · general government −3,18,384 · households 58,90,330 |
| Net capital inflow from RoW (1.9) | 2,08,891 |
| Income approach (SUT 2023-24 Use-table rows, my sums) | CE 94,42,896 · OS/MI (net) 1,31,83,820 · CFC 38,36,206 · production taxes less subsidies −57,442 |

**Decomposition of the saving–investment gap** (my arithmetic on the published figures; every input is in the table above):

1. GNDI − (PFCE + GFCE) = 2,95,44,506 − 1,95,36,574 = **1,00,07,932**. Gross saving in Statement 1.9 is 94,36,799. The difference is **5,71,133** = household GDI − PFCE − household saving (1.14: 2,28,77,010 − 1,64,15,547 − 58,90,330). MoSPI's formula 12 derives household GDI as a residual (GNDI − GDI of government − saving of corporations), while household saving is estimated independently from RBI data.
2. By the GDP identity, GNDI − final consumption = GCF + current account balance. So the current account balance implied by Statement 1.1 is 1,00,07,932 − 1,00,04,323 = **+3,609** (a small surplus). The net capital inflow in Statement 1.9 (from BoP) is **2,08,891** (a deficit). The gap of **2,12,500** equals SUT 2023-24's CIF adjustment on imports of services (−2,12,499). Statement 1.1 deducts it from imports, but the BoP-based figure does not. (The verifier found the same pattern for 2022-23: 2,92,776.)
3. Therefore GCF − (saving + NCI) = 5,71,133 − 2,12,500 = **3,58,634** (± rounding). This is exactly the official "errors and omissions" (S&M §26.6).

A further consequence: sector GCF in Statement 1.14 (which excludes valuables) plus household gold/silver ornaments in Statement 1.9 (1,72,127) sum to 98,00,218. That leaves **2,04,105 of valuables with no institutional sector** (3,76,232 − 1,72,127).

**How the SAM handles this:** a single, visible `X_DISC` account (see ACCOUNT_STRUCTURE §9). It receives the household residual (5,71,133), pays the NAS–BoP CIF reconciliation to RoW (2,12,499), and pays the balance (3,58,634) into the capital accounts. These cells are *pinned to the published figures*, excluded from balancing, and shown on the site as "statistical discrepancy". This follows SPEC rule 4: no silent patching.

## 6. Alternatives considered

| Option | Verdict | Reason |
|---|---|---|
| **2023-24 on the new base** | **Recommended** | Every block except new-base D4–D7 (missing for all years) is available. It is the latest Final year. Smaller residuals than 2022-23. HCES and SUT years coincide |
| 2022-23 on the new base | Build as a **validation SAM** (optional, low cost; owner to approve) | Equally feasible and the base year. The old-base sequence of accounts and IFPRI's 2022/23 SAM exist for this exact year, which makes it the best test of our institutional-block estimation, compared in **shares and ratios** (e.g. D4 or D5 as a share of sector GVA, quintile income shares), not levels, because of the base mismatch. Rejected as primary because it is older and has a larger E&O (5,20,083) and household residual (8,12,857) |
| 2024-25 on the new base | Rejected for now | FRE (non-zero discrepancy). No SUT, FSF or HCES. PLFS design break. Would need three blocks estimated |
| 2025-26 | Rejected | PE aggregates only |
| Any year on the old 2011-12 base (e.g. using NAS 2024's full sequence of accounts) | Rejected | Superseded series. The site would show numbers that no longer match official GDP |
| Symmetric IOT year from ICIO/ADB/FIGARO | Rejected as a base | Modelled or old-base, in USD or EUR. FIGARO's India cells are non-commercial only. Used as cross-checks only |

## 7. What changes if a newer SUT or Flow of Funds appears

| Event | Expected timing (basis) | Action |
|---|---|---|
| NAS revision of 2023-24 (e.g. another "updated Final", or the back-series release) | Possible at any NAS release. The back series is expected by Dec 2026 | Re-pin the vintage. Re-run Phase 1–2. Diff every control total and log changes > 0.1% in ISSUES.md. The SAM structure is unchanged |
| **Final 2024-25** | 26 Feb 2027 (ARC 2026-27, verified) | Not enough on its own: no SUT yet |
| **SUT 2024-25** | Unknown. In 2026 the SUT followed the series release by ~2.5 months (27 Feb → 15 May), so perhaps ~May 2027 (inference, unverified) | Necessary condition for rolling forward |
| **FSF 2024-25** | Past editions came out 17 Jan 2025 (for 2022-23) and 21 Jan 2026 (for 2023-24), so ~Jan 2027 (inference) | Necessary condition for rolling forward. It will probably be the first FSF on the new base; check its stated base |
| RBI State Finances 2026-27 edition (2024-25 accounts) | ~Dec 2026–Jan 2027 (inference from past cadence) | Makes the 2024-25 States block machine-readable |
| New HCES round | None scheduled in the ARC 2026-27. A press report suggests ~3 years (unverified) | Until then, any year after 2023-24 uses 2023-24 quintile shares, labelled `estimated (rolled forward)` |
| New-base institutional sequence of accounts (if MoSPI publishes or shares it; see access request) | Unknown | Replaces the old-base ratios in the transfer block. This is the single biggest reduction in estimated cells available to us |

**Roll-forward rule (proposed):** move the reference year to 2024-25 only when (a) NAS 2024-25 is Final, (b) SUT 2024-25 and (c) FSF 2024-25 are published. Keep 2023-24 as the benchmark SAM. The time-series layer (top ~50 flows) is updated every release regardless.

## 8. My own re-checks for this document (2026-09-29)

- Downloaded SUT 2023-24 and 2022-23 (Aug-2026 revised files, HTTP 200, plain GET) and NAS 2026 Statements 1.1, 1.9, 1.14 and 7.1C into the session scratchpad (outside the repo). Parsed them with openpyxl. Values quoted above are from these files.
- SUT 2023-24 GDP identity checked: 32,44,229 taxes = product taxes 30,15,341 + import duty 2,28,887; with subsidies (5,76,422), taxes net of subsidies = 26,67,806. GVA 2,64,05,480 + 26,67,806 = 2,90,73,286 ≈ GDP 2,90,73,287.
- Data quirks found in the SUT during this check are logged for ISSUES.md and described in GAP_MAP.md §4.1:
  - swapped product labels for crude/natural gas in the 2023-24 file (Q1);
  - CE/GVA ratios that are identical within NAS broad groups (Q2);
  - travel flows embedded in unexpected product rows (Q3).
- Also re-read for GAP_MAP (same date):
  - NAS 2026 Statements 4.1, 4.2, 5.3, 6.1 and 7.1C, and NAS 2024 Statements 4.0 and 5.0;
  - the FSF 2023-24 workbook (sha256 `3de9013dd37ef78dddd724f908ba89b5d80357494a0c34d99b8524b083bf3a1a`).
- **Design-review re-checks (same date, after three critiques; details in DESIGN_REVIEW.md):**
  - Downloaded MoSPI *Sources and Methods for Compilation of National Accounts Statistics*, September 2026 (https://www.mospi.gov.in/uploads/documents/pressRelease/1789976245319-Sources%20and%20Methods%20for%20Compilation%20of%20National%20Accounts%20Statistics.pdf; HTTP 200, application/pdf, 3,801,146 bytes, Last-Modified 21 Sep 2026; sha256 `8bd5f5f9fa1597894719fa0e8f293773d1d4d4a4c634325104c64791603d926e`) and read the passages on:
    - tax classification (§4.6);
    - pensions (§3.1.1);
    - food subsidy / FCI;
    - GST net basis;
    - household saving;
    - EPFO (§7.4.8);
    - autonomous bodies;
    - dwellings.
  - Re-derived nominal GDP growth 2023-24 on the new base: 11.06%, not the 10.97% I wrote earlier.
  - Confirmed the NAS 2024 old-base 2022-23 GDP of 2,69,49,646 (First Revised) against NAS 2025's 2,68,90,473.
  - Re-checked that the FSF 2023-24 xlsx cannot be fetched by script: HTTP 200, but `text/html`, 42,904 bytes, a bot-challenge page.
  - Confirmed that the DEA page https://dea.gov.in/reports-public-debt-management (HTTP 200) lists the Jan–Mar 2024 quarterly report and the Status Paper on Government Debt 2023-24.
