# ISSUES

The log of loud failures, gaps and contradictions (SPEC rule 4: no silent fallbacks). Newest phase first. Each item has a status: OPEN, RESOLVED (with where), or WONTFIX (with a reason).

## Phase 3 (2026-10-02): orchestrator findings (Phase 2 code and registry)

| # | Issue | Impact | Status |
|---|---|---|---|
| P3-O1 | **`just test` had a non-raw failure (review V4-01):** `tests/sam/test_sam_production.py::test_production_prior_closed_with_pseudo_entries_balances` failed with "KKT certificate FAILED". **Root cause: floating-point cancellation in the certificate's duality-gap test, not solver or library drift and not a stale block** (`test_built_outputs_equal_a_fresh_build` passes; the repo has a single snapshot commit, so no history to bisect). This synthetic prior is closed by construction (a free pseudo-entry per constraint target and I_OTHR closings), so the optimum sits at the prior: f = sum c (z ln z - z + 1) is about 1.9e-5 while sum c = 1.8e9. The certificate tests \|f - q\| / max(1, \|f\|) <= 1e-8, which here is an absolute 1e-8 on two sums whose rounding floor is about eps x sum c = 4e-7; it reported 2.2e-8 to 3.9e-8 of noise. The same iterate's gap through the exact identity f - q = -lambda.res - sum mu (s - bound) is 9e-13 to 2.2e-12, and a log1p form summed with math.fsum agrees. Every other criterion passed (stationarity 1.1e-16, residuals within tolerance, no bound, band or box violation). Likely latent since Wave B (S-2) made the gap a stopping and certificate test; FRAMEWORK_REQUESTS V-2 records the Wave A run of this test. A second defect in the test: the I_OTHR closings were summed by polars' parallel `group_by`, whose last bits vary from run to run, so the solver took 5 or 18 steps on different runs. | None on the Map or the certified SAM: its f is 1.14e5 and its recorded gap 3.15e-13 (`balancing_run.json`), well above the noise floor. `tests/verify/test_sam_balanced_audit.py` and `test_sam_solver_certificate.py` pass (79 passed, 1 known strict xfail BS-1). | RESOLVED in the test (2026-10-02): closings summed with math.fsum (deterministic input); every certificate criterion is required as before, and the gap is tested in the exact-identity form, plus a check that the certificate's own figure is within its rounding floor. `tests/sam`: 506 passed. Nothing in `pipeline/sam` or `data/sam` changed. |
| P3-O2 | **Latent framework weakness behind P3-O1:** `kkt_certificate` and Newton's `_gap_rel` compute f and q as large sums that cancel, so on any problem whose optimum is within about 1e-7 x sum c of the prior, the gap test measures rounding, not optimality (usually a false failure; noise of either sign could equally mask a true gap of the floor's size, though the stationarity and residual tests still bound such an iterate). | A future rebalance with a near-closed prior could fail loudly for no real reason. | OPEN (Phase 4+ framework change): compute the gap as -lambda.res - sum mu (s - bound) in `pipeline/sam/balance.py`. Not done now because it changes the recorded `duality_gap_rel` in `data/sam/2023-24/balancing_run.json` and possibly Newton's stopping step, i.e. the certified Phase 2 outputs; it needs a re-run, `repro` and an independent verifier. |
| P3-O3 | **A cited source came from an unmerged registry addition (reviews V1-07, V5-08):** `ifpri_nexus_sam_india_2022_23_paper` (cited by 263 SAM entries, 11 totals or bands and 24 story figures) was only in `data/registry_additions/io_tables.yaml` (unverified). | Its CC BY 4.0 licence and attribution rested on an unchecked record. | RESOLVED (2026-10-02): licence and release re-checked live on the CGSpace record (REST API and item page: dcterms.license CC-BY-4.0, Open Access, Data Paper, issued 2024-10-01, publisher IFPRI; PDF 501,277 bytes, the same byte count as the pinned file (hash not re-taken); no later India data paper) and merged into `data/registry.yaml` as `verified` with the evidence; the addition file now has no sources. Follow-ups for other owners: (a) the strict xfail `tests/verify/test_phase3_data_fidelity.py::test_every_cited_source_in_registry` now XPASSes and must be removed by its owner (V1); (b) `data/registry.yaml` is an export input, so the export must be re-run (`registry_status` for this source becomes `verified`; `tests/export/test_export_current.py` fails until then); (c) U1: the exporter's "not in data/registry.yaml" check still accepts additions (PLAN s.3.1). |
| P3-O4 | **Three registry additions stay unmerged:** `pib_gst_monthly_releases` (union_fiscal; licence text not found), `nss_health_2025_report` and `nss_cms_education_2025_report` (hces_consumption; licence assumed from other MoSPI reports, not re-read). None is cited by the Phase 3 export (all 32 cited sources are now in `registry.yaml`). | Clean data from them carries an unverified licence. | OPEN: verify and merge, or confirm terms, before any Phase 4 use or citation. |
| P3-O5 | **Story pages' axe `aria-prohibited-attr`** (docs/phase3/requests/U5.md): controlled-mode Sankey marks carried `aria-label` without a role. | Blocked `a11y.spec.ts` on the three story pages. | RESOLVED (fix in `SankeySvg.tsx` on 2026-10-02 by the integrator; re-verified 2026-11-10, thread 05): fresh build, `vitest` 523/523, Playwright Chromium desktop+phone 369 passed, 0 failed (a11y on all story pages included). WebKit projects not run on this host (browser not installed). |
| P3-O6 | **Data freshness re-check (2026-11-10, thread 05):** SPEC rule 2. NAS 2026 (31 Aug 2026; 2023-24 = Final Estimates, base 2022-23) is still MoSPI's latest: Statements 1.1, 1.14, 5.3, 7.1 re-downloaded with identical SHA-256; eSankhyiki API gives the same 2023-24 GDP (2,90,73,287 cr); no national-accounts release since except the Sources and Methods book (21 Sep, methods only). **Re-checked 2026-11-18 (Personal · Side apps): Statements 1.1, 1.14 and 5.3 re-downloaded, SHA-256 identical to the pins.** | None now. | OPEN (watch): re-check Statement 1.1's hash after the Q2 2026-27 release (30 Nov 2026) and the annual round (26 Feb 2027); rebuild only if a 2023-24 number moves. |

## Phase 2 (2026-10-01): headline issues

The balanced SAM 2023-24 passes every SPEC acceptance test. The items below are what it does not settle. Full detail: `docs/phase2/CHECKPOINT_B.md` (the owner summary), `BALANCING.md`, `docs/phase2/issues/<block>.md` (per block, with verifier dispositions) and `docs/phase2/verify/*.md`. Amounts in Rs lakh crore (1 lakh crore = 1,00,000 crore), FY 2023-24, with % of GDP (NAS GDP 290.73 lakh crore).

| # | Issue | Impact | Status |
|---|---|---|---|
| P2-1 | **Household distributive gap Z.** Households' accounts deliver less saving than NAS 1.9: -11.44 lakh (3.94% of GDP) at first assembly. After the evidenced repairs (D2-20, D2-21, D2-24) it is -3.85 lakh (1.32%). Balancing closes the rest through property income (+2.15), lower interest paid (+0.85) and State cash transfers (+0.58). | The household total is evidenced; the split over the ten groups follows the balancing weights and keys. | OPEN (Checkpoint B): closure-3, closure-19 |
| P2-2 | **Centre vs States.** Prior gaps: G_STA +4.50, G_CEN -2.99, GG +1.51 lakh. Traced to CSS money outside treasuries with no agency spending written, the Centre's own-output GFCE, GG deposit interest, and the States' outlays below treasury spending. | Balancing moves 0.88 lakh through the saving split, 0.87 lakh of GFCE and 0.46 lakh of product taxes. Union CGST, cess and excise end on their +5% cash ceilings. The direction is backed by FSF; the levels are not. | OPEN (Checkpoint B): government-27, -34, -35; taxes-26, -30 |
| P2-3 | **Public NFCs keep +3.13 lakh** (1.08%) over NAS saving, with no evidenced outlet once the published totals are held. | 12 explanation items say "Unexplained" (1.45 lakh of moves on E_NFPU interest and receipts); strict xfail `test_no_explanation_item_says_unexplained` (BS-1). Likely cause: departmental enterprises' surplus to GG is not written. | OPEN (Checkpoint B; NAD question): fincorp-37, government-33 |
| P2-4 | **Balanced levels set by tolerances.** 174 of 429 constraints end on a band edge (28 of 38 government). The widths of several bands are judgements: COFOG transfers ±5%, R9d / CSS / R18 ±10%, GST cash +5%, `f4b.centre` ±5%, `t4a.nfpu` ±25%. | Those flows' balanced levels equal the chosen tolerances. The owner should accept the widths or ask for a width sensitivity. | OPEN (Checkpoint B): V-GOV-13, factors-23 (V-F-10), taxes-29 (V-TX-6) |
| P2-5 | **FC sub-sector saving.** NAS fixes the total; FSF and RBI RTP disagree on the bank/NBFC split. Banks 4.59 → 4.12 lakh, NBFCs 3.38 → 4.05 lakh, insurers 1.00 → 0.78 lakh. Insurers' SAM investment income was 1.38 lakh below IRDAI + PF accounts. | 32 fincorp items are "level unexplained". | OPEN (Checkpoint B): fincorp-2, -31, -34(b) |
| P2-6 | **Household group profile.** Saving / (consumption + saving): rural Q4 40.1% vs rural Q5 13.5%. The keys rest on HCES (44.3% of NAS PFCE), IFPRI old-base gradients (k = q, D2-19), AIDIS 2019 and HCES item 539. T3a has no open source. | Every split by household group is estimated. Options: a rural/urban saving ordering, a crosswalk variant, a top-heavy PFCE variant. | OPEN (Checkpoint B): factors-19, -24; closure-16; households-1, -2, -19; taxes-8 |
| P2-7 | **Autonomous decisions awaiting the owner:** D2-11 (2.17 lakh of income tax on quasi-corporations), D2-13 (0.78 lakh cess as a current transfer), D2-19, D2-20 (R9b none; alternatives 1.87 / 4.27 lakh), D2-21 (old-base structures, 8.21 lakh of private NFC distributed income), D2-24 (PM-KISAN 0.52 lakh as a household transfer), and rest_of_world-26 (amends D2-7). | Each has a size, an alternative and its effect in CHECKPOINT_B.md §6. | OPEN (Checkpoint B) |
| P2-8 | **States' subsidies are 1.96 × RBI SF St 36** (6.47 vs 3.30 lakh). They rest on the NAS 4.2 identity for D39 and on unexplained SUT trade and pesticide subsidies (1.05 and 0.62 lakh). | The States' D39 residual is not supported by State-level evidence. | OPEN (NAD; Checkpoint B): taxes-11, -13, -24 |
| P2-9 | **NAS vs FSF financial accounts.** K9 residuals are lakh-sized (banks -5.22, States -1.80 lakh balanced). The SAM's NFC borrowing (F48) is 27.88 lakh against FSF's 22.17 (+25.7%). | They are different concepts; the residuals are named and logged, not bridged. | OPEN (Checkpoint B): capital_financial-1, -30; timeseries-25 |
| P2-10 | **RoW property income re-split** among domestic payers against FLA and EDR evidence. The Union's IMF income and SDR charges (6,929 + 7,118 crore) sit on the RBI. | Small in GDP terms. A decision is requested (amends D2-7). | OPEN (Checkpoint B): rest_of_world-26, -27 |
| P2-11 | **Old vs new base.** New/old ratios are uneven (PFCE 0.905, FC saving 1.31 in 2023-24). Only 10 flows are ratio-linked; 11 SAM checks are "explained" because balancing moved them. | The time series shows the break; the old-base structures used as priors do not match new-base totals. | OPEN (MoSPI back series, Dec 2026): timeseries-5, -26; P1-6 |
| P2-12 | **Questions for MoSPI NAD:** new-base institutional accounts; departmental-enterprise surplus and pensions; D612 in GG GDI; the NAS 4.2 subsidy concept; classification of PM-KISAN, motor-vehicle tax, STT and the cess-funded loan repayment; dwelling CFC by sector; imputed-rent source; spectrum; RBI surplus accrual. | Answers would replace most of the judgement calls in P2-1 to P2-8. | OPEN: owner (one letter; list in CHECKPOINT_B.md §7) |
| P2-13 | **Data access** that would turn estimates into data: CBDT ITR distribution (T3a), unit-level HCES/PLFS/AIDIS, DPE survey, RBI corporate finances and credit by purpose, GSTN settlement timing, NSDL FPI, IGAS-2 grantee spending, RGI population. | Blocked by policy, terms or registration (P1-4, D1-1, D1-2). | OPEN: owner |
| P2-14 | **Framework and coverage gaps:** premiums = claims by payer cannot be declared (FR-C-3; strict xfail for V-FIN-9); P6a (imports by using activity) and S6 (energy PSUT by activity) not built. | Minor. | OPEN: FRAMEWORK_REQUESTS FR-C-3; production-2, -3 |

## Phase 1 (2026-09-29): headline issues

Full detail: `docs/phase1/COVERAGE.md`, `docs/phase1/RECONCILIATION.md`, `docs/phase1/issues/<unit>.md` (per unit, with verifier dispositions), `docs/phase1/verify/<unit>.md`.

| # | Issue | Impact | Status |
|---|---|---|---|
| P1-1 | **10 of the 56 OFFICIAL gap-map cells are only partly covered**: I3a, R2, R3, R7, R9, K6, K8b, S7, S9, S6. R3, R7 and R9 are complete once the Union and State halves are combined. | Phase 2 handles them by combining sources or estimating, with the reasons listed in COVERAGE.md. | HANDLED in Phase 2 (2026-10-01). R3, R7 and R9 combine the Union and State halves. I3a, R2, K6 and K8b hold their published totals, with the splits estimated: CSS outside treasuries is banded ±10% (government-34) and K6 ±5% of NAS 4.2 COFOG. S7 (`s7_igst_settlement`) and S9 (`s9_funded_schemes`) are published as partial satellites. S6 by activity is not built (production-3, OPEN). |
| P1-2 | **23 UNEXPLAINED cross-source gaps** (kept as xfail tests so they stay visible). Largest: FSF vs NAS net lending by sector (NFC −₹5.73 lakh cr in 2023-24; FC +₹2.29; HH +₹2.95; GG +₹1.20); SUT product taxes exceed Union + State receipts by ₹1.61 lakh cr (+5.2%); grants to States disagree across Finance Accounts views (MH 3601 vs IGAS-2 −₹1.41 lakh cr) and vs RBI State Finances (+₹0.67 lakh cr); State CE in NAS vs FC16 salaries +8.4%; product subsidies SUT vs budgets +8.1%; FPI BoP vs SEBI +8.9%. | These become explicit, logged residuals in Phase 2 balancing, never silent adjustments. | HANDLED in Phase 2 (2026-10-01); residuals OPEN as P2-2, P2-8 and P2-9. **FSF vs NAS:** NAS is the control and the differences sit in named K9 residuals; F48 is +25.7% vs FSF (timeseries-25). **TAX-1:** 1.61 → 0.47 lakh after D2-4 (taxes-1). **Grants:** institutional view (D2-8), with CSS outside treasuries banded (government-34). **Subsidies:** the SUT wins; States end at 1.96 × St 36 (taxes-24). **FPI:** BoP used. **GOV-7:** open (fincorp-10). The 23 xfail tests stay. |
| P1-3 | **rbidocs.rbi.org.in serves a bot challenge** since about 15:00 IST on 29 Sep. Files fetched before that are pinned; under D1-4 the framework now refuses a host for the rest of a run after its first challenge. PIB also challenged after 2 of 12 monthly GST releases. | Refreshes of RBI files may fail until RBI grants permission or the challenge lifts. | OPEN: owner (RBI permission) |
| P1-4 | **Blocked by policy or terms:** GSTN and CBDT (D1-1c); unit-level microdata (D1-2); NSDL FPI Monitor and AMFI (terms forbid reuse, refused in code); Commerce TradeStat (session/CSRF form, plus a DGCI&S permission); STRBI, detailed BSR and RBI corporate-finance levels (DBIE only); IFPRI SAM file (guestbook); OECD ICIO zip (Cloudflare challenge); DPE survey (keyed CMS API). | Substitutes are in use (Finance Accounts, PIB, published report tables, IMF IMTS and the Comtrade preview, RTP tables, ADB MRIO and FIGARO). **T3a (income-tax incidence by household group) has no open input at all.** | OPEN: owner access list (Checkpoint A) |
| P1-5 | **Survey reference periods are not fiscal years.** HCES runs Aug–Jul, and PLFS and NSS rounds run Jul–Jun. They're now stored with an explicit survey-window period type (`sy`). | Phase 2 must map survey windows to FY 2023-24 explicitly and label the mapping. | RESOLVED in data; Phase 2 method |
| P1-6 | **Old-base vs new-base series:** the new-base back series is still unpublished. The NAS API old-base series from 1950-51 is ingested for the time series, kept separate by base_year. | The time series will carry a visible break at 2022-23. | OPEN (MoSPI, expected Dec 2026) |
| P1-7 | **Publisher defects found and handled:** NAS 2024 St 3.0 code column shifted one row (the build now asserts it); a misprinted FSF label for pension funds vs others (counterparties reassigned and flagged); undivided AP double-counted in the RBI State Finances guarantees aggregate; an AP 2022-23 subsidy figure apparently carried forward; stale PLFS table pages; an HCES A6/A10S publisher break. | Each is documented in its unit's issue file with evidence. | RESOLVED / DOCUMENTED |
| P1-8 | Cosmetic follow-ups (no effect on values or tests): union_fiscal coverage note wording (K6 extent 'partial', citation union_fiscal-23, "Expenditure Profile"); stale lines in the finsector_markets, trade_satellites and state_fiscal issue files. | Housekeeping. | OPEN (minor) |
| P1-9 | **Pre-launch permissions** (RBI deep-link and caching, MoF, SEBI, GSTN, DGCI&S, CAG) are still outstanding. | Blocks the public site (Checkpoint C), not the pipeline. | CLOSED (owner, 2026-11-18): no permission requests will be made. The site shows only the model's own computed figures, credited to their publishers; raw source files are never published (git-ignored, private repo) and RBI files are not deep-linked. Maps and stories stay as they are. A source whose terms forbid even that would have its figures removed. |

## Phase 0 (2026-09-29): headline issues

| # | Issue | Impact | Status |
|---|---|---|---|
| P0-1 | **No new-base (2022-23) institutional sequences of accounts** (interest, dividends, transfers and taxes by institution) exist for any year. NAS 2026 publishes only Statement 1.14 key indicators; NAS 2026 statement files for the full sequences return 403. | The institution × institution transfer block must be estimated, anchored to official sector totals and to old-base (NAS 2024, to 2022-23) ratios. | OPEN: ask MoSPI NAD (access list) |
| P0-2 | **The official 2023-24 accounts do not close.** Household residual ₹5,71,133 cr; saving–investment errors and omissions ₹3,58,634 cr; NAS–BoP CIF gap ₹2,12,499 cr. | They are carried in an explicit `X_DISC` account, not balanced away. | OPEN (design decision; see ACCOUNT_STRUCTURE §9) |
| P0-3 | **The Flow of Funds (RBI FSF 2023-24) is on the old GDP base**, and 2023-24 household credit is distorted by the HDFC–HDFC Bank merger (1 Jul 2023). | The FoF is used for structure and counterparties only, with NAS 5.3 and BoP as controls; the merger is treated as a reclassification. | OPEN |
| P0-4 | **HCES consumption is only ~44% of NAS PFCE.** | Quintile shares from HCES are scaled to the NAS control total; the method and its limits are shown in the UI. | OPEN (method in GAP_MAP §4) |
| P0-5 | **Three-plus vintages of the new GDP series** (27 Feb, 5 Jun, 31 Aug 2026). SUT 2022-23 and 2023-24 xlsx files were silently replaced on 31 Aug 2026 without a version label. | Every raw file must be pinned by sha256 plus vintage; the pipeline must detect silent replacement. | OPEN (Phase 1 design requirement) |
| P0-6 | **No new-base back series before 2022-23** (expected by Dec 2026). There is a ~-2.9% level break at rebasing. | The Phase 2 time series must either wait or splice old-base data, visibly labelled. | OPEN |
| P0-7 | **Licences: no source states GODL-India explicitly.** RBI's Disclaimer restricts deep links and caching without permission; the MoF, SEBI, GSTN and DGCI&S terms require permission to reproduce; GSTN classes scraping as unauthorised; the GSDD 2026 Category B unit-data "non-commercial" definition may catch a company-run public site. | Permissions must be requested before the public launch (see SOURCES.md §5). | OPEN: owner |
| P0-8 | **Bot protection.** RBI's rbidocs (F5 challenge), incometaxindia.gov.in (403), MoSPI /uploads (403 without browser-style headers), data.gov.in (timeouts, robots `Disallow: /`, labelled a "sandbox"). | Manual downloads by the owner or written permission for scripted access; data.gov.in is not relied on. | OPEN: owner |
| P0-9 | **The latest official symmetric IOTT is 2007-08.** Only SUTs exist for recent years. | The design uses an activity × commodity SAM; the multiplier model makes an explicit technology assumption. | RESOLVED (design) |
| P0-10 | **Classification questions Sources & Methods doesn't answer** (motor-vehicle tax class, farm-support class, RBI surplus cash vs accrual, cess-funded loan recovery, OPS factor, Trade/pesticide subsidy rows). | Defaults chosen and flagged; questions for MoSPI NAD. | OPEN (DESIGN_REVIEW.md) |
| P0-11 | **Three registry entries were added during the fix pass** (mospi_asuse_unit_data, nsi_small_savings_collections, dpe_public_enterprises_survey) and have not been through an independent verifier. The DPE survey content could not be read (JS-only site). | Status is `unverified` in the registry. | OPEN: verify at the start of Phase 1 |
| P0-12 | **WebSearch quota ran out** during verification (200/200), so later verifiers used direct fetches only. News-based claims (e.g. BusinessLine on back-series timing) could not be re-checked. | These claims are marked unverified. | OPEN |
| P0-13 | **Releases due 29–30 Sep 2026** (ASI 2024-25, end-June 2026 external debt and IIP, Q1 2026-27 invisibles) were not yet out at check time. | The registry was frozen at 2026-09-29; refresh at the start of Phase 1. | OPEN |
| P0-14 | The **MoSPI NAS API** CSV format returns only the header row (JSON works); the official esankhyiki Python client defaults to a private UAT IP. | The ingest layer uses JSON and sets the production base URL explicitly. | OPEN (Phase 1 note) |
| P0-15 | **Windows environment:** `core.autocrlf=true` is set system-wide, there is no `sh` on PATH, and BLAS inverse bytes vary with thread count. | `.gitattributes` enforces LF; threads are pinned; floats are rounded before writing; Linux CI is authoritative (STACK_AND_REPO §11). | PARTLY RESOLVED (.gitattributes added) |

## Phase 0: raw issue log by source family

Verbatim from the finder and verifier agents. Many are resolved in SOURCES.md, REFERENCE_YEAR.md or DESIGN_REVIEW.md; this is the audit trail.


### mospi_nas

Verifier verdicts: {'corrected': 3, 'confirmed': 3, 'unverifiable': 1}

**Finder:**

- Full institutional sequences of accounts (Statements 1.3, 1.15, 2.0-2.2, 3.0-3.2, 4.0, 5.0, 6.0) are absent from NAS 2026 and NAS 2025. Files under NAS-2026-Statements return 403 and under NAS2025 return 404. MoSPI's own Sources and Methods (§30.7, 21 Sep 2026) says NAS contains them. On the new base only Statement 1.14 key indicators exist, so the primary/secondary income distribution by institution must come from old-base NAS 2024 (to 2022-23) or be estimated.
- No back series on base 2022-23 yet (expected by Dec 2026, per the FAQ and the 27 Feb press note). The time series before 2022-23 must use old-base data, with a level break of about -2.7% in 2022-23 GDP (old 2,68,90,473 vs new 2,61,77,001 crore).
- Two vintages of the new series exist (27 Feb 2026 and 31 Aug 2026 / NAS 2026). For example, 2022-23 GDP changed from 2,61,17,627 to 2,61,77,001 crore. Provenance must record the vintage.
- The original 27 Feb 2026 press-note URL (latest_release_1772189865181_..._27022026.pdf) now returns HTTP 403. It was replaced by a '-F' file. MoSPI /uploads/ returns 403 rather than 404 for missing files.
- mospi.gov.in and esankhyiki.mospi.gov.in are React SPAs. HTML pages contain no data, so file lists had to be read from the public JSON endpoints under https://www.mospi.gov.in/api/.
- api.mospi.gov.in getNASData with Format=CSV returns only the header row (three queries tested); JSON works.
- The official esankhyiki Python client defaults to the private UAT base_url http://10.24.89.9:5000; production https://api.mospi.gov.in must be set explicitly.
- data.gov.in catalog pages (national-accounts-key-aggregates) timed out twice via curl (90 s) and returned HTTP 403 to WebFetch. Whether the 2022-23-base data are mirrored there is unverified. The /government-open-data-license-india URL redirects to page_not_found.
- The current-price discrepancy is 0 only for Final years. The 2024-25 FRE (-1,07,438 crore), 2025-26 PE (-1,18,500 crore), constant-price and quarterly discrepancies are non-zero (e.g. Q1 2026-27 current -69,478 crore).
- State GSDP (API account_code=2) is still on base 2011-12 only; the new-base state series is not yet published.
- No explicit GODL licence on mospi.gov.in. Reuse rests on GSDD 2026 Category A open access plus the copyright policy (accurate reproduction, not misleading, source acknowledged).
- The BusinessLine report (21 Sep 2026) on back-series timing was seen only as a search-result headline (paywalled); not opened.

**Verifier:**

- WebSearch budget exhausted (200/200) in this session, so all checks used direct fetches. News coverage (e.g. the BusinessLine back-series report) could not be re-checked.
- Critical: saving–investment errors & omissions are non-zero in all new-base years (+5,20,083; +3,58,634; -2,79,181 crore as GCF minus saving plus NCI). NAS does not publish them as a row; they are implied by 1.1 vs 1.9 and documented in S&M §26.6.
- Critical: household GDI is derived as a residual (27 Feb Formula 12) while household saving is estimated independently, so the household account does not close (+8,12,857; +5,71,133; -1,28,402 crore).
- Statement 6.1 current account uses services imports without the CIF adjustment (-5,27,525 cr in 2022-23), while the 1.1 aggregates are CIF-adjusted (implied -2,34,750 cr). The SAM RoW account needs one consistent treatment.
- NAS 4.2 COFOG has no government interest payments (property income). D41 for government must come from budget or RBI sources or the old-base 4.0.
- There are at least 3 vintages of the new series (27 Feb, 5 Jun, 31 Aug 2026), and the 2024-25 discrepancy flipped sign between the 5 Jun and 31 Aug vintages.
- PE 2025-26 was released on 5 June 2026 (not 7 June). The 7 June rule applies from now on.
- The data.gov.in footer declares the site a 'sandbox environment … data … may be incomplete or inaccurate'. Catalog pages time out or return 403. Do not rely on it.
- The MoSPI latest-release and publication list APIs paginate only with the body key {"page_no":N}. Other keys silently return page 1.
- MoSPI CMS publication dates for NAS 2024/2025 cannot be cross-checked against file Last-Modified (all 16 May 2025, which looks like a migration stamp).

**Reference-year corrections:**

- NAS-side candidate 2023-24 confirmed: the latest Final year on the new base, with a zero current-price expenditure discrepancy and a SUT (updated 31 Aug 2026). But the capital account does NOT close. Gross saving + net capital inflow falls short of GCF by 3,58,634 cr (1.23% of GDP), and the household residual (HH GDI - PFCE - HH saving) is 5,71,133 cr. Both must be carried as explicit errors & omissions / balancing items.
- 2024-25 is FRE (discrepancy -1,07,438 cr). Its Final estimate is due 26 Feb 2027, which will likely bring a zero discrepancy and an updated SUT.
- The NAS full sequence of accounts (D1-D8 by sector) is available only for 2022-23 at the latest, on the OLD base (NAS 2024), and for no year on the new base.
- New-base State GSDP: not yet published (API base 2011-12 only). The new-base 2022-23 to 2024-25 GSDP is under finalisation (joint discussions ended 19 Jun 2026).
- New back series (base 2022-23): not released as of 2026-09-29; expected by Dec 2026. The old-base back series in the API runs from 1950-51.

### mospi_io

Verifier verdicts: {'corrected': 7, 'confirmed': 5}

**Finder:**

- www.mospi.gov.in file URLs (/uploads/..., /sites/default/files/...) return HTTP 403 to WebFetch and to plain curl. They return 200 only with browser-style headers (Sec-Fetch-Dest: document, Sec-Fetch-Mode: navigate, browser User-Agent, Referer). No login or CAPTCHA is involved. www.pib.gov.in also returned 403 to WebFetch but 200 to curl with browser headers.
- www.mospi.gov.in is a React SPA: every route returns the same 2.6 KB shell. Content lists require POST to https://www.mospi.gov.in/api/... (GET returns 403). robots.txt returns the SPA shell (no rules).
- Contradiction: the SUT press release (15 May 2026) says 'adoption of updated classifications like NIC 2025', but the SUT methodological note says 'NIC 2008 and NPCMS 2011 (Revised)/NPCSS have been used'.
- The SUT 2022-23 and 2023-24 xlsx files were silently replaced on 2026-08-31 with no version label. The May-release total supply at PP (627.18 lakh crore for 2022-23) no longer matches the file (628.01 lakh crore). The original files are no longer listed.
- There is no official IOTT after 2007-08. The SUT has no valuation matrices (TTM and taxes by use cell), no import-use matrix, and no GST sub-split (CGST/SGST/IGST/cess). All of these must be estimated for the SAM.
- ASI 2024-25 results are not in the MoSPI latest-release feed through 2026-09-28; ASI 2023-24 came out 27 Aug 2025, so this looks overdue. Expected date unverified.
- The NAS back series before 2022-23 is not yet released (FAQ: expected by Dec 2026). Old-base SUTs 2011-12 to 2021-22 are not comparable with the new series, and units vary (Rs lakh in 2015-16, Rs crore in 2021-22).
- Licence: MoSPI's copyright policy references 'revised GSDD 2026', but the GSDD 2026 document could not be located (only the 2019 GSDD and a Jan 2025 draft). No GODL named. OEA (eaindustry.nic.in) links disclaimer.asp, which returns HTTP 404; no licence found.
- The api.mospi.gov.in CPI endpoint getCPIIndex returns 'No Data Found' for base 2024 (must use getCPIData). getCPIData rejects limit<10. The IIP swagger YAML on GitHub omits base 2022-23, although the live API accepts it.
- The eSankhyiki Energy API covers only 2012-13 to 2023-24 while the ES 2026 book covers 2024-25.
- MoSPI API file metadata (filesize) is unreliable (e.g. 351272960 for a PDF; Energy Ch6/Ch7 listed with identical sizes).
- No machine-readable SUT product<->NPCMS or industry<->NIC concordance was found in the SUT publication; only the narrative method is in the note. NPCSS was not located as a standalone file.
- api.data.gov.in returned HTTP 503 on probe; data.gov.in pages are an SPA that was not parsed.
- The first WebFetch attempts on the MoSPI GDP press note and PIB returned 403. The esankhyiki ard.json fetch hung more than 120 s once (succeeded on retry with a timeout).

**Verifier:**

- Finder's access-method claim (Sec-Fetch headers required, WebFetch gets 403 on MoSPI files) was not reproducible on 2026-09-29. Plain GETs and WebFetch returned 200. WAF behaviour may be intermittent, so the pipeline should retry and log, and must not spoof browsers.
- PIB press-release pages returned 401/403 to curl and WebFetch. They returned 200 only with full browser navigation headers plus a cookie jar. Prefer the MoSPI-hosted PDF copies of PIB releases.
- SUT files carry no internal version stamp, and the May 2026 originals are no longer listed. Hash every download and alert on change. The May PR totals (627.18 and 669.88 lakh crore) disagree with the revised files (628.01 and 671.79).
- The NIC 2025 vs NIC 2008 contradiction between the SUT PR and the SUT note is confirmed. Treat the SUT as NIC 2008-based (per the note) and the IIP as NIC 2025-based. The concordance exists only at 4-digit.
- NPCMS_2011_revised.pdf is the manufacturing-only product classification with no HS concordance. NPCSS could not be located. No SUT product/industry concordance file is published.
- NMDS_SUT.xlsx is old-series (2011-12) metadata and is wrongly attached to the new-base SUT source.
- The Energy API returns HTTP 500 with a leaked Postgres error when a required parameter is missing; validate parameters client-side.
- GSDD 2026 (the reuse terms cited in MoSPI's copyright policy) could not be found in the acts/policies, public-documents or announcement lists. The OEA disclaimer.asp returns 404. The licence position for republishing derived data is unconfirmed.
- WebSearch was unavailable to this verifier (session budget exhausted). All checks were done by direct fetch, so external secondary sources were not searched. Notes are written to D:\India Economy Model\docs\phase0\verify\mospi_io.md.

**Reference-year corrections:**

- SUT (new series): latest year 2023-24 (also 2022-23), base 2022-23, Aug-2026 vintage consistent with NAS 2026 Final Estimates. Confirmed by recomputing GDP from the xlsx. A 2024-25 SUT cannot precede the FE of 2024-25, which the ARC schedules for 26 Feb 2027 (the SUT timing itself is an inference). The 2023-24 SUT is the binding constraint from this family.
- ASI: CORRECTION. The latest published year is 2023-24, but ASI 2024-25 results are scheduled for 29 Sep 2026 (today) per ARC 2026-27. Not released as of about 12:35 IST. It is not 'overdue'; re-check after release.
- Energy: physical energy SUT exists for 2023-24 (final) and 2024-25(P) in ES 2026 Ch 9. The API energy balance runs 2012-13 to 2023-24 (confirmed).
- IIP/WPI/OPPI: monthly from April 2023 to August 2026 on base 2022-23, so FY 2023-24 is fully covered. CPI 2024 base starts January 2025; FY 2023-24 is covered only via the general-index back series (linking factors) or the 2012-base series.
- Service PPIs start in Q1 2023-24, except Air (Passenger), which starts in FY 2025-26.
- IOTT: latest official is 2007-08 (130 sectors, factor cost, 2004-05 NAS series). No official symmetric IOT exists for 2022-23 or 2023-24; one must be derived from the SUT (estimated).

### mospi_households

Verifier verdicts: {'confirmed': 10, 'corrected': 6, 'unverifiable': 1}

**Finder:**

- MoSPI main site (www.mospi.gov.in) is a JavaScript single-page app: product pages, the copyright policy page and the full PLFS Annual Report 2025 PDF URL could not be read with curl/WebFetch. Browser rendering was not available because several Chrome browsers are connected and a subagent cannot ask the user which to use.
- MoSPI internal endpoint https://www.mospi.gov.in/api/main-site/product-search returned 403. Not pursued further because it is not a documented public API.
- The new-GDP-series press note at https://www.mospi.gov.in/uploads/latestReleases/latest_release_1772189865181_...27022026.pdf returned 403 to curl. I read the PIB version (PRID 2233518) instead.
- https://www.mospi.gov.in/sites/default/files/press_release/PressNote_AIDIS_SAS-Final.pdf returned 404.
- The NSS publication-use policy PDF (policy_nss_pub_25se17.pdf) is a scanned image with no text layer, so it was not read.
- The GSDD 2026 PDF failed over http:// (curl code 000) and worked over https://. https://www.niip.gov.in/web/mospi/copyright-policy failed (curl 000).
- WebFetch gets 403 on pib.gov.in; curl with a browser User-Agent works.
- A search snippet attributed to MoSPI's copyright policy says reproduction needs 'proper permission by sending a mail'. This conflicts with GSDD 2026, which makes reports open access. It is UNVERIFIED because the page could not be rendered.
- No explicit GODL-India licence statement was found for MoSPI publications. The governing terms are GSDD 2026 (Category A open access; Category B non-commercial only).
- The swagger for api.mospi.gov.in declares a bearerAuth scheme, but calls worked without a token. Access terms for the API may change.
- Contradiction or series break: PLFS 2025 is not comparable with earlier years (MoSPI caveat). There is no July 2024–June 2025 PLFS annual report. ASUSE has a coverage gap for Oct–Dec 2024.
- Large level gap: HCES 2023-24 per-capita consumption is about 51% of NAS PFCE per capita, and the HCES population estimate (1,217.6 mn) is well below the NAS-implied population (~1,395 mn). My computation, estimated. HCES must be used for shares only.
- The PIB note of 17 Mar 2026 gives the NHIS period as 'April 2026 to March 2026' (a typo). The NHIS results date ('mid-2027') comes only from secondary sources and is unverified.
- Not verified: WID licence and latest year, CMIE CPHS price, PRICE ICE360 reuse terms, IHDS-3 release (none found), and the AIDIS 2019 flow reference period.
- The NADA catalog 'created on' dates are portal-entry dates, not original release dates (e.g., the HCES 2022-23 entry was created Dec 2024, but the data was released June 2024).

**Verifier:**

- The HCES API call without indicator_code got no response within 120 s (HTTP 000). The recon's evidence URL hid the parameters ('...'). The swagger marks indicator_code as required.
- The PLFS API 'annual' earnings return four quarterly CWS values, not one annual number. The pipeline must aggregate them or use the report tables.
- WID licence: the active link is CC BY-NC-SA 4.0 (a commented-out tooltip says CC BY 4.0). The terms-of-use page returns 404. Treat WID as non-commercial/share-alike unless WID confirms otherwise.
- The recon lists 'Household income proxies' as a SAM use of HCES unit data. HCES has no income questions, and MoSPI's Rider tells users not to use the auxiliary household variables for estimation. Remove this use.
- ICPSR IHDS page returns 403 to curl, so its terms are unverified.
- MoSPI NHIS press note URL (Press%20Note%20NHIS%202026_13.10.2025.pdf) returns 404. PressNote_AIDIS_SAS-Final.pdf returns 404 (reproduced).
- MoSPI copyright-policy page is still unreadable: WebFetch saw only the title (JS SPA). It is unverified whether it conflicts with GSDD 2026. The owner should check it in a browser.
- The microdata portal still links GSDD 2026 over http://. The recon noted that the http:// URL fails, so use https://.
- NHIS sample size (4.5 lakh households) and the mid-2027 results date come only from secondary sources.
- TUS 2024 report release date (March 2025) was not re-verified against a primary source.
- The WebSearch budget ran out during verification. Remaining checks used direct curl fetches only, so a HCES next-round announcement could not be confirmed.
- Notes written to D:\India Economy Model\docs\phase0\verify\mospi_households.md. Probe files are in the session scratchpad only.

**Reference-year corrections:**

- PLFS quarterly: Apr–Jun 2026 is AVAILABLE, not just scheduled. The API returns 2026 Jan-Mar and Apr-Jun rows (frequency_code=2).
- PLFS annual: besides CY 2025 (new design) and agricultural years to 2023-24, the AR 2025 presents calendar-year 2022–2024 results derived from unit-level data. A CY-aligned 2022–2024 series therefore exists, with a comparability caveat against 2025.
- ASUSE: add quarterly 2026 Q1 (Jan–Mar) and Q2 (Apr–Jun) via the API. ASUSE 2025 unit data appeared 6 May 2026 (catalog 293), not in April as announced.
- AIDIS/SAS: the new round is in the field (Jul 2026–Jun 2027), so the 2019 round stays the latest for any reference year up to at least 2027-28 releases (inference).
- HCES: the latest is still 2023-24. Free-item imputation by quintile can be estimated from published A10F quantities plus imputation rates. 'No future round' is unverified: a press report suggests a round in about 3 years.
- New NAS 2022-23 base: the household sector level is compiled from ASUSE + PLFS (primary PIB source). This strengthens FY 2022-23 or 2023-24 as the household-consistent reference year. FY 2024-25+ lacks HCES and straddles the PLFS design break and the ASUSE Oct–Dec 2024 gap.

### rbi_core

Verifier verdicts: {'corrected': 6, 'confirmed': 9}

**Finder:**

- rbidocs.rbi.org.in serves an F5 TSPD JS bot challenge to minimal curl (HTML 48 KB instead of XLSX). Standard browser headers returned the files. A third party reports CAPTCHA escalation (not observed). Pipelines must be polite and never solve challenges.
- dbie.rbi.org.in (old DBIE host) does not connect (curl 000), so old RBI links to it (e.g. Basic Statistical Returns Vol 47) are dead.
- DBIE has no documented public API. Reports/Publications (STRBI, detailed BSR, HBS online) are SAP BusinessObjects reports needing a guest session that is reportedly rationed.
- No explicit data licence on rbi.org.in or data.rbi.org.in. The Disclaimer prohibits caching and framing and requires prior permission for deep links. This conflicts with the project's plan to link every number to its source.
- HBS mixes GDP bases across tables (T1/T11 new 2022-23 base; T12/T13 old 2011-12 base).
- FSF/FoF 2023-24 is on the old base (inferred); no new-base FoF and no 2024-25 FoF yet.
- The Household Financial Savings quarterly page is stale (latest Aug 28, 2025). Current data exist only as Bulletin table 52(a)/(b), and no XLSX link was found for Sept 2026 (PDF only).
- Series break: bank-credit reporting date changed to month-end from Dec 31, 2025 (Banking Laws (Amendment) Act 2025). The HDFC merger on 1 Jul 2023 and HFC-to-NBFC conversions also affect bank/NBFC/HFC splits.
- Discontinued releases: Composition and Ownership Pattern of Deposits (last Mar 2018); Performance of Non-Govt NBFIs (last 2018-19, released Jul 2020).
- HalfYearlyPublications.aspx?head=Financial Stability Report returned 'Error occured. Please try again.'; FsReports.aspx works.
- No robots.txt is served (rbi.org.in returns a WAF 'Unauthorised Access' page; data.rbi.org.in returns 'Page Not Found').
- Unverified third-party DBIE mirror at dbie.rbihub.in (GitHub org not verified; rbihub.in does not mention it). It reverse-engineers the DBIE gateway cipher, so it should not be used as a source or method.
- The DBIE disclaimer text could not be read because it loads at runtime via an internal API. Chrome automation was not used because several browsers were connected and a subagent cannot ask the user to pick one.
- NAS 2026 release (reported as 31 Aug 2026) is known only from secondary sources. The MOSPI family must verify it.

**Verifier:**

- Licence finding: RBI Bulletin content carries an explicit reproduction permission with acknowledgement, and the archived DBIE disclaimer said the same. The recon's blanket 'no explicit licence found' is wrong for Bulletin/DBIE data. The website Disclaimer's deep-link/framing/caching restriction is separate and still needs an RBI request.
- The current DBIE disclaimer text cannot be read without executing the SPA (route /dbie/disclaimer); static paths return 404. It is unverified.
- dbie.rbi.org.in is a TLS certificate-mismatch redirect to data.rbi.org.in, not an unreachable host. Old links fail in strict clients but the server redirects.
- FSF workbook contains unindexed legacy sheets S 8.4-8.7 labelled '₹ Billion' with crore-magnitude values and only 2011-12..2017-18 coverage. An ingestion pipeline must exclude them or flag them.
- FSF FWTW (S 6.x) is sector x sector only. Instrument detail is a separate instrument x sector table (S 7.x), so a full from-whom-to-whom-by-instrument matrix needs estimation.
- Household financial savings estimates differ between RBI (52a) and NSO (HBS T11) and are revised heavily between vintages.
- rbidocs access behaviour: the default curl UA gets its TLS connection dropped, a browser UA alone gets the F5 TSPD JS challenge, and full browser headers get the file. Do not attempt to solve challenges.
- Web search quota (200) was exhausted during verification, so no secondary search was possible for RCF editions after July 2024 or for the NBFC series start. Primary RBI listing pages were used instead.
- Not reproduced or unverifiable: DBIE BOE guest-session rationing, the 252 SDMX element count, the dbie.rbihub.in affiliation, and the discontinuation of Composition and Ownership Pattern of Deposits.

**Reference-year corrections:**

- FSF/FWTW latest = 2023-24 (confirmed), on the old 2011-12 base (inferred from 12.0% nominal growth vs 10.97% new-base). It is the only year with an official RBI FWTW; any later reference year needs the financial block estimated.
- Bulletin 52(a) household flows: 2025-26 preliminary confirmed, but the vintages are unstable. 2024-25 NFA was revised from 19,94,202.4 crore (Aug 2025, old base) to 22,57,092.5 crore (Sep 2026), and RBI states estimates 'will undergo revision with the release of National Accounts Statistics 2024-25 by the NSO'. Pin the vintage and retrieval date.
- RTP NBFC balance sheet: end-March 2025 is latest annual (plus end-September 2025), available as XLSX Appendix VI.1 (not PDF-only).
- NBFC monthly sectoral credit exists only from the Jul 2026 release (data columns from 31-Jul-2024), so it cannot supply a 2023-24 year.
- Add HBS T49 consolidated SCB balance sheet (latest 2024-25) and AR 2025-26 Appendix 3 gross savings % GNDI (new base, 2022-23..2024-25) as reference-year inputs.
- HBS T42's 2025-26 value is a month-end (31-Mar-2026) figure despite its 'last reporting Friday' header, so there is a break against earlier years.

### external

Verifier verdicts: {'confirmed': 18, 'corrected': 4, 'unverifiable': 1}

**Finder:**

- rbidocs.rbi.org.in blocks automated downloads (F5/TSPD JavaScript challenge to curl/requests; CAPTCHA to WebFetch). Affected: BoP Statements I/II (BOPS01092026_1/2.xlsx), external debt statements, IIP xlsx, invisibles xlsx (IRIPQ4E30062026.xlsx), ODI xlsx, HBS XLSX/PDF, Bulletin PDFs. Not bypassed. Workaround: parse the HTML pages on www.rbi.org.in, or download manually.
- The RBI website disclaimer prohibits caching, framing and deep-linking without permission and states no open-data licence. This conflicts with SPEC rule 5 (attribute and link every source) until RBI permission is obtained.
- www.rbi.org.in/robots.txt returns an 'Unauthorised Access' page (Support ID 679480896859709071), so the robots rules could not be read.
- dbie.rbi.org.in fails TLS verification (SEC_E_WRONG_PRINCIPAL certificate name mismatch); it redirects to data.rbi.org.in/DBIE only with -k. DBIE is a JS SPA with no documented public API.
- dbie.rbihub.in (Next.js 'RBI DBIE' front-end) has unverified official status and terms, and shows a stale 'Real GDP growth Q2 2025-26' tile.
- DGCI&S copyright and re-dissemination policy restricts publishing TradeStat/DGCI&S trade data on the public site without written permission from DG, DGCIS. Detailed portal data need login plus payment.
- TradeStat flags an ITC-HS reclassification ('dropped or re-allocated ... from April 2026'), which is a classification break for 2026-27 onward.
- The DPIIT website is client-rendered: the FDI factsheet listing and the copyright/terms pages cannot be read by curl, and WebFetch gets 403. The June 2026 factsheet PDF URL was not found (only press reports). The DPIIT licence is unverified.
- mospi.gov.in returns HTTP 403 to curl and WebFetch, so the GDP 2022-23 base-year release (27 Feb 2026) is confirmed only via search results.
- imf.org terms page and data.imf.org return 403. The IMF licence terms come from a search snippet only (medium confidence). The IMF SDMX API itself works.
- data.gov.in robots.txt says 'Disallow: /'. OGD catalogs (possibly GODL-licensed Commerce trade-by-partner data) were not fetched; use api.data.gov.in with a key.
- The monthly BoP (non-BPM6) does not add up to the quarterly BPM6 (Apr-Jun 2026 CA -3.1 vs -4.2; transfers 41.4 vs secondary income 40.8). Keep the two series separate.
- Old-format reserves-variation tables differ from BPM6 (2025-26 CAB -25.4 vs -25.2).
- RBI %-of-GDP ratios were restated (end-March 2025 external debt/GDP 19.1% to 19.8%) without stating the GDP series used. This is inferred to be the new base; the national-accounts family should confirm.
- 2026-27 external flows are distorted by the RBI FCNR(B)/ECB/OFCB swap window (US$143.6 bn mobilised by 18 Sep 2026), the West Asia oil shock and rupee depreciation (~₹96/US$). 2026-27 is unsuitable as a SAM reference year.
- End-June 2026 IIP and external debt were not yet released as of 2026-09-29 (expected ~30 Sep 2026).
- No 7th-round RBI Remittances Survey was found. The source-country split rests on 2023-24 shares.
- The World Bank bilateral remittance matrix appears to be 2021 at latest (unverified); knomad.org/data/remittances redirects to a worldbank.org brief.
- UN Comtrade India services (EBOPS) by partner only go to 2023. For services by partner, only the RBI ITES survey (destination shares) is current.

**Verifier:**

- WebSearch budget for this session was exhausted (200/200) before verification, so three things could not be checked: the June 2026 DPIIT factsheet (press report), the absence of a 7th-round remittance survey, and the data.gov.in licence/vintage.
- I made one GET to a data.gov.in catalog page (it timed out) before deciding not to proceed; robots.txt there is 'Disallow: /'. No further requests were made.
- RBI robots.txt returns HTTP 418 'Unauthorised Access', so the robots rules cannot be read.
- RBI Bulletin Current Statistics tables (No. 34 NRI deposits, No. 36 LRS outward remittances) are PDF-only on rbidocs.rbi.org.in, which returns a bot challenge to scripts. There is no HTML route except annual HBS tables or DBIE.
- HBS T190 (monthly services trade) has a duplicate 'March-2020' row label (the Feb-2020 row is mislabelled). The parser must not key on month labels alone.
- IMF SDMX API returns OBS_VALUE in US$ units while the series declares SCALE="6". The ingestion code must not apply the scale again.
- UN Comtrade India data originate from DGCI&S. Comtrade terms allow not-for-profit visualisation, but DGCI&S's policy governs the national source. Ask DGCI&S whether a Comtrade-sourced public display needs its permission.
- DPIIT country and sector FDI detail is equity-only and provisional; total FDI by country/sector needs RBI FLA (stocks) or estimation.
- KNOMAD has been discontinued per the World Bank brief ('active from 2013 until 2024'), so no maintained bilateral remittance matrix exists as a fallback.
- The finder's scratchpad folder (scratchpad/ext) was shared with this verifier; I re-downloaded every file I relied on rather than reusing the finder's files.

**Reference-year corrections:**

- National accounts on the new 2022-23 base (NSO via HBS 2025-26 T1) have NO 2025-26 values yet for primary income from RoW, other current transfers from RoW, gross saving, gross capital formation or consumption of fixed capital (all '-'). BoP 2025-26 (P) exists, but the national-accounts/RoW closure for 2025-26 does not. 2024-25 is the latest year with both: NAS current transfers from RoW (net) ₹10,53,958 cr = BoP T127 1.C.1 net exactly; NAS primary income (net) -₹4,09,303 cr vs BoP -₹4,09,118 cr. Recommend 2024-25 as the external-block reference year unless NSO publishes 2025-26 RoW and saving items first.
- RBI FLA census: latest published round is 2024-25 (Oct 29, 2025). The 2025-26 round is compiled (the MF survey used it for AMCs) but unpublished, so FDI/ODI stocks by country and sector are only available for 2024-25.
- DPIIT factsheet: 2025-26 country and sector detail covers FDI EQUITY only (US$58,846 mn, excl. NRI schemes), not total FDI. Reinvested earnings and other capital by country/sector are not available from DPIIT.
- UN Comtrade India monthly goods: latest is July 2026 (released 2026-09-18), not June 2026. Annual CY2025 confirmed (released 2026-07-10).
- ODI monthly: latest is August 2026 (released 2026-09-18). The finder's cited prid=63396/OFDI18082026.xlsx is July 2026.
- End-June 2026 external debt, end-June 2026 IIP and Q1 2026-27 invisibles were not released as of 2026-09-29. The previous-year equivalents all came out on 2025-09-30, so all three are likely due 2026-09-30. Re-check before freezing the registry.
- GDP ratio series break: RBI restated debt/GDP (end-March 2024 18.5% to 19.2%; end-March 2025 19.1% to 19.8%). HBS T1 shows the new base only from 2022-23, so any ratio time series spanning pre-2022-23 years mixes bases.
- Remittance survey 2023-24 source-country shares are bank-channel shares (Table 1 '(Banks)'). Applying them to total BoP personal transfers for 2024-25 is an estimate and should be labelled so.

### union_fiscal

Verifier verdicts: {'corrected': 5, 'confirmed': 4, 'unverifiable': 2}

**Finder:**

- incometaxindia.gov.in returns HTTP 403 to all automated requests (curl with a browser UA, WebFetch), including robots.txt. The CBDT Time Series and ITR statistics could not be fetched or licence-checked.
- incometax.gov.in/iec/foportal/statistics-data returned HTTP 500 (curl and WebFetch).
- www.gst.gov.in serves an F5 JS bot-challenge to curl (not bypassed). Its Terms and Conditions prohibit web scraping. The data files are directly downloadable from tutorial.gst.gov.in.
- GSTN statistics XLSX excludes compensation cess. PIB monthly GST press releases stopped after the May-2024 data (secondary source: BusinessToday 3 Jul 2024).
- The DEA Economic and Functional Classification of the Central Budget has no edition after 2017-18. The economic classification for the SAM year must be rebuilt from CGA object heads, AFS major heads and Expenditure Budget statements, and cross-checked with MoSPI NAS general-government accounts.
- The Budget 2026-27 and Economic Survey 2025-26 %-of-GDP ratios use old-base GDP (2011-12). MoSPI's 2022-23-base series (27 Feb 2026) puts 2025-26 nominal GDP at 346.36 lakh crore vs the 357.14 lakh crore used by the Budget.
- Possible data error: CGA Provisional Accounts 2025-26 'Recovery of Loans' = 24,617 cr, identical to the 2024-25 actual in Budget 2026-27. A verifier should check it.
- www.dea.gov.in fails TLS (schannel SEC_E_WRONG_PRINCIPAL, certificate name mismatch). dea.gov.in without www works.
- doe.gov.in had an intermittent TLS handshake failure; it succeeded on retry with TLS 1.2.
- indiabudget.gov.in and CGA return 404 for HEAD requests on existing files; GET works. Freshness checks must use GET or ranged GET.
- openbudgetsindia.org (CBGA open budget portal) is compromised or lapsed: it redirects to indiabullsmf.com and serves a 'Casino Sites India' page. Do not use it.
- The data.gov.in catalog page is JS-rendered (WebFetch 403; curl shows 'No Result Found'). The footer oddly says it is a 'sandbox environment'. Contents unverified.
- No GODL licence on any Union fiscal source site. indiabudget.gov.in and DEA require permission to reproduce; the GST Council requires permission by email; the CGA copyright page is empty.
- CBIC website is a JS app with no structured customs or excise revenue statistics found. Product-level customs revenue is not available from this family.
- Status Paper on Government Debt 2024-25 not yet published (latest 2023-24). The DEA quarterly debt report for Apr-Jun 2026 was not posted as of 2026-09-29.
- Monthly direct-tax collection updates for 2026-27 (e.g. Rs 12.12 lakh crore to 17 Sep 2026) were seen only in secondary media; the primary release channel is unverified.
- The Chrome browser extension was not used for blocked sites: 4 browsers were connected and choosing one needs the owner's input.

**Verifier:**

- CGA monthly and PA pages: the '(Details)' links for Tax Revenue, Non-Tax, Non-Debt Capital Receipts and Total Expenditure are broken (HTTP 404 at both /MonthlyReport/Published/{m}/ and /MonthlyReport/Published/; some hrefs point to file:///D:/ paths). Tax-by-type and devolution detail are not available from the CGA page, only the headline table, financing and major subsidies.
- CGA PA 2025-26 'Recovery of Loans' = 24,617 cr, identical to the 2024-25 Budget actual; the COPPY 94.7% implies the prior year is also 24,617. Reproduced and unexplained; ask CGA.
- CGA vs Budget 'actuals' differ for 2024-25 Urea subsidy: 120,879.83 (CGA PA page COPPY) vs 117,872.96 (Expenditure Budget stat7).
- Budget XLSX internal inconsistencies: Revenue Receipts A 2024-25 is 3036613 (BAAG) vs 3036619 (Receipts sheet); Fertiliser BE 2026-27 is 170781 (BAG) vs 170799 (stat7). The site states that PDFs prevail over the system-generated Excel.
- indiabudget.gov.in Last-Modified headers are unreliable (allafs.xlsx LM 2024-08-07 with 2026-27 content). tutorial.gst.gov.in files all show LM 2026-09-25 (bulk sync). Detect freshness from content, not headers.
- Expenditure Budget statements 27 and 27a have no XLSX (404); PDF only.
- GSTN state-wise sheets label imports 'IGST and CESS on Import' and export refunds 'IGST and CESS Refund on Exports'. The inclusion of compensation cess in the import/refund figures is ambiguous and must be reconciled with major head 0009 before use.
- GSTN monthly PDF comparators use REVISED ex-cess prior-year figures (Aug-25 = 1,74,116), not the originally published headline. The time series must be built from GSTN files, not press archives.
- incometaxindia.gov.in blocks every automated request (403, including robots.txt); incometax.gov.in statistics page returns 500. The CBDT time series, ITR statistics and monthly 'Direct tax collections as on' PDFs all need a manual download by the owner.
- CBDT direct tax/GDP ratios (6.73% for 2024-25) use old 2011-12-base GDP (22.26/0.0673 ≈ 330.8 lakh cr).
- Search results show a CBDT FAQ on transition to the 'Income-tax Act, 2025'. Future ITR statistics may switch from Assessment Year to 'tax year' labelling. Unverified; the site is blocked.
- DEA 'Indian Public Finance Statistics' listing (dea.gov.in/reports-public-finance-statistics) shows 'No Data Available'. It cannot substitute for the stale EFC.
- The PIB halt of monthly GST press releases (July 2024) is documented only by secondary media (ThePrint, BusinessToday). No official notice was found.
- The CGA site footer says 'All rights reserved' while the Copyright Policy page is empty. Treat it as not openly licensed until CGA clarifies.
- Cross-family pointers not verified here: MoSPI NAS general-government accounts on the 2022-23 base and the RBI Handbook/DBIE central government finance tables are the natural cross-checks for the rebuilt Union economic classification.

**Reference-year corrections:**

- DEA Economic and Functional Classification: the latest ACTUALS year is 2015-16, not 2017-18. The 2017-18 edition has columns 2015-16 (A), 2016-17 (RE) and 2017-18 (BE).
- CGA Accounts at a Glance 2024-25: the PDF Last-Modified is 2026-06-30, so it has been available only since about end-June 2026 (lag about 15 months, not about 9).
- CGA Finance Accounts 2025-26: the page /FinanceReport/Published/2025-2026.aspx exists but is empty as of 2026-09-29. Expect about Dec 2026, based on 2024-25 posting on 22-23 Dec 2025.
- GSTN FY 2025-26 totals (gross 22,27,095.73 cr; net 19,34,465.16 cr) are confirmed, but whether they exclude cess is unverified: import and export-refund lines are labelled 'IGST and CESS'.
- Economic Survey tab 2.3: 2024-25 is PA (FD 15,77,270), not the Budget Actual (15,74,431). Use the Budget or Finance Accounts for the SAM year.
- CAG audit of Union Government Accounts 2024-25 (Report 6 of 2026) exists, so 2024-25 is the latest fully audited AND audit-reviewed Union year. 2025-26 has CGA PA only (FD 15,19,169 cr); Budget actuals for 2025-26 arrive with Budget 2027-28 (about 1 Feb 2027).
- PPAC petroleum exchequer contribution is available to 2025-26 (P), with 2024-25 final.

### state_fiscal

Verifier verdicts: {'confirmed': 10, 'corrected': 4}

**Finder:**

- rbidocs.rbi.org.in (all RBI XLSX and PDF files for State Finances, Handbook of Indian States, Municipal and PRI finances) returns an F5/TSPD JavaScript challenge to curl and an image CAPTCHA to WebFetch. Not bypassed. Automated ingestion is impossible without owner action.
- RBI Terms of Use prohibit caching, framing and deep-linking without written permission. This conflicts with the plan to link every figure to its source.
- CAG machine-readable Finance and Appropriation Accounts data ('FA&AA data') is on SharePoint behind Microsoft login. Public CAG data is PDF only.
- fincomindia.nic.in/copyright_policy has no policy text (curl 200 with an empty body; WebFetch 403). No explicit licence is stated for the FC16 data files.
- WebFetch returns 403 for indiabudget.gov.in, pib.gov.in and mospi.gov.in. curl works for indiabudget and PIB. The MoSPI press-note PDF returns 403 even to curl.
- cag.gov.in/en/state-accounts returns 404 (the correct path is /en/state-accounts-report). prsindia.org/terms-of-use returns 404. gstcouncil.gov.in/gst-revenue-collection returns 404. openbudgetsindia.org RBI organisation page returns 404.
- gst.gov.in/download/gststatistics embeds a CAPTCHA. The monthly GST PDF filename changes each month.
- data.gov.in: first request timed out, retry returned 200. The GODL licence page path redirected to page_not_found. No state-fiscal dataset on data.gov.in was confirmed.
- Contradiction: UP's Aug 2026 devolution is 19,208 crore per PIB versus 17,908 in a secondary report. Use PIB.
- Quirk: FC16 KFI year headers ('2024') mean FY 2023-24.
- Quirk: the FC16 ULB dump appears to be in rupees while the other FC16 files are in Rs crore.
- Quirk: the RBI SF 2025-26 and FC16 %-of-GDP ratios predate the 2022-23-base GDP (27 Feb 2026), so they use the old base. State GSDP is moving to the new base during FY27.
- Quirk: PRS UP 2026-27 analysis shows GSDP growth of 28% over 2025-26 RE, which looks anomalous and may reflect a base or projection issue.
- Unverified: RBI SF file units (crore vs lakh), because the files could not be opened; the exact set of states with 2024-25 CAG Finance Accounts; FC16 Table 8.9 state shares (secondary: UP 17.939% to 17.619%); 2026-27 BE devolution of Rs 15,26,255 crore (search snippet only); structure of eGramSwaraj reports; the CAG dashboard export capability.
- PFMS has no public bulk report on state-wise releases; it is login-gated.

**Verifier:**

- Finder missed the CAG State Finances 2024-25 publication (16 Jun 2026). Its 'latest audited all-state year = 2023-24' is wrong.
- The CAG SF 2024-25 data is published only as a Tableau Public workbook on a personal profile plus a press release. No PDF or annexure was found. Its provenance and reuse terms need confirming with CAG.
- CAG machine-readable MKI Excel files (the 'Click Here' links) are on SharePoint behind a Microsoft login, the same as the FA&AA data. Tested with curl only.
- The Goa, Delhi and Puducherry CAG state-accounts pages are empty. Goa accounts must be sourced elsewhere (AG Goa site not checked).
- The FC16 KFI has zeros for all debt and public-account flow rows and excludes UTs. FC16 subsidies cover only 21 states plus Union.
- Statement 18 mixes grants and loans (EAP loans, SASCI). CSS there includes releases to implementing agencies outside state treasuries, which is a Centre-to-State reconciliation gap in the SAM.
- openbudgetsindia.org now redirects to unrelated commercial or casino sites. Do not use or link it.
- No explicit licence was found for fincomindia.nic.in (empty copyright page), indiabudget.gov.in (terms of use have no reproduction clause) or PIB (copyright URL errors). Only PRS (CC BY 4.0) and CAG (reproduce with acknowledgement) have clear reuse terms. RBI prohibits deep links without permission.
- The state GSDP migration to the 2022-23 base is attested only by a secondary source (devdiscourse, 7 May 2026). All state fiscal %GSDP ratios in RBI SF 2025-26, FC16 and CAG SF 2023-24 use the old base. The base behind CAG SF 2024-25's 15.78% ratio is unverified.
- RBI SF file units (crore vs lakh) remain unverified because of the bot wall.
- The WebSearch budget ran out mid-verification, so remaining checks used curl only.

**Reference-year corrections:**

- CAG State Finances: the latest year available is 2024-25 (audited, all 28 states; published 16 Jun 2026), not 2023-24.
- CAG Finance Accounts: 2024-25 is posted for all states except Goa (the Goa, Delhi and Puducherry pages are empty), not just 'many states'.
- CAG MKI: the latest month varies by state. August 2026 for 22 states (including UP, not July); July for Arunachal and Nagaland; May 2026 for Manipur; none for Goa.
- FC16 Transfers: 2023-24 onward is Union Budget Statement 18 data (Centre-side), not state-account actuals. The latest state-account actuals in that file are 2022-23 (RBI).
- FC16 KFI: the latest year is 2023-24, but it has no debt or public-account flow data (all zeros) and no UTs. The financing block for any year still needs RBI or CAG.
- Implication: the state-government block supports a 2024-25 reference year now (from CAG PDFs and dashboard) and machine-readably after the next RBI SF edition, expected around Dec 2026 to Jan 2027 (inferred). Local bodies are the binding constraint: ULBs to 2023-24; PRIs (RBI) only to 2022-23.

### markets_finsector

Verifier verdicts: {'corrected': 8, 'confirmed': 6}

**Finder:**

- NSE Terms of Use prohibit automated collection, reproduction and use 'for any gaming, virtual trading or simulation activities': this directly conflicts with the project's ABM/simulator. Do not use nseindia.com data directly.
- BSE terms/disclaimer pages are JS-rendered and WebFetch returned 403. The prohibition on reproduction/redistribution was seen only in a search-engine snippet of https://www.bseindia.com/static/about/disclaimer.htm (unverified by direct fetch).
- NSDL FPI Monitor disclaimer: 'Reproduction, redistribution and transmission of any information ... strictly prohibited'. The DII report endpoint (DIIGenerateReport.aspx?Rep=L) and Index.aspx returned 'Request Rejected' (WAF, support ID 18072527208414543657). Excel export is by postback only.
- AMFI Terms of Use limit use to personal, non-commercial use and forbid publishing, derivative works and electronic storage of 'any significant portion'. Republication requires permission.
- SEBI website policy requires permission by e-mail before reproduction; tables sourced from NSE/BSE/NSDL/AMFI may count as third-party material.
- CCIL Terms of Use prohibit automated collection and commercial use without written consent. The Rakshitra monthly page showed 'temporarily unavailable'. CCIL data services are paid, price not stated.
- rbidocs.rbi.org.in serves an F5 TSPD JavaScript challenge to curl and a CAPTCHA to WebFetch for RBI Handbook XLSX files (T107 ownership, T213 CP, T214 CD, T61, T68, T181). Not bypassed; contents unverified.
- RBI Weekly Statistical Supplement page (https://www.rbi.org.in/Scripts/WSSView.aspx) returned 'Error occured. Please try again.' RBI Bulletin pages use ASP.NET postbacks; DBIE (dbie.rbihub.in/tables) is a JS SPA with no static table IDs.
- The MOSPI press note PDF on the new GDP series (base 2022-23) returned HTTP 403 to curl and WebFetch. The base-year change was confirmed indirectly (search title; RBI HBS 2025-26 table titles).
- The RBI HBS 2025-26 still lists 'Institutional Sector-Wise Gross Capital Formation (At Current Prices) (Base Year: 2011-12)'. Institutional-sector/Flow of Funds data may lag the 2022-23 base, which affects the reference-year choice (for the RBI/NAS families to confirm).
- SEBI Handbook T11 (outstanding corporate bonds) shows an apparent reclassification break between 2023-24 and 2024-25 (listed non-financial drops from Rs 1,467,027 cr to 1,053,958 cr while financial rises sharply). To be logged in ISSUES.md.
- SEBI Bulletin layout drift: the Sep 2026 T56 dropped the cumulative-FPI column present in the Aug 2026 T56. File names change every month; xlsx contain formulas (cached values needed).
- IRDAI Handbook T20 interleaves growth-rate rows with inconsistent sign/parenthesis formatting (+13.8% printed as '-13.83'). Growth rows must be ignored and recomputed.
- PFRDA xlsx files do not state units (Rs crore inferred from M2/M6 consistency). The annual A-series lags the monthly series (A2 stops at Mar-2025).
- AMFI vs SEBI MF AUM differ slightly (Jul-2026: SEBI 8,575,626.6 vs AMFI 8,575,656.52 per news).
- nsdl.co.in (depository site) is in a 301 redirect loop, so NSDL depository statistics were not reached. The CDSL disclaimer page had no static text, so its licence is unverified.
- EPFO audited annual accounts lag ~3 years (latest 2022-23). The EPFO CDN upload folder dates (2025/08) are migration dates, not release dates, so the exact Annual Report 2024-25 release date is unverified.
- irdai.gov.in and npstrust.org.in return 403 to HEAD requests (GET works for IRDAI). Pipelines must use GET.
- No source in this family publishes under GODL-India/NDSAP. The data.gov.in presence of SEBI/AMFI/PFRDA datasets was not confirmed (search pointed to third-party aggregators).
- CP/CD issuance data (RBI HBS T213/T214, DBIE fortnightly) could not be verified in this family; FIMMDA's site is a frameset with no data catalogue found.

**Verifier:**

- DEA licence was wrong in the recon: DEA Copyright Policy says content 'may not be reproduced partially or fully, without due permission' and asks for e-mail permission. Add DEA to the access requests.
- SEBI's permission explicitly excludes third-party copyright material. SEBI tables sourced from NSDL (T56/T59/T60), AMFI (HBS T72) or BSE/NSE (T14) may still need those holders' authorisation, which weakens the 'use SEBI aggregates instead of NSDL/AMFI' workaround.
- RBI Disclaimer: 'caching and links to, and the framing of this Web Site or any of the contents are prohibited'. Deep links to internal RBI pages need prior permission. This affects the website's per-flow source links and raw-data caching (cross-family, RBI).
- SEBI Bulletin T1 Mcap/GDP denominator changed between issues (Aug: FY26 PE ₹346.36 lakh cr → 140.73; Sep: Budget FY27 ₹393 lakh cr → 125.08). Never splice T1 ratios across issues; recompute from Mcap and official GDP.
- AMFI vs SEBI discrepancy is directly verified: Jul-2026 AUM 8,575,656.52 (AMFI) vs 8,575,626.60 (SEBI); Aug-2026 gross/net flows differ by ~30 cr (41,353.60 vs 41,383.43). Mar-2026 matches exactly. Pick one canonical source and log the difference.
- DEA ownership 'Others' category mixes State Governments, DICGC, PSUs, Trusts, Foreign Central Banks and HUF/Individuals. It cannot be assigned to households or RoW without an estimate.
- The SEBI Handbook T11 corporate-bond reclassification break (2023-24 → 2024-25: listed NFC 1,467,027 → 1,053,958; listed FC 2,331,582 → 3,201,537; issuers 4,178 → 5,384) is confirmed and must be logged.
- BSE terms/disclaimer remain unverifiable (Angular shell, WebFetch 403). The MOSPI new-series press note returns 403. data.gov.in is a JS SPA, so GODL coverage of SEBI/IRDAI/PFRDA datasets is unverified. This session's WebSearch budget was exhausted, so no search corroboration was possible.
- nsdl.co.in depository site: infinite 301 to itself even with a cookie jar; WebFetch ECONNRESET. The CDSL licence is still unverifiable.
- NBFCs are in SPEC scope ('non-bank financial sector') but absent from this finder's output. They are covered in recon/rbi_core.md (sectoral NBFC credit, FSR Jun-2026, Trend & Progress 2024-25), so ownership must be assigned to the RBI family explicitly.
- The finder's claim that SEBI T1 ratios use 'GDP (now the 2022-23 base)' is unverified: the T1 notes cite the PE/Budget GDP figures without naming a base year.

**Reference-year corrections:**

- FY2025-26 GDP Provisional Estimates: the SEBI Aug-2026 Bulletin T1 note says 'released on June 05, 2026', ₹346.36 lakh crore at current prices. The SEBI Sep-2026 Bulletin uses the Budget 2026-27 estimate ₹393 lakh crore for FY2026-27. Neither states the GDP base. Confirm with the MOSPI family.
- NSDL fortnightly sector-wise FPI data are available from 31 Jan 2012, not Jul 2022.
- DEA quarterly ownership: the latest is Mar-2026 (released 13 Jul 2026). The Apr-Jun 2026 report was not yet out on 2026-09-29. The archive goes back to at least 2022 (paginated listing).
- EPFO: FY2024-25 is covered only by the unaudited Annual Report 2024-25 (contributions ₹3,35,628.81 cr). The latest audited Consolidated Annual Accounts are 2022-23. The family summary 'FY2024-25 fully covered by every source' holds only if the Annual Report is accepted.
- PFRDA Handbook of NPS Statistics 2025-26 returns 404 (2024-25 edition Last-Modified 2025-10-14). The FY2025-26 annual A-series is absent. Use the M-series Mar-2026 rows.
- IRDAI Handbook: 4 consecutive editions came out in early Feb (2023-2026), so the FY2025-26 edition should arrive ~Feb 2027 (inference). IRDAI monthly non-life flash data to Aug-2026 was released 2026-09-15.
- MF asset composition by instrument (SEBI deployment page) stops at May 2025, so FY2025-26 year-end MF asset-side data is not available in this family.
- AMFI monthly archive begins Jul 1999, not Apr 1999.

### international

Verifier verdicts: {'confirmed': 9, 'corrected': 5}

**Finder:**

- The OECD ICIO page blocks WebFetch (HTTP 403). curl with a browser User-Agent returns 200.
- data.adb.org (ADB Data Library, including the MRIO dataset page and its terms) returns 403 with a Cloudflare JS challenge. I did not bypass it. The ADB MRIO licence is unverified. adb.org/what-we-do/data/regional-input-output-tables also returned 403 to curl.
- IMF data.imf.org home, the API page, imf.org/external/terms.htm and imf.org/en/about/copyright-and-terms return Akamai 403 'Access Denied'. The IMF licence was inferred only from the API LICENSE field ('All Rights Reserved') and a search snippet.
- The legacy IMF API host dataservices.imf.org does not resolve (curl exit 6). Any old code using it will fail.
- The IMF PIP India CSV response was truncated (pandas 'EOF inside string'). This needs paged or filtered queries.
- UN Comtrade public preview returned HTTP 429 'Rate limit is exceeded' on back-to-back calls. The full data API returns 401 without a subscription key.
- The UN AMA download server returns 404 to HEAD but serves the file on GET.
- The Zenodo REST API returned 403 'restricted due to unusual traffic'. The record HTML page worked via WebFetch.
- EXIOBASE licence contradiction: exiobase.eu states CC BY-SA 4.0, while the Zenodo record v3.9.6 states a customised non-commercial CC-BY-SA-NC derivative.
- Base-year vintage mismatch across international sources: ADB MRIO (Aug 2025), OECD ICIO 2025 and UN AMA (Jan 2026) reflect India's old 2011-12 base, while WDI and IMF ANEA are on the 2022-23 base. Structures from IO sources must be rescaled to new-base totals.
- Year-basis mismatch: WDI India years are FY (2024 = FY2024-25). IMF ANEA converts to calendar years. IMF BOP annual and Comtrade are calendar years. The pipeline must carry an explicit year_basis field.
- WDI current account 2025 (-16.49 bn USD) differs from IMF BOP 2025 CAB (-20.23 bn USD). The cause (FY vs CY or vintage) is unresolved.
- The OECD ICIO 2016-2022 zip has server Last-Modified 18 May 2026, later than the 'mid-January 2026' revision stated on the page. There may have been a silent re-upload. Record checksums in Phase 1.
- worldmrio.com (Eora1) said it would stay open only through 30 Jun 2026. It is still online on 2026-09-29 but may disappear.
- Not confirmed in this session: India inclusion in FIGARO and EXIOBASE (search snippets only); the GTAP 12 reference years (search snippet only); the ADB MRIO year convention (FY vs CY); WITS licence.
- The UNdata SNA detailed-tables Datamart URL tried (data.un.org/Datamart/Explorer.aspx?d=SNA) returned 404. Official country data tables were not probed.

**Verifier:**

- The recon's ADB licence access request is unnecessary: kidb.adb.org/terms grants commercial and non-commercial reuse with attribution. Remove it from access_requests.
- FIGARO licence is misstated as CC BY 4.0. Eurostat's copyright notice excludes non-EU/EFTA/candidate-country data (including India) from commercial reuse. If the site ever monetises, FIGARO India cells must be removed.
- All IO sources except FIGARO (OECD ICIO, OECD national IOTs, ADB) are on the old 2011-12 base. The FY2022-23 GVA level gap is -3.6% (₹246.47 → ₹237.64 lakh crore), and sector shares differ. IO structures must be rescaled to new-base totals and flagged as estimated.
- BIS licence includes a translation-disclaimer condition that the recon omitted. It matters for the planned Hindi version.
- The IMF copyright/terms pages (imf.org/external/terms.htm, /en/about/copyright-and-terms, data.imf.org) remain Akamai 403 to curl and WebFetch. The access request for a manual check stands. The per-dataset LICENSE field differs (ANEA citation string vs 'All Rights Reserved' for BOP/IMTS/GFS/WEO).
- The OECD BaTIS SDMX endpoint returned HTTP 500 for a partially specified key. Only the all-wildcard key worked, so pipelines should pull wide and filter locally.
- IMF DIP returns 403 when the key has the wrong number of dimensions (5 required). This is not an access block.
- The recon's MOSPI press-note URL (…1772189865181…27022026.pdf) returns 403. Use the '-F' URL recorded in recon/mospi_nas.md.
- ADB India IOT rows r62 (direct purchases abroad), r63 (non-resident purchases) and trs are all zeros. They cannot fill tourism/DPABR cells.
- ADB's annual August release did not happen in 2026: the latest files are still 'Updated on August 2025'.
- Not re-verified by me: IMF IIP to 2026-Q1, GFS_COFOG to 2018, PIP CSV truncation; the OECD/WTO note on India services-import over-reporting; the WTO API 401; the AMA HEAD-404 behaviour; EXIOBASE and GTAP India membership/source vintage; WITS licence.
- The web search quota was exhausted (200/200) before this verification. Every check used direct fetches, which left GTAP reference years and WID licence unverified.

**Reference-year corrections:**

- UN Comtrade monthly goods: latest period is 2026-07, not 2026-06 (202607 returned X = 44,302,522,916 USD; 202608 empty).
- WDI national accounts '2025' (₹345.47 lakh crore) is MOSPI's 27 Feb 2026 SAE vintage. It is superseded by the 5 Jun 2026 PE (₹346.36 lakh crore) and NAS 2026 of 31 Aug (₹345.37 lakh crore; FY22-23 revised to ₹261.77 lakh crore). Do not treat WDI as the latest vintage.
- WDI BOP series (e.g. BN.CAB.XOKA.CD) are calendar-year, not FY. They equal IMF BOP CY values for 2022-2024.
- ADB IOT/MRIO '2024' = FY2024-25 on the old 2011-12 base (high confidence, 0.005% match for 2022). No 2025-reference ADB table exists as of 2026-09-29.
- OECD ICIO 2025 / OECD national IOTs 2025 '2022' = FY2022-23, and the old base is certain: the final revision (mid-Jan 2026) predates the 27 Feb 2026 new series.
- Eurostat FIGARO: India confirmed to 2024 (naio_10_fcp_ii4, updated 2026-07-20), in EUR million, probably new-base CY-converted (inference). Non-commercial licence for India cells.
- EXIOBASE: latest is v3.10.2 (2026-05-13) with IOT files to 2024. Real SUT inputs run to about 2021 (FIGARO) and trade to 2022; later years are nowcasts.
- IMF WEO (missed): FY new-base India GDP actuals to 2025 plus projections to 2031, Apr 2026 vintage.
- GTAP 12 reference year (2023) is unverifiable from the fetched GTAP pages.

### prior_art

Verifier verdicts: {'corrected': 8, 'confirmed': 5}

**Finder:**

- rbidocs.rbi.org.in PDFs (e.g. RBI Bulletin June 2021 article) return a CAPTCHA page ('What code is in the image?') to both curl and WebFetch. Not bypassed; the rbi.org.in HTML versions were used instead.
- The RBI Monetary Policy Report April 2019 box (primary source of the 2.45/3.14 capex multipliers) could not be reached: the RBI MPR archive uses JavaScript __doPostBack links. The figures are verified only as quoted in the RBI Bulletin of Dec 2020.
- www.ncaer.org fails TLS with Windows schannel (SEC_E_ILLEGAL_MESSAGE, curl exit 35); ncaer.org without www works.
- www.ies.gov.in fails TLS with a certificate name mismatch (SEC_E_WRONG_PRINCIPAL, curl exit 60), so the Esha Swaroop expenditure multiplier paper is unverified.
- journals.sagepub.com returned HTTP 403 to WebFetch, so the NCAER SAM supplementary file (Margin journal) is unverified.
- IMF country report PDFs (CR 25/54, 25/55) returned 403 to curl. CR 25/55, obtained via WebFetch, is the FSAP FSSA and has no multipliers. No India-specific IMF fiscal multiplier estimate was verified.
- The IFPRI Dataverse terms are internally ambiguous: Section 3 restricts copying and republishing, while Section 4 grants CC-BY-4.0 by default. Treat the raw IFPRI SAM as cross-check only until IFPRI confirms redistribution.
- Every published Indian SAM (IFPRI 2022-23, NCAER 2021-22, CSEP 2019-20, CSTEP/IFPRI 2017-18) is on the old 2011-12 GDP series and old SUT/IOT vintages. Levels are not comparable with the new 2022-23 base series; only structure and multipliers are.
- The NAS PFCE vs NSS/HCES gap (45% in 2011-12 per the Adhikari Committee; about 54% in 2023-24 per EPW 2026) must be logged in ISSUES.md. HCES can supply distributions only, and the gap is concentrated in non-food items.
- No India-wide quantified remittance multiplier was found. The Phase 4 remittance cross-check will rely on our own SAM, with this literature gap stated.
- Published SAM 'output multipliers' (2–7) are gross-output sums across endogenous accounts and are not comparable with fiscal GDP multipliers (about 1–3.5). Phase 4 validation must compare like with like.
- The EPW 2026 figure ('nearly 54% in 2023-24') was taken from a paywalled page summary, not the full text.
- The CSEP landing page shows 22 Nov 2023 but the PDF says 'Embargoed till 12 pm, Friday, 13 January, 2023'. The publication date is ambiguous.

**Verifier:**

- Material: the finder's RBI capex figures (2.45 t / 3.14 t+1) come from a Bulletin paraphrase. The primary MPR April 2019 Box III.1 (reachable in HTML at id=18941, contrary to the finder's issue note) gives peak 3.25 (Centre capex), 2.00 (States capex), 0.45 / 0.82 (revenue expenditure).
- Material: NCAER 2021-22 SAM sector description is wrong. It has 39 producing sectors in total, including the energy sectors. The WP itself also says '30 production sectors' in one place and misuses 'decile' for quintile.
- The CGSpace bitstream URLs the finder gave as 'data paper PDF' are the extracted-text (.txt) bundles. The real PDFs are ff7b1ece-8897-4567-be3a-4c99db75dca3 (2022/23) and a separate ORIGINAL bitstream for 2017-18.
- IFPRI licence is stronger than the finder reported: CGSpace dataset record 10568/163735 is explicitly CC-BY-4.0, and the ToU Section 3 restrictions are expressly subject to Section 4 (CC-BY-4.0). The Section 5 adaptation disclaimer remains mandatory. Asking IFPRI-Data@cgiar.org is still prudent because of the Section 6 third-party (MoSPI/IMF) content.
- Unreported IFPRI quirk: the enterprise/household savings split is assumed (equal savings rates after depreciation), so the 49,632 / 47,714 split must not be used as an observed benchmark.
- The IFPRI 2017-18 Dataverse file was served by the API (303 to S3) without a guestbook response, although guestbook 9 is configured. I did not follow it. The owner should still complete the guestbook through the UI to respect the intended terms.
- The CSEP multipliers (Table 11) come from an aggregated ESAM (32 labour / 40 households), not the full 318/80 ESAM.
- The CSEP 'embargoed till 13 Jan 2023' claim could not be reproduced from the current PDF, so it is unverifiable.
- CSTEP SAM has 4 tax accounts (including atax), not 3. CSTEP Table 1 is a partial catalogue, not 'all published Indian SAMs'.
- '6 tax accounts' in the IFPRI India 2022/23 SAM is unverifiable: the file is gated by guestbook 380 and only the generic Nexus template lists 6.
- ies.gov.in: www.ies.gov.in fails the certificate name check (curl 60; WebFetch: 'not in the cert's altnames: DNS:ies.gov.in'). https://ies.gov.in/pdfs/Seminar_Paper_EshaSwaroop.pdf returns HTTP 404. The Esha Swaroop paper remains unverified.
- BIS Papers 122 India chapter (bispap122_j.pdf) now redirects to an HTML landing page, so its content was not checked.
- The web-search budget (200 calls, shared across the session) was exhausted during verification. The IMF India fiscal-multiplier search and an exhaustive remittance-multiplier search could not be completed.
- MOSPI SUT publication page is JavaScript-rendered (curl shell 2.6 KB), so the SUT files and the licence could not be inspected from this family. That belongs to the NAS/SUT family.

**Reference-year corrections:**

- IFPRI Nexus SAM India: latest year 2022/23 confirmed. No newer national IFPRI SAM exists on Dataverse as of 2026-09-29, and none on the new 2022-23 base series.
- MOSPI SUT: latest year 2023-24 confirmed (SUT 2022-23 and 2023-24 on base 2022-23, released 15 May 2026). Add the dimensions: 155 products x 67 industries.
- Fiscal multiplier benchmarks: the RBI estimate is RBI MPR April 2019, sample 1980-81 to 2017-18, peak Centre capex 3.25 and States 2.00; revenue expenditure 0.45 (Centre) and 0.82 (States). Update the Phase 4 band to 'capex about 2–3.25 (RBI SEM), up to 3.56 cumulative (Jain-Kumar SVAR); revenue expenditure about 0.2–1.0'.
- NIPFP WP 2013-125 sample: annual 1991-2012, not 1990-2012.
- Jain & Kumar 2013 sample: annual 1980-81 to 2011-12.
- The EPW 2026 'nearly 54% in 2023-24' gap implies HCES 2023-24 is available. The IFPRI SAM uses HCES 2022-23. The latest HCES vintage should be confirmed by the household-survey family (not verified here).

## Phase 0: registry check (independent checker), all addressed in the fix pass

- [major] data/registry.yaml: rbi_state_finances_study (key_series, base_year_price_basis); SOURCES.md §6.3 ('Units in RBI State Finances XLSX (crore vs lakh): the files could not be opened past the bot wall'): 1. The units are recorded as unverified on the grounds that the files could not be opened. They can be opened, and the units are readable.
2. key_series says Statements 1-37 including 'Tax revenue (14)' are in Rs crore. Statement 14 is actually in per cent.
3. The registry's own access note says files are served with ordinary browser headers, which contradicts §6.3.
- [major] data/registry.yaml verification.status on fimmda_cp_cd_traded, nse_bse_market_data, ppac_petroleum_exchequer, wb_wits_trains, cdsl_periodic_stats, pib_tax_devolution_releases, cmie_cphs (and egramswaraj_panchayat_accounts = corrected); SOURCES.md header count 'verified 99': The file header defines 'verified' as 'verifier confirmed'. These entries are marked 'verified' although their licence and/or latest_release was never checked or confirmed. The headline count of 99 verified entries therefore overstates what was confirmed. This breaks SPEC rule 2 (confirm the latest release and licence before relying on a source).
- [minor] data/registry.yaml: required fields present but empty: Every key exists, but several required fields are empty:
- quirks is empty in 21 entries.
- formats is an empty list in mospi_nhis_2026.
- latest_release.date is null in 19 entries, including ones marked verified (dgcis_trade, bis_stats, oecd_tiva_2025, oecd_wto_batis, eora_mrio, undata_sna_institutional, nss_cms_education_2025, mospi_state_gsdp, rbi_dbie).
- [minor] data/registry.yaml: gstn_gst_statistics and gst_monthly_state_revenue latest_release.date = '2026-09-25': The recorded release date is the server Last-Modified time of a bulk file sync, not the publication date. The entry's own quirk says so ('File Last-Modified 2026-09-25 on all files (bulk sync)'), and release_lag claims '~1-2 days' for the PDF. As recorded, the August report appears to have come out 25 days after month-end, which would mislead the Phase 6 scheduler.
- [minor] data/registry.yaml: mospi_asuse (latest_release, access.requires): 1. latest_release.date is 2026-03-24, but the entry's own description cites a later release (the quarterly bulletin of 28 Sep 2026).
2. MoSPI's release feed shows another ASUSE 2025 publication on 10 Sep 2026 that the entry does not mention.
3. access.requires is 'none', but the unit data needs registration, and SOURCES §5 lists it as an owner action.
- [minor] data/registry.yaml: cbdt_time_series access.requires = 'none'; SOURCES.md summary table Access column: The summary table says CBDT needs no access arrangement. But SOURCES §5 item 7 makes the owner responsible for a manual browser download, because the site returns 403 to automated clients. The 'requires' field understates what access actually needs.
- [minor] data/registry.yaml license.url on all MoSPI entries; rbi_remittances_survey and rbi_bulletin_capex_multipliers license: Two licence URLs point to documents that don't contain the terms they are cited for.
1. MoSPI entries cite the GSDD 2026 Gazette PDF. The Gazette defines access categories ('shared free of cost') but has no reproduction or attribution clause. That clause ('reproduced accurately ... source must be prominently acknowledged') is only in the MoSPI copyright-policy API.
2. The RBI Bulletin licence quotes the September 2026 imprint ('(c) Reserve Bank of India 2026') and applies it to articles from March 2025, December 2020 and June 2021, whose own issues were not checked.
- [minor] SOURCES.md §2 fact 6 ('rebasing lowered the level by 2.65%'): The 2.65% compares the old series with the later NAS 2026 vintage (2,61,77,001). MoSPI's own comparison at the time of rebasing gives -2.9% (26890473 to 26117627). Using the -2.65% figure mixes a rebasing effect with a later revision.
- [minor] data/registry.yaml access.notes for rbidocs sources; SOURCES.md §5 ('No ... bot challenge was bypassed'): 1. Whether the F5/TSPD JavaScript challenge appears depends on the request headers. When it does, the response is still HTTP 200, with an HTML page instead of the file, so status checks cannot detect a failed download.
2. The documented method is to send ordinary browser headers so that the challenge doesn't appear. The owner should confirm this is acceptable under the RBI Disclaimer ('reserves all right to deny or restrict access'). RBI robots.txt returns 418 'Unauthorised Access', so robots rules cannot be read at all.
- [minor] data/registry.yaml: cag_state_finances_publication latest_release.date = '2026-06-16'; SOURCES.md §2 fact 12 and §6.2: No source is cited for the 16 Jun 2026 release date. The landing page shows no release date (only 'Last Updated: 30/07/2026'), and neither the finder nor the verifier evidence quotes one.
- [minor] data/registry.yaml: mospi_iott_2007 urls.landing (and MoSPI landing-page checks generally): The MoSPI site answers every path, including nonexistent ones, with a 200 status and the same 2,644-byte page shell. So HTTP 200 does not show that a MoSPI landing URL exists. The IOTT landing uses an old-style '/publication/...' path, which is likely dead in the new site.
- [minor] Coverage vs SPEC §4 (Firms public/private; Government borrowing) - absent from both files, no explanation: Two relevant official sources are missing and their absence is not explained:
1. DPE Public Enterprises Survey (CPSE accounts), relevant to the public vs private non-financial corporation split.
2. National Small Savings Fund accounts, relevant to household-to-government financing, which is large: 'Securities against Small Savings' was Rs 4,29,502 crore in 2024-25 Actuals.
The NAS 2026 statements 7.1A/7.1B and the Budget cover these partly, but SPEC §5 asks for better sources to be added or their absence explained.

## Phase 0: design critiques

All 44 points and their dispositions are in `docs/phase0/DESIGN_REVIEW.md`. Stack review points (17) are in `docs/phase0/STACK_AND_REPO.md` §11.

